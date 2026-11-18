"""Unit tests for scripts/pm_clv_tiers.py: observations from stored closes, point-in-time fits, tiers."""
import os, random, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import pm_clv_tiers as CT  # noqa: E402

T0 = 1_800_000_000
EV = lambda slug: slug.split("|")[0] if slug else None


def world(skill, n_games=40, n_wallets=40, seed=1):
    """Wallets 'a0'..: noise around 0 CLV; 'sharp' gains +2 points a game, 'dull' loses 2. One market per game, one close."""
    rnd = random.Random(seed)
    rows, markets, closes = [], {}, {}
    ws = ["a%d" % i for i in range(n_wallets)] + ["sharp", "dull"]
    for g in range(n_games):
        cid = "c%d" % g
        markets[cid] = {"slug": "g%d|x" % g}
        closes[(cid, 0)] = 0.50
        for w in ws:
            edge = {"sharp": skill, "dull": -skill}.get(w, 0.0)
            avg = 0.50 - edge + rnd.gauss(0, 0.02)
            rows.append({"w": w, "cid": cid, "oi": 0, "avg": avg, "stake": 100.0, "gst": T0 + g * 86400, "mt": "moneyline",
                         "hedged": False, "split": False})
    return rows, markets, closes


class Tiers(unittest.TestCase):
    def test_skill_is_found_and_noise_is_not(self):
        rows, mk, cl = world(0.02)
        obs = CT.observations(rows, mk, cl, EV)
        f = CT.fit(obs, T0 + 100 * 86400)
        self.assertEqual(f["wallets"]["sharp"]["tier"], "sharp")
        self.assertEqual(f["wallets"]["dull"]["tier"], "dull")
        noise = [v["tier"] for w, v in f["wallets"].items() if w.startswith("a")]
        self.assertLessEqual(noise.count("sharp"), 3)

    def test_point_in_time(self):
        rows, mk, cl = world(0.02)
        obs = CT.observations(rows, mk, cl, EV)
        early = CT.fit(obs, T0 + 5 * 86400)["wallets"]["sharp"]        # games 0..4 only
        late = CT.fit(obs, T0 + 100 * 86400)["wallets"]["sharp"]
        self.assertEqual(early["n"], 5)
        self.assertEqual(early["tier"], "thin")                          # under MIN_N: listed, not tiered
        self.assertEqual(late["n"], 40)
        self.assertEqual(CT.fit(obs, T0 + 5 * 86400)["wallets"].get("sharp", {}).get("n"), 5)

    def test_a_game_never_sees_itself(self):
        rows, mk, cl = world(0.02)
        obs = CT.observations(rows, mk, cl, EV)
        f = CT.fit(obs, T0 + 39 * 86400)                                  # the cut of game 39: its own start is not before it
        self.assertEqual(f["wallets"]["sharp"]["n"], 39)

    def test_hedged_split_unpriced_and_closeless_rows_are_left_out(self):
        rows, mk, cl = world(0.0, n_games=3, n_wallets=1)
        rows[0]["hedged"] = True
        rows[1]["split"] = True
        rows[2]["avg"] = 0.01
        del cl[("c2", 0)]                                                 # a game with no stored close
        obs = CT.observations(rows, mk, cl, EV)
        total = sum(len(v) for v in obs.values())
        self.assertEqual(total, len(rows) - 3 - 3)                        # 3 bad rows, then game c2's 3 wallet rows (one counted above)

    def test_too_few_wallets_gives_no_tiers(self):
        rows, mk, cl = world(0.02, n_wallets=5)
        f = CT.fit(CT.observations(rows, mk, cl, EV), T0 + 100 * 86400)
        self.assertIsNone(f["params"])
        self.assertEqual(f["wallets"], {})

    def test_backtest_reads_next_week_by_tier(self):
        rows, mk, cl = world(0.02, n_games=80)
        obs = CT.observations(rows, mk, cl, EV)
        bt = CT.backtest(obs, T0 + 45 * 86400, T0 + 80 * 86400)
        self.assertGreater(bt["by_tier"]["sharp"]["clv"], 0.005)
        self.assertLess(bt["by_tier"]["dull"]["clv"], -0.005)


if __name__ == "__main__":
    unittest.main()
