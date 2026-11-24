/* Unit tests for Novig beside cents, the gap against Pinnacle's fair, the two price chips and the "why" line in sv2-sharps.js.
   No dependencies: node sharp-money/sharps-v2/tests/sv2-novig.test.mjs. Every fixture is synthetic: no network, no _dev files. */
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const NOW = 1795278675;

function load() {
  const sandbox = {
    console, Intl, Date, Math, JSON, Object, Array, String, Number, RegExp, Promise, setTimeout, clearTimeout, setInterval, clearInterval,
    module: { exports: {} },
    location: { hostname: 'localhost', search: '?now=' + NOW, hash: '' },
    localStorage: { getItem: () => null, setItem() {} },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  for (const f of ['sv2-core.js', 'sv2-sharps.js']) vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), sandbox);
  return sandbox.module.exports;
}

let pass = 0, fail = 0;
function ok(name, cond, extra) { if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); } }
function eq(name, a, b) { ok(name, JSON.stringify(a) === JSON.stringify(b), { got: a, want: b }); }

const SV2 = load();
SV2.sizesOk = () => true;
const P = SV2.sharpsPage;
const EM = String.fromCharCode(0x2014), EN = String.fromCharCode(0x2013);
const strip = (h) => h.replace(/<[^>]+>/g, ' ').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
const NOT_WORDS = /Diamond|Odds Drop|\blean\b|\bleans\b|\bleaned\b/i;

const mkp = (v2) => ({ game: { ev: 'e1', sport: 'nba', gst: NOW + 7200, cut: NOW + 6300, vault: { away: 'MEM', home: 'CHA', teams: { away: ['Memphis Grizzlies', 'Grizzlies'], home: ['Charlotte Hornets', 'Hornets'] } },
  markets: { spread: { v2: Object.assign({ side: 'Hornets' }, v2) } } }, g: 'spread', sf: { side: 'Hornets', line: -3.5, price: 0.525 }, key: 'e1|spread', sport: 'nba', units: 1, tier: 'mixed', cut: NOW + 6300, facts: { tiered: true } });
const PIN = (state) => ({ state, pts: 2.3, t_a: 1.5, from: 105, to: -129, line: -3.5, rows: 12 });
const FL = (pin, line, extra) => Object.assign({ rule: 'v2f-2', span_min: 1290, window_min: 1440, pin, line, limit: null }, extra || {});
const NOVIG = (px, extra) => Object.assign({ px, t: NOW - 1200, since_min: 14 }, extra || {});
const VF = (fair, why) => ({ pts: 0.4, fair, line: -3.5, why: why === undefined ? null : why });
const play = (o) => mkp(Object.assign({ flags: FL(PIN('quiet'), null) }, o));

console.log('the gap and the odds');
{
  eq('the live example: px 0.735 and fair 0.7363 is +0.2%', P.gapTxt(P.novigGap(0.735, 0.7363)), '+0.2%');
  eq('a worse price is a minus', P.gapTxt(P.novigGap(0.75, 0.7363)), '-1.8%');
  eq('level is 0.0% with no sign', P.gapTxt(P.novigGap(0.6, 0.6)), '0.0%');
  eq('a tiny positive gap keeps its plus', P.gapTxt(P.novigGap(0.7, 0.70028)), '+0.0%');
  eq('one decimal, rounded', [P.gapTxt(0.0124), P.gapTxt(0.01251), P.gapTxt(-0.0049)], ['+1.2%', '+1.3%', '-0.5%']);
  eq('the gap is fair / px - 1', P.novigGap(0.5, 0.55) > 0.0999 && P.novigGap(0.5, 0.55) < 0.1001, true);
  eq('px outside (0, 1) is nothing: 0, 1, negative, above 1', [P.novigGap(0, 0.5), P.novigGap(1, 0.5), P.novigGap(-0.1, 0.5), P.novigGap(1.2, 0.5)], [null, null, null, null]);
  eq('px just inside the range still reads', P.novigGap(0.001, 0.0011) > 0.099, true);
  eq('not a number: null, NaN, a string, a boolean, Infinity', [P.novigGap(null, 0.5), P.novigGap(NaN, 0.5), P.novigGap('0.5', 0.5), P.novigGap(true, 0.5), P.novigGap(Infinity, 0.5)], [null, null, null, null, null]);
  eq('fair missing or out of range is nothing', [P.novigGap(0.6, null), P.novigGap(0.6, undefined), P.novigGap(0.6, 0), P.novigGap(0.6, 1), P.novigGap(0.6, NaN)], [null, null, null, null, null]);
  eq('no gap text for a missing gap', [P.gapTxt(null), P.gapTxt(undefined), P.gapTxt(NaN), P.gapTxt('x')], [null, null, null, null]);
  eq('American odds are the plain conversion of the stored price', [SV2.fmt.american(0.735), SV2.fmt.american(0.5), SV2.fmt.american(0.4), SV2.fmt.american(0), SV2.fmt.american(1)], ['-277', '-100', '+150', null, null]);
}

console.log('the Novig line');
{
  const nv = NOVIG(0.735);
  eq('cents, American, age and the gap before fees', P.novigText(nv, 0.7363), 'Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old); +0.2% vs Pinnacle\'s fair, before fees');
  eq('no fair: no gap, never a guess', P.novigText(nv, null), 'Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old)');
  eq('no age number: the time alone', P.novigText(NOVIG(0.735, { since_min: null }), null), 'Novig 73.5c (-277), unchanged since 10:11 AM CT');
  eq('no time: cents and odds only', P.novigText({ px: 0.735 }, null), 'Novig 73.5c (-277)');
  eq('an old quote reads in hours', P.novigText(NOVIG(0.575, { since_min: 2272 }), null), 'Novig 57.5c (-135), unchanged since 10:11 AM CT (38 hours old)');
  ok('never "read at"', !/read at/i.test(P.novigText(nv, 0.7363)));
  const lines = P.execLines({ exec: { novig: nv } }, 0.7363);
  eq('execLines carries the Novig line with the gap', lines, ['Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old); +0.2% vs Pinnacle\'s fair, before fees']);
  eq('execLines without a fair has no gap', P.execLines({ exec: { novig: nv } }), ['Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old)']);
  eq('a Novig px of 0 or 1 or missing gives no line', [P.execLines({ exec: { novig: { px: 0 } } }), P.execLines({ exec: { novig: { px: 1 } } }), P.execLines({ exec: { novig: {} } }), P.execLines({ exec: {} })], [[], [], [], []]);
  eq('the other exec lines are untouched', P.execLines({ exec: { kalshi: { px: 0.54, t: 1795278420 } } }), ['Kalshi 54c (10:27 AM CT)']);
}

console.log('reading it from the card');
{
  const ex = (n) => ({ exec: { novig: n }, vs_fair: VF(0.7363) });
  eq('present: px, gap', [P.novigOf(play(ex(NOVIG(0.735)))).px, Math.round(P.novigOf(play(ex(NOVIG(0.735)))).gap * 1000)], [0.735, 2]);
  eq('no Novig quote: nothing', [P.novigOf(play({ vs_fair: VF(0.7) })), P.novigOf(play({ exec: {} })), P.novigOf(play({ exec: { novig: null } })), P.novigOf(play({}))], [null, null, null, null]);
  eq('a quote at 0 or 1 or a string is nothing', [P.novigOf(play(ex({ px: 0 }))), P.novigOf(play(ex({ px: 1 }))), P.novigOf(play(ex({ px: '0.7' })))], [null, null, null]);
  eq('vs_fair with a why set: the quote shows, the gap does not', [P.novigOf(play({ exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7363, 'ticket_line_not_main_at_cut') })).gap, P.vsFairOf(play({ vs_fair: VF(0.7363, 'no_tape') }))], [null, null]);
  eq('vs_fair missing or fair null: no gap', [P.novigOf(play({ exec: { novig: NOVIG(0.735) } })).gap, P.novigOf(play({ exec: { novig: NOVIG(0.735) }, vs_fair: VF(null) })).gap], [null, null]);
  eq('a readable fair', P.vsFairOf(play({ vs_fair: VF(0.7363) })), 0.7363);
}

console.log('the two price chips');
{
  const withBoth = play({ flags: FL(PIN('toward'), null), exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7363) });
  const keys = (p) => P.priceChips(p).map((c) => c.k);
  eq('both fire: dropped then still open', keys(withBoth), ['drop', 'open']);
  eq('texts', P.priceChips(withBoth).map((c) => c.text), ['Price dropped', 'Price still open']);
  eq('Pinnacle quiet or away: no Price dropped', [keys(play({ flags: FL(PIN('quiet'), null) })), keys(play({ flags: FL(PIN('away'), null) })), keys(play({ flags: FL(null, null) })), keys(play({ flags: null })), keys(play({ flags: undefined }))], [[], [], [], [], []]);
  eq('Price dropped needs only the flag, not a Novig quote', keys(play({ flags: FL(PIN('toward'), null) })), ['drop']);
  const open = (n, vf) => keys(play({ flags: FL(PIN('quiet'), null), exec: n === undefined ? undefined : { novig: n }, vs_fair: vf }));
  eq('Price still open: gap above 0 and a quote', open(NOVIG(0.735), VF(0.7363)), ['open']);
  eq('gap exactly 0 or below: no chip', [open(NOVIG(0.7363), VF(0.7363)), open(NOVIG(0.75), VF(0.7363))], [[], []]);
  eq('no quote, no fair, a why, a bad px: no chip', [open(undefined, VF(0.7363)), open(NOVIG(0.735), undefined), open(NOVIG(0.735), VF(null)), open(NOVIG(0.735), VF(0.7363, 'no_tape')), open(NOVIG(0), VF(0.7363)), open(NOVIG(1), VF(0.7363))], [[], [], [], [], [], []]);
  const tip = P.priceChips(withBoth).map((c) => c.tip);
  ok('the open chip tooltip carries the gap, before fees, and the quote age', /Novig 73\.5c \(-277\) is \+0\.2% against Pinnacle's fair price, before fees, unchanged since 10:11 AM CT \(14 min old\)\./.test(tip[1]), tip[1]);
  ok('the dropped chip tooltip carries the Pinnacle move', /Pinnacle's price for this side moved toward it \(\+105 to -129\)/.test(tip[0]), tip[0]);
  ok('both say context only, not a bet signal, and make no result claim', tip.every((t) => /Context only, not a bet signal\./.test(t) && !/win|profit|beat|will/i.test(t)), tip);
  const h = P.writeupHtml(withBoth, {});
  ok('the chips sit in the existing chip row, after the two flag chips', h.indexOf('data-flag="line"') < h.indexOf('data-flag="drop"') && h.indexOf('data-flag="drop"') < h.indexOf('data-flag="open"') && /sv2-wu-chips/.test(h));
  ok('same ink chip class as the flag chips, no tier colour', (h.match(/<span class="sv2-fl" data-flag="(drop|open)"/g) || []).length === 2 && !/data-flag="(drop|open)"[^>]*(gold|violet|win|loss)/.test(h));
  const none = P.writeupHtml(play({ flags: FL(PIN('quiet'), null) }), {});
  ok('neither: no new chip and no Novig line', !/data-flag="(drop|open)"/.test(none) && !/Novig/.test(none));
  const flagsGone = P.writeupHtml(play({ flags: null, exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7363) }), {});
  ok('with the flags dropped by the size gate the open chip still shows', /data-flag="open"/.test(flagsGone) && !/data-flag="drop"/.test(flagsGone));
}

console.log('the card: tile, sentence, why line');
{
  const gradeA = { rule: 'mg-1', letter: 'A', against: false, basis: 'a_mark', a: 'toward', c: 'quiet', a_pts: 2.31, c_pts: null, cut: { m_a: 0.5, t_a: 1.5, x_a: 2.0, m_c: 1.0, t_c: 2.0, x_c: 3.5 }, why: null };
  const base = { flags: FL(PIN('toward'), null, { limit: { from: 3700, to: 5300, rows: 6 } }), exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7363) };
  const h = P.writeupHtml(play(Object.assign({ move_grade: gradeA }, base)), {});
  const t = strip(h);
  ok('the price tile says Novig in cents and American', /Novig 73\.5c \(-277\)/.test(t));
  ok('the one sentence adds Novig with the gap, before fees', /Pinnacle moved this side from \+105 to -129 while its limit rose from \$3\.7K to \$5\.3K\. Novig still shows -277, which is \+0\.2% against Pinnacle's fair price, before fees\./.test(t), t.match(/Pinnacle moved this side[^.]*\.[^.]*\.[^.]*\./));
  ok('the why area has the one line, in its own paragraph after the label line', /How this label was earned\.[\s\S]*<p class="sv2-mg-why sv2-mg-evid">A price that looks better than Pinnacle&#39;s at one moment has not paid on its own in our tests/.test(h));
  ok('the line cites the stored backtest numbers and says the label does not predict results', /47\.3% on 203 plays against 54\.5% expected/.test(t) && /The label does not predict results\./.test(t));
  const noGap = strip(P.writeupHtml(play(Object.assign({ move_grade: gradeA }, base, { vs_fair: VF(0.7363, 'no_tape') })), {}));
  ok('gap not readable: the sentence stops after the move, never a made-up percent', !/Novig still shows/.test(noGap) && /Pinnacle moved this side from/.test(noGap));
  const noNv = strip(P.writeupHtml(play(Object.assign({ move_grade: gradeA }, base, { exec: {} })), {}));
  ok('no quote: no Novig anywhere', !/Novig/.test(noNv));
  const whyOnly = P.writeupHtml(play(base), {});
  ok('no label but a Novig price: the why line still shows once', (whyOnly.match(/sv2-mg-evid/g) || []).length === 1 && !/How this label was earned/.test(whyOnly));
  const labelOnly = P.writeupHtml(play({ move_grade: gradeA, flags: base.flags }), {});
  ok('a label with no Novig: the line shows', /sv2-mg-evid/.test(labelOnly));
  const plain = P.writeupHtml(play({ flags: FL(PIN('quiet'), null) }), {});
  ok('no label, no quote: the card has none of the new bits', !/sv2-mg|Novig/.test(plain));
  const texts = [h, whyOnly, noGap, noNv, labelOnly].map(strip).join(' ') + ' ' + P.priceChips(play(base)).map((c) => c.text + ' ' + c.tip).join(' ') + ' ' + P.PRICE_WHY + ' ' + P.execLines({ exec: { novig: NOVIG(0.735) } }, 0.7363).join(' ');
  ok('the words Diamond, Odds Drop and lean appear nowhere', !NOT_WORDS.test(texts), texts.match(NOT_WORDS));
  ok('no em or en dash, no unfilled slot', !texts.includes(EM) && !texts.includes(EN) && !/[{}]|undefined|\bnull\b|NaN/.test(texts));
  ok('no book other than Novig, Pinnacle and DraftKings is named by the new text', !/Kalshi|BookMaker|Circa|Caesars|Fanatics/.test(texts));
  ok('Novig is never described as read at a time', !/read at/i.test(texts));
}

console.log('\n' + pass + ' pass, ' + fail + ' fail');
process.exit(fail ? 1 : 0);
