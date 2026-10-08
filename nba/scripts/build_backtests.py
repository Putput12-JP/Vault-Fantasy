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
SNAME = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', '3pm': '3-pointers', 'pra': 'pts + reb + ast', 'pr': 'pts + reb', 'pa': 'pts + ast', 'ra': 'reb + ast'}


def load(name):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else None


def r(x, d=4):
    return None if x is None else round(x, d)


def side_of(v):
    return v.split('(')[1].rstrip(')') if '(' in v else None


def hr_text(hr):
    if not hr:
        return ''
    S = hr['sets']
    o = lambda k, rule: S[k]['rules'][rule]
    c = next(c for c in S['espn2025_open']['calibration'] if c['l10'] == '9-10 of 10')
    return (f"Sportsbooks: at 9-10 of 10 the streak said {c['streak_rate']:.0%}, the line said {c['market']:.0%}, it hit {c['actual']:.0%}; "
            f"8+ of 10 overs returned {o('espn2025_open', 'L10 over (hit 8+ of 10)')['roi']:+.1%} (2024-25) and {o('espn2026_close', 'L10 over (hit 8+ of 10)')['roi']:+.1%} (2025-26 close). "
            f"Kalshi: 8+ of 10 overs {o('kalshi2026', 'L10 over (hit 8+ of 10)')['roi']:+.1%}; 2-or-fewer unders {o('kalshi2026', 'L10 under (hit 2 or fewer of 10)')['roi']:+.1%}, "
            f"less than betting every NO ({o('kalshi2026', 'Baseline: every under')['roi']:+.1%}). At the same price a streak is worth about "
            f"{S['kalshi2026']['same_price']['cold_under']['diff']:+.1%}: a little information, not enough to make the losing side win. Players who beat their lines one half did not the next "
            f"(correlation {S['kalshi2026']['persistence']['corr']}).")


def main():
    gm, mm, m3, uc = load('game_model.json'), load('minutes_model.json'), load('minutes_model_v3.json'), load('usage_cascade.json')
    p1, p2, p3, pf = load('prop_model.json'), load('prop_model_v2.json'), load('prop_model_v3.json'), load('prop_model_v3_full.json')
    rv3, st, mp, cb = load('rates_v3.json'), load('starters_backtest.json'), load('minutes_v3_pricing.json'), load('consensus_backtest.json')
    hr = load('hit_rates.json')
    gv = load('game_venues.json')
    mvp, ss = load('moved_players_test.json'), load('season_start_test.json')

    # ── signals: what passed, out of sample (2025-26 second half for Kalshi blends) ──
    signals = []
    for m, v in (p2['verdict']['v2'] if p2 else {}).items():
        if v.startswith(('GO', 'WATCH')):
            sd = side_of(v)
            b = p2['kalshi_bias'].get(m, {}).get('v2', {}).get(f'blend/{sd}') or {}
            signals.append({'engine': 'Prop model v2 + Kalshi price', 'venue': 'Kalshi', 'stat': m, 'side': sd, 'gate': v.split()[0],
                            'n': b.get('n'), 'games': b.get('games'), 'roi': b.get('roi'), 'z': b.get('z'), 'key': f'{m}|kalshi|{sd}', 'doc': 'prop-model-v2.md',
                            'daily': b.get('daily')})          # [ET day, wins, losses, units] per game day of the test half
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
    pc_ = load('pickem_corr.json')
    pk_diff = ''
    if pc_:
        opp = [f for f in pc_['families'] if f['family'].startswith('Opponents')]
        w = [1 / f['test']['se'] ** 2 for f in opp]
        cp = sum(wi * f['test']['c'] for wi, f in zip(w, opp)) / sum(w)
        pk_diff = (f"{len(opp)} opposing-team families, {sum(1 for f in opp if f['candidate'])} candidates, {sum(1 for f in opp if f['pass'])} passes. The largest lift on 2025-26 was "
                   f"{max(f['test']['lift'] for f in opp) - 1:+.1%} (bar: 4%); pooled over all of them it is {cp / .25:+.1%}. With no lift, each pick would need 57.7% at a 3x payout.")
    pe_ = load('pickem_entries.json')
    pk_ent = ''
    if pe_:
        c = pe_['cells']
        pk_ent = (f"On near-even lines the model's picks hit {c['S1/2']['test']['leg_hit']:.1%} each in a 2-pick (it needs 57.7% at 3x) and {c['S1/6']['test']['leg_hit']:.1%} in a 6-pick (it needs 54.7%). "
                  f"Every cell lost money on 2025-26. Bigger entries ask less per pick, but the picks were not better than a coin flip. A pick would need its line shifted off fair by about "
                  f"{pe_['shading']['pts']['2']} points (points, 2-pick) or {pe_['shading']['pts']['6']} (6-pick).")
    xs = (load('prop_model_extra.json') or {}).get('espn_2026')
    nl = load('news_lag_test.json') or {}
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
        {'id': 'hit_rates', 'area': 'Streaks', 'when': (hr or {}).get('generated'), 'doc': 'hit-rates.md',
         'q': 'Players who keep hitting a line ("8 of his last 10"): do they keep hitting it, and do players who beat their lines keep beating them?',
         'rule': 'Bet OVER at 8+ of last 10 against the same line, UNDER at 2 or fewer; GO = test ROI > 0 with z >= 2 over 50+ games, and better than betting that side blind.',
         'result': hr_text(hr), 'verdict': 'NO-GO', 'shipped': 'Nothing; a myth check for the page'},
        {'id': 'sharp', 'area': 'Sharp money', 'when': '2026-09-28', 'doc': 'https://github.com/Putput12-JP/Vault-Fantasy/blob/main/docs/retro/sharp-money-study.md',
         'q': 'Can Vault tell where sharp money is, and does following it pay?',
         'rule': 'Polymarket accounts scored walk-forward on their own trades vs the close; then copy their side later.',
         'result': 'Sharp accounts beat the close (+0.38%, t 7 on 2,684 NFL trades; NFL-sharp accounts +1.76% on 439 NBA trades). Copying 30 min to 2 h later: -0.19%. Size alone is not skill.',
         'verdict': 'Context', 'shipped': 'Sharp Price page, every signal graded live'},
        {'id': 'sharp_copy', 'area': 'Sharp money', 'when': '2026-10-01', 'doc': 'https://github.com/Putput12-JP/Vault-Fantasy/blob/main/docs/pm-accounts-copy-results.md',
         'q': "Priced at the exact ask from Polymarket's order-book archive, does copying a sharp account 15 minutes later beat the close?",
         'rule': 'Labels from older games only; GO if the average at 15 minutes is above zero by 2+ standard errors (NFL and college, Aug 18 - Sept 29).',
         'result': 'Copy at 15 minutes +0.09% vs the close (SE 0.59, 36 copies). The market drifts toward sharp accounts over hours (+1.05% by kickoff), not minutes; 40 trades settle nothing. Re-test declared on Oct 1-27.',
         'verdict': 'NO-GO', 'shipped': 'Nothing; sharp accounts stay context'},
        {'id': 'game_venues', 'area': 'Game model', 'when': '2026-10-01', 'doc': 'game-venues-results.md',
         'q': 'Which market is sharpest on NBA game lines at tip: Polymarket, Kalshi or the sportsbooks? And does the game model add to the sharpest?',
         'rule': "A venue moves ahead of the sportsbook in the Slate's fallback only if its log loss is lower by 2+ SE; the model must improve the sharpest venue's log loss on games after Feb 1 by 2+ SE.",
         'result': (f"{gv['n']:,} games of 2025-26. Log loss: sportsbook {gv['logloss']['book']:.4f}, Polymarket {gv['logloss']['pm']:.4f}, Kalshi {gv['logloss']['kal']:.4f}: "
                    f"Polymarket ties the sportsbook close, Kalshi trails by a hair (not significant). Model blend on later games: {gv['model']['gain']:+.4f} (SE {gv['model']['se']:.4f}).") if gv else '',
         'verdict': 'NO-GO', 'shipped': 'Nothing changes: the Slate keeps its fallback order, the game model stays context'},
        {'id': 'moved_players', 'area': 'Minutes', 'when': '2026-10-02', 'doc': 'moved-players-results.md',
         'q': 'Should a player on a new team (trade, signing) count toward its minutes from his first game with it?',
         'rule': 'Minutes MAE on new-arrival team-games lower by 2+ SE, and not worse on all team-games by more than 2 SE.',
         'result': (f"New-arrival games {mvp['new_arrival']['diff']:+.2f} min (z {mvp['new_arrival']['z']}); a mover is left out of only his first game, and teams rarely "
                    "have too few players for it to matter. Where they do (7 or fewer projected, or anyone at 44+ minutes), minutes run 2 to 4 too high.") if mvp else '',
         'verdict': 'NO-GO', 'shipped': "Roster guard: those teams and players with no minutes for their current team are priced and shown but never a call, edge, pick'em leg or shadow bet"},
        {'id': 'season_start', 'area': 'Game model', 'when': '2026-10-02', 'doc': 'season-start-results.md',
         'q': "Should the game model's season start use the new rosters (who joined and left) and reset the league scoring level?",
         'rule': 'Each variant: first-4-weeks MAE lower by 2+ SE (margin for rosters, total for scoring level), whole season not worse by more than 2 SE.',
         'result': (f"Rosters: first 4 weeks {ss['R']['early']['diff']:+.3f} pts margin (z {ss['R']['early']['z']}). Scoring level: first 4 weeks {ss['T']['early']['diff']:+.2f} pts total "
                    f"(z {ss['T']['early']['z']}), whole season {ss['T']['season']['diff']:+.2f} (z {ss['T']['season']['z']}); it does fix the week-1 lean (model minus close "
                    f"{ss['T']['week1_close_bias']['current']['model_minus_close']:+.1f} to {ss['T']['week1_close_bias']['T']['model_minus_close']:+.1f}).") if ss else '',
         'verdict': 'NO-GO', 'shipped': "Neither. The Slate labels the Vault line as last season's rosters for 4 weeks, names who joined and left, and leaves out the Vault total"},
        {'id': 'pickem_corr', 'area': "Pick'em", 'when': '2026-10-01', 'doc': 'pickem-correlation-results.md',
         'q': "Do two teammates' stats hit together more often than a pick'em app's flat payout assumes?",
         'rule': "Families of pairs found on 2024-25, tested on the untouched 2025-26: a family passes only if it holds in the same direction with strong evidence on the test season and at closing prices. Written before any result.",
         'result': "Two families passed: teammates' points with assists (both hit about 4% more often than independent, z +5.1) and teammates' assists with 3-pointers (about 4%, z +4.2). Every other combination failed, including every pairing of opponents.",
         'verdict': 'GO', 'shipped': "Pick'em Pairs page and Pick'em of the night, for those two families only"},
        {'id': 'copula_a', 'area': 'Game simulation', 'when': '2026-10-06', 'doc': 'copula-fit-results.md',
         'q': "Can a joint model of how players' stats move together (a copula) beat treating every prop as independent?",
         'rule': "Gain over independence at z >= 2 on the 2025-26 test season, and the calibration slope's 95% interval must contain 1 and exclude 0.",
         'result': "The gain was large (z +5.4) but the slope was 0.36 (interval -0.07 to 0.78): the market's habit of pricing overs too high contaminated the fit, so the check failed. Fixed in the next step.",
         'verdict': 'NO-GO', 'shipped': 'Nothing; led to step A2'},
        {'id': 'copula_a2', 'area': 'Game simulation', 'when': '2026-10-06', 'doc': 'copula-freeze.md',
         'q': 'With the over bias removed first, does the frozen joint model hold on games it has never seen?',
         'rule': "Fit on 2024-25 and 2025-26, frozen before 2026-27 exists. First look at 150 regular-season games: GO needs z >= 2.4 and an agreement slope whose interval contains 1 and excludes 0.",
         'result': "Frozen: 918 games, 23,753 legs, the in-sample over-bias check passed (every stat within 0.5 points after the shift). Waiting for the 2026-27 holdout.",
         'verdict': 'Frozen', 'shipped': 'Game Simulation stays independent until this passes'},
        {'id': 'script_b', 'area': 'Game simulation', 'when': '2026-10-07', 'doc': 'game-script-minutes-results.md',
         'q': "Does tying simulated minutes to the game's score make them behave like real ones (blowouts sit starters)?",
         'rule': "Starters' 80% coverage within 76-84%, mean rank 0.50 +/- 0.02, and the model's togetherness of minute swings inside the observed 95% interval.",
         'result': "Coverage was fine (83.1%) but starters' minutes moved together only +0.10 against +0.19 observed, and the mean rank was 0.520.",
         'verdict': 'NO-GO', 'shipped': 'Nothing; led to B2'},
        {'id': 'script_b2', 'area': 'Game simulation', 'when': '2026-10-07', 'doc': 'game-script-minutes-b2-results.md',
         'q': 'Adding overtime and a shared team minutes shock: is that enough?',
         'rule': 'The same checks as B, plus overtime share within 1.5 points.',
         'result': "Starters with starters and starters with bench now passed, and overtime matched (5.3% simulated vs 5.0% observed). Bench with bench came in at +0.165 against +0.214 observed, one miss.",
         'verdict': 'NO-GO', 'shipped': 'Nothing; led to B3'},
        {'id': 'script_b3', 'area': 'Game simulation', 'when': '2026-10-07', 'doc': 'game-script-minutes-b3-results.md',
         'q': 'With a clamp calibration for the bench floor, does the minutes model pass on a season it was not tuned on?',
         'rule': "All four B2 checks on 200 regular-season 2026-27 games, with the model frozen first.",
         'result': "Frozen. On the development seasons every check passed (a sanity check, not the test). The real test waits for 200 games.",
         'verdict': 'Frozen', 'shipped': 'Nothing until the holdout passes'},
        {'id': 'extra_markets', 'area': 'Prop model', 'when': '2026-10-07', 'doc': 'prop-model-extra.md',
         'q': 'Can the same minutes-times-rate model price steals, blocks, turnovers, steals plus blocks, field goals, free throws, 3-point attempts, offensive and defensive rebounds and fouls?',
         'rule': "Written before anyone bets on them: no prior season of main-line prices to calibrate or blend on, no book history for most, none on Kalshi, so every one of these is NO-GO. Steals and blocks are scored on ESPN's 2025-26 closing lines.",
         'result': (f"Steals: the model's Brier score {xs['stl']['brier_model']} against the book's {xs['stl']['brier_market']} on {xs['stl']['n_rows']} lines (level). Blocks: {xs['blk']['brier_model']} against {xs['blk']['brier_market']} on {xs['blk']['n_rows']} lines (behind the book). The others have no prices to score against.") if xs else '',
         'verdict': 'NO-GO', 'shipped': 'The markets are priced and shown on the Props Table, labelled untested, never a gated bet'},
        {'id': 'pickem_diff', 'area': "Pick'em", 'when': '2026-10-08', 'doc': 'pickem-different-teams.md',
         'q': "Some pick'em apps only let you combine players on different teams. Is there a pairing like that worth playing?",
         'rule': "A re-read of the same pre-registered test, no new threshold: an opposing-team family passes with 2,000+ pairs, z >= 3 on 2024-25, then the same sign at z >= 2 and a lift of at least 4% on 2025-26.",
         'result': pk_diff,
         'verdict': 'NO-GO', 'shipped': "A switch on Pick'em Pairs and Pick'em of the night for apps that need different teams: it shows no pairs and says why"},
        {'id': 'pickem_entries', 'area': "Pick'em", 'when': '2026-10-08', 'doc': 'pickem-entries-results.md',
         'q': "Pick'em entries can mix players from different games. Built from independent picks, which entry size and which way of choosing the picks would have been profitable?",
         'rule': "Daily entries of 2 to 6 picks, one pick per player and game, three ways to rank the picks (model, model minus market, market). The best cell on 2024-25 is judged on 2025-26: ROI above zero at z >= 2.4 with 100+ entries and both halves positive. Run 1 allowed unrealistic lines (80% favourites), so a second run kept only lines near even money (45-55%), written down before it ran.",
         'result': pk_ent,
         'verdict': 'NO-GO', 'shipped': "Nothing; Pick'em Pairs says what each entry size needs per pick"},
        {'id': 'alt_tails', 'area': 'Edges', 'when': '2026-10-07', 'doc': 'alt-tails-results.md',
         'q': "Are alternate-line overs priced with a favourite-longshot shape, so some price bucket of them makes money?",
         'rule': "Bet the over at every ESPN alternate rung. Choose buckets on 2024-25 (1,000+ bets, return above zero, z >= 1.5), then judge them on 2025-26 (z >= 2.4, both halves positive).",
         'result': "Every bucket lost money on 2024-25, from about -50% on long shots to about -9% on heavy favourites, so none was chosen. The 2025-26 pre-tip data is too thin to judge anything.",
         'verdict': 'NO-GO', 'shipped': 'Nothing'},
    ]
    for e in log:
        e['when'] = (e['when'] or '')[:10]

    # ── What Works page: the Edge Finder's slices, the streak myth check, what does not work ──
    finder = {'model': {}, 'model_side': {}, 'cons': {}}
    for k, v in ((p2 or {}).get('blend_oos') or {}).items():
        d = v.get('v2') or {}
        finder['model'].setdefault('kalshi' if k.startswith('kalshi') else 'books', {})[k.split('/')[-1]] = \
            {t: [d[t]['n'], d[t]['games'], d[t]['win'], d[t]['roi'], d[t]['z']] for t in d if t.startswith('0.')}
    for m, by in ((p2 or {}).get('kalshi_bias') or {}).items():
        for sd in ('YES', 'NO'):
            b = by.get('v2', {}).get(f'blend/{sd}') or {}
            if b.get('n'):
                finder['model_side'].setdefault(m, {})[sd] = [b['n'], b['games'], None, b['roi'], b['z']]
    for test, by in ((cb or {}).get('tests') or {}).items():
        for m, d in by.items():
            for sd, b in ((d.get('bets') or {}).get('consensus + model') or {}).items():
                if b.get('n'):
                    finder['cons'].setdefault(test, {}).setdefault(m, {})[sd] = [b['n'], b['games'], None, b['roi'], b['z']]
    myth = None
    if hr:
        pick = lambda k: {'cal': hr['sets'][k]['calibration'], 'hot': hr['sets'][k]['rules']['L10 over (hit 8+ of 10)'],
                          'cold': hr['sets'][k]['rules']['L10 under (hit 2 or fewer of 10)'], 'base_under': hr['sets'][k]['rules']['Baseline: every under'],
                          'same': hr['sets'][k].get('same_price'), 'persist': hr['sets'][k]['persistence'], 'n': hr['sets'][k]['n']}
        myth = {'books': pick('espn2025_open'), 'books26': pick('espn2026_close'), 'kalshi': pick('kalshi2026')}
    dont = []
    if game:
        w = game['ats_close']['0']['win']
        dont.append(['Betting game spreads with our game model', f"The closing line already knows everything our model knows. Against the close the model's side won {w:.1%} of {game['games']:,} games; you need 52.4% to beat the vig.", 'Game model, 2024-25 and 2025-26'])
        dont.append(['Game totals', f"Our side won {game['ou_close']['0']['win']:.1%} against the closing total. The model's totals miss by more than the line does ({game['mae']['tip']['total']} vs {game['mae']['market_close']['total']} points).", 'Game model'])
        lost = sum(1 for r in game['kalshi']['ml'] if r[2] < 0)
        dont.append(['Kalshi game winners', f"At prices you could actually trade (1pm), betting where the model disagreed lost after fees at {lost} of {len(game['kalshi']['ml'])} edge sizes.", f"{game['kalshi']['sides']:,} sides"])
    if props:
        best = max(((m, r) for m, r in (finder['model'].get('books') or {}).items() if r.get('0.03')), key=lambda x: x[1]['0.03'][4], default=None)
        dont.append(['Sportsbook player props', 'Sportsbook prop lines are sharp: no stat passed.' + (f" The best, {SNAME.get(best[0], best[0])} at a 3% edge, returned {'+' if best[1]['0.03'][3] >= 0 else '-'}${abs(best[1]['0.03'][3]) * 100:.2f} per $100 but could easily be luck." if best else ''), 'ESPN lines, 2025-26'])
        dont.append(['Combo props (PRA, P+R, P+A, R+A)', 'No edge at any edge size on sportsbooks; Kalshi does not list them.', 'ESPN lines'])
        dont.append(['Buying overs (YES) on Kalshi', 'The mirror image of the bets that pass: YES is overpriced in every stat, so buying it loses unless our model finds a rare exception.', 'Kalshi, 2025-26'])
    dont.append(['Copying sharp bettors late', 'Accounts with a winning record do beat the closing price, but copying their side 30 minutes to 2 hours later lost money.', '31k Polymarket trades'])
    dont.append(['Following the biggest tickets', 'Size is not skill: even $100k+ tickets lost to the closing price on average.', 'Polymarket tape'])
    ex = load('prop_model_extra.json') or {}
    NAMES = {'stl': 'Steals', 'blk': 'Blocks', 'tov': 'Turnovers', 'sb': 'Steals + blocks', 'fgm': 'Field goals made', 'fga': 'Field goals attempted', 'ftm': 'Free throws made',
             'fta': 'Free throws attempted', 'tpa': '3-pointers attempted', 'oreb': 'Offensive rebounds', 'dreb': 'Defensive rebounds', 'pf': 'Personal fouls'}
    extra = []
    for m, nm in NAMES.items():
        a_, c_, e_ = (ex.get('accuracy') or {}).get(m), (ex.get('selfcheck') or {}).get(m), (ex.get('espn_2026') or {}).get(m)
        if not a_:
            continue
        extra.append({'m': m, 'name': nm, 'mae': a_['mae'], 'mean_actual': a_['mean_actual'], 'n': a_['n'],
                      'self': {'brier_model': c_['brier_model'], 'brier_base': c_['brier_base_rate']} if c_ else None,
                      'espn': {k: e_[k] for k in ('n_rows', 'brier_model', 'brier_market', 'logloss_model', 'logloss_market')} if e_ else None,
                      'verdict': (ex.get('verdict') or {}).get(m, 'NO-GO'),
                      'next': 'Scored against ESPN closing lines already; more main lines accumulate from opening night' if e_ else 'No price history: lines are collected from opening night, then a first test'})
    nb = ((nl.get('news') or {}).get('bets')) or 0
    pending = [
        {'name': 'Joint model of players\' stats (copula A2)', 'area': 'Game simulation', 'due': '2026-11-09', 'doc': 'copula-fit-a2.md',
         'rule': 'First look at 150 regular-season games: z >= 2.4 and an agreement slope whose interval contains 1 and excludes 0.', 'status': 'Frozen, waiting for 150 games'},
        {'name': 'Game-script minutes (B3)', 'area': 'Game simulation', 'due': '2026-11-16', 'doc': 'game-script-minutes-b3.md',
         'rule': 'All four B2 checks on 200 regular-season games with the model frozen.', 'status': 'Frozen, waiting for 200 games'},
        {'name': 'Minutes model v3 shadow review', 'area': 'Minutes', 'due': '2026-11-20', 'doc': 'minutes-v3-pricing.md',
         'rule': 'One month of live v3 shadow minutes against v2, then the pre-registered pricing rule can be re-run.', 'status': 'Shadow running'},
        {'name': 'News lag', 'area': 'Edges', 'due': '2026-11-23', 'doc': 'edge-tests-r2.md',
         'rule': 'Bets placed while a price is older than injury or lineup news: 150 settled bets over 25 days, ROI z >= 2.4, closing-line value z >= 2, both halves positive.', 'status': f'{nb} of 150 settled bets so far'},
        {'name': "Pick'em lines against Pinnacle", 'area': "Pick'em", 'due': '2026-11-23', 'doc': 'edge-tests-r2.md',
         'rule': "Pick the side with fair chance at least 3 points above the flex break-even: 150 picks over 40 games, hit rate above 54.25% at z >= 2.4, both halves above.", 'status': 'Rule frozen; Pinnacle props not posting in preseason'},
    ]
    out = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'doc': DOC,
           'signals': signals, 'log': log, 'pending': pending, 'extra': extra, 'finder': finder, 'myth': myth, 'dont': dont, 'game': game, 'minutes': minutes, 'usage': usage, 'props': props, 'consensus': consensus,
           'test': {'seasons': 'fit 2024-25, test 2025-26', 'player_games': (pf or {}).get('n_test'), 'games': (game or {}).get('games')}}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print(f"backtests: {len(log)} tests, {len(signals)} GO / WATCH signals -> {os.path.relpath(OUT)} ({os.path.getsize(OUT) // 1000} KB)")


if __name__ == '__main__':
    main()
