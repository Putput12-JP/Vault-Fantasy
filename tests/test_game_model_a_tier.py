import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import test_game_model_a_tier as T  # noqa: E402


class Rules(unittest.TestCase):
    def game(self, res, L, model, news=0.0, day_n=40):
        return T.make_game(res, L, model, news, day_n)

    def test_home_pick_covers_when_result_beats_the_line(self):
        g = self.game(res=8, L=3, model=9)             # model likes home by 6 more than the line; home wins by 8 against a 3-point line
        self.assertTrue(g["home"]); self.assertAlmostEqual(g["edge"], 6); self.assertGreater(g["cover"], 0)

    def test_away_pick_underdog_flag(self):
        g = self.game(res=2, L=7, model=1)            # the line has home by 7, the model has home by 1: away +7 is the pick (edge 6)
        self.assertFalse(g["home"]); self.assertTrue(g["dog"]); self.assertGreater(g["cover"], 0)

    def test_no_edge_is_no_game(self):
        self.assertIsNone(self.game(res=3, L=3, model=3))

    def test_fade_is_the_opposite_side_and_pushes_are_skipped(self):
        gs = [self.game(8, 3, 9), self.game(0, 3, 9), self.game(3, 3, 9)]      # win, loss, push (all A: edge 6)
        self.assertEqual(T.rule_games(gs, "S0 all A, followed"), (1, 1))
        self.assertEqual(T.rule_games(gs, "S1 all A, faded"), (1, 1))
        self.assertEqual(T.rule_games([self.game(8, 3, 9)], "S1 all A, faded"), (0, 1))

    def test_below_the_tier_is_not_counted(self):
        self.assertEqual(T.rule_games([self.game(8, 3, 6)], "S0 all A, followed"), (0, 0))   # edge 3

    def test_early_split(self):
        g = [self.game(8, 3, 9, day_n=5), self.game(8, 3, 9, day_n=60)]
        self.assertEqual(T.rule_games(g, "S7 A in the first 28 days"), (1, 0))
        self.assertEqual(T.rule_games(g, "S6 A after day 28"), (1, 0))


if __name__ == "__main__":
    unittest.main()
