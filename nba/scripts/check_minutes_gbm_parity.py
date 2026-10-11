#!/usr/bin/env python3
"""
Proof that live pricing projects minutes with the GBM exactly as the backtest did (the GBM twin of check_minutes_parity.py).

For sampled 2025-26 games it (1) takes the training walk's rows (minutes_gbm features, oracle absences) scored by the trees, and
(2) rebuilds the same game from ONLY the exported state (Walk.export -> JSON round trip -> Pricer.game_minutes_gbm), the path the
daily job and the recorder take. The two must agree for every player who played. State is rounded to 4 decimals on export, so the
tolerance is 0.01 minutes.

  python3 nba/scripts/check_minutes_gbm_parity.py [--games 40]
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_minutes_gbm as G
import minutes_gbm as MG
import pricing as PX


def main():
    n_games = int(sys.argv[sys.argv.index('--games') + 1]) if '--games' in sys.argv else 40
    box = C.player_games(G.SEASONS)
    margins = MM.expected_margins(box)
    df = G.build_rows(box, margins)
    df = df[df.season == 2026]
    train = df.set_index(['gid', 'aid'])
    model = MG.load_model()
    games = [g for g in C.games([2026]) if box.get(g['game_id']) and g['game_id'] in set(df.gid)]
    pick = set(g['game_id'] for g in games[40::max(1, len(games) // n_games)][:n_games])
    pr = PX.Pricer(example=False)
    walk, worst, n, miss = MG.Walk(), 0.0, 0, 0
    for g in C.games(G.SEASONS):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['game_id'] in pick:
            tip = g['tip'].timestamp()
            pr.state = {'gbm': json.loads(json.dumps(walk.export(tip)))}
            if hasattr(pr, '_gbm_pl'):
                del pr._gbm_pl
            played = {r['athlete_id'] for r in rows if r['played']}
            mg = margins.get(g['game_id'])
            gg = {'id': g['game_id'], 'tip': tip, 'home': g['home'], 'away': g['away'], 'spread': -mg if mg is not None else None}
            for team in (g['home'], g['away']):
                rot = MG.rotation({int(a): MG.from_export(r) for a, r in pr.state['gbm']['players'].items()}, team, tip)
                status = {a: 'Out' for a in rot if a not in played}
                pr.cand_override[(team, str(g['game_id']))] = [r['athlete_id'] for r in rows if r['team'] == team and r['played']]
                live = pr.game_minutes_gbm(team, gg, status, {})
                for r in rows:
                    if r['team'] != team or not r['played']:
                        continue
                    k = (g['game_id'], r['athlete_id'])
                    if k not in train.index:
                        continue
                    ref = min(48.0, max(0.0, MG.predict([train.loc[k][c] for c in MG.COLS])))
                    if r['athlete_id'] not in live:
                        miss += 1
                        continue
                    worst = max(worst, abs(live[r['athlete_id']] - ref))
                    n += 1
        walk.update(g, rows, MM.group)
    print(f'{len(pick)} games, {n} player-games compared, {miss} in the backtest but not priced live; max |live - backtest| = {worst:.5f} min')
    if not (worst < 0.01 and miss == 0):
        raise SystemExit('PARITY FAILED')
    print('PARITY OK')


if __name__ == '__main__':
    main()
