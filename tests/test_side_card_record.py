"""Unit tests for scripts/grade_side_cards.py and scripts/benchmark_h2h.py: the grading rules of docs/sharp-card-prereg.md."""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import grade_side_cards as G  # noqa: E402
import benchmark_h2h as H  # noqa: E402

GST = 1_800_000_000
CUT = GST - 900


def card(lock=None, sf=None, counts=True, sport="nba", group="spread"):
    m = {"lock_shadow": {"all": lock or {"side": None}, "fwd": {"side": None}}}
    if sf:
        m["sf"] = {"all": sf, "fwd": {"side": None, "units": 0}}
    return {"sport": sport, "ev": "nba-orl-uta-2026-11-11", "gst": GST, "cut": CUT,
            "test": {"counts": counts, "why_not": [] if counts else ["built after game start"]}, "markets": {group: m}}


LOCK = {"side": "Jazz", "cid": "c1", "line": -4.5, "outs": ["Magic", "Jazz"], "price": 0.515, "price_t": CUT - 60,
        "units_clean_ladder": 3}
FACT = {"c1": {"mt": "spreads", "line": -4.5, "outs": ["Magic", "Jazz"], "final": [1.0, 0.0]}}
CLOSES = {"games": {"nba|nba-orl-uta-2026-11-11": {"spreads": [{"line": -4.5, "outcomes": ["Magic", "Jazz"], "p": 0.52}]}}}


class Grade(unittest.TestCase):
    def test_loss_by_polymarket_resolution_with_clv(self):
        rows, wait = G.grade(card(LOCK), "nba/frozen/d/x.json", None, FACT, CLOSES, GST + 3600)
        self.assertEqual(wait, [])
        r, c = rows
        self.assertEqual((r["res"], r["flat"], r["units_pl"]), ("loss", -1.0, -3.0))
        self.assertEqual((c["kind"], c["of"]), ("close", r["key"]))
        self.assertAlmostEqual(c["close"], 0.48)                  # the Jazz side is outcomes[1]: 1 - p
        self.assertAlmostEqual(c["clv"], 0.48 - 0.515)

    def test_win_pays_one_over_price_minus_one(self):
        f = {"c1": {**FACT["c1"], "final": [0.0, 1.0]}}
        r = G.grade(card(LOCK), "k", None, f, CLOSES, GST + 3600)[0][0]
        self.assertAlmostEqual(r["flat"], 1 / 0.515 - 1, places=5)

    def test_half_resolution_is_a_push(self):
        f = {"c1": {**FACT["c1"], "final": [0.5, 0.5]}}
        self.assertEqual(G.grade(card(LOCK), "k", None, f, CLOSES, GST + 3600)[0][0]["flat"], 0.0)

    def test_unresolved_waits(self):
        f = {"c1": {**FACT["c1"], "final": None}}
        rows, wait = G.grade(card(LOCK), "k", None, f, CLOSES, GST + 3600)
        self.assertEqual(rows, [])
        self.assertEqual(wait[0][1], "not resolved")

    def test_result_never_waits_for_a_close_and_a_late_close_still_lands(self):
        rows, wait = G.grade(card(LOCK), "k", None, FACT, {}, GST + 3600)
        self.assertEqual([r["kind"] for r in rows], ["result"])
        self.assertEqual(wait[0][1], "no close stored yet")
        s = G.summarize(rows)
        self.assertEqual((s["n"], s["no_close"], s["clv_n"]), (1, 1, 0))
        late = G.grade(card(LOCK), "k", None, FACT, CLOSES, GST + 30 * 86400)[0]   # weeks later, the close arrives
        closes = {r["of"]: r for r in late if r["kind"] == "close"}
        s = G.summarize(rows, closes=closes)
        self.assertEqual((s["no_close"], s["clv_n"]), (0, 1))

    def test_cfb_has_no_close_row(self):
        rows, wait = G.grade(card(LOCK, sport="cfb"), "k", None, FACT, CLOSES, GST + 3600)
        self.assertEqual(([r["kind"] for r in rows], wait), (["result"], []))

    def test_stale_price_is_unpriced_and_kept_out_of_roi(self):
        lock = {**LOCK, "price_t": CUT - G.STALE_PRICE - 1}
        r = G.grade(card(lock), "k", None, FACT, CLOSES, GST + 3600)[0][0]
        self.assertEqual((r["status"], r["flat"], r["res"]), ("unpriced", None, "loss"))
        s = G.summarize([r])
        self.assertEqual((s["n"], s["unpriced"]), (0, 1))

    def test_close_needs_identical_outcome_list(self):
        flipped = {"games": {"nba|nba-orl-uta-2026-11-11": {"spreads": [{"line": -4.5, "outcomes": ["Jazz", "Magic"], "p": 0.5}]}}}
        self.assertIsNone(G.close_for(flipped, "nba", "nba-orl-uta-2026-11-11", "spread", -4.5, ["Magic", "Jazz"], "Jazz"))

    def test_sf_market_found_in_keyframe_when_card_has_no_cid(self):
        kf = {"mk": {"c1": {"mt": "spreads", "line": -4.5, "outs": ["Magic", "Jazz"], "px": [0.485, 0.515]},
                     "c2": {"mt": "spreads", "line": -6.5, "outs": ["Magic", "Jazz"], "px": [0.4, 0.6]}}}
        sf = {"side": "Jazz", "units": 2, "line": -4.5, "price": 0.515, "price_t": CUT - 60, "rung": "PRESS"}
        rows = [r for r in G.grade(card(sf=sf), "k", kf, FACT, CLOSES, GST + 3600)[0] if r["kind"] == "result"]
        self.assertEqual([(r["play"], r["cid"], r["units_pl"]) for r in rows], [("sf", "c1", -2.0)])

    def test_record_reads_counted_cards_only(self):
        a = G.grade(card(LOCK), "a", None, FACT, CLOSES, GST + 3600)[0]
        b = G.grade(card(LOCK, counts=False), "b", None, FACT, CLOSES, GST + 3600)[0]
        rec = G.record(a + b, [card(LOCK), card(LOCK, counts=False)], 0)
        s = rec["sports"]["nba"]
        self.assertEqual(s["lock"]["all"]["spread"]["counted"]["n"], 1)
        self.assertEqual(s["lock"]["all"]["spread"]["all_cards"]["n"], 2)
        self.assertEqual(s["cards"]["not_counted_by_reason"], {"built after game start": 1})
        self.assertEqual(s["lock"]["all"]["spread"]["counted"]["clv_n"], 1)

    def test_unpriced_share_over_ten_percent_fails_data_quality(self):
        ml = {"c1": {"mt": "moneyline", "line": None, "outs": ["Magic", "Jazz"], "final": [1.0, 0.0]}}
        good = {**LOCK, "line": None}
        stale = {**good, "price_t": CUT - G.STALE_PRICE - 1}
        rows = []
        for i, lk in enumerate([good] * 8 + [stale] * 2):
            rows += G.grade(card(lk, group="ml"), f"c{i}", None, ml, {}, GST + 3600)[0]
        dq = G.record(rows, [], 0)["sports"]["nba"]["data_quality"]
        self.assertEqual((dq["counted_ml_locks"], dq["unpriced_share"], dq["fail"]), (10, 0.2, True))

    def test_result_and_close_rows_save_and_load(self):
        import tempfile
        rows = G.grade(card(LOCK), "nba/frozen/d/x.json", None, FACT, CLOSES, GST + 3600)[0]
        self.assertEqual([r["kind"] for r in rows], ["result", "close"])
        with tempfile.TemporaryDirectory() as d:
            G.append_rows(d, rows)                                      # every row kind carries gst for its month file
            self.assertEqual(sorted(G.load_rows(d)), sorted(r["key"] for r in rows))

    def test_benchmark_list_variant_is_graded_and_compared(self):
        sf = {"side": "Jazz", "units": 2, "line": -4.5, "price": 0.515, "price_t": CUT - 60, "cid": "c1", "outs": ["Magic", "Jazz"]}
        c = card(LOCK)
        c["markets"]["spread"]["sf"] = {"all": {"side": None, "units": 0}, "sfx": sf}
        rows = [r for r in G.grade(c, "k", None, FACT, CLOSES, GST + 3600)[0] if r["kind"] == "result"]
        self.assertIn(("sf", "sfx", -2.0), [(r["play"], r["variant"], r["units_pl"]) for r in rows])
        rec = G.record(rows, [c], 0)["sports"]["nba"]
        self.assertEqual(rec["sf"]["sfx"]["spread"]["all_cards"]["n"], 1)
        h = H.h2h([], rows, 0)["sports"]["nba"]["spread"]
        self.assertEqual((h["vault_sfx"]["n"], h["vault_shown_size"]["n"]), (1, 0))

    def test_bootstrap_is_seeded(self):
        xs = [1.0, -1.0, 0.9, -1.0, 0.5]
        self.assertEqual(G.boot_ci(xs), G.boot_ci(xs))
        self.assertIsNone(G.boot_ci([1.0]))


class Benchmark(unittest.TestCase):
    def test_american_odds_to_price(self):
        self.assertAlmostEqual(H.american_to_price(128), 100 / 228)
        self.assertAlmostEqual(H.american_to_price(-150), 0.6)
        self.assertIsNone(H.american_to_price(None))

    def test_commit_at_or_before_the_cut(self):
        commits = [{"sha": "a", "t": CUT - 600}, {"sha": "b", "t": CUT}, {"sha": "c", "t": CUT + 1}]
        self.assertEqual(H.commit_before(commits, CUT)["sha"], "b")
        self.assertIsNone(H.commit_before(commits, CUT - 3 * 3600))   # nothing in the lookback window

    def test_game_entry_found_by_slug(self):
        j = {"NBA": {"orl_uth": {"away": "Magic", "home": "Jazz", "positions": [{"slug": "nba-orl-uta-2026-11-11-spread-away-4pt5"}]},
                     "was_ind": {"away": "Wizards", "home": "Pacers", "positions": [{"slug": "nba-was-ind-2026-11-11"}]}}}
        key, g = H.game_entry(j, "nba", "nba-orl-uta-2026-11-11")
        self.assertEqual((key, g["home"]), ("orl_uth", "Jazz"))

    def test_pick_mapped_to_polymarket_market(self):
        markets = {"ml": {"mt": "moneyline", "line": None, "outs": ["Magic", "Jazz"], "final": [1.0, 0.0]},
                   "s45": {"mt": "spreads", "line": -4.5, "outs": ["Magic", "Jazz"], "final": [1.0, 0.0]},
                   "s65": {"mt": "spreads", "line": -6.5, "outs": ["Magic", "Jazz"], "final": [0.0, 1.0]},
                   "t": {"mt": "totals", "line": 229.5, "outs": ["Over", "Under"], "final": [0.0, 1.0]}}
        money = {"s45": {"Jazz": 9000.0}, "s65": {"Jazz": 100.0}}
        self.assertEqual(H.map_pick({"marketType": "ml", "team": "Magic"}, markets, money), ("ml", "Magic", "exact"))
        self.assertEqual(H.map_pick({"marketType": "total", "team": "Under 229.5"}, markets, money), ("t", "Under", "exact"))
        self.assertEqual(H.map_pick({"marketType": "spread", "team": "Jazz"}, markets, money), ("s45", "Jazz", "most_money_rung"))
        self.assertEqual(H.map_pick({"marketType": "total", "team": "Over 231.5"}, markets, money), (None, None, "no_market"))

    def test_at_cut_plays_are_the_headline_and_later_changes_are_flagged(self):
        g = {"sport": "nba", "ev": "nba-cle-nyk-2026-11-11", "gst": GST}
        mk = {"ml": {"mt": "moneyline", "line": None, "outs": ["Cavaliers", "Knicks"], "final": [1.0, 0.0]},
              "s": {"mt": "spreads", "line": -3.5, "outs": ["Knicks", "Cavaliers"], "final": [0.0, 1.0]}}
        money = {"s": {"Knicks": 5000.0}}
        arc = {"picks_at_cut": {"picks": [
            {"marketType": "ml", "team": "Cavaliers", "units": 2, "cancelled": False, "oddsLock": 150},
            {"marketType": "spread", "team": "Knicks", "units": 1, "cancelled": False, "oddsLock": -110},
            {"marketType": "ml", "team": "Knicks", "units": 0, "cancelled": False, "oddsLock": -194}]}}
        fin = {"picks": [
            {"marketType": "ml", "team": "Cavaliers", "units": 0, "cancelled": True, "outcome": "WIN", "profit": 0},
            {"marketType": "spread", "team": "Knicks", "units": 1, "cancelled": False, "outcome": "LOSS", "profit": -1},
            {"marketType": "ml", "team": "Knicks", "units": 1, "cancelled": False, "outcome": "LOSS", "profit": -1, "oddsLock": -194}]}
        rows = {(r["set"], r["team"], r["group"]): r for r in H.play_rows(g, arc, fin, mk, money, 0)}
        cav = rows[("at_cut", "Cavaliers", "ml")]
        self.assertEqual((cav["res"], cav["cancelled_later"], cav["units_pl"]), ("win", True, 3.0))   # cancelled later, still graded
        spr = rows[("at_cut", "Knicks", "spread")]
        self.assertEqual((spr["res"], spr["res_mapped"], spr["flat"]), (None, "loss", None))          # no line: no priced result
        self.assertIn(("after_cut", "Knicks", "ml"), rows)                                            # sized up after the cut
        rec = H.h2h(list(rows.values()), [], 0)["sports"]["nba"]["ml"]
        self.assertEqual((rec["benchmark"]["n"], rec["benchmark_after_cut"]["n"], rec["benchmark_at_cut_cancelled_later"]), (1, 1, 1))

    def test_h2h_reads_card_results_and_skips_close_rows(self):
        rows = G.grade(card(LOCK), "nba/frozen/d/x.json", None, FACT, CLOSES, GST + 3600)[0]
        self.assertEqual([r["kind"] for r in rows], ["result", "close"])
        rec = H.h2h([], rows, 0)["sports"]["nba"]["spread"]
        self.assertEqual(rec["vault_lock"]["n"], 1)

    def test_unresolved_market_writes_nothing(self):
        g = {"sport": "nba", "ev": "e", "gst": GST}
        mk = {"ml": {"mt": "moneyline", "outs": ["A", "B"], "final": None}}
        arc = {"picks_at_cut": {"picks": [{"marketType": "ml", "team": "A", "units": 1, "oddsLock": 100}]}}
        self.assertEqual(H.play_rows(g, arc, {"picks": []}, mk, {}, 0), [])

    def test_real_play_rule(self):
        self.assertTrue(H.real_play({"units": 1, "cancelled": False}))
        self.assertFalse(H.real_play({"units": 0, "cancelled": False}))
        self.assertFalse(H.real_play({"units": 2, "cancelled": True}))


if __name__ == "__main__":
    unittest.main()
