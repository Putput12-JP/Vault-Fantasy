# Vault NBA usage tracking

Added Nov 18 2026. Same Firebase Analytics (GA4) property as the main Vault app (`G-E2XHWWQDEQ`).

## Events

| Event | When | Parameters |
|---|---|---|
| `nba_view` | A page or tab opens (and once on first load) | `page`: the view id, e.g. `track`, `pairs`, `propboard` |
| `nba_bet_logged` | A bet is added to My Bets (a prop bet, a pick'em entry or a combo) | none |

## What it never sends
No player, game, price, bet detail, account or league. Page ids only.

## When it sends nothing
- On any host other than vaultfantasy.com. On localhost the events are collected in `window.__vfEvents` for testing.
- When the browser sends Do Not Track or Global Privacy Control.

## Reading it
GA4 Reports, Engagement, Events, then filter `nba_view` and break down by `page`. First read: after 14 days of data, to see which pages and tabs are used before cutting or merging more.

Not covered yet: the Sharps Cards/Record toggle and prop-level opens (the URL carries player ids, so they were left out on purpose).
