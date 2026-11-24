#!/usr/bin/env python3
"""Size gate for the wallets file (docs/sharps-v2-accounts-spec.md section 2): exits 3 when the file is over its budget, so a workflow can
stop before it publishes an over-budget file. Stdlib only.

  python3 -I scripts/sharps_v2/check_size.py live/wallets.json
  python3 -I scripts/sharps_v2/check_size.py --live live/live.json     # the V2 plays keys of live.json (docs/sharps-v2-plays-spec.md section 6)

The wallets gate is hard (exit 3). The live gate NEVER fails the publish: over its budget it rewrites live.json without the V2 keys (the V1 file),
prints a ::warning:: line and exits 0, so a V2 overrun can never freeze the V1 live cards.

The market-move flags (docs/sharps-v2-flags-spec.md 3.1) have a sub-budget inside the V2 budget: `v2.flags` + `v2.series` on every card together get
FLAGS_MAX_KB. Over it the gate drops, in order and stopping at the first that fits, every `v2.series` (the charts), then every
`v2.flags.line.by_book`, then every `v2.flags` (and `v2_plays.flags`); the V1 file and the rest of V2 still publish. Only then does the
V2-wide rule above apply to what is left.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build_side_cards as C  # noqa: E402


LIVE_V2_MAX_KB = 250            # budget (thousands of bytes) of everything the V2 plays data adds to live.json
FLAGS_MAX_KB = 90               # sub-budget of `v2.flags` + `v2.series` over every card (docs/sharps-v2-flags-spec.md 3.1)


def live_v2_kb(doc):
    """Compact-JSON size of live.json minus live.json without the V2 plays keys, in thousands of bytes."""
    from sharps_v2 import plays_v2 as P2
    dump = lambda d: len(json.dumps(d, separators=(",", ":")))
    return (dump(doc) - dump(P2.strip_plays_v2(doc))) / 1000


def _v2_blocks(doc):
    """Every card's v2 block of a live.json (a malformed card or market is skipped, never indexed blind)."""
    for c in (doc.get("games") if isinstance(doc.get("games"), list) else []):
        for m in ((c.get("markets") if isinstance(c, dict) else None) or {}).values():
            v = m.get("v2") if isinstance(m, dict) else None
            if isinstance(v, dict):
                yield v


def flags_kb(doc):
    """Compact-JSON size of `v2.flags` + `v2.series` over every card, in thousands of bytes."""
    n = sum(len(json.dumps({k: v[k] for k in ("flags", "series") if k in v}, separators=(",", ":"))) for v in _v2_blocks(doc))
    return n / 1000


def enforce_flags(doc, max_kb=FLAGS_MAX_KB):
    """-> (doc, dropped). Over `max_kb` the flags drop in the spec's order: all `series`, then all `flags.line.by_book`, then all `flags` (and
    `v2_plays.flags`). `dropped` names what was dropped, [] when the sub-budget held. Mutates and returns `doc`."""
    dropped = []
    if flags_kb(doc) <= max_kb:
        return doc, dropped
    for v in _v2_blocks(doc):
        v.pop("series", None)
    dropped.append("series")
    if flags_kb(doc) > max_kb:
        for v in _v2_blocks(doc):
            ln = (v.get("flags") or {}).get("line") if isinstance(v.get("flags"), dict) else None
            if isinstance(ln, dict):
                ln.pop("by_book", None)
        dropped.append("by_book")
    if flags_kb(doc) > max_kb:
        for v in _v2_blocks(doc):
            v.pop("flags", None)
            v.pop("flags_error", None)
        if isinstance(doc.get("v2_plays"), dict):
            doc["v2_plays"].pop("flags", None)
        dropped.append("flags")
    return doc, dropped


def enforce_live(path, max_kb=LIVE_V2_MAX_KB, flags_max_kb=FLAGS_MAX_KB, report=None):
    """-> (kb, stripped). First the flags sub-budget (see the module docstring; the file is rewritten without what it drops, `report` gets one
    line per drop). Then, when the V2 plays keys are over `max_kb`, the file is rewritten without all of them (the V1 file, compact JSON as the
    builder writes it); otherwise it is left alone. `kb` is the V2 size after the flags step."""
    from sharps_v2 import plays_v2 as P2
    with open(path) as f:
        doc = json.load(f)
    fkb = flags_kb(doc)
    doc, dropped = enforce_flags(doc, flags_max_kb)
    if dropped and report is not None:
        report.append("v2 flags and charts are %.0f KB, over the %d KB sub-budget: dropped %s" % (fkb, flags_max_kb, ", ".join(dropped)))
    kb = live_v2_kb(doc)
    if kb <= max_kb:
        if dropped:
            with open(path + ".tmp", "w") as f:
                json.dump(doc, f, separators=(",", ":"))
            os.replace(path + ".tmp", path)
        return kb, False
    with open(path + ".tmp", "w") as f:
        json.dump(P2.strip_plays_v2(doc), f, separators=(",", ":"))
    os.replace(path + ".tmp", path)
    return kb, True


def main(argv):
    if len(argv) == 3 and argv[1] == "--live":
        report = []
        kb, stripped = enforce_live(argv[2], report=report)
        print("live.json V2 plays keys %.0f KB (budget %d)" % (kb, LIVE_V2_MAX_KB))
        for line in report:
            print("::warning::" + line)
        if stripped:
            print("::warning::live.json V2 plays keys are %.0f KB, over the %d KB budget: publishing the V1 file without them" % (kb, LIVE_V2_MAX_KB))
        return 0
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        doc = json.load(f)
    kb, new_kb = C.wallets_sizes(doc)
    print("wallets file %.0f KB (budget %d), V2 fields %.0f KB (budget %d)" % (kb, C.WALLETS_MAX_KB, new_kb, C.WALLETS_NEW_MAX_KB))
    over = C.over_budget(kb, new_kb)
    if over:
        print("ERROR: over the size budget: " + over, file=sys.stderr)
        return C.BUDGET_EXIT
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
