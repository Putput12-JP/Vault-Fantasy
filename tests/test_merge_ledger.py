"""Ledger merge contracts (scripts/paper_bot/merge_ledger.py). No network.

Run from the repo root: python3 -m unittest tests.test_merge_ledger
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.paper_bot import cfb_jp_novig as S
from scripts.paper_bot import merge_ledger as M
from scripts.paper_bot.ledger import empty, recompute_cash

KICK = 1_792_000_000


def trade(tid, status='open', ts='2026-10-20T12:00:00Z', source='nba_total', stake=10.0, **kw):
    t = {'id': tid, 'ticker': tid.split(':')[0], 'ts': ts, 'status': status, 'source': source, 'stake': stake,
         'contracts': 10, 'price': 0.5, 'side': 'yes'}
    if status == 'settled':
        t.update({'payout': 20.0, 'pnl': 10.0, 'won': True, 'settled_ts': '2026-10-21T01:00:00Z'})
    t.update(kw)
    return t


def jp_trade(tid, **kw):
    return trade(tid, source=S.STRATEGY, book='novig', **kw)


def snap(ts, bid=0.4, ask=0.42):
    return S.snap_str(ts, bid, ask, 100, 100)


def game(key, state='watching', novig_snaps=(), kalshi_snaps=(), trade_id=None, **kw):
    g = {'key': key, 'game': 'A @ B', 'home': 'B', 'away': 'A', 'week': 8, 'kick': KICK, 'side': 'home', 'team': 'B',
         'edge': 5.0, 'edge_bucket': '5+', 'counts_toward_pass': True, 'open_hcap': 6.0, 'state': state,
         'trade_id': trade_id, 'created': '2026-10-20T12:00:00Z',
         'novig': {'hcap': 6.5, 'listed_ts': 100, 'first_seen_ts': 200, 'snaps': list(novig_snaps)},
         'kalshi': {'ticker': None, 'side': None, 'listed_ts': None, 'first_seen_ts': None, 'snaps': list(kalshi_snaps)}}
    g.update(kw)
    return g


def ledger(trades=(), games=None, updated='2026-10-20T12:00:00Z', **kw):
    led = empty(1000)
    led['trades'] = list(trades)
    led['updated'] = updated
    if games is not None:
        led['strategies'] = {S.STRATEGY: {'games': games, 'progress': {}, 'watch': [], 'updated': updated}}
    led.update(kw)
    return led


def ids(led):
    return [t['id'] for t in led['trades']]


def by_id(led):
    return {t['id']: t for t in led['trades']}


class TradeMergeTests(unittest.TestCase):
    def test_rows_only_on_one_side_are_kept(self):
        local = ledger([trade('A:1'), trade('L:1', ts='2026-10-20T13:00:00Z')])
        remote = ledger([trade('A:1'), trade('R:1', ts='2026-10-20T14:00:00Z')])
        out = M.merge_ledgers(local, remote)
        self.assertEqual(ids(out), ['A:1', 'L:1', 'R:1'])

    def test_no_row_is_dropped_whatever_the_state(self):
        rows = [trade('a:1', 'open'), trade('b:1', 'vetoed'), trade('c:1', 'error'), trade('d:1', 'void'), trade('e:1', 'settled')]
        out = M.merge_ledgers(ledger(rows[:3]), ledger(rows[2:]))
        self.assertEqual(sorted(ids(out)), sorted(t['id'] for t in rows))

    def test_settled_beats_open_in_both_directions(self):
        op, st = trade('A:1', 'open'), trade('A:1', 'settled')
        for local, remote in ((op, st), (st, op)):
            out = M.merge_ledgers(ledger([local]), ledger([remote]))
            self.assertEqual(len(out['trades']), 1)
            self.assertEqual(out['trades'][0]['status'], 'settled')

    def test_settled_wins_even_with_an_older_updated_stamp_and_lower_snapshot_count(self):
        out = M.merge_ledgers(ledger([trade('A:1', 'settled')], updated='2026-10-01T00:00:00Z'),
                              ledger([trade('A:1', 'open', mark_ts='2026-10-25T00:00:00Z')], updated='2026-10-25T00:00:00Z'))
        self.assertEqual(out['trades'][0]['status'], 'settled')

    def test_decided_remainder_beats_pending_remainder(self):
        pend = jp_trade('K:1', status='settled', remainder_pending=True, won=None, pnl=3.0, hold_status='pending')
        done = jp_trade('K:1', status='settled', remainder_pending=False, won=False, pnl=-4.0, hold_status='graded',
                        graded_ts='2026-10-22T00:00:00Z')
        for a, b in ((pend, done), (done, pend)):
            out = M.merge_ledgers(ledger([a]), ledger([b]))
            self.assertEqual(out['trades'][0]['hold_status'], 'graded')
            self.assertFalse(out['trades'][0]['remainder_pending'])

    def test_pending_remainder_beats_open(self):
        pend = jp_trade('K:1', status='settled', remainder_pending=True, won=None)
        op = jp_trade('K:1', status='open')
        out = M.merge_ledgers(ledger([op]), ledger([pend]))
        self.assertEqual(out['trades'][0]['status'], 'settled')

    def test_later_update_wins_when_state_ties(self):
        a = trade('A:1', 'open', mark_ts='2026-10-20T15:00:00Z', mark_value=11.0)
        b = trade('A:1', 'open', mark_ts='2026-10-20T16:00:00Z', mark_value=12.0)
        self.assertEqual(M.merge_ledgers(ledger([a]), ledger([b]))['trades'][0]['mark_value'], 12.0)
        self.assertEqual(M.merge_ledgers(ledger([b]), ledger([a]))['trades'][0]['mark_value'], 12.0)

    def test_full_tie_prefers_local(self):
        a = trade('A:1', 'open', note='local')
        b = trade('A:1', 'open', note='remote')
        self.assertEqual(M.merge_ledgers(ledger([a]), ledger([b]))['trades'][0]['note'], 'local')

    def test_rows_without_an_id_are_not_collapsed_into_each_other(self):
        a = {'ticker': 'X', 'ts': '2026-10-20T12:00:00Z', 'status': 'vetoed', 'source': 's', 'side': 'yes'}
        b = {'ticker': 'Y', 'ts': '2026-10-20T12:00:00Z', 'status': 'vetoed', 'source': 's', 'side': 'yes'}
        out = M.merge_ledgers(ledger([a]), ledger([copy.deepcopy(a), b]))
        self.assertEqual(sorted(t['ticker'] for t in out['trades']), ['X', 'Y'])

    def test_output_order_is_deterministic(self):
        a = ledger([trade('A:1', ts='2026-10-20T12:00:00Z'), trade('B:1', ts='2026-10-20T13:00:00Z')])
        b = ledger([trade('C:1', ts='2026-10-20T12:30:00Z')])
        self.assertEqual(ids(M.merge_ledgers(a, b)), ids(M.merge_ledgers(b, a)))
        self.assertEqual(ids(M.merge_ledgers(a, b)), ['A:1', 'C:1', 'B:1'])

    def test_inputs_are_not_modified(self):
        a = ledger([trade('A:1')], {'g': game('g', novig_snaps=[snap(1)])})
        b = ledger([trade('A:1', 'settled')], {'g': game('g', novig_snaps=[snap(2)])})
        a0, b0 = copy.deepcopy(a), copy.deepcopy(b)
        M.merge_ledgers(a, b)
        self.assertEqual(a, a0)
        self.assertEqual(b, b0)

    def test_idempotent(self):
        a = ledger([trade('A:1'), jp_trade('K:1', status='settled', remainder_pending=True, won=None)],
                   {'g': game('g', novig_snaps=[snap(1), snap(2)])})
        b = ledger([trade('A:1', 'settled'), trade('B:1')], {'g': game('g', novig_snaps=[snap(2), snap(3)])})
        once = M.merge_ledgers(a, b)
        twice = M.merge_ledgers(once, b)
        self.assertEqual(once['trades'], twice['trades'])
        self.assertEqual(once['strategies'], twice['strategies'])
        self.assertEqual(once['summary'], twice['summary'])


class SideTests(unittest.TestCase):
    def test_missing_remote_passes_local_through(self):
        local = ledger([trade('A:1')])
        out = M.merge_ledgers(local, None)
        self.assertEqual(ids(out), ['A:1'])

    def test_missing_local_passes_remote_through(self):
        self.assertEqual(ids(M.merge_ledgers(None, ledger([trade('R:1')]))), ['R:1'])

    def test_both_missing_is_an_error(self):
        with self.assertRaises(M.NotALedger):
            M.merge_ledgers(None, None)

    def test_paper_only_is_locked_on(self):
        a, b = ledger([trade('A:1')]), ledger([trade('B:1')])
        a['live_orders'] = True
        b['paper_only'] = False
        out = M.merge_ledgers(a, b)
        self.assertIs(out['paper_only'], True)
        self.assertIs(out['live_orders'], False)

    def test_updated_is_the_later_stamp_and_config_comes_from_local(self):
        a = ledger([], updated='2026-10-20T12:00:00Z', bankroll_start=1000.0)
        b = ledger([], updated='2026-10-21T12:00:00Z', bankroll_start=1000.0, config={'x': 1})
        out = M.merge_ledgers(a, b)
        self.assertEqual(out['updated'], '2026-10-21T12:00:00Z')
        self.assertEqual(out['config'], {})


class GameMergeTests(unittest.TestCase):
    def merged_game(self, lg, rg, key='g'):
        out = M.merge_ledgers(ledger([], {key: lg}), ledger([], {key: rg}))
        return out['strategies'][S.STRATEGY]['games'][key]

    def test_games_on_one_side_only_are_kept(self):
        out = M.merge_ledgers(ledger([], {'a': game('a')}), ledger([], {'b': game('b')}))
        self.assertEqual(sorted(out['strategies'][S.STRATEGY]['games']), ['a', 'b'])

    def test_snapshots_union_and_dedupe_by_ts_and_sort(self):
        g = self.merged_game(game('g', novig_snaps=[snap(10), snap(30)]), game('g', novig_snaps=[snap(20), snap(30, bid=0.1)]))
        self.assertEqual([S.parse_snap(s)['ts'] for s in g['novig']['snaps']], [10, 20, 30])

    def test_duplicate_ts_keeps_the_winners_copy(self):
        lg = game('g', novig_snaps=[snap(10), snap(30, bid=0.45)])
        rg = game('g', novig_snaps=[snap(30, bid=0.11)])
        g = self.merged_game(lg, rg)
        self.assertEqual(S.parse_snap(g['novig']['snaps'][-1])['bid'], 0.45)

    def test_kalshi_snaps_union_too(self):
        g = self.merged_game(game('g', kalshi_snaps=[snap(1)]), game('g', kalshi_snaps=[snap(2)]))
        self.assertEqual(len(g['kalshi']['snaps']), 2)

    def test_malformed_snapshot_is_kept_not_destroyed_and_not_duplicated(self):
        lg = game('g', novig_snaps=[snap(10), 'bad,snap'])
        rg = game('g', novig_snaps=[snap(20), 'bad,snap'])
        g = self.merged_game(lg, rg)
        self.assertEqual(g['novig']['snaps'].count('bad,snap'), 1)
        self.assertEqual(len(g['novig']['snaps']), 3)

    def test_more_advanced_state_wins_and_carries_its_trade(self):
        t = jp_trade('K:1')
        lg = game('g', 'watching', novig_snaps=[snap(1), snap(2), snap(3)])
        rg = game('g', 'entered', novig_snaps=[snap(1)], trade_id='K:1', entry_ts=1)
        for a, b in ((lg, rg), (rg, lg)):
            g = self.merged_game(a, b)
            self.assertEqual((g['state'], g['trade_id']), ('entered', 'K:1'))
            self.assertEqual(len(g['novig']['snaps']), 3)     # the snapshots of the losing side are not lost

    def test_graded_game_is_not_refilled_with_pruned_snapshots(self):
        done = game('g', 'graded', novig_snaps=[snap(1), snap(KICK - 100)], trade_id='K:1')
        stale = game('g', 'exited', novig_snaps=[snap(1), snap(5), snap(6), snap(KICK - 100)], trade_id='K:1')
        for a, b in ((done, stale), (stale, done)):
            g = self.merged_game(a, b)
            self.assertEqual(g['state'], 'graded')
            self.assertEqual(len(g['novig']['snaps']), 2)

    def test_more_snapshots_wins_when_state_ties(self):
        lg = game('g', 'watching', novig_snaps=[snap(1)], edge=5.0)
        rg = game('g', 'watching', novig_snaps=[snap(1), snap(2)], edge=6.0)
        self.assertEqual(self.merged_game(lg, rg)['edge'], 6.0)
        self.assertEqual(self.merged_game(rg, lg)['edge'], 6.0)

    def test_earliest_first_seen_survives(self):
        lg = game('g'); lg['novig']['first_seen_ts'] = 500
        rg = game('g'); rg['novig']['first_seen_ts'] = 300
        self.assertEqual(self.merged_game(lg, rg)['novig']['first_seen_ts'], 300)

    def test_watch_is_rebuilt_from_merged_games_and_progress_from_merged_trades(self):
        lg = game('a', novig_snaps=[snap(1)])
        rg = game('b', novig_snaps=[snap(2)])
        out = M.merge_ledgers(ledger([], {'a': lg}), ledger([], {'b': rg}))
        st = out['strategies'][S.STRATEGY]
        self.assertEqual([w['key'] for w in st['watch']], ['a', 'b'])
        self.assertEqual(st['watch'][0]['novig_snaps'], 1)
        self.assertIn('pass_bar', st['progress'])

    def test_other_strategies_are_unioned_by_name(self):
        a = ledger([]); a['strategies'] = {'x': {'updated': '1', 'v': 'old'}}
        b = ledger([]); b['strategies'] = {'x': {'updated': '2', 'v': 'new'}, 'y': {'v': 1}}
        out = M.merge_ledgers(a, b)
        self.assertEqual(out['strategies']['x']['v'], 'new')
        self.assertIn('y', out['strategies'])

    def test_ledger_without_strategies_stays_without(self):
        self.assertNotIn('strategies', M.merge_ledgers(ledger([trade('A:1')]), ledger([trade('B:1')])))


class FlagTests(unittest.TestCase):
    def test_config_kill_switch_comes_from_local_so_clearing_it_takes_effect(self):
        for lu, ru in (('2026-10-22T00:00:00Z', '2026-10-21T00:00:00Z'), ('2026-10-21T00:00:00Z', '2026-10-22T00:00:00Z')):
            out = M.merge_ledgers(ledger([], config={'kill_switch': False}, updated=lu),
                                  ledger([], config={'kill_switch': True}, updated=ru))
            self.assertFalse(out['config']['kill_switch'])

    def test_config_kill_switch_set_locally_is_kept(self):
        out = M.merge_ledgers(ledger([], config={'kill_switch': True}), ledger([], config={'kill_switch': False}))
        self.assertTrue(out['config']['kill_switch'])

    def test_whole_config_comes_from_local_even_when_remote_is_newer(self):
        out = M.merge_ledgers(ledger([], config={'x': 1}, updated='2026-10-20T00:00:00Z'),
                              ledger([], config={'x': 2, 'y': 3}, updated='2026-10-25T00:00:00Z'))
        self.assertEqual(out['config'], {'x': 1})

    def test_unset_flags_stay_unset(self):
        out = M.merge_ledgers(ledger([], config={'kill_switch': False}), ledger([], config={'kill_switch': False}))
        self.assertFalse(out['config']['kill_switch'])

    def test_runtime_halt_state_stays_sticky_when_only_remote_set_it_even_with_config_cleared(self):
        a = ledger([], config={'kill_switch': False}, updated='2026-10-22T00:00:00Z')
        b = ledger([], config={'kill_switch': True}, updated='2026-10-21T00:00:00Z', halt='daily loss stop 2026-10-20')
        out = M.merge_ledgers(a, b)
        self.assertEqual(out['halt'], 'daily loss stop 2026-10-20')
        self.assertFalse(out['config']['kill_switch'])

    def test_top_level_and_strategy_halt_flags_survive_from_the_older_side(self):
        a = ledger([], {'g': game('g')}, updated='2026-10-22T00:00:00Z')
        b = ledger([], {'g': game('g')}, updated='2026-10-21T00:00:00Z', halt='daily loss stop')
        b['strategies'][S.STRATEGY]['halted'] = True
        out = M.merge_ledgers(a, b)
        self.assertEqual(out['halt'], 'daily loss stop')
        self.assertTrue(out['strategies'][S.STRATEGY]['halted'])

    def test_runs_and_equity_union_by_ts_and_cap(self):
        a = ledger([], runs=[{'ts': '2026-10-20T12:00:00Z', 'halt': 'kill switch is on'}], equity=[{'ts': '1', 'equity': 1}])
        b = ledger([], runs=[{'ts': '2026-10-20T12:00:00Z', 'halt': 'kill switch is on'}, {'ts': '2026-10-20T13:00:00Z', 'halt': None}],
                   equity=[{'ts': '2', 'equity': 2}])
        out = M.merge_ledgers(a, b)
        self.assertEqual([r['ts'] for r in out['runs']], ['2026-10-20T12:00:00Z', '2026-10-20T13:00:00Z'])
        self.assertEqual(out['runs'][0]['halt'], 'kill switch is on')
        self.assertEqual([e['ts'] for e in out['equity']], ['1', '2'])
        many = ledger([], runs=[{'ts': f'2026-01-01T00:{i // 60:02d}:{i % 60:02d}Z'} for i in range(150)])
        many2 = ledger([], runs=[{'ts': f'2026-02-01T00:{i // 60:02d}:{i % 60:02d}Z'} for i in range(150)])
        out = M.merge_ledgers(many, many2)
        self.assertEqual(len(out['runs']), M.RUN_CAP)
        self.assertTrue(out['runs'][-1]['ts'].startswith('2026-02-01'))


class RecomputeTests(unittest.TestCase):
    def test_cash_and_summary_come_from_the_merged_trades(self):
        a = ledger([trade('A:1', 'settled')])
        b = ledger([trade('B:1', 'open')])
        a['cash'], b['cash'] = 9999.0, 1.0       # stale cash on either side is ignored
        out = M.merge_ledgers(a, b)
        self.assertEqual(out['cash'], recompute_cash(copy.deepcopy(out)))
        self.assertEqual(out['cash'], 1000 - 10 + 20 - 10)
        self.assertEqual(out['summary']['overall']['settled'], 1)
        self.assertEqual(out['summary']['overall']['open'], 1)
        self.assertEqual(out['summary']['by_source']['nba_total']['settled'], 1)

    def test_pending_partial_exit_is_pending_in_the_merged_summary(self):
        a = ledger([jp_trade('K:1', status='settled', remainder_pending=True, won=None, pnl=3.0)])
        out = M.merge_ledgers(a, ledger([jp_trade('K:1', status='open')]))
        grp = out['summary']['by_source'][S.STRATEGY]
        self.assertEqual((grp['pending'], grp['losses'], grp['settled']), (1, 0, 0))

    def test_novig_book_rows_stay_out_of_cash(self):
        out = M.merge_ledgers(ledger([jp_trade('K:1', status='open', stake=40.0)]), ledger([]))
        self.assertEqual(out['cash'], 1000.0)


class CliTests(unittest.TestCase):
    def write(self, d, name, data):
        p = os.path.join(d, name)
        with open(p, 'w') as f:
            if isinstance(data, str):
                f.write(data)
            else:
                json.dump(data, f)
        return p

    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'scripts.paper_bot.merge_ledger', *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_cli_merges_and_writes(self):
        with tempfile.TemporaryDirectory() as d:
            lp = self.write(d, 'l.json', ledger([trade('L:1')]))
            rp = self.write(d, 'r.json', ledger([trade('R:1')]))
            op = os.path.join(d, 'sub', 'o.json')
            r = self.run_cli(lp, rp, op)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(op) as f:
                self.assertEqual(sorted(ids(json.load(f))), ['L:1', 'R:1'])
            self.assertIn('merged 2', r.stdout)

    def test_output_may_overwrite_local(self):
        with tempfile.TemporaryDirectory() as d:
            lp = self.write(d, 'l.json', ledger([trade('L:1')]))
            rp = self.write(d, 'r.json', ledger([trade('R:1')]))
            self.assertEqual(self.run_cli(lp, rp, lp).returncode, 0)
            with open(lp) as f:
                self.assertEqual(sorted(ids(json.load(f))), ['L:1', 'R:1'])

    def test_missing_or_empty_remote_is_fine(self):
        with tempfile.TemporaryDirectory() as d:
            lp = self.write(d, 'l.json', ledger([trade('L:1')]))
            empty_p = self.write(d, 'e.json', '')
            for rp in (os.path.join(d, 'nope.json'), empty_p):
                op = os.path.join(d, 'o.json')
                self.assertEqual(self.run_cli(lp, rp, op).returncode, 0)
                with open(op) as f:
                    self.assertEqual(ids(json.load(f)), ['L:1'])

    def test_corrupt_remote_fails_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            lp = self.write(d, 'l.json', ledger([trade('L:1')]))
            for bad in ('{not json', '[]', '{"trades": 5}'):
                rp = self.write(d, 'r.json', bad)
                op = os.path.join(d, 'o.json')
                r = self.run_cli(lp, rp, op)
                self.assertEqual(r.returncode, 2)
                self.assertFalse(os.path.exists(op))

    def test_no_input_ledger_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli(os.path.join(d, 'a'), os.path.join(d, 'b'), os.path.join(d, 'o'))
            self.assertEqual(r.returncode, 2)

    def test_wrong_arg_count_is_a_usage_error(self):
        self.assertEqual(self.run_cli('only-one').returncode, 2)


if __name__ == '__main__':
    unittest.main()
