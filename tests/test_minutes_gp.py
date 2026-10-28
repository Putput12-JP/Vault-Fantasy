"""GP (docs/minutes-bakeoff-results.md): the pool's expected minutes sum to T, covered players are priced on GP, and v2 stays where GP cannot run."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nba', 'scripts'))
import pricing as PX


class GP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pr = PX.Pricer(example=False)
        cls.tip = max(cls.pr.state['team_last'].values()) + 3 * 86400
        cls.team = sorted(cls.pr.state['teams'])[0]
        cls.opp = sorted(cls.pr.state['teams'])[7]

    def game(self, **kw):
        return dict({'id': 'gp1', 'tip': self.tip, 'home': self.team, 'away': self.opp, 'spread': -4.5, 'total': 224.5, 'season_type': 2}, **kw)

    def test_expected_minutes_sum_to_T(self):
        gm = self.pr.game_minutes(self.team, self.game(), {}, {})
        cov = [v for v in gm.values() if v['p_plays'] is not None]
        self.assertGreaterEqual(len(cov), 7)
        self.assertAlmostEqual(sum(v['min'] * v['p_plays'] for v in cov if v['min'] < 48), self.pr.ROTM['T'], delta=1.0)

    def test_priced_minutes_are_gp_not_v2(self):
        gm = self.pr.game_minutes(self.team, self.game(), {}, {})
        self.assertTrue(any(abs(v['min'] - v['min_v2']) > 0.5 for v in gm.values() if v['p_plays'] is not None))
        self.assertTrue(all(0 <= v['min'] <= 48 for v in gm.values()))

    def test_preseason_stays_v2(self):
        gm = self.pr.game_minutes(self.team, self.game(season_type=1), {}, {})
        self.assertTrue(gm and all(v['p_plays'] is None for v in gm.values()))

    def test_out_player_gets_no_minutes(self):
        g = self.game()
        gm = self.pr.game_minutes(self.team, g, {}, {})
        star = max(gm, key=lambda a: gm[a]['min'])
        gm2 = self.pr.game_minutes(self.team, g, {star: 'Out'}, {})
        self.assertNotIn(star, gm2)


if __name__ == '__main__':
    unittest.main()
