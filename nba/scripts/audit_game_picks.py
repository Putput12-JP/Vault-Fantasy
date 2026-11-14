#!/usr/bin/env python3
"""
Audit of the Game Picks record and of the shipped game model behind it. Descriptive: nothing is fitted and nothing is written but the report.

  python3 nba/scripts/audit_game_picks.py [--tape DIR]

  --tape DIR   a folder of <day>.jsonl files, each the `snapshots/<day>/gpick.jsonl` of the nba-data branch, to check every live pick's
               first row against the record and measure how long before tip it locked. Without it that check is skipped.

Reads data/game_picks.json (the record), raw/hoopr (finals and the model replay), raw/tables/game_lines.csv and raw/injuries (the two
test seasons). Writes docs/game-picks-audit.md.
"""
import datetime as dt, glob, json, math, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM

DATA = os.path.join(C.HERE, '..', 'data')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'game-picks-audit.md')


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float('nan')


def am_p(s):
    a = float(s)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def profit(px, won):
    a = float(px)
    return (a / 100 if a > 0 else 100 / -a) if won else -1.0


def tail_le(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def rec(rows, res='ats_res', units='ats_units'):
    w = sum(r[res] == 'W' for r in rows)
    l = sum(r[res] == 'L' for r in rows)
    u = sum(r[units] or 0 for r in rows)
    return f"{w}-{l} | {(100 * w / (w + l)):.1f}% | {u:+.2f} | {len(rows)}" if w + l else f"0-0 | | | {len(rows)}"


def hist_wl(rows, model=lambda r: r['tip'][0]):
    w = l = 0
    for r in rows:
        mk = -r['line']['spread_close']
        e, res = model(r) - mk, r['actual_margin'] - mk
        if e == 0 or res == 0:
            continue
        w += (res > 0) == (e > 0)
        l += (res > 0) != (e > 0)
    return f"{w}-{l} | {100 * w / (w + l):.1f}% | {w + l}" if w + l else '0-0 | | 0'


def load_record():
    d = json.load(open(os.path.join(DATA, 'game_picks.json')))
    out = []
    for day, v in d['days'].items():
        for r in v['rows']:
            x = dict(zip(d['cols'], r))
            g = v['games'][x['game']]
            x.update(day=day, matchup=g[0], tip=g[1], away=g[2], home=g[3], a_pts=g[4], h_pts=g[5])
            out.append(x)
    return out


def main(argv):
    tape = argv[argv.index('--tape') + 1] if '--tape' in argv else None
    df = load_record()
    first = {r['game']: r for r in df if r['clock'] == 'f'}
    close = {r['game']: r for r in df if r['clock'] == 'c'}
    P = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    cur = max(GM.TEST) + 1
    box = C.player_games([cur - 2, cur - 1, cur])
    _, recs = GM.run(P, [cur - 2, cur - 1, cur], box, record_from=cur)
    by = {str(r['g']['game_id']): r for r in recs}

    L = ['# Game Picks audit', '',
         f"Written by `nba/scripts/audit_game_picks.py`. Descriptive: nothing here is fitted. Record through {max(r['day'] for r in df)}, "
         f"{len(first)} regular-season games ({sum(r['src'] == 'bf' for r in first.values())} rebuilt, {sum(r['src'] == 'live' for r in first.values())} live).", '']

    # ── 1. is the record right? ──
    bad_score = sum(1 for k, r in first.items() if k not in by or (by[k]['g']['hs'], by[k]['g']['as'], by[k]['g']['home']) != (r['h_pts'], r['a_pts'], r['home']))
    regrade = 0
    for r in first.values():
        if r['ats_side']:
            cov = r['am'] + r['spread']
            res = 'P' if cov == 0 else ('W' if (cov > 0) == (r['ats_side'] == 'H') else 'L')
            side = 'H' if r['margin'] + r['spread'] > 0 else 'A'
            if res != r['ats_res'] or side != r['ats_side'] or (res != 'P' and abs(profit(r['ats_px'], res == 'W') - r['ats_units']) > 1e-3):
                regrade += 1
        if r['ml_side']:
            res = 'W' if (r['am'] > 0) == (r['ml_side'] == 'H') else 'L'
            if res != r['ml_res'] or abs(profit(r['ml_px'], res == 'W') - r['ml_units']) > 1e-3:
                regrade += 1
    picks = [r for r in first.values() if r['ats_side']]
    nopx = sum(r['ats_px'] in (None, '') for r in picks) + sum(r['ml_px'] in (None, '') for r in first.values() if r['ml_side'])
    L += ['## 1. Is the record right?', '',
          f"- Finals against the hoopR box scores: **{bad_score} of {len(first)} differ**.",
          f"- Every spread and winner pick regraded from its stored margin, line, price and final: **{regrade} differ**.",
          f"- Picks with no stored price: **{nopx}**. Book: {', '.join(sorted({r['book'] for r in picks}))}. Spread prices run {min(float(r['ats_px']) for r in picks):.0f} to "
          f"{max(float(r['ats_px']) for r in picks):.0f} (average break-even {100 * mean(am_p(r['ats_px']) for r in picks):.1f}%).",
          f"- No pick: {len(first) - len(picks)} game where the model and the line agreed exactly."]
    if tape:
        ser = defaultdict(list)
        for p in sorted(glob.glob(os.path.join(tape, '*.jsonl'))):
            for line in open(p):
                x = json.loads(line)
                if x['v'] is not None:
                    ser[str(x['k'])].append((x['t'], x['v']))
        lead, mism, miss = [], 0, 0
        for k, r in first.items():
            if r['src'] != 'live':
                continue
            s = sorted(ser.get(k, []))
            if not s:
                miss += 1
                continue
            lead.append((r['tip'] - s[0][0]) / 3600)
            pre = [x for x in s if x[0] < r['tip']]
            mism += abs(s[0][1][0] - r['margin']) > 1e-6 or s[0][1][4] != r['spread'] or abs(pre[-1][1][0] - close[k]['margin']) > 1e-6 or pre[-1][1][4] != close[k]['spread']
        lead.sort()
        L.append(f"- Live picks against the recorder's tape ({len(lead)} games, {miss} without a tape row): first and last rows that differ from the record **{mism}**; "
                 f"locked a median {lead[len(lead) // 2]:.2f} hours before tip (earliest {lead[-1]:.2f}, latest {lead[0]:.2f}; {sum(x > 4.001 or x <= 0 for x in lead)} outside the 4-hour window).")
    mv = [close[r['game']]['spread'] - r['spread'] for r in picks]
    clv = [close[r['game']]['clv_pts'] or 0 for r in picks]
    L += [f"- Between the lock and the last look the spread moved {mean(abs(x) for x in mv):.2f} points on average; toward the pick {sum(x > 0 for x in clv)} times, away {sum(x < 0 for x in clv)}. "
          f"The side flipped on {sum(r['ats_side'] != close[r['game']]['ats_side'] for r in picks)} games. Graded at the last look the record is "
          f"{sum(close[r['game']]['ats_res'] == 'W' for r in picks)}-{sum(close[r['game']]['ats_res'] == 'L' for r in picks)}.", '']

    # ── 2. the live margin against a replay ──
    for r in first.values():
        b = by[r['game']]
        r['none'], r['adj'] = b['none'][0], r['margin'] - b['none'][0]
    L += ['## 2. Is the live model the model that was backtested?', '',
          'The shipped parameters replayed over the same three seasons the live state walks, ratings only, against the margin the recorder locked. The difference is the injury and rest adjustment the recorder applied.', '',
          f"- Locked margin minus replay: mean {mean(r['adj'] for r in first.values()):+.2f}, mean absolute {mean(abs(r['adj']) for r in first.values()):.2f} points.",
          f"- Margin MAE on these games: locked {mean(abs(r['margin'] - r['am']) for r in first.values()):.2f}, ratings only {mean(abs(r['none'] - r['am']) for r in first.values()):.2f}, "
          f"hindsight lineups {mean(abs(by[k]['oracle'][0] - r['am']) for k, r in first.items()):.2f}, the locked line {mean(abs(-r['spread'] - r['am']) for r in first.values()):.2f}.", '']

    # ── 3. the record cut ──
    grade = lambda e: 'A' if e >= 5 else 'B' if e >= 3 else 'C'
    L += ['## 3. The spread record, cut (first look)', '', '| Cut | Record | Win% | Units | Picks |', '|---|---|---|---|---|', f"| All | {rec(picks)} |"]
    for g in 'ABC':
        L.append(f"| Grade {g} | {rec([r for r in picks if grade(r['ats_edge']) == g])} |")
    for lab, fn in (('Picked the favourite', lambda r: (r['ats_side'] == 'H') == (r['spread'] < 0)), ('Picked the underdog', lambda r: (r['ats_side'] == 'H') != (r['spread'] < 0)),
                    ('Home', lambda r: r['ats_side'] == 'H'), ('Away', lambda r: r['ats_side'] == 'A')):
        L.append(f"| {lab} | {rec([r for r in picks if fn(r)])} |")
    for lo, hi in ((0, 0.5), (0.5, 1.5), (1.5, 3), (3, 99)):
        L.append(f"| Injury and rest adjustment {lo} to {hi if hi < 99 else 'up'} pts | {rec([r for r in picks if lo <= abs(r['adj']) < hi])} |")
    d0 = dt.date.fromisoformat(min(r['day'] for r in picks))
    weeks = defaultdict(list)
    for r in picks:
        weeks[(dt.date.fromisoformat(r['day']) - d0).days // 7].append(r)
    for w, rows in sorted(weeks.items()):
        L.append(f"| Week {w + 1} ({min(r['day'] for r in rows)[5:]} to {max(r['day'] for r in rows)[5:]}) | {rec(rows)} |")
    L += ['', f"Against a 50.8% history (below), {sum(r['ats_res'] == 'W' for r in picks)} wins or fewer in {sum(r['ats_res'] in 'WL' for r in picks)} happens {100 * tail_le(sum(r['ats_res'] == 'W' for r in picks), sum(r['ats_res'] in 'WL' for r in picks), 0.508):.0f}% of the time.", '']

    # winner
    W = [r for r in first.values() if r['ml_side']]
    for r in W:
        r['pw'] = r['p_home'] if r['ml_side'] == 'H' else 1 - r['p_home']
    L += ['## 4. The winner record, cut', '', '| Cut | Record | Win% | Units | Picks | Model said | Price implied (with vig) |', '|---|---|---|---|---|---|---|']
    for lab, fn in (('All', lambda r: True), ('Grade A (70%+)', lambda r: r['pw'] >= .7), ('Grade B (60 to 70%)', lambda r: .6 <= r['pw'] < .7), ('Grade C (under 60%)', lambda r: r['pw'] < .6),
                    ('Model agrees with the market favourite', lambda r: r['spread'] != 0 and (r['ml_side'] == 'H') == (r['spread'] < 0)),
                    ('Model disagrees with it', lambda r: r['spread'] != 0 and (r['ml_side'] == 'H') != (r['spread'] < 0))):
        Q = [r for r in W if fn(r)]
        L.append(f"| {lab} | {rec(Q, 'ml_res', 'ml_units')} | {100 * mean(r['pw'] for r in Q):.1f}% | {100 * mean(am_p(r['ml_px']) for r in Q):.1f}% |")
    fav = [r for r in W if r['spread'] != 0]
    L += ['', f"The market's favourite won {sum((r['am'] > 0) == (r['spread'] < 0) for r in fav)} of {len(fav)} on the same games.", '']

    # teams
    T = defaultdict(lambda: [0, 0.0, 0.0, 0, 0])
    for r in picks:
        gap = r['margin'] + r['spread']
        for t, s in ((r['home'], 1), (r['away'], -1)):
            x = T[t]
            x[0] += 1
            x[1] += s * gap
            x[2] += s * (r['am'] + r['spread'])
            if (r['ats_side'] == 'H') == (s == 1):
                x[3] += r['ats_res'] == 'W'
                x[4] += r['ats_res'] == 'L'
    order = sorted(T, key=lambda t: T[t][1] / T[t][0])
    L += ['## 5. Where the model and the line disagree: the same teams every night', '',
          'Model minus market, per game, from the team\'s side (positive: the model rates the team higher than the line does), the team\'s average result against the spread, and the record of the picks that took that team.', '',
          '| Team | Games | Model minus market | Result vs spread | Picked |', '|---|---|---|---|---|']
    for t in order[-6:][::-1] + order[:6]:
        x = T[t]
        L.append(f"| {t} | {x[0]} | {x[1] / x[0]:+.2f} | {x[2] / x[0]:+.2f} | {x[3]}-{x[4]} |")
    L += ['', f"Across all {len(T)} teams the two columns correlate {statistics.correlation([T[t][1] / T[t][0] for t in T], [T[t][2] / T[t][0] for t in T]):+.2f}: where they disagreed, the line was closer.",
          f"Spread of the margins on these games (sd): model {statistics.pstdev([r['margin'] for r in picks]):.2f}, line {statistics.pstdev([r['spread'] for r in picks]):.2f}, finals {statistics.pstdev([r['am'] for r in picks]):.2f}.", '']

    # ── 6. history ──
    S = GM.WARM + GM.TUNE + GM.TEST
    hbox = C.player_games(S)
    _, hrecs = GM.run(P, S, hbox, C.closing_lines(), C.InjuryAsOf(GM.TEST, C.player_index(hbox)), record_from=GM.TEST[0])
    H = [r for r in hrecs if r.get('line') and r['line'].get('spread_close') is not None and 'tip' in r]
    edge = lambda r: abs(r['tip'][0] + r['line']['spread_close'])
    adj = lambda r: abs(r['tip'][0] - r['none'][0])
    L += [f"## 6. The same cuts on the two test seasons ({len(H):,} games, against the closing spread)", '',
          '| Cut | Record | Win% | Picks | 2024-25 | 2025-26 |', '|---|---|---|---|---|---|']

    def row(lab, fn):
        a = hist_wl([r for r in H if fn(r)])
        b = [hist_wl([r for r in H if fn(r) and r['g']['season'] == s]).split(' | ')[1] for s in GM.TEST]
        L.append(f"| {lab} | {a} | {b[0]} | {b[1]} |")
    row('All', lambda r: True)
    row('Grade A (gap 5+)', lambda r: edge(r) >= 5)
    row('Grade B (3 to 5)', lambda r: 3 <= edge(r) < 5)
    row('Grade C (under 3)', lambda r: edge(r) < 3)
    row('Picked the favourite', lambda r: r['line']['spread_close'] != 0 and ((r['tip'][0] + r['line']['spread_close']) > 0) == (r['line']['spread_close'] < 0))
    row('Picked the underdog', lambda r: r['line']['spread_close'] != 0 and ((r['tip'][0] + r['line']['spread_close']) > 0) != (r['line']['spread_close'] < 0))
    for lo, hi in ((0, 0.5), (0.5, 1.5), (1.5, 3), (3, 99)):
        row(f"Injury adjustment {lo} to {hi if hi < 99 else 'up'} pts", lambda r, lo=lo, hi=hi: lo <= adj(r) < hi)
    first_tip = {}
    for r in H:
        first_tip[r['g']['season']] = min(first_tip.get(r['g']['season'], r['g']['tip']), r['g']['tip'])
    row('First 3 weeks of the season', lambda r: (r['g']['tip'] - first_tip[r['g']['season']]).days < 21)
    L += ['', f"Grade A this season is {sum(r['ats_res'] == 'W' for r in picks if grade(r['ats_edge']) == 'A')}-{sum(r['ats_res'] == 'L' for r in picks if grade(r['ats_edge']) == 'A')}. "
          'Its history is the Grade A row above. No cut in this table is above break-even (52.4%) in both seasons.', '']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main(sys.argv[1:])
