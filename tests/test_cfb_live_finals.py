"""ESPN scoreboard finals: a game the sportsdataverse release has not caught up on still grades, and the release's own grade replaces it later."""
import io, json, os, sys, unittest
from unittest import mock
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import cfb_model as cm


def row(gid, h, a, hs, as_, done, spread=float('nan')):
    return dict(season=2026, week=8, game_id=gid, homeTeamId=h, awayTeamId=a, homeFinalScore=hs, awayFinalScore=as_, homeTeamSpread=spread, status_type_completed=done, neutral_site=False)


FIN = {401871092: dict(week=8, home_id=276, away_id=6, hs=20, as_=13, neutral=False)}
PICK = dict(key='cfb:289598', side='home', entry=2.5, home_id=276, away_id=6)


def sb_event(done, hs=20, aw=13):
    return {'id': '401871092', 'week': {'number': 8}, 'competitions': [{'neutralSite': False, 'status': {'type': {'completed': done}},
            'competitors': [{'homeAway': 'home', 'score': str(hs), 'team': {'id': '276'}}, {'homeAway': 'away', 'score': str(aw), 'team': {'id': '6'}}]}]}


class Overlay(unittest.TestCase):
    def test_adds_a_game_the_release_lacks(self):
        g, n = cm.overlay_live_finals(pd.DataFrame([row(1, 10, 11, 30, 20, True)]), FIN)
        self.assertEqual(n, 1); x = g[g.game_id == 401871092].iloc[0]
        self.assertTrue(x.status_type_completed); self.assertTrue(x.live_final); self.assertTrue(pd.isna(x.homeTeamSpread))      # no close is invented
        self.assertFalse(g[g.game_id == 1].iloc[0].live_final)

    def test_release_row_that_is_already_final_is_untouched(self):
        g, n = cm.overlay_live_finals(pd.DataFrame([row(401871092, 276, 6, 20, 13, True, spread=-2.5)]), FIN)
        self.assertEqual(n, 0); self.assertEqual(len(g), 1); self.assertEqual(g.iloc[0].homeTeamSpread, -2.5); self.assertFalse(g.iloc[0].live_final)

    def test_in_progress_release_row_is_replaced_by_the_final(self):
        g, n = cm.overlay_live_finals(pd.DataFrame([row(401871092, 276, 6, 7, 3, False)]), FIN)
        self.assertEqual((n, len(g)), (1, 1)); self.assertEqual(int(g.iloc[0].homeFinalScore), 20)

    def test_nothing_to_add(self):
        g, n = cm.overlay_live_finals(pd.DataFrame([row(1, 10, 11, 30, 20, True)]), {}); self.assertEqual((n, len(g)), (0, 1))


class Grade(unittest.TestCase):
    def test_overlay_result_is_graded_and_tagged(self):
        g, _ = cm.overlay_live_finals(pd.DataFrame([row(1, 10, 11, 30, 20, True)]), FIN)
        r = cm.settle(PICK, g, {})
        self.assertEqual((r['result'], r['margin'], r['hs'], r['as_']), ('W', 7, 20, 13))      # Marshall +2.5, wins by 7
        self.assertEqual(r['settled_by'], cm.LIVE); self.assertIsNone(r['espn_close']); self.assertIsNone(r['clv'])

    def test_release_result_carries_the_close_and_no_tag(self):
        g, _ = cm.overlay_live_finals(pd.DataFrame([row(401871092, 276, 6, 20, 13, True, spread=-3.0)]), FIN)
        r = cm.settle(PICK, g, {})
        self.assertNotIn('settled_by', r); self.assertEqual(r['espn_close'], 3.0); self.assertEqual(r['clv'], -0.5)     # entry 2.5 vs a close of +3

    def test_a_push_stays_a_push(self):
        g, _ = cm.overlay_live_finals(pd.DataFrame([row(1, 10, 11, 30, 20, True)]), {5: dict(week=8, home_id=276, away_id=6, hs=15, as_=18, neutral=False)})
        self.assertEqual(cm.settle(dict(PICK, entry=3.0), g, {})['result'], 'P')


class Scoreboard(unittest.TestCase):
    def _run(self, payload):
        def fake(req, timeout=0):
            if isinstance(payload, Exception): raise payload
            return io.StringIO(json.dumps(payload))
        with mock.patch.object(cm.urllib.request, 'urlopen', fake), mock.patch.object(cm.time, 'sleep'):
            return cm.espn_finals(days=0, now=1792591597)

    def test_reads_finals_only(self):
        self.assertEqual(self._run({'events': [sb_event(True), dict(sb_event(False), id='9')]}), {401871092: dict(week=8, home_id=276, away_id=6, hs=20, as_=13, neutral=False)})

    def test_outage_is_not_fatal(self):
        self.assertEqual(self._run(OSError('down')), {})

    def test_malformed_event_is_skipped(self):
        self.assertEqual(self._run({'events': [{'id': '1'}, sb_event(True)]}).keys(), {401871092})


if __name__ == '__main__':
    unittest.main()
