#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · PROP PRICE BACKFILL  →  data/prop_line_history.json (in place)

   One-shot repair for snapshots banked before the quote guard existed
   (prop-quote-guard.mjs). It REPLAYS the fixed snapshot over history: every
   hourly snapshot read the committed data/lineup-feed.json, so git holds the
   exact cell each sample was taken from. Per 2026 record:

     1. each banked sample (samples[], plus cur) is matched to the latest feed
        commit at or before its ts, and the raw cell must reproduce what was
        banked (line + over + under) or the sample is left exactly as is;
     2. the cell is repaired and re-banked the way the fixed snapshot would:
        line / over / under / bestOver / bestUnder from prices quoted at the
        repaired line. A cell left with no two-way price at its line is a
        snapshot the fixed code never takes, so that sample is dropped;
     3. the cross-snapshot guard runs over the record's re-banked samples
        (and cur) together; the ones the majority contradicts are dropped;
     4. consecutive identical samples collapse (the snapshot only appends on a
        change), open = first kept sample, cur = re-banked cur unless it was
        dropped, else the last kept sample. q on open/cur is re-derived only
        where it already existed. A record with nothing left is removed: the
        fixed snapshot would never have created it.

   Changed records carry gfix:1 and are skipped on a re-run. Dropped samples
   are kept for audit under gdrop:[{…sample, why}].

   Usage:  node scripts/backfill-prop-prices.mjs [--season=2026] [--dry]
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { repairCell, pricesAtLine, rejectedSamples } from './prop-quote-guard.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');
const ARG = Object.fromEntries(process.argv.slice(2).map(a => { const [k, v] = a.replace(/^--/, '').split('='); return [k, v ?? true]; }));
const SEASON = String(ARG.season || '2026');
const OUT = resolve(ROOT, 'data', 'prop_line_history.json');
const log = (...a) => console.log('[backfill]', ...a);
const num = v => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const git = (...a) => execFileSync('git', a, { cwd: ROOT, maxBuffer: 64 << 20 }).toString();
const sig = s => [s.line, s.over, s.under, s.bestOver, s.bestUnder, s.proj].join('|');   // = snapshot's sig
const bookQuotes = cell => (cell.quotes || [])
  .filter(q => q && q.book && (num(q.over) != null || num(q.under) != null))
  .map(q => [q.book, num(q.line), num(q.over), num(q.under)]);

const hist = JSON.parse(readFileSync(OUT, 'utf8'));
const commits = git('log', '--format=%H %ct', '--', 'data/lineup-feed.json').trim().split('\n')
  .map(l => { const [h, t] = l.split(' '); return { h, t: +t * 1000 }; }).sort((a, b) => a.t - b.t);
const commitAt = ts => {                       // latest feed commit at or before ts
  const t = Date.parse(ts); let lo = 0, hi = commits.length - 1, ans = null;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (commits[m].t <= t) { ans = commits[m]; lo = m + 1; } else hi = m - 1; }
  return ans;
};

// ── pass 1: re-bank every sample from its feed state (each feed parsed once) ──
const byCommit = new Map();
const recs = [];
for (const key in hist.props) {
  const r = hist.props[key];
  if (String(r.season) !== SEASON || r.gfix) continue;
  recs.push(key);
  for (const s of [...(r.samples || []), r.cur]) {
    if (!s || !s.ts) continue;
    const c = commitAt(s.ts); if (!c) continue;
    if (!byCommit.has(c.h)) byCommit.set(c.h, []);
    byCommit.get(c.h).push({ r, s });
  }
}
const redo = new Map();          // sample object → re-banked sample | {drop:'why'}
let matched = 0, unmatched = 0;
for (const [h, tasks] of byCommit) {
  let feed;
  try { feed = JSON.parse(git('show', `${h}:data/lineup-feed.json`)); } catch { unmatched += tasks.length; continue; }
  const vp = feed.vegas_player_props || {};
  for (const { r, s } of tasks) {
    const raw = vp[r.pid] && vp[r.pid].lines && vp[r.pid].lines[r.market];
    if (!raw || num(raw.line) !== s.line || num(raw.over) !== s.over || num(raw.under) !== s.under) { unmatched++; continue; }
    matched++;
    const cell = JSON.parse(JSON.stringify(raw));
    repairCell(cell, r.market);
    if (cell.over == null || cell.under == null) { redo.set(s, { drop: 'no two-way price at its line' }); continue; }
    const at = pricesAtLine(cell.quotes, cell.line);
    const next = { line: num(cell.line), over: num(cell.over), under: num(cell.under), bestOver: num(at.over), bestUnder: num(at.under), proj: s.proj, ts: s.ts };
    if (s.q) next.q = bookQuotes(cell);
    redo.set(s, next);
  }
}

// ── pass 2: rebuild each record's sample chain ──
let changedRecs = 0, removedRecs = 0, dropNoPrice = 0, dropConflict = 0, relined = 0, repriced = 0;
const touched = { weeks: {} };
for (const key of recs) {
  const r = hist.props[key];
  const orig = r.samples || [];
  const kept = [], gdrop = [];
  const reb = orig.map(s => (redo.has(s) ? redo.get(s) : s));             // unmatched → keep as banked
  const curN = r.cur && redo.has(r.cur) ? redo.get(r.cur) : r.cur;
  const nodes = [...reb, curN].map(n => (n && !n.drop ? n : null));
  const bad = rejectedSamples(nodes, r.market);
  reb.forEach((n, i) => {
    const s = orig[i];
    if (n.drop) { gdrop.push({ ...s, why: n.drop }); dropNoPrice++; return; }
    if (bad.has(i)) { gdrop.push({ ...s, why: 'contradicted by other snapshots' }); dropConflict++; return; }
    const lean = { line: n.line, over: n.over, under: n.under, bestOver: n.bestOver, bestUnder: n.bestUnder, proj: n.proj, ts: n.ts };
    const last = kept[kept.length - 1];
    if (last && sig(last) === sig(lean)) return;              // snapshot only appends on a change
    if (n !== s) { if (n.line !== s.line) relined++; else if (n.over !== s.over || n.under !== s.under) repriced++; }
    kept.push(lean);
  });
  // cur: re-banked unless dropped / contradicted, else the last kept sample
  const lastKept = kept[kept.length - 1];
  const cur = (!curN || curN.drop || bad.has(reb.length)) ? (lastKept ? { ...lastKept } : null) : { ...curN };
  const same = kept.length === orig.length && kept.every((k, i) => sig(k) === sig(orig[i])) && JSON.stringify(cur) === JSON.stringify(r.cur);
  if (same) continue;
  changedRecs++;
  touched.weeks[r.week] = (touched.weeks[r.week] || 0) + 1;
  if (!kept.length) { delete hist.props[key]; removedRecs++; continue; }
  const open0 = r.open || {};
  const open = { ...kept[0] };
  if (open0.q) { const n = redo.get(orig[0]); if (n && !n.drop && n.q && kept[0].ts === orig[0].ts) open.q = n.q; }
  r.open = open;
  r.samples = kept;
  r.cur = cur || { ...kept[kept.length - 1] };
  r.gfix = 1;
  if (gdrop.length) r.gdrop = gdrop;
}
hist.keys = Object.keys(hist.props).length;
log(`${byCommit.size} feed commits · ${matched} samples reproduced from git, ${unmatched} not (left as banked)`);
log(`${changedRecs} records changed (by week ${JSON.stringify(touched.weeks)}) · ${removedRecs} removed · samples: ${relined} re-lined, ${repriced} repriced, ${dropNoPrice} dropped (no price at line), ${dropConflict} dropped (contradicted)`);
if (ARG.dry) { log('--dry: not written'); process.exit(0); }
writeFileSync(OUT, JSON.stringify(hist));
log('wrote ' + OUT);
