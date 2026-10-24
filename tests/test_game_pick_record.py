import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import game_pick_record as G  # noqa: E402


def profit(px, won):
    """Per 1 unit risked at an American price string, as ledger.profit does for a book."""
    a = float(px)
    c = 100 / (a + 100) if a > 0 else -a / (-a + 100)
    return (1 - c) / c if won else -1.0


def row(margin, spread, hpx="-110", apx="-110", hml="-150", aml="+130", p_home=None):
    p = G.phi(margin / 13.2) if p_home is None else p_home
    return [margin, 230.0, p, "DraftKings", spread, hpx, apx, hml, aml]


class AtsPick(unittest.TestCase):
    def test_home_favoured_by_model_more_than_line(self):
        # model: home by 6. Line: home -2.5 (spread -2.5). Model likes home to cover by 3.5.
        self.assertEqual(G.ats_pick(6, -2.5), ("H", 3.5))

    def test_model_less_bullish_than_line_takes_the_dog(self):
        # model: home by 1. Line: home -6.5. Away +6.5 is the pick, edge 5.5.
        self.assertEqual(G.ats_pick(1, -6.5), ("A", 5.5))

    def test_home_underdog_cases(self):
        # model: away by 1 (margin -1). Line: home +3.5. Home +3.5 is the pick, edge 2.5.
        self.assertEqual(G.ats_pick(-1, 3.5), ("H", 2.5))

    def test_exact_agreement_is_no_pick(self):
        self.assertIsNone(G.ats_pick(-3.5, 3.5))

    def test_grade_home_cover_away_cover_push(self):
        self.assertEqual(G.ats_grade("H", -2.5, 3), "W")     # home -2.5 wins by 3: covers
        self.assertEqual(G.ats_grade("H", -2.5, 2), "L")
        self.assertEqual(G.ats_grade("A", -2.5, 2), "W")     # away +2.5 loses by 2: covers
        self.assertEqual(G.ats_grade("A", -3.0, 3), "P")     # lands on the number
        self.assertEqual(G.ats_grade("H", 3.0, -3), "P")


class Winner(unittest.TestCase):
    def test_pick_and_grade(self):
        self.assertEqual(G.winner_pick(0.62), "H")
        self.assertEqual(G.winner_pick(0.41), "A")
        self.assertIsNone(G.winner_pick(0.5))
        self.assertEqual(G.winner_grade("H", 4), "W")
        self.assertEqual(G.winner_grade("H", -4), "L")
        self.assertEqual(G.winner_grade("A", -4), "W")


class GradeRow(unittest.TestCase):
    def cols(self, r):
        return dict(zip(G.COLS[1:-1], r))

    def test_ats_win_uses_the_picked_sides_price(self):
        # model home by 6 vs home -2.5 -> HOME pick at -110; home wins by 7 -> covers.
        r = self.cols(G.grade_row(row(6, -2.5, hpx="-120", apx="+100"), 7, "f", None, profit))
        self.assertEqual((r["ats_side"], r["ats_px"], r["ats_res"]), ("H", "-120", "W"))
        self.assertAlmostEqual(r["ats_units"], 100 / 120, places=3)

    def test_ats_loss_is_minus_one_and_push_is_zero(self):
        lose = self.cols(G.grade_row(row(6, -2.5), 1, "f", None, profit))
        self.assertEqual((lose["ats_res"], lose["ats_units"]), ("L", -1.0))
        push = self.cols(G.grade_row(row(6, -3.0), 3, "f", None, profit))
        self.assertEqual((push["ats_res"], push["ats_units"]), ("P", 0.0))

    def test_no_stored_price_means_no_units_never_a_guess(self):
        r = self.cols(G.grade_row(row(6, -2.5, hpx=None), 7, "f", None, profit))
        self.assertEqual(r["ats_res"], "W")
        self.assertIsNone(r["ats_units"])

    def test_no_line_still_grades_the_winner(self):
        r = self.cols(G.grade_row([4.0, 228.0, G.phi(4 / 13.2), None, None, None, None, "-180", "+150"], 6, "f", None, profit))
        self.assertIsNone(r["ats_side"])
        self.assertEqual((r["ml_side"], r["ml_px"], r["ml_res"]), ("H", "-180", "W"))
        self.assertAlmostEqual(r["ml_units"], 100 / 180, places=3)

    def test_winner_uses_the_dogs_price_when_the_model_picks_the_dog(self):
        # model has away by 2 (p_home < .5); away ML +130 and the away team wins.
        r = self.cols(G.grade_row(row(-2, 1.5, hml="-140", aml="+120"), -5, "f", None, profit))
        self.assertEqual((r["ml_side"], r["ml_px"], r["ml_res"]), ("A", "+120", "W"))
        self.assertAlmostEqual(r["ml_units"], 1.2, places=3)


class Clv(unittest.TestCase):
    def cols(self, r):
        return dict(zip(G.COLS[1:-1], r))

    def test_home_pick_clv_positive_when_the_home_number_gets_worse_for_buyers(self):
        # locked HOME at +3.5 (model -1 -> edge 2.5); close moves to +2.5: we beat the close by 1.
        first = row(-1, 3.5)
        close = row(-1, 2.5)
        r = self.cols(G.grade_row(close, 0, "c", first, profit))
        self.assertEqual(r["clv_pts"], 1.0)

    def test_away_pick_clv_sign(self):
        # locked AWAY +6.5 (home -6.5, model home by 1); close home -7.5 (away +7.5): market agreed, we beat the close by -1? No:
        # away got MORE points at close (+7.5 vs the +6.5 we took), so the close was better than our number: CLV -1.
        first = row(1, -6.5)
        close = row(1, -7.5)
        r = self.cols(G.grade_row(close, 0, "c", first, profit))
        self.assertEqual(r["clv_pts"], -1.0)
        # and the other way: close home -5.5, away +5.5: we took +6.5, beat the close by 1.
        r = self.cols(G.grade_row(row(1, -5.5), 0, "c", first, profit))
        self.assertEqual(r["clv_pts"], 1.0)

    def test_first_clock_has_no_clv(self):
        r = self.cols(G.grade_row(row(1, -6.5), 0, "f", row(1, -6.5), profit))
        self.assertIsNone(r["clv_pts"])


class PickLine(unittest.TestCase):
    BOOKS = [["Consensus", 3.5, "-110", "-110", "+128", "-155", 230.0, "-113", "-110", None, 1],
             ["DraftKings", 4.0, "-112", "-108", None, None, 229.5, "-110", "-110", None, 1],
             ["Pinnacle", 3.5, "-106", "-104", "+131", "-145", 230.0, "-106", "-106", None, 1]]

    def test_first_book_in_order_with_a_spread_and_moneyline_from_the_first_with_both(self):
        ln = G.pick_line({"mk": {"books": self.BOOKS}})
        self.assertEqual((ln["book"], ln["spread"], ln["home_px"]), ("DraftKings", 4.0, "-112"))
        self.assertEqual((ln["ml_book"], ln["home_ml"], ln["away_ml"]), ("Pinnacle", "+131", "-145"))

    def test_no_books_is_none(self):
        self.assertIsNone(G.pick_line({}))
        self.assertIsNone(G.pick_line({"mk": {"books": [["DraftKings", None, None, None, None, None, None, None, None, None, 1]]}}))


class Summary(unittest.TestCase):
    def test_counts_by_clock(self):
        rows = []
        for gid, am in (("1", 7), ("2", 1)):
            for clock in ("f", "c"):
                rows.append([gid] + G.grade_row(row(6, -2.5), am, clock, row(6, -2.5), profit) + ["live"])
        s = G.summarize(rows)
        self.assertEqual(s["f"]["ats"], [2, 1, 1, 0])
        self.assertEqual(s["f"]["ml"], [2, 2, 0])


class SettleEndToEnd(unittest.TestCase):
    """record() on a fake nba-data folder: two polls for one game, a final score, and the real ledger helpers."""

    def setUp(self):
        import json, tempfile, ledger
        self.L, self.json = ledger, json
        self.root = tempfile.mkdtemp()
        self.tip = 1792800000                                        # 2026-10-24 ~00:00 UTC: an ET evening of 10-23
        day = self.L.tip_day(self.tip)
        d = os.path.join(self.root, "snapshots", day)
        os.makedirs(d)
        meta = {"k": "G1", "src": "gpick", "game": "G1", "tip": self.tip, "matchup": "AAA @ BBB", "away": "AAA", "home": "BBB", "ml_book": "DraftKings", "kind": "gpick"}
        with open(os.path.join(d, "meta.jsonl"), "w") as f:
            f.write(json.dumps(meta, separators=(",", ":")) + "\n")
        first = [4.0, 228.0, G.phi(4 / 13.2), "DraftKings", -2.5, "-110", "-110", "-150", "+130"]       # model BBB by 4 vs -2.5: HOME pick
        close = [4.0, 228.0, G.phi(4 / 13.2), "DraftKings", -3.5, "-110", "-110", "-170", "+145"]       # line moved toward us by a point
        late = [4.0, 228.0, 0.9, "DraftKings", -3.5, "-110", "-110", "-170", "+145"]                    # a row AFTER tip must never count
        with open(os.path.join(d, "gpick.jsonl"), "w") as f:
            for t, v in ((self.tip - 3 * 3600, first), (self.tip - 600, close), (self.tip + 60, late)):
                f.write(json.dumps({"t": t, "k": "G1", "v": v}, separators=(",", ":")) + "\n")
        os.makedirs(os.path.join(self.root, "results"))
        json.dump({"1": {"points": 1}}, open(os.path.join(self.root, "results", "G1.json"), "w"))
        json.dump({"score": {"AAA": 100.0, "BBB": 104.0}}, open(os.path.join(self.root, "results", "G1.meta.json"), "w"))
        self.now = self.tip + 4 * 3600

    def test_first_and_close_clocks_are_graded_and_summarised(self):
        out = G.record(self.root, self.now, None, 3, None, self.L)
        day = self.L.tip_day(self.tip)
        f = self.json.load(open(os.path.join(self.root, "gpicks", f"{day}.json")))
        self.assertEqual(f["cols"], G.COLS)
        rows = {r[1]: dict(zip(G.COLS, r)) for r in f["rows"]}
        # first look: HOME -2.5, home won by 4 -> covers; units at -110
        self.assertEqual((rows["f"]["ats_side"], rows["f"]["ats_res"], rows["f"]["spread"]), ("H", "W", -2.5))
        self.assertAlmostEqual(rows["f"]["ats_units"], 100 / 110, places=3)
        # close look: HOME -3.5, home won by 4 -> still covers
        self.assertEqual((rows["c"]["spread"], rows["c"]["ats_res"]), (-3.5, "W"))
        # we took HOME -2.5, the close is HOME -3.5: the market moved toward us, a point of CLV
        self.assertEqual(rows["c"]["clv_pts"], 1.0)
        # winner pick: home, won, at the first look's stored moneyline
        self.assertEqual((rows["f"]["ml_side"], rows["f"]["ml_px"], rows["f"]["ml_res"]), ("H", "-150", "W"))
        self.assertEqual(rows["f"]["ml_book"], "DraftKings")
        self.assertEqual(rows["f"]["src"], "live")
        self.assertEqual(f["games"]["G1"], ["AAA @ BBB", self.tip, "AAA", "BBB", 100.0, 104.0])
        self.assertEqual(out[day]["f"], {"ats": [1, 1, 0, 0], "ml": [1, 1, 0]})

    def test_a_game_not_yet_final_is_not_settled(self):
        out = G.record(self.root, self.tip + 600, None, 3, None, self.L)         # inside SETTLE_AFTER_S
        self.assertEqual(out, {})

    def test_row_after_tip_never_counts_as_the_close(self):
        G.record(self.root, self.now, None, 3, None, self.L)
        day = self.L.tip_day(self.tip)
        f = self.json.load(open(os.path.join(self.root, "gpicks", f"{day}.json")))
        close = next(dict(zip(G.COLS, r)) for r in f["rows"] if r[1] == "c")
        self.assertAlmostEqual(close["p_home"], G.phi(4 / 13.2), places=4)


if __name__ == "__main__":
    unittest.main()
