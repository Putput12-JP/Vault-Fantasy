#!/usr/bin/env python3
"""A flagged, hindsight backfill of the prop plays V2 would have shown on a finished slate. It is NOT the live record and is never counted in it.

Why hindsight: the prop ledger keeps the price each call showed the FIRST time it was seen (a median of about 2 days before kickoff) and Pinnacle's fair at that
moment. It keeps no exchange price from then. The only stored exchange price is the close (Kalshi and Novig at the exact line, `closeX`, from
scripts/regrade_prop_clv.py). So the second fair price used here is a number nobody had when the price was taken. A price that beats the close tends to win more,
so choosing plays this way flatters the result. Read it as an upper bound, not as what the live log will show.

Selection (the V2 gates, with the exchange close standing in for the exchange read):
  price at a US sportsbook (not a pick'em app, not an exchange); fair from Pinnacle; edge against Pinnacle's fair at first sight and against the exchange close
  both at least 2%; the two fair prices within 4 points; the edge not over 10%.
Result and units come from the ledger (flat 1 unit at the stored price). CLV is the exchange close over the stored price.

usage: backfill_v2_props.py --date 2026-10-18 [--plays prop_plays.json] [--out data/v2_backfill.json]"""
import argparse, datetime as dt, json, os, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
US = {'Caesars', 'FanDuel', 'DraftKings', 'bet365', 'BetMGM', 'BetRivers', 'Fanatics', 'Parx Casino', 'Hard Rock', 'ESPN BET'}
MIN_EDGE, AGREE, BIG_EDGE = 0.02, 0.04, 0.10
CT = dt.timezone(dt.timedelta(hours=-5))
r4 = lambda x: None if x is None else round(x, 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True); ap.add_argument('--plays'); ap.add_argument('--ml-replay', help='JSON from backfill_v2_slate.py to embed its summary')
    ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'v2_backfill.json'))
    a = ap.parse_args()
    if a.plays:
        with open(a.plays) as f:
            ledger = json.load(f)
    else:
        ledger = json.loads(subprocess.run(['git', '-C', ROOT, 'show', 'origin/sharp-data:prop_plays.json'], capture_output=True, check=True).stdout)
    calls = [p for p in ledger['plays'].values() if dt.datetime.fromtimestamp(p['start'], CT).strftime('%Y-%m-%d') == a.date]
    us = [p for p in calls if p['called'].get('kind') == 'book' and p['called'].get('src') in US and p['called'].get('fairSrc') == 'Pinnacle']
    plays = {}
    for p in us:
        c, fx = p['called'], p.get('closeX')
        if fx is None:
            continue
        e1, e2 = c['fair'] / c['p'] - 1, fx / c['p'] - 1
        if min(e1, e2) < MIN_EDGE or abs(c['fair'] - fx) > AGREE or min(e1, e2) > BIG_EDGE:      # same tests as gates.js: the worst-case edge is the one capped
            continue
        pid = 'bfp|' + p['id']
        plays[pid] = dict(id=pid, kind='prop', sport='nfl', start=p['start'], firstSeen=p['firstSeen'], backfill=True, status=p['status'], units=p.get('units'),
                          clv=p.get('clvX'), close=dict(p=r4(fx), src='Kalshi+Novig close'),
                          first=dict(title='%s %s %s %s' % (p['name'], 'Over' if p['side'] == 'over' else 'Under', p['line'], p['label']), sub=p['team'] + ' ' + p['pos'], market=p['label'],
                                     price=dict(am=c['am'], p=r4(c['p']), book=c['src']),
                                     refs=[dict(n='Pinnacle', p=r4(c['fair']), edge=r4(e1)), dict(n='Exchange close', p=r4(fx), edge=r4(e2))], worst=r4(min(e1, e2)), best=r4(max(e1, e2))),
                          hoursEarly=round((p['start'] - p['firstSeen']) / 3600, 1))
    # one side per prop: if both sides cleared, keep the one with the better worst-case edge (the stance the page takes)
    best = {}
    for k, pl in plays.items():
        pr = ledger['plays'][k[4:]]; key = (pr['pid'], pr['mkt'], pr['line'])
        if key not in best or pl['first']['worst'] > plays[best[key]]['first']['worst']:
            best[key] = k
    plays = {k: v for k, v in plays.items() if k in set(best.values())}
    ml = None
    if a.ml_replay:
        with open(a.ml_replay) as f:
            ml = json.load(f)
    doc = dict(v=1, date=a.date, kind='props, hindsight',
               note='Not the live record. Selected using the exchange CLOSE, which was not known when the price was taken, on prices first seen about two days before kickoff. It reads better than live plays will. Never counted in the live W-L or units.',
               calls_that_day=len(calls), priced_at_a_us_book=len(us), moneyline_replay=dict(games=len(ml['games']), plays=len(ml['plays'])) if ml else None, plays=plays)
    with open(a.out, 'w') as f:
        json.dump(doc, f, indent=1)
    done = [p for p in plays.values() if p['status'] in ('won', 'lost')]
    w = sum(1 for p in done if p['status'] == 'won')
    print(len(calls), 'calls,', len(us), 'at a US book,', len(plays), 'clear the gates;', len(done), 'settled', '%d-%d' % (w, len(done) - w), 'units', round(sum(p['units'] for p in done), 2))


if __name__ == '__main__':
    main()
