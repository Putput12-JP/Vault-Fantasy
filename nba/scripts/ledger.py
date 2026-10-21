#!/usr/bin/env python3
"""
Shadow ledger: every prop edge the Player Props page shows, logged as it happens, settled from the box score.
Nothing here is a real bet. It is how a signal earns GO on this season's games (docs/PLAN.md: promote a market only
when live results agree with the backtest).

Logging (called by snapshot.py after each poll, from the same board the page reads):
  - pricing.py prices every candidate exactly as the page does (Minutes Lab minutes with Outs applied, prop model v2,
    calibration, market blend, fees, gates).
  - A candidate is TRACKED from the first poll its edge reaches EDGE_MIN (3%, the backtest's threshold), for games
    tipping within TRACK_H hours, and then recorded every time its price, fair or edge changes until tip, whether or
    not the edge lasts. Stored as source 'ledger' in the day folder: snapshots/<day>/ledger.jsonl (change-only, like
    prices) with meta.jsonl describing each key.
  - Key: game|player|stat|venue|book|side|line.  Value: [price, fair, edge, gate, projection, minutes, consensus,
    consensus edge, consensus gate]. A candidate is tracked when EITHER edge reaches 3%: the model's (fair from our
    projection blended with the price) or the consensus engine's (consensus.py: every other venue moved to this line).
    Each bet records which one triggered it (etype model / gap / both), so the Track Record can compare them.

Settling (settle(), same job, each poll): for games that tipped 3+ hours ago, ESPN's box score (cached under
results/<game>.json). One shadow bet per key, 1 unit:
  entry  the first poll it reached 3% (the price a live bettor could have taken then)
  close  the last poll before tip (closest to the backtest's clock: Kalshi 30-minute pre-tip VWAP)
  Kalshi YES wins if the stat is over the rung's floor line; cost = price + taker fee (0.07 p (1-p), rounded up).
  Books: over / under the line, American odds, a whole-number landing on the line is a push.
  Player did not play: void (books refund; Kalshi's own rule may differ, noted on the page).
  CLV = the same side's price at close minus at entry, in probability points (positive = the market came to us).
Pick'em lines are logged too (venue 'pickem'): a flat line (PrizePicks) is settled as one pick at the flex
break-even price (PK_BE, about -119), a priced line (Underdog, Sleeper) at its own price.

A book is spelled one way everywhere (nba_common.book_name). ESPN's feed calls DraftKings 'Draft Kings' on some polls and 'DraftKings' on others, and
a ledger key carries the book, so one quote was once logged under two keys and counted as two bets. load_ledger reads keys canonically (so history
heals), and settle() collapses stored bets and cube rows the same way.

Roster guard: a candidate held by pricing.roster_hold (or the source / returning holds) is priced and shown but never logged. Opening night 2026-10-20
held all six teams (PHI 6 players with minutes history, NY / SA stretch 1.15 / 1.14, BOS 1.35, DET 1.45, OKC 1.10), so those three games have no
shadow bets by design. LOG_STATS says it per game and the Data Health page shows it (snapshot.write_flags).

Storage, sized for a season of 100k+ bets:
  bets/<tip ET date>.json   every bet for games tipping that day (only recent days are rewritten)
  track.json                the cube (one row per tip day x stat x venue x book x side x gate x edge bucket with
                            counts, units, sum of squares, CLV sums; every market the page can filter or group),
                            the latest bets, and the GO / WATCH backtest results. Small enough to read every poll.
Preseason games (season_types.json, saved by snapshot.py from ESPN) are logged and settled the same way, as a rehearsal,
but go to track.json 'preseason' instead: the models were never tested on preseason minutes, so those bets never count
toward the season's record, a signal's 50-bet promotion, the Minutes Lab's record, the Injury Wire or Sharp Price.
"""
import datetime as dt, glob, json, math, os, subprocess, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pricing as PX
from nba_common import et, book_name

TRACK_H = 24                 # only games tipping within this many hours are logged
SETTLE_AFTER_S = 3 * 3600    # a game is checked for a final score this long after tip (an overtime or a delay is just not final yet: retried every poll)
MIN_BOX_MINUTES = 300        # a box with fewer player minutes than this is not a finished game's (see box())
SUMMARY = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={}'
try:
    import novig_paper as _NPC
    NPT_CFG = (_NPC.FEE_ON_PROFIT, _NPC.EDGE_MIN, _NPC.STAKE)       # shown beside the Novig paper results, so the page never disagrees with the simulator
except Exception:
    NPT_CFG = (None, None, None)
STAT_COL = {'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists'], '3pm': ['threePointFieldGoalsMade'],
            'pra': ['points', 'rebounds', 'assists'], 'pr': ['points', 'rebounds'], 'pa': ['points', 'assists'],
            'ra': ['rebounds', 'assists'], 'stl': ['steals'], 'blk': ['blocks'], 'tov': ['turnovers'], 'sb': ['steals', 'blocks'],
            'fgm': ['fieldGoalsMade'], 'fga': ['fieldGoalsAttempted'], 'ftm': ['freeThrowsMade'], 'fta': ['freeThrowsAttempted'],
            'tpa': ['threePointFieldGoalsAttempted'], 'oreb': ['offensiveRebounds'], 'dreb': ['defensiveRebounds'], 'pf': ['fouls']}


# ── logging ──────────────────────────────────────────────────────────────────────────────────
def canon_key(k):
    """A ledger key with its book spelled one way (game|player|stat|venue|book|side|line)."""
    p = k.split('|')
    if len(p) > 4:
        p[4] = book_name(p[4])
    return '|'.join(p)


HELD_OUT = ({}, {})  # (rows, meta) of the last log() call: candidates a hold kept out of the bets that carry a GO or WATCH gate (source 'heldbets')
def trigger_gate(c):
    """The gate a candidate would be logged under: the better of the model's gate (if the model edge reached EDGE_MIN) and the consensus gap's gate (if the gap did)."""
    gs = []
    if c['edge'] >= PX.EDGE_MIN:
        gs.append(c['g'])
    if c.get('gap') is not None and c['gap'] >= PX.EDGE_MIN:
        gs.append(c.get('gap_g', 'no-go'))
    return min(gs, key=lambda g: GATE_RANK[g]) if gs else 'no-go'


LOG_STATS = {}      # game id -> {'cands', 'edge', 'held', 'logged'} from the last log() call: snapshot.shadow() puts it in the poll record


def log(day, board, now):
    """-> (rows, meta) for Day.record('ledger', ...). Tracked keys that are missing now (tipped, delisted) are recorded
    as gone by Day.record itself. LOG_STATS says, per game, how many candidates were priced, how many reached the edge
    threshold, how many of those the roster guard (or another hold) kept out, and how many rows were logged: a game with edges
    and zero rows is held, not broken, and the Data Health page can tell the two apart."""
    global HELD_OUT
    LOG_STATS.clear()
    HELD_OUT = ({}, {})
    if not board or not board.get('props'):
        return {}, {}
    tracked = {canon_key(k) for k in (day.last.get('ledger') or {})}
    held_tracked = {canon_key(k) for k in (day.last.get('heldbets') or {})}
    held_rows, held_meta = HELD_OUT
    games = {str(g['id']): g for g in board.get('games', [])}
    rows, meta = {}, {}
    for c in PX.price_board(board):
        g = games.get(c['gid'])
        if not g or not (now < g['tip'] <= now + TRACK_H * 3600):
            continue
        S = LOG_STATS.setdefault(c['gid'], {'cands': 0, 'edge': 0, 'held': 0, 'logged': 0})
        S['cands'] += 1
        bk = book_name(c['bk'])
        k = f"{c['gid']}|{c['p']}|{c['s']}|{c['venue']}|{bk}|{c['side']}|{c['line']}"
        edged = c['edge'] >= PX.EDGE_MIN or (c.get('gap') is not None and c['gap'] >= PX.EDGE_MIN)
        S['edge'] += edged
        if k not in tracked and not edged:
            continue
        if k not in tracked and c.get('hold') and c['hold'].get('why') != 'preseason':   # roster guard (preseason is
            S['held'] += 1                            # still logged, into the separate preseason record)
            if k in held_tracked or trigger_gate(c) != 'no-go':       # a hold keeps it from being a bet, but a GO or WATCH candidate it kept out is
                held_rows[k] = [round(c['price'], 4) if isinstance(c['price'], float) else c['price'], round(c['fair'], 4), round(c['edge'], 4), c['g'], round(c['mu'], 2), round(c['min'], 1),      # recorded apart (source 'heldbets'), never a bet
                                c.get('cons'), round(c['gap'], 4) if c.get('gap') is not None else None, c.get('gap_g', 'no-go'), ','.join(c.get('types') or [])]
                P = board['players'].get(str(c['p'])) or board['players'].get(c['p']) or [str(c['p']), c['team']]
                held_meta[k] = {'game': c['gid'], 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'pid': c['p'], 'player': P[0], 'team': P[1], 'stat': c['s'],
                                'venue': c['venue'], 'book': bk, 'side': c['side'], 'line': c['line'], 'hold': c['hold']['why']}
            continue
        S['logged'] += k not in rows
        rows[k] = [round(c['price'], 4) if isinstance(c['price'], float) else c['price'], round(c['fair'], 4), round(c['edge'], 4), c['g'], round(c['mu'], 2), round(c['min'], 1),
                   c.get('cons'), round(c['gap'], 4) if c.get('gap') is not None else None, c.get('gap_g', 'no-go'), ','.join(c.get('types') or [])]
        P = board['players'].get(str(c['p'])) or board['players'].get(c['p']) or [str(c['p']), c['team']]
        meta[k] = {'game': c['gid'], 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'pid': c['p'], 'player': P[0],
                   'team': P[1], 'stat': c['s'], 'venue': c['venue'], 'book': bk, 'side': c['side'], 'line': c['line']}
    return rows, meta


# ── settling ─────────────────────────────────────────────────────────────────────────────────
def curl_json(url):
    p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '30', url], capture_output=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def parse_box(d):
    """(box, starters, score, names) from an ESPN summary, or None while the game is not final or the box is not filled in yet.
    box: {athlete_id: {stat: value} or None (did not play)}."""
    try:
        if not d['header']['competitions'][0]['status']['type']['completed']:
            return None
    except (KeyError, IndexError, TypeError):
        return None
    out, starters, names = {}, [], {}
    for team in (d.get('boxscore') or {}).get('players', []):
        for block in team.get('statistics', [])[:1]:
            keys = block.get('keys') or []
            for a in block.get('athletes', []):
                aid = int(a['athlete']['id'])
                names[aid] = a['athlete'].get('displayName') or str(aid)
                if a.get('starter'):
                    starters.append(aid)
                if a.get('didNotPlay') or not a.get('stats'):
                    out[aid] = None
                    continue
                v = {}
                for key, raw in zip(keys, a['stats']):
                    for part, name in zip(raw.split('-'), key.split('-')):
                        try:
                            v[name] = float(part)
                        except ValueError:
                            pass
                out[aid] = v
    # ESPN can flip a game to completed a little before its box score is filled in. Caching that would be permanent (the file
    # is never re-read) and every player would settle as 'did not play': void. A real game has 400+ player minutes (480 regulation,
    # 530 with an overtime); anything under MIN_BOX_MINUTES is treated as not final yet and tried again on the next poll.
    if sum((v or {}).get('minutes', 0) for v in out.values()) < MIN_BOX_MINUTES:
        return None
    try:                                          # final score and starters, for the Minutes Lab's record
        comp = d['header']['competitions'][0]
        score = {c['team']['abbreviation']: float(c.get('score') or 0) for c in comp['competitors']}
    except (KeyError, IndexError, TypeError, ValueError):
        score = {}
    return out, starters, score, names


def box(root, gid):
    """{athlete_id: {stat: value} or None (did not play)} once the game is final, cached; None if not final yet.
    The cached file is first-read-wins here; refresh_boxes() re-reads it for BOX_RECHECK_MAX_H after the game, because ESPN corrects a box score
    after the final (Oct 20, 2026: OKC @ SA, Caruso rebounds 7 then 6, steals 2 then 1, McCain rebounds 3 then 2)."""
    path = os.path.join(root, 'results', f'{gid}.json')
    if os.path.exists(path):
        return {int(k): v for k, v in json.load(open(path)).items()}
    got = parse_box(curl_json(SUMMARY.format(gid)))
    if not got:
        return None
    out, starters, score, _ = got
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    json.dump({'score': score, 'starters': starters}, open(os.path.join(root, 'results', f'{gid}.meta.json'), 'w'), separators=(',', ':'))
    return out


def box_meta(root, gid):
    path = os.path.join(root, 'results', f'{gid}.meta.json')
    return json.load(open(path)) if os.path.exists(path) else {}


# ── box scores are corrected after the final: keep re-reading them for a while ─────────────────────────────────────────────
BOX_RECHECK_FAST_H = 36      # re-read every BOX_RECHECK_EVERY_S for this long after tip ...
BOX_RECHECK_EVERY_S = 3600
BOX_RECHECK_MAX_H = 72       # ... and every BOX_RECHECK_SLOW_S until this long after tip (the rescan window)
BOX_RECHECK_SLOW_S = 12 * 3600
BOX_CHANGES_KEEP = 60        # corrections kept in track.json
BOX_CHANGES = []             # corrections the last refresh_boxes() call found: {t, game, matchup, pid, player, stat, old, new}
SETTLE_ERR = {}              # record name -> error, for a record settle() could not update (it keeps the old one); snapshot.shadow() reports it
STUCK_H = 8                  # a game this long after tip with no final box score is "stuck" (a long game ends about 3 hours after tip)


def game_tips(root, since):
    """{game id: (tip, matchup)} for every game the Minutes Lab logged in the day folders from `since` on (held games included)."""
    out = {}
    tag = '"src":"minutes"'
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        mp = os.path.join(d, 'meta.jsonl')
        if os.path.basename(d) < since or not os.path.exists(mp):
            continue
        for line in open(mp):
            if tag in line:
                m = json.loads(line)
                out[str(m['game'])] = (m['tip'], m['matchup'])
    return out


def refresh_boxes(root, now, tips):
    """Re-read the ESPN box score of every finished game still inside the correction window and rewrite it when a stat changed.
    tips: {game id: (tip, matchup)}. Returns the set of game ids whose box changed (BOX_CHANGES says what). Every other record re-reads
    the box from disk on each poll, so a correction flows to them by itself; settled bets are re-graded by settle() for the games returned here.
    Nothing is invented: the new numbers are ESPN's own, and the old numbers stay in track.json 'box_changes'."""
    BOX_CHANGES.clear()
    changed = set()
    for gid, (tip, matchup) in tips.items():
        age = now - tip
        path, mpath = os.path.join(root, 'results', f'{gid}.json'), os.path.join(root, 'results', f'{gid}.meta.json')
        if age < SETTLE_AFTER_S or age > BOX_RECHECK_MAX_H * 3600 or not os.path.exists(path):
            continue
        meta = box_meta(root, gid)
        every = BOX_RECHECK_EVERY_S if age <= BOX_RECHECK_FAST_H * 3600 else BOX_RECHECK_SLOW_S
        if now - meta.get('chk', 0) < every:
            continue
        got = parse_box(curl_json(SUMMARY.format(gid)))
        if not got:
            continue                                  # not final, not filled in, or ESPN did not answer: keep what is stored, look again next time
        new, starters, score, names = got
        old = {int(k): v for k, v in json.load(open(path)).items()}
        if not set(old) <= set(new):                  # a re-read that lost players is a partial box, not a correction
            meta['chk'] = now
            json.dump(meta, open(mpath, 'w'), separators=(',', ':'))
            continue
        diffs = []
        for aid in sorted(set(old) | set(new)):
            a, b = old.get(aid), new.get(aid)
            if a == b:
                continue
            if a is None or b is None or aid not in old or aid not in new:
                diffs.append((aid, 'played', a is not None, b is not None))
                continue
            for stat in sorted(set(a) | set(b)):
                if a.get(stat) != b.get(stat):
                    diffs.append((aid, stat, a.get(stat), b.get(stat)))
        meta['chk'] = now
        if diffs:
            json.dump(new, open(path, 'w'), separators=(',', ':'))
            meta.update(score=score or meta.get('score'), starters=starters or meta.get('starters'), rev=meta.get('rev', 0) + 1)
            changed.add(gid)
            for aid, stat, o, n in diffs:
                BOX_CHANGES.append({'t': now, 'game': gid, 'matchup': matchup, 'pid': aid, 'player': names.get(aid, str(aid)), 'stat': stat, 'old': o, 'new': n})
        json.dump(meta, open(mpath, 'w'), separators=(',', ':'))
    return changed


# ── closing prices and results for the page's "My bets" (users' own bet logs settle in the browser) ────────────────────
CLOSE_SPREAD = 0.10           # a Kalshi rung wider than this is not a price


def close_log(root, board, now):
    """Every prop's market price at each number, rewritten each poll until its game tips, so the last write is the close:
    snapshots/<tip ET date>/propclose.json {gid: {t, tip, m, props: {'pid|stat': [[line, P(over) no-vig, src]]}}}.
    src: pin = Pinnacle, mkt = median of the other books (vig removed proportionally, as the page does), kal = Kalshi mid."""
    if not board or not board.get('props'):
        return
    games = {str(g['id']): g for g in board.get('games', [])}
    per = defaultdict(dict)
    for e in board['props']:
        g = games.get(str(e['g']))
        if not g or now >= g['tip']:
            continue
        pin, other = {}, defaultdict(list)
        for b in e.get('books') or []:
            po, pu = PX.am_p(b[2]), PX.am_p(b[3])
            if po and pu and b[1] is not None:
                (pin.__setitem__(b[1], po / (po + pu)) if b[0] == 'Pinnacle' else other[b[1]].append(po / (po + pu)))
        rows = [[l, round(p, 4), 'pin'] for l, p in pin.items()]
        for l, ps in other.items():
            if l not in pin:
                ps = sorted(ps)
                rows.append([l, round(ps[len(ps) // 2] if len(ps) % 2 else (ps[len(ps) // 2 - 1] + ps[len(ps) // 2]) / 2, 4), 'mkt'])
        for k in e.get('kal') or []:
            if k[1] is not None and k[2] is not None and k[2] - k[1] <= CLOSE_SPREAD and k[0] not in pin and k[0] not in other:
                rows.append([k[0], round((k[1] + k[2]) / 2, 4), 'kal'])
        if rows:
            G = per[tip_day(g['tip'])].setdefault(str(g['id']), {'t': now, 'tip': g['tip'], 'm': f"{g['away']} @ {g['home']}", 'props': {}})
            G['props'][f"{e['p']}|{e['s']}"] = sorted(rows)
    for d, gs in per.items():
        p = os.path.join(root, 'snapshots', d, 'propclose.json')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        cur = json.load(open(p)) if os.path.exists(p) else {}
        cur.update(gs)
        json.dump(cur, open(p, 'w'), separators=(',', ':'))


BOX_COLS = ['points', 'rebounds', 'assists', 'threePointFieldGoalsMade', 'steals', 'blocks', 'turnovers', 'fieldGoalsMade', 'fieldGoalsAttempted',
            'freeThrowsMade', 'freeThrowsAttempted', 'threePointFieldGoalsAttempted', 'offensiveRebounds', 'defensiveRebounds', 'fouls']   # the page's PV_BOXI indexes into this


def closes_record(root, now, rescan_days=3, corrected=()):
    """snapshots/<day>/closes.json for the page: each game's closing prices (propclose.json) and, once final, every
    player's box line {pid: [pts, reb, ast, 3pm, stl, blk, tov, fgm, fga, ftm, fta, tpa, oreb, dreb, pf]} or null for did not play. Only recent days are rewritten."""
    since = tip_day(now - rescan_days * 86400)
    for p in sorted(glob.glob(os.path.join(root, 'snapshots', '20*', 'propclose.json'))):
        d = os.path.basename(os.path.dirname(p))
        if d < since:
            continue
        out = os.path.join(os.path.dirname(p), 'closes.json')
        prev = json.load(open(out)) if os.path.exists(out) else {}
        games = {}
        for gid, g in json.load(open(p)).items():
            old = (prev.get('games') or {}).get(gid)
            if old and old.get('box') is not None and gid not in corrected:
                games[gid] = dict(g, box=old['box'])
                continue
            bx = box(root, gid) if now >= g['tip'] + SETTLE_AFTER_S else None
            games[gid] = dict(g, box=None if bx is None else {str(a): (None if v is None else [v.get(c, 0) for c in BOX_COLS]) for a, v in bx.items()})
        if games != prev.get('games'):
            json.dump({'t': now, 'games': games}, open(out, 'w'), separators=(',', ':'))


# ── the Minutes Lab's record: tonight's projected minutes against the box score ─────────────────
def minutes_log(board, now):
    """Every player's projected minutes for games within TRACK_H, as live pricing computes them (pricing.py
    game_minutes, the backtest's path) -> (rows, meta) for Day.record('minutes', ...). Value: [minutes, recent avg]."""
    rows, meta = {}, {}
    if not board or not board.get('games'):
        return rows, meta
    pr = PX.Pricer(example=bool(board.get('example')))
    if not pr.MM:
        return rows, meta
    status, cache = PX.status_from_board(board), {}
    names = {int(k): v.get('nm') for k, v in pr.state['players'].items() if (v or {}).get('nm')}
    names.update({x['id']: x['name'] for T in pr.D['teams'].values() for x in T['players']})
    names.update({int(k): v[0] for k, v in (board.get('players') or {}).items() if v})
    fives = board.get('starters') or {}
    for g in board['games']:
        if not (now < g['tip'] <= now + TRACK_H * 3600):
            continue
        for team in (g['away'], g['home']):
            five = fives.get(team)
            shadow = {}
            for name, fn in (('v3', lambda: pr.game_minutes_v3(team, g, status, cache, starters=five)),     # shadow, never priced
                             ('gbm', lambda: pr.game_minutes_gbm(team, g, status, cache))):                  # shadow (gradient-boosted minutes), never priced
                try:
                    shadow[name] = fn() or {}
                except Exception as e:                      # a shadow model failing must not take the priced minutes with it
                    PX.row_error(f"minutes {name} {g['id']}|{team}", e)
                    shadow[name] = {}
            v3, gb = shadow['v3'], shadow['gbm']
            try:
                gm = pr.game_minutes(team, g, status, cache)
            except Exception as e:
                PX.row_error(f"minutes {g['id']}|{team}", e)
                continue
            for pid, G in gm.items():
                try:
                    k = f"{g['id']}|{pid}"
                    rows[k] = [round(G['min'], 2), round(((pr.state['players'].get(str(pid)) or {}).get('ms') or [0])[0], 2),
                               round(v3[pid], 2) if pid in v3 else None, 1 if five else 0, round(gb[pid], 2) if pid in gb else None]
                    meta[k] = {'game': str(g['id']), 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'pid': pid,
                               'player': names.get(pid, str(pid)), 'team': team}
                except Exception as e:                      # one player's bad field skips that player, not the game
                    rows.pop(k, None)
                    PX.row_error(f"minutes {g['id']}|{pid}", e)
    return rows, meta


def load_src(root, src, since):
    """key -> {'meta', 'series'} for one logged source across day folders from `since` on."""
    L = defaultdict(lambda: {'meta': None, 'series': []})
    tag = f'"src":"{src}"'
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        if os.path.basename(d) < since:
            continue
        mp = os.path.join(d, 'meta.jsonl')
        if os.path.exists(mp):
            for line in open(mp):
                if tag in line:
                    r = json.loads(line)
                    L[r['k']]['meta'] = {k: v for k, v in r.items() if k not in ('k', 'src')}
        lp = os.path.join(d, f'{src}.jsonl')
        if os.path.exists(lp):
            for line in open(lp):
                r = json.loads(line)
                L[r['k']]['series'].append((r['t'], r['v']))
    return L


def wire_record(root, now, prev, rescan_days=3, games=None):
    """The Injury Wire's season record: per ET day, per venue, per kind of news (inj / five / inactive), the quotes
    affected, how many moved before tip, and each change's first-move time in seconds (-1 = never moved before tip).
    Read from snapshots/<day>/wire.json (snapshot.save_wire); days older than the rescan window are kept as they were."""
    days = dict(prev or {})
    since = tip_day(now - rescan_days * 86400)
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        day = os.path.basename(d)
        path = os.path.join(d, 'wire.json')
        if day < since or not os.path.exists(path):
            continue
        try:
            events = json.load(open(path)).values()
        except ValueError:
            continue
        rec = {}
        for e in events:
            if games and not games(str(e[-2])):
                continue
            for venue, (n, m, med, first) in (e[7] or {}).items():
                r = rec.setdefault(venue, {}).setdefault(e[1], {'n': 0, 'm': 0, 'f': []})
                r['n'] += n
                r['m'] += m
                r['f'].append(int(first) if first is not None else -1)
        days[day] = rec
    return days


def minutes_record(root, now, prev, rescan_days=3, games=None):
    """Per tip day: projected minutes (last value before tip) against the box score. Players who did not play are
    counted apart (books void their props; the backtest scored players who played). Days already final are kept."""
    days = dict(prev or {})
    since = tip_day(now - rescan_days * 86400)
    per_day, replayed = defaultdict(list), defaultdict(int)
    for k, x in load_src(root, 'minutes', since).items():
        m = x['meta']
        pre = [v for t, v in sorted(x['series']) if v is not None and m and t < m['tip']]
        if not m or not pre or now < m['tip'] + SETTLE_AFTER_S or (games and not games(str(m['game']))):
            continue
        bx = box(root, m['game'])
        if bx is None:
            continue
        meta = box_meta(root, m['game'])
        st = bx.get(int(m['pid']))
        actual = st.get('minutes', 0.0) if st else 0.0
        reason = ''
        if not st:
            reason = 'did not play'
        else:
            sc = meta.get('score') or {}
            if len(sc) == 2:
                margin = abs(list(sc.values())[0] - list(sc.values())[1])
                if margin >= 20:
                    reason = f'blowout ({int(margin)} pts)'
            if st.get('fouls', 0) >= 5:
                reason = f"foul trouble ({int(st['fouls'])} fouls)"
        v3 = pre[-1][2] if len(pre[-1]) > 2 else None
        if m.get('replay'):
            replayed[tip_day(m['tip'])] += 1
        per_day[tip_day(m['tip'])].append([m['player'], m['team'], m['matchup'], round(pre[-1][0], 1), round(actual, 1), reason,
                                           round(v3, 1) if v3 is not None else None, pre[-1][3] if len(pre[-1]) > 3 else 0,
                                           round(pre[-1][4], 1) if len(pre[-1]) > 4 and pre[-1][4] is not None else None])
    for d, rows in per_day.items():
        played = [r for r in rows if r[5] != 'did not play']
        err = [r[3] - r[4] for r in played]
        both = [r for r in played if r[6] is not None]                 # the shadow: v3 on the same players
        e2, e3 = [r[3] - r[4] for r in both], [r[6] - r[4] for r in both]
        gbs = [r for r in played if len(r) > 8 and r[8] is not None]       # the GBM shadow, with v2 on the same players
        eg, e2g = [r[8] - r[4] for r in gbs], [r[3] - r[4] for r in gbs]
        days[d] = {'n': len(played), 'dnp': len(rows) - len(played),
                   'gbm': {'n': len(gbs), 'mae_v2': round(sum(abs(e) for e in e2g) / len(e2g), 3) if e2g else None,
                           'mae_gbm': round(sum(abs(e) for e in eg) / len(eg), 3) if eg else None,
                           'miss8_v2': sum(abs(e) >= 8 for e in e2g), 'miss8_gbm': sum(abs(e) >= 8 for e in eg)},
                   'mae': round(sum(abs(e) for e in err) / len(err), 2) if err else None,
                   'bias': round(sum(err) / len(err), 2) if err else None,
                   'miss8': sum(abs(e) >= 8 for e in err),
                   'v3': {'n': len(both), 'starters': sum(r[7] for r in both),
                          'mae_v2': round(sum(abs(e) for e in e2) / len(e2), 3) if e2 else None,
                          'mae_v3': round(sum(abs(e) for e in e3) / len(e3), 3) if e3 else None,
                          'miss8_v2': sum(abs(e) >= 8 for e in e2), 'miss8_v3': sum(abs(e) >= 8 for e in e3)},
                   'worst': sorted(rows, key=lambda r: -abs(r[3] - r[4]))[:12], **({'replay': replayed[d]} if replayed[d] else {})}
    return days


def cost(venue, price):
    """Probability-scale cost of the side, fee included (what a win must beat)."""
    if venue == 'kalshi':
        return price + PX.k_fee(price)
    if venue == 'pickem' and price is None:
        return PX.PK_BE
    return PX.am_p(price)


def profit(venue, price, won):
    """Per 1 unit risked: a win returns (1 - cost) / cost (the same as American odds for a book price)."""
    if won is None:
        return 0.0
    c = cost(venue, price)
    return (1 - c) / c if won else -1.0


def outcome(side, line, y):
    """True win / False loss / None push."""
    if y == line:
        return None
    over = y > line
    return over if side in ('Over', 'YES') else not over


def load_ledger(root, since=None, src='ledger'):
    """key -> {'meta', 'series': [(t, v)]} across day folders from `since` (YYYY-MM-DD) on; a game can span two.
    Keys are read with the book spelled one way (canon_key): a quote the recorder logged as 'Draft Kings' and later as 'DraftKings'
    is one series, so it is one bet. At the same instant a value beats a 'gone' marker (the old spelling going away as the new one appears)."""
    L = defaultdict(lambda: {'meta': None, 'series': []})
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        if since and os.path.basename(d) < since:
            continue
        mp = os.path.join(d, 'meta.jsonl')
        if os.path.exists(mp):
            for line in open(mp):
                if f'"src":"{src}"' not in line:          # meta.jsonl holds every source; skip the parse
                    continue
                r = json.loads(line)
                m = {k: v for k, v in r.items() if k not in ('k', 'src')}
                if m.get('book'):
                    m['book'] = book_name(m['book'])
                L[canon_key(r['k'])]['meta'] = m
        lp = os.path.join(d, f'{src}.jsonl')
        if os.path.exists(lp):
            for line in open(lp):
                r = json.loads(line)
                L[canon_key(r['k'])]['series'].append((r['t'], r['v']))
    for x in L.values():
        x['series'].sort(key=lambda z: (z[0], z[1] is None))      # a value sorts before a 'gone' marker at the same instant
    return L


def backtest_refs():
    """Each GO / WATCH signal's 2025-26 out-of-sample result, for the page to compare against."""
    import render_app
    return (render_app.pricing() or {}).get('backtest') or {}


EDGE_BINS = [(0.05, '3-5%'), (0.08, '5-8%'), (0.12, '8-12%'), (9, '12%+')]
CUBE_COLS = ['day', 'stat', 'venue', 'book', 'side', 'gate', 'ebin', 'etype', 'bets', 'open', 'void', 'w', 'l', 'p',
             'units', 'units_sq', 'units_close', 'clv_sum', 'clv_n', 'edge_sum']


def family(b):
    """Kalshi / Sportsbooks / Polymarket / Pick'em."""
    return 'kalshi' if b['venue'] == 'kalshi' else 'pickem' if b['venue'] == 'pickem' else 'polymarket' if b['book'] == 'Polymarket' else 'book'


TYPE_COLS = ['type', 'venue', 'stat', 'side', 'bets', 'open', 'w', 'l', 'p', 'units', 'units_sq', 'units_close', 'clv_sum', 'clv_n']


def type_rows(bets):
    """Every bet counted once under each of its edge types (news, stale, ladder, gap, model), all time."""
    agg = {}
    for b in bets:
        side = 'over' if b['side'] in ('Over', 'YES') else 'under'
        for t in b.get('types') or ['model']:
            r = agg.setdefault((t, family(b), b['stat'], side), [0] * 10)
            r[0] += 1
            r[1] += b['result'] == 'open'
            r[2] += b['result'] == 'win'
            r[3] += b['result'] == 'loss'
            r[4] += b['result'] == 'push'
            if b['result'] in ('win', 'loss', 'push'):
                r[5] += b['pnl']
                r[6] += b['pnl'] ** 2
                r[7] += b['pnl_close']
            if b.get('clv') is not None:
                r[8] += b['clv']
                r[9] += 1
    return {k: v for k, v in agg.items()}


def preseason_games(root):
    """Game ids ESPN lists as preseason (season type 1), from season_types.json (snapshot.save_season_types)."""
    try:
        return {g for g, t in json.load(open(os.path.join(root, 'season_types.json'))).items() if t == 1}
    except (OSError, ValueError):
        return set()


def tip_day(ts):
    return et(dt.datetime.fromtimestamp(ts, dt.timezone.utc)).date().isoformat()


def cube_rows(bets):
    """Aggregate bets into cube rows (CUBE_COLS)."""
    agg = {}
    for b in bets:
        ebin = next(l for hi, l in EDGE_BINS if b['edge'] < hi)
        side = 'over' if b['side'] in ('Over', 'YES') else 'under'
        k = (tip_day(b['tip']), b['stat'], family(b), b['book'], side, b['gate'], ebin, b.get('etype', 'model'))
        r = agg.setdefault(k, [0] * 12)
        r[0] += 1
        r[1] += b['result'] == 'open'
        r[2] += b['result'] == 'void'
        r[3] += b['result'] == 'win'
        r[4] += b['result'] == 'loss'
        r[5] += b['result'] == 'push'
        if b['result'] in ('win', 'loss', 'push'):
            r[6] += b['pnl']
            r[7] += b['pnl'] ** 2
            r[8] += b['pnl_close']
        if b.get('clv') is not None:
            r[9] += b['clv']
            r[10] += 1
        r[11] += b['edge']
    return [list(k) + [round(x, 4) if isinstance(x, float) else x for x in v] for k, v in sorted(agg.items())]


GATE_RANK = {'go': 0, 'watch': 1, 'no-go': 2}


def gap_of(v):
    return v[7] if len(v) > 7 else None


def triggers(v):
    """Which edges reached EDGE_MIN in a ledger value: ['model'], ['gap'] or both."""
    return [t for t, x in (('model', v[2]), ('gap', gap_of(v))) if x is not None and x >= PX.EDGE_MIN]


def bet_from(k, m, series):
    """One shadow bet from a ledger key's history, or None if it never reached EDGE_MIN before tip."""
    pre = [(t, v) for t, v in series if v is not None and t < m['tip']]
    ent = next(((t, v) for t, v in pre if triggers(v)), None)
    if not ent:
        return None
    (te, ve), (tc, vc) = ent, pre[-1]
    ce, cc = cost(m['venue'], ve[0]), cost(m['venue'], vc[0])
    trig = triggers(ve)
    gate = min((ve[3] if 'model' in trig else 'no-go', ve[8] if 'gap' in trig else 'no-go'), key=lambda g: GATE_RANK[g])
    etype = 'both' if len(trig) == 2 else trig[0]
    return {'k': k, 'game': m['game'], 'tip': m['tip'], 'matchup': m['matchup'], 'pid': m['pid'], 'player': m['player'],
            'team': m['team'], 'stat': m['stat'], 'venue': m['venue'], 'book': m['book'], 'side': m['side'], 'line': m['line'],
            'gate': gate, 'etype': etype, 't': te, 'price': ve[0], 'fair': ve[1], 'edge': max(ve[2], gap_of(ve) or -1) if 'gap' in trig else ve[2],
            'model_edge': ve[2], 'cons': ve[6] if len(ve) > 6 else None, 'gap_edge': gap_of(ve), 'mu': ve[4], 'min': ve[5],
            'types': [x for x in (ve[9] if len(ve) > 9 else '').split(',') if x] or [{'model': 'model', 'gap': 'gap', 'both': 'gap'}[etype]],
            't_close': tc, 'price_close': vc[0], 'fair_close': vc[1], 'edge_close': vc[2],
            'clv': round(cc - ce, 4) if ce is not None and cc is not None else None,
            'result': 'open', 'actual': None, 'pnl': None, 'pnl_close': None, **({'replay': 1} if m.get('replay') else {})}      # replay: replayed from stored prices, not logged live


def grade(b, root, now):
    """Settle an open bet in place once its game is final."""
    if b['result'] != 'open' or now < b['tip'] + SETTLE_AFTER_S:
        return
    bx = box(root, b['game'])
    if bx is None:
        return
    st = bx.get(int(b['pid']))
    if st is None:
        b['result'] = 'void'
        return
    y = sum(st.get(c, 0) for c in STAT_COL[b['stat']])
    won = outcome(b['side'], float(b['line']), y)
    b.update(actual=y, result='push' if won is None else 'win' if won else 'loss',
             pnl=round(profit(b['venue'], b['price'], won), 4), pnl_close=round(profit(b['venue'], b['price_close'], won), 4))


def canon_bet(b):
    """A stored bet with its book spelled one way (and the key to match)."""
    bk = book_name(b.get('book'))
    return b if bk == b.get('book') else dict(b, book=bk, k=canon_key(b['k']))


def dedupe_bets(bets):
    """key -> bet for stored bets, books spelled one way. Two bets with the same canonical key are one quote the recorder logged under
    two spellings of its book: keep the earlier entry, and a result if either one was already settled."""
    out = {}
    for b in map(canon_bet, bets):
        o = out.get(b['k'])
        if o is None:
            out[b['k']] = b
            continue
        keep, other = (o, b) if o['t'] <= b['t'] else (b, o)
        if keep['result'] == 'open' and other['result'] != 'open':
            keep = dict(keep, **{f: other[f] for f in ('result', 'actual', 'pnl', 'pnl_close')})
        out[b['k']] = keep
    return out


def canon_cube(rows):
    """Cube rows with the book spelled one way, rows that now share a key added together."""
    ib, ncol = CUBE_COLS.index('book'), CUBE_COLS.index('bets')
    agg = {}
    for r in rows:
        r = list(r)
        r[ib] = book_name(r[ib])
        k = tuple(r[:ncol])
        if k in agg:
            agg[k] = [a + b if i >= ncol else a for i, (a, b) in enumerate(zip(agg[k], r))]
        else:
            agg[k] = r
    return sorted([[round(x, 4) if isinstance(x, float) else x for x in r] for r in agg.values()])


HELD_BETS_KEEP_DAYS = 14        # bet rows are kept for this many tip days; older days keep only their sums


def held_bets_record(root, now, prev, rescan_days, games):
    """Per tip day: the GO and WATCH candidates a hold (the roster guard, mostly) kept out of the bets, settled as if they had been logged.

    ledger.log never logs a held candidate, so on opening night 2026-10-20, when the guard held all six teams, the Kalshi 3PM NO cell (GO) and the
    PTS / REB / AST YES cells (WATCH) had 3%+ edges that the Props page priced and the Track Record never saw. They are recorded apart (source 'heldbets',
    log() -> HELD_OUT), entered at the first poll the edge reached 3% (the price a live bettor could have taken, the same rule as a bet), closed at the last
    poll before tip, and settled from the box score exactly like bet_from / grade. This is NOT a bet record: it never reaches the cube, the season record, the GO /
    WATCH verdicts or a signal's 50-bet promotion count (none of those read it). One unit each, so units are what the price would have paid.
    Row: [player, team, stat, family, side, line, gate, price, model fair, edge, actual or null, 'W'|'L'|'P'|'V' (void), pnl at entry, why held]."""
    days = dict(prev or {})
    since = tip_day(now - rescan_days * 86400)
    G = {}
    for k, x in load_ledger(root, since, 'heldbets').items():
        if not (x['meta'] and x['series']) or (games and not games(str(x['meta']['game']))):
            continue
        b = bet_from(k, x['meta'], x['series'])
        if not b or b['gate'] == 'no-go' or now < b['tip'] + SETTLE_AFTER_S:
            continue
        b['hold'] = x['meta'].get('hold')
        G.setdefault(b['game'], []).append(b)
    per_day = {}
    for gid, bs in G.items():
        if box(root, gid) is None:
            continue
        sc = (box_meta(root, gid).get('score')) or {}
        tot = {'n': 0, 'W': 0, 'L': 0, 'P': 0, 'V': 0, 'units': 0.0, 'units_close': 0.0, 'pe_price': 0.0, 'pe_model': 0.0, 'pv': 0.0, 'goW': 0, 'goL': 0, 'wW': 0, 'wL': 0}
        rows = []
        for b in sorted(bs, key=lambda b: (b['team'], b['player'], b['stat'], b['side'], b['line'], b['book'])):
            grade(b, root, now)
            res = {'win': 'W', 'loss': 'L', 'push': 'P', 'void': 'V'}.get(b['result'])
            if res is None:
                continue
            tot['n'] += 1
            tot[res] += 1
            c = cost(b['venue'], b['price'])
            if res in ('W', 'L'):
                tot[('go' if b['gate'] == 'go' else 'w') + res] += 1
                tot['units'] += b['pnl']
                tot['units_close'] += b['pnl_close']
                if c is not None:
                    tot['pe_price'] += c
                    tot['pe_model'] += b['fair']
                    tot['pv'] += c * (1 - c)
            elif res == 'P':
                pass
            rows.append([b['player'], b['team'], b['stat'], family(b), 'o' if b['side'] in ('Over', 'YES') else 'u', b['line'], b['gate'], b['price'], b['fair'], round(b['edge'], 4),
                         b['actual'], res, b['pnl'], b['hold']])
        if not rows:
            continue
        b0 = bs[0]
        tot['picks'] = len({(r[0], r[2], r[4]) for r in rows})      # a Kalshi ladder gives several rungs of one pick: bets are rungs, picks are player, stat and side
        entry = {'game': gid, 'matchup': b0['matchup'], 'tip': b0['tip'], 'sum': {k: round(v, 3) if isinstance(v, float) else v for k, v in tot.items()}, 'rows': rows}
        if any(b.get('replay') for b in bs):
            entry['replay'] = 1                          # replayed from stored prices after the fact (replay_polls.py), not logged live
        per_day.setdefault(tip_day(b0['tip']), []).append(entry)
    for d, gs in per_day.items():
        days[d] = sorted(gs, key=lambda g: g['tip'])
    keep = tip_day(now - HELD_BETS_KEEP_DAYS * 86400)
    for d in days:
        if d < keep:
            days[d] = [{k: v for k, v in g.items() if k != 'rows'} for g in days[d]]
    return days


STUCK = []     # games that tipped STUCK_H or more ago with no final box score (or bets still open): [{game, matchup, tip, open}], from the last settle()


def stuck_games(root, now, tips, changed):
    """Games well past their finish that settle() could not close: no results file (ESPN has not marked them final, or the box never filled in),
    or bets still open. A normal game ends about 3 hours after tip, so STUCK_H hours is an overtime, a delay or a break in the feed, and a person has to look."""
    open_by, seen = defaultdict(int), {}
    for bs in changed.values():
        for b in bs:
            if b['result'] == 'open' and now >= b['tip'] + STUCK_H * 3600:
                open_by[str(b['game'])] += 1
                seen[str(b['game'])] = (b['tip'], b['matchup'])
    out = []
    for gid in sorted(set(open_by) | {g for g, (tip, _) in tips.items() if now >= tip + STUCK_H * 3600}):
        tip, matchup = tips.get(gid) or seen.get(gid)
        if not os.path.exists(os.path.join(root, 'results', f'{gid}.json')) or open_by.get(gid):
            out.append({'game': gid, 'matchup': matchup, 'tip': tip, 'open': open_by.get(gid, 0)})
    return out


def settle(root, now=None, rescan_days=3, keep_recent=600):
    """Settle what is settleable; rewrite bets/<day>.json for the days touched and their cube rows in track.json.
    Only the last `rescan_days` of ledger folders are re-read (a key is logged within TRACK_H of its tip), plus the
    bet files of those days and of any day that still has open bets. Returns the number of bets in the record."""
    now = now or int(time.time())
    SETTLE_ERR.clear()
    tpath, bdir = os.path.join(root, 'track.json'), os.path.join(root, 'bets')
    track = json.load(open(tpath)) if os.path.exists(tpath) else {}
    if 'cube' not in track:                       # the first format kept every bet in track.json: move them to files
        old = track.get('bets') or []
        track = {'cube': [], 'open_days': sorted({tip_day(b['tip']) for b in old}), 'n': 0}
        for d in track['open_days']:
            os.makedirs(bdir, exist_ok=True)
            json.dump([b for b in old if tip_day(b['tip']) == d], open(os.path.join(bdir, f'{d}.json'), 'w'), separators=(',', ':'))
    since = tip_day(now - rescan_days * 86400)
    tips, corrected = {}, set()
    try:                                          # ESPN corrects box scores after the final: re-read the recent ones, re-grade what a correction changes
        tips = game_tips(root, since)
        corrected = refresh_boxes(root, now, tips)
    except Exception as e:
        SETTLE_ERR['box refresh'] = f'{type(e).__name__}: {e}'[:120]
        print('box refresh failed:', e, flush=True)
    fresh = {}
    for k, x in load_ledger(root, since).items():
        if x['meta'] and x['series']:
            b = bet_from(k, x['meta'], x['series'])
            if b:
                fresh[k] = b
    days = {tip_day(b['tip']) for b in fresh.values()} | set(track.get('open_days') or [])
    changed = {}
    for d in sorted(days):
        path = os.path.join(bdir, f'{d}.json')
        prev = dedupe_bets(json.load(open(path)) if os.path.exists(path) else [])
        cur = dict(prev)
        for k, b in fresh.items():
            if tip_day(b['tip']) != d:
                continue
            old = prev.get(k)
            if old and old['t'] < b['t']:              # entry logged before the rescan window: keep it
                b.update({f: old[f] for f in ('t', 'price', 'fair', 'edge', 'gate', 'mu', 'min')})
                ce, cc = cost(b['venue'], b['price']), cost(b['venue'], b['price_close'])
                b['clv'] = round(cc - ce, 4) if ce is not None and cc is not None else None
            if old and old['result'] != 'open':
                b.update({f: old[f] for f in ('result', 'actual', 'pnl', 'pnl_close')})
            cur[k] = b
        for b in cur.values():
            if b['game'] in corrected and b['result'] != 'open':       # its box score changed: grade it again from the corrected numbers
                b.update(result='open', actual=None, pnl=None, pnl_close=None)
            grade(b, root, now)
        changed[d] = sorted(cur.values(), key=lambda b: (b['tip'], b['player'], b['stat'], b['line']))
    os.makedirs(bdir, exist_ok=True)
    PRE = preseason_games(root)
    season = lambda gid: str(gid) not in PRE
    for d, bs in changed.items():
        for b in bs:
            b['pre'] = not season(b['game'])
        json.dump(bs, open(os.path.join(bdir, f'{d}.json'), 'w'), separators=(',', ':'))
    reg = {d: [b for b in bs if not b['pre']] for d, bs in changed.items()}
    cube = canon_cube([r for r in track.get('cube', []) if r[0] not in changed])
    for bs in reg.values():
        cube += cube_rows(bs)
    cube.sort()
    P0 = track.get('preseason') or {}             # the rehearsal: same records, kept apart
    pcube = canon_cube([r for r in P0.get('cube', []) if r[0] not in changed] +
                       [r for d, bs in changed.items() for r in cube_rows([b for b in bs if b['pre']])])
    # edge-type totals: kept per tip day so only the days touched are recomputed
    tday = {d: v for d, v in (track.get('types_by_day') or {}).items() if d not in changed}
    for d, bs in reg.items():
        tday[d] = [list(k) + [round(x, 4) if isinstance(x, float) else x for x in v] for k, v in type_rows(bs).items()]
    tot = {}
    for rows in tday.values():
        for r in rows:
            t = tot.setdefault(tuple(r[:4]), [0] * 10)
            for i, x in enumerate(r[4:]):
                t[i] += x
    types = [list(k) + [round(x, 4) if isinstance(x, float) else x for x in v] for k, v in sorted(tot.items())]
    recent = dedupe_bets([b for b in track.get('bets', []) if not b.get('pre')])
    for bs in reg.values():
        recent.update({b['k']: b for b in bs})
    recent = sorted(recent.values(), key=lambda b: (b['tip'], b['player'], b['stat'], b['line']))[-keep_recent:]
    open_days = sorted(d for d, bs in changed.items() if any(b['result'] == 'open' for b in bs))
    n = sum(r[CUBE_COLS.index('bets')] for r in cube)
    minutes_days = minutes_record(root, now, track.get('minutes_days'), rescan_days, games=season)
    wire_days = wire_record(root, now, track.get('wire_days'), rescan_days, games=season)
    me = sys.modules[__name__]
    try:                                          # how the Game Simulation did, game by game (sim_record.py); a failure here never stops settling
        import sim_record as SR
        sim_days = SR.record(root, now, track.get('sim_days'), rescan_days, season, me)
        sim_pre = SR.record(root, now, (track.get('preseason') or {}).get('sim_days'), rescan_days, lambda g: not season(g), me)
    except Exception as e:
        SETTLE_ERR['game simulation record'] = f'{type(e).__name__}: {e}'[:120]
        print('sim record failed:', e, flush=True)
        sim_days, sim_pre = track.get('sim_days'), (track.get('preseason') or {}).get('sim_days')
    try:                                          # single-prop simulations vs the minutes model, settled from the box score (prop_sim_record.py)
        import prop_sim_record as PSR
        psim_days, gap_days = PSR.record_all(root, now, track.get('psim_days'), track.get('gap_days'), rescan_days, season, me)
        psim_pre, gap_pre = PSR.record_all(root, now, (track.get('preseason') or {}).get('psim_days'), (track.get('preseason') or {}).get('gap_days'), rescan_days, lambda g: not season(g), me)
    except Exception as e:
        SETTLE_ERR['props simulation record'] = f'{type(e).__name__}: {e}'[:120]
        print('prop sim record failed:', e, flush=True)
        psim_days, psim_pre = track.get('psim_days'), (track.get('preseason') or {}).get('psim_days')
        gap_days, gap_pre = track.get('gap_days'), (track.get('preseason') or {}).get('gap_days')
    try:                                          # Pick'em of the Night: every slip of every size, settled from the box score (pickem_record.py)
        import pickem_record as PKR
        pkn_days = PKR.record(root, now, track.get('pkn_days'), rescan_days, season, me)
        pkn_pre = PKR.record(root, now, (track.get('preseason') or {}).get('pkn_days'), rescan_days, lambda g: not season(g), me)
    except Exception as e:
        SETTLE_ERR["pick'em record"] = f'{type(e).__name__}: {e}'[:120]
        print('pickem record failed:', e, flush=True)
        pkn_days, pkn_pre = track.get('pkn_days'), (track.get('preseason') or {}).get('pkn_days')
    try:                                          # props the roster guard held, settled as a group of their own (never bets, never in the season record)
        held_days = PSR.record_held(root, now, track.get('held_days'), rescan_days, season, me)
        held_pre = PSR.record_held(root, now, (track.get('preseason') or {}).get('held_days'), rescan_days, lambda g: not season(g), me)
    except Exception as e:
        SETTLE_ERR['held props record'] = f'{type(e).__name__}: {e}'[:120]
        print('held record failed:', e, flush=True)
        held_days, held_pre = track.get('held_days'), (track.get('preseason') or {}).get('held_days')
    try:                                          # the GO / WATCH candidates a hold kept out, settled as if logged (never in the cube or the season record)
        held_bets_days = held_bets_record(root, now, track.get('held_bets_days'), rescan_days, season)
    except Exception as e:
        SETTLE_ERR['held plays record'] = f'{type(e).__name__}: {e}'[:120]
        print('held bets record failed:', e, flush=True)
        held_bets_days = track.get('held_bets_days')
    try:                                          # Novig paper trading, settled from the box score (novig_paper.py)
        import novig_paper as NPT
        novig_days = NPT.record(root, now, track.get('novig_days'), rescan_days, season, me)
        novig_pre = NPT.record(root, now, (track.get('preseason') or {}).get('novig_days'), rescan_days, lambda g: not season(g), me)
    except Exception as e:
        SETTLE_ERR['novig paper record'] = f'{type(e).__name__}: {e}'[:120]
        print('novig paper record failed:', e, flush=True)
        novig_days, novig_pre = track.get('novig_days'), (track.get('preseason') or {}).get('novig_days')
    pre = {'n': sum(r[CUBE_COLS.index('bets')] for r in pcube), 'cube': pcube,
           'minutes_days': minutes_record(root, now, P0.get('minutes_days'), rescan_days, games=lambda g: not season(g)),
           'wire_days': wire_record(root, now, P0.get('wire_days'), rescan_days, games=lambda g: not season(g)),
           'signals': P0.get('signals'), 'sim_days': sim_pre, 'psim_days': psim_pre, 'gap_days': gap_pre, 'held_days': held_pre, 'novig_days': novig_pre, 'pkn_days': pkn_pre}
    try:                                          # closing prices + box lines for users' own bet logs
        closes_record(root, now, rescan_days, corrected={str(g) for g in corrected})
    except Exception as e:
        SETTLE_ERR['closing prices'] = f'{type(e).__name__}: {e}'[:120]
        print('closes record failed:', e, flush=True)
    try:                                          # Sharp Price signals: CLV vs Pinnacle's close, and the final score
        import sharp
        stat_of = lambda bx, pid, stat: (sum(bx[int(pid)].get(c, 0) for c in STAT_COL[stat]) if bx.get(int(pid)) else None)
        signals = sharp.grade_signals(root, now, track.get('signals'), box, box_meta, stat_of=stat_of, games=season)
        pre['signals'] = sharp.grade_signals(root, now, P0.get('signals'), box, box_meta, stat_of=stat_of, games=lambda g: not season(g))
    except Exception as e:
        SETTLE_ERR['signals grading'] = f'{type(e).__name__}: {e}'[:120]
        print('signals grading failed:', e, flush=True)
        signals = track.get('signals')
    box_changes = (list(BOX_CHANGES) + (track.get('box_changes') or []))[:BOX_CHANGES_KEEP]
    STUCK[:] = stuck_games(root, now, tips, changed)
    track = {'t': now, 'edge_min': PX.EDGE_MIN, 'pk_be': PX.PK_BE, 'n': n, 'cube_cols': CUBE_COLS, 'cube': cube, 'minutes_days': minutes_days, 'wire_days': wire_days, 'pkn_days': pkn_days, 'sim_days': sim_days, 'psim_days': psim_days, 'gap_days': gap_days, 'held_days': held_days, 'held_bets_days': held_bets_days, 'novig_days': novig_days, 'novig_cfg': {'fee': NPT_CFG[0], 'edge': NPT_CFG[1], 'stake': NPT_CFG[2]}, 'signals': signals,
             'type_cols': TYPE_COLS, 'types': types, 'types_by_day': tday,
             'open_days': open_days, 'bets': recent, 'backtest': backtest_refs(), 'preseason': pre, 'box_changes': box_changes}
    with open(tpath, 'w') as f:
        json.dump(track, f, separators=(',', ':'))
    return n
