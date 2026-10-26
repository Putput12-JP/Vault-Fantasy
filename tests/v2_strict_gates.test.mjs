/* The strict gates: a Play needs a price of 55% or better (not plus money) and a game under 48 hours away. They were found on the first 204 settled live plays
   (108-96) and cut that record to 33-11; see docs/retro/sharp-v2-strict-gates.md. run: node --test tests/v2_strict_gates.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { loadFixtures, runPage, FIX } from './v2_page_harness.mjs';
import { summary } from '../scripts/track-v2-plays.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const gates = createRequire(import.meta.url)(path.join(ROOT, 'sharp-money', 'v2', 'gates.js'));
const { GATES } = gates;
const LEDGER = JSON.parse(fs.readFileSync(path.join(FIX, 'v2_plays_2026-10-26.json'), 'utf8'));   // sharp-data/v2_plays.json as of 2026-10-26, 222 plays

/* A candidate that clears every older gate: both references say +4%, 1 point apart. Only price and hours out vary. */
const cand = (pr, hoursOut, kind = 'book') => ({ kind, price: { p: pr, am: -110, book: 'DraftKings' }, hoursOut, cautions: [], contradicted: false,
  refs: [{ n: 'Pinnacle', p: pr * 1.04 }, { n: 'Exchange', p: pr * 1.05 }] });

test('the gates are 55% and 48 hours', () => { assert.equal(GATES.MIN_PRICE, 0.55); assert.equal(GATES.EARLY_H, 48); });

test('a price under 55% is a Pass, 55% is a Play', () => {
  assert.equal(gates.judge(cand(0.549, 10)).tier, 'pass');
  assert.match(gates.judge(cand(0.549, 10)).reasons[0], /under 55%/);
  assert.equal(gates.judge(cand(0.55, 10)).tier, 'play');
});

test('a call 48 hours or more out is a Pass, 47.9 is a Play, an unknown start is not judged on time', () => {
  assert.equal(gates.judge(cand(0.6, 48)).tier, 'pass');
  assert.match(gates.judge(cand(0.6, 48)).reasons[0], /48 hours or more/);
  assert.equal(gates.judge(cand(0.6, 47.9)).tier, 'play');
  assert.equal(gates.judge(cand(0.6, null)).tier, 'play');
});

test('a prop anchored on the exchange is held by the same gates', () => {
  const p = (pr, h) => ({ ...cand(pr, h, 'prop'), refs: [{ n: 'Pinnacle', p: pr * 1.04 }, { n: 'Exchange', p: pr * 1.05 }] });
  assert.equal(gates.judge(p(0.5, 10)).tier, 'pass');
  assert.equal(gates.judge(p(0.6, 60)).tier, 'pass');
  assert.equal(gates.judge(p(0.6, 10)).tier, 'play');
});

test('both reasons are given when both gates fail', () => { assert.equal(gates.judge(cand(0.4, 100)).reasons.length, 2); });

test('a candidate that already failed an older gate keeps its older reason', () => {
  const c = cand(0.4, 100); c.refs[0].p = c.refs[1].p = c.price.p * 1.2;                       // 20% edge: over BIG_EDGE
  assert.match(gates.judge(c).reasons[0], /stale or moved line/);
});

test('heldBack reads stored fields: live row, backfilled row and a row with no hours', () => {
  assert.deepEqual(gates.heldBack({ first: { price: { p: 0.43 } }, start: 1000 + 3600 * 5, firstSeen: 1000 }), ['price']);
  assert.deepEqual(gates.heldBack({ first: { price: { p: 0.6 } }, start: 1000 + 3600 * 60, firstSeen: 1000 }), ['early']);
  assert.deepEqual(gates.heldBack({ first: { price: { p: 0.43 } }, start: 1000 + 3600 * 60, firstSeen: 1000 }), ['price', 'early']);
  assert.deepEqual(gates.heldBack({ first: { price: { p: 0.6 } }, hoursEarly: 102.1 }), ['early']);
  assert.deepEqual(gates.heldBack({ first: { price: { p: 0.55 } }, start: 1000 + 3600 * 47, firstSeen: 1000 }), []);
  assert.deepEqual(gates.heldBack({ first: { price: {} } }), []);
});

const W = r => r.status === 'won', S = r => r.status === 'won' || r.status === 'lost';
const rec = rs => { const d = rs.filter(S); return { w: d.filter(W).length, l: d.filter(r => !W(r)).length, u: +d.reduce((a, r) => a + r.units, 0).toFixed(1) } };

test('re-scored on the stored ledger: 108-96 (+1.8u) becomes 33-11 (+11.2u) and the held-back plays went 75-85 (-9.5u)', () => {
  const rows = Object.values(LEDGER.plays), kept = rows.filter(r => !gates.heldBack(r).length), held = rows.filter(r => gates.heldBack(r).length);
  assert.equal(rows.length, 222);
  assert.deepEqual(rec(rows), { w: 108, l: 96, u: 1.8 });
  assert.deepEqual(rec(kept), { w: 33, l: 11, u: 11.2 });
  assert.deepEqual(rec(held), { w: 75, l: 85, u: -9.5 });
  assert.equal(kept.length + held.length, rows.length);
});

test('each gate on its own, on the same ledger', () => {
  const rows = Object.values(LEDGER.plays), by = g => rows.filter(r => gates.heldBack(r).includes(g));
  assert.deepEqual(rec(by('early')), { w: 18, l: 27, u: -9.7 });
  assert.deepEqual(rec(by('price')), { w: 67, l: 79, u: -9.3 });
});

test('the ledger summary counts held-back plays and changes nothing else', () => {
  const s = summary(LEDGER);
  assert.equal(s.held, 176);                               // 160 settled (75-85), 13 open, 3 void
  assert.equal(s.w, 108); assert.equal(s.l, 96); assert.equal(s.n, 222);
});

test('the stored first-sight record is never edited by the gates', () => {
  const before = JSON.stringify(LEDGER); Object.values(LEDGER.plays).forEach(r => gates.heldBack(r)); assert.equal(JSON.stringify(LEDGER), before);
});

test('the standalone page counts only plays that pass, and says how many it held back', async () => {
  const fx = loadFixtures(); fx.plays = LEDGER;
  const page = await runPage({ html: path.join(ROOT, 'sharp-money', 'v2', 'index.html'), fixtures: fx, now: fx.data.ts + 60, pages: ['record'] });
  const html = page.pages.record;
  assert.match(html, /33-11/);
  assert.match(html, /Held back by the strict gates/);
  assert.match(html, /75-85/);
  assert.doesNotMatch(html, /108-96/);
});
