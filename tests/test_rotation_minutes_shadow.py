import json, os, random, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import rotation_minutes as R  # noqa: E402
import test_rotation_minutes as T  # noqa: E402
import pricing as PX  # noqa: E402
import ledger  # noqa: E402
import score_rotation_forward as SC  # noqa: E402


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


def fake_pricer(n_players=10):
    """A Pricer with a hand-built state: team BBB, players 1..n (1 is the best), player 2 out, one old model that returns a constant-ish answer."""
    p = PX.Pricer.__new__(PX.Pricer)
    p.MM = {"rot_min": 10.0, "rot_days": 21, "beta": [0] * 9, "team_min": 265.0}
    one = lambda k, v: [v] + [0.0] * (k - 1)                     # an intercept only: P(plays) and P(rotation) near 0.95, 30 minutes when in the rotation, 4 when not
    p.ROTM = {"T": 240.0, "states": [{"wp": one(18, 3.0), "wr": one(18, 3.0), "wm": one(14, 30.0), "g": 4.0} for _ in range(3)]}
    tip = 2_000_000_000
    players = {}
    for i in range(1, n_players + 1):
        players[str(i)] = {"ms": [40.0 - 3 * i, 0.9 if i <= 5 else 0.1, "G", "BBB", tip - 86400, 80], "r": {"pts": 0.5}}
    players["99"] = {"ms": [30.0, 0.5, "G", "BBB", tip - 86400 * 40, 80], "r": {"pts": 0.4}}        # last played 40 days ago: not in the pool
    p.state = {"players": players, "team_last": {"BBB": tip - 86400}, "team_gn": {"BBB": 6}, "last3": {"1": [30.0, 32.0, 34.0]}, "last_idx": {"1": ["BBB", 6], "3": ["BBB", 2]}}
    p.D = {"teams": {"BBB": {"players": [{"id": i} for i in range(1, n_players + 1)]}}}
    return p, tip


class LiveMethod(unittest.TestCase):
    def test_pool_rank_and_game_number_follow_game_minutes(self):
        p, tip = fake_pricer()
        g = {"id": "G", "away": "AAA", "home": "BBB", "tip": tip, "season_type": 2, "spread": -5.0}
        res = p.game_minutes_rot("BBB", g, {2: "Out"}, {})
        self.assertNotIn(2, res)                                  # ruled out: not in the pool
        self.assertNotIn(99, res)                                 # not seen in 30 days
        self.assertEqual(len(res), 9)
        self.assertTrue(all(v["size"] == 9 for v in res.values()))
        self.assertEqual(res[1]["rank"], 1)
        self.assertEqual(res[3]["rank"], 2)                       # player 2 is out, so player 3 is second by minutes
        self.assertTrue(all(v["tgn"] == 7 for v in res.values())) # 6 games played, this is the 7th
        self.assertAlmostEqual(sum(v["min"] * v["p_plays"] for v in res.values()), 240.0, places=6)   # the unconditional total is T

    def test_nothing_without_the_model_in_the_preseason_or_without_state(self):
        p, tip = fake_pricer()
        g = {"id": "G", "away": "AAA", "home": "BBB", "tip": tip, "season_type": 1}
        self.assertEqual(p.game_minutes_rot("BBB", g, {}, {}), {})
        g["season_type"] = 2
        p.ROTM = None
        self.assertEqual(p.game_minutes_rot("BBB", g, {}, {}), {})
        p2, tip = fake_pricer(); p2.state = None
        self.assertEqual(p2.game_minutes_rot("BBB", g, {}, {}), {})
        p3, tip = fake_pricer(); p3.state.pop("last_idx")                      # a state from before the new fields: nothing is logged
        self.assertEqual(p3.game_minutes_rot("BBB", g, {}, {}), {})


class SettleBlock(unittest.TestCase):
    def test_the_daily_rot_block_scores_c3_beside_v2_with_top8_bias_by_pool_size(self):
        root, tip = tempfile.mkdtemp(), 1792800000
        d = os.path.join(root, "snapshots", ledger.tip_day(tip))
        os.makedirs(d)
        # [min v2, recent, v3, five, gbm, blend, rot, size, tgn, rank]
        vals = {1: [30.0, 30.0, None, 0, None, None, 34.0, 16, 4, 1], 2: [20.0, 20.0, None, 0, None, None, 21.0, 16, 4, 12],
                3: [28.0, 28.0, None, 0, None, None, 26.0, 11, 4, 2], 4: [10.0, 10.0, None, 0, None]}              # 4: an old row with no rot
        with open(os.path.join(d, "meta.jsonl"), "w") as f, open(os.path.join(d, "minutes.jsonl"), "w") as g:
            for pid, v in vals.items():
                f.write(json.dumps({"k": f"G1|{pid}", "src": "minutes", "game": "G1", "tip": tip, "matchup": "A @ B", "pid": pid, "player": f"P{pid}", "team": "B"}, separators=(",", ":")) + "\n")
                g.write(json.dumps({"t": tip - 3600, "k": f"G1|{pid}", "v": v}, separators=(",", ":")) + "\n")
        os.makedirs(os.path.join(root, "results"))
        json.dump({"1": {"minutes": 33.0}, "2": {"minutes": 18.0}, "3": {"minutes": 27.0}, "4": {"minutes": 9.0}}, open(os.path.join(root, "results", "G1.json"), "w"))
        json.dump({"score": {"A": 100.0, "B": 104.0}}, open(os.path.join(root, "results", "G1.meta.json"), "w"))
        day = ledger.minutes_record(root, tip + 4 * 3600, None, 3, None)[ledger.tip_day(tip)]
        self.assertEqual(day["n"], 4)
        r = day["rot"]
        self.assertEqual(r["n"], 3)                                                # player 4 has no rot value
        self.assertAlmostEqual(r["mae_v2"], (3 + 2 + 1) / 3, places=3)             # |30-33|, |20-18|, |28-27|
        self.assertAlmostEqual(r["mae_rot"], (1 + 3 + 1) / 3, places=3)            # |34-33|, |21-18|, |26-27|
        self.assertEqual(r["top8"]["size_ge_15"], {"n": 1, "bias_v2": -3.0, "bias_rot": 1.0})   # only player 1 is a top-8 player in a pool of 15 or more
        self.assertEqual(r["top8"]["size_le_12"]["n"], 1)                          # player 3: pool of 11, rank 2


class Scorer(unittest.TestCase):
    def rows(self, n_games=200, size=16):
        return [{"game": str(i // 10), "pid": i, "day": "d", "pm": 30.0, "rot": 33.0, "size": size, "tgn": 5, "rank": 1 + i % 10, "actual": 33.0} for i in range(n_games * 10)]

    def test_bias_buckets_and_the_rule(self):
        rows = self.rows()
        res = SC.evaluate(rows, [])
        self.assertAlmostEqual(res["overall"]["gain"], 3.0)
        self.assertEqual(res["top8_bias"]["size_ge_15"]["rot"], 0.0)
        self.assertEqual(res["top8_bias"]["size_ge_15"]["v2"], -3.0)
        conds, waiting = SC.verdict(res)
        self.assertEqual(waiting, ["size_le_12"])                                  # no short pools in these rows: the read waits for 500 player-games there
        self.assertFalse(all(conds.values()))

    def test_ready_thresholds(self):
        self.assertEqual((SC.MIN_GAMES, SC.MIN_ROWS, SC.MIN_BUCKET, SC.READ_ON), (150, 3000, 500, "2026-12-15"))


if __name__ == "__main__":
    unittest.main()
