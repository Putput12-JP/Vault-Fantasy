#!/usr/bin/env python3
"""Refit QB passing markets with the sd/calibration trained on EVERY game by an established
starter (finding 1 of docs/leakage-audit-2026-10-06.md), and compare to the current (gated-target) fit
under a season holdout. Writes nothing. Run from repo root: python3 scripts/refit_qb_gate.py"""
import sys, json, math, statistics as st
sys.path.insert(0, 'scripts')
import build_prop_projections as B
import backtest_prop_model as BT

MK = ['pass_att', 'pass_cmp', 'pass_yd', 'pass_td']
KEY = {'pass_att': 'att', 'pass_cmp': 'cmp', 'pass_yd': 'pyds', 'pass_td': 'ptds'}
seasons = B.load_seasons(2016)
SEQ = {}
for yr, pl in seasons.items():
    SEQ.update(B.player_games(pl, yr))

def num(v): return B.num(v)
def gated_hist(rows):                      # past games with 15+ attempts (T-legal history)
    return [r for _, r in rows if (num(r.get('att')) or 0) >= 15]

def eval_after(mkt, spec, seq, hl, kv, ke, priors):
    """Like B.eval_market, but history is gated and the SCORED set is every game the QB played."""
    resid, preds, acts, base = [], [], [], []
    for (name, pos, yr), rows in seq.items():
        if pos not in spec['pos']: continue
        for i, (wk, r) in enumerate(rows):
            att = num(r.get('att'))
            if not att or att <= 0: continue
            h = gated_hist(rows[:i])
            if len(h) < B.MIN_PRIOR: continue
            if B.is_usage(spec):
                vs = [num(x['att']) for x in h]; es = [num(x['pyds']) / num(x['att']) for x in h if num(x.get('pyds')) is not None and num(x['att'])]
                act = num(r.get('pyds'))
                if act is None or len(es) < B.MIN_PRIOR: continue
                proj = B.project_series(vs, priors[mkt + '|vol'], hl, kv) * B.project_series(es, priors[mkt + '|eff'], hl, ke)
                b = st.fmean([num(x.get('pyds')) for x in h[-4:]])
            else:
                vals = [num(x.get(spec['stat'])) for x in h if num(x.get(spec['stat'])) is not None]
                act = num(r.get(spec['stat']))
                if act is None or len(vals) < B.MIN_PRIOR: continue
                proj = B.project_series(vals, priors[mkt], hl, kv); b = st.fmean(vals[-4:])
            preds.append(proj); acts.append(act); resid.append(act - proj); base.append(b)
    return resid, preds, acts, base

def fit(mkt, spec, seq, priors, evalfn):
    best = None
    kvs = [2, 4, 8]
    for hl in [2.5, 4, 6, 9]:
        for kv in kvs:
            for ke in ([6, 12, 24] if spec['kind'] == 'yards' else [0]):
                resid, preds, acts, base = evalfn(mkt, spec, seq, hl, kv, ke, priors) if evalfn is not B.eval_market else B.eval_market(mkt, spec, seq, hl, kv, ke, priors)
                if len(preds) < 300: continue
                rm = B.rmse(resid)
                if best is None or rm < best['rmse']: best = dict(hl=hl, kv=kv, ke=ke, rmse=rm, preds=preds, acts=acts)
    dist, extra = B.choose_dist(spec, best['preds'], best['acts'])
    e = {'dist': dist, **extra}
    e['calib'] = B.fit_calibration_fn(best['preds'], best['acts'], B.prob_fn_for(e), spec['kind'])
    e['shrink'] = B.fit_shrink(spec, best['preds'], best['acts'], e)
    e.update(hl=best['hl'], kv=best['kv'], ke=best['ke'], n=len(best['preds']))
    return e

def serve_p(e, proj, line):
    p = B.apply_calib(e['calib'], B.prob_fn_for(e)(proj, line))
    return min(max(B.shrink_prob(min(max(p, 0.01), 0.99), e['shrink']), 0.01), 0.99)

def test_rows(mkt, spec, priors, T):
    """Every game by an established starter in season T; projection from the gated tail of last season + this one."""
    out = []
    for (name, pos, yr), rows in SEQ.items():
        if yr != T or pos not in spec['pos']: continue
        prev = SEQ.get((name, pos, T - 1), [])
        for i, (wk, r) in enumerate(rows):
            att = num(r.get('att'))
            if not att or att <= 0: continue
            h = gated_hist(prev[-17:] + rows[:i])
            if len(h) < B.MIN_PRIOR: continue
            out.append((mkt, h, r))
    return out

def proj_from(mkt, spec, h, e, priors):
    if B.is_usage(spec):
        vs = [num(x['att']) for x in h]; es = [num(x['pyds']) / num(x['att']) for x in h if num(x.get('pyds')) is not None and num(x['att'])]
        return B.project_series(vs, priors[mkt + '|vol'], e['hl'], e['kv']) * B.project_series(es, priors[mkt + '|eff'], e['hl'], e['ke'])
    vals = [num(x.get(spec['stat'])) for x in h if num(x.get(spec['stat'])) is not None]
    return B.project_series(vals, priors[mkt], e['hl'], e['kv'])

def metrics(pairs):
    n = len(pairs); ll = -st.fmean([y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in pairs])
    br = st.fmean([(p - y) ** 2 for p, y in pairs]); bins = {}
    for p, y in pairs: bins.setdefault(min(int(p * 10), 9), []).append((p, y))
    ece = sum(len(v) / n * abs(st.fmean(a for a, _ in v) - st.fmean(b for _, b in v)) for v in bins.values())
    return dict(n=n, ll=ll, brier=br, ece=ece, mp=st.fmean(p for p, _ in pairs), hit=st.fmean(y for _, y in pairs))

if __name__ == '__main__':
    TEST = [2021, 2022, 2023, 2024, 2025]
    agg = {m: {'before': [], 'after': [], 'before_lowtail': [], 'after_lowtail': []} for m in MK}
    params_now = {}
    for T in TEST:
        train = {k: v for k, v in SEQ.items() if k[2] < T}
        priors = B.compute_priors(train)
        for m in MK:
            spec = B.MARKETS[m]
            eb = fit(m, spec, train, priors, B.eval_market)
            ea = fit(m, spec, train, priors, eval_after)
            if T == 2025: params_now[m] = (eb, ea)
            for _, h, r in test_rows(m, spec, priors, T):
                act = num(r.get(KEY[m]))
                if act is None: continue
                low = (num(r.get('att')) or 0) < 15
                for tag, e in (('before', eb), ('after', ea)):
                    proj = proj_from(m, spec, h, e, priors)
                    for line in B._lines_for(spec['kind'], proj, grid=(0.85, 1.0, 1.15)):
                        pr = (serve_p(e, proj, line), 1.0 if act >= line else 0.0)
                        agg[m][tag].append(pr)
    print('HOLDOUT 2021-2025, every game by an established starter, lines at 0.85/1.0/1.15 x projection')
    print(f"{'market':9s} {'fit':7s} {'n':>6s} {'logloss':>8s} {'brier':>7s} {'ECE':>6s} {'mean p':>7s} {'hit':>6s}")
    for m in MK:
        for tag in ('before', 'after'):
            x = metrics(agg[m][tag]); print(f"{m:9s} {tag:7s} {x['n']:6d} {x['ll']:8.4f} {x['brier']:7.4f} {x['ece']:6.3f} {x['mp']:7.3f} {x['hit']:6.3f}")
    print('\nFITTED PARAMS (trained on seasons < 2025)')
    for m, (eb, ea) in params_now.items():
        f = lambda e: {k: (round(v, 3) if isinstance(v, float) else v) for k, v in e.items() if k not in ('calib',)}
        print(m, '\n  before', f(eb), 'calib pts', len(eb['calib']), '\n  after ', f(ea), 'calib pts', len(ea['calib']))
