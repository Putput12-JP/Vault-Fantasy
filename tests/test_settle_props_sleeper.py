"""settle_bets.py prop settle: a player missing from the box score who took snaps is graded on Sleeper's line (a stat it omits is 0),
a real DNP stays unsettled, the board-vs-box name join drops suffixes, and the Sleeper reads are stored so the rebuild is repeatable."""
import datetime as dt, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import settle_bets as S  # noqa: E402

WK = 8
NOW = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)          # well after week 8: a stored read is final


def record(pid, name, market="rec", line=1.5, team="DEN", proj=1.0):
    snap = {"line": line, "over": -110, "under": -110, "proj": proj, "ts": "2026-10-30T12:00:00Z"}
    return {"season": "2026", "week": WK, "seasonType": "regular", "pid": pid, "name": name, "team": team, "pos": "WR", "opp": "KC",
            "market": market, "open": snap, "cur": snap, "samples": [snap], "firstSeen": snap["ts"], "lastSeen": snap["ts"],
            "commence": "2026-11-01T18:00:00Z"}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data, self.calls = self.tmp.name, []
        self._data, S.DATA = S.DATA, self.data
        S._GAMES_CSV[:] = [[]]                                    # no network: kickoff falls back to the record's commence
        stats = {"Opp Player": {"weeks": [{"wk": WK, "opp": "DEN", "rec": 3, "recyds": 30}]},       # DEN's game is in the box
                 "Chris Godwin Jr.": {"weeks": [{"wk": WK, "opp": "KC", "rec": 4, "recyds": 40}]}}
        self.dump("nflverse_stats_2026.json", stats)
        self.dump("prop_line_history.json", {"props": {str(i): r for i, r in enumerate([
            record("9", "Zero Catch"), record("8", "Inactive Guy"), record("7", "Chris Godwin"), record("6", "Waiting Guy", team="SEA")])}})
        self.sleeper = {"9": {"gp": 1, "off_snp": 29}, "8": {"gms_active": 1}, "7": {"gp": 1, "off_snp": 50, "rec": 4}, "1": {"gp": 1}}

    def tearDown(self):
        S.DATA = self._data
        S._GAMES_CSV[:] = []
        self.tmp.cleanup()

    def dump(self, name, doc):
        with open(os.path.join(self.data, name), "w") as f:
            json.dump(doc, f)

    def get(self, season, week):
        self.calls.append((season, week))
        return self.sleeper if week == WK else None

    def settle(self):
        snaps = {}
        picks, meta = S.settle_props(snaps_for=lambda s: snaps.setdefault(s, S.SleeperSnaps(s, get=self.get, now=NOW)))
        for sn in snaps.values(): sn.save()
        return {p["name"]: p for p in picks}, meta


class SettleTest(Fixture):
    def test_played_zero_graded_dnp_left_out_name_joined(self):
        picks, meta = self.settle()
        z = picks["Zero Catch"]
        self.assertEqual(z["actual"], 0.0); self.assertEqual(z["actual_src"], "sleeper")
        self.assertEqual(z["side"], "under"); self.assertEqual(z["won_close"], 1.0)
        self.assertNotIn("Inactive Guy", picks, "active without a snap: the prop is void")
        self.assertEqual(picks["Chris Godwin"]["actual"], 4, "box score joined by the loose name key, not Sleeper")
        self.assertNotIn("actual_src", picks["Chris Godwin"])
        self.assertNotIn("Waiting Guy", picks, "SEA's game is not in the box yet: wait")
        self.assertEqual((meta["settled_from_sleeper"], meta["did_not_play"]), (1, 1))

    def test_reads_are_stored_and_reused(self):
        self.settle()
        self.assertEqual(self.calls, [("2026", WK)], "one read per week")
        stored = json.load(open(os.path.join(self.data, "sleeper_snaps_2026.json")))["weeks"][str(WK)]["p"]
        self.assertEqual(stored, {"9": {"gp": 1, "off_snp": 29}, "8": {"gms_active": 1}}, "only the players asked about, only the fields used")
        self.sleeper = {}                                         # Sleeper down: the stored read still settles the same way
        picks, _ = self.settle()
        self.assertEqual(self.calls, [("2026", WK)], "a finished week is not read again")
        self.assertEqual(picks["Zero Catch"]["actual"], 0.0)

    def test_sleeper_down_waits(self):
        self.sleeper = None
        picks, meta = self.settle()
        self.assertNotIn("Zero Catch", picks); self.assertEqual(meta["settled_from_sleeper"], 0)
        self.assertFalse(os.path.exists(os.path.join(self.data, "sleeper_snaps_2026.json")))

    def test_live_week_is_read_again(self):
        sn = S.SleeperSnaps("2026", get=self.get, now=dt.datetime(2026, 11, 3, 18, tzinfo=dt.timezone.utc))
        self.assertTrue(sn.player(WK, "9")[0]); sn.save()
        sn = S.SleeperSnaps("2026", get=self.get, now=dt.datetime(2026, 11, 4, tzinfo=dt.timezone.utc))
        sn.player(WK, "9")
        self.assertEqual(len(self.calls), 2, "stat corrections: a week is read again until it settles")


class HelpersTest(unittest.TestCase):
    def test_loose_name_key_matches_the_board(self):
        for a, b in (("Chris Godwin", "Chris Godwin Jr."), ("Kenneth Walker", "Kenneth Walker III"), ("Oronde Gadsden", "Oronde Gadsden II")):
            self.assertEqual(S._jkey(a), S._jkey(b))
        self.assertEqual(S.actual_row({"Deebo Samuel Sr.": {1: {}}}, "Deebo Samuel"), {1: {}})

    def test_week_start(self):
        self.assertEqual(S.nfl_week_start("2026"), dt.datetime(2026, 9, 8, 12, tzinfo=dt.timezone.utc))


if __name__ == "__main__":
    unittest.main()
