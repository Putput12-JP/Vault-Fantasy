import json, os, sys, tempfile, unittest, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import follow_ledger as F  # noqa: E402

TIP = F.FREEZE_T + 20 * 3600
W = {"sharp": {"0xS": "nba"}, "dull": {"0xD"}, "generated": "2026-10-01T00:00:00+00:00"}


def write(d, name, rows):
    with open(os.path.join(d, name), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def build(tape, quotes, polls, now):
    root = tempfile.mkdtemp()
    day = os.path.join(root, "snapshots", dt.datetime.fromtimestamp(now, F.ET).date().isoformat())
    os.makedirs(day)
    write(day, "meta.jsonl", [{"k": "m1", "src": "polymarket", "event": "nba-a-b", "type": "moneyline", "line": None, "start": TIP}])
    write(day, "tape.jsonl", tape)
    write(day, "polymarket.jsonl", [{"t": t, "k": "m1", "v": v} for t, v in quotes])
    write(day, "polls.jsonl", [{"t": t, "src": "polymarket", "ok": True} for t in polls])
    return root, day


def tk(t, w="0xS", o=0, usd=2000, px=0.50):
    return {"t": t, "s": "pm", "k": "m1", "o": o, "usd": usd, "px": px, "w": w, "who": "x", "id": f"{t}{w}{o}"}


class FollowLedger(unittest.TestCase):
    def test_taker_maker_and_grade(self):
        T = F.FREEZE_T + 3600
        quotes = [(T - 60, [0.49, 0.51, 0.5]), (T + 100, [0.52, 0.54, 0.53]), (T + 700, [0.50, 0.50, 0.50]), (TIP - 600, [0.58, 0.60, 0.59])]
        polls = [T - 60, T + 130, T + 330, T + 700, T + 1000, T + 3700, TIP - 300]
        now = TIP + F.GRADE_AFTER_S + 1
        root, day = build([tk(T)], quotes, polls, now)
        self.assertEqual(F.run(root, now, W)["graded"], 1)
        ev = list(json.load(open(os.path.join(day, F.FILE))).values())[0]
        self.assertEqual(ev["cohort"], "sharp"); self.assertFalse(ev["bf"])
        self.assertEqual(ev["f"]["tk2"], [0.54, 130]); self.assertEqual(ev["f"]["tk5"], [0.54, 330])   # quote in force at the poll
        self.assertEqual(ev["f"]["mk"], [0.50, 700])                                                      # ask fell to the wallet's price
        self.assertEqual(ev["close"], 0.59)
        self.assertAlmostEqual(ev["res"]["tk2"]["clv"], round(0.59 / 0.54 - 1, 4))
        self.assertAlmostEqual(ev["res"]["mk"]["val"], round(0.59 / 0.50 - 1, 4))

    def test_unfilled_maker_counts_zero_and_stale_poll_skipped(self):
        T = F.FREEZE_T + 3600
        quotes = [(T + 10, [0.55, 0.57, 0.56]), (TIP - 600, [0.60, 0.62, 0.61])]
        polls = [T + 20, TIP - 200]                    # next poll is hours later: tk5 .. tk60 have no fresh quote
        now = TIP + F.GRADE_AFTER_S + 1
        root, day = build([tk(T)], quotes, polls, now)
        F.run(root, now, W)
        ev = list(json.load(open(os.path.join(day, F.FILE))).values())[0]
        self.assertNotIn("tk5", ev["f"]); self.assertNotIn("tk60", ev["f"])
        self.assertIsNone(ev["f"]["mk"]); self.assertEqual(ev["res"]["mk"], {"fill": 0, "clv": None, "val": 0.0})

    def test_first_ticket_only_cohorts_hedge_backfill_and_no_close(self):
        T = F.FREEZE_T - 5000
        tape = [tk(T - 50, usd=400), tk(T, w="0xD"), tk(T + 10, w="0xD", o=1), tk(T + 20, w="0xD", o=1, usd=3000), tk(T + 30, w="0xZ"), tk(T + 40), tk(T + 60, w="0xS2", usd=999)]
        now = TIP + F.GRADE_AFTER_S + 1
        root, day = build(tape, [(T, [0.5, 0.52, 0.5])], [T + 5], now)       # no poll near tip: nothing can be graded
        r = F.run(root, now, W)
        rows = json.load(open(os.path.join(day, F.FILE))).values()
        self.assertEqual(r["graded"], 0)
        by = {(e["w"], e["o"]): e for e in rows}
        self.assertEqual(set(by), {("0xD", 0), ("0xD", 1), ("0xZ", 0), ("0xS", 0)})   # $400 and $999 tickets are not events
        self.assertEqual(by[("0xD", 0)]["cohort"], "dull"); self.assertEqual(by[("0xZ", 0)]["cohort"], "other")
        self.assertTrue(by[("0xD", 1)]["hedge"]); self.assertFalse(by[("0xD", 0)]["hedge"])
        self.assertTrue(all(e["bf"] for e in rows))                               # before the freeze

    def test_rerun_keeps_first_cohort_and_is_idempotent(self):
        T = F.FREEZE_T + 3600
        now = T + 1000
        root, day = build([tk(T)], [(T + 5, [0.5, 0.52, 0.5])], [T + 130], now)
        F.run(root, now, W)
        W2 = {"sharp": {}, "dull": set(), "generated": W["generated"]}
        self.assertEqual(F.run(root, now + 60, W2)["new"], 0)
        ev = list(json.load(open(os.path.join(day, F.FILE))).values())[0]
        self.assertEqual(ev["cohort"], "sharp")

    def test_build_board_for_the_pages(self):
        T = F.FREEZE_T + 3600
        now = T + 600
        root, day = build([tk(T), tk(T + 5, w="0xD", o=1, px=0.5)], [(T + 5, [0.49, 0.51, 0.5]), (T + 400, [0.55, 0.56, 0.55])], [T + 130, T + 400], now)
        W2 = {"sharp": {"0xS": "nba"}, "dull": set(), "generated": "2026-10-01T00:00:00+00:00"}
        F.run(root, now, W2)
        data = tempfile.mkdtemp()
        rank = {"generated": "2026-10-22T00:00:00+00:00", "counts": {"proven": 1}, "rho": {"value": 0.5, "ci90": [0, 0.9], "pairs": 9}, "params": {"nba": {"tau2": 1e-4, "wallets": 5}},
                "wallets": {"0xS": {"raw": {"nba": [3, 0.02]}, "post": 0.01, "sd": 0.005, "p": 0.97, "tier": "proven", "old": None},
                            "0xD": {"raw": {"nba": [9, -0.02]}, "post": -0.02, "sd": 0.004, "p": 0.01, "tier": "dull", "old": "dull"}}}
        json.dump(rank, open(os.path.join(data, "pm_wallet_rank.json"), "w"))
        old, F.REPO_DATA = F.REPO_DATA, data
        try:
            b = F.build_board(root, now)
        finally:
            F.REPO_DATA = old
        self.assertEqual(len(b["games"]), 1)
        it = b["games"][0]["items"]
        self.assertEqual({(i["o"], i["wallets"][0]["tier"]) for i in it}, {(0, "proven"), (1, "dull")})
        s = next(i for i in it if i["o"] == 0)
        self.assertEqual(s["now"], {"t": T + 400, "bid": 0.55, "ask": 0.56})
        self.assertEqual(next(i for i in it if i["o"] == 1)["now"]["ask"], 0.45)               # the other outcome is priced off the same book
        self.assertEqual([w["w"] for w in b["wallets"]], ["0xS", "0xD"]); self.assertEqual(b["rec"]["sharp_fwd"], 1)
        F.REPO_DATA = os.path.join(data, "nowhere")
        try:
            self.assertIsNone(F.build_board(root, now))                                        # no ranking file: the page shows its banner
        finally:
            F.REPO_DATA = old


if __name__ == "__main__":
    unittest.main()
