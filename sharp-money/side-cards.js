/* Proven-sharps side cards for Sharp Money: the "Sharps" page and the "Proven sharps" section on a game page.
   One file for both layouts (sharp-money/index.html and sharp-money/new/index.html), so the two stay the same page.
   Data: live.json on the pm-cards-live branch, built every 10 minutes by scripts/build_side_cards.py (docs/side-cards.md).
   Until that branch exists the page says so and the game section stays hidden.

   Sharp money is context. The one exception (CLAUDE.md) is the suggested size on this card: it is shown, always labelled as an
   untested rule, and it never feeds Top Reads, SM_GATE or an agree total. The rule is the pre-registered lock of
   docs/sharp-card-prereg.md. Every number on the card is a stored field; a null prints "n/a".

   Size: the card shows SharpFlow's clean-step press ladder exactly as the builder stores it (units_clean_ladder): 3u base, 2u at a
   2x to 3x press, 5u at 3x or more, 1u for any side priced under 50 cents. SharpFlow's live picks also step the size down when the
   price has moved and add rescue rungs; the builder does not record those, so the card can read higher than SharpFlow's own pick. */
(function(){
'use strict';
var OPT = {}, UI = {}, SHOWN = {};
/* the phone layout has its own global .num and .hc rules; these undo them inside the card (lowest precedence of the card's own rules) */
var RESET = '.vsc .sc-ags{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin-top:12px;font-size:13px;color:var(--c-mut)}.vsc .sc-ags b{color:var(--c-ink);font-weight:600}.vsc .sc-ags em{font-style:normal;font-size:12px;color:var(--c-dim);margin-left:auto}.vsc .sc-tier{display:inline-flex;align-items:center;height:22px;padding:0 9px;border-radius:99px;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border:1px solid currentColor}.vsc .sc-tier.WEAK{color:var(--c-warn)}.vsc .sc-tier.LEAN{color:var(--c-gold)}.vsc .sc-tier.LOCK,.vsc .sc-tier.PREMIUM{color:var(--c-good)}.vsc .sc-tier.ELITE{color:var(--c-on-good);background:var(--c-good);border-color:var(--c-good)}.vsc .sc-v.on .sc-ags{margin-top:14px;padding-top:12px;border-top:1px solid var(--c-line)}.vsc .sc-v.on .sc-ags+.sc-ticks{border-top:0;padding-top:0;margin-top:10px}.vsc .num{min-width:0;text-align:inherit;font-size:inherit;font-weight:inherit}.vsc .hc{width:auto;margin:0;padding:0}';
var CSS = ".vsc{--c-card:#222222;--c-line:#2f2f2f;--c-line2:#3a3a3a;--c-ink:#d8d8d8;--c-mut:#999999;--c-dim:#6a6a6a;\n--c-good:#4ade80;--c-on-good:#0d2416;--c-bad:#f87171;--c-warn:#fbbf24;--c-gold:#e8c66a;\n--c-good-line:rgba(74,222,128,.55);--c-good-box:rgba(74,222,128,.06);--c-box:#2a2a2a;--c-rb-unp:#8a8f98;--c-tile:#f1f1f1;--c-tile-ink:#1a1a1a;\n--c-r:16px;--c-pad:20px;--c-mr:14px;--c-sans:var(--halaska-sans,'Geist'),-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--c-num:var(--halaska-mono,'Geist Mono'),'SF Mono',monospace;--c-num-ls:-.02em;\n--vseg-bg:#2a2a2a;--vseg-border:transparent;--vseg-ink:#999999;--vseg-on-ink:#1a1a1a;--vseg-pill:#d8d8d8;color:var(--c-ink);font-family:var(--c-sans)}\nhtml[data-shade=charcoal] .vsc{--c-card:#1b1b1b;--c-box:#242424;--c-line:#2a2a2a;--vseg-bg:#242424}\nhtml[data-theme=light] .vsc{--c-card:#ffffff;--c-line:#eeeeee;--c-line2:#dcdcdc;--c-ink:#2b2b2b;--c-mut:#777777;--c-dim:#a0a0a0;\n--c-good:#16a34a;--c-on-good:#ffffff;--c-bad:#dc2626;--c-warn:#d97706;--c-gold:#a8780a;--c-good-line:rgba(22,163,74,.5);--c-good-box:#f0fdf4;--c-box:#f5f5f5;\n--c-rb-unp:#b4b8bf;--c-tile:#f3f3f3;--c-tile-ink:#2b2b2b;--c-shadow:0 1px 2px rgba(0,0,0,.04);--vseg-bg:#f0f0f0;--vseg-ink:#888888;--vseg-on-ink:#ffffff;--vseg-pill:#3d3d3d}\n.vsc.vsc-new{--c-card:#1c1c1e;--c-line:rgba(255,255,255,.09);--c-line2:rgba(255,255,255,.16);--c-ink:#fff;--c-mut:#98989f;--c-dim:#636366;\n--c-good:#32d583;--c-on-good:#04200f;--c-bad:#ff6b6b;--c-warn:#f5b84a;--c-gold:#f0cf7a;--c-good-line:rgba(50,213,131,.55);--c-good-box:rgba(50,213,131,.07);--c-box:#2c2c2e;\n--c-rb-unp:#8e8e93;--c-tile:#f2f2f7;--c-tile-ink:#000;--c-shadow:none;--c-r:24px;--c-pad:16px;--c-bw:0px;--c-mr:18px;\n--c-sans:-apple-system,\"SF Pro Text\",Geist,system-ui,sans-serif;--c-num:\"Barlow Condensed\",\"SF Pro Rounded\",Geist,sans-serif;--c-num-ls:.01em;\n--vseg-bg:#2c2c2e;--vseg-ink:#98989f;--vseg-on-ink:#000;--vseg-pill:#fff;margin:0 16px 12px}\n.vsc.vsc-new .sc-time .num{font-size:15px}.vsc.vsc-new .sc-w .num,.vsc.vsc-new .sc-ln .num,.vsc.vsc-new .sc-tick .num{font-size:15px}.vsc.vsc-new .sc-w .sc-wr.num{font-size:13.5px}\n.vsc-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,440px),1fr));gap:16px;align-items:start}\n.vsc.vsc-new .vsc-list{grid-template-columns:minmax(0,1fr);gap:12px}\n.vsc .sl{margin:0 0 16px}\n.vsc .sc-tag{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:99px;border:1px dashed var(--c-line2);font-size:10.5px;font-weight:600;color:var(--c-mut);vertical-align:1px}\n.vsc .sc-fold{all:unset;box-sizing:border-box;cursor:pointer;display:flex;align-items:center;gap:10px;width:100%;font-size:13px;color:var(--c-mut);padding:2px 2px 0;transition:transform var(--dur-release) var(--ease-spring)}\n.vsc .sc-fold:active{transform:scale(var(--press-row));transition:transform var(--dur-press) ease-out}\n.vsc .sc-fold b{color:var(--c-ink);font-weight:600}.vsc .sc-fold span{margin-left:auto;white-space:nowrap}\n.vsc .sc-note{background:var(--c-card);border:1px dashed var(--c-line2);border-radius:var(--c-r);padding:22px 18px;text-align:center}\n.vsc .sc-note b{display:block;font-size:15px;font-weight:600}.vsc .sc-note p{margin:6px auto 0;max-width:52ch;font-size:13px;line-height:1.5;color:var(--c-mut)}\n.vsc .sc-sech{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin:0 2px 10px;font-size:15px;font-weight:600}\n.vsc .sc-sech span{font-size:12px;font-weight:500;color:var(--c-mut)}\n@media (prefers-reduced-motion:reduce){.vsc .sc-fold,.vsc .sc-fold:active{transition:none;transform:none}}\n.vsc{--ease-out:cubic-bezier(0.16,1,0.3,1); --ease-rail:cubic-bezier(0.65,0,0.35,1); --ease-spring:cubic-bezier(0.34,1.56,0.64,1); --dur-press:80ms; --dur-release:500ms; --dur-rail:400ms; --press-chip:.88; --press-btn:.94; --press-card:.975; --press-row:.99;}\n.vsc *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}\n.vsc .press{transition:transform var(--dur-release) var(--ease-spring)}\n.vsc .press:active{transform:scale(var(--press-scale,.94));transition:transform var(--dur-press) ease-out}\n.vsc .press-chip{--press-scale:var(--press-chip)}\n.vsc .press-card{--press-scale:var(--press-card)}\n.vsc .vseg{position:relative;display:inline-flex;align-items:center;flex-shrink:0;gap:2px;padding:3px;max-width:100%; background:var(--vseg-bg);border:1px solid var(--vseg-border);border-radius:9px}\n.vsc .vseg>button{position:relative;z-index:1;display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:32px;padding:0 14px; border:0;background:transparent;border-radius:6px;color:var(--vseg-ink);font-family:var(--c-sans);font-size:12.5px;font-weight:600; letter-spacing:-.01em;white-space:nowrap;cursor:pointer;transition:color .12s ease}\n.vsc .vseg>button.on{color:var(--vseg-on-ink)}\n.vsc .vseg>button:disabled{opacity:.38;cursor:default}\n.vsc .vseg.sm>button{min-height:26px;padding:0 10px;font-size:11.5px}\n.vsc .vseg .v-pill{position:absolute;z-index:0;top:3px;bottom:3px;left:0;width:0;border-radius:6px;background:var(--vseg-pill);opacity:0; transition:left var(--dur-rail) var(--ease-rail),width var(--dur-rail) var(--ease-rail)}\n.vsc .vseg.rail-noanim .v-pill{transition:none}\n@media (max-width:767px){\n.vsc .vseg>button{min-height:36px}\n.vsc .vseg.sm>button{min-height:30px}\n.vsc .vseg>button::after{content:\"\";position:absolute;inset:-4px 0}\n}\n.vsc .sc{background:var(--c-card);border:var(--c-bw,1px) solid var(--c-line);border-radius:var(--c-r);padding:var(--c-pad);color:var(--c-ink); font-family:var(--c-sans);font-size:14px;line-height:1.35;min-width:0;box-shadow:var(--c-shadow,none);display:flex;flex-direction:column;gap:10px}\n.vsc .sc .num{font-family:var(--c-num);font-variant-numeric:tabular-nums;letter-spacing:var(--c-num-ls,0)}\n.vsc .sc-body{display:flex;flex-direction:column;gap:10px}\n.vsc .sc-cap{display:block;font-size:12px;font-weight:500;color:var(--c-mut)}\n.vsc .sc-mod{background:var(--c-box);border-radius:var(--c-mr,16px);padding:16px;min-width:0}\n.vsc .sc-top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:2px 2px 4px}\n.vsc .sc-match{font-size:19px;font-weight:600;letter-spacing:-.02em}\n.vsc .sc-match i{font-style:normal;font-weight:400;color:var(--c-dim);font-size:.8em}\n.vsc .sc-time{color:var(--c-mut);font-size:13px;margin-top:2px}\n.vsc .sc-sport{color:var(--c-dim);font-weight:600;letter-spacing:.08em;font-size:11px;margin-right:8px}\n.vsc .sc-pill{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 12px;border-radius:99px;font-size:12px;font-weight:600;white-space:nowrap;flex:none}\n.vsc .sc-pill.live{color:var(--c-mut);background:var(--c-box)}\n.vsc .sc-pill.live i{width:7px;height:7px;border-radius:50%;background:var(--c-warn);animation:sc-pulse 1.8s ease-in-out infinite}\n.vsc .sc-pill.locked{background:var(--c-good);color:var(--c-on-good)}\n.vsc .sc-pill svg{width:12px;height:12px}\n.vsc .vseg.fluid{display:flex}\n.vsc .vseg.fluid>button{flex:1}\n.vsc .sc-dotu{font-size:11px;font-weight:700;padding:1px 6px;border-radius:99px;background:var(--c-good);color:var(--c-on-good)}\n.vsc .sc-v.on{background:var(--c-good-box);box-shadow:inset 0 0 0 1px var(--c-good-line)}\n.vsc .sc-v1{display:flex;align-items:center;gap:16px}\n.vsc .sc-vu{font-size:56px;font-weight:700;letter-spacing:-.05em;line-height:.9;color:var(--c-good);flex:none}\n.vsc .sc-vu small{font-size:.45em;font-weight:600;margin-left:1px;letter-spacing:0}\n.vsc .sc-vu.zero{color:var(--c-dim)}\n.vsc .sc-vt{flex:1;min-width:0}\n.vsc .sc-vt strong{display:block;font-size:24px;font-weight:700;letter-spacing:-.03em;line-height:1.15;margin-top:1px}\n.vsc .sc-v.off .sc-vt strong{color:var(--c-mut)}\n.vsc .sc-vs{display:block;font-size:13.5px;color:var(--c-mut);margin-top:3px;line-height:1.4}\n.vsc .sc-logo{width:48px;height:48px;border-radius:12px;background:var(--c-tile);display:grid;place-items:center;flex:none;overflow:hidden;font-weight:700;font-size:14px;color:var(--c-tile-ink)}\n.vsc .sc-logo img{width:78%;height:78%;object-fit:contain}\n.vsc .sc-logo.sm{width:24px;height:24px;border-radius:7px;font-size:10px}\n.vsc .sc-ticks{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:14px;padding-top:12px;border-top:1px solid var(--c-line)}\n.vsc .sc-tick{display:inline-flex;align-items:center;gap:5px;font-size:13px;color:var(--c-ink)}\n.vsc .sc-tick svg{width:13px;height:13px;flex:none;color:var(--c-good)}\n.vsc .sc-tick.no svg{color:var(--c-bad)}\n.vsc .sc-more{margin-top:10px;font-size:12.5px;color:var(--c-mut)}\n.vsc .sc-more summary{cursor:pointer;list-style:none;color:var(--c-mut);font-weight:500;display:inline-flex;align-items:center;gap:5px}\n.vsc .sc-more summary::-webkit-details-marker,.vsc .sc-dt summary::-webkit-details-marker{display:none}\n.vsc .sc-more summary::after,.vsc .sc-dt summary::after{content:\"\";width:6px;height:6px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(45deg) translateY(-2px);transition:transform .2s var(--ease-out)}\n.vsc .sc-more[open] summary::after,.vsc .sc-dt[open] summary::after{transform:rotate(225deg) translateY(-1px)}\n.vsc .sc-more p{margin:7px 0 0;line-height:1.5}\n.vsc .sc-split{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}\n.vsc .sc-st.pk{box-shadow:inset 0 0 0 1px var(--c-good-line)}\n.vsc .sc-sth{display:flex;align-items:center;gap:8px}\n.vsc .sc-sth b{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.vsc .sc-big{font-size:30px;font-weight:700;letter-spacing:-.03em;line-height:1.1;margin-top:10px}\n.vsc .sc-lns{display:flex;flex-direction:column;gap:3px;margin-top:8px;min-height:20px}\n.vsc .sc-ln{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--c-mut)}\n.vsc .sc-ln b{font-weight:600;color:var(--c-ink)}\n.vsc .sc-ln i{width:8px;height:8px;border-radius:50%;flex:none}\n.vsc .sc-ln.hc i{background:var(--c-gold)}\n.vsc .sc-ln.sharp i{background:var(--c-good)}\n.vsc .sc-ln.loser i{background:var(--c-bad)}\n.vsc .sc-ln.exc i{background:transparent;border:1.5px dashed var(--c-dim)}\n.vsc .sc-ln.exc b{color:var(--c-mut)}\n.vsc .sc-ln.none{color:var(--c-dim)}\n.vsc .sc-bar{grid-column:1 / -1;display:flex;align-items:center;height:8px}\n.vsc .sc-bar>u{width:2px;height:14px;background:var(--c-ink);border-radius:1px;flex:none}\n.vsc .sc-half{flex:1;display:flex;height:100%;gap:1px;min-width:0}\n.vsc .sc-half.l{flex-direction:row-reverse}\n.vsc .sc-half i{display:block;height:100%;flex:none}\n.vsc .sc-half.l i:last-child{border-radius:4px 0 0 4px}\n.vsc .sc-half.r i:last-child{border-radius:0 4px 4px 0}\n.vsc .sc-half .hc{background:var(--c-gold)}\n.vsc .sc-half .sharp{background:var(--c-good)}\n.vsc .sc-half .unp{background:var(--c-rb-unp)}\n.vsc .sc-half .loser{background:var(--c-bad)}\n.vsc .sc-half .exc{background:repeating-linear-gradient(90deg,var(--c-dim) 0 2px,transparent 2px 4px)}\n.vsc .sc-kp{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}\n.vsc .sc-kp b{display:block;font-size:20px;font-weight:700;letter-spacing:-.02em;white-space:nowrap}\n.vsc .sc-kp span{display:block;font-size:12px;color:var(--c-mut);margin-top:1px}\n.vsc .sc-form{display:flex;align-items:center;gap:3px;height:16px;margin-top:12px}\n.vsc .sc-form i{flex:1;max-width:14px;height:7px;border-radius:2px;background:var(--c-dim);align-self:center}\n.vsc .sc-form i.W{background:var(--c-good);align-self:flex-start}\n.vsc .sc-form i.L{background:var(--c-bad);align-self:flex-end}\n.vsc .sc-form span{font-size:12px;color:var(--c-mut);margin-left:8px;white-space:nowrap}\n.vsc .sc-dt{padding:0}\n.vsc .sc-dt summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;padding:13px 16px;font-size:14px;font-weight:600}\n.vsc .sc-dt summary em{font-style:normal;font-weight:500;color:var(--c-mut);font-size:13px;margin-right:auto}\n.vsc .sc-dt summary::after{margin-left:auto;color:var(--c-mut)}\n.vsc .sc-dt summary em+::after{margin-left:0}\n.vsc .sc-dtb{padding:0 16px 14px}\n.vsc .sc-dtb p{margin:0;font-size:12.5px;line-height:1.55;color:var(--c-mut)}\n.vsc .sc-wg{margin-bottom:12px}\n.vsc .sc-w{display:grid;grid-template-columns:14px 74px minmax(0,auto) minmax(0,1fr);gap:10px;align-items:center;min-height:34px;font-size:13px;border-top:1px solid var(--c-line)}\n.vsc .sc-wg .sc-cap{margin-bottom:6px}\n.vsc .sc-w b{font-weight:600;white-space:nowrap}\n.vsc .sc-w.agg{grid-template-columns:14px minmax(0,1fr) auto}\n.vsc .sc-w.agg b{font-weight:500;color:var(--c-mut)}\n.vsc .sc-wd{display:grid;place-items:center}\n.vsc .sc-wd i{width:8px;height:8px;border-radius:50%;background:var(--c-dim)}\n.vsc .sc-wd svg{width:13px;height:13px;color:var(--c-gold)}\n.vsc .sc-w.hc b{color:var(--c-gold)}\n.vsc .sc-w.sharp .sc-wd i{background:var(--c-good)}\n.vsc .sc-w.loser .sc-wd i{background:var(--c-bad)}\n.vsc .sc-w.unp .sc-wd i{background:var(--c-rb-unp)}\n.vsc .sc-w.exc .sc-wd i{background:transparent;border:1.5px dashed var(--c-dim)}\n.vsc .sc-wu{font-weight:600;white-space:nowrap}\n.vsc .sc-wu em{font-style:normal;font-weight:500;color:var(--c-mut);font-size:12px;margin-left:3px}\n.vsc .sc-wr{font-size:12px;color:var(--c-mut);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.vsc .sc-hist{display:flex;align-items:center;justify-content:space-between;gap:10px;padding-top:12px;border-top:1px solid var(--c-line)}\n.vsc .sc-foot{margin:2px 2px 0;font-size:12px;color:var(--c-dim);line-height:1.5}\n.vsc .sc-empty{text-align:center;padding:26px 16px}\n.vsc .sc-empty b{display:block;font-size:16px;font-weight:600}\n.vsc .sc-empty p{margin:6px auto 0;font-size:13.5px;color:var(--c-mut);max-width:34ch;line-height:1.45}\n.vsc .sl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:18px}\n.vsc .sl-t{background:var(--c-card);border:var(--c-bw,1px) solid var(--c-line);border-radius:var(--c-r);padding:16px 18px;min-width:0}\n.vsc .sl-t span{display:block;font-size:12.5px;font-weight:500;color:var(--c-mut)}\n.vsc .sl-t b{display:block;font-size:30px;font-weight:700;letter-spacing:-.03em;margin-top:2px}\n.vsc .sl-t.gold b{color:var(--c-gold)}\n.vsc .sl-t.good b{color:var(--c-good)}\n.vsc .sl-t em{display:block;font-style:normal;font-size:12.5px;color:var(--c-mut)}\n.vsc .sl-dots{display:flex;flex-wrap:wrap;gap:5px;margin:14px 0 9px}\n.vsc .sl-dots i{width:10px;height:10px;border-radius:50%;background:var(--c-line2)}\n.vsc .sl-dots i.signal{background:var(--c-good)}\n.vsc .sl-dots i.building{background:var(--c-warn)}\n@media (max-width:767px){\n.vsc .sc{gap:8px}\n.vsc .sc-body{gap:8px}\n.vsc .sc-split{gap:8px}\n.vsc .sc-mod{padding:14px}\n.vsc .sc-match{font-size:17px}\n.vsc .sc-top{flex-wrap:wrap;gap:8px}\n.vsc .sc-time{white-space:nowrap}\n.vsc .sc-pill{height:26px;padding:0 10px;font-size:11.5px}\n.vsc .sc-vu{font-size:48px}\n.vsc .sc-vt strong{font-size:21px}\n.vsc .sc-v1{gap:12px}\n.vsc .sc-v.on .sc-logo{display:none}\n.vsc .sc-big{font-size:26px}\n.vsc .sc-kp{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 8px}\n.vsc .sc-w{grid-template-columns:14px 70px minmax(0,1fr);padding:6px 0}\n.vsc .sc-wr{grid-column:2 / -1;text-align:left}\n.vsc .sc-dt{padding:0}\n.vsc .sl{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 16px 0}\n.vsc .sl-t{padding:12px 14px}\n.vsc .sl-t b{font-size:24px}\n.vsc .sl-t.clim{grid-column:1 / -1}\n}\n@media (prefers-reduced-motion:reduce){\n.vsc .press,.vsc .press:active{transition:none;transform:none}\n.vsc .vseg .v-pill,.vsc .sc-more summary::after,.vsc .sc-dt summary::after{transition:none}\n.vsc .sc-pill.live i{animation:none}\n}\n@keyframes sc-pulse{50%{opacity:.25}}";
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

function logo(name, g){
  if (name === 'Over' || name === 'Under') return '<div class="sc-logo">' + name[0] + '</div>';
  var url = OPT.logo ? OPT.logo(g, name) : null, ab = null;
  if (!url && g.sport === 'nba'){ ab = [g.vault.away, g.vault.home].filter(function(a){ return TEAMS[a] && TEAMS[a][0] === name; })[0];
    if (ab) url = 'https://a.espncdn.com/i/teamlogos/nba/500/' + TEAMS[ab][1] + '.png'; }
  var mono = esc(ab || name.replace(/[^A-Za-z0-9 ]/g, '').split(' ').map(function(w){ return w[0]; }).join('').slice(0, 3).toUpperCase());
  if (!url) return '<div class="sc-logo">' + mono + '</div>';
  return '<div class="sc-logo"><img alt="" src="' + esc(url) + '" onerror="this.replaceWith(document.createTextNode(\'' + mono + '\'))"></div>';
}
function teamName(g, side){ var ab = g.vault && g.vault[side]; return g.sport === 'nba' && TEAMS[ab] ? TEAMS[ab][0] : (ab || '?'); }
function sideOrder(g, m, key){
  var names = Object.keys(m.sides);
  if (key === 'total') return names.sort();                         /* Over, Under */
  var away = g.sport === 'nba' && TEAMS[g.vault.away] ? TEAMS[g.vault.away][0] : null;
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
/* SharpFlow's score and label for the market: the one side whose stored `ags` score is above zero, or nothing */
var TIER = {WEAK: 'Weak', LEAN: 'Lean', LOCK: 'Lock', PREMIUM: 'Prem', ELITE: 'Elite'};
function agsRow(m, names, v){
  var n = names.filter(function(x){ var a = m.sides[x][v].ags; return a && a.score > 0 && TIER[a.tier]; })[0];
  if (!n) return '';
  var a = m.sides[n][v].ags;
  return '<div class="sc-ags"><span class="sc-tier ' + a.tier + '">' + TIER[a.tier] + '</span><span><b>' + esc(n) + '</b> score <span class="num">+' + a.score.toFixed(2) +
    '</span></span><em>' + a.contributors + ' proven of ' + (a.for_n + a.against_n) + ' tracked</em></div>';
}
function verdict(g, m, key, names, v){
  var ls = shadow(m, v), S = {}; names.forEach(function(n){ S[n] = m.sides[n][v]; });
  var tick = function(ok, t){ return '<span class="sc-tick ' + (ok ? 'ok' : 'no') + '">' + (ok ? CHK : XX) + t + '</span>'; };
  if (ls){
    var q = ls.gates, u = units(ls);
    return '<section class="sc-mod sc-v on"><div class="sc-v1"><b class="sc-vu num">' + (u == null ? 'n/a' : u + '<small>u</small>') + '</b>' +
      '<div class="sc-vt"><span class="sc-cap">Suggested<span class="sc-tag">untested rule</span> ' + (g.frozen ? '· locked' : '· live until ' + ct(g.cut) + ' CT') + '</span>' +
      '<strong>' + esc(sideLabel(ls.side, key, ls)) + '</strong><span class="sc-vs">' +
      (ls.price != null ? '<span class="num">' + trim((ls.price * 100).toFixed(1)) + '¢</span> on Polymarket' + (ls.price_t ? ', read ' + ct(ls.price_t) + ' CT' : '') : 'price n/a') + '</span></div>' +
      logo(ls.side, g) + '</div>' +
      agsRow(m, names, v) + '<div class="sc-ticks">' + tick(1, '<span class="num">' + Math.round(q.share_for * 100) + '%</span> of the money') + tick(1, '<span class="num">' + q.proven_for + '</span> proven for') +
      tick(1, '<span class="num">' + q.proven_against + '</span> against') + tick(1, 'sized up' + (ls.top_press != null ? ' <span class="num">' + ls.top_press + 'x</span>' : '')) + '</div>' +
      '<details class="sc-more"><summary>How the size is set</summary><p>This is SharpFlow\'s press ladder, sized by the biggest press on the side: a press under 2x is 3u, 2x to 3x is 2u, 3x or more is 5u, and any side priced under 50\u00a2 is 1u. ' +
      'SharpFlow also lowers the size when the price has moved, which this card does not track. This rule is in its forward test and has no graded record yet.</p></details></section>';
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
    '<strong>No play</strong><span class="sc-vs">' + why + '</span></div></div>' + agsRow(m, names, v) + '</section>';
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
  if (names.some(function(n){ return m.sides[n][v].ags; })) bits.push('The score is SharpFlow\'s: it compares the average quality of the proven wallets on each side, from -1 to +1. The labels use SharpFlow\'s published cut points (above 0.781 Lean, 0.916 Lock, 0.957 Prem, 0.981 Elite; any lower positive score is Weak). Those were fitted on SharpFlow\'s picks, not Vault\'s, and the label does not set the size.');
  if (cv.two_way_dust_dropped) bits.push(cv.two_way_dust_dropped + ' two-way ' + (cv.two_way_dust_dropped === 1 ? 'wallet' : 'wallets') + ' dropped as balanced dust.');
  if (g.vault.start_gap_flag) bits.push('Start times differ by ' + g.vault.start_gap_min + ' min between Polymarket and Vault.');
  if (g.test) bits.push(g.test.counts ? 'Counts for the forward test.' : 'Does not count for the forward test: ' + g.test.why_not.join(', ') + '.');
  return h + '<details class="sc-mod sc-dt" data-d="n"' + (st.open.n ? ' open' : '') + '><summary>Data notes</summary><div class="sc-dtb"><p>' + bits.join(' ') + '</p></div></details>' +
    '<p class="sc-foot">Sharp money is context. The suggested size comes from an untested rule that is still in its forward test.</p>';
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
  /* open on the market that has a play, else the one with proven money, else the first */
  var lead = keys.filter(function(k){ return shadow(g.markets[k], 'all'); })[0] ||
    keys.filter(function(k){ var m = g.markets[k]; return Object.keys(m.sides).some(function(n){ return m.sides[n].all.sharp_usd > 0; }); })[0] || keys[0];
  var st = UI[g.ev] || (UI[g.ev] = {group: keys.indexOf(opt.group) >= 0 ? opt.group : lead, variant: 'all', open: {}});   /* survives a re-render */
  if (keys.indexOf(st.group) < 0) st.group = keys[0];
  var head = '<div class="sc-top"><div><div class="sc-match">' + esc(teamName(g, 'away')) + ' <i>at</i> ' + esc(teamName(g, 'home')) + '</div>' +
    '<div class="sc-time"><span class="sc-sport">' + g.sport.toUpperCase() + '</span><span class="num">' + ct(g.gst, true) + ' CT</span></div></div>' +
    (g.frozen ? '<div class="sc-pill locked">' + ICON.lock + 'Locked ' + ct(g.cut) + '</div>' : '<div class="sc-pill live"><i></i>Live · locks ' + ct(g.cut) + '</div>') + '</div>';
  if (!keys.length){
    el.innerHTML = head + '<div class="sc-mod sc-empty"><b>Nothing to show yet</b><p>No wallet holds $250 or more on this game. The card fills in as money arrives and locks ' + ct(g.cut, true) + ' CT.</p></div>';
    return;
  }
  if (opt.folded){ el.innerHTML = head + foldHtml(g, keys[0]); return; }
  function strip(){
    return GROUPS.map(function(x){ var m = g.markets[x[0]], ls = m && shadow(m, st.variant);
      return '<button type="button" data-v="' + x[0] + '"' + (m ? '' : ' disabled') + (x[0] === st.group ? ' class="on"' : '') + '>' + x[1] + (ls ? '<span class="sc-dotu num">' + units(ls) + 'u</span>' : '') + '</button>'; }).join('');
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
}


function units(ls){ return ls.units_clean_ladder == null ? null : String(ls.units_clean_ladder); }
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

function foldHtml(g, key){
  var m = g.markets[key], tot = Object.keys(m.sides).reduce(function(t, n){ return t + counted(m.sides[n].all); }, 0);
  return '<button type="button" class="sc-fold"><b>No proven money yet</b>' + usd(tot) + ' on the ' + GNAME[key] + '<span>Show</span></button>';
}

/* ---------- data: one fetch shared by every mount, refreshed every 2 minutes ---------- */
var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname), LIVE = /[?&]live\b/.test(location.search);
var DEV = LOCAL && (location.search.match(/[?&]cards=([^&]+)/) || [])[1];     /* localhost only: ?cards=/path/to/live.json */
var SRC = DEV ? decodeURIComponent(DEV) : LOCAL && !LIVE ? '/mocks/side-card/src/sample.json' : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-cards-live/live.json';
var STORE = {d: null, state: 'loading', busy: false, hosts: [], timer: null};
function load(){
  if (STORE.busy) return; STORE.busy = true;
  fetch(SRC + '?t=' + Math.floor(Date.now() / 120000), {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; })
    .then(function(j){
      STORE.busy = false;
      var changed = !STORE.d || !j || j.built !== STORE.d.built || STORE.state === 'loading';
      if (j && j.games) STORE.d = j;
      STORE.state = STORE.d ? 'ok' : 'none';
      STORE.hosts = STORE.hosts.filter(function(h){ return document.contains(h.el); });
      if (changed) STORE.hosts.forEach(function(h){ h.render(); });
    });
}
function host(el, render){
  STORE.hosts = STORE.hosts.filter(function(h){ return h.el !== el && document.contains(h.el); });
  STORE.hosts.push({el: el, render: render});
  if (!STORE.timer){ STORE.timer = setInterval(function(){ if (STORE.hosts.some(function(h){ return document.contains(h.el); })) load(); }, 120000); }
  if (STORE.state === 'loading') load();
  render();
}
function css(){
  if (document.getElementById('vsc-css')) return;
  var s = document.createElement('style'); s.id = 'vsc-css'; s.textContent = RESET + CSS; document.head.appendChild(s);
}
function rootClass(el, o){ el.className = 'vsc' + (o.skin === 'new' ? ' vsc-new' : ''); }
function card(g, o, folded){
  var el = document.createElement('div'); el.className = 'sc';
  mount(el, g, {folded: folded, group: o.group});
  if (folded) el.addEventListener('click', function(e){ if (e.target.closest('.sc-fold')){ SHOWN[g.ev] = 1; el.replaceWith(card(g, o, false)); } });
  return el;
}

/* the Sharps page: slate strip, then every upcoming game. Signal first, then building, then quiet (folded) */
function mountPage(el, o){
  o = o || {}; css(); rootClass(el, o);
  host(el, function(){
    OPT = o;
    if (STORE.state === 'loading'){ el.innerHTML = '<div class="sc-note"><b>Loading the cards</b></div>'; return; }
    if (STORE.state === 'none'){ el.innerHTML = '<div class="sc-note"><b>No cards yet</b><p>Proven sharps cards start once the Polymarket holders log is running. Nothing is shown until then.</p></div>'; return; }
    var sp = o.sport && o.sport !== 'all' ? o.sport : null, rank = {signal: 0, building: 1, quiet: 2};
    var games = STORE.d.games.filter(function(g){ return !sp || g.sport === sp; }).map(function(g){ return {g: g, c: climate(g, 'all')}; })
      .sort(function(a, b){ return (rank[a.c] - rank[b.c]) || (a.g.gst - b.g.gst); });
    el.innerHTML = '';
    if (!games.length){ el.innerHTML = '<div class="sc-note"><b>No upcoming games</b><p>No card has been built for this sport yet.</p></div>'; return; }
    var sl = document.createElement('div'); sl.className = 'sl'; slate(sl, {games: games.map(function(x){ return x.g; })}); el.appendChild(sl);
    var list = document.createElement('div'); list.className = 'vsc-list';
    games.forEach(function(x){ list.appendChild(card(x.g, o, x.c === 'quiet' && !SHOWN[x.g.ev] && Object.keys(x.g.markets).length > 0)); });
    el.appendChild(list);
    [].forEach.call(el.querySelectorAll('.vseg'), function(s){ rail(s, false); });
  });
}
/* the game page section: the one card whose Vault game key matches, or nothing */
function mountGame(el, key, o){
  o = o || {}; css(); rootClass(el, o);
  host(el, function(){
    OPT = o;
    var g = STORE.d && STORE.d.games.filter(function(x){ return x.vault && x.vault.key === key; })[0];
    el.innerHTML = ''; el.style.display = g ? '' : 'none';
    if (!g) return;
    var h = document.createElement('div'); h.className = 'sc-sech'; h.innerHTML = 'Proven sharps<span>who holds each side on Polymarket</span>'; el.appendChild(h);
    el.appendChild(card(g, o, false));
    [].forEach.call(el.querySelectorAll('.vseg'), function(s){ rail(s, false); });
  });
}
/* the classic layout is a React bundle: thin wrappers that hand a div to the mounts above */
function wrap(fn, keys){
  return function(props){
    var U = window.__smKit().U, ref = U.useRef(null);
    U.useEffect(function(){ if (ref.current) fn(ref.current, props); }, keys.map(function(k){ return props[k]; }));
    return U.createElement('div', {ref: ref});
  };
}
window.VaultSideCards = {
  mountPage: mountPage, mountGame: mountGame, load: load,
  Page: wrap(function(el, p){ mountPage(el, {sport: p.sport}); }, ['sport']),
  Game: wrap(function(el, p){ mountGame(el, p.gameKey, {}); }, ['gameKey'])
};
})();
