#!/usr/bin/env python3
"""
The Backtests page's data: every test the NBA model has been through, what it asked, the rule fixed before it ran,
what came out, and what shipped. Read from each test's own output file (data/*.json) so the page cannot drift from
the docs; the two tests that only print (the game model at Kalshi's 1pm prices, and the sharp-money study, which ran
on the NFL tape) carry their numbers here with the doc they come from.

  python3 nba/scripts/build_backtests.py      -> data/backtests.json (render_app inlines it as /*BACKTESTS*/)
"""
import datetime as dt, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(DATA, 'backtests.json')
DOC = 'https://github.com/Putput12-JP/Vault-Fantasy/blob/main/nba/docs/'
STATS = ['pts', 'reb', 'ast', '3pm', 'pra', 'pr', 'pa', 'ra']


def load(name):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else None


def r(x, d=4):
    return None if x is None else round(x, d)


def side_of(v):
    return v.split('(')[1].rstrip(')') if '(' in v else None


def main():
    gm, mm, m3, uc = load('game_model.json'), load('minutes_model.json'), load('minutes_model_v3.json'), load('usage_cascade.json')
    p1, p2, p3, pf = load('prop_model.json'), load('prop_model_v2.json'), load('prop_model_v3.json'), load('prop_model_v3_full.json')
    rv3, st, mp, cb = load('rates_v3.json'), load('starters_backtest.json'), load('minutes_v3_pricing.json'), load('consensus_backtest.json')

    # ── signals: what passed, out of sample (2025-26 second half for Kalshi blends) ──
    signals = []
    for m, v in (p2['verdict']['v2'] if p2 else {}).items():
        if v.startswith(('GO', 'WATCH')):
            sd = side_of(v)
            b = p2['kalshi_bias'].get(m, {}).get('v2', {}).get(f'blend/{sd}') or {}
            signals.append({'engine': 'Prop model v2 + Kalshi price', 'venue': 'Kalshi', 'stat': m, 'side': sd, 'gate': v.split()[0],
                            'n': b.get('n'), 'games': b.get('games'), 'roi': b.get('roi'), 'z': b.get('z'), 'key': f'{m}|kalshi|{sd}', 'doc': 'prop-model-v2.md'})
    for m, by in ((cb or {}).get('verdicts', {}).get('kalshi_ladder') or {}).items():
        for sd, v in (by.get('consensus + model') or {}).items():
            if v in ('GO', 'WATCH'):
                b = cb['tests']['kalshi_ladder'][m]['bets']['consensus + model'].get(sd) or {}
                signals.append({'engine': 'Consensus ladder + model', 'venue': 'Kalshi', 'stat': m, 'side': sd, 'gate': v,
                                'n': b.get('n'), 'games': b.get('games'), 'roi': b.get('roi'), 'z': b.get('z'), 'key': f'{m}|kalshi|{sd}', 'doc': 'consensus-engine.md'})
    signals.sort(key=lambda s: ({'GO': 0, 'WATCH': 1}[s['gate']], -(s['z'] or 0)))

    # ── per-area detail ──
    game = None
    if gm:
        a = gm['seasons']['all']
        game = {'games': a['with_lines'], 'mae': a['mae'], 'ats_close': a['ats_close_tip'], 'ats_open': a['ats_open_am'],
                'ou_close': a['ou_close_tip'], 'ou_open': a['ou_open_am'], 'info': {k: a[k] for k in ('info_spread_close', 'info_spread_open', 'info_total_close')},
                'params': gm['params'], 'hfa': gm['hfa'], 'play_rates': gm['status_play_rates'], 'generated': gm['generated'],
                # backtest_game_vs_kalshi.py prints these (docs/game-model.md, "Honest bet-time test")
                'kalshi': {'sides': 2790, 'brier_model': 0.2057, 'brier_kalshi_1pm': 0.2008, 'brier_kalshi_pre': 0.1991, 'blend_w': 0.20,
                           'ml': [['2%+', 1028, -0.004], ['4%+', 783, -0.031], ['6%+', 569, -0.004], ['8%+', 408, 0.011], ['10%+', 283, -0.022]],
                           'spread_ladder': 'NO-GO: +14.6% in the first half, -6.6% in the second (flips sign)',
                           'total_ladder': 'WATCH: positive in both halves, but the second half alone is not 2 SE; about +2% per contract'}}
    minutes = None
    if mm:
        minutes = {'v1': {'n': mm['n_test'], 'seasons': '2024-25 and 2025-26', 'rows': [
            ['Recent minutes (EWMA)', mm['mae']['ewma_only'][0]], ['Recent minutes, team scaled to 240', mm['mae']['ewma_rescaled_240'][0]],
            ['Model, injury report', mm['mae']['model_report'][0]], ['Model, injury report, scaled to 240 (shipped as v2)', mm['mae']['model_report_rescaled'][0]],
            ['Model, hindsight (who actually sat)', mm['mae']['model_hindsight'][0]]],
            'teammate_out': [mm['mae_teammate_out']['n'], mm['mae_teammate_out']['ewma_only'][0], mm['mae_teammate_out']['model'][0]]}}
        if m3:
            t = m3['test']
            minutes['v3'] = {'n': m3['n_test'], 'seasons': '2025-26', 'rows': [
                ['v2 (shipped)', t['v2']['mae'], t['v2']['miss8']], ['v3: role, returns, new team, market spread', t['v3']['mae'], t['v3']['miss8']],
                ['v3 knowing who started', t['v3_hindsight_starters']['mae'], t['v3_hindsight_starters']['miss8']]]}
    usage = {s: {'mae': v['mae_vacated'], 'n': v['n_test_vacated'], 'use': v['use']} for s, v in (uc or {}).get('stats', {}).items()}
    props = None
    if p2:
        props = {'kalshi': {}, 'books': {}, 'acc': {}, 'cal': {}, 'verdict': {'v1': (p1 or {}).get('verdict'), 'v2': p2['verdict']['v2'],
                 'v3m': (pf or {}).get('verdict', {}).get('v3m')}}
        for m in ('pts', 'reb', 'ast', '3pm'):
            k = p2['kalshi'][m]
            props['kalshi'][m] = {'n': k['v2']['n'], 'market': k['v2']['logloss_market'], 'v1': k['v1']['logloss_model'], 'v2': k['v2']['logloss_model'],
                                  'v3_shape': (p3 or {}).get('kalshi', {}).get(m, {}).get('v3', {}).get('logloss'),
                                  'v3m': (pf or {}).get('kalshi', {}).get(m, {}).get('v3m', {}).get('logloss'),
                                  't': k['v2']['blend_t']}
            dec = (pf or {}).get('kalshi', {}).get(m, {}).get('v2', {}).get('deciles')
            if dec:
                props['cal'][m] = [[d[1], d[2], d[3]] for d in dec]
        for m in STATS:
            e = p2['espn'].get(m, {})
            if e.get('v2'):
                props['books'][m] = {'n': e['v2'].get('n'), 'market': e['v2'].get('logloss_market'), 'v2': e['v2'].get('logloss_model'), 't': e['v2'].get('blend_t')}
            props['acc'][m] = {'v1': p2['mae']['v1'].get(m), 'v2': p2['mae']['v2'].get(m), 'v3m': ((pf or {}).get('mean', {}).get(m, {}).get('v3m') or {}).get('mae')}
    consensus = None
    if cb:
        consensus = {}
        for test, by in cb['verdicts'].items():
            for m, v in by.items():
                for sd, g in (v.get('consensus + model') or {}).items():
                    b = (cb['tests'][test][m].get('bets') or {}).get('consensus + model', {}).get(sd) or {}
                    consensus.setdefault(test, []).append([m, sd, g, b.get('n'), b.get('games'), b.get('roi'), b.get('z')])

    # ── the decision log, oldest first ──
    def ship_of(x):
        return (x or {}).get('ship') or 'v2'
    k3 = lambda d, c, s: (((d or {}).get('kalshi_bias') or {}).get(s, {}).get(c) or {}).get('blend/NO') or {}
    log = [
        {'id': 'game', 'area': 'Game model', 'when': (gm or {}).get('generated'), 'doc': 'game-model.md',
         'q': 'Do team ratings, home court, back-to-backs and the injury report beat the spread?',
         'rule': 'The model must add information the closing line has not priced: t of the model-minus-line term at least 2.',
         'result': f"Against the close t = {game['info']['info_spread_close']['t']}; the closing spread is still more accurate ({game['mae']['market_close']['margin']} vs {game['mae']['tip']['margin']} points). It beat ESPN's untimed opening line (59% ATS at 5+ points), mostly by knowing injury news the open predated." if game else '',
         'verdict': 'Context', 'shipped': 'Vault line on the Slate page, labeled context'},
        {'id': 'game_kalshi', 'area': 'Game model', 'when': (gm or {}).get('generated'), 'doc': 'game-model.md',
         'q': 'At prices you could actually trade (Kalshi at 1pm), does the game model win?',
         'rule': 'Moneyline YES on the side the model rates higher than its 1pm price, after fees; ladders split into halves.',
         'result': 'Moneyline: Kalshi 1pm Brier 0.2008 beats the model 0.2057, and the edge buckets lost after fees. Spread ladder flips sign between halves. Total ladder positive in both halves but not 2 SE.',
         'verdict': 'NO-GO', 'shipped': 'Nothing'},
        {'id': 'minutes', 'area': 'Minutes', 'when': (mm or {}).get('generated'), 'doc': 'minutes-model.md',
         'q': 'Can minutes be projected better than recent minutes, using the injury report?',
         'rule': 'Walk-forward on 2024-25 and 2025-26 with the report 30 minutes before tip; ship if MAE beats recent minutes scaled to 240.',
         'result': f"MAE {minutes['v1']['rows'][3][1]:.2f} vs {minutes['v1']['rows'][1][1]:.2f} minutes on {minutes['v1']['n']:,} player-games; {minutes['v1']['teammate_out'][2]:.2f} vs {minutes['v1']['teammate_out'][1]:.2f} when a same-position teammate is out." if minutes else '',
         'verdict': 'Shipped', 'shipped': 'Minutes model v2 prices every prop'},
        {'id': 'usage', 'area': 'Usage', 'when': (uc or {}).get('generated'), 'doc': 'usage-cascade.md',
         'q': "When a teammate sits, does a player's production per minute change, beyond his extra minutes?",
         'rule': 'Per stat, keep the cascade only if it lowers held-out error on games with vacated usage.',
         'result': 'MAE on games with vacated usage, without then with the cascade: ' + ', '.join(f"{s} {v['mae'][0]:.3f} to {v['mae'][1]:.3f}" for s, v in usage.items() if s in ('pts', 'reb', 'ast', '3pm'))
                   + f". Kept for {', '.join(s for s, v in usage.items() if v['use']) or 'none'}; dropped for {', '.join(s for s, v in usage.items() if not v['use']) or 'none'}. Small effects.",
         'verdict': 'Shipped', 'shipped': 'Usage cascade in every projection'},
        {'id': 'prop_v1', 'area': 'Prop model', 'when': (p1 or {}).get('generated'), 'doc': 'prop-model.md',
         'q': 'Does a minutes x rate projection, blended with the price, beat Kalshi and sportsbook props?',
         'rule': 'GO = second-half ROI > 0 with z >= 2 over 50+ games, betting the 3%+ blended edge after fees; WATCH = positive.',
         'result': 'Only Kalshi 3-pointers (NO side) passed. Kalshi YES is overpriced in every price bucket all season. Sportsbook props: no reliable edge.',
         'verdict': 'GO: 3PM NO', 'shipped': 'v1 blend'},
        {'id': 'prop_v2', 'area': 'Prop model', 'when': (p2 or {}).get('generated'), 'doc': 'prop-model-v2.md',
         'q': 'Do opponent defense, the game total, shooting volume x regressed %, form, home and rest improve it?',
         'rule': 'Same GO rule; v2 replaces v1 if it keeps every v1 GO and lowers Kalshi log loss.',
         'result': f"Better RMSE on every stat; Kalshi log loss better on all four (3PM {props['kalshi']['3pm']['v2']:.4f} vs market {props['kalshi']['3pm']['market']:.4f}). Kalshi points NO joins 3PM NO as GO." if props else '',
         'verdict': 'Shipped', 'shipped': 'Prop model v2 prices the board'},
        {'id': 'rates_v3', 'area': 'Prop model', 'when': (rv3 or {}).get('generated'), 'doc': 'rates-v3.md',
         'q': 'Do per-stat memories (each volume and percentage with its own learning rate) beat one shared rate?',
         'rule': 'Tuned on 2024-25, scored on 2025-26 with true minutes; carried into the v3 candidate if it helps.',
         'result': ', '.join(f"{s} MAE {v['v1']['mae']:.3f} to {v['v3']['mae']:.3f}" for s, v in (rv3 or {}).get('test', {}).items()) + '.',
         'verdict': 'Into v3 candidate', 'shipped': 'Nothing on its own'},
        {'id': 'minutes_v3', 'area': 'Minutes', 'when': (m3 or {}).get('generated'), 'doc': 'minutes-model-v3.md',
         'q': 'Do role, returns from absence, new-team learning and the market spread improve minutes?',
         'rule': 'Same test set as v2 (2025-26, report 30 minutes before tip).',
         'result': f"MAE {minutes['v3']['rows'][1][1]:.3f} vs {minutes['v3']['rows'][0][1]:.3f}; first game back 5.04 vs 5.49. Knowing who started: {minutes['v3']['rows'][2][1]:.3f}." if minutes and minutes.get('v3') else '',
         'verdict': 'Into v3 candidate', 'shipped': 'Live shadow (Tonight page)'},
        {'id': 'prop_v3a', 'area': 'Prop model', 'when': (p3 or {}).get('generated'), 'doc': 'prop-model-v3.md',
         'q': 'Do full ladder distributions (minutes x production shapes) price Kalshi ladders better than v2\'s curve?',
         'rule': 'Replace v2 only if every v2 GO stays GO with ROI at least v2\'s; then lowest Kalshi log loss.',
         'result': f"Better probabilities (points log loss {props['kalshi']['pts']['v3_shape']:.4f} vs {props['kalshi']['pts']['v2']:.4f}) but the same blended edge, so the rule keeps v2." if props and props['kalshi']['pts'].get('v3_shape') else '',
         'verdict': f"Kept {ship_of(p3)}", 'shipped': 'Nothing'},
        {'id': 'prop_v3', 'area': 'Prop model', 'when': (pf or {}).get('generated'), 'doc': 'prop-model-v3-full.md',
         'q': 'Minutes v3 + per-stat memory together (with and without the ladder shape): replace v2?',
         'rule': 'Same pre-registered rule.',
         'result': f"More accurate on every stat, but Kalshi points NO slips to {((pf or {}).get('verdict', {}).get('v3m') or {}).get('pts', '?')}." if pf else '',
         'verdict': f"Kept {ship_of(pf)}", 'shipped': 'Nothing'},
        {'id': 'starters', 'area': 'Lineups', 'when': (st or {}).get('generated'), 'doc': 'starters-feed.md',
         'q': "Is NBA.com's starting-lineup feed accurate, and does knowing the five improve pricing?",
         'rule': 'Same pre-registered rule; prices are 30 minutes before tip, after lineups usually post.',
         'result': f"Right on {st['acc']['all5_right']:,} of {st['acc']['with_feed']:,} team-games; every listed inactive sat. Best accuracy yet, but backtest prices already knew the lineups." if st else '',
         'verdict': f"Kept {ship_of(st)}", 'shipped': 'Recorder logs lineup times to test the timing edge live'},
        {'id': 'consensus', 'area': 'Consensus', 'when': (cb or {}).get('generated'), 'doc': 'consensus-engine.md',
         'q': "Move one venue's prices to another venue's line: does that consensus find mispriced Kalshi rungs?",
         'rule': 'GO = second-half ROI > 0 with z >= 2 over 50+ games; blends fit on the first half by tip time.',
         'result': 'Kalshi ladder leave-one-out + model: points NO and 3PM NO GO. Books to Kalshi: WATCH. Kalshi to books: no GO.',
         'verdict': 'GO: pts NO, 3PM NO', 'shipped': 'Consensus gap on the Edges page'},
        {'id': 'minutes_v3_pricing', 'area': 'Minutes', 'when': (mp or {}).get('generated'), 'doc': 'minutes-v3-pricing.md',
         'q': "Price with minutes v3 (with and without confirmed starters), everything else v2?",
         'rule': "Replace v2's minutes only if every v2 GO stays GO with ROI at least v2's; then lowest Kalshi log loss.",
         'result': f"Points NO ROI {k3(mp, 'v2m3', 'pts').get('roi', 0) * 100:.1f}% vs v2's {k3(mp, 'v2', 'pts').get('roi', 0) * 100:.1f}%; with starters z {k3(mp, 'v2m3s', 'pts').get('z')}, below 2." if mp else '',
         'verdict': f"Kept {ship_of(mp)}", 'shipped': 'v3 minutes as a logged shadow'},
        {'id': 'sharp', 'area': 'Sharp money', 'when': '2026-09-28', 'doc': 'https://github.com/Putput12-JP/Vault-Fantasy/blob/main/docs/retro/sharp-money-study.md',
         'q': 'Can Vault tell where sharp money is, and does following it pay?',
         'rule': 'Polymarket accounts scored walk-forward on their own trades vs the close; then copy their side later.',
         'result': 'Sharp accounts beat the close (+0.38%, t 7 on 2,684 NFL trades; NFL-sharp accounts +1.76% on 439 NBA trades). Copying 30 min to 2 h later: -0.19%. Size alone is not skill.',
         'verdict': 'Context', 'shipped': 'Sharp Price page, every signal graded live'},
    ]
    for e in log:
        e['when'] = (e['when'] or '')[:10]
    out = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'doc': DOC,
           'signals': signals, 'log': log, 'game': game, 'minutes': minutes, 'usage': usage, 'props': props, 'consensus': consensus,
           'test': {'seasons': 'fit 2024-25, test 2025-26', 'player_games': (pf or {}).get('n_test'), 'games': (game or {}).get('games')}}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print(f"backtests: {len(log)} tests, {len(signals)} GO / WATCH signals -> {os.path.relpath(OUT)} ({os.path.getsize(OUT) // 1000} KB)")


if __name__ == '__main__':
    main()
