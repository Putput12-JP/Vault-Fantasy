"""CFB scoreboard: JP+ numbers are recorded before kickoff and never changed after; the lean record counts the side of the open."""
import os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cfb_scoreboard as sb

K = '2026-10-17T16:00:00Z'; KE = sb.iso_epoch(K)


def g(spread, **kw):
    d = dict(game_id=1, week=7, home_team='A', away_team='B', kickoff_at=K, jp_spread=spread, jp_total=50.0); d.update(kw); return d


class Store(unittest.TestCase):
    def test_pregame_number_is_verified_and_follows_the_site_until_kickoff(self):
        s = {}; sb.update_store(s, [g(-7.0)], KE - 7200)
        self.assertTrue(s['1']['verified']); self.assertEqual(s['1']['jp_spread'], -7.0)
        sb.update_store(s, [g(-8.5)], KE - 600); self.assertEqual(s['1']['jp_spread'], -8.5)

    def test_nothing_changes_after_kickoff(self):
        s = {}; sb.update_store(s, [g(-7.0)], KE - 600)
        sb.update_store(s, [g(-3.0, actual_margin=10)], KE + 7200)
        self.assertEqual(s['1']['jp_spread'], -7.0); self.assertTrue(s['1']['verified']); self.assertEqual(s['1']['final'], 10)

    def test_first_seen_after_kickoff_is_unverified(self):
        s = {}; sb.update_store(s, [g(-7.0)], KE + 60)
        self.assertFalse(s['1']['verified'])

    def test_a_row_without_a_spread_is_skipped(self):
        s = {}; sb.update_store(s, [g(None)], KE - 60); self.assertEqual(s, {})


class Records(unittest.TestCase):
    rows = [dict(open=-7.0, actual=-14, m=-12.0), dict(open=3.0, actual=0, m=7.0), dict(open=0.0, actual=3, m=-1.0), dict(open=-3.0, actual=-3, m=-9.0)]

    def test_lean_counts_the_side_of_the_open_and_drops_pushes(self):
        r = sb.record(self.rows, 'm', 0.01)
        self.assertEqual((r['w'], r['l']), (1, 2))                     # game 1: m is 5 under the open and the home side covered by 7 (win); 2: m 4 over, home did not cover (loss); 3: m 1 under, home won (loss); 4: push

    def test_threshold_filters_small_edges(self):
        self.assertEqual(sb.record(self.rows, 'm', 5.0)['n'], 0 + sum(1 for r in self.rows if abs(r['m'] - r['open']) >= 5 and r['actual'] != r['open']))

    def test_summary_has_every_method(self):
        s = sb.summarize([dict(open=-7.0, actual=-14, ours=-12.0, v1=-6.0, jp=-8.0)])
        self.assertEqual(set(s['methods']), {'ours', 'v1', 'jp', 'open', 'close'}); self.assertEqual(s['methods']['open']['miss'], 7.0)
        self.assertEqual(s['methods']['close']['n'], 0)             # a game with no close is not counted, and the benchmark never gets a lean record
        self.assertIsNone(s['methods']['close']['lean'])


class Weeks(unittest.TestCase):
    def test_by_week_splits_games_and_lists_newest_first(self):
        rows = [dict(week=6, open=-7.0, actual=-14, ours=-12.0, v1=-6.0, jp=-8.0), dict(week=7, open=3.0, actual=0, ours=7.0, v1=1.0, jp=2.0), dict(week=7, open=0.0, actual=3, ours=-1.0, v1=1.0, jp=2.0)]
        w = sb.by_week(rows)
        self.assertEqual([x['week'] for x in w], [7, 6]); self.assertEqual([x['games'] for x in w], [2, 1])

    def test_official_picks_counts_graded_results_only(self):
        o = sb.official_picks([dict(week=7, result='W'), dict(week=7, result='L'), dict(week=7, result='P'), dict(week=7, result=None), dict(week=6, result='W')])
        self.assertEqual(o['total'], dict(w=2, l=1, p=1, pct=round(2 / 3, 4))); self.assertEqual([x['week'] for x in o['weeks']], [7, 6])


if __name__ == '__main__':
    unittest.main()
