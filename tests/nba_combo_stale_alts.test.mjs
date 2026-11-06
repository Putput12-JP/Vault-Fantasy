/* Combo Check uses sportsbook alt prices only while they are fresh (SS_ALT_FRESH_MIN). Past that, or with no as-of time,
   every alt is left out, so a stopped publish job cannot keep pricing combos with old numbers.
   The helpers are read straight from the template between the ss-alt-fresh markers, so this tests the shipped code.
   run: node --test tests/nba_combo_stale_alts.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SRC = fs.readFileSync(path.join(ROOT, 'nba', 'ui', 'projections.template.html'), 'utf8');
const block = SRC.slice(SRC.indexOf('// ss-alt-fresh:start'), SRC.indexOf('// ss-alt-fresh:end'));

function load(asof, now) {
  const ctx = { window: { __ssAsof: asof }, Date: { now: () => now } };
  vm.createContext(ctx);
  vm.runInContext(block + '\n;globalThis.H = {SS_ALT_FRESH_MIN, ssAltsAgeMin, ssAltsFresh, ccAlts};', ctx);
  const H = ctx.H;
  return { ...H, ccAlts: e => [...H.ccAlts(e)] };   // copy into this realm's Array so deepEqual compares values, not prototypes
}

const NOW = 1_800_000_000_000;   // ms, as the publish job writes asof
const ALTS = [['DraftKings', 26.5, '+150', null]];

test('the block is in the template and the window is 15 minutes', () => {
  assert.ok(block.length > 100);
  assert.equal(load(NOW, NOW).SS_ALT_FRESH_MIN, 15);
});

test('fresh prices are used', () => {
  const H = load(NOW - 5 * 60000, NOW);
  assert.equal(H.ssAltsFresh(), true);
  assert.deepEqual(H.ccAlts({ alts: ALTS }), ALTS);
});

test('exactly 15 minutes old is still fresh; just past it is not', () => {
  assert.equal(load(NOW - 15 * 60000, NOW).ssAltsFresh(), true);
  const H = load(NOW - 15 * 60000 - 1000, NOW);
  assert.equal(H.ssAltsFresh(), false);
  assert.deepEqual(H.ccAlts({ alts: ALTS }), []);
});

test('days-old prices (a stopped job) are left out', () => {
  const H = load(NOW - 3 * 86400000, NOW);
  assert.equal(Math.round(H.ssAltsAgeMin()), 3 * 1440);
  assert.deepEqual(H.ccAlts({ alts: ALTS }), []);
});

test('no as-of time means not fresh', () => {
  for (const asof of [undefined, 0, null]) {
    const H = load(asof, NOW);
    assert.equal(H.ssAltsAgeMin(), null);
    assert.equal(H.ssAltsFresh(), false);
    assert.deepEqual(H.ccAlts({ alts: ALTS }), []);
  }
});

test('a prop with no alts gives an empty list either way', () => {
  assert.deepEqual(load(NOW, NOW).ccAlts({}), []);
});
