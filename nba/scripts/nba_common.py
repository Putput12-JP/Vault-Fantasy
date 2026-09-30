"""
Shared loaders for the NBA models. Pure stdlib.

Everything a model needs, keyed so that nothing can leak the future:
  games()            completed games in date order (regular season + play-in + playoffs)
  player_games()     one row per player per game from the box score
  closing_lines()    ESPN open/close spread + total per game (one pre-game book)
  InjuryAsOf         official injury report status for a game AS OF a clock time
"""
import csv, datetime as dt, json, os, re, unicodedata
from collections import defaultdict

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, '..', 'raw')
KEEP_TYPES = {'STD', 'CC', 'RD16', 'QTR', 'SEMI', 'FINAL'}


def name_key(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    if ',' in s:  # injury report "Last,First"; suffixes arrive glued on: "LivelyII,Dereck", "PorterJr.,Kevin"
        last, first = s.split(',', 1)
        last = re.sub(r'(jr\.?|sr\.?|iii|ii|iv)$', '', last)
        s = first + ' ' + last
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b\.?', '', s)
    return re.sub(r'[^a-z]', '', s)


def num(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def utc(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))


def et(d):
    """UTC datetime -> naive US Eastern (DST-aware enough for NBA dates: EDT Mar-Nov)."""
    y = d.year
    # 2nd Sunday of March 07:00 UTC .. 1st Sunday of November 06:00 UTC
    mar = dt.datetime(y, 3, 8, 7, tzinfo=dt.timezone.utc)
    mar += dt.timedelta(days=(6 - mar.weekday()) % 7)
    nov = dt.datetime(y, 11, 1, 6, tzinfo=dt.timezone.utc)
    nov += dt.timedelta(days=(6 - nov.weekday()) % 7)
    off = 4 if mar <= d < nov else 5
    return (d - dt.timedelta(hours=off)).replace(tzinfo=None)


def games(seasons):
    out = []
    for s in seasons:
        for g in csv.DictReader(open(os.path.join(RAW, 'hoopr', f'schedule_{s}.csv'))):
            if g['status_type_completed'] != 'true' or g['type_abbreviation'] not in KEEP_TYPES:
                continue
            tip = utc(g['date'])
            out.append({'game_id': int(g['id']), 'season': s, 'tip': tip, 'tip_et': et(tip),
                        'playoff': g['season_type'] == '3', 'neutral': g['neutral_site'] == 'true',
                        'home': g['home_abbreviation'], 'away': g['away_abbreviation'],
                        'home_name': g['home_display_name'], 'away_name': g['away_display_name'],
                        'hs': num(g['home_score']), 'as': num(g['away_score'])})
    out.sort(key=lambda g: (g['tip'], g['game_id']))
    return out


STAT_COLS = ['minutes', 'points', 'rebounds', 'offensive_rebounds', 'defensive_rebounds', 'assists', 'steals',
             'blocks', 'turnovers', 'fouls', 'field_goals_made', 'field_goals_attempted',
             'three_point_field_goals_made', 'three_point_field_goals_attempted',
             'free_throws_made', 'free_throws_attempted', 'plus_minus']


def player_games(seasons):
    """game_id -> list of player rows (played or DNP). Team-level rows (no athlete) skipped."""
    by_game = defaultdict(list)
    for s in seasons:
        for r in csv.DictReader(open(os.path.join(RAW, 'hoopr', f'player_box_{s}.csv'))):
            if not r['athlete_id'] or not r['game_id']:
                continue
            row = {c: num(r[c]) for c in STAT_COLS}
            row.update(athlete_id=int(r['athlete_id']), name=r['athlete_display_name'], team=r['team_abbreviation'],
                       starter=r['starter'] == 'true', pos=r['athlete_position_abbreviation'],
                       played=r['did_not_play'] != 'true' and num(r['minutes']) > 0)
            by_game[int(r['game_id'])].append(row)
    return by_game


def game_score(r):
    """Hollinger Game Score: one-number box production."""
    return (r['points'] + 0.4 * r['field_goals_made'] - 0.7 * r['field_goals_attempted']
            - 0.4 * (r['free_throws_attempted'] - r['free_throws_made']) + 0.7 * r['offensive_rebounds']
            + 0.3 * r['defensive_rebounds'] + r['steals'] + 0.7 * r['assists'] + 0.7 * r['blocks']
            - 0.4 * r['fouls'] - r['turnovers'])


def closing_lines():
    """game_id -> {spread_open, spread_close, total_open, total_close} (home spread, negative = home favoured).
    One pre-game book per game: DraftKings when present, else ESPN BET."""
    path = os.path.join(RAW, 'tables', 'game_lines.csv')
    out = {}
    pref = {'DraftKings': 0, 'ESPN BET': 1}
    for r in csv.DictReader(open(path)):
        gid = int(r['game_id'])
        if r['book'] not in pref or not r['spread_close']:
            continue
        cur = out.get(gid)
        if cur and pref[cur['book']] <= pref[r['book']]:
            continue
        out[gid] = {'book': r['book'],
                    'spread_open': num(r['spread_open'], None), 'spread_close': num(r['spread_close'], None),
                    'total_open': num(r['total_open'], None), 'total_close': num(r['total_close'], None),
                    'spread_home_px': num(r['spread_home_px_close'], None), 'spread_away_px': num(r['spread_away_px_close'], None),
                    'over_px': num(r['over_px_close'], None), 'under_px': num(r['under_px_close'], None)}
    return out


class InjuryAsOf:
    """Official injury report status per (game, athlete) as of a clock time.

    Reports are snapshots at fixed ET hours (see fetch_injury_reports.SNAPSHOT_HOURS).
    status(game, cutoff_et) uses the LATEST snapshot at or before cutoff_et, so a
    backtest that bets at 1pm only sees the 1pm report.
    """
    def __init__(self, seasons, player_index):
        # player_index: (team_abbr, name_key) -> athlete_id, built from box scores
        self.idx = player_index
        ids = defaultdict(set)
        for (_, k), a in player_index.items():
            ids[k].add(a)
        self.by_name = {k: next(iter(v)) for k, v in ids.items() if len(v) == 1}
        self.snap = defaultdict(lambda: defaultdict(dict))  # (date, team_abbr) -> report_et -> {aid: status}
        self.unmatched = 0
        for s in seasons:
            p = os.path.join(RAW, 'injuries', f'reports_{s}.jsonl')
            if not os.path.exists(p):
                continue
            for line in open(p):
                r = json.loads(line)
                team = TEAM_BY_NAME.get(r['team'].replace(' ', ''))
                if not team or not r.get('game_date'):
                    continue
                m, d, y = r['game_date'].split('/')
                day = f'{y}-{m}-{d}'
                k = name_key(r['player'])
                # A player traded mid-season can be listed by his new team before he plays for it:
                # fall back to the name alone when exactly one player league-wide has it.
                aid = self.idx.get((team, k)) or self.by_name.get(k)
                if aid is None:
                    self.unmatched += 1
                    continue
                self.snap[(day, team)][r['report_et']][aid] = r['status']

    def status(self, game_date, team, cutoff_et):
        """{athlete_id: status} from the latest report at or before cutoff_et ('YYYY-MM-DDTHH:MM'), else {}."""
        reps = self.snap.get((game_date, team))
        if not reps:
            return {}
        ok = [t for t in reps if t <= cutoff_et]
        return reps[max(ok)] if ok else {}


# injury reports name teams "NewYorkKnicks"; box scores use ESPN abbreviations
TEAM_BY_NAME = {
    'AtlantaHawks': 'ATL', 'BostonCeltics': 'BOS', 'BrooklynNets': 'BKN', 'CharlotteHornets': 'CHA',
    'ChicagoBulls': 'CHI', 'ClevelandCavaliers': 'CLE', 'DallasMavericks': 'DAL', 'DenverNuggets': 'DEN',
    'DetroitPistons': 'DET', 'GoldenStateWarriors': 'GS', 'HoustonRockets': 'HOU', 'IndianaPacers': 'IND',
    'LAClippers': 'LAC', 'LosAngelesLakers': 'LAL', 'MemphisGrizzlies': 'MEM', 'MiamiHeat': 'MIA',
    'MilwaukeeBucks': 'MIL', 'MinnesotaTimberwolves': 'MIN', 'NewOrleansPelicans': 'NO', 'NewYorkKnicks': 'NY',
    'OklahomaCityThunder': 'OKC', 'OrlandoMagic': 'ORL', 'Philadelphia76ers': 'PHI', 'PhoenixSuns': 'PHX',
    'PortlandTrailBlazers': 'POR', 'SacramentoKings': 'SAC', 'SanAntonioSpurs': 'SA', 'TorontoRaptors': 'TOR',
    'UtahJazz': 'UTAH', 'WashingtonWizards': 'WSH',
}


def player_index(by_game):
    idx = {}
    for rows in by_game.values():
        for r in rows:
            idx[(r['team'], name_key(r['name']))] = r['athlete_id']
    return idx
