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
  - wallets file (--wallets-out): every proven wallet's book and ALL of its open positions, rebuilt every run beside the live cards

Sharp money is context only (CLAUDE.md). The card's `lock_shadow` is the pre-registered rule of docs/sharp-card-prereg.md, recorded so
it can be graded forward; it is never a pick, never feeds Top Reads, SM_GATE or any agree total.

Every rule constant below is the benchmark's, read from its public source (the teardown notes), never invented:
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
          PREMIUM, ELITE). The benchmark's live cut points sit in its private calibration store, so Vault uses the published fallback.
          Recorded per side as `ags`, a shadow field. It does not set the units: those stay the press ladder.
  Vault approximations of the benchmark admission filters (they filter discovery; Vault applies them on the card):
  HEDGER  hedged-at-cutoff share of the wallet's ledger markets >= 25% with >= 8 markets (BOTH_SIDES_REJECT, MIN_SPORTS_MARKETS;
          The benchmark counts both-sides over all closed sports positions, early exits included)
  CHURN   all-time (all categories, /v2/user-stats) volume / realized PnL > 100 (CHURN_VOL_PNL; the benchmark reads the sports board;
          its ROI < 2% clause is implied by vol/PnL > 100)

Point-in-time rules
  - Wallet stats use only ledger rows with settled_at < cut. User-stats snapshots are taken from the latest one dated <= cut.
  - A wallet first selected into the ledger universe after the cut is untracked on that card (no record, unproven), so a wallet
    picked because it won this game can never count.
  - A frozen card stores when it was built; the pre-registration counts only cards built before game start on a ledger run that
    finished before the cut (`test.counts`).
  - Every stat is computed twice: from all rows (the benchmark's way, which includes `backfill` rows of wallets chosen with hindsight)
    and from `forward` rows only. Both are on the card; the pre-registration names which one is primary.
  - Hedged legs (a wallet on both outcomes at the cutoff) are left out of records. SPLIT-funded rows count in W/L, never in dollars.
  - Money on a side is shares x the market price at the cut (the keyframe's `usd_at_mark`), labelled as mark value, not cost.

The `sf` size (scripts/sf_rungs.py) also reads Pinnacle's moves from Vault's book tape (--book-tape, default data/book_tape, on main),
only rows at or before the cut, and ledger-wide 30-day market books (TOP3-PICK ranks, GAP-LEAD) and season tier-5 reads.

usage: build_side_cards.py --holders DIR --ledger DIR [--sharp-data data.json] --frozen-out DIR --live-out FILE [--sports nba,nfl,cfb]
       [--book-tape DIR] [--prev-wallets FILE] [--now EPOCH] [--wallets-only]

Wallets file V2 (docs/sharps-v2-accounts-spec.md, docs/side-cards.md "Wallets file"): additive fields only, every V1 key keeps its name, shape and
value. `--prev-wallets` is the last published wallets.json (carries `retained` forward); `--now` pins the build time (reproducible runs);
`--wallets-only` skips the frozen and live cards (a local wallets run).
"""
import argparse, bisect, datetime as dt, glob, json, math, os, re, statistics, sys, time
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pm_ledger import CUTOFF_SEC, FULL_GAME  # noqa: E402
import sf_rungs as SF  # noqa: E402
import sf_signals as SIG  # noqa: E402
import sf_publish as PUB  # noqa: E402
import pm_clv_tiers as CT  # noqa: E402
import sf_tiers as TIERS  # noqa: E402

PROVEN_N, PROVEN_WR, PROVEN_ROI = 6, 0.55, 0.03
FLOOR_USD = 250
FOLLOW_FLOOR = {"cbb": 100}          # the wallets file (Following page) lists smaller CBB positions: thin markets, small bettors. Cards keep FLOOR_USD.
SCORECARD_FILES = {"nfl": "pm_wallets.json", "cfb": "pm_wallets_cfb.json", "nba": "pm_wallets_nba.json", "cbb": "pm_wallets_cbb.json"}
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
DATE_RE = re.compile(r"-(\d{4}-\d{2}-\d{2})$")
START_GAP_FLAG = 10 * 60                  # Polymarket and Vault start times more than 10 min apart (prereg "known limits")
VERSION = 1
WALLETS_VERSION = 2                        # the wallets file only (docs/sharps-v2-accounts-spec.md); cards keep VERSION
SINCE_DAYS, RETAIN_DAYS = 60, 60           # window of the since.json lists; days a wallet that left the list stays under `retained`
WALLETS_MAX_KB, WALLETS_NEW_MAX_KB = 1350, 400   # size budget (thousands of bytes, as the spec counts the old 946 KB file) of the wallets file and of the V2 fields in it (spec section 2)
SINCE_FILE = "since.json"                  # the dated settled list per wallet, published beside wallets.json (kept out of it for the size budget, spec section 2 K)
BUDGET_EXIT = 3                            # exit code of a build whose wallets file is over its size budget
CT_ZONE = "America/Chicago"
HEX_NAME = re.compile(r"^0x[0-9a-fA-F]{20,}")     # following.js shortName: a name that is only a wallet address
V2_TIER = {"sharp": "beats", "mid": "even", "dull": "loses", "thin": "few"}     # pm_clv_tiers tier -> V2 tier (no new threshold)
# every key V2 adds, so a reader (and the back-compat test) can strip them and get the V1 file
V2_TOP_KEYS = ("v2_fields", "since_from", "since_file", "retained")
V2_WALLET_KEYS = ("flat_roi", "fwd", "first_seen", "last_settled", "n30_games", "usual_med", "sc_sport", "sc_n", "name_disp", "name_src",
                  "exp_w", "luck_p", "v2")
V2_POSITION_KEYS = ("side_usd", "side_rungs", "side_press", "px_age_min")
V2_RK_KEYS = ("post", "sd")
VARIANTS = ("all", "fwd")                  # plus "sfx" when the benchmark's exclusion list is given (--sf-excluded)
SIZE_BANDS = (0.0, 0.75, 1.5, 3.0)        # size vs usual stake bands for the "at this size" record (below 0.75x, 0.75 to 1.5x, ...)
CLOSE_STALE = 30 * 60                     # a keyframe price older than this at the cut is not a close (prereg "unpriced" rule)


def event_of(slug):
    m = EVENT_RE.match(slug or "")
    return m.group(1) if m else slug


def ev_date(ev):
    """The game date in an event slug (nba-bkn-nop-2026-11-11 -> 2026-11-11), or None."""
    m = DATE_RE.search(ev or "")
    return m.group(1) if m else None


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
    def __init__(self, rows, markets, first_seen, user_stats, run_at=None, closes=None, first_seen_pub=None):
        self.by_w = {}
        for r in rows:
            self.by_w.setdefault(r["w"], []).append(r)
        for rs in self.by_w.values():
            rs.sort(key=lambda r: r["settled_at"])
        self.keys = {w: [r["settled_at"] for r in rs] for w, rs in self.by_w.items()}
        self.markets = markets
        self.first_seen = first_seen
        self.first_seen_pub = first_seen if first_seen_pub is None else first_seen_pub   # the date the wallets file shows (see load)
        self.us = {}
        for s in user_stats:
            self.us.setdefault(s["w"], []).append(s)
        for v in self.us.values():
            v.sort(key=lambda s: s.get("at") or 0)
        self.run_at = run_at
        self.closes = closes or {}
        self.sf_excluded = set()                     # The benchmark's published exclusion list, for the `sfx` variant
        self._wide, self._mb, self._t5 = {}, {}, {}   # ledger-wide reads for sf_rungs (TOP3-PICK, GAP-LEAD, season tier 5)
        self._clv_obs, self._clv_fit = None, {}       # CLV tiers (scripts/pm_clv_tiers.py), one fit per cut

    @classmethod
    def load(cls, root, sport, holders=None, pm_closes=None, follow=False):
        """follow=True also loads the follow-only wallets (follow_only.json: CBB specialists the Following page lists). Their rows
        and dates stay out of every card ledger, so the registered tests (docs/sharp-card-prereg*.md) read exactly the wallets they
        were registered on. Only the wallets file uses a follow ledger."""
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
        fs = j(os.path.join(root, "first_seen.json"), {})
        pub = None
        if follow:
            fo = j(os.path.join(root, "follow_only.json"), {})
            # The date the wallets file publishes is the EARLIEST of the two files for a wallet in both: build_pm_ledger stamped `src`
            # forward from the follow-only date it had at the time, so a later first_seen.json date would put forward rows before the
            # published date. `first_seen` itself (what stats() and the cuts read) keeps the registered date winning, so no V1 number moves.
            pub = {**fo, **{w: min(fo.get(w, t), t) for w, t in fs.items()}}
            fs = {**fo, **fs}
        else:                                        # a follow-only wallet's rows never reach a card ledger
            rows = [r for r in rows if r["w"] in fs]
        return cls(rows, markets, fs, us,
                   (j(os.path.join(root, "summary.json"), {}) or {}).get("run_at"), load_closes(holders, sport, markets, pm_closes),
                   first_seen_pub=pub)

    def clv_tiers(self, asof):
        """{wallet: {n, mean, post, sd, p, tier}} as of `asof`: games that started before it, stored closes only (docs/pm-clv-tiers.md).
        Empty when too few wallets have a close yet. Context only: it never changes a size, a lock or a count."""
        if self._clv_obs is None:
            self._clv_obs = CT.observations([r for rs in self.by_w.values() for r in rs], self.markets, self.closes, event_of)
        if asof not in self._clv_fit:
            self._clv_fit[asof] = CT.fit(self._clv_obs, asof)["wallets"]
        return self._clv_fit[asof]

    def stats(self, w, asof):
        """The wallet's sport book as of `asof` (rows settled strictly before it), all rows and forward rows."""
        fs = self.first_seen.get(w)
        if fs is None or fs > asof:                  # not in the universe at the cut: untracked, whatever its later record
            empty = book([], asof, self.markets)
            return {"tracked": False, "markets": 0, "hedged_share": 0.0, "all": empty, "fwd": empty, "sfx": empty, "churn": None,
                    "excluded": None, "excluded_sfx": "benchmark" if w in self.sf_excluded else None}
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
        # variant `sfx`: the same all-rows book, but the benchmark's own published exclusion list (market makers and traders) instead of
        # Vault's hedger and churn approximations, which the benchmark applies only when it discovers new wallets
        out["all"]["_key"], out["fwd"]["_key"] = (w, "all", len(rs)), (w, "fwd", len(rs))
        out["sfx"] = out["all"]
        out["excluded_sfx"] = "benchmark" if w in self.sf_excluded else None
        return out


    # ---- ledger-wide reads for the benchmark's market rules (scripts/sf_rungs.py) ----

    def _wide_positions(self, variant):
        """Every wallet's positions (non-hedged rows; `fwd` forward rows only):
        (settled_at, game date, market group, stake, pnl, entry price, won, split, result)."""
        key = "fwd" if variant == "fwd" else "all"
        if key not in self._wide:
            out = {}
            for w, rs in self.by_w.items():
                use = [r for r in rs if not r.get("hedged") and (key == "all" or r.get("src") == "forward")]
                out[w] = [(p["settled_at"], ev_date(p["ev"]), GROUP.get(p["mt"]), p["stake"], p["pnl"], p["px"], p["res"] == "win",
                           p["split"], p["res"]) for p in positions(use, self.markets)]
            self._wide[key] = out
        return self._wide[key]

    def population(self, variant, cut):
        """The wallets in the universe at the cut (`sfx` leaves the benchmark's excluded wallets out)."""
        return [w for w in self.by_w if self.first_seen.get(w) is not None and self.first_seen[w] <= cut
                and not (variant == "sfx" and w in self.sf_excluded)]

    def market_books(self, variant, pick_date, cut):
        """GAP-LEAD books and TOP3-PICK ranks (gapLeadRescue.js buildGapLeadBooks, top3PickRung.js buildTop3PickRanks): per wallet x
        market group, positions dated in the 30 days before the pick date and settled before the cut, pushes and zero PnL left out,
        5 or more -> dollar ROI in percent. A group ranks only with 4 or more such wallets; rank 1 is the best ROI. SPLIT-funded
        positions are left out (no real dollars). Returns ({(wallet, group): {n, dol}}, {(wallet, group): rank})."""
        k = (variant, pick_date, cut)
        if k not in self._mb:
            since = (dt.date.fromisoformat(pick_date) - dt.timedelta(days=SF.L30_DAYS)).isoformat()
            wide, acc = self._wide_positions(variant), {}
            for w in self.population(variant, cut):
                for t, d, g, stake, pnl, px, won, split, res in wide.get(w, ()):
                    if t >= cut or not d or not since <= d < pick_date or g is None or split or res == "push" or not stake > 0 or abs(pnl) <= 1e-9:
                        continue
                    a = acc.setdefault((w, g), [0, 0.0, 0.0])
                    a[0] += 1; a[1] += stake; a[2] += pnl
            gap, boards, rank = {}, {}, {}
            for (w, g), (n, inv, pnl) in acc.items():
                if n >= SF.GAP_MIN_N and inv > 0:
                    gap[(w, g)] = {"n": n, "dol": round(100 * pnl / inv, 2)}
                    boards.setdefault(g, []).append((w, n, 100 * pnl / inv))
            for g, people in boards.items():
                if len(people) >= SF.TOP3_MIN_BOARD:
                    for i, (w, _, _) in enumerate(sorted(people, key=lambda x: (-x[2], -x[1], x[0]))):
                        rank[(w, g)] = i + 1
            self._mb[k] = (gap, rank)
        return self._mb[k]

    def t5(self, variant, pick_date, cut, w):
        """Season tier 5 on the pick date (t5LeadPolicy.js t5MorningRead): the wallet's positions priced .02 to .98 with a non-zero
        PnL, dated on or after the sport's season start (the first date after the last 21-day gap, over every wallet's dates) and
        before the pick date, read as tier 5, ON, n >= 10 and 15+ days old. Returns {q, held}: held is t5HoldDays, the days it has
        qualified without a break (walked back one morning at a time to the season start)."""
        k = (variant, pick_date, cut)
        if k not in self._t5:
            wide, rows = self._wide_positions(variant), {}
            for x in self.population(variant, cut):
                rs = [(d, px, won) for t, d, g, stake, pnl, px, won, split, res in wide.get(x, ())
                      if t < cut and d and d < pick_date and px is not None and SF.T5_PRICE_LO < px < SF.T5_PRICE_HI
                      and stake > 0 and abs(pnl) > 1e-9]
                if rs:
                    rows[x] = rs
            self._t5[k] = (SF.season_start([d for rs in rows.values() for d, _, _ in rs]), rows, {})
        start, rows, q = self._t5[k]
        if w not in q:
            held = SF.t5_hold(rows.get(w, []), pick_date, start)
            q[w] = {"q": held is not None, "held": held}
        return q[w]


def positions(rows, markets, closes=None):
    """Ledger rows -> the benchmark positions: one per game x market type x side. Rungs of one side are summed; the result is the sign
    of the summed PnL; a position touched by a SPLIT row is kept out of dollar totals."""
    pos = {}
    for r in rows:
        mk = markets.get(r["cid"]) or {}
        outs = mk.get("outs") or []
        side = outs[r["oi"]] if r["oi"] < len(outs) else r["oi"]
        key = (event_of(mk.get("slug")) or r["cid"], r.get("mt"), side)
        p = pos.setdefault(key, {"ev": key[0], "stake": 0.0, "pnl": 0.0, "settled_at": 0, "split": False, "pxs": 0.0, "mt": r.get("mt"),
                                 "clv_s": 0.0, "clv_st": 0.0, "first": None})
        if r.get("first") is not None:               # the position's first fill: the earliest `first` over its rungs (V2 since.json)
            p["first"] = r["first"] if p["first"] is None else min(p["first"], r["first"])
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


def luck(pairs):
    """How often a record this good happens by luck: P(wins >= the wallet's wins) if every bet won exactly as often as its own entry
    price says (a Polymarket price is the market's chance, so a -150 favourite is a 60% coin, not a 50% one). Poisson-binomial, exact.
    `pairs` is [(entry price, won)]. None under 2 bets."""
    ps = [(px, won) for px, won in pairs if px is not None and 0 < px < 1]
    if len(ps) < 2:
        return None
    dist = [1.0]
    for px, _ in ps:
        nxt = [0.0] * (len(dist) + 1)
        for k, v in enumerate(dist):
            nxt[k] += v * (1 - px)
            nxt[k + 1] += v * px
        dist = nxt
    wins = sum(1 for _, won in ps if won)
    return {"p": max(0.0, min(1.0, sum(dist[wins:]))), "exp_w": round(sum(px for px, _ in ps), 2), "n": len(ps)}


# entry-price bands for the sheet's "at these odds" cut (American odds at the same prices): [key, label, low price, high price)
ODDS_BANDS = [("dd", "+200 or longer", 0.0, 1 / 3), ("d2", "+150 to +199", 1 / 3, 0.4), ("d1", "+100 to +149", 0.4, 0.5),
              ("f1", "-100 to -149", 0.5, 0.6), ("f2", "-150 to -199", 0.6, 2 / 3), ("ff", "-200 or shorter", 2 / 3, 1.01)]
DIVE_COLS = ["w", "l", "roi", "clv_n", "clv_beat", "luck"]   # one dive cell: [wins, losses, dollar ROI, bets with a close, beat it, luck]


def dive(ps, usual, odds=False):
    """The wallet deep dive, from its positions settled before the cut: record, dollar ROI, closing-line beat rate and luck, split by
    market group (its lane), by favourite or underdog (entry price at or above 50 cents is a favourite) and by size vs its usual stake.
    Context only: shown in the wallet sheet, never read by the size, the lock or any record."""
    dec = [p for p in ps if p["res"] in ("win", "loss")]

    def cell(xs):
        if not xs:
            return None
        cash = [p for p in xs if not p["split"] and p["stake"] > 0]
        st, pnl = sum(p["stake"] for p in cash), sum(p["pnl"] for p in cash)
        cl = [p["clv"] for p in xs if p["clv"] is not None]
        lk = luck([(p["px"], p["res"] == "win") for p in xs])
        return [sum(p["res"] == "win" for p in xs), sum(p["res"] == "loss" for p in xs), round(pnl / st, 4) if st > 0 else None,
                len(cl), sum(1 for c in cl if c > 0), float("%.3g" % lk["p"]) if lk else None]
    lk = luck([(p["px"], p["res"] == "win") for p in dec])
    out = {"cols": DIVE_COLS, "exp_w": lk["exp_w"] if lk else None, "all": cell(dec),
           "lane": {g: cell([p for p in dec if GROUP.get(p["mt"]) == g]) for g in ("ml", "spread", "total")},
           "fav": cell([p for p in dec if p["px"] is not None and p["px"] >= 0.5]),
           "dog": cell([p for p in dec if p["px"] is not None and p["px"] < 0.5])}
    if usual:
        sz = [p for p in dec if not p["split"] and p["stake"] > 0]
        out["size"] = {"small": cell([p for p in sz if p["stake"] / usual < 0.75]),
                       "usual": cell([p for p in sz if 0.75 <= p["stake"] / usual < PRESS]),
                       "big": cell([p for p in sz if p["stake"] / usual >= PRESS])}
    if odds:                                         # the sheet only: bands by entry price, one cell each (None when no bets)
        out["odds"] = {k: cell([p for p in dec if p["px"] is not None and lo <= p["px"] < hi]) for k, _, lo, hi in ODDS_BANDS}
    return out


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
         # decided positions: [settled_at, entry price, won, market type, stake, pnl, game date, split] (the sf_rungs trust, market
         # book, last-10 and blend reads)
         "bets": sorted(([p["settled_at"], round(p["px"], 4), p["res"] == "win", p["mt"], round(p["stake"], 2), round(p["pnl"], 2),
                          ev_date(p["ev"]), p["split"]] for p in ps if p["res"] != "push" and p["px"]), key=lambda b: b[0]),
         "legs": sorted(([r["settled_at"], r["res"]] for r in legs.values()), reverse=True)[:LAST_N],
         # price skill: positions with a stored close, and how many were bought below it (the benchmark's "beat the closing line")
         "clv_n": sum(1 for p in ps if p["clv"] is not None),
         "clv_beat": sum(1 for p in ps if p["clv"] is not None and p["clv"] > 0),
         "clv_mean": (sum(p["clv"] for p in ps if p["clv"] is not None) / sum(1 for p in ps if p["clv"] is not None))
         if any(p["clv"] is not None for p in ps) else None,
         "sizes": [[p["stake"], p["res"] == "win"] for p in cash if p["res"] in ("win", "loss") and p["stake"] > 0]}
    b["asof"] = asof
    b["_ps"] = ps                                    # kept for the deep dive, built only for the wallets a card lists (wallet_line)
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

def holder_groups(kf, ledger):
    """The holders of one keyframe, per market group, exactly as the card builds them: every position of $FLOOR_USD or more, a two-way
    wallet collapsed to its larger side, balanced dust dropped, each holder carrying its ledger book `s` and CLV tier `rk` as of the cut.
    -> (groups {ml|spread|total: [{w, side, usd, cid, two_way, s, rk}]}, dust count, best {(group, wallet, side): (usd, cid)}).
    Shared by card() and scripts/sharp_agree.py so the two can never disagree on who holds a side."""
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
        if usd >= FLOOR_USD:                         # the floor applies to each position, as the benchmark's board does
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
    rk = ledger.clv_tiers(cut)
    for ws_ in groups.values():
        for x in ws_:
            x["rk"] = rk.get(x["w"])
    return groups, dust, best


def card(kf, ledger, sport, vault=None, frozen=True, tape=None):
    """One game's card from a keyframe (step 2) and the ledger as of its cut."""
    groups, dust, best = holder_groups(kf, ledger)
    cut = kf["cut"]
    rk = ledger.clv_tiers(cut)                       # cached per cut; the tier plays below read it
    built = int(time.time())
    out = {"v": VERSION, "sport": sport, "ev": kf["ev"], "gst": kf["gst"], "cut": cut, "frozen": frozen, "sf_excluded_n": len(ledger.sf_excluded), "pop": len(ledger.population("all", cut)),
           "built": built, "keyframe_written": kf.get("written"), "ledger_run_at": ledger.run_at,
           "money_basis": "shares x market price at the cut", "context_only": True,
           "coverage": {"markets_read": len(kf["mk"]), "markets_missed": len(kf.get("miss") or []),
                        "late_reads": kf.get("late_reads", 0), "two_way_dust_dropped": dust,
                        "max_read_lag_s": max([m["frz_lag"] for m in kf["mk"].values()] or [0])},
           "vault": vault, "markets": {}}
    if frozen:
        why = []
        if sport not in REGISTERED_SPORTS:
            why.append("sport not in a registered test")
        elif cut < REGISTERED_FROM.get(sport, 0):
            why.append("cut before this sport's registration")
        if built > kf["gst"]:
            why.append("built after game start")
        if not ledger.run_at or ledger.run_at >= cut:
            why.append("ledger run not before the cut")
        out["test"] = {"counts": not why, "why_not": why}
    for g, ws in groups.items():
        sides_all = sorted({side for (gg, _, side) in best if gg == g})
        out["markets"][g] = {"sides": {}, "lock_shadow": {}}
        for variant in VARIANTS + (("sfx",) if ledger.sf_excluded else ()):
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
                    # tracked wallets that are not proven yet (the benchmark's "secondary"), with whatever record they have
                    "unproven_list": [wallet_line(x, variant, "unproven") for x in
                                      sorted((x for x in mine if cls[x["w"]] == "unproven" and x["s"]["tracked"]),
                                             key=lambda x: -x["usd"])[:SHOW_PROVEN]],
                    "counts": {k: sum(1 for x in mine if cls[x["w"]] == k) for k in ("hc", "sharp", "unproven", "loser", "excluded")},
                }
                side_out["ags"] = ags_side(side, ws, cls, variant)
                side_out["rk"] = rk_side(mine)
                if variant == "sfx":                     # a shadow: money and score only, the wallet lists are the `all` ones
                    side_out.update({"list": [], "losers": [], "unproven_list": []})
                p = side_out["proven"]
                p["win_pct"] = round(100 * p["w"] / (p["w"] + p["l"]), 1) if p["w"] + p["l"] else None
                out["markets"][g]["sides"].setdefault(side, {})[variant] = side_out
            out["markets"][g]["lock_shadow"][variant] = lock_shadow(g, ws, cls, variant, kf)
            if variant == "all" and sport in TIERS.TIER_SPORTS and cut >= TIERS.REGISTERED_AT:    # docs/sharp-tier-prereg.md: shadows only
                out["markets"][g]["tp"] = TIERS.tier_plays(ws, cls, rk, ledger.first_seen, kf, cut)
            out["markets"][g].setdefault("sf", {})[variant] = sf_market(g, ws, cls, variant, kf, sides_all, out["markets"][g]["sides"],
                                                                        ledger, sport, tape, vault)
        for variant in ("all", "fwd"):                # the publish-mute shadow of the shown size (scripts/sf_publish.py)
            out["markets"][g].setdefault("pub", {})[variant] = PUB.pub_play(out["markets"][g], variant)
            sg = card_signals(out, g, variant, tape)               # the limit and price reads of the shown side (scripts/sf_signals.py)
            if sg is not None:
                out["markets"][g]["sf"][variant]["signals"] = sg
    return out


def ags_quality(x, variant, k):
    """The benchmark agsV12WalletQuality. Only a proven (CONFIRMED) wallet scores; FLAT is no longer assigned (whitelistTier.js)."""
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
    """The benchmark's AGS-Unified v12 score for one side: (mean quality for - mean quality against) / (for + against + 0.5).
    Every tracked wallet with a book counts in its side's mean (a wallet that is not proven counts as 0, as in aggregateSideV12);
    excluded wallets and wallets with no book are left out. The tier uses the benchmark's fallback cut points, which were fitted on
    The benchmark's picks, not Vault's: Vault has no calibration of its own. A shadow field: it never sets a size or a pick."""
    pool = [x for x in ws if cls[x["w"]] != "excluded" and x["s"][variant]["n"] > 0]
    f = [ags_quality(x, variant, cls[x["w"]]) for x in pool if x["side"] == side]
    a = [ags_quality(x, variant, cls[x["w"]]) for x in pool if x["side"] != side]
    if not f and not a:
        return None
    fm, am = (sum(f) / len(f) if f else 0.0), (sum(a) / len(a) if a else 0.0)
    score = 0.0 if fm == 0 and am == 0 else (fm - am) / (fm + am + 0.5)
    return {"score": round(score, 3), "tier": ags_tier(score), "for_mean": round(fm, 2), "against_mean": round(am, 2),
            "for_n": len(f), "against_n": len(a), "contributors": sum(1 for q in f + a if q > 0)}


def sf_market(g, ws, cls, variant, kf, sides, sides_out, ledger=None, sport=None, tape=None, vault=None):
    """The benchmark's stake policy (scripts/sf_rungs.py, a replica with the gaps it lists) for this market group. One side at most is staked:
    the side with the most units, ties to the higher AGS score. A shadow field; it never feeds the lock, Top Reads or an agree total.
    Steam per side is read from Vault's Pinnacle tape (`tape`), rows at or before the cut only."""
    cut = kf["cut"]
    pick = ev_date(event_of(kf["ev"]))
    pool = [x for x in ws if cls[x["w"]] != "excluded"]
    trust_cache = {}

    def trust(w, market_only):
        k = (w, market_only)
        if k not in trust_cache:
            # walletTrustStatus.js dates a bet by its game date (bets[6]); a bet with no dated slug falls back to its settlement day
            bets = [(b[6] or SF._day(b[0]).isoformat(), b[1], b[2]) for b in x_bets[w] if not market_only or GROUP.get(b[3]) == g]
            t = SF.trust_state_dated(bets, asof_day) if bets else None
            if t and market_only:                    # pressLadderOverlay.js sportBook: the market record carries the sport book's age
                sport_t = trust(w, False)
                t = dict(t, age=sport_t["age"]) if sport_t else t
            trust_cache[k] = t
        return trust_cache[k]

    x_bets = {x["w"]: x["s"][variant]["bets"] for x in pool}
    asof_day = pick or SF._day(cut).isoformat()
    gap, rank = ledger.market_books(variant, pick, cut) if ledger is not None and pick else ({}, {})
    names = team_names(vault, kf["ev"], sport)
    norms = side_norms(g, sides, names)
    game, how = tape.game(sport, vault, kf["ev"], kf["gst"]) if tape is not None else ([], "no_tape")
    order = sorted(sides, key=lambda s: ({"away": 0, "over": 0, "home": 1, "under": 1}.get(norms.get(s), 2), s))
    ctx, info = {}, {}
    for side in sides:
        rows = []
        for x in pool:
            b = x["s"][variant]
            bets = b["bets"]
            streak = 0
            for bet in reversed(bets):
                if bet[2]:
                    break
                streak += 1
            mk_b = [bet for bet in bets if GROUP.get(bet[3]) == g]
            last10 = [bet[2] for bet in bets[-10:]]
            rows.append({"w": x["w"], "dir": "FOR" if x["side"] == side else "AG", "invested": x["usd"],
                         "ratio": x["usd"] / b["usual"] if b["usual"] else None, "n": b["n"], "wins": b["w"],
                         "wr": b["wr"] * 100 if b["wr"] is not None else None, "door2": b["proven"], "streak": streak,
                         "s_n": len(bets), "s_wins": sum(1 for bet in bets if bet[2]), "mkt_n": len(mk_b), "mkt_wins": sum(1 for bet in mk_b if bet[2]),
                         "mkt_wr": 100 * sum(1 for bet in mk_b if bet[2]) / len(mk_b) if mk_b else None,
                         "l10": (sum(last10), len(last10) - sum(last10)) if last10 else None,
                         "trust": trust(x["w"], False), "trust_mkt": trust(x["w"], True),
                         "gap": gap.get((x["w"], g)), "rank": rank.get((x["w"], g)),
                         "t5": ledger.t5(variant, pick, cut, x["w"]) if ledger is not None and pick and x["s"]["tracked"] else None})
        mine = [x for x in pool if x["side"] == side]
        cid = max(mine, key=lambda x: x["usd"])["cid"] if mine else None
        mk = kf["mk"].get(cid) if cid else None
        px, line = None, None
        if mk and side in (mk.get("outs") or []):
            oi = mk["outs"].index(side)
            px = mk["px"][oi] if mk.get("px") and oi < len(mk["px"]) else None
            if mk.get("line") is not None:            # Polymarket's spread line is outcomes[0]'s; the other side has the opposite sign
                line = mk["line"] if g == "total" or oi == 0 else -mk["line"]
        norm = norms.get(side)
        if px is None and g == "ml" and game and norm:   # no Polymarket ticket: the benchmark prices a moneyline from Pinnacle (mlOddsFromMeta)
            px = SF.implied_of(pinnacle_price(game, g, norm, cut))
        if not game:
            st = {"on": None, "why": how}
        elif not norm:
            st = {"on": None, "why": "side_not_mapped_to_home_away"}
        else:
            st = SF.ladder_steam(game, g, norm, line, cut, kf["gst"])
        ags = (sides_out.get(side, {}).get(variant) or {}).get("ags")
        ctx[side] = {"rows": rows, "implied": px, "ags": ags["score"] if ags else None, "steam": st["on"], "juice": st.get("juice"),
                     "pinn_odds": pinnacle_price(game, g, norm, cut, line) if game and norm else None}
        info[side] = {"steam": st, "line": line}
    res = SF.stake_market(ctx, g, pick, order, sport)
    missing = list(SF.MISSING) + ["steam unknown for %s (%s)" % (s, info[s]["steam"].get("why")) for s in order if info[s]["steam"]["on"] is None]
    summary = {s: {"units": res[s]["units"], "rung": res[s]["rung"], "reason": res[s]["reason"], "steam": info[s]["steam"]["on"],
                   "juice": info[s]["steam"].get("juice"), "t5_seat": res[s].get("t5_seat"), "chain": res[s].get("chain") or []}
               for s in order}
    staked = [(r["units"], ctx[s]["ags"] or 0, s) for s, r in res.items() if r["units"] > 0]
    if not staked:
        return {"side": None, "units": 0, "rung": None, "reason": min((r["reason"] for r in res.values()), default="no_wallets"), "missing": missing,
                "pick_date": pick, "sides": summary}
    _, _, side = max(staked)
    r = res[side]
    cid = max((x for x in pool if x["side"] == side), key=lambda x: x["usd"])["cid"] if any(x["side"] == side for x in pool) else None
    mk = kf["mk"].get(cid) or {}
    e = r.get("edge")
    return {"side": side, "units": r["units"], "rung": r["rung"], "reason": r["reason"], "price": ctx[side]["implied"], "price_t": mk.get("px_t"),
            "line": mk.get("line"), "outs": mk.get("outs"), "cid": cid, "missing": missing, "pick_date": pick, "sides": summary,
            "chain": r.get("chain") or [], "press_edge": round(e, 1) if e is not None else None, "blend_edge": r.get("blend"),
            "steam": compact_steam(info[side]["steam"]), "pinnacle_odds": ctx[side]["pinn_odds"], "t5_seat": r.get("t5_seat"),
            "top3_price_src": (r.get("top3") or {}).get("price_src")}


def compact_steam(st):
    keep = ("on", "cut_on", "juice", "lock_juice", "lock_t", "tier", "last_hour_pct", "since_open_pct", "open", "hour", "now", "short_session", "line_open", "line_hour", "line_now",
            "since_open_pts", "last_hour_pts", "rows", "why")
    return {k: st[k] for k in keep if k in st}


def signed_line(mk, g, oi):
    """The line as it reads for the side held. Polymarket stores a spread's line for outcomes[0]; the other side has the opposite sign
    (Texans -13.5 means Colts +13.5). A total has one line for both sides, and a moneyline has none."""
    line = mk.get("line")
    if line is None or g == "total" or oi == 0:
        return line
    return -line


def pinnacle_price(game, g, norm, cut, line=None):
    """Pinnacle's price for the side at the cut, from the last tape row at or before it. On a spread or total it is the main line's
    price, and None when the side's ticket line is not Pinnacle's main at the cut (the tape keeps no alt lines)."""
    key = {"ml": "ml", "spread": "sp", "total": "tot"}[g]
    rows = [r for r in game if r.get(key) and r["t"] <= cut]
    if not rows:
        return None
    v = max(rows, key=lambda r: r["t"])[key]
    away = norm in ("away", "under")
    if g != "ml":
        main = (-v[0] if away else v[0]) if g == "spread" else v[0]
        if line is None or abs(main - line) > SF.PIN_LINE_EPS:
            return None
    return (v[0] if away else v[1]) if g == "ml" else (v[2] if away else v[1])


# NBA nicknames by abbreviation, the same table as sharp-money/side-cards.js TEAMS (Polymarket's NBA outcome names)
NBA_NICK = {"ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets", "CHI": "Bulls", "CLE": "Cavaliers", "DAL": "Mavericks",
            "DEN": "Nuggets", "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers", "LAC": "Clippers", "LAL": "Lakers",
            "MEM": "Grizzlies", "MIA": "Heat", "MIL": "Bucks", "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks", "OKC": "Thunder",
            "ORL": "Magic", "PHI": "76ers", "PHX": "Suns", "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors",
            "UTA": "Jazz", "WAS": "Wizards"}
NFL_ALIAS = {"WSH": "WAS", "LA": "LAR", "JAC": "JAX", "LVR": "LV", "OAK": "LV"}   # scripts/book_tape.py ALIAS
# Sports with a registered side-card test: NBA, NFL, CFB (docs/sharp-card-prereg.md) and CBB (docs/sharp-card-prereg-cbb.md, approved
# 2026-11-12). A frozen card of any other sport is built and graded but never counts ("sport not in a registered test").
REGISTERED_SPORTS = ("nba", "nfl", "cfb", "cbb")
FOLLOW_SPORTS = ("cbb",)             # sports whose wallets file also lists follow-only wallets (scripts/build_pm_ledger.py)
# CBB counts only cards whose cut is at or after its registration: 2026-11-13 00:00 UTC (6:00 PM CT, Nov 12), set after the approval
# commit. Earlier CBB cards stay `counts: false`.
REGISTERED_FROM = {"cbb": 1794528000}
TAPE_START_GAP = 12 * 3600                    # a tape game with the same two teams starting within 12 h of the Polymarket start


def slug_teams(ev, sport):
    """(AWAY, HOME) abbreviations from an NBA event slug (nba-bkn-nop-2026-11-11), only when both are in the NBA table."""
    parts = (ev or "").split("-")
    if sport != "nba" or len(parts) < 3:
        return None
    a, h = parts[1].upper(), parts[2].upper()
    return (a, h) if a in NBA_NICK and h in NBA_NICK else None


def team_names(vault, ev, sport):
    """{away: [names], home: [names]} for mapping outcome names to home / away: Vault's game names, else (NBA) the slug's teams."""
    if vault and vault.get("teams"):
        return vault["teams"]
    st = slug_teams(ev, sport)
    return {"away": [NBA_NICK[st[0]]], "home": [NBA_NICK[st[1]]]} if st else None


def _name_match(n, x):
    x = (x or "").strip().lower()
    return bool(x) and (n == x or x.startswith(n + " ") or x.endswith(" " + n))


def side_norms(g, sides, names):
    """Outcome name -> home | away | over | under. A team name maps only when it matches exactly one of the two teams (equal to a
    team's full or short name, or its leading or trailing words) and the two outcomes land on different teams; otherwise None."""
    if g == "total":
        return {s: {"over": "over", "under": "under"}.get(s.strip().lower()) for s in sides}
    out = {}
    for s in sides:
        n = s.strip().lower()
        hits = [k for k in ("away", "home") if any(_name_match(n, x) for x in (names or {}).get(k) or [])]
        out[s] = hits[0] if len(hits) == 1 else None
    vals = [v for v in out.values() if v]
    if len(vals) != len(set(vals)):
        return {s: None for s in sides}
    return out


class BookTape:
    """Pinnacle rows of data/book_tape/<sport>/<YYYY-MM>.jsonl (written by scripts/sharp_tape.py for NBA and CFB, scripts/book_tape.py
    for the NFL). Backfill rows carry no prices and are not read."""

    def __init__(self, root):
        self.root, self.idx = root, {}

    def _load(self, sport):
        if sport not in self.idx:
            gk, teams = {}, {}
            for fn in sorted(glob.glob(os.path.join(self.root or "", sport, "[0-9][0-9][0-9][0-9]-[0-9][0-9].jsonl"))):
                with open(fn) as f:
                    for line in f:
                        try:
                            r = json.loads(line)
                        except ValueError:
                            continue
                        if r.get("book") != "Pinnacle" or r.get("t") is None or r.get("bf"):
                            continue
                        c = {"t": r["t"], "ml": r.get("ml"), "sp": r.get("sp"), "tot": r.get("tot"), "start": r.get("start"), "lim": r.get("lim")}
                        if r.get("gk"):
                            gk.setdefault(r["gk"], []).append(c)
                        a, h = NFL_ALIAS.get(r.get("away"), r.get("away")), NFL_ALIAS.get(r.get("home"), r.get("home"))
                        teams.setdefault((a, h), []).append(c)
            self.idx[sport] = (gk, teams)
        return self.idx[sport]

    def game(self, sport, vault, ev, gst):
        """(rows, how) for one game: by Vault's game key (NBA, CFB), else by the two teams and a start within 12 h."""
        gk, teams = self._load(sport)
        if vault and vault.get("key") in gk:
            return gk[vault["key"]], "gk"
        pair = None
        if vault and vault.get("away") and vault.get("home"):
            pair = (NFL_ALIAS.get(vault["away"], vault["away"]), NFL_ALIAS.get(vault["home"], vault["home"]))
        elif not vault:
            pair = slug_teams(ev, sport)
        rows = [r for r in teams.get(pair, []) if r.get("start") is not None and abs(r["start"] - gst) <= TAPE_START_GAP] if pair else []
        return (rows, "teams") if rows else ([], "no_tape_rows_for_game")


def card_signals(c, g, variant, tape):
    """The two tape reads of scripts/sf_signals.py for the card's shown side in market group `g` (None when nothing is shown there).
    Derived only from the card's stored fields and the tape rows at or before its cut, so the grader re-derives it for old cards."""
    m = (c.get("markets") or {}).get(g) or {}
    sf = (m.get("sf") or {}).get(variant) or {}
    if not sf.get("side") or not (sf.get("units") or 0) > 0 or tape is None:
        return None
    rows, how = tape.game(c["sport"], c.get("vault"), c["ev"], c["gst"])
    if not rows:
        return {"limit": None, "ev": None, "why": how}
    sides = list((m.get("sides") or {}).keys())
    norm = side_norms(g, sides, team_names(c.get("vault"), c["ev"], c["sport"])).get(sf["side"])
    return {"limit": SIG.limit_read(rows, g, c["cut"]), "ev": SIG.ev_read(rows, g, norm, sf.get("line"), c["cut"], sf.get("price")),
            "how": how, "why": None}


def classify(x, variant):
    b = x["s"][variant]
    if x["s"]["excluded_sfx" if variant == "sfx" else "excluded"]:
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


def wallet_dive(b):
    """The deep dive of a listed wallet, computed once per book (a wallet's book is cached per card)."""
    if "_dive" not in b:
        k = b.get("_key")                            # (wallet, variant, rows before the cut): the same book on another card
        if k is None or k not in _DIVES:
            d = dive(b["_ps"], b["usual"]) if b.get("_ps") else None
            if k is None:
                b["_dive"] = d
                return d
            _DIVES[k] = d
        b["_dive"] = _DIVES[k]
    return b["_dive"]


_DIVES = {}


def rk_side(mine):
    """CLV-tier read of the holders on a side (scripts/pm_clv_tiers.py): every holder at $250 or more, not just the hot ones.
    sharp / dull are the tiers; `list` is the largest sharp positions. Additive and context only."""
    by = lambda t: [x for x in mine if (x.get("rk") or {}).get("tier") == t]
    sh, du = by("sharp"), by("dull")
    return {"sharp_n": len(sh), "sharp_usd": round(sum(x["usd"] for x in sh)), "dull_n": len(du), "dull_usd": round(sum(x["usd"] for x in du)),
            "list": [{"w": x["w"], "usd": round(x["usd"]), "n": x["rk"]["n"], "mean": x["rk"]["mean"], "p": x["rk"]["p"]}
                     for x in sorted(sh, key=lambda x: -x["usd"])[:SHOW_PROVEN]]}


def wallet_line(x, variant, k):
    b = x["s"][variant]
    press = round(x["usd"] / b["usual"], 2) if b["usual"] else None
    return {"w": x["w"], "usd": round(x["usd"]), "class": k, "star": k == "hc", "two_way": x["two_way"],
            "press": press, "w_": b["w"], "l_": b["l"],
            "roi": round(b["roi"], 4) if b["roi"] is not None else None,
            "l30_roi": round(b["l30_roi"], 4) if b["l30_roi"] is not None else None, "pnl": b["pnl"], "n": b["n"],
            "usual": round(b["usual"]) if b["usual"] else None, "at_size": at_size(b, press),
            "clv": {"n": b["clv_n"], "beat": b["clv_beat"], "mean": round(b["clv_mean"], 4) if b["clv_mean"] is not None else None},
            "dive": wallet_dive(b)}


def scorecard_sharp(data_dir):
    """{sport: set of wallets} the account scorecard (scripts/build_pm_wallets.py, data/pm_wallets*.json) calls price-sharp: closing-line
    skill after a false-discovery control, not a win record. This is the list the Sharp Money Accounts page tracks (fetch-sharp-money.mjs
    loadWallets), so reading it here keeps Following and Accounts the same set of accounts. Missing or unreadable files give an empty set."""
    out = {}
    for sport, fn in SCORECARD_FILES.items():
        try:
            with open(os.path.join(data_dir, fn)) as f:
                out[sport] = {str(w).lower() for w in (json.load(f).get("sharp") or [])}
        except (OSError, ValueError, TypeError):
            out[sport] = set()
    return out


def wallet_book(s, name=None, sheet=False):
    """A proven wallet's sport book for the wallets file (variant `all`): the card's wallet line without the position fields, plus the
    wallet's name and its last settled legs ([settled_at, result], newest first), so a page can count results since a follow date."""
    b = s["all"]
    return {"name": name, "w_": b["w"], "l_": b["l"], "n": b["n"],
            "roi": round(b["roi"], 4) if b["roi"] is not None else None,
            "l30_roi": round(b["l30_roi"], 4) if b["l30_roi"] is not None else None, "pnl": b["pnl"],
            "usual": round(b["usual"]) if b["usual"] else None,
            "clv": {"n": b["clv_n"], "beat": b["clv_beat"], "mean": round(b["clv_mean"], 4) if b["clv_mean"] is not None else None},
            "dive": wallet_dive(b), "legs": [[t, r] for t, r in b["legs"]], **(wallet_sheet(b) if sheet else {})}


def wallet_sheet(b):
    """What the account sheet adds, for wallets with an open position only (the file stays small). All of it comes from the wallet's
    settled positions, the same rows the record already uses; nothing is estimated.
      l30    last 30 days: wins, losses, dollar profit, dollar ROI (the page's 30-day ROI is the same field as l30_roi)
      d30    the dive's cuts (market, favourite or underdog, size, odds band) over the last 30 days only
      odds   the all-time odds-band cuts
      curve  every settled position of the last 30 days: [settled_at, dollar profit, stake, market group, entry price]
    Entry price here is the stake-weighted price of a settled position, a stored ledger field, not an estimate."""
    ps = b.get("_ps") or []
    cut = b["asof"] - L30_DAYS * 86400
    r = [p for p in ps if p["res"] in ("win", "loss") and p["settled_at"] >= cut]
    cash = [p for p in r if not p["split"] and p["stake"] > 0]
    st, pnl = sum(p["stake"] for p in cash), sum(p["pnl"] for p in cash)
    return {"l30": {"w": sum(p["res"] == "win" for p in r), "l": sum(p["res"] == "loss" for p in r), "pnl": round(pnl),
                    "roi": round(pnl / st, 4) if st > 0 else None},
            "d30": dive(r, b["usual"], odds=True) if r else None,
            "odds": (dive(ps, b["usual"], odds=True) or {}).get("odds"),
            "curve": [[p["settled_at"], round(p["pnl"], 2), round(p["stake"], 2), GROUP.get(p["mt"]), round(p["px"], 3) if p["px"] else None]
                      for p in sorted(cash, key=lambda p: p["settled_at"])]}


HIST_MAX = 24                              # size changes kept per position in the wallets file: the first one and the latest 23


def position_history(st, cid, oi, w, fs, cut):
    """How one position has changed, from the holders scan's own logs (stored reads only, nothing estimated):
      px_first   the market's logged price for this outcome at the first read that saw the wallet holding it (the last price logged
                 at or before `fs`). It is NOT what the wallet paid: the entry happened at some point before that read. None when no
                 price was logged by then.
      hist       [[read time, shares], ...]: every change in the wallet's share count up to the cut, oldest first (0 = it had left).
                 A repeated, unchanged count is dropped.
                 Capped at HIST_MAX, keeping the first.
    Empty when no scan state is given (tests, or a caller with only a keyframe)."""
    if st is None:
        return {}
    pxs = [(t, px) for t, px in (st.m.get(cid) or {}).get("px_hist") or [] if fs is not None and t <= fs and px and oi < len(px)]
    ch = []
    for rt, a in st.hist.get((cid, oi, w), []):       # the log repeats an unchanged count when a read re-confirms it: keep real changes
        if rt <= cut and (not ch or round(a, 2) != round(ch[-1][1], 2)):
            ch.append([rt, a])
    if len(ch) > HIST_MAX:
        ch = ch[:1] + ch[-(HIST_MAX - 1):]
    out = {"hist": [[rt, round(a, 2)] for rt, a in ch]}
    if pxs:
        out["px_first"], out["px_first_t"] = pxs[-1][1][oi], pxs[-1][0]
    else:
        out["px_first"], out["px_first_t"] = None, None
    return out


def wallet_positions(kf, ledger, sport, st=None, rk=None, extra=None):
    """{wallet: [position]}: every open position of every proven wallet on one game, for the wallets file. Unlike a card, which keeps a
    wallet's largest rung per side and lists the 4 largest wallets, this keeps every rung at or above the floor ($250; FOLLOW_FLOOR lowers it for CBB) for every proven
    wallet that Vault does not exclude (variant `all`, as of the keyframe's cut). `extra` is a set of scorecard price-sharp wallets, listed proven or not. Stored values only: the line and price are the
    market's at the scan, `since` is the first scan that saw the wallet holding it, and no entry price is known or estimated.
    `two_way` marks a wallet holding more than one side of the market group above the floor (a card may collapse or drop it).
    `cens` marks a wallet already holding at the scan's first read of the market, so it got in before `since`. With the scan state
    `st`, each position also carries `px_first` and `hist` (position_history). With `rk` (CLV tiers as of now, pm_clv_tiers) a price-sharp
    wallet is listed too, proven or not."""
    cut, ix = kf["cut"], {c: i for i, c in enumerate(kf["cols"])}
    floor = FOLLOW_FLOOR.get(sport, FLOOR_USD)
    rows, sides = [], {}
    for h in kf["h"]:
        cid, oi, w, usd = h[ix["cid"]], h[ix["oi"]], h[ix["wallet"]], h[ix["usd_at_mark"]]
        mk = kf["mk"].get(cid)
        if not mk or usd is None or usd < floor or mk["mt"] not in GROUP or oi >= len(mk.get("outs") or []):
            continue
        rows.append((w, GROUP[mk["mt"]], mk, cid, oi, usd, h))
        sides.setdefault((w, GROUP[mk["mt"]]), set()).add(mk["outs"][oi])
    out, stats = {}, {}
    for w, g, mk, cid, oi, usd, h in rows:
        if w not in stats:
            stats[w] = ledger.stats(w, cut)
        s = stats[w]
        if not (s["all"]["proven"] or (rk or {}).get(w, {}).get("tier") == "sharp" or w in (extra or ())) or s["excluded"]:
            continue
        usual, px = s["all"]["usual"], (mk.get("px") or [None] * (oi + 1))[oi]
        out.setdefault(w, []).append({
            "sport": sport, "ev": kf["ev"], "gst": kf["gst"], "g": g, "side": mk["outs"][oi], "line": signed_line(mk, g, oi), "cid": cid,
            "usd": round(usd), "shares": round(h[ix["shares"]], 2) if h[ix["shares"]] is not None else None,
            "px": px, "px_t": mk.get("px_t"), "press": round(usd / usual, 2) if usual else None,
            "since": h[ix["fs"]] if "fs" in ix else None, "cens": bool(h[ix["cens"]]) if "cens" in ix else None,
            "two_way": len(sides[(w, g)]) > 1, **position_history(st, cid, oi, w, h[ix["fs"]] if "fs" in ix else None, cut)})
    for ps in out.values():
        ps.sort(key=lambda p: -p["usd"])
    return out, stats


def wallets_file(per_sport, now, retained=None, since_from=None):
    """The wallets file: per sport, every proven wallet (variant `all`, not excluded) with its book and its open positions.
    V2 (docs/sharps-v2-accounts-spec.md) only adds: `v` 2, `v2_fields`, `since_from`, `retained` (wallets that left the list, never under
    `sports`) and the per-wallet fields built by apply_v2. Every V1 top-level key is unchanged."""
    return {"built": now, "v": WALLETS_VERSION, "context_only": True, "floor_usd": FLOOR_USD, "floor_usd_by_sport": FOLLOW_FLOOR,
            "tier_rule": "rk: the wallet's CLV tier now (scripts/pm_clv_tiers.py, NBA and NFL only): sharp, mid, dull or thin. Price skill, not a record.",
            "proven_rule": "sport book n >= %d, win rate >= %d%%, dollar ROI > %d%%, not excluded (hedger, churn)" % (PROVEN_N, PROVEN_WR * 100, PROVEN_ROI * 100),
            "note": "Who holds what, as of the last holders scan. Money is shares x market price, not what the wallet paid. No entry price "
                    "is stored. Context only: never a pick, a size or an agree total.",
            "sports": per_sport,
            "v2_fields": ("per wallet: flat_roi fwd first_seen last_settled n30_games usual_med sc_sport sc_n name_disp name_src exp_w luck_p v2 "
                          "(rk.post rk.sd); per position: side_usd side_rungs side_press px_age_min; top level: since_from since_file retained. "
                          "fwd = rows with src forward, settled at or after the wallet's first_seen (a bet may have been placed before it); "
                          "first_seen = the earliest date for the wallet in first_seen.json and follow_only.json. "
                          "since_file names the file with each wallet's dated settled list (docs/sharps-v2-accounts-spec.md K). "
                          "All stored fields or arithmetic on them; null when not computable."),
            "since_from": since_from if since_from is not None else now - SINCE_DAYS * 86400,
            "since_file": SINCE_FILE,
            "retained": retained or {}}


def strip_v2(doc):
    """The V1 view of a V2 wallets file: every key V2 adds removed (a copy). A V2 build must equal its V1 build under this, except the
    30-day window fields of wallets that were open (spec section 3, audit bug 14) and `v`."""
    out = {k: v for k, v in doc.items() if k not in V2_TOP_KEYS}
    out["sports"] = {}
    for sport, ws in (doc.get("sports") or {}).items():
        out["sports"][sport] = {}
        for w, e in ws.items():
            x = {k: v for k, v in e.items() if k not in V2_WALLET_KEYS}
            if x.get("rk"):
                x["rk"] = {k: v for k, v in x["rk"].items() if k not in V2_RK_KEYS}
            x["positions"] = [{k: v for k, v in p.items() if k not in V2_POSITION_KEYS} for p in e.get("positions") or []]
            out["sports"][sport][w] = x
    return out


def wallets_sizes(doc):
    """(whole file KB, V2 fields KB) in thousands of bytes, as the spec counts them: the compact JSON as published, and its difference
    from the same file with every V2 key stripped."""
    whole = len(json.dumps(doc, separators=(",", ":")))
    return whole / 1000, (whole - len(json.dumps(strip_v2(doc), separators=(",", ":")))) / 1000


def over_budget(kb, new_kb):
    """"" when the wallets file is inside both budgets (spec section 2), else a sentence naming which one is broken."""
    bad = []
    if kb > WALLETS_MAX_KB:
        bad.append("whole file %.0f KB over %d" % (kb, WALLETS_MAX_KB))
    if new_kb > WALLETS_NEW_MAX_KB:
        bad.append("V2 fields %.0f KB over %d" % (new_kb, WALLETS_NEW_MAX_KB))
    return "; ".join(bad)


def since_file(per_sport, retained, now):
    """since.json: each wallet's dated settled list (since_list items), listed wallets under `sports` and leavers under `retained`. A
    wallet with no item in the window is left out (the file's presence says the list is carried: absent means none). Kept out of the
    wallets file because it alone was 364 KB of the 660 KB the V2 fields took (docs/sharps-v2-accounts-spec.md section 2 K)."""
    def keep(d):
        return {sp: {w: x for w, x in ws.items() if x} for sp, ws in d.items()}
    return {"built": now, "v": 1, "context_only": True, "since_from": now - SINCE_DAYS * 86400, "days": SINCE_DAYS,
            "item": "[settled_at, first_fill, r, flat, ev, stake]",
            "note": "Per position: r 1 win, 0 loss, 2 push; flat = profit / stake (null for a SPLIT-funded position); ev = the game; stake in "
                    "whole dollars. A page drops items with first_fill before the follow. Context only: never a pick, a size or an agree total.",
            "sports": keep(per_sport), "retained": keep(retained)}


# ---------- wallets file V2: stored fields only (docs/sharps-v2-accounts-spec.md) ----------

def _r(x, nd):
    return round(x, nd) if x is not None else None


def rk_entry(t):
    """The wallet's CLV tier fields: the V1 four (tier, n, mean, p) plus the shrunk estimate `post` and its sd (price units, x100 = cents),
    both already computed by pm_clv_tiers.fit(). `mean` stays the raw mean. None when the wallet has no tier row."""
    return {"tier": t["tier"], "n": t["n"], "mean": t["mean"], "p": t["p"], "post": t.get("post"), "sd": t.get("sd")} if t else None


def v2_tier(rk):
    """beats / even / loses / few from rk.tier (sharp / mid / dull / thin); no rk (no CLV game, a fit with no params, CFB, CBB) is few."""
    return V2_TIER.get((rk or {}).get("tier"), "few")


def is_hex_name(n):
    return not n or bool(HEX_NAME.match(n))


def name_history(ledger_root, holders):
    """{wallet: (time, name, source)}: the newest name that is not hex-like, over every universe snapshot and every keyframe's `names`."""
    best = {}

    def see(w, n, t, src):
        if is_hex_name(n) or not isinstance(w, str):
            return
        if w not in best or t >= best[w][0]:
            best[w] = (t, n, src)
    for fn in sorted(glob.glob(os.path.join(ledger_root or "", "universe", "*.json"))):
        try:
            with open(fn) as f:
                j = json.load(f)
        except (OSError, ValueError):
            continue
        t = j.get("selected_at") or 0
        for w, x in (j.get("wallets") or {}).items():
            see(w, (x or {}).get("name"), t, "universe")
    for fn in sorted(glob.glob(os.path.join(holders or "", "*", "frozen", "*", "*.json"))):
        try:
            with open(fn) as f:
                kf = json.load(f)
        except (OSError, ValueError):
            continue
        t = kf.get("written") or kf.get("cut") or 0
        for w, n in (kf.get("names") or {}).items():
            see(w, n, t, "keyframe")
    return best


def name_fields(w, name, origin, hist):
    """(name_disp, name_src). The listed name when it is real; else the newest real name stored anywhere; else "Unnamed 0xabcd...1234"."""
    if not is_hex_name(name):
        return name, origin or "universe"
    h = (hist or {}).get(w)
    if h:
        return h[1], h[2]
    return "Unnamed " + w[:6] + "..." + w[-4:], "none"


def scorecard_games(data_dir):
    """{sport: {wallet: games}}: the account scorecard's own game count per wallet (data/pm_wallets*.json, wallets[w][0])."""
    out = {}
    for sport, fn in SCORECARD_FILES.items():
        try:
            with open(os.path.join(data_dir, fn)) as f:
                out[sport] = {str(w).lower(): v[0] for w, v in (json.load(f).get("wallets") or {}).items() if v}
        except (OSError, ValueError, TypeError, IndexError):
            out[sport] = {}
    return out


def stake_median(ps, floor):
    """Median cost of the wallet's cash positions (not split) at or above the sport floor; None when there are none."""
    xs = [p["stake"] for p in ps if not p["split"] and p["stake"] > 0 and p["stake"] >= floor]
    return round(statistics.median(xs)) if xs else None


def fwd_book(b):
    """The forward-only book (ledger rows with src forward, not hedged), same formulas as the all-rows book."""
    return {"w": b["w"], "l": b["l"], "p": b["p"], "n": b["n"], "pnl": b["pnl"], "roi": _r(b["roi"], 4), "flat_roi": _r(b["flat_roi"], 4),
            "clv_n": b["clv_n"], "clv_mean": _r(b["clv_mean"], 4)}


def settled_reads(ps, now):
    """(latest settled_at over every position, distinct games with a decided position settled in [now - 30 d, now))."""
    lo = now - L30_DAYS * 86400
    return (max((p["settled_at"] for p in ps), default=None),
            len({p["ev"] for p in ps if p["res"] in ("win", "loss") and lo <= p["settled_at"] < now}))


def since_list(ps, floor, built, days=SINCE_DAYS):
    """Dated settled positions for "Since you followed": every non-hedged position at or above the sport floor settled in
    [built - days, built), newest first, each [settled_at, first_fill, r, flat, ev, stake]. r: 1 win, 0 loss, 2 push. first_fill is the
    earliest ledger `first` over the position's rungs (a page drops bets placed before the follow). flat = pnl / stake rounded to 3, None
    for a SPLIT-funded position (no real dollars). The unit is a POSITION (a spread and a moneyline on one game are two items), so `ev`
    (the game) and `stake` (whole dollars) ride along: a page can say "n bets on m games" and tally games the way `legs` does (one per game,
    the biggest position). Published in since.json, not in the wallets file."""
    lo = built - days * 86400
    out = []
    for p in ps:
        if p["stake"] < floor or p["stake"] <= 0 or not lo <= p["settled_at"] < built:
            continue
        out.append([p["settled_at"], p["first"], {"win": 1, "loss": 0}.get(p["res"], 2),
                    None if p["split"] else round(p["pnl"] / p["stake"], 3), p["ev"], round(p["stake"])])
    out.sort(key=lambda x: (-x[0], -(x[1] or 0), x[2], x[4]))
    return out


def games_tally(items):
    """Per-game W-L from since_list items: one result per game, that of its biggest position (the `legs` rule). -> (w, l, games)."""
    best = {}
    for it in items:
        if it[4] not in best or it[5] > best[it[4]][5]:
            best[it[4]] = it
    return (sum(1 for x in best.values() if x[2] == 1), sum(1 for x in best.values() if x[2] == 0), len(best))


def side_fields(positions, med):
    """On every open position: the wallet's whole side of that market group (all listed rungs): side_usd (sum of the rungs' usd),
    side_rungs, side_press = side_usd / usual_med (None when usual_med is None). Same value on each rung of the side."""
    by = {}
    for p in positions:
        a = by.setdefault((p["ev"], p["gst"], p["g"], p["side"]), [0, 0])
        a[0] += p["usd"]
        a[1] += 1
    for p in positions:
        u, n = by[(p["ev"], p["gst"], p["g"], p["side"])]
        p["side_usd"], p["side_rungs"] = u, n
        p["side_press"] = round(u / med, 2) if med else None


def px_age(positions, built):
    """Minutes since the price shown on each position was logged (None when no price time is stored). Never negative: a price logged
    after `built` (a pinned --now older than the holders scan) reads 0."""
    for p in positions:
        p["px_age_min"] = max(0, int(round((built - p["px_t"]) / 60))) if p.get("px_t") is not None else None


def wallet_v2_core(s, now, first_seen, rk_t):
    """The V2 fields every listed or retained wallet carries, from fl.stats(w, now): never from a game's cut."""
    ps = (s["all"].get("_ps")) or []
    last, n30 = settled_reads(ps, now)
    return {"first_seen": first_seen, "fwd": fwd_book(s["fwd"]), "last_settled": last, "n30_games": n30, "v2": {"tier": v2_tier(rk_t)}}


def apply_v2(sport, listed, fl, now, rk, sc, sc_games, names, name_origin, name_hist, since=None):
    """Add the V2 fields to every listed wallet of one sport (`listed` is wallets[sport], already carrying V1 fields). Additive, except
    that an open wallet's book is now read at `now` instead of its first game's cut (spec section 3, audit bug 14). `since`, when given,
    collects {wallet: since_list items} for since.json (they are not part of the wallets file)."""
    floor = FOLLOW_FLOOR.get(sport, FLOOR_USD)
    for w, e in listed.items():
        s = fl.stats(w, now)
        if e.get("positions"):                       # the book of a wallet with open positions was read at that game's cut
            e.update(wallet_book(s, name=e.get("name"), sheet=True))
        core = wallet_v2_core(s, now, fl.first_seen_pub.get(w), rk.get(w))
        ps = s["all"].get("_ps") or []
        if since is not None:
            since[w] = since_list(ps, floor, now)
        dv = e.get("dive") or {}
        e.update(core)
        e["flat_roi"] = _r(s["all"]["flat_roi"], 4)
        e["usual_med"] = stake_median(ps, floor)
        e["sc_sport"] = w in sc.get(sport, ())
        e["sc_n"] = (sc_games.get(sport) or {}).get(w) if e["sc_sport"] else None
        e["name_disp"], e["name_src"] = name_fields(w, names.get(w), name_origin.get(w), name_hist)
        e["exp_w"] = dv.get("exp_w")
        e["luck_p"] = (dv.get("all") or [None] * 6)[5]
        side_fields(e["positions"], e["usual_med"])
        px_age(e["positions"], now)


# ---- wallets that left the list ----

def daily_cuts(now, days=RETAIN_DAYS):
    """12:00 AM Central of each of the last `days` Central calendar days (today included), oldest first: always exactly `days` cuts,
    whether or not the window crosses a daylight saving change (a seconds offset gave 60 or 61)."""
    tz = ZoneInfo(CT_ZONE)
    today = dt.datetime.fromtimestamp(now, tz).date()
    out = []
    for i in range(days - 1, -1, -1):
        d = today - dt.timedelta(days=i)
        out.append(int(dt.datetime(d.year, d.month, d.day, tzinfo=tz).timestamp()))
    return out


def seed_retained(fl, sport, now, listed, days=RETAIN_DAYS):
    """One-time backfill of who left the list. Replays the listing rule (proven, or CLV tier sharp, and not excluded) at each daily
    12:00 AM Central cut over the prior `days` days, point in time (fl.stats(w, cut), fl.clv_tiers(cut)): rows settled before the cut,
    closes of games started before it, wallets in the universe at the cut. A wallet listed at some cut and not now gets left_at = the
    first cut after its last listed cut (now when that was the last cut). -> {wallet: left_at}. The account scorecard list is NOT replayed:
    no earlier copy of it is stored and today's list would be look-ahead, so a wallet that was listed only through it is not seeded
    (after the first build `retained` carries forward from the published file and nothing is missed)."""
    cuts = daily_cuts(now, days)
    last = {}
    for i, c in enumerate(cuts):
        rk = fl.clv_tiers(c) if sport in TIERS.TIER_SPORTS else {}
        for w in fl.population("all", c):
            if w in listed:
                continue
            sx = fl.stats(w, c)
            if not sx["excluded"] and (sx["all"]["proven"] or (rk.get(w) or {}).get("tier") == "sharp"):
                last[w] = i
    return {w: (cuts[i + 1] if i + 1 < len(cuts) else now) for w, i in last.items()}


def retained_left(sport, listed, prev, now, seed, days=RETAIN_DAYS):
    """{wallet: left_at} for the wallets that left `sports.<sport>` in the last `days` days. After the first V2 build `left_at` carries
    forward from the previous published file; a wallet in its `sports` and no longer listed leaves at `now`. `seed` is a callable
    (seed_retained) used only when `prev` has no V2 keys. A listed wallet is never retained; one older than `days` from left_at is dropped."""
    pv = prev or {}
    v2 = (pv.get("v") or 0) >= 2
    was = (pv.get("sports") or {}).get(sport) or {}
    if v2:
        out = {w: x.get("left_at") for w, x in ((pv.get("retained") or {}).get(sport) or {}).items()}
    else:
        out = dict(seed())
    for w in was:
        if w not in out:
            out[w] = now
    return {w: t for w, t in out.items() if w not in listed and isinstance(t, int) and 0 <= now - t <= days * 86400}


def retained_entry(w, left_at, s, now, first_seen, rk_t, name, name_disp):
    return {"retained": True, "left_at": left_at, "name": name, "name_disp": name_disp,
            **wallet_v2_core(s, now, first_seen, rk_t), "rk": rk_entry(rk_t)}


def ladder_units(top_press, price):
    """The benchmark pressBand / pressUnits at a clean price step (step 0), then the dog cap on any market type."""
    units = BAND5_UNITS if top_press >= BAND5 else BAND4_UNITS if top_press >= BAND4 else BAND3_UNITS
    if price is not None and price < DOG_PX:
        units = min(units, DOG_UNITS)
    return units


def lock_shadow(g, ws, cls, variant, kf):
    """The benchmark's press-ladder gates for one market group, clean-step ladder for units. A shadow record, never a pick."""
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


def locked_plays(frozen_out, now, hours=12):
    """Plays on cards frozen in the last `hours` (game start within that window), for the Record page's Open plays: once a card locks
    it leaves the live list, and the record job only lists it on its next run, up to 2 hours later. Shown size (variant all) on every
    card, the pre-registered lock on counted cards. `key` matches the graded row's key, so the page drops a play once it is graded."""
    out = []
    for path in sorted(glob.glob(os.path.join(frozen_out, "*", "frozen", "*", "*.json"))):
        try:
            gst = int(os.path.basename(path).rsplit("@", 1)[1].split(".")[0])
        except (IndexError, ValueError):
            continue
        if gst < now - hours * 3600:
            continue
        try:
            with open(path) as f:
                c = json.load(f)
        except (OSError, ValueError):
            continue
        rel = os.path.relpath(path, frozen_out)
        for g, m in (c.get("markets") or {}).items():
            sf = (m.get("sf") or {}).get("all") or {}
            if sf.get("side") and (sf.get("units") or 0) > 0:
                out.append({"key": f"{rel}|{g}|all|sf", "sport": c["sport"], "ev": c["ev"], "gst": c["gst"], "group": g, "play": "sf",
                            "side": sf["side"], "line": sf.get("line"), "outs": sf.get("outs"), "units": sf["units"]})
            ls = (m.get("lock_shadow") or {}).get("all") or {}
            if ls.get("side") and (c.get("test") or {}).get("counts"):
                out.append({"key": f"{rel}|{g}|all|lock", "sport": c["sport"], "ev": c["ev"], "gst": c["gst"], "group": g, "play": "lock",
                            "side": ls["side"], "line": ls.get("line"), "outs": ls.get("outs"), "units": ls.get("units_clean_ladder")})
    return out


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
                    # team names, for mapping Polymarket outcomes to home / away (the steam read)
                    "teams": {k: [n for n in ((g.get(k) or {}).get("name"), (g.get(k) or {}).get("short")) if n] for k in ("away", "home")},
                    # ESPN's own logo link per team, as the poller stored it (college basketball); never built here
                    "logo": {k: u for k in ("away", "home") for u in [((g.get(k) or {}).get("logo") or "")] if u.startswith("https://a.espncdn.com/")},
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
    ap.add_argument("--scorecard-dir", help="folder with pm_wallets*.json: its price-sharp accounts join the wallets file, proven or not (the Accounts page list)")
    ap.add_argument("--wallets-out", help="per-wallet file: every proven wallet's book and all of its open positions (for a follow page)")
    ap.add_argument("--sports", default="nba,nfl,cfb,cbb")
    ap.add_argument("--closes", default="data/pm_closes.json", help="Pendulum Flow closes, for wallet price skill")
    ap.add_argument("--prev-live", help="the last published live.json, to carry the price each shown size was first flagged at")
    ap.add_argument("--sf-excluded", help="The benchmark's public sharp_intel_excluded_wallets.json, for the `sfx` variant")
    ap.add_argument("--book-tape", default="data/book_tape", help="Vault's book tape (Pinnacle rows), for the steam read of the `sf` size")
    ap.add_argument("--prev-wallets", help="the last published wallets.json: `retained` (wallets that left the list) carries forward from it; "
                                           "without V2 keys in it the first V2 build seeds `retained` from a 60 day replay")
    ap.add_argument("--now", type=int, help="pin the build time (epoch seconds) for a reproducible local run; default the clock")
    ap.add_argument("--since-out", help="the since.json path (each wallet's dated settled list); default: beside --wallets-out")
    ap.add_argument("--no-budget-exit", action="store_true",
                    help="write everything and exit 0 even when the wallets file is over its size budget (the workflow then runs "
                         "scripts/sharps_v2/check_size.py before it publishes, so the frozen cards still commit)")
    ap.add_argument("--wallets-only", action="store_true", help="skip the frozen and live cards (a local run that only needs the wallets file)")
    a = ap.parse_args()
    import scan_pm_holders as H
    games = []
    if a.sharp_data and os.path.exists(a.sharp_data):
        with open(a.sharp_data) as f:
            games = json.load(f).get("games") or []
    now = int(a.now or time.time())
    live, wrote = {"built": now, "context_only": True, "games": []}, []
    pm_closes = {}
    if a.closes and os.path.exists(a.closes):
        with open(a.closes) as f:
            pm_closes = json.load(f)
    sf_ex, sf_ex_at = set(), None
    if a.sf_excluded and os.path.exists(a.sf_excluded):
        try:
            with open(a.sf_excluded) as f:
                j = json.load(f)
            sf_ex = {w.lower() for w in j.get("excluded") or [] if isinstance(w, str)}
            sf_ex_at = j.get("updatedAt")
        except (OSError, ValueError):
            sf_ex = set()                            # no list: no `sfx` variant this run, never an empty exclusion list
    live["sf_excluded_at"] = sf_ex_at if sf_ex else None
    prev = {}
    if a.prev_live and os.path.exists(a.prev_live):
        try:
            with open(a.prev_live) as f:
                prev = {(g["ev"], g["gst"]): g for g in (json.load(f).get("games") or [])}
        except (OSError, ValueError, KeyError):
            prev = {}
    names, wallets, retained, name_origin, name_hist = {}, {}, {}, {}, {}
    since, since_ret = {}, {}
    SC = scorecard_sharp(a.scorecard_dir) if a.scorecard_dir else {}
    SCG = scorecard_games(a.scorecard_dir) if a.scorecard_dir else {}
    prev_wallets = {}
    if a.prev_wallets and os.path.exists(a.prev_wallets):
        try:
            with open(a.prev_wallets) as f:
                prev_wallets = json.load(f)
        except (OSError, ValueError):
            prev_wallets = {}
    uni = sorted(glob.glob(os.path.join(a.ledger, "universe", "*.json")))
    if a.wallets_out and uni:
        try:
            with open(uni[-1]) as f:
                names = {w: (x or {}).get("name") for w, x in (json.load(f).get("wallets") or {}).items()}
            name_origin = {w: "universe" for w in names}
        except (OSError, ValueError):
            names = {}
    if a.wallets_out:
        name_hist = name_history(a.ledger, a.holders)
    tape = BookTape(a.book_tape)
    for sport in [s for s in a.sports.split(",") if s in H.SERIES]:
        ledger = Ledger.load(a.ledger, sport, a.holders, pm_closes)
        ledger.sf_excluded = sf_ex
        fl = ledger                                  # the ledger the wallets file reads: cards never see follow-only wallets
        if a.wallets_out and sport in FOLLOW_SPORTS:
            fl = Ledger.load(a.ledger, sport, a.holders, pm_closes, follow=True)
            fl.sf_excluded = sf_ex
        # frozen: one card per keyframe that has none yet
        for kpath in ([] if a.wallets_only else sorted(glob.glob(os.path.join(a.holders, sport, "frozen", "*", "*.json")))):
            rel = os.path.relpath(kpath, os.path.join(a.holders, sport, "frozen"))
            out = os.path.join(a.frozen_out, sport, "frozen", rel)
            if os.path.exists(out):
                continue
            with open(kpath) as f:
                kf = json.load(f)
            c = card(kf, ledger, sport, vault_join(games, kf["ev"], kf["gst"]), frozen=True, tape=tape)
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
        rk = fl.clv_tiers(now) if a.wallets_out and sport in TIERS.TIER_SPORTS else {}     # price-sharp wallets join the directory (docs/pm-clv-tiers.md)
        scx = set().union(*SC.values()) if SC else set()           # skill travels across sports: a scorecard-sharp wallet is listed wherever it holds a position
        evs = {(m["ev"], m["gst"]) for m in st.m.values() if m.get("gst") and m.get("mt") in FULL_GAME and now < m["gst"] - CUTOFF_SEC}
        for ev, gst in sorted(evs, key=lambda x: x[1]):
            kf = H.keyframe(st, ev, gst, now)
            if kf:
                if not a.wallets_only:
                    c = card(kf, ledger, sport, vault_join(games, ev, gst), frozen=False, tape=tape)
                    carry_flagged(c, prev.get((ev, gst)), now)
                    live["games"].append(c)
                if a.wallets_out:
                    pos, sts = wallet_positions(kf, fl, sport, st, rk, scx)
                    names.update({w: n for w, n in (kf.get("names") or {}).items() if n})
                    name_origin.update({w: "keyframe" for w, n in (kf.get("names") or {}).items() if n})
                    for w, ps in pos.items():
                        e = wallets.setdefault(sport, {}).setdefault(w, dict(wallet_book(sts[w], sheet=True), positions=[]))
                        e["positions"] += ps
        if a.wallets_out:                            # proven wallets with nothing open: the directory lists them too
            for w in set(fl.population("all", now)) | SC.get(sport, set()):
                if w in wallets.get(sport, {}):
                    continue
                s = fl.stats(w, now)
                if (s["all"]["proven"] or (rk.get(w) or {}).get("tier") == "sharp" or w in SC.get(sport, ())) and not s["excluded"]:
                    wallets.setdefault(sport, {})[w] = dict(wallet_book(s), positions=[])
            for w, e in wallets.get(sport, {}).items():
                e["name"] = names.get(w)
                e["sc"] = any(w in v for v in SC.values())      # on the account scorecard's price-sharp list (the Accounts page set)
                e["rk"] = rk_entry(rk.get(w))               # CLV tier now; NBA and NFL only (V2 adds post and sd)
                e["positions"].sort(key=lambda p: (p["gst"], -p["usd"]))
            listed = wallets.get(sport, {})
            sl = since.setdefault(sport, {})
            apply_v2(sport, listed, fl, now, rk, SC, SCG, names, name_origin, name_hist, since=sl)     # V2 fields, every wallet read at `now`
            floor = FOLLOW_FLOOR.get(sport, FLOOR_USD)
            left = retained_left(sport, listed, prev_wallets, now, lambda: seed_retained(fl, sport, now, listed))
            for w, left_at in sorted(left.items()):
                nd, _ = name_fields(w, names.get(w), name_origin.get(w), name_hist)
                st = fl.stats(w, now)
                retained.setdefault(sport, {})[w] = retained_entry(w, left_at, st, now, fl.first_seen_pub.get(w), rk.get(w), names.get(w), nd)
                since_ret.setdefault(sport, {})[w] = since_list(st["all"].get("_ps") or [], floor, now)
    live["locked"] = locked_plays(a.frozen_out, now)
    os.makedirs(os.path.dirname(os.path.abspath(a.live_out)), exist_ok=True)
    with open(a.live_out + ".tmp", "w") as f:
        json.dump(live, f, separators=(",", ":"))
    os.replace(a.live_out + ".tmp", a.live_out)
    if a.wallets_out:
        os.makedirs(os.path.dirname(os.path.abspath(a.wallets_out)), exist_ok=True)
        doc = wallets_file(wallets, now, retained)
        payload = json.dumps(doc, separators=(",", ":"))
        with open(a.wallets_out + ".tmp", "w") as f:
            f.write(payload)
        os.replace(a.wallets_out + ".tmp", a.wallets_out)
        kb, new_kb = wallets_sizes(doc)
        spath = a.since_out or os.path.join(os.path.dirname(os.path.abspath(a.wallets_out)), SINCE_FILE)
        spayload = json.dumps(since_file(since, since_ret, now), separators=(",", ":"))
        with open(spath + ".tmp", "w") as f:
            f.write(spayload)
        os.replace(spath + ".tmp", spath)
        print("wallets file %.0f KB, V2 fields %.0f KB (budget %d and %d); since file %.0f KB" % (kb, new_kb, WALLETS_MAX_KB, WALLETS_NEW_MAX_KB,
                                                                                         len(spayload) / 1000), file=sys.stderr)
        over = over_budget(kb, new_kb)
        if over:
            print("ERROR: wallets file over its size budget: " + over, file=sys.stderr)
    print(json.dumps({"frozen_written": wrote, "live_games": len(live["games"]), **({"wallets_kb": round(kb)} if a.wallets_out else {})}))
    return BUDGET_EXIT if a.wallets_out and over and not a.no_budget_exit else 0


if __name__ == "__main__":
    sys.exit(main())
