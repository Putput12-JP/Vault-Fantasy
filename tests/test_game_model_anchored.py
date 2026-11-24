import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import test_game_model_anchored as T  # noqa: E402


class Stats(unittest.TestCase):
    def test_ols_recovers_known_coefficients(self):
        X = [[1.0, i, (i * 7) % 5] for i in range(60)]
        y = [2.0 + 0.5 * x[1] - 1.5 * x[2] for x in X]
        b, se, s = T.ols(X, y)
        self.assertAlmostEqual(b[0], 2.0, places=6); self.assertAlmostEqual(b[1], 0.5, places=6); self.assertAlmostEqual(b[2], -1.5, places=6)

    def test_info_splits_the_two_parts(self):
        # result - L is exactly 0.3 of the ratings part and 1.0 of the news part
        rows = [(L + 0.3 * (m1 - L) + 1.0 * (m2 - m1), L, m1, m2) for L, m1, m2 in [(3, 5, 6), (-2, 0, -1), (7, 6, 9), (0, 2, 2), (-4, -1, -5), (1, 4, 3), (5, 5, 7), (-1, 1, 0)]]
        r = T.info(rows, "x")
        self.assertAlmostEqual(r["g1"], 0.3, places=6); self.assertAlmostEqual(r["g2"], 1.0, places=6)

    def test_picks_follow_the_sign_of_the_part_and_skip_pushes(self):
        rows = [(5, 3, 3, 5), (0, 3, 3, 5), (1, 3, 3, 5), (4, 3, 3, 3.5), (3, 3, 3, 5)]   # news +2 on the first three and the fifth, +0.5 on the fourth (under the cut)
        self.assertEqual(T.picks(rows, "news", 1), (1, 2))                                 # covers by +2 (win), -3 and -2 (losses); the fifth lands on the line: a push, skipped
        self.assertEqual(T.picks(rows, "news", 3), (0, 0))

    def test_paired_t_is_zero_for_equal_errors(self):
        self.assertEqual(T.paired_t([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])[0], 0.0)


if __name__ == "__main__":
    unittest.main()
