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


def pricing():
    """What the page needs to price a prop the way build_prop_model.py backtested it: variance fits, calibration
    knots, and the market/model blend fit on held-out data, per venue (Kalshi) and for sportsbooks (ESPN close)."""
    pm = load('prop_model.json')
    if not pm:
        return None
    coef = lambda c: c and {'a': round(c['a'], 4), 'wm': round(c['w_market'], 4), 'wp': round(c['w_model'], 4), 't': c.get('t')}
    B = pm.get('blend_oos', {})
    return {'variance': pm['variance'], 'calibration': {k: [[round(x, 4), round(y, 4)] for x, y in v] for k, v in pm['calibration'].items() if v},
            'kalshi': {s: coef(B[f'kalshi/{s}']['coef']) for s in ('pts', 'reb', 'ast', '3pm') if B.get(f'kalshi/{s}')},
            'book': {s: coef(B[f'espn25->26/{s}/close']['coef']) for s in ('pts', 'reb', 'ast', '3pm', 'pra', 'pr', 'pa', 'ra') if B.get(f'espn25->26/{s}/close')},
            'verdict': pm.get('verdict', {}), 'generated': pm.get('generated')}


def render():
    tpl = open(os.path.join(HERE, '..', 'ui', 'projections.template.html')).read()
    html = (tpl.replace('/*DATA*/null', json.dumps(load('player_projections.json'), separators=(',', ':')))
               .replace('/*HEALTH*/null', json.dumps(load('data_health.json'), separators=(',', ':')))
               .replace('/*PRICING*/null', json.dumps(pricing(), separators=(',', ':')))
               .replace('/*BOARD*/null', json.dumps(load('prop_board.json'), separators=(',', ':')))
               .replace('/*LOGS*/null', json.dumps(load('gamelogs.json'), separators=(',', ':'))))
    out = os.path.join(HERE, '..', 'projections.html')
    open(out, 'w').write(html)
    print(f'rendered {os.path.relpath(out)} ({os.path.getsize(out) // 1000} KB)')


if __name__ == '__main__':
    render()
