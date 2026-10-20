#!/usr/bin/env python3
"""
Props simulation record: the live, like-for-like score of the minutes model against playing it out 10,000 and 50 games at a time.

Backtest (build_sim_challenger.py, docs/sim-challenger.md) scored these on last season's prices. This is the same comparison on this
season's props, recorded before tip and settled from the box score, for the Track Record page. Nothing here is a bet and nothing here changes
a price.

  log(board, now)   -> (rows, meta) for Day.record('psim', ...), called by snapshot.py after each poll, for games within WINDOW_H of tip.
                       One row per priced prop on pts / reb / ast / 3pm:  key  gid|pid|stat
                       [line, mu, p_exact, p_10k, p_50, p_price, price_src]
                         line     the main line: the sportsbook line most books agree on, else a pick'em app's (Underdog / Sleeper / PrizePicks)
                         mu       the minutes model's mean for the player in that game (pricing.Pricer.mu_for, with the injury report applied)
                         p_exact  P(over line), the Player Props page's model probability (closed form, calibrated)
                         p_10k    the same distribution played 10,000 times, share over the line, through the same calibration
                         p_50     played 50 times (a fixed draw per prop), smoothed (k+.5)/(N+1), through the same calibration
                         p_price  the over chance in the price at that line (vig removed), or null for a flat line with no price
  record(...)       -> per tip day, per game, per stat: log loss and Brier sums for each variant, against the box score.

Biggest gap record: the Props Simulation page headlines one prop per game, the priced prop where the model's chance differs most from the price.
gap_pick() makes that choice from the recorded rows the way the page does, and record_all() settles it, so the page's headline gets a record.
It is where-to-look, not a bet: it is scored on hit rate against the chance in the price (vig removed), never on profit, because no stake or
payout is recorded. A prop with no price (a flat pick'em line) is never the biggest gap; the page calls that one Strongest lean and it is not tracked.

Scoring: a prop is void when the player did not play or the stat lands exactly on the line. Sums are kept per game so the page can cluster the
standard error by game, as the backtest did. A row is scored from the last pre-tip record, so a prop that moved is judged on its final price.
"""
import math, os, sys, zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

WINDOW_H = 3                          # a prop is recorded from this many hours before tip: lineups and injuries have mostly settled
STATS = ['pts', 'reb', 'ast', '3pm']
STAT_BOX = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', '3pm': 'threePointFieldGoalsMade'}
COUNT = {'reb', 'ast', '3pm'}
N_BIG, N_SMALL = 10000, 50
SHOWN = 5                             # the page lists each team's five highest-minute players, and picks the biggest gap among them
NCOL = 12                             # per game per stat: n, ll x3, brier x3, then the priced subset: n, market ll, ll x3


def main_line(e):
    """(line, p_over from the price or None, source) for one board prop: sportsbooks first, then the pick'em apps."""
    import pricing as PX
    def modal(rows):
        cnt = {}
        for r in rows:
            cnt[r['line']] = cnt.get(r['line'], 0) + 1
        return sorted(cnt, key=lambda k: (-cnt[k], k))[0]
    bk = []
    for r in e.get('books', []):
        po, pu = PX.am_p(r[2]), PX.am_p(r[3])
        if r[1] is not None and po is not None and pu is not None:
            bk.append({'n': r[0], 'line': r[1], 'p': po / (po + pu)})
    if bk:
        line = modal(bk); at = [x for x in bk if x['line'] == line]
        return line, sum(x['p'] for x in at) / len(at), 'books'
    pk = []
    for r in e.get('pk', []):
        if r[1] is None:
            continue
        po, pu = (PX.am_p(r[2]) if r[2] is not None else None), (PX.am_p(r[3]) if r[3] is not None else None)
        pk.append({'n': r[0], 'line': r[1], 'p': po / (po + pu) if po is not None and pu is not None else None})
    if pk:
        line = modal(pk); at = [x for x in pk if x['line'] == line]
        pr = next((x['p'] for x in at if x['p'] is not None), None)
        return line, pr, 'pickem'
    return None


def draws_over(rng, stat, mu, var, line, n):
    """Share of n simulated games over the line: gamma-Poisson for counts (Poisson when var <= mu), Normal for points (rounded, as games are)."""
    if stat in COUNT:
        if var <= mu * 1.0001:
            lam = np.full(n, mu)
        else:
            lam = rng.gamma(mu * mu / (var - mu), (var - mu) / mu, size=n)
        x = rng.poisson(lam)
    else:
        x = np.round(rng.normal(mu, math.sqrt(var), size=n))
    return float((x > line).mean())


def log(board, now):
    """Rows and meta for every priced prop whose game tips within WINDOW_H."""
    rows, meta = {}, {}
    if not board or not board.get('games') or not board.get('props'):
        return rows, meta
    import pricing as PX
    pr = PX.Pricer(example=bool(board.get('example')))
    games = {str(g['id']): g for g in board['games']}
    outs, status, cache = PX.outs_from_board(board), PX.status_from_board(board), {}
    for e in board['props']:
        s = e['s']
        g = games.get(str(e['g']))
        if s not in STATS or not g or not (now < g['tip'] <= now + WINDOW_H * 3600):
            continue
        try:
            ml = main_line(e)
            if not ml:
                continue
            line, p_price, src = ml
            P = (board.get('players') or {}).get(str(e['p'])) or (board.get('players') or {}).get(e['p'])
            team = P[1] if P else None
            m = pr.mu_for(int(e['p']), s, g, cache, outs, team, status)
            if not m or not (m['min'] > 0) or pr.roster_hold(m['team'], g, status, cache, m.get('src')):
                continue
            mu, ex = m['mu'], m['extra']
            v0, v1, v2, v3 = pr.PR['variance'][s]
            var = max(.25, v0 + v1 * mu + v2 * mu * mu + (v3 * ex if v3 else 0))
            seed = zlib.crc32(f"{e['g']}|{e['p']}|{s}".encode())            # fixed per prop, so an unchanged input records an unchanged row
            big = draws_over(np.random.default_rng(seed), s, mu, var, line, N_BIG)
            k50 = round(draws_over(np.random.default_rng(seed + 1), s, mu, var, line, N_SMALL) * N_SMALL)
            k = f"{e['g']}|{e['p']}|{s}"
            rows[k] = [line, round(mu, 3), round(pr.cal(s, pr.p_over_raw(s, mu, line, ex)), 4), round(pr.cal(s, min(max(big, 1e-4), 1 - 1e-4)), 4),
                       round(pr.cal(s, (k50 + .5) / (N_SMALL + 1)), 4), None if p_price is None else round(p_price, 4), src]
            meta[k] = {'game': str(e['g']), 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'pid': int(e['p']), 'player': P[0] if P else str(e['p']),
                       'team': m['team'], 'stat': s, 'kind': 'psim', 'min': round(m['min'], 1)}
        except Exception as ex_:                                              # one prop's failure never stops the recorder
            print(f"  psim {e.get('g')}|{e.get('p')}|{s}: {type(ex_).__name__}: {str(ex_)[:100]}", flush=True)
    return rows, meta


def _ll(p, over):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if over else 1 - p)


def score(rows, bx):
    """Per stat NCOL sums for one game. rows: {pid_stat: (row, meta)}. bx: {pid: {stat: value}} from ledger.box. Void props are skipped."""
    per = {s: [0.0] * NCOL for s in STATS}
    for (pid, s), (row, m) in rows.items():
        st = bx.get(int(pid))
        if not st:
            continue
        line, mu, pe, p10, p50, pm, src = row
        y = st.get(STAT_BOX[s], 0)
        if y == line:
            continue
        over = y > line
        a = per[s]
        a[0] += 1
        for i, p in enumerate((pe, p10, p50)):
            a[1 + i] += _ll(p, over)
            a[4 + i] += (p - (1 if over else 0)) ** 2
        if pm is not None:
            a[7] += 1
            a[8] += _ll(pm, over)
            for i, p in enumerate((pe, p10, p50)):
                a[9 + i] += _ll(p, over)
    return per


def gap_pick(rows):
    """The page's Biggest gap for one game, from its recorded rows. rows: {(pid, stat): (row, meta)}.
    Eligible: priced props of each team's SHOWN highest-minute players among the players recorded (meta 'min', as first recorded). The model's side is the side it
    gives more than 50%; the gap is the model's chance for that side minus the price's chance for it. Returns the pick, or None."""
    by_team = {}
    for (pid, s), (row, m) in rows.items():
        if m.get('min') is not None:
            by_team.setdefault(m['team'], {})[m['pid']] = m['min']
    shown = {(t, pid) for t, mins in by_team.items() for pid, _ in sorted(mins.items(), key=lambda kv: (-kv[1], kv[0]))[:SHOWN]}
    best = None
    for (pid, s), (row, m) in rows.items():
        line, mu, pe, p10, p50, pm, src = row
        if pm is None or (m['team'], m['pid']) not in shown:
            continue
        over = pe >= .5
        p_side, p_mkt = (pe, pm) if over else (1 - pe, 1 - pm)
        key = (p_side - p_mkt, -STATS.index(s), -m['pid'])
        if best is None or key > best[0]:
            best = (key, {'pid': m['pid'], 'player': m['player'], 'team': m['team'], 'stat': s, 'side': 'over' if over else 'under', 'line': line,
                          'mu': mu, 'p': round(p_side, 4), 'pm': round(p_mkt, 4)})
    return best[1] if best else None


def settle_gap(pick, bx):
    """Result of one pick against the box score: W, L, P (landed on the line) or D (did not play, props void). Returns (result, actual)."""
    st = bx.get(int(pick['pid']))
    if not st:
        return 'D', None
    y = st.get(STAT_BOX[pick['stat']], 0)
    if y == pick['line']:
        return 'P', y
    return ('W' if (y > pick['line']) == (pick['side'] == 'over') else 'L'), y


def record_all(root, now, prev, prev_gap, rescan_days, games, L):
    """Per tip day: (psim_days, gap_days). psim_days is each final game's last pre-tip prop probabilities scored against the box score
    (see the module doc). gap_days is the Biggest gap pick of each final game from the same last pre-tip rows, settled from the same box score.
    L is the ledger module, passed in because ledger imports this module. Days outside the rescan window are kept."""
    days, gap_days = dict(prev or {}), dict(prev_gap or {})
    since = L.tip_day(now - rescan_days * 86400)
    G = {}
    for k, x in L.load_src(root, 'psim', since).items():
        m = x['meta']
        pre = [v for t, v in sorted(x['series']) if v is not None and m and t < m['tip']]
        if not m or not pre or now < m['tip'] + L.SETTLE_AFTER_S or (games and not games(str(m['game']))):
            continue
        e = G.setdefault(m['game'], {'meta': m, 'rows': {}})
        e['rows'][(m['pid'], m['stat'])] = (pre[-1], m)
    per_day, gap_per_day = {}, {}
    for gid, e in G.items():
        bx = L.box(root, gid)
        if bx is None:
            continue
        m = e['meta']
        pick = gap_pick(e['rows'])
        if pick:
            res, y = settle_gap(pick, bx)
            gap_per_day.setdefault(L.tip_day(m['tip']), []).append({'game': gid, 'matchup': m['matchup'], 'tip': m['tip'], **pick, 'y': y, 'r': res})
        per = score(e['rows'], bx)
        if not any(v[0] for v in per.values()):
            continue
        entry = {'game': gid, 'matchup': m['matchup'], 'tip': m['tip'], 's': {s: [round(x, 4) for x in v] for s, v in per.items() if v[0]}}
        per_day.setdefault(L.tip_day(m['tip']), []).append(entry)
    for d, gs in per_day.items():
        days[d] = sorted(gs, key=lambda g: g['tip'])
    for d, gs in gap_per_day.items():
        gap_days[d] = sorted(gs, key=lambda g: g['tip'])
    return days, gap_days


def record(root, now, prev, rescan_days, games, L):
    """psim_days alone (kept for callers that do not want the Biggest gap record)."""
    return record_all(root, now, prev, None, rescan_days, games, L)[0]


if __name__ == '__main__':
    # smoke test on the example board: log one game as if it tipped in an hour, score it against made-up results
    import json, random
    d = json.load(open(os.path.join(HERE, '..', 'data', 'prop_board.json')))['example']
    g = d['games'][0]
    rows, meta = log(d, g['tip'] - 3600)
    print(len(rows), 'props recorded for', g['away'], '@', g['home'])
    for k in list(rows)[:5]:
        print(k, rows[k], meta[k]['player'])
    random.seed(1)
    bx = {}
    for k, (row, m) in ((k, (rows[k], meta[k])) for k in rows):
        bx.setdefault(m['pid'], {})[STAT_BOX[m['stat']]] = max(0, round(row[1] + random.gauss(0, row[1] ** .5)))
    per = score({(meta[k]['pid'], meta[k]['stat']): (rows[k], meta[k]) for k in rows}, bx)
    for s, v in per.items():
        if v[0]:
            print(s, 'n', int(v[0]), 'll exact/10k/50', [round(x / v[0], 3) for x in v[1:4]])
