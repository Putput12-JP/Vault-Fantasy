/* Tests for the delayed-result check in the Frozen plays box (sv2-record.js): rec.isDelayed, rec.chipText, rec.gradedLine, and the delayed count in
   rec.frozenList / rec.frozenSub. No dependencies: node sharp-money/sharps-v2/tests/sv2-record-delayed.test.mjs
   Loads sv2-core.js then sv2-record.js through node:vm. Every fixture is synthetic: no network, no _dev files. */
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const NOW = 1795278675; // Sat Nov 21 2026 10:31 AM CST

function load() {
  const sandbox = {
    console, Intl, Date, Math, JSON, Object, Array, String, Number, RegExp, Promise, setTimeout, clearTimeout, setInterval, clearInterval,
    module: { exports: {} },
    location: { hostname: 'localhost', search: '?now=' + NOW, hash: '' },
    localStorage: { getItem: () => null, setItem() {} },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'sv2-core.js'), 'utf8'), sandbox);
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'sv2-record.js'), 'utf8'), sandbox);
  return sandbox.module.exports;
}

let pass = 0, fail = 0;
function ok(name, cond, extra) { if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); } }
function eq(name, a, b) { ok(name, JSON.stringify(a) === JSON.stringify(b), { got: a, want: b }); }

const SV2 = load();
const R = SV2.rec;
const HOUR = 3600, MIN = 60;
const H35 = 3.5 * HOUR;
const forbidden = SV2.copy.forbidden;
const banned = (text) => forbidden.filter((w) => new RegExp('\\b' + w + '\\b', 'i').test(text));

let k = 0;
const open = (o) => Object.assign({ key: 'c' + (++k) + '|ml|all|sf', counts: true, sport: 'nba', ev: 'nba-aaa-bbb-2026-11-24', gst: NOW - 4 * HOUR, group: 'ml', play: 'sf', side: 'Hornets', line: null, outs: ['Grizzlies', 'Hornets'], units: 1, price: 0.425 }, o);
const item = (o) => Object.assign({ state: 'open', word: 'Awaiting result', gst: NOW - 4 * HOUR }, o);

console.log('the threshold is 3.5 hours, strictly more');
{
  eq('constants', [R.DELAYED_AFTER, R.BEHIND_AFTER], [12600, 10800]);
  eq('exactly 3.5 hours is not delayed', R.isDelayed(item({ gst: NOW - H35 }), NOW), false);
  eq('one second under is not delayed', R.isDelayed(item({ gst: NOW - H35 + 1 }), NOW), false);
  eq('one second over is delayed', R.isDelayed(item({ gst: NOW - H35 - 1 }), NOW), true);
  eq('well over is delayed', R.isDelayed(item({ gst: NOW - 9 * HOUR }), NOW), true);
  eq('a game that has not started is not delayed', R.isDelayed(item({ gst: NOW + HOUR }), NOW), false);
  eq('a postponed play is never delayed', R.isDelayed(item({ word: 'Postponed', gst: NOW - 9 * HOUR }), NOW), false);
  eq('only an open play can be delayed, whatever its word', R.isDelayed(item({ state: 'win', gst: NOW - 9 * HOUR }), NOW), false);
  eq('a graded play is never delayed', ['win', 'loss', 'push', 'void', 'unpriced'].map((s) => R.isDelayed(item({ state: s, word: 'W', gst: NOW - 9 * HOUR }), NOW)), [false, false, false, false, false]);
  eq('no game start, no clock or no item: not delayed', [R.isDelayed(item({ gst: null }), NOW), R.isDelayed(item({ gst: undefined }), NOW), R.isDelayed(item(), undefined), R.isDelayed(item(), null), R.isDelayed(null, NOW), R.isDelayed(item({ gst: '1' }), NOW)], [false, false, false, false, false, false]);
}

console.log('the result chip text and the aria text');
{
  const plain = R.chipText(item());
  eq('an awaiting play keeps its word, spoken text and no tooltip', [plain.word, plain.say, plain.title], ['Awaiting result', 'Awaiting result', null]);
  const d = R.chipText(item({ delayed: true }));
  eq('a delayed play says Result delayed', d.word, 'Result delayed');
  eq('the tooltip is the exact sentence', d.title, 'The game started over 3.5 hours ago and has no graded result yet. Grading runs about every 2 hours and waits on Polymarket.');
  eq('the spoken text is the word, then the sentence', d.say, 'Result delayed. The game started over 3.5 hours ago and has no graded result yet. Grading runs about every 2 hours and waits on Polymarket.');
  eq('a settled row is unchanged: word with units, spoken as words', [R.chipText({ state: 'win', word: 'W', units: '+0.4u' }), R.chipText({ state: 'loss', word: 'L', units: '-1u' }), R.chipText({ state: 'void', word: 'Void', units: null })],
    [{ word: 'W +0.4u', say: 'Win, +0.4 units', title: null }, { word: 'L -1u', say: 'Loss, -1 units', title: null }, { word: 'Void', say: 'Void', title: null }]);
  eq('a postponed play keeps its own word', R.chipText(item({ word: 'Postponed' })).word, 'Postponed');
}

console.log('the last graded line');
{
  const t = 1795278675 - 20 * MIN;                       /* 10:11 AM Central on Nov 21 */
  eq('today: time with CT, no date, no warning', R.gradedLine(t, NOW), 'Last graded ' + SV2.ct.time(t, true) + '.');
  ok('the shape is the requested one', /^Last graded \d{1,2}:\d\d [AP]M CT\.$/.test(R.gradedLine(t, NOW)), R.gradedLine(t, NOW));
  eq('exactly 3 hours old: no warning', R.gradedLine(NOW - 3 * HOUR, NOW).indexOf('behind'), -1);
  eq('3 hours and a second: behind', R.gradedLine(NOW - 3 * HOUR - 1, NOW).slice(-19), ' Grading is behind.');
  eq('under 3 hours: no warning', R.gradedLine(NOW - 3 * HOUR + 1, NOW).indexOf('behind'), -1);
  const y = NOW - 26 * HOUR;
  eq('another Central day: the date is added so the time is not read as today', R.gradedLine(y, NOW), 'Last graded ' + SV2.ct.md(y) + ', ' + SV2.ct.time(y, true) + '. Grading is behind.');
  eq('Central, not UTC: 10:39 AM CT', R.gradedLine(Date.UTC(2026, 10, 24, 16, 39) / 1000, Date.UTC(2026, 10, 24, 16, 59) / 1000), 'Last graded 10:39 AM CT.');
  eq('a generated time in the future is not behind', R.gradedLine(NOW + HOUR, NOW).indexOf('behind'), -1);
  eq('missing generated shows nothing', [R.gradedLine(undefined, NOW), R.gradedLine(null, NOW), R.gradedLine('x', NOW), R.gradedLine(NaN, NOW), R.gradedLine(Infinity, NOW)], ['', '', '', '', '']);
}

console.log('the list and the subtitle: counts stay, delayed is added apart');
{
  const rows = [], p = (a, o) => open(Object.assign({ gst: NOW - a }, o));
  const file = { open: [p(5 * HOUR), p(H35 + 1), p(H35), p(2 * HOUR), p(6 * HOUR, { postponed: true }), p(6 * HOUR, { sport: 'cfb' })] };
  const L = R.frozenList(rows, file, {}, 'all', { now: NOW });
  eq('awaiting counts every open play, as before', [L.total, L.awaiting, L.settled], [5, 5, 0]);
  eq('delayed counts only those past 3.5 hours and not postponed', L.delayed, 2);
  eq('the rows carry the flag', L.items.map((x) => [x.gst === NOW - 5 * HOUR || x.gst === NOW - H35 - 1 ? 'late' : 'ok', x.delayed === true]).filter((a) => a[0] === 'late').map((a) => a[1]), [true, true]);
  eq('subtitle names the delayed count apart from awaiting', R.frozenSub(L), '5 frozen plays: 5 awaiting result, 2 delayed');
  const L0 = R.frozenList(rows, file, {}, 'all');
  eq('without a clock nothing is delayed and the subtitle is the old one', [L0.delayed, R.frozenSub(L0)], [0, '5 frozen plays: 5 awaiting result']);
  const none = R.frozenList(rows, { open: [p(2 * HOUR)] }, {}, 'all', { now: NOW });
  eq('no delayed play: no delayed words', R.frozenSub(none), '1 frozen play: 1 awaiting result');
  eq('empty list: empty subtitle and zero delayed', [R.frozenSub(R.frozenList([], null, {}, 'all', { now: NOW })), R.frozenList([], null, {}, 'all', { now: NOW }).delayed], ['', 0]);
  /* the live list (locked) takes the same flag */
  const lk = { key: 'nba/frozen/2026-11-21/nba-aaa-bbb-2026-11-21@1.json|ml|all|sf', sport: 'nba', gst: NOW - 5 * HOUR, group: 'ml', play: 'sf', side: 'Hornets', outs: ['A', 'Hornets'], units: 1 };
  const LL = R.frozenList([], null, {}, 'all', { locked: [lk], now: NOW });
  eq('a live frozen play 5 hours in is delayed', [LL.awaiting, LL.delayed, R.frozenSub(LL)], [1, 1, '1 frozen play: 1 awaiting result, 1 delayed']);
}

console.log('parity with the Record page');
{
  const row = (o) => Object.assign({ kind: 'result', play: 'sf', variant: 'all', counts: true, status: 'graded', sport: 'nba', group: 'ml', res: 'win', flat: 0.5, cut: R.FWD_CUT + 1000, key: 'r' + (++k), graded_at: 1000 + k, side: 'Hawks', price: 0.6 }, o);
  const settled = [row({ res: 'win', flat: 0.4 }), row({ res: 'loss', flat: -1, sport: 'cbb' }), row({ res: 'push', flat: 0, sport: 'nfl' }), row({ status: 'void', res: null, flat: null }), row({ sport: 'cfb' }), row({ play: 'lock' })];
  const file = { open: [open({ gst: NOW - 7 * HOUR }), open({ gst: NOW - HOUR })] };
  const a = R.frozenList(settled, file, {}, 'all'), b = R.frozenList(settled, file, {}, 'all', { now: NOW });
  const strip = (L) => JSON.stringify({ total: L.total, awaiting: L.awaiting, settled: L.settled, tally: L.tally, keys: L.items.map((x) => x.key + x.state + x.word) });
  eq('with the clock the total, awaiting, settled, tally and rows equal the list without it', strip(b), strip(a));
  const t = R.tally(R.playRows(settled, 'all'), {});
  eq('the W-L-P is the Record page tally of the same rows', [b.tally.w, b.tally.l, b.tally.p, b.tally.n], [t.w, t.l, t.p, t.n]);
  eq('the settled plays are exactly the Plays record rows', b.items.filter((x) => x.state !== 'open').map((x) => x.key).sort(), R.playRows(settled, 'all').map((x) => x.key).sort());
  eq('awaiting stays the open count; delayed is inside it', [b.awaiting, b.delayed, b.delayed <= b.awaiting], [2, 1, true]);
  eq('the subtitle keeps the record, awaiting, delayed and not graded in that order', R.frozenSub(b), '6 frozen plays, 1-1-1, flat 1u, 2 awaiting result, 1 delayed, 1 not graded');
}

console.log('words and style');
{
  const all = [R.DELAYED_WORD, R.DELAYED_TIP, R.chipText(item({ delayed: true })).say, R.gradedLine(NOW - 5 * HOUR, NOW), R.gradedLine(NOW - 26 * HOUR, NOW),
    R.frozenSub(R.frozenList([], { open: [open({ gst: NOW - 9 * HOUR })] }, {}, 'all', { now: NOW }))].join(' ');
  eq('no banned word in the new text (sv2-core copy.forbidden)', banned(all), []);
  ok('the banned list is the one in the core file', forbidden.length === 16 && forbidden.includes('confidence') && forbidden.includes('best bet'), forbidden);
  const em = String.fromCharCode(0x2014);
  ok('no em dash in the new text', !all.includes(em));
  const src = fs.readFileSync(path.join(ROOT, 'sv2-record.js'), 'utf8');
  const fz = src.slice(src.indexOf('function fzRow'), src.indexOf('function frozenInner'));
  ok('the delayed chip is a neutral ink chip, never a win, loss or caution colour', /m\.delayed \? 'ink'/.test(fz) && !/delayed[^;]*(caution|loss|win)/.test(fz));
  ok('the delayed tooltip and the spoken text come from one place', /rec\.chipText\(m\)/.test(fz) && /chip\.title/.test(fz) && /chip\.say/.test(fz));
  ok('the box passes its clock to the list', /rec\.frozenList\(S\.rows, S\.file, S\.tl\.map, sp, \{ locked: lockedNow\(\), cards: S\.fzc\.map, now: now \}\)/.test(src));
  ok('the box reads the clock once and shows the graded line only from generated', /rec\.gradedLine\(S\.file && S\.file\.generated, now\)/.test(src));
}

console.log('\n' + pass + ' pass, ' + fail + ' fail');
process.exit(fail ? 1 : 0);
