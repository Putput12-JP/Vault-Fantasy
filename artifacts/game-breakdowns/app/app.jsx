// Vault Game Breakdowns, rebuilt on Halaska UI. Same data contract (fetch
// data.json, written by ../build_data.py) and the same wording and rules as the
// vanilla page (index.src.html, kept as the reference). Only rendering moved to
// React + kit. Run `node app/build.mjs` after editing; never hand-edit index.html.
import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ThemeProvider, AccentContext, usePal, tokens, motion,
  Card, Badge, Text, Heading, Table, Chip, Skeleton, AlertBanner, Tooltip, StatusBadge,
} from '../../../src/halaska-kit.jsx';
import CREST from './crest.txt';

// Live data comes from the branch a GitHub Action rewrites; local preview reads the sibling file.
const DATA_SRC = /^(localhost|127\.0\.0\.1)$/.test(location.hostname) ? 'data.json' : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/artifact-data/game-breakdowns/data.json';
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

// ───────────────────────── helpers (verbatim from the vanilla page) ─────────────────────────
const TEAM = { ARI: 'Cardinals', ATL: 'Falcons', BAL: 'Ravens', BUF: 'Bills', CAR: 'Panthers', CHI: 'Bears', CIN: 'Bengals', CLE: 'Browns', DAL: 'Cowboys', DEN: 'Broncos', DET: 'Lions', GB: 'Packers', HOU: 'Texans', IND: 'Colts', JAX: 'Jaguars', KC: 'Chiefs', LA: 'Rams', LAR: 'Rams', LAC: 'Chargers', LV: 'Raiders', MIA: 'Dolphins', MIN: 'Vikings', NE: 'Patriots', NO: 'Saints', NYG: 'Giants', NYJ: 'Jets', PHI: 'Eagles', PIT: 'Steelers', SEA: 'Seahawks', SF: '49ers', TB: 'Buccaneers', TEN: 'Titans', WAS: 'Commanders' };
const ET = { timeZone: 'America/New_York' };
const dayOf = t => new Date(t).toLocaleDateString('en-US', { ...ET, weekday: 'long', month: 'short', day: 'numeric' });
const timeOf = t => new Date(t).toLocaleTimeString('en-US', { ...ET, hour: 'numeric', minute: '2-digit' });
const odds = p => p == null ? '–' : (p > 0 ? '+' : '') + p;
const n1 = x => x == null ? '–' : (Math.round(x * 10) / 10).toString();
const pct = p => p == null ? '–' : Math.round(p * 100) + '%';
const lnum = x => { if (x == null) return '–'; const r = Math.round(x * 100) / 100; return (r > 0 ? '+' : '') + r; };
// spread text from the HOME spread (negative = home favored)
function sprd(g, hs, dp) { if (hs == null) return '–'; const v = dp ? Math.round(hs * 10) / 10 : hs; if (Math.abs(v) < .05) return 'Pick’em'; return v < 0 ? g.home + ' ' + v : g.away + ' −' + v; }
const MK = { spread: 'Spread', total: 'Total', ml: 'Moneyline' };
const BANDTXT = (b, mk, B) => { const x = B[mk] || [], u = mk === 'ml' ? ' win-chance pts' : ' pts'; return b === 'small' ? 'under ' + x[0] + u : b === 'mid' ? x[0] + '–' + x[1] + u : x[1] + u + ' or more'; };
const usd = n => n == null ? '–' : '$' + (n >= 1e6 ? (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M' : n >= 1000 ? Math.round(n / 1000) + 'k' : Math.round(n));
const sl = v => (v > 0 ? '+' : '') + v;
const fmtU = u => (u >= 0 ? '+' : '') + u.toFixed(1) + 'u';
let D = null;

// ───────────────────────── small UI pieces ─────────────────────────
function useWidth() {
  const [w, setW] = useState(typeof window === 'undefined' ? 1200 : window.innerWidth);
  useEffect(() => { const f = () => setW(window.innerWidth); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f); }, []);
  return w;
}
const num = { fontVariantNumeric: 'tabular-nums' };
const Dim = ({ children, size = 'sm', style }) => { const pal = usePal(THEME); return <Text size={size} color={pal.textTertiary} style={{ ...num, ...style }}>{children}</Text>; };
const Sub = ({ children }) => <div><Dim size="xs">{children}</Dim></div>;
const B = ({ children }) => { const pal = usePal(THEME); return <b style={{ color: pal.text, fontWeight: tokens.weight.semibold }}>{children}</b>; };
const Src = ({ children }) => <div style={{ marginTop: 10, lineHeight: 1.55 }}><Dim size="sm">{children}</Dim></div>;
const Empty = ({ children }) => <div style={{ padding: '6px 0' }}><Dim size="base">{children}</Dim></div>;
const Over = ({ children }) => <Text size="xs" weight="semibold" color={usePal(THEME).textTertiary} style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>{children}</Text>;

function Panel({ title, sub, children, style }) {
  return (
    <Card theme={THEME} padding={18} style={{ minWidth: 0, ...style }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '2px 10px', marginBottom: 12 }}>
        <Text size="md" weight="semibold">{title}</Text>
        {sub && <Dim size="sm">{sub}</Dim>}
      </div>
      {children}
    </Card>
  );
}
// a tinted inner row: label + value on top, detail underneath
function Row({ label, value, children, tint }) {
  const pal = usePal(THEME);
  return (
    <div style={{ background: tint || pal.bgSubtle, borderRadius: tokens.radius.sm + 2, padding: '9px 12px', minWidth: 0 }}>
      {(label || value) && <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
        <Over>{label}</Over><Text size="sm" weight="semibold" style={num}>{value}</Text>
      </div>}
      {children && <div style={{ marginTop: label || value ? 3 : 0, lineHeight: 1.5 }}><Text size="sm" secondary style={num}>{children}</Text></div>}
    </div>
  );
}
const Side = ({ children }) => <span style={{ color: ACCENT, fontWeight: 600 }}>{children}</span>;
const Muted = ({ children }) => <span style={{ color: usePal(THEME).textTertiary }}>{children}</span>;
const R = ({ children }) => <div style={{ textAlign: 'right' }}>{children}</div>;

function Dots({ g, on }) {
  const pal = usePal(THEME);
  const ring = on ? pal.bg : pal.text;
  const d = (c, t, extra) => <i key={t} title={t} style={{ width: 7, height: 7, borderRadius: '50%', display: 'inline-block', background: c, ...extra }} />;
  const o = [];
  if (g.card.length) o.push(d(pal.success, 'Vault’s Play'));
  if (g.props.some(p => p.status === 'pass')) o.push(d('#b9d2ec', 'Best Bet'));
  if (g.plays.some(p => p.on && !p.held)) o.push(d(ACCENT, 'Game Play', { boxShadow: `0 0 0 1.5px ${ring}` }));
  if (g.qb) o.push(d(pal.warning, 'Backup QB'));
  return <span style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>{o}</span>;
}

// ───────────────────────── slate (sidebar) ─────────────────────────
function GameBtn({ g, on, pick, chip }) {
  const pal = usePal(THEME);
  const s = g.lines.spread, t = g.lines.total;
  const sub = on ? 'rgba(11,20,32,.72)' : pal.textTertiary;
  return (
    <button type="button" onClick={() => pick(g.key)} aria-current={on ? 'true' : undefined} style={{
      all: 'unset', boxSizing: 'border-box', cursor: 'pointer', display: 'grid', gridTemplateColumns: '1fr auto', gap: '2px 10px', alignItems: 'center',
      width: chip ? 'auto' : '100%', minWidth: chip ? 156 : undefined, padding: '8px 10px', borderRadius: tokens.radius.sm + 2,
      background: on ? ACCENT : chip ? pal.bgElevated : 'transparent', color: on ? '#0b1420' : pal.text,
      border: chip && !on ? `1px solid ${pal.borderSubtle}` : '1px solid transparent',
      transition: `background ${motion.normal} ${motion.easeInOut}`, fontFamily: tokens.font.sans,
    }}>
      <span style={{ ...tokens.type.md, fontWeight: tokens.weight.semibold }}>{g.away} @ {g.home}</span>
      <span style={{ ...tokens.type.sm, fontFamily: tokens.font.mono, color: sub, textAlign: 'right' }}>{timeOf(g.commence)}</span>
      <span style={{ ...tokens.type.sm, fontFamily: tokens.font.mono, color: sub, ...num }}>{sprd(g, s.cons)} · {t.cons ?? '–'}</span>
      <Dots g={g} on={on} />
    </button>
  );
}
function Slate({ cur, pick, wide }) {
  const byDay = {};
  D.games.forEach(g => { (byDay[dayOf(g.commence)] = byDay[dayOf(g.commence)] || []).push(g); });
  return (
    <div style={{ display: 'flex', flexDirection: wide ? 'column' : 'row', gap: 14, overflowX: wide ? 'visible' : 'auto', paddingBottom: wide ? 0 : 6, scrollbarWidth: 'none' }}>
      {Object.entries(byDay).map(([d, gs]) => (
        <div key={d} style={{ flex: 'none' }}>
          <div style={{ padding: '0 6px 6px' }}><Over>{d}{gs[0].week !== D.week ? ' · Wk ' + gs[0].week : ''}</Over></div>
          <div style={{ display: 'flex', flexDirection: wide ? 'column' : 'row', gap: wide ? 2 : 6 }}>
            {gs.map(g => <GameBtn key={g.key} g={g} on={g.key === cur} pick={pick} chip={!wide} />)}
          </div>
        </div>
      ))}
    </div>
  );
}
function Key() {
  const pal = usePal(THEME);
  const k = (c, l, extra) => <span key={l} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><i style={{ width: 7, height: 7, borderRadius: '50%', display: 'inline-block', background: c, ...extra }} /><Dim size="sm">{l}</Dim></span>;
  return <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 12px', padding: '0 6px' }}>{[k(pal.success, 'Vault’s Play'), k('#b9d2ec', 'Best Bet'), k(ACCENT, 'Game Play', { boxShadow: `0 0 0 1.5px ${pal.text}` }), k(pal.warning, 'Backup QB')]}</div>;
}
function Brand({ small }) {
  const pal = usePal(THEME);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 6px' }}>
      <img src={CREST} alt="Vault Fantasy Football" style={{ height: small ? 30 : 36, width: 'auto' }} />
      <div style={{ lineHeight: 1.1 }}><Text size="md" weight="bold" style={{ textTransform: 'uppercase' }}>Vault <span style={{ color: pal.accent }}>Fantasy</span></Text><div><Dim size="xs" style={{ letterSpacing: '0.16em', textTransform: 'uppercase' }}>Football</Dim></div></div>
    </div>
  );
}
const stampTxt = () => 'Data as of ' + new Date(D.generated).toLocaleString('en-US', { ...ET, weekday: 'short', hour: 'numeric', minute: '2-digit' }) + ' ET. Lines and props move; check the price before you bet.';

// ───────────────────────── game page cards ─────────────────────────
function Score({ g }) {
  const pal = usePal(THEME);
  const L = g.lines, f = L.ml.fair;
  const ms = L.spread.model, mt = L.total.model, mw = L.ml.model;
  let body = <Empty>The model has no read on this game yet.</Empty>;
  if (ms != null && mt != null) {
    const vh = (mt - ms) / 2, va = (mt + ms) / 2, hf = vh >= va;
    const team = (ab, pt, fav, right) => (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, textAlign: right ? 'right' : 'left' }}>
        <Text size="sm" weight="bold" color={pal.textTertiary} style={{ letterSpacing: '0.02em' }}>{ab}</Text>
        <span style={{ fontFamily: tokens.font.sans, fontWeight: 700, fontSize: 44, lineHeight: 1, letterSpacing: '-0.03em', color: fav ? pal.text : pal.textSecondary, ...num }}>{n1(pt)}</span>
      </div>
    );
    let wp = null;
    if (mw != null) {
      const hw = Math.round(mw * 100), aw = 100 - hw;
      wp = (
        <div style={{ marginTop: 14 }}>
          <div style={{ display: 'flex', height: 8, borderRadius: 99, overflow: 'hidden', gap: 2 }}>
            <i style={{ display: 'block', width: aw + '%', background: aw > hw ? ACCENT : pal.bgHover }} />
            <i style={{ display: 'block', width: hw + '%', background: hw >= aw ? ACCENT : pal.bgHover }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
            <Dim>{g.away} <B>{aw}%</B></Dim><Dim>win chance</Dim><Dim><B>{hw}%</B> {g.home}</Dim>
          </div>
        </div>
      );
    }
    body = <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'end', gap: 8 }}>
        {team(g.away, va, !hf)}<span style={{ paddingBottom: 8 }}><Text size="xl" color={pal.textTertiary}>–</Text></span>{team(g.home, vh, hf, true)}
      </div>
      {wp}
    </>;
  }
  return (
    <Panel title="Projected score">
      {body}
      {g.score && <div style={{ marginTop: 10 }}><Text size="sm" mono color={pal.textTertiary} style={num}>Market: {g.away} {n1(g.score.away)} · {g.home} {n1(g.score.home)}{f != null ? ' · ' + (f >= .5 ? g.home + ' ' + Math.round(f * 100) : g.away + ' ' + Math.round((1 - f) * 100)) + '% to win' : ''}</Text></div>}
      {g.money && <Money g={g} />}
      <Src>Vault’s team-rating model{g.qb ? ', adjusted for the backup QB' : ''}. The market line is every sportsbook’s price with its margin removed.</Src>
    </Panel>
  );
}

// Polymarket money by market (fetch-polymarket.mjs markets{}): $ on each, the
// busiest line, and the side the last 24h of aggressor money bought. A side
// only shows past 15 trades and $2.5k net, same bar as the app's game cards.
function Money({ g }) {
  const pal = usePal(THEME);
  const M = g.money, PM = M.markets, clear = t => t && t.n >= 15 && t.net >= 2500;
  const head = (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${pal.borderSubtle}` }}>
      <Text size="sm" secondary><B>{usd(M.vol)}</B> traded on Polymarket{PM && PM.other && PM.other.vol >= 1000 ? ' · ' + usd(PM.other.vol) + ' on halves, quarters and team totals' : ''}</Text>
    </div>
  );
  if (!PM) return <>{head}{M.side && <Src>{usd(M.net)} net into {M.side} in the last 24h</Src>}</>;
  const sp = PM.spread || {}, st = sp.top && sp.top[0], to = PM.total || {}, tt = to.top && to.top[0];
  const spSide = clear(sp.taker) && st ? (sp.taker.side === st.fav ? st.fav + ' ' + sl(st.line) : sp.taker.side + ' ' + sl(-st.line)) : null;
  const toSide = clear(to.taker) && tt ? (to.taker.side === 'over' ? 'Over ' : 'Under ') + tt.line : null;
  const row = (lbl, vol, top, side, amt) => (
    <Row key={lbl} label={lbl} value={usd(vol)}>
      {top ? <>{lbl === 'Moneyline' ? 'Price: ' : 'Busiest: '}{top}</> : null}<br />
      24h: {side ? <>money to <Side>{side}</Side> {usd(amt)}</> : <Muted>no clear side</Muted>}
    </Row>
  );
  return <>
    {head}
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
      {row('Spread', sp.vol, st ? <>{st.fav} {sl(st.line)} <Muted>({usd(st.vol)})</Muted></> : '', spSide, sp.taker && sp.taker.net)}
      {row('Total', to.vol, tt ? <>{tt.line} <Muted>({usd(tt.vol)})</Muted></> : '', toSide, to.taker && to.taker.net)}
      {row('Moneyline', (PM.ml || {}).vol, M.ml ? (M.ml.home >= .5 ? g.home + ' ' + Math.round(M.ml.home * 100) : g.away + ' ' + Math.round(M.ml.away * 100)) + '% to win' : '', M.side, M.net)}
    </div>
    <Src>“24h” is net aggressor money: the side traders actively bought.</Src>
  </>;
}

const TAG = { play: ['success', 'Game Play'], held: ['warning', 'Held'], no: ['default', 'Not a play'] };
function Calls({ g }) {
  const pal = usePal(THEME);
  const calls = g.plays.length ? g.plays.map((p, i) => {
    const rec = p.W != null ? p.W + '–' + p.L + (p.units != null ? ', ' + fmtU(p.units) : '') : 'no record yet';
    const [v, l] = TAG[p.held ? 'held' : p.on ? 'play' : 'no'];
    return (
      <div key={i} style={{ display: 'grid', gridTemplateColumns: '64px 1fr auto', gap: '4px 12px', alignItems: 'center', padding: '10px 12px', borderRadius: tokens.radius.sm + 4, background: pal.bgSubtle }}>
        <Over>{MK[p.market]}</Over>
        <Text size="md" weight="semibold">{p.pick} <Text size="sm" mono color={pal.textTertiary}>{p.gap}{p.market === 'ml' ? ' pts' : ' pt'} off</Text></Text>
        <span style={{ justifySelf: 'end' }}><Badge theme={THEME} variant={v}>{l}</Badge></span>
        <span style={{ gridColumn: '2 / 4' }}><Dim>Gaps of {BANDTXT(p.band, p.market, D.bands)} are {rec} over the last 4 weeks.</Dim></span>
      </div>
    );
  }) : <Empty>The model has no read on this game yet.</Empty>;
  const hq = g.plays.some(p => p.held === 'backup QB'), hm = g.plays.some(p => p.held === 'line move');
  return (
    <Panel title="Vault’s call" sub="model vs market, and whether that kind of gap has been winning">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{calls}</div>
      {hq ? <Src>No Game Plays in a game with a backup QB. The model adjusts for an average backup, so a gap here may just be the market pricing this particular one.</Src>
        : hm ? <Src>No Game Plays here: the line has moved 4+ points since the lookahead, 10 days before kickoff. A move that big almost always means news, like a QB injury, that the model may not have caught yet.</Src> : null}
    </Panel>
  );
}

function Lines({ g }) {
  const pal = usePal(THEME);
  const L = g.lines, s = L.spread, t = L.total, m = L.ml;
  const bp = (b, lbl) => b ? <><Text size="sm" mono weight="semibold" style={num}>{lbl} {odds(b.price)}</Text><Sub>{b.book}</Sub></> : '–';
  const lab = l => <Over>{l}</Over>;
  const vl = x => <Text size="sm" weight="semibold" color="#b9d2ec" style={num}>{x}</Text>;
  const rows = [
    [lab('Spread'), <B>{sprd(g, s.cons)}</B>, sprd(g, s.fair, 1), vl(sprd(g, s.model, 1)), bp(s.bestAway, g.away + ' ' + lnum(s.bestAway && s.bestAway.line)), bp(s.bestHome, g.home + ' ' + lnum(s.bestHome && s.bestHome.line))],
    [lab('Total'), <B>{t.cons ?? '–'}</B>, n1(t.fair), vl(n1(t.model)), bp(t.bestOver, 'O ' + (t.bestOver && t.bestOver.line)), bp(t.bestUnder, 'U ' + (t.bestUnder && t.bestUnder.line))],
    [lab('Win chance'), '', g.home + ' ' + pct(m.fair), vl(g.home + ' ' + pct(m.model)), bp(m.bestAway, g.away), bp(m.bestHome, g.home)],
  ];
  const mv = g.move && g.move.open && (g.move.open.spread != null || g.move.open.total != null) ? g.move : null;
  return (
    <Panel title="Game lines" sub="fair line is what Vault shows as its line">
      <div style={{ whiteSpace: 'nowrap', ...num }}><Table theme={THEME} columns={['', 'Market', 'Fair line', 'Vault model', 'Best price, ' + g.away + ' / Over', 'Best price, ' + g.home + ' / Under']} rows={rows} /></div>
      {mv && <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: '6px 18px' }}>
        <Text size="sm" secondary>Opened <B>{sprd(g, mv.open.spread)}</B>, total <B>{mv.open.total ?? '–'}</B></Text>
        <Text size="sm" secondary>Now <B>{sprd(g, mv.cur.spread)}</B>, total <B>{mv.cur.total ?? '–'}</B></Text>
      </div>}
      {g.qb && <Src>The model takes {D.qb.margin} pts off a backup QB’s team and {D.qb.total} off the total, measured from past backup starts.</Src>}
    </Panel>
  );
}

// Sharp money signals. None is PROVEN yet, and the card says so: each one is
// graded on the model scoreboard and only earns a label in the app on GO.
function Sharp({ g }) {
  const SL = D.sharp_lead || {}, rows = [];
  // 1. Pinnacle vs the other books (no-vig lines)
  const ld = g.lead || {};
  const lineTxt = (mk, v) => mk === 'sp' ? sprd(g, v, 1) : n1(v);
  ['sp', 'to'].forEach(mk => {
    const x = (ld[mk] || {}).Pinnacle; if (!x) return;
    const off = Math.abs(x.gap) >= 0.5;
    const lean = mk === 'sp' ? (x.gap > 0 ? g.home : g.away) : (x.gap > 0 ? 'the Over' : 'the Under');
    rows.push(<Row key={'ld' + mk} label={(mk === 'sp' ? 'Spread' : 'Total') + ' · Pinnacle vs other books'} value={off ? <Side>{Math.abs(x.gap).toFixed(1)} pts toward {lean}</Side> : 'in line'}>
      Pinnacle {lineTxt(mk, x.book)} · other books {lineTxt(mk, x.rec)} <Muted>(no-vig)</Muted>
    </Row>);
  });
  const sp = SL.sp || {}, pin = sp.Pinnacle, fd = sp.FanDuel;
  const rec = pin ? 'When Pinnacle sat half a point or more off the other books, they moved toward it by kickoff ' + pin.toward + '–' + pin.away + '. FanDuel, as a check, did ' + (fd ? fd.toward + '–' + fd.away : '–') + '. Not proven yet: ' + (sp.verdict || '') + '.' : '';
  // 2. Polymarket: big tickets ($1k+) vs everyone else, last 24h
  const M = g.money, PM = M && M.markets;
  const st = PM && PM.spread && PM.spread.top && PM.spread.top[0], tt = PM && PM.total && PM.total.top && PM.total.top[0];
  const spFmt = x => x === st.fav ? st.fav + ' ' + sl(st.line) : x + ' ' + sl(-st.line);
  const toFmt = x => (x === 'over' ? 'Over ' : 'Under ') + tt.line;
  const bigRow = (lbl, t, fmtSide) => {
    if (!t) return null; const b = t.big;
    return <Row key={'big' + lbl} label={lbl + ' · Polymarket, last 24h'} value={b ? <>$1k+ tickets: <Side>{fmtSide(b.side)}</Side> {usd(b.net)}</> : <Muted>no $1k+ tickets</Muted>}>
      {b ? b.n + ' big tickets. ' : ''}All money: {fmtSide(t.side)} {usd(t.net)} from {t.n} trades
    </Row>;
  };
  if (M) {
    if (M.big || M.side) rows.push(bigRow('Moneyline', { big: M.big, side: M.side || 'no clear side', net: M.net, n: M.n || 0 }, x => x));
    if (PM && PM.spread && PM.spread.taker && st) rows.push(bigRow('Spread', PM.spread.taker, spFmt));
    if (PM && PM.total && PM.total.taker && tt) rows.push(bigRow('Total', PM.total.taker, toFmt));
  }
  // 3. proven accounts (scripts/build_pm_wallets.py): where accounts with a
  // record of beating the close put money, and where the usually-losing ones did
  if (M) {
    const acctLine = (lbl, sh, du, fmtSide) => {
      if (!sh && !du) return null;
      const part = (x, who) => x ? <>{who === 'sharp' ? <Side>{fmtSide(x.side)}</Side> : <Muted>{fmtSide(x.side)}</Muted>} {usd(x.net)} <Muted>({x.n} trades)</Muted></> : <Muted>none</Muted>;
      return <Row key={'acct' + lbl} label={lbl + ' · accounts with a track record, last 24h'} value={<>Sharp: {part(sh, 'sharp')}</>}>Usually-losing accounts: {part(du, 'dull')}</Row>;
    };
    const A = M.acct || {};
    rows.push(acctLine('Moneyline', A.sharp, A.dull, x => x));
    if (PM && PM.spread && PM.spread.taker && st) rows.push(acctLine('Spread', PM.spread.taker.sharp, PM.spread.taker.dull, spFmt));
    if (PM && PM.total && PM.total.taker && tt) rows.push(acctLine('Total', PM.total.taker.sharp, PM.total.taker.dull, toFmt));
  }
  const out = rows.filter(Boolean);
  if (!out.length) return null;
  return (
    <Panel title="Sharp money" sub="signals Vault is testing; none is proven yet">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{out}</div>
      {rec && <Src>{rec}</Src>}
      {D.pm_study && <Src>Sharp accounts: {D.pm_counts.sharp} Polymarket accounts whose past $1k+ NFL trades beat the closing price (and {D.pm_counts.dull} that usually lose to it). Tested on 613 games, they keep beating it, but only at the moment they trade: copying them 30 minutes to 2 hours later lost to the close, and the side they backed won no more often than the closing price said. This shows where informed money went, not a bet to copy.</Src>}
      <Src>Big tickets are trades of $1,000 or more. Net money is what traders actively bought on that side, minus what they sold.</Src>
    </Panel>
  );
}

// Signal scoreboard: every sharp-money / exchange signal Vault is testing, its
// record so far, and how far it is from a verdict (model_scoreboard.json
// "signals" + "sharp_lead"). Season-wide, same on every game page.
function Signals() {
  const pal = usePal(THEME);
  const S = D.signals, SL = D.sharp_lead || {};
  if (!S && !SL.sp) return null;
  const NEED = 50, rows = [];
  const tag = v => { v = String(v || ''); return /^GO/.test(v) ? <Badge theme={THEME} variant="success">Proven</Badge> : /^no edge/.test(v) ? <Badge theme={THEME}>No edge yet</Badge> : <Badge theme={THEME} variant="warning">Tracking</Badge>; };
  const row = (nm, ds, rec, n, v, unit) => rows.push(
    <div key={nm} style={{ background: pal.bgSubtle, borderRadius: tokens.radius.sm + 2, padding: '10px 12px', display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: '4px 12px', alignItems: 'center' }}>
      <Text size="md" weight="semibold">{nm}</Text>{tag(v)}
      <span style={{ gridColumn: '1 / -1', lineHeight: 1.5 }}><Text size="sm" secondary>{ds}</Text></span>
      <span style={{ gridColumn: '1 / -1' }}><Text size="sm" mono style={num}>{rec}</Text></span>
      <div style={{ gridColumn: '1 / -1', height: 4, borderRadius: 2, background: pal.bgMuted, overflow: 'hidden' }}><i style={{ display: 'block', height: '100%', width: Math.min(100, Math.round(n / NEED * 100)) + '%', background: ACCENT, borderRadius: 2 }} /></div>
      <span style={{ gridColumn: '1 / -1' }}><Over>{Math.min(n, NEED)} of {NEED} {unit || 'bets'} needed for a verdict</Over></span>
    </div>);
  const said = (who, b) => b.n ? <>{who} won <B>{b.won} of {b.n}</B>; the prices said about {Math.round(b.said * 10) / 10}</> : 'Nothing graded yet. Logging started this week.';
  const sp = SL.sp || {}, pin = sp.Pinnacle, fd = sp.FanDuel;
  if (pin) row('Pinnacle moves first (spreads)', 'When Pinnacle sat half a point or more off the other books 3+ hours out, did they follow it by kickoff? FanDuel is the check: any book off the pack gets pulled back.',
    <>Books moved toward Pinnacle <B>{pin.toward}–{pin.away}</B> · FanDuel check {fd ? fd.toward + '–' + fd.away : '–'}</>, pin.n, sp.verdict && /GO/.test(sp.verdict) ? 'GO' : 'tracking', 'games');
  const pp = (SL.props || {}).Pinnacle;
  if (pp) row('Pinnacle moves first (props)', 'Same test on player props, at the same line.', <>Books moved toward Pinnacle <B>{pp.toward}–{pp.away}</B></>, pp.n, (SL.props || {}).verdict && /GO/.test(SL.props.verdict) ? 'GO' : 'tracking', 'props');
  if (S) {
    const P = S.pm_sharp || {};
    if (P.all) row('Sharp accounts ($25k+)', 'Polymarket accounts with a record of beating the closing price, when they put $25k+ on one team before kickoff. Their side is scored against the price at kickoff.', said('Their side', P.all), P.all.n, P.all.verdict, 'games');
    if (P.crowd_disagrees) row('Sharp accounts vs the crowd', 'Same, but only when everyone else put $25k+ on the other team.', said('Sharp side', P.crowd_disagrees), P.crowd_disagrees.n, P.crowd_disagrees.verdict, 'games');
    const K = S.kalshi_vs_books;
    if (K) row('Kalshi vs the sportsbooks', 'When Kalshi’s price on a prop sits 5+ points off the books’ fair price, does Kalshi’s side win more often than the books said?',
      <>{said('Kalshi’s side', K)}{K.all_lines && K.all_lines.n ? ' · all ' + K.all_lines.n + ' lines: Kalshi log-loss ' + K.all_lines.logloss_kalshi + ' vs books ' + K.all_lines.logloss_books + ' (lower is sharper)' : ''}</>, K.n, K.verdict, 'props');
    const V = S.vault_vs_kalshi;
    if (V) row('Vault vs Kalshi', 'When Vault’s model is 10+ points off Kalshi, Best Bets drops the play. Was Kalshi right?', said('Kalshi’s side', V), V.n, V.verdict, 'props');
    const W = S.withheld;
    if (W) {
      const hb = W.would_be_plays;
      row('Withheld props (starter out)', 'Props Vault holds back because a teammate starter is out, usually the QB. Scored anyway to see whether the hold is costing plays.',
        W.lines ? <>Model’s lean won <B>{W.lean_won} of {W.lines}</B> lines · overs hit {W.overs_hit} · would-be Best Bets {hb && (hb.W + hb.L) ? hb.W + '–' + hb.L + ', ' + fmtU(hb.units) : 'none yet'}</> : 'nothing graded yet', W.lines, 'tracking', 'lines');
    }
  }
  return (
    <Panel title="Signal scoreboard" sub="what Vault is testing, and how each one is doing this season">
      <div style={{ display: 'grid', gap: 8 }}>{rows}</div>
      <Src>A signal is proven only after {NEED} bets, and only if its side won clearly more often than its price said (2+ standard errors). Until then it is context, not a bet. Week 3 sharp-account results were rebuilt from Polymarket’s trade history; later weeks are logged live.</Src>
    </Panel>
  );
}

function GapBar({ p }) {
  const pal = usePal(THEME);
  if (p.mktOver == null) return null;
  const mark = (x, c) => <i style={{ position: 'absolute', top: -2, left: `calc(${x * 100}% - 1px)`, width: 2, height: 10, borderRadius: 2, background: c }} />;
  return <span style={{ display: 'inline-block', verticalAlign: 'middle', position: 'relative', width: 92, height: 6, borderRadius: 99, background: pal.bgMuted }}>
    <span style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: pal.border }} />{mark(p.mktOver, pal.textTertiary)}{mark(p.over, '#b9d2ec')}
  </span>;
}
function Pick({ name, small, price, book, desc, lock }) {
  const pal = usePal(THEME);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '2px 12px', alignItems: 'center', padding: '10px 12px', borderRadius: tokens.radius.sm + 4, background: lock ? pal.successBg : pal.bgSubtle }}>
      <span><Text size="md" weight="semibold">{name}</Text> <Dim size="sm" style={{ marginLeft: 4 }}>{small}</Dim></span>
      <span style={{ textAlign: 'right', gridRow: 'span 2' }}><Text size="sm" mono style={num}>{odds(price)}</Text><Sub>{book}</Sub></span>
      <Text size="sm" secondary style={num}>{desc}</Text>
    </div>
  );
}
function Props({ g }) {
  const pal = usePal(THEME);
  const card = g.card.map((c, i) => <Pick key={i} lock name={c.name} small={c.team} price={c.price} book={c.book}
    desc={c.market + ' ' + (c.side === 'under' ? 'Under' : 'Over') + ' ' + c.line + (c.posted ? ' · locked ' + new Date(c.posted).toLocaleDateString('en-US', { ...ET, weekday: 'short' }) + ' ' + timeOf(c.posted) : '') + (c.result ? ' · ' + c.result : '')} />);
  const scored = g.props.filter(p => p.status !== 'out' && p.status !== 'withheld');
  const seenBB = new Set();
  const bb = scored.filter(p => p.status === 'pass').sort((a, b) => (b.ev || 0) - (a.ev || 0)).filter(p => !seenBB.has(p.name) && seenBB.add(p.name)).map((p, i) => <Pick key={i} name={p.name} small={p.team + ' ' + (p.pos || '')} price={p.price} book={p.book}
    desc={p.market + ' ' + (p.side === 'under' ? 'Under' : 'Over') + ' ' + p.line + ' · Vault ' + pct(p.side === 'under' ? 1 - p.over : p.over) + ' vs market ' + pct(p.mktOver == null ? null : (p.side === 'under' ? 1 - p.mktOver : p.mktOver)) + ' · grade ' + p.grade + (p.ev != null ? ' · ' + p.ev + '% EV' : '')} />);
  const diff = p => p.mktOver == null ? 0 : Math.abs(p.over - p.mktOver);
  const rows = scored.slice().sort((a, b) => (a.status === 'pass' ? -1 : 0) - (b.status === 'pass' ? -1 : 0) || diff(b) - diff(a)).map(p => {
    const pass = p.status === 'pass', c = pass ? undefined : pal.textSecondary;
    const t = (x, extra) => <Text size="sm" color={c} style={{ ...num, ...extra }}>{x}</Text>;
    return [
      <><Text size="sm" weight="semibold" color={pass ? pal.text : pal.textSecondary}>{p.name}</Text><Sub>{p.team} {p.pos || ''}</Sub></>,
      t(p.market + ' ' + p.line), <R>{t(pct(p.over))}</R>, <R>{t(pct(p.mktOver))}</R>, <R>{t(pct(p.kalshi))}</R>, <GapBar p={p} />,
      <><Text size="sm" weight="semibold" color={p.side === 'under' ? '#f0a3ae' : pal.success}>{p.side === 'under' ? 'Under' : 'Over'}</Text>{p.proj != null && <Sub>proj {p.proj}</Sub>}</>,
      <R>{t(odds(p.price), { fontFamily: tokens.font.mono })}<Sub>{p.book}</Sub></R>,
      <Text size="sm" weight={pass ? 'semibold' : 'regular'} color={pass ? pal.success : pal.textTertiary}>{p.label}</Text>,
    ];
  });
  const wh = {};
  g.props.filter(p => p.status === 'withheld' || p.status === 'out').forEach(p => { const k = p.status === 'out' ? 'Ruled out' : p.why === 'QB out' ? 'Held: their QB is out' : p.why === 'RB2 out' ? 'Unders held: backup RB is out, so he has the backfield to himself' : 'Held: ' + p.why; wh[k] = wh[k] || []; if (!wh[k].includes(p.name)) wh[k].push(p.name); });
  const whE = Object.entries(wh);
  const Sec = ({ h, children }) => <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 16 }}><Over>{h}</Over>{children}</div>;
  const empty = !card.length && !bb.length && !rows.length && !whE.length;
  return (
    <Panel title="Player props">
      {card.length > 0 && <Sec h="Vault’s Plays · locked card">{card}</Sec>}
      {bb.length > 0 && <Sec h="Best Bets">{bb}</Sec>}
      {rows.length > 0 && <Sec h="Every prop Vault scored · chance the Over hits">
        <div style={{ whiteSpace: 'nowrap' }}><Table theme={THEME} rows={rows} columns={['Player', 'Prop', <R>Vault</R>, <R>Books</R>,
          <R><Tooltip theme={THEME} text="Kalshi’s Over price, read off its nearest strikes"><span>Kalshi</span></Tooltip></R>,
          <Tooltip theme={THEME} text="Grey: market. Blue: Vault. Centre is 50%."><span>Gap</span></Tooltip>, 'Lean', <R>Best price</R>, 'Status']} /></div>
      </Sec>}
      {whE.length > 0 && <Sec h="Not scored"><div style={{ lineHeight: 1.6 }}>{whE.map(([k, v]) => <div key={k}><Text size="sm" secondary><B>{k}:</B> {v.join(', ')}</Text></div>)}</div></Sec>}
      {empty && <Empty>Sportsbooks haven’t posted enough props for this game yet. They usually land midweek, and this page picks them up when it’s refreshed.</Empty>}
    </Panel>
  );
}

function HowTo() {
  const r = (D.record[D.season] || {}).summary;
  const cr = Object.entries(D.card_rule).map(([k, v]) => { const [mk, sd, ps] = k.split('|'); return (mk === 'rec_yd' ? 'receiving-yard' : mk) + ' ' + sd + 's (' + ps + '), ' + v.W + '–' + v.L; }).join('; ');
  const gr = Object.entries(D.game_rules_on).map(([k, v]) => { const [mk, b] = k.split('|'); return MK[mk].toLowerCase() + 's ' + BANDTXT(b, mk, D.bands) + ' off, ' + v.W + '–' + v.L; }).join('; ');
  return (
    <Panel title="How to read this">
      <div style={{ maxWidth: '74ch', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Text size="sm" secondary><B>Vault’s Plays</B> are the locked card: up to 10 props a week, frozen at the line and price they posted with, from play types that have been winning{cr ? ' (today: ' + cr + ')' : ''}.{r ? <> This season: <B>{r.W}–{r.L}, {r.units >= 0 ? '+' : ''}{r.units.toFixed(1)} units</B> at the posted price.</> : null}</Text>
        <Text size="sm" secondary><B>Best Bets</B> pass every filter: at least two sportsbooks on the same line, a real edge at the best price, and no warning signs like an unconfirmed role or a sharp exchange disagreeing. The props table shows every line Vault scored and the reason the rest didn’t make it.</Text>
        <Text size="sm" secondary><B>Game Plays</B> only fire for gap sizes with a winning record over the last 4 weeks{gr ? ' (today: ' + gr + ')' : ''}. Vault’s own line is the sportsbooks’ fair line; the team-rating model hasn’t beaten the closing line over time, so it is context, not a bet on its own.</Text>
      </div>
    </Panel>
  );
}

function Game({ g, wide }) {
  const pal = usePal(THEME);
  const W = g.weather;
  const chips = [];
  const chip = (k, x, warn) => <span key={k} style={{ display: 'inline-flex', alignItems: 'center', ...tokens.type.sm, ...num, color: warn ? pal.warning : pal.textSecondary, background: warn ? pal.warningBg : pal.bgSubtle, border: `1px solid ${warn ? 'transparent' : pal.borderSubtle}`, borderRadius: 999, padding: '3px 10px', fontFamily: tokens.font.sans }}>{x}</span>;
  chips.push(chip('t', dayOf(g.commence) + ', ' + timeOf(g.commence) + ' ET'));
  if (W && W.stadium) chips.push(chip('s', W.stadium + (W.roof && W.roof !== 'outdoor' ? ' · ' + W.roof : '')));
  if (W && W.roof === 'outdoor' && W.temp_f != null) chips.push(chip('w', Math.round(W.temp_f) + '°F · wind ' + Math.round(W.wind_mph) + ' mph' + (W.precip_pct >= 30 ? ' · ' + W.precip_pct + '% rain' : '')));
  if (g.neutral) chips.push(chip('n', 'Neutral site'));
  if (g.qb) [['away', g.away], ['home', g.home]].forEach(([s, t]) => { const q = g.qb[s]; if (q) chips.push(chip('q' + s, t + ' backup QB: ' + (q.starter || 'backup') + ' for ' + q.established, true)); });
  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Over>Week {g.week} breakdown</Over>
        <Heading level={1} style={{ fontSize: wide ? 32 : 24, textWrap: 'balance' }}>{g.away} {TEAM[g.away] || ''}<span style={{ color: pal.textTertiary, fontWeight: 500, margin: '0 .25em' }}>@</span>{g.home} {TEAM[g.home] || ''}</Heading>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>{chips}</div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: wide ? 'minmax(0,1fr) minmax(0,1.25fr)' : 'minmax(0,1fr)', gap: 12 }}>
        <Score g={g} /><Calls g={g} />
      </div>
      <Lines g={g} />
      <Sharp g={g} />
      <Signals />
      <Props g={g} />
      <HowTo />
    </>
  );
}

// ───────────────────────── shell ─────────────────────────
function App() {
  const pal = usePal(THEME);
  const [data, setData] = useState(null); const [err, setErr] = useState(false);
  const [cur, setCur] = useState(null);
  const w = useWidth(); const wide = w > 900;
  useEffect(() => {
    fetch(DATA_SRC, { cache: 'no-store' }).then(r => r.json()).then(d => {
      D = d;
      const h = (location.hash || '').slice(1).replace('-', '@');
      if (d.games.length) setCur(d.games.some(g => g.key === h) ? h : d.games[0].key);
      setData(d);
    }).catch(() => setErr(true));
  }, []);
  const pick = k => {
    setCur(k);
    try { history.replaceState(null, '', '#' + k.replace('@', '-')); } catch (e) {}
    if (!wide) document.getElementById('main')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    else window.scrollTo({ top: 0 });
  };
  const shell = kids => <div style={{ maxWidth: 1320, margin: '0 auto', padding: '0 16px 48px', color: pal.text, fontFamily: tokens.font.sans, display: wide ? 'grid' : 'block', gridTemplateColumns: '268px minmax(0,1fr)', gap: 24, overflowX: 'clip' }}>{kids}</div>;
  if (err) return shell(<div style={{ gridColumn: '1 / -1', paddingTop: 40 }}><AlertBanner theme={THEME} variant="danger" title="Could not load the slate" description="Reload the page to try again." /></div>);
  if (!data) return shell(<div style={{ gridColumn: '1 / -1', paddingTop: 40, display: 'grid', gap: 12 }}><Skeleton theme={THEME} height={40} rounded /><Skeleton theme={THEME} height={180} rounded /><Skeleton theme={THEME} height={260} rounded /></div>);
  const g = data.games.find(x => x.key === cur);
  const side = (
    <aside aria-label="Games" style={wide ? { position: 'sticky', top: 0, alignSelf: 'start', maxHeight: '100dvh', padding: '18px 0 24px', display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' } : { padding: '14px 0 0', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Brand small={!wide} />
      {data.games.length > 0 && <Slate cur={cur} pick={pick} wide={wide} />}
      <Key />
      {wide && <div style={{ padding: '0 6px', display: 'grid', gap: 8, justifyItems: 'start' }}><Fresh d={data} /><Dim size="sm" style={{ lineHeight: 1.5 }}>{stampTxt()}</Dim></div>}
    </aside>
  );
  return shell(<>
    {side}
    <main id="main" style={{ paddingTop: 18, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, scrollMarginTop: 8 }}>
      {g ? <Game key={g.key} g={g} wide={wide} /> : <Empty>No upcoming games on the board.</Empty>}
      {!wide && <div style={{ display: 'grid', gap: 8, justifyItems: 'start' }}><Fresh d={data} /><Dim size="sm">{stampTxt()}</Dim></div>}
    </main>
  </>);
}

// test hook: render one game server-side (scratch smoke test, see build notes)
export const __test = { setData: d => { D = d; }, Game, Slate, Key, Brand, ThemeProvider, AccentContext, THEME, ACCENT };
if (typeof document !== 'undefined' && document.getElementById('root')) createRoot(document.getElementById('root')).render(
  <ThemeProvider theme={THEME}><AccentContext.Provider value={ACCENT}><App /></AccentContext.Provider></ThemeProvider>
);
