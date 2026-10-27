# Pick'em of the Night V2: verdict NO-GO (no profitable method found)

Run 2026-10-27 (Central). Code: `scripts/build_pickem_v2_data.py` (dataset), `scripts/backtest_pickem_v2.py` (walk-forward test).
Data: `data/pickem_v2_legs.json` (13,635 stored app quotes, regular season only), results `data/pickem_v2_backtest.json`.
Places to play are DFS pick'em apps only (PrizePicks, Underdog). Sharp closes are a fair-price reference, never a place to bet.

## 1. Why the old page lost

Record (`track.json` `pkn_days`, 6 tip days, Oct 20-26): 77 slips, 6 won, **-71% per $1** (2-pick 4 of 18, 3-pick 2 of 18, 4/5/6-pick 0 of 41).

| | old number | what it should have been |
|---|---|---|
| Hit rate of the 90 distinct legs it chose | **44.4%** (95% range 34.6% to 54.7%) | it claimed 66.2% on average |
| Rebound unders (41 legs) | 39.0% | claimed 67.9% |
| Legs the moved-consensus rated 60%+ (stored, n=151) | **43.0%** | claimed 63.7% |

Causes, in order of size:
1. **The chance was wrong, and wrong most where it was highest.** The page's "market chance" is the consensus of other venues moved to the app's line through the model's distribution shape. Ranking legs by it picks exactly the lines where that move is largest, which are the lines where the move is least reliable. A de-vigged Pinnacle price at *exactly* the app's line is calibrated (bucket 0.4: 41.3% hit vs 42.2% fair; 0.5: 48.0% vs 49.8%; 0.6: 55.6% vs 57.1%). The moved number is not (0.6+: 43.0% vs 63.7%).
2. **No leg is close to the pay table.** App lines sit on the sharp number (PrizePicks standard lines match Pinnacle's line 660 of 1,159 times, the rest within 1 point), so a typical leg is 50-53% fair. The pay tables need 54.2% to 59.1% per pick (section 3). Greedy "top n by claimed chance" therefore buys the model's own error.
3. **Bigger slips compound it.** A 6-pick at 37.5x needs 54.7% per pick; the page's picks hit 44%, so 41 slips of 4+ picks won none.
4. Not a cause (checked): demon and goblin lines. The board only reads PrizePicks `standard` lines. They are skewed (demon overs hit 22.3%, goblin overs 64.5%, n=12,877 / 9,127) and their payouts are not stored, so V2 does not use them.
5. Not a cause: correlation. Slips already use one player per team, and different-team legs tested independent (docs/pickem-different-teams.md).

## 2. Data inventory (all stored, nothing estimated)

- App lines: `snapshots/<day>/prizepicks.jsonl` (flat, with `odds` standard / demon / goblin), `underdog.jsonl` (line, American price each side, multipliers), `sleeper.jsonl` (decimal price each side). Last quote before tip is the entry price.
- Sharp reference: `propclose.json` per game: de-vigged chance per player-stat line, tagged `pin` (Pinnacle), `mkt` (stored consensus), `kal`. Used only at an app's exact line, never interpolated.
- Outcomes: `results/<game>.json` box scores. Ties are pushes and are excluded from legs.
- Not joined: Sleeper (its feed carries no tip time or ESPN id, so quotes cannot be tied to a game from the stored fields). Preseason (no Pinnacle player closes before Oct 20). Demon and goblin (payout not stored).
- Rows with a Pinnacle number at the app's exact line: 1,695 distinct legs (Oct 20-26). With the consensus number: 3,176.

## 3. Break-even per leg (independent legs)

| size | power | flex |
|---|---|---|
| 2 | 57.7% | n/a |
| 3 | 58.5% | 59.1% |
| 4 | 56.2% | 56.9% |
| 5 | 54.9% | **54.3%** |
| 6 | 54.7% | **54.2%** |

Power = the repo's table (3, 5, 10, 20, 37.5x). Flex tables: 5-flex 10x / 2x / 0.4x reproduces `pricing.PK_BE` (54.25%) exactly; the 3, 4 and 6-flex rows use the published PrizePicks flex table and are not stored in the repo, so treat them as reference. Underdog and Sleeper entries can carry their own per-leg multipliers; the test therefore only admits Underdog legs priced 44-56% on the chosen side (the page's own rule).

## 4. Walk-forward test (rules frozen before the holdout was scored)

- Legs: PrizePicks standard + Underdog, with a reference chance at the exact line; side = the side the reference likes.
- Candidates: reference (Pinnacle or consensus) x threshold (50, 52, 54, 56%) x format (power 2-6, flex 3-6).
- Train: tip days Oct 20-23. Holdout: Oct 24-26. Selection: best train slip ROI with >= 100 train legs. GO = holdout ROI lower 95% bound above 0 with >= 100 legs; WATCH = holdout and train point ROI both above 0; else NO-GO.
- Slip ROI follows from the leg hit rate because legs are independent; the interval is the Wilson interval on the hit rate pushed through the pay table.

Selected on train: **Pinnacle side at 50%+, 6-pick flex** (break-even 54.2%).

| | legs | hit | 95% hit range | slip ROI | 95% ROI range |
|---|---|---|---|---|---|
| Train (Oct 20-23) | 856 | 56.1% | 52.7% to 59.4% | +18.4% | -12.8% to +57.7% |
| **Holdout (Oct 24-26)** | **839** | **53.8%** | 50.4% to 57.1% | **-4.1%** | -30.3% to +29.7% |

**Verdict: NO-GO.** The holdout is below break-even and its interval spans a large loss and a large gain.

Descriptive (not selected, so not evidence): the Pinnacle side with 54%+ looks best on the holdout (125 legs, 61.6% hit) but lost on train (119 legs, 48.7%). The consensus (moved) number at 60%+ hit 43% in both halves. Every other cell is in `pickem_v2_backtest.json`.

## 5. What is worth watching (not a method yet)

Pinnacle's favoured side at the app's exact line hit **54.9%** across all 1,695 legs (95% 52.5% to 57.3%) against a mean fair of 52.3%, so it beat its own price by 2.6 points (about 2 standard errors). That is above the 5/6-flex break-even, but the interval includes it, the train/holdout halves disagree, and one week of one regular season is the whole sample. **Flag for close monitoring: Pinnacle-exact-line favourite, 5/6-pick flex, n = 1,695 legs, 7 tip days.** It must not be called a Lean until a fresh holdout agrees.

Forward test, frozen now: the same rule (Pinnacle side at 50%+, exact line, PrizePicks standard + Underdog priced 44-56%, 5 or 6-pick flex). Rerun both scripts on `nba-data` after tip days from 2026-10-27; **GO** needs >= 400 new legs and a holdout lower bound above break-even (54.2%); until then the page shows every slip as a Pass. No cron is added; it is a manual rerun.

## 6. What changed

Model/data: new dataset and backtest scripts and files above. `pickem_record.py` and `track.json` `pkn_days` are **unchanged**: they stay a record of what the old page built (77 slips, -71% per $1), and its stored `call` field still says lean/pass under the old rule. There are no new tracked rows, so nothing historical needed repair.
UI: every Pick'em of the Night slip is a Pass (was Lean when average per $1 >= 3%); new V2 verdict card at the top; "Market chance" column renamed "Claimed chance".

Sharp money is context only here: the Pinnacle number is a price reference, not a signal, and counts toward no agree total.
