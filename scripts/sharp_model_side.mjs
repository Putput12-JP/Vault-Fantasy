/* Which side does OUR model like on the same bet a Top Read shows?
   Read from the model files already in the repo (NFL / CFB spread model, CFB totals model, NBA game-model
   ratings). Nothing is invented: if a model has no number for a game, the answer is null.
   The edge is measured against the read's own line, so the model and the read are compared on one number.
   Sharp accounts are context only and never count toward an agree total, and neither does this. */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const STRONG = { nfl: 3, cfb: 5, nba: 3 };            // same thresholds as the model pages: spread / moneyline edge
const STRONG_TOT = 5;
const NFL_AB = { JAC: 'JAX', LAR: 'LA', WSH: 'WAS', OAK: 'LV' };
const NBA_AB = { NOP: 'NO', NYK: 'NY', GSW: 'GS', SAS: 'SA', UTA: 'UTAH', WAS: 'WSH', BRK: 'BKN', PHO: 'PHX' };
const norm = s => String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const rj = f => { try { return JSON.parse(readFileSync(f, 'utf8')); } catch { return null; } };

export function loadModelIndex(root) {
  const nfl = rj(resolve(root, 'data', 'nfl_model.json')), cfb = rj(resolve(root, 'data', 'cfb_model.json'));
  const nba = rj(resolve(root, 'nba', 'data', 'game_model.json')), logos = rj(resolve(root, 'scripts', 'sharp_money_card', 'cfb_logos.json')) || {};
  const tot = new Map();
  for (const r of (cfb && cfb.totals && cfb.totals.rows) || []) if (r.model_total != null) tot.set(`${r.home_id}|${r.away_id}`, r);
  const board = x => [...((x && x.board) || []), ...((x && x.slate) || [])];
  return { nfl: board(nfl), cfb: board(cfb), nba, logos, tot, abbr2id: {}, asof: { nfl: nfl && nfl.generated, cfb: cfb && cfb.generated, nba: nba && nba.generated } };
}

// Action Network abbreviations -> ESPN ids, learned from every game that carries a full name.
export function learnAbbrs(idx, games) {
  for (const g of games || []) {
    if (g.sport !== 'cfb') continue;
    for (const s of ['home', 'away']) { const t = g[s] || {}, id = idx.logos[norm(t.name)]; if (id && t.abbr) idx.abbr2id[t.abbr] = id; }
  }
}

function resolveRow(idx, p, g) {
  const rows = idx[p.sport];
  if (!rows) return null;
  const byKey = rows.find(r => r.key === p.game);
  if (byKey) return { row: byKey, src: 'key' };
  const [a0, h0] = String(p.gameLbl || '').split(' @ ').map(x => x.trim());
  if (p.sport === 'nfl') {
    const a = NFL_AB[a0] || a0, h = NFL_AB[h0] || h0;
    const c = rows.filter(r => r.home === h && r.away === a && Math.abs(r.kick - p.start) < 3 * 86400);
    return c.length === 1 ? { row: c[0], src: 'abbr' } : null;
  }
  if (p.sport !== 'cfb') return null;
  let ids = g && g.home && g.away ? [idx.logos[norm(g.home.name)], idx.logos[norm(g.away.name)]] : [];
  if (ids.length < 2 || ids.includes(undefined)) ids = [idx.abbr2id[h0], idx.abbr2id[a0]];
  if (ids[0] && ids[1]) {
    const c = rows.filter(r => r.home_id === ids[0] && r.away_id === ids[1] && Math.abs(r.kick - p.start) < 2 * 86400);
    if (c.length === 1) return { row: c[0], src: 'id' };
  }
  if (p.hline != null) {                              // last resort: same kickoff and a line within a point of the read's
    const best = rows.filter(r => Math.abs(r.kick - p.start) <= 2700).map(r => {
      const gaps = [r.market_margin, r.open_margin].filter(x => x != null).map(x => Math.abs(-p.hline - x));
      return { r, gap: gaps.length ? Math.min(...gaps) : 99 };
    }).sort((x, y) => x.gap - y.gap);
    if (best.length && best[0].gap <= 1 && (best.length === 1 || best[1].gap - best[0].gap > 0.5)) return { row: best[0].r, src: 'line' };
  }
  return null;
}

/* pick: { game, sport, gameLbl, start, m, side, hline, line }. g: the live game (names), optional.
   -> { side, edge, strong, src, asof } or null. */
export function modelSideFor(idx, p, g) {
  if (!idx || !p) return null;
  let mm, src, asof = idx.asof[p.sport] || null, row = null;
  if (p.sport === 'nba') {
    const R = idx.nba && idx.nba.ratings;
    if (!R || p.m === 'tot') return null;
    const [a0, h0] = String(p.gameLbl || '').split(' @ ').map(x => x.trim()), a = NBA_AB[a0] || a0, h = NBA_AB[h0] || h0;
    if (!R[a] || !R[h]) return null;
    mm = R[h].net - R[a].net + idx.nba.hfa; src = 'ratings';
  } else {
    const f = resolveRow(idx, p, g);
    if (!f) return null;
    row = f.row; mm = row.model_margin; src = f.src;
    if (mm == null) return null;
  }
  const lim = STRONG[p.sport];
  if (p.m === 'ml') return { side: mm > 0 ? 'home' : 'away', edge: Math.round(Math.abs(mm) * 10) / 10, strong: Math.abs(mm) >= lim, src, asof };
  if (p.m === 'sp') {
    if (p.hline == null) return null;
    const e = mm + p.hline;                            // hline is the home spread: home covers when e > 0
    return { side: e > 0 ? 'home' : 'away', edge: Math.round(Math.abs(e) * 10) / 10, strong: Math.abs(e) >= lim, src, asof };
  }
  if (p.m === 'tot' && p.sport === 'cfb' && row && p.line != null) {
    const t = idx.tot.get(`${row.home_id}|${row.away_id}`);
    if (!t) return null;
    const e = t.model_total - p.line;
    return { side: e > 0 ? 'over' : 'under', edge: Math.round(Math.abs(e) * 10) / 10, strong: Math.abs(e) >= STRONG_TOT, src, asof };
  }
  return null;
}
