"""cfb_jp_novig: paper-trade JP+ edges against the sportsbook open on Novig's CFB spread ladder.

PAPER ONLY. Nothing here sends an order, and Novig is read through public endpoints with no key.
Rules, fixed in advance (the backtest and its limits: /workspace/cfb-backtests/RESULTS.md, Update 4):

  trigger    JP+ model_margin vs the sportsbook open (open_margin) on the board in data/cfb_model.json,
             CFB week 8+ and bowls. Edges of 3+, 5+ and 7+ points are all logged (edge_bucket is the
             highest threshold reached, so the slices are cumulative); only 5+ counts toward the pass bar.
  strike     the first time the game's Novig spread ladder is seen, the strike whose handicap for JP+'s
             team is nearest the sportsbook open. A tie goes to the strike giving JP+'s team more points.
             The choice is stored and never changed.
  snapshots  every 30 minutes (a run counts a snapshot as due after 25), Novig and the equivalent Kalshi
             KXNCAAFSPREAD market, with the first-listed time of each venue.
  entry      paper-buy at the ask on the first snapshot that has an ask with at least 4 contracts within
             2 cents of it; size is 25% of the contracts offered within 2 cents of the best ask, rounded
             down, then capped at 5% of the bankroll per trade and $150 per ET day of entry for this
             strategy. uncapped_contracts and uncapped_stake keep the pre-cap size.
             entry_delay_min records how long after the first snapshot that was.
  exit       paper-sell at the last bid on a snapshot taken before kick (exit_gap_min is how long before).
             Only the bid size stored on that snapshot (contracts within 2 cents of the bid) can fill; the
             rest is held to settlement. exit_fill_frac records the share sold. Only the best bid and the
             size within 2 cents are stored, not the levels, so the fill is priced at the best bid.
             A partial row has its exit P&L now and its blended P&L (exit part plus hold part) once graded;
             it joins the pass-bar sample only when blended. No bid on any pre-kick snapshot means no exit:
             the row is void and not in the pass-bar sample.
  hold       the same entry held to the final score is tracked as hold_pnl, graded after the game.
  fees       Novig pregame fee is 0. P&L is in dollars per $1-payout contract (Novig quantity / 100).
  pass bar   mean profit per contract (exit bid minus entry ask) > 0, z >= 2, over 60+ trades at 5+ edges.

The paper book is separate from the Kalshi book: rows carry book='novig', so they do not touch cash, the
daily caps, the loss stop or the equity curve. Trades are ledger rows with source/strategy 'cfb_jp_novig';
snapshots, first-listed times and progress live in ledger['strategies']['cfb_jp_novig'].

Every network call is guarded. A Novig, Kalshi or results failure becomes a run note.
"""
import json
import math
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .ledger import et_day, iso
from .novig_public import NovigPublic, outcome_quote, parse_outcome, uuid7_ms
from .quotes import side_bid, side_price, side_size
from .signals.cfb_ml import _abbr_of, _finite, _label_matches, _rating_index, _side_names
from .signals.nba_total import ticker_date

ET = ZoneInfo('America/New_York')

STRATEGY = 'cfb_jp_novig'
BOOK = 'novig'
KALSHI_SERIES = 'KXNCAAFSPREAD'

MIN_WEEK = 8
EDGE_LOG, EDGE_PASS, EDGE_HIGH = 3.0, 5.0, 7.0
SIZE_FRACTION = 0.25
MAX_STAKE_FRACTION = 0.05        # of the bankroll, per trade ($50 on $1000)
MAX_STAKE_PER_DAY = 150.0        # this strategy, by ET date of entry
MIN_DEPTH_CONTRACTS = 4          # 25% of this is one contract
SNAP_EVERY_S = 30 * 60
SNAP_DUE_S = 25 * 60             # a 30-minute cron that fires a little early still snapshots
EVENT_WINDOW_S = 6 * 3600        # Novig event start vs the board's kick
STALE_EXIT_MIN = 45
NO_RESULT_DAYS = 10
KEEP_PRE_KICK_S = 6 * 3600       # snapshots kept per graded game: the first, the entry, and the last 6 hours

PASS_N, PASS_Z = 60, 2.0
SLICES = (('3+', EDGE_LOG), ('5+', EDGE_PASS), ('7+', EDGE_HIGH))

ESPN_SCOREBOARD = ('https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard'
                   '?groups=80&limit=400&dates=')


# ---- trigger ---------------------------------------------------------------------------------

def jp_edge(game):
    """(abs_edge_pts, 'home'|'away') from JP+'s margin vs the sportsbook open, or None.

    open_margin is the home team's expected margin at the open (home -7.5 is 7.5). Positive signed
    edge means JP+ likes the home side more than the open does.
    """
    mm, om = _finite(game.get('model_margin')), _finite(game.get('open_margin'))
    if mm is None or om is None:
        return None
    e = mm - om                     # unrounded: bucket_of carries the float tolerance, rounding here could lift 4.96 to 5
    if abs(e) < 1e-9:
        return None
    return abs(e), ('home' if e > 0 else 'away')


def bucket_of(abs_edge):
    """'7+', '5+', '3+' (the highest threshold reached) or None under 3 points."""
    if abs_edge is None or abs_edge < EDGE_LOG - 1e-9:
        return None
    if abs_edge >= EDGE_HIGH - 1e-9:
        return '7+'
    if abs_edge >= EDGE_PASS - 1e-9:
        return '5+'
    return '3+'


def is_bowl(game, kick_ts):
    """Postseason flag from the row when it has one, else the calendar (Dec 14 to Jan 20, ET).

    CFBD restarts the week count in the postseason, so a bowl can carry a small week number.
    """
    for k in ('season_type', 'seasonType'):
        if str(game.get(k) or '').lower() in ('post', 'postseason'):
            return True
    if game.get('bowl') is True:
        return True
    d = datetime.fromtimestamp(float(kick_ts), ET).date()
    return (d.month == 12 and d.day >= 14) or (d.month == 1 and d.day <= 20)


def week_ok(game):
    try:
        kick = float(game.get('kick'))
    except (TypeError, ValueError):
        return False
    try:
        wk = int(game.get('week') or 0)
    except (TypeError, ValueError):
        wk = 0
    return wk >= MIN_WEEK or is_bowl(game, kick)


def open_handicap(game, side):
    """The sportsbook open as a handicap for `side` (negative = favourite)."""
    om = float(game['open_margin'])
    return -om if side == 'home' else om


def triggers(board, now_ts):
    """Upcoming board games that clear the week filter and a 3+ point edge, as dicts."""
    out = []
    for g in board or []:
        try:
            kick = float(g.get('kick'))
        except (TypeError, ValueError):
            continue
        if kick <= now_ts or not week_ok(g) or not g.get('home') or not g.get('away'):
            continue
        je = jp_edge(g)
        if je is None or bucket_of(je[0]) is None:
            continue
        edge, side = je
        out.append({
            'key': g.get('key') or f"{g['away']}@{g['home']}:{int(kick)}",
            'game': g, 'kick': kick, 'edge': round(edge, 6), 'bucket': bucket_of(edge), 'side': side,
            'team': g['home'] if side == 'home' else g['away'],
            'open_hcap': open_handicap(g, side),
        })
    return out


# ---- Novig matching and strike choice -----------------------------------------------------------

def _code_matches(code, names, abbr):
    c = str(code or '').lower()
    if not c:
        return False
    if abbr and c == str(abbr).lower():
        return True
    for n in names:
        words = re.findall(r'[a-z0-9]+', str(n).lower())
        if len(c) >= 3 and any(w.startswith(c) for w in words):
            return True
        initials = ''.join(w[0] for w in words if w not in ('of', 'the'))
        if c in (initials, 'u' + initials):
            return True
    return False


def match_event(game, ratings, events):
    """The one Novig event for this board game, or None. 'Away @ Home' names, either order (neutral sites)."""
    kick = float(game['kick'])
    hn, _ = _side_names(game, 'home', ratings)
    an, _ = _side_names(game, 'away', ratings)
    habbr, aabbr = _abbr_of(game, 'home', ratings), _abbr_of(game, 'away', ratings)
    hits = []
    for e in events or []:
        m = re.match(r'(.+?) @ (.+)', e.get('description') or '')
        if not m:
            continue
        try:
            start = float(e.get('startsTs')) / 1000.0
        except (TypeError, ValueError):
            continue
        if abs(start - kick) > EVENT_WINDOW_S:
            continue
        a, h = m.group(1).strip(), m.group(2).strip()
        fwd = _label_matches(h, hn, habbr) and _label_matches(a, an, aabbr)
        rev = _label_matches(a, hn, habbr) and _label_matches(h, an, aabbr)
        if fwd or rev:
            hits.append(e)
    return hits[0] if len(hits) == 1 else None


def spread_ladder(markets):
    """[(market, [(code, handicap), (code, handicap)])] for open two-outcome SPREAD markets."""
    out = []
    for mk in markets or []:
        if mk.get('marketType') != 'SPREAD' or mk.get('status') != 'OPEN':
            continue
        outs = mk.get('outcomes') or []
        if len(outs) != 2:
            continue
        parsed = [parse_outcome(o.get('name')) for o in outs]
        if None in parsed:
            continue
        out.append((mk, parsed))
    return out


def code_sides(game, ratings, ladder, open_margin):
    """({code: 'home'|'away'}, how) from the ladder's team codes, or (None, reason).

    Novig outcome names carry a short code ('HAW', 'UNM'), not the team name. Order of evidence: the
    model's abbreviation or the name; then the other code by elimination; then, when the sportsbook
    open is 3+ points, the favourite code (all negative handicaps) is the open's favourite.
    """
    codes = sorted({c for _, parsed in ladder for c, _ in parsed})
    if len(codes) != 2:
        return None, f'{len(codes)} team codes on the ladder'
    hn, _ = _side_names(game, 'home', ratings)
    an, _ = _side_names(game, 'away', ratings)
    habbr, aabbr = _abbr_of(game, 'home', ratings), _abbr_of(game, 'away', ratings)
    found = {}
    for c in codes:
        h, a = _code_matches(c, hn, habbr), _code_matches(c, an, aabbr)
        if h and not a:
            found[c] = 'home'
        elif a and not h:
            found[c] = 'away'
    if len(found) == 2 and set(found.values()) == {'home', 'away'}:
        return found, 'name'
    if len(found) == 1:
        (c, s), = found.items()
        other = codes[0] if codes[1] == c else codes[1]
        return {c: s, other: 'away' if s == 'home' else 'home'}, 'name+elimination'
    neg = {c for c in codes if all(h < 0 for _, p in ladder for cc, h in p if cc == c)}
    pos = {c for c in codes if all(h > 0 for _, p in ladder for cc, h in p if cc == c)}
    if len(neg) == 1 and len(pos) == 1 and abs(open_margin) >= 3:
        fav, dog = next(iter(neg)), next(iter(pos))
        home_fav = open_margin > 0
        return {fav: 'home' if home_fav else 'away', dog: 'away' if home_fav else 'home'}, 'sign'
    return None, f'could not map codes {codes} to the teams'


def choose_strike(ladder, team_code, open_hcap):
    """The (market, outcome index, handicap) nearest the open for team_code; ties go to more points for the team."""
    best = None
    for mk, parsed in ladder:
        for i, (code, h) in enumerate(parsed):
            if code != team_code:
                continue
            key = (round(abs(h - open_hcap), 6), -h)
            if best is None or key < best[0]:
                best = (key, mk, i, h)
    if best is None:
        return None
    _, mk, i, h = best
    outs = mk['outcomes']
    return {'market_id': mk['marketId'], 'outcome_id': outs[i]['outcomeId'], 'other_id': outs[1 - i]['outcomeId'],
            'hcap': h}


# ---- Kalshi (comparison only) ---------------------------------------------------------------------

_KALSHI_SUB = re.compile(r'^(.*?)\s+wins by over\s+([\d.]+)\s+points', re.I)


def _iso_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp()
    except (TypeError, ValueError):
        return None


def kalshi_find(markets, game, ratings, hcap, team_side):
    """{'event', 'listed_ts', 'quote', 'side', 'floor'} for the Kalshi market equivalent to JP+'s team at hcap.

    A team wins by over K points is that team at -K. JP+'s team at -K is YES on its own market. JP+'s team at +K
    is NO on the OTHER team's "wins by over K". quote is None while the event is listed but that strike is not.
    Returns None when no event matches the game.

    Pushes: Novig refunds the price when the margin lands exactly on an integer strike. Kalshi has no push:
    "wins by over K" is NO at exactly K, so YES loses and NO wins in full. At an integer strike the two venues
    are not the same bet, so push_mismatch is True and the quote is a price reference only, never a like for like.
    """
    kick = float(game['kick'])
    kd = datetime.fromtimestamp(kick, ET).date()
    hn, _ = _side_names(game, 'home', ratings)
    an, _ = _side_names(game, 'away', ratings)
    habbr, aabbr = _abbr_of(game, 'home', ratings), _abbr_of(game, 'away', ratings)
    by_event = {}
    for q in markets or []:
        by_event.setdefault(q.get('event'), []).append(q)
    hits = []
    for event, rows in by_event.items():
        day, _blob = ticker_date(event or '')
        if not day or abs((kd - day).days) > 1:
            continue
        sides = set()
        for q in rows:
            m = _KALSHI_SUB.match(q.get('sub') or '')
            if not m:
                continue
            h, a = _label_matches(m.group(1), hn, habbr), _label_matches(m.group(1), an, aabbr)
            if h and not a:
                sides.add('home')
            elif a and not h:
                sides.add('away')
        if sides:
            hits.append((0 if day == kd else 1, event, rows))
    if not hits:
        return None
    hits.sort(key=lambda x: x[0])
    if len([h for h in hits if h[0] == hits[0][0]]) != 1:
        return None
    _, event, rows = hits[0]
    opens = [t for t in (_iso_ts(q.get('open_time')) for q in rows) if t is not None]
    listed = min(opens) if opens else None
    if hcap == 0:
        return {'event': event, 'listed_ts': listed, 'quote': None, 'side': None, 'floor': None, 'push_mismatch': True}
    want_side = team_side if hcap < 0 else ('away' if team_side == 'home' else 'home')
    side = 'yes' if hcap < 0 else 'no'
    floor = abs(hcap)
    quote = None
    for q in rows:
        m = _KALSHI_SUB.match(q.get('sub') or '')
        if not m or q.get('strike') is None or abs(float(q['strike']) - floor) > 1e-9:
            continue
        names, abbr = (hn, habbr) if want_side == 'home' else (an, aabbr)
        if _label_matches(m.group(1), names, abbr):
            quote = q
            break
    return {'event': event, 'listed_ts': listed, 'quote': quote, 'side': side, 'floor': floor,
            'push_mismatch': abs(floor - round(floor)) < 1e-9}


# ---- snapshots, sizing, exit, grading, pass bar -------------------------------------------------------

def snap_str(ts, bid, ask, ask_size, bid_size):
    """Compact 'ts,bid,ask,ask_size,bid_size' (empty field = no quote on that side). Keeps ledger.json small."""
    def f(v, nd):
        return '' if v is None else repr(round(float(v), nd))
    return f'{int(ts)},{f(bid, 4)},{f(ask, 4)},{f(ask_size, 2)},{f(bid_size, 2)}'


def parse_snap(s):
    parts = str(s).split(',')
    parts += [''] * (5 - len(parts))

    def f(v):
        return None if v == '' else float(v)
    return {'ts': int(parts[0]), 'bid': f(parts[1]), 'ask': f(parts[2]), 'ask_size': f(parts[3]), 'bid_size': f(parts[4])}


def try_parse_snap(s):
    """parse_snap, or None for a malformed stored snapshot (e.g. 'bad,snap')."""
    try:
        p = parse_snap(s)
    except (TypeError, ValueError):
        return None
    if any(isinstance(v, float) and not math.isfinite(v) for v in p.values()):
        return None
    return p


def valid_snaps(snaps, notes=None, label=''):
    """Parsed snapshots in stored order. A malformed one is skipped, with one note per call when notes is given."""
    out, bad = [], []
    for s in snaps or []:
        p = try_parse_snap(s)
        if p is None:
            bad.append(s)
        else:
            out.append(p)
    if bad and notes is not None:
        notes.append(f"{label}: skipped {len(bad)} malformed snapshot(s), first {str(bad[0])[:40]!r}")
    return out


def size_contracts(depth):
    """25% of the contracts offered within 2 cents of the best ask, rounded down. 0 when there is no depth."""
    try:
        d = float(depth)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(d) or d <= 0:
        return 0
    return int(math.floor(d * SIZE_FRACTION + 1e-9))


def last_pre_kick_bid(snaps, kick_ts):
    """The last parsed snapshot before kick that has a bid, or None."""
    best = None
    for p in valid_snaps(snaps):
        if p['ts'] < kick_ts and p['bid'] is not None and (best is None or p['ts'] > best['ts']):
            best = p
    return best


def apply_exit(trade, game):
    """Close the paper trade into the last pre-kick bid. Returns True once the row is decided."""
    kick = float(game['kick'])
    snap = last_pre_kick_bid((game.get('novig') or {}).get('snaps'), kick)
    if snap is None:
        trade['status'] = 'void'
        trade['void_reason'] = 'no_exit_bid'
        trade['result'] = 'void'
        trade['settled_ts'] = iso(datetime.fromtimestamp(kick, timezone.utc))
        trade['payout'] = trade['stake']
        trade['pnl'] = 0.0
        trade['won'] = None
        trade['exit_pnl_pc'] = None
        return True
    n, price = int(trade['contracts']), float(trade['price'])
    bid = snap['bid']
    size = snap['bid_size']
    filled = 0 if size is None or not math.isfinite(size) else min(n, int(math.floor(max(size, 0.0) + 1e-9)))
    rem = n - filled
    part_pc = round(bid - price, 5)
    mid = None if snap['ask'] is None else round((snap['bid'] + snap['ask']) / 2, 4)
    exit_pnl = round(filled * part_pc, 4)
    trade.update({
        'status': 'settled', 'result': 'exit' if filled else 'hold',
        'exit_ts': iso(datetime.fromtimestamp(snap['ts'], timezone.utc)),
        'exit_bid': bid, 'exit_bid_size': size,
        'exit_gap_min': round((kick - snap['ts']) / 60.0, 1),
        'settled_ts': iso(datetime.fromtimestamp(snap['ts'], timezone.utc)),
        'exit_filled_contracts': filled, 'exit_remainder_contracts': rem,
        'exit_fill_frac': round(filled / n, 4) if n else 0.0,
        'exit_part_pnl_pc': part_pc, 'exit_part_pnl': exit_pnl,
        'close_mid': mid, 'clv': None if mid is None else round(mid - price, 4),
    })
    if rem == 0:
        trade.update({'payout': round(n * bid, 4), 'exit_pnl_pc': part_pc, 'pnl': round(n * part_pc, 4), 'won': part_pc > 0,
                      'mark_value': round(n * bid, 4), 'remainder_pending': False})
    else:
        # The unfilled remainder rides to settlement. Until it is graded the row carries only the realized exit
        # part and no per-contract result, so it stays out of the pass-bar sample; grade_hold blends the two.
        trade.update({'payout': round(filled * bid, 4), 'exit_pnl_pc': None, 'pnl': exit_pnl, 'won': None,
                      'mark_value': round(rem * bid, 4), 'remainder_pending': True})
    return True


def grade_hold(trade, home_score, away_score):
    """Hold-to-settlement result for the same entry. A push refunds the price."""
    hcap, price, n = float(trade['strike']), float(trade['price']), int(trade['contracts'])
    side = (trade.get('detail') or {}).get('jp_side')
    margin = (home_score - away_score) if side == 'home' else (away_score - home_score)
    cover = margin + hcap
    if cover > 0:
        res, pay = 'win', 1.0
    elif cover < 0:
        res, pay = 'loss', 0.0
    else:
        res, pay = 'push', price
    pc = round(pay - price, 5)
    filled = trade.get('exit_filled_contracts')
    if filled is not None and trade.get('status') == 'settled' and filled < n:
        # blend: the exit part at the exit bid, the remainder at settlement (a push refunds the price)
        bid = float(trade['exit_bid'])
        pnl = round(filled * (bid - price) + (n - filled) * (pay - price), 4)
        trade.update({'payout': round(filled * bid + (n - filled) * pay, 4), 'pnl': pnl, 'exit_pnl_pc': round(pnl / n, 5),
                      'won': pnl > 0, 'mark_value': 0.0, 'remainder_pending': False,
                      'remainder_result': res})
    trade.update({'hold_status': 'graded', 'hold_result': res, 'hold_pnl_pc': pc, 'hold_pnl': round(n * pc, 4),
                  'hold_payout': round(n * pay, 4), 'final_score': {'home': home_score, 'away': away_score},
                  'hold_margin_vs_strike': round(cover, 2)})


def mean_z(vals):
    """{'n', 'mean', 'sd', 'se', 'z'}; z is None under two values or with no spread."""
    vals = [float(v) for v in vals if v is not None]
    n = len(vals)
    out = {'n': n, 'mean': None, 'sd': None, 'se': None, 'z': None}
    if not n:
        return out
    mean = sum(vals) / n
    out['mean'] = round(mean, 5)
    if n >= 2:
        sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
        out['sd'] = round(sd, 5)
        if sd > 1e-9:        # float noise on identical values is not spread
            se = sd / math.sqrt(n)
            out['se'] = round(se, 5)
            out['z'] = round(mean / se, 3)
    return out


def pass_status(stats):
    """'collecting' under 60 trades, else 'pass' (mean > 0 and z >= 2) or 'fail'."""
    if stats['n'] < PASS_N:
        return 'collecting'
    if stats['mean'] is not None and stats['mean'] > 0 and stats['z'] is not None and stats['z'] >= PASS_Z:
        return 'pass'
    return 'fail'


def _edge_of(t):
    return float(t.get('edge') or 0)


_RANK = {'3+': 1, '5+': 2, '7+': 3}


def in_slice(t, label, thr):
    """A row is in a slice by the bucket it was logged in (set from the unrounded edge); the edge value is the fallback."""
    rank = _RANK.get(t.get('edge_bucket'))
    if rank is not None:
        return rank >= _RANK[label]
    return _edge_of(t) >= thr - 1e-9


def build_progress(trades, prev=None):
    """Pass-bar progress and the 3+/5+/7+ slices from the strategy's ledger rows."""
    rows = [t for t in trades if t.get('source') == STRATEGY]
    entered = [t for t in rows if t.get('status') in ('open', 'settled', 'void')]
    slices = {}
    for label, thr in SLICES:
        sel = [t for t in entered if in_slice(t, label, thr)]
        ex = [t['exit_pnl_pc'] for t in sel if t.get('status') == 'settled' and t.get('exit_pnl_pc') is not None]
        hold = [t['hold_pnl_pc'] for t in sel if t.get('hold_status') == 'graded']
        slices[label] = {
            'entered': len(sel),
            'open': sum(1 for t in sel if t.get('status') == 'open'),
            'no_exit_bid': sum(1 for t in sel if t.get('void_reason') == 'no_exit_bid'),
            'exit': mean_z(ex),
            'hold': mean_z(hold),
        }
    p = slices['5+']['exit']
    status = pass_status(p)
    monitor = {'improving': False, 'n': p['n'], 'prev_n': None, 'prev_mean': None,
               'note': None}
    pp = (prev or {}).get('pass_bar') or {}
    if pp.get('n') is not None and p['mean'] is not None and pp.get('mean') is not None:
        monitor.update(prev_n=pp['n'], prev_mean=pp['mean'])
        if p['n'] > pp['n'] and p['mean'] > pp['mean']:
            monitor['improving'] = True
            monitor['note'] = f"5+ mean per contract rose from {pp['mean']} to {p['mean']}; monitor closely, n={p['n']}"
    return {
        'pass_bar': {
            'n': p['n'], 'n_needed': PASS_N, 'to_go': max(0, PASS_N - p['n']), 'mean': p['mean'], 'sd': p['sd'],
            'se': p['se'], 'z': p['z'], 'z_needed': PASS_Z, 'status': status,
            'rule': f'mean profit per contract after spread > 0, z >= {PASS_Z:g}, over {PASS_N}+ trades at {EDGE_PASS:g}+ point edges',
        },
        'slices': slices,
        'monitor': monitor,
        'counts': {
            'entered': len(entered), 'open': sum(1 for t in entered if t.get('status') == 'open'),
            'exited': sum(1 for t in entered if t.get('status') == 'settled'),
            'no_exit_bid': sum(1 for t in entered if t.get('void_reason') == 'no_exit_bid'),
            'stale_exits': sum(1 for t in entered if (t.get('exit_gap_min') or 0) > STALE_EXIT_MIN),
            'hold_graded': sum(1 for t in entered if t.get('hold_status') == 'graded'),
            'hold_pending': sum(1 for t in entered if t.get('hold_status') == 'pending'),
        },
    }


# ---- results ------------------------------------------------------------------------------------------

def board_result(board_game):
    """(home_score, away_score) from a board row that has been graded, else None."""
    if not board_game or board_game.get('result') is None:
        return None
    hs, as_ = _finite(board_game.get('hs')), _finite(board_game.get('as_'))
    if hs is None or as_ is None:
        return None
    return hs, as_


def espn_result(get, game, ratings, kick_ts):
    """(home, away) from ESPN's scoreboard when the event is completed, else None. Guarded by the caller."""
    hn, _ = _side_names(game, 'home', ratings)
    an, _ = _side_names(game, 'away', ratings)
    habbr, aabbr = _abbr_of(game, 'home', ratings), _abbr_of(game, 'away', ratings)
    for delta in (0, 1):
        day = datetime.fromtimestamp(float(kick_ts) + delta * 86400, ET).strftime('%Y%m%d')
        data = get(ESPN_SCOREBOARD + day)
        for ev in (data or {}).get('events') or []:
            comp = ((ev.get('competitions') or [{}])[0])
            if not ((comp.get('status') or ev.get('status') or {}).get('type') or {}).get('completed'):
                continue
            teams = {c.get('homeAway'): c for c in comp.get('competitors') or []}
            if 'home' not in teams or 'away' not in teams:
                continue
            th = (teams['home'].get('team') or {})
            ta = (teams['away'].get('team') or {})
            hmatch = any(_label_matches(x, hn, habbr) for x in (th.get('displayName'), th.get('location'), th.get('shortDisplayName')) if x)
            amatch = any(_label_matches(x, an, aabbr) for x in (ta.get('displayName'), ta.get('location'), ta.get('shortDisplayName')) if x)
            if hmatch and amatch:
                hs, as_ = _finite(teams['home'].get('score')), _finite(teams['away'].get('score'))
                if hs is not None and as_ is not None:
                    return hs, as_
    return None


# ---- the strategy ---------------------------------------------------------------------------------------

def _state(ledger):
    st = ledger.setdefault('strategies', {}).setdefault(STRATEGY, {})
    st.setdefault('games', {})
    st.setdefault('progress', {})
    st.setdefault('watch', [])
    return st


def _trade_for(ledger, game_state):
    tid = game_state.get('trade_id')
    for t in ledger['trades']:
        if t.get('id') == tid:
            return t
    return None


class CfbJpNovig:
    name = STRATEGY

    def __init__(self, cfg, root, novig=None, get=None):
        self.cfg = cfg
        self.root = root
        self.novig = novig if novig is not None else NovigPublic()
        self.get = get          # JSON GET for the ESPN fallback; None skips the fallback

    # -- inputs
    def _load_model(self):
        path = os.path.join(self.root, 'data', 'cfb_model.json')
        if not os.path.exists(path):
            return None, 'data/cfb_model.json is missing'
        try:
            with open(path) as f:
                return json.load(f), None
        except (OSError, json.JSONDecodeError) as e:
            return None, 'could not read the model: ' + str(e)[:160]

    # -- run
    def run(self, ledger, now, kalshi=None):
        """One pass. Returns a note for the run log. Never raises for a data or network failure."""
        st = _state(ledger)
        notes = []
        model, err = self._load_model()
        if model is None:
            notes.append(err)
            model = {}
        board = model.get('board') or []
        ratings = _rating_index(model.get('ratings'))
        by_key = {g.get('key'): g for g in board}
        now_ts = now.timestamp()
        ctx = {'ledger': ledger, 'st': st, 'now': now, 'now_ts': now_ts, 'ratings': ratings, 'notes': notes,
               'kalshi': kalshi, 'kq': None, 'kt': {}}

        stats = {'new': 0, 'snaps': 0, 'entered': 0, 'exited': 0, 'graded': 0, 'unlisted': 0}
        try:
            self._discover(ctx, board, stats)
        except Exception as e:
            notes.append('discover failed: ' + str(e)[:160])
        try:
            self._snapshot_due(ctx, stats)
        except Exception as e:
            notes.append('snapshots failed: ' + str(e)[:160])
        try:
            self._exits(ctx, stats)
        except Exception as e:
            notes.append('exits failed: ' + str(e)[:160])
        try:
            self._grade(ctx, by_key, ratings, stats)
        except Exception as e:
            notes.append('grading failed: ' + str(e)[:160])

        st['progress'] = build_progress(ledger['trades'], st.get('progress'))
        st['watch'] = self._watch(st)
        st['updated'] = iso(now)
        st['version'] = 1
        st['config'] = {'min_week': MIN_WEEK, 'edge_log': EDGE_LOG, 'edge_pass': EDGE_PASS, 'size_fraction': SIZE_FRACTION,
                        'depth_band': 0.02, 'snapshot_minutes': 30, 'pass_n': PASS_N, 'pass_z': PASS_Z, 'fees': 0}
        pb = st['progress']['pass_bar']
        head = (f"{STRATEGY}: {stats['new']} new games, {stats['snaps']} snapshots, {stats['entered']} entered, "
                f"{stats['exited']} exited, {stats['graded']} graded; pass bar {pb['n']}/{pb['n_needed']} {pb['status']}")
        if stats['unlisted']:
            head += f", {stats['unlisted']} triggered games not listed on Novig yet"
        st['last_run'] = {'ts': iso(now), 'notes': notes[:20], 'novig_requests': getattr(self.novig, 'used', None),
                          'novig_errors': getattr(self.novig, 'errors', None)}
        return head if not notes else head + ' | ' + '; '.join(notes[:6])

    # -- 1. new games
    def _discover(self, ctx, board, stats):
        st, now_ts = ctx['st'], ctx['now_ts']
        fresh = [c for c in triggers(board, now_ts) if c['key'] not in st['games']]
        if not fresh:
            return
        events = self.novig.events()
        if not events:
            ctx['notes'].append('Novig events unavailable')
            return
        for c in fresh:
            event = match_event(c['game'], ctx['ratings'], events)
            if not event:
                stats['unlisted'] += 1
                continue
            markets = self.novig.markets(event['eventId'])
            ladder = spread_ladder(markets)
            if not ladder:
                stats['unlisted'] += 1
                continue
            sides, how = code_sides(c['game'], ctx['ratings'], ladder, float(c['game']['open_margin']))
            if not sides:
                ctx['notes'].append(f"{c['key']}: {how}")
                continue
            code = next(k for k, v in sides.items() if v == c['side'])
            pick = choose_strike(ladder, code, c['open_hcap'])
            if not pick:
                ctx['notes'].append(f"{c['key']}: no strike for {code}")
                continue
            listed = [t for t in (uuid7_ms(mk['marketId']) for mk, _ in ladder) if t]
            g = c['game']
            gs = {
                'key': c['key'], 'game': f"{g['away']} @ {g['home']}", 'home': g['home'], 'away': g['away'],
                'home_id': g.get('home_id'), 'away_id': g.get('away_id'),
                'week': g.get('week'), 'kick': int(c['kick']), 'side': c['side'], 'team': c['team'],
                'edge': c['edge'], 'edge_bucket': c['bucket'], 'counts_toward_pass': c['edge'] >= EDGE_PASS - 1e-9,
                'model_margin': _finite(g.get('model_margin')), 'open_margin': _finite(g.get('open_margin')),
                'open_hcap': c['open_hcap'], 'state': 'watching', 'trade_id': None, 'created': iso(ctx['now']),
                'code_src': how,
                'novig': {'event_id': event['eventId'], 'market_id': pick['market_id'], 'outcome_id': pick['outcome_id'],
                          'other_id': pick['other_id'], 'code': code, 'hcap': pick['hcap'],
                          'strike_distance': round(abs(pick['hcap'] - c['open_hcap']), 2),
                          'listed_ts': int(min(listed) / 1000) if listed else None,
                          'first_seen_ts': int(now_ts), 'snaps': []},
                'kalshi': {'event': None, 'ticker': None, 'side': None, 'floor': None, 'listed_ts': None, 'push_mismatch': False,
                           'first_seen_ts': None, 'snaps': []},
            }
            st['games'][c['key']] = gs
            stats['new'] += 1
            self._snap_game(ctx, gs, stats)

    # -- 2. snapshots
    def _snapshot_due(self, ctx, stats):
        now_ts = ctx['now_ts']
        due = []
        for gs in ctx['st']['games'].values():
            if gs['state'] not in ('watching', 'entered') or gs['kick'] <= now_ts:
                continue
            try:
                snaps = valid_snaps(gs['novig'].get('snaps'), ctx['notes'], gs['key'])
            except Exception as e:
                ctx['notes'].append(f"{gs.get('key')}: snapshots unreadable: {str(e)[:100]}")
                continue
            if snaps and now_ts - max(p['ts'] for p in snaps) < SNAP_DUE_S:
                continue
            due.append(gs)
        tickers = [g['kalshi']['ticker'] for g in due if g['kalshi'].get('ticker')]
        if tickers and ctx['kalshi'] is not None:      # one batched lookup for every game already mapped
            try:
                ctx['kt'] = ctx['kalshi'].markets_by_ticker(tickers)
            except Exception as e:
                ctx['notes'].append('Kalshi quotes failed: ' + str(e)[:120])
        for gs in due:
            try:
                self._snap_game(ctx, gs, stats)
            except Exception as e:
                ctx['notes'].append(f"{gs.get('key')}: snapshot failed: {str(e)[:100]}")

    def _snap_game(self, ctx, gs, stats):
        now_ts = int(ctx['now_ts'])
        nv = gs['novig']
        book = self.novig.book(nv['market_id'])
        if book is None:
            ctx['notes'].append(f"{gs['key']}: Novig book unavailable")
        else:
            q = outcome_quote(book, nv['outcome_id'], nv['other_id'])
            nv['snaps'].append(snap_str(now_ts, q['bid'], q['ask'], q['ask_size'], q['bid_size']))
            stats['snaps'] += 1
            self._try_entry(ctx, gs, q, stats)
            self._mark_open(ctx['ledger'], gs, q)
        try:
            self._snap_kalshi(ctx, gs)
        except Exception as e:
            ctx['notes'].append(f"{gs['key']}: Kalshi snapshot failed: {str(e)[:120]}")

    def _try_entry(self, ctx, gs, q, stats):
        if gs['state'] != 'watching' or q['ask'] is None:
            return
        uncapped = size_contracts(q['ask_size'])
        if q['ask_size'] is None or q['ask_size'] < MIN_DEPTH_CONTRACTS or uncapped < 1:
            return
        nv, now = gs['novig'], ctx['now']
        price = float(q['ask'])
        n, capped_by = self._capped(ctx, uncapped, price)
        if n < 1:
            if capped_by:
                ctx['notes'].append(f"{gs['key']}: no entry, {capped_by} leaves no room")
            return
        firsts = valid_snaps(nv['snaps'], ctx['notes'], gs['key'])
        first = firsts[0] if firsts else {'ts': int(now.timestamp())}
        ticker = f"novig:{nv['market_id']}:{nv['outcome_id']}"
        row = {
            'id': f'{ticker}:{int(now.timestamp())}', 'ts': iso(now), 'status': 'open', 'source': STRATEGY,
            'strategy': STRATEGY, 'book': BOOK, 'ticker': ticker, 'event': gs['key'],
            'title': f"{gs['team']} {nv['hcap']:+g}", 'game': gs['game'], 'side': 'yes', 'strike': nv['hcap'],
            'model_prob': None, 'edge': gs['edge'], 'edge_bucket': gs['edge_bucket'],
            'counts_toward_pass': gs['counts_toward_pass'],
            'yes_bid': q['bid'], 'yes_ask': q['ask'], 'price': price, 'fee_per': 0.0, 'fee_total': 0.0,
            'contracts': n, 'stake': round(n * price, 4), 'ask_size': round(q['ask_size'], 2),
            'uncapped_contracts': uncapped, 'uncapped_stake': round(uncapped * price, 4), 'capped_by': capped_by,
            'bankroll_before': None,
            'detail': {
                'venue': 'novig', 'edge_unit': 'pts', 'jp_side': gs['side'], 'team': gs['team'], 'week': gs['week'],
                'kick': gs['kick'], 'model_margin': gs['model_margin'], 'open_margin': gs['open_margin'],
                'open_hcap': gs['open_hcap'], 'strike_distance': nv['strike_distance'],
                'size_rule': (f'{SIZE_FRACTION:.0%} of contracts within 2 cents of the best ask, rounded down, '
                              f'capped at {MAX_STAKE_FRACTION:.0%} of bankroll per trade and ${MAX_STAKE_PER_DAY:.0f} per ET day'),
                'depth_contracts': round(q['ask_size'], 2),
                'entry_delay_min': round((now.timestamp() - first['ts']) / 60.0, 1),
                'novig_listed_ts': nv['listed_ts'], 'first_seen_ts': nv['first_seen_ts'],
                'novig_market_id': nv['market_id'], 'novig_outcome_id': nv['outcome_id'],
            },
            'settled_ts': None, 'result': None, 'payout': None, 'pnl': None, 'close_mid': None, 'clv': None,
            'mark_value': round(n * (q['bid'] or 0.0), 4), 'won': None, 'exit_pnl_pc': None,
            'hold_status': 'pending', 'hold_pnl_pc': None, 'hold_pnl': None, 'hold_result': None,
        }
        ctx['ledger']['trades'].append(row)
        gs['state'] = 'entered'
        gs['trade_id'] = row['id']
        gs['entry_ts'] = int(now.timestamp())
        stats['entered'] += 1

    def _capped(self, ctx, uncapped, price):
        """(contracts, which cap bound or None): the 25% size held to 5% of bankroll per trade and $150 per ET day."""
        if price <= 0:
            return uncapped, None
        ledger = ctx['ledger']
        trade_cap = MAX_STAKE_FRACTION * float(ledger.get('bankroll_start') or 1000)
        today = et_day(ctx['now'])
        spent = sum(float(t.get('stake') or 0) for t in ledger['trades']
                    if t.get('source') == STRATEGY and t.get('status') in ('open', 'settled', 'void')
                    and et_day(t['ts']) == today)
        day_room = max(0.0, MAX_STAKE_PER_DAY - spent)
        by_trade = int(math.floor(trade_cap / price + 1e-9))
        by_day = int(math.floor(day_room / price + 1e-9))
        n = min(uncapped, by_trade, by_day)
        if n >= uncapped:
            return uncapped, None
        return n, ('day cap' if by_day < by_trade else 'trade cap')

    def _mark_open(self, ledger, gs, q):
        if gs['state'] != 'entered':
            return
        t = _trade_for(ledger, gs)
        if t is not None and t.get('status') == 'open' and q['bid'] is not None:
            t['mark_value'] = round(int(t['contracts']) * q['bid'], 4)

    def _kalshi_rows(self, ctx):
        """Open KXNCAAFSPREAD quotes, fetched at most once per run. [] on failure."""
        if ctx['kq'] is None:
            ctx['kq'] = []
            if ctx['kalshi'] is not None:
                try:
                    ctx['kq'] = ctx['kalshi'].markets(KALSHI_SERIES, status='open', limit_pages=40)
                except Exception as e:
                    ctx['notes'].append('Kalshi spread fetch failed: ' + str(e)[:120])
        return ctx['kq']

    def _snap_kalshi(self, ctx, gs):
        if ctx['kalshi'] is None:
            return
        k = gs['kalshi']
        now_ts = int(ctx['now_ts'])
        game = {'home': gs['home'], 'away': gs['away'], 'kick': gs['kick'], 'home_id': gs.get('home_id'),
                'away_id': gs.get('away_id')}
        quote = None
        if k['ticker'] is None:
            found = kalshi_find(self._kalshi_rows(ctx), game, ctx['ratings'], gs['novig']['hcap'], gs['side'])
            if not found:
                return
            if k['event'] is None:
                k['event'], k['listed_ts'], k['first_seen_ts'] = found['event'], found['listed_ts'], now_ts
            if found['quote'] is None:
                return
            k['ticker'], k['side'], k['floor'] = found['quote']['ticker'], found['side'], found['floor']
            k['push_mismatch'] = bool(found.get('push_mismatch'))
            quote = found['quote']
        else:
            quote = (ctx.get('kt') or {}).get(k['ticker'])
        if quote is None:
            return
        k['snaps'].append(snap_str(now_ts, side_bid(quote, k['side']), side_price(quote, k['side']),
                                   side_size(quote, k['side']), None))

    # -- 3. exits
    def _exits(self, ctx, stats):
        now_ts = ctx['now_ts']
        for gs in ctx['st']['games'].values():
            if gs['state'] != 'entered' or gs['kick'] > now_ts:
                continue
            t = _trade_for(ctx['ledger'], gs)
            if t is None:
                gs['state'] = 'watching'
                continue
            if t.get('status') == 'open':
                try:
                    apply_exit(t, gs)
                except Exception as e:      # leave the row open and retry next run rather than lose the others
                    ctx['notes'].append(f"{gs.get('key')}: exit failed: {str(e)[:100]}")
                    continue
                stats['exited'] += 1
            gs['state'] = 'exited'

    # -- 4. grading
    def _grade(self, ctx, by_key, ratings, stats):
        now_ts = ctx['now_ts']
        for gs in ctx['st']['games'].values():
            if gs['state'] == 'watching' and gs['kick'] <= now_ts:
                gs['state'] = 'closed'      # kicked off without a fillable ask: nothing to grade
                self._prune(gs)
                continue
            if gs['state'] != 'exited':
                continue
            t = _trade_for(ctx['ledger'], gs)
            if t is None or t.get('hold_status') != 'pending':
                continue
            res = board_result(by_key.get(gs['key']))
            if res is None and self.get is not None and now_ts > gs['kick'] + 3 * 3600:
                game = {'home': gs['home'], 'away': gs['away'], 'home_id': by_key.get(gs['key'], {}).get('home_id'),
                        'away_id': by_key.get(gs['key'], {}).get('away_id')}
                try:
                    res = espn_result(self.get, game, ratings, gs['kick'])
                except Exception as e:
                    ctx['notes'].append(f"{gs['key']}: result lookup failed: {str(e)[:100]}")
            if res is not None:
                grade_hold(t, res[0], res[1])
                t['graded_ts'] = iso(ctx['now'])
                gs['state'] = 'graded'
                stats['graded'] += 1
                self._prune(gs)
            elif now_ts > gs['kick'] + NO_RESULT_DAYS * 86400:
                t['hold_status'] = 'no_result'
                gs['state'] = 'graded'
                self._prune(gs)

    def _prune(self, gs):
        """Once a game is done keep the first snapshot, the entry snapshot and the last 6 hours before kick."""
        keep_from = gs['kick'] - KEEP_PRE_KICK_S
        entry_ts = gs.get('entry_ts')
        for v in ('novig', 'kalshi'):
            snaps = gs[v].get('snaps') or []
            kept = []
            for i, s in enumerate(snaps):
                p = try_parse_snap(s)
                if i == 0 or p is None or p['ts'] >= keep_from or p['ts'] == entry_ts:   # unreadable ones are kept, not destroyed
                    kept.append(s)
            gs[v]['snaps'] = kept

    def _watch(self, st):
        """Compact per-game rows for the dashboard (no snapshot history)."""
        out = []
        for gs in st['games'].values():
            nv, k = gs['novig'], gs['kalshi']
            ln, lk = valid_snaps(nv.get('snaps')), valid_snaps(k.get('snaps'))
            last_n = ln[-1] if ln else None
            last_k = lk[-1] if lk else None
            out.append({
                'key': gs['key'], 'game': gs['game'], 'week': gs.get('week'), 'kick': gs['kick'], 'team': gs['team'],
                'edge': gs['edge'], 'edge_bucket': gs['edge_bucket'], 'counts_toward_pass': gs['counts_toward_pass'],
                'open_hcap': gs['open_hcap'], 'strike': nv['hcap'], 'state': gs['state'], 'trade_id': gs['trade_id'],
                'novig_listed_ts': nv['listed_ts'], 'novig_first_seen_ts': nv['first_seen_ts'],
                'kalshi_listed_ts': k['listed_ts'], 'kalshi_first_seen_ts': k['first_seen_ts'],
                'kalshi_ticker': k['ticker'], 'kalshi_side': k['side'],
                'novig_snaps': len(nv.get('snaps') or []), 'kalshi_snaps': len(k.get('snaps') or []),
                'novig_last': last_n, 'kalshi_last': last_k,
            })
        out.sort(key=lambda r: (r['kick'], r['key']))
        return out


def build(cfg, root, novig=None, get=None):
    """The strategy instance for this config, or None when it is switched off."""
    sc = dict((cfg.get('sources') or {}).get(STRATEGY) or {})
    if not sc.get('enabled', True):
        return None
    return CfbJpNovig(sc, root, novig=novig, get=get)
