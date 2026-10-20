/* Runs the Sharp Money V2 page headless, exactly as shipped, on stored data.
   The page script is loaded into a vm context with a stub DOM and a stub fetch that serves the fixtures, so what comes out is what the page
   decides (every candidate, tier and reason) and what it renders. tests/v2_gates.test.mjs compares that against the shared module that the
   ledger script uses, and against a stored copy made from the page before the gate logic moved into sharp-money/v2/gates.js. */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

export const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures', 'sharp_v2');
export const readFix = n => JSON.parse(fs.readFileSync(path.join(FIX, n), 'utf8'));

// A deterministic wobble on the stored prices, so the stored snapshot (which has 4 plays) also exercises the other tiers and reasons.
export function mulberry(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
export function jitter(fx, seed, amt = 0.06) {
  const r = mulberry(seed), f = JSON.parse(JSON.stringify(fx));
  const nudge = p => Math.min(0.98, Math.max(0.02, p * (1 + (r() - 0.5) * 2 * amt)));
  for (const row of f.props.props.rows) for (const side of ['over', 'under']) for (const v of (row[side] && row[side].venues) || []) if (v.p != null) { v.p = +nudge(v.p).toFixed(4); v.am = v.p >= 0.5 ? Math.round(-100 * v.p / (1 - v.p)) : Math.round(100 * (1 - v.p) / v.p); }
  for (const e of Object.values(f.tape.props)) for (const b of Object.values(e.books || {})) {
    if (b.ladder) for (const rung of b.ladder) rung[1] = +nudge(rung[1]).toFixed(4);
    else if (b.over != null && r() < 0.5) { b.over = Math.round(b.over + (r() - 0.5) * 24); b.under = Math.round(b.under + (r() - 0.5) * 24); }
  }
  for (const g of f.data.games) for (const b of g.behind || []) { b.fair = +nudge(b.fair).toFixed(3); }
  for (const x of f.edge.rows) { x.fair = +nudge(x.fair).toFixed(4); if (x.second) { for (const k of ['kal', 'pm']) if (x.second[k] != null) x.second[k] = +nudge(x.second[k]).toFixed(4); } }
  return f;
}
export function loadFixtures() { return { data: readFix('data.json'), props: readFix('props.json'), tape: readFix('prop_close_tape.json'), edge: readFix('exchange_edge_live.json') }; }

const URLS = [['sharp-data/data.json', 'data'], ['sharp-data/props.json', 'props'], ['sharp-data/prop_close_tape.json', 'tape'], ['exchange_edge_live.json', 'edge'], ['sharp-data/v2_plays.json', 'plays'], ['nba-live/board.json', 'nba']];

// Projection of one candidate: everything a rule decides, none of the bulky game/row objects.
export const project = c => ({ id: c.id, kind: c.kind, sport: c.sport, start: c.start, gk: c.gk || null, m: c.m || null, side: c.side && typeof c.side === 'string' ? c.side : null, title: c.title, sub: c.sub,
  tier: c.tier, reasons: c.reasons, cautions: c.cautions, worst: c.worst, best: c.best, contradicted: c.contradicted, price: c.price, refs: c.refs });

export async function runPage({ html, fixtures, now, pages = ['plays', 'props', 'board', 'models', 'signals'], games = [] }) {
  const dir = path.dirname(html), src = fs.readFileSync(html, 'utf8');
  const els = {}, el = () => ({ innerHTML: '', textContent: '', dataset: {}, classList: { toggle() {} }, addEventListener() {}, style: {} });
  const RealDate = Date;
  class FixedDate extends RealDate { constructor(...a) { if (a.length) super(...a); else super(now * 1000); } static now() { return now * 1000; } }
  const ctx = { console, location: { hostname: 'localhost', search: '', hash: '' }, document: { getElementById: id => els[id] || (els[id] = el()), addEventListener() {}, querySelectorAll: () => [] },
    addEventListener() {}, setInterval() {}, scrollY: 0, scrollTo() {}, Date: FixedDate, Math, JSON, Promise, URL, setTimeout,
    fetch: async u => { const hit = URLS.find(([k]) => u.includes(k)); const body = hit ? fixtures[hit[1]] : null; return body ? { ok: true, json: async () => JSON.parse(JSON.stringify(body)) } : { ok: false, json: async () => null }; } };
  ctx.window = ctx; ctx.self = ctx; vm.createContext(ctx);
  for (const m of src.matchAll(/<script(?:\s+src="([^"]+)")?\s*>([\s\S]*?)<\/script>/g)) {
    if (m[1]) vm.runInContext(fs.readFileSync(path.join(dir, m[1].split('?')[0]), 'utf8'), ctx, { filename: m[1] });
    else vm.runInContext(m[2], ctx, { filename: 'index.html' });
  }
  await new Promise(r => setTimeout(r, 200));
  const all = JSON.parse(vm.runInContext('JSON.stringify(ALL.map(' + project.toString() + '))', ctx));
  const out = { all, pages: {} };
  for (const p of pages) { ctx.location.hash = '#' + p; vm.runInContext('st.sport="all";st.tier="play";st.pm="all";route()', ctx); out.pages[p] = els.scr.innerHTML; }
  for (const g of games) { ctx.location.hash = '#game/' + g; vm.runInContext('route()', ctx); out.pages['game/' + g] = els.scr.innerHTML; }
  return out;
}
