"""Bankroll Builder combos: two-leg slips built ONLY from Bankroll Builder picks, tracked as a separate SHADOW record. LOCAL: the prices are SmartStake's (licensed).

  python3 scripts/bankroll_combos.py             # one live pass: find combos from the open picks, follow prices, settle from the picks' results, write the record
  python3 scripts/bankroll_combos.py --dry       # print the combos the rules would log right now
  python3 scripts/bankroll_combos.py --backfill  # rebuild the history from the stored picks (see BACKFILL); refuses when live combos are on file unless --force

THE RULES (fixed 2026-10-27, before any combo had settled; docs: nba/docs/experiment-log.md section 13). A combo is two Bankroll Builder picks at ONE sportsbook:
  mates  same game, same team, same side, and the two stats are a measured teammate pairing (assists with 3-pointers, points with assists: nba/docs/pickem-correlation-results.md).
         Its chance is the legs multiplied plus the measured lift (combo_calls.joint).
  cross  two different games. No lift: the legs are treated as independent.
  Everything else is not a combo: opponents in one game, a teammate pairing with no measured lift, two sides that disagree.
  Both legs must be open picks (not settled, game not tipped). Each leg's fair chance is the one logged on its pick (the median of 3+ other venues, margin removed). Price = the
  product of the two legs' prices at that book (the pick's book for both, so no book is ever asked for a leg it does not quote). Edge = joint chance x decimal odds - 1, must be >= 0.
  Caps: per slate (ET day of the earlier tip) at most 6 mates and 6 cross, first come, ranked by edge within a pass. Logged at the first pass it qualifies (its entry price), followed to
  tip (its closing price), graded flat 1 unit at the entry price from the picks' own settled results (a void leg voids the combo, as combo_calls does). A pick that has lost settles the combo as lost.

THIS IS A SHADOW. It is never in the Bankroll Builder headline and never a bet. Nothing is called good or bad before 100 settled combos and a closing-line value that is positive by 2 SE.
Changing a rule starts a new record.

BACKFILL. The history is rebuilt from the picks already on file (live and replayed), same rules, with two limits that keep every number a stored one: the entry price is the product of the
legs' own logged entry prices (each leg's price when IT was picked; the other leg's price at the later pick's moment was not stored), and the close is the product of the legs' logged closes.
Combos on games that have not tipped yet are not backfilled: the live pass logs them, as live. Backfilled combos are tagged source=replay and the record splits them from live ones. The picks themselves are partly replayed, so the whole backfill is in-sample.

State: data/smartstake/bankroll_combo_picks.json. Record: bankroll_combo_record.json, written to the owner's Firestore by smartstake_publish_alts.py. Nothing here is committed.
"""
import json
import sys
import time
from collections import Counter
from itertools import combinations
from pathlib import Path

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combo_calls as CC
import bankroll_builder as BB

SS = CC.SS
PICKS = BB.STATE
STATE, RECORD = SS / "bankroll_combo_picks.json", SS / "bankroll_combo_record.json"
CAP = {"mates": 6, "cross": 6}                       # per slate (ET day)
EDGE_MIN = 0.0


def _leg(p):
    return {"name": p["name"], "stat": p["stat"], "side": p["side"], "line": p["line"], "main": p.get("main", p["line"]), "odds": p["odds0"], "pm": p["pf0"],
            "gid": p["gid"], "tip": p["tip"], "team": p["team"], "pk": p["k"]}


def kind_of(a, b):
    """'mates', 'cross', or None for two picks."""
    if a["pid"] == b["pid"] or a["book"] != b["book"]:
        return None
    if a["gid"] != b["gid"]:
        return "cross"
    if a["team"] == b["team"] and a["side"] == b["side"] and tuple(sorted((a["stat"], b["stat"]))) in CC.FAMILIES:
        return "mates"
    return None


def open_picks(picks, now):
    return [p for p in picks.values() if not p.get("res") and p["tip"] > now and p.get("pf0") is not None and p.get("dec0")]


def candidates(pool, dec_of):
    """Every qualifying combo from a pool of picks. dec_of(a, b) -> the combo's decimal price, or None when it cannot be priced."""
    out = []
    for a, b in combinations(sorted(pool, key=lambda p: p["k"]), 2):
        kind = kind_of(a, b)
        if not kind:
            continue
        dec = dec_of(a, b)
        if not dec:
            continue
        legs = [_leg(a), _leg(b)]
        pj = CC.joint(legs) if kind == "mates" else legs[0]["pm"] * legs[1]["pm"]
        if pj * dec - 1 < EDGE_MIN:
            continue
        c = CC.mk_call(kind, a["book"], legs, pj, dec)
        c["pk"] = [l["pk"] for l in sorted(legs, key=lambda l: (l["name"], l["stat"], l["side"], l["line"]))]
        c["day"] = BB.et_day(min(a["tip"], b["tip"]))
        out.append(c)
    return out


def log_new(S, cands, now, source=None):
    """Log the candidates not on file yet, best edge first, under the per-slate caps. Returns how many were logged."""
    used = Counter((c["day"], c["type"]) for c in S.values())
    n = 0
    for c in sorted(cands, key=lambda c: -c["ev"]):
        if c["k"] in S or used[(c["day"], c["type"])] >= CAP[c["type"]]:
            continue
        used[(c["day"], c["type"])] += 1
        S[c["k"]] = {"k": c["k"], "type": c["type"], "book": c["book"], "first": now, "tip": c["tip"], "day": c["day"], "ev0": round(c["ev"], 4), "dec0": round(c["dec"], 4),
                     "pj0": round(c["pj"], 4), "legs": c["legs"], "pk": c["pk"]}
        if source:
            S[c["k"]]["source"] = source
        n += 1
    return n


def settle_from_picks(c, picks):
    """Settle from the picks' own results: any lost leg loses it, any void leg voids it, all won wins."""
    if c.get("res"):
        return
    rs = [picks.get(k, {}).get("res") for k in c["pk"]]
    for k, l in zip(c["pk"], sorted(c["legs"], key=lambda l: (l["name"], l["stat"], l["side"], l["line"]))):
        y = next((x.get("y") for x in (picks.get(k, {}).get("legs") or []) if x.get("name") == l["name"]), None)
        if y is not None:
            l["y"] = y
    if "void" in rs:
        c["res"], c["units"] = "void", 0.0
    elif "lost" in rs:
        c["res"], c["units"] = "lost", -1.0
    elif all(r == "won" for r in rs):
        c["res"], c["units"] = "won", round(c["dec0"] - 1, 4)
    else:
        return
    if c.get("decN"):
        c["clv"] = round(c["dec0"] / c["decN"] - 1, 4)


def summarize(S):
    calls = list(S.values())
    rec = CC.summarize(calls)
    rec["live"] = CC.summarize([c for c in calls if c.get("source") != "replay"])["all"]
    rec["replay"] = CC.summarize([c for c in calls if c.get("source") == "replay"])["all"]
    rec["rules"] = "v1"
    return rec


def run(dry=False):
    now = int(time.time())
    t, quotes = CC.latest_poll()
    if not quotes:
        print("no SmartStake NBA tape")
        return None
    picks = json.loads(PICKS.read_text())["picks"] if PICKS.exists() else {}
    props = CC.props_from(quotes)

    def dec_of(a, b):
        return CC.price_now({"book": a["book"], "legs": [_leg(a), _leg(b)]}, props)

    S = json.loads(STATE.read_text())["calls"] if STATE.exists() and not dry else {}
    pool = open_picks(picks, now)
    cands = candidates(pool, dec_of)
    print(f"{len(pool)} open picks, {len(cands)} qualifying combos: " + ", ".join(f"{n} {k}" for k, n in sorted(Counter(c['type'] for c in cands).items())))
    if dry:
        for c in sorted(cands, key=lambda c: -c["ev"])[:12]:
            print(f"  {c['type']:6} {c['book']:10} ev {c['ev']*100:5.1f}%  " + " + ".join(f"{l['name']} {l['side'][0]}{l['line']} {l['stat']} {l['odds']:+d}" for l in c["legs"]))
        return None
    new = log_new(S, cands, now)
    for c in S.values():
        if not c.get("res") and now < c["tip"]:
            d = CC.price_now(c, props)
            if d:
                c["decN"] = round(d, 4)
        settle_from_picks(c, picks)
    STATE.write_text(json.dumps({"calls": S, "asof": now}, separators=(",", ":")))
    rec = summarize(S)
    rec["asof"] = now
    RECORD.write_text(json.dumps(rec, separators=(",", ":")))
    a = rec["all"]
    print(f"combo shadow: {a['calls']} combos ({new} new), {a['settled']} settled, {a['units']}u, roi {a['roi']}, clv {a['clv']} (n {a['clv_n']})")
    return rec


def backfill(force=False):
    if STATE.exists() and not force and any(c.get("source") != "replay" for c in json.loads(STATE.read_text())["calls"].values()):
        print("live combos are on file: a backfill would erase them (pass --force to rebuild anyway)")
        return None
    picks = json.loads(PICKS.read_text())["picks"]
    now = int(time.time())
    S = {}
    ps = [p for p in picks.values() if p.get("pf0") is not None and p.get("dec0") and p["tip"] <= now]      # games still to come are left to the live pass, so they count as live
    byk = {p["k"]: p for p in ps}
    for t in sorted({p["first"] for p in ps}):                       # each moment a pick appeared: the combos that became possible then
        pool = [p for p in ps if p["first"] <= t and p["tip"] > t]
        cands = candidates(pool, lambda a, b: a["dec0"] * b["dec0"])
        log_new(S, [c for c in cands if t == max(byk[k]["first"] for k in c["pk"])], t, source="replay")
    for c in S.values():
        ds = [byk[k].get("decN") for k in c["pk"]]
        if all(ds):
            c["decN"] = round(ds[0] * ds[1], 4)
        settle_from_picks(c, picks)
    STATE.write_text(json.dumps({"calls": S, "asof": now, "backfill": now}, separators=(",", ":")))
    rec = summarize(S)
    rec["asof"] = now
    RECORD.write_text(json.dumps(rec, separators=(",", ":")))
    a = rec["all"]
    print(f"backfill: {a['calls']} combos, {a['settled']} settled, {a['units']}u, roi {a['roi']}, clv {a['clv']} (n {a['clv_n']})")
    for k, v in sorted(rec["type"].items()):
        print(f"  {k}: {v['calls']} combos, {v['settled']} settled, {v['units']}u, roi {v['roi']}")
    return rec


if __name__ == "__main__":
    if "--backfill" in sys.argv:
        backfill(force="--force" in sys.argv)
    else:
        run(dry="--dry" in sys.argv)
