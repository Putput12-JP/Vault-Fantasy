#!/usr/bin/env python3
# Fast player-prop settlement feed. nflverse box scores are canonical but publish
# hours-to-a-day after a game, which left tracked PLAYER PROPS "pending" long
# after the game was final — even though the stats already exist. ESPN's summary
# boxscore carries per-player passing/rushing/receiving within minutes of the
# whistle (the same edge that lets GAME bets settle fast off ESPN's scoreboard),
# so this writes those stats into an OVERLAY file both settlement paths read
# alongside nflverse:
#
#   data/espn_player_stats_<season>.json   — { name: {name,pos,team,weeks:[row]} }
#
# shaped exactly like nflverse_stats_<season>.json's per-game `weeks` rows
# (columns pyds/att/cmp/ptds/ints/ryds/car/rtds/rec/recyds/rectds), so:
#   • scripts/settle_bets.py  (Vault Record) overlays it in load_actuals()
#   • window.VaultPropHistory (My Picks)     overlays it in load()
# with nflverse ALWAYS winning on conflict. It's a gap-filler: once nflverse
# publishes a week, that week's real rows take over and the overlay is ignored.
# Pure stdlib, no credits. Missing/failed fetches degrade to writing nothing new.
import json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
SB_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
SUM_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
ESPN_STYPE = {"pre": 1, "reg": 2, "regular": 2, "post": 3, "postseason": 3}

# ESPN team abbreviations → nflverse/Vault codes (cosmetic: only the row's `opp`).
TEAM_ALIAS = {"WSH": "WAS", "LAR": "LA"}
def team_code(t): return TEAM_ALIAS.get(t, t)


def _get(url):
    # Default urllib UA on purpose — ESPN's edge 403s custom/browser UAs (same
    # quirk settle_bets.py relies on for the scoreboard).
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def _num(s):
    """ESPN stat cell → float, or None. Handles '75', '10.7', '-', '' ."""
    if s is None: return None
    s = str(s).strip()
    if s in ("", "-", "--"): return None
    try: return float(s)
    except ValueError: return None


def _cat(team_stats, name):
    for c in team_stats:
        if c.get("name") == name:
            return c.get("labels") or [], c.get("athletes") or []
    return [], []


def target_week():
    """(season, week, espn_seasontype) to fetch — the week tracked props live in."""
    try:
        blob = json.load(open(os.path.join(DATA, "prop_line_history.json")))
        st = (blob.get("seasonType") or "regular").lower()
        return str(blob.get("season")), int(blob.get("week")), ESPN_STYPE.get(st, 2)
    except Exception as e:
        print(f"[espn-box] no prop_line_history week ({e}); nothing to fetch")
        return None


def parse_event(ev, out, season, week):
    """Add one final game's player rows to `out` (keyed by displayName)."""
    comp = ev["competitions"][0]
    if not comp.get("status", {}).get("type", {}).get("completed"):
        return 0                                   # live/scheduled — never settle a partial line
    eid = ev["id"]
    try:
        summ = _get(f"{SUM_URL}?event={eid}")
    except Exception as e:
        print(f"[espn-box] summary {eid} fetch failed ({e}); skipping"); return 0
    teams = summ.get("boxscore", {}).get("players", [])
    # team abbr → opponent abbr, for the row's opp field
    abbrs = [t["team"]["abbreviation"] for t in teams]
    opp_of = {abbrs[0]: team_code(abbrs[1]), abbrs[1]: team_code(abbrs[0])} if len(abbrs) == 2 else {}
    added = 0
    for tm in teams:
        ab = tm["team"]["abbreviation"]
        opp = opp_of.get(ab)
        stats = tm.get("statistics", [])
        rows = {}   # athleteId → row (merged across passing/rushing/receiving)

        def ensure(a):
            aid = a["athlete"]["id"]
            if aid not in rows:
                rows[aid] = {"name": a["athlete"]["displayName"],
                             "pos": (a["athlete"].get("position") or {}).get("abbreviation"),
                             "team": team_code(ab)}
            return rows[aid]

        pl, pa = _cat(stats, "passing")
        for a in pa:
            v = dict(zip(pl, a.get("stats", [])))
            r = ensure(a)
            ca = str(v.get("C/ATT", "")).split("/")
            if len(ca) == 2:
                r["cmp"], r["att"] = _num(ca[0]), _num(ca[1])
            r["pyds"], r["ptds"], r["ints"] = _num(v.get("YDS")), _num(v.get("TD")), _num(v.get("INT"))

        rl, ra = _cat(stats, "rushing")
        for a in ra:
            v = dict(zip(rl, a.get("stats", []))); r = ensure(a)
            r["car"], r["ryds"], r["rtds"] = _num(v.get("CAR")), _num(v.get("YDS")), _num(v.get("TD"))

        cl, cra = _cat(stats, "receiving")
        for a in cra:
            v = dict(zip(cl, a.get("stats", []))); r = ensure(a)
            r["rec"], r["recyds"], r["rectds"] = _num(v.get("REC")), _num(v.get("YDS")), _num(v.get("TD"))

        for r in rows.values():
            nm = r.pop("name"); pos = r.pop("pos"); team = r.pop("team")
            # keep only real stat cols (drop None), then stamp the game row
            wkrow = {k: v for k, v in r.items() if v is not None}
            if not wkrow:
                continue
            wkrow["wk"] = week
            if opp: wkrow["opp"] = opp
            wkrow["src"] = "espn"
            ent = out.get(nm)
            if ent is None:
                out[nm] = {"name": nm, "pos": pos, "team": team, "weeks": [wkrow]}
            elif not any(w.get("wk") == week for w in ent["weeks"]):
                ent["weeks"].append(wkrow)
            added += 1
    return added


def main():
    tw = target_week()
    if not tw:
        return
    season, week, st = tw
    try:
        sb = _get(f"{SB_URL}?dates={season}&seasontype={st}&week={week}")
    except Exception as e:
        print(f"[espn-box] scoreboard {season} wk{week} st{st} failed ({e}); aborting"); return
    events = sb.get("events", [])
    out = {}
    finals = 0
    for ev in events:
        n = parse_event(ev, out, season, week)
        if n: finals += 1
    path = os.path.join(DATA, f"espn_player_stats_{season}.json")
    if not out:
        print(f"[espn-box] {season} wk{week}: no final games with box scores yet; leaving overlay as-is")
        return
    with open(path, "w") as f:
        json.dump(out, f, separators=(",", ":"), sort_keys=True)
    print(f"[espn-box] wrote {os.path.basename(path)}: {len(out)} players from {finals} final game(s), wk{week}")


if __name__ == "__main__":
    main()
