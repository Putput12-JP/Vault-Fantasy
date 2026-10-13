"""The paper ledger: trades, cash, equity, and the scoreboard the page reads.

Cash is recomputed from the trades on every run, so a crashed write cannot
leave the bankroll ahead of the fills.
"""
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')


def iso(now):
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def et_day(stamp):
    """YYYY-MM-DD in America/New_York from an ISO stamp or a datetime."""
    if isinstance(stamp, datetime):
        dt = stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    return dt.astimezone(ET).date().isoformat()


def et_month(stamp):
    return et_day(stamp)[:7]


def in_cash_book(t):
    """False for rows of a separate paper book (book='novig'). They never touch cash, caps, the loss stop or equity."""
    return not t.get('book')


def empty(bankroll):
    return {
        'version': 1,
        'paper_only': True,
        'live_orders': False,
        'updated': None,
        'bankroll_start': round(float(bankroll), 2),
        'cash': round(float(bankroll), 2),
        'trades': [],
        'equity': [],
        'runs': [],
        'summary': {},
        'config': {},
    }


def load(path, bankroll):
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return empty(bankroll)
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get('trades'), list):
        raise SystemExit(f'ledger at {path} is not a paper-bot ledger')
    data.setdefault('equity', [])
    data.setdefault('runs', [])
    data.setdefault('paper_only', True)
    data['live_orders'] = False
    data['bankroll_start'] = round(float(data.get('bankroll_start', bankroll)), 2)
    return data


def save(path, ledger):
    if not path:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(ledger, f, indent=1)
        f.write('\n')
    os.replace(tmp, path)


def recompute_cash(ledger):
    cash = float(ledger['bankroll_start'])
    for t in ledger['trades']:
        if not in_cash_book(t):
            continue
        st = t.get('status')
        if st in ('open', 'settled', 'void'):
            cash -= float(t.get('stake') or 0)
        if st == 'settled':
            cash += float(t.get('payout') or 0)
        elif st == 'void':
            cash += float(t.get('stake') or 0)
    ledger['cash'] = round(cash, 2)
    return ledger['cash']


def _stake_on(trades, day=None, market=None, event=None):
    total = 0.0
    for t in trades:
        if t.get('status') not in ('open', 'settled', 'void') or not in_cash_book(t):
            continue
        if day is not None and et_day(t['ts']) != day:
            continue
        if market is not None and t.get('ticker') != market:
            continue
        if event is not None and t.get('event') != event:
            continue
        total += float(t.get('stake') or 0)
    return total


def spent_buckets(ledger, now, ticker, event):
    day = et_day(now)
    return {
        'day': _stake_on(ledger['trades'], day=day),
        'market': _stake_on(ledger['trades'], market=ticker),
        'event': _stake_on(ledger['trades'], event=event),
    }


def held_tickers(ledger):
    """Kalshi tickers we already acted on. A veto sticks; an error row does not.

    novig: tickers belong to a separate paper book and never block a Kalshi proposal.
    """
    out = set()
    for t in ledger['trades']:
        if str(t.get('ticker') or '').startswith('novig:'):
            continue
        if t.get('status') in ('open', 'settled', 'void', 'vetoed'):
            out.add(t.get('ticker'))
    return out


def build_base_ledger(published, recovered):
    """Ledger a run should start from: published merged with every recovered ledger.

    published is the paper-data copy or None. recovered is a list of ledgers that earlier runs wrote
    before their publish (None entries are skipped). A failed publish leaves new trades only in that
    run's artifact, and a snapshot run that started earlier can upload a newer artifact without them,
    so no single artifact is trusted alone: the union by trade id is taken, the more advanced row wins,
    and held_tickers of the result covers every ticker any source held. None when every input is None.
    """
    from .merge_ledger import merge_ledgers      # lazy: merge_ledger imports cfb_jp_novig, which imports this module
    found = [led for led in [published] + list(recovered or []) if led is not None]
    if not found:
        return None
    base = found[0]
    for led in found[1:]:
        base = merge_ledgers(led, base)
    return base


def choose_base_ledger(published, recovered):
    """Ledger a run should start from, given the published copy and the one recovered ledger (either may be None).

    Merges rather than picks, see build_base_ledger.
    """
    return build_base_ledger(published, [recovered])


def day_pnl(ledger, now):
    """Today's realized P&L, plus the mark-to-market of positions opened today."""
    day = et_day(now)
    pnl = 0.0
    for t in ledger['trades']:
        if not in_cash_book(t):
            continue
        if t.get('status') == 'settled' and t.get('settled_ts') and et_day(t['settled_ts']) == day:
            pnl += float(t.get('pnl') or 0)
        elif t.get('status') == 'open' and et_day(t['ts']) == day:
            pnl += float(t.get('mark_value') if t.get('mark_value') is not None else t.get('stake') or 0) - float(t.get('stake') or 0)
    return pnl


def open_mark(ledger):
    return round(sum(float(t.get('mark_value') if t.get('mark_value') is not None else t.get('stake') or 0)
                     for t in ledger['trades'] if t.get('status') == 'open' and in_cash_book(t)), 2)


def record_equity(ledger, now):
    recompute_cash(ledger)
    point = {
        'ts': iso(now),
        'cash': ledger['cash'],
        'equity': round(ledger['cash'] + open_mark(ledger), 2),
    }
    ledger['equity'].append(point)
    if len(ledger['equity']) > 2000:
        ledger['equity'] = ledger['equity'][-2000:]
    return point


def _is_pending(t):
    """A settled row whose result is not decided yet: a partly exited cfb_jp_novig trade waiting on its remainder."""
    if t.get('status') != 'settled' or not (t.get('book') or t.get('source') == 'cfb_jp_novig'):
        return False    # only the book rows (book='novig', cfb_jp_novig) wait on a remainder; a Kalshi row with won None is a data gap
    return bool(t.get('remainder_pending')) or t.get('won') is None


def _group_rows(trades):
    stake = pnl = 0.0
    w = l = n = pend = 0
    clv = []
    brier_n = brier_s = 0.0
    for t in trades:
        if t.get('status') != 'settled':
            continue
        if _is_pending(t):
            pend += 1       # not a loss: it joins settled/wins/losses/stake/pnl once it is graded
            continue
        n += 1
        stake += float(t.get('stake') or 0)
        pnl += float(t.get('pnl') or 0)
        if t.get('won'):
            w += 1
        else:
            l += 1
        if t.get('clv') is not None:
            clv.append(float(t['clv']))
        p = t.get('model_prob')
        if p is not None:
            hit = 1.0 if t.get('won') else 0.0
            brier_s += (float(p) - hit) ** 2
            brier_n += 1
    return {
        'settled': n,
        'wins': w,
        'losses': l,
        'pending': pend,
        'stake': round(stake, 2),
        'pnl': round(pnl, 2),
        'roi': (round(pnl / stake, 4) if stake else None),
        'clv_n': len(clv),
        'clv_mean': (round(sum(clv) / len(clv), 4) if clv else None),
        'brier': (round(brier_s / brier_n, 4) if brier_n else None),
    }


def summarize(ledger):
    all_trades = ledger['trades']
    trades = [t for t in all_trades if in_cash_book(t)]     # the Kalshi book; other books report under by_source and strategies
    by = {}
    for t in all_trades:
        by.setdefault(t.get('source') or 'unknown', []).append(t)
    sources = {name: _group_rows(rows) for name, rows in sorted(by.items())}
    for name, rows in by.items():
        sources[name]['open'] = sum(1 for t in rows if t.get('status') == 'open')
        sources[name]['vetoed'] = sum(1 for t in rows if t.get('status') == 'vetoed')
    months = {}
    for t in trades:
        if t.get('status') != 'settled' or not t.get('settled_ts'):
            continue
        key = et_month(t['settled_ts'])
        slot = months.setdefault(key, {'pnl': 0.0, 'stake': 0.0, 'n': 0})
        slot['pnl'] += float(t.get('pnl') or 0)
        slot['stake'] += float(t.get('stake') or 0)
        slot['n'] += 1
    for slot in months.values():
        slot['pnl'] = round(slot['pnl'], 2)
        slot['stake'] = round(slot['stake'], 2)
    bins = []
    settled = [t for t in trades if t.get('status') == 'settled' and t.get('model_prob') is not None]
    for i in range(10):
        lo, hi = i / 10, (i + 1) / 10
        rows = [t for t in settled if lo <= float(t['model_prob']) < hi or (i == 9 and float(t['model_prob']) == 1)]
        if not rows:
            bins.append({'lo': lo, 'hi': hi, 'n': 0, 'hit': None, 'pred': None})
            continue
        hit = sum(1 for t in rows if t.get('won')) / len(rows)
        pred = sum(float(t['model_prob']) for t in rows) / len(rows)
        bins.append({'lo': lo, 'hi': hi, 'n': len(rows), 'hit': round(hit, 4), 'pred': round(pred, 4)})
    overall = _group_rows(trades)
    overall['open'] = sum(1 for t in trades if t.get('status') == 'open')
    overall['void'] = sum(1 for t in trades if t.get('status') == 'void')
    overall['vetoed'] = sum(1 for t in trades if t.get('status') == 'vetoed')
    fees = round(sum(float(t.get('fee_total') or 0) for t in trades if t.get('status') in ('open', 'settled', 'void')), 2)
    strategies = {name: dict(s['progress']) for name, s in sorted((ledger.get('strategies') or {}).items())
                  if isinstance(s, dict) and s.get('progress')}
    ledger['summary'] = {
        'strategies': strategies,
        'overall': overall,
        'by_source': sources,
        'months': months,
        'calibration': bins,
        'fees': fees,
        'cash': ledger.get('cash'),
        'open_mark': open_mark(ledger),
    }
    return ledger['summary']


PRE_FIX_TAG = 'pre_fix_raw_v1_margin'
PRE_FIX_DAY = '2026-10-13'


def tag_pre_fix_trades(ledger):
    """Tag CFB trades opened on 2026-10-13 that priced off the raw v1 margin. Idempotent, never removes a trade."""
    n = 0
    for t in ledger.get('trades', []):
        if t.get('source') != 'cfb_ml' or not t.get('ts') or et_day(t['ts']) != PRE_FIX_DAY:
            continue
        d = t.get('detail') or {}
        if 'priced_margin' in d or d.get('model_margin') is None:
            continue
        tags = t.setdefault('tags', [])
        if PRE_FIX_TAG not in tags:
            tags.append(PRE_FIX_TAG)
            n += 1
    return n
