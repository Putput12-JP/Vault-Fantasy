/* Named "Run now" dispatch on the sharp-refresh Worker. A Refresh click (no job field) must stay unchanged.
   run: node --test tests/sharp_refresh_dispatch.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
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

test('Run now for a price job sends no inputs (the workflow does not declare any)', async () => {
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
  assert.doesNotMatch(d.body, /"source"/);
  assert.doesNotMatch(d.body, /"inputs"/);
  assert.match(d.body, /"ref"/);
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


function workflowText(name) {
  try {
    return execSync('git show HEAD:.github/workflows/' + name, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  } catch {
    return readFileSync(new URL('../.github/workflows/' + name, import.meta.url), 'utf8');
  }
}

function declaredDispatchInputs(yml) {
  const m = yml.match(/workflow_dispatch:\s*\n((?:[ \t].*\n)*)/);
  if (!m || !/^\s+inputs:/m.test(m[1])) return [];
  const keys = [];
  let inInputs = false, base = null;
  for (const line of m[1].split('\n')) {
    if (/^\s+inputs:\s*$/.test(line)) { inInputs = true; base = line.search(/\S/); continue; }
    if (!inInputs) continue;
    const ind = line.search(/\S/);
    if (ind === -1) continue;
    if (ind <= base) break;
    if (ind === base + 2 && /^[A-Za-z0-9_]+:/.test(line.trim())) keys.push(line.trim().split(':')[0]);
  }
  return keys;
}

test('dispatch bodies only include inputs each workflow declares on HEAD', async () => {
  for (const id of JOBS) {
    const wf = CLICK_JOBS[id].wf;
    const declared = declaredDispatchInputs(workflowText(wf));
    const calls = [];
    globalThis.fetch = async (url, init = {}) => {
      calls.push({ url: String(url), body: init.body });
      if (String(url).includes('siteverify')) return Response.json({ success: true });
      if (String(url).includes('/runs?')) return Response.json({ workflow_runs: [{ created_at: '2020-01-01T00:00:00Z' }], total_count: 0 });
      if (String(url).includes('/dispatches')) return new Response(null, { status: 204 });
      return Response.json({});
    };
    const r = await worker.fetch(post({ token: 'tok', job: id }), env());
    // lineup may 409 if treated as recent/budget depending on stub; allow 202 or 409
    const d = calls.find(c => c.url.includes('/dispatches'));
    assert.ok(d, id + ' did not dispatch: ' + r.status);
    const body = JSON.parse(d.body);
    const sent = Object.keys(body.inputs || {});
    assert.deepEqual(sent, declared, id + ' sent ' + JSON.stringify(sent) + ' but yml declares ' + JSON.stringify(declared));
    if (declared.includes('force')) assert.equal(body.inputs.force, 'true');
    assert.ok(!('source' in (body.inputs || {})), id + ' must not send source until the yml declares it');
  }
});

test('a Refresh click (maybeLineup) does not send source on update-lineup', async () => {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), body: init.body });
    if (String(url).includes('siteverify')) return Response.json({ success: true });
    if (String(url).includes('/runs?')) return Response.json({ workflow_runs: [{ created_at: '2020-01-01T00:00:00Z' }], total_count: 0 });
    if (String(url).includes('/dispatches')) return new Response(null, { status: 204 });
    return Response.json({});
  };
  const r = await worker.fetch(post({ token: 'tok' }), env());
  assert.equal(r.status, 202);
  const lineup = calls.find(c => c.url.includes('update-lineup.yml') && c.url.includes('/dispatches'));
  assert.ok(lineup);
  const body = JSON.parse(lineup.body);
  assert.equal(body.inputs, undefined);
  assert.ok(!JSON.stringify(body).includes('source'));
});
