#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · POLYMARKET NFL ACCOUNT SCORECARD  →  data/pm_wallets.json
#
#  "Where is the sharp money?" Polymarket's trade tape is public and every
#  trade carries the account (proxyWallet) that made it, so accounts can be
#  scored on their own record. Unit: $1k+ AGGRESSOR (taker) trades on a game's
#  full-game moneyline before kickoff (the trades API only reaches the newest
#  10k trades per market, which in-game trading fills; $1k+ taker trades
#  reach weeks back). Score per trade = closing line value: the closing price
#  of the side bought / the price paid - 1 (close = last trade before kickoff).
#
#  Study, 2026-09-28 (613 settled games, Sep 2024 - Sep 2026, 31k trades;
#  accounts scored walk-forward on games BEFORE each game only):
#    · accounts with a CLV t-stat >= 2 over 10+ trades / 5+ games kept beating
#      the close (+0.38%/trade, t 7); t <= -2 accounts kept losing (-0.90%,
#      t -21). Skill persists.
#    · but by kickoff the price has priced them in: the side they net-bought
#      won no more often than the closing price said (58.1% vs 59.2%, n 260),
#      and copying them 30 min - 2 h later got -0.19% vs the close (2-6 h:
#      -0.90%). The edge lasts minutes, Vault polls hourly. So this is context
#      (where informed money went), NEVER shown as a bet to copy.
#
#  Incremental: `processed` lists finished games; each run adds newly closed
#  NFL games' trades to the per-account aggregates [n, sum, sumsq, games].
#  Bootstrap: --seed=<dir of cached game files from the study>.
#
#  Sports: --sport=nfl (default, data/pm_wallets.json), cfb, nba
#  (data/pm_wallets_<sport>.json). Same unit and rule for every sport; each is
#  scored only on its own games. CFB/NBA events are listed by Polymarket
#  series id (their tag listings are dominated by futures).
#
#  Usage: python3 scripts/build_pm_wallets.py [--sport=nfl] [--max=60] [--dry]
# ════════════════════════════════════════════════════════════════════════════
import json, math, os, re, sys, time, urllib.request, glob
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SPORTS = {"nfl": {"series": 12185, "out": "pm_wallets.json", "skip_months": ("07", "08")},
          "cfb": {"series": 12756, "out": "pm_wallets_cfb.json", "skip_months": ()},
          "nba": {"series": 10345, "out": "pm_wallets_nba.json", "skip_months": ("07", "08", "09")}}
SPORT = "nfl"
OUT = os.path.join(HERE, "..", "data", "pm_wallets.json")
UA = {"User-Agent": "VaultFantasy/1.0 (+vaultfantasy.com)", "Accept": "application/json"}
GAME_RE = re.compile(r"^nfl-[a-z]{2,3}-[a-z]{2,3}-(\d{4}-\d{2}-\d{2})$")


def set_sport(sp):
    global SPORT, OUT, GAME_RE
    SPORT = sp
    OUT = os.path.join(HERE, "..", "data", SPORTS[sp]["out"])
    GAME_RE = re.compile(r"^" + sp + r"-[a-z0-9]{2,8}-[a-z0-9]{2,8}-(\d{4}-\d{2}-\d{2})$")
BIG = 1000              # $ per trade
MIN_N, MIN_GAMES, T_SHARP = 10, 5, 2.0


def get(url, tries=3):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except Exception as e:
            if "400" in str(e): return []
            time.sleep(2 + 3 * i)
    return None


def closed_games():
    out = []
    src = "tag_slug=nfl" if SPORT == "nfl" else f"series_id={SPORTS[SPORT]['series']}"
    for off in range(0, 5000, 100):
        r = get(f"https://gamma-api.polymarket.com/events?closed=true&limit=100&offset={off}&{src}&order=endDate&ascending=false")
        if not r: break
        out += [e for e in r if GAME_RE.match(e.get("slug") or "")]
        if len(r) < 100: break
    # regular season + playoffs only (preseason games are backups)
    return [e for e in out if GAME_RE.match(e["slug"]).group(1)[5:7] not in SPORTS[SPORT]["skip_months"]]


def game_record(e):
    """{slug, start, close0, big:[[wallet, ts, outcomeIndex, side, price, size]]} or None."""
    ms = [m for m in e.get("markets") or [] if m.get("sportsMarketType") == "moneyline"] \
        or [m for m in e.get("markets") or [] if len(json.loads(m.get("outcomes") or "[]")) == 2 and "vs" in (m.get("question") or "")]
    if not ms: return None
    ml = max(ms, key=lambda m: float(m.get("volumeNum") or 0))
    gst = (ml.get("gameStartTime") or e.get("endDate") or "").replace(" ", "T").replace("Z", "+00:00")
    if gst.endswith("+00"): gst += ":00"
    try: start = datetime.fromisoformat(gst).timestamp()
    except Exception: return None
    cid, big, off = ml["conditionId"], [], 0
    while off < 10000:
        r = get(f"https://data-api.polymarket.com/trades?market={cid}&limit=500&offset={off}&takerOnly=true&filterType=CASH&filterAmount={BIG}")
        if not r: break
        big += [[t["proxyWallet"], t["timestamp"], t["outcomeIndex"], t["side"], round(t["price"], 4), round(t["size"], 2)]
                for t in r if t["timestamp"] < start]
        if len(r) < 500: break
        off += 500
    close, off = None, 0
    while off < 10000 and close is None:
        r = get(f"https://data-api.polymarket.com/trades?market={cid}&limit=500&offset={off}")
        if not r: break
        pre = [t for t in r if t["timestamp"] < start]
        if pre:
            t = max(pre, key=lambda t: t["timestamp"])
            close = t["price"] if t["outcomeIndex"] == 0 else 1 - t["price"]
        if len(r) < 500: break
        off += 500
    if close is None and big:
        b = max(big, key=lambda x: x[1]); close = b[4] if b[2] == 0 else 1 - b[4]
    return {"slug": e["slug"], "start": start, "close0": close, "big": big}


def add_game(W, g):
    c0 = g.get("close0")
    if c0 is None or not (0.03 < c0 < 0.97): return 0
    seen, n = set(), 0
    for w, ts, oi, side, p, size in g["big"]:
        if not (0.02 < p < 0.98): continue
        k, q = (oi, p) if side == "BUY" else (1 - oi, 1 - p)
        clv = (c0 if k == 0 else 1 - c0) / q - 1
        a = W.setdefault(w, [0, 0.0, 0.0, 0])
        a[0] += 1; a[1] += clv; a[2] += clv * clv
        if w not in seen: a[3] += 1; seen.add(w)
        n += 1
    return n


def classify(a):
    n, s, ss, gms = a
    if n < MIN_N or gms < MIN_GAMES: return None, None
    m = s / n; var = max(ss / n - m * m, 0)
    t = m / math.sqrt(var / n) if var > 0 else 0
    return ("sharp" if t >= T_SHARP else "dull" if t <= -T_SHARP else None), t


def main():
    args = dict(a.lstrip("-").split("=", 1) if "=" in a else (a.lstrip("-"), True) for a in sys.argv[1:])
    set_sport(args.get("sport", "nfl"))
    try: S = json.load(open(OUT))
    except Exception: S = {"processed": [], "wallets": {}}
    W, done = S.get("wallets") or {}, set(S.get("processed") or [])
    added = 0
    if args.get("seed"):
        for f in sorted(glob.glob(os.path.join(args["seed"], "*.json"))):
            g = json.load(open(f))
            if g["slug"] in done: continue
            add_game(W, g); done.add(g["slug"]); added += 1
    else:
        now = time.time()
        todo = [e for e in closed_games() if e["slug"] not in done]
        todo = todo[: int(args.get("max", 60))]
        with ThreadPoolExecutor(6) as ex:
            for g in ex.map(game_record, todo):
                if not g or g["start"] > now - 6 * 3600: continue      # settled games only
                if args.get("cache"):                                  # keep raw games for walk-forward studies
                    os.makedirs(args["cache"], exist_ok=True)
                    json.dump(g, open(os.path.join(args["cache"], g["slug"] + ".json"), "w"))
                add_game(W, g); done.add(g["slug"]); added += 1
    cls = {w: classify(a) for w, a in W.items()}
    sharp = sorted([w for w, (c, t) in cls.items() if c == "sharp"])
    dull = sorted([w for w, (c, t) in cls.items() if c == "dull"])
    out = {"generated": datetime.now(timezone.utc).isoformat(), "sport": SPORT, "unit": f"${BIG}+ taker trades, full-game moneyline, pre-kickoff",
           "rule": {"min_trades": MIN_N, "min_games": MIN_GAMES, "t": T_SHARP},
           "study": None if SPORT != "nfl" else {"games": 613, "sharp_clv_after": 0.0038, "dull_clv_after": -0.0090,
                     "sharp_side_won": [151, 260], "close_said": 0.592, "follow_30m_2h_clv": -0.0019,
                     "note": "Skill persists, but the edge is gone within about 30 minutes of the trade; by kickoff the price has priced it in. Context only, not a bet to copy."},
           "sharp": sharp, "dull": dull, "processed": sorted(done), "wallets": W}
    print(f"[pm-wallets:{SPORT}] +{added} games -> {len(done)} total · {len(W)} accounts · {len(sharp)} sharp · {len(dull)} dull")
    if args.get("dry"): return
    json.dump(out, open(OUT, "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
