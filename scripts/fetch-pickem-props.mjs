#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · PICK'EM PROPS  →  vegas_player_props
   ────────────────────────────────────────────────────────────────────────
   Free, keyless player-prop feed for the Betting tab. Pulls three DFS pick'em
   boards DIRECTLY:
     • PrizePicks     (partner-api.prizepicks.com — the public api host is
                       Cloudflare-blocked)
     • Underdog       (api.underdogfantasy.com over/under lines)
     • Sleeper        (api.sleeper.com native pick'em — priced, native ids)
     • Pinnacle       (guest.api.arcadia.pinnacle.com — the sharp book's
                       two-way player props, posted near kickoff)
   Resolves each player to its Sleeper id (Sleeper's board already carries it),
   maps each book's stat types to Vault's market keys, and merges the result
   into data/lineup-feed.json under `vegas_player_props` — the exact shape
   betting-data.js already consumes. No API key, no credits. (Sleeper posts no
   game spreads/totals/moneylines — its board is player props only — so the
   game-markets tab stays on ParlayAPI / the Odds API / ESPN.)

   All three books are hit DIRECTLY here, so this job is authoritative and
   fresher than ParlayAPI's mirror of them: on a market ParlayAPI already
   carries, we upsert the direct quote and correct a stale headline line
   rather than only gap-filling (see mergeFeed).

   Cell shape written (matches betting-data.js):
     lines[marketKey] = {
       line, over, under, book,
       quotes:[{book,line,over,under}],
       best:{ over:{book,price}|null, under:{book,price}|null },
       pickem:true                      // flag: single-number line, no 2-sided price
     }

   Pick'em lines have no two-sided American price, so over/under are null. The
   grid renders the line; prices show as "—". (A later UI tweak can label
   pick'em columns "PICK" instead.)

   Run:
     node scripts/fetch-pickem-props.mjs                 # fetch live, merge feed
     node scripts/fetch-pickem-props.mjs --dry           # fetch, print summary, write nothing
     node scripts/fetch-pickem-props.mjs --force         # write even if 0 props (clears stale)
   Offline test (no network):
     node scripts/fetch-pickem-props.mjs --dry \
       --pp-fixture=scripts/_pp.sample.json \
       --sleeper-fixture=scripts/_sleeper.sample.json

   Env / flags:
     --feed=PATH         feed json to merge into        (default data/lineup-feed.json)
     --league=ID         PrizePicks league id           (default 9 = NFL)
     --pp-fixture=PATH   read PrizePicks json from file instead of network
     --sleeper-fixture=PATH  read Sleeper players json from file instead of network
   ════════════════════════════════════════════════════════════════════════ */
'use strict';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { repairCell } from './prop-quote-guard.mjs';

/* ── args ─────────────────────────────────────────────────────────────── */
const ARG = Object.fromEntries(process.argv.slice(2).map(a => {
  const m = a.match(/^--([^=]+)(?:=(.*))?$/); return m ? [m[1], m[2] ?? true] : [a, true];
}));
const DRY      = !!ARG.dry;
const FORCE    = !!ARG.force;
const FEED     = ARG.feed     || 'data/lineup-feed.json';
const LEAGUE   = String(ARG.league || 9);            // 9 = NFL on PrizePicks
const PP_FIX   = ARG['pp-fixture'] || null;
const SL_FIX   = ARG['sleeper-fixture'] || null;
const UD_FIX   = ARG['ud-fixture'] || null;
const SLN_FIX  = ARG['sleeper-lines-fixture'] || null;
const NO_UD    = !!ARG['no-underdog'];
const NO_PP    = !!ARG['no-prizepicks'];
const NO_SL    = !!ARG['no-sleeper'];
const NO_PIN   = !!ARG['no-pinnacle'];
const PIN_FIX  = ARG['pin-fixture'] || null;      // {matchups:[...], markets:[...]} saved from the guest API

// api.prizepicks.com/projections is Cloudflare-blocked (403) for keyless
// server-side callers. partner-api.prizepicks.com serves the same JSON:API
// board and is still reachable, so we hit that host instead.
const PP_HOST = ARG['pp-host'] || 'partner-api.prizepicks.com';

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15';
const log = (...a) => console.log('[pickem]', ...a);

/* ── identity helpers (mirror betting-data.js normName) ───────────────── */
const normName = s => (s || '').toLowerCase().normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '').replace(/\b(jr|sr|ii|iii|iv|v)\b/g, '').replace(/[^a-z]/g, '');

/* ── PrizePicks stat_type → Vault market key ──────────────────────────── */
/* matched by normalized contains, longest-key first so "pass+rush" wins over "rush" */
const STAT_MAP = [
  ['passrushyards',  'pass_rush_yd'],
  ['passrushyds',    'pass_rush_yd'],
  ['rushrecyards',   'rush_rec_yd'],
  ['rushrecyds',     'rush_rec_yd'],
  ['passingyards',   'pass_yd'],
  ['passyards',      'pass_yd'],
  ['passingtds',     'pass_td'],
  ['passtds',        'pass_td'],
  ['passtouchdowns', 'pass_td'],
  ['passcompletions','pass_cmp'],
  ['completions',    'pass_cmp'],
  ['passattempts',   'pass_att'],
  ['interceptions',  'pass_int'],
  ['longestcompletion','long_pass'],
  ['rushingyards',   'rush_yd'],
  ['rushyards',      'rush_yd'],
  ['rushingtds',     'rush_td'],
  ['rushtds',        'rush_td'],
  ['rushattempts',   'rush_att'],
  ['carries',        'rush_att'],
  ['longestrush',    'long_rush'],
  ['receivingyards', 'rec_yd'],
  ['recyards',       'rec_yd'],
  ['rushrectds',     'rush_rec_td'],   // "Rush+Rec TDs" — must precede rectds so the combo doesn't read as receiving TDs
  ['receivingtds',   'rec_td'],
  ['rectds',         'rec_td'],
  ['receptions',     'rec'],
  ['longestreception','long_rec'],
  ['kickingpoints',  'kick_pts'],
  ['fgmade',         'fg_made'],
  ['fieldgoalsmade', 'fg_made'],
  ['tacklesassists', 'tackles'],
  ['tackles',        'tackles'],
  ['sacks',          'sacks'],
];
// Stat types that a naive substring match would MISread as a core market. These
// are alt/derived shapes, not the market line — surfacing one as e.g. Receptions
// puts a wrong number on the board:
//   • "(Combo)"            two-player parlays — the name resolves to one of them
//   • "in first N …"       capped segment props (fewer completions/yards/recs)
//   • "per carry"          a RATE (~4.5), not the counting stat
//   • "percentage"         a rate, not the counting stat
//   • "pass+rush+rec tds"  a total-TD parlay — reads as receiving TDs via "rec tds"
// Checked before STAT_MAP so the greedy `includes()` can't claim them. (A legit
// single-player "Rush+Rec TDs" still maps, via its own STAT_MAP entry above.)
const STAT_EXCLUDE = ['combo', 'infirst', 'percarry', 'percentage', 'passrushrectds'];
function marketKeyFor(statType) {
  const n = (statType || '').toLowerCase().replace(/[^a-z]/g, '');
  if (STAT_EXCLUDE.some(bad => n.includes(bad))) return null;
  for (const [needle, key] of STAT_MAP) if (n.includes(needle)) return key;
  return null;
}

/* ── fetch helpers ────────────────────────────────────────────────────── */
async function getJSON(url, label) {
  const r = await fetch(url, { headers: {
    'User-Agent': UA, 'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9', 'Origin': 'https://app.prizepicks.com',
    'Referer': 'https://app.prizepicks.com/',
  }});
  if (!r.ok) throw new Error(`${label} HTTP ${r.status}`);
  return r.json();
}
function readFixture(p) { return JSON.parse(readFileSync(p, 'utf8')); }

/* ── Sleeper name → {id,team,pos} map ─────────────────────────────────── */
async function loadSleeperMap() {
  const all = SL_FIX ? readFixture(SL_FIX)
    : await getJSON('https://api.sleeper.app/v1/players/nfl', 'sleeper');
  const map = {};        // normName -> {id,team,pos}
  const byNameTeam = {}; // normName+team -> {id,team,pos}  (disambiguates dup names)
  const byId = {};       // sleeperId -> {id,name,team,pos}  (Sleeper lines carry native ids)
  const depth = {};      // sleeperId -> [depth_chart_order, active] — the "will they play" signal
  const status = {};     // sleeperId -> 'out'|'doubtful'|'questionable'|'active' (gameday health)
  const INACTIVE = /inactive|physically unable|injured reserve|\bpup\b|\bir\b|suspend|^out$|\bna\b|not active/i;
  for (const id in all) {
    const p = all[id];
    if (!p || !['QB', 'RB', 'WR', 'TE', 'K', 'LB', 'DB', 'DL'].includes(p.position)) continue;
    const nm = p.full_name || `${p.first_name || ''} ${p.last_name || ''}`;
    const key = normName(nm); if (!key) continue;
    const team = (p.team || '').toUpperCase() || null;
    const rec = { id, team, pos: p.position };
    if (!map[key]) map[key] = rec;
    if (team) byNameTeam[key + ':' + team] = rec;
    byId[id] = { id, name: nm.trim(), team, pos: p.position };
    // depth-chart order (1 = starter) + active flag, for the Best Bets starter
    // gate. Only skill positions the props tab covers; keeps the map small.
    if (['QB', 'RB', 'WR', 'TE'].includes(p.position) && team) {
      const dco = Number.isFinite(p.depth_chart_order) ? p.depth_chart_order : null;
      const st = String(p.injury_status || p.status || '');
      const inactive = p.active === false || INACTIVE.test(st);
      depth[id] = [dco, inactive ? 0 : 1];
      // Finer-grained health for the OUT badge + teammate ripple. Sleeper flips
      // injury_status to "Out" for the 90-min pregame inactive list, so this is
      // the live gameday signal — refreshed hourly on the free props run.
      status[id] = inactive ? 'out'
        : /doubt/i.test(st) ? 'doubtful'
        : /quest/i.test(st) ? 'questionable'
        : 'active';
    }
  }
  return { map, byNameTeam, byId, depth, status };
}

/* ── OUT detection + teammate ripple ──────────────────────────────────────
   Sunday inactives (posted ~90 min pre-kickoff) never reach Vault's frozen prop
   model, so a ruled-OUT starter keeps a stale line + starter projection (phantom
   edge), and his teammates are projected off a lineup that no longer exists. We
   don't invent replacement numbers — we FLAG so the board can void the OUT
   player's props and WITHHOLD the lean/grade on impacted teammates.

   Ripple rules (deliberately conservative — a withheld flag can only hide an
   edge, never fabricate one, so erring wide is safe):
     • QB1 out  → every skill teammate impacted (whole passing game re-rates).
     • RB1 out  → same-team RBs impacted (vacated backfield share).
     • WR1 out  → same-team WRs impacted (vacated target share).
   Doubtful flags only the player's own props (self-caution), no ripple.

   Backup RB out (p.backupOut, NOT p.impacted): the remaining lead back now
   carries the whole backfield, so his volume UNDERS are projected off a
   committee that no longer exists (Warren wk 4 2026: Dowdle out, books at 75.5
   rush yds / 17.5 att, Vault at 48.6 off a shared-backfield history, and the
   rec yds Under still made Best Bets). Only his unders are held, in
   build_best_bets; his overs are still scored. "Lead back" = the healthy RB the
   books price highest on rush yds, so a stale depth chart can't misname him.  */
function applyStatusFlags(feed, sl) {
  const status = (sl && sl.status) || {};
  const depth = (sl && sl.depth) || {};
  const byId = (sl && sl.byId) || {};
  const props = feed.vegas_player_props || {};

  // A lost QB1 has posted passing props (books only price a starter's pass yds),
  // so props-presence is the robust "was the starter" signal — depth_chart_order
  // is often stale or null on Sleeper, which is why a ripple keyed only on
  // dco===1 misses a benched-listed starter. RB1/WR1 use dco (their vacated
  // share is position-local and low-harm to withhold either way).
  const hasPassProps = id => {
    const l = (props[id] && props[id].lines) || {};
    return !!(l.pass_yd || l.pass_td || l.pass_rush_yd);
  };
  // Once a starter has been out a few days, books pull his props and Sleeper
  // demotes him on the depth chart (Caleb Williams wk 3 2026: listed 3rd behind
  // Keenum), so neither signal above fires. The QB who started the team's LAST
  // game counts too: if he is out, the lineup the projections lean on just
  // changed. Not the season attempts leader: a fill-in who started wks 1-2
  // (Cooper Rush, ATL) would flag the real starter's RETURN as a QB loss.
  const primaryQB = lastStarterQBs(feed.season, sl);
  const teamOut = {};   // team -> { QB:bool, RB:bool, WR:bool }
  for (const id in status) {
    if (status[id] !== 'out') continue;
    const rec = byId[id]; if (!rec || !rec.team) continue;
    const dco = depth[id] ? depth[id][0] : null;
    const starter = rec.pos === 'QB' ? (dco === 1 || hasPassProps(id) || primaryQB[rec.team] === id) : (dco === 1);
    if (!starter) continue;                          // only a lost STARTER ripples
    (teamOut[rec.team] = teamOut[rec.team] || {})[rec.pos] = true;
  }

  // A backup RB counts as "having a role" when he is RB2 on the depth chart or
  // the books posted props for him (Dowdle had no depth entry, but a line).
  const rbOut = {};     // team -> names of out non-starter RBs
  for (const id in status) {
    if (status[id] !== 'out') continue;
    const rec = byId[id]; if (!rec || !rec.team || rec.pos !== 'RB') continue;
    const dco = depth[id] ? depth[id][0] : null;
    if (dco === 1 || (teamOut[rec.team] && teamOut[rec.team].RB)) continue;   // starter: the RB1 ripple covers it
    const hasLines = !!(props[id] && Object.keys(props[id].lines || {}).length);
    if (dco === 2 || hasLines) (rbOut[rec.team] = rbOut[rec.team] || []).push(rec.name || (props[id] && props[id].name) || id);
  }
  const leadRB = {};    // team -> id of the healthy RB with the highest rush_yd line
  for (const id in props) {
    const p = props[id], team = p.team || (byId[id] || {}).team;
    if (!rbOut[team] || (p.pos || (byId[id] || {}).pos) !== 'RB' || status[id] === 'out' || status[id] === 'doubtful') continue;
    const c = (p.lines || {}).rush_yd, L = c && c.line != null ? Number(c.line) : null;
    if (L == null || !Number.isFinite(L)) continue;
    if (!leadRB[team] || L > leadRB[team].L) leadRB[team] = { id, L };
  }

  const SKILL = new Set(['QB', 'RB', 'WR', 'TE']);   // ripple never touches K/DEF/IDP props
  const out = [], impacted = [], backup = [];
  for (const id in props) {
    const p = props[id];
    delete p.out; delete p.outStatus; delete p.impacted; delete p.impactedBy; delete p.backupOut;  // idempotent
    const st = status[id];
    const rec = byId[id] || {};
    const team = p.team || rec.team;
    const pos = p.pos || rec.pos;

    if (st === 'out') {                              // player himself is ruled out → void
      p.out = true; p.outStatus = 'out';
      out.push({ id, name: p.name, team, pos });
      continue;
    }
    if (st === 'doubtful') {                         // ~coin-flip → withhold, don't void
      p.impacted = true; p.impactedBy = 'doubtful';
      impacted.push({ id, name: p.name, team, pos, by: 'doubtful' });
      continue;
    }

    if (leadRB[team] && leadRB[team].id === id) {
      p.backupOut = 'RB2 out';
      backup.push({ id, name: p.name, team, pos, by: 'RB2 out', out: rbOut[team] });
    }
    const to = team && SKILL.has(pos) && teamOut[team];
    if (!to) continue;
    let by = null;
    if (to.QB) by = 'QB out';                        // passing game re-rates → all skill
    else if (to.RB && pos === 'RB') by = 'RB1 out';
    else if (to.WR && pos === 'WR') by = 'WR1 out';
    if (by) { p.impacted = true; p.impactedBy = by; impacted.push({ id, name: p.name, team, pos, by }); }
  }

  feed.vegas_status = {
    generated: new Date().toISOString(),
    source: 'sleeper-injury',
    out_count: out.length,
    impacted_count: impacted.length,
    teams_qb_out: Object.keys(teamOut).filter(t => teamOut[t].QB),
    out, impacted, backup_out: backup,
  };
  return { out: out.length, impacted: impacted.length, backup: backup.length };
}
/* Game-model backup QB (data/qb_status.json). build_game_model.py fits the
   points a backup start costs and names each team's ESTABLISHED starter
   (game_model.json qb.established), but it refits twice a week and QB news
   breaks hourly, so this run decides who is on a backup: the established QB is
   OUT on Sleeper, or benched (he has no passing props while the depth-chart #1
   QB does; books only price a starter). Its own file, not the feed: the lineup
   job rewrites lineup-feed.json between props runs. Keys are the game model's
   team codes (LA, not LAR). */
const QB_STATUS = 'data/qb_status.json';
const GM_TEAM = { LA: 'LAR' };   // game-model code -> Sleeper code
function gameQbStatus(feed, sl) {
  let gm;
  try { gm = JSON.parse(readFileSync('data/game_model.json', 'utf8')); } catch (e) { return null; }
  const est = (gm.qb && gm.qb.established) || {};
  const status = sl.status || {}, depth = sl.depth || {}, byId = sl.byId || {};
  const props = feed.vegas_player_props || {};
  const passProps = id => { const l = (props[id] && props[id].lines) || {}; return !!(l.pass_yd || l.pass_td || l.pass_rush_yd); };
  const teams = {};
  for (const t in est) {
    const slTeam = GM_TEAM[t] || t;
    const rec = resolveSleeper(sl, est[t].name, slTeam);
    if (!rec || rec.pos !== 'QB' || rec.team !== slTeam) continue;   // moved on: no established QB to lose
    const qbs = Object.values(byId).filter(r => r.team === slTeam && r.pos === 'QB' && r.id !== rec.id);
    const top = qbs.find(r => depth[r.id] && depth[r.id][0] === 1);
    let reason = null;
    if (status[rec.id] === 'out') reason = 'out';
    else if (top && !passProps(rec.id) && passProps(top.id)) reason = 'benched';
    if (!reason) continue;
    const starter = qbs.find(r => passProps(r.id)) || top || null;
    teams[t] = { backup: true, reason, established: est[t].name, starter: starter ? starter.name : null };
  }
  return { generated: new Date().toISOString(), note: 'Teams whose established QB (game_model.json qb.established) is out or benched. The game model takes qb.margin / qb.total points off them.', teams };
}

/* QB news timing (data/qb_news_log.json). Every change in qb_status (a team
   goes onto a backup, comes back, or changes backups) is appended with the
   time THIS run saw it. scripts/build_qb_news_lag.py grades each one against
   the line history: had the spread already moved when Vault noticed, or did it
   move after? Only a move AFTER is an edge you can bet. Append-only. */
const QB_NEWS_LOG = 'data/qb_news_log.json';
function logQbNews(next) {
  let prev = {}, log_ = { events: [] };
  try { prev = JSON.parse(readFileSync(QB_STATUS, 'utf8')).teams || {}; } catch (e) { /* first run */ }
  try { log_ = JSON.parse(readFileSync(QB_NEWS_LOG, 'utf8')); } catch (e) { /* first run */ }
  if (!Array.isArray(log_.events)) log_.events = [];
  const cur = next.teams || {}, t = next.generated, add = [];
  for (const team of new Set([...Object.keys(prev), ...Object.keys(cur)])) {
    const a = prev[team], b = cur[team];
    if (!a && b) add.push({ t, team, kind: 'out', reason: b.reason, established: b.established, starter: b.starter });
    else if (a && !b) add.push({ t, team, kind: 'back', established: a.established, starter: a.established });
    else if (a && b && a.starter !== b.starter) add.push({ t, team, kind: 'starter', reason: b.reason, established: b.established, starter: b.starter, was: a.starter });
  }
  if (!add.length) return;
  log_.events.push(...add);
  writeFileSync(QB_NEWS_LOG, JSON.stringify(log_, null, 1));
  log(`QB news: ${add.map(e => `${e.team} ${e.kind}${e.starter ? ' (' + e.starter + ')' : ''}`).join(', ')}`);
}

// team -> Sleeper id of the QB who started the team's most recent game (most
// pass attempts that week, nflverse weekly stats in data/). {} when missing.
function lastStarterQBs(season, sl) {
  const out = {};
  let blob;
  try { blob = JSON.parse(readFileSync(`data/nflverse_stats_${season}.json`, 'utf8')); } catch (e) { return out; }
  const last = {};   // team -> { wk, att, name }
  for (const p of (Array.isArray(blob) ? blob : Object.values(blob))) {
    if (!p || p.pos !== 'QB' || !p.team) continue;
    for (const w of p.weeks || []) {
      const wk = Number(w.wk), att = w.att || 0, b = last[p.team];
      if (!(att > 0)) continue;
      if (!b || wk > b.wk || (wk === b.wk && att > b.att)) last[p.team] = { wk, att, name: p.name };
    }
  }
  for (const t in last) {
    const rec = resolveSleeper(sl, last[t].name, t);
    if (rec && rec.pos === 'QB') out[rec.team || t] = rec.id;   // Sleeper team code (LAR, not nflverse LA)
  }
  return out;
}
function resolveSleeper(sl, name, team) {
  const key = normName(name); if (!key) return null;
  if (team && sl.byNameTeam[key + ':' + team.toUpperCase()]) return sl.byNameTeam[key + ':' + team.toUpperCase()];
  return sl.map[key] || null;
}

/* ── PrizePicks loader (paginated JSON:API) ───────────────────────────── */
async function loadPrizePicks() {
  let raw, firstPageError = null;
  if (PP_FIX) {
    raw = [readFixture(PP_FIX)];
  } else {
    raw = [];
    for (let page = 1; page <= 12; page++) {
      const url = `https://${PP_HOST}/projections?league_id=${LEAGUE}&per_page=250&single_stat=true&page=${page}`;
      let j;
      try { j = await getJSON(url, `prizepicks p${page}`); }
      catch (e) { log('fetch failed:', e.message); if (page === 1) firstPageError = e; break; }
      raw.push(j);
      const data = j.data || [];
      const totalPages = j.meta && j.meta.total_pages;
      if (!data.length) break;
      // partner-api returns the whole board on page 1 with no pagination meta —
      // paging further just refetches the same rows (and risks a 429). Stop
      // after the first page unless the host actually advertises more pages.
      if (!totalPages) break;
      if (page >= totalPages) break;
      await new Promise(r => setTimeout(r, 1200)); // be polite (partner-api throttles fast)
    }
  }
  // Surface a hard failure (Cloudflare block, network) by re-throwing — the
  // cron's outer catch logs it and exits 0, but the visible "ERROR:" log + the
  // 0-props line in the workflow tells you the pipeline broke vs. PP being empty.
  if (firstPageError) throw new Error(`PrizePicks unreachable (page 1): ${firstPageError.message}`);
  // flatten across pages
  const players = {}; // ppId -> {name,team,pos}
  const projections = [];
  for (const j of raw) {
    for (const inc of (j.included || [])) {
      if (inc.type === 'new_player' || inc.type === 'player') {
        const a = inc.attributes || {};
        players[inc.id] = {
          name: a.display_name || a.name || '',
          team: (a.team || a.team_name || '').toUpperCase() || null,
          pos: (a.position || '').toUpperCase() || null,
        };
      }
    }
    for (const d of (j.data || [])) {
      if (d.type !== 'projection') continue;
      const a = d.attributes || {};
      const rel = d.relationships || {};
      const ppId = rel.new_player?.data?.id || rel.player?.data?.id || null;
      projections.push({
        ppId,
        stat: a.stat_type || a.stat_display_name || '',
        line: a.line_score != null ? Number(a.line_score) : null,
        oddsType: a.odds_type || 'standard',   // standard | demon | goblin
        start: a.start_time || a.board_time || null,
        desc: a.description || '',
        status: a.status || null,
      });
    }
  }
  return { players, projections };
}

/* ── transform → vegas_player_props ───────────────────────────────────── */
function buildProps(pp, sl) {
  const out = {};           // sleeperId -> {lines, opp, commence}
  const seen = new Set();   // sleeperId|market — keep first standard line
  let events = new Set(), matched = 0, unmatched = 0, lines = 0;

  // STANDARD lines only. demon (higher, longshot) and goblin (lower, easy) are
  // payout-adjusted ALT lines, not the market number — treating one as the line
  // is how Cade Otton's receptions showed 7.5 (a demon) when PrizePicks offered
  // no standard receptions line at all. For 75 players this slate the receptions
  // market is demon/goblin-only; those correctly get NO PrizePicks quote rather
  // than a misleading longshot line. (Sort kept so a standard line always wins
  // its dedupe slot even if the board order ever changes.)
  const ordered = pp.projections.slice().sort((a, b) =>
    (a.oddsType === 'standard' ? 0 : 1) - (b.oddsType === 'standard' ? 0 : 1));

  for (const proj of ordered) {
    if (proj.line == null || !proj.ppId) continue;
    if (proj.oddsType && proj.oddsType !== 'standard') continue;   // drop demon/goblin alts
    if (proj.status && /^(suspended|inactive)$/i.test(proj.status)) continue;
    const market = marketKeyFor(proj.stat); if (!market) continue;
    const ppPlayer = pp.players[proj.ppId]; if (!ppPlayer) continue;

    const hit = resolveSleeper(sl, ppPlayer.name, ppPlayer.team);
    if (!hit) { unmatched++; continue; }
    const id = hit.id;
    const dedupe = id + '|' + market;
    if (seen.has(dedupe)) continue;
    seen.add(dedupe);

    if (!out[id]) {
      // Embed identity (name/team/pos) on the prop so the betting UI can
      // surface props for players the preseason workbook doesn't cover
      // (PrizePicks routinely posts lines for backups and lesser-known WRs
      // the workbook skips). Identity comes from the Sleeper resolver hit.
      out[id] = {
        name: ppPlayer.name || null,
        team: hit.team || ppPlayer.team || null,
        pos: hit.pos || ppPlayer.pos || null,
        lines: {}, opp: null, commence: null,
      };
    }
    const cell = {
      line: proj.line, over: null, under: null, book: 'PrizePicks',
      quotes: [{ book: 'PrizePicks', line: proj.line, over: null, under: null }],
      best: { over: null, under: null },
      pickem: true,
    };
    out[id].lines[market] = cell;
    if (proj.start && !out[id].commence) out[id].commence = proj.start;
    if (proj.desc && !out[id].opp) {
      const m = proj.desc.match(/\b([A-Z]{2,3})\b/);
      if (m) out[id].opp = m[1];
    }
    if (proj.start) events.add(proj.start.slice(0, 10));
    lines++;
  }
  matched = Object.keys(out).length;
  return { props: out, stats: { players: matched, unmatched, lines, events: events.size } };
}

/* ── Underdog Fantasy ───────────────────────────────────────────────────
   Keyless board feed: ONE call to /beta/v5/over_under_lines returns every
   sport flattened into parallel arrays (players, appearances, games,
   over_under_lines). We keep NFL game-level lines (drop the season-long and
   in-period splits), map Underdog stat keys to Vault market keys, resolve each
   player to a Sleeper id, and emit the same cell shape as PrizePicks.

   ParlayAPI only mirrors Underdog for TD markets, so without this Underdog's
   yardage lines never reach the tab — leaving every QB yardage prop single-
   source (PrizePicks only) with nothing to cross-check a bad line against. */
const UD_STAT_MAP = {
  passing_yds: 'pass_yd', passing_tds: 'pass_td', passing_comps: 'pass_cmp',
  passing_att: 'pass_att', passing_ints: 'pass_int', passing_long: 'long_pass',
  passing_and_rushing_yds: 'pass_rush_yd',
  rushing_yds: 'rush_yd', rushing_tds: 'rush_td', rushing_att: 'rush_att',
  rushing_long: 'long_rush',
  // Underdog's receptions key is `receiving_rec` (NOT `receptions`, which it never
  // sends). The wrong key silently dropped EVERY Underdog receptions line league-
  // wide, leaving receptions single-source (PrizePicks-only) — how a lone stale
  // 5.5 on Omarion Hampton stood with nothing to cross-check it. Keep both keys
  // mapped in case Underdog renames back. Verified live: receiving_rec = 167 lines.
  receiving_yds: 'rec_yd', receiving_tds: 'rec_td',
  receptions: 'rec', receiving_rec: 'rec',
  receiving_long: 'long_rec',
  rushing_and_receiving_yds: 'rush_rec_yd', rush_rec_yds: 'rush_rec_yd',
  rush_rec_tds: 'rush_rec_td',   // combined rush+rec TD O/U — Underdog's largest market (~380 lines/slate)
  field_goals_made: 'fg_made', kicking_points: 'kick_pts',
  tackles: 'tackles', sacks: 'sacks',
};
const udAmerican = s => { const n = parseInt(s, 10); return Number.isFinite(n) ? n : null; };

async function loadUnderdog() {
  let j;
  if (UD_FIX) { j = readFixture(UD_FIX); }
  else {
    // /beta/v5 is now version-gated (HTTP 426 "upgrade required") for keyless
    // callers, which silently soft-failed this source and FROZE every Underdog
    // line in the feed — how Cade Otton's receptions stuck at a stale 0.5 (a
    // 1st-quarter alt) while his real line was 3.5. /v1 is the current keyless
    // board and returns the identical response shape (players / appearances /
    // over_under_lines), so the parse below is unchanged.
    const r = await fetch('https://api.underdogfantasy.com/v1/over_under_lines', {
      headers: { 'User-Agent': UA, 'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.9' },
    });
    if (!r.ok) throw new Error(`underdog HTTP ${r.status}`);
    j = await r.json();
  }
  const players = Object.fromEntries((j.players || []).map(p => [p.id, p]));
  const apps    = Object.fromEntries((j.appearances || []).map(a => [a.id, a]));
  // team_id → abbr from each game's "AWAY @ HOME" title (Underdog only exposes
  // team UUIDs on the player; the abbr is what the Sleeper resolver needs).
  const teamAbbr = {};
  for (const g of [...(j.games || []), ...(j.solo_games || [])]) {
    const m = String(g.abbreviated_title || '').match(/([A-Z]{2,3})\s*@\s*([A-Z]{2,3})/);
    if (m) { if (g.away_team_id) teamAbbr[g.away_team_id] = m[1]; if (g.home_team_id) teamAbbr[g.home_team_id] = m[2]; }
  }
  const lines = [];
  for (const l of j.over_under_lines || []) {
    if (l.line_type && l.line_type !== 'balanced') continue;   // skip boosted/special
    const as = l.over_under && l.over_under.appearance_stat; if (!as) continue;
    const stat = as.stat || '';
    if (/^(season_|period_)/.test(stat)) continue;             // game lines only
    const market = UD_STAT_MAP[stat]; if (!market) continue;
    const app = apps[as.appearance_id]; if (!app) continue;
    const player = players[app.player_id]; if (!player || player.sport_id !== 'NFL') continue;
    const opts = l.options || [];
    const over  = opts.find(o => o.choice === 'higher' || o.choice === 'over');
    const under = opts.find(o => o.choice === 'lower'  || o.choice === 'under');
    lines.push({
      name: `${player.first_name || ''} ${player.last_name || ''}`.trim(),
      team: teamAbbr[player.team_id] || null,
      pos: player.position_name || null,
      market,
      line: l.stat_value != null ? Number(l.stat_value) : null,
      over:  over  ? udAmerican(over.american_price)  : null,
      under: under ? udAmerican(under.american_price) : null,
    });
  }
  return { lines };
}

function buildUnderdog(ud, sl) {
  const out = {}; const seen = new Set();
  let matched = 0, unmatched = 0, count = 0;
  for (const row of ud.lines) {
    if (row.line == null) continue;
    const hit = resolveSleeper(sl, row.name, row.team);
    if (!hit) { unmatched++; continue; }
    const id = hit.id;
    const dedupe = id + '|' + row.market;
    if (seen.has(dedupe)) continue;          // one representative line per market
    seen.add(dedupe);
    if (!out[id]) out[id] = { name: row.name || null, team: hit.team || row.team || null, pos: hit.pos || row.pos || null, lines: {}, opp: null, commence: null };
    out[id].lines[row.market] = {
      line: row.line, over: row.over, under: row.under, book: 'Underdog Fantasy',
      quotes: [{ book: 'Underdog Fantasy', line: row.line, over: row.over, under: row.under }],
      best: { over: null, under: null },
      pickem: true,
    };
    count++;
  }
  matched = Object.keys(out).length;
  return { props: out, stats: { players: matched, unmatched, lines: count } };
}

/* ── Sleeper (native pick'em) ───────────────────────────────────────────
   /lines/available returns EVERY sport's over/under pick'em lines flat. The
   NFL slice (sport:"nfl") is player props only — Sleeper posts no game
   spreads/totals/moneylines, so this adds a third BOOK to the props tab, not
   the game-markets tab. Two things make it the cleanest source:
     • subject_id IS the Sleeper player id — no name resolution, no dup-name
       mismatch (the one failure mode PrizePicks/Underdog can hit).
     • each side carries a payout_multiplier (decimal odds), so unlike flat
       pick'em these quotes are PRICED — real over/under American odds.
   Sleeper prices every line (no flat "standard" line), and a player+market can
   carry alt lines; we keep the one whose over/under payouts are most balanced,
   which is the primary line (alts are lopsided by design).                  */
const SLEEPER_STAT_MAP = {
  passing_yards: 'pass_yd', rushing_yards: 'rush_yd', receiving_yards: 'rec_yd',
  receptions: 'rec', passing_touchdowns: 'pass_td', interceptions: 'pass_int',
  // anytime_touchdowns is intentionally excluded — the Anytime TD board uses a
  // separate prob-based cell shape, not a line-based quote.
};
// decimal payout multiplier → American odds (dec is the total-return multiple).
function decToAmerican(dec) {
  const d = Number(dec);
  if (!Number.isFinite(d) || d <= 1) return null;
  return d >= 2 ? Math.round((d - 1) * 100) : -Math.round(100 / (d - 1));
}

async function loadSleeperLines() {
  let arr;
  if (SLN_FIX) { arr = readFixture(SLN_FIX); }
  else {
    const r = await fetch('https://api.sleeper.com/lines/available?dynamic=true&include_preseason=true', {
      headers: { 'User-Agent': UA, 'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.9' },
    });
    if (!r.ok) throw new Error(`sleeper-lines HTTP ${r.status}`);
    arr = await r.json();
  }
  if (!Array.isArray(arr)) return { lines: [] };
  const lines = [];
  for (const l of arr) {
    const over = (l.options || []).find(o => o.outcome === 'over');
    const under = (l.options || []).find(o => o.outcome === 'under');
    const o = over || under || (l.options || [])[0]; if (!o) continue;
    if (o.sport !== 'nfl') continue;                     // nfl = game props (nfl_szn = season-long)
    if (o.subject_type !== 'player') continue;
    const market = SLEEPER_STAT_MAP[o.wager_type]; if (!market) continue;
    const pid = o.subject_id; if (!pid) continue;
    const line = o.outcome_value != null ? Number(o.outcome_value) : null; if (line == null) continue;
    const om = over ? Number(over.payout_multiplier) : null;
    const um = under ? Number(under.payout_multiplier) : null;
    lines.push({
      pid: String(pid), market, line,
      over: decToAmerican(om), under: decToAmerican(um),
      team: (o.subject_team || '').toUpperCase() || null,
      pos: (o.subject_position || '').toUpperCase() || null,
      balance: (om != null && um != null) ? Math.abs(om - um) : Infinity,  // primary line = most balanced
    });
  }
  return { lines };
}

function buildSleeper(sln, sl) {
  const out = {};
  const best = new Map();       // id|market → chosen row (most balanced payouts)
  let matched = 0, unknown = 0, count = 0;
  for (const row of sln.lines) {
    const ident = sl.byId[row.pid];
    if (!ident) { unknown++; continue; }                 // id not in the Sleeper player map (rare)
    const key = row.pid + '|' + row.market;
    const cur = best.get(key);
    if (!cur || row.balance < cur.balance) best.set(key, { row, ident });
  }
  for (const { row, ident } of best.values()) {
    const id = ident.id;
    if (!out[id]) out[id] = { name: ident.name || null, team: ident.team || row.team || null, pos: ident.pos || row.pos || null, lines: {}, opp: null, commence: null };
    out[id].lines[row.market] = {
      line: row.line, over: row.over, under: row.under, book: 'Sleeper',
      quotes: [{ book: 'Sleeper', line: row.line, over: row.over, under: row.under }],
      best: { over: null, under: null },
      pickem: true,
    };
    count++;
  }
  matched = Object.keys(out).length;
  return { props: out, stats: { players: matched, unmatched: unknown, lines: count } };
}

/* ── Pinnacle (sharp book) ──────────────────────────────────────────────
   Pinnacle's public web API (the same guest key scripts/book_tape.py and
   fetch-sharp-money.mjs use for game lines) lists NFL player props with
   two-way prices, usually a day or two before kickoff. Pinnacle is the
   market-making book, so its no-vig price is the sharp anchor the board and
   settlement measure against. Before this, 83% of Week 4 props were priced
   only by pick'em apps (docs/retro/week-4-deep-dive.md). Limits are low
   ($250 to $1,000 a bet), so treat it as a reference price more than a place
   to bet size. Matchups come from the sport-level endpoint (the league-level
   one is geo-blocked from some US IPs), filtered to the NFL league (889).
   Players resolve to Sleeper ids only when Sleeper has them on one of the two
   teams in that game, so a shared name can never cross games.             */
const PIN_BASE = 'https://guest.api.arcadia.pinnacle.com/0.1';
const PIN_KEY = 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R';     // Pinnacle's public web-client key
const PIN_NFL = 889;
const PIN_UNITS = {
  'Receiving Yards': 'rec_yd', Receptions: 'rec', 'Rushing Yards': 'rush_yd', 'Rush Attempts': 'rush_att',
  'Passing Yards': 'pass_yd', 'Pass Attempts': 'pass_att', 'Pass Completions': 'pass_cmp',
  'Touchdown Passes': 'pass_td', Interceptions: 'pass_int',
  // 'Touchdowns' (a player's total TDs) is left out: for a QB it is not the
  // same stat as any Vault market, so it would need its own mapping first.
};
const PIN_NICK = {
  Cardinals: 'ARI', Falcons: 'ATL', Ravens: 'BAL', Bills: 'BUF', Panthers: 'CAR', Bears: 'CHI', Bengals: 'CIN',
  Browns: 'CLE', Cowboys: 'DAL', Broncos: 'DEN', Lions: 'DET', Packers: 'GB', Texans: 'HOU', Colts: 'IND',
  Jaguars: 'JAX', Chiefs: 'KC', Chargers: 'LAC', Rams: 'LAR', Raiders: 'LV', Dolphins: 'MIA', Vikings: 'MIN',
  Patriots: 'NE', Saints: 'NO', Giants: 'NYG', Jets: 'NYJ', Eagles: 'PHI', Steelers: 'PIT', Seahawks: 'SEA',
  '49ers': 'SF', Buccaneers: 'TB', Titans: 'TEN', Commanders: 'WAS',
};

async function pinJSON(path) {
  const headers = { 'X-API-Key': PIN_KEY, Referer: 'https://www.pinnacle.com/', Origin: 'https://www.pinnacle.com',
                    'User-Agent': UA, Accept: 'application/json' };
  let last = null;
  for (let i = 0; i < 5; i++) {               // the guest API now and then 403s a cloud IP for a few seconds
    try {
      const r = await fetch(PIN_BASE + path, { headers });
      if (r.ok) return await r.json();
      last = `HTTP ${r.status}`;
    } catch (e) { last = e.message; }
    await new Promise(res => setTimeout(res, 1500 * (i + 1)));
  }
  throw new Error(`pinnacle ${path}: ${last}`);
}

async function loadPinnacle() {
  let mus, mks;
  if (PIN_FIX) ({ matchups: mus, markets: mks } = readFixture(PIN_FIX));
  else {
    mus = await pinJSON('/sports/15/matchups');
    mks = await pinJSON(`/leagues/${PIN_NFL}/markets/straight`);
  }
  const now = Date.now();
  const team = p => p && PIN_NICK[String(p.name || '').split(' ').pop()];
  const games = {};                            // parent matchup id -> { home, away, start }
  for (const m of mus || []) {
    if (m.type !== 'matchup' || m.parentId || (m.league || {}).id !== PIN_NFL) continue;
    const h = (m.participants || []).find(p => p.alignment === 'home');
    const a = (m.participants || []).find(p => p.alignment === 'away');
    if (team(h) && team(a)) games[m.id] = { home: team(h), away: team(a), start: m.startTime };
  }
  const specials = {};                         // special id -> { name, market, overId, underId, game }
  for (const m of mus || []) {
    const sp = m.special || {};
    if (m.type !== 'special' || sp.category !== 'Player Props' || (m.league || {}).id !== PIN_NFL) continue;
    const market = PIN_UNITS[m.units]; if (!market) continue;
    const game = games[m.parentId]; if (!game) continue;
    // A prop whose own start isn't its game's start is a leftover listing
    // (seen live: two Sunday-dated props hanging off the Monday game).
    if (Date.parse(m.startTime) !== Date.parse(game.start) || Date.parse(game.start) <= now) continue;
    const nm = String(sp.description || '').match(/^(.*?)\s+Total\s+/); if (!nm) continue;
    const over = (m.participants || []).find(p => p.name === 'Over');
    const under = (m.participants || []).find(p => p.name === 'Under');
    if (over && under) specials[m.id] = { name: nm[1].trim(), market, overId: over.id, underId: under.id, game };
  }
  const lines = [];
  for (const x of mks || []) {
    const sp = specials[x.matchupId];
    if (!sp || x.type !== 'total' || x.period !== 0 || x.isAlternate) continue;
    if (x.cutoffAt && Date.parse(x.cutoffAt) <= now) continue;
    const po = (x.prices || []).find(p => p.participantId === sp.overId);
    const pu = (x.prices || []).find(p => p.participantId === sp.underId);
    if (!po || !pu || po.points == null || po.points !== pu.points || po.price == null || pu.price == null) continue;
    lines.push({ name: sp.name, market: sp.market, line: Number(po.points), over: po.price, under: pu.price, game: sp.game });
  }
  return { lines };
}

function buildPinnacle(pin, sl) {
  const out = {};
  let unmatched = 0, count = 0;
  for (const row of pin.lines) {
    const g = row.game, key = normName(row.name);
    const hit = sl.byNameTeam[key + ':' + g.home] || sl.byNameTeam[key + ':' + g.away] || null;
    if (!hit) { unmatched++; continue; }
    const id = hit.id;
    const home = hit.team === g.home;
    if (!out[id]) out[id] = { name: row.name, team: hit.team, pos: hit.pos || null, lines: {},
                              opp: home ? g.away : g.home, ha: home ? 'home' : 'away', commence: g.start };
    if (out[id].lines[row.market]) continue;   // one main line per market (alternates are skipped above)
    const q = { book: 'Pinnacle', line: row.line, over: row.over, under: row.under };
    out[id].lines[row.market] = {
      line: row.line, over: row.over, under: row.under, book: 'Pinnacle', quotes: [q],
      best: { over: { book: 'Pinnacle', price: row.over, line: row.line }, under: { book: 'Pinnacle', price: row.under, line: row.line } },
    };
    count++;
  }
  return { props: out, stats: { players: Object.keys(out).length, unmatched, lines: count } };
}

/* line-first best price for a side (mirrors src-vegas.mjs bestSide): a lower
   line is strictly better for an OVER, a higher line for an UNDER; price only
   breaks a tie. Recomputed after upserting a keyless quote. */
function bestSide(quotes, side) {
  const better = side === 'over' ? (a, b) => a < b : (a, b) => a > b;
  return quotes.reduce((best, q) => {
    if (q[side] == null) return best;
    const cand = { book: q.book, price: q[side], line: q.line ?? null };
    if (!best) return cand;
    if (cand.line != null && best.line != null && cand.line !== best.line)
      return better(cand.line, best.line) ? cand : best;
    return cand.price > best.price ? cand : best;
  }, null);
}

/* ── merge into feed ──────────────────────────────────────────────────────
   MERGE, don't replace. ParlayAPI (run by build-lineup-feed.mjs every 6h) is
   the richer source for two-sided BOOK prices, but it MIRRORS PrizePicks /
   Underdog lines and can serve them stale (that mirror is how Drake Maye's
   pass-yds line got stuck at 169.5 when the real PrizePicks/Underdog line was
   229.5). This hourly keyless job hits PrizePicks and Underdog DIRECTLY, so
   for those two books it is the authoritative, fresher source. Policy:

     • market missing            → add the keyless cell (gap-fill, as before)
     • market present            → UPSERT this book's quote into the cell:
         - replace/insert the same-book quote with the fresh line + prices
         - if the cell's headline book IS this book, refresh cell.line too
           (this is what corrects a stale mirrored line)
         - recompute best over/under across the cell's quotes
       Other books' quotes are never dropped, so nothing flip-flops between
       rich ParlayAPI odds and bare keyless lines — we only correct the number
       and add the missing cross-check quote.                                */
function upsertQuote(cell, fresh, book) {
  cell.quotes = cell.quotes || [];
  const q = { book, line: fresh.line ?? null, over: fresh.over ?? null, under: fresh.under ?? null };
  const i = cell.quotes.findIndex(x => x.book === book);
  if (i >= 0) cell.quotes[i] = q; else cell.quotes.push(q);
  // headline book is this book → its direct line is authoritative
  // Prices move WITH the line: a price-less refresh (PrizePicks never sends
  // one) used to keep the old line's prices under the new number, which is how
  // a 0.5 line banked 1.5-line prices. repairCell (end of mergeFeed) refills
  // the headline from whatever other books quote at this exact line.
  if (cell.book === book && fresh.line != null) {
    cell.line = fresh.line;
    cell.over = fresh.over ?? null;
    cell.under = fresh.under ?? null;
  }
  cell.best = cell.best || {};
  cell.best.over  = bestSide(cell.quotes, 'over');
  cell.best.under = bestSide(cell.quotes, 'under');
}

/* ── prune stale pick'em quotes ────────────────────────────────────────────
   MERGE never removes a quote, so a line this job stops emitting (a demon-only
   PrizePicks receptions cell, or an Underdog alt that self-corrects) lingers
   forever as a stale cross-check — and can still win best.over/under. This job
   is the AUTHORITATIVE source for exactly three books, so for each of them that
   returned a HEALTHY pull this run, drop that book's quotes for any player+
   market the fresh board no longer carries. ParlayAPI books (Fanatics, Fliff,
   DK, …) are never touched — this job doesn't own them. A thin/failed pull
   (book absent from `sources`, or under PRUNE_MIN players) prunes nothing, so a
   soft-fail can't wipe a book's last-good lines.                              */
const OWNED_PICKEM = new Set(['PrizePicks', 'Underdog Fantasy', 'Sleeper', 'Pinnacle']);   // every book this job pulls directly
const PRUNE_MIN = 20;   // players a book must cover this run before we trust it to prune

function reHeadline(cell) {
  // headline book's quote was just removed — promote the best remaining quote
  // (prefer one with two-sided prices, else any) so the cell keeps a valid line.
  const qs = cell.quotes || [];
  const pick = qs.find(q => q.over != null && q.under != null)
            || qs.find(q => q.over != null || q.under != null)
            || qs[0];
  if (!pick) return false;
  cell.book = pick.book; cell.line = pick.line ?? null;
  cell.over = pick.over ?? null; cell.under = pick.under ?? null;
  return true;
}

function pruneStalePickem(existing, sources) {
  let removedQuotes = 0, droppedCells = 0;
  for (const { props, book } of sources) {
    if (!OWNED_PICKEM.has(book)) continue;
    const fresh = new Set(); let players = 0;
    for (const id in (props || {})) { players++; for (const mk in (props[id].lines || {})) fresh.add(id + '|' + mk); }
    if (players < PRUNE_MIN) continue;                      // thin pull — don't trust it to purge
    for (const id in existing) {
      const cell = existing[id].lines || {};
      for (const mk in cell) {
        const c = cell[mk]; if (!c || !Array.isArray(c.quotes)) continue;
        const keyFresh = fresh.has(id + '|' + mk);
        if (keyFresh) continue;                             // still offered — upsert already refreshed it
        const before = c.quotes.length;
        c.quotes = c.quotes.filter(q => q.book !== book);   // this book no longer offers this cell
        if (c.quotes.length === before) continue;
        removedQuotes += before - c.quotes.length;
        if (!c.quotes.length) { delete cell[mk]; droppedCells++; continue; }
        if (c.book === book) reHeadline(c);                 // stale book was the headline
        c.best = c.best || {};
        c.best.over  = bestSide(c.quotes, 'over');
        c.best.under = bestSide(c.quotes, 'under');
      }
      if (existing[id].lines && !Object.keys(existing[id].lines).length) delete existing[id];
    }
  }
  if (removedQuotes) log(`pruned ${removedQuotes} stale pick'em quote(s), dropped ${droppedCells} empty cell(s)`);
}

const TEAM_ALIAS = { LA: 'LAR', WSH: 'WAS', JAC: 'JAX', LVR: 'LV', OAK: 'LV', SD: 'LAC', STL: 'LAR' };
const teamKey = t => { t = String(t || '').toUpperCase(); return TEAM_ALIAS[t] || t; };
const LIVE_GRACE_MS = 4 * 3600e3;   // a game in progress is still "next" for its team

function retagMatchups(existing, sources, games) {
  // team → its soonest game that hasn't finished (schedule, not the week label,
  // so a Thursday team whose game is done rolls to next week on its own)
  const now = Date.now(), next = {};
  for (const g of (games || [])) {
    const t = Date.parse(g && g.commence); if (!Number.isFinite(t) || t < now - LIVE_GRACE_MS) continue;
    for (const [team, opp, ha] of [[g.home, g.away, 'home'], [g.away, g.home, 'away']]) {
      const k = teamKey(team); if (!k) continue;
      if (!next[k] || t < next[k].t) next[k] = { t, opp, ha, commence: g.commence };
    }
  }
  const fresh = new Map();   // id → Set of markets a pick'em book quoted this run
  for (const { props, book } of sources) if (OWNED_PICKEM.has(book))
    for (const id in (props || {})) { const s = fresh.get(id) || new Set(); for (const mk in (props[id].lines || {})) s.add(mk); fresh.set(id, s); }
  let n = 0, droppedQ = 0, droppedC = 0;
  for (const [id, mks] of fresh) {
    const p = existing[id], g = p && next[teamKey(p.team)];
    if (!g) continue;                                     // bye / unknown team: leave as is
    if (p.opp === g.opp && p.commence === g.commence && p.ha === g.ha) continue;
    // A REAL opponent change means every sportsbook quote on this player was
    // priced for the old game: build-lineup-feed sets opp whenever ParlayAPI
    // prices a player, so an old opp proves its last quote predates this week.
    // Drop those, keeping only this run's pick'em quotes, or last week's
    // Pinnacle rec_yd would read as this week's line after the re-tag.
    if (p.opp && teamKey(p.opp) !== teamKey(g.opp)) {
      for (const mk in (p.lines || {})) {
        const c = p.lines[mk];
        const keep = mks.has(mk) ? (c.quotes || []).filter(q => OWNED_PICKEM.has(q.book)) : [];
        droppedQ += (c.quotes || []).length - keep.length;
        if (!keep.length) { delete p.lines[mk]; droppedC++; continue; }
        c.quotes = keep;
        if (!keep.some(q => q.book === c.book)) reHeadline(c);
        c.best = { over: bestSide(c.quotes, 'over'), under: bestSide(c.quotes, 'under') };
      }
      if (!Object.keys(p.lines || {}).length) { delete existing[id]; continue; }
    }
    p.opp = g.opp; p.commence = g.commence; p.ha = g.ha; n++;
  }
  if (droppedQ) log(`matchup re-tag: dropped ${droppedQ} prior-game sportsbook quote(s), ${droppedC} empty cell(s)`);
  return n;
}

function mergeFeed(sources, stats, sl) {
  const depth = sl && sl.depth;
  if (!existsSync(FEED)) { log('feed not found, nothing to merge:', FEED); return false; }
  const feed = JSON.parse(readFileSync(FEED, 'utf8'));
  const existing = feed.vegas_player_props || {};
  const had = Object.keys(existing).length;

  if (!stats.players && !FORCE) {
    log(`0 props parsed — leaving existing feed untouched (had ${had}). Use --force to clear.`);
    return false;
  }

  let addedPlayers = 0, addedMarkets = 0, refreshed = 0;
  for (const { props, book } of sources) {
    for (const id in (props || {})) {
      const src = props[id];
      if (!existing[id]) { existing[id] = src; addedPlayers++; continue; }
      const cur = existing[id];
      // backfill identity / matchup if the richer feed left any of it blank
      cur.name = cur.name || src.name; cur.team = cur.team || src.team; cur.pos = cur.pos || src.pos;
      cur.opp = cur.opp || src.opp; cur.commence = cur.commence || src.commence;
      cur.lines = cur.lines || {};
      for (const mk in (src.lines || {})) {
        if (!cur.lines[mk]) { cur.lines[mk] = src.lines[mk]; addedMarkets++; continue; }
        // market already present — upsert this book's fresh, direct quote so a
        // stale mirrored line self-corrects and the cross-check quote appears
        upsertQuote(cur.lines[mk], src.lines[mk], book);
        refreshed++;
      }
    }
  }

  // Purge stale quotes for the pick'em books that refreshed healthily this run,
  // so a line no longer on their board can't linger as a bad cross-check.
  pruneStalePickem(existing, sources);

  // Re-tag the matchup of every player a pick'em book quoted THIS run. The
  // backfill above only fills a blank opp, and only PrizePicks sends one, so a
  // player refreshed hourly by Underdog/Sleeper kept LAST week's opp forever:
  // Week 3 had 14 of 29 starting QBs (Allen, Herbert, Burrow…) tagged to their
  // Week 2 opponent, and every slate gate dropped them as off-slate. A live
  // quote means the book is pricing the team's next game, so take opp/commence
  // from the schedule. Players with no fresh quote keep their old tag and stay
  // off-slate, which is correct for a line nobody is offering any more.
  const retagged = retagMatchups(existing, sources, feed.vegas_games);
  if (retagged) log(`matchup re-tag: ${retagged} player(s) moved to their next game`);

  // Position-impossible line guard. A QB never has a receptions market — such a
  // cell is always a cross-source name collision (two "Josh Allen"s: the Bills
  // QB and a defender), which no single book/source owns, so drop it wherever it
  // came from. This is the ONLY direction that's universally safe: non-QBs DO
  // throw on trick plays (Taysom Hill), so passing lines are not guarded.
  const QB_FORBIDDEN = ['rec', 'rec_yd', 'rec_td', 'long_rec'];
  let posDropped = 0;
  for (const id in existing) {
    if (existing[id].pos !== 'QB') continue;
    for (const mk of QB_FORBIDDEN) if (existing[id].lines && existing[id].lines[mk]) { delete existing[id].lines[mk]; posDropped++; }
  }
  if (posDropped) log(`position guard: dropped ${posDropped} impossible QB receiving line(s)`);

  // Quote guard + headline rebuild on EVERY cell (prop-quote-guard.mjs): drop a
  // quote that contradicts the rest of its cell (a 0.5 priced less likely to go
  // over than the 1.5 beside it: Weeks 1-2 carried 91 such Underdog period
  // lines), then re-derive over/under from quotes at exactly cell.line. Runs
  // last so upserts, prunes and re-tags above can't leave a cross-line pair.
  let guardDropped = 0;
  for (const id in existing) {
    const lines = existing[id].lines || {};
    for (const mk in lines) {
      const n = repairCell(lines[mk], mk);
      guardDropped += n;
      if (n && !lines[mk].quotes.length) delete lines[mk];   // every quote contradicted another
    }
    if (existing[id].lines && !Object.keys(existing[id].lines).length) delete existing[id];
  }
  if (guardDropped) log(`quote guard: dropped ${guardDropped} contradictory quote(s)`);

  // Sleeper-team override: Sleeper is the authoritative CURRENT-team source, and
  // every entry keyed by a Sleeper id already carries that id — so force its team
  // to Sleeper's, overriding whatever a prop source (parlay-api) claimed. Prop
  // feeds lag on team changes and deep-bench players (measured: a WR still listed
  // on his old team while Sleeper had moved him), and that stale team wrongly
  // groups a player with the wrong roster (e.g. the role-anchor depth check).
  // Entries keyed by a non-Sleeper id (name-fallback), or where Sleeper has no
  // team (free agent), keep their source team as the best available.
  const byId = (sl && sl.byId) || {};
  let teamFixed = 0;
  for (const coll of [existing, feed.vegas_players]) {
    if (!coll) continue;
    for (const id in coll) {
      const st = byId[id] && byId[id].team;
      if (st && coll[id] && coll[id].team !== st) { coll[id].team = st; teamFixed++; }
    }
  }
  if (teamFixed) log(`sleeper-team override: corrected ${teamFixed} stale team(s)`);

  feed.vegas_player_props = existing;
  if (depth && Object.keys(depth).length) feed.vegas_depth = depth;   // [dco, active] per skill-player id
  feed.vegas_meta = feed.vegas_meta || {};
  // Only claim 'prizepicks' as the headline source when nothing richer set one.
  if (!feed.vegas_meta.props_source || feed.vegas_meta.props_source === 'none') feed.vegas_meta.props_source = 'prizepicks';
  feed.vegas_meta.props_players = Object.keys(existing).length;
  feed.vegas_meta.props_pp_filled = addedPlayers + addedMarkets;   // new cells this run
  feed.vegas_meta.props_pp_refreshed = refreshed;                  // same-book lines corrected
  feed.vegas_meta.props_quotes_rejected = guardDropped;            // quote guard drops this run
  feed.vegas_meta.props_pp_generated = new Date().toISOString();

  // Flag OUT players (void their props) + teammates whose projection assumes a
  // lineup that just changed (withhold their lean/grade). Free — reads the same
  // Sleeper injury feed already loaded above.
  const flags = applyStatusFlags(feed, sl);
  log(`status flags: ${flags.out} out/doubtful, ${flags.impacted} impacted teammates, ${flags.backup} lead backs with the backup out`);
  const qbs = gameQbStatus(feed, sl);
  if (qbs) log(`game-model QB status: backup QB for ${Object.keys(qbs.teams).join(', ') || 'no team'}`);

  const summary = `+${addedPlayers} players, +${addedMarkets} markets, ~${refreshed} refreshed — ${had} → ${Object.keys(existing).length}`;
  if (DRY) { log('DRY — would merge:', summary); return true; }
  writeFileSync(FEED, JSON.stringify(feed));
  if (qbs) { logQbNews(qbs); writeFileSync(QB_STATUS, JSON.stringify(qbs, null, 1)); }
  log(`merged into ${FEED}: ${summary}`);
  return true;
}

/* ── main ─────────────────────────────────────────────────────────────── */
(async () => {
  try {
    const sl = await loadSleeperMap();
    log('sleeper map:', Object.keys(sl.map).length, 'names');

    const sources = [];
    let totalPlayers = 0;

    // PrizePicks (partner-api) — soft-fail so an Underdog-only run still works
    if (!NO_PP) {
      try {
        const pp = await loadPrizePicks();
        log('prizepicks:', Object.keys(pp.players).length, 'players,', pp.projections.length, 'projections');
        const { props, stats } = buildProps(pp, sl);
        log(`  → mapped ${stats.players} players, ${stats.lines} lines, ${stats.unmatched} unmatched`);
        sources.push({ props, book: 'PrizePicks' });
        totalPlayers += stats.players;
      } catch (e) { log('prizepicks skipped:', e.message); }
    }

    // Underdog Fantasy — soft-fail so a PrizePicks-only run still works
    if (!NO_UD) {
      try {
        const ud = await loadUnderdog();
        log('underdog:', ud.lines.length, 'nfl game lines');
        const { props, stats } = buildUnderdog(ud, sl);
        log(`  → mapped ${stats.players} players, ${stats.lines} lines, ${stats.unmatched} unmatched`);
        sources.push({ props, book: 'Underdog Fantasy' });
        totalPlayers += stats.players;
      } catch (e) { log('underdog skipped:', e.message); }
    }

    // Sleeper (native pick'em) — priced quotes, resolved by native player id.
    // Replaces ParlayAPI's thin/stale "Sleeper" mirror with the direct board.
    if (!NO_SL) {
      try {
        const sln = await loadSleeperLines();
        log('sleeper:', sln.lines.length, 'nfl player lines');
        const { props, stats } = buildSleeper(sln, sl);
        log(`  → mapped ${stats.players} players, ${stats.lines} lines, ${stats.unmatched} unknown-id`);
        sources.push({ props, book: 'Sleeper' });
        totalPlayers += stats.players;
      } catch (e) { log('sleeper skipped:', e.message); }
    }

    // Pinnacle (sharp book) — two-way prices from the market maker, near kickoff.
    if (!NO_PIN) {
      try {
        const pin = await loadPinnacle();
        log('pinnacle:', pin.lines.length, 'nfl player lines');
        const { props, stats } = buildPinnacle(pin, sl);
        log(`  → mapped ${stats.players} players, ${stats.lines} lines, ${stats.unmatched} unmatched`);
        sources.push({ props, book: 'Pinnacle' });
        totalPlayers += stats.players;
      } catch (e) { log('pinnacle skipped:', e.message); }
    }

    mergeFeed(sources, { players: totalPlayers }, sl);
  } catch (e) {
    log('ERROR:', e.message);
    process.exit(0); // never fail the workflow / never wipe the feed on error
  }
})();
