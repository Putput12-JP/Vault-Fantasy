#!/usr/bin/env python3
"""
Sharp agreement on Vault's own game prices (Step 4). Registration: docs/sharp-agree-prereg.md (read it first, every definition is there).
Context only: not a pick, a size, a Play gate or an agree total (CLAUDE.md). A pass only lets the user *consider* a context label.

  python3 scripts/sharp_agree.py derive --data DIR --holders PM_HOLDERS --ledger PM_LEDGER [--sharp-data data.json] [--closes pm_closes.json] --out FILE
  python3 scripts/sharp_agree.py report --data DIR --out FILE [--derived FILE]

`derive` writes one flag per V2 game-market row (NBA and NFL, `kind` book or exch, Plays + Watch + Passed alike) first seen at or after
START. The flag is rebuilt AS OF the row's `firstSeen`, never later, from stored data only:
  1. the Polymarket event: the slug's two teams and a start within 12 h of the row's (a stored sharp-data join by Vault key, when the game
     is still on the board, supplies the team names that map outcomes to home / away; NBA falls back to the slug's nicknames)
  2. the market: moneyline = the moneyline; spread / total = a market with the SAME line, else `no_read`
  3. holders as of `firstSeen`: the holders change log replayed to that time (scan_pm_holders.keyframe with the cut moved to `firstSeen`);
     the matched market needs an accepted read finished no more than 60 minutes before it, else `no_read`
  4. who is on a side: the card's own holders (scripts/build_side_cards.holder_groups: $250+ per position, a two-way wallet collapsed
     to its larger side), tiers from pm_clv_tiers as of `firstSeen`, only wallets first seen by the Step 2 frozen universe date,
     class `excluded` dropped. Exactly the filter in scripts/sf_tiers.py.
Cell, S = the side the row bets:  agree / against / mixed / none / no_read (see the prereg). Dull wallets are split out inside `none`.
A derived row is written once and never rewritten: a rerun only adds rows it has not seen.
Output of derive: data/sharp_agree.json. Output of report: data/sharp_agree_record.json.

`report` joins the stored flags to the rows' own results (status, clv, units, as the V2 ledger settled them) and prints the registered
contrasts per sport. Nothing here estimates a close or a result.
"""
import argparse, collections, glob, json, math, os, random, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_side_cards as B      # noqa: E402
import sf_tiers as TIERS          # noqa: E402

# ---- fixed by the prereg (do not tune) ----
START = 1795154400            # 2026-11-20 00:00 CT: rows first seen before this are not touched
SPORTS = ("nba", "nfl")
KINDS = ("book", "exch")
READ_WINDOW = 3600            # an accepted holders read must finish this many seconds before firstSeen at most
START_GAP = 12 * 3600         # Polymarket and the row's start within this
MIN_ROWS, MIN_GAMES = 150, 40 # per cell, per sport, rows WITH a close
TESTS = 4                     # 2 sports x 2 contrasts
SEED, BOOT = 20261119, 10000
MIN_NBA_READ_SHARE = 0.70     # at least this share of NBA rows must derive a flag or the test reports "no verdict, data"
GROUP = {"ml": "ml", "sp": "spread", "tot": "total"}
SLUG = re.compile(r"^(nba|nfl)-([a-z0-9]+)-([a-z0-9]+)-(\d{4}-\d{2}-\d{2})")
ABBR = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "PHO": "PHX", "UTAH": "UTA", "WSH": "WAS", **B.NFL_ALIAS}
FILES = (("v2_plays.json", "play"), ("v2_watch.json", "watch"), ("v2_passed.json", "passed"))


def norm(t):
    t = (t or "").upper()
    return ABBR.get(t, t)


def load_rows(d):
    """Every V2 game-market row as {id: row + src}. A row in more than one file keeps the first (Plays, then Watch, then Passed)."""
    out = {}
    for fn, src in FILES:
        try:
            j = json.load(open(os.path.join(d, fn)))
        except (OSError, ValueError):
            continue
        p = j.get("plays") or j.get("rows") or j
        for r in (p.values() if isinstance(p, dict) else p):
            if isinstance(r, dict) and r.get("kind") in KINDS and r.get("sport") in SPORTS and r.get("id") and r["id"] not in out:
                out[r["id"]] = dict(r, src=src)
    return out


def eligible(r, start=None):
    g = r.get("game") or {}
    return (r.get("firstSeen") or 0) >= (START if start is None else start) and g.get("m") in GROUP and r.get("start") and r["firstSeen"] < r["start"]


# ---------- the matching ----------

def find_event(st, row, FULL_GAME):
    """{(ev, gst)} candidates for the row's game: slug teams equal to the row's two teams, start within START_GAP. One or none is a match."""
    g, sport = row["game"], row["sport"]
    want = (norm(g.get("away")), norm(g.get("home")))
    found = set()
    for m in st.m.values():
        if m.get("mt") not in FULL_GAME or not m.get("gst") or abs(m["gst"] - row["start"]) > START_GAP:
            continue
        mm = SLUG.match(m.get("ev") or "")
        if mm and mm.group(1) == sport and (norm(mm.group(2)), norm(mm.group(3))) == want:
            found.add((m["ev"], m["gst"]))
    return found


def team_names(row, games):
    """{away: [names], home: [names]} from the sharp-data game with this Vault key, else (NBA) the slug nicknames, else None."""
    gk = (row.get("game") or {}).get("gk")
    for g in games or []:
        if g.get("key") == gk:
            t = {k: [n for n in ((g.get(k) or {}).get("name"), (g.get(k) or {}).get("short")) if n] for k in ("away", "home")}
            if t["away"] and t["home"]:
                return t
    a, h = norm(row["game"].get("away")), norm(row["game"].get("home"))
    if row["sport"] == "nba" and a in B.NBA_NICK and h in B.NBA_NICK:
        return {"away": [B.NBA_NICK[a]], "home": [B.NBA_NICK[h]]}
    return None


def side_facts(ws, cls, first_seen):
    """{side: {sharp, dull}} counts, with exactly the filter of scripts/sf_tiers.tier_plays: wallet in the frozen universe, not excluded,
    tier sharp or dull. ws: holders of ONE market group ({w, side, usd, cid, rk})."""
    out = collections.defaultdict(lambda: {"sharp": 0, "dull": 0})
    for x in ws:
        fs = first_seen.get(x["w"])
        t = (x.get("rk") or {}).get("tier")
        if fs is None or fs > TIERS.REGISTERED_AT or cls.get(x["w"]) == "excluded" or t not in ("sharp", "dull"):
            continue
        out[x["side"]][t] += 1
    return out


def cell_of(sf, sa):
    if sf and sa:
        return "mixed"
    return "agree" if sf else "against" if sa else "none"


def derive_row(row, st, kf_fn, ledger, games, H):
    """-> the derived record for one row (cell or no_read with a reason). kf_fn(ev, gst, T) is the keyframe as of T."""
    g, T = row["game"], int(row["firstSeen"])
    base = {"id": row["id"], "src": row["src"], "sport": row["sport"], "gk": g.get("gk"), "m": g["m"], "side": g.get("side"),
            "line": g.get("hline") if g["m"] == "sp" else g.get("line"), "start": row["start"], "firstSeen": T}
    ev = find_event(st, row, H.FULL_GAME)
    if len(ev) != 1:
        return dict(base, cell="no_read", why="no_event" if not ev else "ambiguous_event")
    ev, gst = next(iter(ev))
    kf = kf_fn(ev, gst, T)
    if not kf:
        return dict(base, cell="no_read", why="no_read_before_first_sight", ev=ev)
    names = team_names(row, games)
    grp = GROUP[g["m"]]
    mt = {"ml": "moneyline", "sp": "spreads", "tot": "totals"}[g["m"]]
    cids = []
    for cid, mk in kf["mk"].items():
        if mk["mt"] != mt:
            continue
        if g["m"] == "ml":
            cids.append(cid)
        elif g["m"] == "tot":
            if mk.get("line") is not None and abs(mk["line"] - base["line"]) < 1e-9:
                cids.append(cid)
        else:                                          # spread: the market's line belongs to outcome 0; turn it into the HOME line
            norms = B.side_norms("sp", mk.get("outs") or [], names)
            first = norms.get(mk["outs"][0]) if mk.get("outs") else None
            if mk.get("line") is not None and first and abs((mk["line"] if first == "home" else -mk["line"]) - base["line"]) < 1e-9:
                cids.append(cid)
    if not cids:
        return dict(base, cell="no_read", why="no_market_at_line", ev=ev)
    lag = min(kf["mk"][c]["frz_lag"] for c in cids)
    if lag > READ_WINDOW:
        return dict(base, cell="no_read", why="read_too_old", ev=ev, read_lag=lag)
    if names is None and g["m"] != "tot":
        return dict(base, cell="no_read", why="no_team_names", ev=ev)
    groups, _, _ = B.holder_groups(kf, ledger)
    ws = [x for x in groups.get(grp, []) if x["cid"] in cids]
    cls = {x["w"]: B.classify(x, "all") for x in ws}
    norms = B.side_norms(grp if g["m"] != "sp" else "sp", list({x["side"] for x in ws}), names) if ws else {}
    for x in ws:
        x["side"] = norms.get(x["side"]) or x["side"]          # outcome name -> home / away / over / under
    if any(x["side"] not in ("home", "away", "over", "under") for x in ws):
        return dict(base, cell="no_read", why="outcome_not_mapped", ev=ev)
    facts = side_facts(ws, cls, ledger.first_seen)
    s = g["side"]
    other = {"home": "away", "away": "home", "over": "under", "under": "over"}.get(s)
    sf, sa = facts[s]["sharp"], facts[other]["sharp"]
    cell = cell_of(sf, sa)
    rec = dict(base, cell=cell, ev=ev, read_lag=lag, sharp_for=sf, sharp_against=sa, dull_for=facts[s]["dull"], dull_against=facts[other]["dull"])
    if cell == "none":
        rec["dull_split"] = "dull_with" if facts[s]["dull"] else "dull_against" if facts[other]["dull"] else "no_dull"
    return rec


def kf_as_of(H, st):
    """The keyframe machinery of scan_pm_holders with the cut moved to T (cut = gst - CUTOFF_SEC, so CUTOFF_SEC is set to gst - T for the call)."""
    def fn(ev, gst, T):
        old = H.CUTOFF_SEC
        H.CUTOFF_SEC = gst - T
        try:
            return H.keyframe(st, ev, gst, T)
        finally:
            H.CUTOFF_SEC = old
    return fn


def do_derive(a):
    import scan_pm_holders as H
    rows = load_rows(a.data)
    try:
        out = json.load(open(a.out))
    except (OSError, ValueError):
        out = {"version": 1, "start": START, "rows": {}}
    todo = {k: r for k, r in rows.items() if eligible(r, a.start) and k not in out["rows"]}
    games = []
    if a.sharp_data and os.path.exists(a.sharp_data):
        games = json.load(open(a.sharp_data)).get("games") or []
    pm_closes = json.load(open(a.closes)) if a.closes and os.path.exists(a.closes) else {}
    now, n = int(time.time()), 0
    for sport in SPORTS:
        mine = [r for r in todo.values() if r["sport"] == sport]
        if not mine:
            continue
        st, _ = H.replay(a.holders, sport, now)
        ledger = B.Ledger.load(a.ledger, sport, a.holders, pm_closes)
        kf_fn = kf_as_of(H, st)
        for r in sorted(mine, key=lambda r: r["firstSeen"]):
            out["rows"][r["id"]] = derive_row(r, st, kf_fn, ledger, games, H)
            n += 1
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out + ".tmp", "w"), separators=(",", ":"), sort_keys=True)
    os.replace(a.out + ".tmp", a.out)
    c = collections.Counter(v["cell"] for v in out["rows"].values())
    print(f"derived {n} new rows; file holds {len(out['rows'])}: {dict(c)}")


# ---------- the report ----------

def clusters(vals_by_game):
    """[(sum, n)] per game, so a resample draws whole games (rows of one game share a close)."""
    return [(sum(v), len(v)) for v in vals_by_game.values() if v]


def boot_mean(cl, rng):
    ms = []
    for _ in range(BOOT):
        s = [cl[rng.randrange(len(cl))] for _ in cl]
        t = sum(n for _, n in s)
        ms.append(sum(x for x, _ in s) / t if t else 0.0)
    return ms


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(p * len(xs))))]


def contrast(a, b, rng, alpha):
    """a minus b, mean per row, resampling games independently within each cell. -> {diff, lo, hi (at alpha), lo95, hi95}."""
    ca, cb = clusters(a), clusters(b)
    if not ca or not cb:
        return None
    ma, mb = boot_mean(ca, rng), boot_mean(cb, rng)
    d = [x - y for x, y in zip(ma, mb)]
    mean = lambda cl: sum(x for x, _ in cl) / sum(n for _, n in cl)       # noqa: E731
    return {"diff": round(mean(ca) - mean(cb), 5), "lo": round(q(d, alpha / 2), 5), "hi": round(q(d, 1 - alpha / 2), 5),
            "lo95": round(q(d, .025), 5), "hi95": round(q(d, .975), 5)}


def verdict(kind, c, na, nb, ga, gb):
    """kind boost: pass when lo > 0, kill when hi < 0. veto: pass when hi < 0, kill when lo > 0. Underpowered below the cell minimums."""
    if min(na, nb) < MIN_ROWS or min(ga, gb) < MIN_GAMES or c is None:
        return "underpowered"
    if kind == "boost":
        return "pass" if c["lo"] > 0 else "kill" if c["hi"] < 0 else "no pass"
    return "pass" if c["hi"] < 0 else "kill" if c["lo"] > 0 else "no pass"


def do_report(a):
    rows = load_rows(a.data)
    der = json.load(open(a.derived))["rows"] if os.path.exists(a.derived) else {}
    rng = random.Random(SEED)
    out = {"generated": int(time.time()), "prereg": "docs/sharp-agree-prereg.md", "sports": {}}
    alpha = 0.05 / TESTS
    for sport in SPORTS:
        ds = [(d, rows.get(k)) for k, d in der.items() if d["sport"] == sport and rows.get(k)]
        cov = collections.Counter(d["cell"] for d, _ in ds)
        why = collections.Counter(d.get("why") for d, _ in ds if d["cell"] == "no_read")
        pending = sum(1 for r in rows.values() if r["sport"] == sport and eligible(r) and r["id"] not in der)
        total = len(ds) + pending
        cells = {}
        for name in ("agree", "against", "mixed", "none"):
            sel = [(d, r) for d, r in ds if d["cell"] == name]
            clv, roi = collections.defaultdict(list), collections.defaultdict(list)
            for d, r in sel:
                if r.get("clv") is not None:
                    clv[d["gk"]].append(r["clv"])
                if r.get("status") in ("won", "lost") and r.get("units") is not None:
                    roi[d["gk"]].append(r["units"])
            cells[name] = {"rows": len(sel), "plays": sum(1 for d, _ in sel if d["src"] == "play"),
                           "rows_clv": sum(len(v) for v in clv.values()), "games_clv": len(clv),
                           "clv": round(sum(sum(v) for v in clv.values()) / max(1, sum(len(v) for v in clv.values())), 5) if clv else None,
                           "rows_roi": sum(len(v) for v in roi.values()),
                           "roi": round(sum(sum(v) for v in roi.values()) / max(1, sum(len(v) for v in roi.values())), 5) if roi else None,
                           "_clv": clv}
        res = {}
        for kind, a_, b_ in (("boost", "agree", "none"), ("veto", "against", "none")):
            ca, cb = cells[a_], cells[b_]
            c = contrast(ca["_clv"], cb["_clv"], rng, alpha)
            res[kind] = {"contrast": f"{a_} minus {b_}", "ci": c, "n": [ca["rows_clv"], cb["rows_clv"]], "games": [ca["games_clv"], cb["games_clv"]],
                         "verdict": verdict(kind, c, ca["rows_clv"], cb["rows_clv"], ca["games_clv"], cb["games_clv"])}
        read_share = 1 - cov.get("no_read", 0) / len(ds) if ds else None
        data_fail = sport == "nba" and ds and read_share < MIN_NBA_READ_SHARE
        for c in cells.values():
            c.pop("_clv")
        out["sports"][sport] = {"derived": len(ds), "pending": pending, "read_share": round(read_share, 3) if read_share is not None else None,
                                "no_verdict_data": bool(data_fail), "no_read_why": dict(why), "cells": cells,
                                "tests": res if not data_fail else "no verdict, data",
                                "note": "plays-only counts are in cells[*].plays and carry no verdict"}
    try:                                           # leave the file alone when only the timestamp would change (the job commits on a diff)
        old = json.load(open(a.out))
        if {k: v for k, v in old.items() if k != "generated"} == {k: v for k, v in out.items() if k != "generated"}:
            print(json.dumps(old, indent=1))
            return
    except (OSError, ValueError):
        pass
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("derive", "report"))
    ap.add_argument("--data", required=True, help="folder with v2_plays.json, v2_watch.json, v2_passed.json (sharp-data)")
    ap.add_argument("--holders", help="pm_holders folder (pm-holders-data)")
    ap.add_argument("--ledger", help="pm_ledger folder (sharp-history)")
    ap.add_argument("--sharp-data", help="sharp-data data.json, for team names while the game is on the board")
    ap.add_argument("--closes", default="data/pm_closes.json")
    ap.add_argument("--out", required=True, help="derive: the flags file (append-only). report: the record file")
    ap.add_argument("--derived", default="data/sharp_agree.json", help="report: the flags file written by derive")
    ap.add_argument("--start", type=int, help="derive, SMOKE TESTS ONLY: use this start instead of the registered one, and write to a scratch --out, never data/sharp_agree.json")
    a = ap.parse_args()
    if a.mode == "derive":
        if not (a.holders and a.ledger):
            ap.error("derive needs --holders and --ledger")
        do_derive(a)
    else:
        do_report(a)


if __name__ == "__main__":
    main()
