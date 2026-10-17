"""Shared loaders for the SmartStake backtests (smartstake_book_weights.py, smartstake_alt_ladders.py).

LOCAL RESEARCH ONLY. SmartStake's terms allow internal research and backtests; nothing derived from the tape may be
committed, published or shown in a UI without written permission. Every output lands under data/smartstake/ (gitignored).

  tape_close(league)   the last pre-start quote per (event, player, stat, book, line, side, alternate)
  resolve_games(...)   tape event -> ESPN game id, through the recorder's propclose.json (origin/nba-data)
  settled(gid)         ESPN box score for a finished game, or None while it has not landed (forward-only)
  pinnacle_close(...)  the recorder's Pinnacle player-prop series, last pre-tip over/under pair per player-stat
"""
import csv, glob, gzip, json, os, subprocess, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from smartstake_to_book_tape import abbr   # noqa: E402

NBA_DATA = os.environ.get('NBA_DATA_REF', 'origin/nba-data')     # git ref holding snapshots/ and results/ (git fetch to refresh)
STAT = {'points': 'pts', 'rebounds': 'reb', 'assists': 'ast', 'made_threes': '3pm', 'points_rebounds_assists': 'pra',
        'points_rebounds': 'pr', 'points_assists': 'pa', 'rebounds_assists': 'ra'}
PIN_STAT = {'Total Points': 'pts', 'Total Rebounds': 'reb', 'Total Assists': 'ast', 'Total Threes Made': '3pm',
            'Total Pts & Rebs & Asts': 'pra'}
BOX = {'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists'], '3pm': ['threePointFieldGoalsMade'],
       'pra': ['points', 'rebounds', 'assists'], 'pr': ['points', 'rebounds'], 'pa': ['points', 'assists'], 'ra': ['rebounds', 'assists']}
EXCHANGES = {'kalshi', 'polymarket', 'novig', 'prophetx'}
BOOK_NAME = {'draftkings': 'DraftKings', 'fanduel': 'FanDuel', 'betmgm': 'BetMGM', 'caesars': 'Caesars', 'fanatics': 'Fanatics',
             'parlayplay': 'ParlayPlay', 'betrivers': 'BetRivers', 'bet365': 'bet365', 'circa': 'Circa', 'bookmaker': 'Bookmaker',
             'prophetx': 'ProphetX', 'novig': 'Novig', 'kalshi': 'Kalshi', 'polymarket': 'Polymarket', 'prizepicks': 'PrizePicks'}


def main_root():
    """The checkout that owns the gitignored tape: the worktree's own root if it has one, else the main checkout."""
    if os.environ.get('SS_ROOT'):
        return Path(os.environ['SS_ROOT'])
    top = HERE.parent
    if (top / 'data' / 'smartstake').exists():
        return top
    common = subprocess.run(['git', '-C', str(top), 'rev-parse', '--git-common-dir'], capture_output=True, text=True).stdout.strip()
    return (Path(common) if os.path.isabs(common) else top / common).resolve().parent


ROOT = main_root()
SS = ROOT / 'data' / 'smartstake'


def name_key(s):
    sys.path.insert(0, str(ROOT / 'nba' / 'scripts'))
    import nba_common as C
    return C.name_key(s)


def am_prob(a):
    a = float(a)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def devig(over, under):
    po, pu = am_prob(over), am_prob(under)
    return po / (po + pu)


def tape_close(league='nba'):
    """-> (quotes, passes). quotes: {(event, player, stat, book, line, side, alt): quote} as of the last pass before the
    event's start, with pre-start passes only. Live quotes and players without an id are dropped."""
    pre = 'basketball_player_'
    last, passes = {}, 0
    for f in sorted(glob.glob(str(SS / league / '*.jsonl.gz'))):
        for line in gzip.open(f, 'rt', encoding='utf-8'):
            p = json.loads(line)
            passes += 1
            t = p['t'] / 1000 if p['t'] > 1e11 else p['t']
            for q in p['quotes']:
                if q.get('live') or q.get('odds') in (None, 0) or not q.get('player_id') or q.get('line') is None or not q['market_key'].startswith(pre):
                    continue
                st = STAT.get(q['market_key'][len(pre):])
                if not st or q['side'] not in ('over', 'under', 'yes') or not q.get('participant'):
                    continue
                if t >= datetime.fromisoformat(q['starts_at'].replace('Z', '+00:00')).timestamp():
                    continue
                last[(q['event_id'], q['participant'], st, q['book'], q['line'], q['side'], bool(q['alternate']))] = q
    return last, passes


def git_show(path):
    r = subprocess.run(['git', '-C', str(ROOT), 'show', f'{NBA_DATA}:{path}'], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def et_day(ts):
    d = datetime.fromtimestamp(ts, timezone.utc) - timedelta(hours=4 if 3 <= datetime.fromtimestamp(ts, timezone.utc).month <= 10 else 5)
    return d.strftime('%Y-%m-%d')


def resolve_games(quotes):
    """{event_id: (gid, tip)} by (away abbr, home abbr, tip) against the recorder's propclose.json. Unmatched stay out."""
    ev = {}
    for (e, *_), q in quotes.items():
        ev.setdefault(e, (q['away'], q['home'], int(datetime.fromisoformat(q['starts_at'].replace('Z', '+00:00')).timestamp())))
    days = {et_day(t + d) for _, _, t in ev.values() for d in (-86400, 0, 86400)}
    idx = {}
    for day in days:
        raw = git_show(f'snapshots/{day}/propclose.json')
        for gid, g in (json.loads(raw) if raw else {}).items():
            idx[(g['m'], g['tip'])] = gid
    out = {}
    for e, (a, h, t) in ev.items():
        aa, ha = abbr('nba', a), abbr('nba', h)
        gid = idx.get((f'{aa} @ {ha}', t))
        if gid:
            out[e] = (gid, t)
    return out


def settled(gid):
    raw = git_show(f'results/{gid}.json')
    return json.loads(raw) if raw else None


def player_ids():
    """name_key -> ESPN athlete id from the box-score history (rookies with no game yet are absent: counted, not guessed)."""
    out = {}
    for f in sorted(glob.glob(str(ROOT / 'nba' / 'raw' / 'hoopr' / 'player_box_*.csv'))):
        for r in csv.DictReader(open(f, encoding='utf-8')):
            if r.get('athlete_id') and r.get('athlete_display_name'):
                out[name_key(r['athlete_display_name'])] = r['athlete_id']
    return out


def actual(box, pid, stat):
    row = (box or {}).get(str(pid))
    if not row or not row.get('minutes'):
        return None
    return sum(row[c] for c in BOX[stat])


def pinnacle_close(days):
    """The recorder's Pinnacle player-prop series for the given ET days -> {(tip, home name lower, name_key, stat): (line, P(over))}
    from the last over/under pair before tip."""
    out = {}
    for day in days:
        meta_raw, rows_raw = git_show(f'snapshots/{day}/meta.jsonl'), git_show(f'snapshots/{day}/pinnacle.jsonl')
        if not meta_raw or not rows_raw:
            continue
        meta = {}
        for line in meta_raw.splitlines():
            if '"src":"pinnacle"' not in line:
                continue
            m = json.loads(line)
            desc = m.get('desc') or ''
            for suf, st in PIN_STAT.items():
                if m.get('parent') and desc.endswith(' ' + suf):
                    home = next((n for a, n in m.get('teams') or [] if a == 'home'), '')
                    meta[m['k']] = (m['matchup'], desc[:-len(suf) - 1], st, m['side'], m['start'], home.lower())
        state = {}
        for line in rows_raw.splitlines():
            r = json.loads(line)
            m = meta.get(r['k'])
            if m and r['t'] < m[4]:
                if r['v'] is None:
                    state.pop(r['k'], None)
                else:
                    state[r['k']] = r['v']
        pair = defaultdict(dict)
        for k, v in state.items():
            mu, name, st, side, start, home = meta[k]
            pair[(mu, name, st, start, home)][side] = v
        for (mu, name, st, start, home), s in pair.items():
            if 'Over' in s and 'Under' in s and s['Over'][0] == s['Under'][0] and s['Over'][1] and s['Under'][1]:
                out[(start, home, name_key(name), st)] = (s['Over'][0], devig(s['Over'][1], s['Under'][1]))
    return out


def snapshot_days():
    r = subprocess.run(['git', '-C', str(ROOT), 'ls-tree', '--name-only', NBA_DATA, 'snapshots/'], capture_output=True, text=True)
    return sorted(p.split('/')[-1] for p in r.stdout.split() if p.split('/')[-1][:2] == '20')


def main_pairs(quotes):
    """{(event, player, stat, book): (line, P(over) no-vig, over odds, under odds)}: each book's two-sided NON-alternate line."""
    by = defaultdict(dict)
    for (e, who, st, bk, ln, side, alt), q in quotes.items():
        if not alt and side in ('over', 'under'):
            by[(e, who, st, bk)].setdefault(ln, {})[side] = q['odds']
    out = {}
    for k, lines in by.items():
        for ln, s in lines.items():
            if 'over' in s and 'under' in s and abs(s['over']) <= 400 and abs(s['under']) <= 400:
                gap = abs(abs(s['over']) - abs(s['under']))
                if k not in out or gap < out[k][4]:
                    out[k] = (ln, devig(s['over'], s['under']), s['over'], s['under'], gap)
    return {k: v[:4] for k, v in out.items()}
