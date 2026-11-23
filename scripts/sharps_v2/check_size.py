#!/usr/bin/env python3
"""Size gate for the wallets file (docs/sharps-v2-accounts-spec.md section 2): exits 3 when the file is over its budget, so a workflow can
stop before it publishes an over-budget file. Stdlib only.

  python3 -I scripts/sharps_v2/check_size.py live/wallets.json
  python3 -I scripts/sharps_v2/check_size.py --live live/live.json     # the V2 plays keys of live.json (docs/sharps-v2-plays-spec.md section 6)

The wallets gate is hard (exit 3). The live gate NEVER fails the publish: over its budget it rewrites live.json without the V2 keys (the V1 file),
prints a ::warning:: line and exits 0, so a V2 overrun can never freeze the V1 live cards.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build_side_cards as C  # noqa: E402


LIVE_V2_MAX_KB = 250            # budget (thousands of bytes) of everything the V2 plays data adds to live.json


def live_v2_kb(doc):
    """Compact-JSON size of live.json minus live.json without the V2 plays keys, in thousands of bytes."""
    from sharps_v2 import plays_v2 as P2
    dump = lambda d: len(json.dumps(d, separators=(",", ":")))
    return (dump(doc) - dump(P2.strip_plays_v2(doc))) / 1000


def enforce_live(path, max_kb=LIVE_V2_MAX_KB):
    """-> (kb, stripped). When the V2 plays keys are over `max_kb` the file is rewritten without them (the V1 file, compact JSON as the builder
    writes it); otherwise it is left alone."""
    from sharps_v2 import plays_v2 as P2
    with open(path) as f:
        doc = json.load(f)
    kb = live_v2_kb(doc)
    if kb <= max_kb:
        return kb, False
    with open(path + ".tmp", "w") as f:
        json.dump(P2.strip_plays_v2(doc), f, separators=(",", ":"))
    os.replace(path + ".tmp", path)
    return kb, True


def main(argv):
    if len(argv) == 3 and argv[1] == "--live":
        kb, stripped = enforce_live(argv[2])
        print("live.json V2 plays keys %.0f KB (budget %d)" % (kb, LIVE_V2_MAX_KB))
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
