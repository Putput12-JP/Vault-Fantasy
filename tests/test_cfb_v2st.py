"""The CFB model's v2 prior + special teams promotion: restating the stored board and log, and the special teams ratings."""
import os, sys, unittest
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cfb_model as cm
import cfb_v2_st_study as sts


def row(**kw):
    b = dict(key='cfb:1', week=6, kick=1000, home='Home U', away='Away U', home_id=1, away_id=2, neutral=False, model_margin=10.0, market_margin=3.0, edge=7.0,
             side='home', team='Home U', entry=-3.0, is_pick=True, pick=dict(side='home', team='Home U', line=-3.0), logged=500, backfill=False,
             result='W', hs=30, as_=20, margin=10, espn_close=-3.5, clv=0.5, tile_result='W')
    b.update(kw); return b


class Restate(unittest.TestCase):
    def test_same_side_changes_margin_and_keeps_old_as_v1(self):
        b = cm.restate_row(row(), lambda wk, h, a, n: 12.0)
        self.assertEqual((b['model_margin'], b['edge'], b['side'], b['entry']), (12.0, 9.0, 'home', -3.0))
        self.assertEqual((b['v1']['model_margin'], b['v1']['edge'], b['v1']['is_pick']), (10.0, 7.0, True))
        for k in ('result', 'hs', 'margin', 'clv', 'tile_result'): self.assertNotIn(k, b)

    def test_flipped_side_flips_the_line_and_the_captured_line(self):
        b = cm.restate_row(row(line_captured=-3.0), lambda wk, h, a, n: -4.0)
        self.assertEqual((b['side'], b['team'], b['entry'], b['edge']), ('away', 'Away U', 3.0, -7.0))
        self.assertEqual(b['line_captured'], 3.0)
        self.assertTrue(b['is_pick']); self.assertEqual(b['pick']['line'], 3.0)

    def test_under_five_is_not_a_pick_and_early_weeks_never_are(self):
        self.assertFalse(cm.restate_row(row(), lambda wk, h, a, n: 6.0)['is_pick'])
        self.assertFalse(cm.restate_row(row(week=3), lambda wk, h, a, n: 30.0)['is_pick'])

    def test_lock_state_is_restated_at_its_own_line(self):
        b = cm.restate_row(row(final=dict(side='home', team='Home U', entry=-2.0, edge=8.0, is_pick=True, at=900, mins_before=2, cards=None)), lambda wk, h, a, n: 4.0)
        self.assertEqual((b['final']['side'], b['final']['entry'], b['final']['edge'], b['final']['is_pick']), ('home', -2.0, 2.0, False))

    def test_bettable_open_follows_the_new_side(self):
        b = cm.restate_row(row(bettable_open=dict(line=-3.0, side='home', entry=-3.0, model_margin=10.0, edge=7.0, result='W', clv=1.0)), lambda wk, h, a, n: -4.0)
        self.assertEqual((b['bettable_open']['side'], b['bettable_open']['entry']), ('away', 3.0)); self.assertNotIn('result', b['bettable_open'])

    def test_a_row_without_a_projection_is_left_alone(self):
        b = row(model_margin=None); self.assertIs(cm.restate_row(b, lambda *a: 1.0), b); self.assertNotIn('v1', b)


class RestateLog(unittest.TestCase):
    def test_log_is_the_current_picks(self):
        board = [cm.restate_row(row(key='cfb:1', market_margin=-3.0, entry=3.0), lambda *a: 12.0), cm.restate_row(row(key='cfb:2'), lambda *a: 4.0), cm.restate_row(row(key='cfb:3', logged=700), lambda *a: -9.0),
                 cm.restate_row(row(key='cfb:4'), lambda *a: 12.0)]      # cfb:4 is 9 points off but on the favorite: not a pick under the current rule
        log = [dict(key='cfb:1', week=6, kick=1000, home='Home U', away='Away U', home_id=1, away_id=2, side='home', team='Home U', entry=-3.0, logged=500, backfill=False, result='W', hs=1),
               dict(key='cfb:2', week=6, kick=1000, home='Home U', away='Away U', home_id=1, away_id=2, side='home', team='Home U', entry=-3.0, logged=500, backfill=False)]
        out = {e['key']: e for e in cm.restate_log(board, log)}
        self.assertEqual(set(out), {'cfb:1', 'cfb:3'})                                       # cfb:2 is under the bar, cfb:4 is a favorite pick
        self.assertEqual((out['cfb:1']['logged'], out['cfb:1']['backfill']), (500, False))    # same side: keeps its logged time and flag
        self.assertNotIn('result', out['cfb:1'])                                             # and is graded again
        self.assertTrue(out['cfb:3']['backfill']); self.assertEqual(out['cfb:3']['side'], 'away')   # new pick: a point-in-time reconstruction


class SpecialTeams(unittest.TestCase):
    def test_ratings_follow_the_games_and_shrink(self):
        rng = np.random.default_rng(0); rows = []
        for _ in range(200):
            h, a = rng.choice(8, 2, replace=False); rows.append((int(h), int(a), (3.0 if h == 0 else 0.0) - (3.0 if a == 0 else 0.0) + rng.normal(0, 1)))
        o = pd.DataFrame(rows, columns=['home_id', 'away_id', 'st_home'])
        r = sts.st_ratings(o, {}, 5)
        self.assertGreater(r[0], 2.0); self.assertLess(r[0], 3.2)
        self.assertEqual(sts.st_ratings(o.head(10), {1: 0.7}, 5), {1: 0.7})                  # too few games: the prior, untouched

    def test_prior_is_the_centre(self):
        o = pd.DataFrame([(0, 1, 0.0)] * 40, columns=['home_id', 'away_id', 'st_home'])
        r = sts.st_ratings(o, {0: 1.0, 1: -1.0}, 5)
        self.assertGreater(r[0], 0.0); self.assertLess(r[1], 0.0)


if __name__ == '__main__':
    unittest.main()
