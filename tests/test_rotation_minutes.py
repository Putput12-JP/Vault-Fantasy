import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import test_rotation_minutes as T  # noqa: E402


class Pieces(unittest.TestCase):
    def test_state_probabilities_sum_to_one_and_blowouts_grow_with_the_spread(self):
        for e in (0.0, 5.0, -12.0, None):
            self.assertAlmostEqual(sum(T.pis(e)), 1.0, places=9)
        self.assertGreater(T.pis(15.0)[2], T.pis(2.0)[2])
        for a, b in zip(T.pis(-15.0), T.pis(15.0)):
            self.assertAlmostEqual(a, b, places=9)

    def test_state_buckets(self):
        self.assertEqual([T.state_of(x) for x in (0, 9, 10, 19, 20, 40)], [0, 0, 1, 1, 2, 2])

    def test_ols_recovers_a_line(self):
        rows = [{"a": float(i), "y": 3.0 + 2.0 * i} for i in range(20)]
        w = T.ols(rows, lambda r: [1.0, r["a"]], lambda r: r["y"])
        self.assertAlmostEqual(w[0], 3.0, places=4)
        self.assertAlmostEqual(w[1], 2.0, places=4)

    def test_rescale_sets_the_unconditional_total_and_caps_at_48(self):
        preds = [(1.0, 30.0)] * 8 + [(0.5, 10.0)]
        out = T.rescale(preds, 240.0)
        self.assertAlmostEqual(sum(p * o for (p, _), o in zip(preds, out)), 240.0, places=6)
        self.assertLessEqual(max(T.rescale([(1.0, 60.0)] * 8, 800.0)), 48.0)

    def test_logistic_separates_a_clean_signal(self):
        rows = [{"x": float(i % 2), "y": i % 2} for i in range(200)]
        w = T.logit_fit(rows, lambda r: [1.0, r["x"]], lambda r: r["y"])
        self.assertGreater(T.lp(w, [1.0, 1.0]), 0.8)
        self.assertLess(T.lp(w, [1.0, 0.0]), 0.2)


if __name__ == "__main__":
    unittest.main()
