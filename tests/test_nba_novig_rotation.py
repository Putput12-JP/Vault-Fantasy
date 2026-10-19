"""nba/scripts/novig.py game-complete rotation. No network: Novig is a fake.

Run from the repo root: python3 -m pytest tests/test_nba_novig_rotation.py   (or python3 tests/test_nba_novig_rotation.py)
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'nba', 'scripts'))
import novig  # noqa: E402

NOW = 1_792_400_000.0
TIP = NOW + 3600


def game(i, home, away):
    return {'id': i, 'away': away[:3].upper(), 'home': home[:3].upper(), 'away_name': away, 'home_name': home, 'tip': TIP + i * 60}


NAMES = {0: ('Boston Celtics', 'Detroit Pistons', 'BOS', 'DET'), 1: ('Philadelphia 76ers', 'New York Knicks', 'PHI', 'NYK'), 2: ('Oklahoma City Thunder', 'San Antonio Spurs', 'OKC', 'SAS')}
GAMES = [game(i, n[1], n[0]) for i, n in NAMES.items()]
# spreads listed widest first (the API's order); the true main is 1.5. Totals 210.5 .. 230.5, main 220.5
SPREADS = [6.5, 5.5, 4.5, 3.5, 2.5, 1.5]
TOTALS = [230.5, 228.5, 226.5, 224.5, 222.5, 220.5, 218.5, 216.5]
MID_SP = {6.5: .80, 5.5: .74, 4.5: .68, 3.5: .62, 2.5: .56, 1.5: .51}      # P(first outcome): the 1.5 strike sits nearest 50%
MID_TOT = {230.5: .20, 228.5: .27, 226.5: .34, 224.5: .40, 222.5: .45, 220.5: .50, 218.5: .60, 216.5: .70}


class Fake:
    """A Novig that serves 3 games, counts every call, and can fail a market's book."""

    def __init__(self):
        self.calls, self.fail, self.seq = [], set(), 1
        self.markets = {}                                  # event -> [market]
        self.books = {}
        for i, (away, home, a, h) in NAMES.items():
            ev = f'ev{i}'
            ms = [{'marketId': f'{ev}-ml', 'description': h, 'marketType': 'MONEY', 'status': 'OPEN', 'strike': None,
                   'outcomes': [{'outcomeId': f'{ev}-ml-a', 'name': h}, {'outcomeId': f'{ev}-ml-b', 'name': a}]}]
            self.books[f'{ev}-ml'] = (f'{ev}-ml-a', .60)
            for k in SPREADS:
                mid = f'{ev}-sp{k}'
                ms.append({'marketId': mid, 'description': f'{a} +{k}', 'marketType': 'SPREAD', 'status': 'OPEN', 'strike': str(k),
                           'outcomes': [{'outcomeId': mid + '-a', 'name': f'{a} +{k}'}, {'outcomeId': mid + '-b', 'name': f'{h} -{k}'}]})
                self.books[mid] = (mid + '-a', MID_SP[k])
            for k in TOTALS:
                mid = f'{ev}-t{k}'
                ms.append({'marketId': mid, 'description': f'Over {k}', 'marketType': 'TOTAL', 'status': 'OPEN', 'strike': str(k),
                           'outcomes': [{'outcomeId': mid + '-a', 'name': f'Over {k}'}, {'outcomeId': mid + '-b', 'name': f'Under {k}'}]})
                self.books[mid] = (mid + '-a', MID_TOT[k])
            self.markets[ev] = ms

    def __call__(self, path, tries=3):
        self.calls.append(path)
        if path.startswith('/catalog/events'):
            return {'items': [{'eventId': f'ev{i}', 'description': f'{n[0]} @ {n[1]}', 'startsTs': int((TIP + i * 60) * 1000)} for i, n in NAMES.items()]}
        if path.startswith('/catalog/markets?event='):
            return {'items': self.markets[path.split('event=')[1].split('&')[0]]}
        mid = path.split('/')[3]
        if path.endswith('/book'):
            if mid in self.fail:
                return None
            out_a, p = self.books[mid]
            out_b = out_a[:-1] + 'b'
            return {'marketId': mid, 'seq': self.seq, 'orders': {out_a: [{'price': str(round(p - .01, 3)), 'qty': 10000}], out_b: [{'price': str(round(1 - p - .01, 3)), 'qty': 10000}]}}
        if '/trades' in path:
            return {'items': []}
        raise AssertionError(path)

    def count(self, suffix):
        return sum(1 for c in self.calls if c.endswith(suffix) or suffix in c)


class Rotation(unittest.TestCase):
    def setUp(self):
        self.fake = Fake()
        self._get, self._budget, self._pace = novig.get, novig.BUDGET, novig.PACE_S
        novig.get = self.fake
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        novig.get, novig.BUDGET, novig.PACE_S = self._get, self._budget, self._pace

    def poll(self, now, budget):
        novig.BUDGET = budget
        self.fake.calls.clear()
        return novig.poll(GAMES, self.tmp, now)

    def test_full_budget_reads_every_game_with_the_true_main_line(self):
        out = self.poll(NOW, 1000)
        self.assertEqual(out['rotation']['read'], 3)
        for g in out['games'].values():
            self.assertTrue(g['fresh'])
            self.assertEqual(g['age'], 0)
            self.assertEqual(g['main_spread']['k'], 1.5)
            self.assertEqual(g['main_total']['k'], 220.5)
            self.assertEqual(len(g['spreads']), len(SPREADS))
            self.assertEqual(len(g['totals']), len(TOTALS))
            self.assertIsNotNone(g['ml'])

    def test_a_small_budget_reads_whole_games_and_carries_the_rest_with_their_age(self):
        per_game = 1 + len(SPREADS) + len(TOTALS)                    # books; the fake's first read also needs a trades call per book
        budget = per_game * 2 + 4                                    # one game's books + trades fit, a second one does not
        out = self.poll(NOW, budget)
        self.assertEqual(out['rotation']['read'], 1)
        self.assertEqual(out['rotation']['none'], 2)
        fresh = [g for g in out['games'].values() if g['fresh']]
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh[0]['main_spread']['k'], 1.5)
        for g in out['games'].values():
            if not g['fresh']:                                       # never published from a partial ladder
                self.assertIsNone(g['ml'])
                self.assertIsNone(g['main_spread'])
                self.assertIsNone(g['main_total'])
                self.assertEqual(g['spreads'], [])
        self.assertLessEqual(out['used'], budget)
        out2 = self.poll(NOW + 300, budget)                          # the next poll reads a different game (oldest read first), the first one is carried
        got = {gid: g for gid, g in out2['games'].items()}
        self.assertEqual(out2['rotation']['read'], 1)
        carried = [g for g in got.values() if not g['fresh'] and g['age'] is not None]
        self.assertEqual(len(carried), 1)
        self.assertGreaterEqual(carried[0]['age'], 300)
        self.assertEqual(carried[0]['main_spread']['k'], 1.5)       # the carried result is the complete one
        out3 = self.poll(NOW + 600, budget)
        self.assertEqual(out3['rotation']['none'], 0)               # three polls cover three games
        self.assertEqual(out3['rotation']['oldest_age'] >= 300, True)

    def test_a_failed_book_is_retried_then_the_game_keeps_its_previous_read(self):
        first = self.poll(NOW, 1000)
        self.assertEqual(first['rotation']['read'], 3)
        self.fake.fail.add('ev0-sp1.5')                              # the main strike's book will not come back
        out = self.poll(NOW + 300, 1000)
        g0 = out['games']['0']
        self.assertFalse(g0['fresh'])
        self.assertEqual(g0['short'], 1)
        self.assertGreaterEqual(g0['age'], 300)
        self.assertEqual(g0['main_spread']['k'], 1.5)                # not re-chosen from the 5 strikes that did come back
        self.assertEqual(self.fake.count('ev0-sp1.5/book'), 2)       # one retry

    def test_a_game_never_read_whole_publishes_no_line_even_if_most_strikes_came_back(self):
        self.fake.fail.add('ev1-sp1.5')                              # the true main strike: without it a partial ladder would call 2.5 the main
        out = self.poll(NOW, 1000)
        g1 = out['games']['1']
        self.assertIsNone(g1['main_spread'])
        self.assertIsNone(g1['ml'])
        self.assertEqual(g1['short'], 1)
        self.assertEqual(out['games']['0']['main_spread']['k'], 1.5)

    def test_carry_expires(self):
        self.poll(NOW, 1000)
        novig.CARRY_MAX_S = 600
        try:
            out = self.poll(NOW + 601, 20)                           # a budget too small for the rest: the oldest game is forced, the rest are older than the cap
        finally:
            novig.CARRY_MAX_S = 7200
        stale = [g for g in out['games'].values() if not g['fresh']]
        self.assertEqual(len(stale), 2)
        self.assertTrue(all(g['age'] is None and g['main_spread'] is None for g in stale))

    def test_quotes_keys_do_not_move_while_a_game_is_carried(self):
        out1 = self.poll(NOW, 1000)
        rows1, meta1 = novig.quotes(out1, GAMES)
        out2 = self.poll(NOW + 300, 20)                              # only the oldest game is read; the others are carried unchanged
        rows2, meta2 = novig.quotes(out2, GAMES)
        self.assertEqual(sorted(rows1), sorted(rows2))
        self.assertEqual(rows1, rows2)
        self.assertEqual(len(rows1), 9)                              # ml + main spread + main total, 3 games

    def test_trades_calls_are_unchanged_for_a_game_that_was_read(self):
        self.poll(NOW, 1000)
        n_book = self.fake.count('/book')
        n_tr = self.fake.count('/trades')
        self.assertEqual(n_book, 3 * 15)
        self.assertEqual(n_tr, 3 * 15)                               # first sight: every book is new, so every strike's trades are read
        self.poll(NOW + 300, 1000)
        self.assertEqual(self.fake.count('/trades'), 0)              # unchanged books (same seq) skip the trades call, as before

    def test_a_trades_call_skipped_for_budget_is_retried_not_lost(self):
        novig.BUDGET = 15 + 3                                        # one game's books and only a few trades calls
        self.fake.calls.clear()
        novig.poll(GAMES[:1], self.tmp, NOW)
        done = self.fake.count('/trades')
        self.assertLess(done, 15)
        self.fake.calls.clear()
        novig.BUDGET = 1000
        novig.poll(GAMES[:1], self.tmp, NOW + 300)
        self.assertEqual(self.fake.count('/trades'), 15 - done)      # exactly the ones that were skipped


if __name__ == '__main__':
    unittest.main()
