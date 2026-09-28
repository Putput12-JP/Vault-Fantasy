#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · PROP SNAPSHOT LOG  →  data/prop_line_history.json

   Banks the raw inputs needed to BACKTEST the Betting page, using data we
   already ship — no API calls, no credits. Two questions this feeds later:

     1. CLV (closing-line value) for the de-vig / line-shopping engine:
        did the price we flagged (open / best) beat the closing price?
        Answerable WITHOUT game outcomes — just open vs. close per side.
     2. Model Lean backtest: did "Over when proj > line" clear the ~52.4%
        break-even? Answerable by joining `proj_open`/`line` to the weekly
        actuals in data/nflverse_stats_<season>.json.

   Reads the lines already in data/lineup-feed.json:
     · vegas_player_props[pid].lines[market] → line, over, under, best prices
     · players[pid].stats[market]            → Vault projection (Model Lean)

   FREEZE + RETAIN, keyed by season|week|pid|market:
     · first time a key is seen, its snapshot is frozen as `open`;
     · every later run rolls `cur` forward and appends to `samples` only when
       something actually moved (quiet hours are free);
     · keys that leave the feed (game played, prop pulled) are KEPT untouched —
       a backtest needs finished weeks, so unlike line_history nothing is
       dropped. The week in the key means week N and N+1 never collide.

   Usage:  node scripts/snapshot-prop-history.mjs
           node scripts/snapshot-prop-history.mjs --feed=data/lineup-feed.json --out=data/prop_line_history.json --dry
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { repairCell, pricesAtLine, crossSampleVotes } from './prop-quote-guard.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const ARG = Object.fromEntries(process.argv.slice(2).map(a => { const [k, v] = a.replace(/^--/, '').split('='); return [k, v ?? true]; }));
const DRY = !!ARG.dry;
const FEED = ARG.feed ? resolve(process.cwd(), ARG.feed) : resolve(HERE, '..', 'data', 'lineup-feed.json');
const OUT = ARG.out ? resolve(process.cwd(), ARG.out) : resolve(HERE, '..', 'data', 'prop_line_history.json');
const MAX_SAMPLES = 80;            // per key; open is always kept, oldest extras drop
const log = (...a) => console.log('[prop-history]', ...a);

const DAY_MS = 864e5;
const readJSON = p => { try { return JSON.parse(readFileSync(p, 'utf8')); } catch { return null; } };
const num = v => (typeof v === 'number' && Number.isFinite(v) ? v : null);

// Combo yardage markets are derived in the app from base stats; mirror that so
// pass_rush_yd / rush_rec_yd carry a projection too.
function projFor(stats, mk) {
  if (!stats) return null;
  if (stats[mk] != null) return num(stats[mk]);
  if (mk === 'pass_rush_yd' && stats.pass_yd != null && stats.rush_yd != null) return num(stats.pass_yd + stats.rush_yd);
  if (mk === 'rush_rec_yd' && stats.rush_yd != null && stats.rec_yd != null) return num(stats.rush_yd + stats.rec_yd);
  return null;
}

// Best price a bettor could actually take on each side AT THE BANKED LINE.
// This used to scan every quote regardless of line (and the feed's line-first
// `best`), so bestOver could be a +614 alt on a different number. A book on
// another line is a different bet and is not priced against this one.
function bestPrices(cell) {
  if (!Array.isArray(cell.quotes) || !cell.quotes.length) return { bO: num(cell.over), bU: num(cell.under) };
  const at = pricesAtLine(cell.quotes, cell.line);
  return { bO: num(at.over), bU: num(at.under) };
}

function snapshot(cell, proj, ts) {
  const { bO, bU } = bestPrices(cell);
  return { line: num(cell.line), over: num(cell.over), under: num(cell.under), bestOver: bO, bestUnder: bU, proj: num(proj), ts };
}
// Per-book quotes, compact: [book, line, over, under]. Stored ONLY on the
// open and cur snapshots (not every sample) so the history file doesn't
// balloon; settlement reads open.q / q0 (first per-book read for props that
// predate this field) and cur.q to price +EV-by-book on the Track Record.
function bookQuotes(cell) {
  return (cell.quotes || [])
    .filter(q => q && q.book && (num(q.over) != null || num(q.under) != null))
    .map(q => [q.book, num(q.line), num(q.over), num(q.under)]);
}
/* ── Sharp-book lead tracker, props (2026-09-28) ─────────────────────────
   Same test as the game-line tracker (snapshot-game-history.mjs): does
   Pinnacle move first on props? Per prop, per lead book, the FIRST time its
   no-vig P(over) sits >= PROP_LEAD_GAP from the rec books' median at the SAME
   line (3h+ before kickoff), and those rec books' state at the close (their
   modal line + median P(over) at the lead line). FanDuel and DraftKings are
   controls: an off-the-pack book gets pulled back to the pack whoever it is.
   Graded by build_model_scoreboard.py; not shown in the app until GO. */
const PROP_LEAD_BOOKS = ['Pinnacle', 'FanDuel', 'DraftKings'];
const PROP_REC = new Set(['FanDuel', 'DraftKings', 'BetRivers', 'Hard Rock Bet', 'Fliff', 'BetMGM', 'Caesars', 'Fanatics', 'bet365', 'Parx Casino']);
const PROP_LEAD_GAP = 0.03, PROP_LEAD_MIN_H = 3;
const _imp = a => a == null ? null : (a < 0 ? -a / (-a + 100) : 100 / (a + 100));
function _devig(a, b) {
  const po = _imp(a), pu = _imp(b);
  if (!(po > 0) || !(pu > 0)) return null;
  if (po + pu <= 1) return po / (po + pu);
  let lo = 1, hi = 10; for (let i = 0; i < 40; i++) { const k = (lo + hi) / 2; if (po ** k + pu ** k > 1) lo = k; else hi = k; }
  const k = (lo + hi) / 2; return po ** k / (po ** k + pu ** k);
}
const _median = a => { const s = a.slice().sort((x, y) => x - y); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
function trackPropLead(rec, cell, nowMs, nowIso, kickMs) {
  if (!Number.isFinite(kickMs) || nowMs >= kickMs) return;
  const pb = {};                                   // book -> [line, P(over)]
  for (const q of cell.quotes || []) {
    if (!q || !q.book || num(q.line) == null) continue;
    const p = _devig(num(q.over), num(q.under)); if (p != null) pb[q.book] = [num(q.line), p];
  }
  const r3 = x => Math.round(x * 1000) / 1000;
  rec.lead = rec.lead || {};
  for (const b of PROP_LEAD_BOOKS) {
    const rb = Object.entries(pb).filter(([k]) => PROP_REC.has(k) && k !== b);
    if (rb.length < 2) continue;
    const cnt = {}; for (const [, [L]] of rb) cnt[L] = (cnt[L] || 0) + 1;
    const modal = +Object.entries(cnt).sort((x, y) => y[1] - x[1])[0][0];
    const L0 = (rec.lead[b] && rec.lead[b].first) ? rec.lead[b].first.line : (pb[b] ? pb[b][0] : null);
    const atL = L0 == null ? [] : rb.filter(([, [L]]) => L === L0).map(([, [, p]]) => p);
    const x = (rec.lead[b] = rec.lead[b] || {});
    x.close = { ts: nowIso, line: modal, p: atL.length ? r3(_median(atL)) : null };
    if (!x.first && pb[b] && atL.length >= 2 && (kickMs - nowMs) >= PROP_LEAD_MIN_H * 3600e3) {
      const r = _median(atL);
      if (Math.abs(pb[b][1] - r) >= PROP_LEAD_GAP) x.first = { ts: nowIso, line: pb[b][0], b: r3(pb[b][1]), r: r3(r) };
    }
  }
}
// Value signature — used to skip appending a duplicate sample.
const sig = s => [s.line, s.over, s.under, s.bestOver, s.bestUnder, s.proj].join('|');

const feed = readJSON(FEED);
if (!feed || !feed.vegas_player_props || typeof feed.vegas_player_props !== 'object') {
  log('no vegas_player_props in feed — nothing to snapshot'); process.exit(0);
}

const season = feed.season ?? null, week = feed.week ?? null, seasonType = feed.season_type ?? null;
const players = (feed.players && typeof feed.players === 'object') ? feed.players : {};
const now = new Date().toISOString();

const prev = readJSON(OUT) || {};
const props = (prev.props && typeof prev.props === 'object') ? prev.props : {};   // carry ALL prior keys forward (retain finished weeks)

let created = 0, moved = 0, seen = 0, contradicted = 0, started = 0, otherGame = 0;
const nowMs = Date.parse(now);

for (const pid in feed.vegas_player_props) {
  const p = feed.vegas_player_props[pid];
  if (!p || !p.lines) continue;
  const stats = players[pid] && players[pid].stats;
  // Kickoff of the game these lines are for. Nothing is banked at or after it:
  // once a game starts the books pull the market, so what's left is a stale
  // lone quote or a live in-game line, and settlement's "close" must be the
  // last PRE-game read. The feed also keeps cells from games already played
  // (a Week 1 line still in the Week 3 feed), and those carry the old
  // kickoff, so the same check keeps them out of this week's keys.
  const kickMs = Date.parse(p.commence || '');
  const commence = Number.isFinite(kickMs) ? new Date(kickMs).toISOString() : null;
  for (const mk in p.lines) {
    if (!p.lines[mk]) continue;
    // Defence in depth: the feed writers already run the quote guard, but this
    // is the point where prices become permanent, so re-run it on a copy. Only
    // prices quoted at exactly cell.line are banked (prop-quote-guard.mjs).
    const cell = JSON.parse(JSON.stringify(p.lines[mk]));
    repairCell(cell, mk);
    // real two-way only: need both prices (line may be null for prob-kind markets)
    if (cell.over == null || cell.under == null) continue;
    seen++;

    // seasonType is in the key so preseason week N and regular-season week N
    // (same season+week integers) never collide into one settlement record.
    const key = [season, seasonType, week, pid, mk].join('|');
    const rec = props[key];
    if (commence && nowMs >= kickMs) { started++; continue; }
    if (rec && rec.commence) {
      const recKick = Date.parse(rec.commence);
      if (nowMs >= recKick) { started++; continue; }
      // A kickoff a day+ away from the banked one is a different game: the
      // feed rolled to next week's lines while still tagged with this week.
      // (Hours of drift is a flex / time change and is followed.)
      if (commence && Math.abs(kickMs - recKick) > DAY_MS) { otherGame++; continue; }
    }
    const cur = snapshot(cell, projFor(stats, mk), now);
    const q = bookQuotes(cell);
    if (rec) trackPropLead(rec, cell, nowMs, now, Date.parse(commence || rec.commence || ''));
    const curQ = Object.assign({}, cur, { q });   // cur/open carry books; samples stay lean

    if (!rec) {
      props[key] = {
        season, week, seasonType, pid, name: p.name || null, team: p.team || null,
        pos: p.pos || null, opp: p.opp || null, ha: p.ha || null, market: mk, commence,
        open: curQ, cur: curQ, firstSeen: now, lastSeen: now, samples: [cur],
      };
      trackPropLead(props[key], cell, nowMs, now, kickMs);
      created++;
      continue;
    }
    if (commence) rec.commence = commence;
    // existing key: roll cur forward, append a sample only when something moved
    rec.lastSeen = now;
    // matchup rolls forward: the feed used to keep a player's prior-week opp
    // (fixed in fetch-pickem-props re-tag), so a row created then carries the
    // wrong opponent until the feed's corrected tag lands here.
    if (p.opp) rec.opp = p.opp;
    if (p.ha) rec.ha = p.ha;
    // A prop opened before per-book capture existed: bank its FIRST per-book
    // read once, so settlement has the earliest book prices we ever saw.
    if (!(rec.open && rec.open.q) && !rec.q0 && q.length) rec.q0 = { q, ts: now };
    const last = rec.samples && rec.samples.length ? rec.samples[rec.samples.length - 1] : rec.open;
    // Cross-snapshot guard: once every other book pulls a market (after
    // kickoff, typically) a stale lone quote has nothing left in its cell to
    // contradict, but this week's earlier snapshots on other lines still do.
    // A pair that contradicts most of them is not banked, so it can't become
    // the "close" (Kmet: 1.5 rec at -115 all week, then 0.5 at +149 Monday).
    const votes = crossSampleVotes(rec.samples, cur, mk);
    if (votes.of && votes.against * 2 > votes.of) { contradicted++; continue; }
    if (!last || sig(last) !== sig(cur)) {
      rec.cur = curQ;
      rec.samples = rec.samples || [rec.open];
      rec.samples.push(cur);
      if (rec.samples.length > MAX_SAMPLES) rec.samples.splice(1, rec.samples.length - MAX_SAMPLES); // keep open (idx 0), drop oldest middles
      moved++;
    } else {
      rec.cur = curQ;   // ts refresh only; not a movement (books may still move)
    }
  }
}

const payload = { generated: now, season, week, seasonType, keys: Object.keys(props).length, props };
log(`${seen} live two-way lines · ${created} new keys · ${moved} moved · ${contradicted} contradicted · ${started} past kickoff · ${otherGame} other game (not banked) · ${payload.keys} total banked`);
if (DRY) { log('--dry: not written'); process.exit(0); }
writeFileSync(OUT, JSON.stringify(payload));
log('wrote ' + OUT);
