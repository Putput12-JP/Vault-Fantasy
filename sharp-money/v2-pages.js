/* Sharp Money V2 pages for the Halaska layout (the sidebar app in sharp-money/index.html).
   index.html is a hand-patched bundle; scripts/sharp_money_card/patch_v2.py wires these pages into it (sidebar entries, routes, the phone redirect) and exposes the
   kit this file draws with as window.__smKit(). This file holds all the V2 logic and views so it stays readable and testable.

   Rules live in sharp-money/v2/gates.js (window.V2Gates), the one copy shared with the standalone V2 page and the headless play log.
   Sharp-account money is context only: nothing here ranks by it or counts it toward an agree total.
   Evidence: docs/retro/sharp-v2-evidence.md, sharp-v2-data.md, sharp-v2-tells.md, sharp-v2-forward-log.md. */
(function () {
  'use strict';
  var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname), LIVE = /[?&]live\b/.test(location.search);
  var RAW = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/', MAIN = LOCAL && !LIVE ? '/' : RAW + 'main/';
  var SRC = {
    props: RAW + 'sharp-data/props.json', tape: RAW + 'sharp-data/prop_close_tape.json', plays: RAW + 'sharp-data/v2_plays.json',
    edge: MAIN + 'data/exchange_edge_live.json', edgeRec: MAIN + 'data/exchange_edge_record.json', keys: MAIN + 'data/nfl_key_numbers.json',
    lag: MAIN + 'data/lead_lag.json', age: MAIN + 'data/book_age.json', sb: MAIN + 'data/model_scoreboard.json', backfill: MAIN + 'data/v2_backfill.json', rg: MAIN + 'docs/prop-clv-regrade.json'
  };
  var CT = { timeZone: 'America/Chicago' };
  var SPORT = { all: 'All', nfl: 'NFL', cfb: 'CFB', nba: 'NBA' };
  var kit = function () { return window.__smKit(); };
  var G = function () { return window.V2Gates; };

  /* ---------- data: every file the V2 pages read, fetched once, shared by all pages, refreshed every 2 minutes ---------- */
  var STORE = { files: {}, ts: 0, busy: null, subs: new Set() };
  function get(u) { return fetch(u + (u.indexOf('?') >= 0 ? '&' : '?') + 't=' + Math.floor(Date.now() / 120000), { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  function fetchAll() {
    if (STORE.busy) return STORE.busy;
    var names = Object.keys(SRC);
    STORE.busy = Promise.all(names.map(function (k) { return get(SRC[k]); })).then(function (vals) {
      var f = {}; names.forEach(function (k, i) { f[k] = vals[i]; });
      STORE.files = f; STORE.ts = Date.now();
    }).then(function () { STORE.busy = null; STORE.subs.forEach(function (fn) { fn(); }); }, function () { STORE.busy = null; });
    return STORE.busy;
  }
  function useFiles() {
    var U = kit().U, s = U.useState(0), set = s[1];
    U.useEffect(function () {
      var fn = function () { set(function (x) { return x + 1; }); };
      STORE.subs.add(fn);
      loadAssets();
      if (!STORE.ts || Date.now() - STORE.ts > 100000) fetchAll();
      var t = setInterval(function () { if (Date.now() - STORE.ts > 110000) fetchAll(); }, 30000);
      return function () { STORE.subs.delete(fn); clearInterval(t); };
    }, []);
    return STORE.files;
  }
  /* Take a stance: one side per market. For each prop (player, stat, line) and each game market, keep the side with the better edge and drop the other, so a
     bet never shows up as both Over and Under. Candidates on the favoured side stay (the same side can be priced at a book and at an exchange). */
  function stance(list) {
    var score = function (c) { return c.worst != null && c.refs.length > 1 ? c.worst : c.best != null ? c.best : -9; };
    var key = function (c) { return c.kind === 'prop' ? 'p|' + c.row.pid + '|' + c.row.mkt + '|' + c.row.line : 'g|' + c.gk + '|' + c.m; };
    var top = {};
    list.forEach(function (c) { var k = key(c), v = score(c); if (!top[k] || v > top[k].v) top[k] = { v: v, side: c.side }; });
    return list.filter(function (c) { return top[key(c)].side === c.side; });
  }
  function useBuilt(D, F) {
    var U = kit().U;
    return U.useMemo(function () {
      if (!D || !G()) return { all: [], cand: [] };
      var b = G().build({ D: D, P: F.props, T: F.tape, E: F.edge, now: Date.now() / 1000 });
      return { all: stance(b.all), cand: stance(b.cand) };
    }, [D && D.ts, STORE.ts]);
  }

  /* ---------- small helpers ---------- */
  var pct = function (x, d) { return G().pct(x, d); }, spct = function (x, d) { return G().spct(x, d); }, sgn = function (n) { return G().sgn(n); };
  var am = function (n) { return n == null ? '-' : (n > 0 ? '+' : '') + n; };
  var mean = function (a) { return a.length ? a.reduce(function (s, x) { return s + x; }, 0) / a.length : null; };
  function when(ts) { return new Date(ts * 1000).toLocaleString('en-US', Object.assign({ weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }, CT)).replace(/[ ,]/g, function (c) { return c === ',' ? '' : ' '; }) + ' CT'; }
  function dur(sec) { var m = Math.round(sec / 60); return m < 1 ? 'under a minute' : m < 60 ? m + ' min' : m < 1440 ? Math.round(m / 60) + ' h' : Math.round(m / 1440) + ' d'; }
  var tnow = function () { return Date.now() / 1000; };

  /* ---------- scoring a rule: same rule as docs/signal-research.md. Trust needs 100+ games, z of 1.64+ against the price and positive CLV ---------- */
  function stat(rows) {
    var g = rows.filter(function (r) { return r.result === 1 || r.result === -1; }), w = g.filter(function (r) { return r.result === 1; }).length, n = g.length;
    var f = g.filter(function (r) { return r.fair != null; }), fw = f.filter(function (r) { return r.result === 1; }).length;
    var ex = f.length ? fw / f.length - mean(f.map(function (r) { return r.fair; })) : null;
    var v = f.reduce(function (s, r) { return s + r.fair * (1 - r.fair); }, 0), z = f.length && v > 0 ? (fw - f.reduce(function (s, r) { return s + r.fair; }, 0)) / Math.sqrt(v) : null;
    var c = rows.filter(function (r) { return r.clv != null; }).map(function (r) { return r.clv; });
    var u = rows.filter(function (r) { return r.units != null; }).map(function (r) { return r.units; }).sort(function (a, b) { return b - a; });
    var top = u.slice(0, 5).filter(function (x) { return x > 0; }).reduce(function (s, x) { return s + x; }, 0), tot = u.reduce(function (s, x) { return s + x; }, 0);
    var verdict = n < 30 ? ['Too few', 'muted'] : (n >= 100 && z != null && z >= 1.64 && mean(c) > 0) ? ['Trust', 'success'] : (ex != null && ex <= 0) ? ['Ignore', 'danger'] : ['Watch', 'warning'];
    return { n: n, w: w, l: n - w, win: n ? w / n : null, ex: ex, z: z, clv: c.length ? mean(c) : null, clvN: c.length, fn: f.length, units: u.length ? tot : null, uN: u.length, unitsNoTop5: u.length ? tot - top : null, verdict: verdict };
  }
  function rules(D) {
    var pk = ((D && D.picks) || []).filter(function (p) { return p.result === 1 || p.result === -1 || p.result === 0; });
    var kind = function (k) { return pk.filter(function (p) { return p.kinds && p.kinds.length === 1 && p.kinds[0] === k; }); };
    var cards = [
      ['Pinnacle line move', 'The line moved toward this side. Only picks where this was the one signal.', stat(kind('line'))],
      ['Money vs bets', 'More of the money than the bets is on this side. Only picks where this was the one signal.', stat(kind('money'))],
      ['+EV at a book', 'A US book still hangs a price Pinnacle says is good. Only picks where this was the one signal.', stat(kind('behind'))],
      ['Two signals agree', 'The headline of the old Top Reads. It went worse than one signal on its own.', stat(pk.filter(function (p) { return p.kinds && p.kinds.length === 2; }))],
      ['Three signals agree', 'Too few games to say anything.', stat(pk.filter(function (p) { return p.kinds && p.kinds.length === 3; }))],
      ['Both sides flagged', 'The same market flagged on both sides. No play is made from these.', stat(pk.filter(function (p) { return p.conflict; }))]];
    var ctx = stat(((D && D.sharpContext) || []).filter(function (p) { return p.result === 1 || p.result === -1 || p.result === 0; }));
    return { pk: pk, cards: cards, ctx: ctx };
  }

  /* ---------- view kit ---------- */
  function ui() {
    var k = kit(), n = k.V(), h = k.U.createElement, z = k.z;
    var lab = { textTransform: 'uppercase', letterSpacing: '0.1em' };
    var tone = function (x) { return x == null ? 'muted' : x > 0 ? 'ok' : x < 0 ? 'bad' : 'muted'; };
    var tile = function (label, value, sub, t) {
      return h('div', { style: { background: n.bgSubtle, borderRadius: z.radius.md, padding: '10px 12px', minWidth: 0 } },
        h(k.T, { size: 'xs', mono: true, style: lab }, label), h('div', null, h(k.M, { size: 'lg', mono: true, weight: 'semibold' }, value)),
        sub != null ? h(k.se, { tone: t || 'muted', size: 'sm', mono: true }, sub) : null);
    };
    var kv = function (label, value, t, key) {
      return h('div', { key: key || label, style: { display: 'flex', justifyContent: 'space-between', gap: 12, padding: '7px 0', borderTop: '1px solid ' + n.borderSubtle } },
        h(k.T, { size: 'sm' }, label), h(k.se, { tone: t, size: 'sm', mono: true, weight: 'medium', style: { textAlign: 'right' } }, value));
    };
    var grid = function (min, kids, gap) { return h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(min(' + min + 'px,100%),1fr))', gap: gap || 12, alignItems: 'start' } }, kids); };
    var row = function (cols, cells, key, onClick, head) {
      return h('div', { key: key, onClick: onClick, role: onClick ? 'button' : undefined, tabIndex: onClick ? 0 : undefined,
        style: { display: 'grid', gridTemplateColumns: cols, gap: 10, alignItems: 'center', padding: head ? '8px 14px' : '10px 14px', borderTop: head ? 'none' : '1px solid ' + n.borderSubtle, cursor: onClick ? 'pointer' : 'default', minWidth: 0 } }, cells);
    };
    var th = function (t, i) { return h('span', { key: i, style: { textAlign: i ? 'right' : 'left' } }, h(k.Lp, null, t)); };
    var td = function (c, i, o) { return h('span', { key: i, style: { textAlign: i ? 'right' : 'left', minWidth: 0 } }, c); };
    var table = function (min, rows) { return h(k.K, { padding: 0 }, h('div', { style: { overflowX: 'auto' } }, h('div', { style: { minWidth: min } }, rows))); };
    return { k: k, n: n, h: h, z: z, lab: lab, tone: tone, tile: tile, kv: kv, grid: grid, row: row, th: th, td: td, table: table };
  }
  function Wait(p) { var k = kit(), h = k.U.createElement; return h('div', { style: { display: 'grid', gap: 12, marginTop: 20 } }, h(k._a, { height: 96, rounded: true }), h(k._a, { height: 220, rounded: true })); }
  function Details(u, title, body) {
    var h = u.h, n = u.n;
    return h('details', { style: { margin: '12px 0', border: '1px solid ' + n.border, borderRadius: u.z.radius.md, padding: '10px 14px' } },
      h('summary', { style: { cursor: 'pointer', color: n.text, fontWeight: 600, fontSize: 14 } }, title), h('div', { style: { marginTop: 8, display: 'grid', gap: 6 } }, body));
  }

  /* ---------- Plays ---------- */
  var TIER = { play: ['Plays', 'success'], watch: ['Watch', 'warning'], pass: ['Passed', 'default'] };
  function palOf(n) { return { text: n.text, mut: n.textSecondary, dim: n.textTertiary, line: n.border, bg: n.bg, tile: n.bgSubtle, acc: n.accent, good: n.success, bad: n.danger, warn: n.warning }; }
  function PlayCard(u, c, openGame, F, D) {
    var k = u.k, h = u.h, go = c.gk && openGame ? function () { openGame(c.gk); } : undefined;
    return h(k.K, { key: c.id, padding: 0, hover: !!go, onClick: go }, h('div', { dangerouslySetInnerHTML: { __html: cardHtml(c, F, palOf(u.n), D) } }));
  }
  function PassRow(u, c, openGame) {
    var h = u.h, k = u.k;
    return u.row('minmax(0,1fr) auto', [
      h('div', { key: 'a', style: { minWidth: 0 } }, h(k.M, { size: 'base', weight: 'semibold' }, c.title), h(k.T, { size: 'sm' }, '  at ' + c.price.book + ' ' + am(c.price.am)), h('div', null, h(k.T, { size: 'sm' }, c.reasons[0]))),
      h('div', { key: 'b', style: { textAlign: 'right' } }, h(k.T, { size: 'xs', mono: true }, SPORT[c.sport] + ' · ' + (c.start ? when(c.start).split(' ').slice(0, 3).join(' ') : '')))
    ], c.id, c.gk && openGame ? function () { openGame(c.gk); } : undefined);
  }
  function Plays(props) {
    var k = kit(), U = k.U, h = U.createElement, F = useFiles(), built = useBuilt(props.D, F), u = ui(), n = u.n;
    var s = U.useState('play'), tier = s[0], setTier = s[1], s2 = U.useState(12), nProps = s2[0], setNProps = s2[1];
    if (!G()) return h('div', null, h(k.T, { size: 'base' }, 'The V2 rules did not load. Reload the page.'));
    if (!STORE.ts) return h(Wait);
    var sport = props.sport || 'all';
    var inSport = function (c) { return sport === 'all' || c.sport === sport; };
    var list = function (t) { return built.cand.filter(function (c) { return c.tier === t && inSport(c); }); };
    var nP = list('play').length, nW = list('watch').length, nX = list('pass').length;
    var opts = ['Plays ' + nP, 'Watch ' + nW, 'Passed ' + nX], cur = tier === 'play' ? opts[0] : tier === 'watch' ? opts[1] : opts[2];
    var items = list(tier);
    var body;
    if (tier === 'pass') body = items.length ? h(k.K, { padding: 0 }, items.map(function (c) { return PassRow(u, c, props.openGame); })) : h(k.K, { padding: 20 }, h(k.M, { size: 'md', weight: 'medium' }, 'Nothing passed over'));
    else if (!items.length) body = h(k.K, { padding: 20 }, h(k.M, { size: 'md', weight: 'medium' }, tier === 'play' ? 'Nothing clears every gate right now' : 'Nothing on watch'),
      h('div', { style: { marginTop: 4 } }, h(k.T, { size: 'base' }, tier === 'play' ? 'That is the honest answer.' + (nW ? ' ' + nW + ' price' + (nW === 1 ? ' has' : 's have') + ' one reference only (Watch).' : '') + (nX ? ' ' + nX + ' looked good against one price but failed a gate (Passed).' : '') : 'Prices that beat one reference but have no second price to confirm them.')));
    else body = u.grid(420, items.map(function (c) { return PlayCard(u, c, props.openGame, F, props.D); }));
    var propRows = built.all.filter(function (c) { return c.kind === 'prop' && inSport(c); }).sort(function (a, b) { return (b.worst == null ? -9 : b.worst) - (a.worst == null ? -9 : a.worst); });
    var cols = 'minmax(0,1fr) 150px 80px 80px 80px';
    var wide = !props.narrow;
    var table = propRows.length ? u.table(wide ? 560 : 360, [u.row(wide ? cols : 'minmax(0,1fr) 70px 70px', wide ? ['Prop', 'Best US price', 'Pinnacle', 'Exchange', 'Worst'].map(u.th) : ['Prop', 'Pinnacle', 'Exchange'].map(u.th), 'head', null, true)].concat(propRows.slice(0, nProps).map(function (c) {
      var pin = c.refs.find(function (r) { return r.n === 'Pinnacle'; }), ex = c.refs.find(function (r) { return r.n === 'Exchange'; });
      var e = function (r) { return r ? h(k.se, { tone: r.edge >= G().GATES.MIN_EDGE ? 'ok' : r.edge < 0 ? 'bad' : 'muted', size: 'sm', mono: true }, spct(r.edge)) : h(k.T, { size: 'sm' }, '-'); };
      var name = h('div', { style: { minWidth: 0 } }, h(k.M, { size: 'sm', weight: 'medium' }, c.title), h('div', null, h(k.T, { size: 'xs' }, c.sub + ' · ' + (c.start ? when(c.start) : '') + ' · ' + (c.tier === 'play' ? 'Play' : c.tier === 'watch' ? 'Watch' : c.tier === 'pass' ? 'Pass' : 'No edge'))));
      return wide ? u.row(cols, [name, h(k.M, { size: 'sm', mono: true }, c.price.book + ' ' + am(c.price.am)), e(pin), e(ex), c.worst == null || c.refs.length < 2 ? h(k.T, { size: 'sm' }, '-') : h(k.se, { tone: c.worst >= G().GATES.MIN_EDGE ? 'ok' : 'muted', size: 'sm', mono: true }, spct(c.worst))].map(u.td), c.id)
        : u.row('minmax(0,1fr) 70px 70px', [name, e(pin), e(ex)].map(u.td), c.id);
    })).concat(propRows.length > nProps ? [h('div', { key: 'more', style: { padding: 12, borderTop: '1px solid ' + n.borderSubtle } }, h(k.co, { variant: 'secondary', size: 'sm', onClick: function () { setNProps(nProps + 20); } }, 'Show more (' + (propRows.length - nProps) + ' left)'))] : [])) : h(k.K, { padding: 20 }, h(k.T, { size: 'base' }, 'No prop with a usable price right now. The board lists only players whose game has not started.'));
    var gates = G().GATES;
    return h('div', { style: { display: 'grid', gap: 14, marginTop: 20 } },
      h('div', { dangerouslySetInnerHTML: { __html: recordHtml(F, palOf(n)) } }),
      h('div', { style: { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' } }, h(k.ve, { options: opts, value: cur, onChange: function (o) { setTier(o === opts[0] ? 'play' : o === opts[1] ? 'watch' : 'pass'); } }),
        h(k.T, { size: 'sm' }, 'Ranked by the worst-case edge across two independent fair prices. Sport filter: top bar.')),
      body,
      Details(u, 'How a play qualifies', [
        h(k.T, { key: 1, size: 'sm' }, '1. The price is at a US sportsbook (not a pick’em app, and not the exchange used as the check).'),
        h(k.T, { key: 2, size: 'sm' }, '2. Two independent fair prices exist: Pinnacle, and the exchange (Kalshi and Novig at the exact line). A moneyline play can use Kalshi and Novig; a prop needs both.'),
        h(k.T, { key: 3, size: 'sm' }, '3. The price beats both by ' + pct(gates.MIN_EDGE, 0) + ' or more, and the two fair prices sit within ' + gates.AGREE * 100 + ' points of each other.'),
        h(k.T, { key: 4, size: 'sm' }, '4. The edge is not over ' + pct(gates.BIG_EDGE, 0) + ': calls that big have lost money (21-32, ROI -15%).'),
        h(k.T, { key: 5, size: 'sm' }, '5. Both sides of the same market are not flagged at once.'),
        h(k.T, { key: 6, size: 'sm' }, 'A play is a better price than the market, not a prediction. Sharp-account money is context only and never ranks a play.')]),
      h(k.je, { hint: 'Every prop on the board against both references' }, 'Prop prices'), table);
  }

  /* ---------- Signals ---------- */
  function SigCard(u, name, desc, s) {
    var k = u.k, h = u.h, vv = s.verdict;
    return h(k.K, { key: name, padding: 16 }, h('div', { style: { display: 'grid', gap: 6 } },
      h('div', { style: { display: 'flex', justifyContent: 'space-between', gap: 8 } }, h(k.T, { size: 'xs', mono: true, style: u.lab }, name), h(k.oe, { variant: vv[1] === 'muted' ? 'default' : vv[1] }, vv[0])),
      h(k.M, { size: 'lg', mono: true, weight: 'semibold' }, s.n ? s.w + '-' + s.l : 'none graded'),
      h(k.T, { size: 'sm' }, s.n ? pct(s.win) + ' won' + (s.ex != null ? '. On the ' + s.fn + ' picks that logged the market’s fair price, ' + (s.ex >= 0 ? '+' : '') + (s.ex * 100).toFixed(1) + ' pts against the chance those prices implied.' : '') : ''),
      u.kv('Closing-line value', s.clv == null ? '-' : spct(s.clv) + ' (' + s.clvN + ')', s.clv == null ? 'muted' : s.clv > 0 ? 'ok' : 'bad'),
      s.units != null ? u.kv('Units at stored price', sgn(+s.units.toFixed(1)) + 'u (' + s.uN + ' priced; ' + sgn(+s.unitsNoTop5.toFixed(1)) + 'u without the 5 biggest wins)', 'muted') : null,
      h(k.T, { size: 'xs' }, desc)));
  }
  function Signals(props) {
    var k = kit(), h = k.U.createElement, F = useFiles(), u = ui(), D = props.D;
    var r = rules(D), P = F.props, rec = P && P.propRecord && P.propRecord.all, er = F.edgeRec && F.edgeRec.summary;
    var cards = r.cards.map(function (c) { return SigCard(u, c[0], c[1], c[2]); });
    var out = [h(k.T, { key: 'i', size: 'sm' }, 'What each signal has actually done, measured against the price it was taken at. Trust needs 100+ games, a win rate clearly above that price (z of 1.64+) and positive closing-line value. ' + r.pk.length + ' graded picks. Nothing has reached Trust.'),
      u.grid(330, cards)];
    if (rec) { var hasX = rec.clvXN > 0; out.push(h(k.je, { key: 'pj', hint: 'every call, flat 1 unit' }, 'Prop board calls'),
      h(k.K, { key: 'pk', padding: 16 }, h('div', { style: { display: 'grid', gap: 6 } }, h(k.M, { size: 'lg', mono: true, weight: 'semibold' }, rec.w + '-' + rec.l), h(k.T, { size: 'sm' }, 'ROI ' + spct(rec.roi) + ' on ' + (rec.w + rec.l) + ' settled.'),
        u.kv('CLV on the old close (the price that raised the call)', spct(rec.clv), 'muted'), u.kv('CLV against the exchange close', hasX ? spct(rec.clvX) + ' (' + rec.clvXN + ')' : 'arrives with the next data update', hasX ? (rec.clvX > 0 ? 'ok' : 'bad') : 'muted')))); }
    if (er) out.push(h(k.je, { key: 'ej', hint: 'since ' + (F.edgeRec.since || '') }, 'Novig under Pinnacle'), h(k.K, { key: 'ek', padding: 16 }, h('div', { style: { display: 'grid', gap: 6 } },
      h(k.M, { size: 'lg', mono: true, weight: 'semibold' }, er.wins + '-' + (er.graded - er.wins)), h(k.T, { size: 'sm' }, 'Closing-line value ' + (er.mean_clv == null ? '-' : spct(er.mean_clv / 100, 2)) + ' on ' + er.n_same + ' same-line calls; beat the close ' + (er.beat_close == null ? '-' : pct(er.beat_close, 0)) + '.'))));
    out.push(h(k.je, { key: 'cj', hint: 'never ranks a play' }, 'Context only'), SigCard(u, 'Sharp accounts (Polymarket)', 'Accounts whose past $1k+ bets beat the close. Held out, they did not beat it: 113-122 (48.1%). Shown for context only; never counts toward an agree total.', r.ctx));
    return h('div', { style: { display: 'grid', gap: 14, marginTop: 20 } }, out);
  }

  /* ---------- Record ---------- */
  var PLAY_STATE = { won: ['Won', 'success'], lost: ['Lost', 'danger'], push: ['Push', 'default'], void: ['Void', 'default'], open: ['Open', 'accent'] };
  function rowOf(p) {
    var set = p.status === 'won' || p.status === 'lost' || p.status === 'push', f = p.first || {};
    var fair = f.fairMean != null ? f.fairMean : (f.refs && f.refs.length ? mean(f.refs.map(function (r) { return r.p; })) : null);
    return { p: p, result: p.status === 'won' ? 1 : p.status === 'lost' ? -1 : p.status === 'push' ? 0 : null, fair: fair, clv: p.clv == null ? null : p.clv, units: set ? p.units : null };
  }
  function v2Rows(PL) { return Object.values((PL && PL.plays) || {}).map(rowOf); }
  /* The official record: the live log plus the settled plays backfilled from a finished slate (data/v2_backfill.json). Backfilled rows carry p.backfill. */
  function rowsAll(F) {
    var rows = v2Rows(F.plays), B = F.backfill;
    if (B && B.plays) Object.keys(B.plays).forEach(function (k) { var p = B.plays[k]; if (p.status === 'won' || p.status === 'lost' || p.status === 'push') rows.push(rowOf(p)); });
    return rows;
  }
  function LedgerCard(u, name, desc, rows) {
    var k = u.k, h = u.h, s = stat(rows), cnt = function (x) { return rows.filter(function (r) { return r.p.status === x; }).length; };
    var wins = rows.filter(function (r) { return r.units > 0; }).map(function (r) { return r.units; }).sort(function (a, b) { return b - a; }).slice(0, 5), wsum = wins.reduce(function (a, b) { return a + b; }, 0);
    var roi = s.n && s.units != null ? s.units / s.n : null, roiX = s.n > wins.length && s.units != null ? (s.units - wsum) / (s.n - wins.length) : null;
    var claimed = rows.filter(function (r) { return r.p.first && r.p.first.worst != null; }).map(function (r) { return r.p.first.worst; });
    var su = function (x) { return sgn(+x.toFixed(1)) + 'u'; };
    return h(k.K, { key: name, padding: 16 }, h('div', { style: { display: 'grid', gap: 6 } },
      h('div', { style: { display: 'flex', justifyContent: 'space-between', gap: 8 } }, h(k.T, { size: 'xs', mono: true, style: u.lab }, name + ' · ' + rows.length + ' logged'), h(k.oe, { variant: s.verdict[1] === 'muted' ? 'default' : s.verdict[1] }, s.verdict[0])),
      h(k.M, { size: 'lg', mono: true, weight: 'semibold' }, s.n ? s.w + '-' + s.l : 'none graded'),
      h(k.T, { size: 'sm' }, (s.n ? pct(s.win) + ' won of ' + s.n + ' settled' : rows.length + ' logged, none settled yet') + (cnt('push') ? ', ' + cnt('push') + ' push' : '') + (cnt('void') ? ', ' + cnt('void') + ' void' : '') + (cnt('open') ? ', ' + cnt('open') + ' open' : '')),
      u.kv('ROI, flat 1 unit', roi == null ? '-' : spct(roi) + ' (' + s.n + ' settled)', roi == null ? 'muted' : roi < 0 ? 'bad' : 'ok'),
      u.kv('ROI without top ' + (wins.length || 5) + ' wins', roiX == null ? '-' : spct(roiX) + ' (' + (s.n - wins.length) + ' left)', roiX == null ? 'muted' : roiX < 0 ? 'bad' : 'ok'),
      u.kv('Units', s.units == null ? '-' : su(s.units) + ' (' + s.n + ' settled)', 'muted'),
      u.kv('Units without top ' + (wins.length || 5) + ' wins', s.units == null ? '-' : su(s.units - wsum), 'muted'),
      u.kv('CLV vs exchange close', s.clv == null ? '-' : spct(s.clv) + ' (' + s.clvN + ' with a close)', s.clv == null ? 'muted' : s.clv > 0 ? 'ok' : 'bad'),
      u.kv('Edge claimed at first sight', claimed.length ? spct(mean(claimed)) + ' (' + claimed.length + ')' : '-', 'muted'),
      h(k.T, { size: 'xs' }, desc)));
  }
  function ForwardLog(u, F) {
    var k = u.k, h = u.h, PL = F.plays, rows = rowsAll(F);
    if ((!PL || !PL.plays) && !rows.length) return h(k.K, { padding: 16 }, h('div', { style: { display: 'grid', gap: 6 } }, h(k.oe, { variant: 'warning' }, 'Not started'), h(k.T, { size: 'sm' }, 'The log of V2 plays has not been published yet. Every play is written here once, at first sight, with the price and both reference prices it showed, then frozen and graded. Until it has 100 settled plays, treat a play as a better price, not a proven edge.')));
    if (!rows.length) return h(k.K, { padding: 16 }, h(k.M, { size: 'md', weight: 'medium' }, 'No play logged yet'), h('div', null, h(k.T, { size: 'sm' }, 'The log is running. A play is written the first time one clears every gate before kickoff.')));
    var since = Math.min.apply(null, rows.map(function (r) { return r.p.firstSeen; }));
    var recent = rows.slice().sort(function (a, b) { return b.p.firstSeen - a.p.firstSeen; }).slice(0, 20);
    return h('div', { style: { display: 'grid', gap: 12 } },
      h(k.T, { size: 'sm' }, rows.length + ' play' + (rows.length === 1 ? '' : 's') + ' logged since ' + new Date(since * 1000).toLocaleDateString('en-US', Object.assign({ month: 'short', day: 'numeric' }, CT)) + '. Each is written once at first sight, then frozen. Flat 1 unit at the stored price; CLV is the exchange close over the stored price.'),
      u.grid(330, [LedgerCard(u, 'All V2 plays', 'Props and games together.', rows), LedgerCard(u, 'Props', 'Player props, settled from the box score.', rows.filter(function (r) { return r.p.kind === 'prop'; })), LedgerCard(u, 'Games', 'Moneyline, spread and total, settled from the final score.', rows.filter(function (r) { return r.p.kind !== 'prop'; }))]),
      h(k.K, { padding: 0 }, recent.map(function (r) {
        var p = r.p, f = p.first || {}, st = PLAY_STATE[p.status] || ['', 'default'], px = f.price || {};
        return u.row('minmax(0,1fr) auto', [h('div', { key: 'a', style: { minWidth: 0 } }, h(k.M, { size: 'base', weight: 'semibold' }, f.title), h(k.T, { size: 'sm' }, '  at ' + px.book + ' ' + am(px.am)),
          h('div', null, h(k.T, { size: 'xs' }, (f.sub || '') + ' · first seen ' + when(p.firstSeen) + ' · ' + (f.refs || []).map(function (x) { return x.n + ' ' + spct(x.edge); }).join(', '))),
          p.close ? h('div', null, h(k.T, { size: 'xs' }, 'Exchange close ' + pct(p.close.p) + ' (' + p.close.src + '), CLV ' + spct(p.clv))) : null),
          h('div', { key: 'b', style: { textAlign: 'right' } }, h(k.oe, { variant: st[1] }, st[0]), p.units != null && p.status !== 'open' && p.status !== 'void' ? h('div', null, h(k.se, { tone: p.units > 0 ? 'ok' : p.units < 0 ? 'bad' : 'muted', size: 'sm', mono: true }, sgn(+p.units.toFixed(2)) + 'u')) : null)], p.id);
      })));
  }
  function ModelsBlock(u, D, F, sport) {
    var k = u.k, h = u.h, SB = F.sb, gm = SB && SB.games && SB.games.games, pr = SB && SB.props && SB.props.all;
    var card = function (x, lab) {
      if (!x || !x.close) return null; var c = x.close, bad = c.skill < 0 && c.z <= -1.64;
      return h(k.K, { key: lab, padding: 16 }, h('div', { style: { display: 'grid', gap: 6 } },
        h('div', { style: { display: 'flex', justifyContent: 'space-between', gap: 8 } }, h(k.T, { size: 'xs', mono: true, style: u.lab }, lab), h(k.oe, { variant: bad ? 'danger' : 'warning' }, c.skill < 0 ? (bad ? 'Worse than the market' : 'Level (within noise)') : 'Ahead (not significant)')),
        h(k.se, { tone: c.skill < 0 ? 'bad' : 'ok', size: 'lg', mono: true, weight: 'semibold' }, spct(c.skill)),
        h(k.T, { size: 'sm' }, 'log-loss skill against the market close on ' + c.n + ' (z ' + c.z + '). Negative means the market was closer to what happened.'),
        x.bets ? u.kv('Bets at the close, flat 1u', x.bets.win_close == null ? '-' : pct(x.bets.win_close) + ' won, ' + spct(x.bets.roi_close) + ' ROI (' + x.bets.n_close + ')', 'muted') : null));
    };
    var rows = ((D && D.games) || []).filter(function (g) { return g.start > tnow() && g.model && g.pin && g.pin.sp && (sport === 'all' || g.sport === sport); }).map(function (g) { var mk = -g.pin.sp.line, mm = g.model.margin; return { g: g, mk: mk, mm: mm, gap: mm - mk, tg: g.pin.tot ? g.model.total - g.pin.tot.line : null }; }).sort(function (a, b) { return Math.abs(b.gap) - Math.abs(a.gap); });
    var cols = 'minmax(0,1fr) 90px 90px 70px 80px';
    return h('div', { style: { display: 'grid', gap: 12 } },
      h(k.T, { size: 'sm' }, 'The Vault model sits beside the market and never makes a play on its own. Its record against the closing price decides how much a gap means.'),
      u.grid(330, [card(gm, 'Games: Vault line vs the close'), card(pr, 'Player props: Vault projection vs the close')].filter(Boolean)),
      rows.length ? u.table(520, [u.row(cols, ['Game', 'Market (home)', 'Vault (home)', 'Gap', 'Total gap'].map(u.th), 'head', null, true)].concat(rows.slice(0, 20).map(function (r) {
        return u.row(cols, [h('div', { key: 'a' }, h(k.M, { size: 'sm', weight: 'medium' }, r.g.away.abbr + ' @ ' + r.g.home.abbr), h('div', null, h(k.T, { size: 'xs' }, SPORT[r.g.sport] + ' · ' + when(r.g.start)))),
          h(k.M, { key: 'b', size: 'sm', mono: true }, sgn(-r.mk)), h(k.M, { key: 'c', size: 'sm', mono: true }, sgn(+(-r.mm).toFixed(1))), h(k.M, { key: 'd', size: 'sm', mono: true }, (r.gap > 0 ? '+' : '') + r.gap.toFixed(1)), h(k.M, { key: 'e', size: 'sm', mono: true }, r.tg == null ? '-' : (r.tg > 0 ? '+' : '') + r.tg.toFixed(1))].map(u.td), r.g.key);
      }))) : h(k.K, { padding: 16 }, h(k.T, { size: 'sm' }, 'No game has both a Vault line and a Pinnacle spread right now.')),
      h(k.T, { size: 'xs' }, 'Gap is points toward the home side. A big gap is a prompt to look, not a bet: the model has not beaten the close.'));
  }
  function Record(props) {
    var k = kit(), h = k.U.createElement, F = useFiles(), u = ui(), D = props.D, n = u.n, sport = props.sport || 'all';
    if (!STORE.ts) return h(Wait);
    var r = rules(D), all = r.cards.concat([['Sharp accounts (context only)', 'Never ranks a play.', r.ctx]]), P = F.props, rec = P && P.propRecord && P.propRecord.all, rb = F.rg && F.rg.roi_by_exchange_clv;
    var cols = 'minmax(0,1fr) 70px 54px 70px minmax(0,150px) 80px';
    var rulesTable = u.table(640, [u.row(cols, ['Rule', 'W-L', 'Won', 'CLV', 'Units', ''].map(u.th), 'head', null, true)].concat(all.map(function (c) {
      var s = c[2]; return u.row(cols, [h(k.M, { key: 'a', size: 'sm', weight: 'medium' }, c[0]), h(k.M, { key: 'b', size: 'sm', mono: true }, s.n ? s.w + '-' + s.l : '-'), h(k.M, { key: 'c', size: 'sm', mono: true }, s.n ? pct(s.win, 0) : '-'),
        h(k.se, { key: 'd', tone: s.clv == null ? 'muted' : s.clv > 0 ? 'ok' : 'bad', size: 'sm', mono: true }, s.clv == null ? '-' : spct(s.clv)),
        h('span', { key: 'e' }, s.units == null ? h(k.T, { size: 'sm' }, '-') : h('span', null, h(k.M, { size: 'sm', mono: true }, sgn(+s.units.toFixed(1)) + 'u'), h(k.T, { size: 'xs' }, '  ' + sgn(+s.unitsNoTop5.toFixed(1)) + 'u w/o top 5'))),
        h(k.oe, { key: 'f', variant: s.verdict[1] === 'muted' ? 'default' : s.verdict[1] }, s.verdict[0])].map(u.td), c[0]);
    })));
    var rbRow = function (kk, l) { var x = rb && rb[kk]; return x && x.n ? u.row('minmax(0,1fr) 70px 70px 80px', [h(k.M, { key: 'a', size: 'sm' }, l), h(k.M, { key: 'b', size: 'sm', mono: true }, x.n), h(k.M, { key: 'c', size: 'sm', mono: true }, pct(x.hit)), h(k.se, { key: 'd', tone: x.roi < 0 ? 'bad' : 'ok', size: 'sm', mono: true }, spct(x.roi))].map(u.td), kk) : null; };
    return h('div', { style: { display: 'grid', gap: 14, marginTop: 20 } },
      h(k.je, { hint: 'written once at first sight, then frozen and graded' }, 'V2 plays'), ForwardLog(u, F),
      h(k.je, { hint: 'same scoring everywhere; 100+ games to be called' }, 'Every rule, graded'), rulesTable,
      rec ? h(k.K, { padding: 16 }, h('div', { style: { display: 'grid', gap: 6 } }, h('div', { style: { display: 'flex', justifyContent: 'space-between' } }, h(k.T, { size: 'xs', mono: true, style: u.lab }, 'Prop board calls'), h(k.oe, { variant: rec.roi < 0 ? 'danger' : 'warning' }, rec.roi < 0 ? 'Losing' : 'Watch')),
        h(k.M, { size: 'lg', mono: true, weight: 'semibold' }, rec.w + '-' + rec.l), h(k.T, { size: 'sm' }, 'ROI ' + spct(rec.roi) + ' at flat 1 unit on ' + (rec.w + rec.l) + ' settled.'),
        u.kv('CLV on the old close (the price that raised the call)', spct(rec.clv), 'muted'), u.kv('CLV against the exchange close', rec.clvXN > 0 ? spct(rec.clvX) + ' (' + rec.clvXN + ')' : 'arrives with the next data update', rec.clvXN > 0 ? (rec.clvX > 0 ? 'ok' : 'bad') : 'muted'))) : null,
      rb ? h(k.K, { padding: 0 }, [h('div', { key: 'cap', style: { padding: '12px 14px' } }, h(k.T, { size: 'sm' }, 'Does beating the independent close go with winning? A hindsight check on the prop calls, not a rule usable at call time. Even the best slice has not earned its price.'))].concat([u.row('minmax(0,1fr) 70px 70px 80px', ['Calls that', 'Calls', 'Hit', 'ROI'].map(u.th), 'head', null, true), rbRow('beat_exchange_close', 'beat the exchange close'), rbRow('missed_exchange_close', 'missed it'), rbRow('beat_exchange_by_2pts', 'beat it by more than 2%'), rbRow('beat_both_exchange_and_pinnacle', 'beat both exchange and Pinnacle closes'), rbRow('beat_neither', 'beat neither')].filter(Boolean))) : null,
      h(k.je, { hint: 'the Vault line beside the market, scored against the close' }, 'Models'), ModelsBlock(u, D, F, sport));
  }

  /* ---------- Game: who is behind (book tape) and the spread key numbers ---------- */
  var MK = { ml: 'Money', sp: 'Spread', tot: 'Total' };
  function clockLine(F, sport, m) {
    var d = F.lag && F.lag.by_sport && F.lag.by_sport[sport] && F.lag.by_sport[sport][m], uu = d && d.by_book && d.by_book['US books (all five)'], mk = MK[m].toLowerCase();
    if (!uu || uu.n < 15) return 'Not enough ' + SPORT[sport] + ' ' + mk + ' moves in the tape yet to time how fast books follow Pinnacle' + (d ? ' (' + d.events + ' so far)' : '') + '.';
    var med = uu.median_min != null ? ', after a median ' + dur(uu.median_min * 60) : '';
    return d.events + ' Pinnacle ' + mk + ' moves so far in ' + SPORT[sport] + ', ' + uu.n + ' book-moves checked. The US books never followed before kickoff in ' + pct(uu.pct_not_followed, 0) + ', had already moved in ' + pct(uu.pct_led, 0) + ', and followed in ' + pct(uu.followed / uu.n, 0) + med + '. Only ' + pct(uu.pct_followed_within_60, 0) + ' followed within an hour.' + (d.events < 50 ? ' Small sample.' : '');
  }
  function keyNote(F, line) {
    var K = F.keys; if (!K || !K.recent || line == null) return '';
    var dist = K.recent.margin, thr = 0.04, m = Math.abs(line), lo = Math.floor(m), hi = Math.ceil(m);
    if (Math.abs(m - Math.round(m)) < 1e-9) { var s = dist[String(Math.round(m))]; return s >= thr ? 'Sits on ' + Math.round(m) + ': ' + pct(s) + ' of NFL games end on exactly this margin, so it can push.' : ''; }
    var a = dist[String(lo)], b = dist[String(hi)], out = []; if (a >= thr) out.push(lo + ' (' + pct(a) + ')'); if (b >= thr) out.push(hi + ' (' + pct(b) + ')');
    return out.length ? 'A half point either way crosses ' + out.join(' or ') + ': that share of NFL games ends on that margin.' : '';
  }
  function GameTells(props) {
    var k = kit(), h = k.U.createElement, F = useFiles(), u = ui(), g = props.g, built = useBuilt(props.D, F);
    if (!g || !STORE.ts) return null;
    var parts = [], ag = F.age && F.age.games && F.age.games[g.key];
    ['sp', 'tot', 'ml'].forEach(function (m) {
      var a = ag && ag[m]; if (!a) return;
      var fmt = function (v) { return m === 'sp' ? g.home.abbr + ' ' + sgn(v) : m === 'tot' ? String(v) : pct(v) + ' ' + g.home.abbr; };
      var cols = 'minmax(0,1fr) 110px 100px minmax(0,1fr)';
      parts.push(h('div', { key: m, style: { display: 'grid', gap: 6 } },
        h('div', { style: { display: 'flex', justifyContent: 'space-between', gap: 8 } }, h(k.M, { size: 'base', weight: 'semibold' }, MK[m] + ': Pinnacle ' + fmt(a.pin)), h(k.T, { size: 'sm' }, a.pin_moved ? 'moved ' + dur(tnow() - a.pin_moved) + ' ago' : '')),
        u.table(460, [u.row(cols, ['Book', 'Now', 'Last changed', ''].map(u.th), 'head', null, true)].concat(Object.keys(a.books || {}).map(function (b) {
          var x = a.books[b], behind = !x.same && a.pin_moved && x.changed && x.changed <= a.pin_moved;
          return u.row(cols, [h(k.M, { key: 'a', size: 'sm' }, b), h(k.M, { key: 'b', size: 'sm', mono: true }, fmt(x.v)), h(k.T, { key: 'c', size: 'sm', mono: true }, x.changed ? dur(tnow() - x.changed) + ' ago' : '-'),
            h(k.oe, { key: 'd', variant: x.same ? 'success' : behind ? 'warning' : 'default' }, x.same ? 'Same as Pinnacle' : behind ? 'Behind: not changed since Pinnacle moved' : 'Differs')].map(u.td), b);
        }))), h(k.T, { size: 'xs' }, clockLine(F, g.sport, m))));
    });
    var sp = g.pin && g.pin.sp && g.sport === 'nfl' ? keyNote(F, g.pin.sp.line) : '';
    var cs = built.all.filter(function (c) { return c.gk === g.key && c.tier !== 'none'; });
    var read = cs.filter(function (c) { return c.tier === 'play'; }).length ? cs.filter(function (c) { return c.tier === 'play'; }).length + ' price(s) on this game clear every gate: ' + cs.filter(function (c) { return c.tier === 'play'; }).map(function (c) { return c.title + ' at ' + c.price.book + ' ' + am(c.price.am); }).join('; ') + '.' : cs.length ? 'Nothing clears every gate. ' + cs.length + ' price(s) looked at and held back: ' + cs.map(function (c) { return c.title + ' (' + c.reasons[0] + ')'; }).join(' ') : 'No price here beats Pinnacle by enough to look at.';
    return h('div', { style: { display: 'grid', gap: 12 } },
      h(k.je, { hint: 'the V2 read of this game' }, 'Plays on this game'), h(k.K, { padding: 16 }, h(k.T, { size: 'base' }, read)),
      h(k.je, { hint: 'from the book tape' }, 'Who is behind'),
      parts.length ? h('div', { style: { display: 'grid', gap: 14 } }, parts.concat(sp ? [h(k.T, { key: 'kn', size: 'sm' }, 'Spread: ' + sp)] : [])) : h(k.K, { padding: 16 }, h(k.T, { size: 'sm' }, 'No book history for this game yet. The tape records a book only when its number changes, from the first run after it appears.')));
  }


  /* ---------- logos, headshots, the play card and the V2 record, as HTML strings (the desktop and phone layouts both draw them) ---------- */
  var ASSETS = { cfb: null, heads: null, started: false };
  var vN = function (x) { return String(x || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]/g, ''); };
  var pKey = function (x) { return String(x || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z ]/g, '').replace(/\s+/g, ' ').trim(); };
  var pKeyNS = function (x) { return pKey(x).replace(/ (jr|sr|ii|iii|iv|v)$/, ''); };
  function loadAssets() {
    if (ASSETS.started) return; ASSETS.started = true;
    Promise.all([get(MAIN + 'scripts/sharp_money_card/cfb_logos.json'), get(MAIN + 'data/nflverse_stats.json')]).then(function (v) {
      ASSETS.cfb = v[0] || {};
      var m = {}, d = v[1] || {}; Object.keys(d).forEach(function (k) { var h = d[k] && d[k].headshot; if (h) { m[pKey(k)] = h; m[pKeyNS(k)] = h; } });
      ASSETS.heads = m; STORE.subs.forEach(function (fn) { fn(); });
    });
  }
  var NFLM = { LA: 'lar', WAS: 'wsh', JAC: 'jax' }, NBAM = { NOP: 'no', NYK: 'ny', SAS: 'sa', GSW: 'gs', WAS: 'wsh', UTA: 'utah' };
  function teamUrl(sport, t) {
    if (!t) return null; var ab = String(t.abbr || '').toUpperCase(), b = 'https://a.espncdn.com/i/teamlogos/';
    if (sport === 'nfl') return b + 'nfl/500/' + (NFLM[ab] || ab.toLowerCase()) + '.png';
    if (sport === 'nba') return b + 'nba/500/' + (NBAM[ab] || ab.toLowerCase()) + '.png';
    if (sport === 'cfb') { var id = t.espnId || (ASSETS.cfb && (ASSETS.cfb[vN(t.name)] || ASSETS.cfb[vN(String(t.name || '').replace(/\([^)]*\)/g, ''))])); return id ? b + 'ncaa/500/' + id + '.png' : null; }
    return null;
  }
  var ESC = function (x) { return String(x == null ? '' : x).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  function bubble(size, bg, label, img, cover, ring) {
    return '<span style="position:relative;display:inline-grid;place-items:center;width:' + size + 'px;height:' + size + 'px;border-radius:50%;background:' + bg + ';color:#fff;font:700 ' + Math.round(size * 0.27) + 'px/1 system-ui,sans-serif;flex:none;overflow:hidden;' +
      (ring ? 'box-shadow:0 0 0 2px ' + ring + ',0 0 20px ' + ring + ';' : 'box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.18);') + '"><span>' + ESC(label) + '</span>' +
      (img ? '<img src="' + ESC(img) + '" alt="" onerror="this.remove()" style="position:absolute;inset:0;width:100%;height:100%;object-fit:' + (cover ? 'cover' : 'contain') + ';padding:' + (cover ? 0 : '12%') + ';background:#26262a;border-radius:50%;box-sizing:border-box">' : '') + '</span>';
  }
  function teamLogo(sport, t, size, ring) { return bubble(size, (t && t.color) || '#444', (t && t.abbr) || '', teamUrl(sport, t), false, ring); }
  function headshot(name, size, ring) {
    var h = ASSETS.heads && (ASSETS.heads[pKey(name)] || ASSETS.heads[pKeyNS(name)]);
    if (h) h = h.replace('/f_auto,q_auto/', '/f_auto,q_auto,w_' + size * 2 + ',h_' + size * 2 + ',c_thumb,g_face/');
    var ini = String(name || '').split(' ').map(function (w) { return w[0]; }).join('').slice(0, 2).toUpperCase();
    return bubble(size, '#3a3a3e', ini, h, true, ring);
  }
  var ALIASN = { WSH: 'WAS', LA: 'LAR', JAC: 'JAX', LVR: 'LV', OAK: 'LV' }, an = function (t) { return ALIASN[t] || t; };
  function gameForTeam(D, team, start) {
    var gs = (D && D.games) || []; for (var i = 0; i < gs.length; i++) { var g = gs[i]; if (g.sport === 'nfl' && (!start || g.start === start) && (an(g.away.abbr) === an(team) || an(g.home.abbr) === an(team))) return g; } return null;
  }
  function lift(hex, a) {
    if (!hex || hex[0] !== '#' || hex.length !== 7) return null; var r = [1, 3, 5].map(function (i) { return parseInt(hex.slice(i, i + 2), 16); });
    return 'rgb(' + r.map(function (v) { return Math.round(v + (255 - v) * a); }).join(',') + ')';
  }
  function ledgerKey(c) {
    if (c.kind === 'prop') return ['p', c.start, c.row.pid, c.row.mkt, c.row.line, c.side].join('|');
    if (c.kind === 'exch') return ['e', c.gk, c.m, c.side, c.edgeRow.line].join('|');
    return ['b', c.gk, c.m, c.side, c.title].join('|');
  }
  var mix = function (c, pc) { return 'color-mix(in srgb,' + c + ' ' + pc + '%,transparent)'; };
  function priceBar(pal, cost, fairs) {
    var lo = Math.max(0, Math.min.apply(null, [cost].concat(fairs)) - 0.04), hi = Math.min(1, Math.max.apply(null, [cost].concat(fairs)) + 0.04), pos = function (x) { return ((x - lo) / (hi - lo) * 100).toFixed(1); };
    var good = Math.min.apply(null, fairs), dots = fairs.map(function (f) { return '<i style="position:absolute;top:-3px;left:calc(' + pos(f) + '% - 7px);width:14px;height:14px;border-radius:50%;background:' + pal.good + ';border:2px solid ' + pal.bg + ';box-sizing:border-box"></i>'; }).join('');
    return '<div style="margin-top:12px"><div style="position:relative;height:8px;border-radius:8px;background:' + pal.tile + '">' +
      (good > cost ? '<i style="position:absolute;top:0;bottom:0;left:' + pos(cost) + '%;width:' + (pos(good) - pos(cost)).toFixed(1) + '%;border-radius:8px;background:linear-gradient(90deg,' + mix(pal.good, 35) + ',' + pal.good + ')"></i>' : '') +
      '<i style="position:absolute;top:-4px;left:calc(' + pos(cost) + '% - 1.5px);width:3px;height:16px;border-radius:2px;background:' + pal.text + '"></i>' + dots + '</div>' +
      '<div style="display:flex;justify-content:space-between;gap:8px;margin-top:6px;font-size:11.5px;color:' + pal.mut + '"><span>You pay ' + pct(cost) + '</span><span>Fair ' + (fairs.length > 1 ? pct(Math.min.apply(null, fairs)) + ' to ' + pct(Math.max.apply(null, fairs)) : pct(fairs[0])) + '</span></div></div>';
  }
  /* The play card. pal: the layout's colours as CSS values (text, mut, dim, line, bg, tile, acc, good, bad, warn). */
  function cardHtml(c, F, pal, D) {
    var GT = G().GATES, g = c.game, sport = c.sport, tier = c.tier;
    var tag = tier === 'play' ? ['PLAY', pal.good] : tier === 'watch' ? ['WATCH', pal.warn] : ['PASSED', pal.dim];
    var picked = null, away = null, home = null, hero, titleCol = pal.text, ring;
    if (c.kind === 'prop') {
      var pg = gameForTeam(D, c.row.team, c.start); away = pg && pg.away; home = pg && pg.home;
      var mine = pg ? (an(pg.away.abbr) === an(c.row.team) ? pg.away : pg.home) : { abbr: c.row.team, color: '#444' };
      hero = [headshot(c.row.name, 64, mix(pal.good, 60)), teamLogo('nfl', mine, 52)];
    } else if (g) {
      away = g.away; home = g.home;
      var t = c.title.toLowerCase(), hit = function (x) { return x && ((x.short && t.indexOf(String(x.short).toLowerCase()) >= 0) || (x.abbr && new RegExp('(^|[^a-z])' + String(x.abbr).toLowerCase() + '([^a-z]|$)').test(t)) || (x.name && t.indexOf(String(x.name).toLowerCase()) >= 0)); };
      picked = hit(g.away) && !hit(g.home) ? g.away : hit(g.home) && !hit(g.away) ? g.home : null;
      if (c.kind === 'book' && c.m !== 'tot') picked = c.side === 'home' ? g.home : g.away;
      if (picked) titleCol = lift(picked.color, 0.4) || pal.text;
      hero = [teamLogo(sport, g.away, 56, picked === g.away ? mix(pal.good, 70) : null), teamLogo(sport, g.home, 56, picked === g.home ? mix(pal.good, 70) : null)];
    } else hero = ['', ''];
    var gA = away && away.color ? mix(away.color, 28) : 'transparent', gH = home && home.color ? mix(home.color, 28) : 'transparent';
    var tile = function (label, val, sub, ok, hl) {
      return '<div style="border:1px solid ' + (hl ? mix(pal.good, 55) : pal.line) + ';border-radius:14px;padding:9px 10px;min-width:0;text-align:center;background:' + (hl ? mix(pal.good, 8) : 'transparent') + '"><div style="font-size:10.5px;letter-spacing:.09em;color:' + (ok ? pal.good : pal.mut) + ';text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:' + (ok ? pal.good : pal.dim) + ';margin-right:5px;vertical-align:1px"></span>' + label + '</div><div style="font-size:19px;font-weight:700;margin-top:3px;font-variant-numeric:tabular-nums">' + val + '</div>' + (sub ? '<div style="font-size:12px;font-weight:600;color:' + (ok ? pal.good : pal.mut) + '">' + sub + '</div>' : '') + '</div>';
    };
    var tiles = [tile('You pay', am(c.price.am), c.price.book + ' · ' + pct(c.price.p), false, false)].concat(c.refs.map(function (r) { return tile(ESC(r.n) + ' fair', pct(r.p), spct(r.edge), r.edge >= GT.MIN_EDGE, false); }));
    if (c.refs.length > 1 && c.worst != null) tiles.push(tile('Worst case', spct(c.worst), 'edge', c.worst >= GT.MIN_EDGE, true));
    var chips = [], chip = function (txt, col, bg) { chips.push('<span style="display:inline-block;font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:99px;color:' + col + ';background:' + bg + ';border:1px solid ' + mix(col, 30) + ';white-space:normal">' + ESC(txt) + '</span>'); };
    var L = F.plays && F.plays.plays && F.plays.plays[ledgerKey(c)];
    if (L) { var st = L.status; chip(st === 'open' ? 'Logged · open' : st === 'won' ? 'Won ' + (L.units > 0 ? '+' : '') + L.units.toFixed(2) + 'u' : st === 'lost' ? 'Lost ' + L.units.toFixed(2) + 'u' : st === 'push' ? 'Push' : 'Void', st === 'won' ? pal.good : st === 'lost' ? pal.bad : pal.acc, mix(st === 'won' ? pal.good : st === 'lost' ? pal.bad : pal.acc, 10)); }
    if (c.rec && c.rec.w + c.rec.l) chip(c.market + ' so far ' + c.rec.w + '-' + c.rec.l + ' · ROI ' + spct(c.rec.roi), pal.mut, 'transparent');
    if (c.kind === 'book' && c.gk && F.age && F.age.games && F.age.games[c.gk]) {
      var a = F.age.games[c.gk][c.m], x = a && a.books && a.books[c.price.book]; if (x && x.changed) chip(c.price.book + ' unchanged ' + dur(tnow() - x.changed), pal.mut, 'transparent');
    }
    c.cautions.forEach(function (x) { chip(x, pal.warn, mix(pal.warn, 8)); });
    var bar = c.refs.length ? priceBar(pal, c.price.p, c.refs.map(function (r) { return r.p; })) : '';
    var sub = c.kind === 'prop' ? c.sub + (away && home ? ' · ' + away.abbr + ' @ ' + home.abbr : '') : c.sub;
    return '<div style="position:relative;border-radius:22px;overflow:hidden;padding:14px 14px 14px;color:' + pal.text + ';border:1px solid ' + pal.line + ';background:linear-gradient(115deg,' + gA + ' 0%,transparent 42%,transparent 58%,' + gH + ' 100%)">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:' + pal.mut + '"><span style="color:' + tag[1] + ';font-weight:700"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:' + tag[1] + ';margin-right:6px;vertical-align:1px"></span>' + tag[0] + '</span><span>' + SPORT[sport] + ' · ' + (c.start ? when(c.start) : 'time n/a') + '</span></div>' +
      '<div style="display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:10px;margin:12px 0 4px"><div>' + hero[0] + '</div><div style="text-align:center;min-width:0"><div style="font-size:clamp(20px,5.4vw,30px);font-weight:800;line-height:1.1;letter-spacing:-.01em;color:' + titleCol + '">' + ESC(c.title) + '</div><div style="font-size:12.5px;color:' + pal.mut + ';margin-top:4px">' + ESC(sub) + '</div></div><div>' + hero[1] + '</div></div>' +
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(' + (tiles.length > 3 ? 128 : 100) + 'px,1fr));gap:8px;margin-top:12px">' + tiles.join('') + '</div>' + bar +
      '<div style="font-size:12.5px;color:' + pal.mut + ';margin-top:10px">' + ESC(c.reasons.join(' ')) + '</div>' +
      (chips.length ? '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">' + chips.join('') + '</div>' : '') + '</div>';
  }
  /* The V2 record: count and units of every logged play, then the latest results. */
  function recordHtml(F, pal) { return recordCore(F, pal); }
  function recordCore(F, pal) {
    var PL = F.plays, rows = rowsAll(F), bfn = rows.filter(function (r) { return r.p.backfill; }).length, live = rows.filter(function (r) { return !r.p.backfill; }), ls = stat(live), s = stat(rows), cnt = function (k) { return rows.filter(function (r) { return r.p.status === k; }).length; };
    var wins = rows.filter(function (r) { return r.units > 0; }).map(function (r) { return r.units; }).sort(function (a, b) { return b - a; }).slice(0, 5), ws = wins.reduce(function (a, b) { return a + b; }, 0);
    var su = function (u) { var r = Math.round(u * 10) / 10 || 0; return (r > 0 ? '+' : r < 0 ? '-' : '') + Math.abs(r).toFixed(1) + 'u'; };
    var roi = s.n && s.units != null ? s.units / s.n : null;
    var big = function (label, val, sub, col) { return '<div style="border:1px solid ' + pal.line + ';border-radius:14px;padding:10px 12px;min-width:0"><div style="font-size:10.5px;letter-spacing:.09em;color:' + pal.mut + ';text-transform:uppercase">' + label + '</div><div style="font-size:26px;font-weight:800;margin-top:2px;font-variant-numeric:tabular-nums;color:' + (col || pal.text) + '">' + val + '</div><div style="font-size:11.5px;color:' + pal.mut + '">' + sub + '</div></div>'; };
    var started = live.length ? new Date(Math.min.apply(null, live.map(function (r) { return r.p.firstSeen; })) * 1000).toLocaleDateString('en-US', Object.assign({ month: 'short', day: 'numeric' }, CT)) : null;
    var w = s.n ? s.w + '-' + s.l + (cnt('push') ? '-' + cnt('push') : '') : '0-0';
    var tiles = [big('Record', w, s.n + ' settled' + (bfn ? ' (' + bfn + ' backfilled)' : '') + ' · ' + cnt('open') + ' open' + (cnt('void') ? ' · ' + cnt('void') + ' void' : '')),
      big('Units', s.units == null ? '+0.0u' : su(s.units), 'flat 1 unit at the price shown', s.units > 0 ? pal.good : s.units < 0 ? pal.bad : null),
      big('ROI', roi == null ? '-' : spct(roi), s.n ? 'without top ' + (wins.length || 5) + ' wins ' + su((s.units || 0) - ws) : 'after the first result'),
      big('CLV vs close', s.clv == null ? '-' : spct(s.clv), s.clvN + ' with an exchange close', s.clv > 0 ? pal.good : s.clv < 0 ? pal.bad : null)];
    var recent = rows.filter(function (r) { return r.p.status !== 'open'; }).sort(function (a, b) { return b.p.start - a.p.start; }).slice(0, 8);
    var list = recent.length ? '<details style="margin-top:10px"><summary style="cursor:pointer;font-size:12.5px;font-weight:600;color:' + pal.mut + '">Latest results · ' + recent.length + ' of ' + rows.filter(function (r) { return r.p.status !== 'open'; }).length + ' settled</summary>' + recent.map(function (r) {
      var p = r.p, f = p.first || {}, st = p.status, col = st === 'won' ? pal.good : st === 'lost' ? pal.bad : pal.mut;
      return '<div style="display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-top:1px solid ' + pal.line + '"><div style="min-width:0"><div style="font-weight:600;font-size:14px">' + ESC(f.title) + '</div><div style="font-size:12px;color:' + pal.mut + '">' + ESC((f.price || {}).book) + ' ' + am((f.price || {}).am) + ' · ' + SPORT[p.sport] + (p.clv != null ? ' · CLV ' + spct(p.clv) : '') + (p.backfill ? ' · backfilled' : '') + '</div></div><div style="text-align:right;white-space:nowrap;font-weight:700;color:' + col + '">' + (st === 'won' ? 'Won' : st === 'lost' ? 'Lost' : st === 'push' ? 'Push' : 'Void') + (p.units != null && st !== 'void' ? '<div style="font-size:12px">' + su(p.units) + '</div>' : '') + '</div></div>';
    }).join('') + '</details>' : '';
    var note = !PL || !PL.plays ? 'Not started: the log has not been published yet.' : !rows.length ? 'The log is running. A play is written the first time one clears every gate.' : rows.length + ' play' + (rows.length === 1 ? '' : 's') + ' logged since ' + started + '. Each is saved once at first sight, then graded. ' + (s.n < 100 ? s.n + ' of 100 settled plays before it means much.' : '');
    var lsu = ls.units == null ? '+0.0u' : su(ls.units);
    if (bfn) note = (live.length ? live.length + ' live play' + (live.length === 1 ? '' : 's') + ' since ' + started + ' (' + (ls.n ? ls.w + '-' + ls.l + ', ' + lsu : '0 settled') + '), plus ' : '') + bfn + ' settled plays backfilled from the ' + ESC((F.backfill || {}).date || '') + ' slate. The backfilled ones were chosen with hindsight on the exchange close, so the totals read better than live play will.';
    return '<div style="border:1px solid ' + pal.line + ';border-radius:22px;padding:14px;color:' + pal.text + '"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px"><span style="font-size:11px;letter-spacing:.09em;text-transform:uppercase;font-weight:700;color:' + pal.mut + '">V2 play record</span><span style="font-size:11.5px;color:' + pal.mut + '">' + ESC(note) + '</span></div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-top:10px">' + tiles.join('') + '</div>' + list + '</div>';
  }

  /* The data layer and the scoring, for the phone layout (sharp-money/new/), which draws its own HTML from them. */
  var core = {
    STORE: STORE, rowsAll: rowsAll, stance: stance, cardHtml: cardHtml, recordHtml: recordHtml, loadAssets: loadAssets, stat: stat, rules: rules, v2Rows: v2Rows, when: when, dur: dur, clockLine: clockLine, keyNote: keyNote,
    ensure: function () { loadAssets(); if (!STORE.ts || Date.now() - STORE.ts > 100000) fetchAll(); return STORE.ts > 0; },
    subscribe: function (fn) { STORE.subs.add(fn); return function () { STORE.subs.delete(fn); }; }
  };
  window.VaultV2 = { Plays: Plays, Signals: Signals, Record: Record, GameTells: GameTells, stat: stat, rules: rules, core: core };
})();
