"""Joint Monte Carlo NFL game simulator (Phase 1 prototype). ZERO sportsbook inputs.

One simulated game draws, per sim and shared across every player prop in that game:
  game pace + game-script (margin) noise -> team plays and pass rate -> team targets and carries
  -> Dirichlet-multinomial split by rolling role shares -> per-player efficiency (shrunk to position priors)
  -> receiving yards.  QB passing yards = the sum of the simulated receiving yards, so QB/WR correlation
  is produced by the structure rather than bolted on.

Everything is built walk-forward: `State.advance(game)` only ever sees games strictly before the target week.
"""
import math
import numpy as np
import pandas as pd

HFA_PTS = 2.0          # home-field points in the internal margin proxy (league-wide, from nflverse scores)
EWMA_HL_GAMES = 5.0    # half-life, in team games, for role shares
EFF_HL_GAMES = 14.0    # half-life for efficiency (slower: efficiency is noisier)
SHARE_PRIOR_GAMES = 2.0
POOL_GAMES = 17        # a player is in the pool if he played for the team in its last N games
KEY_SHARE = 0.08       # "key" player for the missed-game share-gain table
K_CATCH = 45.0         # pseudo-targets for catch rate shrinkage
K_YPR = 30.0           # pseudo-receptions for yards/reception shrinkage
K_YPC = 70.0           # pseudo-carries for yards/carry shrinkage
POS_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE"}


def _hl_w(n, hl):
    # weight of the k-th most recent game (k=0 is latest)
    return 0.5 ** (np.arange(n) / hl)


class State:
    """Chronological state: player game logs, team-game logs, share-gain table, pre-game forecast residuals."""

    def __init__(self, tg, pw, snaps, inj, games, shapes):
        self.shapes = shapes
        self.tg = tg.merge(games.assign(_h=1)[["game_id", "home_team", "away_team", "home_score", "away_score"]],
                           on="game_id", how="left")
        self.tg["pts"] = np.where(self.tg.team == self.tg.home_team, self.tg.home_score, self.tg.away_score)
        self.tg["opp_pts"] = np.where(self.tg.team == self.tg.home_team, self.tg.away_score, self.tg.home_score)
        self.tg["home"] = (self.tg.team == self.tg.home_team).astype(int)
        self.tg = self.tg.sort_values(["season", "week"]).reset_index(drop=True)
        self.pw = pw.sort_values(["season", "week"]).reset_index(drop=True)
        self.snap_set = set(zip(snaps.season, snaps.week, snaps.team, snaps.gsis))
        self.inj = inj
        self.inj_any = set(zip(inj.season, inj.week, inj.gsis_id))
        self.order = sorted({(s, w) for s, w in zip(self.tg.season, self.tg.week)})
        self._prep_players()

    # ---------- player game table with team totals ----------
    def _prep_players(self):
        pw = self.pw
        tot = pw.groupby(["season", "week", "team"]).agg(t_att=("attempts", "sum"), t_tgt=("targets", "sum"),
                                                          t_car=("carries", "sum")).reset_index()
        pw = pw.merge(tot, on=["season", "week", "team"])
        pw["tshare"] = pw.targets / pw.t_tgt.clip(lower=1)
        pw["cshare"] = pw.carries / pw.t_car.clip(lower=1)
        pw["ashare"] = pw.attempts / pw.t_att.clip(lower=1)
        self.pw = pw
        self.pos_of = pw.groupby("gsis").pos.last().to_dict()
        self.name_of = pw.groupby("gsis").name.last().to_dict()
        # active-flag: played (stat row or offensive snap)
        self.active = {(s, w, t, g) for s, w, t, g in zip(pw.season, pw.week, pw.team, pw.gsis)} | self.snap_set

    def team_hist(self, team, before):
        """Team-game rows strictly before (season, week)."""
        t = self.tg
        m = (t.team == team) & ((t.season < before[0]) | ((t.season == before[0]) & (t.week < before[1])))
        return t[m]

    # ---------- team-level forecast ----------
    def team_ratings(self, before):
        """EWMA offensive/defensive pace, pass rate, points, shrunk to league. Returns dict team -> dict."""
        t = self.tg[(self.tg.season < before[0]) | ((self.tg.season == before[0]) & (self.tg.week < before[1]))]
        lg = dict(plays=t.plays.mean(), pr=(t.dropbacks / t.plays).mean(), pts=t.pts.mean())
        out = {}
        for team, g in t.groupby("team"):
            g = g.tail(24)
            w = _hl_w(len(g), 6.0)[::-1]
            w = w / w.sum()
            n_eff = 1.0 / np.sum(w ** 2) if len(g) else 0
            sh = n_eff / (n_eff + 4.0)
            out.setdefault(team, {})
            out[team].update(
                plays=lg["plays"] + sh * (np.dot(w, g.plays) - lg["plays"]),
                pr=lg["pr"] + sh * (np.dot(w, g.dropbacks / g.plays) - lg["pr"]),
                pts_for=lg["pts"] + sh * (np.dot(w, g.pts) - lg["pts"]))
        for team, g in t.groupby("opp"):
            g = g.tail(24)
            w = _hl_w(len(g), 6.0)[::-1]
            w = w / w.sum()
            n_eff = 1.0 / np.sum(w ** 2) if len(g) else 0
            sh = n_eff / (n_eff + 6.0)
            out.setdefault(team, {})
            out[team].update(
                d_plays=lg["plays"] + sh * (np.dot(w, g.plays) - lg["plays"]),
                d_pr=lg["pr"] + sh * (np.dot(w, g.dropbacks / g.plays) - lg["pr"]),
                pts_against=lg["pts"] + sh * (np.dot(w, g.pts) - lg["pts"]))
        return lg, out

    def fit_game_params(self, before):
        """Walk-forward residual structure from games before `before`, using each game's own pre-game forecast.
        Returns sd of shared pace, per-team pace, pass-rate noise, and the regression of pass rate on realised margin."""
        rows = []
        done = [o for o in self.order if o < before]
        for o in done[-48:]:   # last ~3 seasons of weeks at most; also cheap
            lg, rt = self._rt_cache(o)
            g = self.tg[(self.tg.season == o[0]) & (self.tg.week == o[1])]
            for r in g.itertuples():
                a, b = rt.get(r.team), rt.get(r.opp)
                if not a or not b or "d_plays" not in b or "plays" not in a:
                    continue
                exp_plays = 0.5 * (a["plays"] + b["d_plays"])
                exp_pr = a["pr"] + b["d_pr"] - lg["pr"]
                rows.append((r.game_id, r.plays - exp_plays, r.dropbacks / r.plays - exp_pr, r.pts - r.opp_pts))
        d = pd.DataFrame(rows, columns=["gid", "dp", "dpr", "margin"])
        if len(d) < 200:
            return dict(sd_shared=3.0, sd_team=5.5, sd_pr=0.06, gamma=0.0035, sd_margin=13.0)
        gp = d.groupby("gid").dp.agg(["sum", "count"])
        gp = gp[gp["count"] == 2]
        # shared pace component: cov of the two teams' residuals in the same game
        pairs = d.groupby("gid").dp.apply(lambda x: x.values[0] * x.values[1] if len(x) == 2 else np.nan).dropna()
        sd_shared = math.sqrt(max(pairs.mean(), 1.0))
        sd_team = math.sqrt(max(d.dp.var() - sd_shared ** 2, 4.0))
        # pass rate on realised margin (script effect), residual noise
        x, y = d.margin.values, d.dpr.values
        gamma = -float(np.dot(x - x.mean(), y - y.mean()) / np.dot(x - x.mean(), x - x.mean()))   # per point of margin
        resid = y - (-gamma) * (x - x.mean())
        return dict(sd_shared=sd_shared, sd_team=sd_team, sd_pr=float(np.std(resid)), gamma=gamma,
                    sd_margin=float(np.std(x)))

    _rt = {}

    def _rt_cache(self, o):
        if o not in self._rt:
            self._rt[o] = self.team_ratings(o)
        return self._rt[o]

    # ---------- player role + efficiency state ----------
    def team_pool(self, team, before):
        """Players who played for `team` in its last POOL_GAMES games, with active-only EWMA shares and efficiency."""
        th = self.team_hist(team, before)
        last = th.tail(POOL_GAMES)
        keys = list(zip(last.season, last.week))
        pwt = self.pw[self.pw.team == team]
        pwt = pwt[(pwt.season < before[0]) | ((pwt.season == before[0]) & (pwt.week < before[1]))]
        win = pwt.merge(pd.DataFrame(keys, columns=["season", "week"]), on=["season", "week"])
        win = win[win.pos.isin(["QB", "RB", "FB", "WR", "TE"]) & ((win.targets + win.carries + win.attempts) > 0)]
        return th, win.gsis.unique()

    def sack_rate(self, before):
        t = self.tg[(self.tg.season < before[0]) | ((self.tg.season == before[0]) & (self.tg.week < before[1]))]
        return float(t.sacks.sum() / max(t.dropbacks.sum(), 1))

    def targets_per_attempt(self, before):
        p = self.pw[(self.pw.season < before[0]) | ((self.pw.season == before[0]) & (self.pw.week < before[1]))]
        return float(p.targets.sum() / max(p.attempts.sum(), 1))

    def pos_priors(self, before):
        p = self.pw[(self.pw.season < before[0]) | ((self.pw.season == before[0]) & (self.pw.week < before[1]))]
        p = p[p.pos.isin(["QB", "RB", "WR", "TE"])]
        pri = {}
        for pos, g in p.groupby("pos"):
            pri[pos] = dict(
                catch=g.receptions.sum() / max(g.targets.sum(), 1),
                ypr=g.receiving_yards.sum() / max(g.receptions.sum(), 1),
                ypc=g.rushing_yards.sum() / max(g.carries.sum(), 1))
        return pri

    def player_state(self, gsis, team, before, pri, last_games):
        """Role shares: recency-weighted over the team's last games. A game the player missed while on the injury
        report is skipped (he is not penalised for being hurt); a game he missed otherwise counts as a zero."""
        p = self.pw[(self.pw.gsis == gsis)]
        p = p[(p.season < before[0]) | ((p.season == before[0]) & (p.week < before[1]))]
        pt = p[p.team == team]
        pos = POS_GROUP.get(self.pos_of.get(gsis, ""), "WR")
        pr = pri.get(pos, pri["WR"])
        rows = {(r.season, r.week): r for r in pt.itertuples()}
        games8 = last_games[-8:][::-1]                 # most recent first
        wts = _hl_w(len(games8), EWMA_HL_GAMES)
        n_act = sum(1 for key in games8 if key in rows)
        regular = n_act >= 4                           # only regulars get the benefit of the injury skip
        first = min(rows) if rows else None            # his debut with this team: earlier games say nothing about him
        num = dict(tshare=0.0, cshare=0.0, ashare=0.0)
        den = 0.0
        qnum, qden = 0.0, 0.0                          # QB attempts share uses a much shorter memory (hl 2)
        qw = _hl_w(len(games8), 2.0)
        for wgt, qwgt, key in zip(wts, qw, games8):
            r = rows.get(key)
            if r is not None:
                for k in num:
                    num[k] += wgt * getattr(r, k)
                den += wgt
                qnum += qwgt * r.ashare
                qden += qwgt
            elif first is not None and key < first:
                continue
            elif regular and (key[0], key[1], gsis) in self.inj_any:
                continue                                 # hurt: no information about his role
            else:
                den += wgt                               # healthy scratch / not used: counts as zero
                qden += qwgt
        out = dict(gsis=gsis, pos=pos, n=len(pt), n_act=n_act)
        if den > 0 and n_act > 0:
            for k in num:
                out[k] = num[k] / den
            out["qshare"] = qnum / qden if qden > 0 else 0.0
        else:                                            # not seen in the team's last 8 games: no current role
            for k in num:
                out[k] = 0.0
            out["qshare"] = 0.0
        # efficiency over all of the player's games (team-agnostic: skill travels, volume doesn't), slower decay
        w2 = _hl_w(len(p), EFF_HL_GAMES)[::-1]
        tg_, rc_ = (p.targets.values * w2).sum(), (p.receptions.values * w2).sum()
        ry_, ca_, cy_ = (p.receiving_yards.values * w2).sum(), (p.carries.values * w2).sum(), (p.rushing_yards.values * w2).sum()
        out["catch"] = (rc_ + K_CATCH * pr["catch"]) / (tg_ + K_CATCH)
        out["ypr"] = (ry_ + K_YPR * pr["ypr"]) / (rc_ + K_YPR)
        out["ypc"] = (cy_ + K_YPC * pr["ypc"]) / (ca_ + K_YPC)
        out["n_tgt"], out["n_rec"], out["n_car"] = float(tg_), float(rc_), float(ca_)
        return out

    def gain_table(self, team, before):
        """For each key player i of `team`, the average share change of every active teammate j in games i missed,
        relative to j's own pre-game rolling share. Returns {i: (n_missed, {j: [dT, dC]})}."""
        th = self.team_hist(team, before)
        if len(th) < 4:
            return {}
        pwt = self.pw[(self.pw.team == team) & ((self.pw.season < before[0]) |
                                                  ((self.pw.season == before[0]) & (self.pw.week < before[1])))]
        games_ = list(zip(th.season, th.week))
        # pre-game rolling share per (game idx, player), active games only
        rows_by_game = {k: d for k, d in pwt.groupby(["season", "week"])}
        act = {}
        for idx, (s, w) in enumerate(games_):
            d = rows_by_game.get((s, w))
            act[idx] = (set(d.gsis) if d is not None else set()) | {g for g in pwt.gsis.unique()
                                                                  if (s, w, team, g) in self.snap_set}
        res = {}
        pre = {}   # gsis -> (list of tshare, list of cshare) so far
        for idx, (s, w) in enumerate(games_):
            a = act[idx]
            # who was key before this game and is inactive now
            for i, (ts, cs) in list(pre.items()):
                if i in a or len(ts) < 3:
                    continue
                wts = _hl_w(len(ts), EWMA_HL_GAMES)[::-1]
                wts = wts / wts.sum()
                si = max(float(np.dot(wts, ts)), float(np.dot(wts, cs)))
                if si < KEY_SHARE:
                    continue
                n, dd = res.get(i, (0, {}))
                row = rows_by_game.get((s, w))
                for r in (row.itertuples() if row is not None else []):
                    j = r.gsis
                    if j == i or j not in pre:
                        continue
                    tj, cj = pre[j]
                    if len(tj) < 2:
                        continue
                    wj = _hl_w(len(tj), EWMA_HL_GAMES)[::-1]
                    wj = wj / wj.sum()
                    d0 = dd.get(j, [0.0, 0.0])
                    dd[j] = [d0[0] + r.tshare - float(np.dot(wj, tj)), d0[1] + r.cshare - float(np.dot(wj, cj))]
                res[i] = (n + 1, dd)
            d = rows_by_game.get((s, w))
            for r in (d.itertuples() if d is not None else []):
                ts, cs = pre.setdefault(r.gsis, ([], []))
                ts.append(r.tshare)
                cs.append(r.cshare)
        return res

    def outs_for(self, team, week_key):
        i = self.inj[(self.inj.team == team) & (self.inj.season == week_key[0]) & (self.inj.week == week_key[1])]
        return set(i[i.report_status.isin(["Out"])].gsis_id)


def _normalise(sh, floor_other=0.03):
    s = np.clip(sh, 0, None)
    tot = s.sum()
    other = max(1.0 - tot, floor_other)
    full = np.append(s, other)
    return full / full.sum()


def build_team_roles(state, team, before, pri, outs):
    """Returns list of player dicts with final tshare/cshare after injury reallocation, plus 'other' pseudo-player."""
    th, cand = state.team_pool(team, before)
    gt = state.gain_table(team, before)
    lastg = list(zip(th.season, th.week))
    players = [state.player_state(g, team, before, pri, lastg) for g in cand]
    players = [p for p in players if p["n"] >= 1]
    by = {p["gsis"]: p for p in players}
    # recent-game weights to avoid double counting absence already in the EWMA
    last = list(zip(th.season, th.week))[-8:]
    wts = _hl_w(len(last), EWMA_HL_GAMES)[::-1] if last else np.array([])
    for i in outs:
        if i not in by:
            continue
        pi = by[i]
        inact = np.array([0.0 if (s, w, team, i) in state.active else 1.0 for s, w in last])
        w_in = float(np.dot(wts, inact) / max(wts.sum(), 1e-9)) if len(wts) else 0.0
        for key, gi in (("tshare", 0), ("cshare", 1)):
            freed = pi[key] * (1.0 - w_in)
            pi[key] = 0.0
            if freed <= 0:
                continue
            recv = [p for p in players if p["gsis"] not in outs and p["gsis"] != i]
            if not recv:
                continue
            n_miss, dd = gt.get(i, (0, {}))
            gains = np.array([max(dd.get(p["gsis"], [0, 0])[gi], 0.0) / (n_miss + 2.0) for p in recv]) if n_miss else \
                np.zeros(len(recv))
            used = 0.0
            if gains.sum() > 0:
                a = min(gains.sum(), freed)
                for p, gn in zip(recv, gains):
                    p[key] += gn * a / gains.sum()
                used = a
            rest = freed - used
            if rest > 0:     # fallback: proportional to same-position shares (70%), else/all teammates (30%)
                samepos = [p for p in recv if p["pos"] == pi["pos"]]
                tot_all = sum(p[key] for p in recv) or 1.0
                f_same = 0.7 if samepos else 0.0
                tot_same = sum(p[key] for p in samepos) or 1.0
                for p in recv:
                    p[key] += rest * (1 - f_same) * p[key] / tot_all
                    if p in samepos:
                        p[key] += rest * f_same * p[key] / tot_same
    # QB attempts share: recency-weighted, zero-filled over the last games, among QBs not listed Out;
    # the clear starter is floored at 0.95 (starters play essentially the whole game)
    qbs = [p for p in players if p["pos"] == "QB" and p["gsis"] not in outs and p.get("qshare", 0) > 0]
    sh = []
    if qbs:
        tot = sum(p["qshare"] for p in qbs)
        sh = [p["qshare"] / tot for p in qbs]
        top = int(np.argmax(sh))
        if sh[top] >= 0.5:
            rest = [i for i in range(len(sh)) if i != top]
            rs = sum(sh[i] for i in rest)
            fl = max(sh[top], 0.95)
            sh = [fl if i == top else (sh[i] / rs * (1 - fl) if rs > 0 else 0.0) for i in range(len(sh))]
    for p in players:
        p["ashare_f"] = 0.0
    for p, x in zip(qbs, sh):
        p["ashare_f"] = x
    return players, by


def simulate_game(state, away, home, before, n=10000, seed=0, params=None, kappa=None, sigma_te=0.10):
    """Simulate one game. Returns dict team -> dict gsis -> dict stat -> array(n)."""
    rng = np.random.default_rng(seed)
    lg, rt = state._rt_cache(before)
    pri = state.pos_priors(before)
    tpa = state.targets_per_attempt(before)
    prm = params or state.fit_game_params(before)
    kappa = kappa or 20.0
    margin_hat = {}
    ra, rh = rt.get(away), rt.get(home)
    if not ra or not rh:
        return None
    # internal strength-based margin proxy from points for/against (no sportsbook input)
    mh = ((rh["pts_for"] + ra["pts_against"]) / 2 - (ra["pts_for"] + rh["pts_against"]) / 2) + HFA_PTS
    margin = rng.normal(mh, prm["sd_margin"] * 0.9, n)   # home margin; sd shrunk a little: part of the spread is already in mh noise
    g_pace = rng.normal(0, prm["sd_shared"], n)
    res = {}
    for team, opp, sign in ((home, away, 1.0), (away, home, -1.0)):
        a, b = rt[team], rt[opp]
        plays = 0.5 * (a["plays"] + b["d_plays"]) + g_pace + rng.normal(0, prm["sd_team"], n)
        plays = np.clip(np.round(plays), 40, 95)
        pr = a["pr"] + b["d_pr"] - lg["pr"] - prm["gamma"] * (sign * margin - sign * mh) + rng.normal(0, prm["sd_pr"], n)
        pr = np.clip(pr, 0.30, 0.80)
        # script: team up by more than expected passes less (gamma>0)
        dropbacks = np.round(plays * pr).astype(int)
        sack_rate = state.sack_rate(before)
        sacks = rng.binomial(dropbacks, sack_rate)
        att = dropbacks - sacks
        tgt_tot = rng.binomial(att, tpa)           # throwaways/spikes are attempts but not targets
        car = (plays - dropbacks).astype(int)
        res[team] = dict(att=att, tgt=tgt_tot, car=car)
    out = {}
    z_pass = {t: rng.normal(0, sigma_te, n) for t in (home, away)}   # shared team passing-efficiency shock
    for team in (home, away):
        outs = state.outs_for(team, before)
        players, by = build_team_roles(state, team, before, pri, outs)
        att, car = res[team]["tgt"], res[team]["car"]
        plist = [p for p in players if p["gsis"] not in outs]
        ts = _normalise(np.array([p["tshare"] for p in plist]))
        cs = _normalise(np.array([p["cshare"] for p in plist]))

        def alloc(total, shares):
            gam = rng.gamma(np.maximum(kappa * shares, 1e-3), size=(n, len(shares)))
            pvec = gam / gam.sum(1, keepdims=True)
            return rng.multinomial(total, pvec)
        tgt = alloc(att, ts)
        crs = alloc(car, cs)
        st = {}
        tot_pass_yds = np.zeros(n)
        for k, p in enumerate(plist + [None]):
            if p is None:
                pos, catch, ypr, ypc = "WR", pri["WR"]["catch"], pri["WR"]["ypr"] * 0.85, pri["RB"]["ypc"]
                n_t, n_r, n_c = 100, 60, 100
            else:
                pos, catch, ypr, ypc = p["pos"], p["catch"], p["ypr"], p["ypc"]
                n_t, n_r, n_c = p["n_tgt"], p["n_rec"], p["n_car"]
            # per-sim parameter uncertainty (catch rate Beta, ypr/ypc lognormal) + shared team-efficiency shock
            m = n_t + K_CATCH
            cp = rng.beta(max(catch * m, 1e-3), max((1 - catch) * m, 1e-3), n)
            cp = 1 / (1 + np.exp(-(np.log(cp / (1 - cp)) + z_pass[team] * 0.5)))
            rec = rng.binomial(tgt[:, k], cp)
            shp = state.shapes.get(f"rec_{pos}", state.shapes["rec_WR"])
            kshape = (shp["mean"] / shp["sd"]) ** 2
            mu = ypr * np.exp(rng.normal(0, 0.35 / math.sqrt(n_r + K_YPR), n) + z_pass[team])
            ry = np.where(rec > 0, rng.gamma(np.maximum(rec * kshape, 1e-6)) * (mu / kshape), 0.0)
            tot_pass_yds += ry
            sh2 = state.shapes.get(f"run_{pos}", state.shapes["run_RB"])
            k2 = (sh2["mean"] / sh2["sd"]) ** 2
            mu2 = ypc * np.exp(rng.normal(0, 0.45 / math.sqrt(n_c + K_YPC), n))
            cr = crs[:, k]
            ruy = np.where(cr > 0, rng.gamma(np.maximum(cr * k2, 1e-6)) * (mu2 / k2), 0.0)
            if p is not None:
                st[p["gsis"]] = dict(pos=pos, n_act=p["n_act"], rec=rec, rec_yd=ry, rush_yd=ruy, targets=tgt[:, k], carries=crs[:, k])
        # QB passing yards = team receiving yards x QB share of attempts
        for p in plist:
            if p["pos"] == "QB" and p["ashare_f"] >= 0.6:   # unclear starter (returning from injury, rotation) = no projection
                st[p["gsis"]]["pass_yd"] = tot_pass_yds * p["ashare_f"]
        st["_team_pass_yd"] = tot_pass_yds
        out[team] = st
    out["_margin"] = margin
    return out
