// Rotation-aware minutes (C3) and the GP rescale: JavaScript twin of scripts/rotation_minutes.py + Pricer.game_minutes_rot + Pricer.gp_minutes
// (docs/minutes-bakeoff-results.md). Inlined into the page by scripts/render_app.py (/*ROTATION_MINUTES_JS*/) and loaded by node in
// scripts/check_rotation_minutes_js_parity.py, which proves it returns Python's minutes. No DOM, no globals: everything it needs is passed in.
const RM_SD_MARGIN = 13.2, RM_ROT_CUT = 12.0;
function rmErf(x){                       // double-precision erf: Taylor series for small |x|, continued-fraction erfc beyond
  const ax = Math.abs(x);
  if (ax < 2.5){
    let term = ax, sum = ax;
    for (let n = 1; n < 80; n++){ term *= -ax * ax / n; sum += term / (2 * n + 1); }
    return Math.sign(x) * 2 / Math.sqrt(Math.PI) * sum;
  }
  let f = 0;                             // erfc(x) = exp(-x^2)/(x sqrt(pi)) / (1 + 1/(2x^2)/(1 + 2/(2x^2)/(1 + ...)))
  for (let k = 60; k >= 1; k--) f = (k / 2) / (ax + f);
  return Math.sign(x) * (1 - Math.exp(-ax * ax) / Math.sqrt(Math.PI) / (ax + f));
}
function rmPhi(x){ return 0.5 * (1 + rmErf(x / Math.sqrt(2))); }
function rmPis(e){
  e = e == null ? 0 : e;
  const cdf = x => rmPhi((x - e) / RM_SD_MARGIN), p10 = cdf(10) - cdf(-10), p20 = cdf(20) - cdf(-20);
  return [p10, p20 - p10, 1 - p20];
}
function rmSig(z){ return 1 / (1 + Math.exp(-Math.max(-30, Math.min(30, z)))); }
function rmSizeFeats(r){ const n = r.size; return [n / 15, n >= 15 ? 1 : 0, n <= 12 ? 1 : 0, (n - 13) / 5 * r.rank / 10]; }
function rmXCommon(r){
  return [1, r.m / 48, r.st, Math.min(r.n, 30) / 30, r.rank / 10, r.rank > 8 ? 1 : 0, r.d3 / 10, r.gap / 10, Math.min(r.last_days, 30) / 30,
          r.vs / 48, r.vo / 48, r.nout / 5, r.b2b, r.home, ...rmSizeFeats(r)];
}
function rmXMin(r){ return [1, r.m / 48, r.st, r.vs / 48, r.vo / 48, r.d3 / 10, r.b2b, r.home, r.rank / 10, r.nout / 5, ...rmSizeFeats(r)]; }
const rmDot = (w, x) => w.reduce((a, b, i) => a + b * x[i], 0);
function rmPredictState(M, r){
  const pp = rmSig(rmDot(M.wp, rmXCommon(r))), pr = rmSig(rmDot(M.wr, rmXCommon(r)));
  const mu = Math.max(RM_ROT_CUT, rmDot(M.wm, rmXMin(r)));
  return [pp, pr, pr * mu + (1 - pr) * M.g];
}
// preds: [[P(plays), conditional minutes]] -> conditional minutes after the pool's unconditional total is set to T
function rmRescale(preds, T){
  const tot = preds.reduce((a, [p, m]) => a + p * m, 0), f = tot > 0 && preds.length >= 7 ? T / tot : 1;
  return preds.map(([p, m]) => Math.min(48, f * p * m / Math.max(p, 1e-3)));
}
function rmScorePool(model, rows){
  if (!rows.length) return [];
  const pi = rmPis(rows[0].e), per = [0, 1, 2].map(s => rows.map(r => rmPredictState(model.states[s], r)));
  const mix = k => rows.map((_, i) => pi[0] * per[0][i][k] + pi[1] * per[1][i][k] + pi[2] * per[2][i][k]);
  const mixp = mix(0), mixr = mix(1), mixm = mix(2);
  const cm = rmRescale(mixp.map((p, i) => [p, mixm[i]]), model.T);
  return rows.map((_, i) => ({min: cm[i], p_rot: mixr[i], p_plays: mixp[i]}));
}
// The pool and its rows exactly as Pricer.game_minutes_rot builds them.
//   M = minutes block (rot_min, rot_days), state = live model state (players, team_last, team_gn, last3, last_idx), out = {pid: 1} for Out / Doubtful / Inactive,
//   rosterIds = current roster ids, g = {id, tip, home, spread, season_type}.  -> {pid: {min, p_rot, p_plays}} ({} when the state cannot support it)
function rotMinutes(model, M, state, team, g, out, rosterIds){
  if (!model || !M || !state || g.season_type === 1 || !state.last_idx || !state.last3) return {};
  const P = state.players, S = a => P[String(a)] || {}, tip = g.tip;
  const rot = {};
  for (const [a, v] of Object.entries(P)) if (v && v.ms && v.ms[3] === team && v.ms[0] >= M.rot_min && v.ms[4] >= tip - M.rot_days * 86400) rot[+a] = v.ms;
  const roster = new Set(rosterIds.map(Number));
  for (const [a, v] of Object.entries(P)) if (v && v.ms && v.ms[3] === team && v.ms[4] >= tip - 30 * 86400) roster.add(+a);
  const cand = [...roster].sort((x, y) => x - y).filter(a => S(a).ms && S(a).ms[3] === team && S(a).r && !out[a]);
  if (!cand.length) return {};
  const tl = (state.team_last || {})[team], b2b = tl && tip - tl < 30 * 3600 ? 1 : 0;
  const tgn = (state.team_gn || {})[team] || 0, L3 = state.last3 || {}, LI = state.last_idx || {};
  const nout = Object.keys(rot).filter(a => out[a]).length;
  const order = [...cand].sort((x, y) => S(y).ms[0] - S(x).ms[0]), rank = {};
  order.forEach((a, i) => { rank[a] = i + 1; });
  const rows = cand.map(a => {
    const ms = S(a).ms, h = L3[String(a)], li = LI[String(a)];
    let vs = 0, vo = 0;
    for (const [b, q] of Object.entries(rot)){ if (+b === a) continue; if (q[2] === ms[2]) vs += q[0] * (out[+b] || 0); else vo += q[0] * (out[+b] || 0); }
    return {m: ms[0], st: ms[1], n: ms[5], rank: rank[a], d3: h && h.length ? h.reduce((x, y) => x + y, 0) / h.length - ms[0] : 0,
            gap: li && li[0] === team ? Math.min(10, tgn - li[1]) : (tgn < 3 ? 0 : 10), last_days: (tip - ms[4]) / 86400, vs, vo, nout, b2b,
            home: team === g.home ? 1 : 0, size: cand.length, e: g.spread};
  });
  const res = rmScorePool(model, rows), o = {};
  cand.forEach((a, i) => { o[a] = res[i]; });
  return o;
}
// GP: GBM conditional minutes (v2's number where the GBM has none) x C3 P(plays), pool rescaled to T expected. rt = rotMinutes(), gb = gbmMinutes(), v2 = {pid: v2 minutes}
function gpMinutes(model, rt, gb, v2){
  const ids = Object.keys(rt).map(Number).sort((x, y) => x - y);
  if (ids.length < 7) return {};
  const cm = rmRescale(ids.map(a => [rt[a].p_plays, a in gb ? gb[a] : (a in v2 ? v2[a] : rt[a].min)]), model.T), o = {};
  ids.forEach((a, i) => { o[a] = {min: cm[i], p_plays: rt[a].p_plays, p_rot: rt[a].p_rot}; });
  return o;
}
if (typeof module !== 'undefined') module.exports = {rmErf, rmScorePool, rotMinutes, gpMinutes, rmRescale};
