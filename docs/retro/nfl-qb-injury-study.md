# NFL: do starting quarterback quality and injury-report absences improve the game model? (2026-10-14)

`scripts/nfl_qb_injury_study.py`. Today the model handles one case, a backup quarterback (a flat points adjustment). The market also prices
who the quarterback is and who else is out. Two features, each built from information available before kickoff, 2017-2025, walk-forward,
graded against the closing spread. Rules were written before the run: ridge strength and the quarterback shrinkage chosen on 2017-2021 by
leave-one-season-out miss only, 2022-2025 read once with the 2017-2021 fit, and GO only if the test miss falls by more than 2 standard
errors of the paired difference and the 3+ point pick record against the close is not worse.

**Quarterback quality.** Each quarterback's career EPA per dropback to date (games before this week), shrunk toward 0 by K dropbacks
(150, 300 or 600 tried). Feature is the starter's rating minus the team's established starter's rating (most frequent starter over the
last 24 games, at least 10 starts), home minus away. The team rating already carries the established starter, so only a change in who
plays can move it. That is 1,398 of 4,436 team-games (31%), which is more than injuries to the starter alone: the established starter lags
a permanent change, so a team's new full-time quarterback counts as "different" for a while.

**Injuries.** A regular is a player averaging 60%+ of his team's snaps over its previous 4 games (nflverse snap counts, quarterbacks left out).
Out is Out or Doubtful on the game-week injury report. Feature is the number of regulars out by unit (offensive line, receivers, tight
end, running back, defensive line, linebackers, defensive backs), home minus away. At least one regular is listed out in 37% of team-games.
Every regular counts the same: the feature knows how many, not how good.

| 2022-2025 test, 1,139 games | Miss base | Miss with | Paired t | Market's miss on the features |
|---|---|---|---|---|
| Quarterback only | 12.663 | 12.674 | -0.38 | t = -0.06 |
| Injuries only | 12.663 | 12.695 | -0.92 | no unit beyond t = 1.3 (offensive line) |
| Both | 12.663 | 12.674 | -0.27 | quarterback t = -0.22 |

The market's miss on the same games is 12.423. Tuning chose the heaviest ridge in the grid (1,000) for all three, and its leave-one-season-out
miss never beat the 13.249 baseline by more than 0.007, so the data asked for the features to be shrunk to almost nothing.

| Picks vs the close, test | Baseline | Quarterback only | Injuries only | Both |
|---|---|---|---|---|
| 1.5+ points | 273-266 | 242-239 | 250-263 | 248-252 |
| 3+ points | 103-105 | 84-92 | 97-106 | 89-99 |
| 5+ points | 35-30 | 26-21 | 33-23 | 28-24 |

The 5+ point record for injuries only (33-23, 59%) is the only line above the baseline and it is 56 games, picked among twelve records
after the model changed, so it is not read as a finding.

Coefficients have the right sign (more of the home team's regulars out lowers the home margin: about -1.8 points per linebacker, -1.0 per
receiver, -0.4 per lineman) and none of them is distinguishable from zero at this sample size. Regressing the market's own miss on the
features finds nothing either: the market is not under-pricing a count of absences or a change of quarterback.

**What this says: NO-GO.** Neither feature lowers the miss, in the tuning seasons or the test. Nothing ships; the NFL Model page and
`game_model.json` are unchanged.

What this does not rule out: a feature that knows who a player is. A count treats a backup guard and an all-pro tackle the same, and the
quarterback rating is a career average of EPA, which is noisy for a young player. The study also uses the final game-week status, which
the market sees as it is posted. The next step would be player-level value (snap-weighted production, or a market value such as a
contract), and a forward tracker that records the injury report before lines move. That is a new design, not a tweak to this one.
