#!/usr/bin/env python3
"""Round 4: improve the LIVE model (scripts/build_game_model.py) directly instead of replacing it.

Protocol, to stop the search from fooling itself (rounds 1-3 reused one holdout about 100 times):
  tune 2010-2019  ->  validate 2020-2022 (an idea must beat live on BOTH)  ->  sealed 2023+ (scored once, for the single chosen candidate).
Metric: margin RMSE against the actual result (the live model's own metric, live = 13.003 over 2014+), plus ATS vs the closing spread.

  python3 scripts/explore_nfl_rebuild4.py            # fetches nflverse games.csv
"""
import math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_game_model as M

TUNE, VAL, TEST = (2010, 2019), (2020, 2022), (2023, 9999)
LIVE = dict(K=0.065, KS=0.045, carry=0.72, ridge=0.05, qbm=2.5, qbt=1.25, wS=0.0, kd=0.0, hfa_roll=False, shrink=False, mkt=0.0, qbr=False, KQ=0.03)


def run(games, o):
    rate = defaultdict(float); off = defaultdict(float); dff = defaultdict(float)
    recent = defaultdict(list); season_starts = defaultdict(lambda: defaultdict(int)); gp = defaultdict(int)
    qv = {}                                   # per-QB rating (only when o['qbr'])
    hist = []                                 # (season, margin of non-neutral games) for the rolling HFA
    cur, preds = None, []
    for g in games:
        if g['season'] != cur:
            if cur is not None:
                for t in rate: rate[t] *= o['carry']
                for t in off: off[t] *= o['carry']; dff[t] *= o['carry']
                for k in qv: qv[k] *= 0.85
                gp.clear()
            cur = g['season']
        hb, ab = M.backup_start(recent, g, 'ht', 'hq', season_starts), M.backup_start(recent, g, 'at', 'aq', season_starts)
        if o['hfa_roll']:
            ss = sorted({s for s, _ in hist})[-3:]
            hv = [m for s, m in hist if s in ss]
            hfa_base = statistics.fmean(hv) if len(hv) > 200 else 1.6
        else: hfa_base = 1.455
        hfa = 0.0 if g['neutral'] else hfa_base
        if o['qbr']:
            qadj = (qv.get(g['hq'], -1.0) if g['hq'] else 0.0) - (qv.get(g['aq'], -1.0) if g['aq'] else 0.0)
            pm_rate = rate[g['ht']] - rate[g['at']] + hfa + qadj
        else:
            pm_rate = rate[g['ht']] - rate[g['at']] + hfa - o['qbm'] * (hb - ab)
        own, opp = (o['qbt'] + o['qbm']) / 2, (o['qbm'] - o['qbt']) / 2
        ph = M.BASE_PTS + off[g['ht']] - dff[g['at']] + hfa / 2 - own * hb + opp * ab
        pa = M.BASE_PTS + off[g['at']] - dff[g['ht']] - hfa / 2 - own * ab + opp * hb
        pm = (1 - o['wS']) * pm_rate + o['wS'] * (ph - pa)
        if o['shrink']: pm *= o['shrink']
        if not g['played']: continue
        for tk, qk in (('ht', 'hq'), ('at', 'aq')):
            if g[qk]:
                recent[g[tk]] = (recent[g[tk]] + [g[qk]])[-M.QB_WINDOW:]
                season_starts[(g['season'], g[tk])][g[qk]] += 1
        res = g['hs'] - g['as_']
        preds.append(dict(pm=pm, result=res, spread=g['spread'], season=g['season'], ht=g['ht'], at=g['at'], week=g['week']))
        em = res - pm_rate
        kh = o['K'] * (1 + o['kd'] / (1 + gp[g['ht']])); ka = o['K'] * (1 + o['kd'] / (1 + gp[g['at']]))
        rate[g['ht']] += kh * em; rate[g['at']] -= ka * em
        if o['qbr']:
            if g['hq']: qv[g['hq']] = qv.get(g['hq'], -1.0) + o['KQ'] * em
            if g['aq']: qv[g['aq']] = qv.get(g['aq'], -1.0) - o['KQ'] * em
        eh, ea = g['hs'] - ph, g['as_'] - pa
        off[g['ht']] += o['KS'] * (eh - o['ridge'] * off[g['ht']]); dff[g['at']] -= o['KS'] * (eh - o['ridge'] * dff[g['at']])
        off[g['at']] += o['KS'] * (ea - o['ridge'] * off[g['at']]); dff[g['ht']] -= o['KS'] * (ea - o['ridge'] * dff[g['ht']])
        if o['mkt'] and g['spread'] is not None:
            ex = g['spread'] - pm_rate
            rate[g['ht']] += o['mkt'] * ex; rate[g['at']] -= o['mkt'] * ex
        gp[g['ht']] += 1; gp[g['at']] += 1
        if not g['neutral']: hist.append((g['season'], res))
    return preds


def rmse(ps, w):
    e = [(p['pm'] - p['result']) ** 2 for p in ps if w[0] <= p['season'] <= w[1]]
    return math.sqrt(sum(e) / len(e)), len(e)


def ats(ps, w, thr=0.0):
    wn = l = 0
    for p in ps:
        if not w[0] <= p['season'] <= w[1] or p['spread'] is None: continue
        gap = p['pm'] - p['spread']; c = p['result'] - p['spread']
        if abs(gap) < thr or c == 0: continue
        if (c > 0) == (gap > 0): wn += 1
        else: l += 1
    return wn, l


def main():
    games = M.fetch_games()
    base = run(games, LIVE)
    print('reproduction of live (2014+): margin RMSE %.3f (data/game_model.json says 13.003)' % rmse(base, (2014, 9999))[0])
    b = {n: rmse(base, w)[0] for n, w in (('tune', TUNE), ('val', VAL))}
    print(f"live RMSE  tune {b['tune']:.3f}  validate {b['val']:.3f}\n")
    cands = {}
    for wS in (0.25, 0.5, 0.75): cands[f'blend scoring-ratings margin wS={wS}'] = dict(LIVE, wS=wS)
    for kd in (0.5, 1.0, 2.0, 4.0): cands[f'early-season K boost kd={kd}'] = dict(LIVE, kd=kd)
    cands['rolling 3-season HFA'] = dict(LIVE, hfa_roll=True)
    for s in (0.9, 0.95): cands[f'shrink margin x{s}'] = dict(LIVE, shrink=s)
    for m in (0.1, 0.2): cands[f'market learning m={m}'] = dict(LIVE, mkt=m)
    for KQ in (0.03, 0.06): cands[f'per-QB ratings instead of backup flag KQ={KQ}'] = dict(LIVE, qbr=True, KQ=KQ)
    for car in (0.6, 0.85): cands[f'carry {car}'] = dict(LIVE, carry=car)
    for K in (0.05, 0.08): cands[f'K {K}'] = dict(LIVE, K=K)
    print(f"{'idea':<52}{'tune':>8}{'validate':>10}   verdict")
    keep = []
    for name, o in cands.items():
        p = run(games, o); t, v = rmse(p, TUNE)[0], rmse(p, VAL)[0]
        ok = t < b['tune'] - 0.005 and v < b['val'] - 0.005
        print(f'{name:<52}{t - b["tune"]:>+8.3f}{v - b["val"]:>+10.3f}   {"BEATS live on both" if ok else "no"}')
        if ok: keep.append((t, name, o))
    print('\n(RMSE difference vs live; negative = better)')
    if not keep:
        print('No single idea beat live on both windows; the sealed 2023+ test is not spent.'); return
    # combine the winners (later keys override), then judge once on the sealed window
    combo = dict(LIVE)
    for _, name, o in sorted(keep): combo.update({k: v for k, v in o.items() if v != LIVE[k]})
    p = run(games, combo)
    t, v = rmse(p, TUNE)[0], rmse(p, VAL)[0]
    print('combined winners:', [n for _, n, _ in sorted(keep)]); print(f'  tune {t - b["tune"]:+.3f}  validate {v - b["val"]:+.3f} vs live')
    if t < b['tune'] and v < b['val']:
        lr, n = rmse(base, TEST); cr, _ = rmse(p, TEST)
        mk = math.sqrt(sum((q['spread'] - q['result']) ** 2 for q in p if TEST[0] <= q['season'] and q['spread'] is not None) / n)
        print(f'SEALED 2023+ (n={n}, scored once): live {lr:.3f}  candidate {cr:.3f}  closing line {mk:.3f}')
        for thr in (1.5, 3.0): print(f'  ATS gap>={thr}: live {ats(base, TEST, thr)}  candidate {ats(p, TEST, thr)}')


if __name__ == '__main__':
    main()
