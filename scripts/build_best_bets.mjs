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
   card:[…], game_leans:[…], note }, and appends newly posted plays to the
   locked weekly card, data/best_bets_card.json. Run AFTER the props fetch so it scores fresh lines.

   Run:  node scripts/build_best_bets.mjs                 # score, write feed
         node scripts/build_best_bets.mjs --dry           # score, print, no write
         node scripts/build_best_bets.mjs --top=3         # how many props (default 3)
         node scripts/build_best_bets.mjs --cardmax=10    # locked weekly card size (default 10)
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
// --dump=path: also write EVERY scored prop line (pass or the gate that stopped
// it) for this week and next, for the Game Breakdowns page. Implies --dry.
const DUMP  = ARG.dump || null;
const TOP   = Number(ARG.top || 4);
const LEANS = Number(ARG.leans || 3);
const FEED  = ARG.feed || resolve(ROOT, 'data/lineup-feed.json');
const KPROPS = ARG.kprops || resolve(ROOT, 'data/kalshi_props.json');
// Pick'em pairs (model-upgrade plan Week 4). Same-game legs are correlated
// (data/prop_correlations.json, scripts/build_prop_correlations.py): QB pass
// yds and his WR1 rec yds move together (rho ~0.42), so both-over hits more
// often than p1*p2. Validated: held-out 2025 predicted 25.2% vs 24.6% actual
// both-over (independent said 18.6%); 2026 real lines 31.0% vs 33.8% (25.0%).
// At SPORTSBOOK lines a pair almost never clears a 3x 2-pick payout (1 of 133
// in Wks 1-3), so a pair only surfaces where the pick'em app's line is softer
// than the books': each leg = the books' no-vig P at their line, shifted to the
// app's line by Vault's model shape. Logged pre-kickoff and graded in
// settle_bets.py so pairs earn a record of their own.
const CORR_FILE = ARG.corr || resolve(ROOT, 'data/prop_correlations.json');
const PAIRS_LOG = ARG.pairslog || resolve(ROOT, 'data/pickem_pairs_log.json');
const PAIR_PAYOUT = 3;               // standard 2-pick payout; break-even 1/3
const PAIR_MIN_EV = Number(ARG.pairminev ?? 0.05);   // joint * payout - 1 (--pairminev=-1 lists every pair, for testing)
const PAIR_TOP = 3;
const PAIR_APPS = ['PrizePicks', 'Underdog Fantasy', 'Underdog', 'Sleeper'];
let   SEASONS = [2024, 2025];                 // log window [prev, cur] — reset from feed.season in main() so it rolls to [cur-1, cur] once the new season's nflverse logs land (mirrors the client's ebVaultSeasons)
const BE_REF = 0.524;                         // standard -110 book break-even (entry-agnostic bar)
const MIN_GAMES = 8;                          // enough log to trust the projection
const PRICE_MIN = -250, PRICE_MAX = 200;      // bettable band: no -300 chalk, no lottery longshots
// Locked weekly card. The live top-N rotates as lines move (22-31 different
// plays showed across Weeks 1-3), so a user who looked Thursday and one who
// looked Sunday followed different cards and neither had a record to check.
// A play that reaches the top-N is written to the card ONCE, frozen at the line
// and price it posted with, and never removed. Replaying Weeks 1-3 (git history
// of this feed): first 10 plays a week, one per player = 18-7, +12.3u, positive
// every week; 8 = 14-5 and 12 = 20-10 were no better. Append-only; settle_bets.py
// grades it into data/best_bets_record.json (a separate file, so the props job
// and the settle job never write the same file).
const CARD_MAX = Number(ARG.cardmax || 10);
const CARD_FILE = ARG.card || resolve(ROOT, 'data/best_bets_card.json');
// Which play types may go on the card, and the log that decides it. Every play
// that reaches the live top-N is appended to the shadow log (card or not);
// settle_bets.py grades it and writes the rules: a type (market x side x
// WR/TE|RB|QB) switches on after 15+ plays at a +5% return over the last 4
// weeks, and off once it is losing there. Seed until the rules file exists:
// WR/TE rec-yds unders, the only type that won every week of Weeks 1-3
// (28-11, +14.2u); RB rec-yds unders were 2-3 and nothing else had 10 plays.
const SHADOW_FILE = ARG.shadow || resolve(ROOT, 'data/best_bets_shadow.json');
// Withheld props that would have been Best Bets (best_bets_held.json) and the
// Kalshi-vs-books-vs-Vault read on every Kalshi-priced line (signal_log.json).
// Both are graded, never shown as plays: see logHeld / logSignals.
const HELD_FILE = resolve(ROOT, 'data/best_bets_held.json');
// STRICT TIER (shadow only, 2026-10-05): Vault's own P(side) AND the real books'
// no-vig P(side) both clear a bar, on a market with a measured signal. Backtest on
// 2024-25 ESPN BET closes (scripts/backtest_strict_tier.py, docs/strict-tier-backtest.md):
// ~71% hit, but 2025 alone was 67% at +1% ROI, so it is LOGGED and graded here, never
// shown as a play, until live results confirm it. Thresholds are the backtest's.
const STRICT_FILE = ARG.strict || resolve(ROOT, 'data/best_bets_strict.json');
const STRICT_MODEL = Number(ARG.strictmodel ?? 0.70), STRICT_MKT = Number(ARG.strictmkt ?? 0.58);   // overrides are for testing only
const SIGNAL_FILE = resolve(ROOT, 'data/signal_log.json');
const RULES_FILE = ARG.rules || resolve(ROOT, 'data/best_bets_rules.json');
const CARD_DEFAULT_ON = ['rec_yd|under|WR/TE'];
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
// Structurally-weak markets: mirror of the board's WEAK_MK (index.html). These
// came in below break-even every settled week of 2026, so the board caps their
// grade at C ("thin edge"); Best Bets needs A/B, so they can't headline here
// either. Keep this list identical to the board's and drop a market from both
// the moment it clears break-even on fresh weeks.
// pass_att joined after the Week 4 retro: the model earns 0 weight against the
// no-vig market on all three QB volume markets (docs/retro/week-4-deep-dive.md).
const WEAK_MK = new Set(['pass_yd', 'pass_cmp', 'pass_int', 'rush_rec_yd', 'pass_att']);
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
  return { dvp, leagueFpa, spreadByTeam, totalByTeam, gs: loadGameScript(), wx: loadWeather() };
}
// Kickoff wind (scripts/fetch-weather.mjs → data/weather.json). Each game carries a
// ready-made multiplier per market (mult.pass_yd), present only when the measured
// wind term is active, the game is outdoors and kickoff is near. Team → its SOONEST
// upcoming game. Absent file / game / market → ×1.
function loadWeather() {
  let wx; try { wx = JSON.parse(readFileSync(resolve(ROOT, 'data/weather.json'), 'utf8')); } catch (e) { return {}; }
  const byTeam = {}, al = t => ({ LAR: 'LA', WSH: 'WAS', LVR: 'LV', JAC: 'JAX' }[t] || t);
  for (const g of (wx.games || []).slice().sort((a, b) => Date.parse(a.commence) - Date.parse(b.commence)))
    for (const t of [g.home, g.away]) if (t && !byTeam[al(t)]) byTeam[al(t)] = g;
  return byTeam;
}
function windMultOf(wx, team, mk) {
  if (!wx || !team) return 1;
  const g = wx[({ LAR: 'LA', WSH: 'WAS', LVR: 'LV', JAC: 'JAX' }[team] || team)];
  return num(g && g.mult && g.mult[mk]) ?? 1;
}
function matchupAdjFor(ctx, p, mk) {
  let oppMult = 1, envMult = 1;
  if (p.opp && p.pos) {
    const c = ctx.dvp[p.opp] && ctx.dvp[p.opp][p.pos], avg = ctx.leagueFpa[p.pos];
    // c.mult = fitted damped term (RB/WR/TE, data/dvp_damp.json via the feed);
    // QB carries none and keeps the raw ratio (docs/dvp-damp-backtest.md).
    if (c && num(c.mult) > 0) oppMult = num(c.mult);
    else if (c && c.fpa != null && avg) oppMult = clamp(c.fpa / avg, 0.88, 1.15);
  }
  const spread = p.team != null ? (ctx.spreadByTeam[p.team] ?? null) : null;
  const total = p.team != null ? (ctx.totalByTeam[p.team] ?? null) : null;
  if (total != null && spread != null) envMult = clamp(1 + _ENV_BETA * ((total / 2 - spread / 2) / _ENV_AVG - 1), 0.92, 1.10);
  return { oppMult, envMult, scriptMult: scriptMultOf(ctx.gs, mk, spread), windMult: windMultOf(ctx.wx, p.team, mk) };
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
function gateWeeks(weeks, m) { const g = m.gate; return g ? weeks.filter(w => (num(w[g[0]]) || 0) >= g[1]) : weeks; }  // starter gate: QB history = games with 15+ pass att
function projectFrom(weeks, m, minPrior, role) {
  weeks = gateWeeks(weeks, m);
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
// Zero-inflated log-normal (dist 'hurdle_lognormal', build_prop_projections.py):
// P(records any yards) x P(positive part > line). m.pi0 = [[proj, P(0)], ...].
function pi0At(k, proj) {
  if (!k || !k.length) return 0;
  let v = k[k.length - 1][1];
  if (proj <= k[0][0]) v = k[0][1];
  else for (let i = 1; i < k.length; i++) if (proj <= k[i][0]) { const [x0, y0] = k[i - 1], [x1, y1] = k[i]; v = y0 + (y1 - y0) * (x1 > x0 ? (proj - x0) / (x1 - x0) : 0); break; }
  return Math.min(Math.max(v, 0), 0.9);
}
function hurdleOver(m, proj, line) {
  if (proj <= 0) return 0;
  if (line < 0) return 1;
  const p0 = pi0At(m.pi0, proj), mu = proj / (1 - p0);
  return (1 - p0) * lognormOver(mu, sdAt(m, mu), line);
}
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
  // Fold in the matchup context the board already applies: opponent × environment
  // × game-script. scriptMult scales the VOLUME term only (proj = vol×eff), never
  // efficiency. windMult is the measured kickoff-wind cut (pass_yd). All are null-safe (×1).
  if (adj) proj *= (num(adj.oppMult) ?? 1) * (num(adj.envMult) ?? 1) * (num(adj.scriptMult) ?? 1) * (num(adj.windMult) ?? 1);
  const dist = m.dist || (m.kind === 'poisson' ? 'poisson' : 'normal');
  const count = m.kind === 'count';
  const sd = dist === 'poisson' ? Math.sqrt(Math.max(proj, 0))
           : dist === 'nbinom' ? Math.sqrt(Math.max(proj, 0) + proj * proj / (m.nb_r || 1e6))
           : sdAt(m, proj);
  const L = num(line); if (L == null) return null;
  const raw = dist === 'poisson' ? poisOver(proj, L)
            : dist === 'nbinom' ? nbOver(proj, L, m.nb_r)
            : dist === 'lognormal' ? lognormOver(proj, sd, L)
            : dist === 'hurdle_lognormal' ? hurdleOver(m, proj, L)
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
// Exchange fees — mirror of VaultBettingMath.netAmerican in index.html (keep in
// sync). A fee venue competes on what it PAYS, and the pick banks that net price
// so settlement P/L and the grade's break-even match what the user would get.
const FEE_ON_WIN = { ProphetX: 0.02 };
const KALSHI_TAKER = 0.07;
function netAmerican(book, american) {
  const a = Number(american);
  if (american == null || !Number.isFinite(a) || a === 0) return american;
  const kalshi = String(book || '').toLowerCase() === 'kalshi';
  if (!kalshi && !FEE_ON_WIN[book]) return a;
  const dec = a > 0 ? 1 + a / 100 : 1 + 100 / -a;
  let net;
  if (kalshi) { const P = 1 / dec, cost = P + KALSHI_TAKER * P * (1 - P); if (!(cost > 0 && cost < 1)) return a; net = 1 / cost; }
  else net = 1 + (dec - 1) * (1 - FEE_ON_WIN[book]);
  return Math.round(net >= 2 ? (net - 1) * 100 : -100 / (net - 1));
}
function bestSide(quotes, side) {
  const better = side === 'over' ? (a, b) => a < b : (a, b) => a > b;
  return quotes.reduce((best, q) => {
    if (q[side] == null) return best;
    const cand = { book: q.book, price: netAmerican(q.book, q[side]), line: q.line ?? null };
    if (!best) return cand;
    if (cand.line != null && best.line != null && cand.line !== best.line) return better(cand.line, best.line) ? cand : best;
    return cand.price > best.price ? cand : best;
  }, null);
}
const americanToProb = p => p == null ? null : (p < 0 ? (-p) / (-p + 100) : 100 / (p + 100));
// EV per $1 for a win probability at an American price (payout side only).
// Break-even the price we'd actually take implies (-130 -> 56.5%, +100 -> 50%).
// The grade is scored against it, matching the board's default "Each pick's
// price" mode and settle_bets.py, instead of one flat -110 bar for every price.
function priceBE(american) {
  if (american == null || !Number.isFinite(american)) return BE_REF;
  return american > 0 ? 100 / (american + 100) : -american / (-american + 100);
}
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
// Kalshi prices props on a strike ladder (70+, 80+ yards; 5+, 6+ catches), so a
// book line usually sits BETWEEN two strikes (DeVonta Smith 73.5). Between two
// liquid neighbours, read P(over) on the normal-quantile scale (probit) and
// interpolate. Checked 2026-09-28: estimating each liquid strike from the ones
// two steps away missed Kalshi's own price by ~1 pt (straight-line: 1.2-2.5), and
// on 1,017 settled Wk 1-3 props Kalshi's read at the close line scored as well
// as the books' no-vig price (log-loss .6922 vs .6925; between-strike .6906).
const SHARP_MAX_GAP = { rec: 2, rec_yd: 20, rush_yd: 20, pass_yd: 50, rush_att: 6, pass_att: 10 };
const _probit = p => { p = Math.min(Math.max(p, 1e-3), 1 - 1e-3);   // Acklam inverse normal
  const a = [-39.6968302866538, 220.946098424521, -275.928510446969, 138.357751867269, -30.6647980661472, 2.50662827745924];
  const b = [-54.4760987982241, 161.585836858041, -155.698979859887, 66.8013118877197, -13.2806815528857];
  const c = [-0.00778489400243029, -0.322396458041136, -2.40075827716184, -2.54973253934373, 4.37466414146497, 2.93816398269878];
  const d = [0.00778469570904146, 0.32246712907004, 2.445134137143, 3.75440866190742];
  if (p < 0.02425) { const q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  if (p > 0.97575) { const q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  const q = p - 0.5, r = q * q;
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1); };
const _ncdf = z => { const t = 1 / (1 + 0.2316419 * Math.abs(z)); const dd = 0.3989423 * Math.exp(-z * z / 2); const p = dd * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))); return z > 0 ? 1 - p : p; };
function sharpFairFor(KP, name, mk, line) {
  if (!KP) return null;
  const ladder = (KP.markets[mk] || {})[nkey(name)];
  if (!ladder || !ladder.length || line == null) return null;
  const liq = ladder.filter(r => r.oi >= SHARP_MIN_OI && r.spr <= SHARP_MAX_SPREAD).sort((x, y) => x.k - y.k);   // liquid strikes only
  let best = null;
  for (const r of liq) {
    const d = Math.abs(r.k - line);
    if (d <= SHARP_STRIKE_TOL && (!best || d < best.d)) best = { d, over: r.fair, oi: r.oi, spr: r.spr };
  }
  if (best) return { over: best.over, oi: best.oi, spr: best.spr };
  const lo = liq.filter(r => r.k < line).pop(), hi = liq.find(r => r.k > line);
  if (!lo || !hi || hi.k - lo.k > (SHARP_MAX_GAP[mk] || 20)) return null;
  const t = (line - lo.k) / (hi.k - lo.k);
  const over = _ncdf(_probit(lo.fair) + t * (_probit(hi.fair) - _probit(lo.fair)));
  return { over: Math.round(over * 1000) / 1000, oi: Math.min(lo.oi, hi.oi), spr: Math.max(lo.spr, hi.spr), interp: [lo.k, hi.k] };
}

/* ── score every prop ──────────────────────────────────────────────────── */
function scoreProps(feed, PM, KP) {
  const props = feed.vegas_player_props || {};
  const cands = [], dump = [];
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
  // Slate gate: the props feed merges cells and never subtracts, so a player's
  // entry from an already-played week survives into the next one (Rice "vs IND"
  // headlining Week 3 off his Week 2 lines). In-season, a prop only counts when
  // its team+opp is an unstarted game on the served week's board.
  const inSeason = /^(reg|post)/i.test(feed.season_type || '');
  const now = Date.now(), feedWeek = Number(feed.week) || null;
  const slateKick = {};
  for (const g of (feed.vegas_games || [])) {
    if (!g || !g.home || !g.away || !g.commence) continue;
    const wkOk = DUMP ? (Number(g.week) === feedWeek || Number(g.week) === feedWeek + 1) : Number(g.week) === feedWeek;
    if (feedWeek != null && g.week != null && !wkOk) continue;
    slateKick[[g.home, g.away].sort().join('|')] = g.commence;
  }
  const onSlate = p => {
    if (!p.team || !p.opp) return false;
    const kick = slateKick[[p.team, p.opp].sort().join('|')];
    const t = kick ? Date.parse(kick) : NaN;
    return Number.isFinite(t) && t > now;
  };
  let offslate = 0;
  // Role-corroboration guard (mirror the board's edgeCaution role tier): a
  // volume-market player whose depth rank the market contradicts is projected
  // off his own, possibly stale, history — a confident under/over there is a
  // likely role phantom (the Golden case), so it must never become a best bet.
  const roleOk = roleCorrobSet(feed);
  const roleParams = loadRoleParams();   // role_volume.json — the board's volume anchor
  const ctx = buildMatchupCtx(feed);   // opponent + environment + game-script, per prop
  let benchskip = 0, roleskip = 0, projskip = 0, dfsskip = 0, countskip = 0, sharpskip = 0, weakskip = 0, rechold = 0;
  const heldCands = [], signals = [], heldIds = {}, strictCands = [];
  // Players whose role the books contradict on ANY volume market. The check
  // above is per line, so one market could slip under ROLE_PROJREL while his
  // others tripped it (Warren wk 4 2026: rush yds + receptions flagged "role",
  // rec yds 17.6% off the line made Best Bets). One bad role read voids all.
  const roleBad = new Set();
  // Early-season rec-under hold fires only while the log window is essentially
  // last season only (weeks <= cutoff). feed.week is the served slate week.
  const _feedWeek = Number(feed.week) || 99;
  const _earlyRec = EARLY_REC_HOLD_WEEKS > 0 && _feedWeek <= EARLY_REC_HOLD_WEEKS;
  for (const id in props) {
    const p = props[id];
    if (isPre && p.commence) { const t = new Date(p.commence).getTime(); if (Number.isFinite(t) && t < regCutoff) { preskip++; continue; } }
    if (inSeason && !onSlate(p)) { offslate++; continue; }
    // Gameday health (set by fetch-pickem-props from the live Sleeper inactive
    // feed): p.out = ruled out / doubtful → props void; p.impacted = teammate of
    // an OUT starter (QB1/RB1/WR1) whose projection assumes a lineup that just
    // changed. Never let either become a best bet — the projection is stale.
    if (p.out) { benchskip++; if (DUMP) dump.push({ id, name: p.name, team: p.team, pos: p.pos, opp: p.opp, status: 'out' }); continue; }
    // Withheld (teammate of an OUT starter): still never a best bet, but it is
    // SCORED so the plays it would have made land in the held log
    // (best_bets_held.json), and settlement can tell us whether withholding
    // backup-QB games is costing anything (PHI@CHI: the Bears' overs all hit).
    const held = p.impacted ? (p.impactedBy || 'lineup change') : null;
    if (held) { roleskip++; heldIds[id] = held; if (DUMP) dump.push({ id, name: p.name, team: p.team, pos: p.pos, opp: p.opp, status: 'withheld', why: held }); }
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
        // Backup RB out (fetch-pickem-props p.backupOut): the lead back now has
        // the whole backfield, so a volume UNDER off his committee history is
        // the phantom; hold it like a withheld prop. Overs still score.
        const lineHeld = held || (p.backupOut && side === 'under' && VOL_MK.has(mk) ? p.backupOut : null);
        if (lineHeld && !held) heldIds[id] = lineHeld;
        const trust = lineTrust(lq, line);
        // honest gates: corroborated line, confidence clears the bar, real +EV
        const ev = evPerDollar(g.padj, bs.price);          // confidence-adjusted EV vs best price
        const letter = gradeLetter(g.padj, priceBE(bs.price));   // vs THIS price's break-even
        const bettable = bs.price >= PRICE_MIN && bs.price <= PRICE_MAX; // no chalk, no lottery tickets
        // Role-unconfirmed phantom: market contradicts the depth chart AND the
        // projection sits far off this line → demote below B so it can't pass.
        const roleUnconfirmed = !!ROLE_VOL_MK[p.pos] && !roleOk.has(String(id))
          && v.proj != null && Math.abs(v.proj - line) / Math.abs(line) >= ROLE_PROJREL;
        if (roleUnconfirmed && VOL_MK.has(mk)) roleBad.add(id);   // player-level, applied after the loop
        // Gate 3: sharp-anchor disagreement. Compare our side's confidence-
        // adjusted prob to the exchange's fair for the same side; a liquid,
        // strike-matched market that disagrees by ≥SHARP_GAP caps the grade.
        const sharp = sharpFairFor(KP, p.name, mk, line);   // {over,oi,spr} or null
        const sharpSide = sharp ? (side === 'over' ? sharp.over : 1 - sharp.over) : null;
        const sharpGap = sharpSide != null ? round(g.padj - sharpSide, 3) : null;   // + = we're higher than sharp
        const sharpDisagree = sharpSide != null && Math.abs(g.padj - sharpSide) >= SHARP_GAP;
        const weakMkt = WEAK_MK.has(mk);
        const eff = (roleUnconfirmed || sharpDisagree || weakMkt) ? 'C' : letter;
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
        // Strict tier: both probabilities for THIS side, no grade/EV needed. Real books only
        // (median no-vig at the exact line); QB attempts/completions/yards sit out via weakMkt.
        if (!lineHeld && realBookAtLine && bettable && !weakMkt && !roleUnconfirmed && !projBlowout
            && !countUnderPhantom && !earlyRecHold && !sharpDisagree && sideProb >= STRICT_MODEL) {
          const rq = lq.filter(q => isRealBook(q.book)).map(q => devigPower(q.over, q.under)).filter(x => x != null).sort((x, y) => x - y);
          const mO = rq.length ? (rq.length % 2 ? rq[rq.length >> 1] : (rq[rq.length / 2 - 1] + rq[rq.length / 2]) / 2) : null;
          const mSide = mO == null ? null : side === 'over' ? mO : 1 - mO;
          if (mSide != null && mSide >= STRICT_MKT) strictCands.push({ id, name: p.name, team: p.team || null, pos: p.pos || null, opp: p.opp || null,
            commence: slateKick[[p.team, p.opp].sort().join('|')] || p.commence || null, market: mk, line, side,
            book: bs.book, price: bs.price, prob: round(sideProb, 3), mkt: round(mSide, 3), nBooks: rq.length, proj: v.proj, ev: ev != null ? round(ev * 100, 1) : null });
        }
        // Signal log: every line with a liquid Kalshi read, next to the real
        // books' no-vig P(over) and Vault's, graded by build_model_scoreboard.
        if (sharp) {
          const bp = lq.filter(q => isRealBook(q.book) && String(q.book).toLowerCase() !== 'kalshi')
            .map(q => devigPower(q.over, q.under)).filter(x => x != null).sort((a, b) => a - b);
          const bm = bp.length ? (bp.length % 2 ? bp[bp.length >> 1] : (bp[bp.length / 2 - 1] + bp[bp.length / 2]) / 2) : null;
          signals.push({ id, name: p.name, team: p.team, pos: p.pos, opp: p.opp, market: mk, line,
            commence: slateKick[[p.team, p.opp].sort().join('|')] || p.commence || null,
            kalshi: round(sharp.over, 3), kalshiInterp: !!sharp.interp, books: bm != null ? round(bm, 3) : null, nBooks: bp.length,
            vault: round(v.over, 3), held: lineHeld || undefined });
        }
        if (lineHeld) {
          if (DUMP && !held) dump.push({ id, name: p.name, team: p.team, pos: p.pos, opp: p.opp, market: mk, marketLabel: MKT_LABEL[mk] || mk, line, side, status: 'withheld', why: lineHeld });
          if (pass) heldCands.push({ id, name: p.name, team: p.team || null, pos: p.pos || null, opp: p.opp || null,
            commence: slateKick[[p.team, p.opp].sort().join('|')] || p.commence || null, market: mk, line, side,
            book: bs.book, price: bs.price, ev: round(ev * 100, 1), prob: round(g.padj, 3), grade: eff, proj: v.proj, held: lineHeld });
          continue;
        }
        if (DUMP) dump.push({ id, name: p.name, team: p.team, pos: p.pos, opp: p.opp, market: mk, marketLabel: MKT_LABEL[mk] || mk,
          line, side, prob: round(g.padj, 3), over: round(v.over, 3), proj: v.proj, book: bs.book, price: bs.price,
          ev: ev != null ? round(ev * 100, 1) : null, grade: eff, books: trust.books,
          kalshi: sharp ? sharp.over : null, kalshiInterp: !!(sharp && sharp.interp),
          status: pass ? 'pass' : roleUnconfirmed && wouldPass ? 'role' : sharpDisagree && wouldPass ? 'sharp'
            : weakMkt && wouldPass ? 'thin' : earlyRecHold && wouldPass ? 'hold' : preGate && projBlowout ? 'blowout'
            : preGate && countUnderPhantom ? 'count' : preGate && !realBookAtLine ? 'dfs' : 'no-edge' });
        if (!pass) {
          if (roleUnconfirmed && wouldPass) roleskip++;
          else if (sharpDisagree && wouldPass) sharpskip++;
          else if (weakMkt && wouldPass) weakskip++;
          else if (earlyRecHold && wouldPass) rechold++;
          else if (preGate && projBlowout) projskip++;
          else if (preGate && countUnderPhantom) countskip++;
          else if (preGate && !realBookAtLine) dfsskip++;
          else gated++;
          continue;
        }
        cands.push({
          id, name: p.name, team: p.team || null, pos: p.pos || null, opp: p.opp || null,
          commence: slateKick[[p.team, p.opp].sort().join('|')] || p.commence || null,
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
  if (roleBad.size) {
    const before = cands.length;
    for (let i = cands.length - 1; i >= 0; i--) if (roleBad.has(cands[i].id)) cands.splice(i, 1);
    roleskip += before - cands.length;
    for (const r of dump) if (r.status === 'pass' && roleBad.has(r.id)) { r.status = 'role'; r.grade = 'C'; }
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
  return { list, pool: cands, dump, heldCands, heldIds, strictCands, signals, scored, gated, preskip, offslate, benchskip, roleskip, projskip, dfsskip, countskip, sharpskip, weakskip, rechold, total: cands.length };
}

function loadCardRules() {
  try {
    const r = JSON.parse(readFileSync(RULES_FILE, 'utf8'));
    const on = Object.entries(r.buckets || {}).filter(([, v]) => v && v.on).map(([k]) => k);
    // A rules file with every type off means NO card (e.g. the history veto in
    // settle_bets.py turned the seed off); the default is only for a missing file.
    if (on.length || Object.keys(r.buckets || {}).length) return { on: new Set(on), source: 'rules' };
  } catch (e) { /* not written yet */ }
  return { on: new Set(CARD_DEFAULT_ON), source: 'default' };
}
/* Every play that reaches the live top-N, once per week per player+market, at
   the line + price it first showed. Append-only, in-season only. */
function logShadow(feed, list, bucketOf) {
  let file = null;
  try { file = JSON.parse(readFileSync(SHADOW_FILE, 'utf8')); } catch (e) { /* first run */ }
  if (!file || !Array.isArray(file.picks)) file = { picks: [] };
  const stRaw = String(feed.season_type || '').toLowerCase();
  const stype = /^post/.test(stRaw) ? 'post' : /^reg/.test(stRaw) ? 'reg' : null;
  const season = String(feed.season || ''), week = Number(feed.week) || null;
  let changed = false;
  if (stype && week && season) {
    const have = new Set(file.picks.map(p => p.key)), now = Date.now();
    for (const b of list) {
      const key = [season, stype, week, b.id, b.market].join('|');
      if (have.has(key) || !(Date.parse(b.commence || '') > now)) continue;
      file.picks.push({ key, season, stype, week, pid: String(b.id), name: b.name, team: b.team, pos: b.pos, opp: b.opp,
        commence: b.commence, market: b.market, side: b.side, line: b.line, book: b.book, price: b.price,
        book_real: isRealBook(b.book), ev: b.ev, prob: b.prob, grade: b.grade, bucket: bucketOf(b), posted: new Date().toISOString() });
      have.add(key); changed = true;
    }
  }
  if (changed) {
    file.note = 'Every play that reached the live Best Bets top-N, card or not, at the line and price it first showed. Graded by settle_bets.py into best_bets_rules.json (which play types may go on the card).';
    file.updated = new Date().toISOString();
  }
  return { file, changed };
}

function _slot(feed) {
  const stRaw = String(feed.season_type || '').toLowerCase();
  const stype = /^post/.test(stRaw) ? 'post' : /^reg/.test(stRaw) ? 'reg' : null;
  return { stype, season: String(feed.season || ''), week: Number(feed.week) || null };
}
/* Withheld-but-would-pass log: a player held because a teammate starter is OUT
   (backup-QB games, mostly) whose line still cleared every Best Bets gate.
   First read per week/player/market at its line and price, like the shadow
   log; settle_bets.py grades it into best_bets_record.json "held". */
function logHeld(feed, list, ids) {
  let file = null;
  try { file = JSON.parse(readFileSync(HELD_FILE, 'utf8')); } catch (e) { /* first run */ }
  if (!file || !Array.isArray(file.picks)) file = { picks: [] };
  const { stype, season, week } = _slot(feed);
  let changed = false;
  if (stype && week && season) {
    // every withheld player this week (not just would-pass lines), so the
    // settlement ledger can grade the model's lean on ALL their props
    const wk = [season, stype, week].join('|'), W = ((file.withheld = file.withheld || {})[wk] = file.withheld[wk] || {});
    for (const [id, why] of Object.entries(ids || {})) if (!W[id]) { W[id] = why; changed = true; }
    const have = new Set(file.picks.map(p => p.key)), now = Date.now(), seenP = new Set();
    for (const b of [...list].sort((x, y) => y.ev - x.ev)) {
      const key = [season, stype, week, b.id, b.market].join('|');
      if (seenP.has(key) || have.has(key) || !(Date.parse(b.commence || '') > now)) continue;
      seenP.add(key);
      file.picks.push({ key, season, stype, week, pid: String(b.id), name: b.name, team: b.team, pos: b.pos, opp: b.opp,
        commence: b.commence, market: b.market, side: b.side, line: b.line, book: b.book, price: b.price,
        book_real: isRealBook(b.book), ev: b.ev, prob: b.prob, grade: b.grade, proj: b.proj, held: b.held, posted: new Date().toISOString() });
      have.add(key); changed = true;
    }
  }
  if (changed) {
    file.note = 'Props withheld because a teammate starter is out (usually the QB) whose line still passed every Best Bets gate. Never shown as plays; graded to test whether the hold costs anything.';
    file.updated = new Date().toISOString();
  }
  return { file, changed };
}
/* Strict-tier shadow log (see STRICT_MODEL): first read per week/player/market at the
   line and price it showed, ranked by model probability so the best line per market
   wins the key. Graded by settle_bets.py into best_bets_record.json "strict". */
function logStrict(feed, list) {
  let file = null;
  try { file = JSON.parse(readFileSync(STRICT_FILE, 'utf8')); } catch (e) { /* first run */ }
  if (!file || !Array.isArray(file.picks)) file = { picks: [] };
  const { stype, season, week } = _slot(feed);
  let changed = false;
  if (stype && week && season) {
    const have = new Set(file.picks.map(p => p.key)), now = Date.now();
    for (const b of [...list].sort((x, y) => y.prob - x.prob)) {
      const key = [season, stype, week, b.id, b.market].join('|');
      if (have.has(key) || !(Date.parse(b.commence || '') > now)) continue;
      file.picks.push({ key, season, stype, week, pid: String(b.id), name: b.name, team: b.team, pos: b.pos, opp: b.opp,
        commence: b.commence, market: b.market, side: b.side, line: b.line, book: b.book, price: b.price, book_real: true,
        prob: b.prob, mkt: b.mkt, nBooks: b.nBooks, proj: b.proj, ev: b.ev, posted: new Date().toISOString() });
      have.add(key); changed = true;
    }
  }
  if (changed) {
    file.note = `Strict tier (shadow): Vault P(side) >= ${STRICT_MODEL} and real-book no-vig P(side) >= ${STRICT_MKT}, QB volume excluded. Never shown as plays; graded to test whether the backtest's ~70% hit rate holds live.`;
    file.updated = new Date().toISOString();
  }
  return { file, changed };
}
/* Kalshi signal log: per week/player/market/line, the first and the latest
   pre-kickoff read of Kalshi's P(over) (strike-interpolated), the real books'
   no-vig median, and Vault's. build_model_scoreboard.py grades two signals:
   Kalshi vs the books (when they differ by 5+ pts, whose side wins?) and
   Vault vs Kalshi (the Best Bets gate: when Vault is 10+ pts off Kalshi, who
   was right?). */
function logSignals(feed, rows) {
  let file = null;
  try { file = JSON.parse(readFileSync(SIGNAL_FILE, 'utf8')); } catch (e) { /* first run */ }
  if (!file || typeof file.props !== 'object') file = { props: {} };
  const { stype, season, week } = _slot(feed);
  let changed = false;
  if (stype && week && season) {
    const now = Date.now(), ts = new Date(now).toISOString();
    for (const r of rows) {
      if (!(Date.parse(r.commence || '') > now)) continue;
      const key = [season, stype, week, r.id, r.market, r.line].join('|');
      const read = { ts, kalshi: r.kalshi, interp: r.kalshiInterp, books: r.books, nBooks: r.nBooks, vault: r.vault };
      const e = file.props[key] || (file.props[key] = { season, stype, week, pid: String(r.id), name: r.name, team: r.team, pos: r.pos,
        opp: r.opp, commence: r.commence, market: r.market, line: r.line, held: r.held, first: read });
      e.last = read; changed = true;
    }
  }
  if (changed) file.updated = new Date().toISOString();
  return { file, changed };
}

/* ── pick'em pairs (see PAIR_PAYOUT) ───────────────────────────────────── */
// Inverse normal CDF (Acklam) and a bivariate normal CDF by Gauss-Legendre on
// the rho integral: the JS twin of build_prop_correlations.py joint_over().
function normInv(p) {
  const a = [-39.6968302866538, 220.946098424521, -275.928510446969, 138.357751867269, -30.6647980661472, 2.50662827745924];
  const b = [-54.4760987982241, 161.585836858041, -155.698979859887, 66.8013118877197, -13.2806815528857];
  const c = [-0.00778489400243029, -0.322396458041136, -2.40075827716184, -2.54973253934373, 4.37466414146497, 2.93816398269878];
  const d = [0.00778469570904146, 0.32246712907004, 2.445134137143, 3.75440866190742];
  const pl = 0.02425;
  if (p < pl) { const q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  if (p > 1 - pl) { const q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  const q = p - 0.5, r = q * q;
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}
const GLX = [-0.9739065285, -0.8650633667, -0.6794095683, -0.4333953941, -0.1488743390, 0.1488743390, 0.4333953941, 0.6794095683, 0.8650633667, 0.9739065285];
const GLW = [0.0666713443, 0.1494513492, 0.2190863625, 0.2692667193, 0.2955242247, 0.2955242247, 0.2692667193, 0.2190863625, 0.1494513492, 0.0666713443];
function jointOver(pa, pb, rho) {
  pa = Math.min(Math.max(pa, 1e-6), 1 - 1e-6); pb = Math.min(Math.max(pb, 1e-6), 1 - 1e-6);
  const h = normInv(pa), k = normInv(pb);
  let s = 0;
  for (let i = 0; i < 10; i++) {
    const r = rho * (GLX[i] + 1) / 2, dd = 1 - r * r;
    s += GLW[i] * Math.exp(-(h * h - 2 * r * h * k + k * k) / (2 * dd)) / (2 * Math.PI * Math.sqrt(dd));
  }
  return normCdf(h) * normCdf(k) + s * rho / 2;
}
// Power de-vig (mirror of build_model_scoreboard.devig_power).
function devigPower(ao, au) {
  const po = americanToProb(ao), pu = americanToProb(au);
  if (!(po > 0) || !(pu > 0)) return null;
  if (po + pu <= 1) return po / (po + pu);
  let lo = 1, hi = 10;
  for (let i = 0; i < 60; i++) { const k = (lo + hi) / 2; if (po ** k + pu ** k > 1) lo = k; else hi = k; }
  const k = (lo + hi) / 2; return po ** k / (po ** k + pu ** k);
}
function pickemPairs(feed, PM) {
  let COR = null;
  try { COR = JSON.parse(readFileSync(CORR_FILE, 'utf8')).pairs; } catch (e) { return []; }
  const props = feed.vegas_player_props || {}, depth = feed.vegas_depth || {}, now = Date.now();
  const byTeam = {};
  for (const id in props) {
    const p = props[id];
    const t = Date.parse(p.commence || '');
    if (!(t > now) || p.out || p.impacted || !p.team) continue;
    const dep = depth[id]; if (dep && dep[1] === 0) continue;
    const want = p.pos === 'QB' ? 'pass_yd' : (p.pos === 'WR' || p.pos === 'TE') ? 'rec_yd' : null;
    if (!want || !p.lines || !p.lines[want] || !PM.markets[want]) continue;
    const role = p.pos === 'QB' ? (dep && dep[0] != null && dep[0] > 1 ? null : 'QB1')
      : (dep && dep[0] != null) ? (p.pos === 'WR' && dep[0] <= 2 ? 'WR' + dep[0] : p.pos === 'TE' && dep[0] === 1 ? 'TE1' : null) : null;
    if (!role) continue;
    const quotes = (p.lines[want].quotes || []).filter(q => q && q.line != null);
    // the books' no-vig P(over) at their most-quoted line
    const books = quotes.filter(q => isRealBook(q.book) && q.over != null && q.under != null);
    if (books.length < 2) continue;
    const cnt = new Map(); books.forEach(q => cnt.set(q.line, (cnt.get(q.line) || 0) + 1));
    const Lb = [...cnt.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0][0];
    const qs = books.filter(q => q.line === Lb).map(q => devigPower(q.over, q.under)).filter(x => x != null);
    if (qs.length < 2) continue;
    const qb = qs.reduce((a, b) => a + b, 0) / qs.length;
    const vB = fairProbOver(PM, p.name, want, Lb, null, null);
    if (!vB) continue;
    const apps = {};
    for (const q of quotes) {
      if (!PAIR_APPS.includes(q.book) || apps[q.book] != null) continue;
      const vA = q.line === Lb ? vB : fairProbOver(PM, p.name, want, q.line, null, null);
      if (!vA) continue;
      apps[q.book] = { line: q.line, over: Math.min(Math.max(qb + (vA.over - vB.over), 0.02), 0.98) };
    }
    if (!Object.keys(apps).length) continue;
    (byTeam[p.team] = byTeam[p.team] || []).push({ id: String(id), name: p.name, team: p.team, opp: p.opp, pos: p.pos, commence: p.commence,
      role, market: want, bookLine: Lb, bookOver: round(qb, 4), apps });
  }
  const out = [];
  for (const team in byTeam) {
    const qbs = byTeam[team].filter(x => x.role === 'QB1'), recs = byTeam[team].filter(x => x.role !== 'QB1');
    for (const Q of qbs) for (const Rr of recs) {
      const key = `QB1:pass_yd|${Rr.role}:rec_yd`, c = COR && COR[key];
      if (!c || c.rho == null) continue;
      for (const app in Q.apps) {
        const A = Q.apps[app], B = Rr.apps[app]; if (!B) continue;
        for (const dir of ['over', 'under']) {
          const pa = dir === 'over' ? A.over : 1 - A.over, pb = dir === 'over' ? B.over : 1 - B.over;
          const joint = jointOver(pa, pb, c.rho), ev = joint * PAIR_PAYOUT - 1;
          if (ev < PAIR_MIN_EV) continue;
          out.push({ app, dir, rho: c.rho, joint: round(joint, 4), indep: round(pa * pb, 4), ev: round(ev * 100, 1), payout: PAIR_PAYOUT, commence: Q.commence,
            legs: [{ pid: Q.id, name: Q.name, team, pos: 'QB', role: 'QB1', market: 'pass_yd', side: dir, line: A.line, p: round(pa, 4), bookLine: Q.bookLine },
                   { pid: Rr.id, name: Rr.name, team, pos: Rr.pos, role: Rr.role, market: 'rec_yd', side: dir, line: B.line, p: round(pb, 4), bookLine: Rr.bookLine }] });
        }
      }
    }
  }
  out.sort((a, b) => b.ev - a.ev);
  const seenQB = new Set(), top = [];
  for (const x of out) { if (seenQB.has(x.legs[0].pid)) continue; seenQB.add(x.legs[0].pid); top.push(x); if (top.length >= PAIR_TOP) break; }
  return top;
}
function logPairs(feed, pairs) {
  let file = null;
  try { file = JSON.parse(readFileSync(PAIRS_LOG, 'utf8')); } catch (e) { /* first run */ }
  if (!file || !Array.isArray(file.pairs)) file = { pairs: [] };
  const stRaw = String(feed.season_type || '').toLowerCase();
  const stype = /^post/.test(stRaw) ? 'post' : /^reg/.test(stRaw) ? 'reg' : null;
  const season = String(feed.season || ''), week = Number(feed.week) || null;
  let changed = false;
  if (stype && week && season) {
    const have = new Set(file.pairs.map(x => x.key)), now = Date.now();
    for (const x of pairs) {
      const key = [season, stype, week, x.app, x.legs[0].pid, x.legs[1].pid, x.dir].join('|');
      if (have.has(key) || !(Date.parse(x.commence || '') > now)) continue;
      file.pairs.push({ key, season, stype, week, ...x, posted: new Date().toISOString() });
      have.add(key); changed = true;
    }
  }
  if (changed) {
    file.note = "Every pick'em pair Vault surfaced, at the app lines and joint probability when it first showed. Graded by settle_bets.py (both legs must win; a void or push leg voids the pair).";
    file.updated = new Date().toISOString();
  }
  return { file, changed };
}

/* ── locked weekly card (see CARD_MAX) ─────────────────────────────────────
   Appends any live top-N play not yet on this week's card, up to CARD_MAX and
   one per player, and only before its game kicks off. Existing entries are
   never edited, so the line + price a user saw is the line + price we grade.
   In-season only: preseason/offseason feeds never touch the file. */
function lockCard(feed, list) {
  let file = null;
  try { file = JSON.parse(readFileSync(CARD_FILE, 'utf8')); } catch (e) { /* first run */ }
  if (!file || !Array.isArray(file.picks)) file = { picks: [] };
  const stRaw = String(feed.season_type || '').toLowerCase();
  const stype = /^post/.test(stRaw) ? 'post' : /^reg/.test(stRaw) ? 'reg' : null;
  const season = String(feed.season || ''), week = Number(feed.week) || null;
  const cur = file.picks.filter(p => p.season === season && p.stype === stype && p.week === week);
  const added = [];
  if (stype && week && season) {
    const now = Date.now(), have = new Set(cur.map(p => String(p.pid)));
    for (const b of list) {
      if (cur.length >= CARD_MAX) break;
      if (have.has(String(b.id))) continue;
      const kick = Date.parse(b.commence || '');
      if (!(kick > now)) continue;
      const pick = {
        key: [season, stype, week, b.id, b.market].join('|'), season, stype, week,
        pid: String(b.id), name: b.name, team: b.team, pos: b.pos, opp: b.opp, commence: b.commence,
        market: b.market, marketLabel: b.marketLabel, side: b.side, line: b.line,
        book: b.book, price: b.price, ev: b.ev, prob: b.prob, grade: b.grade, proj: b.proj,
        posted: new Date().toISOString(),
      };
      file.picks.push(pick); cur.push(pick); have.add(pick.pid);
      added.push(`${b.name} ${b.side} ${b.line} ${b.marketLabel}`);
    }
  }
  if (added.length) {
    file.note = 'Vault\'s locked weekly card: each play frozen at the line and price it posted with. Append-only. Graded into best_bets_record.json by scripts/settle_bets.py.';
    file.card_max = CARD_MAX;
    file.updated = new Date().toISOString();
  }
  return { picks: cur, file, changed: added.length > 0, added };
}

/* ── game leans (CONTEXT only; empty while the model is gated) ──────────── */
const GM_ALIAS = { OAK: 'LV', SD: 'LAC', STL: 'LA', LAR: 'LA', WSH: 'WAS' };
function gameLeans(feed) {
  let gm = null;
  try { gm = JSON.parse(readFileSync(resolve(ROOT, 'data/game_model.json'), 'utf8')); } catch (e) { return { list: [], gated: 'no-model' }; }
  // The game model matches but does not beat the market, and gates itself off
  // in the offseason — honor that. Leans light up in-season.
  if (gm.offseason) return { list: [], gated: 'offseason' };
  const teams = gm.teams || {}, hfa = num(gm.hfa) || 0, base = num(gm.base_pts) || 22.5;
  // backup QB (fetch-pickem-props.mjs → qb_status.json): fitted points off
  let qbTeams = {};
  try { qbTeams = JSON.parse(readFileSync(resolve(ROOT, 'data/qb_status.json'), 'utf8')).teams || {}; } catch (e) { /* none */ }
  const qbM = num(gm.qb && gm.qb.margin) || 0, qbT = num(gm.qb && gm.qb.total) || 0;
  // Slate gate (same rule as scoreProps): vegas_games runs weeks ahead, so
  // in-season a lean only counts for an unstarted game on the served week.
  // Without it an Oct-4 game headlined the Week 3 tile.
  const inSeason = /^(reg|post)/i.test(feed.season_type || '');
  const now = Date.now(), feedWeek = Number(feed.week) || null;
  const out = [];
  let offslate = 0;
  for (const g of (feed.vegas_games || [])) {
    if (inSeason) {
      const t = g.commence ? Date.parse(g.commence) : NaN;
      const wrongWeek = feedWeek != null && g.week != null && Number(g.week) !== feedWeek;
      if (wrongWeek || !(Number.isFinite(t) && t > now)) { offslate++; continue; }
    }
    const home = GM_ALIAS[g.home] || g.home, away = GM_ALIAS[g.away] || g.away;   // feed says LAR, model says LA
    const H = teams[home], A = teams[away]; if (!H || !A) continue;
    const gHfa = (gm.neutral || []).includes(`${away}@${home}`) ? 0 : hfa;   // international games: no home field
    const hb = qbTeams[home] ? 1 : 0, ab = qbTeams[away] ? 1 : 0;
    const projMargin = (num(H.rate) - num(A.rate)) + gHfa - qbM * (hb - ab);   // home minus away
    // def is points PREVENTED (positive = good defense), so it comes off the total
    const projTotal = 2 * base + num(H.off) + num(A.off) - num(H.def) - num(A.def) - qbT * (hb + ab);
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
  return { list: out.slice(0, LEANS), gated: null, offslate };
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
    log(`props: ${props.total} qualified of ${props.scored} scored (${props.gated} gated, ${props.offslate} off-slate, ${props.benchskip} benched, ${props.roleskip} role-unconfirmed, ${props.sharpskip} sharp-disagree, ${props.weakskip} thin-edge-market, ${props.rechold} early-rec-hold, ${props.projskip} proj-blowout, ${props.countskip} count-under-phantom, ${props.dfsskip} dfs-only) → top ${props.list.length}`);
    log(`game leans: ${leans.gated ? leans.gated : props.total >= 0 ? leans.list.length : 0}${leans.gated ? ' (empty)' : ` (${leans.offslate} off-slate)`}`);
    for (const b of props.list) log(`  • ${b.name} ${b.marketLabel} ${b.side.toUpperCase()} ${b.line} @ ${b.book} ${b.price > 0 ? '+' : ''}${b.price} — ${b.grade}, ${b.ev}% EV, ${b.books} books, ${b.games}g${b.sharpFair != null ? `, sharp ${(b.sharpFair * 100).toFixed(0)}% (gap ${b.sharpGap > 0 ? '+' : ''}${(b.sharpGap * 100).toFixed(0)}pt)` : ''}`);

    // Card eligibility (data/best_bets_rules.json, written by settle_bets.py):
    // only play types whose own recent record earned a spot. The card draws its
    // top-N from those types alone, at a real sportsbook's price (pick'em apps
    // pay flat, so their "price" isn't a bet anyone can place). props.list stays
    // unfiltered: it feeds the shadow log, which is how a type earns its way on.
    const rules = loadCardRules();
    const bucketOf = b => `${b.market}|${b.side}|${b.pos === 'RB' ? 'RB' : b.pos === 'QB' ? 'QB' : 'WR/TE'}`;
    const seenP = new Set(), eligible = [];
    for (const c of props.pool || []) {
      if (!rules.on.has(bucketOf(c)) || !isRealBook(c.book) || seenP.has(c.id)) continue;
      seenP.add(c.id); eligible.push(c); if (eligible.length >= TOP) break;
    }
    const shadow = logShadow(feed, props.list, bucketOf);
    const pairs = pickemPairs(feed, PM);
    const pairLog = logPairs(feed, pairs);
    log(`pick'em pairs: ${pairs.length}` + pairs.map(x => ` | ${x.app}: ${x.legs[0].name} ${x.dir} ${x.legs[0].line} + ${x.legs[1].name} ${x.dir} ${x.legs[1].line} joint ${(x.joint * 100).toFixed(1)}% (indep ${(x.indep * 100).toFixed(1)}%)`).join(''));
    const card = lockCard(feed, eligible);

    feed.best_bets = {
      generated: new Date().toISOString(),
      season: feed.season || null, week: feed.week || null,
      be_ref: BE_REF, be_mode: 'price',
      props: props.list,
      // The locked weekly card (data/best_bets_card.json): every play that has
      // posted this week, frozen at the line + price it posted with. This is
      // what the hero shows; `props` above is the live top-N that feeds it.
      card: card.picks, card_max: CARD_MAX,
      card_rule: { on: [...rules.on].sort(), source: rules.source },
      pairs,
      game_leans: leans.list,
      game_leans_note: leans.gated === 'offseason'
        ? 'Game leans light up in-season — the game model is context, not an edge, and is gated off in the offseason.'
        : 'Game leans are model context, not an edge — the game model matches the market without beating it.',
      note: 'Top props by confidence-adjusted EV on corroborated lines (≥2 books), modeled markets only.',
    };
    if (DUMP) { writeFileSync(DUMP, JSON.stringify({ generated: feed.best_bets.generated, props: props.dump, eligible: eligible.map(c => c.id + '|' + c.market) }, null, 1)); log(`dump: ${props.dump.length} rows → ${DUMP}`); return; }
    if (DRY) { log('DRY — not writing'); return; }
    if (shadow.changed) writeFileSync(SHADOW_FILE, JSON.stringify(shadow.file, null, 1) + '\n');
    const strictLog = logStrict(feed, props.strictCands);
    log(`strict tier (shadow): ${props.strictCands.length} lines now · ${strictLog.file.picks.length} logged`);
    if (strictLog.changed) writeFileSync(STRICT_FILE, JSON.stringify(strictLog.file, null, 1) + '\n');
    const heldLog = logHeld(feed, props.heldCands, props.heldIds), sigLog = logSignals(feed, props.signals);
    log(`held (withheld but would have passed): ${props.heldCands.length} now · ${heldLog.file.picks.length} logged · kalshi signals: ${props.signals.length} lines now`);
    if (heldLog.changed) writeFileSync(HELD_FILE, JSON.stringify(heldLog.file, null, 1) + '\n');
    if (sigLog.changed) writeFileSync(SIGNAL_FILE, JSON.stringify(sigLog.file));
    if (pairLog.changed) writeFileSync(PAIRS_LOG, JSON.stringify(pairLog.file, null, 1) + '\n');
    if (card.changed) { writeFileSync(CARD_FILE, JSON.stringify(card.file, null, 1) + '\n'); log('card: locked', card.added.join(', ') || 'nothing new'); }
    writeFileSync(FEED, JSON.stringify(feed));
    log('wrote best_bets to', FEED);
  } catch (e) {
    log('ERROR:', e.message);
    process.exit(0);   // never fail the workflow
  }
})();
