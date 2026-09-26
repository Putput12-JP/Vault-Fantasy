#!/usr/bin/env python3
"""build_market_implied_calib.py — how wide is ONE game, for the market → stat inverse?

The "Market" fantasy projection (index.html, VaultPropModel.impliedMeanFrom)
turns a vig-free prop price into the stat line it implies: the MEAN of a
distribution whose P(over line) equals the market's fair probability. For count
and TD markets the shape barely matters. For YARDS it does: prop_model.json's
log-normal spread (sd_v0 + sd_v1·mean) is fitted on Vault's projection RESIDUALS,
which carry projection error on top of game-to-game noise. That extra width adds
skew, so the implied mean lands too far above the line.

This measures the spread SCALE k (variance multiplier) that makes the implied
mean unbiased against what actually happened, on every settled prop with a real
two-way closing price in data/bet_results.json. Markets below MIN_N borrow the
pooled log-normal fit and say so (`borrowed`). Writes data/market_implied_calib.json:

  { "markets": { "rec_yd": { "k": 0.40, "n": 373, "bias_raw": -4.57,
                             "bias_fit": 0.0, "borrowed": false }, ... },
    "meta": { ... } }

The client reads it through impliedMeanFrom(…, calib); absent file → k = 1
(the raw model spread), so a cold cache costs accuracy, never a crash.

    python3 scripts/build_market_implied_calib.py
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
MIN_N = 150                      # below this a market borrows the pooled fit
MAX_HOLD = 0.15                  # same sane-hold gate as VaultBettingMath.consensusFair
K_GRID = [round(0.05 * i, 2) for i in range(1, 41)]   # 0.05 … 2.00


def am_prob(a):
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def devig(o, u):
    po, pu = am_prob(o), am_prob(u)
    s = po + pu
    if s < 1 or s - 1 > MAX_HOLD:
        return None
    return po / s


def norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def lognorm_over(mu, var, line):
    if mu <= 0:
        return 0.0
    if line <= 0:
        return 1.0
    s2 = math.log(1 + var / (mu * mu))
    if s2 <= 0:
        return 1.0 if mu > line else 0.0
    return 1 - norm_cdf((math.log(line) - (math.log(mu) - s2 / 2)) / math.sqrt(s2))


def implied_mean(m, k, line, p):
    """Mirror of impliedMeanFrom for dist == 'lognormal' with variance × k."""
    if not (0.005 < p < 0.995):
        return None
    var = lambda mu: max(k * (m.get("sd_v0", 0) + m.get("sd_v1", 0) * max(mu, 0)), 1e-6)
    lo, hi = 1e-4, max(line * 4 + 10, 60)
    if lognorm_over(hi, var(hi), line) < p:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if lognorm_over(mid, var(mid), line) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def bias(m, k, rows):
    errs = [a - mu for (L, p, a) in rows for mu in [implied_mean(m, k, L, p)] if mu is not None]
    return (sum(errs) / len(errs)) if errs else None


def fit(m, rows):
    best = min(K_GRID, key=lambda k: abs(bias(m, k, rows) or 1e9))
    return best, bias(m, 1.0, rows), bias(m, best, rows)


def main():
    model = json.load(open(os.path.join(DATA, "prop_model.json")))["markets"]
    tape = json.load(open(os.path.join(DATA, "bet_results.json"))).get("props", [])
    logn = [k for k, m in model.items() if m.get("dist") == "lognormal"]

    rows, seen, weeks = {k: [] for k in logn}, set(), set()
    for b in tape:
        mk = b.get("market")
        if mk not in rows:
            continue
        key = (b.get("season"), b.get("week"), b.get("pid"), mk)
        if key in seen:                              # one row per player-market-week
            continue
        L, a, o, u = b.get("line_close"), b.get("actual"), b.get("close_over"), b.get("close_under")
        if None in (L, a, o, u):
            continue
        p = devig(o, u)
        if p is None:
            continue
        seen.add(key)
        weeks.add(f"{b.get('season')}w{b.get('week')}")
        rows[mk].append((float(L), p, float(a)))

    # Pooled fit across every log-normal market, each in its own units: the scale
    # multiplies that market's OWN fitted variance, so pooling k is meaningful.
    def pooled_bias(k):
        tot, n = 0.0, 0
        for mk, rs in rows.items():
            b = bias(model[mk], k, rs)
            if b is not None:
                tot += b * len(rs); n += len(rs)
        return tot / n if n else None
    pool_n = sum(len(r) for r in rows.values())
    pool_k = min(K_GRID, key=lambda k: abs(pooled_bias(k) or 1e9)) if pool_n else 1.0

    out = {}
    for mk, rs in rows.items():
        if len(rs) >= MIN_N:
            k, b0, b1 = fit(model[mk], rs)
            out[mk] = {"k": k, "n": len(rs), "bias_raw": round(b0, 2), "bias_fit": round(b1, 2), "borrowed": False}
        elif pool_n >= MIN_N:
            b0 = bias(model[mk], 1.0, rs) if rs else None
            b1 = bias(model[mk], pool_k, rs) if rs else None
            out[mk] = {"k": pool_k, "n": len(rs), "bias_raw": None if b0 is None else round(b0, 2),
                       "bias_fit": None if b1 is None else round(b1, 2), "borrowed": True}

    doc = {
        "markets": out,
        "meta": {
            "method": "variance scale k on prop_model log-normal so implied mean is unbiased vs actuals at the closing two-way fair",
            "min_n": MIN_N, "pooled_k": pool_k, "pooled_n": pool_n,
            "weeks": sorted(weeks),
        },
    }
    path = os.path.join(DATA, "market_implied_calib.json")
    json.dump(doc, open(path, "w"), indent=1, sort_keys=True)
    for mk, v in out.items():
        print(f"  {mk:8s} k={v['k']:.2f} n={v['n']:4d} bias {v['bias_raw']} -> {v['bias_fit']}{' (borrowed)' if v['borrowed'] else ''}")
    print(f"wrote {path} (pooled k={pool_k}, n={pool_n})")


if __name__ == "__main__":
    main()
