/* Sharp Money V2 Plays rules (sharp-money/v2/gates.js, the Plays rules block): nba-sig5, nba-aplus and cfb-novig.
   A rule makes a Play out of a price the gates pass over, tags it (c.rule, c.rules), never takes a slot in rule C's nightly NBA cap, keeps one
   side per market, and sorts CFB Novig first. The NBA rule groups come from board.rules (nba/scripts/prop_rules.py).
   run: node --test tests/v2_plays_rules.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { logPlays } from '../scripts/track-v2-plays.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const gates = createRequire(import.meta.url)(path.join(ROOT, 'sharp-money', 'v2', 'gates.js'));
const NOW = 1_800_000_000, TIP = NOW + 1800;
const DK = (line, o, u) => ['DraftKings', line, o, u, line, '+100', NOW - 900], PIN = (line, o, u) => ['Pinnacle', line, o, u, line, '-110', NOW - 900];
function board(rules, extra = []) {
  return {
    t: NOW, src_ok: { kalshi: { ok: NOW - 60 }, pinnacle: { ok: NOW - 60 }, espn: { ok: NOW - 60 } },
    games: [{ id: 'g1', tip: TIP, away: 'DET', home: 'BOS' }],
    players: { 1: ['Play Er', 'BOS', null, 's'], 2: ['Disagree Dan', 'BOS', null, 's'], 7: ['Combo Cal', 'BOS', null, 's'], 8: ['Assist Al', 'BOS', null, 's'] },
    outs: [], novig: { asof: NOW - 30, props: {} },
    props: [
      /* rule C play: beats Kalshi 60% at -125 with Pinnacle agreeing */
      { p: 1, s: 'pts', g: 'g1', kal: [[24.5, 0.59, 0.61, 0.60, 10, 10, NOW - 100]], books: [DK(24.5, '-125', '-105'), PIN(24.5, '-160', '+140')] },
      /* gates: Pass (Pinnacle prices the over the other way) */
      { p: 2, s: 'reb', g: 'g1', kal: [[8.5, 0.59, 0.61, 0.60, 10, 10, NOW - 100]], books: [DK(8.5, '-125', '-105'), PIN(8.5, '+120', '-140')] },
      /* gates: no edge at all (fair price) */
      { p: 7, s: 'pra', g: 'g1', kal: [[30.5, 0.49, 0.51, 0.5, 10, 10, NOW - 100]], books: [DK(30.5, '-110', '-110'), PIN(30.5, '-105', '-105')] },
      { p: 8, s: 'ast', g: 'g1', kal: [[6.5, 0.49, 0.51, 0.5, 10, 10, NOW - 100]], books: [DK(6.5, '-110', '-110'), PIN(6.5, '-105', '-105')] },
      ...extra,
    ],
    rules: rules === undefined ? null : { v: 1, t: NOW - 60, rows: rules },
  };
}
const build = (N, L = null, now = NOW) => gates.build({ N, L, now, D: { games: [] }, P: null, T: null, E: null });
const nba = (r, title) => r.all.find(c => c.title === title);

test('without board.rules nothing changes: the gates decide alone', () => {
  const r = build(board());
  assert.equal(nba(r, 'Disagree Dan Over 8.5 Rebounds').tier, 'pass');
  assert.equal(nba(r, 'Combo Cal Over 30.5 Pts + Reb + Ast').tier, 'none');
  assert.ok(r.all.every(c => !c.rule));
});

test('nba-sig5: five of five on the model side at the main line makes a tagged Play, whatever the gates said', () => {
  const r = build(board({ 'g1|2|reb': [8.5, 'O', 5, 0, 'B', 'O'] }));
  const c = nba(r, 'Disagree Dan Over 8.5 Rebounds');
  assert.equal(c.tier, 'play'); assert.equal(c.rule, 'nba-sig5'); assert.deepEqual(c.rules, ['nba-sig5']);
  assert.equal(c.gateTier, 'pass');
  assert.match(c.cautions[0], /^Untested rule \(5 of 5 signals\)/);
  assert.match(c.reasons[0], /^Rule play:/);
  assert.equal(nba(r, 'Disagree Dan Under 8.5 Rebounds').tier !== 'play', true, 'the other side is not a play');
  assert.ok(r.cand.includes(c));
});

test('nba-sig5 needs all five, the same side and the same line', () => {
  for (const row of [[8.5, 'O', 4, 0, 'B', 'O'], [8.5, 'U', 5, 0, 'B', 'U'], [9.5, 'O', 5, 0, 'B', 'O']]) {
    const c = nba(build(board({ 'g1|2|reb': row })), 'Disagree Dan Over 8.5 Rebounds');
    assert.equal(c.tier, 'pass', JSON.stringify(row));
  }
});

test('a stale rules block is not read (older than the reference age limit)', () => {
  const N = board({ 'g1|2|reb': [8.5, 'O', 5, 0, 'B', 'O'] }); N.rules.t = NOW - gates.GATES.MAX_AGE - 1;
  assert.equal(nba(build(N), 'Disagree Dan Over 8.5 Rebounds').tier, 'pass');
});

test('nba-aplus: A+ on PRA, RA or PA on the grade side; not on other stats', () => {
  const r = build(board({ 'g1|7|pra': [30.5, 'U', 2, 1, 'A+', 'O'], 'g1|8|ast': [6.5, 'O', 3, 0, 'A+', 'O'] }));
  const c = nba(r, 'Combo Cal Over 30.5 Pts + Reb + Ast');
  assert.equal(c.tier, 'play'); assert.equal(c.rule, 'nba-aplus'); assert.equal(c.gateTier, 'none');
  assert.notEqual(nba(r, 'Combo Cal Under 30.5 Pts + Reb + Ast').tier, 'play');
  assert.notEqual(nba(r, 'Assist Al Over 6.5 Assists').tier, 'play', 'A+ on assists alone is not in the rule');
});

test('nba-reb-a: rebounds graded A+, A or A- with grade and model on the same side', () => {
  const ok = c => nba(build(board({ 'g1|2|reb': c })), 'Disagree Dan Over 8.5 Rebounds');
  for (const g of ['A+', 'A', 'A-']) { const c = ok([8.5, 'O', 3, 1, g, 'O']); assert.equal(c.tier, 'play', g); assert.equal(c.rule, 'nba-reb-a'); }
  assert.equal(ok([8.5, 'O', 3, 1, 'B+', 'O']).tier, 'pass', 'B+ is not in the rule');
  assert.equal(ok([8.5, 'U', 3, 1, 'A', 'O']).tier, 'pass', 'the grade and the model must point the same way');
  const pra = nba(build(board({ 'g1|7|pra': [30.5, 'O', 2, 0, 'A', 'O'] })), 'Combo Cal Over 30.5 Pts + Reb + Ast');
  assert.equal(pra.tier, 'none', 'A on a combo stat is not a rule');
});

test('stance(): a rule Play wins its market even when the other side has the better reference edge (QA: Brunson PRA Over 35.5)', () => {
  const extra = [{ p: 9, s: 'pra', g: 'g1', kal: [[35.5, 0.44, 0.46, 0.45, 10, 10, NOW - 100]], books: [DK(35.5, '-110', '-110'), PIN(35.5, '+105', '-125')] }];
  const N = board({ 'g1|9|pra': [35.5, 'O', 3, 1, 'A+', 'O'] }, extra); N.players[9] = ['Jalen Brunson', 'NYK', null, 's'];
  const r = build(N), over = nba(r, 'Jalen Brunson Over 35.5 Pts + Reb + Ast'), under = nba(r, 'Jalen Brunson Under 35.5 Pts + Reb + Ast');
  assert.equal(over.rule, 'nba-aplus'); assert.equal(over.tier, 'play');
  assert.ok((under.best ?? -9) > (over.best ?? -9), 'the Under has the better reference edge');
  for (const list of [r.all, r.cand]) {
    const kept = gates.stance(list).filter(c => /Jalen Brunson .* 35\.5 Pts \+ Reb \+ Ast/.test(c.title));
    assert.ok(kept.includes(over), 'the rule Play is shown'); assert.ok(!kept.includes(under), 'the Under is dropped');
  }
  /* without the rule the reference edge still decides */
  const M = board(undefined, extra); M.players[9] = ['Jalen Brunson', 'NYK', null, 's'];
  const plain = gates.stance(build(M).all).filter(c => /Jalen Brunson/.test(c.title)).map(c => c.title);
  assert.deepEqual(plain, ['Jalen Brunson Under 35.5 Pts + Reb + Ast']);
});

test('cfb-novig: the chip and the Record card share one computed rebuild (cfbNovigRebuild)', () => {
  const row = (id, best, status, units, extra = {}) => ({ id, sport: 'cfb', kind: 'exch', status, units, firstSeen: 1, first: { best }, ...extra });
  const r = gates.cfbNovigRebuild([[row('a', 0.03, 'won', 1), row('b', 0.01, 'won', 1)], [row('a', 0.05, 'lost', -1, { firstSeen: 2 }), row('c', 0.02, 'lost', -1), row('d', 0.04, 'push', 0), row('e', 0.04, 'won', 1, { rules: ['cfb-novig'] })]]);
  assert.deepEqual([r.w, r.l, r.n, r.units], [1, 1, 2, 0], 'first sighting per id, edge 2%+ only, pushes and rule rows out');
  assert.ok(!/197-172|369/.test(JSON.stringify(gates.RULES || {})), 'no hard-coded record left');
});

/* five rebounds props, all fair-priced (no gate edge), for the nightly cap */
function rebBoard(grades, edges, tip = TIP) {
  const extra = grades.map((g, i) => ({ p: 11 + i, s: 'reb', g: 'g1', kal: [[5.5, 0.49, 0.51, 0.5, 10, 10, NOW - 100]], books: [DK(5.5, '-110', '-110'), PIN(5.5, '-105', '-105')] }));
  const rows = {}; grades.forEach((g, i) => { rows['g1|' + (11 + i) + '|reb'] = [5.5, 'O', 2, 0, g, 'O', edges[i]] });
  const N = board(rows, extra); N.games[0].tip = tip;
  grades.forEach((g, i) => { N.players[11 + i] = ['Reb ' + i, 'BOS', null, 's'] });
  return N;
}
const rebPlays = r => r.all.filter(c => c.row && c.row.mkt === 'reb' && c.side === 'over' && /^Reb /.test(c.title));

test('nba-reb-a cap: top 3 a night by grade, then model edge; the rest are Passes', () => {
  const r = build(rebBoard(['A-', 'A+', 'A', 'A-', 'A'], [0.09, 0.01, 0.02, 0.05, 0.04]));
  const rs = rebPlays(r), play = rs.filter(c => c.tier === 'play').map(c => c.title).sort();
  assert.deepEqual(play, ['Reb 1 Over 5.5 Rebounds', 'Reb 2 Over 5.5 Rebounds', 'Reb 4 Over 5.5 Rebounds'], 'A+, then both A (edge breaks no tie needed), A- left out');
  const out = rs.filter(c => c.rebCapped);
  assert.equal(out.length, 2); assert.ok(out.every(c => c.tier === 'pass' && !c.rule && /top 3 rebounds/.test(c.reasons[0])));
  const r2 = build(rebBoard(['A-', 'A-', 'A-', 'A-'], [0.01, 0.04, 0.03, 0.02]));
  assert.deepEqual(rebPlays(r2).filter(c => c.tier === 'play').map(c => c.title).sort(), ['Reb 1 Over 5.5 Rebounds', 'Reb 2 Over 5.5 Rebounds', 'Reb 3 Over 5.5 Rebounds'], 'same grade: the bigger model edge wins');
});

test('stance(): a capped rebounds Pass keeps its side in Passed even when the other side has the better reference edge', () => {
  /* four rebounds A props; Reb 3 (lowest edge) is capped, and its Under has the better reference edge */
  const N = rebBoard(['A', 'A', 'A', 'A'], [0.04, 0.03, 0.02, 0.01]);
  const x = N.props.find(p => p.p === 14); x.kal = [[5.5, 0.44, 0.46, 0.45, 10, 10, NOW - 100]]; x.books = [DK(5.5, '-110', '-110'), PIN(5.5, '+105', '-125')];
  const r = build(N), over = nba(r, 'Reb 3 Over 5.5 Rebounds'), under = nba(r, 'Reb 3 Under 5.5 Rebounds');
  assert.equal(over.rebCapped, true); assert.equal(over.tier, 'pass'); assert.ok(!over.rule, 'not a rule play');
  assert.ok(!over.cautions.some(t => /^Untested rule/.test(t)), 'no rule chip');
  assert.ok((under.best ?? -9) > (over.best ?? -9), 'the Under has the better reference edge');
  const kept = gates.stance(r.all).filter(c => /^Reb 3 /.test(c.title));
  assert.deepEqual(kept.map(c => c.title), ['Reb 3 Over 5.5 Rebounds']);
  assert.match(kept[0].reasons[0], /Outside tonight\u2019s top 3 rebounds plays/);
  assert.equal(gates.stance(r.all).filter(c => c.rebCapped).length, r.all.filter(c => c.rebCapped).length, 'every capped row is shown');
});

test('nba-reb-a cap: before the lock the top 3 show but are not logged; rows already logged tonight hold slots', () => {
  const early = build(rebBoard(['A', 'A', 'A', 'A'], [0.04, 0.03, 0.02, 0.01], NOW + 5 * 3600));
  const top = rebPlays(early).filter(c => c.tier === 'play');
  assert.equal(top.length, 3); assert.ok(top.every(c => c.capPending && /Not locked yet/.test(c.cautions[0])));
  const L = { plays: {} };
  assert.equal(logPlays(L, early.cand, NOW, {}).filter(id => /\|reb\|/.test(id)).length, 0, 'pending plays are not logged');
  const held = { plays: { a: { id: 'a', sport: 'nba', kind: 'prop', status: 'open', start: TIP, firstSeen: NOW - 600, rule: 'nba-reb-a', first: { price: { p: 0.5 } }, prop: { pid: 'nba:99', mkt: 'reb', side: 'over', line: 4.5 } },
    b: { id: 'b', sport: 'nba', kind: 'prop', status: 'won', start: TIP, firstSeen: NOW - 600, rule: 'nba-reb-a', first: { price: { p: 0.5 } }, prop: { pid: 'nba:98', mkt: 'reb', side: 'over', line: 4.5 } } } };
  assert.equal(rebPlays(build(rebBoard(['A', 'A', 'A'], [0.04, 0.03, 0.02]), held)).filter(c => c.tier === 'play').length, 1, 'two slots taken: one left');
});

test('a rebounds prop that is also five of five plays as nba-sig5, outside the cap', () => {
  const N = rebBoard(['A', 'A', 'A', 'A'], [0.04, 0.03, 0.02, 0.01]); N.rules.rows['g1|14|reb'][2] = 5;
  const c = rebPlays(build(N)).find(x => x.title === 'Reb 3 Over 5.5 Rebounds');
  assert.equal(c.tier, 'play'); assert.equal(c.rule, 'nba-sig5');
  assert.equal(rebPlays(build(N)).filter(x => x.rule === 'nba-reb-a').length, 3);
});

test('a rule C play that also matches is tagged but stays rule C (no rule id), and rule plays never take a cap slot', () => {
  const r = build(board({ 'g1|1|pts': [24.5, 'O', 5, 0, 'A', 'O'] }));
  const c = nba(r, 'Play Er Over 24.5 Points');
  assert.equal(c.tier, 'play'); assert.equal(c.rule, undefined); assert.deepEqual(c.rules, ['nba-sig5']);
  const rows = [1, 2, 3, 4, 5, 6].map(i => ({ id: 'r' + i, sport: 'nba', kind: 'prop', status: 'open', start: TIP, firstSeen: NOW - 7200, first: { worst: 0.05, price: { p: 0.5 } }, prop: { pid: 'nba:' + i, mkt: 'pts', side: 'over' }, rule: 'nba-sig5' }));
  assert.equal(gates.capOut(rows).size, 0, 'six rule rows on one night: none capped');
});

test('one side per market: a rule play never takes the side opposite a logged play', () => {
  const L = { plays: { x: { id: 'x', sport: 'nba', kind: 'prop', status: 'open', start: TIP, firstSeen: NOW - 3600, first: { price: { p: 0.55 }, refs: [{ n: 'Exchange', p: 0.6, edge: 0.05 }, { n: 'Pinnacle', p: 0.6, edge: 0.05 }], worst: 0.05 }, prop: { pid: 'nba:2', mkt: 'reb', side: 'under', line: 8.5 }, rule: 'nba-sig5' } } };
  const c = nba(build(board({ 'g1|2|reb': [8.5, 'O', 5, 0, 'B', 'O'] }), L), 'Disagree Dan Over 8.5 Rebounds');
  assert.notEqual(c.tier, 'play');
});

test('heldBack: a stored rule row is judged by its own test, not rule C', () => {
  const row = { id: 'r', sport: 'nba', kind: 'prop', status: 'won', start: TIP, firstSeen: NOW, first: { price: { p: 0.52 }, refs: [] }, rule: 'nba-aplus' };
  assert.deepEqual(gates.heldBack(row), []);
  assert.deepEqual(gates.heldBack({ ...row, rule: undefined }).sort(), ['edge', 'fairs', 'kalshi']);
  assert.deepEqual(gates.heldBack({ ...row, rule: 'nope' }), ['rule']);
});

test('the ledger stores the rule on the row', () => {
  const r = build(board({ 'g1|2|reb': [8.5, 'O', 5, 0, 'B', 'O'] })), L = { plays: {} };
  logPlays(L, r.cand, NOW, {});
  const row = Object.values(L.plays).find(p => p.prop && p.prop.mkt === 'reb');
  assert.equal(row.rule, 'nba-sig5'); assert.deepEqual(row.rules, ['nba-sig5']);
});

/* ---- cfb-novig ---- */
const T0 = NOW + 86400;
const erow = (o) => Object.assign({ sport: 'cfb', gk: 'cfb:1', start: T0, m: 'ml', label: 'KU', line: null, home: 'KU', away: 'KSU', price: '+120', cost: 0.4545, fair: 0.47, ev: 0.034, second: null, nm: 0 }, o);
const cfb = (rows, L = null) => gates.build({ D: { games: [] }, E: { rows }, now: NOW, L });

test('cfb-novig: a CFB Novig price beating Pinnacle by 2%+ that the gates hold back (price under 55%) is a Play, sorted first', () => {
  const nfl = erow({ sport: 'nfl', gk: 'nfl:1', label: 'KC', home: 'KC', away: 'LV', price: '-150', cost: 0.6, fair: 0.64, second: { kal: 0.635 } });
  const r = cfb([nfl, erow()]);
  const c = r.all.find(x => x.sport === 'cfb');
  assert.equal(c.tier, 'play'); assert.equal(c.rule, 'cfb-novig'); assert.equal(c.prio, 1);
  assert.equal(r.cand[0], c, 'CFB Novig sorts ahead of the gates\u2019 plays');
});

test('cfb-novig needs a 2% edge on some reference, and one side per market', () => {
  assert.notEqual(cfb([erow({ fair: 0.46 })]).all[0].tier, 'play', 'under 2% on every reference: not on the board, not a rule play');
  const r = cfb([erow(), erow({ label: 'KSU', price: '+110', cost: 0.4762, fair: 0.5, ev: 0.05 })]);
  assert.equal(r.all.filter(c => c.tier === 'play').length, 1, 'both sides clear: only the better one plays');
  assert.equal(r.all.find(c => c.tier === 'play').side, 'KSU');
});
