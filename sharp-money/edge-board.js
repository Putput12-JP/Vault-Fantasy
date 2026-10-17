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
  var st = { sport: 'all', m: 'all', sort: 'ev', pos: 1 }, data = null, dataP = null, dataAt = 0;

  function get(n) {
    return fetch(BASE + n + '?t=' + Math.floor(Date.now() / 120000), { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function load() { return dataP || (dataP = Promise.all([get('exchange_edge_live.json'), get('exchange_edge_record.json')]).then(function (x) { data = { live: x[0], rec: x[1] }; dataAt = Date.now(); dataP = null; return data; })); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function when(t) { return new Date(t * 1000).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' }); }
  function ago(t) { var m = Math.round((Date.now() / 1000 - t) / 60); return m < 60 ? m + ' min ago' : m < 1440 ? Math.round(m / 60) + ' h ago' : Math.round(m / 1440) + ' d ago'; }
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
  function liveHtml() {
    var rows = liveRows(), g = data.live && data.live.generated;
    var o = '<div class="veb-h"><span>Right now</span><span>' + (g ? 'feed ' + ago(Date.parse(g) / 1000) : '') + '</span></div>';
    if (!data.live) return o + '<div class="veb-empty">The live edge file did not load. Try again in a minute.</div>';
    if (!rows.length) return o + '<div class="veb-empty">' + (st.pos ? 'Nothing is above zero EV for this filter right now.' : 'No games match this filter.') + '</div>';
    rows.forEach(function (x) {
      var bits = [];
      if (x.pm != null) bits.push('Pinnacle ' + sg(x.pm) + ' pts in 4h');
      if (x.nm != null) bits.push('Novig ' + sg(x.nm) + ' pts');
      if (x.depth != null) bits.push(usd(x.depth) + ' deep');
      if (x.lim) bits.push('Pinnacle limit ' + usd(x.lim));
      o += '<div class="veb-row" role="button" tabindex="0" data-gk="' + esc(x.gk) + '"><div class="veb-top"><span>' + esc(x.away) + ' @ ' + esc(x.home) + '</span><span>' + SPORT[x.sport] + ' · ' + when(x.start) + '</span></div>' +
        '<div class="veb-main"><div><b>' + MK[x.m] + '</b> ' + esc(x.label) + ' <span class="veb-px">' + esc(x.price) + '</span><small>fair ' + (x.fair * 100).toFixed(1) + '%</small></div><div class="veb-ev ' + (x.ev > 0 ? 'pos' : 'neg') + '">' + sg(x.ev) + '%<small>EV</small></div></div>' +
        (bits.length || x.stale ? '<div class="veb-sub">' + (x.stale ? '<i class="veb-stale">Pinnacle moved, Novig did not</i> ' : '') + bits.join(' · ') + '</div>' : '') + '</div>';
    });
    return o;
  }

  function sumLine(x, label) {
    var o = '<div class="veb-rr"><span>' + label + '</span><span>';
    if (!x || !x.signals) return o + 'none yet</span></div>';
    if (!x.graded) return o + x.signals + ' called, none graded yet</span></div>';
    o += x.graded + ' graded';
    if (x.same_line) o += ', beat the close ' + Math.round(x.beat_close * 100) + '%, avg ' + sg(x.mean_clv) + ' pts' + (x.ci95 != null ? ' ±' + x.ci95 : '');
    if (x.line_moved) o += ', line moved ' + x.line_moved + ' (' + x.line_favoured + ' our way)';
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
      o += '<div class="veb-row" role="button" tabindex="0" data-gk="' + esc(c.gk || '') + '"><div class="veb-top"><span>' + esc(c.game.replace('@', ' @ ')) + '</span><span>' + SPORT[c.sport] + ' · called ' + when(c.t) + '</span></div>' +
        '<div class="veb-main"><div><b>' + MK[c.m] + '</b> ' + side + line + (c.stale ? ' <i class="veb-stale">Pinnacle moved, Novig did not</i>' : '') + '<small>paid ' + Math.round(c.cost * 100) + '¢, fair ' + (c.fair * 100).toFixed(1) + '%</small></div><div class="veb-ev pos">' + sg(c.ev) + '%<small>at the call</small></div></div><div class="veb-sub">' + res + '</div></div>';
    });
    return o;
  }

  var CSS = '.veb{color:inherit;max-width:900px}.veb-bar{display:flex;flex-wrap:wrap;gap:8px 12px;margin:0 0 14px}.veb-seg{display:inline-flex;gap:2px;padding:2px;border-radius:9px;background:rgba(127,127,127,.14)}' +
    '.veb-seg button{font:inherit;font-size:12.5px;font-weight:600;line-height:1;padding:8px 11px;min-height:34px;border:0;border-radius:7px;background:transparent;color:inherit;opacity:.65;cursor:pointer}.veb-seg button.on{background:rgba(127,127,127,.32);opacity:1}' +
    '.veb-h{display:flex;justify-content:space-between;gap:12px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.6;margin:20px 0 8px}' +
    '.veb-row{padding:12px 4px;border-top:1px solid rgba(127,127,127,.2);cursor:pointer}.veb-row:focus-visible{outline:2px solid currentColor;outline-offset:2px}.veb-top{display:flex;justify-content:space-between;gap:10px;font-size:12px;opacity:.7;font-variant-numeric:tabular-nums}' +
    '.veb-main{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:4px;font-size:15px}.veb-main small{display:block;font-size:12px;opacity:.6;margin-top:2px}.veb-px{font-variant-numeric:tabular-nums;opacity:.85}.veb-px+small{display:inline;margin-left:8px}' +
    '.veb-ev{font-size:20px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}.veb-ev small{font-size:10px;font-weight:500;letter-spacing:.06em}.veb-ev.pos{color:#34c759}.veb-ev.neg{opacity:.6}' +
    '.veb-sub{margin-top:5px;font-size:12px;opacity:.78;font-variant-numeric:tabular-nums;line-height:1.5}.veb-stale{font-style:normal;font-size:11px;font-weight:600;padding:2px 7px;border-radius:999px;border:1px solid #ff9f43;color:#ff9f43;margin-right:4px}' +
    '.veb-win{color:#34c759;font-weight:600}.veb-loss{color:#ff6b6b;font-weight:600}.veb-pend{opacity:.7}.veb-card{padding:4px 0}.veb-sp{font-size:12px;font-weight:700;margin:10px 0 2px}' +
    '.veb-rr{display:flex;justify-content:space-between;gap:12px;font-size:12.5px;padding:5px 0;font-variant-numeric:tabular-nums}.veb-rr span:last-child{text-align:right;opacity:.85}.veb-note{margin-top:10px;font-size:11.5px;opacity:.55;line-height:1.5}.veb-empty{padding:18px 4px;font-size:13px;opacity:.65}';
  function css() { if (!document.getElementById('veb-css')) { var s = document.createElement('style'); s.id = 'veb-css'; s.textContent = CSS; document.head.appendChild(s); } }

  function render(el) {
    var o = '<div class="veb"><div class="veb-bar">' + chips('sport', [['all', 'All'], ['nfl', 'NFL'], ['cfb', 'CFB'], ['nba', 'NBA']]) + chips('m', [['all', 'All markets'], ['ml', 'Money'], ['sp', 'Spread'], ['tot', 'Total']]) +
      chips('sort', [['ev', 'Biggest +EV'], ['soon', 'Soonest'], ['pin', 'Pinnacle moved']]) + chips('pos', [[1, '+EV only'], [0, 'All']]) + '</div>' + liveHtml() + recHtml() +
      '<div class="veb-note">Novig is a peer to peer exchange with no fee before kickoff. EV is against Pinnacle’s no-vig price, so a deep book matters: check the depth before reading a big number. Spreads and totals only show where Novig quotes Pinnacle’s exact line. Context only, not a bet signal.</div></div>';
    el.innerHTML = o;
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
        var r = e.target.closest('.veb-row'); if (r) open(r.getAttribute('data-gk'));
      });
      el.addEventListener('keydown', function (e) { if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('veb-row')) { e.preventDefault(); open(e.target.getAttribute('data-gk')); } });
    }
    if (data) { render(el); if (Date.now() - dataAt > 120000) load().then(function () { render(el); }); }
    else { el.innerHTML = '<div class="veb-empty">Loading…</div>'; load().then(function () { render(el); }); }
  }
  window.VaultEdgeBoard = { mount: mount };
})();
