"""Unit tests for scripts/pm_sharp_tape.py: book reads, trade filters, watch list, and a simulated cycle with a fake API."""
import concurrent.futures as cf, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import pm_sharp_tape as T  # noqa: E402

GST = 1_800_000_000
F = {"mt": "ml", "line": None, "outs": ["Home", "Away"], "toks": ["tA", "tB"], "gst": GST}


def trade(ts, side="BUY", slug="nba-aaa-bbb-2026-11-19", tx="0x1", oi=0):
    return {"side": side, "slug": slug, "event_slug": slug.split("-spread")[0], "condition_id": "c1", "token_id": "tA" if oi == 0 else "tB",
            "outcome_index": oi, "price": 0.50, "size": 200.0, "timestamp": ts, "transaction_hash": tx}


class Book(unittest.TestCase):
    def test_best_prices_and_the_walk(self):
        b = {"bids": [{"price": "0.40", "size": "10"}, {"price": "0.45", "size": "10"}],
             "asks": [{"price": "0.55", "size": "100"}, {"price": "0.50", "size": "100"}]}     # unsorted, as the feed sends them
        r = T.book_read(b, 100)
        self.assertEqual((r["bid"], r["ask"], r["ask_sz"]), (0.45, 0.50, 100.0))
        self.assertAlmostEqual(r["vw"], 100 / (100 + 50 / 0.55), 3)                           # $50 at .50 then $50 at .55
        self.assertEqual(T.book_read({"asks": [{"price": "0.50", "size": "300"}]}, 100)["vw"], 0.50)   # fits in the best level
        r2 = T.book_read(b, 90)                                                                # 100 sh at .50 = $50, then 40 more dollars at .55
        self.assertAlmostEqual(r2["vw"], 90 / (100 + 40 / 0.55), 3)

    def test_a_thin_book_has_no_walk_price(self):
        r = T.book_read({"bids": [], "asks": [{"price": "0.60", "size": "10"}]}, 100)         # $6 of asks only
        self.assertEqual((r["ask"], r["vw"], r["bid"]), (0.60, None, None))

    def test_missing_or_bad_books_are_null_not_estimated(self):
        for b in (None, {}, "x", {"bids": [{"price": "a"}], "asks": []}):
            self.assertEqual(T.book_read(b), {"bid": None, "ask": None, "ask_sz": None, "vw": None})


class Filters(unittest.TestCase):
    facts = {"nba-aaa-bbb-2026-11-19": {"c1": F}}

    def test_only_pregame_full_game_buys(self):
        self.assertEqual(T.accept(trade(GST - 600), self.facts, 0)[1], None)
        self.assertEqual(T.accept(trade(GST - 600, side="SELL"), self.facts, 0)[1], "not_buy")
        self.assertEqual(T.accept(trade(GST + 5), self.facts, 0)[1], "in_play")
        self.assertEqual(T.accept(trade(GST - 600, slug="nba-aaa-bbb-2026-11-19-points-x"), self.facts, 0)[1], "not_full_game")
        self.assertEqual(T.accept(trade(GST - 600), {}, 0)[1], "no_market")

    def test_full_game_slugs(self):
        for s in ("nba-mem-cle-2026-11-18", "nba-mem-cle-2026-11-18-spread-home-3pt5", "nfl-kc-buf-2026-11-22-total-47pt5"):
            self.assertTrue(T.FULL_GAME.match(s), s)
        for s in ("nba-mem-cle-2026-11-18-lebron-points-27pt5", "cbb-a-b-2026-11-18", "itf-abderr1-debru1-2026-11-18"):
            self.assertFalse(T.FULL_GAME.match(s), s)


class Watch(unittest.TestCase):
    def test_sharp_dull_and_the_most_active_mid(self):
        t = {"wallets": {"s": {"tier": "sharp", "n": 40}, "d": {"tier": "dull", "n": 40}, "m1": {"tier": "mid", "n": 90},
                         "m2": {"tier": "mid", "n": 50}, "m3": {"tier": "mid", "n": 70}, "x": {"tier": "thin", "n": 3}}}
        self.assertEqual(T.watch_list(t, control=2), {"s": "sharp", "d": "dull", "m1": "mid", "m3": "mid"})


class Cycle(unittest.TestCase):
    """A fake feed: one sharp wallet buys 30 seconds before our read; the book and Gamma answer from tables."""

    def run_cycle(self, now_s, trades):
        clock = {"t": now_s}

        def get(url):
            if "/trades?user=" in url:
                return {"data": trades}
            if "/events?slug=" in url:
                return [{"startTime": "2027-01-15T08:00:00Z", "markets": [
                    {"sportsMarketType": "moneyline", "conditionId": "c1", "clobTokenIds": json.dumps(["tA", "tB"]),
                     "outcomes": json.dumps(["Home", "Away"]), "line": None, "gameStartTime": "2027-01-15 08:00:00+00"}]}]
            if "/book?token_id=tA" in url:
                return {"bids": [{"price": "0.49", "size": "50"}], "asks": [{"price": "0.51", "size": "500"}]}
            if "/book?token_id=tB" in url:
                return {"bids": [{"price": "0.48", "size": "50"}], "asks": [{"price": "0.52", "size": "500"}]}
            return None

        d = tempfile.mkdtemp()
        tape = T.Tape(d, {"w1": "sharp"}, get=get, now=lambda: clock["t"], interval=45)
        tape.last["w1"] = 0
        return tape, clock, d

    def test_a_new_buy_is_detected_with_both_books_and_markouts_follow(self):
        gst = T.parse_ts("2027-01-15 08:00:00+00")
        tx = trade(gst - 3600, tx="0xaa")
        tx["slug"] = tx["event_slug"] = "nba-aaa-bbb-2027-01-14"
        tape, clock, d = self.run_cycle(gst - 3570, [tx])
        with cf.ThreadPoolExecutor(2) as pool:
            tape.cycle(pool)
            rows = [r for v in tape.buf.values() for r in v]
            self.assertEqual(len(rows), 1)
            r = rows[0]
            self.assertEqual((r["k"], r["tier"], r["lat"], r["late"], r["ask"], r["bid"], r["opp_ask"]), ("t", "sharp", 30, False, 0.51, 0.49, 0.52))
            tape.cycle(pool)                                                       # the same trade again: not a second row
            self.assertEqual(len([x for v in tape.buf.values() for x in v if x["k"] == "t"]), 1)
            clock["t"] += 61
            tape.cycle(pool)
            marks = [x for v in tape.buf.values() for x in v if x["k"] == "m"]
            self.assertEqual([m["dt"] for m in marks], [60])
        tape.flush()
        files = [os.path.join(dp, f) for dp, _, fs in os.walk(d) for f in fs]
        self.assertEqual(len(files), 1)

    def test_a_trade_read_late_is_kept_but_flagged(self):
        gst = T.parse_ts("2027-01-15 08:00:00+00")
        tx = trade(gst - 3600, tx="0xbb")
        tx["slug"] = tx["event_slug"] = "nba-aaa-bbb-2027-01-14"
        tape, _, _ = self.run_cycle(gst - 3600 + 400, [tx])
        with cf.ThreadPoolExecutor(2) as pool:
            tape.cycle(pool)
        r = [x for v in tape.buf.values() for x in v][0]
        self.assertEqual((r["lat"], r["late"]), (400, True))

    def test_in_play_and_old_trades_write_nothing(self):
        gst = T.parse_ts("2027-01-15 08:00:00+00")
        tx = trade(gst + 60, tx="0xcc")
        tx["slug"] = tx["event_slug"] = "nba-aaa-bbb-2027-01-14"
        tape, _, _ = self.run_cycle(gst + 90, [tx])
        with cf.ThreadPoolExecutor(2) as pool:
            tape.cycle(pool)
        self.assertEqual(sum(len(v) for v in tape.buf.values()), 0)


if __name__ == "__main__":
    unittest.main()
