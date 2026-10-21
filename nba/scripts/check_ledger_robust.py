#!/usr/bin/env python3
"""
Checks for the 2026-10-21 recorder repair. No network, no price archive.

  python3 nba/scripts/check_ledger_robust.py

  1. book_name: 'Draft Kings' and 'DraftKings' are one book; an unknown book is left alone.
  2. One quote logged under both spellings is ONE bet (ledger.load_ledger merges the keys, bet_from takes the earliest entry), and a stored
     pair of bets or cube rows with both spellings collapses to one (dedupe_bets, canon_cube).
  3. A null field in the model state (the Oct 19 to 20 failure: a player's minutes record was null) no longer reaches the pricing code,
     and one player whose pricing raises is skipped and counted instead of stopping the poll.
  5. GO / WATCH candidates a hold kept out of the bets (source 'heldbets') settle apart (ledger.held_bets_record), entered at the first 3% price.
  4. Props a held team had are settled as their own group (prop_sim_record.record_held): W, L, push and did-not-play, the model's side, and nothing
     from a prop that was not held.
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

# 4  props the roster guard held settle as a group of their own
import prop_sim_record as PSR
with tempfile.TemporaryDirectory() as root:
    tip, gid = 2000000000, '401909999'
    d = os.path.join(root, 'snapshots', LG.tip_day(tip))
    os.makedirs(d)
    os.makedirs(os.path.join(root, 'results'))
    mk = lambda pid, stat, held: {'game': gid, 'tip': tip, 'matchup': 'AAA @ BBB', 'pid': pid, 'player': f'P{pid}', 'team': 'AAA', 'stat': stat, 'kind': 'psim', 'min': 30.0, **({'held': 'team'} if held else {})}
    rows = {f'{gid}|1|pts': [20.5, 22.0, .62, .62, .62, .55, 'books'],      # model over, price over: player scores 25, W
            f'{gid}|2|pts': [20.5, 18.0, .30, .30, .30, .45, 'books'],      # model under (70%), price under 55%: player scores 25, L
            f'{gid}|3|reb': [5.0, 5.0, .55, .55, .55, None, 'pickem'],      # flat line, lands on it: P
            f'{gid}|4|ast': [4.5, 5.0, .60, .60, .60, .50, 'books'],        # did not play: D
            f'{gid}|5|pts': [10.5, 11.0, .70, .70, .70, .50, 'books']}      # not held: never in the group
    with open(os.path.join(d, 'psim.jsonl'), 'w') as f:
        for k, v in rows.items():
            f.write(json.dumps({'t': tip - 600, 'k': k, 'v': v}, separators=(',', ':')) + '\n')
    with open(os.path.join(d, 'meta.jsonl'), 'w') as f:
        for k in rows:
            pid, stat = int(k.split('|')[1]), k.split('|')[2]
            f.write(json.dumps({'k': k, 'src': 'psim', **mk(pid, stat, pid != 5)}, separators=(',', ':')) + '\n')
    json.dump({'1': {'points': 25, 'minutes': 30}, '2': {'points': 25, 'minutes': 30}, '3': {'rebounds': 5, 'minutes': 30}, '5': {'points': 12, 'minutes': 30}, '4': None},
              open(os.path.join(root, 'results', gid + '.json'), 'w'))
    json.dump({'score': {'AAA': 100, 'BBB': 98}}, open(os.path.join(root, 'results', gid + '.meta.json'), 'w'))
    H = PSR.record_held(root, tip + 5 * 3600, None, 3, lambda g: True, LG)
    g = next(iter(H.values()))[0]
    sm = g['sum']
    check('held props settle: 1 W, 1 L, 1 push, 1 did not play, the unheld prop is not in the group', (sm['W'], sm['L'], sm['P'], sm['D'], sm['n']) == (1, 1, 1, 1, 4))
    check('the model side and the price chance for that side are recorded', g['rows'][0][4] in 'ou' and any(r[4] == 'u' and abs(r[5] - .70) < 1e-9 and abs(r[6] - .55) < 1e-9 for r in g['rows']))
    check('no profit number is stored: only sums for hit rate against what the price expected', sm['pn'] == 2 and abs(sm['pe_price'] - (.55 + .55)) < 1e-9 and sm['pw'] == 1)
    check('before the game is final nothing is settled', PSR.record_held(root, tip + 600, None, 3, lambda g: True, LG) == {})

# 5  GO / WATCH candidates a hold kept out of the bets settle as their own group, entered at the first 3% price
with tempfile.TemporaryDirectory() as root:
    tip, gid = 2000000000, '401909998'
    d = os.path.join(root, 'snapshots', LG.tip_day(tip))
    os.makedirs(d)
    os.makedirs(os.path.join(root, 'results'))
    k1, k2, k3 = (f'{gid}|{pid}|3pm|kalshi|Kalshi|NO|2.5' for pid in (1, 2, 3))
    base = {'game': gid, 'tip': tip, 'matchup': 'AAA @ BBB', 'team': 'AAA', 'stat': '3pm', 'venue': 'kalshi', 'book': 'Kalshi', 'side': 'NO', 'line': 2.5, 'hold': 'team'}
    v = lambda price, edge, gate: [price, .55, edge, gate, 1.0, 30.0, None, None, 'no-go', 'model']
    ser = {k1: [(tip - 7200, v(.40, .02, 'go')), (tip - 6000, v(.38, .05, 'go')), (tip - 600, v(.45, .01, 'go'))],      # reaches 3% at the second look: entry .38, player 1 makes 1: NO wins
           k2: [(tip - 3000, v(.40, .06, 'go'))],                                                                       # player 2 makes 4: NO loses
           k3: [(tip - 3000, v(.40, .06, 'no-go'))]}                                                                    # not a GO / WATCH gate: left out
    with open(os.path.join(d, 'heldbets.jsonl'), 'w') as f:
        for k, rows in ser.items():
            for t, val in rows:
                f.write(json.dumps({'t': t, 'k': k, 'v': val}, separators=(',', ':')) + '\n')
    with open(os.path.join(d, 'meta.jsonl'), 'w') as f:
        for k in ser:
            pid = int(k.split('|')[1])
            f.write(json.dumps({'k': k, 'src': 'heldbets', **base, 'pid': pid, 'player': f'P{pid}'}, separators=(',', ':')) + '\n')
    json.dump({'1': {'threePointFieldGoalsMade': 1, 'minutes': 30}, '2': {'threePointFieldGoalsMade': 4, 'minutes': 30}, '3': {'threePointFieldGoalsMade': 0, 'minutes': 30}},
              open(os.path.join(root, 'results', gid + '.json'), 'w'))
    json.dump({'score': {'AAA': 100, 'BBB': 98}}, open(os.path.join(root, 'results', gid + '.meta.json'), 'w'))
    H = LG.held_bets_record(root, tip + 5 * 3600, None, 3, lambda g: True)
    g = next(iter(H.values()))[0]
    sm = g['sum']
    check('held GO candidates settle: 1 W, 1 L, the no-go one is left out', (sm['W'], sm['L'], sm['n']) == (1, 1, 2))
    check('entry is the first price where the edge reached 3% (.38), with the Kalshi fee in the units', next(r for r in g['rows'] if r[0] == 'P1')[7] == .38 and abs(sm['units'] - (LG.profit('kalshi', .38, True) + -1.0)) < 1e-3)
    check('before the game is final nothing is settled', LG.held_bets_record(root, tip + 600, None, 3, lambda g: True) == {})

print('ALL PASS' if ok else 'FAILED')
sys.exit(0 if ok else 1)
