#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · GAME-MARKET SNAPSHOT LOG  →  data/game_line_history.json

   The game-market twin of scripts/snapshot-prop-history.mjs. Banks the raw
   spread / total / moneyline snapshots the settlement + CLV harness needs,
   using data we already ship (data/lineup-feed.json vegas_games) — no API
   calls, no credits.

   WHY THIS EXISTS SEPARATELY from data/line_history.json:
     line_history.json feeds the LIVE board (open→cur movement) and DROPS a
     game the moment it leaves the feed (finished). Settlement needs the
     opposite: finished games must be KEPT so we can grade them once the score
     lands. So this file RETAINS every key, exactly like prop_line_history.

   FREEZE + RETAIN, keyed by season|seasonType|week|AWY@HOM:
     · first time a key is seen, its snapshot is frozen as `open`;
     · every later run rolls `cur` forward and appends to `samples` only when
       something actually moved;
     · keys that leave the feed (game played) are KEPT untouched — the last
       sample is the closing-line proxy the CLV harness reads.
     · seasonType is in the key so preseason week N and regular week N never
       collide (same reason as the prop log).

   Output (read by scripts/settle_bets.py):
     { generated, season, seasonType, week, keys, games: {
        "AWY@HOM key": { season, seasonType, week, away, home, commence,
          open:{spread,total,mlHome,ts}, cur:{…}, firstSeen, lastSeen,
          samples:[{spread,total,mlHome,ts}, …] } } }

   Usage:  node scripts/snapshot-game-history.mjs
           node scripts/snapshot-game-history.mjs --feed=data/lineup-feed.json --out=data/game_line_history.json --dry
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ARG = Object.fromEntries(process.argv.slice(2).map(a => { const [k, v] = a.replace(/^--/, '').split('='); return [k, v ?? true]; }));
const DRY = !!ARG.dry;
const FEED = ARG.feed ? resolve(process.cwd(), ARG.feed) : resolve(HERE, '..', 'data', 'lineup-feed.json');
const OUT = ARG.out ? resolve(process.cwd(), ARG.out) : resolve(HERE, '..', 'data', 'game_line_history.json');
const MAX_SAMPLES = 120;           // per key; open (idx 0) always kept, oldest middles drop
const log = (...a) => console.log('[game-history]', ...a);

const readJSON = p => { try { return JSON.parse(readFileSync(p, 'utf8')); } catch { return null; } };
const num = v => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const med = a => { const s = (a || []).filter(v => v != null).sort((x, y) => x - y); return s.length ? s[Math.floor((s.length - 1) / 2)] : null; };
const normCdf = z => { const t = 1 / (1 + 0.2316419 * Math.abs(z)); const d = 0.3989423 * Math.exp(-z * z / 2); let p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))); return z > 0 ? 1 - p : p; };

// Vault game model (data/game_model.json) — the same math gmPredict() serves in
// index.html. Banked per snapshot so the settlement harness can grade the model
// line AS IT WAS going into each game (the model refits weekly, so it drifts).
const GM = readJSON(resolve(HERE, '..', 'data', 'game_model.json'));
// The game model keys the Rams "LA" (via build_game_model.py's ALIAS) while the
// feed ships "LAR" — without normalizing, GM.teams['LAR'] is undefined and every
// Rams game silently banks a null model line (and so never settles). Same map
// the builders + settle_bets.py use.
const QBS = ((readJSON(resolve(HERE, '..', 'data', 'qb_status.json')) || {}).teams) || {};
const TEAM_ALIAS = { OAK: 'LV', LVR: 'LV', SD: 'LAC', STL: 'LA', LAR: 'LA', WSH: 'WAS' };
const teamGm = t => TEAM_ALIAS[t] || t;
function vaultLine(away, home) {
  away = teamGm(away); home = teamGm(home);
  // Bank the model line whenever the ratings map both teams — INCLUDING when the
  // model is still on offseason (prior-season) ratings. The settle harness needs
  // Week-1 projections to start the learning corpus (every model predicts Wk 1 on
  // priors); the `off` flag lets settlement segment offseason-based picks. Only
  // regular-season games are ever banked (the feed/caller gate preseason).
  if (!GM || !GM.teams) return null;
  const A = GM.teams[away], H = GM.teams[home];
  if (!A || !H) return null;
  const neutral = (GM.neutral || []).includes(`${away}@${home}`);  // international games: no home field
  const hfa = neutral ? 0 : (GM.hfa || 0), base = GM.base_pts || 0;
  // backup QB (qb_status.json, hourly from Sleeper): fitted points off
  const hb = QBS[home] ? 1 : 0, ab = QBS[away] ? 1 : 0, Q = GM.qb || {};
  const margin = H.rate - A.rate + hfa - (Q.margin || 0) * (hb - ab);        // home margin
  const total = 2 * base + (H.off + A.off) - (A.def + H.def) - (Q.total || 0) * (hb + ab); // hfa/2 terms cancel
  return { spread: num(-margin), total: num(total), winHome: num(normCdf(margin / (GM.sd_margin || 13.2))), off: GM.offseason ? 1 : 0 };
}

// Consensus PRICES at the consensus number (median across books quoting that
// exact line), both sides. Added 2026-09-28 for the model scoreboard: without
// the juice the spread/total market could only be read as 50/50; with both
// sides banked, settlement de-vigs them into a real closing probability.
const atLine = (quotes, pick, line) => (quotes || []).filter(q => q && pick(q) === line);
function spreadPx(g) {
  const c = g.spread && g.spread.cons ? g.spread.cons.home : null;
  if (c == null) return [null, null];
  const qs = atLine(g.spread.quotes, q => q.home && q.home.line, c);
  return [med(qs.map(q => q.home && q.home.price)), med(qs.map(q => q.away && q.away.price))];
}
function totalPx(g) {
  const c = g.total ? g.total.cons : null;
  if (c == null) return [null, null];
  const qs = atLine(g.total.quotes, q => q.line, c);
  return [med(qs.map(q => q.over)), med(qs.map(q => q.under))];
}

// Per-book quotes (2026-09-29): what a fitted book weighting for the fair game
// line needs (index.html gmFair weights books equally until then). Compact rows:
//   sp [book, homeLine, homePrice, awayPrice] · to [book, line, over, under] · ml [book, home, away]
// Kept on `open` and `cur` only (cur = the close once the game kicks off), never
// on the intermediate samples, so the history file stays small.
function bookQuotes(g) {
  const sp = ((g.spread && g.spread.quotes) || []).filter(q => q && q.home && q.away && q.home.line != null)
    .map(q => [q.book, q.home.line, q.home.price ?? null, q.away.price ?? null]);
  const to = ((g.total && g.total.quotes) || []).filter(q => q && q.line != null)
    .map(q => [q.book, q.line, q.over ?? null, q.under ?? null]);
  const ml = ((g.ml && g.ml.quotes) || []).filter(q => q && (q.home != null || q.away != null))
    .map(q => [q.book, q.home ?? null, q.away ?? null]);
  return { sp, to, ml };
}
const noQ = s => { const { q, ...rest } = s; return rest; };

/* ── Sharp-book lead tracker (2026-09-28) ─────────────────────────────────
   Does Pinnacle lead the recreational books? For each unstarted game this
   records, per market, the FIRST time a lead book's no-vig line sits
   >= LEAD_GAP from the rec books' median (3h+ before kickoff), and keeps
   rolling that rec median forward to the close. build_model_scoreboard.py
   grades it: did the rec books move toward the lead book by kickoff, and by
   more than they move toward a CONTROL book (FanDuel)? Weeks 1-3 replay
   (git history of lineup-feed.json): Pinnacle 24 toward / 9 away on spreads,
   but FanDuel as a fake "sharp" did about as well, and no single book beat
   the rest of the market's median. So it is tracked, not shown, until the
   scoreboard says GO. Per-game `lead` field; tiny. */
const LEAD_BOOKS = ['Pinnacle', 'FanDuel'];          // FanDuel = control
const REC_BOOKS = new Set(['FanDuel', 'DraftKings', 'BetRivers', 'Hard Rock Bet', 'Bovada', 'Fliff', 'BetMGM', 'Caesars', 'Fanatics', 'bet365', 'Parx Casino']);
const LEAD_GAP = 0.5, LEAD_MIN_H = 3, LEAD_LIM = { sp: 2.5, to: 3.5 };
const _imp = a => a == null ? null : (a < 0 ? -a / (-a + 100) : 100 / (a + 100));
function _devig(a, b) {
  const po = _imp(a), pu = _imp(b);
  if (!(po > 0) || !(pu > 0)) return null;
  if (po + pu <= 1) return po / (po + pu);
  let lo = 1, hi = 10; for (let i = 0; i < 40; i++) { const k = (lo + hi) / 2; if (po ** k + pu ** k > 1) lo = k; else hi = k; }
  const k = (lo + hi) / 2; return po ** k / (po ** k + pu ** k);
}
function _invN(p) {   // Acklam
  const a = [-39.6968302866538, 220.946098424521, -275.928510446969, 138.357751867269, -30.6647980661472, 2.50662827745924];
  const b = [-54.4760987982241, 161.585836858041, -155.698979859887, 66.8013118877197, -13.2806815528857];
  const c = [-0.00778489400243029, -0.322396458041136, -2.40075827716184, -2.54973253934373, 4.37466414146497, 2.93816398269878];
  const d = [0.00778469570904146, 0.32246712907004, 2.445134137143, 3.75440866190742];
  p = Math.min(Math.max(p, 1e-4), 1 - 1e-4);
  if (p < 0.02425) { const q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  if (p > 0.97575) { const q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  const q = p - 0.5, r = q * q;
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}
const _medAvg = a => { const s = a.slice().sort((x, y) => x - y); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
// per-book fair HOME spread / fair total, outliers (junk quotes) dropped
function bookFairs(g) {
  const sdM = (GM && GM.sd_margin) || 13.2, sdT = (GM && GM.sd_total) || 13.5;
  const sp = {}, to = {};
  for (const q of ((g.spread && g.spread.quotes) || [])) {
    if (!q || !q.home || !q.away || q.home.line == null) continue;
    const p = _devig(q.home.price, q.away.price); if (p != null) sp[q.book] = -(sdM * _invN(p) - q.home.line);
  }
  for (const q of ((g.total && g.total.quotes) || [])) {
    if (!q || q.line == null) continue;
    const p = _devig(q.over, q.under); if (p != null) to[q.book] = q.line + sdT * _invN(p);
  }
  const clean = (o, lim) => { const v = Object.values(o); if (v.length < 3) return o; const m = _medAvg(v); return Object.fromEntries(Object.entries(o).filter(([, x]) => Math.abs(x - m) <= lim)); };
  return { sp: clean(sp, LEAD_LIM.sp), to: clean(to, LEAD_LIM.to) };
}
function trackLead(rec, g, nowIso) {
  const kick = Date.parse(g.commence || rec.commence || ''), t = Date.parse(nowIso);
  if (!Number.isFinite(kick) || t >= kick) return;
  const F = bookFairs(g), r1 = x => Math.round(x * 100) / 100;
  rec.lead = rec.lead || {};
  for (const mk of ['sp', 'to']) {
    const fb = F[mk];
    for (const b of LEAD_BOOKS) {
      const rv = Object.entries(fb).filter(([k]) => REC_BOOKS.has(k) && k !== b).map(([, v]) => v);
      const r = _medAvg(rv); if (r == null || rv.length < 3) continue;
      const L = ((rec.lead[mk] = rec.lead[mk] || {})[b] = rec.lead[mk][b] || {});
      L.close = { ts: nowIso, r: r1(r) };                        // rolls forward; the last one before kickoff is the close
      if (!L.first && fb[b] != null && (kick - t) >= LEAD_MIN_H * 3600e3 && Math.abs(fb[b] - r) >= LEAD_GAP)
        L.first = { ts: nowIso, b: r1(fb[b]), r: r1(r) };
    }
  }
}

function snapshot(g, ts) {
  const [spH, spA] = spreadPx(g), [toO, toU] = totalPx(g);
  return {
    spread: g.spread && g.spread.cons ? num(g.spread.cons.home) : null,   // home spread (signed)
    total: g.total ? num(g.total.cons) : null,                            // game total
    mlHome: g.ml && g.ml.quotes ? med(g.ml.quotes.map(q => q.home)) : null, // home moneyline (American)
    mlAway: g.ml && g.ml.quotes ? med(g.ml.quotes.map(q => q.away)) : null, // away moneyline — lets settle devig the win prob
    spHomePx: num(spH), spAwayPx: num(spA),                              // spread prices at the consensus number
    toOverPx: num(toO), toUnderPx: num(toU),                             // total prices at the consensus number
    vault: vaultLine(g.away, g.home),                                     // model line as-of now (null offseason/unmapped)
    q: bookQuotes(g),                                                     // per-book (open / cur only)
    ts,
  };
}
// Value signature — used to skip appending a duplicate sample (ts-only refresh is free).
// Prices are in it too: settlement reads the LAST SAMPLE as the close, so a
// juice move with no line move has to land as a sample to be the closing price.
const sig = s => [s.spread, s.total, s.mlHome, s.mlAway, s.spHomePx, s.spAwayPx, s.toOverPx, s.toUnderPx].join('|');

const feed = readJSON(FEED);
if (!feed || !Array.isArray(feed.vegas_games)) { log('no vegas_games in feed — nothing to snapshot'); process.exit(0); }

const season = feed.season ?? null, week = feed.week ?? null, seasonType = feed.season_type ?? null;
const now = new Date().toISOString();

const prev = readJSON(OUT) || {};
const games = (prev.games && typeof prev.games === 'object') ? prev.games : {};   // carry ALL prior keys forward (retain finished)

let created = 0, moved = 0, seen = 0;

for (const g of feed.vegas_games) {
  if (!g.away || !g.home) continue;
  seen++;
  const key = [season, seasonType, week, g.away + '@' + g.home].join('|');
  const cur = snapshot(g, now);
  const rec = games[key];

  if (!rec) {
    games[key] = {
      season, seasonType, week, away: g.away, home: g.home, commence: g.commence || null,
      open: cur, cur, firstSeen: now, lastSeen: now, samples: [noQ(cur)],
    };
    trackLead(games[key], g, now);
    created++;
    continue;
  }
  rec.lastSeen = now;
  rec.commence = g.commence || rec.commence || null;
  trackLead(rec, g, now);
  const last = rec.samples && rec.samples.length ? rec.samples[rec.samples.length - 1] : rec.open;
  if (!last || sig(last) !== sig(cur)) {
    rec.cur = cur;
    rec.samples = rec.samples || [noQ(rec.open)];
    rec.samples.push(noQ(cur));
    if (rec.samples.length > MAX_SAMPLES) rec.samples.splice(1, rec.samples.length - MAX_SAMPLES); // keep open (idx 0), drop oldest middles
    moved++;
  } else {
    rec.cur = cur;   // ts refresh only; not a movement
  }
}

// ── News flag → data/line_news.json ─────────────────────────────────────
// A line that moves NEWS_PTS+ from where it sat NEWS_BASE_D days before kickoff
// (the lookahead, before the previous week's games) almost always means news
// the model can't see: a QB out, a benching. 2026 Wks 2-3: 4 of 85 games moved
// 4+ on the spread (PHI@CHI, SEA@WAS, SEA@ARI, CAR@ATL), all QB news, and they
// produced the model's biggest phantom gaps (CHI -2.3 vs the market's +4.5 for
// five days before the Caleb Williams adjustment landed). A flagged game gets
// no Vault Game Play until the model catches up. The same matchup can sit under
// several week tags in this file, so samples are pooled by (away, home, kickoff).
const NEWS_PTS = 4, NEWS_BASE_D = 10;
function lineNews() {
  const pool = {};
  for (const r of Object.values(games)) {
    if (!r.commence) continue;
    const k = r.away + '@' + r.home + '|' + r.commence;
    (pool[k] = pool[k] || { away: r.away, home: r.home, commence: r.commence, s: [] }).s.push(...(r.samples || []));
  }
  const out = {}, t = Date.parse(now);
  for (const P of Object.values(pool)) {
    const kick = Date.parse(P.commence);
    if (!Number.isFinite(kick) || kick <= t - 6 * 3600e3) continue;          // finished
    const S = P.s.filter(x => x && x.ts && Date.parse(x.ts) < kick).sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
    const cut = kick - NEWS_BASE_D * 86400e3, last = S[S.length - 1];
    if (!last) continue;
    const move = {};
    for (const mk of ['spread', 'total']) {
      const base = S.filter(x => x[mk] != null && Date.parse(x.ts) <= cut).pop();
      const cur = [...S].reverse().find(x => x[mk] != null);
      if (base && cur && Math.abs(cur[mk] - base[mk]) >= NEWS_PTS)
        move[mk] = { from: base[mk], to: cur[mk], since: base.ts };
    }
    if (Object.keys(move).length) out[P.away + '@' + P.home] = { commence: P.commence, ...move };
  }
  return out;
}
const NEWS = lineNews();
log(`line news: ${Object.keys(NEWS).length} flagged` + (Object.keys(NEWS).length ? ' (' + Object.keys(NEWS).join(', ') + ')' : ''));

const payload = { generated: now, season, seasonType, week, keys: Object.keys(games).length, games };
log(`${seen} live games · ${created} new keys · ${moved} moved · ${payload.keys} total banked`);
if (DRY) { log('--dry: not written'); process.exit(0); }
writeFileSync(OUT, JSON.stringify(payload));
log('wrote ' + OUT);
const NEWS_OUT = resolve(dirname(OUT), 'line_news.json');
writeFileSync(NEWS_OUT, JSON.stringify({ generated: now, rule: { pts: NEWS_PTS, base_days: NEWS_BASE_D }, games: NEWS }));
log('wrote ' + NEWS_OUT);
