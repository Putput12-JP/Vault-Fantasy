"""Kalshi prop depth for the exchange price-gap shadow test (docs/exchange-book-gap-prereg.md). Recording only: nothing here is a price,
a signal or a bet.

`snapshot.src_kalshi` keeps the contracts resting at the best yes bid and yes ask in KAL_SIZE, which is board-only and never reached a day file.
This turns it into one row per NBA prop rung for Day.record('kaldepth', ...):

  key  <the Kalshi ticker, same key as the `kalshi` source>
  v    [yes bid, yes ask, over $, under $]
         over $   dollars resting to BUY yes at the best bid   = bid x contracts
         under $  dollars resting to BUY no at the best price  = (1 - ask) x contracts, which is the resting yes ask seen from the other side
       Kalshi contracts pay $1, so a resting order's dollars are price x contracts. Rounded to STEP so a one-contract wobble is not a row.

Top of book only (the Kalshi market list gives the best level, not the ladder), so this is NOT comparable to `novigdepth`, which sums orders
within 3 cents of the best bid. The prereg reads each exchange against its own thresholds. Props only: the game series are left out.
"""
STEP = 10   # dollars


def _r(x):
    return int(round(x / STEP)) * STEP


def depth_quotes(rows, meta, sizes, prop_series):
    """rows {ticker: [yes bid, yes ask]}, meta {ticker: {'series': ...}}, sizes {ticker: [bid contracts, ask contracts]} -> {ticker: [bid, ask, over $, under $]}.
    A rung with a missing price or size, or in a series that is not a prop series, is left out (no number is invented)."""
    out = {}
    for k, q in rows.items():
        if (meta.get(k) or {}).get('series') not in prop_series:
            continue
        sz = sizes.get(k)
        if not sz or not q or len(q) < 2 or len(sz) < 2:
            continue
        bid, ask = q[0], q[1]
        nb, na = sz[0], sz[1]
        if bid is None or ask is None or nb is None or na is None or not (0 < bid <= ask < 1):
            continue
        out[k] = [bid, ask, _r(bid * nb), _r((1 - ask) * na)]
    return out
