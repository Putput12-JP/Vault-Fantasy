"""cfb_jp_novig strategy contracts. No network: Novig and Kalshi are fakes, the model file is a fixture.

Run from the repo root: python3 -m pytest tests/test_cfb_jp_novig.py   (or python3 tests/test_cfb_jp_novig.py)
"""
import copy
import json
import math
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.paper_bot import cfb_jp_novig as S
from scripts.paper_bot.config import load
from scripts.paper_bot.engine import Engine
from scripts.paper_bot.ledger import empty, recompute_cash, summarize
from scripts.paper_bot.novig_public import NovigPublic, outcome_quote, parse_outcome, uuid7_ms
from scripts.paper_bot.quotes import parse_market

UTC = timezone.utc
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
KICK = NOW + timedelta(days=3)
HAW_OUT, UNM_OUT = 'out-haw', 'out-unm'


def uuid7(ms):
    h = f'{ms:012x}'
    return f'{h[:8]}-{h[8:]}-7000-8000-000000000000'


def ratings():
    return [{'id': 62, 'team': 'Hawaii', 'abbr': 'HAW'}, {'id': 167, 'team': 'New Mexico', 'abbr': 'NMEX'}]


def board_game(**kw):
    g = {'key': 'cfb:1', 'kick': KICK.timestamp(), 'home': 'Hawaii', 'away': 'New Mexico', 'home_id': 62, 'away_id': 167,
         'week': 8, 'model_margin': 3.0, 'open_margin': -6.0}   # home +6 at the open, JP+ has home by 3: a 9 point edge
    g.update(kw)
    return g


def write_model(root, board):
    os.makedirs(os.path.join(root, 'data'), exist_ok=True)
    with open(os.path.join(root, 'data', 'cfb_model.json'), 'w') as f:
        json.dump({'board': board, 'ratings': ratings()}, f)


def spread_market(strike, mid=None, status='OPEN', codes=('HAW', 'UNM'), created_ms=1_790_000_000_000):
    """Strike k: HAW +k / UNM -k, the market id a UUIDv7 stamped at created_ms."""
    mid = mid or uuid7(created_ms)
    return {'marketId': mid, 'marketType': 'SPREAD', 'status': status, 'strike': str(strike),
            'outcomes': [{'outcomeId': f'{HAW_OUT}-{strike}', 'name': f'{codes[0]} {strike:+g}'},
                         {'outcomeId': f'{UNM_OUT}-{strike}', 'name': f'{codes[1]} {-strike:+g}'}]}


def book(strike, haw_bids=((0.40, 20000),), unm_bids=((0.58, 40000), (0.57, 40000), (0.50, 100000))):
    return {'orders': {f'{HAW_OUT}-{strike}': [{'price': str(p), 'qty': q} for p, q in haw_bids],
                       f'{UNM_OUT}-{strike}': [{'price': str(p), 'qty': q} for p, q in unm_bids]}}


class FakeNovig:
    def __init__(self, strikes=(4.5, 5.5, 6.5, 7.5), codes=('HAW', 'UNM'), fail=False):
        self.fail = fail
        self.used = 0
        self.errors = 0
        self.markets_by_strike = {k: spread_market(k, codes=codes, created_ms=1_790_000_000_000 + int(k * 1000))
                                  for k in strikes}
        self.books = {m['marketId']: book(k) for k, m in self.markets_by_strike.items()}
        self.event = {'eventId': 'ev1', 'description': 'New Mexico @ Hawaii', 'startsTs': int(KICK.timestamp() * 1000)}

    def mid(self, strike):
        return self.markets_by_strike[strike]['marketId']

    def events(self):
        if self.fail:
            return []
        return [self.event]

    def markets(self, event_id):
        return [] if self.fail else list(self.markets_by_strike.values())

    def book(self, market_id):
        return None if self.fail else copy.deepcopy(self.books.get(market_id))


class FakeKalshi:
    def __init__(self, rows=None, fail=False):
        self.rows = rows or []
        self.fail = fail

    def markets(self, series, status='open', limit_pages=20):
        if self.fail:
            raise RuntimeError('kalshi down')
        return list(self.rows)

    def markets_by_ticker(self, tickers):
        if self.fail:
            raise RuntimeError('kalshi down')
        return {r['ticker']: r for r in self.rows if r['ticker'] in tickers}


def kalshi_row(team, floor, bid, ask, event='KXNCAAFSPREAD-26OCT23NMEXHAW', opened='2026-10-19T16:00:00Z'):
    return parse_market({'ticker': f'{event}-{team[:4].upper()}{int(floor)}', 'event_ticker': event,
                         'yes_sub_title': f'{team} wins by over {floor} points', 'floor_strike': floor,
                         'yes_bid_dollars': str(bid), 'yes_ask_dollars': str(ask), 'yes_ask_size_fp': '150.00',
                         'yes_bid_size_fp': '90.00', 'open_time': opened, 'status': 'active'})


def make(tmp, board=None, novig=None):
    root = tmp
    write_model(root, board if board is not None else [board_game()])
    novig = novig or FakeNovig()
    return S.CfbJpNovig({}, root, novig=novig), novig


def ledger_with(strategy=None):
    return empty(1000)


def trades_of(ledger):
    return [t for t in ledger['trades'] if t['source'] == S.STRATEGY]


class TriggerBuckets(unittest.TestCase):
    def test_edge_is_model_minus_open_in_points(self):
        self.assertEqual(S.jp_edge(board_game()), (9.0, 'home'))
        self.assertEqual(S.jp_edge(board_game(model_margin=-8.0, open_margin=-1.0)), (7.0, 'away'))
        self.assertIsNone(S.jp_edge(board_game(open_margin=None)))
        self.assertIsNone(S.jp_edge(board_game(model_margin=-6.0)))

    def test_buckets_are_the_highest_threshold_reached(self):
        for edge, want in ((2.9, None), (3.0, '3+'), (4.9, '3+'), (5.0, '5+'), (6.9, '5+'), (7.0, '7+'), (12.0, '7+')):
            self.assertEqual(S.bucket_of(edge), want, edge)

    def test_triggers_log_3_plus_but_only_5_plus_counts(self):
        now = NOW.timestamp()
        board = [board_game(key='a', model_margin=-6 + 3.0), board_game(key='b', model_margin=-6 + 5.0),
                 board_game(key='c', model_margin=-6 + 7.0), board_game(key='d', model_margin=-6 + 2.9)]
        got = {t['key']: t['bucket'] for t in S.triggers(board, now)}
        self.assertEqual(got, {'a': '3+', 'b': '5+', 'c': '7+'})

    def test_upcoming_only(self):
        self.assertEqual(S.triggers([board_game(kick=NOW.timestamp() - 60)], NOW.timestamp()), [])

    def test_open_handicap_is_for_the_jp_side(self):
        t = S.triggers([board_game()], NOW.timestamp())[0]
        self.assertEqual((t['side'], t['team'], t['open_hcap']), ('home', 'Hawaii', 6.0))
        t = S.triggers([board_game(model_margin=-20.0)], NOW.timestamp())[0]
        self.assertEqual((t['side'], t['team'], t['open_hcap']), ('away', 'New Mexico', -6.0))


class WeekFilter(unittest.TestCase):
    def test_week_7_and_later(self):
        self.assertFalse(S.week_ok(board_game(week=6)))
        self.assertTrue(S.week_ok(board_game(week=7)))
        self.assertTrue(S.week_ok(board_game(week=8)))
        self.assertTrue(S.week_ok(board_game(week=14)))

    def test_a_final_or_a_started_game_is_not_a_trigger(self):
        now = NOW.timestamp()
        self.assertTrue(S.pre_kick(board_game(week=7), now))
        self.assertEqual(S.triggers([board_game(week=7)], now)[0]['key'], 'cfb:1')
        self.assertFalse(S.pre_kick(board_game(week=7, kick=now), now))
        self.assertFalse(S.pre_kick(board_game(week=7, kick=now - 60), now))
        self.assertEqual(S.triggers([board_game(week=7, kick=now - 60)], now), [])
        final = board_game(week=7, result='W', hs=31, as_=17)
        self.assertTrue(S.game_final(final))
        self.assertFalse(S.pre_kick(final, now))
        self.assertEqual(S.triggers([final], now), [])
        self.assertEqual(S.triggers([board_game(week=7, result='P', hs=24, as_=24)], now), [])
        self.assertEqual(S.triggers([board_game(week=7, hs=21, as_=14)], now), [])

    def test_bowls_pass_even_with_a_reset_week_number(self):
        dec = datetime(2026, 12, 22, 20, 0, tzinfo=UTC).timestamp()
        self.assertTrue(S.week_ok(board_game(week=1, kick=dec)))
        self.assertTrue(S.week_ok(board_game(week=1, kick=dec, season_type='postseason')))
        jan = datetime(2027, 1, 9, 20, 0, tzinfo=UTC).timestamp()
        self.assertTrue(S.week_ok(board_game(week=2, kick=jan)))

    def test_early_season_is_out(self):
        sept = datetime(2026, 9, 12, 20, 0, tzinfo=UTC).timestamp()
        self.assertFalse(S.week_ok(board_game(week=3, kick=sept)))
        self.assertEqual(S.triggers([board_game(week=6)], NOW.timestamp()), [])


class StrikeChoice(unittest.TestCase):
    def ladder(self, strikes, codes=('HAW', 'UNM')):
        return S.spread_ladder([spread_market(k, codes=codes) for k in strikes])

    def test_nearest_to_the_open_on_the_jp_side(self):
        pick = S.choose_strike(self.ladder([3.5, 5.5, 8.5, 12.5]), 'HAW', 6.0)
        self.assertEqual(pick['hcap'], 5.5)
        self.assertEqual(pick['outcome_id'], f'{HAW_OUT}-5.5')
        self.assertEqual(pick['other_id'], f'{UNM_OUT}-5.5')

    def test_tie_goes_to_more_points_for_the_jp_team(self):
        self.assertEqual(S.choose_strike(self.ladder([5.5, 6.5]), 'HAW', 6.0)['hcap'], 6.5)

    def test_the_other_team_is_the_negative_side_of_the_same_ladder(self):
        pick = S.choose_strike(self.ladder([5.5, 6.5, 7.5]), 'UNM', -6.0)
        self.assertEqual(pick['hcap'], -5.5)     # -5.5 and -6.5 tie at 0.5; -5.5 is more points for UNM
        self.assertEqual(pick['outcome_id'], f'{UNM_OUT}-5.5')

    def test_closed_markets_and_other_types_are_ignored(self):
        mk = [spread_market(6.0, status='SUSPENDED'), spread_market(9.5)]
        mk.append(dict(spread_market(6.0), marketType='TOTAL'))
        self.assertEqual(S.choose_strike(S.spread_ladder(mk), 'HAW', 6.0)['hcap'], 9.5)

    def test_codes_map_by_abbreviation_or_name_then_elimination(self):
        g = board_game()
        sides, how = S.code_sides(g, S.__dict__['_rating_index'](ratings()), self.ladder([5.5]), -6.0)
        self.assertEqual(sides, {'HAW': 'home', 'UNM': 'away'})
        self.assertEqual(how, 'name')

    def test_codes_fall_back_to_the_favourite_when_names_do_not_help(self):
        g = board_game(home='Zeta', away='Omega', home_id=None, away_id=None)
        ladder = S.spread_ladder([spread_market(k, codes=('QQQ', 'XXX')) for k in (5.5, 6.5)])
        sides, how = S.code_sides(g, {}, ladder, -6.0)     # open: home is the 6 point dog, so the dog code (+) is home
        self.assertEqual((sides, how), ({'QQQ': 'home', 'XXX': 'away'}, 'sign'))
        sides, how = S.code_sides(g, {}, ladder, -1.0)     # too close to read from the sign
        self.assertIsNone(sides)


class Sizing(unittest.TestCase):
    def test_quarter_of_the_depth_rounded_down(self):
        self.assertEqual(S.size_contracts(800), 200)
        self.assertEqual(S.size_contracts(10), 2)
        self.assertEqual(S.size_contracts(7), 1)
        self.assertEqual(S.size_contracts(3), 0)
        self.assertEqual(S.size_contracts(None), 0)
        self.assertEqual(S.size_contracts(float('nan')), 0)

    def test_depth_counts_two_cents_from_the_best_ask_in_dollar_contracts(self):
        q = outcome_quote(book(6.5), f'{HAW_OUT}-6.5', f'{UNM_OUT}-6.5')
        self.assertAlmostEqual(q['ask'], 0.42)
        self.assertAlmostEqual(q['bid'], 0.40)
        self.assertAlmostEqual(q['ask_size'], 800.0)      # 0.58 and 0.57 count; 0.50 is 8 cents away. qty 100 = $1
        self.assertAlmostEqual(q['bid_size'], 200.0)

    def test_empty_sides_are_none_not_zero(self):
        q = outcome_quote(book(6.5, haw_bids=(), unm_bids=()), f'{HAW_OUT}-6.5', f'{UNM_OUT}-6.5')
        self.assertEqual(q, {'bid': None, 'ask': None, 'bid_size': None, 'ask_size': None})

    def test_a_thin_ask_does_not_enter(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat, nv = make(tmp)
            nv.books[nv.mid(6.5)] = book(6.5, unm_bids=((0.58, 300),))      # 3 contracts offered
            nv.books[nv.mid(5.5)] = nv.books[nv.mid(6.5)]
            led = ledger_with()
            strat.run(led, NOW, FakeKalshi())
            self.assertEqual(trades_of(led), [])
            gs = led['strategies'][S.STRATEGY]['games']['cfb:1']
            self.assertEqual(gs['state'], 'watching')
            self.assertEqual(len(gs['novig']['snaps']), 1)


class FullLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.strat, self.nv = make(self.tmp.name)
        self.led = ledger_with()
        self.kalshi = FakeKalshi([kalshi_row('New Mexico', 6.5, 0.50, 0.53), kalshi_row('Hawaii', 3.5, 0.10, 0.14)])

    def run_at(self, when, **kw):
        return self.strat.run(self.led, when, self.kalshi, **kw)

    def game(self):
        return self.led['strategies'][S.STRATEGY]['games']['cfb:1']

    def test_listing_picks_the_strike_snapshots_and_enters_at_the_ask(self):
        self.run_at(NOW)
        gs = self.game()
        self.assertEqual(gs['novig']['hcap'], 6.5)
        self.assertEqual(gs['edge_bucket'], '7+')
        self.assertEqual(gs['code_src'], 'name')
        (t,) = trades_of(self.led)
        self.assertEqual((t['price'], t['contracts'], t['strike'], t['status']), (0.42, 119, 6.5, 'open'))      # 25% of 800 is 200, held to $50 (5% of $1000)
        self.assertAlmostEqual(t['stake'], 49.98)
        self.assertEqual((t['uncapped_contracts'], t['uncapped_stake']), (200, 84.0))
        self.assertEqual(t['fee_total'], 0.0)
        self.assertTrue(t['counts_toward_pass'])
        self.assertEqual((t['source'], t['strategy'], t['book']), ('cfb_jp_novig', 'cfb_jp_novig', 'novig'))
        self.assertEqual(t['detail']['entry_delay_min'], 0.0)
        self.assertEqual(S.parse_snap(gs['novig']['snaps'][0]),
                         {'ts': int(NOW.timestamp()), 'bid': 0.4, 'ask': 0.42, 'ask_size': 800.0, 'bid_size': 200.0})

    def test_first_listed_times_per_venue(self):
        self.run_at(NOW)
        gs = self.game()
        self.assertEqual(gs['novig']['listed_ts'], 1_790_000_004)          # earliest spread market on the ladder, UUIDv7 time
        self.assertEqual(gs['novig']['first_seen_ts'], int(NOW.timestamp()))
        self.assertEqual(gs['kalshi']['listed_ts'], datetime(2026, 10, 19, 16, 0, tzinfo=UTC).timestamp())
        self.assertEqual(gs['kalshi']['first_seen_ts'], int(NOW.timestamp()))

    def test_kalshi_is_the_equivalent_market_and_side(self):
        # JP+ is Hawaii +6.5, which is NO on "New Mexico wins by over 6.5"
        self.run_at(NOW)
        k = self.game()['kalshi']
        self.assertEqual((k['side'], k['floor']), ('no', 6.5))
        self.assertTrue(k['ticker'].startswith('KXNCAAFSPREAD-26OCT23NMEXHAW-') and k['ticker'].endswith('6'))
        s = S.parse_snap(k['snaps'][0])
        self.assertAlmostEqual(s['bid'], 0.47)
        self.assertAlmostEqual(s['ask'], 0.50)

    def test_snapshots_wait_for_the_30_minute_clock(self):
        self.run_at(NOW)
        self.run_at(NOW + timedelta(minutes=10))
        self.assertEqual(len(self.game()['novig']['snaps']), 1)
        self.run_at(NOW + timedelta(minutes=26))
        self.assertEqual(len(self.game()['novig']['snaps']), 2)
        self.assertEqual(len(self.game()['kalshi']['snaps']), 2)

    def test_exit_is_the_last_bid_before_kick_and_hold_is_graded(self):
        self.run_at(NOW)
        self.nv.books[self.nv.mid(6.5)] = book(6.5, haw_bids=((0.47, 30000),), unm_bids=((0.52, 40000),))
        self.run_at(KICK - timedelta(minutes=40))
        self.nv.books[self.nv.mid(6.5)] = book(6.5, haw_bids=((0.60, 30000),), unm_bids=((0.39, 40000),))
        self.run_at(KICK + timedelta(minutes=5))                       # after kick: a book that must NOT be used
        self.assertEqual(len(self.game()['novig']['snaps']), 2)
        (t,) = trades_of(self.led)
        self.assertEqual((t['status'], t['exit_bid'], t['exit_gap_min']), ('settled', 0.47, 40.0))
        self.assertAlmostEqual(t['exit_pnl_pc'], 0.05)
        self.assertAlmostEqual(t['pnl'], 5.95)                          # 119 contracts * 5 cents
        self.assertAlmostEqual(t['payout'], 55.93)
        self.assertEqual(t['exit_fill_frac'], 1.0)
        self.assertTrue(t['won'])
        self.assertAlmostEqual(t['clv'], round((0.47 + 0.48) / 2 - 0.42, 4))
        self.assertEqual(t['hold_status'], 'pending')

        board = [board_game(result='L', hs=20, as_=24)]                 # Hawaii loses by 4, +6.5 covers
        write_model(self.tmp.name, board)
        self.run_at(KICK + timedelta(hours=5))
        (t,) = trades_of(self.led)
        self.assertEqual((t['hold_status'], t['hold_result']), ('graded', 'win'))
        self.assertAlmostEqual(t['hold_pnl_pc'], 0.58)
        self.assertAlmostEqual(t['hold_pnl'], 69.02)
        self.assertEqual(self.game()['state'], 'graded')

    def test_no_pre_kick_bid_means_no_exit_but_hold_still_grades(self):
        nv = self.nv
        for k in (5.5, 6.5):
            nv.books[nv.mid(k)] = book(k, haw_bids=(), unm_bids=((0.58, 40000), (0.57, 40000)))
        self.run_at(NOW)
        write_model(self.tmp.name, [board_game(result='W', hs=40, as_=10)])
        self.run_at(KICK + timedelta(hours=4))
        (t,) = trades_of(self.led)
        self.assertEqual((t['status'], t['void_reason'], t['pnl']), ('void', 'no_exit_bid', 0.0))
        self.assertIsNone(t['exit_pnl_pc'])
        self.assertEqual(t['hold_result'], 'win')
        pb = self.led['strategies'][S.STRATEGY]['progress']
        self.assertEqual(pb['pass_bar']['n'], 0)
        self.assertEqual(pb['counts']['no_exit_bid'], 1)
        self.assertEqual(pb['slices']['5+']['hold']['n'], 1)

    def test_history_is_kept_when_games_are_graded(self):
        self.run_at(NOW)
        for m in range(30, 360, 30):
            self.run_at(NOW + timedelta(minutes=m))
        before = len(self.game()['novig']['snaps'])
        write_model(self.tmp.name, [board_game(result='L', hs=0, as_=30)])
        self.run_at(KICK + timedelta(hours=5))
        self.assertLessEqual(len(self.game()['novig']['snaps']), before)
        self.assertEqual(len(trades_of(self.led)), 1)
        self.assertEqual(S.parse_snap(self.game()['novig']['snaps'][0])['ts'], int(NOW.timestamp()))

    def test_a_game_is_tracked_once(self):
        self.run_at(NOW)
        self.run_at(NOW + timedelta(minutes=30))
        self.assertEqual(len(trades_of(self.led)), 1)

    def test_an_upcoming_week_7_game_enters_before_kickoff(self):
        write_model(self.tmp.name, [board_game(week=7)])
        self.run_at(NOW)
        (t,) = trades_of(self.led)
        self.assertEqual((t['detail']['week'], t['status']), (7, 'open'))
        self.assertLess(int(NOW.timestamp()), self.game()['kick'])

    def test_a_finished_week_7_game_is_not_entered_at_the_live_price(self):
        kick = (NOW - timedelta(days=3)).timestamp()
        g = board_game(week=7, kick=kick, result='W', hs=35, as_=17)
        write_model(self.tmp.name, [g])
        self.nv.event['startsTs'] = int(kick * 1000)
        calls = {'book': 0}
        orig = self.nv.book

        def wrapped(mid):
            calls['book'] += 1
            return orig(mid)

        self.nv.book = wrapped
        self.run_at(NOW)
        self.assertEqual(trades_of(self.led), [])
        self.assertEqual(self.led['strategies'][S.STRATEGY]['games'], {})
        self.assertEqual(calls['book'], 0)

    def test_a_final_score_blocks_entry_when_the_kick_stamp_is_still_ahead(self):
        g = board_game(week=7, result='L', hs=10, as_=28)
        write_model(self.tmp.name, [g])
        calls = {'book': 0}
        orig = self.nv.book

        def wrapped(mid):
            calls['book'] += 1
            return orig(mid)

        self.nv.book = wrapped
        self.run_at(NOW)
        self.assertEqual(S.triggers([g], NOW.timestamp()), [])
        self.assertEqual(trades_of(self.led), [])
        self.assertEqual(calls['book'], 0)

    def test_a_watched_game_does_not_fill_once_kickoff_has_passed(self):
        for k in (5.5, 6.5):
            self.nv.books[self.nv.mid(k)] = book(k, unm_bids=((0.58, 300),))
        self.run_at(NOW)
        self.assertEqual(self.game()['state'], 'watching')
        self.assertEqual(trades_of(self.led), [])
        for k in (5.5, 6.5):
            self.nv.books[self.nv.mid(k)] = book(k)
        self.run_at(KICK + timedelta(minutes=1))
        self.assertEqual(trades_of(self.led), [])
        self.assertEqual(self.game()['state'], 'closed')

    def test_try_entry_refuses_a_post_kick_or_final_price(self):
        for k in (5.5, 6.5):
            self.nv.books[self.nv.mid(k)] = book(k, unm_bids=((0.58, 300),))
        self.run_at(NOW)
        gs = self.game()
        q = {'bid': 0.40, 'ask': 0.42, 'bid_size': 200.0, 'ask_size': 800.0}
        stats = {'entered': 0}
        ctx = {'ledger': self.led, 'now': KICK, 'now_ts': KICK.timestamp(), 'notes': [],
               'by_key': {'cfb:1': board_game()}}
        self.strat._try_entry(ctx, gs, q, stats)
        self.assertEqual(stats['entered'], 0)
        self.assertEqual(trades_of(self.led), [])
        ctx['now'] = NOW
        ctx['now_ts'] = NOW.timestamp()
        ctx['by_key'] = {'cfb:1': board_game(result='W', hs=30, as_=10)}
        self.strat._try_entry(ctx, gs, q, stats)
        self.assertEqual(stats['entered'], 0)
        self.assertEqual(gs['state'], 'watching')
        ctx['by_key'] = {'cfb:1': board_game()}
        self.strat._try_entry(ctx, gs, q, stats)
        self.assertEqual(stats['entered'], 1)
        self.assertEqual(len(trades_of(self.led)), 1)
        self.assertLess(int(NOW.timestamp()), gs['kick'])


class GradingMath(unittest.TestCase):
    def trade(self, side, hcap, price=0.40, n=10):
        return {'strike': hcap, 'price': price, 'contracts': n, 'detail': {'jp_side': side}}

    def test_home_cover_loss_and_push(self):
        t = self.trade('home', 6.5)
        S.grade_hold(t, 20, 24)                  # lose by 4, +6.5 wins
        self.assertEqual((t['hold_result'], t['hold_pnl_pc']), ('win', 0.6))
        t = self.trade('home', -6.5)
        S.grade_hold(t, 20, 24)
        self.assertEqual((t['hold_result'], t['hold_pnl_pc'], t['hold_pnl']), ('loss', -0.4, -4.0))
        t = self.trade('home', -7.0)
        S.grade_hold(t, 27, 20)                  # won by exactly 7: refund
        self.assertEqual((t['hold_result'], t['hold_pnl_pc']), ('push', 0.0))

    def test_away_side_flips_the_margin(self):
        t = self.trade('away', -3.5)
        S.grade_hold(t, 10, 21)                  # away wins by 11
        self.assertEqual(t['hold_result'], 'win')
        t = self.trade('away', 3.5)
        S.grade_hold(t, 31, 20)                  # away loses by 11
        self.assertEqual(t['hold_result'], 'loss')

    def test_board_result_needs_a_graded_row(self):
        self.assertIsNone(S.board_result(board_game()))
        self.assertEqual(S.board_result(board_game(result='W', hs=3, as_=1)), (3.0, 1.0))
        self.assertIsNone(S.board_result(board_game(result='W', hs=3)))


class ExitRules(unittest.TestCase):
    def gs(self, snaps):
        return {'kick': 1000, 'novig': {'snaps': [S.snap_str(*s) for s in snaps]}}

    def row(self):
        return {'price': 0.42, 'contracts': 100, 'stake': 42.0}

    def test_last_bid_strictly_before_kick(self):
        g = self.gs([(100, 0.40, 0.42, 800, 200), (900, 0.45, 0.48, 500, 120), (1000, 0.55, 0.57, 500, 100), (1100, 0.9, 0.95, 5, 5)])
        t = self.row()
        S.apply_exit(t, g)
        self.assertEqual((t['exit_bid'], t['exit_gap_min']), (0.45, round(100 / 60, 1)))
        self.assertAlmostEqual(t['pnl'], 3.0)

    def test_skips_snapshots_with_no_bid(self):
        g = self.gs([(100, 0.40, 0.42, 800, 200), (900, None, 0.48, 500, None)])
        t = self.row()
        S.apply_exit(t, g)
        self.assertEqual(t['exit_bid'], 0.40)

    def test_a_loss_is_a_loss(self):
        g = self.gs([(900, 0.30, 0.34, 500, 500)])
        t = self.row()
        S.apply_exit(t, g)
        self.assertAlmostEqual(t['pnl'], -12.0)
        self.assertFalse(t['won'])


class PartialExit(unittest.TestCase):
    def gs(self, bid_size):
        return {'kick': 1000, 'novig': {'snaps': [S.snap_str(900, 0.50, 0.52, 500, bid_size)]}}

    def row(self, side='home', hcap=6.5):
        return {'price': 0.40, 'contracts': 100, 'stake': 40.0, 'strike': hcap, 'detail': {'jp_side': side}}

    def test_fills_only_the_bid_size_and_the_rest_is_held(self):
        t = self.row()
        S.apply_exit(t, self.gs(30))
        self.assertEqual((t['exit_filled_contracts'], t['exit_remainder_contracts'], t['exit_fill_frac']), (30, 70, 0.3))
        self.assertAlmostEqual(t['pnl'], 3.0)             # only the exit part is realized so far
        self.assertAlmostEqual(t['payout'], 15.0)
        self.assertIsNone(t['exit_pnl_pc'])               # not a pass-bar result until the remainder is graded
        self.assertTrue(t['remainder_pending'])

    def test_blended_pnl_and_payout_once_graded_win_loss_push(self):
        for hs, as_, res, pay_rem in ((20, 24, 'win', 70.0), (20, 40, 'loss', 0.0), (20, 26.5, 'push', 28.0)):
            t = self.row()
            S.apply_exit(t, self.gs(30))
            S.grade_hold(t, hs, as_)
            self.assertEqual(t['remainder_result'], res)
            self.assertAlmostEqual(t['payout'], 15.0 + pay_rem)
            self.assertAlmostEqual(t['pnl'], t['payout'] - 40.0)
            self.assertAlmostEqual(t['exit_pnl_pc'], round(t['pnl'] / 100, 5))
            self.assertFalse(t['remainder_pending'])

    def test_partly_exited_row_counts_as_pending_not_a_loss_in_by_source(self):
        t = self.row()
        t['source'] = S.STRATEGY
        S.apply_exit(t, self.gs(30))
        self.assertTrue(t['remainder_pending'])
        self.assertIsNone(t['won'])
        led = empty(1000)
        led['trades'] = [t]
        grp = summarize(led)['by_source'][S.STRATEGY]
        self.assertEqual((grp['pending'], grp['settled'], grp['wins'], grp['losses']), (1, 0, 0, 0))
        self.assertEqual((grp['stake'], grp['pnl'], grp['roi'], grp['brier']), (0.0, 0.0, None, None))
        S.grade_hold(t, 20, 40)         # remainder loses: now a graded loss
        grp = summarize(led)['by_source'][S.STRATEGY]
        self.assertEqual((grp['pending'], grp['settled'], grp['wins'], grp['losses']), (0, 1, 0, 1))

    def test_bid_larger_than_the_position_fills_everything(self):
        t = self.row()
        S.apply_exit(t, self.gs(900))
        self.assertEqual((t['exit_fill_frac'], t['exit_remainder_contracts']), (1.0, 0))
        self.assertAlmostEqual(t['pnl'], 10.0)
        S.grade_hold(t, 0, 50)                             # grading must not touch a fully exited row's blend
        self.assertAlmostEqual(t['pnl'], 10.0)

    def test_no_stored_bid_size_means_no_fill(self):
        t = self.row()
        g = {'kick': 1000, 'novig': {'snaps': ['900,0.5,0.52,500,']}}
        S.apply_exit(t, g)
        self.assertEqual((t['exit_filled_contracts'], t['exit_fill_frac']), (0, 0.0))
        S.grade_hold(t, 20, 40)
        self.assertAlmostEqual(t['pnl'], -40.0)

    def test_partial_rows_stay_out_of_the_pass_bar_until_graded(self):
        t = self.row()
        t.update({'source': S.STRATEGY, 'edge': 5.0, 'edge_bucket': '5+'})
        S.apply_exit(t, self.gs(30))
        self.assertEqual(S.build_progress([t])['pass_bar']['n'], 0)
        S.grade_hold(t, 20, 24)
        self.assertEqual(S.build_progress([t])['pass_bar']['n'], 1)


class SizingCaps(unittest.TestCase):
    def go(self, led, when, depth_qty=40000):
        with tempfile.TemporaryDirectory() as tmp:
            strat, nv = make(tmp)
            for k in (5.5, 6.5):
                nv.books[nv.mid(k)] = book(k, unm_bids=((0.58, depth_qty),))
            strat.run(led, when, None)
        return trades_of(led)

    def test_trade_cap_is_5_percent_of_bankroll_and_uncapped_is_logged(self):
        (t,) = self.go(ledger_with(), NOW)
        self.assertEqual((t['uncapped_contracts'], t['contracts'], t['capped_by']), (100, 100, None))   # 25% of 400
        (t,) = self.go(ledger_with(), NOW, depth_qty=400000)
        self.assertEqual((t['uncapped_contracts'], t['contracts'], t['capped_by']), (1000, 119, 'trade cap'))
        self.assertLessEqual(t['stake'], 50.0)
        self.assertAlmostEqual(t['uncapped_stake'], 420.0)

    def test_day_cap_counts_this_strategys_stakes_by_et_date_of_entry(self):
        led = ledger_with()
        led['trades'].append({'source': S.STRATEGY, 'status': 'open', 'stake': 120.0, 'ts': '2026-10-20T12:00:00Z'})
        led['trades'].append({'source': S.STRATEGY, 'status': 'open', 'stake': 90.0, 'ts': '2026-10-19T12:00:00Z'})   # another ET day
        led['trades'].append({'source': 'other', 'status': 'open', 'stake': 90.0, 'ts': '2026-10-20T12:00:00Z'})
        t = self.go(led, NOW, depth_qty=400000)[-1]
        self.assertEqual((t['contracts'], t['capped_by']), (71, 'day cap'))     # $30 left / 0.42
        self.assertLessEqual(t['stake'], 30.0)

    def test_day_cap_uses_the_et_date_not_utc(self):
        led = ledger_with()
        led['trades'].append({'source': S.STRATEGY, 'status': 'open', 'stake': 150.0, 'ts': '2026-10-20T23:30:00Z'})   # 19:30 ET Oct 20
        late = datetime(2026, 10, 21, 2, 0, tzinfo=UTC)                                  # 22:00 ET Oct 20: same ET day
        self.assertEqual(len(self.go(led, late)), 1)                                      # only the seeded row, no new entry
        fresh = datetime(2026, 10, 21, 5, 0, tzinfo=UTC)                                  # 01:00 ET Oct 21: new day
        self.assertEqual(len(self.go(led, fresh)), 2)


class StrikeLabel(unittest.TestCase):
    """Hawaii +15.5 vs +6.5: Hawaii is the home underdog at -(-15.5), so the open is +15.5 for them."""

    def test_home_underdog_label_and_strike_are_the_open_handicap(self):
        g = board_game(model_margin=-8.2, open_margin=-15.5)
        (c,) = S.triggers([g], NOW.timestamp())
        self.assertEqual((c['side'], c['open_hcap']), ('home', 15.5))
        ladder = S.spread_ladder([spread_market(k) for k in (6.5, 7.5, 14.5, 15.5, 16.5)])
        pick = S.choose_strike(ladder, 'HAW', c['open_hcap'])
        self.assertEqual(pick['hcap'], 15.5)
        self.assertEqual(pick['outcome_id'], f'{HAW_OUT}-15.5')

    def test_the_trade_is_titled_from_the_strike_it_actually_trades(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat, nv = make(tmp, board=[board_game(model_margin=-8.2, open_margin=-15.5)],
                             novig=FakeNovig(strikes=(6.5, 7.5, 14.5, 15.5, 16.5)))
            led = ledger_with()
            strat.run(led, NOW, None)
            (t,) = trades_of(led)
            self.assertEqual((t['title'], t['strike'], t['detail']['open_hcap']), ('Hawaii +15.5', 15.5, 15.5))
            self.assertTrue(t['ticker'].endswith(f'{HAW_OUT}-15.5'))

    def test_a_ladder_missing_the_open_strike_trades_the_nearest_and_records_the_distance(self):
        # strikes only up to 6.5 are listed: the nearest to +15.5 is +6.5, 9 points off. The distance is stored.
        with tempfile.TemporaryDirectory() as tmp:
            strat, nv = make(tmp, board=[board_game(model_margin=-8.2, open_margin=-15.5)],
                             novig=FakeNovig(strikes=(4.5, 5.5, 6.5)))
            led = ledger_with()
            strat.run(led, NOW, None)
            (t,) = trades_of(led)
            self.assertEqual((t['strike'], t['detail']['strike_distance']), (6.5, 9.0))

    def test_strike_distance_is_on_the_trade_row_and_in_the_watchlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat, nv = make(tmp, board=[board_game(model_margin=-8.2, open_margin=-15.5)],
                             novig=FakeNovig(strikes=(4.5, 5.5, 6.5)))
            led = ledger_with()
            strat.run(led, NOW, None)
            (t,) = trades_of(led)
            self.assertEqual(t['strike_distance'], 9.0)
            (w,) = led['strategies'][S.STRATEGY]['watch']
            self.assertEqual(w['strike_distance'], 9.0)


class PassBar(unittest.TestCase):
    def rows(self, pcs, edge=5.0, status='settled'):
        return [{'source': S.STRATEGY, 'status': status, 'edge': edge, 'exit_pnl_pc': v, 'hold_status': 'pending'} for v in pcs]

    def test_mean_and_z(self):
        m = S.mean_z([0.02, 0.04, 0.06])
        self.assertAlmostEqual(m['mean'], 0.04)
        self.assertAlmostEqual(m['sd'], 0.02)
        self.assertAlmostEqual(m['z'], round(0.04 / (0.02 / math.sqrt(3)), 3))
        self.assertIsNone(S.mean_z([0.1])['z'])
        self.assertIsNone(S.mean_z([0.1, 0.1, 0.1])['z'])       # no spread: z is undefined, not infinite
        self.assertEqual(S.mean_z([])['n'], 0)

    def test_progress_counts_only_5_plus_exits(self):
        rows = self.rows([0.05, 0.03] * 5) + self.rows([0.5] * 4, edge=3.5) + self.rows([0.2] * 2, edge=8.0, status='open')
        pb = S.build_progress(rows)['pass_bar']
        self.assertEqual((pb['n'], pb['n_needed'], pb['to_go'], pb['status']), (10, 60, 50, 'collecting'))
        self.assertAlmostEqual(pb['mean'], 0.04)

    def test_slices_are_cumulative(self):
        rows = self.rows([0.01] * 3, edge=3.5) + self.rows([0.01] * 2, edge=5.5) + self.rows([0.01], edge=7.5)
        sl = S.build_progress(rows)['slices']
        self.assertEqual((sl['3+']['exit']['n'], sl['5+']['exit']['n'], sl['7+']['exit']['n']), (6, 3, 1))

    def test_status_needs_60_trades_positive_mean_and_z_2(self):
        good = [0.06, 0.02] * 30
        self.assertEqual(S.pass_status(S.mean_z(good[:59])), 'collecting')
        self.assertEqual(S.pass_status(S.mean_z(good)), 'pass')
        self.assertEqual(S.pass_status(S.mean_z([0.01, -0.01] * 30)), 'fail')          # mean 0
        self.assertEqual(S.pass_status(S.mean_z([-0.02, -0.04] * 30)), 'fail')         # negative
        noisy = [0.30, -0.26] * 30                                                   # mean +0.02 but z far under 2
        self.assertGreater(S.mean_z(noisy)['mean'], 0)
        self.assertLess(S.mean_z(noisy)['z'], 2)
        self.assertEqual(S.pass_status(S.mean_z(noisy)), 'fail')

    def test_exactly_at_the_z_bar_passes(self):
        vals = [0.05 + (0.01 if i % 2 else -0.01) for i in range(60)]
        stats = S.mean_z(vals)
        self.assertGreaterEqual(stats['z'], 2.0)
        self.assertEqual(S.pass_status(stats), 'pass')

    def test_void_rows_are_not_in_the_sample_and_are_counted(self):
        rows = self.rows([0.05] * 3)
        rows.append({'source': S.STRATEGY, 'status': 'void', 'void_reason': 'no_exit_bid', 'edge': 6.0, 'exit_pnl_pc': None,
                     'hold_status': 'graded', 'hold_pnl_pc': 0.5})
        out = S.build_progress(rows)
        self.assertEqual(out['pass_bar']['n'], 3)
        self.assertEqual(out['counts']['no_exit_bid'], 1)
        self.assertEqual(out['slices']['5+']['hold']['n'], 1)

    def test_other_sources_are_ignored(self):
        rows = self.rows([0.05] * 3) + [{'source': 'cfb_ml', 'status': 'settled', 'edge': 9.0, 'exit_pnl_pc': 1.0}]
        self.assertEqual(S.build_progress(rows)['pass_bar']['n'], 3)

    def test_improving_record_is_flagged_with_its_sample_size(self):
        prev = S.build_progress(self.rows([0.01, 0.03]))
        out = S.build_progress(self.rows([0.01, 0.03, 0.09]), prev)
        self.assertTrue(out['monitor']['improving'])
        self.assertEqual(out['monitor']['n'], 3)
        self.assertIn('n=3', out['monitor']['note'])
        again = S.build_progress(self.rows([0.01, 0.03, 0.09]), out)
        self.assertFalse(again['monitor']['improving'])


class EdgeThresholds(unittest.TestCase):
    def test_compare_before_rounding(self):
        # 4.96 points rounds to 5.0 but has not reached 5
        e, _ = S.jp_edge({'model_margin': 4.96, 'open_margin': 0.0})
        self.assertLess(e, 5.0)
        self.assertEqual(S.bucket_of(e), '3+')
        e, _ = S.jp_edge({'model_margin': 2.96, 'open_margin': -2.04})
        self.assertEqual(S.bucket_of(e), '5+')           # exactly 5.0 up to float noise
        e, _ = S.jp_edge({'model_margin': 2.99, 'open_margin': -0.0})
        self.assertIsNone(S.bucket_of(e))                # 2.99 is not 3
        e, _ = S.jp_edge({'model_margin': 6.97, 'open_margin': 0.0})
        self.assertEqual(S.bucket_of(e), '5+')
        self.assertIsNone(S.jp_edge({'model_margin': 1.0, 'open_margin': 1.0}))

    def test_slices_follow_the_logged_bucket(self):
        t = {'source': S.STRATEGY, 'status': 'open', 'edge': 5.0, 'edge_bucket': '3+'}   # 4.96 stored as 5.0
        self.assertEqual(S.build_progress([t])['slices']['5+']['entered'], 0)
        self.assertEqual(S.build_progress([t])['slices']['3+']['entered'], 1)


class KalshiPushes(unittest.TestCase):
    def find(self, floor, team_side='home'):
        game = {'home': 'Hawaii', 'away': 'New Mexico', 'kick': KICK.timestamp(), 'home_id': 62, 'away_id': 167}
        rows = [kalshi_row('New Mexico', 6.5, 0.5, 0.53), kalshi_row('New Mexico', 7.0, 0.5, 0.53),
                kalshi_row('Hawaii', 7.0, 0.1, 0.14)]
        return S.kalshi_find(rows, game, S._rating_index(ratings()), floor, team_side)

    def test_integer_strike_is_flagged_as_not_the_same_bet(self):
        # Novig refunds at exactly 7. Kalshi NO on "wins by over 7" wins at exactly 7, and YES loses.
        no = self.find(7.0)
        self.assertEqual((no['side'], no['floor'], no['push_mismatch']), ('no', 7.0, True))
        yes = self.find(-7.0)
        self.assertEqual((yes['side'], yes['push_mismatch']), ('yes', True))

    def test_half_point_strike_is_like_for_like(self):
        self.assertFalse(self.find(6.5)['push_mismatch'])

    def test_pick_em_has_no_kalshi_equivalent(self):
        self.assertTrue(self.find(0.0)['push_mismatch'])
        self.assertIsNone(self.find(0.0)['quote'])


class MalformedSnapshots(unittest.TestCase):
    def test_bad_snapshot_is_skipped_with_a_note_and_the_run_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat, nv = make(tmp)
            led = ledger_with()
            strat.run(led, NOW, None)
            gs = led['strategies'][S.STRATEGY]['games']['cfb:1']
            gs['novig']['snaps'].insert(0, 'bad,snap')
            gs['kalshi']['snaps'].append('also,bad')
            note = strat.run(led, NOW + timedelta(minutes=30), None)
            self.assertIn('malformed snapshot', note)
            self.assertEqual(len(trades_of(led)), 1)
            self.assertEqual(len(gs['novig']['snaps']), 3)      # new one added, nothing deleted
            self.assertEqual(led['strategies'][S.STRATEGY]['watch'][0]['novig_snaps'], 3)

    def test_exit_ignores_a_malformed_snapshot(self):
        t = {'price': 0.42, 'contracts': 10, 'stake': 4.2}
        g = {'kick': 1000, 'novig': {'snaps': ['bad,snap', S.snap_str(900, 0.45, 0.5, 100, 100)]}}
        S.apply_exit(t, g)
        self.assertEqual(t['exit_bid'], 0.45)

    def test_prune_keeps_unreadable_rows(self):
        gs = {'kick': 10_000_000, 'entry_ts': None,
              'novig': {'snaps': [S.snap_str(1, 0.4, 0.5, 9, 9), 'bad,snap']}, 'kalshi': {'snaps': []}}
        CfbJp = S.CfbJpNovig({}, '.')
        CfbJp._prune(gs)
        self.assertIn('bad,snap', gs['novig']['snaps'])


class Guards(unittest.TestCase):
    def test_novig_outage_is_a_note_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat, nv = make(tmp, novig=FakeNovig(fail=True))
            led = ledger_with()
            note = strat.run(led, NOW, FakeKalshi())
            self.assertIn('Novig events unavailable', note)
            self.assertEqual(trades_of(led), [])

    def test_real_client_returns_empty_on_errors(self):
        class Boom:
            def pages(self, *a, **k):
                raise OSError('curl missing')

            def get(self, *a, **k):
                raise OSError('curl missing')
        c = NovigPublic(module=Boom())
        self.assertEqual(c.events(), [])
        self.assertEqual(c.markets('x'), [])
        self.assertIsNone(c.book('x'))
        self.assertEqual(c.errors, 3)

    def test_request_budget_caps_a_run(self):
        class Ok:
            def get(self, *a, **k):
                return {'orders': {}}
        c = NovigPublic(module=Ok(), budget=2)
        self.assertEqual([c.book('a') is not None, c.book('b') is not None, c.book('c') is not None], [True, True, False])

    def test_kalshi_failure_does_not_stop_novig_tracking(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat, nv = make(tmp)
            led = ledger_with()
            strat.run(led, NOW, FakeKalshi(fail=True))
            self.assertEqual(len(trades_of(led)), 1)
            self.assertEqual(led['strategies'][S.STRATEGY]['games']['cfb:1']['kalshi']['snaps'], [])

    def test_unreadable_model_is_a_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat = S.CfbJpNovig({}, tmp, novig=FakeNovig())
            self.assertIn('missing', strat.run(ledger_with(), NOW, None))

    def test_uuid7_time_and_parse_outcome(self):
        self.assertEqual(uuid7_ms(uuid7(1_790_000_123_456)), 1_790_000_123_456)
        self.assertIsNone(uuid7_ms('nope'))
        self.assertEqual(parse_outcome('UNM -8.5'), ('UNM', -8.5))
        self.assertEqual(parse_outcome('HAW +8.5'), ('HAW', 8.5))
        self.assertIsNone(parse_outcome('Over 55.5'))


class EngineWiring(unittest.TestCase):
    def engine(self, tmp, strat):
        cfg = load(None)
        led = ledger_with()
        return Engine(cfg, led, [], FakeKalshi(), None, now=NOW, strategies=[strat]), led

    def test_novig_book_stays_out_of_cash_caps_and_equity(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat, _ = make(tmp)
            eng, led = self.engine(tmp, strat)
            run = eng.run()
            self.assertEqual(len(trades_of(led)), 1)
            self.assertEqual(led['cash'], 1000.0)
            self.assertEqual(run['equity'], 1000.0)
            self.assertEqual(recompute_cash(led), 1000.0)
            self.assertEqual(led['summary']['overall']['open'], 0)
            self.assertEqual(led['summary']['by_source'][S.STRATEGY]['open'], 1)
            self.assertEqual(led['summary']['strategies'][S.STRATEGY]['pass_bar']['status'], 'collecting')
            self.assertEqual(led['strategies'][S.STRATEGY]['progress']['pass_bar']['n_needed'], 60)

    def test_a_crashing_strategy_cannot_stop_the_bot(self):
        class Bad:
            name = 'bad'

            def run(self, *a):
                raise ValueError('boom')
        with tempfile.TemporaryDirectory() as tmp:
            eng, led = self.engine(tmp, Bad())
            run = eng.run()
            self.assertTrue(any('bad failed' in n for n in run['notes']))
            self.assertEqual(led['cash'], 1000.0)

    def test_only_mode_leaves_equity_and_runs_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat, _ = make(tmp)
            eng, led = self.engine(tmp, strat)
            eng.run_strategies_only()
            self.assertEqual(led['equity'], [])
            self.assertEqual(led['runs'], [])
            self.assertEqual(len(trades_of(led)), 1)

    def test_kill_switch_stops_strategies_on_both_paths(self):
        for only in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                strat, _ = make(tmp)
                cfg = load(None)
                cfg['kill_switch'] = True
                led = ledger_with()
                eng = Engine(cfg, led, [], FakeKalshi(), None, now=NOW, strategies=[strat])
                run = eng.run_strategies_only() if only else eng.run()
                self.assertEqual(trades_of(led), [])
                self.assertNotIn('strategies', led)
                self.assertTrue(any('kill switch' in n for n in run['notes']))

    def test_strategies_run_when_not_halted(self):
        with tempfile.TemporaryDirectory() as tmp:
            strat, _ = make(tmp)
            eng, led = self.engine(tmp, strat)
            eng.run_strategies_only()
            self.assertEqual(len(trades_of(led)), 1)

    def test_novig_rows_do_not_block_kalshi_tickers(self):
        from scripts.paper_bot.ledger import held_tickers
        led = ledger_with()
        led['trades'] += [{'status': 'open', 'ticker': 'novig:m:o'}, {'status': 'open', 'ticker': 'KXNBA-1'}]
        self.assertEqual(held_tickers(led), {'KXNBA-1'})

    def test_config_toggle(self):
        cfg = load(None)
        self.assertIsNotNone(S.build(cfg, '.'))
        cfg['sources']['cfb_jp_novig']['enabled'] = False
        self.assertIsNone(S.build(cfg, '.'))

    def test_existing_kalshi_rows_still_count(self):
        led = ledger_with()
        led['trades'].append({'status': 'open', 'stake': 25.0, 'ticker': 'K', 'ts': '2026-10-20T12:00:00Z', 'mark_value': 25.0})
        led['trades'].append({'status': 'open', 'stake': 80.0, 'ticker': 'novig:x', 'book': 'novig', 'source': S.STRATEGY,
                              'ts': '2026-10-20T12:00:00Z'})
        self.assertEqual(recompute_cash(led), 975.0)
        summarize(led)
        self.assertEqual(led['summary']['overall']['open'], 1)


if __name__ == '__main__':
    unittest.main()
