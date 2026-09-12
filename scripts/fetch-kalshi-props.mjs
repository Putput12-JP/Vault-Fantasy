#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · KALSHI PLAYER PROPS  →  data/kalshi_props.json

   Pulls NFL player-prop markets from Kalshi, a CFTC-regulated prediction
   exchange, and writes a de-vigged **sharp fair probability** per player /
   market / strike. This is the "sharp anchor": a real-money, two-sided price
   the Betting Edge Board and build_best_bets can measure a Vault projection
   edge AGAINST, the way a sharp shop does — so a graded edge that the exchange
   flatly disagrees with gets caught before it ships.

   Keyless, public, no credits — same free posture as fetch-kalshi.mjs (game
   markets). Prophet X / Novig would deepen the anchor but sit behind an auth'd
   partner API, so they are a paid-aggregator follow-up, not a keyless pull.

   Endpoint: https://api.elections.kalshi.com/trade-api/v2 (per-prop series).
   Each series is one stat; each event is one game; each market is a single
   player at a single threshold — "Justin Jefferson: 6+" carries floor_strike
   5.5, so yes = P(value > 5.5) = P(over a 5.5 book line). We take the two-sided
   mid (yes_bid + (1 − no_bid))/2, same as the game-markets fetcher, and keep the
   spread + open interest so the consumer can trust only LIQUID markets (a thin
   exchange market is worse than none — never gate a Vault grade on 2 contracts).

   Output shape (read by build_best_bets.mjs → sharpFairFor):
     { source, generated, season, week, count,
       markets: { <vaultMarketKey>: {
         "<nkey player>": [ { k:<floor_strike>, fair:<P(over strike)>,
                              oi:<contracts>, spr:<yes bid/ask spread $> }, … ] } } }

   Player keys use the SAME normalization as build_best_bets.mjs (nkey:
   lowercase, strip everything but a-z), so the join is exact.

   Usage:
     node scripts/fetch-kalshi-props.mjs                 # fetch, write data/kalshi_props.json
     node scripts/fetch-kalshi-props.mjs --dry           # fetch, print summary, write nothing
     node scripts/fetch-kalshi-props.mjs --out=path.json # custom output
   ════════════════════════════════════════════════════════════════════════ */
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ARG = Object.fromEntries(process.argv.slice(2).map(a => { const [k, v] = a.replace(/^--/, '').split('='); return [k, v ?? true]; }));
const DRY = !!ARG.dry;
const OUT = ARG.out ? resolve(process.cwd(), ARG.out) : resolve(HERE, '..', 'data', 'kalshi_props.json');
const BASE = 'https://api.elections.kalshi.com/trade-api/v2';
const UA = { 'User-Agent': 'VaultFantasy/1.0 (+vaultfantasy.com)', 'Accept': 'application/json' };
// A prop market wider than this is too thin/stale to store at all (a dead
// exchange market quotes ~1¢/99¢). The strict liquidity trust bar lives in the
// consumer (build_best_bets), which requires a tighter spread + real OI before
// it will fade a Vault grade — here we just drop the truly dead quotes.
const MAX_SPREAD = 0.20;
const log = (...a) => console.log('[kalshi-props]', ...a);

// Kalshi prop series → Vault market key (the keys build_best_bets / prop_model use).
// Only the series that returned open events; TD series aren't posted keyless yet.
const SERIES = {
  KXNFLRSHATT: 'rush_att', KXNFLRSHYDS: 'rush_yd', KXNFLRECYDS: 'rec_yd',
  KXNFLREC: 'rec', KXNFLPASSYDS: 'pass_yd', KXNFLPASSATT: 'pass_att',
  KXNFLPASSINT: 'pass_int',
};

const num = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };
const fp = v => Math.round(num(v) || 0);
// Same normalization as build_best_bets.mjs nkey, so player keys join exactly.
const nkey = s => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z]/g, '');

async function getJSON(url) {
  const r = await fetch(url, { headers: UA });
  if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + url);
  return r.json();
}

// yes price for a market: mid of (yes_bid, yes_ask), yes_ask = 1 − no_bid.
// Identical to fetch-kalshi.mjs yesQuote — one definition of "the price" across
// both feeds. Returns { fair, spread } in dollars, or null when not two-sided.
function yesQuote(m) {
  const yb = num(m.yes_bid_dollars);
  const nb = num(m.no_bid_dollars);
  const ya = nb != null ? 1 - nb : null;
  if (yb == null || ya == null) return null;
  return { fair: (yb + ya) / 2, spread: Math.abs(ya - yb) };
}

// Follow the cursor to collect all open events (with nested markets) for a series.
async function fetchSeries(series) {
  const out = [];
  let cursor = '';
  for (let page = 0; page < 25; page++) {
    const u = new URL(BASE + '/events');
    u.searchParams.set('series_ticker', series);
    u.searchParams.set('status', 'open');
    u.searchParams.set('with_nested_markets', 'true');
    u.searchParams.set('limit', '200');
    if (cursor) u.searchParams.set('cursor', cursor);
    const j = await getJSON(u.toString());
    for (const ev of (j.events || [])) for (const m of (ev.markets || [])) out.push(m);
    cursor = j.cursor || '';
    if (!cursor) break;
  }
  return out;
}

(async () => {
  const markets = {};
  let kept = 0, dropped = 0;
  for (const [series, mk] of Object.entries(SERIES)) {
    let ms;
    try { ms = await fetchSeries(series); }
    catch (e) { log(series, 'fetch failed:', e.message); continue; }
    const bucket = (markets[mk] = markets[mk] || {});
    let nk = 0;
    for (const m of ms) {
      const q = yesQuote(m);
      const strike = num(m.floor_strike);
      if (!q || strike == null || q.spread > MAX_SPREAD) { dropped++; continue; }
      const title = m.yes_sub_title || m.no_sub_title || '';
      const key = nkey(title.replace(/:.*/, ''));
      if (!key) { dropped++; continue; }
      const row = {
        k: strike,
        fair: +q.fair.toFixed(4),
        oi: fp(m.open_interest_fp != null ? m.open_interest_fp : m.open_interest),
        spr: +q.spread.toFixed(3),
      };
      (bucket[key] = bucket[key] || []).push(row);
      kept++; nk++;
    }
    // sort each player's ladder by strike for stable, inspectable output
    for (const k in bucket) bucket[k].sort((a, b) => a.k - b.k);
    log(`${series.padEnd(14)} ${mk.padEnd(9)} kept ${String(nk).padStart(4)} of ${String(ms.length).padStart(4)}`);
  }

  const nPlayers = new Set();
  for (const mk in markets) for (const k in markets[mk]) nPlayers.add(k);
  const payload = {
    source: 'kalshi-props',
    series: Object.keys(SERIES).join('+'),
    generated: new Date().toISOString(),
    count: kept,
    markets,
  };
  log(`${kept} markets kept (${dropped} dropped) · ${Object.keys(markets).length} stats · ${nPlayers.size} players`);
  // spot-check the deepest few so a bad pull is obvious in the log
  const flat = [];
  for (const mk in markets) for (const k in markets[mk]) for (const r of markets[mk][k]) flat.push({ mk, k, ...r });
  flat.sort((a, b) => b.oi - a.oi).slice(0, 5).forEach(r => log(`  deep: ${r.mk} ${r.k} ${(r.fair * 100).toFixed(0)}%  OI ${r.oi.toLocaleString()}  spr ${r.spr}`));
  if (DRY) { log('--dry: not written'); return; }
  writeFileSync(OUT, JSON.stringify(payload));
  log('wrote ' + OUT);
})();
