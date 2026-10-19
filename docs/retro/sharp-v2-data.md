# Sharp Money V2 data PR: independent prop close, reference test, ledger history

Date: 2026-10-18. Follows `docs/retro/sharp-v2-evidence.md` (PR #133). Full tables: `docs/retro/prop-clv-regrade.md`, `docs/prop-clv-regrade.json`.
Rerun: `python3 scripts/regrade_prop_clv.py` (reads `origin/sharp-data`).

## What changed in the numbers

The stored prop CLV was measured against the same Pinnacle fair that raised the call. It is now also measured against the exchange close (mean of Kalshi and
Novig at the call's exact line, read from `prop_close_tape.json`, nothing older than 180 minutes before kickoff). The old field `clv` is kept unchanged so
nothing downstream breaks; the new field is `clvX`.

| Prop record | Old (self-referenced close) | New (exchange close) |
|---|---|---|
| All calls with a close | CLV +2.72% on 1,326 calls, 77.9% positive | **+0.10% on 527 calls, 49.7% positive** |
| Same 449 Pinnacle-fair calls that have an exchange close | +2.01% | **+0.10%**, 218 of 449 beat the close |
| Same 374 calls with both closes | +1.74% (stored) | +1.21% against their own Pinnacle close, **+0.40% against the exchange close** |
| Clean (not 10%+ edge) | +2.44% on 1,268 | -0.09% on 511 |
| Big (10%+ edge) | +8.9% on 58 | +6.0% on 16 (flag: 16 calls) |
| Hit rate minus exchange close | not measured | -5.7 points (z -2.4) |

History fix: running the re-grade over the live ledger sets `clvX` on 527 started calls today. 568 graded calls have no close-tape entry (they predate the tape) and keep
their old CLV only, labelled self-referenced. The 1,326-call ledger itself (results, units, ROI) is unchanged: ROI stays -6.4%.

## Which close is sharpest (the reference test)

Log loss of each reference's P(over) against the box score, same rule as `compare_prop_closes.py` (paired bootstrap 95% CI, called only if the CI
excludes zero and n is at least 150):

| A vs B | Shared props | Gap (A minus B) | 95% CI | Read |
|---|---|---|---|---|
| Exchange vs Pinnacle | 380 | -0.0020 | -0.0048 to +0.0007 | no difference |
| Exchange vs US books | 226 | +0.0019 | -0.0059 to +0.0092 | no difference |
| Pinnacle vs US books | 212 | +0.0024 | -0.0050 to +0.0101 | no difference |
| Sharp3 vs Pinnacle | 382 | -0.0012 | -0.0029 to +0.0005 | no difference |
| Novig vs Pinnacle | 377 | -0.0027 | -0.0057 to +0.0003 | no difference |

The exchange close points the right way (lower log loss than Pinnacle) but not enough to call. **The rule says: do not swap the reference.** What the
test does show is that none of the closes is a good predictor: every one of them beats a coin flip (log loss 0.6931) by only 0.006 to 0.017 at these prop lines.
So V2 will not label any prop price "fair" on one source. It shows the exchange close and Pinnacle side by side and only calls a price
"confirmed" when the price beats both.

## Does beating the independent close go with winning?

Hindsight check on the close, not a rule usable at call time (flat 1u, 460 graded calls with an exchange close):

| Calls that | Calls | Hit | ROI |
|---|---|---|---|
| beat the exchange close | 225 | 45.3% | -7.6% |
| missed the exchange close | 235 | 43.0% | -13.3% |
| beat it by more than 2% | 165 | 48.5% | -1.5% |
| beat both exchange and Pinnacle closes | 177 | 46.9% | -5.0% |
| beat neither | 124 | 41.1% | -19.4% |

The ordering is right (beating the close goes with winning more), which supports using the independent close as the scorecard. But even the best
slice does not earn its price: the standard error on 165 calls is about 7 points of ROI, so none of these separate from zero.

**Flag for close monitoring (small samples):** calls that beat the exchange close by more than 2% (165 calls, 48.5% hit, ROI -1.5%); rush-attempt unders
against the exchange close (22 calls, CLV +4.96%, 54.5% hit); big-edge calls against the exchange close (16 calls, CLV +6.0%).

## What the code now does

- `scripts/regrade_prop_clv.py` re-grades and writes `closeX`, `clvX`, `closeXSrc` onto started plays, and stamps `atCall` (Pinnacle, exchange, books and
  Sharp3 fair for the call's side at first sight) on new calls, so the next test can ask what each reference said at the moment of the call. It only ever
  writes those fields. `update-sharp-money.yml` runs it before and after the poll (`continue-on-error`).
- `scripts/track-prop-plays.mjs` `recordOf` reports `clvXN`, `clvX`, `clvXPos` next to the old `clvN`, `clv`, `clvPos`. The classic page and `new/` do not read
  the new keys yet; V2 does.
- `scripts/snapshot_sharp_ledgers.py` and `.github/workflows/snapshot-sharp-ledgers.yml` copy the four ledgers (prop calls, graded picks, +EV alert history, prop close
  tape) once a day onto `sharp-history`, an ordinary branch that is never force-pushed. It refuses to write, and exits 2, if an id from the previous
  snapshot vanished (tape entries past its own 150-day prune excepted) or a settled row went back to open.
- `tests/test_sharp_v2_data.py` covers the exact-strike and staleness rules, the under complement, the write-back, and the snapshot guard.

Correction to the plan: the prop and pick ledgers are carried forward run to run, so history was not being lost. The risk was a single copy on a
force-pushed branch, which is what the snapshot removes. The graded picks only start on 2026-10-10 because that is when the frozen ledger began.

## Limits

- 449 to 527 calls with a usable exchange close, one short window, mostly two weeks of one NFL and college slate.
- The exchange close is Kalshi and Novig where their ladder has the exact strike; a call at a line they do not list gets no `clvX`.
- Positive `clvX` is still a price test, not a result. ROI on the calls is unchanged and negative.
