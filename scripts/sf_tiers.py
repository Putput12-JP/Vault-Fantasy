#!/usr/bin/env python3
"""Three registered shadow plays from the CLV tiers (Sharps audit, Step 2; docs/sharp-tier-prereg.md, written 2026-11-18).

  A  follow    a CLV-sharp wallet on the side and no CLV-sharp wallet on the other side.
  B  fade      a CLV-dull wallet on one side and none on the other: the play is the OTHER side. A sharp is not required.
             (a dull wallet on the other side of an A play is the evidence C adds, so A does not rule it out)
  C  both      A and B fire on the same side.

Tiers are scripts/pm_clv_tiers.py, as of the card's cut (games that started before it), so a card never sees its own game. The wallet
universe is frozen: a wallet counts only if it was in the ledger universe (`first_seen`) at or before REGISTERED_AT, so wallets added
later from a leaderboard cannot enter. Holders are the card's own: $250 or more on a side, hedges collapsed, excluded wallets dropped.

One play per candidate per market group per card, flat 1 unit, at the market's stored price at the cut (not an ask: none is stored). The
graded market is the rung carrying the most supporting money (the sharps' for A and C, the dull wallets' for B). Written only on cards
cut at or after REGISTERED_AT, NBA and NFL only. No row exists for an earlier card, so there is nothing in-sample.

Shadows: never on a card as a pick, never in a size, Top Reads, SM_GATE or an agree total. Sharp money is context (CLAUDE.md)."""

REGISTERED_AT = 1795068000          # 2026-11-19 12:00 AM Central: cards cut before this get no tier plays
TIER_SPORTS = ("nba", "nfl")
RULES = ("tA", "tB", "tC")
LABEL = {"tA": "Follow price-sharps", "tB": "Fade price-dull", "tC": "Both"}


def _pick(support, kf, side):
    """The market for a play: the rung with the most supporting money, and the price of `side` on it. None when the keyframe lacks it."""
    by = {}
    for x in support:
        by[x["cid"]] = by.get(x["cid"], 0) + x["usd"]
    for cid in sorted(by, key=lambda c: -by[c]):
        mk = (kf.get("mk") or {}).get(cid)
        if mk and side in (mk.get("outs") or []):
            oi = mk["outs"].index(side)
            px = (mk.get("px") or [None] * 2)[oi] if oi < len(mk.get("px") or []) else None
            return {"cid": cid, "line": mk.get("line"), "outs": mk.get("outs"), "price": px, "price_t": mk.get("px_t"),
                    "support_usd": round(by[cid])}
    return None


def tier_plays(ws, cls, tiers, first_seen, kf, cut):
    """{rule: play or None} for one market group. ws: the group's holders [{w, side, usd, cid, ...}]; cls: {wallet: class} (variant all);
    tiers: pm_clv_tiers.fit(...)['wallets'] as of `cut`; first_seen: {wallet: epoch}. A play is {side, cid, line, outs, price, price_t,
    sharp_for, sharp_against, dull_for, dull_against, support_usd, units}."""
    res = {r: None for r in RULES}
    if cut < REGISTERED_AT:
        return res
    elig = []
    for x in ws:
        fs = first_seen.get(x["w"])
        t = (tiers.get(x["w"]) or {}).get("tier")
        if fs is None or fs > REGISTERED_AT or cls.get(x["w"]) == "excluded" or t not in ("sharp", "dull"):
            continue
        elig.append(dict(x, tier=t))
    sides = sorted({x["side"] for x in ws})
    if len(sides) != 2:
        return res
    for side in sides:
        other = [s for s in sides if s != side][0]
        sh = lambda s, t: [x for x in elig if x["side"] == s and x["tier"] == t]     # noqa: E731
        sf, sa, df, da = sh(side, "sharp"), sh(other, "sharp"), sh(side, "dull"), sh(other, "dull")
        facts = {"sharp_for": len(sf), "sharp_against": len(sa), "dull_for": len(df), "dull_against": len(da)}
        fire = {"tA": bool(sf) and not sa,
                "tB": bool(da) and not df,
                }
        fire["tC"] = fire["tA"] and fire["tB"]
        for r in RULES:
            if not fire[r]:
                continue
            support = sf if r in ("tA", "tC") else da
            m = _pick(support, kf, side)
            if m is None:
                continue
            res[r] = {"side": side, "units": 1, **m, **facts}
    return res
