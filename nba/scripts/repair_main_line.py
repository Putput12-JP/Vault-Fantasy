#!/usr/bin/env python3
"""
Repair the Props Simulation rows whose main line was a Polymarket rung (fixed 2026-10-26, prop_sim_record.main_line).

What was wrong: the recorder picked each prop's main line as the line most 'sportsbooks' agree on, and counted Polymarket's threshold ladder as sportsbook
rows. Polymarket posts one row per rung (9.5, 14.5, 19.5 points ...), so when only one real sportsbook posted a prop its line tied each rung at one vote and the
tie went to the LOWEST line: 4.5 points for a player the books had at 10.5, 1.5 rebounds for one at 6.5, priced at Polymarket's junk -3233 / -3233 (a 50% chance).
Where a real book's line sat on a rung (every 3-pointers and rebounds line, some points lines), the rung's price was averaged into the chance too, which pulls it
toward 50%. A prop only Polymarket priced had its rung as the whole price. The Biggest gap record, the held-props record and the minutes-model comparison
(psim_days) all read those rows.

What this does: for every poll that recorded psim rows, it rebuilds the board the way replay_polls.py does (stored prices only, nothing estimated) and runs
the FIXED prop_sim_record.log on it. Then, against each prop's value as the series stood at that poll:
  * the source or price differs and the LINE was right (only a rung's price had been averaged in): the recorder's own model numbers are kept and
    only the price and its source are replaced.
  * the line differs: the chances are recomputed at the right line from the mean the recorder had (prop_sim_record.log mu_of), so a model file that has moved
    since cannot change them.
  * the fixed code has no row (only Polymarket priced it, so it has no sportsbook or pick'em line): the row is cleared (null), as the recorder writes when a prop
    leaves the board. A cleared row is read as 'no price', never as 'the earlier row still stands'; the earlier rows were repaired at their own polls.
A stored row is replaced in place at its own time; a value the series should have taken at a poll that stored no row is inserted at that poll. Every other row is
left exactly as the recorder wrote it. The recorder only stores a row when a value changes, so the series reads as if the fixed code had been running.

  snapshots/<day>/psim.jsonl          the repaired series
  snapshots/<day>/psim_repair.json    what changed: the old and the new value for every replaced key and poll
  track.json                          untouched here. ledger.settle re-records every day that has a psim_repair.json it has not re-recorded yet (track.json
                                      'psim_repaired'), so the next poll rewrites psim_days, gap_days and held_days for those days.

  python3 nba/scripts/repair_main_line.py --dir=<nba-data checkout>              # dry run: prints what it would change
  python3 nba/scripts/repair_main_line.py --dir=<nba-data checkout> --write
  --days=2026-10-20,2026-10-21   only these ET day folders (default: every folder with psim rows)

Running it twice changes nothing the second time. It refuses today's ET folder: the recorder is appending to it.
"""
import datetime as dt, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import replay_polls as RP, prop_board as PB, prop_sim_record as PSR, snapshot as S


def differs(old, new):
    """True when the stored row has the wrong line, source or price (the three things the bug touched)."""
    return old[0] != new[0] or old[6] != new[6] or old[5] != new[5]


def repair_day(folder, say=print):
    """-> (stored rows, {(k, t): new value}, report) for one day folder. Nothing is written."""
    day = os.path.basename(folder)
    stored = [json.loads(l) for l in open(os.path.join(folder, 'psim.jsonl'))]
    meta = {}
    for line in open(os.path.join(folder, 'meta.jsonl')):
        if '"src":"psim"' in line:
            r = json.loads(line)
            meta[r['k']] = r
    ser = defaultdict(list)                                          # key -> [[t, value]] in time order; edited as the pass goes, so each poll sees the repairs before it
    for r in stored:
        ser[r['k']].append([r['t'], r['v']])
    cur = {k: None for k in ser}                                     # the value each key holds at the poll being processed
    idx = {k: 0 for k in ser}
    polls = [json.loads(l) for l in open(os.path.join(folder, 'polls.jsonl'))]
    clock = [p for p in polls if p['src'] == 'ledger']
    games = []
    for off in (-1, 0, 1, 2, 3):
        games += RP.schedule((dt.date.fromisoformat(day) + dt.timedelta(days=off)).isoformat())
    proj = json.load(open(os.path.join(HERE, '..', 'data', 'player_projections.json')))
    tips = {m['game']: m['tip'] for m in meta.values()}
    st = RP.State(folder)
    new, log = {}, []
    for i, p in enumerate(clock):
        now = p['t']
        nxt = clock[i + 1]['t'] if i + 1 < len(clock) else now + 300
        st.advance(nxt)
        for k, s in ser.items():                                     # bring each key's current value up to this poll: the stored rows at or before it, with the edits so far
            while idx[k] < len(s) and s[idx[k]][0] <= now:
                cur[k] = s[idx[k]][1]
                idx[k] += 1
        if not any(now < tip <= now + PSR.WINDOW_H * 3600 for tip in tips.values()):
            continue
        gs = [dict(g, pre=now < g['tip'] <= now + S.AHEAD_H * 3600) for g in games]
        board = PB.build([g for g in gs if g['pre']], st.last, st.meta, st.first, proj, now, when=st.when, wire=(st.hist, st.log, st.t0))
        board['src_ok'] = RP.src_ok(polls, now)
        rows, _ = PSR.log(board, now, mu_of=lambda k: (cur.get(k) or [None, None])[1])
        for k in list(cur):
            m = meta.get(k)
            if not m or not (now < m['tip'] <= now + PSR.WINDOW_H * 3600):
                continue
            old, want = cur[k], rows.get(k)
            if old is None:
                continue                                             # the old code had no row either, and the fixed code never has more rows than it did
            if want is None:
                fixed, why = None, 'none'                            # priced only by Polymarket's ladder: no sportsbook or pick'em line
            elif differs(old, want):
                fixed, why = (old[:5] + [want[5], want[6]], 'price') if old[0] == want[0] else (want, 'line')
            else:
                continue
            new[(k, now)] = fixed
            log.append({'k': k, 't': now, 'why': why, 'old': old, 'new': fixed})
            cur[k] = fixed
            s = ser[k]
            j = next((n for n, x in enumerate(s) if x[0] == now), None)      # replace the stored row at this poll, or insert the one it should have had
            if j is None:
                j = next((n for n, x in enumerate(s) if x[0] > now), len(s))
                s.insert(j, [now, fixed])
                idx[k] += 1
            else:
                s[j][1] = fixed
        say(f'  {day} {dt.datetime.fromtimestamp(now, dt.timezone.utc):%H:%M}Z  changed so far {len(new)}')
    by_why = defaultdict(int)
    for x in log:
        by_why[x['why']] += 1
    rep = {'rule': 'main line from sportsbooks only (Polymarket rungs excluded), prop_sim_record.main_line', 'changed': len(log), 'by': dict(by_why),
           'commit': RP.commit_id(), 'rows': log}
    return stored, new, rep


def write_day(folder, stored, new):
    """Rewrite psim.jsonl: stored rows with their repaired values, plus inserted rows, in time order (a stored row first at the same instant)."""
    keyed, seen = [], set()
    for n, r in enumerate(stored):
        if (r['k'], r['t']) in new:
            r = {**r, 'v': new[(r['k'], r['t'])]}
            seen.add((r['k'], r['t']))
        keyed.append((r['t'], 0, n, r))
    for n, ((k, t), v) in enumerate(sorted(new.items(), key=lambda x: (x[0][1], x[0][0]))):
        if (k, t) not in seen:
            keyed.append((t, 1, n, {'t': t, 'k': k, 'v': v}))
    keyed.sort(key=lambda x: x[:3])
    with open(os.path.join(folder, 'psim.jsonl'), 'w') as f:
        f.write('\n'.join(json.dumps(x[3], separators=(',', ':')) for x in keyed) + '\n')


def main(argv):
    args = {a.split('=')[0].lstrip('-'): (a.split('=', 1)[1] if '=' in a else True) for a in argv}
    root, write = os.path.abspath(args['dir']), bool(args.get('write'))
    snap = os.path.join(root, 'snapshots')
    today = dt.datetime.now(S.ET).strftime('%Y-%m-%d')
    days = str(args['days']).split(',') if args.get('days') else sorted(d for d in os.listdir(snap) if d[:2] == '20' and os.path.exists(os.path.join(snap, d, 'psim.jsonl')))
    for d in days:
        if d == today:
            print(f'{d}: skipped, the recorder is appending to it')
            continue
        folder = os.path.join(snap, d)
        stored, new, rep = repair_day(folder, say=lambda *a: None)
        print(f'{d}: {rep["changed"]} changes {rep["by"]}', flush=True)
        if write and new:
            write_day(folder, stored, new)
            json.dump(rep, open(os.path.join(folder, 'psim_repair.json'), 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main(sys.argv[1:])
