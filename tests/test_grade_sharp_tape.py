"""Unit tests for scripts/grade_sharp_tape.py: follow / fade CLV at the ask, late rows, one observation per rung group, clustering."""
import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import grade_sharp_tape as G  # noqa: E402

CLOSES = {"games": {"nba|nba-aaa-bbb-2026-11-19": {"ml": {"p": 0.60, "outcomes": ["Home", "Away"]}}}}


def row(tier="sharp", ask=0.55, opp=0.46, px=0.52, lat=100, late=False, ev="nba-aaa-bbb-2026-11-19", w="w1", key="k1"):
    return {"k": "t", "key": key, "w": w, "tier": tier, "sport": "nba", "ev": ev, "cid": "c1", "mt": "ml", "line": None, "outs": ["Home", "Away"],
            "oi": 0, "px": px, "ts": 1, "seen": 2, "lat": lat, "late": late, "gst": 9, "ask": ask, "bid": ask - 0.01, "opp_ask": opp, "opp_bid": opp - 0.01}


def tape(rows, marks=()):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "nba"))
    with open(os.path.join(d, "nba", "2026-11-18.jsonl"), "w") as f:
        for r in list(rows) + list(marks):
            f.write(json.dumps(r) + "\n")
    return d


class Grade(unittest.TestCase):
    def test_follow_and_fade_clv_at_the_ask(self):
        r = G.grade(tape([row("sharp", ask=0.55), row("dull", opp=0.46, w="w2", key="k2", ev="nba-aaa-bbb-2026-11-19")]), CLOSES)["sports"]["nba"]["tests"]
        self.assertAlmostEqual(r["sharp:follow"]["mean"], 0.60 - 0.55, 5)                  # close .60 for Home, paid .55
        self.assertAlmostEqual(r["dull:fade"]["mean"], (1 - 0.60) - 0.46, 5)               # the other side: close .40, paid .46
        self.assertAlmostEqual(r["sharp:follow"]["slip"], 0.55 - 0.52, 5)                  # the delay cost 3 points against their price

    def test_late_rows_and_rows_without_a_close_are_not_graded(self):
        t = tape([row(late=True, key="k1"), row(ev="nba-zzz-yyy-2026-11-19", key="k2", w="w3")])
        s = G.grade(t, CLOSES)["sports"]["nba"]
        self.assertEqual((s["late"], s["no_close"]), (1, 1))
        self.assertEqual(s["tests"]["sharp:follow"]["n"], 0)

    def test_a_ladder_counts_once_per_wallet_and_market(self):
        rows = [row(key="k%d" % i, ask=0.50 + 0.01 * i) for i in range(5)]               # five fills of one total / ml position
        st = G.grade(tape(rows), CLOSES)["sports"]["nba"]["tests"]["sharp:follow"]
        self.assertEqual(st["n"], 1)
        self.assertAlmostEqual(st["mean"], 0.60 - 0.52, 5)                               # mean of the five asks

    def test_mid_is_graded_both_ways_as_the_control(self):
        t = G.grade(tape([row("mid")]), CLOSES)["sports"]["nba"]["tests"]
        self.assertEqual((t["mid:follow"]["n"], t["mid:fade"]["n"]), (1, 1))

    def test_the_read_needs_n_and_two_ses(self):
        self.assertEqual(G.read({"n": 50, "mean": 0.05, "se": 0.001}), "too_few")
        self.assertEqual(G.read({"n": 200, "mean": 0.010, "se": 0.004}), "cleared")
        self.assertEqual(G.read({"n": 200, "mean": 0.010, "se": 0.006}), "not_cleared")
        self.assertEqual(G.read({"n": 200, "mean": 0.010, "se": None}), "too_few")

    def test_se_is_clustered_by_game(self):
        same = [{"ev": "g1", "clv": 0.02} for _ in range(100)] + [{"ev": "g2", "clv": -0.02} for _ in range(100)]
        spread = [{"ev": "g%d" % i, "clv": 0.02 if i % 2 else -0.02} for i in range(200)]
        self.assertGreater(G.cluster_mean(same)["se"], 5 * G.cluster_mean(spread)["se"])    # 100 plays in one game are one draw, not 100

    def test_markouts_read_the_bid_after_the_delay(self):
        mk = [{"k": "m", "of": "k1", "dt": 60, "t": 5, "bid": 0.56, "ask": 0.58, "opp_bid": 0.4, "opp_ask": 0.42}]
        s = G.grade(tape([row(ask=0.55)], mk), CLOSES)["sports"]["nba"]["markouts"]
        self.assertAlmostEqual(s["60"]["mean"], 0.01, 5)
        self.assertEqual(s["300"]["n"], 0)


if __name__ == "__main__":
    unittest.main()
