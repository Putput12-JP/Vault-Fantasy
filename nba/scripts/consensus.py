#!/usr/bin/env python3
"""
Consensus fair price engine: every venue's price for one player-stat, turned into one distribution, so a fair chance
exists for ANY line on any venue (a Kalshi 25+ rung, a DraftKings 24.5 line and a PrizePicks 23.5 line on one scale).

How: prop model v2's distribution SHAPE (negative binomial for rebounds / assists / 3PM, normal for points and combos,
variance v0 + v1 mu + v2 mu^2 + v3 (rate x minutes sd)^2, fit on 2024-25) with its MEAN set by the market. The implied
mean is the one whose distribution best matches the quotes: for one quote it reproduces it exactly, for several it
minimises the weighted squared error in log-odds (Pinnacle heavier, docs/v3-plan.md). Our own projection is not used,
only our estimate of how spread out the outcome is, so the consensus is the market's view moved between lines.

  implied_mean(stat, quotes, V, extra)   quotes = [(line, P(over line) with the vig removed, weight)]
  p_over(stat, mu, line, V, extra)       P(stat > line) at mean mu
  quotes_from(entry, venue_weights)      a board entry's books and Kalshi rungs -> quotes (pick'em lines carry no price)
"""
import math

COUNT = {'reb', 'ast', '3pm'}
WEIGHTS = {'Pinnacle': 3.0, 'Kalshi': 1.0, 'Polymarket': 1.0}   # books not named here weigh 1.5


def _nb_sf(k, mu, v):
    if mu <= 0:
        return 0.0
    cdf = 0.0
    if v <= mu * 1.0001:
        p = math.exp(-mu)
        for i in range(k + 1):
            cdf += p
            p *= mu / (i + 1)
        return max(0.0, 1 - cdf)
    r, q = mu * mu / (v - mu), mu / v
    p = q ** r
    for i in range(k + 1):
        cdf += p
        p *= (i + r) / (i + 1) * (1 - q)
    return max(0.0, 1 - cdf)


def _erf(x):                      # Abramowitz-Stegun 7.1.26, the same approximation as the page and pricing.py
    t = 1 / (1 + 0.3275911 * abs(x))
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * math.exp(-x * x)
    return y if x >= 0 else -y


def _phi(x):
    return 0.5 * (1 + _erf(x / math.sqrt(2)))


def lg(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def p_over(stat, mu, line, V, extra=0.0):
    v = V[stat]
    var = max(0.25, v[0] + v[1] * mu + v[2] * mu * mu + (v[3] * extra if len(v) > 3 and v[3] else 0.0))
    if stat in COUNT:
        return _nb_sf(int(math.floor(line)), mu, var)
    return 1 - _phi((line - mu) / math.sqrt(var))


def implied_mean(stat, quotes, V, extra=0.0):
    """The mean whose distribution matches the quotes [(line, p_over, weight)]; None without a usable quote."""
    qs = [(L, min(max(p, .02), .98), w) for L, p, w in quotes if L is not None and p is not None and 0 < p < 1 and w > 0]
    if not qs:
        return None
    hi = max(L for L, _, _ in qs) * 3 + 10
    if len(qs) == 1:                                     # P(over L | mu) rises with mu: bisect to reproduce the quote
        L, p, _ = qs[0]
        lo_, hi_ = 1e-3, hi
        for _ in range(60):
            mid = (lo_ + hi_) / 2
            if p_over(stat, mid, L, V, extra) < p:
                lo_ = mid
            else:
                hi_ = mid
        return (lo_ + hi_) / 2
    f = lambda mu: sum(w * (lg(p_over(stat, mu, L, V, extra)) - lg(p)) ** 2 for L, p, w in qs)
    grid = [1e-3 + i * hi / 60 for i in range(61)]
    i = min(range(len(grid)), key=lambda j: f(grid[j]))
    a, b = grid[max(0, i - 1)], grid[min(len(grid) - 1, i + 1)]
    g = (math.sqrt(5) - 1) / 2
    for _ in range(50):                                   # golden section around the best grid point
        c, d = b - g * (b - a), a + g * (b - a)
        if f(c) < f(d):
            b = d
        else:
            a = c
    return (a + b) / 2


def book_quote(line, over_price, under_price):
    """American odds pair -> (line, P(over) with the vig removed) or None."""
    def am(a):
        try:
            a = float(a)
        except (TypeError, ValueError):
            return None
        return None if a == 0 else 100 / (a + 100) if a > 0 else -a / (-a + 100)
    po, pu = am(over_price), am(under_price)
    if po is None or pu is None or line is None:
        return None
    return float(line), po / (po + pu)


def quotes_from(entry, exclude=None):
    """A board entry (prop_board.py) -> quotes from every priced venue except `exclude` (the venue being judged).
    Books and Polymarket from e['books'], Kalshi rungs from e['kal'] at the bid / ask mid."""
    out = []
    for bk, line, o, u, *_ in entry.get('books', []):
        if bk == exclude:
            continue
        q = book_quote(line, o, u)
        if q:
            out.append((q[0], q[1], WEIGHTS.get(bk, 1.5)))
    if exclude != 'Kalshi':
        for rung in entry.get('kal', []):
            line, bid, ask = rung[:3]
            if bid is not None and ask is not None and 0 < bid <= ask < 1:
                out.append((line, (bid + ask) / 2, WEIGHTS['Kalshi']))
    return out
