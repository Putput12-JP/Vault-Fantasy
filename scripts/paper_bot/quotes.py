"""Kalshi market quotes, in dollars. Public market-data fields only."""


def _f(v):
    if v is None or v == '':
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return n


def parse_market(raw):
    """One /markets row into a quote dict, or None when the bid/ask is unusable."""
    if not isinstance(raw, dict) or not raw.get('ticker'):
        return None
    yb, ya = _f(raw.get('yes_bid_dollars')), _f(raw.get('yes_ask_dollars'))
    result = str(raw.get('result') or '').strip().lower()
    status = str(raw.get('status') or '').strip().lower()
    settled = result in ('yes', 'no') or status in ('finalized', 'determined', 'settled', 'voided', 'void', 'cancelled', 'canceled')
    if yb is None or ya is None or ya < yb or ya > 1 or yb < 0:
        if not settled:
            return None
        yb = 0.0 if yb is None else min(max(yb, 0.0), 1.0)
        ya = 1.0 if ya is None else min(max(ya, 0.0), 1.0)
        if ya < yb:
            yb, ya = ya, yb
    no_bid = _f(raw.get('no_bid_dollars'))
    no_ask = _f(raw.get('no_ask_dollars'))
    if no_bid is None:
        no_bid = round(1 - ya, 4)
    if no_ask is None:
        no_ask = round(1 - yb, 4)
    yes_sz = _f(raw.get('yes_ask_size_fp')) or 0.0
    no_sz = _f(raw.get('no_ask_size_fp'))
    if no_sz is None:
        # Buying NO lifts the yes bid. That size is the no-ask size when Kalshi omits no_ask_size_fp.
        no_sz = _f(raw.get('yes_bid_size_fp')) or 0.0
    return {
        'ticker': raw['ticker'],
        'event': raw.get('event_ticker') or '',
        'title': raw.get('title') or '',
        'sub': raw.get('yes_sub_title') or '',
        'strike': _f(raw.get('floor_strike')),
        'yes_bid': yb,
        'yes_ask': ya,
        'no_bid': no_bid,
        'no_ask': no_ask,
        'yes_ask_size': yes_sz,
        'no_ask_size': no_sz,
        'status': status,
        'result': result,
        'settlement_value': raw.get('settlement_value_dollars'),
        'close_time': raw.get('close_time'),
        'volume': _f(raw.get('volume_fp')) or 0.0,
    }


def market_tradable(q, cfg):
    """Tight, two-sided quote inside the price band. Same 10¢ spread gate as scripts/fetch-kalshi.mjs."""
    spread = q['yes_ask'] - q['yes_bid']
    mid = (q['yes_ask'] + q['yes_bid']) / 2
    if spread > float(cfg['max_spread']) + 1e-9:
        return False
    lo, hi = float(cfg['min_price']), float(cfg['max_price'])
    if not (lo < mid < hi):
        return False
    if q['yes_bid'] <= 0 or q['yes_ask'] >= 1:
        return False
    return True


def side_price(q, side):
    return q['yes_ask'] if side == 'yes' else q['no_ask']


def side_bid(q, side):
    return q['yes_bid'] if side == 'yes' else q['no_bid']


def side_size(q, side):
    return q['yes_ask_size'] if side == 'yes' else q['no_ask_size']


def side_mid(q, side):
    if side == 'yes':
        return (q['yes_bid'] + q['yes_ask']) / 2
    return (q['no_bid'] + q['no_ask']) / 2


def settlement_of(q):
    """'yes', 'no', 'void', or None when the market is still open."""
    if q['result'] in ('yes', 'no'):
        return q['result']
    sv = str(q.get('settlement_value') if isinstance(q, dict) else '').strip()
    if sv in ('1', '1.0', '1.00', '1.0000'):
        return 'yes'
    if sv in ('0', '0.0', '0.00', '0.0000'):
        return 'no'
    status = q.get('status') or ''
    if status in ('voided', 'void', 'cancelled', 'canceled'):
        return 'void'
    return None
