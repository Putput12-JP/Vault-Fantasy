/* Puts the V2 Sharps and Following pages inside the Sharp Money Sharps and Following tabs.
   Loaded by both shells (sharp-money/index.html and sharp-money/new/index.html) after side-cards.js and following.js. It replaces the
   two page mounts those files expose (mountPage and the React Page wrapper) with a frame that holds sharps-v2/index.html in embed mode,
   so V2 keeps its own styles and sheets and cannot leak into the shell. Everything else on those globals (the game section, the NBA
   page) is left alone. ?legacy=1 keeps the old pages for the tab (remembered as sessionStorage sm-legacy). */
(function () {
  'use strict';
  try {
    if (/[?&]legacy=1/.test(location.search)) sessionStorage.setItem('sm-legacy', '1');
    if (sessionStorage.getItem('sm-legacy') === '1') return;
  } catch (e) {}
  var me = document.currentScript, SRC = me && me.src ? new URL('index.html', me.src).href : 'sharps-v2/index.html';
  var LABEL = { sharps: 'Sharps', following: 'Following' };
  function theme() { try { var t = document.documentElement.dataset.theme; return t === 'light' || t === 'dark' ? t : ''; } catch (e) { return ''; } }
  function frame(el, route) {
    el.textContent = '';
    var f = document.createElement('iframe');
    f.src = SRC + '?embed=1#' + route;
    f.title = LABEL[route] + ' (V2)';
    f.style.cssText = 'display:block;width:100%;border:0;background:transparent;height:max(640px,calc(100vh - 170px))';
    f.addEventListener('load', function () {
      var t = theme();
      try { if (t) f.contentDocument.documentElement.setAttribute('data-theme', t); } catch (e) {}
    });
    el.appendChild(f);
  }
  function swap(name, route) {
    var o = window[name]; if (!o) return;
    o.mountPage = function (el) { frame(el, route); };
    if (o.Page) {   /* __smKit is defined later by the shell bundle, so it is read when the page renders */
      o.Page = function () {
        var U = window.__smKit().U, ref = U.useRef(null);
        U.useEffect(function () { if (ref.current) frame(ref.current, route); }, []);
        return U.createElement('div', { ref: ref });
      };
    }
  }
  swap('VaultSideCards', 'sharps');
  swap('VaultFollowing', 'following');
})();
