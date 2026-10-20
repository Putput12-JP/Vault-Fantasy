#!/usr/bin/env python3
# Distribution-width check for the NFL prop model: is the predictive distribution the right WIDTH?
# Season holdout exactly as backtest_prop_model.py (fit on seasons < T, score every game in T), RAW distribution
# (no isotonic), randomized PIT (integer outcomes). Reports per market:
#   cover80  share of outcomes inside the central 80% band (PIT in [.1,.9]); ideal 0.80
#   below10 / above90  tail shares; ideal 0.10 each. below10 high = model too high / too narrow on the low side
#   pit_mean ideal 0.50 (location bias); pit_sd ideal 0.2887 (<: too wide, >: too narrow)
# READ WITH CARE: the 80% band is driven by tail games (early exits, blowouts) that barely touch lines near the
# median. A width multiplier fit on log-loss over the real betting lines (0.85-1.15x proj) came out 0.9-1.0 for the
# yardage / pass markets, so a narrow band here did NOT mean mispriced lines. Judge width fixes on log-loss, not coverage.
# TD markets (large zero atoms): the band is not informative and the zero handling is unchecked.
# Usage: python3 scripts/backtest_prop_coverage.py [--since=2016 --test-from=2022 --markets=a,b]
import argparse, math, os, random, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_prop_model as T
B = T.B


def pit_rows(markets, since, test_from, rng):
    seasons = B.load_seasons(since)
    years = sorted(seasons)
    out = {m: [] for m in markets}
    for Y in [y for y in years if y >= test_from and (y - 1) in seasons]:
        train = {}
        for y in years:
            if y < Y:
                train.update(B.player_games(seasons[y], y))
        priors = B.compute_priors(train)
        prevp, curp = B.player_games(seasons[Y - 1], Y - 1), B.player_games(seasons[Y], Y)
        prev_by = {(nm, pos): rows for (nm, pos, _), rows in prevp.items()}
        for mk in markets:
            spec = B.MARKETS[mk]
            params = T.fit_market(mk, spec, train, priors)
            if not params:
                continue
            hl, kv, ke = params["hl"], params["kv"], params["ke"]
            pf = B.prob_fn_for(params)

            def add(proj, a):
                lo = 1 - pf(proj, a - 0.5)      # P(X <= a-1)
                hi = 1 - pf(proj, a + 0.5)      # P(X <= a)
                out[mk].append((Y, lo + rng.random() * max(0.0, hi - lo)))

            for (nm, pos, _), cur in curp.items():
                if pos not in spec["pos"]:
                    continue
                hist = list(prev_by.get((nm, pos), []))
                if not B.is_usage(spec):
                    pv0 = [v for v in B.market_series(hist, spec) if v is not None]
                    cs = B.market_series(cur, spec)
                    for i, a in enumerate(cs):
                        if a is None:
                            continue
                        pv = pv0 + [v for v in cs[:i] if v is not None]
                        if len(pv) >= B.MIN_PRIOR:
                            add(T.project(pv, priors[mk], hl, kv), a)
                else:
                    vh, nh = B.collect_series(hist, spec["vol"]), B.collect_series(hist, spec["eff_num"])
                    vc, nc = B.collect_series(cur, spec["vol"]), B.collect_series(cur, spec["eff_num"])
                    bv = [v for v in vh if v is not None]
                    be = [nh[j] / vh[j] for j in range(len(vh)) if vh[j] and vh[j] > 0 and nh[j] is not None]
                    for i in range(len(vc)):
                        if vc[i] is None or nc[i] is None:
                            continue
                        pv = bv + [v for v in vc[:i] if v is not None]
                        pe = be + [nc[j] / vc[j] for j in range(i) if vc[j] and vc[j] > 0 and nc[j] is not None]
                        if len(pv) >= B.MIN_PRIOR and len(pe) >= B.MIN_PRIOR:
                            proj = B.project_series(pv, priors[mk + "|vol"], hl, kv) * B.project_series(pe, priors[mk + "|eff"], hl, ke)
                            add(proj, nc[i])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=2016)
    ap.add_argument("--test-from", type=int, default=2022)
    ap.add_argument("--markets", default="")
    ap.add_argument("--by-year", action="store_true")
    a = ap.parse_args()
    mks = [m for m in a.markets.split(",") if m] or list(B.MARKETS)
    rows = pit_rows(mks, a.since, a.test_from, random.Random(7))
    print(f"{'market':11s}{'n':>8s}{'cover80':>9s}{'below10':>9s}{'above90':>9s}{'pit_mean':>9s}{'pit_sd':>8s}  verdict")
    for m, yu in rows.items():
        if not yu:
            continue
        u = [x for _, x in yu]
        if a.by_year:
            for Y in sorted({y for y, _ in yu}):
                w = [x for y, x in yu if y == Y]
                print(f"   {m:9s}{Y} n={len(w):6d} cover80 {sum(.1 <= x <= .9 for x in w)/len(w):.3f} below10 {sum(x < .1 for x in w)/len(w):.3f} pit_mean {statistics.fmean(w):.3f}")
        n = len(u)
        c = sum(.1 <= x <= .9 for x in u) / n
        lo, hi = sum(x < .1 for x in u) / n, sum(x > .9 for x in u) / n
        sd = statistics.pstdev(u)
        v = "ok" if abs(c - .8) <= .02 else ("TOO NARROW" if c < .8 else "too wide")
        print(f"{m:11s}{n:8d}{c:9.3f}{lo:9.3f}{hi:9.3f}{statistics.fmean(u):9.3f}{sd:8.3f}  {v}")


if __name__ == "__main__":
    main()
