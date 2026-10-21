#!/usr/bin/env python3
"""
Replay recorder polls from the prices it stored, to fill rows the live recorder failed to write.

Why it exists: from 2026-10-19 19:01Z to 2026-10-20 21:44Z (184 polls) every shadow-ledger poll died on one player with a null field, after the
ledger rows were written and before the Minutes Lab, Game Simulation and Props Simulation rows were. BOS @ DET, the first game of the season,
tipped inside that window and has no minutes, simulation or props simulation rows at all, so the Track Record could not score it.

What a replay is, exactly:
  * The board is rebuilt for each stored poll from that day's snapshots/<day>/*.jsonl (kalshi, espn, pinnacle, action, polymarket, injuries, lineups,
    prizepicks, underdog, sleeper, novig) with every row cut off at the next poll's start, then passed to the SAME functions the recorder calls:
    ledger.log, ledger.minutes_log, sim_record.log, prop_sim_record.log. Nothing is estimated or filled in by hand; a stored price is the only input.
  * The model files are the ones on hand (nba/data/*.json at the commit that runs this), NOT the files the recorder had at that moment. The last
    daily refresh of model_state.json and player_projections.json before the replayed polls was 2026-10-20 16:44Z; polls before it saw an older state.
    The rows a game is scored on are its LAST pre-tip rows, which come from polls after that refresh.
  * What the recorder kept only in memory is not stored, so it is not replayed: Kalshi book sizes and Polymarket depth (priced rows do not read them),
    the Novig order books (Novig paper trading is not replayed).
  * Every row written carries meta "replay": 1, and snapshots/<day>/replay.json says what was replayed and with which commit. Settling copies the flag
    onto a bet (ledger.bet_from) and onto a Game Simulation entry (sim_record.record).
  * Only the named games, only sources where that game has no rows in that day folder yet (running it twice writes nothing the second time),
    and the rows are merged into each source file in time order, so the file reads as if the recorder had written them.

  python3 nba/scripts/replay_polls.py --dir=<nba-data checkout> --games=401909088            # dry run: prints what it would write
  python3 nba/scripts/replay_polls.py --dir=<nba-data checkout> --games=401909088 --write
  --skip-held-bets  leave out the 'heldbets' source (the GO / WATCH candidates a hold kept out of the bets, see ledger.held_bets_record), which needs
                   ledger.log on every poll (4 s each).
  --check-ledger   also re-run ledger.log on every poll (4 s each) and report the candidates, edges, holds and rows. The ledger stage is never
                   written by a replay: the recorder DID log it during the failure (the stage ran before the one that raised), so its
                   zero rows for a held game are the real record.
"""
import datetime as dt, json, os, subprocess, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import snapshot as S, prop_board as PB, pricing as PX, ledger as LG, sim_record, prop_sim_record

INPUTS = ('kalshi', 'espn', 'pinnacle', 'action', 'polymarket', 'injuries', 'lineups', 'prizepicks', 'underdog', 'sleeper', 'novig')
STAGES = ('ledger', 'minutes', 'sim', 'psim', 'heldbets')          # novig_paper needs the Novig order books, which are not stored
_SCHEDULE = {}


def schedule(day):
    """ESPN's games for one ET date (cached): id, day, tip, away, home, names, season type."""
    if day not in _SCHEDULE:
        gs = S.espn_day(dt.date.fromisoformat(day), {})
        for g in gs:
            g.pop('state')
        _SCHEDULE[day] = gs
    return _SCHEDULE[day]


class State:
    """Day.last / first / when / hist / log / t0 as the recorder had them, advanced poll by poll."""

    def __init__(self, folder):
        self.rows, self.meta = [], defaultdict(dict)
        for f in sorted(os.listdir(folder)):
            if f.endswith('.jsonl') and f[:-6] in INPUTS:
                src = f[:-6]
                self.rows += [(r['t'], src, r) for r in map(json.loads, open(os.path.join(folder, f)))]
        self.rows.sort(key=lambda x: x[0])
        for r in map(json.loads, open(os.path.join(folder, 'meta.jsonl'))):
            if r['src'] in INPUTS:
                self.meta[r['src']][r['k']] = r
        self.last, self.first, self.when = defaultdict(dict), defaultdict(dict), defaultdict(dict)
        self.hist, self.log, self.t0 = defaultdict(lambda: defaultdict(list)), defaultdict(list), {}
        self.i = 0

    def advance(self, t):
        while self.i < len(self.rows) and self.rows[self.i][0] < t:
            tt, src, r = self.rows[self.i]
            self.i += 1
            last = self.last[src]
            self.when[src][r['k']] = tt
            self.hist[src][r['k']].append(tt)
            self.t0.setdefault(src, tt)
            if src in S.WIRE_SRC:
                self.log[src].append((tt, r['k'], last.get(r['k']), r['v']))
            if r['v'] is None:
                last.pop(r['k'], None)
            else:
                last[r['k']] = r['v']
                self.first[src].setdefault(r['k'], r['v'])


def src_ok(polls, t):
    """snapshot.src_ok, from the stored poll log: when each source last answered before t."""
    out = {}
    for r in polls:
        if r['t'] >= t:
            break
        o = out.setdefault(r['src'], {})
        o['try'] = r['t']
        if r.get('ok'):
            o['ok'] = r['t']
    return out


class Fake:
    """The slice of snapshot.Day that ledger.log reads."""

    def __init__(self):
        self.last = {}


def replay_day(folder, gids, check_ledger=False, held_bets=True, say=lambda *a: print(*a, flush=True)):
    """-> ({source: [{'t','k','v'}]}, {source: {key: meta}}, report) for the games `gids` over one day folder's stored polls."""
    day = os.path.basename(folder)
    polls = [json.loads(l) for l in open(os.path.join(folder, 'polls.jsonl'))]
    clock = [p for p in polls if p['src'] == 'ledger']                # one entry per poll, stamped with its start time (`now`)
    games = []
    for off in (-1, 0, 1, 2, 3):
        games += schedule((dt.date.fromisoformat(day) + dt.timedelta(days=off)).isoformat())
    tips = {str(g['id']): g['tip'] for g in games}
    proj = json.load(open(os.path.join(HERE, '..', 'data', 'player_projections.json')))
    st = State(folder)
    last = {s: {} for s in STAGES}
    out, metas = defaultdict(list), defaultdict(dict)
    rep = {gid: {'polls': 0, 'cands': 0, 'edge': 0, 'held': 0, 'edge_free': 0, 'logged': 0} for gid in gids}
    done = {gid: False for gid in gids}
    for i, p in enumerate(clock):
        now = p['t']
        nxt = clock[i + 1]['t'] if i + 1 < len(clock) else now + 300
        st.advance(nxt)                                                # the poll's own source rows are stamped just after `now`
        live = [g for g in gids if not done[g] and tips[g] <= now + LG.TRACK_H * 3600 and (now < tips[g] or any(k.split('|')[0] == g for s in STAGES for k in last[s]))]
        if not live:
            continue
        gs = [dict(g, pre=now < g['tip'] <= now + S.AHEAD_H * 3600) for g in games]
        board = PB.build([g for g in gs if g['pre']], st.last, st.meta, st.first, proj, now, when=st.when, wire=(st.hist, st.log, st.t0))
        board['src_ok'] = src_ok(polls, now)
        fake = Fake()
        fake.last['ledger'] = last['ledger']
        fake.last['heldbets'] = last['heldbets']
        pr = {}
        pr['ledger'] = ({}, {})
        pr['heldbets'] = ({}, {})
        if check_ledger or held_bets:                                  # slow (it prices the whole board, 4s a poll)
            rows_l = LG.log(fake, board, now)
            pr['heldbets'] = LG.HELD_OUT if held_bets else ({}, {})    # the GO / WATCH candidates a hold kept out of the bets (ledger.held_bets_record)
            if check_ledger:                                           # the live recorder did log the ledger stage itself, so it is never written
                pr['ledger'] = rows_l
            for gid, c in LG.LOG_STATS.items():
                if gid in rep:
                    rep[gid]['polls'] += 1
                    rep[gid]['cands'] += c['cands']
                    rep[gid]['edge'] += c['edge']
                    rep[gid]['held'] += c['held']
                    rep[gid]['logged'] += c['logged']
        pr['minutes'] = LG.minutes_log(board, now)
        pr['sim'] = sim_record.log(board, now)
        pr['psim'] = prop_sim_record.log(board, now)
        for src in STAGES:
            rows, meta = pr[src]
            rows = {k: v for k, v in rows.items() if k.split('|')[0] in live}
            for k, v in rows.items():
                if k not in last[src] or last[src][k] != v:
                    out[src].append({'t': now, 'k': k, 'v': v})
                    metas[src][k] = dict(meta[k], replay=1)
            out[src] += [{'t': now, 'k': k, 'v': None} for k in last[src] if k not in rows and k.split('|')[0] in live]
            last[src] = rows
        for g in live:
            if now >= tips[g]:
                done[g] = True                                         # one poll past tip writes the 'gone' rows, as the recorder does
        say(f"  {day} {dt.datetime.fromtimestamp(now, dt.timezone.utc):%H:%M}Z  " + '  '.join(f'{s} {len(last[s])}' for s in STAGES))
    return out, metas, rep


def has_rows(folder, src, gid):
    path = os.path.join(folder, f'{src}.jsonl')
    return os.path.exists(path) and any(f'"k":"{gid}|' in l for l in open(path))


def merge_jsonl(path, new):
    """Insert rows into a change-only source file in time order (existing rows first at the same instant)."""
    old = open(path).read().splitlines() if os.path.exists(path) else []
    keyed = [(json.loads(l)['t'], 0, n, l) for n, l in enumerate(old)]
    keyed += [(r['t'], 1, n, json.dumps(r, separators=(',', ':'))) for n, r in enumerate(new)]
    keyed.sort(key=lambda x: x[:3])
    with open(path, 'w') as f:
        f.write('\n'.join(x[3] for x in keyed) + '\n')


def commit_id():
    try:
        return subprocess.run(['git', '-C', HERE, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except OSError:
        return None


def main(argv):
    args = {a.split('=')[0].lstrip('-'): (a.split('=', 1)[1] if '=' in a else True) for a in argv}
    root, gids, write = os.path.abspath(args['dir']), str(args['games']).split(','), bool(args.get('write'))
    snap = os.path.join(root, 'snapshots')
    tips = {}
    folders = sorted(f for f in os.listdir(snap) if f[:2] == '20')
    # which day folders hold polls inside each game's ledger window: find the game's tip from the stored meta
    folders = [f for f in folders if os.path.exists(os.path.join(snap, f, 'meta.jsonl')) and os.path.exists(os.path.join(snap, f, 'polls.jsonl'))]
    for f in folders:
        for l in open(os.path.join(snap, f, 'meta.jsonl')):
            if '"src":"espn"' in l and l.startswith('{"k":"') and '|game"' in l:
                r = json.loads(l)
                if r['game'] in gids:
                    tips[r['game']] = r['tip']
    missing = [g for g in gids if g not in tips]
    if missing:
        sys.exit(f'no stored ESPN game line for {missing}: cannot tell when they tip')
    report = {'commit': commit_id(), 'written': write, 'games': {}}
    for gid in gids:
        report['games'][gid] = {'tip': tips[gid], 'days': {}}
    for f in folders:
        folder = os.path.join(snap, f)
        todo = [g for g in gids if os.path.exists(os.path.join(folder, 'polls.jsonl'))]
        if not todo:
            continue
        t0 = dt.datetime.fromisoformat(f).replace(tzinfo=S.ET).timestamp()                         # the folder holds one ET day of polls
        todo = [g for g in todo if t0 < tips[g] + 3600 and t0 + 86400 > tips[g] - LG.TRACK_H * 3600]  # the folders the game's 24h window touches
        if not todo:
            continue
        if write and f == dt.datetime.now(S.ET).date().isoformat() and not args.get('force'):
            sys.exit(f'{f} is today\'s ET folder: the recorder is still appending to it. Replay a day that has closed (or pass --force).')
        print(f'{f}: replaying {todo}', flush=True)
        out, metas, rep = replay_day(folder, todo, check_ledger=bool(args.get('check-ledger')), held_bets=not args.get('skip-held-bets'))
        for gid in todo:
            report['games'][gid]['days'][f] = {'ledger': rep[gid], 'wrote': {}}
        for src in ('minutes', 'sim', 'psim') + (() if args.get('skip-held-bets') else ('heldbets',)):
            fresh_games = [g for g in todo if not has_rows(folder, src, g)]
            rows = [r for r in out.get(src, []) if r['k'].split('|')[0] in fresh_games]
            for g in todo:
                report['games'][g]['days'][f]['wrote'][src] = sum(1 for r in rows if r['k'].split('|')[0] == g)
            if rows and write:
                merge_jsonl(os.path.join(folder, f'{src}.jsonl'), rows)
                known = {(json.loads(l)['src'], json.loads(l)['k']) for l in open(os.path.join(folder, 'meta.jsonl')) if f'"src":"{src}"' in l}
                with open(os.path.join(folder, 'meta.jsonl'), 'a') as mf:
                    for k, m in metas[src].items():
                        if k.split('|')[0] in fresh_games and (src, k) not in known:
                            mf.write(json.dumps({'k': k, 'src': src, **m}, separators=(',', ':')) + '\n')
        if write:
            path = os.path.join(folder, 'replay.json')
            cur = json.load(open(path)) if os.path.exists(path) else {}
            for gid in todo:
                was = (cur.get(gid) or {}).get('wrote') or {}                # an earlier replay of other sources stays on record
                wrote = {**was, **{k: v for k, v in report['games'][gid]['days'][f]['wrote'].items() if v or k not in was}}
                cur[gid] = {'commit': report['commit'], 'wrote': wrote,
                            'note': 'replayed from stored prices with the model files on hand, not the recorder\'s files at the time; see nba/scripts/replay_polls.py'}
                if args.get('check-ledger'):
                    cur[gid]['ledger'] = report['games'][gid]['days'][f]['ledger']
            json.dump(cur, open(path, 'w'), separators=(',', ':'))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main(sys.argv[1:])
