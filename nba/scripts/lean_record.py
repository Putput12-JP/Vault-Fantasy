#!/usr/bin/env python3
"""
Lean record: the model's side on every priced prop, whether or not it is an edge. Rules: docs/lean-tracking.md (pre-registered 2026-10-22).

The shadow ledger (ledger.py) logs bets: a prop enters only when its price edge or consensus gap reaches 3%. This records the model's
LEAN (over or under the posted line) for every prop, so hit rate, gap dose-response and the always-under baseline can be measured. Nothing
here is a bet and nothing here changes a price.

  log(board, now)  -> (rows, meta) for Day.record('leans', ...), called by snapshot.py after each poll, for games tipping within TRACK_H.
                      One row per priced prop on the 8 priced markets:  key  gid|pid|stat   (change-only, like every other source)
                      [line, mu, sd, p_model, side, p_blend, p_mkt, min, starter, price, book, src]
                        line     the main line: the sportsbook line most books agree on, else a pick'em app's (prop_sim_record.main_line)
                        mu, sd   the model's mean and standard deviation for the player in that game
                        p_model  calibrated model P(over line), NO market blend. This is the headline lean's probability.
                        side     'O' when p_model > 0.5, else 'U'
                        p_blend  the blended fair the ledger prices with (model + market), or null with no market to blend
                        p_mkt    the over chance in the price at that line, vig removed, or null for a flat pick'em line
                        min      projected minutes
                        starter  1 / 0 when NBA.com's five for the team is known, null when it is not
                        price    best American price for the leaned side at the line across sportsbooks, or null (never inferred)
                        book     the book that holds that price
                        src      'books' or 'pickem'
                      Two clocks come from the change log itself: the first row for a key is `first`, the last before tip is `close`.
                      meta carries 'held' (roster guard / returning / preseason reason) when one applies: held leans are recorded and
                      tagged, and the settle step decides what counts.
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

TRACK_H = 24                               # same window as the ledger
STATS = ['pts', 'reb', 'ast', '3pm', 'pra', 'pr', 'pa', 'ra']      # the priced markets; pricing.EXTRA stays out, as in the ledger


def best_price(e, line, side):
    """(american string, book) with the lowest implied chance (best payout) among sportsbook rows at this line, else (None, None)."""
    import pricing as PX
    best = None
    for r in e.get('books', []):
        if r[1] != line:
            continue
        a = r[2] if side == 'O' else r[3]
        p = PX.am_p(a)
        if p is not None and (best is None or p < best[0]):
            best = (p, a, r[0])
    return (best[1], best[2]) if best else (None, None)


def log(board, now):
    rows, meta = {}, {}
    if not board or not board.get('games') or not board.get('props'):
        return rows, meta
    import pricing as PX
    from prop_sim_record import main_line
    pr = PX.Pricer(example=bool(board.get('example')))
    games = {str(g['id']): g for g in board['games']}
    outs, status, cache = PX.outs_from_board(board), PX.status_from_board(board), {}
    fives = board.get('starters') or {}
    for e in board['props']:
        s = e['s']
        g = games.get(str(e['g']))
        if s not in STATS or not g or not (now < g['tip'] <= now + TRACK_H * 3600):
            continue
        try:
            ml = main_line(e)
            if not ml:
                continue
            line, p_mkt, src = ml
            P = (board.get('players') or {}).get(str(e['p'])) or (board.get('players') or {}).get(e['p'])
            team = P[1] if P else None
            m = pr.mu_for(int(e['p']), s, g, cache, outs, team, status)
            if not m or not (m['min'] > 0):
                continue
            hold = pr.roster_hold(m['team'], g, status, cache, m.get('src')) or pr.returning_hold(int(e['p']), m['team'], g)
            mu = m['mu']
            v0, v1, v2, v3 = pr.PR['variance'][s]
            sd = math.sqrt(max(.25, v0 + v1 * mu + v2 * mu * mu + (v3 * m['extra'] if v3 else 0)))
            pm = pr.cal(s, pr.p_over_raw(s, mu, line, m['extra']))
            side = 'O' if pm > 0.5 else 'U'
            bc = pr.PR['book'].get(s)
            pb = PX.blend(bc, p_mkt, pm) if bc and p_mkt is not None else None
            five = fives.get(m['team'])
            price, book = best_price(e, line, side) if src == 'books' else (None, None)
            k = f"{e['g']}|{e['p']}|{s}"
            rows[k] = [line, round(mu, 3), round(sd, 3), round(pm, 4), side, None if pb is None else round(pb, 4),
                       None if p_mkt is None else round(p_mkt, 4), round(m['min'], 1),
                       (1 if int(e['p']) in {int(x) for x in five} else 0) if five else None, price, book, src]
            meta[k] = {'game': str(e['g']), 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'pid': int(e['p']),
                       'player': P[0] if P else str(e['p']), 'team': m['team'], 'stat': s, 'kind': 'lean'}
            if hold:
                meta[k]['held'] = hold['why']
        except Exception as ex:                                               # one prop's failure never stops the recorder
            PX.row_error(f"lean {e.get('g')}|{e.get('p')}|{s}", ex)
    return rows, meta


if __name__ == '__main__':
    import json, subprocess, time
    src = sys.argv[1] if len(sys.argv) > 1 else None
    board = json.load(open(src)) if src else json.loads(subprocess.run(['git', 'show', 'origin/nba-live:board.json'], capture_output=True, text=True).stdout)
    t0 = time.time()
    now = int(sys.argv[2]) if len(sys.argv) > 2 else board['t']
    rows, meta = log(board, now)
    print(len(rows), 'leans in', round(time.time() - t0, 1), 's')
    for k in list(rows)[:8]:
        print(meta[k]['player'], meta[k]['stat'], rows[k], meta[k].get('held', ''))
    print('held:', sum(1 for m in meta.values() if m.get('held')), ' O:', sum(1 for r in rows.values() if r[4] == 'O'), ' U:', sum(1 for r in rows.values() if r[4] == 'U'))
    print('row errors:', PX.ROW_ERRORS[:3] if (PX := __import__('pricing')) else '')
