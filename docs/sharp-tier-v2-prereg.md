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
plays data"; `scripts/sharps_v2/tier_history.py`). On 205 graded shown plays Contested went 53-32 +9.1% (se 9.8, NBA, NFL and CBB) against Thin
24-21 +6.5% (se 15.2): the tiers do not separate on those samples, and the Contested bucket holds most plays because Contested includes any
past-winner wallet on the other side (A1), which is common. Nothing in that history is used to set a threshold: the only number in the rule is
0.3 points (`EV_ON_PTS` in `scripts/sf_signals.py`, registered Nov 14).

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

Tier, first match wins: **Contested** if any of a1 to a4; **Clear** if (b1 or b2) and b3; **Thin** if proven wallets on S <= 1, no b1, and no price
read (`ev.pts` null); otherwise **Mixed**. College (CBB, CFB) has no tested CLV model, so a2, a3 and b1 are published false and listed in `facts_na`.

Universe: every rule pick (side set, ladder units above 0) on a frozen card, every sport, CFB included (shown size 0, still logged). The log is
`pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl` on `pm-holders-data`, append-only, one row per pick written when the card freezes (and repaired from the
card's own stored block if an append was missed). The tier graded is the one on the frozen card, never a live preview.

## Primary metric: the price at the cut against Pinnacle's no-vig close

For each logged play, **CLV = Pinnacle's no-vig fair for the side at the last tape row at or before game start, minus the price at the cut**, in
points. The price is the stored Polymarket displayed price (a mid or last trade, not an ask: no ask is stored, so this is before the spread, and a
CLV smaller than about half the spread is not copyable). Spread and total need the ticket line to be Pinnacle's main line at the close; otherwise
the play has no close and is counted by reason. No close is ever estimated.

Primary comparison, read per sport, never pooled: **mean CLV of plays that are not Contested minus mean CLV of Contested plays**. The tier rule
claims Contested plays are the ones with stored evidence against them, so it predicts the difference is positive. Interval: 95% percentile
bootstrap, 10,000 resamples, seed 20261111, resampling plays. Also reported, same intervals: mean CLV per tier.

## Secondary: flat ROI

Flat 1 unit at the stored price at the cut, a win pays 1 / price - 1, a loss -1, a push 0, result = the market's own Polymarket resolution, per
sport and tier. Voided plays left out. Read beside CLV, never instead of it.

## Minimum sample and the verdict rule

- **n >= 300 plays per sport** (the existing per-sport minimum of `docs/sharp-card-prereg.md`) **and at least 100 in each side of the primary
  comparison**, counting only plays with a readable close, before any verdict. Before that every read is "no verdict", report-only, monthly.
- A sport passes only if the lower 95% bound of the primary difference is above 0. CBB and CFB only read on CLV where the tape gives a close
  (the CBB tape starts 2026-11-19, so earlier plays have none); a sport where fewer than half of plays have a readable close reads on ROI only and says so.
- A pass lets the user *consider* showing the tier as tested. The page keeps the "untested" wording until then.

## Power, said in advance (from `docs/sharps-audit-2026-11-18.md`, section 5)

ROI on a coin-flip bet has a standard deviation near 1.0 per bet, so with 300 plays one standard error is 5.8 points: ROI can only see an edge near
+11%, and a real +3% edge needs about 4,300 bets. Per tier the sample is smaller still (so far NBA has 50 Contested plays and none in the other three tiers). CLV has a standard error near 0.3 points on a few hundred plays, so **CLV against the close is the metric that can be read this
season, and ROI is context.** At the pace so far (NBA 58 graded shown plays from Nov 12 to Nov 22, about 5 a day) NBA reaches 300 plays around late January; NFL (33 plays in
weekly slates) and CBB (53) later, and CFB shows no size.
Unless something changes, most reads will say "no verdict", and that is the honest answer.

## Kill rules, written in advance

- Stop showing the tier labels (keep logging until the final read) if, at n >= 300 in a sport, the 95% interval of the primary difference lies
  entirely at or below 0, or if the tier ordering (mean CLV or ROI) is reversed in two consecutive monthly reads with n >= 100 in each side.
- **Data quality, no verdict for the sport:** more than 5% of forward log rows whose tier differs from a re-derivation from the stored card (a tape
  row committed after the freeze), or more than 10% of logged plays with a price older than 30 minutes before the cut.
- A tier or fact definition cannot change after registration. Fixing a bug is a new registration, and the old rows stay read as written.
- A better-looking slice found along the way is flagged for close monitoring with its sample size and is never promoted on the same data.

## Not part of this test

Whether to keep or remove the flat 1u on Contested plays (D-P3 of the plays spec), Polymarket ask pricing (needs a stored ask first, D-P1), the
public split (context only, not a tier input, no record), and the account tiers of the wallets file. The tier changes none of the shown sizes.
