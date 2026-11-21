# Sharps V2: page spec (standalone `sharp-money/sharps-v2/`)

Written 2026-11-21 (Central). Architect spec for the V2 Sharps and Following pages. It reconciles three audits of 2026-11-21
(plays, accounts, UI; measured on the 10:21 AM CT build of `live.json` and `wallets.json`) and reads the account data spec
`docs/sharps-v2-accounts-spec.md` (additive `wallets.json` fields, not in the live file yet).

Binding rules (CLAUDE.md and the workflow):

- Sharp money is context only. Nothing on these pages is a bet signal, nothing counts toward an agree total, nothing feeds Top Reads or
  SM_GATE, and the word "agree" never appears on them.
- The only size is the existing flat 1u on NBA, NFL and CBB plays and nothing on CFB. Every place a size appears carries the label
  "untested rule". The play tier in this spec ranks and labels plays; it never changes the 1u.
- Never invent a number: every number shown is a stored field, a count of stored rows, or arithmetic on stored fields.
- No em dashes anywhere (code, comments, copy, docs). All times Central.
- Phone first screen shows real content. New classes use the `sv2-` prefix. Motion uses the repo vocabulary (vault-ds.css section 19),
  inlined, with reduced-motion handling.
- V2 only adds files under `sharp-money/sharps-v2/` (plus tests). It does not edit `following.js`, `side-cards.js`, `index.html`,
  `scripts/build_side_cards.py`, `docs/sharps-v2-accounts-spec.md` or `docs/side-cards.md`.

---

## 1. Reconciled decisions

### 1.1 One play-tier vocabulary: Clear, Mixed, Thin, Contested

The plays audit proposed Context / Watch / Lean / Tested; the UI audit proposed Aligned / Mixed / Contested / Thin. V2 uses
**Clear, Mixed, Thin, Contested** for sized plays, plus **No play** for everything without a size. Why:

- "Watch" in the plays audit means "no size shown". The user has not approved removing the 1u from conflicted plays, so a tier whose
  name means "do not bet" would contradict the 1u printed next to it. Dropped. (Open decision D1.)
- "Lean" names a betting direction and "Tested" claims a passed test that does not exist. Dropped. The plays audit's "Tested" stays
  reserved in the data contract (section 5.4) but has no page label until a registered test passes on its final read.
- "Aligned" reads as a synonym of "agree". Replaced by "Clear", defined narrowly as "no stored fact against, and at least one stored
  price fact for".
- The plays audit's rule content is kept (any stored fact against the side makes it Contested), because it is stricter and every input
  is a stored field. The UI audit's presentation is kept (ink pips, no hue, tier visible on the collapsed row, grouped by freeze time).

Tiers are computed per shown play (sport in NBA, NFL, CBB; `sf.all.side` set; shown units > 0). Let S be the shown side and O the
other side(s) of the same market group. All fields are in today's `live.json` (paths in section 5.2).

Facts against (any one makes the play Contested):

| Id | Fact | Stored test |
|---|---|---|
| A1 | Past-winner wallets on the other side | sum over O of `sides[o].all.counts.hc + counts.sharp` >= 1 |
| A2 | Wallets that beat the close on the other side (NBA, NFL only) | sum over O of `sides[o].all.rk.sharp_n` >= 1 |
| A3 | Wallets that lose to the close are on this side | `tp.tB.side` is set and != S (the registered fade rule fires on the other side) |
| A4 | Price worse than Pinnacle's no-vig fair by 0.3 pts or more | `sf.all.signals.ev.pts` not null and <= -0.3 (0.3 is `EV_ON_PTS` in `scripts/sf_signals.py`, already registered; no new threshold) |

Facts for:

| Id | Fact | Stored test |
|---|---|---|
| B1 | Wallets that beat the close on this side (NBA, NFL only) | `sides[S].all.rk.sharp_n` >= 1 |
| B2 | Price better than Pinnacle's no-vig fair by 0.3 pts or more | `sf.all.signals.ev.pts` >= 0.3 |
| B3 | The rule picks the same side on forward-only wallet books | `sf.fwd.side == S` |
| B4 | Two or more past-winner wallets on this side | `sides[S].all.proven.wallets` >= 2 |

Tier, first match wins:

| Tier | Pips | Rule | Meaning in one line |
|---|---|---|---|
| Contested | `○○○` plus caution outline | any of A1 to A4 | "Stored facts point the other way" |
| Clear | `●●●` | none of A1 to A4, (B1 or B2), and B3 | "Nothing stored against it, and a price fact for it" |
| Thin | `●○○` | none of A1 to A4, not Clear, `proven.wallets` <= 1, not B1, and `ev.pts` null | "One wallet, no price evidence either way" |
| Mixed | `●●○` | everything else | "Nothing stored against it, nothing strong for it" |
| No play | none | no shown size: rule did not fire, CFB, or shown units 0 | context only |

College (CBB) never uses A2 or B1: `live.json` carries `rk` on college sides, but no CLV model is tested there
(`sf_tiers.TIER_SPORTS = nba, nfl`; accounts spec section 1). The page ignores college `rk`.

Applied to the 10:21 AM CT build (computed with the rules above, stdlib, from `live.json`): 11 shown plays, **Contested 10, Thin 1
(CBB Under 144.5), Mixed 0, Clear 0**. The top tier is empty and the page says so plainly. One wallet (`...5fcee5`) is among the
past-winner wallets on 7 of the 11. These are the expected values for the fixture test (section 9).

What the tier is and is not:

- It is a page-local label of this card's own stored fields. It is not a bet signal, not a size, not an input to Top Reads, SM_GATE or
  any total, and it is never called a grade, a confidence or a strength.
- It never changes the 1u. A Contested play shows the same "1u, untested rule" pill as a Clear one.
- It is unproven. Until the tier rule is registered as a dated shadow and logged at freeze (open decision D2), no per-tier record is
  shown. Once logged, the page shows the per-tier forward record with n and "no verdict until n = 300" (the existing per-sport minimum),
  and never reorders or renames tiers from those results.
- Order inside a freeze band: Clear, Mixed, Thin, Contested (Contested last, never hidden, never styled as an error).

### 1.2 Account vocabulary, and how it reads beside the play tiers

The account tier is the accounts spec's `v2.tier` (from `rk.tier`, NBA and NFL only). Play evidence lines reuse the same words, so a
wallet called "Beats the close" in the directory is the same wallet counted in "Wallets that beat the close: 2 on this side" on a play.

| Account tier (`v2.tier`) | Directory chip | Sentence | Used on a play as |
|---|---|---|---|
| `beats` | Beats the close | "Beats the closing price, N games" | B1 (this side) / A2 (other side) |
| `even` | Even with the close | "No clear price edge, N games" | not used (neither for nor against) |
| `loses` | Loses to the close | "Buys worse than the close, N games" | A3 via the registered fade rule `tB` |
| `few` | Too few closing prices | "Too few closing prices to judge (N)" | not used |
| chip | Past winner, picked after the fact | muted, never green | A1 (other side), B4 (this side) |
| chip | No bets in 30 days | muted | not used |
| chip | On the NBA price scorecard, N games | muted, own sport only | not used |

The old words "hot", "proven", "price-sharp", "price-dull", "Elite", "Prem", "Lock", "Lean", "Weak" never appear. "Hot money" is
"Past-winner money". "Sized up" is "bigger than usual" with the multiple as a figure. The play-side tier words (Clear, Mixed, Thin,
Contested) never appear on a wallet; the account words never appear as a play tier.

---

## 2. File layout

```
sharp-money/sharps-v2/
  index.html          shell: <head> (fonts, sv2.css), header, route strip, bottom tab bar (phone), <main id="sv2-main">, sheet host,
                      script tags for sv2-core.js, sv2-sharps.js, sv2-following.js (each with ?v=N, one number bumped together)
  sv2.css             every token (themes, skins, motion), the sv2- reset under .sv2, primitives (press, seg + pill, spinner, skel,
                      chips, pips, rows, sheet), both routes' layout, the one reduced-motion block
  sv2-core.js         window.SV2: router, loaders, formatters, Central time, freshness line, refresh, follow store, rail pill, press,
                      seg, sheet, pure rule functions (tierOf, bandOf, factsOf, sameWallet, v2TierOf, nameOf)
  sv2-sharps.js       route #sharps: plays list (freeze bands, tier order), collapsed rows, expanded card, context list, desktop rail
  sv2-following.js    route #following: Next up feed, directory (search, sort, sport), account sheet (record, this bet, who else)
  tests/
    sv2-core.test.mjs node, no deps: pure functions in sv2-core.js loaded through node:vm
    shoot.mjs         headless Chrome checks (layout, contrast, hit areas, words, motion) against the _dev fixtures
  _dev/               NEVER COMMITTED (section 8): fixture copies of real files, local screenshots
```

Rules for the shell:

- Standalone: no link to `vault-ds.css`, no React, no build step. The tokens and the three primitives it needs (press, seg with rail
  pill, spinner) are copied into `sv2.css` with a comment naming the vault-ds.css section they came from.
- Fonts: Google Fonts only, one `<link>`: Geist (400, 500, 600, 700), Geist Mono (500, 600), Barlow Condensed (500, 600, 700). The
  Apple skin's sans is the system stack (`-apple-system, "SF Pro Text"`), which needs no download.
- Routes: `#sharps` (default when the hash is empty or unknown) and `#following`. Sub-routes for deep links:
  `#sharps/play/<ev>/<g>` opens that play expanded and scrolled into view; `#following/acct/<sport>/<wallet>` opens the account sheet.
  `hashchange` drives rendering; the route strip and the phone tab bar both set the hash. Back closes an open sheet first.
- Theme: `data-theme="dark|light"` on `<html>`. First visit: `localStorage['sv2-theme']`, else `localStorage['vault-appearance']`
  (`light` maps to light, anything else to dark), else `prefers-color-scheme`. A header menu sets it.
- Skin: `data-sv2-skin="default|apple"` on `<html>`. First visit: `localStorage['sv2-skin']`, else `default`. Skins are token sets
  only; no component selector names a skin (fixes the UI audit's skin-detected-three-ways problem).
- All `localStorage` reads and writes are wrapped in try/catch; the page renders correctly without storage.

`sv2-core.js` public surface (all on `window.SV2`, also `module.exports` when present for the node tests):

| Name | Does |
|---|---|
| `route()`, `go(hash)` | parse / set the route |
| `load.cards(force)`, `load.wallets(force)`, `load.splits()` | fetch with cache key (2 min, or `Date.now()` when forced); resolve to the JSON or null; never throw |
| `store` | `{cards, wallets, splits, state: {cards, wallets, splits}}` with state `loading` / `ok` / `none` |
| `follows.all()`, `.has(sport, w)`, `.toggle(sport, w)`, `.at(sport, w)` | follow store (section 2.1) |
| `fmt.usd`, `fmt.cents`, `fmt.american`, `fmt.line`, `fmt.pct`, `fmt.units`, `fmt.wl`, `fmt.n` | formatters (section 6.9) |
| `ct.time`, `ct.day`, `ct.dateKey`, `ct.ago`, `ct.countdown` | Central time (`Intl.DateTimeFormat`, `timeZone: 'America/Chicago'`) |
| `fresh(el, kind)` | renders the one freshness line for the route |
| `refresh()` | the one Refresh (section 4.5) |
| `rail(strip)` | wires a sliding pill into a `.sv2-seg` strip (section 7.2) |
| `sheet.open(html, opts)`, `sheet.close()` | dialog / bottom sheet |
| `rules.tierOf(game, g)`, `rules.factsOf(game, g)`, `rules.shownUnits(game, g)`, `rules.bandOf(cut, now)`, `rules.sameWallet(plays)`, `rules.v2TierOf(walletRow)`, `rules.nameOf(walletRow, w)`, `rules.sideTotals(positions)`, `rules.sinceItems(since, sport, w, retained)`, `rules.sinceFollowed(items, followedAt, sinceFrom)` | pure functions, unit tested |
| `now()` | `Date.now()/1000`, or the dev `?now=` value (section 8) |

### 2.1 Follow storage (carries existing follows over)

- Key `vault-sharps-following`, value `{"<sport>|<wallet>": <followed-at epoch seconds>}`: the exact format `following.js` v13 writes.
  V2 reads and writes the same key and the same shape, so follows made on the classic or new page appear in V2 and the reverse.
- Never rewrite or migrate existing entries; never drop an entry because its wallet left `wallets.json` (it becomes a tombstone row,
  section 4.3).
- Listen to the `storage` event so a follow in another tab updates the page.
- Follows are per sport (`sport|wallet`), as today. The star on a row follows that sport only; the account sheet says
  "Following in NBA" so the scope is visible.

---

## 3. Tokens and palette (`sv2.css`)

All tokens are on `:root` (or `html[data-theme]` / `html[data-sv2-skin]`), prefixed `--sv2-`. Dark is the default; light is set by
`html[data-theme="light"]`, and also by `@media (prefers-color-scheme: light)` under `html:not([data-theme])`. `body` gets an explicit
`background: var(--sv2-page)`.

### 3.1 Colour roles (one meaning per colour)

| Token | Meaning (only) | Dark | Light |
|---|---|---|---|
| `--sv2-ink` | primary text, pips, focus ring, play pill background | #ECECEC | #1F1F1F |
| `--sv2-mut` | secondary text, captions, empty pip outline | #B0B0B0 | #575757 |
| `--sv2-faint` | tertiary text that still carries content (timestamps, n, "untested rule") | #A3A3A3 | #636363 |
| `--sv2-line` | hairlines, dividers, chevron strokes when decorative (non-text) | #3A3A3A | #C4C4C4 |
| `--sv2-win` | settled win, profit, positive ROI | #4ADE80 | #08703D |
| `--sv2-loss` | settled loss, negative ROI | #FA8585 | #B8202E |
| `--sv2-price` | better price: beats the close, price better than fair, line moved toward | #2DD4BF | #0B6B64 |
| `--sv2-caution` | Contested outline, thin sample, split, "untested rule" chip border | #FB923C | #9A4108 |
| `--sv2-follow` | the follow star and the "Following" pill only | #E8C66A | #7C5A06 |
| `--sv2-play-bg` / `--sv2-play-ink` | the suggested-play pill (inverse chip) | ink / page | ink / page |
| `--sv2-tint-a` | alpha of a role colour behind its chip | .10 | .10 |

Not coloured: past-winner (ink, flame-free text chip), "bigger than usual" (ink figure), the tier (ink pips and word), the score of the
staking rule (faint text in the detail only), past-winner money totals (ink). Losing-record money in the split bar is hatched
`--sv2-loss` at 55% opacity (a classification, not a result).

### 3.2 Surfaces per skin and theme

| Skin x theme | `--sv2-page` | `--sv2-card` | `--sv2-box` |
|---|---|---|---|
| default dark | #1A1A1A | #222222 | #2A2A2A |
| default light | #FAFAFA | #FFFFFF | #F5F5F5 |
| apple dark | #000000 | #1C1C1E | #2C2C2E |
| apple light | #F2F2F7 | #FFFFFF | #F2F2F7 |

### 3.3 Skin tokens (shape and type only)

| Token | default | apple |
|---|---|---|
| `--sv2-r` (card radius) | 16px | 24px |
| `--sv2-r-sm` (chip, box) | 10px | 14px |
| `--sv2-pad` (card padding) | 20px desktop, 16px phone | 16px |
| `--sv2-bw` (card border width) | 1px | 0px |
| `--sv2-sans` | 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif | -apple-system, 'SF Pro Text', 'Geist', system-ui, sans-serif |
| `--sv2-num` (numerals) | 'Geist Mono', 'SF Mono', monospace | 'Barlow Condensed', 'SF Pro Rounded', 'Geist', sans-serif |
| `--sv2-num-ls` | -.02em | .01em |

Every numeral uses `font-family: var(--sv2-num); font-variant-numeric: tabular-nums`.

### 3.4 Measured contrast (WCAG 2 relative luminance, computed 2026-11-21)

Ratios: text token on page / card / box, then on its own 10% tint composited over card / over box. AA body text needs 4.5. All pass.

| Token | default dark | apple dark | default light | apple light |
|---|---|---|---|---|
| ink | 14.73 / 13.47 / 12.15; tint 10.23 / 9.19 | 17.78 / 14.40 / 11.80; 10.99 / 8.89 | 15.79 / 16.48 / 15.12; 13.58 / 12.49 | 14.77 / 16.48 / 14.77; 13.58 / 12.17 |
| mut | 8.03 / 7.34 / 6.62; 6.09 / 5.49 | 9.68 / 7.85 / 6.43; 6.52 / 5.31 | 6.92 / 7.23 / 6.63; 6.23 / 5.74 | 6.48 / 7.23 / 6.48; 6.23 / 5.60 |
| faint | 6.90 / 6.31 / 5.69; 5.31 / 4.79 | 8.33 / 6.75 / 5.52; 5.68 / 4.64 | 5.76 / 6.01 / 5.51; 5.22 / 4.81 | 5.38 / 6.01 / 5.38; 5.22 / 4.74 |
| win | 9.99 / 9.13 / 8.24; 7.41 / 6.67 | 12.05 / 9.76 / 8.00; 8.02 / 6.47 | 5.93 / 6.18 / 5.67; 5.35 / 4.93 | 5.54 / 6.18 / 5.54; 5.35 / 4.81 |
| loss | 7.26 / 6.64 / 5.99; 5.60 / 5.05 | 8.76 / 7.10 / 5.81; 6.07 / 4.90 | 6.13 / 6.39 / 5.87; 5.43 / 5.00 | 5.73 / 6.39 / 5.73; 5.43 / 4.88 |
| price | 9.35 / 8.55 / 7.71; 7.01 / 6.33 | 11.28 / 9.14 / 7.49; 7.59 / 6.13 | 6.09 / 6.36 / 5.83; 5.49 / 5.05 | 5.70 / 6.36 / 5.70; 5.49 / 4.93 |
| caution | 7.69 / 7.03 / 6.34; 5.91 / 5.34 | 9.28 / 7.52 / 6.16; 6.35 / 5.17 | 6.42 / 6.70 / 6.15; 5.75 / 5.30 | 6.01 / 6.70 / 6.01; 5.75 / 5.17 |
| follow | 10.54 / 9.63 / 8.69; 7.73 / 6.89 | 12.72 / 10.30 / 8.44; 8.32 / 6.74 | 6.06 / 6.32 / 5.80; 5.46 / 5.07 | 5.66 / 6.32 / 5.66; 5.46 / 4.94 |
| play pill (page colour on ink) | 14.73 | 17.78 | 15.79 | 14.77 |

Changes from the UI audit's `--sm-*` proposal, made so every cell clears 4.5 including tints on box: dark mut #A3A3A3 to #B0B0B0,
dark faint #969696 to #A3A3A3, dark loss #F87171 to #FA8585; light mut #5C5C5C to #575757, faint #6B6B6B to #636363, win #0B7A43 to
#08703D, loss #C22A37 to #B8202E, price #0F766E to #0B6B64, caution #A8480A to #9A4108, follow #8A6508 to #7C5A06. One colour set per
theme serves both skins (the audit's separate Apple values are dropped: the same rule no longer has two greens).

Non-text (3:1): pips and the empty-pip outline use ink / mut (7.2 or more on card); the focus ring is 2px ink; split-bar segments and
W/L dots use win / loss / ink (all above 4.6). `--sv2-line` is decoration only (1.4 to 1.7) and never the only carrier of meaning.

---

## 4. Information architecture

Shared chrome (both routes):

- **Header row**: page title on the left, one Refresh button (44 x 44, SVG icon, `aria-label="Refresh"`) and a theme / skin menu on
  the right. Desktop also carries the route strip (`Sharps | Following`) in the header.
- **Freshness line** (one, directly under the title): `Updated 10:21 AM CT, 6 min ago`. On `#sharps` it is `live.json` `built`; on
  `#following` it is `wallets.json` `built`, with `, cards 10:21 AM CT` appended only when the two differ by more than 15 minutes.
  Older than 30 minutes adds `(older than usual)` in caution. No second clock anywhere on the page.
- **Context line** (one line, collapsible, starts collapsed on phones): "Context only. The size is a flat 1u from an untested rule."
  An info button (44 x 44) expands the "How to read this" note in place.
- **Phone**: a fixed bottom tab bar (Sharps, Following; 56px plus `env(safe-area-inset-bottom)`) is the route switch. 16px side gutter.
  No horizontal scroll at 375px: every strip that can overflow is `min-width:0; overflow-x:auto` (fixes the 36px overflow).
- **Desktop (>= 1024px)**: two columns, main 1fr (max 760px) and a 320px right rail; header full width. 768 to 1023px: one column,
  rail content folds under the list.

### 4.1 `#sharps`, phone (375 x 812)

```
+-------------------------------------+
| Sharps                     [R] [..] |  title, Refresh, menu        y 0-52
| Updated 10:21 AM CT, 6 min ago      |  freshness                   y 52-72
| 11 plays, next freezes in 24m   (i) |  summary + info              y 72-96
| [All 11][NBA 3][NFL 7][CBB 1] [Tier]|  one scroll row              y 96-140
+-------------------------------------+
| FREEZES WITHIN 1 HOUR  10:45 AM  24m|  band header (sticky)        y 148
| +---------------------------------+ |
| | [1u . untested rule]       55c  | |  collapsed row, button      y 176
| | Under 144.5  COLMB at BOSTU CBB | |
| | o.. Thin   one wallet, no price | |
| |                             [v] | |
| +---------------------------------+ |
| LATER TODAY                         |
| +---------------------------------+ |
| | [1u . untested rule]      41.5c | |
| | Trail Blazers ML  POR at NYK    | |
| | ... Contested  3 past winners   | |
| |   on the other side             | |
| +---------------------------------+ |
| (2 more rows visible)               |
+-------------------------------------+
| [ Sharps ]      [ Following ]       |  tab bar 56 + safe area
+-------------------------------------+
```

- First play row top edge at or above y = 190 (tested). About four rows in the first screen.
- The `Tier` chip opens an inline tier strip (`All / Clear 0 / Mixed 0 / Thin 1 / Contested 10`) under the scroll row; counts include
  zeros. Market (ML, Spread, Total) and Starts (Next hour, Today) filters live in the same inline panel. Choices persist in
  `sv2-filters` (storage convenience only).
- Same-wallet line, when one wallet is among the past-winner wallets on 3 or more shown plays, sits above the first band:
  "One wallet is on 7 of today's 11 plays: ...5fcee5 [see]". `[see]` filters the list to those plays. Rows it touches carry a small
  "same wallet" tag.
- Expanded row (tap): opens in place. Order: price block, evidence lines (section 6.2), money split bar with legend, wallets on each side
  (each a 44px row that opens the account sheet), public split (only when splits exist), "More detail" disclosure (rule name, staking
  score, steam and limits, forward-books variant, old ladder shadow).
- After the bands: a collapsed "No play" section: "Context: 48 games with past-winner money on a side, no play [show]". Rows are one
  line (game, side with the most past-winner money, amount). CFB rule picks appear here as "No play on CFB" with no side named.
- Zero shown plays: one line, "No plays right now. Next card freezes 6:15 PM CT." and the No play list opens by default (real content).
- Load: `.sv2-skel` rows in the list's shape (three rows), never a spinner, never a blank screen.

Freeze bands (by `cut`, T-15, Central): `Freezes within 1 hour` (cut - now <= 60 min), `Later today` (same Central date), `Tomorrow`,
`Later` (everything after). Band header: band name, first freeze time, countdown (updated every 30 s, no motion). Inside a band:
tier order (Clear, Mixed, Thin, Contested), then `proven.wallets` descending, then `cut` ascending. No global rank numbers.

### 4.2 `#sharps`, desktop (1440)

```
+----------------------------------------------------------------------------------------------+
| Sharps   [ Sharps | Following ]     [All 11][NBA 3][NFL 7][CBB 1]          [R]  [theme/skin] |
| Updated 10:21 AM CT, 6 min ago.  Context only. The size is a flat 1u from an untested rule. (i)|
+-----------------------------------------------------------------+----------------------------+
| 11 plays, next freezes in 24m                                   | NEXT TO FREEZE             |
| Tier [All 11][Clear 0][Mixed 0][Thin 1][Contested 10]           | 24m  Under 144.5  CBB      |
| Market [All][ML][Spread][Total]   Starts [All][Next hour][Today]|                            |
| One wallet is on 7 of today's 11 plays: ...5fcee5  [see]        | SAME WALLET                |
|                                                                 | ...5fcee5 on 7 plays       |
| FREEZES WITHIN 1 HOUR . 10:45 AM CT . 24m                       |                            |
| +-------------------------------------------------------------+ | TIERS                      |
| | [1u . untested rule] Under 144.5  COLMB at BOSTU . CBB  55c | | Clear 0 . Mixed 0          |
| | o.. Thin . one wallet, no price check          10:45 AM [v] | | Thin 1 . Contested 10      |
| +-------------------------------------------------------------+ | Tier record: not logged    |
| LATER TODAY                                                     | yet                        |
| +-------------------------------------------------------------+ |                            |
| | [1u . untested rule] Trail Blazers ML  POR at NYK . NBA 41.5c| | CONTEXT                   |
| | ... Contested . 3 past winners and 3 that beat the close on | | 48 games with money on a   |
| |     the other side                              6:15 PM [v] | | side, no play [show]       |
| +-------------------------------------------------------------+ |                            |
| TOMORROW                                                        |                            |
| ...                                                             |                            |
+-----------------------------------------------------------------+----------------------------+
```

Desktop expanded card is a two-column body: left the price block and evidence lines, right the split bar and the wallets on each side.

### 4.3 `#following`, phone (375 x 812)

```
+-------------------------------------+
| Following                  [R] [..] |
| Updated 10:21 AM CT, 6 min ago      |
| 3 following, 6 open bets        (i) |
| [All][NFL][CFB][NBA][CBB]           |  sport chips, no counts here
+-------------------------------------+
| NEXT UP                             |  never hidden behind a filter
| SUN 12:00 PM CT                     |  day header (Today / Tomorrow / weekday)
| +---------------------------------+ |
| | NFL  TB at DET        Sun 12:00 | |
| | Moneyline  Buccaneers           | |
| | 0xc249...8a61  $442  2.1x   [>] | |  row = button, opens sheet
| | Spread  Buccaneers              | |
| | monkeymash...  $12K  0.9x   [>] | |
| +---------------------------------+ |
| +-- LV at DEN --------------------+ |
| +---------------------------------+ |
| WALLETS 705     [search......]      |  directory below the feed
| sort [Price edge v]                 |
| [*] monkeymashingkeyboard  NFL      |
|     Beats the close . +1.0c . 130   |
+-------------------------------------+
| [ Sharps ]      [ Following ]       |
+-------------------------------------+
```

- **Next up** is the default: every open position of a followed wallet on a game that has not reached its cut, grouped by game, games
  ordered by start, day headers in Central (`Today`, `Tomorrow`, else `Sun Nov 23`). There is no "today only" default and no hidden
  "Show later games" link.
- A side with several rungs shows one row with the side total (`side_usd`, or the client sum of rung `usd` when absent) and
  "3 positions" that expands to the rung list.
- Followed wallets on the same side of one game get a line on the game card: "2 wallets you follow are on Buccaneers".
- **Zero follows**: no empty-state card. The feed slot shows real content: "Open now from wallets that beat the close" (NBA and NFL
  rows with `v2.tier == beats` that hold open positions, by `rk.post` or raw mean, up to 5), and one line "Tap the star to follow a
  wallet." When no such wallet holds a position: the 5 wallets with the most open positions, labelled "Most open positions now".
- **Follows, no open bets**: one line "No open bets from wallets you follow. Last settled: Sun 3:25 PM CT." then the directory.
- Followed wallet no longer in `sports` (left the list): a tombstone row in a "Not on the list now" group: name (from `retained` when
  present), "Left the list Nov 19" (`left_at`), its since-you-followed tally when `since.json` carries its list under `retained`, an Unfollow button.
  Without `retained`: "Not on the list now. No numbers stored for it here." Never silently dropped.

### 4.4 `#following`, desktop (1440)

```
+----------------------------------------------------------------------------------------------+
| Following   [ Sharps | Following ]     [All][NFL][CFB][NBA][CBB]           [R]  [theme/skin] |
| Updated 10:21 AM CT, 6 min ago.  Context only: no size, no pick.                          (i) |
+-----------------------------------------------------------------+----------------------------+
| 3 following . 6 open bets . 1 game with two you follow on a side| FOLLOWING (3)              |
| NEXT UP                                                         | [*] monkeymash...  NFL  3  |
| SUN NOV 23                                                      | [*] BoomLaLa       NBA  1  |
| +-- NFL . TB at DET . 12:00 PM CT -------------------------------+ | [*] 0xc249...8a61  NFL  2  |
| | Moneyline  Buccaneers  0xc249...8a61  $442   2.1x median cost [>]| |                            |
| | Spread     Buccaneers  monkeymash...  $12K   0.9x              [>]| SINCE YOU FOLLOWED         |
| | 2 wallets you follow are on Buccaneers                          | | 5-3, +0.42u flat, n=8      |
| +-----------------------------------------------------------------+ | small sample               |
+-----------------------------------------------------------------+----------------------------+
| WALLETS 705   [search name or address      ]  [20+ games] [Show inactive]   sort [Price edge v]|
| [*]  wallet                 price edge                since tracked     activity     open now  |
| [*]  monkeymashingkeyboard  Beats the close +1.0c 130 12-9 +3% flat 21  Nov 20 . 14   3 . $18K  |
|      NFL . Past winner, picked after the fact                                                  |
| ...  (24 rows, then "Show 24 more")                                                            |
+----------------------------------------------------------------------------------------------+
```

Directory rules:

- Columns: Price edge (tier word, CLV cents, n), Since tracked (forward W-L, flat ROI, n), Activity (last settled date, games in 30
  days), Open now (count, summed mark value). Record, dollar ROI and Last 10 leave the row; they live in the sheet as "Past record".
- **Every sort key is a visible column**, and the sort control lists only those: `Price edge` (tier order beats, even, few, loses; then
  `rk.post` desc, or `rk.mean` desc labelled raw when `post` is absent; nulls last), `Since tracked` (`fwd.flat_roi` desc, only rows
  with `fwd.n >= 20`, the rest after in n order), `Activity` (`n30_games` desc), `Open now` (summed `usd` desc). The column that drives
  the sort carries the sort arrow.
- Loses-to-the-close wallets sort last under Price edge (fixes the dull-above-no-data bug).
- College (CFB, CBB) default sort is `Activity`, with one line: "No price tier in college: no tested closing-price model there."
- Inactive wallets (`n30_games == 0`) are hidden behind `Show inactive (406)`.
- Search: case-insensitive substring over `name_disp` (or `name`) and the address; accepts `0x` fragments of 4 or more characters;
  results across the current sport filter; "No wallet matches 'abc'." when empty.
- Same wallet in two sports: two rows, each with its sport tag; rows of one address are adjacent when the sport filter is All.
- Phone row (two lines, 56px min): star, name, sport; then tier word, cents, n and open count. Star 44 x 44.
- Paging: 24 rows, then "Show 24 more" (a 44px button).

### 4.5 Account sheet (slim)

Phone: bottom sheet, full width inside 375px, max height 92vh, internal scroll, drag handle, close button 44 x 44 inside the viewport.
Desktop: centered dialog 720px wide.

```
+-------------------------------------------+
| ==                                   [x]  |
| monkeymashingkeyboard  NFL   [* Following]|  line 1: name, sport, follow toggle
| Beats the close, 130 games . +1.0c shrunk |  line 2: tier sentence (or raw, labelled)
| This bet: Buccaneers ML  $442 at 47c,     |  line 3 (only when opened from a bet)
| price logged 16 h ago . 2.1x median cost  |
| [ Their record | This bet | Who else ]    |  .sv2-seg.bar, rail pill
| ...tab content...                         |
+-------------------------------------------+
```

- Default tab: Their record. Header is at most three lines; no banner and no KPI tiles.
- Avatar: none. Name only (`name_disp`, else the client rule in section 5.3).
- **Their record**: (1) "Since we started tracking it (Nov 11): 12-9, flat +3.1%, n=21. Small sample." from `fwd`; (2) price edge
  sentence with n; (3) "Past record (includes games before we tracked it)": W-L, dollar ROI, flat ROI, "Won 162, the prices implied
  165" and the luck p; (4) the cut tiles (sport, this market, favourites or underdogs, this size, these odds) with n as the first line,
  selected tile marked by a 2px ink outline (not gold), "small sample" under n = 20; (5) the 30-day curve, defaulting to Flat.
  (6) "Since you followed" when followed (section 5.3 fallbacks).
- **This bet**: side total and rung list, mark value with the price age, "x median cost" (or the fallback label), held since, price
  when first seen, size over time. Line: "No entry price is stored. Amounts are shares times the market price at the last scan."
- **Who else**: from the card for this game and market: per side, wallets that beat the close (n, $), wallets that lose to the close
  (n, $), past-winner money (secondary line). When the card shows a play in this market: "The Sharps page shows a play on Buccaneers:
  1u, untested rule." When it does not: "The Sharps page has no play in this market."

### 4.6 Refresh (one)

One button per page, same Worker as today (`https://sharp-refresh.vaultfantasy.workers.dev`, Turnstile, shared 60 s cooldown). While
busy: `.sv2-spinner.xs` plus "Building 0:42", button disabled and `dataset.busy` set before the first await. It waits for a newer
`live.json` `built` (up to about 10 minutes), then reloads `live.json`, `wallets.json` and splits. States: idle "Refresh", busy, done
"Up to date" (10 s), fail "Try again" (6 s). The automatic reload every 2 minutes stays (cache key per 2 minutes).

---

## 5. Data contract

Three sources. "Today" means present in the 10:21 AM CT files. "Account spec" means `docs/sharps-v2-accounts-spec.md` (additive,
`wallets.json` `v: 2`). "Plays-data" means the future plays-data workflow publishing into `live.json`; the names below are the names
this page reads, and that workflow publishes under them or this spec is updated first. A missing or null field never becomes 0.

### 5.1 Sources and URLs

| Source | Production URL | Dev override (localhost only) |
|---|---|---|
| cards | `https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-cards-live/live.json` | `?cards=` |
| wallets | `https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-cards-live/wallets.json` | `?wallets=` |
| splits | none in production: read from `live.json` (5.4) when published | `?splits=` (a file shaped like sharp-data `data.json`: `{generated, games:[{key, splits}]}`) |
| refresh | `https://sharp-refresh.vaultfantasy.workers.dev` | `?rfurl=` |

The 4.5 MB sharp-data `data.json` is not fetched in production (open decision D3). Both files must carry `context_only: true`; if not,
the page shows no size anywhere and prints "This file is not marked context only; sizes are hidden."

### 5.2 `live.json` (today)

| Field | Used for |
|---|---|
| `built` | freshness line, price ages, countdowns' clock base when `?now` is absent |
| `context_only` | guard (5.1) |
| `games[]`: `sport`, `ev`, `gst`, `cut`, `frozen` | grouping, freeze bands, start time, hide frozen games from plays |
| `games[].vault.away`, `.home`, `.teams.away/home`, `.key` | game names ("POR at NYK"), dev splits join |
| `markets[g]` for g in `ml`, `spread`, `total` | market rows |
| `markets[g].sides[name].all.sharp_usd` | past-winner money on the side (classes `sharp` + `hc`) |
| `.all.hc_usd`, `.unproven_usd`, `.loser_usd`, `.excluded_usd` | split bar segments |
| `.all.counts.{hc, sharp, unproven, loser, excluded}` | A1, wallet counts |
| `.all.proven.{wallets, w, l, win_pct, l30_roi, lifetime_pnl}` | B4, Thin test, detail "past record of these wallets" (labelled past, never on the row) |
| `.all.list[]` (`w`, `usd`, `class`, `press`, `w_`, `l_`, `n`, `usual`, `clv`), `.losers[]`, `.unproven_list[]` | wallets on each side, same-wallet line (class `hc` or `sharp`) |
| `.all.rk.{sharp_n, sharp_usd, dull_n, dull_usd, list[]}` | A2, B1 (NBA, NFL only), Who else |
| `.all.ags.score` | detail only, faint: "Staking-rule score +0.99 (cut points fitted outside Vault, not tested here)". `ags.tier` is never shown |
| `markets[g].sf.all.{side, units, rung, reason, price, price_t, line, outs}` | the play, its price and time, its line |
| `sf.all.signals.ev.{fair, pts, why}` | A4, B2, price check line |
| `sf.all.signals.limit.{open, now}`, `sf.all.steam.{on, since_open_pts, line_open, line_now, why}` | detail only |
| `sf.all.missing[]` | detail only: "Parts of the outside staking rule Vault does not run: N" with the list |
| `sf.fwd.side` | B3, detail "Same pick on forward-only books: yes / no" |
| `tp.tB.side` | A3 |
| `markets[g].sides` keys | side names for every label |

Shown units: `rules.shownUnits` = `sf.all.shown_units` when present (plays-data, D1 in the plays audit), else 1 when the sport is NBA,
NFL or CBB and `sf.all.units > 0`, else 0. `sf.all.units` (the ladder) is shown only in the detail as "Old size ladder (shadow, not a
size): 2u". Sort by size does not exist (every size is 1u).

Price label: `sf.all.price` is the Polymarket displayed price, or Pinnacle's implied price when Polymarket had none, and today's file
does not say which. Label: "55c at the last read, 10:17 AM CT". The detail says: "Polymarket's displayed price (a mid or last trade,
not the price you would get), or Pinnacle's price when Polymarket had none. The file does not say which." When plays-data publishes
`sf.all.price_src` (`pm` or `pin`), the label names the source.

### 5.3 `wallets.json`: today and account spec

| Field | Today | Account spec | Fallback when absent and its honest label |
|---|---|---|---|
| `built`, `context_only`, `floor_usd`, `floor_usd_by_sport` | yes | unchanged | floor line "Positions under $250 ($100 CBB) are not listed" |
| `sports.<sp>.<w>.name` | yes (296 null) | `name_disp`, `name_src` | `name` when not null and not hex-like (`^0x[0-9a-fA-F]{20,}`); else "Unnamed 0x1234...abcd" |
| `rk.tier`, `rk.n`, `rk.mean`, `rk.p` | yes | unchanged | none needed |
| `rk.post`, `rk.sd` | no | A | show `rk.mean` x100 as cents labelled "raw average, not shrunk"; never the word "shrunk" without `post` |
| `v2.tier` | no | B | derive client-side with the spec's mapping (`sharp` beats, `mid` even, `dull` loses, else few); same words |
| `sc` | yes (any sport) | `sc_sport`, `sc_n` | no scorecard chip at all (the any-sport `sc` is not shown) |
| `w_`, `l_`, `n`, `roi`, `pnl`, `l30`, `d30`, `odds`, `curve`, `dive` | yes | unchanged | sheet "Past record (includes games before we tracked it)" |
| `flat_roi` | no | C | omit flat ROI in Past record |
| `fwd.{w, l, p, n, roi, flat_roi, clv_n, clv_mean}` | no | D | "Since tracked" column and sheet line read "Not published yet"; the Since tracked sort is disabled |
| `first_seen` | no | E | omit "since we started tracking (date)" |
| `last_settled`, `n30_games` | no | F | last settled from `legs[0][0]` (newest leg); inactive when `legs` is empty or `legs[0][0] < built - 30 d`; "games in 30 days" omitted; Activity sort uses last settled |
| `usual` | yes (mean cost) | unchanged | shown as "average cost per settled bet" |
| `usual_med` | no | G | "x usual" from position `press`, labelled "this position vs average cost" |
| positions: `sport, ev, gst, g, side, line, cid, usd, shares, px, px_t, press, since, cens, two_way, hist, px_first, px_first_t` | yes | unchanged | none needed |
| positions: `side_usd`, `side_rungs`, `side_press` | no | H | side total = client sum of the side's rung `usd` (stored arithmetic); rung count = rows; no side multiple, each rung shows its own `press` labelled "this position" |
| positions: `px_age_min` | no | J | `built - px_t` in minutes; `px_t` null: "price time not stored" |
| `since.json` (a separate file, not the wallets file), top `since_from`, `since_file` | no | K | "Since you followed" shows "Not available yet: the account file does not carry a dated list." when `since.json` is missing. No W-L from `legs` (biased) |
| top `retained.<sp>.<w>` | no | L | tombstone row with no numbers (4.3) |
| `exp_w`, `luck_p` | no | N | read `dive.exp_w` and `dive.all[5]` (today) |
| `legs` | yes | unchanged | used only for the last-settled fallback and Last 10 in the sheet (labelled "last 10 settled, any size") |
| `v`, `v2_fields` | `v: 1` | `v: 2` + list | the page checks `v2_fields` (array or string) for each optional key before use |

Since you followed (with `since.json`, loaded only where a follow is tallied): items `[settled_at, first_fill, r, flat, ev, stake]` (a position each) kept when `settled_at >= followedAt` and
`first_fill >= followedAt`; W = r 1, L = r 0, pushes counted apart; units = sum of `flat` over W and L (null flats skipped and counted:
"2 split positions not counted"). The count is in bets (positions); the game tally (one result per `ev`, the biggest `stake`) is shown beside it so a spread and a moneyline on one game are not read as two games. Shown as "Since you followed (Nov 14): 5-3, +0.42u flat, n=8. Small sample." When the follow is older
than `since_from`: "Covers Sep 22 onward (the file keeps 60 days)."

### 5.4 `live.json`: plays-data (future)

| Field (exact path) | Shape | Shown as | Absent |
|---|---|---|---|
| `markets[g].splits` | `{t, src, sides:{<side name>:{bets, money}}}` (integer percents, Action Network consensus at read `t`) | "Public split: 33% of bets, 64% of money (Action Network, read 10:18 AM CT). Context only." | section omitted, no placeholder |
| `sf.all.shown_units` | number | the pill | client rule (5.2) |
| `sf.all.price_src` | `pm` or `pin` | price label names source | neutral label (5.2) |
| `sf.all.exec.pm_ask` | `{px, t}` | "Polymarket ask 56c (10:17 AM CT)" | line omitted |
| `sf.all.exec.us_best` | `{book, odds, line, t}` | "Best US book on this line: -118 at FanDuel (10:15 AM CT)" | line omitted |
| `sf.all.exec.kalshi`, `.novig` | `{px, t}` | "Kalshi 54c (time)", "Novig 55c (time)" | line omitted |
| `sf.all.close_vs_fair` | `{pts, t}` after the game | detail on frozen cards: "Pinnacle close vs fair: +0.4 pts" | omitted |
| `markets[g].v2.tier`, `markets[g].v2.facts` | tier string and `{a1..a4, b1..b4}` logged at freeze | the stored tier wins over the client rule; a dev-only console warning when they differ | client rule (1.1) |
| top `v2_tier_record` | `{<tier>: {w, l, p, n, units, since}}` forward only | desktop rail and phone info panel: "Contested 3-2, n=5. No verdict until n = 300." | "Tier record: not logged yet" (desktop rail only; nothing on phone) |

Dev splits join (`?splits=` only): match `games[].key` to `live.json` `games[].vault.key`; `ml` and `sp` sides map by
`vault.teams.home[1]` / `.away[1]` (the nickname, equal to the card's side name) to `home` / `away`; `total` maps `Over`/`Under` to
`over`/`under`; `t` is the file's `generated`. A side that does not map is omitted, never guessed. On the 10:26 AM CT copy, 171 of 171
live games with a `vault.key` matched a `data.json` game and 111 carried splits.

---

## 6. Copy deck

Rules: plain English, no jargon, no over-claims. Forbidden on these pages: agree / agreement, hot, proven, elite, prem, lock / locks /
locked, lean, weak, sharp pick, best bet, guaranteed, edge (as a claim about a play), confidence, strong. Any record under n = 30 carries
"small sample"; every record carries n. Every size carries "untested rule". Numbers render with `--sv2-num`. Times are Central with
"CT" on the first time of a line.

### 6.1 Shell

| Id | String |
|---|---|
| title.sharps | Sharps |
| title.following | Following |
| tab.sharps / tab.following | Sharps / Following |
| fresh | Updated {10:21 AM} CT, {6 min} ago |
| fresh.cards | , cards {10:21 AM} CT |
| fresh.old | (older than usual) |
| fresh.none | Could not load the data file. [Try again] |
| context.sharps | Context only. The size is a flat 1u from an untested rule. |
| context.following | Context only: no size, no pick. |
| info.title | How to read this |
| info.sharps.1 | A play is a side the staking rule picked from Polymarket wallets. It is copied from an outside tracker's rules and has not passed a forward test here. |
| info.sharps.2 | The size is always 1u on NBA, NFL and CBB, and there is no size on CFB. The tier does not change the size. |
| info.sharps.3 | The tier counts stored facts for and against the side. It is a label, not a prediction, and it has no record yet. |
| info.sharps.4 | Prices are Polymarket's displayed price at the last read, before the spread you would pay. |
| info.following.1 | You see what wallets hold right now. Amounts are shares times the market price at the last scan, not what they paid. |
| info.following.2 | "Beats the close" means a wallet's buys were usually at better prices than the closing price, over 30 or more games (NBA and NFL only). In our tests that price edge was mostly gone by game time. |
| info.following.3 | "Past winner" means a good record on games before we picked the wallet. It was picked after the fact and has not held up going forward. |
| info.following.4 | Follows are saved in this browser only. |
| refresh.idle / busy / done / fail | Refresh / Building {0:42} / Up to date / Try again |
| ctx.guard | This file is not marked context only; sizes are hidden. |
| theme.menu | Theme: System, Dark, Light. Style: Default, Apple |

### 6.2 Sharps

| Id | String |
|---|---|
| summary | {11} plays, next freezes in {24m} |
| summary.zero | No plays right now. Next card freezes {6:15 PM} CT. |
| pill | 1u . untested rule |
| band.hour / today / tomorrow / later | Freezes within 1 hour / Later today / Tomorrow / Later |
| band.meta | {10:45 AM} CT . {24m} |
| tier.clear | Clear |
| tier.clear.why | Nothing stored against it, and a price fact for it |
| tier.mixed | Mixed |
| tier.mixed.why | Nothing stored against it, nothing strong for it |
| tier.thin | Thin |
| tier.thin.why | One wallet, no price check either way |
| tier.contested | Contested |
| tier.contested.why | Stored facts point the other way |
| tier.empty | No play is Clear right now. |
| row.conflict.a1 | {3} past winners on the other side |
| row.conflict.a2 | {2} that beat the close on the other side |
| row.conflict.a3 | Wallets that lose to the close are on this side |
| row.conflict.a4 | Price {1.12} pts worse than Pinnacle's fair |
| row.thin | one wallet, no price check |
| ev.a1 | Past-winner wallets: {2} on this side, {3} on the other ({$4.2K}) |
| ev.a2b1 | Wallets that beat the close: {0} on this side, {2} on the other |
| ev.a2b1.college | No price tier in college (no tested closing-price model) |
| ev.a3 | Wallets that lose to the close hold this side, so the fade rule picks the other side |
| ev.a4b2 | Price vs Pinnacle's no-vig fair: {1.12} pts {worse / better} |
| ev.a4b2.none | No fair price: {off Pinnacle's main line / not stored} |
| ev.b3 | Same pick using only games since we started tracking these wallets: {yes / no} |
| ev.b4 | Distinct past-winner wallets on this side: {1} |
| price | {55c} ({-122}) at the last read, {10:17 AM} CT |
| price.note | Polymarket's displayed price (a mid or last trade, not the price you would get), or Pinnacle's price when Polymarket had none. The file does not say which. |
| split.legend | Past-winner money . Other money . Losing-record money (hatched) |
| split.total | {$9.2K} past-winner money on {Over}, {$0} on {Under} |
| wallets.head | On {Over} / On {Under} |
| wallet.row | {name} . {Beats the close / Past winner, picked after the fact} . {$9.2K} . {3.9x} average cost |
| same.line | One wallet is on {7} of today's {11} plays: {...5fcee5} [see] |
| same.tag | same wallet |
| public.split | Public split: {33%} of bets, {64%} of money (Action Network, read {10:18 AM} CT). Context only. |
| more | More detail |
| more.rule | Staking rule step: {PRESS}. Parts of the outside rule Vault does not run: {6} |
| more.score | Staking-rule score {+0.99} (cut points fitted outside Vault, not tested here) |
| more.ladder | Old size ladder (shadow, not a size): {2u} |
| more.steam | Line {38.5} at open, {37.5} now. Pinnacle limit {$2,000} to {$3,000}. |
| more.steam.none | Pinnacle line move: not readable for this line |
| ctx.head | Context: {48} games with past-winner money on a side, no play [show] |
| ctx.row | {MIA at BUF} . {Bills} . {$17.1K} |
| ctx.cfb | No play on CFB |
| tierrec.none | Tier record: not logged yet |
| tierrec | {Contested} {3-2}, n={5}. No verdict until n = 300. |
| record.link | Play record (opens the current Sharp Money record) |
| filter.tier / market / starts | Tier / Market: All, ML, Spread, Total / Starts: All, Next hour, Today |
| filter.none | No plays match these filters. [Clear filters] |

### 6.3 Following

| Id | String |
|---|---|
| summary | {3} following, {6} open bets |
| summary.same | , {1} game with two you follow on a side |
| next.head | Next up |
| day.today / tomorrow / date | Today / Tomorrow / {Sun Nov 23} |
| game.same | {2} wallets you follow are on {Buccaneers} |
| bet.row | {Moneyline} . {Buccaneers} . {name} . {$442} . {2.1x} median cost |
| bet.row.fallback | {Moneyline} . {Buccaneers} . {name} . {$442} . {2.1x} average cost (this position) |
| bet.rungs | {3} positions |
| bet.twoway | Also holds the other side |
| zero.head | Open now from wallets that beat the close |
| zero.head.alt | Most open positions now |
| zero.hint | Tap the star to follow a wallet. |
| nobets | No open bets from wallets you follow. Last settled: {Sun 3:25 PM} CT. |
| gone.head | Not on the list now |
| gone.row | Left the list {Nov 19} |
| gone.nodata | Not on the list now. No numbers stored for it here. |
| dir.head | Wallets {705} |
| dir.search | Search name or address |
| dir.search.none | No wallet matches "{abc}". |
| dir.sort | Sort: Price edge, Since tracked, Activity, Open now |
| dir.inactive | Show inactive ({406}) |
| dir.min | 20+ games |
| dir.college | No price tier in college: no tested closing-price model there. |
| dir.more | Show {24} more |
| col.price | Price edge |
| col.fwd | Since tracked |
| col.act | Activity |
| col.open | Open now |
| tier.beats | Beats the close |
| tier.beats.s | Beats the closing price, {130} games |
| tier.even | Even with the close |
| tier.even.s | No clear price edge, {58} games |
| tier.loses | Loses to the close |
| tier.loses.s | Buys worse than the close, {144} games |
| tier.few | Too few closing prices |
| tier.few.s | Too few closing prices to judge ({8}) |
| cents | {+1.0c} vs close, shrunk |
| cents.raw | {+1.0c} vs close, raw average, not shrunk |
| chip.past | Past winner, picked after the fact |
| chip.inactive | No bets in 30 days |
| chip.sc | On the {NBA} price scorecard, {11} games |
| fwd | {12-9}, flat {+3.1%}, n={21} |
| fwd.none | Not published yet |
| act | {Nov 20} . {14} games in 30 days |
| act.fallback | Last settled {Nov 20} |
| open | {3} . {$18K} |
| star.on / off (aria) | Unfollow {name} in {NBA} / Follow {name} in {NBA} |
| following.pill | Following in {NBA} |

### 6.4 Account sheet

| Id | String |
|---|---|
| tabs | Their record / This bet / Who else |
| head.bet | This bet: {Buccaneers ML} {$442} at {47c}, price logged {16 h} ago . {2.1x} median cost |
| rec.fwd | Since we started tracking it ({Nov 11}): {12-9}, flat {+3.1%}, n={21}. Small sample. |
| rec.past.head | Past record (includes games before we tracked it) |
| rec.past | {162-132}, {+14.7%} by dollars, flat {+4.0%}, n={294} |
| rec.luck | Won {162}; the prices implied {165}. Chance of doing at least this well by luck: {69%} |
| rec.cut.n | n={22} |
| rec.cut.small | small sample |
| rec.curve | Last 30 days: Flat / Dollars |
| rec.last10 | Last 10 settled, any size |
| rec.since | Since you followed ({Nov 14}): {5-3}, {+0.42u} flat, n={8}. Small sample. |
| rec.since.window | Covers {Sep 22} onward (the file keeps 60 days). |
| rec.since.none | Not available yet: the account file does not carry a dated list. |
| bet.note | No entry price is stored. Amounts are shares times the market price at the last scan. |
| bet.age | Price logged {16 h} ago |
| bet.first | Price when first seen: {44c} ({Nov 16}) |
| bet.held | Held since {Nov 16, 12:13 AM} CT |
| bet.held.cens | Held since before we started scanning it |
| who.side | {Over}: {1} that beat the close ({$388}), {2} that lose to the close ({$1.6K}). Past-winner money {$9.2K}. |
| who.play | The Sharps page shows a play on {Over}: 1u, untested rule. |
| who.noplay | The Sharps page has no play in this market. |
| who.nocard | No card for this game yet. |
| close (aria) | Close |

### 6.5 Loading, empty, error

| Id | String |
|---|---|
| load | (skeleton rows; screen readers: "Loading plays" / "Loading wallets") |
| err.cards | Could not load the plays. [Try again] |
| err.wallets | Could not load the wallet list. [Try again] |
| err.sheet | No account details for this wallet. |

---

## 7. Accessibility and motion

### 7.1 Accessibility

- Landmarks: `header`, `nav` (route strip and tab bar, `aria-label="Pages"`, `aria-current="page"` on the active one), `main`, one `h1`
  per route, `h2` per band / section.
- Rows are `<button>` elements with `aria-expanded` and `aria-controls`; the expanded panel has `role="region"` and a label.
- Segmented strips: `<div class="sv2-seg" role="group" aria-label="...">` with `<button aria-pressed>`.
- Pips are `aria-hidden`; the tier word is always in text. Colour is never the only carrier: W/L have letters for screen readers
  (`aria-label="Last 10: 6 wins, 4 losses"`), the split bar has a text total, Contested has its word plus the caution outline.
- Sheet: `role="dialog"`, `aria-modal="true"`, labelled by the wallet name; focus moves into it, Tab is trapped, Esc and the close
  button close it, focus returns to the opener; `inert` on the page behind it.
- Hit areas: every interactive element is at least 44 x 44 (segments 36px visual with a transparent `::after` to 44px, as in the repo's
  `.vseg` rule); star, Refresh, close, info and chevrons are 44 x 44.
- Text: minimum 12px; "untested rule" 12px at `--sv2-faint` or stronger (4.6 or more everywhere). All text tokens pass 4.5 (3.4).
- Focus ring: `outline: 2px solid var(--sv2-ink); outline-offset: 2px` on `:focus-visible`.
- Refresh status and filter result counts go to one `aria-live="polite"` region.
- Works at 200% zoom and 320px width without horizontal scroll.
- Icons are inline SVG (star, chevron, refresh, close, info). No text glyph icons (no ☆, ★, ×, ›, ⟳).

### 7.2 Motion (inlined from vault-ds.css section 19)

Tokens copied into `sv2.css` `:root` with the same values: `--sv2-ease-out: cubic-bezier(0.16,1,0.3,1)`, `--sv2-ease-sheet:
cubic-bezier(0.32,0.72,0,1)`, `--sv2-ease-rail: cubic-bezier(0.65,0,0.35,1)`, `--sv2-ease-spring: cubic-bezier(0.34,1.56,0.64,1)`,
`--sv2-dur-press: 80ms`, `--sv2-dur-release: 500ms`, `--sv2-dur-rail: 400ms`, `--sv2-press-chip: .88`, `--sv2-press-btn: .94`,
`--sv2-press-card: .975`, `--sv2-press-row: .99`.

| Element | Motion |
|---|---|
| Press (`.sv2-press` + `.sv2-press-chip/btn/card/row`) | rest: `transform var(--sv2-dur-release) var(--sv2-ease-spring)`; `:active`: `scale(var(--sv2-press-scale))`, `transform var(--sv2-dur-press) ease-out`. Chips and star: chip; buttons: btn; play rows and bet rows: row; cut tiles: card. Never on a `<tr>` (no tables are used for rows) |
| Segmented strips (`.sv2-seg`, skins `--fill` and `--bar`) | one shared `.sv2-pill` inside the strip that travels: `left, width` over `var(--sv2-dur-rail) var(--sv2-ease-rail)`. Covers: route strip, sport chips, tier / market / starts filters, sort, sheet tabs, curve Flat / Dollars |
| Row expand | `grid-template-rows: 0fr` to `1fr` with `280ms var(--sv2-ease-out)`; content opacity 150ms ease; chevron SVG `rotate(180deg)` with `200ms var(--sv2-ease-out)` |
| Sheet, phone | `translateY(100%)` to 0, `420ms var(--sv2-ease-sheet)`; scrim opacity 150ms ease |
| Sheet, desktop | `scale(.98)` to 1 on `transform` with `var(--sv2-ease-spring)` 500ms, opacity 150ms ease |
| Follow star | fill change 120ms ease; star `scale` pop on `transform` only with spring |
| Wait | `.sv2-spinner` (arc, `linear .8s`, colours from tokens) only inside the Refresh button; lists use `.sv2-skel` |
| Countdowns, numbers | no animation |

Rail traps the implementation keeps (from CLAUDE.md): the pill lives inside the strip (`bottom:0` for the bar skin); it parks at
`opacity:0` until the strip has a real width; a re-rendered strip seeds the new pill at the last geometry (keyed by a stable strip id)
with transitions off and a forced reflow (`void el.offsetWidth`) before moving it; position is computed by walking `offsetParent` up
to the strip; correctness never depends on `requestAnimationFrame`, `ResizeObserver` or `IntersectionObserver` (a delegated click
handler, `hashchange` and `resize` re-place every visible strip; re-placing no-ops when already correct and skips in-flight travel); a
catch-up pass animates only an already-visible, already-placed pill. Overshoot (`--sv2-ease-spring`) is only ever on `transform`.

Reduced motion: one `@media (prefers-reduced-motion: reduce)` block at the end of `sv2.css`: pill, expand, chevron, sheet and press
transitions become `none` (state changes still apply instantly); the spinner stops (`animation: none; opacity: .6`) and keeps its
text; skeleton shimmer stops.

---

## 8. Localhost dev hooks and fixtures

- Hooks work only when `location.hostname` is `localhost`, `127.0.0.1`, `[::1]` or ends in `.localhost`. Elsewhere they are ignored.
- `?cards=`, `?wallets=`, `?splits=`, `?rfurl=`: each value must be a same-origin path starting with `/` (absolute URLs are rejected,
  so a link cannot point the page at another host). Example:
  `http://localhost:4173/sharp-money/sharps-v2/?cards=/sharp-money/sharps-v2/_dev/live.json&wallets=/sharp-money/sharps-v2/_dev/wallets.json&splits=/sharp-money/sharps-v2/_dev/splits.json&now=1795278675#sharps`
- `?now=<epoch seconds>` pins the page clock (countdowns, bands, ages) for deterministic screenshots.
- Fixtures live in `sharp-money/sharps-v2/_dev/` and are **never committed**:
  - `live.json`, `wallets.json`: copies of the real 10:21 AM CT files (`built` 1795278075).
  - `splits.json`: a copy of the real sharp-data `data.json` (10:26 AM CT), or that file reduced to `{generated, games:[{key, splits}]}`
    by dropping keys only.
  - `wallets-v2.json`: a real V2 build from the account-spec workflow's local run (same ledger, `now` pinned), when it exists.
  - Edge cases are made only by removing entries from real files (no follows, zero plays, a followed wallet missing from `sports`),
    never by editing or typing numbers.
- Git exclusion: the worktree's `info/exclude` resolves (`git rev-parse --git-path info/exclude`) to the shared
  `/Users/jacobputman/Desktop/Draft Tool/.git/info/exclude` in the main checkout, which this workflow must not touch. So the builder
  creates `sharp-money/sharps-v2/_dev/.gitignore` containing the single line `*` (it ignores itself and everything in `_dev/`, and
  changes nothing outside the worktree). Check: `git status --porcelain sharp-money/sharps-v2/_dev` prints nothing and
  `git check-ignore -v sharp-money/sharps-v2/_dev/live.json` names that file. If the user prefers the shared exclude, they add
  `sharp-money/sharps-v2/_dev/` there themselves (open decision D4).
- Server: the existing static server in `.claude/launch.json` (repo root on port 4173) serves the folder; no new server config.

---

## 9. Test plan

### 9.1 Unit (`node sharp-money/sharps-v2/tests/sv2-core.test.mjs`, no dependencies)

Pure functions loaded from `sv2-core.js` through `node:vm`. Tests that need data read `_dev/` and are skipped (reported as skipped)
when it is absent; pure tests use small inline objects.

1. `tierOf` on the 10:21 AM fixture: 11 shown plays; Contested 10, Thin 1 (`cbb-colmb-bostu-2026-11-21` total, Under), Mixed 0, Clear 0.
2. `tierOf` truth table: each of A1 to A4 alone gives Contested; B1 + B3 with no A gives Clear; B2 + B3 gives Clear; B1 without B3 gives
   Mixed; one wallet, no B1, `ev.pts` null gives Thin; CBB ignores `rk` (A2, B1 never fire for college).
3. `shownUnits`: 1 on NBA / NFL / CBB with `sf.all.units > 0`, 0 on CFB, `shown_units` wins when present; ladder units never returned.
4. No tier changes `shownUnits` (property test over every fixture play: same units for all tiers).
5. `bandOf`: boundaries at exactly 60 minutes, Central midnight, a cut tomorrow; DST change dates (Nov 1 2026, Mar 14 2027) keep Central
   dates correct.
6. `sameWallet`: `...5fcee5` on 7 of 11 on the fixture; only classes `hc` and `sharp` count.
7. `v2TierOf`: mapping `sharp` / `mid` / `dull` / `thin` / null; college rows always `few`; equals `v2.tier` when present.
8. `nameOf`: null, hex-like and normal names; `name_disp` wins.
9. `sideTotals`: sum of rung `usd` equals `side_usd` when present (on the V2 fixture); rung counts.
10. `sinceFollowed`: drops items with `first_fill` before the follow; pushes apart; null `flat` skipped and counted; window note when the
    follow predates `since_from`.
11. Fallback labels: with `rk.post` absent the formatter returns the "raw average, not shrunk" string; the word "shrunk" never appears
    without `post`.
12. Follow store: reads a `following.js`-written value unchanged, toggles round-trip the same shape, works when `localStorage` throws.
13. Dev hooks: ignored off localhost; absolute URLs rejected.
14. Formatters: `fmt.american(0.55) = -122`, `fmt.cents(0.415) = 41.5c`, `fmt.usd(17117) = $17.1K`; a null input returns null and the
    caller omits the field (no placeholder number, no dash).

### 9.2 Rendered checks (`node sharp-money/sharps-v2/tests/shoot.mjs`, headless Chrome)

Matrix: phone 375 x 812 (mobile emulation) and desktop 1440 x 900; dark and light; default and apple skins; both routes; follows set to
none, three real wallets with positions, and one wallet missing from the file.

1. First screen: on `#sharps` the first play row's top is at or above y = 190 on phone; on `#following` with three follows the first
   Next up game card is visible without scrolling; with zero follows real wallet rows are visible without scrolling.
2. No horizontal overflow: `document.documentElement.scrollWidth <= innerWidth` on every route and with the sheet open; the sheet's
   bounding box and its close button sit inside the viewport.
3. Contrast: walk every text node, composite its colour over the real stacked background, assert >= 4.5 (large text >= 3) in all four
   skin x theme combinations.
4. Hit areas: every `button`, `a`, `[role=button]` has a hit box at least 44 x 44 (including `::after` extension).
5. Words: the visible text (wallet name nodes excluded via `data-sv2-name`) matches none of the forbidden words (section 6); every
   element showing "1u" has "untested rule" in the same pill; no U+2014 in rendered text or in any file under `sharp-money/sharps-v2/`.
6. Routes: `#sharps`, `#following`, `#sharps/play/<ev>/<g>`, `#following/acct/<sport>/<w>` render; Back closes the sheet first.
7. Motion: after a real click on a segment, `pill.getAnimations()` shows two running transitions (`left`, `width`) and the no-animation
   class is not set; with `prefers-reduced-motion: reduce` emulated, no transitions run on pill, sheet or rows.
8. Fallbacks: on the V1 `wallets.json` the Since tracked column reads "Not published yet", CLV reads "raw average, not shrunk", no
   scorecard chip renders, "Since you followed" reads "Not available yet"; on the V2 fixture (when present) the stored fields render
   instead.
9. Splits: without `?splits` no public-split line exists in the DOM; with it, the line renders only for sides that mapped.
10. Follows carry over: write `vault-sharps-following` in the classic page's format, load V2, see the same follows.
11. Context guard: a fixture copy with `context_only` removed renders no size anywhere.
12. Freshness: exactly one freshness line and one Refresh per route.

### 9.3 Manual

- Real phone (iOS Safari): sheet safe area, no rubber-band pan, tab bar above the home indicator.
- Look at every screenshot of the matrix side by side with the UI audit's shots before any link is added.

---

## 10. Open decisions (for the user)

- **D1. 1u on Contested plays.** The plays audit proposes no size on conflicted plays. Not implemented: the user has not approved it.
  Doing it changes what the card shows, so it needs a CLAUDE.md update, a re-derived headline over all history with old and new
  numbers, and a PR that lists both.
- **D2. Register the tier rule.** The Clear / Mixed / Thin / Contested rule should be registered as a dated shadow (like
  `docs/sharp-shadow-rules-nov16.md`) and logged at freeze by the plays-data workflow before V2 is linked for users. Primary read
  proposed by the plays audit: price at the cut vs Pinnacle's no-vig close, n >= 300 per sport. Until then no per-tier record is shown.
- **D3. Splits in production.** Wait for plays-data to publish `markets[g].splits` into `live.json` (planned), or fetch the 4.5 MB
  sharp-data `data.json` on this page meanwhile. Spec default: wait.
- **D4. Dev fixture exclusion.** Self-ignoring `_dev/.gitignore` (spec default) or a line in the shared `info/exclude` added by the user.
- **D5. Where V2 lives.** Link it from the app and the Sharp Money shells (then add a `VAULT_CHANGELOG` entry for players), and decide
  if and when V2 replaces the classic and new layouts (ending the two-files-in-sync problem).
- **D6. Play record on V2.** V2 links to the current Record view. The headline there still lacks the Nov 20 CBB re-add note in
  `docs/side-card-record.md` (plays audit); rebuilding the record view in V2 is deferred.
- **D7. Staking-rule score.** Show the score number in the detail (spec default, faint, labelled untested) or drop it entirely.
- **D8. EV threshold reuse.** A4 and B2 reuse the registered `EV_ON_PTS = 0.3`; confirm that reusing it as a tier input is acceptable
  rather than registering a separate value.
- **D9. College `rk` on cards.** V2 ignores the CLV counts `live.json` carries for CFB and CBB sides (untested there). Confirm, or have
  the builder stop publishing them.
- **D10. Theme source.** V2 honours `vault-appearance` on first visit; confirm that mapping (charcoal and vapor both become dark).
