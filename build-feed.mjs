#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · LINEUP COMMAND — daily projection feed builder
   ────────────────────────────────────────────────────────────────────────
   Runs once a day (see daily-projections.yml). Pulls projections from the
   sources below, normalizes them onto Sleeper player_ids, computes a real
   Defense-vs-Position (DvP) table, and writes:

       lineup_command/feed/latest.json

   …which the Lineup Command UI fetches and prefers over its modeled spread.
   The app degrades gracefully if this file is absent, so deploying the cron
   is purely additive — nothing breaks if a source is down on a given day.

   SHAPE written:
   {
     "season": "2026", "week": 1, "generated": "2026-09-03T09:00:00Z",
     "players": { "<sleeperId>": { "sources": { "sleeper": 18.4, "espn": 17.9,
                  "cbs": 18.1, "nfl": 17.6, "draftkings": 19.0 } } },
     "dvp": { "BUF": { "QB": {"fpa":16.8,"rank":9}, "RB": {...}, ... }, ... }
   }

   SOURCE STATUS (be honest about this — see README):
     • sleeper     ✅ turnkey   — free read API, no key
     • espn        ✅ turnkey   — public read endpoint (no auth for projections)
     • dvp         ✅ turnkey   — COMPUTED from Sleeper stats + schedule (real)
     • cbs         ⚠️  adapter   — needs a maintained scrape selector
     • nfl         ⚠️  adapter   — needs a maintained scrape selector
     • draftkings  ⚠️  salary-implied — DFS salaries, not a true projection
   Adapters that return {} are simply skipped; the UI shows the sources we
   actually have and models the rest. Wire a licensed feed (FantasyPros /
   Sportradar) into one adapter to make all five authoritative.

   Requires Node 18+ (global fetch). No npm install needed for the turnkey set.
   ════════════════════════════════════════════════════════════════════════ */

import { writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';

const SLEEPER = 'https://api.sleeper.com';
const OUT = new URL('../feed/latest.json', import.meta.url).pathname;
const SKILL = new Set(['QB', 'RB', 'WR', 'TE']);
const POS_IDX = { QB: 0, RB: 1, WR: 2, TE: 3 };

const jget = async (url, opts = {}) => {
  const r = await fetch(url, { headers: { 'user-agent': 'vault-lineup-cron/1.0' }, ...opts });
  if (!r.ok) throw new Error(`HTTP ${r.status} ${url}`);
  return r.json();
};
const norm = s => (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]/g, '');

/* ── 0. current season / week ─────────────────────────────────────────── */
async function getState() {
  const s = await jget(`${SLEEPER}/state/nfl`);
  return { season: s.season, week: s.display_week || s.week || s.leg || 1 };
}

/* ── player id resolver (name+team → sleeperId), built from Sleeper ─────── */
async function buildResolver(rows) {
  // Sleeper projection rows already embed player meta — no 5MB players file needed.
  const map = {}; // "name|team" -> sleeperId
  for (const row of rows) {
    const pl = row.player || {};
    const id = String(row.player_id);
    const name = norm(`${pl.first_name || ''}${pl.last_name || ''}`);
    const team = (pl.team || row.team || '').toUpperCase();
    if (name && team) map[`${name}|${team}`] = id;
  }
  return map;
}

/* ── 1. SLEEPER (consensus) ✅ ────────────────────────────────────────── */
async function srcSleeper(season, week) {
  const url = `${SLEEPER}/projections/nfl/${season}/${week}?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE&order_by=pts_ppr`;
  const rows = await jget(url);
  const out = {};
  for (const row of rows) {
    const pl = row.player || {};
    if (!SKILL.has(pl.position)) continue;
    const ppr = row.stats?.pts_ppr;
    if (ppr == null) continue;
    out[String(row.player_id)] = round(ppr);
  }
  return { values: out, rows };
}

/* ── 2. ESPN (free read endpoint) ✅ ──────────────────────────────────────
   ESPN exposes fantasy projections without auth via the read host. We pull
   the kona_player_info view and read the "projected" stat split (id 10).   */
async function srcESPN(season, week, resolver) {
  try {
    const url = `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/${season}/segments/0/leaguedefaults/3?view=kona_player_info`;
    const filter = {
      players: {
        limit: 1500,
        filterStatsForExternalIds: { value: [Number(season)] },
        filterStatsForSourceIds: { value: [1] },
        filterStatsForSplitTypeIds: { value: [1] },
        sortPercOwned: { sortPriority: 1, sortAsc: false },
      },
    };
    const data = await jget(url, { headers: { 'x-fantasy-filter': JSON.stringify(filter) } });
    const out = {};
    for (const p of data.players || []) {
      const info = p.player || {};
      const name = norm(info.fullName || '');
      const team = ESPN_TEAM[info.proTeamId] || '';
      const id = resolver[`${name}|${team}`];
      if (!id) continue;
      // find the weekly projection stat entry (statSourceId 1 = projections)
      const wk = (info.stats || []).find(s => s.statSourceId === 1 && s.scoringPeriodId === week);
      const pts = wk?.appliedTotal;
      if (pts != null) out[id] = round(pts);
    }
    return out;
  } catch (e) { warn('espn', e); return {}; }
}

/* ── 3. DvP — COMPUTED from real Sleeper stats + schedule ✅ ───────────────
   Fantasy points (PPR) each defense has allowed to each position, per game,
   over completed weeks of the current season (falls back to prior season in
   the early weeks). Ranked 1 (toughest) … 32 (softest).                    */
async function buildDvP(season, week) {
  try {
    const completed = [];
    for (let w = 1; w < week; w++) completed.push(w);
    let useSeason = season, weeks = completed;
    if (weeks.length < 2) { useSeason = String(Number(season) - 1); weeks = range(1, 17); } // preseason → last year
    const schedule = await getSchedule(useSeason);
    const allow = {}; // team -> [QBpts, RBpts, WRpts, TEpts], and games count
    const games = {};
    for (const w of weeks) {
      let rows;
      try { rows = await jget(`${SLEEPER}/stats/nfl/${useSeason}/${w}?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE`); }
      catch { continue; }
      const sched = schedule[w] || {};
      for (const row of rows) {
        const pl = row.player || {};
        const pos = pl.position; if (!SKILL.has(pos)) continue;
        const pts = row.stats?.pts_ppr; if (pts == null) continue;
        const team = (pl.team || row.team || '').toUpperCase();
        const opp = (sched[team] || row.opponent || '').toUpperCase();
        if (!opp) continue;
        (allow[opp] = allow[opp] || [0, 0, 0, 0])[POS_IDX[pos]] += pts;
      }
      for (const tm of Object.keys(sched)) games[tm] = (games[tm] || 0) + 1;
    }
    // per-game averages
    const perGame = {};
    for (const tm of Object.keys(allow)) {
      const g = Math.max(1, (games[tm] || weeks.length));
      perGame[tm] = allow[tm].map(v => round(v / g));
    }
    // ranks per position (1 = fewest allowed = toughest)
    const dvp = {};
    for (const pos of ['QB', 'RB', 'WR', 'TE']) {
      const i = POS_IDX[pos];
      const order = Object.keys(perGame).sort((a, b) => perGame[a][i] - perGame[b][i]);
      order.forEach((tm, idx) => { (dvp[tm] = dvp[tm] || {})[pos] = { fpa: perGame[tm][i], rank: idx + 1 }; });
    }
    return dvp;
  } catch (e) { warn('dvp', e); return null; }
}
async function getSchedule(season) {
  // { week: { TEAM: OPP } }
  const out = {};
  try {
    const data = await jget(`${SLEEPER}/schedule/nfl/regular/${season}`);
    for (const g of data || []) {
      const w = g.week; if (!w) continue;
      const home = (g.home || '').toUpperCase(), away = (g.away || '').toUpperCase();
      if (!home || !away) continue;
      out[w] = out[w] || {}; out[w][home] = away; out[w][away] = home;
    }
  } catch (e) { warn('schedule', e); }
  return out;
}

/* ── 4. CBS / NFL.com adapters ⚠️ (stubs with the real entry points) ──────
   These have no free JSON API; they need an HTML scrape with a selector that
   ESPN/CBS change a few times a year, or a licensed feed. Returning {} means
   the UI simply models that column until you wire it. Replace the body with
   your scrape (cheerio) or a licensed call and map onto sleeperIds.         */
async function srcCBS(season, week, resolver) {
  // e.g. fetch a CBS weekly projections page and parse the table, then:
  //   out[ resolver[`${norm(name)}|${team}`] ] = points;
  return {}; // TODO: scrape https://www.cbssports.com/fantasy/football/stats/.../projections
}
async function srcNFL(season, week, resolver) {
  return {}; // TODO: scrape https://fantasy.nfl.com/research/projections
}
/* ── 5. DraftKings ⚠️ (DFS salaries → directional, not a true projection) ─ */
async function srcDraftKings(season, week, resolver) {
  // DK publishes salaries via draftgroups; convert salary→implied points if desired.
  return {}; // TODO: optional — salary-implied estimate only
}

/* ── orchestrate ──────────────────────────────────────────────────────── */
async function main() {
  const { season, week } = await getState();
  log(`Building feed for ${season} week ${week}…`);

  const { values: sleeper, rows } = await srcSleeper(season, week);
  const resolver = await buildResolver(rows);
  log(`  sleeper: ${Object.keys(sleeper).length} players`);

  const [espn, cbs, nfl, dk, dvp] = await Promise.all([
    srcESPN(season, week, resolver),
    srcCBS(season, week, resolver),
    srcNFL(season, week, resolver),
    srcDraftKings(season, week, resolver),
    buildDvP(season, week),
  ]);
  log(`  espn: ${Object.keys(espn).length} · cbs: ${Object.keys(cbs).length} · nfl: ${Object.keys(nfl).length} · dk: ${Object.keys(dk).length} · dvp teams: ${dvp ? Object.keys(dvp).length : 0}`);

  // merge per player
  const players = {};
  const put = (map, key) => { for (const id of Object.keys(map)) { (players[id] = players[id] || { sources: {} }).sources[key] = map[id]; } };
  put(sleeper, 'sleeper'); put(espn, 'espn'); put(cbs, 'cbs'); put(nfl, 'nfl'); put(dk, 'draftkings');

  const feed = { season, week, generated: new Date().toISOString(), players, ...(dvp ? { dvp } : {}) };
  await mkdir(dirname(OUT), { recursive: true });
  await writeFile(OUT, JSON.stringify(feed));
  log(`Wrote ${OUT} — ${Object.keys(players).length} players, ${Math.round(JSON.stringify(feed).length / 1024)}KB`);
}

/* ── helpers ──────────────────────────────────────────────────────────── */
const round = n => Math.round(n * 10) / 10;
const range = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => a + i);
const log = (...a) => console.log(...a);
const warn = (src, e) => console.warn(`  [skip ${src}] ${e.message || e}`);
const ESPN_TEAM = { 1: 'ATL', 2: 'BUF', 3: 'CHI', 4: 'CIN', 5: 'CLE', 6: 'DAL', 7: 'DEN', 8: 'DET', 9: 'GB', 10: 'TEN', 11: 'IND', 12: 'KC', 13: 'LV', 14: 'LAR', 15: 'MIA', 16: 'MIN', 17: 'NE', 18: 'NO', 19: 'NYG', 20: 'NYJ', 21: 'PHI', 22: 'ARI', 23: 'PIT', 24: 'LAC', 25: 'SF', 26: 'SEA', 27: 'TB', 28: 'WAS', 29: 'CAR', 30: 'JAX', 33: 'BAL', 34: 'HOU' };

main().catch(e => { console.error('FEED BUILD FAILED:', e); process.exit(1); });
