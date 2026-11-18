"""scripts/pm_archive.py close_of: one archive read per hour for every planned game, same answer as reading per game."""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import pm_archive as A  # noqa: E402

H = 1_800_000_000 // 3600 * 3600


def game(n, ko):
    t0, t1 = f"{n:02d}" * 32, f"{n + 50:02d}" * 32
    return {"slug": f"g{n}", "title": "x", "kickoff": ko, "markets": [{"cid": f"{n:064x}", "type": "moneyline", "line": None,
            "outcomes": ["A", "B"], "tokens": [t0, t1], "q": None}]}


class Batch(unittest.TestCase):
    def setUp(self):
        self.calls, self.games = [], [game(1, H + 600), game(2, H + 1800), game(3, H + 3600 + 600)]
        outer = self

        def fake(c, t, event, cols, cids, before=None, mirror=False):
            outer.calls.append((t, event, len(cids)))
            rows = []
            for g in outer.games:
                for m in g["markets"]:
                    if m["cid"] in cids:
                        bid = 0.40 + g["kickoff"] % 7 / 100
                        tm = (g["kickoff"] - 120) * 1000
                        if t == H and g["kickoff"] >= H + 3600:
                            continue                       # game 3 quotes in its own hour only
                        if event == "best_bid_ask" and tm // 3600000 * 3600 == t:
                            rows.append((m["tokens"][0], tm, bid, bid + 0.02, False) if mirror else (m["tokens"][0], tm, bid, bid + 0.02))
                            rows.append((m["tokens"][0], (g["kickoff"] + 60) * 1000, 0.99, 0.99, False))   # after kickoff: must be ignored
            return [r for r in rows if before is None or r[1] < before * 1000]
        self.real, A.query = A.query, fake

    def tearDown(self):
        A.query = self.real

    def test_same_answer_and_fewer_reads(self):
        A.PLAN.clear(); A.BATCH.clear()
        solo = [A.close_of(g, None) for g in self.games]
        solo_calls, self.calls = len(self.calls), []
        A.plan(self.games)
        batched = [A.close_of(g, None) for g in self.games]
        self.assertEqual(batched, solo)
        self.assertLess(len(self.calls), solo_calls)
        self.assertEqual(len({(t, e) for t, e, _ in self.calls}), len(self.calls))   # no (hour, event) is read twice
        self.assertTrue(all(g["ml"] and g["ml"]["p"] < 0.9 for g in batched))        # the post-kickoff 0.99 quotes never count

    def test_unpublished_hour_is_none(self):
        A.query = lambda *a, **k: None
        A.plan(self.games)
        self.assertIsNone(A.close_of(self.games[0], None))


if __name__ == "__main__":
    unittest.main()
