"""Unit tests for scripts/grade_side_cards.py and scripts/sharpflow_h2h.py: the grading rules of docs/sharp-card-prereg.md."""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import grade_side_cards as G  # noqa: E402
import sharpflow_h2h as H  # noqa: E402

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
        r = rows[0]
        self.assertEqual((r["res"], r["flat"], r["units_pl"]), ("loss", -1.0, -3.0))
        self.assertAlmostEqual(r["close"], 0.48)                  # the Jazz side is outcomes[1]: 1 - p
        self.assertAlmostEqual(r["clv"], 0.48 - 0.515)

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

    def test_missing_close_waits_then_writes_without_one(self):
        rows, wait = G.grade(card(LOCK), "k", None, FACT, {}, GST + 3600)
        self.assertEqual((rows, wait[0][1]), ([], "waiting for the close"))
        r = G.grade(card(LOCK), "k", None, FACT, {}, GST + G.CLOSE_WAIT + 1)[0][0]
        self.assertEqual((r["clv"], r["close_status"], r["res"]), (None, "none_stored", "loss"))

    def test_cfb_never_waits_for_a_close(self):
        r = G.grade(card(LOCK, sport="cfb"), "k", None, FACT, {}, GST + 3600)[0][0]
        self.assertEqual(r["close_status"], "no_closes_for_sport")

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
        rows = G.grade(card(sf=sf), "k", kf, FACT, CLOSES, GST + 3600)[0]
        self.assertEqual([(r["play"], r["cid"], r["units_pl"]) for r in rows], [("sf", "c1", -2.0)])

    def test_record_reads_counted_cards_only(self):
        a = G.grade(card(LOCK), "a", None, FACT, CLOSES, GST + 3600)[0]
        b = G.grade(card(LOCK, counts=False), "b", None, FACT, CLOSES, GST + 3600)[0]
        rec = G.record(a + b, [card(LOCK), card(LOCK, counts=False)], 0)
        s = rec["sports"]["nba"]
        self.assertEqual(s["lock"]["all"]["spread"]["counted"]["n"], 1)
        self.assertEqual(s["lock"]["all"]["spread"]["all_cards"]["n"], 2)
        self.assertEqual(s["cards"]["not_counted_by_reason"], {"built after game start": 1})

    def test_bootstrap_is_seeded(self):
        xs = [1.0, -1.0, 0.9, -1.0, 0.5]
        self.assertEqual(G.boot_ci(xs), G.boot_ci(xs))
        self.assertIsNone(G.boot_ci([1.0]))


class SharpFlow(unittest.TestCase):
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

    def test_real_play_rule(self):
        self.assertTrue(H.real_play({"units": 1, "cancelled": False}))
        self.assertFalse(H.real_play({"units": 0, "cancelled": False}))
        self.assertFalse(H.real_play({"units": 2, "cancelled": True}))


if __name__ == "__main__":
    unittest.main()
