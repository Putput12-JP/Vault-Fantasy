#!/usr/bin/env python3
"""Vault's college football model: power ratings, this week's projected spreads, and a graded pick log.

An experiment, and labeled as one. It is the method from scripts/cfb_efficiency_study.py (opponent-adjusted
EPA per play, ridge, last season's ratings as a prior) and that study found it does NOT beat the closing
line (5+ point disagreements covered 47-51% against a 52.4% break-even). So this page reports ratings and
projections honestly, logs every pick it would make, and grades them against real scores and ESPN's
closing spread. It earns a Trust it only by clearing the same bar as every other Sharp Money signal.

  python3 scripts/cfb_model.py priors   # once per offseason: walk-forward 2021-2025, writes the frozen
                                        #   preseason ratings (data/cfb_model_priors.json) and the backtest
                                        #   summary (data/cfb_model_backtest.json)
  python3 scripts/cfb_model.py update --sharp data.json
                                        # in season: refit on 2026 games, project the slate that the
                                        #   Sharp Money feed lists, log new picks, grade finished ones,
                                        #   write data/cfb_model.json for the page

Needs pandas, numpy, scipy, scikit-learn, pyarrow. Handicap convention: a team's spread, + = underdog.
"""
import argparse, datetime, json, math, os, sys, tempfile
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
PRIORS = os.path.join(DATA, 'cfb_model_priors.json')
BACKTEST = os.path.join(DATA, 'cfb_model_backtest.json')
PRIORS_V2 = os.path.join(DATA, 'cfb_model_priors_v2.json')
OUT = os.path.join(DATA, 'cfb_model.json')
PICK_EDGE = 5.0          # disagree with the market by at least this many points
LOCK_SECS = 3600         # the final lock: the state an hour before kickoff (or the last run before it, when none fell in that hour)
PICK_MIN_WEEK = 4        # the first month is dominated by the prior, which has no talent or portal information
BREAKEVEN = 110 / 210
FBS_ADDITIONS = {16}      # teams new to FBS this season (ESPN ids), added each offseason: 2026 = Sacramento State


BLEND_W = 0.10           # weight on the model's disagreement in the blended line: fit on 2022-2025 closing lines (0.07 tuned, 0.13 on the test seasons). It cuts the market's miss by 0.01 pts, i.e. nothing


def cfbd_opens(played=False):
    """(home_id, away_id) -> first posted home spread (+ = home underdog) from CollegeFootballData, ESPN's recorded open, else a CFBD book that recorded a move first, then DraftKings, Bovada, any.
    The feed's own 'open' (Action Network book 30) only starts once the game enters its window, so it can sit well inside the true opener:
    ND @ BYU showed -10 there while the books opened -11 to -12.5. Returns {} until the lines file exists."""
    lp, tp = os.path.join(ROOT, 'data', 'cfbd', 'lines_2026.json'), os.path.join(ROOT, 'data', 'cfbd', 'teams_fbs_2026.json')
    if not (os.path.exists(lp) and os.path.exists(tp)): return {}
    sid = {t['school']: int(t['id']) for t in json.load(open(tp))}
    best = {}
    for r in json.load(open(lp)):
        h, aw = sid.get(r.get('home')), sid.get(r.get('away'))
        if h is None or aw is None or r.get('so') is None or (r.get('hs') is not None and not played): continue
        # a row whose open equals its current line may be a snapshot, not a real opener (DK showed 10/10 for ND @ BYU while its total fell 54.5 -> 47.5),
        # so a book that recorded a move outranks one that did not
        rk = (0 if r.get('sp') is not None and r['sp'] != r['so'] else 1, {'DraftKings': 0, 'Bovada': 1}.get(r['p'], 2))
        if (h, aw) not in best or rk < best[(h, aw)][0]: best[(h, aw)] = (rk, float(r['so']))
    out = {k: v[1] for k, v in best.items()}
    ep = os.path.join(ROOT, 'data', 'cfbd', 'espn_opens_2026.json')      # ESPN records the open as its own field (scripts/fetch_espn_opens.py): it wins over CFBD
    if os.path.exists(ep):
        for r in json.load(open(ep)):
            h, aw = sid.get(r.get('home')), sid.get(r.get('away'))
            if h is not None and aw is not None and r.get('so') is not None and (played or (h, aw) in out): out[(h, aw)] = float(r['so'])
    return out


def market_check(g, side, op=None):
    """does the market, as the Sharp Money feed sees it, point the same way as our side? +1 agrees, -1 disagrees, 0 quiet. Three independent reads."""
    sg = 1 if side == 'home' else -1
    out = {}
    if op is None: op = ((g.get('open') or {}).get('sp') or {}).get('line')
    now = (((g.get('pin') or {}).get('sp') or {}).get('line'))
    if now is None: now = ((g.get('consensus') or {}).get('sp') or {}).get('line')
    if op is not None and now is not None:        # line is the home spread, + = underdog; a falling number means the home side got stronger
        toward = (op - now) * sg
        out['move'] = dict(v=1 if toward >= 0.5 else -1 if toward <= -0.5 else 0, pts=round(toward, 1))
    sp = ((g.get('splits') or {}).get('sp') or {})
    if sp.get('home') and sp.get('away'):         # money share minus ticket share on our side: money heavier than tickets means bigger bets are on it
        mine, t, m = ('home' if side == 'home' else 'away'), None, None
        t, m = sp[mine].get('t'), sp[mine].get('m')
        if t is not None and m is not None:
            d = m - t
            out['money'] = dict(v=1 if d >= 5 else -1 if d <= -5 else 0, pts=d)
    fl = ((g.get('flow') or {}).get('sharp') or {})
    if fl:
        net = (fl.get('sp:home', 0) - fl.get('sp:away', 0) + fl.get('ml:home', 0) - fl.get('ml:away', 0)) * sg
        out['sharp'] = dict(v=1 if net >= 5000 else -1 if net <= -5000 else 0, usd=int(net))
    vs = [x['v'] for x in out.values()]
    out['agree'] = sum(v > 0 for v in vs); out['disagree'] = sum(v < 0 for v in vs); out['reads'] = len(vs)
    return out


def feed_cards(feed):
    """the signals each Sharp Money card showed on the spread, snapshotted before kickoff and kept after (feed['picks']): {game key: {'home': [kinds], 'away': [kinds], 'lbl', 'start'}}"""
    out = {}
    for p in feed.get('picks') or []:
        if p.get('sport') != 'cfb' or p.get('m') != 'sp': continue
        o = out.setdefault(p['game'], {'home': [], 'away': [], 'lbl': p['gameLbl'], 'start': p['start']})
        o[p['side']] = sorted(set(o[p['side']]) | set(p['kinds']))
    return out


def _subseq(ab, name):
    import re
    n = re.sub('[^A-Z]', '', name.upper()); i = 0
    for ch in n:
        if i < len(ab) and ch == ab[i]: i += 1
    return i == len(ab)


def cards_for(cards, key, home, away, kick):
    import re
    if key in cards: return cards[key]
    hit = [c for c in cards.values() if abs(c['start'] - kick) <= 1800 and _subseq(re.sub('[^A-Z]', '', c['lbl'].split('@')[0].upper()), away) and _subseq(re.sub('[^A-Z]', '', c['lbl'].split('@')[1].upper()), home)]
    return hit[0] if len(hit) == 1 else None


def attach_cards(board, cards):
    """give every board game the Sharp Money spread cards it showed before kickoff. Exact on the feed's own key; otherwise by kickoff window and
    the abbreviation test, then a one-to-one pairing of whatever is left at the same kickoff (abbreviations like TEX @ OU defeat a letter test)"""
    import re
    ab = lambda x: re.sub('[^A-Z]', '', x.upper())
    used = set()
    for e in board:
        if e['key'] in cards: e['cards'] = {'home': cards[e['key']]['home'], 'away': cards[e['key']]['away']}; used.add(e['key'])
    for e in board:
        if e.get('cards') is not None: continue
        c = [(k, v) for k, v in cards.items() if k not in used and abs(v['start'] - e['kick']) <= 1800
             and _subseq(ab(v['lbl'].split('@')[0]), e['away']) and _subseq(ab(v['lbl'].split('@')[1]), e['home'])]
        if len(c) == 1: e['cards'] = {'home': c[0][1]['home'], 'away': c[0][1]['away']}; used.add(c[0][0])
    def lcs(x, y):
        m = [[0] * (len(y) + 1) for _ in range(len(x) + 1)]
        for i in range(len(x)):
            for j in range(len(y)): m[i + 1][j + 1] = m[i][j] + 1 if x[i] == y[j] else max(m[i][j + 1], m[i + 1][j])
        return m[-1][-1]
    def sc(a_, name):
        n = ab(name); return lcs(a_, n) / max(len(a_), 1) + (1.0 if a_[:1] == n[:1] else 0.0)
    pairs = []
    for e in board:
        if e.get('cards') is not None: continue
        for k, v in cards.items():
            if k in used or abs(v['start'] - e['kick']) > 1800: continue
            pairs.append((sc(ab(v['lbl'].split('@')[0]), e['away']) + sc(ab(v['lbl'].split('@')[1]), e['home']), id(e), e, k, v))
    for score, _, e, k, v in sorted(pairs, key=lambda x: -x[0]):
        if score < 2.6 or e.get('cards') is not None or k in used: continue          # both sides must look right (max 4)
        e['cards'] = {'home': v['home'], 'away': v['away']}; used.add(k)


def team_names(d, years):
    out = {}
    for y in years:
        s = pd.read_parquet(st.fetch(f'{st.REL}/espn_cfb_schedules/cfb_schedule_{y}.parquet', f'{d}/sched_{y}.parquet'),
                            columns=['home_id', 'away_id', 'home_team', 'away_team', 'home_abbreviation', 'away_abbreviation'])
        for r in s.itertuples():
            out[int(r.home_id)] = [r.home_team, r.home_abbreviation, None]; out[int(r.away_id)] = [r.away_team, r.away_abbreviation, None]
        p = pd.read_parquet(st.fetch(f'{st.REL}/espn_cfb_pbp/play_by_play_{y}.parquet', f'{d}/pbp_{y}.parquet'),
                            columns=['homeTeamId', 'homeTeamName', 'awayTeamId', 'awayTeamName']).drop_duplicates(['homeTeamId', 'awayTeamId'])
        for r in p.itertuples():
            for i, nm in ((int(r.homeTeamId), r.homeTeamName), (int(r.awayTeamId), r.awayTeamName)):
                if i in out: out[i][2] = nm
    return out


def cmd_priors(a):
    d = a.dir; os.makedirs(d, exist_ok=True)
    tg, gm = st.load(d); fbs = st.fbs_sets(gm, d); finals = {}
    res = st.walk_forward(tg, gm, fbs, finals=finals)
    names = team_names(d, st.YEARS)
    fa, fb = finals[2025]
    json.dump(dict(through=2025, S=st.S, ALPHA=st.ALPHA, K=st.K, HFA=st.HFA, generated=pd.Timestamp.now('UTC').isoformat(),
                   a={str(t): round(v, 5) for t, v in fa.items() if t in fbs[2025]}, b={str(t): round(v, 5) for t, v in fb.items() if t in fbs[2025]},
                   fbs=sorted(int(t) for t in fbs[2025]), names={str(t): list(v) for t, v in names.items() if t in fbs[2025]}),
              open(PRIORS, 'w'))
    # backtest summary: the numbers shown on the page
    r = res[res.season >= 2022].dropna(subset=['mkt']).copy(); r['edge'] = r.pred - r.mkt; r['cover'] = r.hm - r.mkt
    def rec(x, T):
        b = x[(x.edge.abs() >= T) & (x.cover != 0)]; w = int(((b.cover * np.sign(b.edge)) > 0).sum()); return [w, len(b) - w]
    seasons = {}
    for y in (2022, 2023, 2024, 2025):
        x = r[r.season == y]; xl = x[x.week >= PICK_MIN_WEEK]
        seasons[str(y)] = dict(games=len(x), model_miss=round(float(np.abs(x.hm - x.pred).mean()), 2), market_miss=round(float(np.abs(x.hm - x.mkt).mean()), 2),
                               picks_wk4=rec(xl, PICK_EDGE), picks_all=rec(x, PICK_EDGE), picks3_wk4=rec(xl, 3), picks7_wk4=rec(xl, 7))
    allw = r[r.week >= PICK_MIN_WEEK]
    # opening_lines is the 2022-2025 open-vs-close record from the retro note. This rewrite
    # recomputes the walk-forward close record only, so keep that key if it is already on the file.
    opening_lines = None
    if os.path.exists(BACKTEST):
        try: opening_lines = json.load(open(BACKTEST)).get('opening_lines')
        except Exception: opening_lines = None
    back = dict(generated=pd.Timestamp.now('UTC').isoformat(), method='walk-forward, ESPN spread as the market line, FBS vs FBS regular season',
                tuned_on='2022-2023', test='2024-2025', pick_edge=PICK_EDGE, min_week=PICK_MIN_WEEK, seasons=seasons,
                combined=dict(picks_wk4=rec(allw, PICK_EDGE), picks3_wk4=rec(allw, 3), picks7_wk4=rec(allw, 7)))
    if opening_lines: back['opening_lines'] = opening_lines
    json.dump(back, open(BACKTEST, 'w'), indent=1)
    print(json.dumps(json.load(open(BACKTEST))['combined']))


def cmd_priors_v2(a):
    """v2 preseason prior for 2026 (see docs/retro/cfb-efficiency-replication.md, step 2): a ridge regression on talent, returning production,
    recruiting and portal movement, fit on the 2022-2025 seasons. Run once per offseason after the Fetch CFBD data workflow."""
    import cfb_v2_prior_study as v2
    d = a.dir; os.makedirs(d, exist_ok=True)
    tg, gm = st.load(d); fbs = st.fbs_sets(gm, d); finals = {}
    st.walk_forward(tg, gm, fbs, finals=finals)
    tabs = []
    for y in range(2022, 2026):
        t = v2.features(y, finals[y - 1], fbs[y]); t['t_o'] = t.team.map(lambda x: finals[y][0].get(x, 0.0)); t['t_d'] = t.team.map(lambda x: finals[y][1].get(x, 0.0)); tabs.append(t)
    tr = pd.concat(tabs); bo, bd = v2.ridge(tr[v2.FEATS].values, tr.t_o.values, v2.LAM), v2.ridge(tr[v2.FEATS].values, tr.t_d.values, v2.LAM)
    F = set(int(t) for t in fbs[2025]) | FBS_ADDITIONS
    cur = v2.features(2026, finals[2025], F); Xc = np.c_[np.ones(len(cur)), cur[v2.FEATS].values]
    json.dump(dict(generated=pd.Timestamp.now('UTC').isoformat(), trained_on='2022-2025', lam=v2.LAM, feats=v2.FEATS, coef_off=[round(float(x), 4) for x in bo], coef_def=[round(float(x), 4) for x in bd],
                   a={str(t): round(float(v), 5) for t, v in zip(cur.team, Xc @ bo)}, b={str(t): round(float(v), 5) for t, v in zip(cur.team, Xc @ bd)}), open(PRIORS_V2, 'w'))
    print('v2 prior written for', len(cur), 'teams')


def grade(entry, g26):
    """grade one logged pick against a finished 2026 game; returns dict of result fields"""
    m = g26[(g26.homeTeamId == entry['home_id']) & (g26.awayTeamId == entry['away_id'])]
    if m.empty or not bool(m.iloc[0].status_type_completed): return {}
    x = m.iloc[0]; home = entry['side'] == 'home'
    margin = (x.homeFinalScore - x.awayFinalScore) * (1 if home else -1)
    close = None if pd.isna(x.homeTeamSpread) else (-x.homeTeamSpread if home else x.homeTeamSpread)
    res = 'W' if margin + entry['entry'] > 0 else 'L' if margin + entry['entry'] < 0 else 'P'
    return dict(result=res, hs=int(x.homeFinalScore), as_=int(x.awayFinalScore), margin=int(margin), espn_close=close, clv=None if close is None or entry.get('line_src') == 'espn' else round(entry['entry'] - close, 1))


def clopper_pearson(w, n, alpha=0.05):
    """Exact two-sided (1 - alpha) interval for w wins in n decided games (pushes already excluded). None when n is 0."""
    if n <= 0: return None
    try:
        from scipy.stats import beta
        lo = 0.0 if w == 0 else float(beta.ppf(alpha / 2, w, n - w + 1))
        hi = 1.0 if w == n else float(beta.ppf(1 - alpha / 2, w + 1, n - w))
        return [round(lo, 3), round(hi, 3)]
    except ImportError:
        pass
    return _cp_bisect(w, n, alpha)


def _cp_bisect(w, n, alpha=0.05):
    """The same interval without scipy: bisection on the binomial CDF."""
    def cdf(k, p): return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))      # P(X <= k)
    def root(f, rising):
        a_, b_ = 0.0, 1.0
        for _ in range(60):
            m = (a_ + b_) / 2
            if (f(m) > 0) == rising: b_ = m
            else: a_ = m
        return (a_ + b_) / 2
    lo = 0.0 if w == 0 else root(lambda p: (1 - cdf(w - 1, p)) - alpha / 2, True)      # P(X >= w) = alpha/2, rises with p
    hi = 1.0 if w == n else root(lambda p: cdf(w, p) - alpha / 2, False)               # P(X <= w) = alpha/2, falls with p
    return [round(lo, 3), round(hi, 3)]


def _iso_utc(ts):
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _epoch(iso):
    """ISO time -> epoch seconds. A timestamp with no zone is read as UTC (every stamp this file writes is UTC), never as the box's local time."""
    try: t = datetime.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
    except (TypeError, ValueError): return None
    if t.tzinfo is None: t = t.replace(tzinfo=datetime.timezone.utc)
    return int(t.timestamp())


def capture_line(row, now):
    """Stamp the row's current market line (its own side, same sign as entry) and the run time while the game has not kicked off. Once now >= kick the stamp
    is never touched again, so line_captured_at < kick always holds for a real pre-kick capture. Returns True when it stamped."""
    kick = row.get('kick')
    if not isinstance(kick, (int, float)) or isinstance(kick, bool): return False      # no kick time: cannot prove the line is pre-kick, so never stamp
    if now >= kick or row.get('market_margin') is None or row.get('side') not in ('home', 'away'): return False
    row['line_captured'] = round(-row['market_margin'] if row['side'] == 'home' else row['market_margin'], 1)
    row['line_captured_at'] = _iso_utc(now)
    return True


def capture_board(board, slate, now):
    """capture_line for every board row whose game is in THIS run's slate. A row missing from the slate keeps its old stamp: its market_margin was not
    refreshed this run, so stamping it would record a stale line at a new time. Returns how many rows were stamped."""
    in_slate = {s_['key'] for s_ in slate}
    return sum(capture_line(e, now) for e in board if e.get('key') in in_slate)


def tile_fields(board):
    """Grade the Sharp Money tile at ONE takeable price: the last line before kickoff. Adds tile_line, tile_result ('W'/'L'/'P') and tile_line_src to every
    settled row and touches nothing else (result, entry and the pick cards stay as they were). An 'espn:' row is already at ESPN's line, which is the close.
    A row with line_captured stamped before kick is graded at that line ('captured_prekick', takes precedence). A 'cfb:' row logged at or after kickoff is a feed backfill whose entry is the OPEN (look-ahead), so it is regraded at espn_close (same sign as entry:
    the line on the row's own side). A 'cfb:' row logged before kickoff keeps entry, the last pre-kick board line. No stored close means no tile grade."""
    for e in board:
        for k in ('tile_line', 'tile_result', 'tile_line_src'): e.pop(k, None)
        if e.get('result') not in ('W', 'L', 'P') or e.get('margin') is None: continue
        cap_at = _epoch(e.get('line_captured_at'))
        if e.get('line_captured') is not None and cap_at is not None and cap_at < e['kick']:
            line, src = e['line_captured'], 'captured_prekick'
        elif e['key'].startswith('cfb:') and e['logged'] >= e['kick']:
            line, src = e.get('espn_close'), 'close_no_ts'      # the book's closing spread (the DraftKings close), no capture timestamp
        else: line, src = e['entry'], 'entry'
        if line is None: continue
        e['tile_line'] = line; e['tile_line_src'] = src
        e['tile_result'] = 'W' if e['margin'] + line > 0 else 'L' if e['margin'] + line < 0 else 'P'


def tile_cards_summary(board):
    """The Sharp Money vs the model tile, built from tile_result. Each table row keeps all/feed as [w, l] and adds n, ci (95% Clopper-Pearson) and
    before (the old record, graded at entry); the feed column's are feed_n, feed_ci, feed_before."""
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
        ('Model picks (5+ points) that Sharp Money backs', 'The model is 5+ points from the market and a card is on its side.', lambda e: e['is_pick'] and mine(e)),
        ('Model picks (5+ points) with no Sharp Money behind them', 'The model is 5+ points from the market and no card is on its side.', lambda e: e['is_pick'] and not mine(e)),
    ]
    feed_only = lambda e: e['key'].startswith('cfb:')           # entered at a feed line, not at ESPN's line
    def _stats(label, note, sel, osel):
        fs, ofs = [e for e in sel if feed_only(e)], [e for e in osel if feed_only(e)]
        al, fe = _cs(sel), _cs(fs)
        return dict(label=label, note=note, all=al, n=sum(al), ci=clopper_pearson(al[0], sum(al)), before=_old(osel),
                    feed=fe, feed_n=sum(fe), feed_ci=clopper_pearson(fe[0], sum(fe)), feed_before=_old(ofs), keys=[e['key'] for e in sel])
    cards_table = [_stats(l, n_, [e for e in withc if f(e)], [e for e in old_withc if f(e)]) for l, n_, f in rows_def]
    base = _stats('Every game the model projected', 'The baseline: the model\'s side in every finished game, picks and leans, whatever Sharp Money did.', gg, old_gg)
    return dict(graded=len(gg), with_cards=len(withc), table=[base] + cards_table)


def rebuild_tile(path=None):
    """Recompute the tile fields and cards_summary from the board already in data/cfb_model.json and rewrite it in place, every other key untouched.
    Offline: python3 -c "import sys; sys.path.insert(0, 'scripts'); import cfb_model; cfb_model.rebuild_tile()" """
    path = path or OUT
    d = json.load(open(path))
    d['cards_summary'] = tile_cards_summary(d['board'])
    json.dump(d, open(path, 'w'))
    return d['cards_summary']


def settle(entry, g26, fin):
    """grade from ESPN's finished game when the play-by-play release has it (also gives closing-line value); until then use the final score the Sharp Money feed
    carries, so a game settles as soon as it ends. The feed-settled result is replaced by the ESPN one when that catches up."""
    r = grade(entry, g26)
    if r: return r
    sc = fin.get(entry.get('key')) if fin else None
    if not sc: return {}
    home = entry['side'] == 'home'; margin = (sc[0] - sc[1]) * (1 if home else -1)
    res = 'W' if margin + entry['entry'] > 0 else 'L' if margin + entry['entry'] < 0 else 'P'
    return dict(result=res, hs=int(sc[0]), as_=int(sc[1]), margin=int(margin), espn_close=None, clv=None, settled_by='feed')


LINES26 = os.path.join(ROOT, 'data', 'cfbd', 'lines_2026.json')


def open_check(g26, F, rated_before, K, HFA):
    """The same model, graded against the OPENING line instead of the close.

    Backtest 2022-2025 (docs/retro/cfb-efficiency-replication.md): 5+ point disagreements with the opening spread covered 57.5% (435-321),
    against 51.5% when measured against the close. That is an edge in a number we may not be able to bet, so this is a record, not a pick list:
    every FBS-vs-FBS game from PICK_MIN_WEEK on is re-projected with ratings fit only on EARLIER weeks (so nothing sees its own game), compared
    with the first spread a book posted (CollegeFootballData spreadOpen: DraftKings, then Bovada, then any), and graded when it ends.
    Nothing is tuned here: the 5-point threshold is the one already used for the pick log. Returns None until the lines file exists."""
    if not os.path.exists(LINES26): return None
    rows = {}
    for r in json.load(open(LINES26)):
        if r.get('so') is None or r.get('id') is None: continue
        rk = {'DraftKings': 0, 'Bovada': 1}.get(r['p'], 2)
        if r['id'] not in rows or rk < rows[r['id']][0]: rows[r['id']] = (rk, r)
    ep = os.path.join(ROOT, 'data', 'cfbd', 'espn_opens_2026.json')       # ESPN's recorded open wins (scripts/fetch_espn_opens.py); same ids as CFBD
    if os.path.exists(ep):
        for r in json.load(open(ep)):
            if r['id'] in rows and r.get('so') is not None: rows[r['id']] = (rows[r['id']][0], dict(rows[r['id']][1], so=r['so'], p='ESPN'))
    games, fbs_games, with_open = [], 0, 0
    for x in g26.itertuples():
        h, aw = int(x.homeTeamId), int(x.awayTeamId)
        if h not in F or aw not in F or int(x.week) < PICK_MIN_WEEK: continue
        fbs_games += 1
        hit = rows.get(int(x.game_id))
        if not hit: continue
        with_open += 1
        ln = hit[1]; ra_w, rb_w = rated_before(int(x.week)); Pw = lambda t: ra_w.get(t, 0.0) - rb_w.get(t, 0.0)
        pred = K * (Pw(h) - Pw(aw)) + (0.0 if x.neutral_site == True else HFA)
        omargin = -float(ln['so']); edge = pred - omargin; home = edge > 0
        side_open = float(ln['so']) if home else -float(ln['so'])
        close = None if ln.get('sp') is None else (float(ln['sp']) if home else -float(ln['sp']))
        g = dict(id=int(x.game_id), week=int(x.week), home_id=h, away_id=aw, provider=ln['p'], side='home' if home else 'away', model_margin=round(pred, 1),
                 open_margin=round(omargin, 1), edge=round(edge, 1), entry=round(side_open, 1), close=close, clv=None if close is None else round(side_open - close, 1))
        if bool(x.status_type_completed):
            m = (x.homeFinalScore - x.awayFinalScore) * (1 if home else -1)
            g.update(margin=int(m), result='W' if m + side_open > 0 else 'L' if m + side_open < 0 else 'P')
        games.append(g)
    # Games not played yet: this is where the early number is still usable. The lines feed has no neutral-site flag and no kickoff time, so home field is
    # assumed (flagged) and the page orders by week. `toward` is how far the line has already moved toward the model's side since the open: when it is
    # positive, some of the edge is gone.
    sid = {}
    tp = os.path.join(ROOT, 'data', 'cfbd', 'teams_fbs_2026.json')
    if os.path.exists(tp): sid = {t['school']: int(t['id']) for t in json.load(open(tp))}
    done_ids = {int(x.game_id) for x in g26.itertuples()}
    nowk = int(g26[g26.status_type_completed == True].week.max() or 0) if len(g26) else 0      # opens for weeks further out are placeholders: only the next slate
    upcoming_n = 0
    for gid, (rk, ln) in rows.items():
        if int(gid) in done_ids or ln.get('hs') is not None or int(ln.get('wk') or 0) < PICK_MIN_WEEK or int(ln['wk']) > nowk + 1: continue
        h, aw = sid.get(ln.get('home')), sid.get(ln.get('away'))
        if h is None or aw is None or h not in F or aw not in F: continue
        wk = int(ln['wk']); ra_w, rb_w = rated_before(wk); Pw = lambda t: ra_w.get(t, 0.0) - rb_w.get(t, 0.0)
        pred = K * (Pw(h) - Pw(aw)) + HFA
        omargin = -float(ln['so']); edge = pred - omargin; home = edge > 0
        cur = None if ln.get('sp') is None else -float(ln['sp'])
        games.append(dict(id=int(gid), week=wk, home_id=h, away_id=aw, home=ln['home'], away=ln['away'], provider=ln['p'], side='home' if home else 'away',
                          model_margin=round(pred, 1), open_margin=round(omargin, 1), edge=round(edge, 1), entry=round(float(ln['so']) if home else -float(ln['so']), 1),
                          close=None if cur is None else round(-cur if home else cur, 1), clv=None if cur is None else round((float(ln['so']) - float(ln['sp'])) if home else (float(ln['sp']) - float(ln['so'])), 1),
                          toward=None if cur is None else round((cur - omargin) * (1 if home else -1), 1), neutral_assumed=True, upcoming=True))
        upcoming_n += 1
    def rec(sel):
        w = sum(g.get('result') == 'W' for g in sel); l = sum(g.get('result') == 'L' for g in sel); n = w + l
        return dict(won=w, lost=l, pct=round(w / n, 3) if n else None, z=round((w - n * BREAKEVEN) / math.sqrt(n * BREAKEVEN * (1 - BREAKEVEN)), 2) if n else None)
    opening = {}
    if os.path.exists(BACKTEST):
        try: opening = json.load(open(BACKTEST)).get('opening_lines') or {}
        except Exception: opening = {}
    vs_open, vs_close = opening.get('vs_open'), opening.get('vs_close')
    backtest = None
    if isinstance(vs_open, list) and isinstance(vs_close, list) and len(vs_open) == 2 and len(vs_close) == 2:
        backtest = dict(seasons=opening.get('seasons') or '2022-2025', vs_open=vs_open, vs_close=vs_close,
                        note=opening.get('note') or '5+ point disagreements, weeks 4+, from data/cfb_model_backtest.json opening_lines')
    out = dict(source='ESPN recorded open (DraftKings), else CollegeFootballData spreadOpen', min_week=PICK_MIN_WEEK, fbs_games=fbs_games, with_open=with_open, upcoming=upcoming_n,
               backtest=backtest,
               by_threshold={str(t): rec([g for g in games if abs(g['edge']) >= t]) for t in (3, 5, 7)},
               by_week={str(w): rec([g for g in games if g['week'] == w and abs(g['edge']) >= PICK_EDGE]) for w in sorted({g['week'] for g in games if 'result' in g})})
    picks = [g for g in games if abs(g['edge']) >= PICK_EDGE]
    clvs = [g['clv'] for g in picks if g.get('clv') is not None and 'result' in g]
    out.update(picks=len(picks), pending=sum('result' not in g for g in picks), clv_n=len(clvs), clv_mean=round(sum(clvs) / len(clvs), 2) if clvs else None,
               clv_pos=round(sum(c > 0 for c in clvs) / len(clvs), 3) if clvs else None, games=sorted(picks, key=lambda g: (-g['week'], -abs(g['edge']))))
    return out


def cmd_update(a):
    d = a.dir; os.makedirs(d, exist_ok=True)
    for f in (f'pbp_2026.parquet', 'sched_2026.parquet'):       # always fresh in season
        if os.path.exists(os.path.join(d, f)): os.remove(os.path.join(d, f))
    pri = json.load(open(PRIORS)); S, K, HFA = pri['S'], pri['K'], pri['HFA']
    prior = ({int(t): S * v for t, v in pri['a'].items()}, {int(t): S * v for t, v in pri['b'].items()})
    tg, gm = st.load(d, years=[2026])
    F = set(pri['fbs']) | FBS_ADDITIONS
    done = gm[(gm.status_type_completed == True)]
    T = tg[tg.game_id.isin(done.game_id) & tg.pos_team_id.isin(F) & tg.def_pos_team_id.isin(F)]
    ra, rb = st.fit(T, *prior)
    names = {int(t): list(v) for t, v in pri['names'].items()}; names.update(team_names(d, [2026]))
    played = {}
    for r in done.itertuples():
        for t in (r.homeTeamId, r.awayTeamId): played[t] = played.get(t, 0) + 1
    P = lambda t: ra.get(t, 0.0) - rb.get(t, 0.0)
    ratings = sorted(({'id': int(t), 'team': names.get(t, [str(t), '', ''])[2] or names.get(t, [str(t)])[0], 'abbr': names.get(t, ['', ''])[1], 'overall': round(K * P(t), 1),
                       'off': round(K * ra.get(t, 0.0), 1), 'def': round(-K * rb.get(t, 0.0), 1), 'games': played.get(t, 0)} for t in F if t in names),
                     key=lambda x: -x['overall'])
    for i, x in enumerate(ratings): x['rank'] = i + 1
    through = int(done.week.max()) if len(done) else 0
    name2id = {v[0]: k for k, v in names.items()}

    # the slate: upcoming FBS games the Sharp Money feed lists, with their lines. --since adds games that
    # already kicked off (a one-time backfill): they are projected with ratings fit only on EARLIER weeks and
    # entered at the opening line, and flagged so the page can say they were logged after the fact.
    gidx = {(int(r.homeTeamId), int(r.awayTeamId)): r for r in gm.drop_duplicates('game_id').itertuples()}
    p2 = json.load(open(PRIORS_V2)) if os.path.exists(PRIORS_V2) else None
    prior2 = ({int(t): v for t, v in p2['a'].items()}, {int(t): v for t, v in p2['b'].items()}) if p2 else None
    cache, cache2 = {}, {}
    def rated_before2(wk):
        if wk not in cache2:
            Tw = tg[tg.game_id.isin(done[done.week < wk].game_id) & tg.pos_team_id.isin(F) & tg.def_pos_team_id.isin(F)]
            cache2[wk] = st.fit(Tw, *prior2)
        return cache2[wk]
    def rated_before(wk):
        if wk not in cache:
            Tw = tg[tg.game_id.isin(done[done.week < wk].game_id) & tg.pos_team_id.isin(F) & tg.def_pos_team_id.isin(F)]
            cache[wk] = st.fit(Tw, *prior)
        return cache[wk]
    school2id = {}
    for t, v in names.items():
        if len(v) > 2 and v[2]: school2id.setdefault(v[2], t)
    def find_id(nm):          # the feed says "Hawai'i Warriors", ESPN says "Hawai'i Rainbow Warriors": fall back to the school name
        if nm in name2id: return name2id[nm]
        best = [sc for sc in school2id if nm.startswith(sc + ' ')]
        return school2id[max(best, key=len)] if best else None
    fin = {}
    copens = cfbd_opens()
    slate, un = [], 0
    if a.sharp and os.path.exists(a.sharp):
        feed = json.load(open(a.sharp)); now = feed['ts']
        fin = {g['key']: (g['final']['home'], g['final']['away']) for g in feed['games'] if g.get('final') and g['final'].get('home') is not None}
        for g in feed['games']:
            if g['sport'] != 'cfb': continue
            started = g['start'] <= now
            if started and not (a.since and g['start'] >= a.since): continue
            h, aw = find_id(g['home']['name']), find_id(g['away']['name'])
            pin_sp = (g.get('pin') or {}).get('sp') or {}
            con_sp = (g.get('consensus') or {}).get('sp') or {}
            line = pin_sp.get('line')
            seen_src, seen_book = (None, None)
            if line is not None: seen_src, seen_book = 'pinnacle', pin_sp
            else:
                line = con_sp.get('line')
                if line is not None: seen_src, seen_book = 'consensus', con_sp
            oline = ((g.get('open') or {}).get('sp') or {}).get('line')
            # The bettable open is the number on the board the moment this game is still pre-kickoff.
            # A game already started is a backfill and does not get one.
            seen = None if started or seen_book is None else dict(src=seen_src, line=line, book=seen_book)
            co = copens.get((h, aw))
            if co is not None: oline = co      # the books' first posted number, not the feed's later window-start open
            if started: line = oline          # in-game lines are live, so a backfilled game uses its opening line
            gr_ = gidx.get((h, aw)) if h is not None else None
            if h is None or aw is None or h not in F or aw not in F or line is None:
                un += 1; continue
            wk = int(gr_.week) if gr_ is not None else through + 1      # an unplayed game is not in the play-by-play: it is the NEXT week's, not the last finished week's
            neutral = bool(gr_ is not None and gr_.neutral_site == True)
            ra_w, rb_w = rated_before(wk)
            Pw = lambda t: ra_w.get(t, 0.0) - rb_w.get(t, 0.0)
            pred = K * (Pw(h) - Pw(aw)) + (0.0 if neutral else HFA)
            mkt = -line
            edge = pred - mkt
            pick = None
            if abs(edge) >= PICK_EDGE and wk >= PICK_MIN_WEEK:
                side = 'home' if edge > 0 else 'away'
                pick = dict(side=side, team=g['home' if side == 'home' else 'away']['short'], line=line if side == 'home' else -line)
            mc = None if started else market_check(g, 'home' if edge > 0 else 'away', oline)    # in-game lines and money are live, not a read on the pre-game market
            slate.append(dict(key=g['key'], mkt_check=mc, kick=g['start'], home=g['home']['short'], away=g['away']['short'], home_id=h, away_id=aw, week=wk, neutral=neutral,
                              backfill=started, seen=seen, model_margin=round(pred, 1), market_margin=round(mkt, 1), open_margin=None if oline is None else round(-oline, 1),
                              edge=round(edge, 1), pick=pick))
        if a.since:       # one-time backfill: games that kicked off since then but are not in the feed (it only lists a window), at ESPN's own line
            sc = pd.read_parquet(st.fetch(f'{st.REL}/espn_cfb_schedules/cfb_schedule_2026.parquet', f'{d}/sched_2026.parquet'), columns=['game_id', 'game_date'])
            sc['kick'] = pd.to_datetime(sc.game_date, utc=True).map(lambda t: int(t.timestamp()))
            kick_of = dict(zip(sc.game_id, sc.kick)); have_ids = {(x['home_id'], x['away_id']) for x in slate}
            if os.path.exists(OUT):
                try: have_ids |= {(b['home_id'], b['away_id']) for b in json.load(open(OUT)).get('board', []) if not b['key'].startswith('espn:')}
                except Exception: pass
            for r in gm.drop_duplicates('game_id').itertuples():
                k = kick_of.get(r.game_id)
                if k is None or k < a.since or k > now or (a.until and k >= a.until) or (int(r.homeTeamId), int(r.awayTeamId)) in have_ids: continue
                h, aw = int(r.homeTeamId), int(r.awayTeamId)
                if h not in F or aw not in F or pd.isna(r.homeTeamSpread): continue
                ra_w, rb_w = rated_before(int(r.week)); Pw = lambda t: ra_w.get(t, 0.0) - rb_w.get(t, 0.0)
                neutral = bool(r.neutral_site == True)
                pred = K * (Pw(h) - Pw(aw)) + (0.0 if neutral else HFA); mkt = float(r.homeTeamSpread); edge = pred - mkt
                nm = lambda t: (names.get(t, [str(t)]) + ['', ''])[2] or names[t][0]
                pick = None
                if abs(edge) >= PICK_EDGE and int(r.week) >= PICK_MIN_WEEK:
                    side = 'home' if edge > 0 else 'away'
                    pick = dict(side=side, team=nm(h if side == 'home' else aw), line=-mkt if side == 'home' else mkt)
                slate.append(dict(key=f'espn:{r.game_id}', kick=int(k), home=nm(h), away=nm(aw), home_id=h, away_id=aw, week=int(r.week), neutral=neutral, backfill=True,
                                  line_src='espn', model_margin=round(pred, 1), market_margin=round(mkt, 1), open_margin=None, edge=round(edge, 1), pick=pick))
        if prior2:      # shadow model: same games and lines, v2 prior. Tracked and graded, never shown as picks
            for x_ in slate:
                ra2, rb2 = rated_before2(x_['week']); P2 = lambda t: ra2.get(t, 0.0) - rb2.get(t, 0.0)
                pred2 = K * (P2(x_['home_id']) - P2(x_['away_id'])) + (0.0 if x_['neutral'] else HFA); e2 = pred2 - x_['market_margin']; sd2 = 'home' if e2 > 0 else 'away'
                x_['v2'] = dict(model_margin=round(pred2, 1), edge=round(e2, 1), side=sd2, team=x_['home'] if sd2 == 'home' else x_['away'],
                                entry=round(-x_['market_margin'] if sd2 == 'home' else x_['market_margin'], 1), is_pick=bool(abs(e2) >= PICK_EDGE and x_['week'] >= PICK_MIN_WEEK), line_src=x_.get('line_src'))
        feed_cards_ = feed_cards(feed)
        for x_ in slate: x_['blend_margin'] = round(x_['market_margin'] + BLEND_W * x_['edge'], 1)
        slate.sort(key=lambda x: (x['kick'], -abs(x['edge'])))
    else: now = int(pd.Timestamp.now('UTC').timestamp())

    # the pick log: every pick logged once, before kickoff, at the line we saw; graded when the game ends
    log = []
    if os.path.exists(OUT):
        try: log = json.load(open(OUT)).get('log', [])
        except Exception: log = []
    sl_ = {s['key']: s for s in slate}
    for e in log:       # a pick logged before kickoff under the wrong week was projected with ratings missing the last finished week: re-derive it from the slate, or drop it if it is no longer a pick
        s_ = sl_.get(e['key'])
        if s_ and e['kick'] > now and 'result' not in e and not e.get('backfill') and e['week'] != s_['week']:
            e['_redo'] = True
            if s_['pick']:
                e.update(week=s_['week'], side=s_['pick']['side'], team=s_['pick']['team'], entry=s_['pick']['line'], model_margin=s_['model_margin'],
                         market_margin=s_['market_margin'], edge=s_['edge'], neutral=s_['neutral'], line_src=s_.get('line_src'))
    log = [e for e in log if not (e.pop('_redo', False) and not sl_[e['key']]['pick'])]
    have = {e['key'] for e in log}
    for s in slate:
        if s['pick'] and s['key'] not in have and (s['kick'] > now or s['backfill']):
            log.append(dict(key=s['key'], week=s['week'], kick=s['kick'], home=s['home'], away=s['away'], home_id=s['home_id'], away_id=s['away_id'],
                            side=s['pick']['side'], team=s['pick']['team'], entry=s['pick']['line'], model_margin=s['model_margin'],
                            market_margin=s['market_margin'], edge=s['edge'], logged=int(now), backfill=s['backfill'], neutral=s['neutral'], line_src=s.get('line_src')))
    g26 = gm.drop_duplicates('game_id')
    # the board: every game the model projected, picks or not, kept after kickoff so the page can show the whole slate and how the
    # model's lean did. Projections freeze once a game has started (or was added after the fact).
    board = []
    if os.path.exists(OUT):
        try: board = json.load(open(OUT)).get('board', [])
        except Exception: board = []
    bidx = {b['key']: b for b in board}
    for s_ in slate:
        old = bidx.get(s_['key'])
        if old and (old['kick'] <= now or old.get('backfill')):
            for k_ in ('mkt_check', 'blend_margin', 'v2', 'cards'):      # added after the first sight: fill in, never change the frozen projection
                if k_ not in old and k_ in s_: old[k_] = s_[k_]
            continue
        side = 'home' if s_['edge'] > 0 else 'away'
        ent = dict(s_, side=side, team=s_['home'] if side == 'home' else s_['away'],
                   entry=round(-s_['market_margin'] if side == 'home' else s_['market_margin'], 1), logged=int(now),
                   is_pick=bool(s_['pick']))
        seen = ent.pop('seen', None)
        if old: bidx[s_['key']].update(ent)     # an existing row keeps the bettable open it was stamped with; a missing one is not backfilled
        else:
            if seen and not s_.get('backfill') and seen.get('line') is not None:
                book = seen.get('book') or {}
                px = book.get(side)
                price = px if isinstance(px, (int, float)) and not isinstance(px, bool) and abs(px) >= 100 else None
                ent['bettable_open'] = dict(line=seen['line'], price=price, ts=int(now), src=seen['src'], model_margin=s_['model_margin'],
                                            edge=s_['edge'], side=side, entry=ent['entry'])
            board.append(ent); bidx[s_['key']] = ent
    # games already played were frozen with whatever open the feed had; restate them from the books' first posted number (display only, the projection stays frozen)
    copens_all = cfbd_opens(played=True)
    for b in board:
        co_ = copens_all.get((b['home_id'], b['away_id']))
        if co_ is not None and not b['key'].startswith('espn:') or co_ is not None and b.get('open_margin') is None: b['open_margin'] = round(-co_, 1)
    seen = {(b['home_id'], b['away_id']) for b in board if not b['key'].startswith('espn:')}
    board[:] = [b for b in board if not (b['key'].startswith('espn:') and (b['home_id'], b['away_id']) in seen)]      # a game the feed also had: keep the feed's entry
    capture_board(board, slate, now)      # the last takeable pre-kick line, with its time, for grading the tile
    if a.sharp and os.path.exists(a.sharp):
        for e in board:                   # signals keep firing until kickoff, so an upcoming game's cards are re-read every run; they freeze when the game starts
            if e['kick'] > now: e.pop('cards', None)
        attach_cards(board, feed_cards_)
        for e in board:                   # the final lock: what the model says an hour before kickoff, Sharp Money cards included
            if e.get('backfill') or 'final' in e: continue
            if 0 < e['kick'] - now <= LOCK_SECS or e['kick'] <= now:
                at = int(now) if e['kick'] > now else e.get('logged', int(now))      # a game that started before any run fell in its last hour keeps the last pre-kickoff state
                e['final'] = dict(side=e['side'], team=e['team'], entry=e['entry'], edge=e['edge'], is_pick=bool(e['is_pick']), at=at, mins_before=max(0, round((e['kick'] - at) / 60)),
                                  cards=e.get('cards'), line_src=e.get('line_src'), home_id=e['home_id'], away_id=e['away_id'])
    def _settle(x, key, ids=None):
        if 'result' in x and x.get('settled_by') != 'feed': return           # settled by ESPN's game: final. A feed-settled one is upgraded when ESPN catches up
        r = settle(dict(x, key=key, **(ids or {})), g26, fin)
        if r: x.pop('settled_by', None); x.update(r)
    for e in board:
        _settle(e, e['key'])
        if e.get('final'): _settle(e['final'], e['key'], dict(home_id=e['home_id'], away_id=e['away_id']))
        if e.get('v2'): _settle(e['v2'], e['key'], dict(home_id=e['home_id'], away_id=e['away_id']))
        bo = e.get('bettable_open')
        if bo and 'result' not in bo:
            r = settle(dict(bo, key=e['key'], home_id=e['home_id'], away_id=e['away_id']), g26, fin)
            if r: bo.update({k: r[k] for k in ('result', 'espn_close', 'clv', 'margin', 'hs', 'as_') if k in r})
    board.sort(key=lambda x: -x['kick'])
    for e in log: _settle(e, e['key'])
    gr = [e for e in log if e.get('result') in ('W', 'L', 'P')]
    w = sum(e['result'] == 'W' for e in gr); l = sum(e['result'] == 'L' for e in gr); n = w + l
    clvs = [e['clv'] for e in gr if e.get('clv') is not None]
    summary = dict(picks=len(log), graded=n, won=w, lost=l, pushed=len(gr) - n, expected=round(n * BREAKEVEN, 2),
                   z=round((w - n * BREAKEVEN) / math.sqrt(n * BREAKEVEN * (1 - BREAKEVEN)), 2) if n else None,
                   clv_n=len(clvs), clv_mean=round(sum(clvs) / len(clvs), 2) if clvs else None, clv_pos=round(sum(c > 0 for c in clvs) / len(clvs), 3) if clvs else None)
    # context for the page: how the same model (every game, side = whichever way it leans) did vs ESPN's line in the earlier weeks of this season
    earlier = [0, 0]; first = min([b['week'] for b in board], default=None)
    if first:
        for wk in range(PICK_MIN_WEEK - 1, first):
            ra_w, rb_w = rated_before(wk)
            for r in g26[(g26.week == wk) & (g26.status_type_completed == True)].itertuples():
                h, aw = int(r.homeTeamId), int(r.awayTeamId)
                if h not in F or aw not in F or pd.isna(r.homeTeamSpread): continue
                pred = K * ((ra_w.get(h, 0) - rb_w.get(h, 0)) - (ra_w.get(aw, 0) - rb_w.get(aw, 0))) + (0.0 if r.neutral_site == True else HFA)
                c = (1 if pred - r.homeTeamSpread > 0 else -1) * ((r.homeFinalScore - r.awayFinalScore) - r.homeTeamSpread)
                earlier[0 if c > 0 else 1] += c != 0 and 1 or 0
    def _rec(rows):
        w = sum(r == 'W' for r in rows); l = sum(r == 'L' for r in rows); return [w, l]
    gb = [e for e in board if e.get('v2') and e['v2'].get('result') in ('W', 'L')]
    v2_summary = dict(games=len(board), graded=len(gb),
                      v1_all=_rec([e['result'] for e in gb if e.get('result')]), v2_all=_rec([e['v2']['result'] for e in gb]),
                      v1_picks=_rec([e['result'] for e in gb if e.get('is_pick') and e.get('result')]), v2_picks=_rec([e['v2']['result'] for e in gb if e['v2']['is_pick']])) if prior2 else None
    cards_summary = tile_cards_summary(board)
    logkeys = {x['key']: x for x in log}
    fg = [e for e in board if e.get('final') and e['final'].get('result') in ('W', 'L')]
    def _fs(sel, get=lambda e: e['final']['result']):
        w = sum(get(e) == 'W' for e in sel); return [w, sum(get(e) in ('W', 'L') for e in sel) - w]
    def _link(e):
        c = e['final'].get('cards')
        if c is None: return 'nocard'
        m, o = c[e['final']['side']], c['away' if e['final']['side'] == 'home' else 'home']
        return 'with' if m and not o else 'against' if o and not m else 'split' if m and o else 'none'
    fp = [e for e in fg if e['final']['is_pick']]
    final_summary = dict(locked=sum(1 for e in board if e.get('final')), graded=len(fg), mins=[e['final']['mins_before'] for e in board if e.get('final')][:0],
        rows=[dict(label='Still a pick when locked', note='A first-sight pick that was still 5+ points from the market an hour before kickoff, graded at the locked line.', all=_fs([e for e in fp if e['key'] in logkeys]), keys=[e['key'] for e in fp if e['key'] in logkeys]),
              dict(label='Dropped under 5 points by the lock', note='Logged as a pick, but the gap closed before kickoff. Graded at the first-sight line, as in the official record.', all=_fs([logkeys[e['key']] for e in fg if e['key'] in logkeys and not e['final']['is_pick']], lambda x: x['result']), keys=[e['key'] for e in fg if e['key'] in logkeys and not e['final']['is_pick']]),
              dict(label='Became a pick in the last hour', note='Under 5 points when first seen, 5+ at the lock.', all=_fs([e for e in fp if e['key'] not in logkeys]), keys=[e['key'] for e in fp if e['key'] not in logkeys]),
              dict(label='Locked picks with Sharp Money on their side', note='At the lock the model is 5+ points off and a card is on its team and none on the other.', all=_fs([e for e in fp if _link(e) == 'with']), keys=[e['key'] for e in fp if _link(e) == 'with']),
              dict(label='Locked picks with Sharp Money against them', note='Cards only on the other team.', all=_fs([e for e in fp if _link(e) == 'against']), keys=[e['key'] for e in fp if _link(e) == 'against']),
              dict(label='Locked picks, Sharp Money split or quiet', note='Cards on both teams, or no card at all.', all=_fs([e for e in fp if _link(e) in ('split', 'none', 'nocard')]), keys=[e['key'] for e in fp if _link(e) in ('split', 'none', 'nocard')])])
    final_summary.pop('mins')
    open_chk = open_check(g26, F, rated_before, K, HFA)
    bos = [e['bettable_open'] for e in board if e.get('bettable_open')]
    bg = [b for b in bos if b.get('result') in ('W', 'L')]
    bclv = [b['clv'] for b in bos if b.get('clv') is not None and b.get('result') in ('W', 'L', 'P')]
    bettable_summary = dict(stamped=len(bos), graded=len(bg), won=sum(b['result'] == 'W' for b in bg), lost=sum(b['result'] == 'L' for b in bg),
                            clv_n=len(bclv), clv_mean=round(sum(bclv) / len(bclv), 2) if bclv else None,
                            note='Stamped the first time the model sees a game, at the line on the board then. Games already on the board are not backfilled, and a line that moved later is not written back onto them.')
    for s_ in slate: s_.pop('seen', None)     # the live slate does not need the book row the stamp was copied from
    backtest = json.load(open(BACKTEST)) if os.path.exists(BACKTEST) else None
    json.dump(dict(generated=pd.Timestamp.now('UTC').isoformat(), season=2026, through_week=through, games_rated=len(done), params=dict(S=S, K=K, HFA=HFA, ALPHA=st.ALPHA),
                   unmatched_games=un, backtest=backtest, ratings=ratings, slate=slate, board=board, v2_summary=v2_summary, cards_summary=cards_summary, final_summary=final_summary, earlier_weeks=dict(first=PICK_MIN_WEEK - 1, last=(first or 0) - 1, record=earlier), log=log, log_summary=summary, open_check=open_chk, bettable_open=bettable_summary), open(OUT, 'w'))
    print(json.dumps(dict(through_week=through, rated=len(ratings), slate=len(slate), unmatched=un, log=summary)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['priors', 'priors-v2', 'update']); ap.add_argument('--dir', default=os.path.join(tempfile.gettempdir(), 'cfbmodel'))
    ap.add_argument('--since', type=int, help='one-time backfill: also project games that kicked off at or after this unix time, entered at the opening line')
    ap.add_argument('--until', type=int, help='with --since: stop the backfill before this unix time')
    ap.add_argument('--sharp', help='path to the Sharp Money data.json (sharp-data branch)'); a = ap.parse_args()
    {'priors': cmd_priors, 'priors-v2': cmd_priors_v2, 'update': cmd_update}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
