"""Exchange-depth shadow contracts (docs/exchange-depth-prereg.md): per-side depth, the frozen p_dep rule, one alert per side. No network.

Run from the repo root: python3 -m unittest discover -s tests -p 'test_exchange_depth.py'
"""
import json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'nba', 'scripts'))
import novig
import sharp

TIP = 1_800_000_000
T0 = TIP - 3600
BY_ID = {'7': {'tip': TIP}}


def day_dir(rows):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, 'novigdepth.jsonl'), 'w') as f:
        for t, k, v in rows:
            f.write(json.dumps({'t': t, 'k': k, 'v': v}) + '\n')
    return d


def run(rows, polls=None):
    return sharp.dep_prop_signals([day_dir(rows)], BY_ID, polls if polls is not None else [T0 - 60, T0 + 540, T0 + 1000], {'7': TIP})


class DepthRule(unittest.TestCase):
    def test_heavier_side_with_floor_and_ratio_fires(self):
        a = run([(T0, '7|11|pts|20.5', [0.40, 0.44, 300, 900])])
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]['side'], 'under')
        self.assertAlmostEqual(a[0]['fair'], 0.58, places=3)       # the under's mid: 1 - 0.42
        self.assertEqual(a[0]['type'], 'p_dep')

    def test_over_side_uses_the_over_mid(self):
        a = run([(T0, '7|11|pts|20.5', [0.60, 0.64, 1200, 400])])
        self.assertEqual((a[0]['side'], a[0]['fair']), ('over', 0.62))

    def test_below_floor_or_ratio_is_silent(self):
        self.assertEqual(run([(T0, '7|11|pts|20.5', [0.5, 0.52, 400, 100])]), [])       # 400 < 500
        self.assertEqual(run([(T0, '7|11|pts|20.5', [0.5, 0.52, 900, 600])]), [])       # 1.5x < 2x

    def test_wide_quote_and_after_tip_are_ignored(self):
        self.assertEqual(run([(T0, '7|11|pts|20.5', [0.30, 0.55, 900, 100])]), [])      # spread 0.25 > 0.10
        self.assertEqual(run([(TIP + 5, '7|11|pts|20.5', [0.5, 0.52, 900, 100])]), [])

    def test_one_alert_per_strike_side_first_sighting(self):
        rows = [(T0, '7|11|pts|20.5', [0.5, 0.52, 900, 100]), (T0 + 600, '7|11|pts|20.5', [0.55, 0.57, 1500, 100])]
        a = run(rows)
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]['t'], T0)                            # the first sighting keeps its time and price

    def test_no_recent_poll_no_alert(self):
        self.assertEqual(run([(T0, '7|11|pts|20.5', [0.5, 0.52, 900, 100])], polls=[T0 - 99999]), [])

    def test_old_four_field_rows_are_not_required_but_short_rows_skip(self):
        self.assertEqual(run([(T0, '7|11|pts|20.5', [0.5, 0.52, 900])]), [])


class PerSideDepth(unittest.TestCase):
    def test_read_book_dp_is_per_outcome_and_depth_is_unchanged(self):
        mk = {'outcomes': [{'outcomeId': 'a'}, {'outcomeId': 'b'}]}
        book = {'orders': {'a': [{'price': '0.60', 'qty': 100000}, {'price': '0.59', 'qty': 50000}, {'price': '0.40', 'qty': 999900}],
                           'b': [{'price': '0.38', 'qty': 10000}]}}
        r = novig.read_book(mk, book)
        self.assertEqual(r['dp'], [round(600 + 295), 38])          # the 0.40 order is more than 3 cents under the best bid
        self.assertEqual(r['depth'], 895 + 38)

    def test_empty_side_is_zero_not_a_shifted_index(self):
        mk = {'outcomes': [{'outcomeId': 'a'}, {'outcomeId': 'b'}]}
        r = novig.read_book(mk, {'orders': {'a': [], 'b': [{'price': '0.40', 'qty': 50000}]}})
        self.assertEqual(r['dp'], [0, 200])

    def test_depth_quotes_row_shape_and_rounding(self):
        out = {'props': {'k': {'g': 7, 'p': 11, 's': 'pts', 'lad': [
            {'o': ['Over', 'Under'], 'k': 20.5, 'bid': [0.4, 0.5], 'ask': [0.5, 0.6], 'dp': [349, 951], 'id': 'm1'},
            {'o': ['Under', 'Over'], 'k': 21.5, 'bid': [0.5, 0.3], 'ask': [0.7, 0.5], 'dp': [610, 90], 'id': 'm2'}]}}}
        rows, meta = novig.depth_quotes(out, [{'id': 7}])
        self.assertEqual(rows['7|11|pts|20.5'], [0.4, 0.5, 300, 1000])
        self.assertEqual(rows['7|11|pts|21.5'], [0.3, 0.5, 100, 600])    # outcome order flipped: over is index 1
        self.assertEqual(meta['7|11|pts|20.5']['mid'], 'm1')


if __name__ == '__main__':
    unittest.main()
