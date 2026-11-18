"""Exchange price-gap grader (nba/scripts/exchange_book_gap.py): cohort rule, no-vig best book, first look, last look, clustering. No network.

Run from the repo root: python3 -m unittest discover -s tests -p 'test_exchange_book_gap.py'
"""
import json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'nba', 'scripts'))
import exchange_book_gap as G

TIP = 1_800_000_000      # an epoch; its ET day is DAY below
DAY = G.et_day(TIP)
PK = (DAY, 'jokic', 'pts')


def ev(*rows):
    """book events (t, book, side, line, odds), sorted."""
    return sorted(rows)


# two books, both sides at 24.5: -110/-110 = 50% over; -130/+110 = 56.5% over after vig removal
BOOKS = ev((100, 'FD', 'over', 24.5, -110), (100, 'FD', 'under', 24.5, -110),
           (100, 'MGM', 'over', 24.5, -110), (100, 'MGM', 'under', 24.5, -110))


class Rule(unittest.TestCase):
    def test_cohorts(self):
        self.assertEqual(G.cohort(0.04, 300), 'A')
        self.assertEqual(G.cohort(0.04, 50), 'B')
        self.assertIsNone(G.cohort(0.04, 150))              # between THIN and DEEP: no cohort
        self.assertEqual(G.cohort(0.005, 300), 'C')
        self.assertEqual(G.cohort(-0.005, 300), 'C')
        self.assertIsNone(G.cohort(0.02, 300))              # gap between FLAT and GAP: no cohort
        self.assertIsNone(G.cohort(0.0, 100))               # no gap and no size

    def test_no_vig_and_best_side(self):
        p = G.state_at(BOOKS, 200, 24.5)
        self.assertEqual(len(p), 2)
        self.assertAlmostEqual(p[0], 0.5)
        self.assertAlmostEqual(G.side_best([0.50, 0.60], 'over'), 0.60)
        self.assertAlmostEqual(G.side_best([0.50, 0.60], 'under'), 0.50)    # highest under chance = 1 - the lowest over chance

    def test_other_line_and_one_sided_books_do_not_count(self):
        b = ev((100, 'FD', 'over', 24.5, -110), (100, 'FD', 'under', 25.5, -110))
        self.assertEqual(G.state_at(b, 200, 24.5), [])


def run(books, reads, tip=TIP):
    info = {PK: (tip, 'g1')}
    return G.observe({PK: list(books)}, info, reads, __import__('collections').Counter())


class Observe(unittest.TestCase):
    def test_first_look_cohort_and_move(self):
        later = BOOKS + ev((500, 'FD', 'over', 24.5, +100), (500, 'FD', 'under', 24.5, -120),
                           (500, 'MGM', 'over', 24.5, +100), (500, 'MGM', 'under', 24.5, -120))
        # exchange over mid 0.55 (gap +0.05 vs books' 0.50), depth 300 over: cohort A, over side
        reads = [('novig', PK, 200, 24.5, 0.54, 0.56, 300, 40)]
        out = run(later, reads)
        a = [r for r in out if r['side'] == 'over']
        self.assertEqual(len(a), 1)
        self.assertEqual((a[0]['cohort'], a[0]['gap']), ('A', 0.05))
        # last look: over +100 / under -120 -> over no-vig = 0.5 / (0.5 + 0.5454) = 0.4783 -> the books moved AWAY from the over
        self.assertLess(a[0]['move'], 0)

    def test_books_moving_toward_the_exchange_is_positive(self):
        later = BOOKS + ev((500, 'FD', 'over', 24.5, -130), (500, 'FD', 'under', 24.5, +110),
                           (500, 'MGM', 'over', 24.5, -130), (500, 'MGM', 'under', 24.5, +110))
        out = run(later, [('kalshi', PK, 200, 24.5, 0.54, 0.56, 300, 40)])
        o = [r for r in out if r['side'] == 'over'][0]
        self.assertGreater(o['move'], 0)

    def test_one_row_per_exchange_prop_line_side(self):
        later = BOOKS + ev((500, 'FD', 'over', 24.5, -105), (500, 'FD', 'under', 24.5, -115))
        out = run(later, [('novig', PK, 200, 24.5, 0.54, 0.56, 300, 40), ('novig', PK, 210, 24.5, 0.55, 0.57, 400, 40)])
        self.assertEqual(len([r for r in out if r['side'] == 'over']), 1)

    def test_reads_after_tip_wide_quotes_and_single_book_are_left_out(self):
        self.assertEqual(run(BOOKS, [('novig', PK, TIP + 1, 24.5, 0.54, 0.56, 300, 40)]), [])
        self.assertEqual(run(BOOKS, [('novig', PK, 200, 24.5, 0.40, 0.60, 300, 40)]), [])          # 20c wide
        one = ev((100, 'FD', 'over', 24.5, -110), (100, 'FD', 'under', 24.5, -110))
        self.assertEqual(run(one, [('novig', PK, 200, 24.5, 0.54, 0.56, 300, 40)]), [])

    def test_no_later_book_look_is_left_out_not_zeroed(self):
        self.assertEqual(run(BOOKS, [('novig', PK, 200, 24.5, 0.54, 0.56, 300, 40)]), [])


class Stats(unittest.TestCase):
    def test_game_clustered_se_and_halves(self):
        rs = [dict(game=f'g{i // 2}', move=0.01, tip=i) for i in range(10)]
        st = G.stat(rs)
        self.assertEqual((st['n'], st['games']), (10, 5))
        self.assertEqual(len(G.halves(rs)), 2)

    def test_collecting_until_the_bar(self):
        by = {c: [dict(game='g', move=0.02, tip=1, t=1, stat='pts', side='over', exch='novig', cohort=c)] * 20 for c in 'ABC'}
        self.assertEqual(G.verdict(by, 40), 'collecting')

    def test_kill_when_mean_minus_two_se_below_zero_at_500(self):
        a = [dict(game=f'g{i % 40}', move=(-0.01 if i % 2 else 0.011), tip=i) for i in range(500)]
        self.assertEqual(G.verdict({'A': a, 'B': [], 'C': []}, 40), 'killed')


class Files(unittest.TestCase):
    def test_nothing_graded_without_kaldepth(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, 'snapshots', '2026-11-19'))
        r = G.build(d, {})
        self.assertIsNone(r['forward_from'])
        self.assertEqual(r['exchanges']['kalshi']['verdict'], 'collecting')


if __name__ == '__main__':
    unittest.main()
