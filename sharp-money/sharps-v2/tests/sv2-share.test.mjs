/* Unit tests for the share-as-image feature: sv2-share.js (the pure poster layout, the share and download step) and the data builder in sv2-sharps.js.
   No dependencies: node sharp-money/sharps-v2/tests/sv2-share.test.mjs. Every fixture is synthetic: no network, no canvas, no _dev files.
   The layout is tested on its list of draw operations with a stand-in text measure; the 2D drawing is tested against a stub context that records its calls. */
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const NOW = 1795278675; // Sat Nov 21 2026 10:31 AM CST

function sandboxOf(extra, files) {
  const sandbox = Object.assign({
    console, Intl, Date, Math, JSON, Object, Array, String, Number, RegExp, Promise, Uint8Array, setTimeout, clearTimeout, setInterval, clearInterval,
    module: { exports: {} },
    location: { hostname: 'localhost', search: '?now=' + NOW, hash: '' },
    localStorage: { getItem: () => null, setItem() {} },
  }, extra || {});
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  for (const f of files) vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), sandbox);
  return sandbox;
}
function load(extra, withShare) { const sb = sandboxOf(extra, ['sv2-core.js'].concat(withShare === false ? [] : ['sv2-share.js']).concat(['sv2-sharps.js'])); return sb.module.exports; }

let pass = 0, fail = 0;
function ok(name, cond, extra) { if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); } }
function eq(name, a, b) { ok(name, JSON.stringify(a) === JSON.stringify(b), { got: a, want: b }); }

const SV2 = load();
SV2.sizesOk = () => true;
const P = SV2.sharpsPage, SH = SV2.share;
const EM = String.fromCharCode(0x2014), EN = String.fromCharCode(0x2013);
const FORBID = SV2.copy.forbidden.concat(['edge']);
const forbidHits = (s) => FORBID.filter((w) => new RegExp('\\b' + w + '\\b', 'i').test(s));
const px = (font) => parseFloat(/(\d+(?:\.\d+)?)px/.exec(font)[1]);
const measureAt = (k) => (font, s) => String(s).length * px(font) * k;
const measure = measureAt(0.52);                 /* a stand-in close to Geist: about 0.52 em per character */
const WIDE = measureAt(0.64);                     /* a stress stand-in, wider than any font in the stack */
const texts = (r) => r.ops.filter((o) => o.t === 'text');
const allText = (r) => texts(r).map((o) => o.s).join('\n');

/* ---------------------------------------------------------------- synthetic plays (same shape as the novig and move-grade tests) */
const mkp = (v2, o) => {
  o = o || {};
  return {
    game: { ev: 'e1', sport: o.sport || 'nba', gst: NOW + 7200, cut: NOW + 6300, frozen: !!o.frozen,
      vault: { away: o.away || 'MEM', home: o.home || 'CHA', teams: { away: ['Memphis Grizzlies', 'Grizzlies'], home: ['Charlotte Hornets', o.team || 'Hornets'] } },
      markets: { spread: { v2: Object.assign({ side: o.team || 'Hornets' }, v2) } } },
    g: 'spread', sf: { side: o.team || 'Hornets', line: -3.5, price: 0.525, price_t: NOW - 240 }, key: 'e1|spread', sport: o.sport || 'nba', units: o.sport === 'cfb' ? 0 : 1,
    tier: o.tier || 'mixed', cut: NOW + 6300, facts: { tiered: o.sport !== 'cfb' && o.sport !== 'cbb' }
  };
};
const PIN = (state) => ({ state, pts: 2.3, t_a: 1.5, from: 105, to: -129, line: -3.5, rows: 12 });
const LIN = (state, kind) => ({ kind: kind || 'line', state, t_c: 1, pin: kind === 'price' ? { from: 105, to: -129 } : { from: 22, to: 19 }, books: 6, same_way: 4, by_book: { Pinnacle: [22, 19], DraftKings: [22.5, 19.5] }, extreme: { book: 'BetMGM', value: 18.5 } });
const FL = (pin, line, extra) => Object.assign({ rule: 'v2f-2', span_min: 1290, window_min: 1440, pin, line, limit: { from: 1100, to: 1450, rows: 14 } }, extra || {});
const GRADE_A = { rule: 'mg-1', letter: 'A', against: false, basis: 'a_mark', a: 'toward', c: 'quiet', a_pts: 2.31, c_pts: null, cut: { m_a: 0.5, t_a: 1.5, x_a: 2.0, m_c: 1.0, t_c: 2.0, x_c: 3.5 }, why: null };
const GRADE_AGAINST = { rule: 'mg-1', letter: null, against: true, basis: 'against', a: 'away', c: 'quiet', cut: GRADE_A.cut };
const SIDE = (usd, holders) => ({ usd, holders, past_winner: { n: 3, usd: 3700 }, losing_record: { n: 2, usd: 504 }, beats: { n: 3, usd: 14900 }, loses: { n: 2, usd: 504 } });
const NOVIG = (px2, extra) => Object.assign({ px: px2, t: NOW - 1200, since_min: 14 }, extra || {});
const full = (o) => mkp({
  flags: FL(PIN('toward'), LIN('toward')), move_grade: GRADE_A,
  exec: { us_best: { book: 'BetMGM', odds: -102 }, novig: NOVIG(0.51) }, vs_fair: { pts: 0.4, fair: 0.521, line: -3.5, why: null },
  sides: { Grizzlies: SIDE(30000, 14), Hornets: SIDE(20000, 17) }
}, Object.assign({ tier: 'clear' }, o || {}));
const dataOf = (p, o) => P.shareDataOf(p, Object.assign({ url: 'vaultfantasy.com/sharp-money', nowT: NOW }, o || {}));
const lay = (d, m) => SH.buildOps(d, m || measure);

/* ---------------------------------------------------------------- the file name */
console.log('file name');
eq('sport and play, lower case, dashes', SH.fileName('nba', 'Hornets -3.5'), 'sharp-money-nba-hornets-3-5.png');
eq('a moneyline', SH.fileName('nfl', 'Jaguars ML'), 'sharp-money-nfl-jaguars-ml.png');
eq('punctuation and accents collapse, an ampersand reads as and', SH.fileName('cbb', 'Texas A&M (Corpus) Over 144.5'), 'sharp-money-cbb-texas-a-and-m-corpus-over-144-5.png');
eq('nothing at all still gives a name', [SH.fileName('', ''), SH.fileName(null, undefined), SH.fileName('!!!', '???')], ['sharp-money-play.png', 'sharp-money-play.png', 'sharp-money-play.png']);
ok('long names are cut and never end in a dash', (() => { const n = SH.fileName('nba', 'x'.repeat(200) + ' y'); return n.length <= 'sharp-money-'.length + 60 + 4 && !/-\.png$/.test(n); })());
ok('only safe characters', /^sharp-money-[a-z0-9-]+\.png$/.test(SH.fileName('nba', 'Zoë "The Man" O\'Neil/Smith')));
ok('the play data carries the same name', dataOf(full()).file === 'sharp-money-nba-hornets-3-5.png', dataOf(full()).file);
{ const ml = mkp({}); ml.g = 'ml'; ml.sf = { side: 'Hornets', line: null, price: 0.6 }; ml.game.markets.ml = { v2: { side: 'Hornets' } }; eq('a moneyline name says ml, so it never matches the same team on the spread', dataOf(ml).file, 'sharp-money-nba-hornets-ml.png'); }

/* ---------------------------------------------------------------- the page address */
console.log('page address');
eq('host and path, no query, no hash, no index.html', SH.pageUrl({ protocol: 'https:', host: 'vaultfantasy.com', pathname: '/sharp-money/index.html', search: '?now=1&tok=x', hash: '#sharps' }), 'vaultfantasy.com/sharp-money');
eq('the sharps-v2 folder is not named', SH.pageUrl({ protocol: 'https:', host: 'vaultfantasy.com', pathname: '/sharp-money/sharps-v2/' }), 'vaultfantasy.com/sharp-money');
eq('a file address has none', [SH.pageUrl({ protocol: 'file:', host: '', pathname: '/x/y.html' }), SH.pageUrl(null), SH.pageUrl({})], ['', '', '']);

/* ---------------------------------------------------------------- words wrap and never run past the box */
console.log('text wrapping');
{
  let bad = 0, n = 0;
  const words = ['Texas', 'A&M', 'Corpus', 'Christi', 'Islanders', 'Under', '144.5', 'Pinnacle', 'Supercalifragilisticexpialidocious', 'x', 'Southeastern', 'Louisiana', 'Lions'];
  for (let seed = 1; seed <= 60; seed++) {
    let s = '', r = seed;
    for (let i = 0; i < 6 + (seed % 14); i++) { r = (r * 1103515245 + 12345) & 0x7fffffff; s += (i ? ' ' : '') + words[r % words.length]; }
    for (const w of [200, 300, 936]) {
      const font = '700 44px sans-serif', L = SH.wrap(measure, font, s, w);
      n++;
      if (L.some((l) => measure(font, l) > w) || L.join('').replace(/ /g, '') !== s.replace(/ /g, '')) bad++;
    }
  }
  ok('no line is wider than its box and no character is lost (' + n + ' cases)', bad === 0, bad);
  eq('empty and junk give no lines', [SH.wrap(measure, '700 20px x', '', 100), SH.wrap(measure, '700 20px x', null, 100), SH.wrap(measure, '700 20px x', 'undefined', 100)], [[], [], []]);
  const C = SH.clamp(measure, '700 20px x', SH.wrap(measure, '700 20px x', 'aaa bbb ccc ddd eee fff ggg hhh iii jjj', 120), 2, 120);
  ok('clamp ends in three periods and still fits', C.length === 2 && /\.\.\.$/.test(C[1]) && C.every((l) => measure('700 20px x', l) <= 120), C);
}

/* ---------------------------------------------------------------- palette: every text colour reads at 4.5:1 or better on the surface it sits on */
console.log('contrast');
{
  const worst = [];
  for (const [fg, bgs] of Object.entries(SH.TEXT_ON)) for (const bg of bgs) worst.push([fg + ' on ' + bg, SH.contrast(SH.PAL[fg], SH.PAL[bg])]);
  worst.forEach(([n, c]) => ok(n + ' is ' + c.toFixed(1) + ':1 (4.5 needed)', c >= 4.5, c));
  for (const [k, c] of Object.entries(SH.TIER_COL)) ok('tier ring ' + k + ' is ' + SH.contrast(c, SH.PAL.panel).toFixed(1) + ':1 on the chip (3 needed for a graphic)', SH.contrast(c, SH.PAL.panel) >= 3);
  const r = lay(dataOf(full()));
  const used = new Set(texts(r).map((o) => o.fill));
  ok('every text op uses a palette text colour that is listed', [...used].every((c) => Object.keys(SH.TEXT_ON).some((k) => SH.PAL[k] === c)), [...used]);
}

/* ---------------------------------------------------------------- the poster for a full play */
console.log('the poster, a LARGE and Clear play with a fresh Novig quote');
const FULL = full(), FD = dataOf(FULL), FR = lay(FD), FT = allText(FR);
{
  ok('the data is built from stored values: title, game, market, date', FD.title === 'The read on Hornets -3.5' && FD.game === 'MEM at CHA' && FD.market === 'Spread' && /^SAT NOV 21$/.test(FD.date), [FD.title, FD.game, FD.market, FD.date]);
  eq('tier word and pips come from the card', FD.tier, { key: 'clear', word: 'Clear', pips: 3 });
  eq('the move label is the card label', FD.move, { key: 'a', word: 'LARGE', bars: 3 });
  eq('price tile: cents and American and best book, as the card words them', [FD.price.cents, FD.price.american, FD.price.best], ['52.5c', '-111 in American', 'Best US book -102 at BetMGM']);
  eq('fair tile: the card words', [FD.fair.value, FD.fair.sub], ['Fair 52.1c', '0.4 pts better than fair, line -3.5']);
  eq('freeze time is Central', [FD.status.label, FD.status.value], ['Freezes', '12:16 PM CT']);
  eq('the size line is the card pill words', FD.status.size, '1u untested rule');
  ok('Novig tile and sentence are both here while fresh', /^Novig 51c \(-104\), unchanged since 10:11 AM CT \(14 min old\)$/.test(FD.price.novig) && /^Novig shows -104, which is /.test(FD.moves.novig), [FD.price.novig, FD.moves.novig]);
  ok('the move sentence has no Novig in it (Novig has its own line)', !/Novig/.test(FD.moves.say) && /^Pinnacle moved this side from \+105 to -129 while its limit rose from \$1.1K to \$1.45K\.$/.test(FD.moves.say), FD.moves.say);
  eq('Pinnacle and market numbers', [FD.moves.pin, FD.moves.line], [{ label: 'Pinnacle Hornets price', from: '+105', to: '-129' }, { label: 'Market line', from: '+22', to: '+19' }]);
  eq('flag facts, as the chips word them', FD.moves.flags, ['Pinnacle\'s price moved toward Hornets', 'The market moved the number toward Hornets (4 of 6 books)']);
  eq('money: names in market order, heavier side marked, rows as the card rows', [FD.money.names, FD.money.more, FD.money.rows.map((r) => r.label)], [['Grizzlies', 'Hornets'], 0, ['Wallets that beat the close', 'Past-winner wallets', 'Wallets that lose to the close', 'All tracked money']]);
  eq('money cells are dollars and wallet counts only', FD.money.rows[3].cells, ['$30K, 14 wallets', '$20K, 17 wallets']);
  eq('footer: disclaimer, source with only the books used, Central read time, page address', [FD.footer.context, FD.footer.source, FD.footer.read, FD.footer.url],
    ['Context only. Not a bet signal.', 'Wallets: Polymarket public positions. Lines: Pinnacle, DraftKings, BetMGM, Novig. Times Central.', 'Price read 10:27 AM CT', 'vaultfantasy.com/sharp-money']);
  ok('4:5 at a pixel ratio of one', SH.W === 1080 && SH.H === 1350 && FR.height === 1350);
  ok('brand mark text, tier word, move word, disclaimer are drawn', /SHARP MONEY/.test(FT) && /\nClear\n/.test('\n' + FT + '\n') && /LARGE/.test(FT) && /Context only\. Not a bet signal\./.test(FT));
  ok('the title, the game and the price are drawn', /The read on Hornets -3\.5/.test(FT) && /MEM at CHA, Spread/.test(FT) && /52\.5c/.test(FT));
  ok('the Novig lines are drawn while fresh', /Novig 51c/.test(FT) && /Novig shows -104/.test(FT));
  ok('the page address and the read time are drawn', /vaultfantasy\.com\/sharp-money/.test(FT) && /Price read 10:27 AM CT/.test(FT));
  ok('everything from the card is here: the money, the flag facts and the line section; only the big from-to numbers (the same numbers are in the sentence) were left out for room', FR.dropped.join() === 'nums' && /WHO IS ON EACH SIDE/.test(FT) && /WHERE THE LINE WENT/.test(FT), FR.dropped);
  const circles = FR.ops.filter((o) => o.t === 'circle' && o.r === 7);
  ok('three tier pips, all filled for Clear (the word still carries it)', circles.length === 3 && circles.every((c) => c.fill), circles.length);
  const mixed = lay(dataOf(full({ tier: 'mixed' }))), cont = lay(dataOf(full({ tier: 'contested' })));
  eq('pips follow the tier: Mixed 2, Contested 0', [mixed, cont].map((r) => r.ops.filter((o) => o.t === 'circle' && o.r === 7 && o.fill).length), [2, 0]);
  eq('the tier ring takes the tier colour', [FR, mixed, cont].map((r) => r.ops.find((o) => o.t === 'rect' && o.r === 28).stroke), [SH.PAL.gold, SH.PAL.teal, SH.PAL.violet]);
}

console.log('footer anchor and flag chips');
{
  const short = lay(dataOf(mkp({})));
  const rule = short.ops.filter((o) => o.t === 'line' && o.y1 === o.y2).pop(), last = texts(short).filter((o) => o.align === 'right' || /^Price read/.test(o.s)).pop();
  ok('the footer is anchored to the bottom edge of the poster, not to the content', rule.y1 > 1000 && last.y > SH.H - SH.MB - 40 && last.y <= SH.H - SH.MB, [rule.y1, last.y]);
  const none = dataOf(mkp({ flags: FL(null, null) }));
  ok('flags with no stored state say nothing (no "no history" or "not enough books" lines)', !none.moves && !/no history|Not enough books/.test(allText(lay(none))), none.moves);
  const quiet = dataOf(mkp({ flags: FL(PIN('quiet'), LIN('quiet')) }));
  eq('quiet flags are stated as the card states them', quiet.moves.flags, ['Pinnacle\'s price held', 'The number held']);
}

console.log('layout bounds: nothing clipped, nothing overlapping');
{
  let cm = measure;
  const boxes = (r) => texts(r).map((o) => {
    const w = cm(o.font, o.s), s = px(o.font), x0 = o.align === 'right' ? o.x - w : o.x;
    return { s: o.s, x0, x1: x0 + w, y0: o.y - s * 0.85, y1: o.y + s * 0.22 };
  });
  const inside = (r) => boxes(r).every((b) => b.x0 >= SH.M - 0.5 && b.x1 <= SH.W - SH.M + 0.5 && b.y0 >= 0 && b.y1 <= SH.H - SH.MB + 20);
  const clean = (r) => { const b = boxes(r); for (let i = 0; i < b.length; i++) for (let j = i + 1; j < b.length; j++) if (b[i].x0 < b[j].x1 - 1 && b[j].x0 < b[i].x1 - 1 && b[i].y0 < b[j].y1 - 2 && b[j].y0 < b[i].y1 - 2) return [b[i].s, b[j].s]; return null; };
  const cases = {
    'full': FD,
    'a long team name': dataOf(full({ team: 'Southeastern Louisiana University Lions Of Hammond' })),
    'a very long team name': dataOf(full({ team: 'Texas A&M University Corpus Christi Islanders Of The Southland Conference Division' + ' X'.repeat(20) })),
    'no label, no flags': dataOf(mkp({ exec: { novig: NOVIG(0.51) }, vs_fair: { pts: 0.4, fair: 0.521, line: -3.5, why: null } })),
    'a CFB play': dataOf(mkp({ flags: FL(PIN('toward'), LIN('toward')) }, { sport: 'cfb' })),
    'against': dataOf(mkp({ flags: FL(PIN('away'), LIN('quiet')), move_grade: GRADE_AGAINST, sides: { Grizzlies: SIDE(30000, 14), Hornets: SIDE(20000, 17) } })),
    'nothing stored': dataOf(mkp({})),
    'long names on both sides of the money table': (() => { const d = dataOf(full()); d.money.names = ['Southeast Missouri State Redhawks', 'Purdue Fort Wayne Mastodons']; d.money.more = 0; return d; })(),
  };
  for (const [n0, d] of Object.entries(cases)) for (const [mn, m] of [['', measure], [' (wide font)', WIDE]]) {
    const n = n0 + mn; cm = m;
    const r = lay(d, m);
    ok(n + ': every drawn string sits inside the margins and above the bottom edge', inside(r), boxes(r).filter((b) => !(b.x0 >= SH.M - 0.5 && b.x1 <= SH.W - SH.M + 0.5 && b.y0 >= 0 && b.y1 <= SH.H - SH.MB + 20)).slice(0, 3));
    ok(n + ': no two strings overlap', clean(r) === null, clean(r));
    ok(n + ': every rectangle stays inside the poster', r.ops.filter((o) => o.t === 'rect').every((o) => o.x >= 0 && o.y >= 0 && o.x + o.w <= SH.W && o.y + o.h <= SH.H), r.ops.filter((o) => o.t === 'rect' && !(o.x + o.w <= SH.W && o.y + o.h <= SH.H)).slice(0, 2));
  }
  /* the worst case: every field long. Something is left out (and reported) before anything is clipped. */
  const big = dataOf(full({ team: 'Southeastern Louisiana University Lions Of Hammond Louisiana Division I' }));
  big.moves.say = 'Pinnacle moved this side from +105 to -129 while its limit rose from $1.1K to $1.45K and kept going for a very long time on a long day '.repeat(3);
  big.moves.flags = ['A very long flag sentence that goes on and on about the market and what it did '.repeat(3), 'Another very long flag sentence that also goes on '.repeat(3)];
  big.price.best = 'Best US book -102 at BetMGM and some more words that make this line very long indeed'; big.fair.sub = 'x '.repeat(80); big.footer.source += ' More source words. '.repeat(10);
  cm = WIDE;
  const br = lay(big, WIDE);
  ok('worst case: still inside and nothing overlaps', inside(br) && clean(br) === null && br.dropped.length > 0, { dropped: br.dropped, used: br.used });
  const VALID = ['', 'nums', 'money', 'nums,money', 'nums,money,flags', 'nums,money,flags,market'];
  const ladder = [[FD, 0.52], [FD, 0.58], [FD, 0.66], [big, 0.6], [big, 0.75], [big, 0.9]].map(([d, k]) => ({ k, dropped: lay(d, measureAt(k)).dropped.join() }));
  ok('only these sets are ever left out: the big numbers, then money, then flag sentences, then the line section', ladder.every((l) => VALID.indexOf(l.dropped) >= 0), ladder);
  ok('a wider font leaves out more, never less', (() => { const rank = (d) => VALID.indexOf(d.dropped); return [0, 1, 2].every((i) => rank(ladder[i]) <= rank(ladder[i + 1]) || ladder[i].dropped === 'nums' || ladder[i + 1].dropped === 'nums'); })(), ladder);
  cm = measureAt(0.9); const huge = lay(big, measureAt(0.9));
  ok('even at 0.9 em per character nothing is clipped', inside(huge) && clean(huge) === null, huge.dropped);
  cm = WIDE;
  const noMoney = lay(Object.assign({}, FD, { money: null }));
  ok('with no money rows the poster has no money block', !/WHO IS ON EACH SIDE/.test(allText(noMoney)) && /WHERE THE LINE WENT/.test(allText(noMoney)));
}

/* ---------------------------------------------------------------- the words: banned words, dashes, placeholders, names */
console.log('drawn strings: dashes and placeholders, a graded play');
{
  eq('an em dash and an en dash are never drawn', [SH.S('a' + EM + 'b'), SH.S('1' + EN + '2')], ['a-b', '1-2']);
  eq('placeholder words are never drawn', [SH.S('undefined'), SH.S('NaN'), SH.S('null'), SH.S('Value: NaN'), SH.S('x null y'), SH.S('[object Object]'), SH.S(5), SH.S(null), SH.S('  Fine  text ')], ['', '', '', '', '', '', '', '', 'Fine text']);
  const d = dataOf(full()); d.title = 'The read on A' + EM + 'B ' + EN + ' C'; d.game = 'NaN at null'; d.fair.sub = 'undefined';
  const t = allText(lay(d));
  ok('data with dashes and placeholder strings draws none of them', t.indexOf(EM) < 0 && t.indexOf(EN) < 0 && !/NaN|null|undefined/.test(t) && /The read on A-B - C/.test(t), t.split('\n').slice(0, 6));
  const g = mkp({ graded: { result: 'won', score: '105-101' }, flags: FL(PIN('toward'), LIN('toward')) }), gd = dataOf(g), gt = allText(lay(gd));
  eq('a graded play shows the final score and result as the card does, not a freeze time', [gd.status.label, gd.status.value, gd.status.sub], ['Status', 'Final 105-101', 'Won']);
  ok('and the poster draws them', /Final 105-101/.test(gt) && /\nWon\n/.test('\n' + gt + '\n') && !/FREEZES/.test(gt), gt);
}

console.log('long names: never cut to make room for the tag, one line when it fits');
{
  const d = dataOf(full()); d.money.names = ['Southeast Missouri State Redhawks', 'Purdue Fort Wayne Mastodons']; d.money.more = 0; delete d.moves.novig; delete d.price.novig; d.moves.flags = [];
  const t = allText(lay(d)).split('\n'), tagOps = lay(d).ops.filter((o) => o.t === 'text' && o.s === 'MORE MONEY');
  ok('both full names are drawn in whole, no three periods', !t.some((x) => /\.\.\./.test(x)) && /Southeast Missouri/.test(t.join(' ')) && /Redhawks/.test(t.join(' ')) && /Mastodons/.test(t.join(' ')), t.filter((x) => /Missouri|Redhawks|Mastodons/.test(x)));
  eq('the tag is drawn once', tagOps.length, 1);
  const short = dataOf(full()), sr = lay(short), tag = sr.ops.find((o) => o.t === 'text' && o.s === 'MORE MONEY'), nm = sr.ops.find((o) => o.t === 'text' && o.s === 'Grizzlies');
  ok('a short name: the tag sits beside it on the same line', Math.abs(tag.y - nm.y) <= 6 && tag.x > nm.x, [tag.y, nm.y]);
  const mid = dataOf(full({ team: 'Hornets' })); mid.title = 'The read on Hornets -3.5';
  const one = lay(mid), titleOps = one.ops.filter((o) => o.t === 'text' && /^The read on/.test(o.s));
  ok('a title that fits on one line is one line at the largest size that fits (66px here)', titleOps.length === 1 && px(titleOps[0].font) === 66, titleOps.map((o) => o.font));
  const t60 = dataOf(full()); t60.title = 'The read on Maryland Terrapins'; const o60 = lay(t60).ops.filter((o) => o.t === 'text' && /^The read on/.test(o.s));
  ok('a title too wide at 66px steps down to 60 or 54 and stays on one line', o60.length === 1 && [60, 54].indexOf(px(o60[0].font)) >= 0, o60.map((o) => o.font));
  const twoLines = dataOf(full()); twoLines.title = 'The read on ' + 'Purdue Fort Wayne Mastodons -2.5';
  const tl = lay(twoLines).ops.filter((o) => o.t === 'text' && o.font.indexOf('700') === 0 && px(o.font) >= 44 && /read on|Wayne|Mastodons/.test(o.s));
  ok('a longer title takes two lines at the largest size that fits', tl.length === 2, tl.map((o) => [o.s, o.font.slice(0, 8)]));
}

console.log('words on the image');
{
  const sets = [FD, dataOf(full({ team: 'Southeastern Louisiana University Lions' })), dataOf(mkp({ flags: FL(PIN('away'), LIN('toward', 'price')), move_grade: GRADE_AGAINST })), dataOf(mkp({ move_grade: Object.assign({}, GRADE_A, { letter: 'B', basis: 'fired' }), flags: FL(PIN('toward'), LIN('quiet')) })), dataOf(mkp({ move_grade: Object.assign({}, GRADE_A, { letter: 'C', basis: 'drift' }), flags: FL(PIN('quiet'), LIN('quiet')) })), dataOf(mkp({}, { sport: 'cfb' })), dataOf(mkp({}, { sport: 'cbb' }))];
  const all = sets.map((d) => allText(lay(d))).join('\n');
  ok('no banned word in any drawn string (' + FORBID.length + ' words, ' + sets.length + ' plays)', forbidHits(all).length === 0, forbidHits(all));
  ok('no em or en dash', all.indexOf(EM) < 0 && all.indexOf(EN) < 0);
  ok('no undefined, NaN, null or object text', !/undefined|NaN|\bnull\b|\[object/.test(all), all.match(/.{0,20}(undefined|NaN|null|\[object).{0,20}/g));
  ok('no wallet address or identity', !/0x[0-9a-fA-F]{6,}/.test(all) && !/wallet [A-Za-z0-9]{6,}/.test(all));
  const dataText = JSON.stringify(sets);
  ok('the data object has no wallet, account or user key', !/"(wallet|account|addr|address|user|email|name_hash|w)"\s*:/i.test(dataText), dataText.match(/"(wallet|account|addr|address|user|email)"/g));
  const books = (all.match(/\b(Pinnacle|DraftKings|FanDuel|BetMGM|MGM|BetRivers|bet365|Novig|Kalshi|Polymarket|Circa|BookMaker|Caesars|Bovada|PointsBet|ESPN BET|Fanatics|Hard Rock)\b/g) || []).filter((v, i, a) => a.indexOf(v) === i);
  ok('only stored books and sources are named', books.every((b) => ['Pinnacle', 'DraftKings', 'FanDuel', 'BetMGM', 'MGM', 'BetRivers', 'bet365', 'Novig', 'Kalshi', 'Polymarket'].indexOf(b) >= 0), books);
  ok('a stored book that is not in our list is never named', !/Circa|BookMaker/.test(allText(lay(dataOf(mkp({ flags: FL(PIN('toward'), Object.assign(LIN('toward'), { by_book: { Circa: [1, 2], BookMaker: [1, 2], FanDuel: [22, 19] }, extreme: { book: 'Circa', value: 20 } })) }))))));
  eq('the source line names only the books the card used (here only Pinnacle and FanDuel)', dataOf(mkp({ flags: FL(PIN('toward'), Object.assign(LIN('toward'), { by_book: { Pinnacle: [22, 19], FanDuel: [22, 19] }, extreme: null })) })).footer.source, 'Wallets: Polymarket public positions. Lines: Pinnacle, FanDuel. Times Central.');
  eq('no books used: no Lines clause', dataOf(mkp({})).footer.source, 'Wallets: Polymarket public positions. Times Central.');
  ok('the disclaimer is drawn at 28px or larger', texts(FR).filter((o) => /^Context only\. Not a bet signal\.$/.test(o.s)).every((o) => px(o.font) >= 28) && texts(FR).some((o) => /^Context only\./.test(o.s)));
  ok('no prediction words (win, cover, will, should, expect)', !/\b(will win|will cover|should|expect|pick|bet on|take the|guarantee)\b/i.test(all.replace('Not a bet signal', '')), all.match(/\b(will win|will cover|should|expect|pick|bet on|take the|guarantee)\b/gi));
  ok('the title is the card title', /^The read on /.test(FD.title));
}

console.log('Novig only while fresh and live (the card rule)');
{
  const q = (nv, o) => dataOf(mkp({ flags: FL(PIN('toward'), LIN('toward')), move_grade: GRADE_A, exec: { novig: nv }, vs_fair: { pts: 0.4, fair: 0.521, line: -3.5, why: null } }, o));
  const fresh = q(NOVIG(0.51)), edge = q(NOVIG(0.51, { since_min: 30 })), over = q(NOVIG(0.51, { since_min: 31 })), old = q(NOVIG(0.51, { since_min: 900, t: NOW - 54000 })), frozen = q(NOVIG(0.51), { frozen: true });
  const has = (d) => /Novig/.test(allText(lay(d)));
  eq('fresh (14 min): both lines', [!!fresh.price.novig, !!fresh.moves.novig, has(fresh)], [true, true, true]);
  eq('exactly 30 minutes counts as fresh', [!!edge.price.novig, !!edge.moves.novig], [true, true]);
  eq('31 minutes is stale: no line anywhere on the poster, and Novig is not a listed source', [!!over.price.novig, !!over.moves.novig, has(over), /Novig/.test(over.footer.source)], [false, false, false, false]);
  eq('a 15 hour old quote: nothing', [has(old), /Novig/.test(JSON.stringify(old))], [false, false]);
  eq('a frozen card: nothing even with a recent quote', [has(frozen), /Novig/.test(JSON.stringify(frozen))], [false, false]);
  eq('no quote at all: nothing', has(q(null)), false);
  eq('a quote with no age is not fresh', has(q({ px: 0.51, t: NOW - 100 })), false);
  eq('a bad price is nothing', [has(q(NOVIG(0))), has(q(NOVIG(1.2))), has(q(NOVIG(NaN)))], [false, false, false]);
  ok('the poster never says "Novig" in a stale case, even in the move sentence', !/Novig/.test(JSON.stringify(old.moves)) && !/Novig/.test(old.moves.say || ''));
  const card = P.writeupHtml(mkp({ flags: FL(PIN('toward'), LIN('toward')), move_grade: GRADE_A, exec: { novig: NOVIG(0.51, { since_min: 900, t: NOW - 54000 }) }, vs_fair: { pts: 0.4, fair: 0.521, line: -3.5, why: null } }), {});
  ok('the card itself still shows the old quote with its age (unchanged): only the poster is stricter', /Novig&#39;s last price was/.test(card) && /last changed/.test(card));
}

console.log('missing fields leave their lines out');
{
  const bare = dataOf(mkp({}));
  const r = lay(bare), t = allText(r);
  ok('a play with nothing stored still draws, with no stray text', !/undefined|NaN|null/.test(t) && /The read on Hornets -3\.5/.test(t) && /Context only\. Not a bet signal\./.test(t), t);
  ok('no move chip, no money, no line section, no Novig', !/MOVE|LARGE|WHO IS ON|WHERE THE LINE|Novig/.test(t), t);
  ok('no fair value: the tile says what the card says', bare.fair.sub === 'No fair price stored' && !bare.fair.value);
  eq('no key invented', Object.keys(bare.price).sort(), ['american', 'cents']);
  const noPrice = mkp({}); noPrice.sf.price = null; noPrice.sf.price_t = null;
  const np = dataOf(noPrice), npt = allText(lay(np));
  ok('no price at all: no cents, no American, no read time', !np.price.cents && !np.price.american && !np.footer.read && !/undefined|NaN|null/.test(npt), np.price);
  const noTime = mkp({}); noTime.cut = null; noTime.game.gst = null;
  const nt = dataOf(noTime);
  ok('no freeze time and no start time: no date chip and no status value', !nt.date && !nt.status.value, nt.status);
  ok('a bad tier draws no chip', !lay(Object.assign({}, bare, { tier: { key: 'x', word: '', pips: 2 } })).ops.some((o) => o.t === 'circle' && o.r === 7));
  const junk = lay({ title: undefined, game: null, market: NaN, tier: {}, move: { word: 5 }, price: { cents: undefined, best: {} }, fair: null, status: [], moves: { say: null, flags: [null, 7, 'ok'], pin: { label: 'x', from: null, to: '1' } }, money: { names: ['a'], rows: [] }, footer: { context: undefined, url: {} } });
  const jt = allText(junk);
  ok('garbage in every field: no crash, no stray text, the disclaimer still drawn', !/undefined|NaN|null|\[object/.test(jt) && /Context only\. Not a bet signal\./.test(jt) && /ok/.test(jt), jt);
  ok('null and undefined data draw the frame', texts(lay(null)).length > 0 && texts(lay(undefined)).length > 0);
}

console.log('the size line, as the card words it');
{
  eq('NBA, NFL and CBB: a flat 1u, untested rule', ['nba', 'nfl', 'cbb'].map((s) => dataOf(mkp({}, { sport: s })).status.size), ['1u untested rule', '1u untested rule', '1u untested rule']);
  eq('CFB: no size', dataOf(mkp({}, { sport: 'cfb' })).status.size, 'No size on CFB');
  SV2.sizesOk = () => false;
  eq('files not marked context only: the card shows no size, so neither does the image (CFB keeps its words)', [dataOf(mkp({})).status.size, dataOf(mkp({}, { sport: 'cfb' })).status.size], [undefined, 'No size on CFB']);
  SV2.sizesOk = () => true;
  ok('the size line is drawn', /1u untested rule/.test(allText(lay(FD))) && /No size on CFB/.test(allText(lay(dataOf(mkp({}, { sport: 'cfb' }))))));
}

console.log('a play with no label, a CFB play, a long name (data)');
{
  const nl = dataOf(mkp({ flags: FL(PIN('toward'), LIN('toward')) }));
  ok('no label: no move key, the line section and flag facts remain', !nl.move && nl.moves.flags.length === 2 && !nl.moves.say);
  eq('Market moved the other way is the card word', dataOf(mkp({ flags: FL(PIN('away'), LIN('quiet')), move_grade: GRADE_AGAINST })).move, { key: 'against', word: 'Market moved the other way', bars: 0 });
  const t = allText(lay(dataOf(mkp({ flags: FL(PIN('away'), LIN('quiet')), move_grade: GRADE_AGAINST }))));
  ok('the against chip is drawn with its words', /Market moved the other way/.test(t));
  const tot = mkp({}); tot.g = 'total'; tot.sf = { side: 'Over', line: 221.5, price: 0.5, price_t: NOW - 60 }; tot.game.markets.total = { v2: { side: 'Over', sides: { Under: SIDE(9000, 9), Over: SIDE(8000, 9) } } };
  const td = dataOf(tot);
  ok('a total reads over then under, and its title and file name', td.title === 'The read on Over 221.5' && td.money.names[0] === 'Over' && td.file === 'sharp-money-nba-over-221-5.png', [td.title, td.money && td.money.names, td.file]);
  const ml = mkp({}); ml.g = 'ml'; ml.sf = { side: 'Hornets', line: null, price: 0.6, price_t: NOW - 60 }; ml.game.markets.ml = { v2: { side: 'Hornets' } };
  eq('a moneyline title is the team alone', dataOf(ml).title, 'The read on Hornets');
  const col = dataOf(mkp({ sides: { Grizzlies: { usd: 1000, holders: 1, losing_record: { n: 1, usd: 500 } }, Hornets: { usd: 2000, holders: 2, losing_record: { n: 1, usd: 500 } } } }, { sport: 'cbb' }));
  ok('college rows carry the "Not measured in college" note, never a number we do not have', col.money.rows[0].label === 'Wallets that beat the close' && col.money.rows[0].cells[0] === 'Not measured in college', col.money.rows[0]);
}

/* ---------------------------------------------------------------- drawing: the 2D calls */
console.log('drawing with a stub 2D context');
{
  const calls = [], texts2 = [];
  const ctx = new Proxy({}, { get: (t, k) => (k in t ? t[k] : (...a) => { calls.push(k); if (k === 'createLinearGradient' || k === 'createRadialGradient') return { addColorStop() {} }; if (k === 'measureText') return { width: 1 }; }), set: (t, k, v) => { t[k] = v; if (k === 'font') ctx._lastFont = v; return true; } });
  ctx.fillText = (s, x, y) => { calls.push('fillText'); texts2.push({ s, x, y, font: ctx.font, fill: ctx.fillStyle, align: ctx.textAlign, baseline: ctx.textBaseline }); };
  SH.draw(ctx, FR.ops);
  ok('every text op was drawn once with its font, colour and alignment', texts2.length === texts(FR).length && texts2.every((t, i) => t.s === texts(FR)[i].s && t.font === texts(FR)[i].font && t.fill === texts(FR)[i].fill), [texts2.length, texts(FR).length]);
  ok('a fixed baseline', texts2.every((t) => t.baseline === 'alphabetic'));
  ok('only plain 2D calls (no image, no drawImage, no external pixels)', calls.every((c) => ['beginPath', 'moveTo', 'lineTo', 'arcTo', 'closePath', 'fill', 'stroke', 'arc', 'fillRect', 'fillText', 'createLinearGradient', 'createRadialGradient'].indexOf(c) >= 0), [...new Set(calls)]);
  ok('the font stack is the page stack with system fallbacks, no web font file', texts2.every((t) => /Geist/.test(t.font) && /system-ui|sans-serif|monospace/.test(t.font) && !/url\(/.test(t.font)));
  ok('no drawn string has a banned word', forbidHits(texts2.map((t) => t.s).join('\n')).length === 0);
}

/* ---------------------------------------------------------------- share or download */
console.log('share or download (stubbed navigator)');
const blob = { size: 5, type: 'image/png' };
function envOf(o) {
  o = o || {};
  const log = { shared: [], clicks: [], appended: 0, revoked: 0, created: 0 };
  const a = { style: {}, click() { log.clicks.push({ href: a.href, download: a.download }); if (o.clickThrows) throw new Error('blocked'); }, remove() {} };
  const env = {
    File: o.noFile ? undefined : function (parts, name, opts) { if (o.fileThrows) throw new Error('x'); this.parts = parts; this.name = name; this.type = opts && opts.type; },
    document: o.noDoc ? null : { createElement: (t) => { log.created++; return a; }, body: { appendChild() { log.appended++; } } },
    URL: o.noURL ? undefined : { createObjectURL: () => { if (o.urlThrows) throw new Error('x'); return 'blob:x'; }, revokeObjectURL: () => { log.revoked++; } },
    setTimeout: (fn) => { fn(); },
    navigator: o.nav === null ? null : o.nav === undefined ? {} : o.nav(log)
  };
  return { env, log };
}
const navWith = (o) => (log) => Object.assign({}, o.noShare ? {} : { share: (d) => { log.shared.push(d); if (o.syncThrow) throw new Error('boom'); return o.reject ? Promise.reject(o.reject) : Promise.resolve(); } }, o.noCan ? {} : { canShare: () => o.can !== false });
{
  let r = envOf({ nav: navWith({}) }), out = await SH.deliver(blob, 'sharp-money-x.png', r.env);
  eq('share supported: the file goes to the share sheet, nothing is downloaded', [out.how, r.log.shared.length, r.log.clicks.length, r.log.shared[0].files[0].name, r.log.shared[0].files[0].type], ['shared', 1, 0, 'sharp-money-x.png', 'image/png']);
  ok('the shared text is only the brand and the file, no link, no tracking', Object.keys(r.log.shared[0]).sort().join() === 'files,title' && r.log.shared[0].title === 'Sharp Money');
  r = envOf({ nav: navWith({ reject: { name: 'AbortError' } }) }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('the person closes the share sheet: cancelled, no message, no download', [out.how, out.msg, r.log.clicks.length], ['cancelled', '', 0]);
  r = envOf({ nav: navWith({ reject: { name: 'NotAllowedError' } }) }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('the browser refuses the share: it is saved instead', [out.how, out.msg, r.log.clicks.length], ['downloaded', 'Saved a.png', 1]);
  r = envOf({ nav: navWith({ reject: new Error('x') }) }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('any other share error: saved instead', [out.how, r.log.clicks.length], ['downloaded', 1]);
  r = envOf({ nav: navWith({ syncThrow: true }) }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('share throws at once: saved instead', [out.how, r.log.clicks.length], ['downloaded', 1]);
  r = envOf({ nav: navWith({ can: false }) }); out = await SH.deliver(blob, 'sharp-money-x.png', r.env);
  eq('this device cannot share files: downloads with the file name in the status', [out.how, out.msg, r.log.shared.length, r.log.clicks[0].download, r.log.clicks[0].href], ['downloaded', 'Saved sharp-money-x.png', 0, 'sharp-money-x.png', 'blob:x']);
  r = envOf({ nav: navWith({ noCan: true }) }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('share without canShare is not trusted for files: downloads', [out.how, r.log.shared.length], ['downloaded', 0]);
  r = envOf({ nav: navWith({ noShare: true }) }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('no share at all: downloads', [out.how, r.log.shared.length], ['downloaded', 0]);
  r = envOf({ nav: null }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('no navigator: downloads', out.how, 'downloaded');
  r = envOf({ nav: navWith({}), noFile: true }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('no File constructor: downloads', [out.how, r.log.shared.length], ['downloaded', 0]);
  r = envOf({ nav: navWith({}), fileThrows: true }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('File constructor throws: downloads', out.how, 'downloaded');
  r = envOf({ nav: navWith({ can: false }), urlThrows: true }); out = await SH.deliver(blob, 'a.png', r.env);
  ok('a download that cannot start says so in words', out.how === 'failed' && /Could not save the image/.test(out.msg), out);
  r = envOf({ nav: navWith({ can: false }), clickThrows: true }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('a blocked click says so in words', [out.how, /Could not save/.test(out.msg)], ['failed', true]);
  r = envOf({ nav: navWith({ can: false }), noDoc: true }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('no document: a status line, not an exception', out.how, 'failed');
  r = envOf({ nav: navWith({ can: false }), noURL: true }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('no URL object: a status line', out.how, 'failed');
  out = await SH.deliver(null, 'a.png', envOf({}).env);
  eq('no blob (the canvas could not make one): a status line', [out.how, out.msg], ['failed', 'Could not make the image.']);
  out = await SH.deliver(blob, 'a.png', undefined);
  eq('no environment at all: a status line, no throw', out.how, 'failed');
  r = envOf({ nav: navWith({ can: false }) }); out = await SH.deliver(blob, 'a.png', r.env);
  eq('the link is removed and the object URL freed after a download', [r.log.appended, r.log.revoked], [1, 1]);
  ok('every status line is plain words without a banned word or a dash', [SH.MSG.shared, SH.MSG.noCanvas, SH.MSG.failed, SH.MSG.blocked, SH.MSG.saved('sharp-money-x.png')].every((m) => forbidHits(m).length === 0 && m.indexOf(EM) < 0 && m.indexOf(EN) < 0));
}

/* ---------------------------------------------------------------- run(): the browser wrapper, with a stub document */
console.log('the browser wrapper');
{
  async function runWith(o) {
    const statuses = [], log = { clicks: [], canvases: [] };
    const ctx = { _t: 0, measureText: (s) => ({ width: String(s).length * 12 }), createLinearGradient: () => ({ addColorStop() {} }), createRadialGradient: () => ({ addColorStop() {} }), beginPath() {}, moveTo() {}, lineTo() {}, arcTo() {}, closePath() {}, arc() {}, fill() {}, stroke() {}, fillRect() {}, fillText() { ctx._t++; } };
    const canvas = { width: 0, height: 0, getContext: () => (o.noCtx ? null : ctx) };
    if (!o.noBlob) canvas.toBlob = (cb) => cb(o.nullBlob ? null : { size: 9, type: 'image/png' });
    if (o.throwBlob) canvas.toBlob = () => { throw new Error('x'); };
    if (o.dataUrl) { delete canvas.toBlob; canvas.toDataURL = () => 'data:image/png;base64,AAAA'; }
    const a = { style: {}, click() { log.clicks.push(a.download); }, remove() {} };
    const doc = { createElement: (t) => { if (t === 'canvas') { log.canvases.push(canvas); return canvas; } return a; }, body: { appendChild() {} }, fonts: o.fonts, getElementById: () => null, querySelector: () => null, addEventListener() {} };
    const nav = o.nav;
    const sb = sandboxOf({ document: doc, navigator: nav, URL: { createObjectURL: () => 'blob:1', revokeObjectURL() {} }, File: function (p, n, op) { this.name = n; this.type = op.type; }, Blob: function () {}, atob: (s) => 'abc' }, ['sv2-core.js', 'sv2-share.js']);
    const res = await sb.window.SV2.share.run(dataOf(FULL), { status: (m) => statuses.push(m) });
    return { res, statuses, log, ctx, canvas };
  }
  let r = await runWith({});
  eq('success on a device that cannot share files: 1080 x 1350, one PNG downloaded, status says the file name', [r.canvas.width, r.canvas.height, r.log.clicks, r.statuses], [1080, 1350, ['sharp-money-nba-hornets-3-5.png'], ['Saved sharp-money-nba-hornets-3-5.png']]);
  ok('the canvas was drawn on', r.ctx._t > 20, r.ctx._t);
  r = await runWith({ noCtx: true });
  eq('no 2D context: a status line and nothing else', [r.res.how, r.statuses, r.log.clicks.length], ['failed', ['This browser cannot make the image.'], 0]);
  r = await runWith({ nullBlob: true });
  eq('toBlob gives nothing: "Could not make the image."', [r.res.how, r.statuses], ['failed', ['Could not make the image.']]);
  r = await runWith({ throwBlob: true });
  eq('toBlob throws: the same status line, no exception', [r.res.how, r.statuses], ['failed', ['Could not make the image.']]);
  r = await runWith({ noBlob: true });
  eq('no toBlob and no toDataURL: a status line', [r.res.how, r.statuses], ['failed', ['Could not make the image.']]);
  r = await runWith({ dataUrl: true });
  eq('no toBlob but a data address: still saved', [r.res.how, r.log.clicks.length], ['downloaded', 1]);
  r = await runWith({ nav: { canShare: () => true, share: () => Promise.reject({ name: 'AbortError' }) } });
  eq('the share sheet is closed by the person: no status line at all', [r.res.how, r.statuses, r.log.clicks.length], ['cancelled', [], 0]);
  r = await runWith({ nav: { canShare: () => true, share: () => Promise.resolve() } });
  eq('shared on a phone: the share sheet took it', [r.res.how, r.statuses], ['shared', ['Shared the image.']]);
  r = await runWith({ fonts: { load: () => new Promise(() => {}) } });
  eq('a font that never loads does not hold the image back (600 ms cap)', r.res.how, 'downloaded');
  r = await runWith({ fonts: { load: () => Promise.reject(new Error('x')) } });
  eq('a font error does not stop the image', r.res.how, 'downloaded');
}

/* ---------------------------------------------------------------- the button on the card */
console.log('the button');
{
  const h = P.writeupHtml(FULL, { share: { nba: 0.99 } });
  const btn = /<button[^>]*data-sp-share[^>]*>/.exec(h);
  ok('a real button with the exact label', !!btn && /^<button type="button"/.test(btn[0]) && /aria-label="Share this play as an image"/.test(btn[0]), btn && btn[0]);
  ok('press primitive classes', /class="sv2-wu-sharebtn sv2-press sv2-press-btn"/.test(btn[0]));
  ok('a polite live status region next to it', /<p class="sv2-wu-sharest" id="[^"]+-share-st" role="status" aria-live="polite"><\/p>/.test(h));
  ok('the button carries the play key and nothing personal', /data-sp-share="e1\|spread"/.test(h));
  ok('it sits above the footer, inside the card', h.indexOf('sv2-wu-share') > h.indexOf('Where the line went') && h.indexOf('sv2-wu-share') < h.indexOf('sv2-wu-ft'));
  ok('one button per card', (h.match(/data-sp-share=/g) || []).length === 1);
  const without = load(undefined, false); without.sizesOk = () => true;
  const hw = without.sharpsPage.writeupHtml(FULL, { share: { nba: 0.99 } });
  ok('without the share module the card has no button (the module is optional)', !/sv2-wu-share/.test(hw));
  eq('everything else on the card is byte for byte the card without the button', h.replace(/<div class="sv2-wu-share">.*?<\/p><\/div>/, ''), hw);
  const css = fs.readFileSync(path.join(ROOT, 'sv2.css'), 'utf8');
  ok('css: 44px target, focus comes from the shared focus ring, no hand-rolled transition or animation on the button', /\.sv2-wu-sharebtn \{[^}]*min-height: 44px/.test(css) && !/sv2-wu-share[^{]*\{[^}]*(transition|animation)/.test(css));
  ok('css: no zoom and no hard-coded hex colour in the share rules', !/sv2-wu-share[^{]*\{[^}]*(zoom|#[0-9a-f]{3,6}\b)/i.test(css));
}

console.log('\n' + pass + ' pass, ' + fail + ' fail');
process.exit(fail ? 1 : 0);
