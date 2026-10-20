"""Track every Combo Check call, settle it from the box score, and keep the record. LOCAL: the prices are SmartStake's (licensed).

  python3 scripts/combo_calls.py                 # one pass: find the current calls, update prices, settle finished games, write the record
  python3 scripts/combo_calls.py --dry           # print the current calls only

A CALL is a play Combo Check puts in front of you, on the same rules as the page (docs: nba/docs/experiment-log.md section 11):
  straight  an alt bet with a 3%+ edge at a sportsbook, priced -140 to +200, at least a point off the main line
  mates     a teammate parlay (assists with a teammate's 3-pointers, or points with a teammate's assists, same side) at one book, 3%+ edge
  cross     the two best alt legs of one book from different games, as a parlay, 3%+ edge
The edge is the leg's price against the fair chance from OTHER venues quoting both sides of the SAME line (margin removed, 2+ venues);
a parlay's chance is the legs multiplied plus the measured teammate lift for the two passed pairings. Every call is logged at the FIRST poll it
appears (its entry price), followed until tip (its closing price), and graded flat 1 unit at the entry price. Calls that stop being shown stay
in the record. Sportsbook venues only: the page also shows exchange (Kalshi, Polymarket, Novig) straights, whose fees are not in the tape, so
they are not in this record.

DIFFERENCES FROM THE PAGE (the page also sees Pinnacle, Kalshi and Polymarket as fair-price sources and uses the model's minutes and roster
holds): here the player filter is the model's recent minutes >= 15 and the returning-player hold, and fair prices come from the tape alone.
Read the record as "what this rule set called", not as a replay of one browser session.

State: data/smartstake/combo_calls.json. Record: data/smartstake/combo_record.json, also written to the owner's Firestore (nbaAlts/_record) by
smartstake_publish_alts.py. Nothing here is committed.
"""
import glob
import gzip
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smartstake_props import NAMES, STAT, PREFIX

ROOT = Path(__file__).resolve().parent.parent
SS = ROOT / "data" / "smartstake"
STATE = SS / "combo_calls.json"
RECORD = SS / "combo_record.json"
MSCACHE = SS / "model_state_cache.json"
MS_URL = "https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/main/nba/data/model_state.json"
SCORE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={}"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={}"
ET = ZoneInfo("America/New_York")

EDGE_MIN = 0.03
CC_LO, CC_HI = 1 / 3, 0.5833            # a leg priced between +200 and -140
EXCH = {"novig"}                        # exchanges in the tape: fair-price sources only, never a bet venue here
FAMILIES = {("3pm", "ast"): 0.01044, ("ast", "pts"): 0.01066}     # data/pickem_corr.json, pass families, covariance at even odds (docs/pickem-correlation-results.md)
MIN_MINUTES, RET_DAYS = 15.0, 150
SETTLE_AFTER_S, MIN_BOX_MINUTES = 3 * 3600, 300
STAT_COL = {"pts": ["points"], "reb": ["rebounds"], "ast": ["assists"], "3pm": ["threePointFieldGoalsMade"], "pra": ["points", "rebounds", "assists"],
            "pr": ["points", "rebounds"], "pa": ["points", "assists"], "ra": ["rebounds", "assists"], "stl": ["steals"], "blk": ["blocks"],
            "sb": ["steals", "blocks"], "tov": ["turnovers"]}
PP_CORE = {"pts", "reb", "ast", "3pm", "pra", "pr", "pa", "ra"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", "", s)
    return re.sub(r"\s+", " ", re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)).strip()


def vkey(book):
    return re.sub(r"[^a-z0-9]", "", book.lower())


def prob(am):
    return 100 / (am + 100) if am > 0 else -am / (-am + 100)


def am_of(p):
    return round(-100 * p / (1 - p)) if p >= .5 else round(100 * (1 - p) / p)


def curl_json(url):
    p = subprocess.run(["curl", "-s", "--compressed", "--max-time", "40", url], capture_output=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


# ── inputs ──────────────────────────────────────────────────────────────
def model_state():
    """The model's live state from main (recent minutes, last game, team): cached six hours."""
    if not MSCACHE.exists() or time.time() - MSCACHE.stat().st_mtime > 6 * 3600:
        d = curl_json(MS_URL)
        if d and d.get("live"):
            MSCACHE.write_text(json.dumps(d["live"], separators=(",", ":")))
    live = json.loads(MSCACHE.read_text()) if MSCACHE.exists() else {}
    players = {}
    for pid, p in (live.get("players") or {}).items():
        if p.get("nm") and p.get("ms"):
            players[norm(p["nm"])] = {"min": p["ms"][0], "team": p["ms"][3], "last": p["ms"][4]}
    return players, live.get("team_last") or {}


def latest_poll(which="last"):
    files = sorted(glob.glob(str(SS / "nba" / "*.jsonl.gz")))
    if not files:
        return None, []
    last = None
    for line in gzip.open(files[-1 if which == "last" else 0], "rt", encoding="utf-8"):
        if which == "last":
            last = line
        else:
            last = line
            break
    p = json.loads(last)
    return p.get("t"), p["quotes"]


_SB = {}


def scoreboard(day):
    """ESPN games for one ET date: [{id, tip, away, home (full names), aabbr, habbr, done}]."""
    if day not in _SB:
        d = curl_json(SCORE_URL.format(day)) or {}
        out = []
        for e in d.get("events", []):
            try:
                c = e["competitions"][0]["competitors"]
                h = next(x for x in c if x["homeAway"] == "home")
                a = next(x for x in c if x["homeAway"] == "away")
                out.append({"id": e["id"], "tip": int(datetime.fromisoformat(e["date"].replace("Z", "+00:00")).timestamp()), "away": a["team"]["displayName"].lower(),
                            "home": h["team"]["displayName"].lower(), "aabbr": a["team"]["abbreviation"], "habbr": h["team"]["abbreviation"],
                            "done": bool(e["status"]["type"]["completed"])})
            except (KeyError, StopIteration, ValueError):
                continue
        _SB[day] = out
    return _SB[day]


def espn_game(away, home, start):
    d = datetime.fromtimestamp(start, ET).strftime("%Y%m%d")
    for g in scoreboard(d):
        if g["away"] == away and g["home"] == home and abs(g["tip"] - start) < 6 * 3600:
            return g
    return None


# ── legs ────────────────────────────────────────────────────────────────
def props_from(quotes):
    """{(event, player, stat): {away, home, start, q: {(book, line): {side: odds}}, mains: {book: line}}} for pregame quotes."""
    pre, stats = PREFIX["nba"], STAT["nba"]
    out = {}
    for q in quotes:
        if q.get("live") or q.get("line") is None or q.get("book") not in NAMES or q.get("side") not in ("over", "under") or not q.get("participant"):
            continue
        mk = q.get("market_key", "")
        st = stats.get(mk[len(pre):]) if mk.startswith(pre) else None
        if st not in PP_CORE:
            continue
        key = (q["event_id"], q["participant"], st)
        p = out.get(key)
        if p is None:
            p = out[key] = {"away": q["away"], "home": q["home"], "start": int(datetime.fromisoformat(q["starts_at"].replace("Z", "+00:00")).timestamp()), "q": {}, "mains": {}}
        book = NAMES[q["book"]]
        p["q"].setdefault((book, q["line"]), {})[q["side"]] = q["odds"]
        if not q.get("alternate"):
            p["mains"][book] = q["line"]
    return out


def fair(side, by_book, ex):
    ests = []
    for book, d in by_book.items():
        if vkey(book) == ex or "over" not in d or "under" not in d:
            continue
        co, cu = prob(d["over"]), prob(d["under"])
        ov = co + cu - 1
        if ov > (.08 if vkey(book) in EXCH else .16) or ov < -.01:
            continue
        ests.append((co if side == "over" else cu) / (co + cu))
    if len(ests) < 2:
        return None
    ests.sort()
    m = len(ests)
    return ests[m // 2] if m % 2 else (ests[m // 2 - 1] + ests[m // 2]) / 2


def all_legs(props, players, team_last, now):
    """Every alt leg that passes the page's rules: a sportsbook price in -140..+200, a point off main, fair from 2+ other venues."""
    legs = []
    for (ev, name, st), p in props.items():
        info = players.get(norm(name))
        if not info or info["min"] < MIN_MINUTES or p["start"] <= now:
            continue
        tl = team_last.get(info["team"])
        if tl and (tl - info["last"]) / 86400 >= RET_DAYS:         # the returning-player hold
            continue
        g = espn_game(p["away"], p["home"], p["start"])
        if not g or info["team"] not in (g["aabbr"], g["habbr"]):
            continue
        mains = Counter(p["mains"].values())
        if not mains:
            continue
        main = mains.most_common(1)[0][0]
        lines = {L for (_, L) in p["q"]}
        for L in lines:
            if abs(L - main) < 1 or L % 1 != .5:
                continue
            by_book = {b: d for (b, ll), d in p["q"].items() if ll == L}
            for side in ("over", "under"):
                for book, d in by_book.items():
                    if vkey(book) in EXCH or d.get(side) is None:
                        continue
                    cost = prob(d[side])
                    if cost < CC_LO - .0005 or cost > CC_HI + .0005:
                        continue
                    f = fair(side, by_book, vkey(book))
                    if f is None:
                        continue
                    legs.append({"name": name, "stat": st, "side": side, "line": L, "main": main, "book": book, "odds": d[side], "dec": 1 / cost, "pm": f,
                                 "ev": f / cost - 1, "gid": g["id"], "tip": g["tip"], "team": info["team"], "ev_id": ev})
    return legs


def joint(legs):
    ind = math.prod(l["pm"] for l in legs)
    adj = 0.0
    for i in range(len(legs)):
        for j in range(i + 1, len(legs)):
            a, b = legs[i], legs[j]
            if a["name"] == b["name"] or a["team"] != b["team"] or a["gid"] != b["gid"]:
                continue
            c0 = FAMILIES.get(tuple(sorted((a["stat"], b["stat"]))))
            if c0 is None:
                continue
            c = (1 if a["side"] == b["side"] else -1) * c0 * math.sqrt(a["pm"] * (1 - a["pm"]) * b["pm"] * (1 - b["pm"])) / .25
            adj += c * math.prod(l["pm"] for k, l in enumerate(legs) if k not in (i, j))
    return min(.999, max(.001, ind + adj))


def calls_from(legs):
    """The calls the page would list: straights (all 3%+), top 6 teammate parlays, top 4 cross-game parlays."""
    out = []
    best = {}
    for l in legs:
        k = (l["name"], l["stat"], l["side"], l["line"])
        if l["ev"] > 0 and (k not in best or l["ev"] > best[k]["ev"]):
            best[k] = l
    for l in best.values():
        if l["ev"] >= EDGE_MIN:
            out.append(mk_call("straight", l["book"], [l], l["pm"], l["dec"]))
    by_book = defaultdict(list)
    for l in legs:
        by_book[l["book"]].append(l)
    mates, cross = [], []
    for book, ls in by_book.items():
        rows = defaultdict(list)
        for l in ls:
            rows[(l["name"], l["stat"], l["side"])].append(l)
        keys = list(rows)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                ka, kb = keys[i], keys[j]
                A, B = rows[ka][0], rows[kb][0]
                if ka[0] == kb[0] or ka[2] != kb[2] or A["team"] != B["team"] or A["gid"] != B["gid"] or tuple(sorted((ka[1], kb[1]))) not in FAMILIES:
                    continue
                top = None
                for a in rows[ka]:
                    for b in rows[kb]:
                        pj, dec = joint([a, b]), a["dec"] * b["dec"]
                        if top is None or pj * dec > top[0]:
                            top = (pj * dec, [a, b], pj, dec)
                if top and top[0] - 1 >= EDGE_MIN:
                    mates.append(mk_call("mates", book, top[1], top[2], top[3]))
        pos = sorted((l for l in ls if l["ev"] > 0), key=lambda l: -l["ev"])
        pick, used = [], set()
        for l in pos:
            if l["gid"] in used:
                continue
            used.add(l["gid"])
            pick.append(l)
            if len(pick) == 2:
                break
        if len(pick) == 2:
            pj, dec = joint(pick), pick[0]["dec"] * pick[1]["dec"]
            if pj * dec - 1 >= EDGE_MIN:
                cross.append(mk_call("cross", book, pick, pj, dec))
    mates.sort(key=lambda c: -c["ev"])
    cross.sort(key=lambda c: -c["ev"])
    return out + mates[:6] + cross[:4]


def mk_call(kind, book, legs, pj, dec):
    legs = sorted(legs, key=lambda l: (l["name"], l["stat"], l["side"], l["line"]))
    key = "|".join([kind, book] + [f"{l['name']}|{l['stat']}|{l['side']}|{l['line']}" for l in legs])
    return {"k": key, "type": kind, "book": book, "ev": pj * dec - 1, "pj": pj, "dec": dec, "tip": min(l["tip"] for l in legs),
            "legs": [{"name": l["name"], "stat": l["stat"], "side": l["side"], "line": l["line"], "main": l["main"], "odds": l["odds"], "pm": round(l["pm"], 4),
                      "gid": l["gid"], "tip": l["tip"]} for l in legs]}


# ── state: first sighting, price now, settlement ───────────────────────
def price_now(call, props):
    """The product of the legs' CURRENT prices at the call's book, or None if any is gone."""
    dec = 1.0
    for l in call["legs"]:
        hit = None
        for (ev, name, st), p in props.items():
            if name == l["name"] and st == l["stat"]:
                d = p["q"].get((call["book"], l["line"]), {}).get(l["side"])
                if d is not None:
                    hit = 1 / prob(d)
                    break
        if hit is None:
            return None
        dec *= hit
    return dec


def box_by_name(gid):
    """{normalized name: {stat: value}} (None = did not play) once the game is final; cached; None if not final yet."""
    path = SS / "combo_results" / f"{gid}.json"
    if path.exists():
        return json.loads(path.read_text())
    d = curl_json(SUMMARY.format(gid))
    try:
        if not d["header"]["competitions"][0]["status"]["type"]["completed"]:
            return None
    except (KeyError, IndexError, TypeError):
        return None
    out = {}
    for team in (d.get("boxscore") or {}).get("players", []):
        for block in team.get("statistics", [])[:1]:
            keys = block.get("keys") or []
            for a in block.get("athletes", []):
                nm = norm(a["athlete"]["displayName"])
                if a.get("didNotPlay") or not a.get("stats"):
                    out[nm] = None
                    continue
                v = {}
                for key, raw in zip(keys, a["stats"]):
                    for part, name in zip(raw.split("-"), key.split("-")):
                        try:
                            v[name] = float(part)
                        except ValueError:
                            pass
                out[nm] = v
    if sum((v or {}).get("minutes", 0) for v in out.values()) < MIN_BOX_MINUTES:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")))
    return out


def settle(call, now):
    if call.get("res") or now < call["tip"] + SETTLE_AFTER_S:
        return
    res = []
    for l in call["legs"]:
        box = box_by_name(l["gid"])
        if box is None:
            return                                           # not final yet: tried again next pass
        v = box.get(norm(l["name"]), "absent")
        if v is None or v == "absent":
            call["res"], call["units"] = "void", 0.0         # a player who did not play voids the call (a book would drop the leg; kept simple and counted apart)
            return
        y = sum(v.get(c, 0) for c in STAT_COL[l["stat"]])
        res.append(y > l["line"] if l["side"] == "over" else y < l["line"])
        l["y"] = y
    call["res"] = "won" if all(res) else "lost"
    call["units"] = round(call["dec0"] - 1, 4) if call["res"] == "won" else -1.0
    if call.get("decN"):
        call["clv"] = round(call["dec0"] / call["decN"] - 1, 4)


# ── record ──────────────────────────────────────────────────────────────
def summarize(calls):
    def agg(cs):
        st = [c for c in cs if c.get("res") in ("won", "lost")]
        u = [c["units"] for c in st]
        clv = [c["clv"] for c in cs if c.get("clv") is not None]
        n = len(u)
        sd = statistics.pstdev(u) if n > 1 else 0
        return {"calls": len(cs), "settled": n, "void": sum(1 for c in cs if c.get("res") == "void"), "won": sum(1 for c in st if c["res"] == "won"),
                "units": round(sum(u), 2), "roi": round(sum(u) / n, 4) if n else None, "z": round(sum(u) / n / (sd / math.sqrt(n)), 2) if n > 1 and sd else None,
                "clv": round(statistics.mean(clv), 4) if clv else None, "clv_n": len(clv), "ev": round(statistics.mean(c["ev0"] for c in cs), 4) if cs else None}
    by = lambda f: {k: agg([c for c in calls if f(c) == k]) for k in sorted({f(c) for c in calls})}
    ebin = lambda c: "3-5%" if c["ev0"] < .05 else "5-8%" if c["ev0"] < .08 else "8%+"
    recent = sorted(calls, key=lambda c: -c["first"])[:80]
    return {"all": agg(calls), "type": by(lambda c: c["type"]), "book": by(lambda c: c["book"]), "edge": by(ebin),
            "recent": [{k: c.get(k) for k in ("type", "book", "first", "tip", "ev0", "dec0", "decN", "res", "units", "clv", "legs")} for c in recent]}


def run(dry=False, poll="last", state_path=STATE, now=None):
    now = now or int(time.time())
    t, quotes = latest_poll(poll)
    if not quotes:
        print("no SmartStake NBA tape")
        return None
    players, team_last = model_state()
    props = props_from(quotes)
    calls = calls_from(all_legs(props, players, team_last, now))
    print(f"{len(props)} props, {len(calls)} calls now: " + ", ".join(f"{n} {k}" for k, n in sorted(Counter(c['type'] for c in calls).items())))
    if dry:
        for c in calls[:12]:
            print(f"  {c['type']:8} {c['book']:10} ev {c['ev']*100:5.1f}%  " + " + ".join(f"{l['name']} {l['side'][0]}{l['line']} {l['stat']} {l['odds']:+d}" for l in c["legs"]))
        return None
    state = json.loads(Path(state_path).read_text()) if Path(state_path).exists() else {"calls": {}}
    S = state["calls"]
    for c in calls:                                            # first sighting = entry
        if c["k"] not in S:
            S[c["k"]] = {"k": c["k"], "type": c["type"], "book": c["book"], "first": now, "tip": c["tip"], "ev0": round(c["ev"], 4), "dec0": round(c["dec"], 4),
                         "pj0": round(c["pj"], 4), "legs": c["legs"]}
    for k, c in S.items():                                     # the price now, followed until tip: the last one seen is the close
        if not c.get("res") and now < c["tip"]:
            d = price_now(c, props)
            if d:
                c["decN"] = round(d, 4)
        settle(c, now)
    state["asof"] = now
    Path(state_path).write_text(json.dumps(state, separators=(",", ":")))
    rec = summarize(list(S.values()))
    rec["asof"] = now
    RECORD.write_text(json.dumps(rec, separators=(",", ":")))
    a = rec["all"]
    print(f"record: {a['calls']} calls, {a['settled']} settled, {a['units']} units, roi {a['roi']}, clv {a['clv']} (n {a['clv_n']})")
    return rec


if __name__ == "__main__":
    run(dry="--dry" in sys.argv)
