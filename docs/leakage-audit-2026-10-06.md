# Leakage audit: NFL and NBA models (2026-10-06)

Method: `leakage-audit` skill (sports-analytic-skills). Code read and traced by hand against its pattern
catalog. No metric was re-run except where stated. Verdict scale: CLEAN / REVIEW REQUIRED / NOT CLEAN.

## Scope and verdicts

| Pipeline | T (decision time) | Verdict |
|---|---|---|
| NFL prop projection, trainer (`build_prop_projections.py`) | kickoff | REVIEW REQUIRED |
| NFL prop season-holdout (`backtest_prop_model.py`) | kickoff | CLEAN (one caveat) |
| NFL live grading (`settle_bets.py`, `model_from`) | bet time | CLEAN |
| NFL game model (`build_game_model.py`) | kickoff | REVIEW REQUIRED (low severity) |
| NFL grade calibration (`build_grade_calibration.py`) | draft day | CLEAN |
| NFL vacated share (`build_vacated_share.py`) | preseason | REVIEW REQUIRED |
| NBA game model (`nba/scripts/build_game_model.py`) | 1pm ET / 30 min pre-tip | REVIEW REQUIRED (disclosed) |
| NBA prop model v2 (`build_prop_model_v2.py`) | 30 min pre-tip | REVIEW REQUIRED |

## Findings, most severe first

### 1. NFL: the QB starter gate filters on the target (REVIEW, medium)
`gated()` (`build_prop_projections.py:94`) keeps only games where the QB threw 15+ attempts. It is applied to
history and priors (legal, past games) and also to the scored games in `eval_market` (line 223). The
scored-game filter uses the same game's actual attempts, a post-T variable. Effects:
- pass_att, pass_cmp, pass_yd and pass_td are scored and calibrated with the left tail removed.
- Data check: of 3,046 games by QBs who threw 25+ in some game (2021-26 files), 252 (8.3%, mean 6.6 attempts)
  fall under the gate. Those are in-game injuries and pulled starters.
- The 2026-10-05 claim "yardage error 61 -> 58 (the line: 56)" is therefore measured on a truncated population.
- Mitigation: books usually void a QB who does not start, so part of the gate is defensible. It does not cover a
  QB who starts and leaves hurt.
Repair: gate on information available at T (listed starter, prior-week attempts), score every game that
player started, report voids separately, then re-run the model-vs-line comparison.

### 2. NBA: backtest candidate set is the post-game box score (REVIEW, medium)
`build_prop_model_v2.py:~240` builds `cand` from `rows`, the box-score rows (`nba_common.py:74`: "played or
DNP"). That includes healthy scratches and anyone dressed, none of which is known 30 minutes before tip beyond
the injury report. Minutes are then normalized to team minutes over that set.
`check_minutes_parity.py:74` proves code parity but does so by forcing `cand_override` to the same box-score
players, so it cannot detect this. Live pricing builds candidates from rosters and depth charts.
Repair: re-run v2 and minutes v3 with candidates = roster as of the pre-tip report plus confirmed lineup feed
(2025-26 has `lineups` data), compare MAE and ROI. If unchanged, mark CLEAN with the evidence.

### 3. NBA: one test season reused for many candidates (REVIEW, medium)
v2, v3, v3_full, minutes v3, minutes-v3 pricing, starters, consensus, moved-players, season-start, copula and
the game-model options are all judged on 2025-26, and the game model's params (K, CARRY, C, B2B) were tuned
before several of those checks. Each look is individually honest. Together they are a forking-paths risk, and
"GO" calls with t of 2 to 3 need that discount. The untouched holdout is the live shadow ledger recorded since
2026-09-30. Treat its results as the real test.
Repair: write the accept rule for each candidate in `experiment-log` before the live ledger is read; count trials.

### 4. NFL vacated share: label filter uses next-season survival (REVIEW, medium)
`build_vacated_share.py` records a ratio only for players who return to the same team and play 6+ games in S+1.
Injured, cut or demoted players drop out, and a departed lead raises the survival chance, so the effect is
biased up. Serving applies the multiplier to everyone. The stability gate is an even/odd season split, which is
not time-ordered, and adjacent pairs share a season.
Repair: include every player in the S room (volume 0 for non-returners, or model survival), validate with
train-before-test season pairs.

### 5. NFL: in-season real-line recalibration gate picked after viewing results (REVIEW, low)
`RECAL_MIN_N = 300` was chosen after "ungated shifts HURT" on 2026 Wks 1-3, then reported as +2.1 z on 1,108
props from the same weeks. A selected gate on the sample that selected it. The point-in-time machinery around it
(`model_from`, `prop_model_at`) is correct.
Repair: re-score the gate on Wks 4+ only, which is untouched.

### 6. NBA game model: tuned on hindsight availability (REVIEW, low, disclosed)
Tuned on 2023-24 with who actually sat; tested with injury reports. That is train/serve skew, not test leakage,
and the docs already say the verdict is "context, not an edge". The ESPN open line has no timestamp (known).

### 7. NFL game model: learning rates picked on the reported walk-forward (REVIEW, low)
"Sit at the minimum" of the same RMSE reported from 2014. The model already loses to the close (13.21 vs 12.87),
so optimism only strengthens the conclusion.

### 8. Data vintage (REVIEW, low, both)
Backtests read current nflverse and hoopR files, which include later stat corrections. Live use sees the
as-published numbers. Likely tiny, unmeasured.

## Checked and clean
- Shift-before-roll: `eval_market` projects from `series[:i]`; NBA `update_after` runs after each record and
  scores defense against pre-game rates (`rt_before`).
- Season-holdout refits projections, priors, distribution and calibration on train seasons only
  (`backtest_prop_model.py:fit_market`, `holdout`).
- Grade calibration is walk-forward by target season, pooled and scored once.
- Live settlement grades with the model version in force at grading time (`model_from`).
- NBA ESPN "current" post-tip prices are excluded by `cur_is_pretip`; live-odds book 59 is excluded.

## Not verified
- I did not re-run any backtest. Findings 1 to 4 are code-reading plus one data count; sizes of the effects are
  unmeasured except the 8.3% in finding 1.
- Not audited: build_usage_cascade (NFL and NBA), build_role_volume, wind and DvP models, lean_search.py,
  Kalshi anchor, consensus engine.

## Addendum: QB gate re-score (finding 1), `scripts/audit_qb_gate.py`

Walk-forward 2018-2026, shipped hyperparameters, QBs with 3+ prior 15-attempt games (a rule knowable at T).
Variants: A = current (gated history, score only att >= 15); B = gated history, score every game the QB played;
C = ungated history, score every game.

| Market | A rmse | B rmse (bias) | C rmse (bias) | C on A's games |
|---|---|---|---|---|
| pass_att | 8.05 | 9.27 (+1.16) | 9.20 (-0.87) | 8.25 |
| pass_cmp | 5.77 | 6.48 (+0.77) | 6.43 (-0.55) | 5.88 |
| pass_yd | 73.8 | 80.6 (+10.3) | 80.1 (-7.8) | 75.1 |
| pass_td | 1.15 | 1.15 | 1.15 | 1.15 |

Findings:
- On the games the gate keeps, gated history beats ungated by 1.7-2.5% (the October 5 gain is real *there*).
- On every game a starter plays, the gate gives no gain (B is not better than C) and flips the bias from
  too low to too high. The headline improvement came from the scored population, not the projection.
- Only 3.6% of established-starter games fall under 15 attempts, but they cost 15% of attempts RMSE.
- Real lines (2026 settled, n = 39-79 per market): Vault's pass_yd projection runs +14 yards above actual
  (line +0.6) and loses to the line on MAE in att, cmp and yds. Not significant alone (about 1.4 SE).
- All 367 settled QB props: Vault's average win probability is 0.582 on overs (hit 51.5%) and 0.552 on
  unders (hit 49.3%); the market said 0.513 and 0.532. QB props are overconfident on both sides, which a
  left-tail leak alone would not explain (it would hit overs only).

Verdict: finding 1 stands as REVIEW REQUIRED, but the damage is smaller and different from first stated.
The gate is a reasonable history cleaner; the flaw is fitting sd and calibration on the truncated target.
Repair: keep the gated history, fit sd and isotonic calibration on all games by established starters, and
re-compare to the line on that population. No shipped numbers were changed.

## Addendum 2: refit of QB passing markets (`scripts/refit_qb_gate.py`, nothing written to data/)

"After" = same gated history, but sd/distribution, isotonic calibration and shrink are fit on every game by an
established starter. Season holdout, trained on seasons before each test year, test 2021-2025, all established
starter games, lines at 0.85/1.0/1.15 x projection (7,875 games per market):

| Market | Fit | Log loss | Brier | ECE | Mean p | Hit |
|---|---|---|---|---|---|---|
| pass_att | before / after | 0.6272 / 0.6238 | 0.2182 / 0.2167 | 0.057 / 0.047 | 0.494 / 0.481 | 0.437 |
| pass_cmp | before / after | 0.6386 / 0.6340 | 0.2234 / 0.2214 | 0.047 / 0.030 | 0.496 / 0.477 | 0.449 |
| pass_yd | before / after | 0.6397 / 0.6370 | 0.2243 / 0.2230 | 0.050 / 0.039 | 0.464 / 0.453 | 0.414 |
| pass_td | before / after | 0.5446 / 0.5414 | 0.1826 / 0.1813 | 0.043 / 0.030 | 0.484 / 0.471 | 0.442 |

Fitted change (trained < 2025): attempts and completions NB dispersion r 32.5/40.7 -> 16.7/16.7 (fatter tails);
pass_yd log-normal sd^2 = 2050 + 13.2*mu -> 6301 + 0*mu (constant, a boundary solution to look at) and its shrink
0.956 -> 1.0; pass_td unchanged except its n.

2026 settled QB props at the closing line (n = 66 to 115 per market; both fits trained < 2026): no measurable
change (log loss within 0.01 either way) and both lose to the no-vig market on att, cmp and yds (e.g. pass_yd
0.713 / 0.723 vs 0.693). pass_td is the one market at or better than the market (0.683 / 0.679 vs 0.684).

Read: the refit is a small, consistent calibration gain out of sample (log loss -0.3 to -0.5%, ECE down 20 to
35%) but does not fix QB overconfidence on real lines; that gap is the projection itself, not the tails.

## Addendum 3: NBA candidate set (finding 2), `nba/scripts/audit_candidate_set.py`

Re-ran `build_prop_model_v2.walk` with the live-style candidate rule (team players seen in the last 30 days, minus
report Outs; non-dressed ones take minutes but are never scored) in place of "everyone in the post-game box score".
Nothing written to `nba/data/`. Test season 2025-26, 27,799 common player-games.

| | Box-score candidates (shipped backtest) | As-of candidates (live-style) |
|---|---|---|
| Candidates per team-game | 12.23 | 12.86 |
| Minutes MAE | 4.860 | 5.040 (+3.7%) |
| pts MAE, v1 / v2 | 4.505 / 4.479 | 4.525 / 4.509 |
| reb, ast, 3pm MAE | unchanged to 0.002 | unchanged to 0.002 |

Betting-grade effect (v2 vs the no-vig market, weighted log-loss gap): ESPN 0.0040 -> 0.0058, Kalshi 0.0119 -> 0.0139
(model still loses to the market on price). The model's weight in the market blend stays significant
(pts t 2.45 -> 2.55 ESPN, 2.59 -> 2.15 Kalshi).

What flips: the pts verdict. v2 pts "GO (NO)" -> "WATCH (YES)", v1 pts "WATCH (NO)" -> "NO-GO". ESPN pts at a 2% gap went
from +14.2% ROI (n 151, z 1.73) to -6.9% (n 173, z -0.8). Caveat: the two runs bet different rows (906 vs 884
ESPN-matched), and ROI on ~150 bets has an SE near 10 points, so this is fragility, not proof of a negative edge.
Kalshi pts ROI barely moves (+4.5% z 2.0 -> +3.1% z 1.5 at the 3% gap).

Direction and size: the box-score rule leaks the dressed-roster decision (healthy scratches, late DNPs). Cost is
about 0.18 minutes of error per player-game and almost nothing on stats other than pts. The as-of rule is slightly
pessimistic (it drops 455 played arrivals who live pricing would add from the depth chart), so the truth sits between.

Verdict: finding 2 downgrades from "unknown" to REVIEW REQUIRED with measured size: small on projection accuracy,
material only for the pts GO label on ESPN prices. Repair: switch `build_prop_model_v2.walk` (and v3, minutes v3,
pickem corr) to the as-of rule with depth-chart arrivals, re-issue the verdict table, and point the parity check at
live-style candidates instead of `cand_override`.

## Addendum 4: NBA candidate rule applied (finding 2 repaired)

`build_prop_model_v2.walk` now defaults to `cand_rule='asof'`: candidates are players with minutes state on the team in
the last 30 days who are not Out on the pre-tip report, matching `pricing.py`. `cand_rule='box'` keeps the old leaky rule
for comparison. `check_minutes_parity.py` no longer forces box-score candidates and its exported state includes the same
30-day set; it reports 0 minutes difference on 40 sampled games (839 player-games), so live pricing and the backtest
now agree under the shared rule. Rebuilt: prop_model_v2, v3, v3_full, backtests, model_state and the rendered page.

Signal changes in `nba/data/backtests.json` (11 signals before and after):
- "Prop model v2 + Kalshi price, pts NO" was GO (n 5,023, ROI +3.5%, z 2.11). It is gone (no pts NO signal survives).
- v2 + Kalshi 3pm NO stays GO, weaker: z 3.53 -> 2.86, ROI +9.4% -> +8.7%.
- v2 ast YES and reb YES stay WATCH (n and ROI move, still below GO).
- All seven "Consensus ladder + model" signals are unchanged (that engine does not use the walk's candidate set).
Not rebuilt: v1 (`build_prop_model.py`, its own walk and candidate rule), `build_consensus.py`.

## Addendum 5: vacated share repaired (finding 4)

`scripts/build_vacated_share.py` changes: (1) a returner now needs 1 game in S+1, not 6 (`NEXT_MIN`); (2) the stability
gate is out of time (early half vs late half of the season pairs) instead of even/odd; (3) a bucket must also have a
lower 90% bootstrap bound above 1 on median(departed)/median(control) (2,000 draws, fixed seed).

Measured survivorship was real but small: share of returners playing 6+ games was 85.4% (departed) vs 84.3% (control)
for RBs and 83.6% vs 87.7% for WR/TE. The larger problem was that no bucket carried an uncertainty test:

| Bucket | Before | After relaxing the games filter | 90% CI (after) | Shipped now |
|---|---|---|---|---|
| WR/TE rank 4+, 2+ higher left | x1.125 | x1.106 | 1.01 to 1.18 | yes (x1.106) |
| WR/TE rank 3, 1 higher left | not published | x1.091 | 0.93 to 1.25 | no |
| RB rank 2, 1 higher left | x1.289 | x1.223 | 0.92 to 1.47 | no |
| RB rank 3, 1 higher left | x1.214 | x1.059 | 0.77 to 1.48 (halves 1.45 / 0.70) | no |
| RB rank 1, 1 lower left | withheld | x1.061 | 0.95 to 1.15 | no |

Effect on users: RB props lose the room-opened bump and show the existing "room?" caution (a starter left, no
reliable measured bump); the WR/TE bump gets a little smaller. Changelog entry added.

## Addendum 6: real-line recalibration gate (finding 5)

Question: does the post-hoc `RECAL_MIN_N = 300` hold up on weeks it was not chosen on? Walk-forward on 2026 settled props
at the closing line, base = the point-in-time served probability (`p_model`), shift fit on weeks before w, scored on
week w, w = 2, 3, 4 (1,886 rows; 1,886 is shared by every row below).

| Rule | Log-loss gain per row vs no shift |
|---|---|
| N >= 300, K 300 (shipped) | +0.00194 |
| N >= 100 / 50, K 300 | +0.00213 / +0.00206 |
| z >= 2, K 300 | +0.00127 |
| z >= 2.5, K 300 | +0.00044 |

All rules help a little, and the differences between them are inside noise. The gain comes from `rec` (+0.0051 per row,
c stable at 0.22 to 0.26 at every cutoff) and `rec_yd` (+0.0023, c 0.11 to 0.16). The markets a low N gate would also
shift lose: `rush_yd` -0.0021 (c cutoffs +0.62, +0.10, +0.09, -0.20), `pass_td` -0.0008, `pass_cmp` -0.0010.

Verdict: the 300 gate was chosen after the fact but it is not the thing doing the protecting. Fix shipped: keep N >= 300
and also require |z| >= 2 (z from the logit model's information, no tuned constant), logged per market. Current outputs
are unchanged: rec (c +0.165, z 3.14, n 791) and rec_yd (c +0.125, z 2.38, n 754) still apply; rush_yd and the QB markets would
now be refused if they reach 300 rows with a noise-level shift. Caveat: 1,886 rows over three test weeks, one season.
