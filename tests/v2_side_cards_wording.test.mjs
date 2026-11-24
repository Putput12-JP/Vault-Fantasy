/* The wording on the classic Sharp Money proven-sharps side card (sharp-money/side-cards.js) says what is true.
   Three honesty rules, asserted on the card as it renders (the real file runs in a vm with a stub DOM, on stored cards):
     (a) the shown size is a flat 1u UNTESTED rule. It is never called the pre-registered lock and never "still in its forward test";
         the pre-registered test is a different, narrower rule counted on its own.
     (b) no chip says Elite, Prem, Lock, Lean, Weak, Trusted or the like: the score bands print as Band 1 to Band 5, with the wallet count behind them.
     (c) "on Polymarket" is printed only when v2.price_src is `pm`; `pin` says it is Pinnacle's price with the vig included; a missing source says nothing.
   The two shells (sharp-money/index.html and sharp-money/new/index.html) are one page: both must load the same side-cards.js version.
   run: node --test tests/v2_side_cards_wording.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SRC = fs.readFileSync(path.join(ROOT, 'sharp-money', 'side-cards.js'), 'utf8');
const LIVE = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests', 'fixtures', 'side_cards_wording', 'live_trim.json'), 'utf8'));
const KEYS = { nba: 'nba:295217', nfl: 'nfl:290995', cbb: 'cbb:298019' };    // PREMIUM, LEAN and ELITE side scores in the stored cards

/* a stub DOM that records every innerHTML the card writes */
function stub(out) {
  const store = { innerHTML: '', className: '', style: {}, dataset: {} };
  return new Proxy(function () {}, {
    get(t, k) {
      if (['innerHTML', 'textContent', 'className', 'id', 'title'].includes(k)) return store[k] ?? '';
      if (k === 'style' || k === 'dataset') return store[k];
      if (k === Symbol.toPrimitive) return () => '';
      if (k === 'classList') return { contains: () => false, toggle() {}, add() {}, remove() {} };
      if (k === 'length') return 0;
      if (k === 'closest' || k === 'contains') return () => null;
      if (k === 'then' || k === 'previousElementSibling' || k === 'nextElementSibling') return undefined;
      return () => stub(out);
    },
    set(t, k, v) { store[k] = v; if (k === 'innerHTML') out.push(String(v)); return true; },
    apply() { return stub(out); },
  });
}
/* a fresh page context per render, so no state leaks between cases */
async function render(live, how) {
  const out = [], data = JSON.parse(JSON.stringify(live));
  const ctx = { console, setTimeout, setInterval: () => 1, clearInterval() {}, clearTimeout() {}, Date, Math, JSON, Promise, URL, Intl,
    location: { hostname: 'localhost', search: '?live', hash: '' },
    document: { createElement: () => stub(out), getElementById: () => stub(out), querySelectorAll: () => [], querySelector: () => stub(out), contains: () => true, head: stub(out), body: stub(out), addEventListener() {} },
    localStorage: { getItem: () => null, setItem() {} }, fetch: async () => ({ ok: true, json: async () => data }), addEventListener() {},
    matchMedia: () => ({ matches: false, addEventListener() {} }), requestAnimationFrame: f => f() };
  ctx.window = ctx; vm.createContext(ctx); vm.runInContext(SRC, ctx);
  how(ctx.VaultSideCards, stub(out));
  await new Promise(r => setTimeout(r, 120));
  return out.join('\n');
}
const game = (live, sport, src) => {
  const l = JSON.parse(JSON.stringify(live)), g = l.games.find(x => x.vault && x.vault.key === KEYS[sport]);
  if (src === null) delete g.markets.ml.v2.price_src; else g.markets.ml.v2.price_src = src;
  l.games = [g]; return l;
};
const card = (sport, src) => render(game(LIVE, sport, src), (V, el) => V.mountGame(el, KEYS[sport], {}));
/* the price line of the shown play: "72.5¢ on Polymarket, read 10:03 AM CT" */
const priceLine = html => { const m = html.match(/<span class="vc-vs">([\s\S]*?)<\/span><\/div>/); assert.ok(m, 'no price line'); return m[1].replace(/<[^>]*>/g, ''); };
const text = html => html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ');

test('the fixture is a shown play with a stored price source and a positive score', () => {
  for (const sport of ['nba', 'nfl', 'cbb']) {
    const m = game(LIVE, sport, 'pm').games[0].markets.ml;
    assert.equal(m.v2.price_src, 'pm');
    assert.ok(m.sf.all.side && m.sf.all.units > 0 && m.sf.all.price != null);
    assert.ok(Object.values(m.sides).some(s => s.all.ags && s.all.ags.score > 0));
  }
});

/* ---------- (c) the price label ---------- */
test('pm: the price says on Polymarket', async () => {
  const t = priceLine(await card('nba', 'pm'));
  assert.match(t, /^\d+(\.\d)?¢ on Polymarket, read /);
  assert.doesNotMatch(t, /Pinnacle|vig/);
});
test('pin: the price is labelled Pinnacle price, vig included, and never on Polymarket', async () => {
  for (const sport of ['nba', 'nfl', 'cbb']) {
    const t = priceLine(await card(sport, 'pin'));
    assert.match(t, /^\d+(\.\d)?¢ Pinnacle price, vig included, read /, sport);
    assert.doesNotMatch(t, /Polymarket/, sport);
  }
});
test('a missing price source says nothing about the source', async () => {
  const t = priceLine(await card('nba', null));
  assert.match(t, /^\d+(\.\d)?¢, read /);
  assert.doesNotMatch(t, /Polymarket|Pinnacle|vig/);
});
test('an unknown price source value says nothing either', async () => {
  const t = priceLine(await card('nba', 'kalshi'));
  assert.match(t, /^\d+(\.\d)?¢, read /);
  assert.doesNotMatch(t, /Polymarket|Pinnacle|vig/);
});

/* ---------- (b) the chips ---------- */
const BANNED_CHIP = /\b(Elite|Prem|Premium|Lock|Lean|Weak|Trusted|Proven|Best bet|Guaranteed|Confidence)\b/;
test('the score chip prints a band number and the wallets behind it, on the game card', async () => {
  const want = { nba: ['PREMIUM', 'Band 4'], nfl: ['LEAN', 'Band 2'], cbb: ['ELITE', 'Band 5'] };
  for (const [sport, [tier, label]] of Object.entries(want)) {
    const html = await card(sport);
    assert.match(html, new RegExp('<span class="vc-tier ' + tier + '" title="Score band ' + label.slice(5) + ' of 5, from \\d+ hot wallets?\\.[^"]*">' + label + '</span>'), sport);
    assert.match(text(html), /score \+0\.\d\d \d+ hot wallets? scored, \d+ tracked/, sport);
    assert.match(html, /It does not say this side will win/);
    assert.doesNotMatch(html.replace(/<style[\s\S]*?<\/style>/g, ''), BANNED_CHIP, sport);
  }
});
test('the score chip on the Sharps plays list is a band with its wallet count', async () => {
  const html = await render(game(LIVE, 'nba', 'pm'), (V, el) => V.mountPage(el, { sport: 'nba' }));
  assert.match(html, /<span class="vc-tier PREMIUM"[^>]*>Band 4<\/span><span>score <span class="num">\+0\.\d\d<\/span> from \d+ hot wallets?<\/span>/);
});
test('no label the page prints on a chip is one of the forbidden confidence words', () => {
  const get = (re, extra = {}) => vm.runInNewContext('(' + SRC.match(re)[1] + ')', extra);
  const TIER = JSON.parse(JSON.stringify(get(/var TIER = (\{[^}]*\});/)));
  assert.deepEqual(Object.values(TIER), ['Band 1', 'Band 2', 'Band 3', 'Band 4', 'Band 5']);
  assert.deepEqual(Object.keys(TIER), ['WEAK', 'LEAN', 'LOCK', 'PREMIUM', 'ELITE']);      // the stored keys are unchanged
  const FTIERS = JSON.parse(JSON.stringify(get(/var FTIERS = (\[.*\]);/, { TIER })));
  assert.deepEqual(FTIERS.map(x => x[0]), ['ELITE', 'PREMIUM', 'LOCK', 'LEAN', 'WEAK', 'NONE']);
  const RUNG = JSON.parse(JSON.stringify(vm.runInNewContext('(' + SRC.match(/var RUNG = (\{[\s\S]*?\n\});/)[1] + ')')));
  const labels = [...Object.values(TIER), ...FTIERS.map(x => x[1]), ...Object.values(RUNG).map(x => x[0])];
  for (const l of labels) assert.doesNotMatch(l, BANNED_CHIP, l);
  assert.equal(RUNG['TRUST-G'][0], 'Price record');
});

/* ---------- (a) what the shown size is ---------- */
const FOOT = 'Sharp money is context. The suggested size is a flat 1u from an untested rule. It is not the pre-registered test, which is a different, narrower rule counted on its own. CFB games carry no size.';
test('both footers say the size is an untested rule and not the pre-registered test', async () => {
  const gameHtml = await card('nba');
  assert.ok(text(gameHtml).includes(FOOT), 'game card footer');
  const pageHtml = await render(game(LIVE, 'nba', 'pm'), (V, el) => V.mountPage(el, { sport: 'nba' }));
  assert.ok(text(pageHtml).includes(FOOT), 'plays page footer');
  for (const h of [gameHtml, pageHtml]) assert.match(h, /untested rule/);
});
test('the card keeps the untested rule label wherever a size shows', async () => {
  const html = await card('nba');
  assert.match(html, /<b class="vc-vu num">1<small>u<\/small><\/b>[\s\S]*Suggested<span class="vc-tag">untested rule<\/span>/);
  const page = await render(game(LIVE, 'nba', 'pm'), (V, el) => V.mountPage(el, { sport: 'nba' }));
  assert.match(page, /<b class="vp-u num">1<small>u<\/small><\/b><span class="vp-rule">(<b>[^<]*<\/b>)?untested rule<\/span>/);
});
test('no string the page can print calls the shown size the pre-registered lock or says it is still in its forward test', async () => {
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, '');                                    // block comments are notes for developers, not page text
  for (const bad of [/still in its forward test/, /meets the pre-registered press-ladder/, /is the pre-registered lock/, /This is not the "Lock"/, /Counts for the forward test\./,
    /\(L\.n \? 'Locks '/, /What Vault and Lock mean/, /Trusted wallet/, /\bon Polymarket' \+ \(ls\.price_t/]) assert.doesNotMatch(code, bad, String(bad));
  for (const h of [await card('nba'), await card('cbb', 'pin')]) {
    assert.doesNotMatch(text(h), /still in its forward test|pre-registered lock/);
  }
});
test('the record help and forward test card tell the pre-registered rule apart from the shown size', () => {
  assert.ok(SRC.includes('The pre-registered test is a different, narrower rule from the size the card shows.'));
  assert.ok(SRC.includes('The pre-registered rule, not the size the card shows. Counted moneyline locks'));
  assert.ok(SRC.includes("'Test plays ' + wl(L)"));
  assert.ok(SRC.includes('aria-label="What Vault and Test mean"'));
  assert.ok(SRC.includes('It is NOT the pre-registered lock of'));
});
test('the filter help names the bands and says a band is not a promise', () => {
  assert.ok(SRC.includes("['Band 1 to 5', 'The band SharpFlow"));
  assert.ok(SRC.includes('A band describes past wallet records, not how likely a play is to win.'));
  assert.ok(SRC.includes("grp('Score band', 'tier', FTIERS, PV.f.tier)"));
});

/* ---------- the two shells are one page ---------- */
test('both Sharp Money shells load the same side-cards.js version', () => {
  const v = f => fs.readFileSync(path.join(ROOT, f), 'utf8').match(/side-cards\.js\?v=([0-9]+)/)[1];
  assert.equal(v('sharp-money/index.html'), v('sharp-money/new/index.html'));
});
test('the money rules are unchanged: a flat 1u on NBA, NFL and CBB, nothing on CFB', () => {
  assert.match(SRC, /var FLAT_SP = \{nba: 1, nfl: 1, cbb: 1\};/);
});
