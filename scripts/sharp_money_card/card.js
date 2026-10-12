/* Sharp Money "Every line" share card. Lives inside sharp-money/index.html between the vsc markers,
   inserted by patch_index.py. Runs in the bundle's scope: U = React, Il = readGame, Et = no-vig win prob. */
var VSC_CSS = `
.vsc{--bg:#0b0b0d;--line:rgba(255,255,255,.08);--ink:#f4f4f6;--mute:#8b8b95;--dim:#5d5d66;--a:#4f8cff;--b:#f2b84b;--over:#2fe08a;--under:#8c7bff;--sharp:#46e08c;--loss:#ff6b6b;--amber:#f2b84b;
  position:relative;overflow:hidden;border-radius:24px;background:var(--bg);color:var(--ink);border:1px solid var(--line);max-width:none;margin:0;width:100%;container-type:inline-size;
  font:500 15px/1.35 Inter,-apple-system,"SF Pro Display",system-ui,sans-serif;-webkit-font-smoothing:antialiased;text-align:left}
.vsc *{box-sizing:border-box;margin:0}
.vsc .glow{position:absolute;inset:0 0 auto 0;height:400px;pointer-events:none;background:radial-gradient(300px 200px at 50% 40%,rgba(47,224,138,.18),transparent 70%),radial-gradient(260px 190px at 0% 0%,rgba(79,140,255,.22),transparent 70%),radial-gradient(260px 190px at 100% 0%,rgba(242,184,75,.18),transparent 70%)}
.vsc .glow.q{background:radial-gradient(260px 190px at 0% 0%,rgba(79,140,255,.18),transparent 70%),radial-gradient(260px 190px at 100% 0%,rgba(242,184,75,.14),transparent 70%)}
.vsc .in{position:relative;padding:18px 18px 16px}
.vsc .bar{display:flex;justify-content:flex-end;margin-bottom:8px}
.vsc .share{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:rgba(255,255,255,.07);color:var(--ink);font:600 12px/1 Inter,system-ui,sans-serif;padding:8px 12px;border-radius:99px;cursor:pointer;transition:transform 500ms cubic-bezier(.34,1.56,.64,1),background .15s}
.vsc .share:hover{background:rgba(255,255,255,.13)}
.vsc .share:active{transform:scale(.94);transition:transform 80ms ease-out}
.vsc .share[disabled]{opacity:.6;cursor:progress}
.vsc .hd{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:10px}
.vsc .tm{display:flex;align-items:center;gap:10px;min-width:0}
.vsc .tm.r{flex-direction:row-reverse;text-align:right}
.vsc .tm b{display:block;font-size:17px;font-weight:700;letter-spacing:-.01em;line-height:1.15}
.vsc .tm small{display:block;font-size:11px;color:var(--mute);margin-top:1px}
.vsc .lg{width:56px;height:56px;object-fit:contain;flex:none}
.vsc .mono{width:56px;height:56px;border-radius:16px;flex:none;display:grid;place-items:center;font-weight:800;font-size:15px;color:#fff;letter-spacing:-.02em}
.vsc .at{font-size:11px;color:var(--dim);text-align:center;line-height:1.35}
.vsc .at b{display:block;color:var(--mute);font-weight:600;font-size:12px}
.vsc .verdict{margin:16px 0 0;text-align:center}
.vsc .eyebrow{display:inline-flex;align-items:center;gap:7px;font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--sharp)}
.vsc .eyebrow i{width:6px;height:6px;border-radius:50%;background:var(--sharp);box-shadow:0 0 10px var(--sharp)}
.vsc .eyebrow.q{color:var(--mute)} .vsc .eyebrow.q i{background:var(--dim);box-shadow:none}
.vsc .pick{font-size:60px;line-height:1.02;font-weight:800;letter-spacing:-.04em;margin-top:8px}
.vsc .pick span{font-size:inherit;letter-spacing:inherit;margin-left:.22em}
.vsc .pick.sm{font-size:44px}
.vsc .why{font-size:12px;color:var(--mute);margin-top:6px}
.vsc .proof{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:4px;text-align:center}
.vsc .pf{padding:10px 11px;border-radius:14px;background:rgba(255,255,255,.045);border:1px solid var(--line)}
.vsc .pf.on{border-color:rgba(70,224,140,.35)}
.vsc .pf em{display:flex;align-items:center;justify-content:center;gap:6px;font-style:normal;font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);margin-bottom:5px}
.vsc .pf.on em{color:var(--sharp)}
.vsc .pf em i{width:6px;height:6px;border-radius:50%;background:var(--dim);flex:none}
.vsc .pf.on em i{background:var(--sharp)}
.vsc .pf strong{display:block;font-size:17px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.vsc .pf small{display:block;font-size:11px;color:var(--mute);margin-top:2px}
.vsc .sec{display:flex;justify-content:space-between;align-items:baseline;margin:20px 4px 8px;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim)}
.vsc .sec span:last-child{letter-spacing:0;text-transform:none}
.vsc .sec i{display:inline-block;width:2px;height:9px;background:#fff;border-radius:2px;vertical-align:-1px;margin-right:5px}
.vsc .mkts{display:flex;flex-direction:column;gap:10px}
.vsc .mk{border-radius:20px;border:1px solid var(--line);background:linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.015));padding:14px 14px 12px}
.vsc .mk.hot{border-color:rgba(70,224,140,.32);box-shadow:0 0 0 1px rgba(70,224,140,.08),0 12px 40px -18px rgba(70,224,140,.35)}
.vsc .mh{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:8px}
.vsc .mh h4{font-size:14px;font-weight:700}
.vsc .pill{font-size:10px;font-weight:800;letter-spacing:.08em;padding:4px 8px;border-radius:99px;text-transform:uppercase;white-space:nowrap}
.vsc .pill.g{color:#06130c;background:var(--sharp)}
.vsc .pill.b{color:#e8f0ff;background:rgba(79,140,255,.28);border:1px solid rgba(79,140,255,.5)}
.vsc .pill.y{color:#2a1c00;background:var(--amber)}
.vsc .pill.q{color:var(--mute);background:rgba(255,255,255,.06)}
.vsc .body{display:grid;grid-template-columns:minmax(72px,auto) minmax(0,1fr) minmax(72px,auto);gap:12px;align-items:center}
.vsc .px .ln{font-size:22px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1.05;white-space:nowrap}
.vsc .px .pr{font-size:12px;color:var(--mute);margin-top:2px;font-variant-numeric:tabular-nums}
.vsc .px.r{text-align:right}
.vsc .mid .nums{display:flex;justify-content:space-between;align-items:baseline;font-variant-numeric:tabular-nums;margin-bottom:6px}
.vsc .mid .nums b{font-size:20px;font-weight:800;letter-spacing:-.02em}
.vsc .mid .nums span{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim)}
.vsc .track{position:relative;height:14px;display:flex;gap:3px}
.vsc .track>span{display:block;height:100%;border-radius:99px}
.vsc .tick{position:absolute;top:-4px;bottom:-4px;width:2px;background:#fff;border-radius:2px;box-shadow:0 0 0 1px rgba(0,0,0,.45);transform:translateX(-1px)}
.vsc .bets{display:flex;justify-content:space-between;margin-top:7px;font-size:11px;color:var(--mute);font-variant-numeric:tabular-nums}
.vsc .nosp{font-size:12px;color:var(--dim);text-align:center}
.vsc .move{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid var(--line);font-size:12px;color:var(--mute);font-variant-numeric:tabular-nums;flex-wrap:wrap}
.vsc .move .arrow{color:var(--ink);font-weight:700}
.vsc .move .d{margin-left:auto;font-weight:700;text-align:right}
.vsc .up{color:var(--sharp)} .vsc .flat{color:var(--dim)} .vsc .mv{color:var(--ink)} .vsc .warn{color:var(--amber)}
.vsc .ex{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.vsc .chips{display:flex;flex-wrap:wrap;gap:5px;align-content:flex-start;align-items:flex-start}
.vsc .chips.r{justify-content:flex-end}
.vsc .chip{font-size:11px;font-weight:600;padding:3px 8px;border-radius:99px;background:rgba(255,255,255,.06);font-variant-numeric:tabular-nums;border:1px solid transparent;white-space:nowrap}
.vsc .chip.sharp{color:var(--sharp);background:rgba(70,224,140,.12);border-color:rgba(70,224,140,.28)}
.vsc .chip.loss{color:var(--loss);background:rgba(255,107,107,.1);border-color:rgba(255,107,107,.25)}
.vsc .chip.none{color:var(--dim);background:none;padding-left:0;padding-right:0}
.vsc .note{margin-top:12px;padding:10px 12px;border-radius:12px;background:rgba(255,255,255,.035);font-size:11.5px;line-height:1.45;color:var(--mute)}
.vsc .brand{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:14px;padding:0 4px}
.vsc .brand b{font-size:13px;letter-spacing:.14em;font-weight:800}
.vsc .brand span{font-size:11px;color:var(--dim)}
.vsc .top{display:grid;grid-template-columns:1fr auto 1fr;grid-template-areas:"away at home" "verdict verdict verdict" "proof proof proof";align-items:center;gap:10px}
.vsc .top>.tm{grid-area:away}.vsc .top>.tm.r{grid-area:home}.vsc .top>.at{grid-area:at}.vsc .top>.verdict{grid-area:verdict}.vsc .top>.proof{grid-area:proof}
.vsc .wh,.vsc .ab{display:none}
@container (min-width:640px){
  .vsc{border-radius:20px}
  .vsc .in{padding:12px 16px 10px}
  .vsc .top{grid-template-columns:150px minmax(0,1fr) 150px;grid-template-areas:"away verdict home" "proof proof proof";gap:12px;align-items:start}
  .vsc .at{display:none}.vsc .wh{display:inline}
  .vsc .tm{flex-direction:column;align-items:flex-start;gap:6px}.vsc .tm.r{flex-direction:column;align-items:flex-end}.vsc .tm>div{margin:0}
  .vsc .tm b{font-size:15px}
  .vsc .lg,.vsc .mono{width:56px;height:56px}
  .vsc .verdict{margin:0}
  .vsc .pick{font-size:48px;margin-top:2px}.vsc .pick.sm{font-size:38px}.vsc .why{font-size:13px}
  .vsc .why{margin-top:4px}
  .vsc .proof{margin-top:0;gap:10px}
  .vsc .pf{padding:9px 13px;border-radius:14px}.vsc .pf em{margin-bottom:5px;font-size:10.5px}.vsc .pf strong{font-size:19px}.vsc .pf small{font-size:12px}.vsc .pf small{margin-top:1px}
  .vsc .sec{margin:8px 4px 5px}
  .vsc .mkts{gap:7px}
  .vsc .mk{display:grid;grid-template-columns:auto minmax(0,1fr);grid-template-areas:"mh mv" "body body" "ex ex" "note note";row-gap:8px;align-items:center;padding:10px 16px;border-radius:18px}
  .vsc .mh{grid-area:mh;margin:0;gap:10px;justify-content:flex-start}.vsc .mh h4{font-size:16px}
  .vsc .move{grid-area:mv;margin:0;padding:0;border:0;justify-content:flex-end;font-size:12px;gap:6px}
  .vsc .move .d{margin-left:0;text-align:right}
  .vsc .body{grid-area:body;grid-template-columns:84px minmax(0,1fr) 84px;gap:20px}
  .vsc .px .ln{font-size:24px}.vsc .px .pr{font-size:12px}
  .vsc .mid .nums{margin-bottom:4px}.vsc .mid .nums b{font-size:21px}.vsc .track{height:18px}.vsc .tick{top:-5px;bottom:-5px;width:3px}.vsc .bets{margin-top:7px;font-size:12px}
  .vsc .ex{grid-area:ex;grid-template-columns:1fr 1fr;gap:12px;margin:0}
  .vsc .chips{justify-content:flex-start;flex-wrap:wrap;gap:4px}.vsc .chips.r{justify-content:flex-end}
  .vsc .chip{font-size:12px;padding:3px 9px}
  .vsc .note{grid-area:note;margin-top:8px;padding:6px 10px;font-size:11px}
  .vsc .brand{margin-top:6px;padding-right:96px;min-height:29px}
  .vsc .bar{position:absolute;right:16px;bottom:4px;margin:0;z-index:2}.vsc .in{padding-bottom:4px}
  .vsc .share{padding:6px 11px}
}
@container (min-width:400px) and (max-width:639px){
  .vsc.fit{border-radius:18px}
  .vsc.fit .in{padding:10px 12px 8px}
  .vsc.fit .top{grid-template-columns:76px minmax(0,1fr) 76px;grid-template-areas:"away verdict home" "proof proof proof";gap:8px;align-items:start}
  .vsc.fit .at{display:none}.vsc.fit .wh{display:inline}
  .vsc.fit .tm,.vsc.fit .tm.r{flex-direction:column;gap:4px;text-align:center;align-items:center}
  .vsc.fit .tm b{font-size:12px}.vsc.fit .tm small{display:none}
  .vsc.fit .lg,.vsc.fit .mono{width:44px;height:44px}
  .vsc.fit .verdict{margin:0}
  .vsc.fit .eyebrow{font-size:10px}
  .vsc.fit .pick{font-size:34px;margin-top:2px}.vsc.fit .pick.sm{font-size:26px}
  .vsc.fit .why{font-size:11px;margin-top:2px}
  .vsc.fit .proof{margin-top:0;gap:6px}
  .vsc.fit .pf{padding:6px 8px;border-radius:10px}.vsc.fit .pf em{font-size:9px;margin-bottom:2px}.vsc.fit .pf strong{font-size:14px}.vsc.fit .pf small{display:none}
  .vsc.fit .sec{display:none}
  .vsc.fit .mkts{gap:6px;margin-top:8px}
  .vsc.fit .mk{display:grid;grid-template-columns:auto minmax(0,1fr);grid-template-areas:"mh mv" "body body" "ex ex";row-gap:6px;align-items:center;padding:8px 10px;border-radius:14px}
  .vsc.fit .mh{grid-area:mh;margin:0;gap:8px;justify-content:flex-start}.vsc.fit .mh h4{font-size:13px}.vsc.fit .pill{font-size:9px;padding:3px 7px}
  .vsc.fit .move{grid-area:mv;margin:0;padding:0;border:0;justify-content:flex-end;font-size:10.5px;gap:5px}.vsc.fit .move .d{margin-left:0}
  .vsc.fit .body{grid-area:body;grid-template-columns:54px minmax(0,1fr) 54px;gap:8px}
  .vsc.fit .px .ln{font-size:17px}.vsc.fit .px .pr{font-size:10px;max-width:54px}
  .vsc.fit .mid .nums{margin-bottom:3px}.vsc.fit .mid .nums b{font-size:15px}.vsc.fit .track{height:9px}.vsc.fit .tick{top:-3px;bottom:-3px}.vsc.fit .bets{margin-top:4px;font-size:10px}
  .vsc.fit .ex{grid-area:ex;margin:0;gap:6px}
  .vsc.fit .chips{flex-wrap:nowrap;overflow:hidden;gap:4px}.vsc.fit .chip{font-size:10px;padding:2px 6px}
  .vsc.fit .note{grid-area:auto;margin-top:6px;padding:5px 8px;font-size:10.5px}
  .vsc.fit .brand{margin-top:6px;padding-right:84px;min-height:28px}.vsc.fit .in{padding-bottom:4px}.vsc.fit .brand span{display:none}
  .vsc.fit .bar{position:absolute;right:12px;bottom:3px;margin:0;z-index:2}
  .vsc.fit .share{padding:5px 10px;font-size:11px}
}
@media (max-height:1140px){@container (min-width:640px){
  .vsc .lg,.vsc .mono{width:44px;height:44px}
  .vsc .pick{font-size:36px}.vsc .pick.sm{font-size:28px}.vsc .why{font-size:12px;margin-top:2px}
  .vsc .pf{padding:6px 10px}.vsc .pf strong{font-size:16px}.vsc .pf small{display:none}
  .vsc .sec{display:none}
  .vsc .mk{padding:5px 16px;row-gap:2px}.vsc .mkts{gap:6px;margin-top:8px}.vsc .top{gap:6px 12px}.vsc .in{padding:10px 16px 4px}.vsc .brand{margin-top:4px}.vsc .proof{margin-top:2px}.vsc .px .pr{display:none}
  .vsc .px .ln{font-size:21px}.vsc .px .pr{font-size:11px}.vsc .mid .nums{margin-bottom:3px}.vsc .mid .nums b{font-size:19px}.vsc .track{height:15px}.vsc .tick{top:-4px;bottom:-4px}.vsc .bets{margin-top:5px;font-size:11px}
  .vsc .chip{font-size:11px;padding:2px 8px}
}}
.vsc .body.nol{grid-template-columns:minmax(0,1fr)!important}.vsc .body.nol>.px{display:none}
@media (min-height:961px) and (max-height:1140px){@container (min-width:640px){
  .vsc .lg,.vsc .mono{width:52px;height:52px}
  .vsc .pick{font-size:42px}.vsc .pick.sm{font-size:32px}
  .vsc .pf{padding:9px 12px}.vsc .pf strong{font-size:18px}.vsc .pf small{display:block}
  .vsc .mk{padding:10px 16px;row-gap:6px}.vsc .mkts{gap:9px;margin-top:12px}
  .vsc .track{height:18px}.vsc .tick{top:-5px;bottom:-5px}.vsc .px .ln{font-size:23px}.vsc .px .pr{display:block}
  .vsc .mid .nums b{font-size:21px}.vsc .bets{font-size:12px;margin-top:6px}.vsc .chip{font-size:12px;padding:3px 9px}
}}
@container (max-width:399px){.vsc .pick{font-size:46px}.vsc .pick.sm{font-size:34px}.vsc .body{gap:8px}.vsc .px .ln{font-size:19px}.vsc .px .pr{font-size:11px;max-width:64px}.vsc .px.r .pr{margin-left:auto}.vsc .mid .nums span{display:none}.vsc .mid .nums b{font-size:17px}.vsc .proof{grid-template-columns:1fr}.vsc .lg,.vsc .mono{width:44px;height:44px}.vsc .tm b{font-size:15px}.vsc .brand span{display:none}}
`;
var VSC_CFB = /*vsc-cfb*/{}/*end-vsc-cfb*/;
var VSC_NFL = { LA: 'lar', WAS: 'wsh', JAC: 'jax' };
var VSC_NBA = { NOP: 'no', NYK: 'ny', SAS: 'sa', GSW: 'gs', WAS: 'wsh', UTA: 'utah' };
var VSC_SPORT = { nfl: 'NFL', cfb: 'CFB', nba: 'NBA' };
function vscNorm(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]/g, ''); }
// ESPN serves every logo at 500px; one lookup per sport.
function vscLogoUrl(g, side) {
  var t = g[side], ab = String(t.abbr || '').toUpperCase(), base = 'https://a.espncdn.com/i/teamlogos/';
  if (g.sport === 'nfl') return base + 'nfl/500/' + (VSC_NFL[ab] || ab.toLowerCase()) + '.png';
  if (g.sport === 'nba') return base + 'nba/500/' + (VSC_NBA[ab] || ab.toLowerCase()) + '.png';
  if (g.sport === 'cfb') { var id = VSC_CFB[vscNorm(t.name)]; return id ? base + 'ncaa/500/' + id + '.png' : null; }
  return null;
}
function VscLogo({ g, side }) {
  var h = U.createElement, st = U.useState(false), bad = st[0], setBad = st[1], url = vscLogoUrl(g, side), t = g[side];
  if (!url || bad) return h('div', { className: 'mono', style: { background: t.color || '#3a3a44' } }, String(t.abbr || '?').slice(0, 4));
  return h('img', { className: 'lg', crossOrigin: 'anonymous', src: url, alt: t.name, onError: function () { setBad(true); } });
}
// Small logo for list rows (the Board slate). Falls back to the old team-colour dot when there is no logo or it fails to load.
function VscMini({ g, side, size }) {
  var h = U.createElement, st = U.useState(false), bad = st[0], setBad = st[1], url = vscLogoUrl(g, side), t = g[side], z = size || 22;
  if (!url || bad) return h('i', { style: { width: 8, height: 8, borderRadius: '50%', background: t.color || '#666', display: 'inline-block', margin: '0 ' + Math.round((z - 8) / 2) + 'px', verticalAlign: 'middle' } });
  return h('img', { src: url, alt: '', width: z, height: z, loading: 'lazy', onError: function () { setBad(true); }, style: { width: z, height: z, objectFit: 'contain', flex: 'none', verticalAlign: 'middle', marginRight: z > 20 ? 0 : 5 } });
}
// CFB model rows carry ESPN team ids directly, so no name lookup is needed.
function VscId({ id, size }) {
  var h = U.createElement, st = U.useState(false), bad = st[0], setBad = st[1], z = size || 18;
  if (!id || bad) return null;
  return h('img', { src: 'https://a.espncdn.com/i/teamlogos/ncaa/500/' + id + '.png', alt: '', width: z, height: z, loading: 'lazy', onError: function () { setBad(true); }, style: { width: z, height: z, objectFit: 'contain', verticalAlign: 'middle', margin: '0 5px 0 0' } });
}
// "BUF @ LA" with a small logo before each side; plain text when the game object is not on hand.
function VscPair({ g, lbl, size, sport }) {
  var h = U.createElement, parts = String(lbl || '').split(' @ ');
  if (parts.length !== 2) return lbl;
  // Finished games drop out of the game list, but NFL and NBA logos only need the abbreviation in the label.
  if (!g && (sport === 'nfl' || sport === 'nba')) g = { sport: sport, away: { abbr: parts[0] }, home: { abbr: parts[1] } };
  if (!g) return lbl;
  return h(U.Fragment, null, h(VscMini, { g: g, side: 'away', size: size || 16 }), parts[0], ' @ ', h(VscMini, { g: g, side: 'home', size: size || 16 }), parts[1]);
}

var VCP_CSS = `
.vcp{--bg:#0b0b0d;--line:rgba(255,255,255,.08);--ink:#f4f4f6;--mute:#8b8b95;--dim:#5d5d66;--pick:#46e08c;--amber:#f2b84b;--loss:#ff6b6b;
  position:relative;overflow:hidden;border-radius:22px;background:var(--bg);color:var(--ink);border:1px solid var(--line);width:100%;container-type:inline-size;
  font:500 15px/1.35 Inter,-apple-system,"SF Pro Display",system-ui,sans-serif;-webkit-font-smoothing:antialiased;text-align:left}
.vcp *{box-sizing:border-box;margin:0}
.vcp .glow{position:absolute;inset:0 0 auto 0;height:320px;pointer-events:none;background:radial-gradient(300px 190px at 50% 30%,rgba(70,224,140,.16),transparent 70%),radial-gradient(240px 170px at 0% 0%,rgba(79,140,255,.14),transparent 70%),radial-gradient(240px 170px at 100% 0%,rgba(242,184,75,.12),transparent 70%)}
.vcp .glow.lean{background:radial-gradient(260px 170px at 0% 0%,rgba(79,140,255,.12),transparent 70%),radial-gradient(260px 170px at 100% 0%,rgba(242,184,75,.1),transparent 70%)}
.vcp .in{position:relative;padding:16px 18px 12px}
.vcp .top{display:flex;justify-content:space-between;align-items:center;gap:10px}
.vcp .teams{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;min-width:0;flex-wrap:wrap}
.vcp .teams img{width:36px;height:36px;object-fit:contain;flex:none}
.vcp .teams i{font-style:normal;color:var(--dim);font-weight:500}
.vcp .meta{font-size:12px;color:var(--mute);margin-top:4px}
.vcp .back{all:unset;cursor:pointer;font-size:12px;color:var(--mute);padding:4px 0}
.vcp .pill{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;padding:4px 9px;border-radius:99px;white-space:nowrap}
.vcp .pill.g{color:#06130c;background:var(--pick)}.vcp .pill.l{color:var(--amber);background:rgba(242,184,75,.13);border:1px solid rgba(242,184,75,.3)}.vcp .pill.w{color:#06130c;background:var(--pick)}.vcp .pill.x{color:#2a0a0a;background:var(--loss)}.vcp .pill.d{color:var(--mute);background:rgba(255,255,255,.08)}
.vcp .big{margin:14px 0 4px;display:flex;align-items:flex-end;justify-content:space-between;gap:12px}
.vcp .eyebrow{font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--pick);display:inline-flex;align-items:center;gap:7px}
.vcp .eyebrow i{width:6px;height:6px;border-radius:50%;background:var(--pick);box-shadow:0 0 10px var(--pick)}
.vcp .eyebrow.lean{color:var(--amber)}.vcp .eyebrow.lean i{background:var(--amber);box-shadow:none}
.vcp .p{font-size:46px;font-weight:800;letter-spacing:-.04em;line-height:1.02;color:var(--pick)}
.vcp .p.lean{color:#d9d9e0;opacity:.85}
.vcp .e{text-align:right;flex:none}
.vcp .e small{display:block;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim)}
.vcp .e strong{display:block;font-size:46px;font-weight:800;letter-spacing:-.04em;line-height:1.02;color:var(--pick);font-variant-numeric:tabular-nums}
.vcp .e strong.lean{color:var(--amber)}
.vcp .note{font-size:12.5px;color:var(--mute);margin-bottom:12px}
.vcp .res{font-size:12.5px;color:var(--ink);margin:-6px 0 12px;font-weight:600}
.vcp .ruler{position:relative;margin:0 38px;height:128px}
.vcp .axis{position:absolute;left:0;right:0;top:62px;height:3px;border-radius:3px;background:rgba(255,255,255,.12)}
.vcp .win{position:absolute;top:54px;height:19px;border-radius:6px;background:linear-gradient(90deg,rgba(70,224,140,.35),rgba(70,224,140,.12));border:1px solid rgba(70,224,140,.5)}
.vcp .pin{position:absolute;top:0;transform:translateX(-50%);text-align:center;width:90px}
.vcp .pin b{display:block;font-size:12.5px;white-space:nowrap}
.vcp .pin small,.vcp .under small{display:block;font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vcp .stem{position:absolute;width:2px;transform:translateX(-1px);opacity:.75;border-radius:1px}
.vcp .dot{position:absolute;top:58px;width:11px;height:11px;border-radius:50%;transform:translateX(-50%);border:2px solid var(--bg)}
.vcp .under{position:absolute;top:80px;transform:translateX(-50%);text-align:center;width:96px}
.vcp .under b{display:block;font-size:12.5px;white-space:nowrap}
.vcp .scale{display:flex;justify-content:space-between;gap:8px;font-size:10.5px;color:var(--dim)}
.vcp .row{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}
.vcp .row div{padding:9px 12px;border-radius:14px;background:rgba(255,255,255,.045);border:1px solid var(--line);min-width:0}
.vcp .row em{display:block;font-style:normal;font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);margin-bottom:3px}
.vcp .row strong{font-size:16px;font-weight:700;font-variant-numeric:tabular-nums}
.vcp .row small{display:block;font-size:11px;color:var(--mute);margin-top:1px}
.vcp .brand{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:10px;padding:0 2px;min-height:30px}
.vcp .brand b{font-size:13px;letter-spacing:.14em;font-weight:800}
.vcp .brand span{font-size:11px;color:var(--dim);margin-right:96px}
.vcp .shr{position:absolute;right:18px;bottom:8px;z-index:2;display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:rgba(255,255,255,.07);color:var(--ink);font:600 12px/1 Inter,system-ui,sans-serif;padding:7px 12px;border-radius:99px;cursor:pointer;transition:transform 500ms cubic-bezier(.34,1.56,.64,1),background .15s}
.vcp .shr:hover{background:rgba(255,255,255,.13)}.vcp .shr:active{transform:scale(.94);transition:transform 80ms ease-out}.vcp .shr[disabled]{opacity:.6;cursor:progress}
@container (max-width:520px){.vcp .p,.vcp .e strong{font-size:32px}.vcp .row{grid-template-columns:1fr}.vcp .ruler{margin:0 30px}.vcp .brand span{display:none}.vcp .scale span:nth-child(2){display:none}}
`;
// New pill, ruler and stat row for a CFB model game. Margins in the model data are the HOME side's; the ruler plots the AWAY side's
// margin of victory so "model" and "market" read as two points on one line, and the green is the gap between them (the edge).
function VaultCfbPick(P) {
  var h = U.createElement, x = P.x, lean = x.is_pick === false, home = x.side === 'home', mine = home ? x.home : x.away, other = home ? x.away : x.home;
  var A = function (m) { return m == null ? null : -m; };
  var pts = { market: A(x.market_margin), model: A(x.model_margin), open: A(x.open_margin), blend: A(x.blend_margin) };
  var vals = [pts.market, pts.model, pts.open, pts.blend].filter(function (v) { return v != null; });
  var lo = Math.min.apply(null, vals) - 1.5, hi = Math.max.apply(null, vals) + 1.5, pc = function (v) { return ((v - lo) / (hi - lo) * 100).toFixed(2) + '%'; };
  var by = function (v) { return (v >= 0 ? x.away : x.home) + ' by'; };
  // Labels share one line when they are far enough apart; ones that would touch drop to a second tier with a connector.
  var fmtV = function (v) { return Math.abs(v).toFixed(1).replace(/\.0$/, ''); };
  var items = [['model', 'Model', 'var(--pick)', 1], ['market', 'Market', 'var(--ink)', 1], ['blend', 'Blend', 'var(--amber)', 0], ['open', 'Open', 'var(--mute)', 0]]
    .map(function (d) { return { key: d[0], lbl: d[1], tone: d[2], up: d[3], v: pts[d[0]] }; }).filter(function (d) { return d.v != null; });
  var lanes = { 1: 1, 0: 1 };
  [1, 0].forEach(function (side) {
    var last = [];
    items.filter(function (d) { return d.up === side; }).sort(function (a, b) { return a.v - b.v; }).forEach(function (d) {
      var pcn = (d.v - lo) / (hi - lo) * 100, l = 0;
      while (last[l] != null && pcn - last[l] < 17) l++;
      last[l] = pcn; d.lane = l; lanes[side] = Math.max(lanes[side], l + 1);
    });
  });
  var AX = 62 + (lanes[1] > 1 ? 38 : 0), RH = AX + 18 + lanes[0] * 38 + 6, parts = [];
  items.forEach(function (d) {
    var left = pc(d.v), lbl = [h('b', { key: 'b' }, d.lbl + ' ' + fmtV(d.v)), h('small', { key: 's' }, by(d.v))];
    if (d.up) {
      var top = (lanes[1] - 1 - d.lane) * 38;
      parts.push(h('div', { key: d.key + 'p', className: 'pin', style: { left: left, top: top, color: d.tone } }, lbl));
      parts.push(h('i', { key: d.key + 'st', className: 'stem', style: { left: left, top: top + 36, height: AX - top - 36, background: d.tone } }));
    } else {
      var utop = AX + 18 + d.lane * 38;
      parts.push(h('div', { key: d.key + 'u', className: 'under', style: { left: left, top: utop, color: d.tone } }, lbl));
      if (d.lane > 0) parts.push(h('i', { key: d.key + 'st', className: 'stem', style: { left: left, top: AX + 4, height: utop - AX - 4, background: d.tone } }));
    }
    parts.push(h('div', { key: d.key + 'd', className: 'dot', style: { left: left, top: AX - 4, background: d.tone === 'var(--ink)' ? '#fff' : d.tone } }));
  });
  var win = pts.market != null && pts.model != null ? h('div', { className: 'win', style: { top: AX - 8, left: pc(Math.min(pts.market, pts.model)), width: (Math.abs(pts.market - pts.model) / (hi - lo) * 100).toFixed(2) + '%' } }) : null;
  var line = x.entry, margin = (home ? x.model_margin : -x.model_margin), winner = margin >= 0 ? mine : other;
  var cover = line > 0 ? mine + ' covers unless ' + other + ' wins by more than ' + Math.abs(line).toFixed(1).replace(/\.0$/, '') : mine + ' covers if it wins by more than ' + Math.abs(line).toFixed(1).replace(/\.0$/, '');
  var note = cover + '. The model has ' + winner + ' by ' + Math.abs(margin).toFixed(1).replace(/\.0$/, '') + (lean ? ', which is under the 5-point bar, so this is a lean we track, not a pick.' : ', and the green is the edge.');
  var c = P.c, mk = P.mk, sharp = null;
  if (c) { if (c[x.side].length) sharp = ['With us', P.fm(c[x.side]), 'var(--pick)']; else if (c[P.opp].length) sharp = ['Against', P.fm(c[P.opp]), 'var(--loss)']; }
  sharp = sharp || ['None', 'no Sharp Money card', 'var(--dim)'];
  var mv = mk && mk.move ? (mk.move.v > 0 ? Math.abs(mk.move.pts).toFixed(1) + ' toward the pick' : mk.move.v < 0 ? Math.abs(mk.move.pts).toFixed(1) + ' away from the pick' : 'no move') : 'no move data';
  var res = x.result, live = !res && P.live, pill = res === 'W' ? ['w', 'Won'] : res === 'L' ? ['x', 'Lost'] : res === 'P' ? ['d', 'Push'] : live ? ['d', 'Live'] : lean ? ['l', 'Lean'] : ['g', 'Pick'];
  var pk = P.pk, id = 'vcp-card';
  return h('div', { id: id, className: 'vcp' }, h('style', null, VCP_CSS), h('div', { className: 'glow' + (lean ? ' lean' : '') }),
    h('div', { className: 'in' },
      h('div', { className: 'top' },
        h('div', { style: { minWidth: 0 } }, P.back ? h('button', { type: 'button', className: 'back', onClick: P.back, 'data-html2canvas-ignore': 'true' }, '← Games') : null,
          h('div', { className: 'teams' }, h(VscId, { id: x.away_id, size: 36 }), x.away, h('i', null, '@'), x.home, h(VscId, { id: x.home_id, size: 36 })),
          h('div', { className: 'meta' }, 'Week ' + x.week + ' · ' + P.dt + (x.hs != null ? ' · Final ' + x.as_ + '-' + x.hs : ''))),
        h('span', { className: 'pill ' + pill[0] }, pill[1])),
      h('div', { className: 'big' },
        h('div', null, h('span', { className: 'eyebrow' + (lean ? ' lean' : '') }, h('i'), lean ? 'Model lean' : 'Take'), h('div', { className: 'p' + (lean ? ' lean' : '') }, x.team + ' ' + P.sn(x.entry))),
        h('div', { className: 'e' }, h('small', null, 'Edge'), h('strong', { className: lean ? 'lean' : '' }, Math.abs(x.edge).toFixed(1)))),
      h('div', { className: 'note' }, note),
      P.result ? h('div', { className: 'res' }, P.result) : null,
      h('div', { className: 'ruler', style: { height: RH } }, h('div', { className: 'axis', style: { top: AX } }), win, parts),
      h('div', { className: 'scale' }, h('span', null, x.home + ' stronger'), h('span', null, x.away + ' margin of victory'), h('span', null, x.away + ' stronger')),
      h('div', { className: 'row' },
        h('div', null, h('em', null, 'Sharp money'), h('strong', { style: { color: sharp[2] } }, sharp[0]), h('small', null, sharp[1])),
        h('div', null, h('em', null, 'Line move'), h('strong', null, P.hl(x.open_margin) + ' → ' + P.hl(x.market_margin)), h('small', null, mv)),
        h('div', null, h('em', null, 'Live picks'), h('strong', null, pk ? pk.w + '-' + pk.l : '–'), h('small', null, pk && pk.p != null ? (pk.p * 100).toFixed(1) + '% this season' : 'no picks graded'))),
      h('div', { className: 'brand' }, h('b', null, 'VAULT FANTASY'), h('span', null, 'CFB model · vaultfantasy.com')),
      h('button', { type: 'button', className: 'shr', 'data-html2canvas-ignore': 'true', onClick: function (e) { vscShareCard(e.currentTarget, id, 'vault-cfb-' + String(x.away).toLowerCase().replace(/[^a-z0-9]+/g, '-') + '-' + String(x.home).toLowerCase().replace(/[^a-z0-9]+/g, '-') + '.png', x.away + ' @ ' + x.home + ' CFB model'); } },
        h('svg', { width: 13, height: 13, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round' }, h('path', { d: 'M12 15V3M7 8l5-5 5 5M5 14v5a2 2 0 002 2h10a2 2 0 002-2v-5' })), 'Share')));
}
var vscAm = function (n) { return n == null ? '' : (n > 0 ? '+' : '') + n; };
var vscL = function (n) { return (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(n); };
var vscUsd = function (n) { return n >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? '$' + (n / 1e3).toFixed(n >= 1e4 ? 0 : 1) + 'k' : '$' + Math.round(n); };
var vscPct = function (n) { return Math.round(n * 100) + '%'; };
function vscName(g, m, s) { return m === 'tot' ? (s === 'over' ? 'Over' : 'Under') : (g[s].short || g[s].abbr); }

// One object per market: everything the card draws, derived from the same fields the table used.
function vscMarkets(g) {
  var P = g.pin || {}, O = g.open || {}, F = g.flow || {}, reads = {}, out = [];
  try { Il(g).forEach(function (r) { reads[r.m] = r; }); } catch (e) { }
  ['sp', 'tot', 'ml'].forEach(function (m, idx) {
    var sp = g.splits && g.splits[m];
    if (!(P[m] || O[m] || sp)) return;
    var A = m === 'tot' ? 'over' : 'away', B = m === 'tot' ? 'under' : 'home', rd = reads[m] || {}, k = {};
    var cA = m === 'tot' ? 'var(--over)' : 'var(--a)', cB = m === 'tot' ? 'var(--under)' : 'var(--b)';
    var la = '–', pa = '', lb = '–', pb = '', move = null;
    if (m === 'sp') {
      if (P.sp) { la = vscL(-P.sp.line); pa = vscAm(P.sp.away); lb = vscL(P.sp.line); pb = vscAm(P.sp.home); }
      if (O.sp && P.sp) { var d = O.sp.line - P.sp.line; move = { open: vscL(-O.sp.line), now: vscL(-P.sp.line), d: d, thr: .5, side: d > 0 ? B : A, txt: Math.abs(d) + (Math.abs(d) === 1 ? ' pt' : ' pts') + ' toward ' + vscName(g, m, d > 0 ? B : A) }; }
    } else if (m === 'tot') {
      if (P.tot) { la = 'O ' + P.tot.line; pa = vscAm(P.tot.over); lb = 'U ' + P.tot.line; pb = vscAm(P.tot.under); }
      if (O.tot && P.tot) { var dt = P.tot.line - O.tot.line; move = { open: String(O.tot.line), now: String(P.tot.line), d: dt, thr: 1, side: dt > 0 ? A : B, txt: (dt > 0 ? '+' : '−') + Math.abs(dt).toFixed(1) + ' toward ' + vscName(g, m, dt > 0 ? A : B) }; }
    } else {
      if (P.ml) { var ph = Et(P.ml.home, P.ml.away); la = vscAm(P.ml.away); pa = vscPct(1 - ph) + ' implied'; lb = vscAm(P.ml.home); pb = vscPct(ph) + ' implied'; }
      if (O.ml && P.ml && O.ml.home && O.ml.away) { var o0 = 1 - Et(O.ml.home, O.ml.away), n0 = 1 - Et(P.ml.home, P.ml.away), dm = n0 - o0; move = { open: vscAm(O.ml.away), now: vscAm(P.ml.away), d: dm, thr: .03, side: dm > 0 ? A : B, txt: g.away.short || g.away.abbr } ; move.txt = (g.away.short || g.away.abbr) + ' ' + vscPct(o0) + ' to ' + vscPct(n0); }
    }
    var moved = move && Math.abs(move.d) >= move.thr;
    if (move) move.tone = !moved ? 'flat' : (rd.vs && rd.vs === move.side ? 'up' : 'mv');
    if (move && !moved && move.d === 0) move.txt = 'No move';
    else if (move && !moved) move.txt = 'Barely moved';
    var xa = sp && sp[A], xb = sp && sp[B], bets = null, money = null;
    if (xa && xa.t != null) { bets = xa.t; money = xa.m != null ? xa.m : null; } else if (xb && xb.t != null) { bets = 100 - xb.t; money = xb.m != null ? 100 - xb.m : null; }
    var chips = function (s) {
      var key = m + ':' + s, o = [], sh = (F.sharp && F.sharp[key]) || 0, bg = ((F.pmBig && F.pmBig[key]) || 0) + ((F.kalBig && F.kalBig[key]) || 0) + ((F.novBig && F.novBig[key]) || 0), du = (F.dull && F.dull[key]) || 0;
      if (sh) o.push(['sharp', vscUsd(sh) + ' sharp']); if (bg) o.push(['', vscUsd(bg) + ' big']); if (du) o.push(['loss', vscUsd(du) + ' losing accts']);
      return o.length ? o : [['none', 'no exchange money']];
    };
    var pill = rd.strong ? ['g', 'Sharp: ' + vscName(g, m, rd.vs)] : rd.mixed ? ['y', 'Mixed signals'] : rd.vs ? ['b', 'Lean: ' + vscName(g, m, rd.vs)] : ['q', 'Quiet'];
    var note = null;
    (rd.bl || []).forEach(function (b) { if (!note && /^Reverse move:/.test(b.text)) note = b.text; });
    (rd.bl || []).forEach(function (b) { if (!note && b.tone === 'warn') note = b.text; });
    out.push({ m: m, name: { sp: 'Spread', tot: 'Total', ml: 'Moneyline' }[m], A: A, B: B, cA: cA, cB: cB, la: la, pa: pa, lb: lb, pb: pb, bets: bets, money: money, move: move, pill: pill, note: note,
      exA: chips(A), exB: chips(B), rank: rd.strong ? 3 : rd.vs ? 2 : rd.mixed ? 1 : 0, idx: idx, hot: !!rd.strong });
  });
  return out.sort(function (x, y) { return y.rank - x.rank || x.idx - y.idx; });
}

function vscH2C() {
  if (window.html2canvas) return Promise.resolve(window.html2canvas);
  return new Promise(function (ok, no) { var s = document.createElement('script'); s.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js'; s.onload = function () { ok(window.html2canvas); }; s.onerror = no; document.head.appendChild(s); });
}
function vscToast(msg) {
  var t = document.getElementById('vsc-toast');
  if (!t) { t = document.createElement('div'); t.id = 'vsc-toast'; t.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translate(-50%,20px);opacity:0;background:#fff;color:#0b0b0d;font:600 13px Inter,system-ui,sans-serif;padding:10px 16px;border-radius:99px;transition:all .3s cubic-bezier(.22,1,.36,1);pointer-events:none;z-index:99999'; document.body.appendChild(t); }
  t.textContent = msg; t.style.opacity = '1'; t.style.transform = 'translate(-50%,0)'; clearTimeout(t._t); t._t = setTimeout(function () { t.style.opacity = '0'; t.style.transform = 'translate(-50%,20px)'; }, 2200);
}
// Renders the card at a fixed 560px (so the shared image is the same shape on every screen) and hands it to the share sheet,
// the clipboard, or a download, in that order. Guarded by dataset.busy because disabled alone leaves a double-click window.
function vscShareCard(btn, id, name, title) {
  if (btn.dataset.busy) return; btn.dataset.busy = '1'; btn.disabled = true;
  vscH2C().then(function (h2c) {
    return h2c(document.getElementById(id), { scale: 3, backgroundColor: '#0b0b0d', useCORS: true, windowWidth: 1000,
      onclone: function (doc) { var el = doc.getElementById(id); el.className = el.className.replace(/\bfit\b/, '').trim(); el.style.width = '560px'; el.style.maxWidth = 'none'; el.style.margin = '0'; } });
  }).then(function (c) { return new Promise(function (r) { c.toBlob(r, 'image/png'); }); }).then(function (blob) {
    var file = new File([blob], name, { type: 'image/png' });
    if (navigator.canShare && navigator.canShare({ files: [file] })) return navigator.share({ files: [file], title: title });
    return navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]).then(function () { vscToast('Copied image. Paste it anywhere'); }, function () {
      var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); vscToast('Saved PNG');
    });
  }).catch(function (e) { if (!e || e.name !== 'AbortError') vscToast('Could not render the image'); })
    .then(function () { delete btn.dataset.busy; btn.disabled = false; });
}
function vscShare(btn, g) {
  vscShareCard(btn, 'vsc-card', 'vault-sharp-money-' + String(g.away.abbr).toLowerCase() + '-' + String(g.home.abbr).toLowerCase() + '.png', g.away.abbr + ' @ ' + g.home.abbr + ' sharp money');
}

function vscMk(g, m) {
  var h = U.createElement, chips = function (a) { return a.map(function (x, i) { return h('span', { key: i, className: 'chip ' + x[0] }, x[1]); }); };
  var mv = m.move, hasMoney = m.money != null, moneyA = hasMoney ? m.money : m.bets;
  return h('div', { className: 'mk' + (m.hot ? ' hot' : ''), key: m.m },
    h('div', { className: 'mh' }, h('h4', null, m.name), h('span', { className: 'pill ' + m.pill[0] }, m.pill[1])),
    h('div', { className: 'body' + (m.la === '\u2013' && m.lb === '\u2013' ? ' nol' : '') },
      h('div', { className: 'px' }, h('div', { className: 'ln' }, m.la), h('div', { className: 'pr' }, m.pa)),
      moneyA == null ? h('div', { className: 'nosp' }, 'No US book split yet') : h('div', { className: 'mid' },
        h('div', { className: 'nums' }, h('b', { style: { color: m.cA } }, moneyA + '%'), h('span', null, hasMoney ? 'Money' : 'Bets'), h('b', { style: { color: m.cB } }, (100 - moneyA) + '%')),
        h('div', { className: 'track' }, h('span', { style: { flex: moneyA, background: m.cA } }), h('span', { style: { flex: 100 - moneyA, background: m.cB, opacity: .7 } }), hasMoney && m.bets != null ? h('i', { className: 'tick', style: { left: m.bets + '%' } }) : null),
        hasMoney && m.bets != null ? h('div', { className: 'bets' }, h('span', null, 'Bets ' + m.bets + '%'), h('span', null, (100 - m.bets) + '%')) : null),
      h('div', { className: 'px r' }, h('div', { className: 'ln' }, m.lb), h('div', { className: 'pr' }, m.pb))),
    mv ? h('div', { className: 'move' }, h('span', null, 'Open'), h('span', { className: 'arrow' }, mv.open + ' → ' + mv.now), h('span', { className: 'd ' + mv.tone }, mv.txt)) : null,
    h('div', { className: 'ex' }, h('div', { className: 'chips' }, chips(m.exA, m.A)), h('div', { className: 'chips r' }, chips(m.exB, m.B))),
    m.note ? h('div', { className: 'note' }, m.note) : null);
}

function VaultEveryLine({ g, row }) {
  var h = U.createElement, mk = vscMarkets(g), kinds = row ? row.why.map(function (w) { return w.k; }) : [], hm = row && mk.find(function (x) { return x.m === row.m; });
  var when = new Date(g.start * 1000).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' });
  var hero, proof = null, proofEl = null;
  if (row && hm) {
    var s = row.side, isA = s === hm.A, other = isA ? hm.B : hm.A, parts = String(row.pick).split(' '), last = parts[parts.length - 1], hasSub = parts.length > 1 && /^([+\-−]?\d|ML$)/.test(last);
    var word = hasSub ? parts.slice(0, -1).join(' ') : row.pick, sub = hasSub ? last.replace('-', '−') : null;
    var col = isA ? hm.cA : hm.cB, F = g.flow || {}, sh = (F.sharp && F.sharp[hm.m + ':' + s]) || 0, shO = (F.sharp && F.sharp[hm.m + ':' + other]) || 0;
    var mMoney = hm.money != null ? (isA ? hm.money : 100 - hm.money) : null, mBets = hm.bets != null ? (isA ? hm.bets : 100 - hm.bets) : null;
    var mv = hm.move, moved = mv && Math.abs(mv.d) >= mv.thr;
    proof = [
      { k: 'Line move', on: kinds.indexOf('line') >= 0, v: mv ? mv.open + ' → ' + mv.now : 'No line', s: mv ? (moved ? (mv.side === s ? 'toward ' + vscName(g, hm.m, s) : 'toward ' + vscName(g, hm.m, mv.side)) : 'no real move') : '' },
      { k: 'Money vs bets', on: kinds.indexOf('money') >= 0, v: mMoney != null && mBets != null ? mMoney + '% / ' + mBets + '%' : '–', s: mMoney != null && mBets != null ? (mMoney - mBets >= 0 ? 'money ' + (mMoney - mBets) + ' pts ahead of bets' : 'bets ' + (mBets - mMoney) + ' pts ahead of money') : 'no US book split' },
      { k: 'Exchange', on: kinds.indexOf('sharp') >= 0, v: sh ? vscUsd(sh) + ' sharp' : 'No sharp $', s: shO ? 'vs ' + vscUsd(shO) + ' on ' + vscName(g, hm.m, other) : 'none on ' + vscName(g, hm.m, other) }];
    hero = h('div', { className: 'verdict' }, h('div', { className: 'eyebrow' }, h('i'), 'Sharp side'),
      h('div', { className: 'pick' + (word.length > 12 ? ' sm' : ''), style: { color: col } }, word, sub ? h('span', null, sub) : null),
      h('div', { className: 'why' }, row.n + ' independent signals agree · ' + hm.name, h('span', { className: 'wh' }, ' · ' + (VSC_SPORT[g.sport] || '') + ' ' + when)),
      );
    proofEl = h('div', { className: 'proof' }, proof.map(function (p) { return h('div', { key: p.k, className: 'pf' + (p.on ? ' on' : '') }, h('em', null, h('i'), p.k), h('strong', null, p.v), h('small', null, p.s)); }));
  } else {
    hero = h('div', { className: 'verdict' }, h('div', { className: 'eyebrow q' }, h('i'), 'No sharp side yet'), h('div', { className: 'why', style: { marginTop: 10 } }, 'No market has two independent signals agreeing right now.', h('span', { className: 'wh' }, ' \u00B7 ' + (VSC_SPORT[g.sport] || '') + ' ' + when)));
  }
  return h('div', { id: 'vsc-card', className: 'vsc fit' }, h('style', null, VSC_CSS), h('div', { className: 'glow' + (row ? '' : ' q') }),
    h('div', { className: 'in' },
      h('div', { className: 'bar', 'data-html2canvas-ignore': 'true' }, h('button', { type: 'button', className: 'share', onClick: function (e) { vscShare(e.currentTarget, g); } },
        h('svg', { width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round' }, h('path', { d: 'M12 15V3M7 8l5-5 5 5M5 14v5a2 2 0 002 2h10a2 2 0 002-2v-5' })), 'Share')),
      h('div', { className: 'top' },
        h('div', { className: 'tm' }, h(VscLogo, { g: g, side: 'away', key: g.key + 'a' }), h('div', null, h('b', null, g.away.short || g.away.name), h('small', null, 'Away'))),
        h('div', { className: 'at' }, h('b', null, '@'), VSC_SPORT[g.sport] || '', h('br'), when),
        h('div', { className: 'tm r' }, h(VscLogo, { g: g, side: 'home', key: g.key + 'h' }), h('div', null, h('b', null, g.home.short || g.home.name), h('small', null, 'Home'))),
        hero, proofEl),
      mk.length ? h('div', { className: 'sec' }, h('span', null, 'Every line, ranked by signal'), h('span', null, h('i'), '= share of bets')) : null,
      h('div', { className: 'mkts' }, mk.map(function (m) { return vscMk(g, m); })),
      h('div', { className: 'brand' }, h('b', null, 'VAULT FANTASY'), h('span', null, 'Pinnacle + exchanges, last 24h · vaultfantasy.com'))));
}
