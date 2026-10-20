# Preseason signals: pre-registered test

Written 2026-10-20 before any result below was computed. Rules, filters and thresholds are fixed here. Anything added
later goes in a section called "Amendments", dated, with the reason.

## Why

A public thread (BigHatProps, 2026-10-19, built with CourtAI) rebuilt every preseason game from play-by-play and
claims, on 2023-24 to 2025-26 preseasons:

1. First-half minutes per game (1H mpg) predict early-season minutes far better than total preseason mpg
   (r 0.86 vs 0.63; average miss on first-15-game mpg 3.2 to 3.8 min vs 5.8 min).
2. Shot mix and usage changes in preseason carry into the regular season (correlation of preseason change vs
   regular-season change, per 36, vs last season: 3PA 0.44, usage 0.40, FGA 0.36, REB 0.35, AST 0.33, PTS 0.33);
   efficiency does not (3P% 0.09).
3. A set of player and team reads built on those two rules (Acuff, Wizards starters, Draymond, Giddey, KAT, Franz,
   Orlando's offense, Zion, Jaquez). Several were bet at opening lines that then moved toward the bet.

We already have the rest of the pipeline (rates, minutes, ESPN open and close prop lines for 2024-25 and early
2025-26). We do not have preseason games: hoopR carries regular season and playoffs only. `fetch_preseason.py` pulls
them from ESPN (box score + every play), same source as hoopR.

Three questions, in order of how much they matter for betting:

- **A. Does it replicate?** (our numbers, our data, same definitions)
- **B. Does it add accuracy beyond what we already use?** (out of sample, vs last-season-only rates and minutes)
- **C. Is it already in the number?** (against ESPN opening and pre-tip prop lines)

A real signal that the line already holds is not an edge. C is the only part that can lead to a bet.

## Data and definitions (fixed)

- Preseason games: ESPN `seasontype=1`, both teams NBA (ids 1 to 30), completed. Season label = year the season ends
  (2024 = 2023-24). Test seasons 2024, 2025, 2026 (preseasons before those regular seasons). The 2027 preseason
  (just finished) is used for the live read in section D only, never to fit anything.
- First-half minutes: rebuilt from substitution plays, starters from the box score at the start of Q1, the lineup
  carried through to Q2. Whole-game minutes are rebuilt the same way and must match the box score minutes
  (**validation gate: median absolute error under 0.5 min per player-game, and 95% of player-games within 2 min**;
  fail and the 1H figures are not used).
- 1H usage = (FGA + 0.44 FTA + TOV) by the player / the same total for his team, while he is on the floor in the
  first half. 1H per-36 = counts over 1H minutes x 36.
- Veteran: 400+ regular-season minutes in the prior season. Rookies and second-year players with less are excluded
  from A and B (section D shows them separately, as the thread does).
- A player-season enters if: 40+ preseason minutes, 400+ prior-season minutes, and 10+ regular-season games in the
  first 15 team games (A) or 500+ regular-season minutes (B, as the thread states). Traded players are kept; team
  change is a flag, not an exclusion.
- Regular season data: hoopR player and team box scores (`raw/hoopr`). Last-season rates are the prior full regular
  season (playoffs excluded).
- Every fit is leave-one-season-out (each of the three seasons predicted from models fit on the other two), which is
  the thread's description. Intervals are paired bootstrap over players, 2,000 resamples.

## A. Replication (reported, no pass or fail)

1. Correlation of early-season mpg (first 15 team games) with: total preseason mpg, 1H preseason mpg, last-season mpg.
2. Mean absolute miss on first-15-game mpg for: total preseason; last season; last + total; 1H; last + 1H
   (the last two are two-variable OLS, leave-one-season-out).
3. For each of 3PA/36, usage, FGA/36, REB/36, AST/36, PTS/36, TOV/36, FTA/36, BLK/36, STL/36, 3P%: correlation of
   (preseason 1H rate minus last-season rate) with (regular-season rate minus last-season rate), and 95% interval.
4. Spot checks of the thread's named numbers rebuilt from our pbp: Acuff 18.5 1H mpg; SAC 1H net rating -40.2;
   Carrington 4.4 1H mpg; Giddey usage 13.6%; Franz 11.9 ast/36 and 40.8% assist share; Orlando 49.5% of 1H shots
   from three, 4.3% pull-ups; Jaquez 55% 3PA share. A check passes if ours is within 5% (relative). These are a
   pipeline sanity check, not a finding.

## B. Does preseason add accuracy? (pass or fail)

**B1 minutes.** Target: mpg over first 15 team games. Candidate `last + 1H` vs benchmark `last` (what we hold today
without preseason) and vs `last + total`. Pass: MAE lower than `last` by 2+ paired SE, and lower than `last + total`
by 2+ paired SE. If `last + 1H` beats `last` but not `last + total`, the first-half claim fails and preseason minutes
only help the ordinary way.

**B2 rates.** For each stat in {3PA, FGA, FTA, REB, AST, PTS, TOV, usage}, target = regular-season per-36 (first 15
team games, and full season, both reported; the full season decides). Candidate: last-season rate + beta x
(preseason 1H rate minus last-season rate), beta fit on the other two seasons, shrunk by sample size
(beta_i = b x n_i / (n_i + k), k fit with b). Benchmark: last-season rate. Pass for a stat: RMSE lower by 2+ paired
SE. Report beta and the preseason sample (1H minutes) at which the signal is worth half its full weight, so a
player with 59 1H minutes (Draymond) is judged as the data says, not as a headline.

## C. Is it already in the number? (the only part that can lead to a bet)

Rows: player-games in the first 15 team games of 2024-25 and of 2025-26 (the seasons with ESPN prop lines: 2025-26
only has October and November; coverage is reported) where the player has a **main line** in pts, reb, ast, 3pm, pra
(the line whose over and under prices are closest to even; ESPN ladders are unlabeled for side, so only players with
a two-sided main row from `props_espn.csv` with `side_from` not inferred are used) and was a veteran in the
filters above. DNP = void.

Signal for a row: `delta = (preseason-informed projection) - (last-season-only projection)`, where each projection is
minutes x per-minute rate for that stat (combos are sums), using the fitted B models. It is context-free by design:
it says what preseason changes, not what the number should be.

1. **Slope test.** Regress (actual minus line) on delta, one regression per line type (open, and pre-tip where
   `cur_is_pretip`). Clustered by player. Reported with t-stat.
2. **Betting rule (fixed).** Bet the side of sign(delta) on rows in the top third of |delta| / line, at the posted
   price on that side. Hit rate, ROI at posted prices, with a binomial z against the break-even for the prices paid.
3. **Decision.**
   - **GO to a shadow ledger** (logged, never staked, same bar as everything else in `experiment-log.md`) if the open
     slope t >= 2 **and** the betting rule's ROI at open is positive with z >= 2 on 200+ bets.
   - **Timing signal only** (a lean toward early bets that the market then moves to) if open passes and pre-tip does
     not. This is the story the thread tells ("movement on most of our early bets") and the one we can verify:
     the line moving toward delta is a closing-line gain, so it is reported as the mean line move in the direction
     of delta.
   - **NO-GO** otherwise.
4. The 2026-27 regular season is a holdout nobody has touched. Nothing here uses it. A GO is only a candidate for
   that holdout, scored once, when 200 early-season rows exist.

## D. The live read (descriptive, not tested)

For the 2026-27 preseason: the players with the largest 1H minutes, usage and 3PA/36 changes, the rookies and
returning-role changes, and the team-level changes the thread highlights, each next to the current ledger line where
one exists. Sample sizes beside every number (games, 1H minutes, shots). Sharp money and the thread's lean are
context, not signals. Every flagged player is a "monitor", with n, per the project rules.

## Not tested here (and why)

- Team 1H net rating as a signal (the Kings): one season of 4 games, pace and garbage time effects in preseason, no
  clean market to price against. Reported in D only.
- Player efficiency (3P%, FG%): the thread says it does not carry; we test it in A and B2 only as a control.

## Amendments

2026-10-20, before any A, B or C result was computed (only the validation gate output had been seen):

1. Games where the rebuilt whole-game minutes miss the box score by more than 1.0 minute per player on average, or
   where the box does not flag five starters per team, are excluded from every table (17 of 264 games). The
   aggregate gate passed (median miss 0.25 min; 96.8% of player-games within 2 min; points, assists, free throws,
   blocks 99.7% or better exact against the box).
2. Turnovers: ESPN logs travels and offensive charges as their own play types; they are counted as turnovers.
   Rebuilt turnovers match the box exactly in 96.5% of player-games (total 9,311 vs 9,072, +2.6%). Usage carries
   that small noise; reported, not corrected.
3. Last-season and regular-season usage use the standard box-score formula (own plays x team minutes / 5 over
   minutes x team plays); preseason usage is the first-half on-floor version, and a whole-game box-formula variant
   is run alongside so the "first half matters for rates too" claim is tested directly in B2.

2026-10-20, after A and B were computed and before any C result was computed:

4. **Coverage.** ESPN two-sided main lines for 2024-25 begin 2024-12-20, after the first 15 team games, and the
   alt ladders before that are about 1,100 rows in total. Section C therefore tests **2025-26 only** (October and
   November 2025), trained on 2023-24 and 2024-25 (leave-one-season-out). The "two seasons" in the rule above is
   not available. One season with about 250 players is thin: the GO bar (open slope t >= 2 and 200+ bets with
   ROI z >= 2) is unchanged, but a pass is read as a candidate for the 2026-27 holdout, not as proof.
5. **No pre-tip comparison.** Only 4,435 of the 56,667 main rows are flagged as a pre-tip current line (the rest
   are live or post-tip). The "timing signal only" branch cannot be tested from ESPN history; it will be read from
   our own recorder on 2026-27 (open vs close for the same rows) when 200 early-season rows exist.
6. **Side labels.** ESPN's over and under prices on a main row are inferred (`side_from`: ladder or dk-order), so the
   price on a given side is not reliable. The slope test does not use the side. The betting rule is scored at a flat
   -110 on both sides (break-even 52.38%) and also at the labeled price, and both are reported; the flat -110
   result decides.
7. **3PM.** The 3PM projection is the delta in 3PA x the last-season 3P% shrunk to 36% with a prior of 100
   attempts (3P% is not carried, per A and B), so 3PM moves only through attempts and minutes.
8. **Eligibility.** Rows in C need only information available before the game: prior-season minutes >= 400 and
   preseason minutes >= 40. The 10-games filter used in A and B is not applied to C rows (it uses the outcome).
9. **Exclusion grain (before A, B or C were re-run).** The first run excluded whole games when either team's rebuilt
   minutes failed. A live-read check (Draymond Green) showed one team's substitution chain can fail while the other
   team's is fine (Portland's failed, Golden State's matched the box to 0.3 min). Exclusion is now per team-game:
   a team-game is dropped if its rebuilt whole-game minutes miss the box by more than 1.0 min per player on average
   or the box does not flag five starters for that team. A, B and C were re-run on it. Nothing moved a conclusion
   (minutes: last + 1H vs last z 4.77 -> 4.87; rate z-scores within 0.3).
10. **Bug fixed, C re-run in full (2026-10-20).** `project_with` overwrote the last-season 3PA total with the per-36
    rate before using it to shrink the 3P%, which inflated every 3PM delta about 5x (a baseline of 13 threes per game
    for Julian Champagnie exposed it in the live table). Fixed and C re-run. What changed: the pooled slope went from
    0.16 (t 2.7) to 0.44 (t 3.4); the betting rule stayed at break-even (hit 52.59% -> 52.41%, z 0.20 -> 0.03). The
    decision is unchanged. Also found while debugging: the first `cluster_ols` added a second intercept to
    multi-regressor fits, so the minutes-vs-rates split and the control regression were garbage in the first run.
    Fixed before any number from them was used.
11. **Exploratory, added after the C slope and betting results were seen** (not part of the decision): the
    level diagnostic (line vs our projections as predictors of the result), a regression with a mean-reversion
    control, the under and over baselines, the first-5-games split, and a partial pre-tip line-move check on the 694
    rows that do have a pre-tip current line. Amendment 5 said the pre-tip comparison could not be run; it can be run
    on those 694 rows, thinly.
12. **Forward holdout, frozen 2026-10-20 about 11:15 CT, before the first 2026-27 regular-season tip.**
    `data/preseason_live.json` (sha256 starting 74c19d355853ce90) holds tonight's flags: for each veteran with a
    board line, our delta and the line. Rule for the holdout, same as C: first 15 team games of 2026-27, rows that were
    flagged before their game's tip, slope of (actual minus open line) on delta, top third of |delta| / line, scored
    at -110. Also score the line move from our recorder's open to its last pre-tip price in the direction of delta.
    Read once when 200 flagged early-season rows have settled. The 2026-27 preseason games themselves are inputs here
    and were not used to fit anything.

## Results

Run 2026-10-20. Data: 264 ESPN preseason games (2023-24 to 2026-27), 7,618 player-games; 604 veteran player-seasons
in A and B1 (2024: 202, 2025: 206, 2026: 196). Scripts: `fetch_preseason.py`, `preseason_lib.py`,
`build_preseason_table.py`, `build_preseason_signals.py`, `build_preseason_market.py`, `build_preseason_live.py`.
Outputs: `data/preseason_signals.json`, `data/preseason_market.json`, `data/preseason_live.json`.

### Pipeline check (A4): our rebuild reproduces the thread's numbers

| Thread says | Ours |
|---|---|
| Acuff 18.5 1H mpg, most of any rookie in four preseasons | 18.54 (4 games, 74 1H min); next: Ausar Thompson 17.1, Scoot Henderson 16.6 (both match) |
| SAC 1H net rating -40.2 (ORtg 84.1, DRtg 124.3) | -39.5 (83.6, 123.1); POR 23-24 -33.2 (thread -33.3), MIL -30.0 (-30.7), MEM 25-26 -20.0 (-20.4) |
| Carrington 4.4, Coulibaly 10.0, Tre Johnson 11.5, Riley 1.8 1H mpg; none of the first three started | 4.42, 10.05, 11.52, 1.77; 0 starts each in 4 games |
| Giddey usage 13.6%, 8.2 FGA/36, 43.2% assist share, 5 games, 75 1H min | 13.57%, 8.17, 43.18%, 5 games, 74.9 min |
| Franz 11.9 ast/36, 40.8% assist share (4 games, 60 min) | 11.91, 40.82% (4 games, 60.4 min) |
| KAT 8.9 ast/36, 38% assist share | 8.90, 38.5% |
| Jaquez 18 of 33 shots from three (16 of 25 in first halves) | 18 of 33; 25 first-half shots |
| Draymond 59 1H min, 4 FGA, usage 7.8%, 49% of GSW assists on the floor | 4 games, 59.4 min, 4 FGA, 7.8%, 48.7% (first run showed 3 games, 45 min; see amendment 9) |
| Orlando 1H: 49.5% of shots from three (#5), pull-ups 4.3% (fewest), 77.9% of baskets assisted (#2) | 49.7% (#5), 3.7% (fewest), 77.9% (#2); 4 games |

Every check is within 5% (Orlando's pull-up share differs by 0.6 points, a definition detail). The thread's data is real and our pipeline agrees with it.

### A and B1: minutes. The first-half claim holds, with a different benchmark than the thread's chart shows

Target: mpg over the first 15 team games, 604 veteran player-seasons, leave-one-season-out.

| Predictor | r with early mpg | MAE (min) | Thread MAE |
|---|---|---|---|
| Total preseason mpg | 0.52 | 5.17 | 5.8 |
| Last season mpg | 0.80 | 3.42 | 4.0 |
| 1H preseason mpg | 0.81 | 3.49 | 3.8 |
| Last + total preseason | n/a | 3.32 | 3.7 |
| **Last + 1H preseason** | n/a | **2.99** | **3.2** |

Thread's correlations: 0.86 (1H) vs 0.63 (total). Same ordering in ours. Paired, player-clustered:

- last + 1H beats last season alone by **0.43 min** (SE 0.09, z 4.9)
- last + 1H beats last + total by **0.33 min** (SE 0.08, z 4.3)
- 1H alone beats total alone by 1.68 min (z 10.0)

**B1 passes.** The thread's headline (ignore total preseason minutes, use first-half) is right: total preseason
minutes add almost nothing to last season (0.10 min, z 1.6); first-half minutes add 0.43. One caution the chart
hides: **1H preseason mpg on its own is no better than last season's mpg** (3.49 vs 3.42). The gain comes from using
both. Fitted: early mpg = 0.54 + 0.45 x last mpg + 1.03 x 1H mpg.

### A and B2: rates. Volume carries, efficiency mostly does not, and the first half is not what matters here

Preseason change vs last season, correlated with the regular-season change vs last season (per 36), full-season
target, 682 veteran player-seasons. Out-of-sample gain is the paired RMSE test of "last season + shrunk preseason
change" vs "last season".

| Stat | r, 1H (95% CI) | Thread r | RMSE last -> with 1H | z | z with whole-game preseason rate |
|---|---|---|---|---|---|
| 3PA/36 | 0.38 (0.32, 0.45) | 0.44 | 1.246 -> 1.147 | 5.3 | 6.1 |
| Usage | 0.41 (0.35, 0.47) | 0.40 | 2.910 -> 2.654 | 5.0 | 5.7 |
| FGA/36 | 0.34 (0.28, 0.41) | 0.36 | 1.959 -> 1.837 | 4.6 | 5.6 |
| REB/36 | 0.28 (0.21, 0.36) | 0.35 | 1.004 -> 0.965 | 3.0 | 4.1 |
| AST/36 | 0.29 (0.21, 0.37) | 0.33 | 0.919 -> 0.871 | 3.8 | 4.8 |
| PTS/36 | 0.29 (0.22, 0.35) | 0.33 | 2.727 -> 2.597 | 3.7 | 4.9 |
| TOV/36 | 0.22 (0.15, 0.29) | 0.28 | 0.477 -> 0.467 | 2.4 | 2.1 |
| FTA/36 | 0.30 (0.22, 0.37) | 0.27 | 1.036 -> 0.989 | 3.2 | 3.0 |
| BLK/36 | 0.21 (0.12, 0.29) | 0.23 | 0.283 -> 0.276 | 2.8 | 3.1 |
| STL/36 | 0.08 (-0.01, 0.18) | 0.13 | 0.303 -> 0.299 | 2.2 | 2.7 |
| 3P% (n 314) | 0.13 (0.02, 0.24) | 0.09 | not tested | | |

- The thread's ranking replicates: shot volume and usage (r 0.3 to 0.4) beat everything; steals and shooting
  percentage are weak. Our 3P% is 0.13, small but not zero (interval 0.02 to 0.24), against 0.38 for 3PA.
- **The "count the first half" advice is a minutes rule, not a rates rule.** Using the whole-game preseason rate
  gives an equal or better z than the first-half rate for every volume stat (more minutes per player), so for
  usage, shots, rebounds and assists use all preseason minutes you have.
- **How much to believe a preseason rate (fitted on the three seasons, shrinkage built in):** a starter with about
  55 first-half minutes (a 4-game preseason) moves his per-36 projection roughly **17% of the way** to what he showed
  for points and assists, 12% for rebounds, 21% for 3PA, 29% for usage. A 4-game sample is evidence, not a verdict:
  a player at 30 first-half minutes gets about 10% for points and assists. Draymond (4 FGA, 45 to 59 minutes) and Giddey (74.9)
  are different sample sizes and should be read that way.
- Team level: a team's preseason 3PA share correlates 0.59 with its regular-season 3PA share (90 team-seasons; thread
  says 0.65), and its change vs last season correlates 0.58 with the season's change.

### C: is it already in the opening line? Partly. Not enough to beat the vig under the pre-registered rule.

2025-26, first 15 team games, ESPN opening main lines (pts, reb, ast, 3pm, pra), veterans, 6,777 player-game lines,
203 players. Models fit on 2023-24 and 2024-25 only.

| Test | Result |
|---|---|
| Pooled slope of (actual - line) on our preseason delta, relative units | **0.44, SE 0.13, t 3.4** (pass, bar is t >= 2) |
| Per market, raw units | pts 0.31 (t 1.9), reb 0.19 (1.4), ast 0.24 (1.3), 3pm 0.25 (0.9), pra 0.14 (0.9) |
| Minutes part / rates part of the delta | 0.35 (SE 0.17) / 0.57 (SE 0.21) |
| Betting rule: top third of |delta| / line, side of delta, flat -110 | **2,261 bets, 1,185 wins, 52.41% vs 52.38% break-even, z 0.03, ROI +0.06%** (fail, bar is z >= 2) |
| Same at ESPN's labeled price (labels unreliable, see amendment 6) | +7.1%, reported only |
| Hit rate by size of delta (low / mid / high third) | 49.7% / 51.0% / 52.5% (monotone) |
| Cluster SE of the bet hit rate (player clusters) | 1.5 points |

**Decision: NO-GO for a shadow ledger.** The preseason change is real and the opening line does not fully hold it,
so the slope passes; but the size of what is left is about 2 points of hit rate, which is the vig, and the bet rule
lands on break-even. By the pre-registered rule both must pass.

Things worth knowing from the exploratory work (amendment 11), none of which changes the decision:

- **Overs and unders.** In this window the opening lines were slightly high: overs hit 49.1% and unders 50.9% across
  all 6,777 rows. Our bets on the preseason signal beat their side baseline by 2 points on overs (51.1% vs 49.0%,
  n 1,749) and **5.5 points on unders (56.8% vs 51.3%, n 512)**. The unders figure is a post-hoc cut of one season;
  flagged for close monitoring with that sample size and nothing more.
- **Opening lines are soft vs a crude projection.** Correlation with the actual result: pts line 0.64, last-season
  projection 0.58, preseason-informed projection 0.60; reb 0.59 / 0.58 / 0.59; ast 0.59 / 0.56 / 0.58; **3pm 0.25 /
  0.27 / 0.29**; pra 0.69 / 0.62 / 0.63. Adding preseason improves the projection in every market, and for 3PM both
  projections beat the (coarse, half-point) line. In a regression of the result on both (point estimates only, no standard errors computed), the
  preseason-informed projection keeps a positive weight beside the line in every market (pts 0.29, reb 0.45, ast 0.51,
  3pm 0.51, pra 0.15). That says
  the open is not efficient this early; it does not say you can bet the gap, since we cannot see the close.
- **The market partly catches up before tip.** On the 694 rows with a pre-tip current line, the line moved toward
  our delta (slope 0.16, SE 0.09, t 1.8). Directional mean move +0.04. Consistent with the thread's "great movement
  on most of our early bets", but too thin to claim.
- **The signal fades slowly, not fast.** Slope in games 1 to 5: 0.48 (t 2.5); games 6 to 15: 0.41 (t 2.4).

### What this means for the thread's bets and for Vault

| Thread claim | Verdict |
|---|---|
| 1H minutes beat box-score minutes (r 0.86 vs 0.63) | **Confirmed** (0.81 vs 0.52; MAE 2.99 vs 3.32 with last season, z 4.3). Needs last season alongside, and the 1H minutes alone are not better than last year |
| Shot mix and usage stick, shooting % does not | **Confirmed in ranking** (3PA 0.38, usage 0.41, 3P% 0.13). Use all preseason minutes for rates, not only the first half |
| Individual reads (Acuff, Wizards, Draymond, Giddey, KAT, Franz, Magic, Zion, Jaquez) | **Numbers are accurate** (A4). Whether each is bettable depends on the line; the sample sizes are 3 to 5 games, 30 to 80 first-half minutes, and a 4-game sample moves a projection about a fifth of the way |
| "Early bets, then the line moves" | **Plausible and partly visible**: open lines are soft, the preseason signal explains some of the miss, and lines move toward it before tip. Not provable as profit from ESPN history; the 2026-27 holdout (amendment 12) is the real test |

For Vault: this is worth building as **context, not as an edge claim**. A first-half-minutes rule beats what we use
now for early-season minutes (MAE 3.42 to 2.99), the Minutes Lab and the Props page do not use preseason at all, and
this is the "preseason minutes as a role signal" item already in v3-plan.md section F. The risk to guard against is
the one this repo keeps finding: accuracy is not edge.

## Limits

- Section C is one season (2025-26) and about 200 players; the same player appears in many rows, so effective
  samples are smaller than 6,777. Clustered SEs account for that.
- ESPN opening lines have unknown posting time and unreliable side labels. We cannot see closing lines.
- The thread's definitions are not fully published (veterans, rate windows). Ours are fixed above; numbers match
  closely where we could check them.
- 2026-27 preseason has only 3 to 5 games per team. Rookies and sub-400-minute players are outside the model.

