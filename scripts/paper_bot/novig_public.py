"""Public Novig market data for the paper bot. No key, reads only, never raises.

This wraps nba/scripts/novig.py (the paced curl client the NBA board already uses) so the
paper bot does not grow a second Novig client. Every call returns [] or None on any failure,
so a Novig outage costs the strategy a snapshot and costs the rest of the bot nothing.

Units (docs.novig.com/api/concepts/money): one Novig contract pays 1 cent, so a resting
quantity of 100 is one dollar of payout. The paper bot counts $1-payout contracts, the same
unit as the Kalshi paper trades and the backtest, so size = quantity / 100.
"""
import importlib.util
import os
import re

NOVIG_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        'nba', 'scripts', 'novig.py')
LEAGUE = 'NCAAF'
UNIT = 100.0           # Novig contracts per $1 of payout
BAND = 0.02            # size counts orders within 2 cents of the best price
DEFAULT_BUDGET = 400   # requests per run


def uuid7_ms(uuid):
    """Creation time in ms from a UUIDv7 id (the first 48 bits), or None. Novig market ids are v7."""
    try:
        return int(str(uuid).replace('-', '')[:12], 16)
    except (TypeError, ValueError):
        return None


def parse_price(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if 0 < x < 1 else None


def outcome_quote(book, outcome_id, other_id, band=BAND):
    """Quote for one outcome of a two-outcome book, in dollars per $1-payout contract.

    A bid on the other outcome at p is an ask on this one at 1 - p, so this outcome's ask is
    1 - the other's best bid. ask_size is the $1-payout contracts offered within `band` of that
    best ask; bid_size the same on the bid side. Any field is None when that side is empty.
    """
    orders = (book or {}).get('orders') or {}

    def levels(oid):
        out = []
        for o in orders.get(oid) or []:
            p = parse_price(o.get('price'))
            try:
                q = float(o.get('qty'))
            except (TypeError, ValueError):
                continue
            if p is not None and q > 0:
                out.append((p, q))
        return out

    mine, theirs = levels(outcome_id), levels(other_id)
    bid = max((p for p, _ in mine), default=None)
    best_other = max((p for p, _ in theirs), default=None)
    ask = None if best_other is None else round(1 - best_other, 4)
    bid_size = None if bid is None else sum(q for p, q in mine if bid - p <= band + 1e-9) / UNIT
    ask_size = None if best_other is None else sum(q for p, q in theirs if best_other - p <= band + 1e-9) / UNIT
    return {'bid': bid, 'ask': ask, 'bid_size': bid_size, 'ask_size': ask_size}


class NovigPublic:
    """Events, markets and books for one league. `budget` caps requests per instance (one run)."""

    def __init__(self, module=None, budget=DEFAULT_BUDGET):
        self._mod = module
        self.budget = budget
        self.used = 0
        self.errors = 0

    def _novig(self):
        if self._mod is None:
            spec = importlib.util.spec_from_file_location('vault_novig_public', NOVIG_PY)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._mod = mod
        return self._mod

    def _spend(self):
        if self.used >= self.budget:
            return False
        self.used += 1
        return True

    def events(self, league=LEAGUE):
        """Open pregame events: [{eventId, description 'Away @ Home', startsTs ms, ...}]."""
        try:
            if not self._spend():
                return []
            return self._novig().pages(f'/catalog/events?league={league}&status=OPEN_PREGAME&limit=200') or []
        except Exception:
            self.errors += 1
            return []

    def markets(self, event_id):
        try:
            if not self._spend():
                return []
            return self._novig().pages(f'/catalog/markets?event={event_id}&limit=1000') or []
        except Exception:
            self.errors += 1
            return []

    def book(self, market_id):
        try:
            if not self._spend():
                return None
            d = self._novig().get(f'/catalog/markets/{market_id}/book')
            return d if isinstance(d, dict) else None
        except Exception:
            self.errors += 1
            return None


_OUTCOME = re.compile(r'^\s*(\S+)\s+([+-]?\d+(?:\.\d+)?)\s*$')


def parse_outcome(name):
    """'HAW +8.5' -> ('HAW', 8.5); 'UNM -8.5' -> ('UNM', -8.5); None when it is not a spread name."""
    m = _OUTCOME.match(str(name or ''))
    if not m or m.group(1).lower() in ('over', 'under'):
        return None
    return m.group(1), float(m.group(2))
