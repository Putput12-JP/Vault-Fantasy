#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · NOVIG PLAYER PROPS  →  data/novig_props.json

   Novig is a peer-to-peer exchange with a public, keyless, edge-cached read API
   (docs.novig.com). An NFL game carries ~550 markets, most of them player props,
   each with its own order book. One book call per market, so we only read the
   ones that can be compared to something: a (player, stat) the lineup feed has
   a line for, at the 1-3 strikes nearest that line.

   Output mirrors data/kalshi_props.json so the same joins work:
     { source, generated, count, markets: { <vaultKey>: { "<nkey>": [ row, … ] } } }
   row = { k, ob, oa, ub, ua, mid, fair, spr, depth, rest, t, ev, id }
     ob/oa  best bid / ask to buy OVER (probabilities, 0-1)
     ub/ua  best bid / ask to buy UNDER
     mid    over-side midpoint (null when the quote is wider than TIGHT)
     fair   = mid: Novig's own two-sided read of P(over k). Not de-vigged against
            another venue: an exchange mid carries no vig to remove.
     depth  $ resting within 3¢ of the best price, both sides; rest = all resting $
     t      unix seconds the book was read (rows age out, see MAX_AGE)

   Pregame props carry no taker fee (`charged: WHEN_LIVE`), so ask IS the price
   you pay. If a market ever reports charged ALWAYS the fee is recorded as `fee`
   so the consumer can net it.

   Units: 1 contract pays 1 cent; $ = price * qty / 100. A bid on outcome A at p
   is the same liquidity as an ask on outcome B at 1 - p.

   Usage:
     node scripts/fetch-novig-props.mjs                     # data/lineup-feed.json -> data/novig_props.json
     node scripts/fetch-novig-props.mjs --out=x.json --budget=150   # seconds of polling
     node scripts/fetch-novig-props.mjs --dry
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ARG = Object.fromEntries(process.argv.slice(2).map(a => { const [k, v] = a.replace(/^--/, '').split('='); return [k, v ?? true]; }));
const ROOT = resolve(HERE, '..');
const OUT = ARG.out ? resolve(process.cwd(), ARG.out) : resolve(ROOT, 'data', 'novig_props.json');
const FEED = ARG.feed ? resolve(process.cwd(), ARG.feed) : resolve(ROOT, 'data', 'lineup-feed.json');
const BUDGET_MS = (+ARG.budget || 150) * 1000;
const DRY = !!ARG.dry;
const N = 'https://api.novig.com/v3/public/catalog';
const PACE_MS = 300;             // ~3 req/s; 4 parallel streams were throttled to 3 of 15 games in the Sharp Money poller
const CLOSE = 0.03;              // depth counts orders within 3 cents of the best
const TIGHT = 0.10;              // a quote wider than this says nothing about the price
const MAX_AGE = 45 * 60;         // a row older than this is dropped from the output (the board stops trusting a row at 30 min)
const AHEAD_DAYS = 6;
const STRIKES = 2;               // strikes per (player, stat), nearest the market line
const log = (...a) => console.log('[novig-props]', ...a);

// Novig marketType -> Vault market key (the keys lineup-feed / kalshi_props use).
const MKT = {
  RECEIVING_YARDS: 'rec_yd', RECEPTIONS: 'rec', RUSHING_YARDS: 'rush_yd', RUSHING_ATTEMPTS: 'rush_att',
  PASSING_YARDS: 'pass_yd', PASSING_TOUCHDOWNS: 'pass_td', PASSING_ATTEMPTS: 'pass_att',
  PASSING_COMPLETIONS: 'pass_cmp', INTERCEPTIONS_THROWN: 'pass_int',
  PASSING_AND_RUSHING_YARDS: 'pass_rush_yd', RUSHING_AND_RECEIVING_YARDS: 'rush_rec_yd',
  LONGEST_RECEPTION: 'long_rec', LONGEST_RUSH: 'long_rush', LONGEST_COMPLETION: 'long_pass',
  FIELD_GOALS_MADE: 'fg_made', KICKING_POINTS: 'kick_pts', TOUCHDOWNS: 'anytime_td',
};

// Same normalisation as fetch-kalshi-props / build_best_bets, plus generational suffixes so
// "Marvin Harrison Jr." joins "Marvin Harrison".
const prob = a => a < 0 ? -a / (-a + 100) : 100 / (a + 100);
const nkey = s => String(s || '').toLowerCase().replace(/\b(jr|sr|ii|iii|iv|v)\b\.?/g, '').replace(/[^a-z]/g, '');

let last = 0, pauseUntil = 0;
async function get(path, tries = 4) {
  for (let i = 0; i < tries; i++) {
    const wait = Math.max(last + PACE_MS, pauseUntil) - Date.now();
    if (wait > 0) await new Promise(r => setTimeout(r, wait));
    last = Date.now();
    try {
      const r = await fetch(N + path, { headers: { accept: 'application/json', 'user-agent': 'VaultFantasy/1.0 (+vaultfantasy.com)' }, signal: AbortSignal.timeout(20000) });
      if (r.status === 429) { pauseUntil = Date.now() + (+r.headers.get('retry-after') || 3) * 1000 + 500; continue; }
      if (!r.ok) return null;
      return await r.json();
    } catch { /* retry */ }
  }
  return null;
}
async function pages(path, cap = 6) {
  const out = []; let after = null;
  for (let i = 0; i < cap; i++) {
    const d = await get(path + (after ? `&after=${after}` : ''));
    if (!d) break;
    out.push(...(d.items || []));
    after = d.next;
    if (!after || !(d.items || []).length) break;
  }
  return out;
}

const dollars = (p, q) => +p * q / 100;
function readBook(mk, book) {
  if ((mk.outcomes || []).length !== 2) return null;
  const orders = book.orders || {};
  const L = mk.outcomes.map(o => (orders[o.outcomeId] || []).slice().sort((a, b) => b.price - a.price));
  const best = L.map(l => l.length ? +l[0].price : null);
  const depth = L.reduce((s, l, i) => s + (best[i] == null ? 0 : l.filter(x => best[i] - +x.price <= CLOSE + 1e-9).reduce((t, x) => t + dollars(x.price, x.qty), 0)), 0);
  const rest = L.reduce((s, l) => s + l.reduce((t, x) => t + dollars(x.price, x.qty), 0), 0);
  const ob = best[0], ub = best[1];
  const oa = ub == null ? null : 1 - ub, ua = ob == null ? null : 1 - ob;
  let mid = null;
  if (ob != null && oa != null && ob > 0 && ob <= oa && oa < 1 && oa - ob <= TIGHT + 1e-9) mid = (ob + oa) / 2;
  const r3 = x => x == null ? null : Math.round(x * 1000) / 1000;
  return { ob: r3(ob), oa: r3(oa), ub: r3(ub), ua: r3(ua), mid: r3(mid), fair: r3(mid), spr: ob != null && oa != null ? r3(oa - ob) : null, depth: Math.round(depth), rest: Math.round(rest) };
}

async function main() {
  const t0 = Date.now();
  const feed = JSON.parse(readFileSync(FEED, 'utf8'));
  // (nkey, vaultKey) -> the market's reference line, from the lineup feed
  const want = new Map(), pinFair = new Map();   // pinFair: P(over) no-vig at Pinnacle's line, to spot which Novig props are worth refreshing first
  for (const p of Object.values(feed.vegas_player_props || {})) {
    for (const [m, l] of Object.entries(p.lines || {})) {
      const qs = (l.quotes || []).filter(q => q.line != null);
      const pin = qs.find(q => q.book === 'Pinnacle');
      const ref = pin ? pin.line : l.line;
      if (ref == null) continue;
      if (!pin && qs.length < 3) continue;            // nothing sharp to compare against: not worth a book call
      if (/^(long_|fg_|kick_|sacks|tackles)/.test(m)) continue;
      want.set(nkey(p.name) + '|' + m, ref);
      if (pin) { const po = prob(pin.over), pu = prob(pin.under); pinFair.set(nkey(p.name) + '|' + m, po / (po + pu)); }
    }
  }
  log('wanted', want.size, 'player-stat pairs');

  let prev = {};
  if (existsSync(OUT)) { try { prev = JSON.parse(readFileSync(OUT, 'utf8')).markets || {}; } catch { /* fresh start */ } }
  const lastRead = new Map();   // marketId -> t of the previous read
  const hot = new Set();        // marketIds that last showed a gap or an edge at Pinnacle's own line: these are the ones the Props page is showing
  for (const [vk, byP] of Object.entries(prev)) for (const [nk, rows] of Object.entries(byP)) for (const r of rows) {
    if (!r.id) continue;
    lastRead.set(r.id, r.t || 0);
    const f = pinFair.get(nk + '|' + vk);
    if (f == null || r.k !== want.get(nk + '|' + vk)) continue;
    const evO = r.oa ? f / r.oa - 1 : -1, evU = r.ua ? (1 - f) / r.ua - 1 : -1;
    if ((r.mid != null && Math.abs(r.mid - f) >= 0.025) || evO >= 0.02 || evU >= 0.02) hot.add(r.id);
  }

  const evs = (await pages('/events?league=NFL&limit=200')).filter(e => / @ /.test(e.description || '') && /^OPEN/.test(e.status) && e.startsTs < Date.now() + AHEAD_DAYS * 864e5);
  log('events', evs.length);
  const queue = [];
  for (const e of evs) {
    const mks = await pages(`/markets?event=${e.eventId}&limit=1000`);
    const by = new Map();   // nkey|vaultKey -> markets
    for (const mk of mks) {
      const vk = MKT[mk.marketType]; if (!vk || mk.status !== 'OPEN') continue;
      const m = /^(.+?)\s+(-?[\d.]+)\s+[A-Z_]+$/.exec(mk.description || ''); if (!m) continue;
      const key = nkey(m[1]) + '|' + vk;
      if (!want.has(key)) continue;
      (by.get(key) || by.set(key, []).get(key)).push({ mk, k: +mk.strike, name: m[1], vk, nk: nkey(m[1]), start: e.startsTs });
    }
    for (const [key, list] of by) {
      const ref = want.get(key);
      const near = vk => list.sort((a, b) => Math.abs(a.k - ref) - Math.abs(b.k - ref)).slice(0, vk === 'anytime_td' ? 1 : STRIKES);
      queue.push(...near(list[0].vk));
    }
  }
  // oldest read first, so a time-boxed run still rotates through everything
  // order: (1) props that were showing a gap or edge last read, (2) the main line over alt strikes, (3) oldest read first
  const rank = q => [hot.has(q.mk.marketId) ? 0 : 1, q.k === want.get(q.nk + '|' + q.vk) ? 0 : 1];
  queue.sort((a, b) => { const ra = rank(a), rb = rank(b); return ra[0] - rb[0] || ra[1] - rb[1] || (lastRead.get(a.mk.marketId) || 0) - (lastRead.get(b.mk.marketId) || 0) || a.start - b.start; });
  log('hot (last showed a gap or edge):', [...hot].length);
  log('markets to read', queue.length, 'budget', BUDGET_MS / 1000 + 's');

  const now = Math.floor(Date.now() / 1000);
  const fresh = {};   // vk -> nk -> rows
  let read = 0;
  for (const q of queue) {
    if (Date.now() - t0 > BUDGET_MS) break;
    const book = await get(`/markets/${q.mk.marketId}/book`);
    if (!book) continue;
    const r = readBook(q.mk, book);
    if (!r || (r.ob == null && r.ub == null)) continue;
    read++;
    const row = { k: q.k, ...r, t: now, id: q.mk.marketId, name: q.name };
    if (q.mk.fee?.charged === 'ALWAYS') row.fee = +q.mk.fee.coefficient;
    ((fresh[q.vk] ||= {})[q.nk] ||= []).push(row);
  }
  log('read', read, 'books in', Math.round((Date.now() - t0) / 1000) + 's');

  // merge: fresh rows replace the same marketId; unread rows survive until MAX_AGE
  const markets = {};
  const put = (vk, nk, row) => { const a = ((markets[vk] ||= {})[nk] ||= []); const i = a.findIndex(x => x.id === row.id); if (i >= 0) a[i] = row; else a.push(row); };
  for (const [vk, byP] of Object.entries(prev)) for (const [nk, rows] of Object.entries(byP)) for (const r of rows) if (now - (r.t || 0) <= MAX_AGE) put(vk, nk, r);
  for (const [vk, byP] of Object.entries(fresh)) for (const [nk, rows] of Object.entries(byP)) for (const r of rows) put(vk, nk, r);
  let count = 0;
  for (const byP of Object.values(markets)) for (const rows of Object.values(byP)) { rows.sort((a, b) => a.k - b.k); count += rows.length; }

  const out = { source: 'novig-props', generated: new Date().toISOString(), count, read, queued: queue.length, markets };
  if (DRY) { log('dry run', count, 'rows'); return; }
  writeFileSync(OUT, JSON.stringify(out));
  log('wrote', OUT, count, 'rows');
}
main().catch(e => { console.error('[novig-props] failed:', e.message); process.exit(1); });
