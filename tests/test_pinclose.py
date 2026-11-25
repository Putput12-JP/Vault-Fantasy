"""Unit tests for the `pinclose` rows (scripts/sharps_v2/pinclose.py, docs/sharps-v2-grader-note.md): Pinnacle's closing no-vig price for the side of
every graded shown play, stored once beside the result rows. Synthetic inputs only; no network, no stored data. Run from the repo root:
    python3 -m unittest tests.test_pinclose
"""
import contextlib, copy, io, json, os, sys, tempfile, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)
import benchmark_h2h as H  # noqa: E402
import build_side_cards as BSC  # noqa: E402
import grade_side_cards as G  # noqa: E402
from sharps_v2 import move_grade_history as MGH  # noqa: E402
from sharps_v2 import pinclose as PC  # noqa: E402
from sharps_v2 import pinclose_history as PH  # noqa: E402
from sharps_v2 import tier_history as TH  # noqa: E402
import test_side_card_record as TSR  # noqa: E402

GST = 1_800_000_000
CUT = GST - 900
NOW = GST + 6 * 3600
MONTH = time.strftime("%Y-%m", time.gmtime(GST))        # append_rows files a row under the month of its game start (UTC)


def slurp(*parts, mode="r"):
    with open(os.path.join(*parts), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        return f.read()


def prob(o):
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)


def fair2(mine, other):
    a, b = prob(mine), prob(other)
    return a / (a + b)


def tape_row(t, ml=None, sp=None, tot=None, gk="nba:1", start=GST, book="Pinnacle"):
    return {"t": t, "book": book, "gk": gk, "ml": ml, "sp": sp, "tot": tot, "start": start, "lim": [1000, 1000, 1000]}


def pin_rows(rows):
    """What BookTape would hand over for one game: Pinnacle rows with t, ml, sp, tot."""
    return [{"t": r["t"], "ml": r.get("ml"), "sp": r.get("sp"), "tot": r.get("tot")} for r in rows]


def card(sport="nba", g="ml", side="A", line=None, price=0.55, ev="nba-bos-nyk-2026-11-20", gk="nba:1", names=None, sides=None):
    if sides is None:
        sides = ["Over", "Under"] if g == "total" else ["A", "B"]
    m = {"sides": {s: {"all": {}} for s in sides},
         "sf": {"all": {"side": side, "units": 3, "line": line, "price": price, "price_t": CUT - 60}}}
    return {"sport": sport, "ev": ev, "gst": GST, "cut": CUT, "frozen": True, "test": {"counts": True, "why_not": []},
            "vault": {"key": gk, "teams": names or {"away": ["B"], "home": ["A"]}}, "markets": {g: m}}


def result(rel, c, g="ml", side="A", line=None, price=0.55, status="graded", play="sf", variant="all", gst=None):
    return {"kind": "result", "play": play, "variant": variant, "status": status, "card": rel, "group": g, "side": side, "line": line,
            "price": price, "cut": c["cut"], "gst": gst or c["gst"], "sport": c["sport"], "ev": c["ev"], "res": "win", "flat": 0.8, "units": 3,
            "graded_at": c["gst"] + 3600, "key": f"{rel}|{g}|{variant}|{play}"}


class Env:
    """A throwaway pm-holders-data folder (pm_cards, pm_record) and a tape folder, for the end to end tests."""

    def __init__(self, d):
        self.d = d
        self.cards, self.out, self.tape = (os.path.join(d, x) for x in ("pm_cards", "pm_record", "tape"))
        self.n = 0
        self.rows = {}

    def add(self, c, **kw):
        self.n += 1
        rel = f"{c['sport']}/frozen/2026-11-{self.n:02d}/{c['ev']}-{self.n}@{c['gst']}.json"
        p = os.path.join(self.cards, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump(c, f)
        g = next(iter(c["markets"]))
        sf = c["markets"][g]["sf"]["all"]
        r = result(rel, c, g=g, side=kw.pop("side", sf["side"]), line=sf.get("line"), price=sf.get("price"), **kw)
        self.rows[r["key"]] = r
        return rel, r

    def write_rows(self, sport="nba", month=MONTH):
        p = os.path.join(self.out, "cards", sport)
        os.makedirs(p, exist_ok=True)
        with open(os.path.join(p, month + ".jsonl"), "w") as f:
            for r in self.rows.values():
                if r["sport"] == sport:
                    f.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")

    def write_tape(self, rows, sport="nba"):
        p = os.path.join(self.tape, sport)
        os.makedirs(p, exist_ok=True)
        with open(os.path.join(p, MONTH + ".jsonl"), "w") as f:
            f.write("".join(json.dumps(r) + "\n" for r in rows))

    def run(self, now=NOW):
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = PC.main(["--cards", self.cards, "--out", self.out, "--book-tape", self.tape, "--now", str(now)])
        return rc, buf.getvalue(), err.getvalue()

    def pin_rows(self, sport="nba"):
        fn = os.path.join(self.out, "cards", sport, MONTH + ".jsonl")
        with open(fn) as f:
            return [json.loads(l) for l in f if '"pinclose"' in l]


ML_ROWS = [tape_row(CUT - 3600, ml=[150, -170]), tape_row(GST - 30, ml=[130, -150]), tape_row(GST + 30, ml=[-300, 250])]


class ReadClose(unittest.TestCase):
    def read(self, rows, g="ml", norm="home", line=None, price=0.55, cut=CUT, gst=GST, how=None):
        return PC.read_close(pin_rows(rows), g, norm, gst, cut, line, price, how)

    def test_the_close_is_the_last_row_at_or_before_start_and_a_later_row_is_never_read(self):
        r = self.read(ML_ROWS)
        self.assertEqual(r["close_t"], GST - 30)
        self.assertAlmostEqual(r["close_fair"], fair2(-150, 130), places=5)          # home: mine = the home price (second)
        self.assertEqual(r["why"], None)
        self.assertAlmostEqual(r["clv"], r["close_fair"] - 0.55, places=5)
        self.assertEqual(r["pts"], round((r["close_fair"] - 0.55) * 100, 2))
        # the same rows without the post-start row give the same close: the row at start + 30 changed nothing
        self.assertEqual(self.read(ML_ROWS[:2]), r)

    def test_a_row_exactly_at_start_counts_and_one_second_later_does_not(self):
        at = self.read(ML_ROWS + [tape_row(GST, ml=[200, -230])])
        self.assertEqual(at["close_t"], GST)
        later = self.read([tape_row(GST - 30, ml=[130, -150]), tape_row(GST + 1, ml=[200, -230])])
        self.assertEqual(later["close_t"], GST - 30)

    def test_a_game_with_only_post_start_rows_has_no_close_and_says_why(self):
        r = self.read([tape_row(GST + 5, ml=[130, -150])])
        self.assertEqual((r["close_fair"], r["clv"], r["pts"], r["move_pts"]), (None, None, None, None))
        self.assertEqual((r["why"], r["move_why"]), (PC.WHY_NO_CLOSE, PC.WHY_NO_CLOSE))

    def test_moneyline_home_and_away_read_the_two_prices_of_the_same_row(self):
        h, a = self.read(ML_ROWS, norm="home"), self.read(ML_ROWS, norm="away")
        self.assertAlmostEqual(h["close_fair"], fair2(-150, 130), places=5)
        self.assertAlmostEqual(a["close_fair"], fair2(130, -150), places=5)
        self.assertAlmostEqual(h["close_fair"] + a["close_fair"], 1.0, places=5)
        self.assertIsNone(h["close_line"])

    def test_spread_away_takes_the_negated_home_line_and_the_other_price(self):
        rows = [tape_row(CUT - 60, sp=[-3.5, -105, -115]), tape_row(GST - 60, sp=[-4.0, -110, -110])]
        home = self.read(rows, g="spread", norm="home", line=-4.0)
        away = self.read(rows, g="spread", norm="away", line=4.0)
        self.assertEqual((home["close_line"], away["close_line"]), (-4.0, 4.0))
        self.assertAlmostEqual(home["close_fair"], 0.5, places=5)
        self.assertEqual((home["why"], away["why"]), (None, None))
        self.assertIsNotNone(away["clv"])
        # on the earlier row the prices are not even: away reads the third value, home the second
        e = [tape_row(GST - 60, sp=[-3.5, -105, -115])]
        self.assertAlmostEqual(self.read(e, g="spread", norm="home", line=-3.5)["close_fair"], fair2(-105, -115), places=5)
        self.assertAlmostEqual(self.read(e, g="spread", norm="away", line=3.5)["close_fair"], fair2(-115, -105), places=5)

    def test_total_over_and_under_share_the_line(self):
        rows = [tape_row(GST - 60, tot=[221.5, -108, -112])]
        o, u = self.read(rows, g="total", norm="over", line=221.5), self.read(rows, g="total", norm="under", line=221.5)
        self.assertEqual((o["close_line"], u["close_line"]), (221.5, 221.5))
        self.assertAlmostEqual(o["close_fair"], fair2(-108, -112), places=5)
        self.assertAlmostEqual(u["close_fair"], fair2(-112, -108), places=5)

    def test_a_close_at_another_line_keeps_the_close_but_has_no_clv(self):
        rows = [tape_row(GST - 60, sp=[-5.5, -110, -110])]
        r = self.read(rows, g="spread", norm="home", line=-4.5)
        self.assertEqual(r["close_line"], -5.5)
        self.assertIsNotNone(r["close_fair"])
        self.assertEqual((r["clv"], r["pts"], r["why"]), (None, None, PC.WHY_LINE_CLOSE))
        self.assertIsNone(self.read(rows, g="total", norm="over", line=221.5)["clv"])

    def test_the_ticket_line_matches_within_the_registered_tolerance_only(self):
        rows = [tape_row(GST - 60, tot=[221.5, -110, -110])]
        self.assertIsNotNone(self.read(rows, g="total", norm="over", line=221.5 + PC.F.LINE_EPS - 0.001)["clv"])
        self.assertIsNone(self.read(rows, g="total", norm="over", line=221.5 + PC.F.LINE_EPS + 0.01)["clv"])
        self.assertEqual(self.read(rows, g="total", norm="over", line=None)["why"], PC.WHY_LINE_CLOSE)

    def test_no_tape_a_missing_price_and_an_unmapped_side_are_stored_reasons_never_zero(self):
        r = PC.read_close([], "ml", "home", GST, CUT, None, 0.5, "no_tape_rows_for_game")
        self.assertEqual((r["close_fair"], r["clv"], r["pts"], r["why"], r["move_why"]), (None, None, None, "no_tape_rows_for_game", "no_tape_rows_for_game"))
        self.assertEqual(self.read(ML_ROWS, norm=None)["why"], PC.WHY_UNMAPPED)
        self.assertEqual(self.read(ML_ROWS, norm=None)["close_fair"], None)
        for bad in (None, 0, 1, -0.2, 1.5):
            r = self.read(ML_ROWS, price=bad)
            self.assertEqual((r["clv"], r["pts"], r["why"]), (None, None, PC.WHY_NO_PRICE))
            self.assertIsNotNone(r["close_fair"])                                   # the close itself is still readable
            self.assertIsNotNone(r["move_pts"])

    def test_malformed_rows_are_skipped_never_indexed_blind(self):
        rows = [tape_row(GST - 90, ml=[130, -150]), {"t": GST - 60, "ml": [130]}, {"t": GST - 50, "ml": None}, {"t": None, "ml": [100, -100]},
                {"t": GST - 40, "ml": ["x", None]}, "junk"]
        r = PC.read_close(pin_rows(rows[:3]) + [rows[3], rows[4], rows[5]], "ml", "home", GST, CUT, None, 0.5)
        self.assertEqual(r["close_t"], GST - 90)
        self.assertIsNotNone(r["clv"])

    def test_the_move_after_the_cut_is_close_fair_minus_fair_at_the_cut_in_points(self):
        rows = [tape_row(CUT - 100, ml=[150, -170]), tape_row(GST - 30, ml=[130, -150])]
        r = self.read(rows)
        self.assertAlmostEqual(r["fair_cut"], fair2(-170, 150), places=5)
        self.assertEqual(r["move_pts"], round((r["close_fair"] - r["fair_cut"]) * 100, 2))
        self.assertGreater(abs(r["move_pts"]), 0)
        # a row between the cut and the start moves the close, never the fair at the cut; a row after the cut is never the cut read
        r2 = self.read([tape_row(CUT - 100, ml=[150, -170]), tape_row(CUT + 5, ml=[100, -120]), tape_row(GST - 30, ml=[130, -150])])
        self.assertAlmostEqual(r2["fair_cut"], fair2(-170, 150), places=5)

    def test_no_change_in_the_last_fifteen_minutes_is_a_move_of_exactly_zero_not_unreadable(self):
        r = self.read([tape_row(CUT - 600, ml=[130, -150])])
        self.assertEqual((r["move_pts"], r["move_why"]), (0.0, None))
        self.assertEqual(r["close_t"], CUT - 600)

    def test_no_row_at_the_cut_leaves_the_clv_readable_and_the_move_with_a_reason(self):
        r = self.read([tape_row(CUT + 100, ml=[130, -150])])
        self.assertIsNotNone(r["clv"])
        self.assertEqual((r["move_pts"], r["fair_cut"], r["move_why"]), (None, None, PC.WHY_NO_CUT))

    def test_a_line_that_changed_since_the_cut_has_no_move_but_keeps_the_clv(self):
        rows = [tape_row(CUT - 100, sp=[-3.5, -110, -110]), tape_row(GST - 60, sp=[-4.5, -110, -110])]
        r = self.read(rows, g="spread", norm="home", line=-4.5)
        self.assertEqual((r["move_pts"], r["move_why"], r["line_cut"], r["close_line"]), (None, PC.WHY_LINE_MOVED, -3.5, -4.5))
        self.assertIsNotNone(r["clv"])


class Rows(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.env = Env(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def basic(self):
        rel, r = self.env.add(card())
        self.env.write_rows()
        self.env.write_tape(ML_ROWS)
        return rel, r

    def test_a_graded_shown_play_gets_one_row_with_every_field_and_the_price_at_the_cut(self):
        rel, r = self.basic()
        rc, out, err = self.env.run()
        self.assertEqual((rc, err), (0, ""))
        (p,) = self.env.pin_rows()
        self.assertEqual((p["key"], p["of"], p["kind"], p["v"]), (r["key"] + "|pinclose", r["key"], "pinclose", 1))
        self.assertEqual((p["sport"], p["ev"], p["gst"], p["cut"], p["group"], p["side"], p["price"]), ("nba", r["ev"], GST, CUT, "ml", "A", 0.55))
        self.assertEqual((p["close_t"], p["graded_at"]), (GST - 30, NOW))
        self.assertAlmostEqual(p["pts"], round((p["close_fair"] - 0.55) * 100, 2))
        for k in ("close_fair", "close_t", "close_line", "fair_cut", "line_cut", "clv", "pts", "move_pts", "why", "move_why"):
            self.assertIn(k, p)
        self.assertIn('"pinclose_new_rows":1', out.replace(" ", ""))

    def test_only_the_graded_shown_play_gets_a_row(self):
        c = card()
        self.env.add(c)                                                           # graded sf all: the only one
        self.env.add(card(ev="nba-a-b-2026-11-21"), status="void")
        self.env.add(card(ev="nba-c-d-2026-11-21"), status="unpriced")
        self.env.add(card(ev="nba-e-f-2026-11-21"), play="lock")
        self.env.add(card(ev="nba-g-h-2026-11-21"), variant="fwd")
        self.env.add(card(ev="nba-i-j-2026-11-21"), play="pub")
        self.env.write_rows()
        self.env.write_tape(ML_ROWS)
        self.env.run()
        self.assertEqual(len(self.env.pin_rows()), 1)

    def test_a_play_with_no_tape_for_its_game_gets_a_null_row_with_the_reason(self):
        self.env.add(card(gk="nba:99", ev="nba-zzz-yyy-2026-11-20"))
        self.env.write_rows()
        self.env.write_tape(ML_ROWS + [tape_row(GST + 100, ml=[100, -100], gk="nba:7")])    # the sport's tape runs past the start, the game is not in it
        self.env.run()
        (p,) = self.env.pin_rows()
        self.assertEqual((p["close_fair"], p["clv"], p["pts"], p["move_pts"], p["why"]), (None, None, None, None, "no_tape_rows_for_game"))

    def test_a_tape_that_does_not_run_past_the_start_holds_the_play_instead_of_writing_a_final_null(self):
        self.env.add(card())
        self.env.write_rows()
        self.env.write_tape([tape_row(GST - 5000, ml=[130, -150])])                # stale checkout: last tape row long before the start
        rc, out, _ = self.env.run()
        self.assertEqual(self.env.pin_rows(), [])
        self.assertIn('"tape_not_through_start":1', out.replace(" ", ""))
        self.env.write_tape(ML_ROWS)                                               # the tape catches up: the next run writes it
        self.env.run()
        self.assertEqual(len(self.env.pin_rows()), 1)

    def test_a_missing_tape_folder_writes_nothing_and_holds_every_play(self):
        self.env.add(card())
        self.env.write_rows()
        rc, out, err = self.env.run()
        self.assertEqual((rc, err), (0, ""))                                       # a held play is not an error
        self.assertEqual(self.env.pin_rows(), [])
        self.assertIn('"tape_not_through_start":1', out.replace(" ", ""))

    def test_the_tape_runs_through_the_start_when_a_row_sits_exactly_at_it(self):
        self.env.add(card())
        self.env.write_rows()
        self.env.write_tape([tape_row(GST - 30, ml=[130, -150]), tape_row(GST, ml=[100, -100], gk="nba:2")])
        self.env.run()
        self.assertEqual(len(self.env.pin_rows()), 1)

    def test_a_tape_that_ends_one_second_before_the_start_holds_the_play(self):
        self.env.add(card())
        self.env.write_rows()
        self.env.write_tape([tape_row(GST - 30, ml=[130, -150]), tape_row(GST - 1, ml=[100, -100], gk="nba:2")])
        _, out, _ = self.env.run()
        self.assertEqual(self.env.pin_rows(), [])
        self.assertIn('"tape_not_through_start":1', out.replace(" ", ""))

    def test_a_game_with_no_vault_key_is_found_by_its_two_teams_and_a_start_within_twelve_hours(self):
        c = card(gk="none")
        c["vault"] = {"away": "BOS", "home": "NYK", "teams": {"away": ["B"], "home": ["A"]}}               # no key: the tape is matched on the two teams
        self.env.add(c)
        self.env.write_rows()
        near = dict(tape_row(GST - 30, ml=[130, -150], gk=None), away="BOS", home="NYK", start=GST + 600)
        wrong_start = dict(tape_row(GST - 10, ml=[-500, 400], gk=None), away="BOS", home="NYK", start=GST + 13 * 3600)   # another game of the same two teams
        later = tape_row(GST + 60, ml=[100, -100], gk="nba:2")
        self.env.write_tape([near, wrong_start, later])
        self.env.run()
        (p,) = self.env.pin_rows()
        self.assertEqual(p["close_t"], GST - 30)

    def test_a_tape_game_other_than_the_play_is_never_read(self):
        self.env.add(card(gk="nba:1"))
        self.env.write_rows()
        self.env.write_tape([tape_row(GST - 30, ml=[-1000, 700], gk="nba:2"), tape_row(GST - 20, ml=[130, -150], gk="nba:1"), tape_row(GST + 9, ml=[1, 1], gk="nba:2")])
        self.env.run()
        (p,) = self.env.pin_rows()
        self.assertEqual(p["close_t"], GST - 20)
        self.assertAlmostEqual(p["close_fair"], fair2(-150, 130), places=5)

    def test_a_play_is_held_until_half_an_hour_after_the_start(self):
        self.basic()
        self.env.run(now=GST + PC.GRACE - 1)
        self.assertEqual(self.env.pin_rows(), [])
        self.env.run(now=GST + PC.GRACE)
        self.assertEqual(len(self.env.pin_rows()), 1)

    def test_a_missing_card_file_holds_the_play(self):
        rel, _ = self.basic()
        os.remove(os.path.join(self.env.cards, rel))
        _, out, _ = self.env.run()
        self.assertEqual(self.env.pin_rows(), [])
        self.assertIn('"card_missing":1', out.replace(" ", ""))

    def test_one_unreadable_play_never_stops_the_others(self):
        bad = card(ev="nba-bad-bad-2026-11-20")
        bad["markets"]["ml"]["sides"] = 5                                          # .keys() raises
        self.env.add(bad)
        self.env.add(card())
        self.env.write_rows()
        self.env.write_tape(ML_ROWS)
        rc, out, err = self.env.run()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.env.pin_rows()), 1)
        self.assertIn("read_error", out)
        self.assertIn("::warning::pinclose", err)

    def test_an_unmapped_side_is_a_stored_reason(self):
        self.env.add(card(names={"away": ["Nope"], "home": ["Never"]}))
        self.env.write_rows()
        self.env.write_tape(ML_ROWS)
        self.env.run()
        (p,) = self.env.pin_rows()
        self.assertEqual((p["why"], p["close_fair"]), (PC.WHY_UNMAPPED, None))

    def test_a_second_run_writes_nothing_and_changes_no_byte(self):
        self.basic()
        self.env.run()
        fn = os.path.join(self.env.out, "cards", "nba", MONTH + ".jsonl")
        rec = os.path.join(self.env.out, "pinclose_record.json")
        before = (slurp(fn, mode="rb"), slurp(rec, mode="rb"))
        _, out, _ = self.env.run(now=NOW + 7200)
        self.assertEqual((slurp(fn, mode="rb"), slurp(rec, mode="rb")), before)
        self.assertIn('"pinclose_new_rows":0', out.replace(" ", ""))

    def test_existing_lines_stay_byte_for_byte_and_rows_only_append(self):
        rel, r = self.env.add(card())
        fn = os.path.join(self.env.out, "cards", "nba")
        os.makedirs(fn)
        odd = json.dumps(r, indent=None, sort_keys=False) + "\n"                   # not the canonical compact form: it must survive untouched
        close = '{"key": "%s|close", "kind": "close", "of": "%s", "clv": 0.01,  "close": 0.5}\n' % (r["key"], r["key"])
        with open(os.path.join(fn, MONTH + ".jsonl"), "w") as f:
            f.write(odd + close)
        self.env.write_tape(ML_ROWS)
        before = slurp(fn, MONTH + ".jsonl", mode="rb")
        self.env.run()
        after = slurp(fn, MONTH + ".jsonl", mode="rb")
        self.assertTrue(after.startswith(before))
        self.assertEqual([json.loads(l)["kind"] for l in after[len(before):].decode().splitlines()], ["pinclose"])

    def test_a_stored_close_is_never_rewritten_even_when_the_tape_changes_later(self):
        self.basic()
        self.env.run()
        first = self.env.pin_rows()
        self.env.write_tape(ML_ROWS[:1] + [tape_row(GST - 10, ml=[300, -400])] + ML_ROWS[2:])
        self.env.run(now=NOW + 86400)
        self.assertEqual(self.env.pin_rows(), first)

    def test_the_row_lands_in_the_month_file_of_its_result(self):
        rel, r = self.basic()
        self.env.run()
        for fn in os.listdir(os.path.join(self.env.out, "cards", "nba")):
            self.assertEqual(fn, MONTH + ".jsonl")
        self.assertEqual(len(self.env.pin_rows()), 1)

    def test_every_sport_is_read_from_its_own_tape(self):
        self.env.add(card(sport="cfb", ev="cfb-a-b-2026-11-20", gk="cfb:1"))
        self.env.add(card(sport="nfl", ev="nfl-a-b-2026-11-20", gk="nfl:1"))
        for sp in ("cfb", "nfl"):
            self.env.write_rows(sp)
            self.env.write_tape([tape_row(GST - 30, ml=[130, -150], gk=sp + ":1"), tape_row(GST + 60, ml=[100, -100], gk=sp + ":2")], sport=sp)
        self.env.run()
        self.assertEqual([len(self.env.pin_rows(sp)) for sp in ("cfb", "nfl")], [1, 1])

    def test_a_row_stays_small(self):
        self.basic()
        self.env.run()
        for p in self.env.pin_rows():
            self.assertLess(len(json.dumps(p, separators=(",", ":"), sort_keys=True)), 700)
        self.assertLess(os.path.getsize(os.path.join(self.env.out, "pinclose_record.json")), 20000)

    def test_a_bad_output_folder_is_a_warning_not_a_failure(self):
        rc, out, err = self.env.run()
        self.assertEqual(rc, 0)                                                    # nothing to read: still exit 0
        with open(os.path.join(self._t.name, "f.txt"), "w") as f:
            f.write("a file where a folder should be")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(io.StringIO()):
            PC_main = PC.main(["--cards", self.env.cards, "--out", os.path.join(self._t.name, "f.txt", "x"), "--book-tape", self.env.tape, "--now", str(NOW)])
        self.assertEqual(PC_main, 0)
        self.assertIn("::warning::pinclose step skipped", buf.getvalue())


class Record(unittest.TestCase):
    def plays_and_closes(self):
        mk = lambda i, sp, g: {"kind": "result", "play": "sf", "variant": "all", "status": "graded", "key": f"{sp}{i}|{g}|all|sf", "sport": sp, "group": g}
        ps = [mk(1, "nba", "ml"), mk(2, "nba", "ml"), mk(3, "nba", "spread"), mk(4, "nba", "total"), mk(5, "nba", "ml")]
        base = {"kind": "pinclose", "v": 1}
        cs = [dict(base, key=ps[0]["key"] + "|pinclose", of=ps[0]["key"], close_fair=0.5, pts=1.0, move_pts=0.0, why=None),
              dict(base, key=ps[1]["key"] + "|pinclose", of=ps[1]["key"], close_fair=0.5, pts=-3.0, move_pts=0.5, why=None),
              dict(base, key=ps[2]["key"] + "|pinclose", of=ps[2]["key"], close_fair=0.5, pts=None, move_pts=None, why=PC.WHY_LINE_CLOSE),
              dict(base, key=ps[3]["key"] + "|pinclose", of=ps[3]["key"], close_fair=None, pts=None, move_pts=None, why=PC.WHY_NO_TAPE)]
        return ps, cs

    def test_counts_reasons_means_and_standard_errors(self):
        ps, cs = self.plays_and_closes()
        rec = PC.record(ps + cs, 5)["sports"]["nba"]
        self.assertEqual((rec["graded"], rec["with_close"], rec["pending"]), (5, 3, 1))
        self.assertEqual(rec["no_close_by_reason"], {PC.WHY_NO_TAPE: 1})
        self.assertEqual(rec["clv_unreadable_by_reason"], {PC.WHY_LINE_CLOSE: 1})
        self.assertEqual((rec["clv"]["n"], rec["clv"]["mean_pts"]), (2, -1.0))
        self.assertAlmostEqual(rec["clv"]["se_pts"], 2.0, places=3)                 # sd of (1, -3) = 2.828, over sqrt(2)
        self.assertEqual((rec["move"]["n"], rec["move"]["mean_pts"]), (2, 0.25))
        self.assertTrue(rec["clv"]["small_sample"])
        self.assertEqual(rec["by_market"]["ml"]["graded"], 3)
        self.assertEqual(rec["by_market"]["spread"]["clv"]["n"], 0)

    def test_a_slice_with_nothing_readable_has_null_means_never_zero(self):
        s = PC.stat([])
        self.assertEqual((s["n"], s["mean_pts"], s["se_pts"]), (0, None, None))
        s = PC.stat([0.5])
        self.assertEqual((s["mean_pts"], s["se_pts"]), (0.5, None))                 # one play: a mean, no standard error
        self.assertEqual(PC.stat([0.0, 0.0])["mean_pts"], 0.0)                      # a measured zero stays a zero

    def test_a_sport_with_no_graded_play_is_left_out(self):
        ps, cs = self.plays_and_closes()
        self.assertEqual(sorted(PC.record(ps + cs, 5)["sports"]), ["nba"])

    def test_only_result_rows_are_plays_and_only_pinclose_rows_are_closes(self):
        ps, cs = self.plays_and_closes()
        notres = dict(ps[0], kind="close", key="n|ml|all|sf")
        self.assertFalse(PC.shown_graded(notres))
        self.assertTrue(PC.shown_graded(ps[0]))
        other = [dict(cs[0], kind="close", key=ps[4]["key"] + "|close", of=ps[4]["key"], clv=0.5)]       # a Polymarket close row has an `of` too
        self.assertEqual(PC.record(ps + cs + other, 5), PC.record(ps + cs, 5))

    def test_rows_that_are_not_graded_shown_plays_do_not_count(self):
        ps, cs = self.plays_and_closes()
        extra = [dict(ps[0], key="x|ml|all|lock", play="lock"), dict(ps[0], key="y|ml|fwd|sf", variant="fwd"), dict(ps[0], key="z|ml|all|sf", status="void")]
        self.assertEqual(PC.record(ps + cs + extra, 5)["sports"]["nba"]["graded"], 5)


class NothingExistingMoves(unittest.TestCase):
    """The row kind is inert for every reader of the record rows."""

    def graded_rows(self):
        rows = []
        for i in range(3):
            rows += TSR.G.grade(TSR.card(TSR.LOCK), f"nba/frozen/d/x{i}.json", None, TSR.FACT, TSR.CLOSES, TSR.GST + 3600)[0]
        return rows

    def pin_for(self, r):
        return {"key": r["key"] + "|pinclose", "kind": "pinclose", "of": r["key"], "v": 1, "sport": r["sport"], "ev": r["ev"], "gst": r["gst"], "close_fair": 0.5,
                "pts": 1.0, "why": None}

    def test_the_record_is_identical_with_and_without_pinclose_rows(self):
        rows = self.graded_rows()
        pins = [self.pin_for(r) for r in rows if r["kind"] == "result"]
        cards = [TSR.card(TSR.LOCK)]
        a = G.record(rows, cards, 7)
        b = G.record(rows + pins, cards, 7)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertIn("pinclose", G.NOT_PLAYS)

    def test_a_pinclose_row_is_not_a_play_the_old_filter_would_have_crashed_on(self):
        rows = self.graded_rows()
        pin = self.pin_for(next(r for r in rows if r["kind"] == "result"))
        self.assertNotIn("play", pin)                                               # the grader's record reads r["play"]: the filter is what keeps it out

    def test_head_to_head_is_identical_with_and_without_pinclose_rows(self):
        rows = [r for r in self.graded_rows() if r["kind"] == "result"]
        pins = [self.pin_for(r) for r in rows]
        a = H.h2h([], rows, 0)
        b = H.h2h([], rows + pins, 0)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        src = slurp(ROOT, "scripts", "benchmark_h2h.py")
        self.assertNotIn('r.get("kind") != "close"', src)                           # both card row reads name pinclose too
        self.assertEqual(src.count('"close", "pinclose"'), 2)

    def test_the_grader_never_writes_or_reads_a_pinclose_row_itself(self):
        src = slurp(ROOT, "scripts", "grade_side_cards.py")
        self.assertEqual(src.count('"pinclose"'), 1)                                # only the NOT_PLAYS entry: the grader does not write the rows
        self.assertNotRegex(src, r"(from|import)\s+sharps_v2|import\s+pinclose")

    def test_the_record_page_reads_only_result_and_close_kinds(self):
        src = slurp(ROOT, "sharp-money", "sharps-v2", "sv2-record.js")
        self.assertNotIn("pinclose", src)                                           # no UI change in this PR: the page ignores the new rows
        self.assertIn("r.kind === 'result'", src)
        self.assertIn("r.kind === 'close'", src)

    def test_tier_history_play_rows_ignore_pinclose_rows(self):
        import test_sharps_v2_plays as TP
        with tempfile.TemporaryDirectory() as d:
            fx = TP.Fixture(d)
            fx.add(TP.tcard("nba", "g1", TP.CUT, pts=0.5))
            rel, = [r["card"] for r in fx.rows]
            fx.commit()
            tape = BSC.BookTape(os.path.join(d, "tape"))
            git = TH.Git(d, "HEAD")
            try:
                rows = TH.graded_rows(git)
                base = TH.play_rows(git, rows, tape)
                pin = {"key": fx.rows[0]["key"] + "|pinclose", "kind": "pinclose", "of": fx.rows[0]["key"], "card": rel, "group": "ml", "variant": "all",
                       "play": "sf", "status": "graded", "sport": "nba"}                     # even one that looks like a play never counts as a result
                self.assertEqual(TH.play_rows(git, rows + [pin], tape), base)
            finally:
                git.close()


class Consistency(unittest.TestCase):
    """The stored row and the two on-the-fly reads the repo already had cannot disagree."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.env = Env(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def cases(self):
        rows = []
        # moneyline, home and away; spread with the line unchanged; spread with the line moved; total with an off-main close
        rows += [tape_row(CUT - 600, ml=[150, -170], sp=[-3.5, -110, -110], tot=[221.5, -110, -110]),
                 tape_row(GST - 60, ml=[130, -150], sp=[-3.5, -105, -115], tot=[222.5, -110, -110]),
                 tape_row(GST + 60, ml=[100, -100], gk="nba:2")]                                   # another game: the sport's tape runs past this start
        return rows

    def test_clv_matches_tier_history_and_the_move_matches_after_moves(self):
        rows = self.cases()
        cases = [("ml", "A", None, 0.55), ("ml", "B", None, 0.45), ("spread", "A", -3.5, 0.52), ("spread", "B", 3.5, 0.48), ("total", "Over", 221.5, 0.5),
                 ("total", "Under", 222.5, 0.5)]
        tape = BSC.BookTape(self._t.name + "/tape")
        self.env.write_tape(rows)
        quotes = BSC.QuoteTape(self._t.name + "/tape")
        cards = {}
        results = []
        for g, side, line, price in cases:
            c = card(g=g, side=side, line=line, price=price, ev="nba-x-y-2026-11-20-%s-%s" % (g, side))
            rel, r = self.env.add(c)
            cards[rel] = c
            results.append(r)
        self.env.write_rows()
        self.env.run()
        stored = {p["of"]: p for p in self.env.pin_rows()}

        class FakeGit:
            def show(_, path):
                return json.dumps(cards[path[len("pm_cards/"):]])
        ps = [{"key": r["key"]} for r in results]
        moves = MGH.after_moves(FakeGit(), results, quotes, ps)
        for r in results:
            c, p = cards[r["card"]], stored[r["key"]]
            clv, _ = TH.pin_close_pts(c, r["group"], c["markets"][r["group"]]["sf"]["all"], tape)
            if p["pts"] is None or clv is None:
                self.assertEqual((p["pts"], clv), (None, None), r["key"])
            else:
                self.assertLessEqual(abs(p["pts"] - clv), 0.0101, r["key"])
            mv = moves.get(r["key"])
            if p["move_pts"] is None or mv is None:
                self.assertEqual((p["move_pts"], mv), (None, None), r["key"])
            else:
                self.assertLessEqual(abs(p["move_pts"] - mv), 0.0101, r["key"])
        self.assertTrue(any(p["pts"] is not None for p in stored.values()))
        self.assertGreaterEqual(sum(1 for r in results if stored[r["key"]]["move_pts"] is not None), 4)
        # the report's cross-check says the same thing: every comparable play agrees, and a doctored stored value is caught
        tier_ps = []
        for r in results:
            c = cards[r["card"]]
            clv, _ = TH.pin_close_pts(c, r["group"], c["markets"][r["group"]]["sf"]["all"], tape)
            tier_ps.append({"key": r["key"], "clv": clv})
        tier_ps.append({"key": "no|stored|row", "clv": 1.0})                         # a play with no pinclose row yet is skipped, not compared
        x = PH.cross_check(tier_ps, stored, tape, results, FakeGit(), quotes)
        self.assertEqual((x["clv_mismatch"], x["move_mismatch"]), (0, 0))
        self.assertGreaterEqual(x["clv_compared"], 4)
        self.assertGreaterEqual(x["move_compared"], 4)
        self.assertEqual((x["clv_only_stored"], x["clv_only_derived"], x["move_only_stored"], x["move_only_derived"]), (0, 0, 0, 0))
        bad = copy.deepcopy(stored)
        k = next(k for k, p in bad.items() if p["pts"] is not None and p["move_pts"] is not None)
        bad[k]["pts"] += 0.5
        bad[k]["move_pts"] += 0.5
        y = PH.cross_check(tier_ps, bad, tape, results, FakeGit(), quotes)
        self.assertEqual((y["clv_mismatch"], y["move_mismatch"]), (1, 1))
        self.assertIsNone(stored[results[5]["key"]]["move_pts"])                 # the total line moved 221.5 -> 222.5: no same-line move


class History(unittest.TestCase):
    def test_the_report_joins_tiers_to_stored_closes_and_flags_every_improving_cell(self):
        ps = [{"key": "a", "sport": "nba", "tier": "contested"}, {"key": "b", "sport": "nba", "tier": "contested"}, {"key": "c", "sport": "cbb", "tier": "clear"},
              {"key": "d", "sport": "nba", "tier": "none"}]
        closes = {"a": {"key": "a|pinclose", "close_fair": 0.5, "pts": 1.0, "move_pts": 0.0, "why": None},
                  "b": {"key": "b|pinclose", "close_fair": 0.5, "pts": 0.5, "move_pts": 0.0, "why": None},
                  "c": {"key": "c|pinclose", "close_fair": 0.5, "pts": -0.2, "move_pts": 0.0, "why": None}}
        t = PH.compute(ps, closes)
        self.assertEqual(t["nba"]["contested"]["clv"]["n"], 2)
        self.assertEqual(t["nba"]["none"]["pending"], 1)
        self.assertEqual(t["headline"]["all"]["graded"], 4)
        fl = PH.flagged(t)
        names = [f["slice"] for f in fl]
        self.assertIn("nba contested", names)
        self.assertNotIn("cbb clear", names)                                         # negative CLV is not an improving cell
        self.assertTrue(all(f["small_sample"] for f in fl))                           # n=2: tagged small sample
        self.assertEqual(sorted(t["headline"]), ["all", "clear", "contested", "none"])  # the headline pools NBA, NFL and CBB (tiers with plays only)
        self.assertEqual(t["headline"]["all"]["with_close"], 3)
        self.assertNotIn("nba", {f["slice"].split()[0] for f in PH.flagged(PH.compute([ps[0]], {"a": dict(closes["a"], pts=-1.0)}))})


class MoveAtTicketLine(unittest.TestCase):
    def test_a_moneyline_move_is_always_at_its_line_and_a_spread_move_needs_the_ticket_line_at_both_reads(self):
        ml = {"group": "ml", "move_pts": 0.7}
        self.assertEqual(PC.move_at_ticket_line(ml), 0.7)
        sp = {"group": "spread", "move_pts": -0.4, "line": -3.5, "line_cut": -3.5, "close_line": -3.5}
        self.assertEqual(PC.move_at_ticket_line(sp), -0.4)
        self.assertIsNone(PC.move_at_ticket_line(dict(sp, line=-4.5)))                       # Pinnacle held -3.5 but the ticket was on -4.5
        self.assertIsNone(PC.move_at_ticket_line(dict(sp, close_line=-4.5)))
        self.assertIsNone(PC.move_at_ticket_line(dict(sp, line_cut=-4.5)))
        self.assertEqual(PC.move_at_ticket_line(dict(sp, move_pts=0.0)), 0.0)                # a measured zero stays a zero
        self.assertIsNone(PC.move_at_ticket_line(dict(sp, move_pts=None)))
        self.assertIsNone(PC.move_at_ticket_line(dict(sp, line=None)))
        self.assertIsNone(PC.move_at_ticket_line(dict(ml, move_pts=None)))
        self.assertIsNone(PC.move_at_ticket_line(dict(ml, move_pts="0.7")))                  # a stored value that is not a number is not a move
        self.assertIsNone(PC.move_at_ticket_line(dict(ml, move_pts=True)))

    def test_the_record_counts_it_beside_the_same_line_move(self):
        ps = [{"kind": "result", "play": "sf", "variant": "all", "status": "graded", "key": f"k{i}", "sport": "nfl", "group": "spread"} for i in range(2)]
        cs = [{"kind": "pinclose", "key": "k0|pinclose", "of": "k0", "close_fair": 0.5, "pts": 1.0, "move_pts": 0.5, "why": None, "group": "spread", "line": -3.5, "line_cut": -3.5, "close_line": -3.5},
              {"kind": "pinclose", "key": "k1|pinclose", "of": "k1", "close_fair": 0.5, "pts": None, "move_pts": 0.5, "why": PC.WHY_LINE_CLOSE, "group": "spread", "line": -4.5, "line_cut": -3.5, "close_line": -3.5}]
        s = PC.record(ps + cs, 1)["sports"]["nfl"]
        self.assertEqual((s["move"]["n"], s["move_at_ticket_line"]["n"]), (2, 1))


class ClosesOf(unittest.TestCase):
    def test_only_pinclose_rows_are_stored_closes(self):
        rows = [{"kind": "pinclose", "key": "a|pinclose", "of": "a", "pts": 1.0}, {"kind": "close", "key": "b|close", "of": "b", "clv": 0.1},
                {"kind": "result", "key": "a"}, {"kind": "pinclose", "key": "c|pinclose"}, "junk"]
        self.assertEqual(sorted(PH.closes_of(rows)), ["a"])


class NoEmDash(unittest.TestCase):
    def test_no_u2014_in_new_files(self):
        for f in ("scripts/sharps_v2/pinclose.py", "scripts/sharps_v2/pinclose_history.py", "tests/test_pinclose.py", "docs/sharps-v2-grader-note.md",
                  "docs/side-card-record.md", ".github/workflows/pm-record.yml", ".github/workflows/pm-cards.yml", "scripts/grade_side_cards.py", "scripts/benchmark_h2h.py"):
            p = os.path.join(ROOT, f)
            if os.path.exists(p):
                self.assertNotIn(chr(0x2014), slurp(p), f)


class Workflow(unittest.TestCase):
    def test_the_pinclose_step_runs_after_the_grade_before_the_commit_and_fails_soft(self):
        t = slurp(ROOT, ".github", "workflows", "pm-record.yml")
        i_grade, i_pin, i_commit = t.index("name: Grade the frozen cards"), t.index("python3 -I scripts/sharps_v2/pinclose.py"), t.index("name: Commit (append-only)")
        self.assertLess(i_grade, i_pin)
        self.assertLess(i_pin, i_commit)
        step = t[t.rfind("- name:", 0, i_pin):t.index("- name:", i_pin)]
        self.assertIn("if: env.SKIP != '1'", step)                                  # skipped with the rest when there is no holders data yet
        self.assertRegex(step, r'pinclose\.py[^\n]*\\\n[^\n]*\|\| echo "::warning::')     # the command itself falls back to a warning
        self.assertRegex(step, r'unittest tests\.test_pinclose \|\| \{[^}]*::warning::[^}]*exit 0')


if __name__ == "__main__":
    unittest.main()
