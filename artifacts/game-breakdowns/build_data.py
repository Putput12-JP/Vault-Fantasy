#!/usr/bin/env python3
"""Rebuild data.json for the Vault Game Breakdowns artifact.
Usage: python3 artifacts/game-breakdowns/build_data.py [--local] [--out=DIR] [--data-only]

Reads the pushed data (refuses to run when the working copy's data/ differs
from origin/main, so the page never shows unpushed numbers), scores every prop
with the live Best Bets builder in --dump mode, and writes data.json next to
this file. One entry per unstarted game in the served week and the next.

Every number here is the one the app serves:
  market   consensus line + best price per side (lineup-feed vegas_games)
  fair     per-book power de-vig -> fair margin/total via the model's sd, median
           across books (index.html gmFair)
  model    team ratings + backup-QB adjustment (index.html gmPredict,
           game_model.json + qb_status.json)
  rules    play-type record per market x gap band (game_rules.json)
  props    build_best_bets.mjs --dump: every scored line + the gate that stopped it
"""
import json, os, re, subprocess, sys, tempfile, statistics
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
_o = [a[6:] for a in sys.argv if a.startswith('--out=')]
OUT_DIR = _o[0] if _o else HERE
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, 'data.json')
ND = statistics.NormalDist()

git = lambda *a: subprocess.run(['git', '-C', REPO, *a], capture_output=True, text=True)
# Read what is PUSHED: a throwaway detached checkout of origin/main, so the
# page never shows unpushed numbers and the working copy is never touched.
# --local reads the working copy instead (preview only; never publish from it).
SRC = REPO
if '--local' not in sys.argv:
    if git('fetch', '-q', 'origin', 'main').returncode != 0:
        sys.exit('git fetch failed')
    SRC = os.path.join(tempfile.mkdtemp(), 'wt')
    r = git('worktree', 'add', '-q', '--detach', SRC, 'origin/main')
    if r.returncode != 0: sys.exit('worktree failed: ' + r.stderr)
    import atexit
    atexit.register(lambda: git('worktree', 'remove', '--force', SRC))
load = lambda p: json.load(open(os.path.join(SRC, 'data', p)))
def try_load(p, d=None):
    try: return load(p)
    except Exception: return d

feed = load('lineup-feed.json')
gm = load('game_model.json')
qbs = (try_load('qb_status.json', {}) or {}).get('teams') or {}
news = (try_load('line_news.json', {}) or {}).get('games') or {}
rules = try_load('game_rules.json', {}) or {}
weather = {(w['away'], w['home']): w for w in (try_load('weather.json', {}) or {}).get('games') or []}
poly = (try_load('polymarket.json', {}) or {}).get('games') or {}
hist = (try_load('game_line_history.json', {}) or {}).get('games') or {}
card = (try_load('best_bets_card.json', {}) or {}).get('picks') or []
brec = try_load('best_bets_record.json', {}) or {}

# every scored prop (pass or the gate that stopped it), this week + next
dump_path = os.path.join(tempfile.mkdtemp(), 'dump.json')
r = subprocess.run(['node', 'scripts/build_best_bets.mjs', '--feed=data/lineup-feed.json', f'--dump={dump_path}'],
                   cwd=SRC, capture_output=True, text=True)
dump = json.load(open(dump_path)) if os.path.exists(dump_path) else {'props': [], 'eligible': []}
eligible = set(dump.get('eligible') or [])

ALIAS = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA', 'WSH': 'WAS'}
mt = lambda t: ALIAS.get(t, t)
now = datetime.now(timezone.utc)
week = int(feed.get('week') or 0)
sdM, sdT = gm.get('sd_margin') or 13.2, gm.get('sd_total') or 13.6


def imp(a):
    return None if a is None else (-a / (-a + 100) if a < 0 else 100 / (a + 100))


def pow_devig(a, b):
    po, pu = imp(a), imp(b)
    if not po or not pu: return None
    if po + pu <= 1: return po / (po + pu)
    lo, hi = 1.0, 10.0
    for _ in range(50):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1: lo = k
        else: hi = k
    k = (lo + hi) / 2
    return po ** k / (po ** k + pu ** k)


def inv(p): return ND.inv_cdf(min(max(p, 1e-6), 1 - 1e-6))
def med(a):
    a = [x for x in a if x is not None]
    return statistics.median(a) if a else None
def rd(x, n=1): return None if x is None else round(x, n)


def fair(g):
    sp, to, wh = [], [], []
    for q in (g.get('spread') or {}).get('quotes') or []:
        h, a = q.get('home') or {}, q.get('away') or {}
        if h.get('line') is None or h.get('price') is None or a.get('price') is None: continue
        p = pow_devig(h['price'], a['price'])
        if p is not None: sp.append(-(sdM * inv(p) - h['line']))
    for q in (g.get('total') or {}).get('quotes') or []:
        if q.get('line') is None or q.get('over') is None or q.get('under') is None: continue
        p = pow_devig(q['over'], q['under'])
        if p is not None: to.append(q['line'] + sdT * inv(p))
    for q in (g.get('ml') or {}).get('quotes') or []:
        p = pow_devig(q.get('home'), q.get('away'))
        if p is not None: wh.append(p)
    cons = ((g.get('spread') or {}).get('cons') or {}).get('home')
    return {'homeSpread': rd(med(sp) if sp else cons), 'total': rd(med(to) if to else (g.get('total') or {}).get('cons')),
            'homeWin': rd(med(wh), 3), 'books': len(sp)}


def model(away, home):
    T = gm.get('teams') or {}
    th, ta = T.get(mt(home)), T.get(mt(away))
    if not th or not ta or gm.get('offseason'): return None
    Q = gm.get('qb') or {}
    qh, qa = qbs.get(mt(home)), qbs.get(mt(away))
    hb, ab = (1 if qh else 0), (1 if qa else 0)
    qm, qt = Q.get('margin') or 0, Q.get('total') or 0
    own, opp = (qt + qm) / 2, (qm - qt) / 2
    hfa = 0 if f'{mt(away)}@{mt(home)}' in (gm.get('neutral') or []) else gm['hfa']
    pm = th['rate'] - ta['rate'] + hfa - qm * (hb - ab)
    ph = gm['base_pts'] + th['off'] - ta['def'] + hfa / 2 - own * hb + opp * ab
    pa = gm['base_pts'] + ta['off'] - th['def'] - hfa / 2 - own * ab + opp * hb
    return {'homeSpread': rd(-pm), 'total': rd(ph + pa), 'homeWin': rd(ND.cdf(pm / gm['sd_margin']), 3),
            'qb': {'home': qh, 'away': qa, 'margin': qm, 'total': qt} if (qh or qa) else None}


BANDS = rules.get('bands') or {'spread': [1.5, 3], 'total': [1.5, 3], 'ml': [2.5, 5]}
def band(mk, d):
    b = BANDS[mk]
    return 'small' if d < b[0] else 'mid' if d < b[1] else 'big'
def rule(mk, d):
    k = f'{mk}|{band(mk, d)}'
    b = (rules.get('buckets') or {}).get(k) or {}
    return {'band': band(mk, d), 'on': bool(b.get('on')), 'W': b.get('W'), 'L': b.get('L'), 'units': b.get('units')}


def best(quotes, pick, at=None):
    """Best (highest) American price among quotes; pick(q) -> (line, price).
    With `at`, only quotes at that exact line (an alt line's price is not
    comparable)."""
    top = None
    for q in quotes or []:
        lp = pick(q)
        if not lp or lp[1] is None or (at is not None and lp[0] != at): continue
        if top is None or lp[1] > top['price']: top = {'line': lp[0], 'price': lp[1], 'book': q.get('book')}
    return top


def movement(g):
    ks = [k for k in hist if k.endswith('|' + f"{g['away']}@{g['home']}")]
    rows = [hist[k] for k in ks if hist[k].get('commence') == g.get('commence')]
    if not rows: return None
    op = min((r.get('open') or {} for r in rows), key=lambda o: o.get('ts') or '9')
    cu = max((r.get('cur') or {} for r in rows), key=lambda o: o.get('ts') or '')
    return {'open': {'spread': op.get('spread'), 'total': op.get('total'), 'ts': op.get('ts')},
            'cur': {'spread': cu.get('spread'), 'total': cu.get('total')}}


def market_over(pl, mk, line):
    """No-vig P(over) at this exact line from every sportsbook pricing both sides."""
    cell = ((feed.get('vegas_player_props') or {}).get(pl) or {}).get('lines', {}).get(mk) or {}
    ps = [pow_devig(q.get('over'), q.get('under')) for q in cell.get('quotes') or []
          if q.get('line') == line and q.get('over') is not None and q.get('under') is not None]
    return rd(med(ps), 3)


REC_BOOKS = {'FanDuel', 'DraftKings', 'BetRivers', 'Hard Rock Bet', 'Bovada', 'Fliff', 'BetMGM', 'Caesars', 'Fanatics', 'bet365', 'Parx Casino'}
def book_lead(g):
    """Pinnacle (and FanDuel, the control) vs the rec books' no-vig median, per
    market, same math as snapshot-game-history.mjs trackLead. + = the book has
    the HOME side / the Over stronger than the rec books."""
    out = {}
    for mk, qs in (('sp', (g.get('spread') or {}).get('quotes') or []), ('to', (g.get('total') or {}).get('quotes') or [])):
        fb = {}
        for q in qs:
            if mk == 'sp':
                H_, A_ = q.get('home') or {}, q.get('away') or {}
                if H_.get('line') is None: continue
                p_ = pow_devig(H_.get('price'), A_.get('price'))
                if p_ is not None: fb[q['book']] = -(sdM * inv(p_) - H_['line'])
            else:
                if q.get('line') is None: continue
                p_ = pow_devig(q.get('over'), q.get('under'))
                if p_ is not None: fb[q['book']] = q['line'] + sdT * inv(p_)
        if len(fb) >= 3:
            m_ = statistics.median(fb.values()); lim = 2.5 if mk == 'sp' else 3.5
            fb = {b: v for b, v in fb.items() if abs(v - m_) <= lim}
        row = {}
        for b in ('Pinnacle', 'FanDuel'):
            rv = [v for k, v in fb.items() if k in REC_BOOKS and k != b]
            if b in fb and len(rv) >= 3:
                r_ = statistics.median(rv)
                # spread: fair HOME spread, so home-stronger = more negative; flip so + = home side stronger
                row[b] = {'book': round(fb[b], 2), 'rec': round(r_, 2), 'gap': round((r_ - fb[b]) if mk == 'sp' else (fb[b] - r_), 2)}
        if row: out[mk] = row
    return out


STATUS = {'pass': 'Best Bet', 'no-edge': 'No edge at this price', 'role': 'Role not confirmed by the books',
          'sharp': 'Kalshi disagrees by 10+ pts', 'thin': 'Market not proven yet', 'hold': 'Early-season hold',
          'blowout': 'Projection too far from the line', 'count': 'Low-count under the market favors over',
          'dfs': 'Only priced on pick’em apps'}

games = []
for g in feed.get('vegas_games') or []:
    try: t = datetime.fromisoformat(g['commence'].replace('Z', '+00:00'))
    except Exception: continue
    if t <= now or g.get('week') not in (week, week + 1): continue
    a, h = g['away'], g['home']
    sp, tot, ml = g.get('spread') or {}, g.get('total') or {}, g.get('ml') or {}
    f, m = fair(g), model(a, h)
    mk = {'spread': (sp.get('cons') or {}).get('home'), 'total': tot.get('cons')}
    lines = {
        'spread': {'cons': mk['spread'], 'fair': f['homeSpread'], 'model': m and m['homeSpread'],
                   'bestHome': best(sp.get('quotes'), lambda q: ((q.get('home') or {}).get('line'), (q.get('home') or {}).get('price')), mk['spread']),
                   'bestAway': best(sp.get('quotes'), lambda q: ((q.get('away') or {}).get('line'), (q.get('away') or {}).get('price')), None if mk['spread'] is None else -mk['spread'])},
        'total': {'cons': mk['total'], 'fair': f['total'], 'model': m and m['total'],
                  'bestOver': best(tot.get('quotes'), lambda q: (q.get('line'), q.get('over')), mk['total']),
                  'bestUnder': best(tot.get('quotes'), lambda q: (q.get('line'), q.get('under')), mk['total'])},
        'ml': {'fair': f['homeWin'], 'model': m and m['homeWin'],
               'bestHome': best(ml.get('quotes'), lambda q: (None, q.get('home'))),
               'bestAway': best(ml.get('quotes'), lambda q: (None, q.get('away')))},
    }
    # model vs market gap, band and that band's record (the Game Plays rule)
    plays = []
    if m:
        if mk['spread'] is not None:
            d = abs(m['homeSpread'] - mk['spread'])
            if d > 0:
                side = h if m['homeSpread'] < mk['spread'] else a
                ln = mk['spread'] if side == h else -mk['spread']
                plays.append({'market': 'spread', 'pick': f'{side} {ln:+g}', 'gap': rd(d), **rule('spread', d)})
        if mk['total'] is not None:
            d = abs(m['total'] - mk['total'])
            if d > 0:
                plays.append({'market': 'total', 'pick': ('Over ' if m['total'] > mk['total'] else 'Under ') + f"{mk['total']:g}",
                              'gap': rd(d), **rule('total', d)})
        if f['homeWin'] is not None:
            d = abs(m['homeWin'] - f['homeWin']) * 100
            if d > 0:
                side = h if m['homeWin'] > f['homeWin'] else a
                plays.append({'market': 'ml', 'pick': f'{side} ML', 'gap': rd(d, 0), **rule('ml', d)})
    if m and m['qb']:   # same hold as the app's Game Plays strip
        for p_ in plays: p_['held'] = 'backup QB'
    nw = news.get(f'{a}@{h}')
    if nw and (not nw.get('commence') or nw['commence'] == g.get('commence')):   # line moved 4+ since the lookahead
        for p_ in plays: p_.setdefault('held', 'line move')
    else: nw = None
    fs, ft = f['homeSpread'], f['total']
    score = {'home': rd((ft - fs) / 2), 'away': rd((ft + fs) / 2)} if fs is not None and ft is not None else None
    P = poly.get(f'{a}@{h}') or {}
    tk = P.get('taker') or {}
    money = None
    if (P.get('flow') or {}).get('vol'):
        side = (h if tk['net'] >= 0 else a) if tk.get('n', 0) >= 15 and abs(tk.get('net', 0)) >= 2500 else None
        big = None
        if tk.get('bigN'):
            big = {'side': h if tk['bigNet'] >= 0 else a, 'net': abs(tk['bigNet']), 'n': tk['bigN']}
        acct = {}
        for cl in ('sharp', 'dull'):
            if tk.get(cl + 'N'):
                acct[cl] = {'side': h if tk[cl + 'Net'] >= 0 else a, 'net': abs(tk[cl + 'Net']), 'n': tk[cl + 'N']}
        money = {'acct': acct, 'vol': P['flow']['vol'], 'vol24': P['flow'].get('vol24'), 'net': abs(tk.get('net') or 0), 'side': side,
                 'markets': P.get('markets'), 'ml': P.get('ml'), 'big': big, 'n': tk.get('n')}
    W = weather.get((a, h))
    # props for this game
    teams = {a, h}
    pr = []
    for x in dump.get('props') or []:
        if x.get('team') not in teams or x.get('opp') not in teams: continue
        if x.get('status') in ('out', 'withheld'):
            pr.append({'name': x['name'], 'team': x['team'], 'pos': x.get('pos'), 'status': x['status'], 'why': x.get('why')})
            continue
        mo = market_over(x['id'], x['market'], x['line'])
        pr.append({'name': x['name'], 'team': x['team'], 'pos': x.get('pos'), 'market': x['marketLabel'], 'mk': x['market'],
                   'line': x['line'], 'side': x['side'], 'over': x.get('over'), 'mktOver': mo, 'proj': rd(x.get('proj')),
                   'price': x.get('price'), 'book': x.get('book'), 'ev': x.get('ev'), 'grade': x.get('grade'),
                   'books': x.get('books'), 'status': x['status'], 'kalshi': x.get('kalshi'), 'label': STATUS.get(x['status'], x['status']),
                   'cardType': f"{x['id']}|{x['market']}" in eligible})
    cp = [{'name': c['name'], 'team': c.get('team'), 'market': c.get('marketLabel') or c['market'], 'side': c['side'],
           'line': c['line'], 'price': c.get('price'), 'book': c.get('book'), 'posted': c.get('posted'), 'result': c.get('result')}
          for c in card if str(c.get('season')) == str(feed.get('season')) and c.get('week') == g.get('week')
          and c.get('team') in teams and c.get('opp') in teams]
    games.append({'key': f'{a}@{h}', 'away': a, 'home': h, 'week': g.get('week'), 'commence': g['commence'],
                  'neutral': f'{mt(a)}@{mt(h)}' in (gm.get('neutral') or []),
                  'lines': lines, 'plays': plays, 'score': score, 'money': money, 'move': movement(g),
                  'weather': W and {k: W.get(k) for k in ('stadium', 'roof', 'wind_mph', 'gust_mph', 'temp_f', 'precip_pct')},
                  'qb': m and m['qb'], 'props': pr, 'card': cp, 'lead': book_lead(g)})
games.sort(key=lambda x: x['commence'])

rec = (brec.get('seasons') or {})
out = {'generated': now.isoformat(), 'built': int(now.timestamp()), 'season': feed.get('season'), 'week': week, 'games': games,
       'qb': {'margin': (gm.get('qb') or {}).get('margin'), 'total': (gm.get('qb') or {}).get('total')},
       'record': rec,
       'card_rule': {k: v for k, v in ((try_load('best_bets_rules.json', {}) or {}).get('buckets') or {}).items() if v.get('on')},
       'game_rules_on': {k: v for k, v in (rules.get('buckets') or {}).items() if v.get('on')},
       'bands': BANDS,
       'sharp_lead': (try_load('model_scoreboard.json', {}) or {}).get('sharp_lead'),
       'signals': (try_load('model_scoreboard.json', {}) or {}).get('signals'),
       'pm_study': (try_load('pm_wallets.json', {}) or {}).get('study'),
       'pm_counts': {k: len((try_load('pm_wallets.json', {}) or {}).get(k) or []) for k in ('sharp', 'dull')}}
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
# content fingerprint (everything but the timestamp): the scheduled refresh
# republishes only when this changes
import hashlib
sig = hashlib.sha1(json.dumps({k: v for k, v in out.items() if k != 'generated'}, sort_keys=True).encode()).hexdigest()
open(os.path.join(OUT_DIR, 'data.sig'), 'w').write(sig + '\n')
print(f'wrote {OUT}: {len(games)} games, {sum(len(g["props"]) for g in games)} props')

# assemble the page: the Halaska React app (app/app.jsx, bundled by
# app/build.mjs into one self-contained index.html). The page reads data.json at
# runtime, so the bundle does not depend on this run's data; rebuilding keeps it
# in step with app.jsx. index.src.html is the old vanilla page, kept as reference.
if '--data-only' in sys.argv: sys.exit(0)
r = subprocess.run(['node', os.path.join(HERE, 'app', 'build.mjs')], capture_output=True, text=True)
if r.returncode != 0:
    sys.exit('page build failed: ' + (r.stderr or r.stdout)[:400])
print('wrote', os.path.join(HERE, 'index.html'))
