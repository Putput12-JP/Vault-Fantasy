// Halaska UI views for the Vault NBA app (nba/ui/projections.template.html).
// The page keeps all its logic (projection, rebalancing, pricing, storage) in plain JS and
// hands these views PLAIN DATA plus callbacks; the views only draw. Bundled to dist.js by
// build.mjs and inlined into projections.html by scripts/render_app.py (so CI needs no npm).
import React, { useState, useEffect, useRef } from 'react';
import {
  usePal, tokens, motion, Card, Badge, Text, Heading, Stack, Table, Button, Chip, SwitchToggle, Slider, Divider,
  SegmentedControl, Select, SearchInput, EmptyState,
} from '../../../src/halaska-kit.jsx';

const THEME = 'dark';
const Dim = ({ children, size = 'sm', mono, style }) => { const pal = usePal(THEME); return <Text size={size} mono={mono} color={pal.textSecondary} style={style}>{children}</Text>; };
const Mono = ({ children, style }) => { const pal = usePal(THEME); return <span style={{ fontFamily: tokens.font.mono, ...tokens.type.xs, letterSpacing: '0.1em', textTransform: 'uppercase', color: pal.textTertiary, ...style }}>{children}</span>; };
const Tone = ({ children, tone, size = 'sm', weight, mono }) => { const pal = usePal(THEME); return <Text size={size} weight={weight} mono={mono} color={tone === 'pos' ? pal.success : tone === 'neg' ? pal.danger : undefined} style={{ fontVariantNumeric: 'tabular-nums' }}>{children}</Text>; };
const Av = ({ ini, size = 32 }) => { const pal = usePal(THEME); return <span style={{ width: size, height: size, borderRadius: '50%', background: pal.bgMuted, color: pal.textSecondary, ...tokens.type.xs, fontWeight: tokens.weight.medium, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>{ini}</span>; };
const useWidth = () => { const [w, setW] = useState(window.innerWidth); useEffect(() => { const f = () => setW(window.innerWidth); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f); }, []); return w; };
const Ico = ({ html, size = 16 }) => <span aria-hidden="true" style={{ display: 'inline-flex', width: size, height: size }} dangerouslySetInnerHTML={{ __html: html.replace('<svg ', `<svg width="${size}" height="${size}" `) }} />;

// ───────────────────────── sidebar ─────────────────────────
export function Sidebar({ pages, view, season, pvCount, onGo }) {
  const pal = usePal(THEME);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, minHeight: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 8px' }}>
        <span style={{ width: 36, height: 36, borderRadius: tokens.radius.sm, background: pal.text, color: pal.bg, ...tokens.type.xs, fontWeight: tokens.weight.bold, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>NBA</span>
        <div style={{ minWidth: 0 }}><Text size="md" weight="semibold">Vault NBA</Text><div><Mono>{season}</Mono></div></div>
      </div>
      <nav aria-label="Pages">
        {pages.map(([sec, items]) => (
          <div key={sec} style={{ marginBottom: 10 }}>
            <div style={{ padding: '8px 10px 6px' }}><Mono>{sec}</Mono></div>
            {items.map(([name, icon, what, live]) => {
              if (!live) return <div key={name} title={what} aria-disabled="true" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 10px', opacity: .5, ...tokens.type.base, color: pal.textTertiary }}><Ico html={icon} />{name}<Badge style={{ marginLeft: 'auto' }}>Soon</Badge></div>;
              const on = view === live;
              return (
                <a key={live} href={'#' + live} title={what} aria-current={on ? 'page' : undefined} onClick={e => { e.preventDefault(); onGo(live); }}
                  style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 10px', borderRadius: tokens.radius.sm, textDecoration: 'none', ...tokens.type.base, background: on ? pal.bgMuted : 'transparent', color: on ? pal.text : pal.textSecondary, fontWeight: on ? tokens.weight.medium : tokens.weight.regular, transition: `background ${motion.normal} ${motion.easeInOut}, color ${motion.normal} ${motion.easeInOut}` }}>
                  <span style={{ display: 'inline-flex', color: on ? pal.text : pal.textTertiary }}><Ico html={icon} /></span>{name}
                  {live === 'props' && pvCount ? <Badge variant="accent" style={{ marginLeft: 'auto' }}>{pvCount}</Badge> : null}
                </a>
              );
            })}
          </div>
        ))}
      </nav>
      <div style={{ marginTop: 'auto', border: `1px solid ${pal.borderSubtle}`, borderRadius: tokens.radius.md, padding: 12 }}>
        <Text size="sm" weight="semibold">Shadow mode</Text>
        <div style={{ marginTop: 2 }}><Dim size="xs" style={{ lineHeight: 1.5 }}>No live bets until a signal passes its gate on this season's games.</Dim></div>
      </div>
    </div>
  );
}

// ───────────────────────── Minutes Lab ─────────────────────────
function Kpi({ k }) {
  const pal = usePal(THEME);
  return (
    <Card padding={18}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}><Text size="base">{k.label}</Text><span style={{ color: pal.textTertiary }}><Ico html={k.icon} /></span></div>
      <div style={{ margin: '14px 0 4px' }}><Text size="xxl" weight="bold" style={{ fontVariantNumeric: 'tabular-nums' }}>{k.val}</Text></div>
      <Dim>{k.delta != null && Math.abs(k.delta) >= .05 ? <><Tone tone={k.delta > 0 ? 'pos' : 'neg'}>{k.delta > 0 ? '+' : ''}{k.delta.toFixed(1)}</Tone> vs projection</> : k.hint}</Dim>
    </Card>
  );
}

function MinutesChart({ pts }) {
  const pal = usePal(THEME);
  const [hov, setHov] = useState(null);
  const W = 760, H = 240, L = 34, R = 10, T = 12, B = 34;
  const mx = Math.max(40, Math.ceil(Math.max(...pts.map(p => Math.max(p.now, p.base))) / 10) * 10);
  const x = i => L + (W - L - R) * (i / Math.max(pts.length - 1, 1)), y = v => T + (1 - v / mx) * (H - T - B);
  const path = k => pts.map((p, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(p[k]).toFixed(1)).join(' ');
  const ticks = []; for (let v = 0; v <= mx; v += 10) ticks.push(v);
  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Minutes by player" style={{ display: 'block', fontFamily: tokens.font.mono, fontSize: 10 }} onMouseLeave={() => setHov(null)}>
        {ticks.map(v => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={pal.borderSubtle} /><text x={L - 8} y={y(v) + 3} textAnchor="end" fill={pal.textTertiary}>{v}</text></g>)}
        <path d={path('now') + ` L${x(pts.length - 1)},${y(0)} L${x(0)},${y(0)} Z`} fill={pal.accent} opacity=".08" />
        <path d={path('base')} fill="none" stroke={pal.textTertiary} strokeWidth="1.5" strokeDasharray="4 4" />
        <path d={path('now')} fill="none" stroke={pal.text} strokeWidth="2" strokeLinejoin="round" />
        {pts.map((p, i) => <g key={i} onMouseEnter={() => setHov(i)}><rect x={x(i) - 18} y={T} width="36" height={H - T - B} fill="transparent" /><circle cx={x(i)} cy={y(p.now)} r={hov === i ? 5 : 3} fill={pal.text} /><text x={x(i)} y={H - 12} textAnchor="middle" fill={hov === i ? pal.text : pal.textTertiary}>{p.last.slice(0, 8)}</text></g>)}
      </svg>
      {hov != null && <div style={{ position: 'absolute', left: `${(x(hov) / W) * 100}%`, top: 0, transform: 'translateX(-50%)', background: pal.bgElevated, border: `1px solid ${pal.border}`, borderRadius: tokens.radius.sm, padding: '6px 10px', pointerEvents: 'none', whiteSpace: 'nowrap' }}><Text size="sm" weight="semibold">{pts[hov].name}</Text><div><Dim size="xs">{pts[hov].now.toFixed(1)} min · projection {pts[hov].base.toFixed(1)}</Dim></div></div>}
      <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
        <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><i style={{ width: 14, height: 2, background: pal.text }} /><Dim size="xs" mono>Your minutes</Dim></span>
        <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><i style={{ width: 14, borderTop: `2px dashed ${pal.textTertiary}` }} /><Dim size="xs" mono>Projection</Dim></span>
      </div>
    </div>
  );
}

// Slider + number box that edit locally while dragging and commit once, so the page recomputes once per edit
// (and the "Recent changes" log gets one line, not one per pixel).
function MinCtl({ r, onSetMin, onOut }) {
  const pal = usePal(THEME);
  const [v, setV] = useState(r.min); const t = useRef(0);
  useEffect(() => { setV(r.min); }, [r.min, r.id]);
  const commit = val => { clearTimeout(t.current); t.current = setTimeout(() => onSetMin(r.id, val), 220); };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 270 }}>
      <Chip theme={THEME} selected={r.out} onToggle={() => onOut(r.id)}>OUT</Chip>
      <div style={{ flex: 1, minWidth: 100 }}><Slider theme={THEME} min={0} max={48} value={Math.round(v)} onChange={val => { setV(val); commit(val); }} aria-label={`${r.name} minutes`} /></div>
      <input type="number" min="0" max="48" step="0.5" value={Number(v).toFixed(1)} aria-label={`${r.name} minutes`}
        onChange={e => setV(+e.target.value)} onBlur={e => onSetMin(r.id, +e.target.value)} onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); }}
        style={{ width: 58, background: pal.bgInput, color: pal.text, border: `1px solid ${pal.borderInput}`, borderRadius: tokens.radius.sm, padding: '5px 6px', fontFamily: tokens.font.mono, ...tokens.type.sm, textAlign: 'right' }} />
    </div>
  );
}

const STAT_KEYS = ['pts', 'reb', 'ast', '3pm', 'pra'];
function LabView(p) {
  const pal = usePal(THEME); const w = useWidth(); const narrow = w < 900;
  const row = r => [
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10, opacity: r.out ? .55 : 1 }}>
      <Av ini={r.ini} />
      <span><Text size="sm" weight="medium">{r.name}</Text>{r.badges.map((b, i) => <React.Fragment key={i}> <Badge variant={b.bad ? 'danger' : b.warn ? 'warning' : b.solid ? 'accent' : 'default'} style={{ textTransform: 'none', letterSpacing: 0 }}>{b.t}</Badge></React.Fragment>)}<div><Dim size="xs">{r.meta}</Dim></div></span>
    </span>,
    <MinCtl r={r} onSetMin={p.onSetMin} onOut={p.onOut} />,
    ...STAT_KEYS.map(k => { const s = r.stats[k]; return <div style={{ lineHeight: 1.25 }}><Tone weight={k === 'pra' ? 'semibold' : undefined}>{s.v.toFixed(1)}</Tone>{Math.abs(s.d) >= .05 && <> <Tone tone={s.d > 0 ? 'pos' : 'neg'} size="xs">{s.d > 0 ? '+' : ''}{s.d.toFixed(1)}</Tone></>}{s.lo != null && <div><Dim size="xs" mono>{s.lo}–{s.hi}</Dim></div>}</div>; }),
    <Tone>{r.sb.toFixed(1)}</Tone>,
  ];
  const cols = ['Player', 'Minutes', 'PTS', 'REB', 'AST', '3PM', 'PRA', 'STL+BLK'];
  const act = p.rows.slice(0, p.nAct), rest = p.rows.slice(p.nAct);
  return (
    <Stack gap={16}>
      <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr 1fr' : 'repeat(4,minmax(0,1fr))', gap: 16 }}>{p.kpis.map(k => <Kpi key={k.label} k={k} />)}</div>
      <Card padding={20}>
        <Text size="lg" weight="semibold">Minutes by player</Text>
        <div style={{ marginBottom: 8 }}><Dim>Your minutes against the season-start projection, top 15 by minutes</Dim></div>
        <MinutesChart pts={p.chart} />
      </Card>
      <Card padding={0} style={{ overflow: 'hidden' }}>
        <div style={{ padding: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div><Text size="lg" weight="semibold">Rotation</Text><div><Dim>Change a player's minutes and every stat moves with them</Dim></div></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <SwitchToggle theme={THEME} checked={p.bal} onChange={p.onBal} label="Move freed minutes to teammates" />
            <Button theme={THEME} size="sm" variant="secondary" onClick={p.onReset}>Reset team</Button>
            <Button theme={THEME} size="sm" onClick={p.onFit}>Fit to 240</Button>
          </div>
        </div>
        <div style={{ overflowX: 'auto' }}><div style={{ minWidth: 940 }}><Table theme={THEME} columns={cols} rows={act.map(row)} /></div></div>
        {rest.length > 0 && <>
          <div style={{ padding: '12px 20px' }}><Dim>Beyond the 13-man rotation · give minutes to include</Dim></div>
          <div style={{ overflowX: 'auto' }}><div style={{ minWidth: 940 }}><Table theme={THEME} columns={cols} rows={rest.map(row)} /></div></div>
        </>}
      </Card>
      <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr' : '1fr 1fr', gap: 16 }}>
        <Card padding={20}>
          <Text size="lg" weight="semibold">Biggest movers</Text><div style={{ marginBottom: 10 }}><Dim>Largest change in points + rebounds + assists from your edits</Dim></div>
          {p.movers.length ? <div style={{ display: 'grid', gap: 12 }}>{p.movers.map(m => (
            <div key={m.name}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><Text size="sm" weight="semibold">{m.name}</Text><Badge variant={m.d > 0 ? 'success' : 'danger'}>{m.d > 0 ? '+' : ''}{m.d.toFixed(1)} PRA</Badge></div>
              <Dim size="xs">{m.line}</Dim>
              <div style={{ position: 'relative', height: 6, borderRadius: 3, background: pal.bgMuted, margin: '6px 0 2px' }}><i style={{ position: 'absolute', inset: '0 auto 0 0', width: `${Math.min(100, m.min / 48 * 100)}%`, background: m.d > 0 ? pal.success : pal.danger, borderRadius: 3 }} /><u style={{ position: 'absolute', top: -2, bottom: -2, width: 2, left: `${m.base / 48 * 100}%`, background: pal.text }} /></div>
              <Dim size="xs" mono>{m.min.toFixed(1)} / {m.base.toFixed(1)}</Dim>
            </div>))}</div> : <Dim size="base">No changes yet. Mark a player OUT or move a slider and the players who gain or lose the most show up here.</Dim>}
        </Card>
        <Card padding={20}>
          <Text size="lg" weight="semibold">Recent changes</Text><div style={{ marginBottom: 10 }}><Dim>What you changed on this team, newest first</Dim></div>
          {p.log.length ? <div style={{ display: 'grid', gap: 10 }}>{p.log.map((e, i) => (
            <div key={i} style={{ display: 'flex', gap: 10 }}><Av ini={e.ini} size={28} /><div><Text size="sm"><b>{e.who}</b> <span style={{ color: pal.textSecondary }}>{e.text}</span></Text><div><Dim size="xs">{e.ago}</Dim></div></div></div>))}</div>
            : <Dim size="base">Nothing changed on the {p.teamName} yet.</Dim>}
        </Card>
      </div>
    </Stack>
  );
}

// ───────────────────────── Player Props ─────────────────────────
// Raw HTML the page still builds itself (deep sections with their own buttons and forms). The page's delegated
// click/change handlers on #pv-detail keep working on it.
const Html = ({ html, className, style }) => <div className={className} style={style} dangerouslySetInnerHTML={{ __html: html }} />;

function PropsTools(p) {
  const pal = usePal(THEME);
  const [q, setQ] = useState(p.q); const t = useRef(0);
  useEffect(() => { setQ(p.q); }, [p.q]);
  const statLabel = Object.fromEntries(p.stats.map(x => [x.l, x.s])); const labelOf = Object.fromEntries(p.stats.map(x => [x.s, x.l]));
  const sorts = [{ value: 'trust', label: 'Sort: bets you can trust' }, { value: 'edge', label: 'Sort: biggest edge' }, { value: 'name', label: 'Sort: player' }];
  return (
    <Card padding={18}>
      <Stack gap={14}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          {p.presets.map(x => <Chip key={x.k} theme={THEME} selected={p.preset === x.k} onToggle={() => p.onPreset(x.k)}>{x.l} {x.n}</Chip>)}
          <span style={{ marginLeft: 'auto' }}><span id="pv-bell" aria-expanded={p.bellOpen}><Button theme={THEME} size="sm" variant={p.bellOpen ? 'primary' : 'secondary'} onClick={p.onBell}>Alerts{p.alerts ? ` ${p.alerts}` : ''}</Button></span></span>
        </div>
        <Divider theme={THEME} spacing={0} />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <div style={{ maxWidth: '100%', overflowX: 'auto' }}><SegmentedControl theme={THEME} options={p.stats.map(x => x.l)} value={labelOf[p.stat]} onChange={l => p.onStat(statLabel[l])} /></div>
          <span style={{ flex: 1 }} />
          {p.games.length > 0 && <div style={{ minWidth: 200 }}><Select theme={THEME} value={p.game} onChange={p.onGame} options={[{ value: 'all', label: 'All games' }, ...p.games.map(g => ({ value: g.id, label: g.label }))]} /></div>}
          <div style={{ minWidth: 220 }}><Select theme={THEME} value={p.sort} onChange={p.onSort} options={sorts} /></div>
        </div>
        <div style={{ maxWidth: 280 }}><SearchInput theme={THEME} value={q} placeholder="Find a player" shortcut="" onChange={v => { setQ(v); clearTimeout(t.current); t.current = setTimeout(() => p.onQ(v), 160); }} /></div>
      </Stack>
    </Card>
  );
}

function PropsList(p) {
  const pal = usePal(THEME);
  if (!p.items.length) return <Card padding={0}><div style={{ padding: 24 }}><Dim size="base">{p.empty}</Dim></div></Card>;
  return (
    <Card padding={0} style={{ overflow: 'hidden' }}>
      {p.items.map((r, i) => {
        const on = r.key === p.sel;
        return (
          <button key={r.key} type="button" aria-current={on} onClick={() => p.onSelect(r.key)} style={{ all: 'unset', boxSizing: 'border-box', width: '100%', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14, padding: '13px 18px', borderBottom: i < p.items.length - 1 ? `1px solid ${pal.borderSubtle}` : 'none', background: on ? pal.bgSubtle : 'transparent', transition: `background ${motion.normal} ${motion.easeInOut}` }}>
            <Av ini={r.ini} size={36} />
            <span style={{ flex: 1, minWidth: 0 }}><Text size="md" weight="semibold">{r.name}</Text><div><Dim>{r.stat} · proj {r.proj}{r.where ? ' · ' + r.where : ''}</Dim></div></span>
            <span style={{ textAlign: 'right', display: 'grid', gap: 3, justifyItems: 'end' }}>
              <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                {r.watch && <span title="Watching" style={{ color: pal.warning }}>★</span>}{r.logged && <Badge>Logged</Badge>}
                <Badge variant={r.verdict === 'bet' ? 'success' : r.verdict === 'lean' ? 'warning' : 'default'}>{r.verdict}</Badge>
              </span>
              {r.edge ? <Tone tone="pos" weight="medium">{r.edge}</Tone> : <Dim size="xs">no edge</Dim>}
              {r.shp && <Dim size="xs"><span style={{ color: r.shp.strong ? (r.shp.t === 'with' ? pal.success : pal.danger) : undefined }}>⚡ {r.shp.t}</span></Dim>}
            </span>
          </button>
        );
      })}
    </Card>
  );
}

function PvDetail(p) {
  const pal = usePal(THEME);
  const h = p.head, v = p.verdict;
  const vc = v.kind === 'bet' ? { b: pal.success, bg: pal.successBg } : v.kind === 'lean' ? { b: pal.warning, bg: pal.warningBg } : { b: pal.borderSubtle, bg: 'transparent' };
  return (
    <Stack gap={16}>
      <Card padding={24}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ minWidth: 0 }}>
            <Heading level={2} style={{ margin: 0 }}>{h.name}</Heading>
            <div style={{ margin: '4px 0 0', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <Dim size="base">{h.stat}</Dim>{h.game && <Dim size="base">{h.game}</Dim>}
              {h.badges.map((b, i) => <Badge key={i} variant={b.warn ? 'warning' : 'default'} style={{ textTransform: 'none', letterSpacing: 0 }}>{b.t}</Badge>)}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}><Dim>Tonight's projection</Dim><div><Text size="display" weight="bold" style={{ fontVariantNumeric: 'tabular-nums' }}>{h.proj}</Text></div>{h.range && <Dim>{h.range}</Dim>}</div>
        </div>
        <Html html={p.minsHtml} className="hk-html" style={{ marginTop: 14 }} />
        <Html html={p.watchHtml} className="hk-html" style={{ marginTop: 12 }} />
      </Card>
      <div style={{ border: `1px solid ${vc.b}${v.kind === 'pass' ? '' : '66'}`, background: vc.bg, borderRadius: tokens.radius.md, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
          <Badge variant={v.kind === 'bet' ? 'success' : v.kind === 'lean' ? 'warning' : 'default'}>{v.kind}</Badge>
          <Text size="lg" weight="semibold">{v.title}</Text>
          {v.pill && <Badge variant={v.pill.cls === 'ok' ? 'success' : v.pill.cls === 'warn' ? 'warning' : 'default'} style={{ textTransform: 'none', letterSpacing: 0 }}>{v.pill.t}</Badge>}
        </div>
        <Html html={v.html} className="hk-html" />
      </div>
      {p.sections.map((s, i) => s.raw ? <Html key={i} html={s.raw} className="hk-raw" />
        : <Card key={i} padding={24}><Text size="lg" weight="semibold">{s.title}</Text><div style={{ margin: '4px 0 14px' }}><Dim size="base" style={{ lineHeight: 1.55 }}>{s.sub}</Dim></div><Html html={s.html} className="hk-html" /></Card>)}
    </Stack>
  );
}

export const views = { Sidebar, LabView, PropsTools, PropsList, PvDetail };
