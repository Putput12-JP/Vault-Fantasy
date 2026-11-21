#!/usr/bin/env python3
"""Size gate for the wallets file (docs/sharps-v2-accounts-spec.md section 2): exits 3 when the file is over its budget, so a workflow can
stop before it publishes an over-budget file. Stdlib only.

  python3 -I scripts/sharps_v2/check_size.py live/wallets.json
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build_side_cards as C  # noqa: E402


def main(argv):
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
