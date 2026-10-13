"""NBA game-model total ladder vs the live Kalshi ask.

The probability is the one in nba/scripts/backtest_game_vs_kalshi.py:

    P(over strike) = 1 - Phi((strike - mu) / sigma)

mu is the game model's projected total (the same formula as the Slate page's
Vault line). sigma is model_state.game.sd_total, which that file already
computes from the tune-season total MAE the way the backtest does
(MAE * sqrt(pi/2)). The edge gate is model probability minus the ask we would
pay, before fees. Fees are charged in the fill.

The fitted model has CT = 0, so absences do not move the total. If CT is ever
non-zero this source refuses to guess a healthy total.

The Slate page leaves the total out for the first four weeks of the regular
season (it ran low in both test seasons). This source does the same, and it
does not trade preseason games.
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..quotes import market_tradable, side_price, side_size

ET = ZoneInfo('America/New_York')
EARLY_DAYS = 28
SERIES = 'KXNBATOTAL'
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='

# Kalshi and ESPN abbreviations -> the game model's team key.
TO_MODEL = {
    'SAS': 'SA', 'NYK': 'NY', 'GSW': 'GS', 'NOP': 'NO', 'UTA': 'UTAH',
    'WAS': 'WSH', 'PHO': 'PHX', 'BRK': 'BKN',
}
MONTHS = {m: i + 1 for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split())}


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def to_model(code):
    u = str(code or '').upper()
    return TO_MODEL.get(u, u)


def ticker_date(event):
    parts = str(event or '').split('-')
    if len(parts) < 2 or len(parts[1]) < 7:
        return None, ''
    code = parts[1]
    mon = code[2:5]
    if mon not in MONTHS:
        return None, ''
    try:
        day = datetime(2000 + int(code[:2]), MONTHS[mon], int(code[5:7])).date()
    except ValueError:
        return None, ''
    return day, code[7:]


def p_over(mu, sigma, strike):
    if not sigma:
        return None
    return 1 - phi((float(strike) - float(mu)) / float(sigma))


def is_b2b(team, tip, state, games):
    last = (state.get('team_last') or {}).get(team)
    if last and tip > float(last) and tip - float(last) < 30 * 3600:
        return True
    for g in games:
        if team in (g['home'], g['away']) and g['tip'] < tip and tip - g['tip'] < 30 * 3600:
            return True
    return False


def project_total(state, home, away, tip, games):
    """Projected total. None when the model would need an injury report we do not have."""
    P = state.get('P') or {}
    if abs(float(P.get('CT') or 0)) > 1e-9:
        return None
    base = float(state['base'])
    hfa = float(state.get('hfa') or 0)
    O, D = state.get('O') or {}, state.get('D') or {}
    b2b = float(P.get('B2B') or 0)
    bh = 1.0 if is_b2b(home, tip, state, games) else 0.0
    ba = 1.0 if is_b2b(away, tip, state, games) else 0.0
    ph = base + float(O.get(home) or 0) - float(D.get(away) or 0) + hfa / 2 - b2b / 2 * bh
    pa = base + float(O.get(away) or 0) - float(D.get(home) or 0) - hfa / 2 - b2b / 2 * ba
    return ph + pa, bh, ba


def window_open(state, tip):
    ss = state.get('season_start')
    if not ss:
        return False
    return float(tip) >= float(ss) + EARLY_DAYS * 86400


def sigma_of(state, game_model):
    if state.get('sd_total'):
        return float(state['sd_total']), 'model_state.game.sd_total'
    tune = (game_model or {}).get('tune_mae') or []
    if len(tune) >= 2 and tune[1]:
        return float(tune[1]) * math.sqrt(math.pi / 2), 'game_model.tune_mae[1] * sqrt(pi/2)'
    return None, None


def match_game(event, games, known):
    day, blob = ticker_date(event)
    if not day or not blob:
        return None
    splits = []
    for cut in (2, 3, 4):
        if cut >= len(blob) or len(blob) - cut < 2:
            continue
        a, h = to_model(blob[:cut]), to_model(blob[cut:])
        if a in known and h in known:
            splits.append(frozenset((a, h)))
    uniq = {frozenset(s) for s in splits}
    if len(uniq) != 1:
        return None
    teams = next(iter(uniq))
    cands = [g for g in games if frozenset((g['home'], g['away'])) == teams and abs((g['et_date'] - day).days) <= 1]
    exact = [g for g in cands if g['et_date'] == day]
    use = exact or cands
    return use[0] if len(use) == 1 else None


def parse_scoreboard(payload, now):
    """ESPN scoreboard JSON -> game dicts. Season type and status come from the feed, not a guess."""
    games = []
    for ev in (payload or {}).get('events') or []:
        comps = ev.get('competitions') or [{}]
        comp = comps[0]
        season = (ev.get('season') or {}).get('type')
        if isinstance(season, dict):
            season = season.get('type')
        try:
            season = int(season)
        except (TypeError, ValueError):
            continue
        status = (((comp.get('status') or {}).get('type') or {}).get('name')) or ''
        home = away = None
        for t in comp.get('competitors') or []:
            abbr = to_model(((t.get('team') or {}).get('abbreviation')))
            if t.get('homeAway') == 'home':
                home = abbr
            elif t.get('homeAway') == 'away':
                away = abbr
        if not home or not away or not ev.get('date'):
            continue
        tip = datetime.fromisoformat(ev['date'].replace('Z', '+00:00'))
        if tip.tzinfo is None:
            tip = tip.replace(tzinfo=timezone.utc)
        games.append({
            'id': str(ev.get('id') or ''),
            'home': home,
            'away': away,
            'tip': tip.timestamp(),
            'et_date': tip.astimezone(ET).date(),
            'season_type': season,
            'status': 'scheduled' if status == 'STATUS_SCHEDULED' else status.lower(),
            'name': ev.get('shortName') or ev.get('name') or f'{away}@{home}',
        })
    return games


def proposals_from(state, games, markets, cfg, now, sigma, sigma_from):
    """Pure signal. Returns (proposals, note)."""
    notes = []
    if not state or sigma is None:
        return [], 'nba total: model state has no sigma'
    ct = float((state.get('P') or {}).get('CT') or 0)
    if abs(ct) > 1e-9:
        return [], 'nba total: CT is non-zero and this source does not read injuries, so it is not trading'
    known = set((state.get('R') or {})) | set((state.get('O') or {}))
    eligible = []
    skipped = {}
    for g in games:
        if g['season_type'] < 2:
            skipped['preseason'] = skipped.get('preseason', 0) + 1
            continue
        if g['status'] != 'scheduled':
            skipped['started'] = skipped.get('started', 0) + 1
            continue
        if g['tip'] <= now.timestamp():
            skipped['tipped'] = skipped.get('tipped', 0) + 1
            continue
        if not window_open(state, g['tip']):
            skipped['first four weeks'] = skipped.get('first four weeks', 0) + 1
            continue
        if g['home'] not in known or g['away'] not in known:
            skipped['no rating'] = skipped.get('no rating', 0) + 1
            continue
        eligible.append(g)
    out = []
    seen_events = set()
    unmatched = 0
    capped = []
    for q in markets:
        if q['event'] in seen_events and q['strike'] is None:
            continue
        if not market_tradable(q, cfg) or q.get('strike') is None:
            continue
        g = match_game(q['event'], eligible, known)
        if not g:
            unmatched += 1
            continue
        projected = project_total(state, g['home'], g['away'], g['tip'], games)
        if projected is None:
            continue
        mu, bh, ba = projected
        p_yes = p_over(mu, sigma, q['strike'])
        if p_yes is None:
            continue
        best = _best_side(q, p_yes, cfg, capped)
        if not best:
            continue
        side, prob, ask, edge = best
        out.append({
            'source': 'nba_total',
            'ticker': q['ticker'],
            'event': q['event'],
            'title': q['title'] or f"{g['away']}@{g['home']} over {q['strike']}",
            'game': f"{g['away']} @ {g['home']}",
            'side': side,
            'strike': q['strike'],
            'model_prob': round(prob, 4),
            'edge': round(edge, 4),
            'yes_bid': q['yes_bid'],
            'yes_ask': q['yes_ask'],
            'no_bid': q['no_bid'],
            'no_ask': q['no_ask'],
            'price': ask,
            'ask_size': side_size(q, side),
            'detail': {
                'mu': round(mu, 2),
                'sigma': round(sigma, 2),
                'sigma_from': sigma_from,
                'formula': 'P(over) = 1 - Phi((strike - mu) / sigma)',
                'b2b_home': bh,
                'b2b_away': ba,
                'home': g['home'],
                'away': g['away'],
                'tip': int(g['tip']),
            },
        })
    bits = [f'{len(eligible)} eligible games', f'{len(out)} signals', f'{unmatched} quotes unmatched']
    if skipped:
        bits.append('skipped ' + ', '.join(f'{n} {k}' for k, n in sorted(skipped.items())))
    if capped:
        bits.append(f'{len(capped)} skipped over the max edge cap')
    return out, 'nba total: ' + '; '.join(bits)


def _best_side(q, p_yes, cfg, capped=None):
    min_edge = float(cfg['min_edge'])
    max_edge = cfg.get('max_edge', 0.15)
    max_edge = float(max_edge) if max_edge else None
    lo, hi = float(cfg['min_price']), float(cfg['max_price'])
    cands = []
    for side, prob in (('yes', p_yes), ('no', 1 - p_yes)):
        ask = side_price(q, side)
        if not (lo < ask < hi):
            continue
        if side_size(q, side) < 1:
            continue
        edge = prob - ask
        if max_edge is not None and edge > max_edge:
            if capped is not None:
                capped.append(q.get('ticker'))
            continue
        if edge >= min_edge:
            cands.append((side, prob, ask, edge))
    if not cands:
        return None
    return max(cands, key=lambda c: c[3])


class NbaTotalSource:
    name = 'nba_total'

    def __init__(self, cfg, root, get=None):
        self.cfg = cfg
        self.root = root
        self.get = get

    def collect(self, kalshi, now):
        state, game_model, err = _load_model(self.root)
        if err:
            return [], err
        sigma, sigma_from = sigma_of(state, game_model)
        games, gerr = _load_slate(self.get, now)
        if gerr:
            return [], gerr
        try:
            markets = kalshi.markets(SERIES, status='open')
        except Exception as e:
            return [], 'nba total: Kalshi fetch failed: ' + str(e)[:200]
        return proposals_from(state, games, markets, self.cfg, now, sigma, sigma_from)


def _load_model(root):
    path = os.path.join(root, 'nba', 'data', 'model_state.json')
    if not os.path.exists(path):
        return None, None, 'nba total: nba/data/model_state.json is missing'
    try:
        with open(path) as f:
            state = (json.load(f) or {}).get('game') or {}
    except (OSError, json.JSONDecodeError) as e:
        return None, None, 'nba total: could not read model state: ' + str(e)[:160]
    gm = {}
    gp = os.path.join(root, 'nba', 'data', 'game_model.json')
    if os.path.exists(gp):
        try:
            with open(gp) as f:
                gm = json.load(f)
        except (OSError, json.JSONDecodeError):
            gm = {}
    return state, gm, None


def _load_slate(get, now):
    if get is None:
        from ..http_json import get_json as get
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    start = now.astimezone(ET).date()
    games = []
    errors = []
    for i in range(3):
        ymd = (start + timedelta(days=i)).strftime('%Y%m%d')
        try:
            payload = get(ESPN + ymd)
        except Exception as e:
            errors.append(str(e)[:120])
            continue
        games.extend(parse_scoreboard(payload, now))
    if not games and errors:
        return [], 'nba total: ESPN scoreboard failed: ' + errors[0]
    # one row per game id
    by_id = {}
    for g in games:
        by_id[g['id'] or (g['away'], g['home'], g['et_date'].isoformat())] = g
    return list(by_id.values()), None
