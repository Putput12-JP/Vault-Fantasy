#!/usr/bin/env python3
"""
Grade the sharp tape (docs/sharp-speed-prereg.md): the CLV a follower gets by buying at the ask when a tiered wallet's buy is first seen.

  follow  buy the wallet's outcome at `ask` (the best ask when the trade was first read).   CLV = close - ask
  fade    buy the OTHER outcome at `opp_ask`.                                               CLV = (1 - close) - opp_ask
  wallet  the wallet's own price: close - px, and the slip = ask - px (what the delay cost a follower), for context.

Sharp wallets are tested as `follow`, dull wallets as `fade`; mid wallets are the control (both, as a baseline any wallet's buy is worth).
Only on-time rows count (`late` false, a stored ask, a stored close). The close is the last quote before kickoff from data/pm_closes.json,
matched on event, market type, line and outcome list (grade_side_cards.close_for); a row with no close is counted, never estimated.

A clear must also hold the same sign in the first and second half of the sample (by game date), reported as `halves`.
One observation per wallet x game x market type x play: the mean over its rungs, so a wallet laying twenty rungs of one total counts once.
Standard errors are clustered by game (wallets in one game share a close). A test is "cleared" when n >= MIN_N observations and the mean CLV is
above zero by CLEAR_SE standard errors. Markouts: what the same side's BID is worth 1, 5 and 15 minutes after detection against the ask paid.

Usage: python3 scripts/grade_sharp_tape.py --tape DIR --closes data/pm_closes.json --out FILE
"""
import argparse, collections, glob, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grade_side_cards import close_for  # noqa: E402

MIN_N, CLEAR_SE = 100, 2.0
GROUP = {"ml": "ml", "spread": "spread", "total": "total"}
BUCKETS = ((0, 120), (120, 240), (240, 300))


def load(tape):
    """{sport: [rows]} and {key: {dt: markout row}} from <tape>/<sport>/*.jsonl."""
    trades, marks = collections.defaultdict(list), collections.defaultdict(dict)
    for p in sorted(glob.glob(os.path.join(tape, "*", "*.jsonl"))):
        sport = os.path.basename(os.path.dirname(p))
        with open(p) as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("k") == "t":
                    trades[sport].append(r)
                elif r.get("k") == "m":
                    marks[r["of"]][r["dt"]] = r
    return trades, marks


def plays_of(r):
    """[(play, price paid, outcome index bought)] a row stands for: sharp follows, dull is faded, mid is both (control)."""
    out = []
    if r["tier"] in ("sharp", "mid") and r.get("ask") is not None:
        out.append(("follow", r["ask"], r["oi"]))
    if r["tier"] in ("dull", "mid") and r.get("opp_ask") is not None:
        out.append(("fade", r["opp_ask"], 1 - r["oi"]))
    return out


def observations(rows, closes, sport):
    """One per wallet x event x market type x line x play: {clv, wallet_clv, slip, lat, ev, tier, play, group, spread}. Skips late rows and rows
    with no ask or no stored close; `no_close` counts the latter."""
    grp, no_close, late = {}, 0, 0
    for r in rows:
        if r.get("late"):
            late += 1
            continue
        for play, price, oi in plays_of(r):
            c = close_for(closes, sport, r["ev"].split("-spread")[0].split("-total")[0], r["mt"], r.get("line"), r["outs"], r["outs"][oi])
            if c is None:
                no_close += 1
                continue
            k = (r["w"], r["ev"], r["mt"], r.get("line"), play)
            g = grp.setdefault(k, {"tier": r["tier"], "ev": r["ev"], "group": r["mt"], "play": play, "clv": [], "wclv": [], "slip": [], "lat": []})
            g["clv"].append(c - price)
            wc = close_for(closes, sport, r["ev"].split("-spread")[0].split("-total")[0], r["mt"], r.get("line"), r["outs"], r["outs"][r["oi"]])
            if wc is not None and r.get("px") is not None:
                g["wclv"].append((wc - r["px"]) if play == "follow" else ((1 - wc) - (1 - r["px"])))
            if play == "follow" and r.get("px") is not None:
                g["slip"].append(price - r["px"])
            g["lat"].append(r["lat"])
    obs = []
    for g in grp.values():
        m = lambda xs: sum(xs) / len(xs) if xs else None      # noqa: E731
        obs.append({**{k: g[k] for k in ("tier", "ev", "group", "play")}, "day": g["ev"][-10:], "clv": m(g["clv"]), "wallet_clv": m(g["wclv"]), "slip": m(g["slip"]),
                    "lat": min(g["lat"])})
    return obs, no_close, late


def cluster_mean(obs, key="clv"):
    """(n, mean, se) of `key` over observations, SE clustered by game: the game's observation sum is the unit."""
    xs = [(o["ev"], o[key]) for o in obs if o.get(key) is not None]
    n = len(xs)
    if n < 2:
        return {"n": n, "mean": xs[0][1] if n else None, "se": None, "games": len({e for e, _ in xs})}
    m = sum(x for _, x in xs) / n
    by = collections.defaultdict(float)
    for e, x in xs:
        by[e] += x - m
    g = len(by)
    se = math.sqrt(g / (g - 1) * sum(v * v for v in by.values())) / n if g > 1 else None
    return {"n": n, "mean": round(m, 5), "se": round(se, 5) if se is not None else None, "games": g}


def read(stats):
    """'cleared' when n >= MIN_N and mean - CLEAR_SE * se > 0; 'not_cleared' at n >= MIN_N otherwise; 'too_few' under MIN_N."""
    if stats["n"] < MIN_N or stats["se"] is None:
        return "too_few"
    return "cleared" if stats["mean"] - CLEAR_SE * stats["se"] > 0 else "not_cleared"


def markouts(rows, marks, closes_ok):
    """Mean (bid after dt) - (ask paid) for follows of on-time rows: what a follower could sell for, per delay. Context only."""
    out = {}
    for d in (60, 300, 900):
        xs = []
        for r in rows:
            m = (marks.get(r["key"]) or {}).get(d)
            if r.get("late") or r.get("ask") is None or not m or m.get("bid") is None:
                continue
            xs.append(m["bid"] - r["ask"])
        out[str(d)] = {"n": len(xs), "mean": round(sum(xs) / len(xs), 5) if xs else None}
    return out


def grade(tape, closes):
    trades, marks = load(tape)
    res = {"min_n": MIN_N, "clear_se": CLEAR_SE, "sports": {}}
    for sport, rows in sorted(trades.items()):
        obs, no_close, late = observations(rows, closes, sport)
        s = {"rows": len(rows), "late": late, "no_close": no_close, "tests": {}, "markouts": markouts(rows, marks, None)}
        for tier, play in (("sharp", "follow"), ("dull", "fade"), ("mid", "follow"), ("mid", "fade")):
            sub = [o for o in obs if o["tier"] == tier and o["play"] == play]
            st = cluster_mean(sub)
            st["read"] = read(st)
            st["wallet_clv"] = cluster_mean(sub, "wallet_clv")["mean"]
            st["slip"] = cluster_mean(sub, "slip")["mean"] if play == "follow" else None
            days = sorted(o["day"] for o in sub)
            mid = days[len(days) // 2] if days else None          # halves by game date: a clear must hold the same sign in both
            st["halves"] = [cluster_mean([o for o in sub if o["day"] < mid]) if mid else None, cluster_mean([o for o in sub if o["day"] >= mid]) if mid else None]
            st["by_group"] = {g: cluster_mean([o for o in sub if o["group"] == g]) for g in ("ml", "spread", "total")}
            st["by_latency"] = {f"{lo}-{hi}s": cluster_mean([o for o in sub if lo <= o["lat"] < hi]) for lo, hi in BUCKETS}
            s["tests"][f"{tier}:{play}"] = st
        res["sports"][sport] = s
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tape", required=True)
    ap.add_argument("--closes", default="data/pm_closes.json")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    closes = json.load(open(a.closes))
    out = grade(a.tape, closes)
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    for sport, s in out["sports"].items():
        for k, v in s["tests"].items():
            print(sport, k, v["n"], v["mean"], v["se"], v["read"])


if __name__ == "__main__":
    main()
