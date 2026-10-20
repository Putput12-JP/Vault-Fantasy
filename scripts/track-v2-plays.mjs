/* ════════════════════════════════════════════════════════════════════════
   VAULT · SHARP MONEY V2 PLAY LEDGER  (run by .github/workflows/update-sharp-money.yml on every refresh, after the poll)

   The V2 page (sharp-money/v2/index.html) calls a price a Play when it beats BOTH Pinnacle and the exchange by 2%+, the two references sit
   within 4 points, the edge is under 10% and the other side of the market is not also flagged. Until this script, nothing recorded those
   calls, so V2 had no record of its own. The rules are not copied here: sharp-money/v2/gates.js is the one module the page and this script
   both run (tests/v2_gates.test.mjs fails if they ever disagree).

     log     the first time a play shows, pregame, it is written ONCE: price, book, both reference fair prices and each edge, the time, the
             game or player key. Those fields live in `first` and are never touched again, even if the play later stops qualifying.
             A play is keyed on the pick (game or player, market, side, line), not on the book, so a better price at another book later
             does not become a second play.
     settle  props from the same box scores the prop ledger uses (data/nflverse_stats_<season>.json, ESPN overlay fills a week nflverse
             lacks; no box score 36h after kickoff = void). Games from the final score (the board's `final`, else
             data/exchange_edge_results.json; no final 72h after kickoff = void). Flat 1 unit at the stored price: win pays 1/price - 1.
     CLV     close fair of the side / stored price - 1, against the EXCHANGE close, which did not raise the call: props from
             prop_close_tape.json (mean of the Kalshi and Novig ladders at the exact line), games from data/book_tape (mean of the Kalshi
             and Novig moneyline mids; the Novig spread or total only at the exact line). The game tape stores a quote only when it changes, so the
             last row before kickoff stands as the close, provided the recorder wrote some row in the 2h before kickoff. A line that moved is
             never converted, the CLV is left empty. An exchange quote wider than 6 points is not a close.
   NBA props (nba-live/board.json, read from <dir>/nba_board.json) are logged the same way. They settle from ESPN's box score (the same summary the NBA
     ledger reads; a game that is not final, or whose box has under 300 player minutes, is not settled yet; a player with no minutes is void) and
     their CLV is the exchange read at the exact line from the last run before tip, kept on the row as `lastRead` and frozen as the close when the
     game starts. A read older than 3 hours, or at another line, is not a close.
   Sharp-account money is context only. It is not read here, does not rank a play and does not count toward an agree total.

   usage: node scripts/track-v2-plays.mjs --dir=sharp-out [--data=data] [--now=UNIX]
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, writeFileSync, existsSync, renameSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { actualOf, overlayEspn } from './track-prop-plays.mjs';

const HERE = dirname(fileURLToPath(import.meta.url)), ROOT = resolve(HERE, '..');
const gates = createRequire(import.meta.url)(resolve(ROOT, 'sharp-money', 'v2', 'gates.js'));
const { GATES, bookP, sideP, mean, tapeIndex } = gates;

export const PROP_VOID_AFTER = 36 * 3600, GAME_VOID_AFTER = 72 * 3600;
const CLOSE_AGE = 180 * 60;          // a prop exchange read older than this before kickoff is not a close (same as scripts/regrade_prop_clv.py)
const ALIVE_WINDOW = 2 * 3600;       // the game tape stores a quote only when it changes, so the last stored row stands as the close; it is only believed if the recorder wrote some row within this long of kickoff
const MAX_SPREAD = 0.06;             // an exchange quote wider than this says where it is for sale, not where the market is
const ALIAS = { WSH: 'WAS', LA: 'LAR', JAC: 'JAX', LVR: 'LV', OAK: 'LV' };
const al = t => ALIAS[t] || t;
const r3 = x => x == null ? null : +x.toFixed(3), r4 = x => x == null ? null : +x.toFixed(4);
export const SETTLED = new Set(['won', 'lost', 'push', 'void']);

/* ---- identity: one ledger row per pick, whatever book hangs it ---- */
export function ledgerKey(c) {
  if (c.kind === 'prop') return ['p', c.start, c.row.pid, c.row.mkt, c.row.line, c.side].join('|');
  if (c.kind === 'exch') return ['e', c.gk, c.m, c.side, c.edgeRow.line].join('|');       // c.side is the exchange row's label ("KU", "ORL -2.5", "Under 44.5")
  return ['b', c.gk, c.m, c.side, c.title].join('|');
}

/* What a settled game pick needs, in one shape for both game kinds: m (ml | sp | tot), side (home | away | over | under), hline (the HOME line,
   as the board stores it) or line (the total). */
function gamePick(c) {
  const g = c.game || {};
  if (c.kind === 'book') { const b = c.bookRow; return { m: b.m, side: b.side, hline: b.m === 'sp' ? b.hline : null, line: b.m === 'tot' ? b.line : null }; }
  const r = c.edgeRow, home = r.home, up = r.sg != null ? r.sg === 1 : null;                 // sg is 1 for the home / over contract, -1 for away / under
  if (r.m === 'ml') return { m: 'ml', side: (up != null ? up : r.label === home) ? 'home' : 'away', hline: null, line: null };
  if (r.m === 'sp') return { m: 'sp', side: (up != null ? up : String(r.label).split(' ')[0] === home) ? 'home' : 'away', hline: r.line, line: null };    // the live file's line is the home line
  return { m: 'tot', side: (up != null ? up : /^over/i.test(r.label)) ? 'over' : 'under', hline: null, line: r.line };
}

/* ---- log ---- */
export function logPlays(L, cands, nowS, { edgeGenerated = null, season = null, week = null, tier = 'play' } = {}) {
  const added = [];
  for (const c of cands) {
    if (c.tier !== tier || !c.start || c.start <= nowS) continue;
    const id = ledgerKey(c);
    if (L.plays[id]) continue;
    const refs = c.refs.map(r => ({ n: r.n, p: r4(r.p), edge: r4(r.edge) }));
    const first = {
      title: c.title, sub: c.sub, market: c.market, price: { am: c.price.am, p: r4(c.price.p), book: c.price.book },
      refs, worst: r4(c.worst), best: r4(c.best), fairMean: r4(mean(c.refs.map(r => r.p))), cautions: c.cautions,
      gates: { minEdge: GATES.MIN_EDGE, agree: GATES.AGREE, bigEdge: GATES.BIG_EDGE },
    };
    const row = { id, kind: c.kind, sport: c.sport, start: c.start, firstSeen: nowS, first, status: 'open' };
    if (c.kind === 'prop' && c.sport === 'nba') {
      row.prop = { season: 'nba', week: null, pid: c.row.pid, espnId: c.row.espnId, gid: c.row.game, name: c.row.name, team: c.row.team, pos: null, mkt: c.row.mkt, label: c.row.label, line: c.row.line, side: c.side };
    } else if (c.kind === 'prop') {
      row.prop = { season: String(season), week, pid: c.row.pid, name: c.row.name, team: c.row.team, pos: c.row.pos, mkt: c.row.mkt, label: c.row.label, line: c.row.line, side: c.side };
    } else {
      const g = c.game || {};
      row.game = { gk: c.gk, away: g.away ? g.away.abbr : c.edgeRow.away, home: g.home ? g.home.abbr : c.edgeRow.home, ...gamePick(c) };
      if (c.kind === 'exch') first.edgeGenerated = edgeGenerated;
    }
    L.plays[id] = row; added.push(id);
  }
  return added;
}

/* ---- close: the exchange read nearest the start that did not raise the call ---- */
// Props: prop_close_tape.json, the entry for this game, Kalshi and Novig P(over) at the exact line.
export function propClose(T, play) {
  const p = play.prop, list = (tapeIndex(T)[p.season + '|' + p.pid + '|' + p.mkt]) || [];
  const entry = list.find(v => Date.parse(v.commence) / 1000 === play.start);
  if (!entry || !entry.books) return null;
  const got = [];
  for (const b of ['Kalshi', 'Novig']) {
    const e = entry.books[b]; if (!e || e.t == null || e.t >= play.start || play.start - e.t > CLOSE_AGE) continue;
    const v = bookP(e, p.line); if (v != null) got.push([b, v, e.t]);
  }
  if (!got.length) return null;
  return { p: r4(sideP(mean(got.map(x => x[1])), p.side)), src: got.map(x => x[0]).join('+'), n: got.length, t: Math.max(...got.map(x => x[2])) };
}

// Games: data/book_tape rows of Kalshi and Novig. NFL rows carry away, home and start; the other sports carry the game key.
export function exchIndex(rows) {
  const by = new Map(), alive = [];
  for (const r of rows) {
    if (!r.bf) alive.push(r.t);                                  // any book, any game: proof the recorder was running then
    if ((r.book !== 'Novig' && r.book !== 'Kalshi') || r.bf) continue;
    const k = r.gk || (al(r.away) + '@' + al(r.home));
    (by.get(k) || by.set(k, []).get(k)).push(r);
  }
  for (const l of by.values()) l.sort((a, b) => a.t - b.t);
  by.alive = alive.sort((a, b) => a - b);
  return by;
}
export function gameClose(idx, play) {
  const g = play.game, rows = (idx.get(g.gk) || idx.get(al(g.away) + '@' + al(g.home)) || []).filter(r => Math.abs(r.start - play.start) < 6 * 3600);
  if (!(idx.alive || []).some(t => t < play.start && play.start - t <= ALIVE_WINDOW)) return null;       // recorder dark around kickoff: no close is claimed
  const last = {};                                             // book -> field -> latest [value, t] strictly before the start
  for (const r of rows) {
    if (r.t >= play.start) break;
    for (const f of ['px', 'nsp', 'ntot']) if (r[f]) ((last[r.book] ||= {})[f] = [r[f], r.t]);
  }
  const mid = q => { const bid = q[q.length - 2], ask = q[q.length - 1]; return ask >= bid && ask - bid <= MAX_SPREAD ? (bid + ask) / 2 : null; };
  const got = [];                                              // [book, chance the HOME side / the OVER wins, t]
  for (const b of ['Kalshi', 'Novig']) {
    const l = last[b]; if (!l) continue;
    if (g.m === 'ml' && l.px) { const m = mid(l.px[0]); if (m != null) got.push([b, m, l.px[1]]); }
    else if (g.m === 'sp' && b === 'Novig' && l.nsp && l.nsp[0][0] === g.hline) { const m = mid(l.nsp[0]); if (m != null) got.push([b, m, l.nsp[1]]); }
    else if (g.m === 'tot' && b === 'Novig' && l.ntot && l.ntot[0][0] === g.line) { const m = mid(l.ntot[0]); if (m != null) got.push([b, m, l.ntot[1]]); }
  }
  if (!got.length) return null;
  const home = mean(got.map(x => x[1])), side = g.side === 'home' || g.side === 'over' ? home : 1 - home;
  return { p: r4(side), src: got.map(x => x[0]).join('+'), n: got.length, t: Math.max(...got.map(x => x[2])) };
}

/* ---- NBA props: the box score, and the exchange read kept until tip ---- */
const NBA_BOX = { pts: ['points'], reb: ['rebounds'], ast: ['assists'], '3pm': ['threePointFieldGoalsMade'], stl: ['steals'], blk: ['blocks'],
  pra: ['points', 'rebounds', 'assists'], pr: ['points', 'rebounds'], pa: ['points', 'assists'], ra: ['rebounds', 'assists'] };
export const MIN_BOX_MINUTES = 300;      // a real game has 400+ player minutes; ESPN can flip a game to completed before the box is filled in (the NBA ledger uses the same cut)
export const NBA_SUMMARY = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=';
/* ESPN summary -> { espnId: {points, rebounds, ..., minutes} | null (did not play) }, or null when the game is not final or the box is not filled in. */
export function parseNbaBox(d) {
  try { if (!d.header.competitions[0].status.type.completed) return null; } catch { return null; }
  const out = {};
  for (const team of (d.boxscore && d.boxscore.players) || []) for (const block of (team.statistics || []).slice(0, 1)) {
    const keys = block.keys || [];
    for (const a of block.athletes || []) {
      const id = String(a.athlete.id);
      if (a.didNotPlay || !a.stats || !a.stats.length) { out[id] = null; continue; }
      const v = {};
      keys.forEach((key, i) => { const raw = String(a.stats[i]).split('-'); key.split('-').forEach((name, j) => { const n = parseFloat(raw[j]); if (Number.isFinite(n)) v[name] = n; }); });
      out[id] = v;
    }
  }
  return Object.values(out).reduce((s, v) => s + ((v && v.minutes) || 0), 0) < MIN_BOX_MINUTES ? null : out;
}
export async function fetchNbaBoxes(L, nowS, fetchJson = async u => { const r = await fetch(u); return r.ok ? r.json() : null; }) {
  const gids = [...new Set(Object.values(L.plays).filter(P => P.status === 'open' && P.kind === 'prop' && P.sport === 'nba' && nowS >= P.start + 3 * 3600).map(P => P.prop.gid))], boxes = {};
  for (const g of gids) { try { const b = parseNbaBox(await fetchJson(NBA_SUMMARY + g)); if (b) boxes[g] = b; } catch { /* not final yet, or ESPN is down: tried again next run */ } }
  return boxes;
}
export const nbaActual = (box, espnId, mkt) => {
  const v = box && box[String(espnId)], ks = NBA_BOX[mkt];
  return !v || !ks || ks.some(k => v[k] == null) ? null : ks.reduce((s, k) => s + v[k], 0);
};
/* Each run before tip keeps the exchange's read at the play's exact line on the row; the last one is the close once the game starts. */
export function noteNbaReads(L, N, nowS) {
  let n = 0;
  for (const P of Object.values(L.plays)) {
    if (P.status !== 'open' || P.kind !== 'prop' || P.sport !== 'nba' || nowS >= P.start) continue;
    const r = gates.nbaExchangeNow({ N, now: nowS }, P.prop.espnId, P.prop.mkt, P.prop.line);
    if (!r) continue;
    P.lastRead = { p: r4(P.prop.side === 'over' ? r.over : 1 - r.over), src: r.src, n: r.n, t: nowS }; n++;
  }
  return n;
}
export function nbaClose(P) {
  const r = P.lastRead;
  return r && r.t < P.start && P.start - r.t <= CLOSE_AGE ? { p: r.p, src: r.src, n: r.n, t: r.t } : null;
}

/* ---- settle ---- */
export const payout = p => 1 / p - 1;
function finish(P, status, nowS) {
  P.status = status; P.settledAt = nowS; if (P.close == null) P.close = false;      // false = settled with no exchange close; it is not looked for again
  P.units = status === 'won' ? r3(payout(P.first.price.p)) : status === 'lost' ? -1 : 0;
}
export function settlePlays(L, { statsFor, finals, T, exch, nowS, nbaBoxes = {} }) {
  const out = { settled: 0, void: 0, closed: 0 };
  for (const P of Object.values(L.plays)) {
    if (P.status !== 'open' && P.close !== undefined) continue;
    if (nowS < P.start) continue;
    // close first: frozen the first time the exchange has a read, tried again each run until the play settles, then left as it is
    if (P.close == null && P.close !== false) {
      const cl = P.kind === 'prop' ? (P.sport === 'nba' ? nbaClose(P) : propClose(T, P)) : exch ? gameClose(exch(P.sport), P) : null;
      if (cl) { P.close = cl; P.clv = r4(cl.p / P.first.price.p - 1); out.closed++; }
    }
    if (P.status !== 'open') continue;
    if (P.kind === 'prop' && P.sport === 'nba') {
      if (nowS < P.start + 3 * 3600) continue;
      const box = nbaBoxes[P.prop.gid];
      if (!box) { if (nowS > P.start + PROP_VOID_AFTER) { finish(P, 'void', nowS); out.void++; } continue; }
      const a = nbaActual(box, P.prop.espnId, P.prop.mkt);
      if (a == null) { finish(P, 'void', nowS); out.void++; continue; }          // did not play, or the stat is not in the box: the prop is void
      P.actual = a;
      finish(P, a === P.prop.line ? 'push' : (P.prop.side === 'over' ? a > P.prop.line : a < P.prop.line) ? 'won' : 'lost', nowS); out.settled++;
    } else if (P.kind === 'prop') {
      if (nowS < P.start + 3 * 3600) continue;
      const a = actualOf(statsFor(P), P.prop.name, P.prop.week, P.prop.mkt);
      if (!a.has) { if (nowS > P.start + PROP_VOID_AFTER) { finish(P, 'void', nowS); out.void++; } continue; }
      P.actual = a.val;
      finish(P, a.val === P.prop.line ? 'push' : (P.prop.side === 'over' ? a.val > P.prop.line : a.val < P.prop.line) ? 'won' : 'lost', nowS); out.settled++;
    } else {
      const f = finals(P);
      if (!f) { if (nowS > P.start + GAME_VOID_AFTER) { finish(P, 'void', nowS); out.void++; } continue; }
      const { home, away } = f, g = P.game; P.final = { away, home };
      let v;                                                   // 1 win, -1 loss, 0 push; the same arithmetic as gradePicks in fetch-sharp-money.mjs
      if (g.m === 'ml') v = home === away ? 0 : (home > away) === (g.side === 'home') ? 1 : -1;
      else if (g.m === 'sp') { const d = home + g.hline - away, r = g.side === 'home' ? d : -d; v = r > 0 ? 1 : r < 0 ? -1 : 0; }
      else { const d = home + away - g.line, r = g.side === 'over' ? d : -d; v = r > 0 ? 1 : r < 0 ? -1 : 0; }
      finish(P, v === 0 ? 'push' : v > 0 ? 'won' : 'lost', nowS); out.settled++;
    }
  }
  return out;
}

/* Final score of a game play: the board's own `final` while the game is on it, else the stored results (gk, else teams and start). */
export function makeFinals(D, results) {
  const byKey = Object.fromEntries((D && D.games || []).filter(g => g.final).map(g => [g.key, g.final]));
  return P => {
    const g = P.game; if (byKey[g.gk]) return byKey[g.gk];
    const r = results && (results[g.gk] || Object.values(results).find(x => x.sport === P.sport && al(x.ah) === al(g.away) && al(x.hh) === al(g.home) && Math.abs(x.start - P.start) < 6 * 3600));
    return r ? { home: r.home, away: r.away } : null;
  };
}

/* ---- aggregates (the page recomputes these from the rows; this is for the run log and the tests) ---- */
export function summary(L) {
  const xs = Object.values(L.plays), done = xs.filter(x => x.status === 'won' || x.status === 'lost'), cl = xs.filter(x => x.clv != null);
  return { n: xs.length, open: xs.filter(x => x.status === 'open').length, w: done.filter(x => x.status === 'won').length, l: done.filter(x => x.status === 'lost').length,
    push: xs.filter(x => x.status === 'push').length, void: xs.filter(x => x.status === 'void').length, units: r3(done.reduce((s, x) => s + x.units, 0)), clvN: cl.length, clv: cl.length ? r4(mean(cl.map(x => x.clv))) : null };
}

/* ---- run ---- */
const rj = f => { try { return JSON.parse(readFileSync(f, 'utf8')); } catch { return null; } };
export function loadLedger(file) {
  if (!existsSync(file)) return { v: 1, plays: {} };
  const L = JSON.parse(readFileSync(file, 'utf8'));            // a ledger that exists but does not parse stops the run; it is never replaced by an empty one
  if (!L || typeof L.plays !== 'object') throw new Error(file + ' has no plays object');
  return L;
}
function readTape(dataDir, sport) {
  const dir = resolve(dataDir, 'book_tape', sport), rows = [];
  if (!existsSync(dir)) return rows;
  for (const f of readdirSync(dir).filter(n => n.endsWith('.jsonl') && n !== 'backfill.jsonl').sort())
    for (const l of readFileSync(resolve(dir, f), 'utf8').split('\n')) { if (!l) continue; try { rows.push(JSON.parse(l)); } catch { /* a torn last line */ } }
  return rows;
}

export const ledgerFile = tier => tier === 'play' ? 'v2_plays.json' : tier === 'watch' ? 'v2_watch.json' : 'v2_passed.json';

export function run({ dir, dataDir, nowS, tier = 'play', nbaBoxes = {} }) {
  const D = rj(resolve(dir, 'data.json')), P = rj(resolve(dir, 'props.json')), T = rj(resolve(dir, 'prop_close_tape.json')), E = rj(resolve(dataDir, 'exchange_edge_live.json')), N = rj(resolve(dir, 'nba_board.json'));
  if (!D) throw new Error('no data.json in ' + dir);
  const file = resolve(dir, ledgerFile(tier)), L = loadLedger(file);
  // An exchange list older than a reference may be is not a price (gates.js MAX_AGE); the page has no such check, so a play off a stale list is not logged.
  const eg = E && E.generated ? Date.parse(E.generated) / 1000 : null;
  const Eok = E && eg != null && nowS - eg <= GATES.MAX_AGE ? E : null;
  const built = gates.build({ D, P, T, E: Eok, N, now: nowS });
  const cand = tier === 'play' ? built.cand : gates.stance(built.cand);        // Watch and Passed keep one side per market, so a bet is never logged as both Over and Under
  const season = P && P.props ? P.props.season : null, week = P && P.props ? P.props.week : null;
  const added = logPlays(L, cand, nowS, { edgeGenerated: eg, season, week, tier });
  const seasons = [...new Set(Object.values(L.plays).filter(x => x.kind === 'prop' && x.sport !== 'nba').map(x => x.prop.season))];
  const stats = {};
  for (const s of seasons) stats[s] = overlayEspn(rj(resolve(dataDir, `nflverse_stats_${s}.json`)), rj(resolve(dataDir, `espn_player_stats_${s}.json`)));
  const tapes = {}, results = rj(resolve(dataDir, 'exchange_edge_results.json'));
  if (N) noteNbaReads(L, N, nowS);
  const out = settlePlays(L, { nbaBoxes,
    statsFor: P => stats[P.prop.season], finals: makeFinals(D, results), T, nowS,
    exch: sport => tapes[sport] ||= exchIndex(readTape(dataDir, sport)),
  });
  return { L, added, out, skippedExch: E && !Eok, file };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const arg = n => (process.argv.find(a => a.startsWith('--' + n + '=')) || '').split('=')[1];
  const dir = resolve(arg('dir') || 'sharp-out'), dataDir = resolve(arg('data') || resolve(ROOT, 'data')), nowS = +arg('now') || Math.floor(Date.now() / 1000);
  const tier = arg('tier') || 'play';
  if (!['play', 'watch', 'pass'].includes(tier)) throw new Error('--tier must be play, watch or pass');
  const nbaBoxes = await fetchNbaBoxes(loadLedger(resolve(dir, ledgerFile(tier))), nowS);      // plays logged in an earlier run; one logged this run has not started
  const { L, added, out, skippedExch, file } = run({ dir, dataDir, nowS, tier, nbaBoxes });
  L.updated = nowS;
  writeFileSync(file + '.tmp', JSON.stringify(L)); renameSync(file + '.tmp', file);
  const s = summary(L);
  console.log(`v2 plays: ${added.length} new, ${out.settled} settled, ${out.void} void, ${out.closed} closes frozen; ledger ${s.n} plays (${s.open} open, ${s.w}-${s.l}, ${s.push} push, ${s.void} void, ${s.units}u, CLV on ${s.clvN})${skippedExch ? '; exchange list too old, game plays off it not logged this run' : ''}`);
}
