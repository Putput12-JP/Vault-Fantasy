/* Named "Run now" dispatch on the sharp-refresh Worker. A Refresh click (no job field) must stay unchanged.
   run: node --test tests/sharp_refresh_dispatch.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { CLICK_JOBS, Gate } from '../workers/sharp-refresh/src/index.js';

const JOBS = [
  'update-sharp-money', 'nfl-book-tape', 'update-props', 'update-prop-history',
  'update-game-history', 'update-kalshi', 'update-polymarket', 'update-line-history', 'update-lineup'
];

test('CLICK_JOBS lists the nine Control Room jobs and maps each to its workflow file', () => {
  assert.deepEqual(Object.keys(CLICK_JOBS), JOBS);
  assert.equal(CLICK_JOBS['update-sharp-money'].wf, 'update-sharp-money.yml');
  assert.equal(CLICK_JOBS['update-sharp-money'].force, true);
  assert.equal(CLICK_JOBS['update-lineup'].lineup, true);
  assert.equal(CLICK_JOBS['update-props'].wf, 'update-props.yml');
});

function env(overrides = {}) {
  const claims = [];
  const gateFetch = async (req) => {
    claims.push(new URL(typeof req === 'string' ? req : req.url).pathname);
    if (overrides.cooldown) return Response.json({ ok: false, retry: 42 }, { status: 429 });
    return Response.json({ ok: true });
  };
  return {
    REPO: 'Putput12-JP/Vault-Fantasy',
    REF: 'main',
    WORKFLOW: 'update-sharp-money.yml',
    LINEUP_WORKFLOW: 'update-lineup.yml',
    GITHUB_TOKEN: 't',
    TURNSTILE_SECRET: 's',
    GATE: { idFromName: (n) => ({ name: n }), get: (id) => ({ id, fetch: gateFetch }) },
    _claims: claims,
    ...overrides
  };
}

function post(body, origin = 'https://vaultfantasy.com') {
  return new Request('https://sharp-refresh.example/', {
    method: 'POST',
    headers: { Origin: origin, 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

test('an unknown job is rejected before Turnstile or GitHub is called', async () => {
  const calls = [];
  globalThis.fetch = async (url) => { calls.push(String(url)); return Response.json({ success: true }); };
  const r = await worker.fetch(post({ token: 'x', job: 'not-a-job' }), env());
  assert.equal(r.status, 400);
  const j = await r.json();
  assert.equal(j.error, 'job');
  assert.ok(!calls.some(u => u.includes('github.com')));
});

test('a Refresh click (no job) still starts update-sharp-money with force=true and maybeLineup', async () => {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), method: init.method || 'GET', body: init.body });
    if (String(url).includes('siteverify')) return Response.json({ success: true });
    if (String(url).includes('/runs?')) return Response.json({ workflow_runs: [{ created_at: '2020-01-01T00:00:00Z' }], total_count: 0 });
    if (String(url).includes('/dispatches')) return new Response(null, { status: 204 });
    return Response.json({});
  };
  const r = await worker.fetch(post({ token: 'tok' }), env());
  assert.equal(r.status, 202);
  const j = await r.json();
  assert.equal(j.ok, true);
  const dispatches = calls.filter(c => c.url.includes('/dispatches'));
  assert.ok(dispatches.some(c => c.url.includes('update-sharp-money.yml') && c.body.includes('"force":"true"')));
});

test('Run now for a price job dispatches that workflow with source=click', async () => {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), method: init.method || 'GET', body: init.body });
    if (String(url).includes('siteverify')) return Response.json({ success: true });
    if (String(url).includes('/dispatches')) return new Response(null, { status: 204 });
    return Response.json({});
  };
  const r = await worker.fetch(post({ token: 'tok', job: 'update-kalshi' }), env());
  assert.equal(r.status, 202);
  const j = await r.json();
  assert.equal(j.ok, true);
  const d = calls.find(c => c.url.includes('/dispatches'));
  assert.match(d.url, /update-kalshi\.yml/);
  assert.match(d.body, /"source":"click"/);
  assert.doesNotMatch(d.body, /force/);
});

test('Run now for Sharp Money refresh sends force=true and does not also start lineup', async () => {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), body: init.body });
    if (String(url).includes('siteverify')) return Response.json({ success: true });
    if (String(url).includes('/dispatches')) return new Response(null, { status: 204 });
    return Response.json({});
  };
  const r = await worker.fetch(post({ token: 'tok', job: 'update-sharp-money' }), env());
  assert.equal(r.status, 202);
  const dispatches = calls.filter(c => c.url.includes('/dispatches'));
  assert.equal(dispatches.length, 1);
  assert.match(dispatches[0].url, /update-sharp-money\.yml/);
  assert.match(dispatches[0].body, /"force":"true"/);
});

test('a failed Turnstile check never reaches GitHub', async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(String(url));
    if (String(url).includes('siteverify')) return Response.json({ success: false });
    return new Response(null, { status: 204 });
  };
  const r = await worker.fetch(post({ token: 'bad', job: 'update-props' }), env());
  assert.equal(r.status, 403);
  assert.ok(!calls.some(u => u.includes('github.com')));
});

test('localhost:4173 is an allowed origin, matching the Vault dev server', async () => {
  globalThis.fetch = async (url) => {
    if (String(url).includes('siteverify')) return Response.json({ success: true });
    if (String(url).includes('/dispatches')) return new Response(null, { status: 204 });
    return Response.json({});
  };
  const r = await worker.fetch(post({ token: 'tok', job: 'update-props' }, 'http://localhost:4173'), env());
  assert.equal(r.status, 202);
});

test('Gate is still exported for the Durable Object binding', () => {
  assert.equal(typeof Gate, 'function');
});
