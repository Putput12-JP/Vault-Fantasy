// The older Sharp Money prop ledger (prop_plays.json): settle in the kickoff's week, grade a player who played and recorded none of a stat,
// void a real DNP, and fix rows settled before those rules once.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { settleProps, fetchPropSnaps, nflWeekOf, SLEEPER_WEEK } from '../scripts/track-prop-plays.mjs';

const START = Date.parse('2026-11-01T18:00Z') / 1000, WK = nflWeekOf(START, '2026');
const play = (o = {}) => ({ id: 'p1', season: '2026', week: WK, pid: '9', name: 'Test Player', team: 'DEN', mkt: 'rec', line: 1.5, side: 'under',
  start: START, firstSeen: START - 3600, called: { p: 0.5 }, status: 'open', ...o });
const leg = (o = {}) => ({ id: 'g1', season: '2026', week: WK, pid: '9', name: 'Test Player', team: 'DEN', mkt: 'rec', book: 'Underdog', line: 1.5, side: 'under',
  p: 0.6, start: START, firstSeen: START - 3600, status: 'open', ...o });
// the opponent has a row that week, so DEN's game is in the box; Test Player has none
const boxNoRow = { Opp: { weeks: [{ wk: WK, opp: 'DEN', rec: 3 }] } };
const snaps = row => ({ ['2026|' + WK]: { 9: row, 77: { gp: 1 } } });
const run = (L, o) => settleProps(L, { nowS: START + 4 * 3600, stats: boxNoRow, ...o });

test('a play and a leg whose player took snaps but has no box-score row are graded at 0 from Sleeper', () => {
  const L = { plays: { p1: play() }, legs: { g1: leg({ side: 'over' }) } };
  const o = run(L, { nflSnaps: snaps({ gp: 1, off_snp: 29 }) });
  assert.equal(L.plays.p1.status, 'won'); assert.equal(L.plays.p1.actual, 0); assert.equal(L.plays.p1.units, 1); assert.equal(L.plays.p1.actualSrc, 'sleeper');
  assert.equal(L.legs.g1.status, 'lost'); assert.equal(L.legs.g1.units, undefined, 'legs carry no price');
  assert.deepEqual(o, { settled: 2, void: 0, regraded: 0 });
});

test('active without a snap, or off the stat sheet, is void once the game is in the box; before that it waits', () => {
  for (const row of [{ gms_active: 1 }, undefined]) {
    const L = { plays: { p1: play() }, legs: { g1: leg() } };
    run(L, { nflSnaps: snaps(row) });
    for (const x of [L.plays.p1, L.legs.g1]) { assert.equal(x.status, 'void'); assert.equal(x.voidWhy, 'dnp'); }
    assert.equal(L.plays.p1.units, 0);
  }
  const L = { plays: { p1: play() }, legs: {} };
  run(L, { stats: {}, nflSnaps: snaps(undefined) });
  assert.equal(L.plays.p1.status, 'open', 'his game is not in the box yet');
  run(L, { stats: {}, nowS: START + 37 * 3600 });
  assert.equal(L.plays.p1.status, 'void'); assert.equal(L.plays.p1.voidWhy, 'nobox', 'no answer 36h after kickoff is still void');
});

test('the box-score week comes from kickoff, not the board week', () => {
  const L = { plays: { p1: play({ week: WK - 1, side: 'over' }) }, legs: {} };
  run(L, { stats: { 'Test Player': { weeks: [{ wk: WK - 1, rec: 0 }, { wk: WK, rec: 4 }] } } });
  assert.equal(L.plays.p1.status, 'won'); assert.equal(L.plays.p1.actual, 4); assert.equal(L.plays.p1.statWeek, WK);
});

test('history: an old void is regraded if he played, and stays void if he did not; an unread week is left to try again', () => {
  const L = { plays: { p1: play({ status: 'void', units: 0 }), p2: play({ id: 'p2', pid: '8', status: 'void', units: 0 }) }, legs: { g1: leg({ status: 'void' }) } };
  const o = run(L, { nowS: START + 50 * 3600, nflSnaps: { ['2026|' + WK]: { 9: { gp: 1, off_snp: 12 }, 8: { gms_active: 1 } } } });
  assert.equal(L.plays.p1.status, 'won'); assert.deepEqual(L.plays.p1.regraded.from, 'void');
  assert.equal(L.legs.g1.status, 'won');
  assert.equal(L.plays.p2.status, 'void'); assert.equal(L.plays.p2.voidWhy, 'dnp'); assert.equal(L.plays.p2.regraded, undefined);
  assert.equal(o.regraded, 2);
  const U = { plays: { p1: play({ status: 'void', units: 0 }) }, legs: {} };
  run(U, { nowS: START + 50 * 3600 });
  assert.equal(U.plays.p1.voidWhy, undefined, 'no Sleeper read: looked at again next run');
});

test('history: a row graded on the board\'s lagging week is graded again on its own game, once', () => {
  const stats = { 'Test Player': { weeks: [{ wk: WK - 1, rec: 5 }, { wk: WK, rec: 1 }] } };
  const L = { plays: { p1: play({ week: WK - 1, side: 'over', status: 'won', actual: 5, units: 1, settledAt: 1 }) }, legs: { g1: leg({ week: WK - 1, side: 'under', status: 'lost', actual: 5 }) } };
  const o = run(L, { stats, nowS: START + 50 * 3600 });
  const P = L.plays.p1;
  assert.equal(P.status, 'lost'); assert.equal(P.units, -1); assert.equal(P.actual, 1); assert.equal(P.statWeek, WK);
  assert.deepEqual(P.regraded, { from: 'won', wk: WK - 1, actual: 5, units: 1, at: START + 50 * 3600 });
  assert.equal(L.legs.g1.status, 'won'); assert.equal(o.regraded, 2);
  assert.deepEqual(run(L, { stats, nowS: START + 60 * 3600 }), { settled: 0, void: 0, regraded: 0 }, 'not looked at again');
  // same result on the right week: the week is noted, nothing is marked regraded
  const S = { plays: { p1: play({ week: WK - 1, side: 'over', status: 'won', actual: 4, units: 1, settledAt: 1 }) }, legs: {} };
  run(S, { stats: { 'Test Player': { weeks: [{ wk: WK, rec: 4 }] } }, nowS: START + 50 * 3600 });
  assert.equal(S.plays.p1.statWeek, WK); assert.equal(S.plays.p1.regraded, undefined); assert.equal(S.plays.p1.settledAt, 1);
});

test('Sleeper is read once per week the plays and legs still need, regular season only', async () => {
  const seen = [];
  const L = { plays: { p1: play(), p2: play({ id: 'p2', status: 'won', actual: 0 }), p3: play({ id: 'p3', start: START + 10 * 86400 }) },
    legs: { g1: leg({ status: 'void' }), g2: leg({ status: 'void', voidWhy: 'dnp', start: START - 7 * 86400 }) } };
  const got = await fetchPropSnaps(L, START + 4 * 3600, async u => { seen.push(u); return { 1: { gp: 1 } }; });
  assert.deepEqual(seen, [SLEEPER_WEEK('2026', WK)]); assert.ok(got['2026|' + WK]);
});
