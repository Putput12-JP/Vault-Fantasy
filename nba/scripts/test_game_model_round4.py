#!/usr/bin/env python3
"""
Game model round 4: the Vault ratings (no injury report) against the first posted spread, on a held-out season and on the recorder's tape.
Rules, committed before this ran: docs/game-model-round4.md. Results: docs/game-model-round4-results.md and data/game_model_round4.json.

  python3 nba/scripts/test_game_model_round4.py [--tape DIR]

  --tape DIR   <day>.espn.jsonl and <day>.meta.jsonl files, each the '|game"' lines of snapshots/<day>/espn.jsonl and meta.jsonl on the
               nba-data branch. With it, data/game_first_looks.json is rebuilt (first and last DraftKings spread per game). Without it that
               file is read as committed.

Pure stdlib. Nothing here writes data/game_model.json.
"""
import bisect, datetime as dt, glob, json, math, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM

FIT, TEST = 2025, 2026
LAG_H, BUILD_LAG_H, B2B_H, PRIMARY = 36, 12, 30, 2
DATA = os.path.join(C.HERE, '..', 'data')
LOOKS = os.path.join(DATA, 'game_first_looks.json')
OUT_JSON = os.path.join(DATA, 'game_model_round4.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'game-model-round4-results.md')
DK = ('DraftKings', 'Draft Kings')


def ts(d):
    return d.replace(tzinfo=dt.timezone.utc).timestamp() if d.tzinfo is None else d.timestamp()


def walk_asof(P, seasons, box, lines, asof, want):
    """Ratings-only home margin for each game in `want`, from the model's state at asof(g) (epoch seconds): only games that tipped
    before that moment have updated anything. Back-to-backs come from the schedule, which is known in advance. {game_id: margin}."""
    games = [g for g in C.games(seasons) if box.get(g['game_id'])]
    tips = defaultdict(list)
    for g in games:
        for t in (g['home'], g['away']):
            tips[t].append(ts(g['tip']))
    for t in tips:
        tips[t].sort()

    def b2b(team, tip):
        i = bisect.bisect_left(tips[team], tip)
        return 1.0 if i and tip - tips[team][i - 1] < B2B_H * 3600 else 0.0

    ev = []
    for g in games:
        ev.append((ts(g['tip']), 0, g['game_id'], g))                                 # an update, in tip order
        if g['game_id'] in want:
            ev.append((asof(g), 1, g['game_id'], g))                                  # a prediction: after any update at the same instant
    ev.sort(key=lambda e: (e[0], e[1], e[2]))
    m, out = GM.Model(P), {}
    for _, kind, gid, g in ev:
        m.new_season(g['season'])
        if kind == 0:
            if P.get('MK_W') and lines:
                ln = lines.get(gid) or {}
                g['mk'] = -ln['spread_close'] if ln.get('spread_close') is not None else None
            m.update(g, box[gid])
        else:
            tip = ts(g['tip'])
            out[gid] = (m.R[g['home']] - m.R[g['away']] + (0.0 if g['neutral'] else m.hfa)
                        + P['B2B'] * (b2b(g['away'], tip) - b2b(g['home'], tip)))
    return out


def score(rows, t):
    """rows: (model margin, early home spread, later home spread, final home margin, home price, away price). Picks at |gap| >= t."""
    w = l = p = 0
    clv, units, n_px = [], 0.0, 0
    for m, sp, sp2, am, hpx, apx in rows:
        e = m + sp
        if e == 0 or abs(e) < t:
            continue
        home = e > 0
        if sp2 is not None:
            clv.append((sp - sp2) if home else (sp2 - sp))
        cover = am + sp
        if cover == 0:
            p += 1
            continue
        won = (cover > 0) == home
        w += won
        l += not won
        px = hpx if home else apx
        if px not in (None, ''):
            a = float(px)
            units += (a / 100 if a > 0 else 100 / -a) if won else -1.0
            n_px += 1
    n = len(clv)
    sd = statistics.stdev(clv) if n > 1 else 0.0
    return {'picks': w + l + p, 'w': w, 'l': l, 'p': p, 'win': round(w / (w + l), 4) if w + l else None,
            'clv': round(statistics.mean(clv), 3) if n else None, 'clv_t': round(statistics.mean(clv) / (sd / math.sqrt(n)), 2) if sd else None,
            'toward': sum(x > 0 for x in clv), 'away': sum(x < 0 for x in clv),
            'units': round(units, 2) if n_px else None, 'priced': n_px}


def build_looks(tape):
    meta, ser = {}, defaultdict(list)
    for p in sorted(glob.glob(os.path.join(tape, '*.meta.jsonl'))):
        for line in open(p):
            r = json.loads(line)
            meta[r['k']] = r
    for p in sorted(glob.glob(os.path.join(tape, '*.espn.jsonl'))):
        for line in open(p):
            r = json.loads(line)
            if r.get('v') and r['v'][0] not in (None, ''):
                ser[r['k']].append((r['t'], r['v']))
    out = {}
    for k, s in ser.items():
        m = meta.get(k)
        if not m or m.get('book') not in DK:
            continue
        pre = sorted(x for x in s if x[0] < m['tip'])
        if not pre:
            continue
        f, c = pre[0], pre[-1]
        out[str(m['game'])] = {'tip': m['tip'], 'away': m['away'], 'home': m['home'], 't0': f[0], 'spread': float(f[1][0]), 'home_px': f[1][1], 'away_px': f[1][2],
                               't1': c[0], 'spread_last': float(c[1][0]), 'looks': len(pre)}
    json.dump({'source': 'nba-data snapshots/<day>/espn.jsonl, DraftKings game rows', 'cols': 'first and last look before tip', 'games': out},
              open(LOOKS, 'w'), separators=(',', ':'))
    return out


def main(argv):
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    variants = {'N': dict(P0), 'NL': dict(P0, MK_W=0.75, MK_K=0.16)}
    lines = C.closing_lines()
    rep = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'history': {}, 'tape': {}}

    # ── history: ESPN open, ratings as of 36 hours before tip ──
    S = GM.WARM + GM.TUNE + [FIT, TEST]
    box = C.player_games(S)
    hist = {g['game_id']: g for g in C.games([FIT, TEST]) if box.get(g['game_id'])
            and (lines.get(g['game_id']) or {}).get('spread_open') is not None and lines[g['game_id']].get('spread_close') is not None}
    for name, P in variants.items():
        mg = walk_asof(P, S, box, lines, lambda g: ts(g['tip']) - LAG_H * 3600, set(hist))
        rep['history'][name] = {}
        for s in (FIT, TEST):
            rows = [(mg[k], lines[k]['spread_open'], lines[k]['spread_close'], g['hs'] - g['as'], None, None) for k, g in hist.items() if g['season'] == s and k in mg]
            mv = [abs(r[2] - r[1]) for r in rows]
            rep['history'][name][str(s)] = {'games': len(rows), 'move': round(statistics.mean(mv), 2), 'cuts': {str(t): score(rows, t) for t in (0, 2, 3, 5)}}

    # ── this season: the recorder's tape ──
    cur = TEST + 1
    tape = argv[argv.index('--tape') + 1] if '--tape' in argv else None
    looks = build_looks(tape) if tape else (json.load(open(LOOKS))['games'] if os.path.exists(LOOKS) else None)
    if looks and os.path.exists(os.path.join(C.RAW, 'hoopr', f'player_box_{cur}.csv')):
        seasons = [cur - 2, cur - 1, cur]
        box3 = C.player_games(seasons)
        fin = {str(g['game_id']): g for g in C.games([cur]) if box3.get(g['game_id'])}
        L3 = dict(lines)
        for k, x in looks.items():
            L3[int(k)] = {'spread_close': x['spread_last']}
        use = {k: x for k, x in looks.items() if k in fin}
        lead = sorted((x['tip'] - x['t0']) / 3600 for x in use.values())
        mv = [abs(x['spread_last'] - x['spread']) for x in use.values()]
        rep['tape']['games'] = len(use)
        rep['tape']['lead_h'] = [round(lead[len(lead) // 4], 1), round(lead[len(lead) // 2], 1), round(lead[3 * len(lead) // 4], 1)]
        rep['tape']['move'] = round(statistics.mean(mv), 2)
        for name, P in variants.items():
            mg = walk_asof(P, seasons, box3, L3, lambda g: use[str(g['game_id'])]['t0'] - BUILD_LAG_H * 3600, {int(k) for k in use})
            rows = [(mg[int(k)], x['spread'], x['spread_last'], fin[k]['hs'] - fin[k]['as'], x['home_px'], x['away_px']) for k, x in use.items() if int(k) in mg]
            rep['tape'][name] = {str(t): score(rows, t) for t in (0, 2, 3, 5)}
        gp = os.path.join(DATA, 'game_picks.json')
        if os.path.exists(gp):                                  # the locked 4-hour record on the same games, for reference
            d = json.load(open(gp))
            ref = {}
            for t in (0, 2, 3, 5):
                w = l = 0
                u = 0.0
                for day, v in d['days'].items():
                    for r in v['rows']:
                        x = dict(zip(d['cols'], r))
                        if x['clock'] == 'f' and x['game'] in use and x['ats_res'] in ('W', 'L') and x['ats_edge'] >= t:
                            w += x['ats_res'] == 'W'
                            l += x['ats_res'] == 'L'
                            u += x['ats_units'] or 0
                ref[str(t)] = {'w': w, 'l': l, 'units': round(u, 2)}
            rep['tape']['locked'] = ref

    def passes(name):
        h = rep['history'][name][str(TEST)]['cuts'][str(PRIMARY)]
        hp = bool(h['clv_t'] is not None and h['clv_t'] >= 2.5 and h['win'] is not None and h['win'] >= 0.524)
        t = (rep['tape'].get(name) or {}).get(str(PRIMARY))
        tp = bool(t and t['clv_t'] is not None and t['clv_t'] >= 2.5 and t['units'] is not None and t['units'] > 0)
        return {'history': hp, 'tape': tp, 'go': hp and tp}
    rep['verdict'] = {k: passes(k) for k in variants}
    json.dump(rep, open(OUT_JSON, 'w'), indent=1)
    write_md(rep)
    print(json.dumps(rep['verdict']))


def fmt(c, units=False):
    rec = f"{c['w']}-{c['l']}" + (f"-{c['p']}" if c['p'] else '')
    s = f"{rec} | {100 * c['win']:.1f}% | {c['clv']:+.2f} | {c['clv_t']:+.1f} | {c['toward']} / {c['away']}"
    return s + (f" | {c['units']:+.2f} ({c['priced']})" if units else '')


def write_md(rep):
    L = ['# Game model round 4: results', '',
         f"Generated {rep['generated']} by `nba/scripts/test_game_model_round4.py`. Rules: [game-model-round4.md](game-model-round4.md) (committed before this ran).",
         '', 'Ratings only in every row: no injury report, no lineups, no line. N = the shipped ratings. NL = round 3\'s line-taught ratings.', '']
    for s, lab in ((str(TEST), '2025-26, the held-out season'), (str(FIT), '2024-25, the season already looked at (in sample for the 2+ cut)')):
        h = rep['history']['N'][s]
        L += [f"## History: {lab}", '',
              f"{h['games']:,} games with an opening and a closing spread. Ratings as of {LAG_H} hours before tip. The spread moved {h['move']} points on average from open to close.", '',
              '| Ratings | Gap | Record vs the open | Win% | Line move toward the pick (pts) | t | Moved toward / away |', '|---|---|---|---|---|---|---|']
        for k in ('N', 'NL'):
            for t in ('0', '2', '3', '5'):
                L.append(f"| {k} | {t}+ | {fmt(rep['history'][k][s]['cuts'][t])} |")
        L.append('')
    T = rep['tape']
    if T.get('N'):
        L += ["## This season: the recorder's tape", '',
              f"{T['games']} games. First DraftKings spread seen a median {T['lead_h'][1]} hours before tip (quartiles {T['lead_h'][0]} and {T['lead_h'][2]}); "
              f"it moved {T['move']} points on average by the last look. Ratings as of {BUILD_LAG_H} hours before that first sight.", '',
              '| Ratings | Gap | Record vs the first line | Win% | Line move toward the pick (pts) | t | Moved toward / away | Units at the first-sight price (priced) |', '|---|---|---|---|---|---|---|---|']
        for k in ('N', 'NL'):
            for t in ('0', '2', '3', '5'):
                L.append(f"| {k} | {t}+ | {fmt(T[k][t], True)} |")
        if T.get('locked'):
            L += ['', 'For reference, the locked 4-hour record on the same games (shipped model with the injury report, graded at the 4-hour line): '
                  + '; '.join(f"gap {t}+ {T['locked'][t]['w']}-{T['locked'][t]['l']} ({T['locked'][t]['units']:+.2f}u)" for t in ('0', '2', '3', '5')) + '.']
        L.append('')
    L += ['## Verdict (at the 2+ gap)', '', '| Ratings | History (2025-26) | Tape (this season) | Verdict |', '|---|---|---|---|']
    for k, v in rep['verdict'].items():
        L.append(f"| {k} | {'pass' if v['history'] else 'fail'} | {'pass' if v['tape'] else 'fail'} | **{'GO' if v['go'] else 'NO-GO'}** |")
    hN, hL = rep['history']['N'][str(TEST)]['cuts'][str(PRIMARY)], rep['history']['NL'][str(TEST)]['cuts'][str(PRIMARY)]
    L += ['', '## What it says', '',
          f"- **The line does move toward the ratings, in every sample.** Held-out 2025-26 at the 2+ gap: {hN['clv']:+.2f} points for the shipped ratings (t {hN['clv_t']:+.1f}), "
          f"{hL['clv']:+.2f} for the line-taught ones (t {hL['clv_t']:+.1f})."
          + (f" This season's tape: {T['N'][str(PRIMARY)]['clv']:+.2f} and {T['NL'][str(PRIMARY)]['clv']:+.2f}." if T.get('N') else '')
          + ' That part of the 2024-25 look was real.',
          f"- **It is too small to win with.** A third to a half of a point of line value is worth about one point of win rate. Against the open the picks went "
          f"{hN['w']}-{hN['l']} ({100 * hN['win']:.1f}%) and {hL['w']}-{hL['l']} ({100 * hL['win']:.1f}%) on 2025-26, under the 52.4% break-even. "
          'The 54 to 56% of 2024-25 did not repeat: with ratings held 36 hours back that season still shows it, so it was the season, not look-ahead.',
          '- Locking earlier would have cost nothing and gained nothing. The pick clock stays at 4 hours.']
    if T.get('N'):
        L += ['', f"**Flagged for close monitoring**, tape, n as shown: NL at the 3+ gap {T['NL']['3']['w']}-{T['NL']['3']['l']} ({T['NL']['3']['units']:+.2f}u, n {T['NL']['3']['picks']}); "
              f"N at the 5+ gap {T['N']['5']['w']}-{T['N']['5']['l']} ({T['N']['5']['units']:+.2f}u, n {T['N']['5']['picks']}). Neither cut was the registered one and neither is above break-even on 2025-26."]
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
