"""Kalshi depth recorder (nba/scripts/kal_depth.py): dollars at the best price, props only, no invented numbers. No network.

Run from the repo root: python3 -m unittest discover -s tests -p 'test_kal_depth.py'
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'nba', 'scripts'))
import kal_depth as K

P = {'KXNBAPTS', 'KXNBAREB'}


class KalDepth(unittest.TestCase):
    def test_dollars_are_price_times_contracts(self):
        r = K.depth_quotes({'A': [0.40, 0.45]}, {'A': {'series': 'KXNBAPTS'}}, {'A': [500, 400]}, P)
        self.assertEqual(r['A'], [0.40, 0.45, 200, 220])           # 0.40 x 500 = 200 over; (1 - 0.45) x 400 = 220 under

    def test_rounds_to_ten_dollars(self):
        r = K.depth_quotes({'A': [0.40, 0.45]}, {'A': {'series': 'KXNBAPTS'}}, {'A': [503, 404]}, P)
        self.assertEqual(r['A'][2:], [200, 220])

    def test_game_series_left_out(self):
        self.assertEqual(K.depth_quotes({'G': [0.5, 0.55]}, {'G': {'series': 'KXNBAGAME'}}, {'G': [100, 100]}, P), {})

    def test_missing_size_or_price_is_left_out_not_zeroed(self):
        m = {k: {'series': 'KXNBAPTS'} for k in 'ABCD'}
        r = K.depth_quotes({'A': [0.4, 0.45], 'B': [None, 0.45], 'C': [0.4, 0.45], 'D': [0.5, 0.4]}, m,
                           {'A': [None, 10], 'B': [10, 10], 'C': [10, 10]}, P)       # D has no size and a crossed quote
        self.assertEqual(list(r), ['C'])

    def test_unknown_ticker_in_sizes_is_ignored(self):
        self.assertEqual(K.depth_quotes({}, {}, {'Z': [1, 1]}, P), {})


if __name__ == '__main__':
    unittest.main()
