import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import test_prop_calibration as T  # noqa: E402


def bet(day, game, edge, fair, fair_close, pnl, result="win", price="-110", pre=False, clv=0.0):
    return {"game": game, "tip": 1, "edge": edge, "fair": fair, "fair_close": fair_close, "pnl": pnl, "result": result, "price": price, "pre": pre, "clv": clv}


class Test2Gate(unittest.TestCase):
    def test_gate_uses_entry_price_and_moves_only_the_fair(self):
        # entry edge 0.04; our fair fell 0.02 by the last look -> 0.02 < 0.03 -> dropped. Fair rose 0.01 -> 0.05 -> kept.
        rows, miss = T.t2_rows({"2026-10-26": [bet("d", "1", 0.04, 0.60, 0.58, -1.0, "loss"), bet("d", "2", 0.04, 0.60, 0.61, 0.9)]})
        self.assertEqual([r["kept"] for r in rows], [False, True])
        self.assertEqual(miss, 0)

    def test_rows_without_a_price_a_result_or_fair_close_are_out(self):
        rows, miss = T.t2_rows({"2026-10-26": [
            bet("d", "1", 0.05, 0.6, 0.6, 0.9, price=None), bet("d", "2", 0.05, 0.6, 0.6, 0.0, result="push"),
            bet("d", "3", 0.05, 0.6, 0.6, 0.9, pre=True), bet("d", "4", 0.05, 0.6, None, 0.9), bet("d", "5", 0.05, 0.6, 0.6, 0.9)]})
        self.assertEqual([r["game"] for r in rows], ["5"])
        self.assertEqual(miss, 1)

    def test_sample_rule_blocks_a_read(self):
        self.assertFalse(T.t2_ready({"nights": 19, "games": 500, "dropped": 900}))
        self.assertFalse(T.t2_ready({"nights": 25, "games": 99, "dropped": 900}))
        self.assertFalse(T.t2_ready({"nights": 25, "games": 500, "dropped": 299}))
        self.assertTrue(T.t2_ready({"nights": 20, "games": 100, "dropped": 300}))

    def test_paired_diff_sign_and_game_clustering(self):
        rows = []
        for g in range(40):
            rows += [{"game": str(g), "pnl": 0.2, "kept": True}, {"game": str(g), "pnl": -0.2, "kept": False}]
        D = T.paired_diff(rows, lambda r: r["pnl"], lambda r: r["kept"], lambda r: not r["kept"])
        self.assertAlmostEqual(D["D"], 0.4)
        self.assertIsNone(T.paired_diff([r for r in rows if r["kept"]], lambda r: r["pnl"], lambda r: r["kept"], lambda r: not r["kept"]))


class Test3Blend(unittest.TestCase):
    def test_halved_sits_between_market_and_blend(self):
        r = {"p_mkt": 0.50, "p_blend": 0.60}
        h = T.halved(r)
        self.assertTrue(0.50 < h < 0.60)
        self.assertAlmostEqual(T.halved({"p_mkt": 0.55, "p_blend": 0.55}), 0.55, places=6)

    def test_rows_window_clock_held_and_side(self):
        cols = ["game", "clock", "held", "res", "side", "p_mkt", "p_blend"]
        d = {"cols": cols, "rows": [
            ["1", "f", None, "W", "O", 0.5, 0.55],      # over, won  -> y_over 1
            ["1", "f", None, "W", "U", 0.5, 0.45],      # under, won -> y_over 0
            ["1", "f", None, "L", "O", 0.5, 0.55],      # over, lost -> y_over 0
            ["1", "c", None, "W", "O", 0.5, 0.55],      # wrong clock
            ["1", "f", "team", "W", "O", 0.5, 0.55],    # held
            ["1", "f", None, "V", "O", 0.5, 0.55],      # did not play
            ["1", "f", None, "W", "O", None, 0.55]]}    # no market
        rows = T.t3_rows({"2026-10-27": d, "2026-10-25": d, "2026-11-18": d}, None)
        self.assertEqual([r["y"] for r in rows], [1, 0, 0])
        self.assertEqual({r["day"] for r in rows}, {"2026-10-27"})


class Test1Cap(unittest.TestCase):
    def test_percentile_index_and_clip(self):
        gaps = sorted(range(100))
        self.assertEqual(gaps[int(0.9 * len(gaps))], 90)
        c = 2.0
        self.assertEqual(max(-c, min(c, 5.0)), 2.0)
        self.assertEqual(max(-c, min(c, -5.0)), -2.0)


if __name__ == "__main__":
    unittest.main()
