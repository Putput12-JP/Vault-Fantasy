/* Vault Edge Board: Novig's price against Pinnacle's fair price, every game, sortable, with the record of every call.
   One module shared by the classic page and new/. Context only, never a bet signal, counts toward no agree total.
   Reads two files the recorders keep fresh:
     data/exchange_edge_live.json    scripts/sharp_tape.py, each Sharp Money refresh: current EV per game and market, best side
     data/exchange_edge_record.json  scripts/exchange_edge_record.py: every call (first time a game side reached EV 1%) with its grade
   EV = Pinnacle's no-vig fair chance / what Novig charges to buy that side - 1. Fair uses the power de-vig, as everywhere else in Sharp Money. */
(function () {
  var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname), LIVE = /[?&]live\b/.test(location.search);
  var BASE = LOCAL && !LIVE ? '/data/' : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/main/data/';
  var SPORT = { nfl: 'NFL', cfb: 'CFB', nba: 'NBA' }, MK = { ml: 'Money', sp: 'Spread', tot: 'Total' };
  var st = { sport: 'all', m: 'all', sort: 'ev', pos: 1, open: null }, data = null, dataP = null, dataAt = 0;

  function get(n) {
    return fetch(BASE + n + '?t=' + Math.floor(Date.now() / 120000), { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function load() { return dataP || (dataP = Promise.all([get('exchange_edge_live.json'), get('exchange_edge_record.json')]).then(function (x) { data = { live: x[0], rec: x[1] }; dataAt = Date.now(); dataP = null; return data; })); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function when(t) { return new Date(t * 1000).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' }); }
  function ago(t) { var m = Math.round((Date.now() / 1000 - t) / 60); return m < 60 ? m + ' min ago' : m < 1440 ? Math.round(m / 60) + ' h ago' : Math.round(m / 1440) + ' d ago'; }
  function dur(sec) { var m = Math.round(sec / 60); return m < 1 ? 'under a minute' : m < 60 ? m + ' min' : Math.floor(m / 60) + ' h' + (m % 60 ? ' ' + (m % 60) + ' m' : ''); }
  function sg(v, d) { return (v > 0 ? '+' : '') + v.toFixed(d == null ? 1 : d); }
  function usd(v) { return '$' + (v >= 1000 ? +(v / 1000).toFixed(v % 1000 ? 1 : 0) + 'k' : Math.round(v)); }
  function chips(key, items) {
    return '<div class="veb-seg" data-k="' + key + '">' + items.map(function (i) { return '<button type="button" data-v="' + i[0] + '" class="' + (String(st[key]) === String(i[0]) ? 'on' : '') + '">' + i[1] + '</button>'; }).join('') + '</div>';
  }

  function liveRows() {
    var now = Date.now() / 1000, r = ((data.live && data.live.rows) || []).filter(function (x) { return x.start > now; });
    if (st.sport !== 'all') r = r.filter(function (x) { return x.sport === st.sport; });
    if (st.m !== 'all') r = r.filter(function (x) { return x.m === st.m; });
    if (st.pos) r = r.filter(function (x) { return x.ev > 0; });
    r.sort(st.sort === 'soon' ? function (a, b) { return a.start - b.start; } : st.sort === 'pin' ? function (a, b) { return (b.pm || -99) - (a.pm || -99); } : function (a, b) { return b.ev - a.ev; });
    return r;
  }
  function stripHtml() {
    var l = data.live; if (!l) return '';
    var age = Date.now() / 1000 - Date.parse(l.generated) / 1000, cov = l.coverage || {}, bits = [];
    ['nfl', 'cfb', 'nba'].forEach(function (sp) { var c = cov[sp]; if (c && c.games) bits.push(SPORT[sp] + ' ' + (c.novig || 0) + '/' + c.games); });
    var stale = age > 1800;
    return '<details class="veb-strip' + (stale ? ' stale' : '') + '"><summary>' + (stale ? 'Prices are ' + dur(age) + ' old. Treat every EV as expired.' : 'Prices read ' + dur(age) + ' ago') + ' <span>\u00B7 ' + bits.join(' \u00B7 ') + '</span></summary><div>Pinnacle, Novig and Kalshi are read in the same run. The numbers are how many games Novig quotes. A game with no Novig quote has no row.</div></details>';
  }
  function drawerHtml(x) {
    var f = x.fill || {}, o = '<div class="veb-drawer"><div class="veb-lad">';
    if (x.fill) {
      [['100', '$100'], ['500', '$500'], ['1000', '$1k']].forEach(function (k) { o += '<div><small>EV at ' + k[1] + '</small><b class="' + (f[k[0]] == null ? '' : f[k[0]] > 0 ? 'pos' : 'neg') + '">' + (f[k[0]] == null ? 'not deep enough' : sg(f[k[0]]) + '%') + '</b></div>'; });
      o += '<div><small>Available at +EV</small><b>' + usd(f.ev_dollars) + '</b></div>';
    } else o += '<div class="veb-note" style="margin:0">Order-book depth is not available for this row yet.</div>';
    o += '</div><div class="veb-ages">' + (x.pin_since ? 'Pinnacle last moved ' + dur(Date.now() / 1000 - x.pin_since) + ' ago' : 'Pinnacle move time unknown') + ' \u00B7 ' + (x.nov_since ? 'Novig unchanged for ' + dur(Date.now() / 1000 - x.nov_since) : 'Novig quote age unknown yet') + (x.lim ? ' \u00B7 Pinnacle limit ' + usd(x.lim) : '') + '</div>';
    o += '<div class="veb-chart" data-chart="' + esc(x.gk) + '"></div><button type="button" class="veb-open" data-gk="' + esc(x.gk) + '">Open the game page</button></div>';
    return o;
  }
  function liveHtml() {
    var rows = liveRows(), g = data.live && data.live.generated;
    var o = '<div class="veb-h"><span>Right now</span><span>' + rows.length + ' shown</span></div>';
    if (!data.live) return o + '<div class="veb-empty">The live edge file did not load. Try again in a minute.</div>';
    if (!rows.length) return o + '<div class="veb-empty">' + (st.pos ? 'Nothing is above zero EV for this filter right now.' : 'No games match this filter.') + '</div>';
    var stale = Date.now() / 1000 - Date.parse(g) / 1000 > 1800;
    rows.forEach(function (x) {
      var bits = [], key = x.gk + '|' + x.m, op = st.open === key;
      if (x.pm != null) bits.push('Pinnacle ' + sg(x.pm) + ' pts in 4h');
      if (x.nm != null) bits.push('Novig ' + sg(x.nm) + ' pts');
      if (x.fill && x.fill['500'] != null) bits.push('EV holds at $500'); else if (x.depth != null) bits.push(usd(x.depth) + ' deep');
      o += '<div class="veb-item' + (stale ? ' stale' : '') + (op ? ' open' : '') + '"><div class="veb-row" role="button" tabindex="0" aria-expanded="' + op + '" data-key="' + esc(key) + '"><div class="veb-top"><span>' + esc(x.away) + ' @ ' + esc(x.home) + '</span><span>' + SPORT[x.sport] + ' \u00B7 ' + when(x.start) + '</span></div>' +
        '<div class="veb-main"><div><b>' + MK[x.m] + '</b> ' + esc(x.label) + ' <span class="veb-px">' + esc(x.price) + '</span><small>fair ' + (x.fair * 100).toFixed(1) + '%</small></div><div class="veb-ev ' + (x.ev > 0 ? 'pos' : 'neg') + '">' + sg(x.ev) + '%<small>EV</small></div></div>' +
        (bits.length || x.stale ? '<div class="veb-sub">' + (x.stale ? '<i class="veb-stale">Pinnacle moved, Novig did not</i> ' : '') + bits.join(' \u00B7 ') + '</div>' : '') + '</div>' + (op ? drawerHtml(x) : '') + '</div>';
    });
    return o;
  }

  function sumLine(x, label) {
    var o = '<div class="veb-rr"><span>' + label + '</span><span>';
    if (!x || !x.signals) return o + 'none yet</span></div>';
    if (!x.graded) return o + x.signals + ' called, none graded yet</span></div>';
    o += x.graded + ' graded';
    if (x.same_line) o += ', beat the close ' + Math.round(x.beat_close * 100) + '%, avg ' + sg(x.mean_clv) + ' pts' + (x.ci95 != null ? ' ±' + x.ci95 : '');
    if (x.settled) o += ', ' + x.wins + '-' + (x.settled - x.wins) + ' settled, ' + sg(x.units, 2) + 'u at 1u each';
    if (x.line_moved) o += ', line moved ' + x.line_moved + ' (' + x.line_favoured + ' our way)';
    if (x.median_dur != null) o += ', usually lasts ' + dur(x.median_dur);
    return o + '</span></div>';
  }
  function recHtml() {
    var rec = data.rec; if (!rec || !rec.by_sport) return '<div class="veb-h"><span>Record of calls</span></div><div class="veb-empty">The record file did not load.</div>';
    var sports = st.sport === 'all' ? ['nfl', 'cfb', 'nba'] : [st.sport];
    var o = '<div class="veb-h"><span>Record of calls</span><span>graded on Pinnacle’s close</span></div><div class="veb-card">';
    sports.forEach(function (sp) {
      var b = rec.by_sport[sp], pick = function (thr, tag) { return b && b.summary.filter(function (x) { return x.thr === thr && x.tag === tag; })[0]; };
      if (st.sport === 'all') { o += '<div class="veb-sp">' + SPORT[sp] + '</div>' + sumLine(pick(1, 'all'), 'EV 1%+') + sumLine(pick(1, 'stale'), 'Pinnacle moved, Novig did not'); }
      else { o += sumLine(pick(1, 'all'), 'EV 1%+') + sumLine(pick(2, 'all'), 'EV 2%+') + sumLine(pick(4, 'all'), 'EV 4%+') + sumLine(pick(1, 'stale'), 'Pinnacle moved, Novig did not (EV 1%+)'); }
    });
    o += '<div class="veb-note">A call is the first time a game side reached EV 1% or more. Beat the close means Pinnacle’s last number before kickoff was better than the Novig price at the call. ± is a 95% range; a range that spans zero is still noise. Started: ' + esc(rec.since) + '. Nothing before that was stored.</div></div>';
    var calls = [];
    sports.forEach(function (sp) { ((rec.by_sport[sp] || {}).calls || []).forEach(function (c) { calls.push(Object.assign({ sport: sp }, c)); }); });
    if (st.m !== 'all') calls = calls.filter(function (c) { return c.m === st.m; });
    calls.sort(function (a, b) { return b.t - a.t; });
    o += '<div class="veb-h"><span>Every call</span><span>' + calls.length + (calls.length === 400 ? '+' : '') + '</span></div>';
    if (!calls.length) return o + '<div class="veb-empty">No calls yet. They are logged as the recorder sees them.</div>';
    calls.slice(0, 60).forEach(function (c) {
      var res = !c.graded ? '<span class="veb-pend">Pending</span>' : c.clv != null ? '<span class="' + (c.clv > 0 ? 'veb-win' : 'veb-loss') + '">' + (c.clv > 0 ? 'Beat the close ' : 'Close beat us ') + sg(c.clv) + ' pts</span>' : '<span class="' + (c.line_favoured ? 'veb-win' : 'veb-loss') + '">Line moved ' + (c.line_favoured ? 'our way' : 'against us') + '</span>';
      var tm = String(c.game).split('@'), A = c.side === 'A', side = c.m === 'tot' ? (A ? 'Over' : 'Under') : (A ? tm[1] : tm[0]);
      var line = c.m === 'sp' ? ' ' + sg(A ? c.line : -c.line, 1).replace(/\.0$/, '') : c.m === 'tot' ? ' ' + c.line : '';
      var life = (c.dur != null ? (c.open ? 'open ' : 'lasted ') + dur(c.dur) + ', peak ' + sg(c.peak) + '%' : '') + (c.nclv != null ? ' \u00B7 Novig closed ' + sg(c.nclv) + ' pts vs the call' : '') + (c.res ? ' \u00B7 ' + (c.res === 'W' ? 'won' : c.res === 'L' ? 'lost' : 'push') + ' ' + sg(c.units, 2) + 'u' : '');
      o += '<div class="veb-item"><div class="veb-row" role="button" tabindex="0" data-gk="' + esc(c.gk || '') + '"><div class="veb-top"><span>' + esc(c.game.replace('@', ' @ ')) + '</span><span>' + SPORT[c.sport] + ' · called ' + when(c.t) + '</span></div>' +
        '<div class="veb-main"><div><b>' + MK[c.m] + '</b> ' + side + line + (c.stale ? ' <i class="veb-stale">Pinnacle moved, Novig did not</i>' : '') + '<small>paid ' + Math.round(c.cost * 100) + '¢, fair ' + (c.fair * 100).toFixed(1) + '%</small></div><div class="veb-ev pos">' + sg(c.ev) + '%<small>at the call</small></div></div><div class="veb-sub">' + res + (life ? ' \u00B7 ' + life : '') + '</div></div></div>';
    });
    return o;
  }

  var CSS = '.veb{color:inherit;max-width:900px}.veb-bar{display:flex;flex-wrap:wrap;gap:6px 8px;margin:0 0 10px}.veb-seg{display:inline-flex;gap:2px;padding:2px;border-radius:9px;background:rgba(127,127,127,.14)}' +
    '.veb-seg button{font:inherit;font-size:12px;font-weight:600;line-height:1;padding:8px 9px;min-height:34px;border:0;border-radius:7px;background:transparent;color:inherit;opacity:.65;cursor:pointer}.veb-seg button.on{background:rgba(127,127,127,.32);opacity:1}' +
    '.veb-h{display:flex;justify-content:space-between;gap:12px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.6;margin:14px 0 4px}' +
    '.veb-row{padding:12px 4px;border-top:1px solid rgba(127,127,127,.2);cursor:pointer}.veb-row:focus-visible{outline:2px solid currentColor;outline-offset:2px}.veb-top{display:flex;justify-content:space-between;gap:10px;font-size:12px;opacity:.7;font-variant-numeric:tabular-nums}' +
    '.veb-main{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:4px;font-size:15px}.veb-main small{display:block;font-size:12px;opacity:.6;margin-top:2px}.veb-px{font-variant-numeric:tabular-nums;opacity:.85}.veb-px+small{display:inline;margin-left:8px}' +
    '.veb-ev{font-size:20px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}.veb-ev small{font-size:10px;font-weight:500;letter-spacing:.06em}.veb-ev.pos{color:#34c759}.veb-ev.neg{opacity:.6}' +
    '.veb-sub{margin-top:5px;font-size:12px;opacity:.78;font-variant-numeric:tabular-nums;line-height:1.5}.veb-stale{font-style:normal;font-size:11px;font-weight:600;padding:2px 7px;border-radius:999px;border:1px solid #ff9f43;color:#ff9f43;margin-right:4px}' +
    '.veb-win{color:#34c759;font-weight:600}.veb-loss{color:#ff6b6b;font-weight:600}.veb-pend{opacity:.7}.veb-card{padding:4px 0}.veb-sp{font-size:12px;font-weight:700;margin:10px 0 2px}' +
    '.veb-rr{display:flex;justify-content:space-between;gap:12px;font-size:12.5px;padding:5px 0;font-variant-numeric:tabular-nums}.veb-rr span:last-child{text-align:right;opacity:.85}.veb-note{margin-top:10px;font-size:11.5px;opacity:.55;line-height:1.5}.veb-strip{padding:8px 12px;border-radius:10px;background:rgba(127,127,127,.12);font-size:12px;line-height:1.5;margin:0 0 4px}.veb-strip summary{cursor:pointer;font-weight:600;list-style:none}.veb-strip summary::-webkit-details-marker{display:none}.veb-strip summary span{font-weight:400;opacity:.7}.veb-strip div{margin-top:6px;opacity:.7}.veb-strip.stale{background:rgba(255,107,107,.16)}.veb-item.stale{opacity:.5}.veb-item.open>.veb-row{background:rgba(127,127,127,.08);border-radius:8px}.veb-drawer{padding:10px 4px 14px;border-top:1px dashed rgba(127,127,127,.25)}.veb-lad{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:8px;margin-bottom:10px}.veb-lad div{padding:8px 10px;border-radius:8px;background:rgba(127,127,127,.1)}.veb-lad small{display:block;font-size:10.5px;opacity:.6;letter-spacing:.04em;text-transform:uppercase}.veb-lad b{font-size:15px;font-variant-numeric:tabular-nums}.veb-lad b.pos{color:#34c759}.veb-lad b.neg{opacity:.65}.veb-ages{font-size:12px;opacity:.72;margin-bottom:10px;line-height:1.5}.veb-chart{margin:6px 0 10px}.veb-open{font:inherit;font-size:12.5px;font-weight:600;padding:8px 12px;min-height:34px;border-radius:8px;border:1.5px solid currentColor;background:transparent;color:inherit;cursor:pointer;opacity:.85}.veb-empty{padding:18px 4px;font-size:13px;opacity:.65}';
  function css() { if (!document.getElementById('veb-css')) { var s = document.createElement('style'); s.id = 'veb-css'; s.textContent = CSS; document.head.appendChild(s); } }

  function render(el) {
    var o = '<div class="veb"><div class="veb-bar">' + chips('sport', [['all', 'All'], ['nfl', 'NFL'], ['cfb', 'CFB'], ['nba', 'NBA']]) + chips('pos', [[1, '+EV only'], [0, 'All']]) + chips('m', [['all', 'All'], ['ml', 'Money'], ['sp', 'Spread'], ['tot', 'Total']]) +
      chips('sort', [['ev', 'Biggest +EV'], ['soon', 'Soonest'], ['pin', 'Pinnacle moved']]) + '</div>' + stripHtml() + liveHtml() + recHtml() +
      '<div class="veb-note">Novig is a peer to peer exchange with no fee before kickoff. EV is against Pinnacle’s no-vig price, so a deep book matters: check the depth before reading a big number. Spreads and totals only show where Novig quotes Pinnacle’s exact line. Context only, not a bet signal.</div></div>';
    el.innerHTML = o;
    var host = el.querySelector('[data-chart]');
    if (host && window.VaultLineChart) {
      var k = host.getAttribute('data-chart'), x = ((data.live && data.live.rows) || []).filter(function (r) { return r.gk === k; })[0];
      if (x) window.VaultLineChart.mount(host, { key: x.gk, sport: x.sport, away: { abbr: x.away }, home: { abbr: x.home }, start: x.start, tab: x.m });
    }
  }
  function open(gk) { if (gk) location.hash = '#game/' + gk; }
  function mount(el) {
    if (!el) return;
    css();
    if (!el.__veb) {
      el.__veb = 1;
      el.addEventListener('click', function (e) {
        var b = e.target.closest('.veb-seg button');
        if (b) { var k = b.parentNode.getAttribute('data-k'); st[k] = k === 'pos' ? +b.getAttribute('data-v') : b.getAttribute('data-v'); render(el); return; }
        var ob = e.target.closest('.veb-open'); if (ob) { open(ob.getAttribute('data-gk')); return; }
        if (e.target.closest('.veb-drawer')) return;
        var r = e.target.closest('.veb-row'); if (!r) return;
        if (r.hasAttribute('data-key')) { var key = r.getAttribute('data-key'); st.open = st.open === key ? null : key; render(el); } else open(r.getAttribute('data-gk'));
      });
      el.addEventListener('keydown', function (e) { if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('veb-row')) { e.preventDefault(); e.target.click(); } });
    }
    if (data) { render(el); if (Date.now() - dataAt > 120000) load().then(function () { render(el); }); }
    else { el.innerHTML = '<div class="veb-empty">Loading…</div>'; load().then(function () { render(el); }); }
  }
  window.VaultEdgeBoard = { mount: mount };
})();
