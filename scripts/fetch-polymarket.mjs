#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · POLYMARKET GAME MARKETS  →  data/polymarket.json

   Pulls NFL game money flow from Polymarket, a real-money prediction exchange,
   and writes a per-game implied win% plus REAL-DOLLAR flow (traded volume, 24h
   volume, open interest) so the Betting tab's Game Markets board can show a
   second, independent real-money read next to Kalshi — the handle-style signal
   sportsbook line feeds never carry.

   Polymarket vs Kalshi: same idea, deeper on marquee game markets ($50k–190k
   traded on top Week-1 games vs Kalshi's contract counts), and priced in DOLLARS
   (not $1 contracts), so the flow numbers here are dollars. The two exchanges
   agreeing is a strong signal; disagreeing is worth surfacing.

   Keyless, public, no credits — same free posture as fetch-kalshi.mjs. Source:
   the Gamma API (https://gamma-api.polymarket.com). NFL game events carry a slug
   `nfl-<away>-<home>-<YYYY-MM-DD>` and ~380 sub-markets each; the money lives in
   a handful (main moneyline / spread / total). We take the main MONEYLINE market
   (two team outcomes, deepest volume, no halves/quarters/props) for the implied
   win%, and the EVENT-level totals for flow (the whole game's money at stake).

   Output shape (mirrors data/prediction_markets.json so the board's flow strip
   logic is shared):
     { source, generated, count, games: {
         "AWY@HOM": { away, home, ml:{ away:<prob>, home:<prob> },
                      flow:{ vol, vol24, oi },   // DOLLARS (rounded)
                      liq, close } } }

   Usage:
     node scripts/fetch-polymarket.mjs                 # write data/polymarket.json
     node scripts/fetch-polymarket.mjs --dry           # summarize, write nothing
     node scripts/fetch-polymarket.mjs --out=path.json # custom output
   ════════════════════════════════════════════════════════════════════════ */
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ARG = Object.fromEntries(process.argv.slice(2).map(a => { const [k, v] = a.replace(/^--/, '').split('='); return [k, v ?? true]; }));
const DRY = !!ARG.dry;
const OUT = ARG.out ? resolve(process.cwd(), ARG.out) : resolve(HERE, '..', 'data', 'polymarket.json');
const GAMMA = 'https://gamma-api.polymarket.com';
const UA = { 'User-Agent': 'VaultFantasy/1.0 (+vaultfantasy.com)', 'Accept': 'application/json' };
const MIN_VOL = 1000;          // skip near-untraded events (future weeks fill in late)
const log = (...a) => console.log('[polymarket]', ...a);

// Polymarket slug code → Vault team code (most already match).
const ALIAS = { WSH: 'WAS', JAC: 'JAX', LVR: 'LV', LA: 'LAR', SFO: 'SF', GBP: 'GB', KAN: 'KC', NWE: 'NE', NOR: 'NO', TAM: 'TB', ARZ: 'ARI', CLV: 'CLE', BLT: 'BAL', HST: 'HOU' };
const code = a => { const u = String(a || '').toUpperCase(); return ALIAS[u] || u; };

const num = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };
const jparse = s => { try { return typeof s === 'string' ? JSON.parse(s) : (s || null); } catch (e) { return null; } };
const GAME_RE = /^nfl-([a-z]{2,3})-([a-z]{2,3})-(\d{4}-\d{2}-\d{2})$/;

async function getJSON(url) {
  const r = await fetch(url, { headers: UA });
  if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + url);
  return r.json();
}

// All open events under the NFL tag (paged). Futures/novelty events come back
// too; the game-slug filter keeps only head-to-head games.
async function fetchNflEvents() {
  const out = [];
  for (let off = 0; off < 800; off += 100) {
    let page;
    try { page = await getJSON(`${GAMMA}/events?closed=false&limit=100&offset=${off}&tag_slug=nfl`); }
    catch (e) { break; }
    if (!Array.isArray(page) || !page.length) break;
    out.push(...page);
    if (page.length < 100) break;
  }
  return out;
}

// Net AGGRESSOR (taker) money into the home side over the last 24h, in dollars.
// Polymarket is a matched exchange, so total volume can't be split by side — but
// the taker feed marks each aggressor trade's side + outcome, so BUY(home) and
// SELL(away) are home-bullish, the reverse home-bearish. Summing signed dollars
// (size × price) gives a real "which way is money actively pushing" read that
// total volume cannot. + = into home, − = into away. Returns { net, n } or null.
const DAY = 86400;
async function takerFlow(conditionId, homeName, awayName) {
  if (!conditionId) return null;
  const cutoff = Math.floor(Date.now() / 1000) - DAY;
  let net = 0, n = 0, offset = 0;
  for (let page = 0; page < 8; page++) {          // cap ~4k recent trades/game
    let rows;
    try {
      rows = await getJSON(`https://data-api.polymarket.com/trades?market=${conditionId}&takerOnly=true&limit=500&offset=${offset}`);
    } catch (e) { break; }
    if (!Array.isArray(rows) || !rows.length) break;
    let hitOld = false;
    for (const t of rows) {
      const ts = num(t.timestamp);
      if (ts != null && ts < cutoff) { hitOld = true; continue; }   // feed is newest-first
      const price = num(t.price), size = num(t.size);
      if (price == null || size == null) continue;
      const nm = String(t.outcome || '').toLowerCase();
      const isHome = homeName && nm && homeName.includes(nm);
      const isAway = awayName && nm && awayName.includes(nm);
      if (!isHome && !isAway) continue;
      const buy = String(t.side || '').toUpperCase() === 'BUY';
      const homeBullish = (isHome && buy) || (isAway && !buy);       // buy home / sell away
      net += (homeBullish ? 1 : -1) * price * size;
      n++;
    }
    if (hitOld || rows.length < 500) break;        // reached the 24h edge (or last page)
    offset += 500;
  }
  return n ? { net: Math.round(net), n } : null;
}

// The main moneyline market: two team outcomes, deepest volume, excluding
// halves / quarters / props / spreads / totals.
function mainMoneyline(ev) {
  const skip = /1h|2h|q1|q2|q3|q4|half|quarter|first|anytime|spread|total|o\/u|over|under|margin|prop|touchdown|score|handicap|cover/i;
  let best = null;
  for (const m of (ev.markets || [])) {
    const q = (m.question || m.groupItemTitle || '');
    if (skip.test(q)) continue;
    const outs = jparse(m.outcomes);
    if (!Array.isArray(outs) || outs.length !== 2) continue;
    const vol = num(m.volumeNum) || 0;
    if (!best || vol > best.vol) best = { m, outs, vol };
  }
  return best;
}

(async () => {
  let evs;
  try { evs = await fetchNflEvents(); }
  catch (e) { log('fetch failed:', e.message); process.exit(1); }
  const games = evs.filter(e => GAME_RE.test(e.slug || ''));
  log(`${evs.length} NFL-tag events · ${games.length} game events`);

  const out = {};
  let kept = 0, thin = 0, noml = 0;
  for (const ev of games) {
    const mm = (ev.slug || '').match(GAME_RE);
    const away = code(mm[1]), home = code(mm[2]);
    const vol = Math.round(num(ev.volume) || 0);
    if (vol < MIN_VOL) { thin++; continue; }
    const ml = mainMoneyline(ev);
    if (!ml) { noml++; continue; }
    const prices = jparse(ml.m.outcomePrices) || [];
    // Map each outcome to home/away by matching the outcome string against the
    // title's team names (title order == slug order == away vs. home).
    const vs = (ev.title || '').split(/\s+vs\.?\s+/i).map(s => s.trim().toLowerCase());
    const awayName = vs[0] || '', homeName = vs[1] || '';
    let pHome = null, pAway = null;
    ml.outs.forEach((o, i) => {
      const name = String(o).toLowerCase(), p = num(prices[i]);
      if (p == null) return;
      if (homeName && name && homeName.includes(name)) pHome = p;
      else if (awayName && name && awayName.includes(name)) pAway = p;
    });
    // Fallback: outcomes in slug order [away, home] if the name match missed.
    if (pHome == null || pAway == null) { const p0 = num(prices[0]), p1 = num(prices[1]); if (p0 != null && p1 != null) { pAway = p0; pHome = p1; } }
    if (pHome == null || pAway == null) { noml++; continue; }
    // Normalize the two order-book mids to a vig-free win prob (they sum to
    // ~1.0x, not exactly 1), so ml.home is directly comparable to the book's
    // vig-free implied home win% the flow-lean math compares against.
    const tot = pHome + pAway;
    if (tot > 0) { pHome /= tot; pAway /= tot; }

    // Net 24h aggressor flow into a side (+ = home). Only the current-slate
    // games carry enough trades to matter; the per-game trades pull is bounded.
    const taker = await takerFlow(ml.m.conditionId, homeName, awayName);

    out[away + '@' + home] = {
      away, home,
      ml: { away: +pAway.toFixed(4), home: +pHome.toFixed(4) },
      flow: {
        vol,
        vol24: Math.round(num(ev.volume24hr) || 0),
        oi: Math.round(num(ev.openInterest) || 0),
      },
      taker,                    // { net, n } | null — + net = money into home
      liq: Math.round(num(ev.liquidity) || 0),
      close: ev.endDate || null,
    };
    kept++;
  }

  const payload = { source: 'polymarket', generated: new Date().toISOString(), count: kept, games: out };
  log(`${kept} games kept · ${thin} thin (<$${MIN_VOL}) · ${noml} no moneyline`);
  Object.values(out).sort((a, b) => b.flow.vol - a.flow.vol).slice(0, 6)
    .forEach(g => { const tk = g.taker ? `  taker24 ${g.taker.net >= 0 ? g.home : g.away} +$${Math.abs(g.taker.net).toLocaleString()} (${g.taker.n} trades)` : ''; log(`  ${g.away}@${g.home}  ml ${(g.ml.away * 100).toFixed(0)}/${(g.ml.home * 100).toFixed(0)}¢  $${g.flow.vol.toLocaleString()} traded · $${g.flow.vol24.toLocaleString()} 24h${tk}`); });
  if (DRY) { log('--dry: not written'); return; }
  writeFileSync(OUT, JSON.stringify(payload));
  log('wrote ' + OUT);
})();
