import datetime as dt, json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import snapshot_sharp_ledgers as S  # noqa: E402

TODAY = dt.date(2026, 10, 18)


def play(status="open", price=0.5, first_seen=1000):
    return {"id": "x", "kind": "prop", "start": 5000, "firstSeen": first_seen, "first": {"price": {"p": price, "book": "FanDuel"}, "refs": [{"n": "Pinnacle", "p": 0.55}]}, "status": status}


class V2Ledger(unittest.TestCase):
    def test_v2_plays_is_one_of_the_snapshotted_ledgers(self):
        self.assertIn("v2_plays.json", S.LEDGERS)

    def test_a_play_can_settle_and_new_plays_can_arrive(self):
        old = {"plays": {"a": play(), "b": play()}}
        new = {"plays": {"a": dict(play(), status="won", units=0.9), "b": play(), "c": play()}}
        self.assertEqual(S.check("v2_plays.json", old, new, TODAY), [])

    def test_a_play_cannot_vanish_or_reopen(self):
        self.assertTrue(S.check("v2_plays.json", {"plays": {"a": play()}}, {"plays": {}}, TODAY))
        self.assertTrue(S.check("v2_plays.json", {"plays": {"a": play("won")}}, {"plays": {"a": play("open")}}, TODAY))

    def test_the_first_sight_record_is_frozen(self):
        old = {"plays": {"a": play()}}
        self.assertTrue(S.check("v2_plays.json", old, {"plays": {"a": play(price=0.45)}}, TODAY), "price")
        self.assertTrue(S.check("v2_plays.json", old, {"plays": {"a": play(first_seen=2000)}}, TODAY), "time")
        later = dict(play(), status="won", units=1.0, close={"p": 0.56}, clv=0.12)
        self.assertEqual(S.check("v2_plays.json", old, {"plays": {"a": later}}, TODAY), [], "outcome fields may change")

    def test_an_empty_v2_ledger_is_written_but_an_empty_prop_ledger_is_refused(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dest:
            for n, d in (("prop_plays.json", {"plays": {"a": {"status": "open"}}}), ("v2_plays.json", {"plays": {}}), ("data.json", {"picks": [{"game": "g", "m": "ml", "side": "home", "result": None}]}),
                         ("ev_alert_history.json", {"entries": [{"key": "k", "result": None}]}), ("prop_close_tape.json", {"props": {"2026|1|rec|2026-10-10": {"frozen": True}}})):
                with open(os.path.join(src, n), "w") as f:
                    json.dump(d, f)
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "snapshot_sharp_ledgers.py"), "--src", src, "--dest", dest], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(os.path.exists(os.path.join(dest, "v2_plays.json")))
            with open(os.path.join(src, "prop_plays.json"), "w") as f:
                json.dump({"plays": {}}, f)
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "snapshot_sharp_ledgers.py"), "--src", src, "--dest", dest], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)

    def test_a_missing_v2_file_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dest:
            for n, d in (("prop_plays.json", {"plays": {"a": {"status": "open"}}}), ("data.json", {"picks": [{"game": "g", "m": "ml", "side": "home", "result": None}]}),
                         ("ev_alert_history.json", {"entries": [{"key": "k", "result": None}]}), ("prop_close_tape.json", {"props": {"2026|1|rec|2026-10-10": {"frozen": True}}})):
                with open(os.path.join(src, n), "w") as f:
                    json.dump(d, f)
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "snapshot_sharp_ledgers.py"), "--src", src, "--dest", dest], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(os.path.exists(os.path.join(dest, "v2_plays.json")))


if __name__ == "__main__":
    unittest.main()
