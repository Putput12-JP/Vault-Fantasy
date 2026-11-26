"""nba/scripts/prop_rules.py: the Sharp Money V2 Plays rule groups (nba-sig5, nba-aplus) written onto the NBA board.
    python3 -m unittest tests.test_nba_prop_rules"""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nba', 'scripts'))
import prop_rules as R          # noqa: E402
import build_prop_signals as S  # noqa: E402

TIP = 1795600000
DAY = R.night(TIP)


def g(day, mins, fga, pts=20, reb=8, ast=6, tpa=5):
    r = [0] * 21
    r[0], r[1], r[2], r[5], r[6], r[7], r[8], r[14], r[17] = day, '2026', 0, mins, pts, reb, ast, fga, tpa
    return r


class FakeLogs:
    """20 earlier games: shot volume up 20% in the last 5, 30 minutes, PRA 34 every night."""
    def __init__(self, rank=25):
        self.grp, self._rank = {1: 'F'}, rank
        self.games = [g(DAY - 1 - i, 30, 12 if i < 5 else 10) for i in range(20)]

    def before(self, pid, day):
        return [x for x in self.games if x[0] < day] if pid == 1 else []

    def rank(self, team, grp, stat, day):
        return self._rank


def lean(stat='pra', line=30.5, p=0.62, p_mkt=0.56, mins=33.0):
    k = f'g1|1|{stat}'
    return {k: [line, 31, 5, p, 'O' if p > .5 else 'U', None, p_mkt, mins, 1, '-110', 'DraftKings', 'books']}, \
           {k: {'game': 'g1', 'tip': TIP, 'matchup': 'DET @ BOS', 'pid': 1, 'player': 'X', 'team': 'BOS', 'stat': stat, 'kind': 'lean'}}


class PropRules(unittest.TestCase):
    def test_five_of_five_on_the_model_side(self):
        rows, meta = lean()
        out = R.evaluate(rows, meta, {}, {}, FakeLogs())
        self.assertEqual(out['g1|1|pra'][:4], [30.5, 'O', 5, 0])

    def test_four_of_five_is_left_off_unless_a_plus(self):
        rows, meta = lean(p_mkt=0.5)                      # the market is within 2 points of even: no market call
        out = R.evaluate(rows, meta, {}, {}, FakeLogs(rank=15))   # and an unranked-middle matchup: 3 agree, A+ not reached
        self.assertEqual(out, {})

    def test_a_plus_only_on_the_combo_stats(self):
        # rank 28 (+2), level 4 projection (+3), minutes +3 (+1), a 30-minute teammate out (+2) = 8: A+ over
        for stat, want in (('pra', True), ('ra', True), ('pa', True), ('pts', False)):
            rows, meta = lean(stat=stat, p=0.70, p_mkt=0.5)
            out = R.evaluate(rows, meta, {2: 'Out'}, {'BOS': [(1, 33), (2, 30)]}, FakeLogs(rank=28))
            k = f'g1|1|{stat}'
            self.assertEqual(k in out and out[k][4] == 'A+', want, stat)

    def test_rebounds_a_grades_on_the_model_side(self):
        # rank 28 (+2), level 3 projection (+2), minutes +3 (+1) = 5: A- over, model over
        rows, meta = lean(stat='reb', line=7.5, p=0.62, p_mkt=0.5)
        out = R.evaluate(rows, meta, {}, {}, FakeLogs(rank=28))
        self.assertEqual(out['g1|1|reb'][4:], ['A-', 'O', 0.12])     # model edge: .62 model vs .50 market
        rows, meta = lean(stat='reb', line=7.5, p=0.62, p_mkt=0.5)
        self.assertEqual(R.evaluate(rows, meta, {}, {}, FakeLogs(rank=15)), {}, 'B (3 points) is left off')

    def test_no_market_chance_no_row(self):
        rows, meta = lean(p_mkt=None)
        self.assertEqual(R.evaluate(rows, meta, {}, {}, FakeLogs()), {})


if __name__ == '__main__':
    unittest.main()
