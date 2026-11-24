"""Unit tests for the Sharps V2 market-move flags (docs/sharps-v2-flags-spec.md, rule v2f-2): scripts/sharps_v2/flags_v2.py, its use in
plays_v2.market_v2 and build_side_cards.card, the size gate, the forward log key and the flag record. Synthetic inputs only; no network,
no stored data. Run from the repo root:
    python3 -m unittest tests.test_sharps_v2_flags
"""
import contextlib, copy, inspect, io, json, os, re, sys, tempfile, time, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)
import build_side_cards as C  # noqa: E402
import sf_signals as SIG  # noqa: E402
from sharps_v2 import flags_v2 as F  # noqa: E402
from sharps_v2 import flag_record as FR  # noqa: E402
from sharps_v2 import plays_v2 as P  # noqa: E402
from sharps_v2 import tier_record as TR  # noqa: E402
from sharps_v2 import check_size as CS  # noqa: E402
import test_side_cards as T  # noqa: E402
import test_sharps_v2_plays as TP  # noqa: E402

ASOF = T.CUT
DAY = 86400
US = ("DraftKings", "FanDuel", "BetMGM", "BetRivers", "bet365")
VAULT = {"key": "nba:1", "teams": {"away": ["A"], "home": ["B"]}}      # side A is the away team, B the home team: the spread pick of the card fixture is A

# The registered thresholds, copied here as literals (spec 1.2 and 1.4, user decision D2 2026-11-23): changing one in the code must break a test.
EXPECT_T_A = {"nba": {"ml": 4.0, "spread": 1.5, "total": 1.5}, "nfl": {"ml": 1.5, "spread": 1.5, "total": 1.5},
              "cbb": {"ml": 3.0, "spread": 1.5, "total": 1.5}, "cfb": {"ml": 2.5, "spread": 1.5, "total": 1.5}}
EXPECT_T_C = {"nba": {"spread": 2.0, "total": 3.0}, "nfl": {"spread": 1.0, "total": 1.0},
              "cbb": {"spread": 1.0, "total": 2.5}, "cfb": {"spread": 1.5, "total": 1.5}}
BANNED = re.compile(r"\b(agree|agrees|agreement|proven|elite|lock|go|confirm|confirms|smart money|sharp action)\b", re.I)


def am(p):
    """American price (float) whose vig-free implied probability is p."""
    return -p / (1 - p) * 100 if p > 0.5 else (1 - p) / p * 100


def ml(book, t, fair_home, **kw):
    return dict({"t": t, "book": book, "ml": [am(1 - fair_home), am(fair_home)]}, **kw)


def sp(book, t, home_line, fair_home=0.5, **kw):
    return dict({"t": t, "book": book, "sp": [home_line, am(fair_home), am(1 - fair_home)]}, **kw)


def tot(book, t, line, fair_over=0.5, **kw):
    return dict({"t": t, "book": book, "tot": [line, am(fair_over), am(1 - fair_over)]}, **kw)


def mk(g, book, t, line=None, fair=0.5, **kw):
    return ml(book, t, fair, **kw) if g == "ml" else sp(book, t, line, fair, **kw) if g == "spread" else tot(book, t, line, fair, **kw)


NORM = {"ml": "home", "spread": "home", "total": "over"}
GROUPS = ("ml", "spread", "total")


def flags(rows, g, norm=None, sport="nba", asof=ASOF, hb=None):
    return F.flags_block(rows, g, norm or NORM[g], asof, sport, hb)


class Constants(unittest.TestCase):
    def test_the_threshold_tables_are_the_registered_values(self):
        self.assertEqual(F.FLAGS_T_A, EXPECT_T_A)
        self.assertEqual(F.FLAGS_T_C, EXPECT_T_C)
        self.assertEqual((F.FLAGS_RULE, F.FLAGS_WINDOW, F.FLAGS_STALE, F.FLAGS_SERIES_N), ("v2f-2", 86400, 1800, 16))
        self.assertEqual(F.LIMIT_SCHEDULE_SHARE, {"nba": 0.99, "nfl": 0.93, "cbb": 0.97, "cfb": 0.89})
        self.assertEqual(F.FLAGS_C_BOOK_MOVE, 1.0)
        self.assertEqual(F.FLAGS_C_MIN_US, 2)

    def test_plays_v2_reads_the_same_constants(self):
        self.assertIs(P.FLAGS_T_A, F.FLAGS_T_A)
        self.assertIs(P.FLAGS_T_C, F.FLAGS_T_C)
        self.assertEqual(P.plays_fields()["flags"], F.flags_fields())
        ff = P.plays_fields()["flags"]
        self.assertEqual((ff["t_a"], ff["t_c"], ff["window_min"], ff["stale_min"]), (EXPECT_T_A, EXPECT_T_C, 1440, 30))
        self.assertEqual(ff["books"], ["Pinnacle", "DraftKings", "FanDuel", "BetMGM", "BetRivers", "bet365"])
        self.assertTrue(ff["limit_is_a_fact_only"] and ff["context_only"])

    def test_only_the_books_in_the_tape_are_ever_shown(self):
        for b in ("BookMaker", "Circa", "Fanatics", "Caesars", "Consensus", "Open", "Novig", "Kalshi"):
            self.assertNotIn(b, F.FLAGS_BOOKS)
        rows = [mk("spread", "Pinnacle", ASOF - 3600, -3.5), mk("spread", "Pinnacle", ASOF - 600, -4.5)]
        for b in ("BookMaker", "Circa", "Fanatics", "Caesars", "Consensus", "Open", "DraftKings", "FanDuel"):
            rows += [mk("spread", b, ASOF - 5000, -3.5), mk("spread", b, ASOF - 3000, -4.5)]
        fl, se = flags(rows, "spread")
        self.assertEqual(sorted(fl["line"]["by_book"]), ["DraftKings", "FanDuel"])
        self.assertEqual(sorted(se["lines"]), ["DraftKings", "FanDuel", "Pinnacle"])


class FlagABoundary(unittest.TestCase):
    """Flag A at its threshold: the move in points of no-vig fair, same line, 24 hours."""

    def rows(self, g, fair_to, line=-3.5):
        return [mk(g, "Pinnacle", ASOF - 7200, line, 0.5), mk(g, "Pinnacle", ASOF - 3600, line, fair_to)]

    def test_each_sport_and_market_fires_at_its_threshold_and_not_below(self):
        for sport, by in EXPECT_T_A.items():
            for g, t in by.items():
                with self.subTest(sport=sport, market=g):
                    line = 220.5 if g == "total" else -3.5
                    at = flags(self.rows(g, 0.5 + t / 100, line), g, sport=sport)[0]["pin"]
                    below = flags(self.rows(g, 0.5 + (t - 0.01) / 100, line), g, sport=sport)[0]["pin"]
                    self.assertEqual((at["state"], at["pts"], at["t_a"]), ("toward", t, t))
                    self.assertEqual((below["state"], below["pts"]), ("quiet", round(t - 0.01, 2)))
                    away = flags(self.rows(g, 0.5 - t / 100, line), g, sport=sport)[0]["pin"]
                    self.assertEqual((away["state"], away["pts"]), ("away", -t))
                    self.assertEqual(flags(self.rows(g, 0.5 - (t - 0.01) / 100, line), g, sport=sport)[0]["pin"]["state"], "quiet")

    def test_state_of(self):
        self.assertEqual([F.state_of(x, 1.5) for x in (1.5, 1.49, -1.5, -1.49, 0)], ["toward", "quiet", "away", "quiet", "quiet"])
        self.assertIsNone(F.state_of(None, 1.5))
        self.assertIsNone(F.state_of(1.0, None))
        self.assertIsNone(F.state_of(True, 1.5))

    def test_the_user_example_plus_105_to_minus_129_is_toward_in_every_sport(self):
        # the side's price +105 then -129, the other side -125 then +109: no-vig fair 46.8% to 54.1%, about +7.3 points
        rows = [{"t": ASOF - 7200, "book": "Pinnacle", "ml": [-125, 105]}, {"t": ASOF - 600, "book": "Pinnacle", "ml": [109, -129]}]
        for sport in EXPECT_T_A:
            pin = flags(rows, "ml", sport=sport)[0]["pin"]
            self.assertEqual(pin["state"], "toward", sport)
            self.assertAlmostEqual(pin["pts"], 7.3, delta=0.2)
            self.assertEqual((pin["from"], pin["to"]), (105, -129))

    def test_a_line_change_is_not_a_price_move_and_a_first_quote_at_a_line_is_null(self):
        # the line moved -3.5 -> -4.5 and the new line has only the current quote: nothing to compare at this line (null, never a move of 0)
        rows = [sp("Pinnacle", ASOF - 7200, -3.5, 0.5), sp("Pinnacle", ASOF - 600, -4.5, 0.5)]
        fl = flags(rows, "spread")[0]
        self.assertEqual((fl["pin"], fl["why"]["pin"], fl["a"]), (None, "no_same_line_history", None))
        # a price move at the OLD line before the line change is ignored: only quotes at the current line are compared
        rows = [sp("Pinnacle", ASOF - 9000, -4.5, 0.5), sp("Pinnacle", ASOF - 7200, -3.5, 0.2), sp("Pinnacle", ASOF - 600, -4.5, 0.53)]
        pin = flags(rows, "spread")[0]["pin"]
        self.assertEqual((pin["state"], pin["t_from"], pin["pts"]), ("toward", ASOF - 9000, 3.0))   # the -3.5 quote (a different line) is skipped
        # the two-row minimum is on the quotes at THIS line: three Pinnacle rows, but one at the current line
        rows = [sp("Pinnacle", ASOF - 9000, -3.5, 0.5), sp("Pinnacle", ASOF - 7200, -3.0, 0.2), sp("Pinnacle", ASOF - 600, -4.5, 0.53)]
        self.assertEqual(flags(rows, "spread")[0]["why"]["pin"], "no_same_line_history")
        # a first quote at a new line that was already showing before the window opened is also null (both rows are before the window: the move is not "held", there is no earlier quote at this line)
        rows = [sp("Pinnacle", ASOF - 3 * DAY, -3.0, 0.5), sp("Pinnacle", ASOF - 2 * DAY, -3.5, 0.5)]
        self.assertEqual(flags(rows, "spread")[0]["why"]["pin"], "no_same_line_history")
        # a moneyline needs two readable rows in all
        self.assertEqual(flags([ml("Pinnacle", ASOF - 600, 0.5)], "ml")[0]["why"]["pin"], "no_pinnacle_history")

    def test_a_row_at_the_current_line_from_before_the_window_is_not_the_start_when_another_line_was_showing(self):
        """Repro: home spread -3.5 three days ago, -3 two days ago, -3.5 an hour ago. -3 was showing when the window opened, so there is no earlier quote at
        -3.5 inside the window: null, never a 6-point move from a 72-hour-old quote at a line the book had left."""
        rows = [sp("Pinnacle", ASOF - 3 * DAY, -3.5, 0.50), sp("Pinnacle", ASOF - 2 * DAY, -3.0, 0.40), sp("Pinnacle", ASOF - 3600, -3.5, 0.56)]
        fl, se = flags(rows, "spread")
        self.assertEqual((fl["pin"], fl["why"]["pin"], fl["a"]), (None, "no_same_line_history", None))
        self.assertNotIn(ASOF - 3 * DAY, [se["t0"] + 60 * x for x, _ in se["pin_px"]])          # the chart does not start from the 72-hour-old quote either
        self.assertEqual(se["t0"] + 60 * se["pin_px"][0][0], ASOF - 3600)
        # the total shape (cfb-miaoh-kentst): 50.5 then 49.5 then back to 50.5
        rows = [tot("Pinnacle", ASOF - 3 * DAY, 50.5, 0.50), tot("Pinnacle", ASOF - 2 * DAY, 49.5, 0.50), tot("Pinnacle", ASOF - 3600, 50.5, 0.56)]
        self.assertEqual(flags(rows, "total")[0]["why"]["pin"], "no_same_line_history")
        # the away side of a spread (cfb-ncar-vir): the home line -7 then -6.5 then -7, read for the away team
        rows = [sp("Pinnacle", ASOF - 4 * DAY, -7.0, 0.50), sp("Pinnacle", ASOF - 40 * 3600, -6.5, 0.50), sp("Pinnacle", ASOF - 600, -7.0, 0.44)]
        self.assertEqual(flags(rows, "spread", "away")[0]["why"]["pin"], "no_same_line_history")
        # with an earlier quote at the current line INSIDE the window, from is that quote (not the old one, not the other line)
        rows = [sp("Pinnacle", ASOF - 3 * DAY, -3.5, 0.50), sp("Pinnacle", ASOF - 2 * DAY, -3.0, 0.40), sp("Pinnacle", ASOF - 5 * 3600, -3.5, 0.50),
                sp("Pinnacle", ASOF - 3600, -3.5, 0.56)]
        pin = flags(rows, "spread")[0]["pin"]
        self.assertEqual((pin["t_from"], pin["pts"], pin["state"]), (ASOF - 5 * 3600, 6.0, "toward"))
        rows = [sp("Pinnacle", ASOF - 3 * DAY, -3.5, 0.50), sp("Pinnacle", ASOF - 2 * DAY, -3.0, 0.40), sp("Pinnacle", ASOF - 5 * 3600, -3.5, 0.50),
                sp("Pinnacle", ASOF - 3 * 3600, -3.5, 0.53), sp("Pinnacle", ASOF - 3600, -3.5, 0.56)]
        pin = flags(rows, "spread")[0]["pin"]
        self.assertEqual((pin["t_from"], pin["pts"]), (ASOF - 5 * 3600, 6.0))                   # the EARLIEST quote at the current line inside the window
        # the row showing at the window start at the SAME line is the start (the unchanged rule)
        rows = [sp("Pinnacle", ASOF - 3 * DAY, -3.0, 0.40), sp("Pinnacle", ASOF - 2 * DAY, -3.5, 0.50), sp("Pinnacle", ASOF - 3600, -3.5, 0.56)]
        pin = flags(rows, "spread")[0]["pin"]
        self.assertEqual((pin["t_from"], pin["pts"]), (ASOF - 2 * DAY, 6.0))
        # the chart of that last shape starts at the window start with the hanging price
        _, se = flags(rows, "spread")
        self.assertEqual(se["pin_px"][0][0], 0)

    def test_the_window_starts_at_the_row_hanging_when_it_opened(self):
        """v2f-2: the tape writes a row only on a change, so the number showing when the window opened is the LAST row at or before the window start."""
        ws = ASOF - DAY
        rows = [ml("Pinnacle", ws - 9000, 0.40), ml("Pinnacle", ws - 5000, 0.45), ml("Pinnacle", ASOF - 100, 0.60)]
        pin = flags(rows, "ml")[0]["pin"]
        self.assertEqual((pin["t_from"], pin["pts"]), (ws - 5000, 15.0))                      # the hanging row (0.45), not the older 0.40
        self.assertAlmostEqual(pin["from"], am(0.45))
        rows = [ml("Pinnacle", ws - 5000, 0.45), ml("Pinnacle", ws + 60, 0.50), ml("Pinnacle", ASOF - 100, 0.60)]
        self.assertEqual((flags(rows, "ml")[0]["pin"]["t_from"], flags(rows, "ml")[0]["pin"]["pts"]), (ws - 5000, 15.0))   # a row inside the window does not replace it
        rows = [ml("Pinnacle", ws, 0.45), ml("Pinnacle", ASOF - 100, 0.50)]
        self.assertEqual(flags(rows, "ml")[0]["pin"]["t_from"], ws)                           # a row exactly at the window start is the hanging one
        rows = [ml("Pinnacle", ws - 5000, 0.40), ml("Pinnacle", ws, 0.45), ml("Pinnacle", ASOF - 100, 0.60)]
        self.assertEqual((flags(rows, "ml")[0]["pin"]["t_from"], flags(rows, "ml")[0]["pin"]["pts"]), (ws, 15.0))   # the row AT the start beats the older one
        rows = [ml("Pinnacle", ws + 1, 0.45), ml("Pinnacle", ASOF - 100, 0.60)]
        pin = flags(rows, "ml")[0]["pin"]                                                      # nothing at or before the start: the first row inside
        self.assertEqual((pin["t_from"], pin["pts"]), (ws + 1, 15.0))
        rows = [ml("Pinnacle", ws - 9000, 0.40), ml("Pinnacle", ws - 5000, 0.60)]              # both before the window: it held all window, a real move of 0
        pin = flags(rows, "ml")[0]["pin"]
        self.assertEqual((pin["t_from"], pin["t_to"], pin["pts"], pin["state"]), (ws - 5000, ws - 5000, 0.0, "quiet"))
        # a single reading is never a move
        rows = [ml("Pinnacle", ws - 5000, 0.4)]
        self.assertEqual(flags(rows, "ml")[0]["why"]["pin"], "no_pinnacle_history")
        # the chart starts at the same hanging row
        rows = [sp("Pinnacle", ws - 5000, -3.5, 0.45), sp("Pinnacle", ws - 100, -3.5, 0.47), sp("Pinnacle", ASOF - 100, -3.5, 0.60)]
        fl, se = flags(rows, "spread")
        self.assertEqual((se["t0"], se["pin_px"][0][0], fl["pin"]["t_from"]), (ws, 0, ws - 100))

    def test_toward_and_away_are_mirrors_for_the_other_side(self):
        rows = [ml("Pinnacle", ASOF - 7200, 0.5), ml("Pinnacle", ASOF - 600, 0.58)]
        self.assertEqual(flags(rows, "ml", "home")[0]["pin"]["state"], "toward")
        self.assertEqual(flags(rows, "ml", "away")[0]["pin"]["state"], "away")
        self.assertEqual(flags(rows, "ml", "home")[0]["direction"], {"a": "toward", "c": None})
        rows = [tot("Pinnacle", ASOF - 7200, 220.5, 0.5), tot("Pinnacle", ASOF - 600, 220.5, 0.56)]
        self.assertEqual(flags(rows, "total", "over")[0]["pin"]["state"], "toward")
        self.assertEqual(flags(rows, "total", "under")[0]["pin"]["state"], "away")
        rows = [sp("Pinnacle", ASOF - 7200, -3.5, 0.5), sp("Pinnacle", ASOF - 600, -3.5, 0.56)]
        self.assertEqual((flags(rows, "spread", "home")[0]["pin"]["state"], flags(rows, "spread", "away")[0]["pin"]["state"]), ("toward", "away"))
        self.assertEqual(flags(rows, "spread", "away")[0]["pin"]["line"], 3.5)              # the away side reads the home line negated


class FlagCBoundary(unittest.TestCase):
    """Flag C on spreads and totals: Pinnacle's main line moved T_C, and 2 or more US books moved 1 point the same way."""

    def tape(self, g, sport, pin_move, books, base=None, norm=None):
        """Pinnacle and `books` ({book: points toward the side}) from `base` toward the side by the given moves, home / over side."""
        s = F._dir_sign(g, norm or NORM[g])
        base = base if base is not None else (220.5 if g == "total" else -3.5)
        rows = [mk(g, "Pinnacle", ASOF - 7200, base), mk(g, "Pinnacle", ASOF - 900, base + s * pin_move)]
        for b, mv in books.items():
            rows += [mk(g, b, ASOF - 7000, base), mk(g, b, ASOF - 800, base + s * mv)]
        return rows

    def test_each_sport_and_market_fires_at_its_threshold(self):
        for sport, by in EXPECT_T_C.items():
            for g, t in by.items():
                with self.subTest(sport=sport, market=g):
                    two = {"DraftKings": 1.0, "FanDuel": 1.0}
                    at = flags(self.tape(g, sport, t, two), g, sport=sport)[0]["line"]
                    self.assertEqual((at["kind"], at["state"], at["t_c"]), ("line", "toward", t))
                    below = flags(self.tape(g, sport, t - 0.5, two), g, sport=sport)[0]["line"]
                    self.assertEqual(below["state"], "quiet")
                    away = flags(self.tape(g, sport, -t, {"DraftKings": -1.0, "FanDuel": -1.0}), g, sport=sport)[0]["line"]
                    self.assertEqual(away["state"], "away")
                    self.assertEqual(flags(self.tape(g, sport, -(t - 0.5), {"DraftKings": -1.0, "FanDuel": -1.0}), g, sport=sport)[0]["line"]["state"], "quiet")

    def test_two_us_books_at_one_point_are_needed(self):
        g, sport = "spread", "nba"
        self.assertEqual(flags(self.tape(g, sport, 2.0, {"DraftKings": 1.0, "FanDuel": 0.5}), g)[0]["line"]["state"], "quiet")      # one at 1.0, one at 0.5
        self.assertEqual(flags(self.tape(g, sport, 2.0, {"DraftKings": 1.0, "FanDuel": 0.0}), g)[0]["line"]["state"], "quiet")
        self.assertEqual(flags(self.tape(g, sport, 2.0, {"DraftKings": 1.0, "FanDuel": 1.0}), g)[0]["line"]["state"], "toward")
        self.assertEqual(flags(self.tape(g, sport, 2.0, {"DraftKings": 1.0, "FanDuel": 1.0, "BetMGM": -3.0}), g)[0]["line"]["state"], "toward")  # a book against does not cancel the line rule
        ln = flags(self.tape(g, sport, 2.0, {"DraftKings": 1.5, "FanDuel": 1.0, "BetMGM": 0.5}), g)[0]["line"]
        self.assertEqual((ln["same_way"], ln["books"]), (3, 4))                      # Pinnacle + DraftKings + FanDuel moved 1 or more; BetMGM did not

    def test_pinnacle_must_move_too(self):
        self.assertEqual(flags(self.tape("spread", "nba", 1.5, {"DraftKings": 2.0, "FanDuel": 2.0}), "spread")[0]["line"]["state"], "quiet")

    def test_the_cornell_example_moves_toward_the_away_side(self):
        # Cornell (away) +22 to +19: the home line -22 to -19; BetMGM lowest at +18.5
        rows = [sp("Pinnacle", ASOF - 7200, -22.0), sp("Pinnacle", ASOF - 900, -19.0)]
        for b, to in (("DraftKings", -19.5), ("FanDuel", -19.0), ("BetMGM", -18.5), ("BetRivers", -19.5)):
            rows += [sp(b, ASOF - 7000, -22.0), sp(b, ASOF - 800, to)]
        fl = flags(rows, "spread", "away", "cbb")[0]
        ln = fl["line"]
        self.assertEqual((ln["state"], ln["pin"]), ("toward", {"from": 22.0, "to": 19.0}))
        self.assertEqual(ln["by_book"]["DraftKings"], [22.0, 19.5])
        self.assertEqual(ln["extreme"], {"book": "BetMGM", "value": 18.5})
        self.assertEqual((ln["same_way"], ln["books"], fl["books_moved"], fl["extreme"]), (5, 5, 5, ln["extreme"]))
        self.assertEqual((fl["c"], fl["direction"]["c"]), ("toward", "toward"))
        home = flags(rows, "spread", "home", "cbb")[0]["line"]
        self.assertEqual(home["state"], "away")                                          # the same tape, read for the other side
        self.assertEqual(home["extreme"], {"book": "BetMGM", "value": -18.5})            # the move was against home: furthest that way is the highest home line

    def test_totals_orientation(self):
        rows = self.tape("total", "nba", 3.0, {"DraftKings": 1.0, "FanDuel": 1.0})
        self.assertEqual(flags(rows, "total", "over")[0]["line"]["state"], "toward")
        self.assertEqual(flags(rows, "total", "under")[0]["line"]["state"], "away")
        self.assertEqual(flags(rows, "total", "over")[0]["line"]["extreme"]["value"], 223.5)
        self.assertEqual(flags(rows, "total", "under")[0]["line"]["pin"], {"from": 220.5, "to": 223.5})

    def test_extreme_ties_go_to_the_earliest_row_then_the_name(self):
        rows = [sp("Pinnacle", ASOF - 7200, -3.0), sp("Pinnacle", ASOF - 900, -5.0)]
        rows += [sp("FanDuel", ASOF - 7000, -3.0), sp("FanDuel", ASOF - 800, -5.0), sp("DraftKings", ASOF - 7000, -3.0), sp("DraftKings", ASOF - 700, -5.0),
                 sp("BetMGM", ASOF - 7000, -3.0), sp("BetMGM", ASOF - 800, -5.0)]
        ex = flags(rows, "spread")[0]["line"]["extreme"]
        self.assertEqual(ex, {"book": "Pinnacle", "value": -5.0})                         # all at -5: the tie goes to the oldest row (Pinnacle, 900 s before the cut)

    def test_a_quiet_state_publishes_no_direction_and_no_extreme(self):
        ln = flags(self.tape("spread", "nba", 0.5, {"DraftKings": 0.0, "FanDuel": 0.0}), "spread")[0]["line"]
        self.assertEqual((ln["state"], ln["same_way"], ln["extreme"]), ("quiet", None, None))


class FlagCMoneyline(unittest.TestCase):
    def rows(self, moves, pin=0.5):
        r = [ml("Pinnacle", ASOF - 7200, 0.5), ml("Pinnacle", ASOF - 900, pin)]
        for b, to in moves.items():
            r += [ml(b, ASOF - 7000, 0.5), ml(b, ASOF - 800, to)]
        return r

    def test_two_us_books_at_the_moneyline_threshold_and_none_the_other_way(self):
        for sport, by in EXPECT_T_A.items():
            t = by["ml"]
            with self.subTest(sport=sport):
                up = {"DraftKings": 0.5 + t / 100, "FanDuel": 0.5 + t / 100}
                ln = flags(self.rows(up), "ml", sport=sport)[0]["line"]
                self.assertEqual((ln["kind"], ln["state"], ln["t_c"], ln["books"], ln["same_way"]), ("price", "toward", t, 2, 2))
                self.assertEqual(flags(self.rows({"DraftKings": 0.5 + t / 100, "FanDuel": 0.5 + (t - 0.01) / 100}), "ml", sport=sport)[0]["line"]["state"], "quiet")
                dn = {"DraftKings": 0.5 - t / 100, "FanDuel": 0.5 - t / 100}
                self.assertEqual(flags(self.rows(dn), "ml", sport=sport)[0]["line"]["state"], "away")
                mixed = dict(up, BetMGM=0.5 - t / 100)
                self.assertEqual(flags(self.rows(mixed), "ml", sport=sport)[0]["line"]["state"], "quiet")                  # one the other way: no verdict

    def test_by_book_carries_american_prices_and_the_extreme_is_the_largest_move(self):
        r = self.rows({"DraftKings": 0.56, "FanDuel": 0.58, "BetMGM": 0.57})
        ln = flags(r, "ml", sport="nfl")[0]["line"]
        self.assertEqual(ln["state"], "toward")
        self.assertEqual(ln["extreme"]["book"], "FanDuel")
        self.assertAlmostEqual(ln["extreme"]["value"], am(0.58))
        self.assertAlmostEqual(ln["by_book"]["DraftKings"][0], am(0.5))
        self.assertAlmostEqual(ln["by_book"]["DraftKings"][1], am(0.56))
        self.assertEqual((ln["books"], ln["same_way"]), (3, 3))

    def test_one_us_book_is_not_enough(self):
        fl, _ = flags(self.rows({"DraftKings": 0.7}), "ml")
        self.assertIsNone(fl["line"])
        self.assertEqual(fl["why"]["line"], "too_few_books")
        self.assertIsNone(fl["c"])


class NullsAndPointInTime(unittest.TestCase):
    def full(self, g="spread"):
        rows = [mk(g, "Pinnacle", ASOF - 7200, -3.5, lim=[1, 3000, 1]), mk(g, "Pinnacle", ASOF - 5000, -5.5, 0.5), mk(g, "Pinnacle", ASOF - 900, -5.5, 0.55, lim=[1, 9000, 1])]
        for b in ("DraftKings", "FanDuel", "BetMGM"):
            rows += [mk(g, b, ASOF - 7000, -3.5), mk(g, b, ASOF - 800, -5.0)]
        return rows

    def test_a_row_after_the_cut_never_changes_a_flag(self):
        rows = self.full()
        base = flags(rows, "spread")
        later = rows + [sp("Pinnacle", ASOF + 1, -9.5, 0.9, lim=[1, 99999, 1]), sp("Pinnacle", ASOF + 2, -9.5, 0.1), sp("FanDuel", ASOF + 5, -12.0), sp("DraftKings", ASOF + 60, -12.0),
                        sp("BetMGM", ASOF + 90, -12.0)]
        self.assertEqual(flags(later, "spread"), base)
        self.assertEqual(flags(later, "spread", asof=ASOF + 400)[0]["pin"]["line"], -9.5)      # a later asof does read them: the cut is the only gate
        self.assertEqual(flags(rows + [sp("Pinnacle", ASOF, -6.5)], "spread")[0]["line"]["pin"]["to"], -6.5)   # a row AT the cut is read

    def test_reasons_for_every_null(self):
        none, _ = flags([], "spread")
        self.assertEqual(none["why"], {"pin": "no_tape_rows_for_game", "limit": "no_limit_before_cut", "line": "too_few_books"})
        self.assertTrue(all(none[k] is None for k in ("pin", "limit", "line", "a", "c", "books_moved", "extreme")))
        self.assertEqual(none["direction"], {"a": None, "c": None})
        none2, ser = F.flags_block(None, "ml", "home", ASOF, "nba")
        self.assertEqual((none2["why"]["pin"], ser), ("no_tape_rows_for_game", None))
        one, _ = flags([sp("Pinnacle", ASOF - 600, -3.5)], "spread")
        self.assertEqual(one["why"]["pin"], "no_pinnacle_history")
        self.assertIsNone(one["a"])                                                   # one reading is not "quiet"
        self.assertEqual(flags(self.full(), "spread", norm="sideways")[0]["why"], {"pin": "side_unmapped", "limit": None, "line": "side_unmapped"})
        self.assertIsNone(F.flags_block(self.full(), "spread", None, ASOF, "nba")[1])
        self.assertEqual(F.flags_block(self.full(), "spread", None, ASOF, "nba")[0]["why"]["pin"], "side_unmapped")
        two_books = [r for r in self.full() if r["book"] in ("Pinnacle", "DraftKings")]
        self.assertEqual(flags(two_books, "spread")[0]["why"]["line"], "too_few_books")
        no_pin = [r for r in self.full() if r["book"] != "Pinnacle"]
        self.assertEqual((flags(no_pin, "spread")[0]["why"]["line"], flags(no_pin, "spread")[0]["why"]["pin"]), ("too_few_books", "no_tape_rows_for_game"))

    def test_missing_values_are_never_zero_and_never_quiet(self):
        rows = [{"t": ASOF - 7200, "book": "Pinnacle", "ml": [None, -120]}, {"t": ASOF - 600, "book": "Pinnacle", "ml": [100, None]}]
        fl, _ = flags(rows, "ml")
        self.assertIsNone(fl["pin"])
        self.assertIsNone(fl["a"])
        self.assertIsNone(fl["span_min"])
        self.assertIsNone(fl["limit"])
        for r in (self.full(),):
            fl, _ = flags(r, "spread")
            self.assertNotEqual(fl["line"]["same_way"], 0 if fl["line"]["state"] == "quiet" else -1)

    def test_a_row_with_a_line_and_no_price_is_not_a_price_reading(self):
        rows = [{"t": ASOF - 7200, "book": "Pinnacle", "sp": [-3.5, -110, -110]}, {"t": ASOF - 600, "book": "Pinnacle", "sp": [-3.5, None, None]}]
        fl, se = flags(rows, "spread")
        self.assertIsNone(fl["pin"])
        self.assertEqual(fl["why"]["pin"], "no_pinnacle_history")                    # one priced row is not a history; the unpriced one is not a 0
        self.assertEqual(se["pin_px"], [[0, -110]])
        self.assertIn("Pinnacle", se["lines"])                                        # its line is still a stored number

    def test_the_limit_never_reads_a_row_after_the_cut_even_if_handed_one(self):
        future = [dict(sp("Pinnacle", ASOF - 100, -3.5), lim=[1, 3000, 1]), dict(sp("Pinnacle", ASOF + 100, -3.5), lim=[1, 99999, 1])]
        with mock.patch.object(F, "_by_book", return_value={"Pinnacle": future}):
            self.assertEqual(F.flag_limit(future, "spread", ASOF)[0]["to"], 3000)

    def test_a_stale_feed_is_unreadable_not_quiet(self):
        rows = self.full()
        fresh = flags(rows, "spread", hb={"pinnacle": ASOF - 600, "us": ASOF - 1800})[0]
        self.assertIsNotNone(fresh["pin"])
        self.assertEqual(fresh["src_age_min"], {"pinnacle": 10, "us": 30})              # exactly 30 minutes is still readable
        self.assertIsNotNone(fresh["line"])
        self.assertIsNotNone(flags(rows, "spread", hb={"pinnacle": ASOF - 1800, "us": ASOF})[0]["pin"])
        stale = flags(rows, "spread", hb={"pinnacle": ASOF - 1801, "us": ASOF - 60})[0]
        self.assertEqual((stale["pin"], stale["line"]), (None, None))
        self.assertEqual((stale["why"]["pin"], stale["why"]["line"]), ("pinnacle_feed_stale", "pinnacle_feed_stale"))
        self.assertIsNotNone(stale["limit"])                                              # the limit is a stored fact, never gated by a heartbeat
        books = flags(rows, "spread", hb={"pinnacle": ASOF - 60, "us": ASOF - 1801})[0]
        self.assertEqual((books["why"]["pin"], books["why"]["line"], books["pin"] is not None), (None, "books_feed_stale", True))
        none = flags(rows, "spread", hb=None)[0]
        self.assertEqual(none["src_age_min"], {"pinnacle": None, "us": None})          # history and frozen cards: read as written
        self.assertIsNotNone(none["pin"])

    def test_span_minutes(self):
        rows = [ml("Pinnacle", ASOF - 5400, 0.5), ml("Pinnacle", ASOF - 60, 0.5)]
        self.assertEqual(flags(rows, "ml")[0]["span_min"], 90)
        rows = [ml("Pinnacle", ASOF - 3 * DAY, 0.5), ml("Pinnacle", ASOF - DAY + 60, 0.5), ml("Pinnacle", ASOF - 60, 0.5)]
        self.assertEqual(flags(rows, "ml")[0]["span_min"], 1440)                                    # from = the row hanging when the window opened
        rows = [ml("Pinnacle", ASOF - 3 * DAY, 0.5), ml("Pinnacle", ASOF - 2 * DAY, 0.5)]            # nothing inside: the last row before the window, capped at the window
        self.assertEqual(flags(rows, "ml")[0]["span_min"], 1440)


class LimitFact(unittest.TestCase):
    ROWS = [dict(sp("Pinnacle", ASOF - 9000, -3.5), lim=[5000, 3000, 2500]), dict(sp("Pinnacle", ASOF - 5000, -3.5), lim=[6000, 7000, 2500]),
            dict(sp("Pinnacle", ASOF - 600, -3.5), lim=[6000, 20000, 4000]), dict(sp("Pinnacle", ASOF + 100, -3.5), lim=[1, 99999, 1])]

    def test_from_is_the_limit_showing_when_the_window_opened_and_to_is_copied_from_limit_read(self):
        ws = ASOF - DAY
        rows = [dict(sp("Pinnacle", ws - 90000, -3.5), lim=[1, 500, 1]), dict(sp("Pinnacle", ws - 5000, -3.5), lim=[1, 1000, 1]),
                dict(sp("Pinnacle", ws + 100, -3.5), lim=[1, 2000, 1]), dict(sp("Pinnacle", ASOF - 600, -3.5), lim=[1, 20000, 1]), dict(sp("Pinnacle", ASOF + 100, -3.5), lim=[1, 99999, 1])]
        fact, why = F.flag_limit(rows, "spread", ASOF)
        lr = SIG.limit_read(rows, "spread", ASOF)
        self.assertEqual((fact["from"], fact["t_from"], fact["to"], fact["rows"], why), (1000, ws - 5000, 20000, 4, None))
        self.assertEqual((fact["to"], fact["rows"]), (lr["now"], lr["rows"]))                 # `to` and the row count are copied from limit_read
        self.assertEqual(lr["open"], 500)                                                      # ...whose `open` is the first limit EVER: not what the window measures
        self.assertEqual(sorted(fact), ["asof", "from", "market", "rows", "t_from", "to"])    # no pct, no rising: a fact line only (D1)
        rows2 = [dict(sp("Pinnacle", ws + 100, -3.5), lim=[1, 2000, 1]), dict(sp("Pinnacle", ASOF - 600, -3.5), lim=[1, 20000, 1])]
        self.assertEqual(F.flag_limit(rows2, "spread", ASOF)[0]["from"], 2000)                 # no row at or before the start: the first inside
        self.assertEqual(F.flag_limit(self.ROWS, "ml", ASOF)[0]["to"], 6000)                   # each market reads its own slot
        self.assertEqual(F.flag_limit(self.ROWS, "total", ASOF)[0]["from"], 2500)
        zero = [dict(sp("Pinnacle", ws - 50, -3.5), lim=[1, 0, 1]), dict(sp("Pinnacle", ASOF - 600, -3.5), lim=[1, 7000, 1])]
        self.assertEqual(F.flag_limit(zero, "spread", ASOF)[0]["from"], 7000)                  # a stored 0 is not a limit (never read as one)

    def test_there_is_no_limit_chip_or_rule_anywhere_in_the_block(self):
        fl, se = flags(self.ROWS + [mk("spread", "DraftKings", ASOF - 100, -3.5)], "spread")
        blob = json.dumps([fl, se])
        for word in ("rising", "falling", "tested", "chip", "pct"):
            self.assertNotIn(word, blob)
        self.assertEqual(sorted(fl["limit"]), ["asof", "from", "market", "rows", "t_from", "to"])

    def test_one_reading_and_no_reading_and_a_bad_reading(self):
        one = F.flag_limit([dict(ml("Pinnacle", ASOF - 60, 0.5), lim=[1500, 1, 1])], "ml", ASOF)[0]
        self.assertEqual((one["from"], one["to"], one["rows"]), (1500, 1500, 1))
        self.assertEqual(F.flag_limit([ml("Pinnacle", ASOF - 60, 0.5)], "ml", ASOF), (None, "no_limit_before_cut"))
        bad = [dict(ml("Pinnacle", ASOF - 60, 0.5), lim="x"), dict(ml("Pinnacle", ASOF - 50, 0.5), lim=[]), dict(ml("Pinnacle", ASOF - 40, 0.5), lim=["a", 1, 1]),
               dict(ml("Pinnacle", ASOF - 30, 0.5), lim=[2500, 1, 1]), dict(ml("DraftKings", ASOF - 20, 0.5), lim=[9, 9, 9])]
        got = F.flag_limit(bad, "ml", ASOF)[0]
        self.assertEqual((got["from"], got["to"]), (2500, 2500))                           # only Pinnacle's, only well-formed

    def test_the_limit_equals_the_stored_signals_limit_on_a_card(self):
        rows = [dict(sp("Pinnacle", ASOF - 9000, -3.5), lim=[1, 3000, 1]), dict(sp("Pinnacle", ASOF - 600, -3.5), lim=[1, 20000, 1])]
        c = TP.Additive().card(vault=VAULT, quotes=TP.Malformed.Quotes(rows))
        self.assertEqual(c["markets"]["spread"]["v2"]["flags"]["limit"]["to"], 20000)


class Downsampling(unittest.TestCase):
    def series(self, n, f=lambda i: 20 + (i * 37) % 23):
        """Values 20..42 with neither the first nor the last point at an extreme, so a dropped endpoint is not rescued by an extreme."""
        pts = [[i * 10, f(i)] for i in range(n)]
        pts[n // 3][1], pts[2 * n // 3][1] = 500, -500
        return pts

    def test_at_most_n_points_endpoints_extremes_and_order_kept(self):
        pts = self.series(200)
        for n in (4, 8, 16):
            out = F.downsample(pts, n)
            self.assertLessEqual(len(out), n)
            self.assertEqual((out[0], out[-1]), (pts[0], pts[-1]))
            self.assertIn(min(p[1] for p in pts), [p[1] for p in out])
            self.assertIn(max(p[1] for p in pts), [p[1] for p in out])
            self.assertEqual([p[0] for p in out], sorted(p[0] for p in out))
            self.assertTrue(all(p in pts for p in out))                                     # values and times are never invented

    def test_a_tiny_cap_keeps_the_endpoints_first_and_never_exceeds_itself(self):
        pts = self.series(50)
        for n in (2, 3, 4):
            out = F.downsample(pts, n)
            self.assertLessEqual(len(out), n)
            self.assertEqual((out[0], out[-1]), (pts[0], pts[-1]))
        self.assertEqual(F.downsample(pts, 0), [])

    def test_a_spike_in_the_middle_survives(self):
        pts = [[i, 20 + (i * 37) % 23] for i in range(100)]
        pts[47][1] = 99
        pts[63][1] = -40
        out = F.downsample(pts, 16)
        self.assertEqual(len(out), 16)
        self.assertIn([47, 99], out)
        self.assertIn([63, -40], out)
        self.assertEqual((out[0], out[-1]), (pts[0], pts[-1]))

    def test_consecutive_duplicates_dropped_but_the_end_is_kept(self):
        self.assertEqual(F.downsample([[0, 1], [1, 1], [2, 1], [3, 2], [4, 2], [5, 2]], 16), [[0, 1], [3, 2], [5, 2]])
        self.assertEqual(F.downsample([[0, 7]], 16), [[0, 7]])
        self.assertEqual(F.downsample([], 16), [])
        self.assertEqual(F.downsample([[0, 1], [9, 1]], 16), [[0, 1], [9, 1]])

    def test_a_short_series_is_unchanged(self):
        pts = [[0, 1], [5, 2], [9, 3]]
        self.assertEqual(F.downsample(pts, 16), pts)

    def tape(self, changes=60):
        rows = []
        for b in ("Pinnacle",) + US:
            for i in range(changes):
                rows.append(sp(b, ASOF - DAY + 100 + i * 1400, -3.0 - (i % 9) * 0.5 - (0.5 if b == "FanDuel" else 0), 0.5 + ((i * 3) % 7 - 3) / 100))
        return rows

    def test_the_series_is_in_whole_minutes_after_t0_and_capped(self):
        fl, se = flags(self.tape(), "spread")
        self.assertEqual(se["unit"], "min")
        self.assertEqual(sorted(se["lines"]), sorted(F.FLAGS_BOOKS))
        for b, pts in list(se["lines"].items()) + [("pin_px", se["pin_px"])]:
            self.assertLessEqual(len(pts), 16, b)
            self.assertTrue(all(isinstance(p[0], int) and p[0] >= 0 for p in pts), b)
        self.assertEqual(min(p[0] for pts in se["lines"].values() for p in pts), 0)
        self.assertEqual(se["lines"]["Pinnacle"][-1][1], fl["line"]["pin"]["to"])           # the last point is the number now
        self.assertEqual(se["lines"]["Pinnacle"][0][1], fl["line"]["pin"]["from"])

    def test_moneyline_has_one_series_and_no_lines(self):
        rows = [ml("Pinnacle", ASOF - 7200 + 100 * i, 0.5 + i / 100) for i in range(20)]
        _, se = flags(rows, "ml")
        self.assertNotIn("lines", se)
        self.assertLessEqual(len(se["pin_px"]), 16)

    def test_the_carried_row_sits_at_the_window_start(self):
        rows = [sp("Pinnacle", ASOF - 2 * DAY, -3.5, 0.5), sp("Pinnacle", ASOF - 60, -3.5, 0.6)]
        _, se = flags(rows, "spread")
        self.assertEqual(se["t0"], ASOF - DAY)
        self.assertEqual(se["pin_px"][0][0], 0)
        self.assertEqual(se["pin_px"][-1][0], 1439)


class SizeGate(unittest.TestCase):
    def doc(self, plays=12, pad_series=3000, pad_book=500, pad_flags=200):
        games = []
        for i in range(plays):
            games.append({"ev": f"e{i}", "markets": {"spread": {"sides": {}, "v2": {
                "rule": "v2t-1", "tier": "thin", "flags": {"rule": "v2f-2", "pad": "f" * pad_flags, "line": {"state": "toward", "by_book": {"X": "b" * pad_book}}},
                "series": {"pad": "s" * pad_series}}}}})
        return {"built": 1, "games": games, "v2_plays": {"rule": "v2t-1", "flags": {"rule": "v2f-2"}}}

    def test_under_budget_is_untouched(self):
        d = self.doc()
        before = json.dumps(d)
        out, dropped = CS.enforce_flags(d, 90)
        self.assertEqual((dropped, json.dumps(out)), ([], before))

    def test_drop_order_series_then_by_book_then_flags(self):
        d = self.doc()
        total = CS.flags_kb(d)
        out, dropped = CS.enforce_flags(copy.deepcopy(d), total - 0.5)
        self.assertEqual(dropped, ["series"])
        self.assertTrue(all("series" not in g["markets"]["spread"]["v2"] and "by_book" in g["markets"]["spread"]["v2"]["flags"]["line"] for g in out["games"]))
        out, dropped = CS.enforce_flags(self.doc(), 1)
        self.assertEqual(dropped, ["series", "by_book", "flags"])
        for g in out["games"]:
            v = g["markets"]["spread"]["v2"]
            self.assertEqual(v, {"rule": "v2t-1", "tier": "thin"})                         # the rest of V2 is untouched
        self.assertNotIn("flags", out["v2_plays"])
        self.assertEqual(out["v2_plays"]["rule"], "v2t-1")

    def test_by_book_is_dropped_before_the_flags_themselves(self):
        d = self.doc(plays=40, pad_series=0, pad_book=2000, pad_flags=100)
        kb = CS.flags_kb(d)
        out, dropped = CS.enforce_flags(d, kb / 2)
        self.assertEqual(dropped, ["series", "by_book"])
        self.assertTrue(all("flags" in g["markets"]["spread"]["v2"] for g in out["games"]))
        self.assertLessEqual(CS.flags_kb(out), kb / 2)

    def test_a_malformed_card_does_not_stop_the_gate(self):
        d = {"games": [None, {"markets": None}, {"markets": {"ml": None, "spread": {"v2": None}, "total": {"v2": {"flags": 5, "series": 1}}}}]}
        out, dropped = CS.enforce_flags(d, 0)
        self.assertEqual(dropped, ["series", "by_book", "flags"])

    def test_enforce_live_drops_flags_and_still_publishes_the_rest_of_v2(self):
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "live.json")
            d = self.doc(plays=40, pad_series=4000, pad_book=200, pad_flags=100)
            with open(path, "w") as f:
                json.dump(d, f, separators=(",", ":"))
            rep = []
            kb, stripped = CS.enforce_live(path, flags_max_kb=50, report=rep)
            self.assertFalse(stripped)                                                       # V2 as a whole is within 250 KB: not stripped
            self.assertEqual(len(rep), 1)
            self.assertIn("dropped series", rep[0])
            got = json.load(open(path))
            self.assertTrue(all("series" not in g["markets"]["spread"]["v2"] and "tier" in g["markets"]["spread"]["v2"] for g in got["games"]))
            self.assertIn("v2_plays", got)

    def test_over_the_v2_budget_after_the_flags_drop_still_strips_to_v1(self):
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "live.json")
            d = self.doc(plays=2)
            d["games"][0]["markets"]["spread"]["v2"]["pad"] = "x" * 260_000
            with open(path, "w") as f:
                json.dump(d, f, separators=(",", ":"))
            kb, stripped = CS.enforce_live(path)
            self.assertTrue(stripped)
            self.assertNotIn("v2", open(path).read().replace('"v2_', ""))

    def test_the_command_prints_a_warning_when_it_drops_flags(self):
        import subprocess
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "live.json")
            with open(path, "w") as f:
                json.dump(self.doc(plays=60, pad_series=2000, pad_book=100, pad_flags=100), f, separators=(",", ":"))
            r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "sharps_v2", "check_size.py"), "--live", path], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertIn("::warning::v2 flags and charts", r.stdout)

    def test_a_worst_case_slate_fits_after_the_gate(self):
        rows = DownsamplingTape.rows()
        games = []
        for i in range(51):
            fl, se = F.flags_block(rows, "spread", "home", ASOF, "nba")
            games.append({"markets": {"spread": {"v2": {"tier": "thin", "flags": fl, "series": se}}}})
        d = {"games": games}
        out, dropped = CS.enforce_flags(d, CS.FLAGS_MAX_KB)
        self.assertLessEqual(CS.flags_kb(out), CS.FLAGS_MAX_KB)
        self.assertEqual(CS.FLAGS_MAX_KB, 90)


class DownsamplingTape:
    @staticmethod
    def rows():
        return Downsampling().tape()


class Guard(unittest.TestCase):
    """A bad tape row, a bad feed or a raising flag build never stops a card, the freeze or the publish."""

    BAD = list(TP.Malformed.BAD) + [
        {"t": ASOF - 10, "book": "Pinnacle", "sp": [-3.5, "x", None]}, {"t": ASOF - 10, "book": "Pinnacle", "tot": "oops"}, {"t": ASOF - 10, "book": "Pinnacle", "ml": [0, 0]},
        {"t": ASOF - 10, "book": "Pinnacle", "sp": [None, -110, -110], "lim": [1, None, 3]}, {"t": float("nan"), "book": "Pinnacle", "ml": [100, -120]},
        {"t": ASOF - 5, "book": "DraftKings", "sp": [float("inf"), -110, -110]}, {"t": True, "book": "FanDuel", "ml": [100, -120]}, {"book": "FanDuel"}, [], 7]

    def test_flags_block_never_raises_on_malformed_rows(self):
        good = [mk("spread", "Pinnacle", ASOF - 600, -3.5), mk("spread", "DraftKings", ASOF - 500, -3.5)]
        for rows in (self.BAD, self.BAD + good, good + self.BAD):
            for g in GROUPS:
                for norm in ("home", "away", "over", "under", None):
                    for sport in ("nba", "nfl", "cbb", "cfb", "xfl"):
                        fl, se = F.flags_block(rows, g, norm, ASOF, sport, {"pinnacle": ASOF})
                        self.assertEqual(fl["rule"], "v2f-2")
                        self.assertIsInstance(fl["why"], dict)
                        json.dumps([fl, se])

    def test_an_unknown_sport_has_no_threshold_not_a_guess(self):
        fl, _ = flags([mk("ml", "Pinnacle", ASOF - 600, None, 0.5), mk("ml", "Pinnacle", ASOF - 60, None, 0.9)], "ml", sport="xfl")
        self.assertEqual((fl["pin"], fl["why"]["pin"]), (None, "no_threshold"))

    def test_a_raising_flag_build_leaves_the_card_with_null_flags_and_a_warning(self):
        rows = [sp("Pinnacle", ASOF - 600, -3.5), sp("Pinnacle", ASOF - 60, -4.5)]
        quotes = TP.Malformed.Quotes(rows)
        c0 = TP.Additive().card(vault=VAULT, quotes=quotes)
        err = io.StringIO()
        with mock.patch.object(P.F, "flags_block", side_effect=TypeError("boom")), contextlib.redirect_stderr(err):
            c1 = TP.Additive().card(vault=VAULT, quotes=quotes)
        v = c1["markets"]["spread"]["v2"]
        self.assertEqual((v["flags"], v["series"], v["flags_error"]), (None, None, "TypeError"))
        self.assertIn("::warning::v2 flags dropped for nba-a-b-2027-01-15 spread: TypeError", err.getvalue())
        self.assertIn("exec", v)                                                              # every other V2 key is still built
        drop = lambda c: {g: {k: x for k, x in m["v2"].items() if k not in ("flags", "series", "flags_error", "move_grade")} for g, m in c["markets"].items()}   # move_grade reads the flags (rule mg-1), so it follows them
        self.assertEqual(drop(c0), drop(c1))
        self.assertEqual(json.dumps(P.strip_plays_v2(c0)), json.dumps(P.strip_plays_v2(c1)))

    def test_the_card_builds_on_malformed_tape_rows(self):
        c = TP.Additive().card(vault=VAULT, quotes=TP.Malformed.Quotes(self.BAD))
        self.assertTrue(all("v2" in m for m in c["markets"].values()))
        self.assertIn("flags", c["markets"]["spread"]["v2"])


class AdditiveOnly(unittest.TestCase):
    ROWS = [dict(sp("Pinnacle", ASOF - 7200, -3.5, 0.5), lim=[1, 3000, 1]), dict(sp("Pinnacle", ASOF - 900, -6.0, 0.5)), dict(sp("Pinnacle", ASOF - 600, -6.0, 0.5), lim=[1, 9000, 1])]
    ROWS += [sp(b, ASOF - 7000, -3.5) for b in US[:3]] + [sp(b, ASOF - 500, -5.0) for b in US[:3]]

    def card(self, **kw):
        return TP.Additive().card(vault=VAULT, quotes=TP.Malformed.Quotes(self.ROWS), **kw)

    def test_flags_only_on_a_shown_play_and_only_inside_v2(self):
        c = self.card()
        self.assertIsNone(c["markets"]["ml"]["v2"]["side"])
        self.assertNotIn("flags", c["markets"]["ml"]["v2"])                                   # no shown play, no flags
        self.assertNotIn("series", c["markets"]["ml"]["v2"])
        v = c["markets"]["spread"]["v2"]
        self.assertEqual(v["flags"]["rule"], "v2f-2")
        self.assertEqual(v["flags"]["asof"], ASOF)
        self.assertEqual((v["flags"]["line"]["state"], v["flags"]["a"]), ("away", "quiet"))   # the home line went -3.5 to -6.0: toward home, so against the away side A
        for k in ("flags", "series"):
            self.assertNotIn(k, P.strip_plays_v2(c)["markets"]["spread"])                    # strip_plays_v2 removes all of v2, so the V1 bytes are the same
        self.assertEqual(json.dumps(P.strip_plays_v2(c), separators=(",", ":")), json.dumps(P.strip_plays_v2(self.card()), separators=(",", ":")))

    def test_old_and_new_differ_only_in_the_new_keys(self):
        with mock.patch.object(P.F, "flags_block", return_value=(None, None)):
            old = self.card()
        new = self.card()
        for c in (old, new):
            for m in c["markets"].values():
                for k in ("flags", "series", "move_grade"):                                  # move_grade reads the flags (rule mg-1), so it follows them
                    m["v2"].pop(k, None)
        self.assertEqual(json.dumps(old, sort_keys=True), json.dumps(new, sort_keys=True))

    def test_tier_and_both_sizes_never_read_the_flags(self):
        def with_flags(fl):
            with mock.patch.object(P.F, "flags_block", return_value=(fl, None)):
                v = self.card()["markets"]["spread"]["v2"]
            return {k: v[k] for k in ("tier", "facts", "shown_units", "shadow_units", "shadow_rule", "untested", "conflict", "lead")}
        a = with_flags(None)
        for fl in ({"a": "toward", "c": "toward"}, {"a": "away", "c": "away", "pin": {"state": "away"}}, "garbage", {"direction": "xx"}, 7):
            self.assertEqual(with_flags(fl), a)
        self.assertEqual((a["shown_units"], a["shadow_rule"]), (1, "v2s-1"))
        for fn in (P.shown_units, P.shadow_units, P.tier_of, P.facts, P.shown_units_at):
            self.assertNotIn("flags", inspect.getsource(fn), fn.__name__)

    def test_no_gate_ladder_or_lock_source_mentions_the_flags(self):
        for rel in ("scripts/sf_rungs.py", "scripts/sf_tiers.py", "scripts/sf_publish.py", "scripts/sf_signals.py", "scripts/sf_solo.py"):
            p = os.path.join(ROOT, rel)
            if os.path.exists(p):
                src = open(p, encoding="utf-8").read()
                self.assertNotIn("flags_v2", src, rel)
                self.assertNotIn("v2f", src, rel)
                self.assertNotIn('["flags"]', src, rel)
        build = open(os.path.join(ROOT, "scripts", "build_side_cards.py"), encoding="utf-8").read()
        self.assertNotIn('v2["flags"]', build)
        imports = [l.strip() for l in inspect.getsource(F).splitlines() if l.startswith(("import ", "from "))]
        self.assertEqual(imports, ["import os, sys", "import sf_signals as SIG  # noqa: E402"])             # the flag module reads nothing else: no gate, no rung, no Top Reads
        self.assertNotIn("flags_v2", open(os.path.join(ROOT, "scripts", "sharps_v2", "tier_record.py"), encoding="utf-8").read())

    def test_frozen_cards_read_as_written_and_live_cards_read_the_heartbeat(self):
        frozen = self.card(frozen=True, heartbeat={"pinnacle": ASOF - 9999, "us": ASOF - 9999})
        self.assertEqual(frozen["markets"]["spread"]["v2"]["flags"]["src_age_min"], {"pinnacle": None, "us": None})
        self.assertIsNotNone(frozen["markets"]["spread"]["v2"]["flags"]["pin"])
        live = self.card(frozen=False, now=ASOF - 100, heartbeat={"pinnacle": ASOF - 9999, "us": ASOF - 9999})
        f = live["markets"]["spread"]["v2"]["flags"]
        self.assertEqual((f["pin"], f["why"]["pin"]), (None, "pinnacle_feed_stale"))


class ForwardLog(unittest.TestCase):
    def frozen(self, with_flags=True):
        c = TP.Additive().card(vault=VAULT, quotes=TP.Malformed.Quotes(AdditiveOnly.ROWS))
        if not with_flags:
            for m in c["markets"].values():
                m["v2"].pop("flags", None)
                m["v2"].pop("series", None)
        return c

    def test_new_rows_carry_mf_and_old_keys_keep_their_values(self):
        c = self.frozen()
        new = P.log_row("nba/frozen/d/x.json", c, "spread", 1)
        old = P.log_row("nba/frozen/d/x.json", self.frozen(False), "spread", 1)
        self.assertIn("mf", new)
        self.assertNotIn("mf", old)                                                           # a card built before the flags: "not logged", never quiet
        self.assertEqual({k: v for k, v in new.items() if k != "mf"}, old)
        self.assertEqual(new["mf"], F.mf_of(c["markets"]["spread"]["v2"]["flags"]))
        self.assertEqual(sorted(new["mf"]), sorted(["rule", "asof", "span_min", "src_age_min", "pin_state", "pin_pts", "pin_from", "pin_to", "pin_line", "lim_from", "lim_to",
                                                    "line_kind", "line_state", "line_pin_from", "line_pin_to", "line_books", "line_same_way", "line_extreme_book",
                                                    "line_extreme", "why"]))
        self.assertNotIn("by_book", json.dumps(new["mf"]))
        self.assertEqual((new["mf"]["lim_from"], new["mf"]["lim_to"]), (3000, 9000))
        json.dumps(new)

    def test_a_dropped_flag_block_logs_a_null_mf_not_a_missing_one(self):
        c = self.frozen()
        c["markets"]["spread"]["v2"]["flags"] = None
        self.assertIn("mf", P.log_row("r", c, "spread", 1))
        self.assertIsNone(P.log_row("r", c, "spread", 1)["mf"])

    def test_the_repair_pass_equals_the_on_time_row(self):
        c = self.frozen()
        with tempfile.TemporaryDirectory() as root:
            rel = "nba/frozen/2027-01-15/x@1800000900.json"
            os.makedirs(os.path.join(root, os.path.dirname(rel)))
            json.dump(c, open(os.path.join(root, rel), "w"))
            on_time = [P.log_row(rel, c, g, 5) for g in ("spread",)]
            self.assertEqual(P.sync_log(root, "nba", 1_800_000_900, extra=[rel]), 1)
            lines = [json.loads(l) for l in open(os.path.join(root, "nba", "v2_tier", "2027-01.jsonl"))]
            self.assertEqual({k: v for k, v in lines[0].items() if k != "logged_at"}, {k: v for k, v in on_time[0].items() if k != "logged_at"})
            self.assertEqual(P.sync_log(root, "nba", 1_800_000_900, extra=[rel]), 0)

    def test_readers_tolerate_old_and_new_rows(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "pm_cards", "nba", "v2_tier"))
            old = {"key": "k1", "cut": 100, "tier": "contested"}
            new = {"key": "k2", "cut": 200, "tier": "thin", "mf": {"pin_state": "toward", "line_state": None}}
            dropped = {"key": "k3", "cut": 300, "tier": "thin", "mf": None}
            with open(os.path.join(root, "pm_cards", "nba", "v2_tier", "2026-11.jsonl"), "w") as f:
                f.write("\n".join(json.dumps(r) for r in (old, new, dropped)) + "\nnot json\n")
            rd = FR.TH.FsReader(root)
            logged = FR.logged_rows(rd)
            self.assertEqual(sorted(logged), ["k1", "k2", "k3"])
            ps = [{"key": k, "sport": "nba", "tier": "thin", "res": "win", "flat": 1.0, "cut": c, "group": "ml", "fa": None, "fc": None}
                  for k, c in (("k1", 100), ("k2", 200), ("k3", 300), ("k4", 400))]
            doc = FR.build(ps, 1, "x", logged)
            self.assertEqual((doc["first_logged_cut"], doc["logged_rows"], doc["forward_graded"]), (200, 2, 2))
            nba = doc["sports"]["nba"]
            self.assertEqual(nba["a_toward"]["forward"]["n"], 1)                               # k2 from its log row
            self.assertEqual(nba["unreadable"]["forward"]["n"], 1)                             # k3: a dropped block
            self.assertEqual(nba["unreadable"]["in_sample"]["n"], 1 + 0)                       # k1 only: cut strictly before the first logged lock (200)
            self.assertEqual(nba["a_toward"]["in_sample"]["n"], 0)
            # the tier record reads the same file with rows that have `mf`: its numbers do not move
            tr_with = TR.build(ps, 1, "x", logged)
            stripped = {k: {kk: vv for kk, vv in r.items() if kk != "mf"} for k, r in logged.items()}
            self.assertEqual(json.dumps(TR.build(ps, 1, "x", stripped), sort_keys=True), json.dumps(tr_with, sort_keys=True))


class FlagRecord(unittest.TestCase):
    def play(self, sport, key, a, c, res="win", flat=0.8, cut=1000, group="ml"):
        return {"key": key, "sport": sport, "group": group, "cut": cut, "res": res, "flat": flat, "fa": a, "fc": c, "tier": "contested", "clv": None}

    def test_slice_membership_partitions_every_play(self):
        cases = {("toward", None): ["a_toward"], ("away", "away"): ["a_away", "c_away"], ("quiet", "quiet"): ["none"], (None, "quiet"): ["none"],
                 (None, None): ["unreadable"], ("toward", "away"): ["a_toward", "c_away"], ("quiet", "toward"): ["c_toward"], ("quiet", None): ["none"]}
        for (a, c), want in cases.items():
            self.assertEqual(FR.slices_of(a, c), want, (a, c))

    def test_shape_counts_by_hand(self):
        ps = [self.play("nba", "1", "toward", "quiet", "win", 0.8), self.play("nba", "2", "toward", "toward", "loss", -1.0),
              self.play("nba", "3", "away", "quiet", "win", 0.5), self.play("nba", "4", "quiet", "quiet", "push", 0.0),
              self.play("nba", "5", None, None, "win", 1.0), self.play("cfb", "6", "toward", None, "loss", -1.0),
              self.play("nfl", "7", "quiet", "away", "win", 0.9), self.play("cbb", "8", None, "toward", "win", 1.06)]
        d = FR.build(ps, 123, "abc", {})
        self.assertEqual((d["built"], d["data_ref"], d["flags_rule"], d["slices"]), (123, "abc", "v2f-2", list(FR.SLICES)))
        nba = d["sports"]["nba"]
        self.assertEqual(nba["a_toward"]["all"], {"w": 1, "l": 1, "p": 0, "n": 2, "units": -0.2, "roi": -0.1})
        self.assertEqual((nba["a_away"]["all"]["n"], nba["c_toward"]["all"]["n"], nba["c_away"]["all"]["n"]), (1, 1, 0))
        self.assertEqual(nba["none"]["all"], {"w": 0, "l": 0, "p": 1, "n": 1, "units": 0.0, "roi": 0.0})
        self.assertEqual(nba["unreadable"]["all"]["n"], 1)
        self.assertEqual(d["sports"]["cfb"]["a_toward"]["all"]["units"], -1.0)
        self.assertEqual(d["all"]["a_toward"]["all"]["n"], 2)                                  # NBA + NFL + CBB: CFB is not pooled
        self.assertEqual(d["all"]["c_toward"]["all"]["n"], 2)
        self.assertEqual(d["sports"]["cbb"]["c_toward"]["all"]["units"], 1.06)
        empty = d["sports"]["nfl"]["a_toward"]["all"]
        self.assertEqual((empty["n"], empty["roi"]), (0, None))                                # null, never 0

    def test_every_play_sits_in_exactly_one_of_fired_none_unreadable(self):
        ps = [self.play("nba", str(i), a, c) for i, (a, c) in enumerate([("toward", None), ("away", "quiet"), ("quiet", "quiet"), (None, "quiet"), (None, None), ("quiet", None)])]
        d = FR.build(ps, 1, "x", {})["sports"]["nba"]
        fired = [FR.slices_of(p["fa"], p["fc"])[0] in ("a_toward", "a_away", "c_toward", "c_away") for p in ps]
        self.assertEqual(sum(fired) + d["none"]["all"]["n"] + d["unreadable"]["all"]["n"], len(ps))

    def test_forward_is_zero_today_and_in_sample_is_everything(self):
        ps = [self.play("nba", "1", "toward", None), self.play("nfl", "2", "away", None)]
        d = FR.build(ps, 1, "x", {"1": {"key": "1", "cut": 1000, "tier": "thin"}})              # a log row with no `mf`: not forward for the flags
        self.assertEqual((d["first_logged_cut"], d["logged_rows"], d["forward_graded"]), (None, 0, 0))
        self.assertEqual(d["forward_note"], FR.FORWARD_NOTE)
        for sp in ("nba", "nfl", "cbb", "cfb"):
            for sl in FR.SLICES:
                self.assertEqual(d["sports"][sp][sl]["forward"]["n"], 0)
                self.assertEqual(d["sports"][sp][sl]["in_sample"], d["sports"][sp][sl]["all"])
        self.assertEqual(sorted(d["sports"]["nba"]["a_toward"]), ["all", "forward", "in_sample"])

    def test_forward_uses_the_logged_flags_not_a_rederivation(self):
        ps = [self.play("nba", "1", "quiet", "quiet", cut=500), self.play("nba", "2", "quiet", "quiet", cut=900)]
        logged = {"2": {"key": "2", "cut": 900, "tier": "thin", "mf": {"pin_state": "away", "line_state": "away"}}}
        d = FR.build(ps, 1, "x", logged)["sports"]["nba"]
        self.assertEqual((d["a_away"]["forward"]["n"], d["c_away"]["forward"]["n"], d["none"]["forward"]["n"]), (1, 1, 0))
        self.assertEqual(d["none"]["in_sample"]["n"], 1)                                       # play 1: cut 500 is before the first logged lock (900)
        self.assertEqual(d["none"]["all"]["n"], 1)

    def test_derive_flags_stored_block_wins_and_the_tape_is_read_at_the_cut(self):
        class Q:
            def game(self, *a):
                return [mk("spread", "Pinnacle", ASOF - 7200, -3.5, 0.5), mk("spread", "Pinnacle", ASOF - 600, -3.5, 0.6),
                        mk("spread", "Pinnacle", ASOF + 50, -3.5, 0.2)], "gk"
        c = {"sport": "nba", "ev": "nba-a-b-2027-01-15", "gst": ASOF + 900, "cut": ASOF, "vault": {"key": "k", "teams": {"away": ["A"], "home": ["B"]}},
             "markets": {"spread": {"sides": {"A": {}, "B": {}}, "v2": {"side": "B", "flags": {"a": "away", "c": None}}}}}
        self.assertEqual(FR.derive_flags(c, "spread", "B", Q()), {"a": "away", "c": None, "src": "frozen"})
        got = FR.derive_flags(c, "spread", "A", Q())                                          # A is the away side: the home line moved nowhere, fair rose 10 for home
        self.assertEqual((got["src"], got["a"]), ("derived", "away"))                          # read at the cut: the row after it (0.2) is not read
        self.assertEqual(FR.derive_flags(c, "spread", "B", None)["src"], "frozen")
        c["markets"]["spread"].pop("v2")
        self.assertEqual(FR.derive_flags(c, "spread", "B", None), {"a": None, "c": None, "src": None})
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(FR.derive_flags(c, "spread", "B", object())["src"], "error")

    def test_compute_flags_every_improving_slice_with_n(self):
        ps = [self.play("nba", "1", "toward", None, "win", 0.8), self.play("nba", "2", "toward", None, "loss", -1.0), self.play("nba", "3", "away", None, "loss", -1.0),
              self.play("nfl", "4", "away", None, "win", 0.9)]
        out = FR.compute(ps)
        names = {f["slice"]: f for f in out["flagged"]}
        self.assertNotIn("NBA A toward", names)                                                # -0.2u does not improve
        self.assertEqual(names["NFL A away"]["n"], 1)
        self.assertTrue(names["NFL A away"]["small_sample"])
        self.assertNotIn("Headline (NBA+NFL+CBB) A away", names)                              # 1-1, -0.1u: not improving
        self.assertEqual(out["old"]["nba"]["n"], 3)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            FR.print_report(out)
        text = buf.getvalue()
        for needle in ("OLD (no flags, every play)", "NEW A toward", "FLAGGED FOR CLOSE MONITORING", "NFL A away (flat ROI, n=1)  [small sample]"):
            self.assertIn(needle, text)
        self.assertNotRegex(text.split("FLAGGED")[1], "NBA A toward")

    def test_a_flat_record_is_not_improving_and_the_small_sample_tag_is_at_30(self):
        ps = [self.play("nba", "p1", "toward", None, "push", 0.0)]
        self.assertEqual([f for f in FR.compute(ps)["flagged"] if f["slice"] == "NBA A toward"], [])        # 0.00u is not an improvement
        seven = [self.play("nba", "s%d" % i, "away", None, "win", 0.5) for i in range(7)]
        thirty = [self.play("nfl", "t%d" % i, "away", None, "win", 0.5) for i in range(30)]
        names = {f["slice"]: f for f in FR.compute(seven + thirty)["flagged"]}
        self.assertEqual((names["NBA A away"]["n"], names["NBA A away"]["small_sample"]), (7, True))
        self.assertEqual((names["NFL A away"]["n"], names["NFL A away"]["small_sample"]), (30, False))
        self.assertEqual(FR.SMALL_N, 30)

    def test_the_headline_totals_equal_the_old_record(self):
        ps = [self.play("nba", str(i), a, c, "win" if i % 2 else "loss", 0.9 if i % 2 else -1.0) for i, (a, c) in enumerate([("toward", None), (None, None), ("quiet", "quiet"), ("away", "toward")])]
        out = FR.compute(ps)
        self.assertEqual(out["old"]["headline"]["n"], 4)
        fired = {p["key"] for p in ps if FR.slices_of(p["fa"], p["fc"])[0] not in ("none", "unreadable")}
        parts = sum(out["slices"]["nba"][s]["n"] for s in ("none", "unreadable")) + len(fired)
        self.assertEqual(parts, out["old"]["nba"]["n"])

    def test_the_command_writes_a_small_file_and_reads_the_log(self):
        with tempfile.TemporaryDirectory() as d:
            fx = TP.Fixture(d)
            card = TP.tcard("nba", "g1", CUT_FIX, v2=None, pts=0.5)
            fx.add(card)
            fx.commit()
            os.makedirs(os.path.join(d, "tape", "nba"), exist_ok=True)
            out = os.path.join(d, "o", "flag_record.json")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(FR.main(["--data-dir", d, "--book-tape", os.path.join(d, "tape"), "--out", out, "--now", "5", "--data-ref", "abc"]), 0)
            doc = json.load(open(out))
            self.assertEqual((doc["built"], doc["data_ref"], doc["forward_graded"]), (5, "abc", 0))
            self.assertEqual(doc["sports"]["nba"]["unreadable"]["all"]["n"], 1)                  # no tape for the game: not readable
            self.assertLess(os.path.getsize(out), 25_000)


CUT_FIX = TP.CUT


class SwappedRow(unittest.TestCase):
    """The stored Pinnacle row of cfb:290201 (M-OH at WMU, 2026-11-23): first row ml [-323, 260] and spread home +7.5, ten minutes later [245, -301] and -7.5. The
    first row has the sides swapped; the US books were at about WMU -245 to -305 and -7 to -7.5 the whole time."""
    T0 = 1795392408

    def rows(self, third=True):
        r = [{"t": self.T0 - 43133, "book": b, "ml": ml_, "sp": [h, -110, -110]} for b, ml_, h in
             (("BetRivers", [250, -335], -7.5), ("DraftKings", [240, -298], -7.5), ("FanDuel", [240, -295], -7.5))]
        r += [{"t": self.T0, "book": "Pinnacle", "ml": [-323, 260], "sp": [7.5, -113, -103], "tot": [49.5, -113, -107]},
              {"t": self.T0, "book": "BetMGM", "ml": [230, -275], "sp": [-7, -110, -110]}, {"t": self.T0, "book": "BetRivers", "ml": [230, -305], "sp": [-7, -110, -110]},
              {"t": self.T0, "book": "DraftKings", "ml": [200, -245], "sp": [-7.5, -110, -110]}, {"t": self.T0, "book": "FanDuel", "ml": [230, -285], "sp": [-7.5, -110, -110]},
              {"t": self.T0 + 593, "book": "Pinnacle", "ml": [245, -301], "sp": [-7.5, -101, -115], "tot": [45.5, -110, -110]}]
        if third:
            r.append({"t": self.T0 + 1216, "book": "Pinnacle", "ml": [257, -318], "sp": [-7.5, -101, -115]})
        return r

    ASOF_ = T0 + 5000

    def test_the_swapped_row_is_dropped_and_no_43_point_move_is_published(self):
        rows = self.rows()
        for g in ("ml", "spread"):
            fl, se = F.flags_block(rows, g, "home", self.ASOF_, "cfb")
            self.assertEqual(fl["pin"]["dropped"], 1, g)
            self.assertLess(abs(fl["pin"]["pts"]), 5.0, g)                                   # the dropped row would have read as a move of about 45 points
            self.assertEqual(fl["pin"]["state"], "quiet", g)
            self.assertGreater(fl["pin"]["t_from"], self.T0, g)                              # the swapped row is nowhere in the chart's price series either
            self.assertNotEqual(se["pin_px"][0][0] if se and se["pin_px"] else None, None)
        self.assertGreater(F.flags_block(rows, "ml", "home", self.ASOF_, "cfb")[1]["pin_px"][0][1], -400)   # home price series starts at -301, not +260

    def test_with_nothing_left_the_reason_is_named_not_a_zero(self):
        fl, _ = F.flags_block(self.rows(False), "ml", "home", self.ASOF_, "cfb")
        self.assertIsNone(fl["pin"])
        self.assertEqual(fl["why"]["pin"], "pinnacle_row_inconsistent")
        self.assertIsNone(fl["a"])

    def test_flag_c_reads_the_cleaned_pinnacle_rows(self):
        rows = self.rows()
        fl, _ = F.flags_block(rows, "ml", "home", self.ASOF_, "cfb")
        self.assertNotEqual(fl["why"]["line"], "pinnacle_row_inconsistent")
        for g in ("spread",):
            ln = F.flags_block(rows, g, "home", self.ASOF_, "cfb")[0]["line"]
            if ln:
                self.assertEqual(ln["pin"]["from"], -7.5)                                    # not the swapped +7.5

    def test_a_real_move_across_even_money_is_not_dropped(self):
        # Pinnacle 0.40 then 0.60 while the US books sit at 0.45 and 0.55 (not all on one side): a real move of 20 points
        rows = [ml("Pinnacle", ASOF - 7000, 0.40), ml("Pinnacle", ASOF - 600, 0.60), ml("DraftKings", ASOF - 8000, 0.45), ml("FanDuel", ASOF - 8000, 0.55)]
        pin = flags(rows, "ml")[0]["pin"]
        self.assertEqual((pin["dropped"], pin["pts"]), (0, 20.0))
        # a coin-flip game: a row 0.49 against books at 0.52 is inside the margin, never "the other side"
        rows = [ml("Pinnacle", ASOF - 7000, 0.52), ml("Pinnacle", ASOF - 600, 0.49), ml("DraftKings", ASOF - 8000, 0.52), ml("FanDuel", ASOF - 8000, 0.51)]
        self.assertEqual(flags(rows, "ml")[0]["pin"]["dropped"], 0)
        # a first row on the other side of every book is dropped; one book alone is not enough evidence and there is no neighbour pair
        rows = [ml("Pinnacle", ASOF - 7000, 0.20), ml("Pinnacle", ASOF - 600, 0.75), ml("DraftKings", ASOF - 8000, 0.70)]
        self.assertEqual(flags(rows, "ml")[0]["pin"]["dropped"], 0)
        rows = [ml("Pinnacle", ASOF - 7000, 0.20), ml("Pinnacle", ASOF - 600, 0.75), ml("DraftKings", ASOF - 8000, 0.70), ml("FanDuel", ASOF - 8000, 0.72)]
        self.assertEqual((flags(rows, "ml")[0]["why"]["pin"], flags(rows, "ml")[0]["pin"]), ("pinnacle_row_inconsistent", None))

    def test_without_us_books_only_an_isolated_row_is_dropped(self):
        rows = [ml("Pinnacle", ASOF - 7000, 0.70), ml("Pinnacle", ASOF - 5000, 0.25), ml("Pinnacle", ASOF - 600, 0.72)]
        pin = flags(rows, "ml")[0]["pin"]
        self.assertEqual((pin["dropped"], pin["pts"]), (1, 2.0))
        rows = [ml("Pinnacle", ASOF - 7000, 0.25), ml("Pinnacle", ASOF - 600, 0.75)]       # two rows that disagree and nothing to say which: both kept
        self.assertEqual(flags(rows, "ml")[0]["pin"]["dropped"], 0)

    def test_a_pickem_spread_is_never_judged_by_its_sign(self):
        """Lines inside 1.5 points of pick'em (nba:295485 shape: Pinnacle -1 while US books show +1 or -1.5) are not 'the other side': the sign is only read when
        both lines are at least FLAGS_SWAP_LINE from pick'em."""
        self.assertEqual(F.FLAGS_SWAP_LINE, 1.5)
        rows = [sp("Pinnacle", ASOF - 7000, 2.0, 0.5), sp("Pinnacle", ASOF - 6000, -1.0, 0.5), sp("Pinnacle", ASOF - 600, -1.0, 0.5),
                sp("DraftKings", ASOF - 8000, 1.0), sp("FanDuel", ASOF - 8000, 1.0), sp("BetMGM", ASOF - 8000, 1.0)]
        self.assertEqual(flags(rows, "spread")[0]["pin"]["dropped"], 0)
        rows = [sp("Pinnacle", ASOF - 7000, 1.5, 0.5), sp("Pinnacle", ASOF - 6000, -1.5, 0.5), sp("Pinnacle", ASOF - 600, -1.5, 0.5),
                sp("DraftKings", ASOF - 8000, -1.5), sp("FanDuel", ASOF - 8000, -1.5)]
        self.assertEqual(flags(rows, "spread")[0]["pin"]["dropped"], 1)                       # at the margin (1.5) the sign is judged

    def test_a_spread_line_with_its_sign_flipped_is_dropped_and_totals_are_never_checked(self):
        rows = [sp("Pinnacle", ASOF - 7000, 7.5, 0.5), sp("Pinnacle", ASOF - 6000, -7.5, 0.5), sp("Pinnacle", ASOF - 600, -7.5, 0.5),
                sp("DraftKings", ASOF - 8000, -7.5), sp("FanDuel", ASOF - 8000, -7.0)]
        self.assertEqual(flags(rows, "spread")[0]["pin"]["dropped"], 1)
        rows = [tot("Pinnacle", ASOF - 7000, 49.5, 0.5), tot("Pinnacle", ASOF - 3000, 45.5, 0.5), tot("Pinnacle", ASOF - 600, 45.5, 0.5), tot("DraftKings", ASOF - 8000, 45.5),
                tot("FanDuel", ASOF - 8000, 45.5)]
        self.assertEqual(flags(rows, "total")[0]["pin"]["dropped"], 0)


class FirstQuotes(unittest.TestCase):
    """A first quote inside the window is not a move from nothing (v2f-2): null for a book, never a move of 0."""

    def base(self):
        rows = [mk("spread", "Pinnacle", ASOF - 9000, -3.0), mk("spread", "Pinnacle", ASOF - 900, -5.5)]
        for b in ("DraftKings", "FanDuel"):
            rows += [mk("spread", b, ASOF - 8000, -3.0), mk("spread", b, ASOF - 800, -5.0)]
        return rows

    def test_a_book_whose_only_row_is_a_first_quote_inside_the_window_is_not_read(self):
        ln = flags(self.base() + [mk("spread", "BetMGM", ASOF - 700, -5.0)], "spread")[0]["line"]
        self.assertEqual(sorted(ln["by_book"]), ["DraftKings", "FanDuel"])
        self.assertEqual((ln["books"], ln["same_way"]), (3, 3))                              # not 4: BetMGM has no history
        fl = flags([r for r in self.base() if r["book"] != "FanDuel"] + [mk("spread", "BetMGM", ASOF - 700, -5.0)], "spread")[0]
        self.assertEqual((fl["line"], fl["why"]["line"]), (None, "too_few_books"))

    def test_a_single_row_is_never_a_move_for_any_book_even_one_showing_since_before_the_window(self):
        """Flag A needs 2 rows; Flag C asks the same of every book (item: both flags agree on a lone moneyline or line row)."""
        ws = ASOF - DAY
        ln = flags(self.base() + [mk("spread", "BetMGM", ws - 3000, -3.0)], "spread")[0]["line"]
        self.assertNotIn("BetMGM", ln["by_book"])                                            # a lone old row is not read as a move of 0
        self.assertEqual((ln["books"], ln["same_way"]), (3, 3))
        self.assertIsNone(flags([ml("Pinnacle", ws - 5000, 0.4)], "ml")[0]["pin"])           # Flag A: the same reading for a lone Pinnacle row
        rows = [ml("Pinnacle", ws - 5000, 0.5), ml("Pinnacle", ASOF - 900, 0.6)]
        for b, to in (("DraftKings", 0.62), ("FanDuel", 0.63)):
            rows += [ml(b, ws - 5000, 0.5), ml(b, ASOF - 800, to)]
        rows += [ml("BetMGM", ws - 4000, 0.9)]                                               # a lone row on a moneyline: the same minimum
        fl = flags(rows, "ml", sport="nfl")[0]
        self.assertEqual(sorted(fl["line"]["by_book"]), ["DraftKings", "FanDuel"])
        self.assertEqual(fl["pin"]["state"], "toward")

    def test_pinnacle_with_a_first_quote_only_is_too_few_books_for_flag_c(self):
        rows = [mk("spread", "Pinnacle", ASOF - 900, -5.5)]
        for b in ("DraftKings", "FanDuel"):
            rows += [mk("spread", b, ASOF - 8000, -3.0), mk("spread", b, ASOF - 800, -5.0)]
        self.assertEqual(flags(rows, "spread")[0]["why"]["line"], "too_few_books")

    def test_the_flag_record_keeps_a_play_with_neither_flag_readable_as_unreadable(self):
        class Q:
            def game(self, *a):
                return [mk("spread", "Pinnacle", ASOF - 900, -5.5)], "gk"
        c = {"sport": "nba", "ev": "nba-a-b-2027-01-15", "gst": ASOF + 900, "cut": ASOF, "vault": {"key": "k", "teams": {"away": ["A"], "home": ["B"]}},
             "markets": {"spread": {"sides": {"A": {}, "B": {}}}}}
        got = FR.derive_flags(c, "spread", "B", Q())
        self.assertEqual((got["a"], got["c"]), (None, None))
        self.assertEqual(FR.slices_of(got["a"], got["c"]), ["unreadable"])

    def test_the_error_path_is_unreadable_never_quiet_or_no_flag_fired(self):
        c = {"sport": "nba", "ev": "x", "gst": ASOF + 900, "cut": ASOF, "markets": {"spread": {"sides": {"A": {}, "B": {}}}}}
        with contextlib.redirect_stderr(io.StringIO()):
            got = FR.derive_flags(c, "spread", "B", object())
        self.assertEqual(got, {"a": None, "c": None, "src": "error"})
        self.assertEqual(FR.slices_of(got["a"], got["c"]), ["unreadable"])
        play = {"key": "e", "sport": "nba", "group": "spread", "cut": 1, "res": "win", "flat": 0.9, "fa": got["a"], "fc": got["c"], "tier": "thin", "clv": None}
        d = FR.build([play], 1, "x", {})["sports"]["nba"]
        self.assertEqual((d["unreadable"]["all"]["n"], d["none"]["all"]["n"]), (1, 0))


class RecordPieces(unittest.TestCase):
    def test_the_logged_mf_has_these_literal_values(self):
        c = TP.Additive().card(vault=VAULT, quotes=TP.Malformed.Quotes(AdditiveOnly.ROWS))
        mf = P.log_row("nba/frozen/d/x.json", c, "spread", 1)["mf"]
        want = {"rule": "v2f-2", "asof": ASOF, "span_min": 120, "src_age_min": {"pinnacle": None, "us": None},
                "pin_state": "quiet", "pin_pts": 0.0, "pin_from": 100.0, "pin_to": 100.0, "pin_line": 6.0, "lim_from": 3000, "lim_to": 9000,
                "line_kind": "line", "line_state": "away", "line_pin_from": 3.5, "line_pin_to": 6.0, "line_books": 4, "line_same_way": 4,
                "line_extreme_book": "Pinnacle", "line_extreme": 6.0, "why": {"pin": None, "limit": None, "line": None}}
        self.assertEqual(mf, want)

    def test_mf_carries_flag_c_in_its_own_fields_not_flag_a(self):
        fl = {"rule": "v2f-2", "asof": 5, "span_min": 9, "src_age_min": None, "why": {},
              "pin": {"state": "toward", "pts": 2.0, "from": -105, "to": -129, "line": None},
              "line": {"kind": "price", "state": "away", "pin": {"from": 1, "to": 2}, "books": 3, "same_way": 2, "extreme": {"book": "FanDuel", "value": -110}},
              "limit": {"from": 10, "to": 20}}
        mf = F.mf_of(fl)
        self.assertEqual((mf["pin_state"], mf["line_state"], mf["line_extreme_book"], mf["line_same_way"], mf["lim_to"]), ("toward", "away", "FanDuel", 2, 20))

    def test_the_headline_excludes_cfb_and_pools_the_three_sports_that_show_a_size(self):
        def play(sp, k, flat):
            return {"key": k, "sport": sp, "group": "ml", "cut": 1, "res": "win" if flat > 0 else "loss", "flat": flat, "fa": "toward", "fc": None, "tier": "thin", "clv": None}
        ps = [play("nba", "1", 1.0), play("nfl", "2", 1.0), play("cbb", "3", -1.0), play("cfb", "4", 5.0)]
        out = FR.compute(ps)
        self.assertEqual((out["old"]["headline"]["n"], out["old"]["headline"]["units"]), (3, 1.0))
        self.assertEqual((out["slices"]["headline"]["a_toward"]["n"], out["slices"]["headline"]["a_toward"]["units"]), (3, 1.0))
        self.assertEqual(out["slices"]["cfb"]["a_toward"]["units"], 5.0)

    def test_tier_record_and_history_still_build_when_the_flag_module_will_not_import(self):
        import sharps_v2
        had = hasattr(sharps_v2, "flag_record")
        saved = getattr(sharps_v2, "flag_record", None)
        if had:
            delattr(sharps_v2, "flag_record")
        try:
            with tempfile.TemporaryDirectory() as d, mock.patch.dict(sys.modules, {"sharps_v2.flag_record": None}):
                fx = TP.Fixture(d)
                fx.add(TP.tcard("nba", "g1", TP.CUT, pts=0.5))
                fx.commit()
                os.makedirs(os.path.join(d, "tape", "nba"), exist_ok=True)
                out = os.path.join(d, "o", "tier_record.json")
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(TR.main(["--data-dir", d, "--book-tape", os.path.join(d, "tape"), "--out", out, "--now", "5", "--data-ref", "abc"]), 0)
                self.assertEqual(json.load(open(out))["data_ref"], "abc")
                buf, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                    self.assertEqual(TP.TH.main(["--repo", d, "--ref", "main", "--book-tape", os.path.join(d, "tape")]), 0)
                self.assertIn("PER-TIER RECORD", buf.getvalue())
                self.assertNotIn("MARKET-MOVE FLAGS", buf.getvalue())
                self.assertIn("flag record skipped", err.getvalue())
        finally:
            if had:
                sharps_v2.flag_record = saved


class Wording(unittest.TestCase):
    def test_no_banned_word_in_any_string_the_feature_publishes(self):
        rows = [dict(sp("Pinnacle", ASOF - 7200, -3.5, 0.5), lim=[1, 3000, 1]), dict(sp("Pinnacle", ASOF - 600, -4.5, 0.6), lim=[1, 9000, 1])]
        rows += [sp(b, ASOF - 7000, -3.5) for b in US[:3]] + [sp(b, ASOF - 500, -5.5) for b in US[:3]]
        blobs = [flags(rows, "spread"), flags([], "total"), flags(rows, "spread", norm=None), (F.flags_fields(),), (F.mf_of(flags(rows, "spread")[0]),)]
        strings = []

        def walk(x):
            if isinstance(x, str):
                strings.append(x)
            elif isinstance(x, dict):
                for k, v in x.items():
                    walk(k)
                    walk(v)
            elif isinstance(x, (list, tuple)):
                for v in x:
                    walk(v)
        walk(blobs)
        self.assertTrue(strings)
        for s in strings:
            self.assertIsNone(BANNED.search(s.replace("_", " ")), s)


class NoEmDash(unittest.TestCase):
    def test_no_u2014_in_the_new_or_changed_files(self):
        files = ["scripts/sharps_v2/flags_v2.py", "scripts/sharps_v2/flag_record.py", "scripts/sharps_v2/plays_v2.py", "scripts/sharps_v2/check_size.py",
                 "scripts/sharps_v2/tier_history.py", "scripts/build_side_cards.py", "tests/test_sharps_v2_flags.py", "docs/sharps-v2-flags-spec.md",
                 "docs/sharp-tier-v2-prereg.md", "docs/side-cards.md", "docs/side-card-record.md", ".github/workflows/pm-cards.yml"]
        for f in files:
            p = os.path.join(ROOT, f)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as fh:
                    self.assertNotIn(chr(0x2014), fh.read(), f)


if __name__ == "__main__":
    unittest.main()
