import os, sys, unittest
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import test_matchup_points_rebounds as M  # noqa: E402


def row(team, fga, fgm, pts, ftm, mins=48.0):
    return {"team": team, "played": True, "field_goals_attempted": fga, "field_goals_made": fgm, "points": pts, "free_throws_made": ftm, "minutes": mins}


class Pieces(unittest.TestCase):
    def setUp(self):
        self.g = {"game_id": 1, "away": "AAA", "home": "BBB"}
        self.box = {1: [row("AAA", 80, 40, 100, 10), row("BBB", 90, 45, 110, 12)] + [row("AAA", 0, 0, 0, 0, 48.0 * 4), row("BBB", 0, 0, 0, 0, 48.0 * 4)]}

    def test_team_games_use_field_goal_points_and_five_man_minutes(self):
        tg = M.team_games(self.box, [self.g])[1]
        self.assertEqual(tg["AAA"]["pts"], 90.0)
        self.assertAlmostEqual(tg["AAA"]["mins"], (48.0 + 48.0 * 4) / 5)       # 48 minutes from the one scorer plus four idle rows: 240 / 5

    def test_defense_sample_is_what_the_other_side_did(self):
        tg = M.team_games(self.box, [self.g])
        d = M.defense_sample(tg, self.g)
        f = 48.0 / tg[1]["AAA"]["mins"]
        self.assertAlmostEqual(d["AAA"]["fga"], 90 * f)                         # AAA the defense allowed BBB's 90 attempts
        self.assertAlmostEqual(d["AAA"]["miss"], d["BBB"]["miss"])              # the game's misses count for both defenses
        self.assertAlmostEqual(d["AAA"]["miss"], (40 + 45) * f)

    def test_league_mean_must_be_over_exactly_30_teams(self):
        def tables(n):
            teams = ["T%d" % i for i in range(n)]
            cur = {"sum": defaultdict(lambda: defaultdict(float)), "n": defaultdict(int)}
            prior = {t: {"fga": 90.0 + i, "pts": 100.0 + i, "miss": 90.0 + i} for i, t in enumerate(teams)}
            return M.vs_table(cur, prior, teams)
        t = tables(30)
        self.assertAlmostEqual(sum(v["P_vol"] for v in t.values()) / 30, 0.0, places=9)
        with self.assertRaises(AssertionError):
            tables(33)                                                          # an All-Star-style invented team would stop the run


if __name__ == "__main__":
    unittest.main()
