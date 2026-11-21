"""Unit tests for the V2 account fields of the wallets file (docs/sharps-v2-accounts-spec.md): scripts/build_side_cards.py.

Small synthetic ledgers only; no network and no stored data. Run from the repo root:
    python3 -m unittest tests.test_sharps_v2_wallets
The one test that needs the real Nov 21 file (size budget) runs only when SHARPS_V2_WALLETS points at a built wallets.json; the workflow
runs the same gate on every built file (scripts/sharps_v2/check_size.py) before it publishes.
"""
import copy, datetime as dt, json, os, random, subprocess, sys, tempfile, unittest
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import build_side_cards as C  # noqa: E402
import pm_clv_tiers as CT  # noqa: E402

NOW = 1_795_278_075                      # 2026-11-21 10:21 AM Central, the build the spec measured
DAY = 86400
TZ = ZoneInfo("America/Chicago")
FLOOR = 250


def row(w, i, res, stake=300.0, settled=None, src="backfill", hedged=False, split=False, cid=None, first=None, oi=0, mt="moneyline", avg=0.5):
    pnl = stake * 0.9 if res == "win" else -stake if res == "loss" else 0.0
    st = settled if settled is not None else NOW - DAY * 20 + i * 3600
    return {"w": w, "cid": cid or f"{w}-c{i}", "oi": oi, "mt": mt, "res": res, "stake": stake, "pnl": pnl, "avg": avg, "settled_at": st,
            "first": first if first is not None else st - 7200, "gst": st - 3600, "src": src, "hedged": hedged, "split": split}


def ledger(rows, first_seen=None, markets=None):
    fs = first_seen if first_seen is not None else {r["w"]: NOW - DAY * 100 for r in rows}
    return C.Ledger(rows, markets or {}, fs, [], NOW - 3600)


def pos(i, usd=900, g="ml", side="A", ev="nba-a-b-2026-11-21", px_t=NOW - 600, gst=NOW + 7200):
    return {"sport": "nba", "ev": ev, "gst": gst, "g": g, "side": side, "line": None, "cid": f"m{i}", "usd": usd, "shares": 10.0, "px": 0.5,
            "px_t": px_t, "press": 1.0, "since": NOW - 100, "cens": False, "two_way": False}


def listed_wallet(fl, w, positions=(), name="Name", sc=False, rk=None):
    s = fl.stats(w, NOW)
    return dict(C.wallet_book(s, name=name, sheet=bool(positions)), positions=list(positions), sc=sc, rk=C.rk_entry(rk))


class Tiers(unittest.TestCase):
    def test_tier_mapping(self):
        for old, new in (("sharp", "beats"), ("mid", "even"), ("dull", "loses"), ("thin", "few")):
            self.assertEqual(C.v2_tier({"tier": old, "n": 40}), new)

    def test_no_rk_is_too_few_never_a_tier(self):
        self.assertEqual(C.v2_tier(None), "few")                       # CFB, CBB, no CLV game, a fit with no params
        self.assertEqual(C.v2_tier({}), "few")
        self.assertEqual(C.v2_tier({"tier": "something-new"}), "few")

    def test_shrunk_estimate_is_carried_through_and_mean_stays_raw(self):
        rnd = random.Random(7)
        obs = {}
        for k in range(40):
            mu = 0.06 if k == 0 else rnd.gauss(0, 0.01)
            obs[f"0x{k:040x}"] = [(1_000 + g, rnd.gauss(mu, 0.05)) for g in range(40 if k else 60)]
        fit = CT.fit(obs, 10_000)["wallets"]
        w = "0x" + "0" * 40
        e = C.rk_entry(fit[w])
        self.assertEqual((e["post"], e["sd"]), (fit[w]["post"], fit[w]["sd"]))        # the module's own posterior, dropped before V2
        self.assertEqual((e["tier"], e["n"], e["mean"], e["p"]), (fit[w]["tier"], fit[w]["n"], fit[w]["mean"], fit[w]["p"]))
        self.assertNotEqual(e["post"], e["mean"])                                      # shrunk, not the raw mean
        self.assertLess(abs(e["post"]), abs(e["mean"]) + 1e-9)                         # toward the prior mean, never past it here
        self.assertEqual(C.v2_tier(e), "beats")
        self.assertIsNone(C.rk_entry(None))

    def test_only_two_keys_are_added_to_rk(self):
        t = {"tier": "mid", "n": 31, "mean": 0.01, "post": 0.004, "sd": 0.002, "p": 0.7}
        self.assertEqual(set(C.rk_entry(t)) - {"tier", "n", "mean", "p"}, set(C.V2_RK_KEYS))


class Books(unittest.TestCase):
    def test_forward_book_uses_src_not_a_date_cutoff(self):
        """Spec section 3: the 2026-11-16 12:00 AM Central line is the shadow rules' card cutoff, not the wallet forward cutoff. A wallet's
        forward record is its own `src == forward` rows, whatever day they settled."""
        cutoff = int(dt.datetime(2026, 11, 16, tzinfo=TZ).timestamp())
        self.assertEqual(cutoff, 1794808800)
        rows = [row("0xf", 0, "win", src="forward", settled=cutoff - 3 * DAY),             # forward, before the cutoff: counts
                row("0xf", 1, "loss", src="forward", settled=cutoff + DAY),                 # forward, after: counts
                row("0xf", 2, "win", src="backfill", settled=cutoff + 2 * DAY),             # backfill after the cutoff: never forward
                row("0xf", 3, "win", src="forward", settled=cutoff + DAY, hedged=True)]     # hedged: out of every record
        s = ledger(rows).stats("0xf", NOW)
        f = C.fwd_book(s["fwd"])
        self.assertEqual((f["w"], f["l"], f["n"]), (1, 1, 2))
        self.assertEqual(s["all"]["n"], 3)
        self.assertEqual(set(f), {"w", "l", "p", "n", "pnl", "roi", "flat_roi", "clv_n", "clv_mean"})
        self.assertAlmostEqual(f["pnl"], 300 * 0.9 - 300, places=2)

    def test_forward_book_of_a_wallet_with_no_forward_rows_is_zero_not_null_counts(self):
        f = C.fwd_book(ledger([row("0xb", 0, "win")]).stats("0xb", NOW)["fwd"])
        self.assertEqual((f["n"], f["w"], f["l"]), (0, 0, 0))
        self.assertIsNone(f["roi"])                                     # not computable: null, never 0
        self.assertIsNone(f["clv_mean"])

    def test_flat_roi_is_mean_of_per_bet_returns(self):
        rows = [row("0xr", 0, "win", stake=100), row("0xr", 1, "loss", stake=900)]
        fl = ledger(rows)
        w = {"0xr": dict(C.wallet_book(fl.stats("0xr", NOW)), positions=[])}
        C.apply_v2("nba", w, fl, NOW, {}, {}, {}, {}, {}, {})
        s = fl.stats("0xr", NOW)["all"]
        self.assertEqual(w["0xr"]["flat_roi"], round((0.9 - 1.0) / 2, 4))
        self.assertLess(s["roi"], s["flat_roi"])                         # dollar ROI weights the big loss; flat ROI does not

    def test_usual_med_floor_split_and_none(self):
        rows = [row("0xm", 0, "win", stake=100), row("0xm", 1, "win", stake=300), row("0xm", 2, "loss", stake=500),
                row("0xm", 3, "win", stake=5000, split=True), row("0xm", 4, "win", stake=700)]
        ps = C.positions(rows, {})
        self.assertEqual(C.stake_median(ps, FLOOR), 500)               # 300, 500, 700 (the $100 is under the floor, the split is not cash)
        self.assertEqual(C.stake_median(ps, 100), 400)                 # CBB floor: 100, 300, 500, 700
        self.assertIsNone(C.stake_median(ps, 1e9))

    def test_last_settled_and_n30_games(self):
        mk = {"a": {"slug": "nba-x-y-2026-11-20", "mt": "moneyline", "outs": ["X", "Y"]},
              "b": {"slug": "nba-x-y-2026-11-20", "mt": "spreads", "outs": ["X", "Y"], "line": 3.5},
              "c": {"slug": "nba-p-q-2026-11-19", "mt": "moneyline", "outs": ["P", "Q"]},
              "d": {"slug": "nba-r-s-2026-11-18", "mt": "moneyline", "outs": ["R", "S"]},
              "e": {"slug": "nba-t-u-2026-09-01", "mt": "moneyline", "outs": ["T", "U"]}}
        rows = [row("0xn", 0, "win", cid="a", settled=NOW - DAY), row("0xn", 1, "loss", cid="b", settled=NOW - DAY + 5),   # one game, two bets
                row("0xn", 2, "push", cid="c", settled=NOW - 2 * DAY),                                                       # a push is not decided
                row("0xn", 3, "win", cid="d", settled=NOW - 29 * DAY),
                row("0xn", 4, "win", cid="e", settled=NOW - 45 * DAY)]
        ps = ledger(rows, markets=mk).stats("0xn", NOW)["all"]["_ps"]
        last, n30 = C.settled_reads(ps, NOW)
        self.assertEqual((last, n30), (NOW - DAY + 5, 2))
        self.assertEqual(C.settled_reads([], NOW), (None, 0))
        self.assertEqual(C.settled_reads(ps, NOW - 60 * DAY)[1], 0)    # nothing settled in that window

    def test_n30_window_boundaries_are_lo_inclusive_now_exclusive(self):
        mk = {c: {"slug": f"nba-x-y-2026-10-{i:02d}", "mt": "moneyline", "outs": ["X", "Y"]} for i, c in enumerate("abc", start=10)}
        rows = [row("0xn", 0, "win", cid="a", settled=NOW - 30 * DAY),           # exactly now - 30 d: in
                row("0xn", 1, "win", cid="b", settled=NOW - 30 * DAY - 1),       # one second earlier: out
                row("0xn", 2, "win", cid="c", settled=NOW)]                      # exactly now: out (an open interval, nothing settles "at" the build)
        ps = C.positions(rows, mk)
        self.assertEqual(C.settled_reads(ps, NOW)[1], 1)
        self.assertEqual(C.settled_reads(ps, NOW)[0], NOW)                       # last_settled has no window


class SinceList(unittest.TestCase):
    def setUp(self):
        self.mk = {"a": {"slug": "nba-x-y-2026-11-20", "mt": "spreads", "outs": ["X", "Y"], "line": 3.5},
                   "b": {"slug": "nba-x-y-2026-11-20", "mt": "spreads", "outs": ["X", "Y"], "line": 4.5}}

    def test_window_floor_hedge_split_and_flat(self):
        rows = [row("0xs", 0, "win", stake=300, settled=NOW - 3 * DAY, first=NOW - 4 * DAY),
                row("0xs", 1, "loss", stake=200, settled=NOW - 4 * DAY),                          # under the floor: out
                row("0xs", 2, "win", stake=400, settled=NOW - 61 * DAY),                          # before since_from: out
                row("0xs", 3, "win", stake=400, settled=NOW - 5 * DAY, hedged=True),              # hedged: out
                row("0xs", 4, "win", stake=800, settled=NOW - 6 * DAY, split=True),               # split: in, flat null
                row("0xs", 5, "push", stake=500, settled=NOW - 7 * DAY),
                row("0xs", 6, "loss", stake=500, settled=NOW + 10)]                               # at or after built: out
        ps = ledger(rows).stats("0xs", NOW)["all"]["_ps"]
        sl = C.since_list(ps, FLOOR, NOW)
        self.assertEqual([x[2] for x in sl], [1, 1, 2])                                           # newest first
        self.assertEqual([x[3] for x in sl], [0.9, None, 0.0])
        self.assertTrue(all(NOW - 60 * DAY <= x[0] < NOW for x in sl))
        self.assertEqual(sl[0][1], NOW - 4 * DAY)                                                 # first_fill
        self.assertEqual(sl[0][3], 0.9)
        self.assertTrue(all(len(x) == 6 for x in sl))                                             # [settled_at, first_fill, r, flat, ev, stake]
        self.assertEqual([x[5] for x in sl], [300, 800, 500])
        self.assertTrue(all(isinstance(x[4], str) for x in sl))

    def test_floor_and_window_boundaries(self):
        rows = [row("0xs", 0, "win", stake=FLOOR, settled=NOW - 2 * DAY),                      # exactly the floor: in
                row("0xs", 1, "win", stake=FLOOR - 0.01, settled=NOW - 3 * DAY),               # a cent under: out
                row("0xs", 2, "win", settled=NOW - 60 * DAY),                                   # exactly built - 60 d: in ([since_from, built))
                row("0xs", 3, "win", settled=NOW - 60 * DAY - 1),                               # one second before: out
                row("0xs", 4, "win", settled=NOW - 1),                                          # one second before built: in
                row("0xs", 5, "win", settled=NOW)]                                              # exactly built: out
        ps = ledger(rows).stats("0xs", NOW + 5)["all"]["_ps"]
        sl = C.since_list(ps, FLOOR, NOW)
        self.assertEqual(sorted(x[0] for x in sl), [NOW - 60 * DAY, NOW - 2 * DAY, NOW - 1])

    def test_a_game_with_two_bets_is_two_items_and_one_game(self):
        """The unit is a position: a spread and a moneyline on one game are two items, so the page must say bets, and can count games."""
        mk = {"a": {"slug": "nba-x-y-2026-11-20", "mt": "moneyline", "outs": ["X", "Y"]},
              "b": {"slug": "nba-x-y-2026-11-20", "mt": "spreads", "outs": ["X", "Y"], "line": 3.5},
              "c": {"slug": "nba-p-q-2026-11-19", "mt": "moneyline", "outs": ["P", "Q"]}}
        rows = [row("0xs", 0, "win", cid="a", stake=400, settled=NOW - DAY), row("0xs", 1, "loss", cid="b", stake=900, settled=NOW - DAY, mt="spreads"),
                row("0xs", 2, "loss", cid="c", stake=300, settled=NOW - 2 * DAY)]
        sl = C.since_list(ledger(rows, markets=mk).stats("0xs", NOW)["all"]["_ps"], FLOOR, NOW)
        self.assertEqual(len(sl), 3)
        self.assertEqual(len({x[4] for x in sl}), 2)                                   # two games
        self.assertEqual(C.games_tally(sl), (0, 2, 2))                                 # the game's biggest position (the $900 loss) is its leg
        self.assertEqual(C.games_tally([]), (0, 0, 0))

    def test_first_fill_is_the_earliest_rung_and_rungs_are_one_position(self):
        rows = [row("0xs", 0, "win", cid="a", stake=200, settled=NOW - DAY, first=NOW - 5000, mt="spreads"),
                row("0xs", 1, "win", cid="b", stake=200, settled=NOW - DAY + 60, first=NOW - 9000, mt="spreads")]
        ps = ledger(rows, markets=self.mk).stats("0xs", NOW)["all"]["_ps"]
        self.assertEqual(len(ps), 1)
        sl = C.since_list(ps, FLOOR, NOW)                         # 200 + 200 = 400 clears the floor only as one position
        self.assertEqual(len(sl), 1)
        self.assertEqual((sl[0][1], sl[0][2], sl[0][3]), (NOW - 9000, 1, 0.9))
        self.assertEqual(C.since_list(ps, 500, NOW), [])

    def test_cbb_floor_is_lower(self):
        rows = [row("0xs", 0, "win", stake=150, settled=NOW - DAY)]
        ps = ledger(rows).stats("0xs", NOW)["all"]["_ps"]
        self.assertEqual(C.since_list(ps, C.FOLLOW_FLOOR["cbb"], NOW)[0][2], 1)
        self.assertEqual(C.since_list(ps, C.FLOOR_USD, NOW), [])

    def test_missing_first_is_null_not_invented(self):
        r = row("0xs", 0, "win", settled=NOW - DAY)
        del r["first"]
        ps = ledger([r]).stats("0xs", NOW)["all"]["_ps"]
        self.assertIsNone(C.since_list(ps, FLOOR, NOW)[0][1])


class Sides(unittest.TestCase):
    def test_rung_totals_and_press(self):
        ps = [pos(0, usd=1000, g="spread"), pos(1, usd=500, g="spread"), pos(2, usd=250, g="spread"), pos(3, usd=700, g="spread", side="B"),
              pos(4, usd=900, g="ml")]
        C.side_fields(ps, 500)
        self.assertEqual([(p["side_usd"], p["side_rungs"], p["side_press"]) for p in ps],
                         [(1750, 3, 3.5)] * 3 + [(700, 1, 1.4), (900, 1, 1.8)])
        self.assertEqual(ps[0]["side_usd"], sum(p["usd"] for p in ps[:3]))                       # equals the sum of its rungs' usd

    def test_side_press_is_null_without_a_median(self):
        ps = [pos(0)]
        C.side_fields(ps, None)
        self.assertEqual((ps[0]["side_usd"], ps[0]["side_rungs"], ps[0]["side_press"]), (900, 1, None))

    def test_a_side_is_per_game(self):
        ps = [pos(0, ev="nba-a-b-2026-11-21"), pos(1, ev="nba-c-d-2026-11-21")]
        C.side_fields(ps, 100)
        self.assertEqual([p["side_rungs"] for p in ps], [1, 1])

    def test_a_side_is_per_start_time_too(self):
        ps = [pos(0, gst=NOW + 100), pos(1, gst=NOW + 200)]                              # same event, market group and side, two start times
        C.side_fields(ps, 100)
        self.assertEqual([p["side_rungs"] for p in ps], [1, 1])

    def test_price_age_minutes(self):
        ps = [pos(0, px_t=NOW - 90), pos(1, px_t=NOW - 6 * 3600), pos(2, px_t=None), pos(3, px_t=NOW), pos(4, px_t=NOW + 33)]
        C.px_age(ps, NOW)
        self.assertEqual([p["px_age_min"] for p in ps], [2, 360, None, 0, 0])      # a price logged after the build (a pinned --now) is 0, never negative


class Names(unittest.TestCase):
    W = "0xabcdef0123456789abcdef0123456789abcdef01"

    def test_hex_like(self):
        for n in (None, "", "0x" + "a" * 20, "0xD3dE95627dE3D2Cf37b6808E46749A9c7595e9Bd-1779261135644"):
            self.assertTrue(C.is_hex_name(n), n)
        for n in ("Putput", "0xBob", "0x" + "a" * 19):
            self.assertFalse(C.is_hex_name(n), n)

    def test_listed_name_passes_and_hex_never_does(self):
        self.assertEqual(C.name_fields(self.W, "Putput", "keyframe", {}), ("Putput", "keyframe"))
        hist = {self.W: (5, "Older", "universe")}
        self.assertEqual(C.name_fields(self.W, "0x" + "b" * 30, "keyframe", hist), ("Older", "universe"))
        self.assertEqual(C.name_fields(self.W, None, None, hist), ("Older", "universe"))

    def test_fallback_is_unnamed_with_short_address(self):
        d, src = C.name_fields(self.W, None, None, {})
        self.assertEqual((d, src), ("Unnamed 0xabcd...ef01", "none"))
        self.assertIsNotNone(d)

    def test_history_takes_newest_non_hex_name_from_universe_and_keyframes(self):
        root, holders = tempfile.mkdtemp(), tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "universe"))
        os.makedirs(os.path.join(holders, "nba", "frozen", "2026-11-20"))
        w2, w3 = "0x" + "2" * 40, "0x" + "3" * 40
        for day, t, nm in (("2026-11-11", 100, "Old"), ("2026-11-12", 200, "0x" + "f" * 30)):
            with open(os.path.join(root, "universe", day + ".json"), "w") as f:
                json.dump({"selected_at": t, "wallets": {self.W: {"name": nm}, w3: {"name": None}}}, f)
        with open(os.path.join(holders, "nba", "frozen", "2026-11-20", "g@1.json"), "w") as f:
            json.dump({"written": 300, "cut": 299, "names": {self.W: "Newest", w2: "0x" + "9" * 24}}, f)
        h = C.name_history(root, holders)
        self.assertEqual(h[self.W], (300, "Newest", "keyframe"))     # newer than the universe name; the hex one at t=200 never counts
        self.assertNotIn(w2, h)                                       # only a hex-like name stored
        self.assertNotIn(w3, h)                                       # only nulls stored
        os.remove(os.path.join(holders, "nba", "frozen", "2026-11-20", "g@1.json"))
        self.assertEqual(C.name_history(root, holders)[self.W], (100, "Old", "universe"))
        with open(os.path.join(holders, "nba", "frozen", "2026-11-20", "tie.json"), "w") as f:
            json.dump({"written": 100, "names": {self.W: "Tie"}}, f)
        self.assertEqual(C.name_history(root, holders)[self.W], (100, "Tie", "keyframe"))      # equal times: the later-read source wins (>=)


class Scorecard(unittest.TestCase):
    def test_games_are_read_per_sport(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "pm_wallets_nba.json"), "w") as f:
            json.dump({"sharp": ["0xA"], "wallets": {"0xA": [14, 0.5, 0.1, 14, 30], "0xB": [9, 0.1, 0.1, 9, 12]}}, f)
        g = C.scorecard_games(d)
        self.assertEqual(g["nba"], {"0xa": 14, "0xb": 9})
        self.assertEqual((g["nfl"], g["cfb"], g["cbb"]), ({}, {}, {}))      # a missing file is empty, never an error
        self.assertEqual(C.scorecard_sharp(d)["nba"], {"0xa"})

    def test_sc_sport_is_this_sport_only_while_sc_stays_any_sport(self):
        w = "0xa"
        fl = ledger([row(w, 0, "win")])
        sc, games = {"nba": {w}, "nfl": set()}, {"nba": {w: 14}}
        nba = {w: listed_wallet(fl, w, sc=True)}
        nfl = {w: listed_wallet(fl, w, sc=True)}                           # V1 `sc`: on any sport's scorecard
        C.apply_v2("nba", nba, fl, NOW, {}, sc, games, {}, {}, {})
        C.apply_v2("nfl", nfl, fl, NOW, {}, sc, games, {}, {}, {})
        self.assertEqual((nba[w]["sc_sport"], nba[w]["sc_n"]), (True, 14))
        self.assertEqual((nfl[w]["sc_sport"], nfl[w]["sc_n"]), (False, None))   # the NFL row no longer wears the NBA badge
        self.assertTrue(nba[w]["sc"] and nfl[w]["sc"])                       # old key untouched

    def test_sc_n_needs_the_sharp_list_not_just_a_row_in_the_games_file(self):
        w = "0xa"
        fl = ledger([row(w, 0, "win")])
        x = {w: listed_wallet(fl, w)}
        C.apply_v2("nba", x, fl, NOW, {}, {"nba": set()}, {"nba": {w: 14}}, {}, {}, {})   # a row in this sport's games file, not on its sharp list
        self.assertEqual((x[w]["sc_sport"], x[w]["sc_n"]), (False, None))

    def test_sc_n_is_null_when_the_file_has_no_row(self):
        w = "0xa"
        fl = ledger([row(w, 0, "win")])
        x = {w: listed_wallet(fl, w)}
        C.apply_v2("nba", x, fl, NOW, {}, {"nba": {w}}, {"nba": {}}, {}, {}, {})
        self.assertEqual((x[w]["sc_sport"], x[w]["sc_n"]), (True, None))


class ApplyV2(unittest.TestCase):
    def setUp(self):
        rows = [row("0xp", i, "win" if i % 4 else "loss", settled=NOW - DAY * 30 + i * 7200, src="forward" if i > 12 else "backfill") for i in range(20)]
        self.fl = ledger(rows)
        self.w = "0xp"
        self.rk = {self.w: {"tier": "sharp", "n": 35, "mean": 0.012, "post": 0.008, "sd": 0.003, "p": 0.97}}
        self.v1 = {"0xp": listed_wallet(self.fl, "0xp", [pos(0, 900, "spread"), pos(1, 600, "spread"), pos(2, 400, "ml", side="B")],
                                        rk=self.rk["0xp"])}
        self.v1["0xp"]["name"] = "Putput"

    def test_back_compat_every_v1_key_unchanged(self):
        v2 = copy.deepcopy(self.v1)
        C.apply_v2("nba", v2, self.fl, NOW, self.rk, {}, {}, {"0xp": "Putput"}, {"0xp": "universe"}, {})
        e = v2["0xp"]
        added = (set(e) | {"rk." + k for k in e["rk"]} | {"pos." + k for k in e["positions"][0]}) - \
                (set(self.v1["0xp"]) | {"rk." + k for k in self.v1["0xp"]["rk"]} | {"pos." + k for k in self.v1["0xp"]["positions"][0]})
        want = set(C.V2_WALLET_KEYS) | {"pos." + k for k in C.V2_POSITION_KEYS}
        self.assertEqual(added, want)                                  # only the documented V2 keys appear (rk.post and rk.sd come from rk_entry)
        self.assertEqual(C.strip_v2({"sports": {"nba": v2}})["sports"]["nba"], C.strip_v2({"sports": {"nba": self.v1}})["sports"]["nba"])
        for k, v in self.v1["0xp"].items():                            # every old key keeps its value (the book is read at `now` in both)
            self.assertEqual(e[k], v, k) if k not in ("rk", "positions") else None
        for p0, p1 in zip(self.v1["0xp"]["positions"], e["positions"]):
            for k, v in p0.items():
                self.assertEqual(p1[k], v, k)
        self.assertEqual({k: e["rk"][k] for k in ("tier", "n", "mean", "p")}, {k: self.rk["0xp"][k] for k in ("tier", "n", "mean", "p")})

    def test_since_items_go_to_the_collector_not_the_wallet(self):
        v2, since = copy.deepcopy(self.v1), {}
        C.apply_v2("nba", v2, self.fl, NOW, self.rk, {}, {}, {"0xp": "Putput"}, {"0xp": "universe"}, {}, since=since)
        self.assertNotIn("since_list", v2["0xp"])
        self.assertEqual(set(since), {"0xp"})
        self.assertEqual(since["0xp"], C.since_list(self.fl.stats("0xp", NOW)["all"]["_ps"], FLOOR, NOW))
        self.assertGreater(len(since["0xp"]), 0)

    def test_values(self):
        v2 = copy.deepcopy(self.v1)
        C.apply_v2("nba", v2, self.fl, NOW, self.rk, {}, {}, {"0xp": "Putput"}, {"0xp": "universe"}, {})
        e = v2["0xp"]
        s = self.fl.stats("0xp", NOW)
        self.assertEqual(e["v2"], {"tier": "beats"})
        self.assertEqual(e["rk"]["post"], 0.008)
        self.assertEqual(e["fwd"]["n"], s["fwd"]["n"])
        self.assertGreater(e["fwd"]["n"], 0)
        self.assertEqual(e["first_seen"], NOW - DAY * 100)
        self.assertEqual(e["usual_med"], 300)
        self.assertEqual(e["flat_roi"], round(s["all"]["flat_roi"], 4))
        self.assertEqual((e["name_disp"], e["name_src"]), ("Putput", "universe"))
        self.assertEqual(e["exp_w"], e["dive"]["exp_w"])
        self.assertEqual(e["luck_p"], e["dive"]["all"][5])
        self.assertEqual(e["last_settled"], max(p["settled_at"] for p in s["all"]["_ps"]))
        self.assertEqual([p["side_rungs"] for p in e["positions"]], [2, 2, 1])
        self.assertEqual([p["side_press"] for p in e["positions"]], [5.0, 5.0, 1.33])
        self.assertEqual([p["px_age_min"] for p in e["positions"]], [10, 10, 10])

    def test_open_wallet_book_is_read_at_now_not_at_the_game_cut(self):
        """Audit bug 14: an open wallet's book used to be taken at its first game's cut (here, 3 days from now)."""
        cut = NOW + 3 * DAY
        stale = dict(C.wallet_book(self.fl.stats("0xp", cut), name="Putput", sheet=True), positions=[pos(0)], sc=False, rk=None)
        now_book = C.wallet_book(self.fl.stats("0xp", NOW), name="Putput", sheet=True)
        self.assertNotEqual(stale["l30"], now_book["l30"])             # the 30-day window moved with the cut
        C.apply_v2("nba", {"0xp": stale}, self.fl, NOW, {}, {}, {}, {}, {}, {})
        for k in ("w_", "l_", "n", "roi", "pnl", "usual", "l30_roi", "l30", "d30", "curve", "legs"):
            self.assertEqual(stale[k], now_book[k], k)

    def test_directory_wallet_without_positions_gets_empty_position_fields(self):
        w = {"0xp": listed_wallet(self.fl, "0xp")}
        C.apply_v2("nba", w, self.fl, NOW, {}, {}, {}, {}, {}, {})
        self.assertEqual(w["0xp"]["positions"], [])
        self.assertEqual(w["0xp"]["v2"], {"tier": "few"})                    # no rk
        self.assertIsNone(w["0xp"]["rk"])
        self.assertNotIn("l30", w["0xp"])                                    # the sheet block stays open-wallets only

    def test_wallet_with_no_name_and_no_rows_has_nulls_not_zeros(self):
        fl = ledger([], first_seen={})
        w = {"0xz" + "0" * 37: dict(C.wallet_book(fl.stats("0xz" + "0" * 37, NOW)), positions=[], sc=False, rk=None)}
        C.apply_v2("nba", w, fl, NOW, {}, {}, {}, {}, {}, {})
        e = next(iter(w.values()))
        self.assertEqual((e["first_seen"], e["last_settled"], e["usual_med"], e["flat_roi"], e["exp_w"], e["luck_p"]), (None,) * 6)
        self.assertEqual((e["n30_games"], e["name_src"]), (0, "none"))
        self.assertNotIn("since_list", e)                                    # the dated list lives in since.json, not the wallets file
        self.assertTrue(e["name_disp"].startswith("Unnamed 0xz"))


class Retained(unittest.TestCase):
    def test_carry_forward_from_a_v2_file(self):
        prev = {"v": 2, "built": NOW - 600, "sports": {"nba": {"a": {}, "b": {}}},
                "retained": {"nba": {"c": {"left_at": NOW - 10 * DAY}, "d": {"left_at": NOW - 61 * DAY}, "e": {"left_at": NOW - 5 * DAY}}}}
        out = C.retained_left("nba", {"b": {}, "e": {}}, prev, NOW, seed=lambda: self.fail("a V2 file never reseeds"))
        self.assertEqual(out, {"a": NOW, "c": NOW - 10 * DAY})        # a left now; c keeps left_at; d is past 60 days; b and e are listed
        self.assertNotIn("b", out)
        self.assertNotIn("e", out)                                    # a wallet back on the list is not retained

    def test_nothing_is_retained_past_60_days_and_never_a_listed_wallet(self):
        prev = {"v": 2, "sports": {"nba": {}}, "retained": {"nba": {"x": {"left_at": NOW - 60 * DAY}, "y": {"left_at": NOW - 60 * DAY - 1}}}}
        out = C.retained_left("nba", {}, prev, NOW, seed=dict)
        self.assertEqual(set(out), {"x"})
        self.assertTrue(all(NOW - t <= C.RETAIN_DAYS * DAY for t in out.values()))

    def test_first_build_seeds_when_the_previous_file_has_no_v2_keys(self):
        for prev in (None, {}, {"v": 1, "sports": {"nba": {"a": {}}}}):
            called = []
            out = C.retained_left("nba", {"z": {}}, prev, NOW, seed=lambda: called.append(1) or {"s": NOW - DAY, "z": NOW - DAY})
            self.assertEqual(called, [1])
            self.assertEqual(out.get("s"), NOW - DAY)
            self.assertNotIn("z", out)
            if prev:
                self.assertEqual(out["a"], NOW)                         # listed in the V1 file, not now: it left at this build

    def test_daily_cuts_are_always_sixty_midnights_across_a_dst_change(self):
        for now in (int(dt.datetime(2027, 3, 15, 0, 30, tzinfo=TZ).timestamp()), int(dt.datetime(2027, 3, 14, 23, 59, tzinfo=TZ).timestamp()),
                    int(dt.datetime(2026, 11, 2, 12, 0, tzinfo=TZ).timestamp()), NOW):
            cuts = C.daily_cuts(now)
            self.assertEqual(len(cuts), 60, now)                                  # 60 calendar days, not 61 when a day is 23 h
            self.assertTrue(all(dt.datetime.fromtimestamp(c, TZ).hour == 0 for c in cuts))
            days = [dt.datetime.fromtimestamp(c, TZ).date() for c in cuts]
            self.assertEqual([(b - a).days for a, b in zip(days, days[1:])], [1] * 59)
            self.assertEqual(days[-1], dt.datetime.fromtimestamp(now, TZ).date())
            self.assertLessEqual(cuts[-1], now)

    def test_daily_cuts_are_midnight_central_across_the_dst_change(self):
        cuts = C.daily_cuts(NOW)
        self.assertEqual(len(cuts), 60)
        self.assertEqual(cuts[-1], int(dt.datetime(2026, 11, 21, tzinfo=TZ).timestamp()))
        self.assertTrue(all(dt.datetime.fromtimestamp(c, TZ).hour == 0 for c in cuts))    # Oct 22 to Nov 21 spans the Nov 1 change
        self.assertTrue(all(NOW - 60 * DAY < c <= NOW for c in cuts))

    def test_seed_is_point_in_time(self):
        cuts = C.daily_cuts(NOW)
        c_last, c_5, c_4 = cuts[-1], cuts[-6], cuts[-5]
        def wins(w, t0, n=6):
            return [row(w, i, "win", settled=t0 + i * 60, cid=f"{w}-w{i}") for i in range(n)]
        rows = (wins("0xlost", c_5 - 10 * DAY)                                              # proven well before, then one big loss after c_5
                + [row("0xlost", 99, "loss", stake=50000, settled=c_5 + 3600, cid="0xlost-big")]
                + wins("0xlate", c_last + 600)                                              # proven only after the last cut
                + wins("0xstay", c_5 - 10 * DAY))                                           # proven now and at every cut: listed now
        fl = ledger(rows)
        self.assertTrue(fl.stats("0xstay", NOW)["all"]["proven"])
        self.assertTrue(fl.stats("0xlate", NOW)["all"]["proven"])
        self.assertFalse(fl.stats("0xlost", NOW)["all"]["proven"])
        out = C.seed_retained(fl, "cbb", NOW, listed={"0xstay"})
        self.assertEqual(out, {"0xlost": c_4})                       # last listed at c_5 (the loss settles after it); left at the next cut
        self.assertNotIn("0xlate", out)                              # it was never listed at any cut: point in time
        self.assertNotIn("0xstay", out)
        # with nothing listed now, 0xlate still is not retained for a cut it was not proven at, and 0xlost is not listed at c_4 or later
        out2 = C.seed_retained(fl, "cbb", NOW, listed=set())
        self.assertEqual(out2["0xlost"], c_4)
        self.assertNotIn("0xlate", out2)
        self.assertEqual(out2["0xstay"], NOW)                        # listed at the last cut: left at "now" if it were not listed

    def test_seed_skips_excluded_untracked_and_never_reads_the_scorecard_list(self):
        cuts = C.daily_cuts(NOW)
        t0 = cuts[-8] - DAY
        def wins(w, n):
            return [row(w, i, "win", settled=t0 + i * 60, cid=f"{w}-w{i}") for i in range(n)]
        # 0xok and 0xhg have the same proven record; 0xhg also sits on both sides of 4 of its 10 markets (hedger: 8+ markets, 25%+ hedged)
        rows = wins("0xok", 6) + wins("0xhg", 6) + [row("0xhg", 50 + i, "win", hedged=True, settled=t0 + 600 + i, cid=f"0xhg-h{i}") for i in range(4)]
        # 0xlate is proven but first seen after the last cut: untracked at every cut; 0xsc has a loss only (never proven or sharp)
        rows += wins("0xlate", 6) + [row("0xsc", 0, "loss", settled=t0)]
        fs = {"0xok": t0 - 10 * DAY, "0xhg": t0 - 10 * DAY, "0xsc": t0 - 10 * DAY, "0xlate": cuts[-1] + 1}
        fl = ledger(rows, first_seen=fs)
        self.assertTrue(fl.stats("0xhg", NOW)["all"]["proven"])
        self.assertEqual(fl.stats("0xhg", NOW)["excluded"], "hedger")                    # the Ledger really marks it excluded
        self.assertIsNone(fl.stats("0xok", NOW)["excluded"])
        out = C.seed_retained(fl, "cbb", NOW, listed=set())
        self.assertIn("0xok", out)
        self.assertNotIn("0xhg", out)                                                    # excluded wallets are never retained
        self.assertNotIn("0xlate", out)                                                  # not in the universe at any cut
        self.assertNotIn("0xsc", out)                                                    # the current scorecard list is look-ahead: not replayed

    def test_retained_entry_shape(self):
        fl = ledger([row("0xr", 0, "win", settled=NOW - DAY)])
        e = C.retained_entry("0xr", NOW - 3 * DAY, fl.stats("0xr", NOW), NOW, fl.first_seen["0xr"],
                             {"tier": "dull", "n": 40, "mean": -0.01, "post": -0.008, "sd": 0.002, "p": 0.02}, "R", "R")
        self.assertEqual(set(e), {"retained", "left_at", "name", "name_disp", "first_seen", "fwd", "last_settled", "n30_games", "v2", "rk"})
        self.assertTrue(e["retained"])
        self.assertNotIn("positions", e)
        self.assertEqual(e["v2"], {"tier": "loses"})


class FileShape(unittest.TestCase):
    def test_top_level_v1_keys_keep_their_values_and_v2_keys_are_added(self):
        doc = C.wallets_file({"nba": {}}, NOW, {"nba": {}})
        for k, v in (("built", NOW), ("context_only", True), ("floor_usd", 250), ("floor_usd_by_sport", {"cbb": 100})):
            self.assertEqual(doc[k], v)
        for k in ("tier_rule", "proven_rule", "note", "sports"):
            self.assertIn(k, doc)
        self.assertEqual(doc["v"], 2)
        self.assertEqual(doc["since_from"], NOW - 60 * DAY)
        self.assertEqual(doc["retained"], {"nba": {}})
        self.assertTrue(all(k in doc for k in C.V2_TOP_KEYS))
        self.assertEqual(C.VERSION, 1)                                   # cards keep their own version
        self.assertEqual(set(C.strip_v2(doc)), set(doc) - set(C.V2_TOP_KEYS))

    def test_retained_wallets_are_never_under_sports(self):
        fl = ledger([row("0xr", 0, "win")])
        listed = {"0xa": listed_wallet(fl, "0xr")}
        doc = C.wallets_file({"nba": listed}, NOW, {"nba": {"0xb": {"retained": True}}})
        self.assertFalse(set(doc["retained"]["nba"]) & set(doc["sports"]["nba"]))
        self.assertTrue(all(e.get("retained") is None for e in doc["sports"]["nba"].values()))

    def test_default_retained_is_an_empty_object_so_classic_never_breaks(self):
        self.assertEqual(C.wallets_file({}, NOW)["retained"], {})

    def test_size_budget_constants_match_the_spec(self):
        self.assertEqual((C.WALLETS_MAX_KB, C.WALLETS_NEW_MAX_KB), (1350, 400))

    def test_over_budget_names_what_is_broken_and_inside_is_empty(self):
        self.assertEqual(C.over_budget(1350, 400), "")                              # at the limit is inside
        self.assertIn("whole file", C.over_budget(1350.1, 100))
        self.assertNotIn("V2 fields", C.over_budget(1350.1, 100))
        self.assertIn("V2 fields", C.over_budget(1000, 400.1))
        self.assertIn("whole file", C.over_budget(1607, 660))
        self.assertIn("V2 fields", C.over_budget(1607, 660))

    def test_sizes_count_the_v2_keys_and_the_gate_script_exits_nonzero_over_budget(self):
        small = C.wallets_file({"nba": {}}, NOW, {"nba": {}})
        kb, new_kb = C.wallets_sizes(small)
        self.assertGreater(new_kb, 0)
        self.assertLess(new_kb, kb)
        gate = os.path.join(os.path.dirname(HERE), "scripts", "sharps_v2", "check_size.py")
        fat = copy.deepcopy(small)
        fat["retained"] = {"nba": {"0x%040x" % i: {"retained": True, "left_at": NOW, "pad": "x" * 600} for i in range(2500)}}   # ~1.7 MB of V2 keys
        for doc, want in ((small, 0), (fat, C.BUDGET_EXIT)):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(doc, f)
            r = subprocess.run([sys.executable, "-I", gate, f.name], capture_output=True, text=True)
            os.unlink(f.name)
            self.assertEqual(r.returncode, want, r.stdout + r.stderr)

    def test_since_file_shape_leaves_out_empty_wallets_and_carries_the_unit(self):
        item = [NOW - DAY, NOW - 2 * DAY, 1, 0.9, "nba-x-y-2026-11-20", 300]
        d = C.since_file({"nba": {"0xa": [item], "0xb": []}}, {"nba": {"0xc": [item]}}, NOW)
        self.assertEqual(d["sports"], {"nba": {"0xa": [item]}})
        self.assertEqual(d["retained"], {"nba": {"0xc": [item]}})
        self.assertEqual((d["built"], d["since_from"], d["days"]), (NOW, NOW - 60 * DAY, 60))
        self.assertEqual(C.wallets_file({}, NOW)["since_file"], C.SINCE_FILE)

    @unittest.skipUnless(os.environ.get("SHARPS_V2_WALLETS"), "set SHARPS_V2_WALLETS to a built wallets.json for the Nov 21 size check")
    def test_real_file_is_inside_the_size_budget(self):
        path = os.environ["SHARPS_V2_WALLETS"]
        with open(path) as f:
            doc = json.load(f)
        kb = os.path.getsize(path) / 1000
        new_kb = kb - len(json.dumps(C.strip_v2(doc), separators=(",", ":"))) / 1000
        self.assertLessEqual(kb, C.WALLETS_MAX_KB)
        self.assertLessEqual(new_kb, C.WALLETS_NEW_MAX_KB)


class PublishedFirstSeen(unittest.TestCase):
    """A wallet in both first_seen.json and follow_only.json: build_pm_ledger stamped `src` forward from the earlier follow-only date, so the
    date the wallets file shows is the earlier one. Everything else (stats, cuts) keeps the registered date winning, so no V1 number moves."""

    def make(self, first_seen, follow_only):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "bets", "cbb"))
        os.makedirs(os.path.join(root, "markets"))
        rows = [row(w, 0, "win", settled=NOW - 3 * DAY, src="forward") for w in ("0xboth", "0xreg", "0xfol")]
        with open(os.path.join(root, "bets", "cbb", "2026-11.jsonl"), "w") as f:
            f.write("\n".join(json.dumps(r) for r in rows))
        with open(os.path.join(root, "first_seen.json"), "w") as f:
            json.dump(first_seen, f)
        with open(os.path.join(root, "follow_only.json"), "w") as f:
            json.dump(follow_only, f)
        return root

    def test_earlier_date_is_published_and_registered_date_still_drives_stats(self):
        early, late = NOW - 5 * DAY, NOW - 2 * DAY
        root = self.make({"0xboth": late, "0xreg": late}, {"0xboth": early, "0xfol": early})
        fl = C.Ledger.load(root, "cbb", None, None, follow=True)
        self.assertEqual(fl.first_seen_pub["0xboth"], early)                    # min of the two
        self.assertEqual(fl.first_seen_pub["0xreg"], late)                      # registered only
        self.assertEqual(fl.first_seen_pub["0xfol"], early)                     # follow-only
        self.assertEqual(fl.first_seen["0xboth"], late)                         # unchanged: registered date wins for stats and cuts
        self.assertFalse(fl.stats("0xboth", NOW - 3 * DAY - 1)["tracked"] and fl.stats("0xboth", early)["tracked"])
        # every forward row of the wallet settles at or after the date the file shows
        fwd = [r for r in fl.by_w["0xboth"] if r["src"] == "forward"]
        self.assertTrue(fwd and all(r["settled_at"] >= fl.first_seen_pub["0xboth"] for r in fwd))

    def test_the_card_ledger_has_no_published_override(self):
        early, late = NOW - 5 * DAY, NOW - 2 * DAY
        fl = C.Ledger.load(self.make({"0xboth": late, "0xreg": late}, {"0xboth": early, "0xfol": early}), "cbb", None, None)
        self.assertIs(fl.first_seen_pub, fl.first_seen)
        self.assertNotIn("0xfol", fl.first_seen)                                # follow-only wallets never reach a card ledger

    def test_the_published_date_is_what_apply_v2_writes(self):
        early, late = NOW - 5 * DAY, NOW - 2 * DAY
        fl = C.Ledger.load(self.make({"0xboth": late}, {"0xboth": early}), "cbb", None, None, follow=True)
        w = {"0xboth": listed_wallet(fl, "0xboth")}
        C.apply_v2("cbb", w, fl, NOW, {}, {}, {}, {}, {}, {})
        self.assertEqual(w["0xboth"]["first_seen"], early)


class Positions(unittest.TestCase):
    def test_position_merging_keeps_old_fields_and_adds_first(self):
        rows = [row("0xq", 0, "win", cid="a", mt="spreads", first=500), row("0xq", 1, "win", cid="b", mt="spreads", first=300)]
        mk = {c: {"slug": "nba-x-y-2026-11-20", "mt": "spreads", "outs": ["X", "Y"], "line": 1.5} for c in "ab"}
        ps = C.positions(rows, mk)
        self.assertEqual(len(ps), 1)
        self.assertEqual((ps[0]["first"], ps[0]["stake"], ps[0]["res"]), (300, 600.0, "win"))


if __name__ == "__main__":
    unittest.main()
