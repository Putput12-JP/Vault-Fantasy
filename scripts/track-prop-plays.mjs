/* ════════════════════════════════════════════════════════════════════════
   VAULT · PROP PLAY TRACKER  (called by fetch-sharp-money.mjs after the props board)

   Every +EV call on the Props board is logged at FIRST SIGHTING, at the price it
   showed, then followed to the whistle:

     log      first time a (week, player, stat, line, side) shows a takeable +EV call,
              pregame, on fresh prices. Stale-price calls are never logged (that is
              the phantom-edge trap). Edges of 10%+ are logged but tagged `big`, so the
              record can say whether they were real.
     close    while the game has not started, keep the latest no-vig fair for that side.
              When the game starts it freezes: that is the closing price.
     CLV      closeFair / calledPrice - 1. Positive = the price beat the close. This is
              the fast read: it accrues without waiting for results. NOTE: closeFair comes from the same fair source that
              raised the call, so it repeats the call's own edge. clvX (scripts/regrade_prop_clv.py) is the same ratio against
              the exchange close from the prop close tape, which did not raise the call. Read clvX, not clv, as confirmation.
     settle   from data/nflverse_stats_<season>.json box scores (ESPN's overlay fills weeks nflverse lacks), in the week the kickoff
              falls in (the board's week can lag the slate). A box score lists only players who recorded a stat, so a missing row is
              not a DNP: once the team's game is in the box, Sleeper's weekly stats say whether the player took a snap. Played =
              graded on Sleeper's number (a stat it omits is 0); not played = void. No answer 36h after kickoff = void. Flat 1 unit
              at the called price. Pick'em legs settle the same way.

   The ledger is append/merge keyed, carried between runs in <dir>/prop_plays.json
   (the Action loads it from the sharp-data branch and publishes it back).
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, existsSync } from 'node:fs';
import { nkey, shiftFair } from './build-props-board.mjs';

// market -> nflverse weekly columns (same table as settle_bets.py COL; combos sum)
const COL = {
  pass_yd: ['pyds'], pass_att: ['att'], pass_cmp: ['cmp'], pass_td: ['ptds'], pass_int: ['ints'],
  rush_yd: ['ryds'], rush_att: ['car'], rec: ['rec'], rec_yd: ['recyds'],
  anytime_td: ['rtds', 'rectds'], rush_rec_yd: ['ryds', 'recyds'], pass_rush_yd: ['pyds', 'ryds'],
};
// the board's team codes and the app's game codes disagree in a few places
const ALIAS = { JAX: 'JAC', LAR: 'LA', WSH: 'WAS', ARZ: 'ARI', BLT: 'BAL', CLV: 'CLE', HST: 'HOU', SD: 'LAC', STL: 'LA', OAK: 'LV' };
const tm = t => ALIAS[t] || t;
const MIN_EV = 0.03;           // log threshold: a bit above the board's 2% so noise-level devig gaps don't pad the record
const VOID_AFTER = 36 * 3600;

const dec = p => 1 / p;
export const keyOf = (season, week, pid, mkt, line, side) => [season, week, pid, mkt, line, side].join('|');

function gameStart(games, team) {
  const t = tm(team);
  for (const g of games) {
    if (g.sport !== 'nfl') continue;
    if (tm(g.home?.abbr) === t || tm(g.away?.abbr) === t) return g.start;
  }
  return null;
}

const _nidx = new WeakMap();
export function actualOf(stats, name, week, mkt) {
  let p = stats?.[name];
  if (!p && stats) {                                   // board and box-score names differ in suffixes ("Aaron Jones" vs "Aaron Jones Sr.")
    let ix = _nidx.get(stats);
    if (!ix) { ix = new Map(); for (const k of Object.keys(stats)) ix.set(nkey(k), k); _nidx.set(stats, ix); }
    const k = ix.get(nkey(name)); if (k) p = stats[k];
  }
  if (!p) return { has: false };
  const w = (p.weeks || []).find(x => x.wk === week);
  if (!w) return { has: false };
  const cols = COL[mkt]; if (!cols) return { has: false };
  return { has: true, val: cols.reduce((s, c) => s + (+w[c] || 0), 0) };
}

/* ---- NFL settle: the week a kickoff is in, and whether a player missing from the box score played ----
   Shared with track-v2-plays.mjs. A row is { season, week, start, name, pid, team, mkt } (the prop ledger's own shape; v2 passes its prop). */
// Week 1 opens the Tuesday after Labor Day and weeks turn over Tuesday 12:00 UTC, after Monday night. Weeks 19+ are the playoffs (nflverse numbering).
export function nflWeekOf(start, season) {
  const y = +season; if (!y || !start) return null;
  const labor = Date.UTC(y, 8, 1 + (8 - new Date(Date.UTC(y, 8, 1)).getUTCDay()) % 7);
  const w = Math.floor((start * 1000 - labor - 36 * 3600e3) / (7 * 86400e3)) + 1;
  return w >= 1 && w <= 22 ? w : null;
}
export const SLEEPER_WEEK = (season, week) => `https://api.sleeper.app/v1/stats/nfl/regular/${season}/${week}`;
const SLEEPER_COL = { pass_yd: ['pass_yd'], pass_att: ['pass_att'], pass_cmp: ['pass_cmp'], pass_td: ['pass_td'], pass_int: ['pass_int'],
  rush_yd: ['rush_yd'], rush_att: ['rush_att'], rec: ['rec'], rec_yd: ['rec_yd'], anytime_td: ['rush_td', 'rec_td'], rush_rec_yd: ['rush_yd', 'rec_yd'], pass_rush_yd: ['pass_yd', 'rush_yd'] };
const BOX_TEAM = { LAR: 'LA', WSH: 'WAS', JAC: 'JAX', LVR: 'LV', OAK: 'LV', ARZ: 'ARI' }, bt = t => BOX_TEAM[t] || t;
// the team's game is in the box once any opponent has a row that week against it
const teamInBox = (stats, team, wk) => !!team && Object.values(stats || {}).some(p => (p.weeks || []).some(w => w.wk === wk && bt(w.opp) === bt(team)));
/* { val, wk, src? } graded, { wk, dnp: true } did not play, or { wk } not known yet. Sleeper's ids are the board's pids. */
export function nflResult(x, stats, snaps = {}) {
  const wk = nflWeekOf(x.start, x.season) ?? x.week;
  const a = actualOf(stats, x.name, wk, x.mkt);
  if (a.has) return { wk, val: a.val };
  const day = snaps[x.season + '|' + wk];
  if (!day || !teamInBox(stats, x.team, wk)) return { wk };
  const s = day[x.pid];
  if (!s || !(s.gp > 0 || s.off_snp > 0)) return { wk, dnp: true };
  const cols = SLEEPER_COL[x.mkt];
  return cols ? { wk, val: cols.reduce((t, c) => t + (+s[c] || 0), 0), src: 'sleeper' } : { wk };
}
const getJson = async u => { const r = await fetch(u, { signal: AbortSignal.timeout(20000) }); return r.ok ? r.json() : null; };
// Sleeper's weekly stats for each (season, week) in rows, regular season only: { 'season|week': { pid: stats } }. A week with no game played yet is left out.
export async function fetchSleeperWeeks(rows, fetchJson = getJson) {
  const keys = new Set(), out = {};
  for (const x of rows) { const w = nflWeekOf(x.start, x.season); if (w && w <= 18) keys.add(x.season + '|' + w); }
  for (const k of keys) {
    try { const d = await fetchJson(SLEEPER_WEEK(...k.split('|'))); if (d && Object.values(d).some(r => r && r.gp > 0)) out[k] = d; } catch { /* Sleeper is down: tried again next run, the 36h void still applies */ }
  }
  return out;
}
const SETTLED = new Set(['won', 'lost', 'push']);
// graded before the week came from kickoff, against the board's lagging week: its own game is a week later
const misweek = x => SETTLED.has(x.status) && x.statWeek == null && (nflWeekOf(x.start, x.season) ?? x.week) !== x.week;
// still to settle, voided before the snap check (no voidWhy), or graded on the wrong week
const nflDue = (x, nowS) => nowS >= x.start + 3 * 3600 && (x.status === 'open' || (x.status === 'void' && !x.voidWhy) || misweek(x));
// the prop ledger's plays and legs that need Sleeper this run; fetch-sharp-money.mjs awaits this before the synchronous trackPlays
export const fetchPropSnaps = (L, nowS, fetchJson) => fetchSleeperWeeks([...Object.values(L?.plays || {}), ...Object.values(L?.legs || {})].filter(x => nflDue(x, nowS)), fetchJson);
function noteWeek(x, r) { if (r.wk !== x.week) x.statWeek = r.wk; if (r.src) x.actualSrc = r.src; }
function gradeRow(x, a, priced, nowS) {
  const was = x.status; x.actual = a;
  const push = a === x.line, win = x.side === 'over' ? a > x.line : a < x.line;
  x.status = push ? 'push' : win ? 'won' : 'lost';
  if (priced) { x.units = push ? 0 : win ? +(dec(x.called.p) - 1).toFixed(3) : -1; if (x.status !== was || x.settledAt == null) x.settledAt = nowS; }
}
function voidRow(x, priced) { x.status = 'void'; if (priced) x.units = 0; delete x.actual; }

// nflverse box scores publish hours-to-a-day after a game; data/espn_player_stats_<season>.json carries ESPN's the minutes it ends
// (settle_bets.py overlays it the same way). Fill any week nflverse does not have yet; nflverse always wins on conflict.
export function overlayEspn(stats, espn) {
  if (!espn) return stats;
  const out = stats ? { ...stats } : {};
  const by = new Map(Object.keys(out).map(k => [nkey(k), k]));
  for (const [name, rec] of Object.entries(espn)) {
    if (!rec || !Array.isArray(rec.weeks)) continue;
    const tgt = by.get(nkey(name)) || name;
    const cur = out[tgt] ? { ...out[tgt], weeks: [...(out[tgt].weeks || [])] } : { name, weeks: [] };
    for (const w of rec.weeks) if (w && w.wk != null && !cur.weeks.some(x => x.wk === w.wk)) cur.weeks.push(w);
    out[tgt] = cur;
    by.set(nkey(tgt), tgt);
  }
  return out;
}

// What the Vault prop model said about the side we called, banked beside the price so the model can be scored later as a tilt on the market
// (scripts/fit_prop_offset.py). d is the model-minus-fair gap in logit space on the called side. Log only; nothing reads it for a decision yet.
const lgt = p => Math.log(Math.min(0.995, Math.max(0.005, p)) / (1 - Math.min(0.995, Math.max(0.005, p))));
function modelBlock(probe, r, c, line, fair) {
  const m = probe ? probe(r.pid, r.mkt, line) : null;
  if (!m || m.over == null) return null;
  const p = c.side === 'over' ? m.over : 1 - m.over;
  return { proj: m.proj, p: +p.toFixed(4), d: fair != null ? +(lgt(p) - lgt(fair)).toFixed(4) : null, games: m.games, roleMult: m.roleMult ?? null };
}

export function trackPlays({ board, feed, games, ledger, stats, nowS, shift, probe, nflSnaps = {} }) {
  const L = ledger && ledger.plays ? ledger : { plays: {} };
  L.legs ||= {};
  const season = String(feed?.season || ''), week = feed?.week;
  const stale = board?.sources?.stale || {};
  const freshFor = r => r.fairSrc === 'Pinnacle' ? !stale.pinnacle : !stale.kalshi;   // the fair price a close or a leg is measured against must itself be fresh

  // 1. log new calls and refresh the close on open ones
  const rowByKey = new Map(), rowByPid = new Map();
  for (const r of board?.rows || []) rowByPid.set(r.pid + '|' + r.mkt, { r });
  for (const r of board?.rows || []) {
    for (const side of ['over', 'under']) rowByKey.set(keyOf(season, week, r.pid, r.mkt, r.line, side), { r, side });
  }
  for (const r of board?.rows || []) {
    for (const c of [r.call, r.alt]) {                              // a same-line call and/or a moved-line (converted) call
      if (!c || c.stale || c.ev < (c.shifted ? 0.05 : MIN_EV) || c.depth === 0) continue;
      const start = gameStart(games, r.team);
      if (!start || start <= nowS) continue;                         // pregame only, and only if we can see the game
      const line = c.shifted ? c.line : r.line;
      const k = keyOf(season, week, r.pid, r.mkt, line, c.side);
      if (L.plays[k]) continue;
      L.plays[k] = {
        id: k, season, week, pid: r.pid, name: r.name, team: r.team, pos: r.pos, mkt: r.mkt, label: r.label, line, side: c.side,
        start, firstSeen: nowS, called: { src: c.src, kind: c.kind, am: c.am, p: c.p, ev: c.ev, evAdj: c.evAdj ?? null, depth: c.depth ?? null, fair: c.shifted ? c.fairAtLine : r[c.side].fair, fairSrc: r.fairSrc },
        big: !!c.big, shifted: !!c.shifted, refLine: r.line, status: 'open',
      };
      const mb = modelBlock(probe, r, c, line, L.plays[k].called.fair);
      if (mb) L.plays[k].model = mb;
    }
  }
  // pick'em legs: no price, so the test is calibration. Log each fresh leg once with the win chance we gave it.
  if (!stale.pinnacle) for (const g of board?.legs || []) {
    if (g.p < 0.56) continue;
    const start = gameStart(games, g.team); if (!start || start <= nowS) continue;
    const k = [season, week, g.pid, g.mkt, g.book, g.line, g.side].join('|');
    if (L.legs[k]) continue;
    L.legs[k] = { id: k, season, week, pid: g.pid, name: g.name, team: g.team, mkt: g.mkt, label: g.label, book: g.book, line: g.line, side: g.side, p: g.p, shifted: g.shifted, start, firstSeen: nowS, status: 'open' };
  }
  for (const P of Object.values(L.plays)) {
    if (P.status !== 'open' && P.closeFair != null) continue;
    if (nowS < P.start) {
      const hit = P.shifted ? rowByPid.get(P.pid + '|' + P.mkt) : rowByKey.get(keyOf(P.season, P.week, P.pid, P.mkt, P.line, P.side));
      let f = hit?.r[P.side]?.fair;
      if (P.shifted && hit?.r.fair != null) {            // convert the current fair over-price at the board's line to the play's line
        const fo = shiftFair(shift, P.mkt, hit.r.fair, hit.r.line, P.line);
        f = fo == null ? null : P.side === 'over' ? fo : 1 - fo;
      }
      if (f != null && hit && freshFor(hit.r)) { P.closeFair = f; P.closeAt = nowS; }
    }
    if (P.closeFair != null) P.clv = +(P.closeFair / P.called.p - 1).toFixed(4);
  }

  settleProps(L, { stats, nowS, nflSnaps });
  return L;
}

// 2. settle (plays and pick'em legs)
export function settleProps(L, { stats, nowS, nflSnaps = {} }) {
  L.legs ||= {};
  // History is fixed here, once per row. A play or leg voided before the snap check may be a player who played and recorded none of the
  // stat: graded if he played, marked dnp if he did not, marked nobox once the week can be read and still says nothing. One graded on
  // the board's lagging week is graded again on its own game; `regraded` keeps what it was.
  const out = { settled: 0, void: 0, regraded: 0 };
  for (const [xs, priced] of [[L.plays, true], [L.legs, false]]) for (const x of Object.values(xs)) {
    if (!nflDue(x, nowS)) continue;
    const r = nflResult(x, stats, nflSnaps), was = x.status, read = !!nflSnaps[x.season + '|' + r.wk] || !(r.wk <= 18);
    const redo = was === 'open' ? null : was === 'void' ? { from: 'void', at: nowS } : { from: was, wk: x.week, actual: x.actual ?? null, ...(priced ? { units: x.units } : {}), at: nowS };
    if (r.val != null) { noteWeek(x, r); gradeRow(x, r.val, priced, nowS); }
    else if (r.dnp) { noteWeek(x, r); x.voidWhy = 'dnp'; voidRow(x, priced); }
    else if (was === 'open' ? nowS > x.start + VOID_AFTER : read) { if (was !== 'void') noteWeek(x, r); x.voidWhy = 'nobox'; voidRow(x, priced); }
    else continue;
    if (!redo) x.status === 'void' ? out.void++ : out.settled++;
    else if (was === 'void' ? x.status !== 'void' : x.status !== was || x.actual !== redo.actual) { x.regraded = redo; out.regraded++; }
  }
  return out;
}

// aggregates the page reads: overall and split by what a reader would want to know
export function recordOf(L) {
  const all = Object.values(L.plays || {});
  const agg = xs => {
    const done = xs.filter(x => x.status === 'won' || x.status === 'lost');
    const cl = xs.filter(x => x.clv != null);
    const cx = xs.filter(x => x.clvX != null);          // CLV against an exchange close that did not raise the call (scripts/regrade_prop_clv.py)
    return {
      n: xs.length, open: xs.filter(x => x.status === 'open').length, w: done.filter(x => x.status === 'won').length, l: done.filter(x => x.status === 'lost').length,
      p: xs.filter(x => x.status === 'push').length, void: xs.filter(x => x.status === 'void').length,
      units: +done.reduce((s, x) => s + x.units, 0).toFixed(2), roi: done.length ? +(done.reduce((s, x) => s + x.units, 0) / done.length).toFixed(4) : null,
      clvN: cl.length, clv: cl.length ? +(cl.reduce((s, x) => s + x.clv, 0) / cl.length).toFixed(4) : null, clvPos: cl.filter(x => x.clv > 0).length,
      clvXN: cx.length, clvX: cx.length ? +(cx.reduce((s, x) => s + x.clvX, 0) / cx.length).toFixed(4) : null, clvXPos: cx.filter(x => x.clvX > 0).length,
    };
  };
  const by = f => { const m = {}; for (const x of all) (m[f(x)] ||= []).push(x); return Object.fromEntries(Object.entries(m).map(([k, v]) => [k, agg(v)])); };
  return {
    all: agg(all), clean: agg(all.filter(x => !x.big)), big: agg(all.filter(x => x.big)),
    legs: (() => {
      const gs = Object.values(L.legs || {}), done = gs.filter(x => x.status === 'won' || x.status === 'lost');
      const bucket = (lo, hi) => { const xs = done.filter(x => x.p >= lo && x.p < hi); return { lo, hi, n: xs.length, hit: xs.length ? +(xs.filter(x => x.status === 'won').length / xs.length).toFixed(4) : null, pred: xs.length ? +(xs.reduce((s, x) => s + x.p, 0) / xs.length).toFixed(4) : null }; };
      return { n: gs.length, open: gs.filter(x => x.status === 'open').length, graded: done.length, buckets: [bucket(0.54, 0.58), bucket(0.58, 0.62), bucket(0.62, 0.7), bucket(0.7, 1)],
        shifted: { n: done.filter(x => x.shifted).length, hit: done.filter(x => x.shifted).length ? +(done.filter(x => x.shifted && x.status === 'won').length / done.filter(x => x.shifted).length).toFixed(4) : null, pred: done.filter(x => x.shifted).length ? +(done.filter(x => x.shifted).reduce((s, x) => s + x.p, 0) / done.filter(x => x.shifted).length).toFixed(4) : null } };
    })(),
    byVenue: by(x => (x.shifted ? 'Different line: ' : '') + (x.called.kind === 'exchange' ? x.called.src : 'US books')), byMarket: by(x => x.label), bySide: by(x => x.side),
    // The fair price a call was measured against: 'Pinnacle' for every call logged before props were anchored on the exchange, then 'Novig', 'Kalshi' or 'Novig + Kalshi'.
    byFair: by(x => /Novig|Kalshi/.test(x.called.fairSrc || '') ? 'Exchange anchor' : (x.called.fairSrc || 'Pinnacle')),
    recent: all.sort((a, b) => b.firstSeen - a.firstSeen).slice(0, 80).map(x => ({ ...x })),
  };
}

export function loadLedger(file) { try { return existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : { plays: {} }; } catch { return { plays: {} }; } }
