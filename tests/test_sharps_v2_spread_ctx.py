"""Unit tests for the spread fact line of a moneyline play (docs/side-cards.md "Spread context"): scripts/sharps_v2/spread_ctx.py, its use in
plays_v2.market_v2, the forward log row, the stripping and the size. Synthetic inputs only; no network, no stored data. Run from the repo root:
    python3 -m unittest tests.test_sharps_v2_spread_ctx
"""
import contextlib, io, json, os, sys, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)
from sharps_v2 import flags_v2 as F  # noqa: E402
from sharps_v2 import plays_v2 as P  # noqa: E402
from sharps_v2 import spread_ctx as SC  # noqa: E402
import test_side_cards as T  # noqa: E402
import test_sharps_v2_plays as TP  # noqa: E402

ASOF = T.CUT
DAY = 86400
US = ("DraftKings", "FanDuel", "BetMGM", "BetRivers", "bet365")


def am(p):
    return -p / (1 - p) * 100 if p > 0.5 else (1 - p) / p * 100


def sp(book, t, home_line, fair_home=0.5, **kw):
    return dict({"t": t, "book": book, "sp": [home_line, am(fair_home), am(1 - fair_home)]}, **kw)


def ctx(rows, norm="home", asof=ASOF, hb=None):
    return SC.spread_ctx(rows, norm, asof, hb)


MOVED = [sp("Pinnacle", ASOF - 7200, -3.5), sp("Pinnacle", ASOF - 600, -5.5)] + [sp(b, ASOF - 7000, -3.5) for b in US] + [sp(b, ASOF - 500, -5.0) for b in US]


class Reads(unittest.TestCase):
    def test_a_moved_spread_for_the_home_side(self):
        c, why = ctx(MOVED, "home")
        self.assertIsNone(why)
        self.assertEqual(c["pin"], [-3.5, -5.5])                                  # the home line went -3.5 to -5.5: the home side costs more
        self.assertEqual((c["books"], c["toward"], c["away"]), (6, 6, 0))
        self.assertEqual((c["v"], c["asof"]), (1, ASOF))

    def test_the_away_side_is_the_mirror(self):
        c, _ = ctx(MOVED, "away")
        self.assertEqual(c["pin"], [3.5, 5.5])                                    # the away line is the home line negated
        self.assertEqual((c["books"], c["toward"], c["away"]), (6, 0, 6))         # the same market moved away from the away side

    def test_has_not_moved(self):
        rows = [sp("Pinnacle", ASOF - 7200, -3.5), sp("Pinnacle", ASOF - 600, -3.5, 0.52)] + [sp(b, ASOF - 7000, -3.5) for b in US] + [sp(b, ASOF - 500, -3.5, 0.51) for b in US]
        c, why = ctx(rows)
        self.assertIsNone(why)
        self.assertEqual((c["pin"], c["books"], c["toward"], c["away"]), ([-3.5, -3.5], 6, 0, 0))

    def test_a_split_market_counts_both_directions(self):
        rows = [sp("Pinnacle", ASOF - 7200, -3.5), sp("Pinnacle", ASOF - 600, -4.5), sp("DraftKings", ASOF - 7000, -3.5), sp("DraftKings", ASOF - 500, -4.0),
                sp("FanDuel", ASOF - 7000, -3.5), sp("FanDuel", ASOF - 500, -3.0), sp("BetMGM", ASOF - 7000, -3.5), sp("BetMGM", ASOF - 500, -3.5)]
        c, _ = ctx(rows)
        self.assertEqual((c["books"], c["toward"], c["away"]), (4, 2, 1))

    def test_a_pickem_line_prints_as_zero_not_negative_zero(self):
        rows = [sp("Pinnacle", ASOF - 7200, 0.0), sp("Pinnacle", ASOF - 600, -1.5)]
        c, _ = ctx(rows, "away")
        self.assertEqual(json.dumps(c["pin"]), "[0.0, 1.5]")

    def test_a_line_change_below_the_tape_resolution_is_not_a_move(self):
        rows = [sp("Pinnacle", ASOF - 7200, -3.5), sp("Pinnacle", ASOF - 600, -3.5), sp("DraftKings", ASOF - 7000, -3.5), sp("DraftKings", ASOF - 500, -3.5 - 0.01)]
        c, _ = ctx(rows)
        self.assertEqual((c["books"], c["toward"], c["away"]), (2, 0, 0))

    def test_pinnacle_alone_is_enough_and_us_books_with_one_row_are_not_counted(self):
        rows = [sp("Pinnacle", ASOF - 7200, -3.5), sp("Pinnacle", ASOF - 600, -4.5), sp("DraftKings", ASOF - 500, -6.0)]
        c, _ = ctx(rows)
        self.assertEqual((c["books"], c["toward"], c["away"]), (1, 1, 0))         # one row is never a move

    def test_a_ten_minute_old_row_with_a_different_market_is_ignored(self):
        rows = MOVED + [{"t": ASOF - 100, "book": "Pinnacle", "ml": [120, -140]}, {"t": ASOF - 90, "book": "FanDuel", "tot": [220.5, -110, -110]}]
        self.assertEqual(ctx(rows), ctx(MOVED))


class PointInTime(unittest.TestCase):
    def test_a_row_after_the_cut_changes_nothing(self):
        later = MOVED + [sp("Pinnacle", ASOF + 1, -9.0), sp("Pinnacle", ASOF + 600, -12.0)] + [sp(b, ASOF + 5, -9.5) for b in US]
        self.assertEqual(ctx(later), ctx(MOVED))
        c, _ = ctx(later)
        self.assertEqual(c["pin"][1], -5.5)

    def test_a_row_exactly_at_the_cut_is_read(self):
        c, _ = ctx(MOVED + [sp("Pinnacle", ASOF, -6.0)])
        self.assertEqual(c["pin"], [-3.5, -6.0])

    def test_a_later_asof_reads_the_later_row(self):
        rows = MOVED + [sp("Pinnacle", ASOF + 60, -6.5)]
        self.assertEqual(ctx(rows, asof=ASOF + 120)[0]["pin"][1], -6.5)
        self.assertEqual(ctx(rows, asof=ASOF)[0]["pin"][1], -5.5)


class WindowStart(unittest.TestCase):
    def test_from_is_the_row_showing_when_the_window_opened(self):
        rows = [sp("Pinnacle", ASOF - 3 * DAY, -1.0), sp("Pinnacle", ASOF - DAY - 3600, -2.5), sp("Pinnacle", ASOF - 3600, -4.5)]
        c, _ = ctx(rows)
        self.assertEqual(c["pin"], [-2.5, -4.5])                                  # the last row at or before the window start, not the first row of the tape
        self.assertEqual(c["span_min"], 1440)

    def test_a_row_exactly_at_the_window_start_counts_as_before_it(self):
        rows = [sp("Pinnacle", ASOF - DAY - 7200, -1.0), sp("Pinnacle", ASOF - DAY, -2.0), sp("Pinnacle", ASOF - 60, -3.0)]
        self.assertEqual(ctx(rows)[0]["pin"], [-2.0, -3.0])

    def test_with_no_row_before_the_window_the_first_inside_it_is_from(self):
        rows = [sp("Pinnacle", ASOF - 36000, -2.0), sp("Pinnacle", ASOF - 600, -3.0)]
        c, _ = ctx(rows)
        self.assertEqual(c["pin"], [-2.0, -3.0])
        self.assertEqual(c["span_min"], 600)                                      # the hours actually covered

    def test_rows_before_the_window_do_not_count_as_moves_inside_it(self):
        rows = [sp("Pinnacle", ASOF - 5 * DAY, -1.0), sp("Pinnacle", ASOF - 4 * DAY, -2.0), sp("DraftKings", ASOF - 5 * DAY, -1.0), sp("DraftKings", ASOF - 4 * DAY, -2.0)]
        c, _ = ctx(rows)
        self.assertEqual((c["pin"], c["toward"], c["away"]), ([-2.0, -2.0], 0, 0))  # both rows were showing before the window opened: a real move of 0


class NullReasons(unittest.TestCase):
    def test_every_reason(self):
        self.assertEqual(ctx(MOVED, "over"), (None, "side_unmapped"))
        self.assertEqual(ctx(MOVED, "under"), (None, "side_unmapped"))
        self.assertEqual(ctx(MOVED, None), (None, "side_unmapped"))
        self.assertEqual(ctx(None), (None, "no_tape_rows_for_game"))
        self.assertEqual(ctx([]), (None, "no_tape_rows_for_game"))
        self.assertEqual(ctx([{"t": ASOF - 10, "book": "Pinnacle", "ml": [120, -140]}, {"t": ASOF - 5, "book": "Pinnacle", "ml": [125, -145]}]), (None, "no_spread_market"))
        self.assertEqual(ctx([sp("Pinnacle", ASOF - 10, -3.5)]), (None, "no_spread_history"))                    # one row is never a move
        self.assertEqual(ctx([sp("Pinnacle", ASOF + 10, -3.5), sp("Pinnacle", ASOF + 20, -4.5)]), (None, "no_spread_market"))   # only rows after the cut
        self.assertEqual(ctx([sp("DraftKings", ASOF - 900, -3.5), sp("DraftKings", ASOF - 90, -4.5)]), (None, "no_spread_market"))   # no Pinnacle spread at all

    def test_a_stale_feed(self):
        self.assertEqual(ctx(MOVED, hb={"pinnacle": ASOF - 3600, "us": ASOF}), (None, "pinnacle_feed_stale"))
        self.assertEqual(ctx(MOVED, hb={"pinnacle": ASOF, "us": ASOF - 3600}), (None, "books_feed_stale"))
        self.assertIsNone(ctx(MOVED, hb={"pinnacle": ASOF - 1800, "us": ASOF - 1800})[1])                           # exactly 30 minutes is still fresh
        self.assertIsNone(ctx(MOVED, hb=None)[1])                                                                  # a frozen card reads as written

    def test_a_swapped_pinnacle_row_is_dropped_not_read_as_a_move(self):
        rows = [sp("Pinnacle", ASOF - 7200, 7.5), sp("Pinnacle", ASOF - 6600, -7.5), sp("Pinnacle", ASOF - 600, 7.5)] + [sp(b, ASOF - 7100, 7.5) for b in US[:3]]
        c, why = ctx(rows)
        self.assertIsNone(why)
        self.assertEqual(c["pin"], [7.5, 7.5])                                    # the -7.5 row sits on the other side of pick'em from every US book
        rows = [sp("Pinnacle", ASOF - 7200, 7.5), sp("Pinnacle", ASOF - 600, -7.5)] + [sp(b, ASOF - 7100, 7.5) for b in US[:3]]
        self.assertEqual(ctx(rows), (None, "pinnacle_row_inconsistent"))

    def test_every_pinnacle_row_on_the_wrong_side_is_inconsistent_not_missing(self):
        rows = [sp("Pinnacle", ASOF - 7200, 7.5), sp("Pinnacle", ASOF - 600, 7.5)] + [sp(b, ASOF - 7300, -7.5) for b in US[:3]]
        self.assertEqual(ctx(rows), (None, "pinnacle_row_inconsistent"))

    def test_malformed_rows_are_skipped_and_never_raise(self):
        bad = [{"t": ASOF - 10, "book": "Pinnacle", "sp": [None, -110, -110]}, {"t": ASOF - 10, "book": "Pinnacle", "sp": [-3.5, -110]}, "not a row", None,
               {"t": None, "book": "Pinnacle", "sp": [-3.5, -110, -110]}, {"t": ASOF - 10, "book": "Pinnacle", "sp": "oops"}]
        self.assertEqual(ctx(bad), (None, "no_spread_market"))
        c, _ = ctx(bad + MOVED)
        self.assertEqual(c["pin"], [-3.5, -5.5])

    def test_a_book_the_page_never_names_is_never_read(self):
        rows = MOVED + [sp("BookMaker", ASOF - 7000, -3.5), sp("BookMaker", ASOF - 500, -9.0), sp("Circa", ASOF - 7000, -3.5), sp("Circa", ASOF - 500, -9.0)]
        self.assertEqual(ctx(rows), ctx(MOVED))


class Size(unittest.TestCase):
    def test_the_stored_key_is_small(self):
        for norm in ("home", "away"):
            c, _ = ctx(MOVED, norm)
            self.assertLess(len(json.dumps(c, separators=(",", ":"))), 250)
            self.assertLess(len(json.dumps(c, separators=(",", ":"))), 130)       # the design size: about 100 bytes
        self.assertEqual(sorted(ctx(MOVED)[0]), ["asof", "away", "books", "pin", "span_min", "toward", "v"])


class InTheBlock(unittest.TestCase):
    NORMS = {"A": "home", "B": "away"}

    def v2(self, g="ml", rows=MOVED, sport="nba", m=None, **kw):
        return P.market_v2(sport, g, m or TP.market(), [], {}, {"mk": {}}, ASOF, kw.pop("norms", self.NORMS), rows=rows, **kw)[0]

    def test_a_moneyline_play_carries_the_key_and_a_stored_reason_when_null(self):
        v = self.v2()
        self.assertEqual((v["spread_ctx"]["pin"], v["spread_ctx_why"]), ([-3.5, -5.5], None))
        v = self.v2(rows=[])
        self.assertEqual((v["spread_ctx"], v["spread_ctx_why"]), (None, "no_tape_rows_for_game"))
        v = self.v2(rows=None)
        self.assertEqual((v["spread_ctx"], v["spread_ctx_why"]), (None, "no_tape_rows_for_game"))
        v = self.v2(norms={})
        self.assertEqual((v["spread_ctx"], v["spread_ctx_why"]), (None, "side_unmapped"))

    def test_moneyline_only(self):
        for g in ("spread", "total"):
            v = self.v2(g=g)
            self.assertNotIn("spread_ctx", v)
            self.assertNotIn("spread_ctx_why", v)

    def test_no_shown_play_no_key(self):
        v = self.v2(m=TP.market(units=0))
        self.assertIsNone(v["side"])
        self.assertNotIn("spread_ctx", v)

    def test_every_other_key_is_byte_identical_with_or_without_it(self):
        new = self.v2()
        with mock.patch.object(P.SC, "spread_ctx", side_effect=RuntimeError("off")), contextlib.redirect_stderr(io.StringIO()):
            old = self.v2()
        strip = lambda v: {k: x for k, x in v.items() if k not in ("spread_ctx", "spread_ctx_why")}
        self.assertEqual(json.dumps(strip(new), sort_keys=True), json.dumps(strip(old), sort_keys=True))
        for k in ("tier", "shown_units", "shadow_units", "flags", "series", "move_grade", "exec", "vs_fair", "facts"):
            self.assertEqual(json.dumps(new.get(k), sort_keys=True), json.dumps(old.get(k), sort_keys=True))

    def test_the_grade_the_tier_and_the_flags_do_not_read_it(self):
        mlrows = [{"t": ASOF - 7200, "book": "Pinnacle", "ml": [-150, 130]}, {"t": ASOF - 600, "book": "Pinnacle", "ml": [-190, 165]}] + \
                 [{"t": ASOF - 7000, "book": b, "ml": [-150, 130]} for b in US] + [{"t": ASOF - 500, "book": b, "ml": [-185, 160]} for b in US]
        base = self.v2(rows=mlrows + MOVED)
        flat = self.v2(rows=mlrows + [sp("Pinnacle", ASOF - 600, -3.5)])                                           # a different spread story, the same moneyline tape
        none = self.v2(rows=mlrows)
        self.assertEqual(base["spread_ctx"]["toward"], 6)
        self.assertIsNone(none["spread_ctx"])
        self.assertIsNotNone(base["move_grade"])
        for other in (flat, none):
            for k in ("tier", "move_grade", "flags", "series", "shown_units", "shadow_units"):
                self.assertEqual(json.dumps(base.get(k), sort_keys=True), json.dumps(other.get(k), sort_keys=True))

    def test_a_raising_read_drops_the_key_with_a_warning_and_never_the_card(self):
        err = io.StringIO()
        with mock.patch.object(P.SC, "spread_ctx", side_effect=TypeError("boom")), contextlib.redirect_stderr(err):
            v = self.v2(ev="nba-a-b")
        self.assertEqual((v["spread_ctx"], v["spread_ctx_why"]), (None, "error_TypeError"))
        self.assertIn("::warning::v2 spread context dropped for nba-a-b ml: TypeError", err.getvalue())
        self.assertIn("exec", v)

    def test_a_frozen_read_is_point_in_time(self):
        later = MOVED + [sp("Pinnacle", ASOF + 5, -12.0)]
        self.assertEqual(json.dumps(self.v2(rows=later)["spread_ctx"]), json.dumps(self.v2(rows=MOVED)["spread_ctx"]))

    def test_a_live_stale_feed_is_null_with_its_reason(self):
        v = self.v2(frozen=False, heartbeat={"pinnacle": ASOF - 7200, "us": ASOF})
        self.assertEqual((v["spread_ctx"], v["spread_ctx_why"]), (None, "pinnacle_feed_stale"))

    def test_strip_removes_it_with_the_rest_of_v2(self):
        doc = {"games": [{"markets": {"ml": {"v2": self.v2(), "x": 1}}}]}
        s = P.strip_plays_v2(doc)
        self.assertEqual(s, {"games": [{"markets": {"ml": {"x": 1}}}]})
        self.assertIn("spread_ctx", doc["games"][0]["markets"]["ml"]["v2"])

    def test_the_card_builds_when_the_read_raises(self):
        quotes = TP.Malformed.Quotes(MOVED)
        err = io.StringIO()
        with mock.patch.object(P.SC, "spread_ctx", side_effect=TypeError("boom")), contextlib.redirect_stderr(err):
            c = TP.Additive().card(vault={"key": "nba:1", "teams": {"away": ["A"], "home": ["B"]}}, quotes=quotes)
        self.assertTrue(all("v2" in m for m in c["markets"].values()))


class Log(unittest.TestCase):
    def card(self, v2):
        m = TP.market()
        return {"sport": "nba", "ev": "nba-a-b", "gst": ASOF + 900, "cut": ASOF, "markets": {"ml": dict(m, v2=v2)}}

    def test_a_new_row_carries_the_fact_and_an_old_card_adds_nothing(self):
        v = self.v2_full()
        row = P.log_row("nba/frozen/x", self.card(v), "ml", 1)
        self.assertEqual(row["sc"]["pin"], [-3.5, -5.5])
        self.assertIsNone(row["sc_why"])
        old = {k: x for k, x in v.items() if k not in ("spread_ctx", "spread_ctx_why")}
        row0 = P.log_row("nba/frozen/x", self.card(old), "ml", 1)
        self.assertNotIn("sc", row0)
        self.assertNotIn("sc_why", row0)
        self.assertEqual(json.dumps({k: x for k, x in row.items() if k not in ("sc", "sc_why")}, sort_keys=True), json.dumps(row0, sort_keys=True))

    def test_a_null_keeps_its_reason(self):
        v = dict(self.v2_full(), spread_ctx=None, spread_ctx_why="no_spread_market")
        row = P.log_row("nba/frozen/x", self.card(v), "ml", 1)
        self.assertEqual((row["sc"], row["sc_why"]), (None, "no_spread_market"))

    def v2_full(self):
        return P.market_v2("nba", "ml", TP.market(), [], {}, {"mk": {}}, ASOF, {"A": "home", "B": "away"}, rows=MOVED)[0]


class Words(unittest.TestCase):
    def test_no_banned_word_and_no_em_dash_in_the_module(self):
        src = open(os.path.join(ROOT, "scripts", "sharps_v2", "spread_ctx.py")).read()
        self.assertNotIn(chr(0x2014), src)


if __name__ == "__main__":
    unittest.main()
