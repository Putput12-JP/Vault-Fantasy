"""Paper-bot settings. The kill switch and the live-trading lock live here."""
import json
import os


DEFAULTS = {
    'paper_only': True,
    'kill_switch': False,
    'bankroll_start': 1000,
    'kelly_fraction': 0.25,
    'min_edge': 0.08,
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
    return cfg


def source_cfg(cfg, name):
    """Global gates, with a source block able to raise min_edge or disable itself."""
    sc = dict((cfg.get('sources') or {}).get(name) or {})
    out = {
        'enabled': bool(sc.get('enabled', True)),
        'min_edge': float(sc.get('min_edge', cfg['min_edge'])),
        'min_price': float(cfg['min_price']),
        'max_price': float(cfg['max_price']),
        'max_spread': float(cfg['max_spread']),
    }
    for k, v in sc.items():
        if k not in out:
            out[k] = v
    return out
