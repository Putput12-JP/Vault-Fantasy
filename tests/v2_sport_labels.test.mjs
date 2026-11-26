/* Desktop Sharp Money sport labels used on the Passed list.
   run: node --test tests/v2_sport_labels.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function sportMap(src) {
  const m = src.match(/var SPORT = \{([^}]+)\}/);
  assert.ok(m, 'expected a SPORT map in v2-pages.js');
  const out = {};
  for (const part of m[1].split(',')) {
    const kv = part.trim().match(/^([A-Za-z0-9_]+):\s*'([^']*)'$/);
    assert.ok(kv, 'could not parse SPORT entry: ' + part);
    out[kv[1]] = kv[2];
  }
  return out;
}

test('the desktop sport-label map includes CBB', () => {
  const pages = readFileSync(join(root, 'sharp-money/v2-pages.js'), 'utf8');
  const map = sportMap(pages);
  assert.equal(map.cbb, 'CBB');
  assert.equal(map.nfl, 'NFL');
  assert.equal(map.cfb, 'CFB');
  assert.equal(map.nba, 'NBA');
  assert.equal(map.all, 'All');
  // PassRow and OpenRow print this map next to the date. A missing key is the
  // "undefined · Thu Nov 26" bug on the Passed list.
  assert.match(pages, /SPORT\[c\.sport\] \+ ' · '/);
  assert.match(pages, /SPORT\[p\.sport\] \+ ' · '/);
});

test('the changelog entry is present, newest first, and has no em dash', () => {
  const index = readFileSync(join(root, 'index.html'), 'utf8');
  const i = index.indexOf('const VAULT_CHANGELOG = [');
  assert.ok(i > 0);
  const head = index.slice(i, i + 1200);
  assert.match(head, /ts:'2026-11-26T04:15'/);
  assert.match(head, /college basketball plays show CBB instead of undefined/);
  assert.match(head, /shows CBB and the game date, instead of the word undefined/);
  assert.ok(head.indexOf("ts:'2026-11-26T04:15'") < head.indexOf("ts:'2026-11-25T22:10'"));
  const newest = head.slice(0, head.indexOf("ts:'2026-11-25T22:10'"));
  assert.doesNotMatch(newest, /\u2014|\u2013/);
});
