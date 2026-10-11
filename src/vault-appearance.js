/* Vault Appearance: the Appearance panel shared by Sharp Money and Vault NBA.
   Source of truth is THIS file; each page inlines it (scripts/inline_appearance.py). Settings: Theme (System / Light / Dark /
   High contrast), Accent (hue slider + swatches), Background tint, Density. One key, 'vault-appearance', so both pages (same
   origin) share the choice. A page registers an adapter that knows how to paint ITS colours:
     VaultAppearance.init({ legacy(), apply(state, ctx), density:true|false })
   ctx = { resolved:'light'|'dark', contrast:bool, accent:'#rrggbb'|null, tint:0..1, hue:number|null, mix(color,amt) }.
   The module owns state, persistence, system-theme tracking and the panel; the adapter owns the page's own palette. */
(function(){
'use strict';
var KEY = 'vault-appearance', DEF = { theme:'system', hue:null, tint:0, density:'comfortable' };
var HUES = [['Blue',250],['Violet',275],['Pink',330],['Red',10],['Orange',30],['Gold',48],['Green',145],['Teal',175]];
var NAMES = [[15,'Red'],[40,'Orange'],[65,'Gold'],[100,'Lime'],[160,'Green'],[195,'Teal'],[225,'Cyan'],[262,'Blue'],[295,'Violet'],[335,'Pink'],[361,'Red']];
var A = null, S = null, el = null, mq = null, lastFocus = null;

function load(){ try{ var v = JSON.parse(localStorage.getItem(KEY)); if (v && typeof v === 'object') return v; }catch(e){} return null; }
function save(){ try{ localStorage.setItem(KEY, JSON.stringify(S)); }catch(e){} }
function clamp(n, a, b){ return Math.min(b, Math.max(a, n)); }
function hueName(h){ for (var i = 0; i < NAMES.length; i++) if (h < NAMES[i][0]) return NAMES[i][1]; return 'Red'; }

/* colour helpers: hsl -> hex, parse #hex / rgb() / rgba(), mix toward a hue */
function hsl2rgb(h, s, l){ h = ((h % 360) + 360) % 360 / 360; var q = l < .5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
  function f(t){ t = (t + 1) % 1; return t < 1/6 ? p + (q - p) * 6 * t : t < .5 ? q : t < 2/3 ? p + (q - p) * (2/3 - t) * 6 : p; }
  return [f(h + 1/3), f(h), f(h - 1/3)].map(function(v){ return Math.round(v * 255); }); }
function hex(rgb){ return '#' + rgb.map(function(v){ return ('0' + clamp(Math.round(v), 0, 255).toString(16)).slice(-2); }).join(''); }
function parse(c){ var m; c = String(c).trim();
  if ((m = /^#([0-9a-f]{3})$/i.exec(c))) return m[1].split('').map(function(x){ return parseInt(x + x, 16); });
  if ((m = /^#([0-9a-f]{6})/i.exec(c))) return [0, 2, 4].map(function(i){ return parseInt(m[1].substr(i, 2), 16); });
  if ((m = /^rgba?\(([^)]+)\)/.exec(c))) return m[1].split(/[ ,\/]+/).slice(0, 3).map(Number);
  return null; }
function lum(rgb){ var v = rgb.map(function(x){ x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; }

function resolved(){ return S.theme === 'light' ? 'light' : S.theme === 'system' ? (mq && mq.matches ? 'dark' : 'light') : 'dark'; }
function context(){
  var res = resolved(), h = S.hue, accent = null, tintRgb = null;
  if (h != null){ accent = hex(hsl2rgb(h, res === 'dark' ? .78 : .62, res === 'dark' ? .68 : .42)); }
  var tint = S.tint / 100;
  tintRgb = hsl2rgb(h == null ? 250 : h, .55, .5);
  return { resolved: res, contrast: S.theme === 'contrast', accent: accent, hue: h, tint: tint, density: S.density,
    ink: accent ? (lum(parse(accent)) > .4 ? '#0b0c0e' : '#ffffff') : null,
    /* mix a page colour toward the accent hue by tint (max ~12% at 100) */
    mix: function(c, amt){ var p = parse(c); if (!p) return c; var t = (amt == null ? tint : amt) * .12; return hex(p.map(function(v, i){ return v + (tintRgb[i] - v) * t; })); } };
}

function apply(){
  var ctx = context(), root = document.documentElement;
  if (ctx.contrast) root.dataset.contrast = 'high'; else delete root.dataset.contrast;
  root.dataset.density = S.density;
  if (A && A.apply) A.apply(S, ctx);
  try{ window.dispatchEvent(new CustomEvent('vault-appearance', { detail: { state: S, ctx: ctx } })); }catch(e){}
}
function set(patch, keepOpen){ for (var k in patch) S[k] = patch[k]; save(); apply(); if (el && keepOpen !== false) sync(); }

/* ── panel ── */
var CSS = '#va-root{position:fixed;inset:0;z-index:2147483000;display:none;align-items:flex-start;justify-content:center;padding:max(24px,5vh) 16px;overflow-y:auto;background:rgba(0,0,0,.5);-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px);font:14px/1.5 Geist,system-ui,-apple-system,"Segoe UI",sans-serif}'
+ '#va-root.on{display:flex}#va-root{--p:#fff;--t:#111;--t2:#6b6b6b;--bd:#e3e3e3;--c:#f6f6f6;--in:#111;--ino:#fff;color:var(--t)}'
+ '#va-root[data-m=dark]{--p:#151619;--t:#f3f4f6;--t2:#9a9ea8;--bd:#2a2c32;--c:#1c1d22;--in:#f3f4f6;--ino:#0b0c0e}'
+ '.va-card{width:min(640px,100%);background:var(--p);border:1px solid var(--bd);border-radius:18px;padding:26px 26px 22px;box-shadow:0 24px 80px rgba(0,0,0,.45);animation:va-in .22s cubic-bezier(.22,1,.36,1)}'
+ '@keyframes va-in{from{opacity:0;transform:translateY(8px) scale(.985)}}@media(prefers-reduced-motion:reduce){.va-card{animation:none}}'
+ '.va-top{display:flex;align-items:flex-start;gap:12px}.va-top h2{margin:0;font-size:22px;font-weight:600;letter-spacing:-.01em}.va-top p{margin:2px 0 0;color:var(--t2);font-size:13px}'
+ '.va-x{all:unset;box-sizing:border-box;margin-left:auto;width:32px;height:32px;border-radius:9999px;display:grid;place-items:center;cursor:pointer;color:var(--t2)}.va-x:hover{background:var(--c);color:var(--t)}'
+ '.va-lab{margin:22px 4px 8px;font-size:13px;color:var(--t2)}'
+ '.va-sec{background:var(--c);border-radius:16px;padding:16px 16px 14px}.va-sec h3{margin:0;font-size:14px;font-weight:600}.va-sec .d{margin:2px 0 12px;color:var(--t2);font-size:13px}'
+ '.va-hr{height:1px;background:var(--bd);margin:14px 0}'
+ '.va-row{display:flex;align-items:center;gap:16px}.va-row>div:first-child{flex:1;min-width:0}.va-row .d{margin:2px 0 0}'
+ '.va-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}@media(max-width:520px){.va-grid{grid-template-columns:repeat(2,1fr)}}'
+ '.va-opt{all:unset;box-sizing:border-box;display:block;cursor:pointer;text-align:left}.va-opt .pv{display:block;aspect-ratio:1.45;border-radius:12px;border:1.5px solid var(--bd);overflow:hidden;position:relative}'
+ '.va-opt[aria-pressed=true] .pv{border:2px solid var(--t)}.va-opt .nm{display:block;margin:7px 2px 0;font-size:13px;color:var(--t2)}.va-opt[aria-pressed=true] .nm{color:var(--t);font-weight:500}'
+ '.va-opt:focus-visible,.va-sw:focus-visible,.va-x:focus-visible,.va-btn:focus-visible{outline:2px solid var(--t);outline-offset:2px}'
+ '.pv i{position:absolute;display:block;border-radius:3px}'
+ '.va-hue{-webkit-appearance:none;appearance:none;width:100%;height:10px;border-radius:9999px;outline:none;margin:6px 0 0;background:linear-gradient(90deg,hsl(0 70% 62%),hsl(45 70% 55%),hsl(95 60% 55%),hsl(165 60% 50%),hsl(215 75% 62%),hsl(275 65% 68%),hsl(330 65% 65%),hsl(360 70% 62%))}'
+ '.va-hue::-webkit-slider-thumb,.va-rng::-webkit-slider-thumb{-webkit-appearance:none;width:20px;height:20px;border-radius:50%;background:#fff;border:1px solid rgba(0,0,0,.25);box-shadow:0 1px 4px rgba(0,0,0,.3);cursor:pointer}'
+ '.va-hue::-moz-range-thumb,.va-rng::-moz-range-thumb{width:18px;height:18px;border-radius:50%;background:#fff;border:1px solid rgba(0,0,0,.25);box-shadow:0 1px 4px rgba(0,0,0,.3);cursor:pointer}'
+ '.va-rng{-webkit-appearance:none;appearance:none;width:200px;max-width:42vw;height:6px;border-radius:9999px;outline:none;background:linear-gradient(90deg,var(--in) var(--v,0%),var(--bd) var(--v,0%))}'
+ '.va-hv{display:flex;align-items:center;justify-content:flex-end;font-size:13px;color:var(--t2);margin-bottom:4px}'
+ '.va-sws{display:flex;gap:12px;margin-top:14px;flex-wrap:wrap}.va-sw{all:unset;box-sizing:border-box;width:28px;height:28px;border-radius:50%;cursor:pointer;position:relative}'
+ '.va-sw[aria-pressed=true]{box-shadow:0 0 0 2px var(--c),0 0 0 4px var(--t)}.va-sw.def{background:var(--p);border:1.5px solid var(--bd)}.va-sw.def::after{content:"";position:absolute;left:5px;right:5px;top:50%;height:1.5px;background:var(--t2);transform:rotate(-45deg)}'
+ '.va-btn{all:unset;box-sizing:border-box;cursor:pointer;padding:7px 12px;border-radius:9px;border:1px solid var(--bd);font-size:13px;color:var(--t)}.va-btn:hover{background:var(--c)}'
+ '.va-foot{display:flex;justify-content:flex-end;margin-top:16px}'
+ '.va-seg{display:inline-flex;gap:2px;padding:2px;border-radius:10px;background:var(--p);border:1px solid var(--bd)}.va-seg button{all:unset;box-sizing:border-box;cursor:pointer;padding:6px 12px;border-radius:8px;font-size:13px;color:var(--t2)}.va-seg button[aria-pressed=true]{background:var(--in);color:var(--ino)}'
+ '.va-seg button:focus-visible{outline:2px solid var(--t);outline-offset:1px}';

/* tiny theme thumbnails: sidebar strip, message bubble, input bar */
function thumb(m, extra){
  var P = { light:['#f1f1f3','#fafafc','#dfe6f5','#d9d9de','#e8e8ec'], dark:['#16171a','#0d0e10','#1d2531','#33353c','#1b1c20'], contrast:['#141414','#000','#000','#9a9a9a','#000'] }[m];
  var line = m === 'contrast' ? '1.5px solid #fff' : '0';
  var body = '<span class="pv" style="background:' + P[1] + (extra || '') + '">'
    + '<i style="left:0;top:0;bottom:0;width:22%;background:' + P[0] + '"></i>'
    + '<i style="left:6%;top:14%;width:10%;height:5%;background:' + P[3] + '"></i><i style="left:6%;top:26%;width:8%;height:5%;background:' + P[3] + '"></i>'
    + '<i style="right:8%;top:16%;width:42%;height:15%;border-radius:8px;background:' + P[2] + ';border:' + line + '"></i>'
    + '<i style="left:30%;top:46%;width:44%;height:5%;background:' + P[3] + '"></i><i style="left:30%;top:58%;width:34%;height:5%;background:' + P[3] + '"></i>'
    + '<i style="left:28%;right:6%;bottom:9%;height:17%;border-radius:8px;background:' + P[4] + ';border:' + (m === 'contrast' ? '1.5px solid #fff' : '1px solid ' + P[3]) + '"></i>'
    + '<i style="right:10%;bottom:14%;width:7%;height:7%;border-radius:50%;background:#6aa8ff"></i></span>';
  return body;
}
function systemThumb(){
  return '<span class="pv" style="background:#fafafc"><span style="position:absolute;inset:0;clip-path:polygon(100% 0,100% 100%,0 100%)">' + thumb('dark', ';border:0;position:absolute;inset:0;width:100%;aspect-ratio:auto;height:100%') + '</span>'
    + '<span style="position:absolute;inset:0;clip-path:polygon(0 0,100% 0,0 100%)">' + thumb('light', ';border:0;position:absolute;inset:0;width:100%;aspect-ratio:auto;height:100%') + '</span></span>';
}

function html(){
  var th = [['system', 'System'], ['light', 'Light'], ['dark', 'Dark'], ['contrast', 'High contrast']].map(function(o){
    return '<button type="button" class="va-opt" data-theme-opt="' + o[0] + '" aria-pressed="false">' + (o[0] === 'system' ? systemThumb() : thumb(o[0])) + '<span class="nm">' + o[1] + '</span></button>'; }).join('');
  var sw = '<button type="button" class="va-sw def" data-hue="" aria-label="Default accent" title="Default" aria-pressed="false"></button>'
    + HUES.map(function(h){ return '<button type="button" class="va-sw" data-hue="' + h[1] + '" aria-label="' + h[0] + '" title="' + h[0] + '" style="background:hsl(' + h[1] + ' 72% 66%)" aria-pressed="false"></button>'; }).join('');
  return '<div class="va-card" role="dialog" aria-modal="true" aria-labelledby="va-h">'
    + '<div class="va-top"><div><h2 id="va-h">Appearance</h2><p>How Vault looks on this device.</p></div><button type="button" class="va-x" data-close aria-label="Close"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div>'
    + '<div class="va-sec" style="margin-top:20px"><h3>Theme</h3><p class="d">System follows your device. High contrast uses stronger edges and text.</p><div class="va-grid" role="group" aria-label="Theme">' + th + '</div></div>'
    + '<div class="va-lab">Color</div><div class="va-sec"><h3>Accent</h3><p class="d">Buttons, links and highlights.</p>'
    + '<div class="va-hv" id="va-hn"></div><input class="va-hue" id="va-hue" type="range" min="0" max="360" step="1" aria-label="Accent hue"><div class="va-sws" role="group" aria-label="Accent swatches">' + sw + '</div>'
    + '<div class="va-hr"></div><div class="va-row"><div><h3>Background tint</h3><p class="d">How much of the accent shows in backgrounds.</p></div><input class="va-rng" id="va-tint" type="range" min="0" max="100" step="1" aria-label="Background tint"><span id="va-tv" style="width:38px;text-align:right;color:var(--t2);font-size:13px"></span></div></div>'
    + (A && A.density !== false ? '<div class="va-lab">Layout</div><div class="va-sec"><div class="va-row"><div><h3>Density</h3><p class="d">Space between rows and inside cards.</p></div><div class="va-seg" role="group" aria-label="Density"><button type="button" data-dens="comfortable" aria-pressed="false">Comfortable</button><button type="button" data-dens="compact" aria-pressed="false">Compact</button></div></div></div>' : '')
    + '<div class="va-foot"><button type="button" class="va-btn" data-reset>Reset to defaults</button></div></div>';
}

function sync(){
  if (!el) return;
  el.dataset.m = resolved();
  [].forEach.call(el.querySelectorAll('[data-theme-opt]'), function(b){ b.setAttribute('aria-pressed', String(b.dataset.themeOpt === S.theme)); });
  var h = S.hue, hr = el.querySelector('#va-hue');
  hr.value = h == null ? 250 : h;
  el.querySelector('#va-hn').textContent = h == null ? 'Default' : hueName(h) + ' ' + Math.round(h) + '°';
  [].forEach.call(el.querySelectorAll('.va-sw'), function(b){ b.setAttribute('aria-pressed', String(h == null ? b.dataset.hue === '' : b.dataset.hue !== '' && +b.dataset.hue === Math.round(h))); });
  var t = el.querySelector('#va-tint'); t.value = S.tint; t.style.setProperty('--v', S.tint + '%'); el.querySelector('#va-tv').textContent = S.tint + '%';
  [].forEach.call(el.querySelectorAll('[data-dens]'), function(b){ b.setAttribute('aria-pressed', String(b.dataset.dens === S.density)); });
}

function build(){
  if (!document.getElementById('va-style')){ var st = document.createElement('style'); st.id = 'va-style'; st.textContent = CSS; document.head.appendChild(st); }
  el = document.createElement('div'); el.id = 'va-root'; el.innerHTML = html(); document.body.appendChild(el);
  el.addEventListener('mousedown', function(e){ if (e.target === el) close(); });
  el.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('button'); if (!b) return;
    if (b.hasAttribute('data-close')) return close();
    if (b.hasAttribute('data-reset')) return set({ theme: DEF.theme, hue: DEF.hue, tint: DEF.tint, density: DEF.density });
    if (b.dataset.themeOpt) return set({ theme: b.dataset.themeOpt });
    if (b.classList.contains('va-sw')) return set({ hue: b.dataset.hue === '' ? null : +b.dataset.hue });
    if (b.dataset.dens) return set({ density: b.dataset.dens });
  });
  el.querySelector('#va-hue').addEventListener('input', function(e){ set({ hue: +e.target.value }); });
  el.querySelector('#va-tint').addEventListener('input', function(e){ set({ tint: +e.target.value }); });
  el.addEventListener('keydown', function(e){
    if (e.key === 'Escape'){ e.stopPropagation(); return close(); }
    if (e.key !== 'Tab') return;
    var f = [].filter.call(el.querySelectorAll('button,input'), function(x){ return x.offsetParent !== null; }); if (!f.length) return;
    var a = f[0], z = f[f.length - 1];
    if (e.shiftKey && document.activeElement === a){ e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z){ e.preventDefault(); a.focus(); }
  });
}
function open(){ if (!el) build(); lastFocus = document.activeElement; sync(); el.classList.add('on'); var f = el.querySelector('[aria-pressed=true]'); if (f) f.focus(); }
function close(){ if (!el) return; el.classList.remove('on'); if (lastFocus && lastFocus.focus) lastFocus.focus(); }

function init(adapter){
  A = adapter || {};
  var saved = load();
  S = { theme: DEF.theme, hue: DEF.hue, tint: DEF.tint, density: DEF.density };
  if (saved){ for (var k in DEF) if (saved[k] !== undefined) S[k] = saved[k]; }
  else { var lg = A.legacy && A.legacy(); if (lg === 'light' || lg === 'dark') S.theme = lg; }   /* keep the theme people already chose */
  S.tint = clamp(+S.tint || 0, 0, 100); if (S.hue != null) S.hue = clamp(+S.hue, 0, 360);
  if (['system', 'light', 'dark', 'contrast'].indexOf(S.theme) < 0) S.theme = 'system';
  if (S.density !== 'compact') S.density = 'comfortable';
  try{ mq = matchMedia('(prefers-color-scheme: dark)'); (mq.addEventListener ? mq.addEventListener('change', function(){ if (S.theme === 'system'){ apply(); sync(); } }) : mq.addListener(function(){ if (S.theme === 'system'){ apply(); sync(); } })); }catch(e){}
  apply();
}
window.VaultAppearance = { init: init, open: open, close: close, reapply: function(){ if (S) apply(); }, state: function(){ return S; }, context: function(){ return S && context(); } };
})();
