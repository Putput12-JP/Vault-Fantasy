#!/usr/bin/env python3
"""The per-tier record of every graded shown play, re-derived point in time (CLAUDE.md "fix the historical data and the records").

Reads the frozen cards and the graded rows on `pm-holders-data` with `git show` (nothing is checked out), derives each play's evidence tier
(scripts/sharps_v2/plays_v2.py, rule v2t-1) from the fields stored on its own card at its cut (stored `sf.signals`, else the tape rows at or
before the cut), and prints the record per sport and tier with sample sizes. Nothing is computed from the outcome: the tier of a play never
reads its result, price after the cut, or the close. The close (Pinnacle's no-vig fair at the last tape row at or before kickoff, the
`pinclose` rule of the spec) appears only as a separate CLV column.

Every number is in-sample: the tier rule was written after these results. It is a record, never a signal; sharp money is context only.

  python3 -I scripts/sharps_v2/tier_history.py [--repo .] [--ref origin/pm-holders-data] [--book-tape data/book_tape] [--json OUT.json]

Also prints the Nov 20 CBB re-add numbers (docs/side-card-record.md) and the record at the size the page showed at each cut.
Flat units: 1 unit at the stored price at the cut, a win pays 1 / price - 1. Voided plays are left out, as in the record.

Also prints the market-move flag record (scripts/sharps_v2/flag_record.py, docs/sharps-v2-flags-spec.md): the same plays by Flag A and Flag C state beside the
old record with no flags, derived point in time from the tape rows at or before each cut, with every improving slice flagged with its n.

Also prints the tier-scaled size SHADOW v2s-1 (plays_v2.SHADOW, user decision 2026-11-23) beside the flat record: each play's flat result times
its shadow size (Clear 1.5u, Mixed 1u, Thin 0.5u, Contested 0.5u, CFB 0, no tier no size). In-sample, an ordering by evidence and not fitted to
results; the flat 1u stays the size the page shows.
"""
import argparse, json, math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build_side_cards as BSC  # noqa: E402
import sf_signals as SIG  # noqa: E402
from sharps_v2 import plays_v2 as P2  # noqa: E402

SPORTS = ("nba", "nfl", "cbb", "cfb")
HEADLINE = ("nba", "nfl", "cbb")                # the sports the page's headline adds up today
TIERS = ("clear", "mixed", "thin", "contested", "none")
NOV18_AM = P2.FLAT_FROM                          # 2026-11-18 8:31 AM CT, #461
NOV20_MERGE = P2.CBB_FROM                        # 2026-11-20 4:47 PM CT, #534
NOV20_MIDNIGHT = 1795154400                      # 2026-11-20 12:00 AM CT
SMALL_N = 30                                     # a flagged record under this sample size carries a "small sample" tag (a tag, not a cutoff: every improving slice is flagged)
NO_TAPE_WHY = ("no_tape_rows_for_game", "no_pinnacle_before_cut")   # stored reasons for "no price check was possible at the cut"


class Git:
    """`git show` on a ref, through one persistent `git cat-file --batch` (684 cards would be 684 processes otherwise)."""

    def __init__(self, repo, ref):
        self.repo, self.ref = repo, ref
        self.p = subprocess.Popen(["git", "-C", repo, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    @property
    def sha(self):
        return subprocess.run(["git", "-C", self.repo, "rev-parse", self.ref], capture_output=True, check=True).stdout.decode().strip()

    def ls(self, prefix):
        out = subprocess.run(["git", "-C", self.repo, "ls-tree", "-r", "--name-only", self.ref, prefix + "/"], capture_output=True, check=True)
        return [l for l in out.stdout.decode().splitlines() if l]

    def show(self, path):
        self.p.stdin.write(f"{self.ref}:{path}\n".encode())
        self.p.stdin.flush()
        head = self.p.stdout.readline().decode().split()
        if len(head) < 3 or head[1] != "blob":
            return None
        data = self.p.stdout.read(int(head[2]))
        self.p.stdout.read(1)
        return data.decode()

    def close(self):
        self.p.stdin.close()
        self.p.wait()


class FsReader:
    """The same two calls on a checked-out pm-holders-data folder (the workflow's `pmdata`), for the per-run tier_record.json."""

    def __init__(self, root, sha=None):
        self.root, self.sha = root, sha

    def ls(self, prefix):
        out = []
        for dp, _, fns in os.walk(os.path.join(self.root, prefix)):
            out += [os.path.relpath(os.path.join(dp, fn), self.root) for fn in fns]
        return sorted(out)

    def show(self, path):
        try:
            with open(os.path.join(self.root, path)) as f:
                return f.read()
        except OSError:
            return None

    def close(self):
        pass


def graded_rows(git):
    rows = []
    for path in git.ls("pm_record/cards"):
        if path.endswith(".jsonl"):
            rows += [json.loads(l) for l in (git.show(path) or "").splitlines() if l.strip()]
    return rows


def pin_close_pts(c, g, sf, tape):
    """Pinnacle's no-vig close against the price at the cut, in points ((close fair - price) x 100), or None with a reason. The last
    Pinnacle tape row at or before game start, through the registered fair formula (sf_signals.ev_read). Outcome-free."""
    rows, how = tape.game(c["sport"], c.get("vault"), c["ev"], c["gst"])
    if not rows:
        return None, how
    sides = list((c["markets"][g].get("sides") or {}).keys())
    norm = BSC.side_norms(g, sides, BSC.team_names(c.get("vault"), c["ev"], c["sport"])).get(sf["side"])
    ev = SIG.ev_read(rows, g, norm, sf.get("line"), c["gst"], sf.get("price"))
    return ev["pts"], ev["why"]


def derive(c, g, side, tape):
    """-> dict(tier, why, facts, src, ev_pts) for the shown side on card `c`, market group `g`, from the card's stored fields (variant all).
    A card that already carries a v2 block (built after the V2 plays data shipped) answers from it (src frozen)."""
    m = c["markets"][g]
    v2 = m.get("v2")
    sf = (m.get("sf") or {}).get("all") or {}
    if v2 and v2.get("side") == side:
        return {"tier": v2.get("tier"), "why": None, "facts": v2.get("facts"), "src": "frozen", "ev_pts": (v2.get("vs_fair") or {}).get("pts")}
    sg = sf.get("signals") or BSC.card_signals(c, g, "all", tape)
    m2 = dict(m, sf=dict(m["sf"], all=dict(sf, signals=sg) if sg is not None else sf))
    f, _ = P2.facts(c["sport"], m2, side)
    ev = (sg or {}).get("ev")
    if sg is None or ev is None or (ev.get("pts") is None and ev.get("why") in NO_TAPE_WHY):
        f["a4"] = f["b2"] = None                         # no price check was possible at the cut (the tape did not exist yet): unknown, never "no price evidence"
    pts = (P2.ev_of(m2["sf"]["all"]) or {}).get("pts")
    proven_n = ((m["sides"][side]["all"].get("proven") or {}).get("wallets")) or 0
    tier, why = P2.tier_of(f, proven_n, pts)
    return {"tier": tier, "why": why, "facts": f, "src": "derived", "ev_pts": pts}


def play_rows(git, rows, tape, quotes=None):
    """One record per graded sf play of variant all: the result row joined to its tier. With `quotes` (a QuoteTape) each play also carries its
    market-move flag states `fa` (Flag A) and `fc` (Flag C) at its cut, from its card's stored v2.flags or re-derived from the tape (`fsrc`);
    without it they are None (not readable) and the record is exactly what it was."""
    from sharps_v2 import flag_record as FR
    out, cards = [], {}
    for r in rows:
        if r.get("kind") != "result" or r.get("play") != "sf" or r.get("variant") != "all" or r.get("status") != "graded":
            continue
        rel = r["card"]
        if rel not in cards:
            raw = git.show("pm_cards/" + rel)
            cards[rel] = json.loads(raw) if raw else None
        c = cards[rel]
        if not c or r["group"] not in (c.get("markets") or {}):
            continue
        d = derive(c, r["group"], r["side"], tape)
        sf = c["markets"][r["group"]]["sf"]["all"]
        clv, _ = pin_close_pts(c, r["group"], sf, tape)
        fl = FR.derive_flags(c, r["group"], r["side"], quotes) if quotes is not None else {"a": None, "c": None, "src": None}
        out.append({"fa": fl["a"], "fc": fl["c"], "fsrc": fl["src"], "key": r["key"], "sport": r["sport"], "group": r["group"], "cut": r["cut"], "gst": r["gst"], "graded_at": r.get("graded_at") or 0,
                    "res": r["res"], "flat": r["flat"], "tier": d["tier"] or "none", "why": d["why"], "src": d["src"], "facts": d["facts"],
                    "ladder": r.get("units") or 0, "clv": clv})
    return out


def stats(ps):
    n = len(ps)
    flat = [p["flat"] for p in ps]
    clv = [p["clv"] for p in ps if p["clv"] is not None]
    mean = sum(flat) / n if n else None
    sd = math.sqrt(sum((x - mean) ** 2 for x in flat) / (n - 1)) if n > 1 else None
    return {"n": n, "w": sum(p["res"] == "win" for p in ps), "l": sum(p["res"] == "loss" for p in ps), "p": sum(p["res"] == "push" for p in ps),
            "units": round(sum(flat), 2), "roi": round(100 * mean, 1) if n else None, "se": round(100 * sd / math.sqrt(n), 1) if sd is not None else None,
            "clv_n": len(clv), "clv_mean": round(sum(clv) / len(clv), 2) if clv else None}


def shadow_stats(ps):
    """The rule v2s-1 record of a play list: size per play from its sport and derived tier (plays_v2.shadow_units), result = the play's flat result
    (unit result at its own stored price) times the size. A play with no tier or no size (None) is left out and counted in `unsized`; a CFB play
    (size 0) is left out of n and stakes nothing. roi = units / staked (percent), None at 0 staked; se is the delta-method standard error of that
    ratio, sqrt(sum(size^2 (r - roi)^2)) / staked (percent), None under 2 sized plays."""
    sized = [(p, P2.shadow_units(p["sport"], p["tier"] if p["tier"] != "none" else None)) for p in ps]
    live = [(p, u) for p, u in sized if u]
    staked = sum(u for _, u in live)
    units = sum(p["flat"] * u for p, u in live)
    roi = units / staked if staked else None
    se = None
    if roi is not None and len(live) > 1:
        se = round(100 * math.sqrt(sum((u * (p["flat"] - roi)) ** 2 for p, u in live)) / staked, 1)
    return {"n": len(live), "n_all": len(ps), "unsized": sum(1 for _, u in sized if u is None), "staked": round(staked, 2), "units": round(units, 2),
            "roi": round(100 * roi, 1) if roi is not None else None, "se": se}


def fmt(s):
    if not s["n"]:
        return "none"
    wl = f"{s['w']}-{s['l']}" + (f"-{s['p']}" if s["p"] else "")
    clv = f"; Pin CLV {s['clv_mean']:+.2f} pts (n={s['clv_n']})" if s["clv_n"] else "; Pin CLV n=0"
    se = f", se {s['se']}" if s["se"] is not None else ""
    return f"{wl}, {s['units']:+.2f}u, {s['roi']:+.1f}%{se}, n={s['n']}{clv}"


def at_the_time(ps):
    """The record at the size the page actually showed at each play's cut (ladder before Nov 18, flat NBA and NFL after, CBB from Nov 20 4:47 PM)."""
    sized = [(p, P2.shown_units_at(p["sport"], p["cut"], p["ladder"])) for p in ps]
    sized = [(p, u) for p, u in sized if u]
    return {"n": len(sized), "w": sum(p["res"] == "win" for p, _ in sized), "l": sum(p["res"] == "loss" for p, _ in sized),
            "staked": round(sum(u for _, u in sized), 2), "units": round(sum(p["flat"] * u for p, u in sized), 2)}


def headline(ps, sports):
    return stats([p for p in ps if p["sport"] in sports])


LABEL = {"none": "not derivable"}


def slice_label(t):
    return LABEL.get(t, t)


def compute(ps):
    """Every number the report prints, as data: per sport and tier, the headline, the size shown at the time, the Nov 20 CBB re-add lines, and
    the flag list. Pure: a list of play records in, a dict out (tests feed it fixtures)."""
    out = {"plays": len(ps), "tiers": {}, "headline": {}, "cbb_readd": {}}
    slices = []                                           # (name, stats, sample-size field) of every slice a record can improve in
    for sport in SPORTS:
        sp = [p for p in ps if p["sport"] == sport]
        out["tiers"][sport] = {"all": stats(sp)}
        slices.append((f"{sport.upper()} all shown plays", out["tiers"][sport]["all"]))
        for t in TIERS:
            out["tiers"][sport][t] = stats([p for p in sp if p["tier"] == t])
            slices.append((f"{sport.upper()} {slice_label(t)}", out["tiers"][sport][t]))
    hp = [p for p in ps if p["sport"] in HEADLINE]
    out["headline"]["all"] = stats(hp)
    slices.append(("Headline (NBA+NFL+CBB)", out["headline"]["all"]))
    for t in TIERS:
        out["headline"][t] = stats([p for p in hp if p["tier"] == t])
        slices.append((f"Headline {slice_label(t)}", out["headline"][t]))
    out["headline"]["at_the_time"] = at_the_time(ps)
    out["shadow"] = shadow_compute(ps, out)
    out["at_the_time_by_sport"] = {sp: at_the_time([p for p in ps if p["sport"] == sp]) for sp in SPORTS}
    before = [p for p in ps if p["cut"] < NOV20_MIDNIGHT]
    graded = [p for p in ps if p["graded_at"] < NOV20_MERGE]
    cbb = [p for p in ps if p["sport"] == "cbb"]
    out["cbb_readd"] = {
        "before_nov20_old": headline(before, ("nba", "nfl")), "before_nov20_new": headline(before, HEADLINE),
        "graded_before_merge_old": headline(graded, ("nba", "nfl")), "graded_before_merge_new": headline(graded, HEADLINE),
        "today_old": headline(ps, ("nba", "nfl")), "today_new": headline(ps, HEADLINE),
        "cbb_before_nov18_831am": stats([p for p in cbb if p["cut"] < NOV18_AM]),
        "cbb_nov18_to_merge (hidden)": stats([p for p in cbb if NOV18_AM <= p["cut"] < NOV20_MERGE]),
        "cbb_nov18_to_nov19": stats([p for p in cbb if NOV18_AM <= p["cut"] < NOV20_MIDNIGHT]),
        "cbb_since_nov20_midnight": stats([p for p in cbb if p["cut"] >= NOV20_MIDNIGHT]),
        "cbb_after_merge": stats([p for p in cbb if p["cut"] >= NOV20_MERGE])}
    flagged = []                                          # EVERY slice whose record improves (units above 0, or a mean CLV above 0), with its n
    for name, st in slices:
        if st["n"] and st["units"] > 0:
            flagged.append({"slice": name, "metric": "flat ROI", "n": st["n"], "small_sample": st["n"] < SMALL_N, "stats": st})
        if st["clv_n"] and st["clv_mean"] > 0:
            flagged.append({"slice": name, "metric": "Pinnacle CLV", "n": st["clv_n"], "small_sample": st["clv_n"] < SMALL_N, "stats": st})
    out["flagged"] = flagged
    return out


def shadow_compute(ps, out):
    """The shadow beside the flat record, per sport and tier, for the headline (NBA+NFL+CBB), and the slices where the shadow ROI is above the flat
    ROI of the SAME plays (flagged with n). The shadow sizes only plays with a tier, so an "all" slice is compared with the flat record of its
    derivable plays (`flat_derived`), never with the flat record that also holds the not-derivable plays. A tier slice of one sport has one size
    for every play, so its ROI equals the flat ROI by construction; only the mixed-size slices (a sport's all, the headline's all) can differ,
    and every slice's units scale by its size."""
    sh = {"rule": P2.SHADOW_RULE, "sizes": dict(P2.SHADOW["sizes"]), "cfb": P2.SHADOW["cfb"], "tiers": {}, "flat_derived": {}, "headline": {}, "flagged": []}
    pairs = []                                            # (name, flat stats, shadow stats)
    for sport in SPORTS:
        sp = [p for p in ps if p["sport"] == sport]
        sh["tiers"][sport] = {"all": shadow_stats(sp)}
        sh["flat_derived"][sport] = stats([p for p in sp if p["tier"] != "none"])
        pairs.append((f"{sport.upper()} all derivable plays", sh["flat_derived"][sport], sh["tiers"][sport]["all"]))
        for t in TIERS:
            sh["tiers"][sport][t] = shadow_stats([p for p in sp if p["tier"] == t])
            pairs.append((f"{sport.upper()} {slice_label(t)}", out["tiers"][sport][t], sh["tiers"][sport][t]))
    hp = [p for p in ps if p["sport"] in HEADLINE]
    derived = [p for p in hp if p["tier"] != "none"]
    sh["headline"]["all"] = shadow_stats(hp)
    sh["headline"]["flat_on_derived"] = stats(derived)    # the flat 1u on the same plays the shadow sizes (the not-derivable plays are left out)
    pairs.append(("Headline (NBA+NFL+CBB) derivable plays", sh["headline"]["flat_on_derived"], sh["headline"]["all"]))
    for t in TIERS:
        sh["headline"][t] = shadow_stats([p for p in hp if p["tier"] == t])
        pairs.append((f"Headline {slice_label(t)}", out["headline"][t], sh["headline"][t]))
    for name, fl, sd in pairs:
        if fl["n"] and sd["roi"] is not None and fl["roi"] is not None and sd["roi"] > fl["roi"]:
            sh["flagged"].append({"slice": name, "n": sd["n"], "small_sample": sd["n"] < SMALL_N, "flat_roi": fl["roi"], "shadow_roi": sd["roi"],
                                  "flat_units": fl["units"], "shadow_units": sd["units"], "flat_n": fl["n"]})
    return sh


def fmt_flat(st):
    return f"{st['units']:+.2f}u, {st['roi']:+.1f}%, n={st['n']}" if st["n"] else "n=0"


def fmt_shadow(fl, sd):
    if not sd["n"] or sd["roi"] is None:
        return "no shadow stake" + (f" ({sd['unsized']} not derivable, no size)" if sd["unsized"] else "")
    se = f", se {sd['se']}" if sd["se"] is not None else ""
    return f"{sd['units']:+.2f}u on {sd['staked']:g}u staked, {sd['roi']:+.1f}%{se}, n={sd['n']}"


def print_shadow(out):
    sh = out["shadow"]
    sz = sh["sizes"]
    print(f"\nTIER-SCALED SIZE SHADOW {sh['rule']}: Clear {sz['clear']:g}u, Mixed {sz['mixed']:g}u, Thin {sz['thin']:g}u, Contested {sz['contested']:g}u, CFB {sh['cfb']:g}u, "
          "no tier no size.")
    print("An ordering by evidence, NOT fitted to results; in-sample; the flat 1u stays the size the page shows. shadow units = each play's flat result times its size.")
    for sport in SPORTS:
        print(f"\n{sport.upper()}{' (no size shown)' if sport == 'cfb' else ''}:")
        rows = [("all", out["tiers"][sport]["all"], {"n": 0, "roi": None, "unsized": 0})]
        if out["tiers"][sport]["all"]["n"]:
            rows.append(("all derivable", sh["flat_derived"][sport], sh["tiers"][sport]["all"]))
        rows += [(slice_label(t), out["tiers"][sport][t], sh["tiers"][sport][t]) for t in TIERS if out["tiers"][sport][t]["n"]]
        for name, fl, sd in rows:
            print(f"  {name:<13} flat {fmt_flat(fl)}" + (f"  |  shadow {fmt_shadow(fl, sd)}" if name != "all" else ""))
    hd = sh["headline"]
    fa, fd = out["headline"]["all"], hd["flat_on_derived"]
    print("\nOVERALL NBA+NFL+CBB")
    line = lambda st: f"{st['units']:+.2f}u on {st['n']}u staked, {st['roi']:+.1f}%, se {st['se']}, n={st['n']}" if st["n"] else "n=0"
    print(f"  flat 1u, every play:           {line(fa)}")
    print(f"  flat 1u, derivable plays only: {line(fd)}")
    s = hd["all"]
    if s["roi"] is not None:
        print(f"  shadow {sh['rule']}:                {s['units']:+.2f}u on {s['staked']:g}u staked, {s['roi']:+.1f}%, se {s['se']}, n={s['n']} sized ({s['unsized']} not derivable get no size)")
    print("  Caveat: one standard error of an ROI at n=300 is about 5.8 points, so no sport (n under 300 each) can read an edge, and the flat-versus-shadow gap is inside noise.")
    print(f"  Per-tier ROI inside one sport is the same under both rules (one size per tier); only the sport-all and headline-all lines can differ in ROI.")
    print(f"\nIMPROVES UNDER THE SHADOW (shadow ROI above flat ROI), for close monitoring, with n (tag under n={SMALL_N}); in-sample, none promoted, none a signal")
    if not sh["flagged"]:
        print("  none")
    for f in sh["flagged"]:
        tag = "  [small sample]" if f["small_sample"] else ""
        print(f"  {f['slice']} (n={f['n']}){tag}: flat {f['flat_roi']:+.1f}% ({f['flat_units']:+.2f}u, n={f['flat_n']}) -> shadow {f['shadow_roi']:+.1f}% ({f['shadow_units']:+.2f}u)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--ref", default="origin/pm-holders-data", help="the data ref to read; its commit hash is printed and written to --json")
    ap.add_argument("--book-tape", default="data/book_tape")
    ap.add_argument("--json", help="also write the numbers to this file")
    a = ap.parse_args(argv)
    git = Git(a.repo, a.ref)
    sha = git.sha
    tape = BSC.BookTape(a.book_tape)
    rows = graded_rows(git)
    ps = play_rows(git, rows, tape, BSC.QuoteTape(a.book_tape))
    voided = sum(1 for r in rows if r.get("play") == "sf" and r.get("variant") == "all" and r.get("status") == "void")
    git.close()
    out = compute(ps)
    out.update({"ref": a.ref, "data_ref_sha": sha, "rule": P2.RULE, "voided_left_out": voided})
    print(f"Data: {a.ref} at commit {sha}. Numbers are as of that commit.")
    print(f"Shown plays graded (sf, variant all): {len(ps)}; voided and left out: {voided}")
    print(f"Derived from each card's stored fields at its cut (rule {P2.RULE}); {sum(p['src'] == 'frozen' for p in ps)} read from a stored v2 block.")
    print("Where no price check was possible at the cut because the tape did not exist yet, the price facts are unknown and the play is 'not derivable'.")
    print("Every number below is IN-SAMPLE: the tier rule was written after these results.\n")
    print("PER-TIER RECORD (flat 1u at the stored price at the cut; Pin CLV = Pinnacle no-vig close minus the price, points)")
    for sport in SPORTS:
        print(f"\n{sport.upper()}{' (no size shown)' if sport == 'cfb' else ''}: all {fmt(out['tiers'][sport]['all'])}")
        for t in TIERS:
            if out["tiers"][sport][t]["n"]:
                print(f"  {slice_label(t):<13} {fmt(out['tiers'][sport][t])}")
    print(f"\nHEADLINE (NBA + NFL + CBB, the sports the page sizes today): {fmt(out['headline']['all'])}")
    for t in TIERS:
        if out["headline"][t]["n"]:
            print(f"  {slice_label(t):<13} {fmt(out['headline'][t])}")
    tt = out["headline"]["at_the_time"]
    print(f"\nAT THE SIZE THE PAGE SHOWED AT EACH CUT (all four sports): {tt['w']}-{tt['l']}, {tt['units']:+.2f}u on {tt['staked']:g}u staked, n={tt['n']}")
    for sport in SPORTS:
        x = out["at_the_time_by_sport"][sport]
        print(f"  {sport.upper()}: {x['units']:+.2f}u on {x['staked']:g}u staked, n={x['n']}")
    r = out["cbb_readd"]
    short = lambda st: fmt(st).split("; ")[0]
    print("\n2026-11-20 CBB RE-ADD (docs/side-card-record.md)")
    print(f"  plays cut before Nov 20 12:00 AM CT: old (NBA+NFL) {short(r['before_nov20_old'])}")
    print(f"                                       new (+CBB)    {short(r['before_nov20_new'])}")
    print(f"  rows graded before #534 merged (Nov 20 4:47 PM CT): old {short(r['graded_before_merge_old'])}")
    print(f"                                                       new {short(r['graded_before_merge_new'])}")
    print(f"  today: old (NBA+NFL) {short(r['today_old'])}")
    print(f"         new (+CBB)    {short(r['today_new'])}")
    for k in ("cbb_before_nov18_831am", "cbb_nov18_to_merge (hidden)", "cbb_nov18_to_nov19", "cbb_since_nov20_midnight", "cbb_after_merge"):
        print(f"  {k}: {short(r[k])}")
    print_shadow(out)
    from sharps_v2 import flag_record as FR
    out["flags"] = FR.compute(ps)
    FR.print_report(out["flags"])
    print(f"\nFLAGGED FOR CLOSE MONITORING: every record that improves, with its n (tag under n={SMALL_N}); in-sample, none promoted, none a signal")
    for f in out["flagged"]:
        tag = "  [small sample]" if f["small_sample"] else ""
        print(f"  {f['slice']} ({f['metric']}, n={f['n']}){tag}: {fmt(f['stats'])}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
