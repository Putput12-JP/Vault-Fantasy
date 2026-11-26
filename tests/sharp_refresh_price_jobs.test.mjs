/* The price-feed workflows are started by the sharp-refresh Worker's every-10-minute cron (workers/sharp-refresh/src/price-jobs.js), not by GitHub's
   schedule: trigger. run: node --test tests/sharp_refresh_price_jobs.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { PRICE_JOBS, dueJobs, runPriceJobs, parseCron, cronMatches, LINEUP_MAX_SCHEDULED, LINEUP_MAX_CLICK } from '../workers/sharp-refresh/src/price-jobs.js';

const wfPath = wf => new URL(`../.github/workflows/${wf}`, import.meta.url);
const due = iso => dueJobs(Date.parse(iso)).map(j => j.wf);

test('every migrated workflow has no schedule trigger, keeps workflow_dispatch and a concurrency group', () => {
  for (const j of PRICE_JOBS) {
    assert.ok(existsSync(wfPath(j.wf)), j.wf + ' exists');
    const y = readFileSync(wfPath(j.wf), 'utf8');
    assert.doesNotMatch(y, /^\s+schedule:/m, j.wf + ' must not carry a GitHub schedule (it would double-run)');
    assert.match(y, /^\s+workflow_dispatch:/m, j.wf + ' must accept workflow_dispatch');
    assert.match(y, /^concurrency:\n\s+group: \S+/m, j.wf + ' needs a concurrency group');
  }
});

test('the Worker keeps the exact crons the workflows used to carry', () => {
  for (const j of PRICE_JOBS) {
    const y = readFileSync(wfPath(j.wf), 'utf8');
    const m = y.match(/same UTC schedule: (.+)$/m);
    assert.ok(m, j.wf + ' records its old schedule');
    assert.deepEqual(m[1].split('; ').map(s => s.trim()), j.crons, j.wf);
  }
});

test('cron parsing', () => {
  assert.ok(cronMatches(parseCron('*/20 * * * *'), new Date('2026-11-25T22:40:00Z')));
  assert.ok(!cronMatches(parseCron('*/20 * * * *'), new Date('2026-11-25T22:41:00Z')));
  assert.ok(cronMatches(parseCron('0 13,17,21 * 9,10,11,12,1 2,3,5'), new Date('2026-11-25T21:00:00Z')));   // a Wednesday
  assert.ok(!cronMatches(parseCron('0 13,17,21 * 9,10,11,12,1 2,3,5'), new Date('2026-11-26T21:00:00Z')));  // Thursday
  assert.throws(() => parseCron('61 * * * *'));
  assert.throws(() => parseCron('* * * *'));
});

test('a job is due on the 10-minute tick that contains its minute', () => {
  for (const mm of ['00', '20', '40']) assert.ok(due(`2026-11-25T10:${mm}:00Z`).includes('nfl-book-tape.yml'));
  for (const mm of ['10', '30', '50']) assert.ok(!due(`2026-11-25T10:${mm}:00Z`).includes('nfl-book-tape.yml'));
  assert.deepEqual(due('2026-11-25T10:10:00Z'), ['update-props.yml']);
  assert.deepEqual(due('2026-11-25T10:20:00Z').sort(), ['nfl-book-tape.yml', 'update-game-history.yml', 'update-prop-history.yml'].sort());
  assert.deepEqual(due('2026-11-25T10:30:00Z'), ['update-kalshi.yml']);
  assert.deepEqual(due('2026-11-25T10:40:00Z').sort(), ['nfl-book-tape.yml', 'update-line-history.yml', 'update-polymarket.yml'].sort());
  assert.ok(due('2026-11-25T21:00:00Z').includes('update-lineup.yml'));
  assert.ok(!due('2026-11-25T22:00:00Z').includes('update-lineup.yml'));
  assert.ok(due('2026-07-01T09:00:00Z').includes('update-lineup.yml'));
  assert.ok(!due('2026-07-01T08:00:00Z').includes('update-lineup.yml'));
});

function lineupRuns(fromIso, toIso) {
  let n = 0;
  for (let t = Date.parse(fromIso); t < Date.parse(toIso); t += 600000) if (dueJobs(t).some(j => j.wf === 'update-lineup.yml')) n++;
  return n;
}
test('update-lineup keeps its ParlayAPI budget: 36 runs an in-season week, under the cap every month', () => {
  assert.equal(lineupRuns('2026-11-23T00:00:00Z', '2026-11-30T00:00:00Z'), 36);
  for (const [a, b] of [['2026-09-01', '2026-10-01'], ['2026-10-01', '2026-11-01'], ['2026-11-01', '2026-12-01'], ['2026-12-01', '2027-01-01'], ['2027-01-01', '2027-02-01'], ['2027-07-01', '2027-08-01']]) {
    const n = lineupRuns(a + 'T00:00:00Z', b + 'T00:00:00Z');
    assert.ok(n <= LINEUP_MAX_SCHEDULED && n * 6 <= 1000, `${a}: ${n} runs`);
  }
  assert.ok(LINEUP_MAX_CLICK < LINEUP_MAX_SCHEDULED);
});

function mockGitHub({ busy = {}, busyAt = '2026-11-25T10:35:00Z', monthRuns = 0, dispatchStatus = 204, runsError = {} } = {}) {
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), method: init.method || 'GET' });
    const u = new URL(url);
    const wf = u.pathname.split('/workflows/')[1]?.split('/')[0];
    if (u.pathname.endsWith('/dispatches')) return new Response(null, { status: dispatchStatus });
    const st = u.searchParams.get('status');
    if (st && runsError[wf]) return new Response('boom', { status: runsError[wf] });
    if (st) { const hit = busy[wf] === st; return Response.json({ total_count: hit ? 1 : 0, workflow_runs: hit ? [{ status: st, created_at: busyAt }] : [] }); }
    if (u.searchParams.get('created')) return Response.json({ total_count: monthRuns });
    return Response.json({});
  };
  return calls;
}
const env = { REPO: 'o/r', REF: 'main', GITHUB_TOKEN: 'test' };

test('runPriceJobs starts due jobs, skips busy ones, and stops update-lineup at the monthly cap', async () => {
  let calls = mockGitHub({ busy: { 'update-polymarket.yml': 'in_progress' } });
  const r = await runPriceJobs(env, Date.parse('2026-11-25T10:40:00Z'));
  assert.equal(r['nfl-book-tape.yml'], 'started');
  assert.equal(r['update-line-history.yml'], 'started');
  assert.equal(r['update-polymarket.yml'], 'skipped in_progress');
  assert.equal(calls.filter(c => c.method === 'POST').length, 2);

  mockGitHub({ monthRuns: LINEUP_MAX_SCHEDULED });
  const r2 = await runPriceJobs(env, Date.parse('2026-11-25T21:00:00Z'));
  assert.match(r2['update-lineup.yml'], /^skipped: 165 runs/);
  assert.equal(r2['nfl-book-tape.yml'], 'started');

  mockGitHub({ monthRuns: 10 });
  assert.equal((await runPriceJobs(env, Date.parse('2026-11-25T21:00:00Z')))['update-lineup.yml'], 'started');

  calls = mockGitHub();
  assert.deepEqual(await runPriceJobs({ ...env, PRICE_JOBS: 'off' }, Date.parse('2026-11-25T10:40:00Z')), { off: true });
  assert.equal(calls.length, 0);

  // A run stuck as "queued" for weeks (GitHub left one on update-polymarket from Oct 7) must not block the feed.
  mockGitHub({ busy: { 'update-polymarket.yml': 'queued' }, busyAt: '2026-10-07T16:57:41Z' });
  assert.equal((await runPriceJobs(env, Date.parse('2026-11-25T10:40:00Z')))['update-polymarket.yml'], 'started');

  // Fail closed: when the runs API errors we can't tell if a run is going, so skip (no dispatch) and say why.
  calls = mockGitHub({ runsError: { 'update-polymarket.yml': 502 } });
  const r3 = await runPriceJobs(env, Date.parse('2026-11-25T10:40:00Z'));
  assert.equal(r3['update-polymarket.yml'], 'skipped unknown (runs API 502)');
  assert.equal(r3['nfl-book-tape.yml'], 'started');
  assert.ok(!calls.some(c => c.method === 'POST' && c.url.includes('update-polymarket.yml')));
});
