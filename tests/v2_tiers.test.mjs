/* Watch and Passed are logged forward too (scripts/track-v2-plays.mjs --tier=watch|pass), one side per market. run: node --test tests/v2_tiers.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { loadFixtures } from './v2_page_harness.mjs';
import { logPlays, ledgerKey, ledgerFile } from '../scripts/track-v2-plays.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const gates = createRequire(import.meta.url)(path.join(ROOT, 'sharp-money', 'v2', 'gates.js'));
const fx = loadFixtures(), TS = fx.data.ts + 60;
const built = gates.build({ D: fx.data, P: fx.props, T: fx.tape, E: fx.edge, now: TS });
const opts = { edgeGenerated: 1, season: '2026', week: 6 };

test('each tier writes its own file name', () => {
  assert.equal(ledgerFile('play'), 'v2_plays.json');
  assert.equal(ledgerFile('watch'), 'v2_watch.json');
  assert.equal(ledgerFile('pass'), 'v2_passed.json');
});

test('a tier ledger holds only that tier, one side per market, frozen at first sight', () => {
  for (const tier of ['watch', 'pass']) {
    const L = { v: 1, plays: {} }, cand = gates.stance(built.cand), added = logPlays(L, cand, TS, { ...opts, tier });
    const want = cand.filter(c => c.tier === tier && c.start > TS);
    assert.equal(added.length, want.length);
    assert.ok(want.length > 0, tier + ' has candidates in the fixture');
    for (const c of want) assert.equal(L.plays[ledgerKey(c)].status, 'open');
    assert.equal(logPlays(L, cand, TS + 600, { ...opts, tier }).length, 0, 'a second look adds nothing');
    const markets = new Set(Object.values(L.plays).map(r => r.kind === 'prop' ? 'p|' + r.prop.pid + '|' + r.prop.mkt + '|' + r.prop.line : 'g|' + r.game.gk + '|' + r.game.m));
    assert.equal(markets.size, Object.keys(L.plays).length, 'no market is logged on both sides');
  }
});

test('the default tier is the play tier, as before', () => {
  const L = { v: 1, plays: {} }, added = logPlays(L, built.cand, TS, opts);
  assert.equal(added.length, built.cand.filter(c => c.tier === 'play').length);
});

test('stance keeps one side per market and never drops a market', () => {
  const s = gates.stance(built.all), key = c => c.kind === 'prop' ? 'p|' + c.row.pid + '|' + c.row.mkt + '|' + c.row.line : 'g|' + c.gk + '|' + c.m;
  const sides = {}; s.forEach(c => { (sides[key(c)] ||= new Set()).add(c.side); });
  assert.ok(Object.values(sides).every(x => x.size === 1));
  assert.equal(new Set(built.all.map(key)).size, Object.keys(sides).length);
});
