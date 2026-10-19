/* The V2 play ledger (scripts/track-v2-plays.mjs): log once and freeze, settle from the stored sources, CLV against the exchange close.
   run: node --test tests/v2_gates.test.mjs tests/v2_ledger.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { loadFixtures, jitter } from './v2_page_harness.mjs';
import { logPlays, settlePlays, propClose, gameClose, exchIndex, makeFinals, ledgerKey, summary, payout, loadLedger } from '../scripts/track-v2-plays.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const gates = createRequire(import.meta.url)(path.join(ROOT, 'sharp-money', 'v2', 'gates.js'));
const fx = loadFixtures(), TS = fx.data.ts + 60;
const build = (f = fx, now = TS) => gates.build({ D: f.data, P: f.props, T: f.tape, E: f.edge, now }).cand;
const fresh = () => ({ v: 1, plays: {} });
const opts = { edgeGenerated: 1, season: '2026', week: 6 };

test('logs each play once, with the price, both references, edges and time', () => {
  const L = fresh(), added = logPlays(L, build(), TS, opts);
  const plays = build().filter(c => c.tier === 'play');
  assert.equal(added.length, plays.length);
  assert.ok(plays.length >= 4);
  for (const c of plays) {
    const r = L.plays[ledgerKey(c)];
    assert.equal(r.firstSeen, TS);
    assert.equal(r.status, 'open');
    assert.equal(r.first.price.book, c.price.book);
    assert.equal(r.first.price.p, +c.price.p.toFixed(4));
    assert.equal(r.first.refs.length, c.refs.length);
    assert.ok(r.first.refs.length >= 2 && r.first.refs.every(x => x.p > 0 && x.edge >= gates.GATES.MIN_EDGE - 1e-4), 'a play beat every reference');
    assert.ok(r.first.worst >= gates.GATES.MIN_EDGE - 1e-4 && r.first.worst <= gates.GATES.BIG_EDGE);
    assert.equal(r.kind === 'prop' ? r.prop.pid : r.game.gk, r.kind === 'prop' ? c.row.pid : c.gk);
  }
  assert.equal(logPlays(L, build(), TS + 600, opts).length, 0, 'a second look at the same plays adds nothing');
});

test('a logged play is frozen: a later price, a better book, or the play dropping out of the gates changes nothing', () => {
  const L = fresh(); logPlays(L, build(), TS, opts);
  const snap = JSON.stringify(L.plays);
  for (const seed of [11, 22, 33]) logPlays(L, build(jitter(fx, seed, 0.1), TS + 300), TS + 300, opts);
  const after = Object.fromEntries(Object.entries(L.plays).filter(([k]) => JSON.parse(snap)[k]));
  for (const [k, v] of Object.entries(JSON.parse(snap))) assert.deepEqual(after[k], v, k);
  assert.ok(Object.keys(L.plays).length > Object.keys(JSON.parse(snap)).length, 'the jittered data produced new plays that were appended');
  logPlays(L, [], TS + 900, opts);
  for (const [k, v] of Object.entries(JSON.parse(snap))) assert.deepEqual(L.plays[k], v, 'nothing is removed when a play stops qualifying');
});

test('a play is one row per pick, not one per book', () => {
  const c = build().find(x => x.tier === 'play' && x.kind === 'book');
  const other = { ...c, price: { ...c.price, book: 'DraftKings', am: c.price.am + 5 }, id: c.id + 'x' };
  assert.equal(ledgerKey(c), ledgerKey(other));
});

test('nothing is logged that is not a play, or that has started', () => {
  const L = fresh(), cands = build();
  logPlays(L, cands.filter(c => c.tier !== 'play'), TS, opts);
  assert.equal(Object.keys(L.plays).length, 0);
  logPlays(L, cands, Math.max(...cands.map(c => c.start)) + 1, opts);
  assert.equal(Object.keys(L.plays).length, 0);
});

const propPlay = (over = {}) => ({ id: 'p1', kind: 'prop', sport: 'nfl', start: 1_800_000_000, firstSeen: 1_799_990_000, status: 'open',
  first: { price: { am: -110, p: 0.5238, book: 'FanDuel' } }, prop: { season: '2026', week: 6, pid: '9', name: 'Test Player', mkt: 'rec_yd', line: 50.5, side: 'over', ...over } });
const stats = (val, wk = 6) => ({ 'Test Player': { weeks: [{ wk, recyds: val }] } });
const tapeFor = (kal, nov, { line = 50.5, age = 600, start = 1_800_000_000 } = {}) => ({ props: { ['2026|9|rec_yd|' + new Date(start * 1000).toISOString().slice(0, 10)]: { commence: new Date(start * 1000).toISOString(),
  books: { Kalshi: { ladder: [[line, kal, 100, 0.01]], t: start - age }, Novig: { ladder: [[line, nov, 0.02, 100]], t: start - age } }, frozen: true } } });

test('props settle from the box score: win pays 1/price - 1, loss is -1, a push is 0', () => {
  for (const [val, status, units] of [[60, 'won', +payout(0.5238).toFixed(3)], [40, 'lost', -1], [51, 'won', +payout(0.5238).toFixed(3)]]) {
    const P = propPlay(); const L = { plays: { p1: P } };
    settlePlays(L, { statsFor: () => stats(val), finals: () => null, T: {}, nowS: P.start + 4 * 3600 });
    assert.equal(P.status, status); assert.equal(P.units, units);
  }
  const P = propPlay({ line: 50 }); settlePlays({ plays: { p1: P } }, { statsFor: () => stats(50), finals: () => null, T: {}, nowS: P.start + 4 * 3600 });
  assert.equal(P.status, 'push'); assert.equal(P.units, 0);
  const U = propPlay({ side: 'under' }); settlePlays({ plays: { p1: U } }, { statsFor: () => stats(40), finals: () => null, T: {}, nowS: U.start + 4 * 3600 });
  assert.equal(U.status, 'won');
});

test('a prop waits 3 hours, and a player with no box score 36 hours after kickoff is void', () => {
  const P = propPlay(); settlePlays({ plays: { p1: P } }, { statsFor: () => stats(60), finals: () => null, T: {}, nowS: P.start + 2 * 3600 });
  assert.equal(P.status, 'open');
  settlePlays({ plays: { p1: P } }, { statsFor: () => ({}), finals: () => null, T: {}, nowS: P.start + 20 * 3600 });
  assert.equal(P.status, 'open');
  settlePlays({ plays: { p1: P } }, { statsFor: () => ({}), finals: () => null, T: {}, nowS: P.start + 37 * 3600 });
  assert.equal(P.status, 'void'); assert.equal(P.units, 0);
});

test('prop CLV is the exchange close (mean of the Kalshi and Novig ladders at the exact line) over the stored price', () => {
  const P = propPlay(), T = tapeFor(0.6, 0.5);
  const c = propClose(T, P);
  assert.equal(c.p, 0.55); assert.equal(c.src, 'Kalshi+Novig');
  settlePlays({ plays: { p1: P } }, { statsFor: () => stats(60), finals: () => null, T, nowS: P.start + 4 * 3600 });
  assert.equal(P.clv, +(0.55 / 0.5238 - 1).toFixed(4));
  assert.equal(P.close.p, 0.55);
  const U = propPlay({ side: 'under' }); assert.equal(propClose(T, U).p, 0.45);
});

test('prop CLV is empty, never invented, when the line moved, the read is stale, or it came after kickoff', () => {
  const P = propPlay();
  assert.equal(propClose(tapeFor(0.6, 0.5, { line: 51.5 }), P), null, 'a ladder with no rung at the line');
  assert.equal(propClose(tapeFor(0.6, 0.5, { age: 4 * 3600 }), P), null, 'older than 180 minutes');
  assert.equal(propClose(tapeFor(0.6, 0.5, { age: -60 }), P), null, 'read after kickoff');
  const L = { plays: { p1: P } }; settlePlays(L, { statsFor: () => stats(60), finals: () => null, T: tapeFor(0.6, 0.5, { line: 51.5 }), nowS: P.start + 4 * 3600 });
  assert.equal(P.status, 'won'); assert.equal(P.clv, undefined); assert.equal(P.close, false);
});

test('prop CLV matches scripts/regrade_prop_clv.py on the same tape', () => {
  const T = tapeFor(0.63, 0.48), entry = Object.values(T.props)[0], start = 1_800_000_000;
  const py = spawnSync('python3', ['-c', `import sys,json;sys.path.insert(0,'${path.join(ROOT, 'scripts')}');import regrade_prop_clv as R;print(R.refs(json.loads(sys.argv[1]),50.5,${start},180*60)['Exchange'])`, JSON.stringify(entry)], { encoding: 'utf8' });
  assert.equal(py.status, 0, py.stderr);
  assert.ok(Math.abs(+py.stdout - propClose(T, propPlay()).p) < 1e-9);
});

const gamePlay = (g, over = {}) => ({ id: 'g1', kind: 'book', sport: 'cfb', start: 1_800_000_000, firstSeen: 1_799_990_000, status: 'open',
  first: { price: { am: 120, p: 0.4545, book: 'FanDuel' } }, game: { gk: 'cfb:1', away: 'AAA', home: 'HHH', m: 'ml', side: 'home', hline: null, line: null, ...g }, ...over });
const fin = (home, away) => () => ({ home, away });
const settleG = (P, f, now = P.start + 4 * 3600) => settlePlays({ plays: { g1: P } }, { statsFor: () => null, finals: f, T: {}, nowS: now });

test('games settle from the final score the way the pick ledger does (home 24, away 20)', () => {
  const cases = [
    [{ m: 'ml', side: 'home' }, 24, 20, 'won'], [{ m: 'ml', side: 'away' }, 24, 20, 'lost'], [{ m: 'ml', side: 'home' }, 20, 20, 'push'],
    [{ m: 'sp', side: 'home', hline: -3.5 }, 24, 20, 'won'], [{ m: 'sp', side: 'away', hline: -3.5 }, 24, 20, 'lost'], [{ m: 'sp', side: 'home', hline: -4 }, 24, 20, 'push'],
    [{ m: 'sp', side: 'home', hline: -4.5 }, 24, 20, 'lost'], [{ m: 'sp', side: 'away', hline: -4.5 }, 24, 20, 'won'],
    [{ m: 'tot', side: 'over', line: 43.5 }, 24, 20, 'won'], [{ m: 'tot', side: 'under', line: 43.5 }, 24, 20, 'lost'], [{ m: 'tot', side: 'under', line: 44 }, 24, 20, 'push'], [{ m: 'tot', side: 'under', line: 45.5 }, 24, 20, 'won']];
  for (const [g, h, a, exp] of cases) {
    const P = gamePlay(g); settleG(P, fin(h, a));
    assert.equal(P.status, exp, JSON.stringify(g)); assert.deepEqual(P.final, { away: a, home: h });
    assert.equal(P.units, exp === 'won' ? +payout(0.4545).toFixed(3) : exp === 'lost' ? -1 : 0);
  }
});

test('a game with no final stays open, then goes void at 72 hours', () => {
  const P = gamePlay({}); settleG(P, () => null, P.start + 10 * 3600); assert.equal(P.status, 'open');
  settleG(P, () => null, P.start + 73 * 3600); assert.equal(P.status, 'void');
});

test('the final comes from the board while it is there, else the stored results by game key, else by teams and start', () => {
  const D = { games: [{ key: 'cfb:1', final: { home: 1, away: 2 } }] };
  const f = makeFinals(D, { 'cfb:9': { sport: 'cfb', ah: 'XXX', hh: 'YYY', home: 7, away: 3, start: 1_800_000_000 } });
  assert.deepEqual(f(gamePlay({})), { home: 1, away: 2 });
  assert.deepEqual(f(gamePlay({ gk: 'cfb:9' })), { home: 7, away: 3 });
  assert.deepEqual(f(gamePlay({ gk: 'cfb:x', away: 'XXX', home: 'YYY' })), { home: 7, away: 3 });
  assert.equal(f(gamePlay({ gk: 'cfb:x', away: 'XXX', home: 'ZZZ' })), null);
});

const K = 1_800_000_000;
const rows = [
  { t: K - 600, book: 'Novig', gk: 'cfb:1', away: 'AAA', home: 'HHH', start: K, px: [0.40, 0.42], nsp: [-3.5, 0.48, 0.50], ntot: [44.5, 0.47, 0.49] },
  { t: K - 500, book: 'Kalshi', gk: 'cfb:1', away: 'AAA', home: 'HHH', start: K, px: [0.44, 0.46] },
  { t: K + 60, book: 'Novig', gk: 'cfb:1', away: 'AAA', home: 'HHH', start: K, px: [0.90, 0.92] },                    // after kickoff: not a close
];
test('game CLV: moneyline close is the mean of the Novig and Kalshi mids, the spread and total only at the exact line', () => {
  const idx = exchIndex(rows);
  const ml = gameClose(idx, gamePlay({}));
  assert.equal(ml.p, 0.43); assert.equal(ml.src, 'Kalshi+Novig');                                                         // (0.41 + 0.45) / 2
  assert.equal(gameClose(idx, gamePlay({ side: 'away' })).p, 0.57);
  assert.equal(gameClose(idx, gamePlay({ m: 'sp', side: 'home', hline: -3.5 })).p, 0.49);
  assert.equal(gameClose(idx, gamePlay({ m: 'sp', side: 'away', hline: -3.5 })).p, 0.51);
  assert.equal(gameClose(idx, gamePlay({ m: 'sp', side: 'home', hline: -4 })), null, 'a moved spread is never converted');
  assert.equal(gameClose(idx, gamePlay({ m: 'tot', side: 'over', line: 44.5 })).p, 0.48);
  assert.equal(gameClose(idx, gamePlay({ m: 'tot', side: 'under', line: 44.5 })).p, 0.52);
  assert.equal(gameClose(idx, gamePlay({ m: 'tot', side: 'over', line: 45.5 })), null);
});

test('game CLV ignores a quote wider than 6 points, and NFL rows match on teams and start', () => {
  const wide = exchIndex([{ ...rows[0], px: [0.30, 0.45] }]); assert.equal(gameClose(wide, gamePlay({})), null);
  const nfl = exchIndex([{ t: K - 300, src: 'nov', book: 'Novig', away: 'JAC', home: 'LA', start: K + 60, px: [0.60, 0.62] }]);
  assert.equal(gameClose(nfl, gamePlay({ gk: 'nfl:5', away: 'JAX', home: 'LAR' }, { sport: 'nfl' })).p, 0.61);
});

test('the game tape stores a quote only when it changes: an old last row stands as the close while the recorder was running, and is not believed when it was dark', () => {
  const old = { ...rows[0], t: K - 20 * 3600 }, other = { t: K - 600, book: 'FanDuel', gk: 'cfb:2', away: 'X', home: 'Y', start: K + 5000, ml: [100, -120] };
  assert.equal(gameClose(exchIndex([old, other]), gamePlay({})).p, 0.41, 'unchanged since 20h out, recorder alive 10 minutes before kickoff');
  assert.equal(gameClose(exchIndex([old]), gamePlay({})), null, 'no row of any book in the 2h before kickoff');
  assert.equal(gameClose(exchIndex([old, { ...other, bf: 1 }]), gamePlay({})), null, 'backfilled rows are not proof the recorder ran');
});

test('game CLV lands on the play when it settles, and the result is the stored price over the close', () => {
  const P = gamePlay({}); const L = { plays: { g1: P } };
  settlePlays(L, { statsFor: () => null, finals: fin(24, 20), T: {}, exch: () => exchIndex(rows), nowS: K + 4 * 3600 });
  assert.equal(P.status, 'won'); assert.equal(P.units, +payout(0.4545).toFixed(3)); assert.equal(P.clv, +(0.43 / 0.4545 - 1).toFixed(4));
  const s = summary(L); assert.equal(s.w, 1); assert.equal(s.clvN, 1);
});

test('a ledger that exists but does not parse stops the run instead of starting an empty one', async () => {
  const fs = await import('node:fs'), os = await import('node:os');
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'v2l-')), 'v2_plays.json');
  assert.deepEqual(loadLedger(f), { v: 1, plays: {} });
  fs.writeFileSync(f, '{"plays":'); assert.throws(() => loadLedger(f));
});
