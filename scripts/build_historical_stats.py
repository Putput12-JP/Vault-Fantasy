#!/usr/bin/env python3
"""
Build historical nflverse JSON files matching Vault's 2025 schema.

USAGE:
  # One-time build of all historical years (1999-2024):
  python3 scripts/build_historical_stats.py --all

  # Refresh just current year (for the nightly GitHub Action):
  python3 scripts/build_historical_stats.py --year 2025

  # Specific years:
  python3 scripts/build_historical_stats.py --year 2005 --year 2006

Output files are written to data/nflverse_stats_{year}.json
"""
import argparse
import csv
import gzip
import io
import json
import os
import sys
import urllib.request

ALL_YEARS = list(range(1999, 2026))
URL_TEMPLATE = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{year}.csv.gz"
SKILL_POSITIONS = {'QB', 'RB', 'WR', 'TE', 'FB'}

def num(row, k, default=0):
    v = row.get(k)
    if v is None or v == '' or v == 'NA':
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default

def calc_fantasy_pts(row):
    """PPR scoring: 0.04/pyd, 4/pTD, -2/INT, 0.1/ryd, 6/rTD, 1/rec, 0.1/recYd, 6/recTD, -2/fumble"""
    pts = 0
    pts += num(row, 'passing_yards') * 0.04
    pts += num(row, 'passing_tds') * 4
    pts -= num(row, 'passing_interceptions') * 2
    pts += num(row, 'rushing_yards') * 0.1
    pts += num(row, 'rushing_tds') * 6
    pts += num(row, 'receptions') * 1
    pts += num(row, 'receiving_yards') * 0.1
    pts += num(row, 'receiving_tds') * 6
    pts -= num(row, 'rushing_fumbles_lost') * 2
    pts -= num(row, 'receiving_fumbles_lost') * 2
    pts -= num(row, 'sack_fumbles_lost') * 2
    pts += num(row, 'passing_2pt_conversions') * 2
    pts += num(row, 'rushing_2pt_conversions') * 2
    pts += num(row, 'receiving_2pt_conversions') * 2
    return round(pts, 2)

def fetch_year_csv(year):
    url = URL_TEMPLATE.format(year=year)
    print(f"  Fetching {url}...", flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'Vault-Fantasy/1.0'})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    decompressed = gzip.decompress(data)
    text = decompressed.decode('utf-8')
    return list(csv.DictReader(io.StringIO(text)))

def transform_year(year, rows):
    players = {}
    for row in rows:
        if row.get('season_type', '') != 'REG':
            continue
        name = row.get('player_display_name') or row.get('player_name') or ''
        if not name:
            continue
        pos = row.get('position') or ''
        if pos not in SKILL_POSITIONS:
            continue
        team = row.get('team') or row.get('recent_team') or ''
        opp = row.get('opponent_team') or ''
        wk = int(num(row, 'week', 0))
        if wk == 0:
            continue

        pts = calc_fantasy_pts(row)
        week_entry = {'wk': wk, 'pts': round(pts, 2), 'opp': opp}

        if num(row, 'attempts') > 0:
            week_entry['cmp'] = int(num(row, 'completions'))
            week_entry['att'] = int(num(row, 'attempts'))
            week_entry['pyds'] = int(num(row, 'passing_yards'))
            week_entry['ptds'] = int(num(row, 'passing_tds'))
            ints_val = num(row, 'passing_interceptions', None)
            week_entry['ints'] = int(ints_val) if ints_val else None
        if num(row, 'carries') > 0:
            week_entry['car'] = int(num(row, 'carries'))
            week_entry['ryds'] = int(num(row, 'rushing_yards'))
            rtds = num(row, 'rushing_tds')
            if rtds > 0:
                week_entry['rtds'] = int(rtds)
        if num(row, 'targets') > 0 or num(row, 'receptions') > 0:
            week_entry['tgt'] = int(num(row, 'targets'))
            week_entry['rec'] = int(num(row, 'receptions'))
            week_entry['reyds'] = int(num(row, 'receiving_yards'))
            retds = num(row, 'receiving_tds')
            if retds > 0:
                week_entry['retds'] = int(retds)

        if name not in players:
            players[name] = {
                'name': name,
                'pos': pos,
                'team': team,
                'headshot': row.get('headshot_url', '') or '',
                'weeks': [],
                'season': {},
            }
        players[name]['weeks'].append(week_entry)
        if team:
            players[name]['team'] = team

    # Aggregate
    for name, p in players.items():
        weeks = sorted(p['weeks'], key=lambda w: w['wk'])
        p['weeks'] = weeks
        games = len(weeks)
        if games == 0:
            continue
        total_pts = sum(w.get('pts', 0) for w in weeks)
        total_pyds = sum(w.get('pyds', 0) for w in weeks)
        total_ptds = sum(w.get('ptds', 0) for w in weeks)
        total_ints = sum((w.get('ints') or 0) for w in weeks)
        total_ryds = sum(w.get('ryds', 0) for w in weeks)
        total_rtds = sum(w.get('rtds', 0) for w in weeks)
        total_rec = sum(w.get('rec', 0) for w in weeks)
        total_reyds = sum(w.get('reyds', 0) for w in weeks)
        total_retds = sum(w.get('retds', 0) for w in weeks)
        total_tgt = sum(w.get('tgt', 0) for w in weeks)
        total_car = sum(w.get('car', 0) for w in weeks)

        season = {
            'games': games,
            'avg_pts': round(total_pts / games, 2),
            'total_pts': round(total_pts, 2),
        }
        if total_pyds > 0:
            season['avg_pyds'] = round(total_pyds / games, 1)
            season['avg_ptds'] = round(total_ptds / games, 2)
            season['total_ints'] = int(total_ints)
        if total_ryds > 0:
            season['avg_ryds'] = round(total_ryds / games, 1)
            season['total_rtds'] = int(total_rtds)
        if total_rec > 0:
            season['avg_rec'] = round(total_rec / games, 1)
            season['total_reyds'] = int(total_reyds)
            season['total_retds'] = int(total_retds)
            season['total_tgt'] = int(total_tgt)
        if total_car > 0:
            season['total_car'] = int(total_car)
        p['season'] = season

        last4 = weeks[-4:]
        if last4:
            p['l4w_avg'] = round(sum(w.get('pts', 0) for w in last4) / len(last4), 1)
    return players

def process_year(year, out_dir):
    out_path = os.path.join(out_dir, f'nflverse_stats_{year}.json')
    print(f"\n[{year}] Processing...", flush=True)
    rows = fetch_year_csv(year)
    print(f"  Got {len(rows)} rows", flush=True)
    players = transform_year(year, rows)
    print(f"  Transformed to {len(players)} players", flush=True)
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(players, f, separators=(',', ':'))
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  → {out_path} ({size_kb:.1f} KB)", flush=True)
    return len(players), size_kb

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true', help='Build all years 1999-2024 (historical)')
    parser.add_argument('--year', type=int, action='append', help='Specific year(s) to build')
    parser.add_argument('--out-dir', default='data', help='Output directory (default: data)')
    args = parser.parse_args()

    if args.all:
        years = list(range(1999, 2025))  # 1999-2024 only; 2025 is the live year handled by nightly action
    elif args.year:
        years = args.year
    else:
        print("ERROR: specify --all or --year YEAR", file=sys.stderr)
        sys.exit(1)

    summary = []
    for year in years:
        try:
            count, kb = process_year(year, args.out_dir)
            summary.append((year, count, int(kb), 'OK'))
        except Exception as e:
            print(f"  ERROR {year}: {e}", file=sys.stderr, flush=True)
            summary.append((year, 0, 0, f'ERR: {e}'))

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"{'Year':<8}{'Players':<10}{'Size KB':<10}{'Status':<20}")
    for year, count, kb, status in summary:
        print(f"{year:<8}{count:<10}{kb:<10}{status:<20}")
    total_kb = sum(s[2] for s in summary)
    print(f"{'TOTAL':<8}{'':<10}{total_kb:<10}")
    
    # Exit non-zero if any year failed
    if any(s[3] != 'OK' for s in summary):
        sys.exit(1)

if __name__ == '__main__':
    main()
