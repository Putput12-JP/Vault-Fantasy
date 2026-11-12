#!/usr/bin/env python3
"""Proven-sharps side cards: per game and per side, how much money proven sharps, unproven wallets and losing wallets hold, plus the
combined record of the proven ones, all as of the cut (game start - 15 min).

Step 3 of the side-card build (docs/side-cards.md). Inputs:
  - the T-15 keyframes and live holder logs from step 2 (pm-holders-data: pm_holders/<sport>/...)
  - the graded wallet ledger from step 1 (sharp-history: pm_ledger/...)
  - sharp-data data.json, only to attach the Vault game key and start time
Outputs:
  - frozen cards: pm_cards/<sport>/frozen/<YYYY-MM-DD>/<slug>@<gst>.json, one per keyframe, written once (append-only branch)
  - live cards: one JSON of every upcoming game, rebuilt every run (published to a force-pushed branch, never to history)

Sharp money is context only (CLAUDE.md). The card's `lock_shadow` is the pre-registered rule of docs/sharp-card-prereg.md, recorded so
it can be graded forward; it is never a pick, never feeds Top Reads, SM_GATE or any agree total.

Every rule constant below is SharpFlow's, read from its public source (docs/sharpflow-teardown.md), never invented:
  PROVEN  Door-2 (src/lib/whitelistTier.js v5): sport book n >= 6, win rate >= 55%, dollar ROI > 3%
  LOSER   not proven and (book PnL < 0, else L30 ROI < 0, else losses > wins) (moneyRiver.js / cH)
  FLOOR   a wallet's money on a side counts from $250 (index.js Nj=250)
  PRESS   sized up = position / usual stake >= 1.5 (Ku=1.5)
  L30     30-day window, shown with n >= 2 (exportWalletProfiles RECENT_DOLLAR_RESCUE_DAYS, l30Book)
  POSITION one bet = one wallet x game x market type x side (writeSharpActions positionDocId): ledger rows on several spread or
          total rungs of the same side are one position (stake and PnL summed, result by the sign of the summed PnL); on a card a
          wallet's side money is its LARGEST single rung, floored at $250 (bundle UW keeps the max position per wallet|side|market)
  HEDGE   a wallet on both sides of one market group keeps only legs at >= 1.0x its usual stake, the highest-ratio one; with no
          such leg it is dropped as balanced dust (ags.js collapseHedgedWalletsV12). A wallet with no usual stake keeps its larger leg.
  LOCK    press-ladder gates (pressLadderOverlay.js): money share for >= 60% of ALL money above the floor (excluded wallets left
          out), a wallet for (any class) with book n >= 15 pressing >= 1.5x, no proven wallet against, at least one proven wallet
          for. Units at a clean price step: biggest press >= 3x 5u, >= 2x 2u, else 3u; a side priced under 0.50 is capped at 1u on
          every market type. Vault records only this clean-step ladder (no price steps, no rescue rungs) and labels it so.
  SCORE   AGS-Unified v12 (src/lib/ags.js): wallet quality = 3 x clamp(prior ROI %, 0, 30) x clamp(size ratio, 0.5, 2.5) x
          min(1, sqrt(n / 20)), proven wallets only; side score = (mean for - mean against) / (for + against + 0.5); a score <= 0 is
          FADE, and positive scores are labelled by the fallback cut points 0.781 / 0.916 / 0.957 / 0.981 (WEAK, LEAN, LOCK,
          PREMIUM, ELITE). SharpFlow's live cut points sit in its private calibration store, so Vault uses the published fallback.
          Recorded per side as `ags`, a shadow field. It does not set the units: those stay the press ladder.
  Vault approximations of SharpFlow admission filters (they filter discovery; Vault applies them on the card):
  HEDGER  hedged-at-cutoff share of the wallet's ledger markets >= 25% with >= 8 markets (BOTH_SIDES_REJECT, MIN_SPORTS_MARKETS;
          SharpFlow counts both-sides over all closed sports positions, early exits included)
  CHURN   all-time (all categories, /v2/user-stats) volume / realized PnL > 100 (CHURN_VOL_PNL; SharpFlow reads the sports board;
          its ROI < 2% clause is implied by vol/PnL > 100)

Point-in-time rules
  - Wallet stats use only ledger rows with settled_at < cut. User-stats snapshots are taken from the latest one dated <= cut.
  - A wallet first selected into the ledger universe after the cut is untracked on that card (no record, unproven), so a wallet
    picked because it won this game can never count.
  - A frozen card stores when it was built; the pre-registration counts only cards built before game start on a ledger run that
    finished before the cut (`test.counts`).
  - Every stat is computed twice: from all rows (SharpFlow's way, which includes `backfill` rows of wallets chosen with hindsight)
    and from `forward` rows only. Both are on the card; the pre-registration names which one is primary.
  - Hedged legs (a wallet on both outcomes at the cutoff) are left out of records. SPLIT-funded rows count in W/L, never in dollars.
  - Money on a side is shares x the market price at the cut (the keyframe's `usd_at_mark`), labelled as mark value, not cost.

usage: build_side_cards.py --holders DIR --ledger DIR [--sharp-data data.json] --frozen-out DIR --live-out FILE [--sports nba,nfl,cfb]
"""
import argparse, bisect, datetime as dt, glob, json, math, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pm_ledger import CUTOFF_SEC, FULL_GAME  # noqa: E402
import sf_rungs as SF  # noqa: E402

PROVEN_N, PROVEN_WR, PROVEN_ROI = 6, 0.55, 0.03
FLOOR_USD = 250
PRESS = 1.5
L30_DAYS, L30_MIN_N = 30, 2
HEDGER_SHARE, HEDGER_MIN_MARKETS = 0.25, 8
CHURN_VOL_PNL, CHURN_ROI_MAX = 100, 0.02
LOCK_SHARE, LOCK_PRESSER_N = 0.60, 15
HEDGE_FLOOR = 1.0                          # ags.js V12_HEDGE_FLOOR
BAND5, BAND4, BAND4_UNITS, BAND3_UNITS, BAND5_UNITS, DOG_PX, DOG_UNITS = 3.0, 2.0, 2, 3, 5, 0.50, 1
LAST_N = 20
# AGS-Unified v12 (src/lib/ags.js): per-wallet quality and the positive-score cut points of AGS_V12_FALLBACK_CALIBRATION
AGS_TIER_W, AGS_ROI_CAP, AGS_SIZE_LO, AGS_SIZE_HI, AGS_N_REF = 3, 30.0, 0.5, 2.5, 20
AGS_CUTS = ((0.981, "ELITE"), (0.957, "PREMIUM"), (0.916, "LOCK"), (0.781, "LEAN"))
SHOW_PROVEN, SHOW_LOSERS = 4, 3            # wallets listed per side (index.js DN=4, zW=3)
GROUP = {"moneyline": "ml", "spreads": "spread", "totals": "total"}
EVENT_RE = re.compile(r"^(.*?-\d{4}-\d{2}-\d{2})")
START_GAP_FLAG = 10 * 60                  # Polymarket and Vault start times more than 10 min apart (prereg "known limits")
VERSION = 1
SIZE_BANDS = (0.0, 0.75, 1.5, 3.0)        # size vs usual stake bands for the "at this size" record (below 0.75x, 0.75 to 1.5x, ...)
CLOSE_STALE = 30 * 60                     # a keyframe price older than this at the cut is not a close (prereg "unpriced" rule)


def event_of(slug):
    m = EVENT_RE.match(slug or "")
    return m.group(1) if m else slug


def load_closes(holders, sport, markets, pm_closes):
    """{(cid, outcome index): close} for ledger markets, from stored prices only (never estimated):
    1. Vault's own T-15 keyframes (pm_holders/<sport>/frozen): the market's price at the cut, when read within 30 min of it;
    2. data/pm_closes.json (Pendulum Flow, NBA and NFL): the last quote before kickoff, matched on event slug, market type, line and
       an identical outcome list. `p` is outcomes[0]'s price."""
    out, cut_of = {}, {}
    for path in sorted(glob.glob(os.path.join(holders or "", sport, "frozen", "*", "*.json"))):
        try:
            with open(path) as f:
                kf = json.load(f)
        except (OSError, ValueError):
            continue
        for cid, mk in (kf.get("mk") or {}).items():
            px, t = mk.get("px"), mk.get("px_t")
            if not px or t is None or t < kf["cut"] - CLOSE_STALE or kf["cut"] <= cut_of.get(cid, -1):
                continue                             # a postponed game: the keyframe with the latest cut is the close
            if not all(v is not None and 0 < v < 1 for v in px):
                continue                             # both outcomes from one read, or none
            cut_of[cid] = kf["cut"]
            for oi, v in enumerate(px):
                out[(cid, oi)] = v
    games = (pm_closes or {}).get("games") or {}
    key = {"moneyline": "ml", "spreads": "spreads", "totals": "totals"}
    for cid, mk in (markets or {}).items():
        g = games.get(f"{sport}|{event_of(mk.get('slug'))}")
        if not g or mk.get("mt") not in key or (cid, 0) in out:
            continue
        cands = g.get(key[mk["mt"]])
        for c in [cands] if isinstance(cands, dict) else (cands or []):
            if not c or c.get("p") is None or list(c.get("outcomes") or []) != list(mk.get("outs") or []):
                continue
            if mk["mt"] != "moneyline" and (c.get("line") is None or mk.get("line") is None or float(c["line"]) != float(mk["line"])):
                continue
            if 0 < c["p"] < 1:
                out[(cid, 0)], out[(cid, 1)] = c["p"], 1.0 - c["p"]
            break
    return out


# ---------- ledger: per-wallet books as of a time ----------

class Ledger:
    def __init__(self, rows, markets, first_seen, user_stats, run_at=None, closes=None):
        self.by_w = {}
        for r in rows:
            self.by_w.setdefault(r["w"], []).append(r)
        for rs in self.by_w.values():
            rs.sort(key=lambda r: r["settled_at"])
        self.keys = {w: [r["settled_at"] for r in rs] for w, rs in self.by_w.items()}
        self.markets = markets
        self.first_seen = first_seen
        self.us = {}
        for s in user_stats:
            self.us.setdefault(s["w"], []).append(s)
        for v in self.us.values():
            v.sort(key=lambda s: s.get("at") or 0)
        self.run_at = run_at
        self.closes = closes or {}

    @classmethod
    def load(cls, root, sport, holders=None, pm_closes=None):
        rows = []
        for fn in sorted(glob.glob(os.path.join(root, "bets", sport, "*.jsonl"))):
            with open(fn) as f:
                rows += [json.loads(l) for l in f if l.strip()]
        def j(p, d):
            try:
                with open(p) as f:
                    return json.load(f)
            except FileNotFoundError:
                return d
        us = []
        for fn in sorted(glob.glob(os.path.join(root, "user_stats", "*.jsonl"))):
            with open(fn) as f:
                us += [json.loads(l) for l in f if l.strip()]
        markets = j(os.path.join(root, "markets", sport + ".json"), {})
        return cls(rows, markets, j(os.path.join(root, "first_seen.json"), {}), us,
                   (j(os.path.join(root, "summary.json"), {}) or {}).get("run_at"), load_closes(holders, sport, markets, pm_closes))

    def stats(self, w, asof):
        """The wallet's sport book as of `asof` (rows settled strictly before it), all rows and forward rows."""
        fs = self.first_seen.get(w)
        if fs is None or fs > asof:                  # not in the universe at the cut: untracked, whatever its later record
            empty = book([], asof, self.markets)
            return {"tracked": False, "markets": 0, "hedged_share": 0.0, "all": empty, "fwd": empty, "churn": None, "excluded": None}
        rs = self.by_w.get(w, [])
        rs = rs[:bisect.bisect_left(self.keys.get(w, []), asof)]
        hedged_cids = {r["cid"] for r in rs if r.get("hedged")}
        cids = {r["cid"] for r in rs}
        out = {"tracked": True, "markets": len(cids), "hedged_share": (len(hedged_cids) / len(cids)) if cids else 0.0,
               "all": book([r for r in rs if not r.get("hedged")], asof, self.markets, self.closes),
               "fwd": book([r for r in rs if not r.get("hedged") and r.get("src") == "forward"], asof, self.markets, self.closes)}
        snap = [s for s in self.us.get(w, []) if (s.get("at") or 0) <= asof]
        out["churn"] = churn(snap[-1]) if snap else None
        out["excluded"] = ("hedger" if cids and len(cids) >= HEDGER_MIN_MARKETS and out["hedged_share"] >= HEDGER_SHARE
                           else "churn" if out["churn"] else None)
        return out


def positions(rows, markets, closes=None):
    """Ledger rows -> SharpFlow positions: one per game x market type x side. Rungs of one side are summed; the result is the sign
    of the summed PnL; a position touched by a SPLIT row is kept out of dollar totals."""
    pos = {}
    for r in rows:
        mk = markets.get(r["cid"]) or {}
        outs = mk.get("outs") or []
        side = outs[r["oi"]] if r["oi"] < len(outs) else r["oi"]
        key = (event_of(mk.get("slug")) or r["cid"], r.get("mt"), side)
        p = pos.setdefault(key, {"ev": key[0], "stake": 0.0, "pnl": 0.0, "settled_at": 0, "split": False, "pxs": 0.0, "mt": r.get("mt"),
                                 "clv_s": 0.0, "clv_st": 0.0})
        close = closes.get((r["cid"], r["oi"])) if closes else None
        if close is not None and r.get("avg") is not None and r["stake"] > 0 and not r.get("split"):   # a SPLIT's 0.5 is booked, not paid
            p["clv_s"] += (close - r["avg"]) * r["stake"]
            p["clv_st"] += r["stake"]
        p["stake"] += r["stake"]
        p["pxs"] += (r.get("avg") or 0.0) * r["stake"]
        p["pnl"] += r["pnl"]
        p["settled_at"] = max(p["settled_at"], r["settled_at"])
        p["split"] = p["split"] or bool(r.get("split"))
    for p in pos.values():
        p["px"] = p["pxs"] / p["stake"] if p["stake"] > 0 else None
        p["res"] = "win" if p["pnl"] > 1e-9 else "loss" if p["pnl"] < -1e-9 else "push"
        p["clv"] = p["clv_s"] / p["clv_st"] if p["clv_st"] > 0 else None   # stake-weighted close minus entry price, where a close is stored
    return list(pos.values())


def book(rows, asof, markets, closes=None):
    ps = positions(rows, markets, closes)
    wins = sum(p["res"] == "win" for p in ps)
    losses = sum(p["res"] == "loss" for p in ps)
    cash = [p for p in ps if not p["split"]]
    stake = sum(p["stake"] for p in cash)
    pnl = sum(p["pnl"] for p in cash)
    l30 = [p for p in cash if p["settled_at"] >= asof - L30_DAYS * 86400]
    l30_stake = sum(p["stake"] for p in l30)
    legs = {}
    for p in ps:                                     # one leg per game: the biggest position the wallet had on it
        if p["ev"] not in legs or p["stake"] > legs[p["ev"]]["stake"]:
            legs[p["ev"]] = p
    b = {"n": wins + losses, "w": wins, "l": losses, "p": sum(p["res"] == "push" for p in ps),
         "wr": wins / (wins + losses) if wins + losses else None,
         "stake": round(stake, 2), "pnl": round(pnl, 2), "roi": pnl / stake if stake > 0 else None,
         "usual": stake / len(cash) if cash else None,
         "flat_roi": (sum(p["pnl"] / p["stake"] for p in cash if p["stake"] > 0) / sum(1 for p in cash if p["stake"] > 0))
         if any(p["stake"] > 0 for p in cash) else None,
         "l30_n": sum(p["res"] in ("win", "loss") for p in l30),
         "l30_roi": (sum(r["pnl"] for r in l30) / l30_stake) if l30_stake > 0 else None,
         "bets": sorted(([p["settled_at"], round(p["px"], 4), p["res"] == "win", p["mt"]] for p in ps if p["res"] != "push" and p["px"]), key=lambda b: b[0]),
         "legs": sorted(([r["settled_at"], r["res"]] for r in legs.values()), reverse=True)[:LAST_N],
         # price skill: positions with a stored close, and how many were bought below it (SharpFlow's "beat the closing line")
         "clv_n": sum(1 for p in ps if p["clv"] is not None),
         "clv_beat": sum(1 for p in ps if p["clv"] is not None and p["clv"] > 0),
         "clv_mean": (sum(p["clv"] for p in ps if p["clv"] is not None) / sum(1 for p in ps if p["clv"] is not None))
         if any(p["clv"] is not None for p in ps) else None,
         "sizes": [[p["stake"], p["res"] == "win"] for p in cash if p["res"] in ("win", "loss") and p["stake"] > 0]}
    if b["l30_n"] < L30_MIN_N:
        b["l30_roi"] = None
    b["proven"] = bool(b["n"] >= PROVEN_N and b["wr"] is not None and b["wr"] >= PROVEN_WR and b["roi"] is not None
                       and b["roi"] > PROVEN_ROI)
    if b["proven"] or b["n"] == 0:
        b["loser"] = False
    elif stake > 0:
        b["loser"] = pnl < 0
    elif b["l30_roi"] is not None:
        b["loser"] = b["l30_roi"] < 0
    else:
        b["loser"] = losses > wins
    return b


def churn(snap):
    a = (snap or {}).get("all_time_pnl") or {}
    pnl, vol = a.get("realized_pnl"), a.get("volume_usdc")
    if not pnl or not vol or pnl <= 0:
        return False
    return vol / pnl > CHURN_VOL_PNL and pnl / vol < CHURN_ROI_MAX


# ---------- cards ----------

def card(kf, ledger, sport, vault=None, frozen=True):
    """One game's card from a keyframe (step 2) and the ledger as of its cut."""
    cut = kf["cut"]
    ix = {c: i for i, c in enumerate(kf["cols"])}
    best = {}                                        # (group, wallet, side) -> (usd, cid): the wallet's largest single rung
    for h in kf["h"]:
        cid, oi, w, usd = h[ix["cid"]], h[ix["oi"]], h[ix["wallet"]], h[ix["usd_at_mark"]]
        mk = kf["mk"].get(cid)
        if not mk or usd is None or mk["mt"] not in GROUP or oi >= len(mk.get("outs") or []):
            continue
        key = (GROUP[mk["mt"]], w, mk["outs"][oi])
        if key not in best or usd > best[key][0]:
            best[key] = (usd, cid)
    stats_cache = {}

    def st(w):
        if w not in stats_cache:
            stats_cache[w] = ledger.stats(w, cut)
        return stats_cache[w]

    legs_by = {}
    for (g, w, side), (usd, cid) in best.items():
        if usd >= FLOOR_USD:                         # the floor applies to each position, as SharpFlow's board does
            legs_by.setdefault((g, w), []).append((side, usd, cid))
    groups, dust = {}, 0
    for (g, w), legs in legs_by.items():
        s = st(w)
        usual = s["all"]["usual"]
        two_way = len(legs) > 1
        if two_way and usual:
            keep = [l for l in legs if l[1] / usual >= HEDGE_FLOOR]
            if not keep:
                dust += 1                            # balanced dust: dropped
                continue
            side, usd, cid = max(keep, key=lambda l: l[1] / usual)
        else:
            side, usd, cid = max(legs, key=lambda l: l[1])
        groups.setdefault(g, []).append({"w": w, "side": side, "usd": usd, "cid": cid, "two_way": two_way, "s": s})
    built = int(time.time())
    out = {"v": VERSION, "sport": sport, "ev": kf["ev"], "gst": kf["gst"], "cut": cut, "frozen": frozen,
           "built": built, "keyframe_written": kf.get("written"), "ledger_run_at": ledger.run_at,
           "money_basis": "shares x market price at the cut", "context_only": True,
           "coverage": {"markets_read": len(kf["mk"]), "markets_missed": len(kf.get("miss") or []),
                        "late_reads": kf.get("late_reads", 0), "two_way_dust_dropped": dust,
                        "max_read_lag_s": max([m["frz_lag"] for m in kf["mk"].values()] or [0])},
           "vault": vault, "markets": {}}
    if frozen:
        why = []
        if built > kf["gst"]:
            why.append("built after game start")
        if not ledger.run_at or ledger.run_at >= cut:
            why.append("ledger run not before the cut")
        out["test"] = {"counts": not why, "why_not": why}
    for g, ws in groups.items():
        sides_all = sorted({side for (gg, _, side) in best if gg == g})
        out["markets"][g] = {"sides": {}, "lock_shadow": {}}
        for variant in ("all", "fwd"):
            cls = {x["w"]: classify(x, variant) for x in ws}
            for side in sides_all:
                mine = [x for x in ws if x["side"] == side]
                theirs = [x for x in ws if x["side"] != side]
                sharp_for = sum(x["usd"] for x in mine if cls[x["w"]] in ("hc", "sharp"))
                sharp_vs = sum(x["usd"] for x in theirs if cls[x["w"]] in ("hc", "sharp"))
                loser_for = sum(x["usd"] for x in mine if cls[x["w"]] == "loser")
                loser_vs = sum(x["usd"] for x in theirs if cls[x["w"]] == "loser")
                proven = [x for x in mine if cls[x["w"]] in ("hc", "sharp")]
                legs = sorted((l for x in proven for l in x["s"][variant]["legs"]), reverse=True)[:LAST_N]
                l30 = [(x["usd"], x["s"][variant]["l30_roi"]) for x in proven]
                side_out = {
                    "sharp_usd": round(sharp_for), "hc_usd": round(sum(x["usd"] for x in mine if cls[x["w"]] == "hc")),
                    "unproven_usd": round(sum(x["usd"] for x in mine if cls[x["w"]] == "unproven")),
                    "loser_usd": round(loser_for),
                    "excluded_usd": round(sum(x["usd"] for x in mine if cls[x["w"]] == "excluded")),
                    "pct_of_sharp": round(100 * sharp_for / (sharp_for + sharp_vs)) if sharp_for + sharp_vs else None,
                    "pct_of_losers": round(100 * loser_for / (loser_for + loser_vs)) if loser_for + loser_vs else None,
                    "proven": {
                        "wallets": len(proven),
                        "w": sum(x["s"][variant]["w"] for x in proven), "l": sum(x["s"][variant]["l"] for x in proven),
                        "l30_roi": (sum(u * r for u, r in l30) / sum(u for u, _ in l30)) if l30 and all(r is not None for _, r in l30) else None,
                        "lifetime_pnl": round(sum(x["s"][variant]["pnl"] for x in proven)) if proven else None,
                        "last20": [res[0].upper() for _, res in legs]},
                    "list": [wallet_line(x, variant, cls[x["w"]]) for x in sorted(proven, key=lambda x: -x["usd"])[:SHOW_PROVEN]],
                    "losers": [wallet_line(x, variant, "loser") for x in
                               sorted((x for x in mine if cls[x["w"]] == "loser"), key=lambda x: -x["usd"])[:SHOW_LOSERS]],
                    # tracked wallets that are not proven yet (SharpFlow's "secondary"), with whatever record they have
                    "unproven_list": [wallet_line(x, variant, "unproven") for x in
                                      sorted((x for x in mine if cls[x["w"]] == "unproven" and x["s"]["tracked"]),
                                             key=lambda x: -x["usd"])[:SHOW_PROVEN]],
                    "counts": {k: sum(1 for x in mine if cls[x["w"]] == k) for k in ("hc", "sharp", "unproven", "loser", "excluded")},
                }
                side_out["ags"] = ags_side(side, ws, cls, variant)
                p = side_out["proven"]
                p["win_pct"] = round(100 * p["w"] / (p["w"] + p["l"]), 1) if p["w"] + p["l"] else None
                out["markets"][g]["sides"].setdefault(side, {})[variant] = side_out
            out["markets"][g]["lock_shadow"][variant] = lock_shadow(g, ws, cls, variant, kf)
            out["markets"][g].setdefault("sf", {})[variant] = sf_market(g, ws, cls, variant, kf, sides_all, out["markets"][g]["sides"])
    return out


def ags_quality(x, variant, k):
    """SharpFlow agsV12WalletQuality. Only a proven (CONFIRMED) wallet scores; FLAT is no longer assigned (whitelistTier.js)."""
    if k not in ("hc", "sharp"):
        return 0.0
    b = x["s"][variant]
    flat, dollar = b.get("flat_roi"), b["roi"]       # priorRoi: flat ROI of the sport book, else its dollar ROI (actionLockPin.js)
    roi = flat if flat is not None and flat > 0 else dollar if dollar is not None and dollar > 0 else 0.0
    roi = max(0.0, min(AGS_ROI_CAP, roi * 100))
    size = max(AGS_SIZE_LO, min(AGS_SIZE_HI, x["usd"] / b["usual"] if b["usual"] else 0.0))
    return AGS_TIER_W * roi * size * min(1.0, math.sqrt(max(0, b["n"]) / AGS_N_REF))


def ags_tier(score):
    if score is None:
        return None
    if score <= 0:
        return "FADE"
    return next((name for cut, name in AGS_CUTS if score > cut), "WEAK")


def ags_side(side, ws, cls, variant):
    """SharpFlow's AGS-Unified v12 score for one side: (mean quality for - mean quality against) / (for + against + 0.5).
    Every tracked wallet with a book counts in its side's mean (a wallet that is not proven counts as 0, as in aggregateSideV12);
    excluded wallets and wallets with no book are left out. The tier uses SharpFlow's fallback cut points, which were fitted on
    SharpFlow's picks, not Vault's: Vault has no calibration of its own. A shadow field: it never sets a size or a pick."""
    pool = [x for x in ws if cls[x["w"]] != "excluded" and x["s"][variant]["n"] > 0]
    f = [ags_quality(x, variant, cls[x["w"]]) for x in pool if x["side"] == side]
    a = [ags_quality(x, variant, cls[x["w"]]) for x in pool if x["side"] != side]
    if not f and not a:
        return None
    fm, am = (sum(f) / len(f) if f else 0.0), (sum(a) / len(a) if a else 0.0)
    score = 0.0 if fm == 0 and am == 0 else (fm - am) / (fm + am + 0.5)
    return {"score": round(score, 3), "tier": ags_tier(score), "for_mean": round(fm, 2), "against_mean": round(am, 2),
            "for_n": len(f), "against_n": len(a), "contributors": sum(1 for q in f + a if q > 0)}


def sf_market(g, ws, cls, variant, kf, sides, sides_out):
    """SharpFlow's stake policy (scripts/sf_rungs.py, a replica with the gaps it lists) for this market group. One side at most is staked:
    the side with the most units, ties to the higher AGS score. A shadow field; it never feeds the lock, Top Reads or an agree total."""
    cut = kf["cut"]
    pool = [x for x in ws if cls[x["w"]] != "excluded"]
    trust_cache = {}

    def trust(w, market_only):
        k = (w, market_only)
        if k not in trust_cache:
            bets = [(t, p, won) for t, p, won, mt in x_bets[w] if not market_only or GROUP.get(mt) == g]
            trust_cache[k] = SF.trust_state(bets, cut) if bets else None
        return trust_cache[k]

    x_bets = {x["w"]: x["s"][variant]["bets"] for x in pool}
    res = {}
    for side in sides:
        rows = []
        for x in pool:
            b = x["s"][variant]
            decided = [bet[2] for bet in b["bets"]]
            streak = 0
            for won in reversed(decided):
                if won:
                    break
                streak += 1
            rows.append({"dir": "FOR" if x["side"] == side else "AG", "invested": x["usd"],
                         "ratio": x["usd"] / b["usual"] if b["usual"] else None, "n": b["n"],
                         "wr": b["wr"] * 100 if b["wr"] is not None else None, "door2": b["proven"], "streak": streak,
                         "trust": trust(x["w"], False), "trust_mkt": trust(x["w"], True)})
        mine = [x for x in pool if x["side"] == side]
        cid = max(mine, key=lambda x: x["usd"])["cid"] if mine else None
        mk = kf["mk"].get(cid) if cid else None
        px = None
        if mk and mk.get("px") and side in (mk.get("outs") or []):
            oi = mk["outs"].index(side)
            px = mk["px"][oi] if oi < len(mk["px"]) else None
        ags = (sides_out.get(side, {}).get(variant) or {}).get("ags")
        r = SF.evaluate(rows, g, px, ags["score"] if ags else None)
        r.update({"price": px, "ags_score": ags["score"] if ags else None})
        res[side] = r
    staked = [(r["units"], r["ags_score"] or 0, side) for side, r in res.items() if r["units"] > 0]
    if not staked:
        return {"side": None, "units": 0, "rung": None, "reason": min((r["reason"] for r in res.values()), default="no_wallets"), "missing": SF.MISSING}
    _, _, side = max(staked)
    r = res[side]
    cid = max((x for x in pool if x["side"] == side), key=lambda x: x["usd"])["cid"]
    mk = kf["mk"].get(cid) or {}
    return {"side": side, "units": r["units"], "rung": r["rung"], "reason": r["reason"], "price": r["price"], "price_t": mk.get("px_t"),
            "line": mk.get("line"), "outs": mk.get("outs"), "cid": cid, "missing": SF.MISSING}


def classify(x, variant):
    b = x["s"][variant]
    if x["s"]["excluded"]:
        return "excluded"
    if b["proven"]:
        return "hc" if b["usual"] and x["usd"] / b["usual"] >= PRESS else "sharp"
    return "loser" if b["loser"] else "unproven"


def at_size(b, press):
    """The wallet's record on positions in the same size band (vs its usual stake) as this one, and the share of its bets there."""
    if press is None or not b["usual"] or not b.get("sizes"):
        return None
    lo = max(x for x in SIZE_BANDS if x <= press)
    hi = next((x for x in SIZE_BANDS if x > lo), None)
    band = [won for st, won in b["sizes"] if st / b["usual"] >= lo and (hi is None or st / b["usual"] < hi)]
    return {"lo": lo, "hi": hi, "w": sum(band), "l": len(band) - sum(band), "share": round(len(band) / len(b["sizes"]), 3)}


def wallet_line(x, variant, k):
    b = x["s"][variant]
    press = round(x["usd"] / b["usual"], 2) if b["usual"] else None
    return {"w": x["w"], "usd": round(x["usd"]), "class": k, "star": k == "hc", "two_way": x["two_way"],
            "press": press, "w_": b["w"], "l_": b["l"],
            "roi": round(b["roi"], 4) if b["roi"] is not None else None,
            "l30_roi": round(b["l30_roi"], 4) if b["l30_roi"] is not None else None, "pnl": b["pnl"], "n": b["n"],
            "usual": round(b["usual"]) if b["usual"] else None, "at_size": at_size(b, press),
            "clv": {"n": b["clv_n"], "beat": b["clv_beat"], "mean": round(b["clv_mean"], 4) if b["clv_mean"] is not None else None}}


def ladder_units(top_press, price):
    """SharpFlow pressBand / pressUnits at a clean price step (step 0), then the dog cap on any market type."""
    units = BAND5_UNITS if top_press >= BAND5 else BAND4_UNITS if top_press >= BAND4 else BAND3_UNITS
    if price is not None and price < DOG_PX:
        units = min(units, DOG_UNITS)
    return units


def lock_shadow(g, ws, cls, variant, kf):
    """SharpFlow's press-ladder gates for one market group, clean-step ladder for units. A shadow record, never a pick."""
    res = {"side": None, "gates": None}
    live = [x for x in ws if cls[x["w"]] != "excluded"]
    for side in sorted({x["side"] for x in ws}):
        mine = [x for x in live if x["side"] == side]
        theirs = [x for x in live if x["side"] != side]
        f, a = sum(x["usd"] for x in mine), sum(x["usd"] for x in theirs)
        proven_for = [x for x in mine if cls[x["w"]] in ("hc", "sharp")]
        proven_vs = [x for x in theirs if cls[x["w"]] in ("hc", "sharp")]
        pressers = [x for x in mine if x["s"][variant]["n"] >= LOCK_PRESSER_N and x["s"][variant]["usual"]
                    and x["usd"] / x["s"][variant]["usual"] >= PRESS]
        share = f / (f + a) if f + a else None
        gates = {"share_for": round(share, 3) if share is not None else None, "proven_for": len(proven_for),
                 "proven_against": len(proven_vs), "pressers_n15": len(pressers)}
        if not (share is not None and share >= LOCK_SHARE and pressers and not proven_vs and proven_for):
            continue
        by_cid = {}                                  # the graded market: the rung carrying the most proven money for the side
        for x in proven_for:
            by_cid[x["cid"]] = by_cid.get(x["cid"], 0) + x["usd"]
        cid = max(by_cid, key=by_cid.get)
        mk = kf["mk"][cid]
        oi = mk["outs"].index(side)
        price = mk["px"][oi] if mk.get("px") and oi < len(mk["px"]) else None
        top = max(x["usd"] / x["s"][variant]["usual"] for x in pressers)
        res = {"side": side, "gates": gates, "cid": cid, "line": mk.get("line"), "outs": mk.get("outs"), "price": price,
               "price_t": mk.get("px_t"), "units_clean_ladder": ladder_units(top, price), "top_press": round(top, 2)}
        break
    return res


def carry_flagged(c, old, now):
    """`flagged` on each shown size and lock: the price and time this side was first flagged, carried from the previous live build
    while the side stays the same. A new side starts at its current price (live builds only; a frozen card only inherits)."""
    for g, m in (c.get("markets") or {}).items():
        for field in ("sf", "lock_shadow"):
            for variant, x in (m.get(field) or {}).items():
                if not x or not x.get("side"):
                    continue
                o = (((old or {}).get("markets") or {}).get(g) or {}).get(field, {}).get(variant) or {}
                if o.get("side") == x["side"] and o.get("cid") == x.get("cid") and o.get("flagged"):
                    x["flagged"] = o["flagged"]              # same side of the same market: keep the first price
                elif now is not None and x.get("price") is not None:
                    x["flagged"] = {"price": x["price"], "t": x.get("price_t") or now}


def vault_join(games, ev, gst):
    """Attach the Vault game (sharp-data key) by Polymarket event slug; report how far the two start times disagree."""
    for g in games:
        if (g.get("pm") or {}).get("slug") == ev:
            return {"key": g.get("key"), "start": g.get("start"), "away": (g.get("away") or {}).get("abbr"),
                    "home": (g.get("home") or {}).get("abbr"),
                    "start_gap_min": round((gst - g["start"]) / 60) if g.get("start") else None,
                    "start_gap_flag": bool(g.get("start")) and abs(gst - g["start"]) > START_GAP_FLAG}
    return None


# ---------- run ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--holders", required=True, help="pm_holders folder (pm-holders-data)")
    ap.add_argument("--ledger", required=True, help="pm_ledger folder (sharp-history)")
    ap.add_argument("--sharp-data", help="sharp-data data.json, for the Vault game key")
    ap.add_argument("--frozen-out", required=True, help="pm_cards folder on pm-holders-data")
    ap.add_argument("--live-out", required=True)
    ap.add_argument("--sports", default="nba,nfl,cfb")
    ap.add_argument("--closes", default="data/pm_closes.json", help="Pendulum Flow closes, for wallet price skill")
    ap.add_argument("--prev-live", help="the last published live.json, to carry the price each shown size was first flagged at")
    a = ap.parse_args()
    import scan_pm_holders as H
    games = []
    if a.sharp_data and os.path.exists(a.sharp_data):
        with open(a.sharp_data) as f:
            games = json.load(f).get("games") or []
    now = int(time.time())
    live, wrote = {"built": now, "context_only": True, "games": []}, []
    pm_closes = {}
    if a.closes and os.path.exists(a.closes):
        with open(a.closes) as f:
            pm_closes = json.load(f)
    prev = {}
    if a.prev_live and os.path.exists(a.prev_live):
        try:
            with open(a.prev_live) as f:
                prev = {(g["ev"], g["gst"]): g for g in (json.load(f).get("games") or [])}
        except (OSError, ValueError, KeyError):
            prev = {}
    for sport in [s for s in a.sports.split(",") if s in H.SERIES]:
        ledger = Ledger.load(a.ledger, sport, a.holders, pm_closes)
        # frozen: one card per keyframe that has none yet
        for kpath in sorted(glob.glob(os.path.join(a.holders, sport, "frozen", "*", "*.json"))):
            rel = os.path.relpath(kpath, os.path.join(a.holders, sport, "frozen"))
            out = os.path.join(a.frozen_out, sport, "frozen", rel)
            if os.path.exists(out):
                continue
            with open(kpath) as f:
                kf = json.load(f)
            c = card(kf, ledger, sport, vault_join(games, kf["ev"], kf["gst"]), frozen=True)
            carry_flagged(c, prev.get((kf["ev"], kf["gst"])), None)
            # one card per game for the test: a postponed game can have several; the earliest cut is the one that counts
            earlier = sorted(x for x in glob.glob(os.path.join(a.frozen_out, sport, "frozen", "*", f"{kf['ev']}@*.json"))
                             if int(x.rsplit("@", 1)[1].split(".")[0]) < kf["gst"])
            if earlier:
                c["test"]["counts"] = False
                c["test"]["why_not"].append("duplicate of an earlier card for this game")
                c["test"]["dup_of"] = os.path.relpath(earlier[0], a.frozen_out)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out + ".tmp", "w") as f:
                json.dump(c, f, separators=(",", ":"))
            os.replace(out + ".tmp", out)
            wrote.append(os.path.relpath(out, a.frozen_out))
        # live: every game not yet at its cut, from the replayed holder logs
        st, _ = H.replay(a.holders, sport, now)
        evs = {(m["ev"], m["gst"]) for m in st.m.values() if m.get("gst") and m.get("mt") in FULL_GAME and now < m["gst"] - CUTOFF_SEC}
        for ev, gst in sorted(evs, key=lambda x: x[1]):
            kf = H.keyframe(st, ev, gst, now)
            if kf:
                c = card(kf, ledger, sport, vault_join(games, ev, gst), frozen=False)
                carry_flagged(c, prev.get((ev, gst)), now)
                live["games"].append(c)
    os.makedirs(os.path.dirname(os.path.abspath(a.live_out)), exist_ok=True)
    with open(a.live_out + ".tmp", "w") as f:
        json.dump(live, f, separators=(",", ":"))
    os.replace(a.live_out + ".tmp", a.live_out)
    print(json.dumps({"frozen_written": wrote, "live_games": len(live["games"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
