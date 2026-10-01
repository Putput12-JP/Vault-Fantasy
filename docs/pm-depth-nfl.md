# How deep Polymarket NFL markets are

Dollars resting within 1 cent of the best price, per way to bet (each outcome token), for every market of the Sunday 1 PM ET slots of NFL weeks 1-3, from the Pendulum Flow orderbook archive (archive.pendulumflow.com, CC BY 4.0). Built by scripts/pm_depth_report.py. The app caps live stakes from the recorder's own order-book reads each poll; this table is the reference for what those numbers usually are.

| Market | Ways to bet | Median 24 h out | Median 6 h out | Median 1 h out | Share with $100+ (1 h) | Share with $1,000+ (1 h) |
|---|---|---|---|---|---|---|
| Moneyline | 50 | $98,398 | $272,089 | $517,813 | 100% | 100% |
| Spreads (every line) | 1,800 | $294 | $302 | $782 | 78% | 46% |
| Totals (every line) | 2,146 | $220 | $73 | $424 | 70% | 31% |
| 1st-half spreads | 1,604 | $144 | $100 | $308 | 73% | 27% |
| Team totals | 1,240 | $112 | $94 | $160 | 69% | 12% |
| Anytime touchdown | 1,356 | $20 | $34 | $84 | 44% | 13% |
| Receptions | 1,892 | $20 | $20 | $20 | 28% | 2% |
| Receiving yards | 2,684 | $20 | $20 | $20 | 23% | 1% |
| Rushing yards | 1,246 | $20 | $20 | $20 | 26% | 2% |
| Passing yards | 796 | $20 | $20 | $20 | 23% | 2% |

A way to bet with $0 has no order book at all within 1 cent, or none in that hour. Player props are a signal at most: their order books rarely hold enough to place a real stake.

