/* One side per market, across runs (gates.js sideOut / sideLive). A player prop or game market logged as a Play on one side cannot later log
   the other side: live the later side is a Pass, and in the stored record the side logged first stands.
   run: node --test tests/v2_one_side.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { logPlays } from '../scripts/track-v2-plays.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const gates = createRequire(import.meta.url)(path.join(ROOT, 'sharp-money', 'v2', 'gates.js'));
const NOW = 1_800_000_000, TIP = NOW + 1800;

/* a stored NBA prop row that clears rule C at first sight */
const prop = (id, side, line, firstSeen, extra = {}) => ({ id, kind: 'prop', sport: 'nba', status: 'open', start: TIP, firstSeen,
  prop: { pid: 'nba:1', mkt: 'pts', line, side }, first: { title: 'Play Er ' + (side === 'over' ? 'Over ' : 'Under ') + line + ' Points', worst: 0.05, price: { p: 0.5, kal: true }, refs: [{ n: 'Exchange', p: 0.525, edge: 0.05 }, { n: 'Pinnacle', p: 0.527, edge: 0.054 }] }, ...extra });
const game = (id, side, firstSeen, start = TIP) => ({ id, kind: 'book', sport: 'nba', status: 'open', start, firstSeen, game: { gk: 'nba:g1', m: 'ml', side }, first: { title: side + ' to win', price: { p: 0.6 } } });

test('record: the side logged first stands, the later other side is held back', () => {
  const rows = [prop('u', 'under', 24.5, NOW - 5000), prop('o', 'over', 24.5, NOW - 1000)];
  assert.deepEqual([...gates.sideOut(rows)], ['o']);
  assert.deepEqual([...gates.sideOut(rows.slice().reverse())], ['o'], 'order in the file does not matter, first sight does');
  assert.ok(gates.capOut(rows).has('o'), 'capOut holds it back too, so every page that reads capOut drops it');
  assert.ok(!gates.capOut(rows).has('u'));
});

test('record: any line on the other side counts; the same side twice, another game, or a void row does not', () => {
  assert.deepEqual([...gates.sideOut([prop('u', 'under', 24.5, 1), prop('o', 'over', 22.5, 2)])], ['o'], 'Under 24.5 then Over 22.5 is still both sides');
  assert.equal(gates.sideOut([prop('a', 'over', 24.5, 1), prop('b', 'over', 22.5, 2)]).size, 0);
  assert.equal(gates.sideOut([prop('u', 'under', 24.5, 1), prop('o', 'over', 24.5, 2, { start: TIP + 2 * 86400 })]).size, 0, 'a different night');
  assert.equal(gates.sideOut([prop('u', 'under', 24.5, 1, { status: 'void' }), prop('o', 'over', 24.5, 2)]).size, 0, 'a void row holds nothing');
});

test('record: game markets, home then away', () => {
  assert.deepEqual([...gates.sideOut([game('h', 'home', 1), game('a', 'away', 2)])], ['a']);
  assert.equal(gates.sideOut([game('h', 'home', 1), game('a', 'away', 2, TIP + 3 * 86400)]).size, 0);
});

/* one live board: Kalshi 60% on over 24.5, Pinnacle agrees, DraftKings -125: a play on the over */
const board = () => ({
  t: NOW, src_ok: { kalshi: { ok: NOW - 60 }, pinnacle: { ok: NOW - 60 }, espn: { ok: NOW - 60 } },
  games: [{ id: 'g1', tip: TIP, away: 'DET', home: 'BOS' }], players: { 1: ['Play Er', 'BOS', null, 's'] }, outs: [], novig: { asof: NOW - 30, props: {} },
  props: [{ p: 1, s: 'pts', g: 'g1', kal: [[24.5, 0.59, 0.61, 0.60, 10, 10, NOW - 100]], books: [['DraftKings', 24.5, '-125', '-105', 24.5, '+100', NOW - 900], ['Pinnacle', 24.5, '-160', '+140', 24.5, '-110', NOW - 900]] }],
});
const live = L => gates.build({ N: board(), now: NOW, L, D: { games: [] }, P: null, T: null, E: null }).all.filter(c => c.sport === 'nba' && c.kind === 'prop');

test('live: with the Under already a play, the Over is a Pass and the ledger does not log it', () => {
  const free = live({ plays: {} }).find(c => c.side === 'over');
  assert.equal(free.tier, 'play', 'the fixture is a play on its own');
  const u = prop('u', 'under', 24.5, NOW - 3600); u.prop.pid = free.row.pid; u.prop.mkt = free.row.mkt;
  const L = { v: 1, plays: { u } }, c = live(L).find(x => x.side === 'over');
  assert.equal(c.tier, 'pass'); assert.ok(c.sideOut); assert.match(c.reasons[0], /other side .*already a play/);
  assert.equal(logPlays(L, [c], NOW, {}).length, 0);
});

test('live: an Under the gates now hold back does not block the Over', () => {
  const free = live({ plays: {} }).find(c => c.side === 'over');
  const u = prop('u', 'under', 24.5, NOW - 3600); u.prop.pid = free.row.pid; u.prop.mkt = free.row.mkt; u.first.price.kal = false;
  assert.ok(gates.heldBack(u).length);
  assert.equal(live({ plays: { u } }).find(x => x.side === 'over').tier, 'play');
});
