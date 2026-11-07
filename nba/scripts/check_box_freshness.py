#!/usr/bin/env python3
"""Box score gap check. Lists every finished game that has no rows in player_box yet, so a feed that lags the daily refresh is named in
the run log instead of showing up as a missing game on the page. Exits 0 either way (the refresh still publishes what it has); the later
cron runs fill the gap.

"Finished" comes from two places: hoopR's own schedule, and ESPN's live scoreboard for the last few days. The schedule alone cannot see a
gap when the whole hoopR release is a day behind (its schedule is as stale as its box scores), which is how the Nov 6 games passed this
check on the Nov 7 morning run while the page had none of them.

  check_box_freshness.py [season] [--days=3]"""
import csv, datetime as dt, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_espn_box import ET, finished_games

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'raw', 'hoopr')


def main(argv):
    args = dict(a.lstrip('-').split('=', 1) for a in argv if '=' in a)
    pos = [a for a in argv if a.isdigit()]
    today = dt.datetime.now(ET).date()
    s = pos[0] if pos else str(today.year + 1 if today.month >= 8 else today.year)
    have = {r['game_id'] for r in csv.DictReader(open(os.path.join(RAW, f'player_box_{s}.csv'))) if r['game_id']}
    miss = {r['id']: f"{r['game_date'] or r['date'][:10]} {r['away_abbreviation']}@{r['home_abbreviation']}"
            for r in csv.DictReader(open(os.path.join(RAW, f'schedule_{s}.csv')))
            if r['status_type_completed'] == 'true' and r['id'] not in have}
    for back in range(int(args.get('days', 3)), -1, -1):
        day = today - dt.timedelta(days=back)
        try:
            for gid, yr, _ in finished_games(day):
                if str(yr) == s and gid not in have:
                    miss.setdefault(gid, f'{day} game {gid}')
        except Exception as e:
            print(f'::warning::ESPN scoreboard for {day} could not be read ({e}); checked against the hoopR schedule only')
    if not miss:
        print('Box scores complete for every finished game.')
        return
    print(f'::warning::{len(miss)} finished game(s) have no box score yet: ' + ', '.join(sorted(miss.values())[:12]))


if __name__ == '__main__':
    main(sys.argv[1:])
