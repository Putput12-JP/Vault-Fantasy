"""sharp.prop_behind: DraftKings stays p_behind (id unchanged, frozen test); Polymarket and Novig are p_behind_x, graded apart."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nba', 'scripts'))
import sharp

NOW = 1_800_000_000
TIP = NOW + 4 * 3600
BY_ID = {'g1': {'tip': TIP}}
PIN = {(7, 'pts', 'g1'): [[NOW - 3600, 20.5, 0.50, 5], [NOW - 3000, 20.5, 0.50, 5]]}   # Pinnacle -110/-110 -> fair 0.50, unchanged for 50 min


def board(**kw):
    b = {'src_ok': {s: {'ok': NOW - 60} for s in ('pinnacle', 'espn', 'polymarket', 'novig')},
         'props': [{'p': 7, 's': 'pts', 'g': 'g1', 'books': [['Pinnacle', 20.5, '-110', '-110'], ['DraftKings', 20.5, '+110', '-140'],
                                                              ['Polymarket', 20.5, '+108', '-130']]}],
         'novig': {'props': {'7|pts': {'lad': [{'k': 20.5, 'ask': [0.46, 0.60]}, {'k': 21.5, 'ask': [0.30, 0.80]}]}}}}
    b.update(kw)
    return b


def by_venue(alerts):
    return {a['venue']: a for a in alerts if a['side'] == 'over'}


class PropBehind(unittest.TestCase):
    def test_each_venue_and_type(self):
        o = by_venue(sharp.prop_behind(board(), BY_ID, PIN, NOW))
        self.assertEqual(set(o), {'DraftKings', 'Polymarket', 'Novig'})
        self.assertEqual(o['DraftKings']['type'], 'p_behind')
        self.assertEqual(o['DraftKings']['id'], 'g1:p_behind:7:pts:over:20.5')   # the frozen test's id is unchanged
        self.assertEqual(o['Polymarket']['type'], 'p_behind_x')
        self.assertEqual(o['Novig']['type'], 'p_behind_x')
        self.assertIn('Novig', o['Novig']['id'])

    def test_novig_is_priced_off_its_ask(self):
        a = by_venue(sharp.prop_behind(board(), BY_ID, PIN, NOW))['Novig']
        self.assertEqual(a['price'], 0.46)
        self.assertAlmostEqual(a['ev'], round(0.5 / 0.46 - 1, 3), places=3)
        self.assertEqual(a['line'], 20.5)                                     # never the 21.5 strike

    def test_a_stale_source_blocks_only_its_own_venue(self):
        b = board()
        b['src_ok']['novig']['ok'] = NOW - 3600
        self.assertEqual(set(by_venue(sharp.prop_behind(b, BY_ID, PIN, NOW))), {'DraftKings', 'Polymarket'})
        b['src_ok']['pinnacle']['ok'] = NOW - 3600
        self.assertEqual(sharp.prop_behind(b, BY_ID, PIN, NOW), [])

    def test_pinnacle_still_moving_blocks_all(self):
        P = {(7, 'pts', 'g1'): [[NOW - 3600, 20.5, 0.50, 5], [NOW - 300, 20.5, 0.52, 5]]}
        self.assertEqual(sharp.prop_behind(board(), BY_ID, P, NOW), [])

    def test_different_line_is_not_behind(self):
        b = board()
        b['props'][0]['books'][2][1] = 21.5
        self.assertNotIn('Polymarket', by_venue(sharp.prop_behind(b, BY_ID, PIN, NOW)))

    def test_grading_units_for_both_price_kinds(self):
        n = {'type': 'p_behind_x', 'venue': 'Novig', 'price': 0.5, 'pid': 7, 'stat': 'pts', 'line': 20.5, 'side': 'over', 'fair': 0.52}
        sharp.grade_prop(n, {'7|pts': [20.5, 0.55]}, 25)
        self.assertEqual((n['units'], n['clv']), (1.0, round(0.55 / 0.5 - 1, 3)))
        d = {'type': 'p_behind', 'venue': 'DraftKings', 'price': 120, 'pid': 7, 'stat': 'pts', 'line': 20.5, 'side': 'under', 'fair': 0.5}
        sharp.grade_prop(d, None, 25)
        self.assertEqual(d['units'], -1)


if __name__ == '__main__':
    unittest.main()
