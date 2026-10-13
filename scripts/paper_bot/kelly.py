"""Fractional Kelly for a binary contract that pays $1, with the paper-bot caps.

A contract bought at cost c (price + fee, in dollars) pays 1 if it wins.
Full Kelly fraction of bankroll is (q - c) / (1 - c) when q > c, else 0.
"""
import math


def full_kelly(prob, cost):
    p = float(prob)
    c = float(cost)
    if c <= 0 or c >= 1 or p <= c:
        return 0.0
    return (p - c) / (1.0 - c)


def contracts_for(bankroll, prob, price, fee, caps, spent):
    """How many contracts to buy, and a short reason when the answer is zero.

    caps: kelly_fraction, max_stake_per_trade, max_fraction_per_trade,
          max_stake_per_day, max_stake_per_market, max_stake_per_event
    spent: day, market, event — dollars already committed in those buckets
    """
    try:
        if not all(math.isfinite(float(x)) for x in (bankroll, prob, price, fee)):
            return 0, 'non-finite input'
    except (TypeError, ValueError):
        return 0, 'non-finite input'
    cost = float(price) + float(fee)
    if cost <= 0 or cost >= 1:
        return 0, 'price'
    frac = full_kelly(prob, cost) * float(caps['kelly_fraction'])
    if frac <= 0:
        return 0, 'no edge after fees'
    stake = frac * float(bankroll)
    stake = min(stake, float(caps['max_stake_per_trade']))
    stake = min(stake, float(caps['max_fraction_per_trade']) * float(bankroll))
    room = min(
        float(caps['max_stake_per_day']) - float(spent.get('day') or 0),
        float(caps['max_stake_per_market']) - float(spent.get('market') or 0),
        float(caps['max_stake_per_event']) - float(spent.get('event') or 0),
    )
    stake = min(stake, room)
    if not math.isfinite(stake):
        return 0, 'non-finite input'
    if stake <= 0:
        return 0, 'cap'
    cents = int(round(cost * 100))
    if cents <= 0:
        return 0, 'price'
    n = int(stake * 100) // cents
    ask = spent.get('ask_size')
    if ask is not None:
        n = min(n, int(ask))
    if n < 1:
        return 0, 'below one contract'
    return n, None
