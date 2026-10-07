#!/usr/bin/env python3
"""
Player headshots and team logos for the app, embedded in the page as small data URIs (the published artifact blocks
external images, so anything it shows has to ride inside the file).

  players  each team's top ROSTER_N by minutes (data/player_projections.json min0) at 96x70 (cutouts shown without a chip, up to ~60 px tall), from ESPN's image service
           (a.espncdn.com, keyed by the same ESPN athlete id the whole app uses). Everyone else shows initials; on the
           website (where external images load) the page falls back to ESPN's URL for them.
  teams    all 30 logos at 48x48.

Only missing images are downloaded: an existing data/photos.json is kept, entries for players who left the top set are
dropped, so the daily job costs a handful of requests.

  python3 nba/scripts/fetch_photos.py
Writes nba/data/photos.json {heads: {athlete id: data URI}, logos: {team: data URI}}.
"""
import base64, json, os, struct, subprocess, sys, zlib
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(DATA, 'photos.json')
ROSTER_N = 10
HEAD_W, HEAD_H = 96, 70            # everyone in the top ROSTER_N
HQ_N, HQ_W, HQ_H = 4, 192, 140    # each team's top HQ_N get a sharper copy (the big header, retina lists)
HEAD = 'https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/{}.png&w=%d&h=%d'
SPEC = f'{HEAD_W}x{HEAD_H}+top{HQ_N}@{HQ_W}x{HQ_H}'
LOGO = 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/{}.png&w=48&h=48'


def alpha_bbox(png):
    """(top of the figure as a fraction of the height, horizontal centre as a fraction of the width) of a transparent RGBA PNG.
    ESPN frames every headshot a little differently; the page uses this to line every head up the same way."""
    pos, idat, w, h = 8, b'', 0, 0
    while pos < len(png):
        n, = struct.unpack('>I', png[pos:pos + 4]); typ = png[pos + 4:pos + 8]; data = png[pos + 8:pos + 8 + n]; pos += 12 + n
        if typ == b'IHDR':
            w, h, bd, ct = struct.unpack('>IIBB', data[:10])
            if ct != 6 or bd != 8:
                return None
        elif typ == b'IDAT':
            idat += data
    raw = zlib.decompress(idat); bpp, stride = 4, w * 4; prev = bytearray(stride); p = 0; top = None; x0, x1 = w, -1
    for y in range(h):
        f = raw[p]; line = bytearray(raw[p + 1:p + 1 + stride]); p += 1 + stride
        if f == 1:
            for i in range(bpp, stride): line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride): line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride): line[i] = (line[i] + (((line[i - bpp] if i >= bpp else 0) + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0; b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        xs = [i for i, v in enumerate(line[3::4]) if v > 24]
        if xs:
            top = y if top is None else top; x0 = min(x0, xs[0]); x1 = max(x1, xs[-1])
    return None if top is None else [round(top / h, 3), round((x0 + x1 + 1) / 2 / w, 3)]


def get(url):
    p = subprocess.run(['curl', '-s', '--max-time', '30', '-w', '\n%{http_code}', url], capture_output=True)
    body, _, code = p.stdout.rpartition(b'\n')
    return body if code == b'200' and body[:4] == b'\x89PNG' else None


def uri(png):
    return 'data:image/png;base64,' + base64.b64encode(png).decode()


def team_colors():
    """team abbreviation -> [primary, alternate] hex from ESPN's own box score file (the same abbreviations the app uses)"""
    out = {}
    try:
        import csv
        with open(os.path.join(HERE, '..', 'raw', 'hoopr', 'player_box_2026.csv')) as f:
            for r in csv.DictReader(f):
                a = r.get('team_abbreviation')
                if a and a not in out and r.get('team_color'):
                    out[a] = ['#' + r['team_color'], '#' + (r.get('team_alternate_color') or 'ffffff')]
                if len(out) >= 30:
                    break
    except Exception:
        pass
    return out


def main():
    proj = json.load(open(os.path.join(DATA, 'player_projections.json')))
    want, hq = {}, set()
    for t, T in proj['teams'].items():
        for i, p in enumerate(sorted(T['players'], key=lambda p: -(p.get('min0') or 0))[:ROSTER_N]):
            want[str(p['id'])] = t
            if i < HQ_N:
                hq.add(str(p['id']))
    old = json.load(open(OUT)) if os.path.exists(OUT) else {'heads': {}, 'logos': {}}
    if old.get('spec') != SPEC:      # the image size changed: refetch every headshot
        old['heads'] = {}
    heads = {k: v for k, v in old.get('heads', {}).items() if k in want}
    logos = dict(old.get('logos', {}))
    todo = [k for k in want if k not in heads]
    with ThreadPoolExecutor(8) as ex:
        for k, png in zip(todo, ex.map(lambda k: get(HEAD.format(k) % ((HQ_W, HQ_H) if k in hq else (HEAD_W, HEAD_H))), todo)):
            if png:
                heads[k] = uri(png)
    miss = [t for t in proj['teams'] if t not in logos]
    for t in miss:
        png = get(LOGO.format(t.lower()))
        if png:
            logos[t] = uri(png)
    fit = {}
    for k, v in heads.items():
        try:
            f = alpha_bbox(base64.b64decode(v.split(',', 1)[1]))
        except Exception:
            f = None
        if f:
            fit[k] = f
    json.dump({'spec': SPEC, 'heads': heads, 'hq': sorted(k for k in hq if k in heads), 'fit': fit, 'logos': logos, 'colors': team_colors()}, open(OUT, 'w'), separators=(',', ':'), sort_keys=True)
    print(f"photos: {len(heads)} headshots ({len(todo)} fetched, {len([k for k in todo if k not in heads])} without a photo), "
          f"{len(logos)} logos ({len(miss)} fetched) -> data/photos.json {os.path.getsize(OUT) // 1024} KB")


if __name__ == '__main__':
    main()
