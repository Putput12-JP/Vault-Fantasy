import contextlib, io, json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_ev_history as B  # noqa: E402


def _load(n):
    with open(os.path.join(HERE, n)) as f:
        return json.load(f)


def entry(i):
    return {"key": "g%d|ml|home|" % i, "game": "g%d" % i, "m": "ml", "side": "home", "line": None, "start": i}


class LoadHistory(unittest.TestCase):
    def write(self, d, raw):
        p = os.path.join(d, "h.json")
        with open(p, "wb") as f:
            f.write(raw)
        return p

    def test_keeps_repairable_skips_bare(self):
        rows = [entry(i) for i in range(23)]
        rows.append({"game": "gx", "m": "sp", "side": "away", "line": "-3.0"})
        rows.append({})
        rows.append(7)
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, json.dumps({"entries": rows}).encode())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                got = B.load_history(p)
        self.assertEqual(len(got), 24)
        self.assertIn("gx|sp|away|-3", got)
        self.assertIn("::warning::", buf.getvalue())
        self.assertIn("skipped 2", buf.getvalue())

    def test_moneyline_without_line_key_repairs(self):
        rows = [entry(i) for i in range(23)]
        rows.append({"game": "gm", "m": "ml", "side": "away"})
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, json.dumps({"entries": rows}).encode())
            got = B.load_history(p)
        self.assertEqual(len(got), 24)
        self.assertIn("gm|ml|away|", got)

    def run_cli(self, raw):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, raw)
            r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "build_ev_history.py"),
                                "--history", p], capture_output=True, text=True)
            with open(p, "rb") as f:
                after = f.read()
            self.assertEqual(os.listdir(d), ["h.json"])
            return r, after

    def test_broken_json_exits_untouched(self):
        raw = b'{"entries": [1,'
        r, after = self.run_cli(raw)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("::error::", r.stdout)
        self.assertEqual(after, raw)

    def test_wrong_shape_exits_untouched(self):
        raw = b"[1,2]"
        r, after = self.run_cli(raw)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(after, raw)

    def test_missing_file_fresh_and_empty_output_written(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "none.json")
            r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "build_ev_history.py"),
                                "--history", p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(p) as f:
                self.assertEqual(json.load(f)["entries"], [])


def graded(i):
    return {"type": "behind", "game": "p%d" % i, "m": "ml", "side": "home", "price": -110, "ts": i,
            "fair": 0.5, "result": 1, "start": i}


class Pending(unittest.TestCase):
    SCRIPT = os.path.join(ROOT, "scripts", "build_ev_history.py")

    def cli(self, d, *rows):
        data = os.path.join(d, "data.json")
        with open(data, "w") as f:
            json.dump({"alerts": list(rows)}, f)
        return subprocess.run([sys.executable, "-I", self.SCRIPT, "--history", os.path.join(d, "h.json"),
                               "--data", data], capture_output=True, text=True)

    def test_broken_history_parks_rows_then_next_run_merges(self):
        with tempfile.TemporaryDirectory() as d:
            h = os.path.join(d, "h.json")
            raw = b'{"entries": [1,'
            with open(h, "wb") as f:
                f.write(raw)
            r = self.cli(d, graded(1), graded(2))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("::error::", r.stdout)
            with open(h, "rb") as f:
                self.assertEqual(f.read(), raw)
            pend = os.path.join(d, "h.pending.json")
            with open(pend) as f:
                self.assertEqual(len(json.load(f)["entries"]), 2)
            # a second broken run merges into the same pending file, deduped by key
            r = self.cli(d, graded(2), graded(3))
            self.assertNotEqual(r.returncode, 0)
            with open(pend) as f:
                self.assertEqual(len(json.load(f)["entries"]), 3)
            # repair the history; the next healthy run folds pending in and removes it
            with open(h, "w") as f:
                json.dump({"entries": [entry(9)]}, f)
            r = self.cli(d, graded(4))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(os.path.exists(pend))
            with open(h) as f:
                self.assertEqual(json.load(f)["count"], 5)

    def test_broken_pending_gets_timestamped_name(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "h.json"), "w") as f:
                f.write("nope")
            with open(os.path.join(d, "h.pending.json"), "w") as f:
                f.write("also nope")
            r = self.cli(d, graded(1))
            self.assertNotEqual(r.returncode, 0)
            names = sorted(os.listdir(d))
            stamped = [n for n in names if n.startswith("h.pending.") and n != "h.pending.json"]
            self.assertEqual(len(stamped), 1, names)
            with open(os.path.join(d, "h.pending.json")) as f:
                self.assertEqual(f.read(), "also nope")


class LineKey(unittest.TestCase):
    def test_matches_js(self):
        cases = _load("evln_cases.json")
        exp = _load("evln_expected.json")
        self.assertEqual([B.line_key(c) for c in cases], exp)


if __name__ == "__main__":
    unittest.main()
