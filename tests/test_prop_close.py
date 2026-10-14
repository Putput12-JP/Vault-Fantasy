"""Prop close tape contracts. No network; synthetic feed, ladders and results.

Run from the repo root: python3 -m unittest discover -s tests -p 'test_prop_close.py'
"""
import json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import prop_close_lib as lib
import build_prop_close_tape as tape_mod
import compare_prop_closes as cmp

KICK = '2026-10-18T17:00:00.000Z'
KICK_S = tape_mod.iso_s(KICK)


def feed(quotes=None, commence=KICK, week=5):
    return {'season': '2026', 'week': week, 'season_type': 'regular', 'vegas_player_props': {
        '96': {'name': 'Aaron Rodgers', 'team': 'PIT', 'commence': commence, 'lines': {
            'pass_yd': {'line': 224.5, 'quotes': quotes if quotes is not None else [
                {'book': 'Pinnacle', 'line': 224.5, 'over': -110, 'under': -110},
                {'book': 'PrizePicks', 'line': 224.5, 'over': None, 'under': None}]}}}}}


KAL = {'generated': '2026-10-17T12:00:00Z', 'markets': {'pass_yd': {'aaronrodgers': [
    {'k': 224.5, 'fair': 0.52, 'oi': 40, 'spr': 0.02}, {'k': 249.5, 'fair': 0.34, 'oi': 10, 'spr': 0.03}]}}}
NOV = {'generated': '2026-10-17T12:00:00Z', 'markets': {'pass_yd': {'aaronrodgers': [
    {'k': 224.5, 'fair': 0.5, 'spr': 0.02, 'depth': 900, 't': KICK_S - 3600}]}}}


class Lib(unittest.TestCase):
    def test_devig_even_and_vig(self):
        self.assertAlmostEqual(lib.devig(-110, -110), 0.5)
        self.assertTrue(0.5 < lib.devig(-130, 110) < 0.6)
        self.assertIsNone(lib.devig(None, -110))

    def test_ladder_exact_only_by_default(self):
        rows = [[224.5, 0.52], [249.5, 0.34]]
        self.assertEqual(lib.ladder_p_over(rows, 224.5), 0.52)
        self.assertIsNone(lib.ladder_p_over(rows, 230.5))                 # between strikes: not a guess

    def test_ladder_interp_between_and_never_extrapolates(self):
        rows = [[224.5, 0.52], [249.5, 0.34]]
        mid = lib.ladder_p_over(rows, 237.0, interp=True)
        self.assertTrue(0.34 < mid < 0.52)
        self.assertIsNone(lib.ladder_p_over(rows, 300.5, interp=True))
        self.assertIsNone(lib.ladder_p_over(rows, 100.5, interp=True))

    def test_priced_quote_needs_same_line(self):
        e = {'line': 224.5, 'over': -110, 'under': -110}
        self.assertAlmostEqual(lib.book_p_over(e, 224.5), 0.5)
        self.assertIsNone(lib.book_p_over(e, 225.5))

    def test_nkey(self):
        self.assertEqual(lib.nkey('J.K. Dobbins'), 'jkdobbins')
        self.assertEqual(lib.nkey('Amon-Ra St. Brown'), 'amonrastbrown')


class Builder(unittest.TestCase):
    def run_once(self, t, f, now, kal=KAL, nov=NOV):
        return tape_mod.update(t, f, kal, nov, now)

    def test_key_is_game_date_not_feed_week(self):
        a, b = {'props': {}}, {'props': {}}
        self.run_once(a, feed(week=5), KICK_S - 7200)
        self.run_once(b, feed(week=6), KICK_S - 7200)
        self.assertEqual(list(a['props']), list(b['props']))
        self.assertEqual(list(a['props'])[0], '2026|96|pass_yd|2026-10-18')

    def test_books_recorded_and_pickem_dropped(self):
        t = {'props': {}}
        self.run_once(t, feed(), KICK_S - 7200)
        books = t['props']['2026|96|pass_yd|2026-10-18']['books']
        self.assertEqual(set(books), {'Pinnacle', 'Kalshi', 'Novig'})
        self.assertEqual(books['Kalshi']['ladder'][0], [224.5, 0.52, 40, 0.02])

    def test_missing_book_keeps_last_read(self):
        t = {'props': {}}
        self.run_once(t, feed(), KICK_S - 7200)
        self.run_once(t, feed(quotes=[]), KICK_S - 3600, kal=None, nov=None)          # thin response
        self.assertEqual(set(t['props']['2026|96|pass_yd|2026-10-18']['books']), {'Pinnacle', 'Kalshi', 'Novig'})

    def test_refresh_replaces_a_book_until_kickoff(self):
        t = {'props': {}}
        self.run_once(t, feed(), KICK_S - 7200)
        self.run_once(t, feed(quotes=[{'book': 'Pinnacle', 'line': 225.5, 'over': -115, 'under': -105}]), KICK_S - 600)
        self.assertEqual(t['props']['2026|96|pass_yd|2026-10-18']['books']['Pinnacle']['line'], 225.5)

    def test_frozen_after_kickoff(self):
        t = {'props': {}}
        self.run_once(t, feed(), KICK_S - 600)
        pin_before = dict(t['props']['2026|96|pass_yd|2026-10-18']['books']['Pinnacle'])
        st = self.run_once(t, feed(quotes=[{'book': 'Pinnacle', 'line': 999, 'over': -110, 'under': -110}]), KICK_S + 600)
        self.assertEqual(t['props']['2026|96|pass_yd|2026-10-18']['books']['Pinnacle'], pin_before)
        self.assertEqual(st['frozen'], 1)
        self.assertTrue(t['props']['2026|96|pass_yd|2026-10-18']['frozen'])

    def test_read_stamped_after_kickoff_is_not_a_close(self):
        late = {'generated': '2026-10-18T17:30:00Z', 'markets': KAL['markets']}
        t = {'props': {}}
        self.run_once(t, feed(), KICK_S - 60, kal=late)
        self.assertNotIn('Kalshi', t['props']['2026|96|pass_yd|2026-10-18']['books'])

    def test_preseason_and_empty_props_not_stored(self):
        t = {'props': {}}
        f = feed(); f['season_type'] = 'pre'
        self.run_once(t, f, KICK_S - 7200)
        self.assertEqual(t['props'], {})
        self.run_once(t, feed(quotes=[]), KICK_S - 7200, kal=None, nov=None)
        self.assertEqual(t['props'], {})

    def test_unparseable_tape_stops_the_run(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            f.write('{broken')
        with self.assertRaises(SystemExit):
            tape_mod.load(f.name)
        os.unlink(f.name)

    def test_empty_tape_file_starts_fresh(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            pass
        self.assertIsNone(tape_mod.load(f.name))
        os.unlink(f.name)


class Compare(unittest.TestCase):
    def test_pair_calls_only_with_enough_props_and_clear_gap(self):
        good = [{'p': {'A': 0.7, 'B': 0.5}, 'won_over': True, 'market': 'm'} for _ in range(200)]
        bad = [{'p': {'A': 0.3, 'B': 0.5}, 'won_over': True, 'market': 'm'} for _ in range(200)]
        r = cmp.pair(good + bad, 'A', 'B')
        self.assertEqual(r['n'], 400)
        self.assertEqual(r['verdict'], 'B closer')                      # A wins 200 small, loses 200 big
        self.assertEqual(cmp.pair(good[:20], 'A', 'B')['verdict'], 'too few')
        self.assertEqual(cmp.pair(good, 'A', 'B')['verdict'], 'A closer')

    def test_rows_use_one_shared_line_and_drop_pushes_and_stale_reads(self):
        results = [
            {'season': '2026', 'week': 5, 'pid': '96', 'market': 'pass_yd', 'team': 'PIT', 'actual': 250.0, 'line_close': 224.5, 'close_over': -110, 'close_under': -110},
            {'season': '2026', 'week': 5, 'pid': '97', 'market': 'pass_yd', 'team': 'PIT', 'actual': 224.5, 'line_close': 224.5},          # push
        ]
        kick = {('2026', '5', 'PIT'): KICK}
        tp = {'2026|96|pass_yd|2026-10-18': {'books': {
            'Pinnacle': {'line': 225.5, 'over': -110, 'under': -110, 't': int(KICK_S - 600)},                                            # other line: skipped
            'Kalshi': {'ladder': [[224.5, 0.6]], 't': int(KICK_S - 600)},
            'Novig': {'ladder': [[224.5, 0.55]], 't': int(KICK_S - 6 * 3600)}}}}                                                       # 6h stale: skipped
        rs = cmp.rows(tp, results, kick, lambda t: t, 3 * 3600, False)
        self.assertEqual(len(rs), 1)
        self.assertEqual(set(rs[0]['p']), {'Kalshi', 'Consensus'})
        self.assertTrue(rs[0]['won_over'])


if __name__ == '__main__':
    unittest.main()
