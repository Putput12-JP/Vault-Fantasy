#!/usr/bin/env python3
"""
Build ADP JSON files from FantasyFootballCalculator's free REST API.

Generates 24 files: 6 formats × 4 team sizes.
- Formats: standard, ppr, half-ppr, 2qb (superflex), dynasty (startup), rookie
- Team sizes: 8, 10, 12, 14
- Output: data/adp_{format}_{teams}team.json

USAGE:
  python3 scripts/build_adp_data.py --all
  python3 scripts/build_adp_data.py --format ppr --teams 12
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

API_BASE = "https://fantasyfootballcalculator.com/api/v1/adp"
CURRENT_YEAR = 2026

# (frontend_label, ffc_endpoint, output_basename)
FORMATS = {
    'standard':  ('Standard',         'standard',  'standard'),
    'ppr':       ('PPR',              'ppr',       'ppr'),
    'halfppr':   ('Half-PPR',         'half-ppr',  'halfppr'),
    'superflex': ('Superflex / 2QB',  '2qb',       'superflex'),
    'dynasty':   ('Dynasty Startup',  'dynasty',   'dynasty'),
    'rookie':    ('Dynasty Rookie',   'rookie',    'rookie'),
}

TEAM_SIZES = [8, 10, 12, 14]

USER_AGENT = "Vault-Fantasy/1.0 (+https://putput12-jp.github.io/Vault-Fantasy)"


def fetch_adp(ffc_format, teams, year=CURRENT_YEAR, timeout=60):
    """Fetch ADP data from FFC for a specific format + team size."""
    url = f"{API_BASE}/{ffc_format}?teams={teams}&year={year}"
    print(f"  GET {url}", flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def normalize_name(name):
    """Normalize player name for matching (lowercase, alphanumeric only)."""
    return ''.join(c.lower() for c in name if c.isalnum())


def transform(raw, frontend_label, ffc_format, teams):
    """Convert FFC payload into Vault-friendly schema."""
    players = raw.get('players', [])
    transformed = []
    name_index = {}  # normalized name → ADP value, for fast lookup
    for p in players:
        name = p.get('name', '').strip()
        if not name:
            continue
        adp_val = p.get('adp')
        if adp_val is None:
            continue
        entry = {
            'name': name,
            'pos': p.get('position', ''),
            'team': p.get('team', ''),
            'adp': float(adp_val),
            'adp_hi': p.get('high'),
            'adp_lo': p.get('low'),
            'stdev': p.get('stdev'),
            'times_drafted': p.get('times_drafted'),
            'bye': p.get('bye'),
        }
        transformed.append(entry)
        name_index[normalize_name(name)] = float(adp_val)
    # Sort by ADP ascending (lower ADP = earlier pick = "better")
    transformed.sort(key=lambda x: x['adp'])
    return {
        'format': ffc_format,
        'format_label': frontend_label,
        'teams': teams,
        'year': raw.get('meta', {}).get('year', CURRENT_YEAR),
        'total_drafts': raw.get('meta', {}).get('total_drafts'),
        'fetched_at': raw.get('meta', {}).get('updated'),
        'source': 'fantasyfootballcalculator.com',
        'count': len(transformed),
        'players': transformed,
        'name_to_adp': name_index,
    }


def build_one(format_key, teams, out_dir, year=CURRENT_YEAR):
    """Build a single ADP file for one format + team size."""
    if format_key not in FORMATS:
        raise ValueError(f"Unknown format: {format_key}")
    label, ffc_endpoint, basename = FORMATS[format_key]
    out_path = os.path.join(out_dir, f'adp_{basename}_{teams}team.json')
    print(f"\n[{format_key} · {teams}-team]", flush=True)
    try:
        raw = fetch_adp(ffc_endpoint, teams, year=year)
    except urllib.error.HTTPError as e:
        # 404 means this combo isn't published (e.g. some formats only have 12-team)
        if e.code == 404:
            print(f"  → SKIP (404 - combo not published)", flush=True)
            return ('skip', 0)
        raise
    transformed = transform(raw, label, ffc_endpoint, teams)
    if not transformed['players']:
        print(f"  → SKIP (empty player list)", flush=True)
        return ('skip', 0)
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(transformed, f, separators=(',', ':'))
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  → {out_path} · {transformed['count']} players · {size_kb:.1f} KB", flush=True)
    return ('ok', size_kb)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--all', action='store_true',
                   help='Build all 24 combos (6 formats × 4 team sizes)')
    p.add_argument('--format', choices=list(FORMATS.keys()),
                   help='Specific format to build')
    p.add_argument('--teams', type=int, choices=TEAM_SIZES,
                   help='Specific team size')
    p.add_argument('--year', type=int, default=CURRENT_YEAR,
                   help=f'Year to fetch (default: {CURRENT_YEAR})')
    p.add_argument('--out-dir', default='data',
                   help='Output directory (default: data)')
    p.add_argument('--sleep', type=float, default=1.5,
                   help='Seconds to wait between requests (default: 1.5)')
    args = p.parse_args()

    if not args.all and not args.format:
        print("ERROR: specify --all or --format FORMAT", file=sys.stderr)
        sys.exit(1)

    combos = []
    if args.all:
        for fk in FORMATS:
            for t in TEAM_SIZES:
                combos.append((fk, t))
    elif args.format and args.teams:
        combos.append((args.format, args.teams))
    elif args.format:
        for t in TEAM_SIZES:
            combos.append((args.format, t))

    results = []
    for fk, teams in combos:
        try:
            status, size = build_one(fk, teams, args.out_dir, year=args.year)
            results.append((fk, teams, status, size))
        except Exception as e:
            print(f"  → ERROR: {e}", file=sys.stderr, flush=True)
            results.append((fk, teams, 'err', 0))
        time.sleep(args.sleep)  # Be polite to FFC

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Format':<12}{'Teams':<8}{'Status':<10}{'KB':<8}")
    total_kb = 0
    ok_count = 0
    for fk, teams, status, kb in results:
        marker = '✓' if status == 'ok' else ('-' if status == 'skip' else '✗')
        print(f"{fk:<12}{teams:<8}{marker} {status:<8}{kb:<8.1f}")
        total_kb += kb
        if status == 'ok':
            ok_count += 1
    print(f"\nGenerated {ok_count}/{len(results)} files · {total_kb:.1f} KB total")

    if any(r[2] == 'err' for r in results):
        sys.exit(1)


if __name__ == '__main__':
    main()
