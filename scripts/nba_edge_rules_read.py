#!/usr/bin/env python3
"""Read the NBA edge-rule forward test (docs/nba-edge-rules-prereg.md).

Reads nba/data/track.json 'cube' only. Prints, for the baseline window and the forward window, the
bet count, entry ROI, win rate and the 95% half-width for each frozen rule. Changes nothing.
Usage: python3 scripts/nba_edge_rules_read.py [--from 2026-11-19] [--to 2026-12-09]
"""
import json, math, sys, argparse

BASE_END = "2026-11-18"          # last in-sample day (registration date)
FWD_START = "2026-11-19"         # first forward day, Central

# Rule definitions are FROZEN. See the prereg doc.
CELLS = {("pra", "under"), ("3pm", "over"), ("pr", None), ("pa", None)}   # R3, None = either side

def load():
    d = json.load(open("nba/data/track.json"))
    c = d["cube_cols"]
    return [dict(zip(c, r)) for r in d["cube"]]

def tot(rows):
    n = sum(r["bets"] for r in rows)
    u = sum(r["units"] for r in rows)
    sq = sum(r["units_sq"] for r in rows)
    w = sum(r["w"] for r in rows); l = sum(r["l"] for r in rows)
    if n == 0:
        return dict(n=0, roi=None, hw=None, win=None)
    mean = u / n
    var = max(sq / n - mean * mean, 0)
    return dict(n=n, roi=mean, hw=1.96 * math.sqrt(var / n), win=w / max(1, w + l))

def fmt(t):
    if not t["n"]:
        return "n=0"
    return f"n={t['n']} ROI {100*t['roi']:+.1f}% (95% +/-{100*t['hw']:.1f}) win {100*t['win']:.1f}%"

def rules(rows):
    hi = lambda r: r["ebin"] == "12%+"
    mid = lambda r: r["ebin"] in ("3-5%", "5-8%", "8-12%")
    cell = lambda r: (r["stat"], r["side"]) in CELLS or (r["stat"], None) in CELLS
    return {
        "R1 12%+ edge (capped)":            [r for r in rows if hi(r)],
        "R1 control: 3-12% edge":           [r for r in rows if mid(r)],
        "R2 both sources agree":            [r for r in rows if r["etype"] == "both"],
        "R2 control: gap or model alone":   [r for r in rows if r["etype"] in ("gap", "model")],
        "R3 down-rank cells at 12%+":       [r for r in rows if hi(r) and cell(r)],
        "ALL (bet everything)":             rows,
    }

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="a", default=FWD_START)
    ap.add_argument("--to", dest="b", default="9999-12-31")
    a = ap.parse_args()
    rows = load()
    for title, sel in (("BASELINE (in-sample, through " + BASE_END + ")", lambda r: r["day"] <= BASE_END),
                       (f"FORWARD ({a.a} to {a.b})", lambda r: a.a <= r["day"] <= a.b)):
        print("==", title)
        for k, v in rules([r for r in rows if sel(r)]).items():
            print(f"  {k:34s} {fmt(tot(v))}")
