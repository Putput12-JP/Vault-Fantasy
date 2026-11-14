#!/usr/bin/env python3
"""Two checks from the benchmark's "signals aligned" row that Vault can read from its own Pinnacle tape (data/book_tape), shown on a
play and graded by slice. Context only: neither sets a size, a lock, a pick, Top Reads, SM_GATE or an agree total, and there is no
"signals aligned" count (CLAUDE.md).

  LIMIT RISING   Pinnacle's maximum stake on the market went up between the first tape row of the game and the cut: by $500 or more, or to
                 1.45x or more of the first limit (src/lib/marketAgreement.js buildLockedMarketSignals: maxDelta >= 500 or maxNow >=
                 maxOpen * 1.45). "Tested" is a limit of $3,000 or more at the cut (LIMIT_TESTED_USD). The benchmark reads the limit at
                 Pinnacle's open; Vault's first tape row is when it first recorded the game, so "open" here is that row (same gap as steam).
  PRICE VS FAIR  the Polymarket price for the side at the cut against Pinnacle's no-vig fair price for the same side at the cut, in
                 points; on at +0.3 or more (marketAgreement.js plusEv: evPct >= 0.3). The benchmark compares its ticket price (the wallets'
                 average entry) with a Pinnacle-heavy blend of sharp books; Vault has no entry price, and the tape's Consensus row is not
                 read, so this is Polymarket's price at the cut against Pinnacle alone. It behaves like closing-line value, not a true edge.
                 Spreads and totals read only when the side's line is Pinnacle's main line at the cut (the tape keeps no alt lines).

Only tape rows at or before the cut are read, so a frozen card re-derives the same answer whenever it is read."""

LIMIT_RISE_USD, LIMIT_RISE_MULT, LIMIT_TESTED_USD = 500, 1.45, 3000
EV_ON_PTS = 0.3
PIN_LINE_EPS = 0.051                       # pinnacleMain.js LINE_EPS, the same ticket-line match as sf_rungs.py
LIM_IDX = {"ml": 0, "spread": 1, "total": 2}      # the tape row's `lim` is [moneyline, spread, total] max stakes


def american_prob(o):
    if o is None or o == 0:
        return None
    return 100.0 / (o + 100.0) if o > 0 else -o / (-o + 100.0)


def limit_read(rows, market, cut):
    """Pinnacle's limit on this market group at the first tape row and at the last row at or before the cut.
    Returns {open, now, rising, falling, tested, rows, why}; rising / tested are None when no row carries a limit."""
    i = LIM_IDX[market]
    pts = sorted((r["t"], r["lim"][i]) for r in rows
                 if r.get("t") is not None and r["t"] <= cut and r.get("lim") and len(r["lim"]) > i and r["lim"][i])
    if not pts:
        return {"open": None, "now": None, "rising": None, "falling": None, "tested": None, "rows": 0, "why": "no_limit_before_cut"}
    op, now = pts[0][1], pts[-1][1]
    return {"open": op, "now": now, "rising": bool(now - op >= LIMIT_RISE_USD or now >= op * LIMIT_RISE_MULT),
            "falling": bool(now - op <= -LIMIT_RISE_USD), "tested": bool(now >= LIMIT_TESTED_USD), "rows": len(pts), "why": None}


def ev_read(rows, market, side_norm, ticket_line, cut, price):
    """The price against Pinnacle's no-vig fair price for the side at the cut. side_norm: home | away | over | under.
    Returns {fair, pts, on, why}; fair / pts / on are None when the read is not possible (the why says which)."""
    none = lambda why: {"fair": None, "pts": None, "on": None, "why": why}
    if price is None or not 0 < price < 1:
        return none("no_price")
    key = {"ml": "ml", "spread": "sp", "total": "tot"}[market]
    have = [r for r in rows if r.get("t") is not None and r["t"] <= cut and r.get(key)]
    if not have:
        return none("no_pinnacle_before_cut")
    v = max(have, key=lambda r: r["t"])[key]
    if side_norm not in ("home", "away", "over", "under"):
        return none("side_unmapped")
    away = side_norm in ("away", "under")
    if market == "ml":
        p_away, p_home = american_prob(v[0]), american_prob(v[1])
        mine, other = (p_away, p_home) if away else (p_home, p_away)
    else:
        if market == "spread":
            main = -v[0] if away else v[0]
            p_home, p_away = american_prob(v[1]), american_prob(v[2])
            mine, other = (p_away, p_home) if away else (p_home, p_away)
        else:
            main = v[0]
            p_over, p_under = american_prob(v[1]), american_prob(v[2])
            mine, other = (p_under, p_over) if away else (p_over, p_under)
        if ticket_line is None or abs(main - ticket_line) > PIN_LINE_EPS:
            return none("ticket_line_not_main_at_cut")
    if mine is None or other is None or mine + other <= 0:
        return none("no_pinnacle_price")
    fair = mine / (mine + other)
    pts = (fair - price) * 100.0
    return {"fair": round(fair, 4), "pts": round(pts, 2), "on": bool(pts >= EV_ON_PTS), "why": None}
