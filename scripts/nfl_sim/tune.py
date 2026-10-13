#!/usr/bin/env python3
"""One-time dispersion tuning (kappa = Dirichlet concentration, sigma_te = shared team passing-efficiency shock).
Tuned ONLY on 2023 weeks 8-12, which precede every backtested prop week (2024 onward), against box scores, with no
sportsbook data: score = mean pinball loss at q10/25/50/75/90 for players the model rates above the median volume.
Usage: python3 -I scripts/nfl_sim/tune.py"""
import itertools, json, os, sys
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import runner, model

QS = np.array([0.1, 0.25, 0.5, 0.75, 0.9])
WEEKS = [(2023, w) for w in (8, 9, 10, 11, 12)]


def pin(sim, y):
    q = np.quantile(sim, QS)
    d = y - q
    return float(np.mean(np.maximum(QS * d, (QS - 1) * d)))


def score(args):
    kappa, ste = args
    st = runner.get_state(2023)
    tot = {"rec_yd": [], "rec": [], "rush_yd": [], "pass_yd": []}
    for s, w in WEEKS:
        prm = st.fit_game_params((s, w))
        g = st.tg[(st.tg.season == s) & (st.tg.week == w)]
        seen = set()
        for r in g.itertuples():
            if r.game_id in seen:
                continue
            seen.add(r.game_id)
            row = g[g.game_id == r.game_id]
            home, away = row[row.home == 1].team.iloc[0], row[row.home == 0].team.iloc[0]
            res = model.simulate_game(st, away, home, (s, w), n=3000, seed=11, params=prm, kappa=kappa, sigma_te=ste)
            for team in (home, away):
                for gs, d in res[team].items():
                    if gs == "_team_pass_yd" or d["n_act"] < 4:
                        continue
                    pr = st.pw[(st.pw.season == s) & (st.pw.week == w) & (st.pw.gsis == gs)]
                    if not len(pr):
                        continue
                    for mk, col in (("rec_yd", "receiving_yards"), ("rec", "receptions"), ("rush_yd", "rushing_yards"),
                                    ("pass_yd", "passing_yards")):
                        if mk in d and d[mk].mean() >= {"rec_yd": 30, "rec": 2.5, "rush_yd": 25, "pass_yd": 120}[mk]:
                            tot[mk].append(pin(d[mk], float(pr[col].iloc[0])) / max(d[mk].mean(), 1e-9))
    return kappa, ste, {k: float(np.mean(v)) for k, v in tot.items()}, {k: len(v) for k, v in tot.items()}


if __name__ == "__main__":
    runner.get_state(2023)
    grid = list(itertools.product([8.0, 20.0, 50.0], [0.0, 0.06, 0.12]))
    with Pool(4) as p:
        out = p.map(score, grid)
    best = None
    for k, s, sc, n in out:
        m = float(np.mean(list(sc.values())))
        print(f"kappa={k:5.1f} sigma_te={s:.2f}  mean={m:.5f}  {json.dumps({a: round(b, 4) for a, b in sc.items()})}")
        if best is None or m < best[0]:
            best = (m, k, s)
    print("BEST", best)
    json.dump(dict(best_kappa=best[1], best_sigma_te=best[2], grid=[dict(kappa=k, sigma_te=s, score=sc, n=n) for k, s, sc, n in out]),
              open(os.path.join(HERE, "..", "..", "data", "nfl_sim", "tune_dispersion.json"), "w"), indent=1)
