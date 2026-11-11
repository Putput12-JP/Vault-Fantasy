/* Proven-sharps side card renderer (mock). Reads Vault's card format straight from the sample (docs/side-cards.md).
   Every number on screen is a stored field. A null field prints "n/a". No units, no "to win": sharp money is context only. */
(function(){
'use strict';
var TEAMS = {ATL:['Hawks','atl'],BOS:['Celtics','bos'],BKN:['Nets','bkn'],CHA:['Hornets','cha'],CHI:['Bulls','chi'],CLE:['Cavaliers','cle'],
  DAL:['Mavericks','dal'],DEN:['Nuggets','den'],DET:['Pistons','det'],GSW:['Warriors','gs'],HOU:['Rockets','hou'],IND:['Pacers','ind'],
  LAC:['Clippers','lac'],LAL:['Lakers','lal'],MEM:['Grizzlies','mem'],MIA:['Heat','mia'],MIL:['Bucks','mil'],MIN:['Timberwolves','min'],
  NOP:['Pelicans','no'],NYK:['Knicks','ny'],OKC:['Thunder','okc'],ORL:['Magic','orl'],PHI:['76ers','phi'],PHX:['Suns','phx'],
  POR:['Trail Blazers','por'],SAC:['Kings','sac'],SAS:['Spurs','sa'],TOR:['Raptors','tor'],UTA:['Jazz','utah'],WAS:['Wizards','wsh']};
var GROUPS = [['ml','Moneyline'],['spread','Spread'],['total','Total']];
var GNAME = {ml:'moneyline', spread:'spread', total:'total'};
var ICON = {
  lock:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="10" height="7" rx="1.8"/><path d="M5.2 7V5a2.8 2.8 0 0 1 5.6 0v2"/></svg>',
  star:'<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 1.2l2 4.3 4.7.6-3.4 3.2.9 4.6L8 11.6l-4.2 2.3.9-4.6L1.3 6.1 6 5.5z"/></svg>',
  hour:'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 2.5h10M5 17.5h10M6 2.5c0 4 4 4.5 4 7.5s-4 3.5-4 7.5M14 2.5c0 4-4 4.5-4 7.5s4 3.5 4 7.5"/></svg>',
  flag:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 14.5v-12M3.5 3h8l-1.8 2.8L11.5 8.6h-8"/></svg>'
};

function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function trim(s){ return s.replace(/\.0+$/, '').replace(/(\.\d*[1-9])0+$/, '$1'); }
function usd(n){
  if (n == null) return 'n/a';
  var a = Math.abs(n), s;
  if (a < 1000) s = String(Math.round(a));
  else if (a < 1e4) s = trim((a / 1e3).toFixed(2)) + 'K';
  else if (a < 1e5) s = trim((a / 1e3).toFixed(1)) + 'K';
  else if (a < 1e6) s = Math.round(a / 1e3) + 'K';
  else s = trim((a / 1e6).toFixed(2)) + 'M';
  return '$' + s;
}
function susd(n){ return n == null ? 'n/a' : (n < 0 ? '-' : '+') + usd(n); }
function roi(x){ return x == null ? 'n/a' : (x < 0 ? '-' : '+') + trim(Math.abs(x * 100).toFixed(1)) + '%'; }
function tail(w){ return '…' + w.slice(-6); }
function ct(ts, withDay){
  var d = new Date(ts * 1000), o = {timeZone:'America/Chicago', hour:'numeric', minute:'2-digit'};
  var t = d.toLocaleTimeString('en-US', o);
  if (!withDay) return t;
  return d.toLocaleDateString('en-US', {timeZone:'America/Chicago', weekday:'short', month:'short', day:'numeric'}) + ' · ' + t;
}
function dur(s){ var h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); return h >= 48 ? Math.round(h / 24) + 'd' : h ? h + 'h ' + m + 'm' : m + 'm'; }
function phone(){ return matchMedia('(max-width:767px)').matches; }

function logo(name, g){
  if (name === 'Over' || name === 'Under') return '<div class="sc-logo">' + name[0] + '</div>';
  var ab = [g.vault.away, g.vault.home].filter(function(a){ return TEAMS[a] && TEAMS[a][0] === name; })[0];
  if (!ab) return '<div class="sc-logo">' + esc(name.slice(0, 3).toUpperCase()) + '</div>';
  return '<div class="sc-logo"><img alt="" src="https://a.espncdn.com/i/teamlogos/nba/500/' + TEAMS[ab][1] + '.png" onerror="this.replaceWith(document.createTextNode(\'' + ab + '\'))"></div>';
}
function sideOrder(g, m, key){
  var names = Object.keys(m.sides);
  if (key === 'total') return names.sort();                         /* Over, Under */
  var away = TEAMS[g.vault.away] && TEAMS[g.vault.away][0];
  return names.sort(function(a, b){ return (a === away ? 0 : 1) - (b === away ? 0 : 1); });
}
function sideLabel(name, key, ls){
  if (key === 'ml') return name + ' ML';
  if (key === 'total') return name;
  if (ls && ls.side === name && ls.line != null) return name + ' ' + (ls.line > 0 ? '+' : '') + ls.line;
  return name + ' spread';
}

var CHK = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 8.5l3 3 6-7"/></svg>';
var XX = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/></svg>';
function counted(s){ return s.sharp_usd + s.unproven_usd + s.loser_usd; }
function nProven(s){ return s.counts.sharp + s.counts.hc; }
function shadow(m, v){ var ls = (m.lock_shadow || {})[v] || {}; return ls.side && ls.gates ? ls : null; }
/* climate, from stored fields only: signal = a side meets the tracked rule; building = proven money somewhere; quiet = none */
function climate(g, v){
  var c = 'quiet';
  Object.keys(g.markets).forEach(function(k){ var m = g.markets[k];
    if (shadow(m, v)) c = 'signal';
    else if (c === 'quiet' && Object.keys(m.sides).some(function(n){ return m.sides[n][v].sharp_usd > 0; })) c = 'building'; });
  return c;
}
var CLIM = {quiet:'Quiet', building:'Building', signal:'Signal'};

/* one side of the balance bar: classes stacked outward from the centre line */
function half(s, max, dir){
  var seg = function(k, v){ return v > 0 ? '<i class="' + k + '" style="width:' + Math.max(1.2, v / max * 100).toFixed(2) + '%"></i>' : ''; };
  return '<div class="sc-half ' + dir + '">' + seg('hc', s.hc_usd) + seg('sharp', s.sharp_usd - s.hc_usd) + seg('unp', s.unproven_usd) + seg('loser', s.loser_usd) + seg('exc', s.excluded_usd) + '</div>';
}
/* v3: a stack of small modules. Verdict, money split, proven record, wallets (collapsed), data notes (collapsed). */
function verdict(g, m, key, names, v){
  var ls = shadow(m, v), S = {}; names.forEach(function(n){ S[n] = m.sides[n][v]; });
  var tick = function(ok, t){ return '<span class="sc-tick ' + (ok ? 'ok' : 'no') + '">' + (ok ? CHK : XX) + t + '</span>'; };
  if (ls){
    var q = ls.gates, u = ls.units_clean_ladder;
    return '<section class="sc-mod sc-v on"><div class="sc-v1"><b class="sc-vu num">' + (u == null ? 'n/a' : u + '<small>u</small>') + '</b>' +
      '<div class="sc-vt"><span class="sc-cap">Suggested ' + (g.frozen ? '· locked' : '· live until ' + ct(g.cut) + ' CT') + '</span>' +
      '<strong>' + esc(sideLabel(ls.side, key, ls)) + '</strong><span class="sc-vs">' +
      (ls.price != null ? '<span class="num">' + trim((ls.price * 100).toFixed(1)) + '¢</span> on Polymarket' + (ls.price_t ? ', read ' + ct(ls.price_t) + ' CT' : '') : 'price n/a') + '</span></div>' +
      logo(ls.side, g) + '</div>' +
      '<div class="sc-ticks">' + tick(1, '<span class="num">' + Math.round(q.share_for * 100) + '%</span> of the money') + tick(1, '<span class="num">' + q.proven_for + '</span> proven for') +
      tick(1, '<span class="num">' + q.proven_against + '</span> against') + tick(1, 'sized up' + (ls.top_press != null ? ' <span class="num">' + ls.top_press + 'x</span>' : '')) + '</div>' +
      '<details class="sc-more"><summary>How the size is set</summary><p>Size follows the biggest press on the side: 3x or more is 5u, 2x or more is 2u, otherwise 3u. A side priced under 50¢ is capped at 1u. ' +
      'The rule is in its forward test and has no graded record yet.</p></details></section>';
  }
  var lead = names.slice().sort(function(a, b){ return (nProven(S[b]) - nProven(S[a])) || (counted(S[b]) - counted(S[a])); })[0];
  var other = names.filter(function(n){ return n !== lead; })[0], tot = counted(S[lead]) + counted(S[other]);
  var share = tot ? counted(S[lead]) / tot : null, pf = nProven(S[lead]), pa = nProven(S[other]), why;
  if (!tot) why = 'No wallet holds $250 or more here yet.';
  else if (!pf) why = v === 'fwd' ? 'No wallet is proven on forward-only results yet.' : 'No proven wallet on either side yet. The ledger is still filling.';
  else if (pa) why = 'Proven wallets are on both sides.';
  else if (share < .6) why = 'Proven money is on ' + esc(lead) + ', but it holds <span class="num">' + Math.round(share * 100) + '%</span> of the money. The rule needs 60%.';
  else why = esc(lead) + ' has the money and a proven wallet. No wallet is sized up to 1.5x its usual stake yet.';
  return '<section class="sc-mod sc-v off"><div class="sc-v1"><b class="sc-vu num zero">0<small>u</small></b><div class="sc-vt"><span class="sc-cap">Suggested</span>' +
    '<strong>No play</strong><span class="sc-vs">' + why + '</span></div></div></section>';
}
function sideTile(g, n, s, pick){
  var line = function(k, v, t){ return v > 0 ? '<span class="sc-ln ' + k + '"><i></i><b class="num">' + usd(v) + '</b> ' + t + '</span>' : ''; };
  var lines = line('hc', s.hc_usd, 'sized up') + line('sharp', s.sharp_usd - s.hc_usd, 'proven') + line('loser', s.loser_usd, 'losers') + line('exc', s.excluded_usd, 'excluded');
  return '<div class="sc-mod sc-st' + (pick ? ' pk' : '') + '"><div class="sc-sth">' + logo(n, g).replace('sc-logo', 'sc-logo sm') + '<b>' + esc(n) + '</b></div>' +
    '<div class="sc-big num">' + usd(counted(s)) + '</div><div class="sc-lns">' + (lines || '<span class="sc-ln none">no proven or loser money</span>') + '</div></div>';
}
function walletRow(w, k){
  return '<div class="sc-w ' + k + '"><span class="sc-wd">' + (w.star ? ICON.star : '<i></i>') + '</span><b class="num">' + tail(w.w) + '</b>' +
    '<span class="sc-wu num">' + usd(w.usd) + (w.press != null ? ' <em>' + w.press + 'x</em>' : '') + '</span>' +
    '<span class="sc-wr num">' + w.w_ + '-' + w.l_ + ' · L30 ' + roi(w.l30_roi) + ' · ' + susd(w.pnl) + '</span></div>';
}
function walletList(n, s){
  var sum = function(a){ return a.reduce(function(t, x){ return t + x.usd; }, 0); }, c = s.counts, np = nProven(s), h = '<div class="sc-wg"><span class="sc-cap">' + esc(n) + '</span>';
  var agg = function(k, t, v){ return '<div class="sc-w agg ' + k + '"><span class="sc-wd"><i></i></span><b>' + t + '</b><span class="sc-wu num">' + usd(v) + '</span></div>'; };
  s.list.forEach(function(w){ h += walletRow(w, w.star ? 'hc' : 'sharp'); });
  if (np > s.list.length) h += agg('sharp', '+' + (np - s.list.length) + ' more proven', Math.max(0, s.sharp_usd - sum(s.list)));
  s.losers.forEach(function(w){ h += walletRow(w, 'loser'); });
  if (c.loser > s.losers.length) h += agg('loser', '+' + (c.loser - s.losers.length) + ' more losers', Math.max(0, s.loser_usd - sum(s.losers)));
  if (c.unproven) h += agg('unp', c.unproven + ' unproven', s.unproven_usd);
  if (c.excluded) h += agg('exc', c.excluded + ' excluded, not counted', s.excluded_usd);
  if (!(np + c.loser + c.unproven + c.excluded)) h += '<div class="sc-w agg exc"><span class="sc-wd"><i></i></span><b>No holders at $250 or more</b></div>';
  return h + '</div>';
}
function body(g, st){
  var m = g.markets[st.group], names = sideOrder(g, m, st.group), v = st.variant, ls = shadow(m, v);
  var a = m.sides[names[0]][v], b = m.sides[names[1]][v], max = Math.max(counted(a) + a.excluded_usd, counted(b) + b.excluded_usd) || 1;
  var h = verdict(g, m, st.group, names, v);
  h += '<div class="sc-split">' + sideTile(g, names[0], a, ls && ls.side === names[0]) + sideTile(g, names[1], b, ls && ls.side === names[1]) +
    '<div class="sc-bar">' + half(a, max, 'l') + '<u></u>' + half(b, max, 'r') + '</div></div>';
  var best = names.slice().sort(function(x, y){ return m.sides[y][v].sharp_usd - m.sides[x][v].sharp_usd; })[0], p = m.sides[best][v].proven;
  if (p.wallets){
    h += '<section class="sc-mod sc-pr"><span class="sc-cap">Proven wallets on ' + esc(best) + ' · ' + p.wallets + '</span><div class="sc-kp">' +
      '<div><b class="num">' + (p.win_pct == null ? 'n/a' : p.win_pct + '%') + '</b><span>win</span></div><div><b class="num">' + p.w + '-' + p.l + '</b><span>record</span></div>' +
      '<div><b class="num">' + roi(p.l30_roi) + '</b><span>last 30 days</span></div><div><b class="num">' + susd(p.lifetime_pnl) + '</b><span>lifetime</span></div></div>' +
      (p.last20.length ? '<div class="sc-form">' + p.last20.map(function(r){ return '<i class="' + r + '"></i>'; }).join('') + '<span>last ' + p.last20.length + '</span></div>' : '') + '</section>';
  }
  var nW = names.reduce(function(t, n){ var c = m.sides[n][v].counts; return t + c.hc + c.sharp + c.unproven + c.loser + c.excluded; }, 0);
  h += '<details class="sc-mod sc-dt" data-d="w"' + (st.open.w ? ' open' : '') + '><summary>Wallets<em class="num">' + nW + '</em></summary><div class="sc-dtb">' +
    names.map(function(n){ return walletList(n, m.sides[n][v]); }).join('') +
    '<div class="sc-hist"><span class="sc-cap">Wallet history</span><div class="vseg sm" data-k="variant"><i class="v-pill"></i><button type="button" data-v="all"' + (v === 'all' ? ' class="on"' : '') +
    '>All</button><button type="button" data-v="fwd"' + (v === 'fwd' ? ' class="on"' : '') + '>Forward only</button></div></div></div></details>';
  var cv = g.coverage, bits = ['Money is mark value ' + (g.frozen ? 'at the lock' : 'now') + ' (shares x price), not cost.',
    cv.markets_read + ' markets read, ' + cv.markets_missed + ' missed' + (cv.late_reads ? ', ' + cv.late_reads + ' late' : '') + '.',
    'Oldest read ' + dur(cv.max_read_lag_s) + ' before ' + (g.frozen ? 'the lock' : 'this build') + '.', 'Ledger refreshed ' + ct(g.ledger_run_at) + ' CT.'];
  if (cv.two_way_dust_dropped) bits.push(cv.two_way_dust_dropped + ' two-way ' + (cv.two_way_dust_dropped === 1 ? 'wallet' : 'wallets') + ' dropped as balanced dust.');
  if (g.vault.start_gap_flag) bits.push('Start times differ by ' + g.vault.start_gap_min + ' min between Polymarket and Vault.');
  if (g.test) bits.push(g.test.counts ? 'Counts for the forward test.' : 'Does not count for the forward test: ' + g.test.why_not.join(', ') + '.');
  return h + '<details class="sc-mod sc-dt" data-d="n"' + (st.open.n ? ' open' : '') + '><summary>Data notes</summary><div class="sc-dtb"><p>' + bits.join(' ') + '</p></div></details>' +
    '<p class="sc-foot">Sharp money is context. Units come from a rule still in its forward test.</p>';
}

function rail(strip, animate){
  var on = strip.querySelector('button.on'), pill = strip.querySelector('.v-pill');
  if (!on || !pill || !strip.offsetWidth) return;
  if (!animate || pill.style.opacity !== '1'){ strip.classList.add('rail-noanim'); }
  pill.style.left = on.offsetLeft + 'px'; pill.style.width = on.offsetWidth + 'px'; pill.style.opacity = '1';
  void pill.offsetWidth; strip.classList.remove('rail-noanim');
}

function mount(el, g, opt){
  opt = opt || {};
  var keys = GROUPS.filter(function(x){ return g.markets[x[0]]; }).map(function(x){ return x[0]; });
  var st = {group: keys.indexOf(opt.group) >= 0 ? opt.group : keys[0], variant: 'all', open: {}};
  var away = TEAMS[g.vault.away], home = TEAMS[g.vault.home];
  var head = '<div class="sc-top"><div><div class="sc-match">' + esc(away ? away[0] : g.vault.away) + ' <i>at</i> ' + esc(home ? home[0] : g.vault.home) + '</div>' +
    '<div class="sc-time"><span class="sc-sport">' + g.sport.toUpperCase() + '</span><span class="num">' + ct(g.gst, true) + ' CT</span></div></div>' +
    (g.frozen ? '<div class="sc-pill locked">' + ICON.lock + 'Locked ' + ct(g.cut) + '</div>' : '<div class="sc-pill live"><i></i>Live · locks ' + ct(g.cut) + '</div>') + '</div>';
  if (!keys.length){
    el.innerHTML = head + '<div class="sc-mod sc-empty"><b>Nothing to show yet</b><p>No wallet holds $250 or more on this game. The card fills in as money arrives and locks ' + ct(g.cut, true) + ' CT.</p></div>';
    return;
  }
  function strip(){
    return GROUPS.map(function(x){ var m = g.markets[x[0]], ls = m && shadow(m, st.variant);
      return '<button type="button" data-v="' + x[0] + '"' + (m ? '' : ' disabled') + (x[0] === st.group ? ' class="on"' : '') + '>' + x[1] + (ls ? '<span class="sc-dotu num">' + ls.units_clean_ladder + 'u</span>' : '') + '</button>'; }).join('');
  }
  el.innerHTML = head + '<div class="vseg fluid" data-k="group" role="tablist" aria-label="Market"><i class="v-pill"></i>' + strip() + '</div><div class="sc-body"></div>';
  var bodyEl = el.querySelector('.sc-body'), top = el.querySelector('.vseg[data-k=group]');
  function paint(){ bodyEl.innerHTML = body(g, st); var h = bodyEl.querySelector('.vseg'); if (h && h.offsetWidth) rail(h, false); }
  paint(); rail(top, false);
  el.addEventListener('toggle', function(e){ var d = e.target; if (d.dataset && d.dataset.d){ st.open[d.dataset.d] = d.open; var h = d.querySelector('.vseg'); if (h && d.open) rail(h, false); } }, true);
  el.addEventListener('click', function(e){
    var b = e.target.closest('.vseg > button');
    if (!b || b.disabled) return;
    var s = b.parentNode; st[s.dataset.k] = b.dataset.v;
    if (s === top){ [].forEach.call(s.children, function(c){ c.classList.toggle('on', c === b); }); rail(s, true); paint(); }
    else { top.innerHTML = '<i class="v-pill"></i>' + strip(); rail(top, false); paint(); }
  });
  el._repaint = function(){ paint(); rail(top, false); };
}

/* slate strip: totals over every game in the file, stored fields only */
function slate(el, data){
  var usdSum = 0, sides = 0, wallets = {}, cl = {quiet:0, building:0, signal:0}, plays = 0, ex = 0;
  data.games.forEach(function(g){
    cl[climate(g, 'all')]++;
    Object.keys(g.markets).forEach(function(k){ var m = g.markets[k]; if (shadow(m, 'all')) plays++;
      Object.keys(m.sides).forEach(function(n){ var s = m.sides[n].all; usdSum += s.sharp_usd; ex += s.excluded_usd; if (s.sharp_usd > 0) sides++;
        s.list.forEach(function(w){ wallets[w.w] = 1; }); }); });
  });
  var t = function(v, l, sub, cls){ return '<div class="sl-t ' + (cls || '') + '"><span>' + l + '</span><b class="num">' + v + '</b><em>' + sub + '</em></div>'; };
  el.innerHTML = t(plays, 'Suggested plays', 'of ' + data.games.length + ' games', 'good') +
    t(usd(usdSum), 'Proven money', sides + ' sides, ' + Object.keys(wallets).length + ' wallets', 'gold') +
    '<div class="sl-t clim"><span>Climate</span><div class="sl-dots">' +
      ['signal', 'building', 'quiet'].map(function(k){ return new Array(cl[k] + 1).join('<i class="' + k + '"></i>'); }).join('') + '</div><em>' +
      cl.signal + ' signal · ' + cl.building + ' building · ' + cl.quiet + ' quiet</em></div>';
}

window.SideCard = {mount: mount, slate: slate};
})();
