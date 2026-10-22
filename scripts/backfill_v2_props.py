#!/usr/bin/env python3
"""A flagged, hindsight backfill of the prop plays V2 would have shown on a finished slate. It is NOT the live record and is never counted in it.

Why hindsight: the prop ledger keeps the price each call showed the FIRST time it was seen (a median of about 2 days before kickoff) and Pinnacle's fair at that
moment. It keeps no exchange price from then. The only stored exchange price is the close (Kalshi and Novig at the exact line, `closeX`, from
scripts/regrade_prop_clv.py). So the second fair price used here is a number nobody had when the price was taken. A price that beats the close tends to win more,
so choosing plays this way flatters the result. Read it as an upper bound, not as what the live log will show.

Selection (the V2 gates, props anchored on the exchange, with the exchange close standing in for the exchange read):
  price at a US sportsbook (not a pick'em app, not an exchange); fair from Pinnacle; the edge against the exchange close at least 2% and not over 10%; Pinnacle within
  4 points of the exchange and not pricing the side the other way.
Result and units come from the ledger (flat 1 unit at the stored price). CLV is the exchange close over the stored price.

usage: backfill_v2_props.py --date 2026-10-18 [--plays prop_plays.json] [--out data/v2_backfill.json]"""
import argparse, collections, datetime as dt, json, os, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DFS = {'Sleeper', 'Underdog', 'Underdog Fantasy', 'PrizePicks', 'Fliff', 'Dabble'}
US = {'Caesars', 'FanDuel', 'DraftKings', 'bet365', 'BetMGM', 'BetRivers', 'Fanatics', 'Parx Casino', 'Hard Rock', 'ESPN BET'}
MIN_EDGE, AGREE, BIG_EDGE = 0.02, 0.04, 0.10
CT = dt.timezone(dt.timedelta(hours=-5))
r4 = lambda x: None if x is None else round(x, 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True); ap.add_argument('--plays'); ap.add_argument('--games', help='JSON from backfill_v2_slate.py: the game plays, watch and passed to merge in')
    ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'v2_backfill.json'))
    a = ap.parse_args()
    if a.plays:
        with open(a.plays) as f:
            ledger = json.load(f)
    else:
        ledger = json.loads(subprocess.run(['git', '-C', ROOT, 'show', 'origin/sharp-data:prop_plays.json'], capture_output=True, check=True).stdout)
    calls = [p for p in ledger['plays'].values() if dt.datetime.fromtimestamp(p['start'], CT).strftime('%Y-%m-%d') == a.date and p['called'].get('fairSrc') == 'Pinnacle']
    # candidates: every call whose best stored edge is 2%+ (the live page drops the rest as "no edge")
    cands = []
    for p in calls:
        c, fx = p['called'], p.get('closeX')
        e1 = c['fair'] / c['p'] - 1
        e2 = fx / c['p'] - 1 if fx is not None else None
        edges = [e for e in (e1, e2) if e is not None]
        if max(edges) < MIN_EDGE:
            continue
        cands.append(dict(p=p, e1=e1, e2=e2, fx=fx, key=(p['pid'], p['mkt'], p['line']), worst=min(edges), best=max(edges), nrefs=len(edges)))
    # The ledger keeps one stored price per side, the best EV anywhere (often an exchange). The live page prices a side at the best US book first, so an
    # exchange-priced call on the other side of a prop that has a US-book call would not have been that side's candidate. Only US-book calls can contradict.
    is_us = lambda c: c['p']['called']['kind'] == 'book' and c['p']['called']['src'] in US
    us_sides = collections.defaultdict(set)
    for c in cands:
        if is_us(c):
            us_sides[c['key']].add(c['p']['side'])
    cands = [c for c in cands if not us_sides[c['key']] or c['p']['side'] in us_sides[c['key']]]
    sides = us_sides
    top = {}
    for c in cands:
        v = c['worst'] if c['nrefs'] > 1 else c['best']
        if c['key'] not in top or v > top[c['key']][0]:
            top[c['key']] = (v, c['p']['side'])
    tiers = {'play': {}, 'watch': {}, 'pass': {}}
    for c in cands:
        p, src, kind = c['p'], c['p']['called']['src'], c['p']['called']['kind']
        if top[c['key']][1] != p['side']:
            continue
        if src in DFS or (kind == 'book' and src not in US) or kind == 'exchange':
            tier, why = 'pass', 'priced at ' + ('an exchange' if kind == 'exchange' else 'a pick\u2019em app or non-US book')
        elif len(sides[c['key']]) > 1:
            tier, why = 'pass', 'both sides clear a reference'
        elif c['nrefs'] < 2:
            tier, why = 'watch', 'one reference only'
        elif abs(p['called']['fair'] - c['fx']) > AGREE:
            tier, why = 'pass', 'references disagree'
        elif c['e2'] < MIN_EDGE:
            tier, why = 'pass', 'does not beat the exchange'
        elif c['e1'] < 0:
            tier, why = 'pass', 'Pinnacle prices it the other way'
        elif c['e2'] > BIG_EDGE:
            tier, why = 'pass', 'edge over 10%'
        else:
            tier, why = 'play', 'clears every gate (anchored on the exchange)'
        cc = p['called']
        refs = [dict(n='Pinnacle', p=r4(cc['fair']), edge=r4(c['e1']))] + ([dict(n='Exchange close', p=r4(c['fx']), edge=r4(c['e2']))] if c['fx'] is not None else [])
        pid = 'bfp|%s|%s' % (tier, p['id'])
        tiers[tier][pid] = dict(id=pid, kind='prop', sport='nfl', start=p['start'], firstSeen=p['firstSeen'], backfill=True, status=p['status'], units=p.get('units'),
                                clv=p.get('clvX'), close=dict(p=r4(c['fx']), src='Kalshi+Novig close') if c['fx'] is not None else None,
                                first=dict(title='%s %s %s %s' % (p['name'], 'Over' if p['side'] == 'over' else 'Under', p['line'], p['label']), sub=p['team'] + ' ' + p['pos'], market=p['label'],
                                           price=dict(am=cc['am'], p=r4(cc['p']), book=src), refs=refs, worst=r4(c['e2'] if c['e2'] is not None else c['worst']), best=r4(c['best']), why=why),
                                hoursEarly=round((p['start'] - p['firstSeen']) / 3600, 1))
    games = None
    if a.games:
        with open(a.games) as f:
            games = json.load(f)
        for t, k in (('play', 'plays'), ('watch', 'watch'), ('pass', 'passed')):
            tiers[t].update(games[k])
    doc = dict(v=2, date=a.date,
               note='Rebuilt after the fact for a finished slate, not the live log. Props: the second price is the exchange CLOSE (not known when the price was taken) on prices first seen about two days early. Games: replayed from the book tape using only what was stored at each moment, moneyline with the exchange, spread and total with Pinnacle only. Passed props are calls whose best stored price was at an exchange or pick\u2019em app, or that failed a gate.',
               calls_that_day=len(calls), games=games['games'] if games else None, plays=tiers['play'], watch=tiers['watch'], passed=tiers['pass'])
    with open(a.out, 'w') as f:
        json.dump(doc, f, indent=1)
    for t in ('play', 'watch', 'pass'):
        ps = list(tiers[t].values()); done = [x for x in ps if x['status'] in ('won', 'lost', 'push')]
        w = sum(1 for x in done if x['status'] == 'won')
        print(t, len(ps), 'rows;', len(done), 'settled', '%d-%d' % (w, len(done) - w), 'units', round(sum(x['units'] or 0 for x in done), 2), collections.Counter(x['kind'] for x in ps))


if __name__ == '__main__':
    main()
