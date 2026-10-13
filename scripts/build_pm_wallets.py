#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · POLYMARKET NFL ACCOUNT SCORECARD  →  data/pm_wallets.json
#
#  "Where is the sharp money?" Polymarket's trade tape is public and every
#  trade carries the account (proxyWallet) that made it, so accounts can be
#  scored on their own record. Unit: one sample per account per game. The
#  sample is that account's $1k+ taker trades on the full-game moneyline
#  before kickoff, collapsed to a single dollar-weighted entry on their net
#  side. Several fills by the same account on the same game are one bet, not
#  several independent proofs of skill.
#
#  Close: volume-weighted average price of outcome 0 over the last 10 minutes
#  before kickoff (widened to 30 minutes when that window is under $500).
#  The last single trade is only a fallback, and it is labeled as such: a
#  tiny fill is not a close. Score = close of the side bought / price paid - 1.
#
#  The trades API only returns the newest 10k rows for an offset. In-game
#  trading fills that window, so a plain offset walk never reaches kickoff on
#  a busy market. `end=<unix>` is a real upper bound (unlike `before` /
#  `endTs`, which the API ignores). When the offset cap is hit, the walk
#  restarts at the oldest timestamp it has seen.
#
#  Rule (schema 2): 5+ games, 10+ trades, t >= 3 on the per-game samples.
#  t >= 2 on per-trade samples flagged ~2.3% of qualifying wallets by luck
#  (NFL: 52 of 496, about 11 expected). One-sided t >= 3 is about 0.13%.
#  Benjamini-Hochberg q-values at 5% are stored on every tested wallet so the
#  multiple-testing result is visible; the live label stays t >= 3 because a
#  q cutoff moves as the wallet set changes and would flip accounts between
#  weekly runs. A file written by the old per-trade rule (no schema, or
#  schema != 2) is not mixed in: the aggregates mean something else, so the
#  next run starts a fresh scorecard and backfills newest games first.
#
#  Study, 2026-09-28 (613 settled games, per-trade, kept here as history):
#  skill persisted, but copying 30 min+ later did not. Context only.
#
#  Sports: --sport=nfl (default, data/pm_wallets.json), cfb, nba.
#  Usage: python3 scripts/build_pm_wallets.py [--sport=nfl] [--max=60] [--dry] [--selftest]
# ════════════════════════════════════════════════════════════════════════════
import json, math, os, re, sys, time, urllib.request, glob
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SPORTS = {"nfl": {"series": 12185, "out": "pm_wallets.json", "skip_months": ("07", "08")},
          "cfb": {"series": 12756, "out": "pm_wallets_cfb.json", "skip_months": ()},
          "nba": {"series": 10345, "out": "pm_wallets_nba.json", "skip_months": ("07", "08", "09")}}
SPORT = "nfl"
OUT = os.path.join(HERE, "..", "data", "pm_wallets.json")
UA = {"User-Agent": "VaultFantasy/1.0 (+vaultfantasy.com)", "Accept": "application/json"}
GAME_RE = re.compile(r"^nfl-[a-z]{2,3}-[a-z]{2,3}-(\d{4}-\d{2}-\d{2})$")
SCHEMA = 2


def set_sport(sp):
    global SPORT, OUT, GAME_RE
    SPORT = sp
    OUT = os.path.join(HERE, "..", "data", SPORTS[sp]["out"])
    GAME_RE = re.compile(r"^" + sp + r"-[a-z0-9]{2,8}-[a-z0-9]{2,8}-(\d{4}-\d{2}-\d{2})$")
BIG = 1000              # $ per trade to enter the sample
MIN_TRADES, MIN_GAMES, T_SHARP = 10, 5, 3.0
FDR_Q = 0.05
CLOSE_WINDOWS = (600, 1800)    # 10 min, then 30 min
CLOSE_MIN_USD = 500
OFFSET_CAP = 10000             # data-api rejects offset >= 10000
PAGE = 500


def get(url, tries=3):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except Exception as e:
            if "400" in str(e): return []
            time.sleep(2 + 3 * i)
    return None


def norm_sf(t):
    """One-sided P(Z > t) for a standard normal."""
    return 0.5 * math.erfc(t / math.sqrt(2))


def bh_q(pairs, q=FDR_Q):
    """Benjamini-Hochberg q-values. pairs = [(id, p), ...]. Returns (pass_ids, q_by_id)."""
    m = len(pairs)
    if not m: return set(), {}
    ordered = sorted(pairs, key=lambda x: (x[1], x[0]))
    cutoff = 0
    for i, (id_, p) in enumerate(ordered, start=1):
        if p <= q * i / m: cutoff = i
    passed = {id_ for id_, _p in ordered[:cutoff]}
    qs, running = {}, 1.0
    for i, (id_, p) in reversed(list(enumerate(ordered, start=1))):
        running = min(running, p * m / i)
        qs[id_] = min(1.0, running)
    return passed, qs


def fetch_trades(cid, end_ts, extra="", page_cap=40, getter=None):
    """Trades with timestamp < end_ts, newest first.

    Walks offset up to the API cap, then restarts with `end` set to the oldest
    timestamp already seen. `end` is the parameter the API actually honors.
    """
    getter = getter or get
    out, cursor, off, pages = [], int(end_ts), 0, 0
    while pages < page_cap:
        url = (f"https://data-api.polymarket.com/trades?market={cid}&limit={PAGE}&offset={off}&end={cursor}{extra}")
        r = getter(url)
        if not r: break
        rows = [t for t in r if t.get("timestamp", 0) < end_ts]
        out.extend(rows)
        pages += 1
        oldest = min(t["timestamp"] for t in r)
        if len(r) < PAGE: break
        off += PAGE
        if off >= OFFSET_CAP:
            if oldest >= cursor: break
            cursor, off = oldest, 0
    return out


def vwap_from_trades(trades, start, window, min_usd=CLOSE_MIN_USD):
    """Dollar-weighted price of outcome 0 over [start-window, start). None if thin."""
    lo = start - window
    num = den = 0.0
    for t in trades:
        ts = t["timestamp"]
        if ts >= start or ts < lo: continue
        p0 = t["price"] if t.get("outcomeIndex") == 0 else 1 - t["price"]
        usd = float(t.get("size") or 0) * float(t.get("price") or 0)
        if usd <= 0 or not (0.02 < p0 < 0.98): continue
        num += p0 * usd
        den += usd
    if den < min_usd: return None
    return num / den


def last_price(trades, start):
    pre = [t for t in trades if t["timestamp"] < start and 0.02 < t.get("price", 0) < 0.98]
    if not pre: return None
    t = max(pre, key=lambda x: x["timestamp"])
    return t["price"] if t.get("outcomeIndex") == 0 else 1 - t["price"]


def close_from_trades(trades, start):
    for window, src in ((CLOSE_WINDOWS[0], "vwap10m"), (CLOSE_WINDOWS[1], "vwap30m")):
        px = vwap_from_trades(trades, start, window)
        if px is not None: return px, src
    px = last_price(trades, start)
    return (px, "last") if px is not None else (None, None)


def closed_games():
    out = []
    src = "tag_slug=nfl" if SPORT == "nfl" else f"series_id={SPORTS[SPORT]['series']}"
    for off in range(0, 5000, 100):
        r = get(f"https://gamma-api.polymarket.com/events?closed=true&limit=100&offset={off}&{src}&order=endDate&ascending=false")
        if not r: break
        out += [e for e in r if GAME_RE.match(e.get("slug") or "")]
        if len(r) < 100: break
    return [e for e in out if GAME_RE.match(e["slug"]).group(1)[5:7] not in SPORTS[SPORT]["skip_months"]]


def game_record(e):
    """{slug, start, close0, close_src, big:[[wallet, ts, outcomeIndex, side, price, size]]} or None."""
    ms = [m for m in e.get("markets") or [] if m.get("sportsMarketType") == "moneyline"] \
        or [m for m in e.get("markets") or [] if len(json.loads(m.get("outcomes") or "[]")) == 2 and "vs" in (m.get("question") or "")]
    if not ms: return None
    ml = max(ms, key=lambda m: float(m.get("volumeNum") or 0))
    gst = (ml.get("gameStartTime") or e.get("endDate") or "").replace(" ", "T").replace("Z", "+00:00")
    if gst.endswith("+00"): gst += ":00"
    try: start = datetime.fromisoformat(gst).timestamp()
    except Exception: return None
    cid = ml["conditionId"]
    big_rows = fetch_trades(cid, start, f"&takerOnly=true&filterType=CASH&filterAmount={BIG}", page_cap=30)
    big = [[t["proxyWallet"], t["timestamp"], t["outcomeIndex"], t["side"], round(t["price"], 4), round(t["size"], 2)]
           for t in big_rows if t["timestamp"] < start and t.get("side") in ("BUY", "SELL")]
    # The close only needs the last half hour, so stop the walk once a page is entirely older than that.
    close_rows, cursor, off, pages = [], int(start), 0, 0
    while pages < 40:
        r = get(f"https://data-api.polymarket.com/trades?market={cid}&limit={PAGE}&offset={off}&end={cursor}")
        if not r: break
        close_rows.extend(t for t in r if t["timestamp"] < start)
        pages += 1
        oldest = min(t["timestamp"] for t in r)
        if oldest < start - CLOSE_WINDOWS[-1]: break
        if len(r) < PAGE: break
        off += PAGE
        if off >= OFFSET_CAP:
            if oldest >= cursor: break
            cursor, off = oldest, 0
    close, src = close_from_trades(close_rows, start)
    if close is None and big:
        b = max(big, key=lambda x: x[1])
        close, src = (b[4] if b[2] == 0 else 1 - b[4]), "last_big"
    return {"slug": e["slug"], "start": start, "close0": close, "close_src": src, "big": big}


def samples_from_game(g):
    """One CLV sample per wallet: dollar-weighted entry on the net side. {wallet: (clv, n_trades)}."""
    c0 = g.get("close0")
    if c0 is None or not (0.03 < c0 < 0.97): return {}
    book = {}
    for w, ts, oi, side, p, size in g.get("big") or []:
        if not (0.02 < p < 0.98) or side not in ("BUY", "SELL"): continue
        k, q = (oi, p) if side == "BUY" else (1 - oi, 1 - p)
        usd = float(size) * float(q)
        if usd <= 0: continue
        slot = book.setdefault(w, {0: [0.0, 0.0], 1: [0.0, 0.0], "n": 0})
        slot[k][0] += usd
        slot[k][1] += usd * q
        slot["n"] += 1
    out = {}
    for w, slot in book.items():
        u0, u1 = slot[0][0], slot[1][0]
        if u0 == u1: continue
        k = 0 if u0 > u1 else 1
        q = slot[k][1] / slot[k][0]
        if not (0.02 < q < 0.98): continue
        cl = c0 if k == 0 else 1 - c0
        out[w] = (cl / q - 1, slot["n"])
    return out


def add_game(W, g):
    n = 0
    for w, (clv, ntr) in samples_from_game(g).items():
        a = W.setdefault(w, [0, 0.0, 0.0, 0, 0])   # games, sum, sumsq, games (again), trades
        if len(a) < 5: a += [0] * (5 - len(a))
        a[0] += 1
        a[1] += clv
        a[2] += clv * clv
        a[3] += 1
        a[4] += ntr
        n += 1
    return n


def t_of(a):
    """t on per-game samples. None when there is nothing to score."""
    n, s, ss = a[0], a[1], a[2]
    if n < 2: return None
    m = s / n
    var = max(ss / n - m * m, 0)
    if var <= 0: return 0.0 if m == 0 else (math.inf if m > 0 else -math.inf)
    return m / math.sqrt(var / n)


def wallet_view(w, a, q=None):
    n, s, ss, gms = a[0], a[1], a[2], a[3]
    trades = a[4] if len(a) > 4 else None
    t = t_of(a)
    m = s / n if n else None
    # one-sided p in the direction of the mean
    if t is None: p = None
    elif not math.isfinite(t): p = 0.0 if t > 0 else 1.0
    else: p = norm_sf(t) if t >= 0 else norm_sf(-t)
    t_out = None if t is None else (99.0 if t == math.inf else -99.0 if t == -math.inf else round(t, 2))
    return {"n": n, "games": gms, "trades": trades, "clv": None if m is None else round(m, 4),
            "t": t_out, "p": None if p is None else round(p, 4), "q": None if q is None else round(q, 4)}


def classify_all(W):
    """sharp / dull lists plus a stats map. Live label is t >= 3; q is reported, not the gate."""
    tested = []
    ts = {}
    for w, a in W.items():
        trades = a[4] if len(a) > 4 else a[0]
        t = t_of(a)
        ts[w] = t
        if a[0] < MIN_GAMES or trades < MIN_TRADES or t is None: continue
        # Zero residual variance is a real result: every game went the same way.
        if not math.isfinite(t):
            tested.append((w, 0.0 if t > 0 else 1.0, 99.0 if t > 0 else -99.0))
            continue
        p = norm_sf(t) if t >= 0 else norm_sf(-t)
        tested.append((w, p, t))
    _passed, qs = bh_q([(w, p) for w, p, _t in tested])
    stats = {w: wallet_view(w, a, qs.get(w)) for w, a in W.items() if a[0] >= 1}
    sharp, dull = [], []
    for w, p, t in tested:
        if t >= T_SHARP: sharp.append(w)
        elif t <= -T_SHARP: dull.append(w)
    fdr_pass = sorted(w for w, p, t in tested if w in _passed and t >= T_SHARP)
    return sorted(sharp), sorted(dull), stats, {"q": FDR_Q, "tested": len(tested), "pass_t3": len(sharp), "pass_fdr_and_t3": len(fdr_pass)}


def load_state(path):
    try: S = json.load(open(path))
    except Exception: S = {}
    if S.get("schema") != SCHEMA:
        if S.get("wallets"):
            print(f"[pm-wallets] {os.path.basename(path)} is schema {S.get('schema')}, not {SCHEMA}; starting a fresh per-game scorecard (old per-trade totals are not reusable)")
        return {"schema": SCHEMA, "processed": [], "wallets": {}}
    return S


def main():
    args = dict(a.lstrip("-").split("=", 1) if "=" in a else (a.lstrip("-"), True) for a in sys.argv[1:])
    if args.get("selftest"): return selftest()
    set_sport(args.get("sport", "nfl"))
    S = load_state(OUT)
    W, done = S.get("wallets") or {}, set(S.get("processed") or [])
    added = 0
    if args.get("seed"):
        for f in sorted(glob.glob(os.path.join(args["seed"], "*.json"))):
            g = json.load(open(f))
            if g["slug"] in done: continue
            add_game(W, g); done.add(g["slug"]); added += 1
    else:
        now = time.time()
        todo = [e for e in closed_games() if e["slug"] not in done]
        todo = todo[: int(args.get("max", 60))]
        with ThreadPoolExecutor(6) as ex:
            for g in ex.map(game_record, todo):
                if not g or g["start"] > now - 6 * 3600: continue
                if args.get("cache"):
                    os.makedirs(args["cache"], exist_ok=True)
                    json.dump(g, open(os.path.join(args["cache"], g["slug"] + ".json"), "w"))
                add_game(W, g); done.add(g["slug"]); added += 1
    sharp, dull, stats, fdr = classify_all(W)
    # Keep the array shape the page already reads: [n, sum, sumsq, games, trades].
    # n is games (the sample size), not fills. `stats` repeats n and t explicitly.
    out = {"generated": datetime.now(timezone.utc).isoformat(), "sport": SPORT, "schema": SCHEMA,
           "unit": f"one ${BIG}+ taker sample per game, dollar-weighted entry vs 10-minute VWAP close",
           "close": "vwap of the 10 minutes before kickoff, else 30 minutes, else the last trade",
           "rule": {"min_trades": MIN_TRADES, "min_games": MIN_GAMES, "t": T_SHARP, "unit": "game", "fdr_q": FDR_Q,
                    "note": "Labeled sharp at t>=3. q is Benjamini-Hochberg on the tested wallets and is not the live gate."},
           "fdr": fdr,
           "study": None if SPORT != "nfl" else {"games": 613, "sharp_clv_after": 0.0038, "dull_clv_after": -0.0090,
                     "sharp_side_won": [151, 260], "close_said": 0.592, "follow_30m_2h_clv": -0.0019,
                     "note": "Skill persists, but the edge is gone within about 30 minutes of the trade; by kickoff the price has priced it in. Context only, not a bet to copy."},
           "sharp": sharp, "dull": dull, "processed": sorted(done), "wallets": W, "stats": stats}
    print(f"[pm-wallets:{SPORT}] +{added} games -> {len(done)} total · {len(W)} accounts · {len(sharp)} sharp · {len(dull)} dull · fdr {fdr}")
    if args.get("dry"): return
    json.dump(out, open(OUT, "w"), separators=(",", ":"))


def selftest():
    # Three fills by one account on one game are one sample, weighted by dollars.
    g = {"close0": 0.60, "big": [
        ["A", 1, 0, "BUY", 0.40, 1000],   # $400 on outcome 0? size is shares, usd = size * q = 400
        ["A", 2, 0, "BUY", 0.50, 6000],   # $3000
        ["A", 3, 1, "BUY", 0.40, 100],    # small other side, net still outcome 0
        ["B", 4, 0, "BUY", 0.55, 2000],
    ]}
    s = samples_from_game(g)
    assert set(s) == {"A", "B"}, s
    # A's dollar-weighted price = (400*0.40 + 3000*0.50) / 3400
    clv_a, n_a = s["A"]
    assert n_a == 3
    assert abs(clv_a - (0.60 / (1660 / 3400) - 1)) < 1e-9, clv_a
    W = {}
    assert add_game(W, g) == 2
    assert W["A"][0] == 1 and W["A"][4] == 3, W["A"]
    # A second game, so the two games are two samples, not four trades.
    g2 = {"close0": 0.70, "big": [["A", 5, 0, "BUY", 0.50, 2000]]}
    add_game(W, g2)
    assert W["A"][0] == 2 and W["A"][4] == 4
    # VWAP: a $10 trade must not set the close when a $10k trade is there.
    trades = [
        {"timestamp": 100, "outcomeIndex": 0, "price": 0.90, "size": 10},
        {"timestamp": 200, "outcomeIndex": 0, "price": 0.40, "size": 25000},
    ]
    px = vwap_from_trades(trades, start=600, window=600, min_usd=100)
    assert abs(px - (0.90 * 9 + 0.40 * 10000) / (9 + 10000)) < 1e-9, px
    assert vwap_from_trades(trades, start=600, window=600, min_usd=10**9) is None
    c, src = close_from_trades(trades, 600)
    assert src == "vwap10m" and abs(c - px) < 1e-9
    # Thin 10-minute window falls through to 30 minutes.
    old = [{"timestamp": 600 - 1200, "outcomeIndex": 0, "price": 0.55, "size": 2000}]
    c, src = close_from_trades(trades[:1] + old, 600)  # $9 in the last 10 min, $1100 at 20 min
    assert src == "vwap30m", src
    # t >= 3, not t >= 2. Eight flat games stay unlabeled; eight +8% games are sharp.
    noise, edge = {}, {}
    for i in range(8):
        add_game(noise, {"close0": 0.50, "big": [["N", i, 0, "BUY", 0.50, 2000], ["N", i, 0, "BUY", 0.50, 2000]]})
        add_game(edge, {"close0": 0.54, "big": [["E", i, 0, "BUY", 0.50, 2000], ["E", i, 0, "BUY", 0.50, 2000]]})
    sn, sd, _st, _f = classify_all(noise)
    en, ed, est, ef = classify_all(edge)
    assert sn == [] and sd == [], (sn, sd)
    assert en == ["E"] and est["E"]["n"] == 8 and est["E"]["trades"] == 16 and est["E"]["t"] >= 3, est["E"]
    # t = 2.4 over 20 games clears the old bar and fails the new one.
    mild = {"M": [20, 0.4, 0.035778, 20, 40]}
    mn, _md, mst, _mf = classify_all(mild)
    assert 2.0 <= mst["M"]["t"] < 3, mst["M"]
    assert mn == []
    # Old per-trade file is not mixed into the new aggregates.
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "w.json")
    json.dump({"wallets": {"Z": [40, 1.2, 0.2, 8]}, "processed": ["nfl-a-b-2024-09-05"], "sharp": ["Z"]}, open(p, "w"))
    global OUT
    OUT = p
    S = load_state(p)
    assert S["wallets"] == {} and S["processed"] == [] and S["schema"] == 2
    # `end` walk: a getter that only returns rows at or before the requested end, and
    # refuses offset >= 10000, still reaches a trade older than the cap window.
    def fake_get(url):
        end = int(re.search(r"end=(\d+)", url).group(1))
        off = int(re.search(r"offset=(\d+)", url).group(1))
        if off >= OFFSET_CAP: return []
        # One trade per second, newest at 50_000. A full page is always returned
        # until the clock runs out, matching the API (it does not return a short
        # page just because the caller asked for an `end` inside the book).
        newest = 50000
        base = max(0, newest - end + 1)
        rows = []
        for j in range(PAGE):
            ts = newest - (base + off + j)
            if ts <= 0: break
            rows.append({"timestamp": ts, "price": 0.5, "outcomeIndex": 0, "size": 1, "side": "BUY", "proxyWallet": "Z"})
        return rows
    rows = fetch_trades("cid", 50000, getter=fake_get, page_cap=40)
    assert rows, "walk returned nothing"
    assert min(t["timestamp"] for t in rows) < 50000 - OFFSET_CAP, min(t["timestamp"] for t in rows)
    print("build_pm_wallets selftest ok")
    return 0


if __name__ == "__main__":
    main()
