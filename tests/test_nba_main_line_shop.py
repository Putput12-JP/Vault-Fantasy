"""NBA main line: the Action Network books (e['shop']) vote on the line. No network; synthetic board rows.

Run from the repo root: python3 -m unittest tests.test_nba_main_line_shop
(needs numpy, as prop_sim_record does)
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'nba', 'scripts'))
import prop_sim_record as PSR
import lean_record as LR
import repair_shop_lines as RSL

PM = ['Polymarket', 1.5, '-646', '-10421', 1.5, None, 1795542919, [6, 10]]       # Bam Adebayo assists, 2026-11-24: a thin rung, no bid on the under
FD = ['FanDuel', 3.5, '+108', '-144', 3.5, '+104', 1795544724]
FN = ['Fanatics', 3.5, '+100', '-130', 3.5, '+100', 1795546524]
DK = ['DraftKings', 4.5, '-110', '-110', 4.5, '-110', 1795544000]
PIN = ['Pinnacle', 4.5, '-115', '-105', 4.5, '-115', 1795544000]


def prop(books=(), shop=(), pk=()):
    return {'p': 1, 's': 'ast', 'g': '9', 'kal': [], 'books': list(books), 'shop': list(shop), 'pk': list(pk)}


class MainLine(unittest.TestCase):
    def test_a_prop_only_the_shop_books_post_takes_their_line_not_a_polymarket_rung(self):
        line, p, src = PSR.main_line(prop(books=[PM], shop=[FD, FN]))
        self.assertEqual((line, src), (3.5, 'books'))
        self.assertAlmostEqual(p, (0.4808 / (0.4808 + 0.5902) + 0.5 / (0.5 + 0.5652)) / 2, places=3)   # FanDuel and Fanatics, vig removed

    def test_the_shop_line_beats_a_pickem_line(self):
        line, _, src = PSR.main_line(prop(shop=[FD, FN], pk=[['Underdog', 4.5, '-120', '-110', 4.5, 1795410635]]))
        self.assertEqual((line, src), (3.5, 'books'))

    def test_the_price_is_the_books_when_they_post_the_line_and_the_shop_when_they_do_not(self):
        e = prop(books=[DK], shop=[['FanDuel', 4.5, '+120', '-150', 4.5, '+120', 1]])
        _, p, _ = PSR.main_line(e)                                    # DraftKings and FanDuel both at 4.5: the price is DraftKings' alone, as before the fix
        self.assertAlmostEqual(p, 0.5)
        line, p2, _ = PSR.main_line(prop(books=[DK], shop=[FD, FN, ['bet365', 3.5, '+110', '-140', 3.5, None, 1]]))
        self.assertEqual(line, 3.5)                                   # three shop books at 3.5 outvote DraftKings at 4.5: that line's price is the shop's
        self.assertNotAlmostEqual(p2, 0.5, places=2)

    def test_pinnacle_still_breaks_a_tie(self):
        line, _, _ = PSR.main_line(prop(books=[PIN], shop=[FD]))
        self.assertEqual(line, 4.5)

    def test_polymarket_alone_is_still_no_line(self):
        self.assertIsNone(PSR.main_line(prop(books=[PM])))

    def test_unchanged_where_the_shop_books_are_absent(self):
        for e in (prop(books=[DK, PIN]), prop(books=[DK], pk=[['Underdog', 5.5, '-120', '-110', 5.5, 1]]), prop(pk=[['PrizePicks', 5.5, None, None, 5.5, 1]])):
            self.assertEqual(PSR.main_line(e), RSL.main_line_before(e))


class BestPrice(unittest.TestCase):
    def test_a_shop_only_line_has_a_price(self):
        self.assertEqual(LR.best_price(prop(shop=[FD, FN]), 3.5, 'O'), ('+108', 'FanDuel'))
        self.assertEqual(LR.best_price(prop(shop=[FD, FN]), 3.5, 'U'), ('-130', 'Fanatics'))

    def test_a_price_the_record_already_had_is_never_replaced_by_a_softer_book(self):
        e = prop(books=[['DraftKings', 3.5, '+100', '-130', 3.5, None, 1]], shop=[['FanDuel', 3.5, '+110', '-125', 3.5, None, 1]])
        self.assertEqual(LR.best_price(e, 3.5, 'O'), ('+100', 'DraftKings'))


class Repair(unittest.TestCase):
    def test_same_line_changes_only_the_price_and_source(self):
        old = [4.5, 4.1, .55, .56, .57, None, 'pickem']
        new = [4.5, 9.9, .1, .1, .1, .52, 'books']
        self.assertEqual(RSL.fix_row('psim', old, new), [4.5, 4.1, .55, .56, .57, .52, 'books'])

    def test_a_new_line_takes_the_new_row_and_keeps_the_leans_minutes_and_starter(self):
        old = [24.5, 22.0, 5.0, .4, 'U', None, None, 31.0, 1, None, None, 'pickem']
        new = [25.5, 22.0, 5.0, .35, 'U', .4, .45, 99.0, 0, '-110', 'FanDuel', 'books']
        self.assertEqual(RSL.fix_row('leans', old, new), [25.5, 22.0, 5.0, .35, 'U', .4, .45, 31.0, 1, '-110', 'FanDuel', 'books'])


if __name__ == '__main__':
    unittest.main()
