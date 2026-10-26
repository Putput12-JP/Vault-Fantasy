import os, random, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import rotation_minutes as R  # noqa: E402
import test_rotation_minutes as T  # noqa: E402


def rand_row(rng, size=13):
    return {"m": rng.uniform(2, 36), "st": rng.random(), "n": rng.randint(1, 120), "rank": rng.randint(1, size), "d3": rng.uniform(-8, 8), "gap": rng.randint(0, 10),
            "last_days": rng.uniform(0, 60), "vs": rng.uniform(0, 80), "vo": rng.uniform(0, 80), "nout": rng.randint(0, 4), "b2b": float(rng.random() < 0.2),
            "home": float(rng.random() < 0.5), "size": size, "e": rng.uniform(-18, 18), "fm": 10}


class Equality(unittest.TestCase):
    def test_features_and_probabilities_equal_the_registered_test(self):
        rng = random.Random(3)
        for _ in range(200):
            r = rand_row(rng, rng.choice([11, 13, 16]))
            self.assertEqual(R.x_common(r), T.xs_common3(r))
            self.assertEqual(R.x_min(r), T.xs_min3(r))
        for e in (None, 0.0, 4.0, -17.0, 31.0):
            for a, b in zip(R.pis(e), T.pis(e)):
                self.assertAlmostEqual(a, b, places=12)

    def test_a_whole_pool_scores_the_same_as_the_registered_functions(self):
        rng = random.Random(5)
        model = {"T": 239.6, "states": [{"wp": [rng.uniform(-1, 1) for _ in range(18)], "wr": [rng.uniform(-1, 1) for _ in range(18)],
                                         "wm": [rng.uniform(-3, 3) for _ in range(14)], "g": 4.2} for _ in range(3)]}
        rows = [rand_row(rng, 14) for _ in range(14)]
        for r in rows:
            r["e"] = 5.0
        got = R.score_pool(model, rows)
        # the registered path: per-state predictions mixed by pis, then rescale
        pi = T.pis(5.0)
        per = [[T.predict(model["states"][s], r, T.xs_common3, T.xs_common3, T.xs_min3) for r in rows] for s in range(3)]
        mixp = [sum(pi[s] * per[s][i][0] for s in range(3)) for i in range(len(rows))]
        mixm = [sum(pi[s] * per[s][i][2] for s in range(3)) for i in range(len(rows))]
        want = T.rescale(list(zip(mixp, mixm)), 239.6)
        for g, w in zip(got, want):
            self.assertAlmostEqual(g["min"], w, places=9)

    def test_empty_and_short_pools(self):
        self.assertEqual(R.score_pool({"T": 240, "states": []}, []), [])
        rng = random.Random(1)
        model = {"T": 239.6, "states": [{"wp": [0.0] * 18, "wr": [0.0] * 18, "wm": [0.0] * 14, "g": 3.0} for _ in range(3)]}
        out = R.score_pool(model, [rand_row(rng, 5) for _ in range(5)])        # fewer than 7 players: no rescale, as in the registered code
        self.assertEqual(len(out), 5)
        self.assertTrue(all(0 < o["p_plays"] < 1 for o in out))


if __name__ == "__main__":
    unittest.main()
