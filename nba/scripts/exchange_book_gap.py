#!/usr/bin/env python3
"""
Exchange price gap vs the US books: grader for the shadow test frozen in docs/exchange-book-gap-prereg.md (PR 480). Context only: nothing here
is a pick, a size, a gate or an agree total, and nothing reads this file but the results read.

For every NBA prop with an exchange read (Novig `novigdepth`, Kalshi `kaldepth`) and US-book prices (`actionprops`) at the same line, before tip:
  exchange side  a side the exchange prices above the best book's no-vig probability for that side (gap = exchange mid - best book, points)
  best book      per book with BOTH sides at that line, the no-vig over chance; the side's best = the highest probability for that side
                 (the most conservative gap). Needs 2 or more books.
  cohort A       gap >= GAP and exchange depth on that side >= DEEP
  control B      gap >= GAP and depth < THIN
  control C      depth >= DEEP and |gap| < FLAT
  first look     the first pre-tip read that qualifies, one row per exchange x prop x line x side; its cohort is fixed there
  last look      the last pre-tip US-book state at the same line (a line that moved, no later look, or fewer than 2 books is left out and counted)
  move           books' best probability for that side, last minus first look, in points. Positive = the books moved toward the exchange.

Standard errors are clustered by game. Each exchange is read on its own. Not in this version (named in the prereg as context, not tests):
win rate of the exchange side and the overlap with `p_dep` alerts.

Forward sample: snapshot days from the first day a `kaldepth.jsonl` exists. `--from=YYYY-MM-DD` overrides it for a DRY RUN only; the output is then
marked dry_run and must not be read as the test.

  python3 nba/scripts/exchange_book_gap.py --dir=nba-data [--out=nba/data/exchange_book_gap.json] [--from=YYYY-MM-DD]
reads <dir>/snapshots/<day>/{actionprops,novigdepth,kaldepth,kalshi}.jsonl and meta.jsonl. Stateless: rebuilt from the records every run.
"""
import collections, datetime as dt, glob, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nba_common import name_key
from backfill_kalshi import parse_event

HERE = os.path.dirname(os.path.abspath(__file__))
GAP, DEEP, THIN, FLAT, TIGHT = 0.03, 250, 100, 0.01, 0.10     # frozen in the prereg
MIN_BOOKS = 2
MIN_N, MIN_GAMES, MIN_SPAN_DAYS, Z_BAR = 500, 30, 28, 2.0
EXCH = ('novig', 'kalshi')
COHORTS = ('A', 'B', 'C')
KAL_STAT = {'KXNBAPTS': 'pts', 'KXNBAREB': 'reb', 'KXNBAAST': 'ast', 'KXNBA3PT': '3pm', 'KXNBAPRA': 'pra', 'KXNBAPR': 'pr', 'KXNBAPA': 'pa', 'KXNBARA': 'ra'}
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/New_York')
except Exception:                                              # pragma: no cover
    ET = None


def et_day(t):
    return dt.datetime.fromtimestamp(t, ET).date().isoformat()


def am_p(a):
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(a) or a == 0 or -100 < a < 100:
        return None
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def rows_of(path):
    if not os.path.exists(path):
        return
    for ln in open(path):
        try:
            o = json.loads(ln)
            o['k'], o['t']
        except (ValueError, KeyError, TypeError):
            continue
        yield o


def load_meta(path):
    out = collections.defaultdict(dict)
    for o in rows_of_meta(path):
        out[o.get('src')][o['k']] = o
    return out


def rows_of_meta(path):
    if not os.path.exists(path):
        return
    for ln in open(path):
        try:
            o = json.loads(ln)
            o['k'], o['src']
        except (ValueError, KeyError, TypeError):
            continue
        yield o


def roster(path):
    """{pid: name} from the projections file (Novig keys props by our player id)."""
    try:
        p = json.load(open(path))
    except (OSError, ValueError):
        return {}
    return {str(x['id']): x['name'] for t in (p.get('teams') or {}).values() for x in t.get('players') or []}


def load_day(root, day, names):
    """-> (books, reads, skipped). books: {(day, namekey, stat): [(t, book, side, line, odds), ...]} and info {(day,nk,stat): (tip, action game id)}.
    reads: [(exchange, (day, nk, stat), t, line, bid, ask, over$, under$)]."""
    d = os.path.join(root, 'snapshots', day)
    meta = load_meta(os.path.join(d, 'meta.jsonl'))
    skipped = collections.Counter()
    books, info = collections.defaultdict(list), {}
    am = meta.get('actionprops', {})
    for o in rows_of(os.path.join(d, 'actionprops.jsonl')):
        m = am.get(o['k'])
        if not m or not m.get('start'):
            skipped['book row without meta'] += 1
            continue
        pid_key = (et_day(m['start']), name_key(m.get('player')), m['stat'])
        v = o.get('v')
        books[pid_key].append((o['t'], m['book'], m['side'], v[0] if v else None, v[1] if v else None))
        info.setdefault(pid_key, (m['start'], str(m['game'])))
    reads = []
    tips = {k: m['tip'] for k, m in meta.get('espn', {}).items() if k.endswith('|game') and m.get('tip')}
    gtip = {m['game']: m['tip'] for m in meta.get('espn', {}).values() if m.get('tip')}
    for o in rows_of(os.path.join(d, 'novigdepth.jsonl')):
        v = o.get('v')
        m = meta.get('novigdepth', {}).get(o['k'])
        if not v or not m or len(v) < 4:
            continue
        name, tip = names.get(str(m['p'])), gtip.get(str(m['g']))
        if not name or not tip:
            skipped['novig prop without name or tip'] += 1
            continue
        reads.append(('novig', (et_day(tip), name_key(name), m['s']), o['t'], m['line'], v[0], v[1], v[2], v[3]))
    km = meta.get('kalshi', {})
    for o in rows_of(os.path.join(d, 'kaldepth.jsonl')):
        v, m = o.get('v'), km.get(o['k'])
        if not v or not m or len(v) < 4:
            continue
        stat = KAL_STAT.get(m.get('series'))
        ev = next(iter(parse_event(m['event']) or []), None)
        if not stat or ev is None or m.get('floor') is None:
            skipped['kalshi rung unmapped'] += 1
            continue
        reads.append(('kalshi', (ev[0], name_key((m.get('sub') or m.get('title') or '').split(':')[0]), stat), o['t'], m['floor'], v[0], v[1], v[2], v[3]))
    return books, info, reads, skipped


def state_at(events, t, line):
    """Per book with BOTH sides priced at `line` as of time t (events sorted by time): the no-vig over chance. -> [p_over]."""
    cur = {}
    for et_, book, side, ln, odds in events:
        if et_ > t:
            break
        cur.setdefault(book, {})[side] = None if ln is None else (ln, odds)
    out = []
    for b in cur.values():
        o, u = b.get('over'), b.get('under')
        if not o or not u or o[0] != line or u[0] != line:
            continue
        po, pu = am_p(o[1]), am_p(u[1])
        if po is None or pu is None:
            continue
        out.append(po / (po + pu))
    return out


def side_best(p_overs, side):
    return max(p_overs) if side == 'over' else 1 - min(p_overs)


def cohort(gap, depth):
    if gap >= GAP and depth >= DEEP:
        return 'A'
    if gap >= GAP and depth < THIN:
        return 'B'
    if depth >= DEEP and abs(gap) < FLAT:
        return 'C'
    return None


def observe(books, info, reads, skipped):
    """The first-look rows, each with its move to the last pre-tip book state."""
    for ev in books.values():
        ev.sort(key=lambda x: x[0])
    seen, out = set(), []
    for exch, pk, t, line, bid, ask, d_over, d_under in sorted(reads, key=lambda r: r[2]):
        ev, inf = books.get(pk), info.get(pk)
        if not ev or not inf:
            skipped['exchange prop with no US-book prices'] += 1
            continue
        tip, gid = inf
        if t >= tip:
            continue
        if bid is None or ask is None or not (0 < bid <= ask < 1) or ask - bid > TIGHT:
            skipped['exchange quote missing or wider than 10c'] += 1
            continue
        pb = state_at(ev, t, line)
        if len(pb) < MIN_BOOKS:
            skipped['fewer than 2 books with both sides at the line'] += 1
            continue
        mid = (bid + ask) / 2
        for side, p_ex, depth in (('over', mid, d_over), ('under', 1 - mid, d_under)):
            key = (exch, pk, line, side)
            if key in seen or depth is None:
                continue
            p_first = side_best(pb, side)
            gap = p_ex - p_first
            c = cohort(gap, depth)
            if not c:
                continue
            seen.add(key)
            last_t = max((e[0] for e in ev if e[0] < tip), default=None)
            if last_t is None or last_t <= t:
                skipped['no later US-book look'] += 1
                continue
            pl = state_at(ev, last_t, line)
            if len(pl) < MIN_BOOKS:
                skipped['line moved or fewer than 2 books at the last look'] += 1
                continue
            out.append(dict(exch=exch, cohort=c, game=gid, day=pk[0], tip=tip, t=t, stat=pk[2], side=side, gap=round(gap, 4), depth=depth,
                            move=round(side_best(pl, side) - p_first, 5)))
    return out


def stat(rs):
    """n, games, mean move, game-clustered SE, z"""
    if not rs:
        return dict(n=0, games=0, move=None, se=None, z=None)
    G = collections.defaultdict(list)
    for r in rs:
        G[r['game']].append(r['move'])
    n = len(rs)
    mu = sum(r['move'] for r in rs) / n
    se = math.sqrt(sum((sum(v) - mu * len(v)) ** 2 for v in G.values())) / n
    return dict(n=n, games=len(G), move=round(mu, 5), se=round(se, 5), z=round(mu / se, 2) if se else None)


def halves(rs):
    rs = sorted(rs, key=lambda r: (r['tip'], r['game']))
    h = len(rs) // 2
    return [stat(rs[:h]), stat(rs[h:])]


def cleared(rs, span):
    """Criteria 1 to 3 of the prereg for one cohort: n, games and span, mean - 2 SE > 0, same sign in both halves."""
    st = stat(rs)
    if st['n'] < MIN_N or st['games'] < MIN_GAMES or span < MIN_SPAN_DAYS:
        return False
    if st['move'] is None or st['se'] is None or st['move'] - Z_BAR * st['se'] <= 0:
        return False
    return all(h['move'] is not None and h['move'] > 0 for h in halves(rs))


def verdict(by_cohort, span):
    """Prereg wording: cleared = criteria 1 to 4; killed = mean - 2 SE below 0 at n >= 500. Read literally, that kill also fires on a mean that is
    positive but under 2 SE, so at n >= 500 the only outcomes are cleared and killed. Flagged in the PR for the user; not softened here."""
    a = by_cohort['A']
    st = stat(a)
    if st['n'] >= MIN_N and st['se'] is not None and st['move'] - Z_BAR * st['se'] < 0:
        return 'killed'
    if st['n'] < MIN_N or st['games'] < MIN_GAMES or span < MIN_SPAN_DAYS:
        return 'collecting'
    if cleared(a, span) and not cleared(by_cohort['B'], span) and not cleared(by_cohort['C'], span):
        return 'cleared'
    return 'not cleared'


def build(root, names, start=None):
    days = sorted(os.path.basename(p) for p in glob.glob(os.path.join(root, 'snapshots', '20*')))
    kd = [d for d in days if os.path.exists(os.path.join(root, 'snapshots', d, 'kaldepth.jsonl'))]
    first = start or (kd[0] if kd else None)
    use = [d for d in days if first and d >= first]
    rows, skipped = [], collections.Counter()
    for d in use:
        b, i, r, s = load_day(root, d, names)
        skipped.update(s)
        rows += observe(b, i, r, skipped)
    span = (dt.date.fromisoformat(use[-1]) - dt.date.fromisoformat(use[0])).days + 1 if use else 0
    res = {'rule': {'gap': GAP, 'deep': DEEP, 'thin': THIN, 'flat': FLAT, 'tight': TIGHT, 'min_books': MIN_BOOKS, 'doc': 'nba/docs/exchange-book-gap-prereg.md',
                    'bar': f'n >= {MIN_N}, games >= {MIN_GAMES}, span >= {MIN_SPAN_DAYS} days, mean - {Z_BAR:g} SE > 0, same sign in both halves, neither control clears'},
           'forward_from': first, 'dry_run': bool(start), 'days': len(use), 'span_days': span, 'skipped': dict(skipped), 'exchanges': {}}
    for e in EXCH:
        by = {c: [r for r in rows if r['exch'] == e and r['cohort'] == c] for c in COHORTS}
        res['exchanges'][e] = {'verdict': verdict(by, span),
                               'cohorts': {c: dict(stat(by[c]), halves=halves(by[c]) if by[c] else None) for c in COHORTS},
                               'A_by_stat': {s: stat([r for r in by['A'] if r['stat'] == s]) for s in sorted({r['stat'] for r in by['A']})},
                               'A_by_side': {s: stat([r for r in by['A'] if r['side'] == s]) for s in ('over', 'under')}}
    return res


def main():
    a = dict(x.lstrip('-').split('=', 1) for x in sys.argv[1:] if '=' in x)
    root = a.get('dir', 'nba-data')
    out = a.get('out', os.path.join(HERE, '..', 'data', 'exchange_book_gap.json'))
    res = build(root, roster(os.path.join(HERE, '..', 'data', 'player_projections.json')), a.get('from'))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(res, open(out, 'w'), separators=(',', ':'))
    for e, x in res['exchanges'].items():
        c = x['cohorts']
        print(f"exchange_book_gap {e}: {x['verdict']}" + ''.join(f"  {k} n={v['n']} g={v['games']} move={v['move']} z={v['z']}" for k, v in c.items())
              + (' [DRY RUN]' if res['dry_run'] else ''))
    if not res['forward_from']:
        print('exchange_book_gap: no kaldepth.jsonl yet, nothing to grade')


if __name__ == '__main__':
    main()
