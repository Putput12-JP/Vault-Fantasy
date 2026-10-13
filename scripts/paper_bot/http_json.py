"""Small JSON GET with a couple of retries. Used for Kalshi's public API and ESPN."""
import json
import time
import urllib.error
import urllib.request


UA = {'User-Agent': 'VaultFantasy/1.0 (+vaultfantasy.com)', 'Accept': 'application/json'}


def get_json(url, timeout=30, tries=3, sleep=time.sleep):
    delay = 1.0
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            last = e
            if attempt == tries - 1:
                raise
        sleep(delay)
        delay = min(delay * 2, 8)
    raise last
