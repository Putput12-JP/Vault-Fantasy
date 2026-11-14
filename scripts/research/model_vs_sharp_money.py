#!/usr/bin/env python3
"""Is there a connection between Vault's game models and sharp money, and does it matter for results?

Research only. Nothing here feeds a model, a gate, Top Reads, SM_GATE or an agree total.

Two lenses, per sport, each sharp-money family on its own (never pooled into one score):

  1. SIGNAL LENS. Every Sharp Money alert logged before kickoff (first alert per game, market, side and family).
     For each one we ask what the model said about that market at the alert's OWN line, then split the alert's
     graded result by agree / disagree. Measures: W-L, win% minus the fair probability logged with the alert,
     flat ROI at the stored price (exchange price or US-book price) with a game-clustered bootstrap CI, and mean
     CLV (stored close minus stored fair).
  2. MODEL LENS. The model's own pre-kickoff side on every game it logged live (not backfilled), split by whether
     each family backed the model's team, the other team, both, or neither before kickoff. Measures: the model's
     graded ATS / winner / total record, flat ROI where a price is stored (NBA only), CLV in points where stored.
  Plus: Top Reads (graded bet reads) with the model side the poller stamped when it first saw the read, kept only
  when that stamp is before kickoff; and the proven-sharps side cards (pm_record on pm-holders-data).

Point in time:
  - Model: NFL / CFB board rows with backfill false (the board row is overwritten every run until kickoff, so it is
    the last pre-kick model output, and `logged` < kick is checked). CFB totals rows with backfill false.
    NBA game_picks rows with src 'live' (the 'c' clock is the last row before tip; 'f' is the first sighting).
  - Alerts: ts < start. Top Reads: model stamp `at` < start.
No refit, no estimated price, no estimated close.

Usage: python3 scripts/research/model_vs_sharp_money.py [--state state.json] [--out docs/research/model-vs-sharp-money.json]
"""
import argparse, collections, json, math, os, random, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_state, ROOT  # noqa: E402

D = lambda *p: os.path.join(ROOT, *p)
FAMILIES = {
    'sharp': 'Proven sharp accounts (Polymarket, record-qualified)',
    'cross': 'Sharp-account net position vs the crowd',
    'whale': 'Big tickets on exchanges (no record filter)',
    'steam': 'Pinnacle line move (steam)',
    'split': 'Money share above ticket share (handle split)',
    'behind': 'US book behind Pinnacle (+EV price)',
}
TEAM = ('sp', 'ml')
NET = ('sharp', 'whale')                           # wallet families also get a net-dollar side per game in the model lens
LENS_FAMS = list(FAMILIES) + [f + '_net' for f in NET]
NBA_AB = {'NYK': 'NY', 'GSW': 'GS', 'SAS': 'SA', 'NOP': 'NO', 'UTA': 'UTAH', 'WAS': 'WSH', 'BRK': 'BKN', 'PHO': 'PHX'}
BUCKETS = [(0, 1.5), (1.5, 3), (3, 5), (5, 1e9)]
B = 2000
RNG = random.Random(20261112)


def jl(p):
    return json.load(open(p))


def git_json(ref):
    return json.loads(subprocess.run(['git', '-C', ROOT, 'show', ref], capture_output=True, check=True).stdout)


def git_jsonl(ref):
    r = subprocess.run(['git', '-C', ROOT, 'show', ref], capture_output=True)
    return [json.loads(x) for x in r.stdout.decode().splitlines() if x.strip()] if r.returncode == 0 else []


def am_profit(price, won):
    if not won:
        return -1.0
    return price / 100 if price > 0 else 100 / -price


def wilson(w, n, z=1.96):
    if not n:
        return None
    p = w / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def boot_roi(rows):
    """Flat 1u ROI over rows carrying 'pl' (profit per 1u at a stored price), CI by resampling GAMES (rows in one game move together)."""
    pr = [r for r in rows if r.get('pl') is not None]
    if not pr:
        return None, None, 0
    by = collections.defaultdict(list)
    for r in pr:
        by[r['g']].append(r['pl'])
    gs = list(by.values())
    roi = sum(map(sum, gs)) / len(pr)
    if len(gs) < 5:
        return round(roi, 3), None, len(pr)
    sims = []
    for _ in range(B):
        s = n = 0
        for _ in range(len(gs)):
            x = gs[RNG.randrange(len(gs))]
            s += sum(x); n += len(x)
        sims.append(s / n)
    sims.sort()
    return round(roi, 3), [round(sims[int(.025 * B)], 3), round(sims[int(.975 * B)], 3)], len(pr)


def pack(rows):
    w = sum(r['res'] > 0 for r in rows); l = sum(r['res'] < 0 for r in rows); n = w + l
    fw = [r for r in rows if r['res'] != 0 and r.get('fair') is not None]
    roi, ci, rn = boot_roi([r for r in rows if r['res'] != 0 or r.get('pl') is not None])
    cl = [r['clv'] for r in rows if isinstance(r.get('clv'), (int, float))]
    r3 = lambda x: None if x is None else round(x, 3)
    return dict(n=len(rows), games=len({r['g'] for r in rows}), w=w, l=l, p=len(rows) - n, win=r3(w / n) if n else None, win_ci=wilson(w, n),
                vs_fair=r3(sum(r['res'] > 0 for r in fw) / len(fw) - sum(r['fair'] for r in fw) / len(fw)) if fw else None, fair_n=len(fw),
                roi=roi, roi_ci=ci, roi_n=rn, clv=r3(sum(cl) / len(cl)) if cl else None, clv_n=len(cl))


def diff_ci(a, b):
    """Bootstrap CI on agree minus disagree, resampling games within each group. The measure is win minus the logged fair probability
    on the rows that store a fair (so a group of favourites does not look better just for being favourites), else raw win%."""
    dec = [r for r in a + b if r['res'] != 0]
    use_fair = bool(dec) and any(r.get('fair') is not None for r in dec)
    use_pl = not use_fair and bool(dec) and all(r.get('pl') is not None for r in dec)
    if use_fair:                                  # rows without a stored fair are left out of this comparison (never filled in)
        a = [r for r in a if r.get('fair') is not None]; b = [r for r in b if r.get('fair') is not None]
    def games(rows):
        by = collections.defaultdict(list)
        for r in rows:
            if r['res'] != 0:
                by[r['g']].append(r['pl'] if use_pl else (1 if r['res'] > 0 else 0) - (r['fair'] if use_fair else 0))
        return list(by.values())
    ga, gb = games(a), games(b)
    if len(ga) < 5 or len(gb) < 5:
        return None
    def rate(gs):
        s = n = 0
        for _ in range(len(gs)):
            x = gs[RNG.randrange(len(gs))]; s += sum(x); n += len(x)
        return s / n
    sims = sorted(rate(ga) - rate(gb) for _ in range(B))
    pa = sum(map(sum, ga)) / sum(map(len, ga)); pb = sum(map(sum, gb)) / sum(map(len, gb))
    return dict(measure='win minus fair' if use_fair else 'ROI at stored price' if use_pl else 'win %', diff=round(pa - pb, 3), ci=[round(sims[int(.025 * B)], 3), round(sims[int(.975 * B)], 3)])


# ------------------------------------------------------------------ model sides (point in time)
def nba_key(lbl):
    a, h = [NBA_AB.get(x.strip(), x.strip()) for x in lbl.split(' @ ')]
    return a, h


def load_models():
    nfl, cfb = jl(D('data', 'nfl_model.json')), jl(D('data', 'cfb_model.json'))
    M = {}
    skipped = collections.Counter()
    for sp, b in (('nfl', nfl['board']), ('cfb', cfb['board'])):
        for r in b:
            if r.get('backfill') or not (r.get('logged') and r['logged'] < r['kick']):
                skipped[sp] += 1
                continue
            res = {'W': 1, 'L': -1, 'P': 0}.get(r.get('result'))
            M[r['key']] = dict(sport=sp, kick=r['kick'], mm=r['model_margin'], ats_side=r['side'], ats_edge=abs(r['edge']), ats_res=res,
                               ats_clv=r.get('clv'), open_m=r.get('open_margin'), last_m=r.get('market_margin'), game_id=r.get('game_id'),
                               home=r['home'], away=r['away'], is_pick=bool(r.get('is_pick')))
    # CFB totals: live rows only, model total vs the stored open, graded vs that open
    tot = {}
    for r in cfb['totals']['rows']:
        if r.get('backfill') or r.get('model_total') is None:
            continue
        tot[r['game_id']] = dict(mt=r['model_total'], side=r['side'], edge=abs(r['edge']) if r.get('edge') is not None else None,
                                 res={'W': 1, 'L': -1, 'P': 0}.get(r.get('result')), clv=r.get('clv'))
    for k, m in M.items():
        if m['sport'] == 'cfb' and m.get('game_id') in tot:
            m['tot'] = tot[m['game_id']]
    # NBA game picks, live rows only
    gp = jl(D('nba', 'data', 'game_picks.json'))
    C = gp['cols']; ix = {c: i for i, c in enumerate(C)}
    nba = {}
    for day, dd in gp['days'].items():
        for gid, g in dd['games'].items():
            nba.setdefault(gid, dict(lbl=g[0], tip=g[1], away=NBA_AB.get(g[2], g[2]), home=NBA_AB.get(g[3], g[3])))
        for row in dd['rows']:
            if row[ix['src']] != 'live':
                skipped['nba'] += 1
                continue
            nba[row[0]][row[ix['clock']]] = {c: row[i] for c, i in ix.items()}
    nba = {k: v for k, v in nba.items() if 'c' in v and 'f' in v}
    return M, nba, skipped


def nba_profit(px, won):
    if px is None:
        return None
    return am_profit(int(px), won)


# ------------------------------------------------------------------ joins
def join_nba(alerts_or_picks, nba):
    idx = collections.defaultdict(list)
    for gid, g in nba.items():
        idx[(g['away'], g['home'])].append((g['tip'], gid))
    out = {}
    for a in alerts_or_picks:
        if a['sport'] != 'nba' or a['game'] in out:
            continue
        try:
            k = nba_key(a['gameLbl'])
        except ValueError:
            continue
        c = [gid for tip, gid in idx.get(k, []) if abs(tip - a['start']) < 6 * 3600]
        if len(c) == 1:
            out[a['game']] = c[0]
    return out


def model_view(a, M, nba, nbamap):
    """Model side for the alert's market at the alert's own line -> (side, edge pts) or None."""
    sp, m = a['sport'], a['m']
    if sp == 'nba':
        g = nba.get(nbamap.get(a['game']))
        if not g:
            return None
        c = g['c']
        if m in ('sp', 'ml'):
            if a.get('hline') is None or c['margin'] is None:
                return None
            e = c['margin'] + a['hline']
            return None if e == 0 else ('home' if e > 0 else 'away', abs(e))
        if m == 'tot':
            if a.get('line') is None or c['total'] is None:
                return None
            e = c['total'] - a['line']
            return None if e == 0 else ('over' if e > 0 else 'under', abs(e))
        return None
    g = M.get(a['game'])
    if not g:
        return None
    if m in ('sp', 'ml'):                     # moneyline too: the model's value side vs the market's spread at the alert, not its winner
        if a.get('hline') is None:
            return None
        e = g['mm'] + a['hline']
        return None if e == 0 else ('home' if e > 0 else 'away', abs(e))
    if m == 'tot' and g.get('tot') and a.get('line') is not None:
        e = g['tot']['mt'] - a['line']
        return None if e == 0 else ('over' if e > 0 else 'under', abs(e))
    return None


def alert_pl(a):
    if a.get('result') is None or not (a.get('px') or a.get('price')):
        return None
    if a['result'] == 0:
        return 0.0
    won = a['result'] > 0
    if a.get('px'):
        return (1 - a['px']) / a['px'] if won else -1.0
    if a.get('price'):
        return am_profit(a['price'], won)
    return None


def bucket(e):
    for lo, hi in BUCKETS:
        if lo <= e < hi:
            return f'{lo:g}-{hi:g}' if hi < 1e8 else f'{lo:g}+'


# ------------------------------------------------------------------ 1. signal lens
def signal_lens(state, M, nba, nbamap):
    seen = set(); rows = []
    for a in sorted(state['alerts'], key=lambda x: x['ts']):
        if a['type'] not in FAMILIES or a.get('result') is None or a['ts'] >= a['start']:
            continue
        k = (a['game'], a['m'], a['side'], a['type'])
        if k in seen:
            continue
        seen.add(k)
        mv = model_view(a, M, nba, nbamap)
        rows.append(dict(sport=a['sport'], fam=a['type'], m=a['m'], g=a['game'], res=a['result'], fair=a.get('fair'), clv=a.get('clv'),
                         pl=alert_pl(a), model=None if mv is None else ('agree' if mv[0] == a['side'] else 'disagree'),
                         edge=None if mv is None else mv[1]))
    out = {}
    for sp in ('nfl', 'cfb', 'nba'):
        out[sp] = {}
        for f in FAMILIES:
            R = [r for r in rows if r['sport'] == sp and r['fam'] == f]
            if not R:
                continue
            J = [r for r in R if r['model']]
            ag = [r for r in J if r['model'] == 'agree']; dg = [r for r in J if r['model'] == 'disagree']
            byb = {}
            for r in J:
                byb.setdefault(bucket(r['edge']), [0, 0])[0 if r['model'] == 'agree' else 1] += 1
            out[sp][f] = dict(
                alerts=len(R), with_model=len(J),
                agree_rate=round(len(ag) / len(J), 3) if J else None, agree_rate_ci=wilson(len(ag), len(J)),
                agree_by_model_edge={b: dict(agree=v[0], disagree=v[1], rate=round(v[0] / sum(v), 3)) for b, v in sorted(byb.items(), key=lambda t: float(t[0].split('-')[0].rstrip('+')))},
                by_market={m: dict(n=len(x), agree=sum(r['model'] == 'agree' for r in x)) for m in ('sp', 'ml', 'tot') for x in [[r for r in J if r['m'] == m]] if x},
                all=pack(R), agree=pack(ag), disagree=pack(dg), no_model=pack([r for r in R if not r['model']]),
                agree_minus_disagree_win=diff_ci(ag, dg),
                agree_model_3plus=pack([r for r in ag if r['edge'] >= 3]), disagree_model_3plus=pack([r for r in dg if r['edge'] >= 3]))
    return out, rows


# ------------------------------------------------------------------ 2. model lens
def team_sides(state, nbamap):
    """(game) -> family -> set of home/away the family backed on spread or moneyline before kickoff."""
    S = collections.defaultdict(lambda: collections.defaultdict(set))
    T = collections.defaultdict(lambda: collections.defaultdict(set))
    usd = collections.defaultdict(lambda: collections.defaultdict(float))
    for a in state['alerts']:
        if a['type'] not in FAMILIES or a['ts'] >= a['start']:
            continue
        g = nbamap.get(a['game'], a['game']) if a['sport'] == 'nba' else a['game']
        if a['m'] in TEAM:
            S[g][a['type']].add(a['side'])
            if a['type'] in NET and a.get('usd'):
                usd[(g, a['type'])][a['side']] += a['usd']
        elif a['m'] == 'tot':
            T[g][a['type']].add(a['side'])
    for (g, f), d in usd.items():                 # net dollars: the side with more logged money (spread + moneyline) before kickoff
        if len(d) == 1 or d.get('home', 0) != d.get('away', 0):
            S[g][f + '_net'].add(max(d, key=d.get))
    return S, T


def rel(sides, mine):
    if not sides:
        return 'none'
    if len(sides) > 1:
        return 'both'
    return 'agree' if mine in sides else 'disagree'


def model_lens(state, M, nba, nbamap):
    S, T = team_sides(state, nbamap)
    out = {}
    # NFL / CFB ATS (graded at the last pre-kick line the board saw; no price stored, so W-L and CLV pts only)
    for sp in ('nfl', 'cfb'):
        G = [(k, g) for k, g in M.items() if g['sport'] == sp and g['ats_res'] is not None]
        base = [dict(g=k, res=g['ats_res'], clv=g['ats_clv']) for k, g in G]
        fam = {}
        for f in LENS_FAMS:
            grp = collections.defaultdict(list)
            for k, g in G:
                grp[rel(S[k][f], g['ats_side'])].append(dict(g=k, res=g['ats_res'], clv=g['ats_clv'], pick=g['is_pick']))
            fam[f] = {r: pack(v) for r, v in grp.items()}
            fam[f]['agree_minus_disagree_win'] = diff_ci(grp['agree'], grp['disagree'])
            sided = len(grp['agree']) + len(grp['disagree'])
            fam[f]['agree_rate'] = round(len(grp['agree']) / sided, 3) if sided else None
            fam[f]['agree_rate_ci'] = wilson(len(grp['agree']), sided)
        # market move: stored open -> last pre-kick line (the feed's open, not Pinnacle's)
        grp = collections.defaultdict(list)
        for k, g in G:
            if g['open_m'] is None or g['last_m'] is None or g['last_m'] == g['open_m']:
                grp['none'].append(dict(g=k, res=g['ats_res'], clv=g['ats_clv'])); continue
            to = 'home' if g['last_m'] > g['open_m'] else 'away'
            grp['agree' if to == g['ats_side'] else 'disagree'].append(dict(g=k, res=g['ats_res'], clv=g['ats_clv']))
        mv = {r: pack(v) for r, v in grp.items()}
        mv['agree_minus_disagree_win'] = diff_ci(grp['agree'], grp['disagree'])
        sided = len(grp['agree']) + len(grp['disagree'])
        mv['agree_rate'] = round(len(grp['agree']) / sided, 3) if sided else None
        mv['agree_rate_ci'] = wilson(len(grp['agree']), sided)
        fam['line_move_open_to_last'] = mv
        out[sp] = dict(ats_all=pack(base), ats_by_family=fam, price_note='No price is stored on NFL/CFB board rows, so no ROI; CLV is points (close minus entry).')
        if sp == 'cfb':
            TT = [(k, g['tot']) for k, g in M.items() if g['sport'] == 'cfb' and g.get('tot') and g['tot']['res'] is not None]
            tf = {}
            for f in FAMILIES:
                grp = collections.defaultdict(list)
                for k, t in TT:
                    grp[rel(T[k][f], t['side'])].append(dict(g=k, res=t['res'], clv=t['clv']))
                tf[f] = {r: pack(v) for r, v in grp.items()}
                tf[f]['agree_minus_disagree_win'] = diff_ci(grp['agree'], grp['disagree'])
            out[sp]['totals_all'] = pack([dict(g=k, res=t['res'], clv=t['clv']) for k, t in TT])
            out[sp]['totals_by_family'] = tf
    # NBA: ATS and winner, both clocks, with stored prices and CLV
    res = {'W': 1, 'L': -1, 'P': 0}
    nb = {}
    for clock in ('f', 'c'):
        for mk, side_c, res_c, px_c, clv_c in (('ats', 'ats_side', 'ats_res', 'ats_px', 'clv_pts'), ('winner', 'ml_side', 'ml_res', 'ml_px', 'clv_p')):
            base = []; grp = {f: collections.defaultdict(list) for f in LENS_FAMS}
            for gid, g in nba.items():
                r = g[clock]
                if r.get(res_c) not in res or r.get(side_c) not in ('H', 'A'):
                    continue
                mine = 'home' if r[side_c] == 'H' else 'away'
                won = res[r[res_c]]
                row = dict(g=gid, res=won, pl=0.0 if won == 0 else nba_profit(r.get(px_c), won > 0),
                           clv=g['c'].get(clv_c) if clock == 'f' else None)   # stored on the close row: close minus first
                base.append(row)
                for f in LENS_FAMS:
                    grp[f][rel(S[gid][f], mine)].append(row)
            fam = {}
            for f in LENS_FAMS:
                fam[f] = {k: pack(v) for k, v in grp[f].items()}
                fam[f]['agree_minus_disagree_win'] = diff_ci(grp[f]['agree'], grp[f]['disagree'])
                sided = len(grp[f]['agree']) + len(grp[f]['disagree'])
                fam[f]['agree_rate'] = round(len(grp[f]['agree']) / sided, 3) if sided else None
                fam[f]['agree_rate_ci'] = wilson(len(grp[f]['agree']), sided)
            nb[f'{mk}_{clock}'] = dict(all=pack(base), by_family=fam)
    nb['clock_note'] = "'f' is the model's first sighting (the published record, CLV stored); 'c' is the last row before tip (no CLV, it is the close)."
    out['nba'] = nb
    return out


# ------------------------------------------------------------------ 3. Top Reads (graded bet reads, poller's model stamp)
def top_reads(state):
    BET = {'line', 'money', 'behind'}
    sides = collections.defaultdict(set)
    for p in state['picks'].values():
        sides[(p['game'], p['m'])].add(p['side'])
    out = {}
    rows = []
    for p in state['picks'].values():
        if p.get('result') is None or not (set(p.get('kinds') or []) & BET):
            continue
        if len(sides[(p['game'], p['m'])]) > 1:
            continue
        m = p.get('model')
        pit = bool(m and m.get('at') is not None and m['at'] < p['start'])
        st = 'none' if not m else ('agree' if m['side'] == p['side'] else 'disagree')
        pl = None
        if p['result'] == 0:
            pl = 0.0
        elif p.get('price'):
            pl = am_profit(p['price'], p['result'] > 0)
        rows.append(dict(sport=p['sport'], g=p['game'], res=p['result'], fair=p.get('fair'), clv=p.get('clv'), pl=pl, model=st, pit=pit))
    for sp in ('nfl', 'cfb', 'nba'):
        R = [r for r in rows if r['sport'] == sp]
        P = [r for r in R if r['pit']]
        ag = [r for r in P if r['model'] == 'agree']; dg = [r for r in P if r['model'] == 'disagree']
        out[sp] = dict(graded=len(R), point_in_time=len(P), dropped_stamp_after_kick_or_missing=len(R) - len(P),
                       agree_rate=round(len(ag) / len(P), 3) if P else None, agree_rate_ci=wilson(len(ag), len(P)),
                       agree=pack(ag), disagree=pack(dg), agree_minus_disagree_win=diff_ci(ag, dg))
    return out


# ------------------------------------------------------------------ 4. proven-sharps side cards
def side_cards(nba, nbamap_unused):
    out = {}
    for sp in ('cfb', 'nba', 'nfl'):
        rows = git_jsonl(f'origin/pm-holders-data:pm_record/cards/{sp}/2026-11.jsonl')
        res = [r for r in rows if r.get('kind') == 'result' and r.get('status') == 'graded' and r.get('counts')]
        out[sp] = dict(graded_plays=len(res), w=sum(r.get('res') == 'win' for r in res), l=sum(r.get('res') == 'loss' for r in res),
                       note='Side cards started 2026-11-11; far too few to compare with the model.')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state')
    ap.add_argument('--out', default=D('docs', 'research', 'model-vs-sharp-money.json'))
    a = ap.parse_args()
    state = load_state(a.state)
    M, nba, skipped = load_models()
    nbamap = join_nba(state['alerts'], nba)
    sig, rows = signal_lens(state, M, nba, nbamap)
    ts = [x['ts'] for x in state['alerts']]
    out = dict(
        generated_from=dict(alerts=len(state['alerts']), alerts_first_ts=min(ts), alerts_last_ts=max(ts),
                            model_games_live=collections.Counter(g['sport'] for g in M.values()), nba_games_live=len(nba),
                            model_rows_skipped_backfill_or_late=dict(skipped), nba_alert_games_joined=len(nbamap)),
        families=FAMILIES,
        signal_lens=sig,
        model_lens=model_lens(state, M, nba, nbamap),
        top_reads=top_reads(state),
        side_cards=side_cards(nba, nbamap),
        method=dict(bootstrap=f'{B} resamples of games (clustered), seed 20261112', roi='flat 1u at the stored price (exchange price as probability, or American)',
                    clv='alerts: stored close minus stored fair (probability); NFL/CFB board: points, stored; NBA: clv_pts / clv_p stored on the first-sighting row'),
    )
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, 'w'), indent=1, default=lambda o: dict(o))
    print('wrote', a.out)


if __name__ == '__main__':
    main()
