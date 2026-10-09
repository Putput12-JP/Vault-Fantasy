/* ════════════════════════════════════════════════════════════════════════
   VAULT · PROPS BOARD  (read by fetch-sharp-money.mjs → data.json `props`)

   One row per (player, stat) with every venue's price at the SAME line:
     books      Pinnacle + US books + Sleeper / Underdog (lineup-feed vegas_player_props)
     Kalshi     data/kalshi_props.json  (mid + spread + open interest, no per-side asks)
     Novig      data/novig_props.json   (real bid/ask both sides, depth)

   Fair price = Pinnacle's power-devigged price at its line. Without Pinnacle, a LIQUID
   Kalshi strike (tight spread, real open interest) stands in; otherwise there is no fair
   and the row can show price gaps but never a +EV call.

   A side is only priced against fair at a venue quoting the same number. Different
   lines are different bets, so they are never compared.

   buildPropsBoard({ feed, kalshi, novig }) -> { asof, sources, rows }
   ════════════════════════════════════════════════════════════════════════ */

export const nkey = s => String(s || '').toLowerCase().replace(/\b(jr|sr|ii|iii|iv|v)\b\.?/g, '').replace(/[^a-z]/g, '');

const LABEL = {
  rec_yd: 'Receiving yards', rec: 'Receptions', rush_yd: 'Rushing yards', rush_att: 'Rush attempts',
  pass_yd: 'Passing yards', pass_td: 'Passing TDs', pass_att: 'Pass attempts', pass_cmp: 'Completions',
  pass_int: 'Interceptions', pass_rush_yd: 'Pass + rush yards', rush_rec_yd: 'Rush + rec yards', anytime_td: 'Anytime TD',
};
const impl = a => a == null ? null : a < 0 ? -a / (-a + 100) : 100 / (a + 100);
const toAm = p => p == null || p <= 0 || p >= 1 ? null : p >= 0.5 ? Math.round(-100 * p / (1 - p)) : Math.round(100 * (1 - p) / p);
// Power devig: find k with po^k + pu^k = 1 (favourite-longshot aware; same family as the game code's powFair).
function powFair(po, pu) {
  if (!(po > 0 && pu > 0)) return null;
  if (po + pu <= 1) return po / (po + pu);
  let lo = 1, hi = 3;
  for (let i = 0; i < 40; i++) { const k = (lo + hi) / 2; if (po ** k + pu ** k > 1) lo = k; else hi = k; }
  const k = (lo + hi) / 2; return po ** k;
}
const MIN_EV = 0.02;        // below this a "+EV" is inside the noise of a devig
const MIN_GAP = 0.03;       // 3 points of probability between venues on one side
const TIGHT_SPR = 0.06;     // exchange spread (prob points) at which its ask also says where the market is, not just what is for sale
const MIN_DEPTH = 100;      // $ resting at an exchange before its price counts as takeable
const STALE_S = 3 * 3600;   // fair/price older than this and a "+EV" is probably just the line having moved
const BIG_EV = 0.10;        // an edge this large against Pinnacle is far likelier a data problem than a gift: flag it
const DFS = new Set(['Underdog Fantasy', 'Sleeper', 'PrizePicks', 'Fliff', 'Pick6 (DraftKings)']);   // priced lopsided on purpose: a gap against them is their juice, not a market disagreement
const KAL_SPR = 0.04, KAL_OI = 100;   // what makes a Kalshi strike liquid enough to anchor on

export function buildPropsBoard({ feed, kalshi, novig }) {
  const rows = [], src = { pinnacle: 0, kalshi: 0, novig: 0, players: 0 };
  const nowS = Date.now() / 1000, age = g => g ? nowS - Date.parse(g) / 1000 : Infinity;
  const feedStale = age(feed?.generated) > STALE_S, kalStale = age(kalshi?.generated) > STALE_S, novStale = age(novig?.generated) > STALE_S;
  const K = kalshi?.markets || {}, NV = novig?.markets || {};
  for (const [pid, p] of Object.entries(feed?.vegas_player_props || {})) {
    const nk = nkey(p.name);
    for (const [mkt, l] of Object.entries(p.lines || {})) {
      if (!LABEL[mkt]) continue;
      const qs = (l.quotes || []).filter(q => q.line != null);
      const pin = qs.find(q => q.book === 'Pinnacle' && q.over != null && q.under != null);
      const ref = pin ? pin.line : l.line;
      if (ref == null) continue;
      const venues = [];   // { src, kind, over:{p,am,depth?}, under:{…}, line }
      for (const q of qs) {
        if (q.line !== ref || q.over == null || q.under == null) continue;
        venues.push({ src: q.book, kind: 'book', over: { p: impl(q.over), am: q.over }, under: { p: impl(q.under), am: q.under } });
      }
      const nv = (NV[mkt]?.[nk] || []).find(r => r.k === ref);
      if (nv && (nv.oa != null || nv.ua != null)) {
        venues.push({ src: 'Novig', kind: 'exchange', mid: nv.mid, spr: nv.spr, depth: nv.depth, age: nv.t,
          over: nv.oa != null ? { p: nv.oa, am: toAm(nv.oa), depth: nv.depth } : null, under: nv.ua != null ? { p: nv.ua, am: toAm(nv.ua), depth: nv.depth } : null });
        src.novig++;
      }
      const kl = (K[mkt]?.[nk] || []).find(r => r.k === ref);
      if (kl && kl.fair != null) {
        const h = Math.min(kl.spr ?? 0.04, 0.2) / 2;
        venues.push({ src: 'Kalshi', kind: 'exchange', mid: kl.fair, spr: kl.spr, oi: kl.oi, liquid: kl.spr <= KAL_SPR && kl.oi >= KAL_OI,
          over: { p: Math.min(0.99, kl.fair + h), am: toAm(Math.min(0.99, kl.fair + h)), oi: kl.oi }, under: { p: Math.min(0.99, 1 - kl.fair + h), am: toAm(Math.min(0.99, 1 - kl.fair + h)), oi: kl.oi } });
        src.kalshi++;
      }
      if (venues.length < 2) continue;   // nothing to compare

      let fair = null, fairSrc = null;
      if (pin) { fair = powFair(impl(pin.over), impl(pin.under)); fairSrc = 'Pinnacle'; src.pinnacle++; }
      else { const kv = venues.find(v => v.src === 'Kalshi' && v.liquid); if (kv) { fair = kv.mid; fairSrc = 'Kalshi'; } }

      // per side: every venue's price, EV vs fair, and the spread of prices between venues
      const sides = {};
      for (const side of ['over', 'under']) {
        const pf = fair == null ? null : side === 'over' ? fair : 1 - fair;
        const vs = venues.filter(v => v[side]?.p != null).map(v => {
          const x = v[side];
          const thin = v.kind === 'exchange' && ((v.src === 'Novig' && (x.depth ?? 0) < MIN_DEPTH) || (v.src === 'Kalshi' && !v.liquid));
          return { src: v.src, kind: v.kind, spr: v.spr ?? null, p: +x.p.toFixed(4), am: x.am, ev: pf == null || v.src === fairSrc ? null : +(pf / x.p - 1).toFixed(4), depth: x.depth ?? null, oi: x.oi ?? null, thin };
        });
        const takeable = vs.filter(v => !v.thin);
        const best = takeable.length ? takeable.reduce((a, b) => a.p <= b.p ? a : b) : null;
        const worst = takeable.length > 1 ? takeable.reduce((a, b) => a.p >= b.p ? a : b) : null;
        sides[side] = { fair: pf == null ? null : +pf.toFixed(4), venues: vs, best, gap: best && worst ? +(worst.p - best.p).toFixed(4) : 0, gapFrom: worst?.src || null };
      }
      // the headline call: the side + venue with the most EV that is takeable and not the fair source itself
      let call = null;
      for (const side of ['over', 'under']) for (const v of sides[side].venues) {
        if (v.thin || v.ev == null || v.ev < MIN_EV || v.src === fairSrc) continue;
        if (!call || v.ev > call.ev) call = { side, src: v.src, kind: v.kind, am: v.am, p: v.p, ev: v.ev, depth: v.depth };
      }
      if (call) {
        // verify flags: say WHY a call should be checked before it is bet
        const why = [];
        if (feedStale && (fairSrc === 'Pinnacle' || call.kind === 'book')) why.push('book prices are old');
        if (kalStale && (fairSrc === 'Kalshi' || call.src === 'Kalshi')) why.push('Kalshi prices are old');
        if (novStale && call.src === 'Novig') why.push('Novig prices are old');
        if (call.ev >= BIG_EV) why.push('edge this big is usually a moved line');
        call.check = why;
        call.stale = why.some(w => /are old|is old/.test(w) || /old$/.test(w));   // an edge against an old price: never tracked
        call.big = call.ev >= BIG_EV;
      }
      // exchange price differs from the field: any exchange vs any other venue by MIN_GAP on one side
      let diff = null;
      for (const side of ['over', 'under']) {
        const ex = sides[side].venues.filter(v => v.kind === 'exchange' && !v.thin);
        for (const e of ex) for (const o of sides[side].venues) {
          if (o.src === e.src || o.thin || DFS.has(o.src)) continue;
          const op = o.src === fairSrc && sides[side].fair != null ? sides[side].fair : o.p;   // the fair source's own price carries vig: compare its no-vig price
          const d = op - e.p;   // positive: the exchange is cheaper than the other venue
          // An exchange asking MORE than the field is usually just a wide book (nobody offering). Only trust that direction when the quote is tight.
          if (d < 0 && !(e.spr != null && e.spr <= TIGHT_SPR)) continue;
          if (Math.abs(d) >= MIN_GAP && (!diff || Math.abs(d) > Math.abs(diff.d))) diff = { side, d: +d.toFixed(4), cheap: d > 0 ? e.src : o.src, rich: d > 0 ? o.src : e.src, cheapAm: d > 0 ? e.am : o.am, richAm: d > 0 ? o.am : e.am, fairBased: op !== o.p };
        }
      }
      if (!call && !diff) continue;
      src.players++;
      rows.push({
        pid, name: p.name, team: p.team, pos: p.pos, mkt, label: LABEL[mkt], line: ref,
        fair: fair == null ? null : +fair.toFixed(4), fairSrc,
        over: sides.over, under: sides.under, call, diff,
      });
    }
  }
  rows.sort((a, b) => (b.call?.ev ?? -1) - (a.call?.ev ?? -1) || Math.abs(b.diff?.d ?? 0) - Math.abs(a.diff?.d ?? 0));
  return { asof: Math.floor(Date.now() / 1000), sources: { ...src, stale: { books: feedStale, kalshi: kalStale, novig: novStale }, novigAsof: novig?.generated || null, kalshiAsof: kalshi?.generated || null, feedAsof: feed?.generated || null }, rows: rows.slice(0, 500) };
}
