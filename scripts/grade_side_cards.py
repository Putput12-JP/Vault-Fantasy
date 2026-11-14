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
import argparse, datetime as dt, glob, gzip, json, os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pm_ledger import Client, Budget, gamma_facts, jload, jsave  # noqa: E402
from pm_data_api import PMDataError  # noqa: E402
import sf_publish as PUB  # noqa: E402
import sf_solo as SOLO  # noqa: E402
import build_side_cards as BSC  # noqa: E402                # card_signals, BookTape (the signals are re-derived for every card)

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
            if variant in ("all", "fwd"):                       # pub: derived from the stored sf + ags, so old cards grade too
                pb = PUB.pub_play(m, variant) or {}
                if pb.get("side") and (pb.get("units") or 0) > 0:
                    cid = sf_cid(sf, g, kf)
                    mk = (kf or {}).get("mk", {}).get(cid) or {}
                    out.append({"group": g, "variant": variant, "play": "pub", "side": pb["side"], "cid": cid, "line": pb.get("line"),
                                "outs": mk.get("outs"), "price": pb.get("price"), "price_t": pb.get("price_t"), "units": pb["units"],
                                "rung": pb.get("rung")})
                so = SOLO.solo_play(m, variant) or {}            # solo: the shown size capped at 1u on one wallet or a small lead bet
                if so.get("side") and (so.get("units") or 0) > 0:
                    cid = sf_cid(sf, g, kf)
                    mk = (kf or {}).get("mk", {}).get(cid) or {}
                    out.append({"group": g, "variant": variant, "play": "solo", "side": so["side"], "cid": cid, "line": so.get("line"),
                                "outs": mk.get("outs"), "price": so.get("price"), "price_t": so.get("price_t"), "units": so["units"],
                                "rung": so.get("rung"), "capped": so.get("capped"), "was_units": so.get("was"), "cap_reason": so.get("reason")})
    return out


def price_confirmations(holders, sport, cids, lo, hi):
    """{cid: [times]}: holders-scan cycles that read the market's price successfully (cycle `price_err` null) and then its holders,
    between lo and hi. Before 2026-11-13 the scan logged a price only when it changed, so a steady price kept the time it last moved;
    each of these cycles re-read it and found it unchanged, so the stored price was the market's price at that cycle's start."""
    out, cids = {}, set(cids)
    if not cids or not holders:
        return out
    days = {dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d") for t in range(int(lo) - 86400, int(hi) + 86400, 86400)}
    for day in sorted(days):
        for fn in sorted(glob.glob(os.path.join(holders, sport, "log", day, "*.jsonl*"))):
            try:
                op = gzip.open if fn.endswith(".gz") else open
                with op(fn, "rt") as f:
                    rows = [json.loads(l) for l in f if l.strip()]
            except (OSError, ValueError):
                continue
            cyc = next((r for r in rows if r.get("k") == "cyc"), None)
            if not cyc or cyc.get("price_err") or not cyc.get("ok", True) or cyc.get("t") is None:
                continue
            for r in rows:
                if r.get("k") == "r" and r.get("c") in cids and r.get("rt") is not None and lo <= cyc["t"] <= hi:
                    out.setdefault(r["c"], []).append((cyc["t"], r["rt"]))
    return out


def confirmed_price_t(p, cut, conf):
    """The latest cycle that re-read this market's price before the cut, if it is within STALE_PRICE of the cut and not before the
    stored price's own time. None otherwise."""
    ts = [t for t, rt in (conf or {}).get(p.get("cid"), []) if rt <= cut and t >= cut - STALE_PRICE and t >= (p.get("price_t") or 0)]
    return max(ts) if ts else None


def grade(card, rel, kf, facts, closes, now, conf=None):
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
        if not priced and p["price"] is not None and 0 < p["price"] < 1:
            ct_ = confirmed_price_t(p, cut, conf)                 # the price was re-read unchanged near the cut: it is the price at the cut
            if ct_ is not None:
                p = dict(p, price_t=ct_, price_t_src="confirmed by a later unchanged read")
                base = dict(base, price_t=ct_, price_t_src=p["price_t_src"])
                priced = True
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
            if p["play"] in ("pub", "solo"):                        # shadows of the shown size are graded, never listed as open plays
                continue
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


SIGNAL_DEFS = {"limit_rising": "Pinnacle's max stake up $500 or 1.45x between the first tape row and the lock (scripts/sf_signals.py)",
               "ev_on": "Polymarket price at the lock at least 0.3 points under Pinnacle's no-vig fair price for the side"}


def derive_signals(todo, tape):
    """{(card path, group, variant): signals} for the shown side of every frozen card, read from the tape at each card's lock. Derived, not
    stored in the append-only card files, so cards from before the signals existed are covered too."""
    out = {}
    for rel, c, kf in todo:
        for g in (c.get("markets") or {}):
            for variant in ("all", "fwd"):
                s = BSC.card_signals(c, g, variant, tape)
                if s is not None:
                    out[(rel, g, variant)] = s
    return out


def signal_slices(rs, sig, closes):
    """The record of one play type split by each signal: yes, no, and unknown (the read was not possible). Variant `all`, every market."""
    def val(r, name):
        s = sig.get((r.get("card"), r["group"], r["variant"])) or {}
        if name == "limit_rising":
            return (s.get("limit") or {}).get("rising")
        return (s.get("ev") or {}).get("on")
    out = {}
    for name in ("limit_rising", "ev_on"):
        out[name] = {k: summarize([r for r in rs if val(r, name) is v], boot=False, closes=closes)
                     for k, v in (("yes", True), ("no", False), ("unknown", None))}
    return out


def record(rows, cards, now, sig=None):
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
             "lock": {}, "sf": {}, "pub": {}, "solo": {}}
        for play in ("lock", "sf", "pub", "solo"):
            for variant in ("all", "fwd", "sfx"):
                for g in ("ml", "spread", "total"):
                    sub = [r for r in rs if r["play"] == play and r["variant"] == variant and r["group"] == g]
                    if not sub:
                        continue
                    s[play].setdefault(variant, {})[g] = {
                        "counted": summarize([r for r in sub if r["counts"]], closes=closes),
                        "all_cards": summarize(sub, boot=False, closes=closes)}
        if sig is not None:
            s["signals"] = {"defs": SIGNAL_DEFS, "context_only": True}
            for play in ("sf", "pub"):
                s["signals"][play] = signal_slices([r for r in rs if r["play"] == play and r["variant"] == "all"], sig, closes)
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


def rewrite_rows(root, fixed):
    """Replace the given rows in place in their month files (same position), keeping every other line byte-for-byte."""
    for fn in sorted(glob.glob(os.path.join(root, "cards", "*", "*.jsonl"))):
        with open(fn) as f:
            lines = f.readlines()
        out, hit = [], False
        for l in lines:
            k = json.loads(l)["key"] if l.strip() else None
            if k in fixed:
                out.append(json.dumps(fixed[k], separators=(",", ":"), sort_keys=True) + "\n")
                hit = True
            else:
                out.append(l)
        if hit:
            with open(fn + ".tmp", "w") as f:
                f.writelines(out)
            os.replace(fn + ".tmp", fn)


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
    ap.add_argument("--book-tape", default="data/book_tape", help="Vault's book tape (Pinnacle rows), for the limit and price signals")
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

    # price confirmations for plays whose stored price time is older than the 30-minute rule (see price_confirmations)
    conf = {}
    by_sport = {}
    for rel, c, kf in todo:
        for p in plays(c, kf):
            if p["cid"] and p["price"] is not None and (p["price_t"] is None or p["price_t"] < c["cut"] - STALE_PRICE):
                b = by_sport.setdefault(c["sport"], [set(), c["cut"], c["cut"]])
                b[0].add(p["cid"]); b[1] = min(b[1], c["cut"]); b[2] = max(b[2], c["cut"])
    for sp, (cids, lo, hi) in by_sport.items():
        conf.update(price_confirmations(a.holders, sp, cids, lo - STALE_PRICE, hi))

    new, waiting, fixed = [], [], {}
    for rel, c, kf in todo:
        rows, wait = grade(c, rel, kf, {**facts, **fetched}, closes, now, conf)
        for r in rows:
            old = have.get(r["key"])
            if old is None:
                new.append(r)
            elif old.get("status") == "unpriced" and r.get("status") == "graded":
                # a correction, not a new grade: the row was written unpriced from a recording gap (prices logged only on change)
                fixed[r["key"]] = dict(r, corrected={"at": now, "was": "unpriced", "why": "price re-read unchanged at "
                                                     + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(r["price_t"])) + ", before the lock"})
        waiting += wait
    if fixed:
        rewrite_rows(a.out, fixed)
        have.update(fixed)
        print(f"corrected {len(fixed)} rows that were unpriced only because a steady price was not re-logged")
    append_rows(a.out, new)
    jsave(cache_p, facts)
    allrows = list(have.values()) + new
    rec = record(allrows, cards, now, derive_signals(todo, BSC.BookTape(a.book_tape)))
    rec["waiting"] = {"plays": len(waiting), "why": {w: sum(1 for _, x in waiting if x == w) for _, w in waiting}}
    rec["open"] = open_plays(todo, {r["key"] for r in allrows}, now)
    save_record(os.path.join(a.out, "cards_record.json"), rec)
    print(json.dumps({"new_rows": len(new), "waiting": rec["waiting"], "cards": len(cards)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
