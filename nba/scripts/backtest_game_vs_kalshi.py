#!/usr/bin/env python3
"""
The honest bet-time test for the game model: model at 1pm ET (1pm injury report)
vs the Kalshi price that was actually tradeable at 1pm ET.

ESPN's "open" line has no timestamp, so beating it (build_game_model.py) can't
tell a real edge from knowing news the open predates. Kalshi's trade tape can:
every price here is the last trades before 1pm ET on game day.

Moneyline (KXNBAGAME): model win% = Phi(margin / SIGMA) vs Kalshi 1pm price.
  - calibration / Brier: model vs Kalshi 1pm vs Kalshi pre-tip
  - CLV: when the model likes a side at 1pm, did Kalshi's pre-tip price move toward it?
  - ROI: buy YES at the 1pm price (+ Kalshi taker fee) when model edge >= threshold

  python3 nba/scripts/backtest_game_vs_kalshi.py
Appends its results to nba/docs/game-model.md
"""
import json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_game_model as GM
from backfill_kalshi import TEAM

RAW_K = os.path.join(C.RAW, 'kalshi')


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def fee(p):
    """Kalshi taker fee per $1 contract: 0.07 * p * (1 - p), rounded up to the cent (per contract, small orders)."""
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def load(series):
    mk = {m['ticker']: m for m in map(json.loads, open(os.path.join(RAW_K, f'markets_{series}.jsonl')))}
    am = {r['ticker']: r for r in map(json.loads, open(os.path.join(RAW_K, f'prices_am_{series}.jsonl')))}
    pre = {r['ticker']: r for r in map(json.loads, open(os.path.join(RAW_K, f'prices_{series}.jsonl')))}
    return mk, am, pre


def price(rec, key):
    s = (rec or {}).get(key) or {}
    return s.get('vwap30') or s.get('last')


def main():
    P = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    _, recs = GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, C.closing_lines(), inj, record_from=GM.TEST[0])
    by_gid = {r['g']['game_id']: r for r in recs}
    tune_mae = json.load(open(GM.OUT_JSON))['tune_mae'][0]
    sigma = tune_mae * math.sqrt(math.pi / 2)   # Normal: MAE = sigma * sqrt(2/pi); fit on TUNE seasons only

    mk, am, pre = load('KXNBAGAME')
    rows = []
    for t, m in mk.items():
        a, p = am.get(t), pre.get(t)
        gid = (a or {}).get('game_id')
        r = by_gid.get(gid)
        if not r or m['result'] not in ('yes', 'no'):
            continue
        team = TEAM.get(t.rsplit('-', 1)[1], t.rsplit('-', 1)[1])
        g = r['g']
        if team not in (g['home'], g['away']):
            continue
        k1, k2 = price(a, 'am'), price(p, 'pretip')
        if k1 is None or k2 is None or not (0.02 < k1 < 0.98):
            continue
        margin = r['am'][0] if team == g['home'] else -r['am'][0]
        rows.append({'gid': gid, 'season': g['season'], 'team': team, 'model': phi(margin / sigma),
                     'k_am': k1, 'k_pre': k2, 'won': 1 if m['result'] == 'yes' else 0})

    def brier(key):
        return statistics.mean((r[key] - r['won']) ** 2 for r in rows)

    L = ['', '## Honest bet-time test: model at 1pm vs the Kalshi price at 1pm (moneyline)', '',
         f'`nba/scripts/backtest_game_vs_kalshi.py`. {len(rows):,} team-sides with a Kalshi trade before 1pm ET and before tip.',
         f'Win% = Phi(margin / {sigma:.1f}), sigma from the tune seasons only.', '',
         f"Brier score (lower is better): model {brier('model'):.4f}, Kalshi 1pm {brier('k_am'):.4f}, Kalshi pre-tip {brier('k_pre'):.4f}.", '']
    # blend test: does adding the model to the 1pm price improve it?
    best = min((statistics.mean(((1 - w) * r['k_am'] + w * r['model'] - r['won']) ** 2 for r in rows), w)
               for w in [i / 20 for i in range(0, 11)])
    L.append(f'Best blend of Kalshi 1pm + model: weight on model {best[1]:.2f} (Brier {best[0]:.4f}). Weight 0 = the model adds nothing.')
    L += ['', '| Model edge vs 1pm price | Bets | Win% | Avg price | ROI after fees | CLV: pre-tip moved toward model |', '|---|---|---|---|---|---|']
    for th in (0.02, 0.04, 0.06, 0.08, 0.10):
        bets = [r for r in rows if r['model'] - r['k_am'] >= th]
        if not bets:
            continue
        cost = sum(r['k_am'] + fee(r['k_am']) for r in bets)
        ret = sum(r['won'] for r in bets)
        tow = sum(1 for r in bets if r['k_pre'] > r['k_am'])
        away = sum(1 for r in bets if r['k_pre'] < r['k_am'])
        L.append(f"| {th:.0%}+ | {len(bets)} | {statistics.mean(r['won'] for r in bets):.1%} | {statistics.mean(r['k_am'] for r in bets):.2f} | "
                 f"{(ret - cost) / cost:+.1%} | {tow} toward / {away} away |")
    L += ['', 'Each game has two sides; a bet is a YES buy on the side the model rates higher than its 1pm price.', '']
    L += ['', '**Verdict:** moneyline no edge; spread ladder unstable (flips sign between halves, NO-GO); total ladder',
          'positive in both halves and on both sides but the 2nd half alone is not 2 SE, and per CONTRACT (equal stake on',
          'every strike) it is only about +2% (WATCH, marginal). The per-game ROI below weights cheap long-shot contracts',
          'heavily, so it reads much bigger than the money result. Likely mechanism: thin Kalshi total ladders drift from',
          'the sportsbook number at 1pm; test live against Pinnacle before betting.']
    L += ladder_test(by_gid, sigma, json.load(open(GM.OUT_JSON))['tune_mae'][1] * math.sqrt(math.pi / 2))
    print('\n'.join(L))
    with open(GM.OUT_MD, 'a') as f:
        f.write('\n'.join(L))


def ladder_test(by_gid, sig_m, sig_t):
    """Spreads (KXNBASPREAD: 'TEAM wins by over X') and totals (KXNBATOTAL: 'over X'), same 1pm test.
    Every strike on the ladder is a separate bet; one game contributes many correlated strikes, so
    the per-game count is shown next to the strike count."""
    out = []
    for series, label in (('KXNBASPREAD', 'Spread ladder'), ('KXNBATOTAL', 'Total ladder')):
        if not os.path.exists(os.path.join(RAW_K, f'prices_am_{series}.jsonl')):
            continue
        mk, am, pre = load(series)
        rows = []
        for t, m in mk.items():
            a, p = am.get(t), pre.get(t)
            r = by_gid.get((a or {}).get('game_id'))
            if not r or m['result'] not in ('yes', 'no') or m.get('floor_strike') is None:
                continue
            k1, k2 = price(a, 'am'), price(p, 'pretip')
            if k1 is None or k2 is None or not (0.05 < k1 < 0.95):
                continue
            g, x = r['g'], m['floor_strike']
            if series == 'KXNBASPREAD':
                team = TEAM.get(t.rsplit('-', 1)[1].rstrip('0123456789'), t.rsplit('-', 1)[1].rstrip('0123456789'))
                if team not in (g['home'], g['away']):
                    continue
                mu = r['am'][0] if team == g['home'] else -r['am'][0]
                pm = 1 - phi((x - mu) / sig_m)
            else:
                pm = 1 - phi((x - r['am'][1]) / sig_t)
            rows.append({'gid': g['game_id'], 'tip': g['tip'], 'model': pm, 'k_am': k1, 'k_pre': k2,
                         'won': 1 if m['result'] == 'yes' else 0})
        if not rows:
            continue
        out += ['', f'### {label} (Kalshi, 1pm)', '',
                f"{len(rows):,} strikes across {len({r['gid'] for r in rows}):,} games. Brier: model "
                f"{statistics.mean((r['model'] - r['won']) ** 2 for r in rows):.4f}, Kalshi 1pm "
                f"{statistics.mean((r['k_am'] - r['won']) ** 2 for r in rows):.4f}, pre-tip "
                f"{statistics.mean((r['k_pre'] - r['won']) ** 2 for r in rows):.4f}.", '',
                '| Model edge (either side) | Strikes | Games | ROI after fees | CLV toward / away |', '|---|---|---|---|---|']
        for th in (0.04, 0.08, 0.12):
            cost = ret = 0.0
            n = tow = away = 0
            games = set()
            for r in rows:
                e = r['model'] - r['k_am']
                if abs(e) < th:
                    continue
                yes = e > 0
                px = r['k_am'] if yes else 1 - r['k_am']
                cost += px + fee(px)
                ret += r['won'] if yes else 1 - r['won']
                mv = r['k_pre'] - r['k_am']
                tow += (mv > 0) == yes and mv != 0
                away += (mv > 0) != yes and mv != 0
                n += 1
                games.add(r['gid'])
            if n:
                out.append(f'| {th:.0%}+ | {n} | {len(games)} | {(ret - cost) / cost:+.1%} | {tow} / {away} |')
        # Stability: an edge that is real survives a split by date; also compare to "always buy NO" (a YES bias check).
        rows.sort(key=lambda r: r['tip'])
        half = len(rows) // 2
        out += ['', f"YES hit rate {statistics.mean(r['won'] for r in rows):.3f} vs average price "
                f"{statistics.mean(r['k_am'] for r in rows):.3f} (no gap = no overs bias here).", '',
                '| Split (8%+ edge) | Model: strikes, games, ROI/game, z | Model YES side | Model NO side | Always NO |',
                '|---|---|---|---|---|']
        for lab, R in (('1st half', rows[:half]), ('2nd half', rows[half:])):
            sel = [(r, r['model'] > r['k_am']) for r in R if abs(r['model'] - r['k_am']) >= 0.08]
            cells = [clustered([x for x in sel]), clustered([x for x in sel if x[1]]),
                     clustered([x for x in sel if not x[1]]), clustered([(r, False) for r in R])]
            out.append(f'| {lab} | ' + ' | '.join(cells) + ' |')
    return out


def clustered(sel):
    """ROI per game (each game's mean return per $ staked) and its z, games as the unit."""
    per = defaultdict(list)
    for r, yes in sel:
        c = r['k_am'] if yes else 1 - r['k_am']
        c += fee(c)
        win = r['won'] if yes else 1 - r['won']
        per[r['gid']].append(((1 - c) if win else -c) / c)
    gm = [statistics.mean(v) for v in per.values()]
    if len(gm) < 2:
        return '-'
    z = statistics.mean(gm) / (statistics.stdev(gm) / math.sqrt(len(gm)))
    return f'{len(sel)}, {len(gm)}, {statistics.mean(gm):+.1%}, {z:.2f}'


if __name__ == '__main__':
    main()
