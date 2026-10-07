#!/usr/bin/env python3
"""
Render the app page (nba/projections.html) from ui/projections.template.html with its data inlined,
since an artifact page cannot fetch local files. Called by build_player_projections.py and
build_data_health.py; run it alone to re-render after a template change.

  python3 nba/scripts/render_app.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')


def load(name):
    path = os.path.join(DATA, name)
    return json.load(open(path)) if os.path.exists(path) else None


def backtest(v2):
    """Each GO / WATCH signal's 2025-26 out-of-sample Kalshi result, keyed stat|kalshi|side (Track Record compares)."""
    out = {}
    for m, v in v2['verdict']['v2'].items():
        if v.startswith(('GO', 'WATCH')) and '(' in v:
            side = v.split('(')[1].rstrip(')')
            b = v2.get('kalshi_bias', {}).get(m, {}).get('v2', {}).get(f'blend/{side}') or {}
            out[f'{m}|kalshi|{side}'] = {'gate': v.split()[0].lower(), 'roi': b.get('roi'), 'n': b.get('n'), 'z': b.get('z')}
    return out


def consensus_params():
    """The consensus engine's fitted Kalshi blend (a + b logit(consensus) + c logit(model), per stat, from the ladder test)
    and its verdicts by stat and side (build_consensus.py)."""
    cb = load('consensus_backtest.json')
    if not cb:
        return None
    lad = cb['tests'].get('kalshi_ladder', {})
    return {'kalshi': {m: d['blends']['consensus + model'] for m, d in lad.items() if d.get('blends')},
            'verdict': {m: v.get('consensus + model', {}) for m, v in cb['verdicts'].get('kalshi_ladder', {}).items()},
            'generated': cb['generated']}


def extra():
    """The extra markets (build_prop_model_extra.py): variance and a standing NO-GO, plus a plain
    scorecard against ESPN's 2025-26 closing lines. Merged into the pricing and model state so the page prices them like any stat."""
    return load('prop_model_extra.json')


def with_extra(d):
    st = extra()
    if d and st:
        d['variance'] = {**d['variance'], **st['variance']}
        d['verdict'] = {**d.get('verdict', {}), **st['verdict']}
        d['extra'] = {'accuracy': st['accuracy'], 'espn_2026': st['espn_2026'], 'why': st['why']}
    return d


def projections():
    """player_projections.json for the page, with the extra markets' per-minute rates filled in where a player's rate dict lacks them
    (never overwriting: the existing stats' rates, fga included, are what the other models were fit on)."""
    d = load('player_projections.json')
    st = extra()
    if d and st:
        for t in d['teams'].values():
            for p in t['players']:
                for k, v in (st['rates'].get(str(p['id'])) or {}).items():
                    p['rate'].setdefault(k, v)
    return d


def model_state():
    m = load('model_state.json')
    st = extra()
    if m and st:                        # per-minute steal / block / turnover rates ride in each player's rate state
        for side in ('live', 'example'):
            for pid, p in ((m.get(side) or {}).get('players') or {}).items():
                rates = st['rates'].get(str(pid))
                if rates and p.get('r'):
                    p['r'].update(rates)
                if rates and p.get('rate'):
                    p['rate'].update(rates)
    return m


def pricing():
    return with_extra(pricing_base())


def pricing_base():
    """What the page needs to price a prop the way the backtest did. Prop model v2 when it has been built
    (build_prop_model_v2.py): stacker weights, variance with the minutes term, calibration, and blend weights fit
    on all the priced history (Kalshi 2025-26, ESPN 2024-25 open + 2025-26 close). Else v1's held-out blend."""
    coef = lambda c: c and {'a': round(c['a'], 4), 'wm': round(c['w_market'], 4), 'wp': round(c['w_model'], 4), 't': c.get('t')}
    v2 = load('prop_model_v2.json')
    if v2:
        return {'model': 'v2', 'features': v2['features'],
                'stacker': {s: v['beta'] for s, v in v2['stacker'].items()},
                'variance': v2['variance']['v2'],
                'calibration': {k: [[round(x, 4), round(y, 4)] for x, y in v] for k, v in v2['calibration']['v2'].items() if v},
                'kalshi': {s: coef(c) for s, c in v2['blend_live']['kalshi'].items() if c},
                'book': {s: coef(c) for s, c in v2['blend_live']['book'].items() if c},
                'verdict': v2['verdict']['v2'], 'backtest': backtest(v2), 'consensus': consensus_params(), 'generated': v2['generated']}
    pm = load('prop_model.json')
    if not pm:
        return None
    B = pm.get('blend_oos', {})
    return {'model': 'v1', 'variance': pm['variance'], 'calibration': {k: [[round(x, 4), round(y, 4)] for x, y in v] for k, v in pm['calibration'].items() if v},
            'kalshi': {s: coef(B[f'kalshi/{s}']['coef']) for s in ('pts', 'reb', 'ast', '3pm') if B.get(f'kalshi/{s}')},
            'book': {s: coef(B[f'espn25->26/{s}/close']['coef']) for s in ('pts', 'reb', 'ast', '3pm', 'pra', 'pr', 'pa', 'ra') if B.get(f'espn25->26/{s}/close')},
            'verdict': pm.get('verdict', {}), 'generated': pm.get('generated')}


def pickem():
    """The correlated pick'em test (build_pickem_corr.py): the families that passed, measured on the test season, plus
    the closest miss, for the Pick'em Pairs page."""
    d = load('pickem_corr.json')
    if not d:
        return None
    fam = lambda r: {'rel': r['key'][0], 'a': r['key'][1], 'b': r['key'][2], 'family': r['family'], 'c': r['test']['c'], 'z': r['test']['z'],
                     'n': r['test']['n'], 'games': r['test']['games'], 'z0': r['explore']['z'], 'zc': (r.get('close') or {}).get('z')}
    rows = d['families']
    return {'verdict': d['verdict'], 'rules': d['rules'], 'n_families': len(rows), 'pass': [fam(r) for r in rows if r['pass']],
            'near': [fam(r) for r in rows if r['candidate'] and not r['pass']]}


def control():
    """Control Room page: the frozen models, the pre-registered tests with their dates, and past verdicts. Run history is fetched live by the page."""
    fz = lambda name: (lambda d: d and {'fingerprint': d['fingerprint'][:12], 'games': d.get('games'), 'rows': d.get('rows') or d.get('legs')})(load(name))
    v = lambda name: (lambda d: d and d.get('verdict'))(load(name))
    return {'repo': 'Putput12-JP/Vault-Fantasy',
            'frozen': [{'name': 'Dependence model (step A2)', 'what': 'Latent correlations between props, fit on 2024-25 and 2025-26', 'doc': 'nba/docs/copula-fit-a2.md', **(fz('copula_frozen.json') or {})},
                       {'name': 'Game-script minutes model (step B3)', 'what': 'Minutes tied to the game score, overtime and a team shock', 'doc': 'nba/docs/game-script-minutes-b3.md', **(fz('game_script_frozen.json') or {})}],
            'milestones': [
                {'date': '2026-10-20', 'title': 'Opening night', 'what': "Regular season starts. The regular-season record begins; the dependence and minutes models are already frozen.", 'doc': 'nba/docs/game-simulation.md'},
                {'date': '2026-10-21', 'title': 'Opening-night check', 'what': "Review of pick'em mappings, the injury report, the Injury Wire, starting fives, roster holds and season-record routing.", 'doc': None},
                {'date': '2026-11-09', 'title': 'Dependence test (step A2)', 'what': 'Scores the frozen correlations on the first 150 regular-season games. GO needs z of 2.4 and the slope rule.', 'doc': 'nba/docs/copula-fit-a2.md'},
                {'date': '2026-11-16', 'title': 'Minutes test (step B3)', 'what': 'Scores the frozen minutes model on the first 200 regular-season games; all four rules must hold.', 'doc': 'nba/docs/game-script-minutes-b3.md'},
                {'date': '2026-11-20', 'title': 'Minutes v3 shadow review', 'what': "Compares the v3 minutes model's shadow record against v2.", 'doc': 'nba/docs/minutes-model-v3.md'}],
            'results': [{'name': 'Dependence fit, step A', 'verdict': v('copula_corr.json'), 'note': 'prices were biased; fixed in A2', 'doc': 'nba/docs/copula-fit-results.md'},
                        {'name': 'Minutes tied to the margin, step B', 'verdict': v('game_script_minutes.json'), 'note': 'missed overtime and the team shock', 'doc': 'nba/docs/game-script-minutes-results.md'},
                        {'name': 'Overtime and team shock, step B2', 'verdict': v('game_script_minutes_b2.json'), 'note': 'missed one check by 0.009; B3 fixes the bench floor', 'doc': 'nba/docs/game-script-minutes-b2-results.md'},
                        {'name': "Correlated pick'em pairs", 'verdict': (pickem() or {}).get('verdict'), 'note': 'two families passed', 'doc': 'nba/docs/pickem-correlation-results.md'}]}


def render():
    tpl = open(os.path.join(HERE, '..', 'ui', 'projections.template.html')).read()
    hk = os.path.join(HERE, '..', 'ui', 'halaska', 'dist.js')
    # Halaska UI bundle (ui/halaska/dist.js, built by `node build.mjs` there); the page degrades to no kit if it is absent
    tpl = tpl.replace('<script>/*HALASKA*/</script>', '<script>' + (open(hk).read() if os.path.exists(hk) else 'window.HK = null;') + '</script>')
    html = (tpl.replace('/*DATA*/null', json.dumps(projections(), separators=(',', ':')))
               .replace('/*HEALTH*/null', json.dumps(load('data_health.json'), separators=(',', ':')))
               .replace('/*PRICING*/null', json.dumps(pricing(), separators=(',', ':')))
               .replace('/*BOARD*/null', json.dumps(load('prop_board.json'), separators=(',', ':')))
               .replace('/*LOGS*/null', json.dumps(load('gamelogs.json'), separators=(',', ':')))
               .replace('/*TRACK*/null', json.dumps(load('track.json'), separators=(',', ':')))
               .replace('/*STATE*/null', json.dumps(model_state(), separators=(',', ':')))
               .replace('/*BACKTESTS*/null', json.dumps(load('backtests.json'), separators=(',', ':')))
               .replace('/*PICKEM*/null', json.dumps(pickem(), separators=(',', ':')))
               .replace('/*CONTROL*/null', json.dumps(control(), separators=(',', ':')))
               .replace('/*PHOTOS*/null', json.dumps(load('photos.json'), separators=(',', ':'))))
    out = os.path.join(HERE, '..', 'projections.html')
    open(out, 'w').write(html)
    print(f'rendered {os.path.relpath(out)} ({os.path.getsize(out) // 1000} KB)')


if __name__ == '__main__':
    render()
