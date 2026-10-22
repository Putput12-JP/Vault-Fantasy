"""The CFB pick rule: 5+ points from the market, week 4 or later, and the model's side is not the favorite. And the one-time re-pick of a stored board and log."""
import os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cfb_model as cm


class Rule(unittest.TestCase):
    def test_underdog_side_is_a_pick(self):
        self.assertTrue(cm.pick_ok(6.0, 6, -3.0))          # home underdog (market home margin -3), model has home 3: home side +6 over the market
        self.assertTrue(cm.pick_ok(-6.0, 6, 3.0))          # away underdog, model likes away

    def test_favorite_side_is_not(self):
        self.assertFalse(cm.pick_ok(6.0, 6, 3.0))          # home favoured by 3, model says home by 9: a pick on the favorite
        self.assertFalse(cm.pick_ok(-6.0, 6, -3.0))        # away favoured, model likes away more

    def test_pickem_has_no_favorite(self):
        self.assertTrue(cm.pick_ok(6.0, 6, 0.0)); self.assertTrue(cm.pick_ok(-6.0, 6, 0.0))

    def test_thresholds_still_apply(self):
        self.assertFalse(cm.pick_ok(4.9, 6, -3.0)); self.assertTrue(cm.pick_ok(5.0, 6, -3.0)); self.assertFalse(cm.pick_ok(8.0, 3, -3.0))


def board_row(key, week, edge, mkt, result, **kw):
    side = 'home' if edge > 0 else 'away'
    b = dict(key=key, week=week, kick=1000 + week, home='H', away='A', side=side, team='H' if side == 'home' else 'A', edge=edge, market_margin=mkt, model_margin=mkt + edge,
             entry=-mkt if side == 'home' else mkt, is_pick=True, pick=dict(side=side), result=result)
    b.update(kw); return b


class Repick(unittest.TestCase):
    def store(self):
        board = [board_row('a', 5, 6.0, -3.0, 'W'), board_row('b', 5, 7.0, 4.0, 'L'), board_row('c', 6, -6.0, -2.0, 'L'), board_row('d', 6, 2.0, -3.0, 'W', is_pick=False, pick=None)]
        board[1]['final'] = dict(side='home', entry=-4.0, edge=7.0, is_pick=True); board[1]['v1'] = dict(edge=6.0, is_pick=True)
        log = [dict(key=b['key'], week=b['week'], edge=b['edge'], market_margin=b['market_margin'], side=b['side'], team=b['team'], entry=b['entry'], result=b['result']) for b in board if b['is_pick']]
        return dict(board=board, log=log)

    def test_drops_favorite_picks_from_board_and_log_only(self):
        st = self.store(); dropped = cm.repick_store(st)
        self.assertEqual([e['key'] for e in dropped], ['b', 'c']); self.assertEqual([e['key'] for e in st['log']], ['a'])
        self.assertEqual([b['is_pick'] for b in st['board']], [True, False, False, False])
        self.assertIsNone(st['board'][1]['pick']); self.assertFalse(st['board'][1]['final']['is_pick']); self.assertFalse(st['board'][1]['v1']['is_pick'])
        self.assertEqual(st['board'][1]['result'], 'L')                       # the lean is still graded, nothing re-projected
        self.assertEqual(st['pick_rule']['id'], cm.PICK_RULE); self.assertEqual([d['result'] for d in st['pick_rule']['dropped']], ['L', 'L'])

    def test_second_run_drops_nothing(self):
        st = self.store(); cm.repick_store(st); again = cm.repick_store(st)
        self.assertEqual(again, []); self.assertEqual(len(st['pick_rule']['dropped']), 2)

    def test_log_summary_record(self):
        st = self.store(); cm.repick_store(st); s = cm.log_summary_of(st['log'])
        self.assertEqual((s['picks'], s['won'], s['lost']), (1, 1, 0))


if __name__ == '__main__':
    unittest.main()
