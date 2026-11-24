/* Unit tests for the Move grade label (rule mg-1) in sv2-sharps.js and the Move grade record in sv2-record.js.
   No dependencies: node sharp-money/sharps-v2/tests/sv2-movegrade.test.mjs. Every fixture is synthetic: no network, no _dev files. */
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
  for (const f of ['sv2-core.js', 'sv2-sharps.js', 'sv2-record.js']) vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), sandbox);
  return sandbox.module.exports;
}

let pass = 0, fail = 0;
function ok(name, cond, extra) { if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); } }
function eq(name, a, b) { ok(name, JSON.stringify(a) === JSON.stringify(b), { got: a, want: b }); }

const SV2 = load();
SV2.sizesOk = () => true;
const P = SV2.sharpsPage, R = SV2.rec;
const EM = String.fromCharCode(0x2014), EN = String.fromCharCode(0x2013);
/* the banned lists of the two old suites, minus the one word the user chose for the top label (it is checked apart, below) */
const BANNED = /\b(agree|agreement|proven|elite|lock|locks|locked|go|follow|lean|leans|hot|weak|confidence|guaranteed|edge|sharp pick|best bet|confirm|confirms|smart money|sharp action)\b/i;
const strip = (h) => h.replace(/<[^>]+>/g, ' ');

const mkp = (v2, o) => Object.assign({ game: { ev: 'e1', sport: 'nba', gst: NOW + 7200, cut: NOW + 6300, vault: { away: 'MEM', home: 'CHA', teams: { away: ['Memphis Grizzlies', 'Grizzlies'], home: ['Charlotte Hornets', 'Hornets'] } },
  markets: { spread: { v2: Object.assign({ side: 'Hornets' }, v2) } } }, g: 'spread', sf: { side: 'Hornets', line: -3.5, price: 0.525 }, key: 'e1|spread', sport: 'nba', units: 1, tier: 'mixed', cut: NOW + 6300, facts: { tiered: true } }, o || {});
const PIN = (state, pts, extra) => Object.assign({ state, pts, t_a: 1.5, from: 105, to: -129, line: -3.5, rows: 12 }, extra || {});
const LIN = (state, kind, extra) => Object.assign({ kind: kind || 'line', state, t_c: 2, pin: kind === 'price' ? { from: 105, to: -129 } : { from: 22, to: 19 }, books: 6, same_way: 4, by_book: {}, extreme: { book: 'BetMGM', value: 18.5 } }, extra || {});
const FL = (pin, line, extra) => Object.assign({ rule: 'v2f-2', span_min: 1290, window_min: 1440, pin, line, limit: null }, extra || {});
const CUT = { m_a: 0.5, t_a: 1.5, x_a: 2.0, m_c: 1.0, t_c: 2.0, x_c: 3.5 };
const MGB = (o) => Object.assign({ rule: 'mg-1', letter: null, against: false, basis: null, against_by: null, a: null, c: null, a_pts: null, c_pts: null, c_kind: null, c_same_way: null, c_books: null, cut: CUT, why: null, flags_why: null }, o);
const A_MARK = MGB({ letter: 'A', basis: 'a_mark', a: 'toward', a_pts: 2.31 });
const B_FIRED = MGB({ letter: 'B', basis: 'fired', a: 'toward', c: 'quiet', a_pts: 1.8 });
const B_C = MGB({ letter: 'B', basis: 'fired', a: 'quiet', c: 'toward', a_pts: 0.2, c_pts: 2.5, c_kind: 'line', c_same_way: 4, c_books: 6 });
const A_C = MGB({ letter: 'A', basis: 'c_mark', a: 'quiet', c: 'toward', a_pts: 0.2, c_pts: 3.5, c_kind: 'line', c_same_way: 4, c_books: 6 });
const C_DRIFT = MGB({ letter: 'C', basis: 'drift', a: 'quiet', c: 'quiet', a_pts: 0.7, c_pts: 1.0, c_kind: 'line' });
const D_FLAT = MGB({ letter: 'D', basis: 'flat', a: 'quiet', c: 'quiet', a_pts: 0.1, c_pts: 0 });
const AGAINST = MGB({ against: true, basis: 'against', against_by: ['a'], a: 'away', a_pts: -2.1 });
const NOGRADE = (why) => MGB({ against: null, why, cut: null });
const lim = { from: 3700, to: 5300, rows: 6 };
const withGrade = (g, flags) => mkp({ move_grade: g, flags: flags === undefined ? FL(PIN('toward', 2.3), LIN('toward'), { limit: lim }) : flags });

console.log('the label and its chip');
{
  const w = (g) => (P.mgOf(withGrade(g)) || {}).kind;
  eq('A, B and C are letters; against is the marker; D, no grade and null show nothing', [w(A_MARK), w(B_FIRED), w(C_DRIFT), w(AGAINST), w(D_FLAT), w(NOGRADE('no_flags')), w(null)], ['letter', 'letter', 'letter', 'against', undefined, undefined, undefined]);
  eq('an absent block shows nothing', P.mgOf(mkp({})), null);
  eq('garbage shows nothing', [P.mgOf(withGrade('x')), P.mgOf(withGrade(7)), P.mgOf(withGrade([1])), P.mgOf(withGrade({ letter: 'Z' })), P.mgOf(withGrade({ letter: null, against: 1 })), P.mgOf(withGrade({ letter: null, against: 'yes' }))], [null, null, null, null, null, null]);
  const chip = (g) => P.mgChipHtml(withGrade(g));
  ok('A is STRONG with three bars', /data-mg="a"/.test(chip(A_MARK)) && />STRONG</.test(chip(A_MARK)) && (chip(A_MARK).match(/<i class="on">/g) || []).length === 3);
  ok('B is NOTABLE with two bars', />NOTABLE</.test(chip(B_FIRED)) && (chip(B_FIRED).match(/<i class="on">/g) || []).length === 2);
  ok('C is ROUTINE with one bar', />ROUTINE</.test(chip(C_DRIFT)) && (chip(C_DRIFT).match(/<i class="on">/g) || []).length === 1);
  ok('against is the neutral sentence with the away arrow', /Market moved the other way/.test(chip(AGAINST)) && /sv2-fl-i/.test(chip(AGAINST)) && !/<i class="on">/.test(chip(AGAINST)));
  eq('D, no grade and an absent block draw no chip at all', [chip(D_FLAT), chip(NOGRADE('flags_unreadable')), chip(null), P.mgChipHtml(mkp({}))], ['', '', '', '']);
  ok('the letter is not in the label', ![A_MARK, B_FIRED, C_DRIFT, AGAINST].some((g) => /\b(Move grade [ABCD]|grade [ABCD]\b)/.test(strip(chip(g)))));
  ok('the bars are decoration: aria-hidden, and the words carry the meaning for a screen reader', /class="sv2-mg-bars" aria-hidden="true"/.test(chip(A_MARK)) && /class="sv2-sr">\. Move: STRONG\./.test(chip(A_MARK)));
  ok('title and screen reader text say context only, never a bet signal', /Context only, not a bet signal\./.test(chip(B_FIRED)) && /title="[^"]*Context only, not a bet signal/.test(chip(B_FIRED)));
  ok('never a tier class or tier colour on the label', ![A_MARK, B_FIRED, C_DRIFT, AGAINST].some((g) => /sv2-tier|data-tier|--sv2-(gold|violet|price|caution|win|loss|follow)|sv2-(win|loss|chip--)/.test(chip(g))));
  eq('aria text for the row', [P.mgAria(withGrade(A_MARK)), P.mgAria(withGrade(AGAINST)), P.mgAria(withGrade(D_FLAT)), P.mgAria(mkp({}))], [', move STRONG', ', the market moved the other way', '', '']);
  const all = [A_MARK, B_FIRED, C_DRIFT, AGAINST].map((g) => strip(chip(g)) + ' ' + chip(g).replace(/<[^>]+>/g, '|')).join(' ');
  ok('no banned word, no dash, no unfilled slot in any label', !BANNED.test(all) && !all.includes(EM) && !all.includes(EN) && !/[{}]|undefined|null|NaN/.test(all), all);
  ok('STRONG appears only on the top label (the word and its screen reader copy)', (strip(chip(A_MARK)).match(/strong/gi) || []).length === 2 && [B_FIRED, C_DRIFT, AGAINST].every((g) => !/strong/i.test(chip(g))));
  ok('the core copy deck still holds none of the label words', !/strong|notable|routine/i.test(JSON.stringify(SV2.copy, (k, v) => (k === 'forbidden' ? undefined : typeof v === 'function' ? v('x', 7) : v))));
}

console.log('the badge at the top of the flags area, and the one sentence');
{
  const h = P.writeupHtml(withGrade(A_MARK), {});
  const hl = h.slice(h.indexOf('sv2-wu-hl'));
  ok('the badge is the first thing in the line-went block, before the flag numbers and chips', hl.indexOf('sv2-mg-badge') > 0 && hl.indexOf('sv2-mg-badge') < hl.indexOf('sv2-wu-big') && hl.indexOf('sv2-mg-badge') < hl.indexOf('data-flag="pin"'));
  ok('the badge reads Move and the word', />Move<\/span>.*>STRONG</.test(hl));
  ok('the sentence uses only stored numbers: price from and to, limit from and to', /Pinnacle moved this side from \+105 to -129 while its limit rose from \$3\.7K to \$5\.3K\./.test(strip(h)));
  const s = (flags, g) => P.mgSentence(withGrade(g || A_MARK, flags));
  eq('a falling limit says fell', s(FL(PIN('toward', 2.3), null, { limit: { from: 5300, to: 3700, rows: 3 } })), 'Pinnacle moved this side from +105 to -129 while its limit fell from $5.3K to $3.7K.');
  eq('no limit stored: the sentence stops after the move', s(FL(PIN('toward', 2.3), null)), 'Pinnacle moved this side from +105 to -129.');
  eq('a flat or one-reading limit adds no clause', s(FL(PIN('toward', 2.3), null, { limit: { from: 3000, to: 3000, rows: 1 } })), 'Pinnacle moved this side from +105 to -129.');
  eq('a limit with a missing number adds no clause', s(FL(PIN('toward', 2.3), null, { limit: { from: null, to: 5000, rows: 2 } })), 'Pinnacle moved this side from +105 to -129.');
  eq('no Pinnacle price: the line move at Pinnacle is told instead', s(FL(null, LIN('toward'), { limit: lim }), B_C), 'Pinnacle moved the number on this side from +22 to +19 while its limit rose from $3.7K to $5.3K.');
  eq('no numbers at all: no sentence, never invented', [s(FL(null, null), A_MARK), s(null, A_MARK), s(FL({ state: 'toward', pts: 2 }, null), A_MARK)], [null, null, null]);
  eq('D and no grade have no sentence', [s(FL(PIN('quiet', 0.1), null), D_FLAT), s(FL(PIN('quiet', 0.1), null), NOGRADE('no_flags'))], [null, null]);
  ok('the sentence is told once, in the flags area, not in the takeaway', (strip(h).match(/Pinnacle moved this side from/g) || []).length === 1);
  const noFlagsH = P.writeupHtml(withGrade(A_MARK, null), {});
  ok('with the flags dropped by the size gate the badge still shows and nothing breaks', /sv2-mg-badge/.test(noFlagsH) && !/Pinnacle moved this side from/.test(strip(noFlagsH)) && /The takeaway/.test(noFlagsH));
}

console.log('how this label was earned (inside the takeaway)');
{
  const words = (p) => P.sideLabelWords(p);
  const why = (g, flags, o) => { const p = withGrade(g, flags); if (o) Object.assign(p, o); return P.mgWhy(p, words(p)); };
  const f = FL(PIN('toward', 2.31), LIN('quiet'), { limit: lim });
  eq('A by the price mark', why(A_MARK, f), 'STRONG move: Pinnacle\'s price for Hornets went +105 to -129 in the last 22 hours, 2.31 points of no-vig price, past the top mark of 2.');
  eq('A by the line mark', why(A_C, FL(PIN('quiet', 0.2), LIN('toward'))), 'STRONG move: The market moved the number toward Hornets, +22 to +19 at Pinnacle (3.5 points, top mark 3.5), 4 of 6 books the same way.');
  eq('B by Flag A, and the number moved the same way when Flag C agrees', why(MGB({ letter: 'B', basis: 'fired', a: 'toward', c: 'toward', a_pts: 1.8 }), FL(PIN('toward', 1.8), LIN('toward'))), 'NOTABLE move: Pinnacle\'s price for Hornets went +105 to -129, 1.8 points (the flag mark is 1.5, the top mark 2). The market\'s number moved the same way.');
  eq('B by Flag A alone', why(B_FIRED, FL(PIN('toward', 1.8), LIN('quiet'))), 'NOTABLE move: Pinnacle\'s price for Hornets went +105 to -129, 1.8 points (the flag mark is 1.5, the top mark 2).');
  eq('B by Flag C on a line', why(B_C, FL(PIN('quiet', 0.2), LIN('toward'))), 'NOTABLE move: The market moved the number toward Hornets, +22 to +19 at Pinnacle, 4 of 6 books the same way (top mark 3.5 points).');
  eq('B by Flag C on a moneyline', why(MGB({ letter: 'B', basis: 'fired', a: 'quiet', c: 'toward', c_kind: 'price', c_same_way: 3, c_books: 5 }), FL(PIN('quiet', 0.2), LIN('toward', 'price'))), 'NOTABLE move: The books moved the price toward Hornets, 3 of 5 books past the flag mark.');
  eq('C by drift, price and line', why(C_DRIFT, FL(PIN('quiet', 0.7), LIN('quiet'))), 'ROUTINE move: No flag fired; Pinnacle\'s price for Hornets drifted 0.7 points toward it and its line 1 points toward it (typical-day mark 0.5 / 1, flag mark 1.5 / 2).');
  eq('C by price drift alone', why(MGB({ letter: 'C', basis: 'drift', a: 'quiet', a_pts: 0.7 }), FL(PIN('quiet', 0.7), null)), 'ROUTINE move: No flag fired; Pinnacle\'s price for Hornets drifted 0.7 points toward it (typical-day mark 0.5 / 1, flag mark 1.5 / 2).');
  ok('against: the existing flag sentence with its numbers, then that it is shown instead of a label', /^Market moved the other way: Pinnacle \+105 to -129 at -3\.5, away from this side\. A move against the play is shown instead of a label\./.test(why(AGAINST, FL(PIN('away', -2.1), LIN('quiet')))), why(AGAINST, FL(PIN('away', -2.1), LIN('quiet'))));
  eq('D, no grade and an unknown basis give nothing', [why(D_FLAT, f), why(NOGRADE('no_flags'), f), why(MGB({ letter: 'B', basis: 'mystery' }), f), why(null, f)], [null, null, null, null]);
  eq('a placeholder with no stored number forces the template that does not print it', why(MGB({ letter: 'A', basis: 'a_mark', a: 'toward', a_pts: null, cut: {} }), FL({ state: 'toward' }, null)), 'STRONG move: Pinnacle\'s price for Hornets moved in the last 22 hours.');
  const p = withGrade(A_MARK, f);
  const h = P.writeupHtml(p, {});
  ok('the line sits in the takeaway card, after the takeaway text, with its heading', /class="sv2-wu-tk">[^<]*<\/p><p class="sv2-mg-why"><b>How this label was earned\.<\/b> STRONG move/.test(h));
  ok('the takeaway text itself is unchanged and its closer is still its last sentence', /These are descriptions of what the market did\. Past moves like these have not paid off in Vault&#39;s records, so this is context, not a reason to bet\.<\/p><p class="sv2-mg-why">/.test(h));
  const texts = [A_MARK, B_FIRED, B_C, A_C, C_DRIFT, AGAINST].map((g) => strip(P.writeupHtml(withGrade(g, FL(PIN(g.a || 'quiet', g.a_pts == null ? 0 : g.a_pts), LIN(g.c || 'quiet'), { limit: lim })), {}))).join(' ');
  ok('no banned word, dash or unfilled slot in any card', !BANNED.test(texts) && !texts.includes(EM) && !texts.includes(EN) && !/[{}]|undefined|NaN|\bnull\b/.test(texts));
  ok('the card never says a play will win and never says Sharp grade', !/Sharp grade|grade A|A play\b|will win|predict/i.test(texts));
  ok('only the allowed book names appear in the label text', !/Novig|Kalshi|BookMaker|Circa|Caesars|Fanatics|Diamond|Odds Drop/.test(texts));
}

console.log('the table row');
{
  const FACTS = { tiered: true, side: 'Hornets', a1: { on: false, n: 0 }, a2: { on: false, n: 0 }, a3: { on: false }, a4: { on: false, pts: null }, b1: { on: false, n: 0 }, b2: { on: false }, b3: { on: false }, b4: { on: false }, pts: null, proven: 0 };
  const row = (g) => P.rowHtml(Object.assign(withGrade(g), { facts: FACTS }), { open: {}, more: {} }, {});
  const tier = (h) => (/<td class="sv2-tb-c c-tier">([\s\S]*?)<\/td>/.exec(h) || [])[1] || '';
  ok('the chip sits in the Tier cell, after the tier chip', /^<span class="sv2-tier [^>]*>[\s\S]*<\/span><span class="sv2-mg sv2-mg--a"/.test(tier(row(A_MARK))), tier(row(A_MARK)).slice(0, 120));
  ok('no new column: the row has the same eleven cells with and without a grade', (row(A_MARK).match(/<td class="sv2-tb-c /g) || []).length === (row(null).match(/<td class="sv2-tb-c /g) || []).length && (row(A_MARK).match(/<td class="sv2-tb-c /g) || []).length === 11);
  ok('D, no grade and absent: the Tier cell is the tier chip alone', [D_FLAT, NOGRADE('flags_unreadable'), null].every((g) => !/sv2-mg/.test(tier(row(g)))));
  ok('the row keeps data-tier and the tier word, and the aria label adds the move', /data-tier="mixed"/.test(row(A_MARK)) && /Mixed, move STRONG\./.test(row(A_MARK)) && !/move/.test((/aria-label="([^"]*)" data-sp-row/.exec(row(null)) || [])[1]));
  ok('the against marker in the row is the neutral sentence', /Market moved the other way/.test(tier(row(AGAINST))));
  const th = P.theadHtml(null);
  ok('the header is Tier and move and still sorts by tier', /<th scope="col" class="c-tier is-sort"[^>]*><button[^>]*data-sp-sort="tier"[^>]*>Tier and move/.test(th));
}

console.log('everything else in the dropdown is still there');
{
  const f = FL(PIN('toward', 2.3), LIN('toward'), { limit: lim });
  const base = P.writeupHtml(mkp({ flags: f }), { share: { nba: 0.99 } });
  const withMg = P.writeupHtml(mkp({ flags: f, move_grade: A_MARK }), { share: { nba: 0.99 } });
  const stripMg = withMg.replace(/<p class="sv2-mg-badge-row">[\s\S]*?<\/p>/, '').replace(/<p class="sv2-wu-fact sv2-mg-say">[\s\S]*?<\/p>/, '').replace(/<p class="sv2-mg-why">[\s\S]*?<\/p>/, '');
  ok('with the three additions removed the card is byte for byte the card without a grade', stripMg === base, [stripMg.length, base.length]);
  ok('flag chips, the price move numbers and the limit line are all still shown', /data-flag="pin"/.test(withMg) && /data-flag="line"/.test(withMg) && /sv2-wu-big/.test(withMg) && /Pinnacle limit \$3\.7K to \$5\.3K in the last 22 hours\./.test(withMg));
  eq('the table header says Tier and move and the sort is still the tier sort', [P.SORTS.tier.label, P.SORT_ORDER.indexOf('tier') >= 0], ['Tier', true]);
  ok('no grade: the card is exactly the old card', P.writeupHtml(mkp({ flags: f, move_grade: null }), { share: { nba: 0.99 } }) === base && P.writeupHtml(mkp({ flags: f, move_grade: D_FLAT }), { share: { nba: 0.99 } }) === base);
}

console.log('the record by Move grade');
{
  const cell = (w, l, p, units) => ({ w, l, p, n: w + l + p, units, roi: w + l + p ? units / (w + l + p) : null });
  const sl = (o) => ({ all: o, in_sample: o, forward: cell(0, 0, 0, 0) });
  const sport = (k) => ({ a: sl(cell(4, 3, 0, 0.22 * k)), b: sl(cell(7, 2, 0, 2.91 * k)), c: sl(cell(10, 4, 0, 7.58)), d: sl(cell(28, 21, 0, -3.37)), against: sl(cell(11, 8, 0, 1.32)), unreadable: sl(cell(25, 21, 0, 3.32)) });
  const file = { built: NOW, mg_rule: 'mg-1', sports: { nba: sport(1), nfl: sport(1), cbb: sport(1), cfb: sport(1) } };
  ok('a file with the rule and a slice object is usable', R.mgFileOk(file) && !R.mgFileOk({}) && !R.mgFileOk(null) && !R.mgFileOk({ sports: {} }) && !R.mgFileOk({ mg_rule: 'mg-1' }) && !R.mgFileOk('x'));
  const t = R.mgTable(file, 'nba', 'in_sample');
  eq('six rows in order', t.rows.map((r) => r.k), ['a', 'b', 'c', 'd', 'against', 'unreadable']);
  eq('labels and what the page shows', t.rows.map((r) => [r.label, r.shown]), [['A', 'Shown as STRONG'], ['B', 'Shown as NOTABLE'], ['C', 'Shown as ROUTINE'], ['D', 'No label shown'], ['Moved against', 'Shown as "Market moved the other way"'], ['No grade', 'No grade, nothing shown']]);
  eq('W-L, units and n come from the stored cell', [R.fmtWl(t.rows[0].t), t.rows[0].t.n, t.rows[0].t.units], ['4-3', 7, 0.22]);
  ok('an improving row under 30 is flagged watch with the small sample', t.rows[0].flag.watch && t.rows[0].flag.small && t.rows[0].flag.tiny && t.rows[0].flag.n === 7);
  ok('a losing row is not flagged watch', !t.rows[3].flag.watch);
  eq('the total is the sum of the six rows', [t.total.n, t.total.w, t.total.l], [7 + 9 + 14 + 49 + 19 + 46, 4 + 7 + 10 + 28 + 11 + 25, 3 + 2 + 4 + 21 + 8 + 21]);
  const fwd = R.mgTable(file, 'nba', 'forward');
  eq('forward is zero, a null roi is a dash, never 0%', [fwd.total.n, fwd.rows[0].t.roi, R.fmtRoi(fwd.rows[0].t), R.fmtUnits(fwd.rows[0].t)], [0, null, '-', '0u']);
  eq('an unknown bucket reads as in-sample', R.mgTable(file, 'nba', 'since_nov16').bucket, 'in_sample');
  const all = R.mgTable(file, 'all', 'in_sample');
  eq('All pools NBA, NFL and CBB only when the file has no pooled set (CFB is not pooled)', all.rows[0].t.n, 21);
  const withAll = Object.assign({}, file, { all: { a: sl(cell(1, 0, 0, 1)), b: sl(cell(0, 0, 0, 0)), c: sl(cell(0, 0, 0, 0)), d: sl(cell(0, 0, 0, 0)), against: sl(cell(0, 0, 0, 0)), unreadable: sl(cell(0, 0, 0, 0)) } });
  eq('the file\'s own pooled set wins', R.mgTable(withAll, 'all', 'in_sample').rows[0].t.n, 1);
  eq('CFB reads its own slices', R.mgTable(file, 'cfb', 'in_sample').rows[0].t.n, 7);
  eq('a sport not in the file has no table', [R.mgTable(file, 'xfl', 'in_sample'), R.mgTable({ built: 1, mg_rule: 'mg-1', sports: { nba: sport(1) } }, 'nfl', 'in_sample')], [null, null]);
  eq('empty slices: zeros, not errors', R.mgTable({ mg_rule: 'mg-1', sports: { nba: {} } }, 'nba', 'in_sample').total.n, 0);
  ok('the notes say in-sample is history, not a test, and forward starts at zero', /written after these results\. Read it as history, not a test\./.test(R.MG_NOTE.in_sample) && /Starts at zero\./.test(R.MG_NOTE.forward));
  const texts = JSON.stringify([R.MG_LABEL, R.MG_SHOWN, R.MG_NOTE]);
  ok('record copy: no banned word, no dash', !BANNED.test(texts) && !texts.includes(EM) && !texts.includes(EN));
}

console.log('\n' + pass + ' pass, ' + fail + ' fail');
process.exit(fail ? 1 : 0);
