// Vault NBA refresh trigger. Starts the recorder and the daily job on time and serves the page's Refresh button.
//   cron */10      -> recorder, unless a run is already in progress or queued (its own loop covers game windows)
//   cron 23 11     -> daily job
//   GET /board     -> the live board from the nba-live branch, with raw.githubusercontent's 5 minute CDN cache bypassed (30 s here)
//   POST {what}    -> a person asked: 'prices' (recorder) or 'daily'; a cooldown keeps it from being spammed

const ORIGINS = ['https://vaultfantasy.com', 'https://www.vaultfantasy.com', 'http://localhost:4173', 'http://localhost:8000'];
const FLOW = { prices: 'nba-snapshots.yml', daily: 'nba-daily.yml' };
const COOLDOWN_S = { prices: 60, daily: 300 };

const gh = (env, path, init = {}) => fetch(`https://api.github.com/repos/${env.REPO}/actions/${path}`, {
  ...init,
  headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'vault-nba-refresh' },
});

async function busy(env, wf) {
  for (const status of ['in_progress', 'queued']) {
    const r = await gh(env, `workflows/${wf}/runs?status=${status}&per_page=1`);
    if (r.ok && (await r.json()).total_count > 0) return status;
  }
  return null;
}

async function dispatch(env, what, force) {
  const wf = FLOW[what];
  if (!force) { const b = await busy(env, wf); if (b) return { ok: true, skipped: b }; }
  const r = await gh(env, `workflows/${wf}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: env.REF }) });
  return { ok: r.status === 204, status: r.status };
}

const cors = origin => ({
  'Access-Control-Allow-Origin': ORIGINS.includes(origin) ? origin : ORIGINS[0],
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  Vary: 'Origin',
});

export default {
  async scheduled(event, env) {
    const what = event.cron === '23 11 * * *' ? 'daily' : 'prices';
    const r = await dispatch(env, what, false);
    if (!r.ok) console.error('dispatch failed', what, r.status);
  },

  async fetch(req, env) {
    const origin = req.headers.get('Origin') || '';
    const h = { ...cors(origin), 'Content-Type': 'application/json' };
    const out = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: h });
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: h });
    if (req.method === 'GET' && new URL(req.url).pathname === '/board') {
      const r = await fetch(`https://raw.githubusercontent.com/${env.REPO}/nba-live/board.json?r=${Math.floor(Date.now() / 30000)}`, { cf: { cacheTtl: 30, cacheEverything: true } });
      return new Response(r.body, { status: r.status, headers: { ...h, 'Cache-Control': 'public, max-age=30' } });
    }
    if (req.method !== 'POST') return out({ ok: true, service: 'nba-refresh' });
    if (!ORIGINS.includes(origin)) return out({ ok: false, error: 'origin' }, 403);
    let what = 'prices';
    try { what = (await req.json()).what || 'prices'; } catch (e) { /* default */ }
    if (!FLOW[what]) return out({ ok: false, error: 'what' }, 400);

    const cache = caches.default, key = new Request(`https://nba-refresh.internal/cooldown/${what}`);
    if (await cache.match(key)) return out({ ok: false, error: 'cooldown', retry: COOLDOWN_S[what] }, 429);
    const r = await dispatch(env, what, true);
    if (r.ok) await cache.put(key, new Response('1', { headers: { 'Cache-Control': `max-age=${COOLDOWN_S[what]}` } }));
    return out({ ok: r.ok, status: r.status }, r.ok ? 202 : 502);
  },
};
