"""Shared helpers for the signal research scripts. Free data only: the stored ledger (state.json on the sharp-data branch) and data/*.json.
Nothing here estimates a price. ROI uses a stored price, CLV uses a stored closing value (or close minus fair when both are stored)."""
import json, math, os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def load_state(path=None):
    """state.json from a path, else from the sharp-data branch (git show origin/sharp-data:state.json)."""
    if path:
        return json.load(open(path))
    out = subprocess.run(['git', '-C', ROOT, 'show', 'origin/sharp-data:state.json'], capture_output=True, check=True).stdout
    return json.loads(out)


def stats(rows):
    """rows: dicts with res (1/-1/0), fair (win prob when logged, or None), px (stored exchange price as probability, or None), clv (stored, or None)."""
    w = sum(r['res'] > 0 for r in rows); l = sum(r['res'] < 0 for r in rows); p = len(rows) - w - l; n = w + l
    fr = [r['fair'] for r in rows if r['res'] != 0 and r.get('fair') is not None]
    ex = None
    fw = [r for r in rows if r['res'] != 0 and r.get('fair') is not None]   # only rows that stored a fair probability
    if fw:
        ex = sum(r['res'] > 0 for r in fw) / len(fw) - sum(r['fair'] for r in fw) / len(fw)
    pr = [r for r in rows if r['res'] != 0 and r.get('px')]
    roi = None
    if pr:
        pnl = sum(((1 - r['px']) / r['px']) if r['res'] > 0 else -1 for r in pr)
        roi = pnl / len(pr)
    cl = [r['clv'] for r in rows if isinstance(r.get('clv'), (int, float))]
    z = (w - n * 0.5) / math.sqrt(n * 0.25) if n else None
    # z against the logged fair probability (what the market said), not 50%
    zf = None
    if fw:
        e = sum(fr); v = sum(f * (1 - f) for f in fr)
        zf = (sum(r['res'] > 0 for r in fw) - e) / math.sqrt(v) if v > 0 else None
    r3 = lambda x: None if x is None else round(x, 3)
    return dict(n=len(rows), fair_n=len(fw), w=w, l=l, p=p, win=r3(w / n) if n else None, vs_fair=r3(ex), z_vs_fair=r3(zf), roi_stored_px=r3(roi), roi_n=len(pr),
                clv=r3(sum(cl) / len(cl)) if cl else None, clv_n=len(cl), z_vs_50=r3(z))


def verdict(test, min_n=100):
    """A signal earns a place in the agree count only if, on held-out games, it beats what the market implied AND is positive on every stored
    price measure it has, with at least min_n decisions."""
    n = test['w'] + test['l']
    why = []
    if n < min_n: why.append(f'held-out decisions {n} < {min_n}')
    if test['vs_fair'] is None or test['vs_fair'] <= 0: why.append('does not beat the logged fair probability')
    elif test['z_vs_fair'] is not None and test['z_vs_fair'] < 1.64: why.append(f"excess over fair not significant (z {test['z_vs_fair']})")
    if test['roi_stored_px'] is not None and test['roi_stored_px'] <= 0: why.append('ROI at the stored price is not positive')
    if test['clv'] is not None and test['clv'] <= 0: why.append('mean closing-line value is not positive')
    return ('ADD' if not why else 'LEAVE OUT'), why
