/* Puts the V2 Sharps and Following pages inside the Sharp Money Sharps and Following tabs, in the page itself (no frame), so they
   share the page's scroll, theme and layout like every other tab.
   Loaded by both shells (sharp-money/index.html and sharp-money/new/index.html) after side-cards.js and following.js. It replaces the
   two tab mounts those files expose (mountPage and the React Page wrapper) and leaves everything else on those globals (the game
   section, the NBA page) alone. V2's own header, route tabs and menu are not used here: the shell supplies the title and the tabs.
   The markup is taken from sharps-v2/index.html so the two stay the same page. ?legacy=1 keeps the old tabs for the browser tab
   (sessionStorage sm-legacy). */
(function () {
  'use strict';
  try {
    if (/[?&]legacy=1/.test(location.search)) sessionStorage.setItem('sm-legacy', '1');
    if (sessionStorage.getItem('sm-legacy') === '1') return;
  } catch (e) {}
  var me = document.currentScript, BASE = me && me.src ? new URL('./', me.src).href : 'sharps-v2/';
  var V = { css: 27, core: 6, sharps: 8, following: 3, record: 10 };
  var tpl = null, assets = null, pending = null;
  /* A wallet link on the Sharps tab points at #following/acct/<sport>/<wallet>, an address the Sharp Money shell does not know (it would land
     on the plays tab). Take the shell to its Following tab and open that wallet's popup there. */
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest && e.target.closest('a[href^="#following/acct/"]');
    if (!a || !a.closest('.sv2-root')) return;
    if (window.SV2 && typeof window.SV2.openAccount === 'function') return;   /* the Following page is mounted and opens it itself */
    e.preventDefault(); e.stopPropagation();
    pending = a.getAttribute('href'); location.hash = '#following';
  }, true);
  /* the one slim line inside a tab: freshness on the left, info and refresh on the right. Same ids as the standalone header, so core drives it unchanged. */
  var ICON_INFO = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 11v5.5M12 7.6v.2" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';
  var ICON_RF = '<svg class="sv2-rf-i" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20 12a8 8 0 1 1-2.4-5.7M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var HD = '<header class="sv2-hd sv2-hd--bar" id="sv2-hd" data-info="closed"><div class="sv2-hbar">' +
    '<div class="sv2-hbar-t"><p class="sv2-fresh" id="sv2-fresh" aria-label="Data freshness"><span class="sv2-sr">Loading</span></p><p class="sv2-context" id="sv2-context"></p></div>' +
    '<div class="sv2-hd-actions">' +
    '<button type="button" class="sv2-ibtn sv2-press sv2-press-btn" id="sv2-info-btn" aria-expanded="false" aria-controls="sv2-info" aria-label="How to read this">' + ICON_INFO + '</button>' +
    '<button type="button" class="sv2-ibtn sv2-rf sv2-press sv2-press-btn" id="sv2-refresh" data-state="idle" aria-label="Refresh">' + ICON_RF + '<span class="sv2-spinner xs" aria-hidden="true"></span><span class="sv2-rf-t">Refresh</span></button>' +
    '</div></div><p class="sv2-guard" id="sv2-guard" role="status" hidden></p>' +
    '<div class="sv2-info" id="sv2-info" role="region" aria-label="How to read this" hidden></div></header>';

  function loadTemplate() {
    if (tpl) return Promise.resolve(tpl);
    return fetch(BASE + 'index.html?v=' + V.css).then(function (r) { return r.ok ? r.text() : ''; }).then(function (t) {
      var d = new DOMParser().parseFromString(t, 'text/html');
      var main = d.getElementById('sv2-main');
      if (!main) throw new Error('V2 template missing');
      var wrap = main.querySelector('.sv2-wrap');
      tpl = { hd: HD, pages: wrap ? wrap.innerHTML.replace(/<noscript>[\s\S]*?<\/noscript>/g, '') : main.innerHTML };
      return tpl;
    });
  }
  function script(src) {
    return new Promise(function (ok, bad) { var s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = bad; document.head.appendChild(s); });
  }
  function loadAssets() {
    if (assets) return assets;
    if (!document.getElementById('sv2-css')) {
      var l = document.createElement('link'); l.id = 'sv2-css'; l.rel = 'stylesheet'; l.href = BASE + 'sv2.css?v=' + V.css; document.head.appendChild(l);
    }
    assets = script(BASE + 'sv2-core.js?v=' + V.core).then(function () { return script(BASE + 'sv2-sharps.js?v=' + V.sharps); })
      .then(function () { return script(BASE + 'sv2-following.js?v=' + V.following); })
      .then(function () { return script(BASE + 'sv2-record.js?v=' + V.record); });
    assets.catch(function () { assets = null; });
    return assets;
  }
  /* the sheet host is shared and lives on the body, so a position:fixed sheet is never trapped inside a host container */
  function sheetHost() {
    if (document.getElementById('sv2-sheet-host')) return;
    var w = document.createElement('div'); w.className = 'sv2-root sv2'; w.innerHTML = '<div class="sv2-sheet-host" id="sv2-sheet-host"></div>';
    document.body.appendChild(w);
  }
  function mount(el, route, sport) {
    el.textContent = '';
    var root = document.createElement('div'); root.className = 'sv2-root sv2 sv2-embedded'; root.innerHTML = '<p class="sv2-empty-line" style="padding:16px 0;color:var(--sv2-mut)">Loading</p>';
    el.appendChild(root);
    Promise.all([loadTemplate(), loadAssets()]).then(function (r) {
      if (!document.contains(root)) return;                              /* the shell moved on to another tab while this loaded */
      var t = r[0];
      /* the shell's phone layout (new/) takes the Apple style; the desktop layout takes the default one. Not stored: V2's own page keeps its setting. */
      document.documentElement.setAttribute('data-sv2-skin', /\/new\//.test(location.pathname) ? 'apple' : 'default');
      root.innerHTML = t.hd + '<main id="sv2-main" tabindex="-1">' + t.pages + '</main><div class="sv2-sr" id="sv2-live" aria-live="polite" role="status"></div>';
      sheetHost();
      window.SV2.setSport(sport);            /* before boot, so the page's first paint already follows the host's sport */
      var start = pending; pending = null;
      window.SV2.boot(route, route === 'following' ? start : undefined);
      if (window.SV2.rec && window.SV2.rec.init) window.SV2.rec.init();   /* the Plays or Accounts | Record switch */
    }).catch(function () {
      root.innerHTML = '<p class="sv2-empty-line" style="padding:16px 0">Could not load this page. <a href="?legacy=1">Open the previous version</a></p>';
    });
  }
  /* The host's sport: the desktop React wrapper gets props.sport, the phone shell passes opts.sport. No sport (null) means the host
     has no sport chips for this page, so V2 keeps its own strip (the contract side-cards.js and following.js used: o.sport != null hides the strip). */
  function swap(name, route) {
    var o = window[name]; if (!o) return;
    o.mountPage = function (el, opts) { mount(el, route, opts && opts.sport != null ? opts.sport : null); };
    if (o.Page) {   /* __smKit is defined later by the shell bundle, so it is read when the page renders */
      o.Page = function (props) {
        var U = window.__smKit().U, ref = U.useRef(null), sport = props && props.sport != null ? props.sport : 'all';
        U.useEffect(function () { if (ref.current) mount(ref.current, route, sport); }, []);
        /* a chip change updates the mounted page in place (no remount, so scroll and open rows stay) */
        U.useEffect(function () { if (window.SV2 && window.SV2.setSport) window.SV2.setSport(sport); }, [sport]);
        return U.createElement('div', { ref: ref });
      };
    }
  }
  swap('VaultSideCards', 'sharps');
  swap('VaultFollowing', 'following');
})();
