import math, os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import rank_pm_wallets as R  # noqa: E402

P = {"nba": {"m": 0.0, "tau2": 1e-4, "sigma2": 6e-4, "wallets": 1}, "nfl": {"m": 0.0, "tau2": 1e-4, "sigma2": 6e-4, "wallets": 1}}


class Rank(unittest.TestCase):
    def test_solver(self):
        x = R.solve([[2.0, 1.0], [1.0, 3.0]], [3.0, 5.0])
        self.assertAlmostEqual(x[0], 0.8); self.assertAlmostEqual(x[1], 1.4)

    def test_shrinkage_scales_with_games(self):
        small, _ = R.posterior({"nba": (3, 0.03, 6e-4)}, "nba", P, 0.5)
        big, _ = R.posterior({"nba": (300, 0.03, 6e-4)}, "nba", P, 0.5)
        self.assertTrue(0 < small < big < 0.03)
        self.assertAlmostEqual(big, 0.03, delta=0.002)

    def test_other_sport_record_moves_an_unseen_sport(self):
        none, sd0 = R.posterior({}, "nba", P, 0.6)
        pooled, sd1 = R.posterior({"nfl": (40, 0.02, 6e-4)}, "nba", P, 0.6)
        zero, _ = R.posterior({"nfl": (40, 0.02, 6e-4)}, "nba", P, 0.0)
        self.assertEqual(none, 0.0); self.assertGreater(pooled, 0.002); self.assertAlmostEqual(zero, 0.0, places=9)
        self.assertLess(sd1, sd0)                                       # evidence narrows the posterior

    def test_posterior_matches_closed_form_for_one_sport(self):
        n, y = 10, 0.02
        m, sd = R.posterior({"nba": (n, y, 6e-4)}, "nba", P, 0.5)
        v = R.wallet_var(n, 6e-4, 6e-4) / n
        self.assertAlmostEqual(m, 1e-4 / (1e-4 + v) * y, places=9)
        self.assertAlmostEqual(sd ** 2, 1e-4 * v / (1e-4 + v), places=9)

    def test_tiers_and_p(self):
        self.assertAlmostEqual(R.p_pos(0.0, 1.0), 0.5)
        self.assertEqual([R.tier_of(p) for p in (0.97, 0.85, 0.65, 0.4, 0.03)], ["proven", "probable", "watching", None, "dull"])

    def test_prior_recovers_spread(self):
        import random
        rnd = random.Random(3)
        d, sig2 = {}, 6e-4
        for i in range(3000):
            mu = rnd.gauss(-0.004, 0.01)
            n = rnd.randint(5, 30)
            ys = [rnd.gauss(mu, math.sqrt(sig2)) for _ in range(n)]
            m = sum(ys) / n
            d[i] = [n, m, sum((y - m) ** 2 for y in ys) / (n - 1)]
        m, t2 = R.prior(d, R.pooled_var(d))
        self.assertAlmostEqual(m, -0.004, delta=0.001); self.assertAlmostEqual(math.sqrt(t2), 0.01, delta=0.002)


if __name__ == "__main__":
    unittest.main()
