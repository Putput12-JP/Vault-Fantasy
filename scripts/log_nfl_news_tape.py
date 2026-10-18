#!/usr/bin/env python3
"""NFL news-timing tape -> data/nfl_news_tape.jsonl (append-only), state in data/nfl_news_state.json.

Why: to test whether the market prices injury and QB news before or after it lands, you need WHEN each status changed and what the line was at that
moment. Lines are already banked with timestamps in data/game_line_history.json (open, every move, last pre-kick sample = close). Nothing banked
status changes. This diffs two sources each run and appends one row per change:
  - Sleeper players/nfl (free, no key): injury_status, body part, depth_chart_order, team, position
  - data/qb_status.json: teams whose established QB is out or benched (the game model's own flag)

Each row carries the player's NEXT game and the line at that moment, so a later test is a pure join:
  {ts, kind: injury | depth | qb_status, baseline, team, pid, name, pos, depth, from, to, body, game:{key, opp, home, commence, week, hours_to_kick},
   line:{spread, total, open_spread, ts}}      # spread is the HOME spread, negative = home favored (same as game_line_history)
Rows are written when the status changes. The first run writes a baseline (baseline:true) for everyone currently listed so later changes have a
'from'. Close = the last game_line_history sample at or before `commence`.

  python3 scripts/log_nfl_news_tape.py                       # live: fetch Sleeper, diff, append
  python3 scripts/log_nfl_news_tape.py --players p.json --now 2026-10-18T12:00:00Z --dry     # offline / test

Stdlib only. Sleeper is rate-limited to ~1000 calls/min; this makes one call per run.
"""
import argparse, datetime, json, os, ssl, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
TAPE = os.path.join(DATA, 'nfl_news_tape.jsonl')
STATE = os.path.join(DATA, 'nfl_news_state.json')
ALIAS = {'LA': 'LAR', 'WSH': 'WAS', 'JAC': 'JAX', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LAR'}
SLEEPER = 'https://api.sleeper.app/v1/players/nfl'
LIVE = {'Out', 'Doubtful', 'Questionable', 'IR', 'PUP', 'Sus', 'NA', 'COV'}


def team(t): return ALIAS.get(str(t or '').upper(), str(t or '').upper())


def load(path, default):
    try: return json.load(open(path))
    except Exception: return default


def iso(dt): return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def parse(ts): return datetime.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))


def fetch_players():
    req = urllib.request.Request(SLEEPER, headers={'User-Agent': 'vault-news-tape'})
    return json.load(urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()))


def next_games(hist, now):
    """team -> the earliest not-yet-kicked game (regular season or later) from game_line_history."""
    out = {}
    for key, g in (hist.get('games') or {}).items():
        if g.get('seasonType') == 'preseason' or not g.get('commence') or g['commence'] <= iso(now): continue
        for side, opp in ((g.get('home'), g.get('away')), (g.get('away'), g.get('home'))):
            t = team(side)
            if t not in out or g['commence'] < out[t][1]['commence']: out[t] = (key, g, team(opp), side == g.get('home'))
    return out


def tag(ng, t, now):
    if t not in ng: return None, None
    key, g, opp, home = ng[t]
    samples = [s for s in g.get('samples', []) if s.get('ts') and s['ts'] <= iso(now) and s.get('spread') is not None]
    cur = samples[-1] if samples else None
    game = dict(key=key, opp=opp, home=home, commence=g['commence'],      # join on commence + teams: the week inside the feed's key can lag
                hours_to_kick=round((parse(g['commence']) - now).total_seconds() / 3600, 1))
    line = dict(spread=cur['spread'], total=cur.get('total'), open_spread=(g.get('open') or {}).get('spread'), ts=cur['ts']) if cur else None
    return game, line


def run(players, qb_status, hist, state, now):
    ng = next_games(hist, now)
    first = not state.get('players')
    rows, new = [], {}
    for pid, p in players.items():
        t = team(p.get('team'))
        if not p.get('team'): continue
        status, depth, pos = p.get('injury_status') or '', p.get('depth_chart_order'), p.get('position')
        if not status and pos != 'QB' and pid not in state.get('players', {}): continue      # track statuses, plus every QB's depth
        new[pid] = [status, depth, t]
        old = state.get('players', {}).get(pid)
        base = dict(ts=iso(now), team=t, pid=pid, name=p.get('full_name') or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(), pos=pos, depth=depth,
                    body=p.get('injury_body_part') or None)
        kinds = []
        if old is None:
            if status and status in LIVE: kinds.append(('injury', None, status, first))
        else:
            if old[0] != status: kinds.append(('injury', old[0] or None, status or None, False))
            elif pos == 'QB' and old[1] != depth: kinds.append(('depth', old[1], depth, False))
        for kind, frm, to, bl in kinds:
            game, line = tag(ng, t, now)
            rows.append(dict(base, kind=kind, baseline=bl, **{'from': frm, 'to': to}, game=game, line=line))
    # QB status: teams whose established QB is out or benched, from the game model's flag
    qnow = {team(t): [v.get('starter'), v.get('reason')] for t, v in (qb_status.get('teams') or {}).items()}      # lists, so the JSON state round-trips equal
    qold = state.get('qb')
    if qold is not None or first:
        for t in sorted(set(qnow) | set(qold or {})):
            a, b = (qold or {}).get(t), qnow.get(t)
            if a == b and not (first and b): continue
            game, line = tag(ng, t, now)
            rows.append(dict(ts=iso(now), kind='qb_status', baseline=bool(first and b), team=t, pid=None, name=(b or a)[0], pos='QB', depth=None, body=None,
                             **{'from': a, 'to': b}, game=game, line=line))
    state = dict(players=new, qb=qnow, updated=iso(now))
    return rows, state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--players', help='local Sleeper players json instead of fetching'); ap.add_argument('--now'); ap.add_argument('--dry', action='store_true')
    ap.add_argument('--hist', default=os.path.join(DATA, 'game_line_history.json')); ap.add_argument('--qb', default=os.path.join(DATA, 'qb_status.json'))
    ap.add_argument('--tape', default=TAPE); ap.add_argument('--state', default=STATE)
    a = ap.parse_args()
    now = parse(a.now) if a.now else datetime.datetime.now(datetime.timezone.utc)
    players = json.load(open(a.players)) if a.players else fetch_players()
    if len(players) < 1000: sys.exit(f'refusing to diff: only {len(players)} players came back (a thin response must not look like mass status changes)')
    rows, state = run(players, load(a.qb, {}), load(a.hist, {}), load(a.state, {}), now)
    print(f'{len(rows)} change(s)' + (' (dry run, nothing written)' if a.dry else ''))
    for r in rows[:8]: print('  ', r['kind'], r['team'], r['name'], r['from'], '->', r['to'], '| game', (r['game'] or {}).get('key'), '| spread', (r['line'] or {}).get('spread'))
    if a.dry: return
    if rows:
        with open(a.tape, 'a') as f:
            for r in rows: f.write(json.dumps(r, separators=(',', ':')) + '\n')
    tmp = a.state + '.tmp'; json.dump(state, open(tmp, 'w'), separators=(',', ':')); os.replace(tmp, a.state)


if __name__ == '__main__':
    main()
