#!/usr/bin/env python3
"""
Point-in-time closing-line-value (CLV) tiers for Polymarket wallets (Sharps audit, Step 1; docs/pm-clv-tiers.md).

Why: the card's "hot" wallets are picked on win rate and dollar ROI from leaderboards, which is hindsight; forward they have not beaten
the market (docs/sharps-audit-2026-11-18.md). CLV is the one wallet skill that persisted out of sample. This ranks each wallet by the
posterior mean of its CLV in a sport, using only games that had started before `asof`.

  observation   one per wallet x game x market type: the mean of (close - the wallet's average entry price) over its positions in
                that market, from stored closes only (Vault's T-15 keyframes, else data/pm_closes.json). Hedged and split rows, and
                entries priced outside .02 to .98, are left out. No close is ever estimated.
  model         the same shrinkage as scripts/rank_pm_wallets.py, within one sport: y ~ N(mu_w, sigma_w^2 / n), mu_w ~ N(m, tau^2),
                m and tau^2 by DerSimonian-Laird over wallets with 5+ games, sigma^2 the median wallet variance.
  tiers         sharp: n >= MIN_N games and P(mu_w > 0) >= 0.95.  dull: n >= MIN_N and P(mu_w > 0) <= 0.05.
                mid: ranked, neither.  thin: under MIN_N games (listed, not tiered).
                Conventional cut-offs, set before the walk-forward below, not tuned.
  point in time a game counts only if its start is before `asof` (its close is a T-15 or pre-kickoff quote, so it is known by then).
                A card cut at T-15 therefore never sees its own game.

Context only. A sharp tier is not a bet signal and does not count toward an agree total (CLAUDE.md).

Usage:
  python3 scripts/pm_clv_tiers.py --root LEDGER --holders HOLDERS --closes data/pm_closes.json --sport nba [--asof EPOCH] --out FILE
  python3 scripts/pm_clv_tiers.py ... --backtest --out data/pm_clv_tiers_backtest.json     (weekly walk-forward, see below)
"""
import argparse, collections, json, math, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rank_pm_wallets as R                       # noqa: E402

MIN_N = 30                  # games a wallet needs before it is tiered
MIN_RANKED = 5              # games for a wallet to inform the cross-wallet prior (rank_pm_wallets.MIN_N_PRIOR)
MIN_WALLETS = 30            # wallets with MIN_RANKED+ games needed before any tier is given
P_SHARP, P_DULL = 0.95, 0.05
PX_LO, PX_HI = 0.02, 0.98


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def observations(rows, markets, closes, event_of):
    """{wallet: [(game start, clv)]} sorted by start, one per wallet x game x market type. `rows` are ledger rows, `closes` is
    {(cid, outcome index): close} (build_side_cards.load_closes), `event_of` maps a slug to its game key."""
    grp = {}
    for r in rows:
        avg, stake = r.get("avg"), r.get("stake") or 0
        if r.get("hedged") or r.get("split") or avg is None or stake <= 0 or not (PX_LO < avg < PX_HI):
            continue
        c = closes.get((r["cid"], r["oi"]))
        if c is None:
            continue
        ev = event_of((markets.get(r["cid"]) or {}).get("slug")) or r["cid"]
        g = grp.setdefault((r["w"], ev, r.get("mt")), [r["gst"], 0.0, 0])
        g[1] += c - avg
        g[2] += 1
    out = collections.defaultdict(list)
    for (w, _, _), (gst, s, n) in grp.items():
        out[w].append((gst, s / n))
    for l in out.values():
        l.sort()
    return out


def fit(obs, asof, min_n=MIN_N):
    """Tier every wallet from games that started before `asof`. -> {"params": {...}, "wallets": {w: {n, mean, post, sd, p, tier}}}.
    Empty wallets and params None when too few wallets have data."""
    d = {}
    for w, l in obs.items():
        xs = [c for g, c in l if g < asof]
        n = len(xs)
        if not n:
            continue
        m = sum(xs) / n
        d[w] = [n, m, sum((x - m) ** 2 for x in xs) / (n - 1) if n > 1 else None]
    sp = R.pooled_var(d)
    if sp is None or sum(1 for v in d.values() if v[0] >= MIN_RANKED) < MIN_WALLETS:
        return {"params": None, "wallets": {}}
    mm, tau2 = R.prior(d, sp)
    wallets = {}
    for w, (n, y, v) in d.items():
        vw = R.wallet_var(n, v, sp) / n
        if tau2 > 0:
            pv = 1 / (1 / tau2 + 1 / vw)
            post = pv * (mm / tau2 + y / vw)
            sd = math.sqrt(pv)
            p = phi(post / sd)
        else:
            post, sd, p = mm, 0.0, 0.5
        tier = "thin" if n < min_n else "sharp" if p >= P_SHARP else "dull" if p <= P_DULL else "mid"
        wallets[w] = {"n": n, "mean": round(y, 5), "post": round(post, 5), "sd": round(sd, 5), "p": round(p, 4), "tier": tier}
    return {"params": {"m": round(mm, 5), "tau2": round(tau2, 8), "sigma2": round(sp, 6), "wallets": len(d), "asof": int(asof)},
            "wallets": wallets}


def backtest(obs, start, end, step=7 * 86400, min_n=MIN_N):
    """Weekly walk-forward: tier every wallet as of each Monday-ish step using earlier games only, then read the next step's games
    by tier. Returns {tier: {"n", "clv", "se"}} pooled over steps, plus the wallet counts per step. A tier with n < 2 has no SE."""
    acc = collections.defaultdict(list)
    steps = []
    t = start
    while t < end:
        f = fit(obs, t, min_n)
        if f["params"]:
            tiers = f["wallets"]
            steps.append({"asof": t, "sharp": sum(1 for x in tiers.values() if x["tier"] == "sharp"),
                          "dull": sum(1 for x in tiers.values() if x["tier"] == "dull")})
            for w, l in obs.items():
                k = (tiers.get(w) or {}).get("tier") or "unranked"
                acc[k] += [c for g, c in l if t <= g < t + step]
        t += step
    res = {}
    for k, xs in acc.items():
        n = len(xs)
        m = sum(xs) / n if n else None
        se = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n) if n > 1 else None
        res[k] = {"n": n, "clv": round(m, 5) if m is not None else None, "se": round(se, 5) if se is not None else None}
    return {"by_tier": res, "steps": steps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="pm_ledger directory (bets/, markets/)")
    ap.add_argument("--holders", default=None, help="pm_holders directory, for T-15 keyframe closes")
    ap.add_argument("--closes", default="data/pm_closes.json")
    ap.add_argument("--sport", required=True)
    ap.add_argument("--asof", type=int, default=None, help="epoch seconds; default now")
    ap.add_argument("--out", required=True)
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--from", dest="start", type=int, default=None)
    a = ap.parse_args()
    import build_side_cards as B
    led = B.Ledger.load(a.root, a.sport, a.holders, json.load(open(a.closes)) if os.path.exists(a.closes) else None)
    obs = observations([r for rs in led.by_w.values() for r in rs], led.markets, led.closes, B.event_of)
    asof = a.asof or int(time.time())
    if a.backtest:
        out = {"sport": a.sport, "min_n": MIN_N, "p_sharp": P_SHARP, "p_dull": P_DULL,
               **backtest(obs, a.start or asof - 8 * 7 * 86400, asof)}
    else:
        out = {"sport": a.sport, "min_n": MIN_N, "p_sharp": P_SHARP, "p_dull": P_DULL, **fit(obs, asof)}
    with open(a.out, "w") as f:
        json.dump(out, f, separators=(",", ":"), sort_keys=True)
    print(a.sport, "tiers" if not a.backtest else "backtest", "->", a.out)


if __name__ == "__main__":
    main()
