"""sharp.pin_move: Pinnacle's last move on the number a soft book is behind on. Never guessed: None without an earlier row."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nba', 'scripts'))
import sharp

#      t    sp    spP   tot  oP   ml    lim
S = [[100, -3.5, 0.52, 220, 0.50, 0.60, [1]],
     [200, -3.5, 0.52, 220, 0.50, 0.60, [1]],
     [300, -4.5, 0.55, 221, 0.50, 0.62, [1]]]


class PinMove(unittest.TestCase):
    def test_spread_line_moved(self):
        self.assertEqual(sharp.pin_move(S, 'sp', 'home', -4.5), {'t': 300, 'line0': -3.5, 'p0': 0.52, 'p1': 0.55})

    def test_away_side_is_the_complement(self):
        self.assertEqual(sharp.pin_move(S, 'ml', 'away', None), {'t': 300, 'line0': None, 'p0': 0.4, 'p1': 0.38})

    def test_time_is_the_first_row_of_the_current_run(self):
        T = S + [[400, -4.5, 0.55, 221, 0.50, 0.62, [1]]]
        self.assertEqual(sharp.pin_move(T, 'sp', 'home', -4.5)['t'], 300)

    def test_alternate_number_is_none(self):
        self.assertIsNone(sharp.pin_move(S, 'sp', 'home', -3.5))

    def test_no_earlier_row_is_none(self):
        self.assertIsNone(sharp.pin_move(S[:1], 'ml', 'home', None))
        self.assertIsNone(sharp.pin_move([], 'ml', 'home', None))

    def test_unmoved_market_is_none(self):
        self.assertIsNone(sharp.pin_move(S[:2], 'tot', 'over', 220))

    def test_prop(self):
        P = [[1, 20.5, 0.50, 5], [2, 20.5, 0.58, 5]]
        self.assertEqual(sharp.pin_move(P, None, 'under', 20.5, prop=True), {'t': 2, 'line0': 20.5, 'p0': 0.5, 'p1': 0.42})
        self.assertIsNone(sharp.pin_move(P, None, 'over', 21.5, prop=True))


if __name__ == '__main__':
    unittest.main()
