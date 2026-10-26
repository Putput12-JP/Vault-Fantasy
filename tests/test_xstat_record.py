import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import pricing as PX  # noqa: E402
import ledger  # noqa: E402
import xstat_record as XR  # noqa: E402
import score_xstat_forward as S  # noqa: E402


class SettleEndToEnd(unittest.TestCase):
    def setUp(self):
        self.root, self.tip = tempfile.mkdtemp(), 1792800000
        self.day = ledger.tip_day(self.tip)
        d = os.path.join(self.root, "snapshots", self.day)
        os.makedirs(d)
        rows = {"G1|1|stl": [30.0, 1.0, 0.1], "G1|1|tov": [30.0, 2.0, -0.2], "G1|2|stl": [20.0, 0.8, 0.0], "G1|3|stl": [10.0, 0.4, 0.05]}
        with open(os.path.join(d, "meta.jsonl"), "w") as f, open(os.path.join(d, "xstat.jsonl"), "w") as g:
            for k, v in rows.items():
                _, pid, stat = k.split("|")
                f.write(json.dumps({"k": k, "src": "xstat", "game": "G1", "tip": self.tip, "matchup": "AAA @ BBB", "pid": int(pid), "player": f"P{pid}", "team": "BBB", "stat": stat, "kind": "xstat"}, separators=(",", ":")) + "\n")
                g.write(json.dumps({"t": self.tip - 3600, "k": k, "v": v}, separators=(",", ":")) + "\n")
                g.write(json.dumps({"t": self.tip + 60, "k": k, "v": [99, 99, 99]}, separators=(",", ":")) + "\n")          # after tip: never the scored row
        os.makedirs(os.path.join(self.root, "results"))
        json.dump({"1": {"minutes": 30.0, "steals": 2.0, "turnovers": 3.0}, "2": {"minutes": 20.0, "steals": 0.0, "turnovers": 1.0}, "3": None},
                  open(os.path.join(self.root, "results", "G1.json"), "w"))
        json.dump({"score": {"AAA": 100.0, "BBB": 104.0}}, open(os.path.join(self.root, "results", "G1.meta.json"), "w"))

    def test_rows_are_graded_the_void_player_is_counted_and_the_post_tip_row_is_ignored(self):
        out = XR.record(self.root, self.tip + 4 * 3600, None, 3, None, ledger)
        f = json.load(open(os.path.join(self.root, "xstats", f"{self.day}.json")))
        self.assertEqual(f["cols"], XR.COLS)
        rows = {(r[0], r[3]): r for r in f["rows"]}
        self.assertEqual(rows[(1, "stl")][4:], [30.0, 1.0, 0.1, 2.0])           # minutes, mu0, mt, actual (box 'steals')
        self.assertEqual(rows[(1, "tov")][7], 3.0)                               # box 'turnovers'
        self.assertEqual(rows[(2, "stl")][7], 0.0)                               # played and had no steals: a real zero
        self.assertNotIn((3, "stl"), rows)                                        # did not play: void
        self.assertEqual(out[self.day], {"n": 3, "void": 1})

    def test_a_game_not_yet_final_is_not_settled(self):
        self.assertEqual(XR.record(self.root, self.tip + 600, None, 3, None, ledger), {})


class Projection(unittest.TestCase):
    def test_mu_extra_is_minutes_times_the_lab_rate_with_the_term_on_it(self):
        p = PX.Pricer.__new__(PX.Pricer)
        p.MM, p.example = True, False
        p.pidx = {7: ("BBB", {"id": 7, "rate": {"stl": 0.03, "tov": 0.07}})}
        p.game_minutes = lambda team, g, status, cache: {7: {"min": 30.0}}
        p.matchup_term = lambda pid, opp, s, mu: 0.1 * mu
        g = {"id": "G", "away": "AAA", "home": "BBB"}
        x = p.mu_extra(7, "stl", g, {}, {}, "BBB", {})
        self.assertAlmostEqual(x["mu0"], 0.9)
        self.assertAlmostEqual(x["mt"], 0.09)
        self.assertIsNone(p.mu_extra(7, "blk", g, {}, {}, "BBB", {}))           # only steals and turnovers
        self.assertIsNone(p.mu_extra(8, "stl", g, {}, {}, "BBB", {}))           # no minutes for him


class Scorer(unittest.TestCase):
    def test_gain_and_readiness(self):
        rows = [{"day": "d", "game": str(i), "stat": "stl", "mu0": 1.0, "mt": 0.2, "actual": 1.2} for i in range(10)]
        self.assertAlmostEqual(S.per_stat(rows)["stl"]["stats"]["gain"], 0.2)
        self.assertFalse(S.ready({"rows": 499, "nights": 30}))
        self.assertTrue(S.ready({"rows": 500, "nights": 25}))


if __name__ == "__main__":
    unittest.main()
