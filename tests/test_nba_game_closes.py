#!/usr/bin/env python3
"""Line-taught ratings (build_game_model option L) and the closing-spread file the daily state build reads (game_closes.py)."""
import datetime as dt, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'nba', 'scripts'))
import build_game_model as GM
import game_pick_record as G


def game(hs, as_, mk=None):
    g = {'game_id': 1, 'season': 2027, 'tip': dt.datetime(2026, 11, 1, 0, 0), 'home': 'AAA', 'away': 'BBB', 'neutral': False, 'playoff': False, 'hs': hs, 'as': as_}
    if mk is not None:
        g['mk'] = mk
    return g


class LineTaught(unittest.TestCase):
    def model(self, **extra):
        m = GM.Model(dict(GM.DEFAULT, K=0.04, **extra))
        m.new_season(2027)
        return m

    def test_off_by_default_ignores_the_line(self):
        a, b = self.model(), self.model()
        a.update(game(120, 100), [])
        b.update(game(120, 100, mk=-30.0), [])                # a closing line on the game changes nothing unless MK_W is set
        self.assertEqual(a.R['AAA'], b.R['AAA'])

    def test_moves_toward_the_closing_line(self):
        m = self.model(MK_W=1.0, MK_K=0.5)
        before = m.predict(game(0, 0), 0, 0)[0]               # home court only
        m.update(game(150, 100, mk=before + 8.0), [])         # the final is a 50-point blowout, the close said 8 better than the model
        self.assertAlmostEqual(m.R['AAA'], 0.5 * 8.0)         # W = 1: only the line moves the rating, by KL of the miss
        self.assertAlmostEqual(m.R['BBB'], -0.5 * 8.0)

    def test_blend_of_line_and_final(self):
        m = self.model(MK_W=0.75, MK_K=0.16)
        base = m.predict(game(0, 0), 0, 0)[0]
        m.update(game(110, 100, mk=base + 4.0), [])
        want = 0.16 * (0.75 * 4.0 + 0.25 * (10.0 - base))
        self.assertAlmostEqual(m.R['AAA'], want)

    def test_game_without_a_line_updates_from_the_final(self):
        a, b = self.model(), self.model(MK_W=0.75, MK_K=0.16)
        a.update(game(110, 100), [])
        g = game(110, 100)
        g['mk'] = None
        b.update(g, [])
        self.assertEqual(a.R['AAA'], b.R['AAA'])


class Closes(unittest.TestCase):
    def test_close_clock_rows_only(self):
        import game_closes as GC, build_game_picks as BG
        row = lambda gid, clock, spread: [gid, clock, 1.0, 220.0, 0.5, 'DraftKings', spread] + [None] * (len(G.COLS) - 7)
        live = {'2026-11-01': {'games': {'9': ['A @ B', 0, 'A', 'B', 100, 110]}, 'rows': [row('9', 'c', -4.5), row('9', 'f', -3.5)]}}
        old_live, old_read = BG.live_days, GC._read
        BG.live_days, GC._read = (lambda: live), (lambda: {'1': -2.0})
        try:
            out = GC.load(fetch=False, save=False)
        finally:
            BG.live_days, GC._read = old_live, old_read
        self.assertEqual(out[9], {'spread_close': -4.5})      # the last look, not the first
        self.assertEqual(out[1], {'spread_close': -2.0})      # stored history is kept


if __name__ == '__main__':
    unittest.main()
