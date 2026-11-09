#!/usr/bin/env python3
"""
Sharp Money "Top Reads" ledger and forward-test ladder.

Reads the Sharp Money state (state.json, prop_plays.json) plus the stored book tape and writes two files into --dir:

  topreads_ledger.json   append-only. One row per signal key, written once at first sighting and never pruned:
                           game signals:  <game>|<market>|<side>          (Top Reads with bet kinds line / money / behind,
                                                                           and non-sharp alerts behind / split / steam / whale)
                           prop calls:    <player>|<prop>|<game>|<side>   (Sharp Money Props page calls, NFL)
                         state.picks prunes at 60 days and state.alerts keeps a rolling window, so rows already in the
                         previous ledger are carried forward untouched; only result, units, kinds_later and new rule
                         matches are filled in later. Point-in-time fields are never overwritten.
  topreads_record.json   small summary the pages read: headline, slices, per-rule forward record and stage, today's
                         qualifying firings, proven plays, and sharp money as context only.

Prices are never invented. A row is priced (units_1u) only at a real US sportsbook on the whitelist (data/topreads_rules.json
us_books). A game row whose own signal has no US-book price gets the best whitelisted US-book price for that side AT THE SAME
NUMBER from data/book_tape/<sport>/*.jsonl, using each book's latest tape row at or before the firing (and before kickoff; a latest row without the market means the book
pulled it, so the row stays unpriced at that book),
only when that row is at most TAPE_MAX_AGE_H old (the tape appends a row only when a book's line changes, so an older row is
still that book's line, but past 12h we cannot be sure the book is still dealing it). Otherwise the row stays unpriced and only
its win-loss is kept. Pinnacle, pick'em apps (Underdog, PrizePicks, ...), state-limited books (Parx, ...), Fliff and every
exchange (Kalshi, Polymarket, Novig, ...) are never a bet price.

Sharp money (Polymarket sharp accounts, cross alerts, sharp-account whales, sharp-only reads) is context only. It never creates a
ledger row, never counts toward a rule, and its record is published separately under "context".

Usage:
  python3 scripts/build_topreads_ledger.py --dir=sharp-out [--rules=data/topreads_rules.json] [--tape=data/book_tape] [--now=UNIX]
  python3 scripts/build_topreads_ledger.py --selftest
  python3 scripts/build_topreads_ledger.py --hash          (print the canonical hash of every rule: id, version, predicate, frozen_at)
Stdlib only, Python 3.11.
"""
import collections, copy, datetime as dt, glob, hashlib, json, math, os, random, re, sys, tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CT = ZoneInfo('America/Chicago')
LEDGER_V = 1
TAPE_MAX_AGE_H = 12.0
NFL_ALIAS = {'WSH': 'WAS', 'LA': 'LAR', 'JAC': 'JAX', 'LVR': 'LV', 'OAK': 'LV'}
NONSHARP_ALERTS = {'behind', 'split', 'steam', 'whale'}
SHARP_ALERTS = {'sharp', 'cross'}
BET_KINDS = {'line', 'money', 'behind'}
HOLDOUT_FROM = int(dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc).timestamp())   # edge hunt split (games on/after)

# Stage and meter thresholds
METER_MIN_N, METER_MIN_DAYS = 50, 6
PROVING_N, PROVING_DAYS, BEST_DAY_SHARE = 75, 8, 0.40
PROVEN_N, PROVEN_GAMES, BOOT_DRAWS, BOOT_SEED, BOOT_P = 150, 60, 2000, 20261109, 0.01
PRICE_TO_BEAT_MIN_N = 50

# ── book names ─────────────────────────────────────────────────────────────
US_CANON = {
    'draftkings': 'DraftKings', 'dk': 'DraftKings', 'draftkingssportsbook': 'DraftKings',
    'fanduel': 'FanDuel', 'fd': 'FanDuel', 'fanduelsportsbook': 'FanDuel',
    'betmgm': 'BetMGM', 'mgm': 'BetMGM',
    'caesars': 'Caesars', 'caesarssportsbook': 'Caesars', 'czr': 'Caesars', 'williamhill': 'Caesars', 'williamhillus': 'Caesars',
    'fanatics': 'Fanatics', 'fanaticssportsbook': 'Fanatics',
    'betrivers': 'BetRivers', 'rivers': 'BetRivers', 'sugarhouse': 'BetRivers',
    'bet365': 'bet365', 'b365': 'bet365',
}
PICKEM_SUBSTR = ('underdog', 'prizepicks', 'sleeper', 'dabble', 'pick6', 'parlayplay', 'chalkboard', 'fliff', 'ownersbox', 'splashsports')
PICKEM_EXACT = {'betr', 'betrpicks', 'splash'}      # exact only: 'betr' is a prefix of 'betrivers'
EXCHANGE_KEYS = ('kalshi', 'polymarket', 'novig', 'prophetx', 'prophet', 'sporttrade', 'betfair', 'exchange', 'onyx')
OFFSHORE_KEYS = ('pinnacle', 'pin', 'bookmaker', 'bovada', 'betonline', 'mybookie', 'betus', 'heritage', 'circa', 'lowvig', 'betcris')
NONE_KEYS = ('consensus', 'open', 'opener', 'market', 'avg', 'average', '')


def book_key(name):
    return re.sub(r'[^a-z0-9]', '', str(name or '').lower())


def norm_book(name):
    """(canonical name, venue). venue: us_book | state_limited | offshore | pickem | exchange | none.
    Pick'em is checked first so 'DraftKings Pick6' never reads as DraftKings."""
    k = book_key(name)
    if not k or k in NONE_KEYS:
        return (name or None), 'none'
    if k in PICKEM_EXACT or any(p in k for p in PICKEM_SUBSTR):
        return name, 'pickem'
    if any(k == p or k.startswith(p) for p in EXCHANGE_KEYS):
        return name, 'exchange'
    if k in US_CANON:
        return US_CANON[k], 'us_book'
    if any(k == p or k.startswith(p) for p in OFFSHORE_KEYS):
        return name, 'offshore'
    # Parx, betParx, Hard Rock, ESPN BET, BetWay, Bally, Betfred, Unibet, SI, WynnBet and anything unknown: never a bet price
    return name, 'state_limited'


# ── small helpers ──────────────────────────────────────────────────────────
def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def am_ok(a):
    return num(a) is not None and abs(a) >= 100


def am_profit(a):
    return a / 100.0 if a > 0 else 100.0 / -a


def am_implied(a):
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def prob_to_am(p):
    """The American price whose implied chance is at most p. Rounded up, so the price never needs a higher win rate than p."""
    if p is None or not (0 < p < 1):
        return None
    return int(math.ceil(-100.0 * p / (1 - p))) if p >= 0.5 else int(math.ceil(100.0 * (1 - p) / p))


def units_for(result, american):
    if result is None or not am_ok(american):
        return None
    return round(am_profit(american), 4) if result == 1 else (-1.0 if result == -1 else 0.0)


def iso_utc(t):
    return None if t is None else dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def ct_str(t):
    if t is None:
        return None
    d = dt.datetime.fromtimestamp(t, CT)
    return d.strftime('%a %b ') + str(d.day) + d.strftime(', ') + d.strftime('%I:%M %p').lstrip('0') + ' CT'


def ct_day(t):
    return None if t is None else dt.datetime.fromtimestamp(t, CT).strftime('%Y-%m-%d')


def parse_iso(s):
    return int(dt.datetime.fromisoformat(s).timestamp())


def band_of(p):
    if p is None:
        return None
    if p < 0.30:
        return 'long dog'
    if p < 0.45:
        return 'dog'
    if p < 0.55:
        return "pick'em"
    if p < 0.70:
        return 'fav'
    return 'heavy fav'


def timing_of(h):
    if h is None:
        return None
    return '24h+' if h >= 24 else '3-24h' if h >= 3 else 'under 3h'


def canon_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def rule_hash(rule):
    """Hash of everything that defines a frozen rule: id, version, predicate and frozen_at. Moving frozen_at earlier would
    otherwise turn pre-freeze rows into forward rows on the next run, and tags are never removed."""
    return canon_hash({'id': rule['id'], 'version': rule['version'], 'predicate': rule['predicate'], 'frozen_at': rule['frozen_at']})


def norm_team(s):
    return NFL_ALIAS.get(s, s)


# ── book tape ──────────────────────────────────────────────────────────────
class Tape:
    """US-book rows only: {(gk, book): [rows by t]}. NFL rows carry no gk and are matched by teams + kickoff."""

    def __init__(self, tape_dir, nfl_games):
        self.rows = collections.defaultdict(list)
        self.stats = collections.Counter()
        self.newest = {}
        nfl_lookup = collections.defaultdict(list)
        for gk, (lbl, start) in nfl_games.items():
            if ' @ ' in (lbl or ''):
                a, h = lbl.split(' @ ', 1)
                nfl_lookup[(norm_team(a), norm_team(h))].append((start, gk))
        if not tape_dir or not os.path.isdir(tape_dir):
            self.stats['no_tape_dir'] = 1
            return
        for f in sorted(glob.glob(os.path.join(tape_dir, '*', '*.jsonl'))):
            sport = os.path.basename(os.path.dirname(f))
            with open(f) as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        self.stats['bad_lines'] += 1
                        continue
                    bk, venue = norm_book(r.get('book'))
                    if venue != 'us_book' or not any(k in r for k in ('ml', 'sp', 'tot')):
                        continue
                    gk = r.get('gk')
                    if not gk and sport == 'nfl':
                        cands = nfl_lookup.get((norm_team(r.get('away')), norm_team(r.get('home'))), [])
                        best = min(cands, key=lambda c: abs(c[0] - (r.get('start') or 0)), default=None)
                        if best and abs(best[0] - (r.get('start') or 0)) <= 6 * 3600:
                            gk = best[1]
                    if not gk or num(r.get('t')) is None:
                        self.stats['rows_unmatched'] += 1
                        continue
                    self.stats['rows_used'] += 1
                    self.rows[(gk, bk)].append(r)
                    self.newest[sport] = max(self.newest.get(sport, 0), r['t'])
        for v in self.rows.values():
            v.sort(key=lambda r: r['t'])

    def quote(self, gk, book, m, side, hline, line, t, start):
        """That book's price for side at the row's number from its latest row at or before t (and before kickoff)."""
        rows = self.rows.get((gk, book))
        if not rows:
            return None
        lim = min(t, start - 1)
        lo, hi = 0, len(rows)
        while lo < hi:
            mid = (lo + hi) // 2
            if rows[mid]['t'] <= lim:
                lo = mid + 1
            else:
                hi = mid
        i = lo - 1
        if i < 0:
            return None
        r = rows[i]
        # tape rows are full snapshots: a latest row without this market means the book had pulled it, so an older price is not dealt
        if not r.get(m):
            return None
        age_h = (t - r['t']) / 3600.0
        if age_h > TAPE_MAX_AGE_H:
            return None
        arr = r[m]
        if m == 'ml':
            price = arr[0] if side == 'away' else arr[1] if side == 'home' else None
        elif m == 'sp':
            if hline is None or arr[0] != hline:
                return None
            price = arr[1] if side == 'home' else arr[2] if side == 'away' else None
        elif m == 'tot':
            if line is None or arr[0] != line:
                return None
            price = arr[1] if side == 'over' else arr[2] if side == 'under' else None
        else:
            return None
        if not am_ok(price):
            return None
        return {'price': price, 'book': book, 'age_h': round(age_h, 2), 'tape_t': r['t']}

    def best_us(self, gk, m, side, hline, line, t, start):
        best = None
        for b in sorted(set(US_CANON.values())):
            q = self.quote(gk, b, m, side, hline, line, t, start)
            if q and (best is None or am_profit(q['price']) > am_profit(best['price'])):
                best = q
        return best


# ── signal events from state ───────────────────────────────────────────────
def side_number(m, side, hline, line):
    if m == 'sp':
        return None if hline is None else (hline if side == 'home' else -hline)
    if m == 'tot':
        return line
    return None


def game_events(S):
    """Non-sharp game signals, sharp context signals. Each event: dict with key, ts, kind, src_ref, ..."""
    ev, ctx = [], []
    for a in S.get('alerts') or []:
        typ, start, ts = a.get('type'), num(a.get('start')), num(a.get('ts'))
        if start is None or ts is None or ts >= start or a.get('m') not in ('ml', 'sp', 'tot') or not a.get('side'):
            continue
        m = a['m']
        hline = num(a.get('hline')) if m == 'sp' else None
        line = num(a.get('line')) if m == 'tot' else None
        e = {'key': f"{a['game']}|{m}|{a['side']}", 'game': a['game'], 'sport': a.get('sport'), 'label': a.get('gameLbl'),
             'start': start, 'ts': ts, 'm': m, 'side': a['side'], 'hline': hline, 'line': line, 'fair': num(a.get('fair')),
             'src_ref': f"alert:{a.get('id')}", 'text': a.get('text'), 'type': typ, 'source': 'alert'}
        is_sharp = typ in SHARP_ALERTS or (typ == 'whale' and a.get('cls') == 'sharp')
        if typ == 'behind' or typ == 'cross':
            e['sig_book'], e['sig_price'] = a.get('book'), num(a.get('price'))
        elif typ == 'whale' or typ == 'sharp':
            e['sig_book'], e['sig_price'] = (a.get('src') or ('Polymarket' if typ == 'sharp' else 'Exchange')), None
            e['sig_px'] = num(a.get('px'))
        if is_sharp:
            e['kind'] = 'sharp' if typ != 'whale' else 'sharp_whale'
            ctx.append(e)
        elif typ in NONSHARP_ALERTS:
            e['kind'] = typ
            ev.append(e)
    for k, p in (S.get('picks') or {}).items():
        kinds = sorted(set(p.get('kinds') or []) & BET_KINDS)
        start, ts = num(p.get('start')), num(p.get('ts'))
        if not kinds or start is None or ts is None or ts >= start or p.get('m') not in ('ml', 'sp', 'tot'):
            continue
        m = p['m']
        e = {'key': f"{p['game']}|{m}|{p['side']}", 'game': p['game'], 'sport': p.get('sport'), 'label': p.get('gameLbl'),
             'start': start, 'ts': ts, 'm': m, 'side': p['side'], 'hline': num(p.get('hline')) if m == 'sp' else None,
             'line': num(p.get('line')) if m == 'tot' else None, 'fair': num(p.get('fair')), 'src_ref': f'pick:{k}',
             'text': '; '.join(f'{x}: {(p.get("sig") or {}).get(x)}' for x in kinds), 'type': 'top_read', 'source': 'top_read',
             'kinds': kinds, 'sig_book': 'Pinnacle', 'sig_price': num(p.get('price')),
             'context': p.get('context')}
        ev.append(e)
    for k, p in (S.get('sharpContext') or {}).items():
        start, ts = num(p.get('start')), num(p.get('ts'))
        if start is None or ts is None or ts >= start or p.get('m') not in ('ml', 'sp', 'tot'):
            continue
        m = p['m']
        ctx.append({'key': f"{p['game']}|{m}|{p['side']}", 'game': p['game'], 'sport': p.get('sport'), 'label': p.get('gameLbl'),
                    'start': start, 'ts': ts, 'm': m, 'side': p['side'], 'hline': num(p.get('hline')) if m == 'sp' else None,
                    'line': num(p.get('line')) if m == 'tot' else None, 'fair': num(p.get('fair')), 'src_ref': f'sctx:{k}',
                    'text': p.get('context') or (p.get('sig') or {}).get('sharp'), 'type': 'sharp_read', 'source': 'sharp_read',
                    'kind': 'sharp_read', 'sig_book': 'Pinnacle', 'sig_price': None})
    return ev, ctx


def prop_events(PP, nfl_game_at):
    out = []
    for pid, p in ((PP or {}).get('plays') or {}).items():
        c = p.get('called') or {}
        start, ts = num(p.get('start')), num(p.get('firstSeen'))
        if start is None or ts is None or ts >= start or p.get('side') not in ('over', 'under'):
            continue
        wk = f"{p.get('season')}w{p.get('week')}"
        game = nfl_game_at.get((start, norm_team(p.get('team')))) or f"nfl:{wk}:{p.get('team')}"
        out.append({'key': f"nfl:{p.get('pid')}|{p.get('mkt')}|{wk}|{p['side']}", 'game': game, 'sport': 'nfl',
                    'label': f"{p.get('name')} ({p.get('team')} {p.get('pos')})", 'player': p.get('name'), 'team': p.get('team'),
                    'prop': p.get('mkt'), 'prop_label': p.get('label'), 'start': start, 'ts': ts, 'm': 'prop', 'side': p['side'],
                    'hline': None, 'line': num(p.get('line')), 'fair': num(c.get('fair')), 'src_ref': f'prop:{pid}',
                    'type': 'prop_call', 'source': 'prop_call', 'kind': 'prop_call', 'sig_book': c.get('src'),
                    'sig_price': num(c.get('am')), 'sig_p': num(c.get('p')), 'text': None})
    return out


def result_lookup(S, PP):
    res = {}
    for a in S.get('alerts') or []:
        r = a.get('result')
        res[f"alert:{a.get('id')}"] = r if r in (1, 0, -1) else None
    for k, p in (S.get('picks') or {}).items():
        r = p.get('result')
        res[f'pick:{k}'] = r if r in (1, 0, -1) else None
    for k, p in (S.get('sharpContext') or {}).items():
        r = p.get('result')
        res[f'sctx:{k}'] = r if r in (1, 0, -1) else None
    for k, p in ((PP or {}).get('plays') or {}).items():
        st = p.get('status')
        # void = the player did not play: the book refunds it, so it settles as a push (0 units)
        res[f'prop:{k}'] = {'won': 1, 'lost': -1, 'push': 0, 'void': 0}.get(st)
    return res


# ── rules ──────────────────────────────────────────────────────────────────
def load_rules(path):
    R = json.load(open(path))
    rules = R['rules']
    if R.get('us_books') and set(R['us_books']) != set(US_CANON.values()):
        raise SystemExit(f"registry us_books {sorted(R['us_books'])} differ from the script's whitelist {sorted(set(US_CANON.values()))}")
    for r in rules:
        h = rule_hash(r)
        if r.get('rule_hash') != h:
            raise SystemExit(f"rule {r['id']}: rule_hash does not match its id, version, predicate and frozen_at ({h}); a frozen rule cannot change in place")
        r['_frozen_ts'] = parse_iso(r['frozen_at'])
    return R, rules


def rule_candidate(pred, e):
    """Does event e belong to the rule's base population (source/type/sport/market/side)? Price and timing are checked on
    the FIRST such event per key only, so a later event can never stand in for a first one that failed the rule."""
    if pred.get('source') and e['source'] != pred['source']:
        return False
    if pred.get('type') and e['type'] != pred['type']:
        return False
    sp = pred.get('sport')
    if sp and e.get('sport') not in (sp if isinstance(sp, list) else [sp]):
        return False
    if pred.get('market') and e['m'] != pred['market']:
        return False
    if pred.get('side') and e['side'] != pred['side']:
        return False
    return True


def rule_fire(pred, e):
    """Point-in-time rule entry for the first candidate event, or None when it fails the rule."""
    hb = (e['start'] - e['ts']) / 3600.0
    if pred.get('min_hours_before') is not None and hb < pred['min_hours_before']:
        return None
    book, venue = norm_book(e.get('sig_book'))
    price = e.get('sig_price')
    if pred.get('price_venue') and (venue != pred['price_venue'] or not am_ok(price)):
        return None
    return {'ts': e['ts'], 'hours_before': round(hb, 2), 'book': book, 'price': price, 'price_venue': venue,
            'line': side_number(e['m'], e['side'], e['hline'], e['line']) if e['m'] != 'prop' else e['line'],
            'src_ref': e['src_ref'], 'result': None, 'units_1u': None}


# ── ledger build ───────────────────────────────────────────────────────────
PIT_FIELDS = ('key', 'kind_src', 'sport', 'game', 'label', 'start', 'market', 'prop', 'prop_label', 'side', 'line', 'hline',
              'first_ts', 'hours_before', 'kinds_at_fire', 'sources_at_fire', 'book', 'price', 'price_venue', 'price_src',
              'tape_age_h', 'signal_book', 'signal_price', 'signal_venue', 'fair_entry', 'band', 'timing', 'context_sharp',
              'src_ref')


def new_row(key, evs, tape, ctx_by_key, kind_src):
    """First sighting: every point-in-time field comes from the events at the earliest timestamp."""
    evs = sorted(evs, key=lambda e: e['ts'])
    t0 = evs[0]['ts']
    first = [e for e in evs if e['ts'] == t0]
    kinds = set()
    for e in first:
        kinds.update(e.get('kinds') or [e['kind']])
    # the signal that sets the number (and so the result): a priced US-book signal first, then a Top Read, then any
    def rank(e):
        _, v = norm_book(e.get('sig_book'))
        us = v == 'us_book' and am_ok(e.get('sig_price'))
        return (0 if us else 1, -am_profit(e['sig_price']) if us else 0, 0 if e['source'] == 'top_read' else 1, e['src_ref'])
    lead = sorted(first, key=rank)[0]
    sbook, svenue = norm_book(lead.get('sig_book'))
    sprice = lead.get('sig_price') if am_ok(lead.get('sig_price')) else None
    row = {'key': key, 'kind_src': kind_src, 'sport': lead.get('sport'), 'game': lead['game'], 'label': lead.get('label'),
           'start': lead['start'], 'market': 'prop' if kind_src == 'prop' else lead['m'], 'prop': lead.get('prop'),
           'prop_label': lead.get('prop_label'), 'side': lead['side'],
           'line': lead['line'] if kind_src == 'prop' else side_number(lead['m'], lead['side'], lead['hline'], lead['line']),
           'hline': lead['hline'], 'first_ts': t0, 'hours_before': round((lead['start'] - t0) / 3600.0, 2),
           'kinds_at_fire': sorted(kinds), 'sources_at_fire': sorted({e['source'] for e in first}),
           'signal_book': sbook, 'signal_price': sprice, 'signal_venue': svenue,
           'book': None, 'price': None, 'price_venue': 'none', 'price_src': None, 'tape_age_h': None,
           'fair_entry': lead.get('fair'), 'src_ref': lead['src_ref']}
    if svenue == 'us_book' and sprice is not None:
        row.update(book=sbook, price=sprice, price_venue='us_book', price_src='signal')
    elif kind_src == 'game':
        q = tape.best_us(lead['game'], lead['m'], lead['side'], lead['hline'], lead['line'], t0, lead['start']) if tape else None
        if q:
            row.update(book=q['book'], price=q['price'], price_venue='us_book', price_src='tape', tape_age_h=q['age_h'])
        else:
            row.update(book=sbook if sprice is not None else None, price=sprice, price_venue=svenue if sprice is not None else 'none')
    else:
        row.update(book=sbook, price=sprice, price_venue=svenue)
    p = row['fair_entry'] if row['fair_entry'] is not None else (am_implied(row['price']) if am_ok(row['price']) else None)
    row['band'] = band_of(p)
    row['timing'] = timing_of(row['hours_before'])
    sharp = [c for c in ctx_by_key.get(key, []) if c['ts'] <= t0 and c.get('text')]
    row['context_sharp'] = sharp[-1]['text'] if sharp else None
    row.update(kinds_later=[], result=None, units_1u=None, rule_match={}, rule_tags=[])
    return row


def update_row(row, evs, res, rules_by_id, rule_firsts):
    """Fill-later fields only. Never touches a point-in-time field."""
    later = set(row.get('kinds_later') or [])
    for e in evs:
        if e['ts'] > row['first_ts']:
            later.update(e.get('kinds') or [e['kind']])
    row['kinds_later'] = sorted(later)
    if row.get('result') is None:
        r = res.get(row['src_ref'])
        if r is not None:
            row['result'] = r
    row['units_1u'] = units_for(row['result'], row['price']) if row.get('price_venue') == 'us_book' else None
    rm = row.setdefault('rule_match', {})
    for rid, fire in rule_firsts.items():
        if rid not in rm and fire is not None:
            rm[rid] = fire          # a key evaluated once (passed or failed) is never evaluated again
    for rid, f in rm.items():
        if f.get('failed'):
            continue
        if f.get('result') is None:
            r = res.get(f['src_ref'])
            if r is not None:
                f['result'] = r
        f['units_1u'] = units_for(f['result'], f['price']) if f.get('price_venue') == 'us_book' else None
    tags = set(row.get('rule_tags') or [])
    for rid, f in rm.items():
        rule = rules_by_id.get(rid)
        if rule and not f.get('failed') and f['ts'] > rule['_frozen_ts'] and row['first_ts'] > rule['_frozen_ts']:
            tags.add(rid)
    row['rule_tags'] = sorted(tags)


def build_ledger(S, PP, prev, rules, tape, now):
    rules_by_id = {r['id']: r for r in rules}
    ev, ctx = game_events(S)
    nfl_game_at = {}
    for e in ev + ctx:
        if e['sport'] == 'nfl' and ' @ ' in (e.get('label') or ''):
            a, h = e['label'].split(' @ ', 1)
            nfl_game_at[(e['start'], norm_team(a))] = e['game']
            nfl_game_at[(e['start'], norm_team(h))] = e['game']
    pev = prop_events(PP, nfl_game_at)
    res = result_lookup(S, PP)

    by_key = collections.defaultdict(list)
    for e in ev:
        by_key[('game', e['key'])].append(e)
    for e in pev:
        by_key[('prop', e['key'])].append(e)
    ctx_by_key = collections.defaultdict(list)
    for c in ctx:
        ctx_by_key[c['key']].append(c)
    for v in ctx_by_key.values():
        v.sort(key=lambda c: c['ts'])

    rows = copy.deepcopy((prev or {}).get('rows') or {})
    carried = len(rows)
    added = 0
    for (kind_src, key), evs in by_key.items():
        evs.sort(key=lambda e: (e['ts'], e['src_ref']))
        firsts = {}
        for r in rules:
            if r.get('retired'):
                continue
            cands = [e for e in evs if rule_candidate(r['predicate'], e)]
            if cands:
                # several books can fire in the same poll: the first firing is that poll, and its best US-book price stands
                t0 = cands[0]['ts']
                same = [e for e in cands if e['ts'] == t0]
                fires = [f for f in (rule_fire(r['predicate'], e) for e in same) if f]
                if fires:
                    firsts[r['id']] = max(fires, key=lambda f: (am_profit(f['price']) if am_ok(f['price']) else -9, f['src_ref']))
                else:
                    # the first firing failed the rule: store that, so once it is pruned from state a later event never becomes "first"
                    firsts[r['id']] = {'ts': t0, 'failed': True, 'src_ref': same[0]['src_ref'],
                                       'hours_before': round((same[0]['start'] - t0) / 3600.0, 2)}
        if key not in rows:
            rows[key] = new_row(key, evs, tape, ctx_by_key, kind_src)
            added += 1
        update_row(rows[key], evs, res, rules_by_id, firsts)
    # rows no longer in state still settle if the source is somehow present, and keep everything else
    for key, row in rows.items():
        if row.get('result') is None and res.get(row.get('src_ref')) is not None:
            update_row(row, [], res, rules_by_id, {})
    contested = flag_contested(rows)

    # sharp money context ledger (never a bet row, never counts toward a rule)
    cx = copy.deepcopy((prev or {}).get('context') or {})
    for key, cs in ctx_by_key.items():
        if key not in cx:
            cx[key] = new_row(key, cs, tape, {}, 'game')
            cx[key]['kind_src'] = 'sharp_context'
        row = cx[key]
        later = set(row.get('kinds_later') or [])
        later.update(c['kind'] for c in cs if c['ts'] > row['first_ts'])
        row['kinds_later'] = sorted(later)
        if row.get('result') is None and res.get(row['src_ref']) is not None:
            row['result'] = res[row['src_ref']]
        row['units_1u'] = units_for(row['result'], row['price']) if row.get('price_venue') == 'us_book' else None
    seen = copy.deepcopy((prev or {}).get('rules_seen') or {})
    for r in rules:
        seen.setdefault(r['id'], {'version': r['version'], 'frozen_at': r['frozen_at'], 'rule_hash': r['rule_hash']})
    return {'v': LEDGER_V, 'generated': iso_utc(now), 'tape_max_age_h': TAPE_MAX_AGE_H, 'rules_seen': seen, 'rows': rows, 'context': cx}, \
        {'carried': carried, 'added': added, 'context_rows': len(cx), 'contested': contested}


def flag_contested(rows):
    """A key whose opposite side of the same game and market (or player, prop and week) also has a row is contested: the two
    bets mostly offset, so neither counts in the headline or the slices. Both rows are marked, the earlier one included, and
    the flag is never removed (rows are never removed either). Returns the number of contested rows."""
    by_mkt = collections.defaultdict(lambda: collections.defaultdict(list))
    for key, row in rows.items():
        by_mkt[key.rsplit('|', 1)[0]][row['side']].append(key)
    for sides in by_mkt.values():
        if len(sides) < 2:
            continue
        # the moment both sides first had a row
        t_both = max(min(rows[k]['first_ts'] for k in ks) for ks in sides.values())
        for side, ks in sides.items():
            others = sorted(k for s2, ks2 in sides.items() if s2 != side for k in ks2)
            for k in ks:
                row = rows[k]
                if not row.get('contested'):
                    row['contested'] = True
                    row['contested_ts'] = t_both
                row['contested_with'] = sorted(set(row.get('contested_with') or []) | set(others))
    return sum(1 for r in rows.values() if r.get('contested'))


# ── stats ──────────────────────────────────────────────────────────────────
def wilson(w, n, z=1.96):
    if n <= 0:
        return None, None
    p = w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c - h) / d, 4), round((c + h) / d, 4)


def bets_from_rows(rows, rule_id=None):
    """Settled bets: {res, u, imp, day, game, book} for rows priced at a US book; plus the unpriced settled rows."""
    priced, unpriced = [], []
    for r in rows:
        if rule_id:
            f = (r.get('rule_match') or {}).get(rule_id)
            if not f or f.get('failed'):
                continue
            res, price, venue, book = f.get('result'), f.get('price'), f.get('price_venue'), f.get('book')
        else:
            res, price, venue, book = r.get('result'), r.get('price'), r.get('price_venue'), r.get('book')
        if res is None:
            continue
        b = {'res': res, 'day': ct_day(r['start']), 'game': r['game'], 'book': book}
        if venue == 'us_book' and am_ok(price):
            b.update(u=units_for(res, price), imp=am_implied(price))
            priced.append(b)
        else:
            unpriced.append(b)
    return priced, unpriced


def stat_block(priced, unpriced=(), proven=False):
    n = len(priced)
    w = sum(b['res'] == 1 for b in priced)
    l = sum(b['res'] == -1 for b in priced)
    p = n - w - l
    units = round(sum(b['u'] for b in priced), 2)
    dec = [b for b in priced if b['res'] != 0]
    be = round(sum(b['imp'] for b in dec) / len(dec), 4) if dec else None
    win = round(w / (w + l), 4) if (w + l) else None
    lo, hi = wilson(w, w + l)
    days = len({b['day'] for b in priced})
    s = {'n': n, 'w': w, 'l': l, 'p': p, 'units': units, 'roi': round(units / n, 4) if n else None, 'breakeven': be,
         'win': win, 'wilson_lo': lo, 'wilson_hi': hi, 'game_days': days, 'games': len({b['game'] for b in priced}),
         'unpriced_n': len(unpriced), 'unpriced_w': sum(b['res'] == 1 for b in unpriced),
         'unpriced_l': sum(b['res'] == -1 for b in unpriced)}
    s['meter'] = meter(s, proven)
    return s


def meter(s, proven=False):
    if s['n'] < METER_MIN_N or s['game_days'] < METER_MIN_DAYS:
        return 'Too early'
    if proven:
        return 'Holding'
    if s['win'] is not None and s['breakeven'] is not None and s['win'] > s['breakeven'] and s['units'] > 0:
        return 'Leaning'
    return 'Coin flip'


def stage_of(priced, retired=False):
    """watching -> proving -> proven, from forward bets only. Returns (stage, checks)."""
    if retired:
        return 'retired', {}
    s = stat_block(priced)
    by_day = collections.defaultdict(float)
    by_game = collections.defaultdict(float)
    by_book = collections.Counter()
    for b in priced:
        by_day[b['day']] += b['u']
        by_game[b['game']] += b['u']
        by_book[b['book']] += 1
    units = sum(b['u'] for b in priced)
    best_day = max(by_day.values()) if by_day else 0.0
    edge = s['win'] is not None and s['breakeven'] is not None and s['win'] > s['breakeven']
    c = {'n': s['n'] >= PROVING_N, 'game_days': s['game_days'] >= PROVING_DAYS, 'units': units > 0, 'win_over_breakeven': edge,
         'best_day_share': units > 0 and best_day < BEST_DAY_SHARE * units}
    if not all(c.values()):
        return 'watching', c
    top5 = set(sorted(by_game, key=lambda g: by_game[g], reverse=True)[:5])
    book1 = by_book.most_common(1)[0][0] if by_book else None
    rng = random.Random(BOOT_SEED)
    days = list(by_day.values())
    le0 = 0
    for _ in range(BOOT_DRAWS):
        if sum(rng.choice(days) for _ in days) <= 0:
            le0 += 1
    c2 = {'n_150': s['n'] >= PROVEN_N, 'games_60': s['games'] >= PROVEN_GAMES,
          'wilson_lo_over_breakeven': s['wilson_lo'] is not None and s['wilson_lo'] > s['breakeven'],
          'bootstrap_p_le_0': round(le0 / BOOT_DRAWS, 4) <= BOOT_P,
          'units_without_top5_games': sum(b['u'] for b in priced if b['game'] not in top5) > 0,
          'units_without_top_book': sum(b['u'] for b in priced if b['book'] != book1) > 0}
    c.update(c2)
    c['bootstrap_p'] = round(le0 / BOOT_DRAWS, 4)
    return ('proven' if all(c2.values()) else 'proving'), c


# ── record ─────────────────────────────────────────────────────────────────
def side_label(row, line=None):
    line = row.get('line') if line is None else line
    if row['kind_src'] == 'prop':
        return f"{'Over' if row['side'] == 'over' else 'Under'} {line} {row.get('prop_label') or row.get('prop')}"
    lbl = row.get('label') or ''
    a, h = (lbl.split(' @ ', 1) + [''])[:2] if ' @ ' in lbl else ('Away', 'Home')
    team = h if row['side'] == 'home' else a if row['side'] == 'away' else None
    if row['market'] == 'ml':
        return f'{team} to win'
    if row['market'] == 'sp':
        ln = line
        return f"{team} {('+' if ln is not None and ln > 0 else '')}{ln if ln is not None else ''}".strip()
    return f"{'Over' if row['side'] == 'over' else 'Under'} {line}"


def firing_item(row, rule_id, ptb):
    f = row['rule_match'][rule_id]
    return {'rule': rule_id, 'key': row['key'], 'game': row.get('label'), 'sport': row.get('sport'), 'market': row['market'],
            'prop': row.get('prop'), 'side': row['side'], 'side_label': side_label(row, f.get('line')), 'line': f.get('line'),
            'book': f.get('book'), 'price': f.get('price'), 'fired_ct': ct_str(f['ts']), 'fired_utc': iso_utc(f['ts']),
            'hours_before': f.get('hours_before'), 'expires_ct': ct_str(row['start']), 'start_utc': iso_utc(row['start']),
            'price_to_beat': ptb}


def build_record(ledger, R, rules, now, tape_info):
    all_rows = list(ledger['rows'].values())
    # a game and market where signals took both sides mostly offsets: those rows are counted on their own, not in the headline or slices
    rows = [r for r in all_rows if not r.get('contested')]
    split_rows = [r for r in all_rows if r.get('contested')]
    priced, unpriced = bets_from_rows(rows)
    frozen = min(r['frozen_at'] for r in rules) if rules else None
    frozen_ts = min(r['_frozen_ts'] for r in rules) if rules else None
    head = stat_block(priced, unpriced)
    # the pooled headline is not a rule and is mostly signals from before the freeze: it never earns a meter
    head['meter'] = 'Context only'
    rec = {'v': 1, 'generated': iso_utc(now), 'generated_ct': ct_str(now), 'frozen_at': frozen,
           'ledger_rows': len(all_rows), 'pending': sum(r.get('result') is None for r in all_rows),
           'headline_label': 'Every signal (reads, alerts, prop calls), mostly before the freeze',
           'headline': head}
    if frozen_ts is not None:
        bp, bu = bets_from_rows([r for r in rows if r['first_ts'] <= frozen_ts])
        ap, au = bets_from_rows([r for r in rows if r['first_ts'] > frozen_ts])
        before = stat_block(bp, bu)
        before['meter'] = 'Context only'
        rec['headline_split'] = {'frozen_at': frozen, 'before': before, 'after': stat_block(ap, au)}
    sp, su = bets_from_rows(split_rows)
    sb = stat_block(sp, su)
    sb['meter'] = 'Context only'
    rec['contested'] = {'label': 'Signals split: games where signals took both sides of the same market. Left out of the record above.',
                        'rows': len(split_rows), 'markets': len({r['key'].rsplit('|', 1)[0] for r in split_rows}), 'record': sb}
    # slices (never Holding)
    def group(keyfn):
        g = collections.defaultdict(lambda: ([], []))
        for r in rows:
            p, u = bets_from_rows([r])
            for k in keyfn(r):
                if k is None:
                    continue
                g[k][0].extend(p)
                g[k][1].extend(u)
        return [dict(key=k, **stat_block(p, u)) for k, (p, u) in sorted(g.items(), key=lambda kv: str(kv[0]))]
    rec['slices'] = {
        'kind_sport': [dict(x, kind=x['key'].split('|')[0], sport=x['key'].split('|')[1])
                       for x in group(lambda r: [f"{k}|{r.get('sport')}" for k in r.get('kinds_at_fire') or []])],
        'band': group(lambda r: [r.get('band')]),
        'timing': group(lambda r: [r.get('timing')]),
        'market': group(lambda r: [r.get('market')]),
    }
    rec['rules'], rec['plays'] = [], []
    for rule in rules:
        rid = rule['id']
        tagged = [r for r in all_rows if rid in (r.get('rule_tags') or [])]
        fp, fu = bets_from_rows(tagged, rid)
        stage, checks = stage_of(fp, bool(rule.get('retired')))
        fwd = stat_block(fp, fu, proven=(stage == 'proven'))
        # pre-freeze holdout: predicate matches on games from the edge-hunt holdout start up to the freeze, context only
        hold_rows = [r for r in all_rows if rid in (r.get('rule_match') or {}) and not r['rule_match'][rid].get('failed')
                     and rid not in (r.get('rule_tags') or [])
                     and r['start'] >= HOLDOUT_FROM and r['rule_match'][rid]['ts'] <= rule['_frozen_ts']]
        hp, hu = bets_from_rows(hold_rows, rid)
        hb = stat_block(hp, hu)
        hb.update(label=f"Before the freeze: games from {ct_str(HOLDOUT_FROM)} to {ct_str(rule['_frozen_ts'])}. Shown for context only, it does not count.",
                  counts=False)
        # good-to price from the low end of the forward win range, not the point estimate (that is only a zero-EV price)
        ptb = None
        if fwd['n'] >= PRICE_TO_BEAT_MIN_N and fwd['wilson_lo'] is not None:
            ptb = prob_to_am(fwd['wilson_lo'])
        today = [firing_item(r, rid, ptb) for r in tagged if r['start'] > now]
        today.sort(key=lambda x: (x['start_utc'], x['fired_utc']))
        rec['rules'].append({'id': rid, 'version': rule['version'], 'plain': rule['plain'], 'frozen_at': rule['frozen_at'],
                             'rule_hash': rule['rule_hash'], 'read_note': rule.get('read_note'), 'stage': stage,
                             'stage_checks': checks, 'forward': fwd, 'holdout_note': hb,
                             'progress': {'n': fwd['n'], 'need': PROVEN_N, 'game_days': fwd['game_days'], 'need_days': PROVING_DAYS},
                             'today': today})
        if stage == 'proven':
            rec['plays'].extend(today)
    cxr = list(ledger.get('context', {}).values())
    cp, cu = bets_from_rows(cxr)
    cb = stat_block(cp, cu)
    cb['meter'] = 'Context only'
    rec['context'] = {'label': 'Sharp money (Polymarket sharp accounts, cross alerts, sharp-account whales). Context only: it is not a bet signal and never counts toward any record above.',
                      'context_only': True, 'rows': len(cxr), 'record': cb}
    rec['pricing'] = {'us_books': sorted(set(US_CANON.values())), 'tape_max_age_h': TAPE_MAX_AGE_H,
                      'tape_newest_ct': {k: ct_str(v) for k, v in tape_info.items()},
                      'note': 'Units count only at a real US sportsbook price. A row priced from its own signal uses that one book. A row '
                              'priced from the book tape takes the best of the whitelisted US books at that moment, which is line shopping '
                              'and flatters units. A row with no such price keeps its win-loss as unpriced.'}
    return rec


# ── io ─────────────────────────────────────────────────────────────────────
def write_json(path, obj, compact=True):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(obj, f, separators=(',', ':') if compact else None, indent=None if compact else 1)
    os.replace(tmp, path)


def run(d, rules_path, tape_dir, now):
    R, rules = load_rules(rules_path)
    S = json.load(open(os.path.join(d, 'state.json')))
    pp_path = os.path.join(d, 'prop_plays.json')
    PP = json.load(open(pp_path)) if os.path.exists(pp_path) else {}
    led_path = os.path.join(d, 'topreads_ledger.json')
    prev = None
    if os.path.exists(led_path):
        prev = json.load(open(led_path))          # a ledger that does not parse stops here: nothing is overwritten
        if not isinstance(prev, dict) or not isinstance(prev.get('rows'), dict):
            raise SystemExit('topreads_ledger.json exists but has no rows map; refusing to start a new ledger over it')
    nfl_games = {}
    for a in (S.get('alerts') or []) + list((S.get('picks') or {}).values()):
        if a.get('sport') == 'nfl' and a.get('game') and a.get('gameLbl'):
            nfl_games.setdefault(a['game'], (a['gameLbl'], a['start']))
    for r in ((prev or {}).get('rows') or {}).values():
        if r.get('sport') == 'nfl' and r.get('kind_src') == 'game':
            nfl_games.setdefault(r['game'], (r.get('label'), r['start']))
    tape = Tape(tape_dir, nfl_games)
    for r in rules:
        was = ((prev or {}).get('rules_seen') or {}).get(r['id'])
        if was and (was.get('frozen_at') != r['frozen_at'] or was.get('version') != r['version']):
            raise SystemExit(f"rule {r['id']}: frozen_at/version changed from {was.get('frozen_at')} v{was.get('version')} to "
                             f"{r['frozen_at']} v{r['version']} since the ledger first saw it; a frozen rule needs a new id")
    ledger, info = build_ledger(S, PP, prev, rules, tape, now)
    if prev and len(ledger['rows']) < len(prev['rows']):
        raise SystemExit('ledger shrank; refusing to write')
    rec = build_record(ledger, R, rules, now, tape.newest)
    write_json(led_path, ledger)
    write_json(os.path.join(d, 'topreads_record.json'), rec, compact=False)
    h = rec['headline']
    print(f"topreads: {len(ledger['rows'])} rows ({info['carried']} carried, {info['added']} new), "
          f"{h['n']} priced {h['w']}-{h['l']}-{h['p']} {h['units']:+.2f}u, unpriced {h['unpriced_n']}; tape {dict(tape.stats)}")
    for r in rec['rules']:
        f = r['forward']
        print(f"  {r['id']}: {r['stage']} forward n={f['n']} {f['units']:+.2f}u; holdout n={r['holdout_note']['n']} {r['holdout_note']['units']:+.2f}u")
    return ledger, rec


# ── selftest ───────────────────────────────────────────────────────────────
def selftest():
    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)

    # book names
    for name, venue in [('Underdog Fantasy', 'pickem'), ('underdog', 'pickem'), ('UNDERDOG', 'pickem'), ('PrizePicks', 'pickem'),
                        ('DraftKings Pick6', 'pickem'), ('Fliff', 'pickem'), ('Parx Casino', 'state_limited'), ('betParx', 'state_limited'),
                        ('Pinnacle', 'offshore'), ('Kalshi', 'exchange'), ('Polymarket', 'exchange'), ('Novig', 'exchange'),
                        ('Consensus', 'none'), ('draft kings', 'us_book'), ('FanDuel', 'us_book'), ('Bet365', 'us_book'),
                        ('William Hill', 'us_book'), ('BetRivers', 'us_book'), ('betrivers', 'us_book'), ('Betr', 'pickem'), ('Betr Picks', 'pickem'), ('Hard Rock Bet', 'state_limited'), ('ESPN BET', 'state_limited')]:
        ok(norm_book(name)[1] == venue, f'norm_book({name!r}) -> {norm_book(name)} not {venue}')
    ok(norm_book('draft kings')[0] == 'DraftKings', 'DraftKings canonical name')

    tmp = tempfile.mkdtemp(prefix='topreads_selftest_')
    frozen = parse_iso('2026-11-09T12:00:00-06:00')
    rules = []
    for rid, pred in [('nfl_prop_under_us_book', {'source': 'prop_call', 'sport': 'nfl', 'side': 'under', 'first': 'player|prop|game|side', 'price_venue': 'us_book'}),
                      ('behind_spread_24h', {'source': 'alert', 'type': 'behind', 'market': 'sp', 'first': 'game|market|side', 'min_hours_before': 24, 'price_venue': 'us_book'}),
                      ('cfb_behind_spread_24h', {'source': 'alert', 'type': 'behind', 'sport': 'cfb', 'market': 'sp', 'first': 'game|market|side', 'min_hours_before': 24, 'price_venue': 'us_book'})]:
        rules.append({'id': rid, 'version': 1, 'plain': rid, 'predicate': pred, 'frozen_at': '2026-11-09T12:00:00-06:00'})
        rules[-1]['rule_hash'] = rule_hash(rules[-1])
    rp = os.path.join(tmp, 'rules.json')
    json.dump({'rules': rules}, open(rp, 'w'))
    H = 3600
    pre_ts, post_ts = frozen - 2 * H, frozen + 2 * H
    start_pre, start_post = pre_ts + 30 * H, post_ts + 30 * H

    def alert(gid, typ, ts, start, book='DraftKings', price=-105, side='home', m='sp', res=None, sport='cfb', aid=None, cls=None):
        return {'game': gid, 'sport': sport, 'gameLbl': 'AAA @ BBB', 'start': start, 'ts': ts, 'type': typ, 'm': m, 'side': side,
                'book': book, 'price': price, 'hline': -3.5, 'line': -3.5, 'fair': 0.52, 'cls': cls, 'src': 'Novig', 'px': 0.5,
                'id': aid or f'{gid}:{typ}:{book}:{ts}', 'text': f'{typ} alert', 'result': res}
    S = {'alerts': [alert('cfb:1', 'behind', pre_ts, start_pre, res=1),                       # pre-freeze, matches predicate
                    alert('cfb:2', 'behind', post_ts, start_post),                            # post-freeze, counts
                    alert('cfb:3', 'behind', post_ts, start_post, book='Parx Casino'),        # state-limited: never priced
                    alert('cfb:4', 'sharp', post_ts, start_post, book=None, price=None),      # context only
                    alert('cfb:5', 'whale', post_ts, start_post, book=None, price=None, cls='sharp'),
                    alert('cfb:6', 'whale', post_ts, start_post, book=None, price=None),
                    # contested: a home whale, then an away split on the same game and market
                    alert('cfb:8', 'whale', post_ts, start_post, book=None, price=None, side='home', res=1),
                    alert('cfb:8', 'split', post_ts + 600, start_post, book=None, price=None, side='away', res=-1),
                    # a first behind alert that fails the 24h rule (under 24h), then a later one on the same key
                    alert('cfb:9', 'behind', post_ts, post_ts + 10 * H),
                    alert('cfb:9', 'behind', post_ts + 1800, post_ts + 10 * H, aid='cfb:9:late')],
         'picks': {'cfb:7|sp|home': {'game': 'cfb:7', 'gameLbl': 'AAA @ BBB', 'sport': 'cfb', 'start': start_post, 'm': 'sp', 'side': 'home',
                                     'hline': -3.5, 'line': None, 'kinds': ['line'], 'sig': {'line': 'moved'}, 'ts': post_ts, 'price': -110,
                                     'fair': 0.5, 'result': None}},
         'sharpContext': {}}
    PP = {'plays': {}}
    for i, src in enumerate(['Underdog Fantasy', 'Parx Casino', 'Pinnacle', 'DraftKings', 'Kalshi']):
        PP['plays'][f'2026|10|{i}|rec|4.5|under'] = {'season': '2026', 'week': 10, 'pid': str(i), 'name': f'P{i}', 'team': 'AAA', 'pos': 'WR',
                                                      'mkt': 'rec', 'label': 'Receptions', 'line': 4.5, 'side': 'under', 'start': start_post,
                                                      'firstSeen': post_ts, 'called': {'src': src, 'kind': 'book', 'am': 120, 'p': 0.45, 'fair': 0.5},
                                                      'status': 'won'}
    d = os.path.join(tmp, 'out')
    os.makedirs(d)
    json.dump(S, open(os.path.join(d, 'state.json'), 'w'))
    json.dump(PP, open(os.path.join(d, 'prop_plays.json'), 'w'))
    now = post_ts + H
    L1, rec1 = run(d, rp, None, now)
    rows = L1['rows']
    ok('cfb:1|sp|home' in rows and not rows['cfb:1|sp|home']['rule_tags'], 'pre-freeze row must not carry a rule tag')
    ok('behind_spread_24h' in rows['cfb:1|sp|home']['rule_match'], 'pre-freeze row still records its predicate match')
    ok(rows['cfb:2|sp|home']['rule_tags'] == ['behind_spread_24h', 'cfb_behind_spread_24h'], f"post-freeze tags {rows['cfb:2|sp|home']['rule_tags']}")
    ok(rows['cfb:3|sp|home']['price_venue'] == 'state_limited' and not rows['cfb:3|sp|home']['rule_tags'], 'Parx behind alert priced or tagged')
    ok('cfb:4|sp|home' not in rows and 'cfb:5|sp|home' not in rows, 'sharp money created a ledger row')
    ok('cfb:6|sp|home' in rows, 'non-sharp whale must create a row')
    ok('cfb:4|sp|home' in L1['context'], 'sharp alert missing from context')
    for i, src in enumerate(['Underdog Fantasy', 'Parx Casino', 'Pinnacle', 'DraftKings', 'Kalshi']):
        r = rows[f'nfl:{i}|rec|2026w10|under']
        ok((r['units_1u'] is not None) == (src == 'DraftKings'), f'{src} prop priced={r["units_1u"]}')
        ok(('nfl_prop_under_us_book' in r['rule_tags']) == (src == 'DraftKings'), f'{src} prop rule tag {r["rule_tags"]}')
    fwd = {x['id']: x for x in rec1['rules']}
    ok(fwd['behind_spread_24h']['forward']['n'] == 0, 'unsettled forward row counted')
    ok(fwd['behind_spread_24h']['holdout_note']['n'] == 1 and not fwd['behind_spread_24h']['holdout_note']['counts'], 'holdout row not in context note')
    ok(fwd['nfl_prop_under_us_book']['forward']['n'] == 1, 'DraftKings prop under should count forward')
    ok(len(fwd['behind_spread_24h']['today']) == 1, 'today list should hold the open post-freeze firing')
    # contested: both sides flagged, and kept out of the headline and slices
    ok(rows['cfb:8|sp|home'].get('contested') and rows['cfb:8|sp|away'].get('contested'), 'both sides of a split game must be contested')
    ok(rows['cfb:8|sp|home']['contested_with'] == ['cfb:8|sp|away'], f"contested_with {rows['cfb:8|sp|home'].get('contested_with')}")
    ok(not rows['cfb:6|sp|home'].get('contested'), 'a one-sided game must not be contested')
    ok(rec1['contested']['rows'] == 2 and rec1['contested']['markets'] == 1, f"contested count {rec1['contested']['rows']}")
    ok(rec1['headline']['unpriced_n'] == 4 and rec1['headline']['meter'] == 'Context only',
       f"headline must leave contested rows out (unpriced_n={rec1['headline']['unpriced_n']}) and carry no meter")
    ok(rec1['contested']['record']['unpriced_n'] == 2, 'contested record holds both sides')
    hl1 = rec1['headline']
    ok(sum(x['unpriced_n'] + x['n'] for x in rec1['slices']['market']) == hl1['unpriced_n'] + hl1['n'], 'slices must leave contested rows out')
    # failed first fire is stored and never replaced by a later event
    f9 = rows['cfb:9|sp|home']['rule_match'].get('behind_spread_24h')
    ok(f9 and f9.get('failed') and f9['src_ref'] != 'alert:cfb:9:late', f'failed first fire not stored: {f9}')
    ok(not rows['cfb:9|sp|home']['rule_tags'], 'a key whose first fire failed must not be tagged')

    # run 2: state drops the old alert, changes a price and moves a timestamp earlier; results arrive
    S2 = copy.deepcopy(S)
    S2['alerts'] = [a for a in S2['alerts'] if a['game'] != 'cfb:1']
    # prune the failing first cfb:9 alert and make the later one pass the 24h test: it must still not stand in for the first
    S2['alerts'] = [a for a in S2['alerts'] if a['id'] != f'cfb:9:behind:DraftKings:{post_ts}']
    for a in S2['alerts']:
        if a['id'] == 'cfb:9:late':
            a['start'] = post_ts + 40 * H
    for a in S2['alerts']:
        if a['game'] == 'cfb:2':
            a['price'], a['result'] = +150, 1
    S2['picks']['cfb:7|sp|home']['ts'] = pre_ts
    S2['picks']['cfb:7|sp|home']['kinds'] = ['line', 'money']
    json.dump(S2, open(os.path.join(d, 'state.json'), 'w'))
    L2, rec2 = run(d, rp, None, now + H)
    r2 = L2['rows']
    ok('cfb:1|sp|home' in r2, 'carry-forward lost a pruned row')
    ok(r2['cfb:1|sp|home']['result'] == 1, 'carried row lost its result')
    ok(r2['cfb:2|sp|home']['price'] == -105, 'point-in-time price overwritten')
    ok(r2['cfb:2|sp|home']['result'] == 1 and r2['cfb:2|sp|home']['units_1u'] == round(100 / 105, 4), 'result/units not filled at the frozen price')
    ok(r2['cfb:7|sp|home']['first_ts'] == post_ts and r2['cfb:7|sp|home']['kinds_at_fire'] == ['line'], 'first_ts / kinds_at_fire overwritten')
    ok(r2['cfb:2|sp|home']['rule_match']['behind_spread_24h']['price'] == -105, 'rule fire price overwritten')
    ok(r2['cfb:9|sp|home']['rule_match']['behind_spread_24h'].get('failed') and not r2['cfb:9|sp|home']['rule_tags'],
       'a later event stood in for a pruned failing first fire')
    ok(r2['cfb:8|sp|home'].get('contested'), 'contested flag lost on carry-forward')
    ok(L2.get('rules_seen', {}).get('behind_spread_24h', {}).get('frozen_at') == '2026-11-09T12:00:00-06:00', 'rules_seen not stored')

    # meter and stage thresholds
    def bets(n, wins, price=-110, days=10, games=None, book='DraftKings'):
        out = []
        for i in range(n):
            res = 1 if i < wins else -1
            out.append({'res': res, 'u': units_for(res, price), 'imp': am_implied(price), 'day': f'd{i % days}',
                        'game': f'g{i if games is None else i % games}', 'book': book if i % 2 else 'FanDuel'})
        return out
    ok(meter(stat_block(bets(49, 40))) == 'Too early', 'n<50 must be Too early')
    ok(meter(stat_block(bets(60, 50, days=5))) == 'Too early', 'game_days<6 must be Too early')
    ok(meter(stat_block(bets(60, 40))) == 'Leaning', '40-20 at -110 should be Leaning')
    ok(meter(stat_block(bets(60, 30))) == 'Coin flip', '30-30 at -110 should be Coin flip')
    ok(meter(stat_block(bets(60, 40)), proven=True) == 'Holding', 'proven rule meter should be Holding')
    ok(stage_of(bets(74, 60))[0] == 'watching', 'n<75 must stay watching')
    ok(stage_of(bets(80, 60, days=7))[0] == 'watching', 'game_days<8 must stay watching')
    ok(stage_of(bets(100, 70))[0] == 'proving', '70-30 n=100 should be proving')
    ok(stage_of(bets(200, 140, games=100))[0] == 'proven', '140-60 n=200 over 100 games should be proven')
    ok(stage_of(bets(200, 140, games=50))[0] == 'proving', 'fewer than 60 games must not be proven')
    ok(stage_of(bets(200, 140, games=100), retired=True)[0] == 'retired', 'retired flag')
    lop = bets(100, 70)
    for b in lop[:30]:
        b['day'] = 'big'
    ok(stage_of(lop)[0] == 'watching', 'one game day over 40% of units must block proving')
    ok(prob_to_am(0.6) == -150 and prob_to_am(0.4) == 150, 'prob_to_am')
    ok(prob_to_am(0.55) == -122 and prob_to_am(0.45) == 123, f'prob_to_am rounding {prob_to_am(0.55)} {prob_to_am(0.45)}')
    for q in (0.51, 0.55, 0.58, 0.45, 0.42, 0.3):
        ok(am_implied(prob_to_am(q)) <= q + 1e-12, f'prob_to_am({q}) needs more than {q}')
    # tape: a newer row without the market means the book pulled it
    tt = Tape(None, {})
    tt.rows[('g1', 'DraftKings')] = [{'t': 1000, 'ml': [120, -140], 'sp': [-3.5, -110, -110]}, {'t': 2000, 'ml': [125, -145]}]
    ok(tt.quote('g1', 'DraftKings', 'sp', 'home', -3.5, None, 2500, 99999) is None, 'tape attached a pulled spread from an older row')
    ok(tt.quote('g1', 'DraftKings', 'sp', 'home', -3.5, None, 1500, 99999)['price'] == -110, 'tape lost a live spread')
    ok(tt.quote('g1', 'DraftKings', 'ml', 'away', None, None, 2500, 99999)['price'] == 125, 'tape lost the latest moneyline')
    # broken previous ledger must stop the run without overwriting
    with open(os.path.join(d, 'topreads_ledger.json'), 'w') as f:
        f.write('{"rows": ')
    try:
        run(d, rp, None, now)
        fails.append('a broken ledger was overwritten')
    except (ValueError, SystemExit):
        pass
    ok(open(os.path.join(d, 'topreads_ledger.json')).read() == '{"rows": ', 'broken ledger file changed')
    # frozen_at moved earlier: a stale hash fails, and a recomputed hash still fails against the ledger's first-seen frozen_at
    good = json.load(open(rp))
    moved = copy.deepcopy(good)
    moved['rules'][1]['frozen_at'] = '2026-10-01T12:00:00-06:00'
    json.dump(moved, open(rp, 'w'))
    try:
        load_rules(rp)
        fails.append('a frozen_at edit with a stale hash was accepted')
    except SystemExit:
        pass
    moved['rules'][1]['rule_hash'] = rule_hash(moved['rules'][1])
    json.dump(moved, open(rp, 'w'))
    d2 = os.path.join(tmp, 'out2')
    os.makedirs(d2)
    for fn in ('state.json', 'prop_plays.json'):
        json.dump(json.load(open(os.path.join(d, fn))), open(os.path.join(d2, fn), 'w'))
    write_json(os.path.join(d2, 'topreads_ledger.json'), L2)
    before_bytes = open(os.path.join(d2, 'topreads_ledger.json')).read()
    try:
        run(d2, rp, None, now + 2 * H)
        fails.append('a frozen_at edit with a recomputed hash was accepted against the ledger')
    except SystemExit:
        pass
    ok(open(os.path.join(d2, 'topreads_ledger.json')).read() == before_bytes, 'ledger changed on a refused frozen_at edit')
    json.dump(good, open(rp, 'w'))
    # tampered rule
    bad = json.load(open(rp))
    bad['rules'][0]['predicate']['side'] = 'over'
    json.dump(bad, open(rp, 'w'))
    try:
        load_rules(rp)
        fails.append('a predicate edit with a stale hash was accepted')
    except SystemExit:
        pass
    if fails:
        print('SELFTEST FAILED:\n  ' + '\n  '.join(fails))
        sys.exit(1)
    print('selftest ok')


def main(argv):
    args = {}
    for a in argv:
        if a.startswith('--'):
            k, _, v = a[2:].partition('=')
            args[k] = v if _ else True
    if args.get('selftest'):
        return selftest()
    rules_path = args.get('rules') or os.path.join(ROOT, 'data', 'topreads_rules.json')
    if args.get('hash'):
        for r in json.load(open(rules_path))['rules']:
            print(r['id'], rule_hash(r))
        return
    d = args.get('dir') or 'sharp-out'
    tape_dir = args.get('tape') or os.path.join(ROOT, 'data', 'book_tape')
    now = int(args['now']) if args.get('now') else int(dt.datetime.now(dt.timezone.utc).timestamp())
    run(d, rules_path, tape_dir, now)


if __name__ == '__main__':
    main(sys.argv[1:])
