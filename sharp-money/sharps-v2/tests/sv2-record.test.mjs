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

console.log('copy rules');
{
  const src = fs.readFileSync(path.join(ROOT, 'sv2-record.js'), 'utf8');
  ok('no em dash', !src.includes(String.fromCharCode(0x2014)));
  ok('no agree, proven or elite in the page text', !/'[^']*\b(agree|agreement|proven|elite)\b[^']*'/i.test(src.replace(/\/\*[\s\S]*?\*\//g, '')));
}

console.log('\n' + pass + ' pass, ' + fail + ' fail');
process.exit(fail ? 1 : 0);
