# Sharps V2 Move grade mg-1: pre-registration

**Status: Registered (approved by the user in chat, 2026-11-24).** The commit that changes this line to Registered is the
registration, and the first play that can count is the first one cut after it (`REGISTERED_CUT` in `scripts/sharps_v2/move_grade_record.py` holds that commit's time in epoch seconds). The registered `docs/sharp-tier-v2-prereg.md` is frozen and is **not edited** by this file: the
text below is a separate, dated section in its own file, so no registered rule changes (the user can ask for it to be appended there instead). The build that logs the grade at
lock (`scripts/sharps_v2/move_grade.py`, the `mg` key of the `v2_tier` rows) exists before the registration, so a row logged before the registering commit exists but cannot count. In code, `REGISTERED_CUT` in `move_grade_record.py` was None until the user registered, which kept the forward record at zero; it is now the registering commit's time.

Spec: `docs/sharps-v2-movegrade-spec.md`. Code: `scripts/sharps_v2/move_grade.py`; the cutoffs and the in-sample record are reproduced by `scripts/sharps_v2/move_grade_history.py`;
the record file is `scripts/sharps_v2/move_grade_record.py`.

---

## Move grade mg-1 (shadow, proposed 2026-11-23, Registered 2026-11-24)

Added by the user's decision of 2026-11-23. Rule id `mg-1`, spec `docs/sharps-v2-movegrade-spec.md`, code `scripts/sharps_v2/move_grade.py`
(cutoff tables `MG_M_A`, `MG_M_C`, `MG_X_A`, `MG_X_C`, frozen at the registering commit). This registration changes no earlier rule of the registered
`docs/sharp-tier-v2-prereg.md`: v2t-1, v2s-1 and v2f-2 and their thresholds, metrics, dates and kill rules stand as registered. Any change to a cutoff, an input or a branch of
mg-1 after registration is a new rule id (mg-2) and a new registration; old rows stay read as written.

What it is. A per-play letter A, B, C or D saying how far the market moved toward the play's side in the 24 hours before the cut, from the
registered v2f-2 Flag A (Pinnacle's no-vig price at the same line) and Flag C (the market's main line, or the books' price on a moneyline) only.
A = a flag fired toward and the move passed the A mark (the 95th percentile of the absolute 24-hour move for the sport and market, at least half a
point past the flag threshold); B = a flag fired toward; C = no flag fired, Pinnacle's price or line moved toward by at least the median 24-hour move
and not that far away; D = otherwise. Any flag fired away gives the "moved against" marker and no letter. Neither flag readable gives no grade.
Pinnacle's limit is never an input. Cutoffs were set from the distribution of moves on every started game of the tape (origin/main a6b75ea6c404,
2026-11-23 6:28 PM CT), never from results.

Context only. The grade never changes the shown size (flat 1u on NBA, NFL and CBB, none on CFB, "untested rule"), the shadow size v2s-1, the
evidence tier, the ladder, sf_rungs, the gates or the locks, and it never feeds Top Reads, SM_GATE or an agree total. Passing this test only lets
the user consider calling the grade tested, as a separate decision. It does not make one.

Logged at lock. New rows of pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl carry `mg`, a projection of the frozen card's stored v2.move_grade. The
first play that can count is the first one cut after the registering commit. A forward row is read as written (no staleness rule, as for mf).
Old rows without `mg` are "not logged", never D.

Primary metric: the market move after the cut. after = Pinnacle's no-vig fair for the side at the last tape row at or before game start (the
pinclose row) minus its no-vig fair at the cut, in points, same line (a play whose close is at a different line is left out and counted apart).
Plays with price_src == "pin" are left out and reported apart. Statistic, per sport, never pooled: the least-squares slope of after on the letter
score (D = 0, C = 1, B = 2, A = 3) over plays with a letter, 95% percentile bootstrap, 10,000 resamples, seed 20261111, resampling plays. The
"moved against" group is read apart: mean after of "moved against" minus mean after of D, same interval, report only.

Why not CLV as the primary. CLV (Pinnacle's no-vig close minus the stored Polymarket price at the cut) contains Pinnacle's fair at the cut, which
Flag A and therefore the letter are built from, so a letter could "win" on CLV without the market moving after the cut (the same overlap the
v2f-2 section removed). CLV stays as a secondary, labelled as overlapping by construction.

Secondary (reported, never a pass condition): CLV per letter (overlapping), flat 1u ROI per letter at the stored price at the cut
(move_grade_record.json), and the after-cut mean per letter. Expected in advance: the after-cut window is 15 minutes, and 91 of the 143 graded
plays with a readable after-cut move had a move of exactly 0, so the metric has a low spread and most of its information comes from the minority
of games that move in the last 15 minutes.

Minimum n before any verdict, per sport: 300 plays with a letter and a readable after-cut move, and at least 30 in each of A, B and C and 100 in
D. With the population letter shares (A 5.5%, B 14.5%, C 20.9%, D 59.0% of lettered sides) the letter score has a standard deviation of 0.92; with
the after-cut standard deviation measured on the graded headline plays (0.49 points, n=78), 300 plays give the slope a standard error near 0.031
points per letter step, so 80% power at 95% confidence to see a slope of about 0.09 points per step. A needs about 550 lettered plays in a sport to
reach 30, so the honest expectation this season is Underpowered in every sport, said here in advance.

Final reads: the same dates as the tier registration above (NBA: the first Monday after the 2026-27 regular season; NFL: the Tuesday after Week
18; CFB: the Monday after conference championship weekend; CBB: the Monday after the 2027 national championship game). Monthly interim reads
are report-only and can neither pass nor fail a sport; repeated looks do not add up to a pass.

Pass (per sport): the lower 95% bound of the slope is above 0 with every minimum met. Fail: every minimum met and the lower bound at or below 0:
the letter comes off the page at the final read (logging continues to the end of the season), and the "moved against" marker stays only as the
v2f-2 flag it already is. Underpowered: any minimum short at the final read; neither pass nor fail, and the read says which group was short and
by how much.

Data quality, no verdict for the sport: more than 5% of forward mg rows whose letter differs from move_grade() re-run on the same frozen card's
stored v2.flags, or more than 10% of forward rows with mg null for a reason other than side_unmapped.

What every read reports: n per letter and per sport, the plays with no grade by reason, win-loss and flat ROI with standard errors, the after-cut
and CLV means with intervals, the "moved against" read, the CFB read (no size shown) apart, and every cell that improves (units above 0) flagged
for close monitoring with its n (small sample under 30), never promoted on the same data.

In-sample record (not evidence): docs/side-card-record.md, "Move grade mg-1". On the 205 graded plays, read point in time, the letter did not
order results (headline A 4-3 +0.22u n=7, B 7-2 +2.91u n=9, C 10-4 +7.58u n=14, D 28-21 -3.37u n=49, moved against 11-8 +1.32u n=19) and
the after-cut slope was -0.002 (interval -0.099 to +0.098, n=78).
