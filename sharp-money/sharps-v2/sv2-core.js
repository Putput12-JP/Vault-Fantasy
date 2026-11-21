/* Sharps V2 core. window.SV2 is the one namespace the page files (sv2-sharps.js, sv2-following.js) build on.
   Sharp money is context only: nothing here is a bet signal, a size rule, or an input to Top Reads, SM_GATE or any total.
   Every number is a stored field or arithmetic on stored fields; a missing field returns null and the caller omits it.
   All times Central. No text-glyph icons, no em dashes.
   Loads standalone (no build step). Also loads in node (module.exports) for the pure-function tests: nothing touches the
   DOM or storage until boot() runs, and boot() only runs when #sv2-main exists. */
(function () {
  'use strict';
  var root = typeof window !== 'undefined' ? window : globalThis;
  var SV2 = {};
  SV2.version = 1;

  /* ------------------------------------------------------------------ small helpers */
  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function num(x) { return isNum(x) ? x : null; }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function trim(x, d) { return String(+x.toFixed(d)); }
  function sportName(sp) { return { nba: 'NBA', nfl: 'NFL', cfb: 'CFB', cbb: 'CBB' }[String(sp).toLowerCase()] || String(sp || '').toUpperCase(); }
  function $(sel, el) { return (el || document).querySelector(sel); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  SV2.esc = esc; SV2.$ = $; SV2.$$ = $$; SV2.sportName = sportName; SV2.isNum = isNum;

  /* tiny event bus. Events: cards, wallets, splits, follows, route, theme, tick, refresh */
  var handlers = {};
  SV2.on = function (name, fn) { (handlers[name] = handlers[name] || []).push(fn); return fn; };
  SV2.off = function (name, fn) { handlers[name] = (handlers[name] || []).filter(function (f) { return f !== fn; }); };
  SV2.emit = function (name, arg) {
    (handlers[name] || []).slice().forEach(function (f) { try { f(arg); } catch (e) { if (root.console) console.error('SV2 handler', name, e); } });
  };

  /* ------------------------------------------------------------------ dev hooks (localhost only) */
  function loc() { return root.location || { hostname: '', search: '', hash: '' }; }
  function isLocalHost(h) { h = String(h || ''); return h === 'localhost' || h === '127.0.0.1' || h === '[::1]' || h === '::1' || /\.localhost$/.test(h); }
  /* a dev value must be a same-origin path: starts with one slash, never // or /\ (browsers read \ as /) */
  function validDevPath(p) { return typeof p === 'string' && p.charAt(0) === '/' && p.charAt(1) !== '/' && p.charAt(1) !== '\\' && p.indexOf('\\') < 0; }
  function devParam(name) {
    var l = loc();
    if (!isLocalHost(l.hostname)) return null;
    var m = new RegExp('[?&]' + name + '=([^&]*)').exec(l.search || '');
    if (!m) return null;
    var v; try { v = decodeURIComponent(m[1]); } catch (e) { return null; }
    return validDevPath(v) ? v : null;
  }
  SV2.dev = { ok: function () { return isLocalHost(loc().hostname); }, param: devParam, validPath: validDevPath };

  /* page clock: epoch seconds, or the dev ?now= value (pins countdowns, bands and ages for stable screenshots) */
  SV2.now = function () {
    if (isLocalHost(loc().hostname)) {
      var m = /[?&]now=(\d{9,11})/.exec(loc().search || '');
      if (m) return +m[1];
    }
    return Date.now() / 1000;
  };

  /* ------------------------------------------------------------------ Central time */
  var DTF = {};
  function dtf(key, opts) {
    return DTF[key] || (DTF[key] = new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: 'America/Chicago' }, opts)));
  }
  function clean(s) { return s.replace(/[  ]/g, ' '); }
  function ctParts(t) {
    var o = {};
    dtf('parts', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
      .formatToParts(new Date(t * 1000)).forEach(function (p) { o[p.type] = p.value; });
    return o;
  }
  var ct = {};
  ct.dateKey = function (t) { if (!isNum(t)) return null; var p = ctParts(t); return p.year + '-' + p.month + '-' + p.day; };
  ct.addDays = function (key, n) {
    var a = key.split('-').map(Number), d = new Date(Date.UTC(a[0], a[1] - 1, a[2] + n, 12));
    return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0');
  };
  /* "10:21 AM", or "10:21 AM CT" with withCT (put CT on the first time of a line) */
  ct.time = function (t, withCT) {
    if (!isNum(t)) return null;
    var s = clean(dtf('time', { hour: 'numeric', minute: '2-digit', hour12: true }).format(new Date(t * 1000)));
    return withCT ? s + ' CT' : s;
  };
  ct.md = function (t) { return isNum(t) ? dtf('md', { month: 'short', day: 'numeric' }).format(new Date(t * 1000)) : null; };
  ct.dayTime = function (t) {
    return isNum(t) ? clean(dtf('wd', { weekday: 'short' }).format(new Date(t * 1000))) + ' ' + ct.time(t) : null;
  };
  ct.stamp = function (t) { return isNum(t) ? ct.md(t) + ', ' + ct.time(t) : null; };
  /* Today / Tomorrow / "Sun Nov 23" */
  ct.day = function (t, nowT) {
    if (!isNum(t)) return null;
    var k = ct.dateKey(t), today = ct.dateKey(isNum(nowT) ? nowT : SV2.now());
    if (k === today) return 'Today';
    if (k === ct.addDays(today, 1)) return 'Tomorrow';
    return clean(dtf('wdmd', { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date(t * 1000))).replace(',', '');
  };
  ct.ago = function (t, nowT) {
    if (!isNum(t)) return null;
    var s = (isNum(nowT) ? nowT : SV2.now()) - t;
    if (s < 60) return 'just now';
    if (s < 3600) return Math.floor(s / 60) + ' min ago';
    if (s < 86400) return Math.floor(s / 3600) + ' h ago';
    return Math.floor(s / 86400) + ' d ago';
  };
  /* seconds to "24m", "1h 05m", "2d 3h". No motion on countdowns. */
  ct.countdown = function (s) {
    if (!isNum(s)) return null;
    if (s <= 0) return 'now';
    if (s < 60) return '<1m';
    if (s < 3600) return Math.floor(s / 60) + 'm';
    if (s < 86400) return Math.floor(s / 3600) + 'h ' + String(Math.floor((s % 3600) / 60)).padStart(2, '0') + 'm';
    return Math.floor(s / 86400) + 'd ' + Math.floor((s % 86400) / 3600) + 'h';
  };
  SV2.ct = ct;

  /* ------------------------------------------------------------------ number formatters (null in, null out: the caller omits the field) */
  var fmt = {};
  fmt.n = function (x, d) { return isNum(x) ? x.toLocaleString('en-US', { maximumFractionDigits: d || 0 }) : null; };
  /* $442, $1.6K, $17.1K, $358K, $1.2M ; { full:true } gives $2,000 */
  fmt.usd = function (x, o) {
    if (!isNum(x)) return null;
    var sign = x < 0 ? '-' : '', a = Math.abs(x);
    if (o && o.full) return sign + '$' + Math.round(a).toLocaleString('en-US');
    var r = Math.round(a);
    if (r < 1000) return sign + '$' + r;
    var k = a / 1000;
    if (k >= 999.5) return sign + '$' + trim(a / 1e6, 1) + 'M';
    return sign + '$' + trim(k, k < 100 ? 1 : 0) + 'K';
  };
  /* price 0..1 to "41.5c" or "55c" */
  fmt.cents = function (p) { return isNum(p) ? trim(Math.round(p * 1000) / 10, 1) + 'c' : null; };
  /* closing-line value in price units to "+1.0c" (always one decimal, signed) */
  fmt.centsSigned = function (x) {
    if (!isNum(x)) return null;
    var c = Math.round(x * 1000) / 10;
    return (c > 0 ? '+' : '') + c.toFixed(1) + 'c';
  };
  /* implied probability to American odds, as a string: 0.55 -> "-122", 0.4 -> "+150" */
  fmt.american = function (p) {
    if (!isNum(p) || p <= 0 || p >= 1) return null;
    return p >= 0.5 ? '-' + Math.round(p / (1 - p) * 100) : '+' + Math.round((1 - p) / p * 100);
  };
  fmt.line = function (x, o) {
    if (!isNum(x)) return null;
    var s = trim(x, 2);
    return o && o.signed && x > 0 ? '+' + s : s;
  };
  /* fraction to percent: 0.147 -> "14.7%" ; { d:0 } digits ; { signed:true } adds + */
  fmt.pct = function (f, o) {
    if (!isNum(f)) return null;
    var d = o && isNum(o.d) ? o.d : 1, s = (f * 100).toFixed(d);
    return (o && o.signed && f > 0 ? '+' : '') + s + '%';
  };
  /* already a percent (Action Network split) to "33%" */
  fmt.pctInt = function (x) { return isNum(x) ? Math.round(x) + '%' : null; };
  fmt.units = function (u, o) {
    if (!isNum(u)) return null;
    return (o && o.signed && u > 0 ? '+' : '') + trim(u, 2) + 'u';
  };
  fmt.wl = function (w, l, p) {
    if (!isNum(w) || !isNum(l)) return null;
    return w + '-' + l + (isNum(p) && p > 0 ? '-' + p : '');
  };
  fmt.mult = function (x) { return isNum(x) ? trim(x, 1) + 'x' : null; };
  fmt.addr = function (w) { return typeof w === 'string' && w.length > 10 ? w.slice(0, 6) + '...' + w.slice(-4) : (typeof w === 'string' ? w : null); };
  fmt.tail = function (w) { return typeof w === 'string' && w.length > 6 ? '...' + w.slice(-6) : (typeof w === 'string' ? w : null); };
  SV2.fmt = fmt;

  /* ------------------------------------------------------------------ copy deck strings used by shared components */
  var copy = {
    title: { sharps: 'Sharps', following: 'Following' },
    context: {
      sharps: 'Context only. The size is a flat 1u from an untested rule.',
      following: 'Context only: no size, no pick.'
    },
    info: {
      title: 'How to read this',
      sharps: [
        'A play is a side the staking rule picked from Polymarket wallets. It is copied from an outside tracker\'s rules and has not passed a forward test here.',
        'The size is always 1u on NBA, NFL and CBB, and there is no size on CFB. The tier does not change the size.',
        'The tier counts stored facts for and against the side. It is a label, not a prediction, and it has no record yet.',
        'Prices are Polymarket\'s displayed price at the last read, before the spread you would pay.'
      ],
      following: [
        'You see what wallets hold right now. Amounts are shares times the market price at the last scan, not what they paid.',
        '"Beats the close" means a wallet\'s buys were usually at better prices than the closing price, over 30 or more games (NBA and NFL only). In our tests that price edge was mostly gone by game time.',
        '"Past winner" means a good record on games before we picked the wallet. It was picked after the fact and has not held up going forward.',
        'Follows are saved in this browser only.'
      ]
    },
    guard: 'This file is not marked context only; sizes are hidden.',
    fresh: { none: 'Could not load the data file.', old: '(older than usual)', stale: 'Last refresh failed, showing the earlier file.' },
    refresh: { idle: 'Refresh', done: 'Up to date', fail: 'Try again' },
    tier: {
      clear: { word: 'Clear', pips: 3, why: 'Nothing stored against it, and a price fact for it' },
      mixed: { word: 'Mixed', pips: 2, why: 'Nothing stored against it, only partial support for it' },
      thin: { word: 'Thin', pips: 1, why: 'One wallet, no price check either way' },
      contested: { word: 'Contested', pips: 0, why: 'Stored facts point the other way' }
    },
    tierOrder: ['clear', 'mixed', 'thin', 'contested'],
    acct: {
      beats: { word: 'Beats the close', sentence: function (n) { return 'Beats the closing price, ' + n + ' games'; } },
      even: { word: 'Even with the close', sentence: function (n) { return 'No clear price edge, ' + n + ' games'; } },
      loses: { word: 'Loses to the close', sentence: function (n) { return 'Buys worse than the close, ' + n + ' games'; } },
      few: { word: 'Too few closing prices', sentence: function (n) { return 'Too few closing prices to judge (' + n + ')'; } }
    },
    acctOrder: ['beats', 'even', 'few', 'loses'],
    chip: {
      past: 'Past winner, picked after the fact',
      inactive: 'No bets in 30 days',
      sc: function (sport, n) { return 'On the ' + sportName(sport) + ' price scorecard, ' + n + ' games'; }
    },
    play: { pill: '1u', label: 'untested rule' },
    star: {
      on: function (name, sport) { return 'Unfollow ' + name + ' in ' + sportName(sport); },
      off: function (name, sport) { return 'Follow ' + name + ' in ' + sportName(sport); }
    },
    forbidden: ['agree', 'agreement', 'hot', 'proven', 'elite', 'prem', 'lock', 'locks', 'locked', 'lean', 'weak', 'sharp pick', 'best bet', 'guaranteed', 'confidence', 'strong']
  };
  SV2.copy = copy;

  /* ------------------------------------------------------------------ pure rule functions (unit tested) */
  var PLAY_SPORTS = { nba: 1, nfl: 1, cbb: 1 };   /* flat 1u; none on CFB */
  var TIER_SPORTS = { nba: 1, nfl: 1 };           /* the closing-price model exists for these only */
  var EV_PTS = 0.3;                               /* EV_ON_PTS in scripts/sf_signals.py, already registered */
  var rules = {};

  function mkt(game, g) { return game && game.markets && game.markets[g] || null; }
  function sidesOf(m) { return m && m.sides || {}; }
  function sideAll(m, name) { var s = sidesOf(m)[name]; return s && s.all || null; }
  function sfAll(m) { return m && m.sf && m.sf.all || null; }
  function lc(s) { return String(s || '').toLowerCase(); }

  /* the size shown on the page: shown_units when the plays-data build publishes it, else a flat 1 on NBA, NFL, CBB.
     The old ladder (sf.all.units) is never returned as a size. */
  rules.shownUnits = function (game, g) {
    var m = mkt(game, g), sf = sfAll(m);
    if (!sf || !sf.side) return 0;
    if (isNum(sf.shown_units)) return sf.shown_units > 0 ? sf.shown_units : 0;
    if (!PLAY_SPORTS[lc(game.sport)]) return 0;
    return isNum(sf.units) && sf.units > 0 ? 1 : 0;
  };

  /* the stored facts for and against the shown side (spec 1.1). Returns null when the market has no shown play. */
  rules.factsOf = function (game, g) {
    var m = mkt(game, g), sf = sfAll(m);
    if (!sf || !sf.side) return null;
    var S = sf.side, sport = lc(game.sport), tiered = !!TIER_SPORTS[sport];
    var others = Object.keys(sidesOf(m)).filter(function (k) { return k !== S; });
    var a1 = 0, a2 = 0;
    others.forEach(function (k) {
      var a = sideAll(m, k); if (!a) return;
      var c = a.counts || {};
      a1 += (c.hc || 0) + (c.sharp || 0);
      if (tiered && a.rk) a2 += a.rk.sharp_n || 0;
    });
    var mine = sideAll(m, S) || {};
    var ev = sf.signals && sf.signals.ev, pts = ev && isNum(ev.pts) ? ev.pts : null;
    var tB = m.tp && m.tp.tB && m.tp.tB.side ? m.tp.tB.side : null;
    var b1n = tiered && mine.rk ? (mine.rk.sharp_n || 0) : 0;
    var provenN = mine.proven && isNum(mine.proven.wallets) ? mine.proven.wallets : 0;
    var f = {
      side: S, sport: sport, others: others, tiered: tiered, pts: pts, proven: provenN,
      a1: { on: a1 >= 1, n: a1 },
      a2: { on: a2 >= 1, n: a2 },
      a3: { on: !!tB && tB !== S, side: tB },
      a4: { on: pts != null && pts <= -EV_PTS, pts: pts },
      b1: { on: b1n >= 1, n: b1n },
      b2: { on: pts != null && pts >= EV_PTS, pts: pts },
      b3: { on: !!(m.sf && m.sf.fwd && m.sf.fwd.side === S) },
      b4: { on: provenN >= 2, n: provenN }
    };
    f.against = ['a1', 'a2', 'a3', 'a4'].filter(function (k) { return f[k].on; });
    f.for = ['b1', 'b2', 'b3', 'b4'].filter(function (k) { return f[k].on; });
    return f;
  };

  /* Clear / Mixed / Thin / Contested for a shown play, 'none' for no shown size. First match wins. A stored tier
     (plays-data v2.tier logged at freeze) wins over the client rule. */
  rules.tierOf = function (game, g) {
    if (rules.shownUnits(game, g) <= 0) return 'none';
    var f = rules.factsOf(game, g); if (!f) return 'none';
    var m = mkt(game, g), stored = m && m.v2 && typeof m.v2.tier === 'string' ? lc(m.v2.tier) : null;
    var t;
    if (f.against.length) t = 'contested';
    else if ((f.b1.on || f.b2.on) && f.b3.on) t = 'clear';
    else if (f.proven <= 1 && !f.b1.on && f.pts == null) t = 'thin';
    else t = 'mixed';
    if (stored && copy.tier[stored]) {
      if (stored !== t && SV2.dev.ok() && root.console) console.warn('SV2 tier differs from stored', game.ev, g, stored, t);
      return stored;
    }
    return t;
  };

  /* freeze band by cut (T-15) in Central: hour (within 60 min), today, tomorrow, later */
  rules.bandOf = function (cut, nowT) {
    if (!isNum(cut)) return 'later';
    nowT = isNum(nowT) ? nowT : SV2.now();
    if (cut - nowT <= 3600) return 'hour';
    var k = ct.dateKey(cut), today = ct.dateKey(nowT);
    if (k === today) return 'today';
    if (k === ct.addDays(today, 1)) return 'tomorrow';
    return 'later';
  };

  /* wallets (classes hc or sharp) holding the shown side of 3 or more shown plays. plays: [{game, g}] */
  rules.sameWallet = function (plays, o) {
    var min = o && isNum(o.min) ? o.min : 3, by = {}, total = 0;
    (plays || []).forEach(function (p) {
      var m = mkt(p.game, p.g), sf = sfAll(m); if (!sf || !sf.side) return;
      total++;
      var a = sideAll(m, sf.side), seen = {};
      ((a && a.list) || []).forEach(function (r) {
        if (!r || !r.w || (r.class !== 'hc' && r.class !== 'sharp') || seen[r.w]) return;
        seen[r.w] = 1;
        (by[r.w] = by[r.w] || []).push(p.game.ev + '|' + p.g);
      });
    });
    return Object.keys(by).map(function (w) { return { w: w, n: by[w].length, total: total, keys: by[w] }; })
      .filter(function (r) { return r.n >= min; })
      .sort(function (a, b) { return b.n - a.n || (a.w < b.w ? -1 : 1); });
  };

  /* wallet tier on the V2 words. A stored v2.tier wins; college rows are always 'few' (no tested model there). */
  rules.v2TierOf = function (row, sport) {
    if (row && row.v2 && typeof row.v2.tier === 'string' && copy.acct[row.v2.tier]) return row.v2.tier;
    if (sport && !TIER_SPORTS[lc(sport)]) return 'few';
    var t = row && row.rk && row.rk.tier;
    return t === 'sharp' ? 'beats' : t === 'mid' ? 'even' : t === 'dull' ? 'loses' : 'few';
  };

  var HEXLIKE = /^0x[0-9a-fA-F]{20,}/;
  /* display name: name_disp, else a real name, else "Unnamed 0x1234...abcd" */
  rules.nameOf = function (row, w) {
    if (row && typeof row.name_disp === 'string' && row.name_disp) return row.name_disp;
    var n = row && row.name;
    if (typeof n === 'string' && n && !HEXLIKE.test(n)) return n;
    var a = String(w || '');
    return 'Unnamed ' + (a.length > 10 ? a.slice(0, 6) + '...' + a.slice(-4) : a);
  };

  /* positions that are rungs of one side: total mark value (stored side_usd, else the sum of rung usd), rung count, stored multiple */
  rules.sideTotals = function (positions) {
    var ps = positions || [], sum = 0, any = false;
    ps.forEach(function (p) { if (isNum(p.usd)) { sum += p.usd; any = true; } });
    var first = ps[0] || {};
    return {
      usd: any ? sum : null,
      stored_usd: isNum(first.side_usd) ? first.side_usd : null,
      rungs: isNum(first.side_rungs) ? first.side_rungs : ps.length,
      press: isNum(first.side_press) ? first.side_press : null
    };
  };
  rules.sideKey = function (p) { return [p.ev, p.gst, p.g, p.side].join('|'); };
  /* group a wallet's positions by game + market + side, in first-seen order */
  rules.groupSides = function (positions) {
    var out = [], idx = {};
    (positions || []).forEach(function (p) {
      var k = rules.sideKey(p);
      if (!(k in idx)) { idx[k] = out.length; out.push({ key: k, ev: p.ev, gst: p.gst, g: p.g, side: p.side, positions: [] }); }
      out[idx[k]].positions.push(p);
    });
    out.forEach(function (s) { var t = rules.sideTotals(s.positions); s.usd = t.usd; s.rungs = t.rungs; s.press = t.press; });
    return out;
  };

  /* "Since you followed": a wallet's items from since.json: [settled_at, first_fill, r, flat, ev, stake]; r 1 win, 0 loss, 2 push.
     The unit of an item is a POSITION, so w / l / p count bets (a spread and a moneyline on one game are two). `games` tallies one
     result per game, that of its biggest stake (the way the classic page's legs do). null when the list is missing (the caller says
     "Not available yet"). Items placed (first_fill) or settled before the follow are dropped. */
  rules.sinceItems = function (since, sport, w, retained) {
    var o = since && since[retained ? 'retained' : 'sports'], l = o && o[sport] && o[sport][w];
    return Array.isArray(l) ? l : (since && isNum(since.built) ? [] : null);   /* a wallet with no item is left out of the file: none */
  };
  rules.sinceFollowed = function (items, followedAt, sinceFrom) {
    var list = items;
    if (!Array.isArray(list) || !isNum(followedAt)) return null;
    var w = 0, l = 0, p = 0, units = 0, skipped = 0, best = {};
    list.forEach(function (it) {
      if (!Array.isArray(it) || !(it[0] >= followedAt) || !(it[1] >= followedAt)) return;
      if (it[2] === 2) { p++; return; }
      if (it[2] === 1) w++; else if (it[2] === 0) l++; else return;
      if (isNum(it[3])) units += it[3]; else skipped++;
      var k = it[4] == null ? 'x' + w + '-' + l : it[4];
      if (!(k in best) || (isNum(it[5]) && it[5] > best[k][5])) best[k] = it;
    });
    var gw = 0, gl = 0;
    Object.keys(best).forEach(function (k) { if (best[k][2] === 1) gw++; else gl++; });
    return { w: w, l: l, p: p, n: w + l, units: Math.round(units * 100) / 100, skipped: skipped, games: { w: gw, l: gl, n: gw + gl },
             from: followedAt, windowNote: isNum(sinceFrom) && followedAt < sinceFrom, sinceFrom: isNum(sinceFrom) ? sinceFrom : null };
  };
  SV2.rules = rules;

  /* ------------------------------------------------------------------ router */
  var PAGES = ['sharps', 'following'];
  /* embedded in a host page (embed.js) the route lives in this variable, never in the host's location */
  var EH = null;
  function curHash() { return EH != null ? EH : loc().hash; }
  function parseHash(h) {
    var s = String(h == null ? curHash() : h).replace(/^#\/?/, '');
    var parts = s.split('/').filter(Boolean).map(function (x) { try { return decodeURIComponent(x); } catch (e) { return x; } });
    var known = PAGES.indexOf(parts[0]) >= 0;
    return { page: known ? parts[0] : 'sharps', sub: known ? parts.slice(1) : [], known: known, hash: '#' + (known ? parts.join('/') : 'sharps') };
  }
  SV2.route = function () { return parseHash(); };
  SV2.parseHash = parseHash;
  /* go('following/acct/nba/0x...') pushes a history entry (state {sv2:1}); go(h, {replace:true}) replaces.
     Boot installs SV2._route, which applies the route and emits 'route' (pushState does not fire hashchange). */
  SV2.go = function (h, o) {
    var next = '#' + String(h).replace(/^#\/?/, '');
    if (EH != null) EH = next;
    else if (loc().hash !== next) {
      if (o && o.replace) root.history.replaceState(null, '', next); else root.history.pushState({ sv2: 1 }, '', next);
    }
    if (SV2._route) SV2._route(); else SV2.emit('route', parseHash(next));
  };

  /* ------------------------------------------------------------------ follow store (the exact shape following.js v13 writes) */
  var FKEY = 'vault-sharps-following', fmem = null;
  function fRead() {
    try {
      var raw = root.localStorage.getItem(FKEY), o = raw ? JSON.parse(raw) : {};
      return o && typeof o === 'object' && !Array.isArray(o) ? o : {};
    } catch (e) { return fmem ? fmem : {}; }
  }
  function fWrite(o) {
    fmem = o;
    try { root.localStorage.setItem(FKEY, JSON.stringify(o)); } catch (e) { /* kept in memory for this session */ }
  }
  var follows = {
    all: function () { return Object.assign({}, fRead()); },
    has: function (sport, w) { return (sport + '|' + w) in fRead(); },
    at: function (sport, w) { var v = fRead()[sport + '|' + w]; return isNum(v) ? v : null; },
    list: function () {
      var o = fRead();
      return Object.keys(o).map(function (k) { var i = k.indexOf('|'); return { sport: k.slice(0, i), w: k.slice(i + 1), at: o[k] }; })
        .sort(function (a, b) { return (b.at || 0) - (a.at || 0); });
    },
    /* flips one follow, leaves every other entry untouched, returns the new state */
    toggle: function (sport, w) {
      var o = Object.assign({}, fRead()), k = sport + '|' + w, on;
      if (k in o) { delete o[k]; on = false; } else { o[k] = Math.floor(Date.now() / 1000); on = true; }
      fWrite(o);
      SV2.emit('follows', { sport: sport, w: w, on: on });
      return on;
    }
  };
  SV2.follows = follows;

  /* ------------------------------------------------------------------ data store and loaders */
  var RAW = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-cards-live/';
  var store = {
    cards: null, wallets: null, splits: null,
    state: { cards: 'loading', wallets: 'loading', splits: 'none' },
    stale: { cards: false, wallets: false },
    loadedAt: { cards: 0, wallets: 0 }
  };
  SV2.store = store;
  var inflight = {};
  /* the cards file is published as live.json; wallets.json and since.json keep their names */
  function srcFor(kind) { return devParam(kind) || (RAW + (kind === 'cards' ? 'live' : kind) + '.json'); }
  function withKey(url, force) {
    var k = force ? Date.now() : Math.floor(Date.now() / 120000);
    return url + (url.indexOf('?') < 0 ? '?' : '&') + 't=' + k;
  }
  function fetchJSON(url, force) {
    var ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, 25000) : null;
    return fetch(withKey(url, force), { cache: force ? 'no-store' : 'default', signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; })
      .then(function (j) { if (timer) clearTimeout(timer); return j && typeof j === 'object' ? j : null; });
  }
  function loadKind(kind, force) {
    if (inflight[kind] && !force) return inflight[kind];
    var p = fetchJSON(srcFor(kind), force).then(function (j) {
      delete inflight[kind];
      var held = store[kind];
      if (!j) {
        /* failure: keep what we hold and say so (stale), else 'none' */
        if (held) store.stale[kind] = true; else store.state[kind] = 'none';
        SV2.emit(kind, null);
        return held || null;
      }
      store.stale[kind] = false;
      /* a CDN can serve an older build after a newer one: never step backwards */
      if (held && isNum(held.built) && isNum(j.built) && j.built < held.built) { SV2.emit(kind, held); return held; }
      store[kind] = j; store.state[kind] = 'ok'; store.loadedAt[kind] = Date.now();
      if (kind === 'cards') buildSplits();
      SV2.emit(kind, j);
      return j;
    });
    inflight[kind] = p;
    return p;
  }
  var load = {
    cards: function (force) { return loadKind('cards', force); },
    wallets: function (force) { return loadKind('wallets', force); },
    /* since.json: each wallet's dated settled list, published beside wallets.json and read only where a follow is tallied */
    since: function (force) { return loadKind('since', force); },
    /* production: splits come from live.json when plays-data publishes markets[g].splits (nothing to fetch).
       dev: ?splits=/path/to/file shaped like sharp-data data.json ({generated, games:[{key, splits}]}). */
    splits: function () {
      var src = devParam('splits');
      if (!src) { buildSplits(); return Promise.resolve(store.splits); }
      if (inflight.splits) return inflight.splits;
      store.state.splits = 'loading';
      inflight.splits = fetchJSON(src, false).then(function (j) {
        delete inflight.splits;
        store.devSplits = j; store.state.splits = j ? 'ok' : 'none';
        buildSplits(); SV2.emit('splits', store.splits);
        return store.splits;
      });
      return inflight.splits;
    }
  };
  SV2.load = load;

  /* Dev splits join (spec 5.4): data.json games[].key = live games[].vault.key; ml and sp sides map by the team nickname
     (vault.teams.home[1] / away[1]) to home / away; total maps Over / Under. A side that does not map is omitted. */
  var SPLIT_KEY = { ml: 'ml', spread: 'sp', total: 'tot' };
  function buildSplits() {
    var d = store.devSplits, c = store.cards;
    if (!d || !c || !Array.isArray(d.games)) { store.splits = null; return; }
    var by = {}; d.games.forEach(function (g) { if (g && g.key && g.splits) by[g.key] = g.splits; });
    var t = typeof d.generated === 'string' ? Math.floor(Date.parse(d.generated) / 1000) : num(d.generated);
    var out = {};
    (c.games || []).forEach(function (game) {
      var sp = game.vault && by[game.vault.key]; if (!sp) return;
      var tm = game.vault.teams || {}, home = tm.home && tm.home[1], away = tm.away && tm.away[1];
      Object.keys(game.markets || {}).forEach(function (g) {
        var src = sp[SPLIT_KEY[g]]; if (!src) return;
        var sides = {};
        Object.keys(sidesOf(game.markets[g])).forEach(function (name) {
          var which = g === 'total' ? (name === 'Over' ? 'over' : name === 'Under' ? 'under' : null) : (name === home ? 'home' : name === away ? 'away' : null);
          var s = which && src[which];
          if (s && (isNum(s.t) || isNum(s.m))) sides[name] = { bets: num(s.t), money: num(s.m) };
        });
        if (Object.keys(sides).length) out[game.ev + '|' + g] = { t: t, src: 'Action Network', sides: sides };
      });
    });
    store.splits = { byKey: out, generated: t };
  }
  /* splits for one market: published in live.json (markets[g].splits) first, else the dev join. null when absent (omit the section). */
  SV2.splitsFor = function (game, g) {
    var m = mkt(game, g);
    if (m && m.splits && m.splits.sides) return m.splits;
    var s = store.splits && store.splits.byKey[game.ev + '|' + g];
    return s || null;
  };

  /* sizes may show only when the plays file is marked context only (and the wallets file, if loaded) */
  SV2.sizesOk = function () {
    if (!store.cards || store.cards.context_only !== true) return false;
    if (store.wallets && store.wallets.context_only !== true) return false;
    return true;
  };

  /* age of a file in seconds (page clock minus its built time), or null */
  SV2.age = function (kind) { var f = store[kind]; return f && isNum(f.built) ? SV2.now() - f.built : null; };

  /* ------------------------------------------------------------------ theme and skin (head script sets the first paint) */
  function lsGet(k) { try { return root.localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { root.localStorage.setItem(k, v); } catch (e) { /* storage unavailable */ } }
  SV2.theme = {
    /* 'system' (no override), 'dark' or 'light' */
    get: function () { var v = lsGet('sv2-theme'); return v === 'dark' || v === 'light' || v === 'system' ? v : null; },
    effective: function () {
      var a = document.documentElement.getAttribute('data-theme');
      if (a === 'dark' || a === 'light') return a;
      return root.matchMedia && root.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    },
    set: function (v) {
      if (v !== 'dark' && v !== 'light') v = 'system';
      lsSet('sv2-theme', v);
      if (v === 'system') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', v);
      SV2.emit('theme', v);
    }
  };
  SV2.skin = {
    get: function () { return document.documentElement.getAttribute('data-sv2-skin') === 'apple' ? 'apple' : 'default'; },
    set: function (v) {
      v = v === 'apple' ? 'apple' : 'default';
      lsSet('sv2-skin', v); document.documentElement.setAttribute('data-sv2-skin', v);
      SV2.emit('theme', v);
    }
  };

  /* ------------------------------------------------------------------ UI components (HTML strings; the page files own their markup) */
  var ui = {};
  var ICONS = {
    star: '<path d="M12 3.2l2.7 5.6 6.1.8-4.5 4.2 1.2 6.1L12 17l-5.5 2.9 1.2-6.1L3.2 9.6l6.1-.8z"/>',
    chevron: '<path d="M6 9.5l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.4-5.7M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    close: '<path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    info: '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 11v5.5M12 7.6v.2" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    menu: '<path d="M5 8h14M5 16h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="9" cy="8" r="2.2" fill="var(--sv2-card)" stroke="currentColor" stroke-width="2"/><circle cx="15" cy="16" r="2.2" fill="var(--sv2-card)" stroke="currentColor" stroke-width="2"/>',
    sharps: '<path d="M4 18V9M10 18V5M16 18v-6M21 18H3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    following: '<circle cx="12" cy="8.5" r="3.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M5 20c.6-3.6 3.4-5.5 7-5.5s6.4 1.9 7 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
  };
  /* inline SVG icon. Fill icons (star) are styled by CSS; the rest are stroked with currentColor. */
  ui.icon = function (name, cls) {
    return '<svg class="' + (cls || '') + '" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + (ICONS[name] || '') + '</svg>';
  };
  ui.spinner = function (size) { return '<span class="sv2-spinner ' + (size || 'sm') + '" aria-hidden="true"></span>'; };
  /* loading skeleton in the shape of a list of rows; screen readers get the label */
  ui.skel = function (n, label, rowClass) {
    var rows = ''; for (var i = 0; i < (n || 3); i++) rows += '<div class="sv2-skel ' + (rowClass || 'sv2-skel-row') + '"></div>';
    return '<div class="sv2-skel-list" role="status" aria-label="' + esc(label || 'Loading') + '">' + rows + '<span class="sv2-sr">' + esc(label || 'Loading') + '</span></div>';
  };
  ui.chip = function (text, kind, extra) {
    return '<span class="sv2-chip sv2-chip--' + (kind || 'muted') + (extra ? ' ' + extra : '') + '">' + esc(text) + '</span>';
  };
  /* play tier: pips (aria-hidden) plus the word, ink only. { why:true } appends the one-line meaning. */
  ui.tier = function (tier, o) {
    var t = copy.tier[tier]; if (!t) return '';
    var pips = '<span class="sv2-pips" aria-hidden="true">' + [0, 1, 2].map(function (i) { return '<i class="' + (i < t.pips ? 'on' : '') + '"></i>'; }).join('') + '</span>';
    var chip = '<span class="sv2-tier sv2-tier--' + tier + '" data-tier="' + tier + '">' + pips + '<span>' + esc(t.word) + '</span></span>';
    return o && o.why ? chip + ' <span class="sv2-tier-why">' + esc(t.why) + '</span>' : chip;
  };
  /* account tier chip. Only "Beats the close" takes the price colour; the rest are muted. { n } adds the games count after the word. */
  ui.acct = function (tier, o) {
    var t = copy.acct[tier]; if (!t) return '';
    var n = o && isNum(o.n) ? o.n : null;
    return '<span class="sv2-chip ' + (tier === 'beats' ? 'sv2-chip--price' : 'sv2-chip--muted') + '" data-acct="' + tier + '">' + '<span>' + esc(t.word) + (n != null ? ', <span class="sv2-num">' + fmt.n(n) + '</span> games' : '') + '</span></span>';
  };
  /* "1u . untested rule" pill. Returns '' when the files are not marked context only, so a size never shows without its label or guard. */
  ui.playPill = function (units) {
    if (!SV2.sizesOk() || !isNum(units) || units <= 0) return '';
    return '<span class="sv2-play"><b>' + esc(fmt.units(units)) + '</b><span>' + esc(copy.play.label) + '</span></span>';
  };
  /* follow star (44 x 44). Clicks are handled by core: it flips the store and updates every star for that wallet. */
  ui.star = function (sport, w, name) {
    var on = follows.has(sport, w);
    return '<button type="button" class="sv2-star sv2-press sv2-press-chip" data-sv2-star data-sport="' + esc(sport) + '" data-w="' + esc(w) + '" data-name="' + esc(name || '') + '" aria-pressed="' + on + '" aria-label="' + esc(on ? copy.star.on(name, sport) : copy.star.off(name, sport)) + '">' + ui.icon('star') + '</button>';
  };
  /* segmented strip. items: [{v, label, count}]. Wire with SV2.seg.bind(strip, onChange); the rail pill is wired automatically. */
  var seg = {
    html: function (o) {
      var skin = o.skin || 'fill';
      return '<div class="sv2-seg sv2-seg--' + skin + (o.size ? ' ' + o.size : '') + (o.scroll ? ' sv2-scroll' : '') + (o.fluid ? ' fluid' : '') + '" role="group" aria-label="' + esc(o.label || '') + '"' + (o.id ? ' data-rail-id="' + esc(o.id) + '"' : '') + '>' +
        (o.items || []).map(function (it) {
          return '<button type="button" data-v="' + esc(it.v) + '" aria-pressed="' + (String(it.v) === String(o.value)) + '">' + esc(it.label) + (it.count != null ? ' <span class="sv2-cnt">' + esc(it.count) + '</span>' : '') + '</button>';
        }).join('') + '</div>';
    },
    set: function (strip, v) {
      $$('button[data-v]', strip).forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-v') === String(v))); });
    },
    value: function (strip) { var b = $('button[aria-pressed="true"]', strip); return b ? b.getAttribute('data-v') : null; },
    /* delegated: sets aria-pressed on the clicked item and calls onChange(value, button) */
    bind: function (strip, onChange) {
      strip.addEventListener('click', function (e) {
        var b = e.target.closest ? e.target.closest('button[data-v]') : null;
        if (!b || !strip.contains(b)) return;
        var v = b.getAttribute('data-v');
        if (b.getAttribute('aria-pressed') === 'true') return;
        seg.set(strip, v);
        if (onChange) onChange(v, b);
      });
    }
  };
  SV2.seg = seg;
  SV2.ui = ui;

  /* ------------------------------------------------------------------ rail pill: one shared bar that travels (CLAUDE.md traps kept) */
  var rail = (function () {
    var lastGeom = {}, wired = typeof WeakSet !== 'undefined' ? new WeakSet() : null, SKINS = ['fill', 'bar', 'soft'];
    function activeItem(strip) {
      return strip.querySelector(':scope > [aria-pressed="true"], :scope > [aria-current="page"], :scope > .on');
    }
    function stripKey(strip) {
      var pg = strip.closest ? strip.closest('[data-sv2-page]') : null;
      return (pg ? pg.getAttribute('data-sv2-page') : '') + '/' + (strip.getAttribute('data-rail-id') || strip.id || strip.getAttribute('aria-label') || strip.className);
    }
    function ensure(strip) {
      /* trap 0: re-assert the classes every run, in case something rewrote className */
      if (!strip.classList.contains('sv2-seg')) strip.classList.add('sv2-seg');
      if (!SKINS.some(function (s) { return strip.classList.contains('sv2-seg--' + s); })) strip.classList.add('sv2-seg--fill');
      if (strip.getAttribute('data-rail') !== 'on') strip.setAttribute('data-rail', 'on');
      var pill = strip.querySelector(':scope > .sv2-pill');
      if (!pill) { pill = document.createElement('span'); pill.className = 'sv2-pill'; pill.setAttribute('aria-hidden', 'true'); strip.insertBefore(pill, strip.firstChild); }
      return pill;
    }
    /* trap 4: offsetLeft is relative to offsetParent, so walk the chain up to the strip */
    function xOf(item, strip) {
      var x = 0, el = item;
      while (el && el !== strip) { x += el.offsetLeft; el = el.offsetParent; }
      return el === strip ? x : item.offsetLeft;
    }
    /* returns true when the pill is placed */
    function place(strip, animate) {
      var pill = ensure(strip), item = activeItem(strip);
      /* trap 1: park at opacity 0 until the strip has a real width (hidden pages report 0) */
      if (!item || !strip.offsetWidth || !item.offsetWidth) { pill.style.opacity = '0'; pill.removeAttribute('data-ready'); return false; }
      var left = xOf(item, strip), width = item.offsetWidth, L = left + 'px', W = width + 'px', key = stripKey(strip), prev = lastGeom[key];
      var fresh = !pill.style.left;
      if (pill.style.left === L && pill.style.width === W && pill.style.opacity === '1') { pill.setAttribute('data-ready', ''); lastGeom[key] = { left: left, width: width }; return true; }
      var visible = pill.style.opacity === '1' && !fresh;
      if (fresh && animate && prev) {
        /* trap 0b: a re-rendered strip has a brand-new pill; seed it where the old one was, flush, then move it */
        strip.classList.add('sv2-noanim');
        pill.style.left = prev.left + 'px'; pill.style.width = prev.width + 'px'; pill.style.opacity = '1';
        void strip.offsetWidth;
        strip.classList.remove('sv2-noanim');
        pill.style.left = L; pill.style.width = W;
      } else if (animate && visible) {
        pill.style.left = L; pill.style.width = W;
      } else {
        strip.classList.add('sv2-noanim');
        pill.style.left = L; pill.style.width = W; pill.style.opacity = '1';
        void strip.offsetWidth;                      /* trap 2: flush with a reflow, never requestAnimationFrame */
        strip.classList.remove('sv2-noanim');
      }
      pill.style.opacity = '1'; pill.setAttribute('data-ready', '');
      lastGeom[key] = { left: left, width: width };
      return true;
    }
    function wire(strip) {
      if (!strip || (wired && wired.has(strip))) return;
      if (wired) wired.add(strip);
      /* a strip that was re-rendered (innerHTML) has a stable key with a remembered geometry: seed and travel instead of teleporting */
      place(strip, !!lastGeom[stripKey(strip)]);
      if (typeof MutationObserver !== 'undefined') {
        new MutationObserver(function () { place(strip, true); })
          .observe(strip, { subtree: true, childList: true, attributes: true, attributeFilter: ['aria-pressed', 'aria-current', 'class'] });
      }
    }
    function scan(rootEl) { $$('.sv2-seg', rootEl || document).forEach(wire); }
    /* trap 5 and 5b: re-place every visible strip, animating only an already visible, already placed pill */
    function catchUp() {
      $$('.sv2-seg').forEach(function (strip) {
        if (!wired || !wired.has(strip)) { wire(strip); return; }
        var pill = strip.querySelector(':scope > .sv2-pill');
        place(strip, !!(pill && pill.style.opacity === '1' && pill.style.left));
      });
    }
    var api = function (strip) { wire(strip); };
    api.place = place; api.scan = scan; api.catchUp = catchUp; api.wire = wire;
    return api;
  })();
  SV2.rail = rail;

  /* ------------------------------------------------------------------ sheet: bottom sheet on phone, dialog on desktop */
  var sheet = (function () {
    var host = null, panel = null, bodyEl = null, opener = null, curOpts = null, closing = false, closeTimer = null;
    var INERT = ['sv2-hd', 'sv2-main', 'sv2-tabbar'];
    function setInert(on) {
      INERT.forEach(function (id) { var el = document.getElementById(id); if (el) { if (on) el.setAttribute('inert', ''); else el.removeAttribute('inert'); } });
      document.body.classList.toggle('sv2-lock', on);
    }
    function focusables() {
      return $$('a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])', panel)
        .filter(function (el) { return el.offsetParent !== null || el === document.activeElement; });
    }
    function onKey(e) {
      if (!panel) return;
      if (e.key === 'Escape') { e.preventDefault(); api.close(); return; }
      if (e.key !== 'Tab') return;
      var f = focusables(); if (!f.length) { e.preventDefault(); return; }
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    var api = {
      isOpen: function () { return !!panel && !closing; },
      route: function () { return curOpts && curOpts.route || null; },
      body: function () { return bodyEl; },
      /* open(html, {label, route, onClose, returnFocus}). A second open replaces the content in place. */
      open: function (html, o) {
        o = o || {};
        host = host || document.getElementById('sv2-sheet-host');
        if (!host) return null;
        if (panel && !closing) { curOpts = Object.assign(curOpts || {}, o); api.set(html); return bodyEl; }
        if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; if (panel) { panel.remove(); } host.innerHTML = ''; panel = null; }
        closing = false; curOpts = o;
        opener = o.returnFocus || document.activeElement;
        host.innerHTML = '<div class="sv2-scrim" data-sv2-scrim></div>' +
          '<div class="sv2-sheet" role="dialog" aria-modal="true" aria-label="' + esc(o.label || 'Details') + '">' +
          '<div class="sv2-sheet-top"><span class="sv2-sheet-grab" aria-hidden="true"></span>' +
          '<button type="button" class="sv2-ibtn sv2-sheet-x sv2-press sv2-press-btn" data-sv2-close aria-label="Close">' + ui.icon('close') + '</button></div>' +
          '<div class="sv2-sheet-body" data-sv2-sheet-body></div></div>';
        panel = host.querySelector('.sv2-sheet'); bodyEl = host.querySelector('[data-sv2-sheet-body]');
        bodyEl.innerHTML = html || '';
        host.querySelector('[data-sv2-scrim]').addEventListener('click', function () { api.close(); });
        host.querySelector('[data-sv2-close]').addEventListener('click', function () { api.close(); });
        document.addEventListener('keydown', onKey, true);
        setInert(true);
        void panel.offsetWidth;                         /* flush the closed state so the entrance transitions (no rAF) */
        host.setAttribute('data-open', '');
        rail.scan(panel); rail.catchUp();
        var auto = panel.querySelector('[data-autofocus]') || panel.querySelector('[data-sv2-close]');
        if (auto) auto.focus({ preventScroll: true });
        return bodyEl;
      },
      set: function (html) { if (bodyEl) { bodyEl.innerHTML = html || ''; rail.scan(bodyEl); } },
      /* fromRoute: the route already moved (Back), so do not touch history */
      close: function (fromRoute) {
        if (!panel || closing) return;
        closing = true;
        var o = curOpts || {}, back = opener;
        host.removeAttribute('data-open');
        document.removeEventListener('keydown', onKey, true);
        setInert(false);
        var reduce = root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches;
        function done() {
          closeTimer = null;
          if (host) host.innerHTML = '';
          panel = null; bodyEl = null; closing = false; curOpts = null;
          if (back && back.focus && document.contains(back)) { try { back.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
          if (o.onClose) o.onClose();
        }
        if (reduce) done(); else closeTimer = setTimeout(done, 440);
        /* the sheet was opened from a route (#following/acct/...): step back to its parent */
        if (!fromRoute && o.route) {
          if (EH != null) { EH = '#' + parseHash().page; if (SV2._route) SV2._route(); }
          else if (root.history.state && root.history.state.sv2) root.history.back();
          else { root.history.replaceState(null, '', '#' + parseHash().page); if (SV2._route) SV2._route(); }
        }
      }
    };
    return api;
  })();
  SV2.sheet = sheet;

  /* ------------------------------------------------------------------ freshness line, context guard, info panel */
  /* kind: 'cards' | 'wallets' | undefined (by route). One freshness line per route. */
  SV2.fresh = function (el, kind) {
    if (!el) return;
    var k = kind || (SV2.route().page === 'following' ? 'wallets' : 'cards'), f = store[k], st = store.state[k];
    if (!f) {
      el.innerHTML = st === 'loading' ? '<span class="sv2-sr">Loading</span>' : esc(copy.fresh.none) + ' <button type="button" data-sv2-retry>' + esc(copy.refresh.fail) + '</button>';
      return;
    }
    var t = f.built, s = 'Updated ' + ct.time(t, true) + ', ' + ct.ago(t);
    if (k === 'wallets' && store.cards && isNum(store.cards.built) && Math.abs(store.cards.built - t) > 900) s += ', cards ' + ct.time(store.cards.built, true);
    var html = esc(s), age = SV2.age(k);
    if (isNum(age) && age > 1800) html += ' <span class="sv2-old">' + esc(copy.fresh.old) + '</span>';
    if (store.stale[k]) html += ' <span class="sv2-old">' + esc(copy.fresh.stale) + '</span> <button type="button" data-sv2-retry>' + esc(copy.refresh.fail) + '</button>';
    el.innerHTML = html;
  };

  /* ------------------------------------------------------------------ refresh: the one Refresh (Worker, Turnstile, shared 60 s cooldown) */
  var RF = { state: 'idle', sec: 0, clock: null };
  function rfUrl() { return devParam('rfurl') || 'https://sharp-refresh.vaultfantasy.workers.dev'; }
  function paintRf() {
    var b = document.getElementById('sv2-refresh'); if (!b) return;
    var t = b.querySelector('.sv2-rf-t');
    b.setAttribute('data-state', RF.state);
    var label = RF.state === 'busy' ? 'Building ' + Math.floor(RF.sec / 60) + ':' + String(RF.sec % 60).padStart(2, '0') : copy.refresh[RF.state] || copy.refresh.idle;
    if (t) t.textContent = label;
    b.setAttribute('aria-label', RF.state === 'busy' ? label : copy.refresh.idle);
    var live = document.getElementById('sv2-live');
    if (live && (RF.state === 'done' || RF.state === 'fail')) live.textContent = label;
  }
  function turnstileToken(sitekey) {
    return new Promise(function (res, rej) {
      var timer = setTimeout(function () { rej(new Error('turnstile')); }, 20000);
      function go() {
        var el = document.getElementById('sv2-turnstile');
        if (!el) { el = document.createElement('div'); el.id = 'sv2-turnstile'; el.className = 'sv2-turnstile'; document.body.appendChild(el); }
        if (el.dataset.wid) { try { root.turnstile.remove(el.dataset.wid); } catch (e) { /* gone */ } }
        el.replaceChildren();
        el.dataset.wid = root.turnstile.render(el, {
          sitekey: sitekey,
          callback: function (tk) { clearTimeout(timer); res(tk); },
          'error-callback': function () { clearTimeout(timer); rej(new Error('turnstile')); },
          'timeout-callback': function () { clearTimeout(timer); rej(new Error('turnstile')); }
        });
      }
      if (root.turnstile) go();
      else {
        var s = document.createElement('script');
        s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'; s.async = true; s.onload = go;
        s.onerror = function () { clearTimeout(timer); rej(new Error('turnstile')); };
        document.head.appendChild(s);
      }
    });
  }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  /* idle -> busy -> done (10 s) or fail (6 s). dataset.busy is set before the first await (disabled alone leaves a double-write window). */
  SV2.refresh = async function () {
    var btn = document.getElementById('sv2-refresh');
    if (btn && btn.dataset.busy) return;
    if (btn) { btn.dataset.busy = '1'; btn.disabled = true; }
    RF.state = 'busy'; RF.sec = 0; paintRf();
    RF.clock = setInterval(function () { RF.sec++; paintRf(); }, 1000);
    var ok = false;
    try {
      var token = null, sk = null, url = rfUrl();
      try { sk = await fetch(url + '/sitekey', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }); } catch (e) { sk = null; }
      if (sk && sk.sitekey) token = await turnstileToken(sk.sitekey);
      var r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(token ? { token: token } : {}) });
      if (r.status === 429) { ok = true; }
      else {
        if (!r.ok) throw new Error(String(r.status));
        var was = store.cards && isNum(store.cards.built) ? store.cards.built : 0;
        for (var i = 0; i < 60; i++) {
          await sleep(i < 4 ? 15000 : 8000);
          var j = await load.cards(true);
          if (j && isNum(j.built) && j.built > was) break;
        }
        ok = true;
      }
      await Promise.all([load.cards(true), load.wallets(true), load.splits()]);
    } catch (e) { ok = false; }
    clearInterval(RF.clock);
    var w = document.getElementById('sv2-turnstile'); if (w) w.remove();
    if (btn) { delete btn.dataset.busy; btn.disabled = false; }
    RF.state = ok ? 'done' : 'fail'; paintRf();
    setTimeout(function () { RF.state = 'idle'; paintRf(); }, ok ? 10000 : 6000);
    SV2.emit('refresh', ok);
    return ok;
  };

  /* ------------------------------------------------------------------ page mounts: the page files register theirs */
  var mounts = {}, mounted = {};
  /* register('sharps', function (el) { ... }) from sv2-sharps.js; register('following', ...) from sv2-following.js */
  SV2.register = function (name, fn) { mounts[name] = fn; };
  /* the page files may delegate to the stub while they are being built: SV2.mountStub('sharps', el) */
  SV2.mountStub = function (page, el) { return stubMount(page, el); };
  SV2.mountSharps = function (el) { return (mounts.sharps || stubMount.bind(null, 'sharps'))(el); };
  SV2.mountFollowing = function (el) { return (mounts.following || stubMount.bind(null, 'following'))(el); };

  /* Foundation stub shown until a page file registers its own mount. It reads the real data so the shell can be checked end to end. */
  function stubMount(page, el) {
    var stubSport = 'all';
    function paint() {
      var c = store.cards, w = store.wallets, html = '';
      if (page === 'sharps') {
        if (!c) { el.innerHTML = store.state.cards === 'loading' ? ui.skel(3, 'Loading plays') : '<p class="sv2-err">Could not load the plays. <button type="button" class="sv2-link" data-sv2-retry>Try again</button></p>'; return; }
        var plays = [], counts = { clear: 0, mixed: 0, thin: 0, contested: 0 };
        (c.games || []).forEach(function (g) {
          Object.keys(g.markets || {}).forEach(function (mk) {
            var t = rules.tierOf(g, mk);
            if (t !== 'none') { plays.push({ g: g, mk: mk, t: t }); counts[t]++; }
          });
        });
        html += '<h2 class="sv2-h2">Foundation check</h2><p class="sv2-empty-line">' + esc(fmt.n(plays.length) + ' plays shown from ' + fmt.n((c.games || []).length) + ' games. Clear ' + counts.clear + ', Mixed ' + counts.mixed + ', Thin ' + counts.thin + ', Contested ' + counts.contested + '.') + '</p><ul class="sv2-stub-list">';
        plays.slice(0, 5).forEach(function (p) {
          var sf = p.g.markets[p.mk].sf.all, v = p.g.vault || {};
          html += '<li class="sv2-card sv2-stub-row" style="display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;margin-bottom:10px">' +
            ui.playPill(rules.shownUnits(p.g, p.mk)) + '<span><b>' + esc(sf.side) + '</b> <span class="sv2-mut">' + esc(p.mk) + '</span></span>' +
            '<span class="sv2-mut">' + esc((v.away || '') + ' at ' + (v.home || '')) + '</span>' + '<span class="sv2-num">' + esc(fmt.cents(sf.price) || '') + '</span>' + ui.tier(p.t) + '</li>';
        });
        html += '</ul><p class="sv2-faint" style="font-size:13px">Placeholder: sv2-sharps.js replaces this view.</p>';
      } else {
        if (!w) { el.innerHTML = store.state.wallets === 'loading' ? ui.skel(3, 'Loading wallets') : '<p class="sv2-err">Could not load the wallet list. <button type="button" class="sv2-link" data-sv2-retry>Try again</button></p>'; return; }
        var sports = Object.keys(w.sports || {}), nrows = 0, rows = [];
        sports.forEach(function (sp) { Object.keys(w.sports[sp]).forEach(function (a) { nrows++; if (stubSport === 'all' || stubSport === sp) rows.push({ sp: sp, w: a, r: w.sports[sp][a] }); }); });
        rows.sort(function (a, b) { return copy.acctOrder.indexOf(rules.v2TierOf(a.r, a.sp)) - copy.acctOrder.indexOf(rules.v2TierOf(b.r, b.sp)) || (b.r.rk && b.r.rk.mean || -9) - (a.r.rk && a.r.rk.mean || -9); });
        html += '<h2 class="sv2-h2">Foundation check</h2><p class="sv2-empty-line">' + esc(fmt.n(nrows) + ' wallets across ' + sports.map(sportName).join(', ') + '. ' + follows.list().length + ' followed.') + '</p>' +
          seg.html({ id: 'stub-sport', label: 'Sport', value: stubSport, size: 'sm', scroll: true, items: [{ v: 'all', label: 'All' }].concat(sports.map(function (s) { return { v: s, label: sportName(s) }; })) }) +
          '<ul style="margin-top:10px">';
        rows.slice(0, 6).forEach(function (x) {
          var name = rules.nameOf(x.r, x.w);
          html += '<li class="sv2-card" style="display:flex;align-items:center;gap:8px;margin-bottom:8px;padding:6px 12px 6px 6px">' + ui.star(x.sp, x.w, name) +
            '<div style="min-width:0;flex:1"><div class="sv2-ell" data-sv2-name><b>' + esc(name) + '</b></div><div class="sv2-mut" style="font-size:13px">' + esc(sportName(x.sp)) + '</div></div>' +
            ui.acct(rules.v2TierOf(x.r, x.sp), { n: x.r.rk && x.r.rk.n }) + '</li>';
        });
        html += '</ul><p class="sv2-faint" style="font-size:13px">Placeholder: sv2-following.js replaces this view.</p>';
      }
      el.innerHTML = html;
      rail.scan(el);
      var strip = $('.sv2-seg', el);
      if (strip && page === 'following') seg.bind(strip, function (v) { stubSport = v; paint(); });
    }
    paint();
    SV2.on('cards', paint); SV2.on('wallets', paint); SV2.on('follows', function () { if (page === 'following') paint(); });
  }

  /* ------------------------------------------------------------------ boot: shell wiring (browser only) */
  function paintFresh() { SV2.fresh(document.getElementById('sv2-fresh')); }
  function paintGuard() {
    var el = document.getElementById('sv2-guard'); if (!el) return;
    var bad = store.cards && !SV2.sizesOk();
    el.hidden = !bad; el.textContent = bad ? copy.guard : '';
  }
  function paintInfo(page) {
    var el = document.getElementById('sv2-info'); if (!el) return;
    el.innerHTML = '<h2 class="sv2-h2">' + esc(copy.info.title) + '</h2><ul>' + copy.info[page].map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('') + '</ul>';
  }
  function setInfo(open) {
    var hd = document.getElementById('sv2-hd'), btn = document.getElementById('sv2-info-btn'), panel = document.getElementById('sv2-info');
    if (!hd || !btn || !panel) return;
    hd.setAttribute('data-info', open ? 'open' : 'closed'); btn.setAttribute('aria-expanded', String(open)); panel.hidden = !open;
  }
  function setMenu(open) {
    var m = document.getElementById('sv2-menu'), b = document.getElementById('sv2-menu-btn');
    if (!m || !b) return;
    m.hidden = !open; b.setAttribute('aria-expanded', String(open));
    if (open) { rail.scan(m); rail.catchUp(); var f = m.querySelector('button'); if (f) f.focus({ preventScroll: true }); }
  }
  function applyRoute(initial) {
    var r = SV2.route();
    PAGES.forEach(function (p) {
      var el = document.getElementById('sv2-page-' + p); if (el) el.hidden = p !== r.page;
    });
    var el = document.getElementById('sv2-page-' + r.page);
    if (el && !mounted[r.page]) {
      mounted[r.page] = true;
      try { r.page === 'sharps' ? SV2.mountSharps(el) : SV2.mountFollowing(el); } catch (e) { if (root.console) console.error('SV2 mount', r.page, e); }
      rail.scan(el);
    }
    var h1 = document.getElementById('sv2-title'); if (h1) h1.textContent = copy.title[r.page];
    document.title = copy.title[r.page] + ' | Vault Fantasy';
    $$('#sv2-routes a, #sv2-tabs a').forEach(function (a) {
      var on = a.getAttribute('data-route') === r.page;
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    var ctx = document.getElementById('sv2-context'); if (ctx) ctx.textContent = copy.context[r.page];
    paintInfo(r.page); paintFresh(); paintGuard();
    /* the sheet follows the route: Back closes it first */
    if (sheet.isOpen() && sheet.route() && (r.page + (r.sub.length ? '/' + r.sub.join('/') : '')) !== sheet.route().replace(/^#\/?/, '')) sheet.close(true);
    rail.catchUp();
    return r;
  }

  var mainObs = null;
  function observeMain() {
    if (typeof MutationObserver === 'undefined') return;
    var m = document.getElementById('sv2-main'); if (!m) return;
    if (mainObs) mainObs.disconnect();
    mainObs = new MutationObserver(function () { rail.scan(document); }); mainObs.observe(m, { childList: true, subtree: true });
  }
  /* boot() starts the standalone page; boot('sharps' | 'following') mounts one page inside a host (embed.js), as often as the host re-renders the tab */
  function boot(embedPage) {
    if (!document.getElementById('sv2-main')) return;
    var embedded = typeof embedPage === 'string';
    if (embedded) { EH = '#' + embedPage; mounted = {}; }
    /* nav + theme + skin state */
    var themeStrip = document.getElementById('sv2-theme-seg'), skinStrip = document.getElementById('sv2-skin-seg');
    if (themeStrip) { seg.set(themeStrip, SV2.theme.get() || 'system'); seg.bind(themeStrip, function (v) { SV2.theme.set(v); }); }
    if (skinStrip) { seg.set(skinStrip, SV2.skin.get()); seg.bind(skinStrip, function (v) { SV2.skin.set(v); }); }
    rail.scan(document);

    var lastPage = null;
    function onRoute() {
      var r = applyRoute();
      if (lastPage && lastPage !== r.page) { root.scrollTo(0, 0); var m = document.getElementById('sv2-main'); if (m) m.focus({ preventScroll: true }); }
      lastPage = r.page;
      SV2.emit('route', r);
    }
    if (!embedded) root.addEventListener('hashchange', onRoute);
    SV2._route = onRoute;
    applyRoute(true); lastPage = SV2.route().page;
    if (SV2.wired) { observeMain(); load.cards(); load.wallets(); load.splits(); return; }   /* a later mount: the document level wiring below is already in place */
    SV2.wired = true;


    document.addEventListener('click', function (e) {
      var t = e.target; if (!t.closest) return;
      /* follow star: one handler for every star on every page */
      var star = t.closest('[data-sv2-star]');
      if (star) {
        var sp = star.getAttribute('data-sport'), w = star.getAttribute('data-w'), name = star.getAttribute('data-name');
        var on = follows.toggle(sp, w);
        $$('[data-sv2-star]').forEach(function (b) {
          if (b.getAttribute('data-sport') === sp && b.getAttribute('data-w') === w) {
            b.setAttribute('aria-pressed', String(on));
            b.setAttribute('aria-label', on ? copy.star.on(b.getAttribute('data-name') || name, sp) : copy.star.off(b.getAttribute('data-name') || name, sp));
          }
        });
        star.classList.remove('sv2-star-pop'); void star.offsetWidth; if (on) star.classList.add('sv2-star-pop');
        return;
      }
      if (t.closest('[data-sv2-retry]')) { load.cards(true); load.wallets(true); load.splits(); return; }
      var menuBtn = t.closest('#sv2-menu-btn');
      if (menuBtn) { setMenu(document.getElementById('sv2-menu').hidden); return; }
      if (!t.closest('#sv2-menu')) { var mm = document.getElementById('sv2-menu'); if (mm && !mm.hidden) setMenu(false); }
      if (t.closest('#sv2-info-btn')) { setInfo(document.getElementById('sv2-hd').getAttribute('data-info') !== 'open'); return; }
      if (t.closest('#sv2-refresh')) { SV2.refresh(); return; }
      /* trap 5: a delegated click re-places every strip after the page has changed */
      setTimeout(rail.catchUp, 0);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        var mm = document.getElementById('sv2-menu');
        if (mm && !mm.hidden) { setMenu(false); var b = document.getElementById('sv2-menu-btn'); if (b) b.focus(); }
      }
    });
    root.addEventListener('resize', rail.catchUp);
    root.addEventListener('storage', function (e) { if (e.key === FKEY) SV2.emit('follows', null); });
    SV2.on('follows', function () {
      $$('[data-sv2-star]').forEach(function (b) {
        var on = follows.has(b.getAttribute('data-sport'), b.getAttribute('data-w'));
        b.setAttribute('aria-pressed', String(on));
      });
    });
    SV2.on('cards', function () { paintFresh(); paintGuard(); });
    SV2.on('wallets', paintFresh);
    SV2.on('theme', function () { setTimeout(rail.catchUp, 0); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(rail.catchUp);   /* trap 5: a webfont swap widens the text after first paint */

    /* document-level observer wires any strip a page renders later (microtask based, fires without painting) */
    observeMain();

    /* data: cards first (the Sharps route), wallets and splits beside it */
    load.cards(); load.wallets(); load.splits();

    /* clock tick every 30 s: freshness line and countdown text (no animation) */
    setInterval(function () { paintFresh(); SV2.emit('tick', SV2.now()); }, 30000);
    /* automatic reload every 2 minutes while the page is visible; catch up when it becomes visible again */
    setInterval(function () { if (!document.hidden) { load.cards(); load.wallets(); } }, 120000);
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) return;
      var stale = Date.now() - Math.min(store.loadedAt.cards || 0, store.loadedAt.wallets || 0) > 120000;
      if (stale) { load.cards(); load.wallets(); }
      paintFresh();
    });
    SV2.booted = true;
  }
  SV2.boot = boot;

  root.SV2 = SV2;
  if (typeof module !== 'undefined' && module.exports) module.exports = SV2;
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else setTimeout(boot, 0);
  }
})();
