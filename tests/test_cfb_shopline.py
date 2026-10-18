"""The shopped line: the best retail spread for the picked side at the moment a CFB pick is logged, graded like the entry line."""
import os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cfb_model as cm


def q(t, line, hp=-110, ap=-110):          # one tape value: [t, [ml, sp, tot, ...]], sp = [home line, home price, away price]
    return [t, [[-150, 130], [line, hp, ap], [50.5, -110, -110], None, None, None, None]]


TAPE = {'cfb:1|DraftKings': q(100, 3.0), 'cfb:1|FanDuel': q(100, 3.5), 'cfb:1|BetMGM': q(100, 2.5), 'cfb:1|Pinnacle': q(100, 5.0), 'cfb:1|Consensus': q(100, 4.0), 'cfb:1|Novig': [100, [None, None, None, [0.4, 0.5], None, None]]}


class Shop(unittest.TestCase):
    def test_away_pick_takes_the_most_favourable_number(self):
        # home +3.5 at FanDuel means away -3.5; the away side wants the largest own-side line, i.e. the smallest home line: home +2.5 at BetMGM -> away -2.5
        s = cm.shop_line('cfb:1', 'away', TAPE); self.assertEqual((s['best_line'], s['best_book']), (-2.5, 'BetMGM'))

    def test_home_pick_takes_the_most_favourable_number(self):
        s = cm.shop_line('cfb:1', 'home', TAPE); self.assertEqual((s['best_line'], s['best_book']), (3.5, 'FanDuel'))
        self.assertEqual([r['book'] for r in s['spread']], ['DraftKings', 'FanDuel', 'BetMGM'])     # retail books only, in book order; no Pinnacle, Consensus or exchange

    def test_sign_matches_market_margin(self):
        # home -5.5 on the tape = market_margin +5.5; a home pick enters at -5.5 (entry = -market_margin), an away pick at +5.5
        t = {'cfb:2|DraftKings': q(100, -5.5)}
        self.assertEqual(cm.shop_line('cfb:2', 'home', t)['best_line'], -5.5); self.assertEqual(cm.shop_line('cfb:2', 'away', t)['best_line'], 5.5)

    def test_tie_goes_to_book_order(self):
        t = {'cfb:3|bet365': q(100, 3.0), 'cfb:3|FanDuel': q(100, 3.0), 'cfb:3|DraftKings': q(100, 2.5)}
        self.assertEqual(cm.shop_line('cfb:3', 'home', t)['best_book'], 'FanDuel')

    def test_no_tape_row_is_null(self):
        self.assertIsNone(cm.shop_line('cfb:9', 'home', TAPE)); self.assertIsNone(cm.shop_line('cfb:1', 'home', {})); self.assertIsNone(cm.shop_line('cfb:1', 'home', None))
        self.assertIsNone(cm.shop_line('cfb:4', 'home', {'cfb:4|Pinnacle': q(100, 3.0)}))     # only a reference book: not a shop

    def test_snapshot_at_or_before_log_time(self):
        t = dict(TAPE, **{'cfb:1|BetRivers': q(250, 9.0)})                  # a later quote
        self.assertEqual(cm.shop_line('cfb:1', 'home', t, at=200)['best_line'], 3.5); self.assertEqual(cm.shop_line('cfb:1', 'home', t, at=250)['best_line'], 9.0)
        self.assertIsNone(cm.shop_line('cfb:1', 'home', TAPE, at=50))

    def entry(self, **kw):
        e = dict(key='cfb:1', side='home', entry=3.0, backfill=False); e.update(kw); return e

    def test_stamp_once_and_a_later_tape_row_never_rewrites_it(self):
        e = self.entry(); self.assertTrue(cm.stamp_shop(e, TAPE, 200))
        self.assertEqual((e['best_line'], e['best_book'], e['best_at'], e['shop_gain']), (3.5, 'FanDuel', 100, 0.5))
        later = dict(TAPE, **{'cfb:1|BetRivers': q(300, 7.0)})
        self.assertFalse(cm.stamp_shop(e, later, 400)); self.assertEqual((e['best_line'], e['best_book']), (3.5, 'FanDuel'))

    def test_no_stamp_for_backfill_or_no_row(self):
        e = self.entry(backfill=True); self.assertFalse(cm.stamp_shop(e, TAPE, 200)); self.assertNotIn('best_line', e)
        e = self.entry(key='cfb:77'); self.assertFalse(cm.stamp_shop(e, TAPE, 200)); self.assertNotIn('best_line', e)

    def test_grade_like_the_entry_line(self):
        for margin, best, res in ((3, -2.5, 'W'), (2, -2.5, 'L'), (3, -3.0, 'P')):
            e = dict(best_line=best, margin=margin); cm.shop_grade(e); self.assertEqual(e['shop_result'], res)
        e = dict(best_line=None, margin=3); cm.shop_grade(e); self.assertNotIn('shop_result', e)
        e = dict(best_line=-2.5); cm.shop_grade(e); self.assertNotIn('shop_result', e)

    def test_summary_null_until_data_then_counts_only_shopped_picks(self):
        log = [dict(key='a', result='W', entry=3.0), dict(key='b', result='L', entry=3.0)]
        self.assertIsNone(cm.log_summary_of(log)['shopped'])
        log[0].update(best_line=3.5, shop_gain=0.5, shop_result='W'); log[1].update(best_line=4.0, shop_gain=1.0, shop_result='W')
        log.append(dict(key='c', entry=1.0, best_line=1.5, shop_gain=0.5))        # not graded yet
        s = cm.log_summary_of(log); self.assertEqual((s['won'], s['lost']), (1, 1))        # the entry-line record is untouched
        self.assertEqual(s['shopped'], dict(picks=3, n=3, graded=2, won=2, lost=0, pushed=0, gain_mean=0.67))

    def test_repick_keeps_the_stamp_on_what_stays(self):
        from test_cfb_pickrule import board_row
        b = board_row('a', 5, 6.0, -3.0, 'W', best_line=-2.5, best_book='X')
        st = dict(board=[b], log=[dict(key='a', week=5, edge=6.0, market_margin=-3.0, side='home', team='H', entry=3.0, result='W', best_line=-2.5)])
        cm.repick_store(st); self.assertEqual(st['log'][0]['best_line'], -2.5); self.assertEqual(st['board'][0]['best_line'], -2.5)


if __name__ == '__main__':
    unittest.main()
