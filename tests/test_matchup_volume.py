import os, sys, unittest
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import test_matchup_volume as M  # noqa: E402


class Pieces(unittest.TestCase):
    def test_slope_through_origin(self):
        rows = [(x, 0.5 * x) for x in (1.0, 2.0, 3.0)]
        self.assertAlmostEqual(M.slope(rows), 0.5)

    def test_shares_blend_the_prior_until_the_current_season_is_deep(self):
        cur, prior = {"a": 10.0}, {"b": 100.0}
        sh, n = M.shares(cur, prior, 200.0, ["a", "b"])
        self.assertAlmostEqual(n, 10 + (1 - 10 / 200) * 100)
        self.assertAlmostEqual(sum(sh.values()), 1.0)
        sh2, n2 = M.shares({"a": 300.0}, prior, 200.0, ["a", "b"])             # deep enough: the prior has no weight
        self.assertAlmostEqual(sh2["a"], 1.0)
        self.assertEqual(M.shares(None, None, 200.0, ["a"])[0], None)

    def test_vs_tables_zero_before_any_information_and_relative_to_league_after(self):
        cur_allow, cur_g = defaultdict(lambda: defaultdict(float)), defaultdict(set)
        self.assertEqual(M.vs_tables(cur_allow, cur_g, None), {})                 # no prior and no games: nothing to say
        prior = {"A": {("z", k): 10.0 for k in M.ZK} | {("a", k): 5.0 for k in M.AK}, "B": {("z", k): 20.0 for k in M.ZK} | {("a", k): 5.0 for k in M.AK}}
        t = M.vs_tables(cur_allow, cur_g, prior)
        self.assertAlmostEqual(t["A"][("z", "c3")], 10 / 15 - 1)
        self.assertAlmostEqual(t["B"][("z", "c3")], 20 / 15 - 1)
        self.assertAlmostEqual(t["A"][("a", "rim")], 0.0)


if __name__ == "__main__":
    unittest.main()
