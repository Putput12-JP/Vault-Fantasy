#!/usr/bin/env python3
"""Sharps V2 spread context for a MONEYLINE play (docs/side-cards.md "Spread context"): pure functions, stdlib only.

A fact line, like the Pinnacle limit: for a moneyline play it says whether the SPREAD of the same game moved for the same side, over the same 24 hours
ending at `asof` that the market-move flags read. NOT a flag, NOT an input to the Move grade or the tier, NOT counted anywhere, NOT tracked or graded, never
a size and never a bet signal (CLAUDE.md: sharp money is context only). It is not part of any registered rule (docs/sharp-tier-v2-prereg.md and
docs/sharp-movegrade-prereg.md are untouched); it reuses the tape readers and the window rule of flags_v2.py (rule v2f-2) and adds no threshold.

What is stored, `v2.spread_ctx` (about 100 bytes), only on a moneyline market with a shown play:
    {"v": 1, "asof": t, "span_min": m, "pin": [from, to], "books": n, "toward": a, "away": b}
`pin` is Pinnacle's spread line FOR THIS SIDE (the home line, negated for the away side), `from` the line it was showing when the window opened (its last
stored row at or before the window start across lines, else its first inside the window, flags_v2._window_from), `to` its last stored row at or before
`asof`. `books` is how many of Pinnacle, DraftKings, FanDuel, BetMGM, BetRivers and bet365 can be read (two or more readable spread rows each, the flags
minimum). `toward` and `away` count the books whose own line changed at all over the window, in the flags' direction words: toward = the side's line moved so
the side costs more (+22 to +19, a favourite -3 to -4), away = the opposite. Both 0 is "has not moved". Any change counts: the page prints the numbers, so
no threshold is invented here.

Never invent a number: when it cannot be read the value is None and the reason is stored beside it (`spread_ctx_why`): never 0, never "has not moved".
Point in time: only tape rows with t <= asof are read, so a later row can never change a frozen card.
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from sharps_v2 import flags_v2 as F  # noqa: E402

SPREAD_CTX_VERSION = 1


def _n(x):
    """A stored number that can be printed: a real int or float that is neither NaN nor infinite (a NaN line is skipped, never written into a card)."""
    return F._n(x) and math.isfinite(x)


def spread_ctx(rows, norm, asof, heartbeat=None):
    """-> (ctx or None, why). `rows`: the book tape rows of the game (every book); `norm`: the play side, home | away (an over or under, or None, is
    unmapped); `asof`: the cut on a frozen card, the build time on a live one; `heartbeat`: {"pinnacle": epoch, "us": epoch} of the live feed or None (a
    frozen card reads as written). The caller calls this for a moneyline market only."""
    if norm not in ("home", "away"):
        return None, "side_unmapped"
    if not isinstance(rows, (list, tuple)) or not rows:
        return None, "no_tape_rows_for_game"
    by = F._by_book(rows, asof)
    pin, dropped = F._pin_clean(by, "spread", norm)
    pin = [r for r in pin if _n(r["line"])]                            # a NaN or infinite line is a row that cannot be read: skipped
    if not pin:
        return None, "pinnacle_row_inconsistent" if dropped else "no_spread_market"
    if len(pin) < 2:
        return None, "pinnacle_row_inconsistent" if dropped else "no_spread_history"
    if F._stale(asof, heartbeat, "pinnacle"):
        return None, "pinnacle_feed_stale"
    if F._stale(asof, heartbeat, "us"):
        return None, "books_feed_stale"
    fr, now = F._window_from(pin, asof), pin[-1]
    books, toward, away = 1, 0, 0                                      # Pinnacle itself is read (two or more rows) and counted
    s = F._dir_sign("spread", norm)                                    # -1: a smaller line for the side costs more, so it is "toward"
    d = round(s * (now["line"] - fr["line"]), 2)
    if abs(d) > F.LINE_EPS:
        toward, away = (1, 0) if d > 0 else (0, 1)
    for b in F.FLAGS_US:
        rd = [r for r in F._reads(by.get(b), "spread", norm) if _n(r["line"])]
        if not rd or not F._has_history(rd, asof):
            continue
        books += 1
        d = round(s * (rd[-1]["line"] - F._window_from(rd, asof)["line"]), 2)
        if abs(d) > F.LINE_EPS:
            toward, away = toward + (1 if d > 0 else 0), away + (1 if d < 0 else 0)
    span = round((asof - max(fr["t"], asof - F.FLAGS_WINDOW)) / 60)
    return {"v": SPREAD_CTX_VERSION, "asof": asof, "span_min": span, "pin": [fr["line"] + 0.0, now["line"] + 0.0],
            "books": books, "toward": toward, "away": away}, None
