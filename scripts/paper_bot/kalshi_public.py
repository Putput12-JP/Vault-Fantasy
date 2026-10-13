"""Public Kalshi market data. No API key. Reading only — this module has no order call."""
import urllib.parse

from .http_json import get_json
from .quotes import parse_market

BASE = 'https://api.elections.kalshi.com/trade-api/v2'


class KalshiPublic:
    def __init__(self, get=None):
        self.get = get or get_json

    def markets(self, series, status='open', limit_pages=20):
        out = []
        cursor = ''
        for _ in range(limit_pages):
            q = f'{BASE}/markets?series_ticker={urllib.parse.quote(series)}&status={urllib.parse.quote(status)}&limit=200'
            if cursor:
                q += '&cursor=' + urllib.parse.quote(cursor)
            data = self.get(q)
            batch = (data or {}).get('markets') or []
            for raw in batch:
                qrow = parse_market(raw)
                if qrow:
                    out.append(qrow)
            cursor = (data or {}).get('cursor') or ''
            if not cursor or not batch:
                break
        return out

    def markets_by_ticker(self, tickers):
        """Look up specific markets (open or settled). Falls back to one request per ticker."""
        found = {}
        want = [t for t in tickers if t]
        for i in range(0, len(want), 15):
            chunk = want[i:i + 15]
            url = BASE + '/markets?tickers=' + ','.join(urllib.parse.quote(t) for t in chunk)
            data = None
            try:
                data = self.get(url)
            except Exception:
                data = None
            rows = (data or {}).get('markets') if isinstance(data, dict) else None
            if rows:
                for raw in rows:
                    qrow = parse_market(raw)
                    if qrow:
                        found[qrow['ticker']] = qrow
                continue
            for t in chunk:
                try:
                    data = self.get(f'{BASE}/markets/{urllib.parse.quote(t)}')
                except Exception:
                    continue
                raw = (data or {}).get('market') if isinstance(data, dict) else None
                qrow = parse_market(raw) if raw else None
                if qrow:
                    found[qrow['ticker']] = qrow
        return found
