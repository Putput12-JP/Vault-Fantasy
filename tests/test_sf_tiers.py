"""Unit tests for scripts/sf_tiers.py: the three registered CLV-tier shadows, the frozen universe, the cut gate."""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import sf_tiers as T  # noqa: E402

CUT = T.REGISTERED_AT + 3600
FS = T.REGISTERED_AT - 86400 * 30
KF = {"mk": {"c1": {"outs": ["Home", "Away"], "px": [0.60, 0.40], "px_t": CUT - 60, "line": None},
             "c2": {"outs": ["Home", "Away"], "px": [0.55, 0.45], "px_t": CUT - 60, "line": None}}}


def h(w, side, usd=1000, cid="c1"):
    return {"w": w, "side": side, "usd": usd, "cid": cid}


def run(ws, tiers, first_seen=None, cls=None, cut=CUT):
    fs = first_seen if first_seen is not None else {x["w"]: FS for x in ws}
    return T.tier_plays(ws, cls or {}, {w: {"tier": t} for w, t in tiers.items()}, fs, KF, cut)


class Rules(unittest.TestCase):
    def test_a_follows_a_sharp_with_nothing_against(self):
        r = run([h("s", "Home"), h("n", "Away")], {"s": "sharp"})
        self.assertEqual((r["tA"]["side"], r["tA"]["price"], r["tA"]["units"]), ("Home", 0.60, 1))
        self.assertIsNone(r["tB"])
        self.assertIsNone(r["tC"])

    def test_a_is_off_when_a_sharp_is_against_but_not_a_dull(self):
        self.assertIsNone(run([h("s", "Home"), h("s2", "Away")], {"s": "sharp", "s2": "sharp"})["tA"])
        self.assertEqual(run([h("s", "Home"), h("d", "Away")], {"s": "sharp", "d": "dull"})["tA"]["side"], "Home")

    def test_b_fades_dull_money_without_needing_a_sharp(self):
        r = run([h("d", "Home"), h("n", "Away")], {"d": "dull"})
        self.assertEqual((r["tB"]["side"], r["tB"]["price"]), ("Away", 0.40))      # the other side, at its own price
        self.assertIsNone(r["tA"])

    def test_b_is_off_when_dull_money_is_on_both_sides(self):
        self.assertIsNone(run([h("d", "Home"), h("d2", "Away")], {"d": "dull", "d2": "dull"})["tB"])

    def test_c_is_a_and_b_on_the_same_side(self):
        r = run([h("s", "Home"), h("d", "Away")], {"s": "sharp", "d": "dull"})
        self.assertEqual((r["tA"]["side"], r["tB"]["side"], r["tC"]["side"]), ("Home", "Home", "Home"))
        self.assertEqual(r["tC"]["price"], 0.60)                       # the sharps' rung, Home's price
        r = run([h("s", "Home"), h("d", "Away"), h("d2", "Home")], {"s": "sharp", "d": "dull", "d2": "dull"})
        self.assertIsNone(r["tB"])                                       # dull on both sides: no fade
        self.assertIsNone(r["tC"])
        r = run([h("s", "Home"), h("d", "Home"), h("n", "Away")], {"s": "sharp", "d": "dull"})
        self.assertIsNotNone(r["tA"])                                    # dull money on the same side as the sharp: A holds
        self.assertEqual(r["tB"]["side"], "Away")                        # B fades it: opposite sides, so no C

    def test_the_frozen_universe(self):
        ws = [h("s", "Home"), h("n", "Away")]
        late = run(ws, {"s": "sharp"}, first_seen={"s": T.REGISTERED_AT + 1, "n": FS})
        self.assertIsNone(late["tA"])                   # added to the universe after registration: cannot enter
        none = run(ws, {"s": "sharp"}, first_seen={"n": FS})
        self.assertIsNone(none["tA"])                   # never tracked

    def test_excluded_and_unranked_wallets_do_not_count(self):
        self.assertIsNone(run([h("s", "Home"), h("n", "Away")], {"s": "sharp"}, cls={"s": "excluded"})["tA"])
        self.assertIsNone(run([h("s", "Home"), h("n", "Away")], {"s": "mid"})["tA"])
        self.assertIsNone(run([h("s", "Home"), h("n", "Away")], {"s": "thin"})["tA"])

    def test_no_play_before_registration_or_on_a_one_sided_market(self):
        self.assertEqual(run([h("s", "Home"), h("n", "Away")], {"s": "sharp"}, cut=T.REGISTERED_AT - 1), {r: None for r in T.RULES})
        self.assertEqual(run([h("s", "Home")], {"s": "sharp"}), {r: None for r in T.RULES})

    def test_the_graded_rung_carries_the_most_supporting_money(self):
        ws = [h("s1", "Home", 500, "c1"), h("s2", "Home", 900, "c2"), h("n", "Away", 100, "c1")]
        r = run(ws, {"s1": "sharp", "s2": "sharp"})
        self.assertEqual((r["tA"]["cid"], r["tA"]["price"], r["tA"]["support_usd"]), ("c2", 0.55, 900))


if __name__ == "__main__":
    unittest.main()
