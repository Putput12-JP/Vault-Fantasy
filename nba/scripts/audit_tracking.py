#!/usr/bin/env python3
"""
Tracking audit: is everything the Vault NBA recorder is supposed to log actually logged, settled and shown?

Run it again after any slate (it only reads; it never writes to nba-data):

  python3 nba/scripts/audit_tracking.py                       # every regular-season day so far, reads nba-data from GitHub, writes a Markdown report to stdout
  python3 nba/scripts/audit_tracking.py --days=2026-10-21     # one ET day
  python3 nba/scripts/audit_tracking.py --cache=DIR --out=report.md

It does not need git (a bare `git fetch` of this repo hangs on a broken ref): files come from raw.githubusercontent.com/<repo>/nba-data/<path> with curl,
and ESPN's scoreboard / summary with curl too. Stdlib only.

What it checks, per finished game (ESPN scoreboard is the source of truth for "what was played"):
  A  Games    the game has a stored box score (results/<id>.json) and it still equals ESPN's box score now (a correction after the final is the
              one thing the recorder cannot see), has Minutes Lab / Game Simulation / Props Simulation rows, and its bets are settled.
  B  Records  what track.json shows for that day, record by record: cube, minutes_days, sim_days (three environments), gap_days, psim_days,
              held_days, held_bets_days, novig_days, signals, wire_days.
  C  Polls    every source's polls.jsonl for the day: polls, ok:false, the longest gap, the last good poll before each tip.
  D  Totals   cube = bets file = track.n, distinct picks, book / team / player spellings.
  E  Watchdog what scripts/watch_recorder_health.py would say about the last two days that have polls.
"""
import collections, datetime as dt, glob, json, os, subprocess, sys, tempfile, urllib.parse
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'scripts'))
ET = ZoneInfo('America/New_York')
REPO = 'Putput12-JP/Vault-Fantasy'
RAW = f'https://raw.githubusercontent.com/{REPO}/nba-data/'
SCORE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={}'
SUMMARY = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={}'
SOURCES = ['kalshi', 'espn', 'pinnacle', 'action', 'polymarket', 'injuries', 'lineups', 'prizepicks', 'underdog', 'sleeper', 'tape', 'novig', 'ledger']
GAP_MIN = 20                      # a gap between two good polls longer than this is listed


def curl(url, raw=False):
    p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '60', '-w', '\n%{http_code}', url], capture_output=True)
    body, _, code = p.stdout.rpartition(b'\n')
    if code != b'200':
        return None
    return body if raw else json.loads(body)


class Mirror:
    """Files of the nba-data branch, downloaded once into a cache folder."""

    def __init__(self, cache):
        self.cache = cache
        os.makedirs(cache, exist_ok=True)

    def get(self, path, fresh=False):
        p = os.path.join(self.cache, path)
        if fresh or not os.path.exists(p):
            body = curl(RAW + urllib.parse.quote(path), raw=True)
            if body is None:
                return None
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(body)
        return p

    def json(self, path, fresh=False):
        p = self.get(path, fresh)
        return json.load(open(p)) if p else None

    def lines(self, path, fresh=False):
        p = self.get(path, fresh)
        return [json.loads(l) for l in open(p) if l.strip()] if p else []


def fmt_et(t):
    return dt.datetime.fromtimestamp(t, ET).strftime('%b %d %H:%M')


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---' for _ in head) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)


def parse_stats(summary):
    """ESPN summary -> {athlete id: {stat: value} or None}, using the recorder's own parser."""
    import ledger
    got = ledger.parse_box(summary)
    return got[0] if got else None


def scoreboard(day):
    out = []
    j = curl(SCORE.format(day.replace('-', ''))) or {}
    for e in j.get('events', []):
        c = e['competitions'][0]
        t = {x['homeAway']: x['team']['abbreviation'] for x in c['competitors']}
        out.append({'id': e['id'], 'away': t['away'], 'home': t['home'], 'tip': int(dt.datetime.fromisoformat(e['date'].replace('Z', '+00:00')).timestamp()),
                    'state': e['status']['type']['state'], 'type': e['season']['type']})
    return out


def main(argv):
    args = {a.split('=')[0].lstrip('-'): (a.split('=', 1)[1] if '=' in a else True) for a in argv}
    cache = args.get('cache') or tempfile.mkdtemp(prefix='nba_audit_')
    M = Mirror(cache)
    track = M.json('track.json', fresh=True)
    status = M.json('status.json', fresh=True)
    ST = M.json('season_types.json', fresh=True) or {}
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    today = dt.datetime.fromtimestamp(now, ET).date()
    first = dt.date.fromisoformat(args['days']) if args.get('days') else dt.date(2026, 10, 20)
    last = dt.date.fromisoformat(args['days']) if args.get('days') else today
    days = [(first + dt.timedelta(n)).isoformat() for n in range((last - first).days + 1)]
    out = [f'# Tracking audit, read {dt.datetime.fromtimestamp(now, ET):%Y-%m-%d %H:%M} ET', '',
           f'track.json written {fmt_et(track["t"])} ET, status.json {fmt_et(status["t"])} ET.', '']

    # A + B ── games
    games = []
    for d in days:
        games += [dict(g, day=d) for g in scoreboard(d) if g['type'] == 2]
    fin = [g for g in games if g['state'] == 'post']
    out += [f'## A. Games ({len(fin)} final, {len(games) - len(fin)} not final yet)', '']
    meta = collections.defaultdict(lambda: collections.defaultdict(int))
    for d in sorted({fmt for fmt in (dt.datetime.fromtimestamp(g['tip'], ET).date().isoformat() for g in games)} | set(days)):
        for day_dir in (d, (dt.date.fromisoformat(d) - dt.timedelta(1)).isoformat()):
            p = M.get(f'snapshots/{day_dir}/meta.jsonl', fresh=(d >= today.isoformat()))
            if not p:
                continue
            seen = set()
            for line in open(p):
                if '"src":"minutes"' in line or '"src":"sim"' in line or '"src":"psim"' in line or '"src":"ledger"' in line or '"src":"heldbets"' in line or '"src":"novig_paper"' in line:
                    r = json.loads(line)
                    if (r['src'], r['k']) not in seen:
                        seen.add((r['src'], r['k']))
                        meta[str(r.get('game'))][r['src']] += 1
    bets = {}
    for d in days:
        b = M.json(f'bets/{d}.json', fresh=True)
        if b:
            bets[d] = b
    rows = []
    for g in games:
        gid, final = g['id'], g['state'] == 'post'
        has_box, diff = '', ''
        if final:
            p = M.get(f'results/{gid}.json', fresh=True)
            has_box = 'yes' if p else '**MISSING**'
            if p:
                import ledger
                stored = {int(k): v for k, v in json.load(open(p)).items()}
                new = parse_stats(curl(SUMMARY.format(gid)) or {})
                if new is None:
                    diff = 'ESPN not final?'
                else:
                    cells = [(a, s) for a in set(stored) | set(new) for s in set((stored.get(a) or {})) | set((new.get(a) or {})) if (stored.get(a) or {}).get(s) != (new.get(a) or {}).get(s)]
                    diff = f'{len(cells)} cells differ ({len({a for a, _ in cells})} players)' if cells else 'same'
        tipday = dt.datetime.fromtimestamp(g['tip'], ET).date().isoformat()
        bs = [b for b in bets.get(tipday, []) if str(b['game']) == gid]
        rows.append([f'{g["away"]} @ {g["home"]}', gid, fmt_et(g['tip']), g['state'], has_box, diff, meta[gid]['minutes'], meta[gid]['sim'], meta[gid]['psim'], meta[gid]['ledger'],
                     meta[gid]['heldbets'], meta[gid]['novig_paper'], len(bs), sum(b['result'] == 'open' for b in bs) if final else '-'])
    out += [table(['game', 'id', 'tip ET', 'ESPN', 'box stored', 'box vs ESPN now', 'minutes keys', 'sim keys', 'psim keys', 'ledger keys', 'heldbets keys', 'novig keys', 'bets', 'open after final'], rows), '']

    out += ['## B. What track.json shows, by tip day', '']
    rows = []
    for d in days:
        def games_in(name, container=track):
            return len(container.get(name, {}).get(d) or []) if isinstance(container.get(name), dict) else 0
        mn = (track.get('minutes_days') or {}).get(d)
        sig = ((track.get('signals') or {}).get('days') or {}).get(d) or {}
        rows.append([d, sum(r[track['cube_cols'].index('bets')] for r in track['cube'] if r[0] == d), f"{mn['n']} played + {mn['dnp']} dnp" if mn else '-',
                     games_in('sim_days'), games_in('gap_days'), games_in('psim_days'), games_in('held_days') if 'held_days' in track else 'no key', games_in('held_bets_days') if 'held_bets_days' in track else 'no key',
                     games_in('novig_days'), sum(v[0] for v in sig.values()) or '-', len((track.get('wire_days') or {}).get(d) or {})])
    out += [table(['tip day', 'cube bets', 'minutes_days', 'sim_days games', 'gap_days picks', 'psim_days games', 'held_days games', 'held_bets_days games', 'novig_days games', 'signals', 'wire venues'], rows), '']

    # C ── polls
    out += ['## C. Polls', '']
    rows = []
    allpolls = {}
    for d in days:
        pl = M.lines(f'snapshots/{d}/polls.jsonl', fresh=True)
        allpolls[d] = pl
        for s in SOURCES:
            rs = [r for r in pl if r['src'] == s]
            if not rs:
                continue
            ok = [r['t'] for r in rs if r['ok']]
            gaps = [(a, b) for a, b in zip(ok, ok[1:]) if b - a > GAP_MIN * 60]
            bad = [r for r in rs if not r['ok']]
            err = collections.Counter(r.get('err', '')[:60] for r in bad).most_common(1)
            rows.append([d, s, len(rs), len(bad), sum(1 for r in rs if r['ok'] and r.get('n') == 0), f'{max([b - a for a, b in zip(ok, ok[1:])] or [0]) // 60} min',
                         ', '.join(f'{fmt_et(a)}-{fmt_et(b)[7:]}' for a, b in gaps[:3]) or '-', (err[0][0] + f' x{err[0][1]}') if err else ''])
    out += [table(['day', 'source', 'polls', 'ok:false', 'ok, n=0', 'longest gap between good polls', f'gaps over {GAP_MIN} min', 'most common error'], rows), '']
    out += ['Last good poll of each source before each final game tipped (minutes before tip):', '']
    rows = []
    for g in fin:
        polls = [r for pl in allpolls.values() for r in pl]
        rows.append([f'{g["away"]} @ {g["home"]}'] + [next((f'{(g["tip"] - max(r["t"] for r in polls if r["src"] == s and r["ok"] and r["t"] < g["tip"])) // 60}' for _ in [0] if any(r["src"] == s and r["ok"] and r["t"] < g["tip"] for r in polls)), '-') for s in SOURCES])
    if rows:
        out += [table(['game'] + SOURCES, rows), '']

    # D ── totals
    out += ['## D. Totals', '']
    ic = track['cube_cols'].index('bets')
    cube_n, files_n = sum(r[ic] for r in track['cube']), sum(len([b for b in v if not b.get('pre')]) for v in bets.values())
    allbets = [b for v in bets.values() for b in v if not b.get('pre')]
    picks = {(b['pid'], b['stat'], 'o' if b['side'] in ('Over', 'YES') else 'u') for b in allbets}
    out += [f'- cube {cube_n}, bets files for these days {files_n}, track.n {track["n"]} (cube covers every regular-season day, files only the days audited).',
            f'- distinct picks {len(picks)} from {len(allbets)} bets.',
            f'- books in bets: {dict(collections.Counter(b["book"] for b in allbets))}',
            f'- teams in bets: {sorted({b["team"] for b in allbets})}']
    nm, ids = collections.defaultdict(set), collections.defaultdict(set)
    for b in allbets:
        nm[b['pid']].add(b['player'])
        ids[b['player']].add(b['pid'])
    out += [f'- one id with two names: {[k for k, v in nm.items() if len(v) > 1] or "none"}; one name with two ids: {[k for k, v in ids.items() if len(v) > 1] or "none"}', '']

    # E ── watchdog
    import watch_recorder_health as W
    names = [os.path.basename(p) for p in glob.glob(os.path.join(cache, 'snapshots', '20*'))]
    d2 = W.days_with_polls(names, lambda d: os.path.exists(os.path.join(cache, 'snapshots', d, 'polls.jsonl')))
    polls = [r for d in d2 for r in M.lines(f'snapshots/{d}/polls.jsonl')]
    rep = W.report(W.failing(polls, lineups=W.lineups_expected(status, now)), status, now)
    out += ['## E. What the watchdog would say now', '', rep or 'healthy', '']
    text = '\n'.join(out)
    if args.get('out'):
        open(args['out'], 'w').write(text)
    print(text)


if __name__ == '__main__':
    main(sys.argv[1:])
