"""Unit tests for scripts/build_pm_ledger.py: the look-ahead and grading rules the side cards rely on."""
import os, sys, unittest, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import build_pm_ledger as L  # noqa: E402

GST = 1_800_000_000                  # game start
CUT = GST - L.CUTOFF_SEC


def fact(final=(1.0, 0.0), mt="moneyline", closed_at=GST + 4 * 3600):
    return {"slug": "nba-bos-tor-2026-11-11", "mt": mt, "line": None, "outs": ["Celtics", "Raptors"], "gst": GST,
            "closed_at": closed_at, "final": list(final) if final else None}


def buy(ts, oi, size, price, typ="TRADE", side="BUY"):
    return {"timestamp": ts, "type": typ, "side": side, "size": size, "usdc_size": size * price, "price": price,
            "outcome_index": oi, "transaction_hash": f"0x{ts}{oi}{side}"}


class Holding(unittest.TestCase):
    def test_average_cost_after_partial_sell(self):
        h = L.holding_at([buy(CUT - 300, 0, 100, .40), buy(CUT - 200, 0, 100, .60), buy(CUT - 100, 0, 50, .70, side="SELL")], CUT)
        self.assertAlmostEqual(h[0]["sh"], 150)
        self.assertAlmostEqual(h[0]["cost"], 75)            # avg 0.50 kept on the shares still held
        self.assertAlmostEqual(h[0]["exited"], 50)

    def test_fills_after_cutoff_are_ignored(self):
        h = L.holding_at([buy(CUT - 10, 0, 100, .5), buy(CUT, 0, 900, .5), buy(GST + 60, 0, 100, .5, side="SELL")], CUT)
        self.assertAlmostEqual(h[0]["sh"], 100)
        self.assertAlmostEqual(h[0]["post"], 1000)

    def test_split_mints_both_sides_at_half(self):
        h = L.holding_at([{"timestamp": CUT - 50, "type": "SPLIT", "size": 10}], CUT)
        self.assertAlmostEqual(h[0]["cost"], 5)
        self.assertAlmostEqual(h[1]["sh"], 10)

    def test_conversion_flags(self):
        self.assertTrue(L.holding_at([{"timestamp": 1, "type": "CONVERSION", "size": 5}], CUT).get("_conv"))


class Grading(unittest.TestCase):
    def test_win_graded_against_resolution(self):
        rows, why = L.bet_rows("0xw", "0xc", fact(), [buy(CUT - 60, 0, 100, .6)], first_seen_ts=CUT - 86400)
        self.assertIsNone(why)
        r = rows[0]
        self.assertEqual((r["res"], r["stake"], r["pnl"], r["src"]), ("win", 60.0, 40.0, "forward"))

    def test_settled_at_is_market_close_not_wallet_last_trade(self):
        rows, _ = L.bet_rows("0xw", "0xc", fact(), [buy(CUT - 60, 0, 100, .6)], None)
        self.assertEqual(rows[0]["settled_at"], GST + 4 * 3600)
        self.assertGreater(rows[0]["settled_at"], rows[0]["last"])

    def test_unresolved_market_writes_nothing(self):
        self.assertEqual(L.bet_rows("0xw", "0xc", fact(final=None), [buy(CUT - 60, 0, 100, .6)], None), ([], "unresolved"))

    def test_exit_before_cutoff_is_not_a_bet(self):
        rows, why = L.bet_rows("0xw", "0xc", fact(), [buy(CUT - 600, 0, 100, .6), buy(CUT - 60, 0, 100, .7, side="SELL")], None)
        self.assertEqual((rows, why), ([], "exited_or_no_pretip"))

    def test_bought_only_in_play_is_not_a_bet(self):
        self.assertEqual(L.bet_rows("0xw", "0xc", fact(), [buy(GST + 60, 1, 100, .3)], None)[1], "exited_or_no_pretip")

    def test_push_and_hedge(self):
        rows, _ = L.bet_rows("0xw", "0xc", fact(final=(.5, .5), mt="spreads"), [buy(CUT - 9, 0, 10, .5), buy(CUT - 8, 1, 30, .5)], None)
        self.assertEqual([r["res"] for r in rows], ["push", "push"])
        self.assertTrue(all(r["hedged"] for r in rows))

    def test_wallet_chosen_after_the_game_is_backfill(self):
        rows, _ = L.bet_rows("0xw", "0xc", fact(), [buy(CUT - 60, 1, 100, .4)], first_seen_ts=GST + 86400)
        self.assertEqual((rows[0]["src"], rows[0]["res"]), ("backfill", "loss"))

    def test_props_are_skipped(self):
        self.assertEqual(L.bet_rows("0xw", "0xc", fact(mt="points"), [], None), ([], "not_full_game"))


class Plumbing(unittest.TestCase):
    def test_merge_never_rewrites_and_flags_conflict(self):
        old = {"k": {"res": "win", "stake": 60.0, "settled_at": 5}}
        added, conflicts = L.merge_rows(old, {"k": {"res": "loss", "stake": 60.0, "settled_at": 5},
                                              "j": {"res": "win", "stake": 1.0, "settled_at": 6}})
        self.assertEqual((list(added), conflicts), (["j"], ["k"]))

    def test_dedupe_redeemable_vs_lost_keeps_both_outcomes(self):
        rows = [{"condition_id": "c", "outcome_index": 0}, {"condition_id": "c", "outcome_index": 0},
                {"condition_id": "c", "outcome_index": 1}]
        self.assertEqual(len(L.dedupe_positions(rows)), 2)

    def test_market_fact_needs_closed_and_resolved(self):
        m = {"slug": "nba-x", "sportsMarketType": "moneyline", "outcomes": '["A","B"]', "outcomePrices": '["1","0"]',
             "gameStartTime": "2026-06-14 00:30:00+00", "closedTime": "2026-06-14 03:47:30+00", "closed": True,
             "umaResolutionStatus": "resolved"}
        f = L.market_fact(m)
        self.assertEqual((f["final"], f["gst"], f["closed_at"] - f["gst"]), ([1.0, 0.0], 1781397000, 11850))
        self.assertIsNone(L.market_fact(dict(m, umaResolutionStatus="proposed"))["final"])
        self.assertIsNone(L.market_fact(dict(m, outcomePrices='["0.62","0.38"]'))["final"])


class Ordering(unittest.TestCase):
    def test_same_block_buy_then_sell_nets_flat(self):
        f = [dict(buy(CUT - 600, 0, 100, .5), transaction_hash="0xff"), dict(buy(CUT - 600, 0, 100, .55, side="SELL"), transaction_hash="0x01")]
        self.assertEqual(L.bet_rows("0xw", "0xc", fact(), f, None)[1], "exited_or_no_pretip")

    def test_conversion_after_cutoff_keeps_the_bet(self):
        f = [buy(CUT - 60, 0, 100, .6), {"timestamp": GST + 60, "type": "CONVERSION", "size": 5}]
        rows, why = L.bet_rows("0xw", "0xc", fact(), f, None)
        self.assertIsNone(why)
        self.assertEqual(len(rows), 1)

    def test_split_rows_are_flagged(self):
        f = [{"timestamp": CUT - 60, "type": "SPLIT", "size": 100}, buy(CUT - 50, 1, 100, .4, side="SELL")]
        rows, _ = L.bet_rows("0xw", "0xc", fact(), f, None)
        self.assertEqual((len(rows), rows[0]["split"]), (1, True))


class FakeClient:
    """Routes v2 / Gamma URLs to canned answers. `gamma_down` makes Gamma fail; `pos_pages` is a list of position pages."""
    def __init__(self, pos_pages=None, fills=None, gamma=None, gamma_down=False, act_page_cap_for=()):
        self.pos_pages, self.fills, self.gamma = pos_pages or [[]], fills or {}, gamma or {}
        self.gamma_down, self.cap_for, self.calls = gamma_down, set(act_page_cap_for), []

    def get(self, url, tries=5):
        u = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(u.query)
        self.calls.append(u.path)
        if u.path.endswith("/positions"):
            if q.get("status") == ["CLOSED"]:
                return {"data": [], "pagination": {}}
            i = int(q.get("cursor", ["0"])[0])
            more = i + 1 < len(self.pos_pages)
            return {"data": self.pos_pages[i], "pagination": {"has_more": more, "next_cursor": str(i + 1) if more else None}}
        if u.path.endswith("/activity"):
            cids = q["condition"][0].split(",")
            rows = [dict(x, condition_id=c) for c in cids for x in self.fills.get(c, [])]
            if set(cids) & self.cap_for:            # pretend the feed never ends
                return {"data": rows, "pagination": {"has_more": True, "next_cursor": "x"}}
            return {"data": rows, "pagination": {}}
        if u.path.endswith("/markets/keyset"):
            if self.gamma_down:
                return None
            want = q.get("condition_ids", [])
            closed = q["closed"][0] == "true"
            return {"markets": [m for c, m in self.gamma.items() if c in want and bool(m["closed"]) == closed]}
        raise AssertionError(url)


def gamma_market(cid, gst_iso="2026-06-14 00:30:00+00", resolved=True):
    return {"conditionId": cid, "slug": "nba-nyk-sas-2026-06-13", "sportsMarketType": "moneyline", "outcomes": '["A","B"]',
            "outcomePrices": '["1","0"]' if resolved else '["0.6","0.4"]', "gameStartTime": gst_iso,
            "closedTime": "2026-06-14 03:47:30+00" if resolved else None, "closed": resolved,
            "umaResolutionStatus": "resolved" if resolved else ""}


GST2 = 1781397000
NOW = GST2 + 86400


def pos(cid, ts=GST2 - 3600):
    return {"condition_id": cid, "outcome_index": 0, "slug": "nba-nyk-sas-2026-06-13", "last_event_at": ts}


class Args:
    sports, max_pages = ["nba"], 3


class Sync(unittest.TestCase):
    def run_sync(self, cli, st=None, pend=None, markets=None, now=NOW):
        st, pend, markets, notes = st if st is not None else {}, pend if pend is not None else {}, markets if markets is not None else {}, {}
        rows = L.sync_wallet(cli, "0xw", Args, st, markets, pend, set(), GST2 - 86400 * 9, now,
                             lambda k: notes.__setitem__(k, notes.get(k, 0) + 1))
        return rows, st, pend, markets, notes

    def test_grades_a_resolved_bet(self):
        cli = FakeClient([[pos("c1")]], {"c1": [buy(GST2 - 3600, 0, 100, .6)]}, {"c1": gamma_market("c1")})
        rows, *_ = self.run_sync(cli)
        self.assertEqual([(r["res"], r["stake"]) for r in rows], [("win", 60.0)])

    def test_gamma_outage_keeps_the_bet_pending(self):
        cli = FakeClient([[pos("c1")]], {"c1": [buy(GST2 - 3600, 0, 100, .6)]}, {"c1": gamma_market("c1")}, gamma_down=True)
        with self.assertRaises(L.PMDataError):
            self.run_sync(cli)
        st, pend = {}, {}
        try:
            self.run_sync(cli, st, pend)
        except L.PMDataError:
            pass
        cli.gamma_down = False
        rows, *_ = self.run_sync(cli, st, pend)
        self.assertEqual(len(rows), 1)

    def test_capped_activity_never_grades_partial_fills(self):
        cli = FakeClient([[pos("c1")]], {"c1": [buy(GST2 - 3600, 0, 100, .6)]}, {"c1": gamma_market("c1")}, act_page_cap_for={"c1"})
        rows, _, pend, _, notes = self.run_sync(cli)
        self.assertEqual(rows, [])
        self.assertEqual(notes.get("too_many_fills"), 1)

    def test_fills_wait_for_cutoff_to_settle(self):
        cli = FakeClient([[pos("c1")]], {"c1": [buy(GST2 - 3600, 0, 100, .6)]}, {"c1": gamma_market("c1")})
        rows, _, pend, *_ = self.run_sync(cli, now=GST2 - L.CUTOFF_SEC + 60)
        self.assertEqual(rows, [])
        self.assertIsNone(pend["0xw"]["c1"]["fills"])

    def test_moved_game_start_refetches_fills(self):
        cli = FakeClient([[pos("c1")]], {"c1": [buy(GST2 - 3600, 0, 100, .6)]}, {"c1": gamma_market("c1", resolved=False)})
        _, st, pend, markets, _ = self.run_sync(cli)
        self.assertIsNotNone(pend["0xw"]["c1"]["fills"])
        # game postponed a day; the wallet sold out before the new start
        cli.gamma["c1"] = gamma_market("c1", gst_iso="2026-06-15 00:30:00+00")
        cli.fills["c1"].append(buy(GST2 + 3600, 0, 100, .7, side="SELL"))
        markets.pop("c1")
        rows, *_ = self.run_sync(cli, st, pend, markets, now=NOW + 2 * 86400)
        self.assertEqual(rows, [])

    def test_capped_newest_first_walk_leaves_a_backlog_then_resumes(self):
        class Stop(FakeClient):
            stop = True
            def get(self, url, tries=5):
                if self.stop and "/positions" in url and "status=OPEN" in url and "cursor=1" in url:
                    raise L.Budget("max_req")
                return super().get(url, tries)
        cli = Stop([[pos("c2", ts=200)], [pos("c1", ts=100)]], {}, {})   # newest first, as the API serves it
        st, pend = {}, {}
        with self.assertRaises(L.Budget):
            self.run_sync(cli, st, pend)
        b = st["0xw"]["b_OPEN"]
        self.assertEqual((b["hw"], b["lo"], b["hi"]), (200, 1, 200))     # newer than 200 read; [1, 200] still owed
        self.assertIn("c2", pend["0xw"])                                  # read before the stop, kept
        cli.stop = False
        self.run_sync(cli, st, pend)
        self.assertIn("c1", pend["0xw"])                                  # the backlog read found the older position
        self.assertNotIn("hi", st["0xw"]["b_OPEN"])

class Discovery(unittest.TestCase):
    def test_fat_ticket_valued_at_current_price(self):
        now = 1_800_000_000
        ev = [{"markets": [{"conditionId": "c1", "sportsMarketType": "moneyline", "gameStartTime": "2027-01-15 12:00:00+00",
                            "outcomes": '["A","B"]', "outcomePrices": '["0.4","0.6"]', "clobTokenIds": '["t0","t1"]'},
                           {"conditionId": "c2", "sportsMarketType": "points", "gameStartTime": "2027-01-15 12:00:00+00",
                            "outcomes": '["Y","N"]', "outcomePrices": '["0.5","0.5"]', "clobTokenIds": '["p0","p1"]'}]}]
        gst = L.parse_ts("2027-01-15 12:00:00+00")
        page = [{"token_id": "t0", "holders": [{"proxy_wallet": "0xA", "amount": 6000, "token_id": "t0"},
                                               {"proxy_wallet": "0xB", "amount": 4000, "token_id": "t0"},
                                               {"proxy_wallet": "0xC", "amount": 3000, "token_id": "t0"}]},
                {"token_id": "t1", "holders": [{"proxy_wallet": "0xC", "amount": 1000, "token_id": "t1"},
                                               {"proxy_wallet": "0xE", "amount": 5000, "token_id": "t1"},
                                               {"proxy_wallet": "0xA", "amount": 10, "token_id": "t1"}]},
                {"token_id": "p0", "holders": [{"proxy_wallet": "0xD", "amount": 99999, "token_id": "p0"}]}]
        got = L.fat_tickets(ev, [page], gst - 3600)
        self.assertEqual(got["0xa"]["usd"], 2406)                 # 6000 x 0.40 + 10 x 0.60
        self.assertNotIn("0xb", got)                              # 1600 < 2000
        self.assertNotIn("0xc", got)                              # 1200 + 600 across both sides = 1800 < 2000
        self.assertTrue(got["0xa"]["both"])                       # holds a little of the other side too
        self.assertEqual(got["0xe"]["usd"], 3000)
        self.assertNotIn("0xd", got)                              # props are not full-game markets
        self.assertEqual(L.fat_tickets(ev, [page], gst + 60), {})  # already started: not upcoming


if __name__ == "__main__":
    unittest.main()
