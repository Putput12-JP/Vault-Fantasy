"""SharpFlow's stake policy (the press ladder, its rungs and the size rules that run after it), ported from its public source
(github.com/dpk1212/nhl-savant) so a side card can show the size SharpFlow's rules would give. Every constant below is SharpFlow's,
with the file it comes from. See docs/sharpflow-teardown.md and docs/side-cards.md.

Order, as scripts/syncPickStateAuthoritative.js applies it for a pick date in the ladder era (create and reconcile paths):
  1. the ladder core (PRESS, PRESS-X, PRESS-N, PRESS-U, STEAM-C, PRESS-R6, STEAM-S, SOLO-Q)           src/lib/pressLadderOverlay.js
  2. FADE-F over it, then the TRUST layer (TRUST-G, ML floor, TRUST-M, TRUST-S, TRUST-T, caps)        src/lib/pressLadderOverlay.js
  3. the v12 score gate (a TRUST stake ships through it), PRESS-M, the odds cap                       sync + pressLadderOverlay.js, oddsCap.js
  4. the -425 favourite mute                                                                          src/lib/walletClvSkill.js
  5. the press-edge / net clamp (dated out from 2026-11-05: edge-under-5 owns every sport after that) pressLadderOverlay.js
  6. ML-DOOR  (NOT PORTED, see MISSING)                                                               src/lib/mlDoorSteamPolicy.js
  7. TOP3-PICK, 8. GAP-LEAD                                                                           src/lib/top3PickRung.js, gapLeadRescue.js
  9. edge under 5 (blended edge x steam from 2026-11-06)                                              src/lib/edgeUnder5.js
  10. T5-LEAD seats with the no-T5 spread / total juice gate, then the odds cap                       src/lib/t5LeadPolicy.js
  11. the press-edge under-5 cap                                                                      src/lib/pressUnder5Cap.js

Steam (Pinnacle shortening toward the side) is measured by `steam_read` from Vault's book tape (data/book_tape), only from rows at or
before the cut, the way src/lib/steamMove.js summarizeSteam does at the T-15 freeze. The ladder's steamOn is
src/lib/unitTierEvSteamOverlay.js isSteamOn: the display tier at the cut is 'steam' or 'gold', OR the ticket's tape-log lock row
(the t15 row, first cycle within 0.40 h of the start) was juice steam (policySteamOn); see `ladder_steam`. T5-LEAD's no-T5 gate reads
juice steam only (a line walk does not count). Approximations, because the tape is coarser than
SharpFlow's Pinnacle history:
  - "since open" is since the first tape row of the game, not Pinnacle's opener (the tape starts when Vault first recorded the game).
  - "last hour" is the last tape row at or before cut - 1 hour against the last row at or before the cut. The tape appends a row only
    when a number changes and is read about every 20 minutes, so a move inside one 20-minute gap is seen at the next read.
  - spreads and totals: the tape keeps only Pinnacle's main line. Juice on the ticket line is measured only from rows where the main
    equals the ticket line, and only when it is still the main at the cut; otherwise the juice part is unknown. The main-line walk
    (0.5 point toward the side) is measured from the main lines and sets steam on by itself (SharpFlow paints it as tier 'steam').
  - pinnapi steam-drop events (a 3%+ drop SharpFlow's drops feed saw, even one that later reverted) are not in Vault's data.
  - the lock row is read at min(cut, start - 0.40 h) from the tape (SharpFlow's sync cycle times are not known).
  - when steam cannot be read (no tape for the game, a side Vault cannot map to home/away, an off-main ticket line) it is None:
    STEAM-C and STEAM-S never fire; SOLO-Q, the price step and PRESS-X read it as off (SharpFlow passes steamOn false when it has no
    tape); edge-under-5 and the no-T5 spread / total gate keep the stake and say so in `chain`; the card lists `steam unknown`.
Other approximations, all recorded on the card:
  - wallet books come from Vault's own ledger (build_pm_ledger.py), not SharpFlow's wallet profiles, so the wallets, ranks and numbers
    differ. Prices are the Polymarket price at the cut (SharpFlow uses the wallets' average entry price on the ticket line).
  - TRUST-G's "legacy V12 sizing would have staked it" is read as the side's AGS v12 score > 0 (Vault has no legacy chain).
  - TOP3-PICK's price test reads Pinnacle's price for the side at the cut (main line only on spreads / totals, None off the main).
    Without it SharpFlow reads the wallet's entry price; Vault's keyframes keep none, so the side's Polymarket price at the cut stands
    in, and `price_src` records which price was read.
  - trust states and the season tier-5 read date a bet by its game date (the event slug), as SharpFlow does; a bet with no dated slug
    falls back to its settlement day. The season start is computed over Vault's ledger, not SharpFlow's.
  - opponent units for TOP3-PICK and GAP-LEAD: a side processed earlier in the market (away before home, over before under) passes its
    final units, a later side its units before these two rungs (SharpFlow reads the earlier side fresh and the later one from its
    last stored cycle).
A dated rule is live when the pick date is on or after its FROM date; a pick date of None counts as live for every rule (Vault grades
only dates after every FROM date below).
It is a shadow field: context only, never a pick, never in Top Reads, SM_GATE or an agree total (CLAUDE.md).
"""
import datetime as dt

# ---- src/lib/pressLadderOverlay.js -------------------------------------------------------------------------------------------
MONEY_MIN, SEASONED_N, RATIO_MIN, BAND5, BAND4 = 0.60, 15, 1.5, 3.0, 2.0  # PRESS_MONEY_MIN, PRESS_SEASONED_N, PRESS_RATIO_MIN, PRESS_BAND_5/4
EDGE_MIN_N, ST_IMPLIED_PCT = 10, 52.4                                     # PRESS_EDGE_MIN_N, PRESS_ST_IMPLIED_PCT
BAND4_UNITS, DOG_IMPLIED, DOG_UNITS, HEAVY_FAV = [2, 1, 2], 0.50, 1, 0.60 # PRESS_BAND_4_UNITS, PRESS_DOG_IMPLIED_MAX, PRESS_DOG_UNITS, PRESS_HEAVY_FAV_IMPLIED
X_MARGIN, X_AG_RATIO, X_UNITS, X_UNITS_STEAM = 1, 1.0, 3, 2               # PRESS_X_MIN_MARGIN, PRESS_X_AG_RATIO_MAX, PRESS_X_UNITS, PRESS_X_UNITS_STEAM_ON
N_MIN_PRESSER, N_UNITS, U_UNITS, R6_VETS, R6_RATIO, R6_UNITS = 50, 3, 2, 2, 1.0, 2  # PRESS_N_*, PRESS_U_UNITS, R6_*
STEAM_C_MAX_MARGIN, STEAM_C_UNITS = 0, 2                                  # STEAM_C_MAX_MARGIN, STEAM_C_UNITS
STEAM_S_FROM, STEAM_S_UNITS = "2026-10-07", 2                             # STEAM_S_FROM, STEAM_S_UNITS
STEAM_S_AG_LO, STEAM_S_AG_HI, STEAM_S_MONEY_LO, STEAM_S_MONEY_HI, STEAM_S_IMPLIED = 1.0, 1.5, 0.2, 0.6, 0.40  # STEAM_S_AG_RATIO_*, STEAM_S_MONEY_*, STEAM_S_IMPLIED_MIN
SOLO_Q_FROM, SOLO_Q_UNITS, SOLO_Q_LO, SOLO_Q_HI = "2026-10-07", 1, 0.50, 0.60  # SOLO_Q_FROM, SOLO_Q_UNITS, SOLO_Q_IMPLIED_MIN/MAX
SOLO_Q_DUST, SOLO_Q_ORD_LO, SOLO_Q_ORD_HI, SOLO_Q_HOT_N, SOLO_Q_HOT_WR = 0.75, 1.0, 1.5, 8, 0.70  # SOLO_Q_DUST_MAX, SOLO_Q_ORD_*, SOLO_Q_HOT_*
FADE_F_FROM = "2026-10-07"                                                # FADE_F_FROM
FADE_N, FADE_WR, FADE_STREAK, FADE_RATIO, FADE_IMPLIED, FADE_UNITS = 15, 45, 3, 1.5, 0.65, 2  # PRESS_SEASONED_N, FADE_F_*
PRESS_M_FROM, PRESS_M_UNITS = "2026-10-07", 1                             # PRESS_M_FROM, PRESS_M_UNITS
TRUST_FROM = "2026-10-09"                                                 # TRUST_FROM
TRUST_G_UNITS, ML_FLOOR_UNITS, ML_FLOOR_LO, ML_FLOOR_HI = 3, 4, 0.50, 0.65  # TRUST_G_UNITS, ML_FLOOR_*
ST_CAP, SPREAD_CAP = 2, 2.5                                               # ST_CAP_UNITS, SPREAD_CAP_UNITS
TS_UNITS, TS_PRESS, TS_DOG, TS_LO, TS_HI, TS_CONV = 2, 2.5, 1, 0.50, 0.70, 1.5  # TRUST_S_*
TT_MIN_FOR, TT_UNITS, TT_PRESS, TT_PRESS_IMPLIED = 2, 2.5, 3, 0.50        # TRUST_T_*
TM_MARGIN, TM_ML_UNITS, TM_FLOOR_UNITS, TM_CONV, TM_DOLLARS = 2, 1, 1, 1.5, 10000  # TRUST_M_MARGIN, _ML_UNITS, _FLOOR_UNITS, _CONVICTION_RATIO, _DOLLAR_MARGIN
TM_STRONG_FLOOR, TM_PLUS1_CEIL = 3, 3                                     # TRUST_M_STRONG_FLOOR_UNITS, TRUST_M_PLUS1_CEIL_UNITS (2026-10-13 v3)
PEN_FROM, PEN_HOLE_LO, PEN_HOLE_HI, PEN_BAD, PEN_MIN_UNITS = "2026-10-25", 0, 5, -8, 2  # PRESS_EDGE_NET_*
# ---- src/lib/walletTrustStatus.js --------------------------------------------------------------------------------------------
TIER_MIN, MIN_AGE, FORM_WIN, FORM_MIN, REGAINED_DAYS = 4, 15, 10, 5, 14  # TRUST_TIER_MIN, TRUST_MIN_AGE_DAYS, TRUST_FORM_*, TRUST_REGAINED_DAYS
# ---- src/lib/walletClvSkill.js (FAV_JUICE_MUTE_THR) and src/lib/oddsCap.js ---------------------------------------------------
FAV_JUICE = -425                                                          # american odds juicier than this are muted to 0u
# ---- src/lib/top3PickRung.js, src/lib/gapLeadRescue.js -----------------------------------------------------------------------
TOP3_FROM, TOP3_MIN_N, TOP3_MIN_BOARD, TOP3_SR_MAX = "2026-10-29", 5, 4, 1.5  # TOP3_PICK_FROM; buildTop3PickRanks n >= 5, board >= 4
TOP3_ODDS_LO, TOP3_ODDS_HI, TOP3_UNITS_FULL, TOP3_UNITS_LIGHT = -101, 120, 4, 2  # isTop3PickPrice (odds > -101, <= 120); 4u at >= 1x, else 2u
L30_DAYS = 30                                                             # top3PickWindowStart / gapLeadWindowStart
GAP_FROM, GAP_MIN_N, GAP_MIN_WALLETS, GAP_MARGIN = "2026-10-30", 5, 2, 40   # GAP_LEAD_FROM, _MIN_N, _MIN_WALLETS, _MARGIN
GAP_RESCUE, GAP_BOOST_UNDER, GAP_FAV_JUICE = 3, 3, -425                   # GAP_LEAD_RESCUE_UNITS, _BOOST_UNDER, _FAV_JUICE
# ---- src/lib/edgeUnder5.js ---------------------------------------------------------------------------------------------------
EU5_FROM, EU5_BLEND_FROM, EU5_MAX, EU5_GAP_LO, EU5_GAP_HI, EU5_NBA_FAV = "2026-11-05", "2026-11-06", 5, 2, 3, -100
BLEND_PULL, BLEND_SPORT_MIN_N = 10, 10                                    # BLEND_PULL; blendWalletWr sport book >= 10
# ---- src/lib/t5LeadPolicy.js (the season tier-5 read; only `oppHasT5` is used, by edge-under-5) --------------------------------
T5_SEASON_GAP, T5_MIN_N, T5_TIER, T5_MIN_AGE = 21, 10, 5, 15              # T5_SEASON_GAP_DAYS, T5_MIN_N, T5_TIER, T5_MIN_AGE_DAYS
T5_PRICE_LO, T5_PRICE_HI = 0.02, 0.98                                     # trustTuple price window
T5_FROM, T5_NO_T5_ST_FROM, T5_HOLD_BOOST, T5_HOLD_LONG, T5_RESCUE_UNITS = "2026-11-08", "2026-11-10", 6, 14, 1  # T5_LEAD_FROM, T5_NO_T5_ST_FROM, T5_HOLD_*, T5_RESCUE_UNITS
T5_SEATS = {"lead14": (3, 6), "lead6": (2, 5), "t5_young": (2, 3), "no_t5": (None, 2), "no_lead": (None, 2)}  # T5_SEAT_* (floor, ceiling)
# ---- src/lib/pressUnder5Cap.js -----------------------------------------------------------------------------------------------
PU5_FROM, PU5_MAX, PU5_UNITS, PU5_ML_UNITS = "2026-11-10", 5, 1, 2       # PRESS_UNDER5_CAP_FROM, _MAX, _UNITS, _ML_UNITS
# ---- src/lib/top3PickRung.js isTop3PickPrice (no odds: the entry price, 45c up to just under 52c) ---------------------------
TOP3_PX_LO, TOP3_PX_HI = 0.45, 0.52
# ---- src/lib/ticketTapeCapture.js T15_HOURS: the lock row is the first cycle within 0.40 h of the start --------------------
T15_LOCK_SEC = 0.40 * 3600
# ---- src/lib/steamMove.js ----------------------------------------------------------------------------------------------------
STEAM_EVENT_PCT, STEAM_GOLD_PCT, STEAM_LINE_PTS, STEAM_HOUR, LINE_EPS = 3, 4.5, 0.5, 3600, 0.001  # STEAM_EVENT/GOLD_PCT, STEAM_LINE_MOVE_PTS, STEAM_HOUR_SEC, LINE_STEAM_EPS
PIN_LINE_EPS = 0.051                                                      # pinnacleMain.js LINE_EPS (ticket-line match)

MISSING = [
    "ML-DOOR (needs the steam state at SharpFlow's first capture of the ticket, i.e. when its pick doc was created, which Vault does not observe)",
    "T5-LEAD +1u winner-align boost (needs SharpFlow's winner boards; the seats themselves are ported)",
    "FADE-F loss streak is per sport (Vault's ledger is one sport per build; SharpFlow merges every sport's recent action)",
    "SharpFlow's create gate (sync: a side with no wallets for or against, no trusted wallet and no TOP3/GAP rung is never created) is not modelled",
    "press-edge-net closers clause (needs net CLV mean prior per wallet; the clamp is dated out from 2026-11-05 anyway)",
    "steam-drop events from SharpFlow's drops feed (Vault reads moves from its own Pinnacle tape)",
]


def _live(pick_date, frm):
    return pick_date is None or pick_date >= frm


def american(p):
    """ticketInstrument.js americanFromPolyPrice."""
    if p is None or not 0 < p < 1:
        return None
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def implied_of(odds):
    """pressLadderOverlay.js impliedFromAmerican."""
    if odds is None or odds == 0:
        return None
    return -odds / (-odds + 100) if odds < 0 else 100 / (odds + 100)


def odds_cap(units, odds):
    """oddsCap.js: favourites through +120 uncapped; +121..+150 2.5u; +151..+199 1.5u; +200 1u; longer 0u."""
    if odds is None:
        return units
    if odds > 200:
        return 0.0
    if odds >= 200:
        return min(units, 1.0)
    if odds >= 151:
        return min(units, 1.5)
    if odds > 120:
        return min(units, 2.5)
    return units


def stamped(edge):
    """stampedPressEdge / stampedEdge: one decimal, the tenth the card stores."""
    return None if edge is None else round(edge, 1) + 0.0


def _day(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()


def trust_tier(edge, n):
    if n < 10 or edge is None:
        return 0
    return 5 if edge >= 8 else 4 if edge >= 4 else 3 if edge >= 0 else 2 if edge >= -4 else 1


def _walk(bets, final_day):
    """walletTrustStatus.js buildTrustState over (day, price, won) rows sorted oldest first; the state on `final_day`."""
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

    i = 0
    while i < len(bets):
        day = bets[i][0]
        snap(day)
        while i < len(bets) and bets[i][0] == day:
            _, p, w = bets[i]
            s["n"] += 1; s["w"] += 1 if w else 0; s["px"] += p; s["last"].append((p, w))
            s["last"] = s["last"][-FORM_WIN:]
            i += 1
    return snap(final_day)


def trust_state(bets, asof):
    """walletTrustStatus.js buildTrustState. bets: (settled_at, price, won) of decided positions; asof: the cut (seconds).
    Bookkeeping runs once per calendar day BEFORE that day's bets, so a day's state never sees that day's results."""
    return _walk(sorted((_day(t), p, w) for t, p, w in bets if 0 < p < 1 and t < asof), _day(asof))


def trust_state_dated(rows, asof_day):
    """buildTrustState as SharpFlow keys it: rows (game date 'YYYY-MM-DD', price, won), bets dated before `asof_day` (the pick date)."""
    return _walk(sorted((_d(d), p, w) for d, p, w in rows if 0 < p < 1 and d < asof_day), _d(asof_day))


def trusted(t):
    return bool(t) and t["tier"] >= TIER_MIN and t["status"] in ("STABLE_ON", "REGAINED_ON") and t["age"] >= MIN_AGE


# ---- season tier 5 (t5LeadPolicy.js), read only for edge-under-5's `oppHasT5` ------------------------------------------------

def _d(s):
    return dt.date.fromisoformat(s)


def season_start(dates):
    """seasonStartFromDates: the first date after the last gap of 21 days or more."""
    uniq = sorted(set(dates))
    if not uniq:
        return None
    start = uniq[0]
    for a, b in zip(uniq, uniq[1:]):
        if (_d(b) - _d(a)).days >= T5_SEASON_GAP:
            start = b
    return start


def t5_read(rows, day, start):
    """t5MorningRead: the season book (start <= date < day) is tier 5, ON, n >= 10, first season bet >= 15 days before `day`.
    rows: (date 'YYYY-MM-DD', price, won), any order."""
    season = sorted((_d(r[0]), round(r[1] * 1000), r[2]) for r in rows if r[0] < day and (not start or r[0] >= start))
    if not season:
        return False
    st = _walk([(d, p / 1000, w) for d, p, w in season], _d(day))
    return st["tier"] == T5_TIER and st["n"] >= T5_MIN_N and st["status"] in ("STABLE_ON", "REGAINED_ON") and st["age"] >= T5_MIN_AGE


def t5_hold(rows, day, start):
    """t5HoldDays: None when the wallet does not qualify on `day`, else the days it has qualified without a break, walking back one
    morning at a time and stopping at the season start."""
    if not t5_read(rows, day, start):
        return None
    cur, held = _d(day), 0
    for _ in range(400):
        prev = cur - dt.timedelta(days=1)
        if (start and prev.isoformat() < start) or not t5_read(rows, prev.isoformat(), start):
            break
        cur, held = prev, held + 1
    return held


def t5_lead(rows):
    """t5LeadForSide from per-wallet reads on the rows (row t5 = {q, held}). Vault keeps one leg per wallet, so no wallet is on both
    sides (SharpFlow's both-sides exclusion has nothing to drop). None when no row carries a read (no season ledger)."""
    if not any(r.get("t5") is not None for r in rows):
        return None
    ours = [r["t5"].get("held") for r in rows if r["dir"] == "FOR" and (r.get("t5") or {}).get("q")]
    theirs = [r["t5"].get("held") for r in rows if r["dir"] == "AG" and (r.get("t5") or {}).get("q")]
    n = lambda arr, m: sum(1 for h in arr if h is not None and h >= m)
    return {"f": len(ours), "a": len(theirs), "lead": len(ours) - len(theirs) >= 1, "hold": max(ours) if ours else None,
            "for14": n(ours, T5_HOLD_LONG), "ag14": n(theirs, T5_HOLD_LONG), "for6": n(ours, T5_HOLD_BOOST), "ag6": n(theirs, T5_HOLD_BOOST)}


def t5_seat(lead):
    """t5Seat."""
    if lead is None:
        return None
    if lead["lead"] and lead["hold"] is not None and lead["hold"] >= T5_HOLD_LONG:
        return "lead14"
    if lead["lead"] and lead["hold"] is not None and lead["hold"] >= T5_HOLD_BOOST:
        return "lead6"
    if lead["lead"] and lead["f"] > 0:
        return "t5_young"
    return "no_t5" if lead["f"] == 0 and lead["a"] == 0 else "no_lead"


def apply_t5(units, lead, market, pick_date, juice_steam, press_edge_muted=False, blocked=False, from_rescue=False):
    """applyT5Lead + applyNoT5StSteamGate. Returns (units, action, seat). The winner-align +1u boost is not ported (MISSING).
    juice_steam: policySteamOn at the cut (True / False / None); a line walk does not count."""
    if not _live(pick_date, T5_FROM):
        return units, "EXEMPT", None
    seat = t5_seat(lead)
    pre, action = units, "PASS"
    if pre > 0 and seat:
        lo, hi = T5_SEATS[seat]
        nxt = pre
        if not from_rescue and lo is not None and 0 < nxt < lo:
            nxt = float(lo)
        if hi is not None and nxt > hi:
            nxt = float(hi)
        if nxt != pre:
            units, action = round(nxt, 2), "BAND"
    elif pre <= 0 and lead is not None:
        armed = lead["lead"] and lead["hold"] is not None and lead["hold"] >= T5_HOLD_BOOST
        no_t5 = lead["f"] == 0 and lead["a"] == 0
        st_mute = _live(pick_date, T5_NO_T5_ST_FROM) and market != "ml" and juice_steam is not True
        if press_edge_muted and not blocked and (armed or (no_t5 and not st_mute)):
            units, action = float(T5_RESCUE_UNITS), "RESCUE"
    if _live(pick_date, T5_NO_T5_ST_FROM) and market != "ml" and seat == "no_t5" and juice_steam is not True and units > 0:
        if juice_steam is None:
            return units, "UNDECIDED_STEAM_UNKNOWN", seat
        return 0.0, "MUTE_NO_T5_ST_STEAM", seat
    return units, action, seat


def press_under5_cap(units, edge, market, pick_date, lead, seat):
    """applyPressUnder5Cap: a stamped press edge under 5 caps at 1u; a moneyline stays at 2u with a 14-day tier-5 on our side and none
    against, or a fresh tier 5 (seat t5_young); a spread or total under 0 goes to 0u. A missing edge is left alone."""
    if not _live(pick_date, PU5_FROM):
        return units, "EXEMPT"
    e = stamped(edge)
    if e is None:
        return units, "PASS"
    if market != "ml" and e < 0:
        return 0.0, ("ZERO" if units > 0 else "HOLD")
    if e >= PU5_MAX:
        return units, "HOLD"
    ceiling = PU5_UNITS
    if market == "ml" and ((lead is not None and lead["for14"] >= 1 and lead["a"] == 0) or seat == "t5_young"):
        ceiling = PU5_ML_UNITS
    return (float(ceiling), "CAP") if units > ceiling else (units, "HOLD")


# ---- the ladder ----------------------------------------------------------------------------------------------------------------

def _press_band(r):
    return None if r is None or r < RATIO_MIN else 5 if r >= BAND5 else 4 if r >= BAND4 else 3


def _units(band, step, implied):
    u = BAND4_UNITS[min(step, 2)] if band == 4 else max(1, band - step)
    return min(u, DOG_UNITS) if implied is not None and implied < DOG_IMPLIED else u


def press_edge(rows, market, implied):
    """pressEdge: mean win rate of FOR wallets with n >= 10, minus the price. A moneyline reads the sport book, a spread or total that
    market's book. The implied percent is the ticket price on a moneyline, 52.4 on spreads and totals (and on a moneyline with no price)."""
    mk = market in ("spread", "total")
    deep = [r for r in rows if r["dir"] == "FOR" and (r.get("mkt_n", 0) if mk else r["n"]) >= EDGE_MIN_N
            and (r.get("mkt_wr") if mk else r["wr"]) is not None]
    if not deep:
        return None
    imp = implied * 100 if market == "ml" and implied is not None else ST_IMPLIED_PCT
    return sum((r["mkt_wr"] if mk else r["wr"]) for r in deep) / len(deep) - imp


_edge = press_edge   # the earlier name


def floor_fade(rows, implied):
    floors = [r for r in rows if r["n"] >= FADE_N and r["wr"] is not None and r["wr"] <= FADE_WR]
    if len(floors) != 1:
        return None
    f = floors[0]
    fi = None if implied is None else (implied if f["dir"] == "FOR" else 1 - implied)
    if f["streak"] < FADE_STREAK or f["ratio"] is None or f["ratio"] >= FADE_RATIO or fi is None or fi >= FADE_IMPLIED:
        return None
    return "BOOST" if f["dir"] == "AG" else "VETO"


def _hot(l10):
    """isHotL10: at least 8 decided in the sport's last 10, won at 70% or better."""
    if not l10:
        return False
    w, l = l10
    return w + l >= SOLO_Q_HOT_N and w / (w + l) >= SOLO_Q_HOT_WR


def core(rows, market, implied, steam=None, pick_date=None, dated=True):
    """evaluatePressLadderCore. steam: True / False / None (unknown). dated=False switches the dated rungs (STEAM-S, SOLO-Q) off, as
    SharpFlow's sibling read for PRESS-M does (it passes no pick date)."""
    steam_on = steam is True
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
    gate = {"money": money is not None and money >= MONEY_MIN, "press": bool(pressers), "noag": not d2_ag, "for": bool(d2_for)}
    margin = len(d2_for) - len(d2_ag)
    heavy = market == "ml" and implied is not None and implied >= HEAVY_FAV
    edge = press_edge(rows, market, implied)
    base = {"gate": gate, "money": money, "door2_for": len(d2_for), "door2_ag": len(d2_ag), "edge": edge, "steam": steam,
            "top_press": presser["ratio"] if presser else None}
    res = lambda rung, units, reason: dict(base, rung=rung, units=float(units), reason=reason)
    dissent_ok = bool(d2_ag) and all(ok(r) and r["ratio"] < X_AG_RATIO for r in d2_ag)
    if gate["money"] and gate["press"] and gate["noag"] and gate["for"]:
        band = _press_band(presser["ratio"])
        step = 0 if not steam_on and not heavy else (1 if edge is not None and edge >= 0 else 2)
        return res("PRESS", _units(band, step, implied), "press_%d_%s" % (band, "clean" if step == 0 else "moved_edge_pos" if step == 1 else "moved_edge_neg"))
    if gate["money"] and gate["press"] and gate["for"] and not gate["noag"] and margin >= X_MARGIN and dissent_ok:
        return res("PRESS-X", X_UNITS_STEAM if steam_on else X_UNITS, "press_x_margin%d_steam_%s" % (margin, "on" if steam_on else "off"))
    if gate["money"] and gate["press"] and not gate["for"] and gate["noag"] and presser["n"] >= N_MIN_PRESSER:
        return res("PRESS-N", N_UNITS, "press_n_deep%d_%s" % (presser["n"], "moved" if steam_on or heavy else "clean"))
    if gate["money"] and not gate["press"] and gate["for"] and not gate["noag"] and margin >= X_MARGIN and dissent_ok:
        return res("PRESS-U", U_UNITS, "press_u_margin%d" % margin)
    press_ag = any(r["n"] >= SEASONED_N and ok(r) and r["ratio"] >= RATIO_MIN for r in ag)
    if steam_on and not gate["noag"] and margin <= STEAM_C_MAX_MARGIN and dissent_ok and not press_ag:
        return res("STEAM-C", STEAM_C_UNITS, "steam_c_margin%d" % margin)
    vets = [r for r in seasoned if r["ratio"] >= R6_RATIO]
    if not gate["press"] and len(vets) >= R6_VETS and gate["noag"] and gate["money"]:
        return res("PRESS-R6", R6_UNITS, "r6_two_veterans")
    seas_for = sum(1 for r in fo if r["n"] >= SEASONED_N)
    seas_ag = sum(1 for r in ag if r["n"] >= SEASONED_N)
    ag_max = max((r["ratio"] or 0) for r in ag) if ag else None
    if (dated and _live(pick_date, STEAM_S_FROM) and steam_on and not gate["press"] and not press_ag and ag
            and STEAM_S_AG_LO <= ag_max < STEAM_S_AG_HI and seas_ag >= 1 and seas_for <= seas_ag
            and money is not None and STEAM_S_MONEY_LO <= money < STEAM_S_MONEY_HI and implied is not None and implied >= STEAM_S_IMPLIED):
        return res("STEAM-S", STEAM_S_UNITS, "steam_s_seas%dv%d_ag%.2fx" % (seas_for, seas_ag, ag_max))
    for_max = max((r["ratio"] or 0) for r in fo) if fo else None
    dust = for_max is not None and for_max < SOLO_Q_DUST
    ordinary = for_max is not None and SOLO_Q_ORD_LO <= for_max < SOLO_Q_ORD_HI and any(_hot(r.get("l10")) for r in fo)
    if (dated and _live(pick_date, SOLO_Q_FROM) and not steam_on and not ag and fo and implied is not None
            and SOLO_Q_LO <= implied < SOLO_Q_HI and (dust or ordinary)):
        return res("SOLO-Q", SOLO_Q_UNITS, "solo_q_%s" % ("dust" if dust else "ordinary_hot"))
    why = [n for n, f in (("money", gate["money"]), ("no_seasoned_press", gate["press"]), ("door2_against", gate["noag"]),
                          ("no_door2_for", gate["for"])) if not f]
    return res(None, 0, "gate_fail:" + ",".join(why))


def margin_read(rows):
    """trustMarginRead on the market book. Vault keeps one leg per wallet per market group (hedges collapse before this), so no wallet is
    on both lists and netHedgedTrusted has nothing to net."""
    t_for = [r for r in rows if r["dir"] == "FOR" and trusted(r.get("trust_mkt"))]
    t_ag = [r for r in rows if r["dir"] == "AG" and trusted(r.get("trust_mkt"))]
    margin = len(t_for) - len(t_ag)
    dollars = sum(r["invested"] for r in t_for) - sum(r["invested"] for r in t_ag)
    conv = any(r["ratio"] is not None and r["ratio"] >= TM_CONV for r in t_for)
    strong = margin >= TM_MARGIN
    plus1 = margin == 1 and (conv or dollars >= TM_DOLLARS)
    return {"for": t_for, "ag": t_ag, "margin": margin, "dollars": dollars, "conv": conv, "strong": strong, "plus1": plus1,
            "through": strong or plus1}


def trust_layer(out, rows, market, implied, legacy, pick_date=None):
    """applyTrustLayer: TRUST-G, the ML floor, TRUST-M (ML rescue, the door through vetoes, floors and the +1 ceiling), TRUST-S,
    TRUST-T and the spread / totals caps. Moneyline gates read the sport-level status, the margin and spreads / totals the market one."""
    out = dict(out, rules=[])
    if not _live(pick_date, TRUST_FROM):
        return out
    rules = out["rules"]
    fo = [r for r in rows if r["dir"] == "FOR"]
    gate = any(trusted(r.get("trust")) for r in fo)
    m = margin_read(rows)
    out["trust_margin"] = m["margin"]
    fade_vetoed = out["reason"].startswith("fade_f_veto")
    vetoed = fade_vetoed and not m["through"]
    if fade_vetoed and m["through"]:
        out["reason"] += "+trust_m_over_fade_f_m%d" % m["margin"]
        rules.append("trust_m")
    ml, sp, tot = market == "ml", market == "spread", market == "total"
    if ml and out["units"] == 0 and not vetoed and out["reason"].startswith("gate_fail") and legacy and gate:
        out.update(rung="TRUST-G", units=float(TRUST_G_UNITS), reason="trust_g:" + out["reason"])
        rules.append("trust_g")
    if ml and out["units"] > 0 and gate and implied is not None and ML_FLOOR_LO <= implied < ML_FLOOR_HI and out["units"] < ML_FLOOR_UNITS:
        out["units"], out["reason"] = float(ML_FLOOR_UNITS), out["reason"] + "+ml_floor4"
        rules.append("ml_floor")
    if ml and out["units"] == 0 and m["through"]:
        out.update(rung="TRUST-G", units=float(TM_ML_UNITS), reason="trust_m_ml_m%d:" % m["margin"] + out["reason"])
        if "trust_m" not in rules:
            rules.append("trust_m")
    trust_t = False
    if sp and not vetoed:
        if m["ag"] and m["through"]:
            out["reason"] += "+trust_m_over_ag_m%d" % m["margin"]
            if "trust_m" not in rules:
                rules.append("trust_m")
        if m["ag"] and not m["through"]:
            if out["units"] > 0:
                out.update(units=0.0, rung=None)
            out["reason"] = "trust_s_veto:" + out["reason"]
            rules.append("trust_s_veto")
        elif m["for"]:
            conv = any(r["ratio"] is not None and r["ratio"] >= TS_CONV for r in m["for"])
            press = conv or len(m["for"]) >= 2
            win = implied is not None and TS_LO <= implied < TS_HI
            dog = implied is not None and implied < TS_LO
            target = (TS_PRESS if press else TS_UNITS) if win else (TS_DOG if dog and press else 0)
            floored = False
            if target == 0 and m["through"]:
                target, floored = TM_FLOOR_UNITS, True
            if target > 0 and out["units"] < target:
                tag = ("trust_m_floor_%su" if floored else "trust_s_%su") % target
                if out["units"] > 0:
                    out["reason"] += "+" + tag
                else:
                    out.update(rung="TRUST-S", reason=tag + ":" + out["reason"])
                out["units"] = float(target)
                if not floored:
                    rules.append("trust_s")
                elif "trust_m" not in rules:
                    rules.append("trust_m")
    if tot and not vetoed:
        if m["ag"] and m["through"]:
            out["reason"] += "+trust_m_over_ag_m%d" % m["margin"]
            if "trust_m" not in rules:
                rules.append("trust_m")
        if m["for"] and m["ag"] and not m["through"]:
            if out["units"] > 0:
                out.update(units=0.0, rung=None)
            out["reason"] = "trust_t_veto:" + out["reason"]
            rules.append("trust_t_veto")
        elif len(m["for"]) >= TT_MIN_FOR:
            target = TT_PRESS if implied is not None and implied <= TT_PRESS_IMPLIED else TT_UNITS
            if out["units"] < target:
                if out["units"] > 0:
                    out["reason"] += "+trust_t_%su" % target
                else:
                    out.update(rung="TRUST-T", reason="trust_t_%su:" % target + out["reason"])
                out["units"] = float(target)
                rules.append("trust_t")
            elif out["units"] > target:
                out["units"], out["reason"] = float(target), out["reason"] + "+tt_cap"
                rules.append("tt_cap")
            trust_t = True
        elif m["for"] and m["through"]:
            if out["units"] < TM_FLOOR_UNITS:
                if out["units"] > 0:
                    out["reason"] += "+trust_m_floor_1u"
                else:
                    out.update(rung="TRUST-T", reason="trust_m_floor_1u:" + out["reason"])
                out["units"] = float(TM_FLOOR_UNITS)
            else:
                out["reason"] += "+trust_m_lone"
            if "trust_m" not in rules:
                rules.append("trust_m")
            trust_t = True
        elif m["for"]:
            if out["units"] > 0:
                out.update(units=0.0, rung=None)
            out["reason"] = "trust_t_lone:" + out["reason"]
            rules.append("trust_t_lone")
    if m["margin"] == 1 and out["units"] > TM_PLUS1_CEIL:
        out["units"], out["reason"] = float(TM_PLUS1_CEIL), out["reason"] + "+trust_m_ceil3_m1"
        rules.append("trust_m_ceil")
    if sp and out["units"] > SPREAD_CAP:
        out["units"], out["reason"] = SPREAD_CAP, out["reason"] + "+sp_cap"
        rules.append("sp_cap")
    if not ml and not sp and not trust_t and out["units"] > ST_CAP:
        out["units"], out["reason"] = float(ST_CAP), out["reason"] + "+st_cap"
        rules.append("st_cap")
    if m["strong"] and 0 < out["units"] < TM_STRONG_FLOOR:
        out["units"], out["reason"] = float(TM_STRONG_FLOOR), out["reason"] + "+trust_m_floor3"
        rules.append("trust_m_floor")
    return out


def ladder(rows, market, implied, steam=None, pick_date=None, legacy=None, ags_score=None):
    """evaluatePressLadder: the core, FADE-F over it, then the trust layer. `legacy` is TRUST-G's legacy-stake test (default: the
    AGS v12 score > 0)."""
    out = core(rows, market, implied, steam, pick_date)
    ff = floor_fade(rows, implied) if _live(pick_date, FADE_F_FROM) else None
    if ff == "VETO":
        out = dict(out, rung=None, units=0.0, reason="fade_f_veto_of_%s" % (out["rung"] if out["units"] > 0 else "none"))
    elif ff == "BOOST" and out["units"] == 0:
        out = dict(out, rung="FADE-F", units=float(FADE_UNITS), reason="fade_f_floor_against")
    if legacy is None:
        legacy = ags_score is not None and ags_score > 0
    return trust_layer(out, rows, market, implied, legacy, pick_date)


def trust_bypass(e):
    """isTrustAgsBypass: a TRUST stake ships through a v12 score that is not > 0."""
    if not e or not e["units"] > 0:
        return False
    if (e["rung"] or "").startswith("TRUST"):
        return True
    return bool({"trust_m", "trust_t", "trust_s", "trust_g", "trust_m_floor", "trust_m_ceil"} & set(e.get("rules") or ()))


def evaluate(rows, market, implied, ags_score, trust_net=None, steam=None, pick_date=None, legacy=None):
    """One side through the ladder, the score gate, the odds cap and the -425 favourite mute (no market-level rules).
    rows: wallets on the market, each {dir FOR|AG, invested, ratio, n, wr (percent), door2, streak, trust, trust_mkt} and optionally
    {w, wins, mkt_n, mkt_wins, mkt_wr, l10, gap, rank, t5}. market: 'ml' | 'spread' | 'total'. implied: the side's price as a
    probability. ags_score: the side's AGS v12 score. Returns {rung, units, reason, ...}."""
    e = ladder(rows, market, implied, steam, pick_date, legacy, ags_score)
    return _stage_a(e, ags_score, american(implied), mirror=False)


def _stage_a(e, ags_score, odds, mirror):
    score_ok = (ags_score is not None and ags_score > 0) or trust_bypass(e)
    out = dict(e)
    if score_ok and e["units"] > 0:
        units = e["units"]
    elif mirror:
        out.update(rung="PRESS-M", reason="press_m_mirror")
        units = float(PRESS_M_UNITS)
    else:
        units = 0.0
        if e["units"] > 0:
            out.update(rung=None, reason="score_not_positive")
    if units > 0 and odds is not None:
        capped = round(odds_cap(units, odds), 2)
        if capped < units:
            out["reason"] += "+odds_cap"
        units = capped
        if units == 0:
            out["rung"] = None
    if units > 0 and odds is not None and odds < FAV_JUICE:
        out.update(rung=None, reason="heavy_favourite_mute")
        units = 0.0
    out["units"] = float(units)
    return out


# ---- market-level rules --------------------------------------------------------------------------------------------------------

def _mirror_shape(c):
    g = c["gate"]
    return g["money"] and g["press"] and g["noag"]


def top3(rows, pinn_odds, opp_units, pick_date, poly_px=None):
    """evaluateTop3Pick: a top-3 wallet (30-day dollar ROI rank in this sport and market) on this side under 1.5x its usual, at a pick'em
    price, and no top-3 wallet against. 4u from a 1x bet, else 2u. isTop3PickPrice: Pinnacle odds -100 through +120; without odds, the
    wallet's entry price 45c up to just under 52c. Vault's keyframes keep no entry price (a row's `entry_px` is used when present),
    so the side's Polymarket price at the cut stands in; `price_src` records which price was read."""
    if not _live(pick_date, TOP3_FROM):
        return {"fires": False, "reason": "not_live"}
    if opp_units > 0:
        return {"fires": False, "reason": "pick_against"}
    if any(r["dir"] == "AG" and (r.get("rank") or 99) <= 3 for r in rows):
        return {"fires": False, "reason": "top3_against"}
    srcs = set()

    def price_ok(r):
        if pinn_odds is not None and pinn_odds != 0:
            srcs.add("pinnacle")
            return TOP3_ODDS_LO < pinn_odds <= TOP3_ODDS_HI
        px, src = (r["entry_px"], "entry") if r.get("entry_px") is not None else (poly_px, "polymarket_at_cut")
        if px is None or not 0 < px < 1:
            return False
        srcs.add(src)
        return TOP3_PX_LO <= px < TOP3_PX_HI
    q = [r for r in rows if r["dir"] == "FOR" and (r.get("rank") or 99) <= 3 and r["ratio"] is not None and r["ratio"] < TOP3_SR_MAX and price_ok(r)]
    if not q:
        return {"fires": False, "reason": "no_qualifying_wallet", "price_src": sorted(srcs)}
    best = max(r["ratio"] for r in q)
    return {"fires": True, "units": TOP3_UNITS_FULL if best >= 1 else TOP3_UNITS_LIGHT, "best_sr": round(best, 2),
            "wallets": [r.get("w") for r in q], "reason": "top3_pick", "price_src": sorted(srcs)}


def gap_lead(rows, pick_date):
    """evaluateGapLead: two or more wallets with a 30-day market book (5+ bets) on this side, the other side scored, our stake-weighted
    30-day dollar ROI 40 points over theirs and theirs negative."""
    if not _live(pick_date, GAP_FROM):
        return {"fires": False, "reason": "not_live"}

    def side(d):
        ws = [r for r in rows if r["dir"] == d and r.get("gap") and r["invested"] > 0]
        inv = sum(r["invested"] for r in ws)
        return ws, (sum(r["gap"]["dol"] * r["invested"] for r in ws) / inv if inv > 0 else None)
    ours, l_ours = side("FOR")
    _, l_opp = side("AG")
    if len(ours) < GAP_MIN_WALLETS:
        return {"fires": False, "reason": "need_two_wallets", "ours": l_ours, "other": l_opp}
    if l_opp is None:
        return {"fires": False, "reason": "other_side_unscored", "ours": l_ours, "other": None}
    if not (l_ours - l_opp >= GAP_MARGIN and l_opp < 0):
        return {"fires": False, "reason": "gap_short", "ours": round(l_ours, 1), "other": round(l_opp, 1)}
    return {"fires": True, "reason": "gap_lead", "ours": round(l_ours, 1), "other": round(l_opp, 1), "margin": round(l_ours - l_opp, 1)}


def blend_edge(rows, market, odds):
    """edgeUnder5.js blendEdgeForSide: each FOR wallet's market win rate pulled toward its other markets in the sport (k = 10), sport
    book of 10+, averaged, minus the price (52.4 on spreads and totals), to a tenth."""
    wrs = []
    for r in rows:
        if r["dir"] != "FOR" or not r["invested"] > 0:
            continue
        n_s = r["s_n"] if r.get("s_n") is not None else (r.get("n") or 0)          # sport book from the same bets list as the market one
        w_s = r["s_wins"] if r.get("s_wins") is not None else (r.get("wins") or 0)
        n_m, w_m = r.get("mkt_n") or 0, r.get("mkt_wins") or 0
        if not n_s or n_s < BLEND_SPORT_MIN_N:
            continue
        wr_s = round(100 * w_s / n_s, 1)
        if n_m < 1 or n_s <= n_m:
            wrs.append(wr_s)
            continue
        wr_m, wr_o = round(100 * w_m / n_m, 1), round(100 * (w_s - w_m) / (n_s - n_m), 1)
        wrs.append((n_m * wr_m + BLEND_PULL * wr_o) / (n_m + BLEND_PULL))
    if not wrs:
        return None
    imp = ST_IMPLIED_PCT if market != "ml" else (implied_of(odds) * 100 if odds is not None else None)
    return None if imp is None else round(sum(wrs) / len(wrs) - imp, 1)


def stake_market(sides, market, pick_date=None, order=None, sport=None):
    """The whole chain for one market group. sides: {name: {rows, implied, ags, steam, pinn_odds}} where `rows` are that side's wallet
    rows (FOR = on this side). order: the side order SharpFlow walks (away, home / over, under); default sorted names.
    Returns {name: result} with `units` the size the chain gives each side and `chain`, the steps that moved it."""
    names = list(order or sorted(sides))
    odds = {s: american(sides[s]["implied"]) for s in names}
    score = {s: sides[s].get("ags") for s in names}
    pos = lambda s: score[s] is not None and score[s] > 0
    shape = {}
    sib_units = {}
    for s in names:                          # PRESS-M's read: gate flags, and the core units at steam off with no dated rungs
        c = core(sides[s]["rows"], market, sides[s]["implied"], False, pick_date, dated=False)
        shape[s], sib_units[s] = _mirror_shape(c), (c["units"] if pos(s) else 0.0)
    res = {}
    for s in names:
        legacy = pos(s)
        if (market == "ml" and legacy and _live(pick_date, PRESS_M_FROM)
                and any(shape[o] and not pos(o) for o in names if o != s)):
            legacy = False                   # TRUST-G yields the market to a PRESS-M sibling
        e = ladder(sides[s]["rows"], market, sides[s]["implied"], sides[s].get("steam"), pick_date, legacy)
        r = _stage_a(e, score[s], odds[s], mirror=False)
        r["chain"] = []
        res[s] = r
    for s in names:                          # PRESS-M: the shape here, no V12 score here, a V12 sibling, nobody staked
        if res[s]["units"] > 0 or pos(s) or not shape[s] or not _live(pick_date, PRESS_M_FROM):
            continue
        sibs = [o for o in names if o != s]
        if not any(pos(o) for o in sibs) or any(sib_units[o] > 0 or res[o]["units"] > 0 for o in sibs):
            continue
        e = ladder(sides[s]["rows"], market, sides[s]["implied"], sides[s].get("steam"), pick_date, False)
        res[s] = dict(_stage_a(e, score[s], odds[s], mirror=True), chain=["press_m"])
    for s in names:                          # press-edge / net clamp, dated out from 2026-11-05 (edge-under-5 owns every sport)
        r = res[s]
        if (_live(pick_date, PEN_FROM) and not _live(pick_date, EU5_FROM) and r["units"] >= PEN_MIN_UNITS
                and r.get("edge") is not None and PEN_HOLE_LO <= stamped(r["edge"]) < PEN_HOLE_HI):
            r.update(units=0.0, rung=None, reason="press_edge_0_5:" + r["reason"])
            r["chain"].append("press_edge_net")
    pre = {s: res[s]["units"] for s in names}
    done = set()
    for s in names:                          # TOP3-PICK, then GAP-LEAD, side by side in SharpFlow's order
        r, rows = res[s], sides[s]["rows"]
        opp = [o for o in names if o != s]
        opp_units = max([res[o]["units"] if o in done else pre[o] for o in opp] or [0])
        t3 = top3(rows, sides[s].get("pinn_odds"), opp_units, pick_date, sides[s]["implied"])
        r["top3"] = t3
        if t3["fires"] and r["units"] + 0.001 < t3["units"]:
            r["chain"].append("top3_%s" % ("floor" if r["units"] > 0 else "rescue"))
            r.update(units=float(t3["units"]), rung="TOP3-PICK", reason="top3_pick:" + r["reason"])
        g = gap_lead(rows, pick_date)
        if g["fires"] and opp_units > 0:               # applyGapLeadRescue: a stake on the other side mutes the rung
            g = dict(g, fires=False, reason="pick_against")
        r["gap"] = g
        if g["fires"] and not (odds[s] is not None and odds[s] < GAP_FAV_JUICE):
            band = _live(pick_date, EU5_FROM) and EU5_GAP_LO <= r["units"] < EU5_GAP_HI and (stamped(r.get("edge")) or 0) < EU5_MAX
            if not band and r["units"] + 0.001 < GAP_BOOST_UNDER:
                raw = GAP_RESCUE if r["units"] <= 0 else r["units"] + 1
                capped = round(odds_cap(raw, odds[s]), 2)
                if capped > r["units"] + 0.001:
                    r["chain"].append("gap_%s" % ("boost" if r["units"] > 0 else "rescue"))
                    r.update(units=float(capped), rung="GAP-LEAD", reason="gap_lead:" + r["reason"])
        done.add(s)
    for s in names:                          # edge under 5
        r, rows = res[s], sides[s]["rows"]
        opp_t5 = any(r2["dir"] == "AG" and (r2.get("t5") or {}).get("q") for r2 in rows)
        r["opp_t5"] = opp_t5
        r["blend"] = blend_edge(rows, market, odds[s])
        if not opp_t5 or not _live(pick_date, EU5_FROM) or not r["units"] > 0:
            continue
        if _live(pick_date, EU5_BLEND_FROM):
            b, st = r["blend"], sides[s].get("steam")
            if b is None or b >= EU5_MAX or st is True:
                continue
            if st is None:
                r["chain"].append("edge_under_5_undecided_steam_unknown")
                continue
            r.update(units=0.0, rung=None, reason="edge_under_5_steam_off:" + r["reason"])
            r["chain"].append("edge_under_5")
        else:
            if (stamped(r.get("edge")) or 0) >= EU5_MAX:
                continue
            if r.get("gap", {}).get("fires") and EU5_GAP_LO <= r["units"] < EU5_GAP_HI:
                continue
            if sport == "nba" and market == "ml" and odds[s] is not None and odds[s] < EU5_NBA_FAV:
                continue
            r.update(units=0.0, rung=None, reason="edge_under_5:" + r["reason"])
            r["chain"].append("edge_under_5")
    for s in names:                          # T5-LEAD seats (+ the no-T5 spread / total juice gate), the odds cap, the press-edge under-5 cap
        r, rows = res[s], sides[s]["rows"]
        lead = t5_lead(rows)
        rescued = any(c in ("top3_rescue", "gap_rescue") for c in r["chain"])
        blocked = r["reason"].startswith("heavy_favourite_mute") or "edge_under_5" in r["chain"]
        units, action, seat = apply_t5(r["units"], lead, market, pick_date, sides[s].get("juice"), False, blocked, rescued)
        r.update(t5_lead=lead, t5_seat=seat, t5_action=action)
        if units != r["units"]:
            r["chain"].append("t5_" + action.lower())
            if units == 0:
                r.update(rung=None, reason="no_t5_st_steam:" + r["reason"])
            if units > 0 and odds[s] is not None:
                units = round(odds_cap(units, odds[s]), 2)
            r["units"] = float(units)
        elif action == "UNDECIDED_STEAM_UNKNOWN":
            r["chain"].append("t5_no_t5_st_undecided_steam_unknown")
        units, action = press_under5_cap(r["units"], r.get("edge"), market, pick_date, lead, seat)
        r["under5_action"] = action
        if units != r["units"]:
            r["chain"].append("press_under5_" + action.lower())
            if units == 0:
                r.update(rung=None, reason="press_under5_zero:" + r["reason"])
            r["units"] = float(units)
    return res


# ---- Pinnacle steam from Vault's tape ------------------------------------------------------------------------------------------

def _dec(a):
    if a is None or a == 0:
        return None
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


def drop_pct(frm, to):
    """steamMove.js decimalDropPct: positive when this side's price shortened."""
    f, t = _dec(frm), _dec(to)
    if f is None or t is None or f <= 1:
        return None
    return round((f - t) / f * 100, 2)


def steam_read(tape, market, side_norm, ticket_line, cut):
    """summarizeSteam at the cut from Vault's Pinnacle tape. tape: rows {t, ml: [away, home], sp: [home line, home price, away price],
    tot: [line, over, under]}. side_norm: home | away | over | under. ticket_line: this side's own line (spread) or the total.
    Returns {on: True | False | None, tier, last_hour_pct, since_open_pct, line_*, rows, ...}. Only rows with t <= cut are read."""
    rows = sorted((r for r in tape if r.get("t") is not None and r["t"] <= cut), key=lambda r: r["t"])
    out = {"on": None, "tier": None, "last_hour_pct": None, "since_open_pct": None, "rows": 0, "why": None}
    if not rows:
        return dict(out, why="no_tape_before_cut")
    hour_ago = cut - STEAM_HOUR
    away = side_norm in ("away", "under")
    if market == "ml":
        hist = [(r["t"], r["ml"][0 if away else 1]) for r in rows if r.get("ml")]
        juice_known = bool(hist)
        mains = []
    else:
        key = "sp" if market == "spread" else "tot"
        mains = [(r["t"], r[key]) for r in rows if r.get(key)]
        if market == "spread":
            line_of = lambda v: -v[0] if away else v[0]
            price_of = lambda v: v[2] if away else v[1]
        else:
            line_of = lambda v: v[0]
            price_of = lambda v: v[2] if away else v[1]
        hist = [(t, price_of(v)) for t, v in mains if ticket_line is not None and abs(line_of(v) - ticket_line) <= PIN_LINE_EPS]
        juice_known = bool(mains) and ticket_line is not None and abs(line_of(mains[-1][1]) - ticket_line) <= PIN_LINE_EPS
    out["rows"] = len(hist) if market == "ml" else len(mains)
    lh = so = None
    if juice_known and hist:
        open_o, now_o = hist[0][1], hist[-1][1]
        before = [o for t, o in hist if t <= hour_ago]
        hour_o = before[-1] if before else open_o
        lh, so = drop_pct(hour_o, now_o), drop_pct(open_o, now_o)
        out.update(open=[hist[0][0], open_o], now=[hist[-1][0], now_o], hour=[next((t for t, o in reversed(hist) if t <= hour_ago), hist[0][0]), hour_o],
                   short_session=not before)
    out.update(last_hour_pct=lh, since_open_pct=so)
    tier = None
    if lh is not None and lh >= STEAM_GOLD_PCT:
        tier = "gold"
    elif (lh is not None and lh >= STEAM_EVENT_PCT) or (so is not None and so >= STEAM_EVENT_PCT):
        tier = "steam"
    # juice steam (steamMove.js policySteamOn / juiceSteam): a 3%+ shorten on the ticket line; a line walk does not count. Vault reads
    # juice only while the ticket line is the main, so pinStillMain / nearFavorableMain hold whenever it is known.
    out["juice"] = tier in ("steam", "gold") if juice_known and hist else None
    walk = False
    if mains:                                # main-line walk toward the ticket (mainLineTowardTicket); paints tier 'steam'
        sign = 1
        if market == "spread":
            first, last = mains[0][1][0], mains[-1][1][0]
            hb = [v[0] for t, v in mains if t <= hour_ago]
            hour = hb[-1] if hb else first
            to_home = lambda a, b: a - b                  # home line getting more negative is toward home
            sign = -1 if away else 1
            so_pts, lh_pts = sign * to_home(first, last), sign * to_home(hour, last)
        else:
            first, last = mains[0][1][0], mains[-1][1][0]
            hb = [v[0] for t, v in mains if t <= hour_ago]
            hour = hb[-1] if hb else first
            sign = -1 if away else 1
            so_pts, lh_pts = sign * (last - first), sign * (last - hour)
        so_pts, lh_pts = round(so_pts, 3), round(lh_pts, 3)
        walk = so_pts >= STEAM_LINE_PTS - LINE_EPS or lh_pts >= STEAM_LINE_PTS - LINE_EPS
        out.update(line_open=first, line_hour=hour, line_now=last, since_open_pts=so_pts, last_hour_pts=lh_pts, walk=walk)
        if walk and tier is None:
            tier = "steam"
    out["tier"] = tier
    if tier in ("steam", "gold"):
        out["on"] = True
    elif juice_known:
        out["on"] = False
    else:
        out["why"] = "no_moneyline_rows" if market == "ml" else "ticket_line_not_main_at_cut"
    return out


def ladder_steam(tape, market, side_norm, ticket_line, cut, gst):
    """The ladder's steamOn (unitTierEvSteamOverlay.js isSteamOn): the display tier at the cut is steam / gold (a 0.5-point walk counts),
    OR tapeSteamOnLock, policySteamOn on the lock row of the ticket's tape log (ticketTapeCapture.js analyzeTicketTapeLog: the t15 row,
    taken on the first cycle within 0.40 h of the start, else the last row), read from tape rows at or before min(cut, start - 0.40 h).
    True when either is on; False only when both are known off; otherwise None. `juice` is policySteamOn at the cut (T5's gate)."""
    now = steam_read(tape, market, side_norm, ticket_line, cut)
    lock_t = min(cut, gst - T15_LOCK_SEC) if gst is not None else cut
    lock = steam_read(tape, market, side_norm, ticket_line, lock_t)
    on = True if now["on"] is True or lock.get("juice") is True else (False if now["on"] is False and lock.get("juice") is False else None)
    out = dict(now, on=on, cut_on=now["on"], lock_t=lock_t, lock_juice=lock.get("juice"))
    if on is None and not out.get("why"):
        out["why"] = "lock_row_juice_unknown"
    return out
