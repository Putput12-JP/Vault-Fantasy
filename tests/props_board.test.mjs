/* The prop board (scripts/build-props-board.mjs) is anchored on the exchange; Pinnacle is the check. run: node --test tests/props_board.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPropsBoard, nkey } from '../scripts/build-props-board.mjs';

const now = new Date().toISOString(), nowS = Date.now() / 1000;
const feed = (extra = {}) => ({
  generated: now, vegas_meta: { props_pp_generated: now },
  vegas_player_props: { 7: { name: 'Test Player', team: 'WAS', pos: 'WR', lines: { rec: { line: 4.5, quotes: [
    { book: 'Pinnacle', line: 4.5, over: -110, under: -110 },
    { book: 'DraftKings', line: 4.5, over: 110, under: -140 },        // Over at +110 costs 47.6%
    ...(extra.quotes || [])] } } } },
});
const nk = nkey('Test Player');
const novig = (mid, over = {}) => ({ generated: now, markets: { rec: { [nk]: [{ k: 4.5, mid, spr: 0.02, depth: 500, oa: mid + 0.01, ob: mid - 0.01, ua: 1 - mid + 0.01, ub: 1 - mid - 0.01, t: nowS, ...over }] } } });
const kalshi = (fair) => ({ generated: now, markets: { rec: { [nk]: [{ k: 4.5, fair, spr: 0.02, oi: 1000 }] } } });
const row = (b) => b.rows.find(r => r.pid === '7');

test('with an exchange, the fair price is the exchange and Pinnacle is carried as the check', () => {
  const r = row(buildPropsBoard({ feed: feed(), kalshi: kalshi(0.54), novig: novig(0.56) }));
  assert.equal(r.fairSrc, 'Novig + Kalshi');
  assert.deepEqual(r.fairFrom, ['Novig', 'Kalshi']);
  assert.ok(Math.abs(r.fair - 0.55) < 1e-9);
  assert.ok(Math.abs(r.pinFair - 0.5) < 0.01, 'Pinnacle is -110 / -110');
  assert.equal(r.call.src, 'DraftKings', 'the call is the book price, never an exchange venue');
  assert.ok(Math.abs(r.call.ev - (0.55 / (100 / 210) - 1)) < 1e-3);
});

test('an exchange venue is never the call when the exchange is the anchor', () => {
  const r = row(buildPropsBoard({ feed: feed(), kalshi: kalshi(0.54), novig: novig(0.56) }));
  for (const side of ['over', 'under']) for (const v of r[side].venues) if (v.kind === 'exchange') assert.equal(v.ev, null);
  assert.notEqual(r.call.kind, 'exchange');
});

test('a call Pinnacle prices the other way, or far from the exchange, says so', () => {
  const r = row(buildPropsBoard({ feed: feed(), kalshi: kalshi(0.62), novig: novig(0.62) }));
  assert.equal(r.fairSrc, 'Novig + Kalshi');
  assert.ok(r.call.pinEdge != null);
  assert.ok(r.call.check.some(x => /Pinnacle is [\d.]+ points from the exchange/.test(x)));
  const r2 = row(buildPropsBoard({ feed: feed({ quotes: [] }), kalshi: kalshi(0.30), novig: novig(0.30) }));
  const under = r2.call && r2.call.side === 'under';
  if (under) assert.ok(r2.call.check.some(x => /other way|points from the exchange/.test(x)));
});

test('without a usable exchange the old rule stands: Pinnacle is the fair price', () => {
  const r = row(buildPropsBoard({ feed: feed(), kalshi: { generated: now, markets: {} }, novig: { generated: now, markets: {} } }));
  assert.equal(r.fairSrc, 'Pinnacle');
  assert.equal(r.fairFrom, null);
  const thin = row(buildPropsBoard({ feed: feed(), kalshi: kalshi(0.54), novig: novig(0.56, { depth: 10, spr: 0.2 }) }));
  assert.equal(thin.fairSrc, 'Kalshi', 'a thin Novig quote is not an anchor; the liquid Kalshi strike is');
});

test('a stale exchange is not an anchor', () => {
  const old = new Date(Date.now() - 3 * 3600 * 1000).toISOString();
  const r = row(buildPropsBoard({ feed: feed(), kalshi: { ...kalshi(0.54), generated: old }, novig: { ...novig(0.56), generated: old } }));
  assert.equal(r.fairSrc, 'Pinnacle');
});
