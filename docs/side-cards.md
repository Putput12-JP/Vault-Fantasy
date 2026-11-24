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

### Filters on the plays list (`sharp-money/side-cards.js`)

A Filter button above the plays list (Plays view only, not All games). Chips in one group are "any of"; each Sharps chip and each
group narrows further. All are read from the stored card for the suggested side:
- **Tier:** the AGS label of the side (`ags.tier`, only when `ags.score` > 0), or "No tier" when the side did not score above 0.
- **Win 60%+:** `proven.win_pct` >= 60 over at least 20 recorded bets (`proven.w + proven.l`; AGS gives a record full credit at 20).
- **2+ proven:** `counts.hc + counts.sharp` >= 2 on the side. **Sized up:** `counts.hc` >= 1 (a proven wallet at 1.5x or more of
  its usual stake). **No hot wallet against** (formerly "Unopposed"): no proven wallet holds $250 or more on the other side. Tracked Polymarket wallets only; it says nothing about sportsbook money. **Steam:** the stored steam read is on (Pinnacle toward the
  side; unknown counts as off). **2u+:** the shown size is 2 units or more.
- **Market:** moneyline, spread or total.
The choice is kept in `localStorage` (`vsc-filters`) on the device. A "What these mean" panel under the chips defines each label.
Filters only hide plays on the page: the stored cards, the record and every size are unchanged.

### Refresh button (`sharp-money/side-cards.js`)

The "Updated" line above the cards has a Refresh button. It uses the same Cloudflare Worker as the page's own Refresh button
(`workers/sharp-refresh`: Turnstile check, one shared 60 s cooldown): a click dispatches `update-sharp-money.yml` with `force`, which
skips that workflow's quiet-hours gate and starts `pm-cards.yml`. The button then polls `live.json` (a fresh cache key each time) and
stops when its `built` time moves past the one it started with, showing the build timer; a 429 from the cooldown means a build was
just started, so it waits for that one. It gives up after about 10 minutes ("Try again"). Without a click, the board still reloads
every 2 minutes. `?rfurl=` (localhost only) points the button at a stand-in Worker for testing.

The Record view has the same button in its header. A forced `update-sharp-money.yml` run also starts `pm-record.yml` (the "Regrade
proven-sharps record" step: only when `force` is true, and not if a record run started in the last 10 minutes), so the Worker needs no
change. That button waits for `cards_record.json`'s `generated` time to move, then redraws the Record view. `pm-record.yml` otherwise
runs every 2 hours and takes about 30 s.

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

## Wallets file (`wallets.json` on `pm-cards-live`)

Built on the same run as the live cards (`--wallets-out`) and published beside `live.json`. It exists so a page can follow
specific wallets. A card cannot do that: it keeps a wallet's largest rung per side and lists only the 4 largest proven wallets.

`sports.<sport>.<wallet>` holds every proven wallet Vault does not exclude (variant `all`), whether or not it has anything open:

- **Book:** `name`, `w_`, `l_`, `n`, `roi`, `l30_roi`, `pnl`, `usual`, `clv`, `dive`. The same values as a card's wallet line.
- **`legs`:** its last 20 settled games, `[settled_at, result]`, newest first. A page can count results since a follow date.
- **`positions`:** every open position at or above the $250 floor on a game not yet at its cut, every rung:
  - `ev`, `gst`, `g` (ml, spread, total), `side`, `line`, `cid`;
  - `usd` and `shares`: shares times the market price at the scan, not what the wallet paid;
  - `px`, `px_t`: the market's price at the scan. **No entry price is stored or estimated;**
  - `press`: `usd` over the wallet's usual stake;
  - `since`: the first scan that saw the wallet holding it;
  - `cens`: the wallet already held it at the scan's first read of the market, so it got in before `since`;
  - `px_first`, `px_first_t`: the market's logged price for that outcome at the `since` read (the last price logged at or before
    it). It is the price when Vault first saw the position, **not what the wallet paid**. Null when no price was logged by then;
  - `hist`: `[[read time, shares], ...]`, every change in the wallet's share count, oldest first, repeats dropped, capped at 24
    (the first change and the latest 23). The scan replays 8 days of logs, so older changes are not there;
  - `two_way`: the wallet holds more than one side of the market group. A card may collapse or drop such a wallet.

It is a snapshot, rebuilt every run on a force-pushed branch, so it has no history to correct. Context only: never a pick, a size or
an agree total.

### Change on 2026-11-18: price-sharp wallets and the "hot" label in the wallets file

Each wallet entry now carries `rk` (`tier`, `n`, `mean`, `p`): its CLV tier as of the build (`scripts/pm_clv_tiers.py`, `docs/pm-clv-tiers.md`),
NBA and NFL only (`null` elsewhere). In NBA and NFL a **price-sharp wallet is listed even when it is not "hot"**, with its book and open
positions, so the Following page can show price skill. The "hot" rule (6+ bets, 55%, 3% ROI) is unchanged and is a record, not proof of skill.
The Following page tags price-sharp and price-dull wallets, sorts by price skill by default, shows no size on college plays, and no longer
calls wallets "proven" (`following.js?v=6`). Context only: no size, pick or agree total comes from it.

### Change on 2026-11-21: the account sheet fields in the wallets file

A bet in the Following feed now opens a sheet (centered on desktop, a bottom sheet on a phone) with the bet, three headline reads
(size against usual, last-30-day profit, the other side) and three tabs: This bet, Their record, Who else. Wallets with at least one open
position carry four more fields (the directory-only wallets do not, to keep the file small: 696 KB to 891 KB on the Nov 21 build, 48 wallets):

- **`l30`:** last 30 days, `{w, l, pnl, roi}`: wins, losses, dollar profit, dollar ROI. Same positions and cash rule as `l30_roi`.
- **`d30`:** the dive's cuts (market, favorite or underdog, size, odds band) over those 30 days only. Same cell shape as `dive`.
- **`odds`:** all-time cuts by entry-price band (`dd` +200 or longer, `d2` +150 to +199, `d1` +100 to +149, `f1` -100 to -149,
  `f2` -150 to -199, `ff` -200 or shorter). The bands are `ODDS_BANDS` in `build_side_cards.py` and the same cut points are in `following.js`.
- **`curve`:** every settled cash position of the last 30 days, `[settled_at, dollar profit, stake, market group, entry price]`. The
  sheet draws a running total (Actual, or Flat: every bet one unit, profit over stake) and gold-dots the bets matching the selected cut.

Entry price in `curve` and `odds` is the stake-weighted price of a settled ledger position, a stored field. The open position's own
entry price is still not stored; the sheet says so. `dive` on cards and `live.json` is unchanged (no `odds` there). Context only: no size,
pick or agree total comes from any of it. Page: `following.js?v=10` (both Sharp Money layouts load the same file).

### Change on 2026-11-21: the account sheet opens from the Sharps cards

A hot wallet's row in a card's Wallets list, and the "Open account sheet" button inside a wallet's deep dive in the play detail, open the same
account sheet as the Following feed. `side-cards.js` names the wallet, game, market and side; `following.js` (`VaultFollowing.openSheet`) finds
the wallet's largest rung of that bet in `wallets.json` and opens the sheet over the page. A wallet or bet that is not in the file (an old card,
an unproven or excluded wallet) does not open anything: the row says "No account sheet for this wallet". Losing, other and excluded wallets
have no link. No new data and no change to any card, size or record. Pages: `side-cards.js?v=60`, `following.js?v=11`.


### Change on 2026-11-21: Sharps V2 account fields in the wallets file (`v` 2)

Spec: `docs/sharps-v2-accounts-spec.md`. **Additive only.** Every V1 key keeps its name, shape and value (`following.js?v=13` renders the V2
file unchanged), `legs` keeps its 20 cap, `sc` keeps its any-sport meaning, `rk.mean` stays the raw mean, `usual` stays the mean. New keys sit
beside them. `v` is now 2 (cards keep their own `v`). Every new number is a stored field, a count of stored rows or arithmetic on them; a
value that cannot be computed is `null`, never 0. Context only: none of it is a bet signal, a size, a pick or an input to Top Reads,
SM_GATE or an agree total.

**One existing number moves (audit bug 14).** A wallet with open positions used to have its book read at its first game's cut (a time in
the future). Every wallet is now read at the build time. Only the 30-day window can differ (`l30`, `l30_roi`, `d30`, `curve`); `n`, `w_`,
`l_`, `roi`, `pnl` cannot. On the Nov 21 10:21 AM CT inputs that changed `l30` for 7 of 58 open wallets (all NFL).

Top level, added: `v2_fields` (the list of added keys), `since_from` (the start of every dated list in `since.json`: build time minus 60 days),
`since_file` (`since.json`) and `retained` (below). Per wallet, added:

- **`rk.post`, `rk.sd`:** the shrunk CLV estimate (posterior mean) and its sd, in price units (x100 = cents). Already computed by
  `pm_clv_tiers.fit()` and dropped before. `rk.mean` is still the raw mean; show `post` where the page says "shrunk".
- **`v2.tier`:** `beats` (rk sharp), `even` (mid), `loses` (dull), `few` (thin, or no `rk`: no CLV game, CFB, CBB). No new threshold: the
  module's own constants (30 games, P 0.95 / 0.05). The scorecard is not folded into the tier.
- **`flat_roi`:** mean of profit over stake across cash positions, every bet one unit (the all-rows book's `flat_roi`).
- **`fwd`:** the forward-only book `{w, l, p, n, pnl, roi, flat_roi, clv_n, clv_mean}`, same formulas as the all-rows book, on ledger
  rows with `src == forward` (not hedged). **Definition:** a row counts when it settled at or after the wallet's `first_seen`; the bet itself
  may have been placed before it (it was open when Vault began tracking the wallet). That is not look-ahead on a result, but it is not "placed
  after first_seen" either. On the Nov 21 inputs, listed wallets' forward non-hedged rows with a first fill before `first_seen`: NBA 140 of
  2,010 (33 wallets), NFL 81 of 517 (16), CFB 23 of 398 (7), CBB 38 of 594 (7). The 2026-11-16 12:00 AM CT line
  (`docs/sharp-shadow-rules-nov16.md`) is the card-play cutoff, **not** this one: no V2 account field uses it.
- **`first_seen`:** when the wallet entered the ledger universe (epoch; CBB follow-only wallets from `follow_only.json`). A wallet in both
  `follow_only.json` and `first_seen.json` publishes the EARLIER date, which is the one `build_pm_ledger` used to stamp `src`, so the date
  and the forward rows agree (before: the later `first_seen.json` date won and 3 wallets showed forward games settled before it; on the Nov 21
  inputs `0x280602b4` CBB moves from 2026-11-20 9:19 PM CT to 2026-11-17 5:06 PM CT and `0xd2753130` from 2026-11-19 8:31 AM CT to
  2026-11-18 12:06 PM CT). The date the stats and the cuts read is unchanged, so no V1 number moves.
- **`last_settled`, `n30_games`:** latest settlement over the wallet's positions; distinct games with a decided position settled in the
  30 days before the build (0 means "No bets in 30 days").
- **`usual_med`:** median cost of its cash positions (not split) at or above the sport floor ($250, CBB $100). `null` when none. `usual`
  stays the mean.
- **`sc_sport`, `sc_n`:** on the account scorecard's price-sharp list for **this** sport, and that file's game count for the wallet (`null`
  when absent). `sc` is unchanged.
- **`name_disp`, `name_src`:** the display name. `name` when it is real (not null, not a bare address); else the newest real name stored
  for the wallet in any universe snapshot or keyframe; else `Unnamed 0xabcd...1234`. `name_src` is `universe`, `keyframe` or `none`.
- **`exp_w`, `luck_p`:** the price-implied expected wins and P(wins at least as many), from `dive` (`dive.exp_w`, `dive.all[5]`).
- **`since.json` (a separate file, `since_file`):** the dated settled list per wallet, `sports.<sport>.<wallet>` and `retained.<sport>.<wallet>`,
  items `[settled_at, first_fill, r, flat, ev, stake]` for every non-hedged position at or above the sport floor settled in
  `[since_from, built)`, newest first. `r`: 1 win, 0 loss, 2 push. `first_fill` is the earliest ledger fill of the position, so a page can
  drop bets placed before a follow. `flat` is profit over stake (3 places), `null` for a SPLIT-funded position. `ev` is the game and `stake`
  is whole dollars. **The unit is a position:** a spread and a moneyline on one game are two items. Tally games with `ev` (one result per
  game, the biggest `stake`, the way `legs` does) and say "bets" for the position count. A wallet with no item is left out. It replaces `legs`
  for "Since you followed" only. A follow older than `since_from` cannot be tallied. It is a separate file because it alone was 364 KB of
  the 660 KB the V2 fields first took in the wallets file; the classic page re-reads the wallets file every 2 minutes and never reads
  `since.json`.

Per open position, added: `side_usd` (sum of `usd` over the wallet's listed rungs of that game, market and side), `side_rungs`,
`side_press` (`side_usd / usual_med`, `null` without a median; "mark value over median cost") and `px_age_min` (minutes between the price
time `px_t` and the build, `null` when `px_t` is `null`). The rungs of one side carry the same three side values.

**`retained.<sport>.<wallet>`:** a wallet that was on the list at some build in the last 60 days and no longer is:
`{retained, left_at, name, name_disp, first_seen, fwd, last_settled, n30_games, v2, rk}`, no `positions` and no list (its dated list is
under `retained` in `since.json`). A retained wallet is
never also under `sports`, and it is dropped 60 days after `left_at`. After the first V2 build `left_at` carries forward from the previous
published file (`--prev-wallets`). The first V2 build (no previous file with V2 keys) seeds it by replaying the listing rule at each daily
12:00 AM Central cut over the prior 60 days, point in time (`fl.stats(w, cut)`, `fl.clv_tiers(cut)`, wallets in the universe at the cut);
the scorecard list is NOT replayed (no earlier copy is stored and today's list would be look-ahead), so a wallet listed only through it is not
seeded; after the first build `retained` carries forward and nothing is missed. Excluded wallets (hedger, churn) are never seeded. The 60 cuts
are 12:00 AM Central of the last 60 Central calendar days, so there are always 60 of them across a daylight saving change. Follows live in the
viewer's browser, so every leaver is retained.

Not collected, so not shown (spec "Deferred"): an open position's entry price, a college price tier, a follow tally older than
`since_from`, per-user follow tombstones.

Run locally: `python3 scripts/build_side_cards.py --holders pm_holders --ledger pm_ledger --frozen-out out/cards --live-out out/live.json
--wallets-out out/wallets.json --scorecard-dir data --now EPOCH --wallets-only [--prev-wallets last_wallets.json]`. `--now` pins the build
time, `--wallets-only` skips the cards (about 80 seconds on the Nov 21 inputs including the 60 day seed). The workflow passes
`--prev-wallets` (the last published `wallets.json` from `pm-cards-live`), so `retained` carries forward there; a local run without it
re-seeds from the replay. Old and new numbers:
`python3 -I scripts/sharps_v2/compare_wallets.py --old OLD.json --new NEW.json [--base V1_SAME_INPUTS.json]` (reads `since.json` beside NEW).
Tests: `python3 -m unittest tests.test_sharps_v2_wallets` (the workflow runs them).

**File size (spec budget: whole wallets file at most 1,350 KB, V2 fields in it at most 400 KB).** Measured on the Nov 21 10:21 AM CT inputs:
946 KB before. With the dated lists in the wallets file it was 1,607 KB (V2 fields 660 KB, of which `since_list` 364 KB), over both budgets.
With them in `since.json` it is **1,242 KB, V2 fields 295 KB**, inside both; `since.json` is 711 KB and is not budgeted (the classic page never
reads it). The budget is enforced, not warned: `build_side_cards.py` exits 3 when the wallets file is over, and the pm-cards workflow runs
`scripts/sharps_v2/check_size.py` before its publish step, so an over-budget file is never published and the last good file stays live.
`SHARPS_V2_WALLETS=file python3 -m unittest tests.test_sharps_v2_wallets` runs the same check as a test.

## V2 plays data (`markets[g].v2`, `markets[g].splits`)

Spec: `docs/sharps-v2-plays-spec.md`. Code: `scripts/sharps_v2/plays_v2.py`, called from `card()` in `scripts/build_side_cards.py`. **Additive only:**
no existing key of `live.json`, a frozen card or the shadow logs changes its name, shape or value, and `scripts/sf_rungs.py` and every gate and lock
are untouched. On the Nov 23 inputs the new builder's `live.json` with the new keys stripped is JSON-equal to the old builder's apart from `built` (the clock; equal in the pinned runs; games matched
by event and start, since same-start games come out in a hash-seed order in both builders), and so are all 925 frozen cards rebuilt from the keyframes
(`tests.test_sharps_v2_plays` runs the same strip-and-compare against `origin/main`). Sharp money is context only; the tier never changes the size.

| Key | What |
|---|---|
| `v2.shown_units`, `v2.shown_rule`, `v2.untested` | the size the page shows: flat 1u on NBA, NFL and CBB plays, 0 on CFB or without a pick, always "untested rule". The ladder stays in `sf.all.units`. Never reads the tier |
| `v2.shadow_units`, `v2.shadow_rule` | the tier-scaled size shadow `v2s-1` (user decision 2026-11-23), **beside** the flat 1u and never shown: Clear 1.5, Mixed 1, Thin 0.5, Contested 0.5, CFB 0, and `null` (never 0) when the play has no derivable tier or the market has no pick. The five values are an ordering by evidence, **not fitted to results** (one constant, `SHADOW` in `plays_v2.py`, which the tests read). Never reads an outcome and never feeds Top Reads, SM_GATE or an agree total. `shadow_rule` is always `"v2s-1"` |
| `v2.tier`, `v2.facts`, `v2.facts_na` | evidence tier (`clear`, `mixed`, `thin`, `contested`, rule `v2t-1`, `docs/sharp-tier-v2-prereg.md`) and the eight facts behind it, from fields stored at the cut. On a live card it is a preview |
| `v2.sides[<side>]` | per side: holders, money, past winners, losing record, and (NBA, NFL) holders whose CLV tier at the cut beats, loses to or is even with the close, plus `few`; college is all `few` |
| `v2.conflict`, `v2.lead`, `v2.past_winners_for` | the shown side against the other side(s); the largest past-winner wallet; every past-winner wallet on the side (the card's `list` keeps the top 4) |
| `v2.price_src`, `v2.pm` | whether `sf.all.price` is Polymarket's displayed price (`pm`) or Pinnacle's vig-included price (`pin`), with its time and age. Never a price you pay |
| `v2.exec` | best US book on the same line (DraftKings, FanDuel, BetMGM, BetRivers, bet365), Kalshi, Novig, Pinnacle, from the book tape, each with its last-change time and age (tape rows are written on change: "unchanged since", never "read at"). Reads stop at the cut. No Polymarket ask is stored, so there is no `pm_ask` yet |
| `v2.vs_fair` | `sf.all.signals.ev` plus the Pinnacle row time and ticket line, with the reason when not readable |
| `splits` | Action Network public split joined by `vault.key`, both sides as stored (live) or the last history row at or before the cut with the other side 100 minus it, marked `comp` (frozen). Absent when the feed has none, never 0. Context only |
| top `v2_slate`, `v2_plays`, `v2_tier_record` | live only: shown plays by tier, wallets that are past winners on 2 or more shown plays, field list (`v2_plays.shadow` names the shadow rule and its sizes), and the per-tier forward record when `--v2-tier-record` is given |

**Never fails the build.** The V2 block of a market, the quote tape, the log sync and the slate each run inside a guard: on any exception that market
(or that step) simply has no V2 keys and a `::warning::` line is printed. Malformed tape rows (a short or `null` list) are skipped, never indexed.
`--now` pins `built` and a live card's V2 reads.

**Shadow log.** `pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl` on `pm-holders-data`: one append-only row per rule pick on each new frozen card (key = the
graded `sf` row's key), a projection of the card's own stored `v2` block, repaired on the next run if an append was missed. The month is the **Central**
date of game start. Committed by the existing `commit_push("pmdata", "pm_cards", ...)` step.
New rows (from the shadow's merge) also carry `shadow_units` and `shadow_rule` (a projection of the card's stored `v2` block; a card frozen before the shadow
existed gets the same value from its stored tier, which is a pure function of it). The log is append-only: older rows are never rewritten and have neither
key, and every reader treats a missing key as "not logged", never as 0.

**History.** `python3 -I scripts/sharps_v2/tier_history.py [--ref REF]` re-derives the tier of every graded shown play from its card at the cut and prints
the commit hash it read, the record per tier, the Nov 20 CBB numbers and the flag list (every improving record, with its n). In-sample. It also prints the tier-scaled shadow `v2s-1` beside the flat record per sport and tier (units on units staked, ROI, standard error, n), the overall NBA+NFL+CBB
line (flat every play, flat on the plays the shadow sizes, shadow) with the standard-error caveat, and the slices where the shadow ROI is above the flat ROI of
the same plays, with n. Output as `shadow` in `--json`. On an old card
with no price check possible at the cut (the tape did not exist yet) the price facts are unknown and the play is "not derivable", not Thin.

**Size.** The V2 keys add 54 KB to a 839 KB `live.json` (183 games). `scripts/sharps_v2/check_size.py --live live/live.json` is **not** a hard gate: over
250 KB it rewrites `live.json` without the V2 keys (the V1 file), prints a `::warning::` line and exits 0, so the V1 publish is never frozen. Only
`wallets.json` keeps the hard gate (exit 3).

### Market-move flags (`markets[g].v2.flags`, `markets[g].v2.series`, forward log key `mf`)

Spec: `docs/sharps-v2-flags-spec.md` (rule `v2f-2`); code: `scripts/sharps_v2/flags_v2.py`, called from `plays_v2.market_v2`. Registration text:
`docs/sharp-tier-v2-prereg.md` "Market-move flags v2f-2" (Registered 2026-11-23). **Additive only, shown plays only** (`v2.side` set): the keys sit inside `v2`, so
`strip_plays_v2` removes them with the rest and the V1 file is unchanged byte for byte. They are **context only**: they never feed Top Reads, SM_GATE, an agree
total, `sf_rungs`, a gate, a lock, the evidence tier `v2t-1`, the shown size (flat 1u) or the shadow size `v2s-1`, and they read "what the market did", never
"sharp action confirms". User decisions of 2026-11-23: D1 the Pinnacle limit is a **fact line only**, D2 thresholds per sport and market, D3 moneyline Flag C
reads the US books' price, D4 only the books already in the tape (Pinnacle, DraftKings, FanDuel, BetMGM, BetRivers, bet365; BookMaker and Circa are never
read or shown, Fanatics and Caesars are not added), D5 the prereg is approved and registered, D7 the spec's title and eyebrow.

```
v2.flags = {
  "rule": "v2f-2", "asof": epoch, "window_min": 1440, "span_min": n|null, "src_age_min": {"pinnacle": n|null, "us": n|null},
  "pin":   {"state": "toward|away|quiet", "pts": 2.31, "t_a": 1.5, "from": -105, "to": -129, "line": -3.5|null, "t_from", "t_to", "rows", "dropped": 0} | null,   # Flag A
  "limit": {"market": "spread", "from": 3000, "to": 20000, "rows": 14, "t_from": epoch, "asof": epoch} | null,                                    # a FACT, no flag
  "line":  {"kind": "line|price", "state": "toward|away|quiet", "t_c": 1.0, "pin": {"from", "to"}, "books": 6, "same_way": 4|null,
            "by_book": {"DraftKings": [22.0, 19.5], ...}, "extreme": {"book": "BetMGM", "value": 18.5}|null} | null,                          # Flag C
  "a": "toward|away|quiet"|null, "c": same, "direction": {"a": "toward|away|none"|null, "c": ...}, "books_moved": same_way, "extreme": line.extreme,
  "why": {"pin": null|reason, "limit": null|reason, "line": null|reason} }
v2.series = {"t0": epoch, "unit": "min", "pin_px": [[x, price], ...] | null, "lines": {"Pinnacle": [[x, line], ...], ...}} | null   # x = whole minutes after t0; spreads, totals only for `lines`
v2.flags_error = "<ExceptionType>"      # only when the flag build raised: flags and series are null, every other v2 key is built, a ::warning:: is printed
v2_plays.flags = {thresholds t_a and t_c, window_min, stale_min, series_points, limit_schedule_share, books, limit_is_a_fact_only, context_only}
```

- **The window (v2f-2).** The tape writes a row only when a book's numbers change, so the number a book was showing when the 24-hour window opened is its **last row at or before the
  window start** (it held until the next row); with none, its first row inside the window. **A book needs 2 or more readable rows** (Flag A's Pinnacle and every Flag C book alike): a single
  stored row is never a move, whether it was first quoted inside the window or already showing when it opened (null, never a move of 0); two rows both before the window are a real 0. v2f-1 started the window at the first row inside it, which dropped the first
  move of the window and read a first quote as a 0; it never shipped.
- **Swapped Pinnacle rows.** A stored Pinnacle row on the other side of even money (moneyline fair at least 0.05 from 0.5; spread: the sign of the line, both at least 1.5 points from pick'em) from every US book showing at its time (2 or
  more), or, with fewer than 2 US books, from BOTH of Pinnacle's neighbouring rows, is dropped before any read (`pin.dropped`; `pinnacle_row_inconsistent` when nothing is left). Real case:
  `cfb:290201` M-OH at WMU on 2026-11-23, first row ml [-323, 260] and home +7.5, ten minutes later [245, -301] and -7.5, US books at WMU -245 to -305: a 45-point Flag A if read raw.
  A total is never checked. No graded play has a dropped row; across the whole tape it drops rows in 4 CFB moneyline and 6 CFB spread markets and nowhere else (without the 1.5 point margin it also dropped
  8 NBA and 1 CBB spread markets near -1 and +1, e.g. nba:295485).
- **Flag A** (Pinnacle's price): the two-way no-vig fair for the side (`mine / (mine + other)`, the formula of `sf_signals.ev_read`) at the last readable
  Pinnacle row at or before `asof` against the row hanging when the window opened (above). Moneylines need 2 or more readable rows; spreads and totals compare only quotes at
  the same line as now (a line change is Flag C's) and need **2 or more of them** (a first quote at a new line is `no_same_line_history`, never a 0). The row showing at the window start is picked
  across all lines: when it is at another line, `from` is the first earlier quote at the current line INSIDE the window, and with none the flag is `no_same_line_history` (home spread -3.5 three days ago, -3 two
  days ago, -3.5 an hour ago is null, not a 6-point move from a 72-hour-old quote). `pts` = fair move x 100; toward at
  `pts >= T_A`, away at `pts <= -T_A`, else quiet, compared on the stored 2-decimal value.
- **Flag C**: spreads and totals, Pinnacle's side line moved `T_C` or more AND at least 2 of the 5 US books moved their own line 1 point or more the same way.
  Moneylines (`kind: "price"`): at least 2 US books moved their no-vig price for the side by `T_A(ml)` or more one way and none the other way. A book is read only if it has history (the window rule above). `same_way` counts
  the books (Pinnacle included on a line) that moved the same way and, like `extreme` (the book furthest in the move's direction, ties to the oldest row then the
  name), exists only on a toward or away state. Direction: toward = the side costs more (a spread side's line shrank, an over's total rose, an under's fell).
- **Thresholds** (one table, `FLAGS_T_A` and `FLAGS_T_C` in `flags_v2.py`, re-exported by `plays_v2.py`; the tests hold a literal copy), measured under the v2f-2 window rule: `T_A` points of fair:
  NBA ml 4.0, spread 1.5, total 1.5; NFL 1.5, 1.5, 1.5; CBB 3.0, 1.5, 1.5; CFB 2.5, 1.5, 1.5. `T_C` points of line: NBA spread 2.0, total 3.0; NFL 1.0, 1.0; CBB 1.0, 2.5; CFB 1.5, 1.5.
  Against v2f-1: NFL total, CBB total and CFB moneyline `T_A` moved from 1.0, 1.0 and 2.0; CFB spread and total `T_C` moved from 1.0. Fire rate (either direction, readable games): Flag A 13% to 26%,
  Flag C 4% to 34% (the NFL spread floor binds); the tables are in `docs/sharps-v2-flags-spec.md` 1.2 and 1.4. A change is a new rule id (`v2f-3`) and a new registration.
- **Limit**: `to` = the last stored Pinnacle limit for the market at or before `asof` (copied from `sf_signals.limit_read`'s `now`, what `sf.all.signals.limit` stores); `from` = the limit Pinnacle
  was **showing when the 24-hour window opened** (its last stored limit at or before the window start, else its first stored limit inside the window; `t_from` is that row's time, which can be days
  earlier). The copy on the page must say exactly that: "Pinnacle limit $A when the last 24 hours began, $B now" (the cut, on a frozen card); one reading gives `from == to`. There is no `rising`,
  no percent, no chip. `v2_plays.flags.limit_schedule_share` (`limit_share_basis`) is the share of markets whose limit at the cut was above the limit showing when the window opened: NBA 99%,
  NFL 93%, CBB 97%, CFB 89% (tape at origin/main afd35efe).
- **Null, never 0, never quiet:** `why` names each missing flag: `side_unmapped`, `no_tape_rows_for_game`, `no_pinnacle_history`, `too_few_books`,
  `no_same_line_history`, `pinnacle_row_inconsistent`, `pinnacle_feed_stale`, `books_feed_stale`, `no_limit_before_cut`, `no_threshold`.
- **Point in time:** only tape rows with `t <= asof` are read (the cut on a frozen card, the build time on a live one); a later row can never change a card.
  **Staleness** (a source heartbeat more than 30 minutes older than `asof` makes the flag null) is read on **live cards only**, from the `seen` map of
  `data/exchange_edge_live.json` (`--heartbeat`, Pinnacle and "US books"; the same two sources for every sport, because the NFL `last.json` carries no read
  times). A frozen card is built after its cut, so a heartbeat read then would not be the cut's: frozen cards and the history read the tape as written and
  carry `src_age_min: null`. **A forward `mf` row is therefore read as written: the staleness rule is not applied to it** (a stale feed at the cut is not visible in a change-only tape); this is also said in the prereg.
- **Mini charts** (`v2.series`): Pinnacle's price for the side (at its current line on a spread or total) and, on spreads and totals, every stored book's line.
  Step series, at most 16 points each: consecutive equal values are dropped, the first point, the last point and the lowest and highest value are always kept, the
  rest are spread evenly by index; the row before the window sits at x = 0.
- **Size gate** (`check_size.py --live`, never fails the publish): `v2.flags` + `v2.series` over every card get 90 KB. Over it the gate drops every `series`, then
  every `flags.line.by_book`, then every `flags` (and `v2_plays.flags`), stopping at the first step that fits, and prints a `::warning::`; the V1 file and the rest of
  V2 still publish. Only if V2 as a whole is still over 250 KB does the existing rule strip all V2 keys.
- **Guard:** the flag build runs inside its own `try` in `market_v2`; on any exception that card gets `flags: null`, `series: null`, `flags_error` and a
  `::warning::v2 flags dropped for <ev> <group>: <type>` line, and every other key and the build are unaffected. A malformed tape row is skipped, never indexed.
- **Forward log:** new rows of `pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl` carry `mf`, a projection of the card's own stored `v2.flags` (no `by_book`, no series:
  `rule, asof, span_min, src_age_min, pin_state, pin_pts, pin_from, pin_to, pin_line, lim_from, lim_to, line_kind, line_state, line_pin_from, line_pin_to,
  line_books, line_same_way, line_extreme_book, line_extreme, why`), so the repair pass equals the on-time row. A card built before the flags gets a row with **no**
  `mf` key ("not logged", never quiet); a dropped flag block logs `mf: null`. Old rows are never rewritten and every reader tolerates both.
- **Coverage and size on the Nov 23 inputs** (v2f-2; a pinned `--now` of Nov 23, 1:15 PM CT, the heartbeat 9 minutes old). Live slate, 16 shown plays (NBA 8, NFL 1, CBB 5, CFB 2): every play has a flag block,
  a limit fact and (15 of 16) charts; Flag A and Flag C are readable on 15 (the other CFB play's side did not map to a team: `side_unmapped`). The 205 graded plays, re-derived from the tape at each cut: Flag A readable on
  NBA 57 of 58, NFL 32 of 33, **CBB 6 of 53**, CFB 43 of 61; Flag C on NBA 58, NFL 33, **CBB 7 of 53**, CFB 46 of 61 (the CBB tape began 2026-11-19 9:08 AM CT; earlier plays are null for good). The 61
  plays with neither flag: CBB 46 = 8 `side_unmapped` (no Vault join; 2 have tape rows) + 38 with no Pinnacle row at the cut (1 has US-book rows); CFB 15 = 9 `side_unmapped` + 6 with no Pinnacle row at the cut
  (4 have US-book rows). `live.json` grew by 15.6 KB (1,479,703 to 1,495,298 bytes) on 16 plays, about 1 KB a play (flags and charts 15.0 KB), so the 90 KB sub-budget holds about 90 plays. The 245 shown plays
  of the rebuilt frozen cards added 139 KB across the cards (0.6 KB a play) and the 245 forward log rows 107 KB (0.4 KB a row). Old (origin/main) and new builds on the same inputs and `--now`: every
  pre-existing key identical (215 live games matched by event and start, 955 frozen cards, 245 log rows without `mf`); only `v2_slate.same_wallet` lists the same keys in a different order, as it does between
  two runs of the old builder (hash-seed order).
- **Differences from the spec, said plainly:** the extra convenience keys `a`, `c`, `direction`, `books_moved`, `extreme` repeat values of `pin` and `line`; the limit has
  no `pct` or `rising` (D1); the flag block's own guard sits in `market_v2` (not in `build_side_cards.py`) so a flag failure keeps the rest of `v2`; the history
  record is `flag_record.json` beside `tier_record.json` (below), not a `v2_flag_record` key of `live.json`; `flag_history.py` (the measuring script) is not committed:
  the distributions in the spec were reproduced from the tape with the same window rule before the thresholds were used.

### `flag_record.json` (beside `tier_record.json` on `pm-cards-live`)

Written by `scripts/sharps_v2/flag_record.py` every run (workflow step "Flag record", never blocking: a failure drops the file for that run) from the frozen cards,
the graded rows and the book tape, **point in time**: a play's flags come from its own card's stored `v2.flags` when it has them, else from the tape rows at or
before its cut, never from its result. Flat 1u at the stored price at the cut (as `tier_record.json`; not the size the page shows), variant `all`, voided left out.
Slices (a play can sit in more than one: A and C are separate flags): `a_toward`, `a_away`, `c_toward`, `c_away`, `none` (at least one flag readable and neither
fired), `unreadable` (neither readable; kept apart so it never pads `none`). The limit is a fact, not a slice.

```
{ "built", "data_ref", "rule", "flags_rule": "v2f-2", "units_basis", "slices": [...], "first_logged_cut": epoch|null, "logged_rows": n (rows with mf),
  "forward_graded": n, "forward_note", "all_sports": ["nba", "nfl", "cbb"],
  "sports": {"nba|nfl|cfb|cbb": {"<slice>": {"all": cell, "in_sample": cell, "forward": cell}}}, "all": same (NBA+NFL+CBB; CFB is a flat-1u reference) }
cell = {"w", "l", "p", "n", "units", "roi" (fraction, null at n = 0)}
```

`in_sample` = every play cut strictly before the first forward log row that carries `mf` (all plays when none); `forward` = only plays whose flags were logged at
lock, joined to the graded record, with the states the log holds: zero until a logged play is graded. `python3 -I scripts/sharps_v2/tier_history.py` prints the same
plays by slice beside the old record with no flags, and the list of every improving slice with its n ("small sample" under 30). Context only: a record, not a signal.

### Move grade (`markets[g].v2.move_grade`, forward log key `mg`)

Rule `mg-1` (`scripts/sharps_v2/move_grade.py`, spec `docs/sharps-v2-movegrade-spec.md`, text `docs/sharp-movegrade-prereg.md`, **PROPOSED, not registered**). A letter A to D for how far the market moved
**toward** a shown play in the 24 hours before the cut. Inputs: the play's stored `v2.flags` (Flag A `pin.state` and `pin.pts`; Flag C `line.state` and `line.pin` from and to) and the side's direction, nothing else:
not Pinnacle's limit, the tier, the wallets, the price, the result or anything after the cut. A pure read, computed in `plays_v2.market_v2` right after the flags in its own `try` (a failure sets `move_grade: null` and
`move_grade_error` and leaves every other key as it was). Shadow only: it never changes the shown size, `shadow_units`, the tier, the ladder, `sf_rungs`, the gates, the locks, Top Reads, SM_GATE or an agree total, and none of
those modules reads it (a test greps for it).

- **A**: a flag fired toward and the move passed the A mark (`MG_X_A` Flag A points, or `MG_X_C` Pinnacle line points); **B**: a flag fired toward; **C**: no flag fired, Pinnacle's price (`MG_M_A`) or line (`MG_M_C`) moved
  toward by at least the median 24 hour move and not that far the other way; **D**: otherwise. A value exactly at a mark takes the higher letter. A flag fired **against** gives `against: true`, `letter: null`
  (it wins over a flag fired toward) and no letter, never a low one. No flag readable gives `letter: null, against: null` and `why`: `side_unmapped`, `no_flags`, `flags_unreadable` (with `flags_why`) or `no_cutoff`. A flag
  state with no stored number is `flags_unreadable`, never a guessed D. On a moneyline `c_pts` is null and Flag C toward gives at most B.
- The marks are literal tables in `move_grade.py` (`MG_M_A`, `MG_M_C`, `MG_X_A`, `MG_X_C`), set from the tape population by `scripts/sharps_v2/move_grade_history.py`, and listed on `live.json` `v2_plays.move_grade`
  (`rule`, `spec`, `m_a`, `m_c`, `x_a`, `x_c`, `letters`, `shown`, `context_only`). `v2_plays` is an existing top key, so `V2_TOP_KEYS` does not change.
- The stored block carries its own inputs and marks, so a page can explain a letter even when the flags sub-budget dropped `v2.flags`:

```
v2.move_grade = { "rule": "mg-1", "letter": "A"|"B"|"C"|"D"|null, "against": true|false|null, "basis": "a_mark"|"c_mark"|"fired"|"drift"|"flat"|"against"|null,
  "against_by": ["a","c"]|null, "a": "toward"|"away"|"quiet"|null, "c": same, "a_pts": 2.31|null, "c_pts": -0.5|null (Pinnacle's main-line move toward the side, points; null on a moneyline),
  "c_kind": "line"|"price"|null, "c_same_way": 4|null, "c_books": 6|null, "cut": {"m_a","t_a","x_a","m_c","t_c","x_c"}|null, "why": null|"side_unmapped"|"no_flags"|"flags_unreadable"|"no_cutoff",
  "flags_why": {...}|null }
```

- **Frozen at lock, never recomputed.** A frozen card stores `v2.move_grade` computed at its cut from the flags computed at its cut. Rows of `pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl` written after this build carry
  `mg = {"rule","letter","against","basis","against_by","a_pts","c_pts","why"}`, a projection of the card's stored block written by `plays_v2.log_row` beside `mf`; the repair pass re-projects from the same block, so a
  late append equals an on-time one. A card built before the grade has no `mg` ("not logged", never D); a dropped grade logs `mg: null`.
- **Size.** The block is its own key, outside `v2.flags` and `v2.series`, so the 90 KB flags sub-budget does not count it and `check_size.enforce_flags` never drops it (a test checks every drop step). If V2 as a whole
  goes over 250 KB, `strip_plays_v2` removes it with the rest of `v2`.

### `move_grade_record.json` (beside `flag_record.json` on `pm-cards-live`)

Written by `scripts/sharps_v2/move_grade_record.py` every run (workflow step "Move grade record", never blocking: a failure drops the file for that run) from the frozen cards, the graded rows and the book tape, **point in
time**. Flat 1u at the stored price at the cut (as `tier_record.json`; not the size the page shows), variant `all`, voided left out. Slices (a play is in exactly one): `a`, `b`, `c`, `d`, `against` (the marker, no letter) and
`unreadable` (no grade; kept apart so it never pads D). Each play's grade comes from, in order (`src`): the log row's `mg` (`logged`, never recomputed), the card's stored `v2.move_grade` (`frozen`), `move_grade()` on the card's
stored `v2.flags` (`frozen_flags`), or `move_grade()` on flags re-derived from the tape rows at or before the cut (`derived`). A failure is `unreadable` with a warning, never a guess.

```
{ "built", "data_ref", "rule", "mg_rule": "mg-1", "units_basis", "slices": [...], "first_logged_cut": epoch|null, "logged_rows": n (rows with mg), "forward_graded": n (counted), "registered_cut": epoch|null, "logged_not_counted": n, "forward_note",
  "all_sports": ["nba", "nfl", "cbb"], "sports": {"nba|nfl|cfb|cbb": {"<slice>": {"all": cell, "in_sample": cell, "forward": cell}}}, "all": same (NBA+NFL+CBB; CFB is a flat-1u reference) }
cell = {"w", "l", "p", "n", "units" (flat sum, 2 places), "roi" (fraction: the UNROUNDED sum over n, 6 places, null at n = 0), "se" (one standard error of the per-play result, fraction of 1u, null under 2 plays)}
```

`in_sample` = every play cut strictly before the first log row that carries `mg` (all plays when none). `forward` = only plays whose grade was logged at lock AND whose cut is after `REGISTERED_CUT`
(a constant in `move_grade_record.py`, None until the user registers `docs/sharp-movegrade-prereg.md`), joined to the graded record. While it is None `forward` is zero and `forward_note` reads "The forward test is
proposed, not registered. Plays logged before registration do not count."; the `mg` rows keep being written, a play logged but not counted sits in `all` only (`logged_not_counted`), and `registered_cut` is published.
The Record page reads these two fields, shows "small sample" under 30 plays (one definition, as in `docs/side-card-record.md`) and the standard errors. `python3 -I scripts/sharps_v2/tier_history.py` prints the same plays by slice beside the old record with no grade as its last block, with every improving slice flagged with its n ("small sample" under 30).
Context only: a record, not a signal. The classic page does not read it.

### `tier_record.json` (beside `live.json` on `pm-cards-live`)

Written by `scripts/sharps_v2/tier_record.py` every run from the frozen cards and the graded rows of the `pm-holders-data` checkout, point in time (a
play's tier comes from its own card at its cut, never from its result). About 20 KB with the shadow cells (budget 25 KB). A failed build drops the file for that run; the V1 files still
publish. Context only: a record, not a signal.

```
{ "built": epoch, "data_ref": "<pm-holders-data commit read>", "rule": "<text>", "units_basis": "flat 1u at the stored price at the cut",
  "first_logged_cut": epoch|null, "logged_rows": n, "forward_graded": n, "forward_note": "forward starts at the first logged lock",
  "since_nov16_from": 1794808800, "all_sports": ["nba", "nfl", "cbb"], "shadow_rule": "v2s-1", "shadow_note": "<text>",
  "sports": { "nba|nfl|cfb|cbb": { "tiers": { "clear|mixed|thin|contested|none": {
        "all":       {"w", "l", "p", "n", "units", "roi", "shadow": {"units_staked", "units", "roi"} | null},
        "in_sample": {...}, "forward": {...}, "since_nov16": {...},
        "by_market": {"ml": {...}, "spread": {...}, "total": {...}} } } } },
  "all": { "tiers": { ...same shape... } } }
```

- `units` and `roi` are **flat 1u** at the stored price at the cut (a win pays 1 / price - 1, a loss -1, a push 0), not the size the page shows. `roi` =
  units / n as a fraction (0.081 = 8.1%) and is `null` when n is 0, never 0. A tier with no plays is present with zeros.
- `in_sample` = every play cut **strictly before the first row of the forward tier log** (`pm_cards/<sport>/v2_tier/*.jsonl`, written by the live builder
  at lock); with no log, every play. The tier rule (v2t-1) was written Nov 21 to 23, so these tiers are derived after the fact.
- `forward` = **only plays whose tier was logged at lock** by the live builder, joined to the graded record by key, with the tier the log holds. It
  starts at the first logged lock: until a logged play is graded it is all zeros and `forward_note` says "forward starts at the first logged lock".
  A play cut at or after the first logged lock with no log row is in `all` only.
- `since_nov16` = plays cut on or after 2026-11-16 12:00 AM Central (`since_nov16_from`), the Nov 16 shadow rules; informational, tier still derived
  after the fact, **never forward**. `all` (inside a tier) is every play.
- `none` = not derivable at the cut. It is never folded into a tier.
- `shadow` (every cell: `all`, `in_sample`, `forward`, `since_nov16`, each `by_market`) is the same plays at the tier-scaled size rule `v2s-1`:
  `units` = the sum of each play's flat result (the unit result at its own stored price: a win pays 1 / price - 1, a loss -1, a push 0) **times its shadow
  size** (Clear 1.5, Mixed 1, Thin 0.5, Contested 0.5, CFB 0), `units_staked` = the sum of the sizes (a push is staked and returns 0), `roi` = units /
  units_staked as a fraction, `null` at 0 staked (a CFB cell, an empty cell) and never 0. The `none` bucket has `shadow: null` (no tier, no size). The size
  of a forward play follows the tier the log holds. The flat fields stay the page's shown size; the shadow is a record beside it, never shown. Every cell is one
  tier, so one size: its shadow ROI equals its flat ROI by construction (CFB and the null cases aside) and only the units and the stake differ. The slices
  that mix tiers (a sport's derivable plays, the headline) are in `tier_history.py`. The file stays under 25 KB.
- `by_market` splits a tier's `all` plays by market group.
- Top-level `all` pools NBA, NFL and CBB (the sports that show a size, the page headline). CFB shows no size, so it appears under `sports.cfb` as a
  flat-1u reference only and is not pooled.
- Voided plays are left out. Variant `all` only.

**Not built yet (forward only, said explicitly):** `exec.pm_ask` (needs `bestBid` and `bestAsk` in the holders scan, spec D-P1); the grader's
`pinclose` rows, per-tier `cards_record.json` sections and `v2_tier_record.json` (the builder already reads that file when present); a one-time splits
backfill from `state.json` (spec D-P4); the splits and tape quotes of games already pruned from `sharp-data`. Tests: `python3 -m unittest tests.test_sharps_v2_plays`.
