#!/usr/bin/env python3
"""
Rebuild every earlier game pick at the lineup lock (docs/game-pick-lock.md), from rows already on the nba-data tape.

Until 2026-11-23 a game's pick was written once, 4 hours before tip. Official injury statuses and the starting fives land after that (Nov 22: Gilgeous-Alexander
went Out 90 minutes before tip and Antetokounmpo 59 minutes before, after the OKC @ MIA pick was written), so the lock moved to the moment both fives are
confirmed, 20 minutes before tip at the latest. A change to the lock changes every row of the record, so the days before it are rebuilt here rather than left
under a rule that no longer applies. Nothing is replayed with today's model: the margin is the Game Simulation's `vault` row the recorder already wrote at that poll
(the game model as the page showed it, with that moment's injury report and NBA.com inactives in), and the line is ESPN's feed at the same poll, taken by the
same function the live recorder uses (game_pick_record.pick_line), the same book order. Graded by game_pick_record.grade_row.

For each game, on the recorder's own polls (the `ledger` records in polls.jsonl):
  lock  the first poll before tip at which a spread is posted, a vault row exists, and game_pick_record.lock_open says so (both fives Confirmed in the lineups
        rows as they stood at that poll, or 20 minutes to tip).
  close the last such poll before tip.
--rule 4h keeps the old lock (the first poll with a spread and a vault row inside 4 hours). It exists to check this rebuild against the live 4-hour record,
which the recorder wrote with the exact model margin: see docs/game-pick-lock.md.

Limits (the same as backfill_game_picks.py): the vault row's margin is the simulation's mean margin to one decimal, not vault_mean's exact margin. Measured against
the live record (--rule 4h on the days the recorder wrote): see the doc. The line is ESPN's feed (DraftKings first), not the board's merge with Action Network and
Pinnacle; DraftKings was present for every game.

  python3 nba/scripts/rebuild_game_picks_lineup_lock.py --tape DIR [--rule lineup|4h] [--out FILE] [--before YYYY-MM-DD]
DIR holds snapshots/<day>/{sim,espn,meta,lineups,polls}.jsonl and results/<gid>.meta.json (a checkout of the nba-data branch, or the slice of it):
  git archive origin/nba-data snapshots/<day> results | tar -x -C DIR
"""
import argparse, bisect, collections, datetime as dt, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import game_pick_record as G
import backfill_game_picks as B

OLD_WINDOW_H = 4                                # the rule this replaced: from 4 hours before tip


def load_lineups(d):
    """Lineup events sorted by time: [(t, key, value)], value None when the row was removed."""
    p = os.path.join(d, 'lineups.jsonl')
    if not os.path.exists(p):
        return []
    ev = [json.loads(x) for x in open(p)]
    ev.sort(key=lambda r: r['t'])
    return [(r['t'], r['k'], r['v']) for r in ev]


def load_polls(d):
    """Times of the recorder's own polls (the ledger records), the moments game_pick_record.log ran."""
    p = os.path.join(d, 'polls.jsonl')
    return sorted(json.loads(x)['t'] for x in open(p) if '"src":"ledger"' in x) if os.path.exists(p) else []


def game_locks(day_dir, day, rule):
    """{gid: (meta, lock t, lock row, close t, close row)} for the games of one tip day. row = (margin, total, spread line dict)."""
    import ledger as L
    sim, smeta, esp, _ = B.load_day(day_dir)
    polls, events = load_polls(day_dir), load_lineups(day_dir)
    state, i, conf_at = {}, 0, {}
    for t in polls:                                         # the lineups state as it stood at every poll
        while i < len(events) and events[i][0] <= t:
            state[events[i][1]] = events[i][2]
            i += 1
        conf_at[t] = G.fives_confirmed(state)
    out = {}
    for gid, series in sim.items():
        m = smeta.get(gid)
        if not m or L.tip_day(m['tip']) != day:
            continue
        series = sorted((t, v) for t, v in series if t < m['tip'])
        st = [t for t, _ in series]
        g = {'id': gid, 'day': day, 'tip': m['tip'], 'away': m['away'], 'home': m['home']}
        cands = []
        for t in polls:
            if t >= m['tip']:
                break
            k = bisect.bisect_right(st, t) - 1
            if k < 0:                                       # no vault row yet: the recorder wrote nothing
                continue
            ln = G.pick_line({'mk': {'books': B.books_at(esp, gid, t)}})
            if not ln:                                      # no spread posted: wait, as the recorder does
                continue
            cands.append((t, series[k][1], ln))
        if rule == '4h':
            pool = [c for c in cands if c[0] >= m['tip'] - OLD_WINDOW_H * 3600]
        else:
            pool = [c for c in cands if G.lock_open(g, c[0], conf_at[c[0]])]
        if not pool:
            continue
        out[gid] = (m, pool[0], cands[-1] if cands else pool[-1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tape', required=True, help='nba-data checkout (snapshots/, results/)')
    ap.add_argument('--rule', default='lineup', choices=['lineup', '4h'])
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'data', 'game_picks_backfill.json'))
    ap.add_argument('--before', default=None, help='only days before this ET date (the live recorder owns the rest)')
    a = ap.parse_args()
    import ledger as L
    ms = json.load(open(os.path.join(HERE, '..', 'data', 'model_state.json')))['game']
    sd = ms['sd_margin']
    days, skipped, lock_min = {}, [], []
    for d in sorted(glob.glob(os.path.join(a.tape, 'snapshots', '20*'))):
        day = os.path.basename(d)
        if a.before and day >= a.before:
            continue
        if not all(os.path.exists(os.path.join(d, f)) for f in ('sim.jsonl', 'espn.jsonl', 'meta.jsonl', 'polls.jsonl')):
            continue
        for gid, (m, lk, cl) in game_locks(d, day, a.rule).items():
            rp = os.path.join(a.tape, 'results', f'{gid}.meta.json')
            sc = (json.load(open(rp)).get('score') if os.path.exists(rp) else None) or {}
            if m['home'] not in sc or m['away'] not in sc:
                skipped.append((day, m['matchup'], 'no final score'))
                continue
            rows = []
            for t, v, ln in (lk, cl):
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
            lock_min.append(round((m['tip'] - lk[0]) / 60, 1))
    for day, dd in days.items():
        dd['rows'].sort(key=lambda r: (r[0], r[1]))
        dd['summary'] = G.summarize(dd['rows'])
    note = ('Rebuilt at the lineup lock (rebuild_game_picks_lineup_lock.py, docs/game-pick-lock.md) from the Game Simulation vault rows, the lineups rows and the ESPN line feed on the tape. '
            'Kept apart from the forward record.') if a.rule == 'lineup' else \
           'Rebuilt at the OLD 4-hour lock, only to check the rebuild against the live 4-hour record. Not used by the page.'
    out = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'cols': G.COLS, 'sd_margin': sd, 'rule': a.rule,
           'lock_v2_from': G.LOCK_V2_FROM, 'days': days, 'note': note}
    json.dump(out, open(a.out, 'w'), separators=(',', ':'))
    n = sum(len(d['games']) for d in days.values())
    lock_min.sort()
    print(f"{n} games over {len(days)} days (rule {a.rule}) -> {os.path.relpath(a.out)}")
    if lock_min:
        q = lambda f: lock_min[int(f * (len(lock_min) - 1))]
        print(f"minutes before tip at the lock: min {lock_min[0]}  p25 {q(.25)}  median {q(.5)}  p75 {q(.75)}  max {lock_min[-1]}")
    for s in skipped:
        print('  skipped', *s)


if __name__ == '__main__':
    main()
