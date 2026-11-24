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
eq('cleanFilters keeps valid values', P.cleanFilters({ sport: 'nfl', tier: 'thin', market: 'total', starts: 'hour' }), { sport: 'nfl', tier: 'thin', market: 'total', starts: 'hour', moves: 'all' });
eq('cleanFilters drops invalid values', P.cleanFilters({ sport: 'mlb', tier: 'strong', market: 5, starts: null }), { sport: 'all', tier: 'all', market: 'all', starts: 'all', moves: 'all' });
eq('cleanFilters keeps cfb (CFB plays show, with no size)', P.cleanFilters({ sport: 'cfb' }).sport, 'cfb');
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
  ok('CFB markets where the rule picked a side are plays now (tier, no size), so none is left as a cfb context row', ctx.filter((r) => r.cfb).length === 0, ctx.filter((r) => r.cfb).length);
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

console.log('table: sorting, bands under each sort, column cells (synthetic plays, no fixtures needed)');
{
  const mk = (key, o) => {
    const o2 = Object.assign({ tier: 'mixed', cut: 1000, band: 'today', price: 0.5, units: 1, sport: 'nba', proven: 0, pts: null, side: 'Home', tiered: true, v2: null, splits: null }, o);
    const mkt = { v2: o2.v2, splits: o2.splits };
    return {
      key, g: 'ml', sport: o2.sport, tier: o2.tier, cut: o2.cut, band: o2.band, units: o2.units,
      sf: { side: o2.side, price: o2.price },
      facts: { side: o2.side, proven: o2.proven, pts: o2.pts, tiered: o2.tiered, a1: { n: 0 }, a2: { n: 0 }, b1: { n: 0 } },
      game: { ev: key, sport: o2.sport, markets: { ml: mkt } }
    };
  };
  const A = mk('a', { tier: 'contested', cut: 300, price: 0.62, pts: -0.5, band: 'hour' });
  const B = mk('b', { tier: 'clear', cut: 500, price: 0.45, pts: 0.7, band: 'hour' });
  const C = mk('c', { tier: 'thin', cut: 100, price: 0.8, band: 'today', units: 0, sport: 'cfb' });
  const D = mk('d', { tier: 'mixed', cut: 200, price: null, pts: 0.1, band: 'tomorrow' });
  const E = mk('e', { tier: 'contested', cut: 400, price: 0.55, pts: -1.2, band: 'today' });
  const list = [A, B, C, D, E];
  const keys = (l) => l.map((p) => p.key).join('');

  eq('SORTS lists the five sortable columns', P.SORT_ORDER, ['freeze', 'price', 'fair', 'tier', 'size']);
  eq('first-click directions: Freezes up, the rest start at their useful end', P.SORT_ORDER.map((k) => P.SORTS[k].dir), [1, -1, -1, 1, -1]);
  eq('cleanSort defaults to Freezes ascending', P.cleanSort(null), { k: 'freeze', dir: 1 });
  eq('cleanSort drops an unknown column', P.cleanSort({ k: 'bogus', dir: -1 }), { k: 'freeze', dir: -1 });
  eq('cleanSort fills the first-click direction', P.cleanSort({ k: 'price' }), { k: 'price', dir: -1 });
  eq('nextSort: a new column starts at its own direction', P.nextSort({ k: 'freeze', dir: 1 }, 'price'), { k: 'price', dir: -1 });
  eq('nextSort: the active column flips', P.nextSort({ k: 'price', dir: -1 }, 'price'), { k: 'price', dir: 1 });
  eq('nextSort: Freezes flips to descending', P.nextSort({ k: 'freeze', dir: 1 }, 'freeze'), { k: 'freeze', dir: -1 });
  eq('nextSort: an unknown column changes nothing', P.nextSort({ k: 'tier', dir: 1 }, 'x'), { k: 'tier', dir: 1 });

  eq('price descending, a missing price last', keys(P.sortFlat(list, 'price', -1)), 'caebd');
  eq('price ascending, a missing price still last', keys(P.sortFlat(list, 'price', 1)), 'beacd');
  eq('vs fair descending (best price first), a missing fair last', keys(P.sortFlat(list, 'fair', -1)), 'bdaec');
  eq('vs fair ascending (worst first), a missing fair last', keys(P.sortFlat(list, 'fair', 1)), 'eadbc');
  eq('tier ascending follows the tier order (Clear first)', keys(P.sortFlat(list, 'tier', 1)), 'bdcae');
  eq('size descending: 1u plays first, CFB (no size) last', keys(P.sortFlat(list, 'size', -1)).slice(-1), 'c');
  eq('ties fall back to the default order (tier, then cut)', keys(P.sortFlat([E, A], 'tier', 1)), 'ae');
  eq('sortFlat does not change its input', keys(list), 'abcde');

  const v1 = P.viewOf(list, null);
  eq('Freezes sort: bands, in band order', v1.bands.map((b) => b.band), ['hour', 'today', 'tomorrow']);
  eq('Freezes sort: rows inside a band keep tier order (Clear before Contested)', v1.bands[0].rows.map((p) => p.key), ['b', 'a']);
  eq('Freezes sort: no flat list', v1.rows, null);
  eq('Freezes descending reverses the bands, not the rows inside', P.viewOf(list, { k: 'freeze', dir: -1 }).bands.map((b) => b.band), ['tomorrow', 'today', 'hour']);
  const v2 = P.viewOf(list, { k: 'price', dir: -1 });
  eq('any other sort: a flat list and no bands', [v2.bands, keys(v2.rows)], [null, 'caebd']);
  eq('every sort shows every play once', P.SORT_ORDER.every((k) => { const v = P.viewOf(list, { k, dir: P.SORTS[k].dir }); const n = v.bands ? v.bands.reduce((a, b) => a + b.rows.length, 0) : v.rows.length; return n === 5; }), true);
  eq('an empty list has no bands', P.viewOf([], null).bands, []);

  console.log('table: column cells');
  eq('vs fair: stored v2.vs_fair.pts, signed', P.vsFairCell(mk('f', { v2: { vs_fair: { pts: 0.72 } } })), { text: '+0.72', tone: 'pos' });
  eq('vs fair: negative', P.vsFairCell(mk('f', { v2: { vs_fair: { pts: -1.1 } } })), { text: '-1.1', tone: 'neg' });
  eq('vs fair: zero', P.vsFairCell(mk('f', { v2: { vs_fair: { pts: 0 } } })), { text: '0', tone: 'zero' });
  eq('vs fair: null pts is blank (never a number made up)', P.vsFairCell(mk('f', { v2: { vs_fair: { pts: null, why: 'ticket_line_not_main_at_cut' } } })), { text: '', tone: null });
  eq('vs fair: no v2 and no stored signal is blank', P.vsFairCell(mk('f', {})), { text: '', tone: null });
  eq('vs fair: falls back to the stored sf signal the facts read', P.vsFairCell(mk('f', { pts: -0.3 })), { text: '-0.3', tone: 'neg' });
  eq('fairPts prefers v2.vs_fair over the facts', P.fairPts(mk('f', { v2: { vs_fair: { pts: 0.4 } }, pts: -0.3 })), 0.4);

  const sp = (bets, money) => ({ t: 1, sides: { Home: { bets, money }, Away: { bets: 100 - bets, money: 100 - money } } });
  eq('splits: the play side, whole percents', P.splitCell(mk('s', { splits: sp(46.4, 48.6) })), { bets: 46, money: 49 });
  eq('splits: absent is null (the cell says n/a)', P.splitCell(mk('s', {})), null);
  eq('splits: a side the file does not list is null', P.splitCell(mk('s', { side: 'Nobody', splits: sp(50, 50) })), null);
  eq('splits: money only', P.splitCell(mk('s', { splits: { sides: { Home: { bets: null, money: 30 } } } })), { bets: null, money: 30 });
  eq('splits: both null is null', P.splitCell(mk('s', { splits: { sides: { Home: { bets: null, money: null } } } })), null);

  const conf = (o) => ({ conflict: Object.assign({ past_winner_against: { n: 0, usd: 0 }, beats_for: 1, beats_against: 2 }, o) });
  eq('wallets: for and against from v2.conflict', P.walletsCell(mk('w', { v2: conf({}) })), { tiered: true, forN: 1, againstN: 2, pwAgainst: 0 });
  eq('wallets: past winners against', P.walletsCell(mk('w', { v2: conf({ past_winner_against: { n: 3, usd: 9 } }) })).pwAgainst, 3);
  eq('wallets: 0 for and 0 against is a real count, not "no price tier"', P.walletsCell(mk('w', { v2: conf({ beats_for: 0, beats_against: 0 }) })).tiered, true);
  eq('wallets: null counts (college) mean no price tier here', P.walletsCell(mk('w', { sport: 'cbb', v2: conf({ beats_for: null, beats_against: null }) })), { tiered: false, forN: null, againstN: null, pwAgainst: null });
  eq('wallets: no v2 and not a priced sport is no price tier', P.walletsCell(mk('w', { tiered: false })).tiered, false);
  eq('wallets: no v2 on NBA or NFL falls back to the facts counts', P.walletsCell(mk('w', {})), { tiered: true, forN: 0, againstN: 0, pwAgainst: 0 });

  eq('size: 1u pill on a sized play', P.sizeCell(A), { kind: 'pill', units: 1 });
  eq('size: CFB says No size on CFB', P.sizeCell(C), { kind: 'none', text: 'No size on CFB' });
  eq('size: a non-CFB play with no size is blank', P.sizeCell(mk('z', { units: 0, sport: 'nba' })), { kind: 'blank', text: '' });
  const cells = [P.sizeCell(C).text, 'Freezes', 'vs fair', 'Bets vs money on the play', 'Wallets that beat the close'].concat(P.SORT_ORDER.map((k) => P.SORTS[k].label)).join(' ');
  ok('table copy has no forbidden word', FORBID.every((w) => !new RegExp('\\b' + w + '\\b', 'i').test(cells)), cells);
  ok('table copy has no em dash', !cells.includes(String.fromCharCode(0x2014)));
}

console.log('exec lines (plays-data fields, present only when published)');
{
  const sf = { exec: { pm_ask: { px: 0.56, t: 1795278420 }, us_best: { book: 'FanDuel', odds: -118, line: 38.5, t: 1795278300 }, kalshi: { px: 0.54, t: 1795278420 }, novig: { px: 0.55, t: 1795278420 } }, close_vs_fair: { pts: 0.4 } };
  const lines = P.execLines(sf);
  eq('five lines when all are published', lines.length, 5);
  ok('formats', lines[0] === 'Polymarket ask 56c (10:27 AM CT)' && lines[1] === 'Best US book on this line: -118 at FanDuel (10:25 AM CT)' && lines[4] === 'Pinnacle close vs fair: +0.4 pts', lines);
  eq('absent or malformed fields give nothing', P.execLines({ exec: { pm_ask: { px: null }, us_best: {} } }), []);
}

console.log('flag chips (v2.flags, optional)');
SV2.sizesOk = () => true;
const mk = (flags, extra) => ({ game: { ev: 'e1', sport: 'nba', gst: NOW + 7200, cut: NOW + 6300, vault: { away: 'MEM', home: 'CHA', teams: { away: ['Memphis Grizzlies', 'Grizzlies'], home: ['Charlotte Hornets', 'Hornets'] } },
  markets: { spread: Object.assign({ v2: Object.assign({ side: 'Hornets' }, flags === undefined ? {} : { flags }) }, extra || {}) } }, g: 'spread', sf: { side: 'Hornets', line: -3.5, price: 0.525 }, key: 'e1|spread', sport: 'nba', units: 1, tier: 'mixed', cut: NOW + 6300, facts: { tiered: true } });
const F = (pin, line, extra) => Object.assign({ rule: 'v2f-1', span_min: 1290, window_min: 1440, pin, line, limit: null }, extra || {});
const PIN = (state) => ({ state, pts: 2.3, t_a: 1.5, from: 105, to: -129, line: -3.5, rows: 12 });
const LIN = (state, kind) => ({ kind: kind || 'line', state, t_c: 1, pin: kind === 'price' ? { from: 105, to: -129 } : { from: 22, to: 19 }, books: 6, same_way: 4, by_book: {}, extreme: { book: 'BetMGM', value: 18.5 } });
eq('absent flags: no chips', P.flagChips(mk(undefined)), []);
eq('null flags: no chips', P.flagChips(mk(null)), []);
eq('flags with both null: no chips', P.flagChips(mk(F(null, null))), []);
eq('quiet draws no chip', P.flagChips(mk(F(PIN('quiet'), LIN('quiet')))), []);
{
  const c = P.flagChips(mk(F(PIN('toward'), LIN('away'))));
  eq('toward A and away C draw two chips', c.map((x) => x.text), ['Pinnacle moved toward this side', 'Market line moved away from this side']);
  ok('tooltip carries the numbers', c[0].tip.indexOf('Pinnacle +105 to -129') === 0 && c[1].tip.indexOf('Market line +22 to +19') === 0 && c[1].tip.indexOf('4 of 6 books the same way') > 0, c.map((x) => x.tip));
  const pc = P.flagChips(mk(F(null, LIN('toward', 'price'))));
  eq('moneyline C reads as the price', pc.map((x) => x.text), ['Market price moved toward this side']);
  const h = P.chipsHtml(mk(F(PIN('away'), null)));
  ok('chip html: neutral class, svg arrow, aria text, no tier or win/loss class', /class="sv2-fl"/.test(h) && /<svg/.test(h) && /sv2-sr/.test(h) && !/sv2-chip--(win|loss|price|caution|follow)|sv2-tier/.test(h), h);
  eq('no chip html when absent', P.chipsHtml(mk(undefined)), '');
  ok('a flag with no numbers still draws the state without inventing numbers', P.flagChips(mk(F({ state: 'toward' }, null)))[0].tip === 'Pinnacle\'s price, toward this side');
  ok('garbage flags (string, array) are absent', P.flagsOf(mk('x')) === null && P.flagsOf(mk([1])) === null);
  eq('movesOf: any direction counts, quiet does not', [P.movesOf(mk(F(PIN('away'), LIN('quiet')))), P.movesOf(mk(undefined))].map((m) => [m.pin, m.line, m.any]), [[true, false, true], [false, false, false]]);
}
eq('filters: a play without a Pinnacle move fails the Pinnacle filter', P.passes(mk(F(PIN('quiet'), null)), { sport: 'all', tier: 'all', market: 'all', starts: 'all', moves: 'pin' }, null, null, {}), false);
eq('filters: a moved play passes it', P.passes(mk(F(PIN('toward'), null)), { sport: 'all', tier: 'all', market: 'all', starts: 'all', moves: 'pin' }, null, null, {}), true);
eq('filters: moves is a valid value and garbage falls back', [P.cleanFilters({ moves: 'line' }).moves, P.cleanFilters({ moves: 'x' }).moves], ['line', 'all']);

console.log('chart series to points');
{
  eq('empty series', P.chartPoints([], 16), []);
  eq('missing series', P.chartPoints(undefined, 16), []);
  eq('single point kept', P.chartPoints([[0, -105]], 16), [[0, -105]]);
  eq('consecutive duplicates dropped, last kept', P.chartPoints([[0, 5], [10, 5], [20, 6], [30, 6], [40, 6]], 16), [[0, 5], [20, 6], [40, 6]]);
  eq('non-numeric rows dropped and order fixed', P.chartPoints([[20, 2], ['x', 1], [0, 1], [10, null]], 16), [[0, 1], [20, 2]]);
  const big = []; for (let i = 0; i < 60; i++) big.push([i * 10, i === 17 ? -40 : i === 41 ? 90 : i % 7 === 0 ? 10 : 11 + (i % 2)]);
  const th = P.chartPoints(big, 12);
  ok('thinned to at most the cap', th.length <= 12, th.length);
  ok('first and last kept', th[0][0] === 0 && th[th.length - 1][0] === 590, th);
  ok('lowest and highest kept', th.some((r) => r[1] === -40) && th.some((r) => r[1] === 90), th);
  const sx = (x) => x / 10, sy = (y) => 100 - y;
  const sp = P.stepPath([[0, 10], [100, 20], [200, 5]], sx, sy);
  eq('step path holds then steps', sp.d, 'M0 90H10V80H20V95');
  ok('single point is a dot, not a path', P.stepPath([[50, 7]], sx, sy).single === true);
  eq('no points gives null', P.stepPath([], sx, sy), null);
  eq('extremes are found', P.extremes([[0, 5], [1, 9], [2, 1], [3, 5]]), { lo: 2, hi: 1 });
  eq('a flat or tiny series has no extremes', [P.extremes([[0, 5], [1, 5]]), P.extremes([[0, 5]])], [null, null]);
}
console.log('series and the text alternative');
{
  const ser = { t0: NOW - 40000, unit: 'min', pin_px: [[0, -105], [95, -110], [1230, -129]], lines: { Pinnacle: [[0, 22], [300, 20], [1100, 19]], DraftKings: [[0, 22.5], [1100, 19.5]], BookMaker: [[0, 1], [10, 2]], Circa: [[0, 1], [10, 2]] } };
  const p = mk(F(PIN('toward'), LIN('toward')), { v2: { side: 'Hornets', flags: F(PIN('toward'), LIN('toward')), series: ser } });
  const s = P.seriesOf(p);
  eq('only stored books are kept (never BookMaker or Circa)', Object.keys(s.lines), ['Pinnacle', 'DraftKings']);
  const t = P.chartTable(s, 'spread');
  eq('table head', t.head, ['Time', 'Pinnacle price', 'Pinnacle line', 'DraftKings line']);
  eq('table has a row per change time', t.rows.length, 5);
  eq('values are held between changes and blank before a series starts', [t.rows[1][1], t.rows[1][2], t.rows[1][3], t.rows[4][1]], ['-110', '+22', '+22.5', '-129']);
  ok('rows start with a Central time', /CT$/.test(t.rows[0][0]), t.rows[0][0]);
  const html = P.writeupHtml(p, {});
  ok('chart is role=img with a label and a hidden table', /role="img" aria-label="Pinnacle&#39;s price for Hornets/.test(html) && /<table class="sv2-sr"><caption>/.test(html), html.length);
  ok('no BookMaker or Circa anywhere', !/BookMaker|Circa/.test(html));
  ok('draws in only when asked', /is-draw/.test(P.writeupHtml(p, { draw: true })) && !/is-draw/.test(html));
  eq('absent series: no chart, no table', /sv2-wu-charts/.test(P.writeupHtml(mk(F(PIN('toward'), LIN('toward'))), {})), false);
  eq('series with only empty books is absent', P.seriesOf(mk(F(null, null), { v2: { side: 'Hornets', series: { t0: 1, pin_px: [], lines: {} } } })), null);
}

console.log('money share formatting');
{
  eq('limit money: $1.1K to $1.45K, whole dollars under $1,000', [P.limitMoney(1100), P.limitMoney(1450), P.limitMoney(20000), P.limitMoney(504), P.limitMoney(null)], ['$1.1K', '$1.45K', '$20K', '$504', null]);
  const side = (usd, holders, extra) => Object.assign({ usd, holders, past_winner: { n: 3, usd: 3700 }, losing_record: { n: 2, usd: 504 }, beats: { n: 3, usd: 14900 }, loses: { n: 2, usd: 504 } }, extra || {});
  const tiered = P.sideRows(side(97900, 54), true);
  eq('tiered rows', tiered.map((r) => [r.label, r.usd, r.n]), [['Wallets that beat the close', '$14.9K', '3 wallets'], ['Past-winner wallets', '$3.7K', '3 wallets'], ['Wallets that lose to the close', '$504', '2 wallets'], ['All tracked money', '$97.9K', '54 wallets']]);
  const col = P.sideRows(side(1000, 1), false);
  eq('college rows say not measured and use the losing record', [col[0].note, col[2].label, col[3].n], ['Not measured in college', 'Wallets with a losing record', '1 wallet']);
  eq('a missing entry is omitted, never zero', P.sideRows({ usd: 5 }, true).map((r) => r.label), ['Wallets that beat the close'.replace('beat', 'beat')].length ? ['All tracked money'] : []);
  const base = { v2: { side: 'Hornets', sides: { Grizzlies: side(30000, 14), Hornets: side(20000, 17) } } };
  const html = P.writeupHtml(mk(F(PIN('toward'), null), base), {});
  ok('the heavier side gets the neutral ring and the tag, the other does not', (html.match(/sv2-wu-side is-more/g) || []).length === 1 && /Grizzlies<\/span><span class="sv2-chip sv2-chip--ink sv2-wu-mtag">More money/.test(html));
  ok('panels run away then home, not heavier first', html.indexOf('>Grizzlies<') < html.indexOf('>Hornets<'));
  ok('no tier class on the money panels', !/sv2-wu-side[^>]*sv2-tier/.test(html));
  const eqHtml = P.writeupHtml(mk(F(PIN('toward'), null), { v2: { side: 'Hornets', sides: { Grizzlies: side(20000, 14), Hornets: side(20000, 17) } } }), {});
  ok('equal money: no tag', !/sv2-wu-mtag/.test(eqHtml));
  eq('no sides: no panels', /Who is on each side/.test(P.writeupHtml(mk(F(PIN('toward'), null)), {})), false);
  const totalP = mk(F(null, null)); totalP.g = 'total'; totalP.sf = { side: 'Over', line: 221.5, price: 0.5 }; totalP.game.markets.total = { v2: { side: 'Over', sides: { Under: side(9000, 9), Over: side(8000, 9) } } };
  /* the plays table fit tiers (sv2.css section 17): the narrow tier drops Sport and Market from the row and shows them under the play name */
  const rowP = Object.assign({}, totalP, { facts: { tiered: false, side: 'Over' } });
  const rowH = P.rowHtml(rowP, { open: {}, more: {} }, {});
  ok('the play cell carries the sport and market line the narrow tier shows', /<span class="sv2-tb-sm">NBA \u00B7 Total<\/span>/.test(rowH), rowH.slice(0, 600));
  eq('a row still has one cell per column', (rowH.split('<tr class="sv2-tb-d"')[0].match(/<td /g) || []).length, 11);
  const th = P.writeupHtml(totalP, {});
  ok('totals run over then under', th.indexOf('>Over<') < th.indexOf('>Under<'));
}

console.log('takeaway templates, every branch');
{
  const st = [null, 'toward', 'away', 'quiet'];
  const flagsFor = (A, C, kind) => F(A ? { state: A, from: 105, to: -129 } : null, C ? Object.assign(LIN(C, kind), {}) : null);
  const money = (ms, mo, n) => ({ mine: { usd: ms, holders: n }, theirs: { usd: mo, holders: n }, other: 'Grizzlies' });
  const bannedRe = /\b(agree|agreement|proven|elite|lock|locks|locked|go|follow|lean|hot|strong|weak|confidence|guaranteed|edge|sharp pick|best bet)\b/i;
  let n = 0, bad = [];
  const seen = {};
  for (const A of st) for (const C of st) for (const kind of ['line', 'price']) for (const mon of [null, money(30000, 20000, 20), money(20000, 30000, 20), money(10000, 10000, 20), money(300, 200, 2)]) for (const size of [true, false]) for (const gr of [null, { score: '105-101', result: 'won' }]) for (const span of [1290, 75, null]) {
    const f = flagsFor(A, C, kind); if (span == null) delete f.span_min; else f.span_min = span;
    const out = P.takeaway({ flags: f, side: 'Hornets', other: 'Grizzlies', g: kind === 'price' ? 'ml' : 'spread', money: mon, size, graded: gr });
    const txt = out.join(' ');
    n++;
    if (/[{}]/.test(txt) || bannedRe.test(txt) || /undefined|null|NaN|0 books/.test(txt) || new RegExp(String.fromCharCode(8212) + '|' + String.fromCharCode(8211)).test(txt)) bad.push(txt);
    seen[A + '/' + C + (kind === 'price' ? 'p' : '')] = out[0];
    if (out[out.length - 1].indexOf('These are descriptions of what the market did.') !== 0) bad.push('last sentence: ' + txt);
    if (gr && out[out.length - 2].indexOf('Final 105-101: the play won.') !== 0) bad.push('graded: ' + txt);
  }
  ok('every combination renders, no unfilled slot, no banned word, S4 last (' + n + ' cases)', bad.length === 0, bad.slice(0, 3));
  const T1 = (A, C, o) => P.takeaway(Object.assign({ flags: flagsFor(A, C), side: 'Hornets', other: 'Grizzlies', g: 'spread', money: null, size: true }, o || {}))[0];
  eq('toward and toward', T1('toward', 'toward'), 'In the last 22 hours Pinnacle\'s price and the market\'s number both moved toward Hornets.');
  eq('away and away appends the unchanged-size note', T1('away', 'away'), 'In the last 22 hours Pinnacle\'s price and the market\'s number both moved against Hornets. The play and its size are unchanged by this.');
  eq('away and away, no size shown: no note', T1('away', 'away', { size: false }), 'In the last 22 hours Pinnacle\'s price and the market\'s number both moved against Hornets.');
  eq('toward and away', T1('toward', 'away'), 'Pinnacle\'s price moved toward Hornets while the market\'s number moved against it, so the market did not settle on one direction. The play and its size are unchanged by this.');
  eq('away and toward', T1('away', 'toward'), 'The market\'s number moved toward Hornets while Pinnacle\'s price moved against it, so the market did not settle on one direction. The play and its size are unchanged by this.');
  eq('toward and quiet', T1('toward', 'quiet'), 'Pinnacle\'s price moved toward Hornets (+105 to -129); the market\'s number held.');
  eq('toward and null', T1('toward', null), 'Pinnacle\'s price moved toward Hornets (+105 to -129); there were not enough book readings to say where the number went.');
  eq('away and quiet', T1('away', 'quiet'), 'Pinnacle\'s price moved against Hornets (+105 to -129); the market\'s number held. The play and its size are unchanged by this.');
  eq('away and null', T1('away', null), 'Pinnacle\'s price moved against Hornets (+105 to -129); there were not enough book readings to say where the number went. The play and its size are unchanged by this.');
  eq('quiet and toward', T1('quiet', 'toward'), 'The market moved the number toward Hornets (+22 to +19 at Pinnacle, 4 of 6 books the same way); Pinnacle\'s price at that number held.');
  eq('null and toward', T1(null, 'toward'), 'The market moved the number toward Hornets (+22 to +19 at Pinnacle, 4 of 6 books the same way).');
  eq('quiet and away', T1('quiet', 'away'), 'The market moved the number against Hornets (+22 to +19 at Pinnacle, 4 of 6 books the same way); Pinnacle\'s price at that number held. The play and its size are unchanged by this.');
  eq('null and away', T1(null, 'away'), 'The market moved the number against Hornets (+22 to +19 at Pinnacle, 4 of 6 books the same way). The play and its size are unchanged by this.');
  eq('quiet and quiet', T1('quiet', 'quiet'), 'The market barely moved on this spread in the last 22 hours.');
  eq('quiet and null', T1('quiet', null), 'Pinnacle\'s price barely moved; there were not enough book readings to say where the number went.');
  eq('null and quiet', T1(null, 'quiet'), 'The number barely moved at the books; Pinnacle\'s price history was not readable.');
  eq('null and null', T1(null, null), 'No market history is stored for this game, so there is nothing to say about where the line went.');
  eq('moneyline reads price, and Pinnacle\'s own price held', P.takeaway({ flags: flagsFor('quiet', 'toward', 'price'), side: 'Hornets', g: 'ml', size: false })[0], 'The market moved the price toward Hornets (+105 to -129 at Pinnacle, 4 of 6 books the same way); Pinnacle\'s own price held.');
  eq('a short span says since the first reading', P.takeaway({ flags: Object.assign(flagsFor('toward', 'toward'), { span_min: 75 }), side: 'Hornets', g: 'spread', size: true })[0], 'Since the first stored reading 75 minutes earlier, Pinnacle\'s price and the market\'s number both moved toward Hornets.');
  eq('absent flags: no S1 at all (never faked)', P.takeaway({ flags: null, side: 'Hornets', g: 'spread', money: null, size: true }).length, 1);
  const s2 = (m, A, C) => P.takeaway({ flags: flagsFor(A || 'quiet', C || 'quiet'), side: 'Hornets', other: 'Grizzlies', g: 'spread', money: m, size: true });
  eq('S2 side heavier', s2(money(30000, 20000, 20))[1], 'More of the tracked Polymarket money is on Hornets ($30K against $20K).');
  eq('S2 other heavier', s2(money(20000, 30000, 20))[1], 'More of the tracked Polymarket money is on Grizzlies ($30K against $20K).');
  eq('S2 close money is written in full when the short forms collide', s2({ mine: { usd: 120400, holders: 20 }, theirs: { usd: 119800, holders: 20 }, other: 'Grizzlies' })[1], 'More of the tracked Polymarket money is on Hornets ($120,400 against $119,800).');
  eq('S2 even', s2(money(10000, 10000, 20))[1], 'The tracked Polymarket money is split evenly ($10K each).');
  eq('S2 small sample (wallets)', s2(money(900000, 800000, 2))[1], 'Only 4 tracked wallets ($1.7M) hold this market, too few to describe.');
  eq('S2 small sample (dollars)', s2(money(300, 200, 20))[1], 'Only 40 tracked wallets ($500) hold this market, too few to describe.');
  eq('S3 when the heavier money is the other side and the market moved toward the play', s2(money(20000, 30000, 20), 'toward')[2], 'The tracked money and the market\'s moves point in different directions here.');
  eq('S3 when the heavier money is the play and the market moved against it', s2(money(30000, 20000, 20), 'quiet', 'away')[2].indexOf('The tracked money and the market\'s moves'), 0);
  ok('no S3 when they point the same way, or the sample is small', s2(money(30000, 20000, 20), 'toward').length === 3 && s2(money(300, 200, 2), 'toward').length === 3);
  ok('the closer is never advice', P.takeaway({ flags: null, side: 'x', g: 'ml', size: false }).pop() === 'These are descriptions of what the market did. Past moves like these have not paid off in Vault\'s records, so this is context, not a reason to bet.');
}

console.log('the card');
{
  const p = mk(F(PIN('toward'), LIN('toward'), { limit: { from: 1100, to: 1450, pct: 31.8, rising: true, rows: 14 } }), { v2: { side: 'Hornets', exec: { us_best: { book: 'BetMGM', odds: -102 } }, vs_fair: { pts: 0.4, fair: 0.478, line: -3.5, why: null }, flags: F(PIN('toward'), LIN('toward'), { limit: { from: 1100, to: 1450, rows: 14 } }) } });
  const h = P.writeupHtml(p, { share: { nba: 0.99 } });
  ok('top row, title, date pill, tier, no tile row', /sv2-ac-top/.test(h) && /Sharp Money, <\/span>Play breakdown/.test(h) && />NBA<span/.test(h) && />Spread<\/span>/.test(h) && /<span class="sv2-sr">The read on <\/span>Hornets -3\.5<\/h3>/.test(h) && /sv2-wu-date/.test(h) && /class="sv2-tier /.test(h) && !/sv2-wu-tile|sv2-wu-tiles|sv2-wu-take/.test(h));
  ok('shared card classes', /class="sv2-card sv2-acc-ink sv2-wu sv2-ac"/.test(h) && /<dl class="sv2-ac-rows sv2-card-inset">/.test(h));
  const rowKeys = (x) => (x.match(/data-ac="([a-z]+)"/g) || []).map((m) => m.slice(9, -1));
  eq('rows: Pinnacle price and limit, the price, fair, status (no Novig quote and no spread row on a spread play)', rowKeys(h), ['pin', 'limit', 'price', 'fair', 'status']);
  ok('limit fact line is plain text, not a chip', /Pinnacle limit \$1.1K to \$1.45K in the last 22 hours\. Pinnacle raises limits toward start on almost every game \(99% of NBA markets this season\)\./.test(h) && !/data-flag="limit"/.test(h));
  ok('chips name the side and carry text, aria and no tier colour', /Pinnacle&#39;s price moved toward Hornets/.test(h) && /The market moved the number toward Hornets \(4 of 6 books\)/.test(h));
  ok('phone: sections closed; desktop: open', !/<details[^>]* open/.test(P.writeupHtml(p, { phone: true })) && /<details class="sv2-wu-sec" open/.test(h));
  const noFlags = P.writeupHtml(mk(undefined), {});
  ok('absent flags and series: no section 2, no chips, still has the card rows and the note', !/Where the line went/.test(noFlags) && !/data-flag=/.test(noFlags) && /sv2-ac-note/.test(noFlags) && rowKeys(noFlags).join() === 'price,fair,status');
  ok('limit fact line absent without flags', !/Pinnacle limit/.test(noFlags));
  eq('limit null prints the stored-none line', P.limitLine(F(PIN('quiet'), null), null, 'nba'), 'No Pinnacle limit stored for this game.');
  eq('one reading', P.limitLine(F(null, null, { limit: { from: 3000, to: 3000, rows: 1 } }), null, 'nba'), 'Pinnacle limit $3K (one reading).');
  ok('no share sentence when the share is not stored', P.limitLine(F(null, null, { limit: { from: 3000, to: 20000, rows: 3 } }), null, 'nba').indexOf('raises limits') < 0);
  ok('fair row says none stored when absent', /data-ac="fair"><dt>Fair<\/dt><dd class="sv2-ac-v"><\/dd><dd class="sv2-ac-n">No fair price stored<\/dd>/.test(noFlags));
  ok('size pill and label untouched, CFB says No size', /untested rule/.test(h) && /No size on CFB/.test(P.writeupHtml(Object.assign(mk(undefined), { sport: 'cfb', units: 0 }), {})));
  ok('card text has no banned word or em dash', !/\b(agree|proven|elite|lock|follow|lean|strong|weak|confidence|edge)\b/i.test(h.replace(/<[^>]+>/g, ' ')) && h.indexOf(String.fromCharCode(8212)) < 0);
  eq('eyebrow sport names', ['nba', 'nfl', 'cbb', 'cfb'].map(P.eyebrowOf), ['NBA', 'NFL', 'College basketball', 'College football']);
  eq('date pill is Central', P.dateWords(1795478400), 'MON NOV 23');
}

console.log('plays table fit tiers (css)');
{
  const css = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'sv2.css'), 'utf8');
  ok('the wide columns leave by card width (container query), not viewport', /@container \(max-width: 999px\) \{\s*\.sv2 \.sv2-tb \.c-spl, \.sv2 \.sv2-tb \.c-wal \{ display: none; \}/.test(css) && !/@media \(max-width: 1100px\) \{\s*\.sv2 \.sv2-tb \.c-spl/.test(css));
  ok('Sport and Market leave under 830 and the stacked row starts under 700, both by card width', /@container \(max-width: 829px\) \{[^}]*\.c-sport, \.sv2 \.sv2-tb \.c-mkt \{ display: none; \}/.test(css) && /@container \(max-width: 699px\) \{\s*\.sv2 \.sv2-tb \.sv2-tb-sm \{ display: none; \}\s*\.sv2 \.sv2-tb, \.sv2 \.sv2-tb tbody/.test(css));
  ok('no viewport media query still stacks a table row', !/@media \(max-width: 760px\) \{\s*\.sv2 \.sv2-tb, \.sv2 \.sv2-tb tbody/.test(css) && !/@media \(max-width: 760px\) \{\s*\.sv2 \.sv2-rec-tb/.test(css));
  const emb = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'embed.js'), 'utf8');
  ok('the phone shell pins the dark theme (it has no light mode) and leaves the desktop shell alone', emb.includes("location.pathname) && !document.documentElement.hasAttribute('data-theme')) document.documentElement.setAttribute('data-theme', 'dark')"));
  ok('the rail is 272px up to 1600 and sits beside the table from 1280', /@media \(min-width: 1280px\) \{\s*\.sv2-embedded \.sv2-cols\.sv2-sp \{ grid-template-columns: minmax\(0, 1fr\) clamp\(272px, 17vw, 360px\); \}/.test(css));
}

console.log('\n' + pass + ' pass, ' + fail + ' fail, ' + skipped + ' skipped');
process.exit(fail ? 1 : 0);
