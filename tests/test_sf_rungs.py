"""Unit tests for the SharpFlow rules ported into scripts/sf_rungs.py: steam (STEAM-C, STEAM-S, SOLO-Q, the price step), TRUST-M,
PRESS-M, the odds cap, the edge clamps (press-edge-net, edge-under-5), GAP-LEAD and TOP3-PICK, plus the tape read in build_side_cards."""
import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
sys.path.insert(0, HERE)
import sf_rungs as S  # noqa: E402
import build_side_cards as C  # noqa: E402

T = 1_800_000_000
TRUSTED = {"status": "STABLE_ON", "tier": 5, "n": 30, "edge": 20.0, "age": 40}


def w(d, usd=1000, ratio=1.0, n=20, wr=60.0, door2=False, streak=0, trust=None, trust_mkt=None, **kw):
    r = {"w": kw.pop("wid", None), "dir": d, "invested": usd, "ratio": ratio, "n": n, "wins": round(n * wr / 100) if wr is not None else 0,
         "wr": wr, "door2": door2, "streak": streak, "trust": trust, "trust_mkt": trust_mkt}
    r.update(kw)
    return r


def flip(rows):
    return [dict(r, dir="AG" if r["dir"] == "FOR" else "FOR") for r in rows]


class Steam(unittest.TestCase):
    def tape(self):
        return [{"t": T - 7200, "ml": [150, -170], "sp": [-3.5, -110, -110], "tot": [220.5, -110, -110]},
                {"t": T - 1800, "ml": [130, -150], "sp": [-4.0, -110, -110], "tot": [220.5, -105, -115]},
                {"t": T + 60, "ml": [100, -120], "sp": [-6.0, -110, -110], "tot": [224.5, -110, -110]}]   # after the cut

    def test_moneyline_shortening_is_steam_and_rows_after_the_cut_are_ignored(self):
        home = S.steam_read(self.tape(), "ml", "home", None, T)
        self.assertFalse(home["on"])                                   # -170 -> -150 lengthens the home price: no steam
        away = S.steam_read(self.tape(), "ml", "away", None, T)
        self.assertEqual(away["now"], [T - 1800, 130])                  # the row at T+60 is after the cut and is not read
        self.assertEqual(away["since_open_pct"], S.drop_pct(150, 130))
        self.assertTrue(away["on"])                                    # +150 -> +130 shortens the away price 8%
        self.assertEqual(S.steam_read(self.tape()[:1], "ml", "away", None, T)["on"], False)   # one row: no move
        self.assertIsNone(S.steam_read(self.tape()[2:], "ml", "away", None, T)["on"])        # nothing at or before the cut

    def test_spread_walk_and_off_main_ticket(self):
        h = S.steam_read(self.tape(), "spread", "home", -3.5, T)
        self.assertEqual((h["since_open_pts"], h["on"]), (0.5, True))  # home -3.5 -> -4.0 walks toward home
        a = S.steam_read(self.tape(), "spread", "away", 3.5, T)
        self.assertEqual(a["since_open_pts"], -0.5)
        self.assertIsNone(a["on"])                                     # no walk toward away, and +3.5 is not the main at the cut: unknown
        self.assertFalse(S.steam_read(self.tape(), "spread", "away", 4.0, T)["on"])   # +4.0 is the main: its juice is flat -> off

    def test_total_juice_on_the_ticket_line(self):
        under = S.steam_read(self.tape(), "total", "under", 220.5, T)
        self.assertEqual(under["since_open_pct"], S.drop_pct(-110, -115))  # read on the 220.5 rows only
        self.assertFalse(under["on"])                                  # a 2.07% shorten is under the 3% steam floor
        self.assertIsNone(S.steam_read(self.tape(), "total", "under", 221.5, T)["on"])   # an alt total: no rows, no walk -> unknown

    def test_drop_pct_units(self):
        self.assertEqual(S.drop_pct(-110, -130), round((1 + 100 / 110 - (1 + 100 / 130)) / (1 + 100 / 110) * 100, 2))
        self.assertLess(S.drop_pct(-130, -110), 0)


class SteamRungs(unittest.TestCase):
    def test_price_step(self):
        rows = [w("FOR", 3000, ratio=3.2, door2=True), w("AG", 1000)]
        self.assertEqual(S.evaluate(rows, "ml", 0.55, 0.9, steam=False)["units"], 5.0)        # clean
        self.assertEqual(S.evaluate(rows, "ml", 0.55, 0.9, steam=True)["units"], 4.0)         # moved, FOR edge 60 - 55 >= 0 -> step 1
        rows[0]["wr"] = 50.0
        self.assertEqual(S.evaluate(rows, "ml", 0.55, 0.9, steam=True)["units"], 3.0)         # moved, edge < 0 -> step 2
        self.assertEqual(S.evaluate(rows, "ml", 0.55, 0.9, steam=None)["units"], 5.0)         # unknown steam reads as off

    def test_press_x_split(self):
        x = [w("FOR", 3000, ratio=2.0, door2=True), w("FOR", 500, door2=True), w("AG", 500, door2=True, ratio=0.5)]
        self.assertEqual(S.evaluate(x, "ml", 0.55, 0.5, steam=False)["units"], 3.0)
        self.assertEqual(S.evaluate(x, "ml", 0.55, 0.5, steam=True)["units"], 2.0)

    def test_steam_c(self):
        rows = [w("FOR", 400, ratio=1.0), w("AG", 900, door2=True, ratio=0.6)]                 # proven against, under normal size
        self.assertEqual(S.evaluate(rows, "ml", 0.55, 0.5, steam=True)["rung"], "STEAM-C")
        self.assertIsNone(S.evaluate(rows, "ml", 0.55, 0.5, steam=False)["rung"])
        self.assertIsNone(S.evaluate(rows, "ml", 0.55, 0.5, steam=None)["rung"])
        rows[1]["ratio"] = 1.2                                                                  # the dissent is at full size: not STEAM-C
        self.assertEqual(S.evaluate(rows, "ml", 0.55, 0.5, steam=True)["rung"], "STEAM-S")      # (it is STEAM-S's shape: a normal-size seasoned AG)
        rows[1]["ratio"] = 1.6
        self.assertIsNone(S.evaluate(rows, "ml", 0.55, 0.5, steam=True)["rung"])

    def test_steam_s(self):
        rows = [w("FOR", 400, ratio=0.8, n=16), w("AG", 600, ratio=1.2, n=20)]                 # money 40%, seasoned AG at 1.2x
        e = S.evaluate(rows, "spread", 0.5, 0.5, steam=True)
        self.assertEqual((e["rung"], e["units"]), ("STEAM-S", 2.0))
        self.assertIsNone(S.evaluate(rows, "spread", 0.5, 0.5, steam=False)["rung"])
        self.assertIsNone(S.evaluate(rows, "spread", 0.35, 0.5, steam=True)["rung"])           # a long dog
        self.assertIsNone(S.evaluate(rows, "spread", 0.5, 0.5, steam=True, pick_date="2026-10-06")["rung"])   # before STEAM_S_FROM

    def test_solo_q(self):
        dust = [w("FOR", 400, ratio=0.5)]
        e = S.evaluate(dust, "ml", 0.55, 0.5, steam=False)
        self.assertEqual((e["rung"], e["units"]), ("SOLO-Q", 1.0))
        self.assertIsNone(S.evaluate(dust, "ml", 0.55, 0.5, steam=True)["rung"])
        self.assertEqual(S.evaluate(dust, "ml", 0.55, 0.5, steam=None)["rung"], "SOLO-Q")     # unknown steam reads as off (SharpFlow passes false)
        self.assertIsNone(S.evaluate(dust, "ml", 0.65, 0.5, steam=False)["rung"])             # outside .50-.60
        ordinary = [w("FOR", 400, ratio=1.2, l10=(8, 2))]
        self.assertEqual(S.evaluate(ordinary, "ml", 0.55, 0.5, steam=False)["rung"], "SOLO-Q")
        ordinary[0]["l10"] = (6, 4)
        self.assertIsNone(S.evaluate(ordinary, "ml", 0.55, 0.5, steam=False)["rung"])


class TrustM(unittest.TestCase):
    def test_moneyline_rescue_needs_a_margin(self):
        rows = [w("FOR", 500, trust_mkt=TRUSTED), w("FOR", 500, trust_mkt=TRUSTED), w("AG", 2000)]
        e = S.evaluate(rows, "ml", 0.52, -0.2)
        self.assertEqual((e["rung"], e["units"]), ("TRUST-G", 3.0))     # 1u, then the margin-2 floor lifts it to 3; ships through a score <= 0
        self.assertEqual(S.evaluate(rows, "ml", 0.45, -0.2)["units"], 2.5)   # at +122 the odds cap trims it
        one = [w("FOR", 500, trust_mkt=TRUSTED), w("AG", 2000)]
        self.assertEqual(S.evaluate(one, "ml", 0.52, -0.2)["units"], 0.0)   # margin +1, no conviction, under $10k
        one[0]["ratio"] = 1.6                                                 # conviction carries a +1
        self.assertEqual(S.evaluate(one, "ml", 0.52, -0.2)["units"], 1.0)

    def test_spread_margin_goes_through_a_trusted_wallet_against(self):
        rows = [w("FOR", 500, ratio=0.5, trust_mkt=TRUSTED), w("FOR", 500, ratio=0.5, trust_mkt=TRUSTED),
                w("FOR", 500, ratio=0.5, trust_mkt=TRUSTED), w("AG", 600, trust_mkt=TRUSTED)]
        e = S.evaluate(rows, "spread", 0.55, 0.3)
        self.assertEqual((e["rung"], e["units"]), ("TRUST-S", 3.0))     # margin +2: no veto; the FOR path sizes 2.5u, the margin-2 floor 3u
        self.assertIn("trust_m_over_ag", e["reason"])
        vetoed = S.evaluate(rows[2:], "spread", 0.55, 0.3)
        self.assertTrue(vetoed["reason"].startswith("trust_s_veto"))    # margin 0: the veto stands

    def test_total_lone_floor_and_plus_one_ceiling(self):
        lone = [w("FOR", 500, ratio=1.6, trust_mkt=TRUSTED), w("AG", 500)]
        e = S.evaluate(lone, "total", 0.55, 0.3)
        self.assertEqual((e["rung"], e["units"]), ("TRUST-T", 1.0))     # a lone trusted wallet with conviction takes the 1u floor
        lone[0]["ratio"] = 1.0
        self.assertTrue(S.evaluate(lone, "total", 0.55, 0.3)["reason"].startswith("trust_t_lone"))
        press = [w("FOR", 3000, ratio=3.5, door2=True, trust_mkt=TRUSTED, n=20), w("AG", 500)]
        self.assertEqual(S.evaluate(press, "ml", 0.55, 0.9)["units"], 3.0)   # PRESS 5u, margin exactly +1 -> ceiling 3


class MarketRules(unittest.TestCase):
    def side(self, rows, implied, ags, steam=False, pinn=None):
        return {"rows": rows, "implied": implied, "ags": ags, "steam": steam, "pinn_odds": pinn}

    def test_press_m(self):
        a = [w("FOR", 3000, ratio=2.0, n=20), w("AG", 500)]                                    # money, seasoned press, no Door-2 against
        sides = {"A": self.side(a, 0.55, -0.2), "B": self.side(flip(a), 0.45, 0.4)}
        r = S.stake_market(sides, "ml", "2026-11-11", ["A", "B"])
        self.assertEqual((r["A"]["rung"], r["A"]["units"]), ("PRESS-M", 1.0))
        sides["B"]["ags"] = None                                                               # no V12 side among the siblings
        self.assertEqual(S.stake_market(sides, "ml", "2026-11-11", ["A", "B"])["A"]["units"], 0.0)

    def test_odds_cap(self):
        self.assertEqual(S.odds_cap(5, -150), 5)
        self.assertEqual(S.odds_cap(5, 130), 2.5)
        self.assertEqual(S.odds_cap(5, 180), 1.5)
        self.assertEqual(S.odds_cap(5, 200), 1.0)
        self.assertEqual(S.odds_cap(5, 201), 0.0)
        rows = [w("FOR", 500, trust=TRUSTED), w("AG", 500)]
        self.assertEqual(S.evaluate(rows, "ml", 0.40, 0.3)["units"], 2.5)   # TRUST-G 3u at +150 -> 2.5u
        self.assertEqual(S.evaluate(rows, "ml", 0.30, 0.3)["units"], 0.0)   # +233: no stake

    def test_press_edge_net_is_dated(self):
        rows = [w("FOR", 3000, ratio=3.2, door2=True, wr=57.0), w("AG", 1000)]                 # press edge 57 - 55 = 2
        sides = {"A": self.side(rows, 0.55, 0.9), "B": self.side(flip(rows), 0.45, -0.5)}
        self.assertEqual(S.stake_market(sides, "ml", "2026-10-30", ["A", "B"])["A"]["units"], 0.0)
        self.assertEqual(S.stake_market(sides, "ml", "2026-11-04", ["A", "B"])["A"]["units"], 0.0)
        rows[0]["wr"] = 61.0                                                                   # edge 6: out of the hole
        self.assertEqual(S.stake_market(sides, "ml", "2026-10-30", ["A", "B"])["A"]["units"], 5.0)
        rows[0]["wr"] = 57.0
        self.assertEqual(S.stake_market(sides, "ml", "2026-11-07", ["A", "B"])["A"]["units"], 5.0)   # edge-under-5 owns it from 11-05

    def test_edge_under_5(self):
        rows = [w("FOR", 3000, ratio=3.2, door2=True, wr=57.0, n=100), w("AG", 1000, t5={"q": True})]
        sides = {"A": self.side(rows, 0.55, 0.9, steam=False), "B": self.side(flip(rows), 0.45, -0.5)}
        r = S.stake_market(sides, "ml", "2026-11-07", ["A", "B"])["A"]
        self.assertEqual((r["units"], r["blend"]), (0.0, 2.0))                                  # blend 57 - 55 under 5, steam off, a tier 5 against
        sides["A"]["steam"] = True
        self.assertEqual(S.stake_market(sides, "ml", "2026-11-07", ["A", "B"])["A"]["units"], 4.0)   # kept (steam on), price step 1
        sides["A"]["steam"] = None
        r = S.stake_market(sides, "ml", "2026-11-07", ["A", "B"])["A"]
        self.assertEqual((r["units"], r["chain"]), (5.0, ["edge_under_5_undecided_steam_unknown"]))
        sides["A"]["steam"] = False
        rows[1]["t5"] = {"q": False}                                                            # nobody tier 5 against: no mute
        self.assertEqual(S.stake_market(sides, "ml", "2026-11-07", ["A", "B"])["A"]["units"], 5.0)

    def test_gap_lead(self):
        g = lambda dol: {"n": 8, "dol": dol}
        rows = [w("FOR", 500, gap=g(30)), w("FOR", 500, gap=g(20)), w("AG", 2000, gap=g(-25))]
        sides = {"A": self.side(rows, 0.55, -0.1), "B": self.side(flip(rows), 0.45, -0.1)}
        r = S.stake_market(sides, "ml", "2026-11-11", ["A", "B"])["A"]
        self.assertEqual((r["rung"], r["units"]), ("GAP-LEAD", 3.0))                            # 25 vs -25: a 50-point lead
        rows[2]["gap"] = g(-5)
        self.assertEqual(S.stake_market(sides, "ml", "2026-11-11", ["A", "B"])["A"]["units"], 0.0)   # 30 points: short
        self.assertEqual(S.gap_lead([w("FOR", 500, gap=g(30)), w("AG", 500, gap=g(-30))], None)["reason"], "need_two_wallets")

    def test_top3_pick(self):
        rows = [w("FOR", 500, ratio=1.2, rank=2), w("AG", 500, rank=9)]
        sides = {"A": self.side(rows, 0.5, -0.1, pinn=105), "B": self.side(flip(rows), 0.5, -0.1, pinn=-125)}
        r = S.stake_market(sides, "ml", "2026-11-11", ["A", "B"])
        self.assertEqual((r["A"]["rung"], r["A"]["units"]), ("TOP3-PICK", 4.0))
        self.assertEqual(r["B"]["units"], 0.0)
        rows[0]["ratio"] = 0.8
        self.assertEqual(S.stake_market(sides, "ml", "2026-11-11", ["A", "B"])["A"]["units"], 2.0)
        rows[1]["rank"] = 3                                                                     # a top-3 wallet against
        self.assertEqual(S.stake_market(sides, "ml", "2026-11-11", ["A", "B"])["A"]["units"], 0.0)
        rows[1]["rank"] = 9
        t = S.top3(rows, None, 0, "2026-11-11", 0.50)                                          # no Pinnacle price: the price at the cut, 45-52c
        self.assertEqual((t["fires"], t["price_src"]), (True, ["polymarket_at_cut"]))
        self.assertFalse(S.top3(rows, None, 0, "2026-11-11", 0.55)["fires"])
        self.assertEqual(S.top3([dict(rows[0], entry_px=0.48), rows[1]], None, 0, "2026-11-11", 0.55)["price_src"], ["entry"])
        self.assertFalse(S.top3(rows, -130, 0, "2026-11-11")["fires"])                          # -130 is not a pick'em


class SeasonTier5(unittest.TestCase):
    def test_season_start_and_read(self):
        self.assertEqual(S.season_start(["2026-06-01", "2026-06-10", "2026-10-21", "2026-10-25"]), "2026-10-21")
        rows = [("2026-10-%02d" % (1 + i // 2), 0.5, i % 5 != 0) for i in range(30)]           # 80% at 50 cents from Oct 1
        self.assertTrue(S.t5_read(rows, "2026-11-11", "2026-10-01"))
        self.assertFalse(S.t5_read(rows, "2026-10-10", "2026-10-01"))                          # only 9 days old (and few bets)


class BuildTape(unittest.TestCase):
    def test_tape_lookup_side_mapping_and_cut(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "nba"))
            rows = [{"t": T - 7200, "gk": "nba:1", "away": "BKN", "home": "NOP", "start": T + 900, "book": "Pinnacle", "ml": [150, -170]},
                    {"t": T - 600, "gk": "nba:1", "away": "BKN", "home": "NOP", "start": T + 900, "book": "Pinnacle", "ml": [130, -150]},
                    {"t": T + 300, "gk": "nba:1", "away": "BKN", "home": "NOP", "start": T + 900, "book": "Pinnacle", "ml": [100, -120]},
                    {"t": T - 600, "gk": "nba:1", "away": "BKN", "home": "NOP", "start": T + 900, "book": "FanDuel", "ml": [300, -400]}]
            with open(os.path.join(d, "nba", "2027-01.jsonl"), "w") as f:
                f.write("\n".join(json.dumps(r) for r in rows))
            tape = C.BookTape(d)
            game, how = tape.game("nba", {"key": "nba:1"}, "nba-bkn-nop-2027-01-15", T + 900)
            self.assertEqual((len(game), how), (3, "gk"))                                       # Pinnacle rows only
            game2, how2 = tape.game("nba", None, "nba-bkn-nop-2027-01-15", T + 900)
            self.assertEqual((len(game2), how2), (3, "teams"))                                  # no Vault game: the slug's teams
            self.assertEqual(C.pinnacle_price(game, "ml", "away", T), 130)                    # the T+300 row is after the cut
            names = C.team_names(None, "nba-bkn-nop-2027-01-15", "nba")
            self.assertEqual(C.side_norms("ml", ["Nets", "Pelicans"], names), {"Nets": "away", "Pelicans": "home"})
            self.assertEqual(C.side_norms("ml", ["Nets", "Hornets"], names), {"Nets": "away", "Hornets": None})
            self.assertEqual(C.side_norms("total", ["Over", "Under"], None), {"Over": "over", "Under": "under"})
            cfb = {"away": ["Memphis Tigers", "Memphis"], "home": ["South Florida Bulls", "S. Florida"]}
            self.assertEqual(C.side_norms("spread", ["Memphis", "South Florida"], cfb), {"Memphis": "away", "South Florida": "home"})

    def test_card_steam_reads_only_rows_at_or_before_the_cut(self):
        from test_side_cards import kf, ledger, proven
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "nba"))
            # the away side (outcome A) shortens 8% before the cut, and lengthens back after it
            rows = [{"t": T - 7200, "gk": "nba:9", "start": T + 900, "book": "Pinnacle", "ml": [150, -170]},
                    {"t": T - 600, "gk": "nba:9", "start": T + 900, "book": "Pinnacle", "ml": [130, -150]},
                    {"t": T + 300, "gk": "nba:9", "start": T + 900, "book": "Pinnacle", "ml": [180, -210]}]
            with open(os.path.join(d, "nba", "2027-01.jsonl"), "w") as f:
                f.write("\n".join(json.dumps(r) for r in rows))
            vault = {"key": "nba:9", "away": "AAA", "home": "BBB", "teams": {"away": ["A"], "home": ["B"]}}
            c = C.card(kf([("m1", 0, "0xp", 400)]), ledger(proven("0xp")), "nba", vault, tape=C.BookTape(d))
            self.assertIs(c["markets"]["ml"]["sf"]["all"]["sides"]["A"]["steam"], True)    # +150 -> +130 before the cut; +180 after is not read
            self.assertEqual(S.steam_read(C.BookTape(d).game("nba", vault, "", T + 900)[0], "ml", "away", None, T)["now"], [T - 600, 130])


class LedgerReads(unittest.TestCase):
    def test_market_books_rank_and_window(self):
        from test_side_cards import row
        markets, rows = {}, []
        for k, (wid, pnl) in enumerate([("0xa", 90), ("0xb", 50), ("0xc", 10), ("0xd", -50), ("0xe", -90)]):
            for i in range(6):
                cid = "%s-%d" % (wid, i)
                markets[cid] = {"slug": "nba-x-y-2027-01-%02d" % (5 + i), "mt": "moneyline", "outs": ["X", "Y"]}
                rows.append(dict(row(wid, i, "win" if pnl > 0 else "loss", stake=100, pnl=pnl, settled=T - 86400 * (12 - i), cid=cid),
                                 mt="moneyline"))
        L = C.Ledger(rows, markets, {x["w"]: 0 for x in rows}, [], T - 3600)
        gap, rank = L.market_books("all", "2027-01-15", T)
        self.assertEqual(rank[("0xa", "ml")], 1)
        self.assertEqual(rank[("0xe", "ml")], 5)
        self.assertEqual(gap[("0xb", "ml")], {"n": 6, "dol": 50.0})
        gap2, _ = L.market_books("all", "2027-01-08", T)                                       # only games dated before the pick date
        self.assertNotIn(("0xa", "ml"), gap2)


class Tier5Seats(unittest.TestCase):
    def rows(self, f_held=(), a_held=(), d="FOR"):
        out = [w("FOR", 500, t5={"q": True, "held": h}) for h in f_held] + [w("AG", 500, t5={"q": True, "held": h}) for h in a_held]
        return out + [w("AG", 100, t5={"q": False, "held": None})]

    def test_hold_walks_back(self):
        rows = [("2026-10-%02d" % (1 + i // 2), 0.5, i % 5 != 0) for i in range(30)]
        held = S.t5_hold(rows, "2026-11-11", "2026-10-01")
        self.assertGreater(held, 0)
        self.assertEqual(S.t5_hold(rows, "2026-11-11", "2026-11-05"), None)                   # season starts after the bets: no read
        self.assertIsNone(S.t5_hold(rows, "2026-10-10", "2026-10-01"))

    def test_seats(self):
        self.assertEqual(S.t5_seat(S.t5_lead(self.rows([20]))), "lead14")
        self.assertEqual(S.t5_seat(S.t5_lead(self.rows([8]))), "lead6")
        self.assertEqual(S.t5_seat(S.t5_lead(self.rows([2]))), "t5_young")
        self.assertEqual(S.t5_seat(S.t5_lead(self.rows())), "no_t5")
        self.assertEqual(S.t5_seat(S.t5_lead(self.rows([20], [3]))), "no_lead")
        self.assertIsNone(S.t5_lead([w("FOR", 500)]))                                           # no season read at all: no seat

    def test_band_and_rescue_floor(self):
        lead14 = S.t5_lead(self.rows([20]))
        self.assertEqual(S.apply_t5(1.0, lead14, "ml", "2026-11-11", None)[:2], (3.0, "BAND"))   # floor 3
        self.assertEqual(S.apply_t5(8.0, lead14, "ml", "2026-11-11", None)[:2], (6.0, "BAND"))   # ceiling 6
        self.assertEqual(S.apply_t5(1.0, lead14, "ml", "2026-11-11", None, from_rescue=True)[:2], (1.0, "PASS"))   # a rescue keeps 1u
        self.assertEqual(S.apply_t5(5.0, S.t5_lead(self.rows()), "ml", "2026-11-11", None)[:2], (2.0, "BAND"))   # no tier 5: 2u
        self.assertEqual(S.apply_t5(5.0, lead14, "ml", "2026-11-07", None)[:2], (5.0, "EXEMPT"))  # before T5_LEAD_FROM

    def test_no_t5_spread_total_needs_juice_steam(self):
        no_t5 = S.t5_lead(self.rows())
        self.assertEqual(S.apply_t5(2.0, no_t5, "spread", "2026-11-11", False)[:2], (0.0, "MUTE_NO_T5_ST_STEAM"))
        self.assertEqual(S.apply_t5(2.0, no_t5, "spread", "2026-11-11", True)[:2], (2.0, "PASS"))
        self.assertEqual(S.apply_t5(2.0, no_t5, "total", "2026-11-11", None)[:2], (2.0, "UNDECIDED_STEAM_UNKNOWN"))
        self.assertEqual(S.apply_t5(2.0, no_t5, "ml", "2026-11-11", False)[:2], (2.0, "PASS"))   # moneylines are not gated
        self.assertEqual(S.apply_t5(2.0, no_t5, "spread", "2026-11-09", False)[:2], (2.0, "PASS"))   # before T5_NO_T5_ST_FROM

    def test_in_the_chain(self):
        rows = [w("FOR", 3000, ratio=3.2, door2=True, wr=70.0, n=100, t5={"q": False}), w("AG", 1000, t5={"q": False})]
        sides = {"A": {"rows": rows, "implied": 0.55, "ags": 0.9, "steam": False, "juice": False, "pinn_odds": None},
                 "B": {"rows": flip(rows), "implied": 0.45, "ags": -0.5, "steam": False, "juice": False, "pinn_odds": None}}
        r = S.stake_market(sides, "ml", "2026-11-11", ["A", "B"])["A"]
        self.assertEqual((r["units"], r["t5_seat"]), (2.0, "no_t5"))                              # PRESS 5u, no tier 5 on either side: 2u
        self.assertEqual(S.stake_market(sides, "ml", "2026-11-07", ["A", "B"])["A"]["units"], 5.0)


class PressUnder5Cap(unittest.TestCase):
    def test_cap(self):
        self.assertEqual(S.press_under5_cap(3.0, 3.0, "ml", "2026-11-11", None, None), (1.0, "CAP"))
        self.assertEqual(S.press_under5_cap(3.0, 3.0, "ml", "2026-11-11", {"for14": 1, "a": 0}, "lead14"), (2.0, "CAP"))
        self.assertEqual(S.press_under5_cap(3.0, 3.0, "ml", "2026-11-11", {"for14": 0, "a": 0}, "t5_young"), (2.0, "CAP"))
        self.assertEqual(S.press_under5_cap(3.0, 3.0, "spread", "2026-11-11", {"for14": 1, "a": 0}, "lead14"), (1.0, "CAP"))
        self.assertEqual(S.press_under5_cap(2.0, -0.5, "total", "2026-11-11", None, None), (0.0, "ZERO"))
        self.assertEqual(S.press_under5_cap(2.0, -0.5, "ml", "2026-11-11", None, None), (1.0, "CAP"))   # a moneyline under 0 takes the cap
        self.assertEqual(S.press_under5_cap(3.0, 5.0, "ml", "2026-11-11", None, None), (3.0, "HOLD"))
        self.assertEqual(S.press_under5_cap(3.0, None, "ml", "2026-11-11", None, None), (3.0, "PASS"))
        self.assertEqual(S.press_under5_cap(3.0, 3.0, "ml", "2026-11-09", None, None), (3.0, "EXEMPT"))


class ReviewFixes2(unittest.TestCase):
    def test_lock_row_juice_counts(self):
        gst = T + 900
        tape = [{"t": T - 7200, "ml": [150, -170]}, {"t": gst - 1500, "ml": [130, -150]}, {"t": T - 60, "ml": [152, -172]}]
        st = S.ladder_steam(tape, "ml", "away", None, T, gst)
        self.assertEqual((st["cut_on"], st["lock_juice"], st["on"]), (False, True, True))         # shortened by the lock row, faded by the cut
        flat = [{"t": T - 7200, "ml": [150, -170]}, {"t": T - 60, "ml": [150, -170]}]
        self.assertIs(S.ladder_steam(flat, "ml", "away", None, T, gst)["on"], False)
        walk = [{"t": T - 7200, "sp": [-3.5, -110, -110]}, {"t": T - 60, "sp": [-4.5, -110, -110]}]
        st = S.ladder_steam(walk, "spread", "home", -4.5, T, gst)
        self.assertEqual((st["on"], st["juice"]), (True, False))                                   # a walk is ladder steam, not juice steam

    def test_pinnacle_price_off_main_is_none(self):
        game = [{"t": T - 60, "sp": [-4.5, -105, -115], "tot": [220.5, -110, -110]}]
        self.assertEqual(C.pinnacle_price(game, "spread", "away", T, 4.5), -115)
        self.assertIsNone(C.pinnacle_price(game, "spread", "away", T, 3.5))
        self.assertIsNone(C.pinnacle_price(game, "total", "over", T, 221.5))

    def test_gap_does_not_fire_against_a_stake(self):
        g = lambda dol: {"n": 8, "dol": dol}
        rows = [w("FOR", 500, gap=g(30)), w("FOR", 500, gap=g(20)), w("AG", 2000, gap=g(-25))]
        sides = {"A": {"rows": rows, "implied": 0.55, "ags": -0.1, "steam": False, "pinn_odds": None},
                 "B": {"rows": flip(rows), "implied": 0.45, "ags": 0.9, "steam": False, "pinn_odds": None}}
        flip_b = sides["B"]["rows"]
        flip_b[2]["ratio"], flip_b[2]["door2"], flip_b[2]["n"] = 3.2, True, 20                    # B is a PRESS side
        r = S.stake_market(sides, "ml", "2026-11-07", ["B", "A"])
        self.assertGreater(r["B"]["units"], 0)
        self.assertEqual((r["A"]["gap"]["fires"], r["A"]["gap"]["reason"], r["A"]["units"]), (False, "pick_against", 0.0))

    def test_trust_walk_by_game_date(self):
        rows = [("2026-10-%02d" % (1 + i // 2), 0.5, True) for i in range(20)]
        self.assertEqual(S.trust_state_dated(rows, "2026-10-05")["n"], 8)                          # games dated Oct 1-4 only
        self.assertEqual(S.trust_state_dated(rows, "2026-11-01")["n"], 20)

    def test_blend_reads_the_bets_list(self):
        r = w("FOR", 500, n=40, wr=50.0, s_n=10, s_wins=8)                                         # the bets list: 8 of 10
        self.assertEqual(S.blend_edge([r], "spread", None), round(80.0 - 52.4, 1))


if __name__ == "__main__":
    unittest.main()
