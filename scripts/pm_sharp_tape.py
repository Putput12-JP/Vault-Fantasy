#!/usr/bin/env python3
"""
Sharp tape (Sharps audit, Step 3; docs/sharp-speed-prereg.md): what a follower can actually get when a CLV-tiered wallet buys.

The tiers (scripts/pm_clv_tiers.py, docs/pm-clv-tiers.md) say sharp wallets get better entry prices than the close. They do not say a
follower can. This watches the wallets and, the moment a pre-game buy shows up in Polymarket's trade feed, reads the order book: the ASK a
follower would pay, the depth behind it, and the price for $100. It also reads the book again 1, 5 and 15 minutes later (markouts) so the
edge's decay is on record. The close comes later from data/pm_closes.json, and scripts/grade_sharp_tape.py grades CLV = close - the ask.

  wallets   every sharp and dull wallet of the sport's tier file as of the start of the run, plus the CONTROL most active `mid` wallets (what
            any wallet's buy is worth to a follower, the baseline a sharp must beat). Wallets, tiers and the control are frozen for the run.
  trades    GET data-api /v2/trades?user=W&limit=20, every INTERVAL seconds. BUYs only, full-game NBA and NFL moneyline / spread / total,
            before the game starts, newer than the wallet's last seen trade. Sells are not read (an exit is not a follow).
  detection `seen` is the time this script first read the trade, `lat` = seen - the trade's own timestamp. The book is read right then,
            both outcomes (the second is the price a follower pays to FADE the wallet).
  late      a trade first read more than LATE_S after it happened (a gap between runs, a slow cycle) is flagged `late` and kept, but the
            test reads only on-time rows: a follower would not have been there. NOTE the feed itself lags a trade by 2 to 4 minutes.

Rows append to <out>/<sport>/<UTC date>.jsonl, one JSON object per line, never rewritten:
  k "t"  a detected trade with its books;   k "m"  a markout read of the same trade's books (dt = 60, 300, 900 seconds after `seen`).

Stored data only: a missing book leaves its fields null; nothing is estimated. Context only (CLAUDE.md).

Usage: python3 scripts/pm_sharp_tape.py --tiers nba=FILE nfl=FILE --out DIR [--commit] [--loop --max-minutes 170] [--interval 45]
"""
import argparse, collections, concurrent.futures as cf, datetime as dt, json, os, re, subprocess, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DATA = "https://data-api.polymarket.com/v2"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
CONTROL = 40                  # most active `mid` wallets per sport, watched as the baseline
LATE_S = 300                  # first read more than this after the trade: flagged late. The trade feed itself shows a buy 2 to 4
                              # minutes after it happens (smoke run 2026-11-18: 186 to 239 s), so 300 s is the realistic floor, not a choice
MARKOUTS = (60, 300, 900)
FOLLOW_USD = 100              # the book walk: price for this many dollars
SPORTS = ("nba", "nfl")
FULL_GAME = re.compile(r"^(nba|nfl)-[a-z0-9]+-[a-z0-9]+-\d{4}-\d{2}-\d{2}(-(spread|total)-[a-z0-9-]+)?$")
MT = {"moneyline": "ml", "spreads": "spread", "totals": "total"}


def http(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "vault-sharp-tape"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001
        return None


# ---------- pure logic (tests/test_pm_sharp_tape.py) ----------

def book_read(book, usd=FOLLOW_USD):
    """{bid, ask, ask_sz, vw}: the best bid, the best ask and its size (shares), and the average price paid for `usd` dollars of asks walked
    from the best up (None when the book is too thin to fill it). None fields for a missing or empty book. Prices are strings in the feed."""
    out = {"bid": None, "ask": None, "ask_sz": None, "vw": None}
    if not isinstance(book, dict):
        return out
    try:
        bids = [(float(x["price"]), float(x["size"])) for x in book.get("bids") or []]
        asks = sorted((float(x["price"]), float(x["size"])) for x in book.get("asks") or [])
    except (KeyError, TypeError, ValueError):
        return out
    if bids:
        out["bid"] = max(p for p, _ in bids)
    if asks:
        out["ask"], out["ask_sz"] = asks[0]
        left, cost, shares = float(usd), 0.0, 0.0
        for p, s in asks:
            take = min(s, left / p)
            cost += take * p
            shares += take
            left -= take * p
            if left <= 1e-9:
                break
        out["vw"] = round(cost / shares, 4) if left <= 1e-9 and shares else None
    return out


def accept(trade, facts, now):
    """(market facts, reason). Reason is None for a trade to record: a BUY of a full-game NBA/NFL market that has not started."""
    if not isinstance(trade, dict) or trade.get("side") != "BUY":
        return None, "not_buy"
    if not FULL_GAME.match(trade.get("slug") or ""):
        return None, "not_full_game"
    f = (facts.get(trade.get("event_slug")) or {}).get(trade.get("condition_id"))
    if not f:
        return None, "no_market"
    if f["gst"] is None or trade["timestamp"] >= f["gst"]:
        return None, "in_play"
    return f, None


def trade_row(w, tier, sport, trade, f, seen, books, opp):
    """One `t` row. books / opp: book_read() of the bought token and of the opposite outcome's token."""
    ts = int(trade["timestamp"])
    return {"k": "t", "key": f"{trade.get('transaction_hash')}|{trade.get('token_id')}", "w": w, "tier": tier, "sport": sport,
            "ev": trade.get("event_slug"), "cid": trade.get("condition_id"), "mt": f["mt"], "line": f["line"], "outs": f["outs"],
            "oi": trade.get("outcome_index"), "px": trade.get("price"), "sz": trade.get("size"),
            "usd": round(float(trade.get("size") or 0) * float(trade.get("price") or 0), 2), "ts": ts, "seen": int(seen), "lat": int(seen) - ts,
            "late": int(seen) - ts > LATE_S, "gst": f["gst"],
            "ask": books["ask"], "ask_sz": books["ask_sz"], "bid": books["bid"], "vw": books["vw"],
            "opp_ask": opp["ask"], "opp_bid": opp["bid"], "opp_vw": opp["vw"]}


def watch_list(tiers, control=CONTROL):
    """{wallet: tier} from one sport's tier file ({"wallets": {w: {tier, n, ...}}}): every sharp and dull wallet, plus the `control` most
    active mid wallets (most games)."""
    ws = (tiers or {}).get("wallets") or {}
    out = {w: v["tier"] for w, v in ws.items() if v.get("tier") in ("sharp", "dull")}
    mid = sorted((w for w, v in ws.items() if v.get("tier") == "mid"), key=lambda w: (-ws[w]["n"], w))[:control]
    out.update({w: "mid" for w in mid})
    return out


# ---------- io ----------

def parse_ts(s):
    """Gamma's start times: '2026-11-19 00:00:00+00' or '2026-11-19T00:00:00Z' -> epoch seconds. ValueError when unreadable."""
    s = s.strip().replace("Z", "+00:00")
    if re.search(r"[+-]\d\d$", s):
        s += ":00"
    return int(dt.datetime.fromisoformat(s).timestamp())


def event_facts(slug, get=http):
    """{condition id: {mt, line, outs, toks, gst}} for the full-game markets of one Gamma event, or None when it cannot be read."""
    j = get(f"{GAMMA}/events?slug={urllib.parse.quote(slug)}")
    if not isinstance(j, list) or not j:
        return None
    out = {}
    for m in j[0].get("markets") or []:
        mt = MT.get(m.get("sportsMarketType"))
        if not mt:
            continue
        try:
            toks, outs = json.loads(m["clobTokenIds"]), json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
            g = m.get("gameStartTime") or j[0].get("startTime")
            gst = parse_ts(g)
        except (KeyError, TypeError, ValueError):
            continue
        out[m["conditionId"]] = {"mt": mt, "line": m.get("line"), "outs": outs, "toks": toks, "gst": gst}
    return out


class Tape:
    def __init__(self, out, wallets, get=http, now=time.time, interval=45):
        self.out, self.wallets, self.get, self.now, self.interval = out, wallets, get, now, interval
        self.last = {}                                   # {wallet: newest trade timestamp seen}
        self.keys = set()                                # trade keys already written (this run)
        self.facts = {}                                  # {event slug: facts or None}
        self.pending = []                                # [(due, key, sport, f, oi, tok, opp_tok)] markout reads
        self.buf = collections.defaultdict(list)         # {(sport, utc date): [rows]}
        self.start = now()

    def _facts(self, ev):
        if ev not in self.facts or (self.facts[ev] is None and int(self.now()) % 300 < self.interval):    # a failed read is retried every ~5 min
            self.facts[ev] = event_facts(ev, self.get)
        return self.facts[ev]

    def _book(self, tok):
        return book_read(self.get(f"{CLOB}/book?token_id={tok}")) if tok else book_read(None)

    def _emit(self, sport, row):
        d = dt.datetime.fromtimestamp(row["seen"] if row["k"] == "t" else row["t"], dt.timezone.utc).strftime("%Y-%m-%d")
        self.buf[(sport, d)].append(row)

    def poll_wallet(self, w):
        j = self.get(f"{DATA}/trades?user={w}&limit=50")
        if not isinstance(j, dict) or "data" not in j:
            return None
        return j["data"]

    def cycle(self, pool):
        """One pass over every watched wallet: read new trades, read their books, run due markouts. Returns the rows written."""
        n0 = sum(len(v) for v in self.buf.values())
        ws = list(self.wallets)
        for w, rows in zip(ws, pool.map(self.poll_wallet, ws)):
            if rows is None:
                continue
            seen = self.now()
            prev = self.last.get(w)
            newest = max((int(x["timestamp"]) for x in rows), default=prev)
            for x in sorted(rows, key=lambda r: r["timestamp"]):
                if prev is not None and int(x["timestamp"]) <= prev:
                    continue
                key = f"{x.get('transaction_hash')}|{x.get('token_id')}"
                if key in self.keys or not FULL_GAME.match(x.get("slug") or ""):
                    continue
                facts = {x["event_slug"]: self._facts(x["event_slug"])}
                f, why = accept(x, {k: v for k, v in facts.items() if v}, seen)
                if why:
                    continue
                sport = f"{x['slug'].split('-')[0]}"
                if sport not in SPORTS:
                    continue
                oi = int(x["outcome_index"])
                tok, opp = f["toks"][oi], f["toks"][1 - oi]
                b, ob = self._book(tok), self._book(opp)
                row = trade_row(w, self.wallets[w], sport, x, f, seen, b, ob)
                self.keys.add(key)
                self._emit(sport, row)
                for d in MARKOUTS:
                    self.pending.append((seen + d, key, sport, d, tok, opp))
            if newest is not None:
                self.last[w] = max(newest, prev or 0)
        due = [p for p in self.pending if p[0] <= self.now()]
        self.pending = [p for p in self.pending if p[0] > self.now()]
        for _, key, sport, d, tok, opp in due:
            b, ob = self._book(tok), self._book(opp)
            self._emit(sport, {"k": "m", "of": key, "dt": d, "t": int(self.now()), "bid": b["bid"], "ask": b["ask"], "opp_bid": ob["bid"], "opp_ask": ob["ask"]})
        return sum(len(v) for v in self.buf.values()) - n0

    def flush(self):
        """Append the buffered rows to their day files. Returns the sports written."""
        sports = set()
        for (sport, day), rows in self.buf.items():
            if not rows:
                continue
            p = os.path.join(self.out, sport, day + ".jsonl")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "a") as f:
                f.write("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
            sports.add(sport)
        self.buf.clear()
        return sports

    def prime(self):
        """Start point: each wallet's newest existing trade becomes `last`, so only trades after the start are detected. A wallet that
        cannot be read now is retried by the first cycle (it then reads from its own newest)."""
        with cf.ThreadPoolExecutor(8) as pool:
            for w, rows in zip(list(self.wallets), pool.map(self.poll_wallet, list(self.wallets))):
                if rows:
                    self.last[w] = max(int(x["timestamp"]) for x in rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tiers", nargs="+", required=True, help="sport=FILE, a pm_clv_tiers.py output")
    ap.add_argument("--out", required=True, help="folder of <sport>/<date>.jsonl (pm_tape on pm-holders-data)")
    ap.add_argument("--interval", type=int, default=45)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=170)
    ap.add_argument("--commit", action="store_true", help="commit and push every 10 minutes (the out folder's repo is the data worktree)")
    ap.add_argument("--control", type=int, default=CONTROL)
    ap.add_argument("--first-seen", help="pm_ledger/first_seen.json: only wallets first seen at or before sf_tiers.REGISTERED_AT are watched (the frozen universe)")
    a = ap.parse_args()
    wallets = {}
    for spec in a.tiers:
        sport, path = spec.split("=", 1)
        for w, t in watch_list(json.load(open(path)), a.control).items():
            wallets.setdefault(w, t)
    if a.first_seen:
        import sf_tiers
        fs = json.load(open(a.first_seen))
        wallets = {w: t for w, t in wallets.items() if fs.get(w) is not None and fs[w] <= sf_tiers.REGISTERED_AT}
    print(f"watching {len(wallets)} wallets: " + ", ".join(f"{t} {n}" for t, n in collections.Counter(wallets.values()).most_common()), flush=True)
    tape = Tape(a.out, wallets, interval=a.interval)
    tape.prime()
    for sp in SPORTS:                                     # a run marker, so coverage gaps between runs can be counted
        tape._emit(sp, {"k": "r", "t": int(time.time()), "watch": len(wallets), "interval": a.interval})
    end = time.time() + a.max_minutes * 60
    last_push = time.time()
    repo = os.path.dirname(os.path.abspath(a.out))
    with cf.ThreadPoolExecutor(8) as pool:
        while True:
            t0 = time.time()
            n = tape.cycle(pool)
            sports = tape.flush()
            if n:
                print(f"{dt.datetime.now(dt.timezone.utc):%H:%M:%S} {n} rows ({int(time.time() - t0)}s)", flush=True)
            if a.commit and time.time() - last_push > 600:
                from scan_pm_holders import commit_push
                commit_push(repo, os.path.basename(os.path.abspath(a.out)), SPORTS, "pm_tape: sharp wallet trades and books [skip ci]")
                last_push = time.time()
            if not a.loop or time.time() > end:
                break
            time.sleep(max(1, a.interval - (time.time() - t0)))
    tape.flush()
    if a.commit:
        from scan_pm_holders import commit_push
        commit_push(repo, os.path.basename(os.path.abspath(a.out)), SPORTS, "pm_tape: sharp wallet trades and books [skip ci]")


if __name__ == "__main__":
    main()
