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
import argparse, json, math, os, sys, tempfile
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
PRIORS = os.path.join(DATA, 'cfb_model_priors.json')
BACKTEST = os.path.join(DATA, 'cfb_model_backtest.json')
OUT = os.path.join(DATA, 'cfb_model.json')
PICK_EDGE = 5.0          # disagree with the market by at least this many points
PICK_MIN_WEEK = 4        # the first month is dominated by the prior, which has no talent or portal information
BREAKEVEN = 110 / 210
FBS_ADDITIONS = {16}      # teams new to FBS this season (ESPN ids), added each offseason: 2026 = Sacramento State


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
    json.dump(dict(generated=pd.Timestamp.now('UTC').isoformat(), method='walk-forward, ESPN spread as the market line, FBS vs FBS regular season',
                   tuned_on='2022-2023', test='2024-2025', pick_edge=PICK_EDGE, min_week=PICK_MIN_WEEK, seasons=seasons,
                   combined=dict(picks_wk4=rec(allw, PICK_EDGE), picks3_wk4=rec(allw, 3), picks7_wk4=rec(allw, 7))),
              open(BACKTEST, 'w'), indent=1)
    print(json.dumps(json.load(open(BACKTEST))['combined']))


def grade(entry, g26):
    """grade one logged pick against a finished 2026 game; returns dict of result fields"""
    m = g26[(g26.homeTeamId == entry['home_id']) & (g26.awayTeamId == entry['away_id'])]
    if m.empty or not bool(m.iloc[0].status_type_completed): return {}
    x = m.iloc[0]; home = entry['side'] == 'home'
    margin = (x.homeFinalScore - x.awayFinalScore) * (1 if home else -1)
    close = None if pd.isna(x.homeTeamSpread) else (-x.homeTeamSpread if home else x.homeTeamSpread)
    res = 'W' if margin + entry['entry'] > 0 else 'L' if margin + entry['entry'] < 0 else 'P'
    return dict(result=res, hs=int(x.homeFinalScore), as_=int(x.awayFinalScore), margin=int(margin), espn_close=close, clv=None if close is None else round(entry['entry'] - close, 1))


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
    cache = {}
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
    slate, un = [], 0
    if a.sharp and os.path.exists(a.sharp):
        feed = json.load(open(a.sharp)); now = feed['ts']
        for g in feed['games']:
            if g['sport'] != 'cfb': continue
            started = g['start'] <= now
            if started and not (a.since and g['start'] >= a.since): continue
            h, aw = find_id(g['home']['name']), find_id(g['away']['name'])
            line = ((g.get('pin') or {}).get('sp') or {}).get('line')
            if line is None: line = ((g.get('consensus') or {}).get('sp') or {}).get('line')
            oline = ((g.get('open') or {}).get('sp') or {}).get('line')
            if started: line = oline          # in-game lines are live, so a backfilled game uses its opening line
            gr_ = gidx.get((h, aw)) if h is not None else None
            if h is None or aw is None or h not in F or aw not in F or line is None:
                un += 1; continue
            wk = int(gr_.week) if gr_ is not None else through; neutral = bool(gr_ is not None and gr_.neutral_site == True)
            ra_w, rb_w = rated_before(wk)
            Pw = lambda t: ra_w.get(t, 0.0) - rb_w.get(t, 0.0)
            pred = K * (Pw(h) - Pw(aw)) + (0.0 if neutral else HFA)
            mkt = -line
            edge = pred - mkt
            pick = None
            if abs(edge) >= PICK_EDGE and wk >= PICK_MIN_WEEK:
                side = 'home' if edge > 0 else 'away'
                pick = dict(side=side, team=g['home' if side == 'home' else 'away']['short'], line=line if side == 'home' else -line)
            slate.append(dict(key=g['key'], kick=g['start'], home=g['home']['short'], away=g['away']['short'], home_id=h, away_id=aw, week=wk, neutral=neutral,
                              backfill=started, model_margin=round(pred, 1), market_margin=round(mkt, 1), open_margin=None if oline is None else round(-oline, 1),
                              edge=round(edge, 1), pick=pick))
        slate.sort(key=lambda x: (x['kick'], -abs(x['edge'])))
    else: now = int(pd.Timestamp.now('UTC').timestamp())

    # the pick log: every pick logged once, before kickoff, at the line we saw; graded when the game ends
    log = []
    if os.path.exists(OUT):
        try: log = json.load(open(OUT)).get('log', [])
        except Exception: log = []
    have = {e['key'] for e in log}
    for s in slate:
        if s['pick'] and s['key'] not in have and (s['kick'] > now or s['backfill']):
            log.append(dict(key=s['key'], week=s['week'], kick=s['kick'], home=s['home'], away=s['away'], home_id=s['home_id'], away_id=s['away_id'],
                            side=s['pick']['side'], team=s['pick']['team'], entry=s['pick']['line'], model_margin=s['model_margin'],
                            market_margin=s['market_margin'], edge=s['edge'], logged=int(now), backfill=s['backfill'], neutral=s['neutral']))
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
        if old and (old['kick'] <= now or old.get('backfill')): continue
        side = 'home' if s_['edge'] > 0 else 'away'
        ent = dict(s_, side=side, team=s_['home'] if side == 'home' else s_['away'],
                   entry=round(-s_['market_margin'] if side == 'home' else s_['market_margin'], 1), logged=int(now),
                   is_pick=bool(s_['pick']))
        if old: bidx[s_['key']].update(ent)
        else: board.append(ent); bidx[s_['key']] = ent
    for e in board:
        if 'result' not in e: e.update(grade(e, g26))
    board.sort(key=lambda x: -x['kick'])
    for e in log:
        if 'result' not in e: e.update(grade(e, g26))
    gr = [e for e in log if e.get('result') in ('W', 'L', 'P')]
    w = sum(e['result'] == 'W' for e in gr); l = sum(e['result'] == 'L' for e in gr); n = w + l
    clvs = [e['clv'] for e in gr if e.get('clv') is not None]
    summary = dict(picks=len(log), graded=n, won=w, lost=l, pushed=len(gr) - n, expected=round(n * BREAKEVEN, 2),
                   z=round((w - n * BREAKEVEN) / math.sqrt(n * BREAKEVEN * (1 - BREAKEVEN)), 2) if n else None,
                   clv_mean=round(sum(clvs) / len(clvs), 2) if clvs else None, clv_pos=round(sum(c > 0 for c in clvs) / len(clvs), 3) if clvs else None)
    backtest = json.load(open(BACKTEST)) if os.path.exists(BACKTEST) else None
    json.dump(dict(generated=pd.Timestamp.now('UTC').isoformat(), season=2026, through_week=through, games_rated=len(done), params=dict(S=S, K=K, HFA=HFA, ALPHA=st.ALPHA),
                   unmatched_games=un, backtest=backtest, ratings=ratings, slate=slate, board=board, log=log, log_summary=summary), open(OUT, 'w'))
    print(json.dumps(dict(through_week=through, rated=len(ratings), slate=len(slate), unmatched=un, log=summary)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['priors', 'update']); ap.add_argument('--dir', default=os.path.join(tempfile.gettempdir(), 'cfbmodel'))
    ap.add_argument('--since', type=int, help='one-time backfill: also project games that kicked off at or after this unix time, entered at the opening line')
    ap.add_argument('--sharp', help='path to the Sharp Money data.json (sharp-data branch)'); a = ap.parse_args()
    {'priors': cmd_priors, 'update': cmd_update}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
