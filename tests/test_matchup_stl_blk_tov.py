import os, sys, unittest
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import test_matchup_stl_blk_tov as M  # noqa: E402


def row(team, fga, tpa, fta, tov, oreb, mins=48.0):
    return {"team": team, "played": True, "field_goals_attempted": fga, "three_point_field_goals_attempted": tpa, "free_throws_attempted": fta,
            "turnovers": tov, "offensive_rebounds": oreb, "minutes": mins}


class Pieces(unittest.TestCase):
    def test_solve2_recovers_two_slopes(self):
        rows = [(float(i), float((i * 7) % 5), 2.0 * i + 3.0 * ((i * 7) % 5)) for i in range(1, 30)]
        b1, b2 = M.solve2(M.sums(rows))
        self.assertAlmostEqual(b1, 2.0, places=6)
        self.assertAlmostEqual(b2, 3.0, places=6)

    def test_sample_assigns_each_side_the_right_turnovers_and_one_shared_pace(self):
        g = {"game_id": 1, "away": "AAA", "home": "BBB"}
        box = {1: [row("AAA", 80, 30, 20, 12, 8, 240.0), row("BBB", 90, 40, 25, 15, 10, 240.0)]}
        s = M.sample(M.team_games(box, [g]), g)
        f = 48.0 / 48.0                                                          # 240 player-minutes / 5 = 48
        self.assertAlmostEqual(s["AAA"]["tov_comm"], 12 * f)
        self.assertAlmostEqual(s["AAA"]["tov_forced"], 15 * f)                  # AAA's defense forces BBB's 15
        self.assertAlmostEqual(s["BBB"]["tov_forced"], 12 * f)
        self.assertAlmostEqual(s["AAA"]["twopa"], 50 * f)
        self.assertEqual(s["AAA"]["pace"], s["BBB"]["pace"])
        self.assertAlmostEqual(s["AAA"]["pace"], ((80 + 0.44 * 20 + 12 - 8) + (90 + 0.44 * 25 + 15 - 10)) / 2)

    def test_league_mean_must_be_over_exactly_30_teams(self):
        def tables(n):
            teams = ["T%d" % i for i in range(n)]
            cur = {"sum": defaultdict(lambda: defaultdict(float)), "n": defaultdict(int)}
            prior = {t: {k: 10.0 + i for k in M.KEYS} for i, t in enumerate(teams)}
            return M.vs_table(cur, prior, teams)
        t = tables(30)
        self.assertAlmostEqual(sum(v["pace"] for v in t.values()) / 30, 0.0, places=9)
        with self.assertRaises(AssertionError):
            tables(31)


if __name__ == "__main__":
    unittest.main()
