// Vault Track Record, rebuilt on Halaska UI. Same data contract (fetch data.json)
// and the SAME scoring logic as the vanilla page: agg / units pricing / EV /
// Wilson / grade rules are copied verbatim. Only rendering moved to React + kit.
import React, { useState, useEffect, useMemo, useRef, useLayoutEffect } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ThemeProvider, AccentContext, usePal, tokens, motion,
  Card, Badge, Text, Heading, Stack, Table, Button, SegmentedControl, Chip,
  DropdownMenu, Popover, Choicebox, SearchInput, Skeleton, AlertBanner, Divider, StatusBadge,
} from '../../../src/halaska-kit.jsx';
import CREST from './crest.txt';

// Live data comes from the branch a GitHub Action rewrites; local preview reads the sibling file.
const DATA_SRC = /^(localhost|127\.0\.0\.1)$/.test(location.hostname) ? 'data.json' : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/artifact-data/track-record/data.json';
const agoTxt = ts => { const s = Math.max(0, Date.now() / 1000 - ts); if (s < 90) return 'just now'; if (s < 3600) return Math.floor(s / 60) + 'm ago'; if (s < 86400) { const m = Math.floor(s / 60) % 60; return Math.floor(s / 3600) + 'h' + (m ? ' ' + m + 'm' : '') + ' ago'; } return Math.floor(s / 86400) + 'd ago'; };
function Fresh({ d }) {
  const [, tick] = useState(0);
  useEffect(() => { const t = setInterval(() => tick(x => x + 1), 30000); return () => clearInterval(t); }, []);
  const ts = d.built || Date.parse(d.generated) / 1000;
  const age = Date.now() / 1000 - ts;
  return <StatusBadge theme={THEME} status={age > 6 * 3600 ? 'offline' : age > 45 * 60 ? 'pending' : 'online'} pulse={age <= 45 * 60}><span title={'Checked ' + new Date(ts * 1000).toLocaleString()}>{'Updated ' + agoTxt(ts)}</span></StatusBadge>;
}

const THEME = 'dark';
const ACCENT = '#8fb4e0';

// ───────────────────────── logic (verbatim from the vanilla page) ─────────────────────────
const MK = { rec: 'Receptions', rec_yd: 'Rec Yds', rush_yd: 'Rush Yds', rush_att: 'Rush Att', rush_rec_yd: 'Rush+Rec Yds', pass_int: 'Pass INT', pass_td: 'Pass TD', pass_yd: 'Pass Yds', pass_cmp: 'Completions', pass_att: 'Pass Att', rush_td: 'Rush TD', pass_rush_yd: 'Pass+Rush Yds' };
const BE = 110 / 210;
let D, P = [], G = [], PA = [], PB = [];
const DEFAULTS = { bb: 'all', week: 'all', grade: 'all', side: 'all', pos: 'all', mkt: 'all', res: 'all', px: 'flat', gm: 'px', ev: 'all', books: [], grp: 'none', q: '', sort: 'week', dir: -1, page: 0, drill: null };
let st = DEFAULTS;
const loadSaved = () => { try { const s = JSON.parse(localStorage.getItem('vtr-filters') || 'null'); const o = { ...DEFAULTS, ...(s || {}), page: 0, q: '' }; if (!Array.isArray(o.books)) o.books = []; return o; } catch (e) { return { ...DEFAULTS }; } };
const save = s => { try { localStorage.setItem('vtr-filters', JSON.stringify({ bb: s.bb, week: s.week, grade: s.grade, side: s.side, pos: s.pos, mkt: s.mkt, px: s.px, gm: s.gm, ev: s.ev, books: s.books, grp: s.grp })); } catch (e) {} };

const fmtU = u => (u >= 0 ? '+' : '−') + Math.abs(u).toFixed(1) + 'u';
const fmtP = (x, d = 1) => x == null || isNaN(x) ? '—' : (x * 100).toFixed(d) + '%';
const sgn = x => x > 0 ? 'pos' : x < 0 ? 'neg' : '';
const payOf = a => a == null ? 100 / 110 : (a > 0 ? a / 100 : 100 / Math.abs(a));
const sidePx = (r, side) => st.px === 'posted' ? (r.bpx != null && side === r.side ? r.bpx : null) : st.px === 'close' ? (side === 'over' ? r.co : side === 'under' ? r.cu : null) : st.px === 'bet' ? (r._ev && side === r.side ? r._ev.price : null) : null;
const defPay = r => payOf(r.px !== undefined ? r.px : sidePx(r, r.side));
const pxLabel = () => st.px === 'posted' ? 'at the posted Best Bets price' : st.px === 'close' ? 'at closing price' : st.px === 'bet' ? 'at the +EV book\'s opening price' : 'at −110';
const decA = a => a > 0 ? 1 + a / 100 : 1 + 100 / Math.abs(a);
const _imp = a => a > 0 ? 100 / (a + 100) : -a / (-a + 100);
function mktEv(r) {
  if (!r.side) return null; const i = r.side === 'over' ? 0 : 1; let pairs = [];
  if (r.bo) { for (const b in r.bo) { if (st.books.length && !st.books.includes(b)) continue; const p = r.bo[b]; if (p && p[0] != null && p[1] != null) pairs.push([b, p[0], p[1]]); } }
  else if (!st.books.length && r.oo != null && r.ou != null) pairs = [[null, r.oo, r.ou]];
  if (!pairs.length) return null;
  const med = a => { const s = a.slice().sort((x, y) => x - y); return s[Math.floor((s.length - 1) / 2)]; };
  const mo = med(pairs.map(p => p[1])), mu = med(pairs.map(p => p[2])); const po = _imp(mo), pu = _imp(mu);
  const fair = (i ? pu : po) / (po + pu); let best = null;
  pairs.forEach(p => { const a = p[1 + i]; if (best == null || decA(a) > decA(best.price)) best = { price: a, book: p[0] }; });
  return { ev: fair * decA(best.price) - 1, price: best.price, book: best.book, n: pairs.length };
}
function evInfo(r) {
  if (r.pm == null || !r.side) return null; const i = r.side === 'over' ? 0 : 1;
  if (r.bo) { let best = null; for (const b in r.bo) { if (st.books.length && !st.books.includes(b)) continue; const a = r.bo[b][i]; if (a == null) continue; const ev = r.pm * decA(a) - 1; if (!best || ev > best.ev) best = { ev, book: b, price: a, src: r.bs || 'open' }; } return best; }
  if (st.books.length) return null;
  const a = r.side === 'over' ? r.oo : r.ou; return a == null ? null : { ev: r.pm * decA(a) - 1, book: null, price: a, src: 'headline' };
}
function wilson(w, n) { if (!n) return [0, 0]; const z = 1.96, p = w / n, d = 1 + z * z / n, c = p + z * z / (2 * n), m = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [(c - m) / d, (c + m) / d]; }
function agg(rows, payout) {
  const s = rows.filter(r => r.res === 'W' || r.res === 'L'); const W = s.filter(r => r.res === 'W').length, n = s.length;
  const units = s.reduce((a, r) => a + (r.res === 'W' ? (payout ? payout(r) : defPay(r)) : -1), 0);
  const bc = s.filter(r => r.beat != null);
  return { n, W, L: n - W, P: rows.filter(r => r.res === 'P').length, wr: n ? W / n : null, units, roi: n ? units / n : null, beat: bc.length ? bc.filter(r => r.beat === 1).length / bc.length : null };
}
const base = (r, skip) => (skip === 'week' || st.week === 'all' || r.week == st.week) && (skip === 'grade' || st.grade === 'all' || r.grade === st.grade) && (skip === 'side' || st.side === 'all' || r.side === st.side) && (skip === 'pos' || st.pos === 'all' || r.pos === st.pos) && (skip === 'mkt' || st.mkt === 'all' || r.market === st.mkt) && (skip === 'ev' || evOk(r));
const evOk = r => st.ev === 'pos' ? !!(r._ev && r._ev.ev > 0) : st.ev === 'neg' ? !!(r._ev && r._ev.ev <= 0) : (!st.books.length || !!r._ev);
const rows = skip => P.filter(r => base(r, skip));
const drillOk = r => {
  const d = st.drill; if (!d) return true; if (!(r._ev && r._ev.ev > 0 && (r.res === 'W' || r.res === 'L'))) return false;
  if (d.k === 'hl') return r._ev.src === 'headline'; if (d.k.startsWith('bk:')) return r._ev.book === d.k.slice(3);
  const [, lo, hi] = d.k.split(':'); return r._ev.ev >= +lo && r._ev.ev < +hi;
};
const uniq = a => [...new Set(a)];
const ini = s => String(s).replace(/[^A-Za-z+ ]/g, '').split(/[ +]/).filter(Boolean).map(w => w[0]).join('').slice(0, 2).toUpperCase();
const roiTxt = a => a.roi == null ? '—' : (a.roi * 100).toFixed(1) + '%';
const reduce = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion:reduce)').matches;

// ───────────────────────── small UI pieces ─────────────────────────
function useWidth() {
  const [w, setW] = useState(typeof window === 'undefined' ? 1200 : window.innerWidth);
  useEffect(() => { const f = () => setW(window.innerWidth); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f); }, []);
  return w;
}
const toneColor = (pal, t) => t === 'pos' || t === 'ok' ? pal.success : t === 'neg' || t === 'bad' ? pal.danger : t === 'warn' ? pal.warning : t === 'muted' ? pal.textTertiary : undefined;
const N = ({ t, children, size = 'sm', weight, style }) => { const pal = usePal(THEME); return <Text size={size} weight={weight} color={toneColor(pal, t)} style={{ fontVariantNumeric: 'tabular-nums', ...style }}>{children}</Text>; };
const Dim = ({ children, size = 'sm', style }) => <N t="muted" size={size} style={style}>{children}</N>;
const Ico = ({ d, size = 16, extra }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} />{extra}</svg>;
const ICONS = {
  home: 'M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z', bars: 'M4 20V10M10 20V4M16 20v-7M22 20H2', money: 'M12 3v18M17 7.5c-.6-1.5-2.4-2.5-5-2.5-3 0-5 1.5-5 3.5 0 4.5 10 2.5 10 7 0 2-2 3.5-5 3.5-2.6 0-4.4-1-5-2.5',
  table: 'M3 10h18M9 10v10M6 4h12a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z', trend: 'M3 17l6-6 4 4 8-8M15 7h6v6', ball: 'M9.5 14.5l5-5M11 11l2 2', rings: 'M9 6a6 6 0 1 0 0 12M15 6a6 6 0 1 1 0 12',
  rule: 'M4 7h10M4 12h16M4 17h7', fade: 'M4 17l6-6 4 4 6-8M4 7l6 6', list: 'M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01', rec: 'M4 7h16M4 12h16M4 17h10', pct: 'M19 5L5 19', clv: 'M12 3v18M5 10l7-7 7 7',
  bulb: 'M12 3a6 6 0 0 0-3.5 10.9V17h7v-3.1A6 6 0 0 0 12 3zM9.5 21h5', clock: 'M12 7v5l3 2', cal: 'M3 10h18M8 3v4M16 3v4', pie: 'M12 3v9h9', target: 'M3 21L21 3', swap: 'M7 4v16M7 4l-3 3M7 4l3 3M17 20V4M17 20l-3-3M17 20l3-3', user: 'M4 21a8 8 0 0 1 16 0', sliders: 'M4 7h10M4 17h6M18 7h2M14 17h6',
};

function Panel({ id, icon, title, sub, count, children, dark, right, pad = 20 }) {
  const pal = usePal(THEME);
  return (
    <section id={id} style={{ scrollMarginTop: 72 }}>
      <Card padding={0} style={dark ? { background: pal.bgSubtle } : undefined}>
        <div style={{ padding: pad }}>
          {(title) && (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
              <span style={{ width: 32, height: 32, borderRadius: tokens.radius.sm, background: pal.accentBg, color: pal.accent, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}><Ico d={ICONS[icon] || ICONS.bars} /></span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}><Text size="lg" weight="semibold">{title}</Text>{count != null && <Badge>{count}</Badge>}{right}</div>
                {sub && <div><Dim size="sm">{sub}</Dim></div>}
              </div>
            </div>
          )}
          {children}
        </div>
      </Card>
    </section>
  );
}
const Grid = ({ min = 150, children, gap = 10, style }) => <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fit,minmax(${min}px,1fr))`, gap, ...style }}>{children}</div>;
const Two = ({ children }) => { const w = useWidth(); return <div style={{ display: 'grid', gridTemplateColumns: w >= 1000 ? 'minmax(0,1fr) minmax(0,1fr)' : 'minmax(0,1fr)', gap: 12 }}>{children}</div>; };
const Mini = ({ v, tone, label }) => {
  const pal = usePal(THEME);
  return <div style={{ background: pal.bgSubtle, borderRadius: tokens.radius.sm + 2, padding: '12px 14px' }}><div><N size="xl" weight="bold" t={tone}>{v}</N></div><Dim size="sm">{label}</Dim></div>;
};
const Note = ({ children }) => <div style={{ marginTop: 12 }}><Dim size="sm" style={{ display: 'block', maxWidth: '88ch', lineHeight: 1.6 }}>{children}</Dim></div>;
const Empty = ({ children }) => <div style={{ padding: '20px 4px' }}><Dim size="base">{children}</Dim></div>;
const T = ({ cols, rows: rs }) => <div style={{ overflowX: 'auto' }}><div style={{ minWidth: 520 }}><Table theme={THEME} columns={cols} rows={rs} /></div></div>;
const Lbl = ({ children }) => <Text size="sm" weight="medium">{children}</Text>;
const LinkRow = ({ onClick, active, children }) => {
  const pal = usePal(THEME);
  return <button type="button" onClick={onClick} style={{ all: 'unset', cursor: 'pointer', ...tokens.type.sm, fontWeight: tokens.weight.medium, color: active ? pal.accent : pal.text, textDecoration: 'underline', textDecorationColor: pal.border, textUnderlineOffset: 3, display: 'inline-flex', alignItems: 'center', gap: 8 }}>{children}</button>;
};
const Av = ({ pos, children }) => {
  const pal = usePal(THEME);
  const c = pos === 'QB' ? pal.danger : pos === 'RB' ? pal.success : pos === 'WR' ? pal.accent : pos === 'TE' ? pal.warning : pal.textSecondary;
  return <span style={{ width: 24, height: 24, borderRadius: '50%', background: pal.bgMuted, color: c, ...tokens.type.xs, fontWeight: tokens.weight.bold, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>{children}</span>;
};
const GradeB = ({ g }) => <Badge variant={g === 'A' ? 'success' : g === 'B' ? 'accent' : g === 'D' ? 'warning' : g === 'F' ? 'danger' : 'default'}>{g || '·'}</Badge>;
const ResB = ({ r }) => <Badge variant={r === 'W' ? 'success' : r === 'L' ? 'danger' : 'default'}>{{ W: 'Won', L: 'Lost', P: 'Push' }[r]}</Badge>;
const WBar = ({ a }) => { const pal = usePal(THEME); return <span style={{ display: 'inline-block', width: 56, height: 4, borderRadius: 2, background: pal.bgMuted, verticalAlign: 'middle', marginLeft: 8, overflow: 'hidden' }}><i style={{ display: 'block', height: '100%', width: ((a.wr || 0) * 100) + '%', background: a.wr > BE ? pal.success : pal.textTertiary }} /></span>; };

// agg → table cells (Picks, W–L, Win %, Units, ROI, [Beat close])
const cellsOf = (a, { beat = true, bar = false } = {}) => [
  <N>{a.n}</N>, <N>{a.W}–{a.L}</N>, <span><N>{fmtP(a.wr)}</N>{bar && <WBar a={a} />}</span>,
  <N t={sgn(a.units)}>{fmtU(a.units)}</N>, <N t={sgn(a.roi)}>{roiTxt(a)}</N>, ...(beat ? [<N>{fmtP(a.beat, 0)}</N>] : []),
];
const HEAD = ['Picks', 'W–L', 'Win %', 'Units', 'ROI', 'Beat close'];
const HEAD5 = ['Picks', 'W–L', 'Win %', 'Units', 'ROI'];

// ───────────────────────── charts ─────────────────────────
function BarChart({ items, aria }) {
  const pal = usePal(THEME);
  const W = 520, H = 210, L = 34, Rr = 8, T = 18, B = 38, lo = .3, hi = .8;
  const y = v => T + (1 - (Math.min(Math.max(v, lo), hi) - lo) / (hi - lo)) * (H - T - B);
  const bw = (W - L - Rr) / items.length;
  const grid = []; for (let v = lo; v <= hi + 1e-9; v += .1) grid.push(v);
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={aria} style={{ display: 'block', fontFamily: tokens.font.sans, fontSize: 11 }}>
        {grid.map(v => <g key={v}><line x1={L} x2={W - Rr} y1={y(v)} y2={y(v)} stroke={pal.borderSubtle} /><text x={L - 8} y={y(v) + 4} textAnchor="end" fill={pal.textTertiary}>{Math.round(v * 100)}</text></g>)}
        {items.map((it, i) => {
          const a = it.a, w = Math.min(40, bw * .55), x = L + i * bw + (bw - w) / 2, cx = x + w / 2;
          const good = a.n >= 25 && a.wr > BE;
          const top = a.n ? y(a.wr) : 0, [c0, c1] = a.n ? wilson(a.W, a.n) : [0, 0];
          return (
            <g key={i}>
              {a.n ? <>
                <rect x={x} y={top} width={w} height={Math.max(4, y(lo) - top)} rx="10" fill={good ? pal.success : pal.bgMuted}><title>{it.label}: {a.W}–{a.L} · {fmtP(a.wr)} · {fmtU(a.units)}</title></rect>
                <line x1={cx} x2={cx} y1={y(c1)} y2={y(c0)} stroke={pal.textSecondary} strokeWidth="1" opacity=".4" />
                <text x={cx} y={Math.min(y(c1), top) - 6} textAnchor="middle" fill={pal.text} fontWeight="600">{Math.round(a.wr * 100)}</text>
              </> : null}
              <text x={cx} y={H - B + 16} textAnchor="middle" fill={pal.textSecondary}>{it.label}</text>
              <text x={cx} y={H - B + 30} textAnchor="middle" fill={pal.textTertiary}>{a.n}</text>
            </g>
          );
        })}
        <line x1={L} x2={W - Rr} y1={y(BE)} y2={y(BE)} stroke={pal.textTertiary} strokeDasharray="4 4" />
      </svg>
      <Legend items={[[pal.success, 'Clears break-even'], [pal.textTertiary, 'Dashed = 52.4% break-even'], [null, 'Bar label = win %, below = picks']]} />
    </>
  );
}
const Legend = ({ items }) => <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 16px', marginTop: 10 }}>{items.map(([c, t], i) => <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>{c && <i style={{ width: 8, height: 8, borderRadius: '50%', background: c, display: 'inline-block' }} />}<Dim size="sm">{t}</Dim></span>)}</div>;

function CalibChart({ R }) {
  const pal = usePal(THEME);
  const W = 520, H = 230, L = 34, Rr = 10, T = 10, B = 32, lo = .3, hi = .9;
  const sx = v => L + (v - lo) / (hi - lo) * (W - L - Rr), sy = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const cuts = [.3, .45, .5, .55, .6, .65, .7, .75, .8, 1.01]; const pts = [];
  for (let i = 0; i < cuts.length - 1; i++) { const s = R.filter(r => r.pm != null && r.pm >= cuts[i] && r.pm < cuts[i + 1] && (r.res === 'W' || r.res === 'L')); if (s.length < 8) continue; pts.push({ p: s.reduce((a, r) => a + r.pm, 0) / s.length, w: s.filter(r => r.res === 'W').length / s.length, n: s.length }); }
  const grid = []; for (let v = lo; v <= hi + 1e-9; v += .1) grid.push(v);
  const mx = Math.max(1, ...pts.map(p => p.n));
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Promised versus actual win rate" style={{ display: 'block', fontFamily: tokens.font.sans, fontSize: 11 }}>
        {grid.map(v => <g key={v}><line x1={L} x2={W - Rr} y1={sy(v)} y2={sy(v)} stroke={pal.borderSubtle} /><text x={L - 8} y={sy(v) + 4} textAnchor="end" fill={pal.textTertiary}>{Math.round(v * 100)}</text><text x={sx(v)} y={H - B + 16} textAnchor="middle" fill={pal.textTertiary}>{Math.round(v * 100)}</text></g>)}
        <line x1={sx(lo)} y1={sy(lo)} x2={sx(hi)} y2={sy(hi)} stroke={pal.textTertiary} strokeDasharray="4 4" />
        <text x={W - Rr} y={H - 2} textAnchor="end" fill={pal.textTertiary}>promised win chance →</text>
        {pts.length > 1 && <polyline fill="none" stroke={pal.accent} strokeWidth="2" strokeLinejoin="round" points={pts.map(p => sx(p.p) + ',' + sy(Math.max(lo, p.w))).join(' ')} />}
        {pts.map((p, i) => <circle key={i} cx={sx(p.p)} cy={sy(Math.max(lo, p.w))} r={3 + 6 * Math.sqrt(p.n / mx)} fill={pal.accent} stroke={pal.bgElevated} strokeWidth="2"><title>Promised {fmtP(p.p)} · hit {fmtP(p.w)} · {p.n} picks</title></circle>)}
        {!pts.length && <text x={W / 2} y={H / 2} textAnchor="middle" fill={pal.textTertiary}>Not enough picks</text>}
      </svg>
      <Legend items={[[pal.accent, 'Actual hit rate (size = picks)'], [pal.textTertiary, 'Dashed = perfectly honest']]} />
    </>
  );
}

function WeekChart({ R }) {
  const pal = usePal(THEME);
  const wk = uniq(R.map(r => r.week)).sort((a, b) => a - b); const a = wk.map(w => ({ w, u: agg(R.filter(r => r.week === w)).units }));
  const tot = a.reduce((x, y) => x + y.u, 0), best = a.reduce((m, x) => !m || x.u > m.u ? x : m, null), all = agg(R);
  const W = 520, H = 190, L = 34, Rr = 8, T = 14, B = 26; const ext = Math.max(5, ...a.map(x => Math.abs(x.u))) * 1.15;
  const y = v => T + (1 - (v + ext) / (2 * ext)) * (H - T - B); const bw = (W - L - Rr) / Math.max(a.length, 1);
  const step = ext > 40 ? 20 : ext > 16 ? 10 : 5; const ticks = []; for (let v = -Math.floor(ext / step) * step; v <= ext; v += step) ticks.push(v);
  return (
    <>
      <Grid min={120} style={{ marginBottom: 14 }}>
        <Mini v={fmtU(tot)} tone={tot < 0 ? 'neg' : undefined} label="Season units" />
        <Mini v={best ? 'Wk ' + best.w : '—'} tone={best && best.u < 0 ? 'neg' : undefined} label={'Best week' + (best ? ' · ' + fmtU(best.u) : '')} />
        <Mini v={fmtP(all.wr)} tone={all.wr != null && all.wr < BE ? 'neg' : undefined} label="Win rate" />
      </Grid>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Units by week" style={{ display: 'block', fontFamily: tokens.font.sans, fontSize: 11 }}>
        {ticks.map(v => <g key={v}><line x1={L} x2={W - Rr} y1={y(v)} y2={y(v)} stroke={pal.borderSubtle} /><text x={L - 8} y={y(v) + 4} textAnchor="end" fill={pal.textTertiary}>{(v > 0 ? '+' : '') + v}</text></g>)}
        <line x1={L} x2={W - Rr} y1={y(0)} y2={y(0)} stroke={pal.border} />
        {a.map((x, i) => {
          const w = Math.min(40, bw * .5), bx = L + i * bw + (bw - w) / 2, isBest = best && x === best && x.u > 0;
          return <g key={i}><rect x={bx} y={Math.min(y(0), y(x.u))} width={w} height={Math.max(4, Math.abs(y(x.u) - y(0)))} rx="10" fill={isBest ? pal.success : x.u < 0 ? pal.danger : pal.bgMuted} opacity={x.u < 0 ? .55 : 1}><title>Week {x.w}: {fmtU(x.u)}</title></rect><text x={bx + w / 2} y={H - B + 16} textAnchor="middle" fill={pal.textSecondary}>Wk {x.w}</text></g>;
        })}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}><Dim size="xs">Losing</Dim><Dim size="xs">Winning</Dim></div>
    </>
  );
}

function Ladder({ R }) {
  const pal = usePal(THEME);
  const gs = ['A', 'B', 'C', 'D', 'F', null];
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,minmax(0,1fr))', gap: '8px 6px', textAlign: 'center' }}>
        {gs.map(g => <Dim key={'h' + g} size="sm">{g || 'None'}</Dim>)}
        {gs.map(g => {
          const a = agg(R.filter(r => (r.grade || null) === g));
          const cls = !a.n ? 'none' : a.n < 25 ? 'thin' : a.wr > BE ? 'up' : 'dn';
          const bg = cls === 'up' ? pal.success : pal.bgMuted, fg = cls === 'up' ? pal.bg : cls === 'dn' ? pal.textSecondary : pal.textTertiary;
          return (
            <div key={'c' + g}>
              <div title={`${g || 'Ungraded'}: ${a.W}–${a.L} · ${fmtU(a.units)}`} style={{ width: 44, height: 44, borderRadius: '50%', margin: '0 auto 6px', background: bg, color: fg, opacity: cls === 'thin' ? .6 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center', ...tokens.type.md, fontWeight: tokens.weight.bold, border: cls === 'up' ? 'none' : `1px solid ${pal.border}` }}>{a.n ? Math.round(a.wr * 100) : '·'}</div>
              <div><Dim size="xs">{a.n ? fmtU(a.units) : ''}</Dim></div><div><Dim size="xs">{a.n} picks</Dim></div>
            </div>
          );
        })}
      </div>
      <Legend items={[[pal.success, 'Clears break-even'], [pal.bgMuted, 'Below it'], [pal.textMuted, 'Under 25 picks']]} />
    </>
  );
}

function Bubbles({ R }) {
  const pal = usePal(THEME);
  const ref = useRef(null); const [Wd, setWd] = useState(380); const Hd = 210;
  useLayoutEffect(() => { const f = () => ref.current && setWd(ref.current.clientWidth || 380); f(); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f); }, []);
  const s = R.filter(r => r.res === 'W' || r.res === 'L'); const tot = s.length || 1;
  const by = uniq(s.map(r => r.market)).map(m => ({ m, a: agg(s.filter(r => r.market === m)) })).sort((x, y) => y.a.n - x.a.n);
  const top = by.slice(0, 4), rest = by.slice(4);
  if (rest.length) { const rr = s.filter(r => rest.some(x => x.m === r.market)); top.push({ m: 'other', a: agg(rr), label: 'Other' }); }
  const tones = [pal.accent, pal.success, pal.danger, pal.warning, pal.textSecondary];
  const gap = 6, mx = Math.max(...top.map(x => x.a.n), 1), maxR = Math.min(78, Hd / 2 - 4, Wd * .22);
  const cs = top.map(b => ({ b, r: Math.max(17, maxR * Math.sqrt(b.a.n / mx)) }));
  const placed = [], cx0 = Wd * .46, cy0 = Hd / 2;
  cs.slice().sort((p, q) => q.r - p.r).forEach((c, i) => {
    if (!i) { c.x = Math.max(c.r, cx0 - c.r * .35); c.y = cy0; placed.push(c); return; }
    for (let tries = 0; tries < 6; tries++) {
      let best = null;
      placed.forEach(p => { for (let a = 0; a < 360; a += 10) { const t = a * Math.PI / 180, x = p.x + (p.r + c.r + gap) * Math.cos(t), y = p.y + (p.r + c.r + gap) * Math.sin(t);
        if (x - c.r < 0 || x + c.r > Wd || y - c.r < 0 || y + c.r > Hd) continue;
        if (placed.some(q => Math.hypot(q.x - x, q.y - y) < q.r + c.r + gap - .5)) continue;
        const dd = Math.hypot(x - cx0, y - cy0); if (!best || dd < best.d) best = { x, y, d: dd }; } });
      if (best) { c.x = best.x; c.y = best.y; placed.push(c); break; }
      c.r = Math.max(14, c.r * .8);
    }
  });
  const name = b => b.label || MK[b.m] || b.m;
  return (
    <>
      <div ref={ref} style={{ position: 'relative', height: Hd }}>
        {placed.map(c => { const i = cs.indexOf(c), b = c.b, sh = b.a.n / tot, d = c.r * 2;
          return <span key={i} title={`${name(b)}: ${b.a.W}–${b.a.L} · ${fmtP(b.a.wr)}`} style={{ position: 'absolute', left: c.x - c.r, top: c.y - c.r, width: d, height: d, borderRadius: '50%', background: tones[i] + '33', color: tones[i], display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', ...tokens.type.sm, fontWeight: tokens.weight.bold }}>{Math.round(sh * 100)}%{d > 64 && <small style={{ ...tokens.type.xxs, fontWeight: tokens.weight.medium }}>{fmtP(b.a.wr, 0)} hit</small>}</span>; })}
      </div>
      <Legend items={top.map((b, i) => [tones[i], name(b)])} />
    </>
  );
}

// ───────────────────────── sections ─────────────────────────
function Kpis({ a, props, R, pricedTxt }) {
  const pal = usePal(THEME);
  const chip = (ok, t) => <Badge variant={ok == null ? 'warning' : ok ? 'success' : 'danger'}>{t}</Badge>;
  const tiles = [
    ['rec', 'Record', a.W + '–' + a.L, <Dim size="xs">{a.n.toLocaleString()} settled{a.P ? ' · ' + a.P + ' push' : ''}</Dim>],
    ['pct', 'Win rate', fmtP(a.wr), a.wr == null ? null : chip(a.wr > BE, (a.wr > BE ? '+' : '−') + Math.abs((a.wr - BE) * 100).toFixed(1) + ' vs BE')],
    ['money', 'Units', fmtU(a.units), <Dim size="xs">{props ? pxLabel() : 'at price'}</Dim>],
    ['trend', 'ROI', a.roi == null ? '—' : (a.roi >= 0 ? '+' : '−') + Math.abs(a.roi * 100).toFixed(1) + '%', a.roi == null ? null : chip(a.roi > 0, a.roi > 0 ? 'profit' : 'loss')],
    ['clv', 'Beat the close', fmtP(a.beat, 0), <Dim size="xs">{props && st.px === 'close' ? pricedTxt : 'line moved Vault\'s way'}</Dim>],
  ];
  return (
    <Grid min={190} gap={12}>
      {tiles.map(([ic, l, v, x]) => (
        <Card key={l} padding={16}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ width: 36, height: 36, borderRadius: tokens.radius.sm, background: pal.accentBg, color: pal.accent, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}><Ico d={ICONS[ic]} /></span>
            <div style={{ minWidth: 0 }}>
              <Dim size="sm">{l}</Dim>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}><N size="xl" weight="bold">{v}</N>{x}</div>
            </div>
          </div>
        </Card>
      ))}
    </Grid>
  );
}

function Verdict({ R }) {
  const pal = usePal(THEME);
  const out = []; const a = agg(R);
  if (a.n < 30) out.push(['meh', 'Only ' + a.n + ' settled picks match these filters. Treat every number here as noise until the sample grows.']);
  else {
    const ci = wilson(a.W, a.n);
    out.push(ci[0] > BE ? ['good', 'Win rate is clear of break-even even at the low end of its range (' + fmtP(ci[0]) + '). That is a real edge on this slice.']
      : ci[1] < BE ? ['bad', 'Win rate is below break-even even at the top of its range (' + fmtP(ci[1]) + '). This slice loses money.']
      : ['meh', 'Win rate could still be anywhere from ' + fmtP(ci[0]) + ' to ' + fmtP(ci[1]) + '. Not enough games yet to call this slice a winner or a loser.']);
    if (st.grade === 'all') {
      const g = k => agg(R.filter(r => r.grade === k)); const A = g('A'), F = g('F');
      if (A.n >= 20 && F.n >= 20) out.push(A.wr > F.wr + .03 ? ['good', 'A grades are hitting ' + fmtP(A.wr) + ' vs ' + fmtP(F.wr) + ' for F. The grade is ranking picks the right way so far.'] : A.wr < F.wr ? ['bad', 'A grades (' + fmtP(A.wr) + ') are hitting below F grades (' + fmtP(F.wr) + '). The grade is not sorting picks yet.'] : ['meh', 'A grades (' + fmtP(A.wr) + ') barely separate from F grades (' + fmtP(F.wr) + ').']);
      const mids = ['B', 'C', 'D'].map(k => [k, g(k)]).filter(x => x[1].n >= 40).sort((x, y) => y[1].wr - x[1].wr);
      if (mids.length && mids[0][1].wr > A.wr) out.push(['meh', 'Grade ' + mids[0][0] + ' is outhitting A (' + fmtP(mids[0][1].wr) + ' on ' + mids[0][1].n + ' picks). The ladder is not in order yet.']);
    }
    if (st.side === 'all') {
      const o = agg(R.filter(r => r.side === 'over')), u = agg(R.filter(r => r.side === 'under'));
      if (o.n >= 30 && u.n >= 30 && Math.abs(o.wr - u.wr) > .04) out.push(['meh', (o.wr > u.wr ? 'Overs' : 'Unders') + ' are carrying the record (' + fmtP(Math.max(o.wr, u.wr)) + ' vs ' + fmtP(Math.min(o.wr, u.wr)) + '). ' + (o.n > u.n * 1.5 ? 'Vault leans Over on ' + Math.round(o.n / (o.n + u.n) * 100) + '% of picks, so that tilt is costing it.' : '')]);
    }
    const bc = R.filter(r => r.beat != null); if (bc.length >= 50) { const b = bc.filter(r => r.beat === 1).length / bc.length; out.push([b > .55 ? 'good' : b < .48 ? 'bad' : 'meh', 'The line moved toward Vault\'s side before kickoff on ' + fmtP(b, 0) + ' of picks.' + (b > .55 ? ' See Closing line value for whether that is turning into wins.' : '')]); }
  }
  const col = { good: pal.success, bad: pal.danger, meh: pal.warning };
  return <div style={{ display: 'grid', gap: 10 }}>{out.map(([c, t], i) => <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}><i style={{ width: 8, height: 8, borderRadius: '50%', background: col[c], marginTop: 7, flex: 'none' }} /><Text size="base">{t}</Text></div>)}</div>;
}

function EvCard({ R, upd }) {
  const S = R.filter(r => r._ev && r._ev.ev > 0 && (r.res === 'W' || r.res === 'L'));
  const betPay = r => payOf(r._ev.price);
  const closePay = r => { const b = r._ev.book, i = r.side === 'over' ? 0 : 1; const a = b && r.bc && r.bc[b] ? r.bc[b][i] : (r.side === 'over' ? r.co : r.cu); return payOf(a); };
  const A = agg(S, betPay), C = agg(S, closePay);
  const hl = S.filter(r => r._ev.src === 'headline').length;
  const sub = (st.books.length ? st.books.join(', ') + ' only. ' : '') + 'Picks where Vault\'s win chance beat the opening price. Units at that price.';
  const go = d => {
    if (st.drill && st.drill.k === d) { upd({ drill: null }); return; }
    const lab = d === 'hl' ? 'no book on record (Wk 1–3)' : d.startsWith('bk:') ? 'best +EV book ' + d.slice(3) : d.split(':')[3] + ' Vault EV at open';
    upd({ drill: { k: d, label: lab }, sort: 'evp', dir: -1, page: 0 });
    setTimeout(() => { const el = document.getElementById('s-picks'); el && el.scrollIntoView({ behavior: reduce() ? 'auto' : 'smooth', block: 'start' }); }, 30);
  };
  const on = d => st.drill && st.drill.k === d;
  const rw = (l, a, d) => [d ? <LinkRow active={on(d)} onClick={() => go(d)}>{l}{on(d) && <Badge variant="accent">showing</Badge>}</LinkRow> : <Lbl>{l}</Lbl>, ...cellsOf(a, { beat: false, bar: true })];
  const bk = [[0, .05, '0–5%'], [.05, .1, '5–10%'], [.1, .2, '10–20%'], [.2, 99, '20%+']];
  const byBook = uniq(S.map(r => r._ev.book).filter(Boolean)).map(b => ({ b, a: agg(S.filter(r => r._ev.book === b), betPay) })).sort((x, y) => y.a.n - x.a.n);
  return (
    <Panel id="s-ev" icon="money" title="+EV bets" count={S.length} sub={sub}>
      {!S.length ? <Empty>{st.books.length ? 'No settled +EV picks at those books yet. Per-book prices start with Week 4 results.' : 'No settled +EV picks match these filters.'}</Empty> : (
        <>
          <Grid min={130} style={{ marginBottom: 14 }}>
            <Mini v={A.W + '–' + A.L} label={'Record · ' + fmtP(A.wr)} />
            <Mini v={fmtU(A.units)} tone={A.units < 0 ? 'neg' : undefined} label="Units at the +EV price" />
            <Mini v={(A.roi >= 0 ? '+' : '−') + Math.abs(A.roi * 100).toFixed(1) + '%'} tone={A.roi < 0 ? 'neg' : undefined} label="ROI" />
            <Mini v={fmtU(C.units)} tone={C.units < 0 ? 'neg' : undefined} label="Same picks at close" />
          </Grid>
          <Two>
            <T cols={['EV at open', ...HEAD5]} rows={bk.map(([lo, hi, l]) => rw(l, agg(S.filter(r => r._ev.ev >= lo && r._ev.ev < hi), betPay), 'ev:' + lo + ':' + hi + ':' + l))} />
            <T cols={['Best +EV book', ...HEAD5]} rows={[...(byBook.length ? byBook.map(x => rw(x.b, x.a, 'bk:' + x.b)) : [[<Dim>Book names start with Week 4 results</Dim>, '', '', '', '', '']]), ...(hl ? [rw('No book on record (Wk 1–3)', agg(S.filter(r => r._ev.src === 'headline'), betPay), 'hl')] : [])]} />
          </Two>
          <Note>Click any label to list those picks below. Vault EV = Vault's win chance × the opening payout − 1, at the best of the selected books. Weeks 1–3 have no per-book record, so they use the single headline opening price and only count when no book is selected. Props that opened before per-book capture use the first book prices on record. Units assume 1u at that price.</Note>
        </>
      )}
    </Panel>
  );
}

function MarketTable({ R, upd }) {
  const m = uniq(R.map(r => r.market)).map(k => ({ k, a: agg(R.filter(r => r.market === k)) })).sort((x, y) => y.a.n - x.a.n);
  return (
    <Panel id="s-markets" icon="table" title="By market" count={m.length} sub="Click a market to filter everything to it. Proj bias = actual minus projection.">
      <T cols={['Market', ...HEAD, 'Proj bias', 'Proj miss']} rows={m.map(({ k, a }) => { const q = D.mk[k] || {};
        return [<LinkRow active={st.mkt === k} onClick={() => upd({ mkt: st.mkt === k ? 'all' : k, page: 0 })}><Av>{ini(MK[k] || k)}</Av>{MK[k] || k}{st.mkt === k && <Badge variant="accent">filtered</Badge>}</LinkRow>, ...cellsOf(a, { bar: true }), <N t={sgn(q.bias)}>{q.bias == null ? '—' : (q.bias > 0 ? '+' : '') + q.bias.toFixed(1)}</N>, <N>{q.mae == null ? '—' : q.mae.toFixed(1)}</N>]; })} />
    </Panel>
  );
}

function Clv({ R }) {
  const b = agg(R.filter(r => r.beat === 1)), n = agg(R.filter(r => r.beat === 0)); const A = agg(R);
  const moved = R.filter(r => r.clv && r.clv !== 0).length;
  const lift = b.wr != null && n.wr != null ? ((b.wr - n.wr) * 100 >= 0 ? '+' : '−') + Math.abs((b.wr - n.wr) * 100).toFixed(1) + ' pts' : '—';
  return (
    <Panel id="s-clv" icon="trend" title="Closing line value" sub="Beating the close is the early, low-noise sign of a sharp model">
      <Grid min={150} style={{ marginBottom: 14 }}>
        <Mini v={fmtP(A.beat, 0)} label="Beat-close rate" /><Mini v={fmtP(R.length ? moved / R.length : null, 0)} label="Lines that moved" />
        <Mini v={lift} tone={b.wr != null && n.wr != null && b.wr <= n.wr ? 'neg' : undefined} label="Win rate lift when beating it" />
      </Grid>
      <T cols={['Line moved', ...HEAD]} rows={[[<Lbl>Toward Vault</Lbl>, ...cellsOf(b)], [<Lbl>Away or flat</Lbl>, ...cellsOf(n)]]} />
      <Note>{b.n >= 40 && n.n >= 40 ? (b.wr > n.wr + .02 ? 'Picks where the market moved toward Vault are winning more often, which is what real CLV should look like.' : 'Beating the close is not yet turning into a higher win rate (' + fmtP(b.wr) + ' vs ' + fmtP(n.wr) + '). Props that "beat the close" by a half point on a stale open line are common, so this signal is weaker than it looks.') : 'Not enough picks on each side to compare.'}</Note>
    </Panel>
  );
}

const rw5 = (l, a) => [<Lbl>{l}</Lbl>, ...cellsOf(a, { beat: false })];
const wkRow = (w, vals, ex) => [<Lbl>Wk {w}</Lbl>, ...vals.map(x => <N t={sgn(x)}>{fmtU(x)}</N>), ...(ex || [])];

function Shadow({ R }) {
  const S = R.filter(r => r.wh != null && (r.res === 'W' || r.res === 'L'));
  const body = !S.length ? <Empty>{P.some(r => r.wh != null) ? 'No shadow picks match these filters.' : 'Shadow results start with the next nightly settlement run.'}</Empty> : (() => {
    const live = S.map(r => ({ res: r.res, week: r.week, beat: null, px: sidePx(r, r.side) })), adj = S.map(r => ({ res: r.wh === 1 ? 'W' : 'L', week: r.week, beat: null, px: sidePx(r, r.sh) }));
    const flip = S.filter(r => r.sh !== r.side), fl = agg(flip.map(r => ({ res: r.res, px: sidePx(r, r.side) }))), fa = agg(flip.map(r => ({ res: r.wh === 1 ? 'W' : 'L', px: sidePx(r, r.sh) })));
    const th = S.filter(r => r.pm != null && r.pm >= .6), ta = S.filter(r => r.ph != null && r.ph >= .6);
    const wk = uniq(S.map(r => r.week)).sort((a, b) => a - b); const L = agg(live), A = agg(adj), d = A.units - L.units;
    return (
      <>
        <Grid min={130} style={{ marginBottom: 14 }}>
          <Mini v={fmtU(L.units)} tone={L.units < 0 ? 'neg' : undefined} label={'Live model · ' + L.W + '–' + L.L} />
          <Mini v={fmtU(A.units)} tone={A.units < 0 ? 'neg' : undefined} label={'History-adjusted · ' + A.W + '–' + A.L} />
          <Mini v={fmtU(d)} tone={d < 0 ? 'neg' : undefined} label="Adjusted minus live" />
          <Mini v={flip.length} label={'Sides flipped · ' + flip.filter(r => r.side === 'over').length + ' to under'} />
        </Grid>
        <Two>
          <T cols={['Same props', ...HEAD5]} rows={[rw5('Live model', L), rw5('History-adjusted', A), rw5('Flipped · live side', fl), rw5('Flipped · adjusted side', fa), rw5('Live, win chance 60%+', agg(th.map(r => ({ res: r.res, px: sidePx(r, r.side) })))), rw5('Adjusted, win chance 60%+', agg(ta.map(r => ({ res: r.wh === 1 ? 'W' : 'L', px: sidePx(r, r.sh) }))))]} />
          <T cols={['Week', 'Live', 'Adjusted', 'Diff']} rows={wk.map(w => { const a = agg(live.filter(x => x.week === w)), b = agg(adj.filter(x => x.week === w)); return wkRow(w, [a.units, b.units, b.units - a.units]); })} />
        </Two>
        <Note>Covers receptions, rush yards, rush attempts, pass yards, pass attempts and completions. Each side is judged on its own pick {pxLabel()}. Flipped picks are where the two models disagree, so those rows are the real test.</Note>
      </>
    );
  })();
  return <Panel id="s-shadow" icon="rings" title="Shadow test" right={<Badge>background only</Badge>} sub="History-adjusted model vs the live one, same props, same closing lines">{body}</Panel>;
}

function GradeRule({ R }) {
  const S = R.filter(r => r.res === 'W' || r.res === 'L');
  let body;
  if (!S.some(r => r.gmk !== undefined && r.gmk !== null || r.ga)) body = <Empty>Grade rule results start with the next nightly settlement run.</Empty>;
  else {
    const oth = r => r.side === 'over' ? 'under' : 'over'; const AB = g => g === 'A' || g === 'B';
    const lean = k => S.filter(r => AB(r[k])).map(r => ({ res: r.res, week: r.week, px: sidePx(r, r.side) }));
    const alt = k => S.filter(r => AB(r[k]) && r.wa != null).map(r => ({ res: r.wa === 1 ? 'W' : 'L', week: r.week, px: sidePx(r, oth(r)) }));
    const liveL = lean('gpx'), oldL = lean('gb'), mktL = lean('gmk'), liveA = alt('ga'), mktA = alt('gma'); const both = (a, b) => a.concat(b);
    const LV = agg(both(liveL, liveA)), OL = agg(oldL), MKA = agg(both(mktL, mktA));
    const chg = S.filter(r => r.gb != null && r.gpx != null && r.gb !== r.gpx);
    const wk = uniq(S.map(r => r.week)).sort((a, b) => a - b); const lvAll = both(liveL, liveA), mkAll = both(mktL, mktA);
    body = (
      <>
        <Grid min={130} style={{ marginBottom: 14 }}>
          <Mini v={fmtU(LV.units)} tone={LV.units < 0 ? 'neg' : undefined} label={'Live rule A+B · ' + LV.W + '–' + LV.L} />
          <Mini v={fmtU(MKA.units)} tone={MKA.units < 0 ? 'neg' : undefined} label={'Market shadow A+B · ' + MKA.W + '–' + MKA.L} />
          <Mini v={fmtU(MKA.units - LV.units)} tone={MKA.units - LV.units < 0 ? 'neg' : undefined} label="Shadow minus live" />
          <Mini v={chg.length} label="Past grades changed Sep 26" />
        </Grid>
        <Two>
          <T cols={['A and B grades', ...HEAD5]} rows={[rw5('Vault\'s side · live', agg(liveL)), rw5('Vault\'s side · old 50% pull', agg(oldL)), rw5('Vault\'s side · market shadow', agg(mktL)), rw5('Other side · live', agg(liveA)), rw5('Other side · market shadow', agg(mktA)), rw5('Grades changed Sep 26', agg(chg.map(r => ({ res: r.res, px: sidePx(r, r.side) }))))]} />
          <T cols={['Week', 'Live', 'Market', 'Diff']} rows={wk.map(w => { const a = agg(lvAll.filter(x => x.week === w)), b = agg(mkAll.filter(x => x.week === w)); return wkRow(w, [a.units, b.units, b.units - a.units]); })} />
        </Two>
        <Note>Every grade is scored against the price of the side it grades, {pxLabel()}. "Other side" is the card Vault does not lean toward, where a plus-money price can earn a grade on its own. The live rule stopped the 50% pull from lifting a side Vault gives under 50%; the old rule is kept so past weeks can be compared. The market shadow is not shown on the board. It goes live only if it beats the live rule over more weeks, mostly on the other side.</Note>
      </>
    );
  }
  return <Panel id="s-rule" icon="rule" title="Grade rule test" right={<Badge>since Sep 26</Badge>} sub="A and B grades under the live rule, the old one, and a stricter market-anchored shadow">{body}</Panel>;
}

function Fade({ R }) {
  const S = R.filter(r => (r.res === 'W' || r.res === 'L') && (r.vtl === 'over' || r.vtl === 'under') && r.market !== 'pass_int');
  let body;
  if (!S.length) body = <Empty>{P.some(r => r.vtl) ? 'No props match these filters.' : 'Fade results start with the next nightly settlement run.'}</Empty>;
  else {
    const oth = r => r.side === 'over' ? 'under' : 'over'; const AB = g => g === 'A' || g === 'B';
    const pick = (r, own) => own ? { res: r.res, week: r.week, px: sidePx(r, r.side) } : { res: r.wa === 1 ? 'W' : 'L', week: r.week, px: sidePx(r, oth(r)) };
    const against = [], withL = [];
    S.forEach(r => { if (AB(r.gpx)) (r.side !== r.vtl ? against : withL).push(pick(r, true)); if (AB(r.ga) && r.wa != null) (oth(r) !== r.vtl ? against : withL).push(pick(r, false)); });
    const A = agg(against), W = agg(withL); const wk = uniq(S.map(r => r.week)).sort((a, b) => a - b);
    body = (
      <>
        <Grid min={130} style={{ marginBottom: 14 }}>
          <Mini v={fmtU(A.units)} tone={A.units < 0 ? 'neg' : undefined} label={'Against the lean · ' + A.W + '–' + A.L} />
          <Mini v={fmtU(W.units)} tone={W.units < 0 ? 'neg' : undefined} label={'With the lean · ' + W.W + '–' + W.L} />
          <Mini v={fmtU(A.units - W.units)} tone={A.units - W.units < 0 ? 'neg' : undefined} label="Against minus with" />
        </Grid>
        <Two>
          <T cols={['A and B props', ...HEAD5]} rows={[rw5('Against Vault\'s team lean', A), rw5('With Vault\'s team lean', W)]} />
          <T cols={['Week', 'Against', 'With', 'Diff']} rows={wk.map(w => { const a = agg(against.filter(x => x.week === w)), b = agg(withL.filter(x => x.week === w)); return [<Lbl>Wk {w}</Lbl>, <N t={sgn(a.units)}>{fmtU(a.units)} <Dim size="xs">{a.W}–{a.L}</Dim></N>, <N t={sgn(b.units)}>{fmtU(b.units)} <Dim size="xs">{b.W}–{b.L}</Dim></N>, <N t={sgn(a.units - b.units)}>{fmtU(a.units - b.units)}</N>]; })} />
        </Two>
        <Note>Vault's team lean compares the team points its game model expects with the market's implied team total (game total ÷ 2 minus the team's spread ÷ 2), as of kickoff, with a 1-point bar. Against the lean means an under when Vault expects the team to beat its total, or an over when it expects a miss. Scored {pxLabel()}. This is the same filter as "Fade Vault's team lean" on the props board.</Note>
      </>
    );
  }
  return <Panel id="s-fade" icon="fade" title="Fade Vault's team lean" right={<Badge>test</Badge>} sub="A and B props against Vault's team scoring lean vs with it">{body}</Panel>;
}

function Games({ week }) {
  const Gw = G.filter(g => week === 'all' || g.week == week);
  const pay = g => { if (g.market !== 'ml') return 100 / 110; const px = g.price_close ?? g.price_open; if (px != null) return px > 0 ? px / 100 : 100 / Math.abs(px); const p = g.p_market; return p && p > 0 && p < 1 ? (1 - p) / p : 100 / 110; };
  const L = { spread: 'Spread', total: 'Total', ml: 'Moneyline' };
  const err = (m, f) => { const s = Gw.filter(g => g.market === m && g.vault_line != null && g.line_close != null); if (!s.length) return null; return s.reduce((a, g) => a + Math.abs(f(g)), 0) / s.length; };
  const sp = [err('spread', g => g.vault_line + g.actual), err('spread', g => g.line_close + g.actual)], to = [err('total', g => g.vault_line - g.actual), err('total', g => g.line_close - g.actual)];
  const r2 = (l, [v, m]) => [<Lbl>{l}</Lbl>, <N>{v == null ? '—' : v.toFixed(2)}</N>, <N>{m == null ? '—' : m.toFixed(2)}</N>, v != null && m != null ? <Badge variant={v < m ? 'success' : 'danger'} style={{ textTransform: 'none', letterSpacing: 0 }}>{v < m ? 'Vault closer' : 'Market closer'} by {Math.abs(v - m).toFixed(2)}</Badge> : '—'];
  const rec = s => { const w = s.filter(g => g.res === 'W').length, l = s.filter(g => g.res === 'L').length; return w + l ? <span><N>{w}–{l}</N> <Dim>{fmtP(w / (w + l), 0)}</Dim></span> : '—'; };
  const pmRow = (l, s) => { const p = s.filter(g => g.pm_close != null); if (!p.length) return null; const ag = p.filter(g => g.pm_close > 0.5), dg = p.filter(g => g.pm_close <= 0.5);
    return [<Lbl>{l}</Lbl>, <N>{p.length}</N>, <N>{fmtP(p.reduce((a, g) => a + g.pm_close, 0) / p.length, 1)}</N>, <N>{fmtP(ag.length / p.length, 0)}</N>, rec(ag), rec(dg)]; };
  const pr = ['spread', 'total', 'ml'].map(m => pmRow(L[m], Gw.filter(g => g.market === m))).filter(Boolean);
  const a = agg(Gw, pay);
  return (
    <>
      <div id="s-games" style={{ scrollMarginTop: 72, marginTop: 12 }}><Text size="xs" weight="semibold" style={{ letterSpacing: '0.08em', textTransform: 'uppercase' }} color={usePal(THEME).textSecondary}>Game markets</Text></div>
      <Kpis a={a} props={false} R={Gw} />
      <Two>
        <Panel icon="ball" title="Spread, total, moneyline" sub="Spreads and totals at −110; moneylines at the side's closing price">
          <T cols={['Market', ...HEAD]} rows={[...['spread', 'total', 'ml'].map(m => [<Lbl>{L[m]}</Lbl>, ...cellsOf(agg(Gw.filter(g => g.market === m), pay))]),
            ...['home', 'away', 'over', 'under'].map(sd => { const s = Gw.filter(g => g.side === sd && g.market !== 'ml'); return s.length ? [<Dim>{(sd === 'home' || sd === 'away' ? 'Spread' : 'Total') + ' · ' + sd}</Dim>, ...cellsOf(agg(s, pay))] : null; }).filter(Boolean)]} />
        </Panel>
        <Panel icon="target" title="Vault line vs the market" sub="Average miss against the final score. Lower is better.">
          <T cols={['Market', 'Vault miss', 'Market miss', 'Closer']} rows={[r2('Spread (pts)', sp), r2('Total (pts)', to)]} />
          <Note>If the market's number is closer, Vault's line is context, not an edge.</Note>
        </Panel>
      </Two>
      <Panel icon="trend" title="Polymarket at kickoff" sub="Polymarket's chance for Vault's side at the closing number, the deepest market on NFL game lines">
        {pr.length ? <T cols={['Market', 'Calls', 'Avg chance, our side', 'Agreed', 'Record when it agreed', 'When it did not']} rows={pr} /> : <Empty>No Polymarket closes yet.</Empty>}
        <Note>From the Pendulum Flow orderbook archive (archive.pendulumflow.com, CC BY 4.0). A record that holds up when Polymarket agreed and falls apart when it did not means our leans only win when the sharp money already sits there.</Note>
      </Panel>
    </>
  );
}

function GroupBox({ R, upd }) {
  if (st.grp === 'none') return null;
  const pal = usePal(THEME);
  const keyOf = { grade: r => r.grade || 'Ungraded', market: r => MK[r.market] || r.market, book: r => r._ev ? (r._ev.book || 'No book (Wk 1–3)') : 'No opening price', pos: r => r.pos || '?', side: r => r.side === 'under' ? 'Under' : 'Over' }[st.grp];
  const m = new Map(); R.forEach(r => { const k = keyOf(r); if (!m.has(k)) m.set(k, []); m.get(k).push(r); });
  const g = [...m.entries()].map(([k, rs]) => ({ k, a: agg(rs) })).filter(x => x.a.n).sort((x, y) => y.a.units - x.a.units);
  const mx = Math.max(1, ...g.map(x => Math.abs(x.a.units)));
  const lbl = { grade: 'Grade', market: 'Market', book: st.ev === 'pos' ? 'Best +EV book' : 'Book', pos: 'Position', side: 'Side' }[st.grp];
  const go = k => {
    const p = { page: 0 };
    if (st.grp === 'grade') p.grade = k === 'Ungraded' ? 'all' : (st.grade === k ? 'all' : k);
    else if (st.grp === 'market') { const code = Object.keys(MK).find(c => MK[c] === k) || k; p.mkt = st.mkt === code ? 'all' : code; }
    else if (st.grp === 'book') { if (!/^No /.test(k)) p.books = (st.books.length === 1 && st.books[0] === k) ? [] : [k]; }
    else if (st.grp === 'pos') p.pos = st.pos === k ? 'all' : k;
    else if (st.grp === 'side') { const v = k.toLowerCase(); p.side = st.side === v ? 'all' : v; }
    upd(p);
  };
  return (
    <div style={{ margin: '4px 0 16px' }}>
      {g.length ? <T cols={[lbl, ...HEAD5]} rows={g.map(x => [<LinkRow onClick={() => go(x.k)}>{st.grp === 'grade' ? <GradeB g={x.k === 'Ungraded' ? null : x.k} /> : x.k}</LinkRow>, <N>{x.a.n}</N>, <N>{x.a.W}–{x.a.L}</N>, <N>{fmtP(x.a.wr)}</N>,
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><N t={sgn(x.a.units)}>{fmtU(x.a.units)}</N><i style={{ display: 'inline-block', height: 4, borderRadius: 2, width: Math.round(40 * Math.abs(x.a.units) / mx), background: x.a.units >= 0 ? pal.success : pal.danger }} /></span>, <N t={sgn(x.a.roi)}>{roiTxt(x.a)}</N>])} /> : <Empty>Nothing settled to group.</Empty>}
      <Note>Units {pxLabel()}{st.ev === 'pos' && st.px !== 'bet' ? ' (switch Units at to +EV book price to count them at the price that was +EV)' : ''}. Tap a label to filter the page to it.</Note>
    </div>
  );
}

function Picks({ upd }) {
  const pal = usePal(THEME);
  let R = rows().filter(r => drillOk(r) && (st.res === 'all' || r.res === st.res) && (!st.q.trim() || (r.name + ' ' + r.team + ' ' + r.opp).toLowerCase().includes(st.q.trim().toLowerCase())));
  R.forEach(r => { r.odds = r.side === 'over' ? r.co : r.side === 'under' ? r.cu : null; r.evp = r._ev ? r._ev.ev : null; r._m = mktEv(r); r.mev = r._m ? r._m.ev : null; r.evbook = r._ev ? (r._ev.book || 'No book (Wk 1–3)') : null; });
  const cols = [['name', 'Player'], ['week', 'Wk'], ['market', 'Market'], ['side', 'Pick'], ['proj', 'Proj'], ['actual', 'Actual'], ['grade', 'Grade'], ['pm', 'Win %'], ['edge', 'Edge'], ['evp', 'Vault EV'], ['mev', 'EV'], ['evbook', '+EV book'], ['odds', 'Odds'], ['res', 'Result']];
  const k = st.sort, d = st.dir; R = R.slice().sort((a, b) => { const x = a[k], y = b[k]; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * d || (b.week - a.week); });
  const per = 40, pages = Math.max(1, Math.ceil(R.length / per)); const page = Math.min(Math.max(0, st.page), pages - 1);
  const pg = R.slice(page * per, page * per + per);
  const sortBy = c => upd(st.sort === c ? { dir: st.dir * -1 } : { sort: c, dir: (c === 'name' || c === 'market') ? 1 : -1 });
  const pc = v => v == null ? '—' : (v > 0 ? '+' : '') + (v * 100).toFixed(1) + (v === undefined ? '' : '%');
  return (
    <Panel id="s-picks" icon="list" title="Every settled pick" count={R.length.toLocaleString()} sub="Respects the filters above. Sort any column.">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 18px', alignItems: 'center', marginBottom: 14 }}>
        <SegmentedControl theme={THEME} options={['All', 'Won', 'Lost']} value={{ all: 'All', W: 'Won', L: 'Lost' }[st.res]} onChange={v => upd({ res: { All: 'all', Won: 'W', Lost: 'L' }[v], page: 0 })} />
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><Dim>+EV</Dim><SegmentedControl theme={THEME} options={['All', '+EV', 'Not +EV']} value={{ all: 'All', pos: '+EV', neg: 'Not +EV' }[st.ev]} onChange={v => upd({ ev: { All: 'all', '+EV': 'pos', 'Not +EV': 'neg' }[v], page: 0 })} /></span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><Dim>Break down by</Dim><SegmentedControl theme={THEME} options={['None', 'Grade', 'Market', 'Book', 'Position', 'Side']} value={{ none: 'None', grade: 'Grade', market: 'Market', book: 'Book', pos: 'Position', side: 'Side' }[st.grp]} onChange={v => upd({ grp: { None: 'none', Grade: 'grade', Market: 'market', Book: 'book', Position: 'pos', Side: 'side' }[v], page: 0 })} /></span>
      </div>
      {st.drill && <div style={{ marginBottom: 14 }}><AlertBanner theme={THEME} variant="default" title={`Showing +EV picks: ${st.drill.label}`} description={`${R.length} picks, highest Vault EV first`} /><div style={{ marginTop: 8 }}><Button theme={THEME} size="sm" variant="secondary" onClick={() => upd({ drill: null })}>Show all picks</Button></div></div>}
      <GroupBox R={R} upd={upd} />
      <div style={{ overflowX: 'auto' }}>
        <div style={{ minWidth: 1180 }}>
          <Table theme={THEME}
            columns={cols.map(([c, l]) => <button key={c} type="button" onClick={() => sortBy(c)} aria-sort={k === c ? (d > 0 ? 'ascending' : 'descending') : undefined} style={{ all: 'unset', cursor: 'pointer', color: k === c ? pal.text : 'inherit' }}>{l}{k === c ? (d > 0 ? ' ↑' : ' ↓') : ''}</button>)}
            rows={pg.length ? pg.map(r => [
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}><Av pos={r.pos}>{ini(r.name)}</Av><span><Text size="sm" weight="medium">{r.name}</Text><div><Dim size="xs">{r.team} {r.pos} v {r.opp}</Dim></div></span></span>,
              <N>{r.week}</N>, <N>{MK[r.market] || r.market}</N>, <N>{r.side === 'over' ? 'O' : 'U'} {r.line}</N>, <N>{r.proj ?? '—'}</N>, <N>{r.actual}</N>, <GradeB g={r.grade} />, <N>{fmtP(r.pm, 0)}</N>,
              <N t={sgn(r.edge)}>{r.edge == null ? '—' : (r.edge > 0 ? '+' : '') + (r.edge * 100).toFixed(1)}</N>,
              <span title={r._ev ? (r._ev.book || 'Headline price') + ' at open ' + (r._ev.price > 0 ? '+' : '') + r._ev.price : 'No opening price on record'}><N t={sgn(r.evp)}>{r.evp == null ? '—' : (r.evp > 0 ? '+' : '') + (r.evp * 100).toFixed(1) + '%'}</N></span>,
              <span title={r._m ? 'Best open ' + (r._m.price > 0 ? '+' : '') + r._m.price + (r._m.book ? ' at ' + r._m.book : '') + ' vs the no-vig market' + (r._m.n < 2 ? ' (one price on record, so this is just its juice)' : '') : 'No opening price on record'}><N t={sgn(r.mev)}>{r.mev == null ? '—' : (r.mev > 0 ? '+' : '') + (r.mev * 100).toFixed(1) + '%'}</N></span>,
              <Dim>{r._ev && r._ev.ev > 0 ? r.evbook : '—'}</Dim>, <N>{r.odds == null ? '—' : (r.odds > 0 ? '+' : '−') + Math.abs(r.odds)}</N>, <ResB r={r.res} />,
            ]) : [[<Dim>No picks match.</Dim>, ...Array(13).fill('')]]} />
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
        <Dim>{R.length ? (page * per + 1) + '–' + Math.min(R.length, page * per + per) + ' of ' + R.length.toLocaleString() : '0 picks'}</Dim>
        <span style={{ display: 'inline-flex', gap: 8 }}><Button theme={THEME} size="sm" variant="secondary" disabled={page <= 0} onClick={() => upd({ page: page - 1 })}>Previous</Button><Button theme={THEME} size="sm" disabled={page >= pages - 1} onClick={() => upd({ page: page + 1 })}>Next</Button></span>
      </div>
    </Panel>
  );
}

// ───────────────────────── filter bar ─────────────────────────
function FilterChip({ label, value, set, options, onPick }) {
  // options: [[value,label]]; first is the "all" entry
  const cur = options.find(o => o[0] === value);
  return (
    <DropdownMenu theme={THEME} trigger={<Chip theme={THEME} selected={set} onToggle={() => {}}>{label}{set && cur ? ': ' + cur[1] : ''} ▾</Chip>}
      items={options.map(([v, l]) => ({ label: l, icon: v === value ? '✓' : '', onClick: () => onPick(v) }))} />
  );
}

function FilterBar({ s, upd, weeks, mkts, BOOKS, resetAll, hasFilters }) {
  const pal = usePal(THEME);
  const w = useWidth();
  const weekOpts = ['All', ...weeks.map(x => 'Wk ' + x)];
  const bbMap = { all: 'All picks', bb: 'Best Bets', card: "Vault's Plays" };
  const setBB = v => { const bb = Object.keys(bbMap).find(k => bbMap[k] === v); const p = { bb, page: 0 }; if (bb !== 'all' && s.px === 'flat') p.px = 'posted'; else if (bb === 'all' && s.px === 'posted') p.px = 'flat'; upd(p); };
  const pxName = { flat: '−110', close: 'Closing', bet: '+EV book', posted: 'Posted' }[s.px] + ' · ' + { px: 'Live grades', boost: 'Old 50% pull', mkt: 'Shadow grades', flat: 'Old 55%' }[s.gm];
  const booksTxt = s.books.length ? s.books[0] + (s.books.length > 1 ? ' +' + (s.books.length - 1) : '') : '';
  return (
    <div style={{ position: 'sticky', top: 0, zIndex: 20, background: `linear-gradient(${pal.bg} 85%, transparent)`, padding: '8px 0 12px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
      <span>
        <Popover theme={THEME} trigger={<Button theme={THEME} size="sm" variant="secondary" icon={<Ico d={ICONS.sliders} size={14} />}>Scoring · {pxName}</Button>}>
          <div style={{ width: Math.min(320, w - 64) }}>
            <Text size="xs" weight="semibold" color={pal.textSecondary} style={{ letterSpacing: '0.06em', textTransform: 'uppercase' }}>Count units at</Text>
            <div style={{ margin: '8px 0 16px' }}><Choicebox theme={THEME} value={s.px} onChange={v => upd({ px: v, page: 0 })} options={[
              { id: 'flat', title: '−110 on everything', description: 'Flat price, the break-even baseline' }, { id: 'close', title: 'Closing price', description: "Consensus close at the pick's line" },
              { id: 'bet', title: '+EV book price', description: 'Best opening price among the selected books' }, { id: 'posted', title: 'Posted price', description: 'The price shown when the pick was posted' }]} /></div>
            <Text size="xs" weight="semibold" color={pal.textSecondary} style={{ letterSpacing: '0.06em', textTransform: 'uppercase' }}>Grade model</Text>
            <div style={{ marginTop: 8 }}><Choicebox theme={THEME} value={s.gm} onChange={v => upd({ gm: v, page: 0 })} options={[
              { id: 'px', title: 'Live', description: 'Grades as the board shows them today' }, { id: 'boost', title: 'Old: 50% pull', description: 'Previous rule, half-way toward the market' },
              { id: 'mkt', title: 'Shadow: market', description: 'Market-anchored grade, tracked only' }, { id: 'flat', title: 'Old: fixed 55%', description: 'Original flat 55% bar' }]} /></div>
          </div>
        </Popover>
      </span>
      <div style={{ maxWidth: '100%', overflowX: 'auto' }}><SegmentedControl theme={THEME} options={Object.values(bbMap)} value={bbMap[s.bb]} onChange={setBB} /></div>
      <div style={{ maxWidth: '100%', overflowX: 'auto' }}><SegmentedControl theme={THEME} options={weekOpts} value={s.week === 'all' ? 'All' : 'Wk ' + s.week} onChange={v => upd({ week: v === 'All' ? 'all' : v.slice(3), page: 0 })} /></div>
      <FilterChip label="Grade" value={s.grade} set={s.grade !== 'all'} options={[['all', 'All grades'], ...['A', 'B', 'C', 'D', 'F'].map(g => [g, g])]} onPick={v => upd({ grade: v, page: 0 })} />
      <FilterChip label="Side" value={s.side} set={s.side !== 'all'} options={[['all', 'Both sides'], ['over', 'Over'], ['under', 'Under']]} onPick={v => upd({ side: v, page: 0 })} />
      <FilterChip label="Position" value={s.pos} set={s.pos !== 'all'} options={[['all', 'All positions'], ...['QB', 'RB', 'WR', 'TE'].map(g => [g, g])]} onPick={v => upd({ pos: v, page: 0 })} />
      <FilterChip label="Market" value={s.mkt} set={s.mkt !== 'all'} options={[['all', 'All markets'], ...mkts.map(m => [m, MK[m] || m])]} onPick={v => upd({ mkt: v, page: 0 })} />
      <FilterChip label="+EV" value={s.ev} set={s.ev !== 'all'} options={[['all', 'All picks'], ['pos', '+EV only'], ['neg', 'Not +EV']]} onPick={v => upd({ ev: v, page: 0 })} />
      <Popover theme={THEME} trigger={<Chip theme={THEME} selected={s.books.length > 0} onToggle={() => {}}>Books{booksTxt ? ': ' + booksTxt : ''} ▾</Chip>}>
        <div style={{ minWidth: 220 }}>
          {BOOKS.length ? <Choicebox theme={THEME} multiple options={BOOKS.map(b => ({ id: b, title: b }))} value={s.books} onChange={v => upd({ books: v, page: 0 })} /> : <Dim size="base">Per-book prices start with Week 4 results</Dim>}
          {s.books.length > 0 && <div style={{ marginTop: 10 }}><Button theme={THEME} size="sm" variant="secondary" onClick={() => upd({ books: [], page: 0 })}>Any book</Button></div>}
        </div>
      </Popover>
      {hasFilters && <Button theme={THEME} size="sm" variant="ghost" onClick={resetAll}>Clear all</Button>}
    </div>
  );
}

// ───────────────────────── shell ─────────────────────────
const NAV = [
  ['Record', [['s-overview', 'Overview', 'home'], ['s-grades', 'Grades & edge', 'bars'], ['s-ev', '+EV bets', 'money', 'ev'], ['s-markets', 'Markets', 'table', 'mk'], ['s-clv', 'Line value', 'trend']]],
  ['Models', [['s-games', 'Game markets', 'ball', 'gm'], ['s-shadow', 'Shadow test', 'rings'], ['s-rule', 'Grade rule test', 'rule'], ['s-fade', 'Fade team lean', 'fade']]],
  ['Picks', [['s-picks', 'Every pick', 'list', 'pk']]],
];

function Sidebar({ cur, counts, go, wide }) {
  const pal = usePal(THEME);
  const items = NAV.flatMap(([, xs]) => xs);
  if (!wide) return (
    <nav style={{ display: 'flex', gap: 6, overflowX: 'auto', padding: '10px 0' }} aria-label="Sections">
      {items.map(([id, l]) => <Chip key={id} theme={THEME} selected={cur === id} onToggle={() => go(id)}>{l}</Chip>)}
    </nav>
  );
  return (
    <aside aria-label="Sections" style={{ position: 'sticky', top: 0, alignSelf: 'start', height: '100dvh', padding: '18px 0 24px', display: 'flex', flexDirection: 'column', gap: 18, overflow: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 10px' }}>
        <img src={CREST} alt="" style={{ height: 36, width: 'auto' }} />
        <div style={{ lineHeight: 1.1 }}><Text size="md" weight="bold" style={{ textTransform: 'uppercase' }}>Vault <span style={{ color: pal.accent }}>Fantasy</span></Text><div><Dim size="xs" style={{ letterSpacing: '0.16em', textTransform: 'uppercase' }}>Football</Dim></div></div>
      </div>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {NAV.map(([h, xs], gi) => (
          <div key={h} style={{ marginTop: gi ? 12 : 0 }}>
            <div style={{ padding: '0 10px 6px' }}><Dim size="sm">{h}</Dim></div>
            {xs.map(([id, l, ic, ck]) => {
              const on = cur === id;
              return (
                <button key={id} type="button" onClick={() => go(id)} style={{ all: 'unset', boxSizing: 'border-box', width: '100%', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10, padding: '9px 10px', borderRadius: tokens.radius.sm, ...tokens.type.base, background: on ? pal.accent : 'transparent', color: on ? pal.bg : pal.text, fontWeight: on ? tokens.weight.medium : tokens.weight.regular, transition: `background ${motion.normal} ${motion.easeInOut}` }}>
                  <span style={{ color: on ? pal.bg : pal.textTertiary, display: 'inline-flex' }}><Ico d={ICONS[ic]} /></span>{l}
                  {ck && counts[ck] != null && <span style={{ marginLeft: 'auto', ...tokens.type.xs, padding: '0 6px', borderRadius: 4, background: on ? 'rgba(0,0,0,.18)' : pal.bgMuted, color: on ? pal.bg : pal.textSecondary }}>{counts[ck]}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>
      <div style={{ marginTop: 'auto', padding: '0 10px' }}><Dim size="xs">A record of Vault's model, not betting advice.</Dim></div>
    </aside>
  );
}

function App() {
  const pal = usePal(THEME);
  const [data, setData] = useState(null); const [err, setErr] = useState(false);
  const [s, setS] = useState(loadSaved);
  const [cur, setCur] = useState('s-overview');
  const w = useWidth(); const wide = w >= 900;
  const searchRef = useRef(null);
  useEffect(() => { const load = first => fetch(DATA_SRC, { cache: 'no-store' }).then(r => r.json()).then(d => { setData(d); setErr(false); }).catch(() => { if (first) setErr(true); }); load(true); const t = setInterval(() => load(false), 180000); return () => clearInterval(t); }, []);
  useEffect(() => { save(s); }, [s.bb, s.week, s.grade, s.side, s.pos, s.mkt, s.px, s.gm, s.ev, s.books, s.grp]);
  const upd = patch => setS(o => ({ ...o, ...patch }));

  // one-time dataset prep (mirrors init())
  const prep = useMemo(() => {
    if (!data) return null;
    D = data; const c = data.pcols;
    const mkRow = (a, cols) => { const o = {}; cols.forEach((k, i) => o[k] = a[i]); o.g55 = o.grade; o.res = o.push ? 'P' : o.won === 1 ? 'W' : o.won === 0 ? 'L' : null; o.edge = (o.pm != null && o.pk != null) ? o.pm - o.pk : null; return o; };
    PA = data.props.map(a => mkRow(a, c)).filter(r => r.res);
    PB = (data.bb || []).map(a => mkRow(a, c.concat(['bb', 'bpx', 'bbk']))).filter(r => r.res);
    G = data.games.map(g => Object.assign({}, g, { beat: g.beat_close, res: g.push ? 'P' : g.won_close === 1 ? 'W' : g.won_close === 0 ? 'L' : null })).filter(g => g.res);
    const weeks = uniq(PA.map(r => r.week)).sort((a, b) => a - b);
    const mkts = uniq(PA.map(r => r.market)).sort((a, b) => (MK[a] || a).localeCompare(MK[b] || b));
    const BOOKS = uniq(PA.flatMap(r => r.bo ? Object.keys(r.bo) : [])).sort();
    return { weeks, mkts, BOOKS };
  }, [data]);

  // scroll spy
  useEffect(() => {
    if (!prep) return;
    let tick = false;
    const spy = () => { tick = false; const y = innerHeight * .35; let c = 's-overview';
      document.querySelectorAll('[id^="s-"]').forEach(el => { if (el.getBoundingClientRect().top <= y) c = el.id; });
      if (innerHeight + scrollY >= document.documentElement.scrollHeight - 4) c = 's-picks'; setCur(c); };
    const f = () => { if (!tick) { tick = true; setTimeout(spy, 60); } };
    addEventListener('scroll', f, { passive: true }); return () => removeEventListener('scroll', f);
  }, [prep]);
  useEffect(() => { const k = e => { if (e.key === '/' && !['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) { e.preventDefault(); document.querySelector('input[type=search]')?.focus(); } }; document.addEventListener('keydown', k); return () => document.removeEventListener('keydown', k); }, []);
  const go = id => { const t = document.getElementById(id); if (t) { t.scrollIntoView({ behavior: reduce() ? 'auto' : 'smooth', block: 'start' }); setCur(id); } };

  const shell = (kids) => (
    <div style={{ maxWidth: 1320, margin: '0 auto', padding: '0 16px 48px', color: pal.text, fontFamily: tokens.font.sans, display: wide ? 'grid' : 'block', gridTemplateColumns: '212px minmax(0,1fr)', gap: 20, overflowX: 'clip' }}>{kids}</div>
  );
  if (err) return shell(<div style={{ gridColumn: '1 / -1', paddingTop: 40 }}><AlertBanner theme={THEME} variant="danger" title="Could not load results" description="Reload the page to try again." /></div>);
  if (!prep) return shell(<div style={{ gridColumn: '1 / -1', paddingTop: 40, display: 'grid', gap: 12 }}><Skeleton theme={THEME} height={40} rounded /><Skeleton theme={THEME} height={96} rounded /><Skeleton theme={THEME} height={260} rounded /></div>);

  // render() from the vanilla page: derive picks + grades from the current filters
  st = s;
  P = s.bb === 'card' ? PB.filter(r => r.bb === 'card') : s.bb === 'bb' ? PB : PA;
  P.forEach(r => { r._ev = evInfo(r); });
  P.forEach(r => { r.grade = s.gm === 'px' ? (r.gpx || null) : s.gm === 'boost' ? (r.gb !== undefined && r.gb !== null ? r.gb : r.gpx || null) : s.gm === 'mkt' ? (r.gmk || null) : r.g55; });
  const R = rows();
  const evCt = R.filter(r => r._ev && r._ev.ev > 0 && (r.res === 'W' || r.res === 'L')).length;
  const counts = { ev: evCt, mk: uniq(R.map(r => r.market)).length, gm: G.length, pk: R.length > 999 ? (R.length / 1000).toFixed(1) + 'k' : R.length };
  const a = agg(R);
  const priced = () => { const s2 = R.filter(r => r.res === 'W' || r.res === 'L'); const n = s2.filter(r => sidePx(r, r.side) != null).length; return n + ' of ' + s2.length + ' at a closing price'; };
  const hasFilters = ['grade', 'side', 'pos', 'mkt', 'ev'].some(k => s[k] !== 'all') || s.books.length > 0;
  const resetAll = () => upd({ grade: 'all', side: 'all', pos: 'all', mkt: 'all', ev: 'all', books: [], page: 0, drill: null });
  const gen = new Date(data.generated);
  const meta = data.meta;

  return shell(
    <>
      <Sidebar cur={cur} counts={counts} go={go} wide={wide} />
      <main style={{ paddingTop: 14, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        {!wide && <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}><img src={CREST} alt="" style={{ height: 30 }} /></div>}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 14px', minHeight: 44 }}>
          <div style={{ flex: '1 1 auto' }}><Heading level={1} style={{ margin: 0 }}>Vault Track Record</Heading></div>
          <Dim size="sm">Through <b style={{ color: pal.text }}>Week {Math.max(...PA.map(r => r.week))}</b></Dim>
          <Fresh d={data} />
          <SearchInput theme={THEME} value={s.q} onChange={v => upd({ q: v, page: 0 })} placeholder="Search player or team" shortcut="/" style={{ width: 240 }} />
        </div>
        {!wide && <Sidebar cur={cur} counts={counts} go={go} wide={false} key="m" />}
        <FilterBar s={s} upd={upd} weeks={prep.weeks} mkts={prep.mkts} BOOKS={prep.BOOKS} resetAll={resetAll} hasFilters={hasFilters} />

        <section id="s-overview" style={{ scrollMarginTop: 72 }}><Kpis a={a} props R={R} pricedTxt={priced()} /></section>

        <Two>
          <Panel icon="bulb" title="What the record says" sub={a.n.toLocaleString() + ' settled picks on the current filters'}><Verdict R={R} /></Panel>
          <Panel icon="clock" title="Units by week" sub="Net units per slate, best week highlighted"><WeekChart R={rows('week')} /></Panel>
        </Two>

        <div id="s-grades" style={{ scrollMarginTop: 72 }}>
          <Two>
            <Panel dark icon="cal" title="Grade ladder" sub={s.gm === 'px' ? 'Each pick judged against its own opening price, like the Betting tab' : 'Old grades: every pick judged against a flat 55%'}><Ladder R={rows('grade')} /></Panel>
            <Panel icon="pie" title="Where the picks go" sub="Share of settled picks by market, with win rate"><Bubbles R={R} /></Panel>
          </Two>
        </div>
        <Two>
          <Panel icon="bars" title="Does a bigger edge win more?" sub="Win rate by Vault's edge over the no-vig market (pts)">
            <BarChart aria="Win rate by model edge in points" items={[[-1, 0, '< 0'], [0, .03, '0–3'], [.03, .06, '3–6'], [.06, .1, '6–10'], [.1, .2, '10–20'], [.2, 1, '20+']].map(([lo, hi, l]) => ({ label: l, a: agg(R.filter(r => r.edge != null && r.edge >= lo && r.edge < hi)) }))} />
          </Panel>
          <Panel icon="target" title="Is the Win % honest?" sub="Promised win chance vs how often it hit"><CalibChart R={R} /></Panel>
        </Two>

        <EvCard R={rows('ev')} upd={upd} />
        <MarketTable R={rows('mkt')} upd={upd} />
        <Two>
          <Panel icon="swap" title="Over vs Under" sub="Same filters, split by side"><T cols={['Side', ...HEAD]} rows={[['over', 'Over'], ['under', 'Under']].map(([k, l]) => [<Lbl>{l}</Lbl>, ...cellsOf(agg(rows('side').filter(r => r.side === k)))])} /></Panel>
          <Panel icon="user" title="By position" sub="Same filters, split by position"><T cols={['Pos', ...HEAD]} rows={['QB', 'RB', 'WR', 'TE'].map(k => [<span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><Av pos={k}>{k[0]}</Av><Lbl>{k}</Lbl></span>, ...cellsOf(agg(rows('pos').filter(r => r.pos === k)))])} /></Panel>
        </Two>
        <Clv R={R} />

        <Games week={s.week} />
        <Shadow R={R} />
        <GradeRule R={rows('grade')} />
        <Fade R={rows('grade')} />
        <Picks upd={upd} />

        <div style={{ marginTop: 8, maxWidth: '100ch' }}><Dim size="sm" style={{ lineHeight: 1.6 }}>
          Source: Vault's nightly settlement of every prop it graded and every game line it posted ({meta.props.settled.toLocaleString()} props, {meta.games.settled} game calls settled; {meta.props.unsettled.toLocaleString()} props still open or unmatched). Win and loss are judged at the closing line. Props are counted at −110 or at each side's closing consensus price (Units toggle; rows with no clean two-way closing market stay at −110). Spreads and totals are always at −110. This is a record of the model, not advice.
          {s.bb !== 'all' ? ` Best Bets view: each play is graded at the line it posted with on Vault's Best Bets${s.bb === 'card' ? " (only the plays locked on the weekly Vault's Plays card)" : ' (every play that reached the top of Best Bets before kickoff)'}. “Posted price” counts each at the book price shown when it posted.` : ''}
        </Dim></div>
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(
  <ThemeProvider theme={THEME}><AccentContext.Provider value={ACCENT}><App /></AccentContext.Provider></ThemeProvider>
);
