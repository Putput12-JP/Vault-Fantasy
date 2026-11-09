#!/usr/bin/env python3
"""Rebuild data/pm_signal_log.json reads lost to the Polymarket Data API v1 retirement.

From 2026-11-02 18:51 UTC every /trades call answered HTTP 410, takerFlow()
returned null, and fetch-polymarket.mjs logged "0 upcoming games updated":
games already in the log kept a stale `last` read, and newer games never got
an entry. This rebuilds the read the hourly job would have stored, from the
v2 trade tape: all taker trades on the full-game moneyline in the 24 hours
before kickoff (the live read's window), split by the account scorecard the
live job had loaded at the time (pm_wallets.json as committed on 2026-11-03,
scored only on earlier games). home_p is the last pre-kickoff trade.

Rows are marked src:'backfill' with a note, like the week-3 backfill. A game
whose tape cannot be fetched is left as it was.

Usage: python3 scripts/backfill_pm_signal_log.py [--since=2026-11-02T18:51] [--wallets=<git rev>] [--dry]
"""
import json, os, subprocess, sys, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pm_data_api import pm_pages, PMDataError  # noqa: E402

ROOT = os.path.dirname(HERE)
LOG = os.path.join(ROOT, "data", "pm_signal_log.json")
UA = {"User-Agent": "VaultFantasy/1.0 (+vaultfantasy.com)", "Accept": "application/json"}
ALIAS = {"WSH": "WAS", "JAC": "JAX", "LVR": "LV", "LA": "LAR", "SFO": "SF", "GBP": "GB", "KAN": "KC", "NWE": "NE",
         "NOR": "NO", "TAM": "TB", "ARZ": "ARI", "CLV": "CLE", "BLT": "BAL", "HST": "HOU"}
code = lambda a: ALIAS.get(a.upper(), a.upper())


def get(url):
    for _ in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except Exception: pass
    return None


def iso(ts): return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def main():
    a = dict(x.lstrip("-").split("=", 1) if "=" in x else (x.lstrip("-"), True) for x in sys.argv[1:])
    since = datetime.fromisoformat(a.get("since", "2026-11-02T18:51") + "+00:00").timestamp()
    rev = a.get("wallets", "585358373")          # the scorecard the hourly job had loaded 2026-11-03 .. 2026-11-09
    W = json.loads(subprocess.check_output(["git", "-C", ROOT, "show", f"{rev}:data/pm_wallets.json"]))
    sharp, dull = set(W.get("sharp") or []), set(W.get("dull") or [])
    L = json.load(open(LOG))
    now = datetime.now(timezone.utc).timestamp()
    evs = []
    for off in range(0, 600, 100):
        r = get(f"https://gamma-api.polymarket.com/events?closed=true&tag_slug=nfl&limit=100&offset={off}&order=endDate&ascending=false")
        if not r: break
        evs += r
        if len(r) < 100: break
    done = 0
    for e in evs:
        parts = (e.get("slug") or "").split("-")
        if len(parts) != 6 or parts[0] != "nfl": continue
        ms = [m for m in e.get("markets") or [] if m.get("sportsMarketType") == "moneyline"]
        if not ms: continue
        ml = max(ms, key=lambda m: float(m.get("volumeNum") or 0))
        gst = (ml.get("gameStartTime") or "").replace(" ", "T").replace("Z", "+00:00")
        if gst.endswith("+00"): gst += ":00"
        try: kick = datetime.fromisoformat(gst).timestamp()
        except Exception: continue
        if not (since < kick < now): continue
        away, home = code(parts[1]), code(parts[2])
        vs = (e.get("title") or "").lower().split(" vs")
        an, hn = vs[0].strip(), (vs[1].lstrip(". ").strip() if len(vs) > 1 else "")
        net = sh = du = 0.0; shn = 0; last = None
        try:
            for rows, _more in pm_pages(get, "/trades", {"condition": ml["conditionId"], "taker_only": True, "limit": 1000}, 200):
                for t in rows:
                    ts = t["timestamp"]
                    if ts >= kick: continue
                    if ts < kick - 86400: continue
                    nm = str(t.get("outcome") or "").lower()
                    is_h, is_a = bool(nm and nm in hn), bool(nm and nm in an)
                    if not (is_h or is_a): continue
                    buy = t.get("side") == "BUY"
                    usd = (1 if (is_h == buy) else -1) * t["price"] * t["size"]
                    net += usd
                    if t.get("proxyWallet") in sharp: sh += usd; shn += 1
                    elif t.get("proxyWallet") in dull: du += usd
                    if last is None or ts > last[0]: last = (ts, t["price"] if is_h else 1 - t["price"])
                if rows and rows[-1]["timestamp"] < kick - 86400: break
        except PMDataError as ex:
            print(f"[backfill] {e['slug']}: {ex}; left as it was", file=sys.stderr); continue
        if last is None: continue
        read = {"ts": iso(kick), "home_p": round(last[1], 4), "all": round(net), "sharp": round(sh), "sharpN": shn,
                "dull": round(du), "crowd": round(net - sh), "spread_sharp": None}
        k = f"{away}@{home}|{iso(kick)}"
        # Same game already logged under the event's endDate (the live key): reuse that key, never add a twin.
        for k0, e0 in L["games"].items():
            if e0.get("away") == away and e0.get("home") == home and abs(datetime.fromisoformat(e0["commence"].replace("Z", "+00:00")).timestamp() - kick) < 6 * 3600:
                k = k0; break
        old = L["games"].get(k)
        ent = {"away": away, "home": home, "commence": (old or {}).get("commence") or iso(kick), "src": "backfill",
               "note": "rebuilt from the v2 trade tape after the v1 API retirement (2026-11-02): 24h taker flow to kickoff, scorecard as loaded then",
               "first": (old or {}).get("first") or read, "last": read}
        if old: ent["stale_last"] = old.get("last")
        L["games"][k] = ent; done += 1
        print(f"[backfill] {k}  all {read['all']:+,}  sharp {read['sharp']:+,} ({shn})  home_p {read['home_p']}  {'replaced stale' if old else 'new'}")
    print(f"[backfill] {done} games rebuilt")
    if not a.get("dry"):
        json.dump(L, open(LOG, "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
