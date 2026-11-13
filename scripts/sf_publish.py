#!/usr/bin/env python3
"""`pub`: a shadow of the card's shown size (`sf`) with the benchmark's publish mute, so Vault can measure whether matching what the
benchmark actually publishes keeps its ROI.

Read from the benchmark's public source (scripts/syncPickStateAuthoritative.js evaluateBaseHealthV12 and the appliedStatus block,
src/lib/sharpFlowPnl.js isCancelled), 2026-11-13:
  - a side whose AGS-Unified v12 score is <= 0, or has no score, is MUTED ("agsv12_mute_below_zero", "no_agsv12_signal"), and a
    MUTED side counts as cancelled in its record, whatever its units;
  - the mute is bypassed only by the PRESS-M mirror rung and the CONFIRMED-Q1 / CONFIRMED-UNOPP slices. Vault ports PRESS-M; the
    two CONFIRMED slices are not ported, so `pub` can mute a side the benchmark would rescue (a known gap).
  - the benchmark never stakes both sides of one market; a card whose port staked both (it should not happen) is skipped.

Built only from fields every card with an `sf` block already stores (the shown size and each side's `ags`), so the grader derives it
for frozen cards written before this rule existed: the record covers the whole history, not only cards built from now on.
Context only: never the shown size, never the lock or the forward test, never Top Reads, SM_GATE or an agree total."""

BYPASS_RUNGS = ("PRESS-M",)


def pub_play(market, variant="all"):
    """The `pub` play for one market group of a card: the `sf` play (same side, units, price) or no play with the mute reason.
    None when the card has no `sf` block for this variant (built before the shown size existed)."""
    sf = ((market or {}).get("sf") or {}).get(variant)
    if sf is None:
        return None
    keep = {k: sf.get(k) for k in ("side", "units", "rung", "price", "price_t", "line", "outs", "cid")}
    if not sf.get("side") or not (sf.get("units") or 0) > 0:
        return dict(keep, side=None, units=0, reason="no_shown_size")
    staked = [s for s, x in (sf.get("sides") or {}).items() if (x.get("units") or 0) > 0]
    if len(staked) > 1:
        return dict(keep, side=None, units=0, reason="both_sides")
    ags = ((((market.get("sides") or {}).get(sf["side"]) or {}).get(variant) or {}).get("ags")) or {}
    score = ags.get("score")
    if sf.get("rung") not in BYPASS_RUNGS and (score is None or score <= 0):
        return dict(keep, side=None, units=0, reason="ags_v12_mute", ags=score)
    return dict(keep, reason=None, ags=score)
