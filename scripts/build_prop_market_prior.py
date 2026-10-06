#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · PROP MODEL vs REAL HISTORICAL LINES  →  data/prop_market_prior.json
#
#  Vault's own line archive starts in 2026, so every "does the prop model beat
#  the book?" answer used to rest on a few weeks. ESPN's public core API keeps
#  ESPN BET's player-prop lines for past games (opening AND closing line, with
#  prices on both sides), free and keyless:
#     events/{id}/competitions/{id}/odds            → providers (58 = ESPN BET)
#     events/{id}/competitions/{id}/odds/58/propBets?limit=1000&page=N
#  Half-point items are the priced main lines, one side per item; whole-number
#  items are unpriced alt ladders and are skipped. Anytime TD was priced only in
#  2025 Week 1, so it is not scored here (see anytime_td_history.json).
#
#  This replays the SHIPPED model (data/prop_model.json, the same projection the
#  board serves: last season + this season's games before kickoff) on every
#  2024-25 two-way line and measures, per market:
#    • log-loss of Vault vs the de-vigged market, and the best weight on Vault in
#      a logit blend with the market (w_model) — the measured starting point for
#      the board's market blend (build_prop_projections.py reads it as the prior
#      that this season's settled bets then move);
#    • ROI of betting Vault's +EV side at the open and at the close;
#    • the same ROI per Best Bets play type (market|side|RB/QB/WR/TE), which
#      settle_bets.py uses to veto a type that lost on the historical lines.
#  Not in the replay: the board's opponent / game-environment / role multipliers
#  (not in the historical rows). Re-run when prop_model.json changes materially.
#
#  Usage:
#    python3 scripts/build_prop_market_prior.py            # crawl (cached) + replay + write
#    python3 scripts/build_prop_market_prior.py --refresh  # re-crawl ESPN
#    python3 scripts/build_prop_market_prior.py --dry
# ════════════════════════════════════════════════════════════════════════════
import argparse, csv, io, json, math, os, re, sys, unicodedata, urllib.request
import concurrent.futures as cf
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
sys.path.insert(0, HERE)
import build_prop_projections as B

OUT = os.path.join(DATA, "prop_market_prior.json")
CACHE = os.path.join(DATA, "espn_prop_lines_{}.json")
GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PLAYERS_URL = "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{e}/competitions/{e}/odds"
SEASONS = (2024, 2025)
ESPN_TYPES = {
    "Total Receiving Yards (incl. overtime)": "rec_yd", "Total Receptions (incl. overtime)": "rec",
    "Total Rushing Yards (incl. overtime)": "rush_yd", "Total Carries (incl. overtime)": "rush_att",
    "Total Passing Yards (incl. overtime)": "pass_yd", "Total Passing Attempts (incl. overtime)": "pass_att",
    "Total Pass Completions (incl. overtime)": "pass_cmp", "Total Passing Touchdowns (incl. overtime)": "pass_td",
}
MIN_VETO_N = 200      # a play type needs this many historical bets before history can veto it
UA = {"User-Agent": "Mozilla/5.0"}


def get_json(url):
    for _ in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
        except Exception:
            pass
    return {}


def get_text(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode("utf-8", "replace")


def american(x):
    a = (x or {}).get("american")
    if a in (None, ""): return None
    if a == "Even": return 100
    try: return int(str(a).replace("+", ""))
    except ValueError: return None


# ── crawl ──────────────────────────────────────────────────────────────────
def crawl_game(g):
    """→ [[gid, espn athlete id, market, line_o, over_o, under_o, line_c, over_c, under_c], ...]"""
    e, pairs = g["espn"], defaultdict(dict)
    for it in get_json(CORE.format(e=e)).get("items", []):
        if "Live" in it["provider"]["name"] or "propBets" not in it: continue
        pid = it["$ref"].split("/odds/")[1].split("?")[0]
        page = 1
        while True:
            d = get_json(CORE.format(e=e) + f"/{pid}/propBets?limit=1000&page={page}")
            for i in d.get("items", []):
                mkt = ESPN_TYPES.get(i["type"]["name"])
                c, o = i.get("current") or {}, i.get("open") or {}
                side = "over" if "over" in c else "under" if "under" in c else None
                if not mkt or not side: continue
                ath = i["athlete"]["$ref"].split("/athletes/")[1].split("?")[0]
                for when, blk in (("c", c), ("o", o)):
                    line, px = (blk.get("target") or {}).get("value"), american(blk.get(side))
                    if line is None or px is None or float(line) % 1 == 0: continue
                    pairs[(ath, mkt, when, float(line))][side] = px
            if page >= (d.get("pageCount") or 1): break
            page += 1
        break                          # one book (ESPN BET) per game
    out, by = [], defaultdict(dict)
    for (ath, mkt, when, line), s in pairs.items():
        if "over" in s and "under" in s:
            by[(ath, mkt)][when] = (line, s["over"], s["under"])
    for (ath, mkt), w in by.items():
        o, c = w.get("o"), w.get("c")
        if not c: continue
        out.append([g["game_id"], ath, mkt, *(o or (None, None, None)), *c])
    return out


def load_lines(season, games, refresh):
    path = CACHE.format(season)
    if not refresh and os.path.exists(path):
        return json.load(open(path))["rows"]
    gs = [g for g in games if g["season"] == str(season) and g["game_type"] == "REG" and g["espn"]]
    rows = []
    with cf.ThreadPoolExecutor(10) as ex:
        for r in ex.map(crawl_game, gs):
            rows += r
    json.dump({"source": "ESPN BET via ESPN core API propBets", "season": season,
               "cols": ["gid", "espn_ath", "market", "line_o", "over_o", "under_o", "line_c", "over_c", "under_c"],
               "rows": rows}, open(path, "w"), separators=(",", ":"))
    print(f"[prop-prior] crawled {season}: {len(rows)} two-way lines from {len(gs)} games")
    return rows


# ── replay the shipped model ───────────────────────────────────────────────
def nkey(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return re.sub(r"[^a-z]", "", "".join(ch for ch in s if unicodedata.category(ch) != "Mn"))


def load_weeks(seasons):
    out = {}
    for yr in seasons:
        try:
            blob = json.load(open(os.path.join(DATA, f"nflverse_stats_{yr}.json")))
        except FileNotFoundError:
            continue
        for p in (blob.values() if isinstance(blob, dict) else blob):
            k = (nkey(p.get("name")), yr)
            wk = sorted(p.get("weeks") or [], key=lambda w: B.num(w.get("wk")) or 0)
            if k not in out or len(wk) > len(out[k][1]):
                out[k] = (p.get("pos"), wk)
    return out


def project(m, mkt, weeks):
    """Mirror of index.html projectFrom (no role anchor / matchup multipliers)."""
    g = m.get("gate")
    if g: weeks = [w for w in weeks if (B.num(w.get(g[0])) or 0) >= g[1]]
    if m.get("vol") and m.get("eff_num"):
        vs, es = [], []
        for w in weeks:
            v, n = B.num(w.get(m["vol"])), B.num(w.get(m["eff_num"]))
            if v is not None: vs.append(v)
            if v and v > 0 and n is not None: es.append(n / v)
        if len(vs) < 3 or len(es) < 3: return None
        return (B.project_series(vs, m["prior"][mkt + "|vol"], m["half_life"], m["k_vol"])
                * B.project_series(es, m["prior"][mkt + "|eff"], m["half_life"], m["k_eff"]))
    keys = m.get("stat_sum") or [m.get("stat")]
    s = []
    for w in weeks:
        vals = [B.num(w.get(k)) for k in keys]
        if all(v is None for v in vals): continue
        s.append(sum(v or 0 for v in vals))
    if len(s) < 3: return None
    return B.project_series(s, m["prior"][mkt], m["half_life"], m["k_vol"])


def actual_of(m, row):
    if m.get("vol") and m.get("eff_num"): return B.num(row.get(m["eff_num"]))
    keys = m.get("stat_sum") or [m.get("stat")]
    vals = [B.num(row.get(k)) for k in keys]
    return None if all(v is None for v in vals) else sum(v or 0 for v in vals)


def p_over(m, proj, line):
    p = B.apply_calib(m.get("calib") or [], B.prob_fn_for(m)(proj, line))
    p = B.shrink_prob(p, m.get("shrink", 1.0))
    return min(max(p, 0.01), 0.99)


dec = lambda a: 1 + (a / 100 if a > 0 else 100 / -a)
imp = lambda a: 1 / dec(a)
lg = lambda p: math.log(min(max(p, 1e-6), 1 - 1e-6) / (1 - min(max(p, 1e-6), 1 - 1e-6)))
sig = lambda x: 1 / (1 + math.exp(-max(-60, min(60, x))))


def ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p) if y else -math.log(1 - p)


def posgroup(pos):
    return "RB" if pos == "RB" else "QB" if pos == "QB" else "WR/TE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    games = list(csv.DictReader(io.StringIO(get_text(GAMES_URL))))
    gmap = {g["game_id"]: g for g in games}
    e2n = {r["espn_id"]: r["display_name"] for r in csv.DictReader(io.StringIO(get_text(PLAYERS_URL))) if r.get("espn_id")}
    model = json.load(open(os.path.join(DATA, "prop_model.json")))["markets"]
    W = load_weeks([min(SEASONS) - 1, *SEASONS])

    scored = defaultdict(list)       # market -> rows
    skipped = defaultdict(int)
    for season in SEASONS:
        for gid, ath, mkt, lo, oo, uo, lc, oc, uc in load_lines(season, games, args.refresh):
            m = model.get(mkt)
            if not m: skipped["no model market"] += 1; continue
            name = e2n.get(ath)
            if not name: skipped["no player id"] += 1; continue
            g = gmap.get(gid)
            if not g: skipped["no game"] += 1; continue
            yr, wk = int(g["season"]), int(g["week"])
            pos, cur = W.get((nkey(name), yr), (None, []))
            if pos is None: skipped["no game log"] += 1; continue
            if pos not in m["pos"]: skipped["position"] += 1; continue
            row = next((w for w in cur if B.num(w.get("wk")) == wk), None)
            if row is None: skipped["did not play"] += 1; continue
            prev = W.get((nkey(name), yr - 1), (None, []))[1]
            proj = project(m, mkt, prev + [w for w in cur if (B.num(w.get("wk")) or 0) < wk])
            act = actual_of(m, row)
            if proj is None or act is None: skipped["thin history"] += 1; continue
            for when, line, o, u in (("open", lo, oo, uo), ("close", lc, oc, uc)):
                if line is None or o is None or u is None or abs(act - line) < 1e-9: continue
                q = imp(o) / (imp(o) + imp(u))
                scored[mkt].append({"when": when, "p": p_over(m, proj, line), "q": q, "o": o, "u": u,
                                    "y": act > line, "g": posgroup(pos), "season": yr})

    def roi(rows, thr):
        n = w = 0; u = 0.0
        for r in rows:
            eo, eu = r["p"] * dec(r["o"]) - 1, (1 - r["p"]) * dec(r["u"]) - 1
            side, ev, px = ("over", eo, r["o"]) if eo >= eu else ("under", eu, r["u"])
            if ev < thr: continue
            win = r["y"] == (side == "over")
            n += 1; w += win; u += (dec(px) - 1) if win else -1.0
        return {"n": n, "hit": round(w / n, 4) if n else None, "roi": round(u / n, 4) if n else None}

    markets, buckets = {}, defaultdict(lambda: [0, 0, 0.0])
    for mkt, rows in sorted(scored.items()):
        cl = [r for r in rows if r["when"] == "close"]
        if len(cl) < 100: continue
        llm = sum(ll(r["p"], r["y"]) for r in cl) / len(cl)
        llq = sum(ll(r["q"], r["y"]) for r in cl) / len(cl)
        w_best = min((sum(ll(sig(a * lg(r["p"]) + (1 - a) * lg(r["q"])), r["y"]) for r in cl), a)
                     for a in [i / 20 for i in range(21)])[1]
        markets[mkt] = {
            "n": len(cl), "ll_model": round(llm, 4), "ll_market": round(llq, 4), "w_model": w_best,
            "roi": {when: {f"ev{int(t * 100)}": roi([r for r in rows if r["when"] == when], t) for t in (0.0, 0.05, 0.10)}
                    for when in ("open", "close")},
        }
        for r in cl:                                      # Best Bets play types, at the close, any +EV
            eo, eu = r["p"] * dec(r["o"]) - 1, (1 - r["p"]) * dec(r["u"]) - 1
            side, ev, px = ("over", eo, r["o"]) if eo >= eu else ("under", eu, r["u"])
            if ev < 0: continue
            b = buckets[f"{mkt}|{side}|{r['g']}"]
            win = r["y"] == (side == "over")
            b[0] += 1; b[1] += win; b[2] += (dec(px) - 1) if win else -1.0
        print(f"[prop-prior] {mkt:8s} n={len(cl):5d} | log-loss Vault {llm:.4f} vs market {llq:.4f} | best weight on Vault {w_best:.2f} "
              f"| ROI +EV close {markets[mkt]['roi']['close']['ev0']['roi']:+.3f} open {markets[mkt]['roi']['open']['ev0']['roi']:+.3f}")
    bk = {k: {"n": n, "W": w, "roi": round(u / n, 4), "veto": n >= MIN_VETO_N and u < 0} for k, (n, w, u) in sorted(buckets.items())}
    for k, v in bk.items():
        print(f"[prop-prior]   {k:22s} {v['n']:5d} bets ROI {v['roi']:+.3f}{'  VETO' if v['veto'] else ''}")
    print(f"[prop-prior] skipped: {dict(skipped)}")

    out = {"generated": datetime.now(timezone.utc).isoformat(), "source": "ESPN BET lines via ESPN core API",
           "seasons": list(SEASONS), "line_basis": "close (w_model, buckets); open + close (roi)",
           "min_veto_n": MIN_VETO_N, "markets": markets, "buckets": bk,
           "note": "Shipped prop_model.json replayed on real historical lines. No matchup/role multipliers. "
                   "w_model seeds the board's market blend; a bucket with veto=true cannot switch on in Best Bets."}
    if args.dry:
        print("[prop-prior] --dry: not written"); return
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"[prop-prior] wrote {OUT}")


if __name__ == "__main__":
    main()
