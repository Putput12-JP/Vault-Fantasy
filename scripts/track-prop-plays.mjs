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
              the fast read: it accrues without waiting for results.
     settle   from data/nflverse_stats_<season>.json box scores. Flat 1 unit at the
              called price. A player with no box-score row 36h after kickoff is void.

   The ledger is append/merge keyed, carried between runs in <dir>/prop_plays.json
   (the Action loads it from the sharp-data branch and publishes it back).
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, existsSync } from 'node:fs';
import { nkey } from './build-props-board.mjs';

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

function actualOf(stats, name, week, mkt) {
  const p = stats?.[name]; if (!p) return { has: false };
  const w = (p.weeks || []).find(x => x.wk === week);
  if (!w) return { has: false };
  const cols = COL[mkt]; if (!cols) return { has: false };
  return { has: true, val: cols.reduce((s, c) => s + (+w[c] || 0), 0) };
}

export function trackPlays({ board, feed, games, ledger, stats, nowS }) {
  const L = ledger && ledger.plays ? ledger : { plays: {} };
  const season = String(feed?.season || ''), week = feed?.week;
  const stale = board?.sources?.stale || {};
  const anyStale = stale.books || stale.kalshi || stale.novig;

  // 1. log new calls and refresh the close on open ones
  const rowByKey = new Map();
  for (const r of board?.rows || []) {
    for (const side of ['over', 'under']) rowByKey.set(keyOf(season, week, r.pid, r.mkt, r.line, side), { r, side });
  }
  if (!anyStale) for (const r of board?.rows || []) {
    const c = r.call; if (!c || c.stale || c.ev < MIN_EV || c.depth === 0) continue;
    const start = gameStart(games, r.team);
    if (!start || start <= nowS) continue;                         // pregame only, and only if we can see the game
    const k = keyOf(season, week, r.pid, r.mkt, r.line, c.side);
    if (L.plays[k]) continue;
    L.plays[k] = {
      id: k, season, week, pid: r.pid, name: r.name, team: r.team, pos: r.pos, mkt: r.mkt, label: r.label, line: r.line, side: c.side,
      start, firstSeen: nowS, called: { src: c.src, kind: c.kind, am: c.am, p: c.p, ev: c.ev, depth: c.depth ?? null, fair: r[c.side].fair, fairSrc: r.fairSrc },
      big: !!c.big, status: 'open',
    };
  }
  for (const P of Object.values(L.plays)) {
    if (P.status !== 'open' && P.closeFair != null) continue;
    if (nowS < P.start) {
      const hit = rowByKey.get(keyOf(P.season, P.week, P.pid, P.mkt, P.line, P.side));
      const f = hit?.r[P.side]?.fair;
      if (f != null && !anyStale) { P.closeFair = f; P.closeAt = nowS; }
    }
    if (P.closeFair != null) P.clv = +(P.closeFair / P.called.p - 1).toFixed(4);
  }

  // 2. settle
  for (const P of Object.values(L.plays)) {
    if (P.status !== 'open' || nowS < P.start + 3 * 3600) continue;
    const a = actualOf(stats, P.name, P.week, P.mkt);
    if (!a.has) { if (nowS > P.start + VOID_AFTER) { P.status = 'void'; P.units = 0; } continue; }
    P.actual = a.val;
    const win = P.side === 'over' ? a.val > P.line : a.val < P.line;
    const push = a.val === P.line;
    P.status = push ? 'push' : win ? 'won' : 'lost';
    P.units = push ? 0 : win ? +(dec(P.called.p) - 1).toFixed(3) : -1;
    P.settledAt = nowS;
  }
  return L;
}

// aggregates the page reads: overall and split by what a reader would want to know
export function recordOf(L) {
  const all = Object.values(L.plays || {});
  const agg = xs => {
    const done = xs.filter(x => x.status === 'won' || x.status === 'lost');
    const cl = xs.filter(x => x.clv != null);
    return {
      n: xs.length, open: xs.filter(x => x.status === 'open').length, w: done.filter(x => x.status === 'won').length, l: done.filter(x => x.status === 'lost').length,
      p: xs.filter(x => x.status === 'push').length, void: xs.filter(x => x.status === 'void').length,
      units: +done.reduce((s, x) => s + x.units, 0).toFixed(2), roi: done.length ? +(done.reduce((s, x) => s + x.units, 0) / done.length).toFixed(4) : null,
      clvN: cl.length, clv: cl.length ? +(cl.reduce((s, x) => s + x.clv, 0) / cl.length).toFixed(4) : null, clvPos: cl.filter(x => x.clv > 0).length,
    };
  };
  const by = f => { const m = {}; for (const x of all) (m[f(x)] ||= []).push(x); return Object.fromEntries(Object.entries(m).map(([k, v]) => [k, agg(v)])); };
  return {
    all: agg(all), clean: agg(all.filter(x => !x.big)), big: agg(all.filter(x => x.big)),
    byVenue: by(x => x.called.kind === 'exchange' ? x.called.src : 'US books'), byMarket: by(x => x.label), bySide: by(x => x.side),
    recent: all.sort((a, b) => b.firstSeen - a.firstSeen).slice(0, 80).map(x => ({ ...x })),
  };
}

export function loadLedger(file) { try { return existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : { plays: {} }; } catch { return { plays: {} }; } }
