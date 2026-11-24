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

const mkp = (v2, frozen) => ({ game: { ev: 'e1', sport: 'nba', gst: NOW + 7200, cut: NOW + 6300, frozen: !!frozen, vault: { away: 'MEM', home: 'CHA', teams: { away: ['Memphis Grizzlies', 'Grizzlies'], home: ['Charlotte Hornets', 'Hornets'] } },
  markets: { spread: { v2: Object.assign({ side: 'Hornets' }, v2) } } }, g: 'spread', sf: { side: 'Hornets', line: -3.5, price: 0.525 }, key: 'e1|spread', sport: 'nba', units: 1, tier: 'mixed', cut: NOW + 6300, facts: { tiered: true } });
const PIN = (state) => ({ state, pts: 2.3, t_a: 1.5, from: 105, to: -129, line: -3.5, rows: 12 });
const FL = (pin, line, extra) => Object.assign({ rule: 'v2f-2', span_min: 1290, window_min: 1440, pin, line, limit: null }, extra || {});
const NOVIG = (px, extra) => Object.assign({ px, t: NOW - 1200, since_min: 14 }, extra || {});   /* 10:11 AM CT, Sat Nov 21 */
const VF = (fair, why) => ({ pts: 0.4, fair, line: -3.5, why: why === undefined ? null : why });
const play = (o, frozen) => mkp(Object.assign({ flags: FL(PIN('quiet'), null) }, o), frozen);
const GRADE_A = { rule: 'mg-1', letter: 'A', against: false, basis: 'a_mark', a: 'toward', c: 'quiet', a_pts: 2.31, c_pts: null, cut: { m_a: 0.5, t_a: 1.5, x_a: 2.0, m_c: 1.0, t_c: 2.0, x_c: 3.5 }, why: null };

console.log('the gap and the odds');
{
  eq('px 0.735 and fair 0.7363 is +0.2%', P.gapTxt(P.novigGap(0.735, 0.7363)), '+0.2%');
  eq('the sign follows the ROUNDED gap: 0.04% rounds to 0.0 and shows no sign, either way', [P.gapTxt(0.0004), P.gapTxt(-0.0004), P.gapTxt(0), P.gapTxt(0.0006), P.gapTxt(-0.0006)], ['0.0%', '0.0%', '0.0%', '+0.1%', '-0.1%']);
  eq('the words follow the rounded gap: a price below fair is a positive gap and says below, above fair says above', [P.gapWords(0.005), P.gapWords(-0.017), P.gapWords(0.0004), P.gapWords(-0.0004)], ['0.5% below Pinnacle\'s fair price', '1.7% above Pinnacle\'s fair price', 'level with Pinnacle\'s fair price', 'level with Pinnacle\'s fair price']);
  eq('one decimal, rounded', [P.gapTxt(0.0124), P.gapTxt(0.01251), P.gapTxt(-0.0049)], ['+1.2%', '+1.3%', '-0.5%']);
  eq('the gap is fair / px - 1', P.novigGap(0.5, 0.55) > 0.0999 && P.novigGap(0.5, 0.55) < 0.1001, true);
  eq('px outside (0, 1) is nothing: 0, 1, negative, above 1', [P.novigGap(0, 0.5), P.novigGap(1, 0.5), P.novigGap(-0.1, 0.5), P.novigGap(1.2, 0.5)], [null, null, null, null]);
  eq('px just inside the range still reads', P.novigGap(0.001, 0.0011) > 0.099, true);
  eq('not a number: null, NaN, a string, a boolean, Infinity', [P.novigGap(null, 0.5), P.novigGap(NaN, 0.5), P.novigGap('0.5', 0.5), P.novigGap(true, 0.5), P.novigGap(Infinity, 0.5)], [null, null, null, null, null]);
  eq('fair missing or out of range is nothing', [P.novigGap(0.6, null), P.novigGap(0.6, undefined), P.novigGap(0.6, 0), P.novigGap(0.6, 1), P.novigGap(0.6, NaN)], [null, null, null, null, null]);
  eq('no text for a missing gap', [P.gapTxt(null), P.gapTxt(undefined), P.gapTxt(NaN), P.gapTxt('x'), P.gapWords(null), P.gapPct(undefined)], [null, null, null, null, null, null]);
  eq('American odds are the plain conversion of the stored price', [SV2.fmt.american(0.735), SV2.fmt.american(0.5), SV2.fmt.american(0.4), SV2.fmt.american(0), SV2.fmt.american(1)], ['-277', '-100', '+150', null, null]);
}

console.log('a recent quote on a live card, and the 30 minute rule');
{
  const ex = (n, frozen, fair) => play({ exec: { novig: n }, vs_fair: VF(fair === undefined ? 0.7363 : fair) }, frozen);
  eq('14 minutes: fresh, with the gap', [P.novigOf(ex(NOVIG(0.735))).fresh, Math.round(P.novigOf(ex(NOVIG(0.735))).gap * 1000)], [true, 2]);
  eq('exactly 30 minutes is still fresh', [P.novigOf(ex(NOVIG(0.735, { since_min: 30 }))).fresh, P.novigOf(ex(NOVIG(0.735, { since_min: 30 }))).gap !== null], [true, true]);
  eq('31 minutes is not: the quote reads, the gap does not', [P.novigOf(ex(NOVIG(0.735, { since_min: 31 }))).fresh, P.novigOf(ex(NOVIG(0.735, { since_min: 31 }))).gap, P.novigOf(ex(NOVIG(0.735, { since_min: 31 }))).px], [false, null, 0.735]);
  eq('a frozen card is never fresh, even at 1 minute', [P.novigOf(ex(NOVIG(0.735, { since_min: 1 }), true)).fresh, P.novigOf(ex(NOVIG(0.735, { since_min: 1 }), true)).gap], [false, null]);
  eq('no since_min is not fresh', [P.novigOf(ex(NOVIG(0.735, { since_min: null }))).fresh, P.novigOf(ex({ px: 0.735, t: NOW - 100 })).fresh], [false, false]);
  eq('no quote: nothing', [P.novigOf(play({ vs_fair: VF(0.7) })), P.novigOf(play({ exec: {} })), P.novigOf(play({ exec: { novig: null } })), P.novigOf(play({}))], [null, null, null, null]);
  eq('a quote at 0 or 1 or a string is nothing', [P.novigOf(ex({ px: 0 })), P.novigOf(ex({ px: 1 })), P.novigOf(ex({ px: '0.7' }))], [null, null, null]);
  eq('vs_fair with a why set: a fresh quote reads, the gap does not', [P.novigOf(ex(NOVIG(0.735), false, 0.7363)).fresh, P.novigOf(play({ exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7363, 'ticket_line_not_main_at_cut') })).gap, P.vsFairOf(play({ vs_fair: VF(0.7363, 'no_tape') }))], [true, null, null]);
  eq('vs_fair missing or fair null: no gap', [P.novigOf(play({ exec: { novig: NOVIG(0.735) } })).gap, P.novigOf(play({ exec: { novig: NOVIG(0.735) }, vs_fair: VF(null) })).gap], [null, null]);
}

console.log('how old the quote is, in words');
{
  eq('under 2 hours: the time and the minutes', P.novigAge(NOVIG(0.7), false), 'unchanged since 10:11 AM CT (14 min old)');
  eq('2 to 12 hours: the time and the hours', P.novigAge(NOVIG(0.7, { since_min: 300 }), false), 'unchanged since 10:11 AM CT (5 hours old)');
  eq('exactly 12 hours keeps the time', P.novigAge(NOVIG(0.7, { since_min: 720 }), false), 'unchanged since 10:11 AM CT (12 hours old)');
  eq('past 12 hours: the date, and how long before this read', P.novigAge(NOVIG(0.7, { since_min: 721 }), false), 'last changed Nov 21, 10:11 AM CT, 12 hours before this read');
  eq('38 hours', P.novigAge(NOVIG(0.7, { since_min: 2272 }), false), 'last changed Nov 21, 10:11 AM CT, 38 hours before this read');
  eq('on a frozen card it is before the freeze', P.novigAge(NOVIG(0.7, { since_min: 2272 }), true), 'last changed Nov 21, 10:11 AM CT, 38 hours before the freeze');
  eq('the minutes to hours switch is at 120', [P.novigAge(NOVIG(0.7, { since_min: 119 }), false), P.novigAge(NOVIG(0.7, { since_min: 120 }), false)], ['unchanged since 10:11 AM CT (119 min old)', 'unchanged since 10:11 AM CT (2 hours old)']);
  ok('never an unchanged-since next to an age past 12 hours', !/unchanged since/.test(P.novigAge(NOVIG(0.7, { since_min: 2272 }), false)));
  eq('no time stored: the age alone, or nothing', [P.novigAge({ px: 0.7, since_min: 14 }, false), P.novigAge({ px: 0.7, since_min: 300 }, false), P.novigAge({ px: 0.7 }, false)], ['14 min old', '5 hours old', null]);
}

console.log('the Novig line, the tile and the sentence');
{
  const fresh = NOVIG(0.735), old = NOVIG(0.735, { since_min: 2272 });
  eq('fresh line: cents, American, age and the gap before fees', P.novigText(fresh, 0.7363, { fresh: true }), 'Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old); 0.2% below Pinnacle\'s fair price, before fees');
  eq('fresh line with a price above fair says above', P.novigText(fresh, 0.7, { fresh: true }), 'Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old); 4.8% above Pinnacle\'s fair price, before fees');
  eq('fresh line with no fair: no gap', P.novigText(fresh, null, { fresh: true }), 'Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old)');
  eq('an old quote: the plain price with its date, no gap even with a fair', P.novigText(old, 0.7363, { fresh: false }), 'Novig 73.5c (-277), last changed Nov 21, 10:11 AM CT, 38 hours before this read');
  eq('no options: no gap', P.novigText(fresh, 0.7363), 'Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old)');
  eq('execLines passes the rule through', [P.execLines({ exec: { novig: fresh } }, 0.7363, { fresh: true }), P.execLines({ exec: { novig: fresh } }, 0.7363, { fresh: false })], [['Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old); 0.2% below Pinnacle\'s fair price, before fees'], ['Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old)']]);
  eq('a Novig px of 0 or 1 or missing gives no line', [P.execLines({ exec: { novig: { px: 0 } } }), P.execLines({ exec: { novig: { px: 1 } } }), P.execLines({ exec: { novig: {} } }), P.execLines({ exec: {} })], [[], [], [], []]);
  eq('the other exec lines are untouched', P.execLines({ exec: { kalshi: { px: 0.54, t: 1795278420 } } }), ['Kalshi 54c (10:27 AM CT)']);
  ok('never "read at"', !/read at/i.test(P.novigText(fresh, 0.7363, { fresh: true }) + P.novigText(old, 0.7363)));
  const nvq = (n, frozen) => P.novigOf(play({ exec: { novig: n }, vs_fair: VF(0.7363) }, frozen));
  eq('tile: a fresh price carries its age', P.novigTile(nvq(fresh), false), 'Novig 73.5c (-277), unchanged since 10:11 AM CT (14 min old)');
  eq('tile: an old price carries its date, never a bare price', P.novigTile(nvq(old), false), 'Novig 73.5c (-277), last changed Nov 21, 10:11 AM CT, 38 hours before this read');
  eq('tile: an old price with no time and no age shows nothing', P.novigTile(nvq({ px: 0.735 }), false), null);
  eq('sentence, fresh price above fair', P.novigSentence(nvq(fresh), false) && P.novigSentence(P.novigOf(play({ exec: { novig: fresh }, vs_fair: VF(0.7223) })), false), 'Novig shows -277, which is 1.7% above Pinnacle\'s fair price (before fees).');
  eq('sentence, fresh price below fair', P.novigSentence(P.novigOf(play({ exec: { novig: NOVIG(0.575) }, vs_fair: VF(0.5778) })), false), 'Novig shows -135, which is 0.5% below Pinnacle\'s fair price (before fees).');
  eq('sentence, fresh and level', P.novigSentence(P.novigOf(play({ exec: { novig: NOVIG(0.6) }, vs_fair: VF(0.6002) })), false), 'Novig shows -150, which is level with Pinnacle\'s fair price (before fees).');
  eq('sentence, fresh with no fair: the price only', P.novigSentence(P.novigOf(play({ exec: { novig: fresh } })), false), 'Novig shows -277.');
  eq('sentence, old: the last price and when it changed, no gap', P.novigSentence(nvq(old), false), 'Novig\'s last price was -277 (last changed Nov 21, 10:11 AM CT).');
  eq('sentence, 31 minutes: the last price, no gap', P.novigSentence(nvq(NOVIG(0.735, { since_min: 31 })), false), 'Novig\'s last price was -277 (last changed 10:11 AM CT).');
  eq('sentence, frozen: the last price, no gap, no "shows"', P.novigSentence(nvq(NOVIG(0.735, { since_min: 1 }), true), true), 'Novig\'s last price was -277 (last changed 10:11 AM CT).');
  ok('no sentence says "still"', ![nvq(fresh), nvq(old)].some((q) => /\bstill\b/i.test(P.novigSentence(q, false))));
}

console.log('the one chip');
{
  const open = (n, vf, frozen) => P.priceChips(play({ exec: n === undefined ? undefined : { novig: n }, vs_fair: vf }, frozen)).map((c) => c.k);
  eq('fresh, live, gap above 0: Novig under fair', open(NOVIG(0.735), VF(0.7363)), ['novig']);
  eq('the text names what it measures and says before fees', P.priceChips(play({ exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7363) }))[0].text, 'Novig under fair (before fees)');
  eq('exactly 30 minutes shows it, 31 does not, a frozen card does not', [open(NOVIG(0.735, { since_min: 30 }), VF(0.7363)), open(NOVIG(0.735, { since_min: 31 }), VF(0.7363)), open(NOVIG(0.735, { since_min: 1 }), VF(0.7363), true)], [['novig'], [], []]);
  eq('a gap that rounds to 0.0 gets no chip (0.04% up), and 0.05% rounds to 0.1 and does', [open(NOVIG(0.7, {}), VF(0.70028)), open(NOVIG(0.7, {}), VF(0.70035))], [[], ['novig']]);
  eq('gap at 0 or below: no chip', [open(NOVIG(0.7363), VF(0.7363)), open(NOVIG(0.75), VF(0.7363))], [[], []]);
  eq('no quote, no fair, a why, a bad px: no chip', [open(undefined, VF(0.7363)), open(NOVIG(0.735), undefined), open(NOVIG(0.735), VF(null)), open(NOVIG(0.735), VF(0.7363, 'no_tape')), open(NOVIG(0), VF(0.7363)), open(NOVIG(1), VF(0.7363))], [[], [], [], [], [], []]);
  const tip = P.priceChips(play({ exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7363) }))[0].tip;
  ok('the tooltip carries the gap in words, before fees, and the quote age', /Novig 73\.5c \(-277\) is 0\.2% below Pinnacle's fair price, before fees, unchanged since 10:11 AM CT \(14 min old\)\./.test(tip), tip);
  ok('it says context only, not a bet signal, and makes no result claim', /Context only, not a bet signal\./.test(tip) && !/win|profit|beat|will/i.test(tip), tip);
  const withFlag = play({ flags: FL(PIN('toward'), null), exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7363) });
  const h = P.writeupHtml(withFlag, {});
  ok('the Price dropped chip is gone, even with Pinnacle moving toward the side; the existing flag chip stays', !/Price dropped|data-flag="drop"/.test(h) && /Pinnacle&#39;s price moved toward Hornets/.test(h));
  ok('the chip sits in the chip row after the flag chips, in the same ink chip class', h.indexOf('data-flag="line"') < h.indexOf('data-flag="novig"') && /<span class="sv2-fl" data-flag="novig"/.test(h) && !/data-flag="novig"[^>]*(gold|violet|win|loss)/.test(h));
  ok('neither Novig nor a chip when there is no quote', !/Novig|data-flag="novig"/.test(P.writeupHtml(play({ flags: FL(PIN('quiet'), null) }), {})));
  const flagsGone = P.writeupHtml(play({ flags: null, exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7363) }), {});
  ok('with the flags dropped by the size gate the chip still shows', /data-flag="novig"/.test(flagsGone));
  const stale = P.writeupHtml(play({ flags: FL(PIN('quiet'), null), exec: { novig: NOVIG(0.575, { since_min: 2272 }) }, vs_fair: VF(0.5778) }), {});
  ok('a stale quote: no chip, no gap anywhere in the card', !/data-flag="novig"/.test(stale) && !/below Pinnacle|above Pinnacle/.test(strip(stale)));
}

console.log('the card: tile, sentence, why line');
{
  const base = { flags: FL(PIN('toward'), null, { limit: { from: 3700, to: 5300, rows: 6 } }), exec: { novig: NOVIG(0.735) }, vs_fair: VF(0.7223) };
  const h = P.writeupHtml(play(Object.assign({ move_grade: GRADE_A }, base)), {});
  const t = strip(h);
  const tile = strip((/The price<\/p>[\s\S]*?Price now/.exec(h) || [''])[0]);
  ok('the price tile says Novig in cents and American with its age', /Novig 73\.5c \(-277\), unchanged since 10:11 AM CT \(14 min old\)/.test(tile), tile);
  const priceSec = strip(P.priceHtml(play(Object.assign({ move_grade: GRADE_A }, base))));
  ok('the Price section carries the Novig line with the gap in words, before fees', /Novig 73\.5c \(-277\), unchanged since 10:11 AM CT \(14 min old\); 1\.7% above Pinnacle's fair price, before fees/.test(priceSec), priceSec);
  const priceStale = strip(P.priceHtml(play({ exec: { novig: NOVIG(0.735, { since_min: 2272 }) }, vs_fair: VF(0.7223) })));
  ok('the Price section with an old quote: the plain price and its date, no gap', /Novig 73\.5c \(-277\), last changed Nov 21, 10:11 AM CT, 38 hours before this read/.test(priceStale) && !/above Pinnacle|below Pinnacle/.test(priceStale), priceStale);
  ok('no Novig line in the Price section when there is no quote', !/Novig/.test(strip(P.priceHtml(play({ flags: base.flags, vs_fair: VF(0.7363) })))));
  ok('the one sentence: the Pinnacle move, then the fresh Novig price in sign-clear words before fees', /Pinnacle moved this side from \+105 to -129 while its limit rose from \$3\.7K to \$5\.3K\. Novig shows -277, which is 1\.7% above Pinnacle's fair price \(before fees\)\./.test(t), t.match(/Pinnacle moved this side[^.]*\.[^.]*\.[^.]*\./));
  const staleSentence = strip(P.writeupHtml(play(Object.assign({ move_grade: GRADE_A }, base, { exec: { novig: NOVIG(0.735, { since_min: 2272 }) } })), {}));
  ok('an old quote: "last price", the date, no gap and no "shows"', /Novig's last price was -277 \(last changed Nov 21, 10:11 AM CT\)\./.test(staleSentence) && !/Novig shows/.test(staleSentence));
  const frozenSentence = strip(P.writeupHtml(play(Object.assign({ move_grade: GRADE_A }, base, { exec: { novig: NOVIG(0.735, { since_min: 3 }) } }), true), {}));
  ok('a frozen card: the last price only', /Novig's last price was -277 \(last changed 10:11 AM CT\)\./.test(frozenSentence) && !/Novig shows|above Pinnacle|below Pinnacle/.test(frozenSentence));
  ok('the why area has the one line in its own paragraph after the label line', /How this label was earned\.[\s\S]*<p class="sv2-mg-why sv2-mg-evid">A price that looks better than Pinnacle&#39;s at one moment has not paid on its own in our tests\./.test(h));
  ok('the line says it was NBA player props at DraftKings, a different market, and the label does not predict results', /In an earlier test on NBA player props at DraftKings, plays that looked \+EV against Pinnacle hit 47\.3% on 203 plays against 54\.5% expected\. That is a different market, so treat it as a caution about the idea, not a measure of this label\. The label does not predict results\./.test(t));
  const noGap = strip(P.writeupHtml(play(Object.assign({ move_grade: GRADE_A }, base, { vs_fair: VF(0.7223, 'no_tape') })), {}));
  ok('gap not readable: the fresh price only, never a made-up percent', /Novig shows -277\./.test(noGap) && !/above Pinnacle|below Pinnacle/.test(noGap));
  const noNv = strip(P.writeupHtml(play(Object.assign({ move_grade: GRADE_A }, base, { exec: {} })), {}));
  ok('no quote: no Novig anywhere', !/Novig/.test(noNv));
  const whyOnly = P.writeupHtml(play(base), {});
  ok('no label but a Novig price: the why line still shows once', (whyOnly.match(/sv2-mg-evid/g) || []).length === 1 && !/How this label was earned/.test(whyOnly));
  const labelOnly = P.writeupHtml(play({ move_grade: GRADE_A, flags: base.flags }), {});
  ok('a label with no Novig: the line shows', /sv2-mg-evid/.test(labelOnly));
  const plain = P.writeupHtml(play({ flags: FL(PIN('quiet'), null) }), {});
  ok('no label, no quote: the card has none of the new bits', !/sv2-mg|Novig/.test(plain));
  const texts = [h, whyOnly, noGap, noNv, labelOnly, staleSentence, frozenSentence, stale0()].map(strip).join(' ') + ' ' + P.priceChips(play(base)).map((c) => c.text + ' ' + c.tip).join(' ') + ' ' + P.PRICE_WHY + ' ' + P.execLines({ exec: { novig: NOVIG(0.735) } }, 0.7223, { fresh: true }).join(' ');
  function stale0() { return P.writeupHtml(play(Object.assign({}, base, { exec: { novig: NOVIG(0.575, { since_min: 2272 }) } })), {}); }
  ok('the words Diamond, Odds Drop, lean and strong appear nowhere', !NOT_WORDS.test(texts) && !/strong/i.test(texts), texts.match(NOT_WORDS));
  ok('no em or en dash, no unfilled slot', !texts.includes(EM) && !texts.includes(EN) && !/[{}]|undefined|\bnull\b|NaN/.test(texts));
  ok('no book other than Novig, Pinnacle and DraftKings is named by the new text', !/Kalshi|BookMaker|Circa|Caesars|Fanatics/.test(texts));
  ok('Novig is never described as read at a time, and "still" never appears in the new copy', !/read at/i.test(texts) && !/Novig still/i.test(texts));
}

console.log('\n' + pass + ' pass, ' + fail + ' fail');
process.exit(fail ? 1 : 0);
