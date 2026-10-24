#!/usr/bin/env python3
"""
Game picks: the Vault line's side against the spread and straight up, locked before tip and graded in public. Rules: docs/game-picks.md.

The model is the game model already on the Slate page (build_game_model.py, shipped as model_state.json `game`, scored live by
sim_engine.vault_mean): team ratings, home court, back-to-back, and the value of whoever the injury report says is out. Nothing here
changes it and nothing here adds a constant to it. This module only writes down what it said and what the market said at that moment,
then scores both against the final.

  log(board, now)   -> (rows, meta) for Day.record('gpick', ...), called by snapshot.py after each poll, for regular-season games
                       tipping within WINDOW_H. One row per game (change-only, like every other source):
                         gid  [margin, total, p_home, book, spread, home_px, away_px, home_ml, away_ml]   (written only once a spread is posted)
                           margin   the model's home margin (positive = home wins by that many)
                           total    the model's total, context only: no total pick is made
                           p_home   Normal(margin / sd_margin), the sd measured on the tune seasons (model_state game.sd_margin)
                           book     the sportsbook the line came from (BOOK_ORDER, first with a spread)
                           spread   that book's HOME spread (negative = home favoured); prices are American strings as posted
                           home_ml, away_ml   moneyline from the first book in BOOK_ORDER that posted both, never inferred
                       The first row for a game is the `first` clock, the last before tip is `close`.
  record(...)       -> per tip day: each final game's two clocks graded against the final score. Called by ledger.settle.

Definitions (fixed in docs/game-picks.md before any pick was graded):
  ATS pick   edge = margin + spread. Edge above 0: home covers by the model, so the pick is HOME at `spread`; below 0: AWAY at -spread.
             Result is the final margin + spread against 0, a push at exactly 0. Units: 1 unit at the posted price of the picked side, null
             when none was stored (a price is never inferred); a push is 0.
  Winner     the team the model gives better than even odds. Graded straight up. Units: 1 unit at the stored moneyline of that team.
  CLV        ATS: how far the spread moved from `first` to `close` in the picked side's favour (points; positive = we got the better number).
             Winner: the no-vig chance of the picked team at close minus at first, when both clocks carry both moneylines.
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

WINDOW_H = 4                                   # a game is picked from this many hours before tip: lineups and injuries have mostly settled (as sim_record)
BOOK_ORDER = ['DraftKings', 'Pinnacle', 'FanDuel', 'BetMGM', 'bet365', 'Consensus']   # the backtest's book first (data/game_model.json: DraftKings where available)
DAY_KEYS = ('f', 'c')                          # clock: first sighting (the headline) and last before tip
COLS = ['game', 'clock', 'margin', 'total', 'p_home', 'book', 'spread', 'ats_side', 'ats_edge', 'ats_px', 'ats_res', 'ats_units',
        'ml_side', 'ml_px', 'ml_res', 'ml_units', 'ml_book', 'am', 'clv_pts', 'clv_p', 'src']


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def pick_line(g):
    """{'book', 'spread', 'home_px', 'away_px', 'home_ml', 'away_ml', 'ml_book'} from the board game g's books, or None with no spread.
    The spread and its prices come from ONE book row; the moneyline from the first book in order that posted both sides."""
    books = ((g.get('mk') or {}).get('books')) or []
    by = {r[0]: r for r in books}
    order = BOOK_ORDER + [b for b in by if b not in BOOK_ORDER]
    sp = next((by[b] for b in order if b in by and by[b][1] is not None), None)
    if not sp:
        return None
    ml = next((by[b] for b in order if b in by and by[b][4] not in (None, '') and by[b][5] not in (None, '')), None)
    return {'book': sp[0], 'spread': float(sp[1]), 'home_px': sp[2], 'away_px': sp[3],
            'home_ml': ml[4] if ml else None, 'away_ml': ml[5] if ml else None, 'ml_book': ml[0] if ml else None}


def ats_pick(margin, spread):
    """('H' | 'A', edge in points) for a model home margin and a home spread, or None when they agree exactly (no lean)."""
    e = margin + spread
    if e == 0:
        return None
    return ('H' if e > 0 else 'A'), abs(e)


def ats_grade(side, spread, am):
    """'W' / 'L' / 'P' for a pick on side 'H' or 'A' given the home spread and the actual home margin am."""
    cover = am + spread
    if cover == 0:
        return 'P'
    return 'W' if (cover > 0) == (side == 'H') else 'L'


def winner_pick(p_home):
    """'H' / 'A' for the team the model gives better than even odds, None at exactly even."""
    return None if p_home == 0.5 else ('H' if p_home > 0.5 else 'A')


def winner_grade(side, am):
    return 'W' if (am > 0) == (side == 'H') else 'L'


def devig(a, b):
    """No-vig chance of the first side from two American prices, or None when either is missing / unreadable."""
    import pricing as PX
    pa, pb = PX.am_p(a), PX.am_p(b)
    if pa is None or pb is None or pa + pb <= 0:
        return None
    return pa / (pa + pb)


def log(board, now):
    rows, meta = {}, {}
    if not board or not board.get('games'):
        return rows, meta
    import pricing as PX, sim_engine as SE
    pr = PX.Pricer(example=bool(board.get('example')))
    G = (pr.MS_all or {}).get('game')
    if not G or not G.get('sd_margin'):
        return rows, meta
    for g in board['games']:
        if not (now < g['tip'] <= now + WINDOW_H * 3600):
            continue
        try:
            mean = SE.vault_mean(pr, g, board)               # None before the regular season, or with no game model state
            if not mean:
                continue
            ln = pick_line(g)
            if not ln:                                       # no book has posted a spread yet: wait, so the first look is a pick with a line, never a bare lean
                continue
            m = float(mean['m'])
            k = str(g['id'])
            rows[k] = [round(m, 2), round(float(mean['t']), 1), round(phi(m / G['sd_margin']), 4), ln.get('book'), ln.get('spread'),
                       ln.get('home_px'), ln.get('away_px'), ln.get('home_ml'), ln.get('away_ml')]
            meta[k] = {'game': k, 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'away': g['away'], 'home': g['home'],
                       'ml_book': ln.get('ml_book'), 'kind': 'gpick'}
        except Exception as ex:                              # one game's failure never stops the recorder
            PX.row_error(f"gpick {g.get('id')}", ex)
    return rows, meta


def write_open(root, day, now, sub='gpicks'):
    """<root>/<sub>/open.json: today's picks that have not settled yet, for the Game Picks page. {'t', 'games': {gid: {'m': meta, 'f': first row,
    'c': last row so far}}}. The first row is the locked pick and never changes once written; `c` follows the market until tip. Settled games move to
    <sub>/<day>.json (record), so this file only ever holds the current day's folder. Rows come from the Day object the recorder already holds."""
    import json as _json
    meta, first, last = day.meta.get('gpick') or {}, day.first.get('gpick') or {}, day.last.get('gpick') or {}
    games = {}
    for k, m in meta.items():
        if k in first:
            games[k] = {'m': {x: m.get(x) for x in ('game', 'tip', 'matchup', 'away', 'home', 'ml_book')}, 'f': first[k], 'c': last.get(k, first[k])}
    os.makedirs(os.path.join(root, sub), exist_ok=True)
    with open(os.path.join(root, sub, 'open.json'), 'w') as f:
        _json.dump({'t': now, 'cols': COLS, 'games': games}, f, separators=(',', ':'))
    return len(games)


# ── settling ─────────────────────────────────────────────────────────────────────────────────
def grade_row(v, am, clock, first=None, profit=None):
    """One graded line for the stored row v at a clock. profit(price_string, won) -> units, injected so tests need no ledger.
    Returns the COLS values after 'game' and before 'src' are the caller's to add: [clock, margin, ..., clv_p]."""
    margin, total, p_home, book, spread, hpx, apx, hml, aml = v[:9]
    ats = ats_pick(margin, spread) if spread is not None else None
    side = edge = px = res = units = None
    if ats:
        side, edge = ats
        px = hpx if side == 'H' else apx
        res = ats_grade(side, spread, am)
        if res != 'P' and px not in (None, '') and profit:
            units = round(profit(px, res == 'W'), 4)
        elif res == 'P':
            units = 0.0
    mside = winner_pick(p_home)
    mpx = mres = munits = None
    if mside:
        mpx = hml if mside == 'H' else aml
        mres = winner_grade(mside, am)
        if mpx not in (None, '') and profit:
            munits = round(profit(mpx, mres == 'W'), 4)
    clv_pts = clv_p = None
    if first is not None and clock == 'c':                   # CLV is a close-clock number: how the line moved after we locked
        f_spread = first[4]
        if ats and f_spread is not None and spread is not None:
            f_ats = ats_pick(first[0], f_spread)
            if f_ats:
                fs = f_ats[0]                                # the side the LOCKED pick took, at the locked number
                clv_pts = round((f_spread - spread) if fs == 'H' else (spread - f_spread), 2)
        if mside:
            p_first, p_close = devig(first[7], first[8]), devig(hml, aml)
            fm = winner_pick(first[2])
            if fm and p_first is not None and p_close is not None:
                clv_p = round((p_close - p_first) * (1 if fm == 'H' else -1), 4)
    return [clock, margin, total, p_home, book, spread, side, None if edge is None else round(edge, 2), px, res, units,
            mside, mpx, mres, munits, None, am, clv_pts, clv_p]


def record(root, now, prev, rescan_days, games, L, sub='gpicks'):
    """Settle every final game's pick from the box score. Writes <root>/<sub>/<tip ET day>.json for each day in the rescan window:
        {'day', 'cols': COLS, 'games': {gid: [matchup, tip, away, home, away score, home score]}, 'rows': [[...COLS]]}
    two rows per game (clock 'f' first sighting, 'c' last before tip), each graded against its own line. The pick is the FIRST clock's;
    the close row is the same game re-read at the close, kept for the CLV and for "did the pick flip" (compare ats_side across clocks).
    Returns {day: {'f': {'ats': [n, w, l, p], 'ml': [n, w, l]}, 'c': {...}}}, merged over `prev`. `games` picks which games count."""
    import json as _json
    out = dict(prev or {})
    since = L.tip_day(now - rescan_days * 86400)
    per = {}
    for gid, x in L.load_src(root, 'gpick', since).items():
        m = x['meta']
        pre = [v for t, v in sorted(x['series'], key=lambda z: (z[0], z[1] is None)) if v is not None and m and t < m['tip']]
        if not m or not pre or L.tip_day(m['tip']) < since or now < m['tip'] + L.SETTLE_AFTER_S or (games and not games(str(m['game']))):
            continue
        per[gid] = (m, pre[0], pre[-1])
    days = {}
    for gid, (m, first, close) in per.items():
        if L.box(root, gid) is None:
            continue
        sc = (L.box_meta(root, gid).get('score')) or {}
        if m['home'] not in sc or m['away'] not in sc:
            continue
        am = sc[m['home']] - sc[m['away']]
        day = L.tip_day(m['tip'])
        d = days.setdefault(day, {'games': {}, 'rows': []})
        d['games'][gid] = [m['matchup'], m['tip'], m['away'], m['home'], sc[m['away']], sc[m['home']]]
        for clock, v in (('f', first), ('c', close)):
            r = grade_row(v, am, clock, first, lambda px, won: L.profit('book', px, won))
            r[COLS.index('ml_book') - 1] = m.get('ml_book')          # grade_row's list starts after 'game'
            d['rows'].append([gid] + r + ['live'])
    os.makedirs(os.path.join(root, sub), exist_ok=True)
    for day, d in days.items():
        d['rows'].sort(key=lambda r: (r[0], r[1]))
        with open(os.path.join(root, sub, f'{day}.json'), 'w') as f:
            _json.dump({'day': day, 'cols': COLS, 'games': d['games'], 'rows': d['rows']}, f, separators=(',', ':'))
        out[day] = summarize(d['rows'])
    return out


def summarize(rows):
    """{'f': {'ats': [n, w, l, p], 'ml': [n, w, l]}, 'c': {...}} for a list of COLS rows."""
    i = {c: COLS.index(c) for c in COLS}
    s = {k: {'ats': [0, 0, 0, 0], 'ml': [0, 0, 0]} for k in DAY_KEYS}
    for r in rows:
        c = s[r[i['clock']]]
        if r[i['ats_res']]:
            c['ats'][0] += 1
            c['ats'][{'W': 1, 'L': 2, 'P': 3}[r[i['ats_res']]]] += 1
        if r[i['ml_res']]:
            c['ml'][0] += 1
            c['ml'][{'W': 1, 'L': 2}[r[i['ml_res']]]] += 1
    return s


if __name__ == '__main__':
    import json, subprocess, time
    src = sys.argv[1] if len(sys.argv) > 1 else None
    board = json.load(open(src)) if src else json.loads(subprocess.run(['git', 'show', 'origin/nba-live:board.json'], capture_output=True, text=True).stdout)
    now = int(sys.argv[2]) if len(sys.argv) > 2 else int(min(g['tip'] for g in board['games'] if g['tip'] > board['t']) - 2 * 3600)
    t0 = time.time()
    rows, meta = log(board, now)
    print(len(rows), 'game picks in', round(time.time() - t0, 1), 's  (now = tip - %.1fh)' % ((min(g['tip'] for g in board['games'] if g['tip'] > now) - now) / 3600))
    for k, v in rows.items():
        m = meta[k]
        ats = ats_pick(v[0], v[4]) if v[4] is not None else None
        print(f"{m['matchup']:12s} model home {v[0]:+6.1f}  p_home {v[2]:.3f}  {v[3]} spread {v[4]}  px {v[5]}/{v[6]}  ml {v[7]}/{v[8]}  -> ATS {ats}  winner {winner_pick(v[2])}")
