/* Unit tests for the alert card at the top of the Sharps dropdown and the spread fact line of a moneyline play (sv2-sharps.js alertCardHtml, spreadOf,
   shareDataOf; sv2-share.js). No dependencies: node sharp-money/sharps-v2/tests/sv2-card.test.mjs. Synthetic fixtures only (tests/sv2-card-fixtures.mjs). */
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { NOW, PIN, LIN, FL, GRADE_A, GRADE_B, GRADE_AGAINST, NOVIG, SPREAD, SIDE, play, FULL, goldenPlays } from './sv2-card-fixtures.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');

function load() {
  const sb = { console, Intl, Date, Math, JSON, Object, Array, String, Number, RegExp, Promise, Uint8Array, setTimeout, clearTimeout, setInterval, clearInterval, module: { exports: {} },
    location: { hostname: 'localhost', search: '?now=' + NOW, hash: '' }, localStorage: { getItem: () => null, setItem() {} } };
  sb.window = sb; vm.createContext(sb);
  for (const f of ['sv2-core.js', 'sv2-share.js', 'sv2-sharps.js']) vm.runInContext(fs.readFileSync(path.join(ROOT, f), 'utf8'), sb);
  return sb.module.exports;
}
let pass = 0, fail = 0;
function ok(name, cond, extra) { if (cond) { pass++; console.log('  ok   ' + name); } else { fail++; console.log('  FAIL ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); } }
function eq(name, a, b) { ok(name, JSON.stringify(a) === JSON.stringify(b), { got: a, want: b }); }

const SV2 = load();
SV2.sizesOk = () => true;
const P = SV2.sharpsPage, SH = SV2.share;
const EM = String.fromCharCode(0x2014), EN = String.fromCharCode(0x2013);
const FORBID = SV2.copy.forbidden.concat(['edge']);
const strip = (h) => h.replace(/<[^>]+>/g, ' ').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ');
const rowKeys = (h) => (h.match(/data-ac="([a-z]+)"/g) || []).map((m) => m.slice(9, -1));
const rowText = (h, k) => strip((new RegExp('data-ac="' + k + '"[\\s\\S]*?</div>').exec(h) || [''])[0]);
const ml = (extra, o) => play(Object.assign(FULL(), { flags: FL(PIN('toward'), LIN('toward', 'price')) }, extra || {}), Object.assign({ g: 'ml', tier: 'clear' }, o || {}));
const withSpread = (c, o) => ml({ spread_ctx: c }, o);

console.log('no tile row, the card replaces it');
{
  const h = P.writeupHtml(withSpread(SPREAD()), { share: { nba: 0.99 } });
  ok('no tile row, no tile, no takeaway block, no old header', !/sv2-wu-tile|sv2-wu-take|sv2-wu-tiles|The takeaway|THE PLAY|The price<|Line and fair/.test(h) && !/sv2-wu-ey/.test(h));
  ok('the card is one article with the top row first, then the title, the sentence, the chips, the rows', /<article class="sv2-card sv2-acc-ink sv2-wu sv2-ac"[^>]*><div class="sv2-ac-top">/.test(h) && h.indexOf('sv2-ac-top') < h.indexOf('<h3') && h.indexOf('<h3') < h.indexOf('sv2-ac-say') && h.indexOf('sv2-ac-say') < h.indexOf('data-flag="pin"') && h.indexOf('data-flag="pin"') < h.indexOf('sv2-ac-rows'));
  ok('the numbered sections, the Share button and the footer are still below the card', h.indexOf('sv2-ac-main') < h.indexOf('Who is on each side') && h.indexOf('Who is on each side') < h.indexOf('Where the line went') && h.indexOf('Where the line went') < h.indexOf('data-sp-share') && h.indexOf('data-sp-share') < h.indexOf('sv2-wu-ft'));
  ok('the sections stay collapsible details elements', (h.match(/<details class="sv2-wu-sec"/g) || []).length === 2 && /sv2-wu-sb/.test(h));
}

console.log('every fact the old tiles and takeaway showed is in the card');
{
  const p = withSpread(SPREAD());
  p.game.markets.ml.v2.vs_fair = { pts: 0.4, fair: 0.521, line: null, why: null };
  const h = P.writeupHtml(p, { share: { nba: 0.99 } }), t = strip(h), top = strip(h.slice(h.indexOf('sv2-ac-top'), h.indexOf('sv2-ac-main')));
  ok('the title is the play (the side and ML), with the screen reader prefix "The read on"', /<h3[^>]*><span class="sv2-sr">The read on <\/span>Hornets ML<\/h3>/.test(h));
  ok('the date pill is kept', /<span class="sv2-wu-date">[A-Z]{3} [A-Z]{3} \d+<\/span>/.test(h));
  ok('the game and the market, then the tier chip with its word and pips', /sv2-ac-sub"><span>MEM at CHA, ML<\/span><span class="sv2-tier/.test(h) && /Clear/.test(strip(/sv2-ac-sub[\s\S]*?<\/p>/.exec(h)[0])));
  ok('top row: Price move, the sport, the market word, the Move label with its bars and word', /Price move/.test(top) && /NBA/.test(top) && /Moneyline/.test(top) && /Move\s+LARGE/.test(top) && /sv2-mg-bars/.test(h.slice(h.indexOf('sv2-ac-top'), h.indexOf('sv2-ac-main'))));
  ok('status: the freeze time in Central and the size pill with its untested rule label', /Freezes \d+:\d\d [AP]M CT/.test(rowText(h, 'status')) && /1u/.test(rowText(h, 'status')) && /untested rule/.test(rowText(h, 'status')), rowText(h, 'status'));
  ok('price: cents, American and the best US book at its name', /52\.5c/.test(rowText(h, 'price')) && /-?\d+ in American/.test(rowText(h, 'price')) && /Best US book -102 at BetMGM/.test(rowText(h, 'price')), rowText(h, 'price'));
  ok('Novig in cents and American with its age, and the gap before fees', /51c \(-?\d+\)/.test(rowText(h, 'novig')) && /unchanged since .* CT \(14 min old\)/.test(rowText(h, 'novig')) && /before fees/.test(rowText(h, 'novig')), rowText(h, 'novig'));
  ok('fair and how far the price is from it', /Fair 52\.1c/.test(rowText(h, 'fair')) && /0\.4 pts better than fair/.test(rowText(h, 'fair')), rowText(h, 'fair'));
  ok('Pinnacle price from and to, and the limit from and to as a fact', /\+105.*-129/.test(rowText(h, 'pin')) && /\$1\.1K.*\$1\.45K/.test(rowText(h, 'limit')) && /fact only/.test(rowText(h, 'limit')));
  ok('the takeaway: the market sentence, the money sentence, and the closer as the note', /Pinnacle's price and the market's price both moved toward Hornets/.test(t) && /More of the tracked Polymarket money is on Memphis Grizzlies|More of the tracked Polymarket money is on/.test(t) && /Context only\. Not a bet signal\. These are descriptions of what the market did\. Past moves like these have not paid off in Vault's records, so this is context, not a reason to bet\./.test(t));
  ok('the move sentence with the limit clause and Novig sits in the sentence slot', /Pinnacle moved this side from \+105 to -129 while its limit rose from \$1\.1K to \$1\.45K\. Novig shows/.test(strip(/sv2-ac-say[\s\S]*?<\/p>/.exec(h)[0])));
  ok('the flag chips moved into the card, not repeated in the section', /data-flag="pin"/.test(h) && (h.match(/data-flag="pin"/g) || []).length === 1 && h.indexOf('data-flag="pin"') < h.indexOf('<details'));
  ok('the Share button is still there with its status line', /data-sp-share="e1\|ml"/.test(h) && /sv2-wu-sharest/.test(h));
  ok('section 2 still has the Pinnacle price, the Books price and the limit line with the schedule share', /Pinnacle Hornets price/.test(t) && /Books' price/.test(t) && /Pinnacle limit \$1\.1K to \$1\.45K in the last 22 hours\. Pinnacle raises limits toward start/.test(t));
}

console.log('the toggle: why this label');
{
  const p = withSpread(SPREAD());
  const h = P.writeupHtml(p, {}), open = P.writeupHtml(p, { whyOpen: true });
  ok('closed by default: aria-expanded false, no data-open, the panel is still in the page behind the expander', /aria-expanded="false"[^>]*data-sp-why="e1\|ml"/.test(h) && !/class="sv2-x"[^>]*data-open/.test(h) && /<div class="sv2-x" id="sv2-wu-e1-ml-why">/.test(h));
  ok('open when asked', /aria-expanded="true"/.test(open) && /class="sv2-x" id="sv2-wu-e1-ml-why" data-open/.test(open));
  ok('the button names the controlled panel and has the press primitive', /aria-controls="sv2-wu-e1-ml-why"/.test(h) && /class="sv2-ac-why sv2-press sv2-press-btn"/.test(h) && /data-fid="why:e1\|ml"/.test(h));
  const panel = h.slice(h.indexOf('sv2-ac-whyp'), h.indexOf('</div></div></div>', h.indexOf('sv2-ac-whyp')));
  ok('the panel holds How this label was earned and the price caution, and nothing else', /How this label was earned\./.test(panel) && /A price that looks better than Pinnacle&#39;s at one moment has not paid/.test(panel) && /The label does not predict results\./.test(panel));
  ok('those two lines are nowhere else in the card', (h.match(/How this label was earned/g) || []).length === 1 && (h.match(/sv2-mg-evid/g) || []).length === 1);
  ok('the Move label stays visible outside the toggle', h.indexOf('sv2-mg-badge') < h.indexOf('sv2-ac-whywrap'));
  const noLabelNovig = P.writeupHtml(ml({ move_grade: null }), {});
  ok('no label but a Novig price: the button reads About this price and holds only the caution', /About this price/.test(noLabelNovig) && !/How this label was earned/.test(noLabelNovig) && /sv2-mg-evid/.test(noLabelNovig));
  const plain = P.writeupHtml(play({ flags: FL(PIN('quiet'), LIN('quiet')) }, { g: 'ml' }), {});
  ok('no label and no Novig: no toggle at all', !/data-sp-why|sv2-ac-whywrap/.test(plain));
  const against = P.writeupHtml(play({ flags: FL(PIN('away'), LIN('quiet')), move_grade: GRADE_AGAINST }, { g: 'ml' }), {});
  ok('a move against the play: the neutral badge shows in the top row and the toggle explains it', /Market moved the other way/.test(against.slice(0, against.indexOf('sv2-ac-main'))) && /Why this label/.test(against));
}

console.log('the spread row of a moneyline play');
{
  const h = P.writeupHtml(withSpread(SPREAD()), {});
  eq('rows in order on a moneyline play with a spread', rowKeys(h), ['pin', 'limit', 'spread', 'novig', 'price', 'fair', 'status']);
  const r = rowText(h, 'spread');
  ok('the row shows Pinnacle\'s spread for this side from and to and the book count toward the side', /Spread/.test(r) && /-3\.5/.test(r) && /-5\.5/.test(r) && /5 of 6 books moved toward Hornets/.test(r), r);
  ok('from and to are read out for a screen reader', /from <\/span>-3\.5.*to <\/span>-5\.5/.test(/data-ac="spread"[\s\S]*?<\/div>/.exec(h)[0].replace(/<svg[\s\S]*?<\/svg>/g, '')));
  const row = (c, o) => P.spreadOf(withSpread(c, o));
  eq('away from', row(SPREAD({ toward: 0, away: 4 })).note, '4 of 6 books moved away from Hornets');
  eq('a split', row(SPREAD({ toward: 3, away: 1 })).note, '3 toward and 1 away from Hornets, of 6 books');
  eq('one book', row(SPREAD({ books: 1, toward: 1, away: 0 })).note, '1 of 1 book moved toward Hornets');
  const still = P.writeupHtml(withSpread(SPREAD({ pin: [-3.5, -3.5], toward: 0, away: 0 })), {});
  ok('has not moved: the one number and the plain words, no arrow', /has not moved \(6 books read\)/.test(rowText(still, 'spread')) && !/sv2-wu-arr/.test(/data-ac="spread"[\s\S]*?<\/div>/.exec(still)[0]) && /-3\.5/.test(rowText(still, 'spread')));
  eq('the sentence helper for the share image', [row(SPREAD()).text, row(SPREAD({ pin: [-3.5, -3.5], toward: 0, away: 0 })).text],
    ['Spread at Pinnacle went -3.5 to -5.5, 5 of 6 books moved toward Hornets.', 'Spread at Pinnacle -3.5, has not moved (6 books read).']);
  eq('a positive line keeps its plus sign', P.spreadOf(withSpread(SPREAD({ pin: [22, 19] }))).from, '+22');
  eq('a pick\'em line prints 0 without a minus', P.spreadOf(withSpread(SPREAD({ pin: [0, -1.5] }))).from, '0');
  const bad = [undefined, null, {}, 'x', [], SPREAD({ pin: null }), SPREAD({ pin: [-3.5] }), SPREAD({ pin: ['-3.5', -5.5] }), SPREAD({ pin: [null, -5.5] }), SPREAD({ books: 0 }), SPREAD({ books: null }), SPREAD({ toward: null }), SPREAD({ away: 'x' })];
  ok('nothing is drawn for an absent key, a stored null, or a malformed one (' + bad.length + ' cases)', bad.every((c) => P.spreadOf(withSpread(c)) === null && rowKeys(P.writeupHtml(withSpread(c), {})).indexOf('spread') < 0));
  ok('the card builds and every other row is unchanged without the spread row', JSON.stringify(rowKeys(P.writeupHtml(withSpread(undefined), {}))) === JSON.stringify(['pin', 'limit', 'novig', 'price', 'fair', 'status']));
  const sp = play(Object.assign(FULL(), { spread_ctx: SPREAD() }), { g: 'spread' }), tot = play(Object.assign(FULL(), { spread_ctx: SPREAD() }), { g: 'total' });
  ok('a spread play and a total play never get the row, even with the key stored', P.spreadOf(sp) === null && P.spreadOf(tot) === null && rowKeys(P.writeupHtml(sp, {})).indexOf('spread') < 0 && rowKeys(P.writeupHtml(tot, {})).indexOf('spread') < 0);
  ok('the spread row is not in the grade sentence, the takeaway or the chips', !/Spread/.test(strip(/sv2-ac-say[\s\S]*?<\/p>/.exec(h)[0])) && !/data-flag="spread"/.test(h) && !/spread/i.test(strip(/sv2-ac-tk[\s\S]*?<\/p>/.exec(h) ? /sv2-ac-tk[\s\S]*?<\/p>/.exec(h)[0] : '')));
  ok('the grade and the tier do not read it: the Move label and tier are the same with and without the key', P.mgBadgeHtml(withSpread(SPREAD())) === P.mgBadgeHtml(withSpread(undefined)) && P.mgSentence(withSpread(SPREAD())) === P.mgSentence(withSpread(undefined)) && P.writeupHtml(withSpread(SPREAD()), {}).match(/class="sv2-tier [^"]*"/)[0] === P.writeupHtml(withSpread(undefined), {}).match(/class="sv2-tier [^"]*"/)[0]);
}

console.log('share data: unchanged for every existing play, the spread line added only where there is one');
{
  const gold = JSON.parse(fs.readFileSync(path.join(HERE, 'fixtures', 'sv2-share-data-golden.json'), 'utf8'));
  const plays = goldenPlays(), keys = Object.keys(plays);
  const bytes = (k) => JSON.stringify(P.shareDataOf(plays[k], { url: 'vaultfantasy.com/sharp-money', nowT: NOW }));
  ok('every play in the golden file (built by the previous build) gives byte-identical share data (' + keys.length + ' plays)', keys.every((k) => bytes(k) === JSON.stringify(gold[k])), keys.filter((k) => bytes(k) !== JSON.stringify(gold[k])));
  const a = withSpread(SPREAD()), b = withSpread(undefined);
  const da = P.shareDataOf(a, { url: 'u', nowT: NOW }), db = P.shareDataOf(b, { url: 'u', nowT: NOW });
  eq('the moneyline spread line is added under moves.spread', da.moves.spread, 'Spread at Pinnacle went -3.5 to -5.5, 5 of 6 books moved toward Hornets.');
  const da2 = JSON.parse(JSON.stringify(da)); delete da2.moves.spread;
  eq('and nothing else changes', da2, db);
  eq('a spread play with the key stored has no spread line', P.shareDataOf(play(Object.assign(FULL(), { spread_ctx: SPREAD() }), { g: 'spread' }), { url: 'u', nowT: NOW }).moves.spread, undefined);
  eq('the title and file name are unchanged', [da.title, da.file], ['The read on Hornets', 'sharp-money-nba-hornets-ml.png']);
}

console.log('share image: the spread line follows the flag sentences in the drop order');
{
  const px = (font) => parseFloat(/(\d+(?:\.\d+)?)px/.exec(font)[1]), measure = (font, s) => String(s).length * px(font) * 0.52;
  const d = P.shareDataOf(withSpread(SPREAD()), { url: 'vaultfantasy.com/sharp-money', nowT: NOW });
  const r = SH.buildOps(d, (font, s) => String(s).length * px(font) * 0.4), tx = r.ops.filter((o) => o.t === 'text').map((o) => o.s).join('\n');
  ok('drawn with the flag sentences', /Spread at Pinnacle went -3\.5 to -5\.5/.test(tx) && /5 of 6 books moved toward Hornets/.test(tx), tx.split('\n').filter((s) => /Spread/.test(s)));
  const d0 = P.shareDataOf(withSpread(undefined), { url: 'vaultfantasy.com/sharp-money', nowT: NOW });
  ok('a play without it draws exactly what it drew before (no spread text)', !/Spread at Pinnacle/.test(SH.buildOps(d0, measure).ops.filter((o) => o.t === 'text').map((o) => o.s).join('\n')));
  /* the line is one more flag fact: it is drawn with the flag sentences and is left out with them, in the unchanged drop order (nums, money, flags, market) */
  const variant = (dd, extra) => { dd = JSON.parse(JSON.stringify(dd)); dd.moves.flags = (dd.moves.flags || []).concat(Array.from({ length: extra }, () => 'word '.repeat(12))); return dd; };
  const place = (dd, k) => { const rr = SH.buildOps(dd, (font, s) => String(s).length * px(font) * k); return { dropped: rr.dropped, spread: /Spread at Pinnacle/.test(rr.ops.filter((o) => o.t === 'text').map((o) => o.s).join('|')) }; };
  const noSpread = (dd) => { dd = JSON.parse(JSON.stringify(dd)); delete dd.moves.spread; return dd; };
  eq('roomy: nothing is dropped and the line is drawn', place(variant(d, 0), 0.4), { dropped: [], spread: true });
  eq('tight: the lowest block goes first and the line is still drawn with the flag sentences', place(variant(d, 0), 0.6), { dropped: ['money'], spread: true });
  eq('tighter: with the flag sentences dropped the line is dropped with them', place(variant(d, 10), 0.52), { dropped: ['nums', 'money', 'flags'], spread: false });
  let grid = 0, bad = [];
  for (const k of [0.4, 0.52, 0.6, 0.64, 0.7, 0.8]) for (const extra of [0, 1, 2, 4, 6, 10]) {
    grid++;
    const w = place(variant(d, extra), k);
    if (w.spread !== (w.dropped.indexOf('flags') < 0 && w.dropped.indexOf('market') < 0)) bad.push([k, extra, w]);
  }
  eq('for ' + grid + ' widths and lengths the line is drawn exactly while the flag sentences are', bad, []);
  ok('the dropped list names only the registered steps', place(variant(d, 10), 0.52).dropped.every((k) => ['nums', 'money', 'flags', 'market'].indexOf(k) >= 0));
  eq('a play without the line has exactly the old dropped list', SH.buildOps(P.shareDataOf(withSpread(undefined), { url: 'u', nowT: NOW }), measure).dropped, SH.buildOps(noSpread(d), measure).dropped);
  ok('the poster keeps its size', r.height === 1350 && r.used <= 1350 - 60 - 50, [r.used, r.height]);
}

console.log('the card: sentence, status, fair, limit, toggle state');
{
  const quiet = P.writeupHtml(play({ flags: FL(PIN('quiet'), LIN('quiet')), exec: { novig: NOVIG(0.51) }, vs_fair: { pts: 0.4, fair: 0.521, line: null, why: null }, sides: { Grizzlies: SIDE(30000, 14), Hornets: SIDE(20000, 17) } }, { g: 'ml' }), {});
  ok('no label: the first takeaway sentence is the plain sentence and the rest follows as the takeaway', /sv2-ac-say">The market barely moved on this moneyline in the last 22 hours\./.test(quiet) && /sv2-ac-tk">More of the tracked Polymarket money is on/.test(quiet) && !/The market barely moved[^<]*<\/p><p class="sv2-ac-tk">[^<]*The market barely moved/.test(quiet));
  const away = P.spreadOf(withSpread(SPREAD({ toward: 0, away: 4 })));
  eq('away only: the sentence and the row value follow the numbers', [away.text, away.same], ['Spread at Pinnacle went -3.5 to -5.5, 4 of 6 books moved away from Hornets.', false]);
  const gp = play(Object.assign(FULL(), { graded: { result: 'won', score: '110-102' } }), { g: 'ml' });
  ok('graded: Final score and the result in the status row, no freeze time', /Final 110-102/.test(rowText(P.writeupHtml(gp, {}), 'status')) && /Won/.test(rowText(P.writeupHtml(gp, {}), 'status')) && !/Freezes/.test(rowText(P.writeupHtml(gp, {}), 'status')));
  ok('the fair row does not repeat its own label', /data-ac="fair"><dt>Fair<\/dt><dd class="sv2-ac-v">52\.1c<\/dd>/.test(P.writeupHtml(ml(), {})));
  const lim = (from, to, rows) => strip(P.limitRow(FL(PIN('quiet'), null, { limit: { from, to, rows } })).v).trim() + ' | ' + P.limitRow(FL(PIN('quiet'), null, { limit: { from, to, rows } })).n;
  eq('limit rose', lim(1100, 1450, 14), 'from $1.1K to $1.45K | +32%, fact only');
  eq('limit fell', lim(1450, 1100, 14), 'from $1.45K to $1.1K | -24%, fact only');
  eq('limit unchanged', lim(3000, 3000, 6), '$3K | unchanged, fact only');
  eq('limit one reading', lim(3000, 3000, 1), '$3K | one reading, fact only');
  eq('limit with no stored number draws nothing', [P.limitRow(FL(PIN('quiet'), null, { limit: null })), P.limitRow(FL(PIN('quiet'), null, { limit: { from: 1, to: null, rows: 2 } })), P.limitRow(null)], [null, null, null]);
  /* the toggle keeps its choice through a redraw, and its handler flips the expander */
  const key = 'e1|ml', p0 = ml();
  p0.facts = { tiered: true, side: 'Hornets', a1: { on: false, n: 0 }, a2: { on: false, n: 0 }, a3: { on: false }, a4: { on: false, pts: null }, b1: { on: false, n: 0 }, b2: { on: false }, b3: { on: false }, b4: { on: false }, pts: null, proven: 0 };
  const st = { more: {}, why: {} };
  ok('a redraw with no choice is closed', /aria-expanded="false"/.test(P.detailFor(p0, st)));
  const el = (attrs) => ({ attrs: Object.assign({}, attrs), hasAttribute(k) { return k in this.attrs; }, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; }, getAttribute(k) { return this.attrs[k] === undefined ? null : this.attrs[k]; } });
  const panel = el({}), btn = el({ 'data-sp-why': key, 'aria-expanded': 'false' }); btn.parentNode = { querySelector: (q) => (q === '.sv2-x' ? panel : null) };
  eq('the first press opens it', [P.whyToggle(btn, st), 'data-open' in panel.attrs, btn.attrs['aria-expanded'], st.why[key]], [true, true, 'true', true]);
  ok('a redraw after that keeps it open, in the dropdown body and in the table row', /aria-expanded="true"/.test(P.detailFor(p0, st)) && /class="sv2-x" id="sv2-wu-e1-ml-why" data-open/.test(P.detailFor(p0, st)) && /class="sv2-x" id="sv2-wu-e1-ml-why" data-open/.test(P.rowHtml(p0, { open: { [key]: true }, more: {}, why: st.why }, {})));
  eq('the second press closes it', [P.whyToggle(btn, st), 'data-open' in panel.attrs, btn.attrs['aria-expanded'], st.why[key]], [false, false, 'false', false]);
  ok('after closing, a redraw is closed again', /aria-expanded="false"/.test(P.detailFor(p0, st)) && !/id="sv2-wu-e1-ml-why" data-open/.test(P.detailFor(p0, st)));
  const src = fs.readFileSync(path.join(ROOT, 'sv2-sharps.js'), 'utf8');
  ok('the click handler routes the button to whyToggle, and the first draw and a redraw both go through detailFor', /var wy = t\.closest\('\[data-sp-why\]'\);\s*if \(wy\) \{ whyToggle\(wy, st\); return; \}/.test(src) && /inEl\.innerHTML = detailFor\(p, st\)/.test(src) && /\(open \? detailFor\(p, st\) : ''\)/.test(src));
  ok('a state without a why map still draws', /sv2-ac-top/.test(P.detailFor(p0, { more: {} })));
}

console.log('words, books, dashes');
{
  const cards = [P.writeupHtml(withSpread(SPREAD()), {}), P.writeupHtml(withSpread(SPREAD({ toward: 3, away: 1 })), {}), P.writeupHtml(withSpread(SPREAD({ pin: [-3.5, -3.5], toward: 0, away: 0 })), {}),
    P.writeupHtml(play(Object.assign(FULL(), { flags: FL(PIN('toward'), LIN('toward')) }), { g: 'total' }), {}), P.writeupHtml(play({}, {}), {}), P.writeupHtml(withSpread(SPREAD(), { sport: 'cfb' }), {})];
  const all = cards.map(strip).join(' ') + ' ' + P.spreadOf(withSpread(SPREAD())).text;
  ok('no banned word in any card', FORBID.every((w) => !new RegExp('\\b' + w + '\\b', 'i').test(all)), FORBID.filter((w) => new RegExp('\\b' + w + '\\b', 'i').test(all)));
  ok('no em or en dash, no unfilled slot', !all.includes(EM) && !all.includes(EN) && !/[{}]|undefined|\bnull\b|NaN/.test(all));
  ok('only the stored books are named', !/Kalshi|BookMaker|Circa|Caesars|Fanatics|Diamond|Odds Drop/.test(all));
  ok('a CFB moneyline says No size on CFB in the status row', /No size on CFB/.test(rowText(cards[5], 'status')));
  ok('every control is a real button and the card holds no table and no CSS zoom', !/<table|zoom/i.test(cards[0].replace(/<svg[\s\S]*?<\/svg>/g, '')) && /<button type="button"/.test(cards[0]));
}

console.log(pass + ' pass, ' + fail + ' fail');
process.exit(fail ? 1 : 0);
