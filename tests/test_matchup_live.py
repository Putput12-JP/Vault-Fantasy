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


def pricer(enabled=True, example=False):
    p = PX.Pricer.__new__(PX.Pricer)
    p.DDF, p.MT, p.example = DD, dict(copy.deepcopy(MT), enabled=enabled), example
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

    def test_nothing_when_thin_off_unknown_or_example(self):
        self.assertIsNone(pricer().matchup_idx(8, "OPP", "3pm"))              # under 50 shots
        self.assertIsNone(pricer().matchup_idx(9, "OPP", "3pm"))              # under 5% of his shots are threes
        self.assertIsNone(pricer().matchup_idx(8, "OPP", "ast"))              # no assist shares
        self.assertIsNone(pricer(enabled=False).matchup_idx(7, "OPP", "3pm"))
        self.assertIsNone(pricer().matchup_idx(7, "NOPE", "3pm"))
        self.assertIsNone(pricer().matchup_idx(7, "OPP", "pts"))              # not a matchup stat yet
        self.assertEqual(pricer(example=True).matchup_term(7, "OPP", "3pm", 2.0), 0.0)


if __name__ == "__main__":
    unittest.main()
