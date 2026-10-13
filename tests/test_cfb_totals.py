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

    def test_center_is_the_in_season_mean_before_the_week_and_the_prior_when_there_are_no_games(self):
        T = pd.DataFrame(dict(week=[1, 1, 2, 3], pts=[20.0, 30.0, 40.0, 100.0], nplays=[60.0, 70.0, 80.0, 99.0]))
        fb = dict(pts=27.0, pace=66.0)
        self.assertEqual(cm.totals_center(T, 1, fb), fb)                                   # nothing final before week 1: prior-years level
        self.assertEqual(cm.totals_center(T, 2, fb), dict(pts=25.0, pace=65.0))
        c = cm.totals_center(T, 3, fb); self.assertAlmostEqual(c['pts'], 30.0); self.assertAlmostEqual(c['pace'], 70.0)      # week 3 and later games never leak in
        self.assertEqual(cm.totals_center(T.iloc[0:0], 5, fb), fb)

    def test_walk_forward_centres_each_week_on_the_season_so_far(self):
        rng = np.random.default_rng(1); rows, games = [], []
        for w in range(1, 5):
            for g in range(20):
                h, a = rng.choice(8, 2, replace=False); gid = w * 100 + g; hp, ap = 20.0 + 3 * w, 10.0 + 3 * w
                games.append(dict(season=2024, week=w, game_id=gid, homeTeamId=int(h), awayTeamId=int(a), homeFinalScore=int(hp), awayFinalScore=int(ap), status_type_completed=True))
                for o, d, ho, pts in ((h, a, 1, hp), (a, h, -1, ap)):
                    rows.append(dict(season=2024, week=w, game_id=gid, pos_team_id=int(o), def_pos_team_id=int(d), home_off=ho, pts=pts, nplays=60.0 + w))
        tt, gm = pd.DataFrame(rows), pd.DataFrame(games); fbs = {2024: set(range(8))}
        res = cm.totals_walk_forward(tt, gm, fbs, [2024])
        # week 1: no finished game, so the prior-years level (here the season's own mean); week 4: the mean of weeks 1-3 only
        w3 = tt[tt.week < 4]; cen4 = dict(pts=w3.pts.mean(), pace=w3.nplays.mean())
        g4 = res[res.week == 4].iloc[0]; self.assertNotAlmostEqual(g4.pts_h + g4.pts_a, 2 * tt.pts.mean(), places=1)
        self.assertAlmostEqual((g4.pts_h + g4.pts_a) / 2, cen4['pts'], delta=3.0)

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

    def test_unproven_until_150_live_graded_3plus_and_secondary_rows_never_count(self):
        pick = lambda i, **k: dict(dict(week=5, edge=4.0, result='W', clv=1.0, backfill=False), **k)
        s = cm.totals_summary([pick(i) for i in range(149)] + [dict(pick(0), backfill=True), dict(pick(0), edge=1.0), dict(week=5, edge=None, result=None, dk_edge=6.0, dk_result='W', backfill=False)])
        self.assertEqual((s['proven_target'], s['live_graded_3plus'], s['status']), (150, 149, 'unproven'))      # backfill, sub-3 and secondary-only rows are not live 3+ picks
        s = cm.totals_summary([pick(i) for i in range(150)]); self.assertEqual((s['live_graded_3plus'], s['status']), (150, 'sample_reached'))
        self.assertEqual(cm.totals_summary([pick(i, backfill=True) for i in range(3)])['live_graded_3plus'], 0)


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

    def bv(self, gid=100, wk=5, ou=58.0, ouo=61.5, **k): return dict(dict(id=gid, wk=wk, home='Alpha', away='Beta', hs=30, as_=20, p='Bovada', sp=-3, so=-3, ou=ou, ouo=ouo), **k)
    def dk(self, gid=100, wk=5, ou=58.0, ouo=61.5, **k): return dict(dict(id=gid, wk=wk, home='Alpha', away='Beta', hs=30, as_=20, p='DraftKings', sp=-3, so=-3, ou=ou, ouo=ouo), **k)

    def run_update(self, prev=None, feed=None):
        return cm.totals_update('unused', self.g26, self.F, self.names, self.sid, prev, feed, 0)

    def season_games(self, pts, plays, weeks=(1, 2, 3)):
        """finished earlier-week team-games: every team scores `pts` on `plays` snaps, so the in-season league level is exactly that"""
        gs, rows = [], []
        for w in weeks:
            gid = w; gs.append(dict(game_id=gid, week=w, homeTeamId=1, awayTeamId=2, homeFinalScore=int(pts), awayFinalScore=int(pts), status_type_completed=True))
            for o, d, ho in ((1, 2, 1), (2, 1, -1)): rows.append(dict(game_id=gid, pos_team_id=o, def_pos_team_id=d, week=w, home_off=ho, pts=float(pts), nplays=float(plays)))
        self.g26 = pd.concat([pd.DataFrame(gs), self.g26], ignore_index=True)
        tt = pd.DataFrame(rows)
        cm.totals_load = lambda d, years: (tt, self.g26.assign(neutral_site=False))

    def test_under_edge_graded_against_the_bovada_open_with_clv_toward_our_side(self):
        # open 61.5: model 54.6 is 6.9 under it (5+); the game ends 50 total so the under wins; the close fell to 58, so CLV for an under is +3.5
        self.lines([self.bv()])
        r = self.run_update()['rows'][0]
        self.assertEqual((r['side'], r['flag'], r['result'], r['total']), ('under', '5+', 'W', 50))
        self.assertEqual((r['open'], r['open_src'], r['close'], r['clv']), (61.5, 'Bovada', 58.0, 3.5))
        self.assertAlmostEqual(r['model_total'], round(self.model, 2)); self.assertEqual(r['edge'], round(round(self.model, 2) - 61.5, 2))
        self.assertTrue(r['backfill']); self.assertEqual(r['totals_version'], cm.TOT_VERSION)

    def test_flag_and_grade_use_the_unrounded_edge(self):
        # model 58.5044 vs open 61.5: edge -2.9956 displays as -3.0 but is NOT a 3+ pick
        self.assertIsNone(cm._flag(-2.9956)); self.assertEqual((cm._flag(-3.0), cm._flag(4.99), cm._flag(-5.0)), ('3+', '3+', '5+'))
        self.assertEqual(cm._grade_total(58.5044, 61.5, 60.0, 50)[0], 'under')
        self.lines([self.bv(ou=60.0, ouo=61.5)]); saved = cm.totals_project
        cm.totals_project = lambda *a: (30.0, 28.5044, 130.0, 58.5044)
        try: r = self.run_update()['rows'][0]; s = self.run_update()['summary']['by_edge']
        finally: cm.totals_project = saved
        self.assertEqual((r['edge'], r['flag']), (-3.0, None)); self.assertAlmostEqual(r['edge_raw'], -2.9956, 6)
        self.assertEqual(s['3']['n'], 0)
        self.assertEqual(cm.totals_summary([dict(week=5, edge=-3.0, edge_raw=-2.9956, result='W', clv=1.0)])['by_edge']['3']['n'], 0)

    def test_over_loses_and_push_is_a_push(self):
        self.lines([self.bv(ou=50.0, ouo=50.0)])
        r = self.run_update()['rows'][0]
        self.assertEqual((r['side'], r['result'], r['clv']), ('over', 'P', 0.0))      # model 54.6 over 50, final total 50 exactly
        self.g26.loc[:, 'homeFinalScore'] = 20
        r = self.run_update()['rows'][0]; self.assertEqual((r['total'], r['result']), (40, 'L'))

    def test_primary_is_bovada_and_draftkings_rides_along_as_secondary(self):
        self.lines([self.bv(ou=57.0, ouo=58.0), self.dk(ou=59.0, ouo=60.0)])
        m = cm.market_totals(self.sid)[100]
        self.assertEqual((m['open'], m['open_src'], m['close'], m['close_src'], m['dk_open'], m['dk_close']), (58.0, 'Bovada', 57.0, 'Bovada', 60.0, 59.0))
        r = self.run_update()['rows'][0]
        self.assertEqual((r['open'], r['close'], r['result'], r['clv']), (58.0, 57.0, 'W', 1.0))      # model 54.6 is under 58, final 50: the under wins, and the close fell 1 toward it
        self.assertEqual((r['dk_open'], r['dk_open_src'], r['dk_close'], r['dk_side'], r['dk_result'], r['dk_clv']), (60.0, 'DraftKings', 59.0, 'under', 'W', 1.0))
        self.assertAlmostEqual(r['dk_edge'], round(round(self.model, 2) - 60.0, 2))
        json.dump([dict(id=100, wk=5, home='Alpha', away='Beta', so=-3, ouo=61.0)], open(os.path.join(cm.ROOT, 'data', 'cfbd', 'espn_opens_2026.json'), 'w'))
        m = cm.market_totals(self.sid)[100]; self.assertEqual((m['dk_open'], m['dk_open_src'], m['dk_close'], m['open']), (61.0, 'ESPN', 59.0, 58.0))      # ESPN's recorded DK open wins over CFBD's

    def test_no_bovada_open_means_no_graded_pick_and_draftkings_is_secondary_only(self):
        self.lines([self.dk(ou=58.0, ouo=61.5)])
        out = self.run_update(); r = out['rows'][0]
        self.assertIsNone(r['open']); self.assertIsNone(r['edge']); self.assertIsNone(r['side']); self.assertIsNone(r['flag']); self.assertNotIn('result', r)
        self.assertEqual((r['dk_open'], r['dk_result'], r['dk_clv']), (61.5, 'W', 3.5))
        self.assertEqual(out['summary']['by_edge']['3']['n'], 0); self.assertEqual(out['summary']['live_graded_3plus'], 0)       # never in the record
        self.lines([self.bv(ou=58.0, ouo=None), self.dk()])                             # a Bovada row with no stored open is no open either
        self.assertIsNone(self.run_update()['rows'][0]['open'])

    def test_nothing_is_invented_when_a_number_is_missing(self):
        self.lines([self.bv(ou=None, ouo=61.5)])
        r = self.run_update()['rows'][0]; self.assertIsNone(r['close']); self.assertIsNone(r['clv']); self.assertEqual(r['result'], 'W')
        self.lines([self.bv(ou=58.0, ouo=None)])
        self.assertEqual(self.run_update()['rows'], [])                                 # no stored open at all, no row

    def test_league_level_is_the_in_season_mean_before_the_week(self):
        self.season_games(35, 70)                                                       # weeks 1-3: every team-game 35 pts on 70 plays
        self.lines([self.bv()])
        r = self.run_update()['rows'][0]
        self.assertAlmostEqual(r['model_total'], round(-10.12 + 0.797 * 70 + 0.150 * 140, 2)); self.assertEqual((r['league_pts'], r['league_plays']), (35.0, 70.0))

    def test_league_level_falls_back_to_the_prior_years_mean_with_no_finished_games(self):
        self.lines([self.bv()])
        r = self.run_update()['rows'][0]; self.assertEqual((r['league_pts'], r['league_plays']), (28.0, 67.0)); self.assertAlmostEqual(r['model_total'], round(self.model, 2))

    def test_graded_v2_rows_are_frozen_and_early_weeks_are_skipped(self):
        self.lines([self.bv(), self.bv(gid=101, wk=3)])
        first = self.run_update(); self.assertEqual([r['game_id'] for r in first['rows']], [100])
        self.lines([self.bv(ou=99.0, ouo=99.0)])                                        # the book later changes its stored numbers
        again = self.run_update(first)['rows'][0]; self.assertEqual((again['open'], again['close'], again['result']), (61.5, 58.0, 'W'))

    def test_a_v1_graded_row_is_rebuilt_once_then_frozen(self):
        self.lines([self.bv(ou=58.0, ouo=61.5), self.dk(ou=59.0, ouo=60.0)])
        v1 = dict(game_id=100, week=5, open=40.0, open_src='DraftKings', edge=14.0, side='over', flag='5+', result='L', close=41.0, clv=1.0, backfill=False, upcoming=False)
        r = self.run_update(dict(rows=[v1]))['rows'][0]
        self.assertEqual((r['totals_version'], r['open'], r['open_src'], r['result']), (cm.TOT_VERSION, 61.5, 'Bovada', 'W'))
        self.assertTrue(r['backfill'])                                                  # the v2 pick was not logged before the game, so it is not a live pick
        self.lines([self.bv(ou=99.0, ouo=99.0)])
        self.assertEqual(self.run_update(dict(rows=[r]))['rows'][0]['open'], 61.5)

    def test_a_game_not_yet_played_is_flagged_live_with_the_current_number(self):
        self.g26 = self.g26.iloc[0:0]
        self.lines([self.bv(gid=200, wk=1, ou=50, ouo=50), self.bv(gid=201, wk=1, hs=None, as_=None, ou=57.0, ouo=58.0)])
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
        self.picks = [r for r in self.t['rows'] if r.get('open') is not None]

    def test_rows_have_the_documented_fields(self):
        need = {'game_id', 'week', 'home_id', 'away_id', 'home', 'away', 'model_pts_home', 'model_pts_away', 'model_plays', 'model_total', 'open', 'open_src', 'edge', 'side', 'flag', 'backfill', 'upcoming', 'totals_version'}
        for r in self.t['rows']:
            self.assertTrue(need <= set(r), r); self.assertGreaterEqual(r['week'], 4); self.assertEqual(r['totals_version'], cm.TOT_VERSION)
            if r['open'] is None: self.assertIsNone(r['edge']); self.assertIsNone(r['side']); self.assertIsNone(r['flag']); continue      # secondary-only row: no pick
            self.assertEqual(r['open_src'], 'Bovada')
            self.assertIn(r['side'], ('over', 'under')); self.assertEqual(r['flag'], cm._flag(r['edge_raw'])); self.assertEqual(r['edge'], round(r['edge_raw'], 2))
            if not r['upcoming']: self.assertIn(r['result'], ('W', 'L', 'P')); self.assertEqual(r['total'], r['hs'] + r['as_'])

    def test_result_and_clv_recompute_from_stored_numbers(self):
        for r in self.picks:
            if r['upcoming']: continue
            sg = 1 if r['edge_raw'] > 0 else -1; d = (r['total'] - r['open']) * sg
            self.assertEqual(r['result'], 'W' if d > 0 else 'L' if d < 0 else 'P')
            self.assertEqual(r['clv'], None if r['close'] is None else round((r['close'] - r['open']) * sg, 1))

    def test_draftkings_secondary_recomputes_from_stored_numbers(self):
        for r in self.t['rows']:
            if r.get('dk_open') is None: continue
            self.assertEqual(r['dk_edge'], round(r['dk_edge_raw'], 2))
            if r['upcoming']: continue
            sg = 1 if r['dk_edge_raw'] > 0 else -1; d = (r['total'] - r['dk_open']) * sg
            self.assertEqual(r['dk_result'], 'W' if d > 0 else 'L' if d < 0 else 'P')
            self.assertEqual(r['dk_clv'], None if r.get('dk_close') is None else round((r['dk_close'] - r['dk_open']) * sg, 1))

    def test_summary_matches_rows(self):
        for k in ('3', '5'):
            sel = [r for r in self.picks if abs(r['edge_raw']) >= int(k)]
            self.assertEqual(self.t['summary']['by_edge'][k], cm._totals_rec(sel))
        s = self.t['summary']; live3 = sum(1 for r in self.picks if not r['backfill'] and abs(r['edge_raw']) >= 3 and r.get('result'))
        self.assertEqual((s['proven_target'], s['live_graded_3plus']), (cm.TOT_PROVEN_TARGET, live3)); self.assertEqual(s['status'], 'unproven' if live3 < 150 else 'sample_reached')

    def test_backtest_is_the_computed_one(self):
        self.assertEqual(self.t['backtest'], cm.TOT_BACKTEST)


if __name__ == '__main__':
    unittest.main()
