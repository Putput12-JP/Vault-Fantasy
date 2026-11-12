/* Proven-sharps side cards for Sharp Money: the "Sharps" page and the "Proven sharps" section on a game page.
   One file for both layouts (sharp-money/index.html and sharp-money/new/index.html), so the two stay the same page.
   Vault NBA loads the same file for its Proven Sharps page (nba/ui/projections.template.html, skin 'nba').
   Data: live.json on the pm-cards-live branch, built every 10 minutes by scripts/build_side_cards.py (docs/side-cards.md).
   Until that branch exists the page says so and the game section stays hidden.

   Sharp money is context. The one exception (CLAUDE.md) is the suggested size on this card: it is shown, always labelled as an
   untested rule, and it never feeds Top Reads, SM_GATE or an agree total. The rule is the pre-registered lock of
   docs/sharp-card-prereg.md. Every number on the card is a stored field; a null prints "n/a".

   Size: the card shows the benchmark's clean-step press ladder exactly as the builder stores it (units_clean_ladder): 3u base, 2u at a
   2x to 3x press, 5u at 3x or more, 1u for any side priced under 50 cents. The benchmark's live picks also step the size down when the
   price has moved and add rescue rungs; the builder does not record those, so the card can read higher than the benchmark's own pick. */
(function(){
'use strict';
var OPT = {}, UI = {}, SHOWN = {};
/* Vault NBA skin: every colour comes from the NBA page's own theme variables, so light, dark and charcoal follow the page */
var STEAM_CSS = '.vsc .vc-steam{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;margin-top:12px;font-size:13px}\n.vsc .vc-steam i{width:8px;height:8px;border-radius:50%;background:var(--c-dim);flex:none}\n.vsc .vc-steam.on i{background:var(--c-warn)}.vsc .vc-steam.off i{background:var(--c-mut)}.vsc .vc-steam.unknown i{background:transparent;border:1.5px dashed var(--c-dim)}\n.vsc .vc-steam b{font-weight:600}.vsc .vc-steam span{color:var(--c-mut)}\n.vd-pin{margin-top:12px;padding-top:12px;border-top:1px solid var(--c-line)}\n.vd-kv{display:flex;justify-content:space-between;gap:12px;padding:5px 0;font-size:13px}.vd-kv span{color:var(--c-mut);flex:none}.vd-kv b{font-weight:500;text-align:right}\n.vd-chain{margin:6px 0 0;padding-left:18px;font-size:13px;line-height:1.5;color:var(--c-ink)}.vd-chain li{margin:2px 0}\n';
/* HC +N: proven wallets sized up (1.5x+) on a side minus those on the other side, from the stored counts.hc. Context only. */
var HC_CSS = '.vsc .vc-hc{margin-left:auto;display:inline-flex;align-items:center;gap:4px;height:22px;padding:0 8px;border-radius:99px;font-size:11px;font-weight:700;letter-spacing:.02em;white-space:nowrap;flex:none;color:var(--c-gold);border:1px solid currentColor}\n.vsc .vc-hc svg{width:11px;height:11px;flex:none}.vsc .vc-hc.x2{border-width:1.5px;background:color-mix(in srgb,var(--c-gold) 16%,transparent)}\n@media (max-width:767px){.vsc .vc-sth{flex-wrap:wrap;row-gap:6px}.vsc .vc-sth b{flex-shrink:0;max-width:calc(100% - 32px)}}\n';
var RECORD_CSS = '.vsc .vr-view{margin:0 0 16px}\n.vsc .vr{display:flex;flex-direction:column;gap:14px;max-width:880px}\n.vsc .vr-head{display:flex;justify-content:space-between;align-items:center;gap:12px;min-height:32px}\n.vsc .vr-upd{font-size:12.5px;color:var(--c-dim)}\n.vsc .vr-score{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}\n.vsc .vr-tile{background:var(--c-card);border:var(--c-bw,1px) solid var(--c-line);border-radius:var(--c-r);padding:20px 20px 18px;min-width:0}\n.vsc .vr-tile.lead{box-shadow:inset 0 0 0 1px var(--c-good-line)}\n.vsc .vr-th{display:flex;justify-content:space-between;align-items:center;gap:8px;min-height:22px}\n.vsc .vr-th b{font-size:14px;font-weight:600}\n.vsc .vr-lead{font-size:11.5px;font-weight:600;color:var(--c-good);background:var(--c-good-box);padding:3px 8px;border-radius:7px;white-space:nowrap}\n.vsc .vr-big{font-size:44px;font-weight:700;letter-spacing:-.04em;line-height:1;margin:14px 0 8px}\n.vsc .vr-big.up{color:var(--c-good)}.vsc .vr-big.dn{color:var(--c-bad)}.vsc .vr-big.dim{color:var(--c-dim)}\n.vsc .vr-ts{margin:0;font-size:14px;color:var(--c-ink)}\n.vsc .vr-tsub{margin:4px 0 0;font-size:12.5px;color:var(--c-mut);text-wrap:pretty}\n.vsc .vr-note{margin:-2px 2px 0;font-size:12.5px;line-height:1.5;color:var(--c-mut);max-width:65ch;text-wrap:pretty}\n.vsc .vr-card{background:var(--c-card);border:var(--c-bw,1px) solid var(--c-line);border-radius:var(--c-r);padding:18px 20px}\n.vsc .vr-card h3{margin:0;font-size:14px;font-weight:600;letter-spacing:-.01em}\n.vsc .vr-grid{display:grid;grid-template-columns:minmax(80px,1fr) minmax(0,1.2fr) minmax(0,1.2fr);margin-top:10px}\n.vsc .vr-grid>span{padding:10px 0;border-top:1px solid var(--c-line);font-size:13.5px;display:flex;align-items:baseline;gap:10px;min-width:0}\n.vsc .vr-grid>.vr-col{border-top:0;padding-top:0;font-size:12px;color:var(--c-mut)}.vsc .vr-grid>span:first-child{border-top:0;padding-top:0}\n.vsc .vr-mk{color:var(--c-mut)}.vsc .vr-c em{font-style:normal;font-size:12.5px;color:var(--c-mut)}.vsc .vr-c em.up{color:var(--c-good)}.vsc .vr-c em.dn{color:var(--c-bad)}\n.vsc .vr-none{color:var(--c-dim)}\n.vsc .vr-fh{display:flex;justify-content:space-between;align-items:baseline}.vsc .vr-fh span{font-size:13px;color:var(--c-mut)}\n.vsc .vr-bar{height:6px;border-radius:3px;background:var(--c-box);margin:12px 0 10px;overflow:hidden}.vsc .vr-bar i{display:block;height:100%;min-width:3px;border-radius:3px;background:var(--c-good)}\n.vsc .vr-fs{margin:0;font-size:14px}\n.vsc .vr-fn{margin:6px 0 0;font-size:12.5px;line-height:1.5;color:var(--c-mut);max-width:65ch}.vsc .vr-fn b.dn{color:var(--c-bad);font-weight:600}\n.vsc .vr-games{margin-top:6px}\n.vsc .vr-g{display:grid;grid-template-columns:minmax(110px,170px) minmax(0,1fr);gap:4px 16px;padding:12px 0;border-top:1px solid var(--c-line)}.vsc .vr-g:first-child{border-top:0}\n.vsc .vr-gn b{display:block;font-size:13.5px;font-weight:600}.vsc .vr-gn span{font-size:12px;color:var(--c-dim)}\n.vsc .vr-gp{display:flex;flex-direction:column;gap:6px;min-width:0}\n.vsc .vr-pl{display:grid;grid-template-columns:52px minmax(0,1fr) auto 24px;align-items:center;gap:10px;font-size:13.5px}\n.vsc .vr-pl b{font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.vsc .vr-u{font-size:12.5px;color:var(--c-mut)}\n.vsc .vr-who{font-size:11px;font-weight:600;letter-spacing:.02em;color:var(--c-mut)}.vsc .vr-who.vault,.vsc .vr-who.lock{color:var(--c-ink)}\n.vsc .vr-res{display:inline-grid;place-items:center;width:24px;height:22px;border-radius:6px;font-size:11.5px;font-weight:700}\n.vsc .vr-res.win{background:var(--c-good);color:var(--c-on-good)}.vsc .vr-res.loss{background:var(--c-bad);color:#fff}.vsc .vr-res.push,.vsc .vr-res.na{background:var(--c-box);color:var(--c-mut)}\n.vsc .vr-more{all:unset;box-sizing:border-box;cursor:pointer;display:block;width:100%;margin-top:10px;padding:10px;border-radius:10px;text-align:center;font-size:13px;font-weight:600;color:var(--c-mut);background:var(--c-box);transition:color .15s ease}\n.vsc .vr-more:hover{color:var(--c-ink)}.vsc .vr-more:focus-visible{outline:2px solid var(--c-ink);outline-offset:2px}\n.vsc .vr-notes{padding:4px 2px}.vsc .vr-notes summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--c-mut);list-style:none;display:inline-flex;align-items:center;gap:6px}\n.vsc .vr-notes summary::-webkit-details-marker{display:none}\n.vsc .vr-notes summary::after{content:"";width:6px;height:6px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(45deg) translateY(-2px);transition:transform .2s var(--ease-out)}\n.vsc .vr-notes[open] summary::after{transform:rotate(225deg) translateY(-1px)}\n.vsc .vr-notes ul{margin:10px 0 0;padding-left:18px;font-size:12.5px;line-height:1.6;color:var(--c-mut);max-width:70ch}\n.vsc .vr-skel{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}.vsc .vr-skel.tall{grid-template-columns:1fr}\n.vsc .vr-skel i{display:block;height:132px;border-radius:var(--c-r);background:var(--c-card);border:1px solid var(--c-line)}.vsc .vr-skel.tall i{height:180px}\n@media (max-width:767px){\n.vsc .vr{gap:12px}.vsc .vr-score{gap:8px}.vsc .vr-tile{padding:16px}.vsc .vr-big{font-size:34px;margin:12px 0 6px}\n.vsc .vr-ts{font-size:13px}.vsc .vr-card{padding:16px}\n.vsc .vr-g{grid-template-columns:1fr;gap:6px}.vsc .vr-pl{grid-template-columns:48px minmax(0,1fr) auto 24px;gap:8px}\n.vsc .vr-grid>span{gap:6px;flex-wrap:wrap}\n}\n@media (prefers-reduced-motion:reduce){.vsc .vr-notes summary::after,.vsc .vr-more{transition:none}}\n.vsc .vr-st{display:inline-block;margin-top:6px;padding:2px 8px;border-radius:7px;font-size:11.5px;font-weight:600;white-space:nowrap}.vsc .vr-st.live{color:var(--c-mut);background:var(--c-box)}.vsc .vr-st.lock{color:var(--c-ink);background:var(--c-box)}.vsc .vr-st.wait{color:var(--c-warn);background:color-mix(in srgb,var(--c-warn) 12%,transparent)}.vsc .vr-res.open{background:transparent;border:1.5px dashed var(--c-line2)}.vsc .vr-gn{display:flex;flex-direction:column;align-items:flex-start}\n';
var DETAIL = '.vd-wrap{position:fixed;inset:0;z-index:1000;margin:0!important;--ease-sheet:cubic-bezier(0.32,0.72,0,1)}\n.vd-scrim{position:absolute;inset:0;background:rgba(0,0,0,.55);opacity:0;transition:opacity .2s ease}\n.vd-wrap.on .vd-scrim{opacity:1}\n.vd{position:absolute;top:0;right:0;bottom:0;width:min(560px,100%);overflow-y:auto;overscroll-behavior:contain;background:var(--c-card);color:var(--c-ink);font-family:var(--c-sans);font-size:14px;line-height:1.4;padding:20px 20px 32px;border-left:1px solid var(--c-line);transform:translateX(100%);transition:transform var(--dur-rail,400ms) var(--ease-sheet)}\n.vd-wrap.on .vd{transform:none}\n.vd .num{font-family:var(--c-num);font-variant-numeric:tabular-nums;letter-spacing:var(--c-num-ls,0)}\n.vd .vd-cap{display:block;font-size:11.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--c-mut)}\n.vd-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}\n.vd-top h2{margin:6px 0 4px;font-size:26px;font-weight:700;letter-spacing:-.03em;line-height:1.1}\n.vd-px{display:flex;align-items:baseline;gap:10px;font-size:15px}.vd-px b{font-size:20px}.vd-px span{color:var(--c-mut)}\n.vd-px em{font-style:normal;font-weight:600;color:var(--c-mut)}.vd-px em.up{color:var(--c-good)}.vd-px em.dn{color:var(--c-bad)}\n.vd-sub{display:block;margin-top:3px;font-size:12.5px;color:var(--c-dim)}\n.vd-x{all:unset;box-sizing:border-box;cursor:pointer;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;background:var(--c-box);color:var(--c-mut);flex:none}\n.vd-x svg{width:16px;height:16px}.vd-x:focus-visible{outline:2px solid var(--c-ink);outline-offset:2px}\n.vd-hero{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;margin-top:18px}\n.vd-hero b{font-size:40px;font-weight:700;letter-spacing:-.04em;line-height:1}\n.vd-op{margin-left:10px;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}.vd-op.ok{color:var(--c-good)}.vd-op.no{color:var(--c-warn)}\n.vd-u{text-align:right}.vd-u b{display:block;font-size:24px;color:var(--c-gold)}\n.vd-mix{display:flex;height:6px;border-radius:3px;overflow:hidden;background:var(--c-box);margin-top:12px;gap:1px}\n.vd-mix i{display:block;height:100%}.vd-mix .sharp{background:var(--c-good)}.vd-mix .unp{background:var(--c-rb-unp)}.vd-mix .loser{background:var(--c-bad)}\n.vd-mixl{display:flex;gap:14px;margin-top:6px;font-size:12px;color:var(--c-mut)}\n.vd-sec,.vd-lead{margin-top:18px;padding:16px;border-radius:var(--c-mr,14px);background:var(--c-box)}\n.vd-key{display:flex;flex-wrap:wrap;gap:4px 12px;margin:8px 0 4px;font-size:12px;color:var(--c-mut)}\n.vd-key span{display:inline-flex;align-items:center;gap:5px}.vd-key em{font-style:normal;margin-left:auto;color:var(--c-dim)}\n.vd-key i{width:9px;height:9px;border-radius:50%}.vd-key .sharp{background:var(--c-good)}.vd-key .gold{background:var(--c-gold)}\n.vd-key .unp{background:transparent;border:1.5px dashed var(--c-rb-unp)}.vd-key .loser{background:var(--c-bad)}.vd-key .opp{background:transparent;border:1.5px solid var(--c-mut)}\n.vd-sc{display:block;width:100%;height:auto;margin-top:4px}\n.vd-sc .gl{stroke:var(--c-line2);stroke-width:1}.vd-sc .gl.z{stroke:var(--c-mut);stroke-dasharray:3 4}\n.vd-sc .ax{fill:var(--c-dim);font-size:11px;font-family:var(--c-num)}.vd-sc .axt{fill:var(--c-mut);font-size:11.5px;font-family:var(--c-sans)}\n.vd-sc .b circle{stroke-width:1.5;fill-opacity:.85}.vd-sc .b.sharp circle{fill:var(--c-good);stroke:var(--c-good)}.vd-sc .b.gold circle{fill:var(--c-gold);stroke:var(--c-gold)}\n.vd-sc .b.unp circle{fill:var(--c-rb-unp);fill-opacity:.25;stroke:var(--c-rb-unp);stroke-dasharray:3 3}.vd-sc .b.loser circle{fill:var(--c-bad);stroke:var(--c-bad)}\n.vd-sc .b.opp circle{fill-opacity:0}.vd-sc .bl{fill:var(--c-gold);font-size:13px;font-weight:700;font-family:var(--c-num)}\n.vd-held{margin:8px 0 0;font-size:12px;line-height:1.5;color:var(--c-mut)}\n.vd-lead{box-shadow:inset 3px 0 0 var(--c-gold)}\n.vd-lh{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-top:8px}\n.vd-lh b{font-size:18px}.vd-lu{text-align:right}.vd-lu b{display:block;font-size:24px;color:var(--c-gold)}.vd-lu span{font-size:12px;color:var(--c-mut)}\n.vd-tag{display:inline-block;margin-left:8px;padding:1px 8px;border-radius:99px;font-size:11px;font-weight:700;vertical-align:2px;border:1px solid currentColor}\n.vd-tag.sharp{color:var(--c-good)}.vd-tag.gold{color:var(--c-gold)}.vd-tag.unp{color:var(--c-mut)}.vd-tag.loser{color:var(--c-bad)}\n.vd-two{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}\n.vd-box{padding:12px;border-radius:12px;background:var(--c-card);min-width:0}.vd-box b{display:block;font-size:24px;margin-top:4px}.vd-box span.num{font-size:12.5px;color:var(--c-mut)}\n.vd-box.good{box-shadow:inset 0 0 0 1px var(--c-good-line)}.vd-box.good b{color:var(--c-good)}\n.vd-size{margin-top:14px}.vd-szh{display:flex;justify-content:space-between;align-items:baseline;font-size:12.5px;color:var(--c-mut)}.vd-szh b{color:var(--c-good);font-size:15px}\n.vd-bar{position:relative;height:6px;border-radius:3px;background:var(--c-card);margin:8px 0 6px}.vd-bar i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--c-good)}\n.vd-bar u{position:absolute;top:-3px;width:2px;height:12px;background:var(--c-ink)}\n.vd-size p{margin:6px 0 0;font-size:12.5px;color:var(--c-mut)}\n.vd-who{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}\n.vd-col{padding:12px;border-radius:12px;background:var(--c-card);min-width:0;border-top:2px solid var(--c-bad)}.vd-col.own{border-top-color:var(--c-good)}\n.vd-ch{display:flex;justify-content:space-between;align-items:baseline}.vd-ch b{font-size:16px}.vd-cn{display:block;margin:2px 0 6px;font-size:15px}\n.vd-w{display:grid;grid-template-columns:8px minmax(0,1fr) auto;gap:8px;align-items:center;padding:7px 0;border-top:1px solid var(--c-line)}\n.vd-w>i{width:8px;height:8px;border-radius:50%;background:var(--c-dim)}.vd-w.sharp>i{background:var(--c-good)}.vd-w.gold>i{background:var(--c-gold)}.vd-w.loser>i{background:var(--c-bad)}\n.vd-w.unp>i{background:transparent;border:1.5px dashed var(--c-rb-unp)}\n.vd-w b{font-size:13px}.vd-w div span{display:block;font-size:11.5px;color:var(--c-mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.vd-wr{text-align:right}.vd-wr span{display:block;font-size:11.5px;color:var(--c-mut)}\n.vd-none,.vd-more{margin:6px 0 0;font-size:12px;color:var(--c-dim)}\n.vd-p{margin:8px 0 0;font-size:13px;line-height:1.5;color:var(--c-mut)}.vd-p b{color:var(--c-ink)}\n.vd-foot{margin:16px 2px 0;font-size:12px;color:var(--c-dim);line-height:1.5}\n.vsc .vc-open{all:unset;box-sizing:border-box;cursor:pointer;display:flex;align-items:center;justify-content:center;width:100%;min-height:40px;margin-top:14px;border-radius:12px;background:var(--c-card);border:1px solid var(--c-line2);font-size:13.5px;font-weight:600;color:var(--c-ink)}\n.vsc .vc-open:focus-visible{outline:2px solid var(--c-ink);outline-offset:2px}\n@media (max-width:767px){\n.vd{top:6vh;width:100%;border-left:0;border-radius:20px 20px 0 0;padding:18px 16px 28px;transform:translateY(100%)}\n.vd-top h2{font-size:23px}.vd-hero b{font-size:34px}\n.vd-who{grid-template-columns:1fr}\n.vd-sec,.vd-lead{padding:14px}\n}\n@media (prefers-reduced-motion:reduce){.vd,.vd-scrim{transition:none}}\n';
var NBA = 'html .vsc.vsc-nba{--c-card:var(--surface);--c-box:var(--surface2,var(--raised));--c-line:var(--border);--c-line2:var(--border2);--c-ink:var(--fg);--c-mut:var(--fg2);--c-dim:var(--fg3);' +
  '--c-good:var(--up);--c-on-good:var(--bg);--c-bad:var(--down);--c-warn:var(--warn);--c-gold:#e5c877;--c-good-line:color-mix(in srgb,var(--up) 50%,transparent);--c-good-box:color-mix(in srgb,var(--up) 7%,transparent);' +
  '--c-rb-unp:var(--fg3);--c-tile:#f3f4f6;--c-tile-ink:#0b0c0e;--c-r:var(--r-card,16px);--c-pad:22px;--c-mr:12px;--c-shadow:none;--c-sans:var(--font-sans);--c-num:var(--font-mono);--c-num-ls:-.02em;' +
  '--vseg-bg:var(--surface2,var(--raised));--vseg-border:transparent;--vseg-ink:var(--fg2);--vseg-on-ink:var(--on-primary);--vseg-pill:var(--primary)}' +
  'html[data-theme=light] .vsc.vsc-nba{--c-gold:#8a6400;--c-tile:#ebebee;--c-tile-ink:#1d1e22}html .vsc.vsc-nba .vsc-list{grid-template-columns:repeat(auto-fill,minmax(min(100%,400px),1fr))}@media (max-width:767px){html .vsc.vsc-nba{--c-pad:16px}}';
/* the phone layout has its own global .num and .hc rules; these undo them inside the card (lowest precedence of the card's own rules) */
var RESET = '.vsc .vc-why{margin:12px 0 0;font-size:13px;line-height:1.45;color:var(--c-mut)}.vsc .vc-ags{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin-top:12px;font-size:13px;color:var(--c-mut)}.vsc .vc-ags b{color:var(--c-ink);font-weight:600}.vsc .vc-ags em{font-style:normal;font-size:12px;color:var(--c-dim);margin-left:auto}.vsc .vc-tier{display:inline-flex;align-items:center;height:22px;padding:0 9px;border-radius:99px;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border:1px solid currentColor}.vsc .vc-tier.WEAK{color:var(--c-warn)}.vsc .vc-tier.LEAN{color:var(--c-gold)}.vsc .vc-tier.LOCK,.vsc .vc-tier.PREMIUM{color:var(--c-good)}.vsc .vc-tier.ELITE{color:var(--c-on-good);background:var(--c-good);border-color:var(--c-good)}.vsc .vc-v.on .vc-ags{margin-top:14px;padding-top:12px;border-top:1px solid var(--c-line)}.vsc .vc-v.on .vc-ags+.vc-ticks{border-top:0;padding-top:0;margin-top:10px}.vsc .num{min-width:0;text-align:inherit;font-size:inherit;font-weight:inherit}.vsc .hc{width:auto;margin:0;padding:0}';
var CSS = ".vsc{--c-card:#222222;--c-line:#2f2f2f;--c-line2:#3a3a3a;--c-ink:#d8d8d8;--c-mut:#999999;--c-dim:#6a6a6a;\n--c-good:#4ade80;--c-on-good:#0d2416;--c-bad:#f87171;--c-warn:#fbbf24;--c-gold:#e8c66a;\n--c-good-line:rgba(74,222,128,.55);--c-good-box:rgba(74,222,128,.06);--c-box:#2a2a2a;--c-rb-unp:#8a8f98;--c-tile:#f1f1f1;--c-tile-ink:#1a1a1a;\n--c-r:16px;--c-pad:20px;--c-mr:14px;--c-sans:var(--halaska-sans,'Geist'),-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--c-num:var(--halaska-mono,'Geist Mono'),'SF Mono',monospace;--c-num-ls:-.02em;\n--vseg-bg:#2a2a2a;--vseg-border:transparent;--vseg-ink:#999999;--vseg-on-ink:#1a1a1a;--vseg-pill:#d8d8d8;color:var(--c-ink);font-family:var(--c-sans)}\nhtml[data-shade=charcoal] .vsc{--c-card:#1b1b1b;--c-box:#242424;--c-line:#2a2a2a;--vseg-bg:#242424}\nhtml[data-theme=light] .vsc{--c-card:#ffffff;--c-line:#eeeeee;--c-line2:#dcdcdc;--c-ink:#2b2b2b;--c-mut:#777777;--c-dim:#a0a0a0;\n--c-good:#16a34a;--c-on-good:#ffffff;--c-bad:#dc2626;--c-warn:#d97706;--c-gold:#a8780a;--c-good-line:rgba(22,163,74,.5);--c-good-box:#f0fdf4;--c-box:#f5f5f5;\n--c-rb-unp:#b4b8bf;--c-tile:#f3f3f3;--c-tile-ink:#2b2b2b;--c-shadow:0 1px 2px rgba(0,0,0,.04);--vseg-bg:#f0f0f0;--vseg-ink:#888888;--vseg-on-ink:#ffffff;--vseg-pill:#3d3d3d}\n.vsc.vsc-new{--c-card:#1c1c1e;--c-line:rgba(255,255,255,.09);--c-line2:rgba(255,255,255,.16);--c-ink:#fff;--c-mut:#98989f;--c-dim:#636366;\n--c-good:#32d583;--c-on-good:#04200f;--c-bad:#ff6b6b;--c-warn:#f5b84a;--c-gold:#f0cf7a;--c-good-line:rgba(50,213,131,.55);--c-good-box:rgba(50,213,131,.07);--c-box:#2c2c2e;\n--c-rb-unp:#8e8e93;--c-tile:#f2f2f7;--c-tile-ink:#000;--c-shadow:none;--c-r:24px;--c-pad:16px;--c-bw:0px;--c-mr:18px;\n--c-sans:-apple-system,\"SF Pro Text\",Geist,system-ui,sans-serif;--c-num:\"Barlow Condensed\",\"SF Pro Rounded\",Geist,sans-serif;--c-num-ls:.01em;\n--vseg-bg:#2c2c2e;--vseg-ink:#98989f;--vseg-on-ink:#000;--vseg-pill:#fff;margin:0 16px 12px}\n.vsc.vsc-new .vc-time .num{font-size:15px}.vsc.vsc-new .vc-w .num,.vsc.vsc-new .vc-ln .num,.vsc.vsc-new .vc-tick .num{font-size:15px}.vsc.vsc-new .vc-w .vc-wr.num{font-size:13.5px}\n.vsc-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,440px),1fr));gap:16px;align-items:start}\n.vsc.vsc-new .vsc-list{grid-template-columns:minmax(0,1fr);gap:12px}\n.vsc .vc-sl{margin:0 0 16px}\n.vsc .vc-tag{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:99px;border:1px dashed var(--c-line2);font-size:10.5px;font-weight:600;color:var(--c-mut);vertical-align:1px}\n.vsc .vc-fold{all:unset;box-sizing:border-box;cursor:pointer;display:flex;align-items:center;gap:10px;width:100%;font-size:13px;color:var(--c-mut);padding:2px 2px 0;transition:transform var(--dur-release) var(--ease-spring)}\n.vsc .vc-fold:active{transform:scale(var(--press-row));transition:transform var(--dur-press) ease-out}\n.vsc .vc-fold b{color:var(--c-ink);font-weight:600}.vsc .vc-fold span{margin-left:auto;white-space:nowrap}\n.vsc .vc-note{background:var(--c-card);border:1px dashed var(--c-line2);border-radius:var(--c-r);padding:22px 18px;text-align:center}\n.vsc .vc-note b{display:block;font-size:15px;font-weight:600}.vsc .vc-note p{margin:6px auto 0;max-width:52ch;font-size:13px;line-height:1.5;color:var(--c-mut)}\n.vsc .vc-sech{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin:0 2px 10px;font-size:15px;font-weight:600}\n.vsc .vc-sech span{font-size:12px;font-weight:500;color:var(--c-mut)}\n@media (prefers-reduced-motion:reduce){.vsc .vc-fold,.vsc .vc-fold:active{transition:none;transform:none}}\n.vsc{--ease-out:cubic-bezier(0.16,1,0.3,1); --ease-rail:cubic-bezier(0.65,0,0.35,1); --ease-spring:cubic-bezier(0.34,1.56,0.64,1); --dur-press:80ms; --dur-release:500ms; --dur-rail:400ms; --press-chip:.88; --press-btn:.94; --press-card:.975; --press-row:.99;}\n.vsc *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}\n.vsc .press{transition:transform var(--dur-release) var(--ease-spring)}\n.vsc .press:active{transform:scale(var(--press-scale,.94));transition:transform var(--dur-press) ease-out}\n.vsc .press-chip{--press-scale:var(--press-chip)}\n.vsc .press-card{--press-scale:var(--press-card)}\n.vsc .vseg{position:relative;display:inline-flex;align-items:center;flex-shrink:0;gap:2px;padding:3px;max-width:100%; background:var(--vseg-bg);border:1px solid var(--vseg-border);border-radius:9px}\n.vsc .vseg>button{position:relative;z-index:1;display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:32px;padding:0 14px; border:0;background:transparent;border-radius:6px;color:var(--vseg-ink);font-family:var(--c-sans);font-size:12.5px;font-weight:600; letter-spacing:-.01em;white-space:nowrap;cursor:pointer;transition:color .12s ease}\n.vsc .vseg>button.on{color:var(--vseg-on-ink)}\n.vsc .vseg>button:disabled{opacity:.38;cursor:default}\n.vsc .vseg.sm>button{min-height:26px;padding:0 10px;font-size:11.5px}\n.vsc .vseg .v-pill{position:absolute;z-index:0;top:3px;bottom:3px;left:0;width:0;border-radius:6px;background:var(--vseg-pill);opacity:0; transition:left var(--dur-rail) var(--ease-rail),width var(--dur-rail) var(--ease-rail)}\n.vsc .vseg.rail-noanim .v-pill{transition:none}\n@media (max-width:767px){\n.vsc .vseg>button{min-height:36px}\n.vsc .vseg.sm>button{min-height:30px}\n.vsc .vseg>button::after{content:\"\";position:absolute;inset:-4px 0}\n}\n.vsc .vc{background:var(--c-card);border:var(--c-bw,1px) solid var(--c-line);border-radius:var(--c-r);padding:var(--c-pad);color:var(--c-ink); font-family:var(--c-sans);font-size:14px;line-height:1.35;min-width:0;box-shadow:var(--c-shadow,none);display:flex;flex-direction:column;gap:10px}\n.vsc .vc .num{font-family:var(--c-num);font-variant-numeric:tabular-nums;letter-spacing:var(--c-num-ls,0)}\n.vsc .vc-body{display:flex;flex-direction:column;gap:10px}\n.vsc .vc-cap{display:block;font-size:12px;font-weight:500;color:var(--c-mut)}\n.vsc .vc-mod{background:var(--c-box);border-radius:var(--c-mr,16px);padding:16px;min-width:0}\n.vsc .vc-top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:2px 2px 4px}\n.vsc .vc-match{font-size:19px;font-weight:600;letter-spacing:-.02em}\n.vsc .vc-match i{font-style:normal;font-weight:400;color:var(--c-dim);font-size:.8em}\n.vsc .vc-time{color:var(--c-mut);font-size:13px;margin-top:2px}\n.vsc .vc-sport{color:var(--c-dim);font-weight:600;letter-spacing:.08em;font-size:11px;margin-right:8px}\n.vsc .vc-pill{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 12px;border-radius:99px;font-size:12px;font-weight:600;white-space:nowrap;flex:none}\n.vsc .vc-pill.live{color:var(--c-mut);background:var(--c-box)}\n.vsc .vc-pill.live i{width:7px;height:7px;border-radius:50%;background:var(--c-warn);animation:vc-pulse 1.8s ease-in-out infinite}\n.vsc .vc-pill.locked{background:var(--c-good);color:var(--c-on-good)}\n.vsc .vc-pill svg{width:12px;height:12px}\n.vsc .vseg.fluid{display:flex}\n.vsc .vseg.fluid>button{flex:1}\n.vsc .vc-dotu{font-size:11px;font-weight:700;padding:1px 6px;border-radius:99px;background:var(--c-good);color:var(--c-on-good)}\n.vsc .vc-v.on{background:var(--c-good-box);box-shadow:inset 0 0 0 1px var(--c-good-line)}\n.vsc .vc-v1{display:flex;align-items:center;gap:16px}\n.vsc .vc-vu{font-size:56px;font-weight:700;letter-spacing:-.05em;line-height:.9;color:var(--c-good);flex:none}\n.vsc .vc-vu small{font-size:.45em;font-weight:600;margin-left:1px;letter-spacing:0}\n.vsc .vc-vu.zero{color:var(--c-dim)}\n.vsc .vc-vt{flex:1;min-width:0}\n.vsc .vc-vt strong{display:block;font-size:24px;font-weight:700;letter-spacing:-.03em;line-height:1.15;margin-top:1px}\n.vsc .vc-v.off .vc-vt strong{color:var(--c-mut)}\n.vsc .vc-vs{display:block;font-size:13.5px;color:var(--c-mut);margin-top:3px;line-height:1.4}\n.vsc .vc-logo{width:48px;height:48px;border-radius:12px;background:var(--c-tile);display:grid;place-items:center;flex:none;overflow:hidden;font-weight:700;font-size:14px;color:var(--c-tile-ink)}\n.vsc .vc-logo img{width:78%;height:78%;object-fit:contain}\n.vsc .vc-logo.sm{width:24px;height:24px;border-radius:7px;font-size:10px}\n.vsc .vc-ticks{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:14px;padding-top:12px;border-top:1px solid var(--c-line)}\n.vsc .vc-tick{display:inline-flex;align-items:center;gap:5px;font-size:13px;color:var(--c-ink)}\n.vsc .vc-tick svg{width:13px;height:13px;flex:none;color:var(--c-good)}\n.vsc .vc-tick.no svg{color:var(--c-bad)}\n.vsc .vc-more{margin-top:10px;font-size:12.5px;color:var(--c-mut)}\n.vsc .vc-more summary{cursor:pointer;list-style:none;color:var(--c-mut);font-weight:500;display:inline-flex;align-items:center;gap:5px}\n.vsc .vc-more summary::-webkit-details-marker,.vsc .vc-dt summary::-webkit-details-marker{display:none}\n.vsc .vc-more summary::after,.vsc .vc-dt summary::after{content:\"\";width:6px;height:6px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(45deg) translateY(-2px);transition:transform .2s var(--ease-out)}\n.vsc .vc-more[open] summary::after,.vsc .vc-dt[open] summary::after{transform:rotate(225deg) translateY(-1px)}\n.vsc .vc-more p{margin:7px 0 0;line-height:1.5}\n.vsc .vc-split{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}\n.vsc .vc-st.pk{box-shadow:inset 0 0 0 1px var(--c-good-line)}\n.vsc .vc-sth{display:flex;align-items:center;gap:8px}\n.vsc .vc-sth b{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.vsc .vc-big{font-size:30px;font-weight:700;letter-spacing:-.03em;line-height:1.1;margin-top:10px}\n.vsc .vc-lns{display:flex;flex-direction:column;gap:3px;margin-top:8px;min-height:20px}\n.vsc .vc-ln{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--c-mut)}\n.vsc .vc-ln b{font-weight:600;color:var(--c-ink)}\n.vsc .vc-ln i{width:8px;height:8px;border-radius:50%;flex:none}\n.vsc .vc-ln.hc i{background:var(--c-gold)}\n.vsc .vc-ln.sharp i{background:var(--c-good)}\n.vsc .vc-ln.loser i{background:var(--c-bad)}\n.vsc .vc-ln.exc i{background:transparent;border:1.5px dashed var(--c-dim)}\n.vsc .vc-ln.exc b{color:var(--c-mut)}\n.vsc .vc-ln.none{color:var(--c-dim)}\n.vsc .vc-bar{grid-column:1 / -1;display:flex;align-items:center;height:8px}\n.vsc .vc-bar>u{width:2px;height:14px;background:var(--c-ink);border-radius:1px;flex:none}\n.vsc .vc-half{flex:1;display:flex;height:100%;gap:1px;min-width:0}\n.vsc .vc-half.l{flex-direction:row-reverse}\n.vsc .vc-half i{display:block;height:100%;flex:none}\n.vsc .vc-half.l i:last-child{border-radius:4px 0 0 4px}\n.vsc .vc-half.r i:last-child{border-radius:0 4px 4px 0}\n.vsc .vc-half .hc{background:var(--c-gold)}\n.vsc .vc-half .sharp{background:var(--c-good)}\n.vsc .vc-half .unp{background:var(--c-rb-unp)}\n.vsc .vc-half .loser{background:var(--c-bad)}\n.vsc .vc-half .exc{background:repeating-linear-gradient(90deg,var(--c-dim) 0 2px,transparent 2px 4px)}\n.vsc .vc-kp{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}\n.vsc .vc-kp b{display:block;font-size:20px;font-weight:700;letter-spacing:-.02em;white-space:nowrap}\n.vsc .vc-kp span{display:block;font-size:12px;color:var(--c-mut);margin-top:1px}\n.vsc .vc-form{display:flex;align-items:center;gap:3px;height:16px;margin-top:12px}\n.vsc .vc-form i{flex:1;max-width:14px;height:7px;border-radius:2px;background:var(--c-dim);align-self:center}\n.vsc .vc-form i.W{background:var(--c-good);align-self:flex-start}\n.vsc .vc-form i.L{background:var(--c-bad);align-self:flex-end}\n.vsc .vc-form span{font-size:12px;color:var(--c-mut);margin-left:8px;white-space:nowrap}\n.vsc .vc-dt{padding:0}\n.vsc .vc-dt summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;padding:13px 16px;font-size:14px;font-weight:600}\n.vsc .vc-dt summary em{font-style:normal;font-weight:500;color:var(--c-mut);font-size:13px;margin-right:auto}\n.vsc .vc-dt summary::after{margin-left:auto;color:var(--c-mut)}\n.vsc .vc-dt summary em+::after{margin-left:0}\n.vsc .vc-dtb{padding:0 16px 14px}\n.vsc .vc-dtb p{margin:0;font-size:12.5px;line-height:1.55;color:var(--c-mut)}\n.vsc .vc-wg{margin-bottom:12px}\n.vsc .vc-w{display:grid;grid-template-columns:14px 74px minmax(0,auto) minmax(0,1fr);gap:10px;align-items:center;min-height:34px;font-size:13px;border-top:1px solid var(--c-line)}\n.vsc .vc-wg .vc-cap{margin-bottom:6px}\n.vsc .vc-w b{font-weight:600;white-space:nowrap}\n.vsc .vc-w.agg{grid-template-columns:14px minmax(0,1fr) auto}\n.vsc .vc-w.agg b{font-weight:500;color:var(--c-mut)}\n.vsc .vc-wd{display:grid;place-items:center}\n.vsc .vc-wd i{width:8px;height:8px;border-radius:50%;background:var(--c-dim)}\n.vsc .vc-wd svg{width:13px;height:13px;color:var(--c-gold)}\n.vsc .vc-w.hc b{color:var(--c-gold)}\n.vsc .vc-w.sharp .vc-wd i{background:var(--c-good)}\n.vsc .vc-w.loser .vc-wd i{background:var(--c-bad)}\n.vsc .vc-w.unp .vc-wd i{background:var(--c-rb-unp)}\n.vsc .vc-w.exc .vc-wd i{background:transparent;border:1.5px dashed var(--c-dim)}\n.vsc .vc-wu{font-weight:600;white-space:nowrap}\n.vsc .vc-wu em{font-style:normal;font-weight:500;color:var(--c-mut);font-size:12px;margin-left:3px}\n.vsc .vc-wr{font-size:12px;color:var(--c-mut);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.vsc .vc-hist{display:flex;align-items:center;justify-content:space-between;gap:10px;padding-top:12px;border-top:1px solid var(--c-line)}\n.vsc .vc-foot{margin:2px 2px 0;font-size:12px;color:var(--c-dim);line-height:1.5}\n.vsc .vc-empty{text-align:center;padding:26px 16px}\n.vsc .vc-empty b{display:block;font-size:16px;font-weight:600}\n.vsc .vc-empty p{margin:6px auto 0;font-size:13.5px;color:var(--c-mut);max-width:34ch;line-height:1.45}\n.vsc .vc-sl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:18px}\n.vsc .vc-slt{background:var(--c-card);border:var(--c-bw,1px) solid var(--c-line);border-radius:var(--c-r);padding:16px 18px;min-width:0}\n.vsc .vc-slt span{display:block;font-size:12.5px;font-weight:500;color:var(--c-mut)}\n.vsc .vc-slt b{display:block;font-size:30px;font-weight:700;letter-spacing:-.03em;margin-top:2px}\n.vsc .vc-slt.gold b{color:var(--c-gold)}\n.vsc .vc-slt.good b{color:var(--c-good)}\n.vsc .vc-slt em{display:block;font-style:normal;font-size:12.5px;color:var(--c-mut)}\n.vsc .vc-sldots{display:flex;flex-wrap:wrap;gap:5px;margin:14px 0 9px}\n.vsc .vc-sldots i{width:10px;height:10px;border-radius:50%;background:var(--c-line2)}\n.vsc .vc-sldots i.signal{background:var(--c-good)}\n.vsc .vc-sldots i.building{background:var(--c-warn)}\n@media (max-width:767px){\n.vsc .vc{gap:8px}\n.vsc .vc-body{gap:8px}\n.vsc .vc-split{gap:8px}\n.vsc .vc-mod{padding:14px}\n.vsc .vc-match{font-size:17px}\n.vsc .vc-top{flex-wrap:wrap;gap:8px}\n.vsc .vc-time{white-space:nowrap}\n.vsc .vc-pill{height:26px;padding:0 10px;font-size:11.5px}\n.vsc .vc-vu{font-size:48px}\n.vsc .vc-vt strong{font-size:21px}\n.vsc .vc-v1{gap:12px}\n.vsc .vc-v.on .vc-logo{display:none}\n.vsc .vc-big{font-size:26px}\n.vsc .vc-kp{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 8px}\n.vsc .vc-w{grid-template-columns:14px 70px minmax(0,1fr);padding:6px 0}\n.vsc .vc-wr{grid-column:2 / -1;text-align:left}\n.vsc .vc-dt{padding:0}\n.vsc .vc-sl{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 16px 0}\n.vsc .vc-slt{padding:12px 14px}\n.vsc .vc-slt b{font-size:24px}\n.vsc .vc-slt.clim{grid-column:1 / -1}\n}\n@media (prefers-reduced-motion:reduce){\n.vsc .press,.vsc .press:active{transition:none;transform:none}\n.vsc .vseg .v-pill,.vsc .vc-more summary::after,.vsc .vc-dt summary::after{transition:none}\n.vsc .vc-pill.live i{animation:none}\n}\n@keyframes vc-pulse{50%{opacity:.25}}";
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
  if (name === 'Over' || name === 'Under') return '<div class="vc-logo">' + name[0] + '</div>';
  var url = OPT.logo ? OPT.logo(g, name) : null, ab = null;
  if (!url && g.sport === 'nba'){ ab = [g.vault.away, g.vault.home].filter(function(a){ return TEAMS[a] && TEAMS[a][0] === name; })[0];
    if (ab) url = 'https://a.espncdn.com/i/teamlogos/nba/500/' + TEAMS[ab][1] + '.png'; }
  var mono = esc(ab || name.replace(/[^A-Za-z0-9 ]/g, '').split(' ').map(function(w){ return w[0]; }).join('').slice(0, 3).toUpperCase());
  if (!url) return '<div class="vc-logo">' + mono + '</div>';
  return '<div class="vc-logo"><img alt="" src="' + esc(url) + '" onerror="this.replaceWith(document.createTextNode(\'' + mono + '\'))"></div>';
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
  if (ls && ls.side === name && ls.line != null){
    /* Polymarket's spread line is outcomes[0]'s: the other team gets the opposite sign (Magic -4.5 makes the Jazz +4.5) */
    var outs = ls.outs || ls._outs, ln = outs && outs.length === 2 && outs[1] === name ? -ls.line : ls.line;
    return name + ' ' + (ln > 0 ? '+' : '') + ln;
  }
  return name + ' spread';
}

var CHK = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 8.5l3 3 6-7"/></svg>';
var XX = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/></svg>';
function counted(s){ return s.sharp_usd + s.unproven_usd + s.loser_usd; }
function nProven(s){ return s.counts.sharp + s.counts.hc; }
/* HC margin for side n of market m: sized-up proven wallets for minus against (the benchmark's HC margin, from stored counts) */
function hcMargin(m, n, v){ var o = Object.keys(m.sides).filter(function(x){ return x !== n; })[0]; return m.sides[n][v].counts.hc - (o ? m.sides[o][v].counts.hc : 0); }
function hcBadge(m, n, v){
  var d = hcMargin(m, n, v), f = m.sides[n][v].counts.hc;
  if (d < 1) return '';
  return '<span class="vc-hc' + (d >= 2 ? ' x2' : '') + '" title="' + f + ' proven wallet' + (f === 1 ? '' : 's') + ' sized up to 1.5x or more on this side, ' + (f - d) + ' on the other">' +
    (d >= 2 ? ICON.star : '') + ICON.star + '<span class="num">HC +' + d + '</span></span>';
}
/* the market's play: the benchmark's stake policy as the builder replicates it (m.sf), else the older lock rule on cards built before it existed */
function shadow(m, v){
  var sf = (m.sf || {})[v];
  if (sf && sf.side && !sf.outs && !sf._outs){                       /* cards built before sf stored its outcome order */
    var lk = (m.lock_shadow || {})[v] || {};
    if (lk.outs && (lk.cid === sf.cid || (lk.line === sf.line && lk.outs.indexOf(sf.side) >= 0))) sf._outs = lk.outs;
  }
  if (sf) return sf.side && sf.units > 0 ? sf : null;
  var ls = (m.lock_shadow || {})[v] || {};
  return ls.side && ls.gates ? ls : null;
}
/* ---------- Pinnacle steam and the size steps, from the stored `steam` and `chain` fields on the shown size ---------- */
var STEAM_WHY = {no_tape_before_cut: 'no Pinnacle prices before the lock', ticket_line_not_main_at_cut: 'this line is not Pinnacle\'s main line',
  no_moneyline_rows: 'no Pinnacle moneyline prices', side_not_mapped_to_home_away: 'teams not matched to Pinnacle', lock_row_juice_unknown: 'Pinnacle\'s price on this line is not known'};
var SEAT = {no_t5: 'no tier-5 wallet: up to 2u', no_lead: 'no lead: up to 2u', t5_young: 'young tier-5 lead: 2u to 3u', lead6: '6-day lead: 2u to 5u', lead14: '14-day lead: 3u to 6u'};
function ptsTxt(p, side){ if (!p) return null; var a = trim(Math.abs(p).toFixed(1)); return 'line moved ' + a + ' pt ' + (p > 0 ? 'toward ' : 'away from ') + esc(side); }
function pctTxt(p){ if (p == null || !p) return null; return 'price ' + (p > 0 ? 'shortened ' : 'drifted ') + trim(Math.abs(p).toFixed(1)) + '%'; }
function steamState(s){ return !s ? null : s.on === true ? 'on' : s.on === false ? 'off' : 'unknown'; }
function steamBits(s, side){
  var b = [], so = ptsTxt(s.since_open_pts, side), lh = ptsTxt(s.last_hour_pts, side), po = pctTxt(s.since_open_pct), ph = pctTxt(s.last_hour_pct);
  if (so) b.push(so + ' since open'); if (lh) b.push(lh + ' in the last hour');
  if (po) b.push(po + ' since open'); if (ph) b.push(ph + ' in the last hour');
  return b;
}
function steamRow(ls, key){
  var s = ls && ls.steam, st = steamState(s);
  if (!st) return '';
  var b = steamBits(s, ls.side), lbl = st === 'on' ? 'Pinnacle steam toward ' + esc(ls.side) : st === 'off' ? 'No Pinnacle steam' : 'Pinnacle steam unknown';
  var why = st === 'unknown' ? (STEAM_WHY[s.why] || 'not enough Pinnacle prices') : b[0] || (st === 'off' ? 'price and line steady' : '');
  return '<div class="vc-steam ' + st + '"><i></i><b>' + lbl + '</b>' + (why ? '<span>' + why + '</span>' : '') + '</div>';
}
function steamDetail(ls, key, side){
  var s = ls && ls.steam, st = steamState(s);
  if (!st) return '';
  var b = steamBits(s, ls.side), rows = [];
  rows.push(['Steam', st === 'on' ? 'On, toward ' + esc(ls.side) + (s.tier === 'gold' ? ' (gold: 4.5%+ in the last hour)' : '') : st === 'off' ? 'Off' : 'Unknown: ' + (STEAM_WHY[s.why] || 'not enough Pinnacle prices')]);
  if (b.length) rows.push(['Moves', b.join(' · ')]);
  if (s.juice != null || s.lock_juice != null) rows.push(['Price itself', s.juice === true || s.lock_juice === true ? 'shortened 3% or more' : s.juice === false ? 'no 3% shorten' : 'not known']);
  else if (st !== 'off' && key !== 'ml') rows.push(['Price itself', 'not known (a line move alone counts as steam, but not for the seat gate)']);
  if (s.rows) rows.push(['Pinnacle reads', s.rows + ' before the lock']);
  return '<div class="vd-pin"><span class="vd-cap">Pinnacle</span>' + rows.map(function(r){ return '<div class="vd-kv"><span>' + r[0] + '</span><b>' + r[1] + '</b></div>'; }).join('') + '</div>';
}
var CHAIN = {press_under5_cap: 'Capped at 1u: the press edge is under 5.', press_under5_zero: 'Muted: the press edge is under 0 on a spread or total.',
  t5_band: 'Moved into its seat\'s range.', t5_cap: 'Cut to its seat\'s ceiling.', t5_rescue: 'Raised to its seat\'s floor.', t5_zero: 'Muted by the seat rules.',
  t5_no_t5_st: 'Muted: no tier-5 wallet and Pinnacle\'s price has not moved.', t5_no_t5_st_undecided_steam_unknown: 'Kept: Pinnacle\'s price move on this line is not known, so the no-tier-5 gate could not decide.',
  t5_undecided_steam_unknown: 'Kept: Pinnacle\'s price move is not known, so the seat gate could not decide.',
  gap_boost: '+1u: wallets here lead the other side on recent form.', gap_rescue: 'Rescued at 3u: wallets here lead the other side on recent form.',
  top3_floor: 'Raised: a top-ranked wallet is on this side.', top3_rescue: 'Rescued: a top-ranked wallet is on this side.',
  edge_under_5: 'Held back: the edge is under 5.', edge_under_5_undecided_steam_unknown: 'Kept: the edge is under 5 but Pinnacle steam is not known.',
  press_edge_net: 'Clamped by the press edge and the wallets\' closing record.'};
function chainList(ls){
  var c = (ls && ls.chain) || [], seat = ls && ls.t5_seat;
  var items = c.map(function(x){ var k = String(x).split(':')[0]; return CHAIN[k] || null; }).filter(Boolean);
  if (seat && SEAT[seat]) items.unshift('Seat: ' + SEAT[seat] + '.');
  if (!items.length) return '';
  return '<div class="vd-pin"><span class="vd-cap">Size steps</span><ol class="vd-chain">' + items.map(function(t){ return '<li>' + t + '</li>'; }).join('') + '</ol></div>';
}
var RUNG = {
  'PRESS': ['Press', 'A proven wallet is sized up on this side, the money is with it, and no proven wallet is against it.'],
  'PRESS-X': ['Press X', 'The press shape, but proven wallets on the other side are betting small and fewer than the proven wallets here.'],
  'PRESS-N': ['Press N', 'A wallet with a long record is pressing, the money is with it, and no proven wallet is on either side.'],
  'PRESS-U': ['Press U', 'More proven wallets here than against, the ones against are betting small, and nobody is pressing.'],
  'PRESS-R6': ['Two veterans', 'Two wallets with long records are on this side at their normal size, the money is with it, and no proven wallet is against it.'],
  'FADE-F': ['Fade', 'The only losing wallet in this market is on the other side and is on a losing streak.'],
  'TRUST-G': ['Trusted wallet', 'A wallet that has beaten its own prices lately is on this moneyline, and the older score is positive.'],
  'TRUST-S': ['Trusted wallet', 'A wallet that has beaten its prices in spread markets is on this side and none is against it.'],
  'TRUST-T': ['Trusted wallets', 'Two or more wallets that have beaten their prices in totals are on this side and none is against.'],
  'STEAM-C': ['Steam', 'Pinnacle\'s price is moving toward this side, and the proven wallets against it are betting small. The market overrules a small dissent.'],
  'STEAM-S': ['Steam', 'Pinnacle\'s price is moving toward this side against a seasoned wallet\'s ordinary-size bet, with 20% to 60% of the money here.'],
  'SOLO-Q': ['Quiet favourite', 'Nobody is against this side, Pinnacle is not moving, it is a 50% to 60% favourite, and the money here is small or from a wallet in hot form.'],
  'PRESS-M': ['Mirror press', 'The press shape (money, a sized-up veteran, no proven wallet against) is on the side the wallet-quality score did not favour.'],
  'GAP-LEAD': ['Recent form', 'At least two wallets here have much better last-30-day results in this market than the wallets on the other side, whose recent results are negative.']
};
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
  return '<div class="vc-half ' + dir + '">' + seg('hc', s.hc_usd) + seg('sharp', s.sharp_usd - s.hc_usd) + seg('unp', s.unproven_usd) + seg('loser', s.loser_usd) + seg('exc', s.excluded_usd) + '</div>';
}
/* v3: a stack of small modules. Verdict, money split, proven record, wallets (collapsed), data notes (collapsed). */
/* The benchmark's score and label for the market: the one side whose stored `ags` score is above zero, or nothing */
var TIER = {WEAK: 'Weak', LEAN: 'Lean', LOCK: 'Lock', PREMIUM: 'Prem', ELITE: 'Elite'};
function agsRow(m, names, v){
  var n = names.filter(function(x){ var a = m.sides[x][v].ags; return a && a.score > 0 && TIER[a.tier]; })[0];
  if (!n) return '';
  var a = m.sides[n][v].ags;
  return '<div class="vc-ags"><span class="vc-tier ' + a.tier + '">' + TIER[a.tier] + '</span><span><b>' + esc(n) + '</b> score <span class="num">+' + a.score.toFixed(2) +
    '</span></span><em>' + a.contributors + ' proven of ' + (a.for_n + a.against_n) + ' tracked</em></div>';
}
function verdict(g, m, key, names, v){
  var ls = shadow(m, v), S = {}; names.forEach(function(n){ S[n] = m.sides[n][v]; });
  var tick = function(ok, t){ return '<span class="vc-tick ' + (ok ? 'ok' : 'no') + '">' + (ok ? CHK : XX) + t + '</span>'; };
  if (ls){
    var q = ls.gates, u = units(ls), rg = ls.rung && RUNG[ls.rung];
    return '<section class="vc-mod vc-v on"><div class="vc-v1"><b class="vc-vu num">' + (u == null ? 'n/a' : u + '<small>u</small>') + '</b>' +
      '<div class="vc-vt"><span class="vc-cap">Suggested<span class="vc-tag">untested rule</span>' + (rg ? '<span class="vc-tag">' + rg[0] + '</span>' : '') + ' ' + (g.frozen ? '· locked' : '· live until ' + ct(g.cut) + ' CT') + '</span>' +
      '<strong>' + esc(sideLabel(ls.side, key, ls)) + '</strong><span class="vc-vs">' +
      (ls.price != null ? '<span class="num">' + trim((ls.price * 100).toFixed(1)) + '¢</span> on Polymarket' + (ls.price_t ? ', read ' + ct(ls.price_t) + ' CT' : '') : 'price n/a') + '</span></div>' +
      logo(ls.side, g) + '</div>' +
      agsRow(m, names, v) + (q ? '<div class="vc-ticks">' + tick(1, '<span class="num">' + Math.round(q.share_for * 100) + '%</span> of the money') + tick(1, '<span class="num">' + q.proven_for + '</span> proven for') +
      tick(1, '<span class="num">' + q.proven_against + '</span> against') + tick(1, 'sized up' + (ls.top_press != null ? ' <span class="num">' + ls.top_press + 'x</span>' : '')) + '</div>'
      : '<p class="vc-why">' + (rg ? rg[1] : 'This side meets one of the staking rules.') + '</p>') +
      '<details class="vc-more"><summary>How the size is set</summary><p>' + (ls.rung ? 'Rule: <b>' + esc(ls.rung) + '</b>. ' : '') + 'The size comes from the staking rules, built from Vault\'s own wallet records. ' +
      'They use Pinnacle steam, the odds cap, the trusted-margin, mirror, recent-form and top-wallet rules, the seat caps and the edge clamps. A few inputs Vault cannot observe are left out. This rule has no graded record yet.</p></details>' + steamRow(ls, key) + '<button type="button" class="vc-open press press-btn">See who\'s on it</button></section>';
  }
  var lead = names.slice().sort(function(a, b){ return (nProven(S[b]) - nProven(S[a])) || (counted(S[b]) - counted(S[a])); })[0];
  var other = names.filter(function(n){ return n !== lead; })[0], tot = counted(S[lead]) + counted(S[other]);
  var share = tot ? counted(S[lead]) / tot : null, pf = nProven(S[lead]), pa = nProven(S[other]), why;
  if (!tot) why = 'No wallet holds $250 or more here yet.';
  else if (!pf) why = v === 'fwd' ? 'No wallet is proven on forward-only results yet.' : 'No proven wallet on either side yet. The ledger is still filling.';
  else if (pa) why = 'Proven wallets are on both sides.';
  else if (share < .6) why = 'Proven money is on ' + esc(lead) + ', but it holds <span class="num">' + Math.round(share * 100) + '%</span> of the money. The rule needs 60%.';
  else why = esc(lead) + ' has the money and a proven wallet. No wallet is sized up to 1.5x its usual stake yet.';
  return '<section class="vc-mod vc-v off"><div class="vc-v1"><b class="vc-vu num zero">0<small>u</small></b><div class="vc-vt"><span class="vc-cap">Suggested</span>' +
    '<strong>No play</strong><span class="vc-vs">' + why + '</span></div></div>' + agsRow(m, names, v) + (tot ? '<button type="button" class="vc-open press press-btn">See who\'s on it</button>' : '') + '</section>';
}
function sideTile(g, n, s, pick, hc){
  var line = function(k, v, t){ return v > 0 ? '<span class="vc-ln ' + k + '"><i></i><b class="num">' + usd(v) + '</b> ' + t + '</span>' : ''; };
  var lines = line('hc', s.hc_usd, 'sized up') + line('sharp', s.sharp_usd - s.hc_usd, 'proven') + line('loser', s.loser_usd, 'losers') + line('exc', s.excluded_usd, 'excluded');
  return '<div class="vc-mod vc-st' + (pick ? ' pk' : '') + '"><div class="vc-sth">' + logo(n, g).replace('vc-logo', 'vc-logo sm') + '<b>' + esc(n) + '</b>' + (hc || '') + '</div>' +
    '<div class="vc-big num">' + usd(counted(s)) + '</div><div class="vc-lns">' + (lines || '<span class="vc-ln none">no proven or loser money</span>') + '</div></div>';
}
function walletRow(w, k){
  return '<div class="vc-w ' + k + '"><span class="vc-wd">' + (w.star ? ICON.star : '<i></i>') + '</span><b class="num">' + tail(w.w) + '</b>' +
    '<span class="vc-wu num">' + usd(w.usd) + (w.press != null ? ' <em>' + w.press + 'x</em>' : '') + '</span>' +
    '<span class="vc-wr num">' + w.w_ + '-' + w.l_ + ' · L30 ' + roi(w.l30_roi) + ' · ' + susd(w.pnl) + '</span></div>';
}
function walletList(n, s){
  var sum = function(a){ return a.reduce(function(t, x){ return t + x.usd; }, 0); }, c = s.counts, np = nProven(s), h = '<div class="vc-wg"><span class="vc-cap">' + esc(n) + '</span>';
  var agg = function(k, t, v){ return '<div class="vc-w agg ' + k + '"><span class="vc-wd"><i></i></span><b>' + t + '</b><span class="vc-wu num">' + usd(v) + '</span></div>'; };
  s.list.forEach(function(w){ h += walletRow(w, w.star ? 'hc' : 'sharp'); });
  if (np > s.list.length) h += agg('sharp', '+' + (np - s.list.length) + ' more proven', Math.max(0, s.sharp_usd - sum(s.list)));
  s.losers.forEach(function(w){ h += walletRow(w, 'loser'); });
  if (c.loser > s.losers.length) h += agg('loser', '+' + (c.loser - s.losers.length) + ' more losers', Math.max(0, s.loser_usd - sum(s.losers)));
  if (c.unproven) h += agg('unp', c.unproven + ' unproven', s.unproven_usd);
  if (c.excluded) h += agg('exc', c.excluded + ' excluded, not counted', s.excluded_usd);
  if (!(np + c.loser + c.unproven + c.excluded)) h += '<div class="vc-w agg exc"><span class="vc-wd"><i></i></span><b>No holders at $250 or more</b></div>';
  return h + '</div>';
}
function body(g, st){
  var m = g.markets[st.group], names = sideOrder(g, m, st.group), v = st.variant, ls = shadow(m, v);
  var a = m.sides[names[0]][v], b = m.sides[names[1]][v], max = Math.max(counted(a) + a.excluded_usd, counted(b) + b.excluded_usd) || 1;
  var h = verdict(g, m, st.group, names, v);
  h += '<div class="vc-split">' + sideTile(g, names[0], a, ls && ls.side === names[0], hcBadge(m, names[0], v)) + sideTile(g, names[1], b, ls && ls.side === names[1], hcBadge(m, names[1], v)) +
    '<div class="vc-bar">' + half(a, max, 'l') + '<u></u>' + half(b, max, 'r') + '</div></div>';
  var best = names.slice().sort(function(x, y){ return m.sides[y][v].sharp_usd - m.sides[x][v].sharp_usd; })[0], p = m.sides[best][v].proven;
  if (p.wallets){
    h += '<section class="vc-mod vc-pr"><span class="vc-cap">Proven wallets on ' + esc(best) + ' · ' + p.wallets + '</span><div class="vc-kp">' +
      '<div><b class="num">' + (p.win_pct == null ? 'n/a' : p.win_pct + '%') + '</b><span>win</span></div><div><b class="num">' + p.w + '-' + p.l + '</b><span>record</span></div>' +
      '<div><b class="num">' + roi(p.l30_roi) + '</b><span>last 30 days</span></div><div><b class="num">' + susd(p.lifetime_pnl) + '</b><span>lifetime</span></div></div>' +
      (p.last20.length ? '<div class="vc-form">' + p.last20.map(function(r){ return '<i class="' + r + '"></i>'; }).join('') + '<span>last ' + p.last20.length + '</span></div>' : '') + '</section>';
  }
  var nW = names.reduce(function(t, n){ var c = m.sides[n][v].counts; return t + c.hc + c.sharp + c.unproven + c.loser + c.excluded; }, 0);
  h += '<details class="vc-mod vc-dt" data-d="w"' + (st.open.w ? ' open' : '') + '><summary>Wallets<em class="num">' + nW + '</em></summary><div class="vc-dtb">' +
    names.map(function(n){ return walletList(n, m.sides[n][v]); }).join('') +
    '<div class="vc-hist"><span class="vc-cap">Wallet history</span><div class="vseg sm" data-k="variant"><i class="v-pill"></i><button type="button" data-v="all"' + (v === 'all' ? ' class="on"' : '') +
    '>All</button><button type="button" data-v="fwd"' + (v === 'fwd' ? ' class="on"' : '') + '>Forward only</button></div></div></div></details>';
  var cv = g.coverage, bits = ['Money is mark value ' + (g.frozen ? 'at the lock' : 'now') + ' (shares x price), not cost.',
    cv.markets_read + ' markets read, ' + cv.markets_missed + ' missed' + (cv.late_reads ? ', ' + cv.late_reads + ' late' : '') + '.',
    'Oldest read ' + dur(cv.max_read_lag_s) + ' before ' + (g.frozen ? 'the lock' : 'this build') + '.', 'Ledger refreshed ' + ct(g.ledger_run_at) + ' CT.'];
  if (names.some(function(n){ return m.sides[n][v].ags; })) bits.push('The score compares the average quality of the proven wallets on each side, from -1 to +1. The labels use published cut points (above 0.781 Lean, 0.916 Lock, 0.957 Prem, 0.981 Elite; any lower positive score is Weak). Those were fitted outside Vault, and the label does not set the size.');
  if (cv.two_way_dust_dropped) bits.push(cv.two_way_dust_dropped + ' two-way ' + (cv.two_way_dust_dropped === 1 ? 'wallet' : 'wallets') + ' dropped as balanced dust.');
  if (g.vault.start_gap_flag) bits.push('Start times differ by ' + g.vault.start_gap_min + ' min between Polymarket and Vault.');
  if (g.test) bits.push(g.test.counts ? 'Counts for the forward test.' : 'Does not count for the forward test: ' + g.test.why_not.join(', ') + '.');
  return h + '<details class="vc-mod vc-dt" data-d="n"' + (st.open.n ? ' open' : '') + '><summary>Data notes</summary><div class="vc-dtb"><p>' + bits.join(' ') + '</p></div></details>' +
    '<p class="vc-foot">Sharp money is context. The suggested size comes from an untested rule that is still in its forward test.</p>';
}

/* ---------- play detail: one market, every wallet on it, opened from the verdict ("See who's on it") ----------
   The benchmark's play page, built only from stored fields. Price skill is the share of a wallet's past bets bought below the stored close
   (Vault's T-15 price, or the Pendulum Flow close); it is plotted only once a wallet has CLV_MIN bets with a close, and always shows its n.
   No "signals aligned" count: sharp money is context, never an agree total (CLAUDE.md). */
var CLV_MIN = 5;
function american(p){ if (p == null || p <= 0 || p >= 1) return null; return p >= .5 ? '-' + Math.round(p / (1 - p) * 100) : '+' + Math.round((1 - p) / p * 100); }
function cents(p){ return p == null ? 'n/a' : trim((p * 100).toFixed(1)) + '¢'; }
function beat(w){ var c = w.clv; return c && c.n >= CLV_MIN ? c.beat / c.n : null; }
function beatTxt(w){ var c = w.clv; if (!c || !c.n) return 'no closes yet'; return (c.n >= CLV_MIN ? Math.round(c.beat / c.n * 100) + '%' : c.beat + ' of ' + c.n) + ' beat the close'; }
function wr(w){ return w.w_ + w.l_ ? Math.round(w.w_ / (w.w_ + w.l_) * 100) + '%' : 'n/a'; }
function sideWallets(s){
  return s.list.map(function(w){ return {w: w, k: w.star ? 'gold' : 'sharp'}; })
    .concat((s.unproven_list || []).map(function(w){ return {w: w, k: 'unp'}; }), s.losers.map(function(w){ return {w: w, k: 'loser'}; }));
}
/* where the money sits: x = price skill, y = lifetime ROI, area = $ on this market. This side solid, the other side hollow. */
function scatter(mine, theirs){
  var nar = window.innerWidth < 768, W = nar ? 340 : 560, H = nar ? 260 : 300, L = 44, R = 12, T = 28, B = 40, pts = [], held = [];   /* a phone draws narrower, so labels stay legible */
  mine.forEach(function(x){ pts.push({x: x, own: true}); }); theirs.forEach(function(x){ pts.push({x: x, own: false}); });
  var plot = pts.filter(function(p){ return beat(p.x.w) != null && p.x.w.roi != null; });
  pts.forEach(function(p){ if (plot.indexOf(p) < 0) held.push(p); });
  var xs = plot.map(function(p){ return beat(p.x.w); }), ys = plot.map(function(p){ return p.x.w.roi; });
  var x0 = Math.min(.4, Math.min.apply(null, xs.concat([.4]))), x1 = Math.max(.65, Math.max.apply(null, xs.concat([.65])));
  var y0 = Math.min(-.1, Math.min.apply(null, ys.concat([-.1]))), y1 = Math.max(.15, Math.max.apply(null, ys.concat([.15])));
  var px = (x1 - x0) * .12, py = (y1 - y0) * .18; x0 -= px; x1 += px; y0 -= py; y1 += py;      /* room for the bubbles at the edges */
  var sx = function(v){ return L + (v - x0) / (x1 - x0) * (W - L - R); }, sy = function(v){ return T + (y1 - v) / (y1 - y0) * (H - T - B); };
  var maxU = Math.max.apply(null, pts.map(function(p){ return p.x.w.usd; }).concat([1]));
  var rad = function(u){ return 6 + 22 * Math.sqrt(u / maxU); };
  var g = '<svg class="vd-sc" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Wallets by price skill and lifetime ROI">';
  [x0, (x0 + x1) / 2, x1].forEach(function(v){ g += '<line class="gl" x1="' + sx(v) + '" x2="' + sx(v) + '" y1="' + T + '" y2="' + (H - B) + '"/><text class="ax" x="' + sx(v) + '" y="' + (H - B + 18) + '" text-anchor="middle">' + Math.round(v * 100) + '%</text>'; });
  [y0, 0, y1].forEach(function(v){ g += '<line class="gl' + (v === 0 ? ' z' : '') + '" x1="' + L + '" x2="' + (W - R) + '" y1="' + sy(v) + '" y2="' + sy(v) + '"/><text class="ax" x="' + (L - 8) + '" y="' + (sy(v) + 4) + '" text-anchor="end">' + (v > 0 ? '+' : '') + Math.round(v * 100) + '%</text>'; });
  if (x0 < .5 && x1 > .5) g += '<line class="gl z" x1="' + sx(.5) + '" x2="' + sx(.5) + '" y1="' + T + '" y2="' + (H - B) + '"/>';
  g += '<text class="axt" x="' + ((L + W - R) / 2) + '" y="' + (H - 4) + '" text-anchor="middle">Beat the close →</text><text class="axt" x="12" y="' + ((T + H - B) / 2) + '" text-anchor="middle" transform="rotate(-90 12 ' + ((T + H - B) / 2) + ')">Lifetime ROI →</text>';
  plot.sort(function(a, b){ return b.x.w.usd - a.x.w.usd; }).forEach(function(p, i){
    var w = p.x.w, cx = sx(beat(w)), cy = sy(w.roi), r = rad(w.usd);
    g += '<g class="b ' + p.x.k + (p.own ? ' own' : ' opp') + '"><title>' + tail(w.w) + ' · ' + usd(w.usd) + ' · ' + w.w_ + '-' + w.l_ + ' · ROI ' + roi(w.roi) + ' · ' + beatTxt(w) + '</title>' +
      '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="' + r.toFixed(1) + '"/>' +
      (p.own && i === 0 ? '<text class="bl" x="' + cx.toFixed(1) + '" y="' + (cy - r - 7).toFixed(1) + '" text-anchor="middle">' + usd(w.usd) + '</text>' : '') + '</g>';
  });
  g += '</svg>';
  var note = held.length ? '<p class="vd-held">' + held.length + ' ' + (held.length === 1 ? 'wallet is' : 'wallets are') + ' not plotted: fewer than ' + CLV_MIN + ' past bets with a stored close. ' +
    'Closes are stored from Nov 11 (all sports) and late October (NBA, NFL), so this fills in over time.</p>' : '';
  return g + note;
}
function leadCard(x, side){
  if (!x) return '';
  var w = x.w, p = w.press, u = w.usual, a = w.at_size, k = {gold: 'Proven, sized up', sharp: 'Proven', unp: 'Unproven', loser: 'Losing'}[x.k];
  var pos = p == null ? null : Math.min(1, p / 4);
  return '<section class="vd-lead"><span class="vd-cap">Lead wallet</span><div class="vd-lh"><div><b class="num">' + tail(w.w) + '</b><span class="vd-tag ' + x.k + '">' + k + '</span></div>' +
    '<div class="vd-lu"><b class="num">' + usd(w.usd) + '</b><span>on ' + esc(side) + '</span></div></div>' +
    '<div class="vd-two"><div class="vd-box"><span class="vd-cap">Record</span><b class="num">' + w.w_ + '-' + w.l_ + '</b><span class="num">' + roi(w.roi) + ' ROI · ' + wr(w) + ' wins</span></div>' +
    '<div class="vd-box' + (beat(w) != null && beat(w) > .5 ? ' good' : '') + '"><span class="vd-cap">Price skill</span><b class="num">' + (beat(w) != null ? Math.round(beat(w) * 100) + '%' : 'n/a') + '</b><span class="num">' +
    (w.clv && w.clv.n ? w.clv.beat + ' of ' + w.clv.n + ' bets beat the close' : 'no past bet has a stored close') + '</span></div></div>' +
    (p != null && u ? '<div class="vd-size"><div class="vd-szh"><span class="vd-cap">Size vs usual</span><b class="num">' + p + 'x</b></div><div class="vd-bar"><i style="width:' + (pos * 100).toFixed(1) + '%"></i><u style="left:25%"></u></div>' +
      '<div class="vd-szh"><span class="num">usual ' + usd(u) + '</span><span class="num">this ' + usd(w.usd) + '</span></div>' +
      (a && a.w + a.l ? '<p class="num">' + Math.round(a.w / (a.w + a.l) * 100) + '% wins at this size (' + a.w + '-' + a.l + ') · ' + Math.round(a.share * 100) + '% of its bets</p>' : '') + '</div>' : '') + '</section>';
}
function whoCol(name, s, total, own){
  var rows = sideWallets(s);
  return '<div class="vd-col' + (own ? ' own' : '') + '"><div class="vd-ch"><span class="vd-cap">' + (own ? 'This side' : 'Other side') + '</span><b class="num">' + usd(total) + '</b></div><b class="vd-cn">' + esc(name) + '</b>' +
    (rows.length ? rows.map(function(x){ var w = x.w;
      return '<div class="vd-w ' + x.k + '"><i></i><div><b class="num">' + tail(w.w) + '</b><span class="num">' + w.w_ + '-' + w.l_ + ' · ' + wr(w) + ' · ' + roi(w.roi) + ' ROI' +
        (w.clv && w.clv.n ? ' · ' + beatTxt(w) : '') + '</span></div><div class="vd-wr"><b class="num">' + usd(w.usd) + '</b>' + (w.press != null ? '<span class="num">' + w.press + 'x</span>' : '') + '</div></div>'; }).join('')
      : '<p class="vd-none">No proven, tracked or losing wallet at $250 or more.</p>') +
    (s.counts.unproven > (s.unproven_list || []).length ? '<p class="vd-more num">+' + (s.counts.unproven - (s.unproven_list || []).length) + ' more unproven or untracked</p>' : '') + '</div>';
}
function detail(g, key, v){
  var m = g.markets[key], names = sideOrder(g, m, key), ls = shadow(m, v);
  var side = ls ? ls.side : names.slice().sort(function(a, b){ return m.sides[b][v].sharp_usd - m.sides[a][v].sharp_usd; })[0], other = names.filter(function(n){ return n !== side; })[0];
  var S = m.sides[side][v], O = m.sides[other][v], tot = counted(S), proven = S.sharp_usd, against = nProven(O);
  var mine = sideWallets(S), theirs = sideWallets(O), lead = mine.filter(function(x){ return x.k === 'gold' || x.k === 'sharp'; })[0] || mine[0];
  var px = ls ? ls.price : null, fl = ls && ls.flagged, mv = fl && px != null ? (px - fl.price) * 100 : null;
  var h = '<div class="vd-top"><div><span class="vd-cap">' + g.sport.toUpperCase() + ' · ' + esc(teamName(g, 'away')) + ' at ' + esc(teamName(g, 'home')) + ' · ' + ct(g.gst, true) + ' CT</span>' +
    '<h2>' + esc(sideLabel(side, key, ls || {side: side})) + '</h2>' +
    (px != null ? '<div class="vd-px num"><b>' + cents(px) + '</b><span>' + (american(px) || '') + '</span>' + (mv != null ? '<em class="' + (mv > 0 ? 'up' : mv < 0 ? 'dn' : '') + '">' + (mv > 0 ? '+' : '') + mv.toFixed(1) + ' pts</em>' : '') + '</div>' +
      (fl ? '<span class="vd-sub num">flagged at ' + cents(fl.price) + ', ' + ct(fl.t) + ' CT</span>' : '') : '<span class="vd-sub">No suggested size on this market. Showing the side with the most proven money.</span>') +
    '</div><button type="button" class="vd-x press press-btn" aria-label="Close">' + XX + '</button></div>';
  h += '<div class="vd-hero"><div><b class="num">' + usd(tot) + '</b><span class="vd-op ' + (against ? 'no' : 'ok') + '">' + (against ? against + ' proven against' : 'Unopposed') + '</span></div>' +
    (ls ? '<div class="vd-u"><b class="num">' + units(ls) + 'u</b><span class="vc-tag">untested rule</span></div>' : '') + '</div>' +
    (tot ? '<div class="vd-mix"><i class="sharp" style="width:' + (proven / tot * 100).toFixed(1) + '%"></i><i class="unp" style="width:' + (S.unproven_usd / tot * 100).toFixed(1) + '%"></i><i class="loser" style="width:' + (S.loser_usd / tot * 100).toFixed(1) + '%"></i></div>' +
      '<div class="vd-mixl num"><span>Proven ' + Math.round(proven / tot * 100) + '%</span><span>Unproven ' + Math.round(S.unproven_usd / tot * 100) + '%</span>' + (S.loser_usd ? '<span>Losers ' + Math.round(S.loser_usd / tot * 100) + '%</span>' : '') + '</div>' : '');
  h += '<section class="vd-sec"><span class="vd-cap">Where the money sits</span><div class="vd-key"><span><i class="sharp"></i>proven</span><span><i class="gold"></i>sized up</span><span><i class="unp"></i>unproven</span><span><i class="loser"></i>losing</span><span><i class="opp"></i>other side</span><em>size = $</em></div>' + scatter(mine, theirs) + '</section>';
  h += leadCard(lead, side);
  h += '<section class="vd-sec"><span class="vd-cap">Who\'s on it</span><div class="vd-who">' + whoCol(side, S, tot, true) + whoCol(other, O, counted(O), false) + '</div></section>';
  if (ls){
    var rg = ls.rung && RUNG[ls.rung];
    h += '<section class="vd-sec"><span class="vd-cap">How the size is set</span><p class="vd-p"><b>' + (rg ? rg[0] : 'Press ladder') + '.</b> ' + (rg ? rg[1] : 'This side meets the pre-registered press-ladder gates.') +
      ' The size comes from the staking rules, built from Vault\'s own wallet records, with Pinnacle steam, the odds cap and the seat and edge caps. It has no graded record yet.</p>' + steamDetail(ls, key, side) + chainList(ls) + '</section>';
  }
  return h + '<p class="vd-foot">Sharp money is context. Price skill counts only past bets with a stored close; a wallet with fewer than ' + CLV_MIN + ' is listed but not plotted.</p>';
}
var DLG = null;
function openDetail(from, g, key, v){
  closeDetail(true);
  var root = from.closest('.vsc'), wrap = document.createElement('div');
  wrap.className = (root ? root.className : 'vsc') + ' vd-wrap';
  wrap.innerHTML = '<div class="vd-scrim"></div><div class="vd" role="dialog" aria-modal="true" aria-label="Play detail">' + detail(g, key, v) + '</div>';
  document.body.appendChild(wrap);
  DLG = {wrap: wrap, from: from, prevOverflow: document.documentElement.style.overflow, prevBody: document.body.style.overflow};
  document.documentElement.style.overflow = 'hidden'; document.body.style.overflow = 'hidden';
  void wrap.offsetWidth; wrap.classList.add('on');                     /* forced reflow, never rAF (CLAUDE.md motion trap 2) */
  wrap.addEventListener('click', function(e){ if (e.target.closest('.vd-x') || e.target.classList.contains('vd-scrim')) closeDetail(); });
  wrap.querySelector('.vd-x').focus();
}
function closeDetail(now){
  if (!DLG) return;
  var d = DLG; DLG = null;
  document.documentElement.style.overflow = d.prevOverflow; document.body.style.overflow = d.prevBody;
  if (d.from && document.contains(d.from)) d.from.focus();
  if (now) { d.wrap.remove(); return; }
  d.wrap.classList.remove('on');
  setTimeout(function(){ d.wrap.remove(); }, 420);
}
document.addEventListener('keydown', function(e){
  if (!DLG) return;
  if (e.key === 'Escape'){ closeDetail(); return; }
  if (e.key !== 'Tab') return;                                         /* keep focus inside the dialog */
  var f = [].filter.call(DLG.wrap.querySelectorAll('button,[href],[tabindex]:not([tabindex="-1"])'), function(x){ return x.offsetParent !== null; });
  if (!f.length) return;
  var first = f[0], last = f[f.length - 1];
  if (!DLG.wrap.contains(document.activeElement)){ e.preventDefault(); first.focus(); }
  else if (e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
});

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
  var head = '<div class="vc-top"><div><div class="vc-match">' + esc(teamName(g, 'away')) + ' <i>at</i> ' + esc(teamName(g, 'home')) + '</div>' +
    '<div class="vc-time"><span class="vc-sport">' + g.sport.toUpperCase() + '</span><span class="num">' + ct(g.gst, true) + ' CT</span></div></div>' +
    (g.frozen ? '<div class="vc-pill locked">' + ICON.lock + 'Locked ' + ct(g.cut) + '</div>' : '<div class="vc-pill live"><i></i>Live · locks ' + ct(g.cut) + '</div>') + '</div>';
  if (!keys.length){
    el.innerHTML = head + '<div class="vc-mod vc-empty"><b>Nothing to show yet</b><p>No wallet holds $250 or more on this game. The card fills in as money arrives and locks ' + ct(g.cut, true) + ' CT.</p></div>';
    return;
  }
  if (opt.folded){ el.innerHTML = head + foldHtml(g, keys[0]); return; }
  function strip(){
    return GROUPS.map(function(x){ var m = g.markets[x[0]], ls = m && shadow(m, st.variant);
      return '<button type="button" data-v="' + x[0] + '"' + (m ? '' : ' disabled') + (x[0] === st.group ? ' class="on"' : '') + '>' + x[1] + (ls ? '<span class="vc-dotu num">' + units(ls) + 'u</span>' : '') + '</button>'; }).join('');
  }
  el.innerHTML = head + '<div class="vseg fluid" data-k="group" role="tablist" aria-label="Market"><i class="v-pill"></i>' + strip() + '</div><div class="vc-body"></div>';
  var bodyEl = el.querySelector('.vc-body'), top = el.querySelector('.vseg[data-k=group]');
  function paint(){ bodyEl.innerHTML = body(g, st); var h = bodyEl.querySelector('.vseg'); if (h && h.offsetWidth) rail(h, false); }
  paint(); rail(top, false);
  el.addEventListener('toggle', function(e){ var d = e.target; if (d.dataset && d.dataset.d){ st.open[d.dataset.d] = d.open; var h = d.querySelector('.vseg'); if (h && d.open) rail(h, false); } }, true);
  el.addEventListener('click', function(e){
    if (e.target.closest('.vc-open')){ openDetail(e.target.closest('.vc-open'), g, st.group, st.variant); return; }
    var b = e.target.closest('.vseg > button');
    if (!b || b.disabled) return;
    var s = b.parentNode; st[s.dataset.k] = b.dataset.v;
    if (s === top){ [].forEach.call(s.children, function(c){ c.classList.toggle('on', c === b); }); rail(s, true); paint(); }
    else { top.innerHTML = '<i class="v-pill"></i>' + strip(); rail(top, false); paint(); }
  });
}


function units(ls){ var u = ls.units != null ? ls.units : ls.units_clean_ladder; return u == null ? null : String(u); }
/* slate strip: totals over every game in the file, stored fields only */
function slate(el, data){
  var usdSum = 0, sides = 0, wallets = {}, cl = {quiet:0, building:0, signal:0}, plays = 0, ex = 0;
  data.games.forEach(function(g){
    cl[climate(g, 'all')]++;
    Object.keys(g.markets).forEach(function(k){ var m = g.markets[k]; if (shadow(m, 'all')) plays++;
      Object.keys(m.sides).forEach(function(n){ var s = m.sides[n].all; usdSum += s.sharp_usd; ex += s.excluded_usd; if (s.sharp_usd > 0) sides++;
        s.list.forEach(function(w){ wallets[w.w] = 1; }); }); });
  });
  var t = function(v, l, sub, cls){ return '<div class="vc-slt ' + (cls || '') + '"><span>' + l + '</span><b class="num">' + v + '</b><em>' + sub + '</em></div>'; };
  el.innerHTML = t(plays, 'Suggested plays', 'of ' + data.games.length + ' games', 'good') +
    t(usd(usdSum), 'Proven money', sides + ' sides, ' + Object.keys(wallets).length + ' wallets', 'gold') +
    '<div class="vc-slt clim"><span>Climate</span><div class="vc-sldots">' +
      ['signal', 'building', 'quiet'].map(function(k){ return new Array(cl[k] + 1).join('<i class="' + k + '"></i>'); }).join('') + '</div><em>' +
      cl.signal + ' signal · ' + cl.building + ' building · ' + cl.quiet + ' quiet</em></div>';
}

function foldHtml(g, key){
  var m = g.markets[key], tot = Object.keys(m.sides).reduce(function(t, n){ return t + counted(m.sides[n].all); }, 0);
  return '<button type="button" class="vc-fold"><b>No proven money yet</b>' + usd(tot) + ' on the ' + GNAME[key] + '<span>Show</span></button>';
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
  var s = document.createElement('style'); s.id = 'vsc-css'; s.textContent = RESET + CSS + NBA + DETAIL + RECORD_CSS + STEAM_CSS + HC_CSS; document.head.appendChild(s);
}
function rootClass(el, o){ el.className = 'vsc' + (o.skin === 'new' ? ' vsc-new' : o.skin === 'nba' ? ' vsc-nba' : ''); }
function card(g, o, folded){
  var el = document.createElement('div'); el.className = 'vc';
  mount(el, g, {folded: folded, group: o.group});
  if (folded) el.addEventListener('click', function(e){ if (e.target.closest('.vc-fold')){ SHOWN[g.ev] = 1; el.replaceWith(card(g, o, false)); } });
  return el;
}

/* ---------- Record: the side card's graded results and the benchmark head-to-head (docs/side-card-record.md) ----------
   Files written every 2 hours by .github/workflows/pm-record.yml on pm-holders-data/pm_record. Interim and report-only: the
   pre-registered test (docs/sharp-card-prereg.md) gives a verdict once, on its final read date. Every number is a stored field. */
var REC_BASE = (LOCAL && (location.search.match(/[?&]rec=([^&]+)/) || [])[1]) ? decodeURIComponent(location.search.match(/[?&]rec=([^&]+)/)[1])
  : 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-holders-data/pm_record/';
var REC = {d: null, state: 'idle', at: 0};
var REC_N = 300;                                                       /* prereg minimum n per sport */
var REC_READ = {nba: 'the first Monday after the 2026-27 regular season', nfl: 'the Tuesday after Week 18', cfb: 'the Monday after conference championship weekend'};
function months(){ var d = new Date(), a = d.toISOString().slice(0, 7); d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() - 1); return [d.toISOString().slice(0, 7), a]; }
function jsonl(t){ return (t || '').split('\n').filter(Boolean).map(function(l){ try { return JSON.parse(l); } catch (e) { return null; } }).filter(Boolean); }
function recLoad(done){
  if (REC.state === 'busy'){ (REC.wait = REC.wait || []).push(done); return; }      /* a second caller waits for the same fetch */
  if (REC.d && Date.now() - REC.at < 300000){ done(); return; }
  REC.state = 'busy';
  var get = function(p, txt){ return fetch(REC_BASE + p + '?t=' + Math.floor(Date.now() / 300000), {cache: 'no-store'})
    .then(function(r){ return r.ok ? (txt ? r.text() : r.json()) : null; }).catch(function(){ return null; }); };
  var rows = [];
  ['nba', 'nfl', 'cfb'].forEach(function(s){ months().forEach(function(m){ rows.push(get('cards/' + s + '/' + m + '.jsonl', 1), get('benchmark/rows/' + s + '/' + m + '.jsonl', 1)); }); });
  Promise.all([get('cards_record.json'), get('h2h_record.json')].concat(rows)).then(function(r){
    var cards = [], sf = [];
    r.slice(2).forEach(function(t, i){ (i % 2 ? sf : cards).push.apply(i % 2 ? sf : cards, jsonl(t)); });
    REC.d = r[0] || r[1] ? {cards: r[0], h2h: r[1], cardRows: cards, sfRows: sf} : null;
    REC.state = REC.d ? 'ok' : 'none'; REC.at = Date.now();
    var w = REC.wait || []; REC.wait = [];
    done(); w.forEach(function(f){ f(); });
  });
}
function wl(s){ return s.w + '–' + s.l + (s.p ? '–' + s.p : ''); }
function u2(x){ return (x > 0 ? '+' : x < 0 ? '−' : '') + trim(Math.abs(x || 0).toFixed(2)) + 'u'; }
function sumRec(parts){
  var t = {n: 0, w: 0, l: 0, p: 0, units_pl: 0, roi_n: 0, roi_s: 0};
  parts.forEach(function(s){ if (!s || !s.n) return; t.n += s.n; t.w += s.w; t.l += s.l; t.p += s.p || 0; t.units_pl += s.units_pl || 0;
    if (s.flat_roi != null){ t.roi_s += s.flat_roi * s.n; t.roi_n += s.n; } });
  t.flat_roi = t.roi_n ? t.roi_s / t.roi_n : null;
  return t;
}
function gameName(ev){ var m = /^[a-z]+-([a-z0-9]+)-([a-z0-9]+)-(\d{4})-(\d{2})-(\d{2})/.exec(ev || ''); if (!m) return {t: esc(ev || ''), d: ''};
  return {t: m[1].toUpperCase() + ' at ' + m[2].toUpperCase(), d: new Date(Date.UTC(+m[3], +m[4] - 1, +m[5], 12)).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'})}; }
function resTag(r){ return '<span class="vr-res ' + (r || 'na') + '">' + ({win: 'W', loss: 'L', push: 'P'}[r] || '–') + '</span>'; }
function playLabel(side, group, line, outs){
  var ln = line != null && outs && outs[1] === side ? -line : line;
  return group === 'ml' ? side + ' ML' : group === 'total' ? side + (line != null && side.indexOf(' ') < 0 ? ' ' + line : '') :
    side + (ln != null ? ' ' + (ln > 0 ? '+' : '') + ln : ' spread');
}
function scoreTile(name, sub, s, other){
  var lead = s.n && other.n && s.units_pl > other.units_pl ? '<span class="vr-lead">Leads by ' + trim((s.units_pl - other.units_pl).toFixed(2)) + 'u</span>' : '';
  if (!s.n) return '<div class="vr-tile"><div class="vr-th"><b>' + name + '</b></div><div class="vr-big num dim">—</div><p class="vr-ts">No graded plays yet</p><p class="vr-tsub">' + sub + '</p></div>';
  return '<div class="vr-tile' + (lead ? ' lead' : '') + '"><div class="vr-th"><b>' + name + '</b>' + lead + '</div>' +
    '<div class="vr-big num ' + (s.units_pl > 0 ? 'up' : s.units_pl < 0 ? 'dn' : '') + '">' + u2(s.units_pl) + '</div>' +
    '<p class="vr-ts num">' + wl(s) + (s.flat_roi != null ? ' · ' + roi(s.flat_roi) + ' ROI' : '') + ' · ' + s.n + (s.n === 1 ? ' play' : ' plays') + '</p>' +
    '<p class="vr-tsub">' + sub + '</p></div>';
}
function cell(s){ return s && s.n ? '<span class="num">' + wl(s) + '</span><em class="num ' + (s.units_pl > 0 ? 'up' : s.units_pl < 0 ? 'dn' : '') + '">' + u2(s.units_pl) + '</em>' : '<span class="vr-none">—</span>'; }
var REC_SP = null, REC_ALL = false;
function recSport(sp, D){
  var c = ((D.cards || {}).sports || {})[sp] || {}, h = ((D.h2h || {}).sports || {})[sp] || {};
  var G = [['ml', 'Moneyline'], ['spread', 'Spread'], ['total', 'Total']];
  var vg = function(g){ return (h[g] || {}).vault_shown_size || ((((c.sf || {}).all || {})[g] || {}).all_cards); };
  var bg = function(g){ return (h[g] || {}).benchmark; };
  var V = sumRec(G.map(function(g){ return vg(g[0]); })), B = sumRec(G.map(function(g){ return bg(g[0]); }));
  var out = '<div class="vr-score">' + scoreTile('Vault', 'The suggested size on every card', V, B) + scoreTile('Benchmark', 'An outside tracker\'s plays, as shown at our lock', B, V) + '</div>';
  out += '<p class="vr-note">' + (V.n + B.n ? 'Graded by Polymarket\'s result at each side\'s own price. ' : '') + 'Small samples swing hard, so treat this as a running tally, not a verdict.</p>';
  out += '<section class="vr-card"><h3>By market</h3><div class="vr-grid"><span></span><span class="vr-col">Vault</span><span class="vr-col">Benchmark</span>' +
    G.map(function(g){ return '<span class="vr-mk">' + g[1] + '</span><span class="vr-c">' + cell(vg(g[0])) + '</span><span class="vr-c">' + cell(bg(g[0])) + '</span>'; }).join('') + '</div></section>';
  /* the pre-registered forward test: counted moneyline locks toward 300, and the lock record over every market */
  var ml = ((((c.lock || {}).all || {}).ml || {}).counted) || {}, L = sumRec(G.map(function(g){ return ((((c.lock || {}).all || {})[g[0]] || {}).counted); }));
  var clvN = G.reduce(function(t, g){ var x = ((((c.lock || {}).all || {})[g[0]] || {}).counted) || {}; return t + (x.clv_n || 0); }, 0);
  var clvS = G.reduce(function(t, g){ var x = ((((c.lock || {}).all || {})[g[0]] || {}).counted) || {}; return t + (x.clv_n ? x.clv_mean * x.clv_n : 0); }, 0);
  var n = ml.n || 0, pct = Math.min(100, n / REC_N * 100);
  out += '<section class="vr-card"><div class="vr-fh"><h3>Forward test</h3><span class="num">' + n + ' / ' + REC_N + '</span></div>' +
    '<div class="vr-bar" role="progressbar" aria-valuemin="0" aria-valuemax="' + REC_N + '" aria-valuenow="' + n + '"><i style="width:' + pct.toFixed(1) + '%"></i></div>' +
    '<p class="vr-fs num">' + (L.n ? 'Locks ' + wl(L) + ' · ' + u2(L.units_pl) + (clvN ? ' · CLV ' + (clvS / clvN > 0 ? '+' : '') + trim((clvS / clvN * 100).toFixed(1)) + ' pts' : '') : 'No counted lock has settled yet') + '</p>' +
    '<p class="vr-fn">The registered test needs ' + REC_N + ' counted moneyline locks and reads once, on ' + (REC_READ[sp] || 'its registered date') + '.' +
    ((c.data_quality || {}).fail ? ' <b class="dn">Data-quality check failing: too many locks have no fresh price.</b>' : '') + '</p></section>';
  /* open plays: Vault's suggested sizes on cards still live (they lock at T-15), and every locked play from either side still waiting for
     its result. Each one lands in the record above once its market settles (the record job runs every 2 hours). */
  var og = {}, nowS = Date.now() / 1000;
  var addO = function(ev, gst, row){ (og[ev] = og[ev] || {gst: gst, rows: [], live: false}).rows.push(row); };
  ((STORE.d || {}).games || []).filter(function(g){ return g.sport === sp && !g.frozen; }).forEach(function(g){
    Object.keys(g.markets).forEach(function(k){ var x = ((g.markets[k].sf || {}).all) || {};
      if (x.side && x.units > 0){ addO(g.ev, g.gst, {who: 'Vault', label: playLabel(x.side, k, x.line, x.outs), units: x.units}); og[g.ev].live = true; og[g.ev].cut = g.cut; } }); });
  (((D.cards || {}).open) || []).filter(function(r){ return r.sport === sp && r.gst > nowS - 7 * 86400; }).forEach(function(r){
    addO(r.ev, r.gst, {who: r.play === 'lock' ? 'Lock' : 'Vault', label: playLabel(r.side, r.group, r.line, r.outs), units: r.units}); });
  (((D.h2h || {}).open) || []).filter(function(r){ return r.sport === sp && r.gst > nowS - 7 * 86400; }).forEach(function(r){
    addO(r.ev, r.gst, {who: 'Bench', label: playLabel(r.team, r.group, null, null), units: r.units}); });
  var oev = Object.keys(og).sort(function(a, b){ return (og[a].live - og[b].live) || (og[a].gst - og[b].gst); });
  if (oev.length){
    out += '<section class="vr-card"><div class="vr-fh"><h3>Open plays</h3><span class="num">' + oev.reduce(function(t, e){ return t + og[e].rows.length; }, 0) + ' pending</span></div>' +
      '<p class="vr-fn">They count in the record above once their games settle.</p><div class="vr-games">' + oev.map(function(ev){ var x = og[ev], gn = gameName(ev);
      var chip = x.live ? '<span class="vr-st live">Locks ' + ct(x.cut || x.gst - 900) + '</span>' : nowS < x.gst ? '<span class="vr-st lock">Locked · starts ' + ct(x.gst) + '</span>' : '<span class="vr-st wait">Awaiting result</span>';
      return '<div class="vr-g"><div class="vr-gn"><b>' + gn.t + '</b><span>' + gn.d + '</span>' + chip + '</div><div class="vr-gp">' + x.rows.map(function(r){
        return '<div class="vr-pl"><span class="vr-who ' + r.who.toLowerCase() + '">' + r.who + '</span><b>' + esc(r.label) + '</b><span class="num vr-u">' + (r.units != null ? r.units + 'u' : '') + '</span><span class="vr-res open" aria-label="pending"></span></div>'; }).join('') + '</div></div>'; }).join('') + '</div></section>';
  }
  /* recent games: Vault's plays (suggested size, and the lock when it counts) and the benchmark's, newest first */
  var by = {};
  D.cardRows.filter(function(r){ return r.sport === sp && r.kind !== 'close' && r.side && r.variant === 'all' && (r.play === 'sf' || r.counts); })
    .forEach(function(r){ (by[r.ev] = by[r.ev] || {gst: r.gst, v: [], s: []}).v.push(r); });
  D.sfRows.filter(function(r){ return r.sport === sp && r.set === 'at_cut'; }).forEach(function(r){ (by[r.ev] = by[r.ev] || {gst: r.gst, v: [], s: []}).s.push(r); });
  var evs = Object.keys(by).sort(function(a, b){ return by[b].gst - by[a].gst; }), shown = REC_ALL ? evs : evs.slice(0, 8);
  if (evs.length){
    var pl = function(who, r, label, res){ return '<div class="vr-pl"><span class="vr-who ' + who.toLowerCase() + '">' + who + '</span><b>' + esc(label) + '</b><span class="num vr-u">' + (r.units != null ? r.units + 'u' : '') + '</span>' + resTag(res) + '</div>'; };
    out += '<section class="vr-card"><h3>Recent games</h3><div class="vr-games">' + shown.map(function(ev){ var x = by[ev], gn = gameName(ev);
      return '<div class="vr-g"><div class="vr-gn"><b>' + gn.t + '</b><span>' + gn.d + '</span></div><div class="vr-gp">' +
        x.v.map(function(r){ return pl(r.play === 'lock' ? 'Lock' : 'Vault', r, playLabel(r.side, r.group, r.line, r.outs), r.status === 'unpriced' ? null : r.res); }).join('') +
        x.s.map(function(r){ return pl('Bench', r, playLabel(r.group === 'ml' ? (r.side || r.team) : r.team, r.group, null, null), r.res); }).join('') + '</div></div>'; }).join('') + '</div>' +
      (evs.length > 8 ? '<button type="button" class="vr-more press press-btn">' + (REC_ALL ? 'Show fewer' : 'Show all ' + evs.length + ' games') + '</button>' : '') + '</section>';
  }
  /* everything else, one tap away */
  var notes = [], X = sumRec(G.map(function(g){ return (h[g[0]] || {}).vault_sfx; })), cc = c.cards || {};
  if (X.n) notes.push('With the benchmark\'s exclusion list instead of Vault\'s, the suggested size is ' + wl(X) + ', ' + u2(X.units_pl) + '.');
  G.forEach(function(g){ var x = h[g[0]] || {}, a = x.benchmark_after_cut || {}, cl = x.benchmark_at_cut_cancelled_later, up = x.benchmark_unpriced_spread_rungs;
    if (a.n) notes.push('Benchmark ' + g[1].toLowerCase() + ': ' + a.n + ' play' + (a.n === 1 ? '' : 's') + ' added or sized up after our lock (' + wl(a) + '), kept out of its record above.');
    if (cl) notes.push('Benchmark ' + g[1].toLowerCase() + ': ' + cl + ' cancelled after our lock, still counted above.');
    if (up) notes.push('Benchmark spread picks name no line, so ' + up + (up === 1 ? ' has' : ' have') + ' no priced result.'); });
  if (cc.frozen) notes.push(cc.frozen + ' cards frozen, ' + (cc.counted || 0) + ' count for the test' + Object.keys(cc.not_counted_by_reason || {}).map(function(k){ return '; ' + cc.not_counted_by_reason[k] + ' ' + esc(k); }).join('') + '.');
  if (notes.length) out += '<details class="vr-notes"><summary>Notes</summary><ul>' + notes.map(function(t){ return '<li>' + t + '</li>'; }).join('') + '</ul></details>';
  return out;
}
function renderRecord(el, o){
  if (!REC.d) el.innerHTML = '<div class="vr-skel"><i></i><i></i></div><div class="vr-skel tall"><i></i></div>';
  recLoad(function(){
    if (!document.contains(el)) return;                                  /* a newer render replaced this one */
    if (!REC.d){ el.innerHTML = '<div class="vc-note"><b>No record yet</b><p>The record fills in once frozen cards settle. It updates every 2 hours.</p></div>'; return; }
    var have = ['nba', 'nfl', 'cfb'].filter(function(s){ return ((REC.d.cards || {}).sports || {})[s] || ((REC.d.h2h || {}).sports || {})[s]; });
    var fixed = o.sport && o.sport !== 'all' ? o.sport : null, sp = fixed || (have.indexOf(REC_SP) >= 0 ? REC_SP : have[0]);
    var gen = Math.max((REC.d.cards || {}).generated || 0, (REC.d.h2h || {}).generated || 0);
    var head = '<div class="vr-head">' + (!fixed && have.length > 1 ? '<div class="vseg sm vr-sp" role="tablist" aria-label="Sport"><i class="v-pill"></i>' +
      have.map(function(s){ return '<button type="button" data-v="' + s + '"' + (s === sp ? ' class="on"' : '') + '>' + s.toUpperCase() + '</button>'; }).join('') + '</div>' : '<span></span>') +
      '<span class="vr-upd">' + (gen ? 'Updated ' + ct(gen) + ' CT' : '') + '</span></div>';
    var body = sp ? recSport(sp, REC.d) : '';
    el.innerHTML = '<div class="vr">' + head + (body || '<div class="vc-note"><b>No graded plays for this sport yet</b><p>Plays settle after each game; the record updates every 2 hours.</p></div>') + '</div>';
    var strip = el.querySelector('.vr-sp');
    if (strip){ rail(strip, false); strip.addEventListener('click', function(e){ var b = e.target.closest('button'); if (!b || b.classList.contains('on')) return;
      REC_SP = b.dataset.v; [].forEach.call(strip.children, function(c){ if (c.tagName === 'BUTTON') c.classList.toggle('on', c === b); }); rail(strip, true); renderRecord(el, o); }); }
    var more = el.querySelector('.vr-more');
    if (more) more.addEventListener('click', function(){ REC_ALL = !REC_ALL; renderRecord(el, o); });
  });
}
function renderCards(el, o){
  if (STORE.state === 'loading'){ el.innerHTML = '<div class="vc-note"><b>Loading the cards</b></div>'; return; }
  if (STORE.state === 'none'){ el.innerHTML = '<div class="vc-note"><b>No cards yet</b><p>Proven sharps cards start once the Polymarket holders log is running. Nothing is shown until then.</p></div>'; return; }
  var sp = o.sport && o.sport !== 'all' ? o.sport : null, rank = {signal: 0, building: 1, quiet: 2};
  var games = STORE.d.games.filter(function(g){ return !sp || g.sport === sp; }).map(function(g){ return {g: g, c: climate(g, 'all')}; })
    .sort(function(a, b){ return (rank[a.c] - rank[b.c]) || (a.g.gst - b.g.gst); });
  el.innerHTML = '';
  if (!games.length){ el.innerHTML = '<div class="vc-note"><b>No upcoming games</b><p>No card has been built for this sport yet.</p></div>'; return; }
  var sl = document.createElement('div'); sl.className = 'vc-sl'; slate(sl, {games: games.map(function(x){ return x.g; })}); el.appendChild(sl);
  var list = document.createElement('div'); list.className = 'vsc-list';
  games.forEach(function(x){ list.appendChild(card(x.g, o, x.c === 'quiet' && !SHOWN[x.g.ev] && Object.keys(x.g.markets).length > 0)); });
  el.appendChild(list);
  [].forEach.call(el.querySelectorAll('.vseg'), function(s){ rail(s, false); });
}
var VIEW = 'cards';
try { VIEW = localStorage.getItem('vsc-view') === 'record' ? 'record' : 'cards'; } catch (e) {}
function mountPage(el, o){
  o = o || {}; css(); rootClass(el, o);
  if (!el._vr){
    el._vr = 1;
    el.addEventListener('click', function(e){
      var b = e.target.closest('.vr-view > button');
      if (!b || b.classList.contains('on')) return;
      VIEW = b.dataset.v; try { localStorage.setItem('vsc-view', VIEW); } catch (x) {}
      [].forEach.call(b.parentNode.children, function(c){ if (c.tagName === 'BUTTON') c.classList.toggle('on', c === b); });
      rail(b.parentNode, true); paint();
    });
  }
  function paint(){
    var body = el.querySelector('.vr-body');
    if (VIEW === 'record') renderRecord(body, o); else renderCards(body, o);
  }
  host(el, function(){
    OPT = o;
    if (VIEW === 'record' && el._sp === (o.sport || '') && el.querySelector('.vr-body .vr, .vr-body .vc-note, .vr-body .vr-skel')) return;   /* a card refresh leaves the record alone */
    el._sp = o.sport || '';
    el.innerHTML = '<div class="vseg sm vr-view" role="tablist" aria-label="View"><i class="v-pill"></i><button type="button" data-v="cards"' + (VIEW === 'cards' ? ' class="on"' : '') +
      '>Cards</button><button type="button" data-v="record"' + (VIEW === 'record' ? ' class="on"' : '') + '>Record</button></div><div class="vr-body"></div>';
    paint(); rail(el.querySelector('.vr-view'), false);
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
    var h = document.createElement('div'); h.className = 'vc-sech'; h.innerHTML = 'Proven sharps<span>who holds each side on Polymarket</span>'; el.appendChild(h);
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
