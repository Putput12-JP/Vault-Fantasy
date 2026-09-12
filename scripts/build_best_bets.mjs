#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · BEST BETS  →  data/lineup-feed.json (best_bets)
   ────────────────────────────────────────────────────────────────────────
   Precomputes Vault's top prop picks of the slate so the Betting tab can show
   a "Best Bets" hero without every client re-scoring the whole board.

   It scores EVERY prop in the feed with the SAME model + gates the UI uses, so
   the list is honest — not "top 3 by raw EV", which would surface exactly the
   junk the board already guards against:

     • the SAME projection prop-model.js fairProbOver computes: recency-weighted
       volume × efficiency, with VOLUME anchored toward the player's current,
       book-corroborated depth role (data/role_volume.json) → per-market
       distribution → P(over) → isotonic calibration → market shrink. Reads the
       same data/nflverse_stats_<season>.json game logs prop-history.js uses. The
       role anchor is what keeps the hero and the board from disagreeing on a
       role-changed player (a rookie RB1 no longer carrying his committee-back
       reception history); it replaced an older workbook blend the board never used.
     • only the 9 MODELED markets (prop_model.json) — the ones with measured
       signal; nothing else is scored.
     • CORROBORATION gate: a line needs ≥2 books agreeing within tolerance.
       A lone-book line (the phantom-edge trap) is never a best bet.
     • CONFIDENCE shrink: the favored-side probability is pulled toward a coin
       flip on thin samples (vaultGrade padj), so a 3-game hot streak can't
       masquerade as a lock.
     • ranked by CONFIDENCE-ADJUSTED EV vs the best available price (line-first,
       so flat DFS pricing can't win a cell on price alone).

   Game "leans" (spreads/totals) come from data/game_model.json — but that
   model MATCHES the market without beating it, so they ship as clearly-labeled
   CONTEXT, never as edge, and are empty while the model is in its offseason
   gate (the same gate the game-line UI honors).

   Writes feed.best_bets = { generated, season, week, be_ref, props:[…],
   game_leans:[…], note }. Run AFTER the props fetch so it scores fresh lines.

   Run:  node scripts/build_best_bets.mjs                 # score, write feed
         node scripts/build_best_bets.mjs --dry           # score, print, no write
         node scripts/build_best_bets.mjs --top=3         # how many props (default 3)
   ════════════════════════════════════════════════════════════════════════ */
'use strict';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');
const ARG = Object.fromEntries(process.argv.slice(2).map(a => {
  const m = a.match(/^--([^=]+)(?:=(.*))?$/); return m ? [m[1], m[2] ?? true] : [a, true];
}));
const DRY   = !!ARG.dry;
const TOP   = Number(ARG.top || 4);
const LEANS = Number(ARG.leans || 3);
const FEED  = ARG.feed || resolve(ROOT, 'data/lineup-feed.json');
const KPROPS = ARG.kprops || resolve(ROOT, 'data/kalshi_props.json');
let   SEASONS = [2024, 2025];                 // log window [prev, cur] — reset from feed.season in main() so it rolls to [cur-1, cur] once the new season's nflverse logs land (mirrors the client's ebVaultSeasons)
const BE_REF = 0.524;                         // standard -110 book break-even (entry-agnostic bar)
const MIN_GAMES = 8;                          // enough log to trust the projection
const PRICE_MIN = -250, PRICE_MAX = 200;      // bettable band: no -300 chalk, no lottery longshots
// Gate 2 — a "consensus" of DFS pick'em apps is not a beatable market. Their
// yardage lines run low and price flat, so ranking by EV against them surfaces
// the biggest model-vs-line disagreements (the least trustworthy bets). A best
// bet must be corroborated by ≥1 TRUE sportsbook at the scored line.
const DFS_BOOKS = new Set(['prizepicks', 'underdog fantasy', 'underdog', 'sleeper']);
const isRealBook = b => !!b && !DFS_BOOKS.has(String(b).toLowerCase());
// Gate 1 — model-vs-market disagreement cap on volume-yardage markets. When the
// projection strays past this fraction of a corroborated line, the model and
// the market are describing different situations — a stale-usage projection on
// a player whose role collapsed (a starter's game logs on a now-backup TE like
// Cole Kmet: model 23 rec yds vs a 7.5 line Loveland now owns) — not an edge.
// This fires REGARDLESS of role-corroboration: the role gate only checks
// depth-chart ORDER, so a correctly-ranked backup (TE2 behind TE1) sails
// through with a stale projection unless the magnitude is checked too. Applies
// to every VOLUME market (yards, receptions, attempts, completions) — TD
// markets are excluded because their low lines make a relative gap meaningless
// and they carry their own tail guards.
const VOL_MK = new Set(['pass_yd', 'pass_att', 'pass_cmp', 'rush_yd', 'rush_att', 'rec', 'rec_yd']);
const MAX_PROJ_GAP = 0.40;
// Absolute-count guard. On a LOW integer-count line the relative MAX_PROJ_GAP is
// too loose: a projection half a catch below a 1.5 line (e.g. a part-time rookie's
// ~0.9 backward-looking log projection) is only a 40% gap, so it clears the ratio
// gate — yet it flips the pick into a plus-money Under longshot and manufactures a
// huge phantom EV. Guard the low-side longshot directly: block when the projection
// sits ≥ABS_COUNT_GAP BELOW a low count line. Only the under side needs it — an
// over phantom on a small line means proj sits far ABOVE the line, which already
// trips the ratio gate. (This is the Bhayshul Tuten "Under 1.5 Rec, +59.9% EV"
// case: log proj ~0.9 while his actual role projects ~2.5, so the board leaned Over.)
const COUNT_MK = new Set(['pass_att', 'pass_cmp', 'rush_att', 'rec']);
const LOW_COUNT_LINE = 3.5;   // where the Under is still a plus-money longshot
const ABS_COUNT_GAP = 0.5;    // half a count below the line flips the side w/o moving the ratio much
// Gate 3 — sharp-anchor agreement. Kalshi is a real-money exchange; its two-
// sided price on a player prop is a sharp fair the projection can be wrong
// about. When our confidence-adjusted prob for a side disagrees with the
// exchange's fair for that SAME side by more than SHARP_GAP, the projection is
// contrarian to real money — cap the grade below B so it can't headline (same
// shape as the role-unconfirmed cap; we demote, we don't invent an edge from
// the disagreement). Trust the exchange ONLY when the strike matches the line
// and the market is genuinely liquid — a thin exchange market is worse than
// none, so a 2-contract quote never fades a Vault grade. Null-safe: if
// kalshi_props.json is missing/thin, sharpFairFor returns null and nothing is
// gated, exactly like a cold cache in the trade engines.
const SHARP_GAP = 0.10;          // ≥10-point prob disagreement on the same side → demote
const SHARP_MIN_OI = 50;         // contracts of open interest before we trust the price
const SHARP_MAX_SPREAD = 0.06;   // yes bid/ask spread ($) — wider = too thin/stale to fade on
const SHARP_STRIKE_TOL = 0.25;   // exchange strike must match the book line (counts align on .5)
// Gate 4 — early-season receptions-UNDER hold. The audit (docs/prop-rec-under-
// bias-finding.md) proved the rec projection is out-of-sample UNBIASED (+0.14
// signed error), so the wall of grade-A rec unders in weeks 1-3 is NOT a low
// projection — it is a backward-looking model (2025-only log window at
// SEASONS=[cur-1,cur]) betting unders into book lines that price a 2026 role the
// tape can't see yet. The honest response is discipline, not a projection boost:
// hold rec count-market unders while the window is essentially last season only.
// This is a GATE, not a model change (needs no walk-forward), and it is behind a
// flag so it can be A/B'd against the go-forward CLV harness — the only valid
// arbiter for this market-disagreement regime. `--rechold=0` disables it;
// `--rechold=N` sets the week cutoff. Default 3 (weeks 1-3).
const EARLY_REC_HOLD_WEEKS = ARG.rechold != null ? Number(ARG.rechold) : 3;
const log = (...a) => console.log('[best-bets]', ...a);

/* ── data-key helpers (mirror the app) ─────────────────────────────────── */
const nkey = s => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z]/g, '');
const num = v => { const f = Number(v); return Number.isFinite(f) ? f : null; };
const round = (x, n) => { const f = 10 ** n; return Math.round(x * f) / f; };
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

/* ── matchup context: opponent (DvP) + environment (implied total) + game script
   (spread-driven pass/rush skew). The Edge Board applies all three to its
   projection; the Best Bets builder applied NONE, so the hero and the board
   scored the same player differently. Adopt the SAME three signals here, from the
   same feed + fitted model, so they agree. Every term is null-safe → ×1. ─────── */
const _ENV_AVG = 22.5, _ENV_BETA = 0.5;                 // mirror index.html matchupAdj
function loadGameScript() {
  try { return JSON.parse(readFileSync(resolve(ROOT, 'data/game_script_model.json'), 'utf8')); }
  catch { return null; }
}
function gsFamily(gs, mk) {
  const f = gs && gs.families; if (!f) return null;
  if ((f.rush || []).includes(mk)) return 'rush';
  if ((f.pass_td || []).includes(mk)) return 'pass_td';
  if ((f.pass || []).includes(mk)) return 'pass';
  return null;
}
// Per-market script multiplier — 1× when the model is absent, inactive (its ship
// gate not yet cleared in-season), off-family, or the spread is unknown.
function scriptMultOf(gs, mk, spread) {
  if (!gs || gs.active !== true || spread == null) return 1;
  const fam = gsFamily(gs, mk); if (!fam) return 1;
  const spref = gs.SP_REF || 10, lo = (gs.clamp && gs.clamp[0]) || 0.9, hi = (gs.clamp && gs.clamp[1]) || 1.12;
  const s = clamp(spread / spref, -1, 1);               // favorite < 0, dog > 0
  let raw = fam === 'rush' ? 1 + (gs.K_RUSH || 0) * (-s) : 1 + (gs.K_PASS || 0) * s;
  if (fam === 'pass_td') { const d = gs.td_damp == null ? 0.5 : gs.td_damp; raw = 1 + d * (raw - 1); }
  return clamp(raw, lo, hi);
}
function buildMatchupCtx(feed) {
  const dvp = feed.dvp || {}, leagueFpa = {};
  for (const pos of ['QB', 'RB', 'WR', 'TE']) {
    let s = 0, n = 0;
    for (const t in dvp) { const c = dvp[t] && dvp[t][pos]; if (c && c.fpa != null) { s += c.fpa; n++; } }
    leagueFpa[pos] = n ? s / n : null;
  }
  const spreadByTeam = {}, totalByTeam = {};
  for (const g of (feed.vegas_games || [])) {
    const sp = g.spread && g.spread.cons, tot = g.total && g.total.cons;
    if (sp) { if (g.home) spreadByTeam[g.home] = num(sp.home); if (g.away) spreadByTeam[g.away] = num(sp.away); }
    if (tot != null) { if (g.home) totalByTeam[g.home] = num(tot); if (g.away) totalByTeam[g.away] = num(tot); }
  }
  return { dvp, leagueFpa, spreadByTeam, totalByTeam, gs: loadGameScript() };
}
function matchupAdjFor(ctx, p, mk) {
  let oppMult = 1, envMult = 1;
  if (p.opp && p.pos) {
    const c = ctx.dvp[p.opp] && ctx.dvp[p.opp][p.pos], avg = ctx.leagueFpa[p.pos];
    if (c && c.fpa != null && avg) oppMult = clamp(c.fpa / avg, 0.88, 1.15);
  }
  const spread = p.team != null ? (ctx.spreadByTeam[p.team] ?? null) : null;
  const total = p.team != null ? (ctx.totalByTeam[p.team] ?? null) : null;
  if (total != null && spread != null) envMult = clamp(1 + _ENV_BETA * ((total / 2 - spread / 2) / _ENV_AVG - 1), 0.92, 1.10);
  return { oppMult, envMult, scriptMult: scriptMultOf(ctx.gs, mk, spread) };
}

/* ── nflverse game logs → per-player weeks (mirror prop-history.js) ─────── */
const _idx = {};   // season → { nameKey → entry }
function seasonIndex(season) {
  if (season in _idx) return _idx[season];
  const p = resolve(ROOT, `data/nflverse_stats_${season}.json`);
  if (!existsSync(p)) { _idx[season] = null; return null; }
  const data = JSON.parse(readFileSync(p, 'utf8'));
  const idx = {};
  for (const nm in data) {
    const k = nkey(nm), e = data[nm];
    if (!idx[k] || (e.weeks?.length || 0) > (idx[k].weeks?.length || 0)) idx[k] = e;
  }
  _idx[season] = idx;
  return idx;
}
function weeksFor(name) {
  const key = nkey(name); let weeks = [];
  for (const s of SEASONS) {
    const idx = seasonIndex(s);
    const p = idx && idx[key];
    if (p && p.weeks) weeks = weeks.concat(p.weeks.slice().sort((a, b) => (a.wk || 0) - (b.wk || 0)));
  }
  return weeks;
}

/* ── projection + probability (mirror prop-model.js exactly) ───────────── */
function wmean(vals, halfLife) {
  const n = vals.length; if (!n) return [null, 0];
  let acc = 0, sw = 0;
  for (let i = 0; i < n; i++) { const w = Math.pow(0.5, ((n - 1) - i) / halfLife); acc += w * vals[i]; sw += w; }
  return [sw ? acc / sw : null, sw];
}
function shrink(vals, prior, halfLife, k) {
  const [wm, sw] = wmean(vals, halfLife); if (wm == null) return prior;
  return (sw * wm + k * prior) / (sw + k);
}
function series(weeks, field) { const o = []; for (const w of weeks) { const v = num(w[field]); if (v != null) o.push(v); } return o; }
function sumSeries(weeks, fields) {
  const o = [];
  for (const w of weeks) { const vals = fields.map(f => num(w[f])); if (vals.every(v => v == null)) continue; o.push(vals.reduce((a, v) => a + (v || 0), 0)); }
  return o;
}
function marketKeyOf(m) { const k = Object.keys(m.prior)[0] || ''; return k.includes('|') ? k.split('|')[0] : k; }
// ── role anchor (mirror prop-model.js roleShift + projectFrom's role arg) ────
// A player's history reflects the role he HELD; his current depth rank may be a
// different role. Read which role his own volume resembles (nearest prior), then
// scale by prior[currentRank]/prior[impliedRank], dampened by the fitted w and
// capped. null when history already matches the role, the rank is unknown, or the
// prior/weight for this stat×pos isn't published. This is the SAME anchor the
// Edge Board applies — adopting it here (in place of the old workbook blend) is
// what stops the hero and the board disagreeing on a role-changed player, e.g. a
// rookie RB1 still carrying his committee-back reception history.
let _roleParams;
function loadRoleParams() {
  if (_roleParams === undefined) {
    try { _roleParams = JSON.parse(readFileSync(resolve(ROOT, 'data/role_volume.json'), 'utf8')); }
    catch { _roleParams = null; }
  }
  return _roleParams;
}
function roleShift(rp, stat, pos, rank, level) {
  if (!rp || !rp.priors || rank == null || level == null || pos == null) return null;
  const ranks = rp.priors[stat] && rp.priors[stat][pos];
  const wobj = rp.weights && rp.weights[stat + '|' + pos];
  if (!ranks || !wobj) return null;
  const cur = num(ranks[String(rank)]); if (cur == null) return null;
  let impVal = null, best = Infinity;
  for (const r in ranks) { const d = Math.abs(ranks[r] - level); if (d < best) { best = d; impVal = ranks[r]; } }
  if (impVal == null || impVal <= 0) return null;
  const w = num(wobj.w); if (w == null) return null;
  const clampV = (rp.meta && num(rp.meta.clamp)) || 3;
  return Math.max(1 / clampV, Math.min(clampV, 1 + w * (cur / impVal - 1)));
}
// role = { params, pos, rank } (optional). When present, VOLUME is anchored toward
// the player's current role; the applied multiplier is written to role.mult for
// provenance. TD/poisson markets are left alone (goal-line scoring doesn't track
// volume rank), matching prop-model.js.
function projectFrom(weeks, m, minPrior, role) {
  const anchor = (stat, level) => {
    if (!role || m.kind === 'poisson') return level;
    const mult = roleShift(role.params, stat, role.pos, role.rank, level);
    if (mult != null) { role.mult = mult; return level * mult; }
    return level;
  };
  if (!(m.vol && m.eff_num) && (m.kind === 'count' || m.kind === 'poisson')) {
    const s = m.stat_sum ? sumSeries(weeks, m.stat_sum) : series(weeks, m.stat);
    if (s.length < minPrior) return null;
    return anchor(m.stat, shrink(s, m.prior[Object.keys(m.prior)[0]], m.half_life, m.k_vol));
  }
  const vs = [], es = [];
  for (const w of weeks) { const vol = num(w[m.vol]), en = num(w[m.eff_num]); if (vol != null) vs.push(vol); if (vol && vol > 0 && en != null) es.push(en / vol); }
  if (vs.length < minPrior || es.length < minPrior) return null;
  const mkt = marketKeyOf(m);
  const pv = anchor(m.vol, shrink(vs, m.prior[mkt + '|vol'], m.half_life, m.k_vol));
  const pe = shrink(es, m.prior[mkt + '|eff'], m.half_life, m.k_eff);
  return pv * pe;
}
function erf(x) { const s = x < 0 ? -1 : 1; x = Math.abs(x); const t = 1 / (1 + 0.3275911 * x); const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x); return s * y; }
const normCdf = z => 0.5 * (1 + erf(z / Math.SQRT2));
const sdAt = (m, proj) => Math.sqrt(Math.max(m.sd_v0 + m.sd_v1 * Math.max(proj, 0), 1e-6));
function rawOver(proj, sd, line, count) { const L = count ? line - 0.5 : line; if (sd <= 0) return proj >= L ? 1 : 0; return 1 - normCdf((L - proj) / sd); }
function nbOver(mean, line, r) { if (!(mean > 0) || !(r > 0)) return 0; const m = Math.ceil(line); if (m <= 0) return 1; const p = r / (r + mean); let term = Math.pow(p, r), cdf = term; for (let k = 1; k < m; k++) { term *= (k - 1 + r) / k * (1 - p); cdf += term; } return Math.max(0, 1 - Math.min(cdf, 1)); }
function lognormOver(proj, sd, line) { if (proj <= 0) return 0; if (line <= 0) return 1; const s2 = Math.log(1 + (sd * sd) / (proj * proj)); if (s2 <= 0) return proj > line ? 1 : 0; return 1 - normCdf((Math.log(line) - (Math.log(proj) - s2 / 2)) / Math.sqrt(s2)); }
function poisOver(lam, line) { if (lam <= 0) return 0; const k = Math.floor(line); let term = Math.exp(-lam), acc = term; for (let i = 1; i <= k; i++) { term *= lam / i; acc += term; } return Math.max(0, 1 - Math.min(acc, 1)); }
function shrinkProb(p, w) { if (!w || w === 1) return p; p = clamp(p, 1e-6, 1 - 1e-6); return 1 / (1 + Math.exp(-w * Math.log(p / (1 - p)))); }
function calibrate(calib, p) {
  if (!calib || !calib.length) return p;
  if (p <= calib[0][0]) return calib[0][1];
  if (p >= calib[calib.length - 1][0]) return calib[calib.length - 1][1];
  for (let i = 0; i < calib.length - 1; i++) { const [x0, y0] = calib[i], [x1, y1] = calib[i + 1]; if (p >= x0 && p <= x1) { const t = x1 === x0 ? 0 : (p - x0) / (x1 - x0); return y0 + t * (y1 - y0); } }
  return p;
}
function fairProbOver(PM, name, marketKey, line, role, adj) {
  const m = PM.markets[marketKey]; if (!m) return null;
  const minPrior = (PM.meta && PM.meta.min_prior) || 3;
  const weeks = weeksFor(name); if (!weeks.length) return null;
  // Role-anchored projection — the SAME projection the Edge Board computes. The
  // log projection is backward-looking (a rookie RB1 still carries his committee
  // reception history); the role anchor scales VOLUME toward his current, book-
  // corroborated depth role. This REPLACES the old workbook blend, which the board
  // never used and which was the source of the hero-vs-board disagreement. The
  // anchor is null-gated (fires only for a corroborated rank on a stat with a
  // published prior), so absent a role this is the pure autoregressive log proj.
  const r = role ? { params: role.params, pos: role.pos, rank: role.rank } : null;
  let proj = projectFrom(weeks, m, minPrior, r); if (proj == null) return null;
  const roleMult = r && r.mult != null ? r.mult : null;
  const logProj = roleMult ? proj / roleMult : proj;   // pre-anchor level, for provenance
  // Fold in the matchup context the board already applies — opponent × environment
  // × game-script. scriptMult scales the VOLUME term only (proj = vol×eff), never
  // efficiency. All three are null-safe (×1) so a cold model changes nothing.
  if (adj) proj *= (num(adj.oppMult) ?? 1) * (num(adj.envMult) ?? 1) * (num(adj.scriptMult) ?? 1);
  const dist = m.dist || (m.kind === 'poisson' ? 'poisson' : 'normal');
  const count = m.kind === 'count';
  const sd = dist === 'poisson' ? Math.sqrt(Math.max(proj, 0))
           : dist === 'nbinom' ? Math.sqrt(Math.max(proj, 0) + proj * proj / (m.nb_r || 1e6))
           : sdAt(m, proj);
  const L = num(line); if (L == null) return null;
  const raw = dist === 'poisson' ? poisOver(proj, L)
            : dist === 'nbinom' ? nbOver(proj, L, m.nb_r)
            : dist === 'lognormal' ? lognormOver(proj, sd, L)
            : rawOver(proj, sd, L, count);
  const cal = clamp(shrinkProb(clamp(calibrate(m.calib, raw), 0.01, 0.99), m.shrink), 0.01, 0.99);
  return { proj: round(proj, 2), logProj: round(logProj, 2), roleMult: roleMult ? round(roleMult, 2) : null, over: round(cal, 4), under: round(1 - cal, 4), games: weeks.length };
}

/* ── grade / trust / pricing (mirror index.html) ───────────────────────── */
function vaultGrade(over, under, n) {
  if (over == null || under == null) return null;
  const p = Math.max(over, under), side = over >= under ? 'over' : 'under';
  const K = 6, g = n || 0, padj = 0.5 + (p - 0.5) * (g / (g + K));
  return { side, p, padj, n: g };
}
const gradeLetter = (padj, be) => { const mrg = padj - be; return mrg >= 0.05 ? 'A' : mrg >= 0.03 ? 'B' : mrg >= 0.01 ? 'C' : mrg >= -0.02 ? 'D' : 'F'; };
function lineTrust(quotes, line) {
  const seen = new Map();
  for (const q of (quotes || [])) if (q && q.book && q.line != null && !seen.has(q.book)) seen.set(q.book, q.line);
  const books = seen.size; if (books < 2) return { books, corrob: false };
  const lines = [...seen.values()]; const spread = Math.max(...lines) - Math.min(...lines);
  const tol = Math.max(1.5, 0.06 * Math.abs(line || 0));
  return { books, corrob: spread <= tol, spread };
}
function bestSide(quotes, side) {
  const better = side === 'over' ? (a, b) => a < b : (a, b) => a > b;
  return quotes.reduce((best, q) => {
    if (q[side] == null) return best;
    const cand = { book: q.book, price: q[side], line: q.line ?? null };
    if (!best) return cand;
    if (cand.line != null && best.line != null && cand.line !== best.line) return better(cand.line, best.line) ? cand : best;
    return cand.price > best.price ? cand : best;
  }, null);
}
const americanToProb = p => p == null ? null : (p < 0 ? (-p) / (-p + 100) : 100 / (p + 100));
// EV per $1 for a win probability at an American price (payout side only).
function evPerDollar(winProb, american) {
  if (winProb == null || american == null) return null;
  const payout = american > 0 ? american / 100 : 100 / (-american);
  return round(winProb * payout - (1 - winProb), 4);
}

const MKT_LABEL = {
  pass_yd: 'Pass Yds', pass_att: 'Pass Att', pass_cmp: 'Completions', pass_td: 'Pass TD',
  rush_yd: 'Rush Yds', rush_att: 'Rush Att', rec: 'Receptions', rec_yd: 'Rec Yds', rec_td: 'Rec TD',
};

/* ── role corroboration (mirror index.html roleCorroborated) ─────────────────
   A depth_chart_order is listing ORDER, not opportunity — a nominal WR3 can be
   the de-facto WR1 (Golden). The frontend anchor only trusts a depth rank the
   BOOKS agree with: rank each team's players at a position by their own volume-
   market line, and mark a player corroborated only when the feed depth rank
   matches that line rank. Where they DISAGREE, the projection is resting on the
   player's own (possibly stale) history, so a confident under/over there is a
   likely role phantom — we cap its grade below B so it can't become a best bet.
   Returns a Set of corroborated player ids. */
const ROLE_VOL_MK = { RB: 'rush_yd', WR: 'rec_yd', TE: 'rec_yd' };   // QB excluded
const ROLE_PROJREL = 0.20;   // |proj − line| / line that makes an unconfirmed role suspect
function roleCorrobSet(feed) {
  const props = feed.vegas_player_props || {}, depth = feed.vegas_depth || {};
  const byTeam = {};
  for (const id in props) {
    const p = props[id], mk = ROLE_VOL_MK[p.pos];
    if (!mk || !p.team) continue;
    const cell = (p.lines || {})[mk];
    const line = cell && cell.line != null ? num(cell.line) : null;
    if (line == null) continue;
    const dep = depth[id], dr = dep ? dep[0] : null;
    if (dr == null) continue;
    (byTeam[p.team + '|' + p.pos] = byTeam[p.team + '|' + p.pos] || []).push({ id, line, dr });
  }
  const ok = new Set();
  for (const k in byTeam) byTeam[k].sort((a, b) => b.line - a.line).forEach((x, i) => { if (x.dr === i + 1) ok.add(String(x.id)); });
  return ok;
}

/* ── sharp anchor (Kalshi player props) ──────────────────────────────────
   The exchange fair for a player/market/line, or null when we shouldn't trust
   it. Kalshi stores yes = P(value > floor_strike), so a strike that equals the
   book line is the same over/under question. We return the exchange fair for
   the OVER, plus its liquidity, and only when a strike matches AND the market
   clears the OI + spread bars — otherwise null (no gate). Mirrors the trade
   engines' "return null until the data lands", never a fake 0. */
function loadKalshiProps() {
  try {
    const kp = JSON.parse(readFileSync(KPROPS, 'utf8'));
    return kp && kp.markets ? kp : null;
  } catch (e) { return null; }   // cold/missing file → anchor no-ops
}
function sharpFairFor(KP, name, mk, line) {
  if (!KP) return null;
  const ladder = (KP.markets[mk] || {})[nkey(name)];
  if (!ladder || !ladder.length || line == null) return null;
  let best = null;
  for (const r of ladder) {
    const d = Math.abs(r.k - line);
    if (d > SHARP_STRIKE_TOL) continue;
    if (r.oi < SHARP_MIN_OI || r.spr > SHARP_MAX_SPREAD) continue;   // liquid strikes only
    if (!best || d < best.d) best = { d, over: r.fair, oi: r.oi, spr: r.spr };
  }
  return best ? { over: best.over, oi: best.oi, spr: best.spr } : null;
}

/* ── score every prop ──────────────────────────────────────────────────── */
function scoreProps(feed, PM, KP) {
  const props = feed.vegas_player_props || {};
  const cands = [];
  let scored = 0, gated = 0, preskip = 0;
  // Preseason gate (mirror the board's propRows): exhibition-game props price a
  // starter's cameo or a backup's heavy workload, so they're apples-to-oranges
  // with a regular-season projection. In preseason keep only real regular-season
  // lines (kickoff on/after Sep 1); in-season this drops nothing.
  const isPre = /^pre/i.test(feed.season_type || '');
  const yr = Number(feed.season) || new Date().getUTCFullYear();
  const regCutoff = Date.UTC(yr, 8, 1);   // Sep 1
  // Starter gate: a backup who won't see the field is never a best bet, however
  // good his historical projection looks (a QB2's pass line, a 4th RB's carries).
  // depth_chart_order 1 = starter; the per-position ceiling keeps genuine
  // committee/rotation players (RB2, WR3) while cutting deep backups.
  const depth = feed.vegas_depth || {};
  const DEPTH_MAX = { QB: 1, RB: 2, WR: 3, TE: 2 };
  // Role-corroboration guard (mirror the board's edgeCaution role tier): a
  // volume-market player whose depth rank the market contradicts is projected
  // off his own, possibly stale, history — a confident under/over there is a
  // likely role phantom (the Golden case), so it must never become a best bet.
  const roleOk = roleCorrobSet(feed);
  const roleParams = loadRoleParams();   // role_volume.json — the board's volume anchor
  const ctx = buildMatchupCtx(feed);   // opponent + environment + game-script, per prop
  let benchskip = 0, roleskip = 0, projskip = 0, dfsskip = 0, countskip = 0, sharpskip = 0, rechold = 0;
  // Early-season rec-under hold fires only while the log window is essentially
  // last season only (weeks <= cutoff). feed.week is the served slate week.
  const _feedWeek = Number(feed.week) || 99;
  const _earlyRec = EARLY_REC_HOLD_WEEKS > 0 && _feedWeek <= EARLY_REC_HOLD_WEEKS;
  for (const id in props) {
    const p = props[id];
    if (isPre && p.commence) { const t = new Date(p.commence).getTime(); if (Number.isFinite(t) && t < regCutoff) { preskip++; continue; } }
    const dep = depth[id];   // [depth_chart_order, active]
    if (dep) {
      if (dep[1] === 0) { benchskip++; continue; }                                 // inactive / out
      const cap = DEPTH_MAX[p.pos];
      if (cap != null && dep[0] != null && dep[0] > cap) { benchskip++; continue; } // buried on the depth chart
    }
    for (const mk in (p.lines || {})) {
      if (!PM.markets[mk]) continue;                       // modeled markets only
      const cell = p.lines[mk];
      // Only quotes that actually PRICE a side define a bettable line. A pick'em
      // placeholder (e.g. PrizePicks Pass TD "1" with null over/under) must never
      // set the line we score — pairing its whole-number line with a half-point
      // plus-price from another book invented the phantom "Under 1" edges.
      const priced = (cell.quotes || []).filter(q => q && q.line != null && (q.over != null || q.under != null));
      if (priced.length < 2) continue;                     // need ≥2 priced books to even consider
      // Role anchor input (mirror the board's verifiedRoleRank): the feed depth
      // rank, but ONLY when the books corroborate it. Trusting listing order alone
      // would anchor a full-snap slot receiver toward a backup prior — the exact
      // phantom the anchor exists to kill. Absent a corroborated rank the anchor
      // no-ops and the projection is the pure log model (then the roleUnconfirmed
      // and count-under guards below catch a confident off-role bet).
      const roleRank = (dep && dep[0] != null && roleOk.has(String(id))) ? dep[0] : null;
      const role = (roleParams && roleRank != null && p.pos) ? { params: roleParams, pos: p.pos, rank: roleRank } : null;
      // Score EACH distinct priced line on its own so the probability and the
      // price we pair always share the same line. The per-player dedup below
      // keeps only the best line if a market quotes several.
      const byLine = new Map();
      for (const q of priced) { const L = num(q.line); if (L == null) continue; if (!byLine.has(L)) byLine.set(L, []); byLine.get(L).push(q); }
      for (const [line, lq] of byLine) {
        if (lq.length < 2) continue;                       // need ≥2 books AT this exact line
        const v = fairProbOver(PM, p.name, mk, line, role, matchupAdjFor(ctx, p, mk));
        if (!v || v.games < MIN_GAMES) continue;
        scored++;
        const g = vaultGrade(v.over, v.under, v.games);
        const side = g.side;
        const sideProb = side === 'under' ? v.under : v.over;
        const bs = bestSide(lq, side);                     // best price for this side AT this line
        if (!bs || bs.price == null) continue;
        const trust = lineTrust(lq, line);
        // honest gates: corroborated line, confidence clears the bar, real +EV
        const ev = evPerDollar(g.padj, bs.price);          // confidence-adjusted EV vs best price
        const letter = gradeLetter(g.padj, BE_REF);
        const bettable = bs.price >= PRICE_MIN && bs.price <= PRICE_MAX; // no chalk, no lottery tickets
        // Role-unconfirmed phantom: market contradicts the depth chart AND the
        // projection sits far off this line → demote below B so it can't pass.
        const roleUnconfirmed = !!ROLE_VOL_MK[p.pos] && !roleOk.has(String(id))
          && v.proj != null && Math.abs(v.proj - line) / Math.abs(line) >= ROLE_PROJREL;
        // Gate 3: sharp-anchor disagreement. Compare our side's confidence-
        // adjusted prob to the exchange's fair for the same side; a liquid,
        // strike-matched market that disagrees by ≥SHARP_GAP caps the grade.
        const sharp = sharpFairFor(KP, p.name, mk, line);   // {over,oi,spr} or null
        const sharpSide = sharp ? (side === 'over' ? sharp.over : 1 - sharp.over) : null;
        const sharpGap = sharpSide != null ? round(g.padj - sharpSide, 3) : null;   // + = we're higher than sharp
        const sharpDisagree = sharpSide != null && Math.abs(g.padj - sharpSide) >= SHARP_GAP;
        const eff = (roleUnconfirmed || sharpDisagree) ? 'C' : letter;
        // Gate 1: projection strays too far from this corroborated line → stale/context, not edge.
        const projGap = v.proj != null && Math.abs(line) > 0 ? Math.abs(v.proj - line) / Math.abs(line) : 0;
        const projBlowout = VOL_MK.has(mk) && projGap >= MAX_PROJ_GAP;
        // Absolute-count guard (see COUNT_MK above): kill an Under on a low count
        // line when the pick contradicts the market's own direction — the phantom
        // regime where our backward-looking log model fades a small counting stat
        // the market (and the player's current role) expects him to clear. Two
        // robust tells, either one is enough: (a) a plus-money Under means the book
        // itself favors the Over; (b) the projection sits half-a-count-plus below
        // the line. Both are checked because a raw price sign can be near-even
        // (Under -105 vs Over -115). Only the Under side needs this — an Over
        // phantom sits far ABOVE a small line and already trips the ratio gate.
        const countUnderPhantom = COUNT_MK.has(mk) && line > 0 && line <= LOW_COUNT_LINE
          && side === 'under'
          && ((bs.price != null && bs.price > 0) || (v.proj != null && v.proj <= line - ABS_COUNT_GAP));
        // Gate 2: at least one true sportsbook must price this exact line (not DFS-only).
        const realBookAtLine = lq.some(q => isRealBook(q.book));
        // Gate 4: hold rec-count unders in the early season (see EARLY_REC_HOLD_WEEKS).
        const earlyRecHold = _earlyRec && mk === 'rec' && side === 'under';
        const wouldPass = trust.corrob && (letter === 'A' || letter === 'B') && ev != null && ev > 0 && bettable;
        const preGate = trust.corrob && (eff === 'A' || eff === 'B') && ev != null && ev > 0 && bettable;
        const pass = preGate && !projBlowout && !countUnderPhantom && !earlyRecHold && realBookAtLine;
        if (!pass) {
          if (roleUnconfirmed && wouldPass) roleskip++;
          else if (sharpDisagree && wouldPass) sharpskip++;
          else if (earlyRecHold && wouldPass) rechold++;
          else if (preGate && projBlowout) projskip++;
          else if (preGate && countUnderPhantom) countskip++;
          else if (preGate && !realBookAtLine) dfsskip++;
          else gated++;
          continue;
        }
        cands.push({
          id, name: p.name, team: p.team || null, pos: p.pos || null, opp: p.opp || null,
          market: mk, marketLabel: MKT_LABEL[mk] || mk, line, side,
          book: bs.book, price: bs.price,
          ev: round(ev * 100, 1),                          // % EV per $1 at best price
          proj: v.proj, logProj: v.logProj, roleMult: v.roleMult, // anchored / pre-anchor / role multiplier
          prob: round(g.padj, 3), rawProb: round(sideProb, 3),
          grade: eff, books: trust.books, games: v.games,
          // sharp anchor (null when no liquid strike-matched exchange market):
          // the exchange fair for this side, our gap to it, and its liquidity,
          // so the Edge Board can show "sharp says X" next to the Vault grade.
          sharpFair: sharpSide != null ? round(sharpSide, 3) : null,
          sharpGap, sharpOi: sharp ? sharp.oi : null,
        });
      }
    }
  }
  // Rank by confidence-adjusted EV — the real value. The price band (above)
  // already strips both -300 chalk (trivial certainties) and lottery longshots
  // (the plus-money tickets that leaned on the model's overfit TD tail), so
  // what's left is genuine value on bettable lines. Confidence breaks ties.
  cands.sort((a, b) => b.ev - a.ev || b.prob - a.prob);
  // One bet per player in the headline list — a "top 3" should be three names,
  // not one player's whole card. (Full ranked pool is still counted.)
  const seenPlayer = new Set(), list = [];
  for (const c of cands) { if (seenPlayer.has(c.id)) continue; seenPlayer.add(c.id); list.push(c); if (list.length >= TOP) break; }
  return { list, scored, gated, preskip, benchskip, roleskip, projskip, dfsskip, countskip, sharpskip, rechold, total: cands.length };
}

/* ── game leans (CONTEXT only; empty while the model is gated) ──────────── */
function gameLeans(feed) {
  let gm = null;
  try { gm = JSON.parse(readFileSync(resolve(ROOT, 'data/game_model.json'), 'utf8')); } catch (e) { return { list: [], gated: 'no-model' }; }
  // The game model matches but does not beat the market, and gates itself off
  // in the offseason — honor that. Leans light up in-season.
  if (gm.offseason) return { list: [], gated: 'offseason' };
  const teams = gm.teams || {}, hfa = num(gm.hfa) || 0, base = num(gm.base_pts) || 22.5;
  const out = [];
  for (const g of (feed.vegas_games || [])) {
    const H = teams[g.home], A = teams[g.away]; if (!H || !A) continue;
    const projMargin = (num(H.rate) - num(A.rate)) + hfa;            // home minus away
    const projTotal = 2 * base + num(H.off) + num(A.off) + num(H.def) + num(A.def);
    const mktSpreadHome = g.spread && g.spread.cons ? num(g.spread.cons.home) : null;   // home line (neg = favored)
    const mktTotal = g.total ? num(g.total.cons) : null;
    // spread lean: model's home margin vs the market's implied home margin (−spread)
    if (mktSpreadHome != null) {
      const edge = projMargin - (-mktSpreadHome);
      if (Math.abs(edge) >= 1.0) out.push({ type: 'spread', game: `${g.away} @ ${g.home}`, side: edge > 0 ? g.home : g.away, lean: round(Math.abs(edge), 1), market_line: mktSpreadHome, model_margin: round(projMargin, 1), commence: g.commence || null });
    }
    if (mktTotal != null) {
      const edge = projTotal - mktTotal;
      if (Math.abs(edge) >= 1.5) out.push({ type: 'total', game: `${g.away} @ ${g.home}`, side: edge > 0 ? 'Over' : 'Under', lean: round(Math.abs(edge), 1), market_line: mktTotal, model_total: round(projTotal, 1), commence: g.commence || null });
    }
  }
  out.sort((a, b) => b.lean - a.lean);
  return { list: out.slice(0, LEANS), gated: null };
}

/* ── main ──────────────────────────────────────────────────────────────── */
(async () => {
  try {
    if (!existsSync(FEED)) { log('feed not found:', FEED); process.exit(0); }
    const feed = JSON.parse(readFileSync(FEED, 'utf8'));
    // Roll the game-log window to the feed's season: [cur-1, cur]. seasonIndex
    // no-ops for any season whose nflverse_stats_<yr>.json isn't published yet,
    // so pre-Week-1 this still reads only last season — same behaviour as before,
    // but the hero starts blending in current-season form the moment logs land.
    { const cur = Number(feed.season); if (cur >= 2024) SEASONS = [cur - 1, cur]; }
    const PM = JSON.parse(readFileSync(resolve(ROOT, 'data/prop_model.json'), 'utf8'));
    if (!PM.markets) { log('prop_model.json has no markets — skipping'); process.exit(0); }

    const KP = loadKalshiProps();   // sharp anchor — null-safe, no-ops if the file isn't there yet
    log(KP ? `sharp anchor: kalshi_props.json (${KP.count} markets)` : 'sharp anchor: none (kalshi_props.json missing) — agreement gate off');
    const props = scoreProps(feed, PM, KP);
    const leans = gameLeans(feed);
    log(`props: ${props.total} qualified of ${props.scored} scored (${props.gated} gated, ${props.benchskip} benched, ${props.roleskip} role-unconfirmed, ${props.sharpskip} sharp-disagree, ${props.rechold} early-rec-hold, ${props.projskip} proj-blowout, ${props.countskip} count-under-phantom, ${props.dfsskip} dfs-only) → top ${props.list.length}`);
    log(`game leans: ${leans.gated ? leans.gated : props.total >= 0 ? leans.list.length : 0}${leans.gated ? ' (empty)' : ''}`);
    for (const b of props.list) log(`  • ${b.name} ${b.marketLabel} ${b.side.toUpperCase()} ${b.line} @ ${b.book} ${b.price > 0 ? '+' : ''}${b.price} — ${b.grade}, ${b.ev}% EV, ${b.books} books, ${b.games}g${b.sharpFair != null ? `, sharp ${(b.sharpFair * 100).toFixed(0)}% (gap ${b.sharpGap > 0 ? '+' : ''}${(b.sharpGap * 100).toFixed(0)}pt)` : ''}`);

    feed.best_bets = {
      generated: new Date().toISOString(),
      season: feed.season || null, week: feed.week || null,
      be_ref: BE_REF,
      props: props.list,
      game_leans: leans.list,
      game_leans_note: leans.gated === 'offseason'
        ? 'Game leans light up in-season — the game model is context, not an edge, and is gated off in the offseason.'
        : 'Game leans are model context, not an edge — the game model matches the market without beating it.',
      note: 'Top props by confidence-adjusted EV on corroborated lines (≥2 books), modeled markets only.',
    };
    if (DRY) { log('DRY — not writing'); return; }
    writeFileSync(FEED, JSON.stringify(feed));
    log('wrote best_bets to', FEED);
  } catch (e) {
    log('ERROR:', e.message);
    process.exit(0);   // never fail the workflow
  }
})();
