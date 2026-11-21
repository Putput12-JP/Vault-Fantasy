/* Unit tests for the pure parts of sv2-core.js. No dependencies: node sharp-money/sharps-v2/tests/sv2-core.test.mjs
   The file is loaded through node:vm with a fake location and localStorage. Tests that need real data read _dev/
   (never committed) and are reported as skipped when it is absent. */
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const DEV = path.join(ROOT, '_dev');

function load(opts = {}) {
  const store = opts.store || {};
  const sandbox = {
    console, Intl, Date, Math, JSON, Object, Array, String, Number, RegExp, Promise, setTimeout, clearTimeout, setInterval, clearInterval,
    module: { exports: {} },
    location: { hostname: opts.host || 'localhost', search: opts.search || '', hash: '' },
    localStorage: opts.throwing
      ? { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } }
      : { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'sv2-core.js'), 'utf8'), sandbox);
  return { SV2: sandbox.module.exports, sandbox, store };
}

let pass = 0, fail = 0, skipped = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); }
}
function eq(name, a, b) { ok(name, JSON.stringify(a) === JSON.stringify(b), { got: a, want: b }); }
function skip(name) { skipped++; console.log('  skip ' + name + ' (no _dev fixtures)'); }
function readDev(f) { const p = path.join(DEV, f); return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null; }

const { SV2 } = load();
const { rules, fmt, ct } = SV2;

console.log('formatters');
eq('american 0.55', fmt.american(0.55), '-122');
eq('american 0.4', fmt.american(0.4), '+150');
eq('american bounds', [fmt.american(0), fmt.american(1), fmt.american(null)], [null, null, null]);
eq('cents 0.415', fmt.cents(0.415), '41.5c');
eq('cents 0.55', fmt.cents(0.55), '55c');
eq('centsSigned', [fmt.centsSigned(0.01), fmt.centsSigned(-0.0164), fmt.centsSigned(0)], ['+1.0c', '-1.6c', '0.0c']);
eq('usd 17117', fmt.usd(17117), '$17.1K');
eq('usd small and big', [fmt.usd(442), fmt.usd(1600), fmt.usd(12040), fmt.usd(358487), fmt.usd(1234567), fmt.usd(999.6)], ['$442', '$1.6K', '$12K', '$358K', '$1.2M', '$1K']);
eq('usd full and negative', [fmt.usd(2000, { full: true }), fmt.usd(-442)], ['$2,000', '-$442']);
eq('pct', [fmt.pct(0.147), fmt.pct(0.031, { signed: true }), fmt.pct(-0.026), fmt.pct(0.5, { d: 0 })], ['14.7%', '+3.1%', '-2.6%', '50%']);
eq('units', [fmt.units(1), fmt.units(0.42, { signed: true }), fmt.units(-1.5, { signed: true })], ['1u', '+0.42u', '-1.5u']);
eq('wl', [fmt.wl(12, 9), fmt.wl(12, 9, 1), fmt.wl(null, 1)], ['12-9', '12-9-1', null]);
eq('line, mult, n', [fmt.line(144.5), fmt.line(3.5, { signed: true }), fmt.mult(2.14), fmt.n(1482)], ['144.5', '+3.5', '2.1x', '1,482']);
eq('addr and tail', [fmt.addr('0x0235dc24b38772bf3339a9e5ec5db3d3a05fcee5'), fmt.tail('0x0235dc24b38772bf3339a9e5ec5db3d3a05fcee5')], ['0x0235...cee5', '...5fcee5']);
eq('null in, null out (no placeholder number)', [fmt.usd(null), fmt.cents(undefined), fmt.pct(NaN), fmt.units(null), fmt.line(null), fmt.pctInt(null)], [null, null, null, null, null, null]);

console.log('Central time');
const NOW = 1795278675; // Sat Nov 21 2026 10:31 AM CST
eq('time', ct.time(1795278075), '10:21 AM');
eq('time with CT', ct.time(1795278075, true), '10:21 AM CT');
eq('dateKey', ct.dateKey(NOW), '2026-11-21');
eq('day today/tomorrow/later', [ct.day(NOW + 3600, NOW), ct.day(NOW + 86400, NOW), ct.day(NOW + 2 * 86400, NOW)], ['Today', 'Tomorrow', 'Mon Nov 23']);
eq('ago', [ct.ago(NOW - 30, NOW), ct.ago(NOW - 600, NOW), ct.ago(NOW - 16 * 3600, NOW), ct.ago(NOW - 3 * 86400, NOW)], ['just now', '10 min ago', '16 h ago', '3 d ago']);
eq('countdown', [ct.countdown(0), ct.countdown(30), ct.countdown(24 * 60), ct.countdown(3900), ct.countdown(2 * 86400 + 3 * 3600)], ['now', '<1m', '24m', '1h 05m', '2d 3h']);
eq('addDays across month and year', [ct.addDays('2026-11-30', 1), ct.addDays('2026-12-31', 1)], ['2026-12-01', '2027-01-01']);

console.log('bandOf');
const midnight = Date.UTC(2026, 10, 22, 6) / 1000; // Nov 22 00:00 CST
eq('exactly 60 min is the hour band', rules.bandOf(NOW + 3600, NOW), 'hour');
eq('60 min and 1 s is later today', rules.bandOf(NOW + 3601, NOW), 'today');
eq('last second before Central midnight', rules.bandOf(midnight - 1, NOW), 'today');
eq('Central midnight is tomorrow', rules.bandOf(midnight, NOW), 'tomorrow');
eq('two days out is later', rules.bandOf(midnight + 86400, NOW), 'later');
{
  const fall = Date.UTC(2026, 10, 1, 3) / 1000;             // Oct 31 2026 10:00 PM CDT
  eq('DST end (Nov 1 2026): noon Nov 1 CST is tomorrow', rules.bandOf(Date.UTC(2026, 10, 1, 18) / 1000, fall), 'tomorrow');
  eq('DST end: 00:30 Nov 2 CST is later', rules.bandOf(Date.UTC(2026, 10, 2, 6, 30) / 1000, fall), 'later');
  const spring = Date.UTC(2027, 2, 14, 2) / 1000;           // Mar 13 2027 8:00 PM CST
  eq('DST start (Mar 14 2027): 1:00 PM CDT is tomorrow', rules.bandOf(Date.UTC(2027, 2, 14, 18) / 1000, spring), 'tomorrow');
  eq('DST start: Central date of Mar 14 midnight', [ct.dateKey(Date.UTC(2027, 2, 14, 5, 59) / 1000), ct.dateKey(Date.UTC(2027, 2, 14, 6) / 1000)], ['2027-03-13', '2027-03-14']);
}

console.log('tierOf truth table (inline objects)');
function side(o = {}) {
  return { all: { counts: { hc: 0, sharp: 0, ...(o.counts || {}) }, rk: o.rk === null ? null : { sharp_n: 0, dull_n: 0, ...(o.rk || {}) }, proven: { wallets: 1, ...(o.proven || {}) }, list: o.list || [] } };
}
function game(sport, o = {}) {
  const S = o.S || 'A', O = o.O || 'B';
  return {
    ev: 'x-1', sport, cut: NOW + 7200,
    markets: {
      ml: {
        sides: { [S]: side(o.mine), [O]: side(o.theirs) },
        tp: { tB: o.tB === undefined ? null : o.tB },
        sf: { all: { side: S, units: o.units === undefined ? 2 : o.units, shown_units: o.shown, signals: { ev: { pts: o.pts === undefined ? null : o.pts } } }, fwd: { side: o.fwd === undefined ? null : o.fwd } },
        ...(o.v2 ? { v2: o.v2 } : {}),
      },
    },
  };
}
const T = (g) => rules.tierOf(g, 'ml');
eq('A1 alone: past winner on the other side', T(game('nba', { theirs: { counts: { hc: 1 } } })), 'contested');
eq('A1 counts class sharp too', T(game('cbb', { theirs: { counts: { sharp: 1 } } })), 'contested');
eq('A2 alone: beat-the-close wallet on the other side (nba)', T(game('nba', { theirs: { rk: { sharp_n: 1 } } })), 'contested');
eq('A3 alone: fade rule fires on the other side', T(game('nfl', { tB: { side: 'B' } })), 'contested');
eq('A3 does not fire when tB names this side', T(game('nfl', { tB: { side: 'A' } })) !== 'contested', true);
eq('A4 alone: price 0.3 pts worse than fair', T(game('nfl', { pts: -0.3 })), 'contested');
eq('A4 boundary: -0.29 is not against', T(game('nfl', { pts: -0.29 })) !== 'contested', true);
eq('B1 + B3 and no A: clear', T(game('nba', { mine: { rk: { sharp_n: 1 } }, fwd: 'A' })), 'clear');
eq('B2 + B3 and no A: clear', T(game('nfl', { pts: 0.3, fwd: 'A' })), 'clear');
eq('B1 without B3: mixed', T(game('nba', { mine: { rk: { sharp_n: 1 } } })), 'mixed');
eq('one wallet, no B1, no fair: thin', T(game('nba', {})), 'thin');
eq('one wallet but a price fact (pts 0.1): mixed', T(game('nba', { pts: 0.1 })), 'mixed');
eq('two wallets, no price evidence: mixed', T(game('nba', { mine: { proven: { wallets: 2 } } })), 'mixed');
eq('college ignores rk: A2 never fires', T(game('cbb', { theirs: { rk: { sharp_n: 3 } } })), 'thin');
eq('college ignores rk: B1 never fires', T(game('cbb', { mine: { rk: { sharp_n: 2 } }, fwd: 'A' })), 'thin');
eq('stored v2.tier wins over the client rule', T(game('nba', { theirs: { counts: { hc: 1 } }, v2: { tier: 'Mixed' } })), 'mixed');
eq('no shown size is none (cfb)', T(game('cfb', {})), 'none');
eq('units 0 is none', T(game('nba', { units: 0 })), 'none');

console.log('shownUnits');
eq('flat 1u on nba, nfl, cbb', ['nba', 'nfl', 'cbb'].map((s) => rules.shownUnits(game(s), 'ml')), [1, 1, 1]);
eq('the old ladder (units 2) is never the size', rules.shownUnits(game('nba', { units: 3 }), 'ml'), 1);
eq('nothing on cfb', rules.shownUnits(game('cfb', { units: 2.5 }), 'ml'), 0);
eq('shown_units wins when present', rules.shownUnits(game('nba', { shown: 1 }), 'ml'), 1);
eq('shown_units 0 hides the size', rules.shownUnits(game('nba', { shown: 0 }), 'ml'), 0);
eq('no play side, no size', rules.shownUnits({ sport: 'nba', markets: { ml: { sf: { all: { side: null, units: 2 } } } } }, 'ml'), 0);

console.log('facts');
{
  const f = rules.factsOf(game('nba', { theirs: { counts: { hc: 2, sharp: 1 }, rk: { sharp_n: 2 } }, pts: -1.1, tB: { side: 'B' } }), 'ml');
  eq('against list and counts', [f.against, f.a1.n, f.a2.n, f.a4.pts], [['a1', 'a2', 'a3', 'a4'], 3, 2, -1.1]);
  eq('no play returns null', rules.factsOf(game('nba', { units: 0 }), 'spread'), null);
}

console.log('v2TierOf and nameOf');
eq('mapping', [{ tier: 'sharp' }, { tier: 'mid' }, { tier: 'dull' }, { tier: 'thin' }, null].map((rk) => rules.v2TierOf({ rk }, 'nba')), ['beats', 'even', 'loses', 'few', 'few']);
eq('stored v2.tier wins', rules.v2TierOf({ v2: { tier: 'loses' }, rk: { tier: 'sharp' } }, 'nba'), 'loses');
eq('college is always few', rules.v2TierOf({ rk: { tier: 'sharp' } }, 'cbb'), 'few');
eq('name_disp wins', rules.nameOf({ name_disp: 'Shown', name: 'raw' }, '0xabc'), 'Shown');
eq('plain name', rules.nameOf({ name: 'darkumbreon88' }, '0x0235dc24b38772bf3339a9e5ec5db3d3a05fcee5'), 'darkumbreon88');
eq('null name', rules.nameOf({ name: null }, '0x0235dc24b38772bf3339a9e5ec5db3d3a05fcee5'), 'Unnamed 0x0235...cee5');
eq('hex-like name', rules.nameOf({ name: '0x0235dc24b38772bf3339a9e5ec5db3d3a05fcee5' }, '0x0235dc24b38772bf3339a9e5ec5db3d3a05fcee5'), 'Unnamed 0x0235...cee5');

console.log('sideTotals and groupSides');
eq('sum of rungs, stored multiple', rules.sideTotals([{ usd: 100, side_usd: 300, side_rungs: 2, side_press: 1.5 }, { usd: 200, side_usd: 300, side_rungs: 2, side_press: 1.5 }]), { usd: 300, stored_usd: 300, rungs: 2, press: 1.5 });
eq('no stored fields: client sum, no invented multiple', rules.sideTotals([{ usd: 100 }, { usd: 50 }]), { usd: 150, stored_usd: null, rungs: 2, press: null });
{
  const g = rules.groupSides([{ ev: 'e', gst: 1, g: 'ml', side: 'A', usd: 5 }, { ev: 'e', gst: 1, g: 'ml', side: 'B', usd: 7 }, { ev: 'e', gst: 1, g: 'ml', side: 'A', usd: 6 }]);
  eq('groups by side in first-seen order', g.map((s) => [s.side, s.usd, s.rungs]), [['A', 11, 2], ['B', 7, 1]]);
}

console.log('sinceFollowed');
{
  const items = [[2000, 1500, 1, 0.9, 'g1', 500], [1900, 1700, 0, -1, 'g2', 300], [1800, 900, 1, 0.5, 'g3', 200], [1700, 1500, 2, 0, 'g4', 100], [1600, 1500, 1, null, 'g5', 100], [500, 400, 1, 1, 'g6', 50]];
  const r = rules.sinceFollowed(items, 1000, 800);
  eq('drops items placed before the follow, counts pushes apart, skips null flats', [r.w, r.l, r.p, r.n, r.units, r.skipped, r.windowNote], [2, 1, 1, 3, -0.1, 1, false]);
  eq('window note when the follow predates the list', rules.sinceFollowed(items, 700, 800).windowNote, true);
  eq('no list is null', rules.sinceFollowed(null, 1000, 800), null);
  eq('bets and games differ when a game has two positions: the game takes its biggest stake', rules.sinceFollowed([[2000, 1500, 1, 0.5, 'g', 100], [2000, 1500, 0, -1, 'g', 400], [2100, 1500, 1, 0.5, 'h', 100]], 1000, 800).games, { w: 1, l: 1, n: 2 });
  eq('bets count every position', (({ w, l }) => [w, l])(rules.sinceFollowed([[2000, 1500, 1, 0.5, 'g', 100], [2000, 1500, 0, -1, 'g', 400]], 1000, 800)), [1, 1]);
  const since = { built: 5, sports: { nba: { '0xa': items } }, retained: { nba: { '0xr': [[1, 1, 1, 1, 'e', 1]] } } };
  eq('sinceItems reads a listed wallet, a retained one, none for a wallet with no item, null without the file', [rules.sinceItems(since, 'nba', '0xa').length, rules.sinceItems(since, 'nba', '0xr', true).length, rules.sinceItems(since, 'nba', '0xz'), rules.sinceItems(null, 'nba', '0xa')], [6, 1, [], null]);
}

console.log('follow store');
{
  const seeded = { 'nba|0xabc': 1795000000, 'nfl|0xdef': 1795100000 };
  const { SV2: S2, store } = load({ store: { 'vault-sharps-following': JSON.stringify(seeded) } });
  eq('reads the shape following.js wrote', S2.follows.all(), seeded);
  eq('has / at', [S2.follows.has('nba', '0xabc'), S2.follows.has('nba', '0xdef'), S2.follows.at('nfl', '0xdef')], [true, false, 1795100000]);
  eq('toggle on returns true and leaves other entries alone', [S2.follows.toggle('cfb', '0x123'), Object.keys(JSON.parse(store['vault-sharps-following'])).sort()], [true, ['cfb|0x123', 'nba|0xabc', 'nfl|0xdef']]);
  eq('toggle off removes only that key', [S2.follows.toggle('cfb', '0x123'), JSON.parse(store['vault-sharps-following'])], [false, seeded]);
  ok('value is epoch seconds', (() => { S2.follows.toggle('cbb', '0x9'); const v = JSON.parse(store['vault-sharps-following'])['cbb|0x9']; return v > 1.7e9 && v < 4e9; })());
  const { SV2: S3 } = load({ throwing: true });
  eq('works when localStorage throws (session memory)', [S3.follows.toggle('nba', '0x1'), S3.follows.has('nba', '0x1'), S3.follows.toggle('nba', '0x1'), S3.follows.has('nba', '0x1')], [true, true, false, false]);
}

console.log('dev hooks');
{
  const a = load({ host: 'localhost', search: '?cards=/a/b.json&wallets=https://evil.example/x.json&splits=//evil.example/x&now=1795278675' }).SV2;
  eq('same-origin path accepted', a.dev.param('cards'), '/a/b.json');
  eq('absolute URL rejected', a.dev.param('wallets'), null);
  eq('protocol-relative rejected', a.dev.param('splits'), null);
  eq('now pinned on localhost', a.now(), 1795278675);
  const b = load({ host: 'vaultfantasy.com', search: '?cards=/a/b.json&now=1795278675' }).SV2;
  eq('ignored off localhost', [b.dev.param('cards'), b.dev.ok(), Math.abs(b.now() - Date.now() / 1000) < 5], [null, false, true]);
  eq('*.localhost counts as local', load({ host: 'x.localhost', search: '?cards=/q' }).SV2.dev.param('cards'), '/q');
}

console.log('router');
{
  const r = SV2.parseHash;
  eq('default', [r('').page, r('#nope').page, r('#nope').sub], ['sharps', 'sharps', []]);
  eq('sub-routes', [r('#sharps/play/nba-por-nyk-2026-11-21/ml').sub, r('#following/acct/nba/0xabc').page], [['play', 'nba-por-nyk-2026-11-21', 'ml'], 'following']);
}

console.log('copy deck');
{
  eq('tier words and pips', SV2.copy.tierOrder.map((t) => [SV2.copy.tier[t].word, SV2.copy.tier[t].pips]), [['Clear', 3], ['Mixed', 2], ['Thin', 1], ['Contested', 0]]);
  eq('account words', Object.keys(SV2.copy.acct).map((k) => SV2.copy.acct[k].word), ['Beats the close', 'Even with the close', 'Loses to the close', 'Too few closing prices']);
  const all = JSON.stringify(SV2.copy, (k, v) => (k === 'forbidden' ? undefined : typeof v === 'function' ? v('x', 7) : v)).toLowerCase();
  const bad = SV2.copy.forbidden.filter((w) => new RegExp('\\b' + w + '\\b').test(all));
  eq('no forbidden word in the shipped strings', bad, []);
}

console.log('files');
{
  const bad = [];
  (function walk(d) {
    for (const f of fs.readdirSync(d, { withFileTypes: true })) {
      if (f.name === '_dev' || f.name === 'node_modules') continue;
      const p = path.join(d, f.name);
      if (f.isDirectory()) walk(p); else if (fs.readFileSync(p, 'utf8').includes(String.fromCharCode(0x2014))) bad.push(path.relative(ROOT, p));
    }
  })(ROOT);
  eq('no em dash in any file under sharps-v2 (outside _dev)', bad, []);
}

console.log('fixture checks');
{
  const live = readDev('live.json');
  if (!live) { skip('tierOf on the 10:21 AM CT build'); skip('same wallet'); skip('dev splits join'); }
  else {
    const plays = [];
    for (const g of live.games) for (const mk of Object.keys(g.markets || {})) { if (rules.shownUnits(g, mk) > 0) plays.push({ game: g, g: mk }); }
    const counts = { clear: 0, mixed: 0, thin: 0, contested: 0 };
    plays.forEach((p) => { counts[rules.tierOf(p.game, p.g)]++; });
    eq('11 shown plays; Contested 10, Thin 1, Mixed 0, Clear 0', [plays.length, counts], [11, { clear: 0, mixed: 0, thin: 1, contested: 10 }]);
    const thin = plays.filter((p) => rules.tierOf(p.game, p.g) === 'thin').map((p) => p.game.ev + '|' + p.g + '|' + p.game.markets[p.g].sf.all.side);
    eq('the one Thin play is CBB Under 144.5', thin, ['cbb-colmb-bostu-2026-11-21|total|Under']);
    ok('size is 1 for every shown play whatever the tier', plays.every((p) => rules.shownUnits(p.game, p.g) === 1));
    const sw = rules.sameWallet(plays);
    eq('one wallet is among the past-winner wallets on 7 of 11', [sw[0] && sw[0].w.slice(-6), sw[0] && sw[0].n, sw[0] && sw[0].total], ['5fcee5', 7, 11]);
    const splits = readDev('splits.json');
    if (!splits) skip('dev splits join');
    else {
      const { SV2: S4, sandbox } = load({ search: '?splits=/x' });
      S4.store.cards = live; S4.store.devSplits = splits;
      sandbox.module.exports.load; // keep reference
      const g = live.games.find((x) => x.ev === 'nba-por-nyk-2026-11-21');
      // buildSplits is internal: trigger through load.splits with a fetch stub
      sandbox.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(splits) });
      const res = await S4.load.splits();
      const n = Object.keys(res.byKey).length;
      ok('splits join produced entries for markets that mapped', n > 100, n);
      eq('POR at NYK moneyline split maps to the card side names', Object.keys(S4.splitsFor(g, 'ml').sides).sort(), ['Knicks', 'Trail Blazers']);
      eq('total maps Over / Under', Object.keys(S4.splitsFor(g, 'total') ? S4.splitsFor(g, 'total').sides : {}).sort(), ['Over', 'Under']);
    }
  }
  const w2 = readDev('wallets-v2.json');
  if (!w2) skip('sideTotals on the V2 wallets file');
  else {
    let groups = 0, mismatch = 0;
    for (const sp of Object.keys(w2.sports)) for (const w of Object.keys(w2.sports[sp])) {
      for (const s of rules.groupSides(w2.sports[sp][w].positions || [])) {
        const t = rules.sideTotals(s.positions);
        if (t.stored_usd != null) { groups++; if (Math.abs(t.stored_usd - t.usd) > 0.51) mismatch++; }
      }
    }
    ok('sum of rung usd equals side_usd (within $0.50 rounding) on every side', groups > 0 && mismatch === 0, { groups, mismatch });
  }
}

console.log(`\n${pass} passed, ${fail} failed, ${skipped} skipped`);
process.exit(fail ? 1 : 0);
