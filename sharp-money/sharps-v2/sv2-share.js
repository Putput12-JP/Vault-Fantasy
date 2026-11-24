/* Sharps V2: "Share this play as an image". Owned by the Sharps page agent.
   What this file is: a poster drawn by hand on a 2D canvas (no library, no external script, no external font or image, no team logos) from a plain data
   object, plus the share or download step. The data object is built by sv2-sharps.js (shareDataOf) from the same stored values and helper functions the
   play write-up card uses, so the image says nothing the card does not say. Nothing here reads storage, the wallet list or any user data.

   Pure parts (tested in node with no canvas): fileName, wrap, buildOps (data + a text measuring function -> a list of draw operations), draw (ops -> any
   2D context), deliver (blob + stubbed navigator and document -> share, download or a status line), pageUrl, contrast.
   Browser part: run (builds the canvas, draws, makes the PNG, delivers it). It never throws: every failure is a status line.

   The poster is always dark (the V2 glass look) whatever the site theme: 1080 x 1350 (4:5) at a device pixel ratio of 1. Colour is never the only carrier:
   the tier shows its word and pips, the move label its word and bars. Context only: the image carries the card's own disclaimers and no prediction.
   No em dashes. All times Central. */
(function () {
  'use strict';
  var SV2 = (typeof window !== 'undefined' && window.SV2) || null;
  if (!SV2) return;

  var W = 1080, H = 1350, M = 72, MT = 60, MB = 50, CW = W - 2 * M, GAP = 16;
  var SANS = "Geist, -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif";
  var NUM = "'Geist Mono', 'SF Mono', ui-monospace, Menlo, Consolas, monospace";

  /* the poster's fixed palette; TEXT_ON lists the surfaces each text colour can sit on (checked at 4.5:1 or better in the tests) */
  var PAL = {
    bg0: '#181818', bg1: '#0F0F0F', panel: '#242424', ring: 'rgba(255,255,255,0.16)', line: '#3A3A3A',
    ink: '#F2F2F2', mut: '#BEBEBE', faint: '#AEAEAE',
    gold: '#F5C542', teal: '#2DD4BF', slate: '#B4BCC8', violet: '#A78BFA', dateBg: '#E8C66A', dateInk: '#161616'
  };
  var TIER_COL = { clear: PAL.gold, mixed: PAL.teal, thin: PAL.slate, contested: PAL.violet };
  var TEXT_ON = { ink: ['bg0', 'bg1', 'panel'], mut: ['bg0', 'bg1', 'panel'], faint: ['bg0', 'bg1', 'panel'], dateInk: ['dateBg'] };

  /* ------------------------------------------------------------------ small pure helpers */
  function hexRgb(h) { var n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  function lum(h) {
    var c = hexRgb(h).map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function contrast(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }

  /* a drawn string: a real string only, no stray placeholder, no em or en dash. Anything else draws nothing (a missing field omits its line). */
  var DASHES = new RegExp('[' + String.fromCharCode(0x2013, 0x2014) + ']', 'g');   /* en and em dash: never drawn */
  function S(x) {
    if (typeof x !== 'string') return '';
    var s = x.replace(DASHES, '-').replace(/\s+/g, ' ').replace(/^ | $/g, '');
    return /\b(undefined|NaN)\b|\bnull\b|\[object/.test(s) ? '' : s;
  }
  function slug(s) { return String(s || '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''); }
  /* sharp-money-<sport>-<play>.png, never empty, never long */
  function fileName(sport, title) {
    var s = slug(String(sport || '') + ' ' + String(title || '')).slice(0, 60).replace(/-+$/g, '');
    return 'sharp-money-' + (s || 'play') + '.png';
  }
  /* host and path of the page, no query, no hash, no index.html; nothing for a non-web address. Takes a location-like object. */
  function pageUrl(loc) {
    if (!loc || !/^https?:$/.test(String(loc.protocol || ''))) return '';
    var host = String(loc.host || ''), path = String(loc.pathname || '/').replace(/index\.html$/, '').replace(/sharps-v2\/?$/, '');
    if (!host) return '';
    return (host + path).replace(/\/+$/, '');
  }

  /* greedy word wrap. measure(font, text) -> width. A word wider than the box is broken by character; lines never exceed maxW. */
  function wrap(measure, font, text, maxW) {
    var words = S(text).split(' ').filter(Boolean), lines = [], cur = '';
    function push() { if (cur) lines.push(cur); cur = ''; }
    words.forEach(function (w) {
      var t = cur ? cur + ' ' + w : w;
      if (measure(font, t) <= maxW) { cur = t; return; }
      push();
      if (measure(font, w) <= maxW) { cur = w; return; }
      var piece = '';
      for (var i = 0; i < w.length; i++) {
        if (measure(font, piece + w[i]) > maxW && piece) { lines.push(piece); piece = ''; }
        piece += w[i];
      }
      cur = piece;
    });
    push();
    return lines;
  }
  /* at most n lines; a longer text ends its last line with three periods, trimmed to fit */
  function clamp(measure, font, lines, n, maxW) {
    if (lines.length <= n) return lines;
    var out = lines.slice(0, n), last = out[n - 1] + '...';
    while (last.length > 4 && measure(font, last) > maxW) last = last.slice(0, -4) + '...';
    out[n - 1] = last;
    return out;
  }

  /* ------------------------------------------------------------------ layout: data -> draw operations */
  /* data: see shareDataOf in sv2-sharps.js. measure(font, text) -> width in canvas pixels. Returns { ops, height, used, dropped }. */
  function buildOps(data, measure) {
    var d = data || {};
    var f = function (weight, size, fam) { return weight + ' ' + size + 'px ' + (fam || SANS); };
    function lines(text, font, w) { return wrap(measure, font, text, w); }

    function txt(ops, x, y, s, font, fill, align) { if (s) ops.push({ t: 'text', x: x, y: y, s: s, font: font, fill: fill, align: align || 'left' }); }
    /* wrapped lines from top y with line height lh; returns the next y */
    function para(ops, x, y, arr, font, size, fill, lh) {
      arr.forEach(function (s, i) { txt(ops, x, y + Math.round(size * 0.82) + i * lh, s, font, fill); });
      return y + arr.length * lh;
    }

    /* ---- header: brand mark text, date chip, eyebrow */
    function header() {
      var date = S(d.date), brand = S(d.brand) || 'Sharp Money', eyebrow = [S(d.eyebrow) || 'Play breakdown', S(d.sport)].filter(Boolean).join(' · ').toUpperCase();
      return {
        h: 84,
        draw: function (ops, y) {
          txt(ops, M, y + 36, brand.toUpperCase(), f(700, 32), PAL.ink);
          if (date) {
            var fo = f(700, 24), w = Math.ceil(measure(fo, date)) + 40;
            ops.push({ t: 'rect', x: W - M - w, y: y + 1, w: w, h: 50, r: 25, fill: PAL.dateBg });
            txt(ops, W - M - w + 20, y + 34, date, fo, PAL.dateInk);
          }
          txt(ops, M, y + 76, eyebrow, f(600, 22), PAL.mut);
        }
      };
    }

    /* ---- title and the game line */
    function title() {
      /* one line when it fits at 54px or larger, else the largest size that fits on two, else three lines at 44px */
      var t = S(d.title), size = 66, fo, L = [], sizes = [66, 60, 54, 48, 44], i;
      for (i = 0; i < 3; i++) { size = sizes[i]; fo = f(700, size); L = lines(t, fo, CW); if (L.length <= 1) break; }
      if (L.length > 1) for (i = 0; i < sizes.length; i++) { size = sizes[i]; fo = f(700, size); L = lines(t, fo, CW); if (L.length <= 2) break; }
      L = clamp(measure, fo, L, 3, CW);
      var lh = Math.round(size * 1.14);
      var sub = [S(d.game), S(d.market)].filter(Boolean).join(', '), sf = f(500, 30), SL = clamp(measure, sf, lines(sub, sf, CW), 2, CW);
      return {
        h: L.length * lh + (SL.length ? 8 + SL.length * 38 : 0),
        draw: function (ops, y) {
          var yy = para(ops, M, y, L, fo, size, PAL.ink, lh);
          if (SL.length) para(ops, M, yy + 8, SL, sf, 30, PAL.mut, 38);
        }
      };
    }

    /* ---- chips: tier (word and pips, tier colour), move label (word and bars, neutral) */
    function chips() {
      var items = [], tr = d.tier && S(d.tier.word) ? d.tier : null, mv = d.move && S(d.move.word) ? d.move : null;
      if (tr) {
        var tf = f(700, 28), tw = Math.ceil(measure(tf, S(tr.word)));
        items.push({ w: 22 + 3 * 22 + 4 + tw + 26, kind: 'tier', fo: tf, word: S(tr.word), key: tr.key, pips: Math.max(0, Math.min(3, tr.pips | 0)) });
      }
      if (mv) {
        var mf = f(700, 28), kf = f(600, 22), against = mv.key === 'against', kw = against ? 0 : Math.ceil(measure(kf, 'MOVE')) + 14, bw = against ? 0 : 3 * 12 + 10;
        items.push({ w: 24 + kw + bw + Math.ceil(measure(mf, S(mv.word))) + 26, kind: 'move', fo: mf, kf: kf, word: S(mv.word), bars: Math.max(0, Math.min(3, mv.bars | 0)), against: against });
      }
      if (!items.length) return { h: 0, draw: function () {} };
      var rows = [[]], x = 0;
      items.forEach(function (it) { if (x && x + it.w > CW) { rows.push([]); x = 0; } rows[rows.length - 1].push(it); x += it.w + 14; });
      return {
        h: rows.length * 56 + (rows.length - 1) * 12,
        draw: function (ops, y) {
          rows.forEach(function (row, ri) {
            var cx = M, cy = y + ri * 68;
            row.forEach(function (it) {
              if (it.kind === 'tier') {
                var col = TIER_COL[it.key] || PAL.slate;
                ops.push({ t: 'rect', x: cx, y: cy, w: it.w, h: 56, r: 28, fill: PAL.panel, stroke: col, lw: 2.5 });
                for (var i = 0; i < 3; i++) ops.push({ t: 'circle', x: cx + 30 + i * 22, y: cy + 28, r: 7, fill: i < it.pips ? col : null, stroke: col, lw: 2 });
                txt(ops, cx + 22 + 3 * 22 + 4, cy + 38, it.word, it.fo, PAL.ink);
              } else {
                ops.push({ t: 'rect', x: cx, y: cy, w: it.w, h: 56, r: 28, fill: PAL.panel, stroke: PAL.ring, lw: 2 });
                var tx = cx + 24;
                if (!it.against) {
                  txt(ops, tx, cy + 36, 'MOVE', it.kf, PAL.mut); tx += Math.ceil(measure(it.kf, 'MOVE')) + 14;
                  for (var b = 0; b < 3; b++) { var bh = 8 + b * 5; ops.push({ t: 'rect', x: tx + b * 12, y: cy + 38 - bh, w: 7, h: bh, r: 2, fill: b < it.bars ? PAL.ink : null, stroke: PAL.ink, lw: 1.5 }); }
                  tx += 3 * 12 + 10;
                }
                txt(ops, tx, cy + 38, it.word, it.fo, PAL.ink);
              }
              cx += it.w + 14;
            });
          });
        }
      };
    }

    /* ---- tiles: price, line and fair, freeze and size. A tile with nothing to say is left out and the rest widen. */
    function tiles() {
      var T = [], p = d.price || {}, fr = d.fair || {}, st = d.status || {};
      var priceSubs = [S(p.american), S(p.best)].filter(Boolean);   /* the Novig price is drawn in the line section, beside its sentence */
      if (S(p.cents) || priceSubs.length) T.push({ label: 'PRICE', value: S(p.cents), subs: priceSubs });
      if (S(fr.value) || S(fr.sub)) T.push({ label: 'LINE AND FAIR', value: S(fr.value), subs: [S(fr.sub)].filter(Boolean) });
      if (S(st.value) || S(st.size)) T.push({ label: S(st.label).toUpperCase() || 'STATUS', value: S(st.value), subs: [S(st.sub), S(st.size)].filter(Boolean) });
      if (!T.length) return { h: 0, draw: function () {} };
      var g = 16, pad = 22, share = { 1: [1], 2: [0.5, 0.5], 3: [0.37, 0.35, 0.28] }[T.length], avail = CW - g * (T.length - 1);
      T.forEach(function (t, i) { t.w = Math.floor(avail * share[i]); });
      T.forEach(function (t) {
        var iw = t.w - 2 * pad, vs = 36, vf;
        for (; vs >= 28; vs -= 2) { vf = f(700, vs, NUM); if (!t.value || measure(vf, t.value) <= iw) break; }
        t.vf = vf; t.vs = vs; t.vl = t.value ? clamp(measure, vf, lines(t.value, vf, iw), 2, iw) : [];
        t.sf = f(400, 22);
        t.sl = t.subs.map(function (s) { return clamp(measure, t.sf, lines(s, t.sf, iw), 2, iw); });
        t.h = 18 + 22 + 8 + t.vl.length * Math.round(t.vs * 1.15) + (t.sl.length ? 8 : 0) + t.sl.reduce(function (a, l) { return a + l.length * 28 + 4; }, 0) + 14;
      });
      var h = Math.max.apply(null, T.map(function (t) { return t.h; }));
      return {
        h: h,
        draw: function (ops, y) {
          var x = M;
          T.forEach(function (t) {
            ops.push({ t: 'rect', x: x, y: y, w: t.w, h: h, r: 22, fill: PAL.panel, stroke: PAL.ring, lw: 1.5 });
            var yy = y + 18;
            txt(ops, x + pad, yy + 18, t.label, f(600, 20), PAL.mut);
            yy += 22 + 8;
            yy = para(ops, x + pad, yy, t.vl, t.vf, t.vs, PAL.ink, Math.round(t.vs * 1.15));
            if (t.sl.length) yy += 8;
            t.sl.forEach(function (l) { yy = para(ops, x + pad, yy, l, t.sf, 22, PAL.mut, 28) + 4; });
            x += t.w + g;
          });
        }
      };
    }

    /* ---- where the line went: the move sentence, Pinnacle's price and the market line from and to, the flag facts, the Novig lines (fresh quote only: the data has none otherwise) */
    function market(o) {
      var mk = d.moves || {}, pr = d.price || {};
      var say = S(mk.say), flags = o.flags ? (mk.flags || []).map(S).filter(Boolean) : [], novig = [S(pr.novig), S(mk.novig)].filter(Boolean);
      var nums = !o.nums ? [] : [mk.pin, mk.line].filter(function (n) { return n && S(n.label) && S(n.from) && S(n.to); });
      if (!say && !nums.length && !flags.length && !novig.length) return null;
      var sf = f(500, 25), lf = f(600, 20), nf = f(700, 38, NUM), ff = f(500, 24), LH = 32;
      var SL = say ? clamp(measure, sf, lines(say, sf, CW), 2, CW) : [];
      var colW = nums.length === 2 ? Math.floor((CW - 20) / 2) : CW;
      var NL = nums.map(function (n) { return clamp(measure, lf, lines(S(n.label).toUpperCase(), lf, colW - 8), 2, colW - 8); });
      var nlh = nums.length ? Math.max.apply(null, NL.map(function (l) { return l.length; })) * 24 : 0;
      var FL = flags.map(function (s) { return clamp(measure, ff, lines(s, ff, CW - 34), 2, CW - 34); });
      var NV = novig.map(function (s) { return clamp(measure, ff, lines(s, ff, CW - 34), 3, CW - 34); });
      var rowsH = function (a) { return a.reduce(function (n, l) { return n + l.length * LH + 4; }, 0); };
      var h = 14 + 20 + 8 + (SL.length ? SL.length * 34 + 10 : 8) + (nums.length ? nlh + 4 + 46 + 8 : 0) + rowsH(FL) + rowsH(NV);
      return {
        h: h,
        draw: function (ops, y) {
          ops.push({ t: 'line', x1: M, y1: y, x2: W - M, y2: y, stroke: PAL.line, lw: 1.5 });
          var yy = y + 14;
          txt(ops, M, yy + 17, 'WHERE THE LINE WENT', f(600, 20), PAL.mut); yy += 20 + 8;
          if (SL.length) yy = para(ops, M, yy, SL, sf, 25, PAL.ink, 34) + 10; else yy += 8;
          if (nums.length) {
            nums.forEach(function (n, i) {
              var x = M + i * (colW + 20);
              para(ops, x, yy, NL[i], lf, 20, PAL.mut, 24);
              var by = yy + nlh + 4 + 36, a = S(n.from), b = S(n.to), ax = x + Math.ceil(measure(nf, a)) + 14;
              txt(ops, x, by, a, nf, PAL.ink);
              ops.push({ t: 'line', x1: ax, y1: by - 13, x2: ax + 32, y2: by - 13, stroke: PAL.mut, lw: 3 });
              ops.push({ t: 'line', x1: ax + 22, y1: by - 22, x2: ax + 32, y2: by - 13, stroke: PAL.mut, lw: 3 });
              ops.push({ t: 'line', x1: ax + 22, y1: by - 4, x2: ax + 32, y2: by - 13, stroke: PAL.mut, lw: 3 });
              txt(ops, ax + 32 + 14, by, b, nf, PAL.ink);
            });
            yy += nlh + 4 + 46 + 8;
          }
          FL.forEach(function (l) {
            ops.push({ t: 'circle', x: M + 8, y: yy + 14, r: 5, fill: PAL.mut });
            yy = para(ops, M + 34, yy, l, ff, 24, PAL.ink, LH) + 4;
          });
          NV.forEach(function (l) {
            ops.push({ t: 'circle', x: M + 8, y: yy + 14, r: 5, fill: null, stroke: PAL.mut, lw: 2 });
            yy = para(ops, M + 34, yy, l, ff, 24, PAL.ink, LH) + 4;
          });
        }
      };
    }

    /* ---- who is on each side: a small table, one column per side; the heavier side carries a small outlined tag */
    function money() {
      var mo = d.money;
      if (!mo || !Array.isArray(mo.names) || mo.names.length !== 2 || !Array.isArray(mo.rows) || !mo.rows.length) return null;
      var labW = 350, colW = Math.floor((CW - labW) / 2), iw = colW - 16, nf = f(700, 26), cf = f(600, 22), lf = f(400, 21), tf = f(600, 15);
      var tagW = Math.ceil(measure(tf, 'MORE MONEY')) + 18;
      /* the tag sits beside the name when it fits on the name's last line, else on a line of its own: a name is never cut to make room for it */
      var NM = mo.names.map(function (n) { return clamp(measure, nf, lines(S(n), nf, iw), 2, iw); });
      var inline = mo.more === 0 || mo.more === 1 ? Math.ceil(measure(nf, NM[mo.more][NM[mo.more].length - 1])) + 10 + tagW <= iw : false;
      var nmH = Math.max(NM[0].length, NM[1].length) * 32 + ((mo.more === 0 || mo.more === 1) && !inline ? 30 : 0);
      var rows = mo.rows.map(function (r) {
        var cells = (r.cells || []).slice(0, 2).map(function (c) { return clamp(measure, cf, lines(S(c) || 'None stored', cf, iw), 2, iw); });
        while (cells.length < 2) cells.push(['None stored']);
        var ll = clamp(measure, lf, lines(S(r.label), lf, labW - 16), 2, labW - 16);
        return { ll: ll, cells: cells, h: Math.max(cells[0].length, cells[1].length, ll.length) * 28 + 8 };
      }).filter(function (r) { return r.ll.length; });
      if (!rows.length) return null;
      var h = 16 + nmH + 8 + rows.reduce(function (a, r) { return a + r.h; }, 0);
      return {
        h: h,
        draw: function (ops, y) {
          ops.push({ t: 'line', x1: M, y1: y, x2: W - M, y2: y, stroke: PAL.line, lw: 1.5 });
          var yy = y + 16;
          txt(ops, M, yy + 24, 'WHO IS ON EACH SIDE', f(600, 20), PAL.mut);
          NM.forEach(function (l, i) {
            var x = M + labW + i * colW;
            para(ops, x, yy, l, nf, 26, PAL.ink, 32);
            if (mo.more === i) {
              var tx = inline ? x + Math.ceil(measure(nf, l[l.length - 1])) + 10 : x, ty = inline ? yy + (l.length - 1) * 32 + 4 : yy + l.length * 32 + 2;
              ops.push({ t: 'rect', x: tx, y: ty, w: tagW, h: 24, r: 12, fill: null, stroke: PAL.ink, lw: 1.5 });
              txt(ops, tx + 9, ty + 17, 'MORE MONEY', tf, PAL.ink);
            }
          });
          yy += nmH + 8;
          rows.forEach(function (r) {
            ops.push({ t: 'line', x1: M, y1: yy, x2: W - M, y2: yy, stroke: PAL.line, lw: 1 });
            para(ops, M, yy + 5, r.ll, lf, 21, PAL.mut, 28);
            r.cells.forEach(function (c, i) { para(ops, M + labW + i * colW, yy + 5, c, cf, 22, PAL.ink, 28); });
            yy += r.h;
          });
        }
      };
    }

    /* ---- footer: the disclaimer (visible size), the source line, the read time and the page address. Always drawn, at the bottom of the poster. */
    function footer() {
      var ft = d.footer || {};
      var cf = f(700, 32), sf = f(400, 22), CL = clamp(measure, cf, lines(S(ft.context) || 'Context only. Not a bet signal.', cf, CW), 2, CW);
      var SLn = [S(ft.source)].concat((ft.notes || []).map(S)).filter(Boolean).map(function (s) { return clamp(measure, sf, lines(s, sf, CW), 3, CW); });
      var left = S(ft.read), right = S(ft.url);
      var stack = !!(left && right && measure(sf, left) + measure(sf, right) + 30 > CW);
      var bottomRows = (left || right) ? (stack ? 2 : 1) : 0;
      var h = 16 + CL.length * 40 + 8 + SLn.reduce(function (a, l) { return a + l.length * 28 + 4; }, 0) + (bottomRows ? 6 + bottomRows * 28 : 0);
      return {
        h: h,
        draw: function (ops, y) {
          ops.push({ t: 'line', x1: M, y1: y, x2: W - M, y2: y, stroke: PAL.line, lw: 1.5 });
          var yy = y + 16;
          yy = para(ops, M, yy, CL, cf, 32, PAL.ink, 40) + 8;
          SLn.forEach(function (l) { yy = para(ops, M, yy, l, sf, 22, PAL.faint, 28) + 4; });
          if (bottomRows) {
            yy += 6;
            if (stack) { txt(ops, M, yy + 21, left, sf, PAL.mut); txt(ops, M, yy + 49, right, sf, PAL.mut); }
            else { txt(ops, M, yy + 21, left, sf, PAL.mut); txt(ops, W - M, yy + 21, right, sf, PAL.mut, 'right'); }
          }
        }
      };
    }

    /* ---- put the blocks in order; when they do not fit, leave out the lowest ones first (money, then the flag sentences, then the whole line section) */
    var avail = H - MT - MB, blocks = null, dropped = [], si;
    var steps = [{ nums: true, money: true, flags: true, market: true }, { nums: false, money: true, flags: true, market: true }, { nums: true, money: false, flags: true, market: true }, { nums: false, money: false, flags: true, market: true },
      { nums: false, money: false, flags: false, market: true }, { nums: false, money: false, flags: false, market: false }];
    for (si = 0; si < steps.length; si++) {
      var st = steps[si], list = [header(), title(), chips(), tiles()];
      var mkt = st.market ? market(st) : null, mon = st.money ? money() : null;
      if (mkt) list.push(mkt);
      if (mon) list.push(mon);
      var foot = footer();
      list = list.filter(function (b) { return b.h > 0; });
      var total = list.reduce(function (a, b) { return a + b.h; }, 0) + foot.h + GAP * list.length;
      blocks = { list: list, foot: foot, total: total };
      dropped = ['nums', 'money', 'flags', 'market'].filter(function (k) { return !st[k]; });
      if (total <= avail) break;
    }
    var ops = [{ t: 'bg' }], y = MT;
    blocks.list.forEach(function (b) { b.draw(ops, y); y += b.h + GAP; });
    blocks.foot.draw(ops, Math.max(y, H - MB - blocks.foot.h));
    return { ops: ops, height: H, used: blocks.total, dropped: dropped, sizes: blocks.list.map(function (b) { return b.h; }).concat([blocks.foot.h]) };
  }

  /* ------------------------------------------------------------------ draw: operations -> a 2D context */
  function rrect(c, x, y, w, h, r) {
    c.beginPath();
    c.moveTo(x + r, y); c.lineTo(x + w - r, y); c.arcTo(x + w, y, x + w, y + r, r); c.lineTo(x + w, y + h - r); c.arcTo(x + w, y + h, x + w - r, y + h, r);
    c.lineTo(x + r, y + h); c.arcTo(x, y + h, x, y + h - r, r); c.lineTo(x, y + r); c.arcTo(x, y, x + r, y, r); c.closePath();
  }
  function draw(c, ops) {
    ops.forEach(function (o) {
      if (o.t === 'bg') {
        var g = c.createLinearGradient(0, 0, 0, H); g.addColorStop(0, PAL.bg0); g.addColorStop(1, PAL.bg1);
        c.fillStyle = g; c.fillRect(0, 0, W, H);
        var rg = c.createRadialGradient(W - 140, 120, 10, W - 140, 120, 560);
        rg.addColorStop(0, 'rgba(245,197,66,0.10)'); rg.addColorStop(1, 'rgba(245,197,66,0)');
        c.fillStyle = rg; c.fillRect(0, 0, W, H);
      } else if (o.t === 'rect') {
        rrect(c, o.x, o.y, o.w, o.h, o.r || 0);
        if (o.fill) { c.fillStyle = o.fill; c.fill(); }
        if (o.stroke) { c.strokeStyle = o.stroke; c.lineWidth = o.lw || 1; c.stroke(); }
      } else if (o.t === 'circle') {
        c.beginPath(); c.arc(o.x, o.y, o.r, 0, Math.PI * 2);
        if (o.fill) { c.fillStyle = o.fill; c.fill(); }
        if (o.stroke) { c.strokeStyle = o.stroke; c.lineWidth = o.lw || 1; c.stroke(); }
      } else if (o.t === 'line') {
        c.beginPath(); c.moveTo(o.x1, o.y1); c.lineTo(o.x2, o.y2); c.strokeStyle = o.stroke; c.lineWidth = o.lw || 1; c.lineCap = 'round'; c.stroke();
      } else if (o.t === 'text') {
        c.font = o.font; c.fillStyle = o.fill; c.textAlign = o.align || 'left'; c.textBaseline = 'alphabetic'; c.fillText(o.s, o.x, o.y);
      }
    });
  }

  /* ------------------------------------------------------------------ share or download */
  var MSG = {
    saved: function (name) { return 'Saved ' + name; },
    shared: 'Shared the image.',
    noCanvas: 'This browser cannot make the image.',
    failed: 'Could not make the image.',
    blocked: 'Could not save the image. Your browser blocked the download.'
  };
  /* blob + file name + env { navigator, document, URL, File, setTimeout } -> Promise of { how, msg }.
     how: 'shared' (the share sheet took it), 'cancelled' (the person closed it: no message), 'downloaded', 'failed'. Never rejects. */
  function deliver(blob, name, env) {
    env = env || {};
    return new Promise(function (resolve) {
      function done(how, msg) { resolve({ how: how, msg: msg || '' }); }
      if (!blob) { done('failed', MSG.failed); return; }
      function download() {
        try {
          var URLc = env.URL, doc = env.document;
          if (!URLc || typeof URLc.createObjectURL !== 'function' || !doc || typeof doc.createElement !== 'function') { done('failed', MSG.blocked); return; }
          var url = URLc.createObjectURL(blob), a = doc.createElement('a');
          a.href = url; a.download = name; a.rel = 'noopener';
          if (a.style) a.style.display = 'none';
          if (doc.body && doc.body.appendChild) doc.body.appendChild(a);
          a.click();
          if (a.remove) a.remove();
          (env.setTimeout || setTimeout)(function () { try { URLc.revokeObjectURL(url); } catch (e) {} }, 4000);
          done('downloaded', MSG.saved(name));
        } catch (e) { done('failed', MSG.blocked); }
      }
      var nav = env.navigator, file = null, can = false;
      try {
        if (nav && typeof nav.share === 'function' && typeof nav.canShare === 'function' && env.File) {
          file = new env.File([blob], name, { type: 'image/png' });
          can = !!nav.canShare({ files: [file] });
        }
      } catch (e) { can = false; }
      if (!can) { download(); return; }
      var p;
      try { p = nav.share({ files: [file], title: 'Sharp Money' }); } catch (e) { p = Promise.reject(e); }
      Promise.resolve(p).then(function () { done('shared', MSG.shared); }, function (e) {
        if (e && e.name === 'AbortError') done('cancelled', '');   /* the person closed the share sheet: say nothing */
        else download();                                           /* the browser refused (for example the tap was too long ago): save it instead */
      });
    });
  }

  function dataUrlToBlob(u) {
    var m = /^data:([^;,]+);base64,(.*)$/.exec(u || ''); if (!m) return null;
    var bin = atob(m[2]), a = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
    return new Blob([a], { type: m[1] });
  }
  function toBlob(canvas) {
    return new Promise(function (resolve) {
      try {
        if (typeof canvas.toBlob === 'function') { canvas.toBlob(function (b) { resolve(b || null); }, 'image/png'); return; }
        resolve(typeof canvas.toDataURL === 'function' ? dataUrlToBlob(canvas.toDataURL('image/png')) : null);
      } catch (e) { resolve(null); }
    });
  }
  /* wait for the page's own fonts (already requested by the page, nothing new is fetched), but never more than 600 ms */
  function fontsReady() {
    try {
      if (!document.fonts || !document.fonts.load) return Promise.resolve();
      return Promise.race([
        Promise.all([document.fonts.load('700 32px Geist'), document.fonts.load('500 24px Geist'), document.fonts.load("700 36px 'Geist Mono'")]).catch(function () {}),
        new Promise(function (r) { setTimeout(r, 600); })
      ]);
    } catch (e) { return Promise.resolve(); }
  }

  /* the browser wrapper. hooks.status(text) is called with a line to show and announce (not for a cancelled share). Always resolves. */
  function run(data, hooks) {
    hooks = hooks || {};
    function say(m) { try { if (m && hooks.status) hooks.status(m); } catch (e) {} }
    return fontsReady().then(function () {
      var canvas, c;
      try {
        canvas = document.createElement('canvas'); canvas.width = W; canvas.height = H;
        c = canvas.getContext && canvas.getContext('2d');
      } catch (e) { c = null; }
      if (!c) { say(MSG.noCanvas); return { how: 'failed', msg: MSG.noCanvas }; }
      try {
        var measure = function (font, s) { c.font = font; return c.measureText(s).width; };
        draw(c, buildOps(data, measure).ops);
      } catch (e) { say(MSG.failed); return { how: 'failed', msg: MSG.failed }; }
      return toBlob(canvas).then(function (blob) {
        var env = { navigator: typeof navigator !== 'undefined' ? navigator : null, document: document, URL: typeof URL !== 'undefined' ? URL : null, File: typeof File !== 'undefined' ? File : null };
        return deliver(blob, (data && data.file) || fileName(data && data.sport, data && data.title), env).then(function (r) { say(r.msg); return r; });
      });
    }).catch(function () { say(MSG.failed); return { how: 'failed', msg: MSG.failed }; });
  }

  SV2.share = {
    W: W, H: H, PAL: PAL, TIER_COL: TIER_COL, TEXT_ON: TEXT_ON, MSG: MSG, M: M, MT: MT, MB: MB, GAP: GAP,
    contrast: contrast, S: S, slug: slug, fileName: fileName, pageUrl: pageUrl, wrap: wrap, clamp: clamp,
    buildOps: buildOps, draw: draw, deliver: deliver, run: run
  };
})();
