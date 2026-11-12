"""SharpFlow's stake policy (the press ladder and its rungs), ported from its public source so a side card can show the size SharpFlow's
rules would give. Sources: src/lib/pressLadderOverlay.js, walletTrustStatus.js, ags.js (see docs/sharpflow-teardown.md).

This is a REPLICA with known gaps, recorded on every result in `missing`:
  - steam (Pinnacle line movement toward the side): Vault does not feed it here, so steam is treated as OFF. That drops STEAM-C, STEAM-S
    and the price step of the ladder, and leaves SOLO-Q unchecked.
  - TRUST-M, PRESS-M, the odds cap, the edge-under-5 and press-edge-net clamps, GAP-LEAD, ML-DOOR and TOP3-PICK are not ported.
  - Wallet books come from Vault's own ledger (build_pm_ledger.py), not SharpFlow's wallet profiles, so the wallets and their numbers differ.
It is a shadow field: context only, never a pick, never in Top Reads, SM_GATE or an agree total (CLAUDE.md).
"""
import datetime as dt

MONEY_MIN, SEASONED_N, RATIO_MIN, BAND5, BAND4 = 0.60, 15, 1.5, 3.0, 2.0
BAND4_UNITS, DOG_IMPLIED, DOG_UNITS, HEAVY_FAV = [2, 1, 2], 0.50, 1, 0.60
X_MARGIN, X_AG_RATIO, X_UNITS = 1, 1.0, 3
N_MIN_PRESSER, N_UNITS, U_UNITS, R6_VETS, R6_RATIO, R6_UNITS = 50, 3, 2, 2, 1.0, 2
FADE_N, FADE_WR, FADE_STREAK, FADE_RATIO, FADE_IMPLIED, FADE_UNITS = 15, 45, 3, 1.5, 0.65, 2
TRUST_G_UNITS, ML_FLOOR_UNITS, ML_FLOOR_LO, ML_FLOOR_HI = 3, 4, 0.50, 0.65
ST_CAP, SPREAD_CAP = 2, 2.5
TS_UNITS, TS_PRESS, TS_DOG, TS_LO, TS_HI, TS_CONV = 2, 2.5, 1, 0.50, 0.70, 1.5
TT_MIN_FOR, TT_UNITS, TT_PRESS, TT_PRESS_IMPLIED = 2, 2.5, 3, 0.50
TIER_MIN, MIN_AGE, FORM_WIN, FORM_MIN, REGAINED_DAYS = 4, 15, 10, 5, 14
HEAVY_FAV_MUTE_IMPLIED = 425 / 525                  # american odds juicier than -425 are muted to 0u
MISSING = ["steam (STEAM-C, STEAM-S, SOLO-Q, price step)", "TRUST-M", "PRESS-M", "odds cap", "edge clamps", "GAP-LEAD", "ML-DOOR", "TOP3-PICK"]


def _day(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()


def trust_tier(edge, n):
    if n < 10 or edge is None:
        return 0
    return 5 if edge >= 8 else 4 if edge >= 4 else 3 if edge >= 0 else 2 if edge >= -4 else 1


def trust_state(bets, asof):
    """walletTrustStatus.js buildTrustState. bets: (settled_at, price, won) of decided positions; asof: the cut (seconds).
    Bookkeeping runs once per calendar day BEFORE that day's bets, so a day's state never sees that day's results."""
    bets = sorted((_day(t), p, w) for t, p, w in bets if 0 < p < 1 and t < asof)
    s = {"n": 0, "w": 0, "px": 0.0, "last": [], "peak": 0, "peak_date": None, "fell": None, "regained": 0}
    first = bets[0][0] if bets else None

    def snap(day):
        edge = 100 * (s["w"] / s["n"] - s["px"] / s["n"]) if s["n"] else 0.0
        tier = trust_tier(edge, s["n"])
        last = s["last"][-FORM_WIN:]
        form_on = (sum(1 for _, w in last if w) - sum(p for p, _ in last) >= 0) if len(last) >= FORM_MIN else True
        if tier > 0:
            if tier > s["peak"]:
                s["peak"], s["peak_date"] = tier, day
                if s["fell"]:
                    s["fell"], s["regained"] = None, s["regained"] + 1
            elif tier < s["peak"] and not s["fell"]:
                s["fell"] = day
            elif tier >= s["peak"] and s["fell"]:
                s["fell"], s["regained"] = None, s["regained"] + 1
        fallen = bool(s["fell"])
        status = ("UNPROVEN" if tier == 0 else "FALLEN_OFF" if fallen and not form_on else "FALLEN_ON" if fallen else "STABLE_OFF" if not form_on
                  else "REGAINED_ON" if s["regained"] > 0 and s["peak_date"] and (day - s["peak_date"]).days <= REGAINED_DAYS else "STABLE_ON")
        return {"status": status, "tier": tier, "n": s["n"], "edge": round(edge, 1), "age": (day - first).days if first else 0}

    i, last_day = 0, None
    while i < len(bets):
        day = bets[i][0]
        snap(day)
        while i < len(bets) and bets[i][0] == day:
            _, p, w = bets[i]
            s["n"] += 1; s["w"] += 1 if w else 0; s["px"] += p; s["last"].append((p, w))
            s["last"] = s["last"][-FORM_WIN:]
            i += 1
        last_day = day
    return snap(_day(asof))


def trusted(t):
    return bool(t) and t["tier"] >= TIER_MIN and t["status"] in ("STABLE_ON", "REGAINED_ON") and t["age"] >= MIN_AGE


def _press_band(r):
    return None if r is None or r < RATIO_MIN else 5 if r >= BAND5 else 4 if r >= BAND4 else 3


def _units(band, step, implied):
    u = BAND4_UNITS[min(step, 2)] if band == 4 else max(1, band - step)
    return min(u, DOG_UNITS) if implied is not None and implied < DOG_IMPLIED else u


def _edge(rows, market, implied):
    deep = [r for r in rows if r["dir"] == "FOR" and r["n"] >= 10 and r["wr"] is not None]
    if not deep:
        return None
    return sum(r["wr"] for r in deep) / len(deep) - (implied * 100 if market == "ml" and implied is not None else 52.4)


def floor_fade(rows, implied):
    floors = [r for r in rows if r["n"] >= FADE_N and r["wr"] is not None and r["wr"] <= FADE_WR]
    if len(floors) != 1:
        return None
    f = floors[0]
    fi = None if implied is None else (implied if f["dir"] == "FOR" else 1 - implied)
    if f["streak"] < FADE_STREAK or f["ratio"] is None or f["ratio"] >= FADE_RATIO or fi is None or fi >= FADE_IMPLIED:
        return None
    return "BOOST" if f["dir"] == "AG" else "VETO"


def evaluate(rows, market, implied, ags_score, trust_net=None):
    """One side. rows: wallets on the market, each {dir FOR|AG, invested, ratio, n, wr (percent), door2, streak, ratio, trust, trust_mkt}.
    market: 'ml' | 'spread' | 'total'. implied: the side's price as a probability. ags_score: the side's AGS v12 score (the score > 0 gate and
    TRUST-G's legacy-sizing test). Returns {rung, units, reason}."""
    fo = [r for r in rows if r["dir"] == "FOR"]
    ag = [r for r in rows if r["dir"] == "AG"]
    allusd = sum(r["invested"] for r in rows)
    money = sum(r["invested"] for r in fo) / allusd if allusd else None
    ok = lambda r: r["ratio"] is not None
    seasoned = [r for r in fo if r["n"] >= SEASONED_N and ok(r)]
    pressers = sorted((r for r in seasoned if r["ratio"] >= RATIO_MIN), key=lambda r: -r["ratio"])
    presser = pressers[0] if pressers else None
    d2_ag = [r for r in ag if r["door2"]]
    d2_for = [r for r in fo if r["door2"]]
    g_money = money is not None and money >= MONEY_MIN
    g_press, g_noag, g_for = bool(pressers), not d2_ag, bool(d2_for)
    margin = len(d2_for) - len(d2_ag)
    heavy = market == "ml" and implied is not None and implied >= HEAVY_FAV
    out = {"rung": None, "units": 0.0, "reason": "gate_fail"}
    dissent_ok = bool(d2_ag) and all(ok(r) and r["ratio"] < X_AG_RATIO for r in d2_ag)
    if g_money and g_press and g_noag and g_for:
        band = _press_band(presser["ratio"])
        step = 0 if not heavy else (1 if (_edge(rows, market, implied) or -1) >= 0 else 2)       # steam unknown: only the heavy-favourite part of the step
        out = {"rung": "PRESS", "units": float(_units(band, step, implied)), "reason": "press_%d_%s" % (band, "clean" if step == 0 else "moved")}
    elif g_money and g_press and g_for and not g_noag and margin >= X_MARGIN and dissent_ok:
        out = {"rung": "PRESS-X", "units": float(X_UNITS), "reason": "press_x_margin%d" % margin}
    elif g_money and g_press and not g_for and g_noag and presser["n"] >= N_MIN_PRESSER:
        out = {"rung": "PRESS-N", "units": float(N_UNITS), "reason": "press_n_deep%d" % presser["n"]}
    elif g_money and not g_press and g_for and not g_noag and margin >= X_MARGIN and dissent_ok:
        out = {"rung": "PRESS-U", "units": float(U_UNITS), "reason": "press_u_margin%d" % margin}
    else:
        vets = [r for r in seasoned if r["ratio"] >= R6_RATIO]
        if not g_press and len(vets) >= R6_VETS and g_noag and g_money:
            out = {"rung": "PRESS-R6", "units": float(R6_UNITS), "reason": "r6_two_veterans"}
        else:
            why = [n for n, f in (("money", g_money), ("no_seasoned_press", g_press), ("door2_against", g_noag), ("no_door2_for", g_for)) if not f]
            out["reason"] = "gate_fail:" + ",".join(why)
    ff = floor_fade(rows, implied)
    if ff == "VETO":
        out = {"rung": None, "units": 0.0, "reason": "fade_f_veto_of_%s" % (out["rung"] or "none")}
    elif ff == "BOOST" and out["units"] == 0:
        out = {"rung": "FADE-F", "units": float(FADE_UNITS), "reason": "fade_f_floor_against"}
    # TRUST layer (moneyline reads the sport-level status, spreads and totals the market-level one)
    key = "trust" if market == "ml" else "trust_mkt"
    t_for = [r for r in fo if trusted(r[key])]
    t_ag = [r for r in ag if trusted(r[key])]
    gate = any(trusted(r["trust"]) for r in fo)
    vetoed = out["reason"].startswith("fade_f_veto")
    if market == "ml":
        if out["units"] == 0 and not vetoed and out["reason"].startswith("gate_fail") and ags_score is not None and ags_score > 0 and gate:
            out = {"rung": "TRUST-G", "units": float(TRUST_G_UNITS), "reason": "trust_g"}
        if out["units"] > 0 and gate and implied is not None and ML_FLOOR_LO <= implied < ML_FLOOR_HI and out["units"] < ML_FLOOR_UNITS:
            out["units"], out["reason"] = float(ML_FLOOR_UNITS), out["reason"] + "+ml_floor4"
    elif market == "spread" and not vetoed:
        if t_ag:
            out = {"rung": None, "units": 0.0, "reason": "trust_s_veto"}
        elif t_for:
            conv = any(r["ratio"] is not None and r["ratio"] >= TS_CONV for r in t_for)
            press = conv or len(t_for) >= 2
            win = implied is not None and TS_LO <= implied < TS_HI
            dog = implied is not None and implied < TS_LO
            target = (TS_PRESS if press else TS_UNITS) if win else (TS_DOG if dog and press else 0)
            if target > 0 and out["units"] < target:
                out = {"rung": out["rung"] or "TRUST-S", "units": float(target), "reason": out["reason"] + "+trust_s" if out["units"] else "trust_s"}
    elif market == "total" and not vetoed:
        if t_for and t_ag:
            out = {"rung": None, "units": 0.0, "reason": "trust_t_veto"}
        elif len(t_for) >= TT_MIN_FOR:
            target = TT_PRESS if implied is not None and implied <= TT_PRESS_IMPLIED else TT_UNITS
            if out["units"] < target:
                out = {"rung": out["rung"] or "TRUST-T", "units": float(target), "reason": "trust_t"}
            elif out["units"] > target:
                out["units"] = float(target)
        elif len(t_for) == 1:
            out = {"rung": None, "units": 0.0, "reason": "trust_t_lone"}
    if market == "spread" and out["units"] > SPREAD_CAP:
        out["units"] = SPREAD_CAP
    if market == "total" and not (out["rung"] == "TRUST-T") and out["units"] > ST_CAP:
        out["units"] = float(ST_CAP)
    if out["units"] > 0 and implied is not None and implied >= HEAVY_FAV_MUTE_IMPLIED:
        out = {"rung": None, "units": 0.0, "reason": "heavy_favourite_mute"}
    if out["units"] > 0 and out["rung"] not in ("TRUST-G", "TRUST-S", "TRUST-T") and (ags_score is None or ags_score <= 0):
        out = {"rung": None, "units": 0.0, "reason": "score_not_positive"}
    return out
