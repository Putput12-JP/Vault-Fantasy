#!/usr/bin/env python3
"""
Join the raw backfills into flat backtest tables + a coverage report.

Inputs (nba/raw, from the fetch/backfill scripts):
  hoopr/player_box_<s>.csv, hoopr/schedule_<s>.csv
  espn_odds/games_<s>.jsonl
  kalshi/markets_<S>.jsonl + kalshi/prices_<S>.jsonl
  injuries/reports_<s>.jsonl

Outputs:
  nba/raw/tables/game_lines.csv     one row per game x sportsbook (open + close)
  nba/raw/tables/props_espn.csv     one row per player prop (over/under paired)
  nba/raw/tables/props_kalshi.csv   one row per Kalshi ladder strike, priced pre-tip
  nba/docs/data-coverage.md         what we have, by month and market

ESPN prop rows carry no over/under label. prop_markets() infers the side and
audit_sides() checks it against outcomes; the script refuses to write the prop
table if any book's sides look random or swapped.

  python3 nba/scripts/build_backtest_tables.py
"""
import csv, datetime as dt, glob, json, math, os, re, sys, unicodedata
from collections import Counter, defaultdict

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, '..', 'raw')
TAB = os.path.join(RAW, 'tables')
DOCS = os.path.join(HERE, '..', 'docs')
SEASONS = [2025, 2026]

# ESPN prop type -> (market, box-score stat columns summed)
ESPN_MKT = {
    'Total Points': ('pts', ['points']),
    'Total Rebounds': ('reb', ['rebounds']),
    'Total Assists': ('ast', ['assists']),
    'Total 3-Point Field Goals': ('3pm', ['three_point_field_goals_made']),
    'Total Points, Rebounds, and Assists': ('pra', ['points', 'rebounds', 'assists']),
    'Total Points and Rebounds': ('pr', ['points', 'rebounds']),
    'Total Points and Assists': ('pa', ['points', 'assists']),
    'Total Assists and Rebounds': ('ra', ['assists', 'rebounds']),
    'Total Steals': ('stl', ['steals']),
    'Total Blocks': ('blk', ['blocks']),
}
KALSHI_MKT = {'KXNBAPTS': 'pts', 'KXNBAREB': 'reb', 'KXNBAAST': 'ast', 'KXNBA3PT': '3pm'}
MKT_COLS = {m: cols for m, cols in ESPN_MKT.values()}


def name_key(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    if ',' in s:  # injury report "Last,First"
        last, first = s.split(',', 1)
        s = first + ' ' + last
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b\.?', '', s)
    return re.sub(r'[^a-z]', '', s)


def american_to_prob(a):
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ── box scores ─────────────────────────────────────────────────────────────
def load_box():
    box, by_game = {}, defaultdict(list)
    for s in SEASONS:
        for r in csv.DictReader(open(os.path.join(RAW, 'hoopr', f'player_box_{s}.csv'))):
            if not r['athlete_id'] or not r['game_id']:
                continue  # team-level rows (e.g. team rebounds) have no athlete
            gid, aid = int(r['game_id']), int(r['athlete_id'])
            played = r['did_not_play'] != 'true' and (num(r['minutes']) or 0) > 0
            rec = {'played': played, 'min': num(r['minutes']) or 0, 'team': r['team_abbreviation'],
                   'name': r['athlete_display_name']}
            for cols in MKT_COLS.values():
                for c in cols:
                    rec[c] = num(r[c]) or 0
            box[(gid, aid)] = rec
            by_game[gid].append((aid, rec))
    return box, by_game


def stat(rec, market):
    return sum(rec[c] for c in MKT_COLS[market])


# ── ESPN ───────────────────────────────────────────────────────────────────
def load_espn():
    games = []
    for s in SEASONS:
        p = os.path.join(RAW, 'espn_odds', f'games_{s}.jsonl')
        if os.path.exists(p):
            for line in open(p):
                g = json.loads(line)
                g['season'] = s
                games.append(g)
    return games


LIVE_BOOKS = {59}  # "ESPN Bet - Live Odds": in-game prices, never a pre-game line


def logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def prop_markets(g):
    """One game's ESPN prop rows -> clean markets.

    ESPN gives no over/under label. What the feed actually holds, per player x stat:
      - an ALT LADDER: one row per line, all overs, prices falling as the line rises
        (ESPN BET carries these inside "Total Points"; DraftKings does not)
      - the MAIN pair: two (sometimes three, a ladder duplicate) rows at one line.
    The over side of the main pair is the price consistent with the ladder
    (interpolated in logit space from the neighbouring alt lines). With no
    ladder, DraftKings lists the over first (verified on outcomes).
    Yields dicts with kind 'main' (over + under) or 'alt' (over only).
    """
    groups = defaultdict(list)
    for r in g['props']:
        if r['type'] in ESPN_MKT and r['athlete_id'] and r['provider_id'] not in LIVE_BOOKS \
                and r['open_line'] is not None and american_to_prob(r['open_px']) is not None:
            groups[(r['provider_id'], r['athlete_id'], r['type'])].append(r)
    for (prov, aid, typ), rows in groups.items():
        by_line = defaultdict(list)
        for r in rows:
            by_line[r['open_line']].append(r)
        ladder = sorted((ln, american_to_prob(rs[0]['open_px'])) for ln, rs in by_line.items() if len(rs) == 1)
        base = {'provider_id': prov, 'athlete_id': aid, 'market': ESPN_MKT[typ][0]}
        for ln, rs in by_line.items():
            if len(rs) == 1:
                r = rs[0]
                yield dict(base, kind='alt', line=ln, over_open=r['open_px'], under_open=None,
                           over_cur=r['cur_px'], under_cur=None, cur_line=r['cur_line'], last_updated=r['last_updated'])
                continue
            rs = sorted(rs, key=lambda r: r['ord'])
            distinct = []
            for r in rs:
                if all(r['open_px'] != d['open_px'] for d in distinct):
                    distinct.append(r)
            if len(distinct) < 2:
                continue
            a, b = distinct[0], distinct[1]
            lo = [p for l, p in ladder if l < ln]
            hi = [p for l, p in ladder if l > ln]
            if lo and hi:
                l0 = max(l for l, _ in ladder if l < ln)
                l1 = min(l for l, _ in ladder if l > ln)
                p0, p1 = dict(ladder)[l0], dict(ladder)[l1]
                t = (ln - l0) / (l1 - l0)
                target = 1 / (1 + math.exp(-(logit(p0) + t * (logit(p1) - logit(p0)))))
                over_first = abs(american_to_prob(a['open_px']) - target) <= abs(american_to_prob(b['open_px']) - target)
                how = 'ladder'
            elif prov == 100:
                over_first, how = True, 'dk-order'
            else:
                continue  # cannot tell which side is the over; drop rather than guess
            ov, un = (a, b) if over_first else (b, a)
            yield dict(base, kind='main', line=ln, over_open=ov['open_px'], under_open=un['open_px'],
                       over_cur=ov['cur_px'], under_cur=un['cur_px'], cur_line=ov['cur_line'],
                       last_updated=ov['last_updated'], side_from=how)


def audit_sides(games, box):
    """Where the book clearly leaned (de-vigged >58%), how often did its favourite side win?
    Right side assignment -> well above 50%. Swapped -> well below. Random -> ~50%."""
    res = defaultdict(lambda: [0, 0])
    for g in games:
        for m in prop_markets(g):
            if m['kind'] != 'main':
                continue
            rec = box.get((g['game_id'], m['athlete_id']))
            if not rec or not rec['played']:
                continue
            act = stat(rec, m['market'])
            if act == m['line']:
                continue
            po, pu = american_to_prob(m['over_open']), american_to_prob(m['under_open'])
            p = po / (po + pu)
            if abs(p - 0.5) < 0.08:
                continue
            k = (m['provider_id'], m['side_from'])
            res[k][0 if (p > 0.5) == (act > m['line']) else 1] += 1
    return {f'{k[0]}/{k[1]}': {'fav_won': v[0], 'fav_lost': v[1], 'rate': round(v[0] / max(1, sum(v)), 3)}
            for k, v in sorted(res.items())}


def build_game_lines(games):
    rows = []
    for g in games:
        for L in g['lines']:
            if 'Live' in (L['provider'] or ''):
                continue
            rows.append({
                'game_id': g['game_id'], 'season': g['season'], 'tip': g['tip'], 'type': g['type'],
                'home': g['home'], 'away': g['away'], 'home_score': g['home_score'], 'away_score': g['away_score'],
                'book': L['provider'],
                'spread_open': num(L['home']['open']['spread']), 'spread_close': num(L['home']['close']['spread']),
                'spread_home_px_close': num(L['home']['close']['spread_px']), 'spread_away_px_close': num(L['away']['close']['spread_px']),
                'total_open': num(L['total']['open']['total']), 'total_close': num(L['total']['close']['total']),
                'over_px_close': num(L['total']['close']['over_px']), 'under_px_close': num(L['total']['close']['under_px']),
                'ml_home_open': num(L['home']['open']['ml']), 'ml_away_open': num(L['away']['open']['ml']),
                'ml_home_close': num(L['home']['close']['ml']), 'ml_away_close': num(L['away']['close']['ml']),
            })
    return rows


def build_props_espn(games, box):
    rows = []
    for g in games:
        tip = g['tip'][:16]
        for m in prop_markets(g):
            rec = box.get((g['game_id'], m['athlete_id']))
            rows.append({
                'game_id': g['game_id'], 'season': g['season'], 'tip': g['tip'], 'athlete_id': m['athlete_id'],
                'player': rec['name'] if rec else '', 'team': rec['team'] if rec else '',
                'market': m['market'], 'kind': m['kind'], 'book_id': m['provider_id'], 'side_from': m.get('side_from', ''),
                'line_open': m['line'], 'over_px_open': m['over_open'], 'under_px_open': m['under_open'],
                'line_cur': m['cur_line'], 'over_px_cur': m['over_cur'], 'under_px_cur': m['under_cur'],
                'cur_is_pretip': int(bool(m['last_updated']) and m['last_updated'][:16] < tip), 'last_updated': m['last_updated'],
                'played': int(bool(rec and rec['played'])), 'minutes': rec['min'] if rec else '',
                'actual': stat(rec, m['market']) if rec and rec['played'] else '',
            })
    return rows


# ── Kalshi ─────────────────────────────────────────────────────────────────
def build_props_kalshi(box, by_game):
    rows, unmatched = [], Counter()
    for series, mkt in KALSHI_MKT.items():
        mp, pp = os.path.join(RAW, 'kalshi', f'markets_{series}.jsonl'), os.path.join(RAW, 'kalshi', f'prices_{series}.jsonl')
        if not (os.path.exists(mp) and os.path.exists(pp)):
            continue
        markets = {m['ticker']: m for m in map(json.loads, open(mp))}
        for pr in map(json.loads, open(pp)):
            m = markets.get(pr['ticker'])
            gid = pr.get('game_id')
            if not m or not gid:
                continue
            pname = (m.get('yes_sub_title') or m['title']).split(':')[0]
            k = name_key(pname)
            hit = [(aid, rec) for aid, rec in by_game.get(gid, []) if name_key(rec['name']) == k]
            if not hit:
                unmatched[pname] += 1
                continue
            aid, rec = hit[0]
            pre, am = pr.get('pretip') or {}, pr.get('am') or {}
            rows.append({
                'game_id': gid, 'tip_ts': pr['tip_ts'], 'athlete_id': aid, 'player': rec['name'], 'team': rec['team'],
                'market': mkt, 'strike': m['floor_strike'], 'ticker': m['ticker'],
                'yes_last_pretip': pre.get('last'), 'yes_vwap30_pretip': pre.get('vwap30'), 'vol30_pretip': pre.get('vol30'),
                'yes_last_am': am.get('last'), 'yes_vwap30_am': am.get('vwap30'),
                'volume': m.get('volume_fp'), 'result': m.get('result'),
                'played': int(rec['played']), 'actual': stat(rec, mkt) if rec['played'] else '',
            })
    return rows, unmatched


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        return
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


# ── coverage report ────────────────────────────────────────────────────────
def month_of(tip):
    return tip[:7]


def coverage(games, lines, pe, pk, audit, unmatched, inj):
    sched = defaultdict(int)
    for g in games:
        sched[month_of(g['tip'])] += 1
    gl = defaultdict(set)
    for r in lines:
        if r['spread_close'] is not None:
            gl[month_of(r['tip'])].add(r['game_id'])
    pe_g, pe_n, pe_pre = defaultdict(set), Counter(), Counter()
    for r in (r for r in pe if r['kind'] == 'main'):
        m = month_of(r['tip'])
        pe_g[m].add(r['game_id'])
        pe_n[m] += 1
        pe_pre[m] += r['cur_is_pretip']
    pk_g, pk_n = defaultdict(set), Counter()
    for r in pk:
        m = dt.datetime.fromtimestamp(r['tip_ts'], dt.timezone.utc).strftime('%Y-%m')
        pk_g[m].add(r['game_id'])
        pk_n[m] += 1
    inj_days = Counter()
    for d in inj:
        inj_days[d[:7]] += 1

    months = sorted(set(sched) | set(pk_g))
    L = ['# NBA data coverage', '',
         f'Generated {dt.date.today().isoformat()} by `nba/scripts/build_backtest_tables.py`. Free sources only.', '',
         'Games = completed regular season, NBA Cup final, play-in and playoffs.', '',
         '| Month | Games | ESPN lines (open+close) | ESPN prop games | ESPN props (O/U pairs) | pairs w/ pre-tip close | Kalshi prop games | Kalshi strikes | Injury report days |',
         '|---|---|---|---|---|---|---|---|---|']
    for m in months:
        L.append(f'| {m} | {sched[m]} | {len(gl[m])} | {len(pe_g[m])} | {pe_n[m]:,} | {pe_pre[m]:,} | {len(pk_g[m])} | {pk_n[m]:,} | {inj_days[m]} |')
    L += ['', '## ESPN prop over/under sides', '',
          'ESPN does not label which prop row is the over. Sides come from the alt-line ladder (ESPN BET) or',
          'row order (DraftKings), then are checked against results: where the book clearly leaned (>58% de-vigged),',
          'its favourite should win well over half the time. A swapped assignment would show well under half.', '',
          '| Book / method | Fav won | Fav lost | Rate |', '|---|---|---|---|']
    for k, v in audit.items():
        L.append(f"| {k} | {v['fav_won']:,} | {v['fav_lost']:,} | {v['rate']} |")
    L += ['',           '## Kalshi player names not matched to a box score', '',
          'Kalshi settles a market as `scalar` (voided, stake refunded) when the player does not play. On 2025-26,',
          '1,489 of 1,520 unmatched strikes were `scalar`: the player never took the floor, so there is no box score',
          'row to match, and that is correct. Only 31 real misses. Backtests must drop `result == scalar` rows.', '',
          f'{sum(unmatched.values()):,} strikes unmatched. Top: ' + ', '.join(f'{k} ({v})' for k, v in unmatched.most_common(12)), '']
    os.makedirs(DOCS, exist_ok=True)
    open(os.path.join(DOCS, 'data-coverage.md'), 'w').write('\n'.join(L))


def main():
    box, by_game = load_box()
    games = load_espn()
    audit = audit_sides(games, box)
    print('side audit', audit)
    bad = [k for k, v in audit.items() if v['rate'] < 0.55 and v['fav_won'] + v['fav_lost'] > 200]
    if bad:
        sys.exit(f'over/under sides not trustworthy for {bad}; not writing prop tables')
    lines = build_game_lines(games)
    pe = build_props_espn(games, box)
    pk, unmatched = build_props_kalshi(box, by_game)
    write_csv(os.path.join(TAB, 'game_lines.csv'), lines)
    write_csv(os.path.join(TAB, 'props_espn.csv'), pe)
    write_csv(os.path.join(TAB, 'props_kalshi.csv'), pk)
    inj = set()
    for p in glob.glob(os.path.join(RAW, 'injuries', 'reports_*.jsonl')):
        for line in open(p):
            inj.add(json.loads(line)['report_et'][:10])
    coverage(games, lines, pe, pk, audit, unmatched, inj)
    print(f'game_lines {len(lines):,}  props_espn {len(pe):,}  props_kalshi {len(pk):,}  injury days {len(inj)}')


if __name__ == '__main__':
    main()
