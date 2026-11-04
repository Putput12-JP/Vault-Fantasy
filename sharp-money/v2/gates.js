/* Sharp Money V2 gates. One copy of the rules, read by the page (sharp-money/v2/index.html, as a plain script) and by the headless ledger
   (scripts/track-v2-plays.mjs, as a CommonJS module), so the plays the page shows and the plays the ledger records cannot drift apart.
   tests/v2_gates.test.mjs runs the page and this module on the same stored data and fails if they disagree.

   Sharp-account money is context only: nothing in here reads it, ranks by it or counts it toward an agree total.
   Evidence behind every gate: docs/retro/sharp-v2-evidence.md (PR 133) and docs/retro/sharp-v2-data.md (PR 134).

   Every function takes the loaded files in one object, X = { D: data.json, P: props.json, T: prop_close_tape.json, E: exchange_edge_live.json, N: nba-live board.json (optional: no NBA props without it), now: unix seconds }. */
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
    MAX_EXCH_SPREAD: 0.06, // an exchange quote wider than 6 points says where it is for sale, not where the market is (the same cut the ledger uses for a close)
    EARLY_H: 48,         // calls 48h+ out: 110-159, ROI -16.3% on 269 settled. Since the strict gates a play must also be inside this window (18-27, ROI -21.7% on 45 settled live plays)
    MIN_PRICE: 0.55,     // strict gate: ROI rises with price (-26% under 50%, +2% at 50-55%, +16% at 55-60%, +24% at 60-65%) and it repeats in the Watch and Passed ledgers. 33-11 (75%) once this and the 48h gate are applied (docs/retro/sharp-v2-strict-gates.md)
    /* Rule C, NBA props only, in place of MIN_PRICE (docs/retro/nba-fair-agreement-rule.md). Found by searching NBA prop rows Oct 20 - Nov 2, 2026, so the
       rebuilt record before NBA_FAIR_SINCE is in-sample: 1,958 settled rows, rules picked on Oct 20-27 and checked once on Oct 28 - Nov 2. */
    NBA_FAIR_AGREE: 0.01,  // Pinnacle and the exchange fair under 1 point apart (not 4) and Kalshi quoting the line. Rebuilt: 69-45, ROI +13.6% on 114; first seen before Oct 28 +20.7% (49), Oct 28 on +8.2% (65)
    NBA_MIN_EDGE: 0.03,  // and the price beats the exchange by 3%+, not 2%. Rebuilt under rule C: 3%+ went 32-16 (ROI +29.1%) on 48, 2-3% went 37-29 (+2.3%) on 66. In-sample, picked Nov 3
    NBA_CAP: 5,          // at most 5 NBA prop plays a night: the top 5 by edge over the exchange an hour before the night's first tip, later plays fill open slots.
                         // Rebuilt under rule C at 3%: 29-12 (ROI +34.9%) on 41 vs 32-16 (+29.1%) uncapped; the first 5 seen instead went 27-14 (+25.9%). In-sample, picked Nov 4
    NBA_LOCK_MIN: 60,
    NBA_CAP_SINCE: 1793795408, // the cap shipped Nov 4, 2026 6:30 AM Central. NBA props logged before it for a night that locks after it compete at the lock like any other
                         // candidate: the ledger stamps each capPick or capOut then (capStamp), instead of letting them hold the night's slots    // minutes before the night's first NBA tip when the top plays lock
    NBA_FAIR_SINCE: 1793750400, // Nov 3, 2026 6:00 PM Central: NBA prop rows first seen before this are re-scored from stored fields, after it they were judged live
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
  /* The two strict gates, from stored fields only so the same test re-scores a ledger row (heldBack) and judges a live candidate (held). */
  const EARLY_WHY = 'Called ' + GATES.EARLY_H + ' hours or more before the game. Early calls decay: 18-27 (ROI -22%) on 45 settled live plays, 110-159 (ROI -16%) on 269 before that.';
  const PRICE_WHY = 'The price is under ' + Math.round(GATES.MIN_PRICE * 100) + '%. Plays priced under that went 67-79 (ROI -6%) on 146 settled live plays; at ' + Math.round(GATES.MIN_PRICE * 100) + '% and up inside ' + GATES.EARLY_H + ' hours they went 33-11 (ROI +26%).';
  const hoursOut = x => x == null ? null : x.hoursOut != null ? x.hoursOut : x.start != null && x.firstSeen != null ? (x.start - x.firstSeen) / 3600 : x.hoursEarly != null ? x.hoursEarly : null;
  const FAIR_WHY = gap => 'Pinnacle and the exchange are ' + (gap * 100).toFixed(1) + ' points apart. NBA props need them under ' + Math.round(GATES.NBA_FAIR_AGREE * 100) + ' point apart: rebuilt, those went 69-45 (ROI +13.6%) on 114 settled, and 1 point or more apart went 37-52 (ROI -21.7%) on 89.';
  const NBA_EDGE_WHY = e => 'The price beats the exchange by ' + spct(e) + '. NBA props need ' + Math.round(GATES.NBA_MIN_EDGE * 100) + '% or more: rebuilt, 3%+ went 32-16 (ROI +29%) on 48 settled and 2-3% went 37-29 (ROI +2%) on 66.';
  const KAL_WHY = 'Kalshi is not quoting this line. NBA props need Kalshi as one of the two exchange prices behind the fair.';
  const nbaProp = c => c && c.sport === 'nba' && c.kind === 'prop';
  function held(c) {
    const out = [];
    if (nbaProp(c)) {
      /* rule C: the fairs agree within 1 point and Kalshi quotes the line. The price floor does not apply: this rule's wins sit under 55%. */
      const ex = (c.refs || []).find(r => r.n === 'Exchange'), pn = (c.refs || []).find(r => r.n === 'Pinnacle');
      const gap = ex && pn ? Math.abs(ex.p - pn.p) : null;
      if (gap == null || gap >= GATES.NBA_FAIR_AGREE) out.push(FAIR_WHY(gap == null ? 1 : gap));
      if (!c.price || !c.price.kal) out.push(KAL_WHY);
      if (ex && ex.edge < GATES.NBA_MIN_EDGE) out.push(NBA_EDGE_WHY(ex.edge));
    } else if (c.price && c.price.p != null && c.price.p < GATES.MIN_PRICE) out.push(PRICE_WHY);
    if (c.hoursOut != null && c.hoursOut >= GATES.EARLY_H) out.push(EARLY_WHY);
    return out;
  }
  /* Kalshi at first sight for NBA prop rows logged before rows stored it (data/v2_nba_kalshi_reads.json, scripts/build_v2_nba_kalshi_reads.py):
     { rows: { id: [bid, ask, read time] | null } }. A row with no stored flag and no read counts as Kalshi absent. */
  let KAL_READS = null;
  function setKalshiReads(x) { KAL_READS = x && x.rows ? x : null; }
  function kalshiAt(p) {
    const px = p.first && p.first.price;
    if (px && px.kal != null) return !!px.kal;
    const r = KAL_READS && KAL_READS.rows[p.id];
    return !!(r && r[0] != null && r[1] != null && r[0] > 0 && r[1] >= r[0] && r[1] - r[0] <= GATES.MAX_EXCH_SPREAD);
  }
  /* A stored ledger row (live or backfilled) judged by the current gates at its first sight: [] if it still qualifies, else the gates it fails.
     Games and NFL props: 'price', 'early'. NBA props: rule C, 'fairs' (gap 1 point or more), 'kalshi' (not quoting), 'edge' (exchange edge outside
     3-10% (NBA_MIN_EDGE) or Pinnacle the other way, which a row from the Passed ledger can fail), 'early'. */
  function heldBack(p) {
    const f = (p && p.first) || {}, px = f.price || {}, h = hoursOut(p), out = [];
    if (p && p.sport === 'nba' && p.kind === 'prop') {
      const ex = (f.refs || []).find(r => r.n === 'Exchange'), pn = (f.refs || []).find(r => r.n === 'Pinnacle');
      if (!ex || !pn || Math.abs(ex.p - pn.p) >= GATES.NBA_FAIR_AGREE) out.push('fairs');
      if (!kalshiAt(p)) out.push('kalshi');
      if (!ex || !pn || ex.edge < GATES.NBA_MIN_EDGE || ex.edge > GATES.BIG_EDGE || pn.edge < 0 || px.dfs || px.exch) out.push('edge');
    } else if (px.p != null && px.p < GATES.MIN_PRICE) out.push('price');
    if (h != null && h >= GATES.EARLY_H) out.push('early');
    return out;
  }
  /* A Passed-ledger NBA prop that rule C would have played: it counts in the Play record (rebuilt, in-sample) and leaves Passed. Only rows first seen
     before NBA_FAIR_SINCE: after it the ledger judges with rule C itself, so a Passed row was passed on purpose (outside the night's top 5, the other
     side of a prop already played). Promoting those let them outrank the plays the lock actually logged. */
  const promoted = p => !!(p && p.sport === 'nba' && p.kind === 'prop' && p.firstSeen < GATES.NBA_FAIR_SINCE && !heldBack(p).length);
  /* The NBA prop Play record as the strict gates scored it before rule C: Play-ledger rows first seen before NBA_FAIR_SINCE, price 55%+, under 48h. */
  const oldGate = p => !!(p && p.sport === 'nba' && p.kind === 'prop' && p.firstSeen < GATES.NBA_FAIR_SINCE && p.first && p.first.price && p.first.price.p >= GATES.MIN_PRICE && !(hoursOut(p) >= GATES.EARLY_H));
  function judge(c) {
    /* c.refs: [{n,p}] fair chance of THIS side from each independent reference. Returns tier + reasons. */
    const rs = c.refs; c.refs.forEach(r => r.edge = r.p / c.price.p - 1);
    const edges = rs.map(r => r.edge); c.worst = edges.length ? Math.min(...edges) : null; c.best = edges.length ? Math.max(...edges) : null;
    /* Props are anchored on the exchange (Kalshi and Novig), which prices props more sharply than Pinnacle: the exchange edge is the headline edge and what plays are
       ranked by, and Pinnacle is the check (it must agree within AGREE and must not price the side the other way). Games keep the worst-case of both. */
    const ex = rs.find(r => r.n === 'Exchange'), pn = rs.find(r => r.n === 'Pinnacle'), anchored = c.kind === 'prop' && ex && pn;
    if (anchored) c.worst = ex.edge;
    const weak = c.best == null || c.best < GATES.MIN_EDGE;
    if (c.price.dfs) { c.tier = weak ? 'none' : 'pass'; c.reasons = ['Pick’em app price. It is a flat price, not a market, so it is not checked against fair.']; return c }
    if (c.price.exch) { c.tier = weak ? 'none' : 'pass'; c.reasons = ['The only price is at an exchange, the same market used as the check.']; return c }
    if (c.contradicted) { c.tier = weak ? 'none' : 'pass'; c.reasons = ['Both sides of this market look good against a reference. That is noise, not an edge.']; return c }
    if (rs.length < 2) { c.tier = (rs.length === 1 && c.best >= GATES.MIN_EDGE) ? 'watch' : 'none'; c.reasons = rs.length === 1 ? ['One reference only (' + rs[0].n + '). A play needs two independent prices to agree.'] : ['No fair price from Pinnacle or an exchange right now.']; return c }
    const gap = Math.abs(rs[0].p - rs[1].p);
    if (anchored) {
      if (gap > GATES.AGREE) { c.tier = 'pass'; c.reasons = ['Pinnacle and the exchange disagree by ' + (gap * 100).toFixed(1) + ' points, so neither is trusted.']; return c }
      if (ex.edge < GATES.MIN_EDGE) { c.tier = c.best >= GATES.MIN_EDGE ? 'pass' : 'none'; c.reasons = ['Does not beat the exchange, the anchor, by ' + pct(GATES.MIN_EDGE, 0) + ' (Exchange ' + spct(ex.edge) + ', Pinnacle ' + spct(pn.edge) + ').']; return c }
      if (pn.edge < 0) { c.tier = 'pass'; c.reasons = ['The exchange likes it (' + spct(ex.edge) + ') but Pinnacle prices it the other way (' + spct(pn.edge) + ').']; return c }
      if (ex.edge > GATES.BIG_EDGE) { c.tier = 'pass'; c.reasons = ['An edge over ' + pct(GATES.BIG_EDGE, 0) + ' is usually a stale or moved line. Calls this size went 21-32 (ROI -15%) on 53 settled.']; return c }
      const hb = held(c); if (hb.length) { c.tier = 'pass'; c.reasons = hb; return c }
      c.tier = 'play'; c.reasons = ['The price beats the exchange, the anchor, by ' + spct(ex.edge) + '. Pinnacle agrees within ' + (GATES.AGREE * 100) + ' points and does not price it the other way.']; return c;
    }
    if (gap > GATES.AGREE) { c.tier = 'pass'; c.reasons = ['Pinnacle and the exchange disagree by ' + (gap * 100).toFixed(1) + ' points, so neither is trusted.']; return c }
    if (c.worst < GATES.MIN_EDGE) { c.tier = c.best >= GATES.MIN_EDGE ? 'pass' : 'none'; c.reasons = ['Does not beat both references by ' + pct(GATES.MIN_EDGE, 0) + ' (' + rs.map(r => r.n + ' ' + spct(r.edge)).join(', ') + ').']; return c }
    if (c.worst > GATES.BIG_EDGE) { c.tier = 'pass'; c.reasons = ['An edge over ' + pct(GATES.BIG_EDGE, 0) + ' is usually a stale or moved line. Calls this size went 21-32 (ROI -15%) on 53 settled.']; return c }
    const hb = held(c); if (hb.length) { c.tier = 'pass'; c.reasons = hb; return c }
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

  /* ---- NBA props: the same gates on the NBA live board (nba-live/board.json, built by nba/scripts/snapshot.py) ----
     The board carries, per player and stat: Kalshi ladder rungs [line, bid, ask, open mid, ...], book rows [book, line, over, under, ...] (DraftKings from ESPN,
     Pinnacle) and, under board.novig.props, the Novig ladder. Same shape of call as the NFL props: the price is a US book, the exchange (Kalshi and Novig at the
     exact line) is the anchor and Pinnacle at the exact line is the check. Nothing is borrowed from NFL data, but the gates themselves are the NFL ones:
     there is no settled NBA Plays record yet to tune them on, so every NBA prop carries that caution until there is. */
  const NBA_STAT = { pts: 'Points', reb: 'Rebounds', ast: 'Assists', '3pm': '3-Pointers', pra: 'Pts + Reb + Ast', pr: 'Pts + Reb', pa: 'Pts + Ast', ra: 'Reb + Ast', stl: 'Steals', blk: 'Blocks' };
  const NBA_CAUTION = 'NBA props play on rule C (fairs within 1 point, Kalshi quoting, 3%+ over the exchange), found on Oct 20 - Nov 2 data. Its record from Nov 3 is the live test.';
  const num = v => { const n = typeof v === 'number' ? v : parseFloat(v); return Number.isFinite(n) ? n : null };
  const sameLine = (a, b) => a != null && b != null && Math.abs(a - b) < 1e-9;
  /* P(over) at one exact line from an exchange ladder, only from a two-sided quote tighter than MAX_EXCH_SPREAD. */
  const mid = (bid, ask) => bid != null && ask != null && bid > 0 && ask > 0 && ask >= bid && ask - bid <= GATES.MAX_EXCH_SPREAD ? (bid + ask) / 2 : null;
  function nbaFresh(N, NOW) {
    const ok = k => N && N.src_ok && N.src_ok[k] && N.src_ok[k].ok != null && NOW - N.src_ok[k].ok <= GATES.MAX_AGE;
    return { kalshi: ok('kalshi'), novig: !!(N && N.novig && N.novig.props && N.novig.asof != null && NOW - N.novig.asof <= GATES.MAX_AGE), pin: ok('pinnacle'), book: ok('espn'), shop: ok('actionprops') };
  }
  /* The exchange's P(over) for one player and stat at one exact line right now, or null: the ledger keeps the last of these before tip as the close. */
  function nbaExchangeNow(X, pid, stat, line) {
    const { N, now } = X, row = N && Array.isArray(N.props) && N.props.find(r => String(r.p) === String(pid) && r.s === stat);
    if (!row) return null;
    const got = [], f = nbaFresh(N, now);
    if (f.kalshi) { const r = (row.kal || []).find(x => sameLine(x[0], line)); const m = r && mid(num(r[1]), num(r[2])); if (m != null) got.push(['Kalshi', m]) }
    if (f.novig) { const e = N.novig.props[row.p + '|' + row.s], l = e && (e.lad || []).find(x => sameLine(x.k, line)); const m = l && l.bid && l.ask && mid(num(l.bid[0]), num(l.ask[0])); if (m != null) got.push(['Novig', m]) }
    return got.length ? { over: mean(got.map(x => x[1])), src: got.map(x => x[0]).join('+'), n: got.length } : null;
  }
  function nbaExchange(N, row, line, fresh) {
    const got = [];
    if (fresh.kalshi) { const r = (row.kal || []).find(x => sameLine(x[0], line)); const m = r && mid(num(r[1]), num(r[2])); if (m != null) got.push(['Kalshi', m]) }
    if (fresh.novig) { const e = N.novig.props[row.p + '|' + row.s], l = e && (e.lad || []).find(x => sameLine(x.k, line)); const m = l && l.bid && l.ask && mid(num(l.bid[0]), num(l.ask[0])); if (m != null) got.push(['Novig', m]) }
    return got.length ? { p: mean(got.map(x => x[1])), kal: got.some(x => x[0] === 'Kalshi') } : null;
  }
  function nbaPropCands(X) {
    const { N, now: NOW } = X, out = [];
    if (!N || !Array.isArray(N.props) || !N.games) return out;
    /* each source answers on its own clock: a row's own time only says when its price last changed, so freshness comes from src_ok */
    const fresh = nbaFresh(N, NOW);
    if (!(fresh.book || fresh.shop) || !(fresh.kalshi || fresh.novig)) return out;
    const games = Object.fromEntries((N.games || []).map(g => [String(g.id), g])), outs = new Set((N.outs || []).map(o => String(o[0])));
    for (const row of N.props) {
      const g = games[String(row.g)], pl = (N.players || {})[String(row.p)];
      if (!g || !pl || !NBA_STAT[row.s] || g.tip <= NOW || outs.has(String(row.p))) continue;
      /* row.books: DraftKings (ESPN), Pinnacle, Polymarket. row.shop: FanDuel, BetMGM, BetRivers, bet365, Caesars, Fanatics (Action Network). Each US book
         counts only while its own feed is answering, and the play takes the best US price at a line. */
      const rd = rs => (rs || []).map(b => ({ src: b[0], line: num(b[1]), over: num(b[2]), under: num(b[3]) })).filter(b => b.line != null);
      const books = rd(row.books), pin = fresh.pin ? books.find(b => b.src === 'Pinnacle') : null;
      const us = [...(fresh.book ? books : []), ...(fresh.shop ? rd(row.shop) : [])].filter(b => US.has(b.src) && b.over != null && b.under != null);
      for (const line of [...new Set(us.map(b => b.line))]) {
        const xr = nbaExchange(N, row, line, fresh), ex = xr && xr.p, pp = pin && sameLine(pin.line, line) ? devig(pin.over, pin.under) : null;
        for (const side of ['over', 'under']) {
          const v = us.filter(b => sameLine(b.line, line)).map(b => ({ b, p: imp(b[side]) })).filter(x => x.p != null).sort((a, b) => a.p - b.p)[0];
          if (!v) continue;
          const rl = [], pn = sideP(pp, side), xp = sideP(ex, side);
          if (pn != null) rl.push({ n: 'Pinnacle', p: pn }); if (xp != null) rl.push({ n: 'Exchange', p: xp });
          const cx = [NBA_CAUTION];
          const bp = mean(us.filter(b => sameLine(b.line, line) && b.src !== v.b.src).map(b => sideP(devig(b.over, b.under), side)).filter(x => x != null));
          if (bp != null && bp / v.p - 1 < 0) cx.push('The average of the other US books does not agree it is a good price.');
          if (pl[2] && !/^(available|active|probable)$/i.test(pl[2])) cx.push('Listed ' + String(pl[2]).toLowerCase() + ' on the injury report.');
          const label = NBA_STAT[row.s];
          out.push({ id: 'n|' + row.p + '|' + row.s + '|' + line + '|' + side + '|' + g.tip, kind: 'prop', sport: 'nba', start: g.tip,
            title: pl[0] + ' ' + (side === 'over' ? 'Over' : 'Under') + ' ' + line + ' ' + label, sub: pl[1],
            price: { am: side === 'over' ? v.b.over : v.b.under, p: v.p, book: v.b.src, dfs: false, exch: false, kal: !!(xr && xr.kal), shop: [...new Set(us.filter(b => sameLine(b.line, line)).map(b => b.src))].sort() }, refs: rl, cautions: cx, market: label, rec: null,
            row: { pid: 'nba:' + row.p, espnId: row.p, name: pl[0], team: pl[1], pos: null, mkt: row.s, label, line, game: String(row.g) }, matchup: { away: g.away, home: g.home }, side });
        }
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
  /* ---- the nightly NBA prop cap (GATES.NBA_CAP) ----
     A night is the Central-time date of the tip. Plays are logged once, at first sight, so the night's best can't be known as each one arrives:
     instead they lock NBA_LOCK_MIN before the night's first tip. Before the lock the top open slots show as Plays marked not locked (capPending;
     the ledger does not log them); at the lock the top slots by edge are logged; after it a new play fills a slot left open. The rest are Passes. */
  const nightOf = t => new Date(t * 1000).toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
  const ctTime = t => new Date(t * 1000).toLocaleTimeString('en-US', { timeZone: 'America/Chicago', hour: 'numeric', minute: '2-digit' });
  const nbaKey = c => ['p', c.start, c.row.pid, c.row.mkt, c.row.line, c.side].join('|');      // scripts/track-v2-plays.mjs ledgerKey for a prop
  const CAP_WHY = n => 'Outside tonight\u2019s top ' + n + ' NBA props by edge over the exchange. Capped at ' + n + ' a night: rebuilt, the top ' + n + ' went 29-12 (ROI +35%) on 41 against 32-16 (+29%) uncapped.';
  /* A row logged before the cap shipped, for a night whose lock comes after it, not yet decided: it does not hold a slot, it competes for one. */
  const lockOf = (r, tips) => (tips[nightOf(r.start)] || r.start) - GATES.NBA_LOCK_MIN * 60;
  const preCap = (r, tips) => r.firstSeen < GATES.NBA_CAP_SINCE && r.capPick == null && r.capOut == null && lockOf(r, tips) > GATES.NBA_CAP_SINCE;
  const nightTips = N => { const t = {}; for (const g of (N && N.games) || []) if (g.tip) { const k = nightOf(g.tip); t[k] = Math.min(t[k] || Infinity, g.tip) } return t };
  /* The Play ledger, after a night locks: each pre-cap row is stamped capPick (still among the plays the cap keeps) or capOut (not). Stamps are
     added fields, like lastRead and close; the first-sight record is not touched. Returns how many rows were stamped. */
  function capStamp(L, all, X) {
    const f = nbaFresh(X.N, X.now);
    if (!(f.book || f.shop) || !(f.kalshi || f.novig)) return 0;      // no live NBA prices this run: decide on the next one, not on an empty board
    const tips = nightTips(X.N), keep = new Set(all.filter(c => c.sport === 'nba' && c.kind === 'prop' && c.tier === 'play' && !c.capPending && c.capLock != null && X.now >= c.capLock).map(nbaKey));
    let n = 0;
    for (const r of Object.values((L && L.plays) || {})) {
      if (!(r.sport === 'nba' && r.kind === 'prop' && preCap(r, tips)) || X.now < lockOf(r, tips) || X.now >= r.start) continue;
      if (keep.has(r.id)) r.capPick = true; else r.capOut = true;
      n++;
    }
    return n;
  }
  function capNba(all, X) {
    const N = X.N, plays = all.filter(c => c.sport === 'nba' && c.kind === 'prop' && c.tier === 'play');
    if (!plays.length) return;
    const tips = nightTips(N);
    const logged = {}; for (const r of Object.values((X.L && X.L.plays) || {})) if (r.sport === 'nba' && r.kind === 'prop' && r.status !== 'void' && !heldBack(r).length && !r.capOut && !preCap(r, tips)) (logged[nightOf(r.start)] || (logged[nightOf(r.start)] = new Set())).add(r.id);
    const by = {}; plays.forEach(c => (by[nightOf(c.start)] || (by[nightOf(c.start)] = [])).push(c));
    for (const [k, cs] of Object.entries(by)) {
      const done = logged[k] || new Set(), lock = (tips[k] || Math.min(...cs.map(c => c.start))) - GATES.NBA_LOCK_MIN * 60;
      const open = cs.filter(c => !done.has(nbaKey(c))).sort((a, b) => b.worst - a.worst);
      const slots = Math.max(0, GATES.NBA_CAP - done.size);
      open.forEach((c, i) => {
        c.capLock = lock;
        if (i >= slots) { c.tier = 'pass'; c.reasons = [CAP_WHY(GATES.NBA_CAP)]; return }
        if (X.now < lock) { c.capPending = true; c.cautions = ['Not locked yet: tonight\u2019s top ' + GATES.NBA_CAP + ' by edge lock at ' + ctTime(lock) + ' CT.', ...c.cautions] }
      });
    }
  }
  /* The stored record through the same cap: per night, the top NBA_CAP rows by first-sight edge among those seen by the lock (an hour before the
     night's first tip in the record), then later rows by time into the slots left. Returns the ids the cap holds back. Pass rows that already
     clear heldBack (and promoted Passed rows), so the count is the plays the record would otherwise show. */
  function capOut(rows) {
    const by = {}, out = new Set();
    rows.forEach(p => { if (p && p.capOut) out.add(p.id) });      // a pre-cap row the lock passed over (capStamp)
    rows.filter(p => p && p.sport === 'nba' && p.kind === 'prop' && p.status !== 'void' && !p.capOut).forEach(p => (by[nightOf(p.start)] || (by[nightOf(p.start)] = [])).push(p));
    for (const rs of Object.values(by)) {
      const lock = Math.min(...rs.map(p => p.start)) - GATES.NBA_LOCK_MIN * 60, w = p => (p.first && p.first.worst) != null ? p.first.worst : -9;
      const early = rs.filter(p => p.firstSeen <= lock).sort((a, b) => w(b) - w(a)), late = rs.filter(p => p.firstSeen > lock).sort((a, b) => a.firstSeen - b.firstSeen);
      [...early, ...late].forEach((p, i) => { if (i >= GATES.NBA_CAP) out.add(p.id) });
    }
    return out;
  }

  /* Every candidate with its tier, and the ones that are not 'none' ranked by worst-case edge. X.L, the Play ledger, is optional: it tells the
     nightly NBA cap how many slots are already logged. */
  function build(X) {
    const all = [...propCands(X), ...nbaPropCands(X), ...gameCands(X)];
    /* contradictions: both sides of one market clearing any reference at once */
    const seen = {};
    all.forEach(c => { if (c.refs.some(r => r.p / c.price.p - 1 >= GATES.MIN_EDGE)) { const k = c.kind === 'prop' ? c.row.pid + '|' + c.row.mkt + '|' + c.row.line : c.gk + '|' + c.m; (seen[k] || (seen[k] = new Set())).add(c.side) } });
    all.forEach(c => { const k = c.kind === 'prop' ? c.row.pid + '|' + c.row.mkt + '|' + c.row.line : c.gk + '|' + c.m; c.contradicted = (seen[k] && seen[k].size > 1) || false; c.hoursOut = c.start ? (c.start - X.now) / 3600 : null; judge(c) });
    capNba(all, X);
    const cand = all.filter(c => c.tier !== 'none').sort((a, b) => (b.worst == null ? -9 : b.worst) - (a.worst == null ? -9 : a.worst));
    cand.noneCount = all.length - cand.length;
    return { all, cand };
  }

  /* One side per market. For each prop (player, stat, line) and each game market keep the side with the better edge and drop the other, so a bet never
     shows up as both Over and Under. Candidates on the favoured side stay (the same side can be priced at a book and at an exchange). */
  function stance(list) {
    const score = c => c.worst != null && c.refs.length > 1 ? c.worst : c.best != null ? c.best : -9;
    const key = c => c.kind === 'prop' ? 'p|' + c.row.pid + '|' + c.row.mkt + '|' + c.row.line : 'g|' + c.gk + '|' + c.m;
    const top = {};
    list.forEach(c => { const k = key(c), v = score(c); if (!top[k] || v > top[k].v) top[k] = { v, side: c.side } });
    return list.filter(c => top[key(c)].side === c.side);
  }

  return { GATES, US, EXCH, MKT, held, heldBack, setKalshiReads, promoted, oldGate, capOut, capStamp, nightOf, hoursOut, stance, pct, spct, sgn, imp, devig, bookP, sideP, mean, tapeIndex, refsAt, judge, propCands, nbaPropCands, nbaExchangeNow, gameCands, build };
});
