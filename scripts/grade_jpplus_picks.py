#!/usr/bin/env python3
"""Grade an outside model's college spread picks against real results and the real closing line.

Why this exists: JP+ (jpplusratings.com) publishes college football spread picks with its own
record and closing-line-value (CLV) figures. Rather than take those on trust, this grades every
pick in data/jpplus_picks.json from ESPN data: the final score, and ESPN's closing spread. It
also reports JP+'s own closing line next to ESPN's, so a mismatch would show.

Input : data/jpplus_picks.json  (picks are entered by hand: week, team, entry handicap)
Output: data/jpplus_graded.json (summary + one row per pick)

Data  : sportsdataverse-data releases (ESPN play-by-play and schedules). Needs pandas + pyarrow.
Run   : python3 scripts/grade_jpplus_picks.py
Handicap convention everywhere: the TEAM's spread, + = underdog (+15.5 means getting 15.5 points).
CLV = entry - close: positive means the pick got a better number than the market ended at.
"""
import json, math, os, sys, tempfile, urllib.request
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICKS = os.path.join(ROOT, 'data', 'jpplus_picks.json')
OUT = os.path.join(ROOT, 'data', 'jpplus_graded.json')
REL = 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download'
ALIAS = {'FIU': 'Florida International', 'Hawaii': "Hawai'i", 'Miami (OH)': 'Miami (OH)'}
BREAKEVEN = 110 / 210          # a -110 bet needs 52.38% to break even


def fetch(url, dest):
    if not os.path.exists(dest):
        req = urllib.request.Request(url, headers={'User-Agent': 'vault-fantasy'})
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, 'wb') as f:
            f.write(r.read())
    return dest


def close_stats(rows):
    """The same final picks, graded against ESPN's closing spread instead of JP+'s entry (opening) number, and split into underdogs (+ handicap)
    and favourites. entry/espn_close are the TEAM's handicap (+ = underdog); a team covers when margin + handicap > 0."""
    def tally(rs, key):
        w = l = p = 0
        for r in rs:
            v = r['margin'] + r[key]
            if v > 0: w += 1
            elif v < 0: l += 1
            else: p += 1
        return w, l, p
    fin = [r for r in rows if r.get('status') == 'final' and r.get('margin') is not None and r.get('espn_close') is not None]
    if not fin: return None
    dogs = [r for r in fin if r['entry'] > 0]
    (w, l, p), (dw, dl, dp), (ow, ol, op) = tally(fin, 'espn_close'), tally(dogs, 'espn_close'), tally(dogs, 'entry')
    return dict(n=len(fin), w=w, l=l, p=p, dog_n=len(dogs), dog_w=dw, dog_l=dl, dog_p=dp, dog_open_w=ow, dog_open_l=ol, dog_open_p=op)


def main():
    doc = json.load(open(PICKS))
    season = doc['season']
    tmp = os.path.join(tempfile.gettempdir(), 'jpplus_grade')
    os.makedirs(tmp, exist_ok=True)
    pbp = pd.read_parquet(fetch(f'{REL}/espn_cfb_pbp/play_by_play_{season}.parquet', os.path.join(tmp, f'pbp_{season}.parquet')),
                          columns=['game_id', 'week', 'seasonType', 'homeTeamName', 'awayTeamName', 'homeFinalScore',
                                   'awayFinalScore', 'homeTeamSpread', 'status_type_completed'])
    g = pbp[pbp.seasonType == 2].drop_duplicates('game_id')
    sch = pd.read_parquet(fetch(f'{REL}/espn_cfb_schedules/cfb_schedule_{season}.parquet', os.path.join(tmp, f'sched_{season}.parquet')),
                          columns=['game_id', 'game_date', 'status'])
    g = g.merge(sch, on='game_id', how='left')

    out = []
    for p in doc['picks']:
        t = ALIAS.get(p['team'], p['team'])
        # JP+ "week 1" includes ESPN's week 0 openers
        m = g[(g.week == p['week']) & ((g.homeTeamName == t) | (g.awayTeamName == t))]
        if m.empty and p['week'] == 1:
            m = g[(g.week == 0) & ((g.homeTeamName == t) | (g.awayTeamName == t))]
        row = dict(week=p['week'], team=p['team'], entry=p['entry'], jp_close=p.get('jp_close'), jp_result=p.get('jp_result'))
        if m.empty:
            row.update(status='not found yet'); out.append(row); continue
        if len(m) > 1:
            # a team can play twice in one ESPN week (Aug 29 and Sep 7 are both 'week 1'): take the game whose
            # closing handicap sits nearest the pick's entry number
            def gap(r):
                h = r.homeTeamName == t
                c = None if pd.isna(r.homeTeamSpread) else (-r.homeTeamSpread if h else r.homeTeamSpread)
                return 99 if c is None else abs(c - p['entry'])
            m = m.assign(_gap=[gap(r) for r in m.itertuples()]).sort_values('_gap').head(1)
            row['matched_by_line'] = True
        x = m.iloc[0]
        home = x.homeTeamName == t
        final = bool(x.status_type_completed)
        margin = (x.homeFinalScore - x.awayFinalScore) * (1 if home else -1)
        close = None if pd.isna(x.homeTeamSpread) else (-x.homeTeamSpread if home else x.homeTeamSpread)
        res = None
        if final:
            res = 'W' if margin + p['entry'] > 0 else 'L' if margin + p['entry'] < 0 else 'P'
        row.update(opp=x.awayTeamName if home else x.homeTeamName, home=bool(home), kick=x.game_date,
                   status='final' if final else 'not final', margin=int(margin) if final else None,
                   espn_close=close, result=res, clv=None if close is None else round(p['entry'] - close, 1),
                   agrees_with_jp=None if not (res and p.get('jp_result') in ('W', 'L')) else (res == p['jp_result']))
        out.append(row)

    done = [r for r in out if r.get('result') in ('W', 'L', 'P')]
    w = sum(r['result'] == 'W' for r in done); l = sum(r['result'] == 'L' for r in done); ps = len(done) - w - l
    n = w + l
    clvs = [r['clv'] for r in out if r.get('clv') is not None]
    chk = [r for r in out if r.get('agrees_with_jp') is not None]
    close_gap = [abs(r['espn_close'] - r['jp_close']) for r in out if r.get('espn_close') is not None and r.get('jp_close') is not None]
    summary = dict(n=n, won=w, lost=l, pushed=ps, expected=round(n * BREAKEVEN, 2),
                   z=round((w - n * BREAKEVEN) / math.sqrt(n * BREAKEVEN * (1 - BREAKEVEN)), 2) if n else None,
                   clv_n=len(clvs), clv_mean=round(sum(clvs) / len(clvs), 2) if clvs else None,
                   clv_pos=round(sum(c > 0 for c in clvs) / len(clvs), 3) if clvs else None,
                   clv_neg=round(sum(c < 0 for c in clvs) / len(clvs), 3) if clvs else None,
                   checked_vs_jp=len(chk), disagreements_vs_jp=sum(not r['agrees_with_jp'] for r in chk),
                   mean_gap_to_jp_close=round(sum(close_gap) / len(close_gap), 2) if close_gap else None,
                   picks=len(out), not_final=sum(r.get('status') != 'final' for r in out),
                   close=close_stats(out))
    json.dump(dict(generated=pd.Timestamp.now('UTC').isoformat(), season=season, source=doc.get('source'), summary=summary, picks=out),
              open(OUT, 'w'), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    sys.exit(main())
