#!/usr/bin/env python3
"""
Repair the Props Simulation ('psim') and lean rows whose main line ignored the Action Network books (fixed 2026-11-24, prop_sim_record.main_line).

What was wrong: main_line read e['books'] (DraftKings, Pinnacle, Polymarket) and the pick'em apps. FanDuel, BetMGM, BetRivers, bet365, Caesars and Fanatics were
stored beside them in e['shop'] and never voted on the line. A prop only those books posted took a pick'em line (a point off the sportsbooks' number on
about one in ten), or no line at all (so no row was recorded). The pick'em fallback also priced the row from the pick'em app, or from nothing for a flat
PrizePicks line. See docs/main-line-shop-books.md.

What this does: for every poll that recorded rows, it rebuilds the board the way replay_polls.py does (stored prices only, nothing estimated, including
the Action Network props, which replay_polls.INPUTS did not read before this fix) and runs the recorder twice on that SAME board: the rule as it was
(main_line_before) and the rule as it is. Against each stored row at that poll:
  * the two rules agree: the row is left exactly as the recorder wrote it.
  * they differ, and the replay under the old rule reproduces the stored row (same line and source): the stored row takes the new rule's line, price and
    source. When the line is the same, only the price and source change and the recorder's own model numbers stay. When the line changes, the chances are
    recomputed at the new line from the mean the recorder had (mu_of), so a model file that has moved since cannot change them.
  * they differ but the replay does not reproduce the stored row: left alone and counted ('unreproducible').
Never inserted: a prop that had no stored row because no line existed. Its mean as the recorder had it was never stored, and a mean from today's model
files would be a number invented for a past date. Those props are recorded from the first poll after the fix.
A day with no stored Action Network props (2026-11-11, and every day before 2026-11-03) cannot change: the replay has no shop books.

  snapshots/<day>/psim.jsonl, leans.jsonl     the repaired series
  snapshots/<day>/psim_repair.json            what changed: the old and the new value for every replaced key and poll
  snapshots/<day>/lean_repair.json            same for the leans; ledger.settle re-records every day that has one it has not re-recorded yet

  python3 nba/scripts/repair_shop_lines.py --dir=<nba-data checkout>              # dry run: prints what it would change
  python3 nba/scripts/repair_shop_lines.py --dir=<nba-data checkout> --write
  --days=2026-11-20,2026-11-21   only these ET day folders (default: every folder with stored Action Network props)

Running it twice changes nothing the second time (the second run's old and new rules agree on the repaired rows). It refuses today's ET folder.
"""
import datetime as dt, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import replay_polls as RP, prop_board as PB, prop_sim_record as PSR, lean_record as LR, snapshot as S

NEW_MAIN_LINE = PSR.main_line
SRCS = {'psim': (PSR.log, PSR.WINDOW_H, 'psim.jsonl', 'psim_repair.json'), 'leans': (LR.log, LR.TRACK_H, 'leans.jsonl', 'lean_repair.json')}
# the columns each source's rule touches: psim [line, mu, p_exact, p_big, p_k50, p_price, src]; lean [line, mu, sd, p_model, side, p_blend, p_mkt, min, starter, price, book, src]
KEY_COLS = {'psim': (0, 5, 6), 'leans': (0, 6, 9, 10, 11)}
REPRODUCE = {'psim': (0, 6), 'leans': (0, 11)}


def main_line_before(e):
    """prop_sim_record.main_line as it was before 2026-11-24: e['books'] (not Polymarket) then the pick'em apps. e['shop'] is not read."""
    import pricing as PX
    bk = []
    for r in e.get('books', []):
        if r[0] in PSR.NOT_A_LINE:
            continue
        po, pu = PX.am_p(r[2]), PX.am_p(r[3])
        if r[1] is not None and po is not None and pu is not None:
            bk.append({'n': r[0], 'line': r[1], 'p': po / (po + pu)})
    if bk:
        line = PSR.modal_line(bk); at = [x for x in bk if x['line'] == line]
        return line, sum(x['p'] for x in at) / len(at), 'books'
    pk = []
    for r in e.get('pk', []):
        if r[1] is None:
            continue
        po, pu = (PX.am_p(r[2]) if r[2] is not None else None), (PX.am_p(r[3]) if r[3] is not None else None)
        pk.append({'n': r[0], 'line': r[1], 'p': po / (po + pu) if po is not None and pu is not None else None})
    if pk:
        line = PSR.modal_line(pk); at = [x for x in pk if x['line'] == line]
        pr = next((x['p'] for x in at if x['p'] is not None), None)
        return line, pr, 'pickem'
    return None


def same(a, b):
    """Two stored values agree on the columns the rule touches (prices to the 4 places they are stored at)."""
    return all((x == y) or (isinstance(x, float) and isinstance(y, float) and abs(x - y) < 6e-5) for x, y in zip(a, b))


def fix_row(src, old, new):
    """The repaired value: the new rule's line, price and source on the stored row's own model numbers when the line holds, else the new row at the new line."""
    if src == 'psim':
        return old[:5] + [new[5], new[6]] if old[0] == new[0] else new
    if old[0] == new[0]:
        r = list(old); r[5], r[6], r[9], r[10], r[11] = new[5], new[6], new[9], new[10], new[11]
        return r
    r = list(new); r[7], r[8] = old[7], old[8]                       # minutes and the starter flag are the recorder's own
    return r


def repair_day(folder, say=print):
    """-> ({src: stored rows}, {src: {(k, t): new value}}, {src: report}) for one day folder. Nothing is written.
    cur_o is the value the recorder held at each poll (the stored series, untouched); cur_e is that series with the edits so far. At every poll each
    key's target is the stored value, or the new rule's value when the two rules differ on the replayed board and the old rule reproduces the stored row;
    a target that differs from cur_e becomes an edit (a replaced row, or an inserted one where the recorder stored nothing at that poll)."""
    day = os.path.basename(folder)
    stored, ser, meta, cur_o, cur_e, idx, new, log, unrep = {}, {}, {}, {}, {}, {}, {}, {}, defaultdict(int)
    for src, (_, _, fname, _) in SRCS.items():
        p = os.path.join(folder, fname)
        stored[src] = [json.loads(l) for l in open(p)] if os.path.exists(p) else []
        meta[src] = {}
        for line in open(os.path.join(folder, 'meta.jsonl')):
            if f'"src":"{src}"' in line:
                r = json.loads(line); meta[src][r['k']] = r
        ser[src] = defaultdict(list)
        for r in stored[src]:
            ser[src][r['k']].append([r['t'], r['v']])
        cur_o[src] = {k: None for k in ser[src]}; cur_e[src] = dict(cur_o[src]); idx[src] = {k: 0 for k in ser[src]}; new[src] = {}; log[src] = []
    polls = [json.loads(l) for l in open(os.path.join(folder, 'polls.jsonl'))]
    clock = [p for p in polls if p['src'] == 'ledger']
    games = []
    for off in (-1, 0, 1, 2, 3):
        games += RP.schedule((dt.date.fromisoformat(day) + dt.timedelta(days=off)).isoformat())
    proj = json.load(open(os.path.join(HERE, '..', 'data', 'player_projections.json')))
    tips = [m['tip'] for src in SRCS for m in meta[src].values()]
    wide = max(w for _, w, _, _ in SRCS.values())
    st = RP.State(folder)
    for i, p in enumerate(clock):
        now = p['t']
        nxt = clock[i + 1]['t'] if i + 1 < len(clock) else now + 300
        st.advance(nxt)
        for src in SRCS:
            for k, s in ser[src].items():
                while idx[src][k] < len(s) and s[idx[src][k]][0] <= now:
                    cur_o[src][k] = cur_e[src][k] = s[idx[src][k]][1]            # a row the recorder stored replaces any edit before it
                    idx[src][k] += 1
        if not any(now < tip <= now + wide * 3600 for tip in tips):
            continue
        gs = [dict(g, pre=now < g['tip'] <= now + S.AHEAD_H * 3600) for g in games]
        board = PB.build([g for g in gs if g['pre']], st.last, st.meta, st.first, proj, now, when=st.when, wire=(st.hist, st.log, st.t0))
        board['src_ok'] = RP.src_ok(polls, now)
        for src, (logf, window, _, _) in SRCS.items():
            mu_of = (lambda c: lambda k: (c.get(k) or [None, None])[1])(cur_o[src])
            PSR.main_line = main_line_before
            try:
                rows_old, _ = logf(board, now, mu_of=mu_of)
            finally:
                PSR.main_line = NEW_MAIN_LINE
            rows_new, _ = logf(board, now, mu_of=mu_of)
            for k in list(cur_o[src]):
                m = meta[src].get(k)
                if not m or not (now < m['tip'] <= now + window * 3600):
                    continue
                old, o, n = cur_o[src][k], rows_old.get(k), rows_new.get(k)
                if old is None:
                    continue                                                      # no stored row to repair
                target = old
                if n is not None and not (o is not None and same([n[c] for c in KEY_COLS[src]], [o[c] for c in KEY_COLS[src]])):
                    if o is not None and same([old[c] for c in REPRODUCE[src]], [o[c] for c in REPRODUCE[src]]):
                        target = fix_row(src, old, n)
                    else:
                        unrep[src] += 1                                           # the replay does not reproduce the stored row: not edited
                if target != cur_e[src][k]:
                    new[src][(k, now)] = target
                    log[src].append({'k': k, 't': now, 'why': 'line' if cur_e[src][k][0] != target[0] else 'price', 'old': cur_e[src][k], 'new': target})
                    cur_e[src][k] = target
        say(f'  {day} {dt.datetime.fromtimestamp(now, dt.timezone.utc):%H:%M}Z  changed so far {sum(len(v) for v in new.values())}')
    rep = {}
    for src in SRCS:
        by = defaultdict(int)
        for x in log[src]:
            by[x['why']] += 1
        rep[src] = {'rule': 'main line votes: e[books] and e[shop] (FanDuel, BetMGM, BetRivers, bet365, Caesars, Fanatics), prop_sim_record.main_line', 'changed': len(log[src]),
                    'by': dict(by), 'unreproducible': unrep[src], 'commit': RP.commit_id(), 'rows': log[src]}
    return stored, new, rep


def write_day(folder, src, stored, new):
    """Rewrite <src>.jsonl: stored rows with their repaired values, plus inserted rows, in time order (a stored row first at the same instant)."""
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
    with open(os.path.join(folder, SRCS[src][2]), 'w') as f:
        f.write('\n'.join(json.dumps(x[3], separators=(',', ':')) for x in keyed) + '\n')


def main(argv):
    args = {a.split('=')[0].lstrip('-'): (a.split('=', 1)[1] if '=' in a else True) for a in argv}
    root, write = os.path.abspath(args['dir']), bool(args.get('write'))
    snap = os.path.join(root, 'snapshots')
    today = dt.datetime.now(S.ET).strftime('%Y-%m-%d')
    days = str(args['days']).split(',') if args.get('days') else sorted(d for d in os.listdir(snap) if d[:2] == '20' and os.path.exists(os.path.join(snap, d, 'actionprops.jsonl')))
    for d in days:
        if d == today:
            print(f'{d}: skipped, the recorder is appending to it')
            continue
        folder = os.path.join(snap, d)
        if not (os.path.exists(os.path.join(folder, 'psim.jsonl')) or os.path.exists(os.path.join(folder, 'leans.jsonl'))):
            continue
        stored, new, rep = repair_day(folder, say=lambda *a: None)
        print(f'{d}: ' + '; '.join(f'{src} {rep[src]["changed"]} changes {rep[src]["by"]}, {rep[src]["unreproducible"]} not reproduced' for src in SRCS), flush=True)
        if write:
            for src, (_, _, _, rname) in SRCS.items():
                if new[src]:
                    write_day(folder, src, stored[src], new[src])
                    json.dump(rep[src], open(os.path.join(folder, rname), 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main(sys.argv[1:])
