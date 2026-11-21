"""Game rows voided for a missing final reopen once it is stored; ESPN's short NBA codes match the feed's (Nov 12 2026 fix)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import backfill_edge_results as B  # noqa: E402
import reopen_v2_game_voids as R  # noqa: E402


def row(status, kind='book', gk='nba:1', **kw):
    return dict({'status': status, 'kind': kind, 'sport': 'nba', 'start': 1000, 'game': {'gk': gk, 'away': 'SAS', 'home': 'PHX'},
                 'settledAt': 5, 'units': 0}, **kw)


class Reopen(unittest.TestCase):
    def test_void_game_row_with_final_reopens(self):
        L = {'plays': {'a': row('void'), 'b': row('void', kind='exch')}}
        self.assertEqual(R.reopen(L, {'nba:1': {'home': 96, 'away': 122}}, 2000), 2)
        a = L['plays']['a']
        self.assertEqual(a['status'], 'open')
        self.assertEqual(a['regraded'], {'from': 'void', 'at': 2000})
        self.assertNotIn('settledAt', a)
        self.assertNotIn('units', a)

    def test_left_alone(self):
        L = {'plays': {'nofinal': row('void', gk='nba:2'), 'prop': row('void', kind='prop'), 'won': row('won'),
                       'again': row('void', regraded={'from': 'void', 'at': 1})}}
        self.assertEqual(R.reopen(L, {'nba:1': {'home': 1, 'away': 2}}, 2000), 0)
        self.assertEqual(L['plays']['nofinal']['status'], 'void')


class NbaCodes(unittest.TestCase):
    def test_espn_short_codes_match_the_feed(self):
        for espn, feed in (('SA', 'SAS'), ('GS', 'GSW'), ('NY', 'NYK'), ('NO', 'NOP'), ('UTAH', 'UTA'), ('WSH', 'WAS')):
            self.assertEqual(B.n(espn, 'nba'), B.n(feed, 'nba'))

    def test_codes_are_per_sport(self):
        self.assertEqual(B.n('NO', 'nfl'), 'NO')      # the Saints keep ESPN's code
        self.assertEqual(B.n('CHA', 'nba'), 'CHA')    # the Hornets are not Charlotte's college team

    def test_open_and_void_plays_need_a_final(self):
        import json, tempfile
        L = {'plays': {'a': row('open'), 'b': row('void', gk='nba:3'), 'c': row('won', gk='nba:4'), 'd': row('open', gk='nba:5', start=2500)}}
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(L, f)
        need = B.open_plays([f.name, '/nonexistent.json'], {}, 2000 + 3 * 3600)
        os.unlink(f.name)
        self.assertEqual(sorted(need), ['nba:1', 'nba:3'])
        self.assertEqual(need['nba:1'], ('nba', 'SAS@PHX', 1000))


if __name__ == '__main__':
    unittest.main()


class CbbFallback(unittest.TestCase):
    """CBB plays sat open because the ESPN fallback had no college basketball board, and ESPN lists some games with home and away reversed."""
    def test_cbb_has_a_board_and_ncsu_alias(self):
        self.assertIn('cbb', B.SCORE)
        self.assertEqual(B.n('NCSU', 'cbb'), 'NCST')

    def test_reversed_sides_store_the_score_on_the_feed_sides(self):
        import datetime as dt, json, tempfile
        start = 1795147200
        ev = [{'date': '2026-11-20T04:00Z', 'competitions': [{'status': {'type': {'completed': True}}, 'competitors': [
            {'homeAway': 'home', 'score': '83', 'team': {'abbreviation': 'KU'}},
            {'homeAway': 'away', 'score': '92', 'team': {'abbreviation': 'HOU'}}]}]}]
        with tempfile.TemporaryDirectory() as d:
            res, plays = os.path.join(d, 'res.json'), os.path.join(d, 'p.json')
            json.dump({}, open(res, 'w'))
            json.dump({'plays': {'a': {'status': 'open', 'kind': 'book', 'sport': 'cbb', 'start': start,
                                       'game': {'gk': 'cbb:1', 'away': 'KU', 'home': 'HOU'}}}}, open(plays, 'w'))
            old = (B.RES, B.board)
            B.RES, B.board = res, lambda sport, day: ev
            try:
                B.main(['--plays', plays])
            finally:
                B.RES, B.board = old
            r = json.load(open(res))['cbb:1']
        self.assertEqual((r['home'], r['away']), (92, 83))   # feed home is HOU, who scored 92
