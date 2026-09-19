#!/usr/bin/env python3
"""
VAULT · MARKET GRADES  →  data/market_grades.json

Fuses four pillars into one 0-100 grade per player per market. The grade is
matchup + environment + the player's own role and production — NO betting line
is consulted, so the odds a viewer sees are context, not an input.

    Opportunity  role / volume        snap% + depth + target|carry share
    Quality      recent production    season + last-4 fantasy pts, market stat
    Matchup      defense vs position  feed['dvp'][opp][pos] (already shrunk)
    Environment  game context         Vegas implied team total + game total

Everything is read from files that already ship and are on a cron:
    data/lineup-feed.json        slate, lines, dvp (shrunk), vegas_games
    data/nflverse_snaps_<yr>.json  snap share
    data/nflverse_stats_<yr>.json  game-log production

This is a v1 fusion: each pillar is percentile-scaled within position across the
live slate, so a 70 means "top third of gradeable players at this position this
week", not an absolute. Weights per market family are hand-set here (documented
below) — the honest next step is to fit them against settled results the way the
prop model already is, but the inputs themselves are all measured.

Usage:  python3 scripts/build_market_grades.py [--feed data/lineup-feed.json]
"""
import json, os, re, sys, argparse
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def dpath(*p): return os.path.join(ROOT, 'data', *p)
def load(p):
    with open(p) as f: return json.load(f)

# ── market catalogue ───────────────────────────────────────────────────────
# label       : shown in the UI
# pos         : positions the market applies to
# family      : 'vol' (yards/att/rec) or 'td' — drives the pillar weights
# vol_stat    : season-stat key that best proxies OPPORTUNITY volume (or None)
# qual_stat   : season-stat key for QUALITY production (falls back to fantasy pts)
MARKETS = {
    'pass_yd':  dict(label='Pass Yds',  pos={'QB'},            family='vol', vol_stat=None,      qual_stat='avg_pyds'),
    'pass_att': dict(label='Pass Att',  pos={'QB'},            family='vol', vol_stat=None,      qual_stat='avg_pyds'),
    'pass_cmp': dict(label='Pass Cmp',  pos={'QB'},            family='vol', vol_stat=None,      qual_stat='avg_pyds'),
    'pass_td':  dict(label='Pass TDs',  pos={'QB'},            family='td',  vol_stat=None,      qual_stat='avg_ptds'),
    'rush_yd':  dict(label='Rush Yds',  pos={'RB','QB'},       family='vol', vol_stat='avg_car', qual_stat='avg_ryds'),
    'rush_att': dict(label='Rush Att',  pos={'RB'},            family='vol', vol_stat='avg_car', qual_stat='avg_car'),
    'rush_td':  dict(label='Rush TDs',  pos={'RB','QB'},       family='td',  vol_stat='avg_car', qual_stat='avg_ryds'),
    'rec':      dict(label='Receptions',pos={'WR','TE','RB'},  family='vol', vol_stat='avg_tgt', qual_stat='avg_rec'),
    'rec_yd':   dict(label='Rec Yds',   pos={'WR','TE','RB'},  family='vol', vol_stat='avg_tgt', qual_stat='avg_recyds'),
    'rec_td':   dict(label='Rec TDs',   pos={'WR','TE','RB'},  family='td',  vol_stat='avg_tgt', qual_stat='avg_recyds'),
}

# pillar weights by market family (sum to 1.0)
WEIGHTS = {
    'vol': dict(opportunity=.34, quality=.30, matchup=.22, environment=.14),
    'td':  dict(opportunity=.24, quality=.24, matchup=.24, environment=.28),
}

DEPTH_SCORE = {1: 100, 2: 68, 3: 42, 4: 24}   # depth-chart slot → opportunity points

# ── name join (Sleeper prop names ↔ nflverse game-log names) ────────────────
_SUFFIX = re.compile(r'\b(jr|sr|ii|iii|iv|v)\b\.?', re.I)
def nkey(name):
    s = (name or '').lower()
    s = s.replace('.', '').replace("'", '').replace('-', ' ')
    s = _SUFFIX.sub('', s)
    return re.sub(r'\s+', ' ', s).strip()

def pct_rank(value, pool):
    """Percentile (0-100) of value within pool. Empty/degenerate → 50."""
    xs = [x for x in pool if x is not None]
    if value is None or len(xs) < 3: return 50.0
    below = sum(1 for x in xs if x < value)
    equal = sum(1 for x in xs if x == value)
    return round(100.0 * (below + 0.5 * equal) / len(xs), 1)

def clamp(x, lo=0, hi=100): return max(lo, min(hi, x))

# Best available price for one side of a line. The headline book is often a DFS
# app (PrizePicks) that posts the line with NO american price; the real prices
# live in `best`/`quotes`. Returns {price, line, book} so the displayed line stays
# consistent with the book the price came from — or None if no book prices it.
def best_price(ln, side):
    best = (ln.get('best') or {}).get(side)
    if best and best.get('price') is not None:
        return {'price': best['price'], 'line': best.get('line', ln.get('line')), 'book': best.get('book')}
    cand = [q for q in (ln.get('quotes') or []) if q.get(side) is not None]
    if cand:
        b = max(cand, key=lambda q: q[side])   # best number for the bettor
        return {'price': b[side], 'line': b.get('line', ln.get('line')), 'book': b.get('book')}
    if ln.get(side) is not None:
        return {'price': ln[side], 'line': ln.get('line'), 'book': ln.get('book')}
    return None

# ── load inputs ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feed', default=dpath('lineup-feed.json'))
    ap.add_argument('--min-games', type=int, default=1)
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    feed = load(args.feed)
    season = str(feed.get('season', datetime.now().year))
    week   = feed.get('week')
    dvp    = feed.get('dvp', {})                  # {TEAM: {POS: {fpa, rank}}}
    props  = feed.get('vegas_player_props', {})   # {pid: {name, team, pos, lines}}
    depth  = feed.get('vegas_depth', {})          # {pid: [depth, ...]}

    try: snaps = load(dpath(f'nflverse_snaps_{season}.json'))
    except FileNotFoundError: snaps = {}
    try: stats = load(dpath(f'nflverse_stats_{season}.json'))
    except FileNotFoundError: stats = {}
    snaps_by = {nkey(k): v for k, v in snaps.items()}
    stats_by = {nkey(k): v for k, v in stats.items()}

    # team → opponent + Vegas environment, from THIS WEEK's game board only.
    # The feed carries next week's games too (books post them early), and a team
    # whose current game has already kicked off drops OFF the board entirely. An
    # unfiltered map therefore hands that team NEXT week's opponent and grades a
    # player for a game that already happened — e.g. the day after DET @ BUF
    # (Wk 2) was played, Amon-Ra was graded for DET @ NYJ (a Wk 3 game). Restrict
    # env to the current-week slate; a team with no current-week game left (played
    # or bye) simply isn't in the map and its players are skipped below.
    env_by_team = {}
    for g in feed.get('vegas_games', []):
        if week is not None and g.get('week') != week: continue
        away, home = g.get('away'), g.get('home')
        imp = g.get('implied', {}) or {}
        tot = (g.get('total', {}) or {}).get('cons')
        if away: env_by_team[away] = dict(opp=home, implied=imp.get('away'), total=tot, home=False)
        if home: env_by_team[home] = dict(opp=away, implied=imp.get('home'), total=tot, home=True)

    implied_pool = [e['implied'] for e in env_by_team.values() if e.get('implied') is not None]

    # ── pass 1: gather raw signals per (player, market) ─────────────────────
    raw = []
    for pid, p in props.items():
        pos, team = p.get('pos'), p.get('team')
        env = env_by_team.get(team)
        if env is None:
            continue  # team's current-week game already played (off the board) or bye — don't grade a stale/next-week matchup
        st  = stats_by.get(nkey(p.get('name')), {})
        sn  = snaps_by.get(nkey(p.get('name')), {})
        season_st = st.get('season', {}) if isinstance(st, dict) else {}
        games = season_st.get('games', 0)
        for mkt, ln in (p.get('lines') or {}).items():
            spec = MARKETS.get(mkt)
            if not spec or pos not in spec['pos']: continue
            raw.append(dict(
                pid=pid, name=p.get('name'), team=team, pos=pos, market=mkt, spec=spec,
                headshot=(st.get('headshot') if isinstance(st, dict) else None),
                line=ln.get('line'), over_bp=best_price(ln, 'over'), under_bp=best_price(ln, 'under'), book=ln.get('book'),
                opp=(env or {}).get('opp'), implied=(env or {}).get('implied'), total=(env or {}).get('total'),
                snap=sn.get('avg_off'),
                depth=(depth.get(pid) or [None])[0],
                vol=season_st.get(spec['vol_stat']) if spec['vol_stat'] else None,
                qual=season_st.get(spec['qual_stat']),
                fpts=season_st.get('avg_pts'), l4w=st.get('l4w_avg') if isinstance(st, dict) else None,
                games=games,
            ))

    # per-position pools for percentile scaling
    def pool(pos, key):
        return [r[key] for r in raw if r['pos'] == pos and r[key] is not None]

    # ── pass 2: build pillars + grade ───────────────────────────────────────
    out = []
    for r in raw:
        if r['games'] < args.min_games and not r['snap']:
            continue  # nothing measured about this player yet — don't fabricate a grade
        pos = r['pos']

        # OPPORTUNITY — snap% (already 0-100) blended with role signals
        opp_parts, opp_wt = [], 0.0
        if r['snap'] is not None:      opp_parts.append((r['snap'], 0.55));                     opp_wt += 0.55
        if r['depth'] in DEPTH_SCORE:  opp_parts.append((DEPTH_SCORE[r['depth']], 0.20));       opp_wt += 0.20
        if r['vol'] is not None:       opp_parts.append((pct_rank(r['vol'], pool(pos,'vol')), .25)); opp_wt += 0.25
        opportunity = round(sum(v*w for v, w in opp_parts) / opp_wt) if opp_wt else 50

        # QUALITY — recent production percentile (market stat + fantasy points)
        q_parts, q_wt = [], 0.0
        if r['qual'] is not None: q_parts.append((pct_rank(r['qual'], pool(pos,'qual')), .50)); q_wt += .50
        if r['fpts'] is not None: q_parts.append((pct_rank(r['fpts'], pool(pos,'fpts')), .30)); q_wt += .30
        if r['l4w']  is not None: q_parts.append((pct_rank(r['l4w'],  pool(pos,'l4w')),  .20)); q_wt += .20
        quality = round(sum(v*w for v, w in q_parts) / q_wt) if q_wt else 50

        # MATCHUP — opponent DvP rank for this position (32 = softest = 100)
        d = (dvp.get(r['opp']) or {}).get(pos) if r['opp'] else None
        matchup = round((d['rank'] / 32) * 100) if d and d.get('rank') else 50

        # ENVIRONMENT — team implied total percentile across the slate
        environment = round(pct_rank(r['implied'], implied_pool)) if r['implied'] is not None else 50

        pillars = dict(opportunity=clamp(opportunity), quality=clamp(quality),
                       matchup=clamp(matchup), environment=clamp(environment))

        w = WEIGHTS[r['spec']['family']]
        grade = round(sum(pillars[k] * w[k] for k in w))

        # direction (grade strength → lean), matchup chip, confidence, fade
        if   grade >= 70: direction = 'strong_over'
        elif grade >= 56: direction = 'lean_over'
        elif grade <= 30: direction = 'strong_under'
        elif grade <= 44: direction = 'lean_under'
        else:             direction = 'no_edge'

        chip_score = (pillars['matchup'] + pillars['environment']) / 2
        chip = 'good' if chip_score >= 58 else 'bad' if chip_score <= 42 else 'even'

        spread = max(pillars.values()) - min(pillars.values())
        strong = grade >= 62 or grade <= 40
        if   spread <= 22 and strong and r['games'] >= 3: confidence = 'high'
        elif spread <= 34: confidence = 'medium'
        else: confidence = 'low'

        fade = pillars['matchup'] <= 40 and pillars['environment'] <= 45 and grade <= 44

        # Display the leaned side's best real price, with the line from the same
        # book so line + price never disagree. Falls back to the headline line
        # when no book actually prices the market (a pure DFS line).
        lean_side = 'under' if direction.find('under') >= 0 else 'over'
        bp = r['under_bp'] if lean_side == 'under' else r['over_bp']
        disp_line = bp['line'] if bp else r['line']
        disp_price = bp['price'] if bp else None
        disp_book = bp['book'] if bp else r['book']
        out.append(dict(
            pid=r['pid'], name=r['name'], team=r['team'], pos=pos, opp=r['opp'],
            headshot=r.get('headshot'),
            market=r['market'], marketLabel=r['spec']['label'],
            line=disp_line, price=disp_price, book=disp_book,
            over=(r['over_bp']['price'] if r['over_bp'] else None),
            under=(r['under_bp']['price'] if r['under_bp'] else None),
            grade=grade, direction=direction, chip=chip, confidence=confidence, fade=fade,
            pillars=pillars, games=r['games'],
        ))

    out.sort(key=lambda x: (-x['grade'], x['name']))

    result = dict(
        generated=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        season=season, week=week,
        method='v1 percentile-fusion; matchup+environment+role+production, no line consulted',
        dvp_meta=feed.get('dvp_meta'),
        weights=WEIGHTS,
        counts=dict(
            graded=len(out),
            good=sum(1 for x in out if x['chip'] == 'good'),
            bad=sum(1 for x in out if x['chip'] == 'bad'),
            even=sum(1 for x in out if x['chip'] == 'even'),
            strong=sum(1 for x in out if x['direction'].startswith('strong')),
            fades=sum(1 for x in out if x['fade']),
        ),
        grades=out,
    )
    with open(dpath('market_grades.json'), 'w') as f:
        json.dump(result, f, separators=(',', ':'))

    if not args.quiet:
        c = result['counts']
        print(f"market_grades.json  ·  {season} wk {week}  ·  {c['graded']} graded "
              f"({c['good']} good / {c['bad']} bad / {c['even']} even · {c['strong']} strong · {c['fades']} fades)")
        if feed.get('dvp_meta', {}).get('stale'):
            print(f"  note: DvP is stale (season {feed['dvp_meta'].get('season')}) — matchup pillar carries last-season shape")
        print("\n  top 12 by grade:")
        print(f"  {'PLAYER':<20}{'POS':<4}{'MARKET':<11}{'LINE':>6}  {'GR':>3} {'DIR':<12}{'CHIP':<6}{'CONF':<7} O/Q/M/E")
        for x in out[:12]:
            pl = f"{x['pillars']['opportunity']}/{x['pillars']['quality']}/{x['pillars']['matchup']}/{x['pillars']['environment']}"
            ln = '' if x['line'] is None else f"{x['line']:g}"
            print(f"  {x['name'][:19]:<20}{x['pos']:<4}{x['marketLabel']:<11}{ln:>6}  {x['grade']:>3} "
                  f"{x['direction']:<12}{x['chip']:<6}{x['confidence']:<7}{pl}")

if __name__ == '__main__':
    main()
