/* ════════════════════════════════════════════════════════════════════════
   VAULT · PROP QUOTE GUARD  (shared by src-vegas, fetch-pickem-props and
   snapshot-prop-history)

   A prop cell is { line, over, under, book, quotes:[{book,line,over,under}],
   best }. Two ways it used to bank a price that was never quoted at its line:

     1. The headline pair was assembled across lines. consensusCell() took the
        MODAL line but the line-first BEST over (lowest line) and BEST under
        (highest line), and upsertQuote() moved cell.line to a pick'em book's
        fresh number while keeping the old prices when that book sent none
        (PrizePicks never does). So a 0.5 line could carry 1.5 / 2.5 prices.
     2. A book's own quote was wrong for the market. Weeks 1-2 of 2026 carried
        frozen Underdog "0.5 pass TDs" quotes at +261 / -345 on starting QBs
        (Cousins, Lamar, Murray, Stroud) next to Sleeper's 1.5 at +122 / -213:
        a lower line priced LESS likely to go over than a higher one, which is
        impossible. Those overs hit 75%+ while the de-vigged pair said ~30%.

   repairCell() fixes both: it drops quotes that contradict the rest of the
   cell (guards below), then rebuilds the headline so cell.over / cell.under
   are only ever prices quoted at exactly cell.line.

   Guards, each a pairwise conflict between two two-way-priced quotes:
     · SAME LINE, OPPOSITE VERDICT: two books at one line whose no-vig P(over)
       differ by more than SAME_LINE_GAP. With 3+ books the outlier loses on
       conflict count; with 2 there's no majority, so both go.
     · MONOTONIC: across lines, P(over L) must be >= P(over L') when L < L'.
     · COUNT SHAPE (counting stats only, small lines): given one line's P(over)
       a Poisson count implies the other's; a lower line priced far BELOW that
       (or a higher line far above it) is not the same market. Poisson is wider
       than receptions and about right for TDs, so this only fires on gaps a
       real distribution can't produce (Burrow 0.5 at 39% vs 2.5 at 36%).
   Conflicts are resolved greedily: the quote in the most conflicts goes first;
   a tie drops the quote further from the cell's median line (alt / period
   lines are what leak), and a tie on that drops every tied quote.
   ════════════════════════════════════════════════════════════════════════ */

export const COUNT_MARKETS = new Set([
  'pass_td', 'pass_int', 'rec', 'rec_td', 'rush_td', 'rush_rec_td',
  'pass_cmp', 'pass_att', 'rush_att', 'rec_tgt', 'sacks', 'tackles', 'fg_made', 'kick_pts',
]);
const SAME_LINE_GAP = 0.25;   // no-vig P(over) gap two books at one line can't both be right about
const MONO_TOL = 0.03;        // rounding / hold slack on the monotonic check
const SHAPE_TOL = 0.25;       // Poisson-shape slack (wide: shape, not calibration)
const SHAPE_MAX_LINE = 10;    // Poisson shape only on small counting lines
const SHAPE_MAX_GAP = 2;      // ...a line or two apart (far alts stretch the Poisson too thin)
const SHAPE_P = [0.08, 0.92]; // ...and off the rails: a -1500 over pins lambda anywhere
const HOLD_LO = 1.005, HOLD_HI = 1.16;   // sane two-way overround (pick'em apps run ~12.5%)

export const amProb = a => (a == null || !Number.isFinite(a) || a === 0) ? null : (a > 0 ? 100 / (a + 100) : -a / (-a + 100));

/** No-vig P(over) for a two-way pair, or null when the pair isn't a real market. */
export function pOverPair(over, under) {
  const po = amProb(over), pu = amProb(under);
  if (po == null || pu == null) return null;
  const s = po + pu;
  if (s < HOLD_LO || s > HOLD_HI) return null;
  return po / s;
}

// P(X > line) for a Poisson(lam) count
function poisOver(lam, line) {
  const k = Math.floor(line);           // X > line  <=>  X >= k+1
  let term = Math.exp(-lam), cdf = term;
  for (let i = 1; i <= k; i++) { term *= lam / i; cdf += term; }
  return Math.max(0, Math.min(1, 1 - cdf));
}
const lamMemo = new Map();
function poisLambda(p, line) {          // lam with P(X > line) = p (monotone in lam)
  const key = line + '|' + p.toFixed(5);
  if (lamMemo.has(key)) return lamMemo.get(key);
  const lam = poisLambdaRaw(p, line);
  if (lamMemo.size < 200000) lamMemo.set(key, lam);
  return lam;
}
function poisLambdaRaw(p, line) {
  let lo = 1e-4, hi = 60;
  for (let i = 0; i < 60; i++) { const m = (lo + hi) / 2; if (poisOver(m, line) < p) lo = m; else hi = m; }
  return (lo + hi) / 2;
}

const IN_CELL = { mono: MONO_TOL, shape: SHAPE_TOL, shapeMaxLo: Infinity };
// Across snapshots the market can genuinely move (news, steam, a role change:
// 4.5 rush attempts on Tuesday, 6.5 on Saturday) between two reads on
// different lines, so only a gross gap counts there, and the count-shape check
// only covers the 0.5 / 1.5 zone where the leaked alt / period lines live.
const CROSS_TIME = { mono: 0.12, shape: SHAPE_TOL, shapeMaxLo: 1.5 };

function conflicts(a, b, count, tol = IN_CELL) {
  if (a.line === b.line) return Math.abs(a.p - b.p) > SAME_LINE_GAP;
  const [lo, hi] = a.line < b.line ? [a, b] : [b, a];
  if (lo.p < hi.p - tol.mono) return true;
  const inP = p => p >= SHAPE_P[0] && p <= SHAPE_P[1];
  if (count && lo.line <= tol.shapeMaxLo && hi.line <= SHAPE_MAX_LINE && hi.line - lo.line <= SHAPE_MAX_GAP && inP(lo.p) && inP(hi.p)) {
    const fromHi = poisOver(poisLambda(hi.p, hi.line), lo.line);   // what the higher line implies for the lower
    const fromLo = poisOver(poisLambda(lo.p, lo.line), hi.line);   // and vice versa
    if (lo.p < fromHi - tol.shape || hi.p > fromLo + tol.shape) return true;
  }
  return false;
}

// Greedy resolution shared by both guards: drop the node in the most
// conflicts; a tie drops the node further from the median line, and a tie on
// that drops every tied node.
function resolve(nodes, edges, med) {
  const out = new Set();
  let live = edges;
  while (live.length) {
    const deg = new Map();
    for (const [a, b] of live) { deg.set(a, (deg.get(a) || 0) + 1); deg.set(b, (deg.get(b) || 0) + 1); }
    const top = Math.max(...deg.values());
    let cand = [...deg.keys()].filter(i => deg.get(i) === top);
    if (cand.length > 1 && med != null) {
      const dist = i => Math.abs(nodes.get(i) - med);
      const far = Math.max(...cand.map(dist));
      cand = cand.filter(i => dist(i) === far);
    }
    for (const i of cand) out.add(i);
    live = live.filter(([a, b]) => !out.has(a) && !out.has(b));
  }
  return out;
}
const medianOf = xs => { const a = xs.slice().sort((x, y) => x - y); return a.length ? a[Math.floor((a.length - 1) / 2)] : null; };

/** Indices of quotes the guards reject. Only two-way-priced quotes with a line
 *  take part; priceless pick'em lines only vote on the median line. */
export function rejectedQuotes(quotes, market) {
  const qs = quotes || [];
  const count = COUNT_MARKETS.has(market);
  const nodes = [];
  qs.forEach((q, i) => {
    if (!q || q.line == null) return;
    const p = pOverPair(q.over, q.under);
    if (p != null) nodes.push({ i, line: Number(q.line), p });
  });
  const med = medianOf(qs.filter(q => q && q.line != null).map(q => Number(q.line)));
  const edges = [];
  for (let x = 0; x < nodes.length; x++)
    for (let y = x + 1; y < nodes.length; y++)
      if (conflicts(nodes[x], nodes[y], count)) edges.push([nodes[x].i, nodes[y].i]);
  return resolve(new Map(nodes.map(n => [n.i, n.line])), edges, med);
}

function modal(vals) {
  const f = new Map();
  for (const v of vals) f.set(v, (f.get(v) || 0) + 1);
  let best = null, n = -1;
  for (const [v, c] of f) if (c > n || (c === n && v < best)) { best = v; n = c; }
  return best;
}

/* line-first best price for a side (same rule as src-vegas bestSide): a lower
   line is strictly better for an OVER, a higher line for an UNDER; price only
   breaks a tie. Kept here so every caller ranks the SAME clean quote list. */
export function bestSide(quotes, side) {
  const better = side === 'over' ? (a, b) => a < b : (a, b) => a > b;
  return (quotes || []).reduce((best, q) => {
    if (!q || q[side] == null) return best;
    const cand = { book: q.book, price: q[side], line: q.line ?? null };
    if (!best) return cand;
    if (cand.line != null && best.line != null && cand.line !== best.line)
      return better(cand.line, best.line) ? cand : best;
    return cand.price > best.price ? cand : best;
  }, null);
}

/** Best over / under price quoted at exactly `line` (null when none). */
export function pricesAtLine(quotes, line) {
  let over = null, under = null, overBook = null;
  for (const q of quotes || []) {
    if (!q || q.line == null || line == null || Number(q.line) !== Number(line)) continue;
    if (q.over != null && (over == null || q.over > over)) { over = q.over; overBook = q.book; }
    if (q.under != null && (under == null || q.under > under)) under = q.under;
  }
  return { over, under, book: overBook };
}

/** Drop contradictory quotes, then rebuild line / over / under / best so the
 *  headline only carries prices quoted at its own line. Mutates and returns
 *  the number of quotes dropped. Prob-kind cells (anytime TD, no line) and
 *  quote-less cells are left alone. */
export function repairCell(cell, market) {
  if (!cell || !Array.isArray(cell.quotes) || !cell.quotes.length) return 0;
  if (market === 'anytime_td' || (cell.line == null && cell.prob != null)) return 0;
  const bad = rejectedQuotes(cell.quotes, market);
  if (bad.size) cell.quotes = cell.quotes.filter((_, i) => !bad.has(i));
  const qs = cell.quotes;
  if (!qs.length) { cell.over = cell.under = null; cell.best = { over: null, under: null }; return bad.size; }
  // the headline line must still be quoted by someone; else move to the modal
  // line of the surviving quotes (priced quotes first)
  const onLine = l => qs.some(q => q.line != null && Number(q.line) === Number(l));
  if (cell.line == null || !onLine(cell.line)) {
    const priced = qs.filter(q => q.line != null && (q.over != null || q.under != null)).map(q => Number(q.line));
    const any = qs.filter(q => q.line != null).map(q => Number(q.line));
    const l = modal(priced.length ? priced : any);
    if (l != null) cell.line = l;
  }
  const at = pricesAtLine(qs, cell.line);
  cell.over = at.over; cell.under = at.under;
  if (!qs.some(q => q.book === cell.book && Number(q.line) === Number(cell.line)))
    cell.book = at.book || (qs.find(q => Number(q.line) === Number(cell.line)) || {}).book || cell.book;
  cell.best = { over: bestSide(qs, 'over'), under: bestSide(qs, 'under') };
  return bad.size;
}

/** Cross-snapshot guard. When every other book has pulled a market (after
 *  kickoff, typically) a stale lone quote has nothing left in its cell to
 *  disagree with, but the same week's OTHER snapshots of that player+market
 *  still do (Kmet: 1.5 rec at -115 all week, then 0.5 at +149 on Monday).
 *  `samples` = [{line, over, under}, …]; returns the indices to drop, by the
 *  same greedy majority as the in-cell guard but with CROSS_TIME tolerance.
 *  Snapshots on the same line are a price move over time, never a conflict. */
export function rejectedSamples(samples, market) {
  const count = COUNT_MARKETS.has(market);
  const nodes = [];
  (samples || []).forEach((s, i) => {
    if (!s || s.line == null) return;
    const p = pOverPair(s.over, s.under);
    if (p != null) nodes.push({ i, line: Number(s.line), p });
  });
  const edges = [];
  for (let x = 0; x < nodes.length; x++)
    for (let y = x + 1; y < nodes.length; y++)
      if (nodes[x].line !== nodes[y].line && conflicts(nodes[x], nodes[y], count, CROSS_TIME)) edges.push([nodes[x].i, nodes[y].i]);
  return resolve(new Map(nodes.map(n => [n.i, n.line])), edges, medianOf(nodes.map(n => n.line)));
}

/** How many of `prior` snapshots (other lines only) the new pair contradicts,
 *  out of how many it could be compared with. The hourly snapshot skips a pair
 *  that contradicts most of them. */
export function crossSampleVotes(prior, next, market) {
  const pn = pOverPair(next && next.over, next && next.under);
  if (pn == null || next.line == null) return { against: 0, of: 0 };
  const count = COUNT_MARKETS.has(market), a = { line: Number(next.line), p: pn };
  let against = 0, of = 0;
  for (const s of prior || []) {
    if (!s || s.line == null || Number(s.line) === a.line) continue;
    const p = pOverPair(s.over, s.under); if (p == null) continue;
    of++;
    if (conflicts(a, { line: Number(s.line), p }, count, CROSS_TIME)) against++;
  }
  return { against, of };
}
