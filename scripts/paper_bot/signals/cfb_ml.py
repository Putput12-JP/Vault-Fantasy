"""CFB margin model, translated to a Kalshi game-winner probability.

The CFB model projects a home margin, not a total (scripts/cfb_model.py). This
source turns that margin into a win probability with the same Normal conversion
the NBA Kalshi backtest uses:

    sigma = (games-weighted test-season model_miss) * sqrt(pi/2)
    P(home wins) = Phi(priced_margin / sigma)

priced_margin is the game's blend_margin, falling back to the v1 model_margin when
the blend is missing.

model_miss and which seasons are the test seasons are read from
data/cfb_model.json's backtest block. Nothing here is a Kalshi result. The
published efficiency study found this model does not beat the closing spread;
the paper bot is here to see whether the moneyline translation pays, not to
claim it already has.

Games before the model's own min week (the first month is prior-dominated) are
skipped. A Kalshi event is used only when both team names match one projected
game. Ambiguous matches are skipped.
"""
import json
import math
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..config import max_edge_of, max_gap_of
from ..quotes import market_tradable, side_price, side_size
from .nba_total import MONTHS, phi, ticker_date

ET = ZoneInfo('America/New_York')
SERIES = 'KXNCAAFGAME'


def sigma_from_backtest(bt):
    """(sigma, provenance) from the published test-season margin miss, or (None, reason)."""
    if not isinstance(bt, dict):
        return None, 'cfb moneyline: no backtest block on the model file'
    years = [int(y) for y in re.findall(r'\d{4}', str(bt.get('test') or ''))]
    if len(years) >= 2:
        ys = range(years[0], years[-1] + 1)
    elif len(years) == 1:
        ys = years
    else:
        return None, 'cfb moneyline: backtest.test does not name a season'
    seasons = bt.get('seasons') or {}
    num = den = 0.0
    used = []
    for y in ys:
        s = seasons.get(str(y)) or {}
        miss, games = s.get('model_miss'), s.get('games')
        if miss is None or not games:
            continue
        num += float(miss) * int(games)
        den += int(games)
        used.append({'season': str(y), 'model_miss': miss, 'games': int(games)})
    if not den:
        return None, 'cfb moneyline: test seasons have no model_miss'
    mae = num / den
    sigma = mae * math.sqrt(math.pi / 2)
    return sigma, {
        'mae': round(mae, 4),
        'sigma': round(sigma, 4),
        'formula': 'games-weighted model_miss * sqrt(pi/2)',
        'test': bt.get('test'),
        'seasons': used,
    }


def _finite(x):
    """x as a float, or None when it is missing or not a finite number."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _tokens(name):
    s = str(name or '').lower().replace('&', ' and ').replace('.', ' ')
    s = s.replace("'", '')
    words = re.sub(r'[^a-z0-9 ]', ' ', s).split()
    out = []
    for w in words:
        if w in ('st', 'state'):
            out.append('state')
        elif w in ('univ', 'university', 'college', 'the', 'of'):
            continue
        else:
            out.append(w)
    return out


def team_match(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb or len(ta) != len(tb):
        return False
    for x, y in zip(ta, tb):
        if x == y:
            continue
        short, long = (x, y) if len(x) <= len(y) else (y, x)
        if len(short) < 4 or not long.startswith(short):
            return False
    return True


def _rating_index(ratings):
    by_id = {}
    for r in ratings or []:
        if r.get('id') is None:
            continue
        by_id[int(r['id'])] = r
    return by_id


def _side_names(game, side, ratings):
    names = [game.get(side) or '']
    rid = game.get('home_id' if side == 'home' else 'away_id')
    rating = ratings.get(int(rid)) if rid is not None and int(rid) in ratings else None
    if rating:
        names.append(rating.get('team') or '')
    return [n for n in names if n], rating


def _abbr_of(game, side, ratings):
    rid = game.get('home_id' if side == 'home' else 'away_id')
    rating = ratings.get(int(rid)) if rid is not None and int(rid) in ratings else None
    return (rating or {}).get('abbr') or ''


def _label_matches(label, names, abbr=''):
    lab = str(label or '').strip()
    for n in names:
        if team_match(lab, n):
            return True
    # An abbreviation only matches itself. As a prefix it would let 'MISS' (Ole Miss) claim 'Missouri'.
    return bool(abbr) and 2 <= len(lab) <= 5 and lab.upper() == str(abbr).upper()


def match_board(event, markets, board, ratings, now):
    """Return the board game and which Kalshi market is home, or None."""
    day, _blob = ticker_date(event)
    if not day:
        return None
    labels = [(m, m.get('sub') or '') for m in markets]
    if len(labels) < 2:
        return None
    cands = []
    for g in board:
        kick = g.get('kick')
        if not kick:
            continue
        kd = datetime.fromtimestamp(float(kick), ET).date()
        if abs((kd - day).days) > 1:
            continue
        home_names, _ = _side_names(g, 'home', ratings)
        away_names, _ = _side_names(g, 'away', ratings)
        home_abbr, away_abbr = _abbr_of(g, 'home', ratings), _abbr_of(g, 'away', ratings)
        home_m = away_m = None
        for m, lab in labels:
            is_home = _label_matches(lab, home_names, home_abbr)
            is_away = _label_matches(lab, away_names, away_abbr)
            if is_home and not is_away:
                home_m = m
            elif is_away and not is_home:
                away_m = m
        if home_m and away_m and home_m is not away_m:
            exact = kd == day
            cands.append((0 if exact else 1, g, home_m, away_m))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    top = [c for c in cands if c[0] == cands[0][0]]
    if len(top) != 1:
        return None
    return top[0][1], top[0][2], top[0][3]


def proposals_from(model, markets, cfg, now):
    if not model:
        return [], 'cfb moneyline: data/cfb_model.json is missing'
    sigma, prov = sigma_from_backtest(model.get('backtest'))
    if sigma is None:
        return [], prov
    min_week = int(cfg.get('min_week') or (model.get('backtest') or {}).get('min_week') or 4)
    ratings = _rating_index(model.get('ratings'))
    board = [g for g in (model.get('board') or []) if (g.get('week') or 0) >= min_week and g.get('model_margin') is not None]
    upcoming = [g for g in board if float(g.get('kick') or 0) > now.timestamp()]
    by_event = {}
    for q in markets:
        by_event.setdefault(q['event'], []).append(q)
    out = []
    unmatched = 0
    capped = gapped = bad_margin = bad_market = 0
    max_gap = max_gap_of(cfg)
    max_edge = max_edge_of(cfg)
    for event, rows in by_event.items():
        hit = match_board(event, rows, upcoming, ratings, now)
        if not hit:
            unmatched += 1
            continue
        game, home_m, away_m = hit
        blend = game.get('blend_margin')
        priced = _finite(blend)
        priced_from = 'blend_margin'
        if priced is None:
            priced = _finite(game.get('model_margin'))
            priced_from = 'model_margin'
        if priced is None:
            bad_margin += 1
            continue
        market = _finite(game.get('market_margin'))
        if max_gap is not None and game.get('market_margin') is not None:
            if market is None:
                bad_market += 1
                continue
            if abs(priced - market) > max_gap:
                gapped += 1
                continue
        p_home = phi(priced / sigma)
        if not math.isfinite(p_home):
            bad_margin += 1
            continue
        best = None
        for side_name, q, prob in (('home', home_m, p_home), ('away', away_m, 1 - p_home)):
            if not market_tradable(q, cfg):
                continue
            ask = side_price(q, 'yes')  # each team is its own YES contract
            if not (float(cfg['min_price']) < ask < float(cfg['max_price'])):
                continue
            if side_size(q, 'yes') < 1:
                continue
            edge = prob - ask
            if not math.isfinite(edge):
                continue
            if max_edge is not None and edge > max_edge:
                capped += 1
                continue
            if edge < float(cfg['min_edge']):
                continue
            cand = (edge, side_name, q, prob, ask)
            if best is None or cand[0] > best[0]:
                best = cand
        if not best:
            continue
        # Both sides clearing the gate means the quotes cross the model in a way
        # we will not paper both of. Take the larger edge only.
        edge, side_name, q, prob, ask = best
        out.append({
            'source': 'cfb_ml',
            'ticker': q['ticker'],
            'event': q['event'],
            'title': q['title'] or q['sub'],
            'game': f"{game.get('away')} @ {game.get('home')}",
            'side': 'yes',
            'strike': None,
            'model_prob': round(prob, 4),
            'edge': round(edge, 4),
            'yes_bid': q['yes_bid'],
            'yes_ask': q['yes_ask'],
            'price': ask,
            'ask_size': side_size(q, 'yes'),
            'detail': {
                'model_margin': _finite(game.get('model_margin')),
                'priced_margin': priced,
                'market_margin': market,
                'priced_from': priced_from,
                'sigma': prov.get('sigma'),
                'sigma_from': prov,
                'formula': 'P(home) = Phi(priced_margin / sigma)',
                'week': game.get('week'),
                'side_team': game.get('home') if side_name == 'home' else game.get('away'),
                'home': game.get('home'),
                'away': game.get('away'),
                'kick': game.get('kick'),
                'note': 'Margin model translated to a moneyline. No Kalshi backtest is claimed for this.',
            },
        })
    note = f'cfb moneyline: {len(upcoming)} projected games, {len(out)} signals, {unmatched} events unmatched, min week {min_week}'
    if capped:
        note += f', {capped} skipped over the max edge cap'
    if gapped:
        note += f', {gapped} skipped over the model/market gap cap'
    if bad_margin:
        note += f', {bad_margin} skipped, bad margin'
    if bad_market:
        note += f', {bad_market} skipped, bad market margin'
    return out, note


class CfbMoneylineSource:
    name = 'cfb_ml'

    def __init__(self, cfg, root, get=None):
        self.cfg = cfg
        self.root = root
        self.get = get

    def collect(self, kalshi, now):
        path = os.path.join(self.root, 'data', 'cfb_model.json')
        if not os.path.exists(path):
            return [], 'cfb moneyline: data/cfb_model.json is missing'
        try:
            with open(path) as f:
                model = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            return [], 'cfb moneyline: could not read the model: ' + str(e)[:160]
        try:
            markets = kalshi.markets(SERIES, status='open')
        except Exception as e:
            return [], 'cfb moneyline: Kalshi fetch failed: ' + str(e)[:200]
        return proposals_from(model, markets, self.cfg, now)
