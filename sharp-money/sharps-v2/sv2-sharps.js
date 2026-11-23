/* Sharps V2, route #sharps. Owned by the Sharps page agent.
   Core (sv2-core.js) calls the registered mount once, the first time #sharps is shown, with the empty
   <section id="sv2-page-sharps"> element.

   What this page is: the plays the staking rule picked (NBA, NFL, CBB at a flat 1u from an untested rule, nothing on CFB),
   shown as a table (one row per play, a detail row under it), grouped by freeze time and then by evidence tier, or sorted flat by Price, vs fair, Tier or Size. Sharp money is context only: nothing here is a bet signal, a size rule,
   or an input to Top Reads, SM_GATE or any total. The tier is a label of this card's own stored fields; it never changes the 1u.
   Every number is a stored field, a count of stored rows, or arithmetic on stored fields. A missing field is omitted.

   Account hook: a tap on a wallet calls SV2.openAccount(sport, wallet, {ev, g, side, from:'sharps'}) when the Following
   page has defined it, and otherwise follows the link #following/acct/<sport>/<wallet>.
   Classes are sv2-sp- (the detail body, filters, rail) and sv2-tb- (the table); rules are at the end of sv2.css. No em dashes, no text-glyph icons. All times Central. */
(function () {
  'use strict';
  var SV2 = (typeof window !== 'undefined' && window.SV2) || null;
  if (!SV2) return;

  var esc = SV2.esc, fmt = SV2.fmt, ct = SV2.ct, rules = SV2.rules, ui = SV2.ui, seg = SV2.seg, copy = SV2.copy, isNum = SV2.isNum, store = SV2.store;

  /* ------------------------------------------------------------------ page copy (the deck lives in docs/sharps-v2-spec.md section 6.2) */
  var T = {
    band: { hour: 'Freezes within 1 hour', today: 'Later today', tomorrow: 'Tomorrow', later: 'Later' },
    bandOrder: ['hour', 'today', 'tomorrow', 'later'],
    market: { ml: 'ML', spread: 'Spread', total: 'Total' },
    marketOrder: ['ml', 'spread', 'total'],
    tierEmpty: 'No play is Clear right now.',
    priceNote: 'Polymarket\'s displayed price (a mid or last trade, not the price you would get), or Pinnacle\'s price when Polymarket had none. The file does not say which.',
    sameTag: 'same wallet',
    noMatch: 'No plays match these filters.',
    ctxCfb: 'No play on CFB',
    noSize: 'No size on CFB',
    collegeNoTier: 'No price tier in college (no tested closing-price model)',
    legend: ['Past-winner money', 'Other money', 'Losing-record money (hatched)']
  };
  var SPORT_ORDER = ['nfl', 'cfb', 'nba', 'cbb'];
  var FKEY = 'sv2-filters';
  var CTX_STEP = 12;

  /* ------------------------------------------------------------------ pure helpers (exported for the node tests) */
  function lc(s) { return String(s || '').toLowerCase(); }
  function mktOf(game, g) { return game && game.markets && game.markets[g] || null; }
  function sideAll(m, name) { var s = m && m.sides && m.sides[name]; return s && s.all || null; }
  function sfOf(m) { return m && m.sf && m.sf.all || null; }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function gameLabel(game) {
    var v = game.vault || {};
    if (v.away && v.home) return v.away + ' at ' + v.home;
    return String(game.ev || '');
  }
  /* "Under 144.5", "Jaguars -6.5", "Trail Blazers ML". The line is the stored sf line; none is invented. */
  function playTitle(game, g, sf) {
    var side = sf.side;
    if (g === 'ml') return side + ' ML';
    var l = g === 'spread' ? fmt.line(sf.line, { signed: true }) : fmt.line(sf.line);
    return l != null ? side + ' ' + l : side;
  }
  function marketLabel(g) { return T.market[g] || String(g || ''); }

  /* shown plays: not frozen, not started, shown size above zero. cards: the live.json object. */
  function collectPlays(cards, nowT) {
    var out = [];
    ((cards && cards.games) || []).forEach(function (game) {
      if (!game || game.frozen) return;
      if (isNum(game.gst) && game.gst <= nowT) return;
      Object.keys(game.markets || {}).forEach(function (g) {
        var units = rules.shownUnits(game, g), sf = sfOf(mktOf(game, g));
        /* CFB: the play shows with its tier and no size (the rule gives none there) */
        if (units <= 0 && !(lc(game.sport) === 'cfb' && sf && sf.side)) return;
        var tier = rules.tierOf(game, g, { noSize: true }), facts = rules.factsOf(game, g);
        if (!sf || !facts || tier === 'none') return;
        out.push({
          key: game.ev + '|' + g, game: game, g: g, sf: sf, units: units, tier: tier, facts: facts,
          cut: game.cut, band: rules.bandOf(game.cut, nowT), sport: lc(game.sport)
        });
      });
    });
    return out;
  }
  /* the default order, inside a freeze band: tier order, then past-winner wallets on the side (descending), then freeze time, then key */
  function baseCmp(a, b) {
    var ord = copy.tierOrder;
    return ord.indexOf(a.tier) - ord.indexOf(b.tier) ||
      (b.facts.proven - a.facts.proven) ||
      ((a.cut || 0) - (b.cut || 0)) ||
      (a.key < b.key ? -1 : a.key > b.key ? 1 : 0);
  }
  function sortPlays(list) { return list.slice().sort(baseCmp); }

  /* the price against Pinnacle's no-vig fair, in points: the stored v2.vs_fair.pts, else the stored sf signal the facts read. null when neither is stored. */
  function fairPts(p) {
    var m = mktOf(p.game, p.g), vf = m && m.v2 && m.v2.vs_fair;
    if (vf && isNum(vf.pts)) return vf.pts;
    return p.facts && isNum(p.facts.pts) ? p.facts.pts : null;
  }
  /* sortable columns. dir is the first-click direction: 1 ascending, -1 descending. Freezes is the default and is the only one with bands. */
  var SORTS = { freeze: { label: 'Freezes', dir: 1 }, price: { label: 'Price', dir: -1 }, fair: { label: 'vs fair', dir: -1 }, tier: { label: 'Tier', dir: 1 }, size: { label: 'Size', dir: -1 } };
  var SORT_ORDER = ['freeze', 'price', 'fair', 'tier', 'size'];
  function cleanSort(o) {
    var k = o && SORTS[o.k] ? o.k : 'freeze';
    return { k: k, dir: o && (o.dir === 1 || o.dir === -1) ? o.dir : SORTS[k].dir };
  }
  /* what a header click does: the active column flips direction, another column starts at its own first direction */
  function nextSort(cur, k) {
    if (!SORTS[k]) return cleanSort(cur);
    return cur && cur.k === k ? { k: k, dir: -cur.dir } : { k: k, dir: SORTS[k].dir };
  }
  function sortValue(p, k) {
    if (k === 'freeze') return isNum(p.cut) ? p.cut : null;
    if (k === 'price') return isNum(p.sf.price) ? p.sf.price : null;
    if (k === 'fair') return fairPts(p);
    if (k === 'tier') { var i = copy.tierOrder.indexOf(p.tier); return i < 0 ? null : i; }
    if (k === 'size') return p.units > 0 ? p.units : 0;
    return null;
  }
  /* a missing value sorts last in either direction; ties fall back to the default order */
  function sortFlat(list, k, dir) {
    var d = dir === -1 ? -1 : 1;
    return list.slice().sort(function (a, b) {
      var x = sortValue(a, k), y = sortValue(b, k);
      if (x == null && y != null) return 1;
      if (y == null && x != null) return -1;
      if (x != null && y != null && x !== y) return (x - y) * d;
      return baseCmp(a, b);
    });
  }
  /* freeze bands, in time order (dir -1 reverses the bands), rows inside a band in the default order */
  function groupBands(list, dir) {
    var out = T.bandOrder.map(function (b) {
      var rows = sortPlays(list.filter(function (p) { return p.band === b; }));
      var first = rows.reduce(function (m, p) { return isNum(p.cut) && (m == null || p.cut < m) ? p.cut : m; }, null);
      return { band: b, rows: rows, first: first };
    }).filter(function (x) { return x.rows.length; });
    return dir === -1 ? out.reverse() : out;
  }
  /* what the table shows: bands for the Freezes sort, one flat list for any other */
  function viewOf(list, sort) {
    var s = cleanSort(sort);
    return s.k === 'freeze' ? { bands: groupBands(list, s.dir), rows: null } : { bands: null, rows: sortFlat(list, s.k, s.dir) };
  }

  /* ---- column cells (pure: the view only draws what these return) ---- */
  /* "vs fair" in points: {text, tone} where tone is pos (price better than fair), neg (worse), zero, or null with empty text when not stored */
  function vsFairCell(p) {
    var pts = fairPts(p);
    if (pts == null) return { text: '', tone: null };
    return { text: pts === 0 ? '0' : fmt.line(pts, { signed: true }), tone: pts > 0 ? 'pos' : pts < 0 ? 'neg' : 'zero' };
  }
  /* Action Network splits on the play's own side: whole percents, or null when the market has none */
  function splitCell(p) {
    var sp = SV2.splitsFor(p.game, p.g), s = sp && sp.sides && sp.sides[p.facts.side];
    if (!s) return null;
    var b = isNum(s.bets) ? Math.round(s.bets) : null, m = isNum(s.money) ? Math.round(s.money) : null;
    return b == null && m == null ? null : { bets: b, money: m };
  }
  /* wallets that beat the close on the play's side (for) and on the other side (against), plus past winners against.
     Stored v2.conflict first; null counts (college has no price tier) give {tiered:false}. */
  function walletsCell(p) {
    var m = mktOf(p.game, p.g), c = m && m.v2 && m.v2.conflict, f = p.facts;
    var forN = null, agN = null, pw = null;
    if (c) { forN = isNum(c.beats_for) ? c.beats_for : null; agN = isNum(c.beats_against) ? c.beats_against : null; pw = c.past_winner_against && isNum(c.past_winner_against.n) ? c.past_winner_against.n : null; }
    else if (f && f.tiered) { forN = f.b1.n; agN = f.a2.n; pw = f.a1.n; }
    if (forN == null || agN == null) return { tiered: false, forN: null, againstN: null, pwAgainst: null };
    return { tiered: true, forN: forN, againstN: agN, pwAgainst: pw };
  }
  /* the size cell: the flat 1u pill (NBA, NFL, CBB), the CFB words, or nothing */
  function sizeCell(p) {
    if (p.units > 0) return { kind: 'pill', units: p.units };
    return p.sport === 'cfb' ? { kind: 'none', text: T.noSize } : { kind: 'blank', text: '' };
  }

  function nextCut(cards, nowT) {
    var best = null;
    ((cards && cards.games) || []).forEach(function (game) {
      if (!game || game.frozen || !isNum(game.cut) || game.cut <= nowT) return;
      if (best == null || game.cut < best) best = game.cut;
    });
    return best;
  }

  /* counts and dollars on one side of a market, from stored fields only */
  function sideNums(game, g, name, tiered) {
    var a = sideAll(mktOf(game, g), name) || {}, c = a.counts || {}, rk = tiered && a.rk ? a.rk : null;
    return {
      pw: (c.hc || 0) + (c.sharp || 0), pwUsd: isNum(a.sharp_usd) ? a.sharp_usd : 0,
      beats: rk ? (rk.sharp_n || 0) : 0, beatsUsd: rk && isNum(rk.sharp_usd) ? rk.sharp_usd : 0,
      dull: rk ? (rk.dull_n || 0) : 0, dullUsd: rk && isNum(rk.dull_usd) ? rk.dull_usd : 0
    };
  }
  function otherSides(game, g, side) {
    return Object.keys((mktOf(game, g) || {}).sides || {}).filter(function (k) { return k !== side; });
  }
  function sumNums(game, g, names, tiered) {
    var t = { pw: 0, pwUsd: 0, beats: 0, beatsUsd: 0, dull: 0, dullUsd: 0 };
    names.forEach(function (n) { var x = sideNums(game, g, n, tiered); Object.keys(t).forEach(function (k) { t[k] += x[k]; }); });
    return t;
  }

  /* the one line that says what is against the play (collapsed row). Up to two phrases, then a count of the rest. */
  function reasonOf(p) {
    var f = p.facts, ph = [];
    if (p.tier === 'contested') {
      if (f.a1.on || f.a2.on) {
        var parts = [];
        if (f.a1.on) parts.push(plural(f.a1.n, 'past winner', 'past winners'));
        if (f.a2.on) parts.push(f.a2.n + ' that beat the close');
        ph.push(parts.join(' and ') + ' on the other side');
      }
      if (f.a3.on) ph.push('Wallets that lose to the close are on this side');
      if (f.a4.on) ph.push('Price ' + fmt.line(Math.abs(f.a4.pts)) + ' pts worse than Pinnacle\'s fair');
      if (ph.length > 2) return ph.slice(0, 2).join('. ') + '. +' + (ph.length - 2) + ' more';
      return ph.join('. ');
    }
    if (p.tier === 'thin') return 'One wallet, no price check';
    return copy.tier[p.tier] ? copy.tier[p.tier].why : '';
  }

  function tagOf(against, forIt) { return against && forIt ? 'both' : against ? 'against' : forIt ? 'for' : null; }
  var TAG_WORD = { against: 'Against', 'for': 'For', both: 'For and against' };

  /* price versus Pinnacle's no-vig fair, or why there is none. Returns {tag, text} */
  function fairLine(p) {
    var f = p.facts, sf = p.sf, ev = sf.signals && sf.signals.ev;
    if (f.pts != null) {
      var fair = ev && isNum(ev.fair) ? ' (' + fmt.cents(ev.fair) + ')' : '';
      var w = f.pts < 0 ? 'worse' : f.pts > 0 ? 'better' : 'level';
      var txt = 'Price vs Pinnacle\'s no-vig fair' + fair + ': ' + (f.pts === 0 ? 'level' : fmt.line(Math.abs(f.pts)) + ' pts ' + w);
      return { tag: tagOf(f.a4.on, f.b2.on), text: txt };
    }
    var why = ev && ev.why === 'ticket_line_not_main_at_cut' ? 'off Pinnacle\'s main line' : 'not stored';
    return { tag: null, text: 'No fair price: ' + why };
  }

  function evidenceLines(p) {
    var f = p.facts, m = mktOf(p.game, p.g), S = f.side, oth = otherSides(p.game, p.g, S);
    var mine = sideNums(p.game, p.g, S, f.tiered), other = sumNums(p.game, p.g, oth, f.tiered), L = [];
    L.push({
      tag: tagOf(f.a1.on, false),
      text: 'Past-winner wallets: ' + mine.pw + ' on this side, ' + other.pw + ' on the other' + (other.pw > 0 && other.pwUsd > 0 ? ' (' + fmt.usd(other.pwUsd) + ')' : '')
    });
    if (f.tiered) L.push({ tag: tagOf(f.a2.on, f.b1.on), text: 'Wallets that beat the close: ' + f.b1.n + ' on this side, ' + f.a2.n + ' on the other' });
    else L.push({ tag: null, text: T.collegeNoTier });
    if (f.a3.on) L.push({ tag: 'against', text: 'Wallets that lose to the close hold this side, so the fade rule picks the other side' });
    L.push(fairLine(p));
    if (m && m.sf && m.sf.fwd) L.push({ tag: f.b3.on ? 'for' : null, text: 'Same pick using only games since we started tracking these wallets: ' + (f.b3.on ? 'yes' : 'no') });
    L.push({ tag: f.b4.on ? 'for' : null, text: 'Distinct past-winner wallets on this side: ' + f.proven });
    return L;
  }

  /* extra price lines, each only when plays-data publishes the field */
  function execLines(sf) {
    var L = [], ex = sf.exec || {}, t;
    if (ex.pm_ask && isNum(ex.pm_ask.px)) { t = ct.time(ex.pm_ask.t, true); L.push('Polymarket ask ' + fmt.cents(ex.pm_ask.px) + (t ? ' (' + t + ')' : '')); }
    if (ex.us_best && isNum(ex.us_best.odds)) {
      t = ct.time(ex.us_best.t, true);
      L.push('Best US book on this line: ' + (ex.us_best.odds > 0 ? '+' : '') + Math.round(ex.us_best.odds) + (ex.us_best.book ? ' at ' + ex.us_best.book : '') + (t ? ' (' + t + ')' : ''));
    }
    if (ex.kalshi && isNum(ex.kalshi.px)) { t = ct.time(ex.kalshi.t, true); L.push('Kalshi ' + fmt.cents(ex.kalshi.px) + (t ? ' (' + t + ')' : '')); }
    if (ex.novig && isNum(ex.novig.px)) { t = ct.time(ex.novig.t, true); L.push('Novig ' + fmt.cents(ex.novig.px) + (t ? ' (' + t + ')' : '')); }
    if (sf.close_vs_fair && isNum(sf.close_vs_fair.pts)) L.push('Pinnacle close vs fair: ' + fmt.line(sf.close_vs_fair.pts, { signed: true }) + ' pts');
    return L;
  }

  /* rows with past-winner money on a side but no shown play, one per game (the market with the most past-winner money).
     CFB games where the rule picked a side say "No play on CFB" and name no side. */
  function contextRows(cards, plays, nowT) {
    var played = {}; plays.forEach(function (p) { played[p.key] = 1; });
    var rows = [];
    ((cards && cards.games) || []).forEach(function (game) {
      if (!game || game.frozen) return;
      if (isNum(game.gst) && game.gst <= nowT) return;
      var best = null, cfbPick = false;
      Object.keys(game.markets || {}).forEach(function (g) {
        var m = game.markets[g], sf = sfOf(m);
        if (played[game.ev + '|' + g]) return;
        if (lc(game.sport) === 'cfb' && sf && sf.side) cfbPick = true;
        Object.keys(m.sides || {}).forEach(function (name) {
          var a = sideAll(m, name), usd = a && isNum(a.sharp_usd) ? a.sharp_usd : 0;
          if (usd > 0 && (!best || usd > best.usd)) best = { g: g, side: name, usd: usd };
        });
      });
      if (!best && !cfbPick) return;
      rows.push({ game: game, sport: lc(game.sport), cfb: lc(game.sport) === 'cfb' && cfbPick, best: best, usd: best ? best.usd : 0 });
    });
    return rows.sort(function (a, b) { return b.usd - a.usd || ((a.game.cut || 0) - (b.game.cut || 0)); });
  }

  function passes(p, f, except, wallet, sameMap) {
    if (except !== 'sport' && f.sport !== 'all' && p.sport !== f.sport) return false;
    if (except !== 'tier' && f.tier !== 'all' && p.tier !== f.tier) return false;
    if (except !== 'market' && f.market !== 'all' && p.g !== f.market) return false;
    if (except !== 'starts' && f.starts !== 'all') {
      if (f.starts === 'hour' && p.band !== 'hour') return false;
      if (f.starts === 'today' && p.band !== 'hour' && p.band !== 'today') return false;
    }
    if (wallet && !(sameMap[wallet] && sameMap[wallet].keys.indexOf(p.key) >= 0)) return false;
    return true;
  }
  var FILTER_VALUES = {
    sport: ['all'].concat(SPORT_ORDER),
    tier: ['all'].concat(copy.tierOrder),
    market: ['all'].concat(T.marketOrder),
    starts: ['all', 'hour', 'today']
  };
  function cleanFilters(o) {
    var f = { sport: 'all', tier: 'all', market: 'all', starts: 'all' };
    if (o && typeof o === 'object') Object.keys(f).forEach(function (k) { if (FILTER_VALUES[k].indexOf(o[k]) >= 0) f[k] = o[k]; });
    return f;
  }

  SV2.sharpsPage = {
    collectPlays: collectPlays, sortPlays: sortPlays, groupBands: groupBands, reasonOf: reasonOf, evidenceLines: evidenceLines,
    contextRows: contextRows, passes: passes, cleanFilters: cleanFilters, playTitle: playTitle, gameLabel: gameLabel, nextCut: nextCut,
    execLines: execLines, fairLine: fairLine,
    SORTS: SORTS, SORT_ORDER: SORT_ORDER, cleanSort: cleanSort, nextSort: nextSort, sortFlat: sortFlat, viewOf: viewOf, fairPts: fairPts,
    vsFairCell: vsFairCell, splitCell: splitCell, walletsCell: walletsCell, sizeCell: sizeCell
  };

  /* ------------------------------------------------------------------ view */
  function lsGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* storage unavailable: the filters just do not persist */ } }
  function loadFilters() { var o = null; try { o = JSON.parse(lsGet(FKEY)); } catch (e) { o = null; } return cleanFilters(o); }

  function walletRow(w, sport) {
    var ws = store.wallets && store.wallets.sports && store.wallets.sports[sport];
    return ws && ws[w] || null;
  }

  /* wallets on one side: past winners (all.list) merged with the wallets that beat the close (rk.list, NBA and NFL only) */
  function sideWallets(game, g, name) {
    var m = mktOf(game, g), a = sideAll(m, name), sport = lc(game.sport), tiered = sport === 'nba' || sport === 'nfl', by = {}, order = [];
    function slot(w) { if (!by[w]) { by[w] = { w: w, usd: 0, press: null, past: false, beats: false }; order.push(w); } return by[w]; }
    if (!a) return [];
    (a.list || []).forEach(function (r) {
      if (!r || !r.w || (r.class !== 'hc' && r.class !== 'sharp')) return;
      var s = slot(r.w); s.past = true; s.usd = Math.max(s.usd, isNum(r.usd) ? r.usd : 0); if (isNum(r.press)) s.press = r.press;
    });
    if (tiered && a.rk) (a.rk.list || []).forEach(function (r) {
      if (!r || !r.w) return;
      var s = slot(r.w); s.beats = true; if (isNum(r.n)) s.n = r.n; s.usd = Math.max(s.usd, isNum(r.usd) ? r.usd : 0);
    });
    return order.map(function (w) {
      var s = by[w], row = walletRow(w, sport);
      s.row = row; s.tier = tiered ? rules.v2TierOf(row, sport) : 'few';
      if (s.tier === 'beats') s.beats = true;
      if (s.beats) s.tier = 'beats';
      s.name = row ? rules.nameOf(row, w) : (fmt.addr(w) || w);
      return s;
    }).sort(function (x, y) { return y.usd - x.usd || (x.w < y.w ? -1 : 1); });
  }

  function chip(text, kind) { return ui.chip(text, kind); }

  function walletHtml(game, g, side, s) {
    var sport = lc(game.sport), chips = '';
    if (s.past) chips += chip(copy.chip.past, 'muted');
    if (s.tier === 'beats' || s.tier === 'even' || s.tier === 'loses') {
      var n = s.row && s.row.rk && isNum(s.row.rk.n) ? s.row.rk.n : (isNum(s.n) ? s.n : null);
      chips = ui.acct(s.tier, { n: n }) + chips;
    }
    var press = isNum(s.press) ? '<span class="sv2-num">' + esc(fmt.mult(s.press)) + '</span> average cost' : '';
    var usd = fmt.usd(s.usd);
    return '<a class="sv2-sp-w sv2-press sv2-press-row" href="#following/acct/' + esc(encodeURIComponent(sport)) + '/' + esc(encodeURIComponent(s.w)) + '" data-sv2-acct data-sport="' + esc(sport) + '" data-w="' + esc(s.w) + '" data-ev="' + esc(game.ev) + '" data-g="' + esc(g) + '" data-side="' + esc(side) + '" data-fid="w:' + esc(game.ev + '|' + g + '|' + side + '|' + s.w) + '">' +
      '<span class="sv2-sp-wl1"><span class="sv2-ell sv2-sp-wname" data-sv2-name>' + esc(s.name) + '</span>' + (usd ? '<span class="sv2-num sv2-sp-wusd">' + esc(usd) + '</span>' : '') + '</span>' +
      '<span class="sv2-sp-wl2">' + chips + (press ? '<span class="sv2-sp-wpress">' + press + '</span>' : '') + '</span>' +
      '</a>';
  }

  function moneyHtml(p) {
    var m = mktOf(p.game, p.g), names = Object.keys(m.sides || {}), S = p.facts.side, order = [S].concat(names.filter(function (n) { return n !== S; }));
    var rows = order.map(function (n) {
      var a = sideAll(m, n) || {};
      var pw = isNum(a.sharp_usd) ? a.sharp_usd : 0, oth = (isNum(a.unproven_usd) ? a.unproven_usd : 0) + (isNum(a.excluded_usd) ? a.excluded_usd : 0), los = isNum(a.loser_usd) ? a.loser_usd : 0;
      return { n: n, pw: pw, oth: oth, los: los, tot: pw + oth + los };
    });
    var max = rows.reduce(function (x, r) { return Math.max(x, r.tot); }, 0);
    var bars = rows.map(function (r) {
      var seg3 = r.tot > 0 ? [['s-win', r.pw], ['s-oth', r.oth], ['s-los', r.los]].filter(function (s) { return s[1] > 0; }).map(function (s) {
        return '<i class="' + s[0] + '" style="width:' + (s[1] / r.tot * 100).toFixed(2) + '%"></i>';
      }).join('') : '';
      var w = max > 0 ? (r.tot / max * 100) : 0;
      return '<div class="sv2-sp-mrow"><div class="sv2-sp-mh"><span class="sv2-ell">' + esc(r.n) + '</span><span class="sv2-num sv2-mut">' + esc(fmt.usd(r.tot) || '') + '</span></div>' +
        '<div class="sv2-bar" role="img" aria-label="' + esc(r.n + ': ' + (fmt.usd(r.pw) || '$0') + ' past-winner money, ' + (fmt.usd(r.oth) || '$0') + ' other money, ' + (fmt.usd(r.los) || '$0') + ' losing-record money') + '" style="width:' + w.toFixed(2) + '%">' + seg3 + '</div></div>';
    }).join('');
    var tot = rows.map(function (r) { return (fmt.usd(r.pw) || '$0') + ' past-winner money on ' + r.n; }).join(', ');
    return bars +
      '<p class="sv2-sp-legend"><span><i class="sv2-sp-sw s-win"></i>' + T.legend[0] + '</span><span><i class="sv2-sp-sw s-oth"></i>' + T.legend[1] + '</span><span><i class="sv2-sp-sw s-los"></i>' + T.legend[2] + '</span></p>' +
      '<p class="sv2-sp-note">' + esc(tot) + '</p>';
  }

  function walletsHtml(p) {
    var m = mktOf(p.game, p.g), S = p.facts.side, names = Object.keys(m.sides || {}), order = [S].concat(names.filter(function (n) { return n !== S; })), tiered = p.facts.tiered;
    return order.map(function (n) {
      var nums = sideNums(p.game, p.g, n, tiered), ws = sideWallets(p.game, p.g, n), head;
      if (tiered) {
        head = esc(n) + ': ' + nums.beats + ' that beat the close' + (nums.beats > 0 && nums.beatsUsd > 0 ? ' (' + esc(fmt.usd(nums.beatsUsd)) + ')' : '') + ', ' +
          nums.dull + ' that lose to the close' + (nums.dull > 0 && nums.dullUsd > 0 ? ' (' + esc(fmt.usd(nums.dullUsd)) + ')' : '') + '. Past-winner money ' + esc(fmt.usd(nums.pwUsd) || '$0') + '.';
      } else head = esc(n) + ': past-winner money ' + esc(fmt.usd(nums.pwUsd) || '$0') + '.';
      return '<div class="sv2-sp-ws"><p class="sv2-sp-wh' + (n === S ? ' is-play' : '') + '">' + head + '</p>' +
        (ws.length ? ws.map(function (s) { return walletHtml(p.game, p.g, n, s); }).join('') : '<p class="sv2-sp-note">No past-winner wallets or wallets that beat the close are listed on this side.</p>') + '</div>';
    }).join('');
  }

  function splitHtml(p) {
    var sp = SV2.splitsFor(p.game, p.g);
    if (!sp || !sp.sides) return '';
    var S = p.facts.side, names = Object.keys((mktOf(p.game, p.g) || {}).sides || {}), rows = '';
    names = [S].concat(names.filter(function (n) { return n !== S; }));
    names.forEach(function (n) {
      var s = sp.sides[n]; if (!s) return;
      var b = fmt.pctInt(s.bets), mo = fmt.pctInt(s.money);
      if (b == null && mo == null) return;
      rows += '<li class="sv2-sp-split"><span class="sv2-ell">' + esc(n) + '</span><span>' + (b != null ? '<span class="sv2-num">' + esc(b) + '</span> of bets' : '') + '</span><span>' + (mo != null ? '<span class="sv2-num">' + esc(mo) + '</span> of money' : '') + '</span></li>';
    });
    if (!rows) return '';
    var t = isNum(sp.t) ? ct.time(sp.t, true) : null;
    return '<section class="sv2-sp-sec"><h3 class="sv2-h2">Public split</h3><ul class="sv2-sp-splits">' + rows + '</ul>' +
      '<p class="sv2-sp-note">' + esc((sp.src || 'Action Network') + (t ? ', read ' + t : '') + '. Context only.') + '</p></section>';
  }

  function moreHtml(p) {
    var sf = p.sf, m = mktOf(p.game, p.g), L = [], a = sideAll(m, p.facts.side) || {};
    if (sf.rung) L.push('Staking rule step: ' + sf.rung + (Array.isArray(sf.missing) ? '. Parts of the outside rule Vault does not run: ' + sf.missing.length : ''));
    if (a.ags && isNum(a.ags.score)) L.push('Staking-rule score ' + fmt.line(a.ags.score, { signed: true }) + ' (cut points fitted outside Vault, not tested here)');
    if (isNum(sf.units) && sf.units > 0) L.push('Old size ladder (shadow, not a size): ' + fmt.units(sf.units));
    var st = sf.steam || {}, lim = sf.signals && sf.signals.limit || {};
    var moved = isNum(st.line_open) && isNum(st.line_now) ? 'Line ' + fmt.line(st.line_open) + ' at open, ' + fmt.line(st.line_now) + ' now' : null;
    var limit = lim && isNum(lim.open) && isNum(lim.now) ? 'Pinnacle limit ' + fmt.usd(lim.open, { full: true }) + ' to ' + fmt.usd(lim.now, { full: true }) : null;
    if (moved || limit) L.push([moved, limit].filter(Boolean).join('. ') + '.');
    else L.push('Pinnacle line move: not readable for this line');
    var pr = a.proven;
    if (pr && isNum(pr.w) && isNum(pr.l) && pr.w + pr.l > 0) {
      var n = pr.w + pr.l;
      L.push('Past record of the past-winner wallets on this side (includes games before we tracked them, picked after the fact): ' + fmt.wl(pr.w, pr.l) + ', n=' + n + (n < 30 ? ', small sample' : ''));
    }
    var src = sf.price_src === 'pm' ? 'Polymarket\'s displayed price (a mid or last trade, not the price you would get).' : sf.price_src === 'pin' ? 'Pinnacle\'s price (Polymarket had none).' : T.priceNote;
    L.push(src);
    return '<ul class="sv2-sp-more-l">' + L.map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('') + '</ul>';
  }

  function priceHtml(p) {
    var sf = p.sf, c = fmt.cents(sf.price), am = fmt.american(sf.price), t = isNum(sf.price_t) ? ct.time(sf.price_t, true) : null, gst = p.game.gst;
    var src = sf.price_src === 'pm' ? 'Polymarket ' : sf.price_src === 'pin' ? 'Pinnacle ' : '';
    var line = '';
    if (c) line = '<p class="sv2-sp-pl">' + esc(src) + '<b class="sv2-num sv2-sp-pbig">' + esc(c) + '</b>' + (am ? ' <span class="sv2-num sv2-mut">(' + esc(am) + ')</span>' : '') + ' at the last read' + (t ? ', ' + esc(t) : '') + '</p>';
    var when = [];
    if (isNum(gst)) when.push('Game starts ' + ct.day(gst) + ' ' + ct.time(gst, true));
    if (isNum(p.cut)) when.push('freezes ' + ct.time(p.cut, true));
    var ex = execLines(sf);
    return line + (when.length ? '<p class="sv2-sp-note">' + esc(when.join(', ')) + '</p>' : '') +
      (ex.length ? '<ul class="sv2-sp-ex">' + ex.map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('') + '</ul>' : '');
  }

  function detailHtml(p, moreOpen) {
    var ev = evidenceLines(p).map(function (l) {
      return '<li class="sv2-sp-evl"><span class="sv2-sp-evt' + (l.tag ? ' is-' + l.tag : '') + '">' + esc(l.tag ? TAG_WORD[l.tag] : '') + '</span><span>' + esc(l.text) + '</span></li>';
    }).join('');
    var mid = esc(p.key.replace(/[^a-z0-9]+/gi, '-'));
    return '<div class="sv2-sp-body">' +
      '<div class="sv2-sp-col">' +
      '<section class="sv2-sp-sec"><h3 class="sv2-h2">Price</h3>' + priceHtml(p) + '</section>' +
      '<section class="sv2-sp-sec"><h3 class="sv2-h2">What is stored for and against</h3><ul class="sv2-sp-ev">' + ev + '</ul></section>' +
      '</div><div class="sv2-sp-col">' +
      '<section class="sv2-sp-sec"><h3 class="sv2-h2">Money on each side</h3>' + moneyHtml(p) + '</section>' +
      '<section class="sv2-sp-sec"><h3 class="sv2-h2">Who holds it</h3>' + walletsHtml(p) + '</section>' +
      splitHtml(p) +
      '</div></div>' +
      '<div class="sv2-sp-morewrap"><button type="button" class="sv2-sp-more sv2-press sv2-press-btn" aria-expanded="' + (moreOpen ? 'true' : 'false') + '" aria-controls="sv2-sp-m-' + mid + '" data-sp-more="' + esc(p.key) + '" data-fid="more:' + esc(p.key) + '">More detail' + ui.icon('chevron', 'sv2-chev') + '</button>' +
      '<div class="sv2-x" id="sv2-sp-m-' + mid + '"' + (moreOpen ? ' data-open' : '') + '><div class="sv2-x-in">' + moreHtml(p) + '</div></div></div>';
  }

  /* ---- the plays table ---- */
  var COLS = [
    { c: 'time', label: 'Freezes', k: 'freeze' }, { c: 'sport', label: 'Sport' }, { c: 'play', label: 'Play' }, { c: 'mkt', label: 'Market' },
    { c: 'px', label: 'Price', k: 'price' }, { c: 'fair', label: 'vs fair (pts)', k: 'fair' }, { c: 'tier', label: 'Tier', k: 'tier' },
    { c: 'spl', label: 'Bets vs money on the play' }, { c: 'wal', label: 'Wallets that beat the close' }, { c: 'size', label: 'Size', k: 'size' },
    { c: 'chev', label: '', sr: 'Details' }
  ];

  function timeText(p) {
    if (!isNum(p.cut)) return '';
    return p.band === 'hour' || p.band === 'today' ? ct.time(p.cut) : ct.dayTime(p.cut);
  }
  function q(s) { return String(s).replace(/"/g, '\\"'); }
  function keyId(prefix, key) { return prefix + key.replace(/[^a-z0-9]+/gi, '-'); }

  function splitCellHtml(p) {
    var s = splitCell(p);
    if (!s) return '<span class="sv2-tb-na">n/a</span>';
    return '<span class="sv2-tb-spl"><span class="sv2-tb-st">' + (s.bets != null ? '<span><span class="sv2-num">' + s.bets + '%</span> bets</span>' : '') +
      (s.money != null ? '<span><span class="sv2-num">' + s.money + '%</span> money</span>' : '') + '</span>' +
      (s.money != null ? '<span class="sv2-tb-sbar" aria-hidden="true"><i style="width:' + s.money + '%"></i></span>' : '') + '</span>';
  }
  function walletsCellHtml(p) {
    var w = walletsCell(p);
    if (!w.tiered) return '<span class="sv2-tb-na">no price tier here</span>';
    return '<span class="sv2-tb-h"><span class="sv2-num">' + w.forN + '</span> for</span><span class="sv2-tb-h is-ag"><span class="sv2-num">' + w.againstN + '</span> against</span>' +
      (w.pwAgainst > 0 ? '<span class="sv2-tb-sub">' + esc(plural(w.pwAgainst, 'past winner', 'past winners')) + ' against</span>' : '');
  }
  function sizeCellHtml(p) {
    var z = sizeCell(p);
    if (z.kind === 'pill') return ui.playPill(z.units);
    return z.text ? '<span class="sv2-nosize">' + esc(z.text) + '</span>' : '';
  }

  function rowHtml(p, st, sameKeys) {
    var open = !!st.open[p.key], id = keyId('sv2-sp-x-', p.key);
    var title = playTitle(p.game, p.g, p.sf), c = fmt.cents(p.sf.price), reason = reasonOf(p), vf = vsFairCell(p);
    var label = title + ', ' + gameLabel(p.game) + ', ' + (copy.tier[p.tier] ? copy.tier[p.tier].word : '') + '. ' + (reason || '');
    var ncol = COLS.length;
    var tr = '<tr class="sv2-tb-r' + (open ? ' is-open' : '') + '" data-key="' + esc(p.key) + '" data-tier="' + esc(p.tier) + '">' +
      '<td class="sv2-tb-c c-time sv2-num">' + esc(timeText(p)) + '</td>' +
      '<td class="sv2-tb-c c-sport">' + ui.chip(SV2.sportName(p.sport), 'muted') + '</td>' +
      '<td class="sv2-tb-c c-play"><span class="sv2-tb-title"><b>' + esc(title) + '</b>' + (sameKeys[p.key] ? ' ' + ui.chip(T.sameTag, 'muted') : '') + '</span><span class="sv2-tb-mu">' + ui.matchup(p.game, gameLabel(p.game)) + '</span></td>' +
      '<td class="sv2-tb-c c-mkt">' + esc(marketLabel(p.g)) + '</td>' +
      '<td class="sv2-tb-c c-px sv2-num">' + esc(c || '') + '</td>' +
      '<td class="sv2-tb-c c-fair sv2-num' + (vf.tone ? ' is-' + vf.tone : '') + '">' + esc(vf.text) + '</td>' +
      '<td class="sv2-tb-c c-tier">' + ui.tier(p.tier) + '</td>' +
      '<td class="sv2-tb-c c-spl">' + splitCellHtml(p) + '</td>' +
      '<td class="sv2-tb-c c-wal">' + walletsCellHtml(p) + '</td>' +
      '<td class="sv2-tb-c c-size">' + sizeCellHtml(p) + '</td>' +
      '<td class="sv2-tb-c c-chev"><button type="button" class="sv2-tb-tog sv2-press sv2-press-btn" aria-expanded="' + open + '" aria-controls="' + id + '" aria-label="' + esc(label) + '" data-sp-row="' + esc(p.key) + '" data-fid="row:' + esc(p.key) + '">' + ui.icon('chevron', 'sv2-chev') + '</button></td></tr>';
    var dr = '<tr class="sv2-tb-d" data-dkey="' + esc(p.key) + '"><td colspan="' + ncol + '"><div class="sv2-x" id="' + id + '"' + (open ? ' data-open' : '') + '><div class="sv2-x-in" role="region" aria-label="' + esc(label) + '">' +
      (open ? detailHtml(p, !!st.more[p.key]) : '') + '</div></div></td></tr>';
    return tr + dr;
  }

  function countdownText(cut, nowT) { return isNum(cut) ? ct.countdown(cut - nowT) : null; }

  function bandRowHtml(b, nowT) {
    var meta = isNum(b.first) ? '<span class="sv2-sp-bmeta sv2-num">' + esc(ct.time(b.first, true)) + ' <span class="sv2-sp-dot" aria-hidden="true"></span> <span data-sp-cd data-cut="' + b.first + '">' + esc(countdownText(b.first, nowT) || '') + '</span></span>' : '';
    return '<tr class="sv2-tb-band"><th scope="colgroup" colspan="' + COLS.length + '"><span class="sv2-tb-bw"><span class="sv2-h2">' + esc(T.band[b.band]) + '</span>' + meta + '</span></th></tr>';
  }
  function theadHtml(sort) {
    var s = cleanSort(sort);
    return '<thead><tr>' + COLS.map(function (c) {
      if (c.sr) return '<th scope="col" class="c-' + c.c + '"><span class="sv2-sr">' + c.sr + '</span></th>';
      if (!c.k) return '<th scope="col" class="c-' + c.c + '">' + esc(c.label) + '</th>';
      var on = s.k === c.k;
      return '<th scope="col" class="c-' + c.c + ' is-sort" aria-sort="' + (on ? (s.dir === 1 ? 'ascending' : 'descending') : 'none') + '"><button type="button" class="sv2-tb-sort sv2-press sv2-press-chip" data-sp-sort="' + c.k + '" data-fid="sort:' + c.k + '">' + esc(c.label) + ui.sortArrow(on, s.dir) + '</button></th>';
    }).join('') + '</tr></thead>';
  }
  function tableHtml(vis, st, sameKeys, nowT) {
    var v = viewOf(vis, st.sort), body;
    if (v.bands) body = v.bands.map(function (b) { return bandRowHtml(b, nowT) + b.rows.map(function (p) { return rowHtml(p, st, sameKeys); }).join(''); }).join('');
    else body = v.rows.map(function (p) { return rowHtml(p, st, sameKeys); }).join('');
    return '<div class="sv2-card sv2-tb-card"><div class="sv2-tb-scroll"><table class="sv2-tb" aria-label="Plays">' + theadHtml(st.sort) + '<tbody>' + body + '</tbody></table></div></div>';
  }
  function sortWord(s) { return SORTS[s.k].label + ', ' + (s.dir === 1 ? 'ascending' : 'descending'); }

  function ctxItemHtml(r) {
    var v = r.game, bits = '<span class="sv2-sp-cg">' + esc(gameLabel(v)) + '</span>' + ui.chip(SV2.sportName(r.sport), 'muted');
    if (r.cfb) return '<li class="sv2-sp-crow">' + bits + '<span class="sv2-mut">' + esc(T.ctxCfb) + '</span></li>';
    return '<li class="sv2-sp-crow">' + bits + '<span>' + esc(r.best.side + (r.best.g === 'ml' ? '' : ' ' + marketLabel(r.best.g))) + '</span><span class="sv2-num sv2-sp-cusd">' + esc(fmt.usd(r.usd) || '') + '</span></li>';
  }
  function ctxHtml(rows, st) {
    if (!rows.length) return '';
    var open = st.ctxOpen != null ? st.ctxOpen : false;
    var n = Math.min(st.ctxN, rows.length), more = rows.length - n;
    return '<h2 class="sv2-sp-ctxh"><button type="button" class="sv2-sp-ctxbtn sv2-press sv2-press-row" aria-expanded="' + open + '" aria-controls="sv2-sp-ctxx" data-sp-ctx data-fid="ctx">' +
      '<span>Context: ' + esc(fmt.n(rows.length)) + ' games with past-winner money on a side, no play</span><span class="sv2-sp-ctxs">' + (open ? 'Hide' : 'Show') + '</span>' + ui.icon('chevron', 'sv2-chev') + '</button></h2>' +
      '<div class="sv2-x" id="sv2-sp-ctxx"' + (open ? ' data-open' : '') + '><div class="sv2-x-in"><ul class="sv2-sp-ctxl">' + rows.slice(0, n).map(ctxItemHtml).join('') + '</ul>' +
      (more > 0 ? '<button type="button" class="sv2-sp-btn sv2-press sv2-press-btn" data-sp-ctxmore data-fid="ctxmore">Show ' + Math.min(CTX_STEP, more) + ' more</button>' : '') + '</div></div>';
  }

  /* ------------------------------------------------------------------ mount */
  SV2.register('sharps', function mount(el) {
    var st = { f: loadFilters(), sort: cleanSort(null), wallet: null, open: {}, more: {}, ctxOpen: null, ctxN: CTX_STEP, panel: false, deep: null, shell: false, sig: '', lastBands: '' };
    var refs = {}, model = null;
    function on(name, fn) { SV2.on(name, function (a) { if (document.contains(el)) fn(a); }); }   /* a re-mounted tab leaves the old closures behind: they stay quiet */

    function nowT() { return SV2.now(); }

    function setLive(msg) { var l = document.getElementById('sv2-live'); if (l && msg) l.textContent = msg; }

    function compute() {
      var cards = store.cards, now = nowT(), all = collectPlays(cards, now);
      var same = rules.sameWallet(all.map(function (p) { return { game: p.game, g: p.g }; })), sameMap = {}, sameKeys = {};
      same.forEach(function (r) { sameMap[r.w] = r; r.keys.forEach(function (k) { sameKeys[k] = 1; }); });
      if (st.wallet && !sameMap[st.wallet]) st.wallet = null;
      var vis = all.filter(function (p) { return passes(p, eff(), null, st.wallet, sameMap); });
      var ctx = contextRows(cards, all, now);
      return { now: now, all: all, same: same, sameMap: sameMap, sameKeys: sameKeys, vis: vis, ctx: ctx, next: nextCut(cards, now) };
    }

    /* ---- shell: built once, when the first data lands. One toolbar row: summary on the left, Filters on the right.
       Sport is the host's (Sharp Money header chips); only a host that does not supply one gets V2's own sport strip. ---- */
    var STARTS = [['all', 'All'], ['hour', 'Next hour'], ['today', 'Today']];
    function eff() { var f = Object.assign({}, st.f), hs = SV2.hostSport(); if (hs != null) f.sport = hs; return f; }
    function isPhone() { return !!(window.matchMedia && window.matchMedia('(max-width: 767px)').matches); }
    function groupItems(key) {
      if (key === 'tier') return [['all', 'All']].concat(copy.tierOrder.map(function (t) { return [t, copy.tier[t].word]; }));
      if (key === 'market') return [['all', 'All']].concat(T.marketOrder.map(function (m) { return [m, T.market[m]]; }));
      return STARTS;
    }
    var GROUPS = [['tier', 'Evidence tier'], ['market', 'Market'], ['starts', 'Starts']];
    function buildShell() {
      st.hasHost = SV2.hostSport() != null;
      var sports = [['all', 'All']].concat(SPORT_ORDER.map(function (s) { return [s, SV2.sportName(s)]; }));
      var sportRow = st.hasHost ? '' : '<div class="sv2-sp-sportrow">' + seg.html({ id: 'sp-sport', label: 'Sport', value: st.f.sport, size: 'sm', scroll: true, items: sports.map(function (it) { return { v: it[0], label: it[1], count: 0 }; }) }) + '</div>';
      el.innerHTML =
        '<div class="sv2-cols sv2-sp"><div class="sv2-sp-main">' +
        '<div class="sv2-sp-bar"><p class="sv2-sp-sum" data-sp="sum"></p>' +
        '<div class="sv2-sp-acts" data-sp="acts"><div class="sv2-sp-fwrap">' +
        '<button type="button" class="sv2-sp-ftog sv2-press sv2-press-btn" data-sp-ftog aria-haspopup="dialog" aria-expanded="false" aria-controls="sv2-sp-pop">' +
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h10M18 7h2M4 17h2M10 17h10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="16" cy="7" r="2.2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="8" cy="17" r="2.2" fill="none" stroke="currentColor" stroke-width="2"/></svg>' +
        '<span>Filters</span><span class="sv2-sp-badge sv2-num" data-sp="badge" hidden></span></button>' +
        '<button type="button" class="sv2-sp-fclr sv2-press sv2-press-chip" data-sp-clear aria-label="Clear filters" hidden>' + ui.icon('close') + '</button>' +
        '<div class="sv2-sp-pop" id="sv2-sp-pop" data-sp="pop" role="dialog" aria-label="Filters" hidden></div></div></div></div>' +
        sportRow +
        '<div class="sv2-sp-active" data-sp="active" hidden></div>' +
        '<div class="sv2-sp-same" data-sp="same"></div>' +
        '<div data-sp="list"></div>' +
        '<section class="sv2-sp-ctx" data-sp="ctx" aria-label="Games with no play"></section>' +
        '</div><aside class="sv2-col-rail sv2-sp-rail" data-sp="rail" aria-label="Summary"></aside></div>';
      ['sum', 'acts', 'badge', 'pop', 'active', 'same', 'list', 'ctx', 'rail'].forEach(function (k) { refs[k] = el.querySelector('[data-sp="' + k + '"]'); });
      refs.strips = {}; var ss = el.querySelector('[data-rail-id="sp-sport"]');
      if (ss) { refs.strips.sport = ss; seg.bind(ss, function (v) { st.f.sport = v; lsSet(FKEY, JSON.stringify(st.f)); paint(true, true); }); }
      refs.ftog = el.querySelector('[data-sp-ftog]'); refs.clear = el.querySelector('[data-sp-clear]');
      st.shell = true;
    }

    function facetValue(p, k, v) {
      if (v === 'all') return true;
      if (k === 'sport') return p.sport === v;
      if (k === 'tier') return p.tier === v;
      if (k === 'market') return p.g === v;
      if (v === 'hour') return p.band === 'hour';
      return p.band === 'hour' || p.band === 'today';
    }
    function countFor(d, k, v) { var f = eff(); return d.all.filter(function (p) { return passes(p, f, k, st.wallet, d.sameMap) && facetValue(p, k, v); }).length; }
    function setCounts(d) {
      Object.keys(refs.strips).forEach(function (k) {
        var strip = refs.strips[k];
        Array.prototype.forEach.call(strip.querySelectorAll('button[data-v]'), function (b) {
          var n = countFor(d, k, b.getAttribute('data-v'));
          var c = b.querySelector('.sv2-cnt'); if (c && c.textContent !== String(n)) c.textContent = String(n);
        });
        seg.set(strip, st.f[k]);
      });
    }
    /* sport is not a filter here: it belongs to the host header (or its own strip), so it never counts toward the badge */
    function activeKeys() { return GROUPS.map(function (g) { return g[0]; }).filter(function (k) { return st.f[k] !== 'all'; }); }
    function itemLabel(k, v) { var it = groupItems(k).filter(function (x) { return x[0] === v; })[0]; return it ? it[1] : v; }

    function panelHtml(d) {
      return '<div class="sv2-sp-pbody">' + GROUPS.map(function (g) {
        var k = g[0];
        return '<div class="sv2-sp-fg" role="group" aria-label="' + esc(g[1]) + '"><h3 class="sv2-h2">' + esc(g[1]) + '</h3><div class="sv2-sp-chips">' +
          groupItems(k).map(function (it) {
            return '<button type="button" class="sv2-sp-fc sv2-press sv2-press-chip" data-sp-fc="' + k + '" data-v="' + esc(it[0]) + '" aria-pressed="' + (st.f[k] === it[0]) + '">' + esc(it[1]) + ' <span class="sv2-cnt sv2-num">' + (d ? countFor(d, k, it[0]) : 0) + '</span></button>';
          }).join('') + '</div></div>';
      }).join('') + '</div><div class="sv2-sp-pf"><button type="button" class="sv2-link sv2-sp-reset" data-sp-reset>Reset</button><button type="button" class="sv2-sp-done sv2-press sv2-press-btn" data-sp-done>Done</button></div>';
    }
    function activeHtml() {
      return activeKeys().map(function (k) {
        var g = GROUPS.filter(function (x) { return x[0] === k; })[0][1], w = itemLabel(k, st.f[k]);
        return '<button type="button" class="sv2-sp-ac sv2-press sv2-press-chip" data-sp-rm="' + k + '" data-fid="rm:' + k + '" aria-label="Remove filter: ' + esc(g + ' ' + w) + '"><span>' + esc(w) + '</span>' + ui.icon('close') + '</button>';
      }).join('');
    }
    function sheetOpen() { return SV2.sheet.isOpen() && SV2.sheet.route() == null && st.panel && isPhone(); }
    function syncFtog() { if (refs.ftog) refs.ftog.setAttribute('aria-expanded', String(!!st.panel)); }
    function openPanel() {
      if (!model) return;
      st.panel = true;
      if (isPhone()) SV2.sheet.open(panelHtml(model), { label: 'Filters', returnFocus: refs.ftog, onClose: function () { st.panel = false; syncFtog(); } });
      else { refs.pop.innerHTML = panelHtml(model); refs.pop.hidden = false; var f0 = refs.pop.querySelector('[aria-pressed="true"]'); if (f0) f0.focus({ preventScroll: true }); }
      syncFtog();
    }
    function closePanel(refocus) {
      if (!st.panel) return;
      if (isPhone() && SV2.sheet.isOpen()) { SV2.sheet.close(); return; }
      st.panel = false; refs.pop.hidden = true; syncFtog();
      if (refocus && refs.ftog) refs.ftog.focus({ preventScroll: true });
    }
    function refreshPanel(focusSel) {
      if (!st.panel || !model) return;
      var box = sheetOpen() ? SV2.sheet.body() : refs.pop;
      if (!box) return;
      if (sheetOpen()) SV2.sheet.set(panelHtml(model)); else box.innerHTML = panelHtml(model);
      if (focusSel) { var n = box.querySelector(focusSel); if (n) n.focus({ preventScroll: true }); }
      SV2.rail.catchUp();
    }
    function resetFilters() { st.f.tier = 'all'; st.f.market = 'all'; st.f.starts = 'all'; st.wallet = null; lsSet(FKEY, JSON.stringify(st.f)); }
    /* one handler for the popover (inside el) and the phone sheet (in the body-level host). Returns true when it took the click. */
    function filterClick(e) {
      var t = e.target; if (!t || !t.closest) return false;
      var chip = t.closest('[data-sp-fc]');
      if (chip) {
        var k = chip.getAttribute('data-sp-fc'), v = chip.getAttribute('data-v');
        st.f[k] = v; lsSet(FKEY, JSON.stringify(st.f)); paint(true, true);
        refreshPanel('[data-sp-fc="' + k + '"][data-v="' + v + '"]');
        return true;
      }
      if (t.closest('[data-sp-reset]')) { resetFilters(); paint(true, true); refreshPanel('[data-sp-done]'); return true; }
      if (t.closest('[data-sp-done]')) { closePanel(true); return true; }
      var rm = t.closest('[data-sp-rm]');
      if (rm) { st.f[rm.getAttribute('data-sp-rm')] = 'all'; lsSet(FKEY, JSON.stringify(st.f)); paint(true, true); return true; }
      if (t.closest('[data-sp-clear]')) { resetFilters(); paint(true, true); return true; }
      if (t.closest('[data-sp-ftog]')) { if (st.panel) closePanel(false); else openPanel(); return true; }
      return false;
    }

    function railHtml(d) {
      var counts = {}; copy.tierOrder.forEach(function (t) { counts[t] = 0; }); d.all.forEach(function (p) { counts[p.tier]++; });
      var nextP = sortPlays(d.all).sort(function (a, b) { return (a.cut || 0) - (b.cut || 0); })[0];
      var h = '';
      if (nextP) h += '<section class="sv2-box sv2-sp-rb"><h2 class="sv2-h2">Next to freeze</h2><p><b class="sv2-num" data-sp-cd data-cut="' + nextP.cut + '">' + esc(countdownText(nextP.cut, d.now) || '') + '</b> ' + esc(playTitle(nextP.game, nextP.g, nextP.sf)) + ' <span class="sv2-mut">' + esc(SV2.sportName(nextP.sport)) + '</span></p></section>';
      if (d.same.length) h += '<section class="sv2-box sv2-sp-rb"><h2 class="sv2-h2">Same wallet</h2>' + d.same.slice(0, 2).map(function (r) { return '<p><span class="sv2-num">' + esc(fmt.tail(r.w)) + '</span> on ' + r.n + ' plays</p>'; }).join('') + '</section>';
      h += '<section class="sv2-box sv2-sp-rb"><h2 class="sv2-h2">Tiers</h2><ul class="sv2-sp-tl">' + copy.tierOrder.map(function (t) { return '<li>' + ui.tier(t) + '<span class="sv2-num">' + counts[t] + '</span></li>'; }).join('') + '</ul>';
      if (d.all.length && !counts.clear) h += '<p class="sv2-sp-note">' + esc(T.tierEmpty) + '</p>';
      var R = SV2.rec, tf = R && R.tierFile ? R.tierFile() : null, line = tf && R.railLine ? R.railLine(tf, eff().sport) : null, sp = eff().sport;
      if (line) {
        h += '<p class="sv2-rec-railn">' + esc(line.label + (sp === 'cfb' ? ', flat 1u, no size shown' : '')) + ':</p><ul class="sv2-rec-railul">' + line.items.map(function (it) {
          return '<li>' + esc(it.word) + ' <span class="sv2-num">' + esc(it.wl || '') + '</span></li>';
        }).join('') + '</ul>';
      } else if (R && R.tierFile && tf) h += '<p class="sv2-rec-railn">' + esc('No tier record for ' + (sp === 'all' ? 'these sports' : SV2.sportName(sp)) + ' yet.') + '</p>';
      else {
        var rec = store.cards && store.cards.v2_tier_record;
        if (rec && typeof rec === 'object') {
          h += copy.tierOrder.filter(function (t) { return rec[t] && isNum(rec[t].n); }).map(function (t) {
            var r = rec[t]; return '<p class="sv2-sp-note">' + esc(copy.tier[t].word + ' ' + (fmt.wl(r.w, r.l, r.p) || '') + ', n=' + r.n + '. No verdict until n = 300.') + '</p>';
          }).join('');
        }
      }
      h += '<p class="sv2-rec-railn"><button type="button" class="sv2-sp-lnk" data-sv2-open-record>See the tier record</button></p>';
      h += '</section>';
      if (d.ctx.length) h += '<section class="sv2-box sv2-sp-rb"><h2 class="sv2-h2">Context</h2><p>' + esc(fmt.n(d.ctx.length)) + ' games with past-winner money on a side, no play <button type="button" class="sv2-sp-lnk" data-sp-ctxgo data-fid="ctxgo">show</button></p></section>';
      h += '<p class="sv2-sp-rec"><a class="sv2-link" href="../new/#vrecord">Play record</a></p>';
      return h;
    }

    function sameHtml(d) {
      if (!d.same.length) return '';
      if (st.wallet) {
        var r = d.sameMap[st.wallet];
        return '<p>Showing the ' + r.n + ' plays held by <span class="sv2-num">' + esc(fmt.tail(st.wallet)) + '</span>. <button type="button" class="sv2-sp-lnk" data-sp-same-clear data-fid="sameclear">Show all</button></p>';
      }
      return d.same.slice(0, 2).map(function (r) {
        return '<p>One wallet is on ' + r.n + ' of these ' + r.total + ' plays: <span class="sv2-num">' + esc(fmt.tail(r.w)) + '</span> <button type="button" class="sv2-sp-lnk" data-sp-same="' + esc(r.w) + '" data-fid="same:' + esc(r.w) + '">see</button></p>';
      }).join('');
    }

    function summaryText(d) {
      if (!d.all.length) {
        return d.next != null ? 'No plays right now. Next card freezes ' + ct.time(d.next, true) + '.' : 'No plays right now.';
      }
      var n = d.vis.length === d.all.length ? plural(d.all.length, 'play', 'plays') : d.vis.length + ' of ' + plural(d.all.length, 'play', 'plays');
      var c = null; d.all.forEach(function (p) { if (isNum(p.cut) && p.cut > d.now && (c == null || p.cut < c)) c = p.cut; });
      return n + (c != null ? ', next freezes in <span data-sp-cd data-cut="' + c + '">' + esc(countdownText(c, d.now)) + '</span>' : '');
    }

    function paint(force, fromFilter) {
      var cards = store.cards;
      if (!cards) {
        st.shell = false; st.sig = '';
        el.innerHTML = store.state.cards === 'loading' ? '<div class="sv2-card sv2-tb-card sv2-tb-skelcard">' + ui.skel(6, 'Loading plays', 'sv2-tb-skel') + '</div>' : '<p class="sv2-err">Could not load the plays. <button type="button" class="sv2-link" data-sv2-retry>Try again</button></p>';
        return;
      }
      var sig = [cards.built, store.wallets && store.wallets.built, store.splits && store.splits.generated, SV2.sizesOk() ? 1 : 0, store.state.wallets].join('|');
      if (!force && sig === st.sig && st.shell) return;
      st.sig = sig;
      if (!st.shell) buildShell();
      var ae = document.activeElement, fid = ae && el.contains(ae) && ae.getAttribute ? ae.getAttribute('data-fid') : null;
      var d = compute(); model = d;
      refs.sum.innerHTML = summaryText(d);
      setCounts(d);
      refs.acts.hidden = !d.all.length;   /* zero plays: no filters, the context list is the page */
      var na = activeKeys().length;
      refs.badge.textContent = String(na); refs.badge.hidden = !na; refs.clear.hidden = !na;
      refs.active.innerHTML = activeHtml(); refs.active.hidden = !na;
      if (!d.all.length && st.panel) closePanel(false);
      refreshPanel();
      refs.same.innerHTML = sameHtml(d); refs.same.hidden = !refs.same.innerHTML;
      if (st.ctxOpen == null) st.ctxOpen = !d.all.length;   /* zero plays: the context list is the real content, open it */
      if (!d.all.length) refs.list.innerHTML = '';
      else if (!d.vis.length && !activeKeys().length && !st.wallet && eff().sport !== 'all') refs.list.innerHTML = '<p class="sv2-empty-line">No ' + esc(SV2.sportName(eff().sport)) + ' plays right now.</p>';
      else if (!d.vis.length) refs.list.innerHTML = '<p class="sv2-empty-line">' + esc(T.noMatch) + ' <button type="button" class="sv2-link" data-sp-clear data-fid="clear2">Clear filters</button></p>';
      else refs.list.innerHTML = tableHtml(d.vis, st, d.sameKeys, d.now);
      st.lastBands = bandSig(d.all);
      refs.ctx.innerHTML = ctxHtml(d.ctx, st);
      refs.rail.innerHTML = railHtml(d);
      SV2.rail.catchUp();
      if (fid) { var back = el.querySelector('[data-fid="' + fid.replace(/"/g, '\\"') + '"]'); if (back && back !== document.activeElement) { try { back.focus({ preventScroll: true }); } catch (e) { /* ignore */ } } }
      if (fromFilter) setLive(d.vis.length + (d.vis.length === 1 ? ' play shown' : ' plays shown'));
      handleDeep();
    }

    function bandSig(all) { return all.map(function (p) { return p.key + ':' + p.band; }).join(','); }

    /* #sharps/play/<ev>/<g>: open that play and bring it into view. Clears filters that hide it. */
    function handleDeep() {
      if (!st.deep || !model) return;
      var key = st.deep.ev + '|' + st.deep.g, p = model.all.filter(function (x) { return x.key === key; })[0];
      st.deep = null;
      if (!p) return;
      if (model.vis.indexOf(p) < 0) {
        st.f = cleanFilters(null); st.wallet = null; lsSet(FKEY, JSON.stringify(st.f));
        st.open[key] = true; paint(true); return;
      }
      st.open[key] = true;
      var item = el.querySelector('tr.sv2-tb-r[data-key="' + q(key) + '"]');
      if (!item) return;
      if (!el.querySelector('tr.sv2-tb-d[data-dkey="' + q(key) + '"] .sv2-x[data-open]')) { paint(true); item = el.querySelector('tr.sv2-tb-r[data-key="' + q(key) + '"]'); }
      if (item) item.scrollIntoView({ block: 'start' });
    }
    function readDeep() {
      var r = SV2.route();
      if (r.page === 'sharps' && r.sub[0] === 'play' && r.sub[1] && r.sub[2]) st.deep = { ev: r.sub[1], g: r.sub[2] };
    }

    function ensureDetail(drow, key) {
      var inEl = drow.querySelector('.sv2-x-in');
      if (!inEl.firstChild && model) {
        var p = model.all.filter(function (x) { return x.key === key; })[0];
        if (p) inEl.innerHTML = detailHtml(p, !!st.more[key]);
      }
    }

    function toggleRow(key) {
      var btn = el.querySelector('[data-sp-row="' + q(key) + '"]'), dr = el.querySelector('tr.sv2-tb-d[data-dkey="' + q(key) + '"]');
      if (!btn || !dr) return;
      var x = dr.querySelector('.sv2-x'), open = !x.hasAttribute('data-open');
      if (open) { ensureDetail(dr, key); x.setAttribute('data-open', ''); } else x.removeAttribute('data-open');
      btn.setAttribute('aria-expanded', String(open)); btn.closest('tr').classList.toggle('is-open', open); st.open[key] = open;
    }

    /* ---- events (delegated) ---- */
    el.addEventListener('click', function (e) {
      var t = e.target; if (!t.closest) return;
      if (filterClick(e)) return;
      var a = t.closest('[data-sv2-acct]');
      if (a) {
        if (typeof SV2.openAccount === 'function') {
          e.preventDefault();
          SV2.openAccount(a.getAttribute('data-sport'), a.getAttribute('data-w'), { ev: a.getAttribute('data-ev'), g: a.getAttribute('data-g'), side: a.getAttribute('data-side'), from: 'sharps' });
        }
        return;
      }
      var sb = t.closest('[data-sp-sort]');
      if (sb) { st.sort = nextSort(st.sort, sb.getAttribute('data-sp-sort')); paint(true); setLive('Sorted by ' + sortWord(st.sort)); return; }
      var tr = t.closest('tr.sv2-tb-r');
      if (tr) { toggleRow(tr.getAttribute('data-key')); return; }   /* the whole row toggles; the chevron button is the keyboard and screen reader control */
      var more = t.closest('[data-sp-more]');
      if (more) {
        var mx = more.parentNode.querySelector('.sv2-x'), mo = !mx.hasAttribute('data-open');
        if (mo) mx.setAttribute('data-open', ''); else mx.removeAttribute('data-open');
        more.setAttribute('aria-expanded', String(mo)); st.more[more.getAttribute('data-sp-more')] = mo;
        return;
      }
      var sw = t.closest('[data-sp-same]');
      if (sw) { st.wallet = sw.getAttribute('data-sp-same'); paint(true, true); return; }
      if (t.closest('[data-sp-same-clear]')) { st.wallet = null; paint(true, true); return; }
      var cx = t.closest('[data-sp-ctx]');
      if (cx) {
        var xx = el.querySelector('#sv2-sp-ctxx'), co = !xx.hasAttribute('data-open');
        if (co) xx.setAttribute('data-open', ''); else xx.removeAttribute('data-open');
        cx.setAttribute('aria-expanded', String(co)); st.ctxOpen = co;
        var lab = cx.querySelector('.sv2-sp-ctxs'); if (lab) lab.textContent = co ? 'Hide' : 'Show';
        return;
      }
      if (t.closest('[data-sp-ctxmore]')) { st.ctxN += CTX_STEP; st.ctxOpen = true; paint(true); return; }
      if (t.closest('[data-sp-ctxgo]')) {
        st.ctxOpen = true; paint(true);
        var sec = el.querySelector('[data-sp="ctx"]'); if (sec) sec.scrollIntoView({ block: 'start' });
        return;
      }
    });

    /* ---- data and clock events ---- */
    on('cards', function () { paint(false); });
    on('tierrecord', function () { if (model && refs.rail) { refs.rail.innerHTML = railHtml(model); SV2.rail.catchUp(); } });   /* the tier file lands after the plays: only the rail changes */
    on('wallets', function () { paint(false); });
    on('splits', function () { paint(false); });
    on('route', function () { readDeep(); if (st.deep && store.cards) paint(true); });
    on('tick', function () {
      if (!store.cards || !st.shell || el.hidden) return;
      var now = nowT(), all = collectPlays(store.cards, now);
      if (bandSig(all) !== st.lastBands) { paint(true); return; }
      Array.prototype.forEach.call(el.querySelectorAll('[data-sp-cd]'), function (n) {
        var c = countdownText(+n.getAttribute('data-cut'), now); if (c != null && n.textContent !== c) n.textContent = c;
      });
    });

    on('sport', function () {
      if (!st.shell) return;
      if ((SV2.hostSport() != null) !== st.hasHost) st.shell = false;   /* the host appeared or went: the sport strip is rebuilt */
      paint(true, true);
    });
    el.addEventListener('keydown', function (e) { if (e.key === 'Escape' && st.panel && !isPhone()) { e.stopPropagation(); closePanel(true); } });
    if (SV2._spOut) document.removeEventListener('click', SV2._spOut);
    SV2._spOut = function (e) { if (st.panel && !isPhone() && document.contains(el) && document.contains(e.target) && e.target.closest && !e.target.closest('.sv2-sp-fwrap')) closePanel(false); };
    document.addEventListener('click', SV2._spOut);
    SV2._spSheet = filterClick;
    var shHost = document.getElementById('sv2-sheet-host');
    if (shHost && !shHost._spf) { shHost._spf = true; shHost.addEventListener('click', function (e) { if (SV2._spSheet) SV2._spSheet(e); }); }

    readDeep();
    paint(true);
  });
})();
