"""scripts/clean_book_tape_outliers.py: another period's line (a 115.5 total on a 232 game) is dropped; real lines, other books and unknown references are left."""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import clean_book_tape_outliers as C


def row(book, tot=None, sp=None, ml=None, t=1):
    return {'t': t, 'src': 'sd', 'gk': 'nba:1', 'away': 'A', 'home': 'B', 'start': 9, 'book': book, 'ml': ml, 'sp': sp, 'tot': tot}


class Clean(unittest.TestCase):
    def run_rows(self, rows):
        with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
            for r in rows:
                f.write(json.dumps(r) + '\n')
        try:
            counts = C.clean(f.name, False)
            return counts, [json.loads(l) for l in open(f.name)]
        finally:
            os.unlink(f.name)

    def test_bad_total_dropped_good_kept(self):
        rows = [row('Consensus', tot=[232, -110, -110]), row('BetMGM', tot=[115.5, -120, -105], ml=[100, -120]),
                row('BetMGM', tot=[232.5, -110, -110]), row('DraftKings', tot=[231.5, -110, -110])]
        (nt, ns, gone), out = self.run_rows(rows)
        self.assertEqual((nt, ns, gone), (1, 0, 0))
        self.assertIsNone(out[1]['tot'])
        self.assertEqual(out[1]['ml'], [100, -120])           # the rest of the row stays
        self.assertEqual(out[2]['tot'][0], 232.5)
        self.assertEqual(out[3]['tot'][0], 231.5)

    def test_bad_spread_dropped(self):
        rows = [row('Consensus', sp=[-4.5, -110, -110]), row('BetRivers', sp=[-24.5, -110, -110], ml=[1, 2])]
        (nt, ns, gone), out = self.run_rows(rows)
        self.assertEqual((nt, ns), (0, 1))

    def test_no_consensus_yet_is_left_alone(self):
        (nt, ns, gone), out = self.run_rows([row('BetMGM', tot=[115.5, -120, -105])])
        self.assertEqual((nt, ns, gone), (0, 0, 0))
        self.assertEqual(out[0]['tot'][0], 115.5)

    def test_pinnacle_and_exchanges_untouched(self):
        rows = [row('Consensus', tot=[232, -110, -110]), row('Pinnacle', tot=[100, -110, -110])]
        (nt, ns, gone), out = self.run_rows(rows)
        self.assertEqual(nt, 0)

    def test_row_with_nothing_left_is_deleted(self):
        rows = [row('Consensus', tot=[232, -110, -110]), row('BetMGM', tot=[115.5, -120, -105])]
        (nt, ns, gone), out = self.run_rows(rows)
        self.assertEqual((nt, gone, len(out)), (1, 1, 1))


if __name__ == '__main__':
    unittest.main()
