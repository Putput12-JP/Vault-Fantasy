#!/usr/bin/env python3
"""
Play-by-play -> stints (who was on the floor, for how long, what happened) from shufinskiy/nba_data (Apache-2.0).

Why: the model has no lineup information. Stints give (a) a free RAPM-style player-quality prior and (b) a
play-by-play garbage-time definition. See docs/reverse-engineering-targets.md.

Method
  * Rows are NBA stats play-by-play (EVENTMSGTYPE 1 make, 2 miss, 3 FT, 4 rebound, 5 turnover, 8 sub, 12 start).
  * Starters of each period are the players who act in the period before their first substitution-in
    (a player subbed OUT before acting is also a starter; handled by the sub rows).
  * A stint ends at any substitution time or period end. Points and possessions are tallied per stint.
  * Possessions = FGA - OREB + TOV + 0.44 FTA, per side (box-score estimate; fine for a ridge prior).

  python3 nba/scripts/build_pbp_stints.py PBP_CSV [PBP_CSV ...] --out nba/raw/stints_<tag>.csv
PBP_CSV is a nbastats_<year>.csv extracted from nba_data's datasets/nbastats_<year>.tar.xz.
Output columns: game_id, season, period, start_s, end_s, home_team, away_team, home5, away5,
                home_pts, away_pts, home_poss, away_poss
"""
import argparse, csv, os, sys
from collections import defaultdict

PERIOD_LEN = lambda p: 720 if p <= 4 else 300


def clock_s(pc, period):
    """Seconds elapsed in the game at a PCTIMESTRING like '11:43'."""
    m, s = pc.split(':')
    left = int(m) * 60 + int(s)
    base = sum(PERIOD_LEN(i) for i in range(1, period))
    return base + PERIOD_LEN(period) - left


def team_of(row, k):
    return row.get(f'PLAYER{k}_TEAM_ID') or ''


def parse_game(rows):
    """rows: list of dict for one game ordered by EVENTNUM. Yields stint dicts."""
    teams = {}                                   # team_id -> 'H'/'A' (home desc present => home)
    for r in rows:
        if r['HOMEDESCRIPTION'] and r['PLAYER1_TEAM_ID'] and r['EVENTMSGTYPE'] not in ('8',):
            teams.setdefault(r['PLAYER1_TEAM_ID'], 'H')
        elif r['VISITORDESCRIPTION'] and r['PLAYER1_TEAM_ID'] and r['EVENTMSGTYPE'] not in ('8',):
            teams.setdefault(r['PLAYER1_TEAM_ID'], 'A')
    home = [t for t, s in teams.items() if s == 'H']
    away = [t for t, s in teams.items() if s == 'A']
    if len(home) != 1 or len(away) != 1:
        return
    side = {home[0]: 'H', away[0]: 'A'}
    by_period = defaultdict(list)
    for r in rows:
        by_period[int(r['PERIOD'])].append(r)
    for period, prs in sorted(by_period.items()):
        # starters: act before being subbed in (type 8: PLAYER1 out, PLAYER2 in)
        seen_in, acted = set(), {'H': [], 'A': []}
        for r in prs:
            t = r['EVENTMSGTYPE']
            if t == '8':
                seen_in.add(r['PLAYER2_ID'])
                if r['PLAYER1_ID'] not in seen_in and r['PLAYER1_ID'] not in acted[side.get(r['PLAYER1_TEAM_ID'], 'H')]:
                    acted[side.get(r['PLAYER1_TEAM_ID'], 'H')].append(r['PLAYER1_ID'])
                continue
            if t in ('1', '2', '3', '4', '5', '6', '7'):
                for k in (1, 2, 3):
                    pid, tid = r[f'PLAYER{k}_ID'], r[f'PLAYER{k}_TEAM_ID']
                    if pid and pid != '0' and tid in side and pid not in seen_in and pid not in acted[side[tid]]:
                        acted[side[tid]].append(pid)
        floor = {s: set(acted[s][:5]) for s in 'HA'}
        if len(floor['H']) != 5 or len(floor['A']) != 5:
            continue
        t0 = clock_s('%d:00' % (PERIOD_LEN(period) // 60), period)
        cur = dict(start=t0, h=sorted(floor['H']), a=sorted(floor['A']), hp=0, ap=0, hq=0.0, aq=0.0)
        def flush(end):
            if end > cur['start']:
                yield dict(period=period, start_s=cur['start'], end_s=end, home5=' '.join(cur['h']), away5=' '.join(cur['a']),
                           home_pts=cur['hp'], away_pts=cur['ap'], home_poss=round(cur['hq'], 2), away_poss=round(cur['aq'], 2),
                           home_team=home[0], away_team=away[0])
        last_miss = None
        for r in prs:
            t = r['EVENTMSGTYPE']
            now = clock_s(r['PCTIMESTRING'], period)
            s = side.get(r['PLAYER1_TEAM_ID'])
            if t == '8':
                out_s, in_id, out_id = side.get(r['PLAYER1_TEAM_ID']), r['PLAYER2_ID'], r['PLAYER1_ID']
                lst = cur['h'] if out_s == 'H' else cur['a']
                if out_id in lst:
                    yield from flush(now)
                    cur = dict(start=now, h=list(cur['h']), a=list(cur['a']), hp=0, ap=0, hq=0.0, aq=0.0)
                    lst = cur['h'] if out_s == 'H' else cur['a']
                    lst.remove(out_id); lst.append(in_id); lst.sort()
                continue
            if not s:
                continue
            pk = 'hp' if s == 'H' else 'ap'
            qk = 'hq' if s == 'H' else 'aq'
            desc = (r['HOMEDESCRIPTION'] if s == 'H' else r['VISITORDESCRIPTION']) or ''
            if t == '1':
                cur[pk] += 3 if '3PT' in desc else 2; cur[qk] += 1
            elif t == '2':
                cur[qk] += 1
            elif t == '3':
                if 'MISS' not in desc.upper():
                    cur[pk] += 1
                cur[qk] += 0.44
            elif t == '5':
                cur[qk] += 1
            elif t == '4' and s == last_miss:
                cur[qk] -= 1                        # offensive rebound: same possession continues
            if t == '2' or (t == '3' and 'MISS' in desc.upper()):
                last_miss = s
            elif t in ('1', '5', '4'):
                last_miss = None
        yield from flush(t0 + PERIOD_LEN(period))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csvs', nargs='+')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cols = ['game_id', 'season', 'period', 'start_s', 'end_s', 'home_team', 'away_team', 'home5', 'away5',
            'home_pts', 'away_pts', 'home_poss', 'away_poss']
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    n_games = n_skip = 0
    with open(a.out, 'w', newline='') as fo:
        w = csv.DictWriter(fo, cols)
        w.writeheader()
        for path in a.csvs:
            season = int(os.path.basename(path).split('_')[-1].split('.')[0]) + 1     # file year = season start -> hoopR season end
            games = defaultdict(list)
            with open(path, newline='') as f:
                for r in csv.DictReader(f):
                    games[r['GAME_ID']].append(r)
            for gid, rows in games.items():
                if not gid.startswith('22'):      # regular season only (22yyNNNNN)
                    continue
                rows.sort(key=lambda r: (int(r['PERIOD']), int(r['EVENTNUM'])))
                got = False
                for st in parse_game(rows):
                    st.update(game_id=gid, season=season)
                    w.writerow(st); got = True
                n_games += got; n_skip += (not got)
            print(f'{path}: games ok {n_games} skipped {n_skip}', file=sys.stderr)


if __name__ == '__main__':
    main()
