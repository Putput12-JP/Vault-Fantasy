# Sharp Money V2 in the Halaska layout

The live page (`vaultfantasy.com/sharp-money/`) is the Halaska sidebar app in `sharp-money/index.html`, a hand-patched bundle with no JSX source in the repo. The V2 pages
are now part of it, in the same layout (sidebar sections, top bar with the status pill, Refresh, the All / NFL / CFB / NBA control and the theme button).

## How it is wired (and how to keep it)

- `sharp-money/v2-pages.js` holds every V2 page and its logic as readable code. It draws with the app's own kit (Card, Text, Badge, segmented control, section
  header, skeleton) through `window.__smKit()`.
- `sharp-money/v2/gates.js` is the one copy of the rules, shared with the standalone V2 page and the headless play log (`scripts/track-v2-plays.mjs`).
- `scripts/sharp_money_card/patch_v2.py` edits the bundle: script tags, the kit, sidebar entries, the hash routes, the sport filter, the page width, the three pages, the
  Game page sections, the phone redirect, and the old Props CLV tiles. Idempotent (`tests/test_patch_v2.py` checks a second run changes nothing and the bundle still parses).
  If another branch edits `index.html`, take their file and run `python3 scripts/sharp_money_card/patch_v2.py`. That is how a merge conflict in this file is resolved.

## What is on screen

| Sidebar | Page |
|---|---|
| Markets > Plays (new, first) | Plays / Watch / Passed with the worst-case edge, both reference prices, cautions, the measured record of that market, and how long the book has been behind. Every prop on the board against both references underneath. Sport filter from the top bar |
| Reads > Signals (new) | Scorecard for each signal: record, CLV, units with and without the 5 biggest wins, Trust / Watch / Ignore. Sharp accounts shown last, context only |
| Reads > Record (new) | V2's own forward log (once published), every rule graded, the prop board, the independent-close table, and the Vault line against the market with its record |
| Markets > Game (existing) | A "Plays on this game" read and a "Who is behind" block (each US book's number, when it last changed, the measured clock) are added under the existing page |
| Markets > Props (existing) | The three CLV tiles now show the exchange close when the ledger has it |

Board, Accounts, Top Reads and the model pages are unchanged. The landing page is still Board.

## Old and new on the Props page tiles (live ledger, 1,328 calls)

| Tile | Old | New |
|---|---|---|
| Avg closing-line value | +2.7%, "price at the call vs the close" (the close came from the price that raised the call) | **+0.1% (exchange close, 527 calls)**, with the old figure named |
| Beat the close | 1035 of 1328 (78%) | **262 of 527 (50%)** against the exchange close |
| Big plays | CLV +8.9%, 47 beat close (58) | CLV +6.0%, 10 of 16 beat the exchange close |

## Limits

- Phones still go to `new/` (the Apple-style mobile layout) from the bare URL. A phone that opens `#plays`, `#signals` or `#record` stays on this page, which is responsive.
  `new/` has no V2 pages: it is under PR #132, so it is not touched here.
- The V2 forward log shows "Not started" until `v2_plays.json` is published on `sharp-data` (PR #137).
- "Who is behind" needs `data/book_age.json`, which the Update Sharp Money workflow writes; until its first commit to `main` that block says so.
