"""Paper-bot contracts. No network. No invented backtest results.

Run from the repo root: python3 tests/test_paper_bot.py
"""
import copy
import importlib.util
import json
import math
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.paper_bot.config import load, source_cfg
from scripts.paper_bot.engine import Engine
from scripts.paper_bot.fees import cost_cents, taker_fee
from scripts.paper_bot.kelly import contracts_for, full_kelly
from scripts.paper_bot.ledger import empty, et_day, recompute_cash, summarize, tag_pre_fix_trades
from scripts.paper_bot.live import LIVE_ORDERS_IMPLEMENTED, KalshiSigner, LiveBroker, LiveTradingDisabled
from scripts.paper_bot.llm_filter import LlmFilter
from scripts.paper_bot.quotes import market_tradable, parse_market, settlement_of
from scripts.paper_bot.signals import load_sources
from scripts.paper_bot.signals.cfb_ml import proposals_from as cfb_proposals
from scripts.paper_bot.signals.cfb_ml import sigma_from_backtest, team_match
from scripts.paper_bot.signals.nba_total import _best_side, p_over, project_total, proposals_from, sigma_of, window_open

ET = ZoneInfo('America/New_York')
GATES = {
    'min_edge': 0.08, 'min_price': 0.05, 'max_price': 0.95, 'max_spread': 0.10,
}


def _fee_from_backtest():
    path = os.path.join(ROOT, 'nba', 'scripts', 'backtest_game_vs_kalshi.py')
    spec = importlib.util.spec_from_file_location('backtest_game_vs_kalshi', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.fee


class FeeTests(unittest.TestCase):
    def test_matches_the_nba_backtest_per_contract(self):
        fee = _fee_from_backtest()
        for cents in range(1, 100):
            p = cents / 100
            self.assertEqual(taker_fee(p), fee(p))

    def test_half_is_two_cents(self):
        self.assertEqual(taker_fee(0.50), 0.02)
        self.assertEqual(cost_cents(0.50), 52)


class KellyTests(unittest.TestCase):
    def test_quarter_kelly_then_the_two_percent_cap(self):
        # cost 0.52, f* = 0.08/0.48, quarter of that on $1000 is $41.67, capped at 2% = $20.
        # $20 buys 38 contracts at 52 cents. The engine turns that into a $19.76 stake.
        fee = 0.02
        n, reason = contracts_for(1000, 0.60, 0.50, fee, _caps(), {'day': 0, 'market': 0, 'event': 0})
        self.assertIsNone(reason)
        self.assertAlmostEqual(full_kelly(0.60, 0.52), 0.08 / 0.48)
        self.assertEqual(n, 38)
        self.assertEqual(round(n * cost_cents(0.50) / 100, 2), 19.76)

    def test_caps_and_ask_size(self):
        caps = _caps()
        self.assertEqual(contracts_for(1000, 0.60, 0.50, 0.02, caps, {'day': 100, 'market': 0, 'event': 0})[0], 0)
        self.assertEqual(contracts_for(1000, 0.60, 0.50, 0.02, caps, {'day': 0, 'market': 25, 'event': 0})[0], 0)
        self.assertEqual(contracts_for(1000, 0.60, 0.50, 0.02, caps, {'day': 0, 'market': 0, 'event': 50})[0], 0)
        n, _ = contracts_for(1000, 0.60, 0.50, 0.02, caps, {'day': 0, 'market': 0, 'event': 0, 'ask_size': 2})
        self.assertEqual(n, 2)
        n, reason = contracts_for(1, 0.60, 0.50, 0.02, caps, {'day': 0, 'market': 0, 'event': 0})
        self.assertEqual(n, 0)
        self.assertEqual(reason, 'below one contract')


class QuoteTests(unittest.TestCase):
    def test_settled_market_parses_without_a_quote(self):
        q = parse_market({'ticker': 'T', 'result': 'yes', 'status': 'finalized'})
        self.assertIsNotNone(q)
        self.assertEqual(settlement_of(q), 'yes')

    def test_live_market_without_a_quote_is_dropped(self):
        self.assertIsNone(parse_market({'ticker': 'T', 'status': 'active'}))

    def test_void_and_numeric_settlement(self):
        self.assertEqual(settlement_of({'result': '', 'status': 'voided', 'settlement_value': None}), 'void')
        self.assertEqual(settlement_of({'result': '', 'status': 'finalized', 'settlement_value': 0}), 'no')


class ConfigTests(unittest.TestCase):
    def test_paper_only_false_refuses_to_run(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump({'paper_only': False}, f)
            path = f.name
        try:
            with self.assertRaises(SystemExit):
                load(path)
        finally:
            os.remove(path)

    def test_kill_env_and_source_edge(self):
        key = 'PAPER_BOT_KILL'
        old = os.environ.get(key)
        os.environ[key] = '1'
        try:
            cfg = load(os.path.join(ROOT, 'paper-bot', 'config.json'))
        finally:
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        self.assertTrue(cfg['kill_switch'])
        self.assertTrue(cfg['paper_only'])
        over = source_cfg({'min_edge': 0.08, 'min_price': 0.05, 'max_price': 0.95, 'max_spread': 0.10,
                           'sources': {'nba_total': {'enabled': True, 'min_edge': 0.12}}}, 'nba_total')
        self.assertEqual(over['min_edge'], 0.12)


class NbaSignalTests(unittest.TestCase):
    def test_total_formula_and_over_probability(self):
        state = _nba_state()
        mu, bh, ba = project_total(state, 'TOR', 'NY', 1_000_000, [])
        self.assertEqual((mu, bh, ba), (202.0, 0.0, 0.0))
        self.assertEqual(p_over(202, 10, 202), 0.5)
        state['team_last'] = {'TOR': 1_000_000 - 10 * 3600}
        mu, bh, ba = project_total(state, 'TOR', 'NY', 1_000_000, [])
        self.assertEqual((mu, bh, ba), (201.0, 1.0, 0.0))

    def test_ct_refuses_and_the_early_window_skips(self):
        state = _nba_state()
        state['P']['CT'] = 1.5
        self.assertIsNone(project_total(state, 'TOR', 'NY', 1_000_000, []))
        out, note = proposals_from(state, [_game()], [_tight_market(0.42)], GATES, _now(), 10, 'sd')
        self.assertEqual(out, [])
        self.assertIn('not trading', note)
        state['P']['CT'] = 0
        state['season_start'] = None
        self.assertFalse(window_open(state, _game()['tip']))
        out, note = proposals_from(state, [_game()], [_tight_market(0.42)], GATES, _now(), 10, 'sd')
        self.assertEqual(out, [])
        self.assertIn('first four weeks', note)
        pre = _game()
        pre['season_type'] = 1
        state['season_start'] = 1000
        out, note = proposals_from(state, [pre], [_tight_market(0.42)], GATES, _now(), 10, 'sd')
        self.assertEqual(out, [])
        self.assertIn('preseason', note)

    def test_edge_and_spread_gates(self):
        state = _nba_state()
        # mu 202, strike 202, p = 0.50. Ask 0.42 clears 8%. Ask 0.43 does not.
        hit, _ = proposals_from(state, [_game()], [_tight_market(0.42)], GATES, _now(), 10, 'sd')
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]['side'], 'yes')
        self.assertEqual(hit[0]['price'], 0.42)
        self.assertAlmostEqual(hit[0]['model_prob'], 0.5)
        miss, _ = proposals_from(state, [_game()], [_tight_market(0.43)], GATES, _now(), 10, 'sd')
        self.assertEqual(miss, [])
        wide = _tight_market(0.42)
        wide['yes_bid'] = 0.20
        self.assertFalse(market_tradable(wide, GATES))
        none, _ = proposals_from(state, [_game()], [wide], GATES, _now(), 10, 'sd')
        self.assertEqual(none, [])

    def test_sigma_fallback_uses_tune_mae(self):
        sigma, src = sigma_of({}, {'tune_mae': [1, 10]})
        self.assertEqual(src, 'game_model.tune_mae[1] * sqrt(pi/2)')
        self.assertAlmostEqual(sigma, 10 * math.sqrt(math.pi / 2))


class CfbSignalTests(unittest.TestCase):
    def test_names_and_sigma_formula(self):
        self.assertTrue(team_match('Middle Tenn', 'Middle Tennessee'))
        self.assertTrue(team_match('Jacksonville St', 'Jacksonville State'))
        self.assertFalse(team_match('Texas', 'Texas A&M'))
        sigma, prov = sigma_from_backtest({
            'test': '2024-2025',
            'seasons': {
                '2024': {'model_miss': 10, 'games': 100},
                '2025': {'model_miss': 20, 'games': 300},
            },
        })
        mae = (10 * 100 + 20 * 300) / 400
        self.assertAlmostEqual(sigma, mae * math.sqrt(math.pi / 2))
        self.assertEqual(prov['formula'], 'games-weighted model_miss * sqrt(pi/2)')
        self.assertNotIn('roi', json.dumps(prov).lower())

    def test_real_backtest_block_is_only_a_formula(self):
        with open(os.path.join(ROOT, 'data', 'cfb_model.json')) as f:
            bt = json.load(f)['backtest']
        sigma, prov = sigma_from_backtest(bt)
        seasons = prov['seasons']
        mae = sum(s['model_miss'] * s['games'] for s in seasons) / sum(s['games'] for s in seasons)
        self.assertAlmostEqual(sigma, mae * math.sqrt(math.pi / 2))
        self.assertEqual([s['season'] for s in seasons], ['2024', '2025'])

    def test_one_side_week_gate_and_ambiguous(self):
        now = _now()
        kick = datetime(2026, 10, 13, 23, tzinfo=timezone.utc).timestamp()
        model = _cfb_model(kick, margin=-10, week=6)
        sigma, _ = sigma_from_backtest(model['backtest'])
        p_home = 0.5 * (1 + math.erf((-10 / sigma) / math.sqrt(2)))
        p_away = 1 - p_home
        home = _cfb_quote('H', 'Middle Tennessee', 0.20)
        away = _cfb_quote('A', 'Delaware', 0.40)
        out, note = cfb_proposals(model, [home, away], dict(GATES, max_edge=0.9), now)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['ticker'], 'A')
        self.assertGreater(p_away - 0.40, p_home - 0.20)
        self.assertIn('No Kalshi backtest', out[0]['detail']['note'])
        self.assertIn('signals', note)
        early = _cfb_model(kick, margin=30, week=3)
        out, note = cfb_proposals(early, [home, away], GATES, now)
        self.assertEqual(out, [])
        self.assertIn('min week 4', note)
        ambiguous = _cfb_model(kick, margin=10, week=6)
        ambiguous['board'].append(dict(ambiguous['board'][0]))
        out, _ = cfb_proposals(ambiguous, [_cfb_quote('H', 'Middle Tennessee', 0.20), _cfb_quote('A', 'Delaware', 0.70)], GATES, now)
        self.assertEqual(out, [])


class PricedMarginTests(unittest.TestCase):
    def _go(self, board_extra, cfg_extra=None, ask_h=0.45, ask_a=0.60):
        kick = datetime(2026, 10, 13, 23, tzinfo=timezone.utc).timestamp()
        model = _cfb_model(kick, margin=0, week=6)
        model['board'][0].update(board_extra)
        cfg = dict(GATES, **(cfg_extra or {}))
        qs = [_cfb_quote('H', 'Middle Tennessee', ask_h), _cfb_quote('A', 'Delaware', ask_a)]
        return cfb_proposals(model, qs, cfg, _now())

    def test_prices_from_blend_and_falls_back_to_model(self):
        out, _ = self._go({'model_margin': 0, 'blend_margin': 3.0, 'market_margin': 3.0}, ask_h=0.45)
        d = out[0]['detail']
        self.assertEqual((d['priced_margin'], d['market_margin'], d['model_margin']), (3.0, 3.0, 0))
        sigma, _ = sigma_from_backtest(_cfb_model(0, 0, 6)['backtest'])
        self.assertAlmostEqual(out[0]['model_prob'], 0.5 * (1 + math.erf((3.0 / sigma) / math.sqrt(2))), 4)
        out, _ = self._go({'model_margin': 4.0, 'market_margin': 4.0}, ask_h=0.45)
        self.assertEqual(out[0]['detail']['priced_margin'], 4.0)
        self.assertEqual(out[0]['detail']['priced_from'], 'model_margin')

    def test_max_edge_cap_skips_and_counts(self):
        board = {'model_margin': 20, 'blend_margin': 20, 'market_margin': 20}
        out, note = self._go(board, {'max_edge': 0.15}, ask_h=0.30)
        self.assertEqual(out, [])
        self.assertIn('over the max edge cap', note)
        out, _ = self._go(board, {'max_edge': 0.9}, ask_h=0.30)
        self.assertEqual(len(out), 1)

    def test_model_market_gap_skips_and_counts(self):
        board = {'model_margin': 10, 'blend_margin': 10, 'market_margin': 1}
        out, note = self._go(board, {'max_edge': 0.9}, ask_h=0.40)
        self.assertEqual(out, [])
        self.assertIn('model/market gap', note)
        out, _ = self._go(board, {'max_edge': 0.9, 'max_model_market_gap': None}, ask_h=0.40)
        self.assertEqual(len(out), 1)

    def test_nba_best_side_edge_cap(self):
        q = {'ticker': 'T', 'yes_bid': 0.28, 'yes_ask': 0.30, 'no_bid': 0.70, 'no_ask': 0.72,
             'yes_ask_size': 100, 'no_ask_size': 100}
        capped = []
        self.assertIsNone(_best_side(q, 0.60, dict(GATES, max_edge=0.15), capped))
        self.assertEqual(capped, ['T'])
        self.assertIsNotNone(_best_side(q, 0.60, dict(GATES, max_edge=0.5), []))

    def test_config_defaults(self):
        cfg = load(None)
        self.assertEqual(cfg['max_edge'], 0.15)
        sc = source_cfg(cfg, 'cfb_ml')
        self.assertEqual((sc['max_edge'], sc['max_model_market_gap']), (0.15, 7.0))

    def test_pre_fix_tag_is_idempotent_and_keeps_trades(self):
        led = empty(1000)
        base = {'source': 'cfb_ml', 'status': 'open', 'stake': 10}
        led['trades'] = [
            dict(base, ts='2026-10-13T14:29:38Z', detail={'model_margin': -10.0}),
            dict(base, ts='2026-10-13T18:00:00Z', detail={'model_margin': 2.0, 'priced_margin': 2.0}),
            dict(base, ts='2026-10-12T14:00:00Z', detail={'model_margin': 2.0}),
            dict(base, ts='2026-10-13T14:29:38Z', source='nba_total', detail={}),
        ]
        self.assertEqual(tag_pre_fix_trades(led), 1)
        self.assertEqual(tag_pre_fix_trades(led), 0)
        self.assertEqual(led['trades'][0]['tags'], ['pre_fix_raw_v1_margin'])
        self.assertEqual(sum('tags' in t for t in led['trades']), 1)
        self.assertEqual(len(led['trades']), 4)
        self.assertEqual(led['trades'][0]['status'], 'open')


class EngineTests(unittest.TestCase):
    def test_paper_fill_logs_the_ask_and_will_not_double_fill(self):
        now = datetime(2026, 10, 13, 16, tzinfo=timezone.utc)
        proposal = _proposal(prob=0.60, price=0.50)
        engine = _engine([proposal, dict(proposal)], now)
        run = engine.run()
        self.assertEqual(run['opened'], 1)
        row = engine.ledger['trades'][0]
        self.assertEqual(row['ts'], '2026-10-13T16:00:00Z')
        self.assertEqual(row['price'], 0.50)
        self.assertEqual(row['model_prob'], 0.6)
        self.assertEqual(row['edge'], proposal['edge'])
        self.assertEqual(row['contracts'], 38)
        self.assertEqual(row['stake'], 19.76)
        self.assertEqual(row['fee_per'], 0.02)
        self.assertEqual(engine.ledger['cash'], 980.24)
        self.assertIsNone(row['close_mid'])
        self.assertIn('filter off', ' '.join(run['notes']))
        self.assertIn('size caps', ' '.join(run['notes']))

    def test_no_side_marks_at_the_bid(self):
        now = datetime(2026, 10, 13, 16, tzinfo=timezone.utc)
        p = _proposal(prob=0.70, price=0.40)
        p['side'] = 'no'
        p['no_bid'] = 0.55
        p['no_ask'] = 0.40
        engine = _engine([p], now)
        engine.run()
        row = engine.ledger['trades'][0]
        self.assertEqual(row['side'], 'no')
        self.assertEqual(row['mark_value'], round(row['contracts'] * 0.55, 2))

    def test_event_cap_blocks_the_second_strike(self):
        now = datetime(2026, 10, 13, 16, tzinfo=timezone.utc)
        a = _proposal()
        b = _proposal()
        b['ticker'] = a['ticker'] + '-B'
        cfg = _engine_cfg()
        cfg['max_stake_per_event'] = 20
        engine = Engine(cfg, empty(1000), [_Source([a, b])], _Kalshi(), _off(), now)
        engine.run()
        self.assertEqual(sum(1 for t in engine.ledger['trades'] if t['status'] == 'open'), 1)

    def test_settlement_cash_and_clv(self):
        t1 = datetime(2026, 10, 13, 16, tzinfo=timezone.utc)
        engine = _engine([_proposal(prob=0.60, price=0.50)], t1)
        engine.run()
        ticker = engine.ledger['trades'][0]['ticker']
        t2 = datetime(2026, 10, 13, 20, tzinfo=timezone.utc)
        kalshi = _Kalshi()
        kalshi.by[ticker] = _quote(ticker, yes_bid=0.55, yes_ask=0.57)
        engine.now = t2
        engine.kalshi = kalshi
        engine.notes = []
        engine.run()
        row = engine.ledger['trades'][0]
        self.assertEqual(row['status'], 'open')
        self.assertEqual(row['close_mid'], 0.56)
        t3 = datetime(2026, 10, 14, 2, tzinfo=timezone.utc)
        kalshi.by[ticker] = _quote(ticker, result='yes', status='finalized')
        engine.now = t3
        engine.run()
        row = engine.ledger['trades'][0]
        self.assertEqual(row['status'], 'settled')
        self.assertTrue(row['won'])
        self.assertEqual(row['payout'], 38)
        self.assertEqual(row['pnl'], 18.24)
        self.assertEqual(row['clv'], 0.06)
        self.assertEqual(engine.ledger['cash'], 1018.24)
        self.assertEqual(et_day(row['settled_ts']), '2026-10-13')

    def test_loss_and_void(self):
        for result, status, cash in (('no', 'settled', 980.24), ('void', 'void', 1000.0)):
            engine = _engine([_proposal(prob=0.60, price=0.50)], datetime(2026, 10, 13, 16, tzinfo=timezone.utc))
            engine.run()
            ticker = engine.ledger['trades'][0]['ticker']
            engine.now = datetime(2026, 10, 14, 2, tzinfo=timezone.utc)
            engine.kalshi = _Kalshi()
            if result == 'void':
                engine.kalshi.by[ticker] = _quote(ticker, result='', status='voided')
            else:
                engine.kalshi.by[ticker] = _quote(ticker, result='no', status='finalized')
            engine.run()
            row = engine.ledger['trades'][0]
            self.assertEqual(row['status'], status)
            self.assertEqual(row['pnl'], 0 if result == 'void' else -19.76)
            self.assertEqual(engine.ledger['cash'], cash)

    def test_loss_stop_and_kill_switch_still_settle(self):
        now = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)
        ledger = empty(1000)
        ledger['trades'].append({
            'status': 'open', 'ticker': 'SETTLE', 'event': 'E', 'side': 'yes', 'source': 'nba_total',
            'contracts': 10, 'stake': 5, 'price': 0.5, 'model_prob': 0.6, 'ts': '2026-10-12T16:00:00Z',
            'mark_value': 5, 'fee_total': 0.2,
        })
        ledger['trades'].append({
            'status': 'settled', 'ticker': 'LOST', 'event': 'E2', 'side': 'yes', 'source': 'nba_total',
            'contracts': 100, 'stake': 80, 'payout': 20, 'pnl': -60, 'won': False, 'price': 0.5,
            'model_prob': 0.6, 'ts': '2026-10-13T14:00:00Z', 'settled_ts': '2026-10-13T16:00:00Z',
        })
        recompute_cash(ledger)
        kalshi = _Kalshi()
        kalshi.by['SETTLE'] = _quote('SETTLE', result='yes', status='finalized')
        engine = Engine(_engine_cfg(), ledger, [_Source([_proposal()])], kalshi, _off(), now)
        run = engine.run()
        self.assertEqual(run['opened'], 0)
        self.assertTrue(run['halt'])
        self.assertEqual(engine.ledger['trades'][0]['status'], 'settled')
        self.assertEqual(len(engine.ledger['trades']), 2)

        fresh = empty(1000)
        fresh['trades'].append({
            'status': 'open', 'ticker': 'SETTLE', 'event': 'E', 'side': 'yes', 'source': 'cfb_ml',
            'contracts': 10, 'stake': 5, 'price': 0.5, 'model_prob': 0.6, 'ts': '2026-10-12T16:00:00Z',
            'mark_value': 5,
        })
        cfg = _engine_cfg()
        cfg['kill_switch'] = True
        engine = Engine(cfg, fresh, [_Source([_proposal()])], kalshi, _off(), now)
        run = engine.run()
        self.assertEqual(run['halt'], 'kill switch is on')
        self.assertEqual(run['opened'], 0)
        self.assertEqual(fresh['trades'][0]['status'], 'settled')

    def test_definitive_veto_sticks_and_a_transport_error_does_not(self):
        now = datetime(2026, 10, 13, 16, tzinfo=timezone.utc)
        cfg = _engine_cfg()
        cfg['llm_filter'] = {'enabled': True, 'env_key': 'PAPER_BOT_LLM_API_KEY', 'model': 'gpt-4o-mini', 'max_calls': 20}

        def veto(url, key, body):
            return {'choices': [{'message': {'content': '{"veto": true, "reason": "starter is out"}'}}]}

        llm = LlmFilter(cfg, env={'PAPER_BOT_LLM_API_KEY': 'test'}, post=veto)
        engine = Engine(cfg, empty(1000), [_Source([_proposal()])], _Kalshi(), llm, now)
        engine.run()
        self.assertEqual(engine.ledger['trades'][0]['status'], 'vetoed')
        self.assertEqual(engine.ledger['trades'][0]['llm']['reason'], 'starter is out')
        self.assertEqual(engine.ledger['cash'], 1000)
        engine.now = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)
        engine.run()
        self.assertEqual(len(engine.ledger['trades']), 1)

        def boom(url, key, body):
            raise TimeoutError('down')

        llm = LlmFilter(cfg, env={'PAPER_BOT_LLM_API_KEY': 'test'}, post=boom)
        engine = Engine(cfg, empty(1000), [_Source([_proposal()])], _Kalshi(), llm, now)
        run = engine.run()
        self.assertEqual(engine.ledger['trades'], [])
        self.assertTrue(any('filter error' in n for n in run['notes']))

        def allow(url, key, body):
            return {'choices': [{'message': {'content': '{"veto": false, "reason": "no news"}'}}]}

        llm.post = allow
        llm.calls = 0
        engine.llm = llm
        engine.now = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)
        engine.run()
        self.assertEqual(engine.ledger['trades'][0]['status'], 'open')

    def test_calibration_bins(self):
        ledger = empty(1000)
        for prob, won, pnl in ((0.62, True, 1), (0.68, False, -1)):
            ledger['trades'].append({
                'status': 'settled', 'source': 'nba_total', 'model_prob': prob, 'won': won,
                'stake': 1, 'pnl': pnl, 'clv': 0.01, 'settled_ts': '2026-10-13T20:00:00Z', 'fee_total': 0,
            })
        summary = summarize(ledger)
        bin6 = summary['calibration'][6]
        self.assertEqual(bin6['n'], 2)
        self.assertEqual(bin6['hit'], 0.5)
        self.assertEqual(summary['by_source']['nba_total']['settled'], 2)


class LiveAndFilterTests(unittest.TestCase):
    def test_place_order_never_reaches_the_network(self):
        import scripts.paper_bot.live as live
        import urllib.request
        called = []
        original = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: called.append(1)
        try:
            with self.assertRaises(LiveTradingDisabled):
                LiveBroker().place_order(ticker='T', side='yes', count=1)
            live.LIVE_ORDERS_IMPLEMENTED = True
            with self.assertRaises(LiveTradingDisabled):
                LiveBroker().place_order(ticker='T', side='yes', count=1)
        finally:
            live.LIVE_ORDERS_IMPLEMENTED = False
            urllib.request.urlopen = original
        self.assertEqual(called, [])
        self.assertFalse(LIVE_ORDERS_IMPLEMENTED)
        with open(os.path.join(ROOT, 'scripts', 'paper_bot', 'live.py')) as f:
            live_src = f.read()
        with open(os.path.join(ROOT, 'scripts', 'paper_bot', 'engine.py')) as f:
            engine_src = f.read()
        self.assertNotIn('urlopen', live_src)
        self.assertNotIn('portfolio/orders', live_src)
        self.assertNotIn('place_order', engine_src)

    def test_signer_round_trip(self):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        import base64
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        signer = KalshiSigner('kid', pem)
        headers = signer.headers('post', '/trade-api/v2/portfolio/orders?ignored=1', 1_700_000_000_000)
        self.assertEqual(headers['KALSHI-ACCESS-KEY'], 'kid')
        message = b'1700000000000POST/trade-api/v2/portfolio/orders'
        key.public_key().verify(
            base64.b64decode(headers['KALSHI-ACCESS-SIGNATURE']),
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )

    def test_filter_off_and_missing_key(self):
        off = LlmFilter({'llm_filter': {'enabled': False}})
        decision = off.review({'game': 'x'})
        self.assertFalse(decision.veto)
        self.assertFalse(decision.enabled)
        on = LlmFilter({'llm_filter': {'enabled': True, 'env_key': 'PAPER_BOT_LLM_API_KEY'}}, env={})
        decision = on.review({'game': 'x'})
        self.assertTrue(decision.veto)
        self.assertTrue(decision.definitive)

    def test_sources_skip_disabled(self):
        cfg = load(os.path.join(ROOT, 'paper-bot', 'config.json'))
        cfg['sources']['nba_total']['enabled'] = False
        names = [s.name for s in load_sources(cfg, ROOT, get=lambda url: {})]
        self.assertEqual(names, ['cfb_ml'])


def _caps():
    return {
        'kelly_fraction': 0.25,
        'max_stake_per_trade': 25,
        'max_fraction_per_trade': 0.02,
        'max_stake_per_day': 100,
        'max_stake_per_market': 25,
        'max_stake_per_event': 50,
    }


def _engine_cfg():
    cfg = copy.deepcopy(_caps())
    cfg.update({'paper_only': True, 'kill_switch': False, 'daily_loss_stop': 50, 'min_edge': 0.08,
                'monthly_cost_target': 30, 'llm_filter': {'enabled': False}})
    return cfg


def _off():
    return LlmFilter({'llm_filter': {'enabled': False}})


class _Source:
    name = 'nba_total'

    def __init__(self, proposals):
        self.proposals = proposals

    def collect(self, kalshi, now):
        return list(self.proposals), 'fixture source'


class _Kalshi:
    def __init__(self):
        self.by = {}

    def markets(self, series, status='open'):
        return []

    def markets_by_ticker(self, tickers):
        return {t: self.by[t] for t in tickers if t in self.by}


def _engine(proposals, now, bankroll=1000):
    return Engine(_engine_cfg(), empty(bankroll), [_Source(proposals)], _Kalshi(), _off(), now)


def _proposal(prob=0.60, price=0.50):
    return {
        'source': 'nba_total',
        'ticker': 'KXNBATOTAL-26OCT13NYKTOR-220',
        'event': 'KXNBATOTAL-26OCT13NYKTOR',
        'title': 'NY at TOR over 220',
        'game': 'NY @ TOR',
        'side': 'yes',
        'strike': 220,
        'model_prob': prob,
        'edge': round(prob - price, 4),
        'yes_bid': round(price - 0.02, 4),
        'yes_ask': price,
        'no_bid': round(1 - price, 4),
        'no_ask': round(1 - (price - 0.02), 4),
        'price': price,
        'ask_size': 500,
        'detail': {},
    }


def _quote(ticker, yes_bid=0.5, yes_ask=0.52, result='', status='active'):
    return {
        'ticker': ticker, 'result': result, 'status': status,
        'yes_bid': yes_bid, 'yes_ask': yes_ask,
        'no_bid': round(1 - yes_ask, 4), 'no_ask': round(1 - yes_bid, 4),
        'settlement_value': None,
    }


def _now():
    return datetime(2026, 10, 13, 16, tzinfo=timezone.utc)


def _nba_state():
    return {
        'base': 100, 'hfa': 2,
        'O': {'NY': 1, 'TOR': 1}, 'D': {'NY': 0, 'TOR': 0},
        'P': {'CT': 0, 'B2B': 2}, 'R': {'NY': 0, 'TOR': 0},
        'team_last': {}, 'season_start': 1000, 'sd_total': 10,
    }


def _game():
    tip = datetime(2026, 10, 13, 23, tzinfo=timezone.utc)
    return {
        'id': '1', 'home': 'TOR', 'away': 'NY', 'tip': tip.timestamp(),
        'et_date': tip.astimezone(ET).date(), 'season_type': 2, 'status': 'scheduled',
        'name': 'NY @ TOR',
    }


def _tight_market(ask):
    return {
        'ticker': 'KXNBATOTAL-26OCT13NYKTOR-202',
        'event': 'KXNBATOTAL-26OCT13NYKTOR',
        'title': 'total', 'sub': '', 'strike': 202,
        'yes_bid': round(ask - 0.02, 4), 'yes_ask': ask,
        'no_bid': round(1 - ask, 4), 'no_ask': round(1 - (ask - 0.02), 4),
        'yes_ask_size': 100, 'no_ask_size': 100,
        'status': 'active', 'result': '',
    }


def _cfb_model(kick, margin, week):
    return {
        'backtest': {
            'test': '2024-2025', 'min_week': 4,
            'seasons': {
                '2024': {'model_miss': 10, 'games': 100},
                '2025': {'model_miss': 20, 'games': 300},
            },
        },
        'ratings': [
            {'id': 1, 'team': 'Middle Tennessee', 'abbr': 'MTSU'},
            {'id': 2, 'team': 'Delaware', 'abbr': 'DEL'},
        ],
        'board': [{
            'home': 'Middle Tenn', 'away': 'Delaware', 'home_id': 1, 'away_id': 2,
            'week': week, 'model_margin': margin, 'kick': kick,
        }],
    }


def _cfb_quote(ticker, sub, ask):
    return {
        'ticker': ticker, 'event': 'KXNCAAFGAME-26OCT13DELMTU', 'title': sub, 'sub': sub,
        'strike': None, 'yes_bid': round(ask - 0.02, 4), 'yes_ask': ask,
        'no_bid': round(1 - ask, 4), 'no_ask': round(1 - (ask - 0.02), 4),
        'yes_ask_size': 100, 'no_ask_size': 100, 'status': 'active', 'result': '',
    }


if __name__ == '__main__':
    unittest.main()
