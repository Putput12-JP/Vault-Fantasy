#!/usr/bin/env python3
"""
DARKO-style true-talent filter vs the EWMA the model uses (rates v3). Question from docs/reverse-engineering-targets.md:
does a local-level Kalman filter (talent drifts as a random walk; each game is a noisy observation whose noise shrinks
with minutes played) predict next-game per-minute production better than a tuned EWMA?

Per player, per stat s (per-minute rate): state mean m, variance P.
  predict: P += q                       (talent drift per game; offseason gap adds q_off)
  observe: rate y over `mins` minutes, noise r / mins
  update : K = P / (P + r/mins); m += K (y - m); P *= (1 - K)
Baseline: EWMA with alpha from a grid, same league-mean start, same minute weighting in the score.

Protocol (as rates v3): tune q, r (and alpha) on seasons 2023-2024, score on 2026 (2025-26), prediction made BEFORE the
game it scores; metric = minutes-weighted RMSE of the per-minute rate. Players start each season carrying their state.

  python3 nba/scripts/build_kalman_rates.py
"""
import itertools, os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SEASONS = [2022, 2023, 2024, 2025, 2026]
TUNE, TEST = (2023, 2024), 2026
STATS = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', 'fg3a': 'three_point_field_goals_attempted',
         'fg3m': 'three_point_field_goals_made'}


def load():
    fr = []
    for s in SEASONS:
        b = pd.read_csv(os.path.join(HERE, '..', 'raw', 'hoopr', f'player_box_{s}.csv'), low_memory=False)
        b = b[(b.season_type == 2) & (b.minutes.fillna(0) >= 4)].copy()
        b['season'] = s
        fr.append(b)
    b = pd.concat(fr)
    b['date'] = pd.to_datetime(b.game_date)
    return b.sort_values(['athlete_id', 'date']).reset_index(drop=True)


def run(b, col, season_filter, q, r, alpha, q_off, prior_var, prior_mean):
    """Return (kalman sq err, ewma sq err, weight) summed over rows in season_filter."""
    ek = ee = w = 0.0
    for aid, g in b.groupby('athlete_id', sort=False):
        m, P = prior_mean, prior_var
        e = prior_mean
        last = None
        for s, mins, y in zip(g.season.values, g.minutes.values, (g[col] / g.minutes).values):
            if last is not None and s != last:
                P += q_off
            last = s
            if s in season_filter:
                ek += mins * (y - m) ** 2
                ee += mins * (y - e) ** 2
                w += mins
            P += q
            K = P / (P + r / mins)
            m += K * (y - m)
            P *= (1 - K)
            e += alpha * (y - e)
    return ek, ee, w


def main():
    b = load()
    out = []
    for name, col in STATS.items():
        mu = float((b[col] / b.minutes).mean())
        var = float(((b[col] / b.minutes - mu) ** 2).mean())
        prior_var = var * 0.5
        # tune on 2023-24
        best_k = best_e = None
        for q, rr, qo in itertools.product([var * f for f in (0.0005, 0.002, 0.008)],
                                           [var * f for f in (20, 60, 180)],
                                           [var * f for f in (0.02, 0.08)]):
            ek, _, w = run(b, col, TUNE, q, rr, 0.1, qo, prior_var, mu)
            sc = (ek / w) ** 0.5
            if best_k is None or sc < best_k[0]:
                best_k = (sc, q, rr, qo)
        for a in (0.02, 0.035, 0.05, 0.07, 0.1, 0.14, 0.2):
            _, ee, w = run(b, col, TUNE, 1e-9, 1.0, a, 0.0, prior_var, mu)
            sc = (ee / w) ** 0.5
            if best_e is None or sc < best_e[0]:
                best_e = (sc, a)
        ek, _, w = run(b, col, (TEST,), best_k[1], best_k[2], 0.1, best_k[3], prior_var, mu)
        _, ee, w = run(b, col, (TEST,), 1e-9, 1.0, best_e[1], 0.0, prior_var, mu)
        rk, re_ = (ek / w) ** 0.5, (ee / w) ** 0.5
        out.append((name, re_, rk, 100 * (1 - rk / re_), best_e[1]))
        print(f'{name:5s} test RMSE/min  EWMA(a={best_e[1]}) {re_:.4f}  Kalman {rk:.4f}  ({100 * (1 - rk / re_):+.2f}%)', flush=True)
    return out


if __name__ == '__main__':
    main()
