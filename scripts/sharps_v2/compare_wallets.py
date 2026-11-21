#!/usr/bin/env python3
"""Old and new numbers for the Sharps V2 account fields (docs/sharps-v2-accounts-spec.md, section 4 "old_new_numbers_to_report").

Reads two wallets.json files and prints, per visible number, the old value and the new one. Stdlib only. Context only: nothing here
is a bet signal, a size or an agree total.

  python3 -I scripts/sharps_v2/compare_wallets.py --old OLD.json --new NEW.json [--new-since SINCE.json] [--base SAME_INPUT_V1_BUILD.json]
                                                  [--json OUT.json]

  --old   the V1 file the spec measured (built 2026-11-21 10:21 AM CT)
  --new   a V2 build (scripts/build_side_cards.py --now 1795278075 on the same ledger commit, holders state and closes)
  --new-since  the since.json written beside the new wallets file (default: since.json in the same folder). The dated settled lists
          live there, not in the wallets file (docs/sharps-v2-accounts-spec.md section 2 K).
  --base  optional: a V1 build run on exactly the new build's inputs. With it the report also (a) checks that the new file, with every V2
          key stripped, equals the base file except the documented 30-day window moves of wallets that were open (audit bug 14), and
          (b) repeats the numbers that move with the inputs against it, so input drift is not read as a V2 effect.

Old numbers are derived from the old file's own fields (legs, px_t, name, rk, sc ...), the way the audit measured them. New numbers read
the V2 fields. Nothing is estimated.
"""
import argparse, datetime as dt, json, os, statistics as S, sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE)))
import build_side_cards as C  # noqa: E402

TZ = ZoneInfo("America/Chicago")
HEX = C.HEX_NAME
SPORTS = ("nba", "nfl", "cfb", "cbb")


def rows(doc):
    for sp, ws in (doc.get("sports") or {}).items():
        for w, e in ws.items():
            yield sp, w, e


def med(xs):
    xs = [x for x in xs if x is not None]
    return S.median(xs) if xs else None


def per_sport(doc, f):
    out = {}
    for sp, w, e in rows(doc):
        out.setdefault(sp, []).append(f(sp, w, e))
    return out


def count_by(doc, key):
    out = {}
    for sp, w, e in rows(doc):
        k = key(sp, w, e)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def hot(e):
    w, l = e.get("w_") or 0, e.get("l_") or 0
    n = w + l
    return n >= C.PROVEN_N and w / n >= C.PROVEN_WR and e.get("roi") is not None and e["roi"] > C.PROVEN_ROI


def ct_midnight(y, m, d):
    return int(dt.datetime(y, m, d, tzinfo=TZ).timestamp())


def wl_old(e, since):
    """The old Following tally: legs (20 cap, any size) settled at or after the follow."""
    r = [x[1] for x in e.get("legs") or [] if x[0] >= since]
    return [sum(1 for x in r if x == "win"), sum(1 for x in r if x == "loss")]


def items_of(since_doc, sp, w, retained=False):
    return ((since_doc or {}).get("retained" if retained else "sports") or {}).get(sp, {}).get(w) or []


def wl_new(items, since):
    """The V2 tally from one wallet's since.json items placed at or after the follow (first_fill) and settled at or after it. A null
    first_fill cannot be placed, so it is left out and counted. Returns (positions W-L, flat units, null first_fill, per-game W-L,
    games, positions W-L-P as a triple). The unit of `positions` is a bet: a spread and a moneyline on one game count twice; `games`
    counts each game once with the result of its biggest position (the old `legs` rule)."""
    kept, flat, nofirst = [], 0.0, 0
    for it in items:
        if it[0] < since:
            continue
        if it[1] is None:
            nofirst += 1
            continue
        if it[1] < since:
            continue
        kept.append(it)
        flat += it[3] if it[3] is not None and it[2] in (0, 1) else 0.0
    gw, gl, games = C.games_tally(kept)
    return [sum(1 for x in kept if x[2] == 1), sum(1 for x in kept if x[2] == 0)], round(flat, 2), nofirst, [gw, gl], games


def small(n):
    return "SMALL SAMPLE" if n < 30 else "n>=30"


def wallet_ref(sp, w, e):
    return "%s %s (%s)" % (sp.upper(), w[:10], e.get("name_disp") or e.get("name") or "unnamed")


def report(old, new, label, since_doc=None):
    R = []                                                # (section, item, old, new)

    def add(sec, item, o, n):
        R.append({"section": sec, "item": item, "old": o, "new": n})

    B_old, B = old["built"], new["built"]
    # tier tags
    add("Tier tags", "price-sharp / Beats", count_by(old, lambda s, w, e: (e.get("rk") or {}).get("tier") == "sharp").get(True, 0),
        count_by(new, lambda s, w, e: (e.get("v2") or {}).get("tier") == "beats").get(True, 0))
    add("Tier tags", "mid / Even", sum(1 for _, _, e in rows(old) if (e.get("rk") or {}).get("tier") == "mid"),
        sum(1 for _, _, e in rows(new) if (e.get("v2") or {}).get("tier") == "even"))
    add("Tier tags", "dull / Loses", sum(1 for _, _, e in rows(old) if (e.get("rk") or {}).get("tier") == "dull"),
        sum(1 for _, _, e in rows(new) if (e.get("v2") or {}).get("tier") == "loses"))
    add("Tier tags", "thin / Too few (new includes the no-tier rows)", sum(1 for _, _, e in rows(old) if (e.get("rk") or {}).get("tier") == "thin"),
        sum(1 for _, _, e in rows(new) if (e.get("v2") or {}).get("tier") == "few"))
    add("Tier tags", "no rk (old) of which now Too few", sum(1 for _, _, e in rows(old) if not e.get("rk")),
        sum(1 for _, _, e in rows(new) if not e.get("rk") and (e.get("v2") or {}).get("tier") == "few"))
    add("Tier tags", "rk.tier, n, mean, p identical old vs new (rows in both, tiered)", None,
        "%d of %d" % (sum(1 for sp, w, e in rows(new) if e.get("rk") and ((old["sports"].get(sp) or {}).get(w) or {}).get("rk")
                          and all(e["rk"][k] == old["sports"][sp][w]["rk"][k] for k in ("tier", "n", "mean", "p"))),
                      sum(1 for sp, w, e in rows(new) if e.get("rk") and ((old["sports"].get(sp) or {}).get(w) or {}).get("rk"))))
    # CLV line
    for sp in SPORTS:
        d = [abs(e["rk"]["post"] - e["rk"]["mean"]) * 100 for s, w, e in rows(new)
             if s == sp and e.get("rk") and e["rk"]["tier"] in ("sharp", "mid", "dull") and e["rk"].get("post") is not None]
        add("CLV line on a tiered row", "%s: rows, median and max abs(post - mean), cents" % sp.upper(), "rk.mean x100 (raw)",
            "%d rows, median %.3f, max %.3f" % (len(d), med(d), max(d)) if d else "no tiered rows")
    # scorecard
    sc_old = [(sp, e) for sp, w, e in rows(old) if e.get("sc")]
    add("Scorecard tag", "rows tagged (old: sc any sport; new: sc_sport this sport)", len(sc_old), sum(1 for _, _, e in rows(new) if e.get("sc_sport")))
    add("Scorecard tag", "old sc rows that are not on this sport's list (new sc_sport false)", sum(1 for sp, w, e in rows(new) if e.get("sc") and not e.get("sc_sport")), 0)
    for sp in SPORTS:
        add("Scorecard tag", "%s rows with sc_sport" % sp.upper(), sum(1 for s, e in sc_old if s == sp), sum(1 for s, w, e in rows(new) if s == sp and e.get("sc_sport")))
    # hot
    add("Hot", "rows labelled hot (old) / Past winner (new), rule n>=6, wr>=55%, ROI>3%", sum(1 for _, _, e in rows(old) if hot(e)), sum(1 for _, _, e in rows(new) if hot(e)))
    # inactive
    d30, d180 = 30 * 86400, 180 * 86400
    add("Inactive", "rows with no settled game in 30 days (old: newest leg; new: n30_games == 0)",
        sum(1 for _, _, e in rows(old) if not e.get("legs") or e["legs"][0][0] < B_old - d30), sum(1 for _, _, e in rows(new) if e.get("n30_games") == 0))
    add("Inactive", "rows with none in 180 days (new: last_settled)", sum(1 for _, _, e in rows(old) if not e.get("legs") or e["legs"][0][0] < B_old - d180),
        sum(1 for _, _, e in rows(new) if e.get("last_settled") is None or e["last_settled"] < B - d180))
    for sp in SPORTS:
        add("Inactive", "%s n30_games == 0" % sp.upper(), sum(1 for s, w, e in rows(old) if s == sp and (not e.get("legs") or e["legs"][0][0] < B_old - d30)),
            sum(1 for s, w, e in rows(new) if s == sp and e.get("n30_games") == 0))
    # usual
    us = [e["usual"] for _, _, e in rows(old) if e.get("usual")]
    um = [e["usual_med"] for _, _, e in rows(new) if e.get("usual_med")]
    add("Usual stake", "median across rows, range", "$%s, $%s to $%s" % (f"{med(us):,.0f}", f"{min(us):,.0f}", f"{max(us):,.0f}") if us else None,
        "$%s, $%s to $%s" % (f"{med(um):,.0f}", f"{min(um):,.0f}", f"{max(um):,.0f}") if um else None)
    add("Usual stake", "rows where usual_med and usual differ by over 2x (either way)", None,
        sum(1 for _, _, e in rows(new) if e.get("usual") and e.get("usual_med") and not 0.5 <= e["usual_med"] / e["usual"] <= 2))
    add("Usual stake", "rows with no usual_med (nothing at or above the floor)", sum(1 for _, _, e in rows(old) if not e.get("usual")),
        sum(1 for _, _, e in rows(new) if not e.get("usual_med")))
    # x usual
    sides_old, sides_new = {}, {}
    for sp, w, e in rows(old):
        for p in e.get("positions") or []:
            sides_old.setdefault((sp, w, p["ev"], p["gst"], p["g"], p["side"]), []).append(p.get("press"))
    multi_old = {k: v for k, v in sides_old.items() if len(v) > 1}
    for sp, w, e in rows(new):
        for p in e.get("positions") or []:
            sides_new[(sp, w, p["ev"], p["gst"], p["g"], p["side"])] = (p.get("side_rungs"), p.get("side_press"), p.get("side_usd"))
    multi_new = {k: v for k, v in sides_new.items() if v[0] and v[0] > 1}
    mx_rung = max((max(x for x in v if x is not None) for v in multi_old.values() if any(x is not None for x in v)), default=None)
    mx_sum = max((sum(x for x in v if x is not None) for v in multi_old.values()), default=None)
    mx_new = max((v[1] for v in multi_new.values() if v[1] is not None), default=None)
    add("x usual", "multi-rung sides", len(multi_old), len(multi_new))
    add("x usual", "max among multi-rung sides: old largest single rung press / old sum of rung presses; new side_press", "rung %s, sum %s" % (mx_rung, mx_sum and round(mx_sum, 2)), mx_new)
    add("x usual", "sides with side_press null (no usual_med)", None, sum(1 for v in sides_new.values() if v[1] is None))
    # price now
    def ages(doc):
        out = []
        for sp, w, e in rows(doc):
            for p in e.get("positions") or []:
                if "px_age_min" in p:
                    out.append(p["px_age_min"])
                elif p.get("px_t") is not None:
                    out.append(round((doc["built"] - p["px_t"]) / 60))
                else:
                    out.append(None)
        return out
    ao, an = ages(old), ages(new)
    known = lambda xs: [x for x in xs if x is not None]
    add("Price now", "positions, null price time", "%d, %d" % (len(ao), len(ao) - len(known(ao))), "%d, %d" % (len(an), len(an) - len(known(an))))
    add("Price now", "positions over 6 h / over 24 h", "%d / %d" % (sum(x > 360 for x in known(ao)), sum(x > 1440 for x in known(ao))),
        "%d / %d" % (sum(x > 360 for x in known(an)), sum(x > 1440 for x in known(an))))
    add("Price now", "positions whose price was logged after the build (px_t > built: a pinned --now older than the holders scan; px_age_min is clamped to 0)", None,
        sum(1 for _, _, e in rows(new) for p in e.get("positions") or [] if p.get("px_t") is not None and p["px_t"] > B))
    add("Price now", "px_age_min median, p90, max (minutes)", "not shown", "%s, %s, %s" % (med(known(an)), sorted(known(an))[int(.9 * (len(known(an)) - 1))] if known(an) else None, max(known(an), default=None)))
    # since you followed: the old tally is one leg per game (biggest position, 20 cap, any size); the new list is one item per POSITION above
    # the floor, so it is reported both ways: bets (positions) and games (the legs rule), never mixed
    follows = (("2026-11-11 12:00 AM CT", ct_midnight(2026, 11, 11)), ("built - 14 d", B - 14 * 86400))
    for name, ts in follows:
        for sp in SPORTS:
            ow = ol = bw = bl = gw = gl = games = diff = nfirst = 0
            flat = 0.0
            for s_, w, e in rows(new):
                if s_ != sp:
                    continue
                oe = (old["sports"].get(sp) or {}).get(w)
                if oe is None:
                    continue
                a = wl_old(oe, ts)
                b, f, nf, g, ng = wl_new(items_of(since_doc, sp, w), ts)
                ow, ol, bw, bl, gw, gl, games, flat, nfirst = ow + a[0], ol + a[1], bw + b[0], bl + b[1], gw + g[0], gl + g[1], games + ng, flat + f, nfirst + nf
                diff += a != g
            add("Since you followed (%s)" % name, "%s: W-L in GAMES, old (legs: one per game, 20 cap, any size) vs new (since.json: one per game, floor, first fill); wallets whose game tally changes" % sp.upper(),
                "%d-%d" % (ow, ol), "%d-%d, %d wallets differ, %d null first_fill" % (gw, gl, diff, nfirst))
            add("Since you followed (%s)" % name, "%s: the same new list counted in BETS (every position above the floor, so a game can count twice): W-L, flat units, games covered" % sp.upper(),
                "not shown", "%d-%d bets, flat %+.1fu, on %d games" % (bw, bl, flat, games))
    # retained
    ret = new.get("retained") or {}
    for sp in SPORTS:
        r = ret.get(sp) or {}
        tot = [0, 0, 0.0, 0, 0]
        for w, e in r.items():
            b, f, _, g, _ = wl_new(items_of(since_doc, sp, w, True), B - 14 * 86400)
            tot = [tot[0] + b[0], tot[1] + b[1], tot[2] + f, tot[3] + g[0], tot[4] + g[1]]
        add("Retained", "%s retained rows (old: 0, a leaver dropped from the tally); their W-L since built - 14 d, in bets and in games" % sp.upper(), 0,
            "%d rows, %d-%d bets, flat %+.1fu, %d-%d games" % (len(r), tot[0], tot[1], tot[2], tot[3], tot[4]))
    add("Retained", "retained wallets also under sports (must be 0)", None, sum(1 for sp, r in ret.items() for w in r if w in (new["sports"].get(sp) or {})))
    add("Retained", "oldest left_at age in days (must be <= 60)", None, round(max([(B - e["left_at"]) / 86400 for r in ret.values() for e in r.values()], default=0), 1))
    # names
    nm_old = sum(1 for _, _, e in rows(old) if not e.get("name") or HEX.match(e["name"]))
    add("Names", "rows that render as an address (old: name null or hex; new: name_src none)", nm_old, sum(1 for _, _, e in rows(new) if e.get("name_src") == "none"))
    add("Names", "of which old null / old hex", "%d / %d" % (sum(1 for _, _, e in rows(old) if not e.get("name")), sum(1 for _, _, e in rows(old) if e.get("name") and HEX.match(e["name"]))), None)
    add("Names", "rows whose name_disp came from universe / keyframe (own name or a stored earlier one)", None,
        "%d / %d" % (sum(1 for _, _, e in rows(new) if e.get("name_src") == "universe"), sum(1 for _, _, e in rows(new) if e.get("name_src") == "keyframe")))
    # forward
    fs_min = min((e["first_seen"] for _, _, e in rows(new) if e.get("first_seen")), default=None)
    age = "no first_seen" if fs_min is None else "the oldest forward record is %.1f days old" % ((B - fs_min) / 86400)
    for sp in SPORTS:
        f = [e["fwd"]["n"] for s, w, e in rows(new) if s == sp and e.get("fwd")]
        add("Forward record", "%s rows with fwd.n > 0, summed fwd.n (%s: small by default)" % (sp.upper(), age), "not shown", "%d rows, n %d" % (sum(1 for x in f if x), sum(f)))
    f = [e["fwd"]["n"] for _, _, e in rows(new) if e.get("fwd")]
    add("Forward record", "all sports: rows with fwd.n > 0, summed n", "not shown", "%d rows of %d, n %d" % (sum(1 for x in f if x), len(f), sum(f)))
    # flat roi
    for sp in SPORTS:
        for t in ("beats", "even", "loses", "few"):
            xs = [e for s, w, e in rows(new) if s == sp and (e.get("v2") or {}).get("tier") == t]
            if not xs:
                continue
            fr, rr = med([e.get("flat_roi") for e in xs]), med([e.get("roi") for e in xs])
            add("Flat ROI", "%s %s (%d rows): median dollar ROI vs median flat ROI" % (sp.upper(), t, len(xs)),
                "ROI %s" % (round(rr, 4) if rr is not None else None), "flat %s" % (round(fr, 4) if fr is not None else None))
    # 30-day block
    ch, tot, chw = 0, 0, []
    for sp, w, e in rows(new):
        o = ((old["sports"].get(sp) or {}).get(w) or {})
        if o.get("l30") and e.get("l30"):
            tot += 1
            if [o["l30"]["w"], o["l30"]["l"]] != [e["l30"]["w"], e["l30"]["l"]]:
                ch += 1
                chw.append("%s %s %d-%d -> %d-%d" % (sp, w[:8], o["l30"]["w"], o["l30"]["l"], e["l30"]["w"], e["l30"]["l"]))
    add("30-day block", "open wallets in both files, and those whose l30 W-L changed (old read at the first game's cut, new at now)", "%d wallets" % tot,
        "%d changed%s" % (ch, ": " + "; ".join(chw[:12]) if chw else ""))
    # size
    sz = lambda d: len(json.dumps(d, separators=(",", ":")))
    nv = sz(C.strip_v2(new))
    add("File size", "wallets.json bytes /1000 (budget: whole file <= %d, new fields <= %d)" % (C.WALLETS_MAX_KB, C.WALLETS_NEW_MAX_KB), round(sz(old) / 1000),
        "%d total, V2 fields %d" % (round(sz(new) / 1000), round((sz(new) - nv) / 1000)))
    add("File size", "within budget", None, "whole %s, new fields %s" % (sz(new) / 1000 <= C.WALLETS_MAX_KB, (sz(new) - nv) / 1000 <= C.WALLETS_NEW_MAX_KB))
    if since_doc is not None:
        add("File size", "since.json bytes /1000 (not budgeted: only a page that shows a follow reads it)", "not published", round(sz(since_doc) / 1000))
    return R


def backcompat(base, new):
    """The new file with every V2 key stripped, against a V1 build on the same inputs: what differs."""
    st = C.strip_v2(new)
    diff, ex = {}, {}
    for k in base:
        if k != "sports" and st.get(k) != base[k]:
            diff["top:" + k] = diff.get("top:" + k, 0) + 1
    for sp, ws in base["sports"].items():
        a, b = set(ws), set(st["sports"].get(sp) or {})
        if a != b:
            diff["wallet set " + sp] = len(a ^ b)
        for w in a & b:
            for k in set(ws[w]) | set(st["sports"][sp][w]):
                if ws[w].get(k) != st["sports"][sp][w].get(k):
                    diff[k] = diff.get(k, 0) + 1
                    ex.setdefault(k, (sp, w))
    return diff, ex


def input_drift(old, base):
    """The spec's old file against the V1 build run on the new build's inputs, wallet by wallet: which wallets differ and in which keys. The
    holders state used for a pinned build can hold scans after --now, so the two are not always byte-equal."""
    only, out = 0, []
    for sp in set(old["sports"]) | set(base["sports"]):
        a, b = old["sports"].get(sp) or {}, base["sports"].get(sp) or {}
        only += len(set(a) ^ set(b))
        for w in sorted(set(a) & set(b)):
            ks = [k for k in sorted(set(a[w]) | set(b[w])) if a[w].get(k) != b[w].get(k)]
            if ks:
                out.append("%s %s: %s" % (sp, w[:10], ", ".join(ks)))
    return {"only_in_one": only, "differs": out}


def close_monitoring(old, new, since_doc=None):
    """Every wallet or slice whose shown record improves under V2 (house rule), each with its own sample size; n under 30 is marked a small
    sample. Lists (sport, wallet, n, W-L) are returned as strings in `lists`; `summary` holds the one-line totals."""
    summary, lists = [], {}
    ow = lambda sp, w: (old["sports"].get(sp) or {}).get(w) or {}
    B = new["built"]

    # D1 forward records above the wallet's all-time dollar ROI
    fw = [(sp, w, e, e["fwd"]) for sp, w, e in rows(new) if e.get("fwd") and e["fwd"]["n"] > 0]
    better = [(sp, w, e, f) for sp, w, e, f in fw if f["roi"] is not None and ow(sp, w).get("roi") is not None and f["roi"] > ow(sp, w)["roi"]]
    summary.append("forward record above the wallet's all-time dollar ROI: %d of %d wallets with forward bets (summed n %d); %d of them under n 30; %s"
                   % (len(better), len(fw), sum(f["n"] for _, _, _, f in fw), sum(1 for *_, f in better if f["n"] < 30),
                      "the median forward n is %s" % med([f["n"] for *_, f in fw])))
    lists["forward ROI above all-time dollar ROI (fwd n, fwd W-L, fwd ROI vs all-time ROI)"] = [
        "%s: fwd n=%d %d-%d roi %+.1f%% vs all-time %+.1f%% (all-time n=%d) %s" % (wallet_ref(sp, w, e), f["n"], f["w"], f["l"], 100 * f["roi"],
                                                                                100 * ow(sp, w)["roi"], ow(sp, w).get("n") or 0, small(f["n"]))
        for sp, w, e, f in sorted(better, key=lambda x: (x[0], -x[3]["n"]))]

    # D2 flat ROI above dollar ROI
    flt = [(sp, w, e) for sp, w, e in rows(new) if e.get("flat_roi") is not None and e.get("roi") is not None and e["flat_roi"] > e["roi"]]
    summary.append("flat ROI above dollar ROI: %d rows (the flat figure weights every bet one unit; each row's sample is its own n, median n %s, %d under n 30)"
                   % (len(flt), med([e["n"] for _, _, e in flt]), sum(1 for _, _, e in flt if e["n"] < 30)))
    lists["flat ROI above dollar ROI (n, flat vs dollar)"] = ["%s: n=%d flat %+.1f%% vs dollar %+.1f%% %s" % (wallet_ref(sp, w, e), e["n"], 100 * e["flat_roi"], 100 * e["roi"], small(e["n"]))
                                                             for sp, w, e in sorted(flt, key=lambda x: (x[0], -x[2]["n"]))]

    # D3 names now shown
    nm = [(sp, w) for sp, w, e in rows(new) if e.get("name_src") in ("universe", "keyframe")
          and (not ow(sp, w).get("name") or HEX.match(ow(sp, w)["name"]))]
    summary.append("a name now shown where the old file rendered an address: %d rows (a label, not a record: counted, not listed)" % len(nm))

    # D4 since-you-followed tallies that improve, per synthetic follow, in games (the old legs unit), each with its own n
    for fname, ts in (("2026-11-11 12:00 AM CT", ct_midnight(2026, 11, 11)), ("built - 14 d", B - 14 * 86400)):
        imp, tot = [], 0
        for sp, w, e in rows(new):
            oe = ow(sp, w)
            if not oe:
                continue
            a = wl_old(oe, ts)
            b, f, nf, g, ng = wl_new(items_of(since_doc, sp, w), ts)
            tot += a != g
            if sum(g) and (not sum(a) or g[0] / sum(g) > a[0] / sum(a)):
                imp.append((sp, w, e, a, g, b, f))
        summary.append("since-you-followed tally (%s) that improves in games: %d wallets of %d whose game tally changes; %d of them under n 30 (new games W+L)"
                       % (fname, len(imp), tot, sum(1 for x in imp if sum(x[4]) < 30)))
        lists["since you followed, %s: old legs W-L -> new games W-L (bets W-L, flat units in the new list)" % fname] = [
            "%s: %d-%d -> %d-%d games (n=%d, %s); %d-%d bets, flat %+.2fu" % (wallet_ref(sp, w, e), a[0], a[1], g[0], g[1], sum(g), small(sum(g)), b[0], b[1], f)
            for sp, w, e, a, g, b, f in sorted(imp, key=lambda x: (x[0], -sum(x[4])))]

    # D5 retained rows: no old tally at all (the old tally dropped a leaver), so every retained record is new; each with its own n
    ret = []
    for sp, r in (new.get("retained") or {}).items():
        for w, e in r.items():
            b, f, nf, g, ng = wl_new(items_of(since_doc, sp, w, True), B - 14 * 86400)
            ret.append((sp, w, e, b, g, f))
    summary.append("retained rows (a leaver the old tally dropped): %d rows, %d with a since-built-minus-14-d tally; %d of those under n 30"
                   % (len(ret), sum(1 for x in ret if sum(x[4])), sum(1 for x in ret if sum(x[4]) and sum(x[4]) < 30)))
    lists["retained rows, built - 14 d (new games W-L, bets W-L, flat units)"] = [
        "%s: left %s, %d-%d games (n=%d, %s); %d-%d bets, flat %+.2fu; fwd n=%d" % (wallet_ref(sp, w, e), dt.datetime.fromtimestamp(e["left_at"], TZ).strftime("%b %d %I:%M %p CT"),
                                                                          g[0], g[1], sum(g), small(sum(g)), b[0], b[1], f, (e.get("fwd") or {}).get("n", 0))
        for sp, w, e, b, g, f in sorted(ret, key=lambda x: (x[0], -sum(x[4]))) if sum(g)]

    # D6 open wallets whose 30-day block improves under the read at now (audit bug 14)
    imp30, chg = [], 0
    for sp, w, e in rows(new):
        o = ow(sp, w)
        if not (o.get("l30") and e.get("l30")):
            continue
        ow_, nw_ = o["l30"], e["l30"]
        if [ow_["w"], ow_["l"]] != [nw_["w"], nw_["l"]] or o.get("l30_roi") != e.get("l30_roi"):
            chg += 1
            wr = lambda x: x["w"] / (x["w"] + x["l"]) if x["w"] + x["l"] else None
            if (e.get("l30_roi") or 0) > (o.get("l30_roi") or 0) or (wr(nw_) or 0) > (wr(ow_) or 0):
                imp30.append((sp, w, e, o))
    summary.append("open wallet 30-day block that improves under the read at now (audit bug 14): %d wallets of %d whose block changes; %d under n 30 (new W+L)"
                   % (len(imp30), chg, sum(1 for *_, e, o in [(x[0], x[1], x[2], x[3]) for x in imp30] if e["l30"]["w"] + e["l30"]["l"] < 30)))
    lists["open wallets, 30-day block old -> new (W-L, ROI)"] = [
        "%s: %d-%d roi %s -> %d-%d roi %s (n=%d, %s)" % (wallet_ref(sp, w, e), o["l30"]["w"], o["l30"]["l"], o.get("l30_roi"), e["l30"]["w"], e["l30"]["l"], e.get("l30_roi"),
                                                       e["l30"]["w"] + e["l30"]["l"], small(e["l30"]["w"] + e["l30"]["l"]))
        for sp, w, e, o in imp30]
    return {"summary": summary, "lists": lists}


def fmt(R):
    out, sec = [], None
    for r in R:
        if r["section"] != sec:
            sec = r["section"]
            out.append("\n## " + sec)
        out.append("- %s\n    old: %s\n    new: %s" % (r["item"], r["old"], r["new"]))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--new-since", help="the since.json beside the new wallets file (default: since.json in the same folder)")
    ap.add_argument("--base")
    ap.add_argument("--json")
    a = ap.parse_args()
    load = lambda p: json.load(open(p))
    old, new = load(a.old), load(a.new)
    sp_path = a.new_since or os.path.join(os.path.dirname(os.path.abspath(a.new)), C.SINCE_FILE)
    since_doc = load(sp_path) if os.path.exists(sp_path) else None
    if since_doc is None:
        print("note: no since.json found (%s): every since-you-followed number below is empty" % sp_path)
    res = {}
    print("# Sharps V2 account fields: old and new numbers")
    print("old built %s, new built %s, new v %s" % (old["built"], new["built"], new.get("v")))
    res["vs_old"] = report(old, new, "old", since_doc)
    print("\n# A. new vs the spec's old file (%s)" % os.path.basename(a.old))
    print(fmt(res["vs_old"]))
    if a.base:
        base = load(a.base)
        diff, ex = backcompat(base, new)
        res["backcompat"] = {"differs": diff, "example": {k: list(v) for k, v in ex.items()}}
        print("\n# B. back-compat: new file with V2 keys stripped vs a V1 build on the same inputs")
        print("keys that differ (count of wallets): %s" % (diff or "none"))
        print("expected: v (1 -> 2) and the 30-day block of wallets that were open (l30, l30_roi, d30, curve), audit bug 14")
        res["vs_base"] = report(base, new, "base", since_doc)
        print("\n# C. new vs the V1 build on the same inputs (%s): input drift removed" % os.path.basename(a.base))
        keep = ("Hot", "Usual stake", "x usual", "Price now", "Since you followed", "30-day block", "Inactive", "Tier tags", "Names")
        seen = {(r["section"], r["item"]): (r["old"], r["new"]) for r in res["vs_old"]}
        moved = [r for r in res["vs_base"] if r["section"].startswith(keep) and seen.get((r["section"], r["item"])) != (r["old"], r["new"])]
        print(fmt(moved) if moved else "no number differs from section A: the two V1 files agree on everything compared, so section A holds no input drift")
        drift = input_drift(old, base)
        res["input_drift"] = drift
        print("\nthe spec's old file vs the V1 base build, wallet by wallet (same inputs are not exact when the holders state holds scans after --now):")
        print("  wallets only in one file: %s; wallets whose keys differ: %d" % (drift["only_in_one"], len(drift["differs"])))
        for line in drift["differs"][:40]:
            print("  - " + line)
    print("\n# D. close monitoring (improves under V2, each with its own sample size; n under 30 is a small sample)")
    res["close_monitoring"] = close_monitoring(old, new, since_doc)
    for x in res["close_monitoring"]["summary"]:
        print("- " + x)
    for title, ls in res["close_monitoring"]["lists"].items():
        print("\n## %s: %d" % (title, len(ls)))
        for x in ls:
            print("  - " + x)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(res, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
