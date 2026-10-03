#!/usr/bin/env python3
# Spread/total sharp-account test. Rules: docs/pm-spread-total-test.md (committed before this ran).
# Usage: python3 scripts/pm_spread_total_test.py [--max=120] [--sports=nfl,cfb,nba] [--cache=DIR]
import json, math, os, sys, time, glob
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_pm_wallets as B
KINDS = {"moneyline": "ml", "spreads": "sp", "totals": "tot"}


def best(e, kind):
    ms = [m for m in e.get("markets") or [] if m.get("sportsMarketType") == kind]
    return max(ms, key=lambda m: float(m.get("volumeNum") or 0)) if ms else None


def market_trades(m, start):
    cid, big, off = m["conditionId"], [], 0
    while off < 10000:
        r = B.get(f"https://data-api.polymarket.com/trades?market={cid}&limit=500&offset={off}&takerOnly=true&filterType=CASH&filterAmount={B.BIG}")
        if not r: break
        big += [[t["proxyWallet"], t["timestamp"], t["outcomeIndex"], t["side"], round(t["price"], 4)] for t in r if t["timestamp"] < start]
        if len(r) < 500: break
        off += 500
    close, off = None, 0
    while off < 10000 and close is None:
        r = B.get(f"https://data-api.polymarket.com/trades?market={cid}&limit=500&offset={off}")
        if not r: break
        pre = [t for t in r if t["timestamp"] < start]
        if pre:
            t = max(pre, key=lambda t: t["timestamp"]); close = t["price"] if t["outcomeIndex"] == 0 else 1 - t["price"]
        if len(r) < 500: break
        off += 500
    if close is None and big:
        b = max(big, key=lambda x: x[1]); close = b[4] if b[2] == 0 else 1 - b[4]
    return close, big


def game(e):
    out = {"slug": e["slug"], "mk": {}}
    for kind in KINDS:
        m = best(e, kind)
        if not m: continue
        gst = (m.get("gameStartTime") or e.get("endDate") or "").replace(" ", "T").replace("Z", "+00:00")
        if gst.endswith("+00"): gst += ":00"
        try: start = datetime.fromisoformat(gst).timestamp()
        except Exception: continue
        out["start"] = start
        close, big = market_trades(m, start)
        out["mk"][KINDS[kind]] = {"close": close, "big": big, "vol": float(m.get("volumeNum") or 0)}
    return out if "start" in out else None


def trades(g, mk):
    """yield (wallet, clv, game slug) for $1k+ pre-kickoff trades."""
    d = g["mk"].get(mk)
    if not d or d["close"] is None or not (0.03 < d["close"] < 0.97): return
    for w, ts, oi, side, p in d["big"]:
        if not (0.02 < p < 0.98): continue
        k, q = (oi, p) if side == "BUY" else (1 - oi, 1 - p)
        yield w, (d["close"] if k == 0 else 1 - d["close"]) / q - 1


def stats(xs):
    n = len(xs)
    if n < 2: return {"n": n}
    m = sum(xs) / n; v = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(v / n); return {"n": n, "mean": m, "se": se, "t": m / se if se else 0}


def main():
    args = dict(a.lstrip("-").split("=", 1) if "=" in a else (a.lstrip("-"), True) for a in sys.argv[1:])
    res = {"generated": datetime.now(timezone.utc).isoformat(), "sports": {}}
    for sp in args.get("sports", "nfl,cfb,nba").split(","):
        B.set_sport(sp)
        lab = json.load(open(B.OUT)); sharp, dull = set(lab["sharp"]), set(lab["dull"])
        now = time.time(); todo = B.closed_games()[: int(args.get("max", 120))]
        G = []
        cdir = os.path.join(args["cache"], sp) if args.get("cache") else None
        if cdir: os.makedirs(cdir, exist_ok=True)
        with ThreadPoolExecutor(6) as ex:
            for g in ex.map(game, todo):
                if g and g["start"] < now - 6 * 3600: G.append(g)
        if cdir:
            for g in G: json.dump(g, open(os.path.join(cdir, g["slug"] + ".json"), "w"))
        G.sort(key=lambda g: g["start"])
        out = {"games": len(G), "depth": {}, "transfer": {}, "own": {}}
        for mk in KINDS.values():
            per = [sum(1 for _ in trades(g, mk)) for g in G if mk in g["mk"]]
            out["depth"][mk] = {"games": len(per), "trades_per_game": sum(per) / max(len(per), 1)}
            buckets = {"sharp": [], "dull": [], "other": []}
            for g in G:
                for w, c in trades(g, mk): buckets["sharp" if w in sharp else "dull" if w in dull else "other"].append(c)
            out["transfer"][mk] = {k: stats(v) for k, v in buckets.items()}
            # own-market: label on first half, test on second half
            h = len(G) // 2; acc = {}
            for g in G[:h]:
                seen = set()
                for w, c in trades(g, mk):
                    a = acc.setdefault(w, [0, 0.0, 0.0, 0]); a[0] += 1; a[1] += c; a[2] += c * c
                    if w not in seen: a[3] += 1; seen.add(w)
            lab1 = {}
            for w, (n, s, ss, gm) in acc.items():
                if n >= B.MIN_N and gm >= B.MIN_GAMES:
                    m = s / n; var = max(ss / n - m * m, 0); t = m / math.sqrt(var / n) if var > 0 else 0
                    lab1[w] = "sharp" if t >= B.T_SHARP else "dull" if t <= -B.T_SHARP else None
            second = {"sharp": [], "dull": []}
            for g in G[h:]:
                for w, c in trades(g, mk):
                    if lab1.get(w): second[lab1[w]].append(c)
            out["own"][mk] = {"labelled": {k: sum(1 for v in lab1.values() if v == k) for k in ("sharp", "dull")}, **{k: stats(v) for k, v in second.items()}}
        res["sports"][sp] = out
        print(sp, json.dumps(out)[:2000], flush=True)
    json.dump(res, open(os.path.join(HERE, "..", "data", "pm_spread_total_test.json"), "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
