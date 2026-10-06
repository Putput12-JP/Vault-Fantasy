#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  NBA · LEAN SEARCH  →  data/lean_trials_nba.json
#
#  Guard-railed refine/rerun loop (same rules as scripts/lean_search.py for the NFL):
#  each candidate input set is scored on THREE expanding time folds of the 2025-26 ESPN
#  pre-tip main lines (fit on the earlier games, score the next block, never the reverse):
#      fold 1 fit 0-40%  -> score 40-60%      fold 2 fit 0-60% -> score 60-80%      fold 3 fit 0-80% -> score 80-100%
#  Metric = log-loss over ALL lines in the fold, not hit rate on a slice. A candidate is
#  ACCEPTED only if it beats the incumbent on every fold, the pooled paired-bootstrap 95%
#  interval for the gain is above 0, and the gain clears a bar that rises with the number
#  of trials already logged. Every trial is logged. NBA-specific inputs: minutes
#  projection + its volatility, starter share, back-to-back, home, blowout risk, teammates
#  out / new team, stat-specific terms.
#
#    python3 nba/scripts/lean_search_nba.py            (first run dumps data/lean_rows_nba.json, ~5 min)
# ════════════════════════════════════════════════════════════════════════════
import json, math, os, random, statistics as st, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
DATA = os.path.join(os.path.dirname(__file__), '..', 'data'); ROWS = os.path.join(DATA, 'lean_rows_nba.json'); TRIALS = os.path.join(DATA, 'lean_trials_nba.json')
lg = lambda p: math.log(min(max(p, 1e-4), 1 - 1e-4) / (1 - min(max(p, 1e-4), 1 - 1e-4)))
sig = lambda z: 1 / (1 + math.exp(-max(-30, min(30, z))))
STATS = ['pts', 'reb', 'ast', '3pm', 'pra', 'pr', 'pa', 'ra']

def build_rows():
    import build_prop_model_v2 as V2, build_prop_model_v3 as A, build_prop_model_v3_full as F
    I = F.inputs(); recs = F.walk_v2(I)
    stk = V2.fit_stacker([r for r in recs if r['season'] == V2.FIT])
    espn, _ = A.load_markets(A.by_rec(recs)); rows = []
    for m in A.MARKETS if hasattr(A, 'MARKETS') else STATS:
        for x in espn.get((str(V2.TEST), m, 'close'), []):
            r, L = x['r'], x['L']; proj = V2.mu2(r, stk)[m]
            if abs(proj - L) < 1e-9: continue
            xp, mp = r['x']['pts'], max(r['mu']['pts'], 1e-6)
            rows.append({'m': m, 'gid': int(x['gid']), 'proj': proj, 'L': L, 'pk': x['pk'], 'y': int(x['over']), 'pm': r['pm'], 'sdm': r['sdm'],
                         'st': r.get('st'), 'spread': r.get('spread'), 'home': 0.5 + xp[5] / mp, 'b2b': xp[6] / mp, 'mv': int(bool(r.get('mv'))), 'na': int(bool(r.get('na')))})
    rows.sort(key=lambda r: r['gid']); json.dump(rows, open(ROWS, 'w'), separators=(',', ':')); return rows

def gap(r): return (r['proj'] - r['L']) / max(abs(r['L']), 0.5)
def base(r): return [1.0, lg(r['pk']), gap(r)]
def market_only(r): return [1.0, lg(r['pk'])]
def per_stat_icpt(r): return base(r) + [1.0 if r['m'] == s else 0.0 for s in STATS]
def per_stat_gap(r): return base(r) + [gap(r) * (1.0 if r['m'] == s else 0.0) for s in STATS]
def side_split(r):
    ov = 1.0 if r['proj'] > r['L'] else 0.0
    return base(r) + [ov, ov * gap(r), ov * lg(r['pk'])]
def minutes_conf(r): return base(r) + [gap(r) * (r['pm'] / max(r['sdm'], 1.0)) / 10, r['sdm'] / max(r['pm'], 1.0)]
def b2b_home(r): return base(r) + [r['b2b'], r['home'] - 0.5, gap(r) * r['b2b']]
def starter(r): return base(r) + [(r['st'] or 0.0) - 0.5, gap(r) * ((r['st'] or 0.0) - 0.5)]
def blowout(r): return base(r) + [abs(r['spread'] or 0.0) / 10, gap(r) * abs(r['spread'] or 0.0) / 10]
def new_team(r): return base(r) + [r['mv'], r['na'], gap(r) * r['mv']]
def all_nba(r): return base(r) + minutes_conf(r)[3:] + b2b_home(r)[3:] + starter(r)[3:] + blowout(r)[3:] + new_team(r)[3:]
CANDS = {'market_only': market_only, 'incumbent(base)': base, 'per_stat_icpt': per_stat_icpt, 'per_stat_gap': per_stat_gap, 'side_split': side_split,
         'minutes_confidence': minutes_conf, 'back_to_back_home': b2b_home, 'starter_share': starter, 'blowout_risk': blowout,
         'new_team_flag': new_team, 'all_nba_inputs': all_nba}

def fit(rows, feats, lam=1.0, it=25):
    X = [feats(r) for r in rows]; y = [r['y'] for r in rows]; k = len(X[0]); w = [0.0] * k
    for _ in range(it):
        g = [0.0] * k; H = [[0.0] * k for _ in range(k)]
        for xi, yi in zip(X, y):
            p = sig(sum(a * b for a, b in zip(w, xi)))
            for a in range(k):
                g[a] += (p - yi) * xi[a]
                for b in range(k): H[a][b] += p * (1 - p) * xi[a] * xi[b]
        for a in range(1, k): g[a] += lam * w[a]; H[a][a] += lam
        for a in range(k): H[a][a] += 1e-9
        A = [H[i][:] + [g[i]] for i in range(k)]
        for i in range(k):
            piv = max(range(i, k), key=lambda q: abs(A[q][i])); A[i], A[piv] = A[piv], A[i]
            for j in range(i + 1, k):
                f = A[j][i] / A[i][i]
                for c in range(i, k + 1): A[j][c] -= f * A[i][c]
        dw = [0.0] * k
        for i in reversed(range(k)): dw[i] = (A[i][k] - sum(A[i][j] * dw[j] for j in range(i + 1, k))) / A[i][i]
        w = [a - b for a, b in zip(w, dw)]
    return w

def score(feats, F):
    out = {}
    for name, (tr, te) in F.items():
        w = fit(tr, feats); ls, hits = [], []
        for r in te:
            p = sig(sum(a * b for a, b in zip(w, feats(r)))); pc = min(max(p, 1e-6), 1 - 1e-6)
            ls.append(-math.log(pc if r['y'] else 1 - pc)); hits.append((p >= .5) == bool(r['y']))
        out[name] = {'ll': st.mean(ls), 'hit': st.mean(hits), 'n': len(te), '_l': ls}
    return out

def main():
    random.seed(11)
    rows = json.load(open(ROWS)) if os.path.exists(ROWS) else build_rows(); n = len(rows)
    F = {f'fold{i+1}': (rows[:int(n * a)], rows[int(n * a):int(n * b)]) for i, (a, b) in enumerate([(.4, .6), (.6, .8), (.8, 1.0)])}
    prior = json.load(open(TRIALS))['trials'] if os.path.exists(TRIALS) else []
    inc = score(base, F); results = []
    print(f"{n} lines | " + ' | '.join(f"{k}: fit {len(v[0])} score {len(v[1])}" for k, v in F.items()))
    print(f"{'candidate':22s} " + ' '.join(f'{k:>22s}' for k in F) + '   verdict')
    for name, fn in CANDS.items():
        s = score(fn, F); better = {k: inc[k]['ll'] - s[k]['ll'] for k in F}
        diffs = [a - b for k in F for a, b in zip(inc[k]['_l'], s[k]['_l'])]; m = len(diffs)
        lo = sorted(st.mean(random.choices(diffs, k=m)) for _ in range(300))[7]
        looks = len(prior) + len(results) + 1; bar = 0.0003 * math.log(1 + looks)
        ok = name not in ('incumbent(base)', 'market_only') and all(v > 0 for v in better.values()) and lo > 0 and st.mean(diffs) > bar
        print(f"{name:22s} " + ' '.join(f"{s[k]['ll']:.4f} ({better[k]*1e4:+5.1f}e-4) {s[k]['hit']*100:4.1f}%" for k in F) + f"   {'ACCEPT' if ok else 'reject'} (pooled {st.mean(diffs)*1e4:+.1f}e-4, CI lo {lo*1e4:+.1f}e-4)")
        results.append({'t': datetime.now(timezone.utc).isoformat(), 'candidate': name, 'verdict': 'ACCEPT' if ok else 'reject', 'pooled_gain': round(st.mean(diffs), 6), 'ci_lo': round(lo, 6),
                        'folds': {k: {'ll': round(s[k]['ll'], 5), 'hit': round(s[k]['hit'], 4), 'n': s[k]['n'], 'vs_incumbent': round(better[k], 6)} for k in F}})
    json.dump({'note': 'NBA lean search trials (2025-26 ESPN pre-tip lines, expanding time folds). ACCEPT needs all folds better + bootstrap CI > 0 + a gain bar that rises with trials.',
               'trials': prior + results}, open(TRIALS, 'w'), indent=1)
    print(f"\n[lean-search-nba] {len(results)} scored, {len(prior)+len(results)} total looks logged")

if __name__ == '__main__':
    main()
