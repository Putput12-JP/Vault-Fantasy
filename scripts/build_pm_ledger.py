#!/usr/bin/env python3
"""Polymarket sharp-wallet ledger: every full-game NBA / NFL / CFB bet a tracked wallet held at tip, graded against the market's resolution.

This is PR 1 of the side-card build (docs/pm-ledger.md). It writes the raw material only. Nothing here decides who is "proven"; that is
computed point in time from these rows by the side-card step. Sharp money stays context only (CLAUDE.md): this file grades wallets, not picks.

What one row means
  A wallet's NET holding of one outcome of one full-game market (moneyline, spread, total) at the lock time, cutoff = game start - 15 min
  (the same T-15 freeze SharpFlow uses). Fills after the cutoff are in-play trading and are ignored (counted in `post`). A position fully
  sold before the cutoff is not a bet and writes no row (counted in the run summary). Stake = average-cost basis of the shares still held at
  the cutoff. pnl = shares x resolved price - stake. A wallet holding both outcomes at the cutoff writes both legs, each flagged `hedged`.

Look-ahead rules (the traps the plan review found)
  - settled_at is the market's Gamma `closedTime`, never the wallet's `last_event_at` (that is the wallet's last trade, often pre-game).
  - A row is written only once the market is closed and resolved; until then its fills wait in pending.json.
  - Every universe snapshot is dated, and first_seen.json records the first date each wallet entered the universe. A row whose cutoff is
    before that date is `src:"backfill"` (the wallet was chosen with hindsight); otherwise `src:"forward"`. Consumers must keep them apart.
  - user-stats (market-maker features) are snapshotted per date, never overwritten, so an exclusion can be applied as of a date.

Files under --out (a checkout of the never-force-pushed `sharp-history` branch, folder pm_ledger/):
  universe/<date>.json        the wallets polled that day and why (leaderboard rank and pnl, or a Vault wallet file)
  first_seen.json             {wallet: first universe date}; dates are only ever added
  user_stats/<date>.jsonl     one /v2/user-stats row per wallet polled that day
  markets/<sport>.json        Gamma facts per condition (type, line, outcomes, game start, closed time, resolved prices)
  bets/<sport>/<YYYY-MM>.jsonl the graded rows, by month of game start; append-only, keyed wallet|condition|outcome_index
                              (slug, outcome name and line are looked up in markets/<sport>.json by `cid`; cutoff = gst - 900)
  pending.json                fills of positions whose market has not resolved yet
  state.json                  per-wallet sync cursors, so a capped run resumes where it stopped
  summary.json                counts, request totals, and the rate-limit observations of the last run

Requests stay polite and bounded: a global pace, Retry-After honoured on 429/503, and --max-req stops the run cleanly (state saved, nothing
half-written). Data rows are merged, never overwritten: a key already in the ledger is never rewritten, and a run that finds a settled row
changing exits 2 without writing.

usage: build_pm_ledger.py --out DIR [--sports nba,nfl,cfb] [--lb-all 1500] [--lb-month 1000] [--wallets N] [--max-req N]
                          [--pace 0.25] [--workers 4] [--rate-probe N] [--today YYYY-MM-DD] [--dry-run]
"""
import argparse, datetime as dt, json, os, sys, threading, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pm_data_api import PM_DATA, PMDataError  # noqa: E402

GAMMA = "https://gamma-api.polymarket.com"
UA = {"User-Agent": "Mozilla/5.0 (compatible; vault-ledger)"}
SPORT_PREFIX = {"nba": "nba-", "nfl": "nfl-", "cfb": "cfb-"}
FULL_GAME = ("moneyline", "spreads", "totals")
CUTOFF_SEC = 15 * 60                      # SharpFlow T-15 freeze (index.js `_=900*1e3`)
MIN_MONTHLY_PNL = 20000                   # SharpFlow seedSportsSharps MIN_MONTHLY_PNL ("monthly hot")
WALLET_FILES = ("data/pm_wallets.json", "data/pm_wallets_cfb.json", "data/pm_wallets_nba.json")   # their `sharp` and `dull` lists
RANK_FILE = "data/pm_wallet_rank.json"     # Vault's CLV ranker; every wallet it has tiered (proven, probable, watching, dull)
COND_BATCH = 20                           # Data API v2 limit on comma-separated condition ids
GAMMA_BATCH = 50
SERIES = {"nba": 10345, "nfl": 12185, "cfb": 12756}   # Gamma sports series ids (GET /sports); games carry tag 100639
GAME_TAG = 100639
FAT_TICKET_USD = 2000      # SharpFlow discoverScanSupplement MIN_POSITION_USD: a holder this big on a full-game market is a candidate
DISCOVER_AHEAD = 36 * 3600 # games starting within the next 36 hours (today's slate plus tomorrow's early games)
EPS = 1e-6


class Budget(Exception):
    pass


class Client:
    """Sequential-safe HTTP with a global pace, Retry-After backoff, and a hard request cap."""

    def __init__(self, pace, max_req, deadline=None):
        self.pace, self.max_req, self.deadline = pace, max_req, deadline
        self.lock = threading.Lock()
        self.next_at = 0.0
        self.n = 0
        self.status = {}
        self.retry_after = []
        self.lat = []

    def get(self, url, tries=5):
        for attempt in range(tries):
            with self.lock:
                if self.max_req and self.n >= self.max_req:
                    raise Budget("max_req")
                if self.deadline and time.time() >= self.deadline:
                    raise Budget("max_secs")
                self.n += 1
                wait = self.next_at - time.time()
                self.next_at = max(time.time(), self.next_at) + self.pace
            if wait > 0:
                time.sleep(wait)
            t0 = time.time()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                    body = r.read()
                    self._log(r.status, time.time() - t0)
                    return json.loads(body)
            except urllib.error.HTTPError as e:
                self._log(e.code, time.time() - t0)
                if e.code in (429, 503):
                    ra = e.headers.get("Retry-After")
                    secs = float(ra) if ra and ra.replace(".", "", 1).isdigit() else 2 ** attempt
                    with self.lock:
                        self.retry_after.append(secs)
                        self.next_at = max(self.next_at, time.time() + secs)
                    continue
                if e.code == 400 or e.code == 404:
                    return None
                time.sleep(2 ** attempt)
            except (urllib.error.URLError, TimeoutError, ValueError):
                self._log("err", time.time() - t0)
                time.sleep(2 ** attempt)
        return None

    def _log(self, code, secs):
        with self.lock:
            self.status[str(code)] = self.status.get(str(code), 0) + 1
            self.lat.append(secs)

    def stats(self):
        lat = sorted(self.lat)
        pct = lambda q: round(lat[min(len(lat) - 1, int(q * len(lat)))], 3) if lat else None
        return {"requests": self.n, "status": self.status, "retry_after": self.retry_after[:50],
                "lat_p50": pct(.5), "lat_p95": pct(.95)}


# ---------- pure logic (unit-tested in tests/test_pm_ledger.py) ----------

def sport_of(slug):
    for s, p in SPORT_PREFIX.items():
        if (slug or "").startswith(p):
            return s
    return None


def parse_ts(s):
    """Gamma timestamps come as '2026-06-14 00:30:00+00' or ISO with Z. Returns epoch seconds or None."""
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00").replace(" ", "T", 1)
    if s.endswith("+00"):
        s += ":00"
    try:
        return int(dt.datetime.fromisoformat(s).timestamp())
    except ValueError:
        return None


def market_fact(m):
    """Gamma market -> the few facts the ledger keeps. `final` is set only when the market is closed AND resolved."""
    def arr(v):
        try:
            return json.loads(v) if isinstance(v, str) else (v or [])
        except ValueError:
            return []
    outs, prices = arr(m.get("outcomes")), arr(m.get("outcomePrices"))
    final = None
    if m.get("closed") and (m.get("umaResolutionStatus") or "").lower() == "resolved":
        try:
            fp = [float(x) for x in prices]
            if len(fp) == len(outs) and all(x in (0.0, 0.5, 1.0) for x in fp):
                final = fp
        except ValueError:
            final = None
    return {"slug": m.get("slug"), "mt": m.get("sportsMarketType"), "line": m.get("line"), "outs": outs,
            "gst": parse_ts(m.get("gameStartTime")), "closed_at": parse_ts(m.get("closedTime")) if m.get("closed") else None,
            "final": final}


def holding_at(fills, cutoff):
    """Average-cost holdings per outcome_index at `cutoff` from activity rows.

    fills: v2 activity rows (TRADE / SPLIT / MERGE / CONVERSION) for ONE condition in the API's ASC order (block time, then
    sequence). The sort below is stable on timestamp alone, so same-block rows keep that order: a buy-then-sell in one block nets to 0.
    Returns {oi: {"sh", "cost", "first", "last", "exited", "post"}}, plus "_conv" when a pre-cutoff CONVERSION appears (left ungraded)
    and "_split" when a pre-cutoff SPLIT or MERGE appears. SPLIT of X mints X of each outcome booked at 0.5, MERGE burns X of each at 0.5
    (the Data API's avg-price convention); once one leg of a split is sold that booked cost is not the wallet's cash, so a `_split` row
    carries split=true and its stake must be kept out of dollar ROI."""
    hold = {}
    flags = {}
    for f in sorted(fills, key=lambda r: r.get("timestamp") or 0):
        ts, typ = f.get("timestamp") or 0, (f.get("type") or "TRADE").upper()
        if typ == "CONVERSION":
            if ts < cutoff:
                flags["_conv"] = True
            continue
        if typ in ("SPLIT", "MERGE") and ts < cutoff:
            flags["_split"] = True
        legs = []
        if typ == "TRADE":
            size = float(f.get("size") or 0)
            usdc = f.get("usdc_size")
            usdc = float(usdc) if usdc is not None else size * float(f.get("price") or 0)
            legs.append((f.get("outcome_index"), (f.get("side") or "").upper(), size, usdc))
        elif typ in ("SPLIT", "MERGE"):
            size = float(f.get("size") or 0)
            side = "BUY" if typ == "SPLIT" else "SELL"
            legs += [(0, side, size, size * .5), (1, side, size, size * .5)]
        else:
            continue
        for oi, side, size, usdc in legs:
            if oi is None or size <= 0:
                continue
            h = hold.setdefault(int(oi), {"sh": 0.0, "cost": 0.0, "first": None, "last": None, "exited": 0.0, "post": 0.0})
            if ts >= cutoff:
                h["post"] += size
                continue
            if side == "BUY":
                h["sh"] += size
                h["cost"] += usdc
                h["first"] = h["first"] or ts
                h["last"] = ts
            elif side == "SELL" and h["sh"] > EPS:
                take = min(size, h["sh"])
                h["cost"] -= h["cost"] * take / h["sh"]
                h["sh"] -= take
                h["exited"] += take
    hold.update(flags)
    return hold


def bet_rows(wallet, cid, fact, fills, first_seen_ts):
    """Graded rows for one wallet x one resolved condition. Returns (rows, note) where note explains an empty result."""
    if not fact or fact.get("mt") not in FULL_GAME:
        return [], "not_full_game"
    if fact.get("gst") is None:
        return [], "no_game_start"
    if fact.get("final") is None or fact.get("closed_at") is None:
        return [], "unresolved"
    cutoff = fact["gst"] - CUTOFF_SEC
    hold = holding_at(fills, cutoff)
    split = hold.pop("_split", False)
    if hold.pop("_conv", False):
        return [], "conversion"
    held = {oi: h for oi, h in hold.items() if h["sh"] > EPS and h["cost"] > EPS}
    if not held:
        return [], "exited_or_no_pretip"
    sport = sport_of(fact.get("slug"))
    rows = []
    for oi, h in sorted(held.items()):
        if oi >= len(fact["final"]):
            continue
        px = fact["final"][oi]
        pnl = h["sh"] * px - h["cost"]
        rows.append({
            "w": wallet, "cid": cid, "oi": oi, "sport": sport, "mt": fact["mt"],
            "gst": fact["gst"], "settled_at": fact["closed_at"],
            "sh": round(h["sh"], 4), "stake": round(h["cost"], 2), "avg": round(h["cost"] / h["sh"], 4),
            "res": "push" if px == .5 else ("win" if px == 1 else "loss"), "pnl": round(pnl, 2),
            "first": h["first"], "last": h["last"], "exited": round(h["exited"], 4), "post": round(h["post"], 4),
            "hedged": len(held) > 1, "split": split,
            "src": "forward" if first_seen_ts is not None and first_seen_ts <= cutoff else "backfill",
        })
    return rows, None


def row_key(r):
    return f"{r['w']}|{r['cid']}|{r['oi']}"


def merge_rows(existing, new):
    """Append-only merge. existing/new: {key: row}. Returns (added, conflicts); a key already present is never rewritten."""
    added, conflicts = {}, []
    for k, r in new.items():
        old = existing.get(k)
        if old is None:
            added[k] = r
        elif (old.get("res"), old.get("stake"), old.get("settled_at")) != (r.get("res"), r.get("stake"), r.get("settled_at")):
            conflicts.append(k)
    return added, conflicts


def dedupe_positions(rows):
    """OPEN (superset incl. REDEEMABLE / REDEEMABLE_LOST) and CLOSED can list the same holding; key on condition + outcome index."""
    out = {}
    for r in rows:
        out.setdefault((r.get("condition_id"), r.get("outcome_index")), r)
    return list(out.values())


# ---------- io ----------

def jload(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def jsave(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, path)


def load_bets(root, sport):
    d = os.path.join(root, "bets", sport)
    out = {}
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".jsonl"):
                with open(os.path.join(d, fn)) as f:
                    for line in f:
                        if line.strip():
                            r = json.loads(line)
                            out[row_key(r)] = r
    return out


def append_bets(root, rows):
    by = {}
    for r in rows:
        month = dt.datetime.fromtimestamp(r["gst"], dt.timezone.utc).strftime("%Y-%m")
        by.setdefault((r["sport"], month), []).append(r)
    for (sport, month), rs in by.items():
        p = os.path.join(root, "bets", sport, month + ".jsonl")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a") as f:
            for r in sorted(rs, key=lambda r: (r["gst"], row_key(r))):
                f.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")


def pages(cli, path, params, max_pages, trunc=None):
    """Yield v2 data pages. When the page cap stops a feed that still has more, `trunc` (a list) gets the path appended.
    A page that cannot be fetched raises PMDataError, so "no rows" and "could not ask" never look the same."""
    cursor = None
    for i in range(max_pages):
        q = dict(params)
        if cursor:
            q["cursor"] = cursor
        j = cli.get(f"{PM_DATA}{path}?{urllib.parse.urlencode(q)}")
        if not isinstance(j, dict) or "data" not in j:
            raise PMDataError(f"{path} {params.get('user') or params.get('condition') or ''}: no response")
        yield j.get("data") or []
        pg = j.get("pagination") or {}
        cursor = pg.get("next_cursor")
        if not (pg.get("has_more") and cursor):
            return
        if i == max_pages - 1 and trunc is not None:
            trunc.append(path)


# ---------- stages ----------

def build_universe(cli, a):
    uni = {}

    def walk(period, depth, keep):
        n = 0
        for rows in pages(cli, "/leaderboard", {"category": "sports", "time_period": period, "sort_by": "PNL", "limit": 1000},
                          max_pages=max(1, -(-depth // 1000))):
            for r in rows:
                if n >= depth:
                    return
                n += 1
                w = (r.get("user_id") or "").lower()
                if w and keep(r):
                    u = uni.setdefault(w, {"name": r.get("user_name"), "why": []})
                    u["why"].append({"board": period, "rank": r.get("rank"), "pnl": round(r.get("pnl") or 0)})
    if a.lb_all:
        walk("all", a.lb_all, lambda r: (r.get("pnl") or 0) > 0)
    if a.lb_month:
        walk("month", a.lb_month, lambda r: (r.get("pnl") or 0) >= MIN_MONTHLY_PNL)
    # Vault's own classified wallets. Not the files' full `wallets` maps: those hold every scored taker (about 7,000), not a judgement.
    for fn in WALLET_FILES:
        j = jload(fn, None) or {}
        for cls in ("sharp", "dull"):
            for w in j.get(cls) or []:
                w = w if isinstance(w, str) else (w.get("w") or w.get("wallet") or "") if isinstance(w, dict) else ""
                if w.startswith("0x"):
                    uni.setdefault(w.lower(), {"name": None, "why": []})["why"].append({"file": fn, "cls": cls})
    rk = (jload(RANK_FILE, None) or {}).get("wallets") or {}
    for w, v in rk.items():
        if isinstance(v, dict) and v.get("tier"):
            uni.setdefault(w.lower(), {"name": None, "why": []})["why"].append({"file": RANK_FILE, "tier": v["tier"]})
    return uni


def fat_tickets(events, holder_pages, now):
    """Pure part of discovery. events: Gamma events (with markets). holder_pages: v2 /holders `data` lists.
    Returns {wallet: {"usd", "cid", "both"}} for holders whose position on one full-game market, valued at the market's current
    price, is at least FAT_TICKET_USD. `both` marks a wallet holding both outcomes of that market."""
    tok = {}
    for e in events:
        for m in e.get("markets") or []:
            f = market_fact(m)
            if f["mt"] not in FULL_GAME or not f["gst"] or not (now <= f["gst"] <= now + DISCOVER_AHEAD):
                continue
            try:
                ids, px = json.loads(m.get("clobTokenIds") or "[]"), [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
            except ValueError:
                continue
            for oi, t in enumerate(ids):
                if oi < len(px):
                    tok[str(t)] = (m.get("conditionId"), oi, px[oi])
    per = {}
    for page in holder_pages:
        for grp in page or []:
            for h in grp.get("holders") or []:
                hit = tok.get(str(h.get("token_id") or grp.get("token_id")))
                w = (h.get("proxy_wallet") or "").lower()
                if not hit or not w.startswith("0x"):
                    continue
                cid, oi, px = hit
                r = per.setdefault((w, cid), {"usd": 0.0, "ois": set()})
                r["usd"] += float(h.get("amount") or 0) * px
                r["ois"].add(oi)
    out = {}
    for (w, cid), r in per.items():
        if r["usd"] >= FAT_TICKET_USD and r["usd"] > out.get(w, {}).get("usd", 0):
            out[w] = {"usd": round(r["usd"]), "cid": cid, "both": len(r["ois"]) > 1}
    return out


def discover(cli, a, known, now):
    """Wallets with a fat ticket on an upcoming full-game NBA / NFL / CFB market, kept when their all-time AND this-month sports
    PnL are both positive (SharpFlow's discovery gate). Returns {wallet: universe entry} for wallets not already known."""
    events = []
    iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for s in a.sports:
        cursor = None
        for _ in range(6):
            # start_time_* bounds the game time (start_date_* is market creation time and drops tonight's games)
            q = {"series_id": SERIES[s], "tag_id": GAME_TAG, "closed": "false", "limit": 50,
                 "start_time_min": iso(now), "start_time_max": iso(now + DISCOVER_AHEAD)}
            if cursor:
                q["after_cursor"] = cursor
            j = cli.get(f"{GAMMA}/events/keyset?{urllib.parse.urlencode(q)}")
            if not isinstance(j, dict):
                raise PMDataError(f"gamma events {s}: no response")
            events += j.get("events") or []
            cursor = j.get("next_cursor")
            if not cursor or not j.get("events"):
                break
    cids = sorted({m.get("conditionId") for e in events for m in e.get("markets") or []
                   if m.get("sportsMarketType") in FULL_GAME and m.get("conditionId")
                   and now <= (parse_ts(m.get("gameStartTime")) or 0) <= now + DISCOVER_AHEAD})
    holder_pages = []
    for i in range(0, len(cids), COND_BATCH):
        for rows in pages(cli, "/holders", {"condition": ",".join(cids[i:i + COND_BATCH]), "limit": 1000}, 5):
            holder_pages.append(rows)
    fat = fat_tickets(events, holder_pages, now)
    out = {}
    for w, t in sorted(fat.items(), key=lambda kv: -kv[1]["usd"]):
        if w in known:
            continue
        lb = {}
        for period in ("all", "month"):
            j = cli.get(f"{PM_DATA}/leaderboard?category=sports&time_period={period}&user={w}")
            d = (j or {}).get("data") if isinstance(j, dict) else None
            lb[period] = (d or {}).get("pnl")
        if (lb["all"] or 0) > 0 and (lb["month"] or 0) > 0:
            out[w] = {"name": None, "why": [{"fat_ticket": t["usd"], "cid": t["cid"], "both_sides": t["both"],
                                              "all_pnl": round(lb["all"]), "month_pnl": round(lb["month"])}]}
    return out, {"markets": len(cids), "fat_tickets": len(fat), "new_candidates": sum(1 for w in fat if w not in known),
                 "added": len(out)}


OVERLAP = 3 * 86400        # incremental position reads go back 3 days before the high-water mark, so a late fill or redeem is not missed
FILL_SETTLE = 30 * 60      # fills are read only once the cutoff is 30 min old, so the activity index has every pre-cutoff fill
GAMMA_MISS_MAX = 3         # a condition Gamma does not know on 3 separate runs is dropped (counted as gamma_missing)


def walk_positions(cli, w, a, ws, trunc, add):
    """Read the wallet's OPEN (superset: open, redeemable, redeemable-lost; archived markets included) and CLOSED books.

    Both are read NEWEST first: the API times out (503 request_timeout) on oldest-first reads of a heavy OPEN book, even at 50 rows
    a page, while newest-first answers in well under a second. Per book the state keeps `hw` (everything newer than it has been
    read) and an optional backlog window [lo, hi] still to read. Each visit reads the new window [hw - OVERLAP, now], then the
    backlog. Progress is saved page by page; a capped or interrupted read leaves the unread part as the backlog, so nothing older is
    ever skipped. Each page's sport rows go to `add` first."""
    for status in ("OPEN", "CLOSED"):
        b = ws.setdefault("b_" + status, {})
        wins = [("new", max(1, b["hw"] - OVERLAP) if b.get("hw") else 1, None)]
        if b.get("hi") is not None:
            wins.append(("backlog", b["lo"], b["hi"]))
        for kind, lo, hi in wins:
            q = {"user": w, "status": status, "limit": 1000, "sort_by": "TIMESTAMP", "sort_direction": "DESC", "start": lo}
            if hi is not None:
                q["end"] = hi
            if status == "OPEN":
                q["include_archived"] = "true"
            cut, low, done = [], None, False
            try:
                for rows in pages(cli, "/positions", q, a.max_pages, cut):
                    for r in rows:
                        t = int(r.get("last_event_at") or 0)
                        if kind == "new":
                            b["hw_next"] = max(b.get("hw_next") or 0, t)
                        low = t if low is None else min(low, t)
                    for r in dedupe_positions([r for r in rows if sport_of(r.get("slug")) in a.sports]):
                        add(r)
                done = not cut
            finally:
                if kind == "new" and b.get("hw_next"):
                    if not done:                       # unread part of the new window joins the backlog (re-reading overlap is harmless)
                        b["lo"] = min(lo, b["lo"]) if b.get("hi") is not None else lo
                        b["hi"] = low if low is not None else (b.get("hi") or int(time.time()))
                    b["hw"] = b.pop("hw_next")
                elif kind == "new" and done:
                    b["hw"] = b.get("hw") or 1
                elif kind == "backlog":
                    if done:
                        b.pop("lo", None)
                        b.pop("hi", None)
                    elif low is not None:
                        b["hi"] = low
            if cut:
                trunc.append("/positions:" + status)


def fetch_fills(cli, w, cids, a, wp, now, note):
    """Fills for conditions whose cutoff is FILL_SETTLE old. A chunk the page cap cuts short is split in half and re-read; a single
    condition that still does not fit is dropped as too_many_fills (no row is ever built from a partial fill list)."""
    if not cids:
        return
    cut = []
    got = {c: [] for c in cids}
    for rows in pages(cli, "/activity", {"user": w, "condition": ",".join(cids), "type": "TRADE,SPLIT,MERGE,CONVERSION",
                                         "start": 1, "limit": 1000, "sort_direction": "ASC"}, a.max_pages, cut):
        for x in rows:
            if x.get("condition_id") in got:
                got[x["condition_id"]].append({k: x.get(k) for k in ("timestamp", "type", "side", "size", "usdc_size",
                                                                      "price", "outcome_index", "transaction_hash")})
    if cut:
        if len(cids) == 1:
            note("too_many_fills")
            wp[cids[0]]["drop"] = "too_many_fills"
            return
        h = len(cids) // 2
        fetch_fills(cli, w, cids[:h], a, wp, now, note)
        fetch_fills(cli, w, cids[h:], a, wp, now, note)
        return
    for c in cids:
        wp[c]["fills"] = got[c]
        wp[c]["fetched_for"] = None                  # set by the caller to the cutoff the read covered


def sync_wallet(cli, w, a, st, markets, pend, have, fs_ts, now, note, positions=True):
    """Positions -> sport conditions -> fills once their cutoff has settled -> graded rows when the market resolves.
    positions=False skips the position read (used only by tests and dry runs); normal runs read every wallet ever selected."""
    ws = st.setdefault(w, {})
    trunc = []
    wp = pend.setdefault(w, {})

    def add(r):
        cid = r.get("condition_id")
        if cid and cid not in wp and (w, cid) not in have:
            wp[cid] = {"fills": None}
    if positions:
        walk_positions(cli, w, a, ws, trunc, add)
    need = [cid for cid, p in wp.items() if cid not in markets or markets[cid].get("missing")]
    answered = gamma_facts(cli, need, markets)
    for cid in need:
        if cid in answered:
            continue
        p = wp[cid]
        p["miss"] = p.get("miss", 0) + 1
        markets.setdefault(cid, {"slug": None, "mt": None, "missing": 1})
    for cid in list(wp):
        m = markets.get(cid) or {}
        if m.get("missing"):
            if wp[cid].get("miss", 0) >= GAMMA_MISS_MAX:
                note("gamma_missing")
                del wp[cid]
            continue
        if m.get("mt") not in FULL_GAME:            # props, halves, futures: never fetch their fills
            note("not_full_game")
            del wp[cid]
    ready = []
    for cid, p in wp.items():
        m = markets.get(cid) or {}
        if not m.get("gst") or p.get("drop"):
            continue
        cutoff = m["gst"] - CUTOFF_SEC
        if p.get("fills") is not None and p.get("fetched_for") != cutoff:
            p["fills"] = None                         # Gamma moved the game start: the stored fills answer the wrong cutoff
        if p.get("fills") is None and cutoff + FILL_SETTLE < now:
            ready.append(cid)
    for i in range(0, len(ready), COND_BATCH):
        chunk = ready[i:i + COND_BATCH]
        fetch_fills(cli, w, chunk, a, wp, now, note)
        for c in chunk:
            if wp[c].get("fills") is not None and wp[c].get("fetched_for") is None:
                wp[c]["fetched_for"] = markets[c]["gst"] - CUTOFF_SEC
    if trunc:
        ws["partial"] = sorted(set(trunc))
    elif positions:
        ws.pop("partial", None)                       # this visit read every page: no longer partial
    out = []
    for cid in list(wp):
        p, f = wp[cid], markets.get(cid)
        if p.get("drop"):
            del wp[cid]
            continue
        if f is None or p.get("fills") is None or f.get("final") is None:
            continue                                  # wait for fills and for resolution
        if p.get("fetched_for") != f["gst"] - CUTOFF_SEC:
            continue                                  # game start moved after the read; refetched next run
        rows, why = bet_rows(w, cid, f, p["fills"], fs_ts)
        note(why or "graded")
        out += rows
        del wp[cid]
    return out


def gamma_facts(cli, cids, markets):
    """Fill `markets` for `cids`. Returns the set Gamma actually answered for; a failed request raises PMDataError, so a Gamma
    outage never looks like "unknown market"."""
    answered = set()
    for i in range(0, len(cids), GAMMA_BATCH):
        chunk = cids[i:i + GAMMA_BATCH]
        for closed in ("true", "false"):
            q = "&".join("condition_ids=" + c for c in chunk) + f"&closed={closed}&limit={GAMMA_BATCH}"
            j = cli.get(f"{GAMMA}/markets/keyset?{q}")
            if not isinstance(j, dict) or "markets" not in j:
                raise PMDataError(f"gamma markets {closed}: no response")
            for m in j.get("markets") or []:
                cid = m.get("conditionId")
                if cid:
                    markets[cid] = market_fact(m)
                    answered.add(cid)
    return answered


def refresh_unresolved(cli, markets, pend):
    """Re-ask Gamma about markets that pending fills are waiting on (resolution, or a moved game start)."""
    waiting = {cid for wp in pend.values() for cid in wp
               if markets.get(cid, {}).get("mt") in FULL_GAME and markets[cid].get("final") is None}
    gamma_facts(cli, sorted(waiting), markets)


def rate_probe(cli, n, wallets):
    """Fire n cheap leaderboard lookups at no pace to see where the per-client allowance answers 429/503."""
    saved = cli.pace
    cli.pace = 0
    t0 = time.time()
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: cli.get(f"{PM_DATA}/leaderboard?user={wallets[i % len(wallets)]}", tries=1), range(n)))
    cli.pace = saved
    return {"n": n, "secs": round(time.time() - t0, 2), "status": dict(cli.status)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sports", default="nba,nfl,cfb")
    ap.add_argument("--lb-all", type=int, default=1500, help="depth of the all-time sports PnL board (SharpFlow LB_DEPTH)")
    ap.add_argument("--lb-month", type=int, default=1000, help="depth of the monthly board, kept at pnl >= $20K")
    ap.add_argument("--wallets", type=int, default=0, help="poll only the first N wallets (dry runs)")
    ap.add_argument("--max-req", type=int, default=20000)
    ap.add_argument("--max-secs", type=int, default=7800, help="stop cleanly after this many seconds (below the job timeout)")
    ap.add_argument("--max-pages", type=int, default=20, help="page cap per feed read; a capped read resumes or re-splits")
    ap.add_argument("--pace", type=float, default=0.25, help="seconds between request starts (global)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rate-probe", type=int, default=0)
    ap.add_argument("--today", help="names the dated files only; first_seen is always the real clock")
    ap.add_argument("--discover-only", action="store_true", help="only run fat-ticket discovery and record new wallets")
    ap.add_argument("--dry-run", action="store_true", help="fetch and grade but write nothing; print the summary")
    a = ap.parse_args()
    a.sports = [s for s in a.sports.split(",") if s in SPORT_PREFIX]
    root = a.out
    now = int(time.time())
    today = a.today or dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d")
    cli = Client(a.pace, a.max_req, now + a.max_secs)

    state = jload(os.path.join(root, "state.json"), {})
    pend = jload(os.path.join(root, "pending.json"), {})
    first_seen = jload(os.path.join(root, "first_seen.json"), {})     # {wallet: epoch seconds the wallet was first selected}
    markets = {}
    for s in a.sports:
        markets.update(jload(os.path.join(root, "markets", s + ".json"), {}))
    existing = {}
    for s in a.sports:
        existing.update(load_bets(root, s))
    have = {(r["w"], r["cid"]) for r in existing.values()}            # graded once, never re-read

    t0 = time.time()
    summary = {"date": today, "run_at": now, "sports": a.sports, "stopped": None}
    try:
        uni = build_universe(cli, a)
    except (PMDataError, Budget) as e:
        print(f"::error::universe fetch failed: {e!r}; nothing written")
        return 1
    if not uni:
        print("::error::empty universe (leaderboard returned nothing); nothing written")
        return 1
    try:
        found, summary["discover"] = discover(cli, a, set(uni) | set(first_seen), now)
        uni.update(found)
    except (PMDataError, Budget) as e:
        summary["discover"] = {"error": repr(e)}       # discovery is additive; the ledger still runs without it
    if a.discover_only:
        order, former = [], []
    selected_at = int(time.time())                                    # the moment today's selection was known
    new_fs = {w: selected_at for w in uni if w not in first_seen}
    fs = {**first_seen, **new_fs}
    best = lambda w: min([x["rank"] for x in uni.get(w, {}).get("why", []) if x.get("rank")] or [10 ** 9])
    # Today's universe by rank, then every wallet ever selected before. Once selected, a wallet is read on every run whether or not
    # it is still on a board, so a forward row never depends on the wallet having kept winning.
    if not a.discover_only:
        order = sorted(uni, key=lambda w: (best(w), w))
        if a.wallets:
            order = order[:a.wallets]
        former = sorted(w for w in fs if w not in uni and (pend.get(w) or not a.wallets))
        if a.wallets:
            former = [w for w in former if pend.get(w)]

    if a.rate_probe:
        summary["rate_probe"] = rate_probe(cli, a.rate_probe, order)
        cli.status = {}

    stats_rows, graded, notes, failed, reached = [], {}, {}, [], set()
    lock = threading.Lock()

    def note(k):
        with lock:
            notes[k] = notes.get(k, 0) + 1

    def one(job):
        w, positions = job
        if summary["stopped"]:
            return
        try:
            j = cli.get(f"{PM_DATA}/user-stats?user={w}")
            rows = sync_wallet(cli, w, a, state, markets, pend, have, fs.get(w), now, note, positions)
            with lock:
                reached.add(w)
                if isinstance(j, dict) and j.get("data"):
                    stats_rows.append({"w": w, "date": today, "at": now, **j["data"]})
                for r in rows:
                    graded[row_key(r)] = r
        except Budget as e:
            with lock:
                summary["stopped"] = summary["stopped"] or str(e) or "budget"
        except PMDataError as e:
            with lock:
                failed.append([w, str(e)])

    try:
        if not a.discover_only:
            refresh_unresolved(cli, markets, pend)
    except Budget as e:
        summary["stopped"] = str(e) or "budget"
    except PMDataError as e:
        failed.append(["gamma-refresh", str(e)])
    with ThreadPoolExecutor(max(1, a.workers)) as ex:
        list(ex.map(one, [(w, True) for w in order + former]))

    added, conflicts = merge_rows(existing, graded)
    by_sport = {}
    for r in added.values():
        b = by_sport.setdefault(r["sport"], {"rows": 0, "wallets": set(), "win": 0, "loss": 0, "push": 0, "stake": 0.0, "pnl": 0.0,
                                             "forward": 0, "backfill": 0, "hedged": 0, "split": 0})
        b["rows"] += 1
        b["wallets"].add(r["w"])
        b[r["res"]] += 1
        b["stake"] += r["stake"]
        b["pnl"] += r["pnl"]
        b[r["src"]] += 1
        b["hedged"] += r["hedged"]
        b["split"] += r["split"]
    for b in by_sport.values():
        b["wallets"] = len(b["wallets"])
        b["stake"], b["pnl"] = round(b["stake"]), round(b["pnl"])
    summary.update({
        "universe": len(uni), "polled": len(order), "former_polled": len(former), "reached": len(reached),
        "not_reached": len(order) + len(former) - len(reached), "new_first_seen": len(new_fs), "user_stats": len(stats_rows),
        "added_rows": len(added), "n_conflicts": len(conflicts), "conflicts": conflicts[:20], "by_sport": by_sport,
        "conditions": notes, "pending_wallets": sum(1 for v in pend.values() if v),
        "pending_conditions": sum(len(v) for v in pend.values()), "failed": failed[:20], "n_failed": len(failed),
        "partial": sorted(w for w in state if state[w].get("partial")), "markets_known": len(markets),
        "secs": round(time.time() - t0, 1), "http": cli.stats(),
    })
    if conflicts:
        # Never rewrite a settled row: the old row stays, the disagreement is quarantined for a person to read, the run still saves.
        print(f"::warning::{len(conflicts)} graded rows disagree with the ledger; kept the ledger rows, see conflicts.jsonl")
    if a.dry_run:
        print(json.dumps(summary, indent=1, default=str))
        return 0

    append_bets(root, list(added.values()))
    if conflicts:
        with open(os.path.join(root, "conflicts.jsonl"), "a") as f:
            for k in conflicts:
                f.write(json.dumps({"at": now, "key": k, "ledger": existing[k], "new": graded[k]}, sort_keys=True) + "\n")
    first_seen.update(new_fs)
    jsave(os.path.join(root, "first_seen.json"), first_seen)
    upath = os.path.join(root, "universe", today + ".json")
    prev = jload(upath, None)
    jsave(upath, {"date": today, "selected_at": selected_at, "lb_all": a.lb_all, "lb_month": a.lb_month,
                  "min_monthly_pnl": MIN_MONTHLY_PNL,
                  "wallets": {**((prev or {}).get("wallets") or {}), **uni}})   # same-day re-run adds, never drops
    if stats_rows:
        p = os.path.join(root, "user_stats", today + ".jsonl")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        seen = set()
        if os.path.exists(p):
            with open(p) as f:
                seen = {json.loads(l)["w"] for l in f if l.strip()}
        with open(p, "a") as f:
            for r in sorted(stats_rows, key=lambda r: r["w"]):
                if r["w"] not in seen:
                    f.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")
    for s in a.sports:
        jsave(os.path.join(root, "markets", s + ".json"), {c: m for c, m in markets.items() if sport_of(m.get("slug")) == s
                                                           and m.get("mt") in FULL_GAME})
    jsave(os.path.join(root, "pending.json"), {w: v for w, v in pend.items() if v})
    jsave(os.path.join(root, "state.json"), state)
    jsave(os.path.join(root, "summary_discover.json" if a.discover_only else "summary.json"), summary)
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
