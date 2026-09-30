#!/usr/bin/env python3
"""
NBA box scores + schedules from sportsdataverse (hoopR) GitHub releases.

The NBA equivalent of nflverse: ESPN-sourced player box, team box, schedule
and game rosters, one CSV per season, rebuilt daily in-season. No auth, works
from GitHub Actions (unlike stats.nba.com, which blocks cloud IPs).

Season label = the year the season ENDS (2026 = the 2025-26 season).

  python3 nba/scripts/fetch_hoopr.py                 # default seasons
  python3 nba/scripts/fetch_hoopr.py 2024 2025 2026  # explicit
  python3 nba/scripts/fetch_hoopr.py --pbp 2026      # also play-by-play (~280 MB/season)

Writes nba/raw/hoopr/<kind>_<season>.csv (raw/ is gitignored).
"""
import os, sys, urllib.request

BASE = 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download'
KINDS = {
    'player_box':   ('espn_nba_player_boxscores', 'player_box_{s}.csv'),
    'team_box':     ('espn_nba_team_boxscores',   'team_box_{s}.csv'),
    'schedule':     ('espn_nba_schedules',        'nba_schedule_{s}.csv'),
    'game_rosters': ('espn_nba_game_rosters',     'game_rosters_{s}.csv'),
}
PBP = ('espn_nba_pbp', 'play_by_play_{s}.csv')
DEFAULT_SEASONS = [2022, 2023, 2024, 2025, 2026]  # 2022-25 = priors, 2025/2026 = backtest seasons

OUT = os.path.join(os.path.dirname(__file__), '..', 'raw', 'hoopr')


def download(tag, name, dest, force=False):
    if os.path.exists(dest) and not force:
        return 'cached'
    url = f'{BASE}/{tag}/{name}'
    tmp = dest + '.part'
    req = urllib.request.Request(url, headers={'User-Agent': 'vault-nba'})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, 'wb') as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(tmp, dest)
    return 'ok'


def main(argv):
    pbp = '--pbp' in argv
    force = '--force' in argv
    seasons = [int(a) for a in argv if a.isdigit()] or DEFAULT_SEASONS
    os.makedirs(OUT, exist_ok=True)
    kinds = dict(KINDS)
    if pbp:
        kinds['pbp'] = PBP
    for s in seasons:
        for kind, (tag, pat) in kinds.items():
            name = pat.format(s=s)
            dest = os.path.join(OUT, f'{kind}_{s}.csv')
            # The current season's files change daily; always refresh it.
            try:
                st = download(tag, name, dest, force=force or s == max(seasons))
                print(f'{kind:13s} {s}  {st}  {os.path.getsize(dest) // 1000:>8,} KB')
            except Exception as e:
                print(f'{kind:13s} {s}  FAILED  {e}')


if __name__ == '__main__':
    main(sys.argv[1:])
