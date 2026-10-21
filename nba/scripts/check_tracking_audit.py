#!/usr/bin/env python3
"""
Checks for the 2026-10-21 tracking audit (nba/docs/tracking-audit-2026-10-21.md). No network, no price archive.

  python3 nba/scripts/check_tracking_audit.py

  1. The watchdog reads the last days that HAVE polls, not the last folders: a future-dated folder (closing prices only) must not hide the day with the
     failing ledger. A lineups outage only counts when a game is still to tip today. A stale recorder and a 'bad' recorder flag are reported.
  2. A box score ESPN corrects after the final is re-read, rewritten, and a bet graded on the old numbers is graded again (win to loss), once an hour,
     only inside the window; a re-read that lost players is ignored; the cube follows the bet.
  3. A game long past its tip with no final box score (or with bets still open) is reported as stuck; a settled one is not.
  4. A record settle() cannot update is named in ledger.SETTLE_ERR instead of only the job log.
  5. The injury report's team ('AtlantaHawks') joins to its game, so Data Health's injuries column is not "none" for every game.
"""
import datetime as dt, json, os, sys, tempfile, time, types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'scripts'))
import ledger as LG, snapshot as SN
import watch_recorder_health as W

ok = True


def check(name, cond):
    global ok
    ok &= bool(cond)
    print(('PASS ' if cond else 'FAIL ') + name)


# 1. watchdog
names = ['2026-10-19', '2026-10-20', '2026-10-21', '2026-10-22', '2026-10-23']
with_polls = {'2026-10-19', '2026-10-20'}
check('days_with_polls skips folders that have no polls (future days hold closing prices only)',
      W.days_with_polls(names, lambda d: d in with_polls) == ['2026-10-19', '2026-10-20'])
check('days_with_polls takes the newest days that have polls', W.days_with_polls(names, lambda d: True) == ['2026-10-22', '2026-10-23'])
mk = lambda src, t, ok_=True, err='': {'t': t, 'src': src, 'ok': ok_, **({'err': err} if err else {})}
polls = [mk('ledger', 1000 + i * 300, False, "'NoneType' object is not subscriptable") for i in range(8)] + [mk('kalshi', 1000 + i * 300) for i in range(8)]
bad = W.failing(polls)
check('a ledger that failed its last 6 polls is reported with its first failure', len(bad) == 1 and bad[0][0] == 'ledger' and bad[0][1] == 1000)
check('a source with one ok poll in its last 6 is not reported', W.failing([mk('ledger', i, i != 7) for i in range(8)]) == [])
now = 1792549200      # 2026-10-21 02:20 UTC = 2026-10-20 22:20 ET
utc = lambda h: int(dt.datetime(2026, 10, 20, h, tzinfo=dt.timezone.utc).timestamp())
night = [mk('lineups', utc(7) + i * 300, False, 'HTTP 403') for i in range(10)]            # 07:00 UTC: before the file is posted
check('lineups 403s before 11:00 UTC are "not posted yet", not an outage', W.failing(night) == [])
day = [mk('lineups', utc(13) + i * 300, False, 'HTTP 403') for i in range(10)]             # 13:00 UTC
check('lineups 403s on a game day after 11:00 UTC are reported', [b[0] for b in W.failing(day)] == ['lineups'])
check('lineups are left out when no game is still to tip today (the day-ahead file never exists)', W.failing(day, lineups=False) == [])
st = {'games': [{'day': '2026-10-20', 'tip': now + 3600}, {'day': '2026-10-21', 'tip': now + 86400}]}
check('lineups expected while a game of today (ET) is still to tip', W.lineups_expected(st, now))
check('lineups not expected once the day\'s last game has tipped', not W.lineups_expected({'games': [{'day': '2026-10-21', 'tip': now + 86400}]}, now))
check('a healthy recorder reports nothing', W.report([], {'t': now - 600, 'flags': []}, now) == '')
check('a recorder silent for more than 3 hours is reported', 'newest poll is 4 hours old' in W.report([], {'t': now - 4 * 3600 - 60}, now))
rep = W.report([], {'t': now, 'flags': [{'level': 'bad', 'kind': 'unsettled', 'text': 'AAA @ BBB: tipped 9 hours ago'}, {'level': 'note', 'kind': 'held', 'text': 'x'}]}, now)
check('a bad recorder flag is reported, a note is not', 'AAA @ BBB' in rep and 'x' not in rep.replace('AAA', '').replace('BBB', '')[:0] + rep.split('Needs attention):')[1].split('Where to look')[0].replace('AAA @ BBB: tipped 9 hours ago', ''))

check('behind(): a recorder missing recorder files is named', 'abc1234' in W.behind({'code': 'abc1234def'}, ['nba/scripts/ledger.py', 'index.html']) and 'ledger.py' in W.behind({'code': 'abc1234def'}, ['nba/scripts/ledger.py']))
check('behind(): nothing to say when only other files changed', W.behind({'code': 'abc1234def'}, ['index.html']) == '' and W.behind({}, ['nba/scripts/x.py']) == '')

# 2. a corrected box score
TIP = 1_900_000_000
NOW0 = TIP + 4 * 3600


def summary(rebounds, minutes=240, players=2):
    ath = lambda i, nm, reb, mn: {'athlete': {'id': str(i), 'displayName': nm}, 'starter': True, 'stats': [str(mn), '10', '4-9', '1-3', '1-2', str(reb), '3', '1', '1', '0', '1', '4', '2', '+3']}
    keys = ['minutes', 'points', 'fieldGoalsMade-fieldGoalsAttempted', 'threePointFieldGoalsMade-threePointFieldGoalsAttempted', 'freeThrowsMade-freeThrowsAttempted',
            'rebounds', 'assists', 'turnovers', 'steals', 'blocks', 'offensiveRebounds', 'defensiveRebounds', 'fouls', 'plusMinus']
    teams = [{'team': {'abbreviation': 'AAA'}, 'statistics': [{'keys': keys, 'athletes': [ath(101, 'Ann Able', rebounds, minutes), ath(102, 'Bo Baker', 3, minutes)][:players]}]},
             {'team': {'abbreviation': 'BBB'}, 'statistics': [{'keys': keys, 'athletes': [ath(201, 'Cy Cole', 5, minutes), ath(202, 'Di Dale', 4, minutes)]}]}]
    return {'header': {'competitions': [{'status': {'type': {'completed': True}}, 'competitors': [{'team': {'abbreviation': 'AAA'}, 'score': '100'}, {'team': {'abbreviation': 'BBB'}, 'score': '90'}]}]},
            'boxscore': {'players': teams}}


served = {'d': summary(6)}
LG.curl_json = lambda url: served['d']
with tempfile.TemporaryDirectory() as root:
    gid = '401900001'
    d = os.path.join(root, 'snapshots', time.strftime('%Y-%m-%d', time.gmtime(TIP)))
    os.makedirs(d)
    k = f'{gid}|101|reb|book|DraftKings|Over|5.5'
    meta = {'game': gid, 'tip': TIP, 'matchup': 'AAA @ BBB', 'pid': 101, 'player': 'Ann Able', 'team': 'AAA', 'stat': 'reb', 'venue': 'book', 'book': 'DraftKings', 'side': 'Over', 'line': 5.5}
    dump = lambda r: json.dumps(r, separators=(',', ':')) + '\n'          # compact, as the recorder writes it (the loaders grep for "src":"ledger")
    with open(os.path.join(d, 'meta.jsonl'), 'w') as f:
        f.write(dump({'k': k, 'src': 'ledger', **meta}))
        f.write(dump({'k': f'{gid}|101', 'src': 'minutes', 'game': gid, 'tip': TIP, 'matchup': 'AAA @ BBB', 'pid': 101, 'player': 'Ann Able', 'team': 'AAA'}))
    with open(os.path.join(d, 'ledger.jsonl'), 'w') as f:
        f.write(dump({'t': TIP - 3600, 'k': k, 'v': [-110, .6, .06, 'no-go', 6.0, 30.0, None, None, 'no-go', 'model']}))
    with open(os.path.join(d, 'minutes.jsonl'), 'w') as f:
        f.write(dump({'t': TIP - 3600, 'k': f'{gid}|101', 'v': [30.0, 28.0, None, 0, None]}))
    n = LG.settle(root, NOW0)
    day = LG.tip_day(TIP)
    bs = json.load(open(os.path.join(root, 'bets', f'{day}.json')))
    check('first read: the bet is graded on 6 rebounds (a win)', len(bs) == 1 and bs[0]['result'] == 'win' and bs[0]['actual'] == 6.0)
    check('the first read has no correction', json.load(open(os.path.join(root, 'track.json')))['box_changes'] == [])
    served['d'] = summary(5)                                                  # ESPN corrects 6 to 5; the first poll after the final looks again
    LG.settle(root, NOW0 + 300)
    bs = json.load(open(os.path.join(root, 'bets', f'{day}.json')))
    tr = json.load(open(os.path.join(root, 'track.json')))
    check('the next poll finds the correction: the stored box is ESPN\'s number', json.load(open(os.path.join(root, 'results', f'{gid}.json')))['101']['rebounds'] == 5.0)
    check('the bet is graded again on 5 rebounds (a loss)', bs[0]['result'] == 'loss' and bs[0]['actual'] == 5.0 and bs[0]['pnl'] == -1.0)
    ic = {c: i for i, c in enumerate(tr['cube_cols'])}
    check('the cube follows the bet (0 wins, 1 loss)', sum(r[ic['w']] for r in tr['cube']) == 0 and sum(r[ic['l']] for r in tr['cube']) == 1)
    ch = [c for c in tr['box_changes'] if c['stat'] == 'rebounds']
    check('the old and the new number are kept', len(ch) == 1 and ch[0]['old'] == 6.0 and ch[0]['new'] == 5.0 and ch[0]['player'] == 'Ann Able')
    served['d'] = summary(4)
    LG.settle(root, NOW0 + 900)
    check('inside the hour the box is not read again', json.load(open(os.path.join(root, 'results', f'{gid}.json')))['101']['rebounds'] == 5.0)
    LG.settle(root, NOW0 + 300 + 3700)
    check('an hour later it is read again', json.load(open(os.path.join(root, 'results', f'{gid}.json')))['101']['rebounds'] == 4.0)
    served['d'] = summary(4, players=1)                                       # a re-read that lost a player is a partial box
    LG.settle(root, NOW0 + 300 + 3700 * 2)
    check('a re-read that lost players is ignored', json.load(open(os.path.join(root, 'results', f'{gid}.json')))['101']['rebounds'] == 4.0)
    served['d'] = summary(3)
    LG.settle(root, TIP + 80 * 3600)
    check('outside the correction window the box is left alone', json.load(open(os.path.join(root, 'results', f'{gid}.json')))['101']['rebounds'] == 4.0)

# 3. stuck games
with tempfile.TemporaryDirectory() as root:
    os.makedirs(os.path.join(root, 'results'))
    open(os.path.join(root, 'results', 'g_done.json'), 'w').write('{}')
    tips = {'g_stuck': (TIP, 'AAA @ BBB'), 'g_done': (TIP, 'CCC @ DDD'), 'g_early': (TIP + 6 * 3600, 'EEE @ FFF')}
    got = LG.stuck_games(root, TIP + 9 * 3600, tips, {})
    check('a game 9 hours past tip with no results file is stuck', [g['game'] for g in got] == ['g_stuck'])
    check('a game under 8 hours past tip is not', LG.stuck_games(root, TIP + 7 * 3600, tips, {}) == [])
    bets = {'x': [{'game': 'g_done', 'tip': TIP, 'matchup': 'CCC @ DDD', 'result': 'open'}]}
    check('a game with a results file but an open bet is stuck, and says how many', [(g['game'], g['open']) for g in LG.stuck_games(root, TIP + 9 * 3600, tips, bets)] == [('g_done', 1), ('g_stuck', 0)])

# 4. a record that cannot be updated is named
try:
    import sim_record
except ImportError:                       # numpy is not installed here: sim_record cannot be imported, so settle() would skip it anyway
    sim_record = None
    print('SKIP a Game Simulation record that raised is named in SETTLE_ERR (needs numpy)')
if sim_record:
    with tempfile.TemporaryDirectory() as root:
        real = sim_record.record
        sim_record.record = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'))
        try:
            LG.settle(root, NOW0)
        finally:
            sim_record.record = real
        check('a Game Simulation record that raised is named in SETTLE_ERR', 'game simulation record' in LG.SETTLE_ERR and 'boom' in LG.SETTLE_ERR['game simulation record'])
        LG.settle(root, NOW0)
        check('SETTLE_ERR is cleared on the next settle', not LG.SETTLE_ERR)

# 5. injuries coverage
slate = types.SimpleNamespace(
    games=[{'id': '1', 'day': '2026-10-21', 'tip': 2_000_000_000, 'away': 'POR', 'home': 'CHA', 'pre': True, 'season_type': 2, 'away_name': 'Portland Trail Blazers', 'home_name': 'Charlotte Hornets'},
           {'id': '2', 'day': '2026-10-21', 'tip': 2_000_000_000, 'away': 'NY', 'home': 'BKN', 'pre': True, 'season_type': 2, 'away_name': 'New York Knicks', 'home_name': 'Brooklyn Nets'}],
    nick={'POR': 'blazers', 'CHA': 'hornets', 'NY': 'knicks', 'BKN': 'nets'})
dayst = types.SimpleNamespace(last={'injuries': {'10/21/2026|PortlandTrailBlazers|A,B': ['Out', 'x'], '10/21/2026|CharlotteHornets|C,D': ['Out', 'x'], '10/21/2026|CharlotteHornets|E,F': ['Out', 'x'],
                                                 '10/21/2026|BrooklynNets|G,H': ['Out', 'x']}})
cov = {g['id']: g['cov'].get('injuries') for g in SN.coverage(slate, dayst, {})}
check('the report\'s team name joins to its game (POR @ CHA: 3 rows; NY @ BKN: 1, and Hornets do not count as Nets)', cov == {'1': [3, 0], '2': [1, 0]})

print('\nALL PASS' if ok else '\nFAILED')
sys.exit(0 if ok else 1)
