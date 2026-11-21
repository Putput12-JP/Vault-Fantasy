/* Sharps V2, route #following. Owned by the Following page agent.
   Core (sv2-core.js) calls the registered mount once, the first time #following is shown, with the empty
   <section id="sv2-page-following"> element.

   Sharp money is context only: nothing here is a bet signal, a size, a pick or an input to Top Reads, SM_GATE or any total.
   There is no size on this page at all. Every number is a stored field (wallets.json, live.json) or arithmetic on stored fields;
   a missing field is omitted or labelled, never turned into a zero. All times Central. No em dashes, no text-glyph icons.

   What it shows (spec docs/sharps-v2-spec.md section 4.3 to 4.5):
     Next up      open bets of followed wallets on games that have not reached their cut, by game start, summed per side
     Rail         who you follow, and one honest "Since you followed" tally (desktop rail, folded on phones)
     Not on list  followed wallets that dropped out of wallets.json (retained rows when the file carries them)
     Wallets      directory: search, four visible columns, a sort key that is one of them, minimum samples, paging
     Account sheet  slim: record (forward first), this bet, who else holds the game

   Follows: localStorage "vault-sharps-following" {"sport|wallet": epoch seconds}, the exact shape following.js v13 writes.
   Core owns the store and the star button; this file only reads it and listens to the "follows" event.
   Optional wallets.json fields are used only when the file's v2_fields names them (spec 5.3). */
(function () {
  'use strict';
  var root = typeof window !== 'undefined' ? window : globalThis;
  var SV2 = root.SV2;
  if (!SV2) return;
  var esc = SV2.esc, fmt = SV2.fmt, ct = SV2.ct, rules = SV2.rules, ui = SV2.ui, copy = SV2.copy, seg = SV2.seg,
    follows = SV2.follows, store = SV2.store, isNum = SV2.isNum, sportName = SV2.sportName;

  var MKT = { ml: 'Moneyline', spread: 'Spread', total: 'Total' };
  var MKT_ORDER = { ml: 0, spread: 1, total: 2 };
  var SPORT_ORDER = ['nfl', 'cfb', 'nba', 'cbb'];
  var TIERED = { nba: 1, nfl: 1 };
  var TIER_RANK = { beats: 0, even: 1, few: 2, loses: 3 };
  var PAGE = 24;            /* directory rows per page (spec 4.4) */
  var CUT_SECS = 900;       /* a game's cut is T-15, the same rule the builder uses to drop a position from the file */
  var MIN_FWD = 20;         /* Since tracked sort: rows below this many forward bets sort after the rest */
  var SMALL = 30;           /* any record under n = 30 carries "small sample" (spec 6) */
  var SMALL_CUT = 20;       /* a cut tile under n = 20 carries "small sample" (spec 4.5) */
  var MIN_GAMES = 20;       /* the "20+ games" directory filter */
  var DAY = 86400;
  var COLLEGE = 'No price tier in college: no tested closing-price model there.';
  /* entry-price bands for the "at these odds" cut: the same cut points as ODDS_BANDS in scripts/build_side_cards.py */
  var ODDS = [['dd', '+200 or longer', 0, 1 / 3], ['d2', '+150 to +199', 1 / 3, 0.4], ['d1', '+100 to +149', 0.4, 0.5],
    ['f1', '-100 to -149', 0.5, 0.6], ['f2', '-150 to -199', 0.6, 2 / 3], ['ff', '-200 or shorter', 2 / 3, 1.01]];

  /* ------------------------------------------------------------------ pure helpers (exposed on SV2.fw for the node tests) */
  function cmpStr(a, b) { return a < b ? -1 : a > b ? 1 : 0; }
  /* nulls last, larger first */
  function numDesc(x, y) {
    var xn = isNum(x), yn = isNum(y);
    if (xn && yn) return y - x;
    return xn ? -1 : yn ? 1 : 0;
  }
  /* does the file declare an optional field? spec 5.3: the page checks v2_fields before using any added key */
  function declared(file, key) {
    var f = file && file.v2_fields;
    if (!f) return false;
    if (Array.isArray(f)) return f.indexOf(key) >= 0;
    return new RegExp('(^|[^A-Za-z0-9_.])' + String(key).replace(/\./g, '\\.') + '(?![A-Za-z0-9_])').test(String(f));
  }
  /* "19 min", "16 h", "5 d" from minutes */
  function ageText(min) {
    if (!isNum(min)) return null;
    if (min < 1) return '<1 min';
    if (min < 60) return Math.round(min) + ' min';
    if (min < 1440) return Math.floor(min / 60) + ' h';
    return Math.floor(min / 1440) + ' d';
  }
  /* minutes since the shown price was logged: the stored px_age_min, else built - px_t (both as of the build). With nowT the minutes
     the file has aged since the build are added, so "price 4 min old" is true now and not only at 10:21 AM. null when no time is stored. */
  function pxAgeMin(file, p, nowT) {
    var base = null;
    if (declared(file, 'px_age_min') && isNum(p.px_age_min)) base = p.px_age_min;
    else if (isNum(p.px_t) && file && isNum(file.built)) base = Math.round((file.built - p.px_t) / 60);
    if (base == null) return null;
    if (isNum(nowT) && file && isNum(file.built) && nowT > file.built) base += Math.round((nowT - file.built) / 60);
    return base;
  }
  /* the stored qualifying rule (file note: sport book n >= 6, win rate >= 55%, dollar ROI > 3%); the file carries the rule, not a flag */
  function pastWinner(r) {
    return !!r && isNum(r.n) && r.n >= 6 && isNum(r.w_) && r.w_ / r.n >= 0.55 && isNum(r.roi) && r.roi > 0.03;
  }
  function oddsBand(px) {
    if (!isNum(px)) return null;
    for (var i = 0; i < ODDS.length; i++) if (px >= ODDS[i][2] && px < ODDS[i][3]) return ODDS[i];
    return null;
  }
  /* size bands vs the wallet's usual stake: the builder's SIZE_BANDS 0.75 and 1.5 */
  function sizeBand(x) { return !isNum(x) ? null : x < 0.75 ? 'small' : x < 1.5 ? 'usual' : 'big'; }
  var SIZE_LBL = { small: 'Under its usual stake', usual: 'Around its usual stake', big: '1.5x its usual or more' };

  /* index one wallets.json row into what the page needs. file is the wallets file (for the declared-field checks). */
  function mkRow(file, sp, w, r, ret) {
    var built = file && file.built;
    var d = function (k) { return declared(file, k); };
    var row = { k: sp + '|' + w, sp: sp, w: w, r: r || {}, ret: !!ret };
    r = row.r;
    row.name = rules.nameOf(r, w);
    row.tier = rules.v2TierOf(r, sp);
    row.rk = r.rk || null;
    row.rkn = row.rk && isNum(row.rk.n) ? row.rk.n : 0;
    row.n = isNum(r.n) ? r.n : null;
    /* closing-line value in price units: the shrunk estimate when published, else the raw average (labelled raw) */
    row.cents = null;
    if (row.tier !== 'few' && row.rk) {
      if (d('rk.post') && isNum(row.rk.post)) row.cents = { v: row.rk.post, raw: false };
      else if (isNum(row.rk.mean)) row.cents = { v: row.rk.mean, raw: true };
    }
    row.fwdPub = d('fwd');
    row.fwd = row.fwdPub && r.fwd && typeof r.fwd === 'object' ? r.fwd : null;
    row.flat = d('flat_roi') && isNum(r.flat_roi) ? r.flat_roi : null;
    row.first = d('first_seen') && isNum(r.first_seen) ? r.first_seen : null;
    var leg0 = Array.isArray(r.legs) && r.legs[0] && isNum(r.legs[0][0]) ? r.legs[0][0] : null;
    row.last = d('last_settled') && isNum(r.last_settled) ? r.last_settled : leg0;
    row.n30 = d('n30_games') && isNum(r.n30_games) ? r.n30_games : null;
    if (row.n30 != null) row.inactive = row.n30 === 0;
    else if (Array.isArray(r.legs)) row.inactive = leg0 == null || !isNum(built) || leg0 < built - 30 * DAY;
    else row.inactive = false;
    row.sc = d('sc_sport') && r.sc_sport === true;
    row.scn = d('sc_n') && isNum(r.sc_n) ? r.sc_n : null;
    row.past = !ret && pastWinner(r);
    row.expW = d('exp_w') && isNum(r.exp_w) ? r.exp_w : (r.dive && isNum(r.dive.exp_w) ? r.dive.exp_w : null);
    row.luck = d('luck_p') && isNum(r.luck_p) ? r.luck_p : (r.dive && r.dive.all && isNum(r.dive.all[5]) ? r.dive.all[5] : null);
    row.sinceInline = d('since_list') && Array.isArray(r.since_list) ? r.since_list : null;   /* older files carried the list inline */
    return row;
  }

  /* a wallet's open positions grouped per side, dropping games already past their cut (the file only lists games before it) */
  function liveGroups(file, row, now) {
    var d = declared(file, 'side_usd');
    return rules.groupSides(row.r.positions || []).filter(function (g) { return !isNum(g.gst) || g.gst - CUT_SECS > now; }).map(function (g) {
      var t = rules.sideTotals(g.positions);
      g.total = d && isNum(t.stored_usd) ? t.stored_usd : t.usd;
      g.sideX = declared(file, 'side_press') ? t.press : null;
      return g;
    });
  }
  function betKey(g) { return [g.ev, g.gst, g.g, g.side].join('|'); }
  /* "nfl-tb-det-2026-11-22" (away, then home) to "TB at DET" */
  function teamsOf(ev) {
    var m = /^[a-z]+-([a-z0-9]+)-([a-z0-9]+)-\d{4}/.exec(ev || '');
    return m ? m[1].toUpperCase() + ' at ' + m[2].toUpperCase() : String(ev || '');
  }
  function lineText(g) {
    var p = g.positions[0] || {};
    if (!isNum(p.line)) return '';
    return g.g === 'spread' ? fmt.line(p.line, { signed: true }) : g.g === 'total' ? fmt.line(p.line) : '';
  }

  /* the Next up feed. fl: follows list; idx: {k: row}; sportFilter 'all' or a sport. Games by start, day-grouped by the caller. */
  function buildFeed(file, fl, idx, now, sportFilter) {
    var games = {}, order = [], nBets = 0, hidden = 0;
    fl.forEach(function (f) {
      var row = idx[f.sport + '|' + f.w]; if (!row) return;
      liveGroups(file, row, now).forEach(function (g) {
        if (sportFilter && sportFilter !== 'all' && f.sport !== sportFilter) { hidden++; return; }
        nBets++;
        var id = g.ev + '|' + g.gst, gm = games[id];
        if (!gm) { gm = games[id] = { id: id, ev: g.ev, gst: g.gst, sport: f.sport, bets: [] }; order.push(gm); }
        gm.bets.push({ row: row, g: g });
      });
    });
    var sameGames = 0, nextCut = null;
    order.sort(function (a, b) { return numAsc(a.gst, b.gst) || cmpStr(a.ev, b.ev); });
    order.forEach(function (gm) {
      gm.bets.sort(function (a, b) {
        return (MKT_ORDER[a.g.g] - MKT_ORDER[b.g.g]) || cmpStr(a.g.side, b.g.side) || numDesc(a.g.total, b.g.total) || cmpStr(a.row.k, b.row.k);
      });
      var by = {};
      gm.bets.forEach(function (b) { var k = b.g.g + '|' + b.g.side; (by[k] = by[k] || {})[b.row.k] = 1; });
      gm.same = [];
      Object.keys(by).forEach(function (k) {
        var n = Object.keys(by[k]).length;
        if (n >= 2) { var i = k.indexOf('|'); gm.same.push({ g: k.slice(0, i), side: k.slice(i + 1), n: n }); }
      });
      if (gm.same.length) sameGames++;
      if (isNum(gm.gst)) { var c = gm.gst - CUT_SECS; if (nextCut == null || c < nextCut) nextCut = c; }
    });
    return { games: order, nBets: nBets, hidden: hidden, sameGames: sameGames, nextCut: nextCut };
  }
  function numAsc(x, y) { var xn = isNum(x), yn = isNum(y); if (xn && yn) return x - y; return xn ? -1 : yn ? 1 : 0; }

  /* directory sorts. Every key is a visible column (spec 4.4). */
  function cmpName(a, b) { return cmpStr(a.name.toLowerCase(), b.name.toLowerCase()) || cmpStr(a.k, b.k); }
  function cmpAct(a, b) { return numDesc(a.n30, b.n30) || numDesc(a.last, b.last); }
  var SORTS = {
    /* tier order beats, even, few, loses (loses sort last); inside a tier by the cents shown; "few" has no cents, so by games then activity */
    price: function (a, b) {
      var d = TIER_RANK[a.tier] - TIER_RANK[b.tier]; if (d) return d;
      if (a.tier === 'few') d = numDesc(a.rkn || null, b.rkn || null);
      else d = numDesc(a.cents && a.cents.v, b.cents && b.cents.v);
      return d || cmpAct(a, b) || cmpName(a, b);
    },
    /* forward flat ROI, only rows with 20+ forward bets lead; the rest follow by how many bets they have */
    fwd: function (a, b) {
      var qa = !!(a.fwd && a.fwd.n >= MIN_FWD), qb = !!(b.fwd && b.fwd.n >= MIN_FWD);
      if (qa !== qb) return qa ? -1 : 1;
      var d = qa ? numDesc(a.fwd.flat_roi, b.fwd.flat_roi) : 0;
      return d || numDesc(a.fwd && a.fwd.n, b.fwd && b.fwd.n) || cmpAct(a, b) || cmpName(a, b);
    },
    act: function (a, b) { return cmpAct(a, b) || cmpName(a, b); },
    open: function (a, b) { return numDesc(a._usd, b._usd) || numDesc(a._n, b._n) || cmpAct(a, b) || cmpName(a, b); }
  };
  function sortRows(rows, key) { return rows.slice().sort(SORTS[key] || SORTS.price); }
  /* search: a name fragment, or an address fragment (4+ hex characters, with or without 0x). Case-insensitive. */
  function matches(row, q) {
    q = String(q || '').trim().toLowerCase();
    if (!q) return true;
    if (row.name.toLowerCase().indexOf(q) >= 0) return true;
    var raw = (row.r && typeof row.r.name === 'string') ? row.r.name.toLowerCase() : '';
    if (raw && raw.indexOf(q) >= 0) return true;
    var hex = q.replace(/^0x/, '');
    return /^[0-9a-f]{4,}$/.test(hex) && row.w.toLowerCase().indexOf(hex) >= 0;
  }
  function defaultSort(sport) { return sport === 'cfb' || sport === 'cbb' ? 'act' : 'price'; }

  /* five cuts around a bet, or the market and side cuts when there is no bet. cell = [w, l, roi, ...] from dive. */
  function cutsOf(row, grp) {
    var dv = row.r.dive || {}, usual = row.r.usual, out = [];
    out.push({ key: 'all', title: sportName(row.sp), sub: 'All bets', cell: [row.r.w_, row.r.l_, row.r.roi], match: function () { return true; } });
    function lane(g) { return { key: 'mkt-' + g, title: sportName(row.sp) + ' ' + MKT[g], sub: 'This bet type', cell: (dv.lane || {})[g], match: function (c) { return c[3] === g; } }; }
    function side(fav) { return { key: fav ? 'fav' : 'dog', title: fav ? 'Favorites' : 'Underdogs', sub: fav ? 'Priced at 50c or more' : 'Priced under 50c', cell: fav ? dv.fav : dv.dog, match: function (c) { return isNum(c[4]) && (c[4] >= 0.5) === fav; } }; }
    if (grp) {
      var px = grp.positions[0] && grp.positions[0].px, fav = isNum(px) ? px >= 0.5 : null;
      out.push(lane(grp.g));
      if (fav != null) { var s = side(fav); s.sub = (fav ? 'Favorite' : 'Underdog') + ' at ' + fmt.cents(px); out.push(s); }
      var sb = isNum(usual) && usual > 0 && isNum(grp.total) ? sizeBand(grp.total / usual) : null;
      if (sb) out.push({ key: 'size', title: 'At this size', sub: SIZE_LBL[sb], cell: (dv.size || {})[sb], match: function (c) { return isNum(usual) && usual > 0 && c[2] > 0 && sizeBand(c[2] / usual) === sb; } });
      var ob = oddsBand(px);
      if (ob) out.push({ key: 'odds', title: 'At these odds', sub: ob[1], cell: (row.r.odds || {})[ob[0]], match: function (c) { var b = oddsBand(c[4]); return !!(b && b[0] === ob[0]); } });
    } else {
      ['ml', 'spread', 'total'].forEach(function (g) { out.push(lane(g)); });
      out.push(side(true)); out.push(side(false));
    }
    return out;
  }

  /* ------------------------------------------------------------------ state */
  var S = {
    el: null, built: null, idx: {}, rows: [], ret: {},
    sport: 'all', sort: 'price', sortUser: false, q: '', min20: false, inactive: false, shown: PAGE,
    openRungs: {}, railOpen: false, sh: null, opener: null, lastOpened: null, pendingRoute: null, nextCut: null, mounted: false
  };
  function now() { return SV2.now(); }
  function file() { return store.wallets; }
  function dot() { return '<span class="sv2-fw-dot" aria-hidden="true"></span>'; }
  function nm(name, cls) { return '<span class="sv2-fw-nm ' + (cls || '') + '" data-sv2-name>' + esc(name) + '</span>'; }
  function small(n, lim) { return n != null && n < (lim || SMALL) ? ' <span class="sv2-fw-small">small sample</span>' : ''; }
  function roiHtml(x, suffix) {
    if (!isNum(x)) return '';
    return '<span class="sv2-num ' + (x > 0 ? 'sv2-win' : x < 0 ? 'sv2-loss' : '') + '">' + fmt.pct(x, { signed: true }) + (suffix || '') + '</span>';
  }

  function index() {
    var f = file(); S.idx = {}; S.rows = []; S.ret = {};
    if (!f || !f.sports) return;
    Object.keys(f.sports).forEach(function (sp) {
      var ws = f.sports[sp] || {};
      Object.keys(ws).forEach(function (w) { var row = mkRow(f, sp, w, ws[w], false); S.idx[row.k] = row; S.rows.push(row); });
    });
    if (declared(f, 'retained') && f.retained && typeof f.retained === 'object') {
      Object.keys(f.retained).forEach(function (sp) {
        var ws = f.retained[sp] || {};
        Object.keys(ws).forEach(function (w) { S.ret[sp + '|' + w] = mkRow(f, sp, w, ws[w], true); });
      });
    }
    /* the same address in more than one sport is one row per sport (follows are per sport); each row says where else it is listed */
    var by = {};
    S.rows.forEach(function (r) { (by[r.w] = by[r.w] || []).push(r.sp); });
    S.rows.forEach(function (r) { r.also = by[r.w].filter(function (x) { return x !== r.sp; }); });
    S.built = f.built;
  }
  function sportsPresent() {
    var f = file(), have = f && f.sports ? Object.keys(f.sports).filter(function (s) { return Object.keys(f.sports[s] || {}).length; }) : [];
    return SPORT_ORDER.filter(function (s) { return have.indexOf(s) >= 0; }).concat(have.filter(function (s) { return SPORT_ORDER.indexOf(s) < 0; }));
  }

  /* ------------------------------------------------------------------ small renderers */
  function tierWord(row) {
    return '<span class="sv2-fw-tw' + (row.tier === 'beats' ? ' is-beats' : '') + '" data-acct="' + row.tier + '">' + esc(copy.acct[row.tier].word) + '</span>';
  }
  function centsCell(row) {
    var c = row.cents; if (!c) return '';
    var s = fmt.centsSigned(c.v); if (s == null) return '';
    return '<span class="sv2-num"' + (c.raw ? ' title="raw average, not shrunk"' : '') + '>' + s + '</span>' + (c.raw ? ' <span class="sv2-fw-raw">raw</span>' : '');
  }
  function priceCell(row) {
    var l2 = [];
    var c = centsCell(row); if (c) l2.push(c);
    if (row.tier !== 'few' && row.rkn) l2.push('<span class="sv2-num">' + fmt.n(row.rkn) + '</span> games');
    else if (row.tier === 'few' && row.rkn) l2.push('<span class="sv2-num">' + fmt.n(row.rkn) + '</span> closes');
    return '<span class="sv2-fw-cell"><span class="sv2-fw-c1">' + tierWord(row) + '</span>' + (l2.length ? '<span class="sv2-fw-c2">' + l2.join(dot()) + '</span>' : '') + '</span>';
  }
  function fwdInner(row) {
    if (!row.fwdPub) return { a: '<span class="sv2-fw-mut">' + esc('Not published yet') + '</span>', b: '' };
    if (!row.fwd) return { a: '<span class="sv2-fw-mut">No bets yet</span>', b: '' };
    var f = row.fwd, wl = fmt.wl(f.w, f.l, f.p);
    if (!isNum(f.n) || f.n === 0) return { a: '<span class="sv2-fw-mut">No settled bets yet</span>', b: '' };
    var a = '<span class="sv2-num">' + esc(wl) + '</span>' + (isNum(f.flat_roi) ? ' ' + roiHtml(f.flat_roi, ' flat') : '');
    return { a: a, b: 'n=<span class="sv2-num">' + f.n + '</span>' + small(f.n) };
  }
  function fwdCell(row) {
    var x = fwdInner(row);
    return '<span class="sv2-fw-cell"><span class="sv2-fw-c1">' + x.a + '</span>' + (x.b ? '<span class="sv2-fw-c2">' + x.b + '</span>' : '') + '</span>';
  }
  function actInner(row) {
    if (row.last == null) return { a: '<span class="sv2-fw-mut">No settled bets</span>', b: '' };
    var a = esc(ct.md(row.last));
    if (row.n30 != null) return { a: a, b: '<span class="sv2-num">' + row.n30 + '</span> games in 30 days' };
    return { a: 'Last settled ' + a, b: '' };
  }
  function actCell(row) {
    var x = actInner(row);
    return '<span class="sv2-fw-cell"><span class="sv2-fw-c1">' + x.a + '</span>' + (x.b ? '<span class="sv2-fw-c2">' + x.b + '</span>' : '') + '</span>';
  }
  function openInner(row) {
    if (!row._n) return '<span class="sv2-fw-mut">None</span>';
    return '<span class="sv2-num">' + row._n + '</span>' + dot() + '<span class="sv2-num">' + esc(fmt.usd(row._usd)) + '</span>';
  }
  function openCell(row) { return '<span class="sv2-fw-cell"><span class="sv2-fw-c1">' + openInner(row) + '</span></span>'; }
  function chipsFor(row) {
    var c = [];
    if (row.past) c.push(ui.chip(copy.chip.past, 'muted'));
    if (row.sc) c.push(ui.chip(row.scn != null ? copy.chip.sc(row.sp, row.scn) : 'On the ' + sportName(row.sp) + ' price scorecard', 'muted'));
    if (row.inactive) c.push(ui.chip(copy.chip.inactive, 'muted'));
    return c.join('');
  }
  function alsoNote(row) {
    return S.sport === 'all' && row.also && row.also.length ? '<span class="sv2-fw-also">Also in ' + esc(row.also.map(sportName).join(', ')) + '</span>' : '';
  }
  /* annotate each row with its open count and mark value (live groups only) */
  function annotate(rows, t) {
    var f = file();
    rows.forEach(function (r) {
      var gs = liveGroups(f, r, t); r._n = gs.length;
      var sum = 0, any = false; gs.forEach(function (g) { if (isNum(g.total)) { sum += g.total; any = true; } });
      r._usd = any ? sum : null;
    });
  }

  /* ------------------------------------------------------------------ directory */
  function dirRow(row) {
    var line2 = [];
    line2.push('<span class="sv2-fw-sp">' + esc(sportName(row.sp)) + '</span>');
    line2.push(tierWord(row));
    if (row.cents) line2.push(centsCell(row));
    if (row.rkn && row.tier !== 'few') line2.push('<span class="sv2-num">' + row.rkn + '</span> games');
    if (S.sort === 'fwd') { var x = fwdInner(row); line2.push(x.a + (x.b ? ' ' + x.b : '')); }
    if (S.sort === 'act') { var y = actInner(row); line2.push(y.a + (y.b ? ' ' + y.b : '')); }
    var chips = chipsFor(row);
    return '<li class="sv2-fw-row" data-k="' + esc(row.k) + '">' + ui.star(row.sp, row.w, row.name) +
      '<button type="button" class="sv2-fw-main sv2-press sv2-press-row" data-fw-open="' + esc(row.k) + '" data-fk="open:' + esc(row.k) + '">' +
      '<span class="sv2-fw-who"><span class="sv2-fw-whol1">' + nm(row.name, 'sv2-ell') + '<span class="sv2-fw-sp sv2-fw-sp--d">' + esc(sportName(row.sp)) + '</span>' +
      (row._n ? '<span class="sv2-fw-openpill">' + openInner(row) + '</span>' : '') + '</span>' +
      ((chips || alsoNote(row)) ? '<span class="sv2-fw-chips-l">' + chips + alsoNote(row) + '</span>' : '') + '</span>' +
      '<span class="sv2-fw-cells">' + priceCell(row) + fwdCell(row) + actCell(row) + openCell(row) + '</span>' +
      '<span class="sv2-fw-l2">' + line2.map(function (x) { return '<span>' + x + '</span>'; }).join(dot()) + '</span>' +
      '</button></li>';
  }
  var COLS = [['price', 'Price edge'], ['fwd', 'Since tracked'], ['act', 'Activity'], ['open', 'Open now']];
  function sortStrip() { return document.querySelector('[data-rail-id="fw-sortseg"]'); }
  function sortAvailable(key) { return key !== 'fwd' || S.rows.some(function (r) { return r.fwdPub; }); }
  function paintDir() {
    var list = document.getElementById('fw-list'); if (!list) return;
    var f = file();
    if (!f) return;
    var t = now(), q = S.q.trim(), base = S.rows.filter(function (r) { return S.sport === 'all' || r.sp === S.sport; });
    annotate(base, t);
    var nInactive = base.filter(function (r) { return r.inactive && !follows.has(r.sp, r.w); }).length;
    var rows;
    if (q) rows = base.filter(function (r) { return matches(r, q); });      /* a search ignores the filters: you can find any wallet */
    else rows = base.filter(function (r) {
      if (follows.has(r.sp, r.w)) return true;                              /* a wallet you follow is never hidden */
      if (r.inactive && !S.inactive) return false;
      if (S.min20 && !(r.n >= MIN_GAMES)) return false;
      return true;
    });
    var key = sortAvailable(S.sort) ? S.sort : defaultSort(S.sport);
    rows = sortRows(rows, key);
    var total = rows.length, show = rows.slice(0, S.shown);
    var cnt = document.getElementById('fw-count'); if (cnt) cnt.textContent = fmt.n(base.length);
    var sub = document.getElementById('fw-match'); if (sub) sub.textContent = q ? (total + (total === 1 ? ' match' : ' matches')) : '';
    list.innerHTML = total ? show.map(dirRow).join('') : '<li class="sv2-empty-line">' + (q ? esc('No wallet matches "' + q + '".') : 'No wallets to show with these filters.') + '</li>';
    var more = document.getElementById('fw-more');
    if (more) { more.hidden = total <= show.length; more.textContent = 'Show ' + Math.min(PAGE, total - show.length) + ' more'; }
    var ib = document.getElementById('fw-tog-inactive'); if (ib) { ib.textContent = 'Show inactive (' + fmt.n(nInactive) + ')'; ib.setAttribute('aria-pressed', String(S.inactive)); }
    var mb = document.getElementById('fw-tog-min'); if (mb) mb.setAttribute('aria-pressed', String(S.min20));
    var cn = document.getElementById('fw-college'); if (cn) cn.hidden = !(S.sport === 'cfb' || S.sport === 'cbb');
    $$('#fw-colhead [data-fw-sort]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-fw-sort') === key)); });
    var strip = sortStrip(); if (strip) seg.set(strip, key);
    S.sortKey = key;
    var live = document.getElementById('sv2-live'); if (live && q) live.textContent = total + (total === 1 ? ' wallet matches' : ' wallets match');
  }
  function $$(sel, el) { return SV2.$$(sel, el); }
  function $(sel, el) { return SV2.$(sel, el); }

  /* ------------------------------------------------------------------ feed, rail, tombstones */
  function betRow(b, gm) {
    var g = b.g, row = b.row, f = file(), key = betKey(g), line = lineText(g);
    var oldest = null;
    g.positions.forEach(function (p) { var a = pxAgeMin(f, p, now()); if (a != null && (oldest == null || a > oldest)) oldest = a; });
    var parts = [nm(row.name, 'sv2-ell')];
    var x = null;
    if (g.sideX != null) x = '<span class="sv2-num">' + fmt.mult(g.sideX) + '</span> median cost';
    else if (g.positions.length === 1 && isNum(g.positions[0].press)) x = '<span class="sv2-num">' + fmt.mult(g.positions[0].press) + '</span> average cost (this position)';
    if (x) parts.push(x);
    parts.push(oldest != null ? 'price ' + esc(ageText(oldest)) + ' old' : 'price time not stored');
    if (g.positions.some(function (p) { return p.two_way; })) parts.push('Also holds the other side');
    var open = !!S.openRungs[row.k + '|' + key], uid = 'fw-r-' + (gm.id + '|' + row.k + '|' + g.g + '|' + g.side).replace(/[^A-Za-z0-9]/g, '');
    var html = '<li class="sv2-fw-bet-w"><button type="button" class="sv2-fw-bet sv2-press sv2-press-row" data-fw-bet="' + esc(key) + '" data-sp="' + esc(row.sp) + '" data-w="' + esc(row.w) + '" data-fk="bet:' + esc(row.k + '|' + key) + '">' +
      '<span class="sv2-fw-b1"><span class="sv2-fw-mk">' + esc(MKT[g.g] || g.g) + '</span><b class="sv2-fw-side">' + esc(g.side) + (line ? ' <span class="sv2-num">' + esc(line) + '</span>' : '') + '</b>' +
      '<span class="sv2-fw-amt sv2-num">' + esc(fmt.usd(g.total) || '') + '</span></span>' +
      '<span class="sv2-fw-b2">' + parts.map(function (x) { return '<span>' + x + '</span>'; }).join(dot()) + '</span>' +
      ui.icon('chevron', 'sv2-fw-go') + '</button>';
    if (g.positions.length > 1) {
      html += '<button type="button" class="sv2-fw-rt" data-fw-rungs="' + esc(row.k + '|' + key) + '" aria-expanded="' + open + '" aria-controls="' + uid + '" data-fk="rt:' + esc(row.k + '|' + key) + '"><span class="sv2-num">' + g.positions.length + '</span> positions' + ui.icon('chevron', 'sv2-chev') + '</button>' +
        '<div class="sv2-x" id="' + uid + '"' + (open ? ' data-open' : '') + '><div class="sv2-x-in"><ul class="sv2-fw-rungs">' + g.positions.map(function (p) { return rungItem(f, g, p); }).join('') + '</ul></div></div>';
    }
    return html + '</li>';
  }
  function rungItem(f, g, p) {
    var bits = [];
    var l = g.g === 'spread' ? fmt.line(p.line, { signed: true }) : g.g === 'total' ? fmt.line(p.line) : null;
    if (l) bits.push(esc(MKT[g.g]) + ' <span class="sv2-num">' + esc(l) + '</span>');
    bits.push('<b class="sv2-num">' + esc(fmt.usd(p.usd) || '') + '</b>');
    if (isNum(p.px)) bits.push('at <span class="sv2-num">' + esc(fmt.cents(p.px)) + '</span>');
    if (isNum(p.press)) bits.push('<span class="sv2-num">' + fmt.mult(p.press) + '</span> average cost (this position)');
    var a = pxAgeMin(f, p, now());
    bits.push(a != null ? 'price ' + esc(ageText(a)) + ' old' : 'price time not stored');
    return '<li>' + bits.join(dot()) + '</li>';
  }
  function gameCard(gm) {
    var head = '<header class="sv2-fw-gh"><span class="sv2-chip sv2-chip--muted">' + esc(sportName(gm.sport)) + '</span><b class="sv2-fw-gt">' + esc(teamsOf(gm.ev)) + '</b>' +
      (isNum(gm.gst) ? '<span class="sv2-fw-gtime sv2-num">' + esc(ct.time(gm.gst, true)) + '</span>' : '') + '</header>';
    var same = gm.same.map(function (s) { return '<p class="sv2-fw-same">' + s.n + ' wallets you follow are on <b>' + esc(s.side) + '</b>' + (s.g === 'ml' ? '' : ' (' + esc(MKT[s.g] || s.g) + ')') + '</p>'; }).join('');
    return '<article class="sv2-card sv2-fw-game" aria-label="' + esc(teamsOf(gm.ev)) + '">' + head + same + '<ul class="sv2-fw-bets">' + gm.bets.map(function (b) { return betRow(b, gm); }).join('') + '</ul></article>';
  }
  function suggestRows() {
    var t = now(), base = S.rows.filter(function (r) { return S.sport === 'all' || r.sp === S.sport; });
    annotate(base, t);
    var withOpen = base.filter(function (r) { return r._n > 0; });
    var beats = withOpen.filter(function (r) { return TIERED[r.sp] && r.tier === 'beats'; })
      .sort(function (a, b) { return numDesc(a.cents && a.cents.v, b.cents && b.cents.v) || numDesc(a._usd, b._usd) || cmpName(a, b); }).slice(0, 5);
    if (beats.length) return { head: 'Open now from wallets that beat the close', rows: beats };
    return { head: 'Most open positions now', rows: withOpen.sort(function (a, b) { return numDesc(a._n, b._n) || numDesc(a._usd, b._usd) || cmpName(a, b); }).slice(0, 5) };
  }
  function miniRow(row) {
    var bits = [tierWord(row)];
    if (row.cents) bits.push(centsCell(row));
    if (row._n) bits.push('<span class="sv2-num">' + row._n + '</span> open, <span class="sv2-num">' + esc(fmt.usd(row._usd)) + '</span>');
    return '<li class="sv2-fw-row sv2-fw-row--mini">' + ui.star(row.sp, row.w, row.name) +
      '<button type="button" class="sv2-fw-main sv2-fw-main--mini sv2-press sv2-press-row" data-fw-open="' + esc(row.k) + '" data-fk="mini:' + esc(row.k) + '">' +
      '<span class="sv2-fw-whol1">' + nm(row.name, 'sv2-ell') + '<span class="sv2-fw-sp sv2-fw-sp--d">' + esc(sportName(row.sp)) + '</span></span>' +
      '<span class="sv2-fw-l2 sv2-fw-l2--on"><span class="sv2-fw-sp">' + esc(sportName(row.sp)) + '</span>' + dot() + bits.map(function (x) { return '<span>' + x + '</span>'; }).join(dot()) + '</span></button></li>';
  }
  function lastSettledAmong(fl) {
    var m = null;
    fl.forEach(function (f) { var r = S.idx[f.sport + '|' + f.w] || S.ret[f.sport + '|' + f.w]; if (r && isNum(r.last) && (m == null || r.last > m)) m = r.last; });
    return m;
  }
  function floorLine() {
    var f = file(); if (!f || !isNum(f.floor_usd)) return '';
    var by = f.floor_usd_by_sport || {}, ex = Object.keys(by).filter(function (s) { return by[s] !== f.floor_usd; })
      .map(function (s) { return fmt.usd(by[s]) + ' ' + sportName(s); });
    return 'Positions under ' + fmt.usd(f.floor_usd) + (ex.length ? ' (' + ex.join(', ') + ')' : '') + ' are not listed.';
  }

  function paintFeed() {
    var box = document.getElementById('fw-feed'); if (!box) return;
    var f = file(), st = store.state.wallets;
    if (!f) {
      box.innerHTML = st === 'loading' ? ui.skel(2, 'Loading wallets', 'sv2-fw-skel') : '<p class="sv2-err">Could not load the wallet list. <button type="button" class="sv2-link" data-sv2-retry>Try again</button></p>';
      return;
    }
    var t = now(), fl = follows.list(), all = buildFeed(f, fl, S.idx, t, 'all'), feed = buildFeed(f, fl, S.idx, t, S.sport);
    S.nextCut = all.nextCut;
    /* summary */
    var sum = document.getElementById('fw-sum');
    if (sum) {
      if (!fl.length) sum.textContent = 'Not following any wallet yet';
      else sum.textContent = fl.length + ' following, ' + all.nBets + (all.nBets === 1 ? ' open bet' : ' open bets') +
        (all.sameGames ? ', ' + all.sameGames + (all.sameGames === 1 ? ' game' : ' games') + ' with two you follow on a side' : '');
    }
    var html = '';
    if (!fl.length) {
      var sg = suggestRows();
      html += '<p class="sv2-fw-hint">Tap the star to follow a wallet.</p>';
      if (sg.rows.length) html += '<h3 class="sv2-h2 sv2-fw-sub">' + esc(sg.head) + '</h3><ul class="sv2-fw-list sv2-fw-list--mini">' + sg.rows.map(miniRow).join('') + '</ul>';
    } else if (!feed.games.length) {
      var ls = lastSettledAmong(fl);
      html += '<p class="sv2-empty-line">No open bets from wallets you follow.' + (ls != null ? ' Last settled: ' + esc(ct.dayTime(ls)) + ' CT.' : '') + '</p>';
    } else {
      var lastDay = null;
      feed.games.forEach(function (gm) {
        var dk = isNum(gm.gst) ? ct.dateKey(gm.gst) : 'x';
        if (dk !== lastDay) { html += '<h3 class="sv2-h2 sv2-fw-dayh">' + esc(isNum(gm.gst) ? ct.day(gm.gst, t) : 'Start time not stored') + '</h3>'; lastDay = dk; }
        html += gameCard(gm);
      });
    }
    if (feed.hidden > 0) html += '<p class="sv2-fw-note">' + feed.hidden + (feed.hidden === 1 ? ' open bet from a wallet you follow is' : ' open bets from wallets you follow are') + ' in other sports.</p>';
    withFocus(function () { box.innerHTML = html; paintGone(fl); paintRail(fl); });
    var fl2 = document.getElementById('fw-floor'); if (fl2) fl2.textContent = floorLine();
  }

  /* "Since you followed" reads the dated settled list from since.json (core loads it only once there is a follow); a wallets file
     that still carries an inline since_list is read the same way. Items: [settled_at, first_fill, r, flat, ev, stake], a position each. */
  function sinceFrom() {
    if (store.since && isNum(store.since.since_from)) return store.since.since_from;
    var f = file(); return f && isNum(f.since_from) ? f.since_from : null;
  }
  /* only ask for since.json when the wallets file names it (since_file), or a localhost ?since= override is given: a v1 file has no list to fetch */
  function sinceWanted() { var f = file(); return !!((f && typeof f.since_file === 'string' && f.since_file) || SV2.dev.param('since')); }
  function sinceState() { return store.since ? 'ok' : (!sinceWanted() || store.state.since === 'none') ? 'none' : 'loading'; }
  function sinceOf(row, at) {
    if (!row || !isNum(at)) return null;
    var items = null;
    if (store.since) items = rules.sinceItems(store.since, row.sp, row.w, row.ret);
    else if (row.sinceInline) items = row.sinceInline;
    if (!Array.isArray(items)) return null;
    var res = rules.sinceFollowed(items, at, sinceFrom());
    if (res) res.hasEv = items.some(function (it) { return Array.isArray(it) && it[4] != null; });
    return res;
  }
  function ensureSince() {
    if (!follows.list().length || store.since || !sinceWanted()) return;
    if (store.state.since === 'none' && S.sinceTriedAt === S.built) return;     /* one retry per wallets build */
    S.sinceTriedAt = S.built;
    SV2.load.since();
  }
  var NO_LIST = 'Not available yet: the account file does not carry a dated list.';
  function sinceTally(fl) {
    var w = 0, l = 0, p = 0, u = 0, skipped = 0, n = 0, na = 0, win = 0, tot = 0, gw = 0, gl = 0, gok = true;
    fl.forEach(function (x) {
      var row = S.idx[x.sport + '|' + x.w] || S.ret[x.sport + '|' + x.w]; tot++;
      var res = sinceOf(row, x.at);
      if (!res) { na++; return; }
      w += res.w; l += res.l; p += res.p; u += res.units; skipped += res.skipped; n += res.n; if (res.windowNote) win++;
      if (res.hasEv && res.games) { gw += res.games.w; gl += res.games.l; } else gok = false;
    });
    return { w: w, l: l, p: p, units: Math.round(u * 100) / 100, skipped: skipped, n: n, na: na, win: win, tot: tot, from: sinceFrom(),
      games: gok && n ? { w: gw, l: gl, n: gw + gl } : null };
  }
  /* "5-3 in bets, +0.42u flat, n=8. By game: 4-2, n=6. Small sample." (the count is positions; the game tally keeps a spread and a
     moneyline on one game from reading as two games) */
  function sinceCore(t) {
    var s = '<span class="sv2-num">' + esc(fmt.wl(t.w, t.l, t.p)) + '</span> in bets, <span class="sv2-num">' + esc(fmt.units(t.units, { signed: true })) + '</span> flat, n=<span class="sv2-num">' + t.n + '</span>.';
    if (t.games && t.games.n) s += ' By game: <span class="sv2-num">' + esc(fmt.wl(t.games.w, t.games.l)) + '</span>, n=<span class="sv2-num">' + t.games.n + '</span>.';
    if (t.n < SMALL) s += ' Small sample.';
    return s;
  }
  function sinceText(t, date) {
    return 'Since you followed (' + esc(ct.md(date)) + '): ' + sinceCore(t);
  }
  function sinceNone() { return sinceState() === 'loading' ? 'Loading the dated list.' : NO_LIST; }
  function paintRail(fl) {
    var rail = document.getElementById('fw-rail'); if (!rail) return;
    if (!fl.length) { rail.hidden = true; rail.innerHTML = ''; return; }
    rail.hidden = false;
    var f = file(), t = sinceTally(fl), live = fl.filter(function (x) { return S.idx[x.sport + '|' + x.w]; });
    var tt = now();
    var items = live.map(function (x) {
      var row = S.idx[x.sport + '|' + x.w]; annotate([row], tt);
      return '<li class="sv2-fw-row sv2-fw-row--mini">' + ui.star(row.sp, row.w, row.name) +
        '<button type="button" class="sv2-fw-main sv2-fw-main--mini sv2-press sv2-press-row" data-fw-open="' + esc(row.k) + '" data-fk="rail:' + esc(row.k) + '"><span class="sv2-fw-whol1">' + nm(row.name, 'sv2-ell') +
        '<span class="sv2-fw-openn sv2-num">' + (row._n ? row._n + ' open' : '') + '</span></span><span class="sv2-fw-l2 sv2-fw-l2--on"><span class="sv2-fw-sp">' + esc(sportName(row.sp)) + '</span></span></button></li>';
    }).join('');
    var since;
    if (t.tot === t.na) since = '<p class="sv2-fw-sinceline">' + esc(sinceNone()) + '</p>';
    else {
      since = '<p class="sv2-fw-sinceline">' + sinceCore(t) + '</p>';
      if (t.na) since += '<p class="sv2-fw-note">' + t.na + (t.na === 1 ? ' follow has' : ' follows have') + ' no dated list in the file.</p>';
      if (t.skipped) since += '<p class="sv2-fw-note">' + t.skipped + (t.skipped === 1 ? ' split position' : ' split positions') + ' not counted in the units.</p>';
      if (t.win) since += '<p class="sv2-fw-note">' + t.win + (t.win === 1 ? ' follow is' : ' follows are') + ' older than the file\'s window: it covers ' + esc(ct.md(t.from)) + ' onward (the file keeps 60 days).</p>';
    }
    var head = '<span class="sv2-h2">Following <span class="sv2-num">' + fl.length + '</span></span>';
    rail.innerHTML = '<div class="sv2-card sv2-fw-railcard">' +
      '<h2 class="sv2-h2 sv2-fw-railh">Following <span class="sv2-num">' + fl.length + '</span></h2>' +
      '<button type="button" class="sv2-fw-railtoggle sv2-press sv2-press-row" data-fw-rail aria-expanded="' + S.railOpen + '" aria-controls="fw-rail-x" data-fk="rail-toggle">' + head + ui.icon('chevron', 'sv2-chev') + '</button>' +
      '<div class="sv2-x" id="fw-rail-x"' + (S.railOpen ? ' data-open' : '') + '><div class="sv2-x-in">' +
      (items ? '<ul class="sv2-fw-list sv2-fw-list--mini">' + items + '</ul>' : '') +
      '<h3 class="sv2-h2 sv2-fw-sub">Since you followed</h3>' + since + '</div></div></div>';
  }
  function paintGone(fl) {
    var box = document.getElementById('fw-gone'); if (!box) return;
    var gone = fl.filter(function (x) { return !S.idx[x.sport + '|' + x.w]; });
    if (!gone.length || !file()) { box.hidden = true; box.innerHTML = ''; return; }
    box.hidden = false;
    var rows = gone.map(function (x) {
      var row = S.ret[x.sport + '|' + x.w], name = row ? row.name : rules.nameOf(null, x.w), body;
      if (row) {
        var bits = [];
        if (isNum(row.r.left_at)) bits.push('Left the list ' + esc(ct.md(row.r.left_at)));
        var res = sinceOf(row, x.at);
        bits.push(res ? sinceText(res, x.at) : esc(sinceNone()));
        body = bits.join(dot());
      } else body = esc('Not on the list now. No numbers stored for it here.');
      return '<li class="sv2-fw-gone-row"><button type="button" class="sv2-fw-gone-main sv2-press sv2-press-row" data-fw-open="' + esc(x.sport + '|' + x.w) + '" data-fk="gone:' + esc(x.sport + '|' + x.w) + '">' +
        '<span class="sv2-fw-whol1">' + nm(name, 'sv2-ell') + '<span class="sv2-fw-sp sv2-fw-sp--d">' + esc(sportName(x.sport)) + '</span></span><span class="sv2-fw-gone-b">' + body + '</span></button>' +
        '<button type="button" class="sv2-btn sv2-press sv2-press-btn sv2-fw-unf" data-fw-unf="' + esc(x.sport + '|' + x.w) + '" aria-label="' + esc(copy.star.on(name, x.sport)) + '" data-fk="unf:' + esc(x.sport + '|' + x.w) + '">Unfollow</button></li>';
    }).join('');
    box.innerHTML = '<h2 class="sv2-h2 sv2-fw-sub">Not on the list now</h2><ul class="sv2-fw-gonelist">' + rows + '</ul>';
  }

  /* repaint a region without losing the keyboard focus: focus keys are data-fk (or the star's sport and wallet) */
  function withFocus(fn) {
    var a = document.activeElement, key = null, star = null, had = !!(a && S.el && S.el.contains(a));
    if (had) {
      var k = a.closest ? a.closest('[data-fk]') : null;
      if (k) key = k.getAttribute('data-fk');
      else if (a.closest && a.closest('[data-sv2-star]')) { var s = a.closest('[data-sv2-star]'); star = [s.getAttribute('data-sport'), s.getAttribute('data-w')]; }
    }
    fn();
    if (key) {
      var els = S.el.querySelectorAll('[data-fk]');
      for (var i = 0; i < els.length; i++) if (els[i].getAttribute('data-fk') === key) { els[i].focus({ preventScroll: true }); return; }
    } else if (star) {
      var ss = S.el.querySelectorAll('[data-sv2-star]');
      for (var j = 0; j < ss.length; j++) if (ss[j].getAttribute('data-sport') === star[0] && ss[j].getAttribute('data-w') === star[1]) { ss[j].focus({ preventScroll: true }); return; }
    }
    /* the focused element is gone (a followed wallet left the suggestions, an unfollowed row left the rail): land on the summary line */
    if (had && !(document.activeElement && S.el.contains(document.activeElement) && document.activeElement !== S.el)) {
      var sm = document.getElementById('fw-sum'); if (sm) sm.focus({ preventScroll: true });
    }
  }

  /* ------------------------------------------------------------------ account sheet */
  var TABS = {
    rec: 'Their record', bet: 'This bet', who: 'Who else', open: 'Open bets'
  };
  function sheetRow(sh) { return S.idx[sh.sp + '|' + sh.w] || S.ret[sh.sp + '|' + sh.w] || null; }
  function sheetGroup(sh, row) {
    if (!sh.betKey || !row) return null;
    var out = null;
    rules.groupSides(row.r.positions || []).forEach(function (g) { if (betKey(g) === sh.betKey) out = g; });
    if (out) { var t = rules.sideTotals(out.positions); out.total = declared(file(), 'side_usd') && isNum(t.stored_usd) ? t.stored_usd : t.usd; out.sideX = declared(file(), 'side_press') ? t.press : null; }
    return out;
  }
  function tabsFor(sh, row, grp) {
    if (grp) return ['rec', 'bet', 'who'];
    if (row && liveGroups(file(), row, now()).length) return ['rec', 'open'];
    return ['rec'];
  }
  function centsFull(row) {
    var c = row.cents; if (!c) return '';
    var s = fmt.centsSigned(c.v); if (s == null) return '';
    return '<span class="sv2-num">' + esc(s) + '</span> vs close, ' + (c.raw ? 'raw average, not shrunk' : 'shrunk');
  }
  function sheetHead(sh, row, grp) {
    var name = row ? row.name : rules.nameOf(null, sh.w), on = follows.has(sh.sp, sh.w), f = file();
    var l1 = '<div class="sv2-fw-sh1"><h2 class="sv2-fw-shname" id="fw-sh-name">' + nm(name) + '</h2><span class="sv2-chip sv2-chip--muted">' + esc(sportName(sh.sp)) + '</span>' +
      '<button type="button" class="sv2-fw-fbtn sv2-press sv2-press-btn" data-sv2-star data-sport="' + esc(sh.sp) + '" data-w="' + esc(sh.w) + '" data-name="' + esc(name) + '" aria-pressed="' + on + '" aria-label="' + esc(on ? copy.star.on(name, sh.sp) : copy.star.off(name, sh.sp)) + '">' +
      ui.icon('star') + '<span class="sv2-fw-fl" data-fw-fl>' + esc((on ? 'Following in ' : 'Follow in ') + sportName(sh.sp)) + '</span></button></div>';
    var l2 = '';
    if (row) {
      if (!TIERED[sh.sp]) l2 = esc(COLLEGE);
      else l2 = '<span>' + esc(copy.acct[row.tier].sentence(row.rkn)) + '</span>' + (centsFull(row) ? '<span>' + centsFull(row) + '</span>' : '');
      var ch = chipsFor(row); if (row.ret) ch = ui.chip('Not on the list now', 'muted') + ch;
      if (ch) l2 += '<span class="sv2-fw-shchips">' + ch + '</span>';
    }
    var l3 = '';
    if (grp) {
      var oldest = null; grp.positions.forEach(function (p) { var a = pxAgeMin(f, p, now()); if (a != null && (oldest == null || a > oldest)) oldest = a; });
      var px = grp.positions.length === 1 ? grp.positions[0].px : null, ln = lineText(grp);
      l3 = '<span class="sv2-fw-sh3"><b>This bet:</b> ' + esc(grp.side) + (ln ? ' <span class="sv2-num">' + esc(ln) + '</span>' : '') + ' ' + esc(MKT[grp.g] || grp.g) + ' <span class="sv2-num">' + esc(fmt.usd(grp.total) || '') + '</span>' +
        (px != null ? ' at <span class="sv2-num">' + esc(fmt.cents(px)) + '</span>' : '') + (oldest != null ? ', price logged ' + esc(ageText(oldest)) + ' ago' : ', price time not stored') +
        (grp.sideX != null ? dot() + '<span class="sv2-num">' + fmt.mult(grp.sideX) + '</span> median cost' : '') + '</span>';
    }
    return '<header class="sv2-fw-shhead">' + l1 + (l2 ? '<p class="sv2-fw-sh2">' + l2 + '</p>' : '') + (l3 ? '<p class="sv2-fw-sh3w">' + l3 + '</p>' : '') + '</header>';
  }
  function sheetHtml() {
    var sh = S.sh, row = sheetRow(sh), grp = sheetGroup(sh, row), tabs = tabsFor(sh, row, grp);
    if (!grp) sh.betKey = null;
    if (tabs.indexOf(sh.tab) < 0) sh.tab = 'rec';
    var strip = tabs.length > 1 ? '<div class="sv2-fw-tabs" data-fw-tabs>' + seg.html({ id: 'fw-sheet-tabs', label: 'Account sections', skin: 'bar', value: sh.tab, items: tabs.map(function (k) { return { v: k, label: TABS[k] }; }) }) + '</div>' : '';
    return '<div class="sv2-fw-sh" data-fw-sheet>' + sheetHead(sh, row, grp) + strip + '<div class="sv2-fw-panel" id="fw-sh-panel" role="' + (strip ? 'tabpanel' : 'region') + '" aria-label="' + esc(TABS[sh.tab]) + '">' + panelHtml(sh, row, grp) + '</div></div>';
  }
  function panelHtml(sh, row, grp) {
    if (!row) return '<p class="sv2-empty-line">' + esc('No account details for this wallet.') + '</p>';
    if (sh.tab === 'bet' && grp) return betPanel(row, grp);
    if (sh.tab === 'who' && grp) return whoPanel(row, grp);
    if (sh.tab === 'open') return openPanel(row);
    return recPanel(sh, row, grp);
  }
  function openPanel(row) {
    var gs = liveGroups(file(), row, now());
    return '<ul class="sv2-fw-openlist">' + gs.map(function (g) {
      var ln = lineText(g);
      return '<li><button type="button" class="sv2-fw-pick sv2-press sv2-press-row" data-fw-pickbet="' + esc(betKey(g)) + '" data-fk="pick:' + esc(betKey(g)) + '"><span><span class="sv2-fw-mk">' + esc(MKT[g.g] || g.g) + '</span> <b>' + esc(g.side) + (ln ? ' <span class="sv2-num">' + esc(ln) + '</span>' : '') + '</b></span>' +
        '<span class="sv2-fw-b2">' + esc(teamsOf(g.ev)) + dot() + esc(isNum(g.gst) ? ct.dayTime(g.gst) + ' CT' : 'start time not stored') + dot() + '<span class="sv2-num">' + esc(fmt.usd(g.total) || '') + '</span></span></button></li>';
    }).join('') + '</ul>';
  }

  function recPanel(sh, row, grp) {
    var r = row.r, f = file(), html = '';
    /* 1 since we started tracking it (forward only) */
    var d1 = row.first != null ? ' (' + esc(ct.md(row.first)) + ')' : '';
    if (!row.fwdPub) html += '<p class="sv2-fw-p"><b>Since we started tracking it:</b> Not published yet.</p>';
    else if (!row.fwd || !isNum(row.fwd.n) || row.fwd.n === 0) html += '<p class="sv2-fw-p"><b>Since we started tracking it' + d1 + ':</b> no settled bets yet.</p>';
    else html += '<p class="sv2-fw-p"><b>Since we started tracking it' + d1 + ':</b> <span class="sv2-num">' + esc(fmt.wl(row.fwd.w, row.fwd.l, row.fwd.p)) + '</span>' +
      (isNum(row.fwd.flat_roi) ? ', flat ' + roiHtml(row.fwd.flat_roi) : '') + ', n=<span class="sv2-num">' + row.fwd.n + '</span>.' + (row.fwd.n < SMALL ? ' Small sample.' : '') + '</p>';
    /* 3 past record */
    if (isNum(r.w_) && isNum(r.l_)) {
      var nn = isNum(r.n) ? r.n : r.w_ + r.l_;
      html += '<section class="sv2-fw-sec"><h3 class="sv2-h2">Past record (includes games before we tracked it)</h3><p class="sv2-fw-p"><span class="sv2-num">' + esc(fmt.wl(r.w_, r.l_)) + '</span>' +
        (isNum(r.roi) ? ', ' + roiHtml(r.roi) + ' by dollars' : '') + (row.flat != null ? ', flat ' + roiHtml(row.flat) : '') + ', n=<span class="sv2-num">' + nn + '</span>.' + (nn < SMALL ? ' Small sample.' : '') + '</p>';
      if (row.expW != null && row.luck != null) html += '<p class="sv2-fw-p">Won <span class="sv2-num">' + r.w_ + '</span>; the prices implied <span class="sv2-num">' + Math.round(row.expW) + '</span>. Chance of doing at least this well by luck: <span class="sv2-num">' + Math.round(row.luck * 100) + '%</span></p>';
      html += '</section>';
      /* 4 cuts */
      var cuts = cutsOf(row, grp), cur = null;
      cuts.forEach(function (c) { if (c.key === sh.cut) cur = c; });
      if (!cur) { cur = cuts[0]; sh.cut = cur.key; }
      html += '<div class="sv2-fw-cuts" role="group" aria-label="Record by kind of bet">' + cuts.map(function (c) { return cutTile(c, c.key === cur.key); }).join('') + '</div>';
      /* 5 curve */
      html += curveBlock(row, cur, sh.cm);
      /* last 10 */
      html += last10(r);
    } else html += '<p class="sv2-fw-p sv2-fw-mut">No past record is stored for this wallet.</p>';
    /* 6 since you followed */
    if (follows.has(sh.sp, sh.w)) {
      var at = follows.at(sh.sp, sh.w);
      html += '<section class="sv2-fw-sec" data-fw-since>' + sinceBlock(sinceOf(row, at), at) + '</section>';
    }
    return html;
  }
  function sinceBlock(res, at) {
    if (!res) return '<p class="sv2-fw-p"><b>Since you followed:</b> ' + esc(sinceNone()) + '</p>';
    var s = '<p class="sv2-fw-p">' + sinceText(res, at) + '</p>';
    if (res.skipped) s += '<p class="sv2-fw-note">' + res.skipped + (res.skipped === 1 ? ' split position' : ' split positions') + ' not counted in the units.</p>';
    if (res.windowNote) s += '<p class="sv2-fw-note">Covers ' + esc(ct.md(res.sinceFrom)) + ' onward (the file keeps 60 days).</p>';
    return s;
  }
  function cutTile(c, on) {
    var cell = c.cell, n = cell ? cell[0] + cell[1] : 0;
    return '<button type="button" class="sv2-fw-cut sv2-press sv2-press-card" data-fw-cut="' + esc(c.key) + '" aria-pressed="' + on + '" data-fk="cut:' + esc(c.key) + '">' +
      '<span class="sv2-fw-cut-n">n=<span class="sv2-num">' + n + '</span>' + (cell && n < SMALL_CUT ? ' <span class="sv2-fw-small">small sample</span>' : '') + '</span>' +
      '<span class="sv2-fw-cut-t">' + esc(c.title) + '</span><span class="sv2-fw-cut-s">' + esc(c.sub) + '</span>' +
      (cell ? '<span class="sv2-fw-cut-r"><span class="sv2-num">' + esc(fmt.wl(cell[0], cell[1])) + '</span> ' + roiHtml(cell[2]) + '</span>' : '<span class="sv2-fw-cut-r sv2-fw-mut">No bets yet</span>') + '</button>';
  }
  /* last 30 days of settled bets as a running total. Flat counts every bet as one unit (profit / stake); Dollars are the real profit. */
  function curveBlock(row, cut, cm) {
    var rows = row.r.curve, f = file(); if (!Array.isArray(rows) || !f || !isNum(f.built)) return '';
    var t1 = f.built, t0 = t1 - 30 * DAY, flat = cm !== 'dollars';
    var pts = rows.filter(function (c) { return c[0] >= t0 && c[0] <= t1 && cut.match(c); }).sort(function (a, b) { return a[0] - b[0]; });
    var head = '<div class="sv2-fw-ch-h"><h3 class="sv2-h2">Last 30 days</h3>' +
      seg.html({ id: 'fw-curve-mode', label: 'Last 30 days profit', skin: 'fill', size: 'sm', value: flat ? 'flat' : 'dollars', items: [{ v: 'flat', label: 'Flat' }, { v: 'dollars', label: 'Dollars' }] }) + '</div>';
    if (!pts.length) return '<section class="sv2-fw-sec sv2-fw-ch" data-fw-curve>' + head + '<p class="sv2-fw-p sv2-fw-mut">' + (cut.key === 'all' ? 'No settled bets in the last 30 days.' : 'None of the last 30 days of settled bets match this cut.') + '</p></section>';
    var c = 0, xy = [[t0, 0]], used = 0;
    pts.forEach(function (p) {
      var step = flat ? (p[2] > 0 ? p[1] / p[2] : null) : p[1];
      if (step == null) return;
      c += step; used++; xy.push([p[0], c]);
    });
    xy.push([t1, c]);
    var mn = Math.min.apply(null, xy.map(function (p) { return p[1]; }).concat(0)), mx = Math.max.apply(null, xy.map(function (p) { return p[1]; }).concat(0)), rg = (mx - mn) || 1;
    var W = 640, H = 140, X = function (t) { return (t - t0) / (t1 - t0) * W; }, Y = function (v) { return H - 10 - (v - mn) / rg * (H - 24); };
    var d = xy.map(function (p, i) { return (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1); }).join(' ');
    var endTxt = flat ? fmt.units(c, { signed: true }) + ' flat' : (c < 0 ? '-' : '+') + fmt.usd(Math.abs(c));
    return '<section class="sv2-fw-sec sv2-fw-ch" data-fw-curve>' + head +
      '<p class="sv2-fw-chv sv2-num ' + (c > 0 ? 'sv2-win' : c < 0 ? 'sv2-loss' : '') + '">' + esc(endTxt) + '</p>' +
      '<svg class="sv2-fw-curve" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" role="img" aria-label="Running ' + (flat ? 'flat-stake' : 'dollar') + ' profit over the last 30 days, ending ' + esc(endTxt) + '">' +
      '<line x1="0" x2="' + W + '" y1="' + Y(0).toFixed(1) + '" y2="' + Y(0).toFixed(1) + '" class="sv2-fw-zero"/>' +
      '<path d="' + d + ' L' + W + ' ' + H + ' L0 ' + H + 'Z" class="sv2-fw-area"/><path d="' + d + '" class="sv2-fw-line" vector-effect="non-scaling-stroke"/></svg>' +
      '<p class="sv2-fw-note"><span class="sv2-num">' + used + '</span> settled ' + (used === 1 ? 'bet' : 'bets') + (cut.key === 'all' ? '' : ' matching this cut') + ', by the day each one settled.' + (used < SMALL_CUT ? ' Small sample.' : '') + '</p></section>';
  }
  function last10(r) {
    var legs = Array.isArray(r.legs) ? r.legs.slice(0, 10) : []; if (!legs.length) return '';
    var w = 0, l = 0;
    var dots = legs.map(function (x) { if (x[1] === 'win') { w++; return '<i class="w"></i>'; } if (x[1] === 'loss') { l++; return '<i class="l"></i>'; } return '<i class="p"></i>'; }).join('');
    return '<div class="sv2-fw-last"><div class="sv2-fw-dots" role="img" aria-label="Last ' + legs.length + ' settled: ' + w + ' wins, ' + l + ' losses">' + dots + '</div><span class="sv2-fw-note">Last ' + legs.length + ' settled, any size: <span class="sv2-num">' + w + '</span> wins, <span class="sv2-num">' + l + '</span> losses. Newest first.</span></div>';
  }

  function betPanel(row, grp) {
    var f = file(), html = '<ul class="sv2-fw-rl">';
    grp.positions.forEach(function (p) {
      var ln = grp.g === 'spread' ? fmt.line(p.line, { signed: true }) : grp.g === 'total' ? fmt.line(p.line) : null;
      var a = pxAgeMin(f, p, now()), lines = [];
      lines.push('<b class="sv2-num">' + esc(fmt.usd(p.usd) || '') + '</b>' + (isNum(p.shares) ? ', <span class="sv2-num">' + esc(fmt.n(p.shares)) + '</span> shares' : '') + (isNum(p.px) ? ' at <span class="sv2-num">' + esc(fmt.cents(p.px)) + '</span>' : '') + (ln ? ', ' + esc(MKT[grp.g]) + ' <span class="sv2-num">' + esc(ln) + '</span>' : ''));
      lines.push(a != null ? 'Price logged ' + esc(ageText(a)) + ' ago' : 'Price time not stored');
      if (isNum(p.press)) lines.push('<span class="sv2-num">' + fmt.mult(p.press) + '</span> average cost (this position)');
      lines.push(p.cens ? 'Held since before we started scanning it' : isNum(p.since) ? 'Held since ' + esc(ct.stamp(p.since)) + ' CT' : '');
      if (isNum(p.px_first)) lines.push('Price when first seen: <span class="sv2-num">' + esc(fmt.cents(p.px_first)) + '</span>' + (isNum(p.px_first_t) ? ' (' + esc(ct.md(p.px_first_t)) + ')' : ''));
      if (Array.isArray(p.hist) && p.hist.length > 1) lines.push('Size over time: ' + p.hist.slice(-6).map(function (h) { return esc(ct.md(h[0])) + ' <span class="sv2-num">' + esc(fmt.n(h[1])) + '</span>'; }).join(', ') + ' shares');
      if (p.two_way) lines.push('Also holds the other side');
      html += '<li>' + lines.filter(Boolean).join('<br>') + '</li>';
    });
    html += '</ul>';
    if (grp.positions.length > 1) html = '<p class="sv2-fw-p"><b class="sv2-num">' + esc(fmt.usd(grp.total) || '') + '</b> across <span class="sv2-num">' + grp.positions.length + '</span> positions' + (grp.sideX != null ? dot() + '<span class="sv2-num">' + fmt.mult(grp.sideX) + '</span> median cost' : '') + '</p>' + html;
    return html + '<p class="sv2-fw-note">No entry price is stored. Amounts are shares times the market price at the last scan.</p>';
  }

  function cardFor(ev, gst) {
    var c = store.cards; if (!c || !Array.isArray(c.games)) return null;
    var hit = null;
    c.games.forEach(function (g) { if (g.ev === ev && g.gst === gst) hit = g; });
    if (!hit) c.games.forEach(function (g) { if (!hit && g.ev === ev) hit = g; });
    return hit;
  }
  function whoPanel(row, grp) {
    var game = cardFor(grp.ev, grp.gst);
    if (!game || !game.markets || !game.markets[grp.g]) {
      return '<p class="sv2-fw-p">' + esc(store.state.cards === 'loading' ? 'Loading the Sharps cards.' : 'No card for this game yet.') + '</p>';
    }
    var m = game.markets[grp.g], tiered = !!TIERED[String(game.sport).toLowerCase()], names = Object.keys(m.sides || {});
    names.sort(function (a, b) { return (b === grp.side) - (a === grp.side); });
    var html = names.map(function (name) {
      var all = m.sides[name] && m.sides[name].all; if (!all) return '';
      var bits = [];
      if (tiered && all.rk && isNum(all.rk.sharp_n) && isNum(all.rk.dull_n)) {
        bits.push('<span class="sv2-num">' + all.rk.sharp_n + '</span> that ' + (all.rk.sharp_n === 1 ? 'beats' : 'beat') + ' the close (<span class="sv2-num">' + esc(fmt.usd(all.rk.sharp_usd) || '$0') + '</span>)');
        bits.push('<span class="sv2-num">' + all.rk.dull_n + '</span> that ' + (all.rk.dull_n === 1 ? 'loses' : 'lose') + ' to the close (<span class="sv2-num">' + esc(fmt.usd(all.rk.dull_usd) || '$0') + '</span>)');
      }
      var line = bits.join(', ');
      if (isNum(all.sharp_usd)) line += (line ? '. ' : '') + 'Past-winner money <span class="sv2-num">' + esc(fmt.usd(all.sharp_usd)) + '</span>';
      if (!tiered) line += (line ? '. ' : '') + 'No price tier in college (no tested closing-price model)';
      return '<li class="sv2-fw-wh' + (name === grp.side ? ' is-mine' : '') + '"><b>' + esc(name) + '</b>' + (name === grp.side ? ' <span class="sv2-fw-small">this bet</span>' : '') + '<p>' + line + '.</p></li>';
    }).join('');
    var units = rules.shownUnits(game, grp.g), sf = m.sf && m.sf.all, sport = String(game.sport).toLowerCase(), play;
    if (sport === 'cfb') play = 'No play on CFB.';
    else if (units > 0 && sf && sf.side) play = 'The Sharps page shows a play on <b>' + esc(sf.side) + '</b>: ' + (ui.playPill(units) || '');
    else play = 'The Sharps page has no play in this market.';
    var sharpsHash = '#sharps/play/' + encodeURIComponent(grp.ev) + '/' + encodeURIComponent(grp.g);
    return '<ul class="sv2-fw-whl">' + html + '</ul><p class="sv2-fw-p">' + play + '</p><p class="sv2-fw-p"><a class="sv2-link" href="' + sharpsHash + '">Open the Sharps page</a></p>';
  }

  /* open / repaint */
  function routeOf(sh) { return 'following/acct/' + sh.sp + '/' + sh.w + (sh.betKey ? '/' + sh.betKey : ''); }
  function showSheet(sp, w, betK) {
    S.sh = { sp: sp, w: w, betKey: betK || null, tab: 'rec', cut: 'all', cm: 'flat' };
    var row = sheetRow(S.sh), label = row ? row.name : rules.nameOf(null, w);
    SV2.sheet.open(sheetHtml(), { label: label, route: routeOf(S.sh), returnFocus: S.opener, onClose: function () { S.sh = null; } });
  }
  function repaintPanel() {
    var sh = S.sh, panel = document.getElementById('fw-sh-panel'); if (!sh || !panel) return;
    var row = sheetRow(sh), grp = sheetGroup(sh, row);
    panel.setAttribute('aria-label', TABS[sh.tab] || '');
    panel.innerHTML = panelHtml(sh, row, grp);
    SV2.rail.scan(panel);
  }
  function openFromRoute(r) {
    var sp = r.sub[1], w = r.sub[2], bk = r.sub.slice(3).join('/') || null;
    if (!sp || !w) return;
    if (SV2.sheet.isOpen() && S.sh && S.sh.sp === sp && S.sh.w === w) return;
    var f = file();
    if (!f && store.state.wallets === 'loading') { S.pendingRoute = r; return; }
    showSheet(sp, w, bk);
  }

  /* ------------------------------------------------------------------ shell + events */
  function sportItems() { return [{ v: 'all', label: 'All' }].concat(sportsPresent().map(function (s) { return { v: s, label: sportName(s) }; })); }
  function buildShell(el) {
    el.innerHTML = '<div class="sv2-fw">' +
      '<p class="sv2-fw-sum" id="fw-sum" tabindex="-1"></p>' +
      '<div class="sv2-fw-sports" id="fw-sports">' + seg.html({ id: 'fw-sport', label: 'Sport', value: 'all', size: 'sm', scroll: true, items: sportItems() }) + '</div>' +
      '<div class="sv2-cols sv2-fw-cols">' +
      '<div class="sv2-fw-maincol"><section aria-labelledby="fw-h-next"><h2 class="sv2-h2 sv2-fw-h" id="fw-h-next">Next up</h2><div id="fw-feed">' + ui.skel(2, 'Loading wallets', 'sv2-fw-skel') + '</div><p class="sv2-fw-note" id="fw-floor"></p></section>' +
      '<section id="fw-gone" class="sv2-fw-gone" hidden></section></div>' +
      '<aside class="sv2-col-rail sv2-fw-rail" id="fw-rail" aria-label="Wallets you follow" hidden></aside></div>' +
      '<section class="sv2-fw-dir" aria-labelledby="fw-h-dir">' +
      '<div class="sv2-fw-dirh"><h2 class="sv2-h2 sv2-fw-h" id="fw-h-dir">Wallets <span class="sv2-num" id="fw-count"></span></h2><span class="sv2-fw-note" id="fw-match"></span></div>' +
      '<div class="sv2-fw-tools"><label class="sv2-fw-search"><span class="sv2-sr">Search name or address</span><input type="search" id="fw-q" placeholder="Search name or address" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search"></label>' +
      '<div class="sv2-fw-sortw"><span class="sv2-fw-sortl" id="fw-sortl">Sort</span><div id="fw-sorts"></div></div>' +
      '<div class="sv2-fw-togs"><button type="button" class="sv2-fw-tog sv2-press sv2-press-chip" id="fw-tog-min" aria-pressed="false">20+ games</button>' +
      '<button type="button" class="sv2-fw-tog sv2-press sv2-press-chip" id="fw-tog-inactive" aria-pressed="false">Show inactive</button></div></div>' +
      '<p class="sv2-fw-note" id="fw-college" hidden>' + esc(COLLEGE) + '</p>' +
      '<div class="sv2-fw-head" id="fw-colhead"><span class="sv2-fw-hc0">Wallet</span>' + COLS.map(function (c) { return '<button type="button" class="sv2-fw-hc" data-fw-sort="' + c[0] + '" aria-pressed="false"' + (sortAvailable(c[0]) ? '' : ' aria-disabled="true"') + '><span>' + esc(c[1]) + '</span>' + ui.icon('chevron', 'sv2-fw-arrow') + '</button>'; }).join('') + '</div>' +
      '<ul class="sv2-fw-list" id="fw-list"></ul>' +
      '<div class="sv2-fw-morew"><button type="button" class="sv2-btn sv2-press sv2-press-btn" id="fw-more" hidden>Show 24 more</button></div></section></div>';
    paintSortStrip();
  }
  function paintSortStrip() {
    var box = document.getElementById('fw-sorts'); if (!box) return;
    var key = S.sortKey || S.sort;
    box.innerHTML = seg.html({ id: 'fw-sortseg', label: 'Sort wallets by', value: key, size: 'sm', scroll: true,
      items: COLS.map(function (c) { return { v: c[0], label: c[1] }; }) });
    var strip = sortStrip();
    if (strip) $$('button[data-v]', strip).forEach(function (b) {
      if (!sortAvailable(b.getAttribute('data-v'))) { b.setAttribute('aria-disabled', 'true'); b.title = 'Not published yet'; }
    });
  }
  function setSort(k) {
    if (!sortAvailable(k)) return;
    S.sort = k; S.sortUser = true; S.shown = PAGE; paintDir();
  }
  function setSport(v) {
    S.sport = v; S.shown = PAGE;
    if (!S.sortUser) S.sort = defaultSort(v);
    paintFeed(); paintDir();
  }
  function repaintAll() {
    index();
    var sp = document.getElementById('fw-sports');
    if (sp) {
      var cur = SV2.seg.value($('.sv2-seg', sp));
      if (sportsPresent().concat(['all']).indexOf(S.sport) < 0) S.sport = 'all';
      sp.innerHTML = seg.html({ id: 'fw-sport', label: 'Sport', value: S.sport, size: 'sm', scroll: true, items: sportItems() });
      void cur;
    }
    if (!S.sortUser) S.sort = defaultSort(S.sport);
    paintSortStrip();
    var hd = document.getElementById('fw-colhead');
    if (hd) $$('[data-fw-sort]', hd).forEach(function (b) { if (!sortAvailable(b.getAttribute('data-fw-sort'))) b.setAttribute('aria-disabled', 'true'); else b.removeAttribute('aria-disabled'); });
    ensureSince();
    paintFeed(); paintDir();
    if (S.pendingRoute && file()) { var r = S.pendingRoute; S.pendingRoute = null; openFromRoute(r); }
    else if (file()) { var cr = SV2.route(); if (cr.page === 'following' && cr.sub[0] === 'acct' && S.lastOpened !== cr.hash && !SV2.sheet.isOpen()) { S.lastOpened = cr.hash; openFromRoute(cr); } }
  }

  function onClick(e) {
    var t = e.target; if (!t.closest) return;
    var b;
    if ((b = t.closest('[data-fw-bet]'))) {
      S.opener = b;
      var key = b.getAttribute('data-fw-bet'), sp = b.getAttribute('data-sp'), w = b.getAttribute('data-w');
      SV2.go('following/acct/' + sp + '/' + w + '/' + encodeURIComponent(key));
      return;
    }
    if ((b = t.closest('[data-fw-open]'))) {
      S.opener = b;
      var k = b.getAttribute('data-fw-open'), i = k.indexOf('|');
      SV2.go('following/acct/' + k.slice(0, i) + '/' + k.slice(i + 1));
      return;
    }
    if ((b = t.closest('[data-fw-rungs]'))) {
      var rk = b.getAttribute('data-fw-rungs'), open = !S.openRungs[rk];
      S.openRungs[rk] = open;
      b.setAttribute('aria-expanded', String(open));
      var x = document.getElementById(b.getAttribute('aria-controls'));
      if (x) { if (open) x.setAttribute('data-open', ''); else x.removeAttribute('data-open'); }
      return;
    }
    if ((b = t.closest('[data-fw-rail]'))) {
      S.railOpen = !S.railOpen; b.setAttribute('aria-expanded', String(S.railOpen));
      var rx = document.getElementById('fw-rail-x'); if (rx) { if (S.railOpen) rx.setAttribute('data-open', ''); else rx.removeAttribute('data-open'); }
      return;
    }
    if ((b = t.closest('[data-fw-unf]'))) {
      var uk = b.getAttribute('data-fw-unf'), ui2 = uk.indexOf('|');
      follows.toggle(uk.slice(0, ui2), uk.slice(ui2 + 1));
      return;
    }
    if ((b = t.closest('[data-fw-sort]'))) { setSort(b.getAttribute('data-fw-sort')); return; }
    if ((b = t.closest('[data-rail-id="fw-sortseg"] button[data-v]'))) { setSort(b.getAttribute('data-v')); return; }
    if ((b = t.closest('#fw-tog-min'))) { S.min20 = !S.min20; S.shown = PAGE; paintDir(); return; }
    if ((b = t.closest('#fw-tog-inactive'))) { S.inactive = !S.inactive; S.shown = PAGE; paintDir(); return; }
    if ((b = t.closest('#fw-more'))) { S.shown += PAGE; paintDir(); return; }
  }
  /* sheet events: the host persists across opens, so one delegated listener on it */
  function onSheetClick(e) {
    var t = e.target; if (!t.closest || !S.sh || !t.closest('[data-fw-sheet]')) return;
    var b;
    if ((b = t.closest('[data-fw-tabs] button[data-v]'))) {
      var v = b.getAttribute('data-v'); if (v === S.sh.tab) return;
      S.sh.tab = v; SV2.seg.set(b.parentNode, v); repaintPanel(); return;
    }
    if ((b = t.closest('[data-fw-cut]'))) { S.sh.cut = b.getAttribute('data-fw-cut'); withSheetFocus(repaintPanel); return; }
    if ((b = t.closest('[data-fw-curve] .sv2-seg button[data-v]'))) {
      var m = b.getAttribute('data-v'); if (m === S.sh.cm) return;
      S.sh.cm = m; SV2.seg.set(b.parentNode, m); withSheetFocus(repaintPanel); return;
    }
    if ((b = t.closest('[data-fw-pickbet]'))) {
      S.sh.betKey = b.getAttribute('data-fw-pickbet'); S.sh.tab = 'bet';
      SV2.sheet.set(sheetHtml());
      var first = document.querySelector('[data-fw-tabs] button[aria-pressed="true"]'); if (first) first.focus({ preventScroll: true });
      return;
    }
  }
  function withSheetFocus(fn) {
    var a = document.activeElement, c = a && a.closest ? a.closest('[data-fk]') : null, k = c ? c.getAttribute('data-fk') : null;
    fn();
    if (k) { var els = document.querySelectorAll('#fw-sh-panel [data-fk]'); for (var i = 0; i < els.length; i++) if (els[i].getAttribute('data-fk') === k) { els[i].focus({ preventScroll: true }); return; } }
  }
  /* keep the visible follow wording in step with the store (core flips aria-pressed and aria-label on every star) */
  function paintFollowLabels() {
    SV2.$$('[data-fw-fl]').forEach(function (s) {
      var b = s.closest('[data-sv2-star]'); if (!b) return;
      s.textContent = (follows.has(b.getAttribute('data-sport'), b.getAttribute('data-w')) ? 'Following in ' : 'Follow in ') + sportName(b.getAttribute('data-sport'));
    });
    var sec = document.querySelector('[data-fw-since]');
    if (S.sh && !sec && S.sh.tab === 'rec' && document.getElementById('fw-sh-panel')) repaintPanel();       /* followed just now: add the since section */
    else if (S.sh && sec) { if (!follows.has(S.sh.sp, S.sh.w)) sec.remove(); }
  }

  function mount(el) {
    if (S.mounted) return;
    S.mounted = true; S.el = el;
    buildShell(el);
    el.addEventListener('click', onClick);
    /* the sport strip is rebuilt on every data load, so delegate on its holder */
    document.getElementById('fw-sports').addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('button[data-v]'); if (!b) return;
      var v = b.getAttribute('data-v'); if (v === S.sport) return;
      seg.set(b.parentNode, v); setSport(v);
    });
    var q = document.getElementById('fw-q');
    q.addEventListener('input', function () { S.q = q.value; S.shown = PAGE; paintDir(); });
    var host = document.getElementById('sv2-sheet-host'); if (host) host.addEventListener('click', onSheetClick);

    SV2.on('wallets', function () {
      var f = file();
      /* the 2 minute reload emits even when nothing changed: skip a repaint of the same build so focus and scroll stay put */
      if (f && S.built === f.built && S.lastState === store.state.wallets && S.lastStale === store.stale.wallets) return;
      S.lastState = store.state.wallets; S.lastStale = store.stale.wallets;
      repaintAll();
    });
    SV2.on('cards', function () {
      if (S.sh && S.sh.tab === 'who') repaintPanel();
    });
    /* since.json arrived (or failed): the tallies in the rail, the not-on-the-list rows and the sheet change */
    SV2.on('since', function () {
      if (!file()) return;
      var fl = follows.list(); withFocus(function () { paintGone(fl); paintRail(fl); });
      var sec = document.querySelector('[data-fw-since]');
      if (S.sh && sec) { var row = sheetRow(S.sh), at = follows.at(S.sh.sp, S.sh.w); sec.innerHTML = sinceBlock(sinceOf(row, at), at); }
    });
    SV2.on('follows', function (ev) {
      ensureSince();
      paintFeed();
      /* a followed row is never hidden by the inactive or 20+ filters, so the list only needs a repaint when this toggle could change
         whether its row shows (or when the change came from another tab) */
      if (file()) {
        var row = ev && ev.w ? S.idx[ev.sport + '|' + ev.w] : null;
        if (!ev || !ev.w || (row && ((row.inactive && !S.inactive) || (S.min20 && !(row.n >= MIN_GAMES))))) withFocus(paintDir);
      }
      paintFollowLabels();
    });
    SV2.on('tick', function (t) { if (S.nextCut != null && t >= S.nextCut) paintFeed(); });
    SV2.on('route', function (r) {
      if (r.page !== 'following') return;
      if (r.sub[0] === 'acct') { S.lastOpened = r.hash; openFromRoute(r); } else S.lastOpened = null;
    });
    /* first paint from whatever core already holds; deep links open once the data is there */
    S.lastState = store.state.wallets; S.lastStale = store.stale.wallets;
    var cr = SV2.route();
    if (cr.page === 'following' && cr.sub[0] === 'acct') { S.lastOpened = cr.hash; S.pendingRoute = cr; }
    repaintAll();
  }

  SV2.register('following', mount);
  /* pure functions for the node tests */
  SV2.fw = {
    declared: declared, ageText: ageText, pxAgeMin: pxAgeMin, pastWinner: pastWinner, mkRow: mkRow, buildFeed: buildFeed, liveGroups: liveGroups,
    sortRows: sortRows, matches: matches, defaultSort: defaultSort, cutsOf: cutsOf, teamsOf: teamsOf, oddsBand: oddsBand, sizeBand: sizeBand, betKey: betKey
  };
})();
