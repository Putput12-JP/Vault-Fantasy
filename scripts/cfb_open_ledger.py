#!/usr/bin/env python3
"""College football opening-line ledger: how do underdogs cover at the OPENING number?

JP+ went 38-28 on underdogs at its entry (opening) number and 32-32-2 at the close (docs/retro/cfb-efficiency-replication.md).
Is that model skill, or is it how opening lines are priced? Answering it needs every game's opening line, not just JP+'s picks.
We had none, so this logs them: for every college game the Sharp Money feed lists, freeze the opening spread the feed
saw first, keep rolling the last pre-kickoff line forward as the close proxy, and settle from the feed's final score.

  python3 scripts/cfb_open_ledger.py --sharp /tmp/sharp.json [--out data/cfb_open_lines.json]

Units: `open`/`close` are the HOME team's handicap (+ = home underdog), like the feed. The home side covers when
(home score - away score) + handicap > 0. Pushes count as pushes.
Caveats, on purpose and shown on the summary: (1) "open" is the first line Sharp Money saw, which can trail the true opener
by hours; (2) the feed only lists a window of games, so this is a sample of the slate, not every FBS game;
(3) the close is the last line seen before kickoff, polled every ~30 min, not the true close.
Read the summary only once it has a real sample (it says so itself under 100 games)."""
import argparse, json, os, time

OUT_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cfb_open_lines.json')
MIN_READ = 100


def line_of(g, which):
    ln = ((g.get(which) or {}).get('sp') or {}).get('line')
    return None if ln is None else float(ln)


def current_line(g):
    for src in ('pin', 'consensus'):
        v = ((g.get(src) or {}).get('sp') or {}).get('line')
        if v is not None: return float(v)
    return None


def update(ledger, feed, now):
    games = ledger.setdefault('games', {})
    for g in feed.get('games', []):
        if g.get('sport') != 'cfb': continue
        k = g['key']; start = g['start']
        r = games.get(k)
        if r is None:
            op = line_of(g, 'open')
            if op is None or start <= now: continue      # nothing to freeze, or already in progress when first seen (its line is live)
            r = games[k] = dict(key=k, home=g['home']['short'], away=g['away']['short'], start=start, open=op, first_seen=now, close=op, last_seen=now)
        if start > now:                                    # pre-game: roll the close proxy forward
            cur = current_line(g)
            if cur is not None: r['close'] = cur; r['last_seen'] = now
        fin = g.get('final')
        if fin and fin.get('home') is not None and 'margin' not in r:
            r['margin'] = fin['home'] - fin['away']        # home score minus away score
    return ledger


def tally(rows, line_key, dog):
    """underdog (dog=True) or favourite record at the open or the close; the home handicap line is + when home is the underdog"""
    w = l = p = 0
    for r in rows:
        ln = r[line_key]
        if ln == 0: continue                               # pick'em: no underdog
        home_is_dog = ln > 0
        v = r['margin'] + ln                               # > 0: home covers
        home_covers = v > 0
        side_covers = home_covers if (home_is_dog == dog) else (v < 0)
        if v == 0: p += 1
        elif side_covers: w += 1
        else: l += 1
    return [w, l, p]


def summarize(ledger):
    rows = [r for r in ledger['games'].values() if 'margin' in r]
    s = dict(settled=len(rows), listed=len(ledger['games']),
             dog_open=tally(rows, 'open', True), dog_close=tally(rows, 'close', True),
             fav_open=tally(rows, 'open', False), fav_close=tally(rows, 'close', False))
    # does the line move toward the underdog or the favourite between the open and the close?
    mv = [(r['close'] - r['open']) * (1 if r['open'] > 0 else -1) for r in rows if r['open'] != 0]   # + = the underdog got MORE points
    s['move_avg_toward_dog'] = round(sum(mv) / len(mv), 2) if mv else None
    for lo, hi, nm in ((0, 7, 'short'), (7, 14, 'mid'), (14, 99, 'long')):
        sub = [r for r in rows if lo <= abs(r['open']) < hi]
        s['by_size_' + nm] = dict(n=len(sub), dog_open=tally(sub, 'open', True), dog_close=tally(sub, 'close', True))
    s['read'] = 'enough games to read' if len(rows) >= MIN_READ else f'only {len(rows)} settled games: under {MIN_READ}, not a reading yet'
    ledger['summary'] = s
    return ledger


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--sharp', required=True); ap.add_argument('--out', default=OUT_DEFAULT)
    a = ap.parse_args()
    feed = json.load(open(a.sharp)); now = int(feed.get('ts') or time.time())
    try: ledger = json.load(open(a.out))
    except Exception: ledger = {}
    summarize(update(ledger, feed, now))
    ledger['generated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now))
    ledger['note'] = 'Opening spreads for every college game the Sharp Money feed lists; see scripts/cfb_open_ledger.py for units and caveats.'
    json.dump(ledger, open(a.out, 'w'), indent=1, sort_keys=True)
    s = ledger['summary']; print(f"cfb open ledger: {s['listed']} games logged, {s['settled']} settled; underdogs at open {s['dog_open']} vs close {s['dog_close']} ({s['read']})")


if __name__ == '__main__':
    main()
