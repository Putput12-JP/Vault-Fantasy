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


def render():
    tpl = open(os.path.join(HERE, '..', 'ui', 'projections.template.html')).read()
    html = (tpl.replace('/*DATA*/null', json.dumps(load('player_projections.json'), separators=(',', ':')))
               .replace('/*HEALTH*/null', json.dumps(load('data_health.json'), separators=(',', ':'))))
    out = os.path.join(HERE, '..', 'projections.html')
    open(out, 'w').write(html)
    print(f'rendered {os.path.relpath(out)} ({os.path.getsize(out) // 1000} KB)')


if __name__ == '__main__':
    render()
