# CFB model: retuning the scale, home field, ridge strength and special teams weight (2026-10-13): accuracy up, picks not

`scripts/cfb_retune_study.py`. K (points per unit of rating gap, 70), the in-season ridge strength ALPHA (300), the flat home field (2.5) and the special teams weight (1.0) were fit for the
v1 model and never redone after the v2 prior and special teams. Searched on 2022-23 by average miss only (weeks 4+); 2024-25 read once.

- ALPHA stays at 300. Tune miss by ALPHA (each with its own best K, HFA, W): 100 12.816, 200 12.755, **300 12.727**, 500 12.747, 800 12.953, 1500 13.420.
- HFA stays at 2.5 and the special teams weight at 1.0 (within 0.01 of the best on the tuning seasons).
- K moves from 70 to 90: the ratings gap is too compressed, the same thing the team-strength-bias test found (elite teams under-rated).

| | miss, tune | miss, test | 5+ vs close, test | 5+ vs open, test | weight on edge, test |
|---|---|---|---|---|---|
| current (K 70) | 12.811 | 12.454 | 197-160 (55.2%) | 205-157 (56.6%) | 0.12 |
| K 90 | 12.727 | 12.313 | 168-150 (52.8%) | 158-126 (55.6%) | 0.08 |

The average miss improves by 0.14 on the untouched seasons (past the 0.05 bar), but the picks do not: 357 -> 318 picks vs the close, hit rate 55.2% -> 52.8%, and the weight the model's disagreement
gets falls 0.12 -> 0.08. Picks come from where the model differs from the market, and a larger K moves the model toward what the market already prices. Not shipped: the goal is better picks and leans,
not a lower miss. K 90 stays a candidate if accuracy of the margin itself becomes the target.
