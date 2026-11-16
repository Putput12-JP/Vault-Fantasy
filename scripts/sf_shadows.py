#!/usr/bin/env python3
"""Three shadows of the card's shown size (`sf`), registered 2026-11-16 after the audit of the first 100 graded plays
(docs/sharp-shadow-rules-nov16.md). Each keeps the shown play (same side, units, price) only when its rule holds:

  only  sharps only: at least one proven wallet on the shown side and no proven wallet on any other side of the market group
  two   two sharps: `only`, with at least two proven wallets on the shown side
  seas  seasoned wallets: `only`, counting a proven wallet only when its sport book has 20 or more graded positions

Why they exist: 30 of the first 100 shown plays had no proven wallet on the side (20 of 23 in CBB), plays with a proven wallet
against went 12-15, and plays whose best proven wallet had under 20 graded positions went 1-5. Those are slices picked after the
results, so none of them changes the card. Each rule is graded forward from here beside the shown size.

Shadows only: the shown size, the pre-registered lock and the forward tests are unchanged (docs/sharp-card-prereg.md,
docs/sharp-card-prereg-cbb.md), and nothing here feeds Top Reads, SM_GATE or an agree total.

Derived from fields every card with an `sf` block already stores (the shown size, each side's `counts` and its `list` of proven
wallets), so the grader covers every frozen card, not only cards built from now on. Rows for cards cut before 2026-11-16 12:00 AM Central (`in_sample`) are
in-sample: the rules were chosen after seeing them.

Known gap: a card lists at most 4 proven wallets per side (the largest by money), so `seas` reads book sizes for those 4 only. A
seasoned wallet ranked fifth or lower on a side is not seen. `only` and `two` use the side's full `counts` and have no such gap."""

RULES = ("only", "two", "seas")
TWO_MIN = 2                     # `two`: proven wallets needed on the shown side
SEASONED_N = 20                 # `seas`: graded positions in the wallet's sport book
REGISTERED_T = 1794808800       # 2026-11-16 12:00 AM Central: a card whose cut is before this is in-sample for these rules


def _proven(side):
    c = (side or {}).get("counts") or {}
    return (c.get("hc") or 0) + (c.get("sharp") or 0)


def _seasoned(side):
    return sum(1 for w in (side or {}).get("list") or [] if (w.get("n") or 0) >= SEASONED_N)


def shadow_plays(market, variant="all"):
    """{rule: play} for one market group of a card. A play is the `sf` play when the rule holds, else no play with the reason.
    None when the card has no `sf` block for this variant (built before the shown size existed)."""
    sf = ((market or {}).get("sf") or {}).get(variant)
    if sf is None:
        return None
    keep = {k: sf.get(k) for k in ("side", "units", "rung", "price", "price_t", "line", "outs", "cid")}
    if not sf.get("side") or not (sf.get("units") or 0) > 0:
        return {r: dict(keep, side=None, units=0, reason="no_shown_size") for r in RULES}
    sides = market.get("sides") or {}
    mine = (sides.get(sf["side"]) or {}).get(variant) or {}
    others = [(v or {}).get(variant) or {} for k, v in sides.items() if k != sf["side"]]
    pf, pa = _proven(mine), sum(_proven(o) for o in others)
    sn_f, sn_a = _seasoned(mine), sum(_seasoned(o) for o in others)
    why = {"only": ("no_proven_for" if pf < 1 else None) or ("proven_against" if pa else None),
           "two": ("under_two_proven_for" if pf < TWO_MIN else None) or ("proven_against" if pa else None),
           "seas": ("no_seasoned_for" if sn_f < 1 else None) or ("seasoned_against" if sn_a else None)}
    facts = {"proven_for": pf, "proven_against": pa, "seasoned_for": sn_f, "seasoned_against": sn_a}
    return {r: dict(keep, reason=None, **facts) if not why[r] else dict(keep, side=None, units=0, reason=why[r], **facts)
            for r in RULES}
