"""Kalshi taker fee, the same per-contract function as the NBA Kalshi backtest.

nba/scripts/backtest_game_vs_kalshi.py charges ceil(0.07 * p * (1 - p)) to the
next cent on every contract. Kalshi itself rounds the fee up on the whole
order, which is a cent or two cheaper on a multi-contract fill. Per-contract
rounding is the harsher of the two, and it is the one the published total-ladder
test used, so paper P&L is comparable to that test.
"""
import math


def taker_fee(price):
    """Fee in dollars for one contract bought at `price` (0–1)."""
    p = float(price)
    if p <= 0 or p >= 1:
        return 0.0
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def cost_cents(price):
    """Price plus fee, in whole cents, for one contract."""
    return int(round((float(price) + taker_fee(price)) * 100))
