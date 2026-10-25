import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import score_matchup_forward as S  # noqa: E402


def row(game, stat, mu, mt, actual):
    return {"day": "2026-11-01", "game": game, "stat": stat, "mu": mu, "mt": mt, "actual": actual}


class Scorer(unittest.TestCase):
    def test_gain_is_error_without_the_term_minus_error_with_it(self):
        rows = [row(str(i), "3pm", 2.0, 0.2, 2.0) for i in range(10)]            # with the term: mu 2.0 hits 2.0 exactly; without it mu0 = 1.8 misses by 0.2
        r = S.per_stat(rows)["3pm"]["stats"]
        self.assertAlmostEqual(r["gain"], 0.2)
        rows = [row(str(i), "ast", 5.0, 0.5, 4.5) for i in range(10)]             # the term pushed mu to 5.0; truth 4.5; without it mu0 = 4.5 is exact: gain -0.5
        self.assertAlmostEqual(S.per_stat(rows)["ast"]["stats"]["gain"], -0.5)

    def test_ready_needs_both_rows_and_nights(self):
        self.assertFalse(S.ready({"rows": 499, "nights": 40}))
        self.assertFalse(S.ready({"rows": 900, "nights": 24}))
        self.assertTrue(S.ready({"rows": 500, "nights": 25}))

    def test_too_few_games_gives_no_statistic(self):
        self.assertIsNone(S.per_stat([row("1", "3pm", 1.0, 0.1, 1.0)])["3pm"]["stats"])


if __name__ == "__main__":
    unittest.main()
