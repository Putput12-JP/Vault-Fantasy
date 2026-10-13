"""Sharp Money vs the model tile: Clopper-Pearson interval and the one-price regrade rule. No network.

Run from the repo root: python3 tests/test_cfb_tile.py
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import cfb_model as cm


def row(key, logged, kick, entry, close, margin, result):
    return dict(key=key, logged=logged, kick=kick, entry=entry, espn_close=close, margin=margin, result=result, side='home', cards=None)


class ClopperPearson(unittest.TestCase):
    def check(self, fn):
        for (w, n), (lo, hi) in {(11, 15): (0.449, 0.922), (16, 21): (0.528, 0.918), (78, 156): (0.419, 0.581)}.items():
            got = fn(w, n)
            self.assertAlmostEqual(got[0], lo, delta=0.001); self.assertAlmostEqual(got[1], hi, delta=0.001)

    def test_known_values(self): self.check(cm.clopper_pearson)
    def test_bisection_fallback(self): self.check(cm._cp_bisect)
    def test_edges(self):
        self.assertIsNone(cm.clopper_pearson(0, 0))
        self.assertEqual(cm.clopper_pearson(0, 2)[0], 0.0)
        self.assertEqual(cm.clopper_pearson(2, 2)[1], 1.0)


class Regrade(unittest.TestCase):
    def grade(self, *rows):
        b = list(rows); cm.tile_fields(b); return b

    def test_espn_row_stays_at_entry(self):
        r, = self.grade(row('espn:1', 200, 100, -3.0, -3.0, 3, 'P'))
        self.assertEqual((r['tile_line'], r['tile_line_src'], r['tile_result']), (-3.0, 'entry', 'P'))

    def test_feed_backfill_regraded_at_close(self):
        # entry (the open) says W by 1, the close line is -3.5 so the same margin loses
        r, = self.grade(row('cfb:1', 200, 100, -2.0, -3.5, 3, 'W'))
        self.assertEqual((r['tile_line'], r['tile_line_src'], r['tile_result']), (-3.5, 'close_no_ts', 'L'))
        self.assertEqual((r['result'], r['entry']), ('W', -2.0))       # what the pick cards read is untouched

    def test_logged_at_kick_counts_as_backfill(self):
        r, = self.grade(row('cfb:1', 100, 100, 1.0, -1.0, 0, 'W'))
        self.assertEqual((r['tile_line_src'], r['tile_result']), ('close_no_ts', 'L'))

    def test_live_row_keeps_entry(self):
        r, = self.grade(row('cfb:2', 50, 100, -2.0, -3.5, 3, 'W'))
        self.assertEqual((r['tile_line'], r['tile_line_src'], r['tile_result']), (-2.0, 'entry', 'W'))

    def test_backfill_without_close_gets_no_grade(self):
        r, = self.grade(row('cfb:3', 200, 100, -2.0, None, 3, 'W'))
        self.assertNotIn('tile_result', r)

    def test_unsettled_row_untouched(self):
        r, = self.grade(dict(key='cfb:4', logged=1, kick=2, entry=1.0))
        self.assertNotIn('tile_result', r)

    def test_summary_uses_tile_result_and_keeps_before(self):
        b = [row('cfb:1', 200, 100, -2.0, -3.5, 3, 'W'), row('cfb:2', 50, 100, -2.0, -3.5, 3, 'W')]
        base = cm.tile_cards_summary(b)['table'][0]
        self.assertEqual((base['all'], base['before'], base['n'], base['feed']), ([1, 1], [2, 0], 2, [1, 1]))


class Capture(unittest.TestCase):
    def mk(self, kick=1000, **kw):
        return dict(key='cfb:9', kick=kick, side='home', market_margin=3.0, logged=1, entry=-3.0, espn_close=-4.5, margin=3, result='W', **kw)

    def test_capture_set_before_kick(self):
        r = self.mk(); self.assertTrue(cm.capture_line(r, 900))
        self.assertEqual((r['line_captured'], r['line_captured_at']), (-3.0, '1970-01-01T00:15:00Z'))

    def test_away_side_sign_matches_entry(self):
        r = self.mk(); r['side'] = 'away'; cm.capture_line(r, 900); self.assertEqual(r['line_captured'], 3.0)

    def test_updated_on_later_prekick_run(self):
        r = self.mk(); cm.capture_line(r, 800); r['market_margin'] = 3.5; cm.capture_line(r, 900)
        self.assertEqual((r['line_captured'], r['line_captured_at']), (-3.5, '1970-01-01T00:15:00Z'))

    def test_never_overwritten_at_or_after_kick(self):
        r = self.mk(); cm.capture_line(r, 900); before = dict(r); r['market_margin'] = 9.0
        self.assertFalse(cm.capture_line(r, 1000)); self.assertFalse(cm.capture_line(r, 1500))
        self.assertEqual((r['line_captured'], r['line_captured_at']), (before['line_captured'], before['line_captured_at']))

    def test_grading_uses_captured_line(self):
        r2 = self.mk(); r2['market_margin'] = 2.0; cm.capture_line(r2, 900); r2['entry'] = -1.0; r2['logged'] = 2000
        b = [r2]; cm.tile_fields(b)
        self.assertEqual((r2['tile_line'], r2['tile_line_src'], r2['tile_result']), (-2.0, 'captured_prekick', 'W'))
        self.assertEqual((r2['entry'], r2['result']), (-1.0, 'W'))

    def test_capture_at_or_after_kick_ignored(self):
        for at in ('1970-01-01T00:16:40Z', '1970-01-01T00:20:00Z'):
            r = self.mk(line_captured=-1.0, line_captured_at=at); r['logged'] = 2000; b = [r]; cm.tile_fields(b)
            self.assertEqual((r['tile_line'], r['tile_line_src']), (-4.5, 'close_no_ts'))


if __name__ == '__main__':
    unittest.main()
