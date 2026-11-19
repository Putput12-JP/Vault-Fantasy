"""Unit tests for scripts/sharp_agree.py (docs/sharp-agree-prereg.md): the as-of flag, the cells, the contrasts and the pass rule."""
import os, random, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import sharp_agree as A  # noqa: E402
import sf_tiers as TIERS  # noqa: E402
import scan_pm_holders as H  # noqa: E402

T0 = A.START + 3600


class Led:
    """Just enough ledger for holder_groups and the classes."""
    def __init__(self, tiers, first_seen):
        self.tiers, self.first_seen = tiers, first_seen

    def stats(self, w, asof):
        return {"tracked": True, "excluded": None, "all": {"usual": 100.0, "proven": False, "loser": False}}

    def clv_tiers(self, asof):
        return {w: {"tier": t} for w, t in self.tiers.items()}


class St:
    def __init__(self, ms):
        self.m = ms


def kf(cut, rungs, lag=120):
    """A keyframe with one moneyline market and the given holders [(wallet, outcome index, usd)]."""
    mk = {"c1": {"mt": "moneyline", "line": None, "outs": ["Trail Blazers", "Timberwolves"], "tok": ["a", "b"], "px": [.4, .6],
                 "px_t": cut - 60, "read_rt": cut - lag, "frz_lag": lag, "lim": [False, False]}}
    return {"cut": cut, "ev": "nba-por-min-2026-11-20", "gst": cut + 7200, "mk": mk, "cols": ["cid", "oi", "wallet", "shares", "usd_at_mark"],
            "h": [["c1", oi, w, 1000, usd] for w, oi, usd in rungs]}


def row(**kw):
    r = {"id": "b|nba:1|ml|home|x", "kind": "book", "sport": "nba", "src": "watch", "start": T0 + 7200, "firstSeen": T0,
         "game": {"gk": "nba:1", "away": "POR", "home": "MIN", "m": "ml", "side": "home", "hline": None, "line": None}}
    r.update(kw)
    return r


def run(rungs, tiers, side="home", lag=120, first_seen=None, **kw):
    r = row(game={"gk": "nba:1", "away": "POR", "home": "MIN", "m": "ml", "side": side, "hline": None, "line": None}, **kw)
    st = St({"c1": {"ev": "nba-por-min-2026-11-20", "gst": r["start"], "mt": "moneyline"}})
    fs = first_seen or {w: TIERS.REGISTERED_AT - 100 for w in tiers}
    return A.derive_row(r, st, lambda ev, gst, T: kf(T, rungs, lag), Led(tiers, fs), [], H)


class Cells(unittest.TestCase):
    def test_cell_of(self):
        self.assertEqual([A.cell_of(1, 0), A.cell_of(0, 1), A.cell_of(2, 1), A.cell_of(0, 0)], ["agree", "against", "mixed", "none"])

    def test_agree_and_against(self):
        # outcome 1 is Minnesota (home). A sharp on Minnesota: agree with a home play, against an away play
        d = run([("w1", 1, 400)], {"w1": "sharp"}, side="home")
        self.assertEqual((d["cell"], d["sharp_for"], d["sharp_against"]), ("agree", 1, 0))
        d = run([("w1", 1, 400)], {"w1": "sharp"}, side="away")
        self.assertEqual((d["cell"], d["sharp_for"], d["sharp_against"]), ("against", 0, 1))

    def test_mixed_and_none_and_dull_split(self):
        self.assertEqual(run([("w1", 1, 400), ("w2", 0, 400)], {"w1": "sharp", "w2": "sharp"})["cell"], "mixed")
        d = run([("w3", 1, 400)], {"w3": "dull"})
        self.assertEqual((d["cell"], d["dull_split"]), ("none", "dull_with"))
        d = run([("w3", 0, 400)], {"w3": "dull"})
        self.assertEqual((d["cell"], d["dull_split"]), ("none", "dull_against"))
        self.assertEqual(run([("w4", 1, 400)], {"w4": "mid"})["dull_split"], "no_dull")

    def test_small_position_and_late_wallet_do_not_count(self):
        self.assertEqual(run([("w1", 1, 200)], {"w1": "sharp"})["cell"], "none")                       # under the $250 floor
        d = run([("w1", 1, 400)], {"w1": "sharp"}, first_seen={"w1": TIERS.REGISTERED_AT + 1})         # joined the ledger after the frozen date
        self.assertEqual(d["cell"], "none")
        d = run([("w1", 1, 400)], {"w1": "sharp"}, first_seen={"zz": 1})                               # not in the ledger at all
        self.assertEqual(d["cell"], "none")

    def test_read_older_than_an_hour_is_no_read(self):
        d = run([("w1", 1, 400)], {"w1": "sharp"}, lag=A.READ_WINDOW + 1)
        self.assertEqual((d["cell"], d["why"]), ("no_read", "read_too_old"))
        self.assertEqual(run([("w1", 1, 400)], {"w1": "sharp"}, lag=A.READ_WINDOW)["cell"], "agree")

    def test_no_event(self):
        r = row()
        d = A.derive_row(r, St({}), lambda *a: None, Led({}, {}), [], H)
        self.assertEqual((d["cell"], d["why"]), ("no_read", "no_event"))

    def test_same_facts_as_the_step2_tier_play(self):
        """side_facts must count exactly what sf_tiers.tier_plays counts (docs/sharp-tier-prereg.md): same filter, same sides."""
        ws = [{"w": "a", "side": "home", "usd": 500, "cid": "c1", "rk": {"tier": "sharp"}},
              {"w": "b", "side": "away", "usd": 500, "cid": "c1", "rk": {"tier": "dull"}},
              {"w": "c", "side": "home", "usd": 500, "cid": "c1", "rk": {"tier": "sharp"}},
              {"w": "d", "side": "away", "usd": 500, "cid": "c1", "rk": {"tier": "sharp"}},
              {"w": "e", "side": "home", "usd": 500, "cid": "c1", "rk": {"tier": "mid"}}]
        cls = {"a": "sharp", "b": "unproven", "c": "excluded", "d": "sharp", "e": "sharp"}
        fs = {w: TIERS.REGISTERED_AT - 1 for w in "abcde"}
        facts = A.side_facts(ws, cls, fs)
        tiers = {x["w"]: x["rk"] for x in ws}
        k = {"mk": {"c1": {"outs": ["home", "away"], "px": [.5, .5], "px_t": 1, "line": None}}}
        tp = TIERS.tier_plays(ws, cls, tiers, fs, k, TIERS.REGISTERED_AT + 1)
        play = tp["tA"] or tp["tB"]
        # home: one sharp for (a; c is excluded), one sharp against (d), a dull against (b): tA is blocked, tB needs no dull for -> fires for home
        self.assertEqual((facts["home"]["sharp"], facts["away"]["sharp"], facts["away"]["dull"]), (1, 1, 1))
        self.assertEqual(play["side"], "home")
        self.assertEqual((play["sharp_for"], play["sharp_against"], play["dull_against"]), (1, 1, 1))


class Rows(unittest.TestCase):
    def test_eligible(self):
        self.assertTrue(A.eligible(row(firstSeen=A.START)))
        self.assertFalse(A.eligible(row(firstSeen=A.START - 1)))
        self.assertFalse(A.eligible(row(firstSeen=A.START + 100, start=A.START + 50)))        # first seen after tip
        self.assertTrue(A.eligible(row(firstSeen=A.START - 1), start=A.START - 10))            # smoke-test override only

    def test_find_event_needs_the_two_teams_and_a_start_near(self):
        st = St({"c": {"ev": "nba-por-min-2026-11-20", "gst": T0 + 7200, "mt": "moneyline"},
                 "d": {"ev": "nba-por-min-2026-11-25", "gst": T0 + 7200 + 5 * 86400, "mt": "moneyline"}})
        self.assertEqual(A.find_event(st, row(), H.FULL_GAME), {("nba-por-min-2026-11-20", T0 + 7200)})
        self.assertEqual(A.find_event(st, row(game={"gk": "x", "away": "MIN", "home": "POR", "m": "ml", "side": "home"}), H.FULL_GAME), set())

    def test_spread_line_is_matched_as_a_home_line(self):
        r = row(game={"gk": "nba:1", "away": "POR", "home": "MIN", "m": "sp", "side": "home", "hline": -2.5, "line": None})
        st = St({"c1": {"ev": "nba-por-min-2026-11-20", "gst": r["start"], "mt": "spreads"}})

        def mkkf(cut_line, outs):
            k = kf(T0, [("w1", 0, 400)])
            k["mk"]["c1"].update(mt="spreads", line=cut_line, outs=outs)
            return k
        led = Led({"w1": "sharp"}, {"w1": TIERS.REGISTERED_AT - 1})
        # Polymarket's line belongs to outcome 0: Minnesota -2.5 is the home line -2.5
        d = A.derive_row(r, st, lambda *a: mkkf(-2.5, ["Timberwolves", "Trail Blazers"]), led, [], H)
        self.assertNotEqual(d.get("why"), "no_market_at_line")
        # outcome 0 is Portland at -2.5: the home line is +2.5, not the row's -2.5
        d = A.derive_row(r, st, lambda *a: mkkf(-2.5, ["Trail Blazers", "Timberwolves"]), led, [], H)
        self.assertEqual(d["why"], "no_market_at_line")


class Stats(unittest.TestCase):
    def cells(self, mean_a, mean_b, games=60, per=4, sd=0.02):
        rng = random.Random(1)
        mk = lambda m: {f"g{i}": [m + rng.gauss(0, sd) for _ in range(per)] for i in range(games)}   # noqa: E731
        return mk(mean_a), mk(mean_b)

    def test_boost_pass_kill_and_underpowered(self):
        a, b = self.cells(0.03, 0.0)
        c = A.contrast(a, b, random.Random(A.SEED), 0.05 / A.TESTS)
        self.assertEqual(A.verdict("boost", c, 240, 240, 60, 60), "pass")
        self.assertEqual(A.verdict("veto", c, 240, 240, 60, 60), "kill")        # wholly above 0 for a veto
        a, b = self.cells(-0.03, 0.0)
        c = A.contrast(a, b, random.Random(A.SEED), 0.05 / A.TESTS)
        self.assertEqual(A.verdict("boost", c, 240, 240, 60, 60), "kill")
        self.assertEqual(A.verdict("veto", c, 240, 240, 60, 60), "pass")
        self.assertEqual(A.verdict("boost", c, A.MIN_ROWS - 1, 240, 60, 60), "underpowered")
        self.assertEqual(A.verdict("boost", c, 240, 240, A.MIN_GAMES - 1, 60), "underpowered")

    def test_no_difference_is_no_pass(self):
        a, b = self.cells(0.0, 0.0)
        c = A.contrast(a, b, random.Random(A.SEED), 0.05 / A.TESTS)
        self.assertEqual(A.verdict("boost", c, 240, 240, 60, 60), "no pass")
        self.assertEqual(A.verdict("veto", c, 240, 240, 60, 60), "no pass")

    def test_contrast_is_seeded(self):
        a, b = self.cells(0.01, 0.0)
        self.assertEqual(A.contrast(a, b, random.Random(A.SEED), 0.0125), A.contrast(a, b, random.Random(A.SEED), 0.0125))

    def test_registered_constants(self):
        self.assertEqual((A.MIN_ROWS, A.MIN_GAMES, A.TESTS, A.SEED, A.BOOT, A.READ_WINDOW), (150, 40, 4, 20261119, 10000, 3600))
        self.assertEqual(A.START, 1795154400)


if __name__ == "__main__":
    unittest.main()
