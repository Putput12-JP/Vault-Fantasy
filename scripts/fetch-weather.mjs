#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · KICKOFF WEATHER  →  data/weather.json
   ────────────────────────────────────────────────────────────────────────
   Kickoff forecast for every game on the feed's slate (vegas_games), plus the
   measured passing-yards wind multiplier from data/wind_model.json.

     • venue: nflverse games.csv gives the real stadium per game, which is what
       catches neutral sites (a "home" DAL game in Rio is outdoors, not under
       AT&T's roof). Falls back to the home team's stadium (data/stadiums.json).
     • roof: dome / closed → no weather effect. A retractable roof with no
       announced status is treated as CLOSED (roof:'retractable', mult 1): the
       wind term only ever fires on a game we know is played outside.
     • wind: Open-Meteo wind_speed_10m (mph), mean over kickoff + next 2 hours,
       the same variable family build_wind_model.py fit on.
     • mult: { pass_yd: x } only when wind_model.json is active AND kickoff is
       within APPLY_DAYS (the fit used day-before forecasts). Readers
       (index.html matchupAdj, build_best_bets.mjs) take it straight from here,
       so the formula lives in one place and every reader falls back to ×1.

   Run:  node scripts/fetch-weather.mjs [--feed=data/lineup-feed.json] [--dry]
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const arg = k => (process.argv.find(a => a.startsWith(`--${k}=`)) || '').split('=')[1];
const FEED = resolve(ROOT, arg('feed') || 'data/lineup-feed.json');
const OUT = resolve(ROOT, 'data/weather.json');
const DRY = process.argv.includes('--dry');
const SHOW_DAYS = 7;    // forecast shown this far ahead
const APPLY_DAYS = 3;   // wind multiplier only applied this close to kickoff
const GAMES_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv';
const ALIAS = { OAK: 'LV', LVR: 'LV', SD: 'LAC', STL: 'LA', LAR: 'LA', WSH: 'WAS', JAC: 'JAX' };
const norm = t => { t = String(t || '').toUpperCase(); return ALIAS[t] || t; };
const r1 = x => (x == null ? null : Math.round(x * 10) / 10);

function readJson(p, dflt) { try { return JSON.parse(readFileSync(p, 'utf8')); } catch { return dflt; } }

// Minimal CSV (games.csv has quoted fields with commas in a few columns).
function parseCsv(text) {
  const rows = []; let row = [], f = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; }
    else if (c !== '\r') f += c;
  }
  if (f || row.length) { row.push(f); rows.push(row); }
  const [h, ...body] = rows;
  return body.map(r => Object.fromEntries(h.map((k, i) => [k, r[i]])));
}

async function venueIndex() {
  // key `${week}|${away}|${home}` → { sid, roof } for the current season
  try {
    const res = await fetch(GAMES_URL); if (!res.ok) return {};
    const rows = parseCsv(await res.text());
    const season = Math.max(...rows.map(r => +r.season || 0));
    const idx = {};
    for (const r of rows) if (+r.season === season)
      idx[`${r.week}|${norm(r.away_team)}|${norm(r.home_team)}`] = { sid: r.stadium_id, roof: r.roof || '' };
    return idx;
  } catch { return {}; }
}

function windMultFor(model, wind) {
  if (!model || model.active !== true || wind == null) return null;
  const k = Number(model.knot_mph), b = Number(model.slope_per_mph), lo = Number(model.floor);
  if (![k, b, lo].every(Number.isFinite)) return null;
  return Math.max(lo, Math.min(1, 1 + b * Math.max(0, wind - k)));
}

async function forecast(st, commence) {
  const t0 = new Date(commence); if (isNaN(t0)) return null;
  const day = d => d.toISOString().slice(0, 10);
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${st.lat}&longitude=${st.lon}` +
    `&hourly=wind_speed_10m,wind_gusts_10m,wind_direction_10m,temperature_2m,precipitation_probability` +
    `&wind_speed_unit=mph&temperature_unit=fahrenheit&timezone=GMT` +
    `&start_date=${day(t0)}&end_date=${day(new Date(+t0 + 4 * 3600e3))}`;
  for (let i = 0; i < 3; i++) {
    try {
      const res = await fetch(url); if (!res.ok) throw new Error(res.status);
      const h = (await res.json()).hourly; if (!h) return null;
      const start = Date.UTC(t0.getUTCFullYear(), t0.getUTCMonth(), t0.getUTCDate(), t0.getUTCHours());
      const at = [0, 1, 2].map(k => h.time.indexOf(new Date(start + k * 3600e3).toISOString().slice(0, 13) + ':00')).filter(i => i >= 0);
      if (!at.length) return null;
      const mean = key => { const xs = at.map(i => h[key][i]).filter(x => x != null); return xs.length ? xs.reduce((a, x) => a + x, 0) / xs.length : null; };
      return { wind: mean('wind_speed_10m'), gust: mean('wind_gusts_10m'), dir: h.wind_direction_10m[at[0]],
               temp: mean('temperature_2m'), precip: mean('precipitation_probability') };
    } catch (e) { await new Promise(r => setTimeout(r, 2000 * (i + 1))); }
  }
  return null;
}

async function main() {
  const feed = readJson(FEED, {});
  const stad = readJson(resolve(ROOT, 'data/stadiums.json'), { stadiums: {}, home_default: {} });
  const model = readJson(resolve(ROOT, 'data/wind_model.json'), null);
  const venues = await venueIndex();
  const now = Date.now(), out = [];
  for (const g of feed.vegas_games || []) {
    const home = norm(g.home), away = norm(g.away), t = Date.parse(g.commence);
    if (!home || !away || !Number.isFinite(t)) continue;
    if (t < now - 5 * 3600e3 || t > now + SHOW_DAYS * 86400e3) continue;  // played, or too far out to be worth showing
    const v = venues[`${g.week}|${away}|${home}`];
    const sid = (v && v.sid) || stad.home_default[home];
    const st = stad.stadiums[sid];
    if (!st) continue;
    // roof: games.csv status wins when announced; otherwise the stadium's type
    const roof = v && v.roof ? (['outdoors', 'open'].includes(v.roof) ? 'outdoor' : 'closed')
               : (st.roof === 'outdoor' ? 'outdoor' : st.roof);            // 'dome' | 'retractable'
    const row = { home: g.home, away: g.away, week: g.week, commence: g.commence, stadium: st.name, roof };
    if (roof === 'outdoor' || roof === 'retractable') {
      const f = await forecast(st, g.commence);
      if (f) Object.assign(row, { wind_mph: r1(f.wind), gust_mph: r1(f.gust), wind_dir: f.dir, temp_f: r1(f.temp), precip_pct: f.precip == null ? null : Math.round(f.precip) });
    }
    // The wind term was fit on DAY-BEFORE forecasts; a week-out forecast is much
    // noisier (day-3 already drops to r≈0.74 vs actual), so it's shown, not applied.
    const m = (roof === 'outdoor' && t - now <= APPLY_DAYS * 86400e3) ? windMultFor(model, row.wind_mph) : null;
    if (m != null && m < 1) row.mult = { pass_yd: Math.round(m * 1000) / 1000 };
    out.push(row);
  }
  const doc = { generated: new Date().toISOString(), model_active: !!(model && model.active), games: out };
  if (DRY) { console.log(JSON.stringify(doc, null, 1)); return; }
  writeFileSync(OUT, JSON.stringify(doc, null, 1) + '\n');
  console.log(`weather: ${out.length} games, ${out.filter(r => r.mult).length} with a wind adjustment`);
}
main().catch(e => { console.error(e); process.exit(1); });
