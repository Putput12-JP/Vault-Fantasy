#!/usr/bin/env python3
"""Polymarket holders scan: who holds which side of every upcoming full-game NBA / NFL / CFB / CBB market, recorded point in time.

Step 2 of the proven-sharps side card (docs/pm-holders.md). Step 1 (scripts/build_pm_ledger.py) grades each wallet's past bets;
this records who is ON each side before a game, and freezes it at the cutoff (game start - 15 min, the benchmark's T-15). Step 3 joins
the two. Sharp money stays context only (CLAUDE.md).

Output (a checkout of the never-force-pushed `pm-holders-data` branch, folder pm_holders/<sport>/):
  log/<YYYY-MM-DD>/<HHMMSS>.jsonl.gz    one immutable change log per cycle (UTC date and time of the cycle start)
  frozen/<YYYY-MM-DD>/<slug>@<gst>.json the T-15 keyframe per game, written once and never rewritten
  status.json                           last good cycle, last error, consecutive failures (this sport only)

There is no state file. State is rebuilt at start by replaying the last REPLAY_DAYS of logs, so a lost run loses nothing and git does
not carry a rewritten state blob every cycle.

Log rows (compact JSON, one per line):
  {"k":"cyc", ...}                      the cycle: start/end, requests, markets due/read, misses, thin reads, late reads, http stats
  {"k":"m","c":cid,"ev":slug,"mt","line","outs","tok","gst"}   market facts, on first sight or change
  {"k":"p","c":cid,"t":T,"px":[p0,p1]}  Gamma outcome prices, on change, stamped when the fetch returned
  {"k":"r","c":cid,"rt":T,"n":[n0,n1],"lim":[b0,b1],"cf":{...}} every accepted holders read of a market (coverage proof)
  {"k":"h","c":cid,"o":oi,"w":wallet,"a":shares,"rt":T}           a holding that changed; a=0 means the wallet left
  {"k":"n","w":wallet,"n":name}         a wallet's display name, on change

Point-in-time rules
  - Every read is stamped with its own completion time `rt` (rounded up). A read that finishes after its market's cut is dropped.
  - The keyframe is rebuilt from the history AS OF THE CUT (holding changes, confirmations and prices with time <= cut), never from
    the live state, so a start time Gamma moves earlier cannot pull later reads in; such reads are counted in `late_reads`.
  - A wallet missing from an accepted read has left (a=0): the API serves every holder down to 0 shares (min_balance defaults to 0)
    and drops a token's group when it has no holders. Exceptions: a token at the page limit (an absent wallet may be past the cap;
    no exit, older `conf` kept), and a THIN read (a token that held at least THIN_MIN wallets comes back empty), which is treated as a
    failed read, not as everyone leaving.
  - firstSeen `fs` is the first read that returned the wallet on that outcome; `fs_prev` is the read before it (the entry happened
    between them). `cens` marks a wallet already holding at our first read of the market, so its true entry is earlier.
  - Keyframes are keyed by slug and game start, so a postponed game gets a new keyframe instead of an edited one.
  - Cut is Gamma's gameStartTime - 900. The side-card step compares it with Vault's own start time and flags a mismatch.

usage: scan_pm_holders.py --out DIR --sports nba|nfl|cfb|cbb [--loop --max-minutes 330] [--commit] [--max-req 400] [--dry-run]
"""
import argparse, bisect, datetime as dt, glob, gzip, json, math, os, subprocess, sys, time, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pm_ledger import (Budget, Client, COND_BATCH, CUTOFF_SEC, FULL_GAME, GAME_TAG, GAMMA, GAMMA_BATCH, PMDataError, SERIES,  # noqa: E402
                             pages, parse_ts, sport_of)

HORIZON_H = {"nba": 72, "nfl": 168, "cfb": 120, "cbb": 48}   # how far ahead to track (the recorder's ahead_h for NBA; sharp-data's NFL/CFB/CBB windows)
TIERS = ((24 * 3600, 6 * 3600), (45 * 60, 15 * 60), (0, 5 * 60))   # (time to start at least, read every): 15-min cards all game day
SLACK = 600                   # hourly-or-slower tiers fire 10 min early so cron jitter cannot turn "hourly" into "every 2 hours"
FREEZE_WIN = 20 * 60          # the freeze read must land in [gst - 20 min, gst - 15 min]
FREEZE_AIM = 18 * 60          # the loop wakes at gst - 18 min to take it
RETRY_FREEZE, RETRY = 60, 300 # back-off after a failed read: inside the freeze window, elsewhere
EVENTS_EVERY = 3600           # re-list Gamma events (new games, moved start times) about hourly
LOOP_NEAR = 24 * 3600         # keep looping while a game starts within 24h (its 15-min tier); otherwise one cycle, hourly cron
REPLAY_DAYS = 8               # NFL horizon (7 days) + 1
KEEP_AFTER = 6 * 3600         # a market stays in memory 6h past its start (its keyframe is written before any prune)
HOLDER_LIMIT = 1000           # rows per outcome token per read (API max)
THIN_MIN = 5                  # a token that held this many wallets and comes back empty is a bad read, not an exodus
CYCLE_MAX = 15 * 60           # one cycle never runs longer than this (Client deadline)
FAIL_RED = 6                  # this many failed cycles in a row turns the job red
BRANCH = "pm-holders-data"


def tier_every(to_start):
    for at_least, every in TIERS:
        if to_start >= at_least:
            return every
    return None


class State:
    """Everything a cycle needs, rebuilt from the logs. Holdings are keyed (cid, oi, wallet); history is kept for the keyframe."""

    def __init__(self):
        self.m = {}          # cid -> {"ev","mt","line","outs","tok","gst","px","px_hist":[(t,px)],"obs0","reads":[(rt,lim)]}
        self.h = {}          # (cid, oi, w) -> {"a","fs","fs_prev","conf"}   (live)
        self.hc = {}         # cid -> {(oi, w): the same holding dict as in self.h}: a read walks only its own market's holdings, not every market's
        self.hist = {}       # (cid, oi, w) -> [(rt, a)]                      (every change, for as-of-cut rebuilds)
        self.cfh = {}        # (cid, oi, w) -> [rt]  confirmations by a page-limited read that listed the wallet
        self.names = {}
        self.events_at = 0
        self.fail_at = {}    # cid -> time of the last failed read (in memory only)

    def apply(self, r):
        k = r.get("k")
        if k == "m":
            m = self.m.setdefault(r["c"], {"px": None, "px_hist": [], "obs0": None, "reads": []})
            for x in ("ev", "mt", "line", "gst"):
                m[x] = r.get(x)
            for x in ("outs", "tok"):                  # never let an empty list from Gamma replace a known one
                if r.get(x) or not m.get(x):
                    m[x] = r.get(x)
        elif k == "p":
            m = self.m.get(r["c"])
            if m is not None:
                m["px"] = r["px"]
                m["px_hist"].append((r["t"], r["px"]))
        elif k == "r":
            m = self.m.get(r["c"])
            if m is None:
                return
            m["obs0"] = m["obs0"] or r["rt"]
            lim, cf = r.get("lim") or [], r.get("cf") or {}
            m["reads"].append((r["rt"], lim))
            # A read confirms every holding it served: on a token below the page limit that is every current holder (the ones it
            # did not serve get an a=0 row right after); on a token at the limit, only the wallets listed in `cf`.
            c = r["c"]
            for (oi, w), v in self.hc.get(c, {}).items():
                if v["a"] <= 0:
                    continue
                if not (oi < len(lim) and lim[oi]):
                    v["conf"] = r["rt"]
                elif w in cf.get(str(oi), ()):
                    v["conf"] = r["rt"]
                    self.cfh.setdefault((c, oi, w), []).append(r["rt"])
        elif k == "h":
            key = (r["c"], r["o"], r["w"])
            self.hist.setdefault(key, []).append((r["rt"], r["a"]))
            cur = self.h.get(key)
            if r["a"] > 0:
                if cur is None or cur["a"] == 0:
                    fs = cur["fs"] if cur and cur.get("fs") else r["rt"]
                    fs_prev = cur["fs_prev"] if cur and cur.get("fs") else self.prev_read(r["c"], r["rt"])
                    self.h[key] = self.hc.setdefault(r["c"], {})[(r["o"], r["w"])] = {"a": r["a"], "fs": fs, "fs_prev": fs_prev, "conf": r["rt"]}
                else:
                    cur.update(a=r["a"], conf=r["rt"])
            elif cur is not None:
                cur.update(a=0, conf=r["rt"])
        elif k == "n":
            self.names[r["w"]] = r["n"]
        elif k == "cyc" and r.get("events"):
            self.events_at = max(self.events_at, r["t"])

    def prev_read(self, cid, rt):
        reads = [x for x, _ in self.m.get(cid, {}).get("reads", []) if x < rt]
        return max(reads) if reads else None

    def prune(self, now):
        dead = {c for c, m in self.m.items() if m.get("gst") and m["gst"] < now - KEEP_AFTER}
        for c in dead:
            del self.m[c]
            self.fail_at.pop(c, None)
            self.hc.pop(c, None)
        for d in (self.h, self.hist, self.cfh):
            for k in [k for k in d if k[0] in dead]:
                del d[k]


def replay(root, sport, now):
    st = State()
    files = []
    for d in range(REPLAY_DAYS, -1, -1):
        day = dt.datetime.fromtimestamp(now - d * 86400, dt.timezone.utc).strftime("%Y-%m-%d")
        files += sorted(glob.glob(os.path.join(root, sport, "log", day, "*.jsonl.gz")))
    for fn in files:
        with gzip.open(fn, "rt") as f:
            for line in f:
                if line.strip():
                    st.apply(json.loads(line))
    return st, len(files)                             # not pruned here: the caller writes owed keyframes first


# ---------- pure helpers (unit-tested) ----------

def due(m, now, fail_at=None):
    """Is this market due a holders read now? Returns "freeze", "tier" or None."""
    gst = m.get("gst")
    if not gst or now >= gst - CUTOFF_SEC:
        return None                                   # never read after the cut
    reads = [rt for rt, _ in m.get("reads") or []]
    freeze = now >= gst - FREEZE_WIN and not any(r >= gst - FREEZE_WIN for r in reads)
    if fail_at and now - fail_at < (RETRY_FREEZE if freeze else RETRY):
        return None
    if freeze:
        return "freeze"
    every = tier_every(gst - now)
    last = max(reads) if reads else None
    if last is None or now - last >= every - (SLACK if every >= 3600 else 0):
        return "tier"
    return None


def diff_read(st, cid, groups, rt, limit=HOLDER_LIMIT):
    """Rows for one read of `cid`. groups: {oi: {wallet: (shares, name)}} for the tokens served (absent = no holders).
    Returns (rows, lim), or (None, why) when the read must be treated as failed (a thin read)."""
    m = st.m[cid]
    n_out = len(m.get("tok") or [])
    if n_out == 0:
        return None, "no_tokens"
    held = {}
    for (c, oi, w), v in st.h.items():
        if c == cid and v["a"] > 0:
            held[oi] = held.get(oi, 0) + 1
    for oi in range(n_out):
        if held.get(oi, 0) >= THIN_MIN and not groups.get(oi):
            return None, "thin"
    lim = [len(groups.get(oi, {})) >= limit for oi in range(n_out)]
    rows = [{"k": "r", "c": cid, "rt": rt, "n": [len(groups.get(oi, {})) for oi in range(n_out)], "lim": lim}]
    if any(lim):
        rows[0]["cf"] = {str(oi): sorted(groups.get(oi, {})) for oi in range(n_out) if lim[oi]}
    seen = set()
    for oi, ws in groups.items():
        for w, (a, name) in ws.items():
            seen.add((oi, w))
            cur = st.h.get((cid, oi, w))
            if cur is None or abs(cur["a"] - a) > 1e-6:
                rows.append({"k": "h", "c": cid, "o": oi, "w": w, "a": round(a, 4), "rt": rt})
            if name and st.names.get(w) != name:
                rows.append({"k": "n", "w": w, "n": name})
    for (c, oi, w), v in list(st.h.items()):
        if c == cid and v["a"] > 0 and (oi, w) not in seen and not (oi < len(lim) and lim[oi]):
            rows.append({"k": "h", "c": cid, "o": oi, "w": w, "a": 0, "rt": rt})
    return rows, lim


def keyframe(st, ev, gst, now):
    """The T-15 picture of one game, rebuilt from history with time <= cut only. None if no market was read before the cut."""
    cut = gst - CUTOFF_SEC
    cids = sorted(c for c, m in st.m.items() if m.get("ev") == ev and m.get("gst") == gst and m.get("mt") in FULL_GAME)
    mk, rows, miss, late = {}, [], [], 0
    by_w = {}
    for c in cids:
        m = st.m[c]
        reads = sorted(m.get("reads") or [])
        late += sum(1 for rt, _ in reads if rt > cut)
        pre = [(rt, lim) for rt, lim in reads if rt <= cut]
        if not pre:
            miss.append(c)
            continue
        read_rt, read_lim = pre[-1]
        pxs = [(t, px) for t, px in m.get("px_hist") or [] if t <= cut]
        px_t, px = pxs[-1] if pxs else (None, None)
        mk[c] = {"mt": m["mt"], "line": m.get("line"), "outs": m.get("outs"), "tok": m.get("tok"), "px": px, "px_t": px_t,
                 "read_rt": read_rt, "frz_lag": cut - read_rt, "lim": read_lim}
        read_times = [rt for rt, _ in pre]
        for key, changes in st.hist.items():
            if key[0] != c:
                continue
            upto = [(rt, a) for rt, a in changes if rt <= cut]
            if not upto or upto[-1][1] <= 0:
                continue
            _, oi, w = key
            a = upto[-1][1]
            fs = next(rt for rt, x in upto if x > 0)
            i = bisect.bisect_left(read_times, fs)
            fs_prev = read_times[i - 1] if i > 0 else None
            if oi < len(read_lim) and read_lim[oi]:
                conf = max([upto[-1][0]] + [t for t in st.cfh.get(key, []) if t <= cut])
            else:
                conf = read_rt
            p = px[oi] if px and oi < len(px) else None
            rows.append([c, oi, w, a, round(a * p, 2) if p is not None else None, fs, fs_prev, fs == m.get("obs0"), conf])
            by_w.setdefault((w, c), set()).add(oi)
    if not mk:
        return None
    both = sorted({w for (w, c), ois in by_w.items() if len(ois) > 1})
    return {"v": 1, "ev": ev, "gst": gst, "cut": cut, "written": now, "mk": mk, "miss": miss, "late_reads": late, "both": both,
            "cols": ["cid", "oi", "wallet", "shares", "usd_at_mark", "fs", "fs_prev", "cens", "conf"], "h": rows,
            "names": {w: st.names[w] for w in {r[2] for r in rows} if w in st.names}}


def next_wake(st, now):
    """The earliest moment any market becomes due: its tier interval, a faster tier starting, the freeze aim, or a retry."""
    best = None
    for c, m in st.m.items():
        gst = m.get("gst")
        if not gst or m.get("mt") not in FULL_GAME or now >= gst - CUTOFF_SEC:
            continue
        reads = [rt for rt, _ in m.get("reads") or []]
        cands = [gst - at for at, _ in TIERS if at and gst - at > now]          # tier boundaries
        if not any(r >= gst - FREEZE_WIN for r in reads):
            cands.append(max(now, gst - FREEZE_AIM))
        every = tier_every(gst - now)
        if every:
            cands.append((max(reads) + every - (SLACK if every >= 3600 else 0)) if reads else now)
        if c in st.fail_at:
            cands = [max(x, st.fail_at[c] + RETRY_FREEZE) for x in cands]
        best = min([best] + cands) if best is not None else min(cands)
    return best


# ---------- io ----------

def gamma_events(cli, sport, now):
    """Upcoming games of one sport from Gamma. A failed or non-JSON answer raises (never 'no games')."""
    iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out, cursor, trunc = [], None, False
    for i in range(20):
        q = {"series_id": SERIES[sport], "tag_id": GAME_TAG, "closed": "false", "limit": 50,
             "start_time_min": iso(now), "start_time_max": iso(now + HORIZON_H[sport] * 3600)}
        if cursor:
            q["after_cursor"] = cursor
        j = cli.get(f"{GAMMA}/events/keyset?{urllib.parse.urlencode(q)}")
        if not isinstance(j, dict) or "events" not in j:
            raise PMDataError(f"gamma events {sport}: no response")
        out += j["events"] or []
        cursor = j.get("next_cursor")
        if not cursor or not j["events"]:
            break
        trunc = i == 19
    return out, trunc


def market_rows(st, events, sport):
    rows = []
    for e in events:
        for m in e.get("markets") or []:
            cid, mt = m.get("conditionId"), m.get("sportsMarketType")
            if not cid or mt not in FULL_GAME or sport_of(m.get("slug") or e.get("slug")) != sport:
                continue
            try:
                outs, tok = json.loads(m.get("outcomes") or "[]"), json.loads(m.get("clobTokenIds") or "[]")
            except ValueError:
                continue
            if not tok or len(tok) != len(outs):
                continue                              # never record a market we could not map to its tokens
            row = {"k": "m", "c": cid, "ev": e.get("slug"), "mt": mt, "line": m.get("line"), "outs": outs, "tok": tok,
                   "gst": parse_ts(m.get("gameStartTime"))}
            cur = st.m.get(cid)
            if cur is None or any(cur.get(x) != row[x] for x in ("ev", "mt", "line", "outs", "tok", "gst")):
                rows.append(row)
    return rows


def price_rows(cli, st, cids, confirm=()):
    """Gamma prices (and game start, which can move) for the markets about to be read. A price is logged when it changes, and for the
    `confirm` markets (the freeze read) also when it has not, so the keyframe's price time is when it was last read. Each row is stamped when its batch returned;
    a price that arrives after its market's cut is dropped (a moved start time is still recorded: it is a fact, not a holding)."""
    rows = []
    for i in range(0, len(cids), GAMMA_BATCH):
        chunk = cids[i:i + GAMMA_BATCH]
        j = cli.get(f"{GAMMA}/markets/keyset?" + "&".join("condition_ids=" + c for c in chunk) + f"&closed=false&limit={GAMMA_BATCH}")
        t = math.ceil(time.time())
        if not isinstance(j, dict):
            raise PMDataError("gamma markets: no response")
        for m in j.get("markets") or []:
            c = m.get("conditionId")
            if c not in st.m:
                continue
            cur = st.m[c]
            gst = parse_ts(m.get("gameStartTime"))
            if gst and gst != cur.get("gst"):
                rows.append({"k": "m", "c": c, "ev": cur["ev"], "mt": cur["mt"], "line": cur.get("line"), "outs": cur.get("outs"),
                             "tok": cur.get("tok"), "gst": gst})
            try:
                px = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
            except ValueError:
                px = None
            if px and (px != cur.get("px") or c in confirm) and t <= (gst or cur.get("gst") or 0) - CUTOFF_SEC:
                rows.append({"k": "p", "c": c, "t": t, "px": px})
    return rows


def read_holders(cli, st, cids, log, stats):
    """Read holders for `cids` in batches of 20, freeze reads and earliest games first. A failed batch is split until the bad market
    is isolated; a failed or thin market goes to `miss`, backs off, and stays due. Budget propagates (the cycle ends cleanly)."""
    def one(batch):
        groups = {c: {} for c in batch}
        tok_of = {}
        for c in batch:
            for oi, t in enumerate(st.m[c].get("tok") or []):
                tok_of[str(t)] = (c, oi)
        try:
            for page in pages(cli, "/holders", {"condition": ",".join(batch), "limit": HOLDER_LIMIT}, 1):
                for g in page:
                    for h in g.get("holders") or []:
                        hit = tok_of.get(str(h.get("token_id") or g.get("token_id")))
                        w = (h.get("proxy_wallet") or "").lower()
                        if hit and w.startswith("0x") and float(h.get("amount") or 0) > 0:
                            c, oi = hit
                            groups[c].setdefault(oi, {})[w] = (float(h["amount"]), h.get("name") or h.get("pseudonym"))
        except PMDataError:
            if len(batch) == 1:
                stats["miss"].append(batch[0])
                st.fail_at[batch[0]] = time.time()
                return
            mid = len(batch) // 2
            one(batch[:mid])
            one(batch[mid:])
            return
        done = time.time()
        rt = math.ceil(done)
        for c in batch:
            if done > st.m[c]["gst"] - CUTOFF_SEC:
                stats["late"].append(c)               # finished after the cut: dropped, so nothing after T-15 leaks in
                continue
            rows, lim = diff_read(st, c, groups[c], rt)
            if rows is None:
                stats["miss"].append(c)
                stats[lim] = stats.get(lim, 0) + 1   # "thin" or "no_tokens"
                st.fail_at[c] = done
                continue
            st.fail_at.pop(c, None)
            for r in rows:
                log.append(r)
                st.apply(r)
            stats["read"] += 1
            stats["limit_hit"] += [c for b in lim if b]
    for i in range(0, len(cids), COND_BATCH):
        one(cids[i:i + COND_BATCH])


def write_log(root, sport, t0, rows):
    d = dt.datetime.fromtimestamp(t0, dt.timezone.utc)
    folder = os.path.join(root, sport, "log", d.strftime("%Y-%m-%d"))
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, d.strftime("%H%M%S"))
    path, n = base + ".jsonl.gz", 1
    while os.path.exists(path):                      # never overwrite an immutable log
        path, n = f"{base}-{n}.jsonl.gz", n + 1
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    os.replace(tmp, path)
    return path


def write_keyframes(root, sport, st, now):
    """Write the keyframe of every game whose cut has passed and that has none yet. Written once, never rewritten."""
    out = []
    games = {(m["ev"], m["gst"]) for m in st.m.values() if m.get("gst") and m.get("mt") in FULL_GAME}
    for ev, gst in sorted(games, key=lambda x: x[1]):
        if now < gst - CUTOFF_SEC:
            continue
        day = dt.datetime.fromtimestamp(gst, dt.timezone.utc).strftime("%Y-%m-%d")
        path = os.path.join(root, sport, "frozen", day, f"{ev}@{gst}.json")
        if os.path.exists(path):
            continue
        kf = keyframe(st, ev, gst, now)
        if kf is None:
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(kf, f, separators=(",", ":"))
        os.replace(tmp, path)
        out.append(os.path.relpath(path, root))
    return out


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def commit_push(repo, folder, sports, msg):
    """Commit this job's own folders and push to the data branch, rebasing on a race. Returns True when the remote has HEAD."""
    git(repo, "add", "-A", *[os.path.join(folder, s) for s in sports])
    if git(repo, "diff", "--cached", "--quiet").returncode != 0:
        if git(repo, "commit", "-q", "-m", msg).returncode != 0:
            return False
    for _ in range(4):
        if git(repo, "push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}").returncode == 0:
            return True
        # the other job pushed first: replay our commits on top (the jobs write disjoint folders, so this never conflicts)
        if git(repo, "fetch", "-q", "origin", BRANCH).returncode == 0 and git(repo, "rebase", "-q", "FETCH_HEAD").returncode != 0:
            git(repo, "rebase", "--abort")
            return False
        time.sleep(2)
    return False


def remote_has_head(repo):
    """True when origin's data branch contains our HEAD (a detached worktree has no upstream, so ask the remote directly)."""
    if git(repo, "rev-parse", "-q", "--verify", "HEAD").returncode != 0:
        return True                                   # nothing was ever committed
    if git(repo, "fetch", "-q", "origin", BRANCH).returncode != 0:
        return False
    return git(repo, "merge-base", "--is-ancestor", "HEAD", "FETCH_HEAD").returncode == 0


def kick_cards(repo, unsent, ref, run=subprocess.run):
    """Start the side-cards build the moment new keyframes are on the remote, instead of waiting for its 10-minute cron.

    GitHub's scheduler can run hours late, and a frozen card only counts for the forward test if it is built before game start.
    Fires only when origin has this run's HEAD (so the build sees the keyframes). pm-cards.yml has one concurrency group that keeps
    the newest pending run, so dispatches from three sport jobs collapse into one build, and every build writes every keyframe
    that has no card yet. Returns the keyframes still unsent: a failed dispatch is retried after the next push, and the cron stays
    as the backstop. Never fails the scan."""
    if not unsent or not ref:
        return unsent
    if not remote_has_head(repo):
        print("::warning::keyframes not on origin yet; the cards build is started after the next push")
        return unsent
    try:
        r = run(["gh", "workflow", "run", "pm-cards.yml", "--ref", ref], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"::warning::could not start the cards build: {e}")
        return unsent
    if r.returncode != 0:
        print(f"::warning::could not start the cards build: {(r.stderr or r.stdout or '').strip()[:300]}")
        return unsent
    print(f"started the cards build for {len(unsent)} new keyframe(s)")
    return []


# ---------- cycle and loop ----------

def cycle(cli, root, sport, st, dry):
    t0 = int(time.time())
    log, stats = [], {"read": 0, "miss": [], "limit_hit": [], "late": []}
    events_listed, err = False, None
    try:
        if t0 - st.events_at >= EVENTS_EVERY - SLACK or not st.m:
            try:
                events, trunc = gamma_events(cli, sport, t0)
                for r in market_rows(st, events, sport):
                    log.append(r)
                    st.apply(r)
                events_listed, stats["events_trunc"] = True, trunc
            except PMDataError as e:
                stats["events_err"] = str(e)          # keep reading the markets already known; only fatal with none known
                if not st.m:
                    raise
        now = int(time.time())
        due_c = [c for c, m in st.m.items() if m.get("mt") in FULL_GAME and due(m, now, st.fail_at.get(c))]
        due_c.sort(key=lambda c: (due(st.m[c], now) != "freeze", st.m[c]["gst"]))   # freeze reads first, then earliest games
        stats["due"] = len(due_c)
        try:
            # the freeze read re-logs every price even when unchanged, so the T-15 keyframe carries a price confirmed at the lock
            # (prices were logged only on change, so a steady price kept the time it last moved: up to hours before the cut)
            for r in price_rows(cli, st, due_c, confirm={c for c in due_c if due(st.m[c], now) == "freeze"}):
                log.append(r)
                st.apply(r)
        except PMDataError as e:
            stats["price_err"] = str(e)               # prices are context; never let them block a holders read
        now = int(time.time())
        read_holders(cli, st, [c for c in due_c if due(st.m[c], now)], log, stats)
    except Budget as e:
        err = f"budget:{e}"
    except PMDataError as e:
        err = str(e)
    if err is None and stats.get("due") and stats["read"] == 0:
        err = f"holders: 0 of {stats['due']} due markets read"
    cyc = {"k": "cyc", "t": t0, "te": int(time.time()), "sp": sport, "v": 2, "ok": err is None, "err": err, "events": events_listed,
           "due": stats.get("due", 0), "read": stats["read"], "miss": stats["miss"][:50], "n_miss": len(stats["miss"]),
           "thin": stats.get("thin", 0), "limit_hit": stats["limit_hit"][:50], "late": stats["late"],
           "events_err": stats.get("events_err"), "events_trunc": stats.get("events_trunc", False),
           "price_err": stats.get("price_err"), "rows": len(log), "http": cli.stats()}
    if events_listed:
        st.events_at = t0
    frames, wrote = [], False
    if not dry:
        if log or err:                                # an idle cycle writes no log file (status.json still records it)
            write_log(root, sport, t0, [cyc] + log)
            wrote = True
        frames = write_keyframes(root, sport, st, int(time.time()))
    cyc["frozen"] = frames
    return cyc, wrote or bool(frames)


def save_status(root, sport, cyc):
    p = os.path.join(root, sport, "status.json")
    try:
        with open(p) as f:
            s = json.load(f)
    except (FileNotFoundError, ValueError):
        s = {}
    s["fails"] = 0 if cyc["ok"] else s.get("fails", 0) + 1
    s["last"] = {k: cyc[k] for k in ("t", "ok", "err", "due", "read", "n_miss", "thin", "rows", "frozen")}
    if cyc["ok"]:
        s["last_ok"] = cyc["t"]
    if cyc["http"].get("retry_after"):
        s["retry_after_at"] = cyc["t"]
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(s, f, indent=1, sort_keys=True)
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="the pm_holders folder inside a pm-holders-data checkout")
    ap.add_argument("--sports", required=True)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=330)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--max-req", type=int, default=400, help="request cap per cycle")
    ap.add_argument("--pace", type=float, default=0.2)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cards-ref", default="", help="with --commit: start pm-cards.yml on this ref after new keyframes are pushed "
                    "(the workflow passes it only on the default branch, so a branch run never writes frozen cards)")
    a = ap.parse_args()
    sports = [s for s in a.sports.split(",") if s in SERIES]
    start = time.time()
    end = start + a.max_minutes * 60
    repo, folder = os.path.dirname(os.path.abspath(a.out)), os.path.basename(os.path.abspath(a.out))
    states, status, unsent = {}, {}, []
    for s in sports:
        states[s], nf = replay(a.out, s, int(start))
        owed = [] if a.dry_run else write_keyframes(a.out, s, states[s], int(time.time()))   # before any prune (a long gap)
        if a.cards_ref:
            unsent += owed
        states[s].prune(int(start))
        print(f"{s}: replayed {nf} log files, {len(states[s].m)} markets, "
              f"{sum(1 for v in states[s].h.values() if v['a'] > 0)} holdings, owed keyframes written: {len(owed)}")
    while True:
        changed = False
        for s in sports:
            cli = Client(a.pace, a.max_req, min(end, time.time() + CYCLE_MAX))
            cyc, wrote = cycle(cli, a.out, s, states[s], a.dry_run)
            print(json.dumps({k: cyc[k] for k in ("sp", "ok", "err", "events", "due", "read", "n_miss", "thin", "rows", "frozen")}))
            if not a.dry_run:
                status[s] = save_status(a.out, s, cyc)
                changed = changed or wrote
                if a.cards_ref:
                    unsent += cyc["frozen"]
            states[s].prune(int(time.time()))
        if changed and a.commit:
            when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            if not commit_push(repo, folder, sports, f"pm holders {','.join(sports)}: {when} [skip ci]"):
                print("::warning::push failed; the next cycle retries")
        if unsent and a.commit:                       # no commit of its own: a failed dispatch just retries next cycle
            unsent = kick_cards(repo, unsent, a.cards_ref)
        if not a.loop or a.dry_run:
            break
        now = int(time.time())
        wakes = [w for w in (next_wake(states[s], now) for s in sports) if w is not None]
        near = any(m.get("gst") and 0 < m["gst"] - CUTOFF_SEC - now <= LOOP_NEAR for s in sports for m in states[s].m.values())
        if not wakes or not near:
            print("no game within 24h: done (the hourly cron takes over)")
            break
        wake = max(now + 5, min(wakes))
        if wake + CYCLE_MAX > end:
            out = os.environ.get("GITHUB_OUTPUT")
            if out:
                with open(out, "a") as f:
                    f.write("handoff=true\n")
            print("max minutes reached: handing off")
            break
        time.sleep(wake - now)
    code = 0
    if a.commit and not a.dry_run:
        when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        for _ in range(3):                            # the last cycle's files (and status) must reach the remote
            if commit_push(repo, folder, sports, f"pm holders {','.join(sports)}: {when} [skip ci]") and remote_has_head(repo):
                unsent = kick_cards(repo, unsent, a.cards_ref)
                break
            time.sleep(10)
        else:
            print("::error::the data branch on origin does not have this run's last commit")
            code = 1
    if any(st.get("fails", 0) >= FAIL_RED for st in status.values()):
        print(f"::error::{FAIL_RED}+ failed cycles in a row")
        code = code or 2
    return code


if __name__ == "__main__":
    sys.exit(main())
