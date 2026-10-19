/* The V2 page and the headless ledger must decide Play / Watch / Passed identically.
   Three checks on the stored data.json, props.json, prop_close_tape.json and exchange_edge_live.json in tests/fixtures/sharp_v2/:
     1. the page as it runs now gives the same candidates, tiers, reasons AND rendered pages as the page did before the rules moved into gates.js
        (tests/fixtures/sharp_v2/page_before.json, recorded from the old inline code)
     2. the shared module called directly (what scripts/track-v2-plays.mjs uses) gives the same candidates as the page
     3. the same, on price-jittered copies of the data, so the Watch / Passed / contradiction branches run too (the stored snapshot has only 4 plays)
   run: node --test tests/v2_gates.test.mjs tests/v2_ledger.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { runPage, loadFixtures, jitter, project, FIX } from './v2_page_harness.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.dirname(HERE);
const HTML = path.join(ROOT, 'sharp-money', 'v2', 'index.html');
const gates = createRequire(import.meta.url)(path.join(ROOT, 'sharp-money', 'v2', 'gates.js'));
const before = JSON.parse(fs.readFileSync(path.join(FIX, 'page_before.json'), 'utf8'));
const fx = loadFixtures(), ts = fx.data.ts;
const SCEN = { base: [fx, ts + 60], j11: [jitter(fx, 11), ts + 60], j22: [jitter(fx, 22, 0.1), ts + 120], late: [fx, ts + 40 * 60] };

/* The one deliberate difference from the recorded page: the old code printed the line twice on an exchange spread or total ("ORL -2.5 -2.5",
   "Under 231.5 231.5") because the label already carries it. Map the old text to the fixed text, then everything else must match exactly. */
/* The recorded page output holds floats from this machine's Math.pow. Another Node or V8 build can differ in the last digit or two (Node 20 on CI vs the
   Node that recorded it), which says nothing about the rules. Compare numbers to 9 decimals; everything else, text and rendered pages, stays exact. */
const r9 = v => JSON.parse(JSON.stringify(v, (k, x) => typeof x === 'number' && !Number.isInteger(x) ? +x.toFixed(9) : x));

const oldTitle = c => c.kind !== 'exch' || c.m === 'ml' ? null : (r => c.side + ' ' + (c.m === 'sp' ? (r.line > 0 ? '+' : '') + r.line : r.line))(fx.edge.rows.find(x => x.gk === c.gk && x.m === c.m && x.label === c.side));
function fixOld(snapshot) {
  const dup = snapshot.all.filter(c => oldTitle(c)).map(c => [oldTitle(c), c.side]);
  const all = snapshot.all.map(c => oldTitle(c) ? { ...c, title: c.side } : c);
  const pages = Object.fromEntries(Object.entries(snapshot.pages).map(([k, h]) => [k, dup.reduce((t, [o, n]) => t.split(o).join(n), h)]));
  return { all, pages, dup: dup.length };
}

for (const [name, [f, now]] of Object.entries(SCEN)) {
  test(`page output is unchanged by moving the gates into gates.js (${name})`, async () => {
    const page = await runPage({ html: HTML, fixtures: f, now, games: before._games }), old = fixOld(before[name]);
    assert.deepEqual(r9(page.all), r9(old.all));
    for (const k of Object.keys(old.pages)) assert.equal(page.pages[k], old.pages[k], `rendered page ${k} changed`);
  });
  test(`the headless module decides exactly what the page decides (${name})`, async () => {
    const page = await runPage({ html: HTML, fixtures: f, now, pages: [] });
    const { all } = gates.build({ D: f.data, P: f.props, T: f.tape, E: f.edge, now });
    assert.deepEqual(JSON.parse(JSON.stringify(all.map(project))), page.all);
  });
}

test('an exchange spread or total no longer repeats its line in the title', () => {
  const t = fixOld(before.base), n = before.base.all.filter(c => c.kind === 'exch' && c.m !== 'ml');
  assert.ok(n.length > 0 && t.dup === n.length);
  for (const c of n) assert.equal(c.title, oldTitle(c), 'the recorded page really did print the line twice');
  const { all } = gates.build({ D: fx.data, P: fx.props, T: fx.tape, E: fx.edge, now: ts + 60 });
  for (const c of all.filter(c => c.kind === 'exch' && c.m !== 'ml')) assert.equal(c.title, c.side);
});

test('the stored snapshot has plays of more than one kind, and every tier appears across the scenarios', () => {
  const tiers = new Set(), kinds = new Set();
  for (const s of Object.values(before)) if (s.all) for (const c of s.all) { tiers.add(c.tier); if (c.tier === 'play') kinds.add(c.kind) }
  assert.deepEqual([...tiers].sort(), ['none', 'pass', 'play', 'watch']);
  assert.ok(kinds.has('prop') && kinds.has('book'));
});
