/* Second prices for spreads and totals from free exchange quotes (sharp-money/v2/gates.js lineRefs, gameCands b and c).
   run: node --test tests/v2_free_refs.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const gates = createRequire(import.meta.url)(path.join(ROOT, 'sharp-money', 'v2', 'gates.js'));
const TS = 1800000000;
const game = (over = {}) => ({
  key: 'nba:1', sport: 'nba', start: TS + 6 * 3600, away: { abbr: 'MIA', short: 'Heat' }, home: { abbr: 'PHI', short: '76ers' },
  consensus: { sp: { line: -3.5 }, tot: { line: 230.5 } }, pin: { sp: { line: -3.5 }, tot: { line: 230.5 } },
  soft: { DraftKings: { sp: { line: -3.5, home: -130, away: 110 }, tot: { line: 230.5, over: -130, under: 110 } } },
  behind: [{ book: 'DraftKings', m: 'tot', side: 'over', price: -130, line: 230.5, fair: 0.6, ev: 0.06 }],
  xref: {
    kal: { t: TS - 60, sp: [[-3.5, 0.59, 0.61, 5000]], tot: [[230.5, 0.59, 0.61, 5000], [231.5, 0.50, 0.52, 5000]] },
    pm: { t: TS - 60, sp: [[-3.5, 0.59, 0.61, 20000]], tot: [[230.5, 0.60, 0.62, 20000]] },
    nov: { t: TS - 60, sp: [[-3.5, 0.40, 0.48, 9000]], tot: [[230.5, 0.58, 0.60, 500]] },
  }, ...over });
const X = g => ({ D: { ts: TS, games: [g] }, E: null, now: TS });
const judged = g => gates.gameCands(X(g)).map(c => { c.hoursOut = (c.start - TS) / 3600; c.contradicted = false; return gates.judge(c) });

test('a source counts only at the same line, inside 3 cents, with liquidity, read within 10 minutes', () => {
  const g = game();
  const t = gates.lineRefs(X(g), g, 'tot', 'over', 230.5);
  assert.deepEqual(t.map(r => r.n), ['Kalshi', 'Polymarket'], 'Novig has $500 behind it: under the $1,000 floor');
  assert.equal(gates.lineRefs(X(g), g, 'tot', 'over', 229.5).length, 0, 'no quote at the number: nothing');
  const s = gates.lineRefs(X(g), g, 'sp', 'away', -3.5);
  assert.deepEqual(s.map(r => r.n), ['Kalshi', 'Polymarket'], 'Novig 8 cents wide: out');
  assert.ok(Math.abs(s[0].p - 0.4) < 1e-9, 'the away side is 1 minus the home mid');
  const old = game({ xref: { kal: { ...game().xref.kal, t: TS - 11 * 60 } } });
  assert.equal(gates.lineRefs(X(old), old, 'tot', 'over', 230.5).length, 0, 'read 11 minutes before the poll: out');
});

test('a spread or total behind Pinnacle gets a liquidity-weighted exchange fair as its second reference', () => {
  const c = judged(game()).find(c => c.m === 'tot' && c.side === 'over');
  assert.deepEqual(c.refs.map(r => r.n), ['Pinnacle', 'Exchange']);
  assert.ok(Math.abs(c.refs[1].p - (0.6 * 5000 + 0.61 * 20000) / 25000) < 1e-9);
  assert.equal(c.tier, 'play', 'price 56.5%, edge 6% over Pinnacle and 7.8% over the exchange fair, inside 48 hours');
  const none = judged(game({ xref: null })).find(c => c.m === 'tot');
  assert.equal(none.tier, 'watch', 'without a free quote it stays a one-reference Watch, as before');
});

test('any two sources more than 4 points apart is a Pass', () => {
  const g = game({ xref: { ...game().xref, pm: { t: TS - 60, tot: [[230.5, 0.66, 0.68, 20000]], sp: [] } } });
  const c = judged(g).find(c => c.m === 'tot' && c.side === 'over');
  assert.equal(c.tier, 'pass');
  assert.match(c.reasons[0], /disagree by 7\.0 points/);
});

test('no Pinnacle: a row exists only with two or more qualifying exchange quotes, and each must show the edge', () => {
  const g = game({ pin: null, behind: [] });
  const cs = judged(g), sp = cs.find(c => c.m === 'sp' && c.side === 'home'), tot = cs.find(c => c.m === 'tot' && c.side === 'over');
  assert.ok(sp && sp.bookRow.noPin);
  assert.deepEqual(sp.refs.map(r => r.n), ['Kalshi', 'Polymarket']);
  assert.equal(sp.tier, 'play');
  assert.equal(tot.tier, 'play');
  const one = game({ pin: null, behind: [], xref: { kal: game().xref.kal } });
  assert.equal(judged(one).filter(c => c.m !== 'ml').length, 0, 'one exchange alone makes no row');
  assert.equal(judged(game({ behind: [] })).filter(c => c.m !== 'ml').length, 0, 'Pinnacle quoting the market: block b decides, no extra row');
});

test('moneylines are unchanged', () => {
  const g = game({ behind: [{ book: 'DraftKings', m: 'ml', side: 'home', price: -130, fair: 0.6, ev: 0.06 }], nov: { ml: { mid: 0.6 } } });
  const c = judged(g).find(c => c.m === 'ml');
  assert.deepEqual(c.refs.map(r => r.n), ['Pinnacle', 'Exchange']);
  assert.equal(c.srcGap, undefined);
});
