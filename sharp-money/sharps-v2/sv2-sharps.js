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
    if (except !== 'moves' && f.moves && f.moves !== 'all' && !movesOf(p)[f.moves]) return false;
    if (wallet && !(sameMap[wallet] && sameMap[wallet].keys.indexOf(p.key) >= 0)) return false;
    return true;
  }
  var FILTER_VALUES = {
    sport: ['all'].concat(SPORT_ORDER),
    tier: ['all'].concat(copy.tierOrder),
    market: ['all'].concat(T.marketOrder),
    starts: ['all', 'hour', 'today'],
    moves: ['all', 'pin', 'line']
  };
  function cleanFilters(o) {
    var f = { sport: 'all', tier: 'all', market: 'all', starts: 'all', moves: 'all' };
    if (o && typeof o === 'object') Object.keys(f).forEach(function (k) { if (FILTER_VALUES[k].indexOf(o[k]) >= 0) f[k] = o[k]; });
    return f;
  }

  /* ------------------------------------------------------------------ market-move flags and the write-up (rule v2f-1, docs/sharps-v2-flags-spec.md).
     Every field here is optional: an absent or null field omits its chip or section, and nothing is ever filled in or shown as 0.
     Flags say what the market did. They are context only: no bet signal, no size, no tier, no count of flags. */
  var BOOKS = ['Pinnacle', 'DraftKings', 'FanDuel', 'BetMGM', 'BetRivers', 'bet365'];   /* only books we store are ever named */
  var SPORT_EYEBROW = { nba: 'NBA', nfl: 'NFL', cbb: 'College basketball', cfb: 'College football' };
  function isObj(x) { return !!x && typeof x === 'object' && !Array.isArray(x); }
  function flagsOf(p) {
    var m = mktOf(p.game, p.g), v = m && m.v2, f = v && v.flags;
    return isObj(f) ? f : null;
  }
  function amer(x) { return isNum(x) ? (x > 0 ? '+' : '') + Math.round(x) : null; }
  function lineTxt(x, g) { return isNum(x) ? (g === 'spread' ? fmt.line(x, { signed: true }) : fmt.line(x)) : null; }
  function flagState(x) { return isObj(x) && (x.state === 'toward' || x.state === 'away' || x.state === 'quiet') ? x.state : null; }
  function pinNums(f) {
    var a = f && isObj(f.pin) ? f.pin : null;
    return a && isNum(a.from) && isNum(a.to) ? { from: amer(a.from), to: amer(a.to) } : null;
  }
  /* Flag C's Pinnacle from and to: a line for spreads and totals (kind line), an American price for moneylines (kind price) */
  function lineNums(f, g) {
    var c = f && isObj(f.line) ? f.line : null, a = c && isObj(c.pin) ? c.pin : null;
    if (!a || !isNum(a.from) || !isNum(a.to)) return null;
    return c.kind === 'price' ? { from: amer(a.from), to: amer(a.to) } : { from: lineTxt(a.from, g), to: lineTxt(a.to, g) };
  }
  function booksTxt(c) { return c && isNum(c.books) && c.books > 0 && isNum(c.same_way) ? c.same_way + ' of ' + c.books + ' books' : null; }

  /* chip text and tooltip for the Sharps table: only a toward or away state draws a chip. Quiet, null and absent draw nothing. */
  function flagChips(p) {
    var f = flagsOf(p), out = [];
    if (!f) return out;
    var a = flagState(f.pin), c = flagState(f.line);
    if (a === 'toward' || a === 'away') {
      var n = pinNums(f), ln = isObj(f.pin) && isNum(f.pin.line) ? lineTxt(f.pin.line, p.g) : null;
      var tip = n ? 'Pinnacle ' + n.from + ' to ' + n.to + (ln ? ' at ' + ln : '') : 'Pinnacle\'s price';
      out.push({ k: 'pin', state: a, text: 'Pinnacle moved ' + (a === 'toward' ? 'toward' : 'away from') + ' this side', tip: tip + ', ' + (a === 'toward' ? 'toward' : 'away from') + ' this side' });
    }
    if (c === 'toward' || c === 'away') {
      var ls = f.line.kind === 'price', nn = lineNums(f, p.g), bk = booksTxt(f.line);
      var tip2 = (ls ? 'Books' : 'Market line') + (nn ? ' ' + nn.from + ' to ' + nn.to + (ls ? '' : ' at Pinnacle') : '') + (bk ? ', ' + bk + ' the same way' : '');
      out.push({ k: 'line', state: c, text: (ls ? 'Market price moved ' : 'Market line moved ') + (c === 'toward' ? 'toward' : 'away from') + ' this side', tip: tip2 + ', ' + (c === 'toward' ? 'toward' : 'away from') + ' this side' });
    }
    return out;
  }
  var FL_ICON = {
    toward: '<path d="M2 8h8M7 5l3 3-3 3M14 4v8"/>',
    away: '<path d="M2 4v8M6 8h8M11 5l3 3-3 3"/>',
    quiet: '<path d="M3 6h10M3 10h10"/>',
    none: '<path d="M4 8h8" stroke-dasharray="2 2"/>'
  };
  function flagIcon(state) { return '<svg class="sv2-fl-i" viewBox="0 0 16 16" aria-hidden="true" focusable="false">' + (FL_ICON[state] || FL_ICON.none) + '</svg>'; }
  function chipsHtml(p) {
    var cs = flagChips(p);
    if (!cs.length) return '';
    return '<span class="sv2-tb-fl">' + cs.map(function (c) {
      return '<span class="sv2-fl" data-flag="' + c.k + '" title="' + esc(c.tip) + '">' + flagIcon(c.state) + '<span>' + esc(c.text) + '</span><span class="sv2-sr">. ' + esc(c.tip) + '</span></span>';
    }).join('') + '</span>';
  }
  /* the Filters group: which plays had a Pinnacle move or a market move (either direction), from the stored flags only */
  function movesOf(p) {
    var f = flagsOf(p), a = f && flagState(f.pin), c = f && flagState(f.line);
    return { pin: a === 'toward' || a === 'away', line: c === 'toward' || c === 'away', any: !!f };
  }

  /* ---- series: points, step paths, table ---- */
  function cleanPts(a) {
    if (!Array.isArray(a)) return [];
    var o = a.filter(function (r) { return Array.isArray(r) && isNum(r[0]) && isNum(r[1]); }).map(function (r) { return [r[0], r[1]]; });
    o.sort(function (x, y) { return x[0] - y[0]; });
    return o;
  }
  /* A step line holds its value until the next change, so a repeat of the previous value carries no information: drop it (the last point stays, it
     sets the right edge). Over max points: keep first, last, lowest, highest, then fill by even spacing. */
  function chartPoints(pts, max) {
    var a = cleanPts(pts), out = [], i;
    for (i = 0; i < a.length; i++) if (!out.length || a[i][1] !== out[out.length - 1][1] || i === a.length - 1) out.push(a[i]);
    max = isNum(max) && max >= 4 ? max : 16;
    if (out.length <= max) return out;
    var keep = {}, lo = 0, hi = 0;
    for (i = 1; i < out.length; i++) { if (out[i][1] < out[lo][1]) lo = i; if (out[i][1] > out[hi][1]) hi = i; }
    keep[0] = 1; keep[out.length - 1] = 1; keep[lo] = 1; keep[hi] = 1;
    var left = max - Object.keys(keep).length, step = (out.length - 1) / (left + 1);
    for (i = 1; i <= left; i++) keep[Math.round(i * step)] = 1;
    return out.filter(function (_, j) { return keep[j]; });
  }
  /* pixel path of a step line. pts [[x,y]], sx and sy map a value to a pixel. null for no points; one point gives a dot. */
  function stepPath(pts, sx, sy) {
    if (!pts || !pts.length) return null;
    var r1 = function (n) { return Math.round(n * 10) / 10; };
    var d = 'M' + r1(sx(pts[0][0])) + ' ' + r1(sy(pts[0][1]));
    for (var i = 1; i < pts.length; i++) d += 'H' + r1(sx(pts[i][0])) + 'V' + r1(sy(pts[i][1]));
    return { d: d, single: pts.length === 1, x: r1(sx(pts[0][0])), y: r1(sy(pts[0][1])) };
  }
  /* the lowest and highest point of a series (first one on a tie), and whether each is an endpoint */
  function extremes(pts) {
    if (!pts || pts.length < 2) return null;
    var lo = 0, hi = 0;
    for (var i = 1; i < pts.length; i++) { if (pts[i][1] < pts[lo][1]) lo = i; if (pts[i][1] > pts[hi][1]) hi = i; }
    if (pts[lo][1] === pts[hi][1]) return null;
    return { lo: lo, hi: hi };
  }
  function seriesOf(p) {
    var m = mktOf(p.game, p.g), s = m && m.v2 && m.v2.series;
    if (!isObj(s) || !isNum(s.t0)) return null;
    var pin = chartPoints(s.pin_px, 16), lines = {}, n = 0;
    if (isObj(s.lines)) BOOKS.forEach(function (b) { var pts = chartPoints(s.lines[b], 16); if (pts.length) { lines[b] = pts; n++; } });
    if (!pin.length && !n) return null;
    return { t0: s.t0, pin: pin, lines: lines, nBooks: n };
  }
  /* the data table behind the charts: one row per time any series changed, each cell the value held at that time (blank before a series starts) */
  function chartTable(s, g) {
    if (!s) return null;
    var cols = [], xs = {};
    if (s.pin.length) { cols.push({ name: 'Pinnacle price', pts: s.pin, am: true }); s.pin.forEach(function (r) { xs[r[0]] = 1; }); }
    BOOKS.forEach(function (b) { if (s.lines[b]) { cols.push({ name: b + ' line', pts: s.lines[b] }); s.lines[b].forEach(function (r) { xs[r[0]] = 1; }); } });
    var times = Object.keys(xs).map(Number).sort(function (a, b) { return a - b; });
    var rows = times.map(function (x) {
      return [ct.time(s.t0 + x * 60, true)].concat(cols.map(function (c) {
        var v = null; c.pts.forEach(function (r) { if (r[0] <= x) v = r[1]; });
        return v == null ? '' : (c.am ? amer(v) : lineTxt(v, g));
      }));
    });
    return { head: ['Time'].concat(cols.map(function (c) { return c.name; })), rows: rows };
  }

  /* ---- tracked money (v2.sides) ---- */
  function moneyOf(p) {
    var m = mktOf(p.game, p.g), s = m && m.v2 && m.v2.sides;
    if (!isObj(s)) return null;
    var S = p.sf.side, names = Object.keys(s).filter(function (k) { return isObj(s[k]); });
    if (names.indexOf(S) < 0 || names.length !== 2) return null;
    var other = names.filter(function (k) { return k !== S; })[0], a = s[S], b = s[other];
    if (!isNum(a.usd) || !isNum(b.usd)) return null;
    return { side: S, other: other, mine: a, theirs: b, sides: s };
  }
  /* the panels run in market order (away then home, over then under), never heavier money first */
  function marketOrder(p, names) {
    if (p.g === 'total') return names.slice().sort(function (a, b) { return /^over/i.test(a) ? -1 : /^over/i.test(b) ? 1 : 0; });
    var t = p.game.vault && p.game.vault.teams, away = t && t.away || [];
    return names.slice().sort(function (a, b) { var x = away.indexOf(a) >= 0, y = away.indexOf(b) >= 0; return x === y ? 0 : x ? -1 : 1; });
  }
  function heavier(a, b) { return isNum(a) && isNum(b) && a !== b ? (a > b ? 'a' : 'b') : null; }
  function walletsTxt(n) { return isNum(n) ? n + (n === 1 ? ' wallet' : ' wallets') : null; }
  /* the rows of one side's panel. tiered (NBA, NFL) has the beats and loses rows, college has a note and the losing-record row. */
  function sideRows(s, tiered) {
    var R = [];
    function row(label, e) { if (isObj(e) && isNum(e.n) && isNum(e.usd)) R.push({ label: label, usd: fmt.usd(e.usd), n: walletsTxt(e.n) }); }
    if (tiered) row('Wallets that beat the close', s.beats); else R.push({ label: 'Wallets that beat the close', note: 'Not measured in college' });
    row('Past-winner wallets', s.past_winner);
    if (tiered) row('Wallets that lose to the close', s.loses); else row('Wallets with a losing record', s.losing_record);
    if (isNum(s.usd)) R.push({ label: 'All tracked money', usd: fmt.usd(s.usd), n: walletsTxt(s.holders) });
    return R;
  }
  /* "$1.1K", "$1.45K", "$20K", "$504": limits read at two decimals, so $1,450 is not rounded to $1.5K */
  function limitMoney(x) {
    if (!isNum(x)) return null;
    if (x < 1000) return '$' + Math.round(x);
    var k = Math.round(x / 10) / 100;
    return '$' + (+k.toFixed(2)) + 'K';
  }
  function spanPhrase(f, cap) {
    var span = f && isNum(f.span_min) ? f.span_min : null;
    if (span == null) return '';
    if (span < 120) return cap ? 'Since the first stored reading ' + Math.max(1, Math.round(span)) + ' minutes earlier, ' : 'since the first stored reading ' + Math.max(1, Math.round(span)) + ' minutes earlier';
    var h = Math.round(span / 60);
    return cap ? 'In the last ' + h + ' hours ' : 'in the last ' + h + ' hours';
  }
  /* two dollar figures compared in one sentence: when the short forms collide ($12K against $12K) both are written in full */
  function usdPair(a, b) {
    var x = fmt.usd(a), y = fmt.usd(b);
    return x === y && a !== b ? [fmt.usd(a, { full: true }), fmt.usd(b, { full: true })] : [x, y];
  }
  /* ---- the takeaway: S1 market, S2 money, S3 mixed signals, graded result, S4 closer. Deterministic templates over stored numbers only. ---- */
  function takeaway(c) {
    var f = c.flags, side = c.side, A = f ? flagState(f.pin) : null, C = f ? flagState(f.line) : null, price = !!(f && f.line && f.line.kind === 'price');
    var np = price ? 'price' : 'number', out = [];
    var pn = f ? pinNums(f) : null, ln = f ? lineNums(f, c.g) : null, bk = f && f.line ? f.line : null;
    var pf = pn ? pn.from + ' to ' + pn.to : null, lf = ln ? ln.from + ' to ' + ln.to : null, sw = booksTxt(bk);
    var held = price ? 'Pinnacle\'s own price held' : 'Pinnacle\'s price at that number held';
    function tw(s) { return s === 'toward' ? 'toward ' + side : 'against ' + side; }
    var mk = c.g === 'ml' ? 'moneyline' : c.g;
    /* a placeholder with no value forces the branch that does not print it: a state whose numbers are missing prints without them */
    function nums(x) { return x ? ' (' + x + ')' : ''; }
    function mvLine() { return 'The market moved the ' + np + ' ' + tw(C) + (lf && sw ? ' (' + lf + ' at Pinnacle, ' + sw + ' the same way)' : lf ? ' (' + lf + ' at Pinnacle)' : ''); }
    var s1 = null, hasAgainst = A === 'away' || C === 'away';
    if (f) {
      var lead = spanPhrase(f, true);
      if (A && A !== 'quiet' && C && C !== 'quiet') {
        if (A === C) s1 = (lead ? lead : '') + 'Pinnacle\'s price and the market\'s ' + np + ' both moved ' + tw(A) + '.';
        else if (A === 'toward') s1 = 'Pinnacle\'s price moved toward ' + side + ' while the market\'s ' + np + ' moved against it, so the market did not settle on one direction.';
        else s1 = 'The market\'s ' + np + ' moved toward ' + side + ' while Pinnacle\'s price moved against it, so the market did not settle on one direction.';
      } else if (A && A !== 'quiet') {
        s1 = 'Pinnacle\'s price moved ' + tw(A) + nums(pf) + '; ' + (C === 'quiet' ? 'the market\'s ' + np + ' held.' : 'there were not enough book readings to say where the ' + np + ' went.');
      } else if (C && C !== 'quiet') {
        s1 = mvLine() + (A === 'quiet' ? '; ' + held + '.' : '.');
      } else if (A === 'quiet' && C === 'quiet') {
        s1 = 'The market barely moved on this ' + mk + (spanPhrase(f, false) ? ' ' + spanPhrase(f, false) : '') + '.';
      } else if (A === 'quiet') s1 = 'Pinnacle\'s price barely moved; there were not enough book readings to say where the ' + np + ' went.';
      else if (C === 'quiet') s1 = 'The ' + np + ' barely moved at the books; Pinnacle\'s price history was not readable.';
      else s1 = 'No market history is stored for this game, so there is nothing to say about where the line went.';
      if (s1 && hasAgainst && c.size) s1 += ' The play and its size are unchanged by this.';
    }
    if (s1) out.push(s1);
    /* S2: the tracked money */
    var heavy = null, small = false, mm = c.money, pr;
    if (mm) {
      var n = (isNum(mm.mine.holders) ? mm.mine.holders : 0) + (isNum(mm.theirs.holders) ? mm.theirs.holders : 0), ms = mm.mine.usd, mo = mm.theirs.usd, tot = ms + mo;
      if (n < 5 || tot < 1000) { small = true; out.push('Only ' + n + (n === 1 ? ' tracked wallet (' : ' tracked wallets (') + fmt.usd(tot) + (n === 1 ? ') holds' : ') hold') + ' this market, too few to describe.'); }
      else if (ms > mo) { heavy = 'side'; pr = usdPair(ms, mo); out.push('More of the tracked Polymarket money is on ' + side + ' (' + pr[0] + ' against ' + pr[1] + ').'); }
      else if (mo > ms) { heavy = 'other'; pr = usdPair(mo, ms); out.push('More of the tracked Polymarket money is on ' + c.other + ' (' + pr[0] + ' against ' + pr[1] + ').'); }
      else out.push('The tracked Polymarket money is split evenly (' + fmt.usd(ms) + ' each).');
    }
    /* S3: the money and the market point different ways (never says which to take) */
    if (mm && !small && heavy && ((heavy === 'other' && (A === 'toward' || C === 'toward')) || (heavy === 'side' && (A === 'away' || C === 'away')))) {
      out.push('The tracked money and the market\'s moves point in different directions here.');
    }
    if (c.graded && c.graded.result) out.push('Final ' + c.graded.score + ': the play ' + ({ won: 'won', lost: 'lost', push: 'pushed' }[c.graded.result] || 'finished') + '.');
    out.push('These are descriptions of what the market did. Past moves like these have not paid off in Vault\'s records, so this is context, not a reason to bet.');
    return out;
  }
  function sideLabelWords(p) {
    var S = p.sf.side;
    if (p.g === 'total') return /^over/i.test(S) ? { side: 'the over', other: 'the under' } : { side: 'the under', other: 'the over' };
    return { side: S, other: null };
  }
  function eyebrowOf(sport) { return SPORT_EYEBROW[sport] || String(sport || '').toUpperCase(); }
  function dateWords(t) {
    if (!isNum(t)) return null;
    try {
      return new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', weekday: 'short', month: 'short', day: 'numeric' }).format(new Date(t * 1000)).replace(',', '').toUpperCase();
    } catch (e) { return null; }
  }

  /* ---- chart (inline SVG, no library). W is the drawing width; the svg scales to its box, capped so the labels stay readable. ---- */
  var CH = { W: 340, padL: 10, padR: 104, padT: 16, padB: 14 };
  function priceProb(a) { return a < 0 ? -a / (-a + 100) : 100 / (a + 100); }   /* American price to implied probability: places +105 and -129 on one scale */
  function chartSvg(pane, s, o) {
    var W = o.W || CH.W, H = pane.h, x1 = 0;
    var all = pane.series.reduce(function (a, r) { return a.concat(r.pts); }, []);
    all.forEach(function (r) { if (r[0] > x1) x1 = r[0]; });
    var yv = function (v) { return pane.am ? priceProb(v) : v; };
    var lo = Infinity, hi = -Infinity;
    all.forEach(function (r) { var v = yv(r[1]); if (v < lo) lo = v; if (v > hi) hi = v; });
    if (!(hi > lo)) { var pad = pane.am ? .01 : 1; lo -= pad; hi += pad; }
    var top = CH.padT, bot = H - CH.padB - (pane.axis ? 16 : 0), w = W - CH.padL - CH.padR;
    var sx = function (x) { return CH.padL + (x1 > 0 ? x / x1 * w : w); };
    var sy = function (v) { return bot - (yv(v) - lo) / (hi - lo) * (bot - top); };
    var parts = '', labels = [], k = 0;
    pane.series.forEach(function (r) {
      var sp = stepPath(r.pts, sx, sy); if (!sp) return;
      var cls = 'sv2-wu-ln ' + (r.main ? 'is-main' : 'b' + (++k)) + (o.draw ? ' is-draw' : '');
      parts += sp.single ? '<circle class="' + cls + ' is-dot" cx="' + sp.x + '" cy="' + sp.y + '" r="3.5"/>' : '<path class="' + cls + '" d="' + sp.d + '" pathLength="1"/>';
      var last = r.pts[r.pts.length - 1];
      labels.push({ y: sy(last[1]), text: r.name + (r.am ? '' : ' ') + (pane.am ? amer(last[1]) : lineTxt(last[1], pane.g)), cls: r.main ? 'is-main' : 'b' + k });
    });
    /* right-edge labels, pushed apart so two books on the same line stay readable */
    labels.sort(function (a, b) { return a.y - b.y; });
    for (var i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < 12) labels[i].y = labels[i - 1].y + 12;
    var lbl = labels.map(function (l) { return '<text class="sv2-wu-tx ' + l.cls + '" x="' + (CH.padL + w + 6) + '" y="' + (Math.round(l.y * 10) / 10 + 4) + '">' + esc(l.text) + '</text>'; }).join('');
    /* the start value, and the highest and lowest points when they are not the end points */
    var main = pane.series[0], pts = main.pts, ex = extremes(pts), marks = '';
    var fmtV = function (v) { return pane.am ? amer(v) : lineTxt(v, pane.g); };
    if (pts.length > 1) marks += '<text class="sv2-wu-tx" x="' + CH.padL + '" y="' + (Math.round((sy(pts[0][1]) + (yv(pts[1][1]) > yv(pts[0][1]) ? 13 : -6)) * 10) / 10) + '">' + esc(fmtV(pts[0][1])) + '</text>';
    if (ex) [ex.lo, ex.hi].forEach(function (ix) {
      if (ix === 0 || ix === pts.length - 1) return;
      var up = ix === ex.hi;
      marks += '<circle class="sv2-wu-pt" cx="' + Math.round(sx(pts[ix][0]) * 10) / 10 + '" cy="' + Math.round(sy(pts[ix][1]) * 10) / 10 + '" r="2.5"/><text class="sv2-wu-tx" text-anchor="middle" x="' + Math.round(sx(pts[ix][0]) * 10) / 10 + '" y="' + (Math.round((sy(pts[ix][1]) + (up ? -6 : 14)) * 10) / 10) + '">' + esc(fmtV(pts[ix][1])) + '</text>';
    });
    var axis = '';
    if (pane.axis) {
      var ya = H - 3, t0 = s.t0, mid = Math.round(x1 / 2);
      axis = '<text class="sv2-wu-ax" x="' + CH.padL + '" y="' + ya + '">' + esc(ct.time(t0, true)) + '</text>' +
        (x1 > 0 ? '<text class="sv2-wu-ax" text-anchor="middle" x="' + (CH.padL + w / 2) + '" y="' + ya + '">' + esc(ct.time(t0 + mid * 60, false)) + '</text>' : '') +
        '<text class="sv2-wu-ax" text-anchor="end" x="' + (CH.padL + w) + '" y="' + ya + '">' + esc(o.edge) + '</text>';
    }
    return '<svg class="sv2-wu-svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(pane.alt) + '" focusable="false">' +
      '<line class="sv2-wu-base" x1="' + CH.padL + '" x2="' + (CH.padL + w) + '" y1="' + (bot + 2) + '" y2="' + (bot + 2) + '"/>' + parts + marks + lbl + axis + '</svg>';
  }
  function paneAlt(title, pts, fmtV, t0) {
    var a = pts[0], b = pts[pts.length - 1], ex = extremes(pts);
    return title + ': ' + fmtV(a[1]) + ' at ' + ct.time(t0 + a[0] * 60, true) + (pts.length > 1 ? ' to ' + fmtV(b[1]) + ' at ' + ct.time(t0 + b[0] * 60, true) : '') +
      (ex ? ', lowest ' + fmtV(pts[ex.lo][1]) + ', highest ' + fmtV(pts[ex.hi][1]) : '') + '.';
  }
  function chartsHtml(p, s, words, o) {
    var panes = [], g = p.g, edge = p.game.frozen ? 'Cut' : 'Now';
    var side = words.side;
    if (s.pin.length) panes.push({ h: s.nBooks ? 88 : 104, am: true, g: g, series: [{ name: '', main: true, am: true, pts: s.pin }], alt: paneAlt('Pinnacle\'s price for ' + side, s.pin, amer, s.t0) });
    if (s.nBooks) {
      var ser = [];
      BOOKS.forEach(function (b) { if (s.lines[b]) ser.push({ name: b, main: b === 'Pinnacle', pts: s.lines[b] }); });
      ser.sort(function (a, b) { return (b.main ? 1 : 0) - (a.main ? 1 : 0); });
      var alt = 'Main line by book: ' + ser.map(function (r) { return r.name + ' ' + lineTxt(r.pts[0][1], g) + ' to ' + lineTxt(r.pts[r.pts.length - 1][1], g); }).join(', ') + '. Times are Central, from ' + ct.time(s.t0, true) + '.';
      panes.push({ h: 124, am: false, g: g, series: ser, alt: alt });
    }
    panes[panes.length - 1].axis = true;
    var tb = chartTable(s, g);
    var table = tb ? '<table class="sv2-sr"><caption>' + esc('Line history for ' + side + ', Central time') + '</caption><thead><tr>' + tb.head.map(function (h) { return '<th scope="col">' + esc(h) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      tb.rows.map(function (r) { return '<tr><th scope="row">' + esc(r[0]) + '</th>' + r.slice(1).map(function (c) { return '<td>' + esc(c) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table>' : '';
    return '<div class="sv2-wu-charts">' + panes.map(function (pn) {
      return '<div class="sv2-wu-pane">' + chartSvg(pn, s, { draw: o.draw, edge: edge, W: o.phone ? 290 : CH.W }) + '</div>';
    }).join('') + table + '</div>';
  }

  /* ---- the card ---- */
  function arrowIcon() { return '<svg class="sv2-wu-arr" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M2 8h11M9 4l4 4-4 4"/></svg>'; }
  function fromTo(a, b) { return '<span class="sv2-sr">from </span>' + esc(a) + arrowIcon() + '<span class="sv2-sr"> to </span>' + esc(b); }
  /* every flag state as a chip, for the card: held and not-readable forms included */
  function fullChips(p, words) {
    var f = flagsOf(p), out = [], side = words.side;
    if (!f) return out;
    var a = flagState(f.pin), c = flagState(f.line), price = !!(f.line && f.line.kind === 'price'), bk = booksTxt(f.line), pn = pinNums(f), ln = lineNums(f, p.g);
    var tow = function (s) { return s === 'toward' ? 'toward ' + side : 'against ' + side; };
    out.push({ k: 'pin', state: a || 'none', tip: pn ? 'Pinnacle ' + pn.from + ' to ' + pn.to : '',
      text: a === 'toward' || a === 'away' ? 'Pinnacle\'s price moved ' + tow(a) : a === 'quiet' ? 'Pinnacle\'s price held' : 'Pinnacle\'s price: no history' });
    out.push({ k: 'line', state: c || 'none', tip: ln ? 'Pinnacle ' + ln.from + ' to ' + ln.to : '',
      text: c === 'toward' || c === 'away' ? (price ? 'The books moved the price ' : 'The market moved the number ') + tow(c) + (bk ? ' (' + bk + ')' : '') : c === 'quiet' ? (price ? 'The price held' : 'The number held') : (price ? 'Not enough books to read the price' : 'Not enough books to read the number') });
    return out;
  }
  function limitLine(f, share, sport) {
    if (!f) return '';
    var l = isObj(f.limit) ? f.limit : null, span = isNum(f.span_min) ? Math.round(f.span_min / 60) : null;
    if (!l || !isNum(l.to)) return 'No Pinnacle limit stored for this game.';
    if (!isNum(l.from) || l.rows === 1 || l.from === l.to) return 'Pinnacle limit ' + limitMoney(l.to) + (l.rows === 1 ? ' (one reading)' : '') + '.';
    var s = 'Pinnacle limit ' + limitMoney(l.from) + ' to ' + limitMoney(l.to) + (span ? ' in the last ' + span + ' hours' : '') + '.';
    if (isObj(share) && isNum(share[sport]) && share[sport] > 0) s += ' Pinnacle raises limits toward start on almost every game (' + Math.round(share[sport] * 100) + '% of ' + eyebrowOf(sport) + ' markets this season).';
    return s;
  }
  function sideHtml(p, s, tiered, isMore) {
    var rows = sideRows(s.data, tiered);
    return '<div class="sv2-card-inset sv2-wu-side' + (isMore ? ' is-more' : '') + '"><h4 class="sv2-wu-sn"><span class="sv2-ell">' + esc(s.name) + '</span>' + (isMore ? '<span class="sv2-chip sv2-chip--ink sv2-wu-mtag">More money</span>' : '') + '</h4><dl class="sv2-wu-rows">' +
      rows.map(function (r) {
        return '<div><dt>' + esc(r.label) + '</dt><dd>' + (r.note ? '<span class="sv2-mut">' + esc(r.note) + '</span>' : '<b class="sv2-num">' + esc(r.usd) + '</b> <span class="sv2-mut">' + esc(r.n || '') + '</span>') + '</dd></div>';
      }).join('') + '</dl></div>';
  }
  var DRAWN = {};
  function isPhoneNow() { try { return !!(window.matchMedia && window.matchMedia('(max-width: 767px)').matches); } catch (e) { return false; } }
  function sectionHtml(n, title, body, open, id) {
    return '<details class="sv2-wu-sec"' + (open ? ' open' : '') + ' id="' + id + '"><summary class="sv2-wu-sum"><span class="sv2-wu-n" aria-hidden="true">' + n + '</span><span class="sv2-wu-st">' + esc(title) + '</span>' +
      '<svg class="sv2-chev" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 9.5l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></summary><div class="sv2-wu-sb">' + body + '</div></details>';
  }
  /* opts: share (v2_plays.flags.limit_schedule_share), phone (sections closed), draw (draw the lines in: first render only) */
  function writeupHtml(p, opts) {
    opts = opts || {};
    var m = mktOf(p.game, p.g), v = m && m.v2 || {}, sf = p.sf, words = sideLabelWords(p), f = flagsOf(p), id = keyId('sv2-wu-', p.key);
    var title = 'The read on ' + (p.g === 'ml' ? sf.side : playTitle(p.game, p.g, sf));
    var date = dateWords(p.game.gst), money = moneyOf(p), series = seriesOf(p);
    var tiered = !!(p.facts && p.facts.tiered);

    /* tiles */
    var c = fmt.cents(sf.price), am = fmt.american(sf.price), ex = v.exec || {}, vf = v.vs_fair || {};
    var priceSub = [];
    if (am) priceSub.push(am + ' in American');
    if (ex.us_best && isNum(ex.us_best.odds)) priceSub.push('Best US book ' + amer(ex.us_best.odds) + (ex.us_best.book && BOOKS.indexOf(ex.us_best.book) >= 0 ? ' at ' + ex.us_best.book : ''));
    var fairV = isNum(vf.fair) ? 'Fair ' + fmt.cents(vf.fair) : '';
    var fp = fairPts(p), fairSub = fp == null ? (vf.why === 'ticket_line_not_main_at_cut' ? 'Off Pinnacle\'s main line' : 'No fair price stored') : fp === 0 ? 'Level with fair' : fmt.line(Math.abs(fp)) + ' pts ' + (fp > 0 ? 'better' : 'worse') + ' than fair';
    if (isNum(vf.line)) fairSub += ', line ' + lineTxt(vf.line, p.g);
    var gr = isObj(v.graded) && v.graded.result ? v.graded : null;
    var stat = gr ? '<p class="sv2-wu-v">Final ' + esc(gr.score || '') + '</p><p class="sv2-wu-s">' + esc({ won: 'Won', lost: 'Lost', push: 'Push' }[gr.result] || '') + '</p>' :
      '<p class="sv2-wu-v">' + (isNum(p.cut) ? 'Freezes ' + esc(ct.time(p.cut, true)) : '') + '</p><p class="sv2-wu-s">' + sizeCellHtml(p) + '</p>';
    var tiles = '<div class="sv2-wu-tiles">' +
      '<div class="sv2-card-inset sv2-wu-tile"><p class="sv2-h2">The play</p><p class="sv2-wu-v">' + esc(p.g === 'ml' ? sf.side : playTitle(p.game, p.g, sf)) + '</p><p class="sv2-wu-s">' + esc(gameLabel(p.game)) + ', ' + esc(marketLabel(p.g)) + '</p><p class="sv2-wu-s">' + ui.tier(p.tier) + '</p></div>' +
      '<div class="sv2-card-inset sv2-wu-tile"><p class="sv2-h2">The price</p><p class="sv2-wu-v sv2-num">' + esc(c || '') + '</p>' + (priceSub.length ? '<p class="sv2-wu-s">' + esc(priceSub.join(', ')) + '</p>' : '') + '<p class="sv2-wu-s sv2-mut">Price now</p></div>' +
      '<div class="sv2-card-inset sv2-wu-tile"><p class="sv2-h2">Line and fair</p><p class="sv2-wu-v sv2-num">' + esc(fairV) + '</p><p class="sv2-wu-s">' + esc(fairSub) + '</p></div>' +
      '<div class="sv2-card-inset sv2-wu-tile"><p class="sv2-h2">Status</p>' + stat + '</div></div>';

    /* the takeaway */
    var tk = takeaway({ flags: f, side: words.side, other: words.other || (money ? money.other : null), g: p.g, money: money, size: p.units > 0, graded: gr });
    var take = '<div class="sv2-card-inset sv2-wu-take"><p class="sv2-h2">The takeaway</p><p class="sv2-wu-tk">' + tk.map(function (s) { return esc(s); }).join(' ') + '</p></div>';

    /* section 1: who is on each side */
    var sec1 = '';
    if (money) {
      var names = marketOrder(p, [money.side, money.other]), hv = heavier(money.mine.usd, money.theirs.usd), heavyName = hv === 'a' ? money.side : hv === 'b' ? money.other : null;
      sec1 = sectionHtml('1', 'Who is on each side', '<div class="sv2-wu-sides">' + names.map(function (n) { return sideHtml(p, { name: n, data: money.sides[n] }, tiered, n === heavyName); }).join('') + '</div>', !opts.phone, id + '-s1');
    }
    /* section 2: where the line went */
    var sec2 = '', pn = f ? pinNums(f) : null, ln = f ? lineNums(f, p.g) : null;
    if (f || series) {
      var head = '';
      if (pn) head += '<p class="sv2-h2">Pinnacle ' + esc(words.side) + ' price</p><p class="sv2-wu-big sv2-num">' + fromTo(pn.from, pn.to) + '</p>';
      if (ln && f.line.kind !== 'price') {
        head += '<p class="sv2-h2">Market line</p><p class="sv2-wu-big sv2-num">' + fromTo(ln.from, ln.to) + '</p>';
        var xt = f.line.extreme, nm = isObj(f.line.pin) ? f.line.pin : null;
        if (isObj(xt) && isNum(xt.value) && BOOKS.indexOf(xt.book) >= 0) head += '<p class="sv2-wu-s">' + (nm && isNum(nm.from) && isNum(nm.to) ? (nm.to < nm.from ? 'Lowest: ' : nm.to > nm.from ? 'Highest: ' : 'Furthest: ') : 'Furthest: ') + esc(xt.book + ' ' + lineTxt(xt.value, p.g)) + '</p>';
      } else if (ln) head += '<p class="sv2-h2">Books\' price</p><p class="sv2-wu-big sv2-num">' + fromTo(ln.from, ln.to) + '</p>';
      var chips = fullChips(p, words).map(function (ch) {
        return '<span class="sv2-fl" data-flag="' + ch.k + '"' + (ch.tip ? ' title="' + esc(ch.tip) + '"' : '') + '>' + flagIcon(ch.state) + '<span>' + esc(ch.text) + '</span>' + (ch.tip ? '<span class="sv2-sr">. ' + esc(ch.tip) + '</span>' : '') + '</span>';
      }).join('');
      var byBook = '';
      if (!series && f && f.line && isObj(f.line.by_book)) {
        byBook = BOOKS.filter(function (b) { var r = f.line.by_book[b]; return Array.isArray(r) && isNum(r[0]) && isNum(r[1]); }).map(function (b) {
          var r = f.line.by_book[b], s = f.line.kind === 'price' ? [amer(r[0]), amer(r[1])] : [lineTxt(r[0], p.g), lineTxt(r[1], p.g)];
          return '<li><span>' + esc(b) + '</span><span class="sv2-num">' + esc(s[0] + ' to ' + s[1]) + '</span></li>';
        }).join('');
        byBook = byBook ? '<ul class="sv2-wu-books">' + byBook + '</ul>' : '';
      }
      var fact = limitLine(f, opts.share, p.sport);
      var text = '<div class="sv2-wu-hl">' + head + (chips ? '<div class="sv2-wu-chips">' + chips + '</div>' : '') + byBook + (fact ? '<p class="sv2-wu-fact">' + esc(fact) + '</p>' : '') + '</div>';
      var chart = series ? chartsHtml(p, series, words, { draw: !!opts.draw, phone: !!opts.phone }) : '';
      sec2 = sectionHtml('2', 'Where the line went', '<div class="sv2-wu-line' + (chart ? ' has-chart' : '') + '">' + text + chart + '</div>', !opts.phone, id + '-s2');
    }
    /* footer */
    var size = p.units > 0 && SV2.sizesOk() ? ' The size is a flat 1u from an untested rule.' : p.sport === 'cfb' ? ' ' + T.noSize + '.' : '';
    var foot = '<footer class="sv2-wu-ft"><p>Wallets: Polymarket public positions.' + (f || series ? ' Lines: ' + BOOKS.join(', ') + '.' : '') + ' Times Central. Context only, not a bet signal.' + esc(size) + '</p><p class="sv2-wu-brand">Sharp Money</p></footer>';
    return '<div class="sv2-wu-wrap"><article class="sv2-card sv2-acc-ink sv2-wu" aria-labelledby="' + id + '-t">' +
      '<header class="sv2-wu-hd"><div class="sv2-wu-hl1"><p class="sv2-wu-ey"><span>Sharp Money</span><span class="sv2-sr">, </span><span>Play breakdown</span><span class="sv2-sr">, </span><span>' + esc(eyebrowOf(p.sport)) + '</span></p>' +
      '<h3 class="sv2-wu-t" id="' + id + '-t">' + esc(title) + '</h3></div>' + (date ? '<span class="sv2-wu-date">' + esc(date) + '</span>' : '') + '</header>' +
      tiles + take + sec1 + sec2 + foot + '</article></div>';
  }

  SV2.sharpsPage = {
    collectPlays: collectPlays, sortPlays: sortPlays, groupBands: groupBands, reasonOf: reasonOf, evidenceLines: evidenceLines,
    contextRows: contextRows, passes: passes, cleanFilters: cleanFilters, playTitle: playTitle, gameLabel: gameLabel, nextCut: nextCut,
    execLines: execLines, fairLine: fairLine,
    SORTS: SORTS, SORT_ORDER: SORT_ORDER, cleanSort: cleanSort, nextSort: nextSort, sortFlat: sortFlat, viewOf: viewOf, fairPts: fairPts,
    vsFairCell: vsFairCell, splitCell: splitCell, walletsCell: walletsCell, sizeCell: sizeCell,
    flagsOf: flagsOf, flagChips: flagChips, chipsHtml: chipsHtml, movesOf: movesOf, chartPoints: chartPoints, stepPath: stepPath, extremes: extremes, seriesOf: seriesOf,
    chartTable: chartTable, moneyOf: moneyOf, sideRows: sideRows, limitMoney: limitMoney, takeaway: takeaway, limitLine: limitLine, fullChips: fullChips, writeupHtml: writeupHtml,
    marketOrder: marketOrder, dateWords: dateWords, eyebrowOf: eyebrowOf, sideLabelWords: sideLabelWords, BOOKS: BOOKS
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
    var draw = !DRAWN[p.key]; DRAWN[p.key] = true;
    var vp = store.cards && store.cards.v2_plays, share = vp && vp.flags && vp.flags.limit_schedule_share;
    return writeupHtml(p, { share: share, phone: isPhoneNow(), draw: draw }) + '<div class="sv2-sp-body">' +
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
      '<td class="sv2-tb-c c-play"><span class="sv2-tb-title"><b>' + esc(title) + '</b>' + (sameKeys[p.key] ? ' ' + ui.chip(T.sameTag, 'muted') : '') + '</span><span class="sv2-tb-mu">' + ui.matchup(p.game, gameLabel(p.game)) + '</span>' + chipsHtml(p) + '</td>' +
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
      st.hasMoves = all.some(function (p) { var m = movesOf(p); return m.pin || m.line; });
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
    function eff() { var f = Object.assign({}, st.f), hs = SV2.hostSport(); if (hs != null) f.sport = hs; if (!st.hasMoves) f.moves = 'all'; return f; }
    function isPhone() { return !!(window.matchMedia && window.matchMedia('(max-width: 767px)').matches); }
    function groupItems(key) {
      if (key === 'tier') return [['all', 'All']].concat(copy.tierOrder.map(function (t) { return [t, copy.tier[t].word]; }));
      if (key === 'market') return [['all', 'All']].concat(T.marketOrder.map(function (m) { return [m, T.market[m]]; }));
      if (key === 'moves') return [['all', 'All'], ['pin', 'Pinnacle moved'], ['line', 'Market line moved']];
      return STARTS;
    }
    var GROUPS_ALL = [['tier', 'Evidence tier'], ['market', 'Market'], ['starts', 'Starts'], ['moves', 'Market moves']];
    /* the Market moves group exists only while some shown play carries stored flags; a saved value is ignored (eff) while it is hidden */
    function groups() { return st.hasMoves ? GROUPS_ALL : GROUPS_ALL.slice(0, 3); }
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
      if (k === 'moves') return !!movesOf(p)[v];
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
    function activeKeys() { return groups().map(function (g) { return g[0]; }).filter(function (k) { return st.f[k] !== 'all'; }); }
    function itemLabel(k, v) { var it = groupItems(k).filter(function (x) { return x[0] === v; })[0]; return it ? it[1] : v; }

    function panelHtml(d) {
      return '<div class="sv2-sp-pbody">' + groups().map(function (g) {
        var k = g[0];
        return '<div class="sv2-sp-fg" role="group" aria-label="' + esc(g[1]) + '"><h3 class="sv2-h2">' + esc(g[1]) + '</h3><div class="sv2-sp-chips">' +
          groupItems(k).map(function (it) {
            return '<button type="button" class="sv2-sp-fc sv2-press sv2-press-chip" data-sp-fc="' + k + '" data-v="' + esc(it[0]) + '" aria-pressed="' + (st.f[k] === it[0]) + '">' + esc(it[1]) + ' <span class="sv2-cnt sv2-num">' + (d ? countFor(d, k, it[0]) : 0) + '</span></button>';
          }).join('') + '</div></div>';
      }).join('') + '</div><div class="sv2-sp-pf"><button type="button" class="sv2-link sv2-sp-reset" data-sp-reset>Reset</button><button type="button" class="sv2-sp-done sv2-press sv2-press-btn" data-sp-done>Done</button></div>';
    }
    function activeHtml() {
      return activeKeys().map(function (k) {
        var g = groups().filter(function (x) { return x[0] === k; })[0][1], w = itemLabel(k, st.f[k]);
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
    function resetFilters() { st.f.tier = 'all'; st.f.market = 'all'; st.f.starts = 'all'; st.f.moves = 'all'; st.wallet = null; lsSet(FKEY, JSON.stringify(st.f)); }
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
      if (R && R.frozenBox) h += R.frozenBox(sp);   /* the Frozen plays box, from the record module (loads lazily, refreshes itself in place) */
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
