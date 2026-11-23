/* Unit tests for the pure parts of sv2-following.js (exposed as SV2.fw). No dependencies:
   node sharp-money/sharps-v2/tests/sv2-following.test.mjs
   sv2-core.js and sv2-following.js are loaded through node:vm. Tests that need real data read _dev/ (never committed) and are
   reported as skipped when it is absent. */
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const DEV = path.join(ROOT, '_dev');

function load() {
  const store = {};
  const sandbox = {
    console, Intl, Date, Math, JSON, Object, Array, String, Number, RegExp, Promise, setTimeout, clearTimeout, setInterval, clearInterval,
    module: { exports: {} },
    location: { hostname: 'localhost', search: '', hash: '' },
    localStorage: { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'sv2-core.js'), 'utf8'), sandbox);
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'sv2-following.js'), 'utf8'), sandbox);
  return sandbox.SV2;
}

let pass = 0, fail = 0, skipped = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); }
}
function eq(name, a, b) { ok(name, JSON.stringify(a) === JSON.stringify(b), { got: a, want: b }); }
function skip(name) { skipped++; console.log('  skip ' + name + ' (no _dev fixtures)'); }
function readDev(f) { const p = path.join(DEV, f); return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null; }

const SV2 = load();
const fw = SV2.fw;
ok('SV2.fw is exposed', !!fw && typeof fw.mkRow === 'function');

console.log('declared (v2_fields is the gate for every added key)');
eq('absent v2_fields', fw.declared({}, 'fwd'), false);
eq('string, whole word', [fw.declared({ v2_fields: 'per wallet: flat_roi fwd first_seen (rk.post rk.sd)' }, 'fwd'), fw.declared({ v2_fields: 'per wallet: flat_roi fwd' }, 'first_seen')], [true, false]);
eq('dotted key', [fw.declared({ v2_fields: '(rk.post rk.sd)' }, 'rk.post'), fw.declared({ v2_fields: 'rk_post' }, 'rk.post')], [true, false]);
eq('array', [fw.declared({ v2_fields: ['fwd', 'v2'] }, 'v2'), fw.declared({ v2_fields: ['fwd'] }, 'v2')], [true, false]);
eq('prefix is not a match', fw.declared({ v2_fields: 'fwdx' }, 'fwd'), false);

console.log('ages and prices');
eq('ageText', [fw.ageText(0), fw.ageText(19), fw.ageText(60), fw.ageText(959), fw.ageText(1440), fw.ageText(7808), fw.ageText(null)], ['<1 min', '19 min', '1 h', '15 h', '1 d', '5 d', null]);
eq('stored px_age_min wins when declared', fw.pxAgeMin({ v2_fields: 'px_age_min', built: 1000 }, { px_age_min: 7, px_t: 100 }), 7);
eq('built minus px_t when not declared', fw.pxAgeMin({ built: 7200 }, { px_age_min: 7, px_t: 0 }), 120);
eq('no px_t: null, not zero', fw.pxAgeMin({ built: 7200 }, {}), null);
eq('with a page clock the file age since the build is added', [fw.pxAgeMin({ built: 7200 }, { px_t: 0 }, 7200 + 600), fw.pxAgeMin({ built: 7200 }, { px_t: 0 }, 7000), fw.pxAgeMin({ built: 7200 }, {}, 9000)], [130, 120, null]);

console.log('rows');
{
  const v1 = { built: 2000000000, sports: {} };
  const r1 = fw.mkRow(v1, 'nba', '0x' + 'a'.repeat(40), { name: null, n: 40, w_: 25, l_: 15, roi: 0.1, rk: { tier: 'sharp', n: 60, mean: 0.0123 } }, false);
  eq('v1: tier words from rk.tier', r1.tier, 'beats');
  eq('v1: raw mean, labelled raw', r1.cents, { v: 0.0123, raw: true });
  eq('v1: forward record is not published', [r1.fwdPub, r1.fwd], [false, null]);
  eq('v1: unnamed wallet', r1.name, 'Unnamed 0xaaaa...aaaa');
  eq('v1: past winner by the stored rule', r1.past, true);
  const v2 = { built: 2000000000, v2_fields: 'fwd rk.post name_disp', sports: {} };
  const r2 = fw.mkRow(v2, 'nba', '0x' + 'b'.repeat(40), { name_disp: 'abc', n: 40, rk: { tier: 'sharp', n: 60, mean: 0.0123, post: 0.01 }, fwd: { w: 1, l: 1, p: 0, n: 2 } }, false);
  eq('v2: shrunk value when rk.post is declared and present', r2.cents, { v: 0.01, raw: false });
  eq('v2: forward record', [r2.fwdPub, r2.fwd.n], [true, 2]);
  const r3 = fw.mkRow({ built: 2000000000, sports: {} }, 'nba', '0x' + 'c'.repeat(40), { rk: { tier: 'sharp', n: 60, mean: 0.02, post: 0.01 } }, false);
  eq('rk.post present but not declared: not used', r3.cents, { v: 0.02, raw: true });
  const r4 = fw.mkRow(v2, 'cfb', '0x' + 'd'.repeat(40), { name: 'x', rk: { tier: 'sharp', n: 60, mean: 0.02 } }, false);
  eq('college row is always "few" with no cents', [r4.tier, r4.cents], ['few', null]);
  const r5 = fw.mkRow({ built: 1000000, v2_fields: 'n30_games' }, 'nba', '0x' + 'e'.repeat(40), { n30_games: 0 }, false);
  eq('inactive from n30_games == 0', r5.inactive, true);
  const r6 = fw.mkRow({ built: 1000000 + 31 * 86400 }, 'nba', '0x' + 'e'.repeat(40), { legs: [[1000000, 'win']] }, false);
  eq('inactive fallback: newest leg older than 30 days', r6.inactive, true);
  const r7 = fw.mkRow({ built: 1000000 + 5 * 86400 }, 'nba', '0x' + 'e'.repeat(40), { legs: [[1000000, 'win']] }, false);
  eq('active fallback: newest leg inside 30 days', r7.inactive, false);
  eq('past winner needs n >= 6, 55% wins and ROI over 3%', [fw.pastWinner({ n: 5, w_: 5, roi: 0.5 }), fw.pastWinner({ n: 20, w_: 10, roi: 0.5 }), fw.pastWinner({ n: 20, w_: 12, roi: 0.03 }), fw.pastWinner({ n: 20, w_: 12, roi: 0.031 })], [false, false, false, true]);
}

console.log('search');
{
  const mk = (name, w) => fw.mkRow({ built: 1 }, 'nba', w, { name }, false);
  const a = mk('MonkeyMash', '0x684baa57c338c2549aec0aa3f034f695d72a8409');
  eq('name fragment, any case', [fw.matches(a, 'monkey'), fw.matches(a, 'MASH'), fw.matches(a, 'zzz')], [true, true, false]);
  eq('address fragment of 4+ hex, with or without 0x', [fw.matches(a, '684b'), fw.matches(a, '0x684b'), fw.matches(a, '8409'), fw.matches(a, 'aa5')], [true, true, true, false]);
  eq('empty query matches all', fw.matches(a, '  '), true);
  eq('a non-hex fragment never matches the address', fw.matches(mk('x', '0x684baa57c338c2549aec0aa3f034f695d72a8409'), 'g684b'), false);
}

console.log('odds and size bands (the builder cut points)');
eq('oddsBand edges', [fw.oddsBand(0.32)[0], fw.oddsBand(0.4)[0], fw.oddsBand(0.5)[0], fw.oddsBand(0.6)[0], fw.oddsBand(0.99)[0], fw.oddsBand(null)], ['dd', 'd1', 'f1', 'f2', 'ff', null]);
eq('sizeBand edges', [fw.sizeBand(0.74), fw.sizeBand(0.75), fw.sizeBand(1.49), fw.sizeBand(1.5), fw.sizeBand(null)], ['small', 'usual', 'usual', 'big', null]);
eq('teamsOf', [fw.teamsOf('nfl-tb-det-2026-11-22'), fw.teamsOf('cbb-colmb-bostu-2026-11-21')], ['TB at DET', 'COLMB at BOSTU']);
eq('default sort: college is Activity, the rest Price edge', [fw.defaultSort('all'), fw.defaultSort('nba'), fw.defaultSort('cfb'), fw.defaultSort('cbb')], ['price', 'price', 'act', 'act']);

console.log('sorts on synthetic rows');
{
  const mkr = (name, tier, mean, n, extra) => Object.assign(fw.mkRow({ built: 1 }, 'nba', '0x' + String(name.charCodeAt(0)).padStart(40, '0'), { name, rk: tier ? { tier, n, mean } : null }, false), extra || {});
  const rows = [mkr('dull', 'dull', -0.01, 100), mkr('none', null, 0, 0), mkr('thin', 'thin', 0.03, 12), mkr('mid', 'mid', 0.002, 80), mkr('sharpA', 'sharp', 0.012, 60), mkr('sharpB', 'sharp', 0.02, 40)];
  eq('price edge: beats, even, few, loses; cents desc inside a tier', fw.sortRows(rows, 'price').map((r) => r.name), ['sharpB', 'sharpA', 'mid', 'thin', 'none', 'dull']);
  ok('a price-dull wallet never sorts above an unrated one', fw.sortRows(rows, 'price').map((r) => r.name).indexOf('dull') > fw.sortRows(rows, 'price').map((r) => r.name).indexOf('none'));
  const f = (n, roi) => ({ fwd: n == null ? null : { n, flat_roi: roi } });
  const fr = [mkr('a', null, 0, 0, f(5, 0.9)), mkr('b', null, 0, 0, f(25, 0.1)), mkr('c', null, 0, 0, f(40, 0.3)), mkr('d', null, 0, 0, f(null)), mkr('e', null, 0, 0, f(3, 0.1))];
  eq('since tracked: 20+ forward bets lead by flat ROI, the rest by bets', fw.sortRows(fr, 'fwd').map((r) => r.name), ['c', 'b', 'a', 'e', 'd']);
  const ar = [mkr('p', null, 0, 0, { n30: 3, last: 10 }), mkr('q', null, 0, 0, { n30: 9, last: 5 }), mkr('r', null, 0, 0, { n30: null, last: 50 }), mkr('s', null, 0, 0, { n30: 9, last: 8 })];
  eq('activity: games in 30 days, then last settled, nulls last', fw.sortRows(ar, 'act').map((r) => r.name), ['s', 'q', 'p', 'r']);
  const or = [mkr('x', null, 0, 0, { _usd: 100, _n: 1 }), mkr('y', null, 0, 0, { _usd: null, _n: 0 }), mkr('z', null, 0, 0, { _usd: 900, _n: 2 })];
  eq('open now: summed value desc, none last', fw.sortRows(or, 'open').map((r) => r.name), ['z', 'x', 'y']);
}

console.log('real files');
const wV2 = readDev('wallets-fin.json'), wV1 = readDev('wallets.json');
if (!wV1) skip('past winner count'); else {
  let n = 0; Object.keys(wV1.sports).forEach((sp) => Object.keys(wV1.sports[sp]).forEach((w) => { if (fw.pastWinner(wV1.sports[sp][w])) n++; }));
  eq('past winner rule gives the 668 rows the audit counted', n, 668);
}
if (!wV2) { skip('feed'); skip('directory'); } else {
  const idx = {}, rows = [];
  Object.keys(wV2.sports).forEach((sp) => Object.keys(wV2.sports[sp]).forEach((w) => { const r = fw.mkRow(wV2, sp, w, wV2.sports[sp][w], false); idx[r.k] = r; rows.push(r); }));
  const pick = (sp, name) => rows.find((r) => r.sp === sp && r.name === name);
  const mm = pick('nfl', 'monkeymashingkeyboard'), fc = pick('nba', 'forecastication4'), nig = pick('cbb', 'nigiri99');
  const fl = [mm, fc, nig].map((r, i) => ({ sport: r.sp, w: r.w, at: 1794890000 + i }));
  const NOW = 1795278675;
  const feed = fw.buildFeed(wV2, fl, idx, NOW, 'all');
  ok('feed has bets', feed.nBets > 0, feed.nBets);
  ok('games are in start order', feed.games.every((g, i) => i === 0 || feed.games[i - 1].gst <= g.gst));
  ok('every shown game is before its cut', feed.games.every((g) => g.gst - 900 > NOW));
  const late = fw.buildFeed(wV2, fl, idx, 1795278675 + 40 * 86400, 'all');
  eq('after every cut the feed is empty', late.nBets, 0);
  const nfl = fw.buildFeed(wV2, fl, idx, NOW, 'nfl');
  ok('sport filter counts what it hides', nfl.hidden === feed.nBets - nfl.nBets && nfl.hidden > 0, [nfl.hidden, feed.nBets, nfl.nBets]);
  const total = feed.games.reduce((s, g) => s + g.bets.length, 0);
  eq('nBets is the number of side rows', total, feed.nBets);
  /* same-side note: two followed wallets on one side of one game */
  const both = fw.buildFeed(wV2, [{ sport: 'nba', w: fc.w, at: 1 }, { sport: 'nba', w: pick('nba', 'SunlineTicker').w, at: 1 }], idx, NOW, 'all');
  ok('two followed wallets on a side are noted', both.sameGames >= 1, both.sameGames);
  const g1 = fw.liveGroups(wV2, fc, NOW).find((g) => g.rungs > 1);
  ok('a multi-rung side carries the stored total (sum of its rungs)', !!g1 && Math.abs(g1.total - g1.positions.reduce((s, p) => s + p.usd, 0)) <= 1, g1 && [g1.total, g1.rungs]);
  /* directory sorts on the real file, all rows */
  const price = fw.sortRows(rows, 'price');
  const rank = { beats: 0, even: 1, few: 2, loses: 3 };
  ok('price edge never puts "loses" above "few" or "even"', price.every((r, i) => i === 0 || rank[price[i - 1].tier] <= rank[r.tier]));
  const beats = price.filter((r) => r.tier === 'beats' && r.cents);
  ok('inside "beats" the cents shown run high to low', beats.every((r, i) => i === 0 || beats[i - 1].cents.v >= r.cents.v));
  const fwd = fw.sortRows(rows, 'fwd'), q = fwd.filter((r) => r.fwd && r.fwd.n >= 20);
  ok('since tracked: all 20+ rows lead', fwd.slice(0, q.length).every((r) => r.fwd && r.fwd.n >= 20));
  ok('since tracked: flat ROI high to low among them', q.every((r, i) => i === 0 || q[i - 1].fwd.flat_roi >= r.fwd.flat_roi));
  const act = fw.sortRows(rows, 'act');
  ok('activity: games in 30 days high to low', act.every((r, i) => i === 0 || act[i - 1].n30 >= r.n30));
  const inactive = rows.filter((r) => r.inactive).length;
  eq('inactive rows (no game in 30 days) on the Nov 21 build', inactive, 406);
  const sc = rows.filter((r) => r.sc).length;
  eq('scorecard chip rows (own sport only) on the Nov 21 build', sc, 22);
  const cuts = fw.cutsOf(fc, fw.liveGroups(wV2, fc, NOW).find((g) => g.g === 'ml'));
  ok('cuts around a moneyline bet: all, this bet type, then favourite or underdog, size, odds', cuts.length >= 3 && cuts[0].key === 'all' && cuts[1].key === 'mkt-ml', cuts.map((c) => c.key));
  ok('every cut cell is a stored dive cell [w, l, roi]', cuts.every((c) => !c.cell || (c.cell.length >= 3)));
}

/* the past-record columns: record, ROI, bets, last 10, market lane */
{
  const r = { w_: 12, l_: 8, roi: 0.05, n: 20, dive: { lane: { ml: [3, 1, 0.4], spread: [0, 0, 0] } },
    legs: [[5, 'win'], [4, 'push'], [3, 'loss'], [2, 'win'], [1, 'win']] };
  const row = fw.mkRow({ built: 100 }, 'nba', '0xabc', r, false);
  eq('record, all bets: stored w_ l_ roi n', fw.recOf(row, 'all'), { w: 12, l: 8, roi: 0.05, n: 20 });
  eq('record by market reads dive.lane [w, l, roi]', fw.recOf(row, 'ml'), { w: 3, l: 1, roi: 0.4, n: 4 });
  ok('a market with no graded bets is null, never a zero', fw.recOf(row, 'spread') === null && fw.recOf(row, 'total') === null);
  eq('last 10: graded legs only, newest first', fw.lastTen(row).map((x) => x[1]), ['win', 'loss', 'win', 'win']);
  const mk = (n, roi, name) => { const x = fw.mkRow({ built: 100 }, 'nba', name, { w_: n, l_: 0, roi, n, name }, false); x._rec = fw.recOf(x, 'all'); return x; };
  const rows = [mk(6, 1.0, 'thin6'), mk(40, 0.1, 'big'), mk(25, 0.3, 'mid')];
  eq('ROI sort: 20+ bets lead, thin rows follow', fw.sortRows(rows, 'roi').map((x) => x.name), ['mid', 'big', 'thin6']);
  eq('Wallet sort is by name', fw.sortRows(rows, 'name').map((x) => x.name), ['big', 'mid', 'thin6']);
}

console.log('\n' + pass + ' passed, ' + fail + ' failed, ' + skipped + ' skipped');
process.exit(fail ? 1 : 0);
