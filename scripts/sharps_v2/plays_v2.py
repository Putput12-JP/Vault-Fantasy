#!/usr/bin/env python3
"""Sharps V2 plays data (docs/sharps-v2-plays-spec.md): pure functions, stdlib only.

Everything here is additive context for the Sharps V2 page. Sharp money is context only (CLAUDE.md): nothing below is a bet signal, a
size or an input to Top Reads, SM_GATE or an agree total. The only size is the documented side-card exception (flat 1u on NBA, NFL and
CBB plays, none on CFB, always labelled "untested rule"), and the evidence tier never changes it.
The tier-scaled size shadow v2s-1 (user decision 2026-11-23, `shadow_units`) sits BESIDE that flat size as a record: it is never shown, never
read by the page, the ladder, the gates or the locks, and its values are an ordering by evidence, not fitted to results.

Never invent a number: every value is a stored price, a stored quote, a stored count, or arithmetic on stored fields. A value that is
not stored is None or an absent key, never 0. Point in time: every read is stopped at `asof` (the cut on a frozen card), so a later
input can never change what a card says.

The builder (scripts/build_side_cards.py) calls `market_v2` for every market group of a card and `v2_slate` once per live build; the
history script (scripts/sharps_v2/tier_history.py) calls `facts` and `tier_of` on stored cards, so a frozen card and a re-derivation
can never disagree on a rule.
"""
import copy, datetime as dt, json, os, sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sf_signals as SIG  # noqa: E402
from sharps_v2 import flags_v2 as F  # noqa: E402

RULE = "v2t-1"                                  # the tier rule version: a rule change is a new string and a new registration
SHOWN_SPORTS = ("nba", "nfl", "cbb")             # the documented side-card exception: flat 1u here, nothing on CFB
PRICE_TIER_SPORTS = ("nba", "nfl")               # the CLV tiers (a2, b1) and the fade-dull rule (a3) exist only here (sf_tiers.TIER_SPORTS)
FACTS_NA = ["a2", "b1", "a3"]                    # facts that do not apply on a college card (published false)
EV_PTS = SIG.EV_ON_PTS                           # 0.3, registered Nov 14 (scripts/sf_signals.py); no new threshold
PIN_LINE_EPS = SIG.PIN_LINE_EPS
# the market-move flags (docs/sharps-v2-flags-spec.md, rule v2f-1): the frozen constants live in flags_v2.py and are re-exported here, the one
# source the docs, the prereg and the tests read. Context only: nothing in this file reads them for a tier, a size or a gate.
FLAGS_RULE, FLAGS_T_A, FLAGS_T_C, FLAGS_WINDOW, FLAGS_STALE = F.FLAGS_RULE, F.FLAGS_T_A, F.FLAGS_T_C, F.FLAGS_WINDOW, F.FLAGS_STALE
FLAGS_SERIES_N, FLAGS_US = F.FLAGS_SERIES_N, F.FLAGS_US
US_BOOKS = ("BetMGM", "BetRivers", "DraftKings", "FanDuel", "bet365")
SHOWN_RULE = "flat 1u on NBA, NFL, CBB; none on CFB; untested rule (since 2026-11-20 4:47 PM CT)"
# The tier-scaled size SHADOW (user decision 2026-11-23). It runs BESIDE the flat 1u above and never replaces it: the page, `shown_units`, the
# ladder, sf_rungs, the gates and the locks do not read it. The values are an ordering by evidence tier, NOT fitted to results. One constant, so the
# code, the docs and the tests read the same source.
SHADOW = {"rule": "v2s-1", "sizes": {"clear": 1.5, "mixed": 1, "thin": 0.5, "contested": 0.5}, "cfb": 0}
SHADOW_RULE = SHADOW["rule"]
SHADOW_SPORTS = SHOWN_SPORTS + ("cfb",)
SPLIT_SRC = "action_network_consensus"
SPLIT_KEY = {"ml": "ml", "spread": "sp", "total": "tot"}
TAPE_KEY = {"ml": "ml", "spread": "sp", "total": "tot"}
NOVIG_KEY = {"ml": "px", "spread": "nsp", "total": "ntot"}
TIERS = ("clear", "mixed", "thin", "contested")
# dated page changes of the shown size (merge times, Central): the ladder before the first, flat 1u on NBA and NFL from it, CBB again from
# the second (git log: #461 2026-11-18 08:31:01 -0600, #534 2026-11-20 16:47:34 -0600)
FLAT_FROM = 1795012261                           # 2026-11-18 8:31:01 AM CT
CBB_FROM = 1795214854                            # 2026-11-20 4:47:34 PM CT
# every key the V2 plays data adds, so a reader (and the byte-compare test) can strip them and get the file as it was
V2_MARKET_KEYS = ("v2", "splits")
V2_TOP_KEYS = ("v2_slate", "v2_tier_record", "v2_plays")


def _n(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def shown_units(sport, side):
    """The size the page shows: flat 1u on NBA, NFL and CBB plays, none on CFB or without a pick. Never reads the tier."""
    return 1 if side and sport in SHOWN_SPORTS else 0


def shadow_units(sport, tier):
    """The rule v2s-1 size of a play: Clear 1.5u, Mixed 1u, Thin 0.5u, Contested 0.5u, nothing (0) on CFB. None, never 0, when the play has no
    tier (not derivable at its cut) or the sport is not one the page covers: "no size because no evidence" is not "a size of zero". Pure: reads
    the sport and the stored tier only, never an outcome, a price or a result. Never feeds Top Reads, SM_GATE or an agree total."""
    if tier is None or sport not in SHADOW_SPORTS:
        return None
    if sport == "cfb":
        return SHADOW["cfb"]
    return SHADOW["sizes"].get(tier)


def shown_units_at(sport, cut, ladder_units):
    """The size the page actually showed at a card's cut: the SharpFlow ladder before 2026-11-18 8:31 AM CT, flat 1u on NBA and NFL from
    then, CBB flat from 2026-11-20 4:47 PM CT, CFB never after the first change. Derived on read, no row is rewritten."""
    if cut < FLAT_FROM:
        return ladder_units
    if sport in ("nba", "nfl"):
        return 1
    return 1 if sport == "cbb" and cut >= CBB_FROM else 0


# ---------- evidence tier ----------

def ev_of(sf):
    """The stored price-vs-fair read of a shown side (sf.signals.ev), or None."""
    return ((sf or {}).get("signals") or {}).get("ev")


def facts(sport, m, side):
    """The eight facts of the tier rule for the shown `side` of market group `m` (a card's markets[g]), from stored fields only:
    -> (facts {a1..a4, b1..b4}, facts_na []). A fact is True or False, or None when its input was not stored on this card (an old card:
    `rk` first stored on cards cut 2026-11-18, `tp` on cards cut from 2026-11-19). A live or new frozen card never carries None."""
    sides = m.get("sides") or {}
    sf = (m.get("sf") or {}).get("all") or {}
    other = [s for s in sides if s != side]
    allv = lambda s: (sides.get(s) or {}).get("all") or {}
    cnt = lambda s: allv(s).get("counts") or {}
    price_tier = sport in PRICE_TIER_SPORTS
    a1 = sum((cnt(o).get("hc") or 0) + (cnt(o).get("sharp") or 0) for o in other) >= 1
    if price_tier:
        rks = [allv(o).get("rk") for o in other]
        if any(r and (r.get("sharp_n") or 0) >= 1 for r in rks):
            a2 = True
        else:
            a2 = False if all(r is not None for r in rks) else None
        rk_s = allv(side).get("rk")
        b1 = (rk_s.get("sharp_n") or 0) >= 1 if rk_s is not None else None
        if "tp" not in m:
            a3 = None
        else:
            tb = (m.get("tp") or {}).get("tB")
            a3 = bool(tb and tb.get("side") and tb["side"] != side)
    else:
        a2 = b1 = a3 = False
    pts = (ev_of(sf) or {}).get("pts")
    a4 = bool(_n(pts) and pts <= -EV_PTS)
    b2 = bool(_n(pts) and pts >= EV_PTS)
    b3 = ((m.get("sf") or {}).get("fwd") or {}).get("side") == side
    b4 = ((allv(side).get("proven") or {}).get("wallets") or 0) >= 2
    f = {"a1": a1, "a2": a2, "a3": a3, "a4": a4, "b1": b1, "b2": b2, "b3": bool(b3), "b4": bool(b4)}
    return f, ([] if price_tier else list(FACTS_NA))


def tier_of(f, proven_n, ev_pts):
    """-> (tier, why). Clear, mixed, thin or contested, first match wins; (None, why) when a fact the rule needs was not stored at the cut
    (old cards only) and no stored fact against the side is already true."""
    if any(f.get(k) is True for k in ("a1", "a2", "a3", "a4")):
        return "contested", None
    unknown = [k for k in ("a1", "a2", "a3", "a4", "b1") if f.get(k) is None]
    if unknown:
        return None, "fact not stored at the cut: " + ", ".join(unknown)
    if (f["b1"] or f["b2"]) and f["b3"]:
        return "clear", None
    if proven_n <= 1 and not f["b1"] and ev_pts is None:
        return "thin", None
    return "mixed", None


# ---------- who holds each side ----------

def _tier_counts(mine):
    by = lambda t: [x for x in mine if (x.get("rk") or {}).get("tier") == t]
    box = lambda xs: {"n": len(xs), "usd": round(sum(x["usd"] for x in xs))}
    sh, mid, du = by("sharp"), by("mid"), by("dull")
    taken = {id(x) for x in sh + mid + du}
    return box(sh), box(du), box(mid), box([x for x in mine if id(x) not in taken])


def side_blocks(sport, sides_out, ws, side_names):
    """v2.sides[<side name>] for every side of the market group (variant all). `ws`: the group's holders as the card built them (after the
    hedge collapse), each with its CLV tier `rk` at the cut. Invariants (tests): holders = sum of counts; past_winner.n = hc + sharp;
    beats.n = rk.sharp_n, loses.n = rk.dull_n (NBA, NFL); usd = sharp + unproven + loser + excluded usd."""
    out = {}
    price_tier = sport in PRICE_TIER_SPORTS
    for s in side_names:
        a = (sides_out.get(s) or {}).get("all")
        if a is None:
            continue
        mine = [x for x in ws if x["side"] == s]
        c = a["counts"]
        blk = {"holders": sum(c.values()), "usd": a["sharp_usd"] + a["unproven_usd"] + a["loser_usd"] + a["excluded_usd"],
               "past_winner": {"n": c["hc"] + c["sharp"], "usd": a["sharp_usd"]},
               "losing_record": {"n": c["loser"], "usd": a["loser_usd"]},
               "price_tier": price_tier}
        if price_tier:
            beats, loses, even, few = _tier_counts(mine)
            blk.update({"beats": beats, "loses": loses, "even": even, "few": few})
        else:                                   # college: no tested CLV model, every holder is "few"
            blk.update({"beats": None, "loses": None, "even": None,
                        "few": {"n": len(mine), "usd": round(sum(x["usd"] for x in mine))}})
        out[s] = blk
    return out


def conflict(sides, side, a3):
    """v2.conflict: the shown side against the others, summed over the other sides. Counts and money only."""
    other = [v for k, v in sides.items() if k != side]
    pw = {"n": sum(o["past_winner"]["n"] for o in other), "usd": sum(o["past_winner"]["usd"] for o in other)}
    me = sides[side]
    pt = me["price_tier"]
    tot = me["usd"] + sum(o["usd"] for o in other)
    return {"past_winner_against": pw,
            "beats_for": me["beats"]["n"] if pt else None, "beats_against": sum(o["beats"]["n"] for o in other) if pt else None,
            "loses_for": me["loses"]["n"] if pt else None, "loses_against": sum(o["loses"]["n"] for o in other) if pt else None,
            "fade_dull_other_side": a3,
            "money_share_for": round(me["usd"] / tot, 3) if tot else None}


def past_winners(ws, cls, side):
    """Every past-winner wallet (class hc or sharp) on `side`, money order, from the full holder list (a card's `list` keeps the top 4)."""
    out = []
    for x in sorted((x for x in ws if x["side"] == side and cls.get(x["w"]) in ("hc", "sharp")), key=lambda x: -x["usd"]):
        usual = x["s"]["all"]["usual"]
        out.append({"w": x["w"], "usd": round(x["usd"]), "class": cls[x["w"]], "press": round(x["usd"] / usual, 2) if usual else None})
    return out


# ---------- the price you would get ----------

def _since(asof, t):
    return max(0, round((asof - t) / 60)) if _n(asof) and _n(t) else None


def _by_book(rows, asof):
    out = {}
    for r in rows or []:
        if isinstance(r, dict) and _n(r.get("t")) and r["t"] <= asof and r.get("book"):
            out.setdefault(r["book"], []).append(r)
    return out


def _last(rows, field):
    have = [r for r in rows or [] if r.get(field)]
    return max(have, key=lambda r: r["t"]) if have else None


def _vals(v, n):
    """The stored list when it has at least `n` entries, else None (a short or non-list row is not readable, never indexed)."""
    return v if isinstance(v, (list, tuple)) and len(v) >= n else None


def _side_line(g, v, away):
    """The book's line as it reads for the side (tape sp: [home line, ...]; tot: [line, ...]); None when the line is not a number."""
    if not _n(v[0]):
        return None
    return (-v[0] if away else v[0]) if g == "spread" else v[0]


def _same_line(ln, line):
    return _n(ln) and _n(line) and abs(ln - line) <= PIN_LINE_EPS


def exec_block(rows, g, norm, line, pin_odds, asof):
    """What a follower could get at `asof`, read from the book tape (rows of every book of one game, written when a book's numbers
    change: each `t` is the last change at or before `asof`, never "read at"). Absent keys mean not readable.
      us_best  best price for the side among DraftKings, FanDuel, BetMGM, BetRivers, bet365 on the SAME line (lowest vig-included
               implied probability, arithmetic on the stored odds); ties go to the alphabetically first book
      kalshi   moneyline only: Kalshi's home contract [bid, ask]; cost of the side = ask if home, 1 - bid if away
      novig    Novig's quote (px / nsp / ntot, the line must equal the ticket's): cost as for Kalshi
      pin      Pinnacle's price for the side (the card's pinnacle_odds) and the time of the tape row it came from
    Polymarket's displayed price is never copied in here, and no best ask is stored anywhere yet (spec D-P1), so `pm_ask` is absent.
    A malformed row (too short, a None where a number belongs) is skipped, never indexed blind."""
    out = {"asof": asof}
    books = _by_book(rows, asof)
    if norm in ("home", "away", "over", "under"):
        away = norm in ("away", "under")
        key = TAPE_KEY[g]
        best = None
        for b in US_BOOKS:
            r = _last(books.get(b), key)
            v = _vals(r[key], 2 if g == "ml" else 3) if r else None
            if v is None:
                continue
            if g == "ml":
                odds, ln = (v[0] if away else v[1]), None
            else:
                ln = _side_line(g, v, away)
                if not _same_line(ln, line):
                    continue
                odds = v[2] if away else v[1]
            p = SIG.american_prob(odds) if _n(odds) else None
            if p is None:
                continue
            if best is None or (p, b) < (best[0], best[1]):
                best = (p, b, odds, ln, r["t"])
        if best:
            out["us_best"] = {"book": best[1], "odds": best[2], "line": best[3], "px": round(best[0], 4), "t": best[4], "since_min": _since(asof, best[4])}
        if g == "ml":
            r = _last(books.get("Kalshi"), "px")
            v = _vals(r["px"], 2) if r else None
            if v is not None and _n(v[0]) and _n(v[1]):
                px = v[1] if norm == "home" else 1.0 - v[0]
                out["kalshi"] = {"px": round(px, 4), "t": r["t"], "since_min": _since(asof, r["t"])}
        nk = NOVIG_KEY[g]
        r = _last(books.get("Novig"), nk)
        v = _vals(r[nk], 2 if g == "ml" else 3) if r else None
        if v is not None:
            if g == "ml":
                bid, ask, ok = v[0], v[1], True
            else:
                bid, ask = v[1], v[2]
                ok = _same_line(_side_line(g, v, away) if g == "spread" else (v[0] if _n(v[0]) else None), line)
            if ok and _n(bid) and _n(ask):
                home = norm in ("home", "over")
                out["novig"] = {"px": round(ask if home else 1.0 - bid, 4), "t": r["t"], "since_min": _since(asof, r["t"])}
    if pin_odds is not None:
        r = _last(books.get("Pinnacle"), TAPE_KEY[g])
        if r:
            out["pin"] = {"odds": pin_odds, "t": r["t"]}
    return out


def vs_fair(sf, rows, g, asof):
    """The shown side's price against Pinnacle's no-vig fair: sf.signals.ev unchanged (pts = (fair - price) x 100, positive = price better
    than fair) plus the time of the Pinnacle row it read and the ticket line. Never absent on a pick; pts may be None with a reason."""
    sg = (sf or {}).get("signals")
    if sg is None:
        return {"pts": None, "fair": None, "t": None, "line": sf.get("line"), "why": "no_tape"}
    ev = sg.get("ev")
    if ev is None:
        return {"pts": None, "fair": None, "t": None, "line": sf.get("line"), "why": sg.get("why") or "no_tape_rows_for_game"}
    t = None
    if ev.get("fair") is not None:
        r = _last(_by_book(rows, asof).get("Pinnacle"), TAPE_KEY[g])
        t = r["t"] if r else None
    return {"pts": ev.get("pts"), "fair": ev.get("fair"), "t": t, "line": sf.get("line"), "why": ev.get("why") if ev.get("pts") is None else None}


def price_src(sf, kf):
    """`pm` when sf.price is the keyframe's Polymarket displayed price of the side on sf.cid, `pin` when the builder fell back to
    Pinnacle's vig-included price (a moneyline with no Polymarket price). None when there is no price."""
    if not sf or sf.get("price") is None:
        return None
    mk = ((kf or {}).get("mk") or {}).get(sf.get("cid")) or {}
    outs, px = mk.get("outs") or [], mk.get("px") or []
    if sf.get("side") in outs:
        oi = outs.index(sf["side"])
        if oi < len(px) and px[oi] is not None:
            return "pm"
    return "pin"


# ---------- public split (context only) ----------

def _split_sides(norms, stored):
    out = {}
    for name, n in norms.items():
        s = stored(n) if n else None
        if s:
            out[name] = s
    return out


def splits_live(game, g, norms, ts):
    """The feed's current public split for the group, both sides as stored (t = tickets %, m = money %), or None when it has none."""
    sp = ((game or {}).get("splits") or {}).get(SPLIT_KEY[g])
    if not isinstance(sp, dict):
        return None
    def stored(n):
        e = sp.get(n)
        return {"bets": e["t"], "money": e["m"]} if isinstance(e, dict) and _n(e.get("t")) and _n(e.get("m")) else None
    sides = _split_sides(norms, stored)
    return {"t": ts, "src": SPLIT_SRC, "basis": "live", "sides": sides} if sides else None


def splits_at(game, g, norms, cut):
    """The split as of the cut: the last splitHist row with ts <= cut. The history keeps the home (or over) side only; the other side is
    100 minus it and carries comp true. A last row with no split for the group means no split (never an older row's value)."""
    rows = [r for r in (game or {}).get("splitHist") or [] if _n(r.get("ts")) and r["ts"] <= cut]
    if not rows:
        return None
    r = max(rows, key=lambda r: r["ts"])
    v = r.get(SPLIT_KEY[g])
    if not isinstance(v, (list, tuple)) or len(v) < 2 or not _n(v[0]) or not _n(v[1]):
        return None
    def stored(n):
        if n in ("home", "over"):
            return {"bets": v[0], "money": v[1]}
        return {"bets": 100 - v[0], "money": 100 - v[1], "comp": True}
    sides = _split_sides(norms, stored)
    return {"t": r["ts"], "src": SPLIT_SRC, "basis": "at_cut", "sides": sides} if sides else None


# ---------- the per-market block ----------

def market_v2(sport, g, m, ws, cls, kf, asof, norms, rows=None, game=None, feed_ts=None, frozen=True, cut=None, heartbeat=None, ev=None):
    """-> (v2 block, splits or None) for one market group of a card. `m`: the market as the card built it (sides, sf, tp); `ws`: its
    holders; `cls`: {wallet: class} for variant all; `norms`: {side name: home|away|over|under|None}; `rows`: the book tape rows of the
    game (every book); `game`: the sharp-data feed game for the split. Reads stop at `asof`."""
    sf = (m.get("sf") or {}).get("all") or {}
    names = list((m.get("sides") or {}).keys())
    side = sf.get("side") if (sf.get("units") or 0) > 0 and sf.get("side") else None
    sides = side_blocks(sport, m["sides"], ws, names)
    v2 = {"rule": RULE, "side": side, "shown_units": shown_units(sport, side), "shown_rule": SHOWN_RULE, "untested": True,
          "tier": None, "shadow_units": None, "shadow_rule": SHADOW_RULE,
          "facts": None, "facts_na": [], "sides": sides, "conflict": None, "lead": None, "past_winners_for": None}
    if side:
        f, na = facts(sport, m, side)
        pw = past_winners(ws, cls, side)
        proven_n = (m["sides"][side]["all"].get("proven") or {}).get("wallets") or 0
        v2["tier"], _ = tier_of(f, proven_n, (ev_of(sf) or {}).get("pts"))
        v2["shadow_units"] = shadow_units(sport, v2["tier"])
        v2["facts"], v2["facts_na"] = f, na
        v2["conflict"] = conflict(sides, side, f["a3"])
        v2["lead"] = dict(pw[0]) if pw else None
        v2["past_winners_for"] = pw
        src = price_src(sf, kf)
        if src:
            v2["price_src"] = src
            if src == "pm":
                v2["pm"] = {"px": sf["price"], "t": sf.get("price_t"), "since_min": _since(asof, sf.get("price_t")), "kind": "displayed"}
        v2["exec"] = exec_block(rows, g, norms.get(side), sf.get("line"), sf.get("pinnacle_odds"), asof)
        v2["vs_fair"] = vs_fair(sf, rows, g, asof)
        try:                                    # the market-move flags: context, additive, and a failure drops them for this card only
            v2["flags"], v2["series"] = F.flags_block(rows, g, norms.get(side), asof, sport, heartbeat)
        except Exception as e:
            v2["flags"], v2["series"], v2["flags_error"] = None, None, type(e).__name__
            print("::warning::v2 flags dropped for %s %s: %s: %s" % (ev, g, type(e).__name__, e), file=sys.stderr)
    sp = None
    if game:
        sp = splits_at(game, g, norms, cut) if frozen else splits_live(game, g, norms, feed_ts)
    return v2, sp


def v2_slate(games):
    """The live-only slate read: shown plays in this build by tier, how many have a readable price-vs-fair, and every wallet that is a
    past winner on two or more shown plays (full holder lists). Sets lead.slate_plays on each play. Not written to frozen cards: a
    card is built at its own cut, before later games freeze, so a same-day count there would not be point in time."""
    plays = []
    for c in games:
        for g, m in (c.get("markets") or {}).items():
            v = m.get("v2") or {}
            if v.get("shown_units") == 1 and v.get("side"):
                plays.append((f"{c['ev']}|{g}", v))
    by_w = {}
    for key, v in plays:
        for p in v.get("past_winners_for") or []:
            by_w.setdefault(p["w"], []).append(key)
    for key, v in plays:
        if v.get("lead"):
            v["lead"]["slate_plays"] = len(by_w.get(v["lead"]["w"], []))
    by_tier = {t: 0 for t in TIERS}
    for _, v in plays:
        if v.get("tier") in by_tier:
            by_tier[v["tier"]] += 1
    same = sorted(({"w": w, "plays": len(k), "keys": k} for w, k in by_w.items() if len(k) >= 2), key=lambda x: (-x["plays"], x["w"]))
    return {"plays": len(plays), "by_tier": by_tier, "no_tier": sum(1 for _, v in plays if v.get("tier") is None),
            "vs_fair_readable": sum(1 for _, v in plays if (v.get("vs_fair") or {}).get("pts") is not None), "same_wallet": same}


def plays_fields():
    """`live.json` v2_plays: the rule version and the names of everything this module adds."""
    return {"rule": RULE, "spec": "docs/sharps-v2-plays-spec.md", "market_keys": list(V2_MARKET_KEYS), "top_keys": list(V2_TOP_KEYS),
            "shown_rule": SHOWN_RULE, "shadow": {"rule": SHADOW_RULE, "sizes": dict(SHADOW["sizes"]), "cfb": SHADOW["cfb"], "shown": False},
            "flags": F.flags_fields(), "context_only": True}


# ---------- shadow log ----------

def month_of(gst):
    """The log file month: the CENTRAL date of game start (an 11 PM CT game on the last day of a month stays in that month)."""
    return dt.datetime.fromtimestamp(gst, ZoneInfo("America/Chicago")).strftime("%Y-%m")


def log_row(rel, card, g, now):
    """One row of pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl: a projection of the frozen card's own stored v2 block (stored values only),
    so a row written later by the repair pass equals the row written at the freeze. Key = the graded sf row's key."""
    m = card["markets"][g]
    v2, sf = m["v2"], (m.get("sf") or {}).get("all") or {}
    conf = v2.get("conflict") or {}
    sides = v2.get("sides") or {}
    side = v2["side"]
    f = v2.get("facts") or {}
    ev = (v2.get("vs_fair") or {})
    tb = ((m.get("tp") or {}).get("tB") or {}).get("side")
    row = {"key": f"{rel}|{g}|all|sf", "v": 1, "rule": v2["rule"], "src": "frozen", "logged_at": now, "sport": card["sport"], "ev": card["ev"],
            "gst": card["gst"], "cut": card["cut"], "group": g, "side": side, "line": sf.get("line"), "outs": sf.get("outs"), "cid": sf.get("cid"),
            "price": sf.get("price"), "price_t": sf.get("price_t"), "price_src": v2.get("price_src"), "shown_units": v2["shown_units"],
            "shadow_units": v2.get("shadow_units", shadow_units(card["sport"], v2["tier"])), "shadow_rule": v2.get("shadow_rule", SHADOW_RULE),
            "ladder_units": sf.get("units"), "tier": v2["tier"], "facts": f, "facts_na": v2.get("facts_na"),
            "ev_pts": ev.get("pts"), "fair": ev.get("fair"), "pin_t": ev.get("t"),
            "past_winner_for": (sides.get(side) or {}).get("past_winner", {}).get("n"),
            "past_winner_against": (conf.get("past_winner_against") or {}).get("n"),
            "beats_for": conf.get("beats_for"), "beats_against": conf.get("beats_against"),
            "loses_for": conf.get("loses_for"), "loses_against": conf.get("loses_against"),
            "tb_side": tb, "fwd_side": ((m.get("sf") or {}).get("fwd") or {}).get("side"),
            "lead_w": (v2.get("lead") or {}).get("w"), "money_share_for": conf.get("money_share_for"),
            "exec": v2.get("exec"), "splits": m.get("splits"),
            "counts": (card.get("test") or {}).get("counts"), "why_not": (card.get("test") or {}).get("why_not")}
    if "flags" in v2:                           # new rows only: a card built before the flags has no key, so its row has none ("not logged", never quiet)
        row["mf"] = F.mf_of(v2["flags"])
    return row


def log_rows_of(rel, card, now):
    """The rows a frozen card owes the log: one per rule pick (side set, ladder units above 0), every sport, CFB included."""
    out = []
    for g in sorted(card.get("markets") or {}):
        m = card["markets"][g]
        v2 = m.get("v2")
        sf = (m.get("sf") or {}).get("all") or {}
        if v2 and v2.get("side") and (sf.get("units") or 0) > 0:
            out.append(log_row(rel, card, g, now))
    return out


def logged_keys(root, sport):
    keys = set()
    d = os.path.join(root, sport, "v2_tier")
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".jsonl"):
                with open(os.path.join(d, fn)) as f:
                    for line in f:
                        try:
                            keys.add(json.loads(line)["key"])
                        except (ValueError, KeyError, TypeError):   # a non-object or keyless line is skipped, never fatal
                            pass
    return keys


def append_log(root, sport, rows):
    """Append-only: rows already in the log (by key) are skipped, existing lines are never rewritten. Month by the Central date of game start."""
    have = logged_keys(root, sport)
    new = sorted((r for r in rows if r["key"] not in have), key=lambda r: r["key"])
    by_month = {}
    for r in new:
        by_month.setdefault(month_of(r["gst"]), []).append(r)
    for mo, rs in sorted(by_month.items()):
        d = os.path.join(root, sport, "v2_tier")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, mo + ".jsonl"), "a") as f:
            for r in rs:
                f.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")
    return len(new)


def sync_log(root, sport, now, extra=(), days=7):
    """Append a row for every frozen card of the last `days` days (plus `extra` card paths relative to root) that has a v2 block and no log
    row: a run that wrote a card but died before the append is healed here. Copies stored values only."""
    paths = {os.path.join(root, p) for p in extra}
    base = os.path.join(root, sport, "frozen")
    for dd in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        d = os.path.join(base, dd)
        for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            try:
                gst = int(fn.rsplit("@", 1)[1].split(".")[0])
            except (IndexError, ValueError):
                continue
            if gst >= now - days * 86400:
                paths.add(os.path.join(d, fn))
    rows = []
    have = logged_keys(root, sport)
    for p in sorted(paths):
        try:
            with open(p) as f:
                c = json.load(f)
        except (OSError, ValueError):
            continue
        rel = os.path.relpath(p, root)
        rows += [r for r in log_rows_of(rel, c, now) if r["key"] not in have]
    return append_log(root, sport, rows)


# ---------- stripping (the back-compat test) ----------

def strip_plays_v2(doc):
    """A copy of a live.json (or one card) without anything this module adds: markets[g].v2, markets[g].splits, and the top-level
    v2_slate, v2_tier_record, v2_plays. What is left must equal the file as it was before the V2 plays data, byte for byte."""
    out = copy.deepcopy(doc)
    for k in V2_TOP_KEYS:
        out.pop(k, None)
    cards = out.get("games") if isinstance(out.get("games"), list) else [out]
    for c in cards:
        for m in (c.get("markets") or {}).values():
            for k in V2_MARKET_KEYS:
                m.pop(k, None)
    return out
