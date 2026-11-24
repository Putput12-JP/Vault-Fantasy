#!/usr/bin/env python3
"""Move grade search: final scores for the tape population (docs/sharps-v2-movegrade-search.md section 1), joined by names, start and line only.

  NBA  nba/data/game_picks.json days[*].games  [label, start, away, home, away score, home score], same teams, start within 12 h
  NFL  data/bet_results.json games[*] (week, away, home, away_score, home_score), the ordered (away, home) pair unique in the season
  CFB  data/cfbd/lines_2026.json (hs, as_, sp, ou), tape abbreviation -> school by teams_fbs_2026.json abbreviation / alternate names, else the
       hand list below (written before any score was read); accepted only when Pinnacle's home line at the cut is within 3.0 of the stored spread
       (or, with no stored spread, the total within 4.0)
  CBB  none stored for this population (report only)

  python3 -I scripts/research/mgs_results.py --pop scratch/mgs_pop.json --out scratch/mgs_scores.json
"""
import argparse, json, sys

NBA_ALIAS = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
NFL_ALIAS = {"WSH": "WAS", "LA": "LAR", "JAC": "JAX", "LVR": "LV", "OAK": "LV"}
CFB_HAND = {"AFA": "Air Force", "ARI": "Arizona", "BAMA": "Alabama", "BOISE": "Boise State", "BUFF": "Buffalo", "NCST": "NC State",
            "NW": "Northwestern", "RUT": "Rutgers", "SAM": "Sam Houston", "UMD": "Maryland", "WF": "Wake Forest", "JVST": "Jacksonville State",
            "CHA": "Charlotte", "CC": "Coastal Carolina", "CHT": "Chattanooga", "CIT": "The Citadel", "ELO": "Elon", "MC": "McNeese",
            "WOF": "Wofford", "TNT": "Tennessee Tech"}
GAP = 12 * 3600


def nba(games):
    d = json.load(open("nba/data/game_picks.json"))
    idx = []
    for day in d["days"].values():
        for g in day["games"].values():
            idx.append((NBA_ALIAS.get(g[2], g[2]), NBA_ALIAS.get(g[3], g[3]), g[1], g[4], g[5]))
    out = {}
    for gid, (a, h, st, _) in games.items():
        hit = [x for x in idx if x[0] == a and x[1] == h and abs(x[2] - st) <= GAP and x[3] is not None and x[4] is not None]
        if len(hit) == 1:
            out[gid] = [hit[0][3], hit[0][4]]
    return out


def nfl(games):
    """bet_results.json has the week but no start time: a tape game matches when its ordered (away, home) pair occurs in exactly one week of
    the season (a division rematch swaps home and away, so the ordered pair is unique in a regular season)."""
    br = json.load(open("data/bet_results.json"))["games"]
    sc = {}
    for x in br:
        if x.get("home_score") is None or x.get("away_score") is None:
            continue
        sc.setdefault((NFL_ALIAS.get(x["away"], x["away"]), NFL_ALIAS.get(x["home"], x["home"])), {})[int(x["week"])] = [x["away_score"], x["home_score"]]
    out = {}
    for gid, (a, h, st, _) in games.items():
        w = sc.get((a, h)) or {}
        if len(w) == 1:
            out[gid] = list(w.values())[0]
    return out


def cfb(games):
    teams = json.load(open("data/cfbd/teams_fbs_2026.json"))
    idx = {}
    for t in teams:
        for n in [t["abbreviation"]] + (t.get("alternateNames") or []) + [t["school"]]:
            if n:
                idx.setdefault(n.upper(), set()).add(t["school"])
    name = lambda ab: CFB_HAND.get(ab) or (next(iter(idx[ab])) if len(idx.get(ab, ())) == 1 else None)
    lines = json.load(open("data/cfbd/lines_2026.json"))
    by = {}
    for x in lines:
        if x.get("hs") is None or x.get("as_") is None:
            continue
        by.setdefault((x["away"], x["home"]), []).append(x)
    out, rej = {}, 0
    for gid, (a, h, st, pl) in games.items():
        na, nh = name(a), name(h)
        if not na or not nh:
            continue
        cands = [(x, False) for x in by.get((na, nh), [])] + [(x, True) for x in by.get((nh, na), [])]
        ok = []
        for x, flip in cands:
            sp = x.get("sp")
            if sp is not None and pl.get("sp") is not None:
                if abs((-sp if flip else sp) - pl["sp"]) <= 3.0:
                    ok.append((x, flip))
            elif sp is None and x.get("ou") is not None and pl.get("tot") is not None and abs(x["ou"] - pl["tot"]) <= 4.0:
                ok.append((x, flip))
        ids = {x["id"] for x, _ in ok}
        if len(ids) == 1:
            x, flip = ok[0]
            out[gid] = [x["hs"], x["as_"]] if flip else [x["as_"], x["hs"]]
        elif cands:
            rej += 1
    print("cfb: %d candidate games rejected by the line check or ambiguous" % rej, file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = json.load(open(a.pop))["rows"]
    games = {"nba": {}, "nfl": {}, "cfb": {}}
    for r in rows:
        if r["sport"] in games:
            g = games[r["sport"]].setdefault(r["gid"], [r["away"], r["home"], r["start"], {}])
            if r["norm"] in ("home", "over") and r["pin_line"] is not None:
                g[3]["sp" if r["g"] == "spread" else "tot" if r["g"] == "total" else "ml"] = r["pin_line"]
    out = {"nba": nba(games["nba"]), "nfl": nfl(games["nfl"]), "cfb": cfb(games["cfb"])}
    for s in out:
        print("%s: %d of %d games with a final score" % (s, len(out[s]), len(games[s])), file=sys.stderr)
    json.dump(out, open(a.out, "w"))


if __name__ == "__main__":
    main()
