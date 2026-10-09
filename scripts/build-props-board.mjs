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
// How old each input may be before a call built on it is held back. Every one of these is refreshed inside the Cloudflare-driven Sharp Money
// run (Pinnacle + pick'em apps + Kalshi + Novig each poll), so 30 min means a run or a source failed. US books (DK/FD/...) only come from the
// ParlayAPI feed, which is slower, so they get a longer leash.
const FRESH_S = 30 * 60, FRESH_US_S = 90 * 60;
const OWNED = new Set(['Pinnacle', 'PrizePicks', 'Underdog Fantasy', 'Sleeper']);   // pulled directly each run
const MOVED_GAP = 0.07;     // a deep, tight exchange this far (probability points) from the fair price at the SAME line has priced a line move the reference has not seen   // fair/price older than this and a "+EV" is probably just the line having moved
const BIG_EV = 0.10;        // an edge this large against Pinnacle is far likelier a data problem than a gift: flag it
const DFS = new Set(['Underdog Fantasy', 'Sleeper', 'PrizePicks', 'Fliff', 'Pick6 (DraftKings)']);   // priced lopsided on purpose: a gap against them is their juice, not a market disagreement
const KAL_SPR = 0.04, KAL_OI = 100;   // what makes a Kalshi strike liquid enough to anchor on

// ── line conversion: P(over L') from a fair price at L (scripts/backtest_prop_line_shift.py) ──
// logit P(over L') = logit(P(over L)) + (L - L') / s,  s = c * L^b per market. Out of sample on 2025 moved lines it beat
// both the open price and the unshifted close. Beyond MAX_SHIFT of the line it is extrapolation, so it returns null.
const MAX_SHIFT = 0.25;
const lgt = p => Math.log(p / (1 - p)), sgm = x => 1 / (1 + Math.exp(-x));
export function shiftFair(shift, mkt, pOver, from, to) {
  if (pOver == null || from == null || to == null) return null;
  if (from === to) return pOver;
  const m = shift?.[mkt]; if (!m || !(from > 0) || Math.abs(to - from) / from > MAX_SHIFT) return null;
  const s = m.c * from ** m.b;
  return Math.min(0.97, Math.max(0.03, sgm(lgt(Math.min(0.995, Math.max(0.005, pOver))) + (from - to) / s)));
}
// The backtest showed edges of 10%+ pay well under what they promise (promised +16%, paid +10%), while 3-10% paid about what
// they promised. So the edge shown as "realistic" is flat to 8% and then keeps only a third of the excess.
export const realisticEv = ev => ev <= 0.08 ? ev : 0.08 + 0.35 * (ev - 0.08);
// Eighth-Kelly on the realistic edge, capped at 1.5% of bankroll: the realistic edge is itself an estimate (backtest +10.4% was +/-5.2%),
// so full or even quarter Kelly would size to a number we are not sure of. f = edge * p / (1 - p) for a price of implied probability p.
export const stakePct = (evAdj, p) => evAdj > 0 && p > 0 && p < 1 ? Math.min(1.5, +(12.5 * evAdj * p / (1 - p)).toFixed(2)) : 0;
const PICKEM = new Set(['PrizePicks', 'Underdog Fantasy', 'Sleeper']);
const SHIFT_MIN_EV = 0.05;   // a converted price carries model error the same-line price does not, so it needs a bigger edge

export function buildPropsBoard({ feed, kalshi, novig, shift }) {
  const rows = [], legs = [], src = { pinnacle: 0, kalshi: 0, novig: 0, players: 0 };
  const nowS = Date.now() / 1000, age = g => g ? nowS - Date.parse(g) / 1000 : Infinity;
  const pinAsof = feed?.vegas_meta?.props_pp_generated || feed?.generated;     // Pinnacle + PrizePicks / Underdog / Sleeper, pulled directly
  const pinStale = age(pinAsof) > FRESH_S, usStale = age(feed?.generated) > FRESH_US_S, kalStale = age(kalshi?.generated) > FRESH_S, novStale = age(novig?.generated) > FRESH_S;
  const feedStale = pinStale;   // kept for the legs / alt checks below: the reference those use is Pinnacle's
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
        venues.push({ src: 'Novig', kind: 'exchange', mid: nv.mid, spr: nv.spr, depth: nv.depth, age: nowS - nv.t,
          over: nv.oa != null ? { p: nv.oa, am: toAm(nv.oa), depth: nv.depth } : null, under: nv.ua != null ? { p: nv.ua, am: toAm(nv.ua), depth: nv.depth } : null });
        src.novig++;
      }
      const kl = (K[mkt]?.[nk] || []).find(r => r.k === ref);
      if (kl && kl.fair != null) {
        // Kalshi quotes Yes/No in cents. "Over k" is the Yes side of the "(k+0.5)+" contract; "Under" is buying No on it.
        // Older files carry only the midpoint and spread, so the bid / ask is rebuilt from those (same cents, to the cent).
        const h = Math.min(kl.spr ?? 0.04, 0.2) / 2;
        const ya = kl.ya ?? Math.min(0.99, kl.fair + h), yb = kl.yb ?? Math.max(0.01, kl.fair - h);
        const c = x => Math.round(x * 100);
        const contract = `${Math.ceil(kl.k)}+`;
        venues.push({ src: 'Kalshi', kind: 'exchange', mid: kl.fair, spr: kl.spr, oi: kl.oi, liquid: kl.spr <= KAL_SPR && kl.oi >= KAL_OI,
          over: { p: Math.min(0.99, ya), am: toAm(Math.min(0.99, ya)), oi: kl.oi, cents: c(ya), bidc: c(yb), contract, side: 'Yes' },
          under: { p: Math.min(0.99, 1 - yb), am: toAm(Math.min(0.99, 1 - yb)), oi: kl.oi, cents: c(1 - yb), bidc: c(1 - ya), contract, side: 'No' } });
        src.kalshi++;
      }
      let fair = null, fairSrc = null;
      if (pin) { fair = powFair(impl(pin.over), impl(pin.under)); fairSrc = 'Pinnacle'; src.pinnacle++; }
      else { const kv = venues.find(v => v.src === 'Kalshi' && v.liquid); if (kv) { fair = kv.mid; fairSrc = 'Kalshi'; } }

      // Has the market moved on without our reference? A deep, tight exchange far from the fair price at the same number is pricing
      // a line move the (hourly) book snapshot has not caught: the "edge" is the reference being out of date, not the exchange being cheap.
      // This is how a stale 31.5 turned into a +11% play when the line had already gone to 34.5.
      let moved = null;
      if (fair != null && fairSrc === 'Pinnacle') for (const v of venues) {
        if (v.kind !== 'exchange' || v.mid == null || (v.spr ?? 1) > TIGHT_SPR) continue;
        if (v.src === 'Novig' ? (v.depth ?? 0) < MIN_DEPTH : !v.liquid) continue;
        const d = v.mid - fair;
        if (Math.abs(d) >= MOVED_GAP && (!moved || Math.abs(d) > Math.abs(moved.d))) moved = { src: v.src, mid: +v.mid.toFixed(3), d: +d.toFixed(3), toward: d > 0 ? 'over' : 'under' };
      }
      // Pick'em legs: a PrizePicks / Underdog / Sleeper line has no price, so its value is the win chance of the better side.
      if (fair != null && !moved && !(fairSrc === 'Pinnacle' && pinStale)) {
        const seen = new Set();
        for (const q of qs) {
          if (!PICKEM.has(q.book) || seen.has(q.book)) continue; seen.add(q.book);
          const po = shiftFair(shift, mkt, fair, ref, q.line); if (po == null) continue;
          const side = po >= 0.5 ? 'over' : 'under', pw = side === 'over' ? po : 1 - po;
          if (pw < 0.54) continue;
          legs.push({ pid, name: p.name, team: p.team, pos: p.pos, mkt, label: LABEL[mkt], book: q.book, line: q.line, side, p: +pw.toFixed(4), refLine: ref, shifted: q.line !== ref, fairSrc });
        }
      }
      // Moved-line plays: a book or exchange strike at a DIFFERENT number than the fair line, priced by converting the fair price to it.
      let alt = null;
      if (fair != null && !moved) {
        const cand = [];
        for (const q of qs) if (q.line !== ref && q.over != null && q.under != null && !PICKEM.has(q.book) && q.book !== 'Pinnacle') cand.push({ src: q.book, kind: 'book', line: q.line, po: impl(q.over), pu: impl(q.under), ao: q.over, au: q.under });
        for (const r of NV[mkt]?.[nk] || []) if (r.k !== ref && (r.depth ?? 0) >= MIN_DEPTH) cand.push({ src: 'Novig', kind: 'exchange', line: r.k, po: r.oa, pu: r.ua, ao: r.oa != null ? toAm(r.oa) : null, au: r.ua != null ? toAm(r.ua) : null, depth: r.depth });
        for (const c of cand) {
          const fo = shiftFair(shift, mkt, fair, ref, c.line); if (fo == null) continue;
          for (const [side, pp, am, pf] of [['over', c.po, c.ao, fo], ['under', c.pu, c.au, 1 - fo]]) {
            if (pp == null || pp <= 0 || pp >= 1) continue;
            const ev = pf / pp - 1;
            if (ev >= SHIFT_MIN_EV && (!alt || ev > alt.ev)) alt = { side, src: c.src, kind: c.kind, line: c.line, am, p: +pp.toFixed(4), ev: +ev.toFixed(4), evAdj: +(realisticEv(ev) * 0.8).toFixed(4), depth: c.depth ?? null, shifted: true, refLine: ref, fairAtLine: +pf.toFixed(4) };
          }
        }
        if (alt) {
          const why = ['a different line than Pinnacle, so the price is converted'];
          if (pinStale) why.push("Pinnacle's line is old");
          if (usStale && alt.kind === 'book') why.push('book prices are old');
          if (novStale && alt.src === 'Novig') why.push('Novig price is old');
          alt.check = why; alt.stale = pinStale || (usStale && alt.kind === 'book') || (novStale && alt.src === 'Novig'); alt.big = alt.ev >= BIG_EV; alt.stake = stakePct(alt.evAdj, alt.p);
        }
      }
      if (venues.length < 2 && !alt) continue;   // nothing to compare

      // per side: every venue's price, EV vs fair, and the spread of prices between venues
      const sides = {};
      for (const side of ['over', 'under']) {
        const pf = fair == null ? null : side === 'over' ? fair : 1 - fair;
        const vs = venues.filter(v => v[side]?.p != null).map(v => {
          const x = v[side];
          const thin = v.kind === 'exchange' && ((v.src === 'Novig' && (x.depth ?? 0) < MIN_DEPTH) || (v.src === 'Kalshi' && !v.liquid));
          return { src: v.src, kind: v.kind, age: v.age ?? null, spr: v.spr ?? null, p: +x.p.toFixed(4), am: x.am, ev: pf == null || v.src === fairSrc ? null : +(pf / x.p - 1).toFixed(4), depth: x.depth ?? null, oi: x.oi ?? null, cents: x.cents ?? null, bidc: x.bidc ?? null, contract: x.contract ?? null, kside: x.side ?? null, thin };
        });
        const takeable = vs.filter(v => !v.thin);
        const best = takeable.length ? takeable.reduce((a, b) => a.p <= b.p ? a : b) : null;
        const worst = takeable.length > 1 ? takeable.reduce((a, b) => a.p >= b.p ? a : b) : null;
        sides[side] = { fair: pf == null ? null : +pf.toFixed(4), venues: vs, best, gap: best && worst ? +(worst.p - best.p).toFixed(4) : 0, gapFrom: worst?.src || null };
      }
      // the headline call: the side + venue with the most EV that is takeable and not the fair source itself
      let call = null;
      if (!moved) for (const side of ['over', 'under']) for (const v of sides[side].venues) {
        if (v.thin || v.ev == null || v.ev < MIN_EV || v.src === fairSrc) continue;
        if (!call || v.ev > call.ev) call = { side, src: v.src, kind: v.kind, am: v.am, p: v.p, ev: v.ev, depth: v.depth, age: v.age ?? null, cents: v.cents ?? null };
      }
      if (call) {
        // verify flags: say WHY a call should be checked before it is bet
        const why = [];
        if (pinStale && (fairSrc === 'Pinnacle' || OWNED.has(call.src))) why.push(fairSrc === 'Pinnacle' ? "Pinnacle's line is old" : 'book prices are old');
        if (usStale && call.kind === 'book' && !OWNED.has(call.src)) why.push(`${call.src} prices are old`);
        if (kalStale && (fairSrc === 'Kalshi' || call.src === 'Kalshi')) why.push('Kalshi prices are old');
        if (call.src === 'Novig' && (novStale || (call.age ?? 0) > FRESH_S)) why.push('Novig price is old');
        if (call.ev >= BIG_EV) why.push('edge this big is usually a moved line');
        call.check = why;
        call.stale = why.some(w => /\bold\b/.test(w) && !/^edge/.test(w));   // an edge against an old price: never tracked
        call.big = call.ev >= BIG_EV;
        call.evAdj = +realisticEv(call.ev).toFixed(4);
        call.stake = stakePct(call.evAdj, call.p);
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
      if (!call && !diff && !alt && !moved) continue;
      if (moved) src.moved = (src.moved || 0) + 1;
      src.players++;
      rows.push({
        pid, name: p.name, team: p.team, pos: p.pos, mkt, label: LABEL[mkt], line: ref,
        fair: fair == null ? null : +fair.toFixed(4), fairSrc,
        over: sides.over, under: sides.under, call, diff, alt, moved,
      });
    }
  }
  const top = r => Math.max(r.call?.evAdj ?? -1, r.alt?.evAdj ?? -1);
  rows.sort((a, b) => top(b) - top(a) || Math.abs(b.diff?.d ?? 0) - Math.abs(a.diff?.d ?? 0));
  legs.sort((a, b) => b.p - a.p);
  return { asof: Math.floor(Date.now() / 1000), sources: { ...src, stale: { pinnacle: pinStale, books: usStale, kalshi: kalStale, novig: novStale }, fresh: { pinnacle: FRESH_S, books: FRESH_US_S, kalshi: FRESH_S, novig: FRESH_S }, pinnacleAsof: pinAsof || null, novigAsof: novig?.generated || null, kalshiAsof: kalshi?.generated || null, feedAsof: feed?.generated || null }, season: feed?.season ?? null, week: feed?.week ?? null, rows: rows.slice(0, 500), legs: legs.slice(0, 400) };
}
