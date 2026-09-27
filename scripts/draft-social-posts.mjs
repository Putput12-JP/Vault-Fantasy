#!/usr/bin/env node
// Drafts @vaultfantasy26 posts and sends them to a private Discord channel for
// approval. Nothing is ever posted to X from here: each Discord message carries
// the draft text and a "Post to X" link that opens X's composer pre-filled, so a
// post only goes out when a human taps it and hits Post.
//
//   --mode=preview   Vault's Best Bets for the next slate, before kickoff.
//                    Only picks kicking off within --hours (default 36) are used,
//                    so a Thursday run drafts TNF and a Sunday run drafts Sun+Mon.
//   --mode=recap     Grades every pick drafted in a preview for --week (default:
//                    the latest previewed week) against the settled box scores in
//                    data/bet_results.json, plus the week's A/B record. Waits
//                    until every pick has settled.
//   --dry            Print the drafts, don't send or record anything.
//
// State: data/social_posts.json remembers what was drafted, so the recap grades
// exactly the picks that were shown (not whatever Best Bets says later) and no
// slate is drafted twice. Env: DISCORD_WEBHOOK_URL (repo secret). Missing
// webhook = print only, exit 0, so the cron never fails on setup.

import fs from 'node:fs';

const args = Object.fromEntries(process.argv.slice(2).map(a => { const [k, v] = a.replace(/^--/, '').split('='); return [k, v ?? true]; }));
const MODE = args.mode || 'preview';
const DRY = !!args.dry;
const HOURS = Number(args.hours || 36);
const FEED = args.feed || 'data/lineup-feed.json';
const LEDGER = args.ledger || 'data/bet_results.json';
const STATE = args.state || 'data/social_posts.json';
const SITE = 'vaultfantasy.com';
const RECORD_URL = `https://${SITE}/record.html`;
const HANDLE = '@vaultfantasy26';
const WEBHOOK = process.env.DISCORD_WEBHOOK_URL || '';

const readJSON = (p, d) => { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return d; } };
const state = readJSON(STATE, { posts: [] });
const MK = { rec: 'rec', rec_yd: 'rec yds', rush_yd: 'rush yds', rush_att: 'rush att', rush_rec_yd: 'rush+rec yds', pass_yd: 'pass yds', pass_td: 'pass TD', pass_att: 'pass att', pass_cmp: 'completions', pass_int: 'INT', pass_rush_yd: 'pass+rush yds', anytime_td: 'anytime TD', rush_td: 'rush TD', rec_td: 'rec TD' };
const odds = a => a == null ? '' : (a > 0 ? '+' : '') + a;
const pays = a => a > 0 ? a / 100 : 100 / -a;
const short = n => { const p = String(n).split(' '); return p.length > 1 ? p.slice(1).join(' ') : n; };   // "Dawson Knox" -> "Knox"
const pickTxt = p => `${p.name} ${p.side === 'under' ? 'u' : 'o'}${p.line} ${MK[p.market] || p.marketLabel || p.market}`;

// X counts every URL as 23 characters. Keep drafts under 280 by dropping lines
// from the end (never mid-line) and saying how many were left out.
function fitTweet(head, lines, tail) {
  const len = s => s.replace(/https?:\/\/\S+/g, 'x'.repeat(23)).length;
  let use = lines.slice();
  const build = (ls, extra) => [head, ...ls, ...(extra ? [extra] : []), '', tail].join('\n');
  while (use.length && len(build(use, lines.length > use.length ? `+${lines.length - use.length} more on the board` : '')) > 280) use.pop();
  return build(use, lines.length > use.length ? `+${lines.length - use.length} more on the board` : '');
}

async function send(title, text, footer) {
  const intent = 'https://x.com/intent/post?text=' + encodeURIComponent(text);
  const body = {
    username: 'Vault post drafts',
    content: `**${title}** · draft for ${HANDLE}, not posted yet`,
    embeds: [{
      description: '```\n' + text + '\n```\n' + `**[Post to X →](${intent})**` + '\nOpens X with this text filled in. Edit it there if you like, then hit Post. Ignore this message to skip.',
      footer: { text: footer },
      color: 0x2f63c4,
    }],
  };
  if (DRY || !WEBHOOK) {
    console.log(`\n--- ${title} (${DRY ? 'dry run' : 'no DISCORD_WEBHOOK_URL set'}) ---\n${text}\n[${text.length} chars]\n${intent}\n`);
    return !DRY && !WEBHOOK ? false : true;
  }
  const r = await fetch(WEBHOOK, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`Discord webhook ${r.status}: ${await r.text()}`);
  console.log(`Sent "${title}" to Discord.`);
  return true;
}

function saveState() { if (!DRY) fs.writeFileSync(STATE, JSON.stringify(state, null, 2) + '\n'); }

async function preview() {
  const feed = readJSON(FEED, null);
  const bb = feed && feed.best_bets;
  if (!bb || !Array.isArray(bb.props) || !bb.props.length) { console.log('No Best Bets in the feed; nothing to draft.'); return; }
  const now = Date.now(), until = now + HOURS * 3600e3;
  const games = feed.vegas_games || [];
  const weekOf = p => {
    const g = games.find(x => (x.home === p.team || x.away === p.team) && x.commence === p.commence);
    return g && g.week != null ? g.week : bb.week;
  };
  const picks = bb.props.filter(p => { const t = Date.parse(p.commence); return Number.isFinite(t) && t > now && t <= until; })
    .map(p => ({ id: p.id, name: p.name, team: p.team, opp: p.opp, market: p.market, marketLabel: p.marketLabel, line: p.line, side: p.side, price: p.price, book: p.book, grade: p.grade, ev: p.ev, commence: p.commence, week: weekOf(p) }));
  if (!picks.length) { console.log(`No Best Bets kick off in the next ${HOURS}h; nothing to draft.`); return; }
  const season = String(bb.season || feed.season || '');
  const week = picks[0].week;
  // one preview per slate: the set of kickoff days covered
  const days = [...new Set(picks.map(p => new Date(p.commence).toLocaleDateString('en-US', { weekday: 'short', timeZone: 'America/New_York' })))];
  const key = `preview-${season}-w${week}-${days.join('')}`;
  if (state.posts.some(x => x.key === key)) { console.log(`Already drafted ${key}; skipping.`); return; }
  const text = fitTweet(`Vault's Week ${week} Best Bets 🏈`, picks.map(p => `• ${pickTxt(p)} (${odds(p.price)})`),
    `Graded before kickoff, settled in public, win or lose: ${RECORD_URL}`);
  const ok = await send(`Week ${week} preview (${days.join(' + ')})`, text, `${picks.length} Best Bets · best price at time of drafting · lines move, check before posting`);
  if (ok) { state.posts.push({ key, kind: 'preview', season, week, sent_at: new Date().toISOString(), picks }); saveState(); }
}

async function recap() {
  const previews = state.posts.filter(x => x.kind === 'preview');
  if (!previews.length) { console.log('No previews drafted yet; nothing to recap.'); return; }
  const season = args.season ? String(args.season) : previews[previews.length - 1].season;
  const week = args.week != null ? Number(args.week) : Math.max(...previews.filter(x => x.season === season).map(x => x.week));
  const key = `recap-${season}-w${week}`;
  if (state.posts.some(x => x.key === key)) { console.log(`Already drafted ${key}; skipping.`); return; }
  const picks = previews.filter(x => x.season === season && x.week === week).flatMap(x => x.picks);
  const ledger = readJSON(LEDGER, null);
  if (!ledger || !ledger.props) { console.log('No ledger; cannot settle yet.'); return; }
  const nn = s => String(s || '').toLowerCase().replace(/[^a-z]/g, '');
  const settled = picks.map(p => {
    const row = ledger.props.find(x => String(x.season) === season && x.week === week && x.market === p.market
      && ((p.id && String(x.pid) === String(p.id)) || nn(x.name) === nn(p.name)) && x.actual != null);
    if (!row) return { ...p, res: null };
    const a = Number(row.actual);
    const res = a === p.line ? 'P' : (p.side === 'under' ? a < p.line : a > p.line) ? 'W' : 'L';
    return { ...p, actual: a, res };
  });
  const open = settled.filter(p => !p.res);
  if (open.length) { console.log(`${open.length} of ${settled.length} Week ${week} picks not settled yet (${open.map(p => p.name).join(', ')}); waiting.`); return; }
  const W = settled.filter(p => p.res === 'W').length, L = settled.filter(p => p.res === 'L').length;
  const units = settled.reduce((t, p) => t + (p.res === 'W' ? pays(p.price) : p.res === 'L' ? -1 : 0), 0);
  const u = (units >= 0 ? '+' : '') + units.toFixed(1) + 'u';
  const lines = settled.map(p => `${p.res === 'W' ? '✅' : p.res === 'L' ? '❌' : '➖'} ${short(p.name)} ${p.side === 'under' ? 'u' : 'o'}${p.line} ${MK[p.market] || p.market}, had ${p.actual}`);
  // The week's full A/B record from the public ledger, so the recap never
  // shows only the posted picks.
  const ab = ledger.props.filter(x => String(x.season) === season && x.week === week && (x.grade === 'A' || x.grade === 'B') && !x.push && x.won_close != null);
  const abW = ab.filter(x => x.won_close).length;
  const head = `Week ${week} Best Bets: ${W}-${L} (${u})` + (ab.length ? `\nAll A/B grades: ${abW}-${ab.length - abW}` : '');
  const text = fitTweet(head, lines, `Every graded prop, win or lose: ${RECORD_URL}`);
  const ok = await send(`Week ${week} recap`, text, `${W}-${L}, ${u} at the drafted prices · A/B record from the public ledger`);
  if (ok) { state.posts.push({ key, kind: 'recap', season, week, sent_at: new Date().toISOString(), record: { W, L, units: +units.toFixed(2) } }); saveState(); }
}

(MODE === 'recap' ? recap() : preview()).catch(e => { console.error(e.message || e); process.exit(1); });
