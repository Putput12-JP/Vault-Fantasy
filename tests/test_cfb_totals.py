"""CFB totals line contracts. No network, no real play-by-play: synthetic team-games and temp lines files.

Run from the repo root: python3 -m unittest discover -s tests -p 'test_cfb_totals.py'
"""
import json, os, sys, tempfile, unittest
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cfb_model as cm


class Formula(unittest.TestCase):
    def test_constants_are_the_2022_fit(self):
        self.assertEqual((cm.TOT_B0, cm.TOT_B1, cm.TOT_B2), (-10.12, 0.797, 0.150))
        self.assertEqual(cm.TOT_EDGES, (3, 5))

    def test_project_is_league_level_plus_offense_plus_opponent_defense(self):
        cur = {'pts': ({1: 3.0, 2: -1.0}, {1: -2.0, 2: 4.0}), 'pace': ({1: 2.0, 2: 0.0}, {1: 1.0, 2: -1.0})}
        cen = {'pts': 28.0, 'pace': 67.0}
        ph, pa, pl, tot = cm.totals_project(cur, cen, 1, 2)
        self.assertAlmostEqual(ph, 28 + 3.0 + 4.0); self.assertAlmostEqual(pa, 28 - 1.0 - 2.0)
        self.assertAlmostEqual(pl, (67 + 2.0 - 1.0) + (67 + 0.0 + 1.0))
        self.assertAlmostEqual(tot, -10.12 + 0.797 * (ph + pa) + 0.150 * pl)

    def test_unknown_team_falls_back_to_league_level(self):
        cur = {'pts': ({}, {}), 'pace': ({}, {})}
        ph, pa, pl, tot = cm.totals_project(cur, {'pts': 28.0, 'pace': 67.0}, 9, 8)
        self.assertEqual((ph, pa, pl), (28.0, 28.0, 134.0))

    def test_fit_moves_ratings_toward_the_data_and_keeps_the_prior_without_data(self):
        rng = np.random.default_rng(0); rows = []
        for g in range(120):
            h, a = rng.choice(6, 2, replace=False)
            for o, d, ho in ((h, a, 1), (a, h, -1)):
                rows.append(dict(pos_team_id=int(o), def_pos_team_id=int(d), home_off=ho, pts=40.0 if o == 0 else 20.0))
        obs = pd.DataFrame(rows)
        a, b = cm.totals_fit(obs, 'pts', {}, {}, 28.0)
        self.assertGreater(a[0], a[1])                       # team 0 scores more than the rest
        pa, pb = {7: 1.5}, {7: -0.5}
        a2, b2 = cm.totals_fit(obs.head(10), 'pts', pa, pb, 28.0)      # fewer than 30 rows: the prior comes back untouched
        self.assertEqual((a2, b2), (pa, pb))

    def test_summary_record_and_clv(self):
        rows = [dict(edge=4, result='W', clv=1.0), dict(edge=-6, result='L', clv=-0.5), dict(edge=3.5, result='P', clv=0.0), dict(edge=5, result=None), dict(edge=1, result='W', clv=2.0)]
        s = cm.totals_summary([dict(r, week=5) for r in rows])['by_edge']
        self.assertEqual((s['3']['won'], s['3']['lost'], s['3']['pushed'], s['3']['pending'], s['3']['n']), (1, 1, 1, 1, 4))
        self.assertEqual(s['3']['pct'], 0.5); self.assertEqual(s['3']['clv_n'], 3); self.assertAlmostEqual(s['3']['clv_mean'], 0.167, 3)
        self.assertEqual((s['5']['n'], s['5']['graded'], s['5']['lost']), (2, 1, 1))     # edges 5 and -6, with 5 not yet played


class Update(unittest.TestCase):
    """totals_update end to end on a made-up two-team league, through temp files"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); t = self.tmp.name
        os.makedirs(os.path.join(t, 'data', 'cfbd'))
        self.saved = (cm.ROOT, cm.LINES26, cm.TOTALS_PRIORS, cm.totals_load)
        cm.ROOT = t; cm.LINES26 = os.path.join(t, 'data', 'cfbd', 'lines_2026.json'); cm.TOTALS_PRIORS = os.path.join(t, 'pri.json')
        json.dump(dict(center=dict(pts=28.0, pace=67.0), pts=dict(a={'1': 0.0, '2': 0.0}, b={'1': 0.0, '2': 0.0}), pace=dict(a={'1': 0.0, '2': 0.0}, b={'1': 0.0, '2': 0.0})), open(cm.TOTALS_PRIORS, 'w'))
        # league level 28 + 28 pts and 134 plays projects -10.12 + 0.797 * 56 + 0.150 * 134 = 54.642
        self.model = -10.12 + 0.797 * 56 + 0.150 * 134
        self.g26 = pd.DataFrame([dict(game_id=100, week=5, homeTeamId=1, awayTeamId=2, homeFinalScore=30, awayFinalScore=20, status_type_completed=True)])
        tt = pd.DataFrame(columns=['game_id', 'pos_team_id', 'def_pos_team_id', 'week', 'home_off', 'pts', 'nplays'])
        cm.totals_load = lambda d, years: (tt, self.g26.assign(neutral_site=False))
        self.F = {1, 2}; self.names = {1: ['Alpha', 'A', 'Alpha'], 2: ['Beta', 'B', 'Beta']}; self.sid = {'Alpha': 1, 'Beta': 2}

    def tearDown(self):
        cm.ROOT, cm.LINES26, cm.TOTALS_PRIORS, cm.totals_load = self.saved; self.tmp.cleanup()

    def lines(self, rows): json.dump(rows, open(cm.LINES26, 'w'))

    def run_update(self, prev=None, feed=None):
        return cm.totals_update('unused', self.g26, self.F, self.names, self.sid, prev, feed, 0)

    def test_under_edge_graded_against_the_open_with_clv_toward_our_side(self):
        # open 61.5: model 54.6 is 6.9 under it (5+); the game ends 50 total so the under wins; the close fell to 58, so CLV for an under is +3.5
        self.lines([dict(id=100, wk=5, home='Alpha', away='Beta', hs=30, as_=20, p='DraftKings', sp=-3, so=-3, ou=58.0, ouo=61.5)])
        r = self.run_update()['rows'][0]
        self.assertEqual((r['side'], r['flag'], r['result'], r['total']), ('under', '5+', 'W', 50))
        self.assertEqual((r['open'], r['close'], r['clv']), (61.5, 58.0, 3.5))
        self.assertAlmostEqual(r['model_total'], round(self.model, 2)); self.assertEqual(r['edge'], round(round(self.model, 2) - 61.5, 2))
        self.assertTrue(r['backfill'])

    def test_over_loses_and_push_is_a_push(self):
        self.lines([dict(id=100, wk=5, home='Alpha', away='Beta', hs=30, as_=20, p='DraftKings', sp=-3, so=-3, ou=50.0, ouo=50.0)])
        r = self.run_update()['rows'][0]
        self.assertEqual((r['side'], r['result'], r['clv']), ('over', 'P', 0.0))      # model 54.6 over 50, final total 50 exactly
        self.g26.loc[:, 'homeFinalScore'] = 20
        r = self.run_update()['rows'][0]; self.assertEqual((r['total'], r['result']), (40, 'L'))

    def test_open_is_espn_else_cfbd_and_close_is_the_same_book(self):
        self.lines([dict(id=100, wk=5, home='Alpha', away='Beta', hs=30, as_=20, p='Bovada', sp=-3, so=-3, ou=57.0, ouo=58.0),
                    dict(id=100, wk=5, home='Alpha', away='Beta', hs=30, as_=20, p='DraftKings', sp=-3, so=-3, ou=59.0, ouo=60.0)])
        m = cm.market_totals(self.sid)[100]; self.assertEqual((m['open'], m['open_src'], m['close'], m['close_src']), (60.0, 'DraftKings', 59.0, 'DraftKings'))
        json.dump([dict(id=100, wk=5, home='Alpha', away='Beta', so=-3, ouo=61.0)], open(os.path.join(cm.ROOT, 'data', 'cfbd', 'espn_opens_2026.json'), 'w'))
        m = cm.market_totals(self.sid)[100]; self.assertEqual((m['open'], m['close']), (61.0, 59.0))

    def test_nothing_is_invented_when_a_number_is_missing(self):
        self.lines([dict(id=100, wk=5, home='Alpha', away='Beta', hs=30, as_=20, p='DraftKings', sp=-3, so=-3, ou=None, ouo=61.5)])
        r = self.run_update()['rows'][0]; self.assertIsNone(r['close']); self.assertIsNone(r['clv']); self.assertEqual(r['result'], 'W')
        self.lines([dict(id=100, wk=5, home='Alpha', away='Beta', hs=30, as_=20, p='DraftKings', sp=-3, so=-3, ou=58.0, ouo=None)])
        self.assertEqual(self.run_update()['rows'], [])                                 # no stored open, no row

    def test_graded_rows_are_frozen_and_early_weeks_are_skipped(self):
        self.lines([dict(id=100, wk=5, home='Alpha', away='Beta', hs=30, as_=20, p='DraftKings', sp=-3, so=-3, ou=58.0, ouo=61.5),
                    dict(id=101, wk=3, home='Alpha', away='Beta', hs=30, as_=20, p='DraftKings', sp=-3, so=-3, ou=58.0, ouo=61.5)])
        first = self.run_update(); self.assertEqual([r['game_id'] for r in first['rows']], [100])
        self.lines([dict(id=100, wk=5, home='Alpha', away='Beta', hs=30, as_=20, p='DraftKings', sp=-3, so=-3, ou=99.0, ouo=99.0)])    # the book later changes its stored numbers
        again = self.run_update(first)['rows'][0]; self.assertEqual((again['open'], again['close'], again['result']), (61.5, 58.0, 'W'))

    def test_a_game_not_yet_played_is_flagged_live_with_the_current_number(self):
        self.g26 = self.g26.iloc[0:0]
        self.lines([dict(id=200, wk=1, home='Alpha', away='Beta', hs=1, as_=0, p='DraftKings', sp=-3, so=-3, ou=50, ouo=50),
                    dict(id=201, wk=1, home='Alpha', away='Beta', hs=None, as_=None, p='DraftKings', sp=-3, so=-3, ou=57.0, ouo=58.0)])
        # weeks before 4 never appear; the upcoming one needs the next-slate rule (no games done yet, week 1 only), so none show: no placeholders
        self.assertEqual(self.run_update()['rows'], [])

    def test_missing_priors_file_means_no_totals(self):
        os.remove(cm.TOTALS_PRIORS); self.assertIsNone(self.run_update())


class StoredData(unittest.TestCase):
    """the committed data file: schema and internal consistency, so the UI can rely on it"""
    def setUp(self):
        p = os.path.join(ROOT, 'data', 'cfb_model.json')
        self.t = json.load(open(p)).get('totals')
        if not self.t: self.skipTest('no totals section yet')

    def test_rows_have_the_documented_fields(self):
        need = {'game_id', 'week', 'home_id', 'away_id', 'home', 'away', 'model_pts_home', 'model_pts_away', 'model_plays', 'model_total', 'open', 'open_src', 'edge', 'side', 'flag', 'backfill', 'upcoming'}
        for r in self.t['rows']:
            self.assertTrue(need <= set(r), r); self.assertGreaterEqual(r['week'], 4)
            self.assertIn(r['side'], ('over', 'under')); self.assertEqual(r['flag'], '5+' if abs(r['edge']) >= 5 else '3+' if abs(r['edge']) >= 3 else None)
            if not r['upcoming']: self.assertIn(r['result'], ('W', 'L', 'P')); self.assertEqual(r['total'], r['hs'] + r['as_'])

    def test_result_and_clv_recompute_from_stored_numbers(self):
        for r in self.t['rows']:
            if r['upcoming']: continue
            sg = 1 if r['edge'] > 0 else -1; d = (r['total'] - r['open']) * sg
            self.assertEqual(r['result'], 'W' if d > 0 else 'L' if d < 0 else 'P')
            self.assertEqual(r['clv'], None if r['close'] is None else round((r['close'] - r['open']) * sg, 1))

    def test_summary_matches_rows(self):
        for k in ('3', '5'):
            sel = [r for r in self.t['rows'] if abs(r['edge']) >= int(k)]
            self.assertEqual(self.t['summary']['by_edge'][k], cm._totals_rec(sel))


if __name__ == '__main__':
    unittest.main()
