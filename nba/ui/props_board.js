// Props Table, Outlier layout (render_app.py inlines this at /*PROPS_BOARD_JS*/).
// One row per prop AND side, colored hit-rate tiles, opponent rank by position, Vault's projection, fair and edge,
// and a Filters panel whose venue switches re-pick the best price. Every number comes from the page's own pricing
// (priceRow, scOf, windowGames, hitRate): nothing here prices a prop. A row opens the existing detail drawer
// (scDetail), so the Kalshi ladder, every book and Log bet work exactly as before.
window.PBX = (() => {
  const LS = 'nba-pbx-f', LSC = 'nba-pbx-classic';
  const FDEF = {ven: {book: 1, kalshi: 1, poly: 1, pickem: 1}, gate: 'any', minEdge: null, minGap: null, minL10: null, oppFav: false, oMin: '', oMax: '', healthy: false, starters: false, moved: 'any'};
  const load = () => { try{ const f = JSON.parse(localStorage.getItem(LS)); return f ? {...FDEF, ...f, ven: {...FDEF.ven, ...(f.ven || {})}} : JSON.parse(JSON.stringify(FDEF)); }catch(e){ return JSON.parse(JSON.stringify(FDEF)); } };
  const S = {stat: 'all', side: 'all', game: 'all', q: '', sort: 'edge', dir: -1, limit: 60, fOpen: false, f: load(), open: null};
  const save = () => { try{ localStorage.setItem(LS, JSON.stringify(S.f)); }catch(e){} };
  const classic = () => { try{ return localStorage.getItem(LSC) === '1'; }catch(e){ return false; } };
  const setClassic = on => { try{ on ? localStorage.setItem(LSC, '1') : localStorage.removeItem(LSC); }catch(e){} };

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
      <div><h6>Player and matchup</h6><div>${o('oppFav', 1, 'Soft matchup', f.oppFav)}${o('healthy', 1, 'No injury tag', f.healthy)}${o('starters', 1, 'Starters only', f.starters)}</div></div>
      <div class="ft"><span class="muted">${n.toLocaleString()} props match. Venues change which price counts as best.</span><button type="button" class="btn" data-freset="1">Reset</button><button type="button" class="btn primary" data-fdone="1">Done</button></div></div>`;
  }

  function render(B){
    css();
    const root = $('pbx-root'), games = (B.games || []).filter(g => g.tip > Date.now() / 1000).sort((a, b) => a.tip - b.tip);
    if (S.game !== 'all' && !games.some(g => String(g.id) === S.game)) S.game = 'all';
    const all = build(B), rows = filtered(all), show = rows.slice(0, S.limit);
    pf.rows = show.map(x => x.r);                    // the shared drawer's Log and Watch buttons look rows up here
    WIN[4][1] = szn(GL.current_season); WIN[5][1] = szn(GL.current_season - 1);
    const statsOn = STATS.filter(([k]) => k === 'all' || all.some(x => x.r.e.s === k));
    const th = (k, l, c, v) => `<button type="button" class="${c ? 'c ' : ''}${v ? 'v ' : ''}${S.sort === k ? 'on' : ''}" data-sort="${k}" aria-sort="${S.sort === k ? (S.dir > 0 ? 'ascending' : 'descending') : 'none'}">${l}${S.sort === k ? `<i>${S.dir > 0 ? '▲' : '▼'}</i>` : ''}</button>`;
    const act = fActive();
    const row = (x, i) => { const r = x.r, h = hits(x), key = `${r.e.p}|${r.e.s}|${x.side}`, open = S.open === key, w = pvW[pvKey(r)];
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
        ${open ? `<div class="sc-dt">${scDetail(r, scFacts(r), [LU_PLAIN[r.lu], r.inj].filter(Boolean).join(' · '))}</div>` : ''}</article>`; };
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
        <span class="pbx-n">${rows.length.toLocaleString()} / ${all.length.toLocaleString()} props</span>
        <button type="button" class="linkbtn" data-classic="1">Classic table</button>
      </div>
      ${S.fOpen ? filterPanel(rows.length) : ''}
      ${act.length ? `<div class="pbx-chips">${act.map(([k, l]) => `<span>${esc(l)}<button type="button" data-fclear="${k}" aria-label="Remove ${esc(l)}">×</button></span>`).join('')}</div>` : ''}
      <p class="pbx-key"><span class="v">Vault model columns</span><span>Hit rates: share of games over (or under) tonight's line</span><span>Opp rank: 1st allows the fewest to his position, 30th the most</span></p>
      <div class="pbx-tbl"><div class="pbx-scroll">
        <div class="pbx-th"><span></span>${th('prop', 'Proposition')}${th('line', 'Line', 1)}${th('odds', 'Best odds')}${th('proj', 'Vault proj', 1, 1)}${th('fair', 'Fair', 1, 1)}${th('edge', 'Edge', 1, 1)}${th('opp', 'Opp rank', 1)}${WIN.map(([k, l]) => th(k, l, 1)).join('')}</div>
        ${show.map(row).join('') || `<p class="empty" style="padding:24px">${all.length ? 'No props match these filters.' : 'Nothing on the board yet.'}</p>`}
      </div></div>
      ${rows.length > S.limit ? `<div class="pbx-more"><button type="button" class="btn" data-more="1">Show ${Math.min(60, rows.length - S.limit)} more</button></div>` : ''}`;
    root._show = show;
  }

  function rerender(){ renderProps(); }
  function wire(){
    const root = $('pbx-root');
    root.addEventListener('click', e => {
      if (pbClick(e, rerender)) return;                                   // Log / Watch inside the shared drawer
      const t = e.target, b = t.closest('[data-game],[data-stat],[data-side],[data-sort],[data-f],[data-fclear],[data-fopen],[data-freset],[data-fdone],[data-more],[data-classic],[data-w],[data-lab]');
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
        else if (d.classic){ setClassic(true); }
        else if (d.f){ const k = d.f, f = S.f;
          if (k === 'ven'){ f.ven[d.v] = f.ven[d.v] ? 0 : 1; if (!Object.values(f.ven).some(Boolean)) f.ven[d.v] = 1; }
          else if (k === 'oppFav' || k === 'healthy' || k === 'starters') f[k] = !f[k];
          else { const v = d.v === 'null' ? null : isNaN(+d.v) ? d.v : +d.v; f[k] = v; }
          save(); S.limit = 60; }
        rerender(); return;
      }
      const tr = t.closest('.pbx-tr, .pbx-card');
      if (tr){ const x = root._show[+tr.closest('.pbx-row').dataset.i], k = `${x.r.e.p}|${x.r.e.s}|${x.side}`; S.open = S.open === k ? null : k; pf.logKey = pf.logIdx = null; rerender(); }
    });
    root.addEventListener('submit', e => { e.preventDefault(); pbSubmit(e, rerender); });
    root.addEventListener('change', e => { const i = e.target.closest('[data-fodds]'); if (i){ S.f[i.dataset.fodds] = i.value.trim(); save(); rerender(); } });
    let qT = null;
    root.addEventListener('input', e => { if (e.target.id !== 'pbx-q') return; S.q = e.target.value; clearTimeout(qT);
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
.pbx-prop .who{display:flex;flex-direction:column;min-width:0}
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
@media (max-width:760px){
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
@media (prefers-reduced-motion:reduce){.pbx-g,.pbx-tr{transition:none}}`;
    document.head.appendChild(st);
  }

  let wired = false;
  return {
    classic, setClassic,
    render(B){ if (!wired){ wire(); wired = true; } render(B); },
  };
})();
