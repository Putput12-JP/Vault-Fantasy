"""SmartStake Odds API client. The key comes from env; nothing secret is in the repo.

  SMARTSTAKE_API_KEY   bearer key (required)
  SMARTSTAKE_HOST      default https://api.server.smartstake.ca

Terms (https://www.smartstake.app/terms/api): internal research, modelling and
backtesting only. Do NOT publish, serve or commit API data, and do not show it in
the public UI without written permission from SmartStake. Raw tapes therefore live
under data/smartstake/, which is gitignored.
"""
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HOST = os.environ.get("SMARTSTAKE_HOST", "https://api.server.smartstake.ca")


def _headers():
    key = os.environ.get("SMARTSTAKE_API_KEY")
    if not key:
        path = os.path.expanduser("~/.config/smartstake/key")
        if os.path.exists(path):
            key = open(path).read().strip()
    if not key:
        sys.exit("SMARTSTAKE_API_KEY is not set and ~/.config/smartstake/key is missing")
    # Accept-Encoding: gzip is mandatory (406 otherwise); requests sends it by default.
    return {"Authorization": f"Bearer {key}", "Accept-Encoding": "gzip"}


def get(path, params=None, retries=3):
    url = HOST + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(min(float(e.headers.get("Retry-After", 2)), 30))
                continue
            sys.exit(f"{path}: HTTP {e.code} {e.read()[:300].decode('utf-8', 'replace')}")
    raise RuntimeError(f"{path}: still throttled after {retries} tries")


def snapshot(league, book=None, **filters):
    """Whole-league board, following next_cursor. Yields quote dicts."""
    params = {"league": league, **filters}
    if book:
        params["book"] = book
    while True:
        body = get("/v1/odds", params)
        data = body.get("data")
        quotes = data.get("quotes", data) if isinstance(data, dict) else data
        for q in quotes or []:
            yield q
        cursor = (data.get("next_cursor") if isinstance(data, dict) else None) or body.get("next_cursor")
        if not cursor:
            return
        params["cursor"] = cursor
        time.sleep(6.5)  # stay under 10 snapshot pages a minute
