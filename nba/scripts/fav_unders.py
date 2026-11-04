#!/usr/bin/env python3
"""
Favorite unders: a watch list, shadow-tracked. Not a bet, no stake, changes no price.

Found in a scenario sweep of this season's priced props (Oct 21 to Nov 2, 2026: 1,621 slices of market x side x home/away x favorite/dog x spread x
total x team total x price x minutes x model agreement x book). One family stayed positive in both halves of the nights; this is the rule, frozen here
before any forward night (docs/fav-unders.md). A prop is on the list when, as of LOCK_MIN minutes before tip:

  1. the player's team is favored by SPREAD (4.5 to 8.5 points) on the DraftKings spread (espn source, key <game>|100|game)
  2. it is the UNDER on the main line (prop_sim_record row: sportsbook consensus line, price_src 'books') for points / rebounds / assists / 3-pointers
  3. the model's under chance (psim p_exact) is at least GAP above the no-vig price's under chance (psim p_price)
  4. the roster guard is not holding the team (psim meta 'held')
  5. DraftKings or Pinnacle has an under price at that exact line (shadow ledger book rows); the best of the two is the price taken

Every number is one the recorders already stored before tip; nothing is rebuilt from today's model. Settled from the box score: W / L, P (landed on the
line) or D (did not play). Return is 1 unit at the stored price. Close: the no-vig under chance at the same line in propclose.json, so close EV =
p_close x decimal - 1 (only when that line has a closing price).

The props on one team in one game move together (one game script), so the page also scores each team-game as one group: units summed, and a
team-game counts as a win when its units are above zero. That is the honest sample size; the prop count overstates it.

  record(root, now, prev, rescan_days, games, L, locks=None) -> {tip_day: [team-game, ...]}
    team-game: {'game', 'matchup', 'tip', 'team', 'fav', 'fwd': 1 when on or after FORWARD_FROM, 'p': [pick, ...]}
    pick: [pid, player, stat, line, model, market, book, american, decimal, actual, result, units, close_p]
  `locks`, when a dict, is filled with tonight's team-games not yet settled (tip within the last 6 hours or later), picks chosen from rows up to
  the lock (or up to now before the lock, with 'live': 1).
  An empty prev (first run, or a VERSION change) scans every stored day, so the record starts on opening night.
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

VERSION = 1
SPREAD = (4.5, 8.5)                  # the player's team is favored by this many points, inclusive
GAP = 0.05                           # model under chance minus the no-vig under chance, at least
LOCK_MIN = 60                        # picks are fixed this many minutes before tip
FORWARD_FROM = '2026-11-04'          # the rule was found on Oct 21 to Nov 2; nights from here on are the forward test
STATS = ('pts', 'reb', 'ast', '3pm')
STAT_BOX = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', '3pm': 'threePointFieldGoalsMade'}
BOOKS = ('DraftKings', 'Pinnacle')


def _dec(am):
    try:
        a = float(am)
    except (TypeError, ValueError):
        return None
    if a == 0 or abs(a) < 100:
        return None
    return 1 + (a / 100 if a > 0 else 100 / -a)


def _at(ser, t):
    """The value as of t. A None (the market was taken down) counts: a line pulled before the lock has no price, not its last one."""
    v = None
    for ts, x in sorted(ser or (), key=lambda z: z[0]):
        if ts > t:
            break
        v = x
    return v


def _scan(root, since, src, keep):
    """{key: [(t, v)]} and {key: meta} for one change log across day folders from `since`, reading only lines `keep` accepts (the ledger is large)."""
    ser, meta = {}, {}
    tag = f'"src":"{src}"'
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        if os.path.basename(d) < since:
            continue
        mp = os.path.join(d, 'meta.jsonl')
        if os.path.exists(mp):
            for line in open(mp):
                if tag in line and keep(line):
                    r = json.loads(line); meta[r['k']] = r
        lp = os.path.join(d, f'{src}.jsonl')
        if os.path.exists(lp):
            for line in open(lp):
                if not keep(line):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                ser.setdefault(r['k'], []).append((r['t'], r['v']))
    return ser, meta


def _closes(root, since):
    out = {}
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        if os.path.basename(d) < since:
            continue
        p = os.path.join(d, 'propclose.json')
        if os.path.exists(p):
            try:
                out.update(json.load(open(p)))
            except ValueError:
                pass
    return out


def screen(root, since, now, games, L):
    """{game: {team: team-game}} for every game from `since` with at least one pick, chosen as of min(now, lock)."""
    psim, pmeta = _scan(root, since, 'psim', lambda l: True)
    gl, gmeta = _scan(root, since, 'espn', lambda l: '|game"' in l)
    led, _ = _scan(root, since, 'ledger', lambda l: '|book|' in l and '|Under|' in l and ('|DraftKings|' in l or '|Pinnacle|' in l))
    lines = {}
    for k, s in led.items():
        gid, pid, st, venue, book, side, ln = k.split('|')
        lines.setdefault((gid, pid, st, float(ln)), {})[book] = s
    spread = {str(m['game']): (m, gl.get(k)) for k, m in gmeta.items()}
    out = {}
    for k, m in pmeta.items():
        gid = str(m['game'])
        if m.get('stat') not in STATS or m.get('held') or (games and not games(gid)):
            continue
        lock = m['tip'] - LOCK_MIN * 60
        asof = min(now, lock)
        v = _at([x for x in psim.get(k, ()) if x[0] < m['tip'] and x[1] is not None], asof)
        if not v:
            continue
        line, mu, pe, _, _, pm, src = v[:7]
        if pm is None or src != 'books':
            continue
        g = spread.get(gid)
        gv = g and _at([x for x in g[1] or () if x[1]], asof)
        try:
            hs = float(gv[0])
        except (TypeError, ValueError, IndexError):
            continue
        tsp = hs if m['team'] == g[0].get('home') else -hs
        if not (SPREAD[0] <= -tsp <= SPREAD[1]):
            continue
        model, market = 1 - pe, 1 - pm
        if model - market < GAP - 1e-9:
            continue
        best = None
        for book, s in lines.get((gid, str(m['pid']), m['stat'], float(line)), {}).items():
            pv = _at([x for x in s if x[0] < m['tip']], asof)
            d = _dec(pv[0]) if pv else None
            if d and (best is None or d > best[2]):
                best = (book, pv[0], d)
        if not best:
            continue
        tg = out.setdefault(gid, {}).setdefault(m['team'], {'game': gid, 'matchup': m['matchup'], 'tip': m['tip'], 'team': m['team'], 'fav': -tsp,
                                                            'fwd': 1 if L.tip_day(m['tip']) >= FORWARD_FROM else 0, 'p': [],
                                                            **({'live': 1} if now < lock else {})})
        tg['p'].append([m['pid'], m['player'], m['stat'], line, round(model, 4), round(market, 4), best[0], str(best[1]), round(best[2], 4)])
    for teams in out.values():
        for tg in teams.values():
            tg['p'].sort(key=lambda p: -(p[4] - p[5]))
    return out


def settle(tg, bx, close):
    """Adds actual, result, units and close_p to each pick; returns the team-game."""
    for p in tg['p']:
        pid, stat, line, dec = p[0], p[2], p[3], p[8]
        st = bx.get(int(pid))
        y = None if not st else st.get(STAT_BOX[stat], 0)
        r = 'D' if y is None else 'P' if y == line else 'W' if y < line else 'L'
        u = round(dec - 1, 4) if r == 'W' else -1.0 if r == 'L' else 0.0
        cp = None
        for c in (close or {}).get('props', {}).get(f'{pid}|{stat}', []):
            if c[0] == line and c[1] is not None:
                cp = round(1 - c[1], 4)
        p += [y, r, u, cp]
    return tg


def record(root, now, prev, rescan_days, games, L, locks=None):
    days = dict(prev or {})
    if prev:
        since = L.tip_day(now - rescan_days * 86400)
    else:
        found = sorted(os.path.basename(d) for d in glob.glob(os.path.join(root, 'snapshots', '20*')))
        since = found[0] if found else L.tip_day(now - rescan_days * 86400)
    picks = screen(root, since, now, games, L)
    closes = _closes(root, since)
    per_day = {}
    for gid, teams in picks.items():
        tip = next(iter(teams.values()))['tip']
        if now < tip + L.SETTLE_AFTER_S:
            if locks is not None and tip > now - 6 * 3600:
                for tg in teams.values():
                    locks[f"{gid}|{tg['team']}"] = tg
            continue
        bx = L.box(root, gid)
        if bx is None:
            if locks is not None and tip > now - 6 * 3600:
                for tg in teams.values():
                    locks[f"{gid}|{tg['team']}"] = tg
            continue
        for tg in teams.values():
            tg.pop('live', None)
            per_day.setdefault(L.tip_day(tip), []).append(settle(tg, bx, closes.get(gid)))
    for d, gs in per_day.items():
        days[d] = sorted(gs, key=lambda g: (g['tip'], g['team']))
    return days


if __name__ == '__main__':                          # python fav_unders.py <nba-data root> : print the whole record
    import time
    import ledger as L
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'raw', 'nba-data')
    locks = {}
    days = record(root, time.time(), None, 3, None, L, locks)
    tot = {'all': [0, 0, 0.0, 0], 'fwd': [0, 0, 0.0, 0]}
    for d in sorted(days):
        w = l = 0; u = 0.0
        for tg in days[d]:
            for p in tg['p']:
                w += p[10] == 'W'; l += p[10] == 'L'; u += p[11]
            for k in ('all',) + (('fwd',) if tg['fwd'] else ()):
                tu = sum(p[11] for p in tg['p'])
                tot[k][0] += sum(p[10] == 'W' for p in tg['p']); tot[k][1] += sum(p[10] == 'L' for p in tg['p']); tot[k][2] += tu; tot[k][3] += 1
        print(f'{d}: {len(days[d])} team-games  {w}-{l}  {u:+.2f}u')
    for k, (w, l, u, n) in tot.items():
        print(f'{k}: {w}-{l}  {u:+.2f}u  ROI {u / max(1, w + l):+.1%}  team-games {n}')
    print('tonight (not settled):', len(locks), 'team-games', sum(len(t['p']) for t in locks.values()), 'props')
