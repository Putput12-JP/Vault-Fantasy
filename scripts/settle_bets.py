#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · SETTLEMENT + CLV HARNESS
#      data/prop_line_history.json  + data/game_line_history.json
#      + data/nflverse_stats_<season>.json + nflverse games.csv
#        →  data/bet_results.json   (per-pick settled ledger)
#        →  data/edge_scoreboard.json (aggregates: UI + model feedback)
#
#  Closes the loop prop-edge-model-plan.md calls #5. The snapshots are RETAINED
#  (finished weeks are kept, unlike the live board), so this rebuilds the whole
#  ledger deterministically each run — no append/merge, no drift.
#
#  CLV (closing-line value) is the PRIMARY signal: it accrues every week at low
#  variance, so it's the fast read on whether our number is sharp. Realized win%
#  is the slower, higher-variance confirmation. The builders read the scoreboard
#  back to sharpen the model over the season (docs/edge-feedback-loop.md).
#
#  Usage:  python3 scripts/settle_bets.py
#          python3 scripts/settle_bets.py --dry            (compute, don't write)
#          python3 scripts/settle_bets.py --season 2026    (limit to one season)
# ════════════════════════════════════════════════════════════════════════════
import argparse, csv, io, json, math, os, sys, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
# ESPN public scoreboard — a SECOND, faster score source. nflverse's games.csv
# is canonical but publishes hours-to-a-day after a game; ESPN carries the final
# within minutes. Used only to fill games nflverse hasn't scored yet, so a game
# (and any bet tracked on it) settles the same night. nflverse always wins on
# conflict, and settlement rebuilds from scratch each run, so a later nflverse
# correction overrides ESPN automatically. Scores only — player props still need
# nflverse box scores (ESPN's scoreboard has no per-player stats at this cadence).
ESPN_SB_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_STYPE = {"pre": 1, "reg": 2, "regular": 2, "post": 3, "postseason": 3}

# Vault/Sleeper team codes → nflverse team codes, so the game-settlement join
# matches. nflverse's games.csv calls the Rams "LA" (Vault ships "LAR"); the
# rest are historical relocations that surface when settling archive weeks.
# Same map the model builders use (build_game_model.py etc.). Without this a
# whole game — SF@LAR — never joins SF@LA and its spread/total/ML bets sit
# unsettled forever even after the box score lands.
TEAM_ALIAS = {"OAK": "LV", "LVR": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "WSH": "WAS"}
def team_nfl(t): return TEAM_ALIAS.get(t, t)

# Share the shipped serving math (dist / calibration / shrink) with the builder.
sys.path.insert(0, HERE)
import build_prop_projections as B  # noqa: E402

# ── market → nflverse weekly stat column(s) (superset of B.MARKETS; combos sum) ─
COL = {
    "pass_yd": ("pyds",), "pass_att": ("att",), "pass_cmp": ("cmp",),
    "pass_td": ("ptds",), "pass_int": ("ints",),
    "rush_yd": ("ryds",), "rush_att": ("car",), "rush_td": ("rtds",),
    "rec": ("rec",), "rec_yd": ("recyds",), "rec_td": ("rectds",),
    "anytime_td": ("rtds", "rectds"), "rush_rec_yd": ("ryds", "recyds"),
    "pass_rush_yd": ("pyds", "ryds"),
}
COUNT_MK = {"pass_att", "pass_cmp", "rush_att", "rec", "pass_int",
            "pass_td", "rush_td", "rec_td", "anytime_td"}   # integer stats → push only on integer line
K_BLEND = 300        # sample-size the in-season blend weight is shrunk against (large ⇒ early weeks barely move)
EPS = 1e-6


# ── odds helpers ────────────────────────────────────────────────────────────
def am_prob(a):
    if a is None: return None
    return 100.0 / (a + 100.0) if a > 0 else (-a) / (-a + 100.0)

def am_dec(a):
    if a is None: return None
    return a / 100.0 + 1.0 if a > 0 else 100.0 / (-a) + 1.0

def devig(over, under):
    """Two-way American prices → vig-free P(over). None if either side missing."""
    po, pu = am_prob(over), am_prob(under)
    if po is None or pu is None or (po + pu) == 0: return None
    return po / (po + pu)

def clamp(p, lo=EPS, hi=1 - EPS): return max(lo, min(hi, p))
def logit(p): p = clamp(p); return math.log(p / (1 - p))
def sig(x): return 1 / (1 + math.exp(-x))
def logloss1(y, p): p = clamp(p); return -(y * math.log(p) + (1 - y) * math.log(1 - p))


# ── model P(over) for a market's shipped params (mirrors prop-model.js serving) ─
def load_prop_model():
    try:
        m = json.load(open(os.path.join(DATA, "prop_model.json")))
        return m.get("markets", m)
    except Exception:
        return {}

# ── point-in-time prop model ─────────────────────────────────────────────────
# Every prop is graded with the model Vault was SHOWING when its line was first
# graded, never today's refit. The in-season corrections (real-line recal,
# projection-bias and in-season overlays) are fitted on settled results, so
# grading old weeks with the current file lets the record see the answers: it
# moved 448 of 2,007 Week 1-3 grades in 2026 (docs/retro/week-4-deep-dive.md).
# data/prop_model_versions.json holds each published model with the time it went
# live (build_prop_projections.py appends; scripts/backfill_prop_model_versions.py
# rebuilds it from git). No file => today's model, the old behaviour.
_PM_VERSIONS = None

def load_prop_model_versions():
    """[(epoch, from_iso, markets)] oldest first; [] when the file is missing."""
    global _PM_VERSIONS
    if _PM_VERSIONS is None:
        out = []
        try:
            blob = json.load(open(os.path.join(DATA, "prop_model_versions.json")))
            for v in blob.get("versions") or []:
                t = _parse_ts(v.get("from"))
                if t is not None and v.get("markets"):
                    out.append((t, v["from"], v["markets"]))
        except Exception:
            pass
        out.sort(key=lambda x: x[0])
        _PM_VERSIONS = out
    return _PM_VERSIONS

def prop_model_at(ts, current):
    """(markets, from_iso) live at epoch `ts`: the newest version published at or
    before it. A line first seen before the oldest version uses the oldest one.
    No history or no timestamp -> (current, None)."""
    V = load_prop_model_versions()
    if not V or ts is None:
        return current, None
    pick = V[0]
    for v in V:
        if v[0] <= ts: pick = v
        else: break
    return pick[2], pick[1]

def prop_model_for_row(row, current):
    """The markets a settled bet_results row was graded with (its `model_from`),
    so downstream scoring (scoreboard, calibration) stays point-in-time too."""
    f = row.get("model_from")
    if f:
        for _, frm, m in load_prop_model_versions():
            if frm == f:
                return m
    return current

# ── structurally weak markets (grade capped at C) ────────────────────────────
# Mirror of the board's WEAK_MK (index.html) and build_best_bets.mjs: markets
# where Vault's projection has shown no edge over the sportsbook line, so the
# board holds their grade at C ("thin edge") and they can't headline. Each
# market carries the time it joined the list, so the record shows what the
# board showed: a prop first graded before then keeps its letter. `grade_raw`
# keeps the uncapped letter so a market can be re-tested and dropped from the
# list the moment it clears break-even. Keep all three lists in step.
WEAK_MK = {
    "pass_yd": "2026-09-25T01:08:21Z", "pass_cmp": "2026-09-25T01:08:21Z",      # 845360ed
    "pass_int": "2026-09-25T01:08:21Z", "rush_rec_yd": "2026-09-25T01:08:21Z",
    # Week 4 retro: the model carries no information beyond the market on pass
    # attempts (walk-forward weight 0.00) and A/B pass-attempt picks went 9-14.
    "pass_att": "2026-10-05T21:08:00Z",
}

def weak_cap(letter, market, ts):
    """Cap an A/B letter at C on a weak market graded on or after it joined."""
    since = WEAK_MK.get(market)
    if letter in ("A", "B") and since and ts is not None and ts >= (_parse_ts(since) or 0):
        return "C"
    return letter

# ── shadow: history-length shift (docs/history-shift-backtest.json) ─────────
# The season-holdout found P(over) over-promises for players with little game
# history (receptions: over hits ~13pt under promise at 3-8 games, honest by
# 21+). data/prop_history_shift.json carries a per-market logit shift per
# history bin, fit on past seasons only. It is SHADOW: nothing on the board
# reads it. Settlement logs the shifted pick beside the live one (p_hist /
# side_hist / won_hist) so the two can be compared on real closing lines before
# anyone switches it on. Missing file => every shadow field is None.
# ── Vault team-total lean (SHADOW, 2026-09-26) ──────────────────────────────
# Wk1-3 (scripts/analyze_game_script_props.py): A/B props on the side AGAINST
# Vault's team-total lean went 60.4%, +18.8% ROI (144 picks), with it -3.7%;
# Vault's team leans themselves went 16-23. Recorded per prop so the Track
# Record can test it forward before the board leans on it. Lean = Vault's
# implied team points (raw game model, banked in game_line_history) minus the
# market's implied team total (total/2 - team spread/2) at the last snapshot,
# at the same 1pt bar the analysis used. The board filter mirrors this
# (index.html _teamLeanOf).
TEAM_LEAN_PTS = 1.0

def pregame_close(g):
    """(market sample, vault line) as of kickoff: the last sample stamped at or
    before `commence` that has a total + spread, and the last banked Vault line
    by then. Samples after kickoff are ignored (the model refits weekly, and a
    post-game refit must never grade its own game)."""
    kick = g.get("commence") or ""
    samples = [x for x in (g.get("samples") or []) + [g.get("cur") or {}]
               if x and (not kick or (x.get("ts") or "") <= kick)]
    close = next((x for x in reversed(samples) if x.get("total") is not None and x.get("spread") is not None), None)
    vault = next((x["vault"] for x in reversed(samples)
                  if x.get("vault") and x["vault"].get("total") is not None and x["vault"].get("spread") is not None), None)
    return close, vault

def load_team_leans():
    """{(season, seasonType, week, team): (market_implied, vault_implied)}.
    The history carries FUTURE games mis-tagged with the current week (seven
    "week 1" PHI games), so a (week, team) key keeps the EARLIEST kickoff, which
    is the real game. Not keyed on the prop's opponent: that field is stale or
    missing on ~20% of props (LAR "vs SF" in weeks 1 and 2, JAC vs JAX)."""
    try:
        games = json.load(open(os.path.join(DATA, "game_line_history.json"))).get("games", {})
    except Exception:
        return {}
    out, kick = {}, {}
    for g in games.values():
        close, vault = pregame_close(g)
        if not close or not vault:
            continue
        k0 = g.get("commence") or "9999"
        home, away = team_nfl(g["home"]), team_nfl(g["away"])
        for is_home in (True, False):
            team = home if is_home else away
            sp, vsp = float(close["spread"]), float(vault["spread"])       # HOME lines
            mi = float(close["total"]) / 2 - (sp if is_home else -sp) / 2
            vi = float(vault["total"]) / 2 - (vsp if is_home else -vsp) / 2
            key = (str(g.get("season")), (g.get("seasonType") or "").lower(), g.get("week"), team)
            if key not in out or k0 < kick[key]:
                out[key], kick[key] = (mi, vi), k0
    return out

def team_lean(mi, vi):
    d = vi - mi
    return "over" if d >= TEAM_LEAN_PTS else "under" if d <= -TEAM_LEAN_PTS else "neutral"

def load_history_shift():
    try:
        return json.load(open(os.path.join(DATA, "prop_history_shift.json")))
    except Exception:
        return None

def history_shift_p_over(hs, market, p_over, hist_n):
    """P(over) with the market's history-bin shift applied, or None when the
    market isn't shifted (or no model prob)."""
    if not hs or p_over is None or hist_n is None:
        return None
    m = (hs.get("markets") or {}).get(market)
    if not m:
        return None
    for i, (lo, hi) in enumerate(hs.get("bins") or []):
        if hist_n >= lo and (hi is None or hist_n <= hi):
            p = clamp(p_over, 0.01, 0.99)
            return sig(logit(p) + m["shift"][i])
    return None

def close_prices(cls):
    """{"close_over", "close_under"} from a closing sample, or both None when
    the pair isn't a real two-way market. Snapshots carry junk (a -19900 under;
    a +483 over paired with a -100 placeholder), so accept a pair only when its
    combined implied probability is 100.5-115% (median real prop hold ~105%;
    pick'em apps run to ~12.5%, e.g. Sleeper -128/-128). The floor is above
    100%: +100/-100 is a no-price placeholder, not a market."""
    o, u = cls.get("over"), cls.get("under")
    po, pu = am_prob(o), am_prob(u)
    if po is None or pu is None or not (1.005 <= po + pu <= 1.15):
        return {"close_over": None, "close_under": None}
    return {"close_over": o, "close_under": u}

def book_prices(q, line):
    """{book: [over, under]} for books quoting THIS line with a sane two-way
    price (same 100.5-115% band as close_prices). q = snapshot per-book list
    [[book, line, over, under], ...]; a book on another number is a different
    bet, so it's left out rather than priced against this line."""
    out = {}
    for row in (q or []):
        try:
            book, ln, o, u = row
        except (TypeError, ValueError):
            continue
        if not book or o is None or u is None:
            continue
        if line is not None and ln is not None and abs(float(ln) - float(line)) > 1e-9:
            continue
        po, pu = am_prob(o), am_prob(u)
        if po is None or pu is None or not (1.005 <= po + pu <= 1.15):
            continue
        out[book] = [o, u]
    return out or None

def model_p_over(mp, proj, line):
    if mp is None or proj is None or line is None: return None
    try:
        raw = B.prob_fn_for(mp)(proj, line)
        p = B.apply_calib(mp.get("calib"), raw)
        p = B.shrink_prob(p, mp.get("shrink", 1.0))
        return clamp(p)
    except Exception:
        return None


# ── actuals ─────────────────────────────────────────────────────────────────
def load_actuals(season):
    """nflverse_stats for a season → {name: {wk: {col: val}}}. Regular/postseason
    weeks only (preseason is never in here, which is why we gate settlement to
    non-preseason: a 'pre' week N would otherwise false-match regular week N)."""
    # ONLY the per-season file — never the generic nflverse_stats.json alias,
    # which is season-ambiguous (it holds the current season) and would settle
    # e.g. 2026 week-1 props against 2025 week-1 actuals before 2026 data lands.
    path = os.path.join(DATA, f"nflverse_stats_{season}.json")
    if not os.path.exists(path):
        return {}
    try:
        blob = json.load(open(path))
    except Exception:
        return {}
    out = {}
    for name, rec in blob.items():
        if not isinstance(rec, dict): continue
        wk = {}
        for row in rec.get("weeks", []) or []:
            if isinstance(row, dict) and row.get("wk") is not None:
                wk[int(row["wk"])] = row
        if wk: out[name] = wk
    _overlay_espn(out, season)
    return out


def _nkey(s):
    """Loose name key for cross-source joins (matches VaultPropHistory's nkey)."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return "".join(c for c in s.lower() if c.isalpha())


def _overlay_espn(out, season):
    """Fill weeks nflverse hasn't published yet from the ESPN box-score overlay
    (data/espn_player_stats_<season>.json). nflverse ALWAYS wins: a week already
    present is never overwritten, so a later nflverse run supersedes ESPN. This is
    what lets a PLAYER PROP settle within minutes of the game going final instead
    of waiting hours-to-a-day for nflverse. Missing overlay → no-op."""
    path = os.path.join(DATA, f"espn_player_stats_{season}.json")
    if not os.path.exists(path):
        return
    try:
        ov = json.load(open(path))
    except Exception:
        return
    bykey = {_nkey(n): n for n in out}          # nflverse name reachable by loose key
    for name, rec in ov.items():
        if not isinstance(rec, dict): continue
        tgt = bykey.get(_nkey(name), name)      # append to the nflverse entry if one matches
        wk = out.setdefault(tgt, {})
        for row in rec.get("weeks", []) or []:
            if isinstance(row, dict) and row.get("wk") is not None:
                w = int(row["wk"])
                if w not in wk:                 # nflverse wins on conflict
                    wk[w] = row

def actual_for(actuals, name, week, market):
    cols = COL.get(market)
    if not cols: return None
    wk = actuals.get(name)
    if not wk: return None
    row = wk.get(int(week))
    if not row: return None
    tot, seen = 0.0, False
    for c in cols:
        v = row.get(c)
        if isinstance(v, (int, float)):
            tot += v; seen = True
    return tot if seen else None

def games_played(actuals, name, before_week):
    wk = actuals.get(name)
    return sum(1 for w in wk if w < before_week) if wk else 0


# ── grade (break-even-aware, confidence-shrunk by games so far) ──────────────
# Cut-offs MUST match the board's gradeLetter in index.html (A >= +5pt over
# break-even, B >= +3, C >= +1, D >= -2), or a Track Record "A" is a different
# claim than the "A" users saw. Until 2026-09-26 this ran stricter (10/5/2/0).
def grade_letter(padj, be=0.55):
    e = padj - be
    if e >= 0.05: return "A"
    if e >= 0.03: return "B"
    if e >= 0.01: return "C"
    if e >= -0.02: return "D"
    return "F"

def shrink_p(p_side, g):
    """Sample-size shrink toward a coin flip that only ever REMOVES confidence.
    A side Vault already puts under 50% keeps its raw prob: pulling it toward
    0.5 pushed it UP and graded a +298 TD over A at 24% vs a 25% bar (board,
    2026-09-26). Mirrors index.html _shrinkP; neutral on Wk1-3 volume props
    (scripts/backtest_grade_anchor.py)."""
    return p_side if p_side < 0.5 else 0.5 + (p_side - 0.5) * g / (g + 6)

def grade_for(p_side, g, be=0.55):
    if p_side is None: return None
    return grade_letter(shrink_p(p_side, g), be)

# The pre-2026-09-26 rule (shrink pushed sub-50% sides UP toward 0.5), kept as
# `grade_boost` so the Track Record can show what changed on past weeks.
def grade_boost_for(p_side, g, be=0.55):
    if p_side is None: return None
    return grade_letter(0.5 + (p_side - 0.5) * g / (g + 6), be)

# SHADOW (not on the board): the same shrink, but toward the side's no-vig
# MARKET probability instead of a coin flip. On a juiced line the coin-flip
# anchor hands the plus-money side a grade whenever Vault is near 50/50 (Olave
# rec 5.5 U +133, 2026 w3: Vault 49%, graded A). The Wk1-3 replay
# (scripts/backtest_grade_anchor.py) could NOT show that was wrong: those picks
# won ~45% vs a ~40% bar. So this is recorded next to `grade` until enough weeks
# settle to decide. No clean two-way price -> None (no market to anchor to).
def grade_mkt_for(p_side, g, be, q_side):
    if p_side is None or be is None or q_side is None: return None
    padj = q_side + (p_side - q_side) * g / (g + 6)
    return grade_letter(padj, be)

# ── grade recalibration (isotonic / PAV) ─────────────────────────────────────
# The shrink above corrects for SAMPLE SIZE, but the first settled weeks showed a
# second miss it can't touch: overconfidence at high padj (grade A promised ~65%,
# hit ~51%), a model bias tied to CONVICTION not game count. The fix is a monotone
# map from padj to the realized win rate, learned from settled outcomes — isotonic
# regression, so it is ORDER-PRESERVING: tiers never reshuffle, the top just stops
# overstating. Published to data/grade_recal.json and applied on the board through
# window.VaultGradeRecal, exactly the VaultTradeMarket contract: INERT until it has
# enough data. Below RECAL_MIN_WEEKS / RECAL_MIN_SAMPLES the file ships ready:false
# and every caller falls back to identity, so a cold start or early season costs
# nothing. Do NOT lower the gate to publish sooner — a curve fit on one or two
# weeks would overfit the very noise it exists to smooth (see the K-bump retro:
# 2 weeks could not even tell thin-sample from rich-sample overconfidence apart).
RECAL_MIN_WEEKS = 4
RECAL_MIN_SAMPLES = 300
RECAL_K = 6   # MUST match grade_for's shrink denominator, or the fit is on the wrong x

def _recal_padj(p_side, g):
    return p_side if p_side < 0.5 else 0.5 + (p_side - 0.5) * g / (g + RECAL_K)   # = shrink_p

def _pav(points):
    """Weighted Pool-Adjacent-Violators isotonic (non-decreasing) fit.
    points: list of (x, y, w) sorted by x ascending. Returns fitted y per point."""
    stack = []   # each block: [mean_y, weight, size]
    for _x, y, w in points:
        cur = [y, w, 1]
        while stack and stack[-1][0] >= cur[0]:
            pm, pw, ps = stack.pop()
            wm = pw + cur[1]
            cur = [(pm * pw + cur[0] * cur[1]) / wm, wm, ps + cur[2]]
        stack.append(cur)
    out = []
    for m, _w, s in stack:
        out.extend([m] * s)
    return out

def build_grade_recal(prop_picks):
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = [p for p in prop_picks
            if not p.get("push") and p.get("p_model") is not None
            and p.get("grade_n") is not None and p.get("won_close") is not None]
    weeks = sorted({p.get("week") for p in rows if p.get("week") is not None})
    out = {"generated": now, "method": "isotonic-pav", "k_shrink": RECAL_K,
           "min_weeks": RECAL_MIN_WEEKS, "min_samples": RECAL_MIN_SAMPLES,
           "n_weeks": len(weeks), "n_samples": len(rows), "weeks": weeks}
    if len(weeks) < RECAL_MIN_WEEKS or len(rows) < RECAL_MIN_SAMPLES:
        out["ready"] = False   # inert: the board applies identity until this clears
        return out
    # Bin padj to 0.01 first (weighted mean outcome per bin), then PAV across bins:
    # a compact, stable curve (≤ ~40 knots) that doesn't chase individual coin-flips.
    agg = {}
    for p in rows:
        pj = _recal_padj(p["p_model"], p["grade_n"])
        k = round(pj, 2)
        a = agg.setdefault(k, [0.0, 0.0, 0])
        a[0] += pj; a[1] += p["won_close"]; a[2] += 1
    keys = sorted(agg)
    pts = [(agg[k][0] / agg[k][2], agg[k][1] / agg[k][2], agg[k][2]) for k in keys]
    fit = _pav(pts)
    knots = [[round(pts[i][0], 4), round(fit[i], 4)] for i in range(len(pts))]
    out["ready"] = True
    out["domain"] = [knots[0][0], knots[-1][0]]
    out["knots"] = knots
    return out


# ── prop settlement ─────────────────────────────────────────────────────────
def settle_props(season_filter=None):
    try:
        blob = json.load(open(os.path.join(DATA, "prop_line_history.json")))
    except Exception:
        return [], {"reason": "no prop_line_history.json"}
    props = blob.get("props", {})
    # Dedup by pick identity (not by history-key): adding seasonType to the
    # snapshot key means one live prop can be retained under both the old and new
    # key format with identical body fields. Collapse to the freshest (latest
    # lastSeen, then most samples) so a settled pick is never double-counted.
    dedup = {}
    for r in props.values():
        ident = (str(r.get("season")), (r.get("seasonType") or "").lower(),
                 r.get("week"), r.get("pid"), r.get("market"))
        cur = dedup.get(ident)
        if cur is None:
            dedup[ident] = r; continue
        better = (r.get("lastSeen") or "", len(r.get("samples") or [])) > \
                 (cur.get("lastSeen") or "", len(cur.get("samples") or []))
        if better: dedup[ident] = r
    actuals_cache, model, hshift = {}, load_prop_model(), load_history_shift()
    leans = load_team_leans()
    kickoffs = load_kickoffs()
    picks, unmatched, unsettled = [], 0, 0
    n_kick = n_clamped = n_no_pregame = 0

    for r in dedup.values():
        seasonType = (r.get("seasonType") or "").lower()
        if seasonType == "pre":       # preseason props settle against nothing meaningful; skip
            continue
        season = str(r.get("season"))
        if season_filter and season != str(season_filter): continue
        market, name, week = r.get("market"), r.get("name"), r.get("week")
        if market not in COL or not name or week is None:
            continue
        if season not in actuals_cache:
            actuals_cache[season] = load_actuals(season)
        actuals = actuals_cache[season]
        # Prior season's game log feeds the early-season grade shrink (below): a
        # Week-1 pick has zero in-season games, which otherwise collapses every
        # grade to F. Cached the same way; missing file → {} → no supplement.
        prior = str(int(season) - 1) if season.isdigit() else None
        if prior and prior not in actuals_cache:
            actuals_cache[prior] = load_actuals(prior)
        prior_actuals = actuals_cache.get(prior, {})

        actual = actual_for(actuals, name, week, market)
        if actual is None:            # game not played yet, or name didn't join
            unsettled += 1
            if name not in actuals: unmatched += 1
            continue

        opn = r.get("open") or {}
        # Close = last snapshot before kickoff (games.csv by team; the record's
        # own banked `commence` when nflverse has no row for it).
        kick = kickoffs.get((season, str(week), team_nfl(r.get("team")))) or r.get("commence")
        cls, cur_pre = pregame_prop_close(r, kick)
        if kick:
            n_kick += 1
            if cls is None:
                n_no_pregame += 1; unsettled += 1; continue
            if cls is not (r.get("samples") or [r.get("cur")])[-1]:
                n_clamped += 1
        line_o, line_c = opn.get("line"), cls.get("line")
        proj = opn.get("proj")
        if line_o is None or line_c is None:
            unsettled += 1; continue

        # Vault's side is set at the flag (open): over if our projection beats the line.
        side = None
        if proj is not None:
            side = "over" if proj > line_o else "under"

        # outcome settled at the CLOSING line (the number a bettor actually gets)
        is_count = market in COUNT_MK
        push = is_count and float(line_c) == round(float(line_c)) and abs(actual - line_c) < 1e-9
        over_won = actual > line_c if is_count else actual > line_c
        won_close = won_open = None
        if side and not push:
            win_side = "over" if actual > line_c else "under"
            won_close = 1.0 if side == win_side else 0.0
            win_side_o = "over" if actual > line_o else "under"
            won_open = 1.0 if side == win_side_o else 0.0

        # ── CLV ──────────────────────────────────────────────────────────────
        # line CLV signed to our side: positive = market moved to give us the better number.
        clv_line = None
        if side == "over":  clv_line = line_c - line_o
        elif side == "under": clv_line = line_o - line_c
        # no-vig probability CLV from the two-way prices (book-agnostic; ~0 on flat pickem)
        q_o = devig(opn.get("over"), opn.get("under"))
        q_c = devig(cls.get("over"), cls.get("under"))
        clv_prob = None
        if side and q_o is not None and q_c is not None:
            qo_side = q_o if side == "over" else 1 - q_o
            qc_side = q_c if side == "over" else 1 - q_c
            clv_prob = qc_side - qo_side       # positive = market came to agree with us
        # price CLV on our side (decimal odds we got vs the close)
        po_side = (opn.get("bestOver") if side == "over" else opn.get("bestUnder"))
        pc_side = (cls.get("bestOver") if side == "over" else cls.get("bestUnder"))
        clv_price = None
        do, dc = am_dec(po_side), am_dec(pc_side)
        if do is not None and dc is not None: clv_price = do - dc

        beat_close = None
        if clv_line is not None:
            beat_close = 1.0 if (clv_line > 1e-9 or (abs(clv_line) < 1e-9 and (clv_prob or 0) > 1e-9)
                                 or (abs(clv_line) < 1e-9 and (clv_price or 0) > 1e-9)) else 0.0

        # ── model vs market probabilities (blend-weight + reliability inputs) ─
        # Graded with the model live when this line was first graded (see
        # prop_model_at), not today's refit.
        t_graded = _parse_ts(opn.get("ts") or r.get("firstSeen"))
        model_t, model_from = prop_model_at(t_graded, model)
        p_model = model_p_over(model_t.get(market) if market in model_t else None, proj, line_o)
        p_model_side = None
        if p_model is not None and side:
            p_model_side = p_model if side == "over" else 1 - p_model
        p_mkt_side = None
        if q_o is not None and side:
            p_mkt_side = q_o if side == "over" else 1 - q_o
        # Confidence sample for the grade shrink. In-season games are the real
        # signal, but early in the year there are few (zero in Week 1), so borrow
        # the player's prior-season track record and let it FADE as in-season
        # sample accrues: at 0 in-season games the full prior season counts, by
        # mid-season it is a minor top-up. Capped at one season so playoff weeks
        # don't over-credit. Rookies / role-less players still shrink hard (no
        # prior log), which is correct.
        g_in = games_played(actuals, name, week)
        g_prior = min(games_played(prior_actuals, name, 10 ** 9), 17)
        g_shrink = g_in + g_prior * 6.0 / (g_in + 6.0)
        # PRICE-AWARE grade (what the board shows by default): the same shrink,
        # judged against the break-even the side's OPENING price implies (what
        # Vault saw when it graded) instead of a flat 0.55. A -130 under needs
        # 56.5%, a +100 over 50%. No clean two-way open price (pickem-only
        # lines) -> the flat 0.55, same fallback as the board. grade_flat keeps
        # the old flat-bar grade for comparison. Backtest:
        # scripts/backtest_price_grades.py.
        opx = close_prices(opn)      # same two-way sanity check, on the open
        be_open = am_prob(opx["close_over"] if side == "over" else opx["close_under"]) if side else None
        grade_flat = grade_for(p_model_side, g_shrink) if p_model_side is not None else None
        grade = (grade_for(p_model_side, g_shrink, be_open if be_open is not None else 0.55)
                 if p_model_side is not None else None)
        # Shadow grade-anchor test (grade_mkt_for above). Graded on BOTH sides:
        # `side` is the projection's side, but the board grades the other card
        # too, and that ALT side is exactly where the plus-money A's come from.
        # won_alt is simply the other side of the same settled result.
        grade_mkt = grade_alt = grade_mkt_alt = won_alt = None
        if p_model_side is not None and side:
            alt = "under" if side == "over" else "over"
            be_alt = am_prob(opx["close_over"] if alt == "over" else opx["close_under"])
            q_side = None
            if be_open is not None and be_alt is not None:
                q_side = be_open / (be_open + be_alt)          # no-vig share of THIS side
            grade_mkt = grade_mkt_for(p_model_side, g_shrink, be_open, q_side)
            grade_alt = grade_for(1 - p_model_side, g_shrink, be_alt if be_alt is not None else 0.55)
            grade_mkt_alt = grade_mkt_for(1 - p_model_side, g_shrink, be_alt,
                                          None if q_side is None else 1 - q_side)
            if won_close is not None:
                won_alt = 1.0 - won_close
        # Weak markets: every letter is held at C once the market joined WEAK_MK,
        # same as the board; grade_raw keeps the uncapped live letter.
        grade_raw = grade
        grade, grade_flat, grade_mkt, grade_alt, grade_mkt_alt = (
            weak_cap(x, market, t_graded) for x in (grade, grade_flat, grade_mkt, grade_alt, grade_mkt_alt))

        # Shadow pick from the history-shifted P(over): its own side (the shift
        # can flip a thin lean), settled at the same closing line. History is the
        # backtest's definition: every prior-season game plus in-season games
        # before this week, uncapped.
        hist_n = g_in + games_played(prior_actuals, name, 10 ** 9)
        p_h = history_shift_p_over(hshift, market, p_model, hist_n)
        side_h = p_hist = won_hist = None
        if p_h is not None:
            side_h = "over" if p_h > 0.5 else "under"
            p_hist = p_h if side_h == "over" else 1 - p_h
            if not push:
                won_hist = 1.0 if side_h == ("over" if actual > line_c else "under") else 0.0

        tl = leans.get((season, seasonType, week, team_nfl(r.get("team"))))

        picks.append({
            "kind": "prop", "season": season, "seasonType": seasonType, "week": week,
            "pid": r.get("pid"), "name": name, "team": r.get("team"), "pos": r.get("pos"),
            "opp": r.get("opp"), "market": market, "side": side,
            "line_open": line_o, "line_close": line_c, "proj": proj, "actual": actual,
            "push": bool(push), "won_close": won_close, "won_open": won_open,
            "clv_line": clv_line, "clv_prob": clv_prob, "clv_price": clv_price,
            "beat_close": beat_close,
            "p_model": p_model_side, "p_market": p_mkt_side, "games": g_in,
            "grade_n": round(g_shrink, 2), "grade": grade, "grade_raw": grade_raw,
            "model_from": model_from,
            "hist_n": hist_n, "p_hist": p_hist, "side_hist": side_h, "won_hist": won_hist,
            # Closing consensus PRICES at line_close (both sides), so units can be
            # scored at the real juice instead of a flat -110. None unless the
            # pair is a sane two-way market; see close_prices(). bestOver/Under
            # are deliberately NOT used: they mix in alt-line prices (+1329 on a
            # 4.5-reception line) and would invent profit.
            **close_prices(cls),
            "open_over": opx["close_over"], "open_under": opx["close_under"],
            # Per-book prices (snapshot q), for +EV-by-book on the Track Record.
            # Open = the opening snapshot's books; props opened before per-book
            # capture use q0, the first per-book read (books_open_src says which).
            "books_open": book_prices((opn.get("q") if opn.get("q") else (r.get("q0") or {}).get("q")), line_o),
            "books_open_src": ("open" if opn.get("q") else ("first_seen" if r.get("q0") else None)),
            "books_close": book_prices(((cur_pre or {}).get("q")), line_c),
            "grade_flat": grade_flat,
            "grade_boost": (weak_cap(grade_boost_for(p_model_side, g_shrink, be_open if be_open is not None else 0.55),
                                     market, t_graded) if p_model_side is not None else None),
            "grade_mkt": grade_mkt, "grade_alt": grade_alt,
            "grade_mkt_alt": grade_mkt_alt, "won_alt": won_alt,
            # Vault team-total lean shadow (see load_team_leans)
            "team_imp": round(tl[0], 2) if tl else None, "vault_team_imp": round(tl[1], 2) if tl else None,
            "vault_team_lean": team_lean(*tl) if tl else None,
        })

    return picks, {"unsettled": unsettled, "unmatched_names": unmatched, "settled": len(picks),
                   "kickoff_known": n_kick, "close_before_kickoff": n_clamped,
                   "no_pregame_line": n_no_pregame}


# ── game-market settlement ───────────────────────────────────────────────────
_GAMES_CSV = []
def games_csv_rows():
    """nflverse games.csv rows, fetched once per run (props need kickoffs,
    games need scores). [] on failure so settlement still proceeds."""
    if not _GAMES_CSV:
        try:
            with urllib.request.urlopen(GAMES_URL, timeout=30) as resp:
                text = resp.read().decode("utf-8")
            _GAMES_CSV.append(list(csv.DictReader(io.StringIO(text))))
        except Exception as e:
            print(f"[settle] games.csv fetch failed ({e})")
            _GAMES_CSV.append([])
    return _GAMES_CSV[0]

def load_kickoffs():
    """{(season, week, team): kickoff ISO-UTC} from games.csv. gameday/gametime
    are US Eastern wall-clock (London/Munich games too), so DST is resolved per
    date. One game per team per week; unknown -> caller falls back."""
    import datetime
    from zoneinfo import ZoneInfo
    et, out = ZoneInfo("America/New_York"), {}
    for row in games_csv_rows():
        try:
            t = datetime.datetime.strptime(f"{row['gameday']} {row['gametime']}", "%Y-%m-%d %H:%M")
        except (KeyError, TypeError, ValueError):
            continue
        ko = t.replace(tzinfo=et).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        for team in (row.get("home_team"), row.get("away_team")):
            out[(str(row.get("season")), str(row.get("week")), team_nfl(team))] = ko
    return out

def pregame_prop_close(r, kick):
    """(closing sample, cur-or-None) as of kickoff. The hourly snapshot keeps
    sampling a week's key until the feed rolls, so the last sample is often a
    Monday-morning read of a Sunday game: a stale lone quote or a live line.
    The close is the last sample stamped BEFORE kickoff; cur (the only snapshot
    carrying per-book quotes) counts only if it was also taken pre-kickoff.
    kick=None -> the old behaviour (last sample, cur). A record with no
    pre-kickoff sample at all returns (None, None): every line it holds is
    in-game or next week's, and it doesn't settle."""
    samples, cur = r.get("samples") or [r.get("cur")], r.get("cur")
    if not kick:
        return samples[-1] or cur or {}, cur
    pre = [x for x in samples if x and (x.get("ts") or "") < kick]
    cur_ok = cur if cur and (cur.get("ts") or "") < kick else None
    return (pre[-1] if pre else None), cur_ok

def load_games_csv(seasons):
    """nflverse games.csv → {(season,week,away,home): {home_score,away_score}}."""
    rows = games_csv_rows()
    if not rows:
        print("[settle] no games.csv; skipping game settlement")
        return {}
    out = {}
    for row in rows:
        try:
            s = int(row.get("season") or 0)
            if s not in seasons: continue
            hs, as_ = row.get("home_score"), row.get("away_score")
            if hs in (None, "", "NA") or as_ in (None, "", "NA"): continue
            key = (str(s), str(row.get("week")), team_nfl(row.get("away_team")), team_nfl(row.get("home_team")))
            out[key] = {"home_score": float(hs), "away_score": float(as_)}
        except Exception:
            continue
    return out

def load_espn_scores(needed):
    """Fetch final scores from ESPN's scoreboard for a set of (season, week,
    espn_seasontype). Returns {(season,week,away,home): {home_score,away_score}}
    keyed with nflverse team codes (team_nfl), so it merges with load_games_csv.
    Only COMPLETED games are returned; any fetch/parse failure is skipped so
    settlement degrades to nflverse-only rather than breaking."""
    out = {}
    for season, week, st in sorted(needed):
        url = f"{ESPN_SB_URL}?dates={season}&seasontype={st}&week={week}"
        try:
            # Default urllib UA on purpose — ESPN's edge 403s some custom/browser
            # UA strings, and the plain Python-urllib UA passes reliably.
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[settle] ESPN scoreboard {season} wk{week} st{st} fetch failed ({e}); skipping")
            continue
        for ev in data.get("events", []):
            try:
                comp = (ev.get("competitions") or [{}])[0]
                status = (comp.get("status") or ev.get("status") or {}).get("type", {})
                if not (status.get("completed") or status.get("state") == "post"):
                    continue                                    # not final — don't settle a live/partial score
                home = away = None
                for c in comp.get("competitors", []):
                    abbr = team_nfl((c.get("team") or {}).get("abbreviation"))
                    sc = c.get("score")
                    sc = float(sc) if sc not in (None, "") else None
                    if c.get("homeAway") == "home": home = (abbr, sc)
                    elif c.get("homeAway") == "away": away = (abbr, sc)
                if not home or not away or home[1] is None or away[1] is None:
                    continue
                out[(str(season), str(week), away[0], home[0])] = {"home_score": home[1], "away_score": away[1]}
            except Exception:
                continue
    return out

NEWS_PTS, NEWS_BASE_D = 4, 10   # mirrors snapshot-game-history.mjs lineNews()

def _parse_ts(t):
    import datetime as _dt
    try: return _dt.datetime.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
    except Exception: return None

def line_news_moves(games):
    """{(away, home, commence): {"sp": d, "to": d}}: how far each game's closing
    spread / total sat from its lookahead (the last sample NEWS_BASE_D+ days
    before kickoff). Samples are pooled across week tags (one matchup can be
    banked under several). A move of NEWS_PTS+ is the "Big line move" hold in
    the app; banking the move on every game lets the scoreboard check that the
    hold is keeping the model out of games it can't read."""
    pool = {}
    for g in games.values():
        if g.get("commence"):
            pool.setdefault((g.get("away"), g.get("home"), g["commence"]), []).extend(g.get("samples") or [])
    out = {}
    for (a, h, c), S in pool.items():
        kick = _parse_ts(c)
        if kick is None: continue
        S = sorted((x for x in S if x and _parse_ts(x.get("ts")) is not None and _parse_ts(x["ts"]) < kick),
                   key=lambda x: _parse_ts(x["ts"]))
        mv = {}
        for mk, f in (("sp", "spread"), ("to", "total")):
            base = [x for x in S if x.get(f) is not None and _parse_ts(x["ts"]) <= kick - NEWS_BASE_D * 86400]
            cur = [x for x in S if x.get(f) is not None]
            mv[mk] = round(cur[-1][f] - base[-1][f], 2) if base and cur else None
        out[(a, h, c)] = mv
    return out

# ── Polymarket's price at kickoff (scripts/pm_archive.py -> data/pm_closes.json) ───────────────
# The deepest market on NFL game lines (about $400k resting within 1c of the touch before Sunday kickoffs), from the
# Pendulum Flow orderbook archive. For each settled game call: Polymarket's chance for the model's side at the closing
# number, so the season can say whether our leans land where the sharpest money finished. Spread and total read the
# Polymarket ladder at the market's closing number, interpolated between neighbouring lines.
PM_NICK = {"Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR", "Bears": "CHI", "Bengals": "CIN",
           "Browns": "CLE", "Cowboys": "DAL", "Broncos": "DEN", "Lions": "DET", "Packers": "GB", "Texans": "HOU", "Colts": "IND",
           "Jaguars": "JAX", "Chiefs": "KC", "Chargers": "LAC", "Rams": "LAR", "Raiders": "LV", "Dolphins": "MIA", "Vikings": "MIN",
           "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ", "Eagles": "PHI", "Steelers": "PIT", "Seahawks": "SEA",
           "49ers": "SF", "Buccaneers": "TB", "Titans": "TEN", "Commanders": "WAS"}


def load_pm_closes():
    """(away, home) in Vault codes -> [(kickoff, close)] for NFL games in data/pm_closes.json."""
    try:
        G = json.load(open(os.path.join(DATA, "pm_closes.json"))).get("games", {})
    except Exception:
        return {}
    out = defaultdict(list)
    for g in G.values():
        if g.get("sport") != "nfl" or not g.get("ml"):
            continue
        teams = [PM_NICK.get(o) for o in g["ml"]["outcomes"]]
        if None in teams:
            continue
        for a, h in (teams, teams[::-1]):
            out[(a, h)].append((g["kickoff"], g))
    return out


def _interp(points, x):
    """Linear interpolation on (x, y) points; None outside the ladder."""
    pts = sorted(points)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return next((y for xx, y in pts if xx == x), None)


def pm_close_for(pmc, away, home, commence):
    """Polymarket at kickoff for one game: home win chance, home-cover chance at a home line, over chance at a total."""
    try:
        ko = _parse_ts(commence).timestamp() if commence else None
    except Exception:
        ko = None
    c = [g for k, g in pmc.get((away, home), []) if ko is None or abs(k - ko) < 6 * 3600]
    if not c:
        return None
    g = c[0]
    names = [PM_NICK.get(o) for o in g["ml"]["outcomes"]]
    p_home = g["ml"]["p"] if names[0] == home else 1 - g["ml"]["p"]
    cover = [(r["line"], r["p"]) if PM_NICK.get(r["outcomes"][0]) == home else (-r["line"], 1 - r["p"])
             for r in g.get("spreads", []) if r.get("line") is not None and PM_NICK.get(r["outcomes"][0]) in (home, away)]
    over = [(r["line"], r["p"] if r["outcomes"][0] == "Over" else 1 - r["p"]) for r in g.get("totals", []) if r.get("line") is not None]
    return {"p_home": p_home, "cover": lambda line: _interp(cover, line), "over": lambda line: _interp(over, line)}


def settle_games(season_filter=None):
    try:
        blob = json.load(open(os.path.join(DATA, "game_line_history.json")))
    except Exception:
        return [], {"reason": "no game_line_history.json"}
    games = blob.get("games", {})
    reg = [g for g in games.values() if (g.get("seasonType") or "").lower() not in ("pre",)]
    if not reg:
        return [], {"settled": 0, "note": "no non-preseason games banked yet"}
    seasons = {int(g["season"]) for g in reg if str(g.get("season")).isdigit()}
    scores = load_games_csv(seasons)
    # Fill any banked game nflverse hasn't scored yet from ESPN (faster feed).
    # Only fetch the specific weeks that are still missing, so a fully-settled
    # backlog costs zero ESPN calls.
    need = set()
    for g in reg:
        k = (str(g.get("season")), str(g.get("week")), team_nfl(g.get("away")), team_nfl(g.get("home")))
        if k not in scores:
            st = ESPN_STYPE.get((g.get("seasonType") or "regular").lower(), 2)
            need.add((str(g.get("season")), str(g.get("week")), st))
    if need:
        espn = load_espn_scores(need)
        n_new = sum(1 for k in espn if k not in scores)
        for k, v in espn.items():
            scores.setdefault(k, v)              # nflverse wins; ESPN only fills gaps
        if n_new: print(f"[settle] ESPN filled {n_new} game(s) nflverse hasn't scored yet")
    if not scores:
        return [], {"settled": 0, "note": "no scores available"}

    picks, unsettled = [], 0
    news = line_news_moves(games)
    pmc = load_pm_closes()
    for g in reg:
        season = str(g.get("season"))
        if season_filter and season != str(season_filter): continue
        away, home, week = g.get("away"), g.get("home"), str(g.get("week"))
        # Join on nflverse codes (LAR→LA); keep Vault codes for display below.
        sc = scores.get((season, week, team_nfl(away), team_nfl(home)))
        if not sc:
            unsettled += 1; continue
        n_before = len(picks)
        sp_side = None                                       # this game's spread lean (ML must agree)
        hs, as_ = sc["home_score"], sc["away_score"]
        margin = hs - as_                                    # home margin (actual)
        total_actual = hs + as_
        opn = g.get("open") or {}
        samples = g.get("samples") or []
        cls = (samples[-1] if samples else None) or g.get("cur") or {}   # closing MARKET line
        # Closing MODEL line: the most recent bank that actually carries a vault
        # line — early samples can predate model banking (vault:null), so don't
        # just read samples[-1].vault (it may be a stale null even when cur has one).
        vl = None
        for s in list(reversed(samples)) + [g.get("cur"), opn]:
            if s and s.get("vault"): vl = s["vault"]; break
        moff = bool(vl.get("off")) if vl else False          # model was on offseason (prior-season) ratings
        base = {"kind": "game", "season": season, "week": g.get("week"), "away": away, "home": home,
                "home_score": hs, "away_score": as_, "model_offseason": moff}   # scores let the UI settle too
        nm = news.get((away, home, g.get("commence"))) or {}
        base.update({"news_sp": nm.get("sp"), "news_to": nm.get("to"),
                     "news": any(v is not None and abs(v) >= NEWS_PTS for v in nm.values()) if nm else None})
        pm = pm_close_for(pmc, away, home, g.get("commence"))

        # SPREAD — the Vault model picks a side vs the closing market spread;
        # does that side cover? (forward ATS test of the game model). proj_err is
        # the raw margin miss (model home margin − actual), the regression signal.
        if vl and vl.get("spread") is not None and cls.get("spread") is not None and opn.get("spread") is not None:
            mkt_c, mkt_o = cls["spread"], opn["spread"]
            side = "home" if vl["spread"] < mkt_c else "away"   # model spread lower ⇒ model likes home more than market
            sp_side = side
            home_cov = margin + mkt_c > 0                       # home covers the closing spread
            push = abs(margin + mkt_c) < 1e-9
            won = None if push else (1.0 if (side == "home") == home_cov else 0.0)
            clv_line = (mkt_o - mkt_c) if side == "home" else (mkt_c - mkt_o)  # signed to model side
            # Consensus prices at the number, both sides [home, away] (banked from
            # 2026-09-28; older samples have none -> the scoreboard reads 50/50).
            picks.append({**base, "market": "spread", "side": side, "line_open": mkt_o, "line_close": mkt_c,
                          "px_open": [opn.get("spHomePx"), opn.get("spAwayPx")], "px_close": [cls.get("spHomePx"), cls.get("spAwayPx")],
                          "vault_line": vl["spread"], "actual": margin, "proj_err": (-vl["spread"]) - margin,
                          "push": push, "won_close": won,
                          "clv_line": clv_line, "beat_close": (1.0 if clv_line > 1e-9 else 0.0),
                          "pm_close": (lambda c: None if c is None else round(c if side == "home" else 1 - c, 4))(pm["cover"](mkt_c) if pm else None)})

        # TOTAL — model over/under vs the closing market total (proj_err = model total − actual)
        if vl and vl.get("total") is not None and cls.get("total") is not None and opn.get("total") is not None:
            mkt_c, mkt_o = cls["total"], opn["total"]
            side = "over" if vl["total"] > mkt_c else "under"
            push = abs(total_actual - mkt_c) < 1e-9
            won = None if push else (1.0 if (side == "over") == (total_actual > mkt_c) else 0.0)
            clv_line = (mkt_c - mkt_o) if side == "over" else (mkt_o - mkt_c)
            picks.append({**base, "market": "total", "side": side, "line_open": mkt_o, "line_close": mkt_c,
                          "px_open": [opn.get("toOverPx"), opn.get("toUnderPx")], "px_close": [cls.get("toOverPx"), cls.get("toUnderPx")],
                          "vault_line": vl["total"], "actual": total_actual, "proj_err": vl["total"] - total_actual,
                          "push": push, "won_close": won,
                          "clv_line": clv_line, "beat_close": (1.0 if clv_line > 1e-9 else 0.0),
                          "pm_close": (lambda c: None if c is None else round(c if side == "over" else 1 - c, 4))(pm["over"](mkt_c) if pm else None)})

        # MONEYLINE / WIN-PROB — the model's home win% vs the market, plus its raw
        # calibration against the actual result (the win-prob learning signal).
        # p_home / y_home feed a full-range reliability curve + Brier in the board.
        wh, ml_c, ml_o = (vl.get("winHome") if vl else None), cls.get("mlHome"), opn.get("mlHome")
        ml_ac, ml_ao = cls.get("mlAway"), opn.get("mlAway")     # away price (banked since the two-sided fix)
        if wh is not None and ml_c is not None:
            # Vig-free market home win when both sides are banked (devig), else the
            # single-sided implied (older samples). Right baseline for the lean/CLV.
            p_mkt_home = devig(ml_c, ml_ac) if ml_ac is not None else am_prob(ml_c)
            side = "home" if wh > (p_mkt_home if p_mkt_home is not None else 0.5) else "away"
            # One model, one opinion per game. The ML lean compares the model's
            # win% to the moneyline, the spread lean compares its margin to the
            # spread, and those two market numbers can disagree with each other,
            # so the model could "lean" SEA on the spread and WAS on the ML (Wk3).
            # When they point opposite ways there is no ML lean: the row stays for
            # win-prob calibration (p_home / y_home) but is not graded as a bet.
            # Wks 1-3: the 10 conflicting ML leans went 3-7.
            conflict = sp_side is not None and side != sp_side
            home_won = margin > 0
            push = abs(margin) < 1e-9                           # tie (rare) → no grade
            won = None if push else (1.0 if (side == "home") == home_won else 0.0)
            clv_prob = None
            if ml_o is not None:
                # Use the SAME method (devig vs single-sided) on both ends so a
                # transition sample (open pre-mlAway, close post) can't invent CLV.
                two = ml_ac is not None and ml_ao is not None
                pc = devig(ml_c, ml_ac) if two else am_prob(ml_c)
                po = devig(ml_o, ml_ao) if two else am_prob(ml_o)
                if pc is not None and po is not None:
                    p_close_side = pc if side == "home" else 1 - pc
                    p_open_side = po if side == "home" else 1 - po
                    clv_prob = p_close_side - p_open_side       # market drift toward the model's side
            # ml_open/ml_close stay the HOME price (legacy readers key on it);
            # price_open/price_close are the price of the side Vault TOOK, so an
            # away pick isn't paid at the home favourite's number.
            px_c = ml_c if side == "home" else ml_ac
            px_o = ml_o if side == "home" else ml_ao
            if conflict:
                picks.append({**base, "market": "ml", "side": None, "no_lean": "spread_disagrees",
                              "ml_open": ml_o, "ml_close": ml_c, "price_open": None, "price_close": None,
                              "vault_winhome": wh, "p_home": wh, "y_home": (None if push else (1.0 if home_won else 0.0)),
                              "p_model": None, "p_market": None, "actual": margin, "push": push,
                              "won_close": None, "clv_prob": None, "beat_close": None})
                continue
            picks.append({**base, "market": "ml", "side": side, "ml_open": ml_o, "ml_close": ml_c,
                          "price_open": px_o, "price_close": px_c,
                          "vault_winhome": wh, "p_home": wh, "y_home": (None if push else (1.0 if home_won else 0.0)),
                          "p_model": (wh if side == "home" else 1.0 - wh),
                          "p_market": (p_mkt_home if side == "home" else (1 - p_mkt_home if p_mkt_home is not None else None)),
                          "actual": margin, "push": push, "won_close": won,
                          "clv_prob": clv_prob, "beat_close": (1.0 if (clv_prob or 0) > 1e-9 else 0.0),
                          "pm_close": None if not pm else round(pm["p_home"] if side == "home" else 1 - pm["p_home"], 4)})

        # Score-only row for a played game Vault never banked a model line on
        # (preseason gating, or a team the ratings map missed). Vault grades no
        # bet here, but the UI still needs the final score to settle a pick the
        # USER tracked on this game (My Picks → "Game bets"). Tagged "final" so
        # the scoreboard aggregation below skips it; the frontend reads only the
        # scores. Without this, a user pick on a no-lean game sits pending forever.
        if len(picks) == n_before:
            picks.append({**base, "market": "final"})

    return picks, {"settled": len(picks), "unsettled": unsettled}


# ── aggregation → scoreboard (UI + model feedback) ──────────────────────────
def mean(xs): xs = [x for x in xs if x is not None]; return sum(xs) / len(xs) if xs else None

def reliability(pairs, edges=(0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 1.01)):
    """(p_model_side, y) → in-season calibration curve, the recalibration input."""
    out, lo = [], 0.5
    for hi in edges:
        b = [(p, y) for p, y in pairs if lo <= p < hi]
        if b:
            out.append([round(lo, 3), round(hi, 3), len(b),
                        round(mean([p for p, _ in b]), 4), round(mean([y for _, y in b]), 4)])
        lo = hi
    return out

def fit_temp(pairs):
    """Grid-search the residual temperature t on the SERVED model probs vs
    in-season outcomes: p' = sig(t·logit(p)). t<1 ⇒ model still overconfident
    this season (needs more shrink); t>1 ⇒ under-confident. The builder composes
    a sample-shrunk version of this onto the shipped calib table (docs)."""
    pairs = [(p, y) for p, y in pairs if p is not None and y is not None]
    if len(pairs) < 40: return None, len(pairs)
    best_t, best_ll = 1.0, 1e18
    for i in range(6, 21):                      # t in [0.6 .. 2.0]
        t = i / 10.0
        ll = mean([logloss1(y, sig(t * logit(p))) for p, y in pairs])
        if ll < best_ll: best_t, best_ll = t, ll
    return best_t, len(pairs)


def fit_blend_w(triples):
    """Grid-search the model↔market blend weight (weight on the model) that
    minimizes blended log-loss vs outcomes. This is the MEASURED weight; the
    builder shrinks it by n/(n+K) so early weeks barely move (docs)."""
    triples = [(pm, pk, y) for pm, pk, y in triples if pm is not None and pk is not None and y is not None]
    if len(triples) < 30: return None, len(triples)
    best_w, best_ll = 1.0, 1e18
    for i in range(21):
        w = i / 20.0
        ll = mean([logloss1(y, sig(w * logit(pm) + (1 - w) * logit(pk))) for pm, pk, y in triples])
        if ll < best_ll: best_w, best_ll = w, ll
    return best_w, len(triples)

from statistics import NormalDist  # noqa: E402
_N = NormalDist()
def _ncdf(z): return _N.cdf(z)
def _nppf(p): return _N.inv_cdf(clamp(p))

def fit_sd_k(pairs):
    """Grid-search the sd_margin scale k that best calibrates the win-prob model
    on in-season outcomes. winHome = Φ(margin/sd), so Φ⁻¹(p) is the standardized
    margin and the recalibrated prob is Φ(Φ⁻¹(p)/k) — k>1 ⇒ model overconfident
    (needs a wider sd), k<1 ⇒ underconfident. Fit without knowing the banked sd.
    The builder applies this shrunk by n/(n+K)."""
    pairs = [(p, y) for p, y in pairs if p is not None and y is not None]
    if len(pairs) < 30: return None, len(pairs)
    best_k, best_ll = 1.0, 1e18
    for i in range(14, 31):                     # k in [0.70 .. 1.50]
        k = i / 20.0
        ll = mean([logloss1(y, _ncdf(_nppf(p) / k)) for p, y in pairs])
        if ll < best_ll: best_k, best_ll = k, ll
    return best_k, len(pairs)


def build_scoreboard(prop_picks, game_picks):
    board = {"markets": {}, "grades": {}, "games": {}}

    by_mk = defaultdict(list)
    for p in prop_picks: by_mk[p["market"]].append(p)
    for mk, ps in by_mk.items():
        graded = [p for p in ps if p["won_close"] is not None]      # excludes pushes / no-side
        rel_pairs = [(p["p_model"], p["won_close"]) for p in graded if p["p_model"] is not None]
        triples = [(p["p_model"], p["market"] and p["p_market"], p["won_close"]) for p in graded]
        w_meas, n_blend = fit_blend_w([(p["p_model"], p["p_market"], p["won_close"]) for p in graded])
        ml = [logloss1(p["won_close"], p["p_model"]) for p in graded if p["p_model"] is not None]
        kl = [logloss1(p["won_close"], p["p_market"]) for p in graded if p["p_market"] is not None]
        temp, n_temp = fit_temp(rel_pairs)
        # Projection-mean feedback: does the model's NUMBER (not just its prob)
        # run systematically high or low vs the actual? bias = mean(proj−actual),
        # positive ⇒ model over-projects. mean_proj / mean_actual give the builder
        # a ratio to correct with (proj_adj); every settled row with a projection
        # counts (pushes included — a push still has a real actual). See docs #… .
        projd = [p for p in ps if p.get("proj") is not None and p.get("actual") is not None]
        perr = [(p["proj"] - p["actual"]) for p in projd]
        board["markets"][mk] = {
            "n": len(ps), "n_graded": len(graded),
            "winrate_close": mean([p["won_close"] for p in graded]),
            "clv_beat_rate": mean([p["beat_close"] for p in ps]),
            "mean_clv_prob": mean([p["clv_prob"] for p in ps]),
            "mean_clv_line": mean([p["clv_line"] for p in ps]),
            "model_logloss": mean(ml), "market_logloss": mean(kl),
            "reliability": reliability(rel_pairs),
            "proj_bias": mean(perr), "proj_mae": mean([abs(e) for e in perr]) if perr else None,
            "mean_proj": mean([p["proj"] for p in projd]), "mean_actual": mean([p["actual"] for p in projd]),
            "n_proj": len(perr),
            "inseason_temp": {"t": temp, "n": n_temp, "k_shrink": K_BLEND,
                              "note": "builder composes t onto calib, shrunk by n/(n+K)"},
            "blend": {"w_measured": w_meas, "n": n_blend, "k_shrink": K_BLEND,
                      "note": "measured model<->market weight; build publishes blend_w, serving blends P(over) toward the vig-free market (docs #3)"},
        }

    by_grade = defaultdict(list)
    for p in prop_picks:
        if p["grade"] and p["won_close"] is not None: by_grade[p["grade"]].append(p)
    for gr, ps in by_grade.items():
        board["grades"][gr] = {"n": len(ps), "winrate_close": mean([p["won_close"] for p in ps]),
                               "clv_beat_rate": mean([p["beat_close"] for p in ps]),
                               "mean_clv_prob": mean([p["clv_prob"] for p in ps])}

    by_gm = defaultdict(list)
    for p in game_picks:
        if p["market"] == "final": continue    # score-only row (no Vault bet) — UI settlement only
        by_gm[p["market"]].append(p)
    for mk, ps in by_gm.items():
        graded = [p for p in ps if p["won_close"] is not None]
        reg = [p for p in ps if not p.get("model_offseason")]   # in-season-rating subset (the clean learning slice)
        entry = {"n": len(ps), "n_graded": len(graded), "n_offseason": len(ps) - len(reg),
                 "ats_or_ou_pct": mean([p["won_close"] for p in graded]),
                 "clv_beat_rate": mean([p["beat_close"] for p in ps]),
                 "mean_clv_line": mean([p.get("clv_line") for p in ps]),
                 "mean_clv_prob": mean([p.get("clv_prob") for p in ps])}
        # Polymarket at kickoff: its average chance for our side, and how often it had our side above 50%
        pmv = [p["pm_close"] for p in ps if p.get("pm_close") is not None]
        entry["pm_close_mean"] = mean(pmv) if pmv else None
        entry["pm_agree_rate"] = mean([1.0 if v > 0.5 else 0.0 for v in pmv]) if pmv else None
        entry["n_pm"] = len(pmv)
        if mk in ("spread", "total"):
            # Projection error is the direct regression signal: MAE = how far off,
            # bias = systematic over/under (positive ⇒ model runs high vs actual).
            errs = [p["proj_err"] for p in ps if p.get("proj_err") is not None]
            reg_errs = [p["proj_err"] for p in reg if p.get("proj_err") is not None]
            entry["proj_mae"] = mean([abs(e) for e in errs]) if errs else None
            entry["proj_bias"] = mean(errs) if errs else None
            entry["proj_mae_inseason"] = mean([abs(e) for e in reg_errs]) if reg_errs else None
            entry["proj_bias_inseason"] = mean(reg_errs) if reg_errs else None
            entry["n_proj"] = len(errs)
            entry["n_proj_inseason"] = len(reg_errs)   # sample the builder shrinks the bias correction against
        if mk == "ml":
            # Win-prob calibration: home win prob vs home-won (0/1), full range so
            # underdogs count. Brier + log-loss + a 10-bin reliability curve are
            # the recalibration inputs for the win% side of the game model.
            cal = [(p["p_home"], p["y_home"]) for p in ps if p.get("p_home") is not None and p.get("y_home") is not None]
            entry["brier"] = mean([(pp - y) ** 2 for pp, y in cal]) if cal else None
            entry["logloss"] = mean([logloss1(y, pp) for pp, y in cal]) if cal else None
            rel, lo = [], 0.0
            for hi in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01):
                b = [(pp, y) for pp, y in cal if lo <= pp < hi]
                if b:
                    rel.append([round(lo, 2), round(hi, 2), len(b),
                                round(mean([pp for pp, _ in b]), 4), round(mean([y for _, y in b]), 4)])
                lo = hi
            entry["reliability"] = rel
            entry["n_cal"] = len(cal)
            entry["lean_winrate"] = mean([p["won_close"] for p in graded]) if graded else None
            # In-season-only sd_margin recalibration factor (the loop-closer input).
            cal_in = [(p["p_home"], p["y_home"]) for p in reg if p.get("p_home") is not None and p.get("y_home") is not None]
            sd_k, n_sdk = fit_sd_k(cal_in)
            entry["winprob_sd_k"] = sd_k
            entry["n_cal_inseason"] = n_sdk
        board["games"][mk] = entry
    return board


# ── Vault's Plays: grade the locked weekly card ──────────────────────────────
# data/best_bets_card.json is the append-only card build_best_bets.mjs locks
# (every play frozen at the line + price it posted with). Graded HERE, at that
# posted line and price, because that is the bet a user following the card made.
# The closing line/price comes from the matching ledger row, for two extra
# reads: units if you had waited and bet the close, and CLV (did the market move
# toward the play after it posted; on an unmoved number, did the price we took
# beat the no-vig closing price, fair_close_over()). A close line more than max(15%, 1) off the
# posted one is treated as a junk snapshot (alt lines leak in) and gets no CLV.
#
# data/best_bets_shadow.json is every play that reached the live Best Bets top-N,
# card or not. It is graded the same way and drives data/best_bets_rules.json:
# which play types (market x side x position group) may go on the card. A type
# earns a spot on its own recent record and loses it the same way, so the card
# follows whatever is actually winning instead of a hand-picked market.
def _am_pay(a):
    return 100 / 110 if a is None else (a / 100 if a > 0 else 100 / abs(a))

def _load_data(name):
    try:
        return json.load(open(os.path.join(DATA, name)))
    except Exception:
        return None

def _power_devig(o, u):
    """Two-way American prices -> vig-free P(over) by the power method (the
    same de-vig as the app's fair line; it takes more vig off the longshot than
    the proportional devig() does). None unless a sane two-way pair."""
    po, pu = am_prob(o), am_prob(u)
    if po is None or pu is None or not (1.0 < po + pu <= 1.15): return devig(o, u)
    lo, hi = 1.0, 3.0
    for _ in range(50):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1: lo = k
        else: hi = k
    return po ** ((lo + hi) / 2)

DFS_BOOKS = {"prizepicks", "underdog fantasy", "underdog", "sleeper"}   # = build_best_bets.mjs

def fair_close_over(led):
    """(P(over) at the closing line with the vig removed, source). Per-book
    power de-vig then the median (the app's fair line) over REAL books when the
    close banked per-book quotes; else the consensus closing pair. Pick'em apps
    price every line the same (-112/-112), which de-vigs to 50% whatever the
    market thinks, so they are left out, and so is a symmetric consensus pair
    (the tell of an app-sourced close). (None, None) when no real price."""
    ps = sorted(p for p in (_power_devig(o, u) for b, (o, u) in ((led or {}).get("books_close") or {}).items()
                            if str(b).lower() not in DFS_BOOKS) if p is not None)
    if ps:
        n = len(ps)
        return (ps[n // 2] if n % 2 else (ps[n // 2 - 1] + ps[n // 2]) / 2), "books"
    o, u = (led or {}).get("close_over"), (led or {}).get("close_under")
    p = _power_devig(o, u) if o is not None and o != u else None
    return (p, "consensus") if p is not None else (None, None)

def _grade_plays(picks, prop_picks):
    by_key = {(str(p.get("season")), p.get("week"), str(p.get("pid")), p.get("market")): p for p in prop_picks}
    # A team whose props have settled this week has played; a card player on it
    # with no box score sat out, and books void the bet (result "V", 0 units).
    # Caveat: a player who dressed but recorded no stat also has no row; for the
    # yardage/catch markets the card plays that is rare (Wk1-3 voids were all
    # confirmed inactive), but check a V against the injury report if in doubt.
    team_done = {(str(p.get("season")), p.get("week"), p.get("team")) for p in prop_picks if p.get("actual") is not None}
    actuals_cache, out = {}, []
    for c in picks:
        season, week, market, side, line = str(c.get("season")), c.get("week"), c.get("market"), c.get("side"), c.get("line")
        if season not in actuals_cache:
            actuals_cache[season] = load_actuals(season)
        row = dict(c)
        actual = actual_for(actuals_cache[season], c.get("name"), week, market) if market in COL else None
        led = by_key.get((season, week, str(c.get("pid")), market))
        if actual is None and led is not None:
            actual = led.get("actual")          # same box score, joined by the ledger's name matching
        if market == "anytime_td" and line is not None and line <= 0:
            line = 0.5                          # "anytime" = over 0.5 TDs; posted as line 0
        res = units = None
        if actual is None and (season, week, c.get("team")) in team_done:
            res, units = "V", 0.0
        elif actual is not None and line is not None and side in ("over", "under"):
            if abs(actual - line) < 1e-9:
                res, units = "P", 0.0
            else:
                won = actual > line if side == "over" else actual < line
                res = "W" if won else "L"
                units = _am_pay(c.get("price")) if won else -1.0
        row.update({"actual": actual, "result": res, "units": None if units is None else round(units, 3)})
        # closing line / price from the ledger (same prop, same week)
        lc = led.get("line_close") if led else None
        cp = (led.get("close_over") if side == "over" else led.get("close_under")) if led else None
        clv_line = beat = units_close = clv_prob = fair_side = None
        fo, fsrc = fair_close_over(led)
        if lc is not None and line is not None and abs(lc - line) <= max(0.15 * abs(line), 1.0):
            clv_line = (lc - line) if side == "over" else (line - lc)
            if abs(clv_line) > 1e-9:
                beat = clv_line > 0
            elif fo is not None and c.get("price") is not None:
                # Same number: grade the price we took against the market's
                # NO-VIG closing price, not the same book's close. A pick'em app
                # or a book that never moves its -112 used to read "no change"
                # (6 of Week 3's 9 card plays had no CLV at all); against the fair
                # close every play gets a verdict, and a flat -112 on a 50/50
                # close is correctly a loss of the vig.
                fair_side = fo if side == "over" else 1 - fo
                clv_prob = fair_side - am_prob(c["price"])
                beat = clv_prob > 0
            if actual is not None and abs(actual - lc) > 1e-9:
                wc = actual > lc if side == "over" else actual < lc
                units_close = _am_pay(cp) if wc else -1.0
            elif actual is not None:
                units_close = 0.0
        row.update({"line_close": lc, "price_close": cp, "clv_line": clv_line, "beat_close": beat,
                    "fair_close": None if fair_side is None else round(fair_side, 4), "fair_src": fsrc if fair_side is not None else None,
                    "clv_prob": None if clv_prob is None else round(clv_prob, 4),
                    "units_close": None if units_close is None else round(units_close, 3)})
        out.append(row)
    return out

def _summ(rows):
    dec = [r for r in rows if r["result"] in ("W", "L")]
    W = sum(1 for r in dec if r["result"] == "W")
    cl = [r for r in rows if r["units_close"] is not None]
    bc = [r for r in rows if r["beat_close"] is not None]
    return {"W": W, "L": len(dec) - W, "P": sum(1 for r in rows if r["result"] == "P"),
            "pending": sum(1 for r in rows if r["result"] is None), "void": sum(1 for r in rows if r["result"] == "V"), "n": len(rows),
            "units": round(sum(r["units"] for r in rows if r["units"] is not None), 2),
            "units_close": round(sum(r["units_close"] for r in cl), 2), "n_close": len(cl),
            "beat_close": sum(1 for r in bc if r["beat_close"]), "n_clv": len(bc),
            # mean edge vs the no-vig close on same-number plays (EV proxy)
            "clv_ev": round(sum(r["clv_prob"] for r in ev) / len(ev), 4) if (ev := [r for r in rows if r.get("clv_prob") is not None]) else None, "n_ev": len(ev)}

# Card eligibility. Measured on Weeks 1-3 of the live top-N (56 valid plays):
# WR/TE rec-yds unders 28-11 +14.2u (every week positive); RB rec-yds unders
# 2-3; every other type under 10 plays. A type needs RULE_ON_N settled plays in
# the last RULE_WEEKS weeks at ROI >= RULE_ON_ROI to switch ON, and switches OFF
# once it is losing (units < 0) over RULE_OFF_N+ plays in that window. The gap
# between the two is deliberate: one bad week should not flip a proven type off,
# and a 3-0 streak should not flip an unproven one on.
RULE_WEEKS, RULE_ON_N, RULE_ON_ROI, RULE_OFF_N = 4, 15, 0.05, 10
RULE_DEFAULT_ON = {"rec_yd|under|WR/TE"}   # the seed, used until the first rules file lands

def _bucket(r):
    pos = r.get("pos")
    return f'{r.get("market")}|{r.get("side")}|{"RB" if pos == "RB" else "QB" if pos == "QB" else "WR/TE"}'

def _card_rules(shadow_rows, prev):
    prev_on = {k for k, v in ((prev or {}).get("buckets") or {}).items() if v.get("on")} if prev else set(RULE_DEFAULT_ON)
    settled = [r for r in shadow_rows if r["result"] in ("W", "L") and r.get("book_real", True)]
    if not settled:
        return {"weeks": [], "buckets": {k: {"on": True, "why": "seed"} for k in sorted(prev_on)}}
    season = max(str(r["season"]) for r in settled)
    wks = sorted({r["week"] for r in settled if str(r["season"]) == season})[-RULE_WEEKS:]
    win = [r for r in settled if str(r["season"]) == season and r["week"] in wks]
    by = defaultdict(list)
    for r in win:
        by[_bucket(r)].append(r)
    out = {}
    for k in sorted(set(by) | prev_on):
        rs = by.get(k, [])
        n = len(rs); W = sum(1 for r in rs if r["result"] == "W"); u = sum(r["units"] for r in rs)
        roi = u / n if n else None
        was = k in prev_on
        if was:
            on = not (n >= RULE_OFF_N and u < 0)
            why = "losing over the window" if not on else "still winning" if n >= RULE_OFF_N else "not enough new plays to judge"
        else:
            on = n >= RULE_ON_N and roi is not None and roi >= RULE_ON_ROI
            why = "earned it" if on else f"needs {RULE_ON_N}+ plays at {int(RULE_ON_ROI * 100)}%+ return"
        out[k] = {"on": on, "was": was, "n": n, "W": W, "L": n - W, "units": round(u, 2),
                  "roi": None if roi is None else round(roi, 4), "why": why}
    return {"season": season, "weeks": wks, "buckets": out}

# ── Game play types: which game calls earn a spot on the game card ──────────
# Same rule as the props card (RULE_*), on every settled game call, bucketed by
# market x how far Vault's raw line sits from the closing market (spread/total
# in points; moneyline in win-% points). Bands match gmxPlayBand in index.html.
# Wks 1-3: totals 1.5-3 pts off 12-5 +5.9u (winning every week); ML 2.5-5 pts
# 6-0 but only 6 plays; every spread band and every "big" gap lost. Units:
# spreads/totals at -110, moneyline at the side's opening price.
GAME_BANDS = {"spread": (1.5, 3.0), "total": (1.5, 3.0), "ml": (2.5, 5.0)}

def game_band(g):
    if g.get("market") == "ml":
        if g.get("p_model") is None or g.get("p_market") is None: return None
        x = abs(g["p_model"] - g["p_market"]) * 100
    elif g.get("market") in ("spread", "total"):
        if g.get("vault_line") is None or g.get("line_close") is None: return None
        x = abs(g["vault_line"] - g["line_close"])
    else:
        return None
    lo, hi = GAME_BANDS[g["market"]]
    return "small" if x < lo else "mid" if x < hi else "big"

def game_rules(game_picks, prev):
    prev_on = {k for k, v in ((prev or {}).get("buckets") or {}).items() if v.get("on")} if prev else set()
    rows = []
    for g in game_picks:
        b = game_band(g)
        if b is None or g.get("won_close") is None or g.get("model_offseason"): continue
        px = g.get("price_open") if g["market"] == "ml" else None
        if g["market"] == "ml" and px is None: continue
        rows.append((str(g["season"]), g["week"], f'{g["market"]}|{b}', g["won_close"], _am_pay(px) if g["won_close"] == 1 else -1.0))
    if not rows:
        return None
    season = max(r[0] for r in rows)
    wks = sorted({int(r[1]) for r in rows if r[0] == season})[-RULE_WEEKS:]
    by = defaultdict(list)
    for r in rows:
        if r[0] == season and int(r[1]) in wks: by[r[2]].append(r)
    out = {}
    for k in sorted(set(by) | prev_on):
        rs = by.get(k, []); n = len(rs); W = sum(1 for r in rs if r[3] == 1); u = sum(r[4] for r in rs)
        roi = u / n if n else None; was = k in prev_on
        if was:
            on = not (n >= RULE_OFF_N and u < 0)
            why = "losing over the window" if not on else "still winning" if n >= RULE_OFF_N else "not enough new plays to judge"
        else:
            on = n >= RULE_ON_N and roi is not None and roi >= RULE_ON_ROI
            why = "earned it" if on else f"needs {RULE_ON_N}+ plays at {int(RULE_ON_ROI * 100)}%+ return"
        out[k] = {"on": on, "was": was, "n": n, "W": W, "L": n - W, "units": round(u, 2),
                  "roi": None if roi is None else round(roi, 4), "why": why}
    return {"season": season, "weeks": wks, "bands": {m: list(v) for m, v in GAME_BANDS.items()},
            "params": {"window_weeks": RULE_WEEKS, "on_min_plays": RULE_ON_N, "on_min_roi": RULE_ON_ROI, "off_min_plays": RULE_OFF_N},
            "buckets": out}

def settle_card(prop_picks):
    card = _load_data("best_bets_card.json")
    if not card:
        return None
    out = _grade_plays(card.get("picks") or [], prop_picks)
    seasons = {}
    for r in out:
        s = seasons.setdefault(r["season"], {"all": [], "weeks": defaultdict(list)})
        s["all"].append(r); s["weeks"][f'{r.get("stype") or "reg"}-{r["week"]}'].append(r)
    res = {"card_max": card.get("card_max"), "picks": out,
           "seasons": {k: {"summary": _summ(v["all"]), "weeks": {w: _summ(rs) for w, rs in sorted(v["weeks"].items())}}
                       for k, v in seasons.items()}}
    # Pick'em pairs (build_best_bets.mjs pickemPairs, plan Week 4): each leg is
    # graded like a card play at its APP line; the entry wins only if both legs
    # win, and a pushed or void leg voids it (apps differ on reduced payouts, so
    # no partial credit is counted). Units at the logged payout (3x -> +2 / -1).
    plog = _load_data("pickem_pairs_log.json")
    if plog and plog.get("pairs"):
        prs = []
        for x in plog["pairs"]:
            legs = [dict(l, season=x["season"], stype=x.get("stype"), week=x["week"], team=l.get("team"), price=None)
                    for l in x.get("legs") or []]
            g = _grade_plays(legs, prop_picks)
            rs = [l["result"] for l in g]
            res_ = (None if any(r is None for r in rs) else "V" if any(r in ("V", "P") for r in rs)
                    else "W" if all(r == "W" for r in rs) else "L")
            pay = (x.get("payout") or 3) - 1
            prs.append({**{k: v for k, v in x.items() if k != "legs"}, "legs": g, "result": res_,
                        "units": None if res_ is None else (pay if res_ == "W" else -1.0 if res_ == "L" else 0.0)})
        dec = [x for x in prs if x["result"] in ("W", "L")]
        res["pairs"] = {"picks": prs, "summary": {
            "W": sum(1 for x in dec if x["result"] == "W"), "L": sum(1 for x in dec if x["result"] == "L"),
            "void": sum(1 for x in prs if x["result"] == "V"), "pending": sum(1 for x in prs if x["result"] is None),
            "units": round(sum(x["units"] or 0 for x in prs), 2),
            "expected_joint": round(sum(x.get("joint") or 0 for x in dec) / len(dec), 4) if dec else None}}
    shadow = _load_data("best_bets_shadow.json")
    if shadow and shadow.get("picks"):
        rows = _grade_plays(shadow["picks"], prop_picks)
        rules = _card_rules(rows, _load_data("best_bets_rules.json"))
        rules["params"] = {"window_weeks": RULE_WEEKS, "on_min_plays": RULE_ON_N, "on_min_roi": RULE_ON_ROI, "off_min_plays": RULE_OFF_N}
        res["rules"] = rules
        # Every Best Bets play, graded at its posted line + price: the Track
        # Record artifact's "Best Bets" filter reads these (card plays ride in
        # "picks" above; a card play the top-N never showed is only there).
        res["shadow_picks"] = rows
    # Withheld-but-would-pass (build_best_bets.mjs logHeld): props held because a
    # teammate starter was out (a backup QB, mostly) whose line still passed every
    # Best Bets gate. Graded the same way to test whether the hold costs us plays.
    heldf = _load_data("best_bets_held.json")
    if heldf and heldf.get("picks"):
        rows = _grade_plays(heldf["picks"], prop_picks)
        res["held"] = {"picks": rows, "summary": _summ(rows)}
    return res

def tag_withheld(prop_picks):
    """Mark ledger rows for players Best Bets withheld that week (a teammate
    starter OUT; best_bets_held.json "withheld"), so the scoreboard can grade
    the model's lean on every line of a held player, not just would-be plays."""
    W = (_load_data("best_bets_held.json") or {}).get("withheld") or {}
    n = 0
    for p in prop_picks:
        st = "post" if str(p.get("seasonType") or "").lower().startswith("post") else "reg"
        why = (W.get(f'{p.get("season")}|{st}|{p.get("week")}') or {}).get(str(p.get("pid")))
        if why: p["withheld"] = why; n += 1
    return n


# ── market-anchored shadow (Week 4 retro, finding 2) ─────────────────────────
# Vault's raw probabilities are ~4x too confident against the market: fitting
# outcome ~ no-vig market + w * (Vault - market) on real lines puts w near 0.22
# pooled (pass TDs ~1.0, QB volume 0). The anchored probability
#     logit p = logit q_market + w_market * (logit p_vault - logit q_market)
# keeps the market as the baseline and lets Vault move it only as far as its
# measured skill. SHADOW: nothing on the board reads it. Each week's weights are
# fit only on EARLIER settled weeks of the same season (walk-forward), so every
# row is out of sample; the scoreboard compares these grades with the live ones
# before anything switches. Inputs are the opening line, the opening two-way
# price (power de-vig) and the point-in-time model; no clean opening price -> no
# anchored row. data/prop_anchor_weights.json carries the newest weights.
ANCHOR_K = 200          # pseudo-count pulling a thin market's weight to the pooled one
ANCHOR_MIN_TRAIN = 150  # fewer pooled training rows than this -> no anchored grade yet


def _fit_anchor_w(rows):
    """w in [0, 1] minimizing log-loss of sig(a + w*b) over rows (y, a, b); the
    loss is convex in w, so a clamped Newton step converges in a few passes."""
    if not rows: return None
    w = 0.3
    for _ in range(30):
        g = h = 0.0
        for y, a, b in rows:
            p = sig(a + w * b)
            g += (p - y) * b; h += p * (1 - p) * b * b
        if h <= 1e-12: break
        w2 = min(1.0, max(0.0, w - g / h))
        if abs(w2 - w) < 1e-7:
            w = w2; break
        w = w2
    return w


def _anchor_inputs(p):
    """(y_open, a, b, q) for one ledger row, or None. a = logit(market P(over)),
    b = logit(Vault P(over)) - a, both at the opening line."""
    lo, lc, act, pm, side = p.get("line_open"), p.get("line_close"), p.get("actual"), p.get("p_model"), p.get("side")
    q = _power_devig(p.get("open_over"), p.get("open_under"))
    if None in (lo, lc, act, pm, q) or side not in ("over", "under"): return None
    if abs(lo - lc) > max(0.15 * abs(lc), 1.0): return None          # junk opening snapshot
    pv = pm if side == "over" else 1 - pm
    a = logit(q)
    y = None if abs(act - lo) < 1e-9 else (1.0 if act > lo else 0.0)
    return y, a, logit(pv) - a, q


def _anchor_weights(train):
    """{'pooled': w, 'markets': {mk: {'w', 'w_fit', 'n'}}} from rows (mk, y, a, b)."""
    if len(train) < ANCHOR_MIN_TRAIN: return None
    pooled = _fit_anchor_w([(y, a, b) for _, y, a, b in train])
    by = defaultdict(list)
    for mk, y, a, b in train: by[mk].append((y, a, b))
    mks = {}
    for mk, rows in by.items():
        wf = _fit_anchor_w(rows)
        mks[mk] = {"w": round((len(rows) * wf + ANCHOR_K * pooled) / (len(rows) + ANCHOR_K), 4),
                   "w_fit": round(wf, 4), "n": len(rows)}
    return {"pooled": round(pooled, 4), "markets": mks}


def anchor_shadow(prop_picks):
    """Adds p_anchor_over / anchor_side / p_anchor / ev_anchor / grade_anchor /
    won_anchor / w_anchor to each row it can price; returns the newest season's
    weights fit on every settled week (for prop_anchor_weights.json)."""
    by_season = defaultdict(list)
    for p in prop_picks: by_season[str(p.get("season"))].append(p)
    latest = None
    for season in sorted(by_season):
        rows = by_season[season]
        inp = {id(p): _anchor_inputs(p) for p in rows}
        weeks = sorted({p["week"] for p in rows if p.get("week") is not None})
        for wk in weeks:
            train = [(p["market"], x[0], x[1], x[2]) for p in rows
                     if p.get("week") is not None and p["week"] < wk
                     for x in [inp[id(p)]] if x is not None and x[0] is not None]
            W = _anchor_weights(train)
            if not W: continue
            for p in rows:
                if p.get("week") != wk: continue
                x = inp[id(p)]
                if x is None: continue
                _, a, b, q = x
                w = (W["markets"].get(p["market"]) or {}).get("w", W["pooled"])
                po = sig(a + w * b)
                best = None
                for sd, px, ps in (("over", p.get("open_over"), po), ("under", p.get("open_under"), 1 - po)):
                    dec = am_dec(px)
                    if dec is None: continue
                    ev = ps * dec - 1
                    if best is None or ev > best[1]: best = (sd, ev, ps, am_prob(px))
                if best is None: continue
                sd, ev, ps, be = best
                lc, act = p.get("line_close"), p.get("actual")
                won = None if (p.get("push") or lc is None or act is None or abs(act - lc) < 1e-9) \
                    else (1.0 if (act > lc) == (sd == "over") else 0.0)
                p.update({"w_anchor": round(w, 3), "p_anchor_over": round(po, 4), "anchor_side": sd,
                          "p_anchor": round(ps, 4), "ev_anchor": round(ev, 4),
                          "grade_anchor": grade_letter(ps, be), "won_anchor": won})
        full = [(p["market"], x[0], x[1], x[2]) for p in rows
                for x in [inp[id(p)]] if x is not None and x[0] is not None]
        Wf = _anchor_weights(full)
        if Wf:
            latest = {"season": season, "through_week": weeks[-1] if weeks else None,
                      "k": ANCHOR_K, "n": len(full), **Wf}
    return latest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default=None)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    prop_picks, pmeta = settle_props(args.season)
    n_wh = tag_withheld(prop_picks)
    if n_wh: print(f"[settle] withheld-player ledger rows: {n_wh}")
    anchor_w = anchor_shadow(prop_picks)
    if anchor_w:
        mk = ", ".join(f"{k} {v['w']:.2f} (n {v['n']})" for k, v in sorted(anchor_w["markets"].items()))
        print(f"[settle] anchored shadow weights (season {anchor_w['season']}, pooled {anchor_w['pooled']:.2f}): {mk}")
    game_picks, gmeta = settle_games(args.season)
    board = build_scoreboard(prop_picks, game_picks)

    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ledger = {"generated": now, "props": prop_picks, "games": game_picks,
              "meta": {"props": pmeta, "games": gmeta}}
    scoreboard = {"generated": now, "k_shrink": K_BLEND,
                  "settled_props": len(prop_picks), "settled_games": len(game_picks),
                  **board, "meta": {"props": pmeta, "games": gmeta}}

    print(f"[settle] props: {pmeta}")
    print(f"[settle] games: {gmeta}")
    for mk, m in sorted(board["markets"].items()):
        wr = m["winrate_close"]; cb = m["clv_beat_rate"]
        print(f"   {mk:14s} n={m['n']:4d} graded={m['n_graded']:4d} "
              f"win={wr:.3f} " if wr is not None else f"   {mk:14s} n={m['n']:4d} graded={m['n_graded']:4d} win=  -   "
              , f"clv-beat={cb:.3f}" if cb is not None else "clv-beat=  -  ",
              f"w={m['blend']['w_measured']}" if m['blend']['w_measured'] is not None else "")

    # Shadow side-by-side (history shift vs live), same rows, -110 each.
    sh = [p for p in prop_picks if p.get("won_hist") is not None and p.get("won_close") is not None]
    if sh:
        u = lambda ws: sum(100 / 110 if w == 1.0 else -1.0 for w in ws)
        cur, hst = [p["won_close"] for p in sh], [p["won_hist"] for p in sh]
        flips = sum(1 for p in sh if p["side_hist"] != p["side"])
        print(f"[settle] history-shift shadow: n={len(sh)} flips={flips} "
              f"live {sum(cur):.0f}-{len(cur) - sum(cur):.0f} {u(cur):+.1f}u | "
              f"shadow {sum(hst):.0f}-{len(hst) - sum(hst):.0f} {u(hst):+.1f}u")

    # Grade-anchor shadow: A/B picks under the live coin-flip anchor vs the
    # market anchor, on the projection side and the alt (against-lean) side.
    # Units at -110 here; the Track Record artifact prices them at the close.
    def _ab(rows, gk, wk):
        ws = [p[wk] for p in rows if p.get(gk) in ("A", "B") and p.get(wk) is not None]
        return f"{sum(ws):.0f}-{len(ws) - sum(ws):.0f} {sum(100 / 110 if w == 1.0 else -1.0 for w in ws):+.1f}u"
    if any(p.get("grade_mkt") for p in prop_picks):
        print(f"[settle] grade-anchor shadow A+B: lean side live {_ab(prop_picks, 'grade', 'won_close')} "
              f"| mkt {_ab(prop_picks, 'grade_mkt', 'won_close')} ; alt side live "
              f"{_ab(prop_picks, 'grade_alt', 'won_alt')} | mkt {_ab(prop_picks, 'grade_mkt_alt', 'won_alt')}")

    # Fade-Vault-team-lean shadow: A/B props on the side against Vault's team
    # lean (pass_int excluded: its over is bad offense). Units at -110 here.
    fade = []
    for p in prop_picks:
        ln = p.get("vault_team_lean")
        if ln not in ("over", "under") or p.get("market") == "pass_int" or p.get("won_close") is None:
            continue
        if p.get("side") != ln and p.get("grade") in ("A", "B"):
            fade.append(p["won_close"])
        if p.get("side") == ln and p.get("grade_alt") in ("A", "B") and p.get("won_alt") is not None:
            fade.append(p["won_alt"])
    if fade:
        print(f"[settle] fade-team-lean shadow A+B: {sum(fade):.0f}-{len(fade) - sum(fade):.0f} "
              f"{sum(100 / 110 if w == 1.0 else -1.0 for w in fade):+.1f}u")

    # Anchored shadow vs live: A/B picks graded each way, settled at the close,
    # units at the closing price of the side taken.
    def _abu(rows, gk, sk, wk):
        n = w_ = 0; u = 0.0
        for p in rows:
            if p.get(gk) not in ("A", "B") or p.get(wk) is None: continue
            px = p.get("close_over") if p.get(sk) == "over" else p.get("close_under")
            dec = am_dec(px) or (1 + 100 / 110)
            n += 1; w_ += p[wk] == 1.0; u += (dec - 1) if p[wk] == 1.0 else -1.0
        return f"{w_}-{n - w_} {u:+.1f}u"
    an = [p for p in prop_picks if p.get("grade_anchor")]
    if an:
        print(f"[settle] anchored shadow A+B (rows it could price, n={len(an)}): live {_abu(an, 'grade', 'side', 'won_close')} "
              f"| anchored {_abu(an, 'grade_anchor', 'anchor_side', 'won_anchor')}")

    recal = build_grade_recal(prop_picks)
    print(f"[settle] grade recal: ready={recal['ready']} "
          f"weeks={recal['n_weeks']}/{recal['min_weeks']} n={recal['n_samples']}"
          + (f" knots={len(recal['knots'])}" if recal.get('knots') else ""))

    plays = settle_card(prop_picks)
    grules = game_rules(game_picks, _load_data("game_rules.json"))
    if grules:
        for k, v in grules["buckets"].items():
            print(f"[settle]   game rule {k:14s} {'ON ' if v['on'] else 'off'} {v['W']}-{v['L']} {v['units']:+.1f}u ({v['why']})")
    if plays:
        for s, v in plays["seasons"].items():
            m = v["summary"]
            print(f"[settle] Vault's Plays {s}: {m['W']}-{m['L']}-{m['P']} ({m['pending']} pending) "
                  f"{m['units']:+.1f}u at posted price | {m['units_close']:+.1f}u at the close | "
                  f"beat close {m['beat_close']}/{m['n_clv']}" + (f" | vs fair close {m['clv_ev']*100:+.1f}% ({m['n_ev']})" if m.get('clv_ev') is not None else ""))
        if plays.get("held"):
            hs = plays["held"]["summary"]
            print(f"[settle] held (would-be plays in withheld games): {hs['W']}-{hs['L']} ({hs['pending']} pending) {hs['units']:+.1f}u")
        if plays.get("pairs"):
            ps = plays["pairs"]["summary"]
            print(f"[settle] pick'em pairs: {ps['W']}-{ps['L']} ({ps['void']} void, {ps['pending']} pending) {ps['units']:+.1f}u")
        for k, v in ((plays.get("rules") or {}).get("buckets") or {}).items():
            print(f"[settle]   card rule {k:22s} {'ON ' if v['on'] else 'off'} {v.get('W', 0)}-{v.get('L', 0)} {v.get('units', 0):+.1f}u ({v['why']})")

    if args.dry:
        print("[settle] --dry: not written"); return
    json.dump(ledger, open(os.path.join(DATA, "bet_results.json"), "w"))
    json.dump(scoreboard, open(os.path.join(DATA, "edge_scoreboard.json"), "w"))
    json.dump(recal, open(os.path.join(DATA, "grade_recal.json"), "w"))
    if anchor_w:
        json.dump({"generated": now, **anchor_w}, open(os.path.join(DATA, "prop_anchor_weights.json"), "w"), indent=1)
    if grules:
        json.dump({"generated": now, **grules}, open(os.path.join(DATA, "game_rules.json"), "w"), indent=1)
    if plays is not None:
        json.dump({"generated": now, **plays}, open(os.path.join(DATA, "best_bets_record.json"), "w"))
        if plays.get("rules"):
            json.dump({"generated": now, **plays["rules"]}, open(os.path.join(DATA, "best_bets_rules.json"), "w"), indent=1)
    print(f"[settle] wrote bet_results.json ({len(prop_picks)} props, {len(game_picks)} games) + edge_scoreboard.json + grade_recal.json")


if __name__ == "__main__":
    main()
