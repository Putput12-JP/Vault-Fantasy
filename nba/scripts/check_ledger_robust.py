#!/usr/bin/env python3
"""
Checks for the 2026-10-21 recorder repair. No network, no price archive.

  python3 nba/scripts/check_ledger_robust.py

  1. book_name: 'Draft Kings' and 'DraftKings' are one book; an unknown book is left alone.
  2. One quote logged under both spellings is ONE bet (ledger.load_ledger merges the keys, bet_from takes the earliest entry), and a stored
     pair of bets or cube rows with both spellings collapses to one (dedupe_bets, canon_cube).
  3. A null field in the model state (the Oct 19 to 20 failure: a player's minutes record was null) no longer reaches the pricing code,
     and one player whose pricing raises is skipped and counted instead of stopping the poll.
"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ledger as LG, pricing as PX
from nba_common import book_name

ok = True


def check(name, cond):
    global ok
    ok &= bool(cond)
    print(('PASS ' if cond else 'FAIL ') + name)


# 1
check('book_name merges the two spellings', book_name('Draft Kings') == book_name('DraftKings') == 'DraftKings')
check('book_name leaves an unknown book alone', book_name('Some New Book') == 'Some New Book' and book_name(None) is None)

# 2
with tempfile.TemporaryDirectory() as root:
    d = os.path.join(root, 'snapshots', '2026-10-21')
    os.makedirs(d)
    base = '401909834|6478|pts|book|%s|Over|24.5'
    tip = 2000000000
    meta = {'game': '401909834', 'tip': tip, 'matchup': 'ATL @ ORL', 'pid': 6478, 'player': 'P', 'team': 'ATL', 'stat': 'pts', 'venue': 'book', 'side': 'Over', 'line': 24.5}
    v = lambda price, edge: [price, .5, edge, 'go', 20.0, 30.0, None, None, 'no-go', 'model']
    with open(os.path.join(d, 'meta.jsonl'), 'w') as f:
        for bk in ('Draft Kings', 'DraftKings'):
            f.write(json.dumps({'k': base % bk, 'src': 'ledger', **meta, 'book': bk}, separators=(',', ':')) + '\n')   # compact, as the recorder writes it
    with open(os.path.join(d, 'ledger.jsonl'), 'w') as f:
        for r in ({'t': 100, 'k': base % 'Draft Kings', 'v': v(-110, .04)},         # entry under the old spelling
                  {'t': 200, 'k': base % 'Draft Kings', 'v': None},                 # the spelling flips: old key gone ...
                  {'t': 200, 'k': base % 'DraftKings', 'v': v(-112, .05)},          # ... new key appears at the same instant
                  {'t': 300, 'k': base % 'DraftKings', 'v': v(-115, .02)}):
            f.write(json.dumps(r) + '\n')
    L = LG.load_ledger(root)
    check('one quote under two spellings is one ledger key', len(L) == 1)
    k, x = next(iter(L.items()))
    b = LG.bet_from(k, x['meta'], x['series'])
    check('it makes one bet, entered at the first poll, book DraftKings', b and b['t'] == 100 and b['price'] == -110 and b['book'] == 'DraftKings' and b['price_close'] == -115)
    one = dict(b, result='open')
    old = dict(b, book='Draft Kings', k=base % 'Draft Kings', t=150, result='open')
    dd = LG.dedupe_bets([old, one])
    check('stored duplicates collapse to the earlier entry', len(dd) == 1 and next(iter(dd.values()))['t'] == 100)
    row = lambda bk, n: ['2026-10-21', 'pts', 'book', bk, 'over', 'go', '3-5%', 'model', n, n, 0, 0, 0, 0, 0, 0, 0, 0.01 * n, n, 0.04 * n]
    cube = LG.canon_cube([row('Draft Kings', 2), row('DraftKings', 3)])
    check('cube rows with both spellings add up', len(cube) == 1 and cube[0][LG.CUBE_COLS.index('bets')] == 5 and cube[0][LG.CUBE_COLS.index('book')] == 'DraftKings')

# 3
ms = json.load(open(os.path.join(HERE, '..', 'data', 'model_state.json')))
pl = ms['live']['players']
ids = [k for k, v in pl.items() if v.get('ms')][:3]
pl[ids[0]]['ms'] = None                       # the failure: a player whose minutes record is null
pl[ids[1]] = None                             # a whole record null
pl[ids[2]]['r'] = None
pr = PX.Pricer(MS=ms)
check('null fields and null records never reach the pricing code', all(isinstance(v, dict) and all(x is not None for x in v.values()) for v in pr.state['players'].values()))
board = json.load(open(os.path.join(HERE, '..', 'data', 'prop_board.json')))['example']
clean = PX.price_board(board)
PX.ROW_ERRORS.clear()
bad = json.loads(json.dumps(board))
bad['props'][0]['books'] = [None]            # one prop whose rows are garbage
rows = PX.price_board(bad)
check('one unpriceable prop is skipped, counted, and the rest of the board is priced', len(PX.ROW_ERRORS) >= 1 and 0 < len(rows) < len(clean) + 1 and len(rows) >= len(clean) - 200)

print('ALL PASS' if ok else 'FAILED')
sys.exit(0 if ok else 1)
