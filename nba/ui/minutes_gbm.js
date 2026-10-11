// Minutes GBM (shadow): JavaScript twin of scripts/minutes_gbm.py + Pricer.game_minutes_gbm. Inlined into the page by
// scripts/render_app.py (/*MINUTES_GBM_JS*/) and loaded by node in scripts/check_minutes_gbm_js_parity.py, which proves it
// returns the Python scorer's minutes. No DOM, no globals: everything it needs is passed in.
const GBM_ROT_MIN = 10, GBM_ROT_DAYS = 21, GBM_DAY = 86400;
function gbmRotation(players, team, tip){
  const lim = tip - GBM_ROT_DAYS * GBM_DAY, rot = {};
  for (const [a, p] of Object.entries(players)) if (p.team === team && p.ew[1] >= GBM_ROT_MIN && p.last >= lim) rot[a] = p;
  return rot;
}
function gbmTeamContext(tips, tip){
  const last = tips && tips.length ? tips[tips.length - 1] : null;
  const b2b = last !== null && tip - last < 30 * 3600 ? 1 : 0;
  const g7 = (tips || []).filter(t => tip - t < 7 * GBM_DAY).length;
  const rest = last !== null ? Math.min(10, (tip - last) / GBM_DAY) : 5;
  return [b2b, g7, rest];
}
function gbmFeatures(p, aid, rot, out, tip, ctx, home, margin, grp){
  const [b2b, g7, rest] = ctx;
  let vs = 0, vo = 0;
  for (const [a, q] of Object.entries(rot)){
    if (!out.has(a) || a === String(aid)) continue;
    if (q.pos === grp) vs += q.ew[1]; else vo += q.ew[1];
  }
  const h = p.h, m5 = h.reduce((x, y) => x + y, 0) / h.length;
  const sd5 = Math.sqrt(h.reduce((x, y) => x + (y - m5) * (y - m5), 0) / h.length);
  return [p.ew[0], p.ew[1], p.ew[2], p.lastm, m5, p.st, p.last_start, rest, g7, home,
          Math.min(60, (tip - p.last) / GBM_DAY), vs, vo, margin !== null ? Math.abs(margin) : 6, b2b,
          grp === 'G' ? 1 : 0, grp === 'C' ? 1 : 0, sd5, Math.min(p.n, 200),
          margin !== null ? (home ? margin : -margin) : 0, out.size];
}
function gbmPredict(model, x){
  let s = 0;
  for (const tr of model.trees){
    let i = 0;
    while (tr.f[i] >= 0) i = x[tr.f[i]] <= tr.t[i] ? tr.l[i] : tr.r[i];
    s += tr.v[i];
  }
  return s;
}
// exported player row [ew1, ew2, ew3, lastm, last_start, st, n, h, team, last, pos] -> player object
function gbmPlayer(r){ return {ew: [r[0], r[1], r[2]], lastm: r[3], last_start: r[4], st: r[5], n: r[6], h: r[7], team: r[8], last: r[9], pos: r[10]}; }
// {pid: minutes} for one team in one game. gb = state.gbm, g = {id, tip, home, spread}, status = {pid: 'Out'|...}, rosterIds = current roster ids
function gbmMinutes(model, gb, team, g, status, rosterIds){
  if (!model || !gb) return {};
  const players = {};
  for (const [a, r] of Object.entries(gb.players)) players[a] = gbmPlayer(r);
  const tip = g.tip, outIds = new Set(Object.entries(status).filter(([, s]) => s === 'Out' || s === 'Doubtful' || s === 'Inactive').map(([a]) => String(a)));
  const rot = gbmRotation(players, team, tip), out = new Set(Object.keys(rot).filter(a => outIds.has(a)));
  const ctx = gbmTeamContext(gb.team_tips[team] || [], tip), sp = g.spread, margin = sp != null ? -sp : null;
  const roster = new Set(rosterIds.map(String));
  for (const [a, p] of Object.entries(players)) if (p.team === team && p.last >= tip - 30 * GBM_DAY) roster.add(a);
  const pm = {};
  for (const a of [...roster].sort((x, y) => x - y)){
    const p = players[a];
    if (!p || outIds.has(a) || p.n < 5) continue;
    pm[a] = Math.max(0, Math.min(48, gbmPredict(model, gbmFeatures(p, a, rot, out, tip, ctx, team === g.home ? 1 : 0, margin, p.pos))));
  }
  return pm;
}
if (typeof module !== 'undefined') module.exports = {gbmMinutes, gbmFeatures, gbmPredict, gbmRotation, gbmTeamContext, gbmPlayer};
