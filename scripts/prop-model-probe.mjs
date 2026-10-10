/* ════════════════════════════════════════════════════════════════════════
   VAULT · PROP MODEL PROBE  (read by track-prop-plays.mjs)

   What the Vault prop model says about ONE line, computed the same way the Best
   Bets builder and the Edge Board compute it (this is scripts/build_best_bets.mjs's
   fairProbOver, imported, not copied): recency-weighted volume x efficiency, the
   corroborated role anchor, the opponent / environment / game-script / wind
   multipliers, then the per-market distribution and isotonic calibration.

   The Sharp Money Props page prices off the market, not the model. This lets the
   play ledger bank the model's number next to every +EV call, so the model can be
   scored as a tilt on the price (scripts/fit_prop_offset.py) before any of it
   changes what a user sees.

   makeModelProbe(feed) -> (pid, mkt, line) => { proj, over, games, roleMult } | null
   Lazy and null-safe: a missing prop_model.json, game log, or unmodeled market
   returns null and the ledger row simply carries no model block.
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { fairProbOver, loadRoleParams, buildMatchupCtx, matchupAdjFor, roleCorrobSet, setSeasons } from './build_best_bets.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

export function makeModelProbe(feed) {
  let st;   // undefined = not built yet, null = unavailable
  const build = () => {
    try {
      const PM = JSON.parse(readFileSync(resolve(ROOT, 'data/prop_model.json'), 'utf8'));
      if (!PM?.markets) return null;
      const cur = Number(feed?.season); if (cur >= 2024) setSeasons([cur - 1, cur]);   // log window [prev, cur], same roll as the builder's main()
      return { PM, props: feed?.vegas_player_props || {}, depth: feed?.vegas_depth || {}, roleOk: roleCorrobSet(feed || {}), rp: loadRoleParams(), ctx: buildMatchupCtx(feed || {}) };
    } catch { return null; }
  };
  return (pid, mkt, line) => {
    if (st === undefined) st = build();
    if (!st || line == null) return null;
    const p = st.props[pid]; if (!p || !st.PM.markets[mkt]) return null;
    try {
      const dep = st.depth[pid], rank = dep && dep[0] != null && st.roleOk.has(String(pid)) ? dep[0] : null;
      const role = st.rp && rank != null && p.pos ? { params: st.rp, pos: p.pos, rank } : null;
      const v = fairProbOver(st.PM, p.name, mkt, Number(line), role, matchupAdjFor(st.ctx, p, mkt));
      return v ? { proj: v.proj, over: v.over, games: v.games, roleMult: v.roleMult } : null;
    } catch { return null; }
  };
}
