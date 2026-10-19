#!/usr/bin/env python3
"""Independent closing-line value for the prop board calls, and a test of which closing reference is sharpest.

Why: the tracker stores CLV = closeFair / calledPrice - 1 where closeFair is the board's last fair from the SAME source that raised the call
(Pinnacle for 97% of calls). If that fair does not move, CLV equals the call's own claimed edge, so it cannot confirm the edge
(docs/retro/sharp-v2-evidence.md, section 3). This re-grades each call against closes that did NOT make the call, read from the prop close tape
(scripts/build_prop_close_tape.py): every book's last read before kickoff.

References, all read at the call's exact line (a book at another line is skipped, never interpolated; a read older than --max-age-min before
kickoff is not a close and is dropped; pushes are dropped):
  Pinnacle   two-way price, de-vigged (prop_close_lib.devig)
  Exchange   mean of Kalshi and Novig P(over line) where the ladder has that strike
  Books      mean of the US book two-way prices, de-vigged (Caesars, FanDuel, DraftKings, bet365, BetMGM, BetRivers, Fanatics, Parx)
  Sharp3     equal-weight mean of whichever of Pinnacle, Kalshi, Novig priced (the same SHARP list compare_prop_closes.py uses; no weights fitted)

Sharpness test (same rule as compare_prop_closes.py): log loss of each reference's P(over) against the box score on props where both priced, with a
paired bootstrap 95% CI. A reference is called closer only when the CI excludes zero and n >= MIN_N.

Modes:
  report (default)  reads origin/sharp-data (or --plays/--tape), writes docs/retro/prop-clv-regrade.md and docs/prop-clv-regrade.json
  --write FILE      also merges closeX / clvX / closeXSrc into the prop_plays.json at FILE (graded or started plays), and stamps `atCall` (the
                    references at first sight) on open plays that have none yet. Never touches an existing field of the ledger other than these.
usage: regrade_prop_clv.py [--plays prop_plays.json] [--tape prop_close_tape.json] [--write prop_plays.json] [--max-age-min 180]"""
import argparse, datetime as dt, json, math, os, random, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from prop_close_lib import book_p_over, log_loss, brier
from build_prop_close_tape import tape_key

MIN_N = 150
BOOTSTRAP = 2000
EXCH = ('Kalshi', 'Novig')
US_BOOKS = ('Caesars', 'FanDuel', 'DraftKings', 'bet365', 'BetMGM', 'BetRivers', 'Fanatics', 'Parx Casino')
r4 = lambda x: None if x is None else round(x, 4)
mean = lambda xs: sum(xs) / len(xs) if xs else None


def branch_json(name):
    out = subprocess.run(['git', '-C', ROOT, 'show', 'origin/sharp-data:' + name], capture_output=True)
    if out.returncode != 0 or not out.stdout.strip():
        raise SystemExit('cannot read origin/sharp-data:' + name)
    return json.loads(out.stdout)


def tape_entry(tape, play):
    """The tape entry for a play (keyed on the game's UTC kickoff date)."""
    d = dt.datetime.fromtimestamp(play['start'], dt.timezone.utc)
    for day in (d, d - dt.timedelta(days=1)):
        e = tape.get(tape_key(play['season'], play['pid'], play['mkt'], day.strftime('%Y-%m-%d')))
        if e:
            return e
    return None


def refs(entry, line, kickoff, max_age_s, asof=None):
    """{Pinnacle, Kalshi, Novig, Exchange, Books, Sharp3} P(over line), only from reads that are real closes (before kickoff, not stale).
    asof: treat reads as of this time instead of the kickoff (used for the at-call stamp, where 'stale' is measured from now)."""
    ref_t = asof if asof is not None else kickoff
    p = {}
    for b, e in ((entry or {}).get('books') or {}).items():
        t = e.get('t')
        if t is None or t >= kickoff or ref_t - t > max_age_s:
            continue
        v = book_p_over(e, line, False)
        if v is not None:
            p[b] = v
    o = {}
    if 'Pinnacle' in p: o['Pinnacle'] = p['Pinnacle']
    for b in EXCH:
        if b in p: o[b] = p[b]
    ex = [p[b] for b in EXCH if b in p]
    if ex: o['Exchange'] = mean(ex)
    us = [p[b] for b in US_BOOKS if b in p]
    if us: o['Books'] = mean(us)
    s3 = [p[b] for b in ('Pinnacle',) + EXCH if b in p]
    if s3: o['Sharp3'] = mean(s3)
    return o


def side_p(p_over, side):
    return p_over if side == 'over' else 1 - p_over


def regrade(plays, tape, max_age_s):
    """One row per graded, non-push play with a tape entry: references as P(over), outcome and the stored numbers."""
    rows = []
    for p in plays.values():
        if p.get('status') not in ('won', 'lost') or p.get('actual') is None:
            continue
        e = tape_entry(tape, p)
        if not e:
            continue
        r = refs(e, p['line'], p['start'], max_age_s)
        if not r:
            continue
        rows.append(dict(id=p['id'], mkt=p['label'], side=p['side'], start=p['start'], won=p['status'] == 'won', won_over=p['actual'] > p['line'],
                         price=p['called']['p'], fair=p['called'].get('fair'), fair_src=p['called'].get('fairSrc'), old_close=p.get('closeFair'), old_clv=p.get('clv'),
                         refs=r, units=p.get('units')))
    return rows


def clv_of(row, ref):
    v = row['refs'].get(ref)
    return None if v is None else side_p(v, row['side']) / row['price'] - 1


def summarize_clv(rows, ref):
    xs = [(clv_of(r, ref), r) for r in rows if ref in r['refs']]
    if not xs:
        return dict(n=0)
    c = [x for x, _ in xs]
    hit = mean([1 if r['won'] else 0 for _, r in xs])
    mp = mean([side_p(r['refs'][ref], r['side']) for _, r in xs])
    var = sum(side_p(r['refs'][ref], r['side']) * (1 - side_p(r['refs'][ref], r['side'])) for _, r in xs)
    z = (sum(1 for _, r in xs if r['won']) - sum(side_p(r['refs'][ref], r['side']) for _, r in xs)) / math.sqrt(var) if var else None
    old = [r['old_clv'] for _, r in xs if r['old_clv'] is not None]
    return dict(n=len(xs), clv=r4(mean(c)), share_positive=r4(mean([1 if x > 0 else 0 for x in c])), mean_close_p=r4(mp), hit=r4(hit),
                hit_minus_close_pts=r4((hit - mp) * 100), z_hit_vs_close=r4(z), old_stored_clv_same_rows=r4(mean(old)) if old else None,
                price_beat_close_wins=sum(1 for x, r in xs if x > 0 and r['won']), price_beat_close=sum(1 for x, _ in xs if x > 0))


def pair(rs, a, b, seed=7):
    """Log loss of A minus B on props where both priced (negative = A is closer to what happened)."""
    d = [log_loss(x['refs'][a], x['won_over']) - log_loss(x['refs'][b], x['won_over']) for x in rs if a in x['refs'] and b in x['refs']]
    n = len(d)
    if n < 2:
        return dict(a=a, b=b, n=n, verdict='too few')
    m = sum(d) / n
    rng = random.Random(seed)
    boots = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOTSTRAP))
    lo, hi = boots[int(.025 * BOOTSTRAP)], boots[int(.975 * BOOTSTRAP) - 1]
    v = 'too few' if n < MIN_N else (f'{a} closer' if hi < 0 else f'{b} closer' if lo > 0 else 'no difference')
    return dict(a=a, b=b, n=n, gap=r4(m), ci95=[r4(lo), r4(hi)], verdict=v)


def single(rs, ref):
    xs = [(x['refs'][ref], x['won_over']) for x in rs if ref in x['refs']]
    n = len(xs)
    if not n:
        return dict(n=0)
    return dict(n=n, log_loss=r4(sum(log_loss(p, w) for p, w in xs) / n), brier=r4(sum(brier(p, w) for p, w in xs) / n),
                mean_p_over=r4(sum(p for p, _ in xs) / n), over_hit_rate=r4(sum(w for _, w in xs) / n))


def report(rows):
    names = ['Pinnacle', 'Kalshi', 'Novig', 'Exchange', 'Books', 'Sharp3']
    rs = [dict(r, p=r['refs']) for r in rows]
    out = dict(graded_with_tape=len(rows), min_n=MIN_N,
               by_ref={n: single(rs, n) for n in names},
               clv_by_ref={n: summarize_clv(rows, n) for n in names},
               pairs=[pair(rs, a, b) for a, b in (('Exchange', 'Pinnacle'), ('Exchange', 'Books'), ('Pinnacle', 'Books'), ('Sharp3', 'Pinnacle'), ('Sharp3', 'Exchange'), ('Kalshi', 'Pinnacle'), ('Novig', 'Pinnacle'))])
    # the headline subset: calls whose fair came from Pinnacle, re-graded against the exchange close (a close that did not raise the call)
    pin_calls = [r for r in rows if r['fair_src'] == 'Pinnacle']
    out['pinnacle_called_vs_exchange_close'] = summarize_clv(pin_calls, 'Exchange')
    out['pinnacle_called_vs_books_close'] = summarize_clv(pin_calls, 'Books')
    both = [r for r in pin_calls if 'Exchange' in r['refs'] and 'Pinnacle' in r['refs']]
    out['pinnacle_called_both_closes'] = dict(n=len(both), old_stored_clv=r4(mean([r['old_clv'] for r in both if r['old_clv'] is not None])),
                                              clv_vs_own_pinnacle_close=r4(mean([clv_of(r, 'Pinnacle') for r in both])), clv_vs_exchange_close=r4(mean([clv_of(r, 'Exchange') for r in both])))
    # does a positive CLV against an independent close go with winning? (hindsight check on the close, not a rule that could be used at call time)
    def roi_slice(xs):
        if not xs:
            return dict(n=0)
        return dict(n=len(xs), w=sum(1 for r in xs if r['won']), roi=r4(mean([r['units'] for r in xs])), hit=r4(mean([1 if r['won'] else 0 for r in xs])))
    ex = [r for r in rows if 'Exchange' in r['refs'] and r['units'] is not None]
    pn = [r for r in ex if 'Pinnacle' in r['refs']]
    out['roi_by_exchange_clv'] = dict(
        beat_exchange_close=roi_slice([r for r in ex if clv_of(r, 'Exchange') > 0]), missed_exchange_close=roi_slice([r for r in ex if clv_of(r, 'Exchange') <= 0]),
        beat_both_exchange_and_pinnacle=roi_slice([r for r in pn if clv_of(r, 'Exchange') > 0 and clv_of(r, 'Pinnacle') > 0]),
        beat_neither=roi_slice([r for r in pn if clv_of(r, 'Exchange') <= 0 and clv_of(r, 'Pinnacle') <= 0]),
        beat_exchange_by_2pts=roi_slice([r for r in ex if clv_of(r, 'Exchange') > 0.02]))
    # by market, exchange close
    byk = {}
    for r in rows:
        if 'Exchange' in r['refs']:
            byk.setdefault(r['mkt'] + ' ' + r['side'], []).append(r)
    out['exchange_clv_by_market_side'] = {k: summarize_clv(v, 'Exchange') for k, v in sorted(byk.items()) if len(v) >= 15}
    return out


def md(res, max_age):
    L = ['# Prop CLV re-grade: independent closes and the sharpest reference', '',
         'Generated by `scripts/regrade_prop_clv.py` from the prop ledger and the prop close tape on `sharp-data`. '
         f'Reads older than {max_age} minutes before kickoff are dropped, ladders are read at the exact strike, pushes are dropped.', '',
         f"Graded calls with a usable tape close: **{res['graded_with_tape']}**.", '',
         '## Which close is nearest to what happened', '',
         '| Reference | Props | Log loss | Brier | Priced P(over) | Over hit rate |', '|---|---|---|---|---|---|']
    for b, s in res['by_ref'].items():
        L.append(f"| {b} | {s['n']} | " + (' | '.join(str(s[k]) for k in ('log_loss', 'brier', 'mean_p_over', 'over_hit_rate')) if s['n'] else '- | - | - | -') + ' |')
    L += ['', f"Gap = log loss of A minus B on props both priced (negative: A is closer). A gap counts only when the 95% CI excludes zero and n is at least {res['min_n']}.", '',
          '| A | B | Shared props | Gap | 95% CI | Read |', '|---|---|---|---|---|---|']
    for p in res['pairs']:
        L.append(f"| {p['a']} | {p['b']} | {p['n']} | " + (f"{p['gap']:+.4f} | {p['ci95'][0]:+.4f} to {p['ci95'][1]:+.4f} | {p['verdict']} |" if 'gap' in p else '- | - | too few |'))
    L += ['', '## CLV of the calls, old and new', '',
          'Old = the stored CLV on the same rows (close taken from the fair that raised the call). New = price against a close that did not raise it.', '',
          '| Close used | Calls | New CLV | Calls with CLV above 0 | Old stored CLV, same rows | Hit rate | Mean close P | Hit minus close (pts) | z |', '|---|---|---|---|---|---|---|---|---|']
    for b, s in res['clv_by_ref'].items():
        if not s['n']:
            continue
        L.append(f"| {b} | {s['n']} | {s['clv'] * 100:+.2f}% | {s['share_positive'] * 100:.1f}% | {s['old_stored_clv_same_rows'] * 100:+.2f}% | {s['hit'] * 100:.1f}% | {s['mean_close_p'] * 100:.1f}% | {s['hit_minus_close_pts']:+.1f} | {s['z_hit_vs_close']:+.2f} |")
    pb = res['pinnacle_called_both_closes']
    L += ['', f"Calls whose fair was Pinnacle and that have both a Pinnacle and an exchange close ({pb['n']}): old stored CLV {pb['old_stored_clv'] * 100:+.2f}%, "
              f"CLV against their own Pinnacle close {pb['clv_vs_own_pinnacle_close'] * 100:+.2f}%, against the exchange close {pb['clv_vs_exchange_close'] * 100:+.2f}%." if pb['n'] else '']
    rb = res['roi_by_exchange_clv']
    L += ['', '## Does beating the independent close go with winning?', '',
          'Hindsight check on the close, not a rule that could be used at call time. ROI is flat 1u at the called price.', '', '| Calls that | Calls | W | Hit | ROI |', '|---|---|---|---|---|']
    for k, lab in (('beat_exchange_close', 'beat the exchange close'), ('missed_exchange_close', 'missed the exchange close'), ('beat_exchange_by_2pts', 'beat it by more than 2%'),
                   ('beat_both_exchange_and_pinnacle', 'beat both exchange and Pinnacle closes'), ('beat_neither', 'beat neither close')):
        x = rb[k]
        L.append(f"| {lab} | {x['n']} | " + (f"{x['w']} | {x['hit'] * 100:.1f}% | {x['roi'] * 100:+.1f}% |" if x['n'] else '- | - | - |'))
    L += ['', '## Exchange-close CLV by market and side (15+ calls)', '', '| Market | Calls | New CLV | Hit | Mean close P |', '|---|---|---|---|---|']
    for k, s in res['exchange_clv_by_market_side'].items():
        L.append(f"| {k} | {s['n']} | {s['clv'] * 100:+.2f}% | {s['hit'] * 100:.1f}% | {s['mean_close_p'] * 100:.1f}% |")
    return '\n'.join(L) + '\n'


def write_back(path, tape, max_age_s, now):
    """Merge closeX/clvX into started plays and stamp atCall on open ones. Only these fields are ever written."""
    with open(path) as f:
        L = json.load(f)
    plays = L.get('plays') or {}
    n_close = n_stamp = 0
    for p in plays.values():
        e = tape_entry(tape, p)
        if not e:
            continue
        if now >= p['start'] and p.get('status') != 'void':
            r = refs(e, p['line'], p['start'], max_age_s)
            ex = r.get('Exchange')
            if ex is not None:
                p['closeX'] = r4(side_p(ex, p['side']))
                p['clvX'] = r4(side_p(ex, p['side']) / p['called']['p'] - 1)
                p['closeXSrc'] = 'exchange'
                n_close += 1
            elif p.get('closeX') is not None:
                pass
        elif p.get('status') == 'open' and not p.get('atCall'):
            r = refs(e, p['line'], p['start'], max_age_s, asof=now)
            if r:
                p['atCall'] = {k: r4(side_p(v, p['side'])) for k, v in r.items() if k in ('Pinnacle', 'Exchange', 'Books', 'Sharp3')}
                p['atCallAt'] = int(now)
                n_stamp += 1
    L['plays'] = plays
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(L, f)
    os.replace(tmp, path)
    return n_close, n_stamp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plays'); ap.add_argument('--tape'); ap.add_argument('--write')
    ap.add_argument('--max-age-min', type=int, default=180)
    ap.add_argument('--out-json', default=os.path.join(ROOT, 'docs', 'prop-clv-regrade.json'))
    ap.add_argument('--out-md', default=os.path.join(ROOT, 'docs', 'retro', 'prop-clv-regrade.md'))
    ap.add_argument('--no-report', action='store_true')
    a = ap.parse_args()
    ma = a.max_age_min * 60
    def jl(path):
        with open(path) as f:
            return json.load(f)
    plays = (jl(a.plays) if a.plays else branch_json('prop_plays.json'))['plays']
    tape = (jl(a.tape) if a.tape else branch_json('prop_close_tape.json'))['props']
    if a.write:
        c, s = write_back(a.write, tape, ma, time.time())
        print(f'closeX/clvX set on {c} plays, atCall stamped on {s} open plays')
    if not a.no_report:
        res = report(regrade(plays, tape, ma))
        os.makedirs(os.path.dirname(a.out_md), exist_ok=True)
        text = md(res, a.max_age_min)
        with open(a.out_json, 'w') as f:
            json.dump(res, f, indent=1)
        with open(a.out_md, 'w') as f:
            f.write(text)
        print(text)


if __name__ == '__main__':
    main()
