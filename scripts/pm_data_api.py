"""Polymarket Data API v2 helpers (v1 retired 2026-11-02 and answers HTTP 410).

Python twin of scripts/pm-data-api.mjs. v2 wraps rows in {data, pagination},
pages by cursor only (no `offset`; `market` is now `condition`), and names
fields in snake_case. pm_row() maps a row back to the v1 names the scripts
already read. On /v2/trades `start`/`end` are honored only for a `user` feed,
so a condition feed is walked newest-first by cursor (no 10k offset cap).

Every page fetch goes through the caller's `get(url)`; it returns parsed JSON or
None on failure. A failure raises PMDataError so callers can tell "no trades"
from "could not ask" (the v1 retirement read as "no trades" for a week).
"""
from urllib.parse import urlencode

PM_DATA = "https://data-api.polymarket.com/v2"


class PMDataError(RuntimeError):
    pass


def pm_row(x):
    if not isinstance(x, dict): return x
    r = dict(x)
    r.update(proxyWallet=x.get("proxy_wallet"), conditionId=x.get("condition_id"), asset=x.get("token_id"),
             outcomeIndex=x.get("outcome_index"), transactionHash=x.get("transaction_hash"),
             eventSlug=x.get("event_slug"), usdcSize=x.get("usdc_size"))
    return r


def pm_pages(get, path, params, max_pages=1):
    """Yield (rows, more) per page, rows v1-shaped. Raises PMDataError when a page cannot be fetched."""
    cursor = None
    for _ in range(max_pages):
        q = {k: ("true" if v is True else "false" if v is False else v) for k, v in params.items() if v is not None}
        if cursor: q["cursor"] = cursor
        j = get(f"{PM_DATA}{path}?{urlencode(q)}")
        if not isinstance(j, dict) or "data" not in j:
            raise PMDataError(f"{path} {params.get('condition') or params.get('user') or ''}: no response")
        rows = [pm_row(x) for x in (j.get("data") or [])]
        pg = j.get("pagination") or {}
        cursor = pg.get("next_cursor")
        more = bool(pg.get("has_more") and cursor)
        yield rows, more
        if not more: return
