/* Following: follow specific proven Polymarket wallets and see every bet they have open, for Sharp Money.
   One file for both layouts (sharp-money/index.html and sharp-money/new/index.html), so the two stay the same page.
   Data: wallets.json on the pm-cards-live branch, built every 10 minutes by scripts/build_side_cards.py --wallets-out
   (docs/side-cards.md, "Wallets file"). Until that file exists the page says so.

   Sharp money is context only (CLAUDE.md). This page shows who holds what. It never shows a suggested size and it never feeds
   Top Reads, SM_GATE or an agree total. Every number is a stored field: money is shares times the market price at the last scan,
   and no entry price is stored, so none is shown.

   Follows are kept in this browser (localStorage `vault-sharps-following`: {"sport|wallet": followed-at seconds}). "Since you
   followed" counts a wallet's settled games dated after its follow time, from the 20 most recent the file carries. */
(function(){
'use strict';
var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
var DEV = LOCAL && (location.search.match(/[?&]wallets=([^&]+)/) || [])[1];      /* localhost only: ?wallets=/path/to/wallets.json */
var SRC = DEV ? decodeURIComponent(DEV) : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-cards-live/wallets.json';
var KEY = 'vault-sharps-following', SEASONED = 20, PRESS = 1.5, PAGE = 12;
var GROUPS = {ml: 'Moneyline', spread: 'Spread', total: 'Total'};
var SPORTS = [['all', 'All'], ['nfl', 'NFL'], ['cfb', 'CFB'], ['nba', 'NBA'], ['cbb', 'CBB']];

var CSS = [
'.vfw{--c-card:#222222;--c-line:#2f2f2f;--c-line2:#3a3a3a;--c-ink:#d8d8d8;--c-mut:#999999;--c-dim:#6a6a6a;--c-good:#4ade80;--c-bad:#f87171;--c-warn:#fbbf24;--c-gold:#e8c66a;',
'--c-good-bg:rgba(74,222,128,.10);--c-warn-bg:rgba(251,191,36,.10);--c-box:#2a2a2a;--c-sel:rgba(216,216,216,.08);--c-r:16px;--c-pad:20px;',
"--c-sans:var(--halaska-sans,'Geist'),-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--c-num:var(--halaska-mono,'Geist Mono'),'SF Mono',monospace;--c-num-ls:-.02em;",
'--vseg-bg:#2a2a2a;--vseg-border:transparent;--vseg-ink:#999999;--vseg-on-ink:#1a1a1a;--vseg-pill:#d8d8d8;',
'--fw-rail:cubic-bezier(0.65,0,0.35,1);--fw-spring:cubic-bezier(0.34,1.56,0.64,1);color:var(--c-ink);font-family:var(--c-sans)}',
'html[data-shade=charcoal] .vfw{--c-card:#1b1b1b;--c-box:#242424;--c-line:#2a2a2a;--vseg-bg:#242424}',
'html[data-theme=light] .vfw{--c-card:#ffffff;--c-line:#eeeeee;--c-line2:#dcdcdc;--c-ink:#2b2b2b;--c-mut:#777777;--c-dim:#a0a0a0;--c-good:#16a34a;--c-bad:#dc2626;--c-warn:#d97706;--c-gold:#a8780a;',
'--c-good-bg:#f0fdf4;--c-warn-bg:#fffbeb;--c-box:#f5f5f5;--c-sel:rgba(0,0,0,.05);--vseg-bg:#f0f0f0;--vseg-ink:#888888;--vseg-on-ink:#ffffff;--vseg-pill:#3d3d3d}',
'.vfw.vfw-new{--c-card:#1c1c1e;--c-line:rgba(255,255,255,.09);--c-line2:rgba(255,255,255,.16);--c-ink:#fff;--c-mut:#98989f;--c-dim:#636366;--c-good:#32d583;--c-bad:#ff6b6b;--c-warn:#f5b84a;--c-gold:#f0cf7a;',
'--c-good-bg:rgba(50,213,131,.12);--c-warn-bg:rgba(245,184,74,.12);--c-box:#2c2c2e;--c-sel:rgba(255,255,255,.08);--c-r:24px;--c-pad:16px;--c-bw:0px;',
'--c-sans:-apple-system,"SF Pro Text",Geist,system-ui,sans-serif;--c-num:"Barlow Condensed","SF Pro Rounded",Geist,sans-serif;--c-num-ls:.01em;',
'--vseg-bg:#2c2c2e;--vseg-ink:#98989f;--vseg-on-ink:#000;--vseg-pill:#fff;margin:0 16px 12px}',
'.vfw *{box-sizing:border-box}.vfw button{font-family:inherit}',
'.vfw dl,.vfw dt,.vfw dd,.vfw p,.vfw h2,.vfw h4,.vfw time,.vfw li{font-family:inherit;letter-spacing:normal;line-height:1.35;text-transform:none}.vfw dt,.vfw dd{font-size:12.5px;font-weight:400}.vfw b{font-family:inherit}',
'.vfw .fw-num{font-family:var(--c-num);letter-spacing:var(--c-num-ls);font-variant-numeric:tabular-nums}',
'.vfw .fw-up{color:var(--c-good)}.vfw .fw-dn{color:var(--c-bad)}',
/* press (vault-ds.css 19.1) and the segmented control with its travelling pill (19.2, 20), inlined: these shells do not link vault-ds.css */
'.vfw .fw-press{transition:transform 500ms var(--fw-spring)}.vfw .fw-press:active{transform:scale(var(--fw-ps,.94));transition:transform 80ms ease-out}',
'.vfw .fw-seg{position:relative;display:inline-flex;align-items:center;flex-shrink:0;gap:2px;padding:3px;max-width:100%;background:var(--vseg-bg);border:1px solid var(--vseg-border);border-radius:9px;overflow-x:auto;scrollbar-width:none}',
'.vfw .fw-seg::-webkit-scrollbar{display:none}',
'.vfw .fw-seg>button{position:relative;z-index:1;display:inline-flex;align-items:center;justify-content:center;min-height:32px;padding:0 13px;border:0;background:transparent;border-radius:6px;color:var(--vseg-ink);font-size:12.5px;font-weight:600;letter-spacing:-.01em;white-space:nowrap;cursor:pointer;transition:color .12s ease}',
'.vfw .fw-seg>button.on{color:var(--vseg-on-ink)}',
'.vfw .fw-seg .fw-pill{position:absolute;top:3px;bottom:3px;left:0;width:0;opacity:0;border-radius:6px;background:var(--vseg-pill);transition:left 400ms var(--fw-rail),width 400ms var(--fw-rail)}',
'.vfw .fw-seg.fw-noanim .fw-pill{transition:none}',
'.vfw .fw-bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:10px 0 6px}',
'.vfw .fw-upd{font-size:12.5px;color:var(--c-dim)}',
'.vfw .fw-sum{display:flex;gap:22px;flex-wrap:wrap;align-items:baseline;margin:14px 0 12px;font-size:13px;color:var(--c-mut)}',
'.vfw .fw-sum b{font-size:22px;font-weight:600;color:var(--c-ink);margin-right:6px}',
'.vfw .fw-link{border:0;background:none;color:var(--c-mut);font-size:12px;text-decoration:underline;text-underline-offset:3px;cursor:pointer;padding:6px 0}',
'.vfw .fw-sum .fw-link{margin-left:auto}',
'.vfw .fw-h{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:28px 0 12px}',
'.vfw .fw-h h2{margin:0;font-size:15px;font-weight:600;color:var(--c-ink)}.vfw .fw-h p{margin:0;font-size:12px;color:var(--c-mut)}.vfw .fw-h .sp{flex:1}',
'.vfw .fw-card{background:var(--c-card);border:var(--c-bw,1px) solid var(--c-line);border-radius:var(--c-r);padding:var(--c-pad)}',
'.vfw .fw-feed{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}',
'.vfw .fw-g{padding:16px 18px;min-width:0}.vfw .fw-dir{min-width:0;overflow:hidden}',
'.vfw .fw-gh{display:flex;align-items:center;gap:10px;margin-bottom:6px}.vfw .fw-gh b{font-size:14.5px;font-weight:600;white-space:nowrap}.vfw .fw-gh time{margin-left:auto;font-size:12px;color:var(--c-mut);white-space:nowrap}',
'.vfw .fw-tag{font-family:var(--c-num);font-style:normal;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--c-mut);background:var(--c-box);border-radius:5px;padding:3px 6px}',
'.vfw .fw-badge{font-size:11px;font-weight:600;border-radius:999px;padding:3px 9px}.vfw .fw-badge.agree{background:var(--c-good-bg);color:var(--c-good)}.vfw .fw-badge.split{background:var(--c-warn-bg);color:var(--c-warn)}',
'.vfw .fw-side{padding:11px 0 2px;border-top:1px solid var(--c-line);margin-top:8px}',
'.vfw .fw-side-h{display:flex;align-items:baseline;gap:8px;font-size:13px}.vfw .fw-side-h span{color:var(--c-mut);font-size:11.5px}.vfw .fw-side-h b{font-weight:600}',
'.vfw .fw-bet{display:flex;align-items:center;gap:10px;padding:7px 0;font-size:12.5px}',
'.vfw .fw-bet .fw-nm{font-weight:500;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.vfw .fw-bet .fw-rec{color:var(--c-mut);font-size:11.5px;white-space:nowrap}.vfw .fw-bet .fw-usd{margin-left:auto;font-size:13px;white-space:nowrap}',
'.vfw .fw-x{font-style:normal;font-size:11.5px;border-radius:5px;padding:2px 6px;background:var(--c-box);color:var(--c-mut);white-space:nowrap}.vfw .fw-x.fw-hot{background:var(--c-good-bg);color:var(--c-good)}',
'.vfw .fw-empty{padding:26px var(--c-pad);font-size:13px;color:var(--c-mut);text-align:center}.vfw .fw-empty b{display:block;color:var(--c-ink);font-size:14px;margin-bottom:4px}',
'.vfw .fw-since{display:flex;flex-wrap:wrap;gap:8px 26px;align-items:baseline;font-size:13px}.vfw .fw-since>b{font-size:22px;font-weight:600}.vfw .fw-since span{color:var(--c-mut)}',
'.vfw .fw-since-l{margin:12px 0 0;padding:0;list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:6px 22px;font-size:12.5px}',
'.vfw .fw-since-l li{display:flex;justify-content:space-between;gap:10px;border-top:1px solid var(--c-line);padding-top:6px}.vfw .fw-since-l i{font-style:normal;color:var(--c-mut);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
'.vfw .fw-tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap}',
'.vfw .fw-chk{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--c-mut);cursor:pointer;min-height:36px}.vfw .fw-chk input{accent-color:var(--c-ink)}',
'.vfw .fw-dir{padding:4px 0}',
'.vfw .fw-cols,.vfw .fw-row{display:grid;grid-template-columns:40px minmax(150px,1.6fr) 54px 84px 76px 60px 96px 96px 70px;align-items:center;gap:8px;padding:0 var(--c-pad)}',
'.vfw .fw-cols{font-size:11px;color:var(--c-dim);padding-top:12px;padding-bottom:8px}',
'.vfw .fw-cols span:nth-child(n+4),.vfw .fw-row>span:nth-child(n+4){text-align:right}',
'.vfw .fw-row{--fw-ps:.99;min-height:50px;border-top:1px solid var(--c-line);font-size:13px;cursor:pointer;color:inherit}.vfw .fw-row:hover{background:var(--c-sel)}',
'.vfw .fw-row .fw-nm{font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.vfw .fw-row .fw-thin{font-style:normal;font-size:10.5px;color:var(--c-warn);margin-left:7px;font-weight:500}',
'.vfw .fw-star{--fw-ps:.88;width:34px;height:34px;border-radius:50%;border:0;background:transparent;color:var(--c-dim);font-size:17px;cursor:pointer;line-height:1}.vfw .fw-star.on{color:var(--c-gold)}',
'.vfw .fw-open{font-style:normal;display:inline-block;min-width:22px;text-align:center;border-radius:999px;padding:2px 7px;font-size:11.5px;background:var(--c-box);color:var(--c-mut)}.vfw .fw-open.fw-has{background:var(--c-good-bg);color:var(--c-good)}',
'.vfw .fw-prof{border-top:1px solid var(--c-line);padding:16px var(--c-pad) 20px;background:var(--c-box);display:grid;grid-template-columns:repeat(3,1fr);gap:18px}',
'.vfw .fw-prof h4{margin:0 0 8px;font-size:11px;font-weight:500;color:var(--c-mut)}',
'.vfw .fw-prof dl{margin:0;display:grid;grid-template-columns:1fr auto auto;gap:6px 14px;font-size:12.5px}.vfw .fw-prof dd{margin:0;text-align:right}.vfw .fw-prof .fw-none{color:var(--c-dim)}',
'.vfw .fw-pn{grid-column:1/-1;margin:0;font-size:11.5px;color:var(--c-mut)}',
'.vfw .fw-ob{grid-column:1/-1;padding-bottom:14px;border-bottom:1px solid var(--c-line2)}.vfw .fw-ob h4{color:var(--c-ink);font-size:12.5px;font-weight:600}',
'.vfw .fw-obh,.vfw .fw-obr{display:grid;grid-template-columns:minmax(150px,1.3fr) minmax(170px,1.5fr) 80px 80px 96px 130px;gap:10px;align-items:center}',
'.vfw .fw-obh{font-size:11px;color:var(--c-dim);padding-bottom:4px}.vfw .fw-obh span:nth-child(n+3),.vfw .fw-obr>span:nth-child(n+3){text-align:right}',
'.vfw .fw-obr{min-height:40px;border-top:1px solid var(--c-line);font-size:12.5px}.vfw .fw-obr i{font-style:normal;color:var(--c-mut);font-size:11.5px}',
'.vfw .fw-obr .gm b{font-weight:500;margin-right:8px}.vfw .fw-obr .bt b{font-weight:500}.vfw .fw-obr .sn{color:var(--c-mut);font-size:11.5px}',
'.vfw .fw-two{font-style:normal;font-size:10.5px;color:var(--c-warn)}',
'.vfw .fw-more{display:block;margin:10px auto 6px}',
'.vfw .fw-note{margin:20px 0 0;font-size:11.5px;line-height:1.55;color:var(--c-dim);max-width:90ch}.vfw .fw-note b{color:var(--c-mut);font-weight:600}',
'.vfw .fw-row>.c-meta{display:none}',
'@media (max-width:767px){',
'.vfw .fw-sum{gap:14px;margin:10px 0;font-size:12px}.vfw .fw-sum b{font-size:24px}',
'.vfw .fw-feed{grid-template-columns:minmax(0,1fr);gap:10px}.vfw .fw-h{margin-top:24px}.vfw .fw-h p{flex-basis:100%;order:3}',
'.vfw .fw-seg>button{min-height:36px}',
'.vfw .fw-cols{display:none}',
'.vfw .fw-row{grid-template-columns:40px 1fr auto auto;grid-template-areas:"s n roi o" "s m roi o";row-gap:2px;padding:9px 12px;min-height:58px}',
'.vfw .fw-row>span{display:none}.vfw .fw-row>.c-star{display:block;grid-area:s}.vfw .fw-row>.c-name{display:block;grid-area:n}',
'.vfw .fw-row>.c-roi{display:block;grid-area:roi;font-size:17px}.vfw .fw-row>.c-open{display:block;grid-area:o}',
'.vfw .fw-row>.c-meta{display:block;grid-area:m;font-size:11.5px;color:var(--c-mut);text-align:left}',
'.vfw .fw-prof{grid-template-columns:1fr;padding:14px 16px 18px}.vfw .fw-bet .fw-usd{font-size:16px}',
'.vfw .fw-obh{display:none}',
'.vfw .fw-obr{grid-template-columns:1fr auto auto;grid-template-areas:"gm gm st" "bt bt sz" "sn sn px";gap:3px 10px;padding:10px 0}',
'.vfw .fw-obr .gm{grid-area:gm}.vfw .fw-obr .bt{grid-area:bt;font-size:14px}.vfw .fw-obr .st{grid-area:st;font-size:17px}.vfw .fw-obr .sz{grid-area:sz}',
'.vfw .fw-obr .px{grid-area:px;color:var(--c-mut);font-size:13px}.vfw .fw-obr .sn{grid-area:sn;text-align:left!important}',
'.vfw .fw-obr .px::before{content:"now "}.vfw .fw-obr .sn::before{content:"held since "}',
'}',
'@media (prefers-reduced-motion:reduce){.vfw .fw-press,.vfw .fw-seg .fw-pill{transition:none}}'
].join('\n');

function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function usd(v){ return v == null ? '' : '$' + (v >= 10000 ? Math.round(v / 1000) + 'K' : v >= 1000 ? (v / 1000).toFixed(1).replace(/\.0$/, '') + 'K' : Math.round(v)); }
function pct(v){ return v == null ? '' : (v > 0 ? '+' : '') + (v * 100).toFixed(1) + '%'; }
function cls(v){ return v > 0 ? 'fw-up' : v < 0 ? 'fw-dn' : ''; }
function cents(px){ return px == null ? '' : Math.round(px * 100) + '¢'; }
function lineTxt(g, line){ return line == null ? '' : g === 'total' ? ' ' + line : ' ' + (line > 0 ? '+' : '') + line; }
/* every time on the page is Central */
function ct(t, o){ return t ? new Date(t * 1000).toLocaleString('en-US', Object.assign({timeZone: 'America/Chicago'}, o)) : ''; }
function gameWhen(t){ return ct(t, {weekday: 'short', hour: 'numeric', minute: '2-digit'}) + ' CT'; }
function shortName(w, n){ return !n || /^0x[0-9a-fA-F]{20,}/.test(n) ? w.slice(0, 6) + '…' + w.slice(-4) : n.slice(0, 22); }
function teams(ev){ var m = /^[a-z]+-([a-z0-9]+)-([a-z0-9]+)-\d{4}/.exec(ev || ''); return m ? m[1].toUpperCase() + ' at ' + m[2].toUpperCase() : ev; }   /* slug: away, then home */

/* ---------- data ---------- */
var STORE = {d: null, state: 'loading', busy: false, hosts: [], timer: null};
var W = [], BOOK = {}, GAMES = [], OPEN = {};
function index(d){
  W = []; BOOK = {}; OPEN = {}; var gm = {};
  Object.keys(d.sports || {}).forEach(function(sport){ var ws = d.sports[sport];
    Object.keys(ws).forEach(function(w){ var e = ws[w], dv = e.dive || {}, k = sport + '|' + w;
      var x = {k: k, w: w, sport: sport, name: shortName(w, e.name), wl: [e.w_, e.l_], roi: e.roi, n: e.n, usual: e.usual, pnl: e.pnl,
        clv: e.clv || {}, lane: dv.lane || {}, fav: dv.fav, dog: dv.dog, size: dv.size || {}, legs: e.legs || [], pos: e.positions || []};
      W.push(x); BOOK[k] = x; if (x.pos.length) OPEN[k] = x.pos.length;
      x.pos.forEach(function(p){ var id = p.ev + '@' + p.gst;
        (gm[id] = gm[id] || {id: id, sport: sport, ev: p.ev, gst: p.gst, pos: []}).pos.push({k: k, p: p}); }); }); });
  GAMES = Object.keys(gm).map(function(i){ return gm[i]; }).sort(function(a, b){ return a.gst - b.gst; });
}
function load(){
  if (STORE.busy) return; STORE.busy = true;
  fetch(SRC + '?t=' + Math.floor(Date.now() / 120000), {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; })
    .then(function(j){
      STORE.busy = false;
      var changed = !STORE.d || !j || j.built !== STORE.d.built || STORE.state === 'loading';
      if (j && j.sports){ STORE.d = j; if (changed) index(j); }
      STORE.state = STORE.d ? 'ok' : 'none';
      STORE.hosts = STORE.hosts.filter(function(h){ return document.contains(h.el); });
      if (changed) STORE.hosts.forEach(function(h){ h.render(); });
    });
}
var FOLLOWS = {};
try { FOLLOWS = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { FOLLOWS = {}; }
function save(){ try { localStorage.setItem(KEY, JSON.stringify(FOLLOWS)); } catch (e) {} }

/* ---------- render ---------- */
function seg(id, opts, cur){ return '<div class="fw-seg" data-seg="' + id + '"><i class="fw-pill"></i>' + opts.map(function(o){ return '<button type="button" class="' + (o[0] === cur ? 'on' : '') + '" data-v="' + o[0] + '">' + o[1] + '</button>'; }).join('') + '</div>'; }
function xUsual(p){ return '<i class="fw-x fw-num' + (p.press >= PRESS ? ' fw-hot' : '') + '">' + (p.press != null ? p.press.toFixed(1) + 'x usual' : 'no usual') + '</i>'; }

function feed(S){
  var out = [], bets = 0, agree = 0;
  GAMES.forEach(function(g){ if (S.sport !== 'all' && g.sport !== S.sport) return;
    var mine = g.pos.filter(function(x){ return FOLLOWS[x.k]; }); if (!mine.length) return;
    var by = {}; mine.forEach(function(x){ var b = by[x.p.g] = by[x.p.g] || {}; (b[x.p.side] = b[x.p.side] || []).push(x); });   /* a side groups every rung of it */
    var ag = false, sp = false;
    Object.keys(by).forEach(function(k){ var sides = Object.keys(by[k]); if (sides.length > 1) sp = true;
      sides.forEach(function(s){ var who = {}; by[k][s].forEach(function(x){ who[x.k] = 1; }); if (Object.keys(who).length > 1) ag = true; }); });
    bets += mine.length; if (ag) agree++;
    out.push('<article class="fw-card fw-g"><div class="fw-gh"><span class="fw-tag">' + g.sport + '</span><b>' + esc(teams(g.ev)) + '</b>' +
      (sp ? '<span class="fw-badge split">Split</span>' : ag ? '<span class="fw-badge agree">Agree</span>' : '') + '<time>' + gameWhen(g.gst) + '</time></div>' +
      ['ml', 'spread', 'total'].filter(function(k){ return by[k]; }).map(function(k){ return Object.keys(by[k]).map(function(side){
        return '<div class="fw-side"><div class="fw-side-h"><span>' + GROUPS[k] + '</span><b>' + esc(side) + '</b></div>' +
          by[k][side].sort(function(a, b){ return b.p.usd - a.p.usd; }).map(function(x){ var w = BOOK[x.k], p = x.p;
            return '<div class="fw-bet"><span class="fw-nm">' + esc(w.name) + '</span><span class="fw-rec fw-num">' + w.wl[0] + '-' + w.wl[1] + '</span>' +
              (p.line != null ? '<span class="fw-rec fw-num">' + lineTxt(p.g, p.line).trim() + '</span>' : '') +
              '<span class="fw-usd fw-num">' + usd(p.usd) + '</span>' + xUsual(p) + '</div>'; }).join('') + '</div>'; }).join(''); }).join('') + '</article>'); });
  return {html: out.join(''), bets: bets, agree: agree};
}
/* results since each follow: settled games dated after the follow time, from the wallet's 20 most recent */
function since(S){
  var w = 0, l = 0, rows = [], capped = false;
  Object.keys(FOLLOWS).forEach(function(k){ var b = BOOK[k]; if (!b || (S.sport !== 'all' && b.sport !== S.sport)) return;
    var a = 0, c = 0; b.legs.forEach(function(x){ if (x[0] >= FOLLOWS[k]){ if (x[1] === 'win') a++; else if (x[1] === 'loss') c++; } });
    if (b.legs.length >= 20 && b.legs[b.legs.length - 1][0] >= FOLLOWS[k]) capped = true;
    w += a; l += c; if (a + c) rows.push('<li><i>' + esc(b.name) + '</i><span class="fw-num">' + a + '-' + c + '</span></li>'); });
  if (!(w + l)) return '<div class="fw-card fw-empty">No games have settled since you followed. Results show up here after the ledger\'s nightly run.</div>';
  return '<div class="fw-card"><div class="fw-since"><b class="fw-num">' + w + '-' + l + '</b><span>settled games by the wallets you follow, since you followed each one</span></div>' +
    '<ul class="fw-since-l">' + rows.join('') + '</ul>' + (capped ? '<p class="fw-pn" style="margin-top:10px">A wallet shows its 20 most recent games at most, so a long follow can undercount.</p>' : '') + '</div>';
}
function rows(S){
  var ws = W.filter(function(w){ return (S.sport === 'all' || w.sport === S.sport) && (!S.seasoned || w.n >= SEASONED); });
  var o = function(w){ return OPEN[w.k] || 0; }, f = function(w){ return FOLLOWS[w.k] ? 1 : 0; };
  var beat = function(w){ return w.clv.n ? w.clv.beat / w.clv.n : -1; };
  var by = {open: function(a, b){ return f(b) - f(a) || o(b) - o(a) || b.n - a.n; }, roi: function(a, b){ return b.roi - a.roi; },
    n: function(a, b){ return b.n - a.n; }, clv: function(a, b){ return beat(b) - beat(a); }};
  return ws.sort(by[S.sort]);
}
function split3(title, items){
  return '<div><h4>' + title + '</h4><dl>' + items.map(function(i){ var v = i[1];
    return '<dt>' + i[0] + '</dt>' + (v ? '<dd class="fw-num">' + v[0] + '-' + v[1] + '</dd><dd class="fw-num ' + cls(v[2]) + '">' + pct(v[2]) + '</dd>' : '<dd class="fw-none">no bets</dd><dd></dd>'); }).join('') + '</dl></div>';
}
function openBets(w){
  if (!w.pos.length) return '<div class="fw-ob"><h4>Open bets</h4><p class="fw-pn">Nothing open right now.</p></div>';
  var tot = w.pos.reduce(function(t, p){ return t + p.usd; }, 0);
  return '<div class="fw-ob"><h4>Open bets · ' + w.pos.length + ' · ' + usd(tot) + ' at the current price</h4>' +
    '<div class="fw-obh"><span>Game</span><span>Bet</span><span>Price now</span><span>Stake</span><span>Size</span><span>Held since</span></div>' +
    w.pos.map(function(p){
      return '<div class="fw-obr"><span class="gm"><b>' + esc(teams(p.ev)) + '</b><i>' + gameWhen(p.gst) + '</i></span>' +
        '<span class="bt"><i>' + GROUPS[p.g] + '</i> ' + esc(p.side) + '<b class="fw-num">' + lineTxt(p.g, p.line) + '</b>' + (p.two_way ? ' <em class="fw-two">both sides</em>' : '') + '</span>' +
        '<span class="fw-num px">' + cents(p.px) + '</span><span class="fw-num st">' + usd(p.usd) + '</span><span class="sz">' + xUsual(p) + '</span>' +
        '<span class="fw-num sn">' + ct(p.since, {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}) + '</span></div>'; }).join('') + '</div>';
}
function profile(w){
  return '<div class="fw-prof">' + openBets(w) +
    split3('By market', [['Moneyline', w.lane.ml], ['Spread', w.lane.spread], ['Total', w.lane.total]]) +
    split3('Favorite or underdog', [['Favorites', w.fav], ['Underdogs', w.dog]]) +
    split3('By bet size', [['Under usual stake', w.size.small], ['Usual stake', w.size.usual], ['1.5x or more', w.size.big]]) +
    '<p class="fw-pn">Record and dollar ROI in ' + w.sport.toUpperCase() + ' as of the last ledger run. Lifetime profit ' + usd(Math.abs(w.pnl)).replace('$', w.pnl < 0 ? '-$' : '$') + '.' +
    (w.n < SEASONED ? ' <b class="fw-dn">Only ' + w.n + ' graded bets: treat this record as thin.</b>' : '') + '</p></div>';
}
function dir(S){
  var all = rows(S), ws = all.slice(0, S.shown);
  var head = '<div class="fw-cols"><span></span><span>Wallet</span><span>Sport</span><span>Record</span><span>ROI</span><span>Bets</span><span>Usual stake</span><span>Beat the close</span><span>Open now</span></div>';
  var body = ws.map(function(w){ var on = !!FOLLOWS[w.k], n = OPEN[w.k] || 0, beat = w.clv.n ? Math.round(w.clv.beat / w.clv.n * 100) + '%' : '';
    return '<div class="fw-row fw-press" role="button" tabindex="0" data-k="' + w.k + '" aria-expanded="' + (S.open === w.k) + '">' +
      '<span class="c-star"><button type="button" class="fw-star fw-press' + (on ? ' on' : '') + '" data-star="' + w.k + '" aria-pressed="' + on + '" aria-label="' + (on ? 'Unfollow ' : 'Follow ') + esc(w.name) + '">' + (on ? '★' : '☆') + '</button></span>' +
      '<span class="c-name fw-nm">' + esc(w.name) + (w.n < SEASONED ? '<i class="fw-thin">thin</i>' : '') + '</span>' +
      '<span><i class="fw-tag">' + w.sport + '</i></span><span class="fw-num">' + w.wl[0] + '-' + w.wl[1] + '</span>' +
      '<span class="c-roi fw-num ' + cls(w.roi) + '">' + pct(w.roi) + '</span><span class="fw-num">' + w.n + '</span><span class="fw-num">' + usd(w.usual) + '</span><span class="fw-num">' + beat + '</span>' +
      '<span class="c-open"><i class="fw-open fw-num' + (n ? ' fw-has' : '') + '">' + n + '</i></span>' +
      '<span class="c-meta fw-num">' + w.sport.toUpperCase() + ' · ' + w.wl[0] + '-' + w.wl[1] + ' · ' + w.n + ' bets · ' + usd(w.usual) + ' usual</span></div>' +
      (S.open === w.k ? profile(w) : ''); }).join('');
  return {n: all.length, html: head + (body || '<div class="fw-empty"><b>No proven wallets here</b>Try another sport or turn off the 20+ bets filter.</div>') +
    (all.length > S.shown ? '<button type="button" class="fw-link fw-more" data-more>Show ' + Math.min(PAGE * 2, all.length - S.shown) + ' more of ' + all.length + '</button>' : '')};
}

/* travelling pill: a re-rendered strip is seeded at its last position so it still animates (CLAUDE.md motion trap 0b); parked at
   opacity 0 until the strip has a width (trap 1); a forced reflow, never rAF (trap 2) */
function rails(el, S){
  [].forEach.call(el.querySelectorAll('.fw-seg'), function(strip){
    var on = strip.querySelector('button.on'), pill = strip.querySelector('.fw-pill'); if (!on || !pill || !strip.offsetWidth) return;
    var id = strip.dataset.seg, was = S.geom[id], to = {l: on.offsetLeft, w: on.offsetWidth};
    strip.classList.add('fw-noanim'); pill.style.left = (was || to).l + 'px'; pill.style.width = (was || to).w + 'px'; pill.style.opacity = '1';
    void pill.offsetWidth; strip.classList.remove('fw-noanim');
    pill.style.left = to.l + 'px'; pill.style.width = to.w + 'px'; S.geom[id] = to; });
}
function draw(el){
  var S = el._fw, o = S.o;
  if (STORE.state === 'loading'){ el.innerHTML = '<div class="fw-card fw-empty">Loading the wallets…</div>'; return; }
  if (STORE.state === 'none'){ el.innerHTML = '<div class="fw-card fw-empty"><b>The wallet file is not published yet</b>It appears after the next card build. Nothing is wrong with your follows.</div>'; return; }
  if (o.sport != null) S.sport = !o.sport || /^all$/i.test(o.sport) ? 'all' : String(o.sport).toLowerCase();
  var F = feed(S), D = dir(S), nf = Object.keys(FOLLOWS).filter(function(k){ return BOOK[k] && (S.sport === 'all' || k.split('|')[0] === S.sport); }).length;
  var y = window.scrollY;
  el.innerHTML =
    '<div class="fw-bar">' + (o.sport == null ? seg('sport', SPORTS, S.sport) : '') +
      '<span class="fw-upd">Updated ' + ct(STORE.d.built, {hour: 'numeric', minute: '2-digit'}) + ' CT · context only, no suggested size</span></div>' +
    '<div class="fw-sum"><span><b class="fw-num">' + nf + '</b>following</span><span><b class="fw-num">' + F.bets + '</b>open ' + (F.bets === 1 ? 'bet' : 'bets') + '</span>' +
      '<span><b class="fw-num">' + F.agree + '</b>' + (F.agree === 1 ? 'game' : 'games') + ' where two agree</span></div>' +
    (F.html ? '<div class="fw-feed">' + F.html + '</div>' :
      '<div class="fw-card fw-empty"><b>' + (nf ? 'No open bets from your wallets right now' : 'Follow a wallet to start your feed') + '</b>' +
      (nf ? 'Their next bets land here as soon as a scan picks them up.' : 'Tap a star in the list below. Their open bets show up here.') + '</div>') +
    (nf ? '<div class="fw-h"><h2>Since you followed</h2><p>Counted forward from the day you follow each wallet. Nothing is backfilled.</p></div>' + since(S) : '') +
    '<div class="fw-h"><h2>Proven wallets</h2><p>' + D.n + ' proven ' + (D.n === 1 ? 'wallet' : 'wallets') + '</p><span class="sp"></span><div class="fw-tools">' +
      '<label class="fw-chk"><input type="checkbox" data-seas' + (S.seasoned ? ' checked' : '') + '>20+ bets only</label>' +
      seg('sort', [['open', 'Open now'], ['roi', 'ROI'], ['n', 'Bets'], ['clv', 'Beat the close']], S.sort) + '</div></div>' +
    '<div class="fw-card fw-dir" style="padding-left:0;padding-right:0">' + D.html + '</div>' +
    '<p class="fw-note"><b>How to read this.</b> Proven means 6 or more graded bets, a 55% or better win rate and a dollar ROI above 3% in that sport. "Thin" marks a record under 20 bets. ' +
      'Stake is what the position is worth at the last scan, and "x usual" compares it with the wallet\'s usual stake. Price is the market\'s price now, not what the wallet paid: no entry price is stored. ' +
      '"Held since" is the first scan that saw the position. Follows are saved in this browser only. This page shows who holds what and never suggests a size.</p>';
  rails(el, S); window.scrollTo(0, y);
}
function css(){ if (document.getElementById('vfw-css')) return; var s = document.createElement('style'); s.id = 'vfw-css'; s.textContent = CSS; document.head.appendChild(s); }
function mountPage(el, o){
  o = o || {}; css();
  el.className = 'vfw' + (o.skin === 'new' ? ' vfw-new' : '');
  if (!el._fw){
    el._fw = {o: o, sport: 'all', sort: 'open', seasoned: false, open: null, shown: PAGE, geom: {}};
    el.addEventListener('click', function(e){
      var S = el._fw, t = e.target, b;
      if ((b = t.closest('[data-star]'))){ var k = b.dataset.star; if (FOLLOWS[k]) delete FOLLOWS[k]; else FOLLOWS[k] = Math.floor(Date.now() / 1000); save(); draw(el); return; }
      if ((b = t.closest('.fw-seg>button'))){ var id = b.parentNode.dataset.seg; S[id] = b.dataset.v; if (id !== 'sort') S.open = null; S.shown = PAGE; draw(el); return; }
      if (t.closest('[data-more]')){ S.shown += PAGE * 2; draw(el); return; }
      if ((b = t.closest('.fw-row'))){ S.open = S.open === b.dataset.k ? null : b.dataset.k; draw(el); }
    });
    el.addEventListener('change', function(e){ if (e.target.matches('[data-seas]')){ el._fw.seasoned = e.target.checked; el._fw.shown = PAGE; draw(el); } });
    el.addEventListener('keydown', function(e){ var r = e.target.closest('.fw-row'); if (r && e.target === r && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); r.click(); } });
  }
  el._fw.o = o;
  STORE.hosts = STORE.hosts.filter(function(h){ return h.el !== el && document.contains(h.el); });
  STORE.hosts.push({el: el, render: function(){ draw(el); }});
  if (!STORE.timer) STORE.timer = setInterval(function(){ if (STORE.hosts.some(function(h){ return document.contains(h.el); })) load(); }, 120000);
  if (STORE.state === 'loading') load();
  draw(el);
}
function wrap(fn, keys){
  return function(props){
    var U = window.__smKit().U, ref = U.useRef(null);
    U.useEffect(function(){ if (ref.current) fn(ref.current, props); }, keys.map(function(k){ return props[k]; }));
    return U.createElement('div', {ref: ref});
  };
}
window.VaultFollowing = {
  mountPage: mountPage,
  Page: wrap(function(el, p){ mountPage(el, {sport: p.sport || 'all'}); }, ['sport'])
};
})();
