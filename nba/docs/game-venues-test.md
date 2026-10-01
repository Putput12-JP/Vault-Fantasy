# Which market is sharpest on NBA game lines? (pre-registered)

Written and committed before any result was computed.

## Why

The Slate and Game Lines pages show "the market" as Pinnacle's line, falling back to Action Network's consensus and
then DraftKings. Kalshi and Polymarket are shown beside it as context. Last season gives three closing prices for most
games (a sportsbook, Kalshi and Polymarket), so we can measure which one predicted the winner best, and whether the
Vault game model adds anything to the sharpest of them.

## Data

- **Games:** the 2025-26 NBA season, regular season and playoffs, the game model's test season
  (`build_game_model.py` TEST, as `backtest_game_vs_kalshi.py` uses it).
- **Polymarket:** each game's moneyline token for the home team, from Polymarket's own minute price history
  (`clob.polymarket.com/prices-history`, free). Close = the last minute at or before tip, within 30 minutes of it.
  A sample of closes is cross-checked against the Pendulum Flow orderbook archive (archive.pendulumflow.com), whose
  2026 copies hold the order books but are too large to pull for a whole season.
- **Kalshi:** the pre-tip price already in the Kalshi backfill (30-minute VWAP before tip, else the last trade).
- **Sportsbook:** ESPN BET's closing moneyline (`raw/tables/game_lines.csv`), vig removed proportionally.
- **Model:** the game model's home win chance at 1 PM ET, as in `backtest_game_vs_kalshi.py`.
- Only games with all three closing prices count; one row per game (home team's chance).

## Measures (fixed now)

1. **Sharpness.** Log loss of each venue's closing home-win chance against the result. Differences between venues
   with standard errors from a paired bootstrap over games. **Decision:** Polymarket (or Kalshi) moves ahead of the
   sportsbook in the Slate's fallback order (used when Pinnacle has no line) only if its log loss is lower than the
   sportsbook's by 2+ standard errors. Otherwise the order stays.
2. **Does the model add anything to the sharpest venue?** Blend = (1 - w) x venue + w x model. Fit w on games
   before Feb 1, 2026 (minimum log loss), then score games from Feb 1 on. **GO** if the blend's log loss on those later
   games beats the venue alone by 2+ standard errors (paired bootstrap). The game model stays context unless it passes.
3. Brier scores reported alongside, not used for the verdict.
