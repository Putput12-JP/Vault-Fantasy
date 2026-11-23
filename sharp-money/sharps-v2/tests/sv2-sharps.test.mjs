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
eq('cleanFilters drops invalid values', P.cleanFilters({ sport: 'mlb', tier: 'strong', market: 5, starts: null }), { sport: 'all', tier: 'all', market: 'all', starts: 'all' });
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

console.log('\n' + pass + ' pass, ' + fail + ' fail, ' + skipped + ' skipped');
process.exit(fail ? 1 : 0);
