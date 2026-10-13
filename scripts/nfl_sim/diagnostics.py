#!/usr/bin/env python3
"""Does the sim carry information the market line does not? Reads data/nfl_sim/sim_props.csv.gz (written by backtest.py).
Per market: correlation with the result, and an OLS  actual ~ line + sim_mean  fit on the in-sample half only, scored
on the out-of-sample half (RMSE of line alone vs line+sim). Informational: this blends in the line, so it is NOT a
Phase 1 projection (which has zero sportsbook inputs); it only measures incremental signal.
Usage: python3 -I scripts/nfl_sim/diagnostics.py"""
import json, os
import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "nfl_sim")


def ols(X, y):
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    cov = (e @ e / (len(y) - X.shape[1])) * np.linalg.inv(X.T @ X)
    return b, np.sqrt(np.diag(cov))


def empirical_qb_wr():
    """Observed correlation of QB1 passing yards with his team's pre-game WR1 receiving yards (2023-26 team-games).
    WR1 = most targets over the team's previous 8 games (no hindsight), so it is comparable to the sim's choice."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import data
    pw = data.player_weeks((2022, 2023, 2024, 2025, 2026))
    pw = pw.sort_values(["season", "week"])
    rows = []
    for team, g in pw.groupby("team"):
        keys = sorted({(s, w) for s, w in zip(g.season, g.week)})
        for i, k in enumerate(keys):
            if k[0] < 2023 or i < 8:
                continue
            prev = set(keys[i - 8:i])
            hist = g[[(s, w) in prev for s, w in zip(g.season, g.week)] & (g.pos == "WR").values]
            if hist.empty:
                continue
            wr1 = hist.groupby("gsis").targets.sum().idxmax()
            cur = g[(g.season == k[0]) & (g.week == k[1])]
            qb = cur[cur.pos == "QB"].sort_values("attempts").tail(1)
            w1 = cur[cur.gsis == wr1]
            if len(qb) and len(w1) and qb.attempts.iloc[0] >= 15:
                rows.append((float(qb.passing_yards.iloc[0]), float(w1.receiving_yards.iloc[0])))
    a = np.array(rows)
    return dict(n=int(len(a)), corr=float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]))


def main():
    d = pd.read_csv(os.path.join(OUT, "sim_props.csv.gz"))
    d["line"] = d.line_c.fillna(d.line_o)
    d = d.dropna(subset=["line", "sim_mean", "actual"])
    res = {}
    for m, x in d.groupby("market"):
        a, b = x[x.half == "in_sample"], x[x.half == "out_of_sample"]
        c = lambda u, v: float(np.corrcoef(u, v)[0, 1])
        Xa = np.c_[np.ones(len(a)), a.line, a.sim_mean]
        beta, se = ols(Xa, a.actual.values)
        Xb = np.c_[np.ones(len(b)), b.line, b.sim_mean]
        rm_line = float(np.sqrt(np.mean((b.actual - b.line) ** 2)))
        rm_sim = float(np.sqrt(np.mean((b.actual - b.sim_mean) ** 2)))
        rm_blend = float(np.sqrt(np.mean((b.actual.values - Xb @ beta) ** 2)))
        res[m] = dict(n_in=int(len(a)), n_oos=int(len(b)),
                      corr_actual_line_oos=c(b.actual, b.line), corr_actual_sim_oos=c(b.actual, b.sim_mean),
                      corr_resid=c(b.sim_mean - b.line, b.actual - b.line),
                      ols_in_sample=dict(beta_line=float(beta[1]), beta_sim=float(beta[2]), t_sim=float(beta[2] / se[2])),
                      oos_rmse=dict(line=rm_line, sim=rm_sim, blend_fit_in_sample=rm_blend,
                                    blend_gain_vs_line_pct=float(100 * (1 - rm_blend / rm_line))),
                      oos_bias=dict(sim_minus_actual=float((b.sim_mean - b.actual).mean()), line_minus_actual=float((b.line - b.actual).mean())))
    res["empirical_qb1_vs_pregame_wr1"] = empirical_qb_wr()
    json.dump(res, open(os.path.join(OUT, "diagnostics.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
