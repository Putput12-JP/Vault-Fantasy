"""
process_nflverse.py
Downloads nflverse player_stats and snap_counts CSVs from GitHub releases,
processes them into compact JSON files served via GitHub Pages.
Run automatically by GitHub Actions daily at 6am UTC.
"""
import requests, csv, json, os, io
from datetime import datetime, timezone
from collections import defaultdict

CURRENT_SEASON = 2024
BASE_URL = "https://github.com/nflverse/nflverse-data/releases/download"
URLS = {
    "player_stats": f"{BASE_URL}/player_stats/player_stats_{CURRENT_SEASON}.csv",
    "snap_counts":  f"{BASE_URL}/snap_counts/snap_counts_{CURRENT_SEASON}.csv",
    "injuries":     f"{BASE_URL}/injuries/injuries_{CURRENT_SEASON}.csv",
}
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
HEADERS = {"User-Agent": "VaultFantasy/1.0"}
INCLUDE_POSITIONS = {"QB", "RB", "WR", "TE", "FB"}

def fetch_csv(url, label):
    print(f"  Fetching {label}...")
    r = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=60)
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))
    print(f"    -> {len(rows):,} rows")
    return rows

def safe_float(val, default=None):
    try:
        f = float(val)
        return None if f != f else round(f, 4)
    except (ValueError, TypeError):
        return default

def safe_int(val, default=None):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

def pct_fmt(val):
    f = safe_float(val)
    return None if f is None else round(f * 100, 1)

def process_player_stats(rows):
    players = {}
    for row in rows:
        name = row.get("player_display_name") or row.get("player_name", "")
        if not name: continue
        pos = (row.get("position") or "?").upper()
        if pos not in INCLUDE_POSITIONS and pos != "?": continue
        week = safe_int(row.get("week"))
        if not week or week < 1 or week > 22: continue
        if row.get("season_type", "REG") not in ("REG", "regular"): continue
        if name not in players:
            players[name] = {"name": name, "pos": pos, "team": row.get("recent_team", ""),
                             "headshot": row.get("headshot_url", ""), "weeks": [], "_acc": defaultdict(float), "_g": 0}
        p = players[name]
        if row.get("recent_team"): p["team"] = row["recent_team"]
        if pos != "?": p["pos"] = pos
        pts = safe_float(row.get("fantasy_points_ppr"), 0)
        wk = {"wk": week, "pts": round(pts, 1)}
        if pos == "QB":
            wk.update({"cmp": safe_int(row.get("completions")), "att": safe_int(row.get("attempts")),
                       "pyds": safe_int(row.get("passing_yards")), "ptds": safe_int(row.get("passing_tds")),
                       "ints": safe_int(row.get("interceptions")), "ryds": safe_int(row.get("rushing_yards")),
                       "car": safe_int(row.get("carries")), "pepa": safe_float(row.get("passing_epa")),
                       "dakota": safe_float(row.get("dakota")), "pacr": safe_float(row.get("pacr"))})
            p["_acc"]["pyds"] += safe_float(row.get("passing_yards"), 0)
            p["_acc"]["ptds"] += safe_float(row.get("passing_tds"), 0)
            p["_acc"]["ints"] += safe_float(row.get("interceptions"), 0)
            p["_acc"]["ryds"] += safe_float(row.get("rushing_yards"), 0)
            p["_acc"]["pepa"] += safe_float(row.get("passing_epa"), 0)
        elif pos == "RB":
            wk.update({"car": safe_int(row.get("carries")), "ryds": safe_int(row.get("rushing_yards")),
                       "rtds": safe_int(row.get("rushing_tds")), "tgt": safe_int(row.get("targets")),
                       "rec": safe_int(row.get("receptions")), "recyds": safe_int(row.get("receiving_yards")),
                       "ts": pct_fmt(row.get("target_share"))})
            p["_acc"]["car"] += safe_float(row.get("carries"), 0)
            p["_acc"]["ryds"] += safe_float(row.get("rushing_yards"), 0)
            p["_acc"]["tgt"] += safe_float(row.get("targets"), 0)
        else:
            wk.update({"tgt": safe_int(row.get("targets")), "rec": safe_int(row.get("receptions")),
                       "recyds": safe_int(row.get("receiving_yards")), "rectds": safe_int(row.get("receiving_tds")),
                       "ts": pct_fmt(row.get("target_share")), "ays": pct_fmt(row.get("air_yards_share")),
                       "wopr": safe_float(row.get("wopr")), "racr": safe_float(row.get("racr")),
                       "ayds": safe_int(row.get("receiving_air_yards"))})
            p["_acc"]["tgt"] += safe_float(row.get("targets"), 0)
            p["_acc"]["rec"] += safe_float(row.get("receptions"), 0)
            p["_acc"]["recyds"] += safe_float(row.get("receiving_yards"), 0)
        p["_acc"]["pts"] += pts
        p["_acc"]["games"] += 1
        p["weeks"].append(wk)
        p["_g"] += 1

    result = {}
    for name, p in players.items():
        if not p["_g"]: continue
        g = p["_g"]; acc = p["_acc"]
        season = {"games": g, "avg_pts": round(acc["pts"]/g, 2), "total_pts": round(acc["pts"], 1)}
        pos = p["pos"]
        if pos == "QB":
            season.update({"avg_pyds": round(acc["pyds"]/g, 1), "avg_ptds": round(acc["ptds"]/g, 2),
                           "total_ints": int(acc["ints"]), "avg_ryds": round(acc["ryds"]/g, 1),
                           "avg_pepa": round(acc["pepa"]/g, 3)})
        elif pos == "RB":
            season.update({"avg_car": round(acc["car"]/g, 1), "avg_ryds": round(acc["ryds"]/g, 1),
                           "avg_tgt": round(acc["tgt"]/g, 1)})
        else:
            season.update({"avg_tgt": round(acc["tgt"]/g, 1), "avg_rec": round(acc["rec"]/g, 1),
                           "avg_recyds": round(acc["recyds"]/g, 1)})
            for key, field in [("avg_ts","ts"),("avg_ays","ays"),("avg_wopr","wopr"),("avg_racr","racr")]:
                vals = [w.get(field) for w in p["weeks"] if w.get(field) is not None]
                if vals: season[key] = round(sum(vals)/len(vals), 3 if "wopr" in field or "racr" in field else 1)
        sorted_wks = sorted(p["weeks"], key=lambda w: w["wk"])
        l4w = sorted_wks[-4:] if len(sorted_wks) >= 4 else sorted_wks
        l4w_avg = round(sum(w["pts"] for w in l4w)/len(l4w), 2) if l4w else 0
        result[name] = {"name": name, "pos": p["pos"], "team": p["team"], "headshot": p["headshot"],
                        "l4w_avg": l4w_avg, "season": season, "weeks": sorted_wks}
    print(f"    -> {len(result)} players processed")
    return result

def process_snap_counts(rows):
    players = {}
    for row in rows:
        name = row.get("player", "").strip()
        if not name: continue
        pos = (row.get("position") or "?").upper()
        if pos not in INCLUDE_POSITIONS and pos != "?": continue
        week = safe_int(row.get("week"))
        if week is None: continue
        off = safe_float(row.get("offense_pct"))
        df = safe_float(row.get("defense_pct"))
        if off is None and df is None: continue
        if name not in players: players[name] = {"weeks": [], "_off": [], "_def": []}
        players[name]["weeks"].append({"wk": week,
            "off": round(off*100,1) if off is not None else None,
            "def": round(df*100,1) if df is not None else None})
        if off is not None: players[name]["_off"].append(off)
        if df is not None: players[name]["_def"].append(df)
    result = {}
    for name, p in players.items():
        sw = sorted(p["weeks"], key=lambda w: w["wk"])
        result[name] = {"avg_off": round(sum(p["_off"])/len(p["_off"])*100,1) if p["_off"] else None,
                        "avg_def": round(sum(p["_def"])/len(p["_def"])*100,1) if p["_def"] else None,
                        "weeks": sw}
    print(f"    -> {len(result)} players with snap data")
    return result

def process_injuries(rows):
    players = {}
    for row in rows:
        name = (row.get("full_name") or row.get("player_name") or "").strip()
        if not name: continue
        week = safe_int(row.get("week"), 0)
        ex = players.get(name, {})
        if week >= ex.get("_wk", 0):
            players[name] = {"_wk": week, "status": row.get("report_status") or "",
                             "designation": row.get("report_primary_injury") or ""}
    return {n: {k:v for k,v in d.items() if not k.startswith("_")} for n, d in players.items()}

def main():
    now = datetime.now(timezone.utc).isoformat()
    print(f"Vault Fantasy nflverse update - {now}")
    stats = {}; snaps = {}; injuries = {}
    try: stats = process_player_stats(fetch_csv(URLS["player_stats"], "player_stats"))
    except Exception as e: print(f"  stats ERROR: {e}")
    try: snaps = process_snap_counts(fetch_csv(URLS["snap_counts"], "snap_counts"))
    except Exception as e: print(f"  snaps ERROR: {e}")
    try: injuries = process_injuries(fetch_csv(URLS["injuries"], "injuries"))
    except Exception as e: print(f"  injuries ERROR: {e}")
    for fname, data in [("nflverse_stats.json", stats), ("nflverse_snaps.json", snaps), ("nflverse_injuries.json", injuries)]:
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w") as f: json.dump(data, f, separators=(",",":"))
        print(f"  {fname} -> {os.path.getsize(path)//1024}KB")
    with open(os.path.join(OUTPUT_DIR, "nflverse_meta.json"), "w") as f:
        json.dump({"updated_at": now, "season": CURRENT_SEASON, "player_count": len(stats), "snap_count": len(snaps)}, f, indent=2)
    print(f"Done - {len(stats)} players, {now[:10]}")

if __name__ == "__main__":
    main()
