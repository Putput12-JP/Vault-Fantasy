#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · QB-OUT IMPACT  →  data/qb_out_impact.json
#
#  MEASURES (does not invent) how a team's skill players' per-game production
#  changes when the team's PRIMARY QB is out — the cross-market, bidirectional
#  effect the same-position usage cascade can't express (a backup QB pulls the
#  passing game DOWN and the run game UP). Sibling of build_usage_cascade.py and
#  built to the same bar: publish only buckets with enough events that also pass
#  a sign check and an out-of-sample stability check; otherwise ship nothing and
#  let the caller fall back to withholding the lean.
#
#  Method (nflverse weekly stats, many seasons):
#    · Per team-season, the PRIMARY QB = the QB with the most pass attempts
#      (min season attempts + games), and his "tenure" = first…last week he
#      appeared. QB-OUT weeks = weeks inside that tenure the team played but the
#      primary QB has no row (the same absence proxy the usage cascade uses).
#    · For each skill teammate p and market m, BASELINE = median of p's per-game
#      value in QB-PRESENT weeks (his normal with the starter). EFFECT for a
#      QB-out week = value_p,m(W) / baseline_p,m, bucketed by (pos, market).
#    · The backup QB's pass markets are measured against the PRIMARY QB's own
#      baseline (backup_value / qb1_baseline) — "the backup produces X% of the
#      starter's line," which is exactly what prices his prop.
#    · Publish the MEDIAN multiplier per (pos,market) with n and IQR.
#
#  Ship gates (a plausible adjustment that doesn't hold up is a no-go, cf. DvP):
#    1. n >= MIN_EVENTS.
#    2. Sign sanity: passing/receiving markets expected <= 1 (down), RB rushing
#       markets expected >= 1 (up). A bucket on the wrong side of 1 is dropped.
#    3. Stability: fit the median on EVEN seasons and ODD seasons separately;
#       both must land on the same side of 1 and within STABILITY_TOL of each
#       other. A bucket that doesn't generalize across the split is dropped.
#
#  Usage:  python3 scripts/build_qb_out_impact.py [--since 2007] [--dry]
# ════════════════════════════════════════════════════════════════════════════
import argparse, json, os, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(DATA, "qb_out_impact.json")

MIN_PRESENT = 6          # weeks the primary QB must appear to be an established starter
MIN_BASELINE = 3         # baseline weeks required to trust a teammate's normal role
MIN_QB_ATT = 150         # season pass attempts to qualify as the team's primary QB
MIN_EVENTS = 40          # events required before a bucket publishes
STABILITY_TOL = 0.10     # max |even_median - odd_median| for a bucket to be stable
MIN_EFFECT = 0.05        # |mult-1| a bucket must reach to be worth applying (else keep withholding)
# Minimum baseline volume so a tiny denominator can't manufacture a huge ratio.
MIN_BASE_VOL = {
    "rec_yd": 20.0, "rec": 2.0, "rec_td": 0.2,
    "rush_yd": 20.0, "rush_att": 5.0,
    "pass_yd": 150.0, "pass_att": 20.0, "pass_td": 0.8,
}
# market → weekly field, per position group
SKILL_MK = {
    "WR": {"rec_yd": "recyds", "rec": "rec", "rec_td": "rectds"},
    "TE": {"rec_yd": "recyds", "rec": "rec", "rec_td": "rectds"},
    "RB": {"rush_yd": "ryds", "rush_att": "car", "rec": "rec", "rec_yd": "recyds"},
}
QB_MK = {"pass_yd": "pyds", "pass_att": "att", "pass_td": "ptds"}
# expected direction when the primary QB is out: -1 = down (<=1), +1 = up (>=1)
EXPECT = {
    "WR|rec_yd": -1, "WR|rec": -1, "WR|rec_td": -1,
    "TE|rec_yd": -1, "TE|rec": -1, "TE|rec_td": -1,
    "RB|rush_yd": +1, "RB|rush_att": +1, "RB|rec": +1, "RB|rec_yd": +1,
    "QB|pass_yd": -1, "QB|pass_att": -1, "QB|pass_td": -1,
}


def load(season):
    path = os.path.join(DATA, f"nflverse_stats_{season}.json")
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path))
    except Exception:
        return None


def team_structs(blob):
    """team -> {weeks_played:set, qbs:{name:{wk:row}}, players:[(name,pos,{wk:row})]}"""
    teams = defaultdict(lambda: {"weeks": set(), "players": []})
    for name, r in blob.items():
        pos, team, weeks = r.get("pos"), r.get("team"), r.get("weeks") or []
        if not team or not pos or not weeks:
            continue
        wkrows = {w.get("wk"): w for w in weeks if w.get("wk") is not None}
        for wk in wkrows:
            teams[team]["weeks"].add(wk)
        teams[team]["players"].append((name, pos, wkrows))
    return teams


def primary_qb(players):
    best, best_att = None, 0
    for name, pos, rows in players:
        if pos != "QB":
            continue
        att = sum((row.get("att") or 0) for row in rows.values())
        if len(rows) >= MIN_PRESENT and att >= MIN_QB_ATT and att > best_att:
            best, best_att = (name, rows), att
    return best


def measure(seasons):
    # events[bucket] = list of (season, mult)
    events = defaultdict(list)
    for season in seasons:
        blob = load(season)
        if not blob:
            continue
        for team, ts in team_structs(blob).items():
            pq = primary_qb(ts["players"])
            if not pq:
                continue
            qb_name, qb_rows = pq
            qb_weeks = set(qb_rows)
            lo, hi = min(qb_weeks), max(qb_weeks)
            tenure = {w for w in ts["weeks"] if lo <= w <= hi}
            out_weeks = {w for w in tenure if w not in qb_weeks}
            if not out_weeks:
                continue
            present_weeks = qb_weeks

            # QB baseline (for pricing the backup's pass markets)
            def med_field(rows, field, wks):
                vals = [rows[w].get(field) for w in wks if w in rows and rows[w].get(field) is not None]
                return st.median(vals) if len(vals) >= MIN_BASELINE else None

            qb_base = {mk: med_field(qb_rows, fld, present_weeks) for mk, fld in QB_MK.items()}

            for name, pos, rows in ts["players"]:
                if pos == "QB":
                    # backup(s): any QB row in an out-week that isn't the primary
                    if name == qb_name:
                        continue
                    for w in out_weeks:
                        row = rows.get(w)
                        if not row:
                            continue
                        for mk, fld in QB_MK.items():
                            base = qb_base.get(mk)
                            v = row.get(fld)
                            if base is None or base < MIN_BASE_VOL[mk] or v is None:
                                continue
                            events[f"QB|{mk}"].append((season, v / base))
                    continue
                mkmap = SKILL_MK.get(pos)
                if not mkmap:
                    continue
                for mk, fld in mkmap.items():
                    base = med_field(rows, fld, present_weeks)
                    if base is None or base < MIN_BASE_VOL[mk]:
                        continue
                    for w in out_weeks:
                        row = rows.get(w)
                        if not row or row.get(fld) is None:
                            continue
                        events[f"{pos}|{mk}"].append((season, row[fld] / base))
    return events


def summarize(events):
    buckets, rejected = {}, {}
    for key, evs in sorted(events.items()):
        mults = [m for _, m in evs]
        n = len(mults)
        med = round(st.median(mults), 3)
        q = sorted(mults)
        iqr = [round(q[n // 4], 3), round(q[(3 * n) // 4], 3)] if n >= 4 else None
        even = [m for s, m in evs if s % 2 == 0]
        odd = [m for s, m in evs if s % 2 == 1]
        emed = st.median(even) if even else None
        omed = st.median(odd) if odd else None
        exp = EXPECT.get(key, 0)
        reasons = []
        if n < MIN_EVENTS:
            reasons.append(f"n={n}<{MIN_EVENTS}")
        if abs(med - 1.0) < MIN_EFFECT:
            reasons.append(f"no material effect (|{med}-1|<{MIN_EFFECT}) — keep withholding")
        if exp == -1 and med > 1.0:
            reasons.append(f"median {med}>1 (expected down)")
        if exp == +1 and med < 1.0:
            reasons.append(f"median {med}<1 (expected up)")
        if emed is None or omed is None:
            reasons.append("no even/odd split")
        else:
            if (emed - 1) * (omed - 1) < 0:
                reasons.append(f"unstable sign even={emed:.3f} odd={omed:.3f}")
            elif abs(emed - omed) > STABILITY_TOL:
                reasons.append(f"unstable |Δ|={abs(emed-omed):.3f}>{STABILITY_TOL}")
        rec = {"mult": med, "n": n, "iqr": iqr,
               "even": round(emed, 3) if emed is not None else None,
               "odd": round(omed, 3) if omed is not None else None}
        if reasons:
            rec["rejected"] = "; ".join(reasons)
            rejected[key] = rec
        else:
            buckets[key] = {"mult": med, "n": n, "iqr": iqr}
    return buckets, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=2007)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    seasons = list(range(args.since, 2027))
    events = measure(seasons)
    buckets, rejected = summarize(events)

    print(f"[qb-out] seasons {args.since}-2026 · {sum(len(v) for v in events.values())} events")
    print(f"[qb-out] PUBLISHED ({len(buckets)}):")
    for k, v in buckets.items():
        print(f"   {k:16s} ×{v['mult']:<6} n={v['n']:<5} iqr={v['iqr']}")
    print(f"[qb-out] rejected ({len(rejected)}):")
    for k, v in rejected.items():
        print(f"   {k:16s} ×{v['mult']:<6} n={v['n']:<5} even={v['even']} odd={v['odd']}  ✗ {v['rejected']}")

    out = {
        "generated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "since": args.since,
        "min_events": MIN_EVENTS,
        "note": "median teammate market multiplier when the team's primary QB is out; measured from nflverse weekly stats, sign- and stability-gated",
        "buckets": buckets,
        "rejected": {k: v for k, v in rejected.items()},
    }
    if args.dry:
        print("[qb-out] DRY — not written")
        return
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"[qb-out] wrote {OUT}")


if __name__ == "__main__":
    main()
