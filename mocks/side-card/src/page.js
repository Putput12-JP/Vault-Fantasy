/* Mock gallery: every state is a real game from the sample. ?state=<id> shows one card. */
(function(){
var STATES = [
  {id:'proven',   ev:'nba-was-ind-2026-11-11', g:'ml',     cap:'Proven money, no play', note:'A proven wallet is on Wizards, but the side holds under 60% of the money, so the rule suggests nothing.'},
  {id:'star',     ev:'nba-den-mem-2026-11-11', g:'spread', cap:'Suggested units (the one play in the sample)', note:'Nuggets spread clears all four gates. The card shows the stored 3u, the price and why.'},
  {id:'total',    ev:'nba-den-mem-2026-11-11', g:'total',  cap:'Total selected', note:'Proven money on the Over without a play. The spread row above still shows its 3u.'},
  {id:'none',     ev:'nba-gsw-hou-2026-11-11', g:'ml',     cap:'No proven money (the common case today)', note:'Quiet climate. The balance bars still show where the money sits.'},
  {id:'losers',   ev:'nba-bos-tor-2026-11-11', g:'ml',     cap:'Loser-heavy side', note:'Five loser wallets on Celtics, one proven wallet on Raptors.'},
  {id:'excluded', ev:'nba-orl-uta-2026-11-11', g:'spread', cap:'Excluded-heavy side', note:'Most of the Magic spread money is excluded. It is hatched and never counted.'},
  {id:'frozen',   ev:'nba-cle-nyk-2026-11-11', g:'spread', frozen:1, cap:'Frozen at the lock', note:'Real card data. The sample has no frozen card yet, so the mock sets the frozen flag to show the locked state.'},
  {id:'thin',     ev:'nba-okc-lac-2026-11-13', g:'ml',     cap:'Two days out, thin money', note:'Only the moneyline has been read. Spread and Total wait as dashed rows.'},
  {id:'empty',    ev:'nba-mil-orl-2026-11-13', g:'ml',     cap:'Nothing read yet', note:'A game with no holders at $250 or more.'}
];
var q = new URLSearchParams(location.search), one = q.get('state'), th = q.get('theme');
if (th) document.documentElement.dataset.theme = th;
if (one) document.body.classList.add('single');
var grid = document.getElementById('grid'), cards = [];
STATES.forEach(function(s){
  if (one && one !== s.id) return;
  var g = JSON.parse(JSON.stringify(SIDE_SAMPLE.games.filter(function(x){ return x.ev === s.ev; })[0]));
  if (s.frozen){ g.frozen = true; }
  var cell = document.createElement('div'); cell.className = 'mk-cell'; cell.id = s.id;
  cell.innerHTML = '<p class="mk-cap"><b>' + s.cap + '</b>' + s.note + '</p><div class="sc"></div>';
  grid.appendChild(cell); SideCard.mount(cell.lastChild, g, {group: s.g}); cards.push(cell.lastChild);
});
var sl = document.getElementById('slate'); if (sl && !one) SideCard.slate(sl, SIDE_SAMPLE);
var tseg = document.getElementById('theme');
if (tseg){
  var cur = document.documentElement.dataset.theme || 'dark';
  [].forEach.call(tseg.querySelectorAll('button'), function(b){ b.classList.toggle('on', b.dataset.v === cur);
    b.onclick = function(){ document.documentElement.dataset.theme = b.dataset.v;
      [].forEach.call(tseg.querySelectorAll('button'), function(c){ c.classList.toggle('on', c === b); }); place(true); }; });
  var place = function(anim){ var on = tseg.querySelector('.on'), p = tseg.querySelector('.v-pill'); if (!anim) tseg.classList.add('rail-noanim');
    p.style.left = on.offsetLeft + 'px'; p.style.width = on.offsetWidth + 'px'; p.style.opacity = '1'; void p.offsetWidth; tseg.classList.remove('rail-noanim'); };
  place(false);
}
var mq = matchMedia('(max-width:767px)'), rp = function(){ cards.forEach(function(c){ c._repaint && c._repaint(); }); };
mq.addEventListener ? mq.addEventListener('change', rp) : mq.addListener(rp);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(rp);
})();
