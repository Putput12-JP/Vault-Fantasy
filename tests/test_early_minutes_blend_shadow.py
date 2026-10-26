import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import pricing as PX  # noqa: E402


def pricer(gn=3, first3=None, eb=True):
    p = PX.Pricer.__new__(PX.Pricer)
    p.MM = {"early_blend": {"w": 0.4, "lo": 4, "hi": 10, "min_games": 2}} if eb else {}
    p.state = {"first3": first3 if first3 is not None else {"7": ["BOS", 30.0, 34.0, 32.0], "8": ["BOS", 20.0], "9": ["LAL", 30.0, 30.0]},
               "team_gn": {"BOS": gn, "LAL": gn}}
    return p


GM = {7: {"min": 26.0}, 8: {"min": 20.0}, 9: {"min": 26.0}, 10: {"min": 15.0}}


class EarlyBlendShadow(unittest.TestCase):
    def test_blends_toward_the_first_three_game_average(self):
        out = pricer().game_minutes_blend("BOS", {"season_type": 2}, GM)
        self.assertAlmostEqual(out[7], 26.0 + 0.4 * (32.0 - 26.0))      # f = 32, w = 0.4
        self.assertEqual(set(out), {7})                                  # 8 has one game, 9 is on another team, 10 has no first-three minutes

    def test_only_in_team_games_4_to_10(self):
        for gn, expect in ((2, False), (3, True), (9, True), (10, False)):       # this game is gn + 1
            self.assertEqual(bool(pricer(gn=gn).game_minutes_blend("BOS", {}, GM)), expect, gn)

    def test_nothing_without_state_weight_or_in_preseason(self):
        self.assertEqual(pricer(eb=False).game_minutes_blend("BOS", {}, GM), {})
        self.assertEqual(pricer(first3={}).game_minutes_blend("BOS", {}, GM), {})
        self.assertEqual(pricer().game_minutes_blend("BOS", {"season_type": 1}, GM), {})
        p = pricer(); p.state.pop("team_gn"); p.state["team_gn"] = None
        self.assertEqual(p.game_minutes_blend("BOS", {}, GM), {})


class SettleEndToEnd(unittest.TestCase):
    """minutes_record() on a fake nba-data folder: the blend shadow is scored against the box score next to v2 on the same players."""

    def test_blend_mae_is_scored_beside_v2_and_old_rows_without_it_still_settle(self):
        import json, tempfile, ledger as L
        root, tip = tempfile.mkdtemp(), 1792800000
        d = os.path.join(root, "snapshots", L.tip_day(tip))
        os.makedirs(d)
        metas = [{"k": f"G1|{pid}", "src": "minutes", "game": "G1", "tip": tip, "matchup": "AAA @ BBB", "pid": pid, "player": f"P{pid}", "team": "BBB"} for pid in (1, 2, 3)]
        vals = {1: [24.0, 27.0, None, 0, None, 28.0],       # v2 24, blend 28, played 30 -> blend closer
                2: [20.0, 20.0, None, 0, None, 22.0],       # v2 20, blend 22, played 19 -> v2 closer
                3: [30.0, 30.0, None, 0, None]}              # an old-format row with no blend column
        with open(os.path.join(d, "meta.jsonl"), "w") as f:
            for m in metas:
                f.write(json.dumps(m, separators=(",", ":")) + "\n")
        with open(os.path.join(d, "minutes.jsonl"), "w") as f:
            for pid, v in vals.items():
                f.write(json.dumps({"t": tip - 3600, "k": f"G1|{pid}", "v": v}, separators=(",", ":")) + "\n")
        os.makedirs(os.path.join(root, "results"))
        json.dump({"1": {"minutes": 30.0}, "2": {"minutes": 19.0}, "3": {"minutes": 31.0}}, open(os.path.join(root, "results", "G1.json"), "w"))
        json.dump({"score": {"AAA": 100.0, "BBB": 104.0}}, open(os.path.join(root, "results", "G1.meta.json"), "w"))
        out = L.minutes_record(root, tip + 4 * 3600, None, 3, None)
        day = out[L.tip_day(tip)]
        self.assertEqual(day["n"], 3)
        self.assertEqual(day["blend"], {"n": 2, "mae_v2": 3.5, "mae_blend": 2.5})       # v2: |24-30|, |20-19| = 6, 1; blend: |28-30|, |22-19| = 2, 3



class ForwardScorer(unittest.TestCase):
    def test_scores_only_players_who_played_with_a_blend_value_and_waits_for_the_sample(self):
        import json, tempfile, ledger as L, test_early_minutes_blend as T
        root, tip = tempfile.mkdtemp(), 1792800000
        d = os.path.join(root, "snapshots", L.tip_day(tip))
        os.makedirs(d); os.makedirs(os.path.join(root, "results"))
        rows = {1: [24.0, 27.0, None, 0, None, 28.0], 2: [20.0, 20.0, None, 0, None, 22.0], 3: [30.0, 30.0, None, 0, None], 4: [20.0, 20.0, None, 0, None, 25.0]}
        with open(os.path.join(d, "meta.jsonl"), "w") as f, open(os.path.join(d, "minutes.jsonl"), "w") as g:
            for pid, v in rows.items():
                f.write(json.dumps({"k": f"G1|{pid}", "src": "minutes", "game": "G1", "tip": tip, "matchup": "A @ B", "pid": pid, "player": f"P{pid}", "team": "B"}, separators=(",", ":")) + "\n")
                g.write(json.dumps({"t": tip - 3600, "k": f"G1|{pid}", "v": v}, separators=(",", ":")) + "\n")
        json.dump({"1": {"minutes": 30.0}, "2": {"minutes": 19.0}, "3": {"minutes": 31.0}, "4": {"minutes": 0.0}}, open(os.path.join(root, "results", "G1.json"), "w"))
        res = T.forward(root, now=tip + 4 * 3600)
        self.assertEqual((res["games"], res["rows"], res["verdict"]), (1, 2, "COLLECTING"))      # player 3 has no blend, player 4 did not play



class BlendIsPriced(unittest.TestCase):
    def test_blend_minutes_reads_the_models_minutes(self):
        p = pricer()
        self.assertAlmostEqual(p.blend_minutes("BOS", {"season_type": 2}, {7: 26.0})[7], 26.0 + 0.4 * (32.0 - 26.0))

    def test_shadow_column_starts_from_min_v2_not_the_priced_minutes(self):
        p = pricer()
        gm = {7: {"min": 28.4, "min_v2": 26.0}}
        self.assertAlmostEqual(p.game_minutes_blend("BOS", {"season_type": 2}, gm)[7], 28.4)


if __name__ == "__main__":
    unittest.main()
