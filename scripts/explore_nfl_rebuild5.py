#!/usr/bin/env python3
"""Round 5: (1) where does the live model lose to the closing line by week of season; (2) a quarterback value from passing EPA per start, used as a
GAP between the game's starter and the team's recent starters (the ELWAY / QBERT idea), on top of the live model.
Same protocol as round 4: tune 2010-19, validate 2020-22, sealed 2023+, 2025 and 2026 reported on their own.

  python3 scripts/explore_nfl_rebuild5.py --team-dir DIR      # DIR holds tw{season}.csv (nflverse stats_team_week)
"""
import argparse, csv, math, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_nfl_rebuild4 as X, build_game_model as M


def load_tpe(d):
    """(season, week, team) -> team passing EPA minus that season's league mean per team-game."""
    raw = {}
    for y in range(2006, 2027):
        p = os.path.join(d, f'tw{y}.csv')
        if not os.path.exists(p): continue
        for r in csv.DictReader(open(p, encoding='utf-8')):
            if r['season_type'] != 'REG': continue
            v = r.get('passing_epa')
            if v not in (None, '', 'NA'): raw[(int(r['season']), int(r['week']), M.norm_team(r['team']))] = float(v)
    mean = defaultdict(list)
    for (s, w, t), v in raw.items(): mean[s].append(v)
    mean = {s: sum(v) / len(v) for s, v in mean.items()}
    return {k: v - mean[k[0]] for k, v in raw.items()}


def stats(ps, lo, hi, key='pm'):
    P = [p for p in ps if lo <= p['season'] <= hi and p['spread'] is not None]
    r = math.sqrt(sum((p[key] - p['result']) ** 2 for p in P) / len(P))
    m = math.sqrt(sum((p['spread'] - p['result']) ** 2 for p in P) / len(P))
    return r, m, len(P)


def ats(ps, lo, hi, thr):
    w = l = 0
    for p in ps:
        if not lo <= p['season'] <= hi or p['spread'] is None: continue
        gap, c = p['pm'] - p['spread'], p['result'] - p['spread']
        if abs(gap) < thr or c == 0: continue
        if (c > 0) == (gap > 0): w += 1
        else: l += 1
    return w, l


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--team-dir', required=True); a = ap.parse_args()
    games = M.fetch_games(); tpe = load_tpe(a.team_dir)
    live = X.run(games, X.LIVE)
    print('(1) live model vs the close by week of season, 2014+ (margin RMSE, lower is better)')
    for lo, hi in ((1, 3), (4, 6), (7, 12), (13, 18)):
        P = [p for p in live if p['season'] >= 2014 and p['spread'] is not None and lo <= p['week'] <= hi]
        r = math.sqrt(sum((p['pm'] - p['result']) ** 2 for p in P) / len(P)); m = math.sqrt(sum((p['spread'] - p['result']) ** 2 for p in P) / len(P))
        print(f'   weeks {lo:>2}-{hi:<2} n={len(P):>4}  live {r:.3f}  close {m:.3f}  gap {r - m:+.3f}')
    print('\n(2) QB-value gap from passing EPA per start, added to the live model')
    b = {n: stats(live, *w)[0] for n, w in (('tune', X.TUNE), ('val', X.VAL))}
    print(f"{'setting':<46}{'tune':>8}{'val':>8}")
    rows = []
    for c in (0.5, 1.0, 1.5, 2.5):
        for qa in (0.1, 0.25):
            for qk in (4, 12):
                for keep_flag in (True, False):
                    o = dict(X.LIVE, qbg=c, qa=qa, qk=qk, tpe=tpe, qbm=2.5 if keep_flag else 0.0, qbt=1.25 if keep_flag else 0.0)
                    p = X.run(games, o); t, v = stats(p, *X.TUNE)[0] - b['tune'], stats(p, *X.VAL)[0] - b['val']
                    rows.append((t, v, c, qa, qk, keep_flag, p))
    rows.sort(key=lambda r: r[0])
    for t, v, c, qa, qk, kf, _ in rows[:6]:
        print(f"c={c} alpha={qa} k={qk} backup-flag={'on ' if kf else 'off'}{'':<18}{t:>+8.3f}{v:>+8.3f}")
    ok = [r for r in rows if r[0] < -0.005 and r[1] < -0.005]
    print(f'\n{len(rows)} settings tried; {len(ok)} beat live on BOTH tune and validate by more than 0.005')
    if not ok: print('Sealed 2023+ not spent.'); return
    t, v, c, qa, qk, kf, p = min(ok, key=lambda r: r[0] + r[1])
    print(f'chosen (best tune+val): c={c} alpha={qa} k={qk} backup-flag={kf}   tune {t:+.3f}  val {v:+.3f}')
    for nm, lo, hi in (('sealed 2023+', 2023, 9999), ('2025', 2025, 2025), ('2026', 2026, 2026)):
        r1, m, n = stats(live, lo, hi); r2, _, _ = stats(p, lo, hi)
        print(f'{nm:<13} n={n:<4} RMSE live {r1:.3f}  candidate {r2:.3f}  close {m:.3f}   ATS 3+: live {ats(live, lo, hi, 3.0)} cand {ats(p, lo, hi, 3.0)}   1.5+: live {ats(live, lo, hi, 1.5)} cand {ats(p, lo, hi, 1.5)}')


if __name__ == '__main__':
    main()
