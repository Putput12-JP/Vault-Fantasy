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

/* rows on the left of one side's flow: proven wallets, the unproven pool, loser wallets, the excluded pool */
function rowsOf(s){
  var rows = [], c = s.counts, sum = function(a){ return a.reduce(function(t, x){ return t + x.usd; }, 0); };
  s.list.forEach(function(w){ rows.push({k: w.star ? 'hc' : 'sharp', usd: w.usd, w: w}); });
  var np = c.sharp + c.hc;
  if (np > s.list.length) rows.push({k:'sharp', agg:1, t:'+' + (np - s.list.length) + ' more proven', usd: Math.max(0, s.sharp_usd - sum(s.list))});
  if (c.unproven) rows.push({k:'unp', agg:1, t: c.unproven + ' unproven', usd: s.unproven_usd});
  s.losers.forEach(function(w){ rows.push({k:'loser', usd: w.usd, w: w}); });
  if (c.loser > s.losers.length) rows.push({k:'loser', agg:1, t:'+' + (c.loser - s.losers.length) + ' more losers', usd: Math.max(0, s.loser_usd - sum(s.losers))});
  if (c.excluded) rows.push({k:'exc', agg:1, t: c.excluded + ' excluded', usd: s.excluded_usd, note:'not counted'});
  return rows;
}
function rowHtml(r){
  if (r.agg) return '<div class="sc-row agg ' + r.k + '"><b>' + r.t + '</b><span class="num">' + usd(r.usd) + (r.note ? ' · ' + r.note : '') + '</span></div>';
  var w = r.w;
  return '<div class="sc-row ' + r.k + '"><b>' + (w.star ? ICON.star : '') + '<span class="num">' + tail(w.w) + '</span><small class="num">' + usd(w.usd) +
    (w.press != null ? '<span class="px"> · ' + w.press + 'x</span>' : '') + '</small></b>' +
    '<span class="num">' + w.w_ + '-' + w.l_ + ' · L30 ' + roi(w.l30_roi) + ' · ' + susd(w.pnl) + '</span></div>';
}
function sankey(rows, H, top, rowH, W, scale){
  var th = rows.map(function(r){ return r.usd > 0 ? Math.max(2, r.usd * scale) : 1.2; });
  var tot = th.reduce(function(a, b){ return a + b; }, 0) + (rows.length - 1) * 1.5, y = H / 2 - tot / 2, x0 = 9, x1 = W, cx = W * .55, out = '';
  out += '<line class="rail" x1="' + x0 + '" x2="' + x0 + '" y1="' + (top + rowH / 2) + '" y2="' + (top + rowH * (rows.length - .5)) + '"/>';
  var dots = '';
  rows.forEach(function(r, i){
    var ys = top + rowH * (i + .5), t = th[i], yt = y + t / 2; y += t + 1.5;
    var ts = Math.min(t, rowH - 10) / 2, te = t / 2;
    if (r.k === 'exc') out += '<path class="rb exc" d="M' + x0 + ' ' + ys + ' C' + cx + ' ' + ys + ' ' + cx + ' ' + yt + ' ' + x1 + ' ' + yt + '"/>';
    else out += '<path class="rb ' + r.k + '" d="M' + x0 + ' ' + (ys - ts) + ' C' + cx + ' ' + (ys - ts) + ' ' + cx + ' ' + (yt - te) + ' ' + x1 + ' ' + (yt - te) +
      ' L' + x1 + ' ' + (yt + te) + ' C' + cx + ' ' + (yt + te) + ' ' + cx + ' ' + (ys + ts) + ' ' + x0 + ' ' + (ys + ts) + 'Z"/>';
    dots += '<circle class="' + r.k + '" cx="' + x0 + '" cy="' + ys + '" r="5"/>';
  });
  return '<svg class="sc-sk" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" aria-hidden="true">' + out + dots + '</svg>';
}
function boxHtml(name, s, sel){
  var tot = s.sharp_usd + s.unproven_usd + s.loser_usd + s.excluded_usd, tone = s.sharp_usd > 0 ? ' good' : s.loser_usd > 0 ? ' bad' : '';
  var h = '<button type="button" class="sc-box press press-card' + tone + (sel ? ' sel' : '') + '" data-side="' + esc(name) + '" aria-pressed="' + !!sel + '"><u>' + esc(name) + '</u>';
  if (s.sharp_usd > 0){
    h += '<div class="big num">' + usd(s.sharp_usd) + '<small>proven</small></div>' +
      '<div class="pc num">' + (s.pct_of_sharp == null ? 'n/a' : s.pct_of_sharp + '%') + '<small>of sharp money</small></div>' +
      '<div class="ln num">' + usd(s.unproven_usd) + '<small>unproven</small></div>' +
      '<div class="ln num' + (s.loser_usd > 0 ? ' red' : ' dim') + '">' + usd(s.loser_usd) + '<small>losers</small></div>';
  } else if (s.loser_usd > 0){
    h += '<div class="big num red">' + usd(s.loser_usd) + '<small>losers</small></div>' +
      '<div class="pc num">' + (s.pct_of_losers == null ? 'n/a' : s.pct_of_losers + '%') + '<small>of loser money</small></div>' +
      '<div class="ln num">' + usd(s.unproven_usd) + '<small>unproven</small></div>' +
      '<div class="ln num dim">$0<small>proven</small></div>';
  } else {
    h += '<div class="big num zero">$0<small>proven</small></div>' +
      '<div class="ln num">' + usd(s.unproven_usd) + '<small>unproven</small></div>' +
      '<div class="ln num dim">$0<small>losers</small></div>';
  }
  if (s.excluded_usd > 0) h += '<div class="ln num dim">' + usd(s.excluded_usd) + '<small>excluded</small></div>';
  if (tot > 0){
    var seg = function(k, v){ return v > 0 ? '<i class="' + k + '" style="width:' + (v / tot * 100).toFixed(2) + '%"></i>' : ''; };
    h += '<div class="sc-mix">' + seg('hc', s.hc_usd) + seg('sharp', s.sharp_usd - s.hc_usd) + seg('unp', s.unproven_usd) + seg('loser', s.loser_usd) + seg('exc', s.excluded_usd) + '</div>';
  }
  return h + '</button>';
}

function body(g, st){
  var m = g.markets[st.group], names = sideOrder(g, m, st.group), v = st.variant, ls = (m.lock_shadow || {})[v] || {};
  var S = {}; names.forEach(function(n){ S[n] = m.sides[n][v]; });
  var top = names.slice().sort(function(a, b){ return S[b].sharp_usd - S[a].sharp_usd; })[0];
  var auto = S[top].sharp_usd > 0 ? top : null, pick = st.side && S[st.side] ? st.side : auto, s = pick ? S[pick] : null;
  var when = g.frozen ? 'at the lock' : 'as of ' + ct(g.built) + ' CT';
  var h = '';

  /* headline: the side, its price, and the proven money on it (where SharpFlow puts units) */
  if (pick){
    var price = ls.side === pick && ls.price != null
      ? '<span class="num">' + trim((ls.price * 100).toFixed(1)) + '¢</span> Polymarket' + (ls.price_t ? ' · read ' + ct(ls.price_t) + ' CT' : '')
      : '<span class="na">price n/a</span>';
    h += '<div class="sc-head">' + logo(pick, g) + '<div class="sc-hl"><div class="sc-eyebrow">' + (pick === auto ? 'Most proven money' : 'Selected side') + '</div>' +
      '<div class="sc-side">' + esc(sideLabel(pick, st.group, ls)) + '</div><div class="sc-price">' + price + '</div></div>' +
      '<div class="sc-amt"><b class="num' + (s.sharp_usd > 0 ? '' : ' zero') + '">' + usd(s.sharp_usd) + '</b><span>proven, mark value ' + (g.frozen ? 'at the lock' : 'now') + '</span></div></div>';
  } else {
    h += '<div class="sc-head"><div class="sc-logo none">$0</div><div class="sc-hl"><div class="sc-eyebrow">' + GNAME[st.group] + '</div>' +
      '<div class="sc-side quiet">No proven money yet</div><div class="sc-price">on either side, ' + when + '</div></div></div>';
  }

  /* combined proven sharps */
  h += '<div class="sc-lab"><span>Combined proven sharps</span>' + (s && s.proven.wallets ? '<em>' + s.proven.wallets + (s.proven.wallets === 1 ? ' wallet' : ' wallets') + ' on ' + esc(pick) + '</em>' : '') + '</div>';
  if (s && s.proven.wallets){
    var p = s.proven, pc = function(x){ return x.replace('%', '<small>%</small>'); };
    h += '<div class="sc-stats">' +
      '<div class="sc-stat"><b class="num' + (p.win_pct == null ? ' na' : '') + '">' + (p.win_pct == null ? 'n/a' : pc(p.win_pct + '%')) + '</b><span>WIN</span></div>' +
      '<div class="sc-stat"><b class="num' + (p.l30_roi == null ? ' na' : '') + '">' + pc(roi(p.l30_roi)) + '</b><span>L30 ROI</span></div>' +
      '<div class="sc-stat"><b class="num' + (p.lifetime_pnl == null ? ' na' : '') + '">' + susd(p.lifetime_pnl) + '</b><span>LIFETIME</span></div>' +
      '<div class="sc-stat"><b class="num">' + p.w + '-' + p.l + '</b><span>RECORD</span></div></div>';
    h += '<div class="sc-dots">' + (p.last20.length ? p.last20.map(function(r){ return '<i class="' + r + '" title="' + r + '"></i>'; }).join('') + '<span>LAST ' + p.last20.length + '</span>' : '<span style="margin-left:0">LAST 20 n/a</span>') + '</div>';
  } else {
    var held = names.reduce(function(t, n){ var c = S[n].counts; return t + c.hc + c.sharp + c.unproven + c.loser + c.excluded; }, 0);
    var msg = v === 'fwd'
      ? 'Forward only counts results from after a wallet was first tracked. No wallet on ' + (pick ? esc(pick) : 'this market') + ' clears the bar on those results alone yet.'
      : held ? held + (held === 1 ? ' wallet holds' : ' wallets hold') + ' this market at $250 or more. None ' + (pick ? 'on ' + esc(pick) + ' ' : '') +
          'has a graded NBA book that clears 6 bets, 55% wins and +3% ROI. The ledger is still filling.'
        : 'No wallet holds $250 or more on this market yet.';
    h += '<div class="sc-none">' + ICON.hour + '<div><b>' + (pick ? 'No proven wallets on ' + esc(pick) : 'No proven wallets here yet') + '</b><p>' + msg + '</p></div></div>';
  }

  /* wallets -> where it went */
  var ph = phone(), rowH = ph ? 56 : 46, W = ph ? 54 : 100, boxH = ph ? 150 : 150;
  var maxTot = Math.max.apply(null, names.map(function(n){ var x = S[n]; return x.sharp_usd + x.unproven_usd + x.loser_usd + x.excluded_usd; })) || 1;
  h += '<div class="sc-lab"><span>Wallets</span><span>Where it went</span></div><div class="sc-flow" style="--row-h:' + rowH + 'px;--sk-w:' + W + 'px;--box-h:' + boxH + 'px;--box-w:' + (ph ? '47%' : '212px') + '">';
  names.forEach(function(n){
    var rows = rowsOf(S[n]);
    if (!rows.length) rows = [{k:'exc', agg:1, t:'No holders', usd:0, note:'none at $250+'}];
    var listH = rows.length * rowH, H = Math.max(listH, boxH), topY = (H - listH) / 2;
    h += '<div class="sc-blk"><div class="sc-rows">' + rows.map(rowHtml).join('') + '</div>' + sankey(rows, H, topY, rowH, W, (ph ? 22 : 30) / maxTot) + boxHtml(n, S[n], n === pick) + '</div>';
  });
  h += '</div>';

  /* tracked rule: a small labelled marker only. No units, no price target. */
  if (ls.side && ls.gates){
    var q = ls.gates;
    h += '<details class="sc-rule"><summary>' + ICON.flag + 'Tracked rule (forward test)<span>' + esc(ls.side) + ' · details</span></summary><p>As of ' + (g.frozen ? 'the lock' : 'this read') + ', ' + esc(ls.side) +
      ' meets the pre-registered gates: <span class="num">' + trim((q.share_for * 100).toFixed(1)) + '%</span> of counted money, <span class="num">' + q.proven_for +
      '</span> proven for, <span class="num">' + q.proven_against + '</span> proven against, <span class="num">' + q.pressers_n15 +
      '</span> wallet at 1.5x or more of its usual stake. It is recorded so the rule can be graded later. It is not a pick.</p></details>';
  }

  var cv = g.coverage, bits = ['<b>Context, not a bet.</b> Money is mark value ' + (g.frozen ? 'at the lock' : 'now') + ' (shares x price), not cost.',
    cv.markets_read + ' markets read, ' + cv.markets_missed + ' missed' + (cv.late_reads ? ', ' + cv.late_reads + ' late' : '') + '.',
    'Oldest read ' + dur(cv.max_read_lag_s) + ' before ' + (g.frozen ? 'the lock' : 'this build') + '.',
    'Ledger refreshed ' + ct(g.ledger_run_at) + ' CT.'];
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
  var st = {group: keys.indexOf(opt.group) >= 0 ? opt.group : keys[0], variant: 'all', side: null};
  var away = TEAMS[g.vault.away], home = TEAMS[g.vault.home];
  var head = '<div class="sc-top"><div><div><span class="sc-sport">' + g.sport.toUpperCase() + '</span><span class="sc-match">' +
    esc(away ? away[0] : g.vault.away) + ' @ ' + esc(home ? home[0] : g.vault.home) + '</span></div><div class="sc-time num">' + ct(g.gst, true) + ' CT</div></div>' +
    '<div>' + (g.frozen
      ? '<div class="sc-pill locked">' + ICON.lock + 'LOCKED</div><div class="sc-pillsub">frozen ' + ct(g.cut) + ' CT</div>'
      : '<div class="sc-pill live"><i></i>LIVE</div><div class="sc-pillsub">locks ' + ct(g.cut) + ' CT</div>') + '</div></div>';
  if (!keys.length){
    el.innerHTML = head + '<div class="sc-empty"><b>Nothing to show yet</b><p>No wallet holds $250 or more on this game. The card fills in as money arrives and locks ' +
      ct(g.cut, true) + ' CT.</p></div><div class="sc-foot"><b>Context, not a bet.</b> ' + g.coverage.markets_read + ' market read, ' + g.coverage.markets_missed +
      ' missed. Ledger refreshed ' + ct(g.ledger_run_at) + ' CT.</div>';
    return;
  }
  el.innerHTML = head + '<div class="sc-ctl"><div class="vseg" data-k="group" role="tablist" aria-label="Market"><i class="v-pill"></i>' +
    GROUPS.map(function(x){ return '<button type="button" data-v="' + x[0] + '"' + (g.markets[x[0]] ? '' : ' disabled') + (x[0] === st.group ? ' class="on"' : '') + '>' + x[1] + '</button>'; }).join('') +
    '</div><div class="vseg sm" data-k="variant" aria-label="History"><i class="v-pill"></i><button type="button" data-v="all" class="on">All history</button><button type="button" data-v="fwd">Forward only</button></div></div><div class="sc-body"></div>';
  var bodyEl = el.querySelector('.sc-body'), strips = [].slice.call(el.querySelectorAll('.vseg'));
  function paint(){ bodyEl.innerHTML = body(g, st); }
  paint(); strips.forEach(function(s){ rail(s, false); });
  el.addEventListener('click', function(e){
    var b = e.target.closest('.vseg > button'), box = e.target.closest('.sc-box');
    if (b && !b.disabled){
      var strip = b.parentNode;
      [].forEach.call(strip.children, function(c){ c.classList.toggle('on', c === b); });
      st[strip.dataset.k] = b.dataset.v; if (strip.dataset.k === 'group') st.side = null;
      rail(strip, true); paint();
    } else if (box){ st.side = box.dataset.side; paint(); }
  });
  el._repaint = function(){ paint(); strips.forEach(function(s){ rail(s, false); }); };
}

window.SideCard = {mount: mount};
})();
