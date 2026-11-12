#!/usr/bin/env python3
"""SharpFlow head-to-head record: archive what SharpFlow showed at each of Vault's cuts, then grade both on the same games.

SharpFlow (nhlsavant.com) publishes its sharp boards and picks as files in a public GitHub repo (dpk1212/nhl-savant, public/) and
rewrites them about every 10 minutes, so its page never shows what it said at a given time. This script keeps that copy:

  1. Archive. For every frozen Vault keyframe (pm_holders/<sport>/frozen/<date>/<slug>@<gst>.json) whose cut has passed, it finds the
     last commit at or before the cut of each SharpFlow file (the version that was public at the cut), and stores that game's entry
     from the three position files and that game's picks from sharp-flow-pnl.json:
       pm_record/sharpflow/<sport>/<date>/<slug>@<gst>.json          written once
     Once the game is 12 hours old it stores SharpFlow's picks for it again from the current file (status, outcome, units, cancels):
       pm_record/sharpflow/<sport>/<date>/<slug>@<gst>.final.json    written once
     Comparing the two shows what SharpFlow cancelled, re-sized or relabelled after the cut.
  2. Grade. Every SharpFlow real play (units > 0, not cancelled, in the final file) is graded by the Polymarket market's own resolution
     at SharpFlow's locked price (oddsLock, American odds). Moneyline and total picks map to one market exactly. A spread pick names
     only the team, so it is mapped to the spread rung carrying the most SharpFlow-listed money on that team, and labelled so.
       pm_record/sharpflow/rows/<sport>/<YYYY-MM>.jsonl              append-only, keyed game|market|team
  3. Record. pm_record/h2h_record.json: per sport and market, SharpFlow's real plays and Vault's card plays (shown size and the
     pre-registered lock, from scripts/grade_side_cards.py), on all games and on the games where both had a play.

Never invents a number: prices are SharpFlow's stored oddsLock and Vault's stored card price; results are Polymarket resolutions.
Sharp money is context only (CLAUDE.md). This is a record, not a signal.

usage: sharpflow_h2h.py --holders DIR --out DIR [--now EPOCH] [--days 10]
"""
import argparse, datetime as dt, glob, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pm_ledger import Client, Budget, gamma_facts, jload, jsave  # noqa: E402
from pm_data_api import PMDataError  # noqa: E402

REPO = "dpk1212/nhl-savant"
POS_FILES = {"ml": "public/sharp_positions.json", "spread": "public/sharp_spread_positions.json",
             "total": "public/sharp_total_positions.json"}
PICKS_FILE = "public/sharp-flow-pnl.json"
SPORT_KEY = {"nba": "NBA", "nfl": "NFL", "cfb": "CFB"}
GROUP = {"ml": "ml", "spread": "spread", "total": "total"}     # SharpFlow marketType -> Vault market group
MT = {"ml": "moneyline", "spread": "spreads", "total": "totals"}
SETTLE_CUT = 30 * 60         # archive a cut only once it is 30 minutes old, so a commit pushed late is already on GitHub
LOOKBACK = 2 * 3600          # a file version older than this at the cut is not "what was shown" (their scanner was down)
SETTLE_AFTER = 12 * 3600     # final picks are stored once the game is this old
GIVE_UP = 3 * 86400          # ... or, with picks still pending, once it is this old
VERSION = 1
UA = {"User-Agent": "vault-record"}


# ---------- pure logic (tests/test_side_card_record.py) ----------

def american_to_price(odds):
    if odds is None:
        return None
    o = float(odds)
    if o >= 100:
        return 100.0 / (o + 100.0)
    if o <= -100:
        return -o / (-o + 100.0)
    return None


def commit_before(commits, cut, lookback=LOOKBACK):
    """The last commit at or before `cut`, within the lookback window. commits: [{"sha", "t"}]."""
    best = None
    for c in commits:
        if cut - lookback <= c["t"] <= cut and (best is None or c["t"] > best["t"]):
            best = c
    return best


def game_entry(j, sport, ev):
    """(key, entry) of the game in one SharpFlow positions file, found by the Polymarket slug on its positions."""
    for k, g in ((j or {}).get(SPORT_KEY[sport]) or {}).items():
        if any((p.get("slug") or "").startswith(ev) for p in (g or {}).get("positions") or []):
            return k, g
    return None, None


def real_play(p):
    return (p.get("units") or 0) > 0 and not p.get("cancelled")


def map_pick(pick, markets, money):
    """(cid, side, method) of the Polymarket market a SharpFlow pick is on. markets: {cid: fact}; money: {cid: {outcome: usd}}."""
    mt, team = MT.get(pick.get("marketType")), (pick.get("team") or "").strip()
    if mt == "moneyline":
        hits = [c for c, f in markets.items() if f.get("mt") == mt and team in (f.get("outs") or [])]
        return (hits[0], team, "exact") if len(hits) == 1 else (None, None, "no_market")
    if mt == "totals":
        m = re.match(r"^(Over|Under)\s+([\d.]+)$", team)
        if m:
            hits = [c for c, f in markets.items() if f.get("mt") == mt and f.get("line") is not None
                    and float(f["line"]) == float(m.group(2)) and m.group(1) in (f.get("outs") or [])]
            if len(hits) == 1:
                return hits[0], m.group(1), "exact"
        return None, None, "no_market"
    if mt == "spreads":
        cands = [c for c, f in markets.items() if f.get("mt") == mt and team in (f.get("outs") or [])]
        cands = [c for c in cands if (money.get(c) or {}).get(team)]
        if cands:
            return max(cands, key=lambda c: money[c][team]), team, "most_money_rung"
    return None, None, "no_market"


def picks_for(picks, sport, date, names):
    """SharpFlow picks for one game: same sport and date, and both team names match the game's."""
    names = {n for n in names if n}
    return [p for p in picks if p.get("sport") == SPORT_KEY[sport] and p.get("date") == date
            and len(names) == 2 and {p.get("away"), p.get("home")} == names]


def play_rows(g, arc, fin, mk, money, now):
    """Graded rows for one game. mk: {cid: Gamma fact} for every market of the game; money: SharpFlow-listed $ per cid and outcome.

    set "at_cut":    real plays (units > 0, not cancelled) in the picks file public at Vault's cut, graded at that file's units and
                     oddsLock, whatever SharpFlow did later (a later cancel is kept and flagged: no survivorship). The headline.
    set "after_cut": real plays in the final file that were not real plays at the cut (posted or sized up after it). Reported apart.
    A spread pick names no line, so its Polymarket rung is a guess (most_money_rung). Its result there is kept as `res_mapped`, but it
    gets no flat or units P/L: SharpFlow's price belongs to a line we cannot see. Its own stated result is kept as `their_res`.
    Rows are skipped (not written) while a mapped market is unresolved."""
    at_cut = {(p.get("marketType"), p.get("team")): p for p in (arc.get("picks_at_cut") or {}).get("picks") or [] if real_play(p)}
    final = {(p.get("marketType"), p.get("team")): p for p in fin.get("picks") or []}
    jobs = [("at_cut", k, p) for k, p in at_cut.items()]
    jobs += [("after_cut", k, p) for k, p in final.items() if real_play(p) and k not in at_cut]
    out = []
    for kind, (mt, team), p in jobs:
        if mt not in GROUP:
            continue
        later = final.get((mt, team)) or {}
        cid, side, how = map_pick(p, mk, money)
        f = mk.get(cid) if cid else None
        if cid and f.get("final") is None:
            continue                                       # not resolved yet
        price = american_to_price(p.get("oddsLock"))
        row = {"key": f"{g['ev']}@{g['gst']}|{kind}|{mt}|{team}", "v": VERSION, "set": kind, "sport": g["sport"], "ev": g["ev"],
               "gst": g["gst"], "date": g["ev"][-10:], "group": GROUP[mt], "team": team, "side": side, "cid": cid, "map": how,
               "units": p.get("units"), "odds_lock": p.get("oddsLock"), "price": price, "stars": p.get("stars"),
               "tier": p.get("v8_hcStakeTier"), "final_units": later.get("units"), "cancelled_later": bool(later.get("cancelled")),
               "their_res": (later.get("outcome") or "").lower() or None, "their_profit": later.get("profit"),
               "res": None, "res_mapped": None, "flat": None, "units_pl": None, "graded_at": now}
        if cid:
            v = f["final"][f["outs"].index(side)]
            res = "win" if v == 1.0 else "loss" if v == 0.0 else "push"
            if how == "exact" and price is not None:
                row["res"] = res
                row["flat"] = round(1.0 / price - 1.0 if v == 1.0 else -1.0 if v == 0.0 else 0.0, 6)
                row["units_pl"] = round(row["flat"] * (p.get("units") or 0), 6)
            else:
                row["res_mapped"] = res
        out.append(row)
    return out


def summarize(rows, units_key="units", pl_key="units_pl"):
    g = [r for r in rows if r.get("res") in ("win", "loss", "push") and r.get("flat") is not None]
    flat = [r["flat"] for r in g]
    return {"n": len(g), "w": sum(r["res"] == "win" for r in g), "l": sum(r["res"] == "loss" for r in g),
            "p": sum(r["res"] == "push" for r in g), "flat_roi": round(sum(flat) / len(flat), 4) if flat else None,
            "units_staked": round(sum(r.get(units_key) or 0 for r in g), 2),
            "units_pl": round(sum(r.get(pl_key) or 0 for r in g), 3)}


def h2h(sf_rows, card_rows, now):
    """Head-to-head per sport and market group. Vault plays are variant `all` (the card's primary)."""
    card_rows = [r for r in card_rows if r.get("kind") != "close"]     # close rows hold CLV only; the plays are the result rows
    out = {"generated": now, "v": VERSION, "context_only": True,
           "note": "SharpFlow headline: real plays (units > 0, not cancelled) in the picks file public at Vault's cut, graded by "
                   "Polymarket resolution at that file's oddsLock, later cancels included; spread picks name no line, so they "
                   "get no priced result. "
                   "Vault rows: the card's shown size (sf, an untested rule) and the pre-registered lock (counted cards only).",
           "sports": {}}
    for sport in sorted({r["sport"] for r in sf_rows} | {r["sport"] for r in card_rows}):
        s = out["sports"].setdefault(sport, {})
        for g in ("ml", "spread", "total"):
            mine_sport = [r for r in sf_rows if r["sport"] == sport and r["group"] == g]
            theirs = [r for r in mine_sport if r.get("set") == "at_cut"]
            after = [r for r in mine_sport if r.get("set") == "after_cut"]
            vsf = [r for r in card_rows if r["sport"] == sport and r["group"] == g and r["play"] == "sf" and r["variant"] == "all"]
            vsfx = [r for r in card_rows if r["sport"] == sport and r["group"] == g and r["play"] == "sf" and r["variant"] == "sfx"]
            vlock = [r for r in card_rows if r["sport"] == sport and r["group"] == g and r["play"] == "lock"
                     and r["variant"] == "all" and r.get("counts")]
            both = {r["ev"] for r in theirs} & {r["ev"] for r in vsf}
            agree = sum(1 for ev in both if {r["side"] for r in theirs if r["ev"] == ev} == {r["side"] for r in vsf if r["ev"] == ev})
            counted = [r for r in mine_sport if r.get("final_units") and not r.get("cancelled_later")]
            s[g] = {"sharpflow": summarize(theirs), "sharpflow_after_cut": summarize(after),
                    "sharpflow_at_cut_cancelled_later": sum(1 for r in theirs if r.get("cancelled_later")),
                    "sharpflow_unpriced_spread_rungs": sum(1 for r in theirs if r.get("map") == "most_money_rung"),
                    "sharpflow_stated": {
                        "note": "SharpFlow's own result and profit on the plays its final file counts",
                        "n": len(counted), "units_pl": round(sum(r.get("their_profit") or 0 for r in counted), 3),
                        "disagree_with_polymarket": sum(1 for r in counted if r.get("their_res") and (r.get("res") or r.get("res_mapped"))
                                                        and r["their_res"] != (r.get("res") or r.get("res_mapped")))},
                    "vault_shown_size": summarize(vsf), "vault_sfx": summarize(vsfx), "vault_lock": summarize(vlock),
                    "same_games": {"games": len(both), "same_side": agree,
                                   "sharpflow": summarize([r for r in theirs if r["ev"] in both]),
                                   "vault_shown_size": summarize([r for r in vsf if r["ev"] in both])}}
        days = {}
        for r in sf_rows:
            if r["sport"] == sport and r.get("set") == "at_cut":
                d = days.setdefault(r["date"], {"sharpflow_units_pl": 0.0, "sharpflow_n": 0, "vault_units_pl": 0.0, "vault_n": 0})
                if r.get("units_pl") is not None:
                    d["sharpflow_units_pl"] = round(d["sharpflow_units_pl"] + r["units_pl"], 3)
                    d["sharpflow_n"] += 1
        for r in card_rows:
            if r["sport"] == sport and r["play"] == "sf" and r["variant"] == "all" and r.get("units_pl") is not None:
                d = days.setdefault(r["ev"][-10:], {"sharpflow_units_pl": 0.0, "sharpflow_n": 0, "vault_units_pl": 0.0, "vault_n": 0})
                d["vault_units_pl"] = round(d["vault_units_pl"] + r["units_pl"], 3)
                d["vault_n"] += 1
        s["by_day"] = dict(sorted(days.items()))
    return out


def save_record(path, obj):
    """Write a record file only when something other than its `generated` time changed, so an idle run makes no commit."""
    old = jload(path, None)
    if isinstance(old, dict) and {k: v for k, v in old.items() if k != "generated"} == \
            json.loads(json.dumps({k: v for k, v in obj.items() if k != "generated"})):
        return False
    jsave(path, obj)
    return True


# ---------- io ----------

def http_json(url, token=None):
    h = dict(UA)
    if token and "api.github.com" in url:
        h["Authorization"] = "Bearer " + token
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 502, 503):
                time.sleep(5 * (attempt + 1))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, ValueError):
            time.sleep(3 * (attempt + 1))
    return None


def commits(path, since, until, token):
    out, page = [], 1
    while True:
        q = urllib.parse.urlencode({"path": path, "since": iso(since), "until": iso(until), "per_page": 100, "page": page})
        j = http_json(f"https://api.github.com/repos/{REPO}/commits?{q}", token)
        if not isinstance(j, list):
            raise RuntimeError(f"GitHub commits {path}: no response")
        for c in j:
            t = (c.get("commit") or {}).get("committer", {}).get("date")
            if t:
                out.append({"sha": c["sha"], "t": int(dt.datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())})
        if len(j) < 100 or page >= 50:
            return out
        page += 1


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Raw:
    """SharpFlow files by commit, fetched once per run."""

    def __init__(self):
        self.cache = {}

    def get(self, sha, path):
        k = (sha, path)
        if k not in self.cache:
            self.cache[k] = http_json(f"https://raw.githubusercontent.com/{REPO}/{sha}/{path}")
        return self.cache[k]


def load_jsonl(pattern):
    rows = {}
    for fn in sorted(glob.glob(pattern)):
        with open(fn) as f:
            for l in f:
                if l.strip():
                    r = json.loads(l)
                    rows[r["key"]] = r
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--holders", required=True, help="pm_holders folder (T-15 keyframes)")
    ap.add_argument("--out", required=True, help="pm_record folder")
    ap.add_argument("--now", type=int)
    ap.add_argument("--days", type=int, default=10, help="archive games whose cut is within this many days")
    a = ap.parse_args()
    now = a.now or int(time.time())
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    root = os.path.join(a.out, "sharpflow")

    games = []
    for path in sorted(glob.glob(os.path.join(a.holders, "*", "frozen", "*", "*.json"))):
        sport, _, date, fn = os.path.relpath(path, a.holders).split(os.sep)
        if sport not in SPORT_KEY:
            continue
        kf = jload(path, None)
        if not kf or kf["cut"] > now - SETTLE_CUT or kf["cut"] < now - a.days * 86400:
            continue
        names = sorted({o for m in kf["mk"].values() if m.get("mt") == "moneyline" for o in (m.get("outs") or [])})
        games.append({"sport": sport, "date": date, "fn": fn, "ev": kf["ev"], "gst": kf["gst"], "cut": kf["cut"],
                      "cids": list(kf["mk"]), "pm_names": names})

    # 1. archive at the cut
    todo = [g for g in games if not os.path.exists(os.path.join(root, g["sport"], g["date"], g["fn"]))]
    raw, archived, problems = Raw(), 0, []
    if todo:
        lo, hi = min(g["cut"] for g in todo) - LOOKBACK, max(g["cut"] for g in todo)
        try:
            hist = {p: commits(p, lo, hi, token) for p in list(POS_FILES.values()) + [PICKS_FILE]}
        except RuntimeError as e:
            print(f"::warning::{e}; archive retried next run")
            hist = None
        for g in todo if hist else []:
            rec = {"v": VERSION, "sport": g["sport"], "ev": g["ev"], "gst": g["gst"], "cut": g["cut"], "archived_at": now,
                   "repo": REPO, "files": {}, "picks_at_cut": None}
            names = None
            for grp, p in POS_FILES.items():
                c = commit_before(hist[p], g["cut"])
                if not c:
                    rec["files"][grp] = {"status": "no_version_in_window"}
                    continue
                j = raw.get(c["sha"], p)
                if j is None:
                    rec = None
                    break
                key, entry = game_entry(j, g["sport"], g["ev"])
                rec["files"][grp] = {"sha": c["sha"], "commit_t": c["t"], "scannedAt": j.get("scannedAt"), "key": key,
                                     "status": "listed" if entry else "not_listed", "entry": entry}
                if entry and not names:
                    names = [entry.get("away"), entry.get("home")]
            if rec is None:
                problems.append([g["ev"], "raw fetch failed"])
                continue
            c = commit_before(hist[PICKS_FILE], g["cut"])
            if c:
                j = raw.get(c["sha"], PICKS_FILE)
                if j is None:
                    problems.append([g["ev"], "picks fetch failed"])
                    continue
                rec["picks_at_cut"] = {"sha": c["sha"], "commit_t": c["t"], "generatedAt": j.get("generatedAt"),
                                       "names": names or g["pm_names"],
                                       "picks": picks_for(j.get("picks") or [], g["sport"], g["ev"][-10:], names or g["pm_names"])}
            else:
                rec["picks_at_cut"] = {"status": "no_version_in_window"}
            jsave(os.path.join(root, g["sport"], g["date"], g["fn"]), rec)
            archived += 1

    # 2. final picks, once the game is old enough
    head, finals = None, 0
    for g in games:
        apath = os.path.join(root, g["sport"], g["date"], g["fn"])
        fpath = apath[:-5] + ".final.json"
        if not os.path.exists(apath) or os.path.exists(fpath) or now < g["gst"] + SETTLE_AFTER:
            continue
        if head is None:
            head = http_json(f"https://raw.githubusercontent.com/{REPO}/main/{PICKS_FILE}") or {}
        if not head.get("picks"):
            break
        arc = jload(apath, {})
        names = (arc.get("picks_at_cut") or {}).get("names") or g["pm_names"]
        ps = picks_for(head["picks"], g["sport"], g["ev"][-10:], names)
        if any(p.get("status") == "PENDING" and not p.get("cancelled") and (p.get("units") or 0) > 0 for p in ps) \
                and now < g["gst"] + GIVE_UP:
            continue
        jsave(fpath, {"v": VERSION, "ev": g["ev"], "gst": g["gst"], "stored_at": now, "generatedAt": head.get("generatedAt"),
                      "names": names, "picks": ps})
        finals += 1

    # 3. grade SharpFlow's real plays by Polymarket resolution
    have = load_jsonl(os.path.join(root, "rows", "*", "*.jsonl"))
    cache_p = os.path.join(a.out, "markets.json")
    facts = jload(cache_p, {})
    pending_games, need = [], set()
    for g in games:
        apath = os.path.join(root, g["sport"], g["date"], g["fn"])
        fin = jload(apath[:-5] + ".final.json", None)
        if not fin:
            continue
        arc = jload(apath, {})
        cids = set(g["cids"])
        money = {}
        for grp, f in (arc.get("files") or {}).items():
            for p in ((f or {}).get("entry") or {}).get("positions") or []:
                if p.get("conditionId"):
                    cids.add(p["conditionId"])
                    m = money.setdefault(p["conditionId"], {})
                    m[p.get("outcome")] = m.get(p.get("outcome"), 0.0) + float(p.get("invested") or 0)
        need |= {c for c in cids if c not in facts}
        pending_games.append((g, arc, fin, cids, money))
    fetched, gamma_ok = {}, True
    if need:
        try:
            gamma_facts(Client(0.2, 3000), sorted(need), fetched)
        except (PMDataError, Budget) as e:
            gamma_ok = False
            print(f"::warning::Gamma read failed ({e}); grading retried next run")
    for c, f in fetched.items():
        if f.get("final") is not None:
            facts[c] = {k: f.get(k) for k in ("slug", "mt", "line", "outs", "gst", "closed_at", "final")}
    allf = {**fetched, **facts}
    new = []
    for g, arc, fin, cids, money in pending_games if gamma_ok else []:
        if any(c not in allf for c in cids):
            continue                                       # Gamma did not answer for every market: never map against a gap
        mk = {c: allf[c] for c in cids}
        for row in play_rows(g, arc, fin, mk, money, now):
            if row["key"] not in have and row is not None:
                new.append(row)
    by = {}
    for r in new:
        by.setdefault((r["sport"], r["date"][:7]), []).append(r)
    for (sport, month), rs in by.items():
        p = os.path.join(root, "rows", sport, month + ".jsonl")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a") as f:
            for r in sorted(rs, key=lambda r: r["key"]):
                f.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")
    jsave(cache_p, facts)

    # 4. head-to-head record
    sf_rows = list(have.values()) + new
    card_rows = [r for r in load_jsonl(os.path.join(a.out, "cards", "*", "*.jsonl")).values() if r.get("kind") != "close"]
    rec = h2h(sf_rows, card_rows, now)
    rec["archive"] = {"games_in_window": len(games), "archived_now": archived, "finals_now": finals, "problems": problems[:20]}
    save_record(os.path.join(a.out, "h2h_record.json"), rec)
    print(json.dumps({"archived": archived, "finals": finals, "new_rows": len(new), "problems": problems[:5]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
