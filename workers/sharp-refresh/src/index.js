// Sharp Money refresh trigger. GitHub's own cron drops runs, so this Worker calls
// workflow_dispatch on a schedule instead, and also serves the page's Refresh button.
//   cron  -> force=false: the workflow gate skips quiet hours / off-cadence slots
//   cron */10 also starts the price-feed workflows on their old schedules (price-jobs.js); their GitHub schedule: triggers are removed
//   POST  -> force=true:  a person asked, after Turnstile, and the Gate object is not in its cooldown

import { runPriceJobs, lineupRunsThisMonth, LINEUP_MAX_CLICK } from './price-jobs.js';

const ORIGINS = ['https://vaultfantasy.com', 'https://www.vaultfantasy.com', 'http://localhost:8000', 'http://127.0.0.1:8000', 'http://localhost:4173', 'http://127.0.0.1:4173'];
const COOLDOWN_S = 60;

// The US books (DraftKings, FanDuel, ...) only come from the ParlayAPI job (update-lineup.yml), which costs credits per run.
// A Refresh click starts it too, but never twice inside LINEUP_COOLDOWN_S, so clicking can not drain the credit budget.
const LINEUP_COOLDOWN_S = 45 * 60;
async function maybeLineup(env) {
  if (!env.LINEUP_WORKFLOW) return 'off';
  const gh = { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'vault-sharp-refresh' };
  try {
    const r = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/${env.LINEUP_WORKFLOW}/runs?per_page=1`, { headers: gh });
    if (r.ok) {
      const last = (await r.json()).workflow_runs?.[0];
      if (last && (Date.now() - Date.parse(last.created_at)) / 1000 < LINEUP_COOLDOWN_S) return 'recent';
    }
    // The cron now starts this workflow on time (price-jobs.js), so the month's credits are really spent: a click stops below the cap
    // the scheduled runs use, so clicking can never take the scheduled runs' credits.
    const n = await lineupRunsThisMonth(env, env.LINEUP_WORKFLOW, Date.now());
    if (n == null || n >= LINEUP_MAX_CLICK) return 'budget';
    const d = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/${env.LINEUP_WORKFLOW}/dispatches`, { method: 'POST', headers: gh, body: JSON.stringify({ ref: env.REF }) });
    return d.status === 204 ? 'started' : 'error';
  } catch { return 'error'; }
}


// Named jobs the Control Room "Run now" button may start. A Refresh click (no job field) still starts
// update-sharp-money plus maybeLineup, unchanged. Unknown job names are rejected.
export const CLICK_JOBS = {
  'update-sharp-money': { wf: 'update-sharp-money.yml', force: true },
  'nfl-book-tape': { wf: 'nfl-book-tape.yml' },
  'update-props': { wf: 'update-props.yml' },
  'update-prop-history': { wf: 'update-prop-history.yml' },
  'update-game-history': { wf: 'update-game-history.yml' },
  'update-kalshi': { wf: 'update-kalshi.yml' },
  'update-polymarket': { wf: 'update-polymarket.yml' },
  'update-line-history': { wf: 'update-line-history.yml' },
  'update-lineup': { wf: 'update-lineup.yml', lineup: true },
};

async function dispatchNamed(env, job) {
  const spec = CLICK_JOBS[job];
  if (!spec) return { ok: false, error: 'job', status: 400 };
  if (spec.lineup) {
    const lineup = await maybeLineup(env);
    const ok = lineup === 'started';
    const status = lineup === 'started' ? 204 : lineup === 'recent' || lineup === 'budget' ? 409 : 502;
    return { ok, status, lineup };
  }
  // Only send inputs the workflow actually declares. On main, the eight price
  // jobs have workflow_dispatch: {} (no inputs). Sending source:click would 422
  // until those ymls declare it. update-sharp-money already declares force.
  const body = { ref: env.REF };
  if (spec.force) body.inputs = { force: 'true' };
  const r = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/${spec.wf}/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'vault-sharp-refresh',
    },
    body: JSON.stringify(body),
  });
  return { ok: r.status === 204, status: r.status };
}

async function dispatch(env, force) {
  const r = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'vault-sharp-refresh',
    },
    body: JSON.stringify({ ref: env.REF, inputs: { force: force ? 'true' : 'false' } }),
  });
  return { ok: r.status === 204, status: r.status };
}

const cors = origin => ({
  'Access-Control-Allow-Origin': ORIGINS.includes(origin) ? origin : ORIGINS[0],
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  Vary: 'Origin',
});

// One cooldown for every visitor, not one per Cloudflare colo. The page's Refresh button
// claims it only after Turnstile accepts the token. Cron never touches this object.
export class Gate {
  constructor(state) { this.storage = state.storage; }
  async fetch(req) {
    const now = Date.now();
    const until = (await this.storage.get('until')) || 0;
    if (until > now) return Response.json({ ok: false, retry: Math.ceil((until - now) / 1000) }, { status: 429 });
    if (req.method !== 'POST') return Response.json({ ok: true, retry: 0 });
    await this.storage.put('until', now + COOLDOWN_S * 1000);
    return Response.json({ ok: true });
  }
}

async function siteverify(env, token, ip) {
  const body = new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: token || '' });
  if (ip) body.set('remoteip', ip);
  const r = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body });
  const j = await r.json().catch(() => ({}));
  return !!j.success;
}

// Kalshi-vs-books gap alerts: a light job (~1 min) dispatched every 2 min, only while NFL lines are moving. Same windows as the
// Sharp Money gate (Central): Mon/Thu 5-11pm, Sat 10am-11pm, Sun 8am-8pm. Outside them there is nothing worth alerting on.
const KB_CRON = '*/2 * * * *';
function nflBusyNow() {
  const p = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', weekday: 'short', hour: 'numeric', hourCycle: 'h23' })
    .formatToParts(new Date()).map(x => [x.type, x.value]));
  const h = +p.hour;
  return p.weekday === 'Mon' || p.weekday === 'Thu' ? h >= 17 : p.weekday === 'Sat' ? h >= 10 : p.weekday === 'Sun' ? h >= 8 && h <= 19 : false;
}
async function dispatchKb(env) {
  const r = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/${env.KB_WORKFLOW}/dispatches`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'vault-sharp-refresh' },
    body: JSON.stringify({ ref: env.REF }),
  });
  return { ok: r.status === 204, status: r.status };
}

export default {
  async scheduled(event, env, ctx) {
    if (event.cron === KB_CRON) {
      if (!env.KB_WORKFLOW || !nflBusyNow()) return;
      const k = await dispatchKb(env);
      if (!k.ok) console.error('kb dispatch failed', k.status);
      return;
    }
    const r = await dispatch(env, false);
    if (!r.ok) console.error('dispatch failed', r.status);
    // Price feeds: started here, on time, instead of by GitHub's schedule: trigger (which fired them every 4-7 hours).
    const p = await runPriceJobs(env, event.scheduledTime || Date.now());
    if (Object.keys(p).length) console.log('price jobs', JSON.stringify(p));
  },

  async fetch(req, env) {
    const origin = req.headers.get('Origin') || '';
    const url = new URL(req.url);
    const h = { ...cors(origin), 'Content-Type': 'application/json' };
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: h });
    if (req.method === 'GET' && url.pathname === '/sitekey') {
      if (origin && !ORIGINS.includes(origin)) return new Response(JSON.stringify({ ok: false, error: 'origin' }), { status: 403, headers: h });
      return new Response(JSON.stringify({ sitekey: env.TURNSTILE_SITEKEY || null }), {
        headers: { ...h, 'Cache-Control': 'public, max-age=300' },
      });
    }
    if (req.method !== 'POST') return new Response(JSON.stringify({ ok: true, service: 'sharp-refresh' }), { headers: h });
    if (!ORIGINS.includes(origin)) return new Response(JSON.stringify({ ok: false, error: 'origin' }), { status: 403, headers: h });
    // Fail closed. Cron (scheduled) does not come through here and stays unauthenticated.
    if (!env.TURNSTILE_SECRET || !env.GATE) return new Response(JSON.stringify({ ok: false, error: 'unconfigured' }), { status: 503, headers: h });
    let token = '', job = '';
    try { const body = await req.json(); token = body.token || ''; job = body.job || ''; } catch { token = ''; }
    if (job && !CLICK_JOBS[job]) return new Response(JSON.stringify({ ok: false, error: 'job' }), { status: 400, headers: h });
    const ok = await siteverify(env, token, req.headers.get('CF-Connecting-IP') || '');
    if (!ok) return new Response(JSON.stringify({ ok: false, error: 'turnstile' }), { status: 403, headers: h });
    const gateName = job ? 'sharp-refresh-' + job : 'sharp-refresh';
    const gate = await env.GATE.get(env.GATE.idFromName(gateName)).fetch('https://gate/claim', { method: 'POST' });
    if (gate.status === 429) {
      const j = await gate.json().catch(() => ({}));
      return new Response(JSON.stringify({ ok: false, error: 'cooldown', retry: j.retry || COOLDOWN_S }), { status: 429, headers: h });
    }
    if (job) {
      const r = await dispatchNamed(env, job);
      const status = r.error === 'job' ? 400 : r.status === 409 ? 409 : r.ok ? 202 : 502;
      return new Response(JSON.stringify({ ok: r.ok, status: r.status, lineup: r.lineup, error: r.error || undefined }), { status, headers: h });
    }
    const r = await dispatch(env, true);
    const lineup = r.ok ? await maybeLineup(env) : 'skipped';
    return new Response(JSON.stringify({ ok: r.ok, status: r.status, lineup }), { status: r.ok ? 202 : 502, headers: h });
  },
};
