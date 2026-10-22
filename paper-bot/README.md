# Paper Kalshi bot

A paper trader for Jacob. It asks whether Vault's own models can cover a monthly cost (default $30) on Kalshi. It simulates fills. It does not send orders.

The edge, when there is one, comes from Vault's models. An optional language-model check can only veto a trade the model already proposed. It is off unless you turn it on.

The page is [vaultfantasy.com/paper-bot/](https://vaultfantasy.com/paper-bot/). It is not in the main nav, because that nav lives in `index.html` and this change leaves existing pages alone.

## What it trades

**NBA totals** (`nba_total`). Same probability as `nba/scripts/backtest_game_vs_kalshi.py`:

```
P(over strike) = 1 - Phi((strike - mu) / sigma)
```

`mu` is the game model's projected total (the Slate page's Vault line). `sigma` is `model_state.game.sd_total`. The published writeup is `nba/docs/game-model.md`: the total ladder was positive in both halves and on both sides, but per contract it was only about +2%, marked WATCH. This bot does not restate that test and does not invent a new one. The 8% edge gate is the threshold that writeup already uses when it splits the ladder, not a new result.

The source sits out preseason, and it sits out the first 28 days of the regular season, matching the Slate page. The fitted contact term is 0, so injuries do not move the total. If that term is ever non-zero, the source stops rather than guessing a healthy total.

**CFB moneylines** (`cfb_ml`). `scripts/cfb_model.py` projects a home margin, not a total, so there is no total ladder here. The bot turns the margin into a win probability:

```
sigma = (games-weighted test-season model_miss) * sqrt(pi/2)
P(home wins) = Phi(model_margin / sigma)
```

`model_miss` is read from `data/cfb_model.json`. This is not a Kalshi backtest. The efficiency study (`docs/retro/cfb-efficiency-replication.md`) found the model does not beat the closing spread. The paper book is how we find out whether the moneyline translation pays.

Games before the model's own minimum week are skipped. A Kalshi event is used only when both team names match one projected game.

## Fills, fees, size

A paper fill buys at the live ask, YES or NO, and only when the spread is 10 cents or tighter (the same gate as `scripts/fetch-kalshi.mjs`) and the ask has size. The fee is the per-contract taker fee from the NBA Kalshi backtest: round `0.07 * p * (1 - p)` up to the next cent on every contract. Kalshi itself rounds the fee up on the whole order, which is a cent or two cheaper. Paper P&L uses the harsher number so it stays comparable to that test.

Size is fractional Kelly on price plus fee, then caps. The defaults in `config.json` are configuration, not fitted edges:

| Knob | Default |
|---|---|
| Bankroll the ledger starts from | $1,000 |
| Kelly fraction | 0.25 |
| Minimum edge (model probability minus the ask) | 0.08 |
| Max stake per trade | $25, and 2% of bankroll |
| Max stake per day | $100 |
| Max stake per market (one ticker) | $25 |
| Max stake per event (a whole ladder) | $50 |
| Daily loss stop | $50 |
| Monthly cost target | $30 |

The daily loss stop counts today's settled P&L plus the mark-to-market of positions opened today (Eastern time). When it trips, that run still settles and marks, and it does not open. `kill_switch: true` does the same. So does the `PAPER_BOT_KILL` repository variable set to `1`, `true`, or `yes`.

`bankroll_start` applies only when a ledger is created. Editing it later does not reset a ledger that already has trades.

Closing-line value is a later quote's mid on our side, minus the ask we paid. The quote from the run that opened the trade is the entry, not a close. A market that resolves before any later quote has no closing-line value. Settlement uses the market's result, not that mid.

## The ledger

Scheduled runs publish `ledger.json` on the `paper-data` branch, force-pushed as one commit, the same way Sharp Money publishes `sharp-data`. The file on `main` at `paper-bot/ledger.json` is only the empty fallback the page uses before the first run. Do not treat a local dry run as that ledger.

Every would-be trade records its time, ask, model probability, edge, and size. Vetoes record the reason. Settled rows carry payout, P&L, and closing-line value when we had a later quote. The summary carries ROI, calibration bins, and P&L by source and by month.

## Schedule

`.github/workflows/paper-bot.yml` runs at about 8:20am, 12:20pm, 5:50pm, and 11:20pm Eastern. Cron is UTC, so each of those hours is listed twice and a clock gate drops the one that is not on Eastern time. A manual run is under Actions → Paper Kalshi bot. The dry input scans and does not publish.

## What you can configure

Nothing is required for paper mode. The workflow uses `paper-bot/config.json` from `main`.

Optional sanity filter, off by default:

1. Set `llm_filter.enabled` to `true` in `paper-bot/config.json` and commit that to `main`.
2. Add a repository secret named `PAPER_BOT_LLM_API_KEY`.
3. Leave `llm_filter.url` on the OpenAI chat-completions URL, or point it at an Anthropic messages URL (`api.anthropic.com`). The model name is `llm_filter.model`.

The filter vetoes for a reported injury or lineup change, news the price is unlikely to reflect yet, a stale line, or a market that is the wrong event. A real veto sticks. A transport error skips that attempt and the next run tries again. If the flag is on and the secret is missing, trades are vetoed until the key is set.

Emergency stop, no commit: repository variable `PAPER_BOT_KILL` = `1`.

The monthly cost on the page is the number in the ledger config, unless this browser has saved its own under the key `paper-bot-cost`.

## Live trading is not implemented

`scripts/paper_bot/live.py` can build the Kalshi request signature (RSA-PSS SHA-256 over `{timestamp_ms}{METHOD}{path}`, headers `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-TIMESTAMP`, `KALSHI-ACCESS-SIGNATURE`). The key id would be `KALSHI_API_KEY`. The PEM would be `KALSHI_PRIVATE_KEY` or `KALSHI_PRIVATE_KEY_PATH`.

`LiveBroker.place_order` raises every time. There is no order HTTP call in that file. Setting `paper_only` to false makes the program exit. Setting the Kalshi env vars does nothing, because the paper bot never constructs a signer. A later change has to replace `place_order` and be reviewed on its own.

## Adding a source

1. Add a class under `scripts/paper_bot/signals/` with a `name` and `collect(self, kalshi, now) -> (proposals, note)`.
2. Register it in `SOURCES` in `scripts/paper_bot/signals/__init__.py`.
3. Add a block under `sources` in `paper-bot/config.json`.

`kalshi.markets(series, status='open')` returns parsed public quotes. A proposal needs `source`, `ticker`, `event`, `title`, `game`, `side` (`yes` or `no`), `model_prob`, `edge`, `price` (the ask), `ask_size`, `yes_bid`, `yes_ask`, and `no_bid` when the side is `no`. Put the model's inputs on `detail` so the ledger can explain the number later.

Disabled sources are skipped. A source that cannot read its model should return no proposals and a note, not a guess.

## cfb_jp_novig (Novig strategy, paper only)

A separate strategy in the same bot and ledger, tagged `source: cfb_jp_novig`. It paper-trades JP+ edges against the sportsbook open on Novig's CFB spread ladder, read through public endpoints with no key. The rules are fixed in advance and live in the docstring of `scripts/paper_bot/cfb_jp_novig.py`; the backtest behind them is the cfb-backtests RESULTS.md Update 4 (11 trades, not proven).

- Trigger: `model_margin - open_margin` on the `data/cfb_model.json` board, CFB week 7+ and bowls. Edges of 3+, 5+ and 7+ are logged (`edge_bucket`); only 5+ counts toward the pass bar.
- No look-ahead: a game that has kicked off, or that already has a final score on the board, is not entered. The paper buy is the live Novig ask at a run time before kickoff. The bot does not backfill a price it did not read before kickoff.
- Strike: at first sight of the game's Novig ladder, the strike nearest the open on JP+'s side. Stored, never changed.
- Snapshots: every 30 minutes, Novig and the equivalent Kalshi `KXNCAAFSPREAD` market, with each venue's first-listed time.
- Entry: paper-buy at the ask, 25% of the contracts offered within 2 cents of it. Exit: the last bid on a snapshot before kick. Hold-to-settlement P&L is tracked on the same row. Novig pregame fees are 0.
- Pass bar: mean profit per contract after spread > 0, z >= 2, over 60+ trades at 5+ edges. Progress is `strategies.cfb_jp_novig.progress` in `ledger.json`.
- Its rows carry `book: "novig"`, so they stay out of the Kalshi cash, caps, loss stop and equity curve.
- `python3 -m scripts.paper_bot --only cfb_jp_novig` runs just this strategy (the 30-minute pass).
