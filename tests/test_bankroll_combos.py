"""Bankroll Builder combos (shadow): which picks may pair, caps, and settlement from the picks' results. No network, no tape.

Run from the repo root: python3 -m unittest discover -s tests -p 'test_bankroll_combos.py'
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import bankroll_combos as BC

TIP = 1_800_000_000


def pick(name, stat='pts', side='under', gid='1', team='AAA', book='bet365', odds=-115, pf=0.56, res=None, pid=None):
    dec = 1 / BC.CC.prob(odds)
    return {'k': f'pick|{gid}|{name}', 'name': name, 'pid': pid or hash(name), 'stat': stat, 'side': side, 'line': 10.5, 'gid': gid, 'team': team, 'book': book,
            'odds0': odds, 'dec0': dec, 'pf0': pf, 'tip': TIP, 'first': TIP - 3600, 'res': res, 'legs': [{'name': name, 'y': 3.0}]}


class Kinds(unittest.TestCase):
    def test_pairing_rules(self):
        a = pick('A', 'ast')
        self.assertEqual(BC.kind_of(a, pick('B', '3pm')), 'mates')                      # measured family, same team, same side
        self.assertIsNone(BC.kind_of(a, pick('B', '3pm', side='over')))                 # sides disagree
        self.assertIsNone(BC.kind_of(a, pick('B', 'reb')))                              # no measured lift
        self.assertIsNone(BC.kind_of(a, pick('B', '3pm', team='BBB')))                  # opponents
        self.assertEqual(BC.kind_of(a, pick('B', 'reb', gid='2')), 'cross')
        self.assertIsNone(BC.kind_of(a, pick('B', 'reb', gid='2', book='fanduel')))     # one slip, one book
        self.assertIsNone(BC.kind_of(a, pick('A2', 'reb', gid='2', pid=a['pid'])))      # same player


class Candidates(unittest.TestCase):
    def test_mates_get_the_lift_and_cross_do_not(self):
        a, b, c = pick('A', 'ast'), pick('B', '3pm'), pick('C', 'pts', gid='2')
        out = {x['type']: x for x in BC.candidates([a, b, c], lambda x, y: x['dec0'] * y['dec0'])}
        self.assertGreater(out['mates']['pj'], 0.56 * 0.56)
        self.assertAlmostEqual(out['cross']['pj'], 0.56 * 0.56)

    def test_negative_edge_is_not_a_combo(self):
        self.assertEqual(BC.candidates([pick('A', pf=0.50), pick('B', gid='2', pf=0.50)], lambda x, y: x['dec0'] * y['dec0']), [])

    def test_caps_per_slate_first_come(self):
        pool = [pick(f'P{i}', gid=str(i)) for i in range(8)]                            # 28 cross pairs
        S = {}
        BC.log_new(S, BC.candidates(pool, lambda x, y: x['dec0'] * y['dec0']), TIP - 60)
        self.assertEqual(len(S), BC.CAP['cross'])
        n = BC.log_new(S, BC.candidates(pool, lambda x, y: x['dec0'] * y['dec0']), TIP - 30)
        self.assertEqual(n, 0)                                                          # nothing re-logged, entry stays the first sighting
        self.assertTrue(all(c['first'] == TIP - 60 for c in S.values()))


class Settle(unittest.TestCase):
    def setUp(self):
        a, b = pick('A', gid='1'), pick('B', gid='2')
        S = {}
        BC.log_new(S, BC.candidates([a, b], lambda x, y: x['dec0'] * y['dec0']), TIP - 60)
        self.c = next(iter(S.values()))
        self.a, self.b = a, b

    def run_settle(self, ra, rb):
        self.a['res'], self.b['res'] = ra, rb
        BC.settle_from_picks(self.c, {self.a['k']: self.a, self.b['k']: self.b})
        return self.c.get('res'), self.c.get('units')

    def test_won_pays_the_product(self):
        res, u = self.run_settle('won', 'won')
        self.assertEqual(res, 'won')
        self.assertAlmostEqual(u, self.c['dec0'] - 1, places=3)

    def test_one_loss_loses_before_the_other_settles(self):
        self.assertEqual(self.run_settle('lost', None), ('lost', -1.0))

    def test_void_leg_voids(self):
        self.assertEqual(self.run_settle('won', 'void'), ('void', 0.0))

    def test_waits_for_both(self):
        self.assertEqual(self.run_settle('won', None), (None, None))


if __name__ == '__main__':
    unittest.main()
