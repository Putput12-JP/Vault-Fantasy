/* Unit tests for the pure parts of sv2-record.js. No dependencies: node sharp-money/sharps-v2/tests/sv2-record.test.mjs
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
function near(name, a, b, tol) { ok(name, typeof a === 'number' && Math.abs(a - b) <= (tol || 1e-9), { got: a, want: b }); }

const SV2 = load();
const R = SV2.rec;
ok('SV2.rec is exposed', !!R && typeof R.tally === 'function');

const CUT = R.FWD_CUT;
eq('the forward cut is 2026-11-16 12:00 AM Central', [SV2.ct.dateKey(CUT), SV2.ct.time(CUT)], ['2026-11-16', '12:00 AM']);

/* a result row of the shown play */
let k = 0;
function row(o) {
  k++;
  return Object.assign({ kind: 'result', play: 'sf', variant: 'all', counts: true, status: 'graded', sport: 'nba', group: 'ml', res: 'win', flat: 0.5, cut: CUT + 1000, key: 'r' + k, graded_at: 1000 + k, side: 'Hawks', price: 0.6 }, o);
}

console.log('parseJsonl');
{
  const t = '{"key":"a","v":1}\nnot json\n\n{"key":"b","v":2}\n{"key":"a","v":3}\n[1]\n';
  const r = R.parseJsonl(t);
  eq('bad lines dropped, a repeated key keeps the last row in place', r.map(x => x.key + x.v), ['a3', 'b2']);
  eq('empty and null input', [R.parseJsonl(''), R.parseJsonl(null)], [[], []]);
}

console.log('playRows (counted shown plays only)');
{
  const rows = [row({ sport: 'nba' }), row({ sport: 'cfb' }), row({ sport: 'cbb' }), row({ counts: false }), row({ play: 'lock' }), row({ variant: 'fwd' }), row({ kind: 'close' }), row({ sport: 'nfl' })];
  eq('all = nba, nfl, cbb (CFB shows no size)', R.playRows(rows, 'all').map(r => r.sport), ['nba', 'cbb', 'nfl']);
  eq('one sport', R.playRows(rows, 'cfb').map(r => r.sport), ['cfb']);
  eq('default is all', R.playRows(rows).length, 3);
  eq('case does not matter', R.playRows(rows, 'NBA').length, 1);
}

console.log('tally (flat 1u)');
{
  const rows = [row({ res: 'win', flat: 0.5 }), row({ res: 'loss', flat: -1 }), row({ res: 'push', flat: 0 }), row({ status: 'unpriced', flat: null, res: null }), row({ flat: null, res: 'win' })];
  const t = R.tally(rows, {});
  eq('w l p n', [t.w, t.l, t.p, t.n], [1, 1, 1, 3]);
  near('units is the sum of stored flat results', t.units, -0.5);
  near('roi is units over n', t.roi, -0.5 / 3);
  eq('unpriced is listed apart and not in n', t.unpriced, 1);
  ok('a graded row with no stored flat result is not invented', t.n === 3);
  const sd = Math.sqrt(((0.5 + 1 / 6) ** 2 + (-1 + 1 / 6) ** 2 + (1 / 6) ** 2) / 2);
  near('se is sample sd over sqrt(n)', t.se, sd / Math.sqrt(3), 1e-9);
  const e = R.tally([], {});
  eq('empty tally has no roi and no se', [e.n, e.roi, e.se, e.clv_mean], [0, null, null, null]);
  eq('one row has no se', R.tally([row()], {}).se, null);
}

console.log('CLV from close rows');
{
  const a = row({ key: 'K1' }), b = row({ key: 'K2' }), c = row({ key: 'K3' });
  const cm = R.closeMap([{ kind: 'close', of: 'K1', clv: 0.02 }, { kind: 'close', of: 'K2', clv: -0.01 }, { kind: 'close', of: 'X', clv: null }, { kind: 'result', of: 'K3', clv: 1 }]);
  eq('closeMap keys by the result key and skips a missing clv', Object.keys(cm), ['K1', 'K2']);
  const t = R.tally([a, b, c], cm);
  eq('clv_n counts only rows with a stored close', t.clv_n, 2);
  near('clv_mean is the mean of the stored clv', t.clv_mean, 0.005);
  eq('no close stored: null, not zero', R.tally([c], cm).clv_mean, null);
}

console.log('splitForward (forward vs in-sample)');
{
  const rows = [row({ cut: CUT }), row({ cut: CUT - 1 }), row({ cut: CUT + 86400 }), row({ cut: null }), row({ cut: CUT - 99999 })];
  const s = R.splitForward(rows);
  eq('cut at or after the registered time is forward', s.forward.length, 2);
  eq('cut before it is in-sample', s.in_sample.length, 2);
  eq('a row with no cut time is in neither', [s.undated.length, s.forward.length + s.in_sample.length + s.undated.length], [1, 5]);
  eq('the boundary second is forward', R.splitForward([row({ cut: CUT })]).forward.length, 1);
  eq('a custom cut', R.splitForward(rows, CUT + 50000).forward.length, 1);
  const f = R.tally(s.forward), i = R.tally(s.in_sample);
  eq('the two halves add up to the whole', [f.n + i.n, R.tally(rows.filter(r => r.cut)).n], [4, 4]);
}

console.log('monitor (small-sample and watch flags)');
{
  eq('improving and small: watch + small', R.monitor({ n: 46, units: 3.9, roi: 0.08 }), { watch: true, small: true, tiny: false, n: 46 });
  eq('improving and tiny', R.monitor({ n: 7, units: 1, roi: 0.1 }), { watch: true, small: true, tiny: true, n: 7 });
  eq('not improving: no watch, tiny still flagged', R.monitor({ n: 7, units: -2, roi: -0.3 }), { watch: false, small: true, tiny: true, n: 7 });
  eq('improving at 300 is no longer small', R.monitor({ n: 300, units: 5, roi: 0.02 }), { watch: true, small: false, tiny: false, n: 300 });
  eq('zero units is not improving', R.monitor({ n: 50, units: 0, roi: 0 }).watch, false);
  eq('empty', R.monitor({ n: 0, units: 0 }), { watch: false, small: false, tiny: false, n: 0 });
  eq('null', R.monitor(null).watch, false);
  eq('roi is used when units is absent', R.monitor({ n: 40, roi: 0.05 }).watch, true);
}

console.log('seNote (what the sample can say)');
{
  const rows = []; for (let i = 0; i < 119; i++) rows.push(row({ res: i % 2 ? 'win' : 'loss', flat: i % 2 ? 0.9 : -1 }));
  const t = R.tally(rows);
  const n = R.seNote(t);
  ok('names n and the size of one standard error', /^At n=119, one standard error on ROI is about \d+\.\d points/.test(n), n);
  ok('under 300 says no edge can be read', /Under 300 plays no edge can be read\.$/.test(n), n);
  eq('n of 1 or no se: nothing to say', [R.seNote({ n: 1, se: null }), R.seNote(null)], [null, null]);
  ok('no em dash, no proof language', !/proven|agree|elite/i.test(n) && !n.includes(String.fromCharCode(0x2014)));
  const big = R.seNote({ n: 400, se: 0.05 });
  ok('at 300 or more the under-300 line is dropped', !/Under 300/.test(big), big);
}

console.log('playLabel and latest');
{
  eq('moneyline', R.playLabel({ side: '76ers', group: 'ml' }), '76ers ML');
  eq('total', R.playLabel({ side: 'Over', group: 'total', line: 224.5 }), 'Over 224.5');
  eq('spread on the first outcome keeps the stored line', R.playLabel({ side: 'Mavericks', group: 'spread', line: -2.5, outs: ['Mavericks', 'Cavaliers'] }), 'Mavericks -2.5');
  eq('spread on the second outcome takes the negative', R.playLabel({ side: 'Bucks', group: 'spread', line: -8.5, outs: ['Hawks', 'Bucks'] }), 'Bucks +8.5');
  const l = R.latest([row({ graded_at: 5, key: 'a' }), row({ graded_at: 9, key: 'b' }), row({ graded_at: 7, key: 'c' }), row({ status: 'unpriced', graded_at: 99, key: 'd' })], 2);
  eq('latest graded first, unpriced skipped', l.map(r => r.key), ['b', 'c']);
}

console.log('tierRecord (never computed here)');
{
  const rows = [row({ tier: 'clear', flat: 0.5 }), row({ tier: 'Clear', res: 'loss', flat: -1 }), row({ evidence_tier: 'thin' }), row({ v2: { tier: 'contested' }, sport: 'nfl' }), row({ tier: 'bogus' })];
  const r = R.tierRecord(rows, null, 'all');
  eq('rows with a tier field are grouped by it', [r.source, r.byTier.clear.n, r.byTier.thin.n, r.byTier.contested.n, r.byTier.mixed.n], ['rows', 2, 1, 1, 0]);
  eq('a sport filter applies', R.tierRecord(rows, null, 'nfl').byTier.contested.n, 1);
  eq('no tier anywhere: null, so the page says not logged yet', R.tierRecord([row(), row()], {}, 'all'), null);
  eq('the exact honest line', R.TIER_NONE, 'Tier record: not logged yet. It starts at the next lock.');
  const file = { tier_record: { clear: { n: 10, w: 6, l: 4, flat_roi: 0.1, clv_n: 4, clv_mean: 0.01 }, contested: { n: 5, w: 1, l: 4, flat_roi: -0.5 } } };
  const f = R.tierRecord([row()], file, 'all');
  eq('a published tier_record object is read as is', [f.source, f.byTier.clear.n, f.byTier.clear.units, f.byTier.mixed, f.byTier.contested.w], ['file', 10, 1, null, 1]);
  const fs2 = R.tierRecord([], { tier_record: { sports: { nba: { clear: { n: 10, w: 6, l: 4, flat_roi: 0.1 } }, nfl: { clear: { n: 10, w: 5, l: 5, flat_roi: 0.3 } }, cfb: { clear: { n: 99, w: 1, l: 1, flat_roi: 9 } } } } }, 'all');
  eq('published per-sport lines add up over the shown sports, CFB left out', [fs2.byTier.clear.n, fs2.byTier.clear.units], [20, 4]);
  eq('rows win over a file object only when rows carry tiers', R.tierRecord([row({ tier: 'mixed' })], file, 'all').source, 'rows');
}

console.log('acctAgg (accounts by tier, forward apart from past)');
{
  const fwd = (w, l, n, flat, pnl, cn, cm) => ({ w, l, p: n - w - l, n, pnl, roi: 0, flat_roi: flat, clv_n: cn, clv_mean: cm });
  const file = {
    v2_fields: 'per wallet: flat_roi fwd first_seen',
    sports: {
      nba: {
        a: { w_: 100, l_: 50, rk: { tier: 'sharp' }, fwd: fwd(6, 4, 10, 0.1, 1000, 10, 0.01) },
        b: { w_: 10, l_: 20, rk: { tier: 'dull' }, fwd: fwd(1, 9, 10, -0.5, -500, 10, -0.02) },
        c: { w_: 30, l_: 30, rk: { tier: 'mid' }, fwd: null },
        d: { w_: 5, l_: 5, v2: { tier: 'few' } },
      },
      cbb: { e: { w_: 12, l_: 8, rk: { tier: 'sharp' }, fwd: fwd(3, 1, 4, 0.25, 50, 0, null) } },
    },
  };
  const a = R.acctAgg(file, 'all');
  eq('forward is published', a.fwdPub, true);
  eq('accounts per tier (college is always too few)', [a.tiers.beats.accounts, a.tiers.even.accounts, a.tiers.loses.accounts, a.tiers.few.accounts], [1, 1, 1, 2]);
  eq('forward w l n sum over the accounts with bets', [a.total.w, a.total.l, a.total.n, a.total.active], [10, 14, 24, 3]);
  near('units are flat roi times bets', a.total.units, 0.1 * 10 - 0.5 * 10 + 0.25 * 4);
  near('forward roi is units over bets', a.total.roi, (1 - 5 + 1) / 24);
  eq('dollar pnl is summed apart from units', a.total.pnl, 550);
  near('clv is weighted by clv_n', a.total.clv_mean, (0.1 - 0.2) / 20);
  eq('past record is w_ and l_ and is kept apart', [a.total.past.w, a.total.past.l, a.total.past.n], [157, 113, 270]);
  eq('an account with no forward bets is not active', [a.tiers.even.active, a.tiers.even.n], [0, 0]);
  eq('college tier line holds the college account only for forward', [a.tiers.few.n, a.tiers.few.w, a.tiers.few.active], [4, 3, 1]);
  const nba = R.acctAgg(file, 'nba');
  eq('a sport filter', [nba.total.accounts, nba.total.n, Object.keys(nba.bySport)], [4, 20, ['nba']]);
  eq('by sport keeps each sport apart', [a.bySport.nba.n, a.bySport.cbb.n], [20, 4]);
  const noFwd = R.acctAgg({ sports: file.sports }, 'all');
  eq('forward not declared in v2_fields: not published, not zero', [noFwd.fwdPub, noFwd.total.n], [false, 0]);
  ok('the past record still reads when forward is not published', noFwd.total.past.n === 270);
  const t = R.asTally(a.tiers.beats);
  eq('asTally feeds the same flags', R.monitor(t).watch, true);
  eq('empty file', R.acctAgg(null, 'all').total.accounts, 0);
  eq('a college sport row keeps tier few even with rk sharp', R.acctAgg(file, 'cbb').tiers.few.accounts, 1);
}

console.log('months (Central)');
{
  eq('this month alone while the month before has no files', R.months(NOW), ['2026-11']);
  eq('across a year end', R.months(1798790400 + 3600 * 12), ['2026-12', '2027-01']);
  eq('never before the first month of the record (Oct 2026 has no files)', R.months(1793000000), ['2026-10']);
}

console.log('tier table (tier_record.json)');
{
  const T = (w, l, p, units) => { const n = w + l + p; return { w, l, p, n, units, roi: n ? Math.round(units / n * 10000) / 10000 : null }; };
  const Z = T(0, 0, 0, 0);
  const tier = (all, ins, fwd, since, bm) => ({ all, in_sample: ins || all, forward: fwd || Z, since_nov16: since || Z, by_market: bm || { ml: all, spread: Z, total: Z } });
  const nba = { tiers: { clear: tier(T(1, 0, 0, 1.2)), mixed: tier(T(2, 1, 0, 0.5)), thin: tier(Z), contested: tier(T(30, 20, 0, 0.96), null, null, T(19, 16, 0, -1.55), { ml: T(27, 14, 0, 3.73), spread: T(2, 4, 0, -1.83), total: T(1, 2, 0, -0.94) }), none: tier(T(5, 5, 0, -0.5)) } };
  const nfl = { tiers: { clear: tier(Z), mixed: tier(T(1, 3, 0, -1)), thin: tier(T(0, 2, 0, -2)), contested: tier(T(19, 11, 0, 2), null, null, null, { ml: T(10, 5, 0, 1), spread: T(9, 6, 0, 1), total: Z }), none: tier(Z) } };
  const cbb = { tiers: { clear: tier(Z), mixed: tier(Z), thin: tier(Z), contested: tier(T(4, 1, 0, 1)), none: tier(T(24, 19, 0, 4.94)) } };
  const cfb = { tiers: { clear: tier(Z), mixed: tier(T(4, 9, 0, -3)), thin: tier(T(9, 5, 0, 2)), contested: tier(T(8, 13, 0, -4)), none: tier(Z) } };
  const file = { built: NOW, forward_note: 'forward starts at the first logged lock', logged_rows: 0, forward_graded: 0, sports: { nba, nfl, cbb, cfb } };
  const pooled = (t) => R.tierPool(['nba', 'nfl', 'cbb'].map((sp) => file.sports[sp].tiers[t].all));
  const withAll = Object.assign({}, file, { all: { tiers: Object.fromEntries(['clear', 'mixed', 'thin', 'contested', 'none'].map((t) => [t, Object.assign({}, tier(pooled(t)), {})])) } });

  /* bucket selection */
  eq('all bucket', R.pickBucket(nba.tiers.contested, 'all').n, 50);
  eq('since_nov16 bucket', R.pickBucket(nba.tiers.contested, 'since_nov16').w, 19);
  eq('forward bucket is zeros with a null roi', R.pickBucket(nba.tiers.contested, 'forward'), { w: 0, l: 0, p: 0, n: 0, units: 0, roi: null });
  eq('an unknown bucket reads as all', R.pickBucket(nba.tiers.contested, 'bogus').n, 50);
  eq('a missing tier is zeros, not a throw', R.pickBucket(undefined, 'all'), { w: 0, l: 0, p: 0, n: 0, units: 0, roi: null });
  near('roi is stored as a fraction', R.pickBucket(nba.tiers.contested, 'all').roi, 0.0192, 1e-6);
  ok('roi null stays null even when units is a number at n 0', R.tierTally({ w: 0, l: 0, p: 0, n: 0, units: 0, roi: 0.5 }).roi === null);

  /* sports and pooling */
  eq('NBA contested 30-20', R.fmtWl(R.tierTable(file, 'nba', 'all').rows[3].t), '30-20');
  eq('NFL contested 19-11', R.fmtWl(R.tierTable(file, 'nfl', 'all').rows[3].t), '19-11');
  eq('CBB contested 4-1', R.fmtWl(R.tierTable(file, 'cbb', 'all').rows[3].t), '4-1');
  eq('CFB has its own rows', ['mixed', 'thin', 'contested'].map((t) => R.fmtWl(R.tierTable(file, 'cfb', 'all').rows[R.TIER_ROWS.indexOf(t)].t)), ['4-9', '9-5', '8-13']);
  eq('all pools NBA + NFL + CBB (contested 53-32)', R.fmtWl(R.tierTable(file, 'all', 'all').rows[3].t), '53-32');
  eq('all, when the file has no pooled block, equals the file pooled block', R.tierTable(file, 'all', 'all').rows.map((r) => r.t), R.tierTable(withAll, 'all', 'all').rows.map((r) => r.t));
  eq('CFB is never pooled into all (mixed is NBA 3 + NFL 4, not the CFB 13)', R.tierTable(file, 'all', 'all').rows[1].t.n, 7);
  eq('a sport missing from the file: null', R.tierTable(file, 'nhl', 'all'), null);
  eq('a bad file: null', R.tierTable({}, 'all', 'all'), null);
  near('pooled units add up', R.tierTable(file, 'all', 'all').rows[3].t.units, 0.96 + 2 + 1, 1e-9);

  /* not derivable stays apart */
  const tb = R.tierTable(file, 'cbb', 'all');
  eq('five rows, Not derivable last', tb.rows.map((r) => r.tier), ['clear', 'mixed', 'thin', 'contested', 'none']);
  eq('CBB not derivable 24-19', R.fmtWl(tb.rows[4].t), '24-19');
  ok('the none row is flagged not derived', tb.rows[4].derived === false && tb.rows.slice(0, 4).every((r) => r.derived));
  eq('the tiers-only total leaves Not derivable out', [tb.derived.n, tb.total.n], [5, 48]);
  near('shares sum to 1 across the five rows', tb.rows.reduce((a, r) => a + r.share, 0), 1, 1e-9);
  eq('a tier with none of the plays has a zero share', tb.rows[0].share, 0);

  /* zero-play tiers and dashes */
  const nbaT = R.tierTable(file, 'nba', 'all');
  eq('Thin with no plays is still a row', nbaT.rows[2].t.n, 0);
  eq('zero-play cells: 0-0, 0u, dash', [R.fmtWl(nbaT.rows[2].t), R.fmtUnits(nbaT.rows[2].t), R.fmtRoi(nbaT.rows[2].t)], ['0-0', '0u', '-']);
  eq('real cells: signed units and signed percent', [R.fmtUnits(nbaT.rows[3].t), R.fmtRoi(nbaT.rows[3].t)], ['+0.96u', '+1.9%']);
  eq('a loss reads negative', [R.fmtUnits(nbaT.rows[4].t), R.fmtRoi(nbaT.rows[4].t)], ['-0.5u', '-5.0%']);
  eq('a push shows as the third number', R.fmtWl({ w: 3, l: 2, p: 1, n: 6 }), '3-2-1');
  const fw = R.tierTable(file, 'nba', 'forward');
  eq('forward is zeros in every row', fw.rows.every((r) => r.t.n === 0 && r.t.roi === null && r.share === null), true);
  eq('forward total is zero', fw.total.n, 0);
  eq('zero-play rows carry no monitor flag', fw.rows.some((r) => r.flag.watch || r.flag.tiny), false);

  /* improving slices */
  eq('Contested NBA improves (units above 0): watch, small, not tiny', [nbaT.rows[3].flag.watch, nbaT.rows[3].flag.small, nbaT.rows[3].flag.tiny, nbaT.rows[3].flag.n], [true, true, false, 50]);
  eq('NBA Clear n=1 improves: watch and tiny', [nbaT.rows[0].flag.watch, nbaT.rows[0].flag.tiny], [true, true]);
  eq('a losing slice is not watched', R.tierTable(file, 'nfl', 'all').rows[2].flag.watch, false);
  eq('a losing slice under 30 still says small sample', R.tierTable(file, 'nfl', 'all').rows[2].flag.tiny, true);
  eq('since Nov 16 contested is losing: not watched', R.tierTable(file, 'nba', 'since_nov16').rows[3].flag.watch, false);

  /* market split */
  eq('market split on the all bucket', nbaT.rows[3].markets.map((m) => [m.k, R.fmtWl(m.t)]), [['ml', '27-14'], ['spread', '2-4'], ['total', '1-2']]);
  eq('in-sample holds the same plays today, so the split shows', R.tierTable(file, 'nba', 'in_sample').rows[3].markets !== null, true);
  eq('since Nov 16 is a subset: no stored split, none shown', R.tierTable(file, 'nba', 'since_nov16').rows[3].markets, null);
  eq('forward has no split', fw.rows[3].markets, null);
  eq('a tier with no plays has no split', nbaT.rows[2].markets, null);

  /* the rail line */
  const rl = R.railLine(file, 'nba');
  eq('rail line names the bucket honestly', rl.label, 'Record so far (in-sample)');
  eq('rail line lists tiers with plays, Contested 30-20', rl.items.find((i) => i.tier === 'contested').wl, '30-20');
  eq('rail line drops zero-play tiers', rl.items.some((i) => i.tier === 'thin'), false);
  eq('rail line keeps Not derivable separate and named', rl.items[rl.items.length - 1], { tier: 'none', word: 'Not derivable', wl: '5-5', n: 10 });
  eq('rail line for all sums the three sports', R.railLine(file, 'all').items.find((i) => i.tier === 'contested').wl, '53-32');
  const logged = JSON.parse(JSON.stringify(file)); logged.sports.nba.tiers.contested.forward = { w: 1, l: 0, p: 0, n: 1, units: 0.9, roi: 0.9 };
  eq('once forward has graded plays the rail label says so', R.railLine(logged, 'nba').label, 'Record so far (in-sample and forward)');
  eq('rail line is null with no file', R.railLine(null, 'nba'), null);
  ok('the footer text is the audited sentence', R.TIER_FOOT === 'In-sample: the tier rule was written after these results. Forward counts start at the first logged lock.');
}

console.log('shadow size v2s-1 (tier_record.json shadow cells)');
{
  const S = (staked, units) => ({ units_staked: staked, units, roi: staked ? Math.round(units / staked * 10000) / 10000 : null });
  const T = (w, l, p, units, shadow) => { const n = w + l + p; return { w, l, p, n, units, roi: n ? Math.round(units / n * 10000) / 10000 : null, shadow }; };
  const Z = T(0, 0, 0, 0, S(0, 0));
  const ZN = Object.assign({}, Z, { shadow: null });
  const tier = (all, ins, fwd, since, bm) => ({ all, in_sample: ins || all, forward: fwd || Z, since_nov16: since || Z, by_market: bm || { ml: all, spread: Z, total: Z } });
  const nba = { tiers: {
    clear: tier(T(1, 0, 0, 1.2, S(1.5, 1.8))), mixed: tier(T(0, 1, 0, -1, S(1, -1))), thin: tier(Z),
    contested: tier(T(30, 20, 0, 0.96, S(25, 0.48)), null, null, T(19, 16, 0, -1.55, S(17.5, -0.77)),
      { ml: T(27, 14, 0, 3.73, S(20.5, 1.86)), spread: T(2, 4, 0, -1.83, S(3, -0.92)), total: T(1, 2, 0, -0.94, S(1.5, -0.47)) }),
    none: tier(T(4, 4, 0, -0.86, null), null, null, null, { ml: T(4, 4, 0, -0.86, null), spread: ZN, total: ZN }) } };
  const cfb = { tiers: { clear: tier(Z), mixed: tier(T(4, 9, 0, -3, S(0, 0))), thin: tier(T(9, 5, 0, 2, S(0, 0))), contested: tier(T(8, 13, 0, -4, S(0, 0))), none: tier(ZN) } };
  const nfl = { tiers: { clear: tier(Z), mixed: tier(T(1, 3, 0, -1, S(4, -1))), thin: tier(T(0, 2, 0, -2, S(1, -1))), contested: tier(T(19, 11, 0, 2, S(15, 1)), null, null, T(10, 6, 0, 4.28, S(8, 2.14))), none: tier(ZN) } };
  const file = { built: NOW, sports: { nba, nfl, cfb } };

  /* the size rule table */
  eq('sizes by tier', ['clear', 'mixed', 'thin', 'contested'].map((t) => R.shadowSize(t, 'nba')), [1.5, 1, 0.5, 0.5]);
  eq('Not derivable has no size', R.shadowSize('none', 'nba'), null);
  eq('CFB has size 0, shown as none', [R.shadowSize('clear', 'cfb'), R.fmtSize(R.shadowSize('clear', 'cfb'))], [0, 'none']);
  eq('size labels as displayed', [1.5, 1, 0.5, null, 0].map(R.fmtSize), ['1.5u', '1u', '0.5u', 'none', 'none']);
  eq('table rows carry the size', R.tierTable(file, 'nba', 'all').rows.map((r) => r.size), [1.5, 1, 0.5, 0.5, null]);
  eq('CFB rows carry size 0 for a tiered row and null for Not derivable', R.tierTable(file, 'cfb', 'all').rows.map((r) => r.size), [0, 0, 0, 0, null]);

  /* null shadow handling */
  eq('a cell with shadow null reads null (Not derivable)', R.shadowTally(nba.tiers.none.all), null);
  eq('a cell with no shadow field reads null', R.shadowTally({ w: 1, n: 1, units: 1 }), null);
  eq('a malformed shadow reads null', R.shadowTally({ shadow: { units_staked: 'x' } }), null);
  eq('zero staked: units 0, roi null', R.shadowTally(Z), { staked: 0, units: 0, roi: null });
  eq('zero staked renders as a dash, never 0%', [R.fmtShadowUnits(R.shadowTally(Z)), R.fmtShadowRoi(R.shadowTally(Z)), R.fmtStaked(R.shadowTally(Z))], ['-', '-', '-']);
  eq('a null shadow renders as dashes', [R.fmtShadowUnits(null), R.fmtShadowRoi(null)], ['-', '-']);
  eq('CFB shadow stakes nothing and shows dashes', R.tierTable(file, 'cfb', 'all').rows.map((r) => R.fmtShadowUnits(r.shadow)), ['-', '-', '-', '-', '-']);
  eq('Not derivable row has a null shadow', R.tierTable(file, 'nba', 'all').rows[4].shadow, null);

  /* rounding as displayed */
  const c = R.tierTable(file, 'nba', 'all').rows[3];
  eq('NBA contested shadow units as displayed', R.fmtShadowUnits(c.shadow), '+0.48u');
  eq('NBA contested shadow roi as displayed', R.fmtShadowRoi(c.shadow), '+1.9%');
  eq('NBA contested staked as displayed', R.fmtStaked(c.shadow), '25u');
  eq('flat beside it is unchanged', [R.fmtUnits(c.t), R.fmtRoi(c.t)], ['+0.96u', '+1.9%']);
  eq('a whole-unit loss has no trailing zeros', R.fmtShadowUnits(R.shadowTally(nba.tiers.mixed.all)), '-1u');
  eq('clear shadow units', R.fmtShadowUnits(R.shadowTally(nba.tiers.clear.all)), '+1.8u');
  eq('1.5u staked reads 1.5u', R.fmtStaked(R.shadowTally(nba.tiers.clear.all)), '1.5u');

  /* by-market rows */
  eq('market rows carry the shadow', c.markets.map((m) => R.fmtShadowUnits(m.shadow)), ['+1.86u', '-0.92u', '-0.47u']);
  eq('market staked adds up to the tier staked', R.shadowPool(c.markets.map((m) => m.shadow)).staked, 25);

  /* bucket switching */
  eq('in-sample reads the same plays today', R.fmtShadowUnits(R.tierTable(file, 'nba', 'in_sample').rows[3].shadow), '+0.48u');
  eq('since Nov 16 reads its own cell', R.fmtShadowUnits(R.tierTable(file, 'nba', 'since_nov16').rows[3].shadow), '-0.77u');
  eq('forward is zeros and dashes', R.tierTable(file, 'nba', 'forward').rows.map((r) => R.fmtShadowUnits(r.shadow)), ['-', '-', '-', '-', '-']);
  eq('an unknown bucket reads as all', R.fmtShadowUnits(R.tierTable(file, 'nba', 'bogus').rows[3].shadow), '+0.48u');
  eq('forward has no like-for-like line', R.tierTable(file, 'nba', 'forward').like, null);

  /* like-for-like: tier rows only, Not derivable out of both sides */
  const l = R.tierTable(file, 'nba', 'all').like;
  near('flat is the sum of the tier rows, Not derivable excluded', l.flat_units, 1.2 - 1 + 0.96, 1e-9);
  eq('n is the tier rows only', l.n, 1 + 1 + 50);
  near('shadow is the sum of the shadow cells', l.shadow_units, 1.8 - 1 + 0.48, 1e-9);
  near('staked is the sum of the sizes', l.staked, 1.5 + 1 + 25, 1e-9);
  near('shadow roi is units on staked', l.shadow_roi, 1.28 / 27.5, 1e-9);
  const withNone = JSON.parse(JSON.stringify(file)); withNone.sports.nba.tiers.none.all.units = 99;
  near('changing Not derivable changes neither side of the line', R.tierTable(withNone, 'nba', 'all').like.flat_units, 1.16, 1e-9);
  eq('the like line, exact text',
    R.likeLine(l, 'all'),
    'Shadow vs flat, plays with a tier only: flat +1.16u (n=52) vs shadow +1.28u on 27.5u staked. Not derivable plays are not staked by the shadow. In-sample, inside the noise.');
  ok('the like line never calls the shadow better or a signal', !/\b(better|edge|recommend|go|best)\b/i.test(R.likeLine(l, 'all')));
  eq('since Nov 16 line says informational', /Informational/.test(R.likeLine(R.tierTable(file, 'nba', 'since_nov16').like, 'since_nov16')), true);
  eq('CFB has no like-for-like (the shadow stakes nothing)', R.tierTable(file, 'cfb', 'all').like, null);
  eq('a null like gives no line', R.likeLine(null, 'all'), null);

  /* pooled all: no pooled block in the file, so the shadow cells are summed across NBA + NFL (CFB never pooled) */
  const all = R.tierTable(file, 'all', 'all');
  eq('pooled contested shadow units (NBA 0.48 + NFL 1)', R.fmtShadowUnits(all.rows[3].shadow), '+1.48u');
  eq('pooled contested staked (25 + 15)', R.fmtStaked(all.rows[3].shadow), '40u');
  eq('pooled Not derivable stays null', all.rows[4].shadow, null);
  eq('pooled mixed staked (NBA 1 + NFL 4)', R.shadowTally({ shadow: all.rows[1].shadow && { units_staked: all.rows[1].shadow.staked, units: all.rows[1].shadow.units } }).staked, 5);
  eq('pooled CFB is not in it (clear row is NBA only)', R.fmtStaked(all.rows[0].shadow), '1.5u');
  const withAll = Object.assign({}, file, { all: { tiers: nba.tiers } });
  eq('a stored pooled block is read as given', R.fmtStaked(R.tierTable(withAll, 'all', 'all').rows[3].shadow), '25u');
  eq('shadowPool of nothing is null, of nulls is null', [R.shadowPool([]), R.shadowPool([null, null])], [null, null]);
  eq('shadowPool skips nulls', R.shadowPool([null, { staked: 1, units: 0.5 }, { staked: 2, units: -1 }]).staked, 3);

  /* the copy */
  ok('tooltip text is the specified sentence', R.SHADOW_TIP === 'What the same plays would have returned at the tier-scaled size. In-sample, not shown on the page.');
  eq('the size table matches the rule v2s-1', R.SHADOW_SIZE, { clear: 1.5, mixed: 1, thin: 0.5, contested: 0.5, none: null });
}

console.log('table sorting (record tables)');
{
  const m = (idx, n, units, roi) => ({ idx, t: { n, units, roi } });
  const list = [m(0, 10, 1.5, 0.15), m(1, 0, 0, null), m(2, 30, -2, -0.07), m(3, 5, 1.5, 0.3)];
  eq('the default sort is the stored order, ascending', R.cleanSort(null), { k: 'def', dir: 1 });
  eq('a known column starts at its own first direction', [R.cleanSort({ k: 'units' }), R.cleanSort({ k: 'n' }), R.cleanSort({ k: 'roi', dir: 1 })], [{ k: 'units', dir: -1 }, { k: 'n', dir: -1 }, { k: 'roi', dir: 1 }]);
  eq('an unknown key or direction is cleaned', [R.cleanSort({ k: 'bogus', dir: 5 }), R.cleanSort({ k: 'constructor' })], [{ k: 'def', dir: 1 }, { k: 'def', dir: 1 }]);
  eq('a click on another column starts at its first direction', R.nextSort({ k: 'def', dir: 1 }, 'units'), { k: 'units', dir: -1 });
  eq('a click on the active column flips it', R.nextSort({ k: 'units', dir: -1 }, 'units'), { k: 'units', dir: 1 });
  eq('a click on the stored-order column after a sort goes back to ascending', R.nextSort({ k: 'roi', dir: -1 }, 'def'), { k: 'def', dir: 1 });
  eq('an unknown key changes nothing', R.nextSort({ k: 'roi', dir: 1 }, 'toString'), { k: 'roi', dir: 1 });
  eq('default order is the stored order', R.sortRows(list).map(x => x.idx), [0, 1, 2, 3]);
  eq('the stored-order column descending reverses it', R.sortRows(list, { k: 'def', dir: -1 }).map(x => x.idx), [3, 2, 1, 0]);
  eq('units descending: ties keep the stored order, no plays last', R.sortRows(list, { k: 'units', dir: -1 }).map(x => x.idx), [0, 3, 2, 1]);
  eq('units ascending: no plays still last', R.sortRows(list, { k: 'units', dir: 1 }).map(x => x.idx), [2, 0, 3, 1]);
  eq('roi: a null roi sorts last either way', [R.sortRows(list, { k: 'roi', dir: -1 }).map(x => x.idx), R.sortRows(list, { k: 'roi', dir: 1 }).map(x => x.idx)], [[3, 0, 2, 1], [2, 0, 3, 1]]);
  eq('n descending', R.sortRows(list, { k: 'n', dir: -1 }).map(x => x.idx), [2, 0, 3, 1]);
  eq('sorting does not change the input', list.map(x => x.idx), [0, 1, 2, 3]);
  eq('empty and missing input', [R.sortRows([]), R.sortRows(null)], [[], []]);
  eq('the live-region words', [R.sortWord({ k: 'units', dir: -1 }), R.sortWord(null)], ['Units, descending', 'default order, ascending']);
  eq('sortValue is null for no plays and for an unknown column', [R.sortValue(m(0, 0, 0, null), 'units'), R.sortValue(m(0, 5, 1, 0.2), 'zzz'), R.sortValue(null, 'n')], [null, null, null]);
}

console.log('table cells (record tables)');
{
  ok('the shared sort arrow marks the active direction', SV2.ui.sortArrow(true, 1).includes('is-asc') && SV2.ui.sortArrow(true, -1).includes('is-desc') && !/is-(asc|desc)/.test(SV2.ui.sortArrow(false, 1)));
  eq('a null roi is a dash, not 0%', R.fmtRoi({ n: 0, roi: null }), '-');
  eq('a roi with plays is signed', R.fmtRoi({ n: 3, roi: 0.123 }), '+12.3%');
  eq('zero plays reads 0-0 and 0u', [R.fmtWl({ n: 0 }), R.fmtUnits({ n: 0, units: 0 })], ['0-0', '0u']);
  eq('close column: mean and count apart', R.clvParts({ clv_n: 91, clv_mean: 0.1 }, 'play'), { value: SV2.fmt.centsSigned(0.1), sub: 'on 91 plays' });
  eq('close column: one bet is singular', R.clvParts({ clv_n: 1, clv_mean: -1 }, 'bet').sub, 'on 1 bet');
  eq('close column: none stored is null', [R.clvParts({ clv_n: 0, clv_mean: null }), R.clvParts(null)], [null, null]);
  eq('past cell: record, games and win rate', R.pastCell({ w: 3566, l: 3612, n: 7178 }), { wl: SV2.fmt.wl(3566, 3612), n: 7178, rate: 3566 / 7178 });
  eq('past cell: none stored is null', [R.pastCell({ w: 0, l: 0, n: 0 }), R.pastCell(null)], [null, null]);
  const win = R.latestModel(row({ res: 'win', flat: 0.46, side: 'Knicks', group: 'ml', sport: 'nba', gst: CUT, price: 0.685 }), { clv: 0 });
  eq('latest row: label, outcome and kind', [win.label, win.word, win.kind, win.market, win.sport], ['Knicks ML', 'Win', 'win', 'ml', 'nba']);
  eq('latest row: price, close, units and date as text', [win.price, win.close, win.units, win.date], [SV2.fmt.cents(0.685), SV2.fmt.centsSigned(0), '+0.46u', SV2.ct.md(CUT)]);
  const loss = R.latestModel(row({ res: 'loss', flat: -1, gst: undefined, price: undefined }), null);
  eq('latest row: a loss with no close, price or date', [loss.word, loss.kind, loss.close, loss.price, loss.date, loss.units], ['Loss', 'loss', '', '', '', '-1u']);
  eq('latest row: a push is neither', R.latestModel(row({ res: 'push', flat: 0 }), null).kind, 'push');
}

console.log('frozen list (Sharps rail box)');
{
  const GST = CUT + 5000;
  const open = (o) => { const r = Object.assign({ key: 'c' + (++k) + '|ml|all|sf', counts: true, sport: 'nba', ev: 'nba-aaa-bbb-2026-11-24', gst: GST, group: 'ml', play: 'sf', side: 'Hornets', line: null, outs: ['Grizzlies', 'Hornets'], units: 1, price: 0.425 }, o); if (r.key.indexOf('|') < 0) r.key += '|ml|all|sf'; return r; };   /* the real open rows carry no variant field; the variant is in the key */
  const settled = [
    row({ key: 'a', cut: CUT + 100, res: 'win', flat: 0.4, price: 0.7, side: 'Knicks' }),
    row({ key: 'b', cut: CUT + 300, res: 'loss', flat: -1, sport: 'cbb', side: 'Duke' }),
    row({ key: 'c', cut: CUT + 200, res: 'push', flat: 0, sport: 'nfl', side: 'Jets' }),
    row({ key: 'd', cut: CUT + 400, status: 'unpriced', res: null, flat: null, price: 0.5 }),
    row({ key: 'e', cut: CUT + 450, status: 'void', res: null, flat: null }),
    row({ key: 'x1', cut: CUT + 999, sport: 'cfb' }), row({ key: 'x2', cut: CUT + 999, counts: false }), row({ key: 'x3', cut: CUT + 999, play: 'lock' }), row({ key: 'x4', cut: CUT + 999, variant: 'fwd' }),
    { kind: 'close', of: 'a', clv: 0.01, key: 'a|close' },
  ];
  const file = { open: [open({ key: 'o1', gst: GST }), open({ key: 'o2', gst: GST + 1800, sport: 'cbb' }), open({ key: 'o1' }),
    open({ key: 'cf', sport: 'cfb' }), open({ key: 'nc', counts: false }), open({ key: 'lk', play: 'lock' }), open({ key: 'fw|ml|fwd|sf' }), open({ key: 'pp', gst: GST - 50, postponed: true }), null, { play: 'sf' }] };
  const L = R.frozenList(settled, file, {}, 'all');
  eq('awaiting first, newest freeze first; then settled newest first', L.items.map((x) => x.key), ['o2|ml|all|sf', 'o1|ml|all|sf', 'pp|ml|all|sf', 'e', 'd', 'b', 'c', 'a']);
  eq('counts: total, awaiting, settled', [L.total, L.awaiting, L.settled], [8, 3, 5]);
  eq('the settled plays are exactly the Record Plays rows (cfb, uncounted, lock and fwd excluded)', L.items.filter((x) => x.state !== 'open').map((x) => x.key).sort(), R.playRows(settled, 'all').map((x) => x.key).sort());
  eq('W-L-P is the Record tally of the same rows', [L.tally.w, L.tally.l, L.tally.p, L.tally.n], (() => { const t = R.tally(R.playRows(settled, 'all'), {}); return [t.w, t.l, t.p, t.n]; })());
  const TW = R.frozenList([row({ key: 'tw|ml|all|sf' })], { open: [open({ key: 'tw' }), open({ key: 'tw2' }), open({ key: 'tw2' })] }, {}, 'all');
  eq('an open row with a graded twin is not listed twice; a duplicate open key once', TW.items.map((x) => x.key + ':' + x.state), ['tw2|ml|all|sf:open', 'tw|ml|all|sf:win']);
  eq('an open row of another variant (key) is not a shown play', L.items.some((x) => x.key.indexOf('|fwd|') >= 0), false);
  eq('open: awaiting result, postponed says so', [L.items.find((x) => x.key === 'o1|ml|all|sf').word, L.items.find((x) => x.key === 'pp|ml|all|sf').word], ['Awaiting result', 'Postponed']);
  eq('freeze time: stored cut, else the card rule (game start minus 15 minutes)', [L.items.find((x) => x.key === 'a').cut, L.items.find((x) => x.key === 'o1|ml|all|sf').cut], [CUT + 100, GST - 900]);
  eq('freeze time: the tier log cut wins over the rule for an open play', R.frozenList([], { open: [open({ key: 'o9' })] }, { 'o9|ml|all|sf': { tier: 'clear', cut: GST - 840 } }, 'all').items[0].cut, GST - 840);
  const a = L.items.find((x) => x.key === 'a'), b = L.items.find((x) => x.key === 'b'), c = L.items.find((x) => x.key === 'c');
  eq('result words and units', [a.word + ' ' + a.units, b.word + ' ' + b.units, c.word + ' ' + c.units], ['W +0.4u', 'L -1u', 'P 0u']);
  eq('title is the Record label', [a.label, L.items.find((x) => x.key === 'o1|ml|all|sf').label], ['Knicks ML', 'Hornets ML']);
  eq('price: stored price as cents, none when missing or unpriced', [a.price, L.items.find((x) => x.key === 'd').price, R.frozenList([row({ key: 'np', price: null })], null, {}, 'all').items[0].price], [SV2.fmt.cents(0.7), null, null]);
  eq('unpriced and void carry no units', [L.items.find((x) => x.key === 'd').units, L.items.find((x) => x.key === 'e').units, L.items.find((x) => x.key === 'e').word], [null, null, 'Void']);
  /* tier at freeze: only from the stored log */
  const T = R.frozenList(settled, file, R.tierLogMap([{ key: 'a', tier: 'clear' }, { key: 'o1|ml|all|sf', tier: 'Contested' }, { key: 'b', tier: 'none' }, { key: 'c', tier: 'bogus' }, { tier: 'clear' }]), 'all');
  eq('tier shown when stored (case-insensitive); none, unknown and missing show nothing', [T.items.find((x) => x.key === 'a').tier, T.items.find((x) => x.key === 'o1|ml|all|sf').tier, T.items.find((x) => x.key === 'b').tier, T.items.find((x) => x.key === 'c').tier, T.items.find((x) => x.key === 'e').tier], ['clear', 'contested', null, null, null]);
  eq('tierLogMap tolerates junk', [R.tierLogMap(null), R.tierLogMap([null, 5, {}])], [{}, {}]);
  /* sport filter */
  eq('one sport', R.frozenList(settled, file, {}, 'cbb').items.map((x) => x.key), ['o2|ml|all|sf', 'b']);
  eq('sport filter is case-insensitive', R.frozenList(settled, file, {}, 'NBA').items.every((x) => x.sport === 'nba'), true);
  const C = R.frozenList(settled, file, {}, 'cfb');
  eq('CFB shows no size: nothing listed, flagged', [C.items.length, C.noSize, C.total], [0, true, 0]);
  /* empty and bad input */
  eq('empty inputs', [R.frozenList([], null, null, 'all').total, R.frozenList(null, { open: 'x' }, undefined, undefined).total, R.frozenList(undefined, undefined, undefined, 'nba').items], [0, 0, []]);
  eq('subtitle is empty for an empty list', R.frozenSub(R.frozenList([], null, {}, 'all')), '');
  eq('subtitle: total, record, flat 1u, awaiting', R.frozenSub(L), '8 frozen plays, ' + R.fmtWl(L.tally) + ', flat 1u, 3 awaiting result, 2 not graded');
  eq('subtitle with nothing settled omits the record', R.frozenSub(R.frozenList([], { open: [open({ key: 'z' })] }, {}, 'all')), '1 frozen play: 1 awaiting result');
  /* parity with the Record page across a bigger set */
  const big = []; for (let i = 0; i < 40; i++) big.push(row({ key: 'big' + i, cut: CUT + i, res: i % 3 ? 'win' : 'loss', flat: i % 3 ? 0.5 : -1, sport: ['nba', 'nfl', 'cbb'][i % 3] }));
  const LB = R.frozenList(big, { open: [] }, {}, 'all'), RT = R.tally(R.playRows(big, 'all'), {});
  eq('list total equals the Record n when nothing is open or unpriced', [LB.total, LB.tally.n, LB.tally.units], [RT.n, RT.n, RT.units]);
  eq('the box holds 12 first (FROZEN_SHOW), newest first', [R.FROZEN_SHOW, LB.items[0].key, LB.items[39].key], [12, 'big39', 'big0']);
}

console.log('frozen list: live.json locked entries');
{
  const KEY = 'cbb/frozen/2026-11-24/cbb-pitt-okl-2026-11-24@1795545000.json|ml|all|sf';
  const LOCKED = { key: KEY, sport: 'cbb', ev: 'cbb-pitt-okl-2026-11-24', gst: 1795545000, group: 'ml', play: 'sf', side: 'Oklahoma Sooners', line: null, outs: ['Pittsburgh Panthers', 'Oklahoma Sooners'], units: 2.0 };
  const lk = (o) => Object.assign({}, LOCKED, o);
  const L = R.frozenList([], { open: [] }, {}, 'all', { locked: [LOCKED] });
  const it = L.items[0];
  eq('the exact live entry becomes one awaiting play', [L.total, L.awaiting, it.key, it.state, it.word], [1, 1, KEY, 'open', 'Awaiting result']);
  eq('title, sport, freeze time (game start minus 15 minutes), no price when none is stored', [it.label, it.sport, it.cut, it.price, it.tier], ['Oklahoma Sooners ML', 'cbb', 1795545000 - 900, null, null]);
  eq('freeze time reads 12:15 PM Central', SV2.ct.time(it.cut), '12:15 PM');
  eq('units of the live entry (the old ladder) are never shown', [it.units, it.flat], [null, null]);
  /* price and cut from the card file */
  const cardOk = R.cardFacts({ cut: 1795544100, markets: { ml: { sf: { all: { price: 0.465, price_t: 1795543806 } } } } }, KEY);
  eq('cardFacts: stored price and cut', cardOk, { price: 0.465, cut: 1795544100 });
  eq('cardFacts: a price older than 30 minutes before the cut is not shown', R.cardFacts({ cut: 1795544100, markets: { ml: { sf: { all: { price: 0.465, price_t: 1795544100 - 1801 } } } } }, KEY).price, null);
  eq('cardFacts: missing market, price or card', [R.cardFacts({ cut: 5, markets: {} }, KEY), R.cardFacts(null, KEY), R.cardFacts({ markets: { ml: { sf: { all: { price: 'x' } } } } }, KEY)], [{ price: null, cut: 5 }, { price: null, cut: null }, { price: null, cut: null }]);
  const L2 = R.frozenList([], null, {}, 'all', { locked: [LOCKED], cards: { [KEY]: { price: 0.465, cut: 1795544100 } } });
  eq('the card price and cut are used when read', [L2.items[0].price, L2.items[0].cut], [SV2.fmt.cents(0.465), 1795544100]);
  /* regex, fields, sport */
  const bad = [lk({ key: 'cbb/frozen/2026-11-24/a.json|ml|fwd|sf' }), lk({ key: 'cbb/frozen/2026-11-24/a.json|ml|all|lock' }), lk({ key: 'cbb/frozen/2026-11-24/a.json|ml|all|sf', play: 'lock' }),
    lk({ key: 'cbb/frozen/2026-11-24/b.json|ml|all|sf', sport: 'cfb' }), null, 5, { side: 'x' }, lk({ key: 7 })];
  eq('only shown plays (key |all|sf, play sf, NBA/NFL/CBB) are taken, junk ignored', R.frozenList([], null, {}, 'all', { locked: bad }).total, 0);
  eq('a missing side is not listed (no title), a missing line or outs still is', [R.frozenList([], null, {}, 'all', { locked: [lk({ side: undefined })] }).total, R.frozenList([], null, {}, 'all', { locked: [lk({ line: undefined, outs: undefined })] }).total], [0, 1]);
  eq('not an array is ignored', [R.frozenList([], null, {}, 'all', { locked: 'x' }).total, R.frozenList([], null, {}, 'all', { locked: null }).total], [0, 0]);
  /* dedupe against graded rows and the record's open list */
  const graded = [{ kind: 'result', play: 'sf', variant: 'all', counts: true, status: 'graded', sport: 'cbb', group: 'ml', res: 'win', flat: 0.5, cut: 10, key: KEY, side: 'Oklahoma Sooners' }];
  eq('a graded twin wins: not listed twice', R.frozenList(graded, null, {}, 'all', { locked: [LOCKED] }).items.map((x) => x.state), ['win']);
  const openRow = { key: KEY, counts: true, sport: 'cbb', gst: 1795545000, group: 'ml', play: 'sf', side: 'Oklahoma Sooners', outs: [], price: 0.47 };
  const LD = R.frozenList([], { open: [openRow] }, {}, 'all', { locked: [LOCKED, LOCKED] });
  eq('the record open row wins, the live twin and a duplicate are dropped', [LD.total, LD.items[0].price], [1, SV2.fmt.cents(0.47)]);
  /* ordering and filter */
  const A = lk({ key: 'nba/frozen/2026-11-24/n.json|spread|all|sf', sport: 'nba', gst: 1795550000, group: 'spread', side: 'Hornets', line: -2.5, outs: ['Grizzlies', 'Hornets'] });
  const sets = [row({ key: 's1', cut: 1795549999, sport: 'nba' })];
  const M = R.frozenList(sets, { open: [] }, {}, 'all', { locked: [LOCKED, A] });
  eq('awaiting first, newest freeze first, then settled even when the settled play is newer', M.items.map((x) => x.key), [A.key, KEY, 's1']);
  eq('spread title uses the stored line the Record way', M.items[0].label, 'Hornets +2.5');
  eq('sport filter applies to live entries', [R.frozenList([], null, {}, 'nba', { locked: [LOCKED, A] }).items.map((x) => x.sport), R.frozenList([], null, {}, 'cbb', { locked: [LOCKED, A] }).items.map((x) => x.sport), R.frozenList([], null, {}, 'cfb', { locked: [LOCKED] }).noSize], [['nba'], ['cbb'], true]);
  eq('the settled W-L-P is untouched by live entries', JSON.stringify(R.frozenList(sets, { open: [] }, {}, 'all', { locked: [LOCKED, A] }).tally), JSON.stringify(R.frozenList(sets, { open: [] }, {}, 'all').tally));
  eq('subtitle keeps the record and states the awaiting count apart', R.frozenSub(M), '3 frozen plays, 1-0, flat 1u, 2 awaiting result');
  eq('tier at freeze joins a live entry by key', R.frozenList([], null, R.tierLogMap([{ key: KEY, tier: 'mixed' }]), 'all', { locked: [LOCKED] }).items[0].tier, 'mixed');
  /* which cards to read */
  const many = []; for (let i = 0; i < 20; i++) many.push(lk({ key: 'cbb/frozen/2026-11-24/g' + i + '.json|ml|all|sf', gst: 1795545000 + i }));
  const miss = R.lockedMissing(graded, { open: [{ key: many[19].key }] }, [LOCKED].concat(many), 12);
  eq('lockedMissing: newest first, capped at 12, skips the record twin, the graded twin and the open row', [miss.length, miss[0], miss.includes(KEY), miss.includes(many[19].key)], [12, many[18].key, false, false]);
  eq('lockedMissing: nothing to read when there is no locked list', [R.lockedMissing([], null, null, 12), R.lockedMissing([], null, [{ key: 'bad|ml|all|sf', sport: 'nba' }], 12)], [[], []]);
  eq('cardPath only accepts the builder path shape', [R.cardPath(KEY), R.cardPath('../../x.json|ml|all|sf'), R.cardPath('https://evil/x.json|a'), R.cardPath(null)], ['cbb/frozen/2026-11-24/cbb-pitt-okl-2026-11-24@1795545000.json', null, null, null]);
}

console.log('copy rules');
{
  /* the flat ROI shown beside the shadow ROI: same plays, same ROI. Numbers are the live tier_record.json of 2026-11-24 (Clear 1-0 +1.2u stored, shadow 1.5u staked +1.8u roi 1.1978) */
  {
    const sh = (st, u, r) => ({ units_staked: st, units: u, roi: r });
    const cell = (w, l, n, u, r, s) => ({ w, l, p: 0, n, units: u, roi: r, shadow: s });
    const mk = (tiers) => ({ built: NOW, sports: { cbb: { tiers } } });
    const clear = cell(1, 0, 1, 1.2, 1.2, sh(1.5, 1.8, 1.1978));
    const f = mk({ clear: { all: clear, in_sample: clear, forward: cell(0, 0, 0, 0, null, sh(0, 0, null)), since_nov16: clear, by_market: { ml: clear } },
      mixed: { all: cell(0, 4, 4, -4, -1, sh(4, -4, -1)) }, thin: { all: cell(3, 5, 8, -1.58, -0.1975, sh(4, -0.79, -0.1978)) },
      contested: { all: cell(5, 1, 6, 2.73, 0.455, sh(3, 1.37, 0.4567)) }, none: { all: cell(24, 19, 43, 4.94, 0.1149, null) } });
    const rows = R.tierTable(f, 'cbb', 'all').rows;
    near('Clear flat ROI shows the unrounded 1.1978, not units/n of the rounded 1.2', rows[0].t.roi, 1.1978, 1e-9);
    eq('Clear flat and shadow ROI print the same', [R.fmtRoi(rows[0].t), R.fmtShadowRoi(rows[0].shadow)], ['+119.8%', '+119.8%']);
    eq('the stored units are not touched (+1.2u)', [rows[0].t.units, R.fmtUnits(rows[0].t)], [1.2, '+1.2u']);
    near('the Clear market split takes the same unrounded ROI', rows[0].markets[0].t.roi, 1.1978, 1e-9);
    near('Mixed (shadow roi equals stored) is unchanged', rows[1].t.roi, -1, 1e-9);
    eq('Thin: flat and shadow print the same', [R.fmtRoi(rows[2].t), R.fmtShadowRoi(rows[2].shadow)], [R.fmtShadowRoi(rows[2].shadow), '-19.8%']);
    eq('Not derivable has no shadow: stored roi kept', rows[4].t.roi, 0.1149);
    /* a cell that is not fully sized (CFB stakes nothing, or staked differs from size x n) keeps the stored flat roi */
    const partial = R.exactRoi({ n: 4, units: 1, roi: 0.25 }, { staked: 1, units: 0.1, roi: 0.1 }, 1);
    eq('staked not equal to size x n: stored roi kept', partial.roi, 0.25);
    eq('no size: stored roi kept', R.exactRoi({ n: 1, units: 1, roi: 1 }, { staked: 0, units: 0, roi: null }, 0).roi, 1);
    eq('null shadow: tally returned as is', R.exactRoi({ n: 1, units: 1, roi: 1 }, null, 1).roi, 1);
    near('the pooled hero ROI is still units / n', R.tierTable(f, 'cbb', 'all').total.roi, (1.2 - 4 - 1.58 + 2.73 + 4.94) / (1 + 4 + 8 + 6 + 43), 1e-9);
  }
  const src = fs.readFileSync(path.join(ROOT, 'sv2-record.js'), 'utf8');
  ok('no em dash', !src.includes(String.fromCharCode(0x2014)));
  ok('no em dash in the stylesheet', !fs.readFileSync(path.join(ROOT, 'sv2.css'), 'utf8').includes(String.fromCharCode(0x2014)));
  ok('no agree, proven or elite in the page text', !/'[^']*\b(agree|agreement|proven|elite)\b[^']*'/i.test(src.replace(/\/\*[\s\S]*?\*\//g, '')));
}

console.log('\n' + pass + ' pass, ' + fail + ' fail');
process.exit(fail ? 1 : 0);
