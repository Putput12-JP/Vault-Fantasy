# Proven-sharps side cards

`scripts/build_side_cards.py` runs from `.github/workflows/pm-cards.yml`. The holders scan starts it right after it pushes a new
T-15 keyframe, so a frozen card is built within minutes of the cut even when GitHub's cron runs late; a 10-minute cron is the
backstop. For every game it builds the card from
your SharpFlow screenshot: who holds each side, how much is proven sharp money, unproven money and losing-wallet money, and the
combined record of the proven wallets on the side. All of it is computed as of the cut (game start minus 15 minutes).

It is step 3. Step 1 (`docs/pm-ledger.md`) grades every tracked wallet's bets. Step 2 (`docs/pm-holders.md`) records who holds
what and freezes it at T-15. The UI comes in later PRs.

**Sharp money is context only** (CLAUDE.md). The card never feeds Top Reads, SM_GATE or an agree total. Its `lock_shadow` is the
pre-registered forward test in `docs/sharp-card-prereg.md`, recorded so it can be graded honestly.

## Where cards live

| Card | Where | Rewritten? |
|---|---|---|
| Frozen (one per game, from its T-15 keyframe) | `pm_cards/<sport>/frozen/<date>/<slug>@<start>.json` on `pm-holders-data` | never |
| Live (every upcoming game) | `live.json` on `pm-cards-live`, a single force-pushed commit | every run |

## How a wallet is classed (SharpFlow's published rules)

| Class | Rule |
|---|---|
| proven (`sharp`) | sport book n >= 6, win rate >= 55%, dollar ROI > 3% |
| sized up (`hc`, the star) | proven, and its position / usual stake >= 1.5 |
| loser | not proven, and book PnL < 0 (else last-30-days ROI < 0, else more losses than wins) |
| unproven | any other wallet, including the many our ledger does not track |
| excluded | holds both sides of 25%+ of its ledger markets (with at least 8), or all-time volume / PnL > 100. These are Vault approximations of SharpFlow's discovery filters, built from different data; see the script header. |
| untracked | first selected into the ledger universe after the cut. It counts as unproven, so a wallet picked because it won this game can never count. |

- **One bet is one position:** wallet x game x market type x side. Rungs of one spread or total side are summed into a position
  in the ledger books.
- **On the card, a wallet's money on a side is its largest single rung,** and it counts from $250, the same as SharpFlow's board.
- **A wallet on both sides of one market group** keeps only legs at 1.0x or more of its usual stake, taking the highest-ratio
  one. With no such leg it is dropped as balanced dust (`coverage.two_way_dust_dropped`).
- **Books use ledger rows settled before the cut only.** Hedged legs are left out of records. SPLIT-funded rows count in win-loss
  but never in dollars.
- **Variant `sfx` (a shadow, since 2026-11-12):** the `all` books, but with SharpFlow's own published exclusion list
  (`sharp_intel_excluded_wallets.json`: its market makers and traders, fetched every build) in place of Vault's hedger and churn
  rules. SharpFlow applies its 25% both-sides and churn rules only when it discovers new wallets; Vault applied them to every
  wallet, which is stricter. `sfx` keeps money, score, `sf` and `lock_shadow` per market, not the wallet lists. It is not part of the
  pre-registered test. If the list cannot be fetched, the variant is left out of that build rather than built on an empty list.
- **Every number is computed twice.** `all` uses every row, which is SharpFlow's way and includes wallets chosen with hindsight.
  `fwd` uses only rows from after a wallet was selected. The pre-registration names `all` as primary and reads `fwd` alongside it.

## Card fields (per market group: ml, spread, total; per side; per variant)

| Field | Meaning |
|---|---|
| `sharp_usd`, `hc_usd`, `unproven_usd`, `loser_usd`, `excluded_usd` | money on the side by class, as shares times price at the cut (mark value) |
| `pct_of_sharp`, `pct_of_losers` | the side's share of all proven money, and of all loser money, in that market group |
| `proven.w`, `proven.l`, `proven.win_pct` | the combined record of the proven wallets on the side |
| `proven.l30_roi` | stake-weighted last-30-days ROI; null if any proven wallet has fewer than 2 bets in the window |
| `proven.lifetime_pnl` | the sum of the proven wallets' book PnL |
| `proven.last20` | the newest 20 results across those wallets, one per wallet per game |
| `list`, `losers` | up to 4 proven and 3 loser wallets: record, ROI, L30, PnL, press, star |
| `counts` | wallets per class |
| HC +N badge (page only, not stored) | `counts.hc` on this side minus `counts.hc` on the other side of the same market group and variant: the benchmark's HC margin (CONFIRMED wallets sized 1.5x or more, for minus against). Shown on a side's tile when it is +1 or more; +2 and up gets the stronger style. Context only: it sets no units and feeds nothing. Vault counts money at mark value and collapses hedged wallets first, where the benchmark uses cost and counts both legs, so the two can differ by a wallet. |
| `ags` | SharpFlow's AGS-Unified v12 side score (`score`, -1 to +1) and its label (`tier`: FADE at 0 or below, then WEAK, LEAN, LOCK, PREMIUM, ELITE at SharpFlow's published cut points 0.781 / 0.916 / 0.957 / 0.981), with the mean wallet quality for and against, the tracked wallets counted on each side, and how many of them scored. Null when no tracked wallet with a book is on the market. A shadow field: it does not set the units. The cut points were fitted on SharpFlow's picks, not Vault's. |
| `sf` (on the market group, per variant) | The size SharpFlow's staking rules give the market, built by `scripts/sf_rungs.py` from Vault's own ledger and Pinnacle tape (so wallets and numbers differ from SharpFlow's). Fields: `side`, `units`, `rung` (PRESS, PRESS-X, PRESS-N, PRESS-U, STEAM-C, PRESS-R6, STEAM-S, SOLO-Q, FADE-F, TRUST-G, TRUST-S, TRUST-T, PRESS-M, TOP3-PICK, GAP-LEAD), `reason`, `price`, `line`, `missing`, and, since 2026-11-12, `pick_date`, `chain` (market rules that moved the size), `press_edge`, `blend_edge`, `pinnacle_odds`, `steam` (the measured Pinnacle move for the staked side: last-hour and since-open shorten in %, main-line walk in points, the open / hour / now tape rows used) and `sides` (every side's units, rung, reason and steam on / off / unknown). Ported, in SharpFlow's order: the ladder with steam (the price step, PRESS-X's steam split, STEAM-C, STEAM-S, SOLO-Q), FADE-F, the trust layer with TRUST-M, the score gate, PRESS-M, the odds cap, the -425 favourite mute, the press-edge / net clamp (dated out from 2026-11-05), TOP3-PICK, GAP-LEAD, edge under 5 (blended edge x steam, read only when a season tier-5 wallet is against), the T5-LEAD seats (no tier 5 2u, no lead 2u, young tier 5 2-3u, 6-day lead 2-5u, 14-day lead 3-6u; from 2026-11-10 a no-tier-5 spread or total needs juice steam) and the press-edge under-5 cap (1u, a moneyline 2u in its two cases, a spread or total under 0 goes to 0u). Steam for the ladder is the tier at the cut or the lock-row juice; `sf.t5_seat` and `sf.top3_price_src` record the seat and which price TOP3-PICK read. Steam is read only from tape rows at or before the cut; it is unknown (never guessed) when the game has no tape, a side cannot be mapped to home / away, or a spread / total ticket line is not Pinnacle's main at the cut. Still missing, listed in `missing`: ML-DOOR (needs the steam state when SharpFlow first captured the ticket), T5-LEAD's +1u winner-align boost, the press-edge-net closers clause, SharpFlow's steam-drop feed, its cross-sport FADE-F loss streak and its create gate. One side at most. The card shows this size. `lock_shadow` stays the pre-registered forward test and is unchanged. |
| `lock_shadow` | the pre-registered gates (money share over ALL money, any-class presser with n >= 15, no proven against, at least one proven for), the locked side, the graded rung and its price at the cut, and the clean-step ladder units (>= 3x 5u, >= 2x 2u, else 3u, capped at 1u under 0.50) |

| `list[].usual`, `list[].at_size` | the wallet's usual stake (mean position), and its record on positions in the same size band vs usual as this one (bands at 0.75x, 1.5x, 3x) with the share of its bets in that band |
| `list[].clv` | price skill: `n` past positions with a stored close, `beat` of them bought below it, `mean` close minus entry price. Closes are stored values only: Vault's own T-15 keyframe price (read within 30 min of the cut) or the Pendulum Flow close in `data/pm_closes.json`. No close is ever estimated, so `n` starts small (keyframes from 2026-11-11, Pendulum NBA/NFL from late October). |
| `unproven_list` | up to 4 tracked wallets on the side that are not proven yet (SharpFlow's "secondary"), with their records |
| `sf.flagged`, `lock_shadow.flagged` | the price and time this side was first flagged, carried from the previous live build while the side stays the same |

## Play detail (`sharp-money/side-cards.js`)

"See who's on it" on a card opens the play detail for that market: price and the move since it was flagged, money and the
proven / unproven / losing split, a chart of every listed wallet by price skill and lifetime ROI (bubble area = $), the lead wallet
(record, price skill, size vs usual, record at this size), every wallet on both sides, and how the size is set. A wallet with fewer
than 5 past positions with a stored close is listed but not plotted. There is no "signals aligned" count: sharp money is context,
never an agree total.

### One-wallet cap shadow (`solo`, `scripts/sf_solo.py`)

The benchmark's T5-LEAD seats floor a stake at 3u when a wallet that has held season tier 5 for 14+ days is on the side and no tier-5
wallet is against, whatever that wallet bet on this game and however many wallets are on it. `solo` is the shown size (`sf`) capped at
1u when exactly one proven wallet is on the shown side, or when the largest proven wallet bet under 1.0x its usual stake. A cap never
raises a size. It is derived from the stored `sf`, each side's `counts` and its largest proven wallet's `press`, so the grader covers
every frozen card (`play: "solo"` rows with `capped`, `was_units` and `cap_reason`; `cards_record.json` `sports.<s>.solo`). Shadow
only: the shown size, the pre-registered lock and the forward test are unchanged. Shadow plays are graded but never listed as open plays.

The card's "Combined proven sharps" strip shows proven wallets out of every wallet holding $250 or more on the side
(`counts.hc + sharp` of `hc + sharp + unproven + loser + excluded`).

### Pinnacle limit and price check (`signals` on the shown size, `scripts/sf_signals.py`)

Two reads of the benchmark's "signals aligned" row that Vault can make from its own Pinnacle tape (`data/book_tape`), at the cut:
- **Limit:** Pinnacle's max stake on the market group at the first tape row and at the lock. `rising` is up $500 or more, or 1.45x or
  more (the benchmark's `buildLockedMarketSignals`); `tested` is $3,000 or more. The first tape row is when Vault first recorded the
  game, not Pinnacle's open. NFL rows carry no limit; CBB has no tape.
- **Price vs fair:** the Polymarket price for the shown side minus Pinnacle's no-vig fair price for it, in points (positive = under
  fair); `on` at +0.3 or more. Spreads and totals read only when the side's line is Pinnacle's main line at the cut. The benchmark
  uses its wallets' average entry price against a blend of sharp books; Vault has neither, so this is Pinnacle alone.

The builder stores `signals` on each shown size; the grader re-derives it from the card and the tape, so every frozen card is covered,
and `cards_record.json` `sports.<s>.signals.{sf,pub}` splits the record by each signal (yes / no / unknown). The Record page shows a
row only when plays fall on both sides of it. Findings on the first 23 graded plays: the limit was up on every play that had one
(Pinnacle raises limits toward every game), and the price sat under Pinnacle's fair price on 1 of 12 plays that could be read, so
neither separates plays yet. Context only: no size, lock, forward test, Top Reads, SM_GATE or agree total reads them.

### Publish-mute shadow (`pub`, `scripts/sf_publish.py`)

Each card's market groups carry `pub` (variants `all` and `fwd`): the shown size (`sf`) with the benchmark's publish mute. A side
whose AGS-Unified v12 score is 0 or below, or has none, is muted unless its rung is PRESS-M (the benchmark's
evaluateBaseHealthV12; a MUTED side counts as cancelled in its record). A market where the port staked both sides is skipped.
The benchmark's CONFIRMED-Q1 and CONFIRMED-UNOPP rescues are not ported. The grader derives `pub` from the stored `sf` and `ags`
fields, so every frozen card since the shown size shipped is graded (`play: "pub"` rows, `cards_record.json` `sports.<s>.pub`), and
`h2h_record.json` reports `vault_pub` and the overlap of each Vault set with the benchmark's plays at the cut. Context only.

### Wallet deep dive (`dive` on each listed wallet, `pop` on each card)

Every listed wallet carries `dive`, built from its positions settled before the cut (point in time, same rows as its record). Each
cell is `[wins, losses, dollar ROI, positions with a stored close, how many were bought below it, luck]` (`cols` names them):
- `all`, then `lane` (`ml`, `spread`, `total`), `fav` / `dog` (entry price at or above 50 cents is a favourite), and `size`
  (`small` under 0.75x its usual stake, `usual` 0.75x to 1.5x, `big` 1.5x or more);
- luck is P(wins >= the wallet's wins) if every position won exactly as often as its entry price says (Poisson-binomial, exact),
  so a 60-cent favourite counts as a 60% coin, not a coin flip; `exp_w` is the expected wins on `all`;
- `pop` is how many wallets were in the sport's universe at the cut. The sheet shows `pop x luck`: about how many tracked wallets
  would post a record that rare by luck alone, which is the selection effect a "1 in N" figure on a hand-picked wallet leaves out.

The sheet marks the row that matches the bet (its market group, favourite or underdog from the suggested side's price, and its
size band) and says when a winning wallet is losing in this bet's lane (5 or more decided bets there). Context only: the dive never
feeds the size, the lock, the forward test or any record.

Each card also carries:
- `coverage`: markets read, markets missed, late reads, and the oldest read's lag;
- `vault`: the Vault game key, plus a flag when Polymarket's and Vault's start times are more than 10 minutes apart;
- `ledger_run_at`: when the ledger was last refreshed;
- frozen cards also carry `test`: whether the card counts for the forward test, and why not (built late, a stale ledger, or a
  duplicate of an earlier card for a postponed game).
