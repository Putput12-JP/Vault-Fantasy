#!/usr/bin/env python3
"""CFB head-to-head scoreboard: our model, the previous model, JP+ and the opening line, graded on the same finished games.

Why this exists: "better than JP+" needs a fair test. The JP+ site shows its spread for finished games too, and there is no way to tell whether that number was
published before kickoff. So every run reads the JP+ games page and records each game's JP+ spread BEFORE kickoff in data/jpplus_games.json; once a game has kicked
off its number is never touched again. A game first seen after kickoff is kept but marked unverified.

  data/jpplus_games.json   one row per game: JP+ spread (home side, + = home favoured), JP+ total, first/last time seen before kickoff, verified yes/no
  data/cfb_scoreboard.json the scoreboard: for weeks 4+ finished games with every number present, per method (ours, previous, JP+, the open line)
                           the average miss, the lean record (which side of the open each method is on, did it cover) at 0+, 3+ and 5+ points, with a 95% interval.
                           Two tiers: "verified" (JP+ recorded before kickoff by this job) and "published" (JP+ as the site shows it now).

Our numbers are the board's frozen projections in data/cfb_model.json; the open line is ESPN's recorded open (data/cfbd/espn_opens_2026.json), else CollegeFootballData's.
Run: python3 scripts/cfb_scoreboard.py        Needs pandas + pyarrow (sportsdataverse schedule for game ids and finals).
"""
import json, math, os, re, sys, tempfile, time, urllib.request
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_model as cm

ROOT = cm.ROOT
JP_URL = 'https://www.jpplusratings.com/games/'
STORE = os.path.join(ROOT, 'data', 'jpplus_games.json')
OUT = os.path.join(ROOT, 'data', 'cfb_scoreboard.json')
MIN_WEEK = 4
METHODS = [('ours', 'Our model'), ('v1', 'Previous model'), ('jp', 'JP+'), ('open', 'Opening line'), ('close', 'Closing line')]
BENCH = ('open', 'close')           # lines, not methods: they get an average miss and no lean record
REPORTED = os.path.join(ROOT, 'data', 'jpplus_reported.json')


def fetch_jp():
    """the JP+ games page's embedded game list (Next.js flight data); None when the page changes shape or is unreachable"""
    req = urllib.request.Request(JP_URL, headers={'User-Agent': 'Mozilla/5.0 (vault-fantasy scoreboard)'})
    html = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
    t = ''.join(json.loads('"' + c + '"') for c in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S))
    i = t.find('"games":[{"game_id"')
    if i < 0: return None
    arr, _ = json.JSONDecoder().raw_decode(t[i + 8:])
    return arr


def iso_epoch(s):
    try: return int(pd.Timestamp(s).tz_convert('UTC').timestamp()) if pd.Timestamp(s).tzinfo else int(pd.Timestamp(s, tz='UTC').timestamp())
    except Exception: return None


def update_store(store, games, now):
    """record JP+'s number before kickoff, never after. Returns how many games changed."""
    n = 0
    for g in games:
        if g.get('jp_spread') is None or g.get('game_id') is None: continue
        gid = str(g['game_id']); k = iso_epoch(g.get('kickoff_at')); row = store.get(gid)
        pre = k is not None and now < k
        if row is None:
            row = store[gid] = dict(week=g.get('week'), home=g.get('home_team'), away=g.get('away_team'), kick=k, jp_spread=g['jp_spread'], jp_total=g.get('jp_total'),
                                    first_seen=now, verified=bool(pre), last_pre_kick=now if pre else None); n += 1
        elif row.get('verified') and pre and row.get('jp_spread') != g['jp_spread']:
            row.update(jp_spread=g['jp_spread'], jp_total=g.get('jp_total'), last_pre_kick=now); n += 1
        elif not row.get('verified') and not pre:
            if row.get('jp_spread') != g['jp_spread']: row.update(jp_spread=g['jp_spread'], jp_total=g.get('jp_total')); n += 1       # unverified rows follow the site
        if k is not None and row.get('kick') is None: row['kick'] = k
        if g.get('actual_margin') is not None: row['final'] = g['actual_margin']
    return n


def record(rows, key, th):
    """lean record against the open: the method's side of the open, did that side cover (pushes dropped), at edges of at least th points"""
    w = l = 0
    for r in rows:
        if r.get(key) is None: continue
        e = r[key] - r['open']; c = r['actual'] - r['open']
        if abs(e) < th or c == 0 or e == 0: continue
        if (e > 0) == (c > 0): w += 1
        else: l += 1
    lo, hi = cm.clopper_pearson(w, w + l) if w + l else (None, None)
    return dict(w=w, l=l, n=w + l, pct=round(w / (w + l), 4) if w + l else None, ci=[lo, hi])


def by_week(rows):
    """the scoreboard one week at a time (a week's games only), newest first"""
    return [dict(week=w, **summarize([r for r in rows if r['week'] == w])) for w in sorted({r['week'] for r in rows}, reverse=True)]


def official_picks(log):
    """our official pick log (graded at the line each pick was made at), overall and by week: the analogue of JP+'s selection engine"""
    out = {}
    for e in log or []:
        if e.get('result') not in ('W', 'L', 'P'): continue
        w = out.setdefault(e['week'], dict(w=0, l=0, p=0)); w[e['result'].lower()] += 1
    tot = dict(w=sum(v['w'] for v in out.values()), l=sum(v['l'] for v in out.values()), p=sum(v['p'] for v in out.values()))
    for v in list(out.values()) + [tot]: v['pct'] = round(v['w'] / (v['w'] + v['l']), 4) if v['w'] + v['l'] else None
    return dict(total=tot, weeks=[dict(week=w, **out[w]) for w in sorted(out, reverse=True)])


def summarize(rows):
    out = dict(games=len(rows), methods={})
    for k, label in METHODS:
        have = [r for r in rows if r.get(k) is not None]
        out['methods'][k] = dict(label=label, n=len(have), miss=round(sum(abs(r[k] - r['actual']) for r in have) / len(have), 3) if have else None,
                                 lean=record(have, k, 0.01) if k not in BENCH else None, edge3=record(have, k, 3.0) if k not in BENCH else None, edge5=record(have, k, 5.0) if k not in BENCH else None)
    return out


def main():
    now = int(time.time())
    store = json.load(open(STORE)) if os.path.exists(STORE) else {}
    changed = 0
    try:
        games = fetch_jp()
        if games: changed = update_store(store, games, now)
        else: print('JP+ page had no game list; store left as it was', file=sys.stderr)
    except Exception as e:
        print('JP+ fetch skipped:', type(e).__name__, e, file=sys.stderr)
    json.dump(store, open(STORE, 'w'), sort_keys=True)

    d = tempfile.gettempdir()
    sched = pd.read_parquet(cm.st.fetch(f'{cm.st.REL}/espn_cfb_schedules/cfb_schedule_2026.parquet', os.path.join(d, 'sched_2026_sb.parquet')),
                            columns=['game_id', 'week', 'home_id', 'away_id', 'home_score', 'away_score', 'status'])
    ids = {(int(r.home_id), int(r.away_id)): int(r.game_id) for r in sched.itertuples()}
    fin = {int(r.game_id): int(r.home_score) - int(r.away_score) for r in sched.itertuples() if pd.notna(r.home_score) and pd.notna(r.away_score) and 'final' in str(r.status).lower()}
    pbp = pd.read_parquet(cm.st.fetch(f'{cm.st.REL}/espn_cfb_pbp/play_by_play_2026.parquet', os.path.join(d, 'pbp_2026_sb.parquet')), columns=['game_id', 'homeTeamSpread'])
    closes = {int(r.game_id): float(r.homeTeamSpread) for r in pbp.drop_duplicates('game_id').itertuples() if pd.notna(r.homeTeamSpread)}      # the ESPN close, as a home margin (+ = home favoured)
    model = json.load(open(cm.OUT)); board = model.get('board', []); copens = cm.cfbd_opens(played=True)
    rows = []
    for b in board:
        if b.get('week', 0) < MIN_WEEK or b.get('model_margin') is None: continue
        gid = ids.get((b['home_id'], b['away_id']))
        if gid is None or gid not in fin: continue
        op = copens.get((b['home_id'], b['away_id']))
        if op is None: op = -b['open_margin'] if b.get('open_margin') is not None else None
        if op is None: continue
        j = store.get(str(gid))
        rows.append(dict(game_id=gid, week=b['week'], home=b['home'], away=b['away'], kick=b['kick'], actual=fin[gid], open=round(-float(op), 1), ours=b['model_margin'],
                         v1=(b.get('v1') or {}).get('model_margin'), jp=None if not j else round(-float(j['jp_spread']), 2), jp_verified=bool(j and j.get('verified')), close=closes.get(gid)))
    # JP+ spread is the home team's spread in the sportsbook convention (negative = home favoured), so the margin is its negation
    whole = [r for r in rows if r['jp'] is not None and r['v1'] is not None]
    ver = [r for r in whole if r['jp_verified']]
    out = dict(generated=pd.Timestamp.now('UTC').isoformat(), min_week=MIN_WEEK, jp_games_recorded=len(store), jp_verified=sum(1 for v in store.values() if v.get('verified')),
               published=summarize(whole), verified=summarize(ver), weeks=by_week(whole), picks=official_picks(model.get('log')),
               jp_reported=json.load(open(REPORTED)) if os.path.exists(REPORTED) else None,
               note='Verified: JP+ number recorded by this job before kickoff. Published: JP+ as its site shows it now, which cannot be shown to be pre-kickoff. Lean record: the method\'s side of the ESPN open covered.',
               games=sorted(rows, key=lambda r: -r['kick']))
    json.dump(out, open(OUT, 'w'))
    print(json.dumps(dict(jp_changed=changed, recorded=len(store), verified=out['jp_verified'], published_games=len(whole), verified_games=len(ver))))


if __name__ == '__main__':
    sys.exit(main())
