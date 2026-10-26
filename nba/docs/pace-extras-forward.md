# Pace term for blocks (and steals): a forward-only test, registered before anything is built

Written 2026-10-26. Nothing here changes what the page shows, prices or bets. The rules below are the verdict. Every result is reported, pass or fail.

## Why this question exists

`matchup-stl-blk-tov-results.md` found, as context with no verdict, that a **pace-only** term beat the bare projection (minutes x shrunk rate) for blocks (gain +0.00069, t 4.36) and steals (+0.00045, t 3.43) on 2025-26, with the slope fitted on 2024-25 and frozen. It did not help turnovers (t -3.50).
Blocks failed the matchup test, so blocks have **no opponent or pace term at all** today. Steals already carry pace inside the joint pace + steal-matchup term (pace slope -0.0515 there, which is about zero), so for steals the pace-only form is an alternative to that term, not an addition.

That finding was **not a registered test**: it had no pass rule, no control and no halves check. And 2025-26 has now been read many times. So the claim needs its own test, on data nobody has read.

## Why forward only

- Older seasons are not clean. The minutes model was fitted on 2023-24 with who actually sat, so 2023-24 is in-sample for the baseline; 2022-23 is the warm-up. 2025-26 has been read for this exact question.
- The only unread data is the 2026-27 season, from the first night the record carries the column (below).

## Frozen terms (fixed now, never refitted)

`mp = mu0 x (clip(1 + b x Pace, 0.7, 1.3) - 1)`, where `mu0` = projected minutes x the player's Minutes Lab rate (the same `mu0` the xstat record already logs), `Pace` = the opponent's possessions per 48 against the league (`data/team_allowance.json`, point-in-time, last season blended in until 15 games).

| Stat | b (pace-only slope, fitted on 2024-25 alone, `matchup_stl_blk_tov.json` `b_pace_only`) |
|---|---|
| Blocks | **+1.9282** |
| Steals | +1.1992 |

Turnovers get no pace-only term (the historical context said it hurts).

## What gets recorded

`xstat_record.py` logs a fourth value `mp` per player-game-stat, for steals and blocks (blocks are added to the record; steals and turnovers already are). It is the last pre-tip value, settled against the box score, exactly like `mt`. Rows from before this merge have no `mp` and are never scored in this test. The existing steals and turnovers matchup read is unchanged: it scores `mt` only and ignores blocks.
Because the record is pre-tip snapshots, earlier nights cannot be reconstructed honestly, so there is **no backfill**; the test starts at the first night that carries `mp`.

## Forward rule (blocks has the verdict; steals is context)

Population: rows with `mp` for blocks, minutes above zero, last pre-tip row. gain = `|actual - mu0| - |actual - (mu0 + mp)|`; game as the unit; bootstrap 2,000 draws, seed 7; t = mean / sd of the bootstrap means.

- **Power, stated honestly.** The historical t of 4.36 on 28,252 rows implies about 9,300 rows to expect t 2.5. At roughly 200 block rows a night that is about 47 nights. Reading earlier would mostly measure noise.
- **Read once**, on or after **2026-12-21**, and only with **at least 7,000 rows and 40 nights**. If the counts are short on that date the read waits.
- **KEEP** (blocks get a pace term, wiring registered separately before anything is built) needs all of: gain > 0 with **t >= 1.65** (one-sided; the slope is frozen and the direction was found on a different season); both halves of the nights (earlier half, later half) positive; and the **dose response** by index fifth monotone-ish: the top fifth's residual share above the bottom fifth's.
- **DEMOTE** otherwise: no pace term for blocks, and this is recorded.
- **Early stop** (checked monthly): gain negative with t <= -2.5 demotes at once.
- **Steals:** the same population and gain are reported against the bare projection, and against the live joint term (`mt`) on the same rows. **No verdict**; it only says whether pace-only is a better steals form than the joint one. The steals joint term keeps its own read (`matchup-extras-wiring.md`).

## Not scored

A pace slope refit on any 2026-27 data, other pace forms (tempo from the line, projected total), pace on other extra stats, blocks matchup indices (already failed), any price or ROI measure (no price history for these markets).

## If blocks are kept

Registered before it is built: a frozen-slope blocks pace term through the extras' own path in Python and the page, with a kill switch in `data/pace_terms.json`, a parity check, and the same forward record continuing to run.

## Reading rules

Nothing under 100 rows is quoted as a rate. A positive cell is flagged for close monitoring with its sample size. Sharp money is not an input. The 2025-26 pace-only result is disclosed above as already seen; it is the reason for the direction, not evidence for the keep.
