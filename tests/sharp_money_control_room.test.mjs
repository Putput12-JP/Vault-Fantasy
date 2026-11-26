/* Control Room page logic: cadences, stale flags, trigger labels, and the markup.
   run: node --test tests/sharp_money_control_room.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

const require = createRequire(import.meta.url);
const CR = require('../sharp-money/control-room.js');

test('the nine jobs are present, with a workflow file and a how-it-runs line that mentions the Worker', () => {
  assert.equal(CR.JOBS.length, 9);
  assert.deepEqual(CR.JOBS.map(j => j.id), [
    'update-sharp-money', 'nfl-book-tape', 'update-props', 'update-prop-history',
    'update-game-history', 'update-kalshi', 'update-polymarket', 'update-line-history', 'update-lineup'
  ]);
  for (const j of CR.JOBS) {
    assert.match(j.wf, /\.yml$/);
    assert.ok(j.name);
    assert.match(j.how, /Worker/);
    assert.ok(j.howShort);
    assert.doesNotMatch(j.howShort, /\n/);
    assert.ok(j.howShort.length <= 36);
    assert.doesNotMatch(j.how, /\u2014|\u2013/);
    assert.doesNotMatch(j.howShort, /\u2014|\u2013/);
    assert.doesNotMatch(j.name, /\u2014|\u2013/);
  }
  assert.match(CR.JOBS[0].how, /sharp-refresh Cloudflare Worker/);
  assert.match(CR.JOBS[0].how, /10-minute tick/);
});

test('nfl-book-tape is due every 20 minutes on the Worker tick that contains that minute', () => {
  const j = CR.JOBS.find(x => x.id === 'nfl-book-tape');
  assert.ok(CR.jobDueAtTick(j, Date.parse('2026-11-25T10:00:00Z')));
  assert.ok(!CR.jobDueAtTick(j, Date.parse('2026-11-25T10:10:00Z')));
  assert.ok(CR.jobDueAtTick(j, Date.parse('2026-11-25T10:20:00Z')));
});

test('update-props is due on the :10 tick (the :17 UTC slot)', () => {
  const j = CR.JOBS.find(x => x.id === 'update-props');
  assert.ok(CR.jobDueAtTick(j, Date.parse('2026-11-25T10:10:00Z')));
  assert.ok(!CR.jobDueAtTick(j, Date.parse('2026-11-25T10:00:00Z')));
});

test('Sharp Money gate: busy Monday evening every 10 min, quiet overnight except 6 AM CT', () => {
  // Monday 25 May 2026 is a Monday. Use 2026-11-23 which is a Monday.
  // 23 Nov 2026 is Monday. 11pm UTC = 5pm CT, start of Mon busy window.
  assert.ok(CR.sharpGateOpen(Date.parse('2026-11-24T00:00:00Z')));  // Mon 6pm CT
  assert.ok(CR.sharpGateOpen(Date.parse('2026-11-24T05:00:00Z')));  // Mon 11pm CT
  // Tuesday 3am CT is quiet
  assert.ok(!CR.sharpGateOpen(Date.parse('2026-11-24T09:00:00Z')));
  // 6:00 AM CT daily
  assert.ok(CR.sharpGateOpen(Date.parse('2026-11-24T12:00:00Z')));
  // Tuesday 10:00 AM CT is a 30-minute slot (m < 10)
  assert.ok(CR.sharpGateOpen(Date.parse('2026-11-24T16:00:00Z')));
  // Tuesday 10:10 AM CT is not
  assert.ok(!CR.sharpGateOpen(Date.parse('2026-11-24T16:10:00Z')));
});

test('a job is stale when its last success is older than twice its cadence', () => {
  const tape = CR.JOBS.find(x => x.id === 'nfl-book-tape'); // 20 min cadence, stale after 40 min
  const now = Date.parse('2026-11-25T10:40:00Z');
  assert.equal(CR.isStale(tape, now / 1000 - 10 * 60, now), false);
  assert.equal(CR.isStale(tape, now / 1000 - 41 * 60, now), true);
  assert.equal(CR.isStale(tape, null, now), true);
});

test('next due job picks the soonest scheduled tick', () => {
  const now = Date.parse('2026-11-25T10:05:00Z'); // next tick :10 is update-props
  const n = CR.nextDueJob(now);
  assert.equal(n.job.id, 'update-props');
  assert.equal(n.at, Date.parse('2026-11-25T10:10:00Z'));
});

test('trigger labels distinguish schedule, Run now, Worker dispatch, and historical dispatch', () => {
  assert.equal(CR.triggerLabel({ ev: 'schedule' }), 'GitHub schedule');
  assert.equal(CR.triggerLabel({ ev: 'workflow_dispatch', title: 'Run now' }), 'Run now');
  assert.equal(CR.triggerLabel({ ev: 'workflow_dispatch', title: 'Worker dispatch' }), 'Worker dispatch');
  assert.equal(CR.triggerLabel({ ev: 'workflow_dispatch', title: 'Update Sharp Money', name: 'Update Sharp Money' }), 'Worker or Run now');
});

test('status pills and duration copy', () => {
  assert.match(CR.crStatus({ st: 'in_progress' }), /Running/);
  assert.match(CR.crStatus({ st: 'completed', c: 'success' }), /Success/);
  assert.match(CR.crStatus({ st: 'completed', c: 'cancelled' }), /Cancelled/);
  assert.match(CR.crStatus({ st: 'completed', c: 'failure' }), /Failed/);
  assert.equal(CR.durationLabel({ st: 'completed', t: 100, end: 125 }), '25 sec');
  assert.equal(CR.durationLabel({ st: 'completed', t: 100, end: 280 }), '3 min');
});

test('board counts use upcoming games and prop rows', () => {
  const now = 1_000_000;
  const c = CR.boardCounts({ ts: now - 60, games: [{ start: now + 10 }, { start: now - 10 }], props: { rows: [1, 2, 3] } }, now);
  assert.equal(c.games, 2);
  assert.equal(c.upcoming, 1);
  assert.equal(c.props, 3);
  assert.equal(c.ts, now - 60);
});

test('renderHtml is the NBA Control Room structure: tiles, pipelines table, recent runs, no em dash', () => {
  const html = CR.renderHtml({
    board: { ts: Date.now() / 1000 - 180, games: [{ start: Date.now() / 1000 + 3600, sport: 'nfl' }], props: { rows: [{}] } },
    onSite: true,
    nowMs: Date.now()
  });
  assert.match(html, /class="sm-cr"/);
  assert.match(html, /Price feeds/);
  assert.match(html, /Sharp board/);
  assert.match(html, /Sharp Money refresh/);
  assert.match(html, /Next due job/);
  assert.match(html, /<h2>Pipelines<\/h2>/);
  assert.match(html, /What keeps the board and the models fresh, and when each last ran/);
  assert.match(html, /<h2>Recent runs<\/h2>/);
  assert.match(html, /The last twelve runs of these jobs, newest first/);
  assert.match(html, /update-sharp-money\.yml/);
  assert.match(html, /data-run="update-props"/);
  assert.match(html, />Run now</);
  assert.match(html, /class="how-full"/);
  assert.match(html, /class="how-short"/);
  assert.match(html, /Busy windows, 10 to 30 min/);
  assert.match(html, /:10 past each hour/);
  assert.doesNotMatch(html, /\u2014|\u2013/);
  assert.match(html, /Board /);
});

test('the CSS and JS files exist and the CSS is scoped under .sm-cr', () => {
  const css = readFileSync(new URL('../sharp-money/control-room.css', import.meta.url), 'utf8');
  assert.match(css, /^\.sm-cr\{/m);
  assert.match(css, /\.sm-cr \.kpis/);
  assert.match(css, /\.sm-cr table\.nt/);
  assert.match(css, /how-short/);
  assert.match(css, /grid-template-areas:"job run" "how how" "last result"/);
  assert.match(css, /prefers-reduced-motion/);
  assert.doesNotMatch(css, /fonts\.googleapis\.com/);
  assert.doesNotMatch(css, /\u2014/);
});

test('a failed GitHub load does not mark every job stale', () => {
  const prev = { runs: CR._state.runs, err: CR._state.err, at: CR._state.at };
  try {
    CR._state.runs = null;
    CR._state.err = '403';
    const html = CR.renderHtml({ board: { ts: Date.now() / 1000 - 180, games: [], props: { rows: [] } }, onSite: true, nowMs: Date.now() });
    assert.match(html, /Could not load run history \(403\)/);
    assert.doesNotMatch(html, />\s*\d+ stale</);
    assert.doesNotMatch(html, /pill warn">Stale/);
    assert.match(html, /could not load run history/);
  } finally {
    CR._state.runs = prev.runs;
    CR._state.err = prev.err;
    CR._state.at = prev.at;
  }
});

test('a short update-sharp-money success is a gate skip and does not count as a refresh', () => {
  const now = 2_000_000;
  const skip = { flow: 'update-sharp-money', st: 'completed', c: 'success', t: now - 60, end: now - 50 }; // 10s
  const real = { flow: 'update-sharp-money', st: 'completed', c: 'success', t: now - 3600, end: now - 3600 + 8 * 60 };
  assert.equal(CR.isSharpRefresh(skip), false);
  assert.equal(CR.isSharpRefresh(real), true);
  const hit = CR.lastRefreshOf([skip, real]);
  assert.equal(hit.t, real.t);
  const board = { ts: now - 180 };
  const fallback = CR.lastRefreshOf([skip], board);
  assert.equal(fallback.t, board.ts);
  assert.equal(fallback.fromBoard, true);
});

test('feedStatus lists failed names separately from stale names', () => {
  const nowMs = Date.parse('2026-11-25T18:00:00Z');
  const now = nowMs / 1000;
  const runs = [
    { flow: 'update-kalshi', st: 'completed', c: 'failure', t: now - 60, end: now - 30 },
    { flow: 'nfl-book-tape', st: 'completed', c: 'success', t: now - 3 * 3600, end: now - 3 * 3600 + 20 }
  ];
  const s = CR.feedStatus(runs, nowMs, {});
  assert.match(s.value, /failed/);
  assert.match(s.hint, /Kalshi/);
  assert.doesNotMatch(s.hint, /book tape/i);
});
