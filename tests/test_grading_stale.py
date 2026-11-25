"""Tests for scripts/grading_stale.py: is the proven-sharps grading stale, so the card build should start pm-record.yml.
Synthetic inputs only; no network, no stored data. A fake `gh` script stands in for GitHub. Run from the repo root:
    python3 -m unittest tests.test_grading_stale
"""
import contextlib, io, json, os, stat, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import grading_stale as GS  # noqa: E402

NOW = 1_800_000_000
MIN, HOUR = 60, 3600


def play(n=1, ago=3 * HOUR, sport="nba", **kw):
    """A shown play of live.json `locked` (or the record's open list) whose game started `ago` seconds before NOW."""
    d = {"key": "%s/frozen/2027-01-15/g%d@%d.json|ml|all|sf" % (sport, n, NOW - ago), "sport": sport, "gst": NOW - ago, "play": "sf", "side": "X"}
    d.update(kw)
    return d


def run(created_ago, status="completed", event="workflow_dispatch"):
    t = NOW - created_ago
    import datetime as dt
    return {"createdAt": dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "status": status, "event": event}


def dec(generated_ago=2 * HOUR, locked=None, open_=None, results=(), runs=()):
    gen = None if generated_ago is None else NOW - generated_ago
    c = GS.shown_candidates(locked if locked is not None else [play()], open_)
    return GS.decide(NOW, gen, c, set(results), list(runs) if runs is not None else None)


class Decision(unittest.TestCase):
    def test_stale_dispatches(self):
        o = dec()
        self.assertTrue(o["stale"] and o["dispatch"])
        self.assertEqual((o["overdue_ungraded"], o["dispatches_6h"], o["active_runs"], o["generated_age_min"]), (1, 0, 0, 120.0))
        self.assertEqual(o["oldest_overdue_hours"], 3.0)

    def test_fresh_record_does_not_dispatch(self):
        o = dec(generated_ago=10 * MIN)
        self.assertFalse(o["stale"] or o["dispatch"])
        self.assertIn("fresh", o["reason"])

    def test_no_frozen_cards(self):
        o = dec(locked=[], open_=[])
        self.assertFalse(o["stale"] or o["dispatch"])
        self.assertEqual(o["frozen_shown_open"], 0)
        self.assertIn("no frozen shown plays", o["reason"])

    def test_ungraded_but_recent(self):
        o = dec(locked=[play(ago=2 * HOUR)])           # started 2 h ago: still inside the grace period
        self.assertFalse(o["stale"] or o["dispatch"])
        self.assertEqual((o["overdue_ungraded"], o["not_yet_overdue"]), (0, 1))

    def test_graded_play_is_not_overdue(self):
        p = play()
        o = dec(locked=[p], results=[p["key"]])
        self.assertFalse(o["stale"])
        self.assertEqual(o["overdue_ungraded"], 0)

    def test_loop_guard(self):
        runs = [run(1 * HOUR), run(2 * HOUR), run(5 * HOUR)]
        o = dec(runs=runs)
        self.assertTrue(o["stale"])
        self.assertFalse(o["dispatch"])
        self.assertEqual(o["dispatches_6h"], 3)
        self.assertIn("3 dispatches", o["reason"])

    def test_loop_guard_two_is_allowed_and_old_ones_do_not_count(self):
        self.assertTrue(dec(runs=[run(1 * HOUR), run(2 * HOUR), run(7 * HOUR), run(30 * HOUR)])["dispatch"])
        self.assertEqual(dec(runs=[run(1 * HOUR), run(2 * HOUR), run(7 * HOUR)])["dispatches_6h"], 2)

    def test_loop_guard_edge_exactly_six_hours_does_not_count(self):
        self.assertEqual(dec(runs=[run(6 * HOUR), run(1 * HOUR), run(2 * HOUR)])["dispatches_6h"], 2)
        self.assertEqual(dec(runs=[run(6 * HOUR - 1), run(1 * HOUR), run(2 * HOUR)])["dispatches_6h"], 3)

    def test_scheduled_runs_are_not_dispatches(self):
        o = dec(runs=[run(1 * HOUR, event="schedule"), run(2 * HOUR, event="schedule"), run(3 * HOUR, event="schedule"), run(4 * HOUR, event="schedule")])
        self.assertTrue(o["dispatch"])
        self.assertEqual(o["dispatches_6h"], 0)

    def test_queued_or_running_run(self):
        for st in ("queued", "in_progress", "waiting", "pending", "requested"):
            o = dec(runs=[run(10 * MIN, status=st, event="schedule")])
            self.assertTrue(o["stale"], st)
            self.assertFalse(o["dispatch"], st)
            self.assertEqual(o["active_runs"], 1)
            self.assertIn("already", o["reason"])
        self.assertTrue(dec(runs=[run(10 * MIN, status="completed", event="schedule")])["dispatch"])

    def test_run_list_unreadable_starts_nothing(self):
        o = dec(runs=None)
        self.assertTrue(o["stale"])
        self.assertFalse(o["dispatch"])
        self.assertIsNone(o["active_runs"])


class Thresholds(unittest.TestCase):
    def test_record_age_exactly_45_minutes_is_fresh_and_one_second_over_is_stale(self):
        self.assertFalse(dec(generated_ago=45 * MIN)["stale"])
        self.assertTrue(dec(generated_ago=45 * MIN + 1)["stale"])
        self.assertFalse(dec(generated_ago=45 * MIN - 1)["stale"])

    def test_play_exactly_2_5_hours_old_is_not_overdue_and_one_second_over_is(self):
        self.assertEqual(dec(locked=[play(ago=int(2.5 * HOUR))])["overdue_ungraded"], 0)
        self.assertEqual(dec(locked=[play(ago=int(2.5 * HOUR) + 1)])["overdue_ungraded"], 1)

    def test_play_older_than_24_hours_is_ignored(self):
        self.assertEqual(dec(locked=[play(ago=24 * HOUR)])["overdue_ungraded"], 1)
        o = dec(locked=[play(ago=24 * HOUR + 1)])
        self.assertEqual(o["overdue_ungraded"], 0)
        self.assertFalse(o["stale"])

    def test_missing_generated_counts_as_stale_when_a_play_is_overdue(self):
        o = dec(generated_ago=None)
        self.assertTrue(o["stale"] and o["dispatch"])
        self.assertIsNone(o["generated_age_min"])
        self.assertIn("no generated time", o["reason"])
        self.assertFalse(dec(generated_ago=None, locked=[])["stale"])      # nothing overdue: still nothing to do

    def test_future_game_is_waiting_not_overdue(self):
        o = dec(locked=[play(ago=-30 * MIN)])
        self.assertEqual((o["overdue_ungraded"], o["not_yet_overdue"]), (0, 1))


class Candidates(unittest.TestCase):
    def test_only_shown_plays_of_the_three_sports(self):
        rows = [play(1), play(2, sport="cfb"), play(3, sport="nfl"), play(4, sport="cbb"), play(5, sport="nhl"),
                dict(play(6), key="nba/frozen/d/g6@1.json|ml|all|lock", play="lock"), dict(play(7), key="nba/frozen/d/g7@1.json|ml|sfx|sf"),
                dict(play(8), play="lock"), dict(play(9), gst="soon"), dict(play(10), gst=True), {"key": 5}, "x", None]
        got = [c["sport"] for c in GS.shown_candidates(rows, None)]
        self.assertEqual(got, ["nba", "nfl", "cbb"])

    def test_key_rule_is_the_record_pages(self):
        ok_key = "nba/frozen/d/g@1.json|ml|all|sf"
        self.assertTrue(GS.is_shown_key(ok_key))
        for bad in ("nba/frozen/d/g@1.json|ml|all|lock", "nba/frozen/d/g@1.json|ml|sfx|sf", "nba/frozen/d/g@1.json|ml|fwd|sf",
                    "nba/frozen/d/g@1.json|ml|all|sf|close", "nba/frozen/d/g@1.json|ml|all|sf|pinclose", "", None, 7):
            self.assertFalse(GS.is_shown_key(bad), bad)

    def test_exit_codes_are_the_ones_the_workflow_reads(self):
        self.assertEqual((GS.EXIT_DISPATCH, GS.EXIT_NONE, GS.EXIT_UNKNOWN), (10, 0, 3))

    def test_deduped_across_the_two_lists(self):
        p = play()
        self.assertEqual(len(GS.shown_candidates([p], [dict(p)])), 1)

    def test_postponed_is_never_overdue(self):
        o = dec(locked=[], open_=[play(postponed=True)])
        self.assertEqual((o["overdue_ungraded"], o["frozen_shown_open"]), (0, 1))
        self.assertFalse(o["stale"])
        self.assertEqual(dec(locked=[], open_=[play(postponed=False)])["overdue_ungraded"], 1)

    def test_open_list_alone_can_make_it_stale(self):
        self.assertTrue(dec(locked=[], open_=[play()])["dispatch"])


class Files(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.td, ignore_errors=True))

    def data(self, generated, open_=(), results=()):
        os.makedirs(os.path.join(self.td, "d", "pm_record", "cards", "nba"), exist_ok=True)
        with open(os.path.join(self.td, "d", "pm_record", "cards_record.json"), "w") as f:
            json.dump({"generated": generated, "open": list(open_)}, f)
        with open(os.path.join(self.td, "d", "pm_record", "cards", "nba", "2027-01.jsonl"), "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")

    def live(self, locked):
        p = os.path.join(self.td, "live.json")
        with open(p, "w") as f:
            json.dump({"locked": locked}, f)
        return p

    def go(self, runs, locked, **kw):
        a = ["--live", self.live(locked), "--data-dir", os.path.join(self.td, "d"), "--now", str(NOW)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = GS.main(a, runs_fn=lambda: runs)
        return rc, json.loads(out.getvalue()), err.getvalue()

    def test_result_row_settles_a_play_and_a_close_or_pinclose_row_does_not(self):
        p = play()
        self.data(NOW - 2 * HOUR, results=[{"kind": "close", "key": p["key"]}, {"kind": "pinclose", "key": p["key"]}])
        rc, o, log = self.go([], [p])
        self.assertEqual((rc, o["overdue_ungraded"]), (GS.EXIT_DISPATCH, 1))
        self.assertIn("DISPATCH", log)
        self.data(NOW - 2 * HOUR, results=[{"kind": "result", "key": p["key"], "status": "void"}])
        rc, o, log = self.go([], [p])
        self.assertEqual((rc, o["overdue_ungraded"]), (GS.EXIT_NONE, 0))
        self.assertIn("no dispatch", log)

    def test_exit_codes(self):
        p = play()
        self.data(NOW - 2 * HOUR)
        self.assertEqual(self.go([], [p])[0], GS.EXIT_DISPATCH)
        self.assertEqual(self.go([run(HOUR)] * 3, [p])[0], GS.EXIT_NONE)
        self.assertEqual(self.go(None, [p])[0], GS.EXIT_UNKNOWN)
        self.data(NOW - 5 * MIN)
        self.assertEqual(self.go([], [p])[0], GS.EXIT_NONE)

    def test_missing_files_do_not_crash(self):
        a = ["--live", os.path.join(self.td, "nope.json"), "--data-dir", os.path.join(self.td, "nodir"), "--now", str(NOW)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = GS.main(a, runs_fn=lambda: [])
        self.assertEqual(rc, GS.EXIT_NONE)
        self.assertEqual(json.loads(out.getvalue())["frozen_shown_open"], 0)

    def test_gh_runs_merges_both_calls_with_a_fake_gh(self):
        gh = os.path.join(self.td, "gh")
        disp, allr = [run(HOUR)], [run(HOUR), run(10 * MIN, status="queued", event="schedule")]
        with open(gh, "w") as f:
            f.write("#!/bin/sh\nif echo \"$*\" | grep -q workflow_dispatch; then echo '%s'; else echo '%s'; fi\n" % (json.dumps(disp), json.dumps(allr)))
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IEXEC)
        log = os.path.join(self.td, "calls.log")
        with open(gh, "a") as f:
            f.write("echo \"$*\" >> '%s'\n" % log)
        r = GS.gh_runs("pm-record.yml", gh)
        calls = open(log).read().splitlines()
        self.assertEqual(calls[0], "run list --workflow pm-record.yml --event workflow_dispatch --limit 20 --json createdAt,status,event")
        self.assertEqual(calls[1], "run list --workflow pm-record.yml --limit 20 --json createdAt,status,event")
        self.assertEqual(len(r), 2)                          # the dispatch run is in both lists and counts once
        bad = os.path.join(self.td, "gh-bad")
        with open(bad, "w") as f:
            f.write("#!/bin/sh\nexit 1\n")
        os.chmod(bad, os.stat(bad).st_mode | stat.S_IEXEC)
        self.assertIsNone(GS.gh_runs("pm-record.yml", bad))
        self.assertIsNone(GS.gh_runs("pm-record.yml", os.path.join(self.td, "no-such-gh")))


if __name__ == "__main__":
    unittest.main()
