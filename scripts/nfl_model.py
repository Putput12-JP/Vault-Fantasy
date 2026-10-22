#!/usr/bin/env python3
"""Vault's NFL model page for Sharp Money: the same view as the CFB model, on the NFL game model.

The projections are NOT new. They are the Vault line from data/game_model.json (team power ratings, home field, backup-QB points), computed the
way artifacts/game-breakdowns/build_data.py does. That model matches the market and does not beat the close (see its backtest), so this page
reports it as an experiment: every game it projects, every pick it would make, and how each did against the real score and the closing spread.

  python3 scripts/nfl_model.py backtest           # once a year: walk-forward 2014-present, picks vs the closing spread -> data/nfl_model_backtest.json
  python3 scripts/nfl_model.py update --sharp data.json
                                                  # in season: project the games the Sharp Money feed lists, log new picks once (before kickoff),
                                                  #   lock them an hour out, grade finished ones -> data/nfl_model.json

Stdlib only. Handicap convention: a team's spread, + = underdog. A pick is a game where the model and the market are PICK_EDGE or more points apart,
the 'big' band of the spread rule in data/game_rules.json (the same bands the Best Bets game plays use).
"""
import argparse, csv, datetime, io, json, math, os, ssl, statistics, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sharp_model_common as sm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'nfl_model.json')
BACKTEST = os.path.join(DATA, 'nfl_model_backtest.json')
GAMES_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
MODEL_VERSION = 'v1'
LOCK_SECS = 3600          # the final lock: the state an hour before kickoff (or the last run before it, when none fell in that hour)
LEAN_EDGE = 1.5           # default, replaced by data/game_rules.json bands.spread[0]
PICK_EDGE = 3.0           # default, replaced by data/game_rules.json bands.spread[1]
BREAKEVEN = sm.BREAKEVEN
ALIAS = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA', 'WSH': 'WAS', 'JAC': 'JAX'}
NAMES = {'ARI': 'Arizona Cardinals', 'ATL': 'Atlanta Falcons', 'BAL': 'Baltimore Ravens', 'BUF': 'Buffalo Bills', 'CAR': 'Carolina Panthers', 'CHI': 'Chicago Bears',
         'CIN': 'Cincinnati Bengals', 'CLE': 'Cleveland Browns', 'DAL': 'Dallas Cowboys', 'DEN': 'Denver Broncos', 'DET': 'Detroit Lions', 'GB': 'Green Bay Packers',
         'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts', 'JAX': 'Jacksonville Jaguars', 'KC': 'Kansas City Chiefs', 'LA': 'Los Angeles Rams', 'LAC': 'Los Angeles Chargers',
         'LV': 'Las Vegas Raiders', 'MIA': 'Miami Dolphins', 'MIN': 'Minnesota Vikings', 'NE': 'New England Patriots', 'NO': 'New Orleans Saints', 'NYG': 'New York Giants',
         'NYJ': 'New York Jets', 'PHI': 'Philadelphia Eagles', 'PIT': 'Pittsburgh Steelers', 'SEA': 'Seattle Seahawks', 'SF': 'San Francisco 49ers', 'TB': 'Tampa Bay Buccaneers',
         'TEN': 'Tennessee Titans', 'WAS': 'Washington Commanders'}
mt = lambda t: ALIAS.get(str(t or '').upper(), str(t or '').upper())


def load(name, default=None):
    try: return json.load(open(os.path.join(DATA, name)))
    except Exception: return default


def fetch_text(url):
    try:
        import requests
        return requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=90).text
    except Exception:
        import urllib.request
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=90, context=ctx).read().decode('utf-8', 'replace')


def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def games_2026(season):
    """nflverse games.csv rows for the season: schedule, week, kickoff, final score and the closing spread (spread_line = expected HOME margin)."""
    out = []
    for r in csv.DictReader(io.StringIO(fetch_text(GAMES_URL))):
        if r.get('season') != str(season): continue
        try: kick = int(datetime.datetime.strptime(r['gameday'] + ' ' + (r.get('gametime') or '13:00'), '%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo('America/New_York')).timestamp())
        except Exception: continue
        hs, as_ = fnum(r.get('home_score')), fnum(r.get('away_score'))
        out.append(dict(home=mt(r['home_team']), away=mt(r['away_team']), week=int(r['week']), kick=kick, neutral=(r.get('location') or '').strip().lower() == 'neutral',
                        done=hs is not None and as_ is not None, hs=None if hs is None else int(hs), as_=None if as_ is None else int(as_), spread=fnum(r.get('spread_line'))))
    return out


def find_game(gs, home, away, kick):
    """the schedule row for this pairing nearest the kickoff (a division rematch is the same pairing twice a season); within 3 days or no match"""
    c = [g for g in gs if g['home'] == home and g['away'] == away and abs(g['kick'] - kick) <= 3 * 86400]
    return min(c, key=lambda g: abs(g['kick'] - kick)) if c else None


def project(gm, qbs, home, away, neutral):
    """the Vault line as a home margin, exactly as artifacts/game-breakdowns/build_data.py model() computes it; also whether either side starts a backup"""
    T = gm['teams']; th, ta = T.get(home), T.get(away)
    if not th or not ta: return None
    qm = (gm.get('qb') or {}).get('margin') or 0
    hb, ab = (1 if qbs.get(home) else 0), (1 if qbs.get(away) else 0)
    hfa = 0.0 if neutral else gm['hfa']
    return th['rate'] - ta['rate'] + hfa - qm * (hb - ab), bool(hb), bool(ab)


def grade(entry, gs):
    g = find_game(gs, entry['home'], entry['away'], entry['kick'])
    if not g or not g['done']: return {}
    home = entry['side'] == 'home'
    margin = (g['hs'] - g['as_']) * (1 if home else -1)
    close = None if g['spread'] is None else (-g['spread'] if home else g['spread'])      # the line on the pick's own side, + = underdog
    res = 'W' if margin + entry['entry'] > 0 else 'L' if margin + entry['entry'] < 0 else 'P'
    return dict(result=res, hs=g['hs'], as_=g['as_'], margin=int(margin), espn_close=close, clv=None if close is None or entry.get('line_src') == 'close' else round(entry['entry'] - close, 1))


def settle(entry, gs, fin):
    """grade from nflverse's finished game; until it posts, use the final score the Sharp Money feed carries so a game settles as soon as it ends"""
    r = grade(entry, gs)
    if r: return r
    sc = fin.get(entry.get('key')) if fin else None
    if not sc: return {}
    home = entry['side'] == 'home'; margin = (sc[0] - sc[1]) * (1 if home else -1)
    res = 'W' if margin + entry['entry'] > 0 else 'L' if margin + entry['entry'] < 0 else 'P'
    return dict(result=res, hs=int(sc[0]), as_=int(sc[1]), margin=int(margin), espn_close=None, clv=None, settled_by='feed')


def backfill(gm, gs, pick_edge, store, now):
    """One-time (--backfill): the weeks of this season played before the page existed. Each game is projected by build_game_model's walk-forward (the
    ratings as they stood BEFORE that game) and entered at the CLOSING spread, because that is the only line stored for those games. It is flagged
    backfill: graded after the fact, a baseline, and no read on beating the close (the close is the line it is graded against)."""
    import build_game_model as bgm
    bgm.HFA = gm['hfa'] - ((gm.get('inseason_overlay') or {}).get('hfa') or {}).get('delta', 0)
    bgm.QB = {'margin': gm['qb']['margin'], 'total': gm['qb']['total']}
    bgm.MKT = {'margin': gm['market_learning']['w']['margin'], 'total': gm['market_learning']['w']['total']}
    season = gm['through_season']
    games = bgm.fetch_games()
    _, _, _, preds, _, _ = bgm.run(games, collect_from=season, qb=bgm.QB)
    played = [g for g in games if g['played'] and g['season'] >= season]
    assert len(played) == len(preds), (len(played), len(preds))
    have = {(b['home'], b['away'], b['week']) for b in store.get('board', [])}
    out = []
    for g, p in zip(played, preds):
        sg_ = next((x for x in gs if x['home'] == g['ht'] and x['away'] == g['at'] and x['week'] == g['week']), None)
        if sg_ is None or p['spread'] is None or (g['ht'], g['at'], g['week']) in have: continue
        edge = p['pm'] - p['spread']; side = 'home' if edge > 0 else 'away'
        out.append(dict(key=f"nflverse:{season}_{g['week']:02d}_{g['at']}_{g['ht']}", kick=sg_['kick'], home=g['ht'], away=g['at'], home_id=g['ht'], away_id=g['at'], week=g['week'],
                        neutral=bool(g['neutral']), backfill=True, line_src='close', model_margin=round(p['pm'], 1), market_margin=round(p['spread'], 1), open_margin=None, edge=round(edge, 1),
                        pick=dict(side=side, team=g['ht'] if side == 'home' else g['at'], line=-p['spread'] if side == 'home' else p['spread']) if abs(edge) >= pick_edge else None,
                        side=side, team=g['ht'] if side == 'home' else g['at'], entry=round(-p['spread'] if side == 'home' else p['spread'], 1), logged=int(now),
                        is_pick=bool(abs(edge) >= pick_edge)))
    return out


def cmd_backtest(a):
    """Walk-forward picks vs the closing spread, from build_game_model's own run(): a prediction is made BEFORE each game updates the ratings."""
    import build_game_model as bgm
    gm = load('game_model.json')
    bgm.HFA = gm['hfa'] - ((gm.get('inseason_overlay') or {}).get('hfa') or {}).get('delta', 0)      # the fitted home field, not the in-season served one
    bgm.QB = {'margin': gm['qb']['margin'], 'total': gm['qb']['total']}
    bgm.MKT = {'margin': gm['market_learning']['w']['margin'], 'total': gm['market_learning']['w']['total']}
    games = bgm.fetch_games()
    _, _, _, preds, _, _ = bgm.run(games, collect_from=bgm.TEST_FROM, qb=bgm.QB)
    mp = [p for p in preds if p['spread'] is not None]
    rules = load('game_rules.json', {}) or {}
    edge = (rules.get('bands') or {}).get('spread', [LEAN_EDGE, PICK_EDGE])[1]
    def rec(ps):
        w = l = 0
        for p in ps:
            e = p['pm'] - p['spread']
            c = (1 if e > 0 else -1) * (p['result'] - p['spread'])        # the model's side vs the closing spread
            if c > 0: w += 1
            elif c < 0: l += 1
        return [w, l]
    seasons = {}
    for y in sorted({p['season'] for p in mp}):
        ps = [p for p in mp if p['season'] == y]
        seasons[str(y)] = dict(games=len(ps), model_miss=round(statistics.fmean(abs(p['pm'] - p['result']) for p in ps), 2), market_miss=round(statistics.fmean(abs(p['spread'] - p['result']) for p in ps), 2),
                               picks_wk4=rec([p for p in ps if abs(p['pm'] - p['spread']) >= edge]), picks_all=rec(ps))
    combined = dict(picks_wk4=rec([p for p in mp if abs(p['pm'] - p['spread']) >= edge]), picks_all=rec(mp))
    by_edge = {}
    for t in (1.5, 3, 5):
        r_ = rec([p for p in mp if abs(p['pm'] - p['spread']) >= t])
        by_edge[str(t)] = dict(record=r_, n=sum(r_), ci=sm.clopper_pearson(r_[0], sum(r_)))
    out = dict(generated=datetime.datetime.now(datetime.timezone.utc).isoformat(), pick_edge=edge, min_week=1, seasons=seasons, combined=combined, by_edge=by_edge,
               n=len(mp), note='Out-of-sample: each game is predicted before it updates the ratings. Graded against the closing spread (nflverse spread_line) at a flat -110, so break-even is 52.4%.')
    json.dump(out, open(BACKTEST, 'w'), indent=1)
    print(json.dumps(dict(n=out['n'], edge=edge, combined=combined, by_edge=by_edge)))


def cmd_update(a):
    gm = load('game_model.json'); rules = load('game_rules.json', {}) or {}
    bands = (rules.get('bands') or {}).get('spread') or [LEAN_EDGE, PICK_EDGE]
    lean_edge, pick_edge = float(bands[0]), float(bands[1])
    qbs = (load('qb_status.json', {}) or {}).get('teams') or {}
    season = int((load('nflverse_meta.json', {}) or {}).get('current_season') or gm.get('through_season'))
    gs = games_2026(season)
    store = load('nfl_model.json', {}) or {}
    feed = json.load(open(a.sharp)); now = feed['ts']
    fin = {g['key']: (g['final']['home'], g['final']['away']) for g in feed['games'] if g.get('final') and g['final'].get('home') is not None}

    played = {}
    for g in gs:
        if g['done']:
            for t in (g['home'], g['away']): played[t] = played.get(t, 0) + 1
    through = max([g['week'] for g in gs if g['done']], default=0)
    ratings = sorted(({'id': t, 'team': NAMES.get(t, t), 'abbr': t, 'overall': round(v['rate'], 1), 'off': round(v['off'], 1), 'def': round(v['def'], 1), 'games': played.get(t, 0)}
                      for t, v in gm['teams'].items()), key=lambda x: -x['overall'])
    for i, x in enumerate(ratings): x['rank'] = i + 1

    # the slate: upcoming games the Sharp Money feed lists, with their lines
    slate, un = [], 0
    offseason = bool(gm.get('offseason'))
    for g in feed['games']:
        if g['sport'] != 'nfl' or g['start'] <= now: continue
        h, aw = mt(g['home'].get('abbr')), mt(g['away'].get('abbr'))
        pin_sp = (g.get('pin') or {}).get('sp') or {}; con_sp = (g.get('consensus') or {}).get('sp') or {}
        line = pin_sp.get('line'); seen_src, seen_book = ('pinnacle', pin_sp) if line is not None else (None, None)
        if line is None:
            line = con_sp.get('line')
            if line is not None: seen_src, seen_book = 'consensus', con_sp
        oline = ((g.get('open') or {}).get('sp') or {}).get('line')
        sg_ = find_game(gs, h, aw, g['start'])
        if line is None or sg_ is None:
            un += 1; continue
        neutral = bool(sg_['neutral'] or f'{aw}@{h}' in (gm.get('neutral') or []))
        pr = project(gm, qbs, h, aw, neutral)
        if pr is None:
            un += 1; continue
        pred, hb, ab = pr
        mkt = -line; edge = pred - mkt
        side = 'home' if edge > 0 else 'away'
        pick = None
        if abs(edge) >= pick_edge and not offseason:
            pick = dict(side=side, team=h if side == 'home' else aw, line=line if side == 'home' else -line)
        slate.append(dict(key=g['key'], mkt_check=sm.market_check(g, side, oline), kick=g['start'], home=h, away=aw, home_id=h, away_id=aw, week=sg_['week'], neutral=neutral, backfill=False,
                          seen=dict(src=seen_src, line=line, book=seen_book), model_margin=round(pred, 1), market_margin=round(mkt, 1), open_margin=None if oline is None else round(-oline, 1),
                          edge=round(edge, 1), pick=pick, backup=dict(home=hb, away=ab)))
    slate.sort(key=lambda x: (x['kick'], -abs(x['edge'])))
    cards = sm.feed_cards(feed, 'nfl')

    if a.backfill:
        have_b = {b['key'] for b in store.get('board', [])}
        store.setdefault('board', []).extend(b for b in backfill(gm, gs, pick_edge, store, now) if b['key'] not in have_b)
        store.setdefault('log', []).extend(dict(b, logged=int(now)) for b in store['board'] if b.get('backfill') and b['is_pick'] and b['key'] not in {e['key'] for e in store.get('log', [])})
    # the pick log: every pick logged once, before kickoff, at the line we saw; graded when the game ends
    log = store.get('log', []); have = {e['key'] for e in log}
    for s in slate:
        if s['pick'] and s['key'] not in have and s['kick'] > now:
            log.append(dict(key=s['key'], week=s['week'], kick=s['kick'], home=s['home'], away=s['away'], home_id=s['home_id'], away_id=s['away_id'], side=s['pick']['side'], team=s['pick']['team'],
                            entry=s['pick']['line'], model_margin=s['model_margin'], market_margin=s['market_margin'], edge=s['edge'], logged=int(now), backfill=False, neutral=s['neutral']))
    # the board: every game the model projected, picks or not, kept after kickoff. Projections freeze once a game has started.
    board = store.get('board', []); bidx = {b['key']: b for b in board}
    for s_ in slate:
        old = bidx.get(s_['key'])
        if old and old['kick'] <= now:
            for k_ in ('mkt_check', 'cards'):
                if k_ not in old and k_ in s_: old[k_] = s_[k_]
            continue
        side = 'home' if s_['edge'] > 0 else 'away'
        ent = dict(s_, side=side, team=s_['home'] if side == 'home' else s_['away'], entry=round(-s_['market_margin'] if side == 'home' else s_['market_margin'], 1), logged=int(now), is_pick=bool(s_['pick']))
        ent.pop('seen', None)
        if old: old.update(ent)
        else: board.append(ent); bidx[s_['key']] = ent
    sm.capture_board(board, slate, now)       # the last takeable pre-kick line, with its time, for grading the tile
    for e in board:                           # signals keep firing until kickoff, so an upcoming game's cards are re-read every run; they freeze when the game starts
        if e['kick'] > now: e.pop('cards', None)
    sm.attach_cards(board, cards)
    for e in board:                           # the final lock: what the model says an hour before kickoff, Sharp Money cards included
        if e.get('backfill') or 'final' in e: continue
        if 0 < e['kick'] - now <= LOCK_SECS or e['kick'] <= now:
            at = int(now) if e['kick'] > now else e.get('logged', int(now))
            e['final'] = dict(side=e['side'], team=e['team'], entry=e['entry'], edge=e['edge'], is_pick=bool(e['is_pick']), at=at, mins_before=max(0, round((e['kick'] - at) / 60)),
                              cards=e.get('cards'), home_id=e['home_id'], away_id=e['away_id'])
    def _settle(x, key, ids=None):
        if 'result' in x and x.get('settled_by') != 'feed': return            # settled by the schedule: final. A feed-settled one is upgraded when nflverse catches up
        r = settle(dict(x, key=key, **(ids or {})), gs, fin)
        if r: x.pop('settled_by', None); x.update(r)
    for e in board:
        _settle(e, e['key'])
        if e.get('final'): _settle(e['final'], e['key'], dict(home=e['home'], away=e['away'], kick=e['kick'], home_id=e['home_id'], away_id=e['away_id']))
    board.sort(key=lambda x: -x['kick'])
    for e in log: _settle(e, e['key'])
    gr = [e for e in log if e.get('result') in ('W', 'L', 'P')]
    w = sum(e['result'] == 'W' for e in gr); l = sum(e['result'] == 'L' for e in gr); n = w + l
    clvs = [e['clv'] for e in gr if e.get('clv') is not None]
    summary = dict(picks=len(log), graded=n, won=w, lost=l, pushed=len(gr) - n, expected=round(n * BREAKEVEN, 2),
                   z=round((w - n * BREAKEVEN) / math.sqrt(n * BREAKEVEN * (1 - BREAKEVEN)), 2) if n else None,
                   clv_n=len(clvs), clv_mean=round(sum(clvs) / len(clvs), 2) if clvs else None, clv_pos=round(sum(c > 0 for c in clvs) / len(clvs), 3) if clvs else None)
    cards_summary = sm.tile_cards_summary(board, pick_edge, 'nfl:')
    final_summary = sm.final_summary(board, pick_edge, {x['key']: x for x in log})
    for s_ in slate: s_.pop('seen', None)
    backtest = json.load(open(BACKTEST)) if os.path.exists(BACKTEST) else None
    json.dump(dict(generated=datetime.datetime.now(datetime.timezone.utc).isoformat(), sport='nfl', season=season, through_week=through, games_rated=sum(1 for g in gs if g['done']),
                   params=dict(pick_edge=pick_edge, lean_edge=lean_edge, hfa=gm['hfa'], base_pts=gm['base_pts'], sd_margin=gm['sd_margin'], qb_margin=(gm.get('qb') or {}).get('margin')), unmatched_games=un,
                   game_model=dict(generated=gm.get('generated'), through_week=gm.get('through_week'), backtest=gm.get('backtest')), backtest=backtest,
                   ratings=ratings, slate=slate, board=board, model_version=MODEL_VERSION, cards_summary=cards_summary, final_summary=final_summary, log=log, log_summary=summary),
              open(OUT, 'w'), separators=(',', ':'))
    print(json.dumps(dict(through_week=through, rated=len(ratings), slate=len(slate), unmatched=un, log=summary)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['backtest', 'update'])
    ap.add_argument('--sharp', help='path to the Sharp Money data.json (sharp-data branch)')
    ap.add_argument('--backfill', action='store_true', help='one time: add this season\'s games played before the page existed, projected walk-forward and entered at the closing spread'); a = ap.parse_args()
    {'backtest': cmd_backtest, 'update': cmd_update}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
