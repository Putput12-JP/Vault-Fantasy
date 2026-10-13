"""Base-ledger loading (scripts/paper_bot/load_base.py, ledger.build_base_ledger). No network.

Run from the repo root: python3 tests/test_load_base.py
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.paper_bot import load_base
from scripts.paper_bot.ledger import build_base_ledger, empty, held_tickers


def row(ticker, status='open', ts='2026-10-20T12:00:00Z', **kw):
    t = {'id': f'{ticker}:1', 'ticker': ticker, 'ts': ts, 'status': status, 'source': 'nba_total', 'stake': 1.0,
         'contracts': 2, 'price': 0.5, 'side': 'yes'}
    t.update(kw)
    return t


def ledger(updated, *rows):
    led = empty(1000)
    led['updated'] = updated
    led['trades'] = list(rows)
    return led


def tickers(led):
    return sorted(t['ticker'] for t in led['trades'])


class FailedPublishScenario(unittest.TestCase):
    def setUp(self):
        self.published = ledger('2026-10-20T12:00:00Z', row('P1'), row('P2'))
        # Kalshi run: every push failed, so its rows live only in artifact A.
        self.a = ledger('2026-10-20T13:00:00Z', row('P1'), row('P2'), row('K1'), row('K2'))
        # A snapshot run that started before A finished uploads the newer artifact B, built from P.
        self.b = ledger('2026-10-20T13:30:00Z', row('P1'), row('P2'))

    def test_merge_keeps_every_row_and_held_ticker(self):
        base = build_base_ledger(self.published, [self.a, self.b])
        self.assertEqual(tickers(base), ['K1', 'K2', 'P1', 'P2'])
        self.assertEqual(held_tickers(base), {'P1', 'P2', 'K1', 'K2'})

    def test_order_of_artifacts_does_not_matter(self):
        base = build_base_ledger(self.published, [self.b, self.a])
        self.assertEqual(held_tickers(base), {'P1', 'P2', 'K1', 'K2'})

    def test_the_more_advanced_row_wins(self):
        settled = ledger('2026-10-20T14:00:00Z', row('P1', status='settled', won=True, payout=2.0, pnl=1.0,
                                                    settled_ts='2026-10-20T14:00:00Z'))
        base = build_base_ledger(self.published, [self.a, settled])
        (p1,) = [t for t in base['trades'] if t['ticker'] == 'P1']
        self.assertEqual(p1['status'], 'settled')

    def test_none_when_nothing_exists(self):
        self.assertIsNone(build_base_ledger(None, []))
        self.assertIsNone(build_base_ledger(None, [None]))

    def test_inputs_are_not_modified(self):
        before = json.dumps(self.published, sort_keys=True)
        build_base_ledger(self.published, [self.a, self.b])
        self.assertEqual(json.dumps(self.published, sort_keys=True), before)


class Cli(unittest.TestCase):
    def write(self, path, obj):
        with open(path, 'w') as f:
            if isinstance(obj, str):
                f.write(obj)
            else:
                json.dump(obj, f)

    def test_cli_merges_published_and_recovered_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = os.path.join(tmp, 'ledgers')
            os.makedirs(rec)
            pub, out = os.path.join(tmp, 'published.json'), os.path.join(tmp, 'out', 'ledger.json')
            self.write(pub, ledger('2026-10-20T12:00:00Z', row('P1')))
            self.write(os.path.join(rec, '100.json'), ledger('2026-10-20T13:00:00Z', row('P1'), row('K1')))
            self.write(os.path.join(rec, '101.json'), ledger('2026-10-20T13:30:00Z', row('P1')))
            self.write(os.path.join(rec, '102.json'), '')       # empty: skipped
            self.assertEqual(load_base.main(['--published', pub, '--recovered-dir', rec, '--out', out]), 0)
            with open(out) as f:
                self.assertEqual(tickers(json.load(f)), ['K1', 'P1'])

    def test_cli_rejects_a_non_ledger_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = os.path.join(tmp, 'ledgers')
            os.makedirs(rec)
            pub, out = os.path.join(tmp, 'published.json'), os.path.join(tmp, 'ledger.json')
            self.write(pub, {'hello': 'world'})
            self.assertEqual(load_base.main(['--published', pub, '--recovered-dir', rec, '--out', out]), 2)
            self.assertFalse(os.path.exists(out))

    def test_cli_skips_a_bad_recovered_file_with_a_warning(self):
        for name, bad in (('truncated.json', '{"trades": [tru'), ('notledger.json', '{"x":1}')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                rec = os.path.join(tmp, 'ledgers')
                os.makedirs(rec)
                pub, out = os.path.join(tmp, 'published.json'), os.path.join(tmp, 'out', 'ledger.json')
                self.write(pub, ledger('2026-10-20T12:00:00Z', row('P1')))
                self.write(os.path.join(rec, '100.json'), ledger('2026-10-20T13:00:00Z', row('P1'), row('K1')))
                self.write(os.path.join(rec, name), bad)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = load_base.main(['--published', pub, '--recovered-dir', rec, '--out', out])
                self.assertEqual(code, 0)
                with open(out) as f:
                    self.assertEqual(tickers(json.load(f)), ['K1', 'P1'])
                warnings = [l for l in buf.getvalue().splitlines() if l.startswith('::warning title=Paper bot ledger::')]
                self.assertEqual(len(warnings), 1)
                self.assertIn(f'Skipped recovered ledger {os.path.join(rec, name)}:', warnings[0])

    def test_cli_with_nothing_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'ledger.json')
            self.assertEqual(load_base.main(['--published', os.path.join(tmp, 'none.json'),
                                             '--recovered-dir', os.path.join(tmp, 'nodir'), '--out', out]), 0)
            self.assertFalse(os.path.exists(out))


if __name__ == '__main__':
    unittest.main()
