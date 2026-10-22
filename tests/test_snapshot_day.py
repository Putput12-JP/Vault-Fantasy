import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nba", "scripts"))
import snapshot as S  # noqa: E402


def write(day, name, rows):
    with open(os.path.join(day, name), "w") as f:
        for r in rows:
            f.write((r if isinstance(r, str) else json.dumps(r)) + "\n")


class DayLoadsWithFastPollFiles(unittest.TestCase):
    def test_fast_poll_files_do_not_stop_the_recorder(self):
        root = tempfile.mkdtemp()
        day = os.path.join(root, "snapshots", "2026-10-22")
        os.makedirs(day)
        write(day, "kalshi.jsonl", [{"t": 1, "k": "a", "v": [1]}, {"t": 2, "k": "b", "v": None}])
        # what fast_poll.py writes beside the change logs: none of these have both k and v
        write(day, "fastpoll.jsonl", [{"t": 3, "qok": True, "tok": True, "q": 59, "tr": 0, "lat": None}])
        write(day, "tape_fast.jsonl", [{"t": 3, "id": "x", "usd": 1200}])
        write(day, "fastpm.jsonl", [{"t": 3, "k": "q1", "v": [0.5]}])
        d = S.Day(root, "2026-10-22")
        self.assertEqual(d.last["kalshi"], {"a": [1]})
        self.assertNotIn("fastpm", d.last)

    def test_a_foreign_row_in_a_change_log_is_skipped(self):
        root = tempfile.mkdtemp()
        day = os.path.join(root, "snapshots", "2026-10-22")
        os.makedirs(day)
        write(day, "newlog.jsonl", [{"t": 1, "k": "a", "v": [1]}, {"t": 2, "q": 1}, '{"t": 3, "k": "b", "v"', {"t": 4, "k": "c", "v": [2]}])
        d = S.Day(root, "2026-10-22")
        self.assertEqual(d.last["newlog"], {"a": [1], "c": [2]})


if __name__ == "__main__":
    unittest.main()
