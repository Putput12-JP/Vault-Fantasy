# CFB model: a weekly-refit blend of the model and the market (2026-10-13): NO-GO

`scripts/cfb_blend_study.py`. Pre-registered (everything fixed in the script's docstring before the first run). Each week, ridge-fit how much of the model's disagreement with the line to believe,
using only games already played (earlier seasons plus this season's earlier weeks, 150-game floor, lambda 500, no intercept), then pick on the refit expectation r_hat. Two input sets (the model's
edge; the rating edge and the special teams term separately), two lines (ESPN close; ESPN open), 2023-25 judged, 2024-25 shown separately. Thresholds on |r_hat| of 1.0 to 2.5 points and a matched-count
version (the same number of picks per season as the current rule, the largest |r_hat|, no threshold search).

- **Against the close the fitted weight is about 0.1 and shrinking.** Its path: 0.21 (2022 wk 12), 0.20 -> 0.15 (2023), 0.11 -> 0.10 (2024), 0.09 -> 0.11 (2025). Believing 10% of a 5 point disagreement is half a point, so
  |r_hat| rarely reaches 1.5: 95 games over three seasons.
- **No accuracy gain over the line.** Average miss 2023-25: line 11.966, line + r_hat 11.967 (B1) and 11.961 (B2), model alone 12.555.
- **Matched-count picks vs the close** (same count as the current rule): B2 306-260 (54.1%) vs the current rule's 305-272 (52.9%) in 2023-25, and 196-154 (56.0%) vs 197-160 (55.2%) in 2024-25. B1 53.0% and 54.3%.
  Differences of one to two points on about 570 and 350 picks are inside the noise band (about 2 points).
- **Against the open the fitted weight is zero.** It is -0.08 to +0.03 every week, yet the 5+ point picks the current rule makes hit 55.8% vs the open in 2023-25. The signal lives in the tail of large
  disagreements, not in a linear scaling, so a smooth blend throws it away. (Exploratory, not part of the pre-registered test.)
- Not shipped. The weekly refit would only help if it beat the current 5+ rule by more than noise; it does not, and nothing here changes a live number.
