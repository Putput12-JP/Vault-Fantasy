"""Shared helpers for the prop close tape, its Kalshi backfill and the close comparison.

A close is the last read of a book before kickoff. Everything here turns one book's read into P(over a line):
two-way American prices are de-vigged with the same power method the JS prop-lead tracker uses, and a ladder
(Kalshi, Novig: P(over k) at several strikes) is read at the line only where it has that strike.
"""
import math
import re
import unicodedata

MIN_P, MAX_P = 0.005, 0.995


def nkey(s):
    """Same player key as build_best_bets.mjs / fetch-kalshi-props.mjs: lowercase a-z only, accents stripped."""
    s = unicodedata.normalize('NFD', str(s or '').lower())
    return re.sub(r'[^a-z]', '', ''.join(c for c in s if not unicodedata.combining(c)))


def implied(american):
    if american is None:
        return None
    a = float(american)
    if a == 0:
        return None
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def devig(over, under):
    """No-vig P(over) from two American prices. Multiplicative when the book is a straight two-way (sum <= 1),
    otherwise the power method (find k with po^k + pu^k = 1). None when either price is missing."""
    po, pu = implied(over), implied(under)
    if not po or not pu or po <= 0 or pu <= 0:
        return None
    if po + pu <= 1:
        return po / (po + pu)
    lo, hi = 1.0, 10.0
    for _ in range(40):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    return po ** k / (po ** k + pu ** k)


def clamp(p):
    return min(MAX_P, max(MIN_P, p))


def logit(p):
    p = clamp(p)
    return math.log(p / (1 - p))


def expit(x):
    return 1 / (1 + math.exp(-x))


def ladder_p_over(rows, line, interp=False):
    """P(over `line`) from a ladder of (strike, p). Exact strike only unless interp, which reads between the two
    strikes that bracket the line in logit space. Never extrapolates: outside the ladder is None, not a guess."""
    pts = sorted((float(r[0]), float(r[1])) for r in rows if r and r[0] is not None and r[1] is not None)
    if line is None or not pts:
        return None
    line = float(line)
    for k, p in pts:
        if abs(k - line) < 1e-9:
            return p
    if not interp:
        return None
    for (k0, p0), (k1, p1) in zip(pts, pts[1:]):
        if k0 < line < k1:
            w = (line - k0) / (k1 - k0)
            return expit(logit(p0) + (logit(p1) - logit(p0)) * w)
    return None


def book_p_over(entry, line, interp=False):
    """P(over line) for one tape book entry: a priced quote (line/over/under) or a ladder."""
    if not entry:
        return None
    if entry.get('ladder') is not None:
        return ladder_p_over(entry['ladder'], line, interp)
    if entry.get('line') is None or line is None or abs(float(entry['line']) - float(line)) > 1e-9:
        return None
    return devig(entry.get('over'), entry.get('under'))


def log_loss(p, won):
    p = clamp(p)
    return -math.log(p if won else 1 - p)


def brier(p, won):
    return (p - (1.0 if won else 0.0)) ** 2
