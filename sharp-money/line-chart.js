/* Vault line movement chart. One module shared by the classic page and new/. Context only, never a bet signal.
   Reads the NFL book tape (data/book_tape/nfl/YYYY-MM.jsonl, written every 20 minutes by scripts/book_tape.py):
   one row per book per game, appended only when that book's line changes, so each series is a step line.
   Books on the tape: Pinnacle, DraftKings, FanDuel, BetMGM, BetRivers, bet365, Consensus and Open.
   Not on the tape: Circa, Bookmaker, Novig, Pinnacle limits. Nothing here is invented to fill those in. */
(function () {
  var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname), LIVE = /[?&]live\b/.test(location.search);
  var RAW = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/main/data/book_tape/nfl/';
  var BASE = LOCAL && !LIVE ? '/data/book_tape/nfl/' : RAW;
  var ALIAS = { WSH: 'WAS', LA: 'LAR', JAC: 'JAX', LVR: 'LV', OAK: 'LV' };
  var BOOKS = [
    ['Pinnacle', '#ff5fa2', 1], ['DraftKings', '#5ec269', 1], ['FanDuel', '#4aa3ff', 1], ['BetMGM', '#d9a93f', 1],
    ['BetRivers', '#b78cff', 0], ['bet365', '#22c7a9', 0], ['Consensus', '#c9ccd3', 0], ['Open', '#8e8e93', 1]
  ];
  var MARKETS = [['sp', 'Spread'], ['tot', 'Total'], ['ml', 'Money']];
  var WINDOWS = [['4h', 4 * 3600], ['12h', 12 * 3600], ['24h', 24 * 3600], ['All', 0]];
  var tape = null, tapeP = null, states = {}, hosts = new WeakMap();

  function monthKey(d) { return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0'); }
  function load() {
    if (tape) return Promise.resolve(tape);
    if (tapeP) return tapeP;
    var now = new Date(), prev = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1));
    var get = function (k) {
      return fetch(BASE + k + '.jsonl?t=' + Math.floor(Date.now() / 300000), { cache: 'no-store' })
        .then(function (r) { return r.ok ? r.text() : ''; }).catch(function () { return ''; });
    };
    tapeP = Promise.all([get(monthKey(prev)), get(monthKey(now))]).then(function (txt) {
      var rows = [];
      txt.join('\n').split('\n').forEach(function (l) { if (l) { try { rows.push(JSON.parse(l)); } catch (e) {} } });
      tape = rows; return tape;
    });
    return tapeP;
  }

  function ab(x) { x = String(x || '').toUpperCase(); return ALIAS[x] || x; }
  function gameRows(g) {
    var a = ab(g.away && g.away.abbr), h = ab(g.home && g.home.abbr);
    return (tape || []).filter(function (r) { return r.away === a && r.home === h && Math.abs(r.start - g.start) < 6 * 3600; });
  }
  function dv(a, b) { // de-vigged home win probability from the two stored moneylines
    var p = function (m) { return m < 0 ? -m / (-m + 100) : 100 / (m + 100); }, pa = p(a), ph = p(b);
    return ph / (pa + ph);
  }
  function val(r, mk) {
    if (mk === 'sp') return r.sp && r.sp[0] != null ? r.sp[0] : null;
    if (mk === 'tot') return r.tot && r.tot[0] != null ? r.tot[0] : null;
    return r.ml && r.ml[0] != null && r.ml[1] != null ? dv(r.ml[0], r.ml[1]) * 100 : null;
  }
  function am(x) { return x > 0 ? '+' + x : String(x); }
  function fmt(v, mk) { return mk === 'ml' ? v.toFixed(1) + '%' : (mk === 'sp' && v > 0 ? '+' : '') + v; }

  function build(g, st) {
    var rows = gameRows(g), mk = st.m, now = Date.now() / 1000, tmax = Math.min(now, g.start);
    var by = {};
    rows.forEach(function (r) { var v = val(r, mk); if (v != null) (by[r.book] = by[r.book] || []).push([r.t, v, r]); });
    var out = [];
    BOOKS.forEach(function (b) {
      var p = by[b[0]]; if (!p) return;
      p.sort(function (x, y) { return x[0] - y[0]; });
      out.push({ book: b[0], color: b[1], pts: p, on: st.hide[b[0]] == null ? !!b[2] : !st.hide[b[0]] });
    });
    var first = Infinity; out.forEach(function (s) { first = Math.min(first, s.pts[0][0]); });
    var span = st.w ? st.w : 0, tmin = span ? Math.max(tmax - span, Math.min(first, tmax)) : Math.min(first, tmax);
    if (!(tmax > tmin)) tmax = tmin + 1;
    return { series: out, tmin: tmin, tmax: tmax, n: rows.length };
  }
  function valueAt(s, t, mk) { // step value held at time t, or null before the first sample
    var v = null; for (var i = 0; i < s.pts.length; i++) { if (s.pts[i][0] <= t) v = s.pts[i]; else break; } return v;
  }

  function svg(d, st, W) {
    var H = W < 480 ? 220 : 250, L = 44, R = 12, T = 12, B = 26, vis = d.series.filter(function (s) { return s.on; });
    if (!vis.length) return '<div class="vlm-empty">Turn a book on to see its line.</div>';
    var lo = Infinity, hi = -Infinity;
    vis.forEach(function (s) {
      s.pts.forEach(function (p) { if (p[0] >= d.tmin - 1) { lo = Math.min(lo, p[1]); hi = Math.max(hi, p[1]); } });
      var v0 = valueAt(s, d.tmin); if (v0) { lo = Math.min(lo, v0[1]); hi = Math.max(hi, v0[1]); }
    });
    if (!isFinite(lo)) return '<div class="vlm-empty">No line changes in this window.</div>';
    var pad = st.m === 'ml' ? 1 : 0.5; lo -= pad; hi += pad;
    if (hi - lo < (st.m === 'ml' ? 4 : 2)) { var mid = (hi + lo) / 2, hf = st.m === 'ml' ? 2 : 1; lo = mid - hf; hi = mid + hf; }
    var step = st.m === 'ml' ? ([1, 2, 5, 10].filter(function (s) { return (hi - lo) / s <= 5; })[0] || 10) : ([0.5, 1, 2, 5].filter(function (s) { return (hi - lo) / s <= 5; })[0] || 5);
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
    var X = function (t) { return L + (t - d.tmin) / (d.tmax - d.tmin) * (W - L - R); };
    var Y = function (v) { return T + (hi - v) / (hi - lo) * (H - T - B); };
    var o = '<svg class="vlm-svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Line movement by book">';
    for (var v = lo; v <= hi + 1e-9; v += step) {
      o += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(v).toFixed(1) + '" y2="' + Y(v).toFixed(1) + '" class="vlm-grid"/><text x="' + (L - 6) + '" y="' + (Y(v) + 4).toFixed(1) + '" text-anchor="end" class="vlm-ax">' + fmt(+v.toFixed(2), st.m) + '</text>';
    }
    var ticks = W < 480 ? 2 : 4;
    for (var i = 0; i <= ticks; i++) {
      var t = d.tmin + (d.tmax - d.tmin) * i / ticks, dt = new Date(t * 1000);
      var lab = (d.tmax - d.tmin) > 36 * 3600 ? dt.toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' }) + (W < 480 ? '' : ' ' + dt.toLocaleTimeString(undefined, { hour: 'numeric' })) : dt.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
      o += '<text x="' + X(t).toFixed(1) + '" y="' + (H - 6) + '" text-anchor="' + (i === 0 ? 'start' : i === ticks ? 'end' : 'middle') + '" class="vlm-ax">' + lab + '</text>';
    }
    var order = vis.slice().sort(function (a, b) { return (a.book === 'Pinnacle') - (b.book === 'Pinnacle'); }); // Pinnacle drawn last, on top
    order.forEach(function (s) {
      var start = valueAt(s, d.tmin), pts = [];
      if (start) pts.push([d.tmin, start[1]]);
      s.pts.forEach(function (p) { if (p[0] > d.tmin && p[0] <= d.tmax) pts.push([p[0], p[1]]); });
      if (!pts.length) return;
      var path = 'M' + X(pts[0][0]).toFixed(1) + ' ' + Y(pts[0][1]).toFixed(1);
      for (var k = 1; k < pts.length; k++) path += 'H' + X(pts[k][0]).toFixed(1) + 'V' + Y(pts[k][1]).toFixed(1);
      path += 'H' + X(d.tmax).toFixed(1);
      var open = s.book === 'Open', w = s.book === 'Pinnacle' ? 2.6 : 1.8;
      o += '<path d="' + path + '" fill="none" stroke="' + s.color + '" stroke-width="' + w + '" stroke-linejoin="round"' + (open ? ' stroke-dasharray="5 4"' : '') + '/>';
      var last = pts[pts.length - 1];
      o += '<circle cx="' + X(d.tmax).toFixed(1) + '" cy="' + Y(last[1]).toFixed(1) + '" r="' + (s.book === 'Pinnacle' ? 3.6 : 2.8) + '" fill="' + s.color + '"/>';
    });
    o += '<line class="vlm-cur" x1="0" x2="0" y1="' + T + '" y2="' + (H - B) + '" style="display:none"/>';
    return o + '<rect class="vlm-hit" x="' + L + '" y="' + T + '" width="' + (W - L - R) + '" height="' + (H - T - B) + '" fill="transparent"/></svg>';
  }

  var CSS = '.vlm{color:inherit}.vlm-tabs{display:flex;gap:6px;flex-wrap:wrap;justify-content:space-between;margin:0 0 10px}.vlm-seg{display:inline-flex;gap:2px;padding:2px;border-radius:9px;background:rgba(127,127,127,.14)}' +
    '.vlm-seg button{font:inherit;font-size:12px;font-weight:600;line-height:1;padding:7px 10px;min-height:30px;border:0;border-radius:7px;background:transparent;color:inherit;opacity:.65;cursor:pointer}' +
    '.vlm-seg button.on{background:rgba(127,127,127,.32);opacity:1}.vlm-svg{width:100%;height:auto;display:block;touch-action:pan-y}.vlm-grid{stroke:rgba(127,127,127,.22);stroke-width:1}' +
    '.vlm-ax{font-size:10.5px;fill:currentColor;opacity:.55;font-variant-numeric:tabular-nums}.vlm-cur{stroke:currentColor;opacity:.4;stroke-width:1}' +
    '.vlm-legend{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.vlm-chip{display:inline-flex;align-items:center;gap:6px;font:inherit;font-size:12px;font-weight:600;padding:6px 10px;min-height:32px;border-radius:999px;border:1.5px solid var(--c);background:transparent;color:inherit;cursor:pointer;font-variant-numeric:tabular-nums}' +
    '.vlm-chip.off{opacity:.4;border-style:dashed}.vlm-chip i{font-style:normal;opacity:.8;font-weight:500}.vlm-read{min-height:18px;margin-top:8px;font-size:12px;opacity:.75;font-variant-numeric:tabular-nums}' +
    '.vlm-empty{padding:18px 4px;font-size:13px;opacity:.65}.vlm-note{margin-top:8px;font-size:11.5px;opacity:.55}';
  function css() { if (!document.getElementById('vlm-css')) { var s = document.createElement('style'); s.id = 'vlm-css'; s.textContent = CSS; document.head.appendChild(s); } }

  function html(g, st, d, W) {
    var mk = st.m, o = '<div class="vlm"><div class="vlm-tabs"><div class="vlm-seg" data-vlm-k="m">';
    MARKETS.forEach(function (m) { o += '<button type="button" data-v="' + m[0] + '" class="' + (m[0] === mk ? 'on' : '') + '">' + m[1] + '</button>'; });
    o += '</div><div class="vlm-seg" data-vlm-k="w">';
    WINDOWS.forEach(function (w) { o += '<button type="button" data-v="' + w[1] + '" class="' + (w[1] === st.w ? 'on' : '') + '">' + w[0] + '</button>'; });
    o += '</div></div>' + svg(d, st, W) + '<div class="vlm-read" aria-live="off"></div><div class="vlm-legend">';
    d.series.forEach(function (s) {
      var last = s.pts[s.pts.length - 1];
      o += '<button type="button" class="vlm-chip' + (s.on ? '' : ' off') + '" style="--c:' + s.color + '" data-b="' + s.book + '" aria-pressed="' + s.on + '">' + s.book + ' <i>' + fmt(+last[1].toFixed(mk === 'ml' ? 1 : 2), mk) + '</i></button>';
    });
    var homeAbbr = g.home && g.home.abbr;
    return o + '</div><div class="vlm-note">' + (mk === 'sp' ? homeAbbr + ' spread. ' : mk === 'ml' ? homeAbbr + ' win chance from each book’s moneyline, vig removed. ' : '') +
      'Steps are when a book changed its line. Context only, not a bet signal.</div></div>';
  }

  function render(el, g) {
    var st = states[g.key]; if (!st) st = states[g.key] = { m: 'sp', w: 24 * 3600, hide: {} };
    var d = build(g, st), W = Math.min(720, Math.max(280, Math.round(el.clientWidth || 640)));
    if (!d.series.length) { el.innerHTML = '<div class="vlm-empty">No line history recorded for this game yet.</div>'; return; }
    el.innerHTML = html(g, st, d, W);
    var sv = el.querySelector('.vlm-svg'); if (!sv) return;
    var cur = sv.querySelector('.vlm-cur'), rd = el.querySelector('.vlm-read');
    var move = function (e) {
      var r = sv.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * W;
      if (x < 44 || x > W - 12) return;
      var t = d.tmin + (x - 44) / (W - 44 - 12) * (d.tmax - d.tmin);
      cur.setAttribute('x1', x); cur.setAttribute('x2', x); cur.style.display = '';
      var dt = new Date(t * 1000), parts = [dt.toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })];
      d.series.forEach(function (s) {
        if (!s.on || s.book === 'Open') return;
        var p = valueAt(s, t); if (p) parts.push(s.book + ' ' + (st.m === 'ml' ? fmtMl(p[2]) : fmt(p[1], st.m)));
      });
      rd.textContent = parts.join('  ·  ');
    };
    sv.addEventListener('pointermove', move); sv.addEventListener('pointerdown', move);
    sv.addEventListener('pointerleave', function () { cur.style.display = 'none'; rd.textContent = ''; });
  }
  function fmtMl(r) { return r && r.ml ? am(r.ml[0]) + '/' + am(r.ml[1]) : ''; }

  function mount(el, g) {
    if (!el || !g || g.sport !== 'nfl') return;
    css(); hosts.set(el, g);
    if (!el.__vlm) {
      el.__vlm = 1;
      el.addEventListener('click', function (e) {
        var b = e.target.closest('button'); if (!b) return;
        var gg = hosts.get(el), st = states[gg.key]; if (!st) return;
        var seg = b.parentNode && b.parentNode.getAttribute('data-vlm-k');
        if (seg === 'm') st.m = b.getAttribute('data-v');
        else if (seg === 'w') st.w = +b.getAttribute('data-v');
        else if (b.hasAttribute('data-b')) { var k = b.getAttribute('data-b'), on = !b.classList.contains('off'); st.hide[k] = on; }
        else return;
        render(el, gg);
      });
    }
    if (tape) render(el, g);
    else { el.innerHTML = '<div class="vlm-empty">Loading line history…</div>'; load().then(function () { if (hosts.get(el) === g) render(el, g); }); }
  }
  function scan(root, lookup) {
    (root || document).querySelectorAll('[data-vlm-key]').forEach(function (el) { mount(el, lookup(el.getAttribute('data-vlm-key'))); });
  }
  window.VaultLineChart = { mount: mount, scan: scan, load: load };
})();
