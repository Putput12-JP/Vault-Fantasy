#!/usr/bin/env python3
"""Move grade search: the graded plays by the frozen system's letter and by mg-1, report only (docs/sharps-v2-movegrade-search.md section 9).
Never used to choose anything. Point in time: each play's features from the tape rows at or before its own cut.

  python3 -I scripts/research/mgs_graded.py --ref 3e17a148dc2f --select scratch/mgs_select.json --system S3 --out scratch/mgs_graded.json
"""
import argparse, bisect, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import build_side_cards as BSC  # noqa: E402
from sharps_v2 import tier_history as TH  # noqa: E402
import mgs_population as POP  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--select", required=True)
    ap.add_argument("--system", default="S3")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    assert a.system == "S3", "only the frozen system's score is implemented here"
    marks = json.load(open(a.select))["marks"]["S3"]
    repo = os.path.dirname(os.path.dirname(HERE))
    git = TH.Git(repo, a.ref)
    tape, quotes = BSC.BookTape("data/book_tape"), BSC.QuoteTape("data/book_tape")
    ps = TH.play_rows(git, TH.graded_rows(git), tape, None)
    byk = {p["key"]: p for p in ps}
    out, cards = [], {}
    for r in TH.graded_rows(git):
        if r.get("key") not in byk:
            continue
        p = byk[r["key"]]
        rel = r["card"]
        if rel not in cards:
            raw = git.show("pm_cards/" + rel)
            cards[rel] = json.loads(raw) if raw else None
        c = cards[rel]
        g = r["group"]
        L3 = L1 = after = None
        why = None
        try:
            rows, _ = quotes.game(c["sport"], c.get("vault"), c["ev"], c["gst"])
            sides = list((c["markets"][g].get("sides") or {}).keys())
            norm = BSC.side_norms(g, sides, BSC.team_names(c.get("vault"), c["ev"], c["sport"])).get(r["side"])
            if norm is None:
                why = "side_unmapped"
            elif not rows:
                why = "no_tape"
            else:
                rows = [dict(x) for x in rows if x.get("book") in POP.BOOKS]
                fe = POP.features(rows, g, norm, c["cut"], c["sport"])
                L1 = POP.mg1(fe, g, c["sport"])
                m = marks.get("%s|%s" % (c["sport"], g))
                s = fe["c"]
                if s is not None and m:
                    s = round(s, 4)
                    L3 = ("A" if s > 0 and s >= m[2] else "B" if s > 0 and s >= m[1] else "C" if s > 0 and s >= m[0]
                          else "against" if s < 0 and s <= -m[1] else "D")
                after, _ = POP.after_move(rows, g, norm, c["cut"], c["gst"])
        except Exception as e:
            why = type(e).__name__
        out.append({"key": r["key"], "sport": p["sport"], "g": g, "res": p["res"], "flat": p["flat"], "clv": p["clv"], "S3": L3, "mg1": L1,
                    "after": after, "why": why})
    git.close()
    json.dump(out, open(a.out, "w"))
    print("graded plays", len(out), file=sys.stderr)


if __name__ == "__main__":
    main()
