import datetime as dt, json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import regrade_prop_clv as R  # noqa: E402
import snapshot_sharp_ledgers as S  # noqa: E402

KICK = 1_800_000_000


def play(i, line=50.5, side="over", status="won", actual=60, price=0.5, fair_src="Pinnacle"):
    return {"id": "p%d" % i, "season": "2026", "week": 6, "pid": str(i), "mkt": "rec_yd", "label": "Receiving yards", "line": line, "side": side,
            "start": KICK, "firstSeen": KICK - 7200, "called": {"p": price, "fair": 0.55, "fairSrc": fair_src, "ev": 0.1},
            "status": status, "actual": actual, "closeFair": 0.55, "clv": 0.1, "units": 1.0 if status == "won" else -1}


def tape_for(i, kal=0.6, nov=0.5, pin=(-110, -110), age=600, line=50.5):
    day = dt.datetime.fromtimestamp(KICK, dt.timezone.utc).strftime("%Y-%m-%d")
    t = KICK - age
    books = {"Kalshi": {"ladder": [[line, kal, 100, 0.01]], "t": t}, "Novig": {"ladder": [[line, nov, 0.02, 100]], "t": t},
             "Pinnacle": {"line": line, "over": pin[0], "under": pin[1], "t": t}}
    return "2026|%d|rec_yd|%s" % (i, day), {"books": books, "frozen": True}


def _dump(path, doc):
    with open(path, 'w') as f:
        json.dump(doc, f)


def _read(path):
    with open(path) as f:
        return f.read()


class Regrade(unittest.TestCase):
    def test_exchange_close_is_mean_of_ladders_at_the_exact_strike(self):
        k, e = tape_for(1, kal=0.6, nov=0.5)
        r = R.refs(e, 50.5, KICK, 3 * 3600)
        self.assertAlmostEqual(r["Exchange"], 0.55)
        self.assertAlmostEqual(r["Pinnacle"], 0.5)
        self.assertAlmostEqual(r["Sharp3"], (0.6 + 0.5 + 0.5) / 3)

    def test_other_line_and_stale_reads_are_dropped(self):
        k, e = tape_for(1)
        self.assertEqual(R.refs(e, 51.5, KICK, 3 * 3600), {})
        k, e = tape_for(1, age=4 * 3600)
        self.assertEqual(R.refs(e, 50.5, KICK, 3 * 3600), {})

    def test_read_at_or_after_kickoff_is_not_a_close(self):
        k, e = tape_for(1, age=0)
        self.assertEqual(R.refs(e, 50.5, KICK, 3 * 3600), {})

    def test_under_uses_the_complement_and_clv_is_against_the_price(self):
        k, e = tape_for(1, kal=0.6, nov=0.6)
        row = R.regrade({"p1": play(1, side="under", status="lost", actual=60, price=0.45)}, {k: e}, 3 * 3600)[0]
        self.assertAlmostEqual(R.clv_of(row, "Exchange"), 0.4 / 0.45 - 1)

    def test_pushes_and_calls_without_a_tape_are_dropped(self):
        k, e = tape_for(1)
        rows = R.regrade({"p1": play(1, status="push", actual=50.5), "p2": play(2)}, {k: e}, 3 * 3600)
        self.assertEqual(rows, [])

    def test_write_back_sets_close_and_stamps_open_calls_without_touching_other_fields(self):
        k1, e1 = tape_for(1, kal=0.6, nov=0.6)
        k2, e2 = tape_for(2, kal=0.4, nov=0.4)
        done = play(1)
        openp = play(2, status="open", actual=None)
        openp["start"] = KICK + 7200                       # not started yet
        e2["books"] = {b: dict(v, t=KICK + 7200 - 600) for b, v in e2["books"].items()}
        k2 = "2026|2|rec_yd|" + dt.datetime.fromtimestamp(KICK + 7200, dt.timezone.utc).strftime("%Y-%m-%d")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "prop_plays.json")
            _dump(path, {"plays": {"p1": done, "p2": openp}, "legs": {"x": 1}})
            c, s = R.write_back(path, {k1: e1, k2: e2}, 3 * 3600, KICK + 3600)
            out = json.loads(_read(path))
        self.assertEqual((c, s), (1, 1))
        self.assertAlmostEqual(out["plays"]["p1"]["clvX"], 0.6 / 0.5 - 1, places=3)
        self.assertEqual(out["plays"]["p1"]["clv"], 0.1)                      # the old field is untouched
        self.assertIn("atCall", out["plays"]["p2"])
        self.assertNotIn("clvX", out["plays"]["p2"])
        self.assertEqual(out["legs"], {"x": 1})


class Snapshot(unittest.TestCase):
    def prev(self):
        return {"plays": {"a": {"status": "won"}, "b": {"status": "open"}}}

    def test_superset_is_allowed_and_open_can_settle(self):
        new = {"plays": {"a": {"status": "won"}, "b": {"status": "lost"}, "c": {"status": "open"}}}
        self.assertEqual(S.check("prop_plays.json", self.prev(), new, dt.date(2026, 10, 18)), [])

    def test_missing_id_and_reopened_row_are_refused(self):
        self.assertTrue(S.check("prop_plays.json", self.prev(), {"plays": {"b": {"status": "open"}}}, dt.date(2026, 10, 18)))
        self.assertTrue(S.check("prop_plays.json", self.prev(), {"plays": {"a": {"status": "open"}, "b": {"status": "open"}}}, dt.date(2026, 10, 18)))

    def test_old_tape_keys_may_be_pruned(self):
        old = {"props": {"2025|1|rec|2025-01-01": {"frozen": True}, "2026|1|rec|2026-10-10": {"frozen": True}}}
        new = {"props": {"2026|1|rec|2026-10-10": {"frozen": True}}}
        self.assertEqual(S.check("prop_close_tape.json", old, new, dt.date(2026, 10, 18)), [])
        self.assertTrue(S.check("prop_close_tape.json", {"props": {"2026|1|rec|2026-10-10": {"frozen": True}}}, {"props": {}}, dt.date(2026, 10, 18)))

    def test_picks_ledger_ids_and_regression(self):
        a = {"picks": [{"game": "g", "m": "ml", "side": "home", "result": 1}], "sharpContext": []}
        b = {"picks": [{"game": "g", "m": "ml", "side": "home", "result": None}], "sharpContext": []}
        self.assertTrue(S.check("picks_ledger.json", a, b, dt.date(2026, 10, 18)))

    def test_cli_refuses_and_leaves_previous_snapshot_alone(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dest:
            _dump(os.path.join(src, "prop_plays.json"), {"plays": {"b": {"status": "open"}}})
            _dump(os.path.join(dest, "prop_plays.json"), {"plays": {"a": {"status": "won"}, "b": {"status": "open"}}})
            before = _read(os.path.join(dest, "prop_plays.json"))
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "snapshot_sharp_ledgers.py"), "--src", src, "--dest", dest], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(_read(os.path.join(dest, "prop_plays.json")), before)


if __name__ == "__main__":
    unittest.main()
