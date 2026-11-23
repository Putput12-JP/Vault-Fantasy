# Play evidence tiers (Clear, Mixed, Thin, Contested): pre-registered forward shadow

**Status: PROPOSED (written 2026-11-23, Central).** Nothing below is registered until the user approves it. The commit that changes this line to
Registered is the registration: its hash and time are the proof that the rule came first, and the first card that can count is the first one cut
after that commit. Nothing below may change after the first counted card is graded; a change is a new registration with its own date.

Sharp money is context only (CLAUDE.md). The tier is a label made of a card's own stored facts. It is **never** a bet signal, never changes the
shown size (flat 1u on NBA, NFL and CBB, nothing on CFB, always "untested rule"), and never feeds Top Reads, SM_GATE or an agree total. Passing
this test only lets the user *consider* a change to the card, as a separate decision. It does not make one. Data contract and rule source:
`docs/sharps-v2-plays-spec.md`; code: `scripts/sharps_v2/plays_v2.py`, rule `v2t-1`.

## What was learned before this registration (not counted as evidence)

The rule was written after looking at the graded history, so every per-tier record on it is in-sample (`docs/side-card-record.md`, "Sharps V2
plays data"; `scripts/sharps_v2/tier_history.py`, data read at `pm-holders-data` commit `dec770c0e7bb`, Nov 23). There are **205 graded rule picks**:
**144** in NBA, NFL and CBB (the sports that show a size) and 61 in CFB (no size shown). On the 144, Contested went 53-32, +9.1% (se 9.8, n=85) and
the plays whose tier is not derivable (no price check possible at the cut on an old card) went 31-23, +13.1% (se 13.7, n=54); the other three
tiers hold 5 plays. The tiers do not separate on those samples, and Contested holds most plays because it includes any past-winner wallet on the
other side (A1). Nothing in that history is used to set a threshold: the only number in the rule is 0.3 points (`EV_ON_PTS` in
`scripts/sf_signals.py`, registered Nov 14).

## The rule, frozen in code at the registering commit

Facts for the shown side S, with O the other side(s) of the same market group, all read from fields stored on the card at the cut (game start minus
15 minutes):

| Fact | Test | Sports |
|---|---|---|
| a1 | a past-winner wallet (class hc or sharp) on O | all |
| a2 | a wallet whose CLV tier at the cut is `sharp` on O | NBA, NFL |
| a3 | the registered fade-dull rule (`tp.tB`) fires on O | NBA, NFL |
| a4 | price worse than Pinnacle's no-vig fair by 0.3 points or more | all |
| b1 | a CLV-`sharp` wallet on S | NBA, NFL |
| b2 | price better than Pinnacle's no-vig fair by 0.3 points or more | all |
| b3 | the forward-only variant picks S too | all |
| b4 | two or more past-winner wallets on S | all |

Tier, first match wins: **Contested** if any of a1 to a4; **Clear** if (b1 or b2) and b3; **Thin** if past-winner wallets on S <= 1, no b1, and no price
read (`ev.pts` null); otherwise **Mixed**. College (CBB, CFB) has no tested CLV model, so a2, a3 and b1 are published false and listed in `facts_na`.

"Forward" in this registration means a tier **logged at lock by the live builder** (the `v2_tier` log), joined to the graded record. A tier derived
after the fact from an older card is in-sample, however recent the card.

Universe: every rule pick (side set, ladder units above 0) on a frozen card, every sport, CFB included (shown size 0, still logged). The log is
`pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl` on `pm-holders-data`, append-only, one row per pick written when the card freezes (and repaired from the
card's own stored block if an append was missed). The tier graded is the one on the frozen card, never a live preview.

## Which price the tier reads, and plays that use Pinnacle's price

`price` is the stored Polymarket displayed price of the side at the cut (a mid or last trade, not an ask: no ask is stored, so everything below is before
the spread). When Polymarket had no price the builder falls back to Pinnacle's vig-included implied price (`price_src == "pin"`, moneylines only, never
yet on a shown play). Any play with `price_src == "pin"` is **reported separately** and is left out of every metric below, because its "price" is the
reference the close is compared with.

## Primary metric: the market move after the cut, on the wallet-fact tiers

**Why this and not close-minus-price.** Two tier facts (a4 Contested, b2 Clear) test the price at the cut against Pinnacle's no-vig fair at the cut.
"Close fair minus price at the cut" is that same quantity plus the move, so reading it by tier would partly just read the tier's own input back. The
primary test therefore (1) uses **market move**, Pinnacle's no-vig fair for the side at the last tape row at or before game start **minus Pinnacle's
no-vig fair for the side at the cut** (the `fair` stored on the log row), in points, which does not use the price at all; and (2) compares the
**wallet-fact tiers only**, so no price fact sorts the plays being compared:

| Group | Plays |
|---|---|
| Against by wallets | any of a1, a2, a3 true |
| No wallet against | none of a1, a2, a3 true and a4 false |
| Read separately, not in the primary | none of a1 to a3 but a4 true (Contested on price alone); Clear and b2 plays; every play with a price fact unknown |

Primary comparison, per sport, never pooled: **mean market move of No wallet against minus mean market move of Against by wallets**. The wallet
facts say money is on the other side; the tier predicts the market then moves less toward (or more away from) S, so the difference is positive. Interval:
95% percentile bootstrap, 10,000 resamples, seed 20261111, resampling plays. A move needs both Pinnacle rows (at the cut and at the close) and, on a spread
or total, the ticket line to be Pinnacle's main line at both; a play without one is counted by reason, never estimated. The close is the grader's `pinclose`
row (spec section 5.3); the grader work is not built yet and is part of the registering commit.

**Secondary (reported, never a pass condition):** mean Pinnacle CLV = close fair minus the price at the cut, per tier, same intervals. It overlaps the
a4 and b2 inputs by construction and is labelled that way. **Flat ROI** per sport and tier: flat 1 unit at the stored price at the cut, a win pays
1 / price - 1, a loss -1, a push 0, result = the market's own Polymarket resolution, voided plays left out.

## When it is read, and what passes

One **final read date per sport** (the same dates as the existing registrations, `docs/sharp-card-prereg.md` and `docs/sharp-card-prereg-cbb.md`):

| Sport | Final read | Minimum n (plays with a readable move, per side of the primary comparison) |
|---|---|---|
| NBA | the first Monday after the last scheduled game of the 2026-27 regular season | 100 per side |
| NFL | the Tuesday after Week 18 of the 2026 season | 100 per side |
| CFB | the Monday after the 2026 conference championship weekend | 100 per side |
| CBB | the Monday after the 2027 men's national championship game | 100 per side |

- **Interim reads** are monthly and report-only. Only the final read on the date above gives a verdict, a verdict is never revisited on this
  registration, and an interim look can neither pass nor fail a sport. Repeated looks do not add up to a pass.
- **Pass** (per sport): the lower 95% bound of the primary difference is above 0, with n at the minimum on both sides.
- **Fail:** n reaches the minimum on both sides and the lower bound is not above 0.
- **Underpowered:** n is below the minimum on the final read date. It is neither a pass nor a fail, and the read says which side was short and by
  how much. Most or all sports are expected to end Underpowered this season; that is said here in advance.
- A pass lets the user *consider* showing the tier as tested. The page keeps the "untested" wording until then.
- **What every read reports:** n per tier and per side, win-loss and flat ROI with intervals, the market-move and CLV means with intervals, the counts
  without a readable close or move by reason, the plays with `price_src == "pin"`, the not-derivable plays, and the CFB read (no size shown) apart.

## Power, said in advance (from `docs/sharps-audit-2026-11-18.md`, section 5, and the Nov 23 counts)

ROI on a coin-flip bet has a standard deviation near 1.0 per bet, so with 300 plays one standard error is 5.8 points: ROI can only see an edge near
+11%, and a real +3% edge needs about 4,300 bets. A market move or CLV read has a standard error near 0.3 points on a few hundred plays, but only on
plays that **have** a readable close.

**The comparison groups are nearly empty today** (graded plays with a readable Pinnacle close, `dec770c0e7bb`, Nov 23). On the wallet-fact grouping
used for the primary, No wallet against vs Against by wallets: **NBA 0 vs 34, NFL 0 vs 16, CBB 1 vs 0, CFB 9 vs 4** (the rest of NBA and NFL is not
derivable at the cut or Contested on price alone). Under the earlier idea of reading Contested against everything else the counts were NBA 0 vs 42, NFL
0 vs 18, CBB 1 vs 3, CFB 9 vs 14. NBA and NFL shown plays are almost all Contested because a past-winner wallet or a close-beating wallet is nearly
always on the other side, so **the "100 per side" condition is unlikely to be met this season** in NBA, NFL or CBB, and CLV or market move should not be
called readable this season unless the forward log shows a non-Contested group actually filling. The honest expectation is Underpowered.

Pace, for the record: NBA has 58 graded shown plays from Nov 12 to Nov 22 (about 5.3 a day), so NBA reaches 300 plays around January 7, but the
bottleneck is the No wallet against group, not the total. NFL has 33 plays over weekly slates, CBB 53, and CFB shows no size.

## Kill rules, written in advance

- Applied **at the final read only** (no early stop on a repeated look): if the lower bound of the primary difference is at or below 0 with n at the
  minimum on both sides, the tier labels come off the page (logging continues to the end of the season).
- **Data quality, no verdict for the sport:** more than 5% of forward log rows whose tier differs from a re-derivation from the stored card (a tape row
  committed after the freeze), or more than 10% of logged plays with a price older than 30 minutes before the cut.
- A tier or fact definition cannot change after registration. Fixing a bug is a new registration, and the old rows stay read as written.
- A better-looking slice found along the way is flagged for close monitoring with its sample size and is never promoted on the same data. The user can
  remove the labels at any time as a product decision; that is not a verdict of this test.

## Not part of this test

Whether to keep or remove the flat 1u on Contested plays (D-P3 of the plays spec), Polymarket ask pricing (needs a stored ask first, D-P1), the
public split (context only, not a tier input, no record), and the account tiers of the wallets file. The tier changes none of the shown sizes.

## Shadow size v2s-1

Added 2026-11-23 by the user's decision, still **PROPOSED** with the rest of this file. The flat 1u was an MVP, so a second sizing rule runs **beside** it:
**v2s-1** sizes a play by its evidence tier: **Clear 1.5u, Mixed 1u, Thin 0.5u, Contested 0.5u, CFB 0**, and a play with no derivable tier gets no shadow
size (null, never 0). The values are an **ordering by evidence, not fitted to results**, and they are frozen in code (`SHADOW` in
`scripts/sharps_v2/plays_v2.py`) at the registering commit. A different value is a new rule id (v2s-2) and a new registration.

- **It changes nothing shown.** The page keeps the flat 1u on NBA, NFL and CBB and the "untested rule" label; `shown_units`, the ladder, `sf_rungs`, the
  gates and the locks do not read it; it never feeds Top Reads, SM_GATE or an agree total. Passing this test only lets the user *consider* showing a
  tier-scaled size, as a separate decision.
- **Logged forward.** Each new `v2_tier` log row carries `shadow_units` and `shadow_rule` next to `shown_units`. The log is append-only, so older rows
  without them stay as written and readers treat a missing key as "not logged", never as 0.
- **Secondary metric only:** the shadow's units and ROI against the flat 1u on the same plays (shadow units = each play's flat result at its own stored
  price times its size; staked = sum of sizes; ROI = units / staked; a push is staked and returns 0), per sport and pooled over NBA, NFL and CBB, flat
  compared on the plays the shadow sizes (not-derivable plays are not sized). Interval: 95% percentile bootstrap, 10,000 resamples, seed 20261111,
  resampling plays. Reported with the CFB read (no size) apart.
- **Read only at the final read date** of each sport (the table above). No verdict before then: monthly interim reads are report-only and cannot pass or
  fail the shadow, and repeated looks do not add up to one.
- **Kill rule, written in advance:** at the final read, with **n >= 300** sized plays in the pooled read, drop the shadow if the interval of its ROI lies
  **below the flat ROI's interval** (the upper bound of the shadow's ROI is below the lower bound of the flat ROI on the same plays). Below n=300 the read is
  Underpowered: neither kept as better nor dropped, and the read says by how much it was short. A standard error of an ROI is about 5.8 points at n=300, so
  an Underpowered ending is the expected one this season, and it is said here in advance.
- **In-sample record (not evidence):** on the Nov 23 history the headline derivable plays were flat +4.91u on 90u (+5.5%) against shadow +3.15u on 46.5u
  (+6.8%), and 85 of those 90 plays are Contested (`docs/side-card-record.md`, "Tier-scaled size shadow v2s-1 (2026-11-23)"). A better-looking slice found
  along the way is flagged for close monitoring with its n and is never promoted on the same data.
