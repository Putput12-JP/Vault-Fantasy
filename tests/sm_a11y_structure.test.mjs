/* Sharp Money structure-only accessibility fixes: page language, an h1 page title, a main landmark,
   and Enter/Space on the desktop Passed and Open rows. None of these may change pixels;
   the pixel diff lives in the PR, these guard the markup.
   run: node --test tests/sm_a11y_structure.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const desk = readFileSync(join(root, 'sharp-money/index.html'), 'utf8');
const phone = readFileSync(join(root, 'sharp-money/new/index.html'), 'utf8');
const pages = readFileSync(join(root, 'sharp-money/v2-pages.js'), 'utf8');
const rule = (css, sel) => { const i = css.indexOf(sel + '{'); assert.ok(i >= 0, 'missing CSS rule ' + sel); return css.slice(i + sel.length + 1, css.indexOf('}', i)); };

test('both shells declare English', () => {
  assert.match(desk.slice(0, 40), /^<html lang="en">\n/);
  // The desktop page has always rendered in quirks mode. A doctype would re-flow it, so it stays out of this PR.
  assert.doesNotMatch(desk.slice(0, 200), /<!doctype/i);
  assert.match(phone.slice(0, 60), /^<!doctype html>\n<html lang="en">\n/);
});

test('the visible page title is the h1, with its old type and no new margin', () => {
  assert.ok(desk.includes('(0,a.jsx)(M,{as:"h1",size:"lg",weight:"semibold",style:{margin:0},children:smPg})'));
  assert.ok(!desk.includes('(0,a.jsx)(M,{size:"lg",weight:"semibold",children:smPg})'));
  // the text component renders the `as` element with the same type tokens
  assert.match(desk, /function M\(\{[^}]*as:p="span"\}\)/);
  // phone: head(), the loading skeleton and the load error all use the same .title class on an h1
  assert.match(phone, /const head=\(t,s\)=>`<div class="trow"><h1 class="title">\$\{t\}<\/h1>/);
  assert.equal((phone.match(/<h1 class="title">Sharp Money<\/h1>/g) || []).length, 2);
  assert.doesNotMatch(phone, /<div class="title">/);
  // narrow desktop header keeps the title on one line now that it is not a span
  assert.ok(desk.includes('.sm-bar>div:first-of-type span,.sm-bar>div:first-of-type h1{white-space:nowrap}'));
});

test('the content column is the main landmark', () => {
  assert.ok(desk.includes('(0,a.jsxs)("main",{className:"sm-main",children:['));
  assert.ok(!desk.includes('(0,a.jsxs)("div",{className:"sm-main"'));
  assert.equal((phone.match(/<main /g) || []).length, 1);
  assert.match(phone, /<main id="scr" aria-live="polite"><\/main>/);
});

test('no skip link on either shell (dropped from this PR by request)', () => {
  for (const [name, src] of [['desktop', desk], ['phone', phone]]) {
    assert.doesNotMatch(src, /Skip to content|sm-skip|class="skip"|a\.skip/, name);
    assert.doesNotMatch(src, /#sm-main:focus|#scr:focus/, name);
  }
  assert.doesNotMatch(desk, /id:"sm-main"/);
  assert.doesNotMatch(phone, /setAttribute\('tabindex','-1'\)/);
});

test('the desktop patch script is idempotent on the committed file', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sm-a11y-'));
  const f = join(dir, 'index.html');
  writeFileSync(f, desk);
  const out = execFileSync('python3', [join(root, 'scripts/sharp_money_card/patch_a11y.py'), '--file', f], { encoding: 'utf8' });
  assert.match(out, /done, 0 change\(s\)/);
  assert.equal(readFileSync(f, 'utf8'), desk);
});

function loadPages() {
  const window = {};
  const ctx = { window, location: { hostname: 'vaultfantasy.com', search: '' }, fetch: () => Promise.resolve({ ok: false }), setInterval: () => 0, setTimeout: () => 0, console, Set, Promise, Math, Date, JSON };
  ctx.document = { addEventListener() {}, querySelector: () => null };
  vm.createContext(ctx);
  vm.runInContext(pages, ctx);
  return window.VaultV2;
}

test('Passed and Open rows answer Enter and Space like a click', () => {
  assert.match(pages, /var row = function \(cols, cells, key, onClick, head\) \{\n\s+return h\('div', \{ key: key, onClick: onClick, role: onClick \? 'button' : undefined, tabIndex: onClick \? 0 : undefined, onKeyDown: rowKeys\(onClick\),/);
  const { rowKeys } = loadPages();
  assert.equal(typeof rowKeys, 'function');
  assert.equal(rowKeys(undefined), undefined, 'rows without a click get no key handler');
  let hits = 0;
  const kd = rowKeys(() => { hits++; });
  const ev = (key, nested) => { const row = {}; const e = { key, currentTarget: row, target: nested ? {} : row, prevented: false, preventDefault() { this.prevented = true; } }; return e; };
  for (const k of ['Enter', ' ']) { const e = ev(k); kd(e); assert.ok(e.prevented, k + ' should not scroll the page'); }
  assert.equal(hits, 2);
  for (const k of ['a', 'Tab', 'Escape', 'ArrowDown']) { const e = ev(k); kd(e); assert.equal(e.prevented, false); }
  const inner = ev('Enter', true); kd(inner);
  assert.equal(hits, 2, 'a key press on a nested element is left alone');
  assert.equal(inner.prevented, false);
});

test('the changelog entry is newest first and has no em dash', () => {
  const index = readFileSync(join(root, 'index.html'), 'utf8');
  const i = index.indexOf('const VAULT_CHANGELOG = [');
  const head = index.slice(i, i + 1500);
  const a = head.indexOf("ts:'2026-11-26T08:25'"), b = head.indexOf("ts:'2026-11-26T04:15'");
  assert.ok(a > 0 && b > a);
  const entry = head.slice(a, b);
  assert.match(entry, /easier to use with a keyboard or screen reader/);
  assert.match(entry, /Nothing on the page looks different/);
  assert.doesNotMatch(entry, /skip/i);
  assert.doesNotMatch(entry, /\u2014|\u2013/);
});
