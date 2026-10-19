import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import build_lead_lag as L  # noqa: E402

START = 1_000_000


def row(t, book, sp, gk="cfb:1"):
    return {"t": t, "src": "sd", "gk": gk, "book": book, "away": "A", "home": "B", "start": START, "sp": [sp, -110, -110], "sport": "cfb"}


def build(rows):
    return L.series(rows)


class Clock(unittest.TestCase):
    def rows(self):
        t0 = START - 20 * 3600
        r = []
        for b in ("Pinnacle", "DraftKings", "FanDuel", "BetMGM"):
            r.append(row(t0, b, -3.0))
        # a poll with no change shows polling went on, then Pinnacle moves -3 -> -3.5 at t0+3600
        r.append(row(t0 + 3000, "Pinnacle", -3.0))
        r.append(row(t0 + 3600, "Pinnacle", -3.5))
        r.append(row(t0 + 3300, "DraftKings", -3.5))          # DraftKings moved first (inside the hour before)
        r.append(row(t0 + 3600 + 900, "FanDuel", -3.5))       # FanDuel follows 15 minutes later
        return r, t0 + 3600                                   # BetMGM never moves

    def test_events_need_a_localised_time(self):
        rows, t1 = self.rows()
        g, meta = build(rows)
        polls = sorted({r["t"] for r in rows})
        ev = L.events(g["cfb:1"]["Pinnacle"], "sp", START, polls)
        self.assertEqual([(e[0], e[1], e[2]) for e in ev], [(t1, -3.0, -3.5)])
        self.assertEqual(L.events(g["cfb:1"]["Pinnacle"], "sp", START, [t1 - 7200]), [])     # nearest poll is 2h before: not localised
        self.assertEqual(L.events(g["cfb:1"]["Pinnacle"], "sp", t1 + 3600, polls), [])       # inside the 3h kickoff buffer

    def test_led_lag_and_not_followed(self):
        rows, t1 = self.rows()
        g, _ = build(rows)
        b = g["cfb:1"]
        self.assertEqual(L.follow(b["DraftKings"], t1, -3.0, -3.5, "sp", START), ("led", None))
        k, m = L.follow(b["FanDuel"], t1, -3.0, -3.5, "sp", START)
        self.assertEqual(k, "lag")
        self.assertAlmostEqual(m, 15.0)
        self.assertEqual(L.follow(b["BetMGM"], t1, -3.0, -3.5, "sp", START), ("none", None))

    def test_a_book_on_another_number_is_judged_on_its_own_move(self):
        t0 = START - 20 * 3600
        ser = [(t0, {"sp": -2.5}), (t0 + 4500, {"sp": -3.0})]       # always half a point off Pinnacle, moves half a point after
        self.assertEqual(L.follow(ser, t0 + 3600, -3.0, -3.5, "sp", START)[0], "lag")

    def test_summary_hides_small_samples(self):
        self.assertNotIn("median_min", L.summary([10.0] * 5, 1, 1))
        s = L.summary([10.0] * 20, 3, 7)
        self.assertEqual(s["n"], 30)
        self.assertEqual(s["median_min"], 10.0)
        self.assertAlmostEqual(s["pct_followed_within_15"], 20 / 30, places=3)

    def test_ages_report_which_book_still_differs(self):
        rows, t1 = self.rows()
        g, meta = build(rows)
        out = L.ages(g, meta, START - 3600, {})
        sp = out["cfb:1"]["sp"]
        self.assertEqual(sp["pin"], -3.5)
        self.assertTrue(sp["books"]["DraftKings"]["same"])
        self.assertFalse(sp["books"]["BetMGM"]["same"])
        self.assertEqual(sp["pin_moved"], t1)
        self.assertEqual(L.ages(g, meta, START + 1, {}), {})                                  # started games are dropped


if __name__ == "__main__":
    unittest.main()
