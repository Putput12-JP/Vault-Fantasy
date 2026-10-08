// Halaska UI views for the Vault NBA app (nba/ui/projections.template.html).
// The page keeps all its logic (projection, rebalancing, pricing, storage) in plain JS and
// hands these views PLAIN DATA plus callbacks; the views only draw. Bundled to dist.js by
// build.mjs and inlined into projections.html by scripts/render_app.py (so CI needs no npm).
import React, { useState, useEffect, useRef } from 'react';
import {
  usePal, tokens, motion, Card, Badge, Text, Heading, Stack, Table, Button, Chip, SwitchToggle, Slider, Divider,
  SegmentedControl, Select, SearchInput, EmptyState,
} from '../../../src/halaska-kit.jsx';

let THEME = 'dark';
export const setThemeName = n => { THEME = n; };
const Dim = ({ children, size = 'sm', mono, style }) => { const pal = usePal(THEME); return <Text size={size} mono={mono} color={pal.textSecondary} style={style}>{children}</Text>; };
const Mono = ({ children, style }) => { const pal = usePal(THEME); return <span style={{ fontFamily: tokens.font.mono, ...tokens.type.xs, letterSpacing: '0.1em', textTransform: 'uppercase', color: pal.textTertiary, ...style }}>{children}</span>; };
const Tone = ({ children, tone, size = 'sm', weight, mono }) => { const pal = usePal(THEME); return <Text size={size} weight={weight} mono={mono} color={tone === 'pos' ? pal.success : tone === 'neg' ? pal.danger : undefined} style={{ fontVariantNumeric: 'tabular-nums' }}>{children}</Text>; };
// Initials circle; with `src` (page phSrc: an embedded headshot, or ESPN's image URL on the website) the photo covers it, cropped to the
// face. A photo that fails to load (the published artifact blocks external images) is dropped and the initials show.
const Av = ({ ini, size = 32, src }) => { const pal = usePal(THEME); const [bad, setBad] = useState(false);
  return <span style={{ position: 'relative', overflow: 'hidden', width: size, height: size, borderRadius: '50%', background: pal.bgMuted, color: pal.textSecondary, ...tokens.type.xs, fontWeight: tokens.weight.medium, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>{ini}
    {src && !bad && <img src={src} alt="" loading="lazy" onError={() => setBad(true)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 0', transform: 'scale(1.3)', transformOrigin: '50% 10%', background: pal.bgMuted }} />}</span>; };
// A player cutout with no chip behind it: the photo is a transparent bust that stands on the bottom edge of its row. Falls back to initials
// when no photo loads. `big` is a sharper image tried first (the website; the published artifact blocks it and the embedded one is used).
const Cut = ({ ini, src, big, h = 52, w, bleed = 0, fit }) => { const pal = usePal(THEME); const [st, setSt] = useState(big ? 'big' : 'ok'); const [ok, setOk] = useState(false);
  const url = st === 'big' ? big : st === 'ok' ? src : null;
  // ESPN frames every photo a little differently: scale so each head starts 8% below the top of the frame, and centre the figure
  const bw = w || Math.round(h * 1.1), sc = fit ? Math.max(.9, Math.min(1.15, .92 / (1 - fit[0]))) : 1, ih = h * sc, iw = ih * 1.3714, left = bw / 2 - (fit ? fit[1] : .5) * iw;
  return <span style={{ position: 'relative', flex: 'none', display: 'inline-block', overflow: 'hidden', width: bw, height: h, alignSelf: 'flex-end', marginBottom: -bleed }}>
    {!ok && <span style={{ position: 'absolute', left: '50%', bottom: Math.round(h * .12), transform: 'translateX(-50%)', width: Math.round(h * .62), height: Math.round(h * .62), borderRadius: '50%', background: pal.bgMuted, color: pal.textSecondary, ...tokens.type.xs, display: 'grid', placeItems: 'center' }}>{ini}</span>}
    {url && <img src={url} alt="" loading="lazy" onLoad={() => setOk(true)} onError={() => setSt(st === 'big' ? 'ok' : 'bad')} style={{ position: 'absolute', left: Math.round(left), bottom: 0, height: Math.round(ih), width: Math.round(iw), maxWidth: 'none' }} />}
  </span>; };
const useWidth = () => { const [w, setW] = useState(window.innerWidth); useEffect(() => { const f = () => setW(window.innerWidth); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f); }, []); return w; };
const Ico = ({ html, size = 16 }) => <span aria-hidden="true" style={{ display: 'inline-flex', width: size, height: size }} dangerouslySetInnerHTML={{ __html: html.replace('<svg ', `<svg width="${size}" height="${size}" `) }} />;

// ───────────────────────── sidebar ─────────────────────────
export function Sidebar({ pages, view, season, pvCount, onGo, collapsed, onToggle, brand, onBrand }) {
  const pal = usePal(THEME);
  // Classes (sb-*) carry the collapsed-rail and active-card styling in the page's stylesheet; the rail shows icons only, with a tooltip.
  const chev = <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ transform: collapsed ? 'rotate(180deg)' : 'none' }}><path d="m11 17-5-5 5-5M18 17l-5-5 5-5" /></svg>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, minHeight: '100%' }}>
      <div className="sb-head" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 8px' }}>
        <button type="button" onClick={onBrand} aria-label="Open your profile" title={brand ? brand.name + ' (your profile)' : 'Your profile'} style={{ all: 'unset', cursor: 'pointer', display: 'inline-flex', flex: 'none' }}>
          {brand && brand.logo ? <img src={brand.logo} alt="" width="36" height="36" style={{ display: 'block', objectFit: 'contain' }} />
            : <span style={{ width: 36, height: 36, borderRadius: tokens.radius.sm, background: pal.text, color: pal.bg, ...tokens.type.xs, fontWeight: tokens.weight.bold, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>NBA</span>}
        </button>
        <div className="sb-brandtxt" style={{ minWidth: 0, flex: 1 }}><Text size="md" weight="semibold">Vault NBA</Text></div>
        <button type="button" className="sb-tog" onClick={onToggle} aria-label={collapsed ? 'Expand the sidebar' : 'Collapse the sidebar'} aria-expanded={!collapsed} data-tip={collapsed ? 'Expand' : 'Collapse'} title="Collapse or expand ( [ )">{chev}</button>
      </div>
      <nav aria-label="Pages">
        {pages.map(([sec, items]) => (
          <div key={sec} className="sb-sec" style={{ marginBottom: 10 }}>
            <div className="sb-secl" style={{ padding: '8px 10px 6px' }}><Mono>{sec}</Mono></div>
            {items.map(([name, icon, what, live]) => {
              if (!live) return <div key={name} title={what} aria-disabled="true" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 10px', opacity: .5, ...tokens.type.base, color: pal.textTertiary }}><Ico html={icon} />{name}<Badge style={{ marginLeft: 'auto' }}>Soon</Badge></div>;
              const on = view === live;
              return (
                <a key={live} href={'#' + live} className="sb-a" data-tip={name} title={collapsed ? undefined : what} aria-current={on ? 'page' : undefined} aria-label={collapsed ? name : undefined} onClick={e => { e.preventDefault(); onGo(live); }}
                  style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 10px', borderRadius: tokens.radius.sm, textDecoration: 'none', ...tokens.type.base, color: on ? pal.text : pal.textSecondary, fontWeight: on ? tokens.weight.medium : tokens.weight.regular, transition: `background ${motion.fast || '120ms'} ease, color ${motion.fast || '120ms'} ease` }}>
                  <span style={{ display: 'inline-flex', color: on ? pal.text : pal.textTertiary, flex: 'none' }}><Ico html={icon} /></span><span className="sb-l">{name}</span>
                  {live === 'props' && pvCount ? <><span className="sb-l" style={{ marginLeft: 'auto' }}><Badge variant="accent">{pvCount}</Badge></span><i className="sb-dot" aria-hidden="true" /></> : null}
                </a>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="sb-foot" style={{ marginTop: 'auto', border: `1px solid ${pal.borderSubtle}`, borderRadius: tokens.radius.md, padding: 12 }}>
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


const STAT_KEYS = ['pts', 'reb', 'ast', '3pm', 'pra'];
const STAT_LAB = { pts: 'PTS', reb: 'REB', ast: 'AST', '3pm': '3PM', pra: 'PRA' };
const fm = x => (Math.round(x * 10) / 10).toFixed(1);

// Shared by the starter cards and bench rows: edits locally while typing/stepping, commits once (debounced) so the page recomputes once per edit.
function useMin(r, onSetMin) {
  const [v, setV] = useState(r.min); const t = useRef(0);
  useEffect(() => { setV(r.min); }, [r.min, r.id]);
  const set = val => { val = Math.max(0, Math.min(48, Math.round(+val * 2) / 2)); if (isNaN(val)) return; setV(val); clearTimeout(t.current); t.current = setTimeout(() => onSetMin(r.id, val), 220); };
  return [v, setV, set];
}
const Stepper = ({ r, v, setV, set, big }) => (
  <div className={'ml-row' + (big ? ' ml-rowbig' : '')}>
    <button type="button" className="ml-step" onClick={() => set(v - 1)} aria-label={`${r.name}: one minute less`} disabled={v <= 0}>−</button>
    <input type="number" min="0" max="48" step="0.5" className={big ? 'ml-num big' : 'ml-num'} value={fm(v)} aria-label={`${r.name} minutes`} onChange={e => setV(+e.target.value)} onBlur={e => set(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); }} />
    <button type="button" className="ml-step" onClick={() => set(v + 1)} aria-label={`${r.name}: one minute more`} disabled={v >= 48}>+</button>
  </div>
);
// Counting stats. PRA is the headline with a bar showing how it splits into points, rebounds and assists; the three parts sit under it
// in their bar colours, and the small stats (3PM, STL, BLK) sit below. Only PRA carries the change against the projection, so the block stays quiet. Bench rows lay the same pieces out on one line.
const Dlt = ({ d }) => Math.abs(d) < .05 ? null : <i className={'ml-d ' + (d > 0 ? 'pos' : 'neg')}>{d > 0 ? '▲' : '▼'}{fm(Math.abs(d))}</i>;
const StatGrid = ({ r, row }) => { const S = r.stats, pra = Math.max(.01, S.pts.v + S.reb.v + S.ast.v);
  const part = (k, l) => <div className={'ml-p ' + k}><small><u />{l}</small><b>{fm(S[k].v)}</b></div>;
  const chip = (k, l) => <span className="ml-c" key={k} title={S[k].lo != null ? `Typical range ${S[k].lo} to ${S[k].hi}` : undefined}>{l}<b>{fm(S[k].v)}</b></span>;
  return (
    <div className={'ml-sg' + (row ? ' row' : '')}>
      <div className="ml-pra"><div className="ml-prah"><small>PRA</small><b>{fm(S.pra.v)}</b><Dlt d={S.pra.d} /></div>
        <div className="ml-split" aria-hidden="true"><i className="pts" style={{ flex: S.pts.v / pra }} /><i className="reb" style={{ flex: S.reb.v / pra }} /><i className="ast" style={{ flex: S.ast.v / pra }} /></div></div>
      <div className="ml-parts">{part('pts', 'PTS')}{part('reb', 'REB')}{part('ast', 'AST')}</div>
      <div className="ml-chips">{chip('3pm', '3PM')}{chip('stl', 'STL')}{chip('blk', 'BLK')}</div>
    </div>
  ); };

// The five projected starters: big cards, like a lineup card.
function StarterCard({ r, onSetMin, onOut, onProps }) {
  const [v, setV, set] = useMin(r, onSetMin); const d = v - r.base, changed = Math.abs(d) >= .05;
  return (
    <article className={'ml-sc' + (changed ? ' ml-ed' : '') + (r.out ? ' ml-out' : '')}>
      <span className="ml-pos">{r.pos}</span>
      <button type="button" className="ml-pb" onClick={() => onProps(r.name)} title={`See ${r.name}'s prop lines`}>Props<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg></button>
      <div className="ml-ph"><Cut ini={r.ini} src={r.src} fit={r.fit} h={78} w={92} /></div>
      <b className="ml-nm">{r.name}</b>
      {r.badges.length > 0 && <span className="ml-bdg c">{r.badges.slice(0, 2).map((b, i) => <Badge key={i} variant={b.bad ? 'danger' : b.warn ? 'warning' : b.solid ? 'accent' : 'default'} style={{ textTransform: 'none', letterSpacing: 0 }}>{b.t}</Badge>)}</span>}
      <Stepper r={r} v={v} setV={setV} set={set} big />
      <input type="range" className="ml-range" min="0" max="48" step="0.5" value={v} style={{ '--p': (v / 48 * 100) + '%' }} aria-label={`${r.name} minutes`} onChange={e => set(e.target.value)} />
      <div className="ml-q">{[[12, 'Bench'], [22, 'Role'], [30, 'Starter'], [36, 'Star']].map(([m, l]) => <button key={m} type="button" className={Math.abs(v - m) < .01 ? 'on' : ''} onClick={() => set(m)}>{m}<small>{l}</small></button>)}</div>
      <StatGrid r={r} />
      <div className="ml-ft">
        <span>{changed ? <><b className={d > 0 ? 'pos' : 'neg'}>{d > 0 ? '+' : ''}{fm(d)} min</b> <button type="button" className="ml-reset" onClick={() => set(r.base)}>Reset</button></> : <span className="ml-same">Projection {fm(r.base)}</span>}</span>
        <button type="button" className={'ml-outb' + (r.out ? ' on' : '')} aria-pressed={r.out} onClick={() => onOut(r.id)} title={r.out ? 'Put him back in the rotation' : 'Mark him out: his minutes go to teammates'}>{r.out ? 'OUT' : 'Mark out'}</button>
      </div>
    </article>
  );
}

// Everyone after the starters: one slim row each.
function BenchRow({ r, onSetMin, onOut, onProps }) {
  const [v, setV, set] = useMin(r, onSetMin); const d = v - r.base, changed = Math.abs(d) >= .05;
  return (
    <div className={'ml-br' + (changed ? ' ml-ed' : '') + (r.out ? ' ml-out' : '')}>
      <Cut ini={r.ini} src={r.src} fit={r.fit} h={46} w={54} />
      <div className="ml-bi"><b>{r.name}</b>{r.badges.slice(0, 1).map((b, i) => <Badge key={i} variant={b.bad ? 'danger' : b.warn ? 'warning' : b.solid ? 'accent' : 'default'} style={{ textTransform: 'none', letterSpacing: 0, marginLeft: 6 }}>{b.t}</Badge>)}</div>
      <span className="ml-bd">{changed ? <><b className={d > 0 ? 'pos' : 'neg'}>{d > 0 ? '+' : ''}{fm(d)}</b> <button type="button" className="ml-reset" onClick={() => set(r.base)}>Reset</button></> : null}</span>
      <button type="button" className="ml-pb" onClick={() => onProps(r.name)} title={`See ${r.name}'s prop lines`}>Props<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg></button>
      <button type="button" className={'ml-outb' + (r.out ? ' on' : '')} aria-pressed={r.out} onClick={() => onOut(r.id)} title="Mark him out">{r.out ? 'OUT' : 'Out'}</button>
      <Stepper r={r} v={v} setV={setV} set={set} />
      <StatGrid r={r} row />
    </div>
  );
}

// The 240-minute budget as one bar: a segment per player, a marker at 240. Over or under 240 is visible at a glance.
function Budget({ rows, total, onFit, note }) {
  const live = rows.filter(r => r.min > 0), span = Math.max(240, total), mk = 240 / span * 100, diff = total - 240;
  const ok = Math.abs(diff) < .5;
  return (
    <div className="ml-bud">
      <div className="ml-budh">
        <div><b className="ml-bn">{fm(total)}</b><span className="ml-bo"> of 240 minutes</span></div>
        <span className={'ml-bs ' + (ok ? 'ok' : diff > 0 ? 'hi' : 'lo')}>{ok ? 'Balanced' : diff > 0 ? `${fm(diff)} over 240` : `${fm(-diff)} left to hand out`}</span>
      </div>
      <div className="ml-bar" role="img" aria-label={`${fm(total)} of 240 minutes assigned`}>
        {live.map((r, i) => { const w = r.min / span * 100; return <i key={r.id} title={`${r.name} ${fm(r.min)}`} style={{ width: w + '%', '--a': Math.max(.28, 1 - i * .075) }}>{w >= 13 ? <span>{r.last}</span> : null}</i>; })}
        <u style={{ left: mk + '%' }} aria-hidden="true"><em>240</em></u>
      </div>
      {!ok && <button type="button" className="ml-fit" onClick={onFit}>{diff > 0 ? 'Trim to 240' : 'Fill to 240'}</button>}
      {note && diff > 5 && <p className="ml-bnote">{note}</p>}
    </div>
  );
}

function LabView(p) {
  const pal = usePal(THEME); const w = useWidth(); const narrow = w < 900;
  const [more, setMore] = useState(false);
  const L = p.lineup, byId = new Map(p.rows.map(r => [r.id, r]));
  const starters = (L ? L.ids.map(id => byId.get(id)).filter(Boolean) : p.rows.slice(0, Math.min(5, p.nAct))).sort((a, b) => b.base - a.base || b.min - a.min);
  const sid = new Set(starters.map(r => r.id));
  const act = p.rows.slice(0, p.nAct).filter(r => !sid.has(r.id)), rest = p.rows.slice(p.nAct).filter(r => !sid.has(r.id));
  const total = p.rows.reduce((a, r) => a + r.min, 0);
  const K = Object.fromEntries(p.kpis.map(k => [k.label, k]));
  const pts = K['Team points per 240 min'], top = K['Top scorer'], chg = K['Players changed'];
  return (
    <Stack gap={16}>
      <section className="ml-hero" style={{ '--ml-c': p.wash || 'var(--accent2, #7fb4ec)' }}>
        <div className="ml-hh">
          <div><h2>{p.teamName} rotation</h2><p>Set each player's minutes. Every stat, and every prop price, moves with them.</p></div>
          <div className="ml-act">
            <SwitchToggle theme={THEME} checked={p.bal} onChange={p.onBal} label="Hand freed minutes to teammates" />
            <Button theme={THEME} size="sm" variant="secondary" onClick={p.onReset}>Reset team</Button>
          </div>
        </div>
        {p.mode && <div className="ml-mode">
          <div className="seg" role="group" aria-label="Which minutes to start from">
            <button type="button" aria-pressed={p.mode === 'tonight'} onClick={() => p.onMode('tonight')}>Tonight's game</button>
            <button type="button" aria-pressed={p.mode === 'season'} onClick={() => p.onMode('season')}>Season start</button>
          </div>
          <span className="ml-modet">{p.mode === 'tonight' ? <>Game-day minutes for <b>{p.tonightLabel}</b>: injuries, lineup, rest and blowout risk applied.</> : p.mode === 'season' ? <>The usual season-start projection, with no game-day news.</> : <>Your edits. Pick a button to start over from it.</>}</span>
        </div>}
        <Budget rows={p.rows} total={total} onFit={p.onFit} note={p.mode === 'tonight' ? "The model's expected minutes add up to more than 240 because every player who might play is counted. Trim to 240 for one game's worth." : ''} />
        <div className="ml-kp">
          <div><small>Team points per 240</small><b>{pts.val}</b>{pts.delta != null && Math.abs(pts.delta) >= .05 ? <i className={pts.delta > 0 ? 'pos' : 'neg'}>{pts.delta > 0 ? '+' : ''}{pts.delta.toFixed(1)}</i> : <i>vs projection: same</i>}</div>
          <div><small>Top scorer</small><b>{top.val}</b><i>{top.hint}</i></div>
          <div><small>Players changed</small><b>{chg.val}</b><i>{chg.hint}</i></div>
        </div>
      </section>
      <div className={'ml-lu ' + (L ? (L.confirmed ? 'conf' : 'exp') : '')}><i className="dot" /><span>{L ? <><b>{L.confirmed ? 'Confirmed starters' : 'Expected starters'}</b> for {L.label}{!L.confirmed && L.listed < 5 ? ` · NBA.com has named ${L.listed} so far, the rest are projected` : ''}</> : <><b>Starters</b> from the season-start projection. Tonight's lineup replaces them once NBA.com posts it.</>}</span></div>
      <div className="ml-starters">{starters.map(r => <StarterCard key={r.id} r={r} onSetMin={p.onSetMin} onOut={p.onOut} onProps={p.onProps} />)}</div>
      {act.length > 0 && <><Mono>Bench</Mono><div className="ml-bench">{[...act].sort((a, b) => b.min - a.min || b.base - a.base).map(r => <BenchRow key={r.id} r={r} onSetMin={p.onSetMin} onOut={p.onOut} onProps={p.onProps} />)}</div></>}
      {rest.length > 0 && <>
        <button type="button" className="ml-more" aria-expanded={more} onClick={() => setMore(!more)}>{more ? 'Hide' : 'Show'} {rest.length} players outside the rotation<span>give a player minutes to bring him in</span></button>
        {more && <div className="ml-bench">{[...rest].sort((a, b) => b.min - a.min || b.base - a.base).map(r => <BenchRow key={r.id} r={r} onSetMin={p.onSetMin} onOut={p.onOut} onProps={p.onProps} />)}</div>}
      </>}
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
          <Text size="lg" weight="semibold">Recent changes</Text><div style={{ marginBottom: 12 }}><Dim>Roster moves since last season, then what you changed on this team, newest first</Dim></div>
          <Stack gap={14}>
            <div>
              <Mono>Roster moves</Mono>
              {p.roster.arrived.length + p.roster.left.length ? <div style={{ display: 'grid', gap: 10, marginTop: 8 }}>
                {p.roster.arrived.map(r => <div key={'a' + r.name} style={{ display: 'flex', gap: 10, alignItems: 'center' }}><Av ini={r.ini} src={r.src} size={28} /><div style={{ flex: 1, minWidth: 0 }}><Text size="sm" weight="medium">{r.name}</Text><div><Dim size="xs">Joined from {r.team}{r.mpg ? ` · ${r.mpg} mpg last season` : ''}</Dim></div></div><Badge variant="success">In</Badge></div>)}
                {p.roster.left.map(r => <div key={'l' + r.name} style={{ display: 'flex', gap: 10, alignItems: 'center' }}><Av ini={r.ini} src={r.src} size={28} /><div style={{ flex: 1, minWidth: 0 }}><Text size="sm" weight="medium">{r.name}</Text><div><Dim size="xs">Left for {r.team}{r.mpg ? ` · ${r.mpg} mpg last season` : ''}</Dim></div></div><Badge variant="danger">Out</Badge></div>)}
              </div> : <div style={{ marginTop: 6 }}><Dim size="base">No roster moves on file for the {p.teamName}.</Dim></div>}
            </div>
            <Divider theme={THEME} spacing={0} />
            <div>
              <Mono>Your edits</Mono>
              {p.log.length ? <div style={{ display: 'grid', gap: 10, marginTop: 8 }}>{p.log.map((e, i) => (
                <div key={i} style={{ display: 'flex', gap: 10 }}><Av ini={e.ini} size={28} /><div><Text size="sm"><b>{e.who}</b> <span style={{ color: pal.textSecondary }}>{e.text}</span></Text><div><Dim size="xs">{e.ago}</Dim></div></div></div>))}</div>
                : <div style={{ marginTop: 6 }}><Dim size="base">Nothing changed on the {p.teamName} yet.</Dim></div>}
            </div>
          </Stack>
        </Card>
      </div>
      <Card padding={20}>
        <Text size="lg" weight="semibold">Minutes by player</Text>
        <div style={{ marginBottom: 8 }}><Dim>Your minutes against the season-start projection, top 15 by minutes</Dim></div>
        <Html html={p.chartHtml} />
      </Card>
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
          <div style={{ flex: '1 1 200px', maxWidth: 280, minWidth: 0 }}><SearchInput theme={THEME} value={q} placeholder="Find a player" shortcut="" onChange={v => { setQ(v); clearTimeout(t.current); t.current = setTimeout(() => p.onQ(v), 160); }} /></div>
          <div style={{ flex: '1 1 280px', minWidth: 0, overflowX: 'auto', scrollbarWidth: 'none' }}><SegmentedControl theme={THEME} options={p.stats.map(x => x.l)} value={labelOf[p.stat]} onChange={l => p.onStat(statLabel[l])} /></div>
          <div style={{ flex: '0 0 auto', minWidth: 210 }}><Select theme={THEME} value={p.sort} onChange={p.onSort} options={sorts} /></div>
        </div>
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
          <button key={r.key} type="button" aria-current={on} onClick={() => p.onSelect(r.key)} style={{ all: 'unset', boxSizing: 'border-box', width: '100%', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12, padding: '0 18px', minHeight: 66, borderBottom: i < p.items.length - 1 ? `1px solid ${pal.borderSubtle}` : 'none', background: on ? pal.bgSubtle : 'transparent', transition: `background ${motion.normal} ${motion.easeInOut}` }}>
            <Cut ini={r.ini} src={r.src} fit={r.fit} h={60} />
            <span style={{ flex: 1, minWidth: 0, padding: '10px 0' }}><Text size="md" weight="semibold">{r.name}</Text><div><Dim>{r.stat} · proj {r.proj}{r.where ? ' · ' + r.where : ''}</Dim></div></span>
            <span style={{ textAlign: 'right', display: 'grid', gap: 3, justifyItems: 'end', padding: '10px 0' }}>
              <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                {r.fav && <Badge variant="accent" style={{ textTransform: 'none', letterSpacing: 0 }}>Yours</Badge>}{r.watch && <span title="Watching" style={{ color: pal.warning }}>★</span>}{r.logged && <Badge>Logged</Badge>}
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
      <Card padding={0} style={{ overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap', padding: '0 24px', background: h.wash ? `color-mix(in srgb, ${h.wash} 20%, ${pal.bgElevated || 'transparent'})` : 'transparent', borderBottom: `1px solid ${pal.borderSubtle}` }}>
          <div style={{ minWidth: 0, display: 'flex', gap: 16, alignItems: 'flex-end' }}>
            <Cut ini={h.ini} src={h.src} big={h.big} fit={h.fit} h={100} w={136} />
            <div style={{ minWidth: 0, padding: '24px 0' }}>
              <Heading level={2} style={{ margin: 0 }}>{h.name}</Heading>
              <div style={{ margin: '4px 0 0', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <Dim size="base">{h.stat}</Dim>{h.game && <Dim size="base">{h.game}</Dim>}
                {h.badges.map((b, i) => <Badge key={i} variant={b.warn ? 'warning' : 'default'} style={{ textTransform: 'none', letterSpacing: 0 }}>{b.t}</Badge>)}
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right', padding: '24px 0' }}><Dim>Tonight's projection</Dim><div><Text size="display" weight="bold" style={{ fontVariantNumeric: 'tabular-nums' }}>{h.proj}</Text></div>{h.range && <Dim>{h.range}</Dim>}</div>
        </div>
        <div style={{ padding: '14px 24px 24px' }}>
          <Html html={p.minsHtml} className="hk-html" />
          <Html html={p.watchHtml} className="hk-html" style={{ marginTop: 12 }} />
        </div>
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
