"""Unit tests for scripts/build_side_cards.py: as-of wallet books, the benchmark's class rules, card money and the lock gates."""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import build_side_cards as C  # noqa: E402

CUT = 1_800_000_000


def row(w, i, res, stake=100.0, pnl=None, settled=None, src="backfill", hedged=False, split=False, cid=None):
    pnl = pnl if pnl is not None else (stake * 0.9 if res == "win" else -stake if res == "loss" else 0.0)
    return {"w": w, "cid": cid or f"{w}-c{i}", "oi": 0, "res": res, "stake": stake, "pnl": pnl,
            "settled_at": settled if settled is not None else CUT - 86400 * 40 + i * 3600, "src": src, "hedged": hedged, "split": split}


def ledger(rows, us=(), markets=None, first_seen=None, run_at=CUT - 3600):
    fs = first_seen if first_seen is not None else {r["w"]: CUT - 86400 * 100 for r in rows}
    return C.Ledger(rows, markets or {}, fs, list(us), run_at)


class Books(unittest.TestCase):
    def test_door2_proven(self):
        rows = [row("0xp", i, "win") for i in range(4)] + [row("0xp", 10 + i, "loss") for i in range(2)]   # 4-2, ROI (360-200)/600
        b = ledger(rows).stats("0xp", CUT)["all"]
        self.assertEqual((b["n"], b["proven"]), (6, True))
        b5 = ledger(rows[:5]).stats("0xp", CUT)["all"]                                                      # n=5: not yet
        self.assertFalse(b5["proven"])

    def test_rows_after_the_cut_are_ignored(self):
        rows = [row("0xp", i, "win") for i in range(6)] + [row("0xp", 99, "loss", stake=10000, settled=CUT + 60)]
        self.assertTrue(ledger(rows).stats("0xp", CUT)["all"]["proven"])
        self.assertEqual(ledger(rows).stats("0xp", CUT)["all"]["n"], 6)

    def test_loser_order_follows_benchmark(self):
        rows = [row("0xl", 0, "win", stake=10), row("0xl", 1, "loss", stake=500)]
        b = ledger(rows).stats("0xl", CUT)["all"]
        self.assertTrue(b["loser"])                                       # book PnL < 0
        rows = [row("0xm", i, "win", stake=100) for i in range(3)] + [row("0xm", 5, "loss", stake=100)]
        self.assertFalse(ledger(rows).stats("0xm", CUT)["all"]["loser"])   # PnL > 0, n=4 < 6: unproven

    def test_hedged_and_split_rows(self):
        rows = [row("0xh", i, "win", hedged=True, cid=f"h{i}") for i in range(8)] + [row("0xh", 20 + i, "win") for i in range(8)]
        s = ledger(rows).stats("0xh", CUT)
        self.assertEqual((s["all"]["n"], s["excluded"]), (8, "hedger"))      # 8 of 16 markets hedged = 50%
        rows = [row("0xs", i, "win") for i in range(6)] + [row("0xs", 9, "loss", stake=1e6, split=True)]
        b = ledger(rows).stats("0xs", CUT)["all"]
        self.assertEqual((b["l"], b["stake"]), (1, 600.0))                   # split row: counts in W/L, not in dollars

    def test_forward_variant_and_l30(self):
        rows = [row("0xf", i, "win", src="forward", settled=CUT - 86400 * 5 + i) for i in range(2)] + \
               [row("0xf", 10 + i, "win") for i in range(6)]
        s = ledger(rows).stats("0xf", CUT)
        self.assertEqual((s["all"]["n"], s["fwd"]["n"], s["all"]["l30_n"]), (8, 2, 2))
        self.assertAlmostEqual(s["all"]["l30_roi"], 0.9)

    def test_churn_uses_snapshot_dated_before_cut(self):
        snap = {"w": "0xc", "at": CUT - 10, "all_time_pnl": {"realized_pnl": 1000, "volume_usdc": 500000}}
        later = {"w": "0xc", "at": CUT + 10, "all_time_pnl": {"realized_pnl": 1e6, "volume_usdc": 500000}}
        self.assertEqual(ledger([row("0xc", 0, "win")], [snap, later]).stats("0xc", CUT)["excluded"], "churn")


def kf(holdings, px=(0.6, 0.4)):
    """holdings: [(cid, oi, wallet, usd)] on one moneyline 'm1' with outcomes A/B, plus optional spread rungs 's1','s2'."""
    mk = {"m1": {"mt": "moneyline", "line": None, "outs": ["A", "B"], "px": list(px), "px_t": CUT - 100, "frz_lag": 60},
          "s1": {"mt": "spreads", "line": -3.5, "outs": ["B", "A"], "px": [0.5, 0.5], "px_t": CUT - 100, "frz_lag": 60},
          "s2": {"mt": "spreads", "line": -4.5, "outs": ["B", "A"], "px": [0.45, 0.55], "px_t": CUT - 100, "frz_lag": 60}}
    return {"ev": "nba-a-b-2027-01-15", "gst": CUT + 900, "cut": CUT, "written": CUT + 5, "mk": mk, "miss": [], "late_reads": 0,
            "cols": ["cid", "oi", "wallet", "shares", "usd_at_mark", "fs", "fs_prev", "cens", "conf"],
            "h": [[c, oi, w, usd, usd, 1, None, False, 1] for c, oi, w, usd in holdings]}


def proven(w, n=20, stake=100.0):
    return [row(w, i, "win" if i % 4 else "loss", stake=stake) for i in range(n)]      # 15-5, ROI well above 3%


class Cards(unittest.TestCase):
    def test_buckets_floor_and_hedge_collapse(self):
        rows = proven("0xp") + [row("0xl", 0, "loss", stake=500)]
        k = kf([("m1", 0, "0xp", 400), ("m1", 0, "0xl", 300), ("m1", 1, "0xu", 900), ("m1", 1, "0xtiny", 100),
                ("m1", 0, "0xh", 1000), ("m1", 1, "0xh", 300)])
        c = C.card(k, ledger(rows), "nba")
        a, b = c["markets"]["ml"]["sides"]["A"]["all"], c["markets"]["ml"]["sides"]["B"]["all"]
        self.assertEqual((a["sharp_usd"], a["hc_usd"], a["loser_usd"]), (400, 400, 300))   # 400 / usual 100 = 4x: starred
        self.assertEqual(a["unproven_usd"], 1000)                         # 0xh collapsed to its larger side, unknown to the ledger
        self.assertEqual(b["unproven_usd"], 900)                          # $100 is under the floor
        self.assertEqual((a["pct_of_sharp"], a["proven"]["w"], a["proven"]["l"]), (100, 15, 5))
        self.assertTrue(a["list"][0]["star"])

    def test_lock_gates_and_units(self):
        rows = proven("0xp", n=20)
        c = C.card(kf([("m1", 1, "0xp", 350)], px=(0.6, 0.4)), ledger(rows), "nba")
        lk = c["markets"]["ml"]["lock_shadow"]["all"]
        self.assertEqual((lk["side"], lk["price"], lk["units_clean_ladder"]), ("B", 0.4, 1))   # a dog is capped at 1u
        rows2 = rows + proven("0xq")
        c2 = C.card(kf([("m1", 1, "0xp", 350), ("m1", 0, "0xq", 300)]), ledger(rows2), "nba")
        self.assertIsNone(c2["markets"]["ml"]["lock_shadow"]["all"]["side"])                    # proven money on both sides
        c3 = C.card(kf([("m1", 0, "0xp", 120 * 3)]), ledger(proven("0xp", n=10)), "nba")
        self.assertIsNone(c3["markets"]["ml"]["lock_shadow"]["all"]["side"])                    # presser has n < 15
        c4 = C.card(kf([("m1", 1, "0xp", 350), ("m1", 0, "0xu", 600)]), ledger(rows), "nba")
        lk4 = c4["markets"]["ml"]["lock_shadow"]["all"]
        self.assertIsNone(lk4["side"])                                                          # 350 / 950 of ALL money < 60%
        self.assertEqual(lk4["gates"], None)

    def test_spread_lock_uses_the_rung_with_most_proven_money(self):
        c = C.card(kf([("s1", 1, "0xp", 200), ("s2", 1, "0xp", 400)]), ledger(proven("0xp")), "nba")
        lk = c["markets"]["spread"]["lock_shadow"]["all"]
        self.assertEqual((lk["side"], lk["cid"], lk["line"], lk["price"]), ("A", "s2", -4.5, 0.55))
        self.assertEqual(c["markets"]["spread"]["sides"]["A"]["all"]["sharp_usd"], 400)        # largest single rung, not 600

    def test_forward_variant_has_no_proven_from_backfill(self):
        c = C.card(kf([("m1", 0, "0xp", 400)]), ledger(proven("0xp")), "nba")
        self.assertEqual(c["markets"]["ml"]["sides"]["A"]["fwd"]["sharp_usd"], 0)
        self.assertIsNone(c["markets"]["ml"]["lock_shadow"]["fwd"]["side"])

    def test_vault_join_and_gap_flag(self):
        games = [{"key": "nba:1", "start": CUT + 900 - 1200, "pm": {"slug": "nba-a-b-2027-01-15"}, "away": {"abbr": "A"}, "home": {"abbr": "B"}}]
        v = C.vault_join(games, "nba-a-b-2027-01-15", CUT + 900)
        self.assertEqual((v["key"], v["start_gap_min"], v["start_gap_flag"]), ("nba:1", 20, True))
        self.assertIsNone(C.vault_join(games, "nba-x-y-2027-01-15", CUT))


class Score(unittest.TestCase):
    """The benchmark's AGS-Unified v12 side score and tier (the `ags` field)."""

    def test_quality_formula_and_bounds(self):
        b = {"flat_roi": 0.20, "roi": 0.10, "usual": 100.0, "n": 5}
        x = {"usd": 400.0, "s": {"all": b}}
        self.assertAlmostEqual(C.ags_quality(x, "all", "sharp"), 3 * 20 * 2.5 * (5 / 20) ** 0.5)    # size capped at 2.5, n under 20
        self.assertEqual(C.ags_quality(x, "all", "unproven"), 0.0)                                    # only proven wallets score
        b2 = {"flat_roi": -0.05, "roi": 0.80, "usual": 100.0, "n": 50}
        self.assertAlmostEqual(C.ags_quality({"usd": 10.0, "s": {"all": b2}}, "all", "hc"), 3 * 30 * 0.5 * 1)   # dollar ROI fallback, capped

    def test_tiers_use_the_published_cut_points(self):
        got = [C.ags_tier(v) for v in (None, -0.2, 0, 0.5, 0.781, 0.8, 0.92, 0.96, 0.99)]
        self.assertEqual(got, [None, "FADE", "FADE", "WEAK", "WEAK", "LEAN", "LOCK", "PREMIUM", "ELITE"])

    def test_side_score_is_mean_for_against(self):
        mk = lambda w, side, usd, flat, n=20: {"w": w, "side": side, "usd": usd, "s": {"all": {"flat_roi": flat, "roi": flat, "usual": 100.0, "n": n}}}
        ws = [mk("a", "X", 100, 0.10), mk("b", "X", 100, 0.0), mk("c", "Y", 100, 0.0), mk("d", "Y", 100, 0.5, n=0), mk("e", "X", 900, 0.3)]
        cls = {"a": "sharp", "b": "unproven", "c": "loser", "d": "unproven", "e": "excluded"}
        g = C.ags_side("X", ws, cls, "all")                       # for: a = 3*10*1*1 = 30 and b = 0, mean 15; against: c = 0 (d has no book)
        self.assertEqual((g["for_n"], g["against_n"], g["contributors"]), (2, 1, 1))
        self.assertAlmostEqual(g["score"], round(15 / 15.5, 3))
        self.assertEqual(g["tier"], "PREMIUM")
        y = C.ags_side("Y", ws, cls, "all")
        self.assertEqual((y["tier"], y["score"]), ("FADE", round(-15 / 15.5, 3)))
        self.assertIsNone(C.ags_side("X", [mk("d", "X", 100, 0.5, n=0)], {"d": "unproven"}, "all"))


class StakeRungs(unittest.TestCase):
    """scripts/sf_rungs.py: the benchmark's press ladder, rescue rungs and trust layer, ported."""

    @staticmethod
    def w(d, usd=1000, ratio=1.0, n=20, wr=60.0, door2=False, streak=0, trust=None, trust_mkt=None):
        return {"dir": d, "invested": usd, "ratio": ratio, "n": n, "wr": wr, "door2": door2, "streak": streak, "trust": trust, "trust_mkt": trust_mkt}

    def test_press_clean_and_bands(self):
        import sf_rungs as S
        rows = [self.w("FOR", 3000, ratio=2.5, door2=True), self.w("AG", 1000)]
        self.assertEqual(S.evaluate(rows, "spread", 0.55, 0.9)["units"], 2.0)          # band 4 clean is cut to 2u
        rows[0]["ratio"] = 3.2
        self.assertEqual((S.evaluate(rows, "ml", 0.55, 0.9)["rung"], S.evaluate(rows, "ml", 0.55, 0.9)["units"]), ("PRESS", 5.0))
        self.assertEqual(S.evaluate(rows, "ml", 0.45, 0.9)["units"], 1.0)               # a dog is capped at 1u
        rows[1]["invested"] = 5000                                                       # money share under 60%
        self.assertEqual(S.evaluate(rows, "ml", 0.55, 0.9)["units"], 0.0)

    def test_press_x_n_u_and_r6(self):
        import sf_rungs as S
        x = [self.w("FOR", 3000, ratio=2.0, door2=True), self.w("FOR", 500, door2=True, ratio=1.0), self.w("AG", 500, door2=True, ratio=0.5)]
        self.assertEqual(S.evaluate(x, "ml", 0.55, 0.5)["rung"], "PRESS-X")
        n = [self.w("FOR", 3000, ratio=2.0, n=60), self.w("AG", 500)]
        self.assertEqual((S.evaluate(n, "ml", 0.55, 0.5)["rung"], S.evaluate(n, "ml", 0.55, 0.5)["units"]), ("PRESS-N", 3.0))
        n[0]["n"] = 30                                                                   # a 30-bet presser does not carry PRESS-N
        self.assertEqual(S.evaluate(n, "ml", 0.55, 0.5)["units"], 0.0)
        r6 = [self.w("FOR", 1500, ratio=1.0), self.w("FOR", 1500, ratio=1.1), self.w("AG", 500)]
        self.assertEqual(S.evaluate(r6, "ml", 0.55, 0.5)["rung"], "PRESS-R6")

    def test_trust_status_and_trust_rungs(self):
        import sf_rungs as S
        day = 86400
        cut = CUT
        bets = [(cut - day * (40 - i), 0.5, i % 4 != 0) for i in range(30)]               # 75% wins at 50 cents: edge +25 points
        t = S.trust_state(bets, cut)
        self.assertEqual((t["tier"], t["status"], t["n"]), (5, "STABLE_ON", 30))
        self.assertTrue(S.trusted(t))
        young = S.trust_state([(cut - day * 3 + i, 0.5, True) for i in range(12)], cut)    # a book under 15 days old is not trusted
        self.assertFalse(S.trusted(young))
        rows = [self.w("FOR", 500, trust=t), self.w("AG", 500)]
        g = S.evaluate(rows, "ml", 0.55, 0.3)                                              # gate fails, score positive, trusted wallet FOR
        self.assertEqual((g["rung"], g["units"]), ("TRUST-G", 4.0))                       # the moneyline floor lifts 3u to 4u in the .50-.65 window
        self.assertEqual(S.evaluate(rows, "ml", 0.55, -0.1)["units"], 0.0)                 # no positive score, no TRUST-G
        sp = [self.w("FOR", 500, trust_mkt=t), self.w("AG", 500, trust_mkt=t)]
        self.assertTrue(S.evaluate(sp, "spread", 0.55, 0.3)["reason"].startswith("trust_s_veto"))   # a trusted wallet against vetoes a spread

    def test_caps_and_mutes(self):
        import sf_rungs as S
        rows = [self.w("FOR", 3000, ratio=3.5, door2=True), self.w("AG", 1000)]
        self.assertEqual(S.evaluate(rows, "spread", 0.55, 0.9)["units"], 2.5)             # spread cap
        self.assertEqual(S.evaluate(rows, "total", 0.55, 0.9)["units"], 2.0)              # totals cap
        self.assertEqual(S.evaluate(rows, "ml", 0.85, 0.9)["reason"], "heavy_favourite_mute")
        self.assertEqual(S.evaluate(rows, "ml", 0.55, -0.5)["reason"], "score_not_positive")


class ReviewFixes(unittest.TestCase):
    def test_wallet_selected_after_the_cut_is_untracked(self):
        rows = proven("0xp")
        late = ledger(rows, first_seen={"0xp": CUT + 3600})
        s = late.stats("0xp", CUT)
        self.assertEqual((s["tracked"], s["all"]["n"], s["all"]["proven"]), (False, 0, False))
        c = C.card(kf([("m1", 0, "0xp", 400)]), late, "nba")
        self.assertEqual(c["markets"]["ml"]["sides"]["A"]["all"]["unproven_usd"], 400)

    def test_rungs_of_one_side_are_one_position(self):
        mk = {f"r{i}": {"slug": f"nba-a-b-2026-10-0{i // 3 + 1}-spread-{i}", "outs": ["A", "B"]} for i in range(6)}
        rows = [dict(row("0xr", i, "win", cid=f"r{i}"), mt="spreads") for i in range(6)]       # 3 rungs x 2 games
        b = ledger(rows, markets=mk).stats("0xr", CUT)["all"]
        self.assertEqual((b["n"], b["w"], b["proven"]), (2, 2, False))                          # 2 bets, not 6

    def test_sub_floor_rungs_are_not_summed(self):
        c = C.card(kf([("s1", 1, "0xp", 200), ("s2", 1, "0xp", 200)]), ledger(proven("0xp")), "nba")
        self.assertNotIn("spread", c["markets"])                                               # each rung under $250

    def test_ladder_units_and_dog_cap(self):
        self.assertEqual([C.ladder_units(x, 0.6) for x in (1.6, 2.5, 3.2)], [3, 2, 5])
        self.assertEqual(C.ladder_units(3.2, 0.45), 1)                                         # any market, price < 0.50

    def test_balanced_dust_is_dropped(self):
        rows = proven("0xp", stake=1000)                                                       # usual stake 1000
        c = C.card(kf([("m1", 0, "0xp", 600), ("m1", 1, "0xp", 400)]), ledger(rows), "nba")
        self.assertNotIn("ml", c["markets"])
        self.assertEqual(c["coverage"]["two_way_dust_dropped"], 1)

    def test_test_eligibility(self):
        k = kf([("m1", 0, "0xp", 400)])                                                         # game in the future
        self.assertTrue(C.card(k, ledger(proven("0xp")), "nba")["test"]["counts"])
        past = dict(k, gst=1_000_000_900, cut=1_000_000_000)
        rows = [dict(r, settled_at=900_000_000 + i) for i, r in enumerate(proven("0xp"))]
        late = C.card(past, ledger(rows, first_seen={"0xp": 1}, run_at=999_000_000), "nba")
        self.assertEqual(late["test"], {"counts": False, "why_not": ["built after game start"]})
        stale = C.card(k, ledger(proven("0xp"), run_at=None), "nba")
        self.assertEqual(stale["test"]["why_not"], ["ledger run not before the cut"])
        cbb = C.card(k, ledger(proven("0xp")), "cbb")                                          # not in docs/sharp-card-prereg.md
        self.assertEqual(cbb["test"], {"counts": False, "why_not": ["sport not in a registered test"]})


class Detail(unittest.TestCase):
    """The play-detail fields: price skill from stored closes, the at-this-size record, the first-flagged price."""
    def test_price_skill_counts_bets_bought_below_the_stored_close(self):
        rows = [dict(row("0xa", i, "win"), avg=0.50) for i in range(4)]
        closes = {(r["cid"], 0): (0.55 if i < 3 else 0.45) for i, r in enumerate(rows)}      # 3 bought below the close, 1 above
        L = C.Ledger(rows, {}, {"0xa": CUT - 86400 * 100}, [], CUT - 3600, closes)
        b = L.stats("0xa", CUT)["all"]
        self.assertEqual((b["clv_n"], b["clv_beat"]), (4, 3))
        self.assertAlmostEqual(b["clv_mean"], (0.05 * 3 - 0.05) / 4)

    def test_split_positions_are_left_out_of_price_skill(self):
        rows = [dict(row("0xa", 0, "win", split=True), avg=0.5), dict(row("0xa", 1, "win"), avg=0.4)]
        closes = {(r["cid"], 0): 0.6 for r in rows}
        b = C.Ledger(rows, {}, {"0xa": CUT - 86400 * 100}, [], CUT - 3600, closes).stats("0xa", CUT)["all"]
        self.assertEqual(b["clv_n"], 1)

    def test_no_close_means_no_price_skill(self):
        b = ledger([dict(row("0xa", 0, "win"), avg=0.5)]).stats("0xa", CUT)["all"]
        self.assertEqual((b["clv_n"], b["clv_mean"]), (0, None))

    def test_closes_from_keyframe_need_a_fresh_price_and_pm_closes_need_identical_outcomes(self):
        import json, tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "nba", "frozen", "x"))
            with open(os.path.join(d, "nba", "frozen", "x", "k.json"), "w") as f:
                json.dump({"cut": CUT, "mk": {"fresh": {"px": [0.6, 0.4], "px_t": CUT - 60},
                                              "stale": {"px": [0.6, 0.4], "px_t": CUT - C.CLOSE_STALE - 1}}}, f)
            with open(os.path.join(d, "nba", "frozen", "x", "j.json"), "w") as f:     # postponed: a later cut for the same market
                json.dump({"cut": CUT + 86400, "mk": {"fresh": {"px": [0.7, 0.3], "px_t": CUT + 86400 - 60}}}, f)
            markets = {"m1": {"slug": "nba-a-b-2026-11-11", "mt": "spreads", "line": -4.5, "outs": ["A", "B"]},
                       "m2": {"slug": "nba-a-b-2026-11-11", "mt": "spreads", "line": -4.5, "outs": ["B", "A"]}}
            pmc = {"games": {"nba|nba-a-b-2026-11-11": {"spreads": [{"line": -4.5, "outcomes": ["A", "B"], "p": 0.52}]}}}
            got = C.load_closes(d, "nba", markets, pmc)
        self.assertEqual(got[("fresh", 1)], 0.3)                # the latest cut wins
        self.assertNotIn(("stale", 0), got)
        self.assertAlmostEqual(got[("m1", 1)], 0.48)
        self.assertNotIn(("m2", 0), got)                     # outcome order differs: not the same market

    def test_at_size_band(self):
        b = {"usual": 100.0, "sizes": [[50, True], [90, True], [110, False], [200, True], [400, False]]}
        a = C.at_size(b, 1.2)                                # 0.75x to 1.5x band: the 90 and 110 positions
        self.assertEqual((a["lo"], a["hi"], a["w"], a["l"], a["share"]), (0.75, 1.5, 1, 1, 0.4))
        self.assertEqual(C.at_size(b, 3.7)["hi"], None)      # 3x and up is open-ended

    def test_flagged_price_is_carried_while_the_side_holds(self):
        new = {"markets": {"ml": {"sf": {"all": {"side": "A", "price": 0.6}}, "lock_shadow": {}}}}
        old = {"markets": {"ml": {"sf": {"all": {"side": "A", "flagged": {"price": 0.55, "t": 1}}}}}}
        C.carry_flagged(new, old, 99)
        self.assertEqual(new["markets"]["ml"]["sf"]["all"]["flagged"], {"price": 0.55, "t": 1})
        flip = {"markets": {"ml": {"sf": {"all": {"side": "B", "price": 0.4}}}}}
        C.carry_flagged(flip, old, 99)
        self.assertEqual(flip["markets"]["ml"]["sf"]["all"]["flagged"], {"price": 0.4, "t": 99})
        moved = {"markets": {"ml": {"sf": {"all": {"side": "A", "price": 0.5, "cid": "other-rung", "price_t": 77}}}}}
        C.carry_flagged(moved, old, 99)                      # same team, different market: flagged again, at its own price time
        self.assertEqual(moved["markets"]["ml"]["sf"]["all"]["flagged"], {"price": 0.5, "t": 77})
        frozen = {"markets": {"ml": {"sf": {"all": {"side": "B", "price": 0.4}}}}}
        C.carry_flagged(frozen, None, None)                  # a frozen card only inherits
        self.assertNotIn("flagged", frozen["markets"]["ml"]["sf"]["all"])


class BenchmarkExclusions(unittest.TestCase):
    """Variant `sfx`: The benchmark's published exclusion list replaces Vault's hedger and churn rules; `all` and `fwd` are unchanged."""
    def hedger_rows(self):
        # a proven wallet that held both sides of 10 of its 20 markets: Vault's hedger rule excludes it
        rows = proven("0xh")
        for i in range(10):
            rows.append(dict(row("0xh", i, "loss", stake=1.0), oi=1, hedged=True, cid=f"0xh-c{i}"))
        return rows

    def test_no_list_means_no_sfx_variant(self):
        c = C.card(kf([("m1", 0, "0xh", 500)]), ledger(self.hedger_rows()), "nba")
        self.assertNotIn("sfx", c["markets"]["ml"]["sides"]["A"])
        self.assertEqual(c["sf_excluded_n"], 0)

    def test_vault_hedger_counts_under_benchmark_list(self):
        L = ledger(self.hedger_rows())
        L.sf_excluded = {"0xother"}
        c = C.card(kf([("m1", 0, "0xh", 500)]), L, "nba")
        A = c["markets"]["ml"]["sides"]["A"]
        self.assertEqual(A["all"]["excluded_usd"], 500)                  # Vault's rule: a hedger
        self.assertEqual((A["sfx"]["sharp_usd"], A["sfx"]["excluded_usd"]), (500, 0))   # The benchmark's list: proven money
        self.assertEqual(A["sfx"]["list"], [])                           # the shadow keeps money and score, not the lists

    def test_wallet_on_benchmark_list_is_excluded_even_untracked(self):
        L = ledger(proven("0xp"))
        L.sf_excluded = {"0xp", "0xstranger"}
        c = C.card(kf([("m1", 0, "0xp", 400), ("m1", 1, "0xstranger", 900)]), L, "nba")
        m = c["markets"]["ml"]["sides"]
        self.assertEqual((m["A"]["all"]["sharp_usd"], m["A"]["sfx"]["excluded_usd"]), (400, 400))
        self.assertEqual((m["B"]["all"]["unproven_usd"], m["B"]["sfx"]["excluded_usd"]), (900, 900))


if __name__ == "__main__":
    unittest.main()
