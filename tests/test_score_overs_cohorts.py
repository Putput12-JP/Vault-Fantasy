import os, random, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import score_overs_cohorts as S  # noqa: E402


def row(game, side, mu, line, res, p_mkt=None, units=None):
    return {"game": game, "side": side, "mu": mu, "line": line, "res": res, "p_mkt": p_mkt, "units": units}


class Cohorts(unittest.TestCase):
    def test_membership(self):
        a = row("1", "O", 7.5, 5.5, "W", p_mkt=0.55)        # gap 0.364: O1, O2
        b = row("1", "O", 5.6, 5.5, "L", p_mkt=0.45)        # gap 0.018: O3 only
        c = row("1", "U", 2.0, 5.5, "W")                    # gap -0.64: U1
        d = row("1", "O", 7.5, 5.5, "W")                    # no market: O1, not O2 or O3
        names = lambda r: sorted(k for k, f in S.COHORTS.items() if f(r))
        self.assertEqual(names(a), ["A_over", "O1", "O2"])
        self.assertEqual(names(b), ["A_over", "O3"])
        self.assertEqual(names(c), ["A_under", "U1"])
        self.assertEqual(names(d), ["A_over", "O1"])

    def test_gap_uses_the_floor_on_small_lines(self):
        self.assertAlmostEqual(S.gap(row("1", "O", 1.0, 0.5, "W")), 1.0)          # (1.0 - 0.5) / 0.5
        self.assertAlmostEqual(S.gap(row("1", "O", 0.4, 0.2, "W")), 0.4)          # the floor of 0.5 on |line|: (0.4 - 0.2) / 0.5

    def test_the_rule(self):
        rows = [row(str(i // 4), "O", 7, 5, "W" if i % 10 < 8 else "L") for i in range(800)]       # 80% hits, 200 games
        s = S.stats(rows)
        self.assertEqual((s["rows"], s["games"]), (800, 200))
        self.assertEqual(S.verdict(s), "WORKS")
        bad = [row(str(i // 4), "O", 7, 5, "W" if i % 10 < 3 else "L") for i in range(800)]
        self.assertEqual(S.verdict(S.stats(bad)), "FAILS")
        rng = random.Random(4)
        coin = [row(str(i // 4), "O", 7, 5, "W" if rng.random() < 0.5 else "L") for i in range(800)]                # a fair coin, outcomes not balanced inside each game
        self.assertEqual(S.verdict(S.stats(coin)), "inconclusive")
        self.assertEqual(S.verdict(S.stats(rows[:100])), "collecting")            # under 300 rows
        self.assertEqual(S.verdict({"rows": 400, "games": 99, "ci95": [0.6, 0.7]}), "collecting")

    def test_constants_match_the_registration(self):
        self.assertEqual((S.FROM_DAY, S.READ_ON, S.MIN_ROWS, S.MIN_GAMES), ("2026-10-26", "2026-11-23", 300, 100))
        self.assertAlmostEqual(S.BE, 0.5238, places=3)


if __name__ == "__main__":
    unittest.main()
