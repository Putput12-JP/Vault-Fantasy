"""retier_v2_backfill moves backfilled plays that fail the strict gates to passed, copying everything else as stored. run: python3 -m unittest tests.test_retier_v2_backfill"""
import copy, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import retier_v2_backfill as R


def play(pid, p, hours, status='won', units=1.0):
    return dict(id=pid, kind='prop', start=hours * 3600, firstSeen=0, status=status, units=units, first=dict(price=dict(p=p), why='clears every gate'), hoursEarly=hours)


class Retier(unittest.TestCase):
    def test_moves_only_failing_plays(self):
        B = dict(plays={'bfp|play|a': play('bfp|play|a', 0.45, 10), 'bfp|play|b': play('bfp|play|b', 0.6, 60), 'bfp|play|c': play('bfp|play|c', 0.6, 47.9), 'bfp|play|d': play('bfp|play|d', 0.55, 5)}, passed={})
        moved = R.retier(B)
        self.assertEqual(sorted(B['plays']), ['bfp|play|c', 'bfp|play|d'])
        self.assertEqual(sorted(B['passed']), ['bfp|pass|a', 'bfp|pass|b'])
        self.assertEqual([m['gates'] for m in moved], [['price'], ['early']])
        q = B['passed']['bfp|pass|a']
        self.assertEqual((q['status'], q['units'], q['first']['price']['p']), ('won', 1.0, 0.45))

    def test_idempotent(self):
        B = dict(plays={'bfp|play|a': play('bfp|play|a', 0.4, 100)}, passed={})
        R.retier(B); once = copy.deepcopy(B)
        self.assertEqual(R.retier(B), [])
        self.assertEqual(B, once)

    def test_stored_file_has_no_failing_play_left(self):
        B = json.load(open(os.path.join(ROOT, 'data', 'v2_backfill.json')))
        self.assertEqual([k for k, p in B['plays'].items() if R.fails(p)], [])
        self.assertEqual(len(B['plays']), 1)
        self.assertEqual(len(B['retiered']), 16)


if __name__ == '__main__':
    unittest.main()
