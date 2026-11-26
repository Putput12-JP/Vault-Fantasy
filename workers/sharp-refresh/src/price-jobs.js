// Price-feed jobs started by this Worker's */10 cron instead of GitHub's own scheduler.
// GitHub's schedule: trigger was firing these every 4-7 hours (Nov 2026, last 30-40 runs: median gap 274-520 min) when they
// were written for every 20-60 min. The Worker's cron is on time, so it calls workflow_dispatch on the same schedules.
// The scraping logic, outputs and commits are unchanged: each workflow still runs exactly as before, only the trigger moved.
//
// Each job keeps the cron string its workflow used to carry (UTC, standard 5 fields). The Worker ticks every 10 minutes, so
// a job is due on the tick whose 10-minute window [tick, tick + 10 min) contains a minute the cron matches. A ':17' job
// therefore starts at :10, a '*/20' job at :00, :20 and :40. No new Cloudflare cron triggers are needed (the free plan's 5
// per account are already 4 used: sharp-refresh 2, nba-refresh 2).

export const PRICE_JOBS = [
  { wf: 'nfl-book-tape.yml', crons: ['*/20 * * * *'] },
  { wf: 'update-props.yml', crons: ['17 * * * *'] },
  { wf: 'update-prop-history.yml', crons: ['27 * * * *'] },
  { wf: 'update-game-history.yml', crons: ['29 * * * *'] },
  { wf: 'update-kalshi.yml', crons: ['37 * * * *'] },
  { wf: 'update-polymarket.yml', crons: ['47 * * * *'] },
  { wf: 'update-line-history.yml', crons: ['47 * * * *'] },
  // ParlayAPI credits: 6 per run on the free 1,000 a month. Same 36 runs a week as before (see update-lineup.yml), plus the
  // monthly cap below, because on-time runs now spend the whole budget the schedule was sized for.
  { wf: 'update-lineup.yml', budget: true, crons: [
    '0 9 * 2,3,4,5,6,7,8 *',
    '0 8 * 9,10,11,12,1 *',
    '0 13,17,21 * 9,10,11,12,1 2,3,5',
    '0 16 * 9,10,11,12,1 6',
    '0 14,16,18,20,22,23 * 9,10,11,12,1 4',
    '0 13,14,15,16,18,19,20,22,23 * 9,10,11,12,1 0',
    '0 17,19,21,23 * 9,10,11,12,1 1',
  ] },
];

// update-lineup.yml runs in a UTC month, all events counted (schedule from here, Refresh clicks, manual runs).
// 166 runs x 6 credits = 996. The schedule tops out at 161 runs in a month, so 165 leaves it room; a Refresh click
// stops at 150 so clicks can never eat the scheduled runs' credits.
export const LINEUP_MAX_SCHEDULED = 165;
export const LINEUP_MAX_CLICK = 150;

const RANGES = [[0, 59], [0, 23], [1, 31], [1, 12], [0, 7]];
function field(spec, [lo, hi]) {
  const out = new Set();
  for (const part of spec.split(',')) {
    const [rng, stepS] = part.split('/');
    const step = stepS ? +stepS : 1;
    let a = lo, b = hi;
    if (rng !== '*') { const m = rng.split('-').map(Number); a = m[0]; b = m.length > 1 ? m[1] : (stepS ? hi : m[0]); }
    if (!(step > 0) || Number.isNaN(a) || Number.isNaN(b) || a < lo || b > hi || a > b) throw new Error('bad cron field: ' + spec);
    for (let v = a; v <= b; v += step) out.add(v);
  }
  return out;
}
export function parseCron(expr) {
  const f = expr.trim().split(/\s+/);
  if (f.length !== 5) throw new Error('cron needs 5 fields: ' + expr);
  const [mi, h, dom, mon, dow] = f.map((s, i) => field(s, RANGES[i]));
  if (dow.has(7)) dow.add(0);
  return { mi, h, dom, mon, dow, domAny: f[2] === '*', dowAny: f[4] === '*' };
}
export function cronMatches(c, d) {
  if (!c.mi.has(d.getUTCMinutes()) || !c.h.has(d.getUTCHours()) || !c.mon.has(d.getUTCMonth() + 1)) return false;
  const dm = c.dom.has(d.getUTCDate()), dw = c.dow.has(d.getUTCDay());
  // standard cron: when both day fields are restricted, either one matching is enough
  return c.domAny && c.dowAny ? true : c.domAny ? dw : c.dowAny ? dm : dm || dw;
}
const PARSED = PRICE_JOBS.map(j => ({ ...j, parsed: j.crons.map(parseCron) }));
export function dueJobs(tickMs, windowMin = 10) {
  const start = Math.floor(tickMs / 60000) * 60000;
  return PARSED.filter(j => {
    for (let i = 0; i < windowMin; i++) { const d = new Date(start + i * 60000); if (j.parsed.some(c => cronMatches(c, d))) return true; }
    return false;
  }).map(({ parsed, ...j }) => j);
}

const ghHeaders = env => ({ Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'vault-sharp-refresh' });
const gh = (env, path, init = {}) => fetch(`https://api.github.com/repos/${env.REPO}/actions/${path}`, { ...init, headers: ghHeaders(env) });

// A run already queued or running covers this tick: skip, so slow runs never pile up behind each other.
// Only runs created in the last BUSY_MAX_AGE_MIN count: GitHub can leave a run stuck as "queued" for weeks
// (update-polymarket has one from Oct 7), and that must not block the feed forever.
export const BUSY_MAX_AGE_MIN = 120;
async function busy(env, wf, nowMs = Date.now()) {
  for (const status of ['queued', 'in_progress']) {
    const r = await gh(env, `workflows/${wf}/runs?status=${status}&per_page=10`);
    // Fail closed: if GitHub can't tell us whether a run is going, skip this tick rather than risk a double run.
    if (!r.ok) { console.warn('busy check failed', wf, status, r.status); return `unknown (runs API ${r.status})`; }
    const runs = (await r.json()).workflow_runs || [];
    if (runs.some(x => nowMs - Date.parse(x.created_at) < BUSY_MAX_AGE_MIN * 60000)) return status;
  }
  return null;
}
export async function lineupRunsThisMonth(env, wf, nowMs) {
  const d = new Date(nowMs), since = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-01T00:00:00Z`;
  const r = await gh(env, `workflows/${wf}/runs?created=${encodeURIComponent('>=' + since)}&per_page=1`);
  if (!r.ok) return null;
  return (await r.json()).total_count;
}
async function start(env, wf) {
  const r = await gh(env, `workflows/${wf}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: env.REF }) });
  return r.status === 204 ? 'started' : 'error ' + r.status;
}

// Runs on every */10 tick. Returns { workflow: outcome } for the log. Never throws: one failed job never blocks the rest.
export async function runPriceJobs(env, tickMs) {
  if (env.PRICE_JOBS === 'off') return { off: true };
  const out = {};
  for (const j of dueJobs(tickMs)) {
    try {
      const b = await busy(env, j.wf, tickMs);
      if (b) { out[j.wf] = 'skipped ' + b; continue; }
      if (j.budget) {
        const n = await lineupRunsThisMonth(env, j.wf, tickMs);
        if (n == null) { out[j.wf] = 'skipped: run count unreadable'; continue; }
        if (n >= LINEUP_MAX_SCHEDULED) { out[j.wf] = `skipped: ${n} runs this month (cap ${LINEUP_MAX_SCHEDULED})`; continue; }
      }
      out[j.wf] = await start(env, j.wf);
    } catch (e) { out[j.wf] = 'error ' + (e && e.message || e); }
  }
  return out;
}
