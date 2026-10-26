import copy, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import pricing as PX  # noqa: E402

AST = {k: [1.0, 1, v] for k, v in (("rim", 10.0), ("smid", 0.0), ("lmid", 0.0), ("c3", 0.0), ("arc3", -10.0))}
DD = {"players": {"7": {"fga": 300, "ast": 100, "zone": {"c3": 0.2, "ab3": 0.3, "ra": 0.3, "paint": 0.1, "mid": 0.1},
                        "ast_share": {"rim": 0.5, "smid": 0.1, "lmid": 0.1, "c3": 0.1, "arc3": 0.2}},
                 "8": {"fga": 30, "ast": 10, "zone": {"c3": 0.5, "ab3": 0.5, "ra": 0, "paint": 0, "mid": 0}},
                 "9": {"fga": 300, "ast": 100, "zone": {"c3": 0.0, "ab3": 0.02, "ra": 0.9, "paint": 0.05, "mid": 0.03}}},
      "teams": {"OPP": {"zone": {"c3": [1, 1, 20.0], "ab3": [1, 1, 10.0]}, "ast": AST}}}
MT = {"enabled": True, "clip": [0.7, 1.3], "stats": {"3pm": {"beta": 0.12}, "ast": {"beta": 0.36}}}


TA = {"teams": {"OPP": {"P_vol": 0.05, "P_eff": -0.02, "R_miss": 0.03}}}
MT["stats"]["pts"] = {"team_terms": [{"index": "P_vol", "beta": 0.7}, {"index": "P_eff", "beta": 0.5}]}
MT["stats"]["reb"] = {"team_terms": [{"index": "R_miss", "beta": 0.26}]}


def pricer(enabled=True, example=False, ta=TA):
    p = PX.Pricer.__new__(PX.Pricer)
    p.DDF, p.MT, p.TA, p.example = DD, dict(copy.deepcopy(MT), enabled=enabled), ta, example
    return p


class MatchupTerm(unittest.TestCase):
    def test_three_point_index_is_his_mix_against_the_defense(self):
        # c3 share 0.2 x +20% and ab3 share 0.3 x +10%, over the 0.5 three-point share: (4 + 3) / 0.5 = 14 percent
        self.assertAlmostEqual(pricer().matchup_idx(7, "OPP", "3pm"), 0.14)

    def test_assist_index_weights_his_assist_locations(self):
        self.assertAlmostEqual(pricer().matchup_idx(7, "OPP", "ast"), (0.5 * 10 + 0.2 * -10) / 100)

    def test_term_is_mu_times_the_clipped_multiplier(self):
        self.assertAlmostEqual(pricer().matchup_term(7, "OPP", "3pm", 2.0), 2.0 * 0.12 * 0.14)
        self.assertAlmostEqual(pricer().matchup_term(7, "OPP", "ast", 5.0), 5.0 * 0.36 * 0.03)

    def test_clip(self):
        p = pricer(); p.MT["stats"]["3pm"]["beta"] = 100.0
        self.assertAlmostEqual(p.matchup_term(7, "OPP", "3pm", 1.0), 0.3)

    def test_points_use_both_team_indices_and_rebounds_one(self):
        self.assertAlmostEqual(pricer().matchup_x(7, "OPP", "pts"), 0.7 * 0.05 + 0.5 * -0.02)
        self.assertAlmostEqual(pricer().matchup_term(7, "OPP", "pts", 20.0), 20.0 * (0.7 * 0.05 + 0.5 * -0.02))
        self.assertAlmostEqual(pricer().matchup_term(None, "OPP", "reb", 8.0), 8.0 * 0.26 * 0.03)      # the player does not matter at team level

    def test_team_level_term_needs_the_file_a_known_opponent_and_the_switch(self):
        self.assertEqual(pricer(ta=None).matchup_term(7, "OPP", "pts", 20.0), 0.0)
        self.assertEqual(pricer().matchup_term(7, "NOPE", "pts", 20.0), 0.0)
        self.assertEqual(pricer(enabled=False).matchup_term(7, "OPP", "reb", 8.0), 0.0)
        self.assertEqual(pricer(example=True).matchup_term(7, "OPP", "pts", 20.0), 0.0)
        p = pricer(); p.MT["stats"]["pts"]["team_terms"][0]["beta"] = 100.0
        self.assertAlmostEqual(p.matchup_term(7, "OPP", "pts", 10.0), 3.0)                                # clipped at 1.3

    def test_a_team_file_missing_an_index_gives_no_term_not_an_error(self):
        old = {"teams": {"OPP": {"P_vol": 0.05, "P_eff": -0.02, "R_miss": 0.03}}}                 # built before S_tov / T_forced / Pace existed
        p = pricer(ta=old)
        p.MT["stats"]["stl"] = {"team_terms": [{"index": "Pace", "beta": -0.05}, {"index": "S_tov", "beta": 0.68}]}
        self.assertIsNone(p.matchup_x(7, "OPP", "stl"))
        self.assertEqual(p.matchup_term(7, "OPP", "stl", 1.0), 0.0)
        self.assertIsNotNone(p.matchup_x(7, "OPP", "pts"))                                         # the indices it does have still work

    def test_nothing_when_thin_off_unknown_or_example(self):
        self.assertIsNone(pricer().matchup_idx(8, "OPP", "3pm"))              # under 50 shots
        self.assertIsNone(pricer().matchup_idx(9, "OPP", "3pm"))              # under 5% of his shots are threes
        self.assertIsNone(pricer().matchup_idx(8, "OPP", "ast"))              # no assist shares
        self.assertIsNone(pricer(enabled=False).matchup_idx(7, "OPP", "3pm"))
        self.assertIsNone(pricer().matchup_idx(7, "NOPE", "3pm"))
        self.assertIsNone(pricer().matchup_idx(7, "OPP", "pts"))              # points use the team-level path, not the player-mix index
        self.assertEqual(pricer(example=True).matchup_term(7, "OPP", "3pm", 2.0), 0.0)


if __name__ == "__main__":
    unittest.main()
