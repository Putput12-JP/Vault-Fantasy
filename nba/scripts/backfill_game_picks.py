#!/usr/bin/env python3
"""
Backfill the game picks for regular-season days played before the live recorder (game_pick_record.py) existed.

Nothing here is a replay with today's model. For every game the Game Simulation already logged its `vault` environment before tip
(sim_record.py): the game model's margin and total as the page showed them, with that day's injury report in. This script reads those rows
from the tape, takes the line as it stood at that moment from the same tape (ESPN's core odds feed: DraftKings and the other books, same book order as the
recorder), and grades both against the final score with the very function the live record uses (game_pick_record.grade_row).

Where it differs from the live record, and why it is kept apart (src 'bf', its own file, never added to the forward record's headline):
  * margin is the simulation's MEAN margin for the vault environment, not vault_mean's exact margin. On 24 live games the two differ by
    0.11 points on average and 0.37 at most (the simulation breaks ties and cuts at zero). A pick whose edge is under about 0.4 points could
    differ from what the live recorder would have written.
  * p_home is Normal(margin / sd_margin) with the same sd as the live record (data/model_state.json game.sd_margin).
  * a game is recorded from its first row that has a posted spread, as the live recorder does. No line or price is ever filled in.

  python3 nba/scripts/backfill_game_picks.py --tape DIR [--out nba/data/game_picks_backfill.json]
DIR is a checkout of the nba-data branch with snapshots/<day>/{sim,espn,meta}.jsonl and results/<gid>.meta.json for the days to rebuild, e.g.
  git archive origin/nba-data snapshots/2026-10-20 results | tar -x -C DIR
"""
import argparse, bisect, collections, datetime as dt, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import game_pick_record as G
from nba_common import book_name

ET_TZ = None


def tip_day(ts):
    import ledger
    return ledger.tip_day(ts)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_day(d):
    """(sim vault series {gid: [(t, v)]}, sim meta {gid: meta}, espn game series {(gid, book): [(t, v)]}, espn meta {key: meta}) for one day folder."""
    sim, smeta, esp, emeta = collections.defaultdict(list), {}, collections.defaultdict(list), {}
    for line in open(os.path.join(d, 'meta.jsonl')):
        if '"src":"sim"' in line and '|vault"' in line:
            r = json.loads(line)
            if r.get('kind') == 'game':
                smeta[r['game']] = r
        elif '"src":"espn"' in line and '|game"' in line:
            r = json.loads(line)
            emeta[r['k']] = r
    for line in open(os.path.join(d, 'sim.jsonl')):
        if '|vault"' not in line:
            continue
        r = json.loads(line)
        gid, env = r['k'].split('|')[:2]
        if len(r['k'].split('|')) == 2 and env == 'vault' and r['v'] is not None:
            sim[gid].append((r['t'], r['v']))
    for line in open(os.path.join(d, 'espn.jsonl')):
        if '|game"' not in line:
            continue
        r = json.loads(line)
        m = emeta.get(r['k'])
        if m:
            esp[(m['game'], book_name(m['book']))].append((r['t'], r['v']))
    return sim, smeta, esp, emeta


def books_at(esp, gid, t):
    """The board's mk.books shape for this game at time t: [book, home spread, home px, away px, home ml, away ml, total, over px, under px]."""
    out = []
    for (g, book), series in esp.items():
        if g != gid:
            continue
        i = bisect.bisect_right([x[0] for x in series], t) - 1
        if i < 0 or series[i][1] is None:
            continue
        v = series[i][1]
        out.append([book, num(v[0]), v[1], v[2], v[3], v[4], num(v[5]), v[6], v[7]])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tape', required=True, help='nba-data checkout (snapshots/, results/)')
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'data', 'game_picks_backfill.json'))
    ap.add_argument('--before', default=None, help='only days before this ET date (the live recorder owns the rest)')
    a = ap.parse_args()
    import ledger as L
    ms = json.load(open(os.path.join(HERE, '..', 'data', 'model_state.json')))['game']
    sd = ms['sd_margin']
    days, skipped = {}, []
    for d in sorted(glob.glob(os.path.join(a.tape, 'snapshots', '20*'))):
        day = os.path.basename(d)
        if a.before and day >= a.before:
            continue
        if not (os.path.exists(os.path.join(d, 'sim.jsonl')) and os.path.exists(os.path.join(d, 'espn.jsonl'))):
            continue
        sim, smeta, esp, _ = load_day(d)
        for gid, series in sim.items():
            m = smeta.get(gid)
            if not m or L.tip_day(m['tip']) != day:
                continue
            pre = [(t, v) for t, v in sorted((t, v) for t, v in series if t < m['tip']) if G.pick_line({'mk': {'books': books_at(esp, gid, t)}})]   # as live: a game is recorded once a spread is posted
            sc = (json.load(open(os.path.join(a.tape, 'results', f'{gid}.meta.json'))).get('score')
                  if os.path.exists(os.path.join(a.tape, 'results', f'{gid}.meta.json')) else None) or {}
            if not pre or m['home'] not in sc or m['away'] not in sc:
                skipped.append((day, m['matchup'], 'no pre-tip row' if not pre else 'no final score'))
                continue
            rows = []
            for t, v in (pre[0], pre[-1]):
                ln = G.pick_line({'mk': {'books': books_at(esp, gid, t)}}) or {}
                margin = float(v[0])
                rows.append([round(margin, 2), round(float(v[1]), 1), round(G.phi(margin / sd), 4), ln.get('book'), ln.get('spread'),
                             ln.get('home_px'), ln.get('away_px'), ln.get('home_ml'), ln.get('away_ml'), ln.get('ml_book')])
            am = sc[m['home']] - sc[m['away']]
            first, close = rows[0][:9], rows[1][:9]
            dd = days.setdefault(day, {'games': {}, 'rows': []})
            dd['games'][gid] = [m['matchup'], m['tip'], m['away'], m['home'], sc[m['away']], sc[m['home']]]
            for clock, r in (('f', rows[0]), ('c', rows[1])):
                out = G.grade_row(r[:9], am, clock, first, lambda px, won: L.profit('book', px, won))
                out[G.COLS.index('ml_book') - 1] = r[9]
                dd['rows'].append([gid] + out + ['bf'])
    for day, dd in days.items():
        dd['rows'].sort(key=lambda r: (r[0], r[1]))
        dd['summary'] = G.summarize(dd['rows'])
    out = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'cols': G.COLS, 'sd_margin': sd, 'days': days,
           'note': 'Rebuilt from the Game Simulation vault rows and the ESPN line feed on the tape (backfill_game_picks.py). Kept apart from the forward record.'}
    json.dump(out, open(a.out, 'w'), separators=(',', ':'))
    n = sum(len(d['games']) for d in days.values())
    print(f'{n} games over {len(days)} days -> {os.path.relpath(a.out)}')
    for day, dd in days.items():
        s = dd['summary']['f']
        print(f"  {day}: {len(dd['games'])} games  ATS {s['ats']}  winner {s['ml']}")
    for s in skipped:
        print('  skipped', *s)


if __name__ == '__main__':
    main()
