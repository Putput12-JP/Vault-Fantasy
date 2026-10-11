// Sharp Money refresh trigger. GitHub's own cron drops runs, so this Worker calls
// workflow_dispatch on a schedule instead, and also serves the page's Refresh button.
//   cron  -> force=false: the workflow gate skips quiet hours / off-cadence slots
//   POST  -> force=true:  a person asked, run now (cooldown below keeps it from being spammed)

const ORIGINS = ['https://vaultfantasy.com', 'https://www.vaultfantasy.com', 'http://localhost:8000', 'http://127.0.0.1:8000'];
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
    const d = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/${env.LINEUP_WORKFLOW}/dispatches`, { method: 'POST', headers: gh, body: JSON.stringify({ ref: env.REF }) });
    return d.status === 204 ? 'started' : 'error';
  } catch { return 'error'; }
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
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  Vary: 'Origin',
});

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
  },

  async fetch(req, env) {
    const origin = req.headers.get('Origin') || '';
    const h = { ...cors(origin), 'Content-Type': 'application/json' };
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: h });
    if (req.method !== 'POST') return new Response(JSON.stringify({ ok: true, service: 'sharp-refresh' }), { headers: h });
    if (!ORIGINS.includes(origin)) return new Response(JSON.stringify({ ok: false, error: 'origin' }), { status: 403, headers: h });

    // Per-colo cooldown. Best effort, and GitHub's own concurrency group queues anything that slips through.
    const cache = caches.default;
    const key = new Request('https://sharp-refresh.internal/cooldown');
    const hit = await cache.match(key);
    if (hit) {
      const left = Number(hit.headers.get('X-Left')) || COOLDOWN_S;
      return new Response(JSON.stringify({ ok: false, error: 'cooldown', retry: left }), { status: 429, headers: h });
    }
    const r = await dispatch(env, true);
    if (r.ok) await cache.put(key, new Response('1', { headers: { 'Cache-Control': `max-age=${COOLDOWN_S}`, 'X-Left': String(COOLDOWN_S) } }));
    const lineup = r.ok ? await maybeLineup(env) : 'skipped';
    return new Response(JSON.stringify({ ok: r.ok, status: r.status, lineup }), { status: r.ok ? 202 : 502, headers: h });
  },
};
