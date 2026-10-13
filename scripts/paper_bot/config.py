"""Paper-bot settings. The kill switch and the live-trading lock live here."""
import json
import math
import os


DEFAULTS = {
    'paper_only': True,
    'kill_switch': False,
    'bankroll_start': 1000,
    'kelly_fraction': 0.25,
    'min_edge': 0.08,
    'max_edge': 0.15,
    'max_model_market_gap': 7,
    'min_price': 0.05,
    'max_price': 0.95,
    'max_spread': 0.10,
    'max_stake_per_trade': 25,
    'max_fraction_per_trade': 0.02,
    'max_stake_per_day': 100,
    'max_stake_per_market': 25,
    'max_stake_per_event': 50,
    'daily_loss_stop': 50,
    'monthly_cost_target': 30,
    'sources': {
        'nba_total': {'enabled': True},
        'cfb_ml': {'enabled': True},
    },
    'llm_filter': {
        'enabled': False,
        'env_key': 'PAPER_BOT_LLM_API_KEY',
        'url': 'https://api.openai.com/v1/chat/completions',
        'model': 'gpt-4o-mini',
        'max_calls': 20,
    },
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path=None):
    cfg = json.loads(json.dumps(DEFAULTS))
    if path and os.path.exists(path):
        with open(path) as f:
            cfg = _merge(cfg, json.load(f))
    # Emergency stop that does not need a commit. Empty / unset leaves the file's flag alone.
    if os.environ.get('PAPER_BOT_KILL', '').strip() in ('1', 'true', 'TRUE', 'yes'):
        cfg['kill_switch'] = True
    if not cfg.get('paper_only', True):
        raise SystemExit(
            'paper_only is false. This program does not place live orders and will not run in that mode.'
        )
    cfg['config_warnings'] = cap_warnings(cfg)
    return cfg


def _cap_value(cfg, key):
    """(value, problem). value is a float, None when the cap is switched off, or the default when the setting is invalid.

    Missing key means the default. Explicit null or 0 switches the cap off. Anything that is
    not a finite, non-negative number (NaN, inf, negative, bool, string) is invalid.
    """
    default = DEFAULTS[key]
    if key not in cfg:
        return float(default), None
    v = cfg[key]
    if v is None:
        return None, None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        return float(default), f'{key}={v!r} is not a finite non-negative number, using {default}'
    if v == 0:
        return None, None
    return float(v), None


def resolve_caps(cfg, min_edge=None, label=None):
    """(max_edge, max_gap, warnings) for one config view, falling back to defaults on invalid values.

    A max_edge at or below min_edge would block every trade, so it becomes max(default, min_edge + 0.05).
    """
    warnings = []
    max_edge, bad = _cap_value(cfg, 'max_edge')
    if bad:
        warnings.append(bad)
    gap, bad = _cap_value(cfg, 'max_model_market_gap')
    if bad:
        warnings.append(bad)
    if min_edge is None:
        min_edge = cfg.get('min_edge', DEFAULTS['min_edge'])
    if (max_edge is not None and isinstance(min_edge, (int, float)) and not isinstance(min_edge, bool)
            and math.isfinite(min_edge) and max_edge <= min_edge):
        used = round(max(float(DEFAULTS['max_edge']), min_edge + 0.05), 10)
        where = f' for source {label}' if label else ''
        warnings.append(f'max_edge {max_edge} <= min_edge {min_edge}{where}, using {used}')
        max_edge = used
    return max_edge, gap, warnings


def max_edge_of(cfg):
    """Edge above this is treated as a model or quote error, not a find. None or 0 turns it off."""
    return resolve_caps(cfg)[0]


def max_gap_of(cfg):
    """CFB only: |priced margin - market margin| above this many points is skipped. None or 0 turns it off."""
    return resolve_caps(cfg)[1]


def cap_warnings(cfg):
    """Every invalid cap setting, global and per source, as run-note strings."""
    out = []
    for w in resolve_caps(cfg)[2]:
        out.append('config: ' + w)
    for name, sc in (cfg.get('sources') or {}).items():
        sc = sc or {}
        if 'max_edge' not in sc and 'max_model_market_gap' not in sc and 'min_edge' not in sc:
            continue
        for w in resolve_caps({**cfg, **sc}, label=name)[2]:
            if ('config: ' + w) not in out:
                out.append(f'config ({name}): ' + w)
    return out


def source_cfg(cfg, name):
    """Global gates, with a source block able to raise min_edge or disable itself."""
    sc = dict((cfg.get('sources') or {}).get(name) or {})
    out = {
        'enabled': bool(sc.get('enabled', True)),
        'min_edge': float(sc.get('min_edge', cfg['min_edge'])),
        'max_edge': None,
        'max_model_market_gap': None,
        'min_price': float(cfg['min_price']),
        'max_price': float(cfg['max_price']),
        'max_spread': float(cfg['max_spread']),
    }
    out['max_edge'], out['max_model_market_gap'], _ = resolve_caps({**cfg, **sc}, out['min_edge'])
    for k, v in sc.items():
        if k not in out:
            out[k] = v
    return out
