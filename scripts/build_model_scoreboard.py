#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · MODEL SCOREBOARD — Vault vs. the de-vigged market, on the same bets
#      data/bet_results.json  (settle_bets.py)
#        →  data/model_scoreboard.json
#        →  docs/retro/model-scoreboard.md
#
#  Week 1 of the model-upgrade plan (reports/NFL prediction model upgrade.md):
#  the scoreboard every later change is judged on. Win-loss is too noisy to
#  tell a better model from a lucky one, so this scores PROBABILITIES:
#
#    • log-loss and Brier of Vault vs. the market's no-vig probability for the
#      SAME event (same line, same outcome). skill = 1 - LL_vault / LL_market:
#      above 0 means Vault knew something the market didn't; below 0 means the
#      market was better. Scored at the OPEN (what Vault saw when it graded)
#      and at the CLOSE (the sharpest number).
#    • CLV: did the market move toward Vault's side after the open.
#    • units: at the open line + open price vs. the close line + close price.
#
#  De-vig: POWER method (find k with p_over^k + p_under^k = 1). It beat the
#  multiplicative method in Clarke, Kovalchik & Ingram (2017) and matters most
#  on lopsided prices (low-count props, TD longshots).
#
#  Market baselines per market:
#    props   no-vig consensus two-way price at that line (open / close)
#    ML      no-vig moneyline (settle_bets p_market at the close)
#    spread  / total: no-vig consensus price at the closing number (banked from
#            2026-09-28); earlier games have only the number, so the market is
#            50/50 there (what a -110/-110 line means). Vault's cover
#            probability comes from its line and the fitted sd
#            (data/game_model.json sd_margin / sd_total).
#
#  Deterministic (no wall-clock): output changes only when the settled tape
#  does, so it rides the settlement commit without churn.
#  Usage: python3 scripts/build_model_scoreboard.py [--dry]
# ════════════════════════════════════════════════════════════════════════════
import json, math, os, sys
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
import settle_bets as SB   # model_p_over / load_prop_model / am_prob: one source of truth

EPS = 1e-4
_N = NormalDist()

def clamp(p): return min(1 - EPS, max(EPS, p))
def ll(y, p): p = clamp(p); return -(y * math.log(p) + (1 - y) * math.log(1 - p))
def brier(y, p): return (p - y) ** 2

def devig_power(a_over, a_under):
    """No-vig P(over) from a two-way American price pair, power method."""
    po, pu = SB.am_prob(a_over), SB.am_prob(a_under)
    if po is None or pu is None or po <= 0 or pu <= 0: return None
    if po + pu <= 1.0:                           # no overround to remove
        return po / (po + pu)
    lo, hi = 1.0, 10.0                           # po^k + pu^k is decreasing in k
    for _ in range(60):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1: lo = k
        else: hi = k
    k = (lo + hi) / 2
    return po ** k / (po ** k + pu ** k)

# 0.5 lines (anytime-style: 0.5 pass TDs, 0.5 receptions) used to be excluded
# here: their banked prices were polluted (frozen Underdog 1st-quarter lines and
# cross-line headline pairs) and said ~50% on overs that hit 72-77%. The capture
# is fixed (scripts/prop-quote-guard.mjs) and Weeks 1-3 were replayed through it
# (scripts/backfill-prop-prices.mjs), so they are scored like any other line.
# half_line_check() keeps watching them: market P(over) vs. the over rate on
# 0.5 lines, per market, so a regression in the capture shows up here first.
HALF = 0.5 + 1e-9

def sane_move(lo, lc):
    """Open lines sometimes carry a junk snapshot (a 57.5 pass-yds 'open').
    Treat an open more than max(15%, 1) off the close as unreliable."""
    return lo is not None and lc is not None and abs(lo - lc) <= max(0.15 * abs(lc), 1.0)


class Acc:
    """Running paired score: Vault vs market on the same events. Because both
    forecasts face the same outcomes, the noise that matters is the spread of
    the per-bet log-loss DIFFERENCE, so `z` = mean difference / its standard
    error (positive = Vault better)."""
    def __init__(self): self.n = 0; self.llv = self.llm = self.bv = self.bm = 0.0; self.d = 0.0; self.d2 = 0.0
    def add(self, y, pv, pm):
        lv, lm = ll(y, pv), ll(y, pm)
        self.n += 1; self.llv += lv; self.llm += lm
        self.bv += brier(y, pv); self.bm += brier(y, pm)
        self.d += lm - lv; self.d2 += (lm - lv) ** 2
    def out(self):
        if not self.n: return None
        lv, lm = self.llv / self.n, self.llm / self.n
        md = self.d / self.n
        var = max(self.d2 / self.n - md * md, 0.0)
        se = math.sqrt(var / self.n) if self.n > 1 else None
        return {"n": self.n, "logloss_vault": round(lv, 4), "logloss_market": round(lm, 4),
                "brier_vault": round(self.bv / self.n, 4), "brier_market": round(self.bm / self.n, 4),
                "skill": round(1 - lv / lm, 4) if lm else None,
                "z": round(md / se, 2) if se else None}


class Bet:
    """CLV + units for Vault's side."""
    def __init__(self):
        self.clv = []; self.beat = []; self.u_open = []; self.u_close = []; self.w_open = []; self.w_close = []
    def out(self):
        m = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
        s = lambda xs: round(sum(xs), 2) if xs else None
        return {"n_clv": len(self.clv), "clv_prob": m(self.clv),
                "n_beat": len(self.beat), "beat_close": m(self.beat),
                "n_open": len(self.u_open), "win_open": m(self.w_open), "units_open": s(self.u_open),
                "roi_open": m(self.u_open),
                "n_close": len(self.u_close), "win_close": m(self.w_close), "units_close": s(self.u_close),
                "roi_close": m(self.u_close)}

def pay(a): return 100 / 110 if a is None else (a / 100 if a > 0 else 100 / abs(a))


def score_props(props, model):
    acc = defaultdict(lambda: {"open": Acc(), "close": Acc()})
    bets = defaultdict(Bet)
    weeks = defaultdict(lambda: {"open": Acc(), "close": Acc()})
    for p in props:
        side, a, lo, lc, proj = p.get("side"), p.get("actual"), p.get("line_open"), p.get("line_close"), p.get("proj")
        if a is None or side not in ("over", "under") or lc is None: continue
        mk, wk = p["market"], p["week"]
        keys = ("all", mk)
        mp = model.get(mk)
        # CLOSE: Vault's P(over) re-priced at the closing line vs. the no-vig close
        q_c = devig_power(p.get("close_over"), p.get("close_under"))
        pv_c = SB.model_p_over(mp, proj, lc) if (mp and proj is not None) else None
        if q_c is not None and pv_c is not None and abs(a - lc) > 1e-9:
            y = 1.0 if a > lc else 0.0
            for k in keys: acc[k]["close"].add(y, pv_c, q_c)
            weeks[wk]["close"].add(y, pv_c, q_c)
        # OPEN: the graded probability at the open line vs. the no-vig open
        q_o = devig_power(p.get("open_over"), p.get("open_under"))
        pv_o = SB.model_p_over(mp, proj, lo) if (mp and proj is not None and lo is not None) else None
        if q_o is not None and pv_o is not None and sane_move(lo, lc) and abs(a - lo) > 1e-9:
            y = 1.0 if a > lo else 0.0
            for k in keys: acc[k]["open"].add(y, pv_o, q_o)
            weeks[wk]["open"].add(y, pv_o, q_o)
        # CLV + units on Vault's side
        for k in keys:
            b = bets[k]
            if sane_move(lo, lc):
                if abs(lo - lc) < 1e-9 and q_o is not None and q_c is not None:
                    so = q_o if side == "over" else 1 - q_o
                    sc = q_c if side == "over" else 1 - q_c
                    b.clv.append(sc - so)
                    if abs(sc - so) > 0.005: b.beat.append(1.0 if sc > so else 0.0)
                elif abs(lo - lc) >= 1e-9:
                    moved = (lc - lo) if side == "over" else (lo - lc)
                    b.beat.append(1.0 if moved > 0 else 0.0)
                if abs(a - lo) > 1e-9:
                    w = (a > lo) == (side == "over")
                    b.w_open.append(1.0 if w else 0.0)
                    b.u_open.append(pay(p.get("open_over") if side == "over" else p.get("open_under")) if w else -1.0)
            if abs(a - lc) > 1e-9:
                w = (a > lc) == (side == "over")
                b.w_close.append(1.0 if w else 0.0)
                b.u_close.append(pay(p.get("close_over") if side == "over" else p.get("close_under")) if w else -1.0)
    return acc, bets, weeks


def half_line_check(props):
    """Market no-vig P(over) vs. the over rate on 0.5 lines at the close, per
    market (n >= 5). A gap well past the noise means the capture is pairing
    prices from another line again."""
    agg = defaultdict(lambda: [0, 0.0, 0.0])
    for p in props:
        a, lc = p.get("actual"), p.get("line_close")
        if a is None or lc is None or lc > HALF: continue
        q = devig_power(p.get("close_over"), p.get("close_under"))
        if q is None: continue
        for k in ("all", p["market"]):
            g = agg[k]; g[0] += 1; g[1] += q; g[2] += 1.0 if a > lc else 0.0
    out = {}
    for k, (n, qs, ys) in sorted(agg.items()):
        if n < 5: continue
        m, h = qs / n, ys / n
        se = math.sqrt(max(m * (1 - m), 1e-6) / n)
        out[k] = {"n": n, "market_p_over": round(m, 3), "over_rate": round(h, 3), "z": round((h - m) / se, 2)}
    return out


def score_games(games, gm):
    sd_m = (gm or {}).get("sd_margin") or 13.2
    sd_t = (gm or {}).get("sd_total") or 13.6
    acc = defaultdict(lambda: {"close": Acc()})
    bets = defaultdict(Bet)
    weeks = defaultdict(lambda: {"close": Acc()})
    for g in games:
        mk = g.get("market")
        if mk not in ("spread", "total", "ml") or g.get("model_offseason") or g.get("actual") is None: continue
        wk = g["week"]
        if mk == "spread" and g.get("vault_line") is not None and g.get("line_close") is not None:
            if abs(g["actual"] + g["line_close"]) < 1e-9: continue          # push
            pv = _N.cdf((-g["vault_line"] + g["line_close"]) / sd_m)       # P(home covers the close)
            y = 1.0 if g["actual"] + g["line_close"] > 0 else 0.0
            pc = g.get("px_close") or [None, None]
            pm = devig_power(pc[0], pc[1]) or 0.5                             # no-vig home cover; 50/50 before prices were banked
        elif mk == "total" and g.get("vault_line") is not None and g.get("line_close") is not None:
            if abs(g["actual"] - g["line_close"]) < 1e-9: continue
            pv = _N.cdf((g["vault_line"] - g["line_close"]) / sd_t)        # P(over the close)
            y = 1.0 if g["actual"] > g["line_close"] else 0.0
            pc = g.get("px_close") or [None, None]
            pm = devig_power(pc[0], pc[1]) or 0.5
        elif mk == "ml" and g.get("p_home") is not None and g.get("y_home") is not None:
            pmh = g.get("p_market")
            if pmh is None or g.get("side") is None: continue               # no-lean rows carry no market prob
            pm = pmh if g["side"] == "home" else 1 - pmh                     # back to HOME probability
            pv, y = g["p_home"], g["y_home"]
        else:
            continue
        for k in ("games", mk): acc[k]["close"].add(y, pv, pm)
        weeks[wk]["close"].add(y, pv, pm)
        # CLV + units on Vault's side (spread/total at -110, ML at the side price)
        if g.get("won_close") is None: continue
        for k in ("games", mk):
            b = bets[k]
            if g.get("beat_close") is not None and (mk != "ml" or g.get("clv_prob") is not None):
                b.beat.append(float(g["beat_close"]))
            if mk == "ml" and g.get("clv_prob") is not None: b.clv.append(g["clv_prob"])
            w = g["won_close"] == 1
            b.w_close.append(1.0 if w else 0.0)
            px = g.get("price_open") if mk == "ml" else None
            if mk == "ml" and px is None: continue
            b.u_close.append(pay(px) if w else -1.0)
    return acc, bets, weeks


# ── news triggers (model-upgrade plan, Week 3) ──────────────────────────────
# Does fresh role news predict props better than the market already prices it,
# and should Vault disagree with the market when news backs it? Per settled
# prop, from information available BEFORE its game:
#   up    usage jump in the player's last game vs his baseline (targets for
#         WR/TE, carries RB, attempts QB: last >= 1.5x baseline and +2; or
#         snap share +15 pts), OR his position's top-usage teammate did not play
#   down  usage / snap-share drop of the same size
# Baseline = this season's earlier weeks, else last season. Week 3 go/no-go
# (2026 Wks 1-3): the market priced both triggers (over hit 48.8% where it said
# 48.9% at the open), and Vault's big disagreements that AGREED with the news
# went 43-58 (it double-counts news the line already moved on) while those
# AGAINST it went 91-80. No-go for a news layer; this table keeps the test
# running as the sample grows. Depth-chart history isn't banked, so it's not
# a trigger yet.
USE_KEY = {"WR": "tgt", "TE": "tgt", "RB": "car", "QB": "att"}


def _load_news(season):
    def ld(name):
        try: return json.load(open(os.path.join(DATA, name)))
        except Exception: return {}
    s = str(season)
    prev = str(int(s) - 1) if s.isdigit() else None
    cur_s, cur_n = ld(f"nflverse_stats_{s}.json"), ld(f"nflverse_snaps_{s}.json")
    prv_s = ld(f"nflverse_stats_{prev}.json") if prev else {}
    prv_n = ld(f"nflverse_snaps_{prev}.json") if prev else {}
    played = defaultdict(set)                     # (team, wk, pos) -> names who played
    for n, rec in cur_s.items():
        for w in rec.get("weeks") or []:
            played[(rec.get("team"), w["wk"], rec.get("pos"))].add(n)
    return {"cur_s": cur_s, "cur_n": cur_n, "prv_s": prv_s, "prv_n": prv_n, "played": played}


def news_trigger(p, N):
    """('up'|'down'|'both'|None, teammate_out) for a settled prop, pre-game info only."""
    n, pos, team, W = p.get("name"), p.get("pos"), p.get("team"), p.get("week")
    k = USE_KEY.get(pos)
    if not k or W is None: return None, False
    rec = N["cur_s"].get(n) or {}
    wks = {w["wk"]: w for w in rec.get("weeks") or []}
    prior = sorted(w for w in wks if w < W)
    last = (wks[prior[-1]].get(k) or 0) if prior else None
    base_rows = [wks[w].get(k) or 0 for w in prior[:-1]] or [w.get(k) or 0 for w in (N["prv_s"].get(n) or {}).get("weeks") or []]
    base = sum(base_rows) / len(base_rows) if base_rows else None
    up = down = False
    if last is not None and base:
        r = (last + 0.5) / (base + 0.5)
        up |= r >= 1.5 and last - base >= 2
        down |= r <= 0.6 and base - last >= 2
    sn = {w["wk"]: w.get("off") for w in (N["cur_n"].get(n) or {}).get("weeks") or []}
    sprior = sorted(w for w in sn if w < W and sn[w] is not None)
    s_last = sn[sprior[-1]] if sprior else None
    s_rows = [sn[w] for w in sprior[:-1]] or [w.get("off") for w in (N["prv_n"].get(n) or {}).get("weeks") or [] if w.get("off") is not None]
    s_base = sum(s_rows) / len(s_rows) if s_rows else None
    if s_last is not None and s_base is not None:
        up |= s_last - s_base >= 15
        down |= s_base - s_last >= 15
    # top-usage teammate at his position did not play this week
    tot = defaultdict(float)
    for nm, r2 in N["cur_s"].items():
        if r2.get("team") == team and r2.get("pos") == pos and nm != n:
            for w in r2.get("weeks") or []:
                if w["wk"] < W: tot[nm] += w.get(k) or 0
    if not tot:
        for nm, r2 in N["prv_s"].items():
            if r2.get("team") == team and r2.get("pos") == pos and nm != n:
                tot[nm] += sum(w.get(k) or 0 for w in r2.get("weeks") or [])
    out = False
    played = N["played"].get((team, W, pos))
    if tot and played and n in played:
        top = max(tot, key=tot.get)
        out = top not in played
    up |= out
    return ("both" if up and down else "up" if up else "down" if down else None), out


def score_news(props):
    seasons = sorted({str(p.get("season")) for p in props if p.get("season")})
    if not seasons: return None
    N = _load_news(seasons[-1])
    cal = defaultdict(lambda: {"open": [0, 0.0, 0.0], "close": [0, 0.0, 0.0]})   # n, hits, market prob sum
    dis = defaultdict(lambda: [0, 0, Acc()])                                      # n, vault-side wins, paired LL
    model = SB.load_prop_model()
    for p in props:
        if str(p.get("season")) != seasons[-1]: continue
        a, lo, lc, proj = p.get("actual"), p.get("line_open"), p.get("line_close"), p.get("proj")
        if a is None or lc is None: continue
        trig, out = news_trigger(p, N)
        tag = {"up": "usage up / teammate out", "down": "usage down", "both": "mixed", None: "no news"}[trig]
        qo = devig_power(p.get("open_over"), p.get("open_under"))
        qc = devig_power(p.get("close_over"), p.get("close_under"))
        if qo is not None and lo is not None and sane_move(lo, lc) and abs(a - lo) > 1e-9:
            c = cal[tag]["open"]; c[0] += 1; c[1] += 1.0 if a > lo else 0.0; c[2] += qo
        if qc is not None and abs(a - lc) > 1e-9:
            c = cal[tag]["close"]; c[0] += 1; c[1] += 1.0 if a > lc else 0.0; c[2] += qc
            mp = model.get(p["market"])
            pv = SB.model_p_over(mp, proj, lc) if (mp and proj is not None) else None
            if pv is not None and abs(pv - qc) >= 0.08 and trig in ("up", "down", None):
                vault_over = pv > qc
                grp = ("no news" if trig is None else
                       "agrees with the news" if (vault_over == (trig == "up")) else "against the news")
                y = 1.0 if a > lc else 0.0
                d = dis[grp]; d[0] += 1; d[1] += 1 if (y == 1.0) == vault_over else 0; d[2].add(y, pv, qc)
    return {"trigger_vs_market": {k: {s2: ({"n": v[s2][0], "over_hit": round(v[s2][1] / v[s2][0], 4),
                                            "market_said": round(v[s2][2] / v[s2][0], 4)} if v[s2][0] else None)
                                      for s2 in ("open", "close")} for k, v in sorted(cal.items())},
            "big_disagreements": {k: {"n": v[0], "vault_side_won": v[1], "win": round(v[1] / v[0], 4) if v[0] else None,
                                      "score": v[2].out()} for k, v in sorted(dis.items())}}


# ── timing: does posting early pay? (plan Weeks 3-4, opening-window capture) ──
# Every Best Bets play (the card + the shadow log, best_bets_record.json) is
# graded at the line and price it POSTED with and at the close. Bucketed by
# how long before kickoff it posted. If early posting is where the value is,
# the posted-vs-close gap should be widest in the earliest buckets. Plays
# without a kickoff time (some rebuilt Wk 1-3 rows) are skipped.
TIMING_BUCKETS = ((72, "3+ days before"), (24, "1-3 days before"), (6, "6-24 hours before"), (0, "under 6 hours"))


def score_timing():
    try:
        rec = json.load(open(os.path.join(DATA, "best_bets_record.json")))
    except Exception:
        return None
    from datetime import datetime
    plays = {c["key"]: c for c in rec.get("shadow_picks") or []}
    plays.update({c["key"]: c for c in rec.get("picks") or []})
    out = {lbl: {"n": 0, "W": 0, "units": 0.0, "n_close": 0, "units_close": 0.0, "beat": 0, "n_clv": 0}
           for _, lbl in TIMING_BUCKETS}
    def ts(x):
        try: return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        except Exception: return None
    for c in plays.values():
        if c.get("result") not in ("W", "L"): continue
        t0, t1 = ts(c.get("posted")), ts(c.get("commence"))
        if not t0 or not t1: continue
        h = (t1 - t0).total_seconds() / 3600
        lbl = next(l for lim, l in TIMING_BUCKETS if h >= lim) if h >= 0 else None
        if not lbl: continue
        b = out[lbl]; b["n"] += 1; b["W"] += c["result"] == "W"; b["units"] += c.get("units") or 0
        if c.get("units_close") is not None: b["n_close"] += 1; b["units_close"] += c["units_close"]
        if c.get("beat_close") is not None: b["n_clv"] += 1; b["beat"] += 1 if c["beat_close"] else 0
    for b in out.values():
        b["units"] = round(b["units"], 2); b["units_close"] = round(b["units_close"], 2)
    return out


def verdict(s):
    # z = paired log-loss difference / its standard error. |z| >= 2 is roughly
    # the 95% line; below it the gap is indistinguishable from noise.
    if not s or s["n"] < 30 or s.get("z") is None: return "too few to read"
    if s["z"] >= 2: return "Vault better than the market"
    if s["z"] <= -2: return "market better than Vault"
    return "level with the market (within noise)"


def main():
    dry = "--dry" in sys.argv
    br = json.load(open(os.path.join(DATA, "bet_results.json")))
    try: gm = json.load(open(os.path.join(DATA, "game_model.json")))
    except Exception: gm = None
    pa, pb, pw = score_props(br.get("props") or [], SB.load_prop_model())
    hc = half_line_check(br.get("props") or [])
    ga, gb, gw = score_games(br.get("games") or [], gm)

    out = {"generated": br.get("generated"), "devig": "power",
           "props_half_line_check": hc,
           "props": {k: {"open": v["open"].out(), "close": v["close"].out(), "bets": pb[k].out()}
                     for k, v in sorted(pa.items())},
           "props_by_week": {str(w): {"open": v["open"].out(), "close": v["close"].out()} for w, v in sorted(pw.items())},
           "games": {k: {"close": v["close"].out(), "bets": gb[k].out()} for k, v in sorted(ga.items())},
           "games_by_week": {str(w): {"close": v["close"].out()} for w, v in sorted(gw.items())},
           "news": score_news(br.get("props") or []),
           "timing": score_timing()}
    for sec in ("props", "games"):
        for k, v in out[sec].items():
            v["verdict"] = verdict(v.get("close"))

    L = ["# Model scoreboard: Vault vs. the market", "",
         "_Week 1 of the model-upgrade plan. Every number compares Vault's probability with the market's "
         "no-vig probability for the SAME bet (same line, same result). Log-loss: lower is better. "
         "**Skill** = 1 − Vault/market log-loss: above 0 means Vault knew something the market didn't. "
         "No-vig = power method._", ""]

    def fmt(s):
        if not s: return "     –"
        return f"n={s['n']:4d}  LL {s['logloss_vault']:.4f} vs {s['logloss_market']:.4f}  skill {s['skill']:+.3f} z {s['z'] if s['z'] is not None else 0:+.1f}"
    def fu(x): return "   –  " if x is None else f"{x:+6.1f}u"
    def fp(x): return "  – " if x is None else f"{x * 100:4.0f}%"

    L += ["## Props", "", "```",
          f"{'market':<14}{'at the CLOSE':<52}{'at the OPEN':<52}verdict (close)"]
    for k, v in out["props"].items():
        L.append(f"{k:<14}{fmt(v['close']):<52}{fmt(v['open']):<52}{v['verdict']}")
    L += ["```"]
    if hc:
        L += ["", "### 0.5 lines: market vs. result (capture watch)", "",
              "_0.5 lines were excluded until the price capture was fixed; this checks they stay clean. "
              "|z| of 3+ means the banked prices are coming from another line again._", "", "```",
              f"{'market':<14}{'n':>5}{'market P(over)':>16}{'over rate':>11}{'z':>7}"]
        for k, v in hc.items():
            L.append(f"{k:<14}{v['n']:>5}{v['market_p_over'] * 100:>15.0f}%{v['over_rate'] * 100:>10.0f}%{v['z']:>+7.1f}")
        L += ["```"]
    L += ["", "### Props: line value and units on Vault's side", "", "```",
          f"{'market':<14}{'beat close':>11}{'avg CLV':>9}   {'open: win   units':>18}   {'close: win   units':>19}"]
    for k, v in out["props"].items():
        b = v["bets"]
        clv = "   – " if b["clv_prob"] is None else f"{b['clv_prob'] * 100:+5.1f}pp"
        L.append(f"{k:<14}{fp(b['beat_close']):>11}{clv:>9}   {fp(b['win_open']):>8} {fu(b['units_open']):>9}   {fp(b['win_close']):>9} {fu(b['units_close']):>9}")
    L += ["```", "", "## Game markets (at the close)", "", "```"]
    for k, v in out["games"].items():
        b = v["bets"]
        L.append(f"{k:<8}{fmt(v['close']):<52}{v['verdict']:<40} beat close {fp(b['beat_close'])}  units {fu(b['units_close'])}")
    nw = out.get("news")
    if nw:
        L += ["```", "", "## News triggers (plan Week 3)", "",
              "_Does fresh role news beat what the market already priced? Pre-game info only: a usage or snap-share jump "
              "or drop in the player's last game, or his position's top teammate not playing. **Go** only if Vault's big "
              "disagreements that agree with the news beat the ones without news._", "", "```",
              f"{'trigger':<26}{'OPEN: over hit vs market said':<34}{'CLOSE: over hit vs market said'}"]
        for k, v in nw["trigger_vs_market"].items():
            f2 = lambda x: "      –" if not x else f"n={x['n']:4d} {x['over_hit'] * 100:5.1f}% vs {x['market_said'] * 100:5.1f}%"
            L.append(f"{k:<26}{f2(v['open']):<34}{f2(v['close'])}")
        L += ["", "Vault vs market disagreements of 8+ pts (close):"]
        for k, v in nw["big_disagreements"].items():
            sc = v["score"]
            L.append(f"  {k:<24} n={v['n']:4d}  Vault's side won {v['vault_side_won']}-{v['n'] - v['vault_side_won']}"
                     + (f"  skill {sc['skill']:+.3f} z {sc['z']:+.1f}" if sc else ""))
    tm = out.get("timing")
    if tm and any(v["n"] for v in tm.values()):
        L += ["```", "", "## Timing: Best Bets by how early they posted (plan Weeks 3-4)", "",
              "_Every Best Bets play (the locked card plus the background log), graded at the line and price it posted "
              "with, then re-priced at the close. If posting early is where the value is, the gap between the two "
              "should be widest in the earliest rows._", "", "```",
              f"{'posted':<20}{'record':>9}{'units posted':>14}{'units at close':>16}{'beat close':>12}"]
        for _, lbl in TIMING_BUCKETS:
            v = tm[lbl]
            if not v["n"]: L.append(f"{lbl:<20}{'–':>9}"); continue
            bc = f"{v['beat']}/{v['n_clv']}" if v["n_clv"] else "–"
            L.append(f"{lbl:<20}{str(v['W']) + '-' + str(v['n'] - v['W']):>9}{v['units']:>+13.1f}u{v['units_close']:>+15.1f}u{bc:>12}")
    L += ["```", "", "- Spread/total market = no-vig closing price at the number where banked (from Sep 28), else 50/50; "
          "Vault's cover chance uses its line and the fitted sd. ML = no-vig closing moneyline.", "",
          "## By week (props at the close / games at the close)", "", "```"]
    for w in sorted(set(out["props_by_week"]) | set(out["games_by_week"]), key=int):
        pc = (out["props_by_week"].get(w) or {}).get("close")
        gc = (out["games_by_week"].get(w) or {}).get("close")
        L.append(f"Wk {w:>2}  props {fmt(pc):<52} games {fmt(gc)}")
    L += ["```", "", "## How to read this", "",
          "- A model change ships only if it moves **skill** up on the markets it touches, over enough bets. "
          "**z** is the log-loss gap divided by its standard error on the same bets: 2 or more (either way) is a real "
          "difference, under 2 is noise. Below 30 bets the verdict says too few.",
          "- CLV is the fast signal for game lines. For props it is weak (low limits let one bet push the line), "
          "so props lean on skill, calibration and units by market and side.",
          "- Open vs. close units show what betting when Vault grades is worth versus waiting.", "",
          "---", "_Auto-generated by `scripts/build_model_scoreboard.py` off the settlement tape; refreshes with each settle._"]

    for sec, lbl in (("props", "props"), ("games", "games")):
        a = out[sec].get("all" if sec == "props" else "games")
        if a and a.get("close"):
            c = a["close"]
            print(f"[scoreboard] {lbl}: n={c['n']} LL vault {c['logloss_vault']:.4f} vs market {c['logloss_market']:.4f} "
                  f"skill {c['skill']:+.3f} -> {a['verdict']}")
    if dry:
        print("\n".join(L)); return
    json.dump(out, open(os.path.join(DATA, "model_scoreboard.json"), "w"), indent=1)
    os.makedirs(os.path.join(ROOT, "docs", "retro"), exist_ok=True)
    open(os.path.join(ROOT, "docs", "retro", "model-scoreboard.md"), "w").write("\n".join(L) + "\n")
    print("[scoreboard] wrote data/model_scoreboard.json + docs/retro/model-scoreboard.md")


if __name__ == "__main__":
    main()
