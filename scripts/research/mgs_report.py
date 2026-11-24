#!/usr/bin/env python3
"""Move grade search: print the sealed-set tables and the graded-play tables as Markdown rows (docs/sharps-v2-movegrade-search-results.md).

  python3 -I scripts/research/mgs_report.py scratch/mgs_sealed.json scratch/mgs_graded.json
"""
import json, math, sys

sealed, graded = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
LET = ("A", "B", "C", "D", "against", "None")


def fmt(c, scale=1.0, k=2):
    if not c or not c.get("n"):
        return "n=0"
    se = "" if c.get("se") is None else " (se %.*f)" % (k, c["se"] * scale)
    tag = ", small" if c["n"] < 30 else ""
    return "%+.*f%s, n=%d%s" % (k, c["mean"] * scale, se, c["n"], tag)


def sl(p, scale=1.0, k=3):
    if not p or p.get("slope") is None:
        return "n/a"
    s = "%+.*f [%+.*f, %+.*f]" % (k, p["slope"] * scale, k, p["lo"] * scale, k, p["hi"] * scale)
    if p.get("p") is not None:
        s += " p %.3f" % p["p"]
    if p.get("p_holm") is not None:
        s += " (Holm %.3f)" % p["p_holm"]
    return s


S = sealed["sealed"]
print("## sealed letters, pooled and by sport")
for grp in ("pooled", "nba", "nfl", "cfb", "cbb"):
    print("\n###", grp)
    print("| Letter | (a) after-cut, pts | (b) CLV vs best US price, pts | (c) ROI, pts | win % |")
    print("|---|---|---|---|---|")
    for L in LET:
        c = S["letters"][grp][L]
        print("| %s | %s | %s | %s | %s |" % (L, fmt(c["a"]), fmt(c["b"]), fmt(c["c"], 100, 1), fmt(c["w"], 100, 1)))
print("\n## sealed slopes (97.5%)")
for t, sc, k in (("a", 1, 3), ("c", 100, 2), ("w", 100, 2), ("b", 1, 3)):
    print(t, "pooled", sl(S["pooled"][t], sc, k), "|", " | ".join("%s %s" % (sp, sl(S["sport"][sp].get(t), sc, k)) for sp in S["sport"] if t in S["sport"][sp]))
print("\n## against vs D (sealed, 95%)")
for sid, v in sealed["against_vs_D"].items():
    for t, x in v.items():
        sc = 100 if t in ("c", "w") else 1
        print(sid, t, "against", fmt(x["against"], sc), "D", fmt(x["D"], sc), "diff %+.3f [%+.3f, %+.3f]" % (x["diff"] * sc, x["lo"] * sc, x["hi"] * sc))
print("\n## exploratory: all systems on sealed (95%, Holm)")
for sid, v in sealed["exploratory_all_sealed"].items():
    print("| %s | %s | %s |" % (sid, sl(v["pooled"]["a"]), sl(v["pooled"]["c"], 100, 2)))
print("\n## graded plays (report only)")
for key in ("S3", "mg1"):
    for grp in (("nba", "nfl", "cbb"), ("nba", "nfl", "cbb", "cfb")):
        print("\n###", key, "+".join(grp))
        print("| Letter | Record | Units | ROI (se) | (a) after-cut mean, n | (b) stored CLV mean, n |")
        print("|---|---|---|---|---|---|")
        for L in LET:
            ps = [p for p in graded if p["sport"] in grp and str(p[key]) == L]
            n = len(ps)
            if not n:
                print("| %s | n=0 | | | | |" % L)
                continue
            w = sum(p["res"] == "win" for p in ps); l = sum(p["res"] == "loss" for p in ps); pu = n - w - l
            u = sum(p["flat"] for p in ps); m = u / n
            se = math.sqrt(sum((p["flat"] - m) ** 2 for p in ps) / (n - 1)) / math.sqrt(n) if n > 1 else None
            af = [p["after"] for p in ps if p["after"] is not None]; cl = [p["clv"] for p in ps if p["clv"] is not None]
            print("| %s | %d-%d%s | %+.2fu | %+.1f%% (%s), n=%d%s | %s | %s |" % (
                L, w, l, ("-%d" % pu) if pu else "", u, 100 * m, ("%.1f" % (100 * se)) if se is not None else "none", n, ", small" if n < 30 else "",
                ("%+.2f, n=%d" % (sum(af) / len(af), len(af))) if af else "n=0", ("%+.2f, n=%d" % (sum(cl) / len(cl), len(cl))) if cl else "n=0"))
