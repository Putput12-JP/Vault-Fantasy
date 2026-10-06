#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · SHARP MONEY WATCH  →  .claude/sharp-money/data.json

   One poll of every free, keyless source that says where informed money is
   going, for NFL, college football and NBA. Run it every few minutes; each
   run diffs against the saved state, so line moves and new trades become
   time-stamped alerts, and every alert is graded against Pinnacle's closing
   price once its game starts.

   Sources (no ParlayAPI, no credits):
     · Pinnacle guest API   the market-making book. Main + alternate lines and
                            bet limits. A Pinnacle move is the sharpest public
                            signal there is; its alt ladder prices any number
                            a soft book is still hanging, so "behind the move"
                            EV is exact, not guessed.
     · Action Network       consensus bets % vs money %, the opening line, and
                            DraftKings / FanDuel / BetMGM / BetRivers / bet365.
     · Polymarket           public trade tape with the account on every trade.
                            Accounts are scored on their own record vs the
                            close (scripts/build_pm_wallets.py, per sport).
     · Kalshi               anonymous tape; the big tickets.
     · ESPN scoreboard      final scores for the alert record.

   What the study already showed (docs/retro/sharp-money-study.md): sharp
   Polymarket accounts beat the close, but copying them 30 min+ later does
   not. So alerts carry their age, and every alert is graded on closing line
   value (CLV) so the page can say which kinds are worth acting on.

   Usage:
     node scripts/fetch-sharp-money.mjs                # one poll
     node scripts/fetch-sharp-money.mjs --loop=120     # poll every 120 s
     node scripts/fetch-sharp-money.mjs --dir=path     # state + data folder
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, writeFileSync, mkdirSync, existsSync, renameSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');
const ARG = Object.fromEntries(process.argv.slice(2).map(a => { const [k, v] = a.replace(/^--/, '').split('='); return [k, v ?? true]; }));
const DIR = ARG.dir ? resolve(process.cwd(), ARG.dir) : resolve(ROOT, '.claude', 'sharp-money');
const STATE = resolve(DIR, 'state.json'), OUT = resolve(DIR, 'data.json');
const log = (...a) => console.log('[sharp]', ...a);
const UA = { 'User-Agent': 'Mozilla/5.0 (VaultFantasy sharp watch)', Accept: 'application/json' };
const PIN_KEY = 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R';     // Pinnacle's public web-client key
const H = 3600, DAY = 86400;
const now = () => Math.floor(Date.now() / 1000);

// Per-sport wiring and thresholds. `steam` = Pinnacle move inside ~30 min
// that fires an alert (points for spread/total, win-prob points for ML).
const SPORTS = {
  nfl: { name: 'NFL', an: 'nfl', pinSport: 15, pinLeague: 889, pm: 12185, kal: 'KXNFLGAME', espn: 'football/nfl', ahead: 7,
         steam: { sp: 0.5, tot: 1.0, ml: 0.025 }, whale: 10000, sharpMin: 1000, wallets: 'pm_wallets.json', sigBig: 25000, crossAt: 25000 },
  cfb: { name: 'College Football', an: 'ncaaf', pinSport: 15, pinLeague: 880, pm: 12756, kal: 'KXNCAAFGAME', espn: 'football/college-football', ahead: 5,
         steam: { sp: 1.0, tot: 1.5, ml: 0.03 }, whale: 5000, sharpMin: 1000, wallets: 'pm_wallets_cfb.json', sigBig: 25000, crossAt: 5000 },
  nba: { name: 'NBA', an: 'nba', pinSport: 4, pinLeague: 487, pm: 10345, kal: 'KXNBAGAME', espn: 'basketball/nba', ahead: 3,
         steam: { sp: 1.0, tot: 1.5, ml: 0.03 }, whale: 10000, sharpMin: 1000, wallets: 'pm_wallets_nba.json', sigBig: 25000, crossAt: 25000 },
};
const WREC = {};
const PROP_MIN_VOL = 300, PROP_MAX = 25;   // prop markets read per game (by Polymarket volume)
// Vault's own team ratings (scripts/build_game_model.py), NFL only. Context on the game page, never an edge.
let GM = null; try { GM = JSON.parse(readFileSync(resolve(ROOT, 'data', 'game_model.json'), 'utf8')); } catch (e) {}
function vaultModel(g) {
  const A = GM?.teams?.[g.away.abbr], Hm = GM?.teams?.[g.home.abbr]; if (!A || !Hm || g.sport !== 'nfl') return null;
  const ph = GM.base_pts + Hm.off - A.def + GM.hfa / 2, pa = GM.base_pts + A.off - Hm.def - GM.hfa / 2, mg = Hm.rate - A.rate + GM.hfa;
  const phi = z => 0.5 * (1 + Math.tanh(Math.sqrt(2 / Math.PI) * (z + 0.044715 * z ** 3)));
  const rank = Object.fromEntries(['rate', 'off', 'def'].map(k => { const xs = Object.entries(GM.teams).sort((p, q) => q[1][k] - p[1][k]).map(e => e[0]); return [k, { home: xs.indexOf(g.home.abbr) + 1, away: xs.indexOf(g.away.abbr) + 1, n: xs.length }]; }));
  return { home: { pts: +ph.toFixed(1) }, away: { pts: +pa.toFixed(1) }, margin: +mg.toFixed(1), total: +(ph + pa).toFixed(1), homeWin: +phi(mg / GM.sd_margin).toFixed(3), rank };
}
// Hourly money on each side over the last 36h (or up to kickoff), sharp vs everyone else.
function flowHours(G, start, t) {
  const t1 = Math.min(t, start), t0 = t1 - 36 * H, NB = 36, rows = {};
  const add = (x, sharp) => { if (x.ts < t0 || x.ts > t1) return; const b = Math.min(NB - 1, Math.floor((x.ts - t0) / H)), r = rows[x.m + ':' + x.side] ||= { sharp: Array(NB).fill(0), other: Array(NB).fill(0) }; r[sharp ? 'sharp' : 'other'][b] += x.usd; };
  for (const x of G.pm || []) add(x, x.cls === 'sharp');
  for (const x of G.kal || []) add(x, false);
  for (const r of Object.values(rows)) { r.sharp = r.sharp.map(Math.round); r.other = r.other.map(Math.round); }
  return Object.keys(rows).length ? { t0, t1, bins: NB, rows } : null;
}
const SOFT = { 68: 'DraftKings', 69: 'FanDuel', 75: 'BetMGM', 71: 'BetRivers', 79: 'bet365' };
const AN_BOOKS = [15, 30, ...Object.keys(SOFT).map(Number)];

// ── helpers ─────────────────────────────────────────────────────────────
async function getJSON(url, headers = {}, tries = 2) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { ...UA, ...headers }, signal: AbortSignal.timeout(25000) });
      if (r.status === 429) { await new Promise(s => setTimeout(s, 1500 * (i + 1))); continue; }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    } catch (e) {
      if (i === tries - 1) throw new Error(e.message + ' ' + url.slice(0, 90));
      await new Promise(s => setTimeout(s, 1500 * (i + 1)));   // Pinnacle now and then 403s a cloud IP for a few seconds
    }
  }
}
async function pool(items, n, fn) {
  const out = new Array(items.length); let i = 0;
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => {
    while (i < items.length) { const k = i++; try { out[k] = await fn(items[k], k); } catch (e) { out[k] = null; } }
  }));
  return out;
}
const imp = a => a == null ? null : a < 0 ? -a / (-a + 100) : 100 / (a + 100);     // American → implied
const payout = a => a < 0 ? 100 / -a : a / 100;                                    // profit per 1 staked
// Power de-vig (x^k + y^k = 1): keeps the favorite-longshot bias out of the
// fair price, so a +900 dog isn't read as +700 fair.
const devig = (a, b) => {
  const x = imp(a), y = imp(b); if (!x || !y) return null;
  let lo = 0.5, hi = 3;
  for (let i = 0; i < 40; i++) { const k = (lo + hi) / 2; (x ** k + y ** k > 1) ? lo = k : hi = k; }
  return x ** ((lo + hi) / 2);
};
const r3 = x => x == null ? null : Math.round(x * 1000) / 1000;
const ymdET = ts => new Date((ts - 4 * H) * 1000).toISOString().slice(0, 10).replace(/-/g, '');

// ── team-name matching across sources ───────────────────────────────────
const EXP = { st: 'state', 'st.': 'state', n: 'north', s: 'south', e: 'east', w: 'west', so: 'south', no: 'north', intl: 'international', mich: 'michigan', fla: 'florida', ga: 'georgia', ky: 'kentucky', tenn: 'tennessee', miss: 'mississippi', la: 'louisiana', wash: 'washington', ark: 'arkansas', ill: 'illinois', ind: 'indiana', okla: 'oklahoma', ala: 'alabama', car: 'carolina', cent: 'central', conn: 'connecticut', mass: 'massachusetts', ariz: 'arizona', colo: 'colorado', univ: '', u: '' };
const toks = s => String(s || '').toLowerCase().replace(/\(([^)]*)\)/g, ' $1 ').replace(/&/g, ' and ').replace(/[^a-z0-9. ]/g, ' ')
  .split(/\s+/).map(t => t.replace(/\.$/, '')).map(t => EXP[t] ?? t).filter(Boolean);
function teamAliases(t) { return [t.full_name, t.display_name, t.location, t.short_name, t.abbr].filter(Boolean).map(toks); }
function sim(name, team) {
  const nt = toks(name); if (!nt.length) return 0;
  let best = 0;
  for (const al of team._al) {
    if (!al.length) continue;
    if (al.join(' ') === nt.join(' ')) return 1;
    const hit = nt.filter(x => al.includes(x)).length;
    best = Math.max(best, hit / Math.max(nt.length, al.length === 1 ? nt.length : Math.min(al.length, nt.length + 1)));
  }
  return best;
}
// Find the master game for a pair of names + a start time. Order-free.
function matchGame(games, n1, n2, ts) {
  let best = null, bs = 0;
  for (const g of games) {
    if (ts && Math.abs(g.start - ts) > 30 * H) continue;
    const a = sim(n1, g._away) + sim(n2, g._home), b = sim(n1, g._home) + sim(n2, g._away);
    const s = Math.max(a, b);
    const minPart = a >= b ? Math.min(sim(n1, g._away), sim(n2, g._home)) : Math.min(sim(n1, g._home), sim(n2, g._away));
    if (minPart >= 0.5 && s > bs) { bs = s; best = { g, flip: b > a }; }
  }
  return best;
}
const teamSide = (g, name) => sim(name, g._home) >= sim(name, g._away) ? 'home' : 'away';

// ── state ───────────────────────────────────────────────────────────────
function loadState() { try { return JSON.parse(readFileSync(STATE, 'utf8')); } catch (e) { return { games: {}, alerts: [], cursors: {} }; } }
function saveState(S) { const tmp = STATE + '.tmp'; writeFileSync(tmp, JSON.stringify(S)); renameSync(tmp, STATE); }
function loadWallets(file) {
  try {
    const j = JSON.parse(readFileSync(resolve(ROOT, 'data', file), 'utf8'));
    const rec = {};
    for (const w of [...(j.sharp || []), ...(j.dull || [])]) {
      const a = j.wallets?.[w]; if (!a) continue;
      const [n, s, ss, gms] = a, m = s / n, sd = Math.sqrt(Math.max(ss / n - m * m, 0));
      rec[w] = { n, games: gms, clv: r3(m), t: sd ? +(m / (sd / Math.sqrt(n))).toFixed(1) : 0, sport: file.includes('_cfb') ? 'cfb' : file.includes('_nba') ? 'nba' : 'nfl' };
    }
    return { sharp: new Set(j.sharp || []), dull: new Set(j.dull || []), rec, n: Object.keys(j.wallets || {}).length, generated: j.generated };
  } catch (e) { return { sharp: new Set(), dull: new Set(), rec: {}, n: 0, generated: null }; }
}

// ── 1. Action Network: master game list, splits, open line, soft books ──
async function actionGames(sk, cfg) {
  const t = now(), dates = [];
  for (let d = 0; d <= cfg.ahead; d++) dates.push(ymdET(t + d * DAY));
  const pages = await pool(dates, 4, d => getJSON(`https://api.actionnetwork.com/web/v2/scoreboard/${cfg.an}?bookIds=${AN_BOOKS.join(',')}&date=${d}&periods=event`));
  const out = [], seen = new Set();
  for (const p of pages) for (const g of (p?.games || [])) {
    if (seen.has(g.id)) continue; seen.add(g.id);
    const T = Object.fromEntries((g.teams || []).map(x => [x.id, x]));
    const away = T[g.away_team_id], home = T[g.home_team_id]; if (!away || !home) continue;
    const start = Math.floor(Date.parse(g.start_time) / 1000);
    if (start < t - 5 * H || start > t + (cfg.ahead + 1) * DAY) continue;
    const books = {};
    for (const [bid, m] of Object.entries(g.markets || {})) {
      const ev = m.event || {}, b = {};
      const pick = (arr, side) => (arr || []).find(o => o.side === side);
      const mh = pick(ev.moneyline, 'home'), ma = pick(ev.moneyline, 'away');
      if (mh && ma) b.ml = { home: mh.odds, away: ma.odds, bi: { home: mh.bet_info, away: ma.bet_info } };
      const sh = pick(ev.spread, 'home'), sa = pick(ev.spread, 'away');
      if (sh && sa) b.sp = { line: sh.value, home: sh.odds, away: sa.odds, bi: { home: sh.bet_info, away: sa.bet_info } };
      const to = pick(ev.total, 'over'), tu = pick(ev.total, 'under');
      if (to && tu) b.tot = { line: to.value, over: to.odds, under: tu.odds, bi: { over: to.bet_info, under: tu.bet_info } };
      books[bid] = b;
    }
    const pct = bi => bi?.tickets?.percent ? { t: bi.tickets.percent, m: bi.money?.percent ?? null } : null;
    const c = books[15] || {};
    const splits = {
      ml: c.ml && pct(c.ml.bi.home) ? { home: pct(c.ml.bi.home), away: pct(c.ml.bi.away) } : null,
      sp: c.sp && pct(c.sp.bi.home) ? { home: pct(c.sp.bi.home), away: pct(c.sp.bi.away) } : null,
      tot: c.tot && pct(c.tot.bi.over) ? { over: pct(c.tot.bi.over), under: pct(c.tot.bi.under) } : null,
    };
    const strip = b => b ? { ml: b.ml ? { home: b.ml.home, away: b.ml.away } : null, sp: b.sp ? { line: b.sp.line, home: b.sp.home, away: b.sp.away } : null, tot: b.tot ? { line: b.tot.line, over: b.tot.over, under: b.tot.under } : null } : null;
    const tm = x => ({ name: x.full_name, short: x.display_name, abbr: x.abbr, color: x.primary_color ? '#' + x.primary_color : null });
    const game = {
      key: `${sk}:${g.id}`, sport: sk, anId: g.id, start, status: g.status,
      away: tm(away), home: tm(home), bets: g.num_bets || null,
      splits, open: strip(books[30]), consensus: strip(books[15]),
      soft: Object.fromEntries(Object.entries(SOFT).map(([id, nm]) => [nm, strip(books[id])]).filter(([, v]) => v && (v.ml || v.sp || v.tot))),
      _away: { _al: teamAliases(away) }, _home: { _al: teamAliases(home) },
    };
    out.push(game);
  }
  return out;
}

// ── 2. Pinnacle: main lines, alt ladders, limits ────────────────────────
async function pinnacle(cfg, games) {
  const hdr = { 'X-API-Key': PIN_KEY, Referer: 'https://www.pinnacle.com/', Origin: 'https://www.pinnacle.com' };
  const [mus, mk] = await Promise.all([
    getJSON(`https://guest.api.arcadia.pinnacle.com/0.1/sports/${cfg.pinSport}/matchups`, hdr, 4),
    getJSON(`https://guest.api.arcadia.pinnacle.com/0.1/leagues/${cfg.pinLeague}/markets/straight`, hdr, 4),
  ]);
  const byId = {};
  for (const m of mus) {
    if (m.type !== 'matchup' || m.parentId || m.league?.id !== cfg.pinLeague || (m.units && m.units !== 'Regular')) continue;
    const h = m.participants.find(p => p.alignment === 'home'), a = m.participants.find(p => p.alignment === 'away');
    if (!h || !a) continue;
    const hit = matchGame(games, a.name, h.name, Date.parse(m.startTime) / 1000);
    if (hit) byId[m.id] = { g: hit.g, flip: hit.flip };
  }
  const res = new Map();
  for (const x of mk) {
    const hit = byId[x.matchupId]; if (!hit || x.period !== 0 || x.status && x.status !== 'open') continue;
    const P = res.get(hit.g) || { spL: {}, totL: {}, lim: {} }; res.set(hit.g, P);
    const pr = d => x.prices.find(p => p.designation === d);
    const lim = x.limits?.[0]?.amount ?? null;
    const H_ = hit.flip ? 'away' : 'home', A_ = hit.flip ? 'home' : 'away';     // Pinnacle side → Vault side
    if (x.type === 'moneyline') { P.ml = { home: pr(H_)?.price, away: pr(A_)?.price }; P.lim.ml = lim; }
    else if (x.type === 'spread') {
      const h = pr(H_), a = pr(A_); if (!h || !a) continue;
      P.spL[h.points] = [h.price, a.price];
      if (!x.isAlternate) { P.sp = { line: h.points, home: h.price, away: a.price }; P.lim.sp = lim; }
    } else if (x.type === 'total') {
      const o = pr('over'), u = pr('under'); if (!o || !u) continue;
      P.totL[o.points] = [o.price, u.price];
      if (!x.isAlternate) { P.tot = { line: o.points, over: o.price, under: u.price }; P.lim.tot = lim; }
    }
  }
  return res;
}
// Fair (no-vig) prob of a side at a given number, from Pinnacle's ladder.
// Spread `line` is the HOME handicap; side 'home'|'away'. Totals: 'over'|'under'.
function pinFair(P, mkt, side, line) {
  if (!P) return null;
  if (mkt === 'ml') { const h = P.ml && devig(P.ml.home, P.ml.away); return h == null ? null : side === 'home' ? h : 1 - h; }
  const L = mkt === 'sp' ? P.spL : P.totL, row = L?.[line];
  if (!row) return null;
  const f = devig(row[0], row[1]); if (f == null) return null;
  return (side === 'home' || side === 'over') ? f : 1 - f;
}

// ── 2b. Polymarket: every sharp account's own activity ──────────────────
// The per-market tape only sees taker fills on markets we matched to a game, so
// a sharp account working a resting limit order, or betting a market we did not
// match, never shows up. Reading each sharp wallet's own activity closes that,
// and feeds the Sharp Accounts page (recent buys + current holdings).
let WT = [];                                                  // new sharp-wallet trades this poll
async function walletPoll(S, wallets) {
  const t = now(); S.acct ||= {}; WT = [];
  await pool(wallets, 6, async w => {
    const A = S.acct[w] ||= { cur: 0, who: null, trades: [], pos: [] };
    const cur = A.cur || t - 3 * DAY;
    let off = 0, newest = cur; const rows = [];
    for (let p = 0; p < 6; p++) {
      const r = await getJSON(`https://data-api.polymarket.com/activity?user=${w}&type=TRADE&limit=100&offset=${off}&sortBy=TIMESTAMP&sortDirection=DESC`);
      if (!Array.isArray(r) || !r.length) break;
      let old = false;
      for (const x of r) { if (x.timestamp <= cur) { old = true; continue; } rows.push(x); newest = Math.max(newest, x.timestamp); }
      if (old || r.length < 100) break; off += 100;
    }
    A.cur = newest;
    for (const x of rows) {
      A.who = x.pseudonym || x.name || A.who;
      const usd = x.usdcSize != null ? +x.usdcSize : x.price * x.size; if (usd < 25) continue;
      const tr = { ts: x.timestamp, side: x.side, usd: Math.round(usd), px: r3(x.price), title: x.title, slug: x.slug, ev: x.eventSlug, out: x.outcome, oi: x.outcomeIndex, cid: x.conditionId, size: x.size,
        id: x.transactionHash?.slice(0, 18) + ':' + x.outcomeIndex + ':' + Math.round(x.size) };
      A.trades.push(tr); WT.push({ ...tr, w });
    }
    A.trades = A.trades.filter(x => x.ts > t - 7 * DAY).sort((a, b) => b.ts - a.ts).slice(0, 200);
    // Holdings: only for accounts that traded in the last 3 days.
    if (A.trades[0] && A.trades[0].ts > t - 3 * DAY) {
      const ps = await getJSON(`https://data-api.polymarket.com/positions?user=${w}&sizeThreshold=1&limit=40&sortBy=CURRENT&sortDirection=DESC`);
      if (Array.isArray(ps)) A.pos = ps.filter(x => x.currentValue >= 100 && !x.redeemable).slice(0, 15)
        .map(x => ({ title: x.title, slug: x.slug, ev: x.eventSlug, out: x.outcome, size: Math.round(x.size), avg: r3(x.avgPrice), cur: r3(x.curPrice), val: Math.round(x.currentValue), cost: Math.round(x.initialValue), pnl: Math.round(x.cashPnl), end: x.endDate }));
    } else A.pos = [];
    // Results per account (refreshed every 6h, active accounts only). Polymarket's
    // closed-positions list leaves out losing bets nobody redeemed, which makes every
    // account look like a 90% winner, so this is rebuilt from the account's own
    // cash flow instead: per market, sells + redemptions - buys + what it still holds.
    // Markets still in play are skipped; only markets we saw from their first trade count.
    if (A.trades[0] && A.trades[0].ts > t - 7 * DAY && (!A.stats || t - A.stats.ts > 6 * H)) {
      const act = [];
      for (let p = 0; p < 10; p++) {
        const r = await getJSON(`https://data-api.polymarket.com/activity?user=${w}&limit=500&offset=${p * 500}&sortBy=TIMESTAMP&sortDirection=DESC`);
        if (!Array.isArray(r) || !r.length) break;
        act.push(...r); if (r.length < 500) break;
      }
      const hp = await getJSON(`https://data-api.polymarket.com/positions?user=${w}&sizeThreshold=1&limit=500&sortBy=CURRENT&sortDirection=DESC`);
      const held = {}, live = new Set();
      for (const x of Array.isArray(hp) ? hp : []) { held[x.conditionId] = (held[x.conditionId] || 0) + x.currentValue; if (x.curPrice > 0.03 && x.curPrice < 0.97) live.add(x.conditionId); }
      const t0 = act.length ? act[act.length - 1].timestamp : t, C = {};
      for (const x of act) {
        const c = C[x.conditionId] ||= { buy: 0, sell: 0, cash: 0, first: x.timestamp, slug: x.slug };
        c.first = Math.min(c.first, x.timestamp);
        if (x.type === 'TRADE') { if (x.side === 'BUY') { c.buy += x.usdcSize; c.cash -= x.usdcSize; } else { c.sell += x.usdcSize; c.cash += x.usdcSize; } }
        else if (x.type === 'REDEEM') c.cash += x.usdcSize;
      }
      const SPORTY = /^(nfl|cfb|nba|cbb|ncaaf|mlb|nhl|wnba)-/;
      const agg = xs => { let n = 0, wn = 0, buy = 0, sell = 0, pnl = 0; for (const [, c] of xs) { n++; buy += c.buy; sell += c.sell; pnl += c.pnl; if (c.pnl > 0) wn++; } return n >= 5 && buy > 0 ? { n, win: r3(wn / n), roi: r3(pnl / buy), pnl: Math.round(pnl), vol: Math.round(buy), flip: r3(sell / buy) } : null; };
      const done = Object.entries(C).filter(([id, c]) => !live.has(id) && c.first > t0 + DAY && c.buy > 0).map(([id, c]) => [id, { ...c, pnl: c.cash + (held[id] || 0) }]);
      A.stats = { ts: t, days: Math.round((t - t0) / DAY), capped: act.length >= 5000, all: agg(done), sp: agg(done.filter(([, c]) => SPORTY.test(c.slug || ''))) };
    }
  });
  for (const [w, A] of Object.entries(S.acct)) if (!A.trades.length && !A.pos.length && A.cur < t - 14 * DAY) delete S.acct[w];
}

// ── 3. Polymarket: tape by account ──────────────────────────────────────
async function polymarket(sk, cfg, games, S, W) {
  const evs = await getJSON(`https://gamma-api.polymarket.com/events?series_id=${cfg.pm}&closed=false&limit=300`);
  const t = now(), out = new Map();
  const todo = [];
  for (const ev of evs || []) {
    const st = Date.parse(ev.startTime || ev.endDate) / 1000;
    if (!st || st < t - 5 * H || st > t + (cfg.ahead + 1) * DAY) continue;
    const vs = String(ev.title || '').split(/\s+vs\.?\s+/i); if (vs.length !== 2) continue;
    const hit = matchGame(games, vs[0], vs[1], st); if (!hit) continue;
    const mk = { ml: null, sp: null, tot: null };
    for (const m of ev.markets || []) {
      const ty = m.sportsMarketType, v = +m.volumeNum || 0, outs = JSON.parse(m.outcomes || '[]'), px = JSON.parse(m.outcomePrices || '[]').map(Number);
      const k = ty === 'moneyline' ? 'ml' : ty === 'spreads' ? 'sp' : ty === 'totals' ? 'tot' : null;
      if (!k || outs.length !== 2) continue;
      if (!mk[k] || v > mk[k].vol) mk[k] = { cid: m.conditionId, outs, px, vol: v, line: m.line != null ? +m.line : null };
    }
    out.set(hit.g, { slug: ev.slug, vol: Math.round(+ev.volume || 0), vol24: Math.round(+ev.volume24hr || 0), mk });
    for (const [k, m] of Object.entries(mk)) if (m && m.vol >= 500) todo.push([hit.g, k, m]);
  }
  // Pull each market's trades newer than the cursor (first run: 24h back).
  await pool(todo, 6, async ([g, k, m]) => {
    const cur = S.cursors['pm:' + m.cid] || t - DAY;
    let off = 0, newest = cur; const rows = [];
    for (let p = 0; p < 10; p++) {
      const r = await getJSON(`https://data-api.polymarket.com/trades?market=${m.cid}&takerOnly=true&limit=500&offset=${off}`);
      if (!Array.isArray(r) || !r.length) break;
      let old = false;
      for (const x of r) { if (x.timestamp <= cur) { old = true; continue; } rows.push(x); newest = Math.max(newest, x.timestamp); }
      if (old || r.length < 500) break; off += 500;
    }
    S.cursors['pm:' + m.cid] = newest;
    const G = S.games[g.key] ||= {};
    const tape = G.pm ||= [];
    for (const x of rows) {
      const usd = x.price * x.size; if (usd < 50) continue;
      // Which Vault side the taker backed: BUY outcome i, or SELL = the other outcome.
      const oi = x.side === 'BUY' ? x.outcomeIndex : 1 - x.outcomeIndex;
      let side;
      if (k === 'tot') side = oi === 0 ? 'over' : 'under';
      else side = teamSide(g, m.outs[oi]);
      const px = x.side === 'BUY' ? x.price : 1 - x.price;                  // price paid for that side
      const cls = W.sharp.has(x.proxyWallet) ? 'sharp' : W.dull.has(x.proxyWallet) ? 'dull' : null;
      tape.push({ ts: x.timestamp, m: k, side, usd: Math.round(usd), px: r3(px), line: m.line, w: x.proxyWallet, who: x.pseudonym || x.name || null, cls, id: x.transactionHash?.slice(0, 18) + ':' + x.outcomeIndex + ':' + Math.round(x.size) });
    }
  });
  // Sharp accounts' own trades on these markets (resting-order fills the taker
  // tape never shows). Same row shape + id as above, so a trade seen both ways
  // is counted once; `late` makes the alert pass look at it even though it may
  // be older than the tape's newest row.
  const byCid = new Map();
  for (const [g, o] of out) for (const [k, m] of Object.entries(o.mk)) if (m) byCid.set(m.cid, [g, k, m]);
  for (const x of WT) {
    const hit = byCid.get(x.cid); if (!hit || !W.sharp.has(x.w)) continue;
    const [g, k, m] = hit, G = S.games[g.key] ||= {}, tape = G.pm ||= [];
    if (tape.some(y => y.id === x.id)) continue;
    const oi = x.side === 'BUY' ? x.oi : 1 - x.oi;
    const side = k === 'tot' ? (oi === 0 ? 'over' : 'under') : teamSide(g, m.outs[oi]);
    const px = x.side === 'BUY' ? x.px : 1 - x.px;
    tape.push({ ts: x.ts, m: k, side, usd: x.usd, px: r3(px), line: m.line, w: x.w, who: S.acct?.[x.w]?.who || null, cls: 'sharp', id: x.id, late: 1 });
  }
  // Player props. The series listing above already carries each game's separate
  // "<game slug>-player-props" event, so this costs no extra listing call: only the
  // busiest prop markets (games within 2 days) get their taker tape read, incrementally,
  // and the money per side is accumulated in state (G.props[cid]) with the sharp share.
  const bySlug = new Map([...out].map(([g, o]) => [o.slug, g]));
  const ptodo = [];
  for (const ev of evs || []) {
    if (!/-player-props$/.test(ev.slug || '')) continue;
    const g = bySlug.get(ev.slug.replace(/-player-props$/, '')); if (!g || g.start > t + 2 * DAY || g.start < t - 5 * H) continue;
    const G = S.games[g.key] ||= {}, P = G.props ||= {};
    const ms = (ev.markets || []).filter(m => +m.volumeNum >= PROP_MIN_VOL && !m.closed).sort((a, b) => +b.volumeNum - +a.volumeNum).slice(0, PROP_MAX);
    for (const m of ms) {
      const mt = /^([^:]+): (.+)$/.exec(m.question || ''); if (!mt) continue;
      const r = P[m.conditionId] ||= { player: mt[1], stat: mt[2].replace(/ O\/U [\d.]+$/, ''), line: m.line != null ? +m.line : null, usd: [0, 0], sharp: [0, 0], n: 0, cur: 0 };
      r.outs = JSON.parse(m.outcomes || '[]'); r.px = JSON.parse(m.outcomePrices || '[]').map(Number); r.vol = Math.round(+m.volumeNum);
      if (g.start > t) ptodo.push([m.conditionId, r]);
    }
  }
  await pool(ptodo, 6, async ([cid, r]) => {
    let newest = r.cur;
    for (let off = 0; off < 1500; off += 500) {
      const rows = await getJSON(`https://data-api.polymarket.com/trades?market=${cid}&takerOnly=true&limit=500&offset=${off}`).catch(() => null);
      if (!Array.isArray(rows) || !rows.length) break;
      let old = false;
      for (const x of rows) {
        if (x.timestamp <= r.cur) { old = true; continue; }
        const usd = x.price * x.size; newest = Math.max(newest, x.timestamp); if (usd < 5) continue;
        const oi = x.side === 'BUY' ? x.outcomeIndex : 1 - x.outcomeIndex;
        r.usd[oi] += usd; r.n++; if (W.sharp.has(x.proxyWallet)) r.sharp[oi] += usd;
      }
      if (old || rows.length < 500) break;
    }
    r.cur = newest; r.usd = r.usd.map(Math.round); r.sharp = r.sharp.map(Math.round);
  });
  return out;
}

// ── 4. Kalshi: big tickets on the winner market ─────────────────────────
async function kalshi(sk, cfg, games, S) {
  const K = 'https://api.elections.kalshi.com/trade-api/v2';
  let evs = [], cursor = '';
  for (let p = 0; p < 5; p++) {
    const r = await getJSON(`${K}/events?series_ticker=${cfg.kal}&status=open&limit=200&with_nested_markets=true${cursor ? '&cursor=' + cursor : ''}`);
    evs.push(...(r.events || [])); cursor = r.cursor; if (!cursor || !(r.events || []).length) break;
  }
  const t = now(), out = new Map(), todo = [];
  for (const ev of evs) {
    const ms = ev.markets || []; if (ms.length !== 2) continue;
    const st = Date.parse(ms[0].occurrence_datetime || ms[0].expected_expiration_time) / 1000 - (cfg.an === 'nba' ? 2.5 * H : 3 * H);
    const n1 = ms[0].yes_sub_title, n2 = ms[1].yes_sub_title;
    const hit = matchGame(games, n1, n2, st > 0 ? st : null); if (!hit) continue;
    const info = { ticker: ev.event_ticker, vol: 0, vol24: 0, px: {} };
    for (const m of ms) {
      const side = teamSide(hit.g, m.yes_sub_title);
      info.vol += +m.volume_fp || 0; info.vol24 += +m.volume_24h_fp || 0;
      info.px[side] = +m.last_price_dollars || null;
      todo.push([hit.g, m.ticker, side]);
    }
    out.set(hit.g, info);
  }
  await pool(todo, 5, async ([g, tk, side]) => {
    const cur = S.cursors['k:' + tk] || t - DAY; let newest = cur;
    const r = await getJSON(`${K}/markets/trades?ticker=${tk}&limit=1000&min_ts=${cur + 1}`);
    const G = S.games[g.key] ||= {}; const tape = G.kal ||= [];
    for (const x of r.trades || []) {
      const ts = Math.floor(Date.parse(x.created_time) / 1000); if (ts <= cur) continue; newest = Math.max(newest, ts);
      const yes = x.taker_side === 'yes', px = yes ? +x.yes_price_dollars : +x.no_price_dollars, n = +x.count_fp || +x.count || 0;
      const usd = px * n; if (usd < 500) continue;
      const other = side === 'home' ? 'away' : 'home';
      tape.push({ ts, m: 'ml', side: yes ? side : other, usd: Math.round(usd), px: r3(yes ? px : 1 - +x.yes_price_dollars), id: x.trade_id });
    }
    S.cursors['k:' + tk] = newest;
  });
  return out;
}

// ── 5. ESPN finals (for the alert record) ───────────────────────────────
async function finals(sk, cfg, S) {
  const t = now(), need = Object.values(S.games).filter(G => G.meta?.sport === sk && !G.final && G.meta.start < t - 3 * H && G.meta.start > t - 5 * DAY);
  if (!need.length) return;
  const days = [...new Set(need.map(G => ymdET(G.meta.start)))];
  for (const d of days) {
    let r; try { r = await getJSON(`https://site.api.espn.com/apis/site/v2/sports/${cfg.espn}/scoreboard?dates=${d}&limit=400${sk === 'cfb' ? '&groups=80' : ''}`); } catch (e) { continue; }
    const fake = need.filter(G => ymdET(G.meta.start) === d).map(G => ({ G, start: G.meta.start, _away: { _al: G.meta.al.away }, _home: { _al: G.meta.al.home } }));
    for (const e of r.events || []) {
      const c = e.competitions?.[0]; if (!c?.status?.type?.completed) continue;
      const h = c.competitors.find(x => x.homeAway === 'home'), a = c.competitors.find(x => x.homeAway === 'away');
      const hit = matchGame(fake, a.team.displayName, h.team.displayName, Date.parse(e.date) / 1000);
      if (!hit) continue;
      const [hs, as] = hit.flip ? [+a.score, +h.score] : [+h.score, +a.score];
      hit.g.G.final = { home: hs, away: as };
    }
  }
}

// ── signals + alerts ────────────────────────────────────────────────────
const MK = { ml: 'Moneyline', sp: 'Spread', tot: 'Total' };
function pinSnap(P) {
  if (!P) return null;
  const s = { ts: now() };
  if (P.ml) s.ml = r3(devig(P.ml.home, P.ml.away));
  if (P.sp) { s.sp = P.sp.line; s.spP = r3(devig(P.sp.home, P.sp.away)); }
  if (P.tot) { s.tot = P.tot.line; s.oP = r3(devig(P.tot.over, P.tot.under)); }
  s.lim = P.lim; return s;
}
// A single "home-side strength" number per market so moves are comparable:
// spread in points (+ = toward home), totals in points (+ = toward over),
// ML in win prob. Prob tweaks at the same number count as 1/20 of a point.
function level(s, m) {
  if (!s) return null;
  if (m === 'ml') return s.ml;
  if (m === 'sp') return s.sp == null ? null : -s.sp + (s.spP - 0.5) * 2.5;
  if (m === 'tot') return s.tot == null ? null : s.tot + (s.oP - 0.5) * 2.5;
}
const sideOf = (m, d) => m === 'tot' ? (d > 0 ? 'over' : 'under') : (d > 0 ? 'home' : 'away');
const nameSide = (g, m, side) => m === 'tot' ? (side === 'over' ? 'Over' : 'Under') : g[side].short || g[side].abbr;
function fmtLine(g, m, side, line) {
  if (m === 'ml') return nameSide(g, m, side) + ' ML';
  if (m === 'tot') return `${nameSide(g, m, side)} ${line}`;
  const l = side === 'home' ? line : -line;
  return `${nameSide(g, m, side)} ${l > 0 ? '+' : ''}${l}`;
}
const am = p => p >= 0.5 ? Math.round(-100 * p / (1 - p)) : Math.round(100 * (1 - p) / p);

function pushAlert(S, a) {
  a.id = a.id || `${a.game}:${a.type}:${a.m}:${a.side}:${a.ts}`;
  if (S.alerts.some(x => x.id === a.id)) return false;
  S.alerts.push(a); S._new.push(a); return true;
}
// Pinnacle fair price for an alert's side, at the alert's number, right now.
function fairNow(P, a) {
  if (a.m === 'ml') return pinFair(P, 'ml', a.side);
  const hl = a.m === 'sp' ? a.hline : a.line;
  return pinFair(P, a.m, a.side, hl);
}

function analyse(sk, cfg, g, P, pmInfo, kInfo, S, W) {
  const t = now(), G = S.games[g.key] ||= {};
  G.meta = { sport: sk, start: g.start, away: g.away, home: g.home, al: { away: g._away._al, home: g._home._al } };
  const live = g.start > t;
  // Pinnacle history (only while pre-game; the last pre-game snap is the close).
  const snap = pinSnap(P);
  G.pin ||= [];
  if (live && snap) {
    const last = G.pin[G.pin.length - 1];
    const same = last && last.ml === snap.ml && last.sp === snap.sp && last.spP === snap.spP && last.tot === snap.tot && last.oP === snap.oP && JSON.stringify(last.lim) === JSON.stringify(snap.lim);
    if (!same) G.pin.push(snap);
    if (G.pin.length > 400) G.pin.splice(1, G.pin.length - 400);
    G.ladder = { sp: P.spL, tot: P.totL, ml: P.ml };              // for closing grades
  }
  if (live && g.splits) {
    const sp = g.splits, last = (G.split ||= [])[G.split.length - 1];
    const row = { ts: t, ml: sp.ml?.home ? [sp.ml.home.t, sp.ml.home.m] : null, sp: sp.sp?.home ? [sp.sp.home.t, sp.sp.home.m] : null, tot: sp.tot?.over ? [sp.tot.over.t, sp.tot.over.m] : null };
    if (!last || JSON.stringify([last.ml, last.sp, last.tot]) !== JSON.stringify([row.ml, row.sp, row.tot])) G.split.push(row);
    if (G.split.length > 200) G.split.splice(1, G.split.length - 200);
  }
  // prune tapes to 3 days
  for (const k of ['pm', 'kal']) if (G[k]) { const seen = new Set(); G[k] = G[k].filter(x => x.ts > t - 3 * DAY && !seen.has(x.id) && seen.add(x.id)); }

  // Sharp side at kickoff (same read as fetch-polymarket's pm_signal_log):
  // 24h net taker money on the full-game moneyline from sharp accounts vs
  // everyone else, plus the price. Rolls forward each poll, so the last
  // pre-game read is what gets graded (+ = money on the home team).
  if (live && G.pm) {
    let sharp = 0, all = 0, sharpN = 0;
    for (const x of G.pm) if (x.m === 'ml' && x.ts > t - DAY) { const v = x.side === 'home' ? x.usd : -x.usd; all += v; if (x.cls === 'sharp') { sharp += v; sharpN++; } }
    let home_p = null;
    const ml = pmInfo?.mk?.ml;
    if (ml && ml.px?.length === 2) { const hi = teamSide(g, ml.outs[0]) === 'home' ? 0 : 1; const a = ml.px[hi], b = ml.px[1 - hi]; if (a > 0 && b > 0) home_p = r3(a / (a + b)); }
    if (home_p == null && P?.ml) home_p = r3(devig(P.ml.home, P.ml.away));
    if (sharpN) G.sig = { ts: t, sharp: Math.round(sharp), sharpN, crowd: Math.round(all - sharp), home_p };
    // Same read on the main spread and total (NFL and NBA only: docs/pm-spread-total-results.md
    // found sharp-account skill on those, none on college). Only trades at the market's
    // current line count, so a line move starts the read over. + = home (spread) / over (total).
    // `line` is the HOME handicap for spreads and the number for totals; `p` is the price of the + side.
    if (sk === 'nfl' || sk === 'nba') {
      for (const [m, key] of [['sp', 'sigSp'], ['tot', 'sigTot']]) {
        const mk = pmInfo?.mk?.[m]; if (!mk || mk.line == null || mk.px?.length !== 2) continue;
        const pos = x => m === 'tot' ? x.side === 'over' : x.side === 'home';
        let sh = 0, al = 0, n = 0;
        for (const x of G.pm) if (x.m === m && x.line === mk.line && x.ts > t - DAY) { const v = pos(x) ? x.usd : -x.usd; al += v; if (x.cls === 'sharp') { sh += v; n++; } }
        if (!n) continue;
        let p, line;
        if (m === 'tot') { p = mk.px[0]; line = mk.line; }
        else { const hi = teamSide(g, mk.outs[0]) === 'home' ? 0 : 1; p = mk.px[hi]; line = hi === 0 ? mk.line : -mk.line; }
        const q = mk.px[0] + mk.px[1]; if (!(q > 0)) continue;
        G[key] = { ts: t, sharp: Math.round(sh), sharpN: n, crowd: Math.round(al - sh), p: r3(p / q), line };
      }
    }
    // Crossed: the first poll where the sharp net on one team reaches the
    // sport's line (NFL/NBA $25k, CFB $5k: CFB markets are far thinner). One
    // alert per game per side, so a flip to the other team fires again.
    const sg = G.sig;
    if (sg && Math.abs(sg.sharp) >= cfg.crossAt && sg.home_p != null) {
      const side = sg.sharp > 0 ? 'home' : 'away', q = side === 'home' ? sg.home_p : 1 - sg.home_p;
      let best = null;
      for (const [bk, x] of Object.entries(g.soft || {})) { const pr = x.ml?.[side]; if (pr != null && (!best || pr > best.price)) best = { book: bk, price: pr }; }
      const better = best && imp(best.price) < q;
      const cr = sg.crowd, crTxt = Math.abs(cr) < 1000 ? 'crowd about even' : `crowd ${(cr > 0) === (sg.sharp > 0) ? 'with them' : 'against them'} $${Math.abs(cr).toLocaleString()}`;
      const nm = g[side].short || g[side].abbr;
      pushAlert(S, { game: g.key, sport: sk, gameLbl: `${g.away.abbr || g.away.short} @ ${g.home.abbr || g.home.short}`, start: g.start,
        ts: t, type: 'cross', m: 'ml', side, usd: Math.abs(sg.sharp), n: sg.sharpN, crowd: cr, px: r3(q), book: best?.book || null, price: best?.price ?? null, better: !!better,
        fair: r3(pinFair(P, 'ml', side)), id: `${g.key}:cross:${side}`,
        text: `Sharp accounts now have $${Math.abs(sg.sharp).toLocaleString()} net on ${nm} to win (${sg.sharpN} trade${sg.sharpN === 1 ? "" : "s"}, ${crTxt}). Exchange price ${Math.round(q * 100)}¢` +
          (best ? `; best US book ${best.book} ${best.price > 0 ? '+' : ''}${best.price}${better ? ', which pays better' : ''}` : '') });
    }
  }
  const gameLbl = `${g.away.abbr || g.away.short} @ ${g.home.abbr || g.home.short}`;
  const base = { game: g.key, sport: sk, gameLbl, start: g.start };

  if (!live) return;

  // (a) Pinnacle steam: move inside the last ~35 min past the threshold.
  // Only when the previous poll was recent: after a gap (overnight, app
  // closed) the move can't be timed, so it shows on the chart, not as steam.
  const hist = G.pin, cur = hist[hist.length - 1];
  if (cur && hist.length > 1 && t - (S.prevPoll || 0) < 25 * 60) {
    for (const m of ['sp', 'tot', 'ml']) {
      const ref = [...hist].reverse().find(s => s.ts <= t - 30 * 60) || hist[0];
      if (ref === cur) continue;
      const lv0 = level(ref, m), lv1 = level(cur, m); if (lv0 == null || lv1 == null) continue;
      const d = lv1 - lv0, thr = cfg.steam[m];
      if (Math.abs(d) < thr) continue;
      const side = sideOf(m, d);
      const line = m === 'sp' ? (side === 'home' ? cur.sp : cur.sp) : m === 'tot' ? cur.tot : null;
      const from = m === 'ml' ? `${Math.round(100 * (side === 'home' ? ref.ml : 1 - ref.ml))}%` : m === 'sp' ? fmtLine(g, m, side, ref.sp) : `${ref.tot}`;
      const to = m === 'ml' ? `${Math.round(100 * (side === 'home' ? cur.ml : 1 - cur.ml))}%` : m === 'sp' ? fmtLine(g, m, side, cur.sp) : `${cur.tot}`;
      // One steam alert per market+side per 3h, so a slow drift doesn't spam.
      const recent = S.alerts.find(a => a.game === g.key && a.type === 'steam' && a.m === m && a.side === side && a.ts > t - 3 * H);
      if (recent) continue;
      pushAlert(S, { ...base, ts: t, type: 'steam', m, side, hline: cur.sp, line: m === 'tot' ? cur.tot : m === 'sp' ? (side === 'home' ? cur.sp : -cur.sp) : null,
        fair: r3(fairNow(P, { m, side, hline: cur.sp, line: cur.tot })), text: `Pinnacle moved ${MK[m].toLowerCase()} toward ${nameSide(g, m, side)}: ${from} → ${to}`,
        size: +Math.abs(d).toFixed(m === 'ml' ? 3 : 1) });
    }
  }

  // (b) Soft books behind Pinnacle: positive EV vs Pinnacle's fair price at
  // the SAME number (alt ladder), so a stale -2.5 vs Pinnacle's -3.5 is priced
  // exactly. Fires once per book+number+price; the EV is re-checked each run.
  const behind = [];
  if (P) for (const [book, b] of Object.entries(g.soft || {})) {
    const cands = [];
    if (b.ml) for (const side of ['home', 'away']) cands.push({ m: 'ml', side, price: b.ml[side], hline: null, line: null });
    if (b.sp?.line != null) for (const side of ['home', 'away']) cands.push({ m: 'sp', side, price: b.sp[side], hline: b.sp.line, line: side === 'home' ? b.sp.line : -b.sp.line });
    if (b.tot?.line != null) for (const side of ['over', 'under']) cands.push({ m: 'tot', side, price: b.tot[side], line: b.tot.line });
    for (const c of cands) {
      if (c.price == null || c.price < -300 || c.price > 300) continue;   // long-shot fairs are too soft to call
      const f = fairNow(P, c); if (f == null) continue;
      const ev = f * (1 + payout(c.price)) - 1;
      if (ev >= 0.02 && ev < 0.25) behind.push({ book, ...c, fair: r3(f), ev: r3(ev) });
    }
  }
  behind.sort((a, b) => b.ev - a.ev);
  G.behind = behind.slice(0, 6);
  for (const x of behind.filter(x => x.ev >= 0.03)) {
    pushAlert(S, { ...base, ts: t, type: 'behind', m: x.m, side: x.side, book: x.book, price: x.price, hline: x.hline, line: x.line, fair: x.fair, ev: x.ev,
      id: `${g.key}:behind:${x.book}:${x.m}:${x.side}:${x.line}:${x.price}`,
      text: `${x.book} still has ${fmtLine(g, x.m, x.side, x.hline ?? x.line)} ${x.price > 0 ? '+' : ''}${x.price}; Pinnacle's fair price is ${am(x.fair) > 0 ? '+' : ''}${am(x.fair)} (${(x.ev * 100).toFixed(1)}% EV)` });
  }

  // (c) Polymarket sharp accounts, (d) whale tickets (PM + Kalshi).
  const cutoff = t - 40 * 60;
  const pmNew = (G.pm || []).filter(x => x.ts > (G._pmSeen || 0) || x.late);
  const groups = {};
  for (const x of pmNew.filter(x => x.cls === 'sharp')) (groups[x.m + ':' + x.side] ||= []).push(x);
  for (const [k, xs] of Object.entries(groups)) {
    const usd = xs.reduce((s, x) => s + x.usd, 0); if (usd < cfg.sharpMin) continue;
    const [m, side] = k.split(':'), top = xs.sort((a, b) => b.usd - a.usd)[0];
    const accts = [...new Set(xs.map(x => x.w))];
    pushAlert(S, { ...base, ts: Math.max(...xs.map(x => x.ts)), type: 'sharp', m, side, usd, n: xs.length, accts: accts.length,
      px: top.px, who: top.who, rec: W.rec[top.w] || null, fair: r3(fairNow(P, { m, side, hline: cur?.sp, line: cur?.tot })), hline: cur?.sp, line: m === 'tot' ? cur?.tot : m === 'sp' ? (side === 'home' ? cur?.sp : cur?.sp != null ? -cur.sp : null) : null,
      text: `${accts.length > 1 ? accts.length + ' sharp accounts' : 'Sharp account ' + (top.who || top.w.slice(0, 8))} put $${usd.toLocaleString()} on ${m === 'ml' ? nameSide(g, m, side) + ' to win' : nameSide(g, m, side) + (m === 'tot' ? ' (total)' : ' (spread)')} at ${Math.round(top.px * 100)}¢` });
  }
  const whales = [...pmNew.map(x => ({ ...x, src: 'Polymarket' })), ...(G.kal || []).filter(x => x.ts > (G._kSeen || 0)).map(x => ({ ...x, src: 'Kalshi' }))].filter(x => x.usd >= cfg.whale);
  for (const x of whales) {
    pushAlert(S, { ...base, ts: x.ts, type: 'whale', m: x.m, side: x.side, usd: x.usd, px: x.px, src: x.src, cls: x.cls || null, who: x.who || null,
      fair: r3(fairNow(P, { m: x.m, side: x.side, hline: cur?.sp, line: cur?.tot })), hline: cur?.sp, line: x.m === 'tot' ? cur?.tot : x.m === 'sp' ? (x.side === 'home' ? cur?.sp : cur?.sp != null ? -cur.sp : null) : null,
      id: `${g.key}:whale:${x.src}:${x.id}`,
      text: `$${x.usd.toLocaleString()} ticket on ${x.m === 'ml' ? nameSide(g, x.m, x.side) + ' to win' : nameSide(g, x.m, x.side)} at ${Math.round(x.px * 100)}¢ (${x.src}${x.cls === 'sharp' ? ', sharp account' : x.cls === 'dull' ? ', usually-losing account' : ''})` });
  }
  if (G.pm?.length) G._pmSeen = Math.max(...G.pm.map(x => x.ts));
  for (const x of G.pm || []) delete x.late;
  if (G.kal?.length) G._kSeen = Math.max(...G.kal.map(x => x.ts));

  // (e) Money vs tickets: big-bettor side (money % well above tickets %)
  // with the line moving their way since open (reverse line move when the
  // tickets are on the other side).
  for (const m of ['sp', 'ml', 'tot']) {
    const sp = g.splits?.[m]; if (!sp) continue;
    const sides = m === 'tot' ? ['over', 'under'] : ['home', 'away'];
    for (const side of sides) {
      const s = sp[side]; if (!s || s.m == null) continue;
      const gap = s.m - s.t;
      if (gap < 20 || s.t > 50) continue;                     // money ≥ tickets + 20 on the minority side
      const moved = lineMoveSince(G, m, side);
      pushAlert(S, { ...base, ts: t, type: 'split', m, side, tk: s.t, mo: s.m, moved,
        fair: r3(fairNow(P, { m, side, hline: cur?.sp, line: cur?.tot })), hline: cur?.sp, line: m === 'tot' ? cur?.tot : m === 'sp' ? (side === 'home' ? cur?.sp : cur?.sp != null ? -cur.sp : null) : null,
        id: `${g.key}:split:${m}:${side}`,
        text: `${s.m}% of the money but only ${s.t}% of bets on ${fmtLine(g, m, side, m === 'sp' ? g.consensus?.sp?.line : g.consensus?.tot?.line)}${moved > 0 ? ', and Pinnacle has moved their way' : ''}` });
    }
  }
}
// How far Pinnacle has moved toward `side` since the first snapshot (points / prob).
function lineMoveSince(G, m, side) {
  const h = G.pin || []; if (h.length < 2) return 0;
  const d = level(h[h.length - 1], m) - level(h[0], m);
  if (!Number.isFinite(d)) return 0;
  return +((side === 'home' || side === 'over') ? d : -d).toFixed(3);
}

// ── closing grades ──────────────────────────────────────────────────────
// Close = Pinnacle's last pre-game ladder. CLV = closing fair prob of the
// alert's side at the alert's number minus the prob when the alert fired
// (for "behind" alerts: EV of the soft-book price at the closing fair).
function grade(S) {
  const t = now();
  for (const a of S.alerts) {
    const G = S.games[a.game]; if (!G) continue;
    if (!a.close && a.start <= t && G.ladder) {
      const P = { ml: G.ladder.ml, spL: G.ladder.sp, totL: G.ladder.tot };
      const f = fairNow(P, a);
      if (f != null) {
        a.close = r3(f);
        if (a.type === 'behind') a.clv = r3(f * (1 + payout(a.price)) - 1);
        else if (a.fair != null) a.clv = r3(f - a.fair);
      } else a.close = 'n/a';
    }
    if (G.final && a.result == null && a.m) {
      const { home, away } = G.final;
      let v;
      if (a.m === 'ml') v = home === away ? 0 : (home > away) === (a.side === 'home') ? 1 : -1;
      else if (a.m === 'sp' && a.hline != null) { const d = home + a.hline - away; const r = a.side === 'home' ? d : -d; v = r > 0 ? 1 : r < 0 ? -1 : 0; }
      else if (a.m === 'tot' && a.line != null) { const d = home + away - a.line; const r = a.side === 'over' ? d : -d; v = r > 0 ? 1 : r < 0 ? -1 : 0; }
      if (v != null) a.result = v;
    }
  }
}

// ── build the page payload ──────────────────────────────────────────────
function payload(S, byGame, W, status) {
  const t = now();
  const games = [];
  for (const g of byGame) {
    const G = S.games[g.key] || {}, P = g._P, pm = g._pm, K = g._k;
    const tapeSum = (tape, since, filt = () => true) => {
      const o = {};
      for (const x of tape || []) if (x.ts >= since && filt(x)) { const k = x.m + ':' + x.side; o[k] = (o[k] || 0) + x.usd; }
      return o;
    };
    const flow = {
      pmAll: tapeSum(G.pm, t - DAY), pmBig: tapeSum(G.pm, t - DAY, x => x.usd >= 1000),
      sharp: tapeSum(G.pm, t - DAY, x => x.cls === 'sharp'), dull: tapeSum(G.pm, t - DAY, x => x.cls === 'dull'),
      sharp2h: tapeSum(G.pm, t - 2 * H, x => x.cls === 'sharp'),
      kalBig: tapeSum(G.kal, t - DAY, x => x.usd >= 1000),
    };
    const tickets = [...(G.pm || []).filter(x => x.usd >= 1000 || x.cls === 'sharp').map(x => ({ ...x, src: 'PM' })), ...(G.kal || []).filter(x => x.usd >= 2000).map(x => ({ ...x, src: 'Kalshi' }))]
      .filter(x => x.ts > t - 2 * DAY).sort((a, b) => b.ts - a.ts).slice(0, 40)
      .map(({ w, id, ...x }) => ({ ...x, w: w ? w.slice(0, 6) + '…' + w.slice(-4) : null, rec: w && WREC[g.sport]?.[w] ? WREC[g.sport][w] : null }));
    // Per-account rollup over the same 24h as flow.sharp, so the game page's money bar adds up
    // to the sharp net it headlines (the 40-row ticket tape above is too short for that).
    const A = {};
    for (const x of G.pm || []) {
      if (x.ts < t - DAY || !x.w) continue;
      const k = x.w + '|' + x.m + ':' + x.side, a = A[k] ||= { w: x.w, who: x.who || null, cls: x.cls || null, m: x.m, side: x.side, usd: 0, n: 0, last: 0 };
      a.usd += x.usd; a.n++; a.last = Math.max(a.last, x.ts);
    }
    for (const [k, v] of Object.entries(flow.kalBig)) { const [m, side] = k.split(':'); A['kal|' + k] = { w: null, who: 'Kalshi big tickets', cls: null, m, side, usd: v, n: (G.kal || []).filter(x => x.ts >= t - DAY && x.usd >= 1000 && x.m === m && x.side === side).length, last: 0, src: 'Kalshi' }; }
    const rolled = Object.values(A).sort((a, b) => b.usd - a.usd);
    const accts = [...rolled.filter(a => a.cls === 'sharp'), ...rolled.filter(a => a.cls !== 'sharp' && a.usd >= 1000).slice(0, 16)]
      .map(({ w, ...a }) => ({ ...a, usd: Math.round(a.usd), w: w ? w.slice(0, 6) + '…' + w.slice(-4) : null, rec: w && WREC[g.sport]?.[w] ? WREC[g.sport][w] : null }));
    games.push({
      key: g.key, sport: g.sport, start: g.start, status: g.status, away: g.away, home: g.home, bets: g.bets, accts,
      props: G.props ? Object.values(G.props).filter(r => r.usd[0] + r.usd[1] >= 100).sort((a, b) => (b.usd[0] + b.usd[1]) - (a.usd[0] + a.usd[1])).slice(0, 40).map(({ cur, vol, ...r }) => r) : null,
      flowH: flowHours(G, g.start, t), model: vaultModel(g),
      splits: g.splits, open: g.open, consensus: g.consensus, soft: g.soft,
      pin: P ? { ml: P.ml, sp: P.sp, tot: P.tot, lim: P.lim } : null,
      pinHist: (G.pin || []).map(s => [s.ts, s.ml ?? null, s.sp ?? null, s.spP ?? null, s.tot ?? null, s.oP ?? null]),
      splitHist: G.split || [],
      pm: pm ? { slug: pm.slug, vol: pm.vol, vol24: pm.vol24, px: Object.fromEntries(Object.entries(pm.mk).filter(([, v]) => v).map(([k, v]) => [k, { line: v.line, outs: v.outs, px: v.px, vol: Math.round(v.vol) }])) } : null,
      kal: K || null, flow, tickets, behind: G.behind || [], final: G.final || null,
    });
  }
  games.sort((a, b) => a.start - b.start);
  // Sharp side at kickoff: every game with a sharp read, graded once final.
  const sigRec = [];
  for (const [k, G] of Object.entries(S.games)) {
    if (!G.sig || !G.meta) continue;
    const f = G.final, m = G.meta;
    sigRec.push({ key: k, sport: m.sport, game: `${m.away.abbr} @ ${m.home.abbr}`, start: m.start, sharp: G.sig.sharp, sharpN: G.sig.sharpN, crowd: G.sig.crowd, home_p: G.sig.home_p,
      final: f ? [f.away, f.home] : null, src: 'watch' });
  }
  for (const [k, G] of Object.entries(S.games)) {          // spread / total reads, same record shape plus m + line
    if (!G.meta) continue;
    for (const [m, key] of [['sp', 'sigSp'], ['tot', 'sigTot']]) {
      const x = G[key]; if (!x) continue;
      const f = G.final, mt = G.meta;
      sigRec.push({ key: k, sport: mt.sport, game: `${mt.away.abbr} @ ${mt.home.abbr}`, start: mt.start, m, line: x.line, sharp: x.sharp, sharpN: x.sharpN, crowd: x.crowd, home_p: x.p,
        final: f ? [f.away, f.home] : null, src: 'watch' });
    }
  }
  // NFL before the watch existed: fetch-polymarket's signal log (Weeks 1-3
  // backfilled from the tape, sharp list with the game itself held out).
  try {
    const L = JSON.parse(readFileSync(resolve(ROOT, 'data', 'pm_signal_log.json'), 'utf8')).games || {};
    const BR = JSON.parse(readFileSync(resolve(ROOT, 'data', 'bet_results.json'), 'utf8')).games || [];
    const born = S.born || now();
    const sc = {}; for (const g of BR) if (g.home_score != null) sc[`${g.season}|${g.away}|${g.home}`] = [g.away_score, g.home_score];
    for (const e of Object.values(L)) {
      const st = Math.floor(Date.parse(e.commence) / 1000), r = e.last || {};
      if (!(st < born) || r.sharp == null) continue;
      sigRec.push({ sport: 'nfl', game: `${e.away} @ ${e.home}`, start: st, sharp: r.sharp, sharpN: r.sharpN, crowd: r.crowd, home_p: r.home_p,
        final: sc[`${e.commence.slice(0, 4)}|${e.away}|${e.home}`] || null, src: 'log' });
    }
  } catch (e) { /* no log */ }
  sigRec.sort((a, b) => b.start - a.start);
  const alerts = S.alerts.filter(a => a.ts > t - 10 * DAY).sort((a, b) => b.ts - a.ts).slice(0, 1500);
  // Sharp Accounts page: each sharp wallet's own buys + current holdings.
  const accounts = Object.entries(S.acct || {}).filter(([, A]) => A.trades.length || A.pos.length).map(([w, A]) => {
    const recs = Object.values(WREC).map(r => r[w]).filter(Boolean);
    const rec = recs.sort((a, b) => b.n - a.n)[0] || null;
    const b24 = A.trades.filter(x => x.ts > t - DAY && x.side === 'BUY');
    return { w, who: A.who, rec, last: A.trades[0]?.ts || 0, n7: A.trades.length, buy24: b24.reduce((s, x) => s + x.usd, 0), n24: b24.length,
      trades: A.trades.slice(0, 25).map(({ ts, side, usd, px, title, slug, out }) => ({ ts, side, usd, px, title, slug, out })), pos: A.pos.map(({ ev, ...x }) => x), posVal: A.pos.reduce((s, x) => s + x.val, 0), stats: A.stats ? { all: A.stats.all, sp: A.stats.sp, days: A.stats.days, capped: A.stats.capped } : null };
  }).filter(a => a.last > t - 7 * DAY || a.pos.length).sort((a, b) => b.buy24 - a.buy24 || b.last - a.last).slice(0, 80);
  return { generated: new Date().toISOString(), ts: t, status, wallets: W, games, alerts, accounts, sigRec, sigBig: Object.fromEntries(Object.entries(SPORTS).map(([k, c]) => [k, c.sigBig])) };
}

// ── main ────────────────────────────────────────────────────────────────
async function pollOnce() {
  mkdirSync(DIR, { recursive: true });
  const S = loadState(); S.born ||= now(); S._new = []; S.prevPoll = S.lastPoll || 0; S.lastPoll = now();
  const status = {}, all = [], walletInfo = {};
  // Accounts are scored per sport, but skill travels: NFL-sharp accounts beat
  // the CFB close by +2.2%/trade (194 trades, t 7, 2026 season). So an account
  // with no record in this sport borrows its sharp label from another sport.
  const OWN = Object.fromEntries(Object.entries(SPORTS).map(([sk, c]) => [sk, loadWallets(c.wallets)]));
  const allSharp = [...new Set(Object.values(OWN).flatMap(o => [...o.sharp]))];
  await walletPoll(S, allSharp).catch(e => { status.accounts = 'error: ' + e.message; });
  for (const [sk, cfg] of Object.entries(SPORTS)) {
    const st = status[sk] = {};
    const own = OWN[sk], W = { sharp: new Set(own.sharp), dull: new Set(own.dull), rec: { ...own.rec }, n: own.n, generated: own.generated };
    for (const [ok, o] of Object.entries(OWN)) if (ok !== sk) for (const w of o.sharp) {
      if (own.rec[w] || own.dull.has(w)) continue;
      W.sharp.add(w); W.rec[w] = o.rec[w];
    }
    WREC[sk] = W.rec;
    walletInfo[sk] = { sharp: own.sharp.size, borrowed: W.sharp.size - own.sharp.size, dull: W.dull.size, scored: W.n, generated: W.generated };
    let games = [];
    try { games = await actionGames(sk, cfg); st.action = games.length; } catch (e) { st.action = 'error: ' + e.message; }
    if (!games.length) { st.games = 0; await finals(sk, cfg, S).catch(() => {}); continue; }
    const [P, PM, K] = await Promise.all([
      pinnacle(cfg, games).catch(e => { st.pinnacle = 'error: ' + e.message; return new Map(); }),
      polymarket(sk, cfg, games, S, W).catch(e => { st.polymarket = 'error: ' + e.message; return new Map(); }),
      kalshi(sk, cfg, games, S).catch(e => { st.kalshi = 'error: ' + e.message; return new Map(); }),
    ]);
    st.pinnacle ??= P.size; st.polymarket ??= PM.size; st.kalshi ??= K.size; st.games = games.length;
    for (const g of games) {
      g._P = P.get(g) || null; g._pm = PM.get(g) || null; g._k = K.get(g) || null;
      analyse(sk, cfg, g, g._P, g._pm, g._k, S, W);
      all.push(g);
    }
    await finals(sk, cfg, S).catch(() => {});
  }
  grade(S);
  // forget games a week after they start
  const t = now();
  for (const [k, G] of Object.entries(S.games)) if (G.meta && G.meta.start < t - 7 * DAY) delete S.games[k];
  S.alerts = S.alerts.filter(a => a.ts > t - 60 * DAY);
  const fresh = S._new; delete S._new;
  saveState(S);
  const P = payload(S, all, { ...walletInfo }, status);
  // `sig` changes only when something a viewer would see changes.
  P.sig = createHash('sha1').update(String(P.alerts.length) + ':' + (P.alerts[0]?.id || '') + ':' + all.map(g => (S.games[g.key]?.pin || []).length + '/' + (S.games[g.key]?.split || []).length).join(',')).digest('hex').slice(0, 12);
  writeFileSync(OUT, JSON.stringify(P));
  writeFileSync(resolve(DIR, 'new_alerts.json'), JSON.stringify(fresh));
  log(new Date().toISOString(), JSON.stringify(status), `${fresh.length} new alerts`);
  for (const a of fresh.slice(0, 12)) log('  +', a.sport, a.type, a.gameLbl, '·', a.text);
  return fresh;
}

if (ARG.loop) {
  const every = Math.max(30, +ARG.loop || 120) * 1000;
  for (;;) { try { await pollOnce(); } catch (e) { log('poll failed', e.message); } await new Promise(s => setTimeout(s, every)); }
} else {
  await pollOnce();
}
