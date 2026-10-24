import math, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import build_live_season as S  # noqa: E402


def bet(game, pid, pnl, side="Under", stat="pts", book="DraftKings", venue="book", gate="no-go", edge=0.04, tip=1792800000):
    return {"game": game, "pid": pid, "pnl": pnl, "pnl_close": pnl, "side": side, "stat": stat, "venue": venue, "book": book,
            "gate": gate, "edge": edge, "tip": tip, "result": "win" if pnl > 0 else "loss" if pnl < 0 else "push", "clv": 0.01}


class Record(unittest.TestCase):
    def test_counts_and_return(self):
        r = S.record([bet("g1", 1, 0.9), bet("g1", 2, -1.0), bet("g2", 3, -1.0), bet("g2", 3, 0.0)])
        self.assertEqual((r["n"], r["w"], r["l"], r["p"]), (4, 1, 2, 1))
        self.assertAlmostEqual(r["u"], -1.1, places=4)
        self.assertEqual((r["games"], r["nights"], r["picks"]), (2, 3, 3))

    def test_same_player_night_is_one_cluster(self):
        # ten bets on one player in one game, every one a loss, plus ten independent nights split win/loss:
        # the ten bets move together, so the clustered standard error must be larger than the per-bet one
        bs = [bet("g1", 1, -1.0, book=f"b{i}") for i in range(10)] + [bet(f"g{i + 2}", 9, 1.0 if i % 2 else -1.0) for i in range(10)]
        r = S.record(bs)
        naive = r["sd"] / math.sqrt(r["n"])
        self.assertEqual(r["nights"], 11)
        self.assertGreater(r["se"], naive * 1.5)

    def test_independent_nights_match_the_plain_standard_error(self):
        # every bet its own night: the clustered standard error is the usual one, up to the small-sample G/(G-1) correction
        bs = [bet(f"g{i}", i, 1.0 if i % 3 else -1.0) for i in range(60)]
        r = S.record(bs)
        naive = r["sd"] / math.sqrt(r["n"])
        self.assertAlmostEqual(r["se"] / naive, 1.0, delta=0.03)

    def test_one_night_has_no_standard_error(self):
        self.assertIsNone(S.record([bet("g1", 1, 1.0), bet("g1", 1, -1.0)])["se"])


class Rows(unittest.TestCase):
    def test_edge_bins_follow_the_ledger(self):
        self.assertEqual([S.ebin(bet("g", 1, 1.0, edge=e)) for e in (0.03, 0.05, 0.08, 0.12, 0.3)], ["3-5%", "5-8%", "8-12%", "12%+", "12%+"])

    def test_kalshi_yes_is_over_and_a_market_is_venue_stat_side(self):
        bs = [bet("g1", 1, 1.0, side="YES", venue="kalshi", book="Kalshi"), bet("g2", 2, -1.0, side="NO", venue="kalshi", book="Kalshi")]
        rows = S.rows(bs, lambda b: (S.L.family(b), b["stat"], S.side_of(b)), lambda k: {"venue": k[0], "stat": k[1], "side": k[2]})
        self.assertEqual({(r["venue"], r["side"]) for r in rows}, {("kalshi", "over"), ("kalshi", "under")})

    def test_gate_is_the_markets_latest(self):
        bs = [bet("g1", 1, 1.0, gate="no-go", tip=100), bet("g2", 2, 1.0, gate="watch", tip=200)]
        self.assertEqual(S.rows(bs, lambda b: "m", lambda k: {})[0]["gate"], "watch")


if __name__ == "__main__":
    unittest.main()
