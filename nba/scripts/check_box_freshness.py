#!/usr/bin/env python3
"""Box score gap check. Lists every game the schedule marks completed that has no rows in player_box yet, so a feed that lags
the daily refresh is named in the run log instead of showing up as a missing game on the page. Exits 0 either way (the refresh still
publishes what it has); the later cron runs fill the gap. Usage: check_box_freshness.py [season]"""
import csv, os, sys

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'raw', 'hoopr')


def main(argv):
    s = argv[0] if argv else None
    if not s:
        import datetime as dt
        t = dt.datetime.now(dt.timezone.utc)
        s = str(t.year + 1 if t.month >= 8 else t.year)
    have = {r['game_id'] for r in csv.DictReader(open(os.path.join(RAW, f'player_box_{s}.csv'))) if r['game_id']}
    miss = [(r['date'][:10], r['away_abbreviation'], r['home_abbreviation']) for r in csv.DictReader(open(os.path.join(RAW, f'schedule_{s}.csv')))
            if r['status_type_completed'] == 'true' and r['id'] not in have]
    if not miss:
        print('Box scores complete for every finished game.')
        return
    print(f'::warning::{len(miss)} finished game(s) have no box score yet: ' + ', '.join(f'{d} {a}@{h}' for d, a, h in sorted(miss)[:12]))


if __name__ == '__main__':
    main(sys.argv[1:])
