#!/usr/bin/env python3
"""When our model agrees with a Top Read, does the read do better?

Two tests, both graded only from stored numbers (no invented prices):

  A. TRACKED. Every graded pick in the Sharp Money feed (sharp-data branch) carries the bet
     signals that fired (line move, money vs bets, +EV at a book) and the line it was graded
     at. We attach our model's side for the same game (NFL/CFB spread model, CFB totals model,
     NBA game-model ratings) and split each record by whether the model agrees.
     Sharp accounts are context only and never count toward the agree total.

  B. PROXY (larger sample). The tracked feed only goes back to the first logged week, so this
     takes the one signal that can be rebuilt after the fact, the line move from the open to
     the close, and splits it by model agreement, graded against the closing spread.
     It is NOT the Pinnacle steam read, it is the same direction on a longer window.

Usage:  python3 scripts/backtest_signal_model_agree.py [--feed path] [--out data/signal_model_agree.json]
"""
import json, math, os, re, subprocess, argparse, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)
BET = {'line', 'money', 'behind'}          # sharp / cross are context, never counted
PICK_EDGE = {'nfl': 3.0, 'cfb': 5.0, 'nba': 3.0}
STEAM = {'nfl': 0.5, 'cfb': 1.0}
BE = 110 / 210
ABBR = {'JAC': 'JAX', 'LAR': 'LA', 'WSH': 'WAS', 'LV': 'LV', 'OAK': 'LV'}


def jl(p):
    return json.load(open(p))


def load_feed(path):
    if path:
        return jl(path)
    try:
        raw = subprocess.check_output(['git', '-C', ROOT, 'show', 'origin/sharp-data:data.json'])
        return json.loads(raw)
    except Exception:
        return jl(D('.claude', 'sharp-money', 'data.json'))


def wilson(w, n, z=1.96):
    if not n:
        return None
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def pack(rows):
    """rows: dicts with res (1/-1/0) and optional units."""
    w = sum(r['res'] > 0 for r in rows)
    l = sum(r['res'] < 0 for r in rows)
    p = len(rows) - w - l
    n = w + l
    u = [r['units'] for r in rows if isinstance(r.get('units'), (int, float))]
    pct = round(w / n, 3) if n else None
    out = dict(w=w, l=l, p=p, n=n, pct=pct, ci=wilson(w, n),
               units=round(sum(u), 2) if u else None, unitsN=len(u),
               roi=round(sum(u) / len(u), 3) if u else None)
    if len(u) != len(rows):                       # units are stored on only some picks, so a mean over them is not the record's ROI
        out['units'] = out['roi'] = None
    out['flag'] = ('monitor' if pct is not None and pct > BE else 'below') if n else None
    out['small'] = n < 30
    return out


# ---------------------------------------------------------------- model side per game
def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def build_models():
    nfl, cfb = jl(D('data', 'nfl_model.json')), jl(D('data', 'cfb_model.json'))
    logos = jl(D('scripts', 'sharp_money_card', 'cfb_logos.json'))
    nba = jl(D('nba', 'data', 'game_model.json'))
    tot = {(r['home_id'], r['away_id']): r for r in cfb['totals']['rows'] if r.get('model_total') is not None}
    return nfl['board'], cfb['board'], logos, nba, tot


def resolve(feed, nflb, cfbb, logos):
    """Map each pick's game key to a model board row (NFL by abbr+kick, CFB by ESPN id, else kick+line)."""
    G = {g['key']: g for g in feed['games']}
    picks, alerts = feed['picks'], feed['alerts']
    out, how = {}, collections.Counter()
    lines = collections.defaultdict(list)
    for r in picks + alerts:
        if r.get('m') == 'sp' and r.get('hline') is not None:
            lines[r['game']].append(r['hline'])
    abbr2id = {}
    for g in feed['games']:
        if g['sport'] != 'cfb':
            continue
        for s in ('home', 'away'):
            i = logos.get(norm(g[s]['name']))
            if i:
                abbr2id[g[s]['abbr']] = i
    info = {}
    for p in picks:
        info.setdefault(p['game'], p)
    for key, p in info.items():
        sp, start = p['sport'], p['start']
        if sp == 'nfl':
            a, h = [ABBR.get(x.strip(), x.strip()) for x in p['gameLbl'].split(' @ ')]
            c = [r for r in nflb if r['home'] == h and r['away'] == a and abs(r['kick'] - start) < 3 * 86400]
            if len(c) == 1:
                out[key] = c[0]; how['nfl abbr'] += 1
            continue
        if sp != 'cfb':
            continue
        ids = None
        g = G.get(key)
        if g:
            ids = (logos.get(norm(g['home']['name'])), logos.get(norm(g['away']['name'])))
        if not ids or None in ids:
            a, h = [x.strip() for x in p['gameLbl'].split(' @ ')]
            ids = (abbr2id.get(h), abbr2id.get(a))
        if None not in ids:
            c = [r for r in cfbb if r['home_id'] == ids[0] and r['away_id'] == ids[1] and abs(r['kick'] - start) < 2 * 86400]
            if len(c) == 1:
                out[key] = c[0]; how['cfb id'] += 1
                continue
        hl = lines.get(key)
        if hl:
            best = []
            for r in cfbb:
                if abs(r['kick'] - start) > 2700:
                    continue
                gap = min(abs(-x - m) for x in hl for m in (r['market_margin'], r['open_margin']) if m is not None)
                best.append((gap, r))
            best.sort(key=lambda t: t[0])
            if best and best[0][0] <= 1.0 and (len(best) == 1 or best[1][0] - best[0][0] > 0.5):
                out[key] = best[0][1]; how['cfb kick+line'] += 1
    return out, how


def model_side(p, row, nba, tot):
    """-> (side the model likes, edge in points, strong?) or None. Edge is measured against the
    read's own line so model and read are compared on the same number."""
    sp, m = p['sport'], p['m']
    if sp == 'nba':
        ab = p['gameLbl'].split(' @ ')
        R = nba['ratings']
        nm = {'NOP': 'NO', 'NYK': 'NY', 'GSW': 'GS', 'SAS': 'SA', 'UTA': 'UTAH', 'WAS': 'WSH', 'BRK': 'BKN', 'PHO': 'PHX'}
        a, h = [nm.get(x.strip(), x.strip()) for x in ab]
        if a not in R or h not in R:
            return None
        mm = R[h]['net'] - R[a]['net'] + nba['hfa']
        if m == 'tot':
            return None
    else:
        if row is None:
            return None
        mm = row['model_margin']
    if m == 'ml':
        return ('home' if mm > 0 else 'away', abs(mm), abs(mm) >= PICK_EDGE[sp])
    if m == 'sp':
        if p.get('hline') is None:
            return None
        e = mm + p['hline']                       # hline is the home spread, so home covers when e > 0
        return ('home' if e > 0 else 'away', abs(e), abs(e) >= PICK_EDGE[sp])
    if m == 'tot' and sp == 'cfb' and row is not None and p.get('line') is not None:
        t = tot.get((row['home_id'], row['away_id']))
        if not t:
            return None
        e = t['model_total'] - p['line']
        return ('over' if e > 0 else 'under', abs(e), abs(e) >= 5)
    return None


# ---------------------------------------------------------------- A. tracked
def tracked(feed, nflb, cfbb, logos, nba, tot):
    rows_by, how = resolve(feed, nflb, cfbb, logos)
    graded = [p for p in feed['picks'] if p.get('result') is not None]
    sides = collections.defaultdict(set)
    for p in feed['picks']:
        sides[(p['game'], p['m'])].add(p['side'])
    rows, cov = [], collections.Counter()
    for p in graded:
        kinds = set(p['kinds']) & BET
        if not kinds:
            continue                                # sharp-only is context, not a read
        conflict = len(sides[(p['game'], p['m'])]) > 1
        sm = p.get('model')                         # stamped by the poller at first sight (or filled once, backfill:true)
        ms = ((sm['side'], sm['edge'], sm['strong']) if sm else None) if 'model' in p else model_side(p, rows_by.get(p['game']), nba, tot)
        cov[p['sport']] += 1
        st = 'none' if ms is None else ('agree' if ms[0] == p['side'] else 'disagree')
        rows.append(dict(sport=p['sport'], m=p['m'], n=len(kinds), model=st,
                         strong=bool(ms and ms[2]), pit=bool(sm and not sm.get('backfill')), conflict=conflict, res=p['result'], units=p.get('units'),
                         game=p['gameLbl'], side=p['side']))
    keep = [r for r in rows if not r['conflict']]

    def tab(sel):
        return {k: pack([r for r in sel if r['model'] == k]) for k in ('agree', 'disagree', 'none')}

    out = dict(
        graded_reads=len(rows), both_sides_dropped=len(rows) - len(keep), joined=dict(how),
        all=tab(keep),
        agree_strong=pack([r for r in keep if r['model'] == 'agree' and r['strong']]),
        disagree_strong=pack([r for r in keep if r['model'] == 'disagree' and r['strong']]),
        by_sport={s: tab([r for r in keep if r['sport'] == s]) for s in ('nfl', 'cfb', 'nba')},
        by_market={m: tab([r for r in keep if r['m'] == m]) for m in ('sp', 'tot', 'ml')},
        by_signals={str(n): tab([r for r in keep if r['n'] == n]) for n in (1, 2, 3)},
        point_in_time=tab([r for r in keep if r['pit']]),
        two_plus=tab([r for r in keep if r['n'] >= 2]),
    )
    return out, keep


# ---------------------------------------------------------------- B. proxy: open->close move
def proxy(nflb, cfbb):
    hist = jl(D('data', 'game_line_history.json'))['games']
    rows = []
    for sp, board in (('cfb', cfbb), ('nfl', nflb)):
        for r in board:
            if r.get('hs') is None or r.get('as_') is None or r.get('market_margin') is None:
                continue                              # board `margin` is from the pick side's view, so rebuild the home margin
            if sp == 'cfb':
                op = r.get('open_margin')
            else:
                k = '2026|regular|%d|%s@%s' % (r['week'], r['away'], r['home'])
                h = hist.get(k) or hist.get(k.replace('@LA', '@LAR').replace('LA@', 'LAR@'))
                o = ((h or {}).get('open') or {}).get('spread')
                op = None if o is None else -o
            if op is None:
                continue
            mv = r['market_margin'] - op             # + means the market moved toward the home side
            if abs(mv) < STEAM[sp]:
                continue
            mside = 'home' if mv > 0 else 'away'
            cov = (r['hs'] - r['as_']) - r['market_margin']   # + means home covered the close
            if cov == 0:
                res = 0
            else:
                res = 1 if (cov > 0) == (mside == 'home') else -1
            e = r['model_margin'] - r['market_margin']
            if e == 0:
                continue
            lean = 'home' if e > 0 else 'away'
            rows.append(dict(sport=sp, res=res, model='agree' if lean == mside else 'disagree',
                             strong=abs(e) >= PICK_EDGE[sp], units=None, mv=abs(mv)))

    def tab(sel):
        return {k: pack([r for r in sel if r['model'] == k]) for k in ('agree', 'disagree')}
    return dict(
        note='Line moved open to close by the steam threshold (NFL 0.5, CFB 1.0). Moved side graded at the closing spread. Model side measured against the closing spread. Proxy only, not the Pinnacle read.',
        all=tab(rows),
        by_sport={s: tab([r for r in rows if r['sport'] == s]) for s in ('nfl', 'cfb')},
        agree_strong=pack([r for r in rows if r['model'] == 'agree' and r['strong']]),
        disagree_strong=pack([r for r in rows if r['model'] == 'disagree' and r['strong']]),
    )


def show(title, t):
    print('\n' + title)
    for k, v in t.items():
        if v is None or 'n' not in v:
            continue
        print('  %-9s %2d-%d-%d  n=%-3d %s  ci=%s  roi=%s%s' % (
            k, v['w'], v['l'], v['p'], v['n'], '%.1f%%' % (v['pct'] * 100) if v['pct'] is not None else '  -  ',
            v['ci'], v['roi'], '  [small]' if v['small'] else ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feed')
    ap.add_argument('--out', default=D('data', 'signal_model_agree.json'))
    a = ap.parse_args()
    feed = load_feed(a.feed)
    nflb, cfbb, logos, nba, tot = build_models()
    A, keep = tracked(feed, nflb, cfbb, logos, nba, tot)
    B = proxy(nflb, cfbb)
    out = dict(generated=feed.get('generated'), tracked=A, proxy=B,
               rules='Sharp accounts are context only and never count toward an agree total. Break-even 52.4% at -110.')
    json.dump(out, open(a.out, 'w'), indent=1)
    print('graded bet-signal reads: %d (both-sides dropped %d); model joins: %s' % (A['graded_reads'], A['both_sides_dropped'], A['joined']))
    show('A. ALL SPORTS, model vs read', A['all'])
    show('   model strong (spread 3+/5+ NFL/CFB, total 5+)', {'agree': A['agree_strong'], 'disagree': A['disagree_strong']})
    for s, t in A['by_sport'].items():
        show('   ' + s, t)
    for s, t in A['by_market'].items():
        show('   market ' + s, t)
    for s, t in A['by_signals'].items():
        show('   %s signals agree' % s, t)
    show('   2+ signals agree', A['two_plus'])
    show('   logged at the time (not backfilled)', A['point_in_time'])
    print('\nB. PROXY open->close move (graded at the close)')
    show('   all', B['all'])
    for s, t in B['by_sport'].items():
        show('   ' + s, t)
    show('   model strong', {'agree': B['agree_strong'], 'disagree': B['disagree_strong']})


if __name__ == '__main__':
    main()
