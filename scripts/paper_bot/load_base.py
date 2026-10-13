"""Build the ledger a paper-bot run starts from. Paper only, never touches an order.

    python3 -m scripts.paper_bot.load_base --published FILE --recovered-dir DIR --out FILE

FILE for --published is the paper-data ledger; a missing or empty file counts as none. Every *.json in
--recovered-dir is a ledger an earlier run wrote before its publish. They are merged with the published
ledger by trade id (see merge_ledger), so rows that only one failed-publish artifact holds survive.
A recovered file that is invalid JSON or not a ledger is skipped with a ::warning line on stdout, so one bad
artifact cannot block the run. Exit 0 on success (nothing is written when there is no ledger at all), 2 only
when the published ledger is unreadable or not a ledger.
"""
import argparse
import glob
import os
import sys

from .ledger import build_base_ledger, held_tickers, save
from .merge_ledger import NotALedger, read


def main(argv=None):
    ap = argparse.ArgumentParser(prog='load_base')
    ap.add_argument('--published', default=None)
    ap.add_argument('--recovered-dir', default=None)
    ap.add_argument('--out', required=True)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    paths = sorted(glob.glob(os.path.join(args.recovered_dir, '*.json'))) if args.recovered_dir else []
    try:
        published = read(args.published)
    except (NotALedger, ValueError) as e:
        print(f'load_base: {e}', file=sys.stderr)
        return 2
    recovered = []
    for p in paths:
        try:
            r = read(p)
        except (NotALedger, ValueError) as e:
            reason = ' '.join(str(e).split())
            print(f'::warning title=Paper bot ledger::Skipped recovered ledger {p}: {reason}')
            continue
        if r is not None:
            recovered.append(r)
    try:
        base = build_base_ledger(published, recovered)
    except NotALedger as e:
        print(f'load_base: {e}', file=sys.stderr)
        return 2
    if base is None:
        print('no published or recovered ledger; the bot will start a new book')
        return 0
    print(f"ledger sources: published={'yes' if published else 'no'} recovered={len(recovered)} "
          f"trades={len(base['trades'])} held={len(held_tickers(base))}")
    if recovered:
        print('::notice title=Paper bot ledger::Merged ledgers earlier runs failed to publish, so those tickers stay held.')
    save(args.out, base)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
