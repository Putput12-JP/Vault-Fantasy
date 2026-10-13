#!/usr/bin/env python3
"""Walk-forward backtest of the joint-sim prop model (Phase 1). Usage:
    python3 -I scripts/nfl_sim/backtest.py [--sims 10000] [--procs 4] [--kappa 20] [--sigma-te 0.10] [--only 2025:6,2025:7]
Writes data/nfl_sim/*.json|csv (small). Report text lives in docs/nfl_sim_backtest.md.
ZERO sportsbook inputs reach the projection: lines/prices are used only to PRICE a probability the sim already made.
"""
import argparse, json, math, os, sys, time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)      # -I drops the script dir from sys.path; this is our own code directory
import numpy as np
import pandas as pd
import data, props, runner

OUT = os.path.join(HERE, "..", "..", "data", "nfl_sim")
THETAS = [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15]
rng_b = np.random.default_rng(7)


def dec(a):
    return 1 + (a / 100 if a > 0 else 100 / -a)


def imp(a):
    return 1 / dec(a)


def devig(o, u):
    """Power devig -> P(over). Falls back to proportional if overround <= 0."""
    po, pu = imp(o), imp(u)
    if po + pu <= 1:
        return po / (po + pu)
    lo, hi = 1.0, 10.0
    for _ in range(60):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1:
            lo = k
        else:
            hi = k
    return po ** ((lo + hi) / 2)


def _work(a):
    return runner.run_week(a)


def run_all(df, sims, procs, kappa, ste, only=None):
    runner.get_state()    # build once, fork shares it
    weeks = sorted({(r.season, r.week) for r in df.itertuples()})
    if only:
        weeks = [w for w in weeks if w in only]
    jobs = []
    for s, w in weeks:
        sub = df[(df.season == s) & (df.week == w) & df.mapped & df.team.notna()]
        jobs.append((s, w, sub.to_dict("records"), kappa, ste, sims))
    t = time.time()
    with Pool(procs) as p:
        res = []
        for i, r in enumerate(p.imap(_work, jobs)):
            res.append(r)
            print(f"  week {jobs[i][0]}-{jobs[i][1]:02d} done ({i + 1}/{len(jobs)}) {time.time() - t:.0f}s", flush=True)
    out = [x for r in res for x in r[0]]
    games = [x for r in res for x in r[1]]
    return pd.DataFrame(out), pd.DataFrame(games)


def price_table(d):
    """Add no-vig market probabilities, assumed-price flags, and the model's bet side at open and close."""
    d = d.copy()
    for tag in ("o", "c"):
        ov, un = d[f"over_{tag}"], d[f"under_{tag}"]
        miss = ov.isna() | un.isna() | d[f"line_{tag}"].isna()
        d[f"assumed_{tag}"] = miss & d[f"line_{tag}"].notna()
        ov = ov.fillna(-110)
        un = un.fillna(-110)
        d[f"over_{tag}"], d[f"under_{tag}"] = ov, un
        d[f"mkt_{tag}"] = [devig(a, b) if pd.notna(l) else np.nan for a, b, l in zip(ov, un, d[f"line_{tag}"])]
    return d


def settle(row_actual, line, side):
    if row_actual == line:
        return 0
    over = row_actual > line
    return 1 if (over == (side == "over")) else -1


def bets(d, theta, tag):
    """One bet per prop at theta: pick the side with the higher EV at the `tag` ('o' open / 'c' close) price."""
    rows = []
    for r in d.itertuples():
        line = getattr(r, f"line_{tag}")
        p = getattr(r, f"p_{tag}")
        if pd.isna(line) or p is None or pd.isna(p) or pd.isna(r.actual):
            continue
        ov, un = getattr(r, f"over_{tag}"), getattr(r, f"under_{tag}")
        ev_o, ev_u = p * dec(ov) - 1, (1 - p) * dec(un) - 1
        side, ev = ("over", ev_o) if ev_o >= ev_u else ("under", ev_u)
        if ev < theta:
            continue
        price = ov if side == "over" else un
        res = settle(r.actual, line, side)
        units = 0.0 if res == 0 else (dec(price) - 1 if res == 1 else -1.0)
        mk = getattr(r, f"mkt_{tag}")
        fair_side_open = (r.mkt_o if side == "over" else 1 - r.mkt_o) if pd.notna(r.mkt_o) else np.nan
        # price CLV (same-line only): no-vig close prob of the side vs the price paid (implied, with vig)
        clv = np.nan
        move = np.nan
        if tag == "o" and pd.notna(r.line_c):
            if r.line_c == line:
                fc = r.mkt_c if side == "over" else 1 - r.mkt_c
                clv = fc / imp(price) - 1
            move = np.sign((r.line_c - line) * (1 if side == "over" else -1))   # +1: close moved toward our side (we got the better number)
        rows.append(dict(season=r.season, week=r.week, market=r.market, src=r.src, gsis=r.gsis, side=side, ev=ev,
                         p_side=p if side == "over" else 1 - p, mkt_side=(mk if side == "over" else 1 - mk),
                         price=price, units=units, res=res, clv=clv, move=move, assumed=bool(getattr(r, f"assumed_{tag}"))))
    return pd.DataFrame(rows)


def summarize(b, boot=True):
    b = b[b.res != 0]
    n = len(b)
    if n == 0:
        return dict(n=0)
    out = dict(n=int(n), wins=int((b.res == 1).sum()), hit=float((b.res == 1).mean()), units=float(b.units.sum()),
               roi=float(b.units.sum() / n))
    if boot and n >= 30:
        u = b.units.values
        idx = rng_b.integers(0, n, (2000, n))
        m = u[idx].mean(1)
        out["roi_ci90"] = [float(np.quantile(m, 0.05)), float(np.quantile(m, 0.95))]
    c = b.clv.dropna()
    if len(c):
        out["clv_price_mean"] = float(c.mean()); out["clv_price_n"] = int(len(c)); out["clv_price_pos"] = float((c > 0).mean())
    mv = b.move.dropna()
    if len(mv):
        out["line_moved_for_us"] = float((mv > 0).mean()); out["line_moved_against"] = float((mv < 0).mean())
        out["line_unchanged"] = float((mv == 0).mean())
    out["assumed_price_share"] = float(b.assumed.mean())
    return out


def scoring(d, tag, pcol):
    """Brier / log loss of model vs market no-vig, same props, same line, pushes dropped."""
    x = d[d[f"line_{tag}"].notna() & d[pcol].notna() & d.actual.notna() & d[f"mkt_{tag}"].notna()]
    x = x[x.actual != x[f"line_{tag}"]]
    y = (x.actual > x[f"line_{tag}"]).astype(float).values
    pm = np.clip(x[pcol].values.astype(float), 1e-4, 1 - 1e-4)
    pk = np.clip(x[f"mkt_{tag}"].values.astype(float), 1e-4, 1 - 1e-4)
    f = lambda p: dict(brier=float(np.mean((p - y) ** 2)), logloss=float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))))
    return dict(n=int(len(x)), model=f(pm), market=f(pk), over_rate=float(y.mean()))


def edge_buckets(b):
    edges = [(0.0, 0.02), (0.02, 0.04), (0.04, 0.06), (0.06, 0.10), (0.10, 0.20), (0.20, 9)]
    out = []
    for lo, hi in edges:
        s = b[(b.ev >= lo) & (b.ev < hi)]
        r = summarize(s, boot=False)
        r["bucket"] = f"{int(lo * 100)}-{int(hi * 100) if hi < 9 else '+'}%"
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=10000)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--kappa", type=float, default=runner.KAPPA)
    ap.add_argument("--sigma-te", type=float, default=runner.SIGMA_TE)
    ap.add_argument("--only", default="")
    ap.add_argument("--reuse", action="store_true", help="reuse data/nfl_sim/_sim_props.csv instead of re-simulating")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    cache = os.path.join(data.CACHE, "sim_props.pkl")
    if a.reuse and os.path.exists(cache):
        d = pd.read_pickle(cache); games = pd.read_pickle(cache + ".games")
    else:
        pw = data.player_weeks()
        df = props.build(pw, data.id_map(), data.roster_ids(2026))
        only = {tuple(int(v) for v in x.split(":")) for x in a.only.split(",") if x} or None
        d, games = run_all(df[df.mapped & df.actual.notna()], a.sims, a.procs, a.kappa, a.sigma_te, only)
        d.to_pickle(cache); games.to_pickle(cache + ".games")
    d = price_table(d)
    report(d, games)


def report(d, games):
    d = d.copy()
    d["order"] = d.season * 100 + d.week
    wk = sorted(d.order.unique())
    split = wk[len(wk) // 2]            # first half of weeks (by calendar order) = in-sample for the gate
    d["half"] = np.where(d.order < split, "in_sample", "out_of_sample")
    res = dict(n_props=int(len(d)), weeks=len(wk), split_at=int(split), by_source=d.groupby("src").size().to_dict(),
               by_market=d.groupby("market").size().to_dict(),
               assumed_price_open=int(d.assumed_o.sum()), assumed_price_close=int(d.assumed_c.sum()))
    # ---- scoring
    res["scoring"] = {tag: {h: scoring(d[d.half == h] if h != "all" else d, tag, f"p_{tag}")
                            for h in ("all", "in_sample", "out_of_sample")} for tag in ("o", "c")}
    res["scoring_by_market"] = {m: scoring(d[d.market == m], "c", "p_c") for m in d.market.unique()}
    # ---- gate: pick theta on in-sample weeks only
    grid = {}
    for th in THETAS:
        for tag in ("o", "c"):
            b = bets(d[d.half == "in_sample"], th, tag)
            grid[f"{th}|{tag}"] = summarize(b, boot=False)
    # primary pricing for the gate = close price (no stale-open flattery); open reported alongside
    cand = [(th, grid[f"{th}|c"]) for th in THETAS if grid[f"{th}|c"].get("n", 0) >= 100]
    best_th = max(cand, key=lambda t: t[1]["roi"])[0] if cand else THETAS[2]
    res["gate"] = dict(chosen_theta=best_th, rule="max in-sample ROI at CLOSE prices over theta grid with n>=100",
                       in_sample_grid=grid)
    oos_grid = {}
    for th in THETAS:
        for tag in ("o", "c"):
            oos_grid[f"{th}|{tag}"] = summarize(bets(d[d.half == "out_of_sample"], th, tag), boot=False)
    res["oos_all_thetas"] = oos_grid
    # ---- headline at chosen theta
    head = {}
    for h in ("in_sample", "out_of_sample", "all"):
        sub = d if h == "all" else d[d.half == h]
        head[h] = {tag: summarize(bets(sub, best_th, tag)) for tag in ("o", "c")}
        head[h]["theta0"] = {tag: summarize(bets(sub, 0.0, tag)) for tag in ("o", "c")}
    res["headline"] = head
    bo = bets(d[d.half == "out_of_sample"], best_th, "o")
    bc = bets(d[d.half == "out_of_sample"], best_th, "c")
    res["oos_by_market_open"] = {m: summarize(bo[bo.market == m], boot=False) for m in bo.market.unique()} if len(bo) else {}
    res["oos_by_market_close"] = {m: summarize(bc[bc.market == m], boot=False) for m in bc.market.unique()} if len(bc) else {}
    res["oos_by_source_open"] = {m: summarize(bo[bo.src == m], boot=False) for m in bo.src.unique()} if len(bo) else {}
    res["oos_by_side_open"] = {m: summarize(bo[bo.side == m], boot=False) for m in bo.side.unique()} if len(bo) else {}
    res["edge_buckets_open_all_weeks"] = edge_buckets(bets(d, 0.0, "o"))
    res["edge_buckets_close_all_weeks"] = edge_buckets(bets(d, 0.0, "c"))
    res["edge_buckets_open_oos"] = edge_buckets(bets(d[d.half == "out_of_sample"], 0.0, "o"))
    res["edge_buckets_close_oos"] = edge_buckets(bets(d[d.half == "out_of_sample"], 0.0, "c"))
    res["by_market_all_open_theta"] = {m: summarize(bets(d[d.market == m], best_th, "o"), boot=False) for m in d.market.unique()}
    res["by_market_all_close_theta"] = {m: summarize(bets(d[d.market == m], best_th, "c"), boot=False) for m in d.market.unique()}
    res["by_week_open_theta"] = {f"{int(o)}": summarize(bets(d[d.order == o], best_th, "o"), boot=False) for o in wk}
    # ---- calibration of the sim itself
    res["calibration"] = {m: dict(n=int(len(x)), sim_mean=float(x.sim_mean.mean()), actual_mean=float(x.actual.mean()),
                                  line_mean=float(x.line_o.mean()),
                                  cover_q10_q90=float(((x.actual >= x.q10) & (x.actual <= x.q90)).mean()),
                                  pit_sd=float(x.rank_pit.std())) for m, x in d.groupby("market")}
    # ---- head to head vs Vault (2026 only: that is where point-in-time Vault probabilities are stored)
    v = d[(d.src == "vault26") & d.vault_p_over.notna()].copy()
    h2h = dict(n=int(len(v)))
    if len(v):
        h2h["scoring_open"] = {k: scoring(v, "o", col) for k, col in (("sim", "p_o"), ("vault", "vault_p_over"))}
        vv = v.copy(); vv["p_o"] = vv.vault_p_over
        h2h["bets"] = {}
        for th in (0.0, best_th):
            h2h["bets"][str(th)] = dict(sim_open=summarize(bets(v, th, "o")), vault_open=summarize(bets(vv, th, "o")))
        # same bets at close price using each model's p at the open line is not comparable (line moved); only unchanged-line props
        same = v[(v.line_o == v.line_c)].copy()
        vs = same.copy(); vs["p_c"] = vs.vault_p_over
        h2h["unchanged_line_close_price"] = dict(
            n=int(len(same)),
            sim=summarize(bets(same, best_th, "c")), vault=summarize(bets(vs, best_th, "c")),
            sim_theta0=summarize(bets(same, 0.0, "c")), vault_theta0=summarize(bets(vs, 0.0, "c")),
            scoring=dict(sim=scoring(same, "c", "p_c"), vault=scoring(vs, "c", "p_c")))
        # ledger side only: Vault's own published side at its stored p (rule-free), for context
        h2h["by_market_open_theta0"] = {m: dict(sim=summarize(bets(v[v.market == m], 0.0, "o"), boot=False),
                                               vault=summarize(bets(vv[vv.market == m], 0.0, "o"), boot=False))
                                       for m in v.market.unique()}
    res["head_to_head_2026"] = h2h
    # ---- correlation of simulated QB passing yards vs top WR receiving yards
    if len(games):
        g = games
        res["qb_wr_corr"] = dict(n_team_games=int(len(g)), qb_wr1_mean=float(g.corr_qb_wr1.mean()),
                                 qb_wr1_p10=float(g.corr_qb_wr1.quantile(.1)), qb_wr1_p90=float(g.corr_qb_wr1.quantile(.9)),
                                 qb_wr2_mean=float(g.corr_qb_wr2.dropna().mean()),
                                 wr1_wr2_mean=float(g.corr_wr1_wr2.dropna().mean()),
                                 team_pass_yd_mean=float(g.team_pass_mean.mean()), team_pass_yd_sd=float(g.team_pass_sd.mean()))
    json.dump(res, open(os.path.join(OUT, "backtest_summary.json"), "w"), indent=1, default=float)
    # small per-prop CSV (rounded)
    keep = ["src", "season", "week", "market", "gsis", "team", "line_o", "over_o", "under_o", "line_c", "over_c", "under_c",
            "actual", "sim_mean", "sim_sd", "p_o", "p_c", "mkt_o", "mkt_c", "vault_p_over", "half"]
    out = d[keep].copy()
    for c in ("sim_mean", "sim_sd", "p_o", "p_c", "mkt_o", "mkt_c", "vault_p_over"):
        out[c] = out[c].astype(float).round(4)
    out.to_csv(os.path.join(OUT, "sim_props.csv.gz"), index=False, compression="gzip")
    if len(games):
        games.round(4).to_csv(os.path.join(OUT, "qb_wr_corr.csv"), index=False)
    print(json.dumps({k: res[k] for k in ("n_props", "weeks", "gate", "headline")}, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()
