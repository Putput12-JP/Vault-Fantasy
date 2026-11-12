#!/usr/bin/env python3
"""Grade every frozen proven-sharps side card (step 4 of the side-card build, docs/side-card-record.md).

For each frozen card (pm_cards/<sport>/frozen/<date>/<slug>@<gst>.json on pm-holders-data) and each market group (ml, spread, total)
and variant (all, fwd), two plays are graded when the card has one:
  lock  the pre-registered lock (`lock_shadow`, docs/sharp-card-prereg.md): flat 1 unit at the stored price at the cut, plus the
        clean-ladder units as a second line
  sf    the size the card shows (`sf`, the benchmark's staking rules, labelled "untested rule"): flat 1 unit and the shown units

Rules, all from the pre-registration:
  - Result is the market's own Polymarket resolution (Gamma outcomePrices once closed and resolved). Every play is graded; none is
    dropped. A win pays 1 / price - 1, a loss -1, a push or 0.5 resolution 0.
  - Price is the one stored on the card at the cut. A play with no price, or a price older than 30 minutes before the cut, is
    unpriced: listed, never in ROI.
  - CLV = close minus the price at the cut, close from data/pm_closes.json (Pendulum Flow, last quote before kickoff), matched on
    event slug, market type, line and an identical outcome list. No close is ever estimated. CFB has no stored close.
  - Every row carries the card's `test.counts`; the record reads counted cards, and lists the rest by reason.

Never invents a number: every price, close and result is a stored value. Rows are append-only and written once:
  - a result row (keyed card|group|variant|play) as soon as the market resolves;
  - a close row (the same key + "|close") whenever its close shows up in pm_closes.json, however late. A play with no close row is
    counted as "no close stored" and is never estimated. Results never wait on closes, so a stalled closes feed cannot freeze a
    play without its CLV.

Sharp money is context only (CLAUDE.md): this is a record of a shadow test and of the card's shown size, never a pick feed.

usage: grade_side_cards.py --cards DIR --holders DIR --closes data/pm_closes.json --out DIR [--now EPOCH] [--no-fetch]
"""
import argparse, glob, json, os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pm_ledger import Client, Budget, gamma_facts, jload, jsave  # noqa: E402
from pm_data_api import PMDataError  # noqa: E402

GROUP_MT = {"ml": "moneyline", "spread": "spreads", "total": "totals"}
CLOSE_KEY = {"ml": "ml", "spread": "spreads", "total": "totals"}
STALE_PRICE = 30 * 60              # prereg "Unpriced": price_t more than 30 minutes before the cut
UNPRICED_FAIL = 0.10               # prereg: unpriced over 10% of a sport's counted moneyline locks = data-quality failure, no verdict
NO_CLOSES = {"cfb", "cbb"}         # prereg: CFB has no stored close, read on ROI only; CBB likewise (data/pm_closes.json has none)
BOOT_N, BOOT_SEED = 10000, 20261111
VERSION = 1


# ---------- pure logic (tests/test_side_card_record.py) ----------

def flat_profit(final, oi, price):
    """1 unit at `price` on outcome `oi` of a market resolved to `final` (list of 0 / 0.5 / 1)."""
    v = final[oi]
    if v == 1.0:
        return "win", 1.0 / price - 1.0
    if v == 0.0:
        return "loss", -1.0
    return "push", 0.0


def close_for(closes, sport, ev, group, line, outs, side):
    """The locked side's close from pm_closes.json, or None. `p` is the price of outcomes[0]."""
    g = (closes.get("games") or {}).get(f"{sport}|{ev}")
    if not g:
        return None
    mk = g.get(CLOSE_KEY[group])
    cands = [mk] if isinstance(mk, dict) else (mk or [])
    for c in cands:
        if not c or c.get("p") is None or list(c.get("outcomes") or []) != list(outs or []):
            continue
        if group != "ml" and (c.get("line") is None or line is None or float(c["line"]) != float(line)):
            continue
        return c["p"] if side == outs[0] else 1.0 - c["p"]
    return None


def sf_cid(sf, group, kf):
    """The market the shown size is on. New cards store `cid`; older ones are matched in the keyframe on market type, line, side and
    the stored price. None when no single market matches."""
    if sf.get("cid"):
        return sf["cid"]
    hits = []
    for cid, mk in (kf or {}).get("mk", {}).items():
        if mk.get("mt") != GROUP_MT[group] or sf["side"] not in (mk.get("outs") or []):
            continue
        if group != "ml" and mk.get("line") != sf.get("line"):
            continue
        oi = mk["outs"].index(sf["side"])
        px = (mk.get("px") or [None] * 2)[oi] if oi < len(mk.get("px") or []) else None
        if sf.get("price") is not None and px != sf["price"]:
            continue
        hits.append(cid)
    return hits[0] if len(hits) == 1 else None


def plays(card, kf):
    """Every gradeable play on one card: (group, variant, play, side, cid, line, outs, price, price_t, units)."""
    out = []
    for g, m in (card.get("markets") or {}).items():
        for variant in ("all", "fwd", "sfx"):                  # sfx: the benchmark's own exclusion list (a shadow, not the test)
            ls = (m.get("lock_shadow") or {}).get(variant) or {}
            if ls.get("side"):
                out.append({"group": g, "variant": variant, "play": "lock", "side": ls["side"], "cid": ls.get("cid"),
                            "line": ls.get("line"), "outs": ls.get("outs"), "price": ls.get("price"), "price_t": ls.get("price_t"),
                            "units": ls.get("units_clean_ladder")})
            sf = (m.get("sf") or {}).get(variant) or {}
            if sf.get("side") and (sf.get("units") or 0) > 0:
                cid = sf_cid(sf, g, kf)
                mk = (kf or {}).get("mk", {}).get(cid) or {}
                out.append({"group": g, "variant": variant, "play": "sf", "side": sf["side"], "cid": cid, "line": sf.get("line"),
                            "outs": mk.get("outs"), "price": sf.get("price"), "price_t": sf.get("price_t"), "units": sf["units"],
                            "rung": sf.get("rung")})
    return out


def grade(card, rel, kf, facts, closes, now):
    """Rows ready to write for one card, and the plays still waiting (with why)."""
    rows, waiting = [], []
    sport, ev, cut, gst = card["sport"], card["ev"], card["cut"], card["gst"]
    test = card.get("test") or {}
    for p in plays(card, kf):
        key = f"{rel}|{p['group']}|{p['variant']}|{p['play']}"
        base = {"key": key, "v": VERSION, "sport": sport, "ev": ev, "gst": gst, "cut": cut, "card": rel,
                "counts": bool(test.get("counts")), "why_not": test.get("why_not") or [], **p}
        if not p["cid"]:
            rows.append({**base, "res": None, "status": "no_market", "graded_at": now})
            continue
        f = facts.get(p["cid"])
        if not f or f.get("final") is None:
            waiting.append((key, "not resolved"))
            continue
        outs = f.get("outs") or p["outs"] or []
        if p["side"] not in outs:
            rows.append({**base, "res": None, "status": "side_not_in_market", "graded_at": now})
            continue
        oi = outs.index(p["side"])
        priced = p["price"] is not None and 0 < p["price"] < 1 and p["price_t"] is not None and p["price_t"] >= cut - STALE_PRICE
        res, flat = flat_profit(f["final"], oi, p["price"]) if priced else (flat_profit(f["final"], oi, 0.5)[0], None)
        rows.append({**base, "kind": "result", "outs": outs, "final": f["final"], "res": res,
                     "status": "graded" if priced else "unpriced", "flat": round(flat, 6) if flat is not None else None,
                     "units_pl": round(flat * p["units"], 6) if flat is not None and p.get("units") else None, "graded_at": now})
        if not priced or sport in NO_CLOSES:
            continue
        close = close_for(closes, sport, ev, p["group"], f.get("line", p["line"]), outs, p["side"])
        if close is None:
            waiting.append((key, "no close stored yet"))
            continue
        rows.append({"key": key + "|close", "kind": "close", "of": key, "v": VERSION, "sport": sport, "ev": ev, "gst": gst,
                     "close": close, "clv": round(close - p["price"], 6), "graded_at": now})
    return rows, waiting


def open_plays(todo, graded, now, days=7):
    """Locked plays still waiting for a result, for the Record page: Vault's shown size (variant all) on every frozen card, and the
    pre-registered lock on counted cards. Newest game first. Stored values only."""
    out = []
    for rel, c, kf in todo:
        for p in plays(c, kf):
            key = f"{rel}|{p['group']}|{p['variant']}|{p['play']}"
            if key in graded or c["gst"] < now - days * 86400 or p["variant"] != "all" or (p["play"] == "lock" and not (c.get("test") or {}).get("counts")):
                continue
            out.append({"sport": c["sport"], "ev": c["ev"], "gst": c["gst"], "group": p["group"], "play": p["play"], "side": p["side"],
                        "line": p["line"], "outs": p["outs"], "units": p["units"], "price": p["price"]})
    return sorted(out, key=lambda r: (-r["gst"], r["ev"], r["group"], r["play"]))


def boot_ci(xs, n=BOOT_N, seed=BOOT_SEED):
    """95% percentile bootstrap of the mean (prereg: 10,000 resamples, seed 20261111)."""
    if len(xs) < 2:
        return None
    rng = random.Random(seed)
    k = len(xs)
    means = sorted(sum(xs[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return [round(means[int(0.025 * n)], 4), round(means[int(0.975 * n) - 1], 4)]


def summarize(rows, boot=True, closes=None):
    """rows: result rows. closes: {result key: close row}."""
    closes = closes or {}
    priced = [r for r in rows if r.get("status") == "graded"]
    flat = [r["flat"] for r in priced]
    clv = [closes[r["key"]]["clv"] for r in priced if r["key"] in closes]
    out = {"n": len(priced), "w": sum(r["res"] == "win" for r in priced), "l": sum(r["res"] == "loss" for r in priced),
           "p": sum(r["res"] == "push" for r in priced),
           "flat_roi": round(sum(flat) / len(flat), 4) if flat else None, "flat_ci": boot_ci(flat) if boot else None,
           "units_staked": sum(r["units"] or 0 for r in priced),
           "units_pl": round(sum(r["units_pl"] or 0 for r in priced), 3),
           "clv_n": len(clv), "clv_mean": round(sum(clv) / len(clv), 4) if clv else None, "clv_ci": boot_ci(clv) if boot else None,
           "no_close": sum(1 for r in priced if r["key"] not in closes),
           "unpriced": sum(1 for r in rows if r.get("status") == "unpriced"),
           "unmatched": sum(1 for r in rows if r.get("status") in ("no_market", "side_not_in_market"))}
    return out


def record(rows, cards, now):
    """The report every read gives (prereg "What every read reports"), per sport. Report-only until the final read date."""
    out = {"generated": now, "v": VERSION, "prereg": "docs/sharp-card-prereg.md", "report_only": True,
           "note": "Interim. Only the final read on the registered date gives a verdict. Sharp money is context only.", "sports": {}}
    for sport in sorted({c["sport"] for c in cards} | {r["sport"] for r in rows}):
        cs = [c for c in cards if c["sport"] == sport]
        why = {}
        for c in cs:
            for w in (c.get("test") or {}).get("why_not") or []:
                why[w] = why.get(w, 0) + 1
        closes = {r["of"]: r for r in rows if r["sport"] == sport and r.get("kind") == "close"}
        rs = [r for r in rows if r["sport"] == sport and r.get("kind") != "close"]
        s = {"cards": {"frozen": len(cs), "counted": sum(1 for c in cs if (c.get("test") or {}).get("counts")),
                       "not_counted_by_reason": why},
             "lock": {}, "sf": {}}
        for play in ("lock", "sf"):
            for variant in ("all", "fwd", "sfx"):
                for g in ("ml", "spread", "total"):
                    sub = [r for r in rs if r["play"] == play and r["variant"] == variant and r["group"] == g]
                    if not sub:
                        continue
                    s[play].setdefault(variant, {})[g] = {
                        "counted": summarize([r for r in sub if r["counts"]], closes=closes),
                        "all_cards": summarize(sub, boot=False, closes=closes)}
        # prereg: if unpriced locks exceed 10% of a sport's counted moneyline locks (variant A), that sport gets no verdict
        ml = [r for r in rs if r["play"] == "lock" and r["variant"] == "all" and r["group"] == "ml" and r["counts"]
              and r.get("status") in ("graded", "unpriced")]
        share = sum(r["status"] == "unpriced" for r in ml) / len(ml) if ml else None
        s["data_quality"] = {"counted_ml_locks": len(ml), "unpriced_share": round(share, 4) if share is not None else None,
                             "fail": share is not None and share > UNPRICED_FAIL}
        out["sports"][sport] = s
    return out


def save_record(path, obj):
    """Write a record file only when something other than its `generated` time changed, so an idle run makes no commit."""
    old = jload(path, None)
    if isinstance(old, dict) and {k: v for k, v in old.items() if k != "generated"} == \
            json.loads(json.dumps({k: v for k, v in obj.items() if k != "generated"})):
        return False
    jsave(path, obj)
    return True


# ---------- io ----------

def load_rows(root):
    rows = {}
    for fn in sorted(glob.glob(os.path.join(root, "cards", "*", "*.jsonl"))):
        with open(fn) as f:
            for l in f:
                if l.strip():
                    r = json.loads(l)
                    rows[r["key"]] = r
    return rows


def append_rows(root, rows):
    by = {}
    for r in rows:
        month = time.strftime("%Y-%m", time.gmtime(r["gst"]))
        by.setdefault((r["sport"], month), []).append(r)
    for (sport, month), rs in by.items():
        p = os.path.join(root, "cards", sport, month + ".jsonl")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a") as f:
            for r in sorted(rs, key=lambda r: r["key"]):
                f.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cards", required=True, help="pm_cards folder (frozen cards)")
    ap.add_argument("--holders", required=True, help="pm_holders folder (T-15 keyframes)")
    ap.add_argument("--closes", default="data/pm_closes.json")
    ap.add_argument("--out", required=True, help="pm_record folder")
    ap.add_argument("--now", type=int)
    ap.add_argument("--no-fetch", action="store_true", help="use only the cached Gamma facts (tests, offline)")
    a = ap.parse_args()
    now = a.now or int(time.time())
    closes = jload(a.closes, {}) or {}
    have = load_rows(a.out)
    cache_p = os.path.join(a.out, "markets.json")
    facts = jload(cache_p, {})                       # only resolved markets are cached: a final result never changes

    cards, todo = [], []
    for path in sorted(glob.glob(os.path.join(a.cards, "*", "frozen", "*", "*.json"))):
        rel = os.path.relpath(path, a.cards)
        c = jload(path, None)
        if not c:
            continue
        cards.append(c)
        sport, _, date, fn = rel.split(os.sep)
        kf = jload(os.path.join(a.holders, sport, "frozen", date, fn), None)
        todo.append((rel, c, kf))

    need = set()
    for rel, c, kf in todo:
        for p in plays(c, kf):
            if p["cid"] and p["cid"] not in facts and f"{rel}|{p['group']}|{p['variant']}|{p['play']}" not in have:
                need.add(p["cid"])
    fetched = {}
    if need and not a.no_fetch:
        try:
            gamma_facts(Client(0.2, 2000), sorted(need), fetched)
        except (PMDataError, Budget) as e:
            print(f"::warning::Gamma read failed ({e}); unresolved plays wait for the next run")
    for cid, f in fetched.items():
        if f.get("final") is not None:
            facts[cid] = {k: f.get(k) for k in ("slug", "mt", "line", "outs", "gst", "closed_at", "final")}

    new, waiting = [], []
    for rel, c, kf in todo:
        rows, wait = grade(c, rel, kf, {**facts, **fetched}, closes, now)
        new += [r for r in rows if r["key"] not in have]
        waiting += wait
    append_rows(a.out, new)
    jsave(cache_p, facts)
    allrows = list(have.values()) + new
    rec = record(allrows, cards, now)
    rec["waiting"] = {"plays": len(waiting), "why": {w: sum(1 for _, x in waiting if x == w) for _, w in waiting}}
    rec["open"] = open_plays(todo, {r["key"] for r in allrows}, now)
    save_record(os.path.join(a.out, "cards_record.json"), rec)
    print(json.dumps({"new_rows": len(new), "waiting": rec["waiting"], "cards": len(cards)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
