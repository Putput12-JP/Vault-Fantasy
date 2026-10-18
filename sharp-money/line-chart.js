/* Vault line movement chart. One module shared by the classic page and new/. Context only, never a bet signal.
   Reads the book tape for the game's sport (data/book_tape/<nfl|cfb|nba>/YYYY-MM.jsonl; the NFL by scripts/book_tape.py every 20
   minutes, college and NBA by scripts/sharp_tape.py each Sharp Money refresh):
   one row per book per game, appended only when that book's line changes, so each series is a step line.
   Books on the tape: Pinnacle, DraftKings, FanDuel, BetMGM, BetRivers, bet365, Consensus and Open, plus the
   Novig and Kalshi exchanges (Money tab only: they quote a win chance, not a spread or total, and were first recorded 2026-10-17).
   Circa and Bookmaker come from SmartStake and are LOCAL ONLY: their API terms forbid publishing the data or showing it in the UI
   without written permission, so they load only on localhost with ?ss (from data/smartstake/book_tape/, gitignored, built by
   scripts/smartstake_to_book_tape.py). In production they never load and the lines stay off the chart. Nothing here is invented. */
(function () {
  var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname), LIVE = /[?&]live\b/.test(location.search);
  var BASE = LOCAL && !LIVE ? '/data/book_tape/' : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/main/data/book_tape/';   // + <sport>/<YYYY-MM>.jsonl
  var ALIAS = { WSH: 'WAS', LA: 'LAR', JAC: 'JAX', LVR: 'LV', OAK: 'LV' };
  var BOOKS = [
    ['Pinnacle', '#ff5fa2', 1], ['DraftKings', '#5ec269', 1], ['FanDuel', '#4aa3ff', 1], ['BetMGM', '#d9a93f', 1],
    ['Novig', '#ff9f43', 1], ['Kalshi', '#19d3f0', 1], ['Circa', '#ef5b5b', 1], ['Bookmaker', '#a3e635', 0], ['BetRivers', '#b78cff', 0], ['bet365', '#38d6a0', 0], ['Consensus', '#c9ccd3', 0], ['Open', '#8e8e93', 1]
  ];
  var MARKETS = [['sp', 'Spread'], ['tot', 'Total'], ['ml', 'Money']];
  var WINDOWS = [['4h', 4 * 3600], ['12h', 12 * 3600], ['24h', 24 * 3600], ['All', 0]];
  var SS = LOCAL && !LIVE && /[?&]ss\b/.test(location.search), SSBASE = '/data/smartstake/book_tape/';   // permission-gated, see the header
  var REC = (LOCAL && !LIVE ? '/data/' : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/main/data/') + 'exchange_edge_record.json';
  var rec = null, recP = null, tapes = {}, tapeP = {}, states = {}, hosts = new WeakMap();

  function monthKey(d) { return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0'); }
  function load(sport) {
    if (tapes[sport]) return Promise.resolve(tapes[sport]);
    if (tapeP[sport]) return tapeP[sport];
    var now = new Date(), prev = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1));
    var get = function (k) {
      return fetch(BASE + sport + '/' + k + '.jsonl?t=' + Math.floor(Date.now() / 300000), { cache: 'no-store' })
        .then(function (r) { return r.ok ? r.text() : ''; }).catch(function () { return ''; });
    };
    var recGet = recP || (recP = fetch(REC + '?t=' + Math.floor(Date.now() / 300000), { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (j) { rec = j; }));
    var ssGet = function (k) {
      if (!SS) return Promise.resolve('');
      return fetch(SSBASE + sport + '/' + k + '.jsonl?t=' + Date.now(), { cache: 'no-store' }).then(function (r) { return r.ok ? r.text() : ''; }).catch(function () { return ''; });
    };
    tapeP[sport] = Promise.all([get(monthKey(prev)), get(monthKey(now)), get('backfill'), recGet, ssGet(monthKey(prev)), ssGet(monthKey(now))]).then(function (x) {
      var rows = [];
      x.slice(0, 3).concat(x.slice(4)).join('\n').split('\n').forEach(function (l) { if (l) { try { rows.push(JSON.parse(l)); } catch (e) {} } });
      tapes[sport] = rows; return rows;
    });
    return tapeP[sport];
  }

  function ab(x) { x = String(x || '').toUpperCase(); return ALIAS[x] || x; }
  function gameRows(g) {
    var t = tapes[g.sport] || [];
    if (g.sport !== 'nfl') return t.filter(function (r) { return r.gk === g.key; });   // college and NBA rows carry the feed's game key
    var a = ab(g.away && g.away.abbr), h = ab(g.home && g.home.abbr);
    return t.filter(function (r) { return r.away === a && r.home === h && Math.abs(r.start - g.start) < 6 * 3600; });
  }
  function dv(a, b) { // de-vigged home win probability from the two stored moneylines (away, home), power method
    var p = function (m) { return m < 0 ? -m / (-m + 100) : 100 / (m + 100); };
    return powFair(p(b), p(a));
  }
  function val(r, mk) {
    if (r.bf && !r.px) { var bv = mk === 'ml' ? (r.mlp != null ? r.mlp * 100 : null) : mk === 'sp' ? r.spl : r.totl; return bv == null ? null : bv; }   // backfilled Pinnacle: line or win chance only, no prices
    if (mk === 'sp') return r.sp && r.sp[0] != null ? r.sp[0] : null;
    if (mk === 'tot') return r.tot && r.tot[0] != null ? r.tot[0] : null;
    if (r.px) return r.px[1] - r.px[0] <= 0.10 ? (r.px[0] + r.px[1]) / 2 * 100 : null;   // exchange: mid of the stored bid and ask, only when tight
    return r.ml && r.ml[0] != null && r.ml[1] != null ? dv(r.ml[0], r.ml[1]) * 100 : null;
  }
  function am(x) { return x > 0 ? '+' + x : String(x); }
  function usd(v) { return '$' + (v >= 1000 ? +(v / 1000).toFixed(v % 1000 ? 1 : 0) + 'k' : v); }
  /* Price view: a book's American price for ONE side at Pinnacle's current line, so a move from -138 to -157 at a fixed number is visible.
     Prices cross the +100/-100 gap, so they are plotted on a continuous scale (a > 0 ? a - 100 : a + 100) and labelled back to American. */
  function pToY(a) { return a > 0 ? a - 100 : a + 100; }
  function yToP(v) { v = Math.round(v); return v === 0 ? 'EVEN' : v > 0 ? '+' + (v + 100) : String(v - 100); }
  function pval(r, mk, side, ref) {
    if (r.px || (r.bf && !r.px)) return null;   // exchanges and backfilled Pinnacle carry no American price
    var a = null;
    if (mk === 'ml') a = r.ml && r.ml[side] != null ? r.ml[side] : null;
    else { var x = r[mk]; if (x && x[0] === ref && x[1 + side] != null) a = x[1 + side]; }
    return a == null ? null : pToY(a);
  }
  function refLine(rows, mk) { // Pinnacle's latest stored line for the market
    var f = null; rows.forEach(function (r) { if (r.book === 'Pinnacle' && !r.bf && r[mk] && r[mk][0] != null && (!f || r.t >= f.t)) f = r; });
    return f ? f[mk][0] : null;
  }
  function sideNames(g, mk, ref) {
    var h = g.home && g.home.abbr, a = g.away && g.away.abbr, sg = function (v) { return (v > 0 ? '+' : '') + v; };
    return mk === 'ml' ? [a, h] : mk === 'sp' ? [h + ' ' + sg(ref), a + ' ' + sg(-ref)] : ['Over ' + ref, 'Under ' + ref];
  }
  function vlab(v, st) { return st.v === 'price' ? yToP(v) : fmt(+v.toFixed(st.m === 'ml' ? 1 : 2), st.m); }
  function fmt(v, mk) { return mk === 'ml' ? v.toFixed(1) + '%' : (mk === 'sp' && v > 0 ? '+' : '') + v; }

  function build(g, st) {
    var rows = gameRows(g), mk = st.m, now = Date.now() / 1000, tmax = Math.min(now, g.start);
    var by = {}, pm = st.v === 'price', ref = pm && mk !== 'ml' ? refLine(rows, mk) : null, sd = st.s || 0;
    rows.forEach(function (r) { var v = pm ? pval(r, mk, sd, ref) : val(r, mk); if (v != null) (by[r.book] = by[r.book] || []).push([r.t, v, r]); });
    var out = [];
    BOOKS.forEach(function (b) {
      var p = by[b[0]]; if (!p) return;
      p.sort(function (x, y) { return x[0] - y[0]; });
      out.push({ book: b[0], color: b[1], pts: p, on: st.hide[b[0]] == null ? !!b[2] : !st.hide[b[0]] });
    });
    var li = mk === 'ml' ? 0 : mk === 'sp' ? 1 : 2, lp = [];
    rows.forEach(function (r) { if (r.book === 'Pinnacle' && r.lim && r.lim[li] != null) lp.push([r.t, r.lim[li], r]); });
    lp.sort(function (x, y) { return x[0] - y[0]; });
    var lim = lp.length ? { book: 'Pinnacle limits', color: 'currentColor', pts: lp, on: st.hide['Pinnacle limits'] == null ? true : !st.hide['Pinnacle limits'], lim: 1 } : null;
    var first = Infinity; out.forEach(function (s) { first = Math.min(first, s.pts[0][0]); });
    var span = st.w ? st.w : 0, tmin = span ? Math.max(tmax - span, Math.min(first, tmax)) : Math.min(first, tmax);
    if (!(tmax > tmin)) tmax = tmin + 1;
    return { series: out, lim: lim, tmin: tmin, tmax: tmax, n: rows.length, rows: rows, ref: ref, pm: pm };
  }
  function valueAt(s, t, mk) { // step value held at time t, or null before the first sample
    var v = null; for (var i = 0; i < s.pts.length; i++) { if (s.pts[i][0] <= t) v = s.pts[i]; else break; } return v;
  }


  /* Exchange edge: Novig's price against Pinnacle's no-vig fair price, per market. EV = fair chance / price paid - 1, where the
     price paid to buy a side is its ask (1 minus the best bid on the other side). Pregame Novig charges no fee. Every number is a
     stored quote; a market with no Novig quote at Pinnacle's current line is left out rather than guessed. */
  function pfn(a) { return a < 0 ? -a / (-a + 100) : 100 / (a + 100); }
  function powFair(x, y) { var lo = 0.5, hi = 3, k; for (var i = 0; i < 40; i++) { k = (lo + hi) / 2; if (Math.pow(x, k) + Math.pow(y, k) > 1) lo = k; else hi = k; } return Math.pow(x, (lo + hi) / 2); }   // power de-vig, same as devig() in fetch-sharp-money.mjs
  function fairFirst(a, b) { return powFair(pfn(a), pfn(b)); }
  function priceAm(p) { return p < 0.5 ? '+' + Math.round(100 * (1 - p) / p) : String(Math.round(-100 * p / (1 - p))); }
  function pick(rows, book, field, t) {
    var f = null;
    for (var i = 0; i < rows.length; i++) { var r = rows[i]; if (r.book === book && r[field] != null && r.t <= t && (!f || r.t >= f.t)) f = r; }
    return f;
  }
  function edgeRows(g, d, w) {
    var rows = d.rows.filter(function (r) { return !r.bf; }), now = Date.now() / 1000, tnow = now + 1, t0 = d.tmin, ha = g.home.abbr, aa = g.away.abbr;
    var sg = function (v) { return (v > 0 ? '+' : '') + v; };
    var spec = [
      ['Money', 'ml', 'px', function (p) { return { fair: fairFirst(p.ml[1], p.ml[0]), line: null }; }, ha, aa],
      ['Spread', 'sp', 'nsp', function (p) { return { fair: fairFirst(p.sp[1], p.sp[2]), line: p.sp[0] }; }, null, null],
      ['Total', 'tot', 'ntot', function (p) { return { fair: fairFirst(p.tot[1], p.tot[2]), line: p.tot[0] }; }, 'Over', 'Under']
    ], out = [];
    spec.forEach(function (sp) {
      var pr = pick(rows, 'Pinnacle', sp[1], tnow), nv = pick(rows, 'Novig', sp[2], tnow); if (!pr || !nv) return;
      var P = sp[3](pr), q = sp[2] === 'px' ? nv.px : nv[sp[2]], bid = sp[2] === 'px' ? q[0] : q[1], ask = sp[2] === 'px' ? q[1] : q[2];
      if (sp[2] !== 'px' && q[0] !== P.line) return;
      var evA = P.fair / ask - 1, evB = (1 - P.fair) / (1 - bid) - 1, a = evA >= evB, side = a ? P.fair : 1 - P.fair;
      var lbA = sp[1] === 'sp' ? ha + ' ' + sg(P.line) : sp[1] === 'tot' ? 'Over ' + P.line : sp[4], lbB = sp[1] === 'sp' ? aa + ' ' + sg(-P.line) : sp[1] === 'tot' ? 'Under ' + P.line : sp[5];
      var cost = a ? ask : 1 - bid, row = { m: sp[0], side: a ? lbA : lbB, ev: (a ? evA : evB) * 100, price: priceAm(cost), cents: Math.round(cost * 1000) / 10, fair: side * 100, since: nv.t };
      var pr0 = pick(rows, 'Pinnacle', sp[1], t0), nv0 = pick(rows, 'Novig', sp[2], t0);
      if (pr0 && nv0) {
        var P0 = sp[3](pr0), q0 = sp[2] === 'px' ? nv0.px : nv0[sp[2]];
        if (P0.line === P.line && (sp[2] === 'px' || q0[0] === q[0])) {
          var m1 = sp[2] === 'px' ? (q[0] + q[1]) / 2 : (q[1] + q[2]) / 2, m0 = sp[2] === 'px' ? (q0[0] + q0[1]) / 2 : (q0[1] + q0[2]) / 2;
          row.pm = (a ? 1 : -1) * (P.fair - P0.fair) * 100; row.nm = (a ? 1 : -1) * (m1 - m0) * 100;
        } else if (P0.line !== P.line) row.lineMove = P0.line + ' to ' + P.line;
      }
      out.push(row);
    });
    return out;
  }

  function recHtml(sport) {
    var rs = rec && (rec.by_sport ? rec.by_sport[sport] : sport === 'nfl' ? rec : null);
    if (!rs || !rs.summary) return '';
    var line = function (x, label) {
      var o = '<div class="vlm-rr"><span>' + label + '</span><span>';
      if (!x.graded) return o + (x.signals ? x.signals + ' seen, none graded yet' : 'none yet') + '</span></div>';
      o += x.graded + ' graded';
      if (x.same_line) o += ', beat the close ' + Math.round(x.beat_close * 100) + '%, avg ' + (x.mean_clv > 0 ? '+' : '') + x.mean_clv + ' pts' + (x.ci95 != null ? ' \u00B1' + x.ci95 : '');
      if (x.line_moved) o += ', line moved ' + x.line_moved + ' (' + x.line_favoured + ' our way)';
      return o + '</span></div>';
    };
    var pick = function (thr, tag) { return rs.summary.filter(function (x) { return x.thr === thr && x.tag === tag; })[0]; };
    var o = '<div class="vlm-rec"><div class="vlm-eh">Record since Oct 17<span>graded on Pinnacle\u2019s close</span></div>';
    [[1, 'EV 1%+'], [2, 'EV 2%+'], [4, 'EV 4%+']].forEach(function (a) { var x = pick(a[0], 'all'); if (x) o += line(x, a[1]); });
    var st = pick(1, 'stale'); if (st) o += line(st, 'Pinnacle moved, Novig did not (EV 1%+)');
    return o + '<div class="vlm-note">Each game side counts once, the first time it reached the EV. Beat the close means Pinnacle\u2019s last number before kickoff was better than the Novig price. \u00B1 is a 95% range, and a range that spans zero means this is still noise. Context only.</div></div>';
  }
  function edgeHtml(g, d, w) {
    var rs = edgeRows(g, d, w); if (!rs.length) return '';
    var s1 = function (v) { return (v > 0 ? '+' : '') + v.toFixed(1); };
    var o = '<div class="vlm-edge"><div class="vlm-eh">Novig price vs Pinnacle fair<span>context only</span></div>';
    rs.forEach(function (r) {
      var mv = r.pm != null ? 'Pinnacle ' + s1(r.pm) + ' pts, Novig ' + s1(r.nm) + ' pts in this window' : r.lineMove ? 'Pinnacle line moved ' + r.lineMove : '';
      o += '<div class="vlm-er"><div class="vlm-em"><b>' + r.m + '</b> ' + r.side + '</div><div class="vlm-ev ' + (r.ev > 0 ? 'pos' : 'neg') + '">' + s1(r.ev) + '% EV</div>' +
        '<div class="vlm-ed">Novig ' + r.price + ' (' + r.cents + '\u00A2) vs Pinnacle fair ' + r.fair.toFixed(1) + '%' + (mv ? '<br>' + mv : '') + '</div></div>';
    });
    return o + '<div class="vlm-note">Fair is Pinnacle\u2019s price with the vig removed. Novig has no fee before kickoff. Spread and total only where Novig quotes Pinnacle\u2019s exact line.</div>' + recHtml(g.sport) + '</div>';
  }

  /* One plain sentence of what Pinnacle did to the selected side in the window, from stored rows only: price, de-vigged fair, limit. */
  function moveHtml(g, st, d) {
    var mk = st.m, sd = st.s || 0, nm = sideNames(g, mk, d.ref)[sd];
    var pin = d.series.filter(function (s) { return s.book === 'Pinnacle'; })[0];
    if (!pin) return '<div class="vlm-sum">No Pinnacle price stored at this line.</div>';
    var a = valueAt(pin, d.tmin) || pin.pts[0], b = pin.pts[pin.pts.length - 1];
    var raw = function (r) { return mk === 'ml' ? r.ml : r[mk].slice(1); }, ends = function (r) { var x = raw(r); return mk === 'ml' ? [x[0], x[1]] : [x[0], x[1]]; };
    var fairOf = function (r) { var x = ends(r); return fairFirst(x[sd], x[1 - sd]) * 100; };
    var pa = yToP(a[1]), pb = yToP(b[1]), o = '<div class="vlm-sum"><b>Pinnacle ' + nm + '</b> ' + (pa === pb ? 'held ' + pb : pa + ' to ' + pb);
    try { var fa = fairOf(a[2]), fb = fairOf(b[2]); if (pa !== pb) o += ' (fair ' + fa.toFixed(1) + '% to ' + fb.toFixed(1) + '%)'; } catch (e) {}
    if (d.lim && d.lim.pts.length) {
      var la = valueAt(d.lim, d.tmin) || d.lim.pts[0], lb = d.lim.pts[d.lim.pts.length - 1];
      o += la[1] === lb[1] ? '. Limit steady at ' + usd(lb[1]) : '. Limit ' + usd(la[1]) + ' to ' + usd(lb[1]);
    }
    return o + '. Only prices at ' + (mk === 'ml' ? 'the moneyline' : 'Pinnacle\u2019s current number (' + d.ref + ')') + ' are drawn.</div>';
  }

  function svg(d, st, W) {
    var H = W < 480 ? 220 : 250, L = 44, R = d.lim && d.lim.on ? 40 : 12, T = 12, B = 26, vis = d.series.filter(function (s) { return s.on; });
    if (!vis.length) return '<div class="vlm-empty">Turn a book on to see its line.</div>';
    var lo = Infinity, hi = -Infinity, PR0 = st.v === 'price';
    vis.forEach(function (s) {
      s.pts.forEach(function (p) { if (p[0] >= d.tmin - 1) { lo = Math.min(lo, p[1]); hi = Math.max(hi, p[1]); } });
      var v0 = valueAt(s, d.tmin); if (v0) { lo = Math.min(lo, v0[1]); hi = Math.max(hi, v0[1]); }
    });
    if (!isFinite(lo)) return '<div class="vlm-empty">' + (PR0 ? 'No prices stored at this line in this window.' : 'No line changes in this window.') + '</div>';
    var PR = st.v === 'price', pad = PR ? 2 : st.m === 'ml' ? 1 : 0.5; lo -= pad; hi += pad;
    if (hi - lo < (PR ? 10 : st.m === 'ml' ? 4 : 2)) { var mid = (hi + lo) / 2, hf = PR ? 5 : st.m === 'ml' ? 2 : 1; lo = mid - hf; hi = mid + hf; }
    var step = PR ? ([1, 2, 5, 10, 20, 50].filter(function (s) { return (hi - lo) / s <= 5; })[0] || 50) : st.m === 'ml' ? ([1, 2, 5, 10].filter(function (s) { return (hi - lo) / s <= 5; })[0] || 10) : ([0.5, 1, 2, 5].filter(function (s) { return (hi - lo) / s <= 5; })[0] || 5);
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
    d.R = R;
    var X = function (t) { return L + (t - d.tmin) / (d.tmax - d.tmin) * (W - L - R); };
    var Y = function (v) { return T + (hi - v) / (hi - lo) * (H - T - B); };
    var o = '<svg class="vlm-svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Line movement by book">';
    for (var v = lo; v <= hi + 1e-9; v += step) {
      o += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(v).toFixed(1) + '" y2="' + Y(v).toFixed(1) + '" class="vlm-grid"/><text x="' + (L - 6) + '" y="' + (Y(v) + 4).toFixed(1) + '" text-anchor="end" class="vlm-ax">' + vlab(v, st) + '</text>';
    }
    var ticks = W < 480 ? 2 : 4;
    for (var i = 0; i <= ticks; i++) {
      var t = d.tmin + (d.tmax - d.tmin) * i / ticks, dt = new Date(t * 1000);
      var lab = (d.tmax - d.tmin) > 36 * 3600 ? dt.toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' }) + (W < 480 ? '' : ' ' + dt.toLocaleTimeString(undefined, { hour: 'numeric' })) : dt.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
      o += '<text x="' + X(t).toFixed(1) + '" y="' + (H - 6) + '" text-anchor="' + (i === 0 ? 'start' : i === ticks ? 'end' : 'middle') + '" class="vlm-ax">' + lab + '</text>';
    }
    if (d.lim && d.lim.on) {
      var lm = 0; d.lim.pts.forEach(function (p) { lm = Math.max(lm, p[1]); });
      var lstep = [1000, 2000, 5000, 10000, 20000, 50000, 100000].filter(function (q) { return lm / q <= 4; })[0] || 100000, lhi = Math.ceil(lm * 1.05 / lstep) * lstep || lstep;
      var YL = function (v) { return T + (lhi - v) / lhi * (H - T - B); };
      [lhi, lhi / 2].forEach(function (v) { o += '<text x="' + (W - R + 5) + '" y="' + (YL(v) + 4).toFixed(1) + '" class="vlm-ax">' + usd(v) + '</text>'; });
      var lv = valueAt(d.lim, d.tmin), lpts = lv ? [[d.tmin, lv[1]]] : [];
      d.lim.pts.forEach(function (p) { if (p[0] > d.tmin && p[0] <= d.tmax) lpts.push([p[0], p[1]]); });
      if (lpts.length) {
        var lpath = 'M' + X(lpts[0][0]).toFixed(1) + ' ' + YL(lpts[0][1]).toFixed(1);
        for (var q = 1; q < lpts.length; q++) lpath += 'H' + X(lpts[q][0]).toFixed(1) + 'V' + YL(lpts[q][1]).toFixed(1);
        o += '<path d="' + lpath + 'H' + X(d.tmax).toFixed(1) + '" fill="none" stroke="currentColor" stroke-width="1.6" opacity=".7"/>';
        o += '<circle cx="' + X(d.tmax).toFixed(1) + '" cy="' + YL(lpts[lpts.length - 1][1]).toFixed(1) + '" r="2.6" fill="currentColor" opacity=".85"/>';
      }
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
    '.vlm-sum{font-size:13px;line-height:1.45;margin:0 0 10px;font-variant-numeric:tabular-nums}.vlm-sum b{font-weight:700}' +
    '.vlm-edge{margin-top:14px;padding-top:12px;border-top:1px solid rgba(127,127,127,.25)}.vlm-eh{display:flex;justify-content:space-between;font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.6;margin-bottom:8px}.vlm-er{display:grid;grid-template-columns:1fr auto;gap:2px 12px;padding:8px 0;border-top:1px solid rgba(127,127,127,.15)}.vlm-er:first-of-type{border-top:0}.vlm-em{font-size:13.5px}.vlm-ev{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums;text-align:right}.vlm-ev.pos{color:#34c759}.vlm-ev.neg{opacity:.6}.vlm-ed{grid-column:1/-1;font-size:12px;opacity:.72;font-variant-numeric:tabular-nums;line-height:1.45}.vlm-rec{margin-top:12px;padding-top:10px;border-top:1px solid rgba(127,127,127,.15)}.vlm-rr{display:flex;justify-content:space-between;gap:12px;font-size:12px;padding:4px 0;font-variant-numeric:tabular-nums}.vlm-rr span:last-child{text-align:right;opacity:.8}.vlm-hint{font:inherit;font-size:12px;font-weight:600;padding:6px 10px;margin:0 6px 6px 0;border-radius:999px;border:1.5px solid #ff9f43;background:transparent;color:inherit;cursor:pointer}.vlm-empty{padding:18px 4px;font-size:13px;opacity:.65}.vlm-note{margin-top:8px;font-size:11.5px;opacity:.55}';
  function css() { if (!document.getElementById('vlm-css')) { var s = document.createElement('style'); s.id = 'vlm-css'; s.textContent = CSS; document.head.appendChild(s); } }

  function html(g, st, d, W) {
    var mk = st.m, o = '<div class="vlm"><div class="vlm-tabs"><div class="vlm-seg" data-vlm-k="m">';
    MARKETS.forEach(function (m) { o += '<button type="button" data-v="' + m[0] + '" class="' + (m[0] === mk ? 'on' : '') + '">' + m[1] + '</button>'; });
    o += '</div><div class="vlm-seg" data-vlm-k="w">';
    WINDOWS.forEach(function (w) { o += '<button type="button" data-v="' + w[1] + '" class="' + (w[1] === st.w ? 'on' : '') + '">' + w[0] + '</button>'; });
    o += '</div></div><div class="vlm-tabs"><div class="vlm-seg" data-vlm-k="v">';
    [['line', 'Line'], ['price', 'Price']].forEach(function (m) { o += '<button type="button" data-v="' + m[0] + '" class="' + ((st.v || 'line') === m[0] ? 'on' : '') + '">' + m[1] + '</button>'; });
    o += '</div>';
    if (d.pm) {
      o += '<div class="vlm-seg" data-vlm-k="s">';
      sideNames(g, mk, d.ref).forEach(function (n, i) { o += '<button type="button" data-v="' + i + '" class="' + (i === (st.s || 0) ? 'on' : '') + '">' + n + '</button>'; });
      o += '</div>';
    }
    o += '</div>' + (d.pm ? moveHtml(g, st, d) : '') + svg(d, st, W) + '<div class="vlm-read" aria-live="off"></div><div class="vlm-legend">';
    d.series.forEach(function (s) {
      var last = s.pts[s.pts.length - 1];
      o += '<button type="button" class="vlm-chip' + (s.on ? '' : ' off') + '" style="--c:' + s.color + '" data-b="' + s.book + '" aria-pressed="' + s.on + '">' + s.book + ' <i>' + vlab(last[1], st) + '</i></button>';
    });
    if (d.lim) {
      var ll = d.lim.pts[d.lim.pts.length - 1];
      o += '<button type="button" class="vlm-chip' + (d.lim.on ? '' : ' off') + '" style="--c:currentColor" data-b="Pinnacle limits" aria-pressed="' + d.lim.on + '">Pinnacle limit <i>' + usd(ll[1]) + '</i></button>';
    }
    var hasEx = d.rows.some(function (r) { return r.book === 'Novig' || r.book === 'Kalshi'; }), hasTr = d.rows.some(function (r) { return r.tr; });
    var homeAbbr = g.home && g.home.abbr;
    return o + '</div><div class="vlm-note">' + (mk === 'sp' ? homeAbbr + ' spread. ' : mk === 'ml' ? homeAbbr + ' win chance from each book’s moneyline, vig removed. Novig and Kalshi show the middle of their best bid and ask, when the two are within 10 points. ' : '') +
      (mk !== 'ml' && hasEx ? '<button type="button" class="vlm-hint" data-ml="1">Novig and Kalshi quote a win chance, not a line. See them on Money</button> ' : '') + (mk === 'ml' && hasTr ? 'Novig before recording began is its traded price. ' : '') + (d.lim ? 'The white line is the most Pinnacle will take on this market, on the right axis. ' : '') + 'Steps are when a book changed its line. Context only, not a bet signal.</div>' + edgeHtml(g, d, st.w) + '</div>';
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
      if (x < 44 || x > W - d.R) return;
      var t = d.tmin + (x - 44) / (W - 44 - d.R) * (d.tmax - d.tmin);
      cur.setAttribute('x1', x); cur.setAttribute('x2', x); cur.style.display = '';
      var dt = new Date(t * 1000), parts = [dt.toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })];
      d.series.forEach(function (s) {
        if (!s.on || s.book === 'Open') return;
        var p = valueAt(s, t); if (p) parts.push(s.book + ' ' + (st.v === 'price' ? vlab(p[1], st) : st.m === 'ml' ? fmtMl(p[2]) : fmt(p[1], st.m)));
      });
      if (d.lim && d.lim.on) { var lq = valueAt(d.lim, t); if (lq) parts.push('Limit ' + usd(lq[1])); }
      rd.textContent = parts.join('  ·  ');
    };
    sv.addEventListener('pointermove', move); sv.addEventListener('pointerdown', move);
    sv.addEventListener('pointerleave', function () { cur.style.display = 'none'; rd.textContent = ''; });
  }
  function fmtMl(r) { return r && r.bf && r.mlp != null ? (r.mlp * 100).toFixed(1) + '%' : r && r.px ? Math.round(r.px[0] * 100) + '-' + Math.round(r.px[1] * 100) + '\u00A2' : r && r.ml ? am(r.ml[0]) + '/' + am(r.ml[1]) : ''; }

  function mount(el, g) {
    if (!el || !g || !/^(nfl|cfb|nba)$/.test(g.sport)) return;
    css(); hosts.set(el, g);
    if (g.tab && !el.__vlmTab) { el.__vlmTab = 1; (states[g.key] || (states[g.key] = { m: 'sp', w: 24 * 3600, hide: {} })).m = g.tab; }   // the Edge page opens the chart on the market of the row
    if (!el.__vlm) {
      el.__vlm = 1;
      el.addEventListener('click', function (e) {
        var b = e.target.closest('button'); if (!b) return;
        var gg = hosts.get(el), st = states[gg.key]; if (!st) return;
        var seg = b.parentNode && b.parentNode.getAttribute('data-vlm-k');
        if (seg === 'm') st.m = b.getAttribute('data-v');
        else if (seg === 'v') st.v = b.getAttribute('data-v');
        else if (seg === 's') st.s = +b.getAttribute('data-v');
        else if (seg === 'w') st.w = +b.getAttribute('data-v');
        else if (b.hasAttribute('data-ml')) st.m = 'ml';
        else if (b.hasAttribute('data-b')) { var k = b.getAttribute('data-b'), on = !b.classList.contains('off'); st.hide[k] = on; }
        else return;
        render(el, gg);
      });
    }
    if (tapes[g.sport]) render(el, g);
    else { el.innerHTML = '<div class="vlm-empty">Loading line history…</div>'; load(g.sport).then(function () { if (hosts.get(el) === g) render(el, g); }); }
  }
  function scan(root, lookup) {
    (root || document).querySelectorAll('[data-vlm-key]').forEach(function (el) { mount(el, lookup(el.getAttribute('data-vlm-key'))); });
  }
  window.VaultLineChart = { mount: mount, scan: scan, load: load };
})();
