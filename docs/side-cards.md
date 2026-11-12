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
| `ags` | SharpFlow's AGS-Unified v12 side score (`score`, -1 to +1) and its label (`tier`: FADE at 0 or below, then WEAK, LEAN, LOCK, PREMIUM, ELITE at SharpFlow's published cut points 0.781 / 0.916 / 0.957 / 0.981), with the mean wallet quality for and against, the tracked wallets counted on each side, and how many of them scored. Null when no tracked wallet with a book is on the market. A shadow field: it does not set the units. The cut points were fitted on SharpFlow's picks, not Vault's. |
| `sf` (on the market group, per variant) | The size SharpFlow's staking rules give the market: `side`, `units`, `rung` (PRESS, PRESS-X, PRESS-N, PRESS-U, PRESS-R6, FADE-F, TRUST-G, TRUST-S, TRUST-T), `reason`, `price`, `line`, and `missing`, the parts of SharpFlow's policy not ported (steam, TRUST-M, PRESS-M, the odds cap, the edge clamps, GAP-LEAD, ML-DOOR, TOP3-PICK). Built from Vault's own ledger by `scripts/sf_rungs.py`, so wallets and numbers differ from SharpFlow's. One side at most. The card shows this size. `lock_shadow` stays the pre-registered forward test and is unchanged. |
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

Each card also carries:
- `coverage`: markets read, markets missed, late reads, and the oldest read's lag;
- `vault`: the Vault game key, plus a flag when Polymarket's and Vault's start times are more than 10 minutes apart;
- `ledger_run_at`: when the ledger was last refreshed;
- frozen cards also carry `test`: whether the card counts for the forward test, and why not (built late, a stale ledger, or a
  duplicate of an earlier card for a postponed game).
