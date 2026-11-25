# CFB model: turnover luck (2026-10-13): NO-GO

`scripts/cfb_turnover_luck_study.py`. The offense and defense ratings are EPA per play, and a turnover is a large EPA swing that is partly luck: 50.3% of fumbles are lost
whoever fumbles them, and part of an interception is a tipped ball. Three luck-neutral versions of the ratings were rebuilt end to end (v1 walk-forward for the targets, the v2
regression prior, the special teams layer) and compared with the current model on 2022-25, weeks 4+, 5+ point picks. Variants fixed before the run, nothing tuned. League-wide
averages are two pooled scalars (fumble plays -1.84 EPA; interception/incompletion plays -0.99, of which 6.5% are interceptions).

| | miss, tune | miss, test | 5+ vs close, test | 5+ vs open, test |
|---|---|---|---|---|
| current (v2 + special teams) | 12.811 | 12.454 | 197-160 (55.2%) | 205-157 (56.6%) |
| F: fumbles luck-neutral | 12.816 | 12.438 | 198-158 (55.6%) | 204-151 (57.5%) |
| FI: + interceptions luck-neutral | 12.811 | 12.521 | 214-177 (54.7%) | 218-162 (57.4%) |
| FI50: + half of interceptions | 12.808 | 12.470 | 209-171 (55.0%) | 210-160 (56.8%) |

- Fumble luck: the average miss moves by 0.016 on the untouched seasons and gets 0.005 worse on the tuning seasons. Under the 0.05 bar. The pick records are within a game or two of the current model.
- Taking interceptions out entirely makes the miss worse (12.521): part of interception rate is real quarterback and defense skill.
- The model's disagreement with the market gets more weight in predicting the final margin (0.12 -> 0.15 with fumbles, 0.20 with interceptions), but the miss does not move, so this is a
  shift in which games clear 5 points, not a better projection. Not shipped.
