#!/usr/bin/env python3
"""Which book's prop close is the best benchmark? Scores each book's closing P(over) against what happened.

For every settled NFL prop in data/bet_results.json that has a book read on the prop close tape (live tape plus the
Kalshi git-replay backfill), each book is asked one question at ONE shared line (the consensus close line): what chance
did you give the over? That chance is scored against the box score with log loss and Brier. The book whose closing
chance is closest to reality is the better yardstick for closing line value.

  - Same line for every book. A book that closed at another line is skipped for that prop, not interpolated, unless
    --interp is passed (then a ladder is read between its two bracketing strikes).
  - Pushes are dropped. A read older than --max-age-min before kickoff is dropped (that is not a close).
  - Pairwise gaps (book A minus book B, log loss, lower is better) use only props where BOTH priced, with a paired
    bootstrap 95% CI over props. A gap only counts when the CI excludes zero AND n >= MIN_N.
  - The over tax: mean P(over) a book priced vs how often the over actually hit.

What this cannot say: who the market FOLLOWS (speed). That needs line-move history per book; the tape stores closes only.

  python3 scripts/compare_prop_closes.py [--tape data/prop_close_tape.json | --tape-ref origin/sharp-data:prop_close_tape.json]
                                          [--backfill data/kalshi_prop_closes_backfill.json] [--interp] [--write]
"""
import argparse
import datetime as dt
import json
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from prop_close_lib import book_p_over, devig, log_loss, brier
from build_prop_close_tape import tape_key, iso_s

MIN_N = 150                   # fewest shared props before a gap can be called
BOOTSTRAP = 2000
SHARP = ['Pinnacle', 'Novig', 'Kalshi']
CONTROLS = ['Consensus', 'FanDuel', 'DraftKings']
BOOKS = SHARP + CONTROLS


def read_tape(path, ref):
    if ref:
        out = subprocess.run(['git', '-C', ROOT, 'show', ref], capture_output=True, text=True)
        return json.loads(out.stdout)['props'] if out.returncode == 0 and out.stdout.strip() else {}
    return json.load(open(path))['props'] if path and os.path.exists(path) else {}


def merge(live, backfill):
    """Live tape wins per book; the backfill fills in books the live tape never saw."""
    out = {k: {**v, 'books': dict(v['books'])} for k, v in backfill.items()}
    for k, v in live.items():
        if k in out:
            out[k]['books'].update(v['books'])
        else:
            out[k] = v
    return out


def rows(tape, results, kickoffs, team_nfl, max_age_s, interp):
    """One record per settled, non-push prop: {key, market, won_over, p: {book: P(over)}}."""
    out, seen = [], set()
    for r in results:
        if (r.get('seasonType') or '').lower() == 'pre' or r.get('actual') is None or r.get('line_close') is None:
            continue
        ko = kickoffs.get((str(r['season']), str(r['week']), team_nfl(r.get('team'))))
        if not ko:
            continue
        key = tape_key(r['season'], r['pid'], r['market'], ko)
        if key in seen:
            continue
        seen.add(key)
        line, actual = float(r['line_close']), float(r['actual'])
        if abs(actual - line) < 1e-9:
            continue
        kt = iso_s(ko)
        p = {}
        entry = tape.get(key)
        for b in SHARP + ['FanDuel', 'DraftKings']:
            e = ((entry or {}).get('books') or {}).get(b)
            if not e or (e.get('t') and kt - e['t'] > max_age_s) or (e.get('t') and e['t'] >= kt):
                continue
            v = book_p_over(e, line, interp)
            if v is not None:
                p[b] = v
        cons = devig(r.get('close_over'), r.get('close_under'))
        if cons is not None:
            p['Consensus'] = cons
        if p:
            out.append({'key': key, 'market': r['market'], 'won_over': actual > line, 'p': p})
    return out


def single(rs, book):
    xs = [(x['p'][book], x['won_over']) for x in rs if book in x['p']]
    n = len(xs)
    if not n:
        return {'n': 0}
    return {'n': n, 'log_loss': round(sum(log_loss(p, w) for p, w in xs) / n, 4),
            'brier': round(sum(brier(p, w) for p, w in xs) / n, 4),
            'mean_p_over': round(sum(p for p, _ in xs) / n, 4), 'over_hit_rate': round(sum(w for _, w in xs) / n, 4)}


def pair(rs, a, b, seed=7):
    """Log-loss of A minus B on props where both priced (negative = A closes closer to the truth)."""
    d = [log_loss(x['p'][a], x['won_over']) - log_loss(x['p'][b], x['won_over']) for x in rs if a in x['p'] and b in x['p']]
    n = len(d)
    if n < 2:
        return {'a': a, 'b': b, 'n': n}
    mean = sum(d) / n
    rng = random.Random(seed)
    boots = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOTSTRAP))
    lo, hi = boots[int(.025 * BOOTSTRAP)], boots[int(.975 * BOOTSTRAP) - 1]
    verdict = 'too few' if n < MIN_N else (f'{a} closer' if hi < 0 else f'{b} closer' if lo > 0 else 'no difference')
    return {'a': a, 'b': b, 'n': n, 'gap': round(mean, 4), 'ci95': [round(lo, 4), round(hi, 4)], 'verdict': verdict}


def build(rs):
    pairs = [(a, b) for i, a in enumerate(SHARP) for b in SHARP[i + 1:]] + [(a, c) for a in SHARP for c in CONTROLS]
    return {'props_scored': len(rs), 'min_n': MIN_N,
            'by_book': {b: single(rs, b) for b in BOOKS},
            'all_three_sharp': sum(all(s in x['p'] for s in SHARP) for x in rs),
            'pairs': [pair(rs, a, b) for a, b in pairs],
            'markets': {m: sum(x['market'] == m for x in rs) for m in sorted({x['market'] for x in rs})}}


def markdown(res, notes):
    L = ['# Prop close comparison', '',
         'Each book\'s closing chance of the over, at one shared line, scored against the box score. Lower log loss and '
         'Brier mean the close was nearer the truth. Generated by `scripts/compare_prop_closes.py`.', '', *notes, '',
         f"Props scored: **{res['props_scored']}** (all three sharp books priced on {res['all_three_sharp']}).", '',
         '| Book | Props | Log loss | Brier | Priced P(over) | Over hit rate |', '|---|---|---|---|---|---|']
    for b, s in res['by_book'].items():
        L.append(f"| {b} | {s['n']} | " + (' | '.join(str(s[k]) for k in ('log_loss', 'brier', 'mean_p_over', 'over_hit_rate')) if s['n'] else '- | - | - | -') + ' |')
    L += ['', f"Gap = log loss of A minus B on props both priced (negative: A is closer). A gap counts only when the 95% CI excludes zero and n is at least {res['min_n']}.", '',
          '| A | B | Shared props | Gap | 95% CI | Read |', '|---|---|---|---|---|---|']
    for p in res['pairs']:
        L.append(f"| {p['a']} | {p['b']} | {p['n']} | " + (f"{p['gap']:+.4f} | {p['ci95'][0]:+.4f} to {p['ci95'][1]:+.4f} | {p['verdict']} |" if 'gap' in p else '- | - | too few |'))
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tape', default=os.path.join(ROOT, 'data', 'prop_close_tape.json'))
    ap.add_argument('--tape-ref', help='git ref:path of the live tape, e.g. origin/sharp-data:prop_close_tape.json')
    ap.add_argument('--backfill', default=os.path.join(ROOT, 'data', 'kalshi_prop_closes_backfill.json'))
    ap.add_argument('--max-age-min', type=float, default=180)
    ap.add_argument('--interp', action='store_true')
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    import settle_bets
    live, back = read_tape(a.tape, a.tape_ref), read_tape(a.backfill, None)
    tape = merge(live, back)
    results = json.load(open(os.path.join(ROOT, 'data', 'bet_results.json')))['props']
    rs = rows(tape, results, settle_bets.load_kickoffs(), settle_bets.team_nfl, a.max_age_min * 60, a.interp)
    res = build(rs)
    res['generated'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    res['sources'] = {'live_tape_props': len(live), 'kalshi_backfill_props': len(back), 'max_age_min': a.max_age_min, 'interp': a.interp}
    notes = [f"Sources: live tape {len(live)} props, Kalshi git-replay backfill {len(back)} props. Reads older than {a.max_age_min:.0f} minutes before kickoff are dropped."
             + (' Ladders read between bracketing strikes.' if a.interp else ' Ladders read at the exact strike only.')]
    md = markdown(res, notes)
    print(md)
    if a.write:
        json.dump(res, open(os.path.join(ROOT, 'data', 'prop_close_comparison.json'), 'w'), indent=1)
        open(os.path.join(ROOT, 'docs', 'prop-close-comparison.md'), 'w').write(md)


if __name__ == '__main__':
    main()
