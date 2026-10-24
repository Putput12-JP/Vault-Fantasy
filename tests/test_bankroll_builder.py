"""Bankroll Builder v3 contracts: unders only, overs shadowed, and the v2 -> v3 cutover. No network, no tape; synthetic candidates and a fake model.

Run from the repo root: python3 -m unittest discover -s tests -p 'test_bankroll_builder.py'
"""
import json, os, sys, tempfile, unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import bankroll_builder as BB

TIP = 1_800_000_000
NOW = TIP - 6 * 3600


def cand(name, side, odds=-115, mk=0.03, n=4, stat='pts', line=20.5):
    cost = BB.CC.prob(odds)
    return {'name': name, 'stat': stat, 'side': side, 'line': line, 'main': line, 'alt': False, 'book': 'bet365', 'odds': odds, 'dec': 1 / cost, 'cost': cost,
            'pf': cost * (1 + mk), 'n': n, 'mk': mk, 'gid': '1', 'tip': TIP, 'away': 'AAA', 'home': 'HHH'}


class FakeOracle:
    def leg(self, name, stat, gid, away, home):
        return {'mu': 1, 'extra': None, 'mmin': 30, 'recent': 30, 'team': 'AAA', 'why': None, 'pid': hash(name) % 1000, 'held': None}

    def chance(self, leg, stat, side, line):
        return 0.6


class Step(unittest.TestCase):
    def setUp(self):
        self._mc, self._pn, self._st, self._po, self._cc = BB.market_cands, BB.CC.price_now, BB.CC.settle, BB.PICK_OVERS, BB.chalk_cands
        BB.chalk_cands = lambda props, now: []
        BB.CC.price_now = lambda c, props: None
        BB.CC.settle = lambda c, now: None

    def tearDown(self):
        BB.market_cands, BB.CC.price_now, BB.CC.settle, BB.PICK_OVERS, BB.chalk_cands = self._mc, self._pn, self._st, self._po, self._cc

    def run_step(self, cands):
        BB.market_cands = lambda props, now: cands
        S = {'picks': {}, 'shadow': {}}
        BB.step(S, [], NOW, lambda n: FakeOracle(), props={})
        return S

    def test_over_is_shadowed_under_is_a_pick(self):
        S = self.run_step([cand('Over Guy', 'over'), cand('Under Guy', 'under')])
        self.assertEqual([p['side'] for p in S['picks'].values()], ['under'])
        self.assertEqual([(p['kind'], p['side']) for p in S['shadow'].values()], [('over_watch', 'over')])

    def test_pick_overs_flag_is_v2(self):
        BB.PICK_OVERS = 1
        S = self.run_step([cand('Over Guy', 'over'), cand('Under Guy', 'under')])
        self.assertEqual(sorted(p['side'] for p in S['picks'].values()), ['over', 'under'])
        self.assertFalse(S['shadow'])

    def test_shadowed_over_does_not_use_a_pick_slot(self):
        cs = [cand(f'Over {i}', 'over') for i in range(5)] + [cand('Under Guy', 'under')]
        S = self.run_step(cs)
        self.assertEqual(len(S['picks']), 1)
        self.assertEqual(len(S['shadow']), 5)

    def test_over_failing_the_market_gate_is_not_watched(self):
        S = self.run_step([cand('Over Guy', 'over', mk=-0.01), cand('Over Few', 'over', n=2)])
        self.assertFalse([p for p in S['shadow'].values() if p['kind'] == 'over_watch'])

    def test_chalk_is_a_shadow_with_no_made_up_fair_price(self):
        def chalk(name, odds):
            c = cand(name, 'under', odds=odds, mk=0.0, n=0)
            return dict(c, pf=None, mk=None, n=0)
        BB.chalk_cands = lambda props, now: [chalk('Chalk A', -330), chalk('Chalk B', -520)]
        S = self.run_step([])
        ch = [p for p in S['shadow'].values() if p['kind'] == 'chalk_watch']
        self.assertEqual(len(ch), 2)
        self.assertFalse(S['picks'])
        self.assertTrue(all(p['pf0'] is None and p['mk0'] is None and p['kf'] == 0.0 for p in ch))
        rec = BB.summarize(S)
        self.assertEqual((rec['shadow']['chalk_300']['picks'], rec['shadow']['chalk_400']['picks']), (1, 1))
        self.assertEqual(rec['all']['picks'], 0)

    def test_summarize_keeps_both_shadows_apart(self):
        S = self.run_step([cand('Over Guy', 'over'), cand('Under Guy', 'under')])
        rec = BB.summarize(S)
        self.assertEqual(rec['rules'], 'v3')
        self.assertEqual(rec['shadow']['over_watch']['picks'], 1)
        self.assertEqual(rec['shadow']['model_only']['picks'], 0)
        self.assertEqual([p['kind'] for p in rec['shadow_list']], ['over_watch'])
        self.assertEqual(rec['all']['picks'], 1)


def stored(kind, name, side, first, res=None, source=None):
    p = {'k': f'{kind}|1|{name}', 'kind': kind, 'type': 'straight', 'book': 'bet365', 'first': first, 'tip': TIP, 'gid': '1', 'name': name, 'team': 'AAA', 'pid': 1, 'away': 'AAA',
         'home': 'HHH', 'stat': 'pts', 'side': side, 'line': 20.5, 'main': 20.5, 'alt': False, 'tier': 'standard', 'agree': True, 'held': None, 'odds0': -115, 'dec0': 1.87,
         'pf0': 0.58, 'n0': 4, 'pm0': 0.6, 'mk0': 0.03, 'md0': 0.05, 'kf': 0.01, 'legs': [{'name': name, 'stat': 'pts', 'side': side, 'line': 20.5, 'gid': '1', 'tip': TIP, 'odds': -115}]}
    if res:
        p.update(res=res, units=0.87 if res == 'won' else -1.0, clv=0.02)
    if source:
        p['source'] = source
    return p


class Adopt(unittest.TestCase):
    def test_cutover_keeps_v2_rebuilds_history_and_carries_live(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            old = (BB.SS, BB.STATE, BB.RECORD)
            BB.SS, BB.STATE, BB.RECORD = d, d / 'bankroll_picks.json', d / 'bankroll_record.json'
            try:
                cut = 1000
                live = {'picks': {}, 'shadow': {}}
                for p in (stored('pick', 'Early Over', 'over', 500, 'lost'), stored('pick', 'Late Under', 'under', 1500), stored('pick', 'Late Over', 'over', 1600)):
                    live['picks'][p['k']] = p
                live['shadow']['model_only|1|Late Shadow'] = stored('model_only', 'Late Shadow', 'under', 1700)
                BB.STATE.write_text(json.dumps(live))
                BB.RECORD.write_text(json.dumps({'all': {'picks': 3}}))
                replay = {'picks': {}, 'shadow': {}}
                for p in (stored('pick', 'Early Under', 'under', 400, 'won'),):
                    replay['picks'][p['k']] = p
                (d / 'bankroll_backtest_v3_picks.json').write_text(json.dumps(replay))
                (d / 'bankroll_backtest_v3_record.json').write_text(json.dumps({'boards': 1, 'days': ['x'], 'models': ['m'], 'polls': 2, 'last_poll': cut - 1}))
                rec = BB.adopt_v3()
                N = json.loads(BB.STATE.read_text())
                self.assertEqual(rec['rules'], 'v3')
                self.assertEqual(sorted(N['picks']), ['pick|1|Early Under', 'pick|1|Late Under'])          # the early over is gone from the headline; history is the replay
                self.assertEqual(N['picks']['pick|1|Early Under']['source'], 'replay')
                self.assertNotIn('source', N['picks']['pick|1|Late Under'])                                   # a live pick stays live
                self.assertEqual(sorted(N['shadow']), ['model_only|1|Late Shadow', 'over_watch|1|Late Over'])
                self.assertEqual(N['shadow']['over_watch|1|Late Over']['kind'], 'over_watch')
                self.assertEqual(json.loads((d / 'bankroll_record_v2_final.json').read_text()), {'all': {'picks': 3}})   # the v2 record is kept as it was
                self.assertIn('Early Over', (d / 'bankroll_picks_v2_final.json').read_text())
                self.assertIsNone(BB.adopt_v3())                                                              # idempotent
                self.assertEqual(json.loads((d / 'bankroll_picks_v2_final.json').read_text())['picks'].keys(), live['picks'].keys())
            finally:
                BB.SS, BB.STATE, BB.RECORD = old


if __name__ == '__main__':
    unittest.main()
