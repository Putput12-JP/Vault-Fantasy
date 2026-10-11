#!/usr/bin/env node
/* ════════════════════════════════════════════════════════════════════════
   VAULT · KALSHI vs BOOKS GAP ALERTS  (runs in the Sharp Money job, every 10-30 min)

   The Sharp Money page grades one rule: when Kalshi lists a prop at the SAME number as the
   books and its P(over) is 5+ points off the books' no-vig median, whose side wins? Those
   rows used to be built hourly-ish by build_best_bets. This runs the same rule on the fresh
   Kalshi + book prices the job just pulled, and posts each NEW gap to Discord.

     in   <dir>/kalshi_props.json, <dir>/lineup-feed.json        (fresh copies the job wrote)
          <dir>/kb_state.json                                     (what was already posted)
     out  <dir>/kb_gaps.json     every gap open right now, with the age of its prices
          <dir>/kb_state.json    carried between runs on the sharp-data branch
          Discord               one message per run, new gaps only

   Same definition as the graded signal: a liquid Kalshi strike within 0.25 of the line
   (never an interpolated one), real books only (no PrizePicks / Underdog / Sleeper),
   power-devigged median, pregame, on the served slate. Labeled WATCH until the tracker
   has 50 graded games (see docs/retro/model-scoreboard.md).

   Nothing posts on old prices: Kalshi and the Pinnacle/pick'em feed must be under 30 min
   old, the US books under 90 (the same limits the Props board uses). A gap on stale
   prices is the phantom this whole page exists to avoid.

   Usage: node scripts/kalshi-book-gaps.mjs --dir=sharp-out [--dry] [--min=0.05]
   ════════════════════════════════════════════════════════════════════════ */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { sharpFairFor, devigPower, isRealBook } from './build_best_bets.mjs';
import { sendDiscord } from './notify-discord.mjs';

const ARG = Object.fromEntries(process.argv.slice(2).map(a => { const [k, v] = a.replace(/^--/, '').split('='); return [k, v ?? true]; }));
const DIR = resolve(process.cwd(), ARG.dir || 'sharp-out');
const DRY = !!ARG.dry;
const MIN_GAP = Number(ARG.min) || 0.05;      // the graded rule
const CLEAR_GAP = MIN_GAP - 0.015;            // a gap must fall this far before it can re-alert (no 4.9 / 5.1 flapping)
const FRESH_S = 30 * 60, FRESH_US_S = 90 * 60;
const MAX_LINES = 8;                          // lines per Discord message; the rest are counted
const SITE = 'https://vaultfantasy.com/sharp-money/';
const LABEL = {
  rec_yd: 'rec yds', rec: 'receptions', rush_yd: 'rush yds', rush_att: 'rush att', pass_yd: 'pass yds', pass_td: 'pass TDs',
  pass_att: 'pass att', pass_cmp: 'completions', pass_int: 'INTs', pass_rush_yd: 'pass+rush yds', rush_rec_yd: 'rush+rec yds', anytime_td: 'anytime TD',
};

const rj = f => { try { return JSON.parse(readFileSync(f, 'utf8')); } catch { return null; } };
const median = a => { const s = [...a].sort((x, y) => x - y); return s.length % 2 ? s[s.length >> 1] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2; };
const ageS = (iso, now) => { const t = Date.parse(iso || ''); return Number.isFinite(t) ? (now - t) / 1000 : Infinity; };
const pct = x => Math.round(x * 100) + '%';
const human = s => s < 90 * 60 ? Math.max(1, Math.round(s / 60)) + ' min' : s < 36 * 3600 ? (s / 3600).toFixed(1) + ' h' : Math.round(s / 86400) + ' d';

export function findGaps({ feed, kalshi, now = Date.now(), min = MIN_GAP }) {
  const gaps = [];
  const kick = {};
  for (const g of feed.vegas_games || []) {
    if (!g?.home || !g?.away || !g.commence) continue;
    if (feed.week != null && g.week != null && Number(g.week) !== Number(feed.week)) continue;
    kick[[g.home, g.away].sort().join('|')] = g.commence;
  }
  for (const [id, p] of Object.entries(feed.vegas_player_props || {})) {
    if (!p.team || !p.opp || p.out || p.impacted) continue;
    const commence = kick[[p.team, p.opp].sort().join('|')] || p.commence;
    if (!(Date.parse(commence || '') > now)) continue;                       // pregame only
    for (const mk of Object.keys(p.lines || {})) {
      const byLine = new Map();
      for (const q of p.lines[mk].quotes || []) {
        if (!q || q.line == null || q.over == null || q.under == null || !isRealBook(q.book) || String(q.book).toLowerCase() === 'kalshi') continue;
        const L = Number(q.line); if (!Number.isFinite(L)) continue;
        (byLine.get(L) || byLine.set(L, []).get(L)).push(q);
      }
      for (const [line, qs] of byLine) {
        const sharp = sharpFairFor(kalshi, p.name, mk, line);
        if (!sharp || sharp.interp) continue;                                // same number only
        const fairs = qs.map(q => devigPower(q.over, q.under)).filter(x => x != null);
        if (!fairs.length) continue;
        const books = median(fairs), gap = sharp.over - books;
        if (Math.abs(gap) < min) continue;
        const over = gap > 0;
        gaps.push({
          key: [feed.season, feed.week, id, mk, line, over ? 'over' : 'under'].join('|'),
          pid: id, name: p.name, team: p.team, opp: p.opp, market: mk, line, side: over ? 'over' : 'under',
          kalshi: +sharp.over.toFixed(3), books: +books.toFixed(3), nBooks: fairs.length, gap: +Math.abs(gap).toFixed(3),
          oi: sharp.oi, commence,
        });
      }
    }
  }
  return gaps.sort((a, b) => b.gap - a.gap);
}

export function pickNew(gaps, state, now) {
  const open = state.open || {}, next = {}, fresh = [];
  for (const g of gaps) {
    if (open[g.key]) next[g.key] = { ...open[g.key], seen: now, gap: g.gap };
    else { next[g.key] = { first: now, seen: now, gap: g.gap }; fresh.push(g); }
  }
  // a gap that dipped under the threshold but not under the clear line stays "open", so it can't re-alert on a wobble
  for (const [k, v] of Object.entries(open)) if (!next[k] && v.gap - 0.005 >= CLEAR_GAP && now - v.seen < 40 * 60 * 1000) next[k] = v;
  return { fresh, open: next };
}

function line(g, now) {
  const ov = g.side === 'over', bookSide = ov ? g.books : 1 - g.books, kalSide = ov ? g.kalshi : 1 - g.kalshi;
  const ko = Date.parse(g.commence) / 1000 - now / 1000;
  return `**${g.name}** ${ov ? 'Over' : 'Under'} ${g.line} ${LABEL[g.market] || g.market} · ${g.team} vs ${g.opp}\n`
    + `Kalshi ${pct(kalSide)} · books ${pct(bookSide)} (${g.nBooks} book${g.nBooks > 1 ? 's' : ''}) · **${Math.round(g.gap * 100)} pts apart** · kickoff in ${human(ko)}`;
}

async function main() {
  const now = Date.now();
  const feed = rj(resolve(DIR, 'lineup-feed.json')), kalshi = rj(resolve(DIR, 'kalshi_props.json'));
  const state = rj(resolve(DIR, 'kb_state.json')) || { open: {} };
  if (!feed || !kalshi) { console.log('kb-gaps: inputs missing, nothing to do'); return; }

  const age = {
    kalshi: ageS(kalshi.generated, now), pinnacle: ageS(feed.vegas_meta?.props_pp_generated || feed.generated, now), books: ageS(feed.generated, now),
  };
  const stale = [];
  if (age.kalshi > FRESH_S) stale.push('Kalshi ' + human(age.kalshi));
  if (age.pinnacle > FRESH_S) stale.push('Pinnacle ' + human(age.pinnacle));
  if (age.books > FRESH_US_S) stale.push('US books ' + human(age.books));

  const gaps = findGaps({ feed, kalshi, now });
  const { fresh, open } = pickNew(gaps, state, now);
  const out = { generated: new Date(now).toISOString(), minGap: MIN_GAP, ageSec: { kalshi: Math.round(age.kalshi), pinnacle: Math.round(age.pinnacle), books: Math.round(age.books) }, stale, gaps };
  console.log(`kb-gaps: ${gaps.length} open, ${fresh.length} new${stale.length ? ', STALE: ' + stale.join(', ') : ''}`);
  if (DRY) { for (const g of fresh) console.log('  +', line(g, now).replace(/\n/g, ' | ')); return; }
  writeFileSync(resolve(DIR, 'kb_gaps.json'), JSON.stringify(out));

  if (stale.length) { writeFileSync(resolve(DIR, 'kb_state.json'), JSON.stringify({ open: state.open || {}, updated: out.generated })); return; }   // hold: neither post nor mark anything as seen
  const save = o => writeFileSync(resolve(DIR, 'kb_state.json'), JSON.stringify({ open: o, updated: out.generated }));
  if (!fresh.length) { save(open); return; }
  const shown = fresh.slice(0, MAX_LINES);
  const r = await sendDiscord({
    title: `WATCH · ${fresh.length} new Kalshi vs books gap${fresh.length > 1 ? 's' : ''}`,
    url: SITE, color: 'watch',
    lines: [
      ...shown.map(g => line(g, now)),
      ...(fresh.length > shown.length ? [`+${fresh.length - shown.length} more on the page`] : []),
      '',
      `Bet the side Kalshi prices higher, at the books' price. Prices read ${human(Math.max(age.kalshi, age.pinnacle))} ago; **check the number on your book first**.`,
      `Unproven: Kalshi's side has won 6 of 11 (needs 50 games), so keep stakes small.`,
    ],
  });
  console.log('kb-gaps: discord', JSON.stringify(r));
  // a failed post must not count as sent: leave the new gaps unmarked so the next run tries again
  if (r.ok) save(open); else { const o = { ...open }; for (const g of fresh) delete o[g.key]; save(o); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main().catch(e => { console.error('kb-gaps failed:', e.message); });
