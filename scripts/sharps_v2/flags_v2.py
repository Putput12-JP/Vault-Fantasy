#!/usr/bin/env python3
"""Sharps V2 market-move flags (docs/sharps-v2-flags-spec.md, rule v2f-2): pure functions, stdlib only.

What the market did on a shown play's market, read from the book tape (rows written when a book's numbers change), stopped at `asof`
(the cut on a frozen card, the build time on a live one). Context only (CLAUDE.md): nothing here is a bet signal, a size or an input to
Top Reads, SM_GATE, an agree total, sf_rungs, the locks, the evidence tier or either size (`shown_units` flat 1u, shadow `v2s-1`).
The flags read "what the market did", never "sharp action confirms".

  Flag A  Pinnacle's no-vig price for the side moved at the SAME line, toward or away, over the 24 hours ending at `asof`
  Flag C  spreads and totals: Pinnacle's main line moved and at least 2 US books moved 1 point or more the same way;
          moneylines: at least 2 US books moved their no-vig price by the A threshold in one direction and none the other way
  limit   Pinnacle's limit, a FACT line only (user decision 2026-11-23, D1): the stored first and last limit, never a chip or a rule

The window (rule v2f-2): the tape writes a row only when a book's numbers change, so the number a book was showing when the 24-hour window opened is its
LAST row at or before the window start (when it has none, its first row inside the window). A first quote inside the window is not a move from nothing: it
has no history and reads as null, never as a move of 0.

Never invent a number: every value is a stored price, a stored line, a stored limit, or arithmetic on them. A value that cannot be read
is None with a reason (`why`), never 0 and never "quiet". Books are the ones in the tape (Pinnacle, DraftKings, FanDuel, BetMGM,
BetRivers, bet365): BookMaker and Circa exist only in a tape whose terms forbid showing it and are never read here (D4).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sf_signals as SIG  # noqa: E402

FLAGS_RULE = "v2f-2"                              # a change to any threshold, window or branch is a new rule id and a new registration
FLAGS_WINDOW = 86400                              # the 24 hours ending at asof (steam_record.py's window)
FLAGS_STALE = 1800                                # a source heartbeat more than 30 minutes older than asof is unreadable (stale-number rule)
FLAGS_SERIES_N = 16                               # points per mini-chart series
FLAGS_US = ("BetMGM", "BetRivers", "DraftKings", "FanDuel", "bet365")
FLAGS_BOOKS = ("Pinnacle", "DraftKings", "FanDuel", "BetMGM", "BetRivers", "bet365")   # display order; the only books ever shown
FLAGS_C_MIN_US = 2                                # US books that must have a row, and (spreads, totals) that must move the same way
FLAGS_SWAP_MARGIN = 0.05                          # a stored Pinnacle row is on "the other side of even money" only when both it and the reference are this far from 0.5
FLAGS_SWAP_LINE = 1.5                             # a spread row has "the other sign" only when both it and the reference are at least this many points from pick'em
FLAGS_C_BOOK_MOVE = 1.0                           # a US book "moved" when its own line moved this many points (the stale-number rule)
# T_A: points of Pinnacle no-vig fair, the 80th percentile of the absolute 24-hour move for the sport and market (rounded to 0.5), user
# decision D2 2026-11-23 (docs/sharps-v2-flags-spec.md 1.2). T_C: points of Pinnacle's main line move, the 80th percentile rounded UP to
# the half point with a floor of 1.0 (spec 1.4). Both percentiles are measured under the v2f-2 window rule (the row hanging when the window opened).
# ONE table: the docs and the tests read these constants.
FLAGS_T_A = {"nba": {"ml": 4.0, "spread": 1.5, "total": 1.5}, "nfl": {"ml": 1.5, "spread": 1.5, "total": 1.5},
             "cbb": {"ml": 3.0, "spread": 1.5, "total": 1.5}, "cfb": {"ml": 2.5, "spread": 1.5, "total": 1.5}}
FLAGS_T_C = {"nba": {"spread": 2.0, "total": 3.0}, "nfl": {"spread": 1.0, "total": 1.0},
             "cbb": {"spread": 1.0, "total": 2.5}, "cfb": {"spread": 1.5, "total": 1.5}}
# The share of Pinnacle markets (a game's moneyline, spread or total) whose limit at the cut (15 minutes before start) was ABOVE the limit it was showing when the
# 24-hour window opened, the same two numbers the limit fact line prints (`from`, `to`), per sport, on the book tape at origin/main afd35efe
# (2026-11-23 1:30 PM CT, started games only): NBA 744 markets 99.2%, NFL 252 92.9%, CBB 480 96.9%, CFB 1,012 89.4%. The page words it "Pinnacle raises
# limits toward start". A description, never a flag.
LIMIT_SCHEDULE_SHARE = {"nba": 0.99, "nfl": 0.93, "cbb": 0.97, "cfb": 0.89}
LIMIT_SHARE_BASIS = "markets whose Pinnacle limit at the cut was above the limit showing when the 24 hour window opened"
TAPE_KEY = {"ml": "ml", "spread": "sp", "total": "tot"}
LINE_EPS = SIG.PIN_LINE_EPS
SIDES = ("home", "away", "over", "under")


def _n(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _vals(v, n):
    return v if isinstance(v, (list, tuple)) and len(v) >= n else None


def _by_book(rows, asof):
    """{book: [rows at or before asof, oldest first]} for the books the flags may show. A malformed row (not an object, no time) is skipped."""
    out = {}
    for r in rows or []:
        if isinstance(r, dict) and _n(r.get("t")) and r["t"] <= asof and r.get("book") in FLAGS_BOOKS:
            out.setdefault(r["book"], []).append(r)
    for rs in out.values():
        rs.sort(key=lambda r: r["t"])
    return out


def _reads(rs, g, norm):
    """The readable rows of one book for market `g` and side `norm`, oldest first: {t, line, px, fair}. line: the side's own line (spread: the
    home line, negated for the away side; total: the number; moneyline: None). px: the side's American price; fair: Pinnacle-style two-way
    multiplicative no-vig fair (mine / (mine + other)). A field is None when not stored; a row with no readable line AND no readable price is
    dropped (spreads and totals need a line, moneylines a price pair)."""
    away = norm in ("away", "under")
    key = TAPE_KEY[g]
    out = []
    for r in rs or []:
        v = _vals(r.get(key), 2 if g == "ml" else 3)
        if v is None:
            continue
        if g == "ml":
            mine, oth, line = (v[0], v[1], None) if away else (v[1], v[0], None)
        else:
            if not _n(v[0]):
                continue
            line = -v[0] if (away and g == "spread") else v[0]
            mine, oth = (v[2], v[1]) if away else (v[1], v[2])
        pm, po = (SIG.american_prob(mine) if _n(mine) else None), (SIG.american_prob(oth) if _n(oth) else None)
        fair = pm / (pm + po) if pm is not None and po is not None and pm + po > 0 else None
        if g == "ml" and fair is None:
            continue
        out.append({"t": r["t"], "line": line, "px": mine if fair is not None else None, "fair": fair})
    return out


def _window_from(rs, asof):
    """The row the book was showing when the 24 hours ending at asof opened: its last row at or before the window start (the tape is change-only,
    so that row's number held until the next row); with none, its first row inside the window. `rs` oldest first and all at or before asof.
    None when empty."""
    if not rs:
        return None
    ws = asof - FLAGS_WINDOW
    before = [r for r in rs if r["t"] <= ws]
    return before[-1] if before else rs[0]


def _has_history(rd, asof):
    """A book can be read for a move only when it has two or more readable rows, the same minimum Flag A applies to Pinnacle: a single stored row is
    never a move, whether it was first quoted inside the window or showed since before it (the tape cannot say a lone old row was not a feed gap)."""
    return len(rd) >= 2


def _side(v, g):
    """-1, 0 or +1: which side of even money a moneyline fair is on (inside the margin: 0), or the sign of a spread line. None for a total."""
    if v is None:
        return None
    if g == "ml":
        return 1 if v >= 0.5 + FLAGS_SWAP_MARGIN else -1 if v <= 0.5 - FLAGS_SWAP_MARGIN else 0
    if g == "spread":
        return 1 if v >= FLAGS_SWAP_LINE else -1 if v <= -FLAGS_SWAP_LINE else 0
    return None


def _pin_clean(by, g, norm):
    """-> (readable Pinnacle rows, rows dropped). A stored Pinnacle row is dropped when it is on the other side of even money (moneyline fair, with a
    margin of 0.05; spread: the sign of the line, both at least 1.5 points from pick'em, so a pick'em line is never judged) from every US book showing at its time (2 or more of them), or, with fewer than 2 US books, from BOTH
    of Pinnacle's own neighbouring rows (an isolated outlier; a first or last row has only one neighbour and is never dropped on that evidence): a stored
    row with its two sides swapped would otherwise read as a 40-point move. A total has no side."""
    rd = _reads(by.get("Pinnacle"), g, norm)
    if g == "total" or len(rd) < 2:
        return rd, 0
    key = "fair" if g == "ml" else "line"
    us = [_reads(by.get(b), g, norm) for b in FLAGS_US if by.get(b)]
    keep, dropped = [], 0
    for i, r in enumerate(rd):
        me = _side(r[key], g)
        bad = False
        if me:
            ref = []
            for rows in us:
                prior = [x for x in rows if x["t"] <= r["t"] and x[key] is not None]
                if prior:
                    ref.append(_side(prior[-1][key], g))
            if len(ref) >= 2:
                bad = all(x and x == -me for x in ref)
            else:
                nb = [rd[i - 1], rd[i + 1]] if 0 < i < len(rd) - 1 else []      # no US evidence: only an isolated row (both neighbours opposite) is dropped
                bad = bool(nb) and all(x[key] is not None and _side(x[key], g) == -me for x in nb)
        if bad:
            dropped += 1
        else:
            keep.append(r)
    return keep, dropped


def _age(asof, hb, key):
    t = (hb or {}).get(key)
    return max(0, round((asof - t) / 60)) if _n(t) and _n(asof) else None


def _stale(asof, hb, key):
    t = (hb or {}).get(key)
    return _n(t) and asof - t > FLAGS_STALE


def state_of(pts, t):
    """toward / away / quiet from a move in points and its threshold. Compared on the 2-decimal value that is stored, so the stored number
    and the state never disagree. None for a move that is not a number."""
    if not _n(pts) or not _n(t):
        return None
    p = round(pts, 2)
    return "toward" if p >= t else "away" if p <= -t else "quiet"


# ---------- Flag A ----------

def flag_pin(rows, g, norm, asof, sport, heartbeat=None):
    """-> (flag or None, why). Pinnacle's no-vig fair for the side, `now` (the last readable row at or before asof) against `from` (v2f-2: the
    row Pinnacle was showing when the 24-hour window opened, i.e. its last readable row at or before the window start across ALL lines, else its first
    row inside the window), in points x 100. Needs 2 or more readable Pinnacle rows in all. Spreads and totals compare only at the SAME line as `now`
    (a line change is Flag C's): when the row showing at the window start is at a different line, `from` is the first earlier quote at the current line
    INSIDE the window, and with none the flag is null (`no_same_line_history`), never a quote from days ago at a line the book has since left.
    A first quote at the current line is also `no_same_line_history`, never a move of 0. A `from` that is the `now` row itself (every row was already
    showing before the window opened) reads as a real move of 0."""
    if norm not in SIDES:
        return None, "side_unmapped"
    t_a = (FLAGS_T_A.get(sport) or {}).get(g)
    if t_a is None:
        return None, "no_threshold"
    clean, dropped = _pin_clean(_by_book(rows, asof), g, norm)
    rs = [r for r in clean if r["fair"] is not None]
    if not rs:
        return None, "pinnacle_row_inconsistent" if dropped else "no_tape_rows_for_game"
    if len(rs) < 2:
        return None, "pinnacle_row_inconsistent" if dropped else "no_pinnacle_history"
    if _stale(asof, heartbeat, "pinnacle"):
        return None, "pinnacle_feed_stale"
    now = rs[-1]
    cand = rs if g == "ml" else [r for r in rs if _n(r["line"]) and _n(now["line"]) and abs(r["line"] - now["line"]) <= LINE_EPS]
    if len(cand) < 2:                                   # no quote at this line before the current one: a first quote is not a move from nothing
        return None, "no_same_line_history"
    fr = _window_from(rs, asof)                         # the row hanging when the window opened, across every line
    if g != "ml" and not (_n(fr["line"]) and abs(fr["line"] - now["line"]) <= LINE_EPS):
        inside = [r for r in cand[:-1] if r["t"] > asof - FLAGS_WINDOW]       # earlier quotes at THIS line inside the window
        if not inside:
            return None, "no_same_line_history"
        fr = inside[0]
    if fr is None or fr["fair"] is None or now["fair"] is None:
        return None, "no_pinnacle_history"
    pts = round((now["fair"] - fr["fair"]) * 100, 2)
    return {"state": state_of(pts, t_a), "pts": pts, "t_a": t_a, "from": fr["px"], "to": now["px"], "line": now["line"],
            "t_from": fr["t"], "t_to": now["t"], "rows": len(rs), "dropped": dropped}, None


# ---------- limit (a fact) ----------

def flag_limit(rows, g, asof):
    """-> (fact or None, why). Pinnacle's stored limit on market `g`: `to` = its last stored limit at or before asof (copied from
    sf_signals.limit_read's `now`), `from` = the limit it was showing when the 24-hour window opened (its last stored limit at or before the window
    start, else its first stored limit inside the window; `t_from` is that row's time, which can be before the window). `rows` counts every stored
    limit up to asof. NOT a flag: no rising rule, no chip, no direction (user decision D1). One reading gives from == to."""
    i = SIG.LIM_IDX[g]
    ok = [r for r in (_by_book(rows, asof).get("Pinnacle") or [])
          if isinstance(r.get("lim"), (list, tuple)) and len(r["lim"]) > i and (r["lim"][i] is None or _n(r["lim"][i]))]
    lr = SIG.limit_read(ok, g, asof)
    if not lr.get("rows"):
        return None, lr.get("why") or "no_limit_before_cut"
    pts = [{"t": r["t"], "v": r["lim"][i]} for r in ok if r["lim"][i]]        # the same readable rows limit_read counts (a stored 0 or null is not a limit)
    fr = _window_from(pts, asof)
    return {"market": g, "from": fr["v"], "to": lr["now"], "rows": lr["rows"], "t_from": fr["t"], "asof": asof}, None


# ---------- Flag C ----------

def _dir_sign(g, norm):
    """+1 when a move TOWARD the side raises the line (an over), -1 when it lowers it (a spread side, an under)."""
    return 1 if (g == "total" and norm == "over") else -1


def _book_moves(rows, g, norm, asof):
    """-> ({book: {fr, to}}, Pinnacle rows dropped) for every book that can be read for a move: its row at the window start and its last row. A book
    whose only row is a first quote inside the window has no history and is left out (never a move of 0); Pinnacle's rows go through `_pin_clean`."""
    out = {}
    by = _by_book(rows, asof)
    pin, dropped = _pin_clean(by, g, norm)
    for b, rs in by.items():
        rd = pin if b == "Pinnacle" else _reads(rs, g, norm)
        if not rd or not _has_history(rd, asof):
            continue
        out[b] = {"fr": _window_from(rd, asof), "to": rd[-1]}
    return out, dropped


def flag_line(rows, g, norm, asof, sport, heartbeat=None):
    """-> (flag or None, why). See the module docstring. Spreads and totals: `pin` = Pinnacle's side line from and to, `by_book` the US books',
    state toward / away when Pinnacle moved T_C or more AND at least 2 US books moved 1 point or more the same way. Moneylines (kind price):
    the same shape with American prices; state toward / away when at least 2 US books moved the no-vig price by T_A or more one way and none
    the other. `same_way` and `extreme` exist only on a toward / away state (None on quiet: no direction was established)."""
    if norm not in SIDES:
        return None, "side_unmapped"
    ml = g == "ml"
    t_c = (FLAGS_T_A if ml else FLAGS_T_C).get(sport, {}).get(g)
    if t_c is None:
        return None, "no_threshold"
    mv, dropped = _book_moves(rows, g, norm, asof)
    us = [b for b in FLAGS_US if b in mv]
    if "Pinnacle" not in mv and dropped:
        return None, "pinnacle_row_inconsistent"
    if "Pinnacle" not in mv or len(us) < FLAGS_C_MIN_US:
        return None, "too_few_books"
    if _stale(asof, heartbeat, "pinnacle"):
        return None, "pinnacle_feed_stale"
    if _stale(asof, heartbeat, "us"):
        return None, "books_feed_stale"
    pin = mv["Pinnacle"]
    if ml:
        val = lambda r: r["px"]
        move = lambda m: (m["to"]["fair"] - m["fr"]["fair"]) * 100          # points of no-vig fair toward the side
        books = us
        up = [b for b in us if round(move(mv[b]), 2) >= t_c]
        dn = [b for b in us if round(move(mv[b]), 2) <= -t_c]
        state = "toward" if len(up) >= FLAGS_C_MIN_US and not dn else "away" if len(dn) >= FLAGS_C_MIN_US and not up else "quiet"
        same = up if state == "toward" else dn if state == "away" else None
        dsign = 1 if state == "toward" else -1
    else:
        s = _dir_sign(g, norm)
        val = lambda r: r["line"]
        if any(not _n(val(m[k])) for m in mv.values() for k in ("fr", "to")):
            return None, "too_few_books"
        move = lambda m: s * (m["to"]["line"] - m["fr"]["line"])           # points toward the side (negative = against)
        books = ["Pinnacle"] + us
        pm_ = round(move(pin), 2)
        up = [b for b in books if round(move(mv[b]), 2) >= FLAGS_C_BOOK_MOVE]
        dn = [b for b in books if round(move(mv[b]), 2) <= -FLAGS_C_BOOK_MOVE]
        us_up, us_dn = [b for b in up if b != "Pinnacle"], [b for b in dn if b != "Pinnacle"]
        state = ("toward" if pm_ >= t_c and len(us_up) >= FLAGS_C_MIN_US else "away" if pm_ <= -t_c and len(us_dn) >= FLAGS_C_MIN_US else "quiet")
        same = up if state == "toward" else dn if state == "away" else None
        dsign = s if state == "toward" else -s
    extreme = None
    if same:                                                                 # the book furthest in the move's direction; ties: earliest row, then name
        pool = [b for b in (books if not ml else us) if b in mv]
        if ml:
            key = lambda b: (-round(dsign * move(mv[b]), 6), mv[b]["to"]["t"], b)
        else:
            key = lambda b: (-dsign * mv[b]["to"]["line"], mv[b]["to"]["t"], b)
        b = sorted(pool, key=key)[0]
        extreme = {"book": b, "value": val(mv[b]["to"])}
    return {"kind": "price" if ml else "line", "state": state, "t_c": t_c,
            "pin": {"from": val(pin["fr"]), "to": val(pin["to"])},
            "books": len(books), "same_way": len(same) if same is not None else None,
            "by_book": {b: [val(mv[b]["fr"]), val(mv[b]["to"])] for b in us}, "extreme": extreme}, None


# ---------- the mini charts ----------

def downsample(pts, n=FLAGS_SERIES_N):
    """At most `n` points of a step series [[x, value], ...]: consecutive equal values dropped (the value holds until the next change; the last
    point is kept so the series still reaches its end), the first point, the last point and the lowest and highest value always kept, the rest
    evenly spaced by index. Order and values are never changed."""
    pts = [list(p) for p in pts]
    if not pts:
        return []
    ded = [pts[0]]
    for p in pts[1:]:
        if p[1] != ded[-1][1]:
            ded.append(p)
    if ded[-1][0] != pts[-1][0]:
        ded.append(pts[-1])
    if len(ded) <= n:
        return ded
    prio = [0, len(ded) - 1, min(range(len(ded)), key=lambda i: (ded[i][1], i)), max(range(len(ded)), key=lambda i: (ded[i][1], -i))]
    keep = set(prio[:max(n, 0)])                                 # priority: first, last, lowest, highest (a tiny `n` never exceeds itself)
    free = n - len(keep)
    rest = [i for i in range(len(ded)) if i not in keep]
    if free > 0 and rest:
        step = len(rest) / free
        keep.update(rest[min(len(rest) - 1, int(k * step))] for k in range(free))
    return [ded[i] for i in sorted(keep)]


def _series_pts(rd, asof, now_line=None):
    """[(t, value)] of the readable rows inside the window plus the row showing when it opened (placed at the window start). `now_line`: the price series
    of a spread or total at that line only: the row showing at the window start counts only when it is at that line (as in `flag_pin`), else the series
    starts at the first quote at that line inside the window."""
    ws = asof - FLAGS_WINDOW
    at = lambda r: now_line is None or (_n(r["line"]) and abs(r["line"] - now_line) <= LINE_EPS)
    before = [r for r in rd if r["t"] <= ws]
    hang = before[-1] if before and at(before[-1]) else None                  # the row showing at the window start, only if it is at the current line
    inw = [r for r in rd if r["t"] > ws and at(r)]
    return ([(ws, hang)] if hang else []) + [(r["t"], r) for r in inw]


def flag_series(rows, g, norm, asof, n=FLAGS_SERIES_N):
    """The two mini-chart series, or None when nothing is readable: Pinnacle's price for the side (at Pinnacle's current line on a spread or
    total) and, on spreads and totals, every stored book's line. x = whole minutes after `t0`, `unit` min; a step chart."""
    if norm not in SIDES:
        return None
    by = _by_book(rows, asof)
    pin, _ = _pin_clean(by, g, norm)
    pin_pts = _series_pts([r for r in pin if r["px"] is not None], asof, None if g == "ml" else (pin[-1]["line"] if pin else None)) if pin else []
    lines = {}
    if g != "ml":
        for b in FLAGS_BOOKS:
            rd = [r for r in _reads(by.get(b), g, norm) if _n(r["line"])]
            if rd:
                lines[b] = _series_pts(rd, asof)
    allp = list(pin_pts) + [p for ps in lines.values() for p in ps]
    if not allp:
        return None
    t0 = min(t for t, _ in allp)
    mins = lambda t: int(round((t - t0) / 60))
    out = {"t0": t0, "unit": "min"}
    out["pin_px"] = downsample([[mins(t), r["px"]] for t, r in pin_pts], n) if pin_pts else None
    if g != "ml":
        out["lines"] = {b: downsample([[mins(t), r["line"]] for t, r in ps], n) for b, ps in lines.items()}
    return out


# ---------- the block ----------

def flags_block(rows, g, norm, asof, sport, heartbeat=None, n=FLAGS_SERIES_N):
    """-> (flags, series) for one shown play. `rows`: the book tape rows of the game (every book); `norm`: the play side's home | away | over |
    under (None = unmapped); `heartbeat`: {"pinnacle": epoch, "us": epoch} of the live feed or None (frozen cards and history: read as
    written). Each flag that cannot be read is None with its reason in `why`; the block itself is never absent."""
    pin, w_pin = flag_pin(rows, g, norm, asof, sport, heartbeat)
    line, w_line = flag_line(rows, g, norm, asof, sport, heartbeat)
    lim, w_lim = flag_limit(rows, g, asof)
    by = _by_book(rows, asof)
    pr = _pin_clean(by, g, norm)[0] if norm in SIDES else []
    fr = _window_from(pr, asof)
    span = round((asof - max(fr["t"], asof - FLAGS_WINDOW)) / 60) if fr else None
    dmap = {"toward": "toward", "away": "away", "quiet": "none"}
    a, c = (pin or {}).get("state"), (line or {}).get("state")
    flags = {"rule": FLAGS_RULE, "asof": asof, "window_min": FLAGS_WINDOW // 60, "span_min": span,
             "src_age_min": {"pinnacle": _age(asof, heartbeat, "pinnacle"), "us": _age(asof, heartbeat, "us")},
             "pin": pin, "limit": lim, "line": line,
             "a": a, "c": c, "direction": {"a": dmap.get(a), "c": dmap.get(c)},
             "books_moved": (line or {}).get("same_way"), "extreme": (line or {}).get("extreme"),
             "why": {"pin": w_pin, "limit": w_lim, "line": w_line}}
    return flags, flag_series(rows, g, norm, asof, n)


def mf_of(flags):
    """The `mf` key of a forward log row: a projection of the card's stored v2.flags (no by_book, no series). None flags give None (the
    caller decides between 'not logged' and 'dropped')."""
    if not isinstance(flags, dict):
        return None
    pin, lim, line = flags.get("pin") or {}, flags.get("limit") or {}, flags.get("line") or {}
    ex = line.get("extreme") or {}
    return {"rule": flags.get("rule"), "asof": flags.get("asof"), "span_min": flags.get("span_min"), "src_age_min": flags.get("src_age_min"),
            "pin_state": pin.get("state"), "pin_pts": pin.get("pts"), "pin_from": pin.get("from"), "pin_to": pin.get("to"), "pin_line": pin.get("line"),
            "lim_from": lim.get("from"), "lim_to": lim.get("to"),
            "line_kind": line.get("kind"), "line_state": line.get("state"), "line_pin_from": (line.get("pin") or {}).get("from"),
            "line_pin_to": (line.get("pin") or {}).get("to"), "line_books": line.get("books"), "line_same_way": line.get("same_way"),
            "line_extreme_book": ex.get("book"), "line_extreme": ex.get("value"), "why": flags.get("why")}


def flags_fields():
    """`live.json` v2_plays.flags: the thresholds, window and books the page reads (never its own constants)."""
    return {"rule": FLAGS_RULE, "spec": "docs/sharps-v2-flags-spec.md", "t_a": {k: dict(v) for k, v in FLAGS_T_A.items()},
            "t_c": {k: dict(v) for k, v in FLAGS_T_C.items()}, "window_min": FLAGS_WINDOW // 60, "stale_min": FLAGS_STALE // 60,
            "series_points": FLAGS_SERIES_N, "limit_schedule_share": dict(LIMIT_SCHEDULE_SHARE), "limit_share_basis": LIMIT_SHARE_BASIS, "books": list(FLAGS_BOOKS),
            "limit_is_a_fact_only": True, "context_only": True}
