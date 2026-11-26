/* The Sharp Money phone shell must fill the viewport below the desktop breakpoint.
   run: node --test tests/sm_phone_fullwidth.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'sharp-money/new/index.html'), 'utf8');
const style = (html.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1];

function rules(sel, block) {
  const out = [];
  const re = new RegExp(sel.replace(/[.*]/g, '\\$&') + '\\{([^}]*)\\}', 'g');
  let m;
  while ((m = re.exec(block))) out.push(m[1]);
  return out;
}

function splitMedia(css) {
  const desktop = [];
  let rest = '';
  let i = 0;
  const needle = '@media (min-width:768px)';
  while (i < css.length) {
    const j = css.indexOf(needle, i);
    if (j < 0) { rest += css.slice(i); break; }
    rest += css.slice(i, j);
    const open = css.indexOf('{', j);
    let depth = 0, k = open;
    for (; k < css.length; k++) {
      if (css[k] === '{') depth++;
      else if (css[k] === '}') {
        depth--;
        if (depth === 0) { k++; break; }
      }
    }
    desktop.push(css.slice(open + 1, k - 1));
    i = k;
  }
  return { rest, desktop: desktop.join('\n') };
}

test('the phone shell has no 560px cap below 768px', () => {
  assert.ok(style.length > 100);
  const { rest, desktop } = splitMedia(style);
  const app = rules('.app', rest);
  const bar = rules('.tabbar', rest);
  assert.ok(app.length, 'expected a base .app rule');
  assert.ok(bar.length, 'expected a base .tabbar rule');
  for (const b of app.concat(bar)) {
    assert.doesNotMatch(b, /max-width:\s*560px/, '560px cap leaked into the phone-width rules: ' + b);
  }
  // Desktop-forced phone view (?view=new) may keep a cap.
  assert.match(desktop, /\.app\{[^}]*max-width:\s*560px/);
  assert.match(desktop, /\.tabbar\{[^}]*max-width:\s*560px/);
});

test('the phone shell and tab bar respect horizontal safe-area insets', () => {
  const { rest } = splitMedia(style);
  const app = rules('.app', rest).join(';');
  const bar = rules('.tabbar', rest).join(';');
  assert.match(app, /padding-left:env\(safe-area-inset-left\)/);
  assert.match(app, /padding-right:env\(safe-area-inset-right\)/);
  assert.match(bar, /safe-area-inset-left/);
  assert.match(bar, /safe-area-inset-right/);
  assert.match(bar, /safe-area-inset-bottom/);
});

test('the changelog entry is present, newest first, and has no em dash', () => {
  const index = readFileSync(join(root, 'index.html'), 'utf8');
  const i = index.indexOf('const VAULT_CHANGELOG = [');
  assert.ok(i > 0);
  const head = index.slice(i, i + 1800);
  assert.match(head, /ts:'2026-11-25T21:53'/);
  assert.match(head, /the phone page fills a wide screen without cutting off labels/);
  assert.match(head, /the Sharp Money page, the bottom menu, and the play cards now use the full width/);
  assert.match(head, /price labels on those cards stay fully readable/);
  assert.doesNotMatch(head, /ts:'2026-11-25T21:29'/);
  // Newest first: combined full-width + labels entry, then Control Room.
  assert.ok(head.indexOf("ts:'2026-11-25T21:53'") < head.indexOf("ts:'2026-11-25T20:33'"));
  assert.doesNotMatch(head.slice(0, head.indexOf("ts:'2026-11-25T20:33'")), /\u2014|\u2013/);
});

test('play cards keep an existing max-width (none) and are not restyled', () => {
  const pages = readFileSync(join(root, 'sharp-money/v2-pages.js'), 'utf8');
  const side = readFileSync(join(root, 'sharp-money/side-cards.js'), 'utf8');
  const neu = readFileSync(join(root, 'sharp-money/new/index.html'), 'utf8');
  // cardHtml itself is untouched; the phone wrapper still uses the 16px side margins.
  assert.match(neu, /function v2card\(c,F\)\{return `<div class="v2card \$\{c\.gk\?'tap':''\}" style="margin:0 16px 12px;border-radius:22px"/);
  assert.match(neu, /class="v2rec" style="margin:0 16px 12px"/);
  assert.match(pages, /function cardHtml\(/);
  // Desktop and classic still use auto-fit; the 2x2 override lives only in the phone shell CSS.
  assert.match(pages, /repeat\(auto-fit,minmax\(' \+ \(tiles\.length > 3 \? 128 : 100\) \+ 'px,1fr\)\)/);
  assert.match(pages, /repeat\(auto-fit,minmax\(130px,1fr\)\)/);
  assert.match(style, /\.v2card \[style\*="minmax\(128px"\]\{grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/);
  assert.match(style, /\.v2rec \[style\*="minmax\(130px"\]\{grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/);
  // The poster card already declares max-width:none and fills its container.
  assert.match(html.includes('VSC_CSS') ? html : side + html, /max-width:none/);
});
