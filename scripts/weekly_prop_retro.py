#!/usr/bin/env python3
# ============================================================================
# VAULT · WEEKLY PLAYER-PROP RETRO
#
# A repeatable post-week retro on how Vault's OWN prop projections did, read
# straight from the settlement tape (data/bet_results.json) that
# scripts/settle_bets.py writes. Answers the four standing questions:
#
#   1. How did the model do?          → record, CLV beat-rate, calibration
#   2. Where can we get sharper?      → per-market projection bias + log-loss gap
#   3. How did we do vs the market?   → model vs vig-free-close log-loss + CLV
#   4. What category did best & why?  → ranked by an edge score, luck-flagged
#
# The "vs industry tools" read is the closing line: the sharpest number anyone
# posts. Beating it (CLV+, lower log-loss) is a real edge; winning while the
# close moved AGAINST us (win% high, CLV low) is variance, and gets flagged.
#
# Pure standard library. Emits a console summary AND a markdown file under
# docs/retro/ so each week is diffable and shareable.
#
# Usage:
#   python3 scripts/weekly_prop_retro.py                 # latest settled week
#   python3 scripts/weekly_prop_retro.py --week 1
#   python3 scripts/weekly_prop_retro.py --all           # every settled week pooled
#   python3 scripts/weekly_prop_retro.py --no-write       # console only
# ============================================================================
import json, math, os, argparse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
RETRO_DIR = os.path.join(ROOT, "docs", "retro")

EPS = 1e-6
BREAK_EVEN = 0.5238        # -110/-110 two-way price: win rate needed to profit


def clamp(p, lo=EPS, hi=1 - EPS): return max(lo, min(hi, p))
def logloss1(y, p): p = clamp(p); return -(y * math.log(p) + (1 - y) * math.log(1 - p))
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None
def pct(x): return "  -  " if x is None else f"{x*100:4.1f}%"
def sgn(x): return "  -  " if x is None else f"{x:+.2f}"


def load_props(week_filter):
    d = json.load(open(os.path.join(DATA, "bet_results.json")))
    props = d.get("props", [])
    weeks = sorted({p.get("week") for p in props if p.get("week") is not None})
    if week_filter == "all":
        sel, label = props, f"weeks {weeks[0]}-{weeks[-1]}" if weeks else "all"
    else:
        wk = week_filter if week_filter is not None else (weeks[-1] if weeks else None)
        sel, label = [p for p in props if p.get("week") == wk], f"week {wk}"
    return d.get("generated"), label, weeks, sel


def summarize(rows):
    """Core stats over a slice of settled props (pushes/no-side excluded from
    win/CLV/log-loss; projection error uses every row that has proj + actual)."""
    graded = [r for r in rows if r.get("won_close") is not None and not r.get("push")]
    projd = [r for r in rows if r.get("proj") is not None and r.get("actual") is not None]
    n = len(graded)
    if not n and not projd:
        return None
    w = sum(r["won_close"] for r in graded)
    ml = [logloss1(r["won_close"], r["p_model"]) for r in graded if r.get("p_model") is not None]
    kl = [logloss1(r["won_close"], r["p_market"]) for r in graded if r.get("p_market") is not None]
    perr = [(r["proj"] - r["actual"]) for r in projd]
    m_ll, x_ll = mean(ml), mean(kl)
    return {
        "n": n, "rec": f"{int(w)}-{n-int(w)}", "wr": (w / n if n else None),
        "clv_beat": mean([r["beat_close"] for r in graded]),
        "mean_clv": mean([r["clv_prob"] for r in graded]),
        "model_ll": m_ll, "market_ll": x_ll,
        "edge_ll": (x_ll - m_ll) if (m_ll is not None and x_ll is not None) else None,
        "n_proj": len(perr),
        "mae": mean([abs(e) for e in perr]),
        "bias": mean(perr),
    }


def reliability(rows, edges=(0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 1.01)):
    graded = [r for r in rows if r.get("won_close") is not None and not r.get("push")
              and r.get("p_model") is not None]
    out = []
    for lo, hi in zip(edges, edges[1:]):
        b = [r for r in graded if lo <= r["p_model"] < hi]
        if b:
            out.append((lo, hi, len(b),
                        mean([r["p_model"] for r in b]), mean([r["won_close"] for r in b])))
    return out


def group_table(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[r.get(key)].append(r)
    out = []
    for k, rs in g.items():
        s = summarize(rs)
        if s:
            out.append((k, s))
    return sorted(out, key=lambda kv: -(kv[1]["n"] or 0))


def edge_score(s):
    """Rank markets/positions by DEMONSTRATED edge, not raw win%. A real edge
    needs the log-loss gap and CLV to agree AND enough sample. When they
    disagree (win% hot but the close moved against us) the score collapses, so
    a lucky small-sample market can't top the list."""
    n = s["n"] or 0
    if n < 8:
        return -9.0
    ll = s["edge_ll"] or 0.0
    clv = (s["clv_beat"] or 0.5) - 0.5
    shrink = n / (n + 40)                       # trust grows with sample
    corrob = 1.0 if (ll > 0) == (clv > 0) else 0.3   # both point the same way?
    return shrink * corrob * (ll + 0.5 * clv)


def find_findings(rows):
    """Auto-flag the actionable stuff so the retro reads itself."""
    f = []
    for mk, s in group_table(rows, "market"):
        if s["n_proj"] and s["mae"] and abs(s["bias"] or 0) / max(s["mae"], EPS) > 0.35 and s["n_proj"] >= 8:
            direction = "OVER-projects" if s["bias"] > 0 else "UNDER-projects"
            f.append(("bias", f"{mk}: {direction} by {abs(s['bias']):.1f} "
                              f"({s['n_proj']} props, MAE {s['mae']:.1f}) — systematic, not noise"))
        if s["edge_ll"] is not None and s["edge_ll"] < -0.03 and s["n"] >= 8:
            f.append(("vs-market", f"{mk}: market prices it better (log-loss {-s['edge_ll']:+.3f} worse) "
                                   f"— defer / blend toward the line"))
        if s["wr"] is not None and s["wr"] >= 0.65 and (s["clv_beat"] or 0) <= 0.35 and s["n"] >= 6:
            f.append(("luck", f"{mk}: {s['rec']} looks hot but CLV beat-rate {pct(s['clv_beat'])} "
                              f"— the close moved against us, this is variance not edge"))
    # grade monotonicity
    grades = {g: s for g, s in group_table(rows, "grade") if g}
    order = [g for g in ["A", "B", "C", "D", "F"] if g in grades]
    wrs = [grades[g]["wr"] for g in order if grades[g]["wr"] is not None]
    if len(wrs) >= 3 and not all(wrs[i] >= wrs[i + 1] - 0.02 for i in range(len(wrs) - 1)):
        f.append(("grades", "grade ladder is non-monotonic vs win% — the letter grade is not "
                             "separating winners from losers this slice"))
    return f


def fmt_row(name, s, w=14):
    return (f"{str(name):{w}s} n={s['n']:4d} {s['rec']:>8s} {pct(s['wr'])} | "
            f"CLV {pct(s['clv_beat'])} | MAE {('   - ' if s['mae'] is None else f'{s['mae']:5.1f}')} "
            f"bias {sgn(s['bias'])} | edge {('  -  ' if s['edge_ll'] is None else f'{s['edge_ll']:+.3f}')}")


def render(label, rows):
    # Deterministic body: no wall-clock, so the committed file changes only when
    # the NUMBERS change (it rides the settlement commit that produced them —
    # git records the authoritative timestamp, not this doc).
    lines = []
    P = lines.append
    o = summarize(rows)
    P(f"# Player-prop retro — {label}")
    P("")
    P(f"_{o['n']} graded props ({o['n_proj']} with a projection to score)._")
    P("")
    # headline
    verdict = "model prices probability better" if (o["edge_ll"] or 0) > 0 else "market prices probability better"
    P("## Headline")
    P("")
    P(f"- **Record:** {o['rec']} ({pct(o['wr'])}) vs {BREAK_EVEN*100:.1f}% break-even "
      f"→ {'profitable' if o['wr'] and o['wr'] > BREAK_EVEN else 'below break-even'}")
    P(f"- **CLV beat-rate:** {pct(o['clv_beat'])} — how often we land on the right side of the closing line")
    P(f"- **Model vs market log-loss:** {o['model_ll']:.4f} vs {o['market_ll']:.4f} → **{verdict}** "
      f"by {abs(o['edge_ll']):.4f}")
    P("")
    P("The closing line is the sharpest number the market posts, so it is our stand-in for "
      "\"industry tools.\" Beating it on CLV = real side-selection edge; a worse log-loss = our "
      "confidence numbers are still less calibrated than consensus.")
    P("")
    # by market
    P("## By market")
    P("")
    P("```")
    for mk, s in group_table(rows, "market"):
        P(fmt_row(mk, s))
    P("```")
    P("")
    # by position
    P("## By position")
    P("")
    P("```")
    for pos, s in group_table(rows, "pos"):
        P(fmt_row(pos, s, w=6))
    P("```")
    P("")
    # over/under
    P("## Over vs under")
    P("")
    P("```")
    for side in ["over", "under"]:
        s = summarize([r for r in rows if r.get("side") == side])
        if s:
            P(fmt_row(side, s, w=6))
    P("```")
    P("")
    # calibration
    rel = reliability(rows)
    if rel:
        P("## Calibration (model P(over) → realized)")
        P("")
        P("```")
        P(f"{'bucket':>12s} {'n':>4s} {'pred':>6s} {'actual':>7s}")
        for lo, hi, n, pred, act in rel:
            flag = "  << overconfident" if (act is not None and pred - act > 0.08) else ""
            P(f"{lo:.2f}-{hi:.2f}   {n:4d} {pred:6.3f} {act:7.3f}{flag}")
        P("```")
        P("")
    # best category — crown a market AND a position, by demonstrated edge
    P("## Best category")
    P("")
    P("Ranked by demonstrated edge (sample-shrunk log-loss + CLV, collapsed when the "
      "two disagree), so a lucky small-sample market can't top it.")
    P("")
    for lbl, keyed in (("market", group_table(rows, "market")), ("position", group_table(rows, "pos"))):
        ranked = sorted(keyed, key=lambda kv: -edge_score(kv[1]))
        if ranked and edge_score(ranked[0][1]) > -9:
            bk, bs = ranked[0]
            bedge = "  -  " if bs["edge_ll"] is None else f"{bs['edge_ll']:+.3f}"
            P(f"- **Best {lbl}: {bk}** — {bs['rec']} ({pct(bs['wr'])}), CLV {pct(bs['clv_beat'])}, "
              f"log-loss edge {bedge}, projection MAE "
              f"{('  - ' if bs['mae'] is None else f'{bs['mae']:.1f}')}.")
    P("")
    # findings
    findings = find_findings(rows)
    P("## Flags")
    P("")
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

    generated, label, weeks, rows = load_props("all" if args.all else args.week)
    if not rows:
        print(f"[retro] no settled props for {label} (settled weeks: {weeks})")
        return
    report = render(label, rows)
    print(f"[retro] settlement tape generated {generated}")
    print(report)

    if args.no_write:
        return
    os.makedirs(RETRO_DIR, exist_ok=True)
    slug = "all-weeks" if args.all else f"week-{label.split()[-1]}"
    path = os.path.join(RETRO_DIR, f"prop-retro-{slug}.md")
    with open(path, "w") as fh:
        fh.write(report + "\n---\n_Auto-generated by `scripts/weekly_prop_retro.py` off the "
                          "settlement tape; refreshes with each settle. See git history for dates._\n")
    print(f"\n[retro] wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
