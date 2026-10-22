"""Bankroll Builder: short-priced NBA props the market AND the model both say are too long. Tracked, settled, and backtested. LOCAL: the prices are SmartStake's (licensed).

  python3 scripts/bankroll_builder.py                 # one live pass: find picks, follow prices, settle finished games, write the record
  python3 scripts/bankroll_builder.py --dry           # print the picks the rules would make right now
  python3 scripts/bankroll_builder.py --backtest      # replay the recorded tape night by night through the same rules (see BACKTEST below)

THE RULES, v2 (frozen in nba/docs/experiment-log.md section 12 on 2026-10-22, before any live pick settled; v1 required a 4% edge AND a model gate and made 8 picks in
two nights, see nba/docs/bankroll-builder-backtest.md). A pick is ONE sportsbook leg (no parlays) that passes all of:
  1. price -110 to -220 at a sportsbook (exchanges are fair-price sources only: their fees are not in the tape); any line, main or alt, tagged
  2. the price is AT OR BETTER than the market's: the fair chance from 3+ OTHER venues quoting both sides of the same line (margin removed, the median) times the
     decimal odds is >= 1, i.e. market edge >= 0%. The price band alone is not an edge: every leg in it, bet at its best price, lost 7.3% on the first nights.
  3. recent minutes >= 20, not a preseason game, not Out / Doubtful / Questionable / Inactive (needs the model's board; no board, no pick). A roster or returning-player
     hold guards the MODEL's minutes, which no longer select picks, so it is recorded on the pick (held), not blocking
  4. one pick per player per game; at most 2 per team-game and 20 per slate (ET day); a game within 36 hours
  5. logged at the first poll it qualifies (its entry price), followed to tip (its closing price), graded flat 1 unit at the entry price
  Tier: Core = market edge >= 4%; Standard = 0% to 4%. The MODEL is not a gate: its chance is recorded on every pick and the record is split by whether it cleared the
  price by 2+ points ("model agrees"), so we keep testing whether it adds anything. Staking: flat 1u on a $1,000 paper bankroll (1u = $10, as Vault Ledger); a
  quarter-Kelly column (cap 2% of the bankroll, on the market's fair chance) runs beside it as a SHADOW.

SHADOW LOG (never counted in the headline): model_only = the model clears the price by 4+ points but the market says the price is worse than fair (edge < 0).

THE MODEL'S CHANCE comes from nba/scripts/pricing.py, the same code the recorder and the page use: projection -> distribution -> calibration.
Live it reads the board on the nba-live branch and today's model files from main. In a BACKTEST it reads, for each poll, the board rebuilt from
that night's stored snapshots (nba-data branch) and the model files as they stood in git at that moment, so nothing from after the poll is used.
BACKTEST LIMITS: the prop model's fitted parameters (variance, calibration, stacker) are the ones on hand; they were last refit 2026-10-09,
before the season, so none of them has seen a regular-season game. A poll's board comes from the recorder's stored rows, cut off at the poll.

State: data/smartstake/bankroll_picks.json (live) and bankroll_backtest_picks.json (backtest). Records: bankroll_record.json / bankroll_backtest_record.json,
written to the owner's Firestore by smartstake_publish_alts.py. Nothing here is committed.
"""
import gzip
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combo_calls as CC

ROOT, SS = CC.ROOT, CC.SS
NBA_SCRIPTS = ROOT / "nba" / "scripts"
STATE, RECORD = SS / "bankroll_picks.json", SS / "bankroll_record.json"
BT_STATE, BT_RECORD = SS / "bankroll_backtest_picks.json", SS / "bankroll_backtest_record.json"
REPO = "Putput12-JP/Vault-Fantasy"
BOARD_URL = f"https://raw.githubusercontent.com/{REPO}/nba-live/board.json"
RAW_MAIN = f"https://raw.githubusercontent.com/{REPO}/main/nba/data/"
FILE_CACHE_S = 6 * 3600

BAND_LO, BAND_HI = CC.prob(-110), CC.prob(-220)        # the price band as the chance it implies: 52.4% to 68.8%
MIN_VENUES, MK_MIN = 3, 0.0                            # other venues quoting both sides; market edge (price at or better than fair)
MODEL_MARGIN, CORE_MK = 0.02, 0.04                    # the model "agrees" when it clears the price by 2 points; Core = market edge 4%+
MODEL_ONLY_MARGIN, MODEL_ONLY_MK_MAX = 0.04, 0.0       # shadow: model clears the price by 4+ while the market says the price is worse than fair
MIN_RECENT_MIN = 20.0
CAP_TEAM_GAME, CAP_SLATE, CAP_SHADOW_SLATE = 2, 20, 30
TRACK_H = 36                                           # hours before tip a pick can be made
BANKROLL0, UNIT_USD = 1000.0, 10.0
KELLY_FRAC, KELLY_CAP = 0.25, 0.02
BAD_STATUS = {"Out", "Doubtful", "Questionable", "Inactive"}
LIST_MAX = 400


# ── the market side: legs in the price band with a fair chance ────────────────────────────────────
def fair_n(side, by_book, ex):
    """(fair chance, venues used): the median of the OTHER venues quoting both sides of this line, margin removed (combo_calls.fair, but it says how many)."""
    ests = []
    for book, d in by_book.items():
        if CC.vkey(book) == ex or "over" not in d or "under" not in d:
            continue
        co, cu = CC.prob(d["over"]), CC.prob(d["under"])
        ov = co + cu - 1
        if ov > (.08 if CC.vkey(book) in CC.EXCH else .16) or ov < -.01:
            continue
        ests.append((co if side == "over" else cu) / (co + cu))
    if not ests:
        return None, 0
    ests.sort()
    m = len(ests)
    return (ests[m // 2] if m % 2 else (ests[m // 2 - 1] + ests[m // 2]) / 2), m


def market_cands(props, now):
    """Every sportsbook leg priced -110..-220 with a fair chance from at least one other venue, for games inside the tracking window."""
    out = []
    for (ev, name, st), p in props.items():
        if not (now < p["start"] <= now + TRACK_H * 3600):
            continue
        g = CC.espn_game(p["away"], p["home"], p["start"])
        if not g:
            continue
        mains = Counter(p["mains"].values())
        main = mains.most_common(1)[0][0] if mains else None
        for L in {L for (_, L) in p["q"]}:
            if L % 1 != .5:
                continue
            by_book = {b: d for (b, ll), d in p["q"].items() if ll == L}
            for side in ("over", "under"):
                for book, d in by_book.items():
                    if CC.vkey(book) in CC.EXCH or d.get(side) is None:
                        continue
                    cost = CC.prob(d[side])
                    if cost < BAND_LO - .0005 or cost > BAND_HI + .0005:
                        continue
                    f, n = fair_n(side, by_book, CC.vkey(book))
                    if f is None:
                        continue
                    out.append({"name": name, "stat": st, "side": side, "line": L, "main": main, "alt": main is not None and abs(L - main) >= 1, "book": book,
                                "odds": d[side], "dec": 1 / cost, "cost": cost, "pf": f, "n": n, "mk": f / cost - 1, "gid": g["id"], "tip": g["tip"],
                                "away": g["aabbr"], "home": g["habbr"]})
    return out


# ── the model side: the page's chance for a side at a line ───────────────────────────────────────
class Oracle:
    """The model's chance for one leg, from a Pricer (nba/scripts/pricing.py) and a board. eval() returns None when the leg cannot be priced or is held."""

    def __init__(self, pricer, board):
        import pricing as PX
        self.pr, self.board, self.PX = pricer, board, PX
        self.games = {str(g["id"]): g for g in board.get("games", [])}
        self.outs, self.status = PX.outs_from_board(board), PX.status_from_board(board)
        self.cache, self.memo, self.errors = {}, {}, 0
        self.pid = {}
        for T in pricer.D["teams"].values():
            for p in T["players"]:
                self.pid[CC.norm(p["name"])] = p["id"]
        for k, v in (pricer.state.get("players") or {}).items():
            if v.get("nm"):
                self.pid[CC.norm(v["nm"])] = int(k)
        for k, v in (board.get("players") or {}).items():
            if v:
                self.pid[CC.norm(v[0])] = int(k)

    def leg(self, name, stat, gid, away, home):
        key = (name, stat, gid)
        if key in self.memo:
            return self.memo[key]
        try:
            out = self._leg(name, stat, gid, away, home)
        except Exception:                                    # one player the pricer cannot price (no roster row) skips that leg, as the recorder's price_board does
            out = None
            self.errors += 1
        self.memo[key] = out
        return out

    def _leg(self, name, stat, gid, away, home):
        pid, g = self.pid.get(CC.norm(name)), self.games.get(str(gid))
        if pid is None or g is None:
            return None
        P = (self.pr.state.get("players") or {}).get(str(pid)) or {}
        ms = P.get("ms")
        team = ms[3] if ms else None
        if team not in (away, home):
            return None
        recent = ms[0] if ms else 0
        mm = self.pr.mu_for(pid, stat, g, self.cache, self.outs, team, self.status)
        if not mm or not (mm["min"] > 0):
            return None
        hold = self.pr.roster_hold(team, g, self.status, self.cache, mm.get("src")) or self.pr.returning_hold(pid, team, g)
        st = self.status.get(pid)
        # hard gates only: a roster / returning-player hold protects the MODEL's minutes projection, which no longer selects picks, so it is recorded (held), not blocking
        why = "preseason" if hold and hold["why"] == "preseason" else "status:" + st if st in BAD_STATUS else "minutes" if recent < MIN_RECENT_MIN else None
        return {"mu": mm["mu"], "extra": mm["extra"], "mmin": mm["min"], "recent": recent, "team": team, "why": why, "pid": pid, "held": hold["why"] if hold else None}

    def chance(self, leg, stat, side, line):
        over = self.pr.cal(stat, self.pr.p_over_raw(stat, leg["mu"], line, leg["extra"]))
        return over if side == "over" else 1 - over


def load_live_oracle():
    """An Oracle on the live board (nba-live) and today's model files (main), both cached."""
    sys.path.insert(0, str(NBA_SCRIPTS))
    import pricing as PX

    def cached(url, path, max_age):
        if not path.exists() or time.time() - path.stat().st_mtime > max_age:
            d = CC.curl_json(url)
            if d:
                path.write_text(json.dumps(d, separators=(",", ":")))
        return json.loads(path.read_text()) if path.exists() else None

    board = cached(BOARD_URL, SS / "bankroll_board_cache.json", 120)
    D = cached(RAW_MAIN + "player_projections.json", SS / "bankroll_proj_cache.json", FILE_CACHE_S)
    MS = cached(RAW_MAIN + "model_state.json", SS / "bankroll_ms_cache.json", FILE_CACHE_S)
    if not (board and D and MS):
        return None
    return Oracle(PX.Pricer(D=D, MS=MS), board)


# ── one poll ────────────────────────────────────────────────────────────────────────────────────
def et_day(ts):
    return datetime.fromtimestamp(ts, CC.ET).strftime("%Y-%m-%d")


def kelly_frac(pf, dec):
    return round(min(KELLY_CAP, KELLY_FRAC * max(0.0, (pf * dec - 1) / (dec - 1))), 4)


def mk_pick(c, ev, pm, kind, now):
    margin = pm - c["cost"]
    tier = "core" if c["mk"] >= CORE_MK else "standard"
    return {"k": f"{kind}|{c['gid']}|{c['name']}", "kind": kind, "type": "straight", "book": c["book"], "first": now, "tip": c["tip"], "gid": c["gid"], "name": c["name"],
            "team": ev["team"], "pid": ev["pid"], "away": c["away"], "home": c["home"], "stat": c["stat"], "side": c["side"], "line": c["line"], "main": c["main"], "alt": c["alt"],
            "tier": tier, "agree": margin >= MODEL_MARGIN, "held": ev.get("held"), "odds0": c["odds"], "dec0": round(c["dec"], 4), "pf0": round(c["pf"], 4), "n0": c["n"], "pm0": round(pm, 4), "mk0": round(c["mk"], 4),
            "md0": round(pm / c["cost"] - 1, 4), "kf": kelly_frac(c["pf"], c["dec"]),
            "legs": [{"name": c["name"], "stat": c["stat"], "side": c["side"], "line": c["line"], "gid": c["gid"], "tip": c["tip"], "odds": c["odds"]}]}


def step(S, quotes, now, oracle_for, props=None):
    """One poll: new picks and shadow picks from this poll's prices, then follow every open pick's price and settle what has finished. oracle_for(now) is
    called at most once, and only when something needs the model."""
    props = props or CC.props_from(quotes)
    P, SH = S["picks"], S["shadow"]
    cands = market_cands(props, now)
    fresh = [c for c in cands if f"pick|{c['gid']}|{c['name']}" not in P]
    need = [c for c in fresh if (c["n"] >= MIN_VENUES and c["mk"] >= MK_MIN) or (c["n"] >= 2 and c["mk"] < MODEL_ONLY_MK_MAX and f"model_only|{c['gid']}|{c['name']}" not in SH)]
    stats = {"band": len(cands), "market": sum(1 for c in cands if c["n"] >= MIN_VENUES and c["mk"] >= MK_MIN), "model_pass": 0, "new": 0}
    if need:
        oracle = oracle_for(now)
        if oracle:
            by_kind = {"pick": [], "model_only": []}
            for c in need:
                lg = oracle.leg(c["name"], c["stat"], c["gid"], c["away"], c["home"])
                if not lg or lg["why"]:
                    continue
                pm = oracle.chance(lg, c["stat"], c["side"], c["line"])
                margin = pm - c["cost"]
                if c["n"] >= MIN_VENUES and c["mk"] >= MK_MIN:
                    by_kind["pick"].append((c, lg, pm))
                elif c["mk"] < MODEL_ONLY_MK_MAX and margin >= MODEL_ONLY_MARGIN:
                    by_kind["model_only"].append((c, lg, pm))
            stats["model_pass"] = sum(1 for c, lg, pm in by_kind["pick"] if pm - c["cost"] >= MODEL_MARGIN)
            for kind, rows in by_kind.items():
                rows.sort(key=lambda r: (-r[0]["mk"], -(r[2] - r[0]["cost"])))
                store = P if kind == "pick" else SH
                for c, lg, pm in rows:
                    k = f"{kind}|{c['gid']}|{c['name']}"
                    if k in store or (kind != "pick" and f"pick|{c['gid']}|{c['name']}" in P):
                        continue
                    day = et_day(c["tip"])
                    same = [p for p in store.values() if p["kind"] == kind]
                    capped = S.setdefault("capped", {})
                    if sum(1 for p in same if et_day(p["tip"]) == day) >= (CAP_SLATE if kind == "pick" else CAP_SHADOW_SLATE):
                        capped.setdefault(kind, {}).setdefault("slate", {})[k] = 1            # a pick the slate cap kept out (counted once per leg)
                        continue
                    if kind == "pick" and sum(1 for p in same if p["gid"] == c["gid"] and p["team"] == lg["team"]) >= CAP_TEAM_GAME:
                        capped.setdefault(kind, {}).setdefault("team_game", {})[k] = 1
                        continue
                    store[k] = mk_pick(c, lg, pm, kind, now)
                    stats["new"] += kind == "pick"
    for store in (P, SH):
        for c in store.values():                              # the price now, followed until tip: the last one seen is the close
            if not c.get("res") and now < c["tip"]:
                d = CC.price_now(c, props)
                if d:
                    c["decN"] = round(d, 4)
            CC.settle(c, now)
    S["last"] = dict(stats, at=now)
    return stats


# ── the record ────────────────────────────────────────────────────────────────────────────────
def agg(ps):
    st = [p for p in ps if p.get("res") in ("won", "lost")]
    u = [p["units"] for p in st]
    clv = [p["clv"] for p in st if p.get("clv") is not None]
    n, nc = len(u), len(clv)
    sd = statistics.pstdev(u) if n > 1 else 0
    am = [p["odds0"] for p in ps]
    return {"picks": len(ps), "settled": n, "void": sum(1 for p in ps if p.get("res") == "void"), "won": sum(1 for p in st if p["res"] == "won"),
            "win": round(sum(1 for p in st if p["res"] == "won") / n, 4) if n else None,
            "units": round(sum(u), 2), "roi": round(sum(u) / n, 4) if n else None,
            "z": round(sum(u) / n / (sd / math.sqrt(n)), 2) if n > 1 and sd else None,
            "clv": round(statistics.mean(clv), 4) if clv else None, "clv_n": nc,
            "clv_se": round(statistics.pstdev(clv) / math.sqrt(nc), 4) if nc > 1 else None,
            "fair": round(statistics.mean(p["pf0"] for p in st), 4) if st else None, "model": round(statistics.mean(p["pm0"] for p in st), 4) if st else None,
            "avg_odds": round(statistics.mean(am)) if am else None, "mk": round(statistics.mean(p["mk0"] for p in ps), 4) if ps else None}


def curve(ps):
    """[tip, flat bankroll, quarter-Kelly shadow bankroll] after each settled pick, in tip order. Flat 1u = $10; Kelly is sequential by tip (a shadow)."""
    flat, kel, out = BANKROLL0, BANKROLL0, []
    for p in sorted((p for p in ps if p.get("res") in ("won", "lost")), key=lambda p: (p["tip"], p["first"])):
        flat += UNIT_USD * p["units"]
        kel *= 1 + p["kf"] * p["units"]
        out.append([p["tip"], round(flat, 2), round(kel, 2)])
    return out


def _core(P, SH):
    """The aggregates for one set of picks: headline, slices, curve, bankroll."""
    by = lambda f, ps=P: {k: agg([p for p in ps if f(p) == k]) for k in sorted({f(p) for p in ps}, key=str)}
    ebin = lambda p: "0-2%" if p["mk0"] < .02 else "2-4%" if p["mk0"] < .04 else "4-6%" if p["mk0"] < .06 else "6%+"
    cv = curve(P)
    return {"all": agg(P), "tier": by(lambda p: p["tier"]), "book": by(lambda p: p["book"]), "stat": by(lambda p: p["stat"]), "side": by(lambda p: p["side"]),
            "kind": by(lambda p: "alt" if p["alt"] else "main"), "edge": by(ebin), "day": by(lambda p: et_day(p["tip"])),
            "model": by(lambda p: "agrees" if p.get("agree") else "disagrees"), "held": by(lambda p: "held: " + p["held"] if p.get("held") else "no hold"),
            "source": by(lambda p: "replayed" if p.get("source") == "replay" else "live"),
            "shadow": {"model_only": agg([p for p in SH if p["kind"] == "model_only"])},
            "curve": cv, "bankroll": {"start": BANKROLL0, "unit_usd": UNIT_USD, "flat": cv[-1][1] if cv else BANKROLL0, "kelly_shadow": cv[-1][2] if cv else BANKROLL0}}


def summarize(S, extra=None):
    """The record. Top level = every pick, live and replayed (a replayed pick carries source 'replay'); rec['live'] = the same aggregates for live picks only,
    so the page can switch the headline between 'live + replayed first nights' and 'live only'."""
    P, SH = list(S["picks"].values()), list(S["shadow"].values())
    keep = ("name", "pid", "team", "away", "home", "stat", "side", "line", "main", "alt", "book", "tier", "first", "tip", "odds0", "dec0", "decN", "pf0", "n0", "pm0", "mk0", "md0",
            "res", "units", "clv", "kf", "agree", "held", "source")
    trim = lambda p: {k: p.get(k) for k in keep} | {"y": (p["legs"][0].get("y"))}
    full = sorted(P, key=lambda p: (-p["tip"], -p["first"]))[:LIST_MAX]
    shadow_full = sorted((p for p in SH if p["kind"] == "model_only"), key=lambda p: (-p["tip"], -p["first"]))[:LIST_MAX]   # so a slice click can show the plays behind the shadow row
    live = lambda ps: [p for p in ps if p.get("source") != "replay"]
    rec = _core(P, SH)
    rec.update({"live": _core(live(P), live(SH)), "replay": S.get("replay"),
                "capped": {kind: {why: len(v) for why, v in d.items()} for kind, d in (S.get("capped") or {}).items()},
                "list": [trim(p) for p in full], "shadow_list": [trim(p) for p in shadow_full], "last": S.get("last")})
    rec.update(dict(extra or {}, rules="v2"))
    return rec


def merge_replay(S, R, cutoff=None):
    """Fold a backtest state R into the live state S, so the record is one source of truth. Replayed picks are tagged source='replay' and keep their own
    entry prices and times; only those first seen BEFORE the live tracker began (the cutoff) are taken, and a replayed pick replaces a later live pick on the same
    player-game (first sighting wins; one pick per player per game). The live step then follows and settles any that are still open, exactly like a live pick.
    Idempotent: the cutoff is stored, and a key already merged is skipped. Returns how many were added."""
    rp = S.get("replay") or {}
    if cutoff is None:
        cutoff = rp.get("cutoff") or min((p["first"] for p in S["picks"].values() if p.get("source") != "replay"), default=int(time.time()))
    added = dropped = 0
    for store, src in ((S["picks"], R["picks"]), (S["shadow"], R["shadow"])):
        for k, p in src.items():
            if p["first"] >= cutoff or (store.get(k) or {}).get("source") == "replay":
                continue
            dropped += k in store                              # a later live sighting of the same player-game
            store[k] = dict(p, source="replay")
            added += 1
    S["replay"] = dict(rp, cutoff=cutoff, merged_at=int(time.time()), picks=sum(1 for p in S["picks"].values() if p.get("source") == "replay"),
                       dropped_live=rp.get("dropped_live", 0) + dropped, polls=R.get("polls") or rp.get("polls"))
    return added


# ── live ─────────────────────────────────────────────────────────────────────────────────────────
def run(dry=False):
    now = int(time.time())
    t, quotes = CC.latest_poll()
    if not quotes:
        print("no SmartStake NBA tape")
        return None
    S = json.loads(STATE.read_text()) if STATE.exists() and not dry else {"picks": {}, "shadow": {}}
    memo = {}
    oracle_for = lambda _n: memo.setdefault("o", load_live_oracle())
    before = set(S["picks"])
    stats = step(S, quotes, now, oracle_for)
    print(f"{stats['band']} legs in the price band, {stats['market']} at or better than the market's price, {stats['model_pass']} of those the model also likes, {stats['new']} new picks")
    if dry:
        for p in sorted(S["picks"].values(), key=lambda p: -p["mk0"]):
            print(f"  {p['tier']:8} {p['book']:10} mkt +{p['mk0']*100:4.1f}% ({p['n0']} venues)  model {p['pm0']*100:4.1f}% vs {100/p['dec0']:4.1f}%  "
                  f"{p['name']} {p['side'][0].upper()}{p['line']} {p['stat']} {p['odds0']:+d}  {p['away']}@{p['home']}")
        return None
    STATE.write_text(json.dumps(S, separators=(",", ":")))
    rec = summarize(S, {"asof": now, "mode": "live"})
    RECORD.write_text(json.dumps(rec, separators=(",", ":")))
    a = rec["all"]
    print(f"record: {a['picks']} picks ({len(set(S['picks']) - before)} new), {a['settled']} settled, {a['units']}u, roi {a['roi']}, clv {a['clv']} (n {a['clv_n']}); "
          f"bankroll ${rec['bankroll']['flat']:.0f}")
    return rec


# ── backtest ─────────────────────────────────────────────────────────────────────────────────────
def _git_json(ref):
    p = subprocess.run(["git", "-C", str(ROOT), "show", ref], capture_output=True)
    return json.loads(p.stdout)


INPUTS = ("kalshi", "espn", "pinnacle", "action", "polymarket", "injuries", "lineups", "prizepicks", "underdog", "sleeper", "novig")   # the recorder's price sources (replay_polls.INPUTS)


class SnapState:
    """The recorder's Day.last / first / when / hist / log / t0 over stored snapshot folders, advanced poll by poll (replay_polls.State, which also
    imports numpy through its other stages; the board needs none of that)."""

    def __init__(self, folders, wire_src):
        self.rows, self.meta, self.wire_src = [], defaultdict(dict), wire_src
        for f in folders:
            for fn in sorted(os.listdir(f)):
                if fn.endswith(".jsonl") and fn[:-6] in INPUTS:
                    self.rows += [(r["t"], fn[:-6], r) for r in map(json.loads, open(Path(f) / fn))]
            for r in map(json.loads, open(Path(f) / "meta.jsonl")):
                if r["src"] in INPUTS:
                    self.meta[r["src"]][r["k"]] = r
        self.rows.sort(key=lambda x: x[0])
        self.last, self.first, self.when = defaultdict(dict), defaultdict(dict), defaultdict(dict)
        self.hist, self.log, self.t0 = defaultdict(lambda: defaultdict(list)), defaultdict(list), {}
        self.i = 0

    def advance(self, t):
        while self.i < len(self.rows) and self.rows[self.i][0] < t:
            tt, src, r = self.rows[self.i]
            self.i += 1
            last = self.last[src]
            self.when[src][r["k"]] = tt
            self.hist[src][r["k"]].append(tt)
            self.t0.setdefault(src, tt)
            if src in self.wire_src:
                self.log[src].append((tt, r["k"], last.get(r["k"]), r["v"]))
            if r["v"] is None:
                last.pop(r["k"], None)
            else:
                last[r["k"]] = r["v"]
                self.first[src].setdefault(r["k"], r["v"])


class Replay:
    """The board and the model files as they stood at each poll, from the recorder's stored snapshots and git history."""

    def __init__(self, snap_root, days):
        sys.path.insert(0, str(NBA_SCRIPTS))
        import pricing as PX
        import prop_board as PB
        import render_app
        import snapshot as SN
        self.PX, self.PB, self.SN = PX, PB, SN
        self.PR = render_app.pricing()
        log = subprocess.run(["git", "-C", str(ROOT), "log", "--reverse", "--format=%H %ct", "--", "nba/data/model_state.json", "nba/data/player_projections.json"],
                             capture_output=True, text=True).stdout.split("\n")
        self.commits = [(int(l.split()[1]), l.split()[0]) for l in log if l.strip()]
        self.files, self.pricers, self.sched = {}, {}, {}
        self.st = SnapState([Path(snap_root) / "snapshots" / d for d in days], SN.WIRE_SRC)
        self.boards_built = 0

    def schedule(self, day):
        if day not in self.sched:
            import datetime as dt
            gs = self.SN.espn_day(dt.date.fromisoformat(day), {})
            for g in gs:
                g.pop("state", None)
            self.sched[day] = gs
        return self.sched[day]

    def sha_at(self, now):
        sha = None
        for ct, h in self.commits:
            if ct <= now:
                sha = h
        return sha

    def oracle_for(self, now):
        from datetime import timedelta
        sha = self.sha_at(now)
        if not sha:
            return None
        if sha not in self.files:
            self.files[sha] = (_git_json(f"{sha}:nba/data/player_projections.json"), _git_json(f"{sha}:nba/data/model_state.json"))
        D, MS = self.files[sha]
        self.st.advance(now)
        d0 = datetime.fromtimestamp(now, CC.ET).date()
        gs = []
        for off in (-1, 0, 1, 2):
            gs += self.schedule((d0 + timedelta(days=off)).isoformat())
        gs = [dict(g, pre=now < g["tip"] <= now + self.SN.AHEAD_H * 3600) for g in gs]
        st = self.st
        board = self.PB.build([g for g in gs if g["pre"]], st.last, st.meta, st.first, D, now, when=st.when, wire=(st.hist, st.log, st.t0))
        self.boards_built += 1
        if sha not in self.pricers:
            self.pricers[sha] = self.PX.Pricer(D=D, PR=self.PR, MS=MS)
        return Oracle(self.pricers[sha], board)


def backtest(snap_root, days, tape_days, final_day):
    """Replay the stored tape poll by poll through step(), then settle from box scores. days: the nba-data snapshot folders; tape_days: the SmartStake tape files."""
    rp = Replay(snap_root, days)
    S = {"picks": {}, "shadow": {}}
    polls = 0
    t0 = time.time()
    for d in tape_days:
        for line in gzip.open(SS / "nba" / f"{d}.jsonl.gz", "rt", encoding="utf-8"):
            m = re.match(r'\{"t":(\d+)', line)
            now = int(m.group(1)) // 1000
            if now > final_day:
                break
            p = json.loads(line)
            polls += 1
            step(S, p["quotes"], now, rp.oracle_for)
            if polls % 25 == 0:
                print(f"  {d} poll {polls}: {len(S['picks'])} picks, {len(S['shadow'])} shadow, {rp.boards_built} boards, {time.time() - t0:.0f}s", flush=True)
    for store in (S["picks"], S["shadow"]):                   # one last pass with no prices: settle whatever has finished
        for c in store.values():
            CC.settle(c, int(time.time()))
    cov = {"mode": "backtest", "polls": polls, "boards": rp.boards_built, "days": tape_days, "asof": int(time.time()),
           "models": sorted({h[:7] for _, h in rp.commits if rp.files.get(h)})}
    BT_STATE.write_text(json.dumps(S, separators=(",", ":")))
    rec = summarize(S, cov)
    BT_RECORD.write_text(json.dumps(rec, separators=(",", ":")))
    a = rec["all"]
    print(f"BACKTEST: {a['picks']} picks, {a['settled']} settled, {a['won']} won, {a['units']}u, roi {a['roi']}, z {a['z']}, clv {a['clv']} (n {a['clv_n']}), "
          f"bankroll ${rec['bankroll']['flat']:.0f} flat / ${rec['bankroll']['kelly_shadow']:.0f} kelly shadow")
    return rec


def main(argv):
    if "--backtest" in argv:
        arg = lambda k, d: next((a.split("=", 1)[1] for a in argv if a.startswith(k + "=")), d)
        days = arg("--days", "2026-10-19,2026-10-20,2026-10-21,2026-10-22").split(",")
        snap = arg("--snap", None)
        if not snap:
            sys.exit("--snap=<dir holding snapshots/<day>/ extracted from the nba-data branch> is required")
        tape = arg("--tape", "2026-10-19,2026-10-20,2026-10-21,2026-10-22").split(",")
        tag = arg("--tag", "")
        for kv in filter(None, arg("--set", "").split(",")):         # a sensitivity run: --set=MIN_VENUES=2,MK_MIN=0.03 --tag=loose (volume only; never the record)
            k, v = kv.split("=")
            globals()[k] = type(globals()[k])(v)
        if tag:
            global BT_STATE, BT_RECORD
            BT_STATE, BT_RECORD = SS / f"bankroll_backtest_{tag}_picks.json", SS / f"bankroll_backtest_{tag}_record.json"
        return backtest(snap, days, tape, int(arg("--until", time.time())))
    if "--merge-replay" in argv:                                   # one-time (idempotent): fold the stored backtest into the live record, tagged 'replay'
        R, meta = json.loads(BT_STATE.read_text()), json.loads(BT_RECORD.read_text())
        S = json.loads(STATE.read_text())
        n = merge_replay(S, R)
        S["replay"].update({"boards": meta["boards"], "days": meta["days"], "models": meta["models"], "polls": meta["polls"]})
        STATE.write_text(json.dumps(S, separators=(",", ":")))
        rec = summarize(S, {"asof": int(time.time()), "mode": "live"})
        RECORD.write_text(json.dumps(rec, separators=(",", ":")))
        a, l = rec["all"], rec["live"]["all"]
        print(f"merged {n} replayed picks (cutoff {S['replay']['cutoff']}, {S['replay']['dropped_live']} later live duplicates replaced): {a['picks']} picks, {a['settled']} settled, {a['units']}u; live only: {l['picks']} picks")
        return rec
    return run(dry="--dry" in argv)


if __name__ == "__main__":
    main(sys.argv[1:])
