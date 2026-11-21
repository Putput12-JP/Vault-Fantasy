/* Following: follow specific Polymarket wallets (hot ones, and price-sharp ones in NBA and NFL) and see every bet they have open, for Sharp Money.
   One file for both layouts (sharp-money/index.html and sharp-money/new/index.html), so the two stay the same page.
   Data: wallets.json on the pm-cards-live branch, built every 10 minutes by scripts/build_side_cards.py --wallets-out
   (docs/side-cards.md, "Wallets file"). Until that file exists the page says so.

   Sharp money is context only (CLAUDE.md). This page shows who holds what. It never shows a suggested size and it never feeds
   Top Reads, SM_GATE or an agree total. Every number is a stored field: money is shares times the market price at the last scan,
   and no entry price is stored, so none is shown.

   Follows are kept in this browser (localStorage `vault-sharps-following`: {"sport|wallet": followed-at seconds}). "Since you
   followed" counts a wallet's settled games dated after its follow time, from the 20 most recent the file carries.

   A bet in the feed opens a detail panel: the position, how the wallet has done on bets like it, and who else holds the game (read
   from the Sharps cards, live.json). The panel names the side of the card's suggested play, flat 1u on NBA, NFL and CBB and none on CFB (the same rule as side-cards.js). */
(function(){
'use strict';
var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
var DEV = LOCAL && (location.search.match(/[?&]wallets=([^&]+)/) || [])[1];      /* localhost only: ?wallets=/path/to/wallets.json */
var SRC = DEV ? decodeURIComponent(DEV) : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-cards-live/wallets.json';
var DEVC = LOCAL && (location.search.match(/[?&]cards=([^&]+)/) || [])[1];        /* localhost only: ?cards=/path/to/live.json */
var CARDS_SRC = DEVC ? decodeURIComponent(DEVC) : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-cards-live/live.json';
var FLAT_SP = {nba: 1, nfl: 1, cbb: 1};      /* the Sharps card shows a flat 1u on these only (side-cards.js) */
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
'.vfw .fw-feed{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;align-items:start}',
'.vfw .fw-g{padding:16px 18px;min-width:0}.vfw .fw-dir{min-width:0;overflow:hidden}',
'.vfw .fw-gh{display:flex;align-items:center;gap:10px;margin-bottom:6px}.vfw .fw-gh b{font-size:14.5px;font-weight:600;white-space:nowrap}.vfw .fw-gh time{margin-left:auto;font-size:12px;color:var(--c-mut);white-space:nowrap}',
'.vfw .fw-rk{margin-left:7px;font-weight:600}.vfw .fw-rk.sharp{color:var(--c-good)}.vfw .fw-rk.dull{color:var(--c-bad)}',
'.vfw .fw-tag{font-family:var(--c-num);font-style:normal;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--c-mut);background:var(--c-box);border-radius:5px;padding:3px 6px}',
'.vfw .fw-badge{font-size:11px;font-weight:600;border-radius:999px;padding:3px 9px}.vfw .fw-badge.agree{background:var(--c-good-bg);color:var(--c-good)}.vfw .fw-badge.split{background:var(--c-warn-bg);color:var(--c-warn)}',
'.vfw .fw-side{padding:11px 0 2px;border-top:1px solid var(--c-line);margin-top:8px}',
'.vfw .fw-side-h{display:flex;align-items:baseline;gap:8px;font-size:13px}.vfw .fw-side-h span{color:var(--c-mut);font-size:11.5px}.vfw .fw-side-h b{font-weight:600}',
'.vfw .fw-bet{display:flex;align-items:center;gap:10px;padding:7px 0;font-size:12.5px}',
'.vfw .fw-bet .fw-nm{font-weight:500;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.vfw .fw-bet .fw-rec{color:var(--c-mut);font-size:11.5px;white-space:nowrap}.vfw .fw-bet .fw-usd{margin-left:auto;font-size:13px;white-space:nowrap}',
'.vfw button.fw-bet{width:100%;border:0;background:none;color:inherit;text-align:left;cursor:pointer;border-radius:8px;--fw-ps:.99}',
'.vfw button.fw-bet:hover,.vfw button.fw-bet[aria-expanded=true]{background:var(--c-sel);box-shadow:-6px 0 0 var(--c-sel),6px 0 0 var(--c-sel)}',
'.vfw .fw-chev{flex:none;width:14px;color:var(--c-dim);font-size:11px;text-align:center;transition:transform 200ms var(--fw-rail)}.vfw button.fw-bet[aria-expanded=true] .fw-chev{transform:rotate(90deg)}',
'.vfw .fw-det{margin:6px -6px 8px;padding:14px 14px 12px;background:var(--c-box);border-radius:12px;font-size:12.5px}',
'.vfw .fw-det h5{margin:14px 0 6px;font-size:11px;font-weight:500;color:var(--c-mut);font-family:inherit;letter-spacing:normal;text-transform:none}.vfw .fw-det h5:first-child{margin-top:0}',
'.vfw .fw-kv{display:grid;grid-template-columns:1fr auto;gap:5px 14px;margin:0}.vfw .fw-kv dt{color:var(--c-mut)}.vfw .fw-kv dd{margin:0;text-align:right}',
'.vfw .fw-like{display:grid;grid-template-columns:1fr auto auto;gap:5px 14px;margin:0}.vfw .fw-like dd{margin:0;text-align:right}',
'.vfw .fw-strip{display:flex;gap:3px;margin-top:9px;align-items:center;flex-wrap:wrap}.vfw .fw-strip i{width:9px;height:9px;border-radius:2px;background:var(--c-dim)}.vfw .fw-strip i.w{background:var(--c-good)}.vfw .fw-strip i.l{background:var(--c-bad)}.vfw .fw-strip span{margin-left:6px;font-size:11px;color:var(--c-mut)}',
'.vfw .fw-sot{display:flex;align-items:flex-end;gap:3px;height:38px;margin-top:2px}.vfw .fw-sot i{flex:1 1 0;max-width:14px;min-width:3px;background:var(--c-mut);border-radius:2px 2px 0 0}.vfw .fw-sot i:last-child{background:var(--c-ink)}',
'.vfw .fw-who{border-top:1px solid var(--c-line2);padding:8px 0 4px}.vfw .fw-who:first-of-type{border-top:0;padding-top:0}',
'.vfw .fw-who-h{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}.vfw .fw-who-h b{font-weight:600}.vfw .fw-who-h span{color:var(--c-mut);font-size:11.5px}.vfw .fw-who-h em{font-style:normal;font-size:10.5px;color:var(--c-mut);border:1px solid var(--c-line2);border-radius:99px;padding:1px 7px}',
'.vfw .fw-who-w{display:flex;gap:10px;align-items:center;padding:4px 0 0;color:var(--c-ink)}.vfw .fw-who-w .fw-nm{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.vfw .fw-who-w .fw-usd{margin-left:auto}.vfw .fw-who-w u{text-decoration:none;color:var(--c-gold)}',
'.vfw .fw-det-n{margin:10px 0 0;font-size:11.5px;color:var(--c-mut)}.vfw .fw-det-l{display:flex;gap:16px;flex-wrap:wrap;margin-top:8px}.vfw .fw-det-l a{color:var(--c-ink);font-size:12px;text-underline-offset:3px}',
'.vfw .fw-x{font-style:normal;font-size:11.5px;border-radius:5px;padding:2px 6px;background:var(--c-box);color:var(--c-mut);white-space:nowrap}.vfw .fw-x.fw-hot{background:var(--c-good-bg);color:var(--c-good)}',
'.vfw .fw-empty{padding:26px var(--c-pad);font-size:13px;color:var(--c-mut);text-align:center}.vfw .fw-empty b{display:block;color:var(--c-ink);font-size:14px;margin-bottom:4px}',
'.vfw .fw-since{display:flex;flex-wrap:wrap;gap:8px 26px;align-items:baseline;font-size:13px}.vfw .fw-since>b{font-size:22px;font-weight:600}.vfw .fw-since span{color:var(--c-mut)}',
'.vfw .fw-since-l{margin:12px 0 0;padding:0;list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:6px 22px;font-size:12.5px}',
'.vfw .fw-since-l li{display:flex;justify-content:space-between;gap:10px;border-top:1px solid var(--c-line);padding-top:6px}.vfw .fw-since-l i{font-style:normal;color:var(--c-mut);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
'.vfw .fw-tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap}',
'.vfw .fw-chk{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--c-mut);cursor:pointer;min-height:36px}.vfw .fw-chk input{accent-color:var(--c-ink)}',
'.vfw .fw-dir{padding:4px 0}',
'.vfw .fw-cols,.vfw .fw-row{display:grid;grid-template-columns:40px minmax(130px,1.6fr) 124px 54px 84px 76px 60px 96px 96px 70px;align-items:center;gap:8px;padding:0 var(--c-pad)}',
'.vfw .fw-cols{font-size:11px;color:var(--c-dim);padding-top:12px;padding-bottom:8px}',
'.vfw .fw-th{all:unset;box-sizing:border-box;font:inherit;color:inherit;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.vfw .fw-th:hover,.vfw .fw-th.on{color:var(--c-ink,currentColor)}.vfw .fw-th:focus-visible{outline:2px solid var(--c-mut);outline-offset:2px;border-radius:4px}.vfw .fw-th i{font-style:normal;margin-left:4px}.vfw .fw-later{margin:14px 0 0;display:flex;align-items:center;gap:8px;cursor:pointer}',
'.vfw .fw-cols>:nth-child(n+5),.vfw .fw-row>span:nth-child(n+5){text-align:right}',
'.vfw .fw-dots{display:flex;gap:4px;align-items:center;justify-self:start}.vfw .fw-dots i{width:8px;height:8px;border-radius:50%;background:var(--c-dim);flex:none}.vfw .fw-dots i.w{background:var(--c-good)}.vfw .fw-dots i.l{background:var(--c-bad)}',
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
/* the account sheet: opened from a bet in the feed (centered on desktop, a bottom sheet on a phone) */
'.vfw .fw-sh-scrim{position:fixed;inset:0;z-index:1100;background:rgba(0,0,0,.55);display:grid;place-items:center;padding:16px}',
'.vfw .fw-sh{position:relative;width:min(900px,100%);max-height:calc(100vh - 32px);overflow-y:auto;overscroll-behavior:contain;background:var(--c-card);color:var(--c-ink);border-radius:var(--c-r);padding:22px 24px 20px;box-shadow:0 30px 80px rgba(0,0,0,.5);border:1px solid var(--c-line)}',
'.vfw .fw-sh.fw-in{animation:fw-sh-in 450ms var(--fw-spring)}.vfw .fw-sh-scrim.fw-in{animation:fw-sh-fade 220ms ease-out}',
'@keyframes fw-sh-in{from{opacity:0;transform:translateY(14px) scale(.97)}to{opacity:1;transform:none}}@keyframes fw-sh-fade{from{opacity:0}to{opacity:1}}',
'.vfw .fw-sh-top{display:flex;align-items:center;gap:12px}.vfw .fw-sh-top h2{margin:0;font-size:18px;font-weight:600}.vfw .fw-sh-top p{margin:2px 0 0;font-size:12.5px;color:var(--c-mut)}',
'.vfw .fw-sh-av{flex:none;width:42px;height:42px;border-radius:50%;background:var(--c-box);display:grid;place-items:center;font-weight:700;font-size:16px}',
'.vfw .fw-sh-top .sp{flex:1}.vfw .fw-sh-fol{border:1px solid var(--c-line2);background:none;color:var(--c-gold);border-radius:999px;padding:7px 14px;font-weight:600;font-size:12.5px;cursor:pointer;min-height:36px;--fw-ps:.94}.vfw .fw-sh-fol.on{background:rgba(240,207,122,.14)}',
'.vfw .fw-sh-x{flex:none;width:34px;height:34px;border-radius:50%;border:0;background:var(--c-box);color:var(--c-mut);font-size:18px;cursor:pointer;line-height:1;--fw-ps:.88}',
'.vfw .fw-sh-ban{margin:16px 0 0;background:var(--c-box);border-radius:18px;padding:14px 18px;display:grid;grid-template-columns:1fr auto;gap:2px 16px;align-items:center}',
'.vfw .fw-sh-ban .m,.vfw .fw-sh-ban .g{font-size:12.5px;color:var(--c-mut)}.vfw .fw-sh-ban .s{font-size:24px;font-weight:600;letter-spacing:-.02em;line-height:1.15}',
'.vfw .fw-sh-ban .px{grid-row:1/4;grid-column:2;text-align:right}.vfw .fw-sh-ban .px b{display:block;font-size:38px;line-height:1;font-weight:500}.vfw .fw-sh-ban .px span{font-size:11.5px;color:var(--c-mut)}',
'.vfw .fw-sh-k{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0 0}',
'.vfw .fw-sh-k>div{background:var(--c-box);border-radius:16px;padding:12px 14px;min-width:0}.vfw .fw-sh-k b{display:block;font-size:28px;line-height:1.1;font-weight:500}.vfw .fw-sh-k span{display:block;font-size:12px;color:var(--c-mut);margin-top:3px}.vfw .fw-sh-k i{display:block;font-style:normal;font-size:11.5px;color:var(--c-dim);margin-top:1px}',
'.vfw .fw-sh-tabs{display:flex;gap:2px;margin:16px 0 14px;border-bottom:1px solid var(--c-line)}.vfw .fw-sh-tabs button{border:0;background:none;color:var(--c-mut);font-size:13px;font-weight:600;padding:10px 14px;cursor:pointer;position:relative;min-height:40px}',
'.vfw .fw-sh-tabs button.on{color:var(--c-ink)}.vfw .fw-sh-tabs button.on::after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:2px;border-radius:2px;background:var(--c-ink)}',
'.vfw .fw-sh-pan{min-height:300px}',
'.vfw .fw-sh-3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}.vfw .fw-sh h5{margin:0 0 8px;font-size:11px;font-weight:600;color:var(--c-mut);letter-spacing:.04em;text-transform:uppercase}',
'.vfw .fw-sh .fw-kv{margin:0}.vfw .fw-sh .fw-det-n{margin:8px 0 0}',
'.vfw .fw-sh-ctx{margin:16px 0 0;background:var(--c-box);border-radius:12px;padding:10px 12px;font-size:12.5px;color:var(--c-mut)}.vfw .fw-sh-ctx b{color:var(--c-ink);font-weight:600}',
'.vfw .fw-sh-cuts{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}',
'.vfw .fw-sh-cut{all:unset;box-sizing:border-box;cursor:pointer;background:var(--c-box);border-radius:16px;padding:12px;border:1.5px solid transparent;min-width:0;--fw-ps:.975;transition:transform 500ms var(--fw-spring),border-color 150ms ease}',
'.vfw .fw-sh-cut:active{transform:scale(var(--fw-ps));transition:transform 80ms ease-out}.vfw .fw-sh-cut:focus-visible{outline:2px solid var(--c-mut)}.vfw .fw-sh-cut.on{border-color:var(--c-gold);background:rgba(240,207,122,.07)}',
'.vfw .fw-sh-cut .t{display:block;font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--c-mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
'.vfw .fw-sh-cut .pl{display:block;font-size:11.5px;color:var(--c-ink);margin:5px 0 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
'.vfw .fw-sh-cut .r{display:flex;justify-content:space-between;align-items:baseline;font-size:20px;gap:6px}.vfw .fw-sh-cut .r b{font-weight:500}',
'.vfw .fw-sh-cut .s{display:block;font-size:11.5px;color:var(--c-mut);margin-top:1px}.vfw .fw-sh-cut .a{display:block;border-top:1px solid var(--c-line);margin-top:8px;padding-top:7px;font-size:11.5px;color:var(--c-mut)}.vfw .fw-sh-cut .a b{font-weight:500;color:var(--c-ink)}',
'.vfw .fw-sh-ch{margin-top:14px;background:var(--c-box);border-radius:16px;padding:12px 14px}',
'.vfw .fw-sh-ch-h{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}.vfw .fw-sh-ch-h h5{margin:0}.vfw .fw-sh-ch-h .sp{flex:1}.vfw .fw-sh-ch-v{font-size:22px}',
'.vfw .fw-sh-ch .fw-seg{background:var(--c-card)}.vfw .fw-sh-ch .fw-seg>button{min-height:28px;padding:0 10px;font-size:12px}',
'.vfw .fw-sh-ch svg{display:block;width:100%;height:auto;overflow:visible}',
'.vfw .fw-sh-n{margin:8px 0 0;font-size:11.5px;color:var(--c-dim)}.vfw .fw-sh-n b{color:var(--c-mut);font-weight:600}',
'.vfw button.fw-bet[aria-haspopup]{--fw-ps:.99}',
'@media (max-width:767px){',
'.vfw .fw-sh-scrim{place-items:end center;padding:0}.vfw .fw-sh{width:100%;max-height:92vh;border-radius:24px 24px 0 0;padding:18px 16px 16px}',
'.vfw .fw-sh-ban .s{font-size:20px}.vfw .fw-sh-ban .px b{font-size:30px}.vfw .fw-sh-k b{font-size:22px}.vfw .fw-sh-k>div{padding:10px}',
'.vfw .fw-sh-3{grid-template-columns:1fr;gap:16px}.vfw .fw-sh-cuts{grid-template-columns:repeat(2,minmax(0,1fr))}.vfw .fw-sh-cuts .fw-sh-cut:last-child:nth-child(odd){grid-column:1/-1}',
'.vfw .fw-sh-fol{padding:7px 11px}',
'}',
'@media (max-width:767px){',
'.vfw .fw-sum{gap:14px;margin:10px 0;font-size:12px}.vfw .fw-sum b{font-size:24px}',
'.vfw .fw-feed{grid-template-columns:minmax(0,1fr);gap:10px}.vfw .fw-h{margin-top:24px}.vfw .fw-h p{flex-basis:100%;order:3}',
'.vfw .fw-seg>button{min-height:36px}',
'.vfw .fw-cols{display:none}',
'.vfw .fw-row{grid-template-columns:40px 1fr auto auto;grid-template-areas:"s n roi o" "s m roi o" "s d roi o";row-gap:2px;padding:9px 12px;min-height:58px}',
'.vfw .fw-row>span{display:none}.vfw .fw-row>.c-star{display:block;grid-area:s}.vfw .fw-row>.c-name{display:block;grid-area:n}',
'.vfw .fw-row>.c-roi{display:block;grid-area:roi;font-size:17px}.vfw .fw-row>.c-open{display:block;grid-area:o}.vfw .fw-row>.c-dots{display:block;grid-area:d;text-align:left}.vfw .fw-row>.c-dots:empty{display:none}',
'.vfw .fw-row>.c-meta{display:block;grid-area:m;font-size:11.5px;color:var(--c-mut);text-align:left}',
'.vfw .fw-prof{grid-template-columns:1fr;padding:14px 16px 18px}.vfw .fw-bet .fw-usd{font-size:16px}',
'.vfw .fw-obh{display:none}',
'.vfw .fw-obr{grid-template-columns:1fr auto auto;grid-template-areas:"gm gm st" "bt bt sz" "sn sn px";gap:3px 10px;padding:10px 0}',
'.vfw .fw-obr .gm{grid-area:gm}.vfw .fw-obr .bt{grid-area:bt;font-size:14px}.vfw .fw-obr .st{grid-area:st;font-size:17px}.vfw .fw-obr .sz{grid-area:sz}',
'.vfw .fw-obr .px{grid-area:px;color:var(--c-mut);font-size:13px}.vfw .fw-obr .sn{grid-area:sn;text-align:left!important}',
'.vfw .fw-obr .px::before{content:"now "}.vfw .fw-obr .sn::before{content:"held since "}',
'}',
'@media (prefers-reduced-motion:reduce){.vfw .fw-press,.vfw .fw-seg .fw-pill,.vfw .fw-chev,.vfw .fw-sh-cut{transition:none}.vfw .fw-sh.fw-in,.vfw .fw-sh-scrim.fw-in{animation:none}}'
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
var STORE = {d: null, state: 'loading', busy: false, hosts: [], timer: null, waiters: []};
var W = [], BOOK = {}, GAMES = [], OPEN = {};
function index(d){
  W = []; BOOK = {}; OPEN = {}; var gm = {};
  Object.keys(d.sports || {}).forEach(function(sport){ var ws = d.sports[sport];
    Object.keys(ws).forEach(function(w){ var e = ws[w], dv = e.dive || {}, k = sport + '|' + w;
      var x = {k: k, w: w, sport: sport, name: shortName(w, e.name), wl: [e.w_, e.l_], roi: e.roi, n: e.n, usual: e.usual, pnl: e.pnl,
        rk: e.rk || null, sc: !!e.sc, clv: e.clv || {}, l30roi: e.l30_roi, l30: e.l30 || null, d30: e.d30 || null, odds: e.odds || null, curve: e.curve || null, lane: dv.lane || {}, fav: dv.fav, dog: dv.dog, size: dv.size || {}, legs: e.legs || [], pos: e.positions || []};
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
      STORE.waiters.splice(0).forEach(function(f){ f(); });
    });
}
var FOLLOWS = {};
try { FOLLOWS = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { FOLLOWS = {}; }
function save(){ try { localStorage.setItem(KEY, JSON.stringify(FOLLOWS)); } catch (e) {} }

/* ---------- render ---------- */
function seg(id, opts, cur){ return '<div class="fw-seg" data-seg="' + id + '"><i class="fw-pill"></i>' + opts.map(function(o){ return '<button type="button" class="' + (o[0] === cur ? 'on' : '') + '" data-v="' + o[0] + '">' + o[1] + '</button>'; }).join('') + '</div>'; }
function xUsual(p){ return '<i class="fw-x fw-num' + (p.press >= PRESS ? ' fw-hot' : '') + '">' + (p.press != null ? p.press.toFixed(1) + 'x usual' : 'no usual') + '</i>'; }

/* the Sharps cards (live.json), loaded the first time a bet is opened: who else holds this game. Stored values only. */
var CARDS = {state: 'idle', by: {}};
function loadCards(){
  if (CARDS.state === 'busy') return; var first = CARDS.state === 'idle'; CARDS.state = first ? 'busy' : CARDS.state;
  fetch(CARDS_SRC + '?t=' + Math.floor(Date.now() / 120000), {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; })
    .then(function(j){
      if (j && j.games){ CARDS.by = {}; j.games.forEach(function(c){ CARDS.by[c.ev + '@' + c.gst] = c; }); CARDS.state = 'ok'; }
      else if (first) CARDS.state = 'none';
      STORE.hosts.forEach(function(h){ if (document.contains(h.el)) h.render(); });
    });
}
function recRow(label, v){
  return '<dt>' + label + '</dt>' + (v ? '<dd class="fw-num">' + v[0] + '-' + v[1] + '</dd><dd class="fw-num ' + cls(v[2]) + '">' + pct(v[2]) + '</dd>' : '<dd class="fw-none">no bets yet</dd><dd></dd>');
}
function whoSide(c, m, name, mine, sport){
  var a = (m.sides[name] || {}).all; if (!a) return '';
  var n = ((a.counts || {}).hc || 0) + ((a.counts || {}).sharp || 0);
  return '<div class="fw-who"><div class="fw-who-h"><b>' + esc(name) + '</b>' + (mine ? '<em>this bet</em>' : '') +
    '<span class="fw-num">' + usd(a.sharp_usd) + ' hot · ' + n + (n === 1 ? ' wallet' : ' wallets') + ' · ' + usd(a.loser_usd) + ' from losing wallets</span></div>' +
    (a.list || []).map(function(x){ var b = BOOK[sport + '|' + x.w];
      return '<div class="fw-who-w"><span class="fw-nm">' + (FOLLOWS[sport + '|' + x.w] ? '<u>★</u> ' : '') + esc(b ? b.name : shortName(x.w)) + '</span><span class="fw-rec fw-num">' + x.w_ + '-' + x.l_ + '</span>' +
        '<span class="fw-usd fw-num">' + usd(x.usd) + '</span>' + xUsual(x) + '</div>'; }).join('') +
    (n > (a.list || []).length ? '<p class="fw-det-n" style="margin-top:4px">The card lists the ' + (a.list || []).length + ' largest.</p>' : '') + '</div>';
}
function whoElse(g, p){
  if (CARDS.state === 'idle' || CARDS.state === 'busy') return '<p class="fw-det-n">Loading the Sharps card…</p>';
  var c = CARDS.by[g.id], m = c && c.markets && c.markets[p.g];
  if (!m) return '<p class="fw-det-n">There is no Sharps card for this ' + GROUPS[p.g].toLowerCase() + ' right now.</p>';
  var names = Object.keys(m.sides).sort(function(a, b){ return (b === p.side) - (a === p.side); });
  var sf = (m.sf || {}).all, key = (c.vault || {}).key;
  return names.map(function(n){ return whoSide(c, m, n, n === p.side, g.sport); }).join('') +
    '<p class="fw-det-n">' + (sf && sf.side && sf.units > 0 && FLAT_SP[g.sport] ? 'The Sharps card has a suggested play on ' + esc(sf.side) + ' in this market. Its size is a flat 1u from an untested rule.'
      : sf && sf.side && sf.units > 0 ? 'The Sharps card shows no size on CFB games.' : 'The Sharps card has no suggested play in this market.') + '</p>' +
    '<div class="fw-det-l"><a href="#sharps">Open the Sharps cards</a>' + (key ? '<a href="#game/' + encodeURIComponent(key) + '">Open this game</a>' : '') + '</div>';
}
/* ---------- the account sheet ----------
   Opened from a bet in the feed. A banner for the bet, three headline reads, then three tabs: This bet, Their record, Who else.
   Every number is a stored field (wallets.json, live.json). The record tab's last-30-day cuts and profit curve come from the wallet's
   settled positions (build_side_cards.py wallet_sheet); a wallet file built before that shipped simply shows no 30-day lines. */
var MKT_G = {ml: 'moneyline', spread: 'spread', total: 'total'};
function sgn(v){ return v == null ? '' : (v < 0 ? '-' : '+') + usd(Math.abs(v)); }
function findBet(id){
  for (var i = 0; i < GAMES.length; i++){ var g = GAMES[i];
    for (var j = 0; j < g.pos.length; j++){ var x = g.pos[j]; if (betId(g, x) === id) return {g: g, x: x}; } }
  return null;
}
/* entry-price bands, the same cut points as ODDS_BANDS in build_side_cards.py */
var ODDS = [['dd', '+200 or longer', 0, 1 / 3], ['d2', '+150 to +199', 1 / 3, 0.4], ['d1', '+100 to +149', 0.4, 0.5], ['f1', '-100 to -149', 0.5, 0.6], ['f2', '-150 to -199', 0.6, 2 / 3], ['ff', '-200 or shorter', 2 / 3, 1.01]];
function oddsBand(px){ if (px == null) return null; for (var i = 0; i < ODDS.length; i++) if (px >= ODDS[i][2] && px < ODDS[i][3]) return ODDS[i]; return null; }
function sizeBand(r){ return r == null ? null : r < 0.75 ? 'small' : r < PRESS ? 'usual' : 'big'; }
var SIZE_LBL = {small: 'Under its usual stake', usual: 'Around its usual stake', big: '1.5x its usual or more'};
/* the five cuts of a wallet around one position: [key, title, pill, all-time cell, last-30-day cell, matcher over a curve row] */
function cuts(w, p){
  var fav = p.px == null ? null : p.px >= 0.5, ob = oddsBand(p.px), sb = sizeBand(p.press), d30 = w.d30 || {};
  return [
    ['all', w.sport.toUpperCase(), 'All bets', [w.wl[0], w.wl[1], w.roi], w.d30 ? d30.all : undefined, function(){ return true; }],
    ['mkt', w.sport.toUpperCase() + ' ' + GROUPS[p.g], 'This bet type', w.lane[p.g], w.d30 ? (d30.lane || {})[p.g] : undefined, function(r){ return r[3] === p.g; }],
    ['side', fav == null ? 'Price' : fav ? 'Favorites' : 'Underdogs', fav == null ? 'No price' : (fav ? 'Favorite' : 'Underdog') + ' · ' + cents(p.px), fav ? w.fav : w.dog, w.d30 ? (fav ? d30.fav : d30.dog) : undefined,
      function(r){ return r[4] != null && (r[4] >= 0.5) === fav; }],
    ['size', 'At this size', sb ? SIZE_LBL[sb] : 'No usual stake yet', sb ? w.size[sb] : null, w.d30 && sb ? (d30.size || {})[sb] : undefined,
      function(r){ return w.usual && r[2] > 0 && sizeBand(r[2] / w.usual) === sb; }],
    ['odds', 'At these odds', ob ? ob[1] : 'No price', ob && w.odds ? w.odds[ob[0]] : null, w.d30 && ob ? ((d30.odds || {})[ob[0]]) : undefined,
      function(r){ var b = oddsBand(r[4]); return !!(b && ob && b[0] === ob[0]); }]
  ];
}
function cutCard(c, on){
  var a = c[3], m = c[4];
  return '<button type="button" class="fw-sh-cut' + (on ? ' on' : '') + '" data-sh-cut="' + c[0] + '" aria-pressed="' + on + '"><span class="t">' + esc(c[1]) + '</span><span class="pl">' + esc(c[2]) + '</span>' +
    (a ? '<span class="r fw-num"><b>' + a[0] + '-' + a[1] + '</b><b class="' + cls(a[2]) + '">' + pct(a[2]) + '</b></span><span class="s">' + Math.round(a[0] / ((a[0] + a[1]) || 1) * 100) + '% wins, all-time' + (a[0] + a[1] < SEASONED ? ' · small sample' : '') + '</span>'
      : '<span class="s" style="margin-top:6px">No bets yet</span>') +
    '<span class="a">' + (m === undefined ? 'Last 30 days: not in this file yet' : m ? 'Last 30 days <b class="fw-num">' + m[0] + '-' + m[1] + '</b> <b class="fw-num ' + cls(m[2]) + '">' + pct(m[2]) + '</b>' : 'Last 30 days: no bets') + '</span></button>';
}
/* last 30 days of settled bets as a running total. Actual = dollars; Flat = every bet one unit (profit / stake), so a big stake does not hide the pattern. */
function curveSvg(w, S, match){
  var rows = w.curve; if (!rows) return '';
  var flat = S.cm === 'flat', hl = S.hm, end = STORE.d.built, t0 = end - 30 * 86400;
  var pts = rows.filter(function(r){ return r[0] >= t0 && (hl !== 'only' || match(r)); });
  if (!pts.length) return '<p class="fw-det-n">' + (hl === 'only' ? 'None of their last-30-day bets match this cut.' : 'No settled bets in the last 30 days.') + '</p>';
  var c = 0, xy = [[t0, 0]].concat(pts.map(function(r){ c += flat ? (r[2] > 0 ? r[1] / r[2] : 0) : r[1]; return [r[0], c]; })); xy.push([end, c]);
  var mn = Math.min.apply(null, xy.map(function(p){ return p[1]; }).concat(0)), mx = Math.max.apply(null, xy.map(function(p){ return p[1]; }).concat(0)), rg = (mx - mn) || 1;
  var W_ = 640, H_ = 150, X = function(t){ return (t - t0) / (end - t0) * W_; }, Y = function(v){ return H_ - 10 - (v - mn) / rg * (H_ - 24); };
  var d = xy.map(function(p, i){ return (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1); }).join(' '), col = c >= 0 ? 'var(--c-good)' : 'var(--c-bad)';
  var dots = hl === 'off' ? '' : pts.map(function(r, i){ return match(r) && hl === 'hl' && S.cut !== 'all' ? '<circle cx="' + X(r[0]).toFixed(1) + '" cy="' + Y(xy[i + 1][1]).toFixed(1) + '" r="4.5" fill="var(--c-gold)" stroke="var(--c-box)" stroke-width="2"/>' : ''; }).join('');
  return '<svg viewBox="0 0 ' + W_ + ' ' + H_ + '" role="img" aria-label="Running ' + (flat ? 'flat-stake' : 'dollar') + ' profit over the last 30 days, ending ' + (flat ? c.toFixed(1) + ' units' : sgn(c)) + '">' +
    '<line x1="0" x2="' + W_ + '" y1="' + Y(0).toFixed(1) + '" y2="' + Y(0).toFixed(1) + '" stroke="var(--c-line2)" stroke-dasharray="3 5"/>' +
    '<path d="' + d + ' L' + W_ + ' ' + H_ + ' L0 ' + H_ + 'Z" fill="' + col + '" opacity=".13"/><path d="' + d + '" fill="none" stroke="' + col + '" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>' + dots + '</svg>' +
    '<p class="fw-sh-n"><b>' + pts.length + ' settled ' + (pts.length === 1 ? 'bet' : 'bets') + '</b>' + (hl === 'only' ? ' matching this cut' : hl === 'hl' && S.cut !== 'all' ? ', ' + pts.filter(match).length + ' matching this cut (gold dots)' : '') + '. Shown by the day each one settled.</p>';
}
function chartHead(w, S, match){
  var rows = w.curve; if (!rows) return '';
  var flat = S.cm === 'flat', t0 = STORE.d.built - 30 * 86400, tot = 0;
  rows.forEach(function(r){ if (r[0] >= t0 && (S.hm !== 'only' || match(r))) tot += flat ? (r[2] > 0 ? r[1] / r[2] : 0) : r[1]; });
  return '<div class="fw-sh-ch-h"><h5>Profit, last 30 days</h5><span class="fw-sh-ch-v fw-num ' + cls(tot) + '">' + (flat ? (tot >= 0 ? '+' : '') + tot.toFixed(1) + ' units' : sgn(tot)) + '</span><span class="sp"></span>' +
    seg('cm', [['actual', 'Actual'], ['flat', 'Flat']], S.cm) + seg('hm', [['hl', 'Highlight'], ['only', 'Only these']], S.hm === 'off' ? 'hl' : S.hm) + '</div>';
}
function contested(g, p){
  if (CARDS.state === 'idle' || CARDS.state === 'busy') return null;
  var c = CARDS.by[g.id], m = c && c.markets && c.markets[p.g]; if (!m) return {none: true};
  var o = 0, n = 0; Object.keys(m.sides).forEach(function(s){ if (s === p.side) return; var a = (m.sides[s] || {}).all; if (a){ o += a.sharp_usd || 0; n += ((a.counts || {}).hc || 0) + ((a.counts || {}).sharp || 0); } });
  return {usd: o, n: n};
}
function sheetBody(S, g, x, w, p){
  var cs = cuts(w, p), cur = cs.filter(function(c){ return c[0] === S.cut; })[0] || cs[1], tab = S.tab;
  if (tab === 'rec'){
    var a = cur[3], m = cur[4];
    return '<div class="fw-sh-cuts">' + cs.map(function(c){ return cutCard(c, c[0] === cur[0]); }).join('') + '</div>' +
      '<div class="fw-sh-ch">' + chartHead(w, S, cur[5]) + (w.curve ? curveSvg(w, S, cur[5]) : '<p class="fw-det-n">The 30-day profit curve appears once the wallet file carries it (after the next card build).</p>') + '</div>' +
      '<div class="fw-strip" style="margin-top:14px" role="img" aria-label="Last games">' + w.legs.slice(0, 20).map(function(l){ return '<i class="' + (l[1] === 'win' ? 'w' : l[1] === 'loss' ? 'l' : '') + '"></i>'; }).join('') +
        '<span>last ' + Math.min(20, w.legs.length) + ' games, newest first</span></div>' +
      (w.clv.n ? '<p class="fw-det-n">Bought below the closing price on ' + w.clv.beat + ' of ' + w.clv.n + ' bets (' + Math.round(w.clv.beat / w.clv.n * 100) + '%).</p>' : '') +
      '<p class="fw-det-n">Record and dollar ROI in ' + w.sport.toUpperCase() + ' as of the last ledger run. Lifetime profit ' + sgn(w.pnl) + '.' + (w.n < SEASONED ? ' <b class="fw-dn">Only ' + w.n + ' graded bets: treat this record as thin.</b>' : '') + '</p>';
  }
  if (tab === 'who') return whoElse(g, p);
  var mv = p.px != null && p.px_first != null ? Math.round((p.px - p.px_first) * 100) : null, h = (p.hist || []).filter(function(y){ return y[1] > 0; });
  var plays = cur[3] ? GROUPS[p.g] + ' ' + cur[3][0] + '-' + cur[3][1] + ', ' + pct(cur[3][2]) : '';
  var lane = w.lane[p.g], sb = sizeBand(p.press), sz = sb ? w.size[sb] : null;
  return '<div class="fw-sh-3"><div><h5>Position</h5><dl class="fw-kv"><dt>Worth now</dt><dd class="fw-num">' + usd(p.usd) + '</dd>' +
      '<dt>Shares</dt><dd class="fw-num">' + (p.shares != null ? Math.round(p.shares).toLocaleString('en-US') : 'n/a') + '</dd>' +
      '<dt>Held since</dt><dd class="fw-num">' + (ct(p.since, {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}) || 'n/a') + '</dd>' +
      (p.two_way ? '<dt>Note</dt><dd class="fw-two">also holds the other side</dd>' : '') + '</dl></div>' +
    '<div><h5>Market since first seen</h5><dl class="fw-kv"><dt>First seen at</dt><dd class="fw-num">' + (cents(p.px_first) || 'n/a') + '</dd><dt>Now</dt><dd class="fw-num">' + (cents(p.px) || 'n/a') + '</dd>' +
      (mv == null ? '' : '<dt>Move</dt><dd class="fw-num ' + cls(mv) + '">' + (mv === 0 ? 'none' : (mv > 0 ? '+' : '') + mv + '¢ ' + (mv > 0 ? 'toward' : 'against')) + '</dd>') + '</dl>' +
      '<p class="fw-det-n">The price they paid is not stored. This is the market at the first scan that saw them holding it.</p></div>' +
    '<div>' + (h.length ? sizeOverTime(p) : '<h5>Size over time</h5><p class="fw-det-n">No size history yet.</p>') + '</div></div>' +
    '<div class="fw-sh-ctx"><b>Plays like this:</b> ' + (lane ? GROUPS[p.g] + ' ' + lane[0] + '-' + lane[1] + ', ' + pct(lane[2]) : 'no graded bets in this market') +
      (sz ? ' · ' + SIZE_LBL[sb].toLowerCase() + ' ' + sz[0] + '-' + sz[1] + ', ' + pct(sz[2]) : '') + (w.clv.n ? ' · beat the close on ' + Math.round(w.clv.beat / w.clv.n * 100) + '% (' + w.clv.n + ' bets)' : '') + '</div>';
}
function sheet(S, anim){
  var f = findBet(S.bet); if (!f) return '';
  var g = f.g, x = f.x, p = x.p, w = BOOK[x.k], c = contested(g, p), fol = !!FOLLOWS[x.k];
  var l30 = w.l30 && (w.l30.w + w.l30.l) ? w.l30 : null, roi30 = l30 ? l30.roi : w.l30roi;
  var K = '<div class="fw-sh-k"><div><b class="fw-num' + (p.press >= PRESS ? ' fw-up' : '') + '">' + (p.press != null ? p.press.toFixed(1) + '×' : 'n/a') + '</b><span>Their usual size</span><i class="fw-num">' + (w.usual ? 'usual ' + usd(w.usual) + ' · this ' + usd(p.usd) : 'no usual stake yet') + '</i></div>' +
    '<div><b class="fw-num ' + cls(l30 ? l30.pnl : roi30) + '">' + (l30 ? sgn(l30.pnl) : pct(roi30) || 'n/a') + '</b><span>Last 30 days' + (l30 ? '' : ' ROI') + '</span><i class="fw-num">' + (l30 ? pct(roi30) + ' ROI · ' + l30.w + '-' + l30.l : roi30 == null ? 'under 2 graded bets' : 'dollars not in this file yet') + '</i></div>' +
    '<div><b' + (c && c.usd ? ' style="color:var(--c-warn)"' : '') + '>' + (!c ? '…' : c.none ? 'No card' : c.usd ? 'Contested' : 'Uncontested') + '</b><span>The other side</span><i class="fw-num">' + (!c ? 'loading the Sharps card' : c.none ? 'no Sharps card for this market' : c.usd ? usd(c.usd) + ' hot money · ' + c.n + (c.n === 1 ? ' wallet' : ' wallets') : 'no hot money against it') + '</i></div></div>';
  var T = [['bet', 'This bet'], ['rec', 'Their record'], ['who', 'Who else']];
  return '<div class="fw-sh-scrim' + (anim ? ' fw-in' : '') + '" data-sh-scrim><div class="fw-sh' + (anim ? ' fw-in' : '') + '" role="dialog" aria-modal="true" aria-label="' + esc(w.name) + ', ' + esc(p.side) + '">' +
    '<div class="fw-sh-top"><div class="fw-sh-av" aria-hidden="true">' + esc(String(w.name).charAt(0).toUpperCase()) + '</div><div><h2>' + esc(w.name) + '</h2><p>' + w.sport.toUpperCase() + (w.rk && w.rk.tier !== 'thin' ? ' · price-' + w.rk.tier : '') + ' · ' + w.n + ' graded bets · ' + sgn(w.pnl) + ' lifetime</p></div><span class="sp"></span>' +
      '<button type="button" class="fw-sh-fol fw-press' + (fol ? ' on' : '') + '" data-sh-fol="' + x.k + '" aria-pressed="' + fol + '">' + (fol ? '★ Following' : '☆ Follow') + '</button><button type="button" class="fw-sh-x fw-press" data-sh-close aria-label="Close">×</button></div>' +
    '<div class="fw-sh-ban"><span class="m">' + GROUPS[p.g] + ' · ' + esc(teams(g.ev)) + ' · ' + gameWhen(g.gst) + '</span><span class="s">' + esc(p.side) + '<span class="fw-num">' + lineTxt(p.g, p.line) + '</span></span>' +
      '<span class="g fw-num">' + usd(p.usd) + ' now · held since ' + (ct(p.since, {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}) || 'n/a') + ' CT</span><span class="px"><b class="fw-num">' + (cents(p.px) || 'n/a') + '</b><span>price now</span></span></div>' +
    K + '<div class="fw-sh-tabs" role="tablist">' + T.map(function(t){ return '<button type="button" role="tab" aria-selected="' + (S.tab === t[0]) + '" class="' + (S.tab === t[0] ? 'on' : '') + '" data-sh-tab="' + t[0] + '">' + t[1] + '</button>'; }).join('') + '</div>' +
    '<div class="fw-sh-pan" role="tabpanel">' + sheetBody(S, g, x, w, p) + '</div>' +
    '<p class="fw-sh-n">Context only, no suggested size. Price is the market now, not what they paid: no entry price is stored.' + (CARDS.state === 'ok' ? ' <a href="#sharps" style="color:inherit">Open the Sharps cards</a>' : '') + '</p></div></div>';
}
/* price when first seen and size over time (wallets.json px_first / hist, from the holders scan's own reads). Never an entry price. */
function firstSeen(p){
  if (p.px_first == null) return '';
  var mv = p.px != null ? Math.round((p.px - p.px_first) * 100) : null;
  return '<dt>Price when first seen</dt><dd class="fw-num">' + cents(p.px_first) + '</dd>' +
    (mv == null ? '' : '<dt>Market move since</dt><dd class="fw-num ' + cls(mv) + '">' + (mv === 0 ? 'none' : (mv > 0 ? '+' : '') + mv + '¢ ' + (mv > 0 ? 'toward this side' : 'against this side')) + '</dd>');
}
function sizeOverTime(p){
  var h = (p.hist || []).filter(function(x){ return x[1] > 0; }); if (!h.length) return '';
  var n = function(v){ return Math.round(v).toLocaleString('en-US'); }, max = Math.max.apply(null, h.map(function(x){ return x[1]; }));
  var up = 0, dn = 0; (p.hist || []).forEach(function(x, i, a){ if (i){ if (x[1] > a[i - 1][1]) up++; else if (x[1] < a[i - 1][1]) dn++; } });
  var first = h[0][1], last = h[h.length - 1][1], when = function(t){ return ct(t, {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}); };
  var txt = h.length === 1 ? 'No change since it was first seen with ' + n(first) + ' shares.'
    : 'First seen with ' + n(first) + ' shares, now ' + n(last) + '. Added ' + up + (up === 1 ? ' time' : ' times') + (dn ? ', trimmed ' + dn + (dn === 1 ? ' time' : ' times') : ', never trimmed') + '.';
  return '<h5>Size over time</h5>' +
    (h.length > 1 ? '<div class="fw-sot" role="img" aria-label="Share count at each change, oldest first">' + h.map(function(x){
      return '<i style="height:' + Math.max(8, Math.round(x[1] / max * 100)) + '%" title="' + esc(when(x[0]) + ': ' + n(x[1]) + ' shares') + '"></i>'; }).join('') + '</div>' : '') +
    '<p class="fw-det-n" style="margin-top:6px">' + txt + ((p.hist || []).length >= 24 ? ' Showing the first change and the latest 23.' : '') +
    (p.cens ? ' It already held this when tracking of the market began, so it got in earlier than "held since".' : '') + '</p>';
}
function betId(g, x){ return g.id + '|' + x.k + '|' + x.p.cid; }
function feed(S){
  var out = [], lat = [], bets = 0, agree = 0, day = function(t){ return ct(t, {year: 'numeric', month: 'numeric', day: 'numeric'}); }, today = day(Date.now() / 1000);
  GAMES.forEach(function(g){ if (S.sport !== 'all' && g.sport !== S.sport) return;
    var mine = g.pos.filter(function(x){ return FOLLOWS[x.k]; }); if (!mine.length) return;
    var by = {}; mine.forEach(function(x){ var b = by[x.p.g] = by[x.p.g] || {}; (b[x.p.side] = b[x.p.side] || []).push(x); });   /* a side groups every rung of it */
    var ag = false, sp = false;
    Object.keys(by).forEach(function(k){ var sides = Object.keys(by[k]); if (sides.length > 1) sp = true;
      sides.forEach(function(s){ var who = {}; by[k][s].forEach(function(x){ who[x.k] = 1; }); if (Object.keys(who).length > 1) ag = true; }); });
    bets += mine.length; if (ag) agree++;
    (day(g.gst) === today || g.gst < Date.now() / 1000 ? out : lat).push('<article class="fw-card fw-g"><div class="fw-gh"><span class="fw-tag">' + g.sport + '</span><b>' + esc(teams(g.ev)) + '</b>' +
      (sp ? '<span class="fw-badge split">Split</span>' : ag ? '<span class="fw-badge agree">Agree</span>' : '') + '<time>' + gameWhen(g.gst) + '</time></div>' +
      ['ml', 'spread', 'total'].filter(function(k){ return by[k]; }).map(function(k){ return Object.keys(by[k]).map(function(side){
        return '<div class="fw-side"><div class="fw-side-h"><span>' + GROUPS[k] + '</span><b>' + esc(side) + '</b></div>' +
          by[k][side].sort(function(a, b){ return b.p.usd - a.p.usd; }).map(function(x){ var w = BOOK[x.k], p = x.p;
            var id = betId(g, x);
            return '<button type="button" class="fw-bet fw-press" data-bet="' + esc(id) + '" aria-haspopup="dialog"><span class="fw-chev" aria-hidden="true">›</span><span class="fw-nm">' + esc(w.name) + '</span><span class="fw-rec fw-num">' + w.wl[0] + '-' + w.wl[1] + '</span>' +
              (p.line != null ? '<span class="fw-rec fw-num">' + lineTxt(p.g, p.line).trim() + '</span>' : '') +
              '<span class="fw-usd fw-num">' + usd(p.usd) + '</span>' + xUsual(p) + '</button>'; }).join('') + '</div>'; }).join(''); }).join('') + '</article>'); });
  return {html: out.join(''), later: lat.join(''), nl: lat.length, nt: out.length, bets: bets, agree: agree};
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
/* the record a row shows: the wallet's whole sport record, or one market when a market is picked. lane is [wins, losses, dollar ROI]
   from the ledger; no lane means no graded bets in that market. */
var MKT = [['all', 'All bets'], ['ml', 'Moneyline'], ['spread', 'Spread'], ['total', 'Total']];
function stat(w, S){
  if (S.mkt === 'all') return {w: w.wl[0], l: w.wl[1], roi: w.roi, n: w.n};
  var l = w.lane[S.mkt]; return l ? {w: l[0], l: l[1], roi: l[2], n: l[0] + l[1]} : null;
}
var SORT_DIR = {name: 'asc', sport: 'asc'};
function rows(S){
  var st = {}, ws = W.filter(function(w){ if (S.sport !== 'all' && w.sport !== S.sport) return false;
    var x = st[w.k] = stat(w, S); return x && x.n > 0 && (!S.seasoned || x.n >= SEASONED); });
  var o = function(w){ return OPEN[w.k] || 0; }, f = function(w){ return FOLLOWS[w.k] ? 1 : 0; };
  var beat = function(w){ return w.clv.n ? w.clv.beat / w.clv.n : -1; };
  var pw = function(w){ var x = st[w.k]; return x.w / ((x.w + x.l) || 1); };
  var by = {open: function(a, b){ return f(b) - f(a) || o(b) - o(a) || st[b.k].n - st[a.k].n; }, roi: function(a, b){ return st[b.k].roi - st[a.k].roi; },
    n: function(a, b){ return st[b.k].n - st[a.k].n; }, clv: function(a, b){ return beat(b) - beat(a); },
    rec: function(a, b){ return pw(b) - pw(a) || st[b.k].n - st[a.k].n; }, usual: function(a, b){ return b.usual - a.usual; },
    name: function(a, b){ return String(a.name).toLowerCase() < String(b.name).toLowerCase() ? -1 : 1; },
    sport: function(a, b){ return a.sport < b.sport ? -1 : a.sport > b.sport ? 1 : 0; },
    tier: function(a, b){ var ta = a.rk ? TIER_ORD[a.rk.tier] : -1, tb = b.rk ? TIER_ORD[b.rk.tier] : -1; return (tb - ta) || ((b.rk ? b.rk.p : 0) - (a.rk ? a.rk.p : 0)) || (o(b) - o(a)); }};
  var fn = by[S.sort] || by.tier, base = SORT_DIR[S.sort] || 'desc', flip = (S.dir || base) !== base;
  ws.sort(function(a, b){ var r = fn(a, b); return flip ? -r : r; });
  ws.st = st; return ws;
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
    (w.rk && w.rk.tier !== 'thin' ? '<p class="fw-pn">Price skill: <b>' + w.rk.tier + '</b>. Its entries have beaten the close by ' + (w.rk.mean >= 0 ? '' : '-') + Math.abs(w.rk.mean * 100).toFixed(1) + ' points on average over ' + w.rk.n + ' games (the estimate is shrunk toward the average wallet).</p>' : '') +
    '<p class="fw-pn">Record and dollar ROI in ' + w.sport.toUpperCase() + ' as of the last ledger run. Lifetime profit ' + usd(Math.abs(w.pnl)).replace('$', w.pnl < 0 ? '-$' : '$') + '.' +
    (w.n < SEASONED ? ' <b class="fw-dn">Only ' + w.n + ' graded bets: treat this record as thin.</b>' : '') + '</p></div>';
}
/* the wallet's 10 newest settled results (legs are newest first): green won, red lost */
function dots(w){
  var l = w.legs.slice(0, 10).filter(function(x){ return x[1] === 'win' || x[1] === 'loss'; }); if (!l.length) return '';
  var wn = l.filter(function(x){ return x[1] === 'win'; }).length;
  return '<span class="fw-dots" role="img" aria-label="Last ' + l.length + ' settled: ' + wn + ' won, ' + (l.length - wn) + ' lost, newest first">' + l.map(function(x){ return '<i class="' + (x[1] === 'win' ? 'w' : 'l') + '"></i>'; }).join('') + '</span>';
}
/* CLV tier (scripts/pm_clv_tiers.py): price skill that held up week to week in testing. NBA and NFL only, so other sports carry no tag. */
var TIER_ORD = {sharp: 3, mid: 2, thin: 1, dull: 0};
function rkTag(w){
  var t = w.rk && w.rk.tier;
  return t === 'sharp' ? '<i class="fw-tag fw-rk sharp" title="Its entry prices have beaten the closing line by more than luck explains, using only games before today">price-sharp</i>'
    : t === 'dull' ? '<i class="fw-tag fw-rk dull" title="Its entry prices have lost to the closing line by more than luck explains">price-dull</i>'
    : w.sc ? '<i class="fw-tag fw-rk sharp" title="On the daily account scorecard\'s price-sharp list (closing-line skill after a false-discovery control). The same accounts as the Accounts page.">scorecard sharp</i>' : '';
}
function dir(S){
  var all = rows(S), ws = all.slice(0, S.shown);
  var H = function(key, label){ var on = S.sort === key, d = S.dir || SORT_DIR[key] || 'desc';
    return '<button type="button" class="fw-th' + (on ? ' on' : '') + '" data-sort="' + key + '" aria-label="Sort by ' + label + '"' + (on ? ' aria-sort="' + (d === 'asc' ? 'ascending' : 'descending') + '"' : '') + '>' + label + (on ? '<i aria-hidden="true">' + (d === 'asc' ? '↑' : '↓') + '</i>' : '') + '</button>'; };
  var head = '<div class="fw-cols"><span></span>' + H('name', 'Wallet') + '<span>Last 10</span>' + H('sport', 'Sport') + H('rec', 'Record') + H('roi', 'ROI') + H('n', 'Bets') + H('usual', 'Usual stake') + H('clv', 'Beat the close') + H('open', 'Open now') + '</div>';
  var body = ws.map(function(w){ var x = all.st[w.k], on = !!FOLLOWS[w.k], n = OPEN[w.k] || 0, beat = w.clv.n ? Math.round(w.clv.beat / w.clv.n * 100) + '%' : '';
    return '<div class="fw-row fw-press" role="button" tabindex="0" data-k="' + w.k + '" aria-expanded="' + (S.open === w.k) + '">' +
      '<span class="c-star"><button type="button" class="fw-star fw-press' + (on ? ' on' : '') + '" data-star="' + w.k + '" aria-pressed="' + on + '" aria-label="' + (on ? 'Unfollow ' : 'Follow ') + esc(w.name) + '">' + (on ? '★' : '☆') + '</button></span>' +
      '<span class="c-name fw-nm">' + esc(w.name) + (x.n < SEASONED ? '<i class="fw-thin">thin</i>' : '') + rkTag(w) + '</span>' +
      '<span class="c-dots">' + dots(w) + '</span><span><i class="fw-tag">' + w.sport + '</i></span><span class="fw-num">' + x.w + '-' + x.l + '</span>' +
      '<span class="c-roi fw-num ' + cls(x.roi) + '">' + pct(x.roi) + '</span><span class="fw-num">' + x.n + '</span><span class="fw-num">' + usd(w.usual) + '</span><span class="fw-num">' + beat + '</span>' +
      '<span class="c-open"><i class="fw-open fw-num' + (n ? ' fw-has' : '') + '">' + n + '</i></span>' +
      '<span class="c-meta fw-num">' + w.sport.toUpperCase() + (S.mkt === 'all' ? '' : ' ' + MKT.filter(function(m){ return m[0] === S.mkt; })[0][1]) + ' · ' + x.w + '-' + x.l + ' · ' + x.n + ' bets · ' + usd(w.usual) + ' usual</span></div>' +
      (S.open === w.k ? profile(w) : ''); }).join('');
  return {n: all.length, html: head + (body || '<div class="fw-empty"><b>No wallets here</b>Try another sport or market, or turn off the 20+ bets filter.</div>') +
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
  if (el._sheetOnly){
    var an = S.anim; S.anim = false; el.innerHTML = sheet(S, an); try { document.body.style.overflow = 'hidden'; } catch (e) {}
    rails(el, S); if (an){ var c0 = el.querySelector('[data-sh-close]'); if (c0) c0.focus({preventScroll: true}); } return;
  }
  if (STORE.state === 'loading'){ el.innerHTML = '<div class="fw-card fw-empty">Loading the wallets…</div>'; return; }
  if (STORE.state === 'none'){ el.innerHTML = '<div class="fw-card fw-empty"><b>The wallet file is not published yet</b>It appears after the next card build. Nothing is wrong with your follows.</div>'; return; }
  var was = S.sport;
  if (o.sport != null) S.sport = !o.sport || /^all$/i.test(o.sport) ? 'all' : String(o.sport).toLowerCase();
  if (S.sport !== was && S.sport === 'cbb'){ S.sort = 'roi'; S.seasoned = true; }   /* CBB markets are thin: open on ROI over 20+ bets; the bettor can undo either */
  var anim = S.anim; S.anim = false;
  var F = feed(S), D = dir(S), nf = Object.keys(FOLLOWS).filter(function(k){ return BOOK[k] && (S.sport === 'all' || k.split('|')[0] === S.sport); }).length;
  var y = window.scrollY;
  el.innerHTML =
    '<div class="fw-bar">' + (o.sport == null ? seg('sport', SPORTS, S.sport) : '') +
      '<span class="fw-upd">Updated ' + ct(STORE.d.built, {hour: 'numeric', minute: '2-digit'}) + ' CT · context only, no suggested size</span></div>' +
    '<div class="fw-sum"><span><b class="fw-num">' + nf + '</b>following</span><span><b class="fw-num">' + F.bets + '</b>open ' + (F.bets === 1 ? 'bet' : 'bets') + '</span>' +
      '<span><b class="fw-num">' + F.agree + '</b>' + (F.agree === 1 ? 'game' : 'games') + ' where two agree</span></div>' +
    (F.html || F.later ? '<div class="fw-h"><h2>Today\'s plays</h2><p>' + F.nt + (F.nt === 1 ? ' game' : ' games') + ' today, Central time</p></div>' +
      (F.html ? '<div class="fw-feed">' + F.html + '</div>' : '<div class="fw-card fw-empty">None of the wallets you follow have a bet on a game today.</div>') +
      (F.nl ? '<button type="button" class="fw-link fw-later" data-later aria-expanded="' + S.later + '">' + (S.later ? 'Hide' : 'Show') + ' later games · ' + F.nl + '</button>' + (S.later ? '<div class="fw-feed">' + F.later + '</div>' : '') : '') :
      '<div class="fw-card fw-empty"><b>' + (nf ? 'No open bets from your wallets right now' : 'Follow a wallet to start your feed') + '</b>' +
      (nf ? 'Their next bets land here as soon as a scan picks them up.' : 'Tap a star in the list below. Their open bets show up here.') + '</div>') +
    (nf ? '<div class="fw-h"><h2>Since you followed</h2><p>Counted forward from the day you follow each wallet. Nothing is backfilled.</p></div>' + since(S) : '') +
    '<div class="fw-h"><h2>Wallets</h2><p>' + D.n + (D.n === 1 ? ' wallet' : ' wallets') + ': hot ones (a record) and price-sharp ones (price skill)</p><span class="sp"></span><div class="fw-tools">' +
      '<label class="fw-chk"><input type="checkbox" data-seas' + (S.seasoned ? ' checked' : '') + '>20+ bets only</label>' +
      seg('mkt', MKT, S.mkt) + seg('sort', [['tier', 'Price skill'], ['open', 'Open now'], ['roi', 'ROI'], ['n', 'Bets'], ['clv', 'Beat the close']], S.sort) + '</div></div>' +
    '<div class="fw-card fw-dir" style="padding-left:0;padding-right:0">' + D.html + '</div>' +
    '<p class="fw-note"><b>How to read this.</b> Hot means 6 or more graded bets, a 55% or better win rate and a dollar ROI above 3% in that sport. That is a record, not proof of skill: in testing, hot wallets have not beaten the market going forward. ' +
      '<b>Price-sharp</b> (NBA and NFL) means the wallet\'s entry prices have beaten the closing line by more than luck explains, judged only on earlier games; price-dull is the reverse. That skill held up week to week in testing, but it is a better price, not a promise of winning picks, and these markets only show a wallet\'s buy a few minutes later. College wallets (CFB, CBB) carry no price tier: their price data is too thin to test, and in our tests college wallets did not beat the market. "Thin" marks a record under 20 bets. ' +
      'Stake is what the position is worth at the last scan, and "x usual" compares it with the wallet\'s usual stake. Price is the market\'s price now, not what the wallet paid: no entry price is stored. ' +
      '"Held since" is the first scan that saw the position, and "price when first seen" is the market\'s price at that scan. Follows are saved in this browser only. This page shows who holds what and never suggests a size.</p>' + (S.bet ? sheet(S, anim) : '');
  try { document.body.style.overflow = S.bet ? 'hidden' : ''; } catch (e) {}
  rails(el, S); window.scrollTo(0, y);
  if (anim){ var cb = el.querySelector('[data-sh-close]'); if (cb) cb.focus({preventScroll: true}); }
}
function css(){ if (document.getElementById('vfw-css')) return; var s = document.createElement('style'); s.id = 'vfw-css'; s.textContent = CSS; document.head.appendChild(s); }
function mountPage(el, o){
  o = o || {}; css();
  el.className = 'vfw' + (o.skin === 'new' ? ' vfw-new' : '');
  if (!el._fw){
    el._fw = {o: o, sport: 'all', sort: 'tier', dir: null, mkt: 'all', later: false, seasoned: false, open: null, bet: null, tab: 'bet', cut: 'mkt', cm: 'actual', hm: 'hl', anim: false, shown: PAGE, geom: {}};
    el.addEventListener('click', function(e){
      var S = el._fw, t = e.target, b;
      if ((b = t.closest('[data-bet]'))){ S.bet = b.dataset.bet; S.tab = 'bet'; S.cut = 'mkt'; S.anim = true; if (CARDS.state === 'idle') loadCards(); draw(el); return; }
      if (t.closest('[data-sh-close]') || t.matches('[data-sh-scrim]')){ S.bet = null; draw(el); return; }
      if ((b = t.closest('[data-sh-tab]'))){ S.tab = b.dataset.shTab; draw(el); return; }
      if ((b = t.closest('[data-sh-cut]'))){ S.cut = b.dataset.shCut; draw(el); return; }
      if ((b = t.closest('[data-sh-fol]'))){ var fk = b.dataset.shFol; if (FOLLOWS[fk]) delete FOLLOWS[fk]; else FOLLOWS[fk] = Math.floor(Date.now() / 1000); save(); draw(el); return; }
      if ((b = t.closest('[data-star]'))){ var k = b.dataset.star; if (FOLLOWS[k]) delete FOLLOWS[k]; else FOLLOWS[k] = Math.floor(Date.now() / 1000); save(); draw(el); return; }
      if ((b = t.closest('[data-sort]'))){ var k2 = b.dataset.sort; if (S.sort === k2) S.dir = (S.dir || SORT_DIR[k2] || 'desc') === 'asc' ? 'desc' : 'asc'; else { S.sort = k2; S.dir = null; } S.shown = PAGE; draw(el); return; }
      if (t.closest('[data-later]')){ S.later = !S.later; draw(el); return; }
      if ((b = t.closest('.fw-seg>button'))){ var id = b.parentNode.dataset.seg; S[id] = b.dataset.v; if (id === 'sort') S.dir = null; if (id !== 'sort') S.open = null; S.shown = PAGE; draw(el); return; }
      if (t.closest('[data-more]')){ S.shown += PAGE * 2; draw(el); return; }
      if ((b = t.closest('.fw-row'))){ S.open = S.open === b.dataset.k ? null : b.dataset.k; draw(el); }
    });
    el.addEventListener('change', function(e){ if (e.target.matches('[data-seas]')){ el._fw.seasoned = e.target.checked; el._fw.shown = PAGE; draw(el); } });
    el.addEventListener('keydown', function(e){ if (e.key === 'Escape' && el._fw.bet){ el._fw.bet = null; draw(el); return; } var r = e.target.closest('.fw-row'); if (r && e.target === r && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); r.click(); } });
  }
  el._fw.o = o;
  STORE.hosts = STORE.hosts.filter(function(h){ return h.el !== el && document.contains(h.el); });
  STORE.hosts.push({el: el, render: function(){ draw(el); }});
  if (!STORE.timer) STORE.timer = setInterval(function(){ if (STORE.hosts.some(function(h){ return document.contains(h.el); })){ load(); if (CARDS.state === 'ok') loadCards(); } }, 120000);
  if (STORE.state === 'loading') load();
  draw(el);
}
/* The sheet on its own, for the Sharps cards: a wallet row there names the wallet, the game, the market and the side, and this finds
   that bet in wallets.json (the wallet's largest rung of it) and opens the same sheet over the page. Resolves false when the wallet or
   the bet is not in the file (an unproven or excluded wallet), and nothing opens. */
function openSheet(q){
  css(); load();
  return new Promise(function(done){
    var go = function(){
      if (!STORE.d){ done(false); return; }
      var hit = null;
      GAMES.forEach(function(g){ if (g.ev !== q.ev || +g.gst !== +q.gst) return;
        g.pos.forEach(function(x){ if (x.k === q.sport + '|' + q.w && x.p.g === q.g && x.p.side === q.side && (!hit || x.p.usd > hit.x.p.usd)) hit = {g: g, x: x}; }); });
      if (!hit){ done(false); return; }
      closeSheet();
      var el = document.createElement('div'); el.id = 'vfw-sheet-host'; el.className = 'vfw' + (/\/new\//.test(location.pathname) ? ' vfw-new' : ''); el.style.margin = '0';
      el._sheetOnly = true; el._fw = {o: {}, bet: betId(hit.g, hit.x), tab: 'bet', cut: 'mkt', cm: 'actual', hm: 'hl', anim: true, geom: {}, sport: 'all'};
      el.addEventListener('click', function(e){
        var S = el._fw, t = e.target, b;
        if (t.closest('[data-sh-close]') || t.matches('[data-sh-scrim]')){ closeSheet(); return; }
        if ((b = t.closest('[data-sh-tab]'))){ S.tab = b.dataset.shTab; draw(el); return; }
        if ((b = t.closest('[data-sh-cut]'))){ S.cut = b.dataset.shCut; draw(el); return; }
        if ((b = t.closest('[data-sh-fol]'))){ var fk = b.dataset.shFol; if (FOLLOWS[fk]) delete FOLLOWS[fk]; else FOLLOWS[fk] = Math.floor(Date.now() / 1000); save(); draw(el); STORE.hosts.forEach(function(h){ if (h.el !== el && document.contains(h.el)) h.render(); }); return; }
        if ((b = t.closest('.fw-seg>button'))){ S[b.parentNode.dataset.seg] = b.dataset.v; draw(el); }
      });
      document.addEventListener('keydown', escClose);
      document.body.appendChild(el);
      STORE.hosts.push({el: el, render: function(){ draw(el); }});
      if (CARDS.state === 'idle') loadCards();
      draw(el); done(true);
    };
    if (STORE.state === 'loading' || STORE.busy) STORE.waiters.push(go); else go();
  });
}
function escClose(e){ if (e.key === 'Escape') closeSheet(); }
function closeSheet(){
  var el = document.getElementById('vfw-sheet-host'); if (!el) return;
  document.removeEventListener('keydown', escClose); STORE.hosts = STORE.hosts.filter(function(h){ return h.el !== el; });
  el.remove(); try { document.body.style.overflow = ''; } catch (e) {}
}
function wrap(fn, keys){
  return function(props){
    var U = window.__smKit().U, ref = U.useRef(null);
    U.useEffect(function(){ if (ref.current) fn(ref.current, props); }, keys.map(function(k){ return props[k]; }));
    return U.createElement('div', {ref: ref});
  };
}
window.VaultFollowing = {
  mountPage: mountPage, openSheet: openSheet, closeSheet: closeSheet,
  Page: wrap(function(el, p){ mountPage(el, {sport: p.sport || 'all'}); }, ['sport'])
};
})();
