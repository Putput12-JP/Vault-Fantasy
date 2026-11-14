"""Unit tests for scripts/scan_pm_holders.py: cadence, change logs, firstSeen, the T-15 keyframe and failure handling."""
import gzip, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import scan_pm_holders as H  # noqa: E402

GST = 1_800_000_000
CUT = GST - 900


def state_with_market(cid="c1", gst=GST, reads=()):
    st = H.State()
    st.apply({"k": "m", "c": cid, "ev": "nba-bos-tor-2027-01-15", "mt": "moneyline", "line": None, "outs": ["Celtics", "Raptors"],
              "tok": ["t0", "t1"], "gst": gst})
    st.apply({"k": "p", "c": cid, "t": 1, "px": [0.6, 0.4]})
    for rt in reads:
        st.apply({"k": "r", "c": cid, "rt": rt, "n": [0, 0], "lim": [False, False]})
    return st


def read(st, cid, groups, rt, limit=H.HOLDER_LIMIT):
    rows, lim = H.diff_read(st, cid, groups, rt, limit)
    for r in rows or []:
        st.apply(r)
    return rows


def R(*rts):
    return [(rt, [False, False]) for rt in rts]


class Cadence(unittest.TestCase):
    def test_tiers(self):
        m = {"gst": GST, "reads": []}
        self.assertEqual(H.due(m, GST - 3 * 86400), "tier")                  # never read
        m["reads"] = R(GST - 40 * 3600)
        self.assertIsNone(H.due(m, GST - 40 * 3600 + 5 * 3600))             # 6h tier, 5h since last read
        self.assertEqual(H.due(m, GST - 40 * 3600 + 6 * 3600 - 600), "tier")   # 10 min of slack for cron jitter
        m["reads"] = R(GST - 10 * 3600)                                       # game day, 10h out: 15-min tier (was hourly)
        self.assertIsNone(H.due(m, GST - 10 * 3600 + 10 * 60))
        self.assertEqual(H.due(m, GST - 10 * 3600 + 15 * 60), "tier")
        m["reads"] = R(GST - 3600)
        self.assertIsNone(H.due(m, GST - 3600 + 10 * 60))                    # 15-min tier, 10 min since
        self.assertEqual(H.due(m, GST - 3600 + 15 * 60), "tier")
        self.assertIsNone(H.due(m, GST - 3600 + 15 * 60, fail_at=GST - 3600 + 14 * 60))   # backing off after a failed read

    def test_freeze_window_and_no_read_after_cut(self):
        m = {"gst": GST, "reads": R(GST - 25 * 60)}
        self.assertEqual(H.due(m, GST - 19 * 60), "freeze")                  # in the window with no read in it
        m["reads"] += R(GST - 19 * 60)
        self.assertIsNone(H.due(m, GST - 17 * 60))                           # 5-min tier, read 2 min ago
        self.assertIsNone(H.due(m, CUT))
        self.assertIsNone(H.due(m, GST + 60))

    def test_next_wake_aims_at_freeze(self):
        st = state_with_market(reads=[GST - 40 * 60])
        self.assertEqual(H.next_wake(st, GST - 39 * 60), GST - 35 * 60)      # 5-min tier comes first
        st = state_with_market(reads=[GST - 21 * 60])
        self.assertEqual(H.next_wake(st, GST - 20 * 60 - 30), GST - 18 * 60)  # no read in the window yet: aim at T-18


class Changes(unittest.TestCase):
    def test_new_unchanged_changed_gone(self):
        st = state_with_market()
        rows = read(st, "c1", {0: {"0xa": (100, "alice"), "0xb": (50, None)}}, 10)
        self.assertEqual(sorted((r["k"], r.get("w")) for r in rows), [("h", "0xa"), ("h", "0xb"), ("n", "0xa"), ("r", None)])
        rows = read(st, "c1", {0: {"0xa": (100, "alice"), "0xb": (70, None)}}, 20)
        self.assertEqual([(r["w"], r["a"]) for r in rows if r["k"] == "h"], [("0xb", 70)])
        rows = read(st, "c1", {0: {"0xa": (100, "alice")}}, 30)
        self.assertEqual([(r["w"], r["a"]) for r in rows if r["k"] == "h"], [("0xb", 0)])

    def test_last_holder_leaving_is_an_exit(self):
        st = state_with_market()
        read(st, "c1", {1: {"0xz": (10, None)}}, 10)
        rows = read(st, "c1", {}, 20)                                       # token group absent = no holders
        self.assertEqual([(r["w"], r["a"]) for r in rows if r["k"] == "h"], [("0xz", 0)])

    def test_no_exit_on_a_token_at_the_page_limit(self):
        st = state_with_market()
        read(st, "c1", {0: {"0xa": (1, None), "0xb": (1, None)}, 1: {"0xq": (1, None)}}, 10, limit=2)
        rows = read(st, "c1", {0: {"0xa": (1, None), "0xc": (5, None)}, 1: {"0xq": (1, None)}}, 20, limit=2)
        self.assertNotIn(("0xb", 0), [(r.get("w"), r.get("a")) for r in rows])
        self.assertEqual(st.h[("c1", 0, "0xb")]["conf"], 10)                 # not confirmed by the capped read
        self.assertEqual(st.h[("c1", 0, "0xa")]["conf"], 20)

    def test_first_seen_window_and_reentry(self):
        st = state_with_market(reads=[5])
        read(st, "c1", {0: {"0xa": (10, None)}}, 10)
        v = st.h[("c1", 0, "0xa")]
        self.assertEqual((v["fs"], v["fs_prev"]), (10, 5))
        read(st, "c1", {}, 20)
        read(st, "c1", {0: {"0xa": (3, None)}}, 30)
        self.assertEqual(st.h[("c1", 0, "0xa")]["fs"], 10)                  # re-entry keeps the first sighting


class Keyframe(unittest.TestCase):
    def test_uses_reads_up_to_cut_and_marks_censored(self):
        st = state_with_market()
        read(st, "c1", {0: {"0xa": (100, None)}, 1: {"0xb": (50, None)}}, CUT - 3000)
        read(st, "c1", {0: {"0xa": (100, None), "0xc": (10, None)}, 1: {"0xb": (50, None), "0xc": (1, None)}}, CUT - 120)
        kf = H.keyframe(st, "nba-bos-tor-2027-01-15", GST, CUT + 30)
        self.assertEqual(kf["mk"]["c1"]["frz_lag"], 120)
        rows = {(r[1], r[2]): r for r in kf["h"]}
        self.assertEqual(rows[(0, "0xa")][4], 60.0)                          # 100 shares x 0.60
        self.assertTrue(rows[(0, "0xa")][7])                                 # held at our first read: censored
        self.assertFalse(rows[(0, "0xc")][7])
        self.assertEqual(kf["both"], ["0xc"])

    def test_no_keyframe_without_a_pre_cut_read(self):
        self.assertIsNone(H.keyframe(state_with_market(), "nba-bos-tor-2027-01-15", GST, CUT + 30))

    def test_written_once_and_keyed_by_start(self):
        with tempfile.TemporaryDirectory() as d:
            st = state_with_market(reads=[CUT - 60])
            self.assertEqual(len(H.write_keyframes(d, "nba", st, CUT + 1)), 1)
            self.assertEqual(H.write_keyframes(d, "nba", st, CUT + 2), [])
            st.apply({"k": "m", "c": "c1", "ev": "nba-bos-tor-2027-01-15", "mt": "moneyline", "line": None,
                      "outs": ["Celtics", "Raptors"], "tok": ["t0", "t1"], "gst": GST + 86400})    # postponed a day
            st.apply({"k": "r", "c": "c1", "rt": GST + 86400 - 1000, "n": [0, 0], "lim": [False, False]})
            got = H.write_keyframes(d, "nba", st, GST + 86400 - 899)
            self.assertTrue(got and got[0].endswith(f"@{GST + 86400}.json"))


class Replay(unittest.TestCase):
    def test_replay_rebuilds_the_live_state(self):
        with tempfile.TemporaryDirectory() as d:
            live = state_with_market()
            log = [{"k": "m", "c": "c1", "ev": "nba-bos-tor-2027-01-15", "mt": "moneyline", "line": None,
                    "outs": ["Celtics", "Raptors"], "tok": ["t0", "t1"], "gst": GST}, {"k": "p", "c": "c1", "t": 1, "px": [0.6, 0.4]}]
            for rt, g in ((CUT - 5000, {0: {"0xa": (1, None), "0xb": (2, None)}}), (CUT - 4000, {0: {"0xa": (1, None), "0xc": (3, None)}})):
                rows, _ = H.diff_read(live, "c1", g, rt, limit=2)
                for r in rows:
                    live.apply(r)
                log += rows
            H.write_log(d, "nba", CUT - 5000, log)
            st, n = H.replay(d, "nba", CUT - 3000)
            self.assertEqual(n, 1)
            self.assertEqual(st.h, live.h)

    def test_log_names_never_collide(self):
        with tempfile.TemporaryDirectory() as d:
            a = H.write_log(d, "nba", 1_800_000_000, [{"k": "cyc"}])
            b = H.write_log(d, "nba", 1_800_000_000, [{"k": "cyc"}])
            self.assertNotEqual(a, b)
            with gzip.open(a, "rt") as f:
                self.assertEqual(json.loads(f.readline()), {"k": "cyc"})


class Failures(unittest.TestCase):
    def test_bad_market_is_isolated_and_late_reads_are_dropped(self):
        st = H.State()
        for i in range(4):
            st.apply({"k": "m", "c": f"c{i}", "ev": "e", "mt": "moneyline", "line": None, "outs": ["A", "B"], "tok": [f"t{i}a", f"t{i}b"],
                      "gst": GST + i})

        class Cli:
            def get(self, url, tries=5):
                if "c2" in url:
                    return None                                              # this market makes the whole batch fail
                return {"data": [], "pagination": {}}
        log, stats = [], {"read": 0, "miss": [], "limit_hit": [], "late": []}
        H.read_holders(Cli(), st, ["c0", "c1", "c2", "c3"], log, stats)
        self.assertEqual((stats["miss"], stats["read"]), (["c2"], 3))


class ReviewFixes(unittest.TestCase):
    def test_thin_read_is_a_miss_not_an_exodus(self):
        st = state_with_market()
        read(st, "c1", {0: {f"0x{i}": (1, None) for i in range(6)}}, 10)
        rows, why = H.diff_read(st, "c1", {}, 20)
        self.assertEqual((rows, why), (None, "thin"))
        self.assertEqual(sum(1 for v in st.h.values() if v["a"] > 0), 6)

    def test_start_moved_earlier_keeps_later_reads_out(self):
        st = state_with_market()
        read(st, "c1", {0: {"0xa": (10, None)}}, GST - 7200)
        read(st, "c1", {0: {"0xa": (10, None), "0xlate": (999, None)}}, GST - 1800)
        new_gst = GST - 3600                                                  # Gamma corrects the start an hour earlier
        st.apply({"k": "m", "c": "c1", "ev": "nba-bos-tor-2027-01-15", "mt": "moneyline", "line": None,
                  "outs": ["Celtics", "Raptors"], "tok": ["t0", "t1"], "gst": new_gst})
        kf = H.keyframe(st, "nba-bos-tor-2027-01-15", new_gst, GST)
        self.assertEqual([r[2] for r in kf["h"]], ["0xa"])
        self.assertEqual(kf["mk"]["c1"]["read_rt"], GST - 7200)
        self.assertEqual(kf["late_reads"], 1)
        self.assertLessEqual(max(r[8] for r in kf["h"]), kf["cut"])          # conf never after the cut

    def test_price_after_cut_stays_out_of_keyframe(self):
        st = state_with_market()                                             # price [0.6, 0.4] at t=1
        read(st, "c1", {0: {"0xa": (100, None)}}, CUT - 60)
        st.apply({"k": "p", "c": "c1", "t": CUT + 30, "px": [0.9, 0.1]})
        kf = H.keyframe(st, "nba-bos-tor-2027-01-15", GST, CUT + 60)
        self.assertEqual((kf["mk"]["c1"]["px"], kf["h"][0][4]), ([0.6, 0.4], 60.0))

    def test_freeze_read_confirms_an_unchanged_price(self):
        st = state_with_market()                                             # price [0.6, 0.4] logged at t=1
        class Cli:
            def get(self, url):
                return {"markets": [{"conditionId": "c1", "gameStartTime": None, "outcomePrices": '["0.6","0.4"]'}]}
        self.assertEqual(H.price_rows(Cli(), st, ["c1"]), [])               # unchanged and not a freeze read: nothing logged
        rows = H.price_rows(Cli(), st, ["c1"], confirm={"c1"})
        self.assertEqual([(r["k"], r["px"]) for r in rows], [("p", [0.6, 0.4])])   # freeze read: logged, stamped now
        for r in rows:
            r["t"] = CUT - 120
            st.apply(r)
        read(st, "c1", {0: {"0xa": (100, None)}}, CUT - 60)
        kf = H.keyframe(st, "nba-bos-tor-2027-01-15", GST, CUT + 60)
        self.assertEqual(kf["mk"]["c1"]["px_t"], CUT - 120)                  # the lock price time is the freeze read, not t=1

    def test_empty_token_list_never_replaces_a_known_one(self):
        st = state_with_market()
        st.apply({"k": "m", "c": "c1", "ev": "nba-bos-tor-2027-01-15", "mt": "moneyline", "line": None, "outs": [], "tok": [],
                  "gst": GST})
        self.assertEqual(st.m["c1"]["tok"], ["t0", "t1"])

    def test_owed_keyframe_written_after_a_long_gap(self):
        with tempfile.TemporaryDirectory() as d:
            live = state_with_market()
            log = [{"k": "m", "c": "c1", "ev": "nba-bos-tor-2027-01-15", "mt": "moneyline", "line": None,
                    "outs": ["Celtics", "Raptors"], "tok": ["t0", "t1"], "gst": GST}]
            rows, _ = H.diff_read(live, "c1", {0: {"0xa": (1, None)}}, CUT - 600)
            log += rows
            H.write_log(d, "nba", CUT - 600, log)
            st, _ = H.replay(d, "nba", GST + 7 * 3600)                        # the next run comes 7h after the start
            self.assertEqual(len(H.write_keyframes(d, "nba", st, GST + 7 * 3600)), 1)

    def test_every_holders_read_failing_is_not_ok(self):
        st = state_with_market(gst=GST)

        class Cli:
            def get(self, url, tries=5):
                return None if "/holders" in url else {"markets": [], "events": []}

            def stats(self):
                return {}
        st.events_at = 10 ** 12
        cyc, _ = H.cycle(Cli(), "/nonexistent", "nba", st, True)
        self.assertFalse(cyc["ok"])


class CardsKick(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self._rh = H.remote_has_head

    def tearDown(self):
        H.remote_has_head = self._rh

    def run_ok(self, cmd, **kw):
        self.calls.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    def run_fail(self, cmd, **kw):
        self.calls.append(cmd)
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "HTTP 403"})()

    def test_dispatches_once_keyframes_are_on_origin(self):
        H.remote_has_head = lambda repo: True
        left = H.kick_cards("r", ["nba/frozen/2026-11-12/x@1.json"], "main", run=self.run_ok)
        self.assertEqual(left, [])
        self.assertEqual(self.calls, [["gh", "workflow", "run", "pm-cards.yml", "--ref", "main"]])

    def test_nothing_new_or_no_ref_never_dispatches(self):
        H.remote_has_head = lambda repo: True
        self.assertEqual(H.kick_cards("r", [], "main", run=self.run_ok), [])
        self.assertEqual(H.kick_cards("r", ["a"], "", run=self.run_ok), ["a"])
        self.assertEqual(self.calls, [])

    def test_waits_until_origin_has_the_keyframes(self):
        H.remote_has_head = lambda repo: False
        self.assertEqual(H.kick_cards("r", ["a"], "main", run=self.run_ok), ["a"])
        self.assertEqual(self.calls, [])

    def test_failed_dispatch_is_kept_for_the_next_push(self):
        H.remote_has_head = lambda repo: True
        self.assertEqual(H.kick_cards("r", ["a"], "main", run=self.run_fail), ["a"])


class MarketIndex(unittest.TestCase):
    """State.hc groups holdings by market so a read walks only its own market's holdings (the replay used to walk every market's)."""

    def two_markets(self):
        st = state_with_market("c1")
        st.apply({"k": "m", "c": "c2", "ev": "nba-lal-mil-2027-01-15", "mt": "moneyline", "line": None, "outs": ["Lakers", "Bucks"],
                  "tok": ["t2", "t3"], "gst": GST})
        read(st, "c1", {0: {"0xa": (10, None)}}, 10)
        read(st, "c2", {0: {"0xa": (5, None), "0xb": (7, None)}}, 11)
        return st

    def test_a_read_confirms_only_its_own_market(self):
        st = self.two_markets()
        st.apply({"k": "r", "c": "c1", "rt": 50, "n": [1, 0], "lim": [False, False]})
        self.assertEqual((st.h[("c1", 0, "0xa")]["conf"], st.h[("c2", 0, "0xa")]["conf"], st.h[("c2", 0, "0xb")]["conf"]), (50, 11, 11))

    def test_index_holds_the_same_holding_dicts_and_follows_prune(self):
        st = self.two_markets()
        self.assertEqual(sum(len(v) for v in st.hc.values()), len(st.h))
        for (c, oi, w), v in st.h.items():
            self.assertIs(st.hc[c][(oi, w)], v)
        read(st, "c1", {}, 60)                                           # a holder leaving zeroes it in place, in both
        self.assertEqual(st.hc["c1"][(0, "0xa")]["a"], 0)
        st.m["c1"]["gst"] = 1                                            # long past: prune drops the market everywhere
        st.prune(GST)
        self.assertNotIn("c1", st.hc)
        self.assertFalse([k for k in st.h if k[0] == "c1"])
        self.assertEqual(sorted(st.hc), ["c2"])


if __name__ == "__main__":
    unittest.main()
