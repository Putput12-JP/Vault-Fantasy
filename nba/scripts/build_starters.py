#!/usr/bin/env python3
"""
Confirmed starters feed (NBA.com daily lineups, scripts/fetch_lineups.py): how accurate it is, and what it is worth
to the prop model, tested the same way as every v3 workstream.

Minutes v3 already has weights for "who is starting tonight" (beta_hindsight_starters, fit with the box score's
starters). Here the starters come from the feed instead, joined to our player ids, plus the feed's inactive list
added to the injury report's Out. Candidates, against v2 on identical rows and prices:

  v3m               v3 base (minutes v3 x per-stat memory), last game's role (what v3 knows without a feed)
  v3s               v3 base with the feed: tonight's confirmed starters + inactive list
  v3s_shape         v3s with workstream A's ladder distribution, uncalibrated; v3s_shape_linecal, line-calibrated

Timing: the Kalshi price is the 30-minute VWAP before tip and ESPN's is the last pre-tip line, so both were set by a
market that could see the same lineups. Past lineup files are stamped with their final update (about 2.5 h after
tip), so they cannot say how early each lineup was confirmed; the live recorder measures that from 2026-27.

Ship rule, unchanged and fixed before this ran: a candidate replaces v2 only if every v2 GO signal stays GO with
out-of-sample ROI at least v2's; among those, lowest average Kalshi log loss.

  python3 nba/scripts/build_starters.py
Writes data/starters_backtest.json and docs/starters-feed.md.
"""
import csv, json, os, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_prop_model_v3_full as F

DATA = os.path.join(C.HERE, '..', 'data')
LINEUPS = os.path.join(C.RAW, 'tables', 'lineups.csv')
OUT_JSON = os.path.join(DATA, 'starters_backtest.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'starters-feed.md')
ALIAS = {'alexandresarr': 'alexsarr', 'carltoncarrington': 'bubcarrington', 'jakobpoltl': 'jakobpoeltl'}   # NBA.com -> ESPN


def feed_key(name):
    k = C.name_key(name)
    return ALIAS.get(k, k)


def load_feed(box, seasons=(2025, 2026)):
    """{(game_id, team): {'start': {aid}, 'inactive': {aid}}} plus an accuracy report against the box score."""
    lu = defaultdict(list)
    for r in csv.DictReader(open(LINEUPS)):
        lu[(r['day'], r['team'])].append(r)
    feed, acc = {}, Counter()
    known = C.player_index(box)            # (team, name) -> id for anyone who ever played; inactives are not in tonight's box
    for g in C.games(list(seasons)):
        rows = box.get(g['game_id'], [])
        day = g['tip_et'].strftime('%Y%m%d')
        for team in (g['home'], g['away']):
            L = lu.get((day, team))
            acc['team_games'] += 1
            if not L:
                acc['no_lineup'] += 1
                continue
            idx = {C.name_key(r['name']): r['athlete_id'] for r in rows if r['team'] == team}
            st = [x for x in L if x['slot']]
            start = {idx[feed_key(x['player'])] for x in st if feed_key(x['player']) in idx}
            inactive = {known[(team, feed_key(x['player']))] for x in L
                        if x['roster'] == 'Inactive' and (team, feed_key(x['player'])) in known}
            acc['unmatched_starters'] += len(st) - len(start)
            if len(start) != 5:
                acc['incomplete'] += 1
                continue
            actual = {r['athlete_id'] for r in rows if r['team'] == team and r['starter']}
            acc['with_feed'] += 1
            acc['all5_right'] += start == actual
            acc['wrong_starters'] += len(start - actual)
            acc['confirmed'] += all(x['status'] == 'Confirmed' for x in st)
            played = {r['athlete_id'] for r in rows if r['team'] == team and r['played']}
            acc['inactive'] += len(inactive)
            acc['inactive_played'] += len(inactive & played)
            feed[(g['game_id'], team)] = {'start': start, 'inactive': inactive}
    return feed, dict(acc)


HEAD = ['# Confirmed starters feed: accuracy and backtest', '',
        'Generated {generated} by `nba/scripts/build_starters.py`. Source: NBA.com daily lineups (free, no key), the file',
        'behind nba.com/players/todays-lineups. Fit on 2024-25, tested on 2025-26, {n_test:,} identical player-games and prices.', '',
        '## The feed, 2024-25 and 2025-26', '',
        '| Team-games | With a full five | All five right | Wrong starters | Inactive listed | Of those, played |',
        '|---|---|---|---|---|---|',
        '| {acc[team_games]:,} | {acc[with_feed]:,} | {acc[all5_right]:,} ({all5_pct}) | {acc[wrong_starters]} | {acc[inactive]:,} | {acc[inactive_played]} |', '',
        'Timing: past files are stamped with their final update (about 2.5 hours after tip), so history cannot say how early',
        'each lineup was confirmed. The live recorder logs every Expected to Confirmed change from 2026-27. The backtest',
        'prices (Kalshi 30-minute pre-tip VWAP, ESPN last pre-tip line) come from a market that could see the same lineups,',
        'so this measures whether the model catches up with the market, not whether it beats a stale price.', '',
        '- **v2**: shipped. **v3m**: v3 base (minutes v3 x per-stat memory), role from last game.',
        '- **v3s**: v3 base with the feed: tonight\'s starters drive the role term (minutes v3\'s starters-known weights) and',
        '  the inactive list joins the injury report. **v3s_shape** / **v3s_shape_linecal**: v3s with workstream A\'s ladder shape.']
FOOT = ['Team minutes target: v3m {team_min_v3}, v3s {team_min_v3s}. Related: [prop-model-v3-full.md](prop-model-v3-full.md),',
        '[minutes-model-v3.md](minutes-model-v3.md).']


def main():
    I = F.inputs()
    feed, acc = load_feed(I['box'])
    print('feed:', acc, flush=True)
    recs3, tm3 = F.walk_v3(I)
    recs3s, tm3s = F.walk_v3(I, feed)
    res = F.compare(F.walk_v2(I), {'v3m': recs3, 'v3s': recs3s}, 'v3s')
    res.update({'team_min_v3': tm3, 'team_min_v3s': tm3s, 'acc': acc,
                'all5_pct': f"{acc['all5_right'] / max(1, acc['with_feed']):.1%}"})
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    F.write_md(res, HEAD, FOOT, OUT_MD)
    print(open(OUT_MD).read())


if __name__ == '__main__':
    main()
