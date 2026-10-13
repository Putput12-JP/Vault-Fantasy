"""One paper-bot run: settle, mark, size, simulate the fill, record it.

The only broker this process uses is the fill written into the ledger. It does
not import the live broker, and it will not run when paper_only is false.
"""
import argparse
import math
from datetime import datetime, timezone

from . import cfb_jp_novig
from .config import load
from .fees import cost_cents, taker_fee
from .http_json import get_json
from .kalshi_public import KalshiPublic
from .kelly import contracts_for
from .ledger import (
    day_pnl, held_tickers, tag_pre_fix_trades, iso, load as load_ledger, open_mark,
    recompute_cash, record_equity, save, spent_buckets, summarize,
)
from .llm_filter import LlmFilter
from .quotes import settlement_of, side_bid, side_mid
from .signals import load_sources


def log(msg):
    print('[paper-bot]', msg, flush=True)


class Engine:
    def __init__(self, cfg, ledger, sources, kalshi, llm, now=None, strategies=None):
        self.cfg = cfg
        self.ledger = ledger
        self.sources = sources
        self.kalshi = kalshi
        self.llm = llm
        self.now = now or datetime.now(timezone.utc)
        self.notes = []
        self.strategies = strategies or []

    def run(self):
        for w in self.cfg.get('config_warnings') or []:
            self.notes.append('warning: ' + w)
        recompute_cash(self.ledger)
        tagged = tag_pre_fix_trades(self.ledger)
        if tagged:
            self.notes.append(f'tagged {tagged} pre-fix CFB trades pre_fix_raw_v1_margin')
        quotes = self._quotes_for_open()
        settled = self._settle(quotes)
        self._mark(quotes)
        self._run_strategies()
        halt, why = self._halted()
        opened = vetoed = skipped = 0
        if halt:
            self.notes.append(why)
        else:
            proposals = self._collect()
            proposals.sort(key=lambda p: -float(p.get('edge') or 0))
            held = held_tickers(self.ledger)
            for p in proposals:
                if p['ticker'] in held:
                    skipped += 1
                    continue
                result = self._open(p)
                held.add(p['ticker'])
                if result == 'opened':
                    opened += 1
                elif result == 'vetoed':
                    vetoed += 1
                else:
                    skipped += 1
            if skipped:
                self.notes.append(f'{skipped} proposals were already on the ledger or came in under the size caps')
        point = record_equity(self.ledger, self.now)
        self.ledger['config'] = _public_config(self.cfg)
        self.ledger['updated'] = iso(self.now)
        self.ledger['live_orders'] = False
        self.ledger['paper_only'] = True
        run = {
            'ts': iso(self.now),
            'settled': settled,
            'opened': opened,
            'vetoed': vetoed,
            'skipped': skipped,
            'halt': why if halt else None,
            'notes': self.notes,
            'equity': point['equity'],
            'cash': point['cash'],
        }
        self.ledger['runs'].append(run)
        if len(self.ledger['runs']) > 200:
            self.ledger['runs'] = self.ledger['runs'][-200:]
        summarize(self.ledger)
        return run

    def _run_strategies(self):
        """Separate paper books (own rows, own accounting). A failure is a run note, never a crash."""
        for s in self.strategies:
            try:
                note = s.run(self.ledger, self.now, self.kalshi)
            except Exception as e:
                note = f'{getattr(s, "name", "strategy")} failed: {str(e)[:180]}'
            if note:
                self.notes.append(note)

    def run_strategies_only(self):
        """The 30-minute pass: snapshots, entries, exits and grading for the strategies, nothing else.

        It does not touch the Kalshi book, the equity curve or the run log, so frequent runs cannot
        crowd out the scheduled runs' history.
        """
        self._run_strategies()
        self.ledger['config'] = _public_config(self.cfg)
        self.ledger['updated'] = iso(self.now)
        self.ledger['live_orders'] = False
        self.ledger['paper_only'] = True
        summarize(self.ledger)
        return {'ts': iso(self.now), 'notes': self.notes}

    def _quotes_for_open(self):
        tickers = [t['ticker'] for t in self.ledger['trades']
                   if t.get('status') == 'open' and t.get('ticker') and not t.get('book')]
        if not tickers:
            return {}
        try:
            return self.kalshi.markets_by_ticker(tickers)
        except Exception as e:
            self.notes.append('could not refresh open markets: ' + str(e)[:180])
            return {}

    def _settle(self, quotes):
        n = 0
        for t in self.ledger['trades']:
            if t.get('status') != 'open' or t.get('book'):
                continue
            q = quotes.get(t['ticker'])
            if not q:
                continue
            outcome = settlement_of(q)
            if outcome is None:
                continue
            t['result'] = outcome
            t['settled_ts'] = iso(self.now)
            if outcome == 'void':
                t['status'] = 'void'
                t['payout'] = t['stake']
                t['pnl'] = 0.0
                t['won'] = None
            else:
                won = outcome == t['side']
                t['status'] = 'settled'
                t['won'] = won
                t['payout'] = round(t['contracts'] * (1.0 if won else 0.0), 2)
                t['pnl'] = round(t['payout'] - float(t['stake']), 2)
            if t.get('close_mid') is not None and t['status'] == 'settled':
                t['clv'] = round(float(t['close_mid']) - float(t['price']), 4)
            n += 1
        return n

    def _mark(self, quotes):
        stamp = iso(self.now)
        for t in self.ledger['trades']:
            if t.get('status') != 'open' or t.get('book'):
                continue
            q = quotes.get(t['ticker'])
            if not q:
                if t.get('mark_value') is None:
                    t['mark_value'] = t['stake']
                continue
            t['mark_value'] = round(float(t['contracts']) * side_bid(q, t['side']), 2)
            t['mark_ts'] = stamp
            # A quote from the run that opened the trade is the entry, not a close.
            if t.get('ts') != stamp:
                t['close_mid'] = round(side_mid(q, t['side']), 4)

    def _halted(self):
        if self.cfg.get('kill_switch'):
            return True, 'kill switch is on'
        pnl = day_pnl(self.ledger, self.now)
        stop = float(self.cfg['daily_loss_stop'])
        if pnl <= -stop:
            return True, f'daily loss stop ({pnl:.2f} vs -{stop:.2f})'
        return False, None

    def _collect(self):
        proposals = []
        for src in self.sources:
            try:
                found, note = src.collect(self.kalshi, self.now)
            except Exception as e:
                self.notes.append(f'{getattr(src, "name", "source")}: {e}'[:200])
                continue
            if note:
                self.notes.append(note)
            proposals.extend(found or [])
        if self.llm is not None:
            self.notes.append(self.llm.status_note())
        return proposals

    def _open(self, p):
        price = float(p['price'])
        prob = float(p['model_prob'])
        if not (math.isfinite(price) and math.isfinite(prob) and math.isfinite(float(p.get('edge') or 0))):
            return 'non-finite signal'
        fee = taker_fee(price)
        if prob <= price + fee:
            return 'no edge after fees'
        decision = self.llm.review(p) if self.llm is not None else None
        if decision is not None and decision.veto:
            if decision.definitive:
                self.ledger['trades'].append(_row(p, self.now, status='vetoed', contracts=0, stake=0,
                                                   fee=fee, prob=prob, llm=decision.as_dict(), bankroll=self.ledger['cash']))
                return 'vetoed'
            self.notes.append(f"skipped {p['ticker']}: {decision.reason}")
            return 'filter'
        bankroll = float(self.ledger['cash']) + open_mark(self.ledger)
        spent = spent_buckets(self.ledger, self.now, p['ticker'], p['event'])
        spent['ask_size'] = p.get('ask_size')
        n, reason = contracts_for(bankroll, prob, price, fee, self.cfg, spent)
        cents = cost_cents(price)
        if cents > 0:
            n = min(n, int(float(self.ledger['cash']) * 100) // cents)
        if n < 1:
            return reason or 'size'
        stake = round(n * cents / 100, 2)
        q_bid = p['yes_bid'] if p['side'] == 'yes' else p.get('no_bid', round(1 - p['yes_ask'], 4))
        row = _row(p, self.now, status='open', contracts=n, stake=stake, fee=fee, prob=prob,
                   llm=(decision.as_dict() if decision else {'enabled': False, 'veto': False, 'reason': 'filter off'}),
                   bankroll=bankroll)
        row['mark_value'] = round(n * float(q_bid), 2)
        row['fee_total'] = round(n * fee, 2)
        self.ledger['trades'].append(row)
        self.ledger['cash'] = round(float(self.ledger['cash']) - stake, 2)
        return 'opened'


def _row(p, now, status, contracts, stake, fee, prob, llm, bankroll):
    return {
        'id': f"{p['ticker']}:{int(now.timestamp())}",
        'ts': iso(now),
        'status': status,
        'source': p.get('source'),
        'ticker': p.get('ticker'),
        'event': p.get('event'),
        'title': p.get('title'),
        'game': p.get('game'),
        'side': p.get('side'),
        'strike': p.get('strike'),
        'model_prob': round(float(prob), 4),
        'edge': p.get('edge'),
        'yes_bid': p.get('yes_bid'),
        'yes_ask': p.get('yes_ask'),
        'price': p.get('price'),
        'fee_per': fee,
        'contracts': contracts,
        'stake': stake,
        'ask_size': p.get('ask_size'),
        'bankroll_before': round(float(bankroll), 2),
        'detail': p.get('detail') or {},
        'llm': llm,
        'settled_ts': None,
        'result': None,
        'payout': None,
        'pnl': None,
        'close_mid': None,
        'clv': None,
        'mark_value': None,
        'won': None,
    }


def _public_config(cfg):
    keep = ('paper_only', 'kill_switch', 'bankroll_start', 'kelly_fraction', 'min_edge',
            'max_edge', 'max_model_market_gap', 'min_price', 'max_price', 'max_spread', 'max_stake_per_trade', 'max_fraction_per_trade',
            'max_stake_per_day', 'max_stake_per_market', 'max_stake_per_event', 'daily_loss_stop',
            'monthly_cost_target')
    out = {k: cfg.get(k) for k in keep}
    out['sources'] = {name: {'enabled': bool((sc or {}).get('enabled', True)),
                             'min_edge': (None if name == cfb_jp_novig.STRATEGY
                                          else (sc or {}).get('min_edge', cfg.get('min_edge')))}
                      for name, sc in (cfg.get('sources') or {}).items()}
    llm = cfg.get('llm_filter') or {}
    out['llm_filter'] = {'enabled': bool(llm.get('enabled')), 'model': llm.get('model')}
    out['live_orders'] = False
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='Vault paper Kalshi bot. Never places an order.')
    ap.add_argument('--ledger', default='paper-out/ledger.json')
    ap.add_argument('--config', default='paper-bot/config.json')
    ap.add_argument('--root', default='.')
    ap.add_argument('--only', choices=[cfb_jp_novig.STRATEGY], help='run just this strategy (the 30-minute snapshot pass)')
    ap.add_argument('--dry', action='store_true', help='run the scan, print the summary, do not write the ledger')
    args = ap.parse_args(argv)
    cfg = load(args.config)
    ledger = load_ledger(args.ledger, cfg['bankroll_start'])
    sources = load_sources(cfg, args.root)
    llm = LlmFilter(cfg)
    strategies = [s for s in (cfb_jp_novig.build(cfg, args.root, get=get_json),) if s is not None]
    if args.only:
        strategies = [s for s in strategies if s.name == args.only]
        engine = Engine(cfg, ledger, [], KalshiPublic(), None, strategies=strategies)
        run = engine.run_strategies_only()
        for note in run['notes']:
            log(note)
        if args.dry:
            log('dry run: ledger not written')
        else:
            save(args.ledger, ledger)
            log('wrote ' + args.ledger)
        return 0
    engine = Engine(cfg, ledger, sources, KalshiPublic(), llm, strategies=strategies)
    run = engine.run()
    log(f"opened {run['opened']}  settled {run['settled']}  vetoed {run['vetoed']}  "
        f"cash ${run['cash']:.2f}  equity ${run['equity']:.2f}")
    for note in run['notes']:
        log(note)
    if run['halt']:
        log(run['halt'])
    if args.dry:
        log('dry run: ledger not written')
    else:
        save(args.ledger, ledger)
        log('wrote ' + args.ledger)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
