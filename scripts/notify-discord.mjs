#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · DISCORD NOTIFIER  (shared by every job that wants to ping a channel)

   The webhook URL is a secret: it lives in the DISCORD_WEBHOOK_URL env var (a GitHub
   Actions secret), never in the repo. Anyone holding it can post to the channel.

   import { sendDiscord } from './notify-discord.mjs'
   await sendDiscord({ title, lines: [...], url, color })   -> { ok, status, skipped? }

   CLI test:  DISCORD_WEBHOOK_URL=... node scripts/notify-discord.mjs --test
   Never throws: a failed ping must not fail the data job that called it.
   ════════════════════════════════════════════════════════════════════════ */
import { fileURLToPath } from 'node:url';

const COLORS = { watch: 0xf5b800, go: 0x2ecc71, info: 0x5865f2, bad: 0xe74c3c };

export async function sendDiscord({ title, lines = [], url, color = 'info', username = 'Vault alerts', webhook = process.env.DISCORD_WEBHOOK_URL } = {}) {
  if (!webhook) return { ok: false, skipped: 'no DISCORD_WEBHOOK_URL' };
  const body = {
    username,
    allowed_mentions: { parse: [] },   // alert text can never @everyone
    embeds: [{
      title: String(title || 'Vault').slice(0, 256),
      description: lines.join('\n').slice(0, 4000),
      url: url || undefined,
      color: typeof color === 'number' ? color : (COLORS[color] ?? COLORS.info),
      timestamp: new Date().toISOString(),
    }],
  };
  try {
    const r = await fetch(webhook + (webhook.includes('?') ? '&' : '?') + 'wait=true', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (r.status === 429) {   // rate limited: honour retry_after once
      const j = await r.json().catch(() => ({}));
      await new Promise(s => setTimeout(s, Math.min(5000, (j.retry_after || 1) * 1000)));
      const r2 = await fetch(webhook, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      return { ok: r2.ok, status: r2.status };
    }
    return { ok: r.ok, status: r.status };
  } catch (e) { return { ok: false, error: e.message }; }
}

if (process.argv[1] === fileURLToPath(import.meta.url) && process.argv.includes('--test')) {
  const r = await sendDiscord({
    title: 'Vault alerts: connection test',
    lines: ['If you can read this, the webhook works.', 'Kalshi vs books gap alerts will post here (labeled **Watch**: unproven so far).'],
    color: 'watch',
  });
  console.log('discord test:', JSON.stringify(r));
  if (r.skipped) { console.error('DISCORD_WEBHOOK_URL is not set. Add it under repo Settings → Secrets and variables → Actions.'); process.exit(1); }
  process.exit(r.ok ? 0 : 1);
}
