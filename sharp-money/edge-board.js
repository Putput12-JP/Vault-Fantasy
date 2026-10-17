/* Vault Edge Board: Novig's price against Pinnacle's fair price, every game, sortable, with the record of every call.
   One module shared by the classic page and new/. Context only, never a bet signal, counts toward no agree total.
   Reads two files the recorders keep fresh:
     data/exchange_edge_live.json    scripts/sharp_tape.py, each Sharp Money refresh: current EV per game and market, best side
     data/exchange_edge_record.json  scripts/exchange_edge_record.py: every call (first time a game side reached EV 1%) with its grade
   EV = Pinnacle's no-vig fair chance / what Novig charges to buy that side - 1. Fair uses the power de-vig, as everywhere else in Sharp Money.
   Layout: wide (the host is 1100px or more): scorecards on top, then the slate, the selected row's detail and the record side by side, each
   column scrolling on its own like the Board. Narrower: scorecards scroll sideways, rows open in place. */
(function () {
  var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname), LIVE = /[?&]live\b/.test(location.search);
  var BASE = LOCAL && !LIVE ? '/data/' : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/main/data/';
  var SPORT = { nfl: 'NFL', cfb: 'CFB', nba: 'NBA' }, MK = { ml: 'Money', sp: 'Spread', tot: 'Total' }, GOAL = 50;   // 50 graded calls, the bar the other Sharp Money signals use
  var st = { sport: 'all', m: 'all', sort: 'ev', pos: 1, open: null, sel: null }, data = null, dataP = null, dataAt = 0, ctx = { games: [], logo: null }, wide = false;

  function get(n) {
    return fetch(BASE + n + '?t=' + Math.floor(Date.now() / 120000), { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function load() { return dataP || (dataP = Promise.all([get('exchange_edge_live.json'), get('exchange_edge_record.json')]).then(function (x) { data = { live: x[0], rec: x[1] }; dataAt = Date.now(); dataP = null; return data; })); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function when(t) { return new Date(t * 1000).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' }); }
  function dur(sec) { var m = Math.round(sec / 60); return m < 1 ? 'under a minute' : m < 60 ? m + ' min' : Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + (m % 60) + ' m' : ''); }
  function sg(v, d) { return (v > 0 ? '+' : '') + v.toFixed(d == null ? 1 : d); }
  function usd(v) { return '$' + (v >= 1000 ? +(v / 1000).toFixed(v % 1000 ? 1 : 0) + 'k' : Math.round(v)); }
  function chips(key, items) {
    return '<div class="veb-seg" data-k="' + key + '">' + items.map(function (i) { return '<button type="button" data-v="' + i[0] + '" class="' + (String(st[key]) === String(i[0]) ? 'on' : '') + '">' + i[1] + '</button>'; }).join('') + '</div>';
  }
  function gameOf(x) {
    var g = ctx.games.filter(function (q) { return q.key === x.gk; })[0];
    return g || { key: x.gk, sport: x.sport, away: { abbr: x.away, name: x.away }, home: { abbr: x.home, name: x.home }, start: x.start };
  }
  function logo(x, side, z) {
    var g = gameOf(x), u = ctx.logo ? ctx.logo(g, side) : null, t = g[side] || {};
    z = z || 22;
    var dot = '<i class="veb-dot" style="width:' + z + 'px;height:' + z + 'px;background:' + esc(t.color || '#555') + '"></i>';
    return u ? '<img class="veb-lg" src="' + esc(u) + '" alt="" width="' + z + '" height="' + z + '" loading="lazy" onerror="this.outerHTML=this.getAttribute(\'data-f\')" data-f=\'' + dot.replace(/'/g, '&#39;') + '\'>' : dot;
  }
  function pair(x, z) { return '<span class="veb-pair">' + logo(x, 'away', z) + logo(x, 'home', z) + '</span>'; }

  /* ---------- data selection ---------- */
  function liveAll() { var now = Date.now() / 1000; return ((data.live && data.live.rows) || []).filter(function (x) { return x.start > now; }); }
  function liveRows() {
    var r = liveAll();
    if (st.sport !== 'all') r = r.filter(function (x) { return x.sport === st.sport; });
    if (st.m !== 'all') r = r.filter(function (x) { return x.m === st.m; });
    if (st.pos) r = r.filter(function (x) { return x.ev > 0; });
    r.sort(st.sort === 'soon' ? function (a, b) { return a.start - b.start; } : st.sort === 'pin' ? function (a, b) { return (b.pm || -99) - (a.pm || -99); } : function (a, b) { return b.ev - a.ev; });
    return r;
  }
  function sports() { return st.sport === 'all' ? ['nfl', 'cfb', 'nba'] : [st.sport]; }
  function pool(list) {
    var o = { signals: 0, graded: 0, n_same: 0, sum_clv: 0, ss_clv: 0, pos: 0, settled: 0, wins: 0, units: 0, line_moved: 0, line_favoured: 0 };
    list.forEach(function (x) { if (!x) return; Object.keys(o).forEach(function (k) { o[k] += x[k] || 0; }); });
    var t = o.n_same ? o.sum_clv / o.n_same : null, ci = null;
    if (o.n_same > 1) { var v = (o.ss_clv - o.n_same * t * t) / (o.n_same - 1); ci = 1.96 * Math.sqrt(Math.max(v, 0) / o.n_same); }
    o.mean = t; o.ci = ci;
    return o;
  }
  function summ(thr, tag) { var rec = data.rec; return pool(sports().map(function (sp) { return rec && rec.by_sport && rec.by_sport[sp] ? rec.by_sport[sp].summary.filter(function (x) { return x.thr === thr && x.tag === tag; })[0] : null; })); }
  function callsAll() {
    var out = [], rec = data.rec; if (!rec || !rec.by_sport) return out;
    sports().forEach(function (sp) { ((rec.by_sport[sp] || {}).calls || []).forEach(function (c) { out.push(Object.assign({ sport: sp }, c)); }); });
    if (st.m !== 'all') out = out.filter(function (c) { return c.m === st.m; });
    return out.sort(function (a, b) { return b.t - a.t; });
  }

  /* ---------- scorecards ---------- */
  function card(label, chip, big, sub, bar, foot, tone) {
    return '<div class="veb-kpi"><div class="veb-kh"><span>' + label + '</span>' + (chip ? '<em class="' + (tone || '') + '">' + chip + '</em>' : '') + '</div><div class="veb-kn">' + big + '</div>' + (sub ? '<div class="veb-ks">' + sub + '</div>' : '') +
      (bar != null ? '<div class="veb-bar"><i style="width:' + Math.max(2, Math.min(100, bar * 100)) + '%"></i></div>' : '') + (foot ? '<div class="veb-kf">' + foot + '</div>' : '') + '</div>';
  }
  function kpiHtml() {
    var rows = liveAll().filter(function (x) { return st.sport === 'all' || x.sport === st.sport; }), up = rows.filter(function (x) { return x.ev > 0; }), best = up.slice().sort(function (a, b) { return b.ev - a.ev; })[0];
    var all = summ(1, 'all'), stale = summ(1, 'stale'), l = data.live || {}, now = Date.now() / 1000, seen = l.seen || {}, o = '';
    o += card('+EV right now', 'LIVE', up.length + ' of ' + rows.length, best ? 'best ' + sg(best.ev) + '% ' + esc(best.label) + (best.m === 'ml' ? ' ML' : '') : 'nothing above zero', rows.length ? up.length / rows.length : 0, 'Novig against Pinnacle, no fee before kickoff');
    o += card('Calls logged', 'TOO EARLY', all.signals, all.graded + ' graded, ' + (all.signals - all.graded) + ' open', Math.min(1, all.graded / GOAL), all.graded + ' of ' + GOAL + ' graded to call it', 'amber');
    o += card('Beat the close', 'TOO EARLY', all.n_same ? Math.round(all.pos / all.n_same * 100) + '%' : 'none', all.n_same ? 'avg ' + sg(all.mean) + ' pts' + (all.ci != null ? ' ±' + all.ci.toFixed(1) : '') : 'no graded calls yet', all.n_same ? all.pos / all.n_same : 0, 'vs Pinnacle’s last number before kickoff', 'amber');
    o += card('Units at 1u each', 'TOO EARLY', all.settled ? sg(all.units, 2) + 'u' : '0.00u', all.settled ? all.wins + '-' + (all.settled - all.wins) + ' settled' : 'no calls settled yet', Math.min(1, all.settled / GOAL), all.settled + ' of ' + GOAL + ' settled', 'amber');
    o += card('Pinnacle moved, Novig did not', 'CONTEXT', rows.filter(function (x) { return x.stale; }).length, stale.graded ? stale.graded + ' graded, avg ' + (stale.mean != null ? sg(stale.mean) : 'n/a') + ' pts' : 'none graded yet', Math.min(1, stale.graded / GOAL), stale.graded + ' of ' + GOAL + ' graded to call it');
    var src = ['Pinnacle', 'Novig', 'Kalshi', 'Polymarket', 'US books'].filter(function (k) { return seen[k] != null; }).map(function (k) { var a = now - seen[k]; return '<span class="veb-src ' + (a > 1800 ? 'bad' : 'ok') + '"><i></i>' + k + ' ' + (a < 90 ? 'now' : dur(a)) + '</span>'; }).join('');
    var age = l.generated ? now - Date.parse(l.generated) / 1000 : null, cov = l.coverage || {}, cv = ['nfl', 'cfb', 'nba'].filter(function (sp) { return cov[sp] && cov[sp].games; }).map(function (sp) { return SPORT[sp] + ' ' + (cov[sp].novig || 0) + '/' + cov[sp].games; }).join(' · ');
    o += '<div class="veb-kpi"><div class="veb-kh"><span>Sources</span><em class="' + (age > 1800 ? 'red' : 'green') + '">' + (age > 1800 ? 'EXPIRED' : 'FRESH') + '</em></div><div class="veb-srcs">' + src + '</div><div class="veb-kf">Novig quotes ' + cv + '. A game with no Novig quote has no row.</div></div>';
    return o;
  }

  /* ---------- the slate ---------- */
  function rowHtml(x, maxEv, selected, op) {
    var bits = [];
    if (x.pm != null) bits.push('Pinnacle ' + sg(x.pm) + ' pts in 4h');
    if (x.nm != null) bits.push('Novig ' + sg(x.nm) + ' pts');
    if (x.second && x.second.of) bits.push(x.second.confirm + ' of ' + x.second.of + ' exchanges agree');
    if (x.fill && x.fill['500'] != null) bits.push('EV holds at $500'); else if (x.depth != null) bits.push(usd(x.depth) + ' deep');
    var key = x.gk + '|' + x.m, heat = Math.max(0.08, Math.min(1, x.ev / (maxEv || 1)));
    return '<div class="veb-item' + (op ? ' open' : '') + '"><div class="veb-row' + (selected ? ' sel' : '') + '" role="button" tabindex="0" aria-expanded="' + !!op + '" data-key="' + esc(key) + '">' +
      '<div class="veb-top">' + pair(x, 22) + '<span class="veb-teams">' + esc(x.away) + ' @ ' + esc(x.home) + '</span><span class="veb-meta"><b class="veb-sp">' + SPORT[x.sport] + '</b>' + when(x.start) + '</span></div>' +
      '<div class="veb-main"><div class="veb-pick"><span class="veb-mk">' + MK[x.m] + '</span> ' + esc(x.label) + ' <span class="veb-px">' + esc(x.price) + '</span><small>fair ' + (x.fair * 100).toFixed(1) + '%</small></div>' +
      '<div class="veb-ev ' + (x.ev > 0 ? 'pos' : 'neg') + '" style="--h:' + heat.toFixed(2) + '">' + sg(x.ev) + '%<small>EV</small></div></div>' +
      (bits.length || x.stale ? '<div class="veb-sub">' + (x.stale ? '<i class="veb-stale">Pinnacle moved, Novig did not</i> ' : '') + bits.join(' · ') + '</div>' : '') + '</div>' + (op ? '<div class="veb-drawer">' + detailInner(x) + '</div>' : '') + '</div>';
  }
  function slateHtml(rows) {
    if (!data.live) return '<div class="veb-empty">The live edge file did not load. Try again in a minute.</div>';
    if (!rows.length) return '<div class="veb-empty">' + (st.pos ? 'Nothing is above zero EV for this filter right now.' : 'No games match this filter.') + '</div>';
    var maxEv = Math.max.apply(null, rows.map(function (x) { return Math.max(x.ev, 0.1); })), stale = Date.now() / 1000 - Date.parse(data.live.generated) / 1000 > 1800, o = '<div class="' + (stale ? 'veb-list stale' : 'veb-list') + '">';
    rows.forEach(function (x) { var key = x.gk + '|' + x.m; o += rowHtml(x, maxEv, wide ? st.sel === key : false, !wide && st.open === key); });
    return o + '</div>';
  }

  /* ---------- the selected row (wide) / the drawer (narrow) ---------- */
  function detailInner(x) {
    var f = x.fill || {}, o = '', now = Date.now() / 1000;
    o += '<div class="veb-lad">';
    if (x.fill) {
      [['100', '$100'], ['500', '$500'], ['1000', '$1k']].forEach(function (k) { o += '<div><small>EV at ' + k[1] + '</small><b class="' + (f[k[0]] == null ? '' : f[k[0]] > 0 ? 'pos' : 'neg') + '">' + (f[k[0]] == null ? 'too thin' : sg(f[k[0]]) + '%') + '</b></div>'; });
      o += '<div><small>Room at +EV</small><b>' + usd(f.ev_dollars) + '</b></div>';
    } else o += '<div class="veb-note" style="grid-column:1/-1;margin:0">Order-book depth is not available for this row this run.</div>';
    o += '</div>';
    var q = x.second, cents = function (v) { return Math.round(v * 1000) / 10 + '¢'; };
    o += '<div class="veb-cmp"><div><small>Pinnacle fair</small><b>' + (x.fair * 100).toFixed(1) + '%</b></div><div><small>Novig costs</small><b>' + cents(x.cost) + '</b></div>' +
      (q && q.kal != null ? '<div><small>Kalshi</small><b>' + cents(q.kal) + '</b></div>' : '') + (q && q.pm != null ? '<div><small>Polymarket</small><b>' + cents(q.pm) + '</b></div>' : '') + '</div>';
    if (q) o += '<div class="veb-ages">' + q.confirm + ' of ' + q.of + ' exchanges are at least a cent above Novig.' + (x.m === 'ml' ? '' : ' Kalshi has the winner market only.') + '</div>';
    o += '<div class="veb-ages">' + (x.pin_since ? 'Pinnacle last moved ' + dur(now - x.pin_since) + ' ago' : 'Pinnacle move time unknown') + ' · ' + (x.nov_since ? 'Novig unchanged for ' + dur(now - x.nov_since) : 'Novig quote age unknown yet') + (x.lim ? ' · Pinnacle limit ' + usd(x.lim) : '') + '</div>';
    return o + '<div class="veb-chart" data-chart="' + esc(x.gk) + '"></div><button type="button" class="veb-open" data-gk="' + esc(x.gk) + '">Open the game page</button>';
  }
  function panelHtml(x) {
    if (!x) return '<div class="veb-empty">Pick a row to see its detail.</div>';
    var g = gameOf(x);
    return '<div class="veb-hero">' + pair(x, 40) + '<div><b>' + esc((g.away && (g.away.name || g.away.abbr)) || x.away) + ' @ ' + esc((g.home && (g.home.name || g.home.abbr)) || x.home) + '</b><small>' + SPORT[x.sport] + ' · ' + when(x.start) + '</small></div></div>' +
      '<div class="veb-call"><div><span class="veb-mk">' + MK[x.m] + '</span><b>' + esc(x.label) + '</b><span class="veb-px">' + esc(x.price) + '</span></div><div class="veb-ev big ' + (x.ev > 0 ? 'pos' : 'neg') + '">' + sg(x.ev) + '%<small>EV</small></div></div>' +
      (x.stale ? '<div class="veb-sub"><i class="veb-stale">Pinnacle moved, Novig did not</i></div>' : '') + detailInner(x);
  }

  /* ---------- the record ---------- */
  function sumLine(x, label) {
    var o = '<div class="veb-rr"><span>' + label + '</span><span>';
    if (!x || !x.signals) return o + 'none yet</span></div>';
    if (!x.graded) return o + x.signals + ' called, none graded yet</span></div>';
    o += x.graded + ' graded';
    if (x.n_same) o += ', beat the close ' + Math.round(x.pos / x.n_same * 100) + '%, avg ' + sg(x.mean) + ' pts' + (x.ci != null ? ' ±' + x.ci.toFixed(1) : '');
    if (x.settled) o += ', ' + x.wins + '-' + (x.settled - x.wins) + ' ' + sg(x.units, 2) + 'u';
    if (x.line_moved) o += ', line moved ' + x.line_moved + ' (' + x.line_favoured + ' our way)';
    return o + '</span></div>';
  }
  function recHtml() {
    var rec = data.rec; if (!rec || !rec.by_sport) return '<div class="veb-empty">The record file did not load.</div>';
    var o = '<div class="veb-card"><div class="veb-h"><span>Record</span><span>graded on Pinnacle’s close</span></div>';
    [[1, 'EV 1%+'], [2, 'EV 2%+'], [4, 'EV 4%+']].forEach(function (a) { o += sumLine(summ(a[0], 'all'), a[1]); });
    o += sumLine(summ(1, 'stale'), 'Pinnacle moved, Novig did not');
    o += '<div class="veb-note">A call is the first time a game side reached EV 1% or more. Beat the close means Pinnacle’s last number before kickoff was better than the Novig price at the call. ± is a 95% range; a range that spans zero is still noise. Started ' + esc(rec.since) + '; nothing earlier was stored.</div></div>';
    return o + calibHtml(rec);
  }
  function calibHtml(rec) {
    var groups = [['band', 'By EV at the call'], ['market', 'By market'], ['stale', 'By what moved']], o = '<div class="veb-card"><div class="veb-h"><span>Does bigger EV mean more?</span><span>vs the close</span></div>', any = false, sp0 = sports()[0];
    groups.forEach(function (gr) {
      var labels = [];
      ((rec.by_sport[sp0] || {}).calib || []).forEach(function (c) { if (c.k === gr[0]) labels.push(c.l); });
      if (!labels.length) return;
      o += '<div class="veb-gl">' + gr[1] + '</div>';
      labels.forEach(function (l) {
        var p = pool(sports().map(function (sp) { return ((rec.by_sport[sp].calib || []).filter(function (c) { return c.k === gr[0] && c.l === l; })[0]); }));
        any = any || p.signals > 0;
        o += '<div class="veb-rr"><span>' + esc(l) + '</span><span>' + (!p.signals ? 'none yet' : !p.graded ? p.signals + ' called' : p.n_same + ' graded, beat ' + Math.round(p.pos / p.n_same * 100) + '%, avg ' + sg(p.mean) + (p.ci != null ? ' ±' + p.ci.toFixed(1) : '') + (p.settled ? ', ' + p.wins + '-' + (p.settled - p.wins) + ' ' + sg(p.units, 2) + 'u' : '')) + '</span></div>';
      });
    });
    return o + '<div class="veb-note">' + (any ? '' : 'Nothing to compare yet. ') + 'If bigger EV is real, the average and the beat-the-close share rise down the EV rows. While the ranges span zero the rows cannot be told apart, so none is labelled.</div></div>';
  }
  function callsHtml() {
    var calls = callsAll(), o = '<div class="veb-card"><div class="veb-h"><span>Every call</span><span>' + calls.length + (calls.length >= 400 ? '+' : '') + '</span></div>';
    if (!calls.length) return o + '<div class="veb-empty">No calls yet. They are logged as the recorder sees them.</div></div>';
    calls.slice(0, 80).forEach(function (c) {
      var tm = String(c.game).split('@'), A = c.side === 'A', side = c.m === 'tot' ? (A ? 'Over' : 'Under') : (A ? tm[1] : tm[0]);
      var line = c.m === 'sp' ? ' ' + sg(A ? c.line : -c.line, 1).replace(/\.0$/, '') : c.m === 'tot' ? ' ' + c.line : '';
      var res = !c.graded ? '<span class="veb-pend">Pending</span>' : c.clv != null ? '<span class="' + (c.clv > 0 ? 'veb-win' : 'veb-loss') + '">' + (c.clv > 0 ? 'Beat the close ' : 'Close beat us ') + sg(c.clv) + ' pts</span>' : '<span class="' + (c.line_favoured ? 'veb-win' : 'veb-loss') + '">Line moved ' + (c.line_favoured ? 'our way' : 'against us') + '</span>';
      var life = (c.dur != null ? (c.open ? 'open ' : 'lasted ') + dur(c.dur) + ', peak ' + sg(c.peak) + '%' : '') + (c.nclv != null ? ' · Novig closed ' + sg(c.nclv) + ' pts vs the call' : '') + (c.res ? ' · ' + (c.res === 'W' ? 'won' : c.res === 'L' ? 'lost' : 'push') + ' ' + sg(c.units, 2) + 'u' : '');
      o += '<div class="veb-call2" role="button" tabindex="0" data-gk="' + esc(c.gk || '') + '"><div class="veb-top"><span class="veb-teams">' + esc(String(c.game).replace('@', ' @ ')) + '</span><span class="veb-meta"><b class="veb-sp">' + SPORT[c.sport] + '</b>' + when(c.t) + '</span></div>' +
        '<div class="veb-main"><div class="veb-pick"><span class="veb-mk">' + MK[c.m] + '</span> ' + esc(side) + line + (c.stale ? ' <i class="veb-stale">Pinnacle moved, Novig did not</i>' : '') + '<small>paid ' + Math.round(c.cost * 100) + '¢, fair ' + (c.fair * 100).toFixed(1) + '%</small></div><div class="veb-ev pos sm">' + sg(c.ev) + '%<small>at the call</small></div></div><div class="veb-sub">' + res + (life ? ' · ' + life : '') + '</div></div>';
    });
    return o + '</div>';
  }

  /* ---------- style ---------- */
  var CSS = '.veb{color:inherit;container-type:inline-size;font-variant-numeric:tabular-nums}' +
    '.veb-kpis{display:grid;grid-auto-flow:column;grid-auto-columns:min(176px,58%);gap:8px;align-items:start;overflow-x:auto;padding:2px 2px 8px;margin:0 0 2px;scrollbar-width:none}.veb-kpis::-webkit-scrollbar{display:none}' +
    '.veb-kpi{padding:11px 12px;border-radius:20px;background:rgba(127,127,127,.1);border:1px solid rgba(127,127,127,.16);min-width:0}.veb-kh{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;font-size:11px;opacity:1;color:rgba(127,127,127,1);line-height:1.35}' +
    '.veb-kh em{font-style:normal;font-size:9.5px;font-weight:600;letter-spacing:.06em;padding:3px 7px;border-radius:8px;background:rgba(127,127,127,.2);white-space:nowrap}.veb-kh em.amber{color:#fbbf24;background:rgba(251,191,36,.1)}.veb-kh em.green{color:#34c759;background:rgba(52,199,89,.12)}.veb-kh em.red{color:#ff6b6b;background:rgba(255,107,107,.14)}' +
    '.veb-kn{font-size:22px;font-weight:600;letter-spacing:-.01em;margin:6px 0 2px;line-height:1.1}.veb-ks{font-size:12px;opacity:.75;min-height:17px}.veb-bar{height:4px;border-radius:3px;background:rgba(127,127,127,.2);margin:9px 0 6px;overflow:hidden}.veb-bar i{display:block;height:100%;border-radius:3px;background:#9bb0e8}' +
    '.veb-kf{display:none;font-size:10.5px;opacity:.55;line-height:1.4}.veb-srcs{display:flex;flex-wrap:nowrap;overflow-x:auto;gap:6px;margin:10px 0 4px;scrollbar-width:none}.veb-src{white-space:nowrap;flex:none}.veb-src{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;padding:3px 8px;border-radius:999px;background:rgba(127,127,127,.14)}.veb-src i{width:6px;height:6px;border-radius:50%;background:#34c759}.veb-src.bad i{background:#ff6b6b}' +
    '.veb-bar2{display:flex;flex-wrap:wrap;gap:6px 8px;margin:0 0 10px}.veb-seg{display:inline-flex;gap:2px;padding:2px;border-radius:9px;background:rgba(127,127,127,.14)}' +
    '.veb-seg button{font:inherit;font-size:12px;font-weight:600;line-height:1;padding:8px 10px;min-height:34px;border:0;border-radius:7px;background:transparent;color:inherit;opacity:.65;cursor:pointer}.veb-seg button.on{background:rgba(127,127,127,.32);opacity:1}' +
    '.veb-grid{display:block}.veb-col{min-width:0}.veb-h{display:flex;justify-content:space-between;gap:12px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.6;margin:12px 0 4px}' +
    '.veb-list.stale{opacity:.5}.veb-item{border-top:1px solid rgba(127,127,127,.18)}.veb-row,.veb-call2{padding:11px 10px;cursor:pointer;border-radius:12px;border-left:3px solid transparent}.veb-row:hover,.veb-call2:hover{background:rgba(127,127,127,.07)}.veb-row:focus-visible,.veb-call2:focus-visible{outline:2px solid currentColor;outline-offset:2px}.veb-row.sel,.veb-item.open>.veb-row{background:rgba(127,127,127,.12);border-left-color:#9bb0e8}' +
    '.veb-top{display:flex;align-items:center;gap:8px;font-size:12px}.veb-pair{display:inline-flex;align-items:center;gap:2px;flex:none}.veb-lg{object-fit:contain}.veb-dot{display:inline-block;border-radius:50%;opacity:.8;margin:0 2px}.veb-teams{font-weight:600;font-size:13px}.veb-meta{margin-left:auto;opacity:.6;white-space:nowrap}.veb-sp{font-weight:600;font-size:10px;letter-spacing:.06em;padding:2px 6px;border-radius:6px;background:rgba(127,127,127,.2);margin-right:7px;opacity:1}' +
    '.veb-main{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:6px}.veb-pick{font-size:14.5px}.veb-mk{font-size:10.5px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;opacity:.6;margin-right:6px}.veb-pick small{display:inline;margin-left:8px;font-size:12px;opacity:.55}.veb-px{font-weight:600;margin-left:4px}' +
    '.veb-ev{min-width:74px;text-align:right;font-size:19px;font-weight:700;padding:5px 9px;border-radius:10px}.veb-ev small{display:block;font-size:9.5px;font-weight:500;letter-spacing:.06em;opacity:.75}.veb-ev.pos{color:#34c759;background:rgba(52,199,89,calc(.06 + var(--h,.3) * .16))}.veb-ev.neg{opacity:.65}.veb-ev.big{font-size:30px;padding:8px 14px}.veb-ev.sm{font-size:15px;min-width:64px;padding:3px 7px}' +
    '.veb-sub{margin-top:6px;font-size:12px;opacity:.78;line-height:1.55}.veb-stale{font-style:normal;font-size:10.5px;font-weight:600;padding:2px 7px;border-radius:999px;border:1px solid #ff9f43;color:#ff9f43;margin-right:4px}.veb-win{color:#34c759;font-weight:600}.veb-loss{color:#ff6b6b;font-weight:600}.veb-pend{opacity:.7}' +
    '.veb-drawer{padding:4px 10px 14px}.veb-hero{display:flex;align-items:center;gap:12px;margin:2px 0 12px}.veb-hero b{display:block;font-size:17px}.veb-hero small{opacity:.6;font-size:12px}.veb-call{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 10px}.veb-call b{font-size:22px;margin-right:8px}.veb-call .veb-px{font-size:18px}' +
    '.veb-lad,.veb-cmp{display:grid;grid-template-columns:repeat(auto-fit,minmax(92px,1fr));gap:8px;margin:0 0 10px}.veb-lad div,.veb-cmp div{padding:9px 11px;border-radius:12px;background:rgba(127,127,127,.1)}.veb-lad small,.veb-cmp small{display:block;font-size:10px;opacity:.6;letter-spacing:.05em;text-transform:uppercase}.veb-lad b,.veb-cmp b{font-size:16px}.veb-lad b.pos{color:#34c759}.veb-lad b.neg{opacity:.65}' +
    '.veb-ages{font-size:12px;opacity:.75;margin:0 0 8px;line-height:1.5}.veb-chart{margin:8px 0 10px}.veb-open{font:inherit;font-size:12.5px;font-weight:600;padding:8px 12px;min-height:34px;border-radius:9px;border:1.5px solid currentColor;background:transparent;color:inherit;cursor:pointer;opacity:.85}' +
    '.veb-card{padding:4px 2px 6px;margin:0 0 6px}.veb-gl{font-size:11px;font-weight:700;margin:9px 0 1px;opacity:.9}.veb-rr{display:flex;justify-content:space-between;gap:12px;font-size:12.5px;padding:5px 0}.veb-rr span:last-child{text-align:right;opacity:.85}.veb-note{margin-top:9px;font-size:11.5px;opacity:.55;line-height:1.5}.veb-empty{padding:18px 4px;font-size:13px;opacity:.65}.veb-call2{border-top:1px solid rgba(127,127,127,.15)}' +
    '@container (min-width:1100px){.veb-srcs{flex-wrap:wrap;overflow:visible;margin:10px 0 8px}.veb-kf{display:block}.veb-kn{font-size:25px}.veb-kpi{padding:13px 14px}.veb-kpis{grid-auto-flow:row;grid-template-columns:repeat(6,minmax(0,1fr));grid-auto-columns:auto;overflow:visible;padding-bottom:6px}.veb-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr) minmax(0,.95fr);gap:14px;align-items:start}.veb-col{max-height:calc(100vh - 330px);min-height:520px;overflow-y:auto;padding:4px 8px 16px;border-radius:20px;background:rgba(127,127,127,.06);border:1px solid rgba(127,127,127,.14);scrollbar-width:thin}.veb-col>.veb-h:first-child{margin-top:8px}}';
  function css() { if (!document.getElementById('veb-css')) { var s = document.createElement('style'); s.id = 'veb-css'; s.textContent = CSS; document.head.appendChild(s); } }

  /* ---------- render ---------- */
  function render(el) {
    wide = el.clientWidth >= 1100;
    var rows = liveRows(), keyOf = function (x) { return x.gk + '|' + x.m; };
    if (wide && !rows.some(function (x) { return keyOf(x) === st.sel; })) st.sel = rows[0] ? keyOf(rows[0]) : null;
    var sel = rows.filter(function (x) { return keyOf(x) === st.sel; })[0];
    var bar = '<div class="veb-bar2">' + chips('sport', [['all', 'All'], ['nfl', 'NFL'], ['cfb', 'CFB'], ['nba', 'NBA']]) + chips('pos', [[1, '+EV only'], [0, 'All']]) + chips('m', [['all', 'All'], ['ml', 'Money'], ['sp', 'Spread'], ['tot', 'Total']]) + chips('sort', [['ev', 'Biggest +EV'], ['soon', 'Soonest'], ['pin', 'Pinnacle moved']]) + '</div>';
    var o = '<div class="veb"><div class="veb-kpis">' + kpiHtml() + '</div>' + bar;
    var slate = '<div class="veb-h"><span>Right now</span><span>' + rows.length + ' shown</span></div>' + slateHtml(rows);
    if (wide) o += '<div class="veb-grid"><div class="veb-col" data-c="slate">' + slate + '</div><div class="veb-col" data-c="detail"><div class="veb-h"><span>Selected</span><span></span></div>' + panelHtml(sel) + '</div><div class="veb-col" data-c="rec">' + recHtml() + callsHtml() + '</div></div>';
    else o += slate + recHtml() + callsHtml();
    o += '<div class="veb-note" style="margin-top:12px">Novig is a peer to peer exchange with no fee before kickoff. EV is against Pinnacle’s no-vig price, so check the room at +EV before reading a big number. Spreads and totals only show where Novig quotes Pinnacle’s exact line. Context only, not a bet signal.</div></div>';
    var keep = {}; Array.prototype.forEach.call(el.querySelectorAll('.veb-col'), function (c) { keep[c.getAttribute('data-c')] = c.scrollTop; });
    el.innerHTML = o;
    Array.prototype.forEach.call(el.querySelectorAll('.veb-col'), function (c) { c.scrollTop = keep[c.getAttribute('data-c')] || 0; });
    var host = el.querySelector('[data-chart]');
    if (host && window.VaultLineChart) {
      var k = host.getAttribute('data-chart'), x = (wide ? sel : rows.filter(function (r) { return keyOf(r) === st.open; })[0]);
      if (x) window.VaultLineChart.mount(host, { key: x.gk, sport: x.sport, away: { abbr: x.away }, home: { abbr: x.home }, start: x.start, tab: x.m });
    }
  }
  function open(gk) { if (gk) location.hash = '#game/' + gk; }
  function mount(el, opts) {
    if (!el) return;
    css();
    if (opts) ctx = { games: opts.games || [], logo: opts.logo || null };
    if (!el.__veb) {
      el.__veb = 1;
      el.addEventListener('click', function (e) {
        var b = e.target.closest('.veb-seg button');
        if (b) { var k = b.parentNode.getAttribute('data-k'); st[k] = k === 'pos' ? +b.getAttribute('data-v') : b.getAttribute('data-v'); render(el); return; }
        var ob = e.target.closest('.veb-open'); if (ob) { open(ob.getAttribute('data-gk')); return; }
        if (e.target.closest('.veb-drawer')) return;
        var r = e.target.closest('.veb-row'); if (r) { var key = r.getAttribute('data-key'); if (wide) st.sel = key; else st.open = st.open === key ? null : key; render(el); return; }
        var c = e.target.closest('.veb-call2'); if (c) open(c.getAttribute('data-gk'));
      });
      el.addEventListener('keydown', function (e) { if ((e.key === 'Enter' || e.key === ' ') && (e.target.classList.contains('veb-row') || e.target.classList.contains('veb-call2'))) { e.preventDefault(); e.target.click(); } });
      if (window.ResizeObserver) { var last = el.clientWidth >= 1100; new ResizeObserver(function () { var w = el.clientWidth >= 1100; if (w !== last && data) { last = w; render(el); } }).observe(el); }
    }
    if (data) { render(el); if (Date.now() - dataAt > 120000) load().then(function () { render(el); }); }
    else { el.innerHTML = '<div class="veb-empty">Loading…</div>'; load().then(function () { render(el); }); }
  }
  window.VaultEdgeBoard = { mount: mount };
})();
