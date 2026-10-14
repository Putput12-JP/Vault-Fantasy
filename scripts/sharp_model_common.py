"""Stdlib-only helpers for a Sharp Money model page (the NFL model uses them).

These are the sport-neutral parts of scripts/cfb_model.py: the Sharp Money card snapshot, the market check, card attachment,
the line stamp, the "Sharp Money vs the model" tile and the exact confidence interval. scripts/cfb_model.py keeps its own copies
(it needs pandas, this does not), so a change to the tile rules has to be made in both places.
"""
import datetime, math, re

BREAKEVEN = 110 / 210


def market_check(g, side, op=None):
    """does the market, as the Sharp Money feed sees it, point the same way as our side? +1 agrees, -1 disagrees, 0 quiet. The line move and the money share count toward agree/disagree/reads; the sharp-account read is context only and does not."""
    sg = 1 if side == 'home' else -1
    out = {}
    if op is None: op = ((g.get('open') or {}).get('sp') or {}).get('line')
    now = (((g.get('pin') or {}).get('sp') or {}).get('line'))
    if now is None: now = ((g.get('consensus') or {}).get('sp') or {}).get('line')
    if op is not None and now is not None:        # line is the home spread, + = underdog; a falling number means the home side got stronger
        toward = (op - now) * sg
        out['move'] = dict(v=1 if toward >= 0.5 else -1 if toward <= -0.5 else 0, pts=round(toward, 1) + 0.0)
    sp = ((g.get('splits') or {}).get('sp') or {})
    if sp.get('home') and sp.get('away'):         # money share minus ticket share on our side: money heavier than tickets means bigger bets are on it
        t, m = sp[side].get('t'), sp[side].get('m')
        if t is not None and m is not None:
            d = m - t
            out['money'] = dict(v=1 if d >= 5 else -1 if d <= -5 else 0, pts=d)
    fl = ((g.get('flow') or {}).get('sharp') or {})
    if fl:
        net = (fl.get('sp:home', 0) - fl.get('sp:away', 0) + fl.get('ml:home', 0) - fl.get('ml:away', 0)) * sg
        out['sharp'] = dict(v=1 if net >= 5000 else -1 if net <= -5000 else 0, usd=int(net))
    vs = [out[k]['v'] for k in ('move', 'money') if k in out]      # sharp money is context only: it is reported above but never counts toward an agree total
    out['agree'] = sum(v > 0 for v in vs); out['disagree'] = sum(v < 0 for v in vs); out['reads'] = len(vs)
    return out


def feed_cards(feed, sport):
    """the signals each Sharp Money card showed on the spread, snapshotted before kickoff and kept after (feed['picks']): {game key: {'home': [kinds], 'away': [kinds], 'lbl', 'start'}}"""
    out = {}
    for p in feed.get('picks') or []:
        if p.get('sport') != sport or p.get('m') != 'sp': continue
        o = out.setdefault(p['game'], {'home': [], 'away': [], 'lbl': p['gameLbl'], 'start': p['start']})
        o[p['side']] = sorted(set(o[p['side']]) | set(p['kinds']))
    return out


def attach_cards(board, cards):
    """give every board game the Sharp Money spread cards it showed before kickoff. Exact on the feed's own key (the feed and the board both use it);
    otherwise by kickoff window and the two team abbreviations in the card's label"""
    ab = lambda x: re.sub('[^A-Z]', '', str(x).upper())
    used = set()
    for e in board:
        if e['key'] in cards: e['cards'] = {'home': cards[e['key']]['home'], 'away': cards[e['key']]['away']}; used.add(e['key'])
    for e in board:
        if e.get('cards') is not None: continue
        hit = [(k, v) for k, v in cards.items() if k not in used and abs(v['start'] - e['kick']) <= 1800 and '@' in v['lbl']
               and ab(v['lbl'].split('@')[0]) == ab(e['away']) and ab(v['lbl'].split('@')[1]) == ab(e['home'])]
        if len(hit) == 1: e['cards'] = {'home': hit[0][1]['home'], 'away': hit[0][1]['away']}; used.add(hit[0][0])


def clopper_pearson(w, n, alpha=0.05):
    """Exact two-sided (1 - alpha) interval for w wins in n decided games (pushes already excluded). None when n is 0. Bisection on the binomial CDF."""
    if n <= 0: return None
    def cdf(k, p):      # P(X <= k), summed in log space so a season-sized n does not overflow
        if p <= 0: return 1.0
        if p >= 1: return 1.0 if k >= n else 0.0
        return min(1.0, sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log1p(-p)) for i in range(k + 1)))
    def root(f, rising):
        a_, b_ = 0.0, 1.0
        for _ in range(60):
            m = (a_ + b_) / 2
            if (f(m) > 0) == rising: b_ = m
            else: a_ = m
        return (a_ + b_) / 2
    lo = 0.0 if w == 0 else root(lambda p: (1 - cdf(w - 1, p)) - alpha / 2, True)
    hi = 1.0 if w == n else root(lambda p: cdf(w, p) - alpha / 2, False)
    return [round(lo, 3), round(hi, 3)]


def iso_utc(ts):
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def epoch(iso):
    """ISO time -> epoch seconds. A timestamp with no zone is read as UTC (every stamp written here is UTC), never as the box's local time."""
    try: t = datetime.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
    except (TypeError, ValueError): return None
    if t.tzinfo is None: t = t.replace(tzinfo=datetime.timezone.utc)
    return int(t.timestamp())


def capture_board(board, slate, now):
    """Stamp each board row that is in THIS run's slate with its current market line (its own side, same sign as entry) and the run time, while the game has
    not kicked off. After kickoff the stamp is never touched, so line_captured_at < kick always holds for a real pre-kick capture."""
    in_slate = {s_['key'] for s_ in slate}
    n = 0
    for row in board:
        kick = row.get('kick')
        if row.get('key') not in in_slate or not isinstance(kick, (int, float)) or now >= kick or row.get('market_margin') is None or row.get('side') not in ('home', 'away'): continue
        row['line_captured'] = round(-row['market_margin'] if row['side'] == 'home' else row['market_margin'], 1)
        row['line_captured_at'] = iso_utc(now); n += 1
    return n


def tile_fields(board):
    """Grade the Sharp Money tile at ONE takeable price: the last line before kickoff. Adds tile_line, tile_result ('W'/'L'/'P') and tile_line_src to every
    settled row and touches nothing else. A row with line_captured stamped before kick is graded at that line; otherwise at its entry (the line first seen)."""
    for e in board:
        for k in ('tile_line', 'tile_result', 'tile_line_src'): e.pop(k, None)
        if e.get('result') not in ('W', 'L', 'P') or e.get('margin') is None: continue
        cap_at = epoch(e.get('line_captured_at'))
        if e.get('line_captured') is not None and cap_at is not None and cap_at < e['kick']: line, src = e['line_captured'], 'captured_prekick'
        else: line, src = e['entry'], 'entry'
        e['tile_line'] = line; e['tile_line_src'] = src
        e['tile_result'] = 'W' if e['margin'] + line > 0 else 'L' if e['margin'] + line < 0 else 'P'


def tile_cards_summary(board, pick_edge, key_prefix):
    """The Sharp Money vs the model tile. Each table row keeps all/feed as [w, l] and adds n, ci (95% Clopper-Pearson) and before (graded at entry);
    the feed column is the rows whose key starts with key_prefix, and its n, ci and before are feed_n, feed_ci, feed_before. Same rows as the CFB tile."""
    tile_fields(board)
    def _cs(sel):
        w = sum(e['tile_result'] == 'W' for e in sel); return [w, sum(e['tile_result'] in ('W', 'L') for e in sel) - w]
    def _old(sel):
        w = sum(e['result'] == 'W' for e in sel); return [w, sum(e['result'] in ('W', 'L') for e in sel) - w]
    gg = [e for e in board if e.get('tile_result') in ('W', 'L')]
    old_gg = [e for e in board if e.get('result') in ('W', 'L')]
    withc = [e for e in gg if e.get('cards') is not None]
    old_withc = [e for e in old_gg if e.get('cards') is not None]
    opp = lambda e: 'away' if e['side'] == 'home' else 'home'
    mine = lambda e: e['cards'][e['side']]; other = lambda e: e['cards'][opp(e)]
    pe = f'{pick_edge:g}'
    rows_def = [
        ('Sharp Money is on the same side as the model', 'A line-move, sharp-account, money or books-behind card showed on the model\'s team and none on the other team.', lambda e: mine(e) and not other(e)),
        ('Sharp Money is on the other side', 'Cards showed only on the team the model is against.', lambda e: other(e) and not mine(e)),
        ('Sharp Money is on both sides', 'Cards showed on both teams, so the signals disagree.', lambda e: mine(e) and other(e)),
        ('The line moved toward the model\'s team', 'The Pinnacle number shortened for the model\'s side before kickoff.', lambda e: 'line' in mine(e)),
        ('The line moved away from the model\'s team', 'The Pinnacle number moved toward the other team.', lambda e: 'line' in other(e)),
        ('Sharp accounts bet the model\'s team', 'Accounts with a proven record put real money on the model\'s side.', lambda e: 'sharp' in mine(e)),
        ('Sharp accounts bet the other team', 'Those accounts went the other way.', lambda e: 'sharp' in other(e)),
        ('Bigger money than bets on the model\'s team', 'A larger share of the dollars than of the tickets, which points to larger bettors.', lambda e: 'money' in mine(e)),
        ('Two or more signals back the model', 'More than one kind of card on the model\'s team.', lambda e: len(mine(e)) >= 2),
        (f'Model picks ({pe}+ points) that Sharp Money backs', f'The model is {pe}+ points from the market and a card is on its side.', lambda e: e['is_pick'] and mine(e)),
        (f'Model picks ({pe}+ points) with no Sharp Money behind them', f'The model is {pe}+ points from the market and no card is on its side.', lambda e: e['is_pick'] and not mine(e)),
    ]
    feed_only = lambda e: e['key'].startswith(key_prefix)
    def _stats(label, note, sel, osel):
        fs, ofs = [e for e in sel if feed_only(e)], [e for e in osel if feed_only(e)]
        al, fe = _cs(sel), _cs(fs)
        return dict(label=label, note=note, all=al, n=sum(al), ci=clopper_pearson(al[0], sum(al)), before=_old(osel),
                    feed=fe, feed_n=sum(fe), feed_ci=clopper_pearson(fe[0], sum(fe)), feed_before=_old(ofs), keys=[e['key'] for e in sel])
    cards_table = [_stats(l, n_, [e for e in withc if f(e)], [e for e in old_withc if f(e)]) for l, n_, f in rows_def]
    base = _stats('Every game the model projected', 'The baseline: the model\'s side in every finished game, picks and leans, whatever Sharp Money did.', gg, old_gg)
    return dict(graded=len(gg), with_cards=len(withc), table=[base] + cards_table)


def final_summary(board, pick_edge, logkeys):
    """The final lock (the state an hour before kickoff, Sharp Money cards included) against first sight, graded."""
    fg = [e for e in board if e.get('final') and e['final'].get('result') in ('W', 'L')]
    def _fs(sel, get=lambda e: e['final']['result']):
        w = sum(get(e) == 'W' for e in sel); return [w, sum(get(e) in ('W', 'L') for e in sel) - w]
    def _link(e):
        c = e['final'].get('cards')
        if c is None: return 'nocard'
        m, o = c[e['final']['side']], c['away' if e['final']['side'] == 'home' else 'home']
        return 'with' if m and not o else 'against' if o and not m else 'split' if m and o else 'none'
    fp = [e for e in fg if e['final']['is_pick']]
    pe = f'{pick_edge:g}'
    fl = [e for e in fg if e['key'] in logkeys and not e['final']['is_pick']]
    return dict(locked=sum(1 for e in board if e.get('final')), graded=len(fg), rows=[
        dict(label='Still a pick when locked', note=f'A first-sight pick that was still {pe}+ points from the market an hour before kickoff, graded at the locked line.',
             all=_fs([e for e in fp if e['key'] in logkeys]), keys=[e['key'] for e in fp if e['key'] in logkeys]),
        dict(label=f'Dropped under {pe} points by the lock', note='Logged as a pick, but the gap closed before kickoff. Graded at the first-sight line, as in the official record.',
             all=_fs([logkeys[e['key']] for e in fl], lambda e: e.get('result')), keys=[e['key'] for e in fl]),
        dict(label='Became a pick in the last hour', note=f'Under {pe} points when first seen, {pe}+ at the lock.',
             all=_fs([e for e in fp if e['key'] not in logkeys]), keys=[e['key'] for e in fp if e['key'] not in logkeys]),
        dict(label='Locked picks with Sharp Money on their side', note=f'At the lock the model is {pe}+ points off and a card is on its team and none on the other.',
             all=_fs([e for e in fp if _link(e) == 'with']), keys=[e['key'] for e in fp if _link(e) == 'with']),
        dict(label='Locked picks with Sharp Money against them', note='Cards only on the other team.',
             all=_fs([e for e in fp if _link(e) == 'against']), keys=[e['key'] for e in fp if _link(e) == 'against']),
        dict(label='Locked picks, Sharp Money split or quiet', note='Cards on both teams, or no card at all.',
             all=_fs([e for e in fp if _link(e) in ('split', 'none', 'nocard')]), keys=[e['key'] for e in fp if _link(e) in ('split', 'none', 'nocard')]),
    ])
