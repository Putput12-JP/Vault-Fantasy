#!/usr/bin/env python3
"""`pinclose` rows: Pinnacle's closing no-vig price for the side of every graded shown play, stored once (docs/sharps-v2-grader-note.md,
docs/sharps-v2-plays-spec.md section 5.3). A new append-only row kind beside `result` and `close` in pm_record/cards/<sport>/<YYYY-MM>.jsonl:

  key  <sf result key>|pinclose        of  the sf result key        v  1
  close_fair  Pinnacle's no-vig fair for the play's side at the CLOSE: its last readable tape row at or before game start (inclusive)
  close_t     epoch seconds of that tape row (the tape writes on change, so this is the last change, not "read at")
  close_line  the side's own line at that row (spread, total); null on a moneyline
  price       the stored price at the cut (the result row's price), copied so CLV needs no other row
  line        the stored Polymarket line, which belongs to outcomes[0] (the favourite); side_line is the PLAY'S OWN line (line for outcomes[0], -line for
              outcomes[1] on a spread; a total's line is the same for both sides). Pinnacle's line for the side is compared with side_line, never with line.
  clv, pts    close_fair - price, and the same times 100 (points). Null unless the close is at the ticket's side line (a moneyline always is).
              It is a CLV "vs the close" only when close_after_cut is true; with it false the close is the same Pinnacle row the cut saw (or an older one),
              so the number is the price against Pinnacle's fair at the cut, and every statistic keeps the two apart.
  close_age_min, close_after_cut   minutes from close_t to start, and whether close_t is after the cut
  tape_last_t, tape_age_min   the last tape row of ANY book for the sport at or before start, and its age before start (the tape's liveness)
  pin_last_t, pin_age_min     the same for Pinnacle rows only (any game of the sport)
  fair_cut, line_cut   Pinnacle's no-vig fair and line for the side at its last readable row at or before the CUT
  move_pts    (close_fair - fair_cut) x 100, the market move after the cut; null unless both reads exist at the same Pinnacle line AND the tape saw a
              PINNACLE row (any game of the sport) between the cut and the start: with no Pinnacle row seen, "unchanged" is not a measurement
              (other books write between Pinnacle's 10 to 20 minute reads, so their rows do not show Pinnacle was re-read; move_why no_pinnacle_tape_after_cut)
              (move_at_ticket_line() narrows it to reads at the ticket's own side line, the tier prereg's wording)
  why, move_why   null when clv / move_pts is readable, else the stored reason (a null is a stored reason, never a 0 and never estimated)

Same side mapping and no-vig method as the market-move flags (scripts/sharps_v2/flags_v2.py `_reads`: two-way multiplicative, home / away /
over / under from the card's own team names). The close read is outcome-free and point in time: a tape row after game start is never read.
`move_pts` is exactly what move_grade_history.after_moves computes (same-line move); the tier prereg's stricter "ticket line main at both reads"
is a subset a reader can check from the stored `line`, `line_cut` and `close_line`.

Written once per graded sf play of variant all (voided and unpriced results get none), after the result row exists and at least GRACE seconds
after game start. A play is HELD, not written null, when the sport's tape (any book) does not run past its start (a missing or stale tape checkout must
never turn into permanent null rows), when its card file is missing, or when its side cannot be mapped to home or away. A null row stores its reason
and is final: the tape only ever grows forward, so a started game gets no later rows.

Sharp money is context only (CLAUDE.md): this is a record input, never a bet signal, never an input to Top Reads, SM_GATE or an agree total.

  python3 -I scripts/sharps_v2/pinclose.py --cards pmdata/pm_cards --out pmdata/pm_record --book-tape data/book_tape [--now EPOCH]

The step never breaks the grade: any problem prints a ::warning:: and writes nothing for the rows it could not read.
"""
import argparse, bisect, collections, glob, json, math, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)
import grade_side_cards as G  # noqa: E402                  # load_rows, append_rows, save_record: the grader's own row io
import build_side_cards as BSC  # noqa: E402                # BookTape, team_names, side_norms: the card's side mapping
from sharps_v2 import flags_v2 as F  # noqa: E402            # _reads: the registered no-vig read the flags use

VERSION = 1
RULE = "pinclose-1"
GRACE = 1800                       # seconds after game start before a close is written (a result row needs a resolved game, hours later)
SPORTS = ("nba", "nfl", "cfb", "cbb")
GROUPS = ("ml", "spread", "total")
SMALL_N = 30                       # a record under 30 plays is a small sample (one definition, as tier_history.SMALL_N)
NDIG = 6

WHY_NO_TAPE = "no_tape_rows_for_game"
WHY_NO_CLOSE = "no_pinnacle_at_or_before_start"
WHY_NO_CUT = "no_pinnacle_at_or_before_cut"
WHY_UNMAPPED = "side_unmapped"
WHY_NO_PRICE = "no_price"
WHY_LINE_CLOSE = "ticket_line_not_main_at_close"
WHY_NO_TICKET_LINE = "ticket_line_unknown"
WHY_NO_TAPE_AFTER_CUT = "no_pinnacle_tape_after_cut"
STALE_MIN = 60                     # a close older than this many minutes before start is reported as stale
WHY_LINE_MOVED = "pinnacle_line_changed_since_cut"


def _r(x):
    return round(x, NDIG) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def last_read(rows, g, norm, t):
    """Pinnacle's last readable row for the side at or before `t`: {t, line, fair} or None. A row is readable when its no-vig fair can be computed
    (flags_v2._reads; a spread or total row also needs its line). Ties on the time keep the later row of the tape, as move_grade_history does."""
    reads = F._reads([r for r in rows if isinstance(r, dict) and F._n(r.get("t")) and r["t"] <= t], g, norm)
    rd = sorted((r for r in reads if r["fair"] is not None), key=lambda r: r["t"])
    return rd[-1] if rd else None


def side_line(g, side, outs, line):
    """The play's own line from the stored result row. Polymarket stores a spread's `line` for outcomes[0] and the other side has the opposite sign
    (page: "The stored line belongs to the first outcome"); a total has one line for both sides; a moneyline has none. None when it cannot be told."""
    if g == "ml" or not F._n(line):
        return None
    if g == "total":
        return line
    if isinstance(outs, (list, tuple)) and len(outs) == 2 and side in outs:
        return line if outs[0] == side else -line
    return None


def side_norm(g, sides, names, side):
    """home / away / over / under for the shown side. A two-sided moneyline or spread whose OTHER side maps to a team is the opposite team, so a
    name the card spells differently from the tape ("Loyola (MD)") still resolves; when neither side maps it is None (the play is held)."""
    norms = BSC.side_norms(g, sides, names)
    n = norms.get(side)
    if n in F.SIDES:
        return n
    other = [x for x in sides if x != side]            # exactly one other side, and it is a team (a total's sides are over / under, never a team)
    if len(other) == 1 and norms.get(other[0]) in ("home", "away"):
        return "away" if norms[other[0]] == "home" else "home"
    return None


def read_close(rows, g, norm, gst, cut, ticket_line, price, how=None, tape_last_t=None, tape_after_cut=None, pin_last_t=None):
    """The stored fields of one pinclose row (everything except the identity keys), from the tape rows of the game. `ticket_line` is the play's OWN
    line (side_line). `rows` empty means no tape for the game (`how` is the tape's own reason). `tape_last_t` is the sport's tape liveness (any book, any game: the last row
    at or before start); `pin_last_t` the same for Pinnacle rows only; `tape_after_cut` whether a PINNACLE row of the sport lies in (cut, start]. When
    not given they are read from `rows` (the game's Pinnacle rows) alone."""
    out = {"close_fair": None, "close_t": None, "close_line": None, "close_age_min": None, "close_after_cut": None, "tape_last_t": None,
           "tape_age_min": None, "pin_last_t": None, "pin_age_min": None, "fair_cut": None, "line_cut": None, "clv": None, "pts": None, "move_pts": None, "why": None, "move_why": None}
    times = [r["t"] for r in rows if isinstance(r, dict) and F._n(r.get("t"))]
    if tape_last_t is None:
        tape_last_t = max((t for t in times if t <= gst), default=None)
    if pin_last_t is None:
        pin_last_t = max((t for t in times if t <= gst), default=None)
    if tape_after_cut is None:
        tape_after_cut = any(cut < t <= gst for t in times)
    out["tape_last_t"] = tape_last_t
    out["tape_age_min"] = round((gst - tape_last_t) / 60, 1) if F._n(tape_last_t) else None
    out["pin_last_t"] = pin_last_t
    out["pin_age_min"] = round((gst - pin_last_t) / 60, 1) if F._n(pin_last_t) else None
    if not rows:
        out["why"] = out["move_why"] = how or WHY_NO_TAPE
        return out
    if norm not in F.SIDES:
        out["why"] = out["move_why"] = WHY_UNMAPPED
        return out
    close = last_read(rows, g, norm, gst)
    if close is None:
        out["why"] = out["move_why"] = WHY_NO_CLOSE
        return out
    out.update(close_fair=_r(close["fair"]), close_t=close["t"], close_line=_r(close["line"]),
               close_age_min=round((gst - close["t"]) / 60, 1), close_after_cut=bool(close["t"] > cut))
    # CLV is close minus the price at the cut, so the close must be the same line the price was for
    if not (isinstance(price, (int, float)) and not isinstance(price, bool) and 0 < price < 1):
        out["why"] = WHY_NO_PRICE
    elif g != "ml" and not F._n(ticket_line):
        out["why"] = WHY_NO_TICKET_LINE
    elif g != "ml" and not (F._n(close["line"]) and abs(close["line"] - ticket_line) <= F.LINE_EPS):
        out["why"] = WHY_LINE_CLOSE
    else:
        out["clv"] = _r(out["close_fair"] - price)
        out["pts"] = round((out["close_fair"] - price) * 100, 2)
    at_cut = last_read(rows, g, norm, cut)
    if at_cut is None:
        out["move_why"] = WHY_NO_CUT
        return out
    out.update(fair_cut=_r(at_cut["fair"]), line_cut=_r(at_cut["line"]))
    if not tape_after_cut:
        out["move_why"] = WHY_NO_TAPE_AFTER_CUT
    elif g != "ml" and not (F._n(at_cut["line"]) and F._n(close["line"]) and abs(at_cut["line"] - close["line"]) <= F.LINE_EPS):
        out["move_why"] = WHY_LINE_MOVED
    else:
        out["move_pts"] = round((out["close_fair"] - out["fair_cut"]) * 100, 2)
    return out


def move_at_ticket_line(row):
    """The move after the cut for a stored row, only when it was read at the ticket's own line at both reads (the tier prereg's wording: "on a
    spread or total, the ticket line to be Pinnacle's main line at both"). A moneyline has no line. None otherwise (never 0). `move_pts` itself is
    the looser same-Pinnacle-line move the flags prereg uses."""
    m = row.get("move_pts")
    if not F._n(m):
        return None
    if row.get("group") == "ml":
        return m
    ticket, at_cut, at_close = row.get("side_line"), row.get("line_cut"), row.get("close_line")
    if all(F._n(x) for x in (ticket, at_cut, at_close)) and abs(ticket - at_cut) <= F.LINE_EPS and abs(ticket - at_close) <= F.LINE_EPS:
        return m
    return None


class TapeClock:
    """The times of every non-backfill row of a sport's tape files, any book and any game (data/book_tape/<sport>/<YYYY-MM>.jsonl): the tape's
    liveness. A tape that wrote nothing between a play's cut and its start tells nothing about whether Pinnacle moved, and rows of other books do not
    say Pinnacle was re-read either (its rows sit on a 10 to 20 minute grid), so the move rule asks for a PINNACLE row of the sport in the window."""

    def __init__(self, root):
        self.root, self.ts = root, {}

    def _times(self, sport, pin=False):
        """Sorted times of the sport's rows: every book, or with pin=True only Pinnacle's."""
        if (sport, pin) not in self.ts:
            out = []
            for fn in sorted(glob.glob(os.path.join(self.root or "", sport, "[0-9][0-9][0-9][0-9]-[0-9][0-9].jsonl"))):
                with open(fn) as f:
                    for line in f:
                        try:
                            r = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(r, dict) and not r.get("bf") and F._n(r.get("t")) and (not pin or r.get("book") == "Pinnacle"):
                            out.append(r["t"])
            out.sort()
            self.ts[(sport, pin)] = out
        return self.ts[(sport, pin)]

    def last(self, sport):
        t = self._times(sport)
        return t[-1] if t else None

    def last_at(self, sport, at, pin=False):
        t = self._times(sport, pin)
        i = bisect.bisect_right(t, at)
        return t[i - 1] if i else None

    def any_between(self, sport, lo, hi, pin=False):
        """True when a row (of Pinnacle only, with pin=True) lies in (lo, hi]."""
        t = self._times(sport, pin)
        i = bisect.bisect_right(t, lo)
        return i < len(t) and t[i] <= hi


def shown_graded(r):
    """The result rows that get a close: the shown play (sf, variant all) once graded. Void and unpriced results get none."""
    return (isinstance(r, dict) and r.get("kind") == "result" and r.get("play") == "sf" and r.get("variant") == "all"
            and r.get("status") == "graded" and isinstance(r.get("key"), str))


def build_rows(have, cards_dir, tape, now, clock=None):
    """-> (new rows, held {reason: n}). `have`: every stored row by key (the append-only guard: a key that exists is never written again)."""
    new, held = [], collections.Counter()
    clock = clock or TapeClock(getattr(tape, "root", None))
    cards = {}
    for key in sorted(k for k, r in have.items() if shown_graded(r)):
        r = have[key]
        pk = key + "|pinclose"
        if pk in have:
            continue
        gst, cut = r.get("gst"), r.get("cut")
        if not (isinstance(gst, (int, float)) and isinstance(cut, (int, float))):
            held["no_start_or_cut"] += 1
            continue
        if now < gst + GRACE:
            held["too_soon_after_start"] += 1
            continue
        rel = r.get("card")
        if rel not in cards:
            cards[rel] = G.jload(os.path.join(cards_dir, rel), None) if isinstance(rel, str) else None
        c = cards[rel]
        g = r.get("group")
        if not c or g not in (c.get("markets") or {}):
            held["card_missing"] += 1
            continue
        sport = r.get("sport")
        top = clock.last(sport)
        if top is None or top < gst:
            held["tape_not_through_start"] += 1
            continue
        try:
            rows, how = tape.game(sport, c.get("vault"), c.get("ev"), c.get("gst"))
            sides = list((c["markets"][g].get("sides") or {}).keys())
            norm = side_norm(g, sides, BSC.team_names(c.get("vault"), c.get("ev"), sport), r.get("side"))
            if rows and norm is None:                     # no tape for the game needs no side: that null is final whatever the names are
                held["side_unmapped"] += 1                # hold: a spelling fix later can still resolve it; a final null row could not be undone
                continue
            sl = side_line(g, r.get("side"), r.get("outs"), r.get("line"))
            f = read_close(rows, g, norm, gst, cut, sl, r.get("price"), how, clock.last_at(sport, gst), clock.any_between(sport, cut, gst, pin=True), clock.last_at(sport, gst, pin=True))
        except Exception as e:                   # one unreadable play is held for the next run, never a stop for the others
            print("::warning::pinclose %s held: %s: %s" % (key, type(e).__name__, e), file=sys.stderr)
            held["read_error"] += 1
            continue
        new.append({"key": pk, "kind": "pinclose", "of": key, "v": VERSION, "sport": sport, "ev": r.get("ev"), "gst": gst, "cut": cut,
                    "group": g, "side": r.get("side"), "line": r.get("line"), "side_line": sl, "price": r.get("price"), "graded_at": now, **f})
    return new, dict(held)


# ---------- the record (pinclose_record.json) ----------

def mean_se(xs):
    n = len(xs)
    if not n:
        return None, None
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else None
    return m, (sd / math.sqrt(n) if sd is not None else None)


def stat(xs):
    """{n, mean_pts, se_pts, small_sample} of a list of point values; mean and se null when there are none (never 0)."""
    m, se = mean_se(xs)
    return {"n": len(xs), "mean_pts": round(m, 3) if m is not None else None, "se_pts": round(se, 3) if se is not None else None,
            "small_sample": len(xs) < SMALL_N}


def summary(plays, closes):
    """One slice: the graded shown plays, how many have a stored close and why the rest do not, how fresh those closes are, and the numbers.
    `clv` is CLV vs the close and counts only closes AFTER the cut; a close at or before the cut (the same Pinnacle row the cut saw, or an older one)
    is reported apart as `price_vs_fair_at_cut`, because it is the price against Pinnacle's fair at the cut, not against a close."""
    have = [closes[p["key"]] for p in plays if p["key"] in closes]
    withc = [c for c in have if c.get("close_fair") is not None]
    why = collections.Counter(c.get("why") or "" for c in have if c.get("close_fair") is None)
    clv_why = collections.Counter(c["why"] for c in withc if c.get("pts") is None)
    pts = lambda cs: [c["pts"] for c in cs if isinstance(c.get("pts"), (int, float))]
    after = [c for c in withc if c.get("close_after_cut") is True]
    before = [c for c in withc if c.get("close_after_cut") is not True]
    old = [c for c in withc if isinstance(c.get("close_age_min"), (int, float)) and c["close_age_min"] > STALE_MIN]
    share = lambda n: round(n / len(withc), 4) if withc else None
    return {"graded": len(plays), "pending": len(plays) - len(have), "with_close": len(withc),
            "no_close_by_reason": dict(sorted(why.items())), "clv_unreadable_by_reason": dict(sorted(clv_why.items())),
            "close_after_cut": {"true": len(after), "false": len(before), "false_share": share(len(before)),
                                "older_than_%d_min" % STALE_MIN: len(old), "older_share": share(len(old))},
            "clv": stat(pts(after)),
            "price_vs_fair_at_cut": stat(pts(before)),
            "move": stat([c["move_pts"] for c in have if isinstance(c.get("move_pts"), (int, float))]),
            "move_by_reason": dict(sorted(collections.Counter(c["move_why"] for c in have if c.get("move_why")).items())),
            "move_at_ticket_line": stat([m for m in (move_at_ticket_line(c) for c in have) if m is not None])}


def record(rows, now, held=None):
    """pinclose_record.json: per sport (and market) the share of graded shown plays with a stored close, the reasons, and the mean CLV and move
    after the cut in points with one standard error. In-sample for every play graded before the rule existed; context only, never a signal."""
    closes = {r["of"]: r for r in rows if isinstance(r, dict) and r.get("kind") == "pinclose" and isinstance(r.get("of"), str)}
    plays = [r for r in rows if shown_graded(r)]
    out = {"generated": now, "v": VERSION, "rule": RULE, "context_only": True,
           "basis": ("Pinnacle's no-vig fair for the play's side at its last readable tape row at or before game start, against the price at the cut "
                     "(clv = close fair minus price, counted as CLV vs the close only when that row is after the cut; otherwise price_vs_fair_at_cut) and "
                     "against Pinnacle's own fair at the cut (move, null when the tape saw no row between the cut and the start). Points. A play whose "
                     "tape does not cover the game, or whose close is at another line, is counted by reason, never estimated. Report only: sharp money "
                     "is context, not a signal."),
           "held_last_run": dict(sorted((held or {}).items())), "sports": {}}
    for sp in SPORTS:
        ps = [p for p in plays if p.get("sport") == sp]
        if not ps:
            continue
        s = summary(ps, closes)
        s["by_market"] = {g: summary([p for p in ps if p.get("group") == g], closes) for g in GROUPS if any(p.get("group") == g for p in ps)}
        out["sports"][sp] = s
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cards", required=True, help="pm_cards folder (frozen cards)")
    ap.add_argument("--out", required=True, help="pm_record folder")
    ap.add_argument("--book-tape", default="data/book_tape")
    ap.add_argument("--now", type=int)
    a = ap.parse_args(argv)
    now = a.now or int(time.time())
    try:
        have = G.load_rows(a.out)
        new, held = build_rows(have, a.cards, BSC.BookTape(a.book_tape), now)
        G.append_rows(a.out, new)
        rec = record(list(have.values()) + new, now, held)
        G.save_record(os.path.join(a.out, "pinclose_record.json"), rec)
    except Exception as e:                       # context: never breaks the grade or the other files
        print("::warning::pinclose step skipped: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        return 0
    with_close = sum(1 for r in new if r["close_fair"] is not None)
    print(json.dumps({"pinclose_new_rows": len(new), "with_close": with_close, "held": held}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
