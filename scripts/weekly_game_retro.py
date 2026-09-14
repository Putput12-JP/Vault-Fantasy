#!/usr/bin/env python3
# ============================================================================
# VAULT · WEEKLY GAME-MARKET RETRO
#
# The game-market sibling of scripts/weekly_prop_retro.py. Reads the same
# settlement tape (data/bet_results.json → `games`) and reports how Vault's
# spread / total / moneyline calls did, settled vs the final score.
#
# READ THIS DIFFERENTLY FROM THE PROP RETRO. The game model is built to HUG the
# market (it lands within ~0.4pt of the number), so it is context, not an edge
# play. That means ATS / O-U / ML win% is almost pure variance at a weekly
# sample — a bad week is a bad beat, not a broken model. The low-variance reads
# are what this retro leads with:
#   • CLV — did the line move to Vault's side by close (accrues every week)
#   • projection bias — does Vault's spread/total number run high or low vs the
#     actual margin/total (the game analog of the prop proj_adj signal)
#   • ML calibration — model vs vig-free-market log-loss + Brier
#
# It also SPLITS preseason-rated games (model_offseason) from in-season ones:
# early-season games are priced off preseason team ratings until the in-season
# model has enough games, so pooling them muddies the read.
#
# Deterministic body (no wall-clock) so the committed doc changes only when the
# numbers do. Pure standard library.
#
# Usage:
#   python3 scripts/weekly_game_retro.py                 # latest settled week
#   python3 scripts/weekly_game_retro.py --week 1
#   python3 scripts/weekly_game_retro.py --all           # every settled week pooled
#   python3 scripts/weekly_game_retro.py --no-write       # console only
# ============================================================================
import json, math, os, argparse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
RETRO_DIR = os.path.join(ROOT, "docs", "retro")

EPS = 1e-6
MKL = {"spread": "Spread", "total": "Total", "ml": "Moneyline"}
MK_ORDER = ["spread", "total", "ml"]


def clamp(p, lo=EPS, hi=1 - EPS): return max(lo, min(hi, p))
def logloss1(y, p): p = clamp(p); return -(y * math.log(p) + (1 - y) * math.log(1 - p))
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None
def pct(x): return "  -  " if x is None else f"{x*100:4.1f}%"
def sgn(x): return "  -  " if x is None else f"{x:+.1f}"


def load_games(week_filter):
    d = json.load(open(os.path.join(DATA, "bet_results.json")))
    games = [g for g in d.get("games", []) if g.get("market") and g.get("market") != "final"]
    weeks = sorted({g.get("week") for g in games if g.get("week") is not None})
    if week_filter == "all":
        sel, label = games, (f"weeks {weeks[0]}-{weeks[-1]}" if weeks else "all")
    else:
        wk = week_filter if week_filter is not None else (weeks[-1] if weeks else None)
        sel, label = [g for g in games if g.get("week") == wk], f"week {wk}"
    return d.get("generated"), label, weeks, sel


def _side(g):
    if g["market"] == "total":
        return "Under" if g.get("side") == "under" else "Over"
    return "Home" if g.get("side") == "home" else "Away"


def summarize(rows):
    """Record + CLV + projection bias (spread/total) + ML calibration."""
    graded = [g for g in rows if g.get("won_close") is not None and not g.get("push")]
    n = len(graded)
    if not n:
        return None
    w = sum(g["won_close"] for g in graded)
    beat = [g["beat_close"] for g in graded if g.get("beat_close") is not None]
    # projection error (spread/total only — margin/total points)
    perr = [g["proj_err"] for g in graded if g.get("proj_err") is not None]
    # ML calibration: model vs vig-free market
    ml = [logloss1(g["won_close"], g["p_model"]) for g in graded if g.get("p_model") is not None]
    kl = [logloss1(g["won_close"], g["p_market"]) for g in graded if g.get("p_market") is not None]
    brier = [(g["p_home"] - g["y_home"]) ** 2 for g in graded
             if g.get("p_home") is not None and g.get("y_home") is not None]
    m_ll, x_ll = mean(ml), mean(kl)
    return {
        "n": n, "rec": f"{int(w)}-{n-int(w)}", "wr": w / n,
        "clv_beat": mean(beat),
        "n_proj": len(perr), "mae": mean([abs(e) for e in perr]) if perr else None, "bias": mean(perr),
        "model_ll": m_ll, "market_ll": x_ll,
        "edge_ll": (x_ll - m_ll) if (m_ll is not None and x_ll is not None) else None,
        "brier": mean(brier),
    }


def group_table(rows, keyfn, order=None):
    g = defaultdict(list)
    for r in rows:
        k = keyfn(r)
        if k is not None:
            g[k].append(r)
    keys = order or sorted(g)
    out = []
    for k in keys:
        if g.get(k):
            s = summarize(g[k])
            if s:
                out.append((k, s))
    return out


def fmt_market_row(name, s):
    base = (f"{name:10s} n={s['n']:3d} {s['rec']:>7s} {pct(s['wr'])} | CLV {pct(s['clv_beat'])}")
    if s["n_proj"]:
        base += f" | projMAE {s['mae']:5.1f} bias {sgn(s['bias'])}"
    if s["edge_ll"] is not None:
        base += f" | ll m{s['model_ll']:.3f} x{s['market_ll']:.3f}"
    return base


def find_findings(rows):
    f = []
    ins = [g for g in rows if not g.get("model_offseason")]
    for mk in MK_ORDER:
        s = summarize([g for g in ins if g["market"] == mk])
        if not s:
            continue
        if s["n_proj"] and s["mae"] and abs(s["bias"] or 0) / max(s["mae"], EPS) > 0.35 and s["n_proj"] >= 8:
            d = "runs high" if s["bias"] > 0 else "runs low"
            f.append(("bias", f"{MKL[mk]}: Vault's number {d} vs actual by {abs(s['bias']):.1f} "
                              f"({s['n_proj']} in-season games) — track it; too thin to correct yet"))
        if s["edge_ll"] is not None and s["edge_ll"] < -0.02 and s["n"] >= 10:
            f.append(("vs-market", f"{MKL[mk]}: market prices win-prob better (log-loss {-s['edge_ll']:+.3f} worse) "
                                   "— expected while the model hugs the line"))
    o = summarize(ins)
    if o and o["clv_beat"] is not None and o["clv_beat"] < 0.45 and o["n"] >= 20:
        f.append(("clv", f"CLV beat-rate {pct(o['clv_beat'])} in-season — the line is not moving to Vault's side; "
                         "the number is not leading the market yet (at this sample, still mostly noise)"))
    return f


def render(label, rows):
    lines = []
    P = lines.append
    off = [g for g in rows if g.get("model_offseason")]
    ins = [g for g in rows if not g.get("model_offseason")]
    o = summarize(rows)
    o_in = summarize(ins)
    P(f"# Game-market retro — {label}")
    P("")
    settled = o["n"] if o else 0
    P(f"_{settled} game calls settled ({len(ins)} in-season-rated, {len(off)} preseason-rated)._")
    P("")
    P("## Read this differently from props")
    P("")
    P("Vault's game model is built to **hug the market** (it lands within ~0.4pt of the number), "
      "so it is context, not an edge play. At a weekly sample the ATS / over-under / moneyline "
      "win% is almost pure variance — a rough week is a bad beat, not a broken model. Lead with "
      "**CLV** and **projection bias**; treat the win-loss as noise until the sample is large.")
    P("")
    if o:
        P("## Headline")
        P("")
        P(f"- **Record (all):** {o['rec']} ({pct(o['wr'])}) · **CLV beat-rate** {pct(o['clv_beat'])}")
        if o_in:
            P(f"- **In-season-rated only:** {o_in['rec']} ({pct(o_in['wr'])}) · CLV {pct(o_in['clv_beat'])}")
        if off:
            so = summarize(off)
            if so:
                P(f"- **Preseason-rated only:** {so['rec']} ({pct(so['wr'])}) — priced off preseason team "
                  "ratings; excluded from the diagnostics below")
        P("")
    # by market (in-season is the clean slice; fall back to all if none)
    base = ins if ins else rows
    slice_lbl = "in-season-rated" if ins else "all"
    P(f"## By market ({slice_lbl})")
    P("")
    P("```")
    for mk in MK_ORDER:
        s = summarize([g for g in base if g["market"] == mk])
        if s:
            P(fmt_market_row(MKL[mk], s))
    P("```")
    P("- projMAE/bias: how far Vault's spread/total number lands from the actual margin/total "
      "(bias +high = Vault's number ran high). ll m/x: model vs vig-free-market log-loss on moneyline.")
    P("")
    # by side
    P(f"## By side ({slice_lbl})")
    P("")
    P("```")
    for k, s in group_table(base, _side, ["Home", "Away", "Over", "Under"]):
        P(f"{k:6s} n={s['n']:3d} {s['rec']:>7s} {pct(s['wr'])} | CLV {pct(s['clv_beat'])}")
    P("```")
    P("")
    # best/worst by CLV (the low-variance read)
    ranked = [(MKL[mk], summarize([g for g in base if g["market"] == mk])) for mk in MK_ORDER]
    ranked = [(k, s) for k, s in ranked if s and s["clv_beat"] is not None]
    if ranked:
        ranked.sort(key=lambda kv: -kv[1]["clv_beat"])
        best, worst = ranked[0], ranked[-1]
        P("## Sharpest / softest market (by CLV)")
        P("")
        P(f"- **Sharpest: {best[0]}** — CLV {pct(best[1]['clv_beat'])}, {best[1]['rec']} ({pct(best[1]['wr'])})")
        if worst[0] != best[0]:
            P(f"- **Softest: {worst[0]}** — CLV {pct(worst[1]['clv_beat'])}, {worst[1]['rec']} ({pct(worst[1]['wr'])})")
        P("")
    # flags
    P("## Flags")
    P("")
    findings = find_findings(rows)
    if findings:
        for tag, msg in findings:
            P(f"- **[{tag}]** {msg}")
    else:
        P("- Nothing tripped the thresholds this slice.")
    P("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    generated, label, weeks, rows = load_games("all" if args.all else args.week)
    if not rows:
        print(f"[game-retro] no settled games for {label} (settled weeks: {weeks})")
        return
    report = render(label, rows)
    print(f"[game-retro] settlement tape generated {generated}")
    print(report)

    if args.no_write:
        return
    os.makedirs(RETRO_DIR, exist_ok=True)
    slug = "all-weeks" if args.all else f"week-{label.split()[-1]}"
    path = os.path.join(RETRO_DIR, f"game-retro-{slug}.md")
    with open(path, "w") as fh:
        fh.write(report + "\n---\n_Auto-generated by `scripts/weekly_game_retro.py` off the "
                          "settlement tape; refreshes with each settle. See git history for dates._\n")
    print(f"\n[game-retro] wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
