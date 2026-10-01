// Vault NBA on Halaska UI: a MOCK. Same layout as nba/projections.html (sidebar
// with sections, title row with page controls, KPI cards, chart, rotation table;
// Player Props list + detail), restyled with kit components. Minutes Lab numbers
// are computed from the real player_projections.json (rate x minutes); Props
// figures are the example board's, with mock detail text where the app computes it.
import React, { useState, useMemo, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ThemeProvider, AccentContext, usePal, tokens, motion,
  Card, Badge, Text, Heading, Stack, Table, Button, SegmentedControl, Chip,
  Select, SearchInput, Slider, SwitchToggle, EmptyState, Divider,
} from '../../../../src/halaska-kit.jsx';
import TEAMS from './teams.json';

const THEME = 'dark';
const ACCENT = '#93c5fd';
const svg = d => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" dangerouslySetInnerHTML={{ __html: d }} />;

const PAGES = [
  ['Research', [['Minutes Lab', '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', 'lab'], ['Tonight', '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>', 'tonight'], ['Slate', '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/>', 'slate'], ['Injury Wire', '<path d="M12 3v18M3 12h18"/>', 'wire']]],
  ['Markets', [['Game Lines', '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>', 'lines'], ['Player Props', '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>', 'props'], ['Props Table', '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16"/>', 'ptable'], ['Sharp Price', '<path d="m12 2 3 7h7l-5.5 4.5 2 7.5L12 16.5 5.5 21l2-7.5L2 9h7z"/>', 'sharp']]],
  ['Betting', [['What Works', '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>', 'backtests'], ['Edge Finder', '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>', 'finder'], ['Edges', '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>', 'edges'], ["Pick'em Pairs", '<rect x="3" y="5" width="8" height="14" rx="2"/><rect x="13" y="5" width="8" height="14" rx="2"/><path d="M11 12h2"/>', 'pairs'], ['My Bets', '<path d="M5 3h14v18l-3.5-2-3.5 2-3.5-2L5 21z"/><path d="M9 8h6M9 12h6"/>', 'mybets'], ['Track Record', '<path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-5"/>', 'track']]],
  ['Model', [['Backtest Lab', '<path d="M9 3h6M10 3v6L4 20h16L14 9V3"/>', 'btlab'], ['Data Health', '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>', 'health']]],
];
const SUB = { lab: '', props: 'One decision per prop · where to bet it · why' };

// real per-player ranges for the Knicks (from the live app); other teams show values only
const NY_RANGE = {
  'Jalen Brunson': [[14, 36], [0, 6], [2, 9], [0, 4], [21, 46]], 'OG Anunoby': [[9, 27], [2, 9], [0, 4], [0, 5], [14, 36]],
  'Mikal Bridges': [[4, 20], [0, 6], [0, 6], [0, 3], [8, 29]], 'Karl-Anthony Towns': [[6, 23], [5, 16], [1, 7], [0, 3], [17, 41]],
  'Josh Hart': [[2, 16], [4, 13], [1, 7], [0, 3], [11, 32]], 'Miles McBride': [[1, 15], [0, 4], [0, 4], [0, 4], [3, 21]],
  'Landry Shamet': [[1, 14], [0, 4], [0, 3], [0, 4], [2, 19]], 'Bruce Brown': [[1, 15], [0, 6], [0, 4], [0, 2], [4, 22]],
  'Jose Alvarado': [[1, 15], [0, 5], [1, 6], [0, 3], [5, 23]], 'Andre Drummond': [[0, 12], [3, 11], [0, 3], [0, 2], [5, 23]],
  'Jordan Clarkson': [[1, 15], [0, 5], [0, 3], [0, 1], [3, 20]], 'Ochai Agbaji': [[0, 12], [0, 5], [0, 2], [0, 2], [1, 17]],
  'Drew Eubanks': [[0, 12], [1, 7], [0, 2], [0, 1], [2, 19]],
};

const initials = n => n.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
const Dim = ({ children, size = 'sm', mono, style }) => { const pal = usePal(THEME); return <Text size={size} mono={mono} color={pal.textSecondary} style={style}>{children}</Text>; };
const Mono = ({ children, style }) => { const pal = usePal(THEME); return <span style={{ fontFamily: tokens.font.mono, ...tokens.type.xs, letterSpacing: '0.1em', textTransform: 'uppercase', color: pal.textTertiary, ...style }}>{children}</span>; };
const useWidth = () => { const [w, setW] = useState(window.innerWidth); useEffect(() => { const f = () => setW(window.innerWidth); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f); }, []); return w; };
const Av = ({ name, size = 36 }) => { const pal = usePal(THEME); return <span style={{ width: size, height: size, borderRadius: '50%', background: pal.bgMuted, color: pal.textSecondary, ...tokens.type.sm, fontWeight: tokens.weight.medium, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>{initials(name)}</span>; };
const Num = ({ children, tone, size = 'sm', weight }) => { const pal = usePal(THEME); return <Text size={size} weight={weight} color={tone === 'up' ? pal.success : tone === 'down' ? pal.danger : undefined} style={{ fontVariantNumeric: 'tabular-nums' }}>{children}</Text>; };

// ───────────────────────── Minutes Lab ─────────────────────────
const statsOf = (p, m) => ({ pts: p.r.pts * m, reb: p.r.reb * m, ast: p.r.ast * m, tpm: p.r['3pm'] * m, pra: (p.r.pts + p.r.reb + p.r.ast) * m, sb: (p.r.stl + p.r.blk) * m });

function KpiCard({ label, value, note, icon }) {
  const pal = usePal(THEME);
  return (
    <Card padding={18}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}><Text size="base">{label}</Text><span style={{ color: pal.textTertiary }}>{svg(icon)}</span></div>
      <div style={{ margin: '14px 0 4px' }}><Text size="xxl" weight="bold" style={{ fontVariantNumeric: 'tabular-nums' }}>{value}</Text></div>
      <Dim>{note}</Dim>
    </Card>
  );
}

function MinutesChart({ rows }) {
  const pal = usePal(THEME);
  const W = 760, H = 200, L = 30, B = 26, T = 10, top = rows.slice(0, 15);
  const mx = 40, x = i => L + (W - L - 10) * (i / Math.max(top.length - 1, 1)), y = v => T + (1 - v / mx) * (H - T - B);
  const path = k => top.map((r, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(r[k]).toFixed(1)).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Minutes by player" style={{ display: 'block', fontFamily: tokens.font.mono, fontSize: 10 }}>
      {[0, 10, 20, 30, 40].map(v => <g key={v}><line x1={L} x2={W - 10} y1={y(v)} y2={y(v)} stroke={pal.borderSubtle} /><text x={L - 8} y={y(v) + 3} textAnchor="end" fill={pal.textTertiary}>{v}</text></g>)}
      <path d={path('now') + ` L${x(top.length - 1)},${y(0)} L${x(0)},${y(0)} Z`} fill={pal.accent} opacity=".08" />
      <path d={path('proj')} fill="none" stroke={pal.textTertiary} strokeWidth="1.5" strokeDasharray="4 4" />
      <path d={path('now')} fill="none" stroke={pal.text} strokeWidth="2" strokeLinejoin="round" />
      {top.map((r, i) => <g key={i}><circle cx={x(i)} cy={y(r.now)} r="3" fill={pal.text} /><text x={x(i)} y={H - 8} textAnchor="middle" fill={pal.textTertiary}>{r.n.split(' ').slice(-1)[0].slice(0, 8)}</text></g>)}
    </svg>
  );
}

function MinutesLab({ team, setTeam, narrow }) {
  const pal = usePal(THEME);
  const T = TEAMS[team];
  const base = useMemo(() => T.players.map(p => ({ ...p, proj: p.m })), [team]);
  const [mins, setMins] = useState({}); const [out, setOut] = useState({});
  useEffect(() => { setMins({}); setOut({}); }, [team]);
  const rows = base.map(p => { const now = out[p.n] ? 0 : (mins[p.n] ?? p.proj); return { ...p, now, s: statsOf(p, now) }; });
  const rot = rows.slice(0, 13), rest = rows.slice(13);
  const sumMin = rows.reduce((a, r) => a + r.now, 0), sumPts = rows.reduce((a, r) => a + r.s.pts, 0);
  const top = rows.slice().sort((a, b) => b.s.pts - a.s.pts)[0];
  const changed = rows.filter(r => Math.abs(r.now - r.proj) > .05);
  const movers = changed.slice().sort((a, b) => Math.abs(b.s.pra - statsOf(b, b.proj).pra) - Math.abs(a.s.pra - statsOf(a, a.proj).pra)).slice(0, 5);
  const rng = NY_RANGE; const isNY = team === 'NY';
  const fmtR = (r, i, name) => isNY && rng[name] ? <Dim size="xs" mono>{rng[name][i][0]}–{rng[name][i][1]}</Dim> : null;
  const cell = (v, i, name) => <div style={{ lineHeight: 1.2 }}><Num>{v.toFixed(1)}</Num><div>{fmtR(null, i, name)}</div></div>;
  const trow = r => [
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}><Av name={r.n} size={32} /><span><Text size="sm" weight="medium">{r.n}</Text>{r.inj ? <> <Badge variant="warning">{String(r.inj).slice(0, 14)}</Badge></> : null}{r.from ? <> <Badge variant="accent">New · was {r.from}</Badge></> : null}<div><Dim size="xs">{r.pos} · depth {r.rank} · {r.lm} mpg last season</Dim></div></span></span>,
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 250 }}>
      <Chip theme={THEME} selected={!!out[r.n]} onToggle={() => setOut(o => ({ ...o, [r.n]: !o[r.n] }))}>OUT</Chip>
      <div style={{ flex: 1, minWidth: 90 }}><Slider theme={THEME} min={0} max={48} value={Math.round(r.now)} onChange={v => { setMins(m => ({ ...m, [r.n]: v })); setOut(o => ({ ...o, [r.n]: false })); }} aria-label={`${r.n} minutes`} /></div>
      <Num weight="semibold">{r.now.toFixed(0)}</Num>
    </div>,
    cell(r.s.pts, 0, r.n), cell(r.s.reb, 1, r.n), cell(r.s.ast, 2, r.n), cell(r.s.tpm, 3, r.n), cell(r.s.pra, 4, r.n), <Num>{r.s.sb.toFixed(1)}</Num>,
  ];
  const cols = ['Player', 'Minutes', 'PTS', 'REB', 'AST', '3PM', 'PRA', 'STL+BLK'];
  return (
    <Stack gap={16}>
      <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr 1fr' : 'repeat(4,1fr)', gap: 16 }}>
        <KpiCard label="Team points per 240 min" value={(sumMin ? sumPts * 240 / sumMin : 0).toFixed(1)} note={changed.length ? 'Moves with your edits' : 'Matches the projection'} icon='<path d="M3 17l6-6 4 4 8-8"/>' />
        <KpiCard label="Rotation minutes" value={Math.round(sumMin)} note="If everyone listed plays · a game is 240" icon='<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>' />
        <KpiCard label="Top scorer" value={top.n.split(' ').slice(-1)[0]} note={`${top.s.pts.toFixed(1)} pts · ${top.s.pra.toFixed(1)} PRA`} icon='<path d="m12 2 3 7h7l-5.5 4.5 2 7.5L12 16.5 5.5 21l2-7.5L2 9h7z"/>' />
        <KpiCard label="Players changed" value={changed.length} note={changed.length ? 'Reset team to undo' : 'No edits yet'} icon='<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>' />
      </div>
      <Card padding={20}>
        <Text size="lg" weight="semibold">Minutes by player</Text>
        <div style={{ marginBottom: 8 }}><Dim>Your minutes against the season-start projection, top 15 by minutes</Dim></div>
        <MinutesChart rows={rows} />
        <div style={{ display: 'flex', gap: 16, marginTop: 8 }}><span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><i style={{ width: 14, height: 2, background: pal.text }} /><Dim size="xs" mono>Your minutes</Dim></span><span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><i style={{ width: 14, borderTop: `2px dashed ${pal.textTertiary}` }} /><Dim size="xs" mono>Projection</Dim></span></div>
      </Card>
      <Card padding={0} style={{ overflow: 'hidden' }}>
        <div style={{ padding: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div><Text size="lg" weight="semibold">Rotation</Text><div><Dim>Change a player's minutes and every stat moves with them</Dim></div></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <SwitchToggle theme={THEME} checked={true} onChange={() => {}} label="Move freed minutes to teammates" />
            <Button theme={THEME} size="sm" variant="secondary" onClick={() => { setMins({}); setOut({}); }}>Reset team</Button>
            <Button theme={THEME} size="sm" variant="secondary" onClick={() => { const s = rows.reduce((a, r) => a + r.now, 0) || 1; const k = 240 / s; const m = {}; rows.forEach(r => { m[r.n] = Math.min(48, Math.round(r.now * k)); }); setMins(m); }}>Fit to 240</Button>
          </div>
        </div>
        <div style={{ overflowX: 'auto' }}><div style={{ minWidth: 900 }}><Table theme={THEME} columns={cols} rows={rot.map(trow)} /></div></div>
        <div style={{ padding: '10px 20px' }}><Dim>Beyond the 13-man rotation · give minutes to include</Dim></div>
        <div style={{ overflowX: 'auto' }}><div style={{ minWidth: 900 }}><Table theme={THEME} columns={cols} rows={rest.map(trow)} /></div></div>
      </Card>
      <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr' : '1fr 1fr', gap: 16 }}>
        <Card padding={20}><Text size="lg" weight="semibold">Biggest movers</Text><div style={{ marginBottom: 10 }}><Dim>Largest change in points + rebounds + assists from your edits</Dim></div>
          {movers.length ? movers.map(r => { const d = r.s.pra - statsOf(r, r.proj).pra; return <div key={r.n} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${pal.borderSubtle}` }}><Text size="sm">{r.n}</Text><Num tone={d >= 0 ? 'up' : 'down'}>{d >= 0 ? '+' : ''}{d.toFixed(1)} PRA</Num></div>; }) : <Dim size="base">No changes yet. Mark a player OUT or move a slider and the players who gain or lose the most show up here.</Dim>}
        </Card>
        <Card padding={20}><Text size="lg" weight="semibold">Recent changes</Text><div style={{ marginBottom: 10 }}><Dim>What you changed on this team, newest first</Dim></div>
          {changed.length ? changed.map(r => <div key={r.n} style={{ padding: '6px 0', borderBottom: `1px solid ${pal.borderSubtle}` }}><Text size="sm">{r.n}: {r.proj.toFixed(0)} to {r.now.toFixed(0)} min</Text></div>) : <Dim size="base">Nothing changed on the {T.name} yet.</Dim>}
        </Card>
      </div>
    </Stack>
  );
}

// ───────────────────────── Player Props ─────────────────────────
const PROPS = [
  { n: 'OG Anunoby', stat: '3-pointers', proj: 2.4, line: 'Kalshi NO on 3+', px: 50, edge: 6.3, usual: '0 to 4', sd: '27 to 41', min: 33.7, mrange: '27 to 41 likely · usual 36', game: 'NY vs SA · Sat 8:30 PM ET', conf: true, pct: 58, ret: '+$9.39', bets: '3,200', stake: 20 },
  { n: 'Jalen Brunson', stat: '3-pointers', proj: 2.3, line: 'Kalshi NO on 3+', px: 56, edge: 3.8, usual: '0 to 5', min: 34.2, mrange: '28 to 41 likely · usual 36', game: 'NY vs SA · Sat 8:30 PM ET', conf: true, pct: 62, ret: '+$9.39', bets: '3,200', stake: 12 },
  { n: 'Mikal Bridges', stat: '3-pointers', proj: 1.3, line: 'Kalshi NO on 2+', px: 57, edge: 3.7, usual: '0 to 3', min: 32.1, mrange: '26 to 38 likely · usual 33', game: 'NY vs SA · Sat 8:30 PM ET', conf: true, pct: 63, ret: '+$9.39', bets: '3,200', stake: 12 },
  { n: 'Karl-Anthony Towns', stat: '3-pointers', proj: 1.3, line: 'Kalshi NO on 1+', px: 26, edge: 3.5, usual: '0 to 3', min: 30.4, mrange: '24 to 36 likely · usual 31', game: 'NY vs SA · Sat 8:30 PM ET', conf: true, pct: 32, ret: '+$9.39', bets: '3,200', stake: 10 },
  { n: 'Keldon Johnson', stat: '3-pointers', proj: 0.8, line: 'Kalshi NO on 5+', px: 94, edge: 3.5, usual: '0 to 3', min: 22.0, mrange: '15 to 28 likely · usual 22', game: 'NY vs SA · Sat 8:30 PM ET', conf: false, pct: 98, ret: '+$9.39', bets: '3,200', stake: 10 },
  { n: 'Josh Hart', stat: '3-pointers', proj: 1.3, line: 'Kalshi NO on 1+', px: 25, edge: 3.1, usual: '0 to 3', min: 29.0, mrange: '23 to 35 likely · usual 30', game: 'NY vs SA · Sat 8:30 PM ET', conf: true, pct: 31, ret: '+$9.39', bets: '3,200', stake: 8 },
];
const CHIPS = [['Bets that passed', 6], ['All edges 3%+', 9], ['Kalshi NO', 7], ["Pick'em plays", 0], ['Sharp money', 0], ['Watching', 0], ['Everything', 132]];
const STATS = ['All', '3PM', 'AST', 'PTS', 'REB', 'P+A', 'P+R', 'PRA', 'R+A'];

function PropsPage({ narrow }) {
  const pal = usePal(THEME);
  const [chip, setChip] = useState('Bets that passed'); const [stat, setStat] = useState('All'); const [sort, setSort] = useState('Sort: bets you can trust'); const [q, setQ] = useState('');
  const [sel, setSel] = useState(0); const [watch, setWatch] = useState({});
  const list = PROPS.filter(p => (stat === 'All' || stat === '3PM') && (!q || p.n.toLowerCase().includes(q.toLowerCase())) && (chip !== "Pick'em plays" && chip !== 'Sharp money' && chip !== 'Watching')).sort((a, b) => sort.includes('edge') ? b.edge - a.edge : 0);
  const p = list[sel] && PROPS.includes(list[sel]) ? list[sel] : list[0];
  const cost = p ? p.px + 2 : 0, prob = p ? cost + p.edge : 0;
  return (
    <Stack gap={16}>
      <div style={{ border: `1px dashed ${pal.border}`, borderRadius: tokens.radius.md, padding: '16px 20px' }}>
        <Text size="base" weight="semibold">Example board.</Text>
        <div style={{ marginTop: 6 }}><Dim size="base" style={{ lineHeight: 1.6 }}>No player props are listed yet. Kalshi lists them the morning of a game; the next game is MIA @ TOR, Sat, Oct 3 at 7:00 PM ET. This is NY @ SA on June 13, 2026, last season's final game, at its pre-tip prices, projected with only what was known that morning (each player's minutes, rates and the model's state before tip). Kalshi shows the last trade as both bid and ask. <b style={{ color: pal.text }}>Mock figures where noted.</b></Dim></div>
      </div>
      <Card padding={20}>
        <Stack gap={14}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            {CHIPS.map(([l, n]) => <Chip key={l} theme={THEME} selected={chip === l} onToggle={() => setChip(l)}>{l} {n}</Chip>)}
            <span style={{ marginLeft: 'auto' }}><Button theme={THEME} size="sm" variant="secondary">Alerts</Button></span>
          </div>
          <Divider theme={THEME} spacing={0} />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ maxWidth: '100%', overflowX: 'auto' }}><SegmentedControl theme={THEME} options={STATS} value={stat} onChange={setStat} /></div>
            <div style={{ width: 240 }}><Select theme={THEME} value={sort} onChange={setSort} options={['Sort: bets you can trust', 'Sort: biggest edge']} /></div>
          </div>
          <div style={{ maxWidth: 260 }}><SearchInput theme={THEME} value={q} onChange={setQ} placeholder="Find a player" shortcut="" /></div>
        </Stack>
      </Card>
      <Card padding={0} style={{ overflow: 'hidden' }}>
        {list.length ? list.map((r, i) => {
          const on = r === p;
          return (
            <button key={r.n} type="button" onClick={() => setSel(i)} style={{ all: 'unset', boxSizing: 'border-box', width: '100%', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px', borderBottom: i < list.length - 1 ? `1px solid ${pal.borderSubtle}` : 'none', background: on ? pal.bgSubtle : 'transparent', transition: `background ${motion.normal} ${motion.easeInOut}` }}>
              <Av name={r.n} />
              <span style={{ flex: 1, minWidth: 0 }}><Text size="md" weight="semibold">{r.n}</Text><div><Dim>{r.stat} · proj {r.proj} · {r.line} · {r.px}¢</Dim></div></span>
              <span style={{ textAlign: 'right' }}><Badge variant="success">BET</Badge><div><Num tone="up" weight="medium">+{r.edge.toFixed(1)}%</Num></div></span>
            </button>
          );
        }) : <EmptyState theme={THEME} title="Nothing here" description="No props match this filter on the example board." />}
      </Card>
      {p && <>
        <Card padding={24}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <Heading level={2} style={{ margin: 0 }}>{p.n}</Heading>
              <div style={{ margin: '4px 0 10px', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}><Dim size="base">{p.stat} · {p.game}</Dim>{p.conf && <Badge variant="default" style={{ textTransform: 'none', letterSpacing: 0 }}>Starting five confirmed</Badge>}</div>
            </div>
            <div style={{ textAlign: 'right' }}><Dim>Tonight's projection</Dim><div><Text size="display" weight="bold" style={{ fontVariantNumeric: 'tabular-nums' }}>{p.proj}</Text></div><Dim>usually {p.usual}</Dim></div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 14, flexWrap: 'wrap' }}>
            <Text size="base">Minutes <b>{p.min}</b></Text>
            <div style={{ flex: 1, minWidth: 160 }}><Slider theme={THEME} value={Math.round(p.min)} onChange={() => {}} min={0} max={48} aria-label="Minutes" /></div>
            <Dim>{p.mrange}</Dim>
          </div>
          <div style={{ marginTop: 14 }}><Button theme={THEME} size="sm" variant="secondary" onClick={() => setWatch(w => ({ ...w, [p.n]: !w[p.n] }))}>{watch[p.n] ? '★ Watching' : '☆ Watch'}</Button></div>
        </Card>
        <div style={{ border: `1px solid ${pal.success}55`, background: pal.successBg, borderRadius: tokens.radius.md, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}><Badge variant="success">BET</Badge><Text size="lg" weight="semibold">{p.line} at {p.px}¢</Text><Badge variant="success" style={{ textTransform: 'none', letterSpacing: 0 }}>● Passed the backtest</Badge></div>
          <Text size="md" style={{ lineHeight: 1.6 }}>We think he gets {p.line.includes('NO') ? 'fewer than the line' : 'the line'} {Math.round(prob)}% of the time; Kalshi charges {cost}¢ with its fee. That is worth +${Math.round(p.edge / cost * 1000)} per $100.</Text>
          <div style={{ marginTop: 10 }}><Dim size="base">Edge <b style={{ color: pal.text }}>+{p.edge.toFixed(1)}%</b> (our {prob.toFixed(1)}% vs {cost.toFixed(1)}% cost). This kind of bet (Kalshi 3-pointers NO) returned <b style={{ color: pal.text }}>{p.ret} per $100</b> over {p.bets} bets last season.</Dim></div>
          <div style={{ marginTop: 10 }}><Dim size="base">Suggested stake <b style={{ color: pal.text, fontSize: 16 }}>${p.stake}</b> · ¼ Kelly on your $1,000 bankroll, at most 2% a play. Set on Edges.</Dim></div>
        </div>
        <Card padding={0} style={{ overflow: 'hidden' }}>
          <div style={{ padding: 20 }}><Text size="lg" weight="semibold">Ways to bet it</Text><div style={{ marginTop: 4 }}><Dim size="base">Every venue, line and side for this prop, the recommended bet first. Value is what a $100 bet makes on average if our chance is right; fees and vig are already in the price. Pass means the edge is under 3%.</Dim></div></div>
          <div style={{ overflowX: 'auto' }}><div style={{ minWidth: 560 }}>
            <Table theme={THEME} columns={['Venue', 'Bet', 'Price', 'Our chance', 'Value per $100', 'Verdict']} rows={[
              [<Text size="sm" weight="medium">Kalshi</Text>, <Num>{p.line.replace('Kalshi ', '')}</Num>, <Num>{p.px}¢</Num>, <Num>{prob.toFixed(1)}%</Num>, <Num tone="up">+${Math.round(p.edge / cost * 1000)}</Num>, <Badge variant="success">Bet</Badge>],
              [<Text size="sm" weight="medium">Kalshi</Text>, <Num>NO on {p.line.includes('3+') ? '4+' : '3+'}</Num>, <Num>{Math.min(98, p.px + 18)}¢</Num>, <Num>{Math.min(99, prob + 9).toFixed(1)}%</Num>, <Num tone="up">+$2</Num>, <Badge>Pass</Badge>],
              [<Text size="sm" weight="medium">Kalshi</Text>, <Num>YES on {p.line.includes('3+') ? '3+' : '2+'}</Num>, <Num>{100 - p.px}¢</Num>, <Num>{(100 - prob).toFixed(1)}%</Num>, <Num tone="down">−$9</Num>, <Badge variant="danger">No</Badge>],
            ]} />
          </div></div>
          <div style={{ padding: '10px 20px' }}><Dim size="xs">Mock figures: the Ways to bet it rows and the non-Anunoby detail numbers are generated from the example row, not priced by the model.</Dim></div>
        </Card>
      </>}
    </Stack>
  );
}

// ───────────────────────── shell ─────────────────────────
function Placeholder({ title }) {
  return <Card padding={24}><EmptyState theme={THEME} title={`${title}: same shell, not mocked here`} description="The mock covers Minutes Lab and Player Props. The other pages keep today's layout and would take the same cards, tables and chips." /></Card>;
}

function Sidebar({ page, go, narrow }) {
  const pal = usePal(THEME);
  const items = PAGES.flatMap(([, xs]) => xs);
  if (narrow) return <nav style={{ display: 'flex', gap: 6, overflowX: 'auto', padding: '10px 16px', borderBottom: `1px solid ${pal.borderSubtle}` }}>{items.map(([n, , id]) => <Chip key={id} theme={THEME} selected={page === id} onToggle={() => go(id)}>{n}</Chip>)}</nav>;
  return (
    <aside style={{ width: 232, flex: 'none', position: 'sticky', top: 0, height: '100dvh', overflowY: 'auto', borderRight: `1px solid ${pal.borderSubtle}`, padding: '20px 12px', background: pal.bg }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 8px 18px' }}>
        <span style={{ width: 36, height: 36, borderRadius: tokens.radius.sm, background: pal.text, color: pal.bg, ...tokens.type.xs, fontWeight: tokens.weight.bold, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>NBA</span>
        <div><Text size="md" weight="semibold">Vault NBA</Text><div><Mono>2026-27 · {page === 'lab' ? 'Minutes Lab' : page === 'props' ? 'Player Props' : 'Mock'}</Mono></div></div>
      </div>
      {PAGES.map(([sec, xs]) => (
        <div key={sec} style={{ marginBottom: 10 }}>
          <div style={{ padding: '8px 10px 6px' }}><Mono>{sec}</Mono></div>
          {xs.map(([n, ic, id]) => {
            const on = page === id;
            return <button key={id} type="button" onClick={() => go(id)} aria-current={on ? 'page' : undefined} style={{ all: 'unset', boxSizing: 'border-box', width: '100%', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12, padding: '9px 10px', borderRadius: tokens.radius.sm, ...tokens.type.base, background: on ? pal.bgMuted : 'transparent', color: on ? pal.text : pal.textSecondary, fontWeight: on ? tokens.weight.medium : tokens.weight.regular, transition: `background ${motion.normal} ${motion.easeInOut}` }}><span style={{ display: 'inline-flex', color: on ? pal.text : pal.textTertiary }}>{svg(ic)}</span>{n}</button>;
          })}
        </div>
      ))}
    </aside>
  );
}

function App() {
  const pal = usePal(THEME); const w = useWidth(); const narrow = w < 900;
  const [page, setPage] = useState('lab'); const [team, setTeam] = useState('NY'); const [q, setQ] = useState('');
  const name = PAGES.flatMap(([, x]) => x).find(x => x[2] === page)[0];
  const teamOpts = Object.entries(TEAMS).map(([k, t]) => ({ value: k, label: t.name })).sort((a, b) => a.label.localeCompare(b.label));
  return (
    <div style={{ display: narrow ? 'block' : 'flex', minHeight: '100dvh', color: pal.text, fontFamily: tokens.font.sans }}>
      <Sidebar page={page} go={setPage} narrow={narrow} />
      <main style={{ flex: 1, minWidth: 0 }}>
        <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', padding: '16px 28px', borderBottom: `1px solid ${pal.borderSubtle}` }}>
          <div>
            <Heading level={2} style={{ margin: 0 }}>{page === 'lab' ? TEAMS[team].name : name}</Heading>
            <Mono>{page === 'lab' ? `${team} · 2026-27 · season start` : SUB[page] || 'Mock'}</Mono>
          </div>
          {page === 'lab' ? <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}><div style={{ width: 230 }}><Select theme={THEME} value={team} onChange={setTeam} options={teamOpts} /></div><div style={{ width: 230 }}><SearchInput theme={THEME} value={q} onChange={setQ} placeholder="Search players" shortcut="" /></div></div>
            : page === 'props' ? <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}><Badge variant="warning" style={{ textTransform: 'none', letterSpacing: 0 }}>● Example</Badge><Dim size="base">Last season's prices</Dim></div> : null}
        </header>
        <div style={{ padding: narrow ? 16 : 28, maxWidth: 1100 }}>
          {page === 'lab' ? <MinutesLab team={team} setTeam={setTeam} narrow={narrow} /> : page === 'props' ? <PropsPage narrow={narrow} /> : <Placeholder title={name} />}
        </div>
      </main>
    </div>
  );
}

function Bg() { const pal = usePal(THEME); useEffect(() => { document.body.style.background = pal.bg; }, [pal.bg]); return <App />; }
createRoot(document.getElementById('root')).render(<ThemeProvider theme={THEME}><AccentContext.Provider value={ACCENT}><Bg /></AccentContext.Provider></ThemeProvider>);
