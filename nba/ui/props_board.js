// Props Table, Outlier layout (render_app.py inlines this at /*PROPS_BOARD_JS*/).
// One row per prop AND side, colored hit-rate tiles, opponent rank by position, Vault's projection, fair and edge,
// and a Filters panel whose venue switches re-pick the best price. A row opens the prop's own page
// (#propboard/<player>/<stat>/<o|u>): game-log chart against the line and Vault's projection, the Vault model card,
// every price, and a bet tracker that saves through pvMkBet into My Bets. Every number comes from the page's own
// pricing (priceRow, scOf, logsOf, hitRate): nothing here prices a prop.
window.PBX = (() => {
  const LS = 'nba-pbx-f';
  try{ localStorage.removeItem('nba-pbx-classic'); }catch(e){}   // the classic table is gone; forget a saved choice of it
  const FDEF = {ven: {book: 1, kalshi: 1, poly: 1, pickem: 1}, gate: 'any', minEdge: null, minGap: null, minL10: null, oppFav: false, oMin: '', oMax: '', healthy: false, starters: false, moved: 'any', watch: false};
  const load = () => { try{ const f = JSON.parse(localStorage.getItem(LS)); return f ? {...FDEF, ...f, ven: {...FDEF.ven, ...(f.ven || {})}} : JSON.parse(JSON.stringify(FDEF)); }catch(e){ return JSON.parse(JSON.stringify(FDEF)); } };
  const S = {stat: 'all', side: 'all', game: 'all', q: '', sort: 'edge', dir: -1, limit: 60, fOpen: false, f: load(), open: null};
  const save = () => { try{ localStorage.setItem(LS, JSON.stringify(S.f)); }catch(e){} };
  // a watch remembers the side it was starred on (over or under); one saved before that remembers both
  const watched = (r, side) => { const w = pvW[pvKey(r)]; return !!w && (!w.side || w.side === side); };

  const VEN = [['book', 'Sportsbooks'], ['kalshi', 'Kalshi'], ['poly', 'Polymarket'], ['pickem', "Pick'em"]];
  const BK = {DraftKings: ['DK', '#53d337', '#0a1f05'], FanDuel: ['FD', '#1493ff', '#fff'], BetMGM: ['MGM', '#b39256', '#fff'], bet365: ['365', '#127a4b', '#fff'], BetRivers: ['BR', '#1b3d6d', '#fff'],
    Fanatics: ['FN', '#e11d2b', '#fff'], Caesars: ['CZR', '#0f3b33', '#e8c770'], Pinnacle: ['PIN', '#f26b21', '#fff'], Kalshi: ['K', '#00b386', '#fff'], Polymarket: ['PM', '#2e5bff', '#fff'],
    PrizePicks: ['PP', '#7b3fe4', '#fff'], prizepicks: ['PP', '#7b3fe4', '#fff'], Underdog: ['UD', '#f7c600', '#1a1500'], underdog: ['UD', '#f7c600', '#1a1500'], Sleeper: ['SL', '#1f2a44', '#7cf0ff'], sleeper: ['SL', '#1f2a44', '#7cf0ff']};
  const bkChip = n => { const b = BK[n] || [String(n || '?').slice(0, 2).toUpperCase(), '#555', '#fff']; return `<span class="pbx-bk" style="background:${b[1]};color:${b[2]}" title="${esc(PKN[n] || n)}">${b[0]}</span>`; };
  const pToAm = p => p >= .5 ? -Math.round(100 * p / (1 - p)) : Math.round(100 * (1 - p) / p);
  const fmtAm = a => (a > 0 ? '+' : '') + a;
  const amNum = x => { if (x == null || x === '') return null; const n = +String(x).replace('−', '-'); return isFinite(n) && n !== 0 ? n : null; };
  const sgn = (x, d = 1) => { if (x == null) return '-'; const v = +x.toFixed(d); return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d); };
  const pc0 = x => x == null ? '-' : Math.round(x * 100) + '%';
  const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] || 'th');
  const isOver = s => /^(over|yes)$/i.test(s);
  const famOf = c => c.venue === 'kalshi' ? 'kalshi' : c.venue === 'pickem' ? 'pickem' : c.bk === 'Polymarket' ? 'poly' : 'book';
  const WIN = [['L5', 'L5'], ['L10', 'L10'], ['L20', 'L20'], ['H2H', 'H2H'], ['S0', ''], ['S1', '']];
  const szn = y => `${String(y - 1).slice(2)}-${String(y).slice(2)}`;

  // opponent rank by position group: this season's per-game total allowed to guards / forwards / centers, 1st = fewest
  let RK = null;
  function ranks(){
    if (RK || !GL) return RK;
    const SEA = GL.current_season, agg = {}, games = {};
    for (const [pid, rows] of Object.entries(GL.players)){
      const grp = PIDX[pid] && PIDX[pid].p && (PIDX[pid].p.grp || PIDX[pid].p.pos); if (!grp) continue;
      for (const r of rows){ if (r[1] !== SEA || r[4]) continue; const t = GL.teams[r[2]]; (games[t] = games[t] || new Set()).add(r[0]);
        for (const s of ['pts', 'reb', 'ast', '3pm', 'stl', 'blk', 'tov', 'pra', 'pr', 'pa', 'ra', 'sb']){ const k = `${t}|${grp}|${s}`; agg[k] = (agg[k] || 0) + gval(r, s); } }
    }
    RK = {};
    const teams = Object.keys(games).filter(t => D.teams[t]);
    for (const grp of ['G', 'F', 'C']) for (const s of ['pts', 'reb', 'ast', '3pm', 'stl', 'blk', 'tov', 'pra', 'pr', 'pa', 'ra', 'sb']){
      teams.map(t => [t, (agg[`${t}|${grp}|${s}`] || 0) / games[t].size]).sort((a, b) => a[1] - b[1]).forEach(([t, v], i) => { RK[`${t}|${grp}|${s}`] = [i + 1, v, games[t].size]; });
    }
    return RK;
  }
  const oppGood = (rk, side) => !rk ? 0 : side === 'o' ? (rk >= 21 ? 1 : rk <= 10 ? -1 : 0) : (rk <= 10 ? 1 : rk >= 21 ? -1 : 0);

  // rows: one per prop and side, rebuilt when the board changes
  let cacheKey = null, ROWS = [];
  function build(B){
    const key = `${B.t}|${(B.props || []).length}|${priceVer}`; if (key === cacheKey) return ROWS;
    cacheKey = key; ROWS = []; const cache = {}, games = B.games || [], now = Date.now() / 1000, rk = ranks();
    for (const e of B.props || []){
      if (!PR.variance[e.s]) continue;
      const g = games.find(x => String(x.id) === String(e.g)); if (g && g.tip <= now) continue;     // a tipped game's pre-tip prices are not bettable
      let r; try{ r = priceRow(e, cache); }catch(err){ continue; }
      if (r.line == null) continue;
      r.game = g;
      const sc = scOf(r), grp = PIDX[e.p] && PIDX[e.p].p && (PIDX[e.p].p.grp || PIDX[e.p].p.pos);
      const opp = g ? (r.team === g.home ? g.away : g.home) : null, orank = rk && opp && grp ? rk[`${opp}|${grp}|${e.s}`] : null;
      for (const side of ['o', 'u']){
        const fams = {};
        for (const c of r.all || []){ if (c.line !== r.line || c.edge == null || isOver(c.side) !== (side === 'o')) continue; const f = famOf(c); if (!fams[f] || c.edge > fams[f].edge) fams[f] = c; }
        ROWS.push({r, sc, side, fams, g, opp, grp, orank, fair: r.fair == null ? null : side === 'o' ? r.fair : 1 - r.fair,
          diff: r.mu == null ? null : side === 'o' ? r.mu - r.line : r.line - r.mu, h: null});
      }
    }
    return ROWS;
  }
  function hits(x){
    if (x.h) return x.h;
    const r = x.r, line = r.line, all = (r._logs || (r._logs = logsOf(r))).all, side = x.side;
    const rate = gl => { const h = hitRate(gl, r.e.s, line); if (!h.n) return null; const n = side === 'o' ? h.over : gl.filter(g => gval(g, r.e.s) < line).length; return {n: h.n, h: n, pct: n / h.n}; };
    return x.h = {L5: rate(windowGames(r, 'L5').gl), L10: rate(windowGames(r, 'L10').gl), L20: rate(windowGames(r, 'L20').gl), H2H: rate(windowGames(r, 'H2H').gl),
      S0: rate(all.filter(g => g[1] === GL.current_season)), S1: rate(all.filter(g => g[1] === GL.current_season - 1))};
  }
  function pick(x){                                   // the best price on this side among the venues the filter allows
    const v = S.f.ven, c = Object.entries(x.fams).filter(([f]) => v[f] && f !== 'pickem').map(([, c]) => c).sort((a, b) => b.edge - a.edge);
    x.best = c[0] || null; x.pk = v.pickem ? x.fams.pickem || null : null; x.nb = c.length;
    x.edge = x.best ? x.best.edge : null; x.gate = x.best ? x.best.g : null;
  }
  const priceTxt = c => !c ? null : c.venue === 'kalshi' ? fmtAm(pToAm(c.price)) : c.price == null ? 'flat' : String(c.price);
  const amOf = c => !c ? null : c.venue === 'kalshi' ? pToAm(c.price) : amNum(c.price);

  function fActive(){
    const f = S.f, o = [];
    if (VEN.some(([k]) => !f.ven[k])) o.push(['ven', 'Venues: ' + VEN.filter(([k]) => f.ven[k]).map(x => x[1]).join(', ')]);
    if (f.gate !== 'any') o.push(['gate', f.gate === 'go' ? 'Passing gates' : 'Go or watch']);
    if (f.minEdge != null) o.push(['minEdge', f.minEdge === 0 ? 'Positive edge' : `Edge ${f.minEdge}%+`]);
    if (f.minGap != null) o.push(['minGap', `Projection ${f.minGap}+ past line`]);
    if (f.minL10 != null) o.push(['minL10', `L10 ${f.minL10}%+`]);
    if (f.oppFav) o.push(['oppFav', 'Soft matchup']);
    if (f.oMin !== '' || f.oMax !== '') o.push(['odds', `Odds ${f.oMin || 'any'} to ${f.oMax || 'any'}`]);
    if (f.healthy) o.push(['healthy', 'No injury tag']);
    if (f.starters) o.push(['starters', 'Starters only']);
    if (f.watch) o.push(['watch', 'Watching only']);
    if (f.moved !== 'any') o.push(['moved', f.moved === 'with' ? 'Line moved toward side' : 'Line moved against side']);
    return o;
  }
  function fClear(k){ const f = S.f; if (k === 'ven') f.ven = {...FDEF.ven}; else if (k === 'odds'){ f.oMin = ''; f.oMax = ''; } else f[k] = FDEF[k]; save(); }

  const SORTS = {
    prop: x => x.r.name, line: x => x.r.line, odds: x => x.edge, proj: x => x.diff, fair: x => x.fair, edge: x => x.edge,
    opp: x => x.orank ? (x.side === 'o' ? x.orank[0] : 31 - x.orank[0]) : null,
    L5: x => (hits(x).L5 || {}).pct, L10: x => (hits(x).L10 || {}).pct, L20: x => (hits(x).L20 || {}).pct, H2H: x => (hits(x).H2H || {}).pct, S0: x => (hits(x).S0 || {}).pct, S1: x => (hits(x).S1 || {}).pct,
  };
  function filtered(rows){
    const q = S.q.trim().toLowerCase(), f = S.f, oMin = amNum(f.oMin), oMax = amNum(f.oMax);
    rows.forEach(pick);
    const out = rows.filter(x => {
      const r = x.r;
      if (!((S.stat === 'all' || r.e.s === S.stat) && (S.side === 'all' || x.side === S.side) && (S.game === 'all' || String(r.e.g) === S.game) && (!q || r.name.toLowerCase().includes(q)))) return false;
      if (!x.best && !x.pk) return false;
      if (f.gate === 'go' && x.gate !== 'go') return false;
      if (f.gate === 'gw' && x.gate !== 'go' && x.gate !== 'watch') return false;
      if (f.minEdge != null && !(x.edge != null && x.edge > 0 && x.edge * 100 >= f.minEdge - 1e-9)) return false;
      if (f.minGap != null && !(x.diff != null && x.diff >= f.minGap)) return false;
      if (f.minL10 != null){ const h = hits(x).L10; if (!h || h.pct * 100 < f.minL10) return false; }
      if (f.oppFav && !(x.orank && oppGood(x.orank[0], x.side) > 0)) return false;
      if (oMin != null || oMax != null){ const a = amOf(x.best); if (a == null) return false; if (oMin != null && amP(a) > amP(oMin) + 1e-9) return false; if (oMax != null && amP(a) < amP(oMax) - 1e-9) return false; }
      if (f.healthy && r.inj && !/^available$/i.test(r.inj)) return false;
      if (f.starters && r.lu !== 's') return false;
      if (f.watch && !watched(r, x.side)) return false;
      if (f.moved !== 'any'){ const d = x.sc.dm; if (!d) return false; if ((f.moved === 'with') !== (x.side === 'o' ? d < 0 : d > 0)) return false; }   // a falling line makes the over easier
      return true;
    });
    const g = SORTS[S.sort] || SORTS.edge, dir = S.sort === 'prop' ? 1 : S.dir;
    out.sort((a, b) => { const p = g(a), q2 = g(b); if (p == null || q2 == null) return (p == null) - (q2 == null); return (typeof p === 'string' ? p.localeCompare(q2) : p - q2) * dir; });
    return out;
  }

  // ── cells ──
  const hcls = h => !h ? 'na' : h.pct >= .7 ? 'h3' : h.pct >= .6 ? 'h2' : h.pct > .5 ? 'h1' : h.pct === .5 ? '' : h.pct > .4 ? 'l1' : h.pct > .3 ? 'l2' : 'l3';
  const hcell = h => `<span class="pbx-hc ${hcls(h)}" title="${h ? `${h.h} of ${h.n}` : 'No games'}">${h ? Math.round(h.pct * 100) + '%' : '-'}</span>`;
  const face = x => `<span class="pbx-face"><span class="hs"><b>${esc(initials(x.r.name))}</b><img src="${phSrc(x.r.e.p)}" alt="" loading="lazy" onerror="this.remove()"></span>${PH && PH.logos && PH.logos[x.r.team] ? `<span class="lo"><img src="${PH.logos[x.r.team]}" alt=""></span>` : ''}</span>`;
  const injTag = r => { const i = r.inj && !/^available$/i.test(r.inj) ? r.inj : r.lu === 'X' ? 'Inactive' : ''; if (!i) return ''; return `<span class="pbx-tag ${/out|inactive/i.test(i) ? 'out' : ''}" title="${esc(i)}">${/^question/i.test(i) ? 'Q' : /^probable/i.test(i) ? 'P' : /^doubt/i.test(i) ? 'D' : esc(i)}</span>`; };
  const sideW = s => s === 'o' ? '<span class="ov">Over</span>' : '<span class="un">Under</span>';
  const odds = x => x.best ? `<span class="pbx-odds">${bkChip(x.best.bk)}<b>${esc(priceTxt(x.best))}</b>${x.nb > 1 ? `<small>+${x.nb - 1}</small>` : ''}</span>`
    : x.pk ? `<span class="pbx-odds">${bkChip(x.pk.bk)}<b>${esc(priceTxt(x.pk))}</b><small>pick'em</small></span>` : '<small class="muted">No price</small>';
  const edgeC = x => { if (x.edge == null) return '<span class="muted">-</span>';
    const tag = x.r.hold ? `<span class="pbx-gate hold" title="${esc(x.r.hold.why || x.r.hold.label || 'Held')}">HOLD</span>` : x.gate === 'go' ? '<span class="pbx-gate go">GO</span>' : x.gate === 'watch' ? '<span class="pbx-gate watch">WATCH</span>' : '';
    return `<span class="pbx-two"><b class="${x.edge > 0 ? 'pos' : 'neg'}">${sgn(x.edge * 100)}%</b>${tag}</span>`; };
  const oppC = x => { const k = x.orank; if (!k) return '<span class="muted">-</span>'; const gd = oppGood(k[0], x.side);
    return `<span class="pbx-opp ${gd > 0 ? 'h1' : gd < 0 ? 'l1' : ''}" title="${x.opp} allow ${fmt(k[1])} ${SLABEL[x.r.e.s]} a game to ${x.grp === 'G' ? 'guards' : x.grp === 'C' ? 'centers' : 'forwards'} this season (${k[2]} games). 1st allows the fewest.">${ord(k[0])}<small>${x.opp}</small></span>`; };
  const lineC = x => { const d = x.sc.dm; return `<span class="pbx-two"><b>${x.r.line}</b>${d ? `<small class="${d > 0 ? 'up' : 'dn'}">${d > 0 ? '▲' : '▼'} ${Math.abs(d)} from ${x.r.line - d}</small>` : ''}</span>`; };
  const projC = x => x.r.mu == null ? '<span class="muted">-</span>' : `<span class="pbx-two"><b>${fmt(x.r.mu)}</b><small class="${x.diff > 0 ? 'pos' : 'neg'}">${sgn(x.diff)}</small></span>`;

  function filterPanel(n){
    const f = S.f, o = (k, v, l, on) => `<button type="button" class="pbx-fopt${on ? ' on' : ''}" data-f="${k}" data-v="${v}" aria-pressed="${!!on}">${l}</button>`;
    return `<div class="pbx-fpanel">
      <div><h6>Venues you can bet</h6><div>${VEN.map(([k, l]) => o('ven', k, l, f.ven[k])).join('')}</div></div>
      <div><h6>Gates</h6><div>${o('gate', 'any', 'Any', f.gate === 'any')}${o('gate', 'gw', 'Go or watch', f.gate === 'gw')}${o('gate', 'go', 'Go only', f.gate === 'go')}</div></div>
      <div><h6>Edge after fees</h6><div>${o('minEdge', 'null', 'Any', f.minEdge == null)}${[0, 2, 3, 5].map(v => o('minEdge', v, v ? v + '%+' : 'Above 0', f.minEdge === v)).join('')}</div></div>
      <div><h6>Vault projection past line</h6><div>${o('minGap', 'null', 'Any', f.minGap == null)}${[.5, 1, 2, 3].map(v => o('minGap', v, '+' + v, f.minGap === v)).join('')}</div></div>
      <div><h6>L10 hit rate</h6><div>${o('minL10', 'null', 'Any', f.minL10 == null)}${[50, 60, 70, 80].map(v => o('minL10', v, v + '%+', f.minL10 === v)).join('')}</div></div>
      <div><h6>Best odds (American)</h6><div class="rng"><input data-fodds="oMin" placeholder="-200" value="${esc(f.oMin)}" aria-label="Shortest price">to<input data-fodds="oMax" placeholder="+200" value="${esc(f.oMax)}" aria-label="Longest price"></div></div>
      <div><h6>Line move since open</h6><div>${o('moved', 'any', 'Any', f.moved === 'any')}${o('moved', 'with', 'Toward side', f.moved === 'with')}${o('moved', 'against', 'Against side', f.moved === 'against')}</div></div>
      <div><h6>Player and matchup</h6><div>${o('oppFav', 1, 'Soft matchup', f.oppFav)}${o('healthy', 1, 'No injury tag', f.healthy)}${o('starters', 1, 'Starters only', f.starters)}${o('watch', 1, '★ Watching only', f.watch)}</div></div>
      <div class="ft"><span class="muted">${n.toLocaleString()} props match. Venues change which price counts as best.</span><button type="button" class="btn" data-freset="1">Reset</button><button type="button" class="btn primary" data-fdone="1">Done</button></div></div>`;
  }

  // ── prop detail page (#propboard/<player id>/<stat>/<o|u>) ──
  const DS = {win: 'L10', med: false, rtab: 'matchup', T: null, bar: null};
  const MIN_I = 5;
  const routeOf = () => { const m = /^#propboard\/(\d+)\/([a-z0-9]+)\/([ou])$/i.exec(location.hash); return m ? {pid: +m[1], s: m[2].toLowerCase(), side: m[3].toLowerCase()} : null; };
  const goProp = (pid, s, side) => { location.hash = `#propboard/${pid}/${s}/${side}`; };
  const avg = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;
  const med = a => { if (!a.length) return null; const b = a.slice().sort((x, y) => x - y), m = b.length >> 1; return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2; };
  const f1 = v => v == null ? '-' : fmt(v);
  function winGl(all, w, opp){
    const SEA = GL.current_season;
    return w === 'L5' ? all.slice(0, 5) : w === 'L10' ? all.slice(0, 10) : w === 'L20' ? all.slice(0, 20) : w === 'H2H' ? all.filter(g => GL.teams[g[2]] === opp)
      : w === 'S0' ? all.filter(g => g[1] === SEA) : all.filter(g => g[1] === SEA - 1);
  }
  // Made-vs-attempted stats get a ghost outline for the attempts (same unit, so it shares the axis).
  const GHOST = {'3pm': 'tpa', fgm: 'fga', ftm: 'fta'};
  // Short names for the numbers printed inside stacked segments.
  const SEG = {pts: 'P', reb: 'R', ast: 'A', stl: 'S', blk: 'B', oreb: 'Off', dreb: 'Def'};
  // Bars split into parts: the combo markets, and rebounds into offensive / defensive when the log has both.
  const partsOf = (g, s) => COMBO[s] || (s === 'reb' && g[GI.oreb] != null && g[GI.dreb] != null && g[GI.oreb] + g[GI.dreb] === g[GI.reb] ? ['dreb', 'oreb'] : [s]);
  const mdShort = day => { const d = new Date(day * 864e5); return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`; };
  function chart(gl, s, line, mu){
    gl = gl.slice(0, 30).reverse();
    if (!gl.length) return '<p class="empty" style="padding:24px">No games in this window.</p>';
    // phones: draw at the screen's own width so 10px text stays 10px (a fixed 440 viewBox shrank it to about 7px)
    const narrow = innerWidth < 760, W = narrow ? Math.max(300, Math.min(440, innerWidth - 56)) : 860, H = (innerWidth < 760 ? 230 : 260) + (COMBO[s] ? 40 : 0), padL = 42, padB = 40, padT = 18, n = gl.length, gk = GHOST[s];
    const padR = mu != null ? (narrow ? 46 : 84) : 8;   // the Vault tag gets its own margin, like the line tag on the left, so no bar or number sits under it
    const vals = gl.map(g => gval(g, s)), ghost = gl.map(g => gk ? g[GI[gk]] : null);
    const max = Math.max(...vals, ...ghost.filter(v => v != null), line, mu || 0) * 1.15 || 1, y = v => padT + (H - padT - padB) * (1 - v / max);
    const bw = Math.min(56, (W - padL - padR) / n * .72), step = (W - padL - padR) / n;
    const full = step >= 46, every = full ? 1 : Math.ceil(30 / step);
    let o = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${SLABEL[s]} by game against the line of ${line}">`;
    for (let i = 0; i <= 4; i++){ const v = max / 1.15 * i / 4; o += `<line class="gl" x1="${padL}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/>` + (Math.abs(y(v) - y(line)) > 12 ? `<text class="ax" x="${padL - 8}" y="${y(v) + 3}" text-anchor="end">${+v.toFixed(1)}</text>` : ''); }
    gl.forEach((g, i) => {
      const v = vals[i], x = padL + step * i + (step - bw) / 2, cx = x + bw / 2, cls = v > line ? 'o' : 'u', opp = GL.teams[g[2]], parts = partsOf(g, s), gv = ghost[i];
      const att = s === 'pts' ? `${g[GI.fgm]}/${g[GI.fga]} FG, ${g[GI['3pm']]}/${g[GI.tpa]} 3PT, ${g[GI.ftm]}/${g[GI.fta]} FT` : gk ? `${v}/${gv} ${SLABEL[gk]}` : parts.length > 1 ? parts.map(k => `${g[GI[k]]} ${SLABEL[k]}`).join(', ') : '';
      o += `<g><title>${gdate(g[0])} ${g[3] ? 'vs' : '@'} ${opp}: ${v} ${SLABEL[s]} in ${g[MIN_I]} min${att ? ` (${att})` : ''}</title>`;
      // attempts ghost sits behind the made bar; its number goes on top when there were misses
      if (gv != null && gv > 0) o += `<rect class="gh" x="${x}" y="${y(gv)}" width="${bw}" height="${Math.max(0, y(0) - y(gv))}" rx="3"/>`;
      if (parts.length > 1){
        let acc = 0;
        parts.forEach((k, j) => {
          const pv = g[GI[k]]; if (!pv) return;
          const top = y(acc + pv), h = Math.max(0, y(acc) - top);
          o += `<rect class="b ${cls}${j}" x="${x}" y="${top}" width="${bw}" height="${h}"/>`;
          const tag = `${pv}${bw >= 34 ? `<tspan class="sk"> ${SEG[k]}</tspan>` : ''}`;
          if (h >= 12 && bw >= 18) o += `<text class="sg${j > 1 ? ' lt' : ''}" x="${cx}" y="${top + h / 2 + 3.5}" text-anchor="middle">${tag}</text>`;
          else if (step - bw >= 16) o += `<text class="so" x="${x + bw + 3}" y="${top + h / 2 + 3.5}">${tag}</text>`;   // too short to hold its number: print it beside the bar
          acc += pv;
        });
      }
      else o += `<rect class="b ${cls}0" x="${x}" y="${y(v)}" width="${bw}" height="${Math.max(2, y(0) - y(v))}" rx="3"/>`;
      // points: the shots behind them, printed inside the base of the bar
      if (s === 'pts' && g[GI.fga] != null && y(0) - y(v) >= 30 && bw >= 30) o += `<text class="sg" x="${cx}" y="${y(0) - 16}" text-anchor="middle">${g[GI.fgm]}/${g[GI.fga]}</text><text class="sg sk" x="${cx}" y="${y(0) - 6}" text-anchor="middle">FG</text>`;
      // keep the made number clear of the ghost label: inside the bar when it is tall enough, else merged into one "made/att" label
      const near = gv != null && gv > v && y(v) - y(gv) < 14, inside = near && y(0) - y(v) >= 16;
      if (gv != null && gv > v) o += `<text class="gt${step < 22 ? ' sm' : ''}" x="${cx}" y="${y(gv) - 5}" text-anchor="middle">${near && !inside ? `<tspan class="gm">${v}</tspan>/` : ''}${gv}${full ? ' att' : ''}</text>`;
      if (!near || inside) o += `<text class="lb${inside ? ' in' : ''}" x="${cx}" y="${inside ? y(v) + 12 : y(v) - 5}" text-anchor="middle">${v}</text>`;
      // date and opponent: full when there is room, else short (4/1, @WSH) and on every k-th bar counting back from the newest
      if ((n - 1 - i) % every === 0) o += full
        ? `<text class="ax" x="${cx}" y="${H - padB + 15}" text-anchor="middle">${gdate(g[0])}</text><text class="ax" x="${cx}" y="${H - padB + 28}" text-anchor="middle">${g[3] ? 'vs' : '@'} ${opp}</text>`
        : `<text class="ax sm" x="${cx}" y="${H - padB + 15}" text-anchor="middle">${mdShort(g[0])}</text><text class="ax sm" x="${cx}" y="${H - padB + 28}" text-anchor="middle">${g[3] ? '' : '@'}${opp}</text>`;
      o += '</g>';
    });
    o += `<line class="ln" x1="${padL}" x2="${W}" y1="${y(line)}" y2="${y(line)}"/><rect class="tg" x="0" y="${y(line) - 9}" width="38" height="18" rx="4"/><text class="tt" x="19" y="${y(line) + 4}" text-anchor="middle">${line}</text>`;
    if (mu != null) o += `<line class="vl" x1="${padL}" x2="${W}" y1="${y(mu)}" y2="${y(mu)}"/><rect class="vtg" x="${W - (narrow ? 42 : 78)}" y="${y(mu) - 9}" width="${narrow ? 40 : 76}" height="18" rx="4"/><text class="vtt" x="${W - (narrow ? 22 : 39)}" y="${y(mu) + 4}" text-anchor="middle">${narrow ? '' : 'Vault '}${fmt(mu)}</text>`;
    return o + '</svg>';
  }
  // chart key: what the ghost, the segments and the inside numbers mean for this stat
  function chartKey(s){
    const gk = GHOST[s], parts = COMBO[s] || (s === 'reb' ? ['dreb', 'oreb'] : null);
    let k = '';
    if (gk) k += `<span><i class="gh"></i>${SLABEL[gk]} (attempts)</span>`;
    if (s === 'pts') k += '<span>Inside bar: FG made/attempted</span>';
    if (parts) k += parts.map((p, j) => `<span><i class="sq o${j}"></i>${SLABEL[p]} (${SEG[p]})</span>`).join('');
    if (s === 'reb' || s === 'ast') k += `<span class="na">Potential ${s === 'reb' ? 'rebounds' : 'assists'}: no source yet</span>`;
    return k;
  }
  // tracker: every candidate on this side (any line) plus "Other book" at the main line
  function trkOpts(x){
    const r = x.r, sideW = x.side === 'o' ? 'Over' : 'Under', kSide = x.side === 'o' ? 'YES' : 'NO';
    const c = (r.all || []).filter(c => c.side === sideW || c.side === kSide).sort((a, b) => (b.line === r.line) - (a.line === r.line) || b.edge - a.edge);
    c.push({venue: 'book', bk: 'Other book', side: sideW, line: r.line, price: '-110', fair: x.fair, edge: null, g: null, other: true});
    return c;
  }
  const isFlat = c => c.venue === 'pickem' && c.price == null;
  const optLbl = c => `${PKN[c.bk] || c.bk} · ${c.venue === 'kalshi' ? `${c.line + .5}+` : c.line}${c.other ? '' : ` · ${isFlat(c) ? 'flat' : c.venue === 'kalshi' ? Math.round(c.price * 100) + '¢' : c.price}`}`;
  const priceStr = (c, unit) => isFlat(c) ? 'flat' : c.venue === 'kalshi' ? (unit === 'am' ? fmtAm(pToAm(c.price)) : String(Math.round(c.price * 100))) : unit === 'am' ? String(c.price) : String(Math.round(amP(c.price) * 1000) / 10);
  function trkInit(x){
    const key = `${x.r.e.p}|${x.r.e.s}|${x.side}`; if (DS.T && DS.T.key === key) return;
    const opts = trkOpts(x); let i = x.best ? opts.indexOf(x.best) : 0; if (i < 0) i = 0;
    const c = opts[i], unit = c.venue === 'kalshi' ? 'pct' : 'am';
    DS.T = {key, i, unit, price: priceStr(c, unit), stake: null};
  }
  function trkCalc(x){
    const T = DS.T, c = trkOpts(x)[T.i], raw = String(T.price).trim();
    let p = null;
    if (isFlat(c)) p = 'flat';
    else if (T.unit === 'pct' || /%|¢/.test(raw)){ const n = parseFloat(raw.replace(/[^0-9.]/g, '')); if (n > 0 && n < 100) p = n / 100; }
    else { const n = amNum(raw.replace(/\s/g, '')); if (n != null && Math.abs(n) >= 100) p = amP(n); }
    if (p == null) return {c, err: T.unit === 'am' ? 'Enter American odds, like -110 or +125.' : 'Enter a chance, like 55.'};
    const cost = p === 'flat' ? PK_BE : c.venue === 'kalshi' ? p + kFee(p) : p, fair = c.fair, edge = fair == null ? null : fair - cost;
    const call = edge == null ? null : x.r.hold ? 'pass' : edge >= EDGE_MIN ? (c.g === 'go' ? 'bet' : 'lean') : 'pass';
    const stake = T.stake != null ? T.stake : call === 'bet' ? Math.max(1, Math.round(pvStakeFor(fair, cost, c))) : 10;
    const inStr = p === 'flat' ? 'flat' : T.unit === 'pct' ? raw.replace(/[^0-9.]/g, '') + '%' : raw;
    return {c, cost, fair, edge, call, stake, inStr, flat: p === 'flat'};
  }
  function trkReadout(x){
    const k = trkCalc(x); if (k.err) return `<p class="muted">${k.err}</p>`;
    const win = k.stake > 0 ? k.stake * (1 - k.cost) / k.cost : null;
    return `<div class="pbx-tro">
      <div><small>Break-even</small><b>${(k.cost * 100).toFixed(1)}%</b><i>${k.flat ? 'flat flex' : fmtAm(pToAm(k.cost))}${k.c.venue === 'kalshi' ? ' with fee' : ''}</i></div>
      <div><small>Vault fair here</small><b class="v">${k.fair == null ? '-' : pc(k.fair)}</b></div>
      <div><small>Edge</small><b class="${k.edge > 0 ? 'pos' : k.edge != null ? 'neg' : ''}">${k.edge == null ? '-' : sgn(k.edge * 100) + '%'}</b></div>
      <div><small>$${k.stake} wins</small><b>${win == null ? '-' : '$' + win.toFixed(2)}</b></div>
      <div><small>Call at your price</small><b>${k.call ? `<span class="pbx-call ${k.call}">${k.call.toUpperCase()}</span>` : '-'}</b></div></div>`;
  }
  function tracker(x){
    trkInit(x); const T = DS.T, r = x.r, opts = trkOpts(x), k = trkCalc(x), mine = pvBets.filter(b => b.k === pvKey(r));
    return `<section class="pbx-card2" id="pbx-trk"><header><h3>Track a bet</h3><small>Saved to My Bets with Vault's fair chance, settled after the game with its closing-line value</small></header>
      <div class="pbx-trk">
        <div class="row">
          <label>Side<span class="seg"><button type="button" data-tside="o" aria-pressed="${x.side === 'o'}">Over</button><button type="button" data-tside="u" aria-pressed="${x.side === 'u'}">Under</button></span></label>
          <label>Where<select id="pbx-tven">${opts.map((c, i) => `<option value="${i}"${i === T.i ? ' selected' : ''}>${esc(optLbl(c))}</option>`).join('')}</select></label>
          <label>Price you got<span class="pr"><input id="pbx-tprice" inputmode="decimal" value="${esc(T.price)}" ${isFlat(opts[T.i]) ? 'readonly' : ''}><span class="seg"><button type="button" data-tunit="am" aria-pressed="${T.unit === 'am'}">-110</button><button type="button" data-tunit="pct" aria-pressed="${T.unit === 'pct'}">55%</button></span></span></label>
          <label>Stake $<input id="pbx-tstake" type="number" min="1" step="1" value="${k.stake || 10}"></label>
        </div>
        <div id="pbx-tro">${trkReadout(x)}</div>
        <div class="act"><span class="muted">American odds as the book showed them (-110, +125) or the chance they imply (55%). Kalshi is in cents and its fee is added for you. Suggested stake follows your Kelly settings on Edges.</span><button type="button" class="btn primary" data-tsave="1">Save to My Bets</button></div>
      </div>
      ${mine.length ? `<div class="pbx-mine">${mine.map(b => `<div><span><b>${esc(b.side)} ${b.venue === 'kalshi' ? (b.line + .5) + '+' : b.line}</b> ${esc(PKN[b.bk] || b.bk)} ${esc(b.price)}</span><span>$${b.stake}</span><span class="${b.edge > 0 ? 'pos' : 'neg'}">${sgn(b.edge * 100)}%</span><span class="pbx-call ${b.call}">${b.call.toUpperCase()}</span><span class="muted">${b.res ? esc(String(b.res.r || b.res)) : 'Open'}</span></div>`).join('')}<a class="linkbtn" href="#mybets" data-go="mybets">All my bets</a></div>` : ''}
    </section>`;
  }
  // ── research cards: teammates, alt lines, opportunity, situations, same-game combos, line history ──
  const HIST = {};                                    // 'YYYY-MM-DD' -> {p: {...}} | 'loading' | null (prop_hist.py on nba-data)
  const IDX = {fga: 14, ftm: 15, fta: 16, tpa: 17};
  function histFor(g, pid, s){
    if (!g || !g.day || typeof H0 === 'undefined' || !H0 || !H0.repo) return {state: 'none'};
    const d0 = g.day, d1 = new Date(Date.parse(d0 + 'T12:00Z') - 864e5).toISOString().slice(0, 10), days = [d1, d0];
    let wait = false;
    for (const d of days) if (!(d in HIST)){
      HIST[d] = 'loading'; wait = true;
      fetch(`${window.PBX_HIST_BASE || `https://raw.githubusercontent.com/${H0.repo}/${H0.branch}/`}snapshots/${d}/prophist.json`, {cache: 'no-store'})
        .then(r => r.ok ? r.json() : null).catch(() => null).then(j => { HIST[d] = j; if (routeOf()) rerender(); });
    } else if (HIST[d] === 'loading') wait = true;
    if (wait) return {state: 'loading'};
    const ser = days.flatMap(d => (HIST[d] && HIST[d].p && HIST[d].p[`${pid}|${s}`]) || []).filter(z => z[0] <= Date.now() / 1000);
    return ser.length ? {state: 'ok', ser} : {state: 'none'};
  }
  function lineChart(ser){
    const W = 300, H = 130, padL = 34, padB = 18, padT = 22, now = Date.now() / 1000;
    const t0 = ser[0][0], t1 = Math.max(Math.min(now, ser[ser.length - 1][0] + 6 * 3600), ser[ser.length - 1][0] + 1);
    const ls = ser.map(z => z[1]), lo = Math.min(...ls) - .5, hi = Math.max(...ls) + .5;
    const x = t => padL + (W - padL - 8) * ((t - t0) / (t1 - t0)), y = v => padT + (H - padT - padB) * (1 - (v - lo) / (hi - lo));
    let d = `M${x(ser[0][0])},${y(ser[0][1])}`; ser.forEach((z, i) => { if (i) d += ` H${x(z[0])} V${y(z[1])}`; }); d += ` H${x(t1)}`;
    const ticks = [...new Set(ls)].sort((a, b) => a - b);
    const lab = ser.length <= 8 ? ser : ser.filter((z, i) => i === 0 || i === ser.length - 1 || z[1] !== ser[i - 1][1]);
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="DraftKings line over time">${ticks.map(v => `<line class="gl" x1="${padL}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/><text class="ax" x="${padL - 5}" y="${y(v) + 3}" text-anchor="end">${v}</text>`).join('')}
      <path class="st" d="${d}"/>${ser.map(z => `<circle class="pt" cx="${x(z[0])}" cy="${y(z[1])}" r="2.6"/>`).join('')}${lab.map(z => `<text class="px" x="${x(z[0])}" y="${y(z[1]) - 6}" text-anchor="middle">${esc(z[2] || '')}</text>`).join('')}
      <text class="ax" x="${padL}" y="${H - 3}">${clock(t0)}</text><text class="ax" x="${W - 4}" y="${H - 3}" text-anchor="end">${clock(t1)} ${TZL}</text></svg>`;
  }
  function mates(r, B){
    const st = statusFromBoard(B);
    const team = Object.entries(PIDX).filter(([id, v]) => v.t === r.team && +id !== +r.e.p).map(([id, v]) => ({id: +id, name: v.p.name, mpg: v.p.min0 || v.p.last_mpg || 0, st: st[+id] || null}));
    const out = id => /out|doubt|inactive/i.test(st[id] || '');
    return team.sort((a, b) => ((out(b.id) && b.mpg >= 15) - (out(a.id) && a.mpg >= 15)) || b.mpg - a.mpg).filter((m, i) => i < 10 || out(m.id));
  }
  function mateSplit(all, mid, onTeam){              // his games with and without teammate mid: same day + same opponent = same team game
    const T = (GL.players[mid] || []).filter(z => !z[4]), td = new Map(T.map(z => [z[0], z[2]]));
    const w = all.filter(g => td.get(g[0]) === g[2]);
    const span = {}; w.forEach(g => { const b = span[g[1]] = span[g[1]] || [g[0], g[0]]; b[0] = Math.min(b[0], g[0]); b[1] = Math.max(b[1], g[0]); });
    const wo = all.filter(g => { const b = span[g[1]]; if (!b || td.has(g[0])) return false; return g[0] >= b[0] && (g[0] <= b[1] || (g[1] === GL.current_season && onTeam)); });
    return {w, wo};
  }
  function hitsFrom(all, s, line, side, opp){
    const ok = g => side === 'o' ? gval(g, s) > line : gval(g, s) < line;
    const rate = gl => gl.length ? {n: gl.length, h: gl.filter(ok).length, pct: gl.filter(ok).length / gl.length} : null;
    return Object.fromEntries(WIN.map(([k]) => [k, rate(winGl(all, k, opp))]));
  }
  // ── game filters: result and the pre-game line (data/game_ctx.json, build_game_ctx.py), home/away and rest (the game log) ──
  let CTX;                                            // undefined = not asked yet, 'loading', null = unavailable, else {g: {team: {day: [pts, opp, spread]}}}
  function ctxGet(){
    if (CTX !== undefined) return CTX === 'loading' ? null : CTX;
    CTX = 'loading';
    const raw = `https://raw.githubusercontent.com/${typeof H0 !== 'undefined' && H0 && H0.repo ? H0.repo : 'Putput12-JP/Vault-Fantasy'}/main/nba/data/game_ctx.json`;
    fetch('data/game_ctx.json', {cache: 'no-store'}).then(r => r.ok ? r.json() : Promise.reject()).catch(() => fetch(raw, {cache: 'no-store'}).then(r => r.ok ? r.json() : null).catch(() => null))
      .then(j => { CTX = j && j.g ? j : null; if (routeOf()) rerender(); });
    return null;
  }
  // one game from his team's side: {pts, opp, m (margin), sp (his team's spread, negative = favoured, null when no line is stored)}
  function ctxOf(g){
    const c = CTX && CTX !== 'loading' && CTX.g[GL.teams[g[2]]], z = c && c[g[0]];
    return z ? {pts: z[1], opp: z[0], m: z[1] - z[0], sp: z[2] == null ? null : -z[2]} : null;
  }
  // [key, group, label, test(game, ctx, rest days), uses game_ctx]; `tonight` marks the ones that describe tonight's game
  const GF = [
    ['won', 'Result (known after the game)', 'Team won', (g, c) => c && c.m > 0, 1], ['lost', 'Result (known after the game)', 'Team lost', (g, c) => c && c.m < 0, 1],
    ['blow', 'Result (known after the game)', 'Blowout (won or lost by 15+)', (g, c) => c && Math.abs(c.m) >= 15, 1], ['close', 'Result (known after the game)', 'Close finish (within 5)', (g, c) => c && Math.abs(c.m) <= 5, 1],
    ['fav', 'Pre-game line', 'Favored', (g, c) => c && c.sp != null && c.sp < 0, 1], ['dog', 'Pre-game line', 'Underdog', (g, c) => c && c.sp != null && c.sp > 0, 1],
    ['fav7', 'Pre-game line', 'Favored by 7+', (g, c) => c && c.sp != null && c.sp <= -7, 1], ['dog7', 'Pre-game line', 'Underdog by 7+', (g, c) => c && c.sp != null && c.sp >= 7, 1],
    ['tight', 'Pre-game line', 'Spread within 4.5', (g, c) => c && c.sp != null && Math.abs(c.sp) <= 4.5, 1],
    ['home', 'Venue', 'Home', g => g[3] === 1, 0], ['away', 'Venue', 'Away', g => g[3] === 0, 0],
    ['b2b', 'Rest', 'Back-to-back', (g, c, rd) => rd === 0, 0], ['r1', 'Rest', '1 day rest', (g, c, rd) => rd === 1, 0], ['r2', 'Rest', '2+ days rest', (g, c, rd) => rd != null && rd >= 2, 0]
  ];
  function gfTonight(k, sp, home, rest){
    return {fav: sp != null && sp < 0, dog: sp != null && sp > 0, fav7: sp != null && sp <= -7, dog7: sp != null && sp >= 7, tight: sp != null && Math.abs(sp) <= 4.5,
      home: home === true, away: home === false, b2b: rest === 0, r1: rest === 1, r2: rest != null && rest >= 2}[k] || false;
  }
  const pcell = v => v == null ? '<span class="muted">-</span>' : `<span class="pbx-hc ${hcls({pct: v})}">${Math.round(v * 100)}%</span>`;
  function ladder(r, side, all){
    const lines = new Set([r.line]); r.kal.forEach(k => lines.add(k.line)); r.books.forEach(b => lines.add(b.line));
    for (const d of [-2, -1, 1, 2]) if (r.line + d > 0) lines.add(r.line + d);
    const sW = side === 'o' ? 'Over' : 'Under', kS = side === 'o' ? 'YES' : 'NO';
    return [...lines].sort((a, b) => a - b).map(L => {
      const ok = g => side === 'o' ? gval(g, r.e.s) > L : gval(g, r.e.s) < L, rate = a => a.length ? a.filter(ok).length / a.length : null;
      const c = (r.all || []).filter(c => c.line === L && (c.side === sW || c.side === kS) && c.venue !== 'pickem' && c.edge != null).sort((a, b) => b.edge - a.edge)[0] || null;
      return {L, l10: rate(all.slice(0, 10)), l20: rate(all.slice(0, 20)), s0: rate(all.filter(g => g[1] === GL.current_season)), both: rate(all), c};
    });
  }
  function spark(vals, n5){
    const W = 160, H = 44, n = vals.length; if (!n) return ''; const mx = Math.max(...vals, 1), bw = W / n;
    return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${vals.map((v, i) => `<rect class="${i >= n - n5 ? 'r5' : ''}" x="${i * bw + 1}" y="${H - v / mx * (H - 2)}" width="${Math.max(1, bw - 2)}" height="${v / mx * (H - 2)}" rx="1.5"/>`).join('')}</svg>`;
  }
  // ── prop signals: fixed checks, each with this season's record (data/prop_signals.json, build_prop_signals.py) ──
  // The definitions below must match build_prop_signals.py exactly: that file rebuilt the records these checks are shown with.
  const PSIG = /*PSIG*/null;
  const SIG_FWD = '2026-11-08';                       // forward test: tiers frozen on Nov 8 2026; nights from here on are out of sample
  const SIG_LEVEL = [0.0345, 0.0683, 0.1223], SIG_OPP = {pts: 'fga', pra: 'fga', pr: 'fga', pa: 'fga', fgm: 'fga', '3pm': 'tpa'};
  const SIG_RANKED = ['pts', 'reb', 'ast', '3pm', 'stl', 'blk', 'tov', 'pra', 'pr', 'pa', 'ra', 'sb'];
  const SIG_COUNTED = ['market', 'matchup', 'minutes', 'opp', 'form'];
  const SIG_NAME = {model: 'Vault model', market: 'Market, no vig', matchup: 'Matchup', minutes: 'Minutes', opp: 'Shot volume', form: 'Form, last 10', move: 'Line move'};
  const TIER = {strong: ['Strong', 'Model level 3-4, three or more checks agree, none against'], lean: ['Lean', 'Two or more checks agree, more for than against'],
    split: ['Split', 'Checks are mixed, or nothing beyond the model'], against: ['Against', 'More checks disagree with the model than agree']};
  const sigLevel = p => 1 + SIG_LEVEL.filter(c => Math.abs(p - .5) >= c).length;
  function sigTier(lv, kf, ka){ return ka > kf ? 'against' : lv >= 3 && kf >= 3 && ka === 0 ? 'strong' : kf >= 2 && kf > ka ? 'lean' : 'split'; }
  // {name: {side: 'O'|'U'|null, why}} for tonight's prop, from what the page already holds
  function sigOf(x, all0, hist){
    // each check: side 'O' | 'U' | null, v = the short reading for its tile, why = the full sentence (tooltip)
    const r = x.r, s = r.e.s, L = r.line, out = {};
    if (r.pm == null) return null;
    const ps = r.pm > .5 ? r.pm : 1 - r.pm;
    out.model = {side: r.pm > .5 ? 'O' : 'U', v: `${pc(ps)} · Level ${sigLevel(r.pm)}`, why: `${pc(ps)} on the ${r.pm > .5 ? 'over' : 'under'}, level ${sigLevel(r.pm)}`};
    if (r.mkt == null) out.market = {side: null, v: 'No price', why: 'No no-vig market price'};
    else { const mp = r.mkt > .5 ? r.mkt : 1 - r.mkt, sd = Math.abs(r.mkt - .5) < .02 ? null : r.mkt > .5 ? 'O' : 'U';
      out.market = {side: sd, v: sd ? pc(mp) : 'Even', why: sd ? `${pc(mp)} on the ${sd === 'O' ? 'over' : 'under'}` : `${pc(r.mkt)} over, within 2 points of even`}; }
    const rk = ranks(), z = rk && x.grp && SIG_RANKED.includes(s) ? rk[`${x.opp}|${x.grp}|${s}`] : null, gw = x.grp === 'G' ? 'guards' : x.grp === 'C' ? 'centers' : 'forwards';
    out.matchup = !z || z[2] < 5 ? {side: null, v: 'Not ranked', why: 'Not ranked for this stat yet'}
      : {side: z[0] >= 21 ? 'O' : z[0] <= 10 ? 'U' : null, v: `${x.opp} ${ordinal(z[0])}`, why: `${x.opp} ${ordinal(z[0])} vs ${gw} (${fmt(z[1])} a game). 1st allows the fewest.`};
    const l5 = all0.slice(0, 5);
    if (r.min != null && l5.length === 5){ const a = l5.reduce((t, g) => t + g[MIN_I], 0) / 5, d = r.min - a;
      out.minutes = {side: d >= 2 ? 'O' : d <= -2 ? 'U' : null, v: `${d >= 0 ? '+' : ''}${fmt(d)} min`, why: `Projected ${fmt(r.min)} vs ${fmt(a)} over his last 5`}; }
    else out.minutes = {side: null, v: 'Too few games', why: 'Needs 5 recent games'};
    const os = SIG_OPP[s];
    if (!os) out.opp = {side: null, v: 'Not scored', why: s === 'reb' || s === 'ast' || s === 'ra' ? `No potential ${s === 'ast' ? 'assists' : s === 'reb' ? 'rebounds' : 'rebounds or assists'} source yet` : 'Not scored for this stat'};
    else if (all0.length < 20) out.opp = {side: null, v: 'Too few games', why: 'Needs 20 games'};
    else { const a = all0.slice(0, 5).reduce((t, g) => t + g[GI[os]], 0) / 5, b = all0.slice(5, 20).reduce((t, g) => t + g[GI[os]], 0) / 15, pct = b > 0 ? (a / b - 1) * 100 : null;
      out.opp = pct == null ? {side: null, v: 'No attempts', why: 'No attempts to compare'}
        : {side: a >= b * 1.1 ? 'O' : a <= b * .9 ? 'U' : null, v: `${SLABEL[os]} ${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`, why: `${SLABEL[os]} ${fmt(a)} a game over his last 5 vs ${fmt(b)} the 15 before`}; }
    const l10 = all0.slice(0, 10);
    if (l10.length === 10){ const h = l10.filter(g => gval(g, s) > L).length; out.form = {side: h >= 7 ? 'O' : h <= 3 ? 'U' : null, v: `${h} of 10 over`, why: `Over ${L} in ${h} of his last 10`}; }
    else out.form = {side: null, v: 'Too few games', why: 'Needs 10 games'};
    const ser = hist && hist.state === 'ok' ? hist.ser : null, f0 = ser ? ser[0][1] : null;
    out.move = f0 == null ? {side: null, v: 'No history', why: 'No DraftKings history for this prop'} : f0 === L ? {side: null, v: `Flat at ${L}`, why: `DraftKings line unchanged at ${L}`}
      : {side: L > f0 ? 'O' : 'U', v: `${f0} → ${L}`, why: `DraftKings line moved from ${f0} to ${L}`};
    const ms = out.model.side, kf = SIG_COUNTED.filter(k => out[k].side === ms).length, ka = SIG_COUNTED.filter(k => out[k].side && out[k].side !== ms).length;
    return {c: out, ms, kf, ka, lv: sigLevel(r.pm), tier: sigTier(sigLevel(r.pm), kf, ka)};
  }
  // records by how many counted checks agree with the model (any number against), from the per-bucket table
  function agreeRec(k){ if (!PSIG || !PSIG.agree) return null; return sumRec(Object.entries(PSIG.agree).filter(([b]) => +b.split('|')[0] === k).map(([, rc]) => rc)); }
  // record text: rec = [n, wins, market-expected wins, se, priced n, units]
  const recHit = rc => rc && rc[0] ? `${rc[1]}-${rc[0] - rc[1]} <i>${Math.round(rc[1] / rc[0] * 1000) / 10}%</i>` : '-';
  const recDiff = rc => { if (!rc || !rc[0]) return null; const d = (rc[1] - rc[2]) / rc[0] * 100; return d; };
  const recRoi = rc => rc && rc[4] ? rc[5] / rc[4] * 100 : null;
  const sgnPt = v => v == null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}`;
  function sumRec(list){ const o = [0, 0, 0, null, 0, 0]; list.forEach(rc => { if (!rc) return; o[0] += rc[0]; o[1] += rc[1]; o[2] += rc[2]; o[4] += rc[4]; o[5] += rc[5]; }); return o; }
  function tierRec(tier, fwd){ if (!PSIG || !PSIG.tier_days) return null; return sumRec(Object.entries(PSIG.tier_days).filter(([d]) => fwd ? d >= SIG_FWD : d < SIG_FWD).map(([, t]) => t[tier])); }
  function sigCard(x, all0, hist, side){
    const S = sigOf(x, all0, hist);
    const head = `<header><h3>Prop signals</h3>${S ? `<small>Model side: ${S.ms === 'O' ? 'Over' : 'Under'}</small>` : ''}</header>`;
    if (!S) return `<section class="pbx-card2 pbx-sig">${head}<p class="note">No model price on this prop, so there is nothing to check.</p></section>`;
    if (!PSIG) return `<section class="pbx-card2 pbx-sig">${head}<p class="note">Signal records are not in this build.</p></section>`;
    const sw = S.ms === 'O' ? 'over' : 'under', mine = (side === 'o' ? 'O' : 'U') === S.ms, T = TIER[S.tier], tr = PSIG.tier[S.tier];
    const hit = rc => rc && rc[0] ? `${(rc[1] / rc[0] * 100).toFixed(1)}%` : '-', roiT = rc => { const v = recRoi(rc); return v == null ? '-' : `${sgnPt(v)}%`; }, cls = v => v > 0 ? 'pos' : v < 0 ? 'neg' : '';
    // meter: one segment per counted check, agreeing first
    const seg = SIG_COUNTED.map(k => S.c[k].side == null ? 'n' : S.c[k].side === S.ms ? 'a' : 'd').sort((a, b) => 'adn'.indexOf(a) - 'adn'.indexOf(b));
    const ladder = [2, 3, 4, 5].map(k => { const rc = agreeRec(k), roi = recRoi(rc);
      return `<div class="${S.kf === k ? 'on' : ''}" title="${rc && rc[0] ? `${rc[1]}-${rc[0] - rc[1]}, market ${hit([rc[0], rc[2]])}, ROI on ${rc[4]} priced` : ''}"><small>${k} agree</small><b>${hit(rc)}</b><i class="${cls(roi)}">${roiT(rc)}</i><em>${rc ? rc[0].toLocaleString() : 0}</em></div>`; }).join('');
    const tile = k => { const c = S.c[k], rc = c.side && PSIG.sig[k] ? PSIG.sig[k][c.side === 'O' ? 'o' : 'u'] : null, lv = k === 'model' ? PSIG.level[String(S.lv)] : null, d = recDiff(lv || rc);
      const st = k === 'model' ? 'm' : k === 'move' ? 'ctx' : !c.side ? 'n' : c.side === S.ms ? 'a' : 'd';
      return `<div class="pbx-st ${st}" title="${esc(c.why)}"><div class="t"><small>${SIG_NAME[k]}</small>${c.side ? `<span>${c.side === 'O' ? 'Over' : 'Under'}</span>` : ''}</div><b>${esc(c.v)}</b>${d != null ? `<i class="${cls(d)}">${sgnPt(d)} pts vs market</i>` : `<i>${k === 'move' ? 'Context only' : 'No call'}</i>`}</div>`; };
    return `<section class="pbx-card2 pbx-sig">${head}
      <div class="pbx-sv ${S.tier}">
        <div class="h"><b>${T[0]}</b><span>${sw}${mine ? '' : ` · you are viewing the ${side === 'o' ? 'over' : 'under'}`}</span></div>
        <div class="pbx-mtr" aria-label="${S.kf} of 5 checks agree, ${S.ka} against">${seg.map(z => `<i class="${z}"></i>`).join('')}<span>${S.kf} of 5 agree${S.ka ? ` · ${S.ka} against` : ''}</span></div>
        <p class="hl">Props like this hit <b>${hit(tr)}</b> <span>(market ${tr && tr[0] ? hit([tr[0], tr[2]]) : '-'})</span> · ROI <b class="${cls(recRoi(tr))}">${roiT(tr)}</b></p>
      </div>
      <div class="pbx-lad">${ladder}</div>
      <div class="pbx-sg">${['model', 'market', 'minutes', 'form', 'opp', 'matchup', 'move'].map(tile).join('')}</div>
      <p class="note">This season, ${PSIG.n.toLocaleString()} props${PSIG.through ? ` through ${PSIG.through.slice(5).replace('-', '/')}` : ''}. "vs market" is how much more often that side won than the no-vig price expected. ROI is after the book's cut. Rebuilt in-sample; forward test from ${SIG_FWD.slice(5).replace('-', '/')}. <a href="#track" data-go="track">Full record</a></p>
    </section>`;
  }
  // Track Record card: each tier rebuilt (before the freeze) and forward, plus every check's record by side
  function trackCard(el, stat){
    if (!el) return;
    if (!PSIG){ el.innerHTML = '<p class="hint">Signal records are not in this build.</p>'; return; }
    const row = (lbl, rc) => { const d = recDiff(rc), roi = recRoi(rc); return `<tr><td class="l">${lbl}</td><td class="num">${rc && rc[0] ? rc[0].toLocaleString() : 0}</td><td class="num">${recHit(rc)}</td><td class="num">${rc && rc[0] ? Math.round(rc[2] / rc[0] * 1000) / 10 + '%' : '-'}</td><td class="num"><span class="${d > 0 ? 'pos' : d < 0 ? 'neg' : ''}">${sgnPt(d)}</span></td><td class="num"><span class="${roi > 0 ? 'pos' : roi < 0 ? 'neg' : ''}">${roi == null ? '-' : sgnPt(roi) + '%'}</span>${rc && rc[4] ? ` <small>${rc[4].toLocaleString()}</small>` : ''}</td></tr>`; };
    const th = '<thead><tr><th class="l"></th><th>Props</th><th>Won-lost</th><th>Market</th><th>vs market</th><th>ROI · priced</th></tr></thead>';
    const tiers = ['strong', 'lean', 'split', 'against'];
    const fw = tiers.map(t => tierRec(t, true)), any = fw.some(rc => rc && rc[0]);
    const st = tierRec('strong', true);
    if (stat) stat.textContent = st && st[0] ? `Strong, forward: ${st[1]}-${st[0] - st[1]}${recRoi(st) != null ? `, ROI ${sgnPt(recRoi(st))}%` : ''}` : 'Strong, rebuilt: ' + (() => { const b = tierRec('strong', false); return b && b[0] ? `${b[1]}-${b[0] - b[1]}, ROI ${sgnPt(recRoi(b))}% (in-sample)` : 'no props'; })();
    el.innerHTML = `<p class="hint tplain">Every prop on the board gets the same fixed checks (model, market, matchup, minutes, opportunity, form; the line move is context). The verdict counts how many back the model's side. Records use the model's side at the last look before tip, against the no-vig market's chance and at the best stored price. Tiers were set on ${PSIG.first.slice(5).replace('-', '/')} to ${PSIG.through.slice(5).replace('-', '/')} data, so that part is in-sample. The forward test started ${SIG_FWD.slice(5).replace('-', '/')}.</p>
      <h3 class="sim-h">Forward, from ${SIG_FWD.slice(5).replace('-', '/')} (the real test)</h3>
      ${any ? `<div class="tablewrap"><table class="ht tsim">${th}<tbody>${tiers.map((t, i) => row(TIER[t][0], fw[i])).join('')}</tbody></table></div>` : '<p class="hint">No settled props since the freeze yet. The first night lands after tonight\'s games settle.</p>'}
      <h3 class="sim-h">Rebuilt, ${PSIG.first.slice(5).replace('-', '/')} to ${PSIG.through < SIG_FWD ? PSIG.through.slice(5).replace('-', '/') : 'the freeze'} (in-sample)</h3>
      <div class="tablewrap"><table class="ht tsim">${th}<tbody>${tiers.map(t => row(`${TIER[t][0]}<small>${TIER[t][1]}</small>`, tierRec(t, false))).join('')}</tbody></table></div>
      <h3 class="sim-h">By how many checks agree with the model (whole season)</h3>
      <div class="tablewrap"><table class="ht tsim">${th}<tbody>${[0, 1, 2, 3, 4, 5].map(k => row(`${k} of 5 agree`, agreeRec(k))).join('')}</tbody></table></div>
      <h3 class="sim-h">Each check, by the side it points to (whole season)</h3>
      <div class="tablewrap"><table class="ht tsim">${th}<tbody>${['model', ...SIG_COUNTED, 'move'].flatMap(k => PSIG.sig[k] ? [['o', 'Over'], ['u', 'Under']].map(([sd, l]) => row(`${SIG_NAME[k]} · ${l}${k === 'move' ? ' <small>context only</small>' : ''}`, PSIG.sig[k][sd])) : []).join('')}</tbody></table></div>
      <h3 class="sim-h">Model level (Props Sim confidence)</h3>
      <div class="tablewrap"><table class="ht tsim">${th}<tbody>${Object.entries(PSIG.level).map(([k, rc]) => row('Level ' + k, rc)).join('')}</tbody></table></div>
      <p class="hint">vs market: the side's win rate minus the no-vig market's average chance for it, in points. ROI: 1 unit at the best stored price on the model's side; the count beside it is how many props had a stored price. Pushes are left out. Checks share props, so their records are not independent.</p>`;
  }

  function detail(B, rt){
    const root = $('pbx-root'), all = build(B);
    all.forEach(pick);
    const x = all.find(z => z.r.e.p === rt.pid && z.r.e.s === rt.s && z.side === rt.side) || all.find(z => z.r.e.p === rt.pid && z.r.e.s === rt.s);
    if (!x){ root.innerHTML = `<button type="button" class="pbx-back" data-back="1">← Props</button><section class="pbx-card2"><p class="empty" style="padding:24px">This prop is not on the board now. The game may have tipped, or the line was pulled.</p></section>`; return; }
    const r = x.r, side = x.side, g = x.g, s = r.e.s, X = PIDX[r.e.p], all0 = (r._logs || (r._logs = logsOf(r))).all.filter(z => !z[4]);
    const ms = mates(r, B); if (DS.mate && !ms.some(m => m.id === DS.mate.id)) DS.mate = null;
    const restD = new Map(all0.map((z, i) => { const n = all0[i + 1]; return [z, n && n[1] === z[1] ? z[0] - n[0] - 1 : null]; }));
    const cx = ctxGet(), gfDef = DS.gf && GF.find(f => f[0] === DS.gf), gfOk = f => z => !!f[3](z, ctxOf(z), restD.get(z));
    const logs0 = DS.mate ? mateSplit(all0, DS.mate.id, true)[DS.mate.mode] : all0;
    const logs = gfDef ? logs0.filter(gfOk(gfDef)) : logs0, h = hitsFrom(logs, s, r.line, side, x.opp);
    const mrows = ms.map(m => { const sp = mateSplit(all0, m.id, true), ok = g2 => side === 'o' ? gval(g2, s) > r.line : gval(g2, s) < r.line, rt2 = a => a.length ? a.filter(ok).length / a.length : null;
      return {m, nw: sp.w.length, nwo: sp.wo.length, aw: avg(sp.w.map(z => gval(z, s))), awo: avg(sp.wo.map(z => gval(z, s))), hw: rt2(sp.w), hwo: rt2(sp.wo), mw: avg(sp.w.map(z => z[MIN_I])), mwo: avg(sp.wo.map(z => z[MIN_I]))}; })
      .filter(z => z.nwo > 0 || /out|doubt|inactive/i.test(z.m.st || ''));
    const lad = ladder(r, side, all0), g15 = all0.slice(0, 15).reverse();
    const tday = g ? Math.floor(Date.parse(g.day + 'T00:00Z') / 864e5) : null, restT = tday != null && all0[0] ? tday - all0[0][0] - 1 : null, homeT = g ? r.team === g.home : null;
    const spT = g && g.spread != null ? (r.team === g.home ? g.spread : -g.spread) : null;
    const gfN = GF.map(f => ({f, n: f[4] && !cx ? null : logs0.filter(gfOk(f)).length, now: gfTonight(f[0], spT, homeT, restT)}));
    const okS = g2 => side === 'o' ? gval(g2, s) > r.line : gval(g2, s) < r.line, restOf = i => { const n = all0[i + 1]; return n && n[1] === all0[i][1] ? all0[i][0] - n[0] - 1 : null; };
    const sit = (lbl, f, now) => { const a = all0.filter(f); return {lbl, n: a.length, min: avg(a.map(z => z[MIN_I])), avg: avg(a.map(z => gval(z, s))), hit: a.length ? a.filter(okS).length / a.length : null, now}; };
    const sits = [sit('Home', z => z[3] === 1, homeT === true), sit('Away', z => z[3] === 0, homeT === false),
      sit('Back-to-back (0 days rest)', z => restOf(all0.indexOf(z)) === 0, restT === 0), sit('1 day rest', z => restOf(all0.indexOf(z)) === 1, restT === 1), sit('2+ days rest', z => restOf(all0.indexOf(z)) >= 2, restT != null && restT >= 2)]
      .concat(cx ? GF.filter(f => f[4]).map(f => sit(f[2], gfOk(f), gfTonight(f[0], spT, homeT, restT))) : []);
    const hist = histFor(g, r.e.p, s);
    pf.rows = [r];                                    // Watch in the header goes through the shared handler, which looks rows up here
    const stats = STATS.map(z => z[0]).filter(k => all.some(z => z.r.e.p === r.e.p && z.r.e.s === k));
    const wg = winGl(logs, DS.win, x.opp), sv = i => { const a = wg.map(z => z[i]); return DS.med ? med(a) : avg(a); };
    const fgp = (() => { const m = wg.reduce((a, z) => a + z[GI.fgm], 0), A = wg.reduce((a, z) => a + z[GI.fga], 0); return A ? m / A : null; })();
    const hw = h[DS.win], wl = Object.fromEntries(WIN);
    const pmS = r.pm == null ? null : side === 'o' ? r.pm : 1 - r.pm, mkS = r.mkt == null ? null : side === 'o' ? r.mkt : 1 - r.mkt;
    const other = all.find(z => z.r === r && z.side !== side);
    const best = x.best, bestTxt = best ? `${PKN[best.bk] || best.bk} ${priceTxt(best)}` : x.pk ? `${PKN[x.pk.bk] || x.pk.bk} ${priceTxt(x.pk)}` : null;
    const verdict = r.hold ? `<b>Held.</b> ${esc(r.hold.why || r.hold.label || '')}`
      : x.gate === 'go' ? `<b>Passes the gates.</b> ${esc(bestTxt)} beats Vault's fair ${pc(x.fair)} by ${sgn(x.edge * 100)} points after fees.`
      : x.edge != null && x.edge > 0 ? `<b>Thin edge, not a play.</b> ${esc(bestTxt)} is ${sgn(x.edge * 100)} points over fair but does not clear every gate.`
      : x.edge != null ? `<b>No edge on the ${side === 'o' ? 'over' : 'under'}.</b> The best price, ${esc(bestTxt)}, costs more than Vault's fair ${pc(x.fair)}.${other && other.edge > 0 ? ` The ${side === 'o' ? 'under' : 'over'} shows ${sgn(other.edge * 100)}.` : ''}`
      : '<b>No priced market on this side.</b>';
    const bld = r.build, adj = bld && r.min > 0 ? PARTS.concat('bias').filter(k => bld[k] != null && Math.abs(bld[k]) >= .005) : [], amax = Math.max(.5, ...adj.map(k => Math.abs(bld[k])));
    const ev = x.sc.ev;
    const main = r.books.find(b => b.bk === r.lineFrom) || r.books[0];
    const rk = ranks(), oppRows = ['pts', 'reb', 'ast', '3pm', 'pra', 'stl', 'blk'].map(k => [k, rk && x.grp ? rk[`${x.opp}|${x.grp}|${k}`] : null]).filter(z => z[1]);
    const stB = statusFromBoard(B), injs = Object.entries(stB).filter(([pid, st]) => /out|doubt|quest|inactive/i.test(st) && PIDX[pid] && g && (PIDX[pid].t === g.away || PIDX[pid].t === g.home))
      .map(([pid, st]) => [PIDX[pid].p.name, PIDX[pid].t, st]).sort((a, b) => a[1].localeCompare(b[1]));
    const grpW = x.grp === 'G' ? 'guards' : x.grp === 'C' ? 'centers' : 'forwards';
    const pkey = pvKey(r), pw = pvW[pkey], watching = watched(r, side), both = watching && !pw.side;
    const kw = g && g.mk && g.mk.kalshi && g.mk.kalshi.win;
    root.innerHTML = `
    <button type="button" class="pbx-back" data-back="1">← Props</button>
    <div class="pbx-detail"><div class="pbx-main">
      <section class="pbx-card2">
        <div class="pbx-dh">${face(x)}
          <div class="id">${g ? `<span class="pbx-mchip">${lgImg(g.away, 14)}${g.away} @ ${g.home}${lgImg(g.home, 14)}${etFmt(g.tip, {weekday: 'short'})} ${clock(g.tip)} ${TZL}</span>` : ''}
            <h2>${esc(r.name)} <small>${esc(r.team)}${x.grp ? ` · ${x.grp === 'G' ? 'Guard' : x.grp === 'C' ? 'Center' : 'Forward'}` : ''}${r.lu === 's' ? ' · Starter' : ''}</small> ${injTag(r)}</h2></div>
          <div class="acts">
            <span class="seg"><button type="button" data-dside="o" aria-pressed="${side === 'o'}">Over</button><button type="button" data-dside="u" aria-pressed="${side === 'u'}">Under</button></span>
            <span class="pbx-sel ${side}">${side === 'o' ? 'Over' : 'Under'} ${r.line} ${best ? bkChip(best.bk) + `<b>${esc(priceTxt(best))}</b>` : ''}</span>
            ${r.kal.length > 1 ? `<select class="pbx-alt" aria-label="Kalshi alt lines"><option>Alt lines (${r.kal.length})</option>${r.kal.map(k => `<option>${k.line + .5}+: Kalshi ${Math.round(k.ask * 100)}¢ · fair ${pc(k.fair)}</option>`).join('')}</select>` : ''}
            <button class="pv-star" type="button" data-pbstar="${esc(pkey)}" data-pbside="${side}" aria-pressed="${watching}"${both ? ` title="Saved before watches kept a side. Tap to keep only the ${side === 'o' ? 'over' : 'under'}."` : ''}>${both ? '★ Watching both' : watching ? '★ Watching' : '☆ Watch'}</button>
            <button type="button" class="btn primary" data-totrk="1">Track a bet ↓</button>
          </div></div>
        <div class="pbx-tabs" id="pbx-stabs">${stats.map(k => `<button type="button" data-ds="${k}" class="${k === s ? 'on' : ''}">${esc(SLABEL[k])}</button>`).join('')}<span class="pbx-ul"></span></div>
        <div class="pbx-wins"><span class="seg">${WIN.map(([k, l]) => `<button type="button" data-win="${k}" aria-pressed="${DS.win === k}">${l}</button>`).join('')}</span>
          <select id="pbx-mate" class="pbx-alt" aria-label="Teammate filter"><option value="">All teammates</option>${ms.map(m => `<option value="w|${m.id}"${DS.mate && DS.mate.id === m.id && DS.mate.mode === 'w' ? ' selected' : ''}>With ${esc(m.name)}</option><option value="wo|${m.id}"${DS.mate && DS.mate.id === m.id && DS.mate.mode === 'wo' ? ' selected' : ''}>Without ${esc(m.name)}${m.st ? ` (${esc(m.st.toLowerCase())} tonight)` : ''}</option>`).join('')}</select>
          <select id="pbx-gf" class="pbx-alt" aria-label="Game filter"><option value="">Any game</option>${[...new Set(GF.map(f => f[1]))].map(grp => `<optgroup label="${grp}">${gfN.filter(z => z.f[1] === grp).map(z => `<option value="${z.f[0]}"${DS.gf === z.f[0] ? ' selected' : ''}${z.n === 0 ? ' disabled' : ''}>${z.f[2]}${z.n != null ? ` (${z.n})` : ''}${z.now ? ' · tonight' : ''}</option>`).join('')}</optgroup>`).join('')}</select></div>
        <div class="pbx-hs"><div><small>${wl[DS.win]} · ${side === 'o' ? 'over' : 'under'} ${r.line}${DS.mate ? `<span class="pbx-mf">${DS.mate.mode === 'w' ? 'With' : 'Without'} ${esc((ms.find(m => m.id === DS.mate.id) || {}).name || '')}<button type="button" data-mclear="1" aria-label="Clear teammate filter">×</button></span>` : ''}${gfDef ? `<span class="pbx-mf">${gfDef[2]}${gfDef[4] && !cx ? ' (loading)' : ''}<button type="button" data-gclear="1" aria-label="Clear game filter">×</button></span>` : ''}</small><b class="${hw && hw.pct > .5 ? 'pos' : hw && hw.pct < .5 ? 'neg' : ''}">${hw ? Math.round(hw.pct * 100) + '%' : '-'}<i>${hw ? `${hw.h} of ${hw.n}` : ''}</i></b></div>
          ${WIN.filter(w => w[0] !== DS.win).map(([k, l]) => `<div class="w"><small>${l}</small><b class="${h[k] && h[k].pct > .5 ? 'pos' : h[k] && h[k].pct < .5 ? 'neg' : ''}">${h[k] ? Math.round(h[k].pct * 100) + '%' : '-'}</b></div>`).join('')}</div>
        <div class="pbx-chart">${chart(wg, s, r.line, r.mu)}</div>
        <div class="pbx-ck"><span><i class="ln"></i>Tonight's line ${r.line}</span>${r.mu != null ? `<span><i class="vl"></i>Vault projection ${fmt(r.mu)}</span>` : ''}<span><i class="sq o"></i>Over</span><span><i class="sq u"></i>Under</span>${chartKey(s)}</div>
        <div class="pbx-suph"><h4>Supporting stats <small>${wg.length} games</small></h4><span class="seg"><button type="button" data-med="0" aria-pressed="${!DS.med}">Average</button><button type="button" data-med="1" aria-pressed="${DS.med}">Median</button></span></div>
        <div class="pbx-sup">
          <div><small>Minutes</small><b>${f1(sv(MIN_I))}${r.min ? ` <i>proj ${fmt(r.min)}</i>` : ''}</b></div>
          <div><small>${esc(SLABEL[s])}</small><b>${f1(DS.med ? med(wg.map(z => gval(z, s))) : avg(wg.map(z => gval(z, s))))}</b></div>
          <div><small>Field goals</small><b>${f1(sv(GI.fgm))}/${f1(sv(GI.fga))} <i>${fgp == null ? '' : Math.round(fgp * 100) + '%'}</i></b></div>
          <div><small>3PT att.</small><b>${f1(sv(GI.tpa))} <i>${f1(sv(GI['3pm']))} made</i></b></div>
          <div><small>Free throws</small><b>${f1(sv(GI.ftm))}/${f1(sv(GI.fta))}</b></div>
          <div><small>Fouls</small><b>${f1(sv(GI.pf))}</b></div>
        </div>
      </section>

      <section class="pbx-card2 vault"><header><h3>Vault model</h3><small>Only Vault has this</small></header>
        <div class="pbx-vg"><div>
          <small>Projection, ${esc(SLABEL[s])}</small>
          <div class="big"><b>${r.mu == null ? '-' : fmt(r.mu)}</b>${r.mu != null ? `<span class="${(side === 'o' ? r.mu > r.line : r.mu < r.line) ? 'pos' : 'neg'}">${sgn(r.mu - r.line)} vs line</span>` : ''}</div>
          <small>${r.min ? `On ${fmt(r.min)} projected minutes` : ''}${r.fair != null ? ` · leans ${r.fair > .5 ? 'over' : 'under'}` : ''}${X && D.teams[r.team] ? ` · <button type="button" class="linkbtn" data-lab="${esc(r.team)}">Change minutes</button>` : ''}</small>
          <div class="probs"><div><small>Model</small><b>${pc(pmS) || '-'}</b></div><div><small>Market, no vig</small><b>${pc(mkS) || '-'}</b></div><div class="fair"><small>Vault fair</small><b>${pc(x.fair) || '-'}</b></div></div>
          <div class="verdict">${r.hold ? '<span class="pbx-gate hold">HOLD</span>' : x.gate === 'go' ? '<span class="pbx-gate go">GO</span>' : x.gate === 'watch' ? '<span class="pbx-gate watch">WATCH</span>' : ''}<p>${verdict}</p></div>
          ${ev && ev.v != null ? `<p class="note">Pinnacle no-vig check: ${esc(ev.bk)} ${esc(ev.side)} ${ev.px > 0 ? '+' : ''}${ev.px} is ${sgn(ev.v * 100)}% EV against Pinnacle's fair. This does not use the model.</p>` : ''}
        </div><div>
          <small>How the projection is built</small>
          ${bld && r.min > 0 ? `<div class="wf"><div class="base"><span>${PART_LABEL.base}</span><b>${fmt(bld.base, 2)}</b></div>${adj.map(k => { const v = bld[k], w = Math.abs(v) / amax * 50;
            return `<div class="wr"><span>${esc(PART_LABEL[k] || k)}</span><span class="trk"><i style="${v >= 0 ? `left:50%;width:${w}%` : `left:${50 - w}%;width:${w}%`}" class="${v >= 0 ? 'p' : 'n'}"></i></span><b class="${v > 0 ? 'pos' : 'neg'}">${sgn(v, 2)}</b></div>`; }).join('')}
            <div class="base tot"><span>Projection</span><b>${fmt(r.mu, 2)}</b></div></div>` : '<p class="muted">Minutes × rate only for this prop.</p>'}
          <p class="note">Fair blends the model and the no-vig market with weights fit on held-out games. Edge is fair minus the break-even of the price, after fees.</p>
        </div></div>
      </section>

      <section class="pbx-card2"><header><h3>With and without teammates</h3><small>${esc(SLABEL[s])}, ${side === 'o' ? 'over' : 'under'} ${r.line} · tap a row to filter the chart</small></header>
        ${mrows.length ? `<div class="pbx-scroll"><table class="pbx-pt pbx-st"><thead><tr><th>Teammate</th><th>Without: games</th><th>Avg</th><th>Hit</th><th>Min</th><th>With: games</th><th>Avg</th><th>Hit</th></tr></thead><tbody>
          ${mrows.map(z => `<tr class="cl${DS.mate && DS.mate.id === z.m.id ? ' main' : ''}" data-mate="${z.m.id}"><td>${esc(z.m.name)}${z.m.st && /out|doubt|quest|inactive/i.test(z.m.st) ? `<span class="pbx-otag${/quest/i.test(z.m.st) ? ' q' : ''}">${esc(z.m.st.toUpperCase())} TONIGHT</span>` : ''}</td>
            <td>${z.nwo}</td><td><b>${z.awo == null ? '-' : fmt(z.awo)}</b>${z.aw != null && z.awo != null ? ` <small class="${z.awo > z.aw ? 'pos' : 'neg'}">${sgn(z.awo - z.aw)}</small>` : ''}</td><td>${pcell(z.hwo)}</td>
            <td>${z.mwo == null ? '-' : fmt(z.mwo)}${z.mw != null && z.mwo != null ? ` <small>${sgn(z.mwo - z.mw)}</small>` : ''}</td><td class="muted">${z.nw}</td><td class="muted">${z.aw == null ? '-' : fmt(z.aw)}</td><td>${pcell(z.hw)}</td></tr>`).join('')}
        </tbody></table></div><p class="note">Last two seasons, only games where both were on the same team. Small samples swing hard; check the game count.</p>` : '<p class="note">No teammate has missed a game alongside him yet.</p>'}
      </section>

      <section class="pbx-card2"><header><h3>Alt lines</h3><small>Hit rate at every line, the best price there and Vault's fair where it prices one</small></header>
        <div class="pbx-scroll"><table class="pbx-pt pbx-st"><thead><tr><th>${side === 'o' ? 'Over' : 'Under'}</th><th>L10</th><th>L20</th><th>${WIN[4][1]}</th><th>2 seasons</th><th>Best price</th><th>Vault fair</th><th>Edge</th></tr></thead><tbody>
          ${lad.map(z => `<tr class="${z.L === r.line ? 'main' : ''}"><td><b>${z.L}</b>${z.L === r.line ? ' <small>main</small>' : ''}</td><td>${pcell(z.l10)}</td><td>${pcell(z.l20)}</td><td>${pcell(z.s0)}</td><td>${pcell(z.both)}</td>
            <td>${z.c ? `<span class="pbx-odds" style="justify-content:flex-end">${bkChip(z.c.bk)}<b>${esc(priceTxt(z.c))}</b></span>` : '<span class="muted">-</span>'}</td><td class="v">${z.c ? pc(z.c.fair) : '-'}</td><td class="${z.c && z.c.edge > 0 ? 'pos' : z.c ? 'neg' : ''}">${z.c ? sgn(z.c.edge * 100) + '%' : '-'}</td></tr>`).join('')}
        </tbody></table></div><p class="note">Lines with no price show hit rates only. Kalshi prices include its fee; a Kalshi line of 19.5 is the 20+ rung.</p>
      </section>

      <section class="pbx-card2"><header><h3>Opportunity</h3><small>Last 15 games · darker bars are the last 5</small></header>
        <div class="pbx-o4">${[[MIN_I, 'Minutes'], [IDX.fga, 'Shots (FGA)'], [IDX.tpa, '3PT attempts'], [IDX.fta, 'Free throw att.']].map(([i, l]) => {
          const v = g15.map(z => z[i]), l5 = avg(all0.slice(0, 5).map(z => z[i])), sz = avg(all0.filter(z => z[1] === GL.current_season).map(z => z[i])), dd = l5 != null && sz != null ? l5 - sz : null;
          return `<div><small><span>${l}</span><span>L5 vs ${WIN[4][1]}</span></small><b>${l5 == null ? '-' : fmt(l5)}<i class="${dd > 0 ? 'pos' : dd < 0 ? 'neg' : ''}">${dd == null ? '' : sgn(dd)}</i></b>${spark(v, Math.min(5, v.length))}</div>`; }).join('')}</div>
        ${r.min ? `<p class="note">Vault projects ${fmt(r.min)} minutes tonight.</p>` : ''}
      </section>

      <section class="pbx-card2"><header><h3>Situations</h3><small>Last two seasons · tonight is highlighted · lines are the last DraftKings spread before tip</small></header>
        <div class="pbx-scroll"><table class="pbx-pt pbx-st"><thead><tr><th>Split</th><th>Games</th><th>Minutes</th><th>${esc(SLABEL[s])} avg</th><th>${side === 'o' ? 'Over' : 'Under'} ${r.line}</th></tr></thead><tbody>
          ${sits.map(z => `<tr class="${z.now ? 'main' : ''}"><td>${z.lbl}${z.now ? ' <small>tonight</small>' : ''}</td><td>${z.n}</td><td>${z.min == null ? '-' : fmt(z.min)}</td><td>${z.avg == null ? '-' : fmt(z.avg)}</td><td>${pcell(z.hit)}</td></tr>`).join('')}
        </tbody></table></div>
        <p class="note">Tonight: ${homeT == null ? '' : homeT ? 'home' : 'away'}${restT == null ? '' : restT === 0 ? ', second night of a back-to-back' : `, ${restT} day${restT === 1 ? '' : 's'} of rest`}${spT != null ? `, ${spT < 0 ? 'favored by ' + Math.abs(spT) : spT > 0 ? 'underdog by ' + spT : 'pick\'em'}` : ''}. Rest counts days between his own games, so a missed game reads as extra rest.${cx ? ' Result rows (won, lost, blowout, close) are only known after the game, and his own big night helps decide them, so they describe the past and cannot be picked in advance.' : ''}</p>
      </section>

      <section class="pbx-card2"><header><h3>Every price</h3><small>${side === 'o' ? 'Over' : 'Under'} side · best in green</small></header>
        <div class="pbx-scroll"><table class="pbx-pt"><thead><tr><th>Venue</th><th>Line</th><th>Over</th><th>Under</th><th>Fair (over)</th><th>Opened</th></tr></thead><tbody>
          <tr class="grp"><td colspan="6">Sportsbooks</td></tr>
          ${r.books.filter(b => b.bk !== 'Polymarket').map(b => { const isB = best && best.bk === b.bk && best.line === b.line;
            return `<tr><td><span class="bkn">${bkChip(b.bk)}${esc(b.bk)}</span></td><td>${b.line}</td><td class="${isB && side === 'o' ? 'best' : ''}">${b.o}</td><td class="${isB && side === 'u' ? 'best' : ''}">${b.u}</td><td class="v">${pc(b.fair) || '-'}</td><td class="muted">${b.l0 != null ? `${b.l0} ${b.o0 || ''}` : '-'}</td></tr>`; }).join('') || '<tr><td colspan="6" class="muted">No sportsbook line.</td></tr>'}
          ${r.books.some(b => b.bk === 'Polymarket') ? `<tr class="grp"><td colspan="6">Polymarket · ask to buy, fee included</td></tr>` + r.books.filter(b => b.bk === 'Polymarket').map(b => `<tr><td><span class="bkn">${bkChip('Polymarket')}Polymarket</span></td><td>${b.line}</td><td>Yes ${Math.round(amP(b.o) * 100)}¢</td><td>No ${Math.round(amP(b.u) * 100)}¢</td><td class="v">${pc(b.fair) || '-'}</td><td class="muted">-</td></tr>`).join('') : ''}
          ${r.kal.length ? `<tr class="grp"><td colspan="6">Kalshi ladder · YES pays if he reaches the rung</td></tr>` + r.kal.map(k => `<tr${k.line === r.line ? ' class="main"' : ''}><td><span class="bkn">${bkChip('Kalshi')}Kalshi</span></td><td>${k.line + .5}+</td><td>Yes ${Math.round(k.ask * 100)}¢</td><td>No ${Math.round((1 - k.bid) * 100)}¢</td><td class="v">${pc(k.fair)}</td><td class="muted">-</td></tr>`).join('') : ''}
          ${r.pk.length ? `<tr class="grp"><td colspan="6">Pick'em apps · flat lines judged against the ${pc(PK_BE, 1)} flex break-even</td></tr>` + r.pk.map(k => `<tr><td><span class="bkn">${bkChip(k.app)}${esc(PKN[k.app] || k.app)}</span></td><td>${k.line}</td><td>${k.o ?? 'flat'}</td><td>${k.u ?? 'flat'}</td><td class="v">${pc(k.fair) || '-'}</td><td class="muted">${k.l0 ?? '-'}</td></tr>`).join('') : ''}
        </tbody></table></div>
      </section>
      ${tracker(x)}
    </div>

    <aside class="pbx-rail">
      <section class="pbx-card2"><div class="pbx-rt">${[['matchup', 'Matchup'], ['inj', 'Injuries'], ['game', 'Game']].map(([k, l]) => `<button type="button" data-rtab="${k}" class="${DS.rtab === k ? 'on' : ''}">${l}</button>`).join('')}</div>
        <div class="pbx-rb">
        ${DS.rtab === 'matchup' ? (oppRows.length ? `<h5>${esc(x.opp)} defense vs ${grpW}</h5><table class="pbx-dt"><thead><tr><th>Stat</th><th>Per game</th><th>Rank</th></tr></thead><tbody>
            ${oppRows.map(([k, v]) => { const gd = oppGood(v[0], side); return `<tr class="${k === s ? 'on' : ''}"><td>${esc(SLABEL[k])}</td><td>${fmt(v[1])}</td><td><span class="pbx-opp ${gd > 0 ? 'h1' : gd < 0 ? 'l1' : ''}">${ord(v[0])}</span></td></tr>`; }).join('')}</tbody></table>
            <p class="note">This season, ${oppRows[0][1][2]} games. 1st allows the fewest, 30th the most. Green favors the ${side === 'o' ? 'over' : 'under'}.</p>` : '<p class="muted">No position ranks yet.</p>') : ''}
        ${DS.rtab === 'inj' ? (injs.length ? injs.map(([n, t, st]) => `<div class="pbx-inj"><span>${esc(n)} <small>${t}</small></span><b class="${/out|inactive/i.test(st) ? 'neg' : 'warn'}">${esc(st)}</b></div>`).join('') : '<p class="muted">No one listed for either team.</p>') : ''}
        ${DS.rtab === 'game' && g ? `<div class="pbx-gc"><div><small>Tip</small><b>${clock(g.tip)} ${TZL}</b></div><div><small>Spread</small><b>${g.spread != null ? `${g.home} ${sgn(g.spread)}` : '-'}</b></div><div><small>Total</small><b>${g.total ?? '-'}</b></div><div><small>Kalshi, ${g.home} win</small><b>${kw != null ? pc(kw) : '-'}</b></div></div><p class="note">Game lines are context for the prop, not part of its edge.</p>` : ''}
        </div></section>
      ${sigCard(x, all0, hist, side)}
      <section class="pbx-card2"><header><h3>Line movement</h3><small>${hist.state === 'ok' ? 'DraftKings · over price at each point' : esc(r.lineFrom || '')}</small></header>
        ${hist.state === 'ok' ? `<div class="pbx-lc">${lineChart(hist.ser)}</div>
          <table class="pbx-lm"><thead><tr><th>When (${TZL})</th><th>Line</th><th>Over</th><th>Under</th></tr></thead><tbody>
          ${hist.ser.slice().reverse().slice(0, 6).map((z, i, a) => `<tr><td${i ? ' class="muted"' : ''}>${clock(z[0])}${i === 0 ? ' · latest' : i === a.length - 1 && hist.ser.length <= 6 ? ' · open' : ''}</td><td>${i === 0 ? `<b>${z[1]}</b>` : z[1]}</td><td>${esc(z[2] || '-')}</td><td>${esc(z[3] || '-')}</td></tr>`).join('')}</tbody></table>
          <p class="note">${hist.ser.length} price change${hist.ser.length === 1 ? '' : 's'} since DraftKings posted it${hist.ser.length > 6 ? '; the latest 6 are listed' : ''}, from the recorder's polls. The table's line can come from another book.</p>`
        : `<table class="pbx-lm"><thead><tr><th>When</th><th>Line</th><th>Over</th></tr></thead><tbody>
          <tr><td>Now</td><td><b>${r.line}</b></td><td>${main ? main.o : '-'}</td></tr>
          <tr><td class="muted">Open</td><td>${main && main.l0 != null ? main.l0 : x.sc.dm != null ? r.line - x.sc.dm : '-'}</td><td>${main && main.o0 ? main.o0 : '-'}</td></tr></tbody></table>
          <p class="note">${hist.state === 'loading' ? 'Loading the move-by-move history...' : 'No DraftKings history recorded for this prop, so only open and now are shown.'}</p>`}
      </section>
    </aside></div>`;
    placeBar();
  }
  function placeBar(){
    const st = $('pbx-stabs'); if (!st) return; const on = st.querySelector('button.on'), bar = st.querySelector('.pbx-ul'); if (!on) return;
    if (DS.bar){ bar.style.transition = 'none'; bar.style.left = DS.bar[0]; bar.style.width = DS.bar[1]; void bar.offsetWidth; bar.style.transition = ''; DS.bar = null; }
    bar.style.left = on.offsetLeft + 'px'; bar.style.width = on.offsetWidth + 'px';
  }
  function trkUpdate(){ const rt = routeOf(); if (!rt) return; const x = build(PS.board).find(z => z.r.e.p === rt.pid && z.r.e.s === rt.s && z.side === rt.side); if (x && $('pbx-tro')) $('pbx-tro').innerHTML = trkReadout(x); }
  function detailClick(e){
    const t = e.target, b = t.closest('[data-back],[data-mate],[data-mclear],[data-dside],[data-ds],[data-win],[data-med],[data-rtab],[data-totrk],[data-tside],[data-tunit],[data-tsave]'); if (!b) return false;
    const d = b.dataset, rt = routeOf(); if (!rt && !d.back) return false;
    if (d.back){ history.length > 1 && /#propboard\//.test(location.hash) ? (location.hash = '#propboard') : goView('propboard'); return true; }
    if (d.totrk){ $('pbx-trk').scrollIntoView({behavior: 'smooth', block: 'center'}); return true; }
    if (d.dside || d.tside){ DS.T = null; goProp(rt.pid, rt.s, d.dside || d.tside); return true; }
    if (d.ds){ const bar = document.querySelector('#pbx-stabs .pbx-ul'); DS.bar = bar ? [bar.style.left, bar.style.width] : null; DS.T = null; goProp(rt.pid, d.ds, rt.side); return true; }
    if (d.win){ DS.win = d.win; rerender(); return true; }
    if (d.mate){ const id = +d.mate; DS.mate = DS.mate && DS.mate.id === id ? null : {mode: 'wo', id}; rerender(); window.scrollTo({top: 0, behavior: 'smooth'}); return true; }
    if (d.mclear){ DS.mate = null; rerender(); return true; }
    if (d.gclear){ DS.gf = null; rerender(); return true; }
    if (d.med){ DS.med = d.med === '1'; rerender(); return true; }
    if (d.rtab){ DS.rtab = d.rtab; rerender(); return true; }
    const x = build(PS.board).find(z => z.r.e.p === rt.pid && z.r.e.s === rt.s && z.side === rt.side); if (!x) return true;
    if (d.tunit){ const u = d.tunit; if (u !== DS.T.unit){ const k = trkCalc(x); if (!k.err && !k.flat){ const raw = k.c.venue === 'kalshi' ? k.cost - kFee(k.cost) : k.cost; DS.T.price = u === 'am' ? fmtAm(pToAm(raw)) : String(Math.round(raw * 1000) / 10); } DS.T.unit = u; }
      $('pbx-tprice').value = DS.T.price; document.querySelectorAll('[data-tunit]').forEach(z => z.setAttribute('aria-pressed', z.dataset.tunit === u)); trkUpdate(); return true; }
    if (d.tsave){ const k = trkCalc(x); if (k.err){ pvToast(k.err); return true; }
      const bet = pvMkBet(x.r, k.c, k.inStr, k.stake);
      if (!bet){ pvToast('Enter a price and a stake.'); return true; }
      pvBets.unshift(bet); pvSave(); pvSettle(); DS.T = null; rerender(); pvToast(bet.ex ? 'Saved to My bets. The example game is over, so it settles right away.' : 'Saved to My bets. It settles after the game.'); return true; }
    return true;
  }
  function detailInput(e){
    const t = e.target; if (!DS.T) return;
    if (t.id === 'pbx-tprice'){ DS.T.price = t.value; trkUpdate(); }
    else if (t.id === 'pbx-tstake'){ DS.T.stake = +t.value || null; trkUpdate(); }
    else if (t.id === 'pbx-tven'){ const rt = routeOf(), x = build(PS.board).find(z => z.r.e.p === rt.pid && z.r.e.s === rt.s && z.side === rt.side), c = trkOpts(x)[+t.value];
      DS.T.i = +t.value; DS.T.unit = c.venue === 'kalshi' ? 'pct' : 'am'; DS.T.price = priceStr(c, DS.T.unit); DS.T.stake = null; rerender(); $('pbx-trk').scrollIntoView({block: 'center'}); }
  }

  function render(B){
    css();
    WIN[4][1] = szn(GL.current_season); WIN[5][1] = szn(GL.current_season - 1);
    const rt = routeOf(), rk = rt ? `${rt.pid}|${rt.s}|${rt.side}` : null;
    if (rt){ const fresh = DS.at !== rk; if (fresh && (!DS.at || DS.at.split('|')[0] !== String(rt.pid))) DS.mate = DS.gf = null; DS.at = rk; detail(B, rt); if (fresh) window.scrollTo(0, 0); return; }
    if (DS.at){ DS.at = null; const y = S.scroll || 0; setTimeout(() => window.scrollTo(0, y), 0); }
    const root = $('pbx-root'), games = (B.games || []).filter(g => g.tip > Date.now() / 1000).sort((a, b) => a.tip - b.tip);
    if (S.game !== 'all' && !games.some(g => String(g.id) === S.game)) S.game = 'all';
    const all = build(B), rows = filtered(all), show = rows.slice(0, S.limit);
    const nWatch = new Set(all.filter(x => watched(x.r, x.side)).map(x => pvKey(x.r))).size;   // props watched that are still on the board
    pf.rows = show.map(x => x.r);                    // the shared drawer's Log and Watch buttons look rows up here
    const statsOn = STATS.filter(([k]) => k === 'all' || all.some(x => x.r.e.s === k));
    const th = (k, l, c, v) => `<button type="button" class="${c ? 'c ' : ''}${v ? 'v ' : ''}${S.sort === k ? 'on' : ''}" data-sort="${k}" aria-sort="${S.sort === k ? (S.dir > 0 ? 'ascending' : 'descending') : 'none'}">${l}${S.sort === k ? `<i>${S.dir > 0 ? '▲' : '▼'}</i>` : ''}</button>`;
    const act = fActive();
    const row = (x, i) => { const r = x.r, h = hits(x), key = `${r.e.p}|${r.e.s}|${x.side}`, open = S.open === key, w = watched(r, x.side);
      const who = x.g ? `${x.g.away} @ ${x.g.home} · ${clock(x.g.tip)}` : esc(r.team);
      return `<article class="pbx-row${open ? ' open' : ''}" data-i="${i}">
        <button type="button" class="pbx-tr press" aria-expanded="${open}">
          <span class="pbx-star${w ? ' on' : ''}" title="${w ? 'Watching' : ''}">${w ? '★' : ''}</span>
          <span class="pbx-prop">${face(x)}<span class="who"><b>${esc(r.name)} ${injTag(r)}<small>${who}</small></b><span>${sideW(x.side)} <b>${r.line}</b> ${esc(SLABEL[r.e.s])}</span></span></span>
          <span class="c">${lineC(x)}</span><span>${odds(x)}</span>
          <span class="c v">${projC(x)}</span><span class="c v"><b>${pc0(x.fair)}</b></span><span class="c v">${edgeC(x)}</span>
          <span class="c">${oppC(x)}</span>${WIN.map(([k]) => `<span class="c">${hcell(h[k])}</span>`).join('')}
        </button>
        <button type="button" class="pbx-card press" aria-expanded="${open}">
          <span class="t">${face(x)}<span class="who"><b>${esc(r.name)} ${injTag(r)}</b><small>${who}</small></span></span>
          <span class="m"><span>${sideW(x.side)} <b>${r.line}</b> ${esc(SLABEL[r.e.s])}</span>${odds(x)}</span>
          <span class="q"><span><small>Proj</small><b>${r.mu == null ? '-' : fmt(r.mu)}</b></span><span><small>Fair</small><b>${pc0(x.fair)}</b></span><span><small>Edge</small><b class="${x.edge > 0 ? 'pos' : x.edge != null ? 'neg' : ''}">${x.edge == null ? '-' : sgn(x.edge * 100) + '%'}</b></span><span><small>Opp</small><b>${x.orank ? ord(x.orank[0]) : '-'}</b></span></span>
          <span class="hh">${WIN.map(([k, l]) => `<span><small>${l}</small>${hcell(h[k])}</span>`).join('')}</span>
        </button>
        </article>`; };
    root.innerHTML = `
      <div class="pbx-games">
        <button type="button" class="pbx-g all${S.game === 'all' ? ' on' : ''}" data-game="all">All games</button>
        ${games.map(g => `<button type="button" class="pbx-g${S.game === String(g.id) ? ' on' : ''}" data-game="${g.id}"><span class="tm">${lgImg(g.away, 16)}${g.away}</span><small>${clock(g.tip)}<br>${g.spread != null ? `${g.home} ${sgn(g.spread)}` : ''}${g.total != null ? ` · ${g.total}` : ''}</small><span class="tm">${lgImg(g.home, 16)}${g.home}</span></button>`).join('')}
      </div>
      <div class="pbx-stats">${statsOn.map(([k, l]) => `<button type="button" class="${S.stat === k ? 'on' : ''}" data-stat="${k}">${k === 'all' ? 'All props' : l}</button>`).join('')}</div>
      <div class="pbx-bar">
        <button type="button" class="pbx-fb${S.fOpen ? ' on' : ''}" data-fopen="1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 5h18M6 12h12M10 19h4"/></svg>Filters${act.length ? `<i>${act.length}</i>` : ''}</button>
        <label class="pbx-fb q"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input id="pbx-q" type="search" placeholder="Players" autocomplete="off" value="${esc(S.q)}" aria-label="Filter players"></label>
        <div class="seg" role="group" aria-label="Side">${[['all', 'Over / Under'], ['o', 'Over'], ['u', 'Under']].map(([k, l]) => `<button type="button" data-side="${k}" aria-pressed="${S.side === k}">${l}</button>`).join('')}</div>
        <button type="button" class="pbx-fb pbx-wf${S.f.watch ? ' on' : ''}" data-f="watch" data-v="1" aria-pressed="${S.f.watch}" title="Show only the props you watch">★ Watching${nWatch ? `<i>${nWatch}</i>` : ''}</button>
        <span class="pbx-n">${rows.length.toLocaleString()} / ${all.length.toLocaleString()} props</span>
      </div>
      ${S.fOpen ? filterPanel(rows.length) : ''}
      ${act.length ? `<div class="pbx-chips">${act.map(([k, l]) => `<span>${esc(l)}<button type="button" data-fclear="${k}" aria-label="Remove ${esc(l)}">×</button></span>`).join('')}</div>` : ''}
      <p class="pbx-key"><span class="v">Vault model columns</span><span>Hit rates: share of games over (or under) tonight's line</span><span>Opp rank: 1st allows the fewest to his position, 30th the most</span></p>
      <div class="pbx-tbl"><div class="pbx-scroll">
        <div class="pbx-th"><span></span>${th('prop', 'Proposition')}${th('line', 'Line', 1)}${th('odds', 'Best odds')}${th('proj', 'Vault proj', 1, 1)}${th('fair', 'Fair', 1, 1)}${th('edge', 'Edge', 1, 1)}${th('opp', 'Opp rank', 1)}${WIN.map(([k, l]) => th(k, l, 1)).join('')}</div>
        ${show.map(row).join('') || `<p class="empty" style="padding:24px">${!all.length ? 'Nothing on the board yet.' : S.f.watch && !nWatch ? 'Nothing on your watch list. Open a prop and tap Watch to add it here.' : 'No props match these filters.'}</p>`}
      </div></div>
      ${rows.length > S.limit ? `<div class="pbx-more"><button type="button" class="btn" data-more="1">Show ${Math.min(60, rows.length - S.limit)} more</button></div>` : ''}`;
    root._show = show;
  }

  function rerender(){ renderProps(); }
  function wire(){
    const root = $('pbx-root');
    root.addEventListener('click', e => {
      if (pbClick(e, rerender)) return;                                   // Watch (and Log in any shared drawer)
      if (detailClick(e)) return;
      const t = e.target, b = t.closest('[data-game],[data-stat],[data-side],[data-sort],[data-f],[data-fclear],[data-fopen],[data-freset],[data-fdone],[data-more],[data-w],[data-lab]');
      if (b){
        const d = b.dataset;
        if (d.w){ pwin = d.w; rerender(); return; }
        if (d.lab){ history.replaceState(null, '', '#' + d.lab.toLowerCase()); goTeam(d.lab); return; }
        if (d.game){ S.game = d.game; S.limit = 60; }
        else if (d.stat){ S.stat = d.stat; S.limit = 60; }
        else if (d.side){ S.side = d.side; }
        else if (d.sort){ if (S.sort === d.sort) S.dir = -S.dir; else { S.sort = d.sort; S.dir = d.sort === 'prop' ? 1 : -1; } }
        else if (d.fopen){ S.fOpen = !S.fOpen; }
        else if (d.fdone){ S.fOpen = false; }
        else if (d.freset){ S.f = JSON.parse(JSON.stringify(FDEF)); save(); }
        else if (d.fclear){ fClear(d.fclear); S.limit = 60; }
        else if (d.more){ S.limit += 60; }
        else if (d.f){ const k = d.f, f = S.f;
          if (k === 'ven'){ f.ven[d.v] = f.ven[d.v] ? 0 : 1; if (!Object.values(f.ven).some(Boolean)) f.ven[d.v] = 1; }
          else if (k === 'oppFav' || k === 'healthy' || k === 'starters' || k === 'watch') f[k] = !f[k];
          else { const v = d.v === 'null' ? null : isNaN(+d.v) ? d.v : +d.v; f[k] = v; }
          save(); S.limit = 60; }
        rerender(); return;
      }
      const tr = t.closest('.pbx-tr, .pbx-card');
      if (tr){ const x = root._show[+tr.closest('.pbx-row').dataset.i]; DS.T = null; S.scroll = scrollY; goProp(x.r.e.p, x.r.e.s, x.side); }
    });
    root.addEventListener('submit', e => { e.preventDefault(); pbSubmit(e, rerender); });
    root.addEventListener('change', e => { if (e.target.id === 'pbx-tven'){ detailInput(e); return; } if (e.target.id === 'pbx-gf'){ DS.gf = e.target.value || null; rerender(); return; } if (e.target.id === 'pbx-mate'){ const v = e.target.value; DS.mate = v ? {mode: v.split('|')[0], id: +v.split('|')[1]} : null; rerender(); return; } const i = e.target.closest('[data-fodds]'); if (i){ S.f[i.dataset.fodds] = i.value.trim(); save(); rerender(); } });
    let qT = null;
    root.addEventListener('input', e => { if (e.target.id === 'pbx-tprice' || e.target.id === 'pbx-tstake'){ detailInput(e); return; } if (e.target.id !== 'pbx-q') return; S.q = e.target.value; clearTimeout(qT);
      qT = setTimeout(() => { const at = e.target.selectionStart; rerender(); const n = $('pbx-q'); if (n){ n.focus(); n.setSelectionRange(at, at); } }, 150); });
  }

  let styled = false;
  function css(){
    if (styled) return; styled = true;
    const st = document.createElement('style'); st.id = 'pbx-css';
    st.textContent = `
#pbx-root{--pbx-g:var(--up);--pbx-r:var(--down);--pbx-v:var(--c-violet,#c4b5fd);--pbx-vbg:color-mix(in srgb,var(--pbx-v) 12%,transparent)}
.pbx-games{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;padding:2px 0 4px;margin-bottom:10px}
.pbx-games::-webkit-scrollbar{display:none}
.pbx-g{flex:none;display:grid;grid-template-columns:auto auto;gap:2px 12px;align-items:center;text-align:left;padding:8px 12px;min-width:150px;border-radius:12px;background:var(--surface);border:1px solid rgb(var(--ink) / .08);color:var(--fg);transition:border-color .15s}
.pbx-g:hover{border-color:rgb(var(--ink) / .2)}
.pbx-g.on{border-color:var(--pbx-g);box-shadow:inset 0 0 0 1px var(--pbx-g)}
.pbx-g.all{min-width:auto;display:flex;font-weight:600}
.pbx-g .tm{display:flex;align-items:center;gap:6px;font-weight:600;font-size:12px}
.pbx-g small{grid-column:2;grid-row:1/3;text-align:right;color:var(--fg3);font-size:11px;line-height:1.35}
.pbx-stats{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;margin-bottom:10px}
.pbx-stats::-webkit-scrollbar{display:none}
.pbx-stats button{flex:none;padding:6px 11px;border-radius:8px;font-weight:600;font-size:12px;color:var(--fg3);border:1px solid transparent;background:none}
.pbx-stats button:hover{color:var(--fg)}
.pbx-stats button.on{color:var(--fg);background:var(--surface2);border-color:rgb(var(--ink) / .08)}
.pbx-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.pbx-fb{display:inline-flex;align-items:center;gap:7px;height:34px;padding:0 12px;border-radius:var(--r-pill);background:var(--chip);border:1px solid transparent;color:var(--fg2);font-weight:600;font-size:12.5px}
.pbx-fb:hover,.pbx-fb.on{color:var(--fg);border-color:rgb(var(--ink) / .15)}
.pbx-fb svg{width:14px;height:14px}
.pbx-wf.on{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 45%,transparent)}
.pbx-fb i{font-style:normal;background:var(--fg);color:var(--bg);border-radius:6px;font-size:11px;padding:0 6px}
.pbx-fb.q input{background:none;border:0;outline:none;color:var(--fg);font:inherit;width:140px}
.pbx-n{margin-left:auto;color:var(--fg3);font-size:12px}
.pbx-fpanel{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px 20px;padding:16px;margin-bottom:12px;border-radius:16px;background:var(--surface);border:1px solid rgb(var(--ink) / .08)}
.pbx-fpanel h6{margin:0 0 7px;font-size:11px;font-weight:600;color:var(--fg3);text-transform:uppercase;letter-spacing:.04em}
.pbx-fpanel > div > div{display:flex;flex-wrap:wrap;gap:5px;align-items:center;color:var(--fg3)}
.pbx-fopt{height:28px;padding:0 10px;border-radius:var(--r-pill);background:var(--chip);border:1px solid transparent;color:var(--fg2);font-weight:600;font-size:12px}
.pbx-fopt:hover{color:var(--fg)}
.pbx-fopt.on{background:var(--primary);color:var(--on-primary)}
.pbx-fpanel .rng input{height:30px;width:84px;border-radius:8px;border:1px solid rgb(var(--ink) / .12);background:var(--ctl);color:var(--fg);font:500 12.5px var(--font-mono);padding:0 9px}
.pbx-fpanel .ft{grid-column:1/-1;display:flex;gap:8px;align-items:center;justify-content:flex-end;border-top:1px solid rgb(var(--ink) / .08);padding-top:12px}
.pbx-fpanel .ft .muted{margin-right:auto;font-size:12px}
.pbx-chips{display:flex;gap:6px;flex-wrap:wrap;margin:-2px 0 10px}
.pbx-chips span{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 5px 0 10px;border-radius:var(--r-pill);background:var(--chip);font-size:11.5px;font-weight:600;color:var(--fg2)}
.pbx-chips button{width:17px;height:17px;border-radius:50%;background:none;border:0;color:var(--fg3);font-size:13px;line-height:1;padding:0}
.pbx-chips button:hover{background:var(--chip-h);color:var(--fg)}
.pbx-key{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 8px;color:var(--fg3);font-size:11.5px}
.pbx-key .v{color:var(--pbx-v);font-weight:600}
.pbx-tbl{border-radius:16px;background:var(--surface);border:1px solid rgb(var(--ink) / .06);overflow:hidden}
.pbx-scroll{overflow-x:auto}
.pbx-th,.pbx-tr{display:grid;grid-template-columns:28px minmax(240px,1fr) 92px 118px 74px 56px 74px 76px repeat(6,52px);align-items:center;min-width:1110px}
.pbx-th{background:var(--surface2);height:38px;position:sticky;top:0;z-index:1}
.pbx-th button{display:flex;align-items:center;gap:4px;height:100%;padding:0 8px;background:none;border:0;color:var(--fg3);font-size:11px;font-weight:600;white-space:nowrap}
.pbx-th button.c{justify-content:center}
.pbx-th button:hover,.pbx-th button.on{color:var(--fg)}
.pbx-th button.v{color:var(--pbx-v)}
.pbx-th button i{font-style:normal;font-size:9px}
.pbx-row{border-top:1px solid rgb(var(--ink) / .06)}
.pbx-tr{width:100%;background:none;border:0;color:var(--fg);text-align:left;padding:0;cursor:pointer;transition:background .12s}
.pbx-tr:hover,.pbx-row.open .pbx-tr{background:var(--surface2)}
.pbx-tr > span{padding:8px;min-width:0;white-space:nowrap}
.pbx-tr > span.c{display:flex;justify-content:center;text-align:center}
.pbx-star{color:var(--warn);font-size:12px;text-align:center}
.pbx-prop{display:flex;align-items:center;gap:10px}
.pbx-face{position:relative;width:38px;height:38px;flex:none}
.pbx-face .hs{position:relative;display:grid;place-items:center;width:38px;height:38px;border-radius:50%;overflow:hidden;background:var(--raised);color:var(--fg3);font-size:11px}
.pbx-face .hs img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 12%}
.pbx-face .lo{position:absolute;right:-4px;bottom:-3px;width:17px;height:17px;border-radius:50%;background:var(--surface);border:1px solid rgb(var(--ink) / .12);display:grid;place-items:center}
.pbx-face .lo img{width:13px;height:13px}
.pbx-prop .who{display:flex;flex-direction:column;align-items:flex-start;text-align:left;min-width:0}
.pbx-prop .who > b{font-weight:600;font-size:13px;display:flex;gap:6px;align-items:center;overflow:hidden;text-overflow:ellipsis}
.pbx-prop .who small{display:inline;font-weight:400;color:var(--fg3);font-size:11.5px;white-space:nowrap}
.pbx-prop .who > b{flex-wrap:nowrap;white-space:nowrap}
.pbx-prop .who > span{color:var(--fg2);font-size:12px;overflow:hidden;text-overflow:ellipsis}
.pbx-prop .who > span{display:block;white-space:nowrap}
.pbx-prop .who > span b,.pbx-prop .who > span span{display:inline;color:var(--fg);font-weight:600}
.pbx-prop .who > span .ov{color:var(--pbx-g);font-weight:700}.pbx-prop .who > span .un{color:var(--pbx-r);font-weight:700}
.ov{color:var(--pbx-g);font-weight:700}.un{color:var(--pbx-r);font-weight:700}
.pbx-tag{font-size:10px;font-weight:700;padding:1px 5px;border-radius:4px;background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn)}
.pbx-tag.out{background:color-mix(in srgb,var(--pbx-r) 16%,transparent);color:var(--pbx-r)}
.pbx-two{display:flex;flex-direction:column;align-items:center;gap:1px;font-variant-numeric:tabular-nums}
.pbx-two b{font-weight:600}
.pbx-two small{font-size:10.5px;color:var(--fg3)}
.pbx-two small.up{color:var(--pbx-g)}.pbx-two small.dn{color:var(--pbx-r)}
#pbx-root .pos{color:var(--pbx-g)}#pbx-root .neg{color:var(--pbx-r)}
.pbx-odds{display:inline-flex;align-items:center;gap:6px;font-variant-numeric:tabular-nums}
.pbx-odds b{font-weight:600}.pbx-odds small{color:var(--fg3);font-size:11px}
.pbx-bk{display:inline-grid;place-items:center;min-width:20px;height:20px;padding:0 3px;border-radius:5px;font-size:9px;font-weight:800;letter-spacing:-.02em}
.pbx-gate{font-size:9px;font-weight:800;letter-spacing:.04em;padding:1px 5px;border-radius:4px}
.pbx-gate.go{background:color-mix(in srgb,var(--pbx-g) 22%,transparent);color:var(--pbx-g)}
.pbx-gate.watch{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn)}
.pbx-gate.hold{background:color-mix(in srgb,var(--pbx-r) 16%,transparent);color:var(--pbx-r)}
.pbx-opp{font-size:11.5px;font-weight:600;padding:3px 6px;border-radius:6px}
.pbx-opp small{color:var(--fg3);font-weight:400;margin-left:3px}
.pbx-hc{display:inline-grid;place-items:center;width:44px;height:28px;border-radius:6px;font:500 11.5px var(--font-mono);color:var(--fg2);background:var(--surface2)}
.pbx-hc.h3{background:var(--pbx-g);color:var(--bg)}.pbx-hc.h2,.pbx-opp.h2{background:color-mix(in srgb,var(--pbx-g) 28%,transparent);color:var(--pbx-g)}.pbx-hc.h1,.pbx-opp.h1{background:color-mix(in srgb,var(--pbx-g) 14%,transparent);color:var(--pbx-g)}
.pbx-hc.l1,.pbx-opp.l1{background:color-mix(in srgb,var(--pbx-r) 14%,transparent);color:var(--pbx-r)}.pbx-hc.l2{background:color-mix(in srgb,var(--pbx-r) 28%,transparent);color:var(--pbx-r)}.pbx-hc.l3{background:var(--pbx-r);color:var(--bg)}
.pbx-hc.na{background:none;color:var(--fg3)}
.pbx-row .sc-dt{padding:0 12px 12px;background:var(--surface2)}
.pbx-card{display:none}
.pbx-more{display:flex;justify-content:center;padding:12px}

#pbx-root table.pbx-lm,#pbx-root table.pbx-dt,#pbx-root table.pbx-pt{min-width:0}
#pbx-root .seg button[aria-pressed="true"]{background:var(--seg-on);color:var(--fg)}
.pbx-back{display:inline-flex;align-items:center;gap:6px;margin:0 0 12px;background:none;border:0;color:var(--fg2);font-weight:600;font-size:13px;padding:0}
.pbx-back:hover{color:var(--fg)}
.pbx-detail{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:16px;align-items:start}
.pbx-main,.pbx-rail{display:flex;flex-direction:column;gap:16px;min-width:0}
.pbx-card2{background:var(--surface);border:1px solid rgb(var(--ink) / .06);border-radius:20px;overflow:hidden}
.pbx-card2 > header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 16px;border-bottom:1px solid rgb(var(--ink) / .06)}
.pbx-card2 > header h3{margin:0;font-size:13.5px;font-weight:600}
.pbx-card2 > header small{color:var(--fg3);font-size:11.5px;text-align:right}
.pbx-card2.vault{border-color:color-mix(in srgb,var(--pbx-v) 35%,transparent)}
.pbx-card2.vault > header{background:linear-gradient(90deg,var(--pbx-vbg),transparent)}
.pbx-card2.vault > header h3{color:var(--pbx-v)}
.pbx-dh{display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:14px 16px}
.pbx-dh .pbx-face,.pbx-dh .pbx-face .hs{width:56px;height:56px}
.pbx-dh .pbx-face .lo{width:22px;height:22px}.pbx-dh .pbx-face .lo img{width:16px;height:16px}
.pbx-dh h2{margin:5px 0 0;font-size:20px;font-weight:700;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pbx-dh h2 small{font-size:12px;color:var(--fg3);font-weight:500}
.pbx-mchip{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--fg2);font-weight:600;background:var(--surface2);border-radius:var(--r-pill);padding:3px 10px}
.pbx-dh .acts{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pbx-sel{display:inline-flex;align-items:center;gap:8px;height:34px;padding:0 12px;border-radius:var(--r-pill);font-weight:700;background:color-mix(in srgb,var(--pbx-g) 14%,transparent);color:var(--pbx-g)}
.pbx-sel.u{background:color-mix(in srgb,var(--pbx-r) 14%,transparent);color:var(--pbx-r)}
.pbx-sel b{color:var(--fg)}
.pbx-alt,.pbx-trk select{height:34px;border-radius:var(--r-pill);border:1px solid rgb(var(--ink) / .12);background:var(--ctl);color:var(--fg);font:500 12.5px var(--font-sans);padding:0 12px}
.pbx-tabs{position:relative;display:flex;gap:2px;padding:0 12px;border-bottom:1px solid rgb(var(--ink) / .06);overflow-x:auto;scrollbar-width:none}
.pbx-tabs::-webkit-scrollbar{display:none}
.pbx-tabs button{flex:none;padding:11px 10px;background:none;border:0;color:var(--fg3);font-weight:600;font-size:12px}
.pbx-tabs button:hover,.pbx-tabs button.on{color:var(--fg)}
.pbx-tabs .pbx-ul{position:absolute;bottom:0;height:2px;border-radius:2px;background:var(--pbx-g);transition:left 400ms var(--ease-rail,cubic-bezier(.65,0,.35,1)),width 400ms var(--ease-rail,cubic-bezier(.65,0,.35,1))}
.pbx-wins{padding:12px 16px 4px}
.pbx-hs{display:flex;align-items:flex-end;gap:22px;flex-wrap:wrap;padding:6px 16px}
.pbx-hs small{display:block;color:var(--fg3);font-size:11px;font-weight:600;margin-bottom:3px}
.pbx-hs > div:first-child b{font-size:30px;font-weight:700;letter-spacing:-.02em}
.pbx-hs > div:first-child b i{font-style:normal;font-size:12px;color:var(--fg3);margin-left:6px;font-weight:500}
.pbx-hs .w b{font:600 13px var(--font-mono)}
.pbx-chart{padding:8px 12px 4px}
.pbx-chart svg{display:block;width:100%;height:auto}
.pbx-chart .gl{stroke:rgb(var(--ink) / .07)}
.pbx-chart .ax{font:500 10px var(--font-sans);fill:var(--fg3)}.pbx-chart .ax.sm{font-size:9.5px}
.pbx-chart .lb{font:600 11px var(--font-sans);fill:var(--fg)}
.pbx-chart .o0{fill:var(--pbx-g)}.pbx-chart .o1{fill:color-mix(in srgb,var(--pbx-g) 72%,#000)}.pbx-chart .o2{fill:color-mix(in srgb,var(--pbx-g) 52%,#000)}
.pbx-chart .u0{fill:var(--pbx-r)}.pbx-chart .u1{fill:color-mix(in srgb,var(--pbx-r) 72%,#000)}.pbx-chart .u2{fill:color-mix(in srgb,var(--pbx-r) 52%,#000)}
.pbx-chart .gh{fill:rgb(var(--ink) / .04);stroke:rgb(var(--ink) / .42);stroke-width:1.2;stroke-dasharray:3 3}
.pbx-chart .gt{font:500 10px var(--font-sans);fill:var(--fg3)}.pbx-chart .gt.sm{font-size:8px;letter-spacing:-.02em}
.pbx-chart .lb.in{fill:#0b0b0c}
/* numbers sitting on a dashed line get a halo in the card colour so the line never runs through them */
.pbx-chart :is(.lb:not(.in),.gt,.so){paint-order:stroke;stroke:var(--surface);stroke-width:3px;stroke-linejoin:round}
.pbx-chart .gt .gm{font-weight:700;fill:var(--fg)}
.pbx-chart .sg{font:700 10px var(--font-mono);fill:rgb(0 0 0 / .78);pointer-events:none}.pbx-chart .sg .sk,.pbx-chart .sg.sk{font-weight:500;fill:rgb(0 0 0 / .55)}
.pbx-chart .sg.lt{fill:rgb(255 255 255 / .9)}.pbx-chart .sg.lt .sk{fill:rgb(255 255 255 / .65)}
/* light theme: the bars are dark green / red, so the numbers inside them go white */
:root[data-theme="light"] .pbx-chart :is(.sg,.lb.in){fill:#fff}:root[data-theme="light"] .pbx-chart .sg .sk,:root[data-theme="light"] .pbx-chart .sg.sk{fill:rgb(255 255 255 / .72)}
.pbx-chart .so{font:600 9px var(--font-mono);fill:var(--fg2)}.pbx-chart .so .sk{font-weight:500;fill:var(--fg3)}
.pbx-chart .ln{stroke:var(--fg);stroke-width:1.5;stroke-dasharray:5 4;opacity:.85}
.pbx-chart .vl{stroke:var(--pbx-v);stroke-width:1.5;stroke-dasharray:2 3}
.pbx-chart .tg{fill:var(--fg)}.pbx-chart .tt{font:700 10.5px var(--font-mono);fill:var(--bg)}
.pbx-chart .vtg{fill:var(--pbx-v)}.pbx-chart .vtt{font:700 10.5px var(--font-mono);fill:var(--bg)}
.pbx-ck{display:flex;gap:14px;flex-wrap:wrap;padding:0 16px 10px;color:var(--fg3);font-size:11px}
.pbx-ck span{display:inline-flex;align-items:center;gap:5px}
.pbx-ck i{display:inline-block;width:14px;border-top:1.5px dashed var(--fg)}.pbx-ck i.vl{border-top:1.5px dotted var(--pbx-v)}
.pbx-ck i.sq{width:9px;height:9px;border:0;border-radius:2px}.pbx-ck i.o,.pbx-ck i.o0{background:var(--pbx-g)}.pbx-ck i.u{background:var(--pbx-r)}
.pbx-ck i.o1{background:color-mix(in srgb,var(--pbx-g) 72%,#000)}.pbx-ck i.o2{background:color-mix(in srgb,var(--pbx-g) 52%,#000)}
.pbx-ck i.gh{width:10px;height:10px;border:1.2px dashed rgb(var(--ink) / .5);border-radius:2px}
.pbx-ck .na{opacity:.7}
.pbx-suph{display:flex;justify-content:space-between;align-items:center;padding:10px 16px 0}
.pbx-suph h4{margin:0;font-size:12.5px}.pbx-suph small{color:var(--fg3);font-weight:500}
.pbx-sup{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));margin-top:10px;border-top:1px solid rgb(var(--ink) / .06)}
.pbx-sup > div{padding:12px 16px;border-right:1px solid rgb(var(--ink) / .06)}
.pbx-sup > div:last-child{border-right:0}
.pbx-sup small,.pbx-tro small,.probs small,.pbx-gc small{display:block;color:var(--fg3);font-size:11px;font-weight:600}
.pbx-sup b{display:block;font:600 15px var(--font-mono);margin-top:3px}
.pbx-sup i,.pbx-tro i{font-style:normal;font-size:11px;color:var(--fg3);font-weight:500}
.pbx-vg{display:grid;grid-template-columns:1.1fr 1fr}
.pbx-vg > div{padding:14px 16px}
.pbx-vg > div + div{border-left:1px solid rgb(var(--ink) / .06)}
.pbx-vg > div > small{color:var(--fg3);font-size:11.5px}
.pbx-vg .big{display:flex;align-items:baseline;gap:10px;margin:2px 0}
.pbx-vg .big b{font-size:34px;font-weight:700;letter-spacing:-.03em}
.pbx-vg .big span{font-weight:600}
.probs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}
.probs > div{background:var(--surface2);border-radius:10px;padding:8px 10px}
.probs b{display:block;font-size:16px;font-weight:600;margin-top:2px}
.probs .fair{background:var(--pbx-vbg);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--pbx-v) 35%,transparent)}
.probs .fair b,.pbx-tro b.v,.pbx-pt td.v{color:var(--pbx-v)}
.pbx-vg .verdict{margin-top:12px;padding:10px 12px;border-radius:10px;background:var(--surface2);display:flex;gap:10px;align-items:flex-start;font-size:12.5px;color:var(--fg2)}
.pbx-vg .verdict p{margin:0}.pbx-vg .verdict b{color:var(--fg)}
#pbx-root .note{color:var(--fg3);font-size:11px;line-height:1.45;margin:10px 0 0}
.pbx-card2 > .note{padding:0 16px 12px}
.wf{display:flex;flex-direction:column;gap:6px;margin-top:8px}
.wf .base{display:flex;justify-content:space-between;font-size:12px;padding-bottom:6px;border-bottom:1px solid rgb(var(--ink) / .06)}
.wf .base.tot{border-bottom:0;border-top:1px solid rgb(var(--ink) / .06);padding:6px 0 0}
.wf .wr{display:grid;grid-template-columns:110px 1fr 48px;gap:8px;align-items:center;font-size:11.5px;color:var(--fg2)}
.wf .wr b{text-align:right;font:600 11.5px var(--font-mono)}
.wf .trk{position:relative;height:8px;border-radius:4px;background:var(--surface2)}
.wf .trk:before{content:"";position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:rgb(var(--ink) / .15)}
.wf .trk i{position:absolute;top:0;height:8px;border-radius:4px}.wf .trk i.p{background:var(--pbx-g)}.wf .trk i.n{background:var(--pbx-r)}
.pbx-pt,.pbx-lm,.pbx-dt{width:100%;min-width:0;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums}
.pbx-pt th,.pbx-lm th{color:var(--fg3);font-weight:600;font-size:11px;text-align:right;padding:8px 16px;background:var(--surface2);white-space:nowrap}
.pbx-pt td,.pbx-lm td{padding:8px 16px;text-align:right;border-top:1px solid rgb(var(--ink) / .06);white-space:nowrap}
.pbx-pt th:first-child,.pbx-pt td:first-child,.pbx-lm th:first-child,.pbx-lm td:first-child{text-align:left}
.pbx-pt tr.grp td{background:var(--surface2);color:var(--fg3);font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:6px 16px}
.pbx-pt tr.main td{background:var(--pbx-vbg)}
.pbx-pt td.best{color:var(--pbx-g);font-weight:700}
.pbx-pt .bkn{display:inline-flex;align-items:center;gap:8px;font-weight:600}
.pbx-trk{display:flex;flex-direction:column;gap:12px;padding:14px 16px 16px}
.pbx-trk .row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}
.pbx-trk label{display:flex;flex-direction:column;gap:5px;font-size:11px;font-weight:600;color:var(--fg3)}
.pbx-trk input{height:34px;width:96px;border-radius:8px;border:1px solid rgb(var(--ink) / .12);background:var(--ctl);color:var(--fg);font:600 13px var(--font-mono);padding:0 10px}
.pbx-trk input:focus,.pbx-trk select:focus{outline:2px solid color-mix(in srgb,var(--pbx-g) 60%,transparent);outline-offset:1px}
.pbx-trk .pr{display:flex;gap:6px;align-items:center}
.pbx-trk .act{display:flex;gap:12px;align-items:center}.pbx-trk .act .muted{flex:1;font-size:11.5px}
.pbx-tro{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid rgb(var(--ink) / .08);border-radius:12px;overflow:hidden}
.pbx-tro > div{padding:9px 12px;border-right:1px solid rgb(var(--ink) / .08)}
.pbx-tro > div:last-child{border-right:0}
.pbx-tro b{display:block;font-size:14px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums}
.pbx-call{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:.04em;padding:2px 8px;border-radius:5px}
.pbx-call.bet{background:color-mix(in srgb,var(--pbx-g) 22%,transparent);color:var(--pbx-g)}.pbx-call.lean{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn)}.pbx-call.pass{background:var(--surface2);color:var(--fg3)}
.pbx-mine{border-top:1px solid rgb(var(--ink) / .06);padding:4px 16px 12px}
.pbx-mine > div{display:grid;grid-template-columns:1fr auto auto auto auto;gap:14px;align-items:center;padding:8px 0;border-bottom:1px solid rgb(var(--ink) / .06);font-size:12px}
.pbx-mine .linkbtn{display:inline-block;margin-top:8px}
.pbx-rt{display:flex;gap:4px;padding:10px 12px 0}
.pbx-rt button{flex:1;padding:7px;border-radius:10px;background:none;border:0;color:var(--fg3);font-weight:600;font-size:12px}
.pbx-rt button.on{background:var(--nav-on);color:var(--fg)}
.pbx-rb{padding:12px 16px 16px}
.pbx-rb h5{margin:0 0 8px;font-size:12px}
.pbx-dt th{color:var(--fg3);font-weight:600;font-size:11px;text-align:right;padding:6px 0}
.pbx-dt td{text-align:right;padding:7px 0;border-top:1px solid rgb(var(--ink) / .06)}
.pbx-dt th:first-child,.pbx-dt td:first-child{text-align:left}
.pbx-dt tr.on td{font-weight:700}
/* prop signals card: verdict, agreement meter, agree ladder, check tiles */
.pbx-sig header{margin-bottom:4px}
.pbx-sv{margin:8px 16px 12px;padding:14px;border-radius:14px;background:rgb(var(--ink) / .035);border:1px solid rgb(var(--ink) / .08)}
.pbx-sv.strong{background:color-mix(in srgb,var(--pbx-g) 9%,transparent);border-color:color-mix(in srgb,var(--pbx-g) 32%,transparent)}
.pbx-sv.against{background:color-mix(in srgb,var(--pbx-r) 7%,transparent);border-color:color-mix(in srgb,var(--pbx-r) 28%,transparent)}
.pbx-sv .h{display:flex;align-items:baseline;gap:8px}.pbx-sv .h b{font-size:20px;font-weight:700;letter-spacing:-.01em}.pbx-sv .h span{color:var(--fg2);font-size:12.5px;text-transform:capitalize}
.pbx-sv.strong .h b{color:var(--pbx-g)}.pbx-sv.lean .h b{color:color-mix(in srgb,var(--pbx-g) 70%,var(--fg))}.pbx-sv.against .h b{color:var(--pbx-r)}
.pbx-mtr{display:flex;align-items:center;gap:4px;margin:10px 0 8px}
.pbx-mtr i{flex:1;max-width:34px;height:6px;border-radius:3px;background:rgb(var(--ink) / .1)}
.pbx-mtr i.a{background:var(--pbx-g)}.pbx-mtr i.d{background:var(--pbx-r)}
.pbx-mtr span{margin-left:8px;color:var(--fg2);font-size:11.5px;white-space:nowrap}
.pbx-sv .hl{margin:0;font-size:12px;color:var(--fg2)}.pbx-sv .hl b{font:600 12.5px var(--font-mono);color:var(--fg)}.pbx-sv .hl span{color:var(--fg3)}
.pbx-sv .hl b.pos{color:var(--pbx-g)}.pbx-sv .hl b.neg{color:var(--pbx-r)}
.pbx-lad{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:0 16px 12px}
.pbx-lad div{display:flex;flex-direction:column;gap:1px;padding:8px 9px;border-radius:10px;border:1px solid rgb(var(--ink) / .07)}
.pbx-lad div.on{border-color:color-mix(in srgb,var(--pbx-g) 45%,transparent);background:color-mix(in srgb,var(--pbx-g) 7%,transparent)}
.pbx-lad small{color:var(--fg3);font-size:10px}.pbx-lad b{font:600 13px var(--font-mono)}
.pbx-lad i{font:500 10.5px var(--font-mono);font-style:normal;color:var(--fg3)}.pbx-lad i.pos{color:var(--pbx-g)}.pbx-lad i.neg{color:var(--pbx-r)}
.pbx-lad em{font-style:normal;font-size:9.5px;color:var(--fg3)}
.pbx-sg{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin:0 16px 10px}
.pbx-st{display:flex;flex-direction:column;gap:3px;padding:9px 10px;border-radius:10px;background:rgb(var(--ink) / .03);border:1px solid rgb(var(--ink) / .06);border-left:3px solid rgb(var(--ink) / .12);min-width:0}
.pbx-st.a{border-left-color:var(--pbx-g)}.pbx-st.d{border-left-color:var(--pbx-r)}.pbx-st.m{border-left-color:var(--pbx-v)}.pbx-st.ctx{opacity:.7;border-left-style:dashed}
.pbx-st .t{display:flex;align-items:center;gap:6px}.pbx-st .t small{color:var(--fg3);font-size:10.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pbx-st .t span{margin-left:auto;font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--fg3)}
.pbx-st.a .t span{color:var(--pbx-g)}.pbx-st.d .t span{color:var(--pbx-r)}.pbx-st.m .t span{color:var(--pbx-v)}
.pbx-st b{font:600 13px var(--font-mono);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pbx-st i{font-style:normal;font-size:10px;color:var(--fg3)}.pbx-st i.pos{color:var(--pbx-g)}.pbx-st i.neg{color:var(--pbx-r)}
.pbx-sig .note a{color:var(--fg);text-decoration:underline}
.pbx-inj{display:flex;justify-content:space-between;padding:7px 0;border-top:1px solid rgb(var(--ink) / .06);font-size:12px}
.pbx-inj:first-child{border-top:0}.pbx-inj small{color:var(--fg3)}
.pbx-inj b.neg{color:var(--pbx-r)}.pbx-inj b.warn{color:var(--warn)}
.pbx-gc{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.pbx-gc > div{background:var(--surface2);border-radius:10px;padding:9px 10px}
.pbx-gc b{display:block;font-size:14px;font-weight:600;margin-top:2px}
.pbx-card2 > .pbx-lm + .note{padding:0 16px 12px}

.pbx-wins{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.pbx-wins .pbx-alt{max-width:260px}.pbx-wins #pbx-mate{margin-left:auto}
.pbx-mf{display:inline-flex;align-items:center;gap:6px;margin-left:12px;padding:1px 4px 1px 9px;border-radius:var(--r-pill);background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn);font-weight:700}
.pbx-mf button{background:none;border:0;color:inherit;font-size:13px;padding:0 3px}
.pbx-st td small{color:var(--fg3);font-weight:500}
.pbx-st tr.cl{cursor:pointer}.pbx-st tr.cl:hover td{background:var(--surface2)}
.pbx-st .pbx-hc{height:24px}
.pbx-otag{font-size:9.5px;font-weight:800;padding:1px 5px;border-radius:4px;margin-left:6px;background:color-mix(in srgb,var(--pbx-r) 16%,transparent);color:var(--pbx-r)}
.pbx-otag.q{background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn)}
.pbx-o4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}
.pbx-o4 > div{padding:12px 16px;border-right:1px solid rgb(var(--ink) / .06)}
.pbx-o4 > div:last-child{border-right:0}
.pbx-o4 small{display:flex;justify-content:space-between;color:var(--fg3);font-size:11px;font-weight:600}
.pbx-o4 b{display:block;font:600 18px var(--font-mono);margin:2px 0 6px}
.pbx-o4 b i{font-style:normal;font-size:11px;margin-left:5px}
.pbx-o4 svg{display:block;width:100%;height:44px}
.pbx-o4 rect{fill:var(--raised)}.pbx-o4 rect.r5{fill:var(--fg3)}
.pbx-lc{padding:8px 12px 0}.pbx-lc svg{display:block;width:100%;height:auto}
.pbx-lc .gl{stroke:rgb(var(--ink) / .07)}.pbx-lc .ax{font:500 9.5px var(--font-sans);fill:var(--fg3)}
.pbx-lc .st{stroke:var(--pbx-g);stroke-width:2;fill:none}.pbx-lc .pt{fill:var(--pbx-g)}.pbx-lc .px{font:600 9px var(--font-mono);fill:var(--fg2)}
@media (max-width:760px){
  .pbx-o4{grid-template-columns:1fr 1fr}
  .pbx-o4 > div:nth-child(2){border-right:0}
  .pbx-o4 > div:nth-child(-n+2){border-bottom:1px solid rgb(var(--ink) / .06)}
  .pbx-wins .pbx-alt{margin-left:0;max-width:none;width:100%}
  .pbx-detail{grid-template-columns:minmax(0,1fr)}
  .pbx-dh .acts{margin-left:0;width:100%}
  .pbx-sup{grid-template-columns:repeat(3,minmax(0,1fr))}
  .pbx-sup > div:nth-child(3){border-right:0}
  .pbx-sup > div:nth-child(-n+3){border-bottom:1px solid rgb(var(--ink) / .06)}
  .pbx-vg{grid-template-columns:1fr}
  .pbx-vg > div + div{border-left:0;border-top:1px solid rgb(var(--ink) / .06)}
  .pbx-tro{grid-template-columns:repeat(2,1fr)}
  .pbx-tro > div{border-bottom:1px solid rgb(var(--ink) / .08)}
  .pbx-trk .act{flex-direction:column;align-items:stretch}
  .pbx-pt th,.pbx-pt td{padding:8px 10px}
  .pbx-fpanel{grid-template-columns:1fr;gap:12px}
  .pbx-n{margin-left:0;width:100%}
  .pbx-fb.q{flex:1}.pbx-fb.q input{width:100%}
  .pbx-key{display:none}
  .pbx-tbl{background:none;border:0;overflow:visible}
  .pbx-scroll{overflow:visible}
  .pbx-th,.pbx-tr{display:none}
  .pbx-row{border:1px solid rgb(var(--ink) / .08);border-radius:14px;background:var(--surface);margin-bottom:10px;overflow:hidden}
  .pbx-card{display:flex;flex-direction:column;gap:8px;width:100%;padding:12px;background:none;border:0;color:var(--fg);text-align:left}
  .pbx-card .t{display:flex;gap:10px;align-items:center}
  .pbx-card .who{display:flex;flex-direction:column;align-items:flex-start;text-align:left}
  .pbx-card .who b{display:flex;gap:6px;align-items:center;font-weight:600}
  .pbx-card .who small{color:var(--fg3);font-size:11.5px}
  .pbx-card .m{display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border-radius:9px;background:var(--surface2);font-size:12.5px}
  .pbx-card .q{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
  .pbx-card .q > span{display:flex;flex-direction:column;padding:6px 8px;border-radius:8px;background:var(--surface2)}
  .pbx-card .q small,.pbx-card .hh small{font-size:10px;color:var(--fg3)}
  .pbx-card .q b{font-weight:600;font-variant-numeric:tabular-nums}
  .pbx-card .hh{display:grid;grid-template-columns:repeat(6,1fr);gap:4px;text-align:center}
  .pbx-card .hh .pbx-hc{width:100%;height:24px}
  .pbx-row .sc-dt{padding:0 8px 8px}
}
@media (prefers-reduced-motion:reduce){.pbx-g,.pbx-tr,.pbx-tabs .pbx-ul{transition:none}}`;
    document.head.appendChild(st);
  }

  let wired = false;
  return {
    render(B){ if (!wired){ wire(); wired = true; } render(B); },
    trackCard,
  };
})();
