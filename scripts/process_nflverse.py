"""
process_nflverse.py  —  Vault Fantasy nflverse data pipeline
Pulls nflverse player_stats + snap_counts CSVs and writes compact JSON.
Run daily via GitHub Actions, or manually: python scripts/process_nflverse.py

Output files (all written to /data/):
  nflverse_stats.json          current season (2025), used as default
  nflverse_snaps.json          current season snaps
  nflverse_stats_2025.json     explicit 2025 copy
  nflverse_snaps_2025.json     explicit 2025 snaps
  nflverse_stats_2024.json     2024 archive
  nflverse_snaps_2024.json     2024 archive snaps
  nflverse_injuries.json       latest injury statuses
  nflverse_meta.json           metadata / timestamps
"""
import requests, csv, json, os, io
from datetime import datetime, timezone
from collections import defaultdict

CURRENT_SEASON = 2025
ARCHIVE_SEASON = 2024
BASE_URL = "https://github.com/nflverse/nflverse-data/releases/download"

def season_urls(season):
    return {
        "player_stats": f"{BASE_URL}/player_stats/player_stats_{season}.csv",
        "snap_counts":  f"{BASE_URL}/snap_counts/snap_counts_{season}.csv",
        "injuries":     f"{BASE_URL}/injuries/injuries_{season}.csv",
    }

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
HEADERS = {"User-Agent": "VaultFantasy/2.0"}
POSITIONS = {"QB", "RB", "WR", "TE", "FB"}

def fetch_csv(url, label):
    print(f"  Fetching {label}...")
    r = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=90)
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))
    print(f"    -> {len(rows):,} rows")
    return rows

def sf(val, default=None):
    try:
        f = float(val)
        return None if f != f else round(f, 4)
    except (ValueError, TypeError):
        return default

def si(val, default=None):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

def pct(val):
    f = sf(val)
    return None if f is None else round(f * 100, 1)

def process_stats(rows):
    players = {}
    for row in rows:
        name = row.get("player_display_name") or row.get("player_name", "")
        if not name: continue
        pos = (row.get("position") or "?").upper()
        if pos not in POSITIONS and pos != "?": continue
        week = si(row.get("week"))
        if not week or week < 1 or week > 22: continue
        if row.get("season_type", "REG") not in ("REG", "regular"): continue
        if name not in players:
            players[name] = {"name": name, "pos": pos, "team": row.get("recent_team", ""),
                             "headshot": row.get("headshot_url", ""), "weeks": [],
                             "_acc": defaultdict(float), "_g": 0}
        p = players[name]
        if row.get("recent_team"): p["team"] = row["recent_team"]
        if pos != "?": p["pos"] = pos
        pts = sf(row.get("fantasy_points_ppr"), 0)
        wk = {"wk": week, "pts": round(pts, 1)}
        if pos == "QB":
            wk.update({"cmp": si(row.get("completions")), "att": si(row.get("attempts")),
                       "pyds": si(row.get("passing_yards")), "ptds": si(row.get("passing_tds")),
                       "ints": si(row.get("interceptions")), "ryds": si(row.get("rushing_yards")),
                       "car": si(row.get("carries")), "pepa": sf(row.get("passing_epa"))})
            for k, f2 in [("pyds","passing_yards"),("ptds","passing_tds"),("ints","interceptions"),
                          ("ryds","rushing_yards")]:
                p["_acc"][k] += sf(row.get(f2), 0)
            p["_acc"]["pepa"] += sf(row.get("passing_epa"), 0)
        elif pos == "RB":
            wk.update({"car": si(row.get("carries")), "ryds": si(row.get("rushing_yards")),
                       "rtds": si(row.get("rushing_tds")), "tgt": si(row.get("targets")),
                       "rec": si(row.get("receptions")), "recyds": si(row.get("receiving_yards")),
                       "ts": pct(row.get("target_share"))})
            for k, f2 in [("car","carries"),("ryds","rushing_yards"),("tgt","targets")]:
                p["_acc"][k] += sf(row.get(f2), 0)
        else:
            wk.update({"tgt": si(row.get("targets")), "rec": si(row.get("receptions")),
                       "recyds": si(row.get("receiving_yards")), "rectds": si(row.get("receiving_tds")),
                       "ts": pct(row.get("target_share")), "ays": pct(row.get("air_yards_share")),
                       "wopr": sf(row.get("wopr")), "racr": sf(row.get("racr")),
                       "ayds": si(row.get("receiving_air_yards"))})
            for k, f2 in [("tgt","targets"),("rec","receptions"),("recyds","receiving_yards")]:
                p["_acc"][k] += sf(row.get(f2), 0)
        p["_acc"]["pts"] += pts
        p["_acc"]["games"] += 1
        p["weeks"].append(wk)
        p["_g"] += 1
    result = {}
    for name, p in players.items():
        if not p["_g"]: continue
        g = p["_g"]; acc = p["_acc"]
        ssn = {"games": g, "avg_pts": round(acc["pts"]/g, 2), "total_pts": round(acc["pts"], 1)}
        pos = p["pos"]
        if pos == "QB":
            ssn.update({"avg_pyds": round(acc["pyds"]/g,1), "avg_ptds": round(acc["ptds"]/g,2),
                        "total_ints": int(acc["ints"]), "avg_ryds": round(acc["ryds"]/g,1),
                        "avg_pepa": round(acc["pepa"]/g,3)})
        elif pos == "RB":
            ssn.update({"avg_car": round(acc["car"]/g,1), "avg_ryds": round(acc["ryds"]/g,1),
                        "avg_tgt": round(acc["tgt"]/g,1)})
        else:
            ssn.update({"avg_tgt": round(acc["tgt"]/g,1), "avg_rec": round(acc["rec"]/g,1),
                        "avg_recyds": round(acc["recyds"]/g,1)})
            for key, field in [("avg_ts","ts"),("avg_ays","ays"),("avg_wopr","wopr"),("avg_racr","racr")]:
                vals = [w.get(field) for w in p["weeks"] if w.get(field) is not None]
                if vals: ssn[key] = round(sum(vals)/len(vals), 3 if "wopr" in key or "racr" in key else 1)
        sw = sorted(p["weeks"], key=lambda w: w["wk"])
        l4 = sw[-4:] if len(sw) >= 4 else sw
        l4avg = round(sum(w["pts"] for w in l4)/len(l4), 2) if l4 else 0
        result[name] = {"name":name,"pos":pos,"team":p["team"],"headshot":p["headshot"],
                        "l4w_avg":l4avg,"season":ssn,"weeks":sw}
    print(f"    -> {len(result)} players")
    return result

def process_snaps(rows):
    players = {}
    for row in rows:
        name = (row.get("player") or "").strip()
        if not name: continue
        pos = (row.get("position") or "?").upper()
        if pos not in POSITIONS and pos != "?": continue
        week = si(row.get("week"))
        if week is None: continue
        off = sf(row.get("offense_pct"))
        if off is None: continue
        if name not in players: players[name] = {"weeks":[], "_off":[]}
        players[name]["weeks"].append({"wk":week,"off":round(off*100,1)})
        players[name]["_off"].append(off)
    return {n:{"avg_off":round(sum(p["_off"])/len(p["_off"])*100,1) if p["_off"] else None,
               "weeks":sorted(p["weeks"],key=lambda w:w["wk"])}
            for n,p in players.items()}

def process_injuries(rows):
    players = {}
    for row in rows:
        name = (row.get("full_name") or row.get("player_name") or "").strip()
        if not name: continue
        week = si(row.get("week"), 0)
        ex = players.get(name, {})
        if week >= ex.get("_wk", 0):
            players[name] = {"_wk":week,"status":row.get("report_status") or "",
                             "designation":row.get("report_primary_injury") or ""}
    return {n:{k:v for k,v in d.items() if not k.startswith("_")} for n,d in players.items()}

def run_season(season):
    urls = season_urls(season)
    stats, snaps, inj = {}, {}, {}
    try: stats = process_stats(fetch_csv(urls["player_stats"], f"player_stats_{season}"))
    except Exception as e: print(f"  WARN stats {season}: {e}")
    try: snaps = process_snaps(fetch_csv(urls["snap_counts"], f"snap_counts_{season}"))
    except Exception as e: print(f"  WARN snaps {season}: {e}")
    try: inj = process_injuries(fetch_csv(urls["injuries"], f"injuries_{season}"))
    except Exception as e: print(f"  WARN inj {season}: {e}")
    return stats, snaps, inj

def write(data, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f: json.dump(data, f, separators=(",",":"))
    print(f"  {filename}  ({os.path.getsize(path)//1024}KB,  {len(data)} entries)")

def main():
    now = datetime.now(timezone.utc).isoformat()
    print(f"\n=== Vault nflverse pipeline  {now[:10]} ===")
    print(f"\n--- Season {CURRENT_SEASON} (current) ---")
    cur_stats, cur_snaps, cur_inj = run_season(CURRENT_SEASON)
    print(f"\n--- Season {ARCHIVE_SEASON} (archive) ---")
    arc_stats, arc_snaps, _ = run_season(ARCHIVE_SEASON)
    print("\n--- Writing files ---")
    write(cur_stats, "nflverse_stats.json")
    write(cur_snaps, "nflverse_snaps.json")
    write(cur_inj,   "nflverse_injuries.json")
    write(cur_stats, f"nflverse_stats_{CURRENT_SEASON}.json")
    write(cur_snaps, f"nflverse_snaps_{CURRENT_SEASON}.json")
    write(arc_stats, f"nflverse_stats_{ARCHIVE_SEASON}.json")
    write(arc_snaps, f"nflverse_snaps_{ARCHIVE_SEASON}.json")
    meta = {"updated_at":now,"current_season":CURRENT_SEASON,"season":CURRENT_SEASON,
            "player_count":len(cur_stats),"snap_count":len(cur_snaps),
            "archive_season":ARCHIVE_SEASON,"archive_player_count":len(arc_stats)}
    with open(os.path.join(OUTPUT_DIR,"nflverse_meta.json"),"w") as f: json.dump(meta,f,indent=2)
    print(f"  nflverse_meta.json")
    print(f"\n Done  {CURRENT_SEASON}: {len(cur_stats)} players | {ARCHIVE_SEASON}: {len(arc_stats)} players")

if __name__ == "__main__":
    main()
