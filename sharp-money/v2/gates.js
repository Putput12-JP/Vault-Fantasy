/* Sharp Money V2 gates. One copy of the rules, read by the page (sharp-money/v2/index.html, as a plain script) and by the headless ledger
   (scripts/track-v2-plays.mjs, as a CommonJS module), so the plays the page shows and the plays the ledger records cannot drift apart.
   tests/v2_gates.test.mjs runs the page and this module on the same stored data and fails if they disagree.

   Sharp-account money is context only: nothing in here reads it, ranks by it or counts it toward an agree total.
   Evidence behind every gate: docs/retro/sharp-v2-evidence.md (PR 133) and docs/retro/sharp-v2-data.md (PR 134).

   Every function takes the loaded files in one object, X = { D: data.json, P: props.json, T: prop_close_tape.json, E: exchange_edge_live.json, now: unix seconds }. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.V2Gates = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  /* Gates. Every number here is either a stored measurement or was fixed before looking and is not tuned (docs/signal-research.md rule). */
  const GATES = {
    MIN_EDGE: 0.02,      // each independent reference must say the price beats fair by 2%+ (Data Golf: the best ROI sat at a 2% threshold, 5% was worse)
    AGREE: 0.04,         // Pinnacle and the exchange fair must sit within 4 probability points, else one of them is wrong
    BIG_EDGE: 0.10,      // 10%+ calls: 21-32, ROI -15.0% on 53 settled (evidence PR). Usually a stale or moved line
    MAX_AGE: 45 * 60,    // a reference read older than this is not a price
    EARLY_H: 48,         // calls 48h+ out: 110-159, ROI -16.3% on 269 settled
    DFS: new Set(['Sleeper', 'Underdog', 'Underdog Fantasy', 'PrizePicks', 'Fliff', 'Dabble'])};
  const US = new Set(['Caesars', 'FanDuel', 'DraftKings', 'bet365', 'BetMGM', 'BetRivers', 'Fanatics', 'Parx Casino', 'Hard Rock', 'ESPN BET']);
  const EXCH = ['Kalshi', 'Novig'];
  const MKT = { ml: 'Money', sp: 'Spread', tot: 'Total' };

  const pct = (x, d = 1) => x == null ? '-' : (x * 100).toFixed(d) + '%';
  const spct = (x, d = 1) => x == null ? '-' : (x > 0 ? '+' : x < 0 ? '-' : '') + Math.abs(x * 100).toFixed(d) + '%';
  const sgn = n => n == null ? '-' : (n > 0 ? '+' : '') + n;

  /* ---- price math: same methods as scripts/prop_close_lib.py ---- */
  const imp = a => a == null || a === 0 ? null : a < 0 ? -a / (-a + 100) : 100 / (a + 100);
  function devig(o, u) { const po = imp(o), pu = imp(u); if (!po || !pu) return null; if (po + pu <= 1) return po / (po + pu); let lo = 1, hi = 10; for (let i = 0; i < 40; i++) { const k = (lo + hi) / 2; if (Math.pow(po, k) + Math.pow(pu, k) > 1) lo = k; else hi = k } const k = (lo + hi) / 2; return Math.pow(po, k) / (Math.pow(po, k) + Math.pow(pu, k)) }
  const bookP = (e, line) => { if (!e) return null; if (e.ladder) { for (const r of e.ladder) if (Math.abs(r[0] - line) < 1e-9) return r[1]; return null } if (e.line == null || line == null || Math.abs(e.line - line) > 1e-9) return null; return devig(e.over, e.under) };
  const sideP = (po, side) => po == null ? null : side === 'over' ? po : 1 - po;
  const mean = a => a.length ? a.reduce((s, x) => s + x, 0) / a.length : null;

  /* ---- candidates: everything that could be a play, with the gate result ---- */
  const _tapeIdx = new WeakMap();
  function tapeIndex(T) {
    if (!T || !T.props) return {};
    let m = _tapeIdx.get(T); if (m) return m;
    m = {}; for (const [k, v] of Object.entries(T.props)) { const q = k.split('|'); (m[q[0] + '|' + q[1] + '|' + q[2]] || (m[q[0] + '|' + q[1] + '|' + q[2]] = [])).push(v) }
    _tapeIdx.set(T, m); return m;
  }
  function refsAt(X, entry, line) {
    const r = {}; if (!entry || !entry.books) return r; const ko = Date.parse(entry.commence) / 1000, p = {};
    for (const [b, e] of Object.entries(entry.books)) { if (e.t == null || e.t >= ko || X.now - e.t > GATES.MAX_AGE) continue; const v = bookP(e, line); if (v != null) p[b] = v }
    if (p.Pinnacle != null) r.pin = p.Pinnacle;
    const ex = EXCH.filter(b => p[b] != null).map(b => p[b]); if (ex.length) r.exch = mean(ex);
    const us = [...US].filter(b => p[b] != null).map(b => p[b]); if (us.length) r.books = mean(us);
    return r;
  }
  function judge(c) {
    /* c.refs: [{n,p}] fair chance of THIS side from each independent reference. Returns tier + reasons. */
    const rs = c.refs; c.refs.forEach(r => r.edge = r.p / c.price.p - 1);
    const edges = rs.map(r => r.edge); c.worst = edges.length ? Math.min(...edges) : null; c.best = edges.length ? Math.max(...edges) : null;
    const weak = c.best == null || c.best < GATES.MIN_EDGE;
    if (c.price.dfs) { c.tier = weak ? 'none' : 'pass'; c.reasons = ['Pick’em app price. It is a flat price, not a market, so it is not checked against fair.']; return c }
    if (c.price.exch) { c.tier = weak ? 'none' : 'pass'; c.reasons = ['The only price is at an exchange, the same market used as the check.']; return c }
    if (c.contradicted) { c.tier = weak ? 'none' : 'pass'; c.reasons = ['Both sides of this market look good against a reference. That is noise, not an edge.']; return c }
    if (rs.length < 2) { c.tier = (rs.length === 1 && c.best >= GATES.MIN_EDGE) ? 'watch' : 'none'; c.reasons = rs.length === 1 ? ['One reference only (' + rs[0].n + '). A play needs two independent prices to agree.'] : ['No fair price from Pinnacle or an exchange right now.']; return c }
    const gap = Math.abs(rs[0].p - rs[1].p);
    if (gap > GATES.AGREE) { c.tier = 'pass'; c.reasons = ['Pinnacle and the exchange disagree by ' + (gap * 100).toFixed(1) + ' points, so neither is trusted.']; return c }
    if (c.worst < GATES.MIN_EDGE) { c.tier = c.best >= GATES.MIN_EDGE ? 'pass' : 'none'; c.reasons = ['Does not beat both references by ' + pct(GATES.MIN_EDGE, 0) + ' (' + rs.map(r => r.n + ' ' + spct(r.edge)).join(', ') + ').']; return c }
    if (c.worst > GATES.BIG_EDGE) { c.tier = 'pass'; c.reasons = ['An edge over ' + pct(GATES.BIG_EDGE, 0) + ' is usually a stale or moved line. Calls this size went 21-32 (ROI -15%) on 53 settled.']; return c }
    c.tier = 'play'; c.reasons = ['The price beats both references by ' + pct(GATES.MIN_EDGE, 0) + ' or more and they agree within ' + (GATES.AGREE * 100) + ' points.']; return c;
  }
  function propCands(X) {
    const { P, T, now: NOW } = X, out = []; if (!P || !P.props || !P.props.rows) return out; const idx = tapeIndex(T), season = P.props.season;
    for (const row of P.props.rows) {
      const list = idx[season + '|' + row.pid + '|' + row.mkt] || [], ent = list.map(v => ({ v, t: Date.parse(v.commence) / 1000 })).filter(x => x.t > NOW - 3600).sort((a, b) => a.t - b.t)[0], entry = ent ? ent.v : null, start = ent ? ent.t : null;
      if (start && start < NOW) continue;                                   // started: not a pregame price
      const refs = refsAt(X, entry, row.line);
      for (const side of ['over', 'under']) {
        const vs = (row[side] && row[side].venues) || [];
        const cands = vs.filter(v => v.p != null);
        const book = cands.filter(v => v.kind === 'book' && US.has(v.src)).sort((a, b) => a.p - b.p)[0];
        const dfs = cands.filter(v => GATES.DFS.has(v.src)).sort((a, b) => a.p - b.p)[0];
        const ex = cands.filter(v => v.kind === 'exchange').sort((a, b) => a.p - b.p)[0];
        const v = book || dfs || ex; if (!v) continue;
        const rl = []; const pp = sideP(refs.pin, side), xp = sideP(refs.exch, side);
        if (pp != null) rl.push({ n: 'Pinnacle', p: pp }); if (xp != null) rl.push({ n: 'Exchange', p: xp });
        const cx = [];
        if (row.pos === 'QB') cx.push('QB props: 114-145, ROI -11.9% on 259 settled.');
        if (start && (start - NOW) / 3600 > GATES.EARLY_H) cx.push('More than ' + GATES.EARLY_H + ' hours out. Early calls decay: 110-159, ROI -16.3% on 269 settled.');
        const bp = sideP(refs.books, side); if (bp != null && bp / v.p - 1 < 0) cx.push('The average of the US books does not agree it is a good price.');
        for (const t of ((row.call && row.call.side === side && row.call.check) || [])) cx.push(t.charAt(0).toUpperCase() + t.slice(1) + '.');
        const rec = P.propRecord && P.propRecord.byMarket && P.propRecord.byMarket[row.label];
        const c = { id: 'p|' + row.pid + '|' + row.mkt + '|' + row.line + '|' + side, kind: 'prop', sport: 'nfl', start,
          title: row.name + ' ' + (side === 'over' ? 'Over' : 'Under') + ' ' + row.line + ' ' + row.label, sub: row.team + ' ' + row.pos,
          price: { am: v.am, p: v.p, book: v.src, dfs: v.kind === 'book' && GATES.DFS.has(v.src), exch: v.kind === 'exchange' },
          refs: rl, cautions: cx, market: row.label, rec: rec || null, row, side };
        if (v.kind === 'book' && GATES.DFS.has(v.src)) c.price.dfs = true;
        out.push(c);
      }
    }
    return out;
  }
  function gameCands(X) {
    const { D, E, now: NOW } = X, out = []; if (!D) return out; const G = Object.fromEntries((D.games || []).map(g => [g.key, g]));
    /* a) Novig priced below Pinnacle fair (data/exchange_edge_live.json), with Kalshi and Polymarket as the second prices */
    for (const r of (E && E.rows) || []) {
      if (r.start <= NOW || r.ev == null) continue; const g = G[r.gk];
      const rl = [{ n: 'Pinnacle', p: r.fair }];
      if (r.second) { if (r.second.kal != null) rl.push({ n: 'Kalshi', p: r.second.kal }); if (r.second.pm != null) rl.push({ n: 'Polymarket', p: r.second.pm }) }
      const label = r.m === 'ml' ? r.label + ' to win' : r.label;      // a spread or total label already carries its line ("ORL -2.5", "Under 231.5")
      out.push({ id: 'e|' + r.gk + '|' + r.m + '|' + r.label + '|' + r.line, kind: 'exch', sport: r.sport, start: r.start, gk: r.gk, m: r.m, side: r.label, title: label, sub: r.away + ' @ ' + r.home + ' (' + MKT[r.m] + ')',
        price: { am: +String(r.price).replace('+', ''), p: r.cost, book: 'Novig', exch: false }, refs: rl, cautions: r.nm != null && Math.abs(r.nm) >= 0.5 ? ['Novig has moved ' + sgn(r.nm) + ' points since the last read.'] : [], game: g, market: MKT[r.m], gameLive: true, edgeRow: r });
    }
    /* b) a US book still hanging a price Pinnacle's ladder says is +EV. The second price exists for the moneyline only. */
    for (const g of D.games || []) {
      if (g.start <= NOW || !g.behind) continue;
      for (const b of g.behind) {
        const rl = [{ n: 'Pinnacle', p: b.fair }];
        if (b.m === 'ml') {
          const nm = g.nov && g.nov.ml && g.nov.ml.mid, kl = g.kal && g.kal.bid != null && g.kal.ask != null ? (g.kal.bid + g.kal.ask) / 2 : null;
          const x = [nm, kl].filter(v => v != null).map(v => b.side === 'home' ? v : 1 - v); if (x.length) rl.push({ n: 'Exchange', p: mean(x) });
        }
        const t = g[b.side]; const nm2 = t ? t.short || t.name : b.side;
        const title = b.m === 'ml' ? nm2 + ' to win' : b.m === 'sp' ? nm2 + ' ' + sgn(b.side === 'home' ? b.hline : -b.hline) : (b.side === 'over' ? 'Over ' : 'Under ') + b.line;
        out.push({ id: 'b|' + g.key + '|' + b.m + '|' + b.side + '|' + b.book + '|' + b.line, kind: 'book', sport: g.sport, start: g.start, gk: g.key, m: b.m, side: b.side, title, sub: g.away.abbr + ' @ ' + g.home.abbr + ' (' + MKT[b.m] + ')',
          price: { am: b.price, p: imp(b.price), book: b.book, dfs: false, exch: false }, refs: rl, cautions: [], game: g, market: MKT[b.m], bookRow: b });
      }
    }
    /* one row per pick: when several US books hang the same side, keep the best price */
    const best = {};
    out.forEach(c => { if (c.kind !== 'book') return; const k = c.gk + '|' + c.m + '|' + c.side + '|' + (c.line == null ? '' : c.line) + c.title; if (!best[k] || c.price.p < best[k].price.p) best[k] = c });
    return out.filter(c => c.kind !== 'book' || best[c.gk + '|' + c.m + '|' + c.side + '|' + (c.line == null ? '' : c.line) + c.title] === c);
  }
  /* Every candidate with its tier, and the ones that are not 'none' ranked by worst-case edge. */
  function build(X) {
    const all = [...propCands(X), ...gameCands(X)];
    /* contradictions: both sides of one market clearing any reference at once */
    const seen = {};
    all.forEach(c => { if (c.refs.some(r => r.p / c.price.p - 1 >= GATES.MIN_EDGE)) { const k = c.kind === 'prop' ? c.row.pid + '|' + c.row.mkt + '|' + c.row.line : c.gk + '|' + c.m; (seen[k] || (seen[k] = new Set())).add(c.side) } });
    all.forEach(c => { const k = c.kind === 'prop' ? c.row.pid + '|' + c.row.mkt + '|' + c.row.line : c.gk + '|' + c.m; c.contradicted = (seen[k] && seen[k].size > 1) || false; judge(c) });
    const cand = all.filter(c => c.tier !== 'none').sort((a, b) => (b.worst == null ? -9 : b.worst) - (a.worst == null ? -9 : a.worst));
    cand.noneCount = all.length - cand.length;
    return { all, cand };
  }

  return { GATES, US, EXCH, MKT, pct, spct, sgn, imp, devig, bookP, sideP, mean, tapeIndex, refsAt, judge, propCands, gameCands, build };
});
