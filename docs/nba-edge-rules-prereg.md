# NBA prop edge rules: pre-registered forward test

Written on 2026-11-18 (Central), before any forward day was read. The commit that adds this file is the registration. Nothing below
may change once the first forward day is read. A change means a new registration with its own date; the old one is still read exactly
as written. The rules are read by `scripts/nba_edge_rules_read.py`, which only reads `nba/data/track.json` and changes nothing.

## Why

The Track Record shadow ledger (every prop with at least a 3% edge at entry, flat 1u, all venues and sides) is 92,636 bets at -5.1% ROI,
about the vig. A diagnostic on 2026-11-18 found the claimed edge does not rank bets: 12%+ edges win 49.2% and return -6.6%, while 3-12%
edges win 51.3% and return -4.8%. Three candidate rules came out of that look. **All three were found in-sample, in a large search, so
none is trusted.** This registers them for a forward-only read.

## Scope and limits

- **Shadow only.** These rules tag existing shadow bets. They change no price, grade, gate, Top Reads entry, SM_GATE copy or record.
  No historical row is edited, so no backfill is owed.
- **Not a bet signal.** Passing means "propose a change to the model/gates in a separate PR", never "bet this". Every group here is
  expected to stay at or below 0% ROI; the test is about *relative* ranking against a control.
- Forward window: game days **2026-11-19 through 2026-12-09** (Central). One read, on or after **2026-12-10**. No early peeks that
  change anything, no extending the window to chase a pass. If a rule is short of its minimum n, it is reported **inconclusive**.
- Only the three rules below are read. No other slice of the forward data is promoted from this test.

## Baseline (in-sample, through 2026-11-18, entry ROI, flat 1u)

| Group | Bets | ROI (95% +/-) | Win |
|---|---|---|---|
| R1 12%+ edge | 15,362 | -6.6% (1.4) | 49.2% |
| R1 control: 3-12% edge | 77,274 | -4.8% (0.7) | 51.3% |
| R2 both sources agree | 6,873 | -3.7% (2.1) | 51.6% |
| R2 control: gap or model alone | 85,763 | -5.2% (0.7) | 50.9% |
| R3 cells at 12%+ | 3,052 | -12.9% (3.3) | 46.1% |
| All bets | 92,636 | -5.1% (0.6) | 51.0% |

R2's in-sample gap is only 1.5 points against a half-width of 2.1, so it is the weakest of the three. The 12%+ "both" slice looked
better (-0.8%, 2,556 bets); it is a sub-slice of a search and is **not** what is registered.

## Rules (frozen definitions)

Groups use the cube's `ebin`, `etype`, `stat` and `side`, at the entry price already stored. Pushes and voids follow the ledger.

**R1: Edge cap.** Group = `ebin` is `12%+`. Control = `ebin` in `3-5%`, `5-8%`, `8-12%`.
Pass if forward ROI(12%+) is at least 1.0 point below ROI(control) **and** win rate(12%+) is not above win rate(control), with
n(12%+) >= 3,000. Pass proposes: treat edges above 12% as a data flag (demote or withhold), in its own PR.

**R2: Agreement.** Group = `etype` is `both`. Control = `etype` is `gap` or `model`.
Pass if forward ROI(both) exceeds ROI(control) by at least 2.0 points with n(both) >= 1,500. Pass proposes: require agreement
for a play, in its own PR. Fail or inconclusive: no change.

**R3: Down-rank cells.** Group = `ebin` is `12%+` and (stat, side) is one of: PRA under, 3PM over, P+R either side, P+A either side.
Pass if forward ROI is at or below -5.0% **and** at least 3.0 points below ROI(all bets), with n >= 1,500. Pass proposes:
down-rank those cells at high edge, in its own PR.

Each rule passes or fails alone. There is no pooled verdict and no multiple-test rescue: three tests are run, so a single
borderline pass is reported as borderline.

## Expected sample

In-sample volume was about 23,000 bets a week, of which 12%+ is about 3,800, `both` about 1,700, R3 cells about 750. Three weeks
should clear the R1 and R2 minimums. R3 is borderline at 1,500 and may come back inconclusive.

## Read

```bash
python3 scripts/nba_edge_rules_read.py --from 2026-11-19 --to 2026-12-09
```

Report each rule's n, ROI, interval and win rate beside its baseline, with its verdict: pass, fail or inconclusive.
