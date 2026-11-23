"""Unit tests for the Sharps V2 plays data (docs/sharps-v2-plays-spec.md): scripts/sharps_v2/plays_v2.py and its use in
scripts/build_side_cards.py. Synthetic inputs only; no network, no stored data. Run from the repo root:
    python3 -m unittest tests.test_sharps_v2_plays
"""
import copy, importlib.util, json, os, subprocess, sys, tempfile, time, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)
import build_side_cards as C  # noqa: E402
from sharps_v2 import plays_v2 as P  # noqa: E402
from sharps_v2 import tier_history as TH  # noqa: E402
import test_side_cards as T  # noqa: E402

CUT = T.CUT


def side_all(hc=0, sharp=0, unproven=0, loser=0, excluded=0, rk=None, proven=0, usd=100):
    d = {"counts": {"hc": hc, "sharp": sharp, "unproven": unproven, "loser": loser, "excluded": excluded},
         "sharp_usd": usd * (hc + sharp), "hc_usd": usd * hc, "unproven_usd": usd * unproven, "loser_usd": usd * loser,
         "excluded_usd": usd * excluded, "proven": {"wallets": proven or hc + sharp}}
    if rk is not None:
        d["rk"] = {"sharp_n": rk[0], "dull_n": rk[1], "sharp_usd": 0, "dull_usd": 0}
    return d


def market(S="A", O="B", s=None, o=None, pts=None, fwd=True, tb=None, tp=True, units=1, sport_rk=True):
    """A market group as the card stores it: sides, sf (all, fwd), tp. pts: the stored price-vs-fair points of the shown side."""
    s = s or side_all(rk=(0, 0) if sport_rk else None)
    o = o or side_all(rk=(0, 0) if sport_rk else None)
    sf = {"side": S, "units": units, "price": 0.55, "price_t": CUT - 600, "line": None, "cid": "m1", "pinnacle_odds": -118}
    if pts is not None:
        sf["signals"] = {"limit": None, "ev": {"fair": 0.56, "pts": pts, "on": pts >= 0.3, "why": None}}
    m = {"sides": {S: {"all": s}, O: {"all": o}}, "sf": {"all": sf, "fwd": {"side": S if fwd else None}}}
    if tp:
        m["tp"] = {"tA": None, "tB": {"side": tb} if tb else None, "tC": None}
    return m


class TierRules(unittest.TestCase):
    def tier(self, sport="nba", **kw):
        m = market(**kw)
        f, na = P.facts(sport, m, "A")
        s = m["sides"]["A"]["all"]
        return P.tier_of(f, s["proven"]["wallets"], (P.ev_of(m["sf"]["all"]) or {}).get("pts"))[0], f, na

    def test_contested_by_each_fact_against(self):
        self.assertEqual(self.tier(o=side_all(hc=1, rk=(0, 0)))[0], "contested")              # a1: a past winner on the other side
        self.assertEqual(self.tier(o=side_all(sharp=1, rk=(0, 0)))[0], "contested")
        self.assertEqual(self.tier(o=side_all(unproven=2, rk=(1, 0)))[0], "contested")        # a2: beats the close on the other side
        self.assertEqual(self.tier(tb="B")[0], "contested")                                    # a3: fade-dull fires on the other side
        self.assertEqual(self.tier(pts=-0.3)[0], "contested")                                  # a4: worse than fair by 0.3
        self.assertNotEqual(self.tier(pts=-0.29)[0], "contested")
        self.assertNotEqual(self.tier(tb="A")[0], "contested")                                 # the fade rule on THIS side is not against it

    def test_clear_needs_a_price_or_close_fact_and_the_forward_pick(self):
        self.assertEqual(self.tier(pts=0.3)[0], "clear")                                       # b2 and b3
        self.assertEqual(self.tier(s=side_all(hc=1, rk=(1, 0)))[0], "clear")                  # b1 and b3
        self.assertEqual(self.tier(pts=0.5, fwd=False)[0], "mixed")                            # no b3
        self.assertEqual(self.tier(s=side_all(hc=2, rk=(0, 0)))[0], "mixed")                  # b4 alone is not clear

    def test_thin_and_mixed(self):
        self.assertEqual(self.tier(s=side_all(hc=1, rk=(0, 0)))[0], "thin")                   # one wallet, no price evidence
        self.assertEqual(self.tier(s=side_all(hc=1, rk=(0, 0)), pts=0.1)[0], "mixed")         # a price read exists: not thin
        self.assertEqual(self.tier(s=side_all(hc=2, rk=(0, 0)))[0], "mixed")
        self.assertEqual(self.tier(s=side_all(unproven=3, proven=0, rk=(0, 0)))[0], "thin")

    def test_college_has_no_price_tier_facts(self):
        t, f, na = self.tier("cbb", s=side_all(hc=1), o=side_all(unproven=1), sport_rk=False, tp=False)
        self.assertEqual((t, na), ("thin", ["a2", "b1", "a3"]))
        self.assertEqual((f["a2"], f["a3"], f["b1"]), (False, False, False))                   # published false, never None
        self.assertEqual(self.tier("cfb", s=side_all(hc=1), sport_rk=False, tp=False)[0], "thin")

    def test_unknown_facts_on_an_old_card(self):
        m = market(sport_rk=False, tp=False)                                                   # no rk, no tp: a card from before they were stored
        f, _ = P.facts("nba", m, "A")
        self.assertEqual((f["a2"], f["a3"], f["b1"]), (None, None, None))
        tier, why = P.tier_of(f, 1, None)
        self.assertIsNone(tier)
        self.assertIn("a2", why)
        m["sides"]["B"]["all"] = side_all(hc=1)                                                # a known fact against still decides
        m["sides"]["A"]["all"].pop("rk", None)
        f, _ = P.facts("nba", m, "A")
        self.assertEqual(P.tier_of(f, 1, None)[0], "contested")

    def test_point_in_time_a_later_input_does_not_change_the_tier(self):
        rows = [{"t": CUT - 50, "book": "Pinnacle", "ml": [130, -150]}]
        m = market(pts=0.4)
        before = P.market_v2("nba", "ml", m, [], {}, {"mk": {}}, CUT, {"A": "home", "B": "away"}, rows=rows)[0]
        later = rows + [{"t": CUT + 1, "book": "Pinnacle", "ml": [400, -600]}, {"t": CUT + 1, "book": "FanDuel", "ml": [-500, 300]},
                        {"t": CUT + 5, "book": "Kalshi", "px": [0.01, 0.02]}]
        after = P.market_v2("nba", "ml", m, [], {}, {"mk": {}}, CUT, {"A": "home", "B": "away"}, rows=later)[0]
        self.assertEqual(json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True))


class ShownUnits(unittest.TestCase):
    def test_flat_1u_on_nba_nfl_cbb_none_on_cfb_and_no_pick(self):
        self.assertEqual([P.shown_units(s, "A") for s in ("nba", "nfl", "cbb", "cfb")], [1, 1, 1, 0])
        self.assertEqual(P.shown_units("nba", None), 0)

    def test_identical_for_every_tier(self):
        seen = set()
        for kw in ({"pts": 0.5}, {"pts": -0.5}, {"s": side_all(hc=1, rk=(0, 0))}, {"s": side_all(hc=2, rk=(0, 0))}, {"tb": "B"}):
            v2, _ = P.market_v2("nba", "ml", market(**kw), [], {}, {"mk": {}}, CUT, {})
            seen.add((v2["shown_units"], v2["untested"]))
        self.assertEqual(seen, {(1, True)})
        v2, _ = P.market_v2("cfb", "ml", market(sport_rk=False, tp=False), [], {}, {"mk": {}}, CUT, {})
        self.assertEqual((v2["shown_units"], v2["tier"] is not None), (0, True))                # CFB: the tier is logged, no size is shown
        v2, _ = P.market_v2("nba", "ml", market(units=0), [], {}, {"mk": {}}, CUT, {})
        self.assertEqual((v2["side"], v2["shown_units"], v2["tier"]), (None, 0, None))

    def test_the_size_shown_at_the_time(self):
        self.assertEqual(P.shown_units_at("cbb", P.FLAT_FROM - 1, 3), 3)                       # the ladder before Nov 18 8:31 AM CT
        self.assertEqual(P.shown_units_at("cfb", P.FLAT_FROM - 1, 2), 2)
        self.assertEqual((P.shown_units_at("nba", P.FLAT_FROM, 5), P.shown_units_at("cfb", P.FLAT_FROM, 5)), (1, 0))
        self.assertEqual((P.shown_units_at("cbb", P.CBB_FROM - 1, 5), P.shown_units_at("cbb", P.CBB_FROM, 5)), (0, 1))

    def test_the_ladder_key_is_left_alone(self):
        m = market(units=4)
        before = copy.deepcopy(m)
        v2, _ = P.market_v2("nba", "ml", m, [], {}, {"mk": {}}, CUT, {})
        self.assertEqual(m, before)                                                            # nothing on the card changed
        self.assertEqual((v2["shown_units"], m["sf"]["all"]["units"]), (1, 4))


class PriceReads(unittest.TestCase):
    ROWS = [
        {"t": CUT - 900, "book": "DraftKings", "ml": [120, -140]}, {"t": CUT - 300, "book": "FanDuel", "ml": [118, -135]},
        {"t": CUT - 200, "book": "BetMGM", "ml": [118, -135]}, {"t": CUT - 100, "book": "Kalshi", "px": [0.60, 0.64]},
        {"t": CUT - 100, "book": "Novig", "px": [0.61, 0.63]}, {"t": CUT - 400, "book": "Pinnacle", "ml": [125, -145]},
    ]

    def test_us_best_is_lowest_implied_with_alphabetical_ties(self):
        e = P.exec_block(self.ROWS, "ml", "home", None, -118, CUT)
        self.assertEqual((e["us_best"]["book"], e["us_best"]["odds"]), ("BetMGM", -135))        # FanDuel ties at -135: BetMGM sorts first
        self.assertEqual(e["us_best"]["since_min"], 3)
        self.assertEqual(e["pin"], {"odds": -118, "t": CUT - 400})
        self.assertNotIn("pm_ask", e)                                                          # no ask is stored: nothing is written
        self.assertEqual(e["asof"], CUT)

    def test_exchange_cost_of_each_side(self):
        h, a = (P.exec_block(self.ROWS, "ml", n, None, None, CUT) for n in ("home", "away"))
        self.assertEqual((h["kalshi"]["px"], a["kalshi"]["px"]), (0.64, 0.4))                  # away = 1 minus the home bid
        self.assertEqual((h["novig"]["px"], a["novig"]["px"]), (0.63, 0.39))
        self.assertNotIn("pin", h)                                                             # no Pinnacle price stored on the card: no pin line

    def test_never_copies_the_polymarket_price(self):
        v2, _ = P.market_v2("nba", "ml", market(), [], {}, {"mk": {"m1": {"outs": ["A", "B"], "px": [0.55, 0.45]}}}, CUT,
                            {"A": "home", "B": "away"}, rows=self.ROWS)
        self.assertEqual(v2["price_src"], "pm")
        self.assertEqual(v2["pm"], {"px": 0.55, "t": CUT - 600, "since_min": 10, "kind": "displayed"})
        self.assertNotIn(0.55, [x.get("px") for x in v2["exec"].values() if isinstance(x, dict)])

    def test_price_src_is_pin_when_polymarket_had_no_price(self):
        sf = {"side": "A", "price": 0.5, "cid": "m1"}
        self.assertEqual(P.price_src(sf, {"mk": {"m1": {"outs": ["A", "B"], "px": [None, None]}}}), "pin")
        self.assertIsNone(P.price_src({"side": "A", "price": None, "cid": "m1"}, {"mk": {}}))

    def test_spread_and_total_need_the_same_line(self):
        rows = [{"t": CUT - 60, "book": "FanDuel", "sp": [-3.5, -110, -110]}, {"t": CUT - 50, "book": "BetMGM", "sp": [-4.5, -105, -115]},
                {"t": CUT - 40, "book": "Novig", "nsp": [-3.5, 0.48, 0.5]}]
        e = P.exec_block(rows, "spread", "home", -3.5, None, CUT)                              # home -3.5: only FanDuel has that line
        self.assertEqual((e["us_best"]["book"], e["us_best"]["line"]), ("FanDuel", -3.5))
        self.assertEqual(e["novig"]["px"], 0.5)
        a = P.exec_block(rows, "spread", "away", 3.5, None, CUT)                               # the away side of -3.5 reads +3.5
        self.assertEqual((a["us_best"]["book"], a["novig"]["px"]), ("FanDuel", 0.52))
        self.assertNotIn("us_best", P.exec_block(rows, "spread", "home", -3.0, None, CUT))     # a different line: omitted
        self.assertNotIn("novig", P.exec_block(rows, "spread", "home", -4.0, None, CUT))
        tot = [{"t": CUT - 60, "book": "DraftKings", "tot": [220.5, -105, -115]}, {"t": CUT - 50, "book": "Novig", "ntot": [220.5, 0.5, 0.52]}]
        u = P.exec_block(tot, "total", "under", 220.5, None, CUT)
        self.assertEqual((u["us_best"]["odds"], u["novig"]["px"]), (-115, 0.5))                # under: odds[2]; cost = 1 minus the over bid

    def test_reads_stop_at_asof(self):
        rows = self.ROWS + [{"t": CUT + 1, "book": "FanDuel", "ml": [-500, 400]}]
        self.assertEqual(P.exec_block(rows, "ml", "home", None, None, CUT)["us_best"]["book"], "BetMGM")
        self.assertEqual(P.exec_block(rows, "ml", "home", None, None, CUT + 1)["us_best"]["book"], "FanDuel")
        self.assertEqual(P.exec_block(rows, "ml", "home", None, None, CUT - 2000), {"asof": CUT - 2000})   # nothing logged yet

    def test_unmapped_side_reads_nothing(self):
        self.assertEqual(P.exec_block(self.ROWS, "ml", None, None, None, CUT), {"asof": CUT})

    def test_vs_fair_carries_the_stored_read_and_its_reason(self):
        sf = market(pts=-0.7)["sf"]["all"]
        rows = [{"t": CUT - 30, "book": "Pinnacle", "ml": [100, -110]}]
        self.assertEqual(P.vs_fair(sf, rows, "ml", CUT), {"pts": -0.7, "fair": 0.56, "t": CUT - 30, "line": None, "why": None})
        self.assertEqual(P.vs_fair({"line": 1.5}, None, "ml", CUT)["why"], "no_tape")
        no_ev = {"signals": {"limit": None, "ev": {"fair": None, "pts": None, "on": None, "why": "ticket_line_not_main_at_cut"}}}
        got = P.vs_fair(no_ev, rows, "ml", CUT)
        self.assertEqual((got["pts"], got["why"]), (None, "ticket_line_not_main_at_cut"))


class Splits(unittest.TestCase):
    GAME = {"splits": {"ml": {"home": {"t": 33, "m": 64}, "away": {"t": 67, "m": 36}}, "sp": None, "tot": {"over": {"t": 0, "m": 5}, "under": {"t": 100, "m": 95}}},
            "splitHist": [{"ts": CUT - 5000, "ml": [30, 60], "sp": None, "tot": None}, {"ts": CUT - 100, "ml": [32, 62], "sp": [50, 47], "tot": [10, 12]},
                          {"ts": CUT + 100, "ml": [99, 99], "sp": None, "tot": None}]}
    NORMS = {"Home": "home", "Away": "away"}

    def test_live_both_sides_as_stored_and_zero_is_stored_not_invented(self):
        s = P.splits_live(self.GAME, "ml", self.NORMS, 123)
        self.assertEqual(s, {"t": 123, "src": "action_network_consensus", "basis": "live",
                             "sides": {"Home": {"bets": 33, "money": 64}, "Away": {"bets": 67, "money": 36}}})
        t = P.splits_live(self.GAME, "total", {"Over": "over", "Under": "under"}, 123)
        self.assertEqual(t["sides"]["Over"], {"bets": 0, "money": 5})

    def test_absent_when_the_feed_has_none(self):
        self.assertIsNone(P.splits_live(self.GAME, "spread", self.NORMS, 1))                    # null in the feed: no key, no placeholder
        self.assertIsNone(P.splits_live({}, "ml", self.NORMS, 1))
        self.assertIsNone(P.splits_at({"splitHist": []}, "ml", self.NORMS, CUT))
        self.assertIsNone(P.splits_at(None, "ml", self.NORMS, CUT))

    def test_at_cut_uses_only_rows_at_or_before_the_cut_and_marks_the_complement(self):
        s = P.splits_at(self.GAME, "ml", self.NORMS, CUT)
        self.assertEqual((s["t"], s["basis"]), (CUT - 100, "at_cut"))                           # the row 100 s after the cut is ignored
        self.assertEqual(s["sides"]["Home"], {"bets": 32, "money": 62})
        self.assertEqual(s["sides"]["Away"], {"bets": 68, "money": 38, "comp": True})
        self.assertEqual(P.splits_at(self.GAME, "ml", self.NORMS, CUT + 100)["sides"]["Home"]["bets"], 99)
        self.assertIsNone(P.splits_at(self.GAME, "spread", self.NORMS, CUT + 100))              # the last row has no spread split: never an older one

    def test_unmapped_side_is_left_out(self):
        s = P.splits_live(self.GAME, "ml", {"Home": "home", "Away": None}, 1)
        self.assertEqual(list(s["sides"]), ["Home"])
        self.assertIsNone(P.splits_live(self.GAME, "ml", {"Home": None, "Away": None}, 1))
        self.assertEqual(list(P.splits_at(self.GAME, "ml", {"Home": "home", "Away": None}, CUT)["sides"]), ["Home"])


class Conflict(unittest.TestCase):
    def holder(self, w, side, usd, tier=None, usual=100.0):
        return {"w": w, "side": side, "usd": usd, "rk": {"tier": tier} if tier else None, "s": {"all": {"usual": usual}}}

    def test_side_blocks_invariants(self):
        ws = [self.holder("a", "A", 400, "sharp"), self.holder("b", "A", 300, "mid"), self.holder("c", "A", 300), self.holder("d", "B", 250, "dull"),
              self.holder("e", "B", 900, "thin")]
        sides_out = {"A": {"all": side_all(hc=1, loser=1, unproven=1, rk=(1, 0), usd=100)}, "B": {"all": side_all(sharp=0, unproven=2, rk=(0, 1))}}
        sides_out["A"]["all"].update(sharp_usd=400, loser_usd=300, unproven_usd=300, hc_usd=400, excluded_usd=0)
        sides_out["B"]["all"].update(unproven_usd=1150)
        b = P.side_blocks("nba", sides_out, ws, ["A", "B"])
        a = b["A"]
        self.assertEqual((a["holders"], a["usd"]), (3, 1000))
        self.assertEqual((a["beats"], a["even"], a["few"], a["loses"]), ({"n": 1, "usd": 400}, {"n": 1, "usd": 300}, {"n": 1, "usd": 300}, {"n": 0, "usd": 0}))
        self.assertEqual(a["beats"]["n"] + a["loses"]["n"] + a["even"]["n"] + a["few"]["n"], a["holders"])
        self.assertEqual(b["B"]["loses"]["n"], 1)
        self.assertEqual(a["past_winner"], {"n": 1, "usd": 400})
        c = P.conflict(b, "A", False)
        self.assertEqual((c["past_winner_against"]["n"], c["beats_for"], c["loses_against"], c["money_share_for"]), (0, 1, 1, round(1000 / 2150, 3)))

    def test_college_holders_are_all_few(self):
        ws = [self.holder("a", "A", 400, "sharp"), self.holder("b", "A", 300)]
        b = P.side_blocks("cbb", {"A": {"all": side_all(hc=1, unproven=1, usd=100)}}, ws, ["A"])["A"]
        self.assertEqual((b["price_tier"], b["beats"], b["loses"], b["even"], b["few"]["n"]), (False, None, None, None, 2))
        self.assertIsNone(P.conflict({"A": b}, "A", False)["beats_for"])

    def test_past_winners_money_order_and_press(self):
        ws = [self.holder("a", "A", 300), self.holder("b", "A", 900, usual=300.0), self.holder("c", "B", 5000), self.holder("d", "A", 700)]
        cls = {"a": "sharp", "b": "hc", "c": "hc", "d": "unproven"}
        pw = P.past_winners(ws, cls, "A")
        self.assertEqual([(p["w"], p["press"]) for p in pw], [("b", 3.0), ("a", 3.0)])


class Slate(unittest.TestCase):
    def game(self, ev, w_lists):
        mk = {}
        for g, ws in w_lists.items():
            pw = [{"w": w, "usd": 100, "class": "hc", "press": 1.0} for w in ws]
            mk[g] = {"v2": {"shown_units": 1, "side": "A", "tier": "contested", "lead": dict(pw[0]) if pw else None, "past_winners_for": pw,
                            "vs_fair": {"pts": None}}}
        return {"ev": ev, "markets": mk}

    def test_same_wallet_across_the_slate_uses_the_full_lists(self):
        games = [self.game("e1", {"ml": ["w1", "w2"]}), self.game("e2", {"ml": ["w1"], "total": ["w3", "w1"]}), self.game("e3", {"ml": ["w9"]})]
        s = P.v2_slate(games)
        self.assertEqual(s["plays"], 4)
        self.assertEqual(s["by_tier"]["contested"], 4)
        self.assertEqual(s["same_wallet"], [{"w": "w1", "plays": 3, "keys": ["e1|ml", "e2|ml", "e2|total"]}])
        self.assertEqual(games[0]["markets"]["ml"]["v2"]["lead"]["slate_plays"], 3)
        self.assertEqual(games[2]["markets"]["ml"]["v2"]["lead"]["slate_plays"], 1)


class Additive(unittest.TestCase):
    """The V2 plays block adds keys and changes none: the card, with the block stripped, equals the card built without it."""

    def card(self, **kw):
        rows = T.proven("0xp") + T.proven("0xq")
        k = T.kf([("m1", 0, "0xp", 400), ("m1", 1, "0xq", 350), ("m1", 1, "0xu", 900), ("s1", 1, "0xp", 500)])
        with mock.patch.object(time, "time", return_value=CUT + 5):
            return C.card(k, T.ledger(rows), "nba", **kw)

    def test_stripped_card_equals_the_card_built_without_the_block(self):
        with mock.patch.object(P, "market_v2", return_value=({}, None)):
            bare = self.card()
        new = self.card()
        self.assertTrue(all("v2" in m for m in new["markets"].values()))
        self.assertEqual(json.dumps(P.strip_plays_v2(new), separators=(",", ":")), json.dumps(P.strip_plays_v2(bare), separators=(",", ":")))

    def test_against_the_builder_on_main(self):
        """Old builder (git, the branch's merge base with origin/main) vs new, same inputs: every pre-existing key is identical."""
        try:
            base = subprocess.run(["git", "-C", ROOT, "show", "origin/main:scripts/build_side_cards.py"], capture_output=True, check=True).stdout.decode()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("origin/main not available")
        if "plays_v2" in base:
            self.skipTest("origin/main already carries the V2 plays data")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "old_build_side_cards.py")
            with open(p, "w") as f:
                f.write(base)
            spec = importlib.util.spec_from_file_location("old_build_side_cards", p)
            old = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(old)
        rows = T.proven("0xp") + T.proven("0xq")
        k = T.kf([("m1", 0, "0xp", 400), ("m1", 1, "0xq", 350), ("m1", 1, "0xu", 900), ("s1", 1, "0xp", 500)])
        with mock.patch.object(time, "time", return_value=CUT + 5):
            o = old.card(copy.deepcopy(k), T.ledger(rows), "nba")
            for frozen in (True, False):
                n = C.card(copy.deepcopy(k), T.ledger(rows), "nba", frozen=frozen)
                o = old.card(copy.deepcopy(k), T.ledger(rows), "nba", frozen=frozen)
                self.assertEqual(json.dumps(P.strip_plays_v2(n), separators=(",", ":")), json.dumps(o, separators=(",", ":")))

    def test_card_block_invariants(self):
        c = self.card()
        for g, m in c["markets"].items():
            v2 = m["v2"]
            self.assertEqual(v2["rule"], "v2t-1")
            for s, b in v2["sides"].items():
                a = m["sides"][s]["all"]
                self.assertEqual(b["holders"], sum(a["counts"].values()))
                self.assertEqual(b["past_winner"]["n"], a["counts"]["hc"] + a["counts"]["sharp"])
                self.assertEqual((b["beats"]["n"], b["loses"]["n"]), (a["rk"]["sharp_n"], a["rk"]["dull_n"]))
                self.assertEqual(b["beats"]["n"] + b["loses"]["n"] + b["even"]["n"] + b["few"]["n"], b["holders"])
            sf = m["sf"]["all"]
            self.assertEqual(v2["side"], sf["side"] if (sf["units"] or 0) > 0 else None)
            if v2["side"]:
                self.assertEqual(v2["vs_fair"]["pts"], ((sf.get("signals") or {}).get("ev") or {}).get("pts"))

    def test_splits_join_by_vault_key_and_omit_without_a_feed(self):
        vault = {"key": "nba:1", "teams": {"away": ["A"], "home": ["B"]}}
        feed = {"games": {"nba:1": {"splits": {"ml": {"home": {"t": 40, "m": 55}, "away": {"t": 60, "m": 45}}},
                                    "splitHist": [{"ts": CUT - 10, "ml": [41, 56]}]}}, "ts": CUT - 30}
        live = self.card(vault=vault, feed=feed, frozen=False)
        self.assertEqual(live["markets"]["ml"]["splits"]["sides"]["B"], {"bets": 40, "money": 55})
        self.assertEqual(live["markets"]["ml"]["splits"]["t"], CUT - 30)
        self.assertNotIn("splits", live["markets"]["spread"])                                    # the feed has none for the spread
        frozen = self.card(vault=vault, feed=feed, frozen=True)
        self.assertEqual(frozen["markets"]["ml"]["splits"]["sides"]["A"], {"bets": 59, "money": 44, "comp": True})
        self.assertNotIn("splits", self.card()["markets"]["ml"])                                  # no feed: no key, never 0
        self.assertNotIn("splits", self.card(vault={"key": "nba:other", "teams": vault["teams"]}, feed=feed)["markets"]["ml"])


class ShadowLog(unittest.TestCase):
    def frozen_card(self, ev="nba-a-b-2026-11-24", gst=1_795_500_000):
        m = market(pts=0.4)
        v2, _ = P.market_v2("nba", "ml", m, [], {}, {"mk": {}}, gst - 900, {"A": "home", "B": "away"})
        m["v2"] = v2
        return {"sport": "nba", "ev": ev, "gst": gst, "cut": gst - 900, "frozen": True, "test": {"counts": True, "why_not": []}, "markets": {"ml": m}}

    def write(self, root, c):
        rel = f"nba/frozen/2026-11-24/{c['ev']}@{c['gst']}.json"
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        with open(os.path.join(root, rel), "w") as f:
            json.dump(c, f)
        return rel

    def test_one_row_per_pick_second_run_appends_nothing_and_heals(self):
        with tempfile.TemporaryDirectory() as d:
            now = 1_795_499_000
            rel = self.write(d, self.frozen_card())
            self.assertEqual(P.sync_log(d, "nba", now, extra=[rel]), 1)
            path = os.path.join(d, "nba", "v2_tier", "2026-11.jsonl")
            first = open(path).read()
            row = json.loads(first)
            self.assertEqual((row["key"], row["tier"], row["shown_units"], row["rule"]), (rel + "|ml|all|sf", "clear", 1, "v2t-1"))
            self.assertEqual(row["counts"], True)
            self.assertEqual(P.sync_log(d, "nba", now + 600, extra=[rel]), 0)                      # a second run appends nothing
            self.assertEqual(open(path).read(), first)
            rel2 = self.write(d, self.frozen_card(ev="nba-c-d-2026-11-24", gst=1_795_503_600))     # a card whose append was missed
            self.assertEqual(P.sync_log(d, "nba", now + 1200), 1)                                  # healed from its stored block
            self.assertTrue(open(path).read().startswith(first))                                    # existing lines byte-identical
            self.assertEqual(len(open(path).read().splitlines()), 2)
            self.assertEqual([json.loads(l)["key"] for l in open(path)][1], rel2 + "|ml|all|sf")

    def test_a_card_without_a_v2_block_or_a_pick_owes_no_row(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.frozen_card()
            del c["markets"]["ml"]["v2"]
            self.write(d, c)
            self.assertEqual(P.sync_log(d, "nba", 1_795_499_000), 0)
            c = self.frozen_card(ev="nba-e-f-2026-11-24", gst=1_795_507_200)
            c["markets"]["ml"]["sf"]["all"]["units"] = 0
            c["markets"]["ml"]["v2"]["side"] = None
            self.write(d, c)
            self.assertEqual(P.sync_log(d, "nba", 1_795_499_000), 0)


class History(unittest.TestCase):
    def test_stats_and_the_size_at_the_time(self):
        ps = [{"sport": "nba", "res": "win", "flat": 0.8, "clv": 1.0, "cut": P.FLAT_FROM + 1, "ladder": 3},
              {"sport": "nba", "res": "loss", "flat": -1.0, "clv": None, "cut": P.FLAT_FROM - 1, "ladder": 3},
              {"sport": "cfb", "res": "win", "flat": 1.0, "clv": None, "cut": P.FLAT_FROM + 1, "ladder": 2}]
        s = TH.stats(ps)
        self.assertEqual((s["n"], s["w"], s["l"], s["units"], s["clv_n"], s["clv_mean"]), (3, 2, 1, 0.8, 1, 1.0))
        t = TH.at_the_time(ps)
        self.assertEqual((t["n"], t["staked"], t["units"]), (2, 4, round(0.8 - 3.0, 2)))         # the CFB play had no size after Nov 18


class NoEmDash(unittest.TestCase):
    def test_no_u2014_in_new_or_changed_files(self):
        files = ["scripts/sharps_v2/plays_v2.py", "scripts/sharps_v2/tier_history.py", "scripts/sharps_v2/check_size.py",
                 "scripts/build_side_cards.py", "tests/test_sharps_v2_plays.py", "docs/sharp-tier-v2-prereg.md", "docs/side-cards.md",
                 "docs/side-card-record.md", ".github/workflows/pm-cards.yml"]
        for f in files:
            p = os.path.join(ROOT, f)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as fh:
                    self.assertNotIn(chr(0x2014), fh.read(), f)


if __name__ == "__main__":
    unittest.main()
