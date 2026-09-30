#!/usr/bin/env python3
"""
Proof that live pricing projects a player the way the backtest did (Minutes Lab v2, step 1).

Walks the backtest's seasons with the backtest's own updates. Before each sampled 2025-26 game it exports the state
exactly as build_model_state.py does for the page, then asks pricing.Pricer for every player's minutes and
projection, feeding it what the backtest knew: the injury report 30 minutes before tip, the game model's margin
for blowout risk, the closing game line, and the players who dressed. Compared with build_prop_model_v2.walk's
records for the same player-games:
  minutes, base projection (minutes x rate + usage cascade)   must match to 1e-9 (same state, same arithmetic)
  projection after the v2 adjustments                         matches to the state file's rounding (pace, defense
                                                              factors at 3-4 decimals: under 1e-3)
Players projected at 0 minutes are skipped in the last check: the page never prices them.

  python3 nba/scripts/check_minutes_parity.py [--games 40]
"""
import datetime as dt, json, os, random, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_prop_model_v2 as V2
import build_prop_model_v3_full as F
import build_model_state as BS
import pricing as PX
from build_prop_model import BASE


def main(n_games=40):
    I = F.inputs()
    box, inj, margins, lines = I['box'], I['inj'], I['margins'], I['lines']
    recs = V2.walk(box, inj, margins, I['mm'], I['casc'], I['team_min'], lines)[0]
    by = {(r['gid'], r['aid']): r for r in recs}
    stk = json.load(open(V2.OUT_JSON))['stacker']
    games = [g for g in C.games(V2.SEASONS) if g['season'] == 2026 and box.get(g['game_id'])]
    random.seed(7)
    sample = {g['game_id'] for g in random.sample(games, min(n_games, len(games)))}
    proj = json.load(open(os.path.join(BS.DATA, 'player_projections.json')))
    keep = {p['id'] for t in proj['teams'].values() for p in t['players']}
    BS.keep_roster = keep
    D = dict(proj, teams={})                      # no current rosters: candidates come from the box score, as in the walk
    minutes = json.load(open(os.path.join(BS.DATA, 'model_state.json')))['minutes']

    ms, ctx, rt = MM.State(I['mm']['alpha']), V2.Context(), {}
    prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    worst = {'min': 0.0, 'base': 0.0, 'mu2': 0.0}
    n = 0
    for g in C.games(V2.SEASONS):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['game_id'] in sample:
            state = json.loads(json.dumps(BS.export(ctx, rt, ms, keep | {r['athlete_id'] for r in rows}, g['season'], asof=g['tip'])))
            pr = PX.Pricer(D=D, MS={'live': state, 'minutes': minutes})
            day = g['tip_et'].strftime('%Y-%m-%d')
            clk = (g['tip_et'] - dt.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
            ln = lines.get(g['game_id']) or {}
            gg = {'id': str(g['game_id']), 'home': g['home'], 'away': g['away'], 'tip': int(g['tip'].timestamp()),
                  'total': ln.get('total_close'), 'spread': ln.get('spread_close'), 'blow_spread': margins.get(g['game_id'])}
            cache = {}
            for team in (g['home'], g['away']):
                status = {a: s for a, s in inj.status(day, team, clk).items()}
                pr.cand_override[(team, gg['id'])] = [r['athlete_id'] for r in rows if r['team'] == team]
                res = pr.game_minutes(team, gg, status, cache)
                for r in rows:
                    rec = by.get((g['game_id'], r['athlete_id']))
                    if r['team'] != team or not rec:
                        continue
                    got = res.get(r['athlete_id'])
                    if not got:
                        print('missing', g['game_id'], r['athlete_id'])
                        continue
                    worst['min'] = max(worst['min'], abs(got['min'] - rec['pm']))
                    worst['base'] = max(worst['base'], max(abs(got['mu'][s] - rec['mu'][s]) for s in BASE))
                    m2 = V2.mu2(rec, stk)
                    if got['min'] <= 0:                   # projected 0 minutes: never priced (the page skips it)
                        continue
                    for s in BASE:
                        mm = pr.mu_for(r['athlete_id'], s, gg, cache, {}, team, status)
                        worst['mu2'] = max(worst['mu2'], abs(mm['mu'] - m2[s]))
                    n += 1
        V2.update_after(g, rows, rt, prior, ms, ctx)
    print(f'{n:,} player-games in {len(sample)} games of 2025-26. Largest difference: minutes {worst["min"]:.2e}, '
          f'base projection {worst["base"]:.2e}, projection after v2 adjustments {worst["mu2"]:.2e}')
    return worst


if __name__ == '__main__':
    main(int(sys.argv[sys.argv.index('--games') + 1]) if '--games' in sys.argv else 40)
