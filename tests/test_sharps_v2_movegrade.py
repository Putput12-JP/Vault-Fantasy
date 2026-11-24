"""Unit tests for the Sharps V2 Move grade (rule mg-1, docs/sharp-movegrade-prereg.md): scripts/sharps_v2/move_grade.py, its use in plays_v2.market_v2 and
log_row, the size gate, move_grade_record.py, the history printout and the measurement helpers of move_grade_history.py. Synthetic inputs only; no network,
no stored data. Run from the repo root:
    python3 -m unittest tests.test_sharps_v2_movegrade
"""
import contextlib, copy, hashlib, inspect, io, json, os, re, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)
import build_side_cards as C  # noqa: E402
from sharps_v2 import flags_v2 as F  # noqa: E402
from sharps_v2 import flag_record as FR  # noqa: E402
from sharps_v2 import move_grade as MG  # noqa: E402
from sharps_v2 import move_grade_record as MGR  # noqa: E402
from sharps_v2 import move_grade_history as MGH  # noqa: E402
from sharps_v2 import plays_v2 as P  # noqa: E402
from sharps_v2 import tier_history as TH  # noqa: E402
from sharps_v2 import tier_record as TR  # noqa: E402
from sharps_v2 import check_size as CS  # noqa: E402
import test_sharps_v2_flags as TF  # noqa: E402
import test_sharps_v2_plays as TP  # noqa: E402

ASOF, US, VAULT, sp, mk = TF.ASOF, TF.US, TF.VAULT, TF.sp, TF.mk
SPORTS = ("nba", "nfl", "cbb", "cfb")
GROUPS = ("ml", "spread", "total")
NORM = {"ml": "home", "spread": "home", "total": "over"}
BANNED_FLAGS = TF.BANNED
FLAGS_V2_SHA256 = "637bc7c140925f5a94ec7013c2d84f316b07d371e3ce3be7ebddb31fa988dfa6"      # the v2f-2 file as registered
BANNED_UI = re.compile(r"\b(lean|leans|leaned|strong|edge|follow|lock|go|confirm|agree|agrees)\b", re.I)

# The cutoffs, copied here as literals (spec section 2.3): changing one in the code must break a test.
EXPECT = {
    "m_a": {"nba": {"ml": 2.0, "spread": 0.5, "total": 1.0}, "nfl": {"ml": 0.5, "spread": 1.0, "total": 0.5}, "cbb": {"ml": 1.0, "spread": 1.0, "total": 0.5}, "cfb": {"ml": 1.0, "spread": 0.5, "total": 0.5}},
    "x_a": {"nba": {"ml": 9.0, "spread": 2.0, "total": 2.5}, "nfl": {"ml": 3.0, "spread": 2.5, "total": 2.5}, "cbb": {"ml": 4.5, "spread": 2.5, "total": 2.5}, "cfb": {"ml": 4.5, "spread": 2.5, "total": 2.0}},
    "m_c": {"nba": {"spread": 1.0, "total": 1.5}, "nfl": {"spread": 0.5, "total": 0.5}, "cbb": {"spread": 0.5, "total": 1.0}, "cfb": {"spread": 0.5, "total": 0.5}},
    "x_c": {"nba": {"spread": 3.5, "total": 4.0}, "nfl": {"spread": 1.5, "total": 1.5}, "cbb": {"spread": 2.0, "total": 4.0}, "cfb": {"spread": 2.5, "total": 2.0}},
}


def dir_of(g, norm):
    return F._dir_sign(g, norm)


def flg(a=None, pts=None, c=None, kind="line", move=None, norm=None, g="spread", same=2, books=3, why=None, line_pin=True):
    """A stored v2.flags block, the fields mg-1 reads. a / c: the v2f-2 state or None (flag block None); pts: Flag A's points; move: Pinnacle's main-line move toward
    the side in points (becomes line.pin from/to for the side's direction)."""
    out = {"rule": "v2f-2", "pin": None, "line": None, "why": why or {"pin": "no_tape_rows_for_game", "limit": None, "line": "too_few_books"}}
    if a is not None:
        out["pin"] = {"state": a, "pts": pts, "t_a": 1.5, "from": -110, "to": -120, "line": -3.5}
    if c is not None:
        out["line"] = {"kind": kind, "state": c, "t_c": 2.0, "books": books, "same_way": same if c != "quiet" else None, "by_book": {}, "extreme": None,
                       "pin": ({"from": 10.0, "to": round(10.0 + (move or 0.0) * dir_of(g, norm or NORM[g]), 2)} if line_pin and move is not None else None)}
        if out["line"]["pin"] is None:
            out["line"].pop("pin")
    return out


def grade(flags, g="spread", sport="nba", norm=None):
    return MG.move_grade(flags, g, norm or NORM[g], sport)


def letter(flags, g="spread", sport="nba", norm=None):
    r = grade(flags, g, sport, norm)
    return "against" if r["against"] else r["letter"]


class Constants(unittest.TestCase):
    def test_the_cutoff_tables_are_the_frozen_values(self):
        self.assertEqual(MG.MG_M_A, EXPECT["m_a"])
        self.assertEqual(MG.MG_X_A, EXPECT["x_a"])
        self.assertEqual(MG.MG_M_C, EXPECT["m_c"])
        self.assertEqual(MG.MG_X_C, EXPECT["x_c"])
        self.assertEqual(MG.MG_RULE, "mg-1")

    def test_the_a_mark_is_above_the_b_mark_and_the_c_mark_below_it(self):
        for sp_ in SPORTS:
            for g in GROUPS:
                self.assertGreaterEqual(MG.MG_X_A[sp_][g], F.FLAGS_T_A[sp_][g] + 0.5)
                self.assertLess(MG.MG_M_A[sp_][g], F.FLAGS_T_A[sp_][g])
                if g != "ml":
                    self.assertGreaterEqual(MG.MG_X_C[sp_][g], F.FLAGS_T_C[sp_][g] + 0.5)
                    self.assertLess(MG.MG_M_C[sp_][g], F.FLAGS_T_C[sp_][g] + 1e-9)

    def test_cutoffs_per_sport_and_market(self):
        self.assertEqual(MG.cutoffs("nba", "spread"), {"m_a": 0.5, "t_a": 1.5, "x_a": 2.0, "m_c": 1.0, "t_c": 2.0, "x_c": 3.5})
        self.assertEqual(MG.cutoffs("nba", "ml"), {"m_a": 2.0, "t_a": 4.0, "x_a": 9.0, "m_c": None, "t_c": None, "x_c": None})
        self.assertIsNone(MG.cutoffs("xfl", "spread"))
        self.assertIsNone(MG.cutoffs("nba", "prop"))

    def test_flags_v2_is_frozen(self):
        """flags_v2.py is the registered v2f-2 rule: this module reads it and never edits it. The hash changes only with a new rule id."""
        with open(os.path.join(ROOT, "scripts", "sharps_v2", "flags_v2.py"), "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), FLAGS_V2_SHA256)

    def test_the_module_imports_only_the_flag_module(self):
        imports = [l.strip() for l in inspect.getsource(MG).splitlines() if l.startswith(("import ", "from "))]
        self.assertEqual(imports, ["import os, sys", "from sharps_v2 import flags_v2 as F  # noqa: E402"])


class NullCases(unittest.TestCase):
    def test_side_unmapped(self):
        r = MG.move_grade(flg("toward", 3.0, "toward", move=3.0), "spread", None, "nba")
        self.assertEqual((r["letter"], r["against"], r["why"]), (None, None, "side_unmapped"))
        self.assertEqual(MG.move_grade(flg("toward", 3.0), "ml", "sideways", "nba")["why"], "side_unmapped")

    def test_flags_null_or_garbage_is_no_flags(self):
        for fl in (None, "x", 7, [], True):
            r = grade(fl)
            self.assertEqual((r["letter"], r["against"], r["why"]), (None, None, "no_flags"), fl)

    def test_both_flags_null_carries_why(self):
        why = {"pin": "no_pinnacle_history", "limit": None, "line": "too_few_books"}
        r = grade({"rule": "v2f-2", "pin": None, "line": None, "why": why})
        self.assertEqual((r["letter"], r["against"], r["why"], r["flags_why"]), (None, None, "flags_unreadable", why))
        self.assertEqual(grade({"pin": None, "line": None})["why"], "flags_unreadable")
        self.assertEqual(grade({"pin": {"state": "weird", "pts": 1.0}, "line": {"state": 3}})["why"], "flags_unreadable")   # an unknown state is not a state

    def test_one_flag_null_and_the_other_quiet_toward_or_away(self):
        self.assertEqual(letter(flg("quiet", 0.0)), "D")
        self.assertEqual(letter(flg("toward", 1.5)), "B")
        self.assertEqual(letter(flg("away", -1.5)), "against")
        self.assertEqual(letter(flg(None, None, "quiet", move=0.0)), "D")
        self.assertEqual(letter(flg(None, None, "toward", move=2.0)), "B")
        self.assertEqual(letter(flg(None, None, "away", move=-2.0)), "against")
        for r in (grade(flg("quiet", 0.0)), grade(flg(None, None, "quiet", move=0.0))):
            self.assertIsNone(r["why"])

    def test_a_moneyline_with_flag_c_null(self):
        self.assertEqual(letter(flg("quiet", 0.1), "ml"), "D")
        self.assertEqual(grade(flg("toward", 4.0), "ml")["c_pts"], None)

    def test_a_moneyline_never_reads_a_line_move_even_from_an_inconsistent_block(self):
        r = grade(flg("quiet", 0.0, "toward", kind="line", move=3.5, g="ml"), "ml")
        self.assertEqual((r["c_pts"], r["letter"]), (None, "B"))
        self.assertIsNone(MG.c_pts_of(flg(None, None, "toward", kind="line", move=3.5, g="ml")["line"], "ml", "home"))

    def test_a_spread_with_the_line_pin_missing(self):
        r = grade(flg(None, None, "toward", move=None))
        self.assertEqual((r["letter"], r["basis"], r["c_pts"]), ("B", "fired", None))             # fired, and no number to reach A: never a guessed A
        r2 = grade(flg("quiet", 0.0, "quiet", move=None))
        self.assertEqual((r2["letter"], r2["basis"], r2["c_pts"]), ("D", "flat", None))
        self.assertIsNone(grade(flg("quiet", 0.0, "quiet", g="ml", kind="price"), "ml")["c_pts"])

    def test_pts_null_with_a_state_set_is_no_grade_never_a_guessed_d(self):
        for st in ("toward", "away", "quiet"):
            for bad in (None, "2.0", True, float("nan")):
                r = grade(flg(st, bad))
                self.assertEqual((r["letter"], r["against"], r["why"]), (None, None, "flags_unreadable"), (st, bad))
        r = grade(flg("quiet", None, "toward", move=3.0))
        self.assertEqual((r["letter"], r["why"]), (None, "flags_unreadable"))

    def test_no_cutoff(self):
        for sp_, g in (("xfl", "spread"), ("nba", "prop")):
            r = MG.move_grade(flg("toward", 3.0), g, "home", sp_)
            self.assertEqual((r["letter"], r["against"], r["why"]), (None, None, "no_cutoff"))

    def test_a_null_grade_never_carries_a_letter_or_a_marker(self):
        for r in (grade(None), grade({"pin": None, "line": None}), MG.move_grade(flg("quiet", 0.0), "spread", None, "nba")):
            self.assertEqual(MG.bucket_of(r), "unreadable")
            self.assertEqual({k: r[k] for k in ("letter", "against", "basis", "against_by", "a_pts", "c_pts", "cut")}, {k: None for k in ("letter", "against", "basis", "against_by", "a_pts", "c_pts", "cut")})


class Boundaries(unittest.TestCase):
    """Every sport and market, exactly at a mark and the smallest step under it. A value equal to a mark takes the higher letter."""

    def tape_value(self, g, norm, move):
        return flg(None, None, "quiet", move=move, norm=norm, g=g)

    def test_the_a_flag_marks(self):
        for sp_ in SPORTS:
            for g in GROUPS:
                m, t, x = MG.MG_M_A[sp_][g], F.FLAGS_T_A[sp_][g], MG.MG_X_A[sp_][g]
                with self.subTest(sport=sp_, market=g):
                    self.assertEqual(letter(flg("quiet", m), g, sp_), "C")                         # exactly at the C mark
                    self.assertEqual(letter(flg("quiet", m - 0.01), g, sp_), "D")                  # 0.01 under
                    self.assertEqual(letter(flg("toward", t), g, sp_), "B")                        # exactly at the B mark (the flag fires)
                    self.assertEqual(letter(flg("toward", x), g, sp_), "A")                        # exactly at the A mark
                    self.assertEqual(letter(flg("toward", x - 0.01), g, sp_), "B")
                    self.assertEqual(grade(flg("toward", x), g, sp_)["basis"], "a_mark")
                    self.assertEqual(grade(flg("toward", x - 0.01), g, sp_)["basis"], "fired")

    def test_the_a_flag_negative_mirror_is_the_drift_away_branch(self):
        for sp_ in SPORTS:
            for g in GROUPS:
                m = MG.MG_M_A[sp_][g]
                with self.subTest(sport=sp_, market=g):
                    self.assertEqual(letter(flg("quiet", -m), g, sp_), "D")                        # drifted away by a day's move: D, not the marker (no flag fired)
                    self.assertEqual(letter(flg("quiet", -(m - 0.01)), g, sp_), "D")
                    self.assertFalse(grade(flg("quiet", -m), g, sp_)["against"])
                    if g != "ml":
                        mc = MG.MG_M_C[sp_][g]                                                     # drift toward on one input, away on the other: D
                        self.assertEqual(letter(flg("quiet", -m, "quiet", move=mc, g=g), g, sp_), "D")
                        self.assertEqual(letter(flg("quiet", m, "quiet", move=-mc, g=g), g, sp_), "D")

    def test_the_c_flag_marks_on_spreads_and_totals(self):
        for sp_ in SPORTS:
            for g in ("spread", "total"):
                m, t, x = MG.MG_M_C[sp_][g], F.FLAGS_T_C[sp_][g], MG.MG_X_C[sp_][g]
                for norm in (("home", "away") if g == "spread" else ("over", "under")):
                    with self.subTest(sport=sp_, market=g, norm=norm):
                        k = dict(g=g, norm=norm)
                        self.assertEqual(letter(flg("quiet", 0.0, "quiet", move=m, **k), g, sp_, norm), "C")
                        self.assertEqual(letter(flg("quiet", 0.0, "quiet", move=m - 0.5, **k), g, sp_, norm), "D")        # one half point under
                        self.assertEqual(letter(flg("quiet", 0.0, "toward", move=t, **k), g, sp_, norm), "B")
                        self.assertEqual(letter(flg("quiet", 0.0, "toward", move=x, **k), g, sp_, norm), "A")
                        self.assertEqual(letter(flg("quiet", 0.0, "toward", move=x - 0.5, **k), g, sp_, norm), "B")
                        self.assertEqual(grade(flg("quiet", 0.0, "toward", move=x, **k), g, sp_, norm)["basis"], "c_mark")
                        self.assertEqual(letter(flg("quiet", 0.0, "quiet", move=-m, **k), g, sp_, norm), "D")             # the mirror

    def test_a_moneyline_reaches_a_only_through_flag_a(self):
        for sp_ in SPORTS:
            x = MG.MG_X_A[sp_]["ml"]
            fl = flg("quiet", 0.0, "toward", kind="price", g="ml", same=3, books=4)
            self.assertEqual(letter(fl, "ml", sp_), "B")                                           # Flag C toward on a moneyline gives at most B
            self.assertEqual(letter(flg("toward", x, "toward", kind="price", g="ml"), "ml", sp_), "A")
            self.assertEqual(letter(flg("toward", x - 0.01, "toward", kind="price", g="ml"), "ml", sp_), "B")

    def test_the_stored_two_decimal_value_decides(self):
        self.assertEqual(letter(flg("quiet", 0.499999), "spread", "nba"), "C")                     # 0.499999 stores as 0.5: the letter agrees with the stored number
        self.assertEqual(MG.move_grade(flg("toward", 2.0), "spread", "home", "nba")["a_pts"], 2.0)


class BranchTable(unittest.TestCase):
    def test_a_via_a_mark_and_via_c_mark(self):
        self.assertEqual(grade(flg("toward", 2.5))["basis"], "a_mark")
        self.assertEqual(grade(flg("quiet", 0.0, "toward", move=3.5))["basis"], "c_mark")
        both = grade(flg("toward", 2.5, "toward", move=3.5))
        self.assertEqual((both["letter"], both["basis"]), ("A", "a_mark"))                         # the price mark is read first

    def test_b_via_a_only_via_c_only_via_both_and_on_a_moneyline(self):
        self.assertEqual(letter(flg("toward", 1.5)), "B")
        self.assertEqual(letter(flg("quiet", 0.0, "toward", move=2.0)), "B")
        self.assertEqual(letter(flg("toward", 1.5, "toward", move=2.0)), "B")
        self.assertEqual(letter(flg("quiet", 0.0, "toward", kind="price", g="ml"), "ml"), "B")

    def test_c_via_price_line_and_both(self):
        self.assertEqual(grade(flg("quiet", 0.6))["basis"], "drift")
        self.assertEqual(letter(flg("quiet", 0.6)), "C")
        self.assertEqual(letter(flg("quiet", 0.0, "quiet", move=1.0)), "C")
        self.assertEqual(letter(flg("quiet", 0.6, "quiet", move=1.0)), "C")

    def test_d_flat_and_tiny(self):
        self.assertEqual(grade(flg("quiet", 0.1, "quiet", move=0.0))["basis"], "flat")
        self.assertEqual(letter(flg("quiet", 0.1, "quiet", move=0.0)), "D")
        self.assertEqual(letter(flg("quiet", -0.6)), "D")                                          # drift away only

    def test_against_by_a_by_c_by_both_and_mixed(self):
        r = grade(flg("away", -2.0))
        self.assertEqual((r["letter"], r["against"], r["basis"], r["against_by"]), (None, True, "against", ["a"]))
        self.assertEqual(grade(flg("quiet", 0.0, "away", move=-2.0))["against_by"], ["c"])
        self.assertEqual(grade(flg("away", -2.0, "away", move=-2.0))["against_by"], ["a", "c"])
        mixed = grade(flg("toward", 3.0, "away", move=-2.0))                                       # against wins over toward (G1)
        self.assertEqual((mixed["letter"], mixed["against"], mixed["against_by"]), (None, True, ["c"]))
        mixed2 = grade(flg("away", -3.0, "toward", move=3.0))
        self.assertEqual((mixed2["letter"], mixed2["against"], mixed2["against_by"]), (None, True, ["a"]))

    def test_a_grade_carries_its_inputs_and_marks(self):
        r = grade(flg("toward", 2.31, "toward", move=2.5, same=4, books=6))
        self.assertEqual((r["rule"], r["a"], r["c"], r["a_pts"], r["c_pts"], r["c_kind"], r["c_same_way"], r["c_books"]), ("mg-1", "toward", "toward", 2.31, 2.5, "line", 4, 6))
        self.assertEqual(r["cut"], {"m_a": 0.5, "t_a": 1.5, "x_a": 2.0, "m_c": 1.0, "t_c": 2.0, "x_c": 3.5})
        self.assertEqual(sorted(r), sorted(["rule", "letter", "against", "basis", "against_by", "a", "c", "a_pts", "c_pts", "c_kind", "c_same_way", "c_books", "cut", "why", "flags_why"]))
        self.assertLess(len(json.dumps(r, separators=(",", ":"))), 330)

    def test_the_limit_is_never_an_input(self):
        base = flg("quiet", 0.0, "quiet", move=0.0)
        with_limit = copy.deepcopy(base)
        with_limit["limit"] = {"from": 1000, "to": 99999, "rows": 9}
        self.assertEqual(grade(base), grade(with_limit))
        self.assertNotIn("limit", inspect.getsource(MG.move_grade))
        self.assertNotIn("limit", inspect.getsource(MG.c_pts_of))


class Direction(unittest.TestCase):
    """The sign of the move toward the side, read through the real flag builder: a favourite -3 to -4, an underdog +22 to +19."""

    def spread_rows(self, base, to, books=("DraftKings", "FanDuel"), book_to=None):
        rows = [sp("Pinnacle", ASOF - 7200, base), sp("Pinnacle", ASOF - 900, to)]
        for b in books:
            rows += [sp(b, ASOF - 7000, base), sp(b, ASOF - 800, book_to if book_to is not None else to)]
        return rows

    def test_a_favourite_moving_from_minus_3_to_minus_4_reads_toward_the_home_side(self):
        rows = self.spread_rows(-3.0, -5.0)                                                       # 2.0 points: NBA's flag threshold
        fl, _ = TF.flags(rows, "spread", "home", "nba")
        self.assertEqual(fl["line"]["state"], "toward")
        r = MG.move_grade(fl, "spread", "home", "nba")
        self.assertEqual((r["letter"], r["c_pts"]), ("B", 2.0))
        away = MG.move_grade(TF.flags(rows, "spread", "away", "nba")[0], "spread", "away", "nba")
        self.assertEqual((away["letter"], away["against"], away["against_by"]), (None, True, ["c"]))

    def test_an_underdog_plus_22_to_plus_19_reads_toward_the_away_side(self):
        rows = self.spread_rows(-22.0, -19.0, books=("DraftKings", "FanDuel", "BetMGM"))
        fl, _ = TF.flags(rows, "spread", "away", "cbb")
        r = MG.move_grade(fl, "spread", "away", "cbb")
        self.assertEqual((r["letter"], r["basis"], r["c_pts"]), ("A", "c_mark", 3.0))             # 3.0 is past CBB's A mark of 2.0
        home = MG.move_grade(TF.flags(rows, "spread", "home", "cbb")[0], "spread", "home", "cbb")
        self.assertTrue(home["against"])

    def test_totals_over_and_under(self):
        rows = [mk("total", "Pinnacle", ASOF - 7200, 220.5), mk("total", "Pinnacle", ASOF - 900, 224.0)]
        for b in ("DraftKings", "FanDuel"):
            rows += [mk("total", b, ASOF - 7000, 220.5), mk("total", b, ASOF - 800, 224.0)]
        over = MG.move_grade(TF.flags(rows, "total", "over", "nba")[0], "total", "over", "nba")
        under = MG.move_grade(TF.flags(rows, "total", "under", "nba")[0], "total", "under", "nba")
        self.assertEqual((over["letter"], over["c_pts"]), ("B", 3.5))                             # 3.5 is the NBA total's A mark? no: 4.0 is, so B
        self.assertEqual((under["letter"], under["against"], under["c_pts"]), (None, True, -3.5))

    def test_a_moneyline_reads_through_flag_a_only(self):
        rows = [TF.ml("Pinnacle", ASOF - 7200, 0.5), TF.ml("Pinnacle", ASOF - 900, 0.6)]
        fl, _ = TF.flags(rows, "ml", "home", "cfb")
        r = MG.move_grade(fl, "ml", "home", "cfb")
        self.assertEqual((r["letter"], r["a"], r["c"], r["c_pts"]), ("A", "toward", None, None))      # 10 points is past CFB's A mark of 4.5; no books, so no Flag C


class PointInTime(unittest.TestCase):
    ROWS = TF.AdditiveOnly.ROWS

    def grade_at(self, rows, asof=ASOF):
        fl, _ = F.flags_block(rows, "spread", "home", asof, "nba", None)
        return MG.move_grade(fl, "spread", "home", "nba")

    def test_a_row_after_the_cut_never_changes_a_letter(self):
        before = self.grade_at(self.ROWS)
        after = [sp("Pinnacle", ASOF + 60, -9.0, 0.9), sp("DraftKings", ASOF + 80, -9.0), sp("FanDuel", ASOF + 90, -9.0), sp("BetMGM", ASOF + 99, -9.0)]
        self.assertEqual(self.grade_at(self.ROWS + after), before)
        self.assertEqual(self.grade_at([r for r in self.ROWS + after if r["t"] <= ASOF]), before)

    def test_the_grade_is_a_pure_function_of_the_stored_block_and_the_side(self):
        fl, _ = F.flags_block(self.ROWS, "spread", "home", ASOF, "nba", None)
        a = MG.move_grade(copy.deepcopy(fl), "spread", "home", "nba")
        self.assertEqual(a, MG.move_grade(copy.deepcopy(fl), "spread", "home", "nba"))
        self.assertEqual(fl, F.flags_block(self.ROWS, "spread", "home", ASOF, "nba", None)[0])       # the input was not edited
        for fn in (MG.move_grade, MG.c_pts_of, MG.cutoffs):                                        # no tape, no time, no price, no result, no limit anywhere in the rule
            src = re.sub(r"#.*", "", re.sub(r'"""[\s\S]*?"""', "", inspect.getsource(fn)))
            for word in ("asof", "gst", "tape", "rows", "result", "close", "limit", "px", "units", "import "):
                self.assertNotIn(word, src, (fn.__name__, word))

    def test_the_cutoff_code_of_the_history_reads_no_result(self):
        for fn in (MGH.population, MGH.distribution, MGH.marks):
            src = re.sub(r'"""[\s\S]*?"""', "", inspect.getsource(fn))
            for word in ("res\"", "flat", "units", "price", "clv", "graded", "sf\""):
                self.assertNotIn(word, src, (fn.__name__, word))

    def test_population_is_started_games_only_and_marks_round_as_specified(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "nba"))
            rows = []
            for gk, start in (("g1", 1000), ("g2", 5000)):                                          # g2 starts after the newest row: not started
                rows.append({"t": 100, "gk": gk, "start": start, "book": "Pinnacle", "ml": [110, -130]})
            rows.append({"t": 2000, "gk": "g1", "start": 1000, "book": "Pinnacle", "ml": [120, -140]})
            rows.append({"t": 2000, "gk": "g1", "start": 1000, "book": "Consensus", "ml": [120, -140]})
            with open(os.path.join(d, "nba", "2026-11.jsonl"), "w") as f:
                f.write("".join(json.dumps(r) + "\n" for r in rows))
            pop = MGH.population(d)
            self.assertEqual([k for k, _, _ in pop["nba"]], ["g1"])
            self.assertEqual(len(pop["nba"][0][2]), 2)                                              # the Consensus row is not one of the six books
        self.assertEqual(MGH._half(0.74, "near"), 0.5)
        self.assertEqual(MGH._half(0.77, "near"), 1.0)
        self.assertEqual(MGH._half(2.75, "near"), 3.0)
        self.assertEqual(MGH._half(1.01, "up"), 1.5)
        self.assertEqual(MGH._half(1.0, "up"), 1.0)
        dist = {g: {"games": 10, "a": [0.1] * 10 + [0.2], "line": [0.0] * 11} for g in GROUPS}
        m = MGH.marks(dist, "nfl")
        self.assertEqual((m["m_a"]["spread"], m["x_a"]["spread"], m["m_c"]["spread"], m["x_c"]["spread"]), (0.5, 2.0, 0.5, 1.5))   # floors: 0.5 and flag threshold + 0.5

    def test_percentile_is_linear_interpolation(self):
        self.assertEqual(MGH.pct([0, 10], 0.5), 5.0)
        self.assertEqual(MGH.pct([1, 2, 3, 4, 5], 0.95), 4.8)
        self.assertIsNone(MGH.pct([], 0.5))

    def test_the_slope_and_the_bootstrap(self):
        pairs = [(0, 0.0), (1, 1.0), (2, 2.0), (3, 3.0)]
        self.assertAlmostEqual(MGH.slope(pairs), 1.0)
        self.assertIsNone(MGH.slope([(1, 1.0), (1, 2.0)]))
        import random
        lo, hi = MGH.bootstrap_slope(pairs, random.Random(MGH.BOOTSTRAP_SEED))
        self.assertAlmostEqual(lo, 1.0)
        self.assertAlmostEqual(hi, 1.0)


class FrozenIntegrity(unittest.TestCase):
    """Nothing that sizes, tiers, gates or locks a play reads the grade, and it changes none of their output."""

    def test_no_module_that_decides_anything_mentions_the_grade(self):
        for rel in ("scripts/sf_rungs.py", "scripts/sf_tiers.py", "scripts/sf_publish.py", "scripts/sf_signals.py", "scripts/sf_solo.py", "scripts/sharps_v2/flags_v2.py",
                    "scripts/sharps_v2/tier_record.py", "scripts/sharps_v2/check_size.py", "sharp-money/v2/gates.js", "sharp-money/side-cards.js"):
            p = os.path.join(ROOT, rel)
            if os.path.exists(p):
                src = open(p, encoding="utf-8").read()
                self.assertNotRegex(src, r"move_grade|\bmg-1\b|\bmg\b\s*[:=\[]|MG\.", rel)
        for fn in (P.shown_units, P.shadow_units, P.tier_of, P.facts, P.shown_units_at, P.v2_slate, P.conflict, P.vs_fair, P.exec_block):
            self.assertNotRegex(inspect.getsource(fn), r"move_grade|\bmg\b", fn.__name__)
        build = open(os.path.join(ROOT, "scripts", "build_side_cards.py"), encoding="utf-8").read()
        self.assertNotIn("move_grade", build)

    def test_tier_sizes_ladder_and_facts_are_identical_with_the_grade_present_absent_null_or_garbage(self):
        def with_grade(g):
            with mock.patch.object(P.MG, "move_grade", return_value=g):
                v = TF.AdditiveOnly().card()["markets"]["spread"]["v2"]
            return {k: v[k] for k in ("tier", "facts", "shown_units", "shadow_units", "shadow_rule", "untested", "conflict", "lead", "flags", "series", "exec", "vs_fair")}
        base = with_grade(None)
        for g in ({"letter": "A", "against": False}, {"letter": None, "against": True}, "garbage", 7, {"letter": "Z"}, [1, 2]):
            self.assertEqual(with_grade(g), base)
        self.assertEqual((base["shown_units"], base["shadow_rule"]), (1, "v2s-1"))


class Stored(unittest.TestCase):
    def card(self, **kw):
        return TF.AdditiveOnly().card(**kw)

    def test_the_grade_is_only_on_a_shown_play_and_only_inside_v2(self):
        c = self.card()
        self.assertNotIn("move_grade", c["markets"]["ml"]["v2"])                                   # no shown play, no grade
        v = c["markets"]["spread"]["v2"]
        self.assertEqual(v["move_grade"]["rule"], "mg-1")
        self.assertEqual((v["move_grade"]["letter"], v["move_grade"]["against"], v["move_grade"]["against_by"]), (None, True, ["c"]))   # the home line moved toward home: against side A
        self.assertEqual(v["move_grade"], MG.move_grade(v["flags"], "spread", "away", "nba"))
        self.assertNotIn("move_grade", P.strip_plays_v2(c)["markets"]["spread"])
        self.assertNotIn("move_grade_error", v)

    def test_v2_plays_lists_the_cutoffs_the_page_reads(self):
        mg = P.plays_fields()["move_grade"]
        self.assertEqual((mg["rule"], mg["letters"], mg["shown"], mg["context_only"]), ("mg-1", ["A", "B", "C", "D"], True, True))
        self.assertEqual((mg["m_a"], mg["x_a"], mg["m_c"], mg["x_c"]), (EXPECT["m_a"], EXPECT["x_a"], EXPECT["m_c"], EXPECT["x_c"]))
        self.assertEqual(sorted(P.V2_TOP_KEYS), sorted(("v2_slate", "v2_tier_record", "v2_plays")))   # no new top key
        old = {k: v for k, v in P.plays_fields().items() if k != "move_grade"}
        self.assertEqual(sorted(old), sorted(["rule", "spec", "market_keys", "top_keys", "shown_rule", "shadow", "flags", "context_only"]))

    def test_old_and_new_differ_only_in_the_new_keys(self):
        with mock.patch.object(P.MG, "move_grade", side_effect=RuntimeError("x")), contextlib.redirect_stderr(io.StringIO()):
            old = self.card()
        new = self.card()
        for c in (old, new):
            for m in c["markets"].values():
                m["v2"].pop("move_grade", None)
                m["v2"].pop("move_grade_error", None)
        self.assertEqual(json.dumps(old, sort_keys=True), json.dumps(new, sort_keys=True))
        self.assertEqual(json.dumps(P.strip_plays_v2(self.card()), sort_keys=True), json.dumps(P.strip_plays_v2(new), sort_keys=True))

    def test_a_raising_grade_leaves_the_card_with_null_and_a_warning_and_every_other_key(self):
        c0 = self.card()
        err = io.StringIO()
        with mock.patch.object(P.MG, "move_grade", side_effect=TypeError("boom")), contextlib.redirect_stderr(err):
            c1 = self.card()
        v = c1["markets"]["spread"]["v2"]
        self.assertEqual((v["move_grade"], v["move_grade_error"]), (None, "TypeError"))
        self.assertIn("::warning::v2 move grade dropped for nba-a-b-2027-01-15 spread: TypeError", err.getvalue())
        drop = lambda c: {g: {k: x for k, x in m["v2"].items() if k not in ("move_grade", "move_grade_error")} for g, m in c["markets"].items()}
        self.assertEqual(drop(c0), drop(c1))                                                       # flags and series included
        self.assertIsNotNone(v["flags"])
        self.assertEqual(json.dumps(P.strip_plays_v2(c0)), json.dumps(P.strip_plays_v2(c1)))

    def test_a_dropped_flag_block_gives_a_no_flags_grade(self):
        with mock.patch.object(P.F, "flags_block", side_effect=TypeError("boom")), contextlib.redirect_stderr(io.StringIO()):
            v = self.card()["markets"]["spread"]["v2"]
        self.assertEqual((v["flags"], v["move_grade"]["why"], v["move_grade"]["letter"]), (None, "no_flags", None))

    def test_the_card_builds_on_malformed_tape_rows(self):
        c = TP.Additive().card(vault=VAULT, quotes=TP.Malformed.Quotes(TF.Guard.BAD))
        self.assertIn("move_grade", c["markets"]["spread"]["v2"])
        json.dumps(c)

    def test_the_grade_is_read_with_the_shown_sides_own_direction(self):
        """An over reads a line moving UP as toward, an under reads it as against: the call in market_v2 passes the shown side's norm."""
        m = TP.market(S="Over", O="Under")
        up = {"rule": "v2f-2", "asof": ASOF, "span_min": 1300, "pin": None, "limit": None, "why": {}, "a": None, "c": "toward",
              "line": {"kind": "line", "state": "toward", "t_c": 3.0, "books": 4, "same_way": 3, "by_book": {}, "extreme": None, "pin": {"from": 220.5, "to": 224.0}}}
        for sidename, norm, want in (("Over", "over", (3.5, "B")), ("Under", "under", (-3.5, "B"))):
            mm = copy.deepcopy(m)
            mm["sf"]["all"]["side"] = sidename
            with mock.patch.object(P.F, "flags_block", return_value=(copy.deepcopy(up), None)):
                v2, _ = P.market_v2("nba", "total", mm, [], {}, {"mk": {}}, ASOF, {"Over": "over", "Under": "under"}, rows=[])
            r = v2["move_grade"]
            self.assertEqual(r["c_pts"], want[0], sidename)
            self.assertEqual(r["letter"], want[1], sidename)

    def test_the_block_size(self):
        c = self.card()
        n = len(json.dumps(c["markets"]["spread"]["v2"]["move_grade"], separators=(",", ":")))
        self.assertLess(n, 400)


class SizeGate(unittest.TestCase):
    def doc(self):
        games = []
        for i in range(12):
            games.append({"ev": f"e{i}", "markets": {"spread": {"sides": {}, "v2": {
                "rule": "v2t-1", "tier": "thin", "move_grade": {"rule": "mg-1", "letter": "B", "against": False},
                "flags": {"rule": "v2f-2", "pad": "f" * 200, "line": {"state": "toward", "by_book": {"X": "b" * 500}}}, "series": {"pad": "s" * 3000}}}}})
        return {"built": 1, "games": games, "v2_plays": {"rule": "v2t-1", "flags": {"rule": "v2f-2"}, "move_grade": {"rule": "mg-1"}}}

    def test_the_grade_survives_every_flags_drop_step_and_is_not_counted_in_the_flags_budget(self):
        full = CS.flags_kb(self.doc())
        no_series = copy.deepcopy(self.doc())
        for v in CS._v2_blocks(no_series):
            v.pop("series")
        steps = (CS.flags_kb(no_series) + 0.001, 0.5, 0.0)                                         # drops series, then by_book, then all flags
        dropped_all = []
        for kb in steps:
            d = self.doc()
            out, dropped = CS.enforce_flags(d, kb)
            dropped_all.append(dropped)
            for v in CS._v2_blocks(out):
                self.assertEqual(v["move_grade"], {"rule": "mg-1", "letter": "B", "against": False})
            self.assertEqual(out["v2_plays"]["move_grade"], {"rule": "mg-1"})
        self.assertEqual(dropped_all[-1], ["series", "by_book", "flags"])
        self.assertGreater(full, 0)
        d = self.doc()
        pad = copy.deepcopy(d)
        for v in CS._v2_blocks(pad):
            v["move_grade"]["pad"] = "m" * 5000
        self.assertEqual(CS.flags_kb(pad), CS.flags_kb(d))                                         # flags_kb counts v2.flags and v2.series only

    def test_the_whole_v2_rule_strips_the_grade_with_the_rest_of_v2(self):
        d = self.doc()
        s = P.strip_plays_v2(d)
        for g in s["games"]:
            self.assertNotIn("v2", g["markets"]["spread"])
        self.assertNotIn("v2_plays", s)


class ForwardLog(unittest.TestCase):
    def frozen(self, grade=True):
        c = TP.Additive().card(vault=VAULT, quotes=TP.Malformed.Quotes(TF.AdditiveOnly.ROWS))
        if not grade:
            for m in c["markets"].values():
                m["v2"].pop("move_grade", None)
        return c

    def test_new_rows_carry_mg_and_old_keys_keep_their_values(self):
        c = self.frozen()
        new = P.log_row("nba/frozen/d/x.json", c, "spread", 1)
        old = P.log_row("nba/frozen/d/x.json", self.frozen(False), "spread", 1)
        self.assertIn("mg", new)
        self.assertNotIn("mg", old)                                                                # a card built before the grade: "not logged", never D
        self.assertEqual({k: v for k, v in new.items() if k != "mg"}, old)
        self.assertEqual(new["mg"], MG.mg_of(c["markets"]["spread"]["v2"]["move_grade"]))
        self.assertEqual(sorted(new["mg"]), sorted(["rule", "letter", "against", "basis", "against_by", "a_pts", "c_pts", "why"]))
        self.assertLess(len(json.dumps(new["mg"], separators=(",", ":"))), 140)
        self.assertIn("mf", new)                                                                   # the flags row is untouched

    def test_a_dropped_grade_logs_a_null_mg_not_a_missing_one(self):
        c = self.frozen()
        c["markets"]["spread"]["v2"]["move_grade"] = None
        row = P.log_row("r", c, "spread", 1)
        self.assertIn("mg", row)
        self.assertIsNone(row["mg"])

    def test_the_repair_pass_equals_the_on_time_row(self):
        c = self.frozen()
        with tempfile.TemporaryDirectory() as root:
            rel = "nba/frozen/2027-01-15/x@1800000900.json"
            os.makedirs(os.path.join(root, os.path.dirname(rel)))
            json.dump(c, open(os.path.join(root, rel), "w"))
            on_time = P.log_row(rel, c, "spread", 5)
            self.assertEqual(P.sync_log(root, "nba", 1_800_000_900, extra=[rel]), 1)
            lines = [json.loads(l) for l in open(os.path.join(root, "nba", "v2_tier", "2027-01.jsonl"))]
            self.assertEqual({k: v for k, v in lines[0].items() if k != "logged_at"}, {k: v for k, v in on_time.items() if k != "logged_at"})
            self.assertEqual(lines[0]["mg"], MG.mg_of(c["markets"]["spread"]["v2"]["move_grade"]))

    def test_mg_of(self):
        self.assertIsNone(MG.mg_of(None))
        self.assertIsNone(MG.mg_of("x"))
        g = grade(flg("toward", 2.5))
        self.assertEqual(MG.mg_of(g), {"rule": "mg-1", "letter": "A", "against": False, "basis": "a_mark", "against_by": None, "a_pts": 2.5, "c_pts": None, "why": None})
        self.assertTrue(MG.mg_of(grade(flg("away", -2.0)))["against"])


class RecordTests(unittest.TestCase):
    def play(self, sport, key, bucket, res="win", flat=0.8, cut=1000, group="ml"):
        mg = {"letter": bucket.upper() if bucket in "abcd" and len(bucket) == 1 else None, "against": bucket == "against", "why": "flags_unreadable" if bucket == "unreadable" else None}
        return {"key": key, "sport": sport, "group": group, "cut": cut, "res": res, "flat": flat, "mg": mg, "msrc": "derived", "fa": None, "fc": None, "tier": "thin", "clv": None}

    def test_every_play_sits_in_exactly_one_slice(self):
        ps = [self.play("nba", str(i), b) for i, b in enumerate(("a", "b", "c", "d", "against", "unreadable", "d"))]
        for p in ps:
            self.assertEqual(sum(1 for sl in MGR.SLICES if MGR._in(p, sl)), 1)
        ps.append(dict(self.play("nba", "9", "a"), mg=None))
        self.assertEqual(MG.bucket_of(None), "unreadable")
        d = MGR.build(ps, 1, "x", {})
        self.assertEqual(sum(d["sports"]["nba"][sl]["all"]["n"] for sl in MGR.SLICES), len(ps))

    def test_slice_totals_equal_the_old_record_per_sport_and_headline(self):
        kinds = ("a", "b", "c", "d", "against", "unreadable")
        ps = [self.play(s, f"{s}{i}", kinds[i % 6], "win" if i % 3 else "loss", 0.9 if i % 3 else -1.0, group="ml") for s in SPORTS for i in range(13)]
        out = MGR.compute(ps)
        for name in ("nba", "nfl", "cbb", "cfb", "headline", "all"):
            tot = lambda k: sum(out["slices"][name][sl][k] for sl in MGR.SLICES)
            self.assertEqual((tot("n"), tot("w"), tot("l")), tuple(out["old"][name][k] for k in ("n", "w", "l")), name)
            self.assertAlmostEqual(sum(out["slices"][name][sl]["units"] for sl in MGR.SLICES), out["old"][name]["units"], places=1)
        d = MGR.build(ps, 1, "x", {})
        self.assertEqual(sum(d["all"][sl]["all"]["n"] for sl in MGR.SLICES), sum(1 for p in ps if p["sport"] in MGR.ALL_SPORTS))      # CFB is not pooled
        self.assertEqual(sum(d["sports"]["cfb"][sl]["all"]["n"] for sl in MGR.SLICES), 13)

    def test_a_marker_wins_over_a_letter_in_the_slice(self):
        self.assertEqual(MG.bucket_of({"against": True, "letter": "A"}), "against")
        self.assertEqual(MG.bucket_of({"against": False, "letter": "C"}), "c")
        self.assertEqual(MG.bucket_of({"against": None, "letter": None}), "unreadable")

    def test_shape_counts_by_hand(self):
        ps = [self.play("nba", "1", "a", "win", 0.8), self.play("nba", "2", "a", "loss", -1.0), self.play("nba", "3", "against", "win", 0.5), self.play("nba", "4", "d", "push", 0.0)]
        d = MGR.build(ps, 123, "abc", {})
        self.assertEqual((d["built"], d["data_ref"], d["mg_rule"], d["slices"]), (123, "abc", "mg-1", list(MGR.SLICES)))
        self.assertEqual(d["sports"]["nba"]["a"]["all"], {"w": 1, "l": 1, "p": 0, "n": 2, "units": -0.2, "roi": -0.1, "se": 0.9})
        self.assertEqual(d["sports"]["nba"]["d"]["all"], {"w": 0, "l": 0, "p": 1, "n": 1, "units": 0.0, "roi": 0.0, "se": None})
        empty = d["sports"]["nfl"]["a"]["all"]
        self.assertEqual((empty["n"], empty["roi"]), (0, None))                                    # null at n = 0, never 0

    def test_forward_is_zero_without_a_log_and_in_sample_is_everything(self):
        ps = [self.play("nba", "1", "a"), self.play("nfl", "2", "b")]
        d = MGR.build(ps, 1, "x", {"1": {"key": "1", "cut": 1000, "tier": "thin", "mf": {"pin_state": "toward"}}})     # a log row with mf but no mg: not forward for the grade
        self.assertEqual((d["first_logged_cut"], d["logged_rows"], d["forward_graded"]), (None, 0, 0))
        self.assertEqual(d["forward_note"], MGR.FORWARD_NOTE_REGISTERED)                           # registered 2026-11-24: the note says what counts
        for s in SPORTS:
            for sl in MGR.SLICES:
                self.assertEqual(d["sports"][s][sl]["forward"]["n"], 0)
                self.assertEqual(d["sports"][s][sl]["in_sample"], d["sports"][s][sl]["all"])

    def test_forward_uses_the_logged_grade_and_never_a_recomputation(self):
        ps = [self.play("nba", "1", "d", cut=500), self.play("nba", "2", "d", cut=900)]
        logged = {"2": {"key": "2", "cut": 900, "tier": "thin", "mg": {"letter": "A", "against": False, "why": None}},
                  "3": {"key": "3", "cut": 950, "tier": "thin", "mg": None}}
        with mock.patch.object(MGR, "REGISTERED_CUT", 800):                                       # as if the prereg were registered at cut 800
            d = MGR.build(ps, 1, "x", logged)
            dropped = MGR.build([self.play("nba", "3", "a")], 1, "x", logged)["sports"]["nba"]
        n = d["sports"]["nba"]
        self.assertEqual((n["a"]["forward"]["n"], n["d"]["forward"]["n"]), (1, 0))                  # play 2 is A as logged, though its card now reads D
        self.assertEqual((d["first_logged_cut"], d["logged_rows"], d["forward_graded"], d["registered_cut"]), (900, 2, 1, 800))
        self.assertEqual(n["d"]["in_sample"]["n"], 1)                                              # play 1: cut 500 is before the first logged lock
        self.assertEqual(n["a"]["all"]["n"], 1)
        self.assertEqual(n["a"]["in_sample"]["n"], 0)                                              # the first logged lock is forward, never also in-sample
        self.assertEqual((dropped["unreadable"]["forward"]["n"], dropped["a"]["forward"]["n"]), (1, 0))   # an mg of null is a dropped block: unreadable

    def test_a_logged_mg_row_cannot_be_forward_while_the_registration_cut_is_none(self):
        """Before a registration, rows logged cannot count however they were logged. The constant is patched to None here (it was None until the user registered on 2026-11-24)."""
        with mock.patch.object(MGR, "REGISTERED_CUT", None):
            self._none_case()

    def test_the_registration_cut_is_set_and_rows_logged_before_it_do_not_count(self):
        self.assertIsInstance(MGR.REGISTERED_CUT, int)
        self.assertGreater(MGR.REGISTERED_CUT, 1795500000)                                        # 2026-11-24, the registering commit
        ps = [self.play("nba", "1", "a", cut=MGR.REGISTERED_CUT - 1), self.play("nba", "2", "a", cut=MGR.REGISTERED_CUT)]
        logged = {k: {"key": k, "cut": ps[i]["cut"], "mg": {"letter": "A", "against": False, "why": None}} for i, k in enumerate(("1", "2"))}
        d = MGR.build(ps, 1, "x", logged)
        self.assertEqual((d["forward_graded"], d["logged_not_counted"], d["registered_cut"]), (0, 2, MGR.REGISTERED_CUT))   # a cut equal to or before the registration never counts

    def _none_case(self):
        ps = [self.play("nba", "1", "a", cut=500), self.play("nba", "2", "b", cut=900), self.play("cfb", "3", "c", cut=2000)]
        logged = {"2": {"key": "2", "cut": 900, "mg": {"letter": "B", "against": False, "why": None}}, "3": {"key": "3", "cut": 2000, "mg": {"letter": "C", "against": False, "why": None}}}
        d = MGR.build(ps, 1, "x", logged)
        self.assertEqual((d["forward_graded"], d["registered_cut"], d["logged_rows"], d["logged_not_counted"]), (0, None, 2, 2))
        self.assertEqual(d["forward_note"], "The forward test is proposed, not registered. Plays logged before registration do not count.")
        for sp_ in SPORTS:
            for sl in MGR.SLICES:
                self.assertEqual(d["sports"][sp_][sl]["forward"]["n"], 0)
        for sl in MGR.SLICES:
            self.assertEqual(d["all"][sl]["forward"]["n"], 0)
        self.assertEqual(d["sports"]["nba"]["b"]["all"]["n"], 1)                                   # still in all, and in no forward cell
        self.assertEqual(d["sports"]["nba"]["b"]["in_sample"]["n"], 0)                             # logged, not counted: not in-sample either
        self.assertEqual(d["sports"]["nba"]["a"]["in_sample"]["n"], 1)                             # cut before the first logged lock

    def test_with_a_registration_cut_only_plays_cut_strictly_after_it_count(self):
        ps = [self.play("nba", "1", "a", cut=800), self.play("nba", "2", "a", cut=801), self.play("nba", "3", "a", cut=2000)]
        logged = {k: {"key": k, "cut": c, "mg": {"letter": "A", "against": False, "why": None}} for k, c in (("1", 800), ("2", 801), ("3", 2000))}
        with mock.patch.object(MGR, "REGISTERED_CUT", 800):
            d = MGR.build(ps, 1, "x", logged)
        self.assertEqual((d["sports"]["nba"]["a"]["forward"]["n"], d["forward_graded"], d["logged_not_counted"]), (2, 2, 1))
        self.assertEqual(d["forward_note"], MGR.FORWARD_NOTE_REGISTERED)
        self.assertFalse(MGR.counts_forward({"forward": False, "cut": 5000}))
        self.assertFalse(MGR.counts_forward({"forward": True, "cut": "x"}))

    def test_units_are_summed_unrounded_and_roi_comes_from_that_sum(self):
        ps = [self.play("nba", str(i), "a", flat=f) for i, f in enumerate((0.2249, 0, 0, 0, 0, 0, 0))]
        c = MGR.cell(ps)
        self.assertEqual((c["n"], c["units"], c["roi"]), (7, 0.22, 0.032129))                        # 0.2249 / 7 = 3.2%; the rounded 0.22 / 7 would give 3.1%
        self.assertEqual(MGR.cell([])["roi"], None)

    def test_the_standard_error(self):
        self.assertEqual(MGR.cell([self.play("nba", "1", "a", flat=1.0), self.play("nba", "2", "a", "loss", -1.0)])["se"], 1.0)
        self.assertIsNone(MGR.cell([self.play("nba", "1", "a")])["se"])
        self.assertIsNone(MGR.cell([])["se"])

    def test_source_order_logged_then_frozen_then_frozen_flags_then_derived(self):
        class Q:
            def game(self, *a):
                return [mk("spread", "Pinnacle", ASOF - 7200, -3.5, 0.5), mk("spread", "Pinnacle", ASOF - 600, -3.5, 0.6),
                        mk("spread", "Pinnacle", ASOF + 50, -3.5, 0.2)], "gk"
        stored = grade(flg("toward", 2.5))
        flags = flg("quiet", 0.0, "toward", move=2.0)
        c = {"sport": "nba", "ev": "nba-a-b-2027-01-15", "gst": ASOF + 900, "cut": ASOF, "vault": {"key": "k", "teams": {"away": ["A"], "home": ["B"]}},
             "markets": {"spread": {"sides": {"A": {}, "B": {}}, "v2": {"side": "B", "move_grade": stored, "flags": flags}}}}
        r = MGR.derive_grade(c, "spread", "B", Q())
        self.assertEqual((r["src"], r["mg"]), ("frozen", stored))                                  # the stored block wins over the stored flags
        del c["markets"]["spread"]["v2"]["move_grade"]
        r = MGR.derive_grade(c, "spread", "B", Q())
        self.assertEqual((r["src"], r["mg"]["letter"], r["mg"]["a"]), ("frozen_flags", "B", "quiet"))   # B is the home side of VAULT: the stored line move is toward it
        self.assertEqual(MGR.derive_grade(c, "spread", "B", None)["src"], "frozen_flags")
                                                                                                  # the card's v2 block is for side B: a play on side A is not covered by it
        r = MGR.derive_grade(c, "spread", "A", Q())
        self.assertEqual(r["src"], "derived")
        c["markets"]["spread"].pop("v2")
        self.assertEqual(MGR.derive_grade(c, "spread", "B", None), {"mg": None, "src": None})
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(MGR.derive_grade(c, "spread", "B", object())["src"], "error")

    def test_a_row_after_the_cut_changes_no_derived_letter(self):
        base = [mk("spread", "Pinnacle", ASOF - 7200, -3.5, 0.5), mk("spread", "Pinnacle", ASOF - 600, -3.5, 0.6)]
        late = [mk("spread", "Pinnacle", ASOF + 50, -3.5, 0.2), mk("spread", "Pinnacle", ASOF + 99, -9.5, 0.2)]
        c = {"sport": "nba", "ev": "nba-a-b-2027-01-15", "gst": ASOF + 900, "cut": ASOF, "vault": {"key": "k", "teams": {"away": ["A"], "home": ["B"]}},
             "markets": {"spread": {"sides": {"A": {}, "B": {}}}}}

        class Q:
            def __init__(self, rows):
                self.rows = rows

            def game(self, *a):
                return self.rows, "gk"
        self.assertEqual(MGR.derive_grade(c, "spread", "B", Q(base)), MGR.derive_grade(c, "spread", "B", Q(base + late)))

    def test_compute_lists_every_improving_slice_with_n(self):
        ps = [self.play("nba", "1", "a", "win", 0.8), self.play("nba", "2", "a", "loss", -1.0), self.play("nba", "3", "against", "loss", -1.0), self.play("nfl", "4", "against", "win", 0.9)]
        out = MGR.compute(ps)
        names = {f["slice"]: f for f in out["flagged"]}
        self.assertNotIn("NBA A", names)                                                           # -0.2u does not improve
        self.assertEqual((names["NFL moved against"]["n"], names["NFL moved against"]["small_sample"]), (1, True))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            MGR.print_report(out)
        text = buf.getvalue()
        for needle in ("OLD (no grade, every play)", "NEW A ", "FLAGGED FOR CLOSE MONITORING (Move grade)", "NFL moved against (flat ROI, n=1)  [small sample]"):
            self.assertIn(needle, text)

    def test_the_small_sample_tag_is_at_30(self):
        thirty = [self.play("nfl", "t%d" % i, "c", "win", 0.5) for i in range(30)]
        seven = [self.play("nba", "s%d" % i, "c", "win", 0.5) for i in range(7)]
        names = {f["slice"]: f for f in MGR.compute(seven + thirty)["flagged"]}
        self.assertEqual((names["NBA C"]["small_sample"], names["NFL C"]["small_sample"]), (True, False))
        self.assertEqual(MGR.SMALL_N, 30)

    def test_the_command_writes_a_small_file_and_reads_the_log(self):
        with tempfile.TemporaryDirectory() as d:
            fx = TP.Fixture(d)
            fx.add(TP.tcard("nba", "g1", TP.CUT, v2=None, pts=0.5))
            fx.commit()
            os.makedirs(os.path.join(d, "tape", "nba"), exist_ok=True)
            out = os.path.join(d, "o", "move_grade_record.json")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(MGR.main(["--data-dir", d, "--book-tape", os.path.join(d, "tape"), "--out", out, "--now", "5", "--data-ref", "abc"]), 0)
            doc = json.load(open(out))
            self.assertEqual((doc["built"], doc["data_ref"], doc["forward_graded"], doc["mg_rule"]), (5, "abc", 0, "mg-1"))
            self.assertEqual(doc["sports"]["nba"]["unreadable"]["all"]["n"], 1)                    # no tape for the game: no grade
            self.assertLess(os.path.getsize(out), 12_000)


class History(unittest.TestCase):
    def build(self, grade_module):
        with tempfile.TemporaryDirectory() as d:
            fx = TP.Fixture(d)
            fx.add(TP.tcard("nba", "g1", TP.CUT, v2=None, pts=0.5))
            fx.commit()
            os.makedirs(os.path.join(d, "tape", "nba"), exist_ok=True)
            buf, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                self.assertEqual(TH.main(["--repo", d, "--ref", "main", "--book-tape", os.path.join(d, "tape")]), 0)
            return buf.getvalue(), err.getvalue()

    def test_the_new_block_is_last_and_everything_above_it_is_what_it_was(self):
        text, _ = self.build(MGR)
        self.assertIn("MOVE GRADE mg-1", text)
        head, block = text.split("\nMOVE GRADE mg-1")
        self.assertIn("FLAGGED FOR CLOSE MONITORING: every record that improves", head)
        self.assertNotIn("MOVE GRADE", head)
        with mock.patch.dict(sys.modules, {"sharps_v2.move_grade_record": None}):
            import sharps_v2
            saved = getattr(sharps_v2, "move_grade_record", None)
            if saved is not None:
                delattr(sharps_v2, "move_grade_record")
            try:
                old_text, err = self.build(None)
            finally:
                if saved is not None:
                    sharps_v2.move_grade_record = saved
        skip_commit = lambda t: t.split("\n", 1)[1].rstrip("\n")                                   # the first line names the fixture repo's commit hash, which depends on the second it was made
        self.assertEqual(skip_commit(old_text), skip_commit(head))                                 # byte for byte, with the block off (the module will not import)
        self.assertIn("move grade record skipped", err)
        self.assertNotIn("MOVE GRADE", old_text)

    def test_the_flag_and_tier_records_are_byte_identical_with_and_without_the_grade_module(self):
        """flag_record.main calls tier_history.play_rows with the quote tape, which imports move_grade_record when it can. The flag and tier records must not change either way."""
        import sharps_v2

        def run(block):
            outs = {}
            with tempfile.TemporaryDirectory() as d:
                fx = TP.Fixture(d)
                fx.add(TP.tcard("nba", "g1", TP.CUT, v2=None, pts=0.5))
                fx.commit()
                os.makedirs(os.path.join(d, "tape", "nba"), exist_ok=True)
                for name, mod in (("flag", FR), ("tier", TR)):
                    out = os.path.join(d, "o", name + ".json")
                    ctx = mock.patch.dict(sys.modules, {"sharps_v2.move_grade_record": None}) if block else contextlib.nullcontext()
                    saved = getattr(sharps_v2, "move_grade_record", None)
                    if block and saved is not None:
                        delattr(sharps_v2, "move_grade_record")
                    try:
                        with ctx, contextlib.redirect_stderr(io.StringIO()):
                            self.assertEqual(mod.main(["--data-dir", d, "--book-tape", os.path.join(d, "tape"), "--out", out, "--now", "5", "--data-ref", "abc"]), 0)
                    finally:
                        if block and saved is not None:
                            sharps_v2.move_grade_record = saved
                    outs[name] = open(out, "rb").read()
            return outs
        with_mg, without_mg = run(False), run(True)
        self.assertEqual(with_mg, without_mg)

    def test_the_tier_and_flag_modules_themselves_never_name_the_grade(self):
        for rel in ("tier_record.py", "flag_record.py", "flags_v2.py"):
            self.assertNotIn("move_grade", open(os.path.join(ROOT, "scripts", "sharps_v2", rel), encoding="utf-8").read(), rel)

    def test_a_problem_in_the_grade_block_never_stops_the_json_write(self):
        with tempfile.TemporaryDirectory() as d:
            fx = TP.Fixture(d)
            fx.add(TP.tcard("nba", "g1", TP.CUT, v2=None, pts=0.5))
            fx.commit()
            os.makedirs(os.path.join(d, "tape", "nba"), exist_ok=True)
            js = os.path.join(d, "out.json")
            buf, err = io.StringIO(), io.StringIO()
            with mock.patch.object(MGR, "compute", side_effect=ValueError("boom")), contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                self.assertEqual(TH.main(["--repo", d, "--ref", "main", "--book-tape", os.path.join(d, "tape"), "--json", js]), 0)
            self.assertIn("move grade report skipped", err.getvalue())
            self.assertNotIn("MOVE GRADE", buf.getvalue())
            doc = json.load(open(js))
            self.assertNotIn("move_grade", doc)
            self.assertIn("tiers", doc)


class Workflow(unittest.TestCase):
    def test_the_step_never_blocks_and_publishes_beside_the_flag_record(self):
        wf = open(os.path.join(ROOT, ".github", "workflows", "pm-cards.yml"), encoding="utf-8").read()
        self.assertIn("name: Move grade record (context only, never blocks the publish)", wf)
        self.assertIn("python3 -I scripts/sharps_v2/move_grade_record.py --data-dir pmdata --book-tape data/book_tape --out live/move_grade_record.json", wf)
        self.assertIn("::warning::move_grade_record.json not built this run", wf)
        self.assertIn("rm -f live/move_grade_record.json", wf)
        self.assertIn("100644 blob %s\\tmove_grade_record.json", wf)
        self.assertIn("tests.test_sharps_v2_movegrade", wf)
        step = wf.split("name: Move grade record")[1].split("- name:")[0]
        self.assertNotIn("exit 1", step)
        self.assertIn("||", step)                                                                  # a failure drops the file for this run only


class Wording(unittest.TestCase):
    def test_no_banned_word_in_any_string_the_feature_publishes(self):
        blobs = [MG.mg_fields(), grade(flg("toward", 2.5)), grade(flg("away", -2.0)), grade(None), grade(flg("quiet", 0.6)),
                 MG.mg_of(grade(flg("toward", 2.5))), MGR.LABEL]
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
        for s in strings + [MGR.RULE, MGR.FORWARD_NOTE, MGR.FORWARD_NOTE_REGISTERED]:
            self.assertIsNone(re.search(r"strong", s, re.I), s)
        for s in strings:
            self.assertIsNone(BANNED_FLAGS.search(s.replace("_", " ")), s)
            self.assertNotRegex(s, r"(?i)sharp grade|\bpick\b|\brating\b")


class NoEmDash(unittest.TestCase):
    def test_no_u2014_or_u2013_in_the_new_or_changed_files(self):
        files = ["scripts/sharps_v2/move_grade.py", "scripts/sharps_v2/move_grade_record.py", "scripts/sharps_v2/move_grade_history.py", "scripts/sharps_v2/plays_v2.py",
                 "scripts/sharps_v2/tier_history.py", "tests/test_sharps_v2_movegrade.py", "docs/sharp-movegrade-prereg.md", "docs/side-cards.md", "docs/side-card-record.md",
                 ".github/workflows/pm-cards.yml"]
        for f in files:
            p = os.path.join(ROOT, f)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as fh:
                    text = fh.read()
                self.assertNotIn(chr(0x2014), text, f)


if __name__ == "__main__":
    unittest.main()
