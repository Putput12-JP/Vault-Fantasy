# Sharp Money V2 forward log

V2 had no record of its own: the page decided Play / Watch / Passed in the browser and nothing wrote the decisions down. This is the log.

## What runs

- `sharp-money/v2/gates.js` is the one copy of the rules (the gates, the judge, the prop and game candidates). The V2 page loads it as a plain script. `scripts/track-v2-plays.mjs` loads it as a CommonJS module. `tests/v2_gates.test.mjs` runs the real page and the module on the same stored data and fails if they disagree.
- `scripts/track-v2-plays.mjs` runs in `update-sharp-money.yml` after every poll (step "Log and settle V2 plays"). It reads `data.json`, `props.json` and `prop_close_tape.json` from the run, and `data/exchange_edge_live.json`, `data/book_tape` and the box scores from the checkout. It writes `v2_plays.json` next to `data.json` on `sharp-data`.
- `scripts/snapshot_sharp_ledgers.py` copies `v2_plays.json` daily to `sharp-history` and refuses to write if a play vanished, a settled play reopened, or a play's first-sight record changed.

## One row per play

```
id, kind (prop | exch | book), sport, start, firstSeen
first   frozen at first sight: title, price {am, p, book}, refs [{n, p, edge}] (both references and each edge),
        worst, best, fairMean, cautions, gates in force
prop | game   the key: player (pid, name, market, line, side) or game (gk, teams, market, side, home line or total)
status  open | won | lost | push | void
units, settledAt, actual | final     settlement
close {p, src, n, t}, clv           the exchange close and close / price - 1
```

The id is the pick (game or player, market, side, line), never the book, so a better price at another book later does not become a second play. First sight stands.

## Settlement and CLV

- Props: the box scores the prop ledger uses (`nflverse_stats_<season>.json`, ESPN overlay fills a week nflverse lacks). No box score 36 hours after kickoff is void. Games: the board's `final`, else `exchange_edge_results.json`. No final 72 hours after kickoff is void.
- Flat 1 unit at the stored price: a win pays `1 / price - 1`, a loss is -1, a push is 0.
- CLV is the close of the exchange (which did not raise the call) over the stored price. Props: Kalshi and Novig ladders at the exact line from `prop_close_tape.json`, the same numbers `scripts/regrade_prop_clv.py` computes (checked on 527 stored calls, 0 differences). Games: Kalshi and Novig moneyline mids from `data/book_tape`; the Novig spread or total only at the exact line. A moved line is never converted: the CLV is left empty. An exchange quote wider than 6 points is not a close. The tape stores a quote only when it changes, so the last row before kickoff stands as the close if the recorder wrote some row in the 2 hours before kickoff.

## Limits

- No history. Nothing recorded the V2 decisions before this, and the stored prop ledger carries no both-reference stamp at call time, so no earlier V2 play can be reconstructed without inventing a price. The log starts empty.
- An exchange-priced play (Novig below Pinnacle) is graded against Kalshi and Polymarket as the second prices, as on the page. Its close includes Novig's own quote.
- A play is logged only while the exchange list (`exchange_edge_live.json`) is under 45 minutes old; the page has no such check.
- Prop week comes from the props feed, as in the prop ledger, so a prop first seen in the gap between a week's last game and the Wednesday feed rollover is settled against the old week number. Same limit as the prop ledger.
- The V2 page's rules are unchanged by this work. One display fix: an exchange spread or total no longer prints its line twice.
