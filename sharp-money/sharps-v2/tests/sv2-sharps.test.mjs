/* Unit tests for the pure parts of sv2-sharps.js. No dependencies: node sharp-money/sharps-v2/tests/sv2-sharps.test.mjs
   Loads sv2-core.js then sv2-sharps.js through node:vm. Data tests read _dev/ (never committed) and are skipped when absent. */
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const DEV = path.join(ROOT, '_dev');
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
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'sv2-sharps.js'), 'utf8'), sandbox);
  return sandbox.module.exports;
}

let pass = 0, fail = 0, skipped = 0;
function ok(name, cond, extra) { if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); } }
function eq(name, a, b) { ok(name, JSON.stringify(a) === JSON.stringify(b), { got: a, want: b }); }
function skip(name) { skipped++; console.log('  skip ' + name + ' (no _dev fixtures)'); }
function readDev(f) { const p = path.join(DEV, f); return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null; }

const SV2 = load();
const P = SV2.sharpsPage;
const FORBID = SV2.copy.forbidden.concat(['edge']);

console.log('page API');
ok('sharpsPage is exported', !!P && typeof P.collectPlays === 'function');

console.log('filters');
eq('cleanFilters keeps valid values', P.cleanFilters({ sport: 'nfl', tier: 'thin', market: 'total', starts: 'hour' }), { sport: 'nfl', tier: 'thin', market: 'total', starts: 'hour' });
eq('cleanFilters drops invalid values (cfb has no plays, so no cfb chip)', P.cleanFilters({ sport: 'cfb', tier: 'strong', market: 5, starts: null }), { sport: 'all', tier: 'all', market: 'all', starts: 'all' });
eq('cleanFilters on garbage', [P.cleanFilters(null), P.cleanFilters('x')].map((f) => f.sport), ['all', 'all']);

console.log('fixture (10:21 AM CT build)');
const live = readDev('live.json');
if (!live) { skip('collectPlays'); skip('bands'); skip('reasons'); skip('filters'); skip('context'); } else {
  const plays = P.collectPlays(live, NOW);
  eq('11 shown plays', plays.length, 11);
  const by = {}; plays.forEach((p) => { by[p.tier] = (by[p.tier] || 0) + 1; });
  eq('Contested 10, Thin 1, Mixed 0, Clear 0', [by.contested || 0, by.thin || 0, by.mixed || 0, by.clear || 0], [10, 1, 0, 0]);
  ok('no CFB play is shown', plays.every((p) => p.sport !== 'cfb'));
  ok('every shown size is a flat 1u', plays.every((p) => p.units === 1));
  ok('no play is frozen or started', plays.every((p) => !p.game.frozen && p.game.gst > NOW));

  const bands = P.groupBands(plays);
  eq('bands in order, none empty', bands.map((b) => b.band), ['hour', 'today', 'tomorrow', 'later']);
  eq('band sizes', bands.map((b) => b.rows.length), [1, 3, 6, 1]);
  eq('first band is the CBB Under', bands[0].rows[0].key, 'cbb-colmb-bostu-2026-11-21|total');
  ok('first freeze time is the earliest cut of the band', bands.every((b) => b.first === Math.min(...b.rows.map((r) => r.cut))));
  const order = SV2.copy.tierOrder;
  ok('inside a band: tier order, then past winners, then cut', bands.every((b) => b.rows.every((r, i) => i === 0 || (() => {
    const a = b.rows[i - 1];
    const ta = order.indexOf(a.tier), tb = order.indexOf(r.tier);
    return ta < tb || (ta === tb && (a.facts.proven > r.facts.proven || (a.facts.proven === r.facts.proven && a.cut <= r.cut)));
  })())));

  const tb = plays.find((p) => p.key === 'nba-por-nyk-2026-11-21|ml');
  const cbb = plays.find((p) => p.key === 'cbb-colmb-bostu-2026-11-21|total');
  eq('title: moneyline', P.playTitle(tb.game, tb.g, tb.sf), 'Trail Blazers ML');
  eq('title: total', P.playTitle(cbb.game, cbb.g, cbb.sf), 'Under 144.5');
  const jx = plays.find((p) => p.g === 'spread');
  eq('title: spread keeps the stored sign', P.playTitle(jx.game, jx.g, jx.sf), 'Jaguars -6.5');
  eq('game label', P.gameLabel(tb.game), 'POR at NYK');
  eq('reason: past winners and price-sharp on the other side', P.reasonOf(tb), '3 past winners and 3 that beat the close on the other side');
  eq('reason: thin', P.reasonOf(cbb), 'One wallet, no price check');
  const st = plays.find((p) => p.key === 'nfl-pit-phi-2026-11-22|ml');
  ok('reason: more than two facts is cut to two plus a count', /\+\d more$/.test(P.reasonOf(st)), P.reasonOf(st));

  const texts = [];
  plays.forEach((p) => { texts.push(P.reasonOf(p)); P.evidenceLines(p).forEach((l) => texts.push(l.text)); P.execLines(p.sf).forEach((t) => texts.push(t)); });
  const all = texts.join(' ');
  ok('no forbidden word in reasons or evidence lines', FORBID.every((w) => !new RegExp('\\b' + w + '\\b', 'i').test(all)), FORBID.filter((w) => new RegExp('\\b' + w + '\\b', 'i').test(all)));
  ok('no em dash', !all.includes(String.fromCharCode(0x2014)));
  eq('college evidence says there is no price tier', P.evidenceLines(cbb).some((l) => /No price tier in college/.test(l.text)), true);
  eq('fair line off the main line', P.fairLine(cbb).text, 'No fair price: off Pinnacle\'s main line');
  ok('fair line with a stored fair', /^Price vs Pinnacle's no-vig fair \(41\.2c\): 0\.26 pts worse$/.test(P.fairLine(tb).text), P.fairLine(tb).text);
  eq('no exec lines when plays-data has not published them', plays.every((p) => P.execLines(p.sf).length === 0), true);

  const f = (o) => Object.assign({ sport: 'all', tier: 'all', market: 'all', starts: 'all' }, o);
  const n = (o, w, m) => plays.filter((p) => P.passes(p, f(o), null, w, m)).length;
  eq('sport filter', [n({ sport: 'nba' }), n({ sport: 'nfl' }), n({ sport: 'cbb' })], [3, 7, 1]);
  eq('tier filter', [n({ tier: 'clear' }), n({ tier: 'mixed' }), n({ tier: 'thin' }), n({ tier: 'contested' })], [0, 0, 1, 10]);
  eq('market filter', [n({ market: 'ml' }), n({ market: 'spread' }), n({ market: 'total' })], [6, 1, 4]);
  eq('starts filter: next hour, today', [n({ starts: 'hour' }), n({ starts: 'today' })], [1, 4]);
  eq('the facet being counted is skipped', plays.filter((p) => P.passes(p, f({ sport: 'nba', tier: 'thin' }), 'sport', null, {})).length, 1);
  const same = SV2.rules.sameWallet(plays.map((p) => ({ game: p.game, g: p.g })));
  const map = {}; same.forEach((r) => { map[r.w] = r; });
  eq('one wallet is on 7 plays', same.map((r) => [r.w.slice(-6), r.n, r.total]), [['5fcee5', 7, 11]]);
  eq('same-wallet focus keeps only its plays', n({}, same[0].w, map), 7);

  console.log('context list');
  const ctx = P.contextRows(live, plays, NOW);
  ok('rows are sorted by past-winner money, largest first', ctx.every((r, i) => i === 0 || ctx[i - 1].usd >= r.usd || ctx[i - 1].cfb || r.cfb));
  ok('a shown play never appears in the context list for the same market', ctx.every((r) => r.cfb || !plays.some((p) => p.game.ev === r.game.ev && p.g === r.best.g)));
  ok('CFB games where the rule picked a side are flagged cfb (the page prints "No play on CFB" and names no side)', ctx.filter((r) => r.cfb).length === 8, ctx.filter((r) => r.cfb).length);
  eq('with no plays the list is the 48 games from the spec', P.contextRows(live, [], NOW).length, 48);

  console.log('clock gates');
  const started = JSON.parse(JSON.stringify(live));
  started.games.forEach((g) => { if (g.ev === 'cbb-colmb-bostu-2026-11-21') g.gst = NOW - 60; });
  eq('a started game is not a play', P.collectPlays(started, NOW).length, 10);
  const frozen = JSON.parse(JSON.stringify(live));
  frozen.games.forEach((g) => { if (g.ev === 'nba-por-nyk-2026-11-21') g.frozen = true; });
  eq('a frozen game is not a play', P.collectPlays(frozen, NOW).length, 10);
  eq('next freeze is the earliest unfrozen cut', P.nextCut(live, NOW), Math.min(...live.games.filter((g) => !g.frozen && g.cut > NOW).map((g) => g.cut)));
}

console.log('exec lines (plays-data fields, present only when published)');
{
  const sf = { exec: { pm_ask: { px: 0.56, t: 1795278420 }, us_best: { book: 'FanDuel', odds: -118, line: 38.5, t: 1795278300 }, kalshi: { px: 0.54, t: 1795278420 }, novig: { px: 0.55, t: 1795278420 } }, close_vs_fair: { pts: 0.4 } };
  const lines = P.execLines(sf);
  eq('five lines when all are published', lines.length, 5);
  ok('formats', lines[0] === 'Polymarket ask 56c (10:27 AM CT)' && lines[1] === 'Best US book on this line: -118 at FanDuel (10:25 AM CT)' && lines[4] === 'Pinnacle close vs fair: +0.4 pts', lines);
  eq('absent or malformed fields give nothing', P.execLines({ exec: { pm_ask: { px: null }, us_best: {} } }), []);
}

console.log('\n' + pass + ' pass, ' + fail + ' fail, ' + skipped + ' skipped');
process.exit(fail ? 1 : 0);
