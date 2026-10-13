"""Merge two paper ledgers without losing a row. Paper only, never touches an order.

The publish step fetches the remote paper-data ledger and merges the ledger this run wrote into it, so a
run that started from an older copy cannot overwrite trades another run published in the meantime.

    python3 -m scripts.paper_bot.merge_ledger LOCAL REMOTE OUT

LOCAL is the ledger this run wrote, REMOTE the one now on the data branch (a missing or empty file counts
as no ledger), OUT the merged file (it may be the same path as LOCAL). Exit 0 on success, 2 when an input
is not a ledger. A ledger that cannot be read is an error, never an empty book, so a bad remote cannot
cause a silent overwrite.

Rules:
  trades      union by id. A row on one side only is kept. For the same id the more advanced state wins
              (graded or settled over open, a decided remainder over a pending one, a graded hold over a
              pending one), then the later update stamp, then LOCAL. A row is never dropped.
  games       strategies.cfb_jp_novig.games union by key. The more advanced state wins, then the one with
              more snapshots; snapshots are unioned by ts and deduped, except for a finished game, whose
              pruned list is kept as is.
  watch       rebuilt from the merged games, progress rebuilt from the merged trades.
  flags       config, kill_switch included, always comes from LOCAL (the current run), so clearing
              PAPER_BOT_KILL takes effect. Runtime halt state that is not derived from config (a daily loss
              stop recorded for a date) stays set if either side set it.
  runs/equity unioned by ts, same caps as the bot.
  summary     cash, summary and the strategy rollups are recomputed with the ledger code.
"""
import copy
import json
import os
import sys

from . import cfb_jp_novig
from .ledger import recompute_cash, save, summarize

RUN_CAP = 200
EQUITY_CAP = 2000
STATE_RANK = {'error': 0, 'open': 1, 'vetoed': 1, 'settled': 3, 'void': 3}
HOLD_RANK = {'pending': 0, 'no_result': 1, 'graded': 2}
GAME_RANK = {'watching': 0, 'entered': 1, 'exited': 2, 'closed': 3, 'graded': 3}
GAME_DONE = ('closed', 'graded')
STAMPS = ('ts', 'mark_ts', 'exit_ts', 'settled_ts', 'graded_ts')


class NotALedger(Exception):
    pass


def read(path):
    """The ledger at path, None when the file is missing or empty. NotALedger when it is there but unusable."""
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except ValueError as e:
        raise NotALedger(f'{path} is not valid JSON: {e}')
    if not isinstance(data, dict) or not isinstance(data.get('trades'), list):
        raise NotALedger(f'{path} is not a paper-bot ledger')
    return data


# ---- trades ---------------------------------------------------------------------------------------------

def trade_key(t):
    if t.get('id'):
        return str(t['id'])
    return 'noid:' + '|'.join(str(t.get(k)) for k in ('source', 'ticker', 'side', 'ts'))


def trade_rank(t):
    state = STATE_RANK.get(t.get('status'), 0)
    if t.get('status') == 'settled' and t.get('remainder_pending'):
        state = 2
    hold = HOLD_RANK.get(t.get('hold_status'), 0)
    upd = max([str(t[k]) for k in STAMPS if t.get(k)] or [''])
    return (state, hold, upd)


def merge_trades(local, remote):
    best = {}
    for side, rows in ((0, remote), (1, local)):     # local goes last so it wins a full tie
        for t in rows:
            if not isinstance(t, dict):
                continue
            k = trade_key(t)
            cur = best.get(k)
            if cur is None or (trade_rank(t), side) >= (trade_rank(cur[0]), cur[1]):
                best[k] = (t, side)
    rows = [copy.deepcopy(t) for t, _ in best.values()]
    rows.sort(key=lambda t: (str(t.get('ts') or ''), trade_key(t)))
    return rows


# ---- games and strategy state ---------------------------------------------------------------------------

def _snap_ts(s):
    p = cfb_jp_novig.try_parse_snap(s)
    return None if p is None else p['ts']


def union_snaps(a, b):
    """a first, so its copy of a duplicate ts wins. Sorted by ts; unreadable snapshots are kept, after the rest."""
    seen, good, bad = set(), [], []
    for s in list(a or []) + list(b or []):
        ts = _snap_ts(s)
        if ts is None:
            if s not in bad:
                bad.append(s)
        elif ts not in seen:
            seen.add(ts)
            good.append((ts, s))
    good.sort(key=lambda x: x[0])
    return [s for _, s in good] + bad


def _snap_count(gs):
    return sum(len((gs.get(v) or {}).get('snaps') or []) for v in ('novig', 'kalshi'))


def _last_snap(gs):
    return max([ts for v in ('novig', 'kalshi') for ts in (_snap_ts(s) for s in (gs.get(v) or {}).get('snaps') or []) if ts is not None] or [0])


def game_rank(gs):
    return (GAME_RANK.get(gs.get('state'), 0), 1 if gs.get('trade_id') else 0, _snap_count(gs), _last_snap(gs))


def merge_game(local, remote):
    lr, rr = game_rank(local), game_rank(remote)
    win, lose = (local, remote) if lr >= rr else (remote, local)
    out = copy.deepcopy(win)
    if out.get('state') not in GAME_DONE:
        for v in ('novig', 'kalshi'):
            if isinstance(out.get(v), dict):
                out[v]['snaps'] = union_snaps(win.get(v, {}).get('snaps'), (lose.get(v) or {}).get('snaps'))
                for f in ('listed_ts', 'first_seen_ts'):      # the earliest sighting is the true one
                    vals = [x for x in (win[v].get(f), (lose.get(v) or {}).get(f)) if x is not None]
                    if vals:
                        out[v][f] = min(vals)
    return out


def _flag_keys(d):
    return [k for k in d if isinstance(k, str) and 'halt' in k.lower()]


def keep_flags(out, *sides):
    """A runtime halt flag that either side set stays set. Config flags such as kill_switch are not handled
    here: config is taken from LOCAL whole."""
    for d in sides:
        for k in _flag_keys(d):
            if d[k] and not out.get(k):
                out[k] = copy.deepcopy(d[k])


def merge_strategy(local, remote):
    if not isinstance(local, dict) or not isinstance(remote, dict):
        return copy.deepcopy(local if isinstance(local, dict) else remote)
    win, lose = (local, remote) if str(local.get('updated') or '') >= str(remote.get('updated') or '') else (remote, local)
    out = copy.deepcopy(win)
    keep_flags(out, local, remote)
    lg, rg = local.get('games'), remote.get('games')
    if isinstance(lg, dict) or isinstance(rg, dict):
        lg, rg = lg if isinstance(lg, dict) else {}, rg if isinstance(rg, dict) else {}
        games = {}
        for key in sorted(set(lg) | set(rg)):
            if key in lg and key in rg:
                games[key] = merge_game(lg[key], rg[key])
            else:
                games[key] = copy.deepcopy(lg.get(key) or rg.get(key))
        out['games'] = games
    return out


def merge_strategies(local, remote):
    local, remote = local or {}, remote or {}
    out = {}
    for name in sorted(set(local) | set(remote)):
        out[name] = merge_strategy(local.get(name), remote.get(name))
    return out


def _by_ts(rows, cap):
    seen, out = set(), []
    for r in rows:
        k = r.get('ts') if isinstance(r, dict) and r.get('ts') else json.dumps(r, sort_keys=True)
        if k not in seen:
            seen.add(k)
            out.append(r)
    out.sort(key=lambda r: str(r.get('ts') or '') if isinstance(r, dict) else '')
    return out[-cap:]


# ---- the ledger -----------------------------------------------------------------------------------------

def merge_ledgers(local, remote):
    """The merged ledger. Either side may be None. Inputs are not modified."""
    if local is None and remote is None:
        raise NotALedger('no ledger on either side')
    if remote is None or local is None:
        out = copy.deepcopy(local if remote is None else remote)
        out.setdefault('trades', [])
        base = out
        local = remote = out
    else:
        newer_local = str(local.get('updated') or '') >= str(remote.get('updated') or '')
        base = local if newer_local else remote
        out = copy.deepcopy(base)
    out['trades'] = merge_trades(local['trades'], remote['trades'])
    out['equity'] = _by_ts(list(remote.get('equity') or []) + list(local.get('equity') or []), EQUITY_CAP)
    out['runs'] = _by_ts(list(remote.get('runs') or []) + list(local.get('runs') or []), RUN_CAP)
    upd = [str(x['updated']) for x in (local, remote) if x.get('updated')]
    out['updated'] = max(upd) if upd else None
    out['paper_only'] = True
    out['live_orders'] = False
    strategies = merge_strategies(local.get('strategies'), remote.get('strategies'))
    if strategies:
        out['strategies'] = strategies
    if isinstance(local.get('config'), dict):       # the current run's config wins, kill_switch included
        out['config'] = copy.deepcopy(local['config'])
    keep_flags(out, local, remote)
    st = (out.get('strategies') or {}).get(cfb_jp_novig.STRATEGY)
    if isinstance(st, dict) and isinstance(st.get('games'), dict):
        st['progress'] = cfb_jp_novig.build_progress(out['trades'], st.get('progress'))
        st['watch'] = cfb_jp_novig.CfbJpNovig._watch(None, st)
    recompute_cash(out)
    summarize(out)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print('usage: python3 -m scripts.paper_bot.merge_ledger LOCAL REMOTE OUT', file=sys.stderr)
        return 2
    local_path, remote_path, out_path = argv
    try:
        local, remote = read(local_path), read(remote_path)
        merged = merge_ledgers(local, remote)
    except NotALedger as e:
        print(f'merge_ledger: {e}', file=sys.stderr)
        return 2
    save(out_path, merged)
    n_l = len(local['trades']) if local else 0
    n_r = len(remote['trades']) if remote else 0
    print(f"merge_ledger: local {n_l} trades, remote {n_r}, merged {len(merged['trades'])} -> {out_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
