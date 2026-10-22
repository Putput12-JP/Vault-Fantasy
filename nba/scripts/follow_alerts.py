#!/usr/bin/env python3
"""
Discord alerts when a ranked Polymarket wallet buys (Sharp Price V2). Called by fast_poll.py each minute with the tickets it
just saw. One alert per wallet, market and outcome (the first $1,000+ ticket, the same event the follow ledger logs), only for
proven and probable wallets (data/pm_wallet_rank.json), only for a ticket seen within MAX_AGE_S and not part of a process's first
backlog read, and never twice: sent keys are saved in the day's alerts.json so a restart of the recorder cannot repeat them.

The webhook URL is a secret and is read from DISCORD_WEBHOOK_URL (a GitHub Actions secret). It is never written to a file or a
log. With no URL set this does nothing. The message is context, not a bet: copying a sharp account late lost money in our study
and the follow ledger's paper test is still running (docs/sharp-follow-prereg.md).
"""
import datetime as dt, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from follow_ledger import side_quote, eid                       # noqa: E402
from sharp import REPO_DATA, ET                                 # noqa: E402

TIERS = ('proven', 'probable')
MAX_AGE_S = 15 * 60                                              # a ticket older than this when we see it is not alerted
MAX_EMBEDS = 10                                                  # Discord's cap per message
COLOR = {'proven': 0x4ADE80, 'probable': 0x7AB4FF}
FILE = 'alerts.json'


def load_rank():
    try:
        return json.load(open(os.path.join(REPO_DATA, 'pm_wallet_rank.json'))).get('wallets') or {}
    except (OSError, ValueError):
        return {}


def load_sent(dirs):
    sent = {}
    for d in dirs:
        p = os.path.join(d, FILE)
        if os.path.exists(p):
            try:
                sent.update(json.load(open(p)))
            except ValueError:
                pass
    return sent


def clean(x, n=60):
    """Names come from Polymarket: strip markdown and mention syntax so a pseudonym cannot format or ping the channel."""
    return ''.join(c for c in str(x or '') if c.isalnum() or c in ' -_.')[:n]


def cents(x):
    return 'n/a' if x is None else f'{round(x * 100)}c'


def side_label(m, o):
    try:
        side = json.loads(m['outcomes'])[o]
    except (ValueError, KeyError, IndexError, TypeError):
        side = '?'
    q = m.get('q') or ''
    t = m.get('type')
    if t == 'moneyline':
        return f'{clean(side)} to win'
    if t == 'spreads':
        x = re.search(r'\(([-+]?[\d.]+)\)', q)
        return f"{clean(side)} {x.group(1) if x else ''}".strip()
    x = re.search(r'([\d.]+)\s*$', q)
    return f"{clean(side)} {x.group(1) if x else ''}".strip()


def follow_line(ask, px):
    if ask is None:
        return 'No ask quoted right now.'
    gap = round((ask - px) * 100)
    if ask <= px + 1e-9:
        return f'Ask {cents(ask)} {"beats" if gap < 0 else "matches"} their {cents(px)}: fillable now.'
    return f'Their price was {cents(px)}; ask is {gap}c above. A resting bid at {cents(px)} fills only if it comes back.'


def build(row, m, rank, quote, now, game=None):
    """One Discord embed for one ticket."""
    v = rank.get(row['w']) or {}
    tier = v.get('tier')
    nba = (v.get('raw') or {}).get('nba')
    other = ', '.join(f'{s.upper()} {r[0]}' for s, r in (v.get('raw') or {}).items() if s != 'nba')
    bid, ask = side_quote(quote, row['o']) if quote else (None, None)
    hours = (m['start'] - now) / 3600
    name = clean(row.get('who')) or row['w'][:6] + '...' + row['w'][-4:]
    rec = f"{nba[0]} NBA game{'s' if nba[0] != 1 else ''}" if nba else 'no NBA games'
    lines = [f"**${row['usd']:,}** at **{cents(row['px'])}**. Now {cents(bid)} bid / {cents(ask)} ask.",
             follow_line(ask, row['px']),
             f"Skill estimate {v['post'] * 100:+.1f}% per game, {round(v['p'] * 100)}% chance it is above zero. Record: {rec}{', ' + other if other else ''}."]
    if row.get('also_other'):
        lines.insert(1, 'This wallet also bought the other side of this market.')
    return {'title': f"{tier.capitalize()} wallet {name} bought {side_label(m, row['o'])}",
            'description': '\n'.join(lines), 'color': COLOR.get(tier, 0x999999),
            'footer': {'text': f"{game or clean(m.get('event'))}, tips in {hours:.1f} h. Context, not a bet: copying late lost money in our study."},
            'timestamp': dt.datetime.fromtimestamp(row['t'], dt.timezone.utc).isoformat()}


def post(url, embeds, curl=None):
    """True if Discord accepted it. The URL is passed to curl on stdin-free argv only and never printed."""
    body = json.dumps({'username': 'Vault Follow', 'embeds': embeds, 'allowed_mentions': {'parse': []}})
    try:
        p = (curl or subprocess.run)(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', '10', '-X', 'POST', '-H', 'Content-Type: application/json', '-d', body, url],
                                    capture_output=True, text=True)
        return p.stdout.strip() in ('200', '204')
    except Exception:
        return False


def notify(st, rows, ms, quotes, now, post_fn=post):
    """Alert on the new tickets in `rows` (fast_poll tape rows). Returns how many were sent. Never raises."""
    url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not url or not (rows or getattr(st, 'pending', None)):
        return 0
    try:
        if getattr(st, 'rank', None) is None:
            st.rank = load_rank()
        if getattr(st, 'sent', None) is None:
            from sharp import day_dirs
            st.sent = load_sent(day_dirs(st.root, now, 2))
        pend = []
        rows = list(getattr(st, 'pending', [])) + list(rows)         # tickets whose alert failed last cycle, still fresh
        st.pending = []
        for r in sorted(rows, key=lambda r: r['t']):
            v = st.rank.get(r['w'])
            m = ms.get(r['k'])
            key = eid(r['w'], r['k'], r['o'])
            if not v or v.get('tier') not in TIERS or not m or key in st.sent or now - r['t'] > MAX_AGE_S or r['t'] >= m['start']:
                continue
            if any(p[0] == key for p in pend):
                continue
            r = {**r, 'also_other': eid(r['w'], r['k'], 1 - r['o']) in st.sent or any(p[0] == eid(r['w'], r['k'], 1 - r['o']) for p in pend)}
            pend.append((key, build(r, m, st.rank, quotes.get(r['k']), now, m.get('event')), r))
        sent = 0
        for i in range(0, len(pend), MAX_EMBEDS):
            chunk = pend[i:i + MAX_EMBEDS]
            if post_fn(url, [x[1] for x in chunk]):
                sent += len(chunk)
                for x in chunk:
                    st.sent[x[0]] = int(now)
            else:
                print('  alert not delivered; will retry while the ticket is fresh', flush=True)
                st.pending = [x[2] for x in pend[i:]]
                break
        if sent:
            day = os.path.join(st.root, 'snapshots', dt.datetime.fromtimestamp(now, ET).date().isoformat())
            p = os.path.join(day, FILE)
            cur = json.load(open(p)) if os.path.exists(p) else {}
            cur.update({k: v for k, v in st.sent.items() if k not in cur and v >= now - 2 * 86400})
            json.dump(cur, open(p, 'w'), separators=(',', ':'))
            print(f'  alerted {sent} ranked-wallet ticket{"s" if sent != 1 else ""}', flush=True)
        return sent
    except Exception as e:
        print(f'  alerts failed: {type(e).__name__}', flush=True)
        return 0
