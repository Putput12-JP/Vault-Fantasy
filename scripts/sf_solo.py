#!/usr/bin/env python3
"""`solo`: a shadow of the card's shown size (`sf`) that caps a play at 1u when it rests on a single proven wallet, or when the biggest
proven wallet on the side bet under its usual stake.

Why it exists: the benchmark's T5-LEAD seats (src/lib/t5LeadPolicy.js, ported in scripts/sf_rungs.py) floor a stake at 3u when a
wallet that has held season tier 5 for 14+ days is on the side and no tier-5 wallet is against. The floor does not look at how many
wallets are on the play or how much this wallet bet: on 2026-11-14 one wallet put 3u on three CFB spreads, on Duke at 0.27x its usual
stake. `solo` measures what the size would have done without that. A shadow only: the shown size, the pre-registered lock and the
forward test are unchanged (docs/sharp-card-prereg.md), and nothing here feeds Top Reads, SM_GATE or an agree total.

Derived from fields every card with an `sf` block already stores (the shown size, each side's `counts` and its largest proven wallet's
`press`), so the grader covers every frozen card, not only cards built from now on."""

CAP_UNITS = 1.0                 # the capped size
LEAD_UNDER = 1.0                # the biggest proven wallet's stake vs its usual stake, below this
SOLO_PROVEN = 1                 # exactly this many proven wallets on the shown side


def solo_play(market, variant="all"):
    """The `solo` play for one market group of a card: the shown size, capped when the rule applies. None when the card has no `sf`
    block for this variant (built before the shown size existed). `capped` and `was` say whether it changed and from what."""
    sf = ((market or {}).get("sf") or {}).get(variant)
    if sf is None:
        return None
    keep = {k: sf.get(k) for k in ("side", "units", "rung", "price", "price_t", "line", "outs", "cid")}
    if not sf.get("side") or not (sf.get("units") or 0) > 0:
        return dict(keep, side=None, units=0, capped=False, was=0, reason="no_shown_size")
    side = (((market.get("sides") or {}).get(sf["side"]) or {}).get(variant)) or {}
    counts = side.get("counts") or {}
    proven = (counts.get("hc") or 0) + (counts.get("sharp") or 0)
    lead = (side.get("list") or [None])[0]                      # the largest proven wallet on the side
    press = lead.get("press") if lead else None
    why = []
    if proven == SOLO_PROVEN:
        why.append("one_proven_wallet")
    if press is not None and press < LEAD_UNDER:
        why.append("lead_under_usual")
    units = min(sf["units"], CAP_UNITS) if why else sf["units"]
    return dict(keep, units=units, capped=units < sf["units"], was=sf["units"], reason=",".join(why) or None, proven=proven, press=press)
