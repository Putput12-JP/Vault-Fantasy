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
function unitChip(ls){
  if (!ls) return '<span class="sc-u off">no play</span>';
  return '<span class="sc-u on num">' + (ls.units_clean_ladder == null ? 'n/a' : ls.units_clean_ladder + 'u') + '</span>';
}
function marketRow(g, key, label, st){
  var m = g.markets[key];
  if (!m) return '<div class="sc-mk off"><div class="sc-mk1"><b>' + label + '</b><span class="sc-u off">not read yet</span></div></div>';
  var names = sideOrder(g, m, key), a = m.sides[names[0]][st.variant], b = m.sides[names[1]][st.variant], ls = shadow(m, st.variant);
  var max = Math.max(counted(a) + a.excluded_usd, counted(b) + b.excluded_usd) || 1;
  var nm = function(n, s){ return '<span' + (ls && ls.side === n ? ' class="pk"' : '') + '>' + esc(n) + ' <em class="num">' + usd(counted(s)) + '</em></span>'; };
  return '<button type="button" class="sc-mk press press-row' + (st.group === key ? ' on' : '') + '" data-g="' + key + '" aria-pressed="' + (st.group === key) + '">' +
    '<div class="sc-mk1"><b>' + label + '</b>' + unitChip(ls) + '</div>' +
    '<div class="sc-mk2">' + nm(names[0], a) + nm(names[1], b) + '</div>' +
    '<div class="sc-bar">' + half(a, max, 'l') + '<u></u>' + half(b, max, 'r') + '</div></button>';
}

/* the suggested-units block. Units are the stored units_clean_ladder of the pre-registered rule; nothing is computed here. */
function signal(g, m, key, names, v){
  var ls = shadow(m, v), S = {}; names.forEach(function(n){ S[n] = m.sides[n][v]; });
  var gate = function(ok, t){ return '<span class="sc-gate ' + (ok == null ? 'na' : ok ? 'ok' : 'no') + '">' + (ok == null ? '' : ok ? CHK : XX) + t + '</span>'; };
  if (ls){
    var q = ls.gates, u = ls.units_clean_ladder, pips = '';
    for (var i = 1; i <= 5; i++) pips += '<i' + (u != null && i <= u ? ' class="on"' : '') + '></i>';
    return '<div class="sc-sig on"><div class="sc-sig1">' + logo(ls.side, g) + '<div class="sc-hl"><div class="sc-eyebrow">Suggested units · ' + (g.frozen ? 'locked' : 'live, can change until ' + ct(g.cut) + ' CT') + '</div>' +
      '<div class="sc-side">' + esc(sideLabel(ls.side, key, ls)) + '</div><div class="sc-price">' +
      (ls.price != null ? '<span class="num">' + trim((ls.price * 100).toFixed(1)) + '¢</span> Polymarket' + (ls.price_t ? ' · read ' + ct(ls.price_t) + ' CT' : '') : '<span class="na">price n/a</span>') + '</div></div>' +
      '<div class="sc-units"><b class="num">' + (u == null ? 'n/a' : u + '<small>u</small>') + '</b><div class="sc-pips">' + pips + '</div></div></div>' +
      '<div class="sc-gates">' + gate(true, '<span class="num">' + trim((q.share_for * 100).toFixed(1)) + '%</span> of counted money (needs 60%)') +
      gate(true, '<span class="num">' + q.proven_for + '</span> proven for') + gate(true, '<span class="num">' + q.proven_against + '</span> proven against') +
      gate(true, '<span class="num">' + q.pressers_n15 + '</span> sized up' + (ls.top_press != null ? ', top <span class="num">' + ls.top_press + 'x</span>' : '')) + '</div>' +
      '<p class="sc-fine">Size comes from the biggest press on the side: 3x or more is 5u, 2x or more is 2u, otherwise 3u, and any side priced under 50¢ is capped at 1u. ' +
      'This rule is in its forward test and has no graded record yet.</p></div>';
  }
  /* no play: show how far the leading side is from the gates, using stored money and counts only */
  var lead = names.slice().sort(function(a, b){ return (nProven(S[b]) - nProven(S[a])) || (counted(S[b]) - counted(S[a])); })[0];
  var other = names.filter(function(n){ return n !== lead; })[0], tot = counted(S[lead]) + counted(S[other]);
  var share = tot ? counted(S[lead]) / tot : null, pf = nProven(S[lead]), pa = nProven(S[other]);
  var why = v === 'fwd' ? 'Forward only counts results from after a wallet was first tracked, and no wallet clears the bar on those alone yet.'
    : pf ? 'A proven wallet is here, but the side does not clear every gate.' : tot ? 'No wallet on this market has a graded book of 6 bets, 55% wins and +3% ROI yet. The ledger is still filling.' : 'No wallet holds $250 or more on this market yet.';
  return '<div class="sc-sig off"><div class="sc-sig1"><div class="sc-logo none">0u</div><div class="sc-hl"><div class="sc-eyebrow">Suggested units</div>' +
    '<div class="sc-side quiet">No play on the ' + GNAME[key] + '</div><div class="sc-price">' + why + '</div></div></div>' +
    (tot ? '<div class="sc-gates"><span class="sc-gl">' + esc(lead) + '</span>' +
      gate(share >= .6, '<span class="num">' + trim((share * 100).toFixed(1)) + '%</span> of counted money (needs 60%)') +
      gate(pf >= 1, '<span class="num">' + pf + '</span> proven for') + gate(pa === 0, '<span class="num">' + pa + '</span> proven against') +
      gate(null, 'sized up: n/a') + '</div>' : '') + '</div>';
}

function walletRow(w, k){
  var p = w.press, fill = p == null ? 0 : Math.min(p / 3, 1) * 100;
  return '<div class="sc-w ' + k + '"><span class="sc-wd">' + (w.star ? ICON.star : '<i></i>') + '</span><b class="num">' + tail(w.w) + '</b>' +
    '<span class="sc-wu num">' + usd(w.usd) + '</span>' +
    '<span class="sc-pm" title="position vs usual stake"><span class="tr"><i style="width:' + fill.toFixed(1) + '%"></i><u></u></span><em class="num">' + (p == null ? 'n/a' : p + 'x') + '</em></span>' +
    '<span class="sc-wr num">' + w.w_ + '-' + w.l_ + ' · L30 ' + roi(w.l30_roi) + ' · ' + susd(w.pnl) + '</span></div>';
}
function aggRow(k, t, v, note){ return '<div class="sc-w agg ' + k + '"><span class="sc-wd"><i></i></span><b>' + t + '</b><span class="sc-wu num">' + usd(v) + '</span><span class="sc-wr">' + (note || '') + '</span></div>'; }
function sideBlock(g, n, s){
  var sum = function(a){ return a.reduce(function(t, x){ return t + x.usd; }, 0); }, c = s.counts, p = s.proven, h = '';
  h += '<div class="sc-sd"><div class="sc-sdh">' + logo(n, g).replace('sc-logo', 'sc-logo sm') + '<b>' + esc(n) + '</b><span class="num">' + usd(counted(s)) + ' counted</span></div>';
  if (p.wallets){
    h += '<div class="sc-rec"><span><b class="num">' + (p.win_pct == null ? 'n/a' : p.win_pct + '%') + '</b> win</span><span><b class="num">' + p.w + '-' + p.l + '</b> record</span>' +
      '<span><b class="num">' + roi(p.l30_roi) + '</b> L30 ROI</span><span><b class="num">' + susd(p.lifetime_pnl) + '</b> lifetime</span></div>';
    if (p.last20.length) h += '<div class="sc-form" aria-label="last ' + p.last20.length + ' results">' + p.last20.map(function(r){ return '<i class="' + r + '"></i>'; }).join('') + '<span>LAST ' + p.last20.length + '</span></div>';
  }
  s.list.forEach(function(w){ h += walletRow(w, w.star ? 'hc' : 'sharp'); });
  var np = nProven(s);
  if (np > s.list.length) h += aggRow('sharp', '+' + (np - s.list.length) + ' more proven', Math.max(0, s.sharp_usd - sum(s.list)));
  if (!np) h += '<div class="sc-w none"><span class="sc-wd"><i></i></span><b>No proven wallets on this side</b></div>';
  s.losers.forEach(function(w){ h += walletRow(w, 'loser'); });
  if (c.loser > s.losers.length) h += aggRow('loser', '+' + (c.loser - s.losers.length) + ' more losers', Math.max(0, s.loser_usd - sum(s.losers)));
  if (c.unproven) h += aggRow('unp', c.unproven + ' unproven', s.unproven_usd);
  if (c.excluded) h += aggRow('exc', c.excluded + ' excluded', s.excluded_usd, 'not counted');
  return h + '</div>';
}

function body(g, st){
  var h = '<div class="sc-mks">' + GROUPS.map(function(x){ return marketRow(g, x[0], x[1], st); }).join('') + '</div>' +
    '<div class="sc-key"><span class="hc">sized up</span><span class="sharp">proven</span><span class="unp">unproven</span><span class="loser">losers</span><span class="exc">excluded</span></div>';
  var m = g.markets[st.group], names = sideOrder(g, m, st.group);
  h += signal(g, m, st.group, names, st.variant);
  h += '<div class="sc-lab"><span>Who holds each side</span><span>press vs usual stake</span></div><div class="sc-sides">' +
    names.map(function(n){ return sideBlock(g, n, m.sides[n][st.variant]); }).join('') + '</div>';
  var cv = g.coverage, bits = ['<b>Sharp money is context.</b> Units come from a rule still in its forward test. Money is mark value ' + (g.frozen ? 'at the lock' : 'now') + ' (shares x price), not cost.',
    cv.markets_read + ' markets read, ' + cv.markets_missed + ' missed' + (cv.late_reads ? ', ' + cv.late_reads + ' late' : '') + '.',
    'Oldest read ' + dur(cv.max_read_lag_s) + ' before ' + (g.frozen ? 'the lock' : 'this build') + '.', 'Ledger refreshed ' + ct(g.ledger_run_at) + ' CT.'];
  if (cv.two_way_dust_dropped) bits.push(cv.two_way_dust_dropped + ' two-way ' + (cv.two_way_dust_dropped === 1 ? 'wallet' : 'wallets') + ' dropped as balanced dust.');
  if (g.vault.start_gap_flag) bits.push('Start times differ by ' + g.vault.start_gap_min + ' min between Polymarket and Vault.');
  if (g.test) bits.push(g.test.counts ? 'Counts for the forward test.' : 'Does not count for the forward test: ' + g.test.why_not.join(', ') + '.');
  return h + '<div class="sc-foot">' + bits.join(' ') + '</div>';
}

/* one travelling pill per strip (vault-ds.css 19.2): seed without animation, then travel on --ease-rail */
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
  var st = {group: keys.indexOf(opt.group) >= 0 ? opt.group : keys[0], variant: 'all'};
  var away = TEAMS[g.vault.away], home = TEAMS[g.vault.home];
  function head(){
    var c = climate(g, st.variant);
    return '<div class="sc-top"><div><div><span class="sc-sport">' + g.sport.toUpperCase() + '</span><span class="sc-match">' +
      esc(away ? away[0] : g.vault.away) + ' @ ' + esc(home ? home[0] : g.vault.home) + '</span></div><div class="sc-time num">' + ct(g.gst, true) + ' CT</div></div>' +
      '<div class="sc-tr"><span class="sc-clim ' + c + '"><i></i><i></i><i></i>' + CLIM[c] + '</span>' + (g.frozen
        ? '<div class="sc-pill locked">' + ICON.lock + 'LOCKED ' + ct(g.cut) + '</div>'
        : '<div class="sc-pill live"><i></i>LIVE · locks ' + ct(g.cut) + '</div>') + '</div></div>';
  }
  if (!keys.length){
    el.innerHTML = head() + '<div class="sc-empty"><b>Nothing to show yet</b><p>No wallet holds $250 or more on this game. The card fills in as money arrives and locks ' +
      ct(g.cut, true) + ' CT.</p></div><div class="sc-foot"><b>Sharp money is context.</b> ' + g.coverage.markets_read + ' market read, ' + g.coverage.markets_missed +
      ' missed. Ledger refreshed ' + ct(g.ledger_run_at) + ' CT.</div>';
    return;
  }
  el.innerHTML = '<div class="sc-hd"></div><div class="sc-ctl"><span class="sc-ctll">Wallet history</span><div class="vseg sm" data-k="variant" aria-label="History"><i class="v-pill"></i>' +
    '<button type="button" data-v="all" class="on">All history</button><button type="button" data-v="fwd">Forward only</button></div></div><div class="sc-body"></div>';
  var hd = el.querySelector('.sc-hd'), bodyEl = el.querySelector('.sc-body'), strips = [].slice.call(el.querySelectorAll('.vseg'));
  function paint(){ hd.innerHTML = head(); bodyEl.innerHTML = body(g, st); }
  paint(); strips.forEach(function(s){ rail(s, false); });
  el.addEventListener('click', function(e){
    var b = e.target.closest('.vseg > button'), mk = e.target.closest('button.sc-mk');
    if (b && !b.disabled){
      var strip = b.parentNode;
      [].forEach.call(strip.children, function(c){ c.classList.toggle('on', c === b); });
      st[strip.dataset.k] = b.dataset.v; rail(strip, true); paint();
    } else if (mk){ st.group = mk.dataset.g; paint(); }
  });
  el._repaint = function(){ paint(); strips.forEach(function(s){ rail(s, false); }); };
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
  el.innerHTML = t(usd(usdSum), 'Proven money on the slate', sides + ' sides · ' + Object.keys(wallets).length + ' proven wallets shown', 'gold') +
    t(plays, 'Suggested plays', 'sides that meet the tracked rule', 'good') +
    t(usd(ex), 'Excluded money', 'two-way and churn wallets, not counted') +
    '<div class="sl-t clim"><span>Sharp climate · ' + data.games.length + ' games</span><div class="sl-dots">' +
      ['signal', 'building', 'quiet'].map(function(k){ return new Array(cl[k] + 1).join('<i class="' + k + '"></i>'); }).join('') + '</div><em>' +
      cl.signal + ' signal · ' + cl.building + ' building · ' + cl.quiet + ' quiet</em></div>';
}

window.SideCard = {mount: mount, slate: slate};
})();
