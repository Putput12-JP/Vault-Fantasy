"""Shadow log: do Circa and Bookmaker game-line moves lead the market? (NFL and NBA)

  python3 scripts/smartstake_lead_log.py            # nfl and nba
  python3 scripts/smartstake_lead_log.py nba

Reads   data/smartstake/<league>/*.jsonl.gz     (written by smartstake_record.py)
Writes  data/smartstake/lead_log.jsonl          append-only: one line per "first" divergence and one per settled game
        data/smartstake/lead_state.json         resume state (per-game first/close, pass cursor)
        data/smartstake/lead_summary.json       per league and market: n of 50, toward/away, mean move, SE, verdict

Port of trackLead (scripts/snapshot-game-history.mjs) and score_sharp_lead() (scripts/build_model_scoreboard.py):
  * lead books Circa and Bookmaker; controls FanDuel and DraftKings (a book merely off the pack gets pulled back
    toward it too, which is not sharp money, so a lead must beat the better control)
  * reference r = median of the OTHER recreational books' main line (needs 3+), junk quotes dropped
  * "first" = the first pass 3h+ before kickoff where the book sat >= the gap off r; "close" rolls forward until kickoff
  * movement = sign(book - r at first) * (r at close - r at first); toward = > +dead zone, away = < -dead zone
  * verdict needs 50+ games for the lead book and a gap over the better control of 2+ standard errors

Differences from the Pinnacle version, all forced by the data:
  * main line per book (the pair whose two prices are closest), compared on the LINE, not a price-adjusted fair
    line, because that conversion needs a fitted margin SD and there is none stored for the NBA. A price-only move
    at the same number is invisible to spreads and totals.
  * moneylines are compared on the no-vig home win probability. The gap is the spread gap (0.5 pts) converted with
    the stored NFL sd_margin (data/game_model.json): 0.5 * pdf(0) / sd. It is applied to the NBA too, which is a
    stretch (no stored NBA SD), and is flagged in the summary.

LOCAL ONLY. SmartStake's terms forbid committing, publishing or showing their data without written permission, so
every output is under data/smartstake/ (gitignored). Context only: never a bet signal, counts toward no agree total.
Circa is thin (about 82 NBA and 646 NFL quotes per pass), so most games will have no Circa main line at all.
"""
import glob
import gzip
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smartstake_to_book_tape import SPORT, main_pair  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SS = Path(os.environ.get("SMARTSTAKE_DIR") or ROOT / "data" / "smartstake")   # override when running from a worktree
LOG, STATE, SUMMARY = SS / "lead_log.jsonl", SS / "lead_state.json", SS / "lead_summary.json"

LEAD_BOOKS = ["circa", "bookmaker"]
CONTROLS = ["fanduel", "draftkings"]
REC_BOOKS = {"fanduel", "draftkings", "betrivers", "betmgm", "caesars", "fanatics", "bet365"}  # the tape's names
MARKETS = ["sp", "to", "ml"]
LEAD_MIN_H, MIN_REF = 3, 3
LIM = {"sp": 2.5, "to": 3.5, "ml": None}          # junk-quote filter around the median, as in bookFairs
MIN_GAMES, Z = 50, 2                               # verdict rule (score_sharp_lead)
GAP_PTS, DEAD_PTS = 0.5, 0.05                      # LEAD_GAP, and the toward/away dead zone
try:
    SD_NFL = json.load(open(ROOT / "data" / "game_model.json"))["sd_margin"]
except Exception:
    SD_NFL = None
# 0.5 pts of margin expressed as win probability at a pick'em: gap * pdf(0) / sd. None when the SD is not stored.
P_PER_PT = (1 / math.sqrt(2 * math.pi)) / SD_NFL if SD_NFL else None
GAP = {"sp": GAP_PTS, "to": GAP_PTS, "ml": GAP_PTS * P_PER_PT if P_PER_PT else None}
DEAD = {"sp": DEAD_PTS, "to": DEAD_PTS, "ml": DEAD_PTS * P_PER_PT if P_PER_PT else None}


def med(a):
    s = sorted(a)
    if not s:
        return None
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def imp(o):
    return -o / (-o + 100) if o < 0 else 100 / (o + 100)


def devig(a, b):
    pa, pb = imp(a), imp(b)
    return pa / (pa + pb) if pa > 0 and pb > 0 else None


def book_values(league, quotes):
    """book -> {sp: home line, to: total line, ml: home win prob} from each book's main (non-alt, non-live) lines."""
    pre = SPORT[league] + "_"
    by = {}
    for q in quotes:
        if q.get("player_id") or q.get("alternate") or q.get("live"):
            continue
        k, b = q["market_key"], q["book"]
        if k == pre + "moneyline":
            mk = "ml"
        elif k == pre + "points_handicap" and q.get("line") is not None:
            mk = "sp"
        elif k == pre + "points" and q.get("line") is not None:
            mk = "to"
        else:
            continue
        by.setdefault(b, {}).setdefault(mk, []).append(q)
    out = {}
    for b, mkts in by.items():
        v = {}
        if "ml" in mkts:
            s = {q["side"]: q["odds"] for q in mkts["ml"]}
            if "hometeam" in s and "awayteam" in s:
                p = devig(s["hometeam"], s["awayteam"])
                if p is not None:
                    v["ml"] = p
        if "sp" in mkts:
            m = main_pair(mkts["sp"], "sp")
            if m:
                v["sp"] = m["hometeam"]["line"]
        if "to" in mkts:
            m = main_pair(mkts["to"], "tot")
            if m:
                v["to"] = m["over"]["line"]
        if v:
            out[b] = v
    return out


def clean(vals, lim):
    if lim is None or len(vals) < 3:
        return vals
    m = med(list(vals.values()))
    return {b: x for b, x in vals.items() if abs(x - m) <= lim}


def load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"cursor": {}, "games": {}}


def emit(rows):
    if rows:
        with open(LOG, "a") as f:
            f.write("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))


def ingest(league, st):
    """Walk new passes in time order; same bookkeeping as trackLead. Returns appended log rows."""
    rows, cur = [], st["cursor"].get(league, 0)
    for f in sorted(glob.glob(str(SS / league / "*.jsonl.gz"))):
        for line in gzip.open(f, "rt", encoding="utf-8"):
            p = json.loads(line)
            t = p["t"] // 1000
            if p["t"] <= cur:
                continue
            cur = p["t"]
            events = {}
            for q in p["quotes"]:
                events.setdefault(q["event_id"], []).append(q)
            for ev, qs in events.items():
                kick = int(datetime.fromisoformat(qs[0]["starts_at"].replace("Z", "+00:00")).timestamp())
                if t >= kick:
                    continue
                bv = book_values(league, qs)
                g = st["games"].setdefault(f"{league}|{ev}", {
                    "league": league, "away": qs[0]["away"], "home": qs[0]["home"], "kick": kick, "lead": {}, "settled": False})
                for mk in MARKETS:
                    if GAP[mk] is None:
                        continue
                    vals = clean({b: v[mk] for b, v in bv.items() if mk in v and b in REC_BOOKS | set(LEAD_BOOKS)}, LIM[mk])
                    for b in LEAD_BOOKS + CONTROLS:
                        ref = [x for k, x in vals.items() if k in REC_BOOKS and k != b]
                        r = med(ref)
                        if r is None or len(ref) < MIN_REF:
                            continue
                        L = g["lead"].setdefault(mk, {}).setdefault(b, {})
                        L["close"] = {"t": t, "r": round(r, 4)}
                        if "first" not in L and b in vals and (kick - t) >= LEAD_MIN_H * 3600 and abs(vals[b] - r) >= GAP[mk]:
                            L["first"] = {"t": t, "b": round(vals[b], 4), "r": round(r, 4)}
                            rows.append({"kind": "first", "league": league, "event_id": ev, "away": g["away"], "home": g["home"],
                                         "kick": kick, "market": mk, "book": b, **L["first"]})
    st["cursor"][league] = cur
    return rows


def settle(st, now):
    """A game is graded once kicked off. Close must be within 6h of kickoff (score_sharp_lead)."""
    rows = []
    for key, g in st["games"].items():
        if g["settled"] or g["kick"] > now:
            continue
        g["settled"] = True
        for mk, books in g["lead"].items():
            for b, x in books.items():
                f, cl = x.get("first"), x.get("close")
                if not f or not cl or g["kick"] - cl["t"] > 6 * 3600:
                    continue
                sgn = 1 if f["b"] > f["r"] else -1
                x["move"] = sgn * (cl["r"] - f["r"])
                rows.append({"kind": "final", "league": g["league"], "event_id": key.split("|", 1)[1], "away": g["away"], "home": g["home"],
                             "kick": g["kick"], "market": mk, "book": b, "move": round(x["move"], 4), "first": f, "close": cl})
    return rows


def summarize(st):
    moves, coverage = {}, {}
    for g in st["games"].values():
        for mk, books in g["lead"].items():
            for b, x in books.items():
                coverage.setdefault((g["league"], mk, b), [0, 0])[0] += 1          # games with a usable reference
                if "first" in x:
                    coverage[(g["league"], mk, b)][1] += 1                          # ... that ever diverged
                if "move" in x:
                    moves.setdefault((g["league"], mk, b), []).append(x["move"])
    out = {}
    for (lg, mk, b), mv in sorted(moves.items()):
        n = len(mv)
        m = sum(mv) / n
        se = (sum((v - m) ** 2 for v in mv) / n) ** .5 / n ** .5 if n > 1 else None
        out.setdefault(lg, {}).setdefault(mk, {})[b] = {
            "n": n, "toward": sum(v > DEAD[mk] for v in mv), "away": sum(v < -DEAD[mk] for v in mv),
            "mean_move": round(m, 4), "se": None if se is None else round(se, 4)}
    for lg in st["cursor"]:
        for mk in MARKETS:
            d = out.setdefault(lg, {}).setdefault(mk, {})
            d["unit"] = "win prob" if mk == "ml" else "points"
            for b in LEAD_BOOKS:
                cs = [d[c] for c in CONTROLS if c in d and d[c]["se"] is not None]
                x = d.get(b)
                n = x["n"] if x else 0
                cov = coverage.get((lg, mk, b), [0, 0])
                v = {"games_with_reference": cov[0], "games_diverged": cov[1], "n_graded": n}
                if not x or n < MIN_GAMES or x["se"] is None or not cs:
                    v["verdict"] = f"too few games ({n} of {MIN_GAMES}): no claim"
                else:
                    c = max(cs, key=lambda y: y["mean_move"])
                    gap, se = x["mean_move"] - c["mean_move"], (x["se"] ** 2 + c["se"] ** 2) ** .5
                    v["verdict"] = (f"lead supported vs better control (context only; gap {gap:+.4f}, z {gap / se:+.1f})"
                                    if se and gap > Z * se else f"no lead: not ahead of the better control (gap {gap:+.4f}, z {gap / se if se else 0:+.1f})")
                d.setdefault("verdicts", {})[b] = v
    return out


def thin_note(league):
    """Quotes per pass for the lead books on the latest pass, so the thinness is stated, not assumed."""
    files = sorted(glob.glob(str(SS / league / "*.jsonl.gz")))
    if not files:
        return {}
    last = None
    for line in gzip.open(files[-1], "rt", encoding="utf-8"):
        last = line
    if not last:
        return {}
    c = {}
    for q in json.loads(last)["quotes"]:
        if q["book"] in LEAD_BOOKS and not q.get("player_id") and not q.get("alternate") and not q.get("live"):
            c[q["book"]] = c.get(q["book"], 0) + 1
    return c


def main():
    leagues = sys.argv[1:] or ["nfl", "nba"]
    SS.mkdir(parents=True, exist_ok=True)
    st, now = load(), int(time.time())
    for lg in leagues:
        st["cursor"].setdefault(lg, 0)
        emit(ingest(lg, st))
    emit(settle(st, now))
    summ = summarize(st)
    thin = {lg: thin_note(lg) for lg in leagues}
    json.dump({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "context_only": True,
               "rule": f"{MIN_GAMES}+ graded games and a gap over the better control of {Z}+ SE; otherwise no claim",
               "ml_gap_note": "ML gap is the 0.5 pt spread gap converted with the stored NFL sd_margin; applied to the NBA too (no stored NBA SD)",
               "lead_book_main_line_quotes_last_pass": thin, "results": summ}, open(SUMMARY, "w"), indent=1)
    json.dump(st, open(STATE, "w"))
    print("SmartStake Circa/Bookmaker lead shadow log. CONTEXT ONLY: not a bet signal, counts toward no agree total.")
    for lg in leagues:
        print(f"\n{lg.upper()}  lead-book main-line quotes on the latest pass: {thin.get(lg) or 'none'}  (Circa is thin)")
        for mk in MARKETS:
            d = summ.get(lg, {}).get(mk, {})
            for b in LEAD_BOOKS:
                v = d.get("verdicts", {}).get(b, {})
                print(f"  {mk:<2} {b:<9} n {v.get('n_graded', 0):>3} of {MIN_GAMES}  "
                      f"(games with a reference {v.get('games_with_reference', 0)}, diverged {v.get('games_diverged', 0)})  {v.get('verdict', '')}")
            for c in CONTROLS:
                if d.get(c):
                    print(f"  {mk:<2} {c:<9} n {d[c]['n']:>3}  control, mean move {d[c]['mean_move']:+.4f}")


if __name__ == "__main__":
    main()
