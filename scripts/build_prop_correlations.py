#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · SAME-GAME PROP CORRELATIONS  →  data/prop_correlations.json
#
#  Model-upgrade plan Week 4 (reports/NFL prediction model upgrade.md): the one
#  simulation idea that holds up is pricing CORRELATED legs. A QB's passing
#  yards and his WR1's receiving yards rise and fall together, so "both over"
#  happens more often than p1 x p2. Pick'em apps pay a flat multiple per entry
#  and (mostly) price legs independently, so a correlated pair can clear the
#  2-pick break-even (1/3 at 3x) even when each leg is near a coin flip.
#
#  Method (pure stdlib, nflverse weekly logs):
#    • roles per team-week from usage in EARLIER weeks of that season only
#      (QB1 by attempts, WR1/WR2/TE1 by targets, RB1 by carries); both players
#      must play that week; weeks 1-2 skipped (no usage history yet)
#    • each player's expectation = his mean in earlier weeks (>= 2 games); the
#      signal is actual minus expectation
#    • rho = Pearson correlation of normal scores of the two residuals (a
#      Gaussian copula fitted on ranks: robust to yardage skew)
#    • joint "both over expectation" rate vs the independent product
#  Fit on TRAIN seasons, then HELD-OUT check on the last season: the copula's
#  predicted both-over rate (from each leg's held-out marginal and the train
#  rho) against what happened, same for both-under.
#
#  Usage: python3 scripts/build_prop_correlations.py [--train=2016-2024 --test=2025] [--dry]
# ════════════════════════════════════════════════════════════════════════════
import argparse, json, math, os
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(DATA, "prop_correlations.json")
_N = NormalDist()

# role -> (position, usage key for ranking)
ROLES = {"QB1": ("QB", "att"), "WR1": ("WR", "tgt"), "WR2": ("WR", "tgt"), "TE1": ("TE", "tgt"), "RB1": ("RB", "car")}
# stat key(s) in the weekly rows per prop market. Receiving yards are "reyds"
# in the pre-2024 nflverse files and "recyds" after; read either.
STAT = {"pass_yd": ("pyds",), "rec_yd": ("recyds", "reyds"), "rush_yd": ("ryds",), "rec": ("rec",)}


def stat(row, mkt):
    for k in STAT[mkt]:
        v = row.get(k)
        if v is not None: return v
    return 0
# pair types: (roleA, marketA, roleB, marketB)
PAIRS = [
    ("QB1", "pass_yd", "WR1", "rec_yd"), ("QB1", "pass_yd", "WR2", "rec_yd"), ("QB1", "pass_yd", "TE1", "rec_yd"),
    ("QB1", "pass_yd", "RB1", "rush_yd"), ("QB1", "pass_yd", "RB1", "rec_yd"),
    ("WR1", "rec_yd", "WR2", "rec_yd"), ("WR1", "rec_yd", "TE1", "rec_yd"), ("WR1", "rec_yd", "RB1", "rush_yd"),
    ("QB1", "pass_yd", "WR1", "rec"), ("WR1", "rec", "WR2", "rec"),
]
MIN_PRIOR = 2


def pair_key(p): return f"{p[0]}:{p[1]}|{p[2]}:{p[3]}"


def load(season):
    try:
        blob = json.load(open(os.path.join(DATA, f"nflverse_stats_{season}.json")))
    except Exception:
        return {}
    return blob if isinstance(blob, dict) else {p.get("name"): p for p in blob}


def team_weeks(players):
    """{(team, wk): {name: (pos, row)}}"""
    tw = defaultdict(dict)
    for n, p in players.items():
        for w in p.get("weeks") or []:
            if w.get("wk") is not None:
                tw[(p.get("team"), int(w["wk"]))][n] = (p.get("pos"), w)
    return tw


def samples(season):
    """Per pair type: list of (residA, residB, overA, overB) for one season."""
    players = load(season)
    tw = team_weeks(players)
    hist = defaultdict(list)                           # (team, name) -> [(wk, row)] sorted
    for (team, wk), roster in tw.items():
        for n, (pos, row) in roster.items():
            hist[(team, n)].append((wk, pos, row))
    for k in hist: hist[k].sort(key=lambda x: x[0])
    out = defaultdict(list)
    for (team, wk), roster in tw.items():
        if wk < 3: continue
        # roles from earlier weeks
        use = defaultdict(lambda: defaultdict(float))  # pos -> name -> usage
        cnt = defaultdict(int)
        for (t, n), rows in hist.items():
            if t != team: continue
            for w, pos, row in rows:
                if w >= wk: break
                for role, (rpos, key) in ROLES.items():
                    if pos == rpos: use[(rpos, key)][n] += row.get(key) or 0
                cnt[n] += 1
        roles = {}
        for role, (rpos, key) in ROLES.items():
            ranked = sorted(use[(rpos, key)].items(), key=lambda x: -x[1])
            idx = 1 if role == "WR2" else 0
            if len(ranked) > idx and ranked[idx][1] > 0: roles[role] = ranked[idx][0]
        def resid(n, mkt):
            if n not in roster: return None
            prior = [stat(row, mkt) or 0 for w, pos, row in hist[(team, n)] if w < wk]
            if len(prior) < MIN_PRIOR: return None
            exp = sum(prior) / len(prior)
            return (stat(roster[n][1], mkt) or 0) - exp
        for pr in PAIRS:
            a, b = roles.get(pr[0]), roles.get(pr[2])
            if not a or not b or a == b: continue
            ra, rb = resid(a, pr[1]), resid(b, pr[3])
            if ra is None or rb is None: continue
            out[pair_key(pr)].append((ra, rb))
    return out


def normal_scores(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    z = [0.0] * len(xs); n = len(xs)
    for r, i in enumerate(order): z[i] = _N.inv_cdf((r + 0.5) / n)
    return z


def rho_of(rows):
    if len(rows) < 30: return None
    za, zb = normal_scores([r[0] for r in rows]), normal_scores([r[1] for r in rows])
    n = len(rows); ma, mb = sum(za) / n, sum(zb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(za, zb)) / n
    va = sum((x - ma) ** 2 for x in za) / n; vb = sum((y - mb) ** 2 for y in zb) / n
    return cov / math.sqrt(va * vb) if va > 0 and vb > 0 else None


def bvn_cdf(h, k, rho):
    """P(X <= h, Y <= k) for a standard bivariate normal (Drezner-Wesolowsky
    style Gauss-Legendre on the integral in rho). Pure stdlib."""
    if abs(rho) < 1e-12: return _N.cdf(h) * _N.cdf(k)
    # integrate d/dr Phi2 = phi2(h, k; r) from 0 to rho
    x = [-0.9739065285, -0.8650633667, -0.6794095683, -0.4333953941, -0.1488743390,
         0.1488743390, 0.4333953941, 0.6794095683, 0.8650633667, 0.9739065285]
    w = [0.0666713443, 0.1494513492, 0.2190863625, 0.2692667193, 0.2955242247,
         0.2955242247, 0.2692667193, 0.2190863625, 0.1494513492, 0.0666713443]
    s = 0.0
    for xi, wi in zip(x, w):
        r = rho * (xi + 1) / 2
        d = 1 - r * r
        s += wi * math.exp(-(h * h - 2 * r * h * k + k * k) / (2 * d)) / (2 * math.pi * math.sqrt(d))
    return _N.cdf(h) * _N.cdf(k) + s * rho / 2


def joint_over(pa, pb, rho):
    """P(A over and B over) for leg over-probabilities pa, pb, Gaussian copula."""
    pa = min(max(pa, 1e-6), 1 - 1e-6); pb = min(max(pb, 1e-6), 1 - 1e-6)
    return bvn_cdf(_N.inv_cdf(pa), _N.inv_cdf(pb), rho)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="2016-2024")
    ap.add_argument("--test", type=int, default=2025)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    t0, t1 = (int(x) for x in args.train.split("-"))
    train = defaultdict(list)
    for s in range(t0, t1 + 1):
        for k, v in samples(s).items(): train[k] += v
    test = samples(args.test)

    res = {}
    print(f"{'pair':<28}{'n train':>8}{'rho':>7}{'rho test':>9}   held-out both-over: predicted vs actual (indep)   both-under")
    for pr in PAIRS:
        k = pair_key(pr); tr, te = train.get(k, []), test.get(k, [])
        r = rho_of(tr); rt = rho_of(te)
        if r is None: continue
        entry = {"n_train": len(tr), "rho": round(r, 4), "n_test": len(te), "rho_test": None if rt is None else round(rt, 4)}
        if len(te) >= 50:
            pa = sum(1 for a, b in te if a > 0) / len(te); pb = sum(1 for a, b in te if b > 0) / len(te)
            oo = sum(1 for a, b in te if a > 0 and b > 0) / len(te)
            uu = sum(1 for a, b in te if a <= 0 and b <= 0) / len(te)
            pred_oo = joint_over(pa, pb, r)
            pred_uu = joint_over(1 - pa, 1 - pb, r)
            se = math.sqrt(oo * (1 - oo) / len(te))
            entry["test"] = {"p_a_over": round(pa, 4), "p_b_over": round(pb, 4),
                             "both_over": round(oo, 4), "pred_both_over": round(pred_oo, 4), "indep_both_over": round(pa * pb, 4),
                             "both_under": round(uu, 4), "pred_both_under": round(pred_uu, 4), "indep_both_under": round((1 - pa) * (1 - pb), 4),
                             "se": round(se, 4)}
            print(f"{k:<28}{len(tr):>8}{r:>7.3f}{(rt if rt is not None else 0):>9.3f}   "
                  f"{pred_oo:6.1%} vs {oo:6.1%} ({pa * pb:5.1%})  ±{se:4.1%}          {pred_uu:6.1%} vs {uu:6.1%}")
        res[k] = entry
    out = {"method": "Gaussian copula on normal scores of actual-minus-prior-mean residuals; roles from earlier-week usage",
           "train": args.train, "test": args.test, "pairs": res}
    if args.dry:
        print("--dry: not written"); return
    json.dump(out, open(OUT, "w"), indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
