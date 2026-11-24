/* Sharps V2 Record view. One shared component mounted inside both the Sharps tab (switch: Plays | Record) and the Sharp Accounts tab
   (switch: Accounts | Record). Three sections: plays record, tier record, accounts record. A sport selector follows the host header.
   Sharp money is context only: nothing here is a bet signal, a size rule, or an input to Top Reads, SM_GATE or any total. A record is
   never proof. Every number is a stored field or arithmetic on stored fields; a missing field is omitted. All times Central.
   Sources: pm_record/cards_record.json and pm_record/cards/<sport>/<YYYY-MM>.jsonl on pm-holders-data (docs/side-card-record.md),
   and wallets.json (store.wallets). Loads in node for the pure-function tests: nothing touches the DOM until init() runs. */
(function () {
  'use strict';
  var root = typeof window !== 'undefined' ? window : globalThis;
  var SV2 = root.SV2 || (typeof module !== 'undefined' && module.exports ? module.exports : null);
  if (!SV2) return;
  var isNum = SV2.isNum, esc = SV2.esc, fmt = SV2.fmt, ct = SV2.ct, copy = SV2.copy, rules = SV2.rules, ui = SV2.ui, seg = SV2.seg, store = SV2.store;
  var sportName = SV2.sportName;

  /* 2026-11-16 12:00 AM Central (REGISTERED_T in scripts/sf_shadows.py): a card cut before it is in-sample, the rest is forward */
  var FWD_CUT = 1794808800;
  var FIRST_MONTH = '2026-11';   /* cards are graded from 2026-11-12: no earlier month file exists */
  var NEED_N = 300;          /* docs/sharps-audit-2026-11-18.md: under 300 plays per sport one standard error is 5.8+ points, no edge can be read */
  var SMALL_N = 30;          /* any record under n = 30 carries "small sample" (same as the Following page) */
  var SHOWN = ['nba', 'nfl', 'cbb'];   /* flat 1u, untested rule */
  var SPORT_ORDER = ['nba', 'nfl', 'cbb', 'cfb'];
  var MARKETS = [['ml', 'Moneyline'], ['spread', 'Spread'], ['total', 'Total']];
  var BASE = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-holders-data/pm_record/';
  var TIER_NONE = 'Tier record: not logged yet. It starts at the next lock.';
  var rec = {};

  /* ------------------------------------------------------------------ pure functions (unit tested) */
  function lc(s) { return String(s == null ? '' : s).toLowerCase(); }

  /* JSONL text to rows, malformed lines dropped, one row per key (the last one wins; the files are append-only) */
  rec.parseJsonl = function (text) {
    var by = {}, out = [];
    String(text || '').split('\n').forEach(function (line) {
      line = line.trim(); if (!line) return;
      var r; try { r = JSON.parse(line); } catch (e) { return; }
      if (!r || typeof r !== 'object' || Array.isArray(r)) return;
      if (typeof r.key === 'string') { if (r.key in by) out[by[r.key]] = r; else { by[r.key] = out.length; out.push(r); } } else out.push(r);
    });
    return out;
  };
  /* { result key: close row } from the close rows ("of" is the result row's key) */
  rec.closeMap = function (rows) {
    var m = {};
    (rows || []).forEach(function (r) { if (r && r.kind === 'close' && typeof r.of === 'string' && isNum(r.clv)) m[r.of] = r; });
    return m;
  };
  /* the rows of the shown play (sf, variant all) from counted cards, in one sport or in the three shown sports ('all') */
  rec.playRows = function (rows, sport) {
    var s = sport == null ? 'all' : lc(sport);
    return (rows || []).filter(function (r) {
      if (!r || r.kind !== 'result' || r.play !== 'sf' || r.variant !== 'all' || r.counts !== true) return false;
      var sp = lc(r.sport);
      return s === 'all' ? SHOWN.indexOf(sp) >= 0 : sp === s;
    });
  };
  /* forward: the card was cut at or after the registered time. in_sample: before it. A row with no cut time is in neither. */
  rec.splitForward = function (rows, cut) {
    var c = isNum(cut) ? cut : FWD_CUT, f = [], p = [], u = [];
    (rows || []).forEach(function (r) { if (!isNum(r.cut)) u.push(r); else if (r.cut >= c) f.push(r); else p.push(r); });
    return { forward: f, in_sample: p, undated: u };
  };
  /* The record of a set of result rows at a flat 1u: only graded rows with a stored flat result count; unpriced rows are listed apart.
     units = sum of stored flat results, roi = units / n, se = standard error of roi (sample sd of the flat results over sqrt(n)). */
  rec.tally = function (rows, closes) {
    var w = 0, l = 0, p = 0, n = 0, sum = 0, unpriced = 0, flats = [], clv = [];
    closes = closes || {};
    (rows || []).forEach(function (r) {
      if (!r) return;
      if (r.status === 'unpriced') { unpriced++; return; }
      if (r.status !== 'graded' || !isNum(r.flat)) return;
      n++; sum += r.flat; flats.push(r.flat);
      if (r.res === 'win') w++; else if (r.res === 'loss') l++; else if (r.res === 'push') p++;
      var c = closes[r.key]; if (c && isNum(c.clv)) clv.push(c.clv);
    });
    var roi = n ? sum / n : null, se = null;
    if (n > 1) { var v = 0; flats.forEach(function (x) { v += (x - roi) * (x - roi); }); se = Math.sqrt(v / (n - 1) / n); }
    var cm = 0; clv.forEach(function (x) { cm += x; });
    return { n: n, w: w, l: l, p: p, units: Math.round(sum * 1000) / 1000, roi: roi, se: se, unpriced: unpriced,
             clv_n: clv.length, clv_mean: clv.length ? cm / clv.length : null };
  };
  /* sum of tallies (used for a file's published tier lines across sports); clv is weighted by clv_n */
  rec.sumTallies = function (list) {
    var o = { n: 0, w: 0, l: 0, p: 0, units: 0, roi: null, se: null, unpriced: 0, clv_n: 0, clv_mean: null }, cs = 0;
    (list || []).forEach(function (t) {
      if (!t) return;
      o.n += t.n || 0; o.w += t.w || 0; o.l += t.l || 0; o.p += t.p || 0; o.units += isNum(t.units) ? t.units : 0; o.unpriced += t.unpriced || 0;
      if (isNum(t.clv_mean) && t.clv_n > 0) { cs += t.clv_mean * t.clv_n; o.clv_n += t.clv_n; }
    });
    o.units = Math.round(o.units * 1000) / 1000;
    o.roi = o.n ? o.units / o.n : null; o.clv_mean = o.clv_n ? cs / o.clv_n : null;
    return o;
  };
  /* Flag for close monitoring: a slice that is improving (units above zero) is watched, and it says how small it is.
     small: under 300 (no edge can be read); tiny: under 30. A slice that is not improving only carries the tiny flag. */
  rec.monitor = function (t) {
    if (!t || !isNum(t.n) || t.n <= 0) return { watch: false, small: false, tiny: false, n: t && t.n || 0 };
    var up = isNum(t.units) ? t.units > 0 : (isNum(t.roi) && t.roi > 0);
    return { watch: !!up, small: t.n < NEED_N, tiny: t.n < SMALL_N, n: t.n };
  };
  /* plain-English note on what the sample size can say */
  rec.seNote = function (t) {
    if (!t || !isNum(t.se) || t.n < 2) return null;
    var pts = (t.se * 100).toFixed(1);
    var s = 'At n=' + t.n + ', one standard error on ROI is about ' + pts + ' points, so this record cannot tell an edge from luck.';
    if (t.n < NEED_N) s += ' Under ' + NEED_N + ' plays no edge can be read.';
    return s;
  };
  rec.latest = function (rows, n) {
    return (rows || []).filter(function (r) { return r && r.status === 'graded'; })
      .sort(function (a, b) { return (b.graded_at || 0) - (a.graded_at || 0) || (a.key < b.key ? -1 : 1); }).slice(0, n || 12);
  };
  /* "76ers ML", "Mavericks -2.5", "Over 224.5". The stored line belongs to the first outcome: the second one takes its negative. */
  rec.playLabel = function (r) {
    var side = r.side || '';
    if (r.group === 'total') return side + (isNum(r.line) ? ' ' + fmt.line(r.line) : '');
    if (r.group === 'spread' && isNum(r.line)) {
      var o = r.outs, ln = o && o.length === 2 && o[1] === side ? -r.line : r.line;
      return side + ' ' + fmt.line(ln, { signed: true });
    }
    return side + (r.group === 'ml' ? ' ML' : '');
  };
  /* Tier record. Reads a tier field from the rows when present (tier, evidence_tier, or v2.tier), else a published tier_record object
     in the file ({ clear: {...}, ... } or { sports: { nba: { clear: {...} } } } or { tiers: ... }). Never computes a tier. null when
     neither exists: the caller says "not logged yet". */
  function tierOfRow(r) {
    var t = lc(r.tier || r.evidence_tier || (r.v2 && r.v2.tier));
    return copy.tier[t] ? t : null;
  }
  function fileTally(o) {
    if (!o || typeof o !== 'object') return null;
    var n = isNum(o.n) ? o.n : null; if (n == null) return null;
    var roi = isNum(o.flat_roi) ? o.flat_roi : (isNum(o.roi) ? o.roi : null);
    var units = isNum(o.units) ? o.units : (isNum(o.flat_units) ? o.flat_units : (roi != null ? Math.round(roi * n * 1000) / 1000 : null));
    return { n: n, w: o.w || 0, l: o.l || 0, p: o.p || 0, units: units, roi: roi, se: null, unpriced: 0, clv_n: o.clv_n || 0, clv_mean: isNum(o.clv_mean) ? o.clv_mean : null };
  }
  rec.tierRecord = function (rows, file, sport, closes) {
    var s = sport == null ? 'all' : lc(sport);
    var tiered = (rows || []).filter(function (r) { return tierOfRow(r); });
    if (tiered.length) {
      var scoped = rec.playRows(tiered, s), by = {};
      copy.tierOrder.forEach(function (t) { by[t] = rec.tally(scoped.filter(function (r) { return tierOfRow(r) === t; }), closes); });
      return { source: 'rows', byTier: by };
    }
    var tr = file && file.tier_record;
    if (tr && typeof tr === 'object') {
      var body = tr.sports || tr.tiers || tr, out = {}, any = false;
      copy.tierOrder.forEach(function (t) {
        var parts = [];
        if (body.nba || body.nfl || body.cbb || body.cfb) {
          SPORT_ORDER.forEach(function (sp) { if ((s === 'all' ? SHOWN.indexOf(sp) >= 0 : sp === s) && body[sp] && body[sp][t]) parts.push(fileTally(body[sp][t])); });
        } else if (body[t]) parts.push(fileTally(body[t]));
        parts = parts.filter(Boolean);
        out[t] = parts.length ? rec.sumTallies(parts) : null; if (out[t]) any = true;
      });
      if (any) return { source: 'file', byTier: out };
    }
    return null;
  };

  /* ---- Tier record table, from tier_record.json (docs/side-cards.md). Context only: a record, not a signal.
     in_sample: the tier rule was written after those results. forward: only plays whose tier was logged at lock (zeros until the first
     logged lock is graded). since_nov16: informational, tier still derived after the fact. none: not derivable, kept apart, never in a tier. */
  var TIER_ROWS = ['clear', 'mixed', 'thin', 'contested', 'none'];
  var BUCKETS = ['all', 'in_sample', 'forward', 'since_nov16'];
  var BUCKET_NAME = { all: 'All plays', in_sample: 'In-sample', forward: 'Forward', since_nov16: 'Since Nov 16' };
  var TIER_FOOT = 'In-sample: the tier rule was written after these results. Forward counts start at the first logged lock.';
  /* cells: zero plays read 0-0 and 0u, and a null roi is a dash, never "0%" */
  rec.fmtWl = function (t) { return t && t.n ? (fmt.wl(t.w, t.l, t.p) || '0-0') : '0-0'; };
  rec.fmtUnits = function (t) { return t && isNum(t.units) && t.n ? fmt.units(t.units, { signed: true }) : '0u'; };
  rec.fmtRoi = function (t) { return t && isNum(t.roi) && t.n ? fmt.pct(t.roi, { signed: true }) : '-'; };
  function zeroTally() { return { w: 0, l: 0, p: 0, n: 0, units: 0, roi: null }; }
  /* one stored {w,l,p,n,units,roi} as a tally. Missing or malformed is zeros. roi is null unless n > 0 and the stored roi is a number. */
  rec.tierTally = function (o) {
    if (!o || typeof o !== 'object' || !isNum(o.n) || o.n < 0) return zeroTally();
    var n = o.n, units = isNum(o.units) ? o.units : 0;
    return { w: isNum(o.w) ? o.w : 0, l: isNum(o.l) ? o.l : 0, p: isNum(o.p) ? o.p : 0, n: n, units: units, roi: n > 0 && isNum(o.roi) ? o.roi : (n > 0 ? units / n : null) };
  };
  /* the file is usable when it has a tier object for the pooled set or any sport */
  rec.tierFileOk = function (f) {
    return !!(f && typeof f === 'object' && ((f.all && f.all.tiers) || (f.sports && typeof f.sports === 'object')));
  };
  /* the tiers object for a sport: 'all' is the file's pooled NBA+NFL+CBB set (CFB is never pooled); when the file lacks it, the three sports are summed here.
     null when the sport is not in the file. */
  rec.tierSlice = function (f, sport) {
    if (!rec.tierFileOk(f)) return null;
    var s = sport == null ? 'all' : lc(sport);
    if (s !== 'all') return f.sports && f.sports[s] && f.sports[s].tiers ? f.sports[s].tiers : null;
    if (f.all && f.all.tiers) return f.all.tiers;
    var out = {}, any = false;
    TIER_ROWS.forEach(function (t) {
      var o = { by_market: {} };
      BUCKETS.forEach(function (b) { o[b] = rec.tierPool(SHOWN.map(function (sp) { var x = f.sports && f.sports[sp] && f.sports[sp].tiers && f.sports[sp].tiers[t]; return x && x[b]; })); });
      MARKETS.forEach(function (m) { o.by_market[m[0]] = rec.tierPool(SHOWN.map(function (sp) { var x = f.sports && f.sports[sp] && f.sports[sp].tiers && f.sports[sp].tiers[t]; return x && x.by_market && x.by_market[m[0]]; })); });
      if (o.all.n) any = true;
      out[t] = o;
    });
    return any ? out : null;
  };
  /* pool stored tallies: counts and units add, roi is units / n, null at n 0 */
  rec.tierPool = function (list) {
    var o = zeroTally(), sh = [];
    (list || []).forEach(function (x) { var t = rec.tierTally(x); o.w += t.w; o.l += t.l; o.p += t.p; o.n += t.n; o.units += t.units; sh.push(rec.shadowTally(x)); });
    o.units = Math.round(o.units * 1000) / 1000;
    o.roi = o.n > 0 ? o.units / o.n : null;
    var sp = rec.shadowPool(sh); if (sp) o.shadow = { units_staked: sp.staked, units: sp.units, roi: sp.roi };
    return o;
  };
  /* ---- Shadow size v2s-1 (docs/sharp-tier-v2-prereg.md, Shadow size). A SHADOW: the same plays at the tier-scaled size beside the flat 1u, never shown
     on the page and never a recommendation. The sizes are an ordering by evidence, not fitted to results. In-sample. The Not derivable plays are not
     staked by the shadow, so the like-for-like comparison is the plays that have a tier. */
  var SHADOW_SIZE = { clear: 1.5, mixed: 1, thin: 0.5, contested: 0.5, none: null };
  var SHADOW_TIP = 'What the same plays would have returned at the tier-scaled size. In-sample, not shown on the page.';
  /* the size for a tier: null for Not derivable, 0 for CFB (no size is shown there), else the rule table */
  rec.shadowSize = function (tier, sport) {
    var t = lc(tier);
    if (!(t in SHADOW_SIZE) || SHADOW_SIZE[t] == null) return null;
    return lc(sport) === 'cfb' ? 0 : SHADOW_SIZE[t];
  };
  rec.fmtSize = function (x) { return isNum(x) && x > 0 ? String(x) + 'u' : 'none'; };
  /* one stored cell's shadow {units_staked, units, roi} as {staked, units, roi}; null when the cell has none (Not derivable, or no size applies).
     Nothing staked reads 0 units and a null roi, never 0%. */
  rec.shadowTally = function (o) {
    var s = o && typeof o === 'object' ? o.shadow : null;
    if (!s || typeof s !== 'object' || !isNum(s.units_staked) || s.units_staked < 0) return null;
    var st = s.units_staked, u = isNum(s.units) ? s.units : 0;
    return { staked: st, units: st > 0 ? u : 0, roi: st > 0 ? (isNum(s.roi) ? s.roi : u / st) : null };
  };
  /* pooled shadow: staked and units add, roi = units / staked. Null cells are skipped; null when every cell is null. */
  rec.shadowPool = function (list) {
    var st = 0, u = 0, any = false;
    (list || []).forEach(function (x) { if (x && isNum(x.staked)) { any = true; st += x.staked; u += isNum(x.units) ? x.units : 0; } });
    if (!any) return null;
    st = Math.round(st * 1000) / 1000; u = Math.round(u * 1000) / 1000;
    return { staked: st, units: u, roi: st > 0 ? u / st : null };
  };
  rec.fmtShadowUnits = function (sh) { return sh && sh.staked > 0 && isNum(sh.units) ? fmt.units(sh.units, { signed: true }) : '-'; };
  rec.fmtShadowRoi = function (sh) { return sh && sh.staked > 0 && isNum(sh.roi) ? fmt.pct(sh.roi, { signed: true }) : '-'; };
  rec.fmtStaked = function (sh) { return sh && sh.staked > 0 ? fmt.units(sh.staked) : '-'; };
  /* which bucket of a tier to read. Anything unknown reads as all. */
  rec.pickBucket = function (tierObj, bucket) {
    var b = BUCKETS.indexOf(bucket) >= 0 ? bucket : 'all';
    return rec.tierTally(tierObj && tierObj[b]);
  };
  /* the table for a sport and a bucket: five rows in order (four tiers, then Not derivable on its own row), each with its tally, its share of the
     bucket's n (null when the bucket is empty), the monitor flags, and the market split. The split is stored for all plays only: it is shown when
     the bucket holds exactly the same plays (same n as all), else null. Zero-play tiers stay in as zeros. */
  rec.tierTable = function (f, sport, bucket) {
    var sl = rec.tierSlice(f, sport);
    if (!sl) return null;
    var b = BUCKETS.indexOf(bucket) >= 0 ? bucket : 'all';
    var rows = TIER_ROWS.map(function (t) {
      var o = sl[t] || {}, tally = rec.pickBucket(o, b), all = rec.pickBucket(o, 'all'), markets = null;
      if (o.by_market && tally.n > 0 && tally.n === all.n) {
        markets = MARKETS.map(function (m) { return { k: m[0], label: m[1], t: rec.tierTally(o.by_market[m[0]]), shadow: rec.shadowTally(o.by_market[m[0]]) }; });
      }
      return { tier: t, derived: t !== 'none', t: tally, share: null, flag: rec.monitor(tally), markets: markets,
               size: rec.shadowSize(t, sport), shadow: rec.shadowTally(o[b]) };
    });
    var total = rec.tierPool(rows.map(function (r) { return r.t; }));
    rows.forEach(function (r) { r.share = total.n > 0 ? r.t.n / total.n : null; });
    var derived = rec.tierPool(rows.filter(function (r) { return r.derived; }).map(function (r) { return r.t; }));
    return { bucket: b, rows: rows, total: total, derived: derived, like: rec.likeForLike(rows) };
  };
  /* Shadow vs flat on the plays that have a tier only (Not derivable is excluded from both): flat units and n are summed from the tier rows,
     the shadow from the tier rows' shadow cells. Null when the shadow stakes nothing (CFB, an empty bucket): there is nothing to compare. */
  rec.likeForLike = function (rows) {
    var d = (rows || []).filter(function (r) { return r.derived; });
    var flat = rec.tierPool(d.map(function (r) { return r.t; })), sh = rec.shadowPool(d.map(function (r) { return r.shadow; }));
    if (!flat.n || !sh || !(sh.staked > 0)) return null;
    return { n: flat.n, flat_units: flat.units, flat_roi: flat.roi, staked: sh.staked, shadow_units: sh.units, shadow_roi: sh.roi };
  };
  rec.likeLine = function (l, bucket) {
    if (!l) return null;
    var tail = bucket === 'forward' ? 'Forward, inside the noise.' : bucket === 'since_nov16' ? 'Informational, tier derived after the fact, inside the noise.' : 'In-sample, inside the noise.';
    return 'Shadow vs flat, plays with a tier only: flat ' + fmt.units(l.flat_units, { signed: true }) + ' (n=' + fmt.n(l.n) + ') vs shadow ' +
      fmt.units(l.shadow_units, { signed: true }) + ' on ' + fmt.units(l.staked) + ' staked. Not derivable plays are not staked by the shadow. ' + tail;
  };
  /* "Record so far (in-sample): Contested 30-20": one entry per tier with plays, Not derivable last and named as such. */
  rec.railLine = function (f, sport) {
    var tb = rec.tierTable(f, sport, 'all');
    if (!tb || !tb.total.n) return null;
    var fw = rec.tierTable(f, sport, 'forward');   /* a forward n above zero means the lock log has started and graded plays */
    var items = tb.rows.filter(function (r) { return r.t.n > 0; }).map(function (r) {
      return { tier: r.tier, word: r.derived ? copy.tier[r.tier].word : 'Not derivable', wl: fmt.wl(r.t.w, r.t.l, r.t.p), n: r.t.n };
    });
    return { items: items, label: fw && fw.total.n > 0 ? 'Record so far (in-sample and forward)' : 'Record so far (in-sample)', total: tb.total.n };
  };

  /* Accounts: the wallets file by account tier. Forward = fwd {w,l,p,n,pnl,flat_roi,clv_n,clv_mean}, settled since the wallet was first tracked
     (published only when v2_fields names fwd). Past = w_ and l_, the record before it was picked: picked after the fact. */
  function declared(file, key) {
    var f = file && file.v2_fields; if (!f) return false;
    if (Array.isArray(f)) return f.indexOf(key) >= 0;
    return new RegExp('(^|[^A-Za-z0-9_.])' + String(key).replace(/\./g, '\\.') + '(?![A-Za-z0-9_])').test(String(f));
  }
  function emptyAgg() { return { accounts: 0, active: 0, w: 0, l: 0, p: 0, n: 0, units: 0, roi: null, pnl: 0, clv_n: 0, clv_mean: null, past: { w: 0, l: 0, n: 0, accounts: 0 }, _cs: 0 }; }
  function finishAgg(a) {
    a.units = Math.round(a.units * 1000) / 1000; a.pnl = Math.round(a.pnl);
    a.roi = a.n ? a.units / a.n : null; a.clv_mean = a.clv_n ? a._cs / a.clv_n : null; delete a._cs;
    return a;
  }
  rec.acctAgg = function (file, sport) {
    var s = sport == null ? 'all' : lc(sport), fwdPub = declared(file, 'fwd');
    var out = { fwdPub: fwdPub, tiers: {}, bySport: {}, total: emptyAgg() };
    copy.acctOrder.forEach(function (t) { out.tiers[t] = emptyAgg(); });
    var sports = file && file.sports || {};
    Object.keys(sports).forEach(function (sp) {
      if (s !== 'all' && sp !== s) return;
      if (!out.bySport[sp]) out.bySport[sp] = emptyAgg();
      var rows = sports[sp] || {};
      Object.keys(rows).forEach(function (w) {
        var r = rows[w]; if (!r || typeof r !== 'object' || Array.isArray(r)) return;
        var tier = rules.v2TierOf(r, sp), tg = out.tiers[tier] || (out.tiers[tier] = emptyAgg());
        [tg, out.bySport[sp], out.total].forEach(function (a) {
          a.accounts++;
          if (isNum(r.w_) && isNum(r.l_)) { a.past.w += r.w_; a.past.l += r.l_; a.past.n += r.w_ + r.l_; a.past.accounts++; }
          var f = fwdPub && r.fwd && typeof r.fwd === 'object' ? r.fwd : null;
          if (!f || !isNum(f.n) || f.n <= 0) return;
          a.active++; a.n += f.n; a.w += f.w || 0; a.l += f.l || 0; a.p += f.p || 0;
          if (isNum(f.flat_roi)) a.units += f.flat_roi * f.n; else a.skipped = (a.skipped || 0) + f.n;
          if (isNum(f.pnl)) a.pnl += f.pnl;
          if (isNum(f.clv_mean) && f.clv_n > 0) { a._cs += f.clv_mean * f.clv_n; a.clv_n += f.clv_n; }
        });
      });
    });
    Object.keys(out.tiers).forEach(function (k) { finishAgg(out.tiers[k]); });
    Object.keys(out.bySport).forEach(function (k) { finishAgg(out.bySport[k]); });
    finishAgg(out.total);
    return out;
  };
  /* an account aggregate seen as a tally, so the same monitor and row code reads it */
  rec.asTally = function (a) { return { n: a.n, w: a.w, l: a.l, p: a.p, units: a.units, roi: a.roi, se: null, unpriced: 0, clv_n: a.clv_n, clv_mean: a.clv_mean }; };

  /* ---- Table view-models and sorting (presentation only: no number is computed here that was not shown before).
     Every record table sorts by Units, ROI or n, or returns to its stored order (key def). A first click starts at the column's own direction. */
  var SORT_FIRST = { def: 1, units: -1, roi: -1, n: -1 };
  var SORT_NAME = { def: 'default order', units: 'Units', roi: 'ROI', n: 'n' };
  function hasSort(k) { return Object.prototype.hasOwnProperty.call(SORT_FIRST, k); }
  rec.cleanSort = function (o) {
    var k = o && hasSort(o.k) ? o.k : 'def';
    return { k: k, dir: o && (o.dir === 1 || o.dir === -1) ? o.dir : SORT_FIRST[k] };
  };
  /* a header click: the active column flips direction, another column starts at its own first direction, an unknown key changes nothing */
  rec.nextSort = function (cur, k) {
    var c = rec.cleanSort(cur);
    if (!hasSort(k)) return c;
    return c.k === k ? { k: k, dir: -c.dir } : { k: k, dir: SORT_FIRST[k] };
  };
  rec.sortWord = function (s) { var c = rec.cleanSort(s); return SORT_NAME[c.k] + ', ' + (c.dir === 1 ? 'ascending' : 'descending'); };
  /* a model is { idx, t } (idx = the stored order, t = a tally). A row with no plays has no units or ROI value. */
  rec.sortValue = function (m, k) {
    if (!m) return null;
    var t = m.t || {};
    if (k === 'def') return isNum(m.idx) ? m.idx : null;
    if (k === 'units') return t.n > 0 && isNum(t.units) ? t.units : null;
    if (k === 'roi') return t.n > 0 && isNum(t.roi) ? t.roi : null;
    if (k === 'n') return isNum(t.n) ? t.n : null;
    return null;
  };
  /* a missing value sorts last in either direction; ties keep the stored order */
  rec.sortRows = function (models, sort) {
    var s = rec.cleanSort(sort), d = s.dir;
    return (models || []).slice().sort(function (a, b) {
      var x = rec.sortValue(a, s.k), y = rec.sortValue(b, s.k);
      if (x == null && y != null) return 1;
      if (y == null && x != null) return -1;
      if (x != null && y != null && x !== y) return (x - y) * d;
      return (a.idx || 0) - (b.idx || 0);
    });
  };
  /* the close column: the mean in cents with the count under it, null when no closing price is stored */
  rec.clvParts = function (t, unit) {
    if (!t || !t.clv_n) return null;
    var u = unit || 'play';
    return { value: fmt.centsSigned(t.clv_mean), sub: 'on ' + t.clv_n + ' ' + u + (t.clv_n === 1 ? '' : 's') };
  };
  /* the past record of one account tier: null when none is stored. rate = wins over games. */
  rec.pastCell = function (past) {
    if (!past || !isNum(past.n) || past.n <= 0) return null;
    return { wl: fmt.wl(past.w, past.l), n: past.n, rate: past.w / past.n };
  };
  /* one latest-graded row as table text: result is the outcome word, kind drives the one place win and loss colour is used */
  rec.latestModel = function (r, close) {
    var win = r.res === 'win', loss = r.res === 'loss';
    return { key: r.key, label: rec.playLabel(r), sport: r.sport, market: r.group, date: isNum(r.gst) ? ct.md(r.gst) : '',
      price: isNum(r.price) ? fmt.cents(r.price) : '', close: close && isNum(close.clv) ? fmt.centsSigned(close.clv) : '',
      word: win ? 'Win' : loss ? 'Loss' : 'Push', kind: win ? 'win' : loss ? 'loss' : 'push', flat: r.flat, units: fmt.units(r.flat, { signed: true }) || '' };
  };
  /* Central month keys to read: this month and the one before */
  rec.months = function (nowT) {
    var k = ct.dateKey(nowT), first = k.slice(0, 7) + '-01', prev = ct.addDays(first, -1).slice(0, 7), cur = k.slice(0, 7);
    return prev >= FIRST_MONTH ? [prev, cur] : [cur];
  };
  /* ---- Frozen plays list (the Sharps rail box under Tiers). The shown plays whose card has frozen at its cut: the same plays the Plays record
     counts (rec.playRows: sf, variant all, counted cards, NBA, NFL and CBB), plus the open list of cards_record.json (locked, no result row yet).
     An open row is dropped when a result row of the same key exists, so a play is never listed twice. Stored values only.
     Freeze time: the stored cut (the result row, else the tier log row), else the card's own rule, game start minus 15 minutes
     (scripts/build_side_cards.py: "the cut (game start - 15 min)"; 1,400+ stored rows agree). tierMap is { result key: tier log row }:
     the tier at freeze comes only from that stored log, never recomputed. */
  var CUT_LEAD = 900;
  rec.CUT_LEAD = CUT_LEAD;
  function freezeTime(r, lg) {
    if (isNum(r.cut)) return r.cut;
    if (lg && isNum(lg.cut)) return lg.cut;
    return isNum(r.gst) ? r.gst - CUT_LEAD : null;
  }
  function stateOf(r) {
    if (r.status === 'graded') return r.res === 'win' ? ['win', 'W'] : r.res === 'loss' ? ['loss', 'L'] : ['push', 'P'];
    if (r.status === 'unpriced') return ['unpriced', 'No price'];
    if (r.status === 'void') return ['void', 'Void'];
    return ['none', 'Not graded'];
  }
  /* A shown play is `card|group|all|sf`: the key shape of the record's open list and of live.json `locked`. */
  var SHOWN_KEY = /\|all\|sf$/;
  /* live.json `locked`: frozen cards awaiting a result, published by every card build (about 10 minutes), where the record's open list only
     catches up when the record job runs (about every 2 hours). extra = { locked: [...], cards: { key: { price, cut } } }, the frozen card's own
     stored price and cut when it could be read; a play with none shows no price and takes the card rule for its freeze time. */
  rec.lockedMissing = function (rows, file, locked, limit) {
    var done = {}, seen = {}, out = [];
    (rows || []).forEach(function (r) { if (r && r.kind === 'result' && typeof r.key === 'string') done[r.key] = true; });
    ((file && Array.isArray(file.open)) ? file.open : []).forEach(function (r) { if (r && typeof r.key === 'string') done[r.key] = true; });
    (Array.isArray(locked) ? locked : []).forEach(function (r) {
      if (!r || typeof r !== 'object' || typeof r.key !== 'string' || !SHOWN_KEY.test(r.key) || (r.play != null && r.play !== 'sf')) return;
      if (SHOWN.indexOf(lc(r.sport)) < 0 || done[r.key] || seen[r.key] || !rec.cardPath(r.key)) return;
      seen[r.key] = true; out.push(r);
    });
    out.sort(function (a, b) { return (isNum(b.gst) ? b.gst : 0) - (isNum(a.gst) ? a.gst : 0) || (a.key < b.key ? -1 : 1); });
    return out.slice(0, isNum(limit) ? limit : out.length).map(function (r) { return r.key; });
  };
  /* the frozen card file behind a key (the part before the first |), only in the shape the builder writes: <sport>/frozen/<date>/<name>.json */
  rec.cardPath = function (key) {
    var p = String(key == null ? '' : key).split('|')[0];
    return /^[a-z]+\/frozen\/[0-9-]+\/[A-Za-z0-9._@-]+\.json$/.test(p) ? p : null;
  };
  /* the stored cut and price at the cut from one frozen card file: the price of the key's market, shown play, and only when it is no more than 30 minutes
     older than the cut (the grader's own rule: an older price is "unpriced"). Missing or unreadable is { price: null, cut: null }. */
  rec.cardFacts = function (card, key) {
    var g = String(key || '').split('|')[1], m = card && card.markets && card.markets[g], sf = m && m.sf && m.sf.all || null, cut = card && isNum(card.cut) ? card.cut : null;
    var fresh = sf && isNum(sf.price) && sf.price > 0 && sf.price < 1 && (!isNum(sf.price_t) || cut == null || sf.price_t >= cut - 1800);
    return { price: fresh ? sf.price : null, cut: cut };
  };
  rec.frozenList = function (rows, file, tierMap, sport, extra) {
    var s = sport == null ? 'all' : lc(sport), tm = tierMap || {}, ex = extra || {}, cards = ex.cards || {};
    var out = { sport: s, items: [], total: 0, awaiting: 0, settled: 0, tally: rec.tally([], {}), noSize: false };
    if (s !== 'all' && SHOWN.indexOf(s) < 0) { out.noSize = true; return out; }
    var inSport = function (r) { var sp = lc(r.sport); return s === 'all' ? SHOWN.indexOf(sp) >= 0 : sp === s; };
    var done = {}, items = [];
    (rows || []).forEach(function (r) { if (r && r.kind === 'result' && typeof r.key === 'string') done[r.key] = true; });
    function model(r, st, lg) {
      var tier = lg && copy.tier[lc(lg.tier)] ? lc(lg.tier) : null;
      var st2 = st || stateOf(r);
      return { key: r.key, sport: lc(r.sport), group: r.group, label: rec.playLabel(r), market: r.group,
        price: isNum(r.price) && r.status !== 'unpriced' ? fmt.cents(r.price) : null, tier: tier,
        state: st2[0], word: st2[1], flat: isNum(r.flat) && st2[0] !== 'unpriced' ? r.flat : null,
        units: isNum(r.flat) && (st2[0] === 'win' || st2[0] === 'loss' || st2[0] === 'push') ? fmt.units(r.flat, { signed: true }) : null,
        cut: freezeTime(r, lg), gst: isNum(r.gst) ? r.gst : null };
    }
    var settledRows = rec.playRows(rows, s);
    settledRows.forEach(function (r) { items.push(model(r, null, tm[r.key])); });
    var seen = {};
    var open = file && Array.isArray(file.open) ? file.open : [];
    open.forEach(function (r) {
      if (!r || typeof r !== 'object' || typeof r.key !== 'string' || r.play !== 'sf' || !/\|all\|sf$/.test(r.key) || r.counts !== true) return;   /* the open list has no variant field: it is in the key (card|group|variant|play) */
      if (!inSport(r) || done[r.key] || seen[r.key]) return;
      seen[r.key] = true;
      items.push(model(r, ['open', r.postponed === true ? 'Postponed' : 'Awaiting result'], tm[r.key]));
    });
    (Array.isArray(ex.locked) ? ex.locked : []).forEach(function (r) {
      if (!r || typeof r !== 'object' || typeof r.key !== 'string' || !SHOWN_KEY.test(r.key) || (r.play != null && r.play !== 'sf')) return;
      if (!inSport(r) || done[r.key] || seen[r.key] || typeof r.side !== 'string' || !r.side) return;   /* no side, no title: not listed */
      seen[r.key] = true;
      var cf = cards[r.key] || {}, o = { key: r.key, sport: r.sport, group: r.group, side: r.side, line: r.line, outs: r.outs, gst: r.gst,
        price: isNum(cf.price) ? cf.price : (isNum(r.price) ? r.price : null), cut: isNum(cf.cut) ? cf.cut : (isNum(r.cut) ? r.cut : undefined) };
      items.push(model(o, ['open', 'Awaiting result'], tm[r.key]));
    });
    items.sort(function (a, b) {
      var ao = a.state === 'open' ? 0 : 1, bo = b.state === 'open' ? 0 : 1;
      if (ao !== bo) return ao - bo;
      var ac = isNum(a.cut) ? a.cut : -Infinity, bc = isNum(b.cut) ? b.cut : -Infinity;
      if (ac !== bc) return bc - ac;
      return a.key < b.key ? -1 : a.key > b.key ? 1 : 0;
    });
    out.items = items; out.total = items.length;
    out.awaiting = items.filter(function (x) { return x.state === 'open'; }).length;
    out.settled = out.total - out.awaiting;
    out.tally = rec.tally(settledRows, {});
    return out;
  };
  /* the box subtitle. W-L-P is rec.tally of the same rows the Plays record counts, so it equals the Record page's Record line. */
  rec.frozenSub = function (L) {
    if (!L || !L.total) return '';
    var t = L.tally, s = fmt.n(L.total) + ' frozen play' + (L.total === 1 ? '' : 's') + (t.n ? ', ' + rec.fmtWl(t) + ', flat 1u' : '');
    var ng = L.items.filter(function (x) { return x.state !== 'open' && x.state !== 'win' && x.state !== 'loss' && x.state !== 'push'; }).length;   /* void, unpriced: listed, never in the record */
    if (L.awaiting) s += (t.n ? ', ' : ': ') + fmt.n(L.awaiting) + ' awaiting result';
    if (ng) s += (t.n || L.awaiting ? ', ' : ': ') + fmt.n(ng) + ' not graded';
    return s;
  };
  /* the V2 tier log rows (pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl) as { key: row }, only rows with a known tier */
  rec.tierLogMap = function (rows) {
    var m = {};
    (rows || []).forEach(function (r) { if (r && typeof r.key === 'string' && copy.tier[lc(r.tier)]) m[r.key] = r; });
    return m;
  };
  rec.FROZEN_SHOW = 12;
  /* ---- Move grade record (rule mg-1, docs/sharp-movegrade-prereg.md): the record by slice from move_grade_record.json. A description of how far the market moved toward the play before it froze, never a signal.
     Every play is in exactly one slice; the letters live here (the Sharps page shows them as labels). In-sample = the rule was written after those results; forward = only plays whose grade was logged at lock. */
  var MG_ROWS = ['a', 'b', 'c', 'd', 'against', 'unreadable'];
  var MG_BUCKETS = ['in_sample', 'forward'];
  var MG_NAME = { in_sample: 'In-sample', forward: 'Forward' };
  var MG_LABEL = { a: 'A', b: 'B', c: 'C', d: 'D', against: 'Moved against', unreadable: 'No grade' };
  var MG_SHOWN = { a: 'Shown as LARGE', b: 'Shown as NOTABLE', c: 'Shown as ROUTINE', d: 'No label shown', against: 'Shown as "Market moved the other way"', unreadable: 'No grade, nothing shown' };
  var MG_NOTE = { in_sample: 'The grade rule was written after these results. Read it as history, not a test.', forward: 'The forward test is proposed, not registered. Plays logged before registration do not count.' };
  /* one definition of a small sample for this table and the docs: under 30 plays */
  var MG_SMALL = 30;
  rec.MG_SMALL = MG_SMALL; rec.MG_ROWS = MG_ROWS; rec.MG_BUCKETS = MG_BUCKETS; rec.MG_LABEL = MG_LABEL; rec.MG_NOTE = MG_NOTE; rec.MG_SHOWN = MG_SHOWN;
  /* the file is usable when it names the rule and has a slice object for the pooled set or any sport */
  rec.mgFileOk = function (f) {
    return !!(f && typeof f === 'object' && f.mg_rule && ((f.all && typeof f.all === 'object') || (f.sports && typeof f.sports === 'object')));
  };
  /* the slices of a sport: 'all' is the file's pooled NBA+NFL+CBB set (CFB is never pooled), summed here when the file lacks it; null when the sport is not in the file */
  rec.mgSlice = function (f, sport) {
    if (!rec.mgFileOk(f)) return null;
    var s = sport == null ? 'all' : lc(sport);
    if (s !== 'all') return f.sports && f.sports[s] && typeof f.sports[s] === 'object' ? f.sports[s] : null;
    if (f.all && typeof f.all === 'object') return f.all;
    var out = {}, any = false;
    MG_ROWS.forEach(function (r) {
      out[r] = {};
      ['all'].concat(MG_BUCKETS).forEach(function (b) { out[r][b] = rec.tierPool(SHOWN.map(function (sp) { var x = f.sports && f.sports[sp] && f.sports[sp][r]; return x && x[b]; })); });
      if (out[r].all.n) any = true;
    });
    return any ? out : null;
  };
  /* the table for a sport and a bucket: six rows in order, each with its tally and the monitor flags (zero-play rows stay in as zeros), and the pooled total. Unknown bucket reads as in-sample. */
  /* the note under the bucket switch. Forward says the test is proposed while the file's registered_cut is null (rows logged before a registration never count). */
  rec.mgNote = function (f, bucket) {
    if (bucket !== 'forward') return MG_NOTE.in_sample;
    return f && f.registered_cut != null ? 'Only plays cut after the registration and logged when the card froze. Starts at zero.' : MG_NOTE.forward;
  };
  /* one stored cell as a tally with its standard error (a fraction of 1u, null under 2 plays or when not stored) */
  rec.mgTally = function (o) {
    var t = rec.tierTally(o);
    t.se = o && isNum(o.se) && t.n > 1 ? o.se : null;
    return t;
  };
  /* the flags of a row: watch when the units are above 0, small sample under MG_SMALL (30) plays, the same rule the docs use */
  rec.mgFlag = function (t) {
    if (!t || !isNum(t.n) || t.n <= 0) return { watch: false, small: false, n: t && t.n || 0 };
    return { watch: isNum(t.units) ? t.units > 0 : (isNum(t.roi) && t.roi > 0), small: t.n < MG_SMALL, n: t.n };
  };
  rec.mgTable = function (f, sport, bucket) {
    var sl = rec.mgSlice(f, sport);
    if (!sl) return null;
    var b = MG_BUCKETS.indexOf(bucket) >= 0 ? bucket : 'in_sample';
    var rows = MG_ROWS.map(function (k) {
      var t = rec.mgTally(sl[k] && sl[k][b]);
      return { k: k, label: MG_LABEL[k], shown: MG_SHOWN[k], t: t, flag: rec.mgFlag(t) };
    });
    return { bucket: b, rows: rows, total: rec.tierPool(rows.map(function (r) { return r.t; })) };
  };
  rec.SORT_FIRST = SORT_FIRST; rec.SHADOW_SIZE = SHADOW_SIZE; rec.SHADOW_TIP = SHADOW_TIP; rec.TIER_ROWS = TIER_ROWS; rec.BUCKETS = BUCKETS; rec.TIER_FOOT = TIER_FOOT; rec.FWD_CUT = FWD_CUT; rec.FIRST_MONTH = FIRST_MONTH; rec.NEED_N = NEED_N; rec.SMALL_N = SMALL_N; rec.TIER_NONE = TIER_NONE; rec.declared = declared;
  SV2.rec = rec;

  /* ------------------------------------------------------------------ browser side */
  if (typeof document === 'undefined') return;
  var S = { sport: 'all', view: 'main', file: null, rows: null, state: 'idle', loadedAt: 0, main: null, page: null, sw: null, swPage: null, busy: false,
    tier: { data: null, state: 'idle', loadedAt: 0, stale: false, busy: null }, mg: { data: null, state: 'idle', loadedAt: 0, stale: false, busy: null }, mgb: 'in_sample', tb: 'all', tSince: false, open: {}, sort: {},
    fz: { sport: 'all', open: false }, tl: { map: {}, loadedAt: 0, busy: false }, fzc: { map: {}, tried: {}, busy: false } };

  /* Dev: ?recbase=/path/ on localhost reads the record files from a local folder (cards_record.json, cards/<sport>/<month>.jsonl, and the
     tier log at tl/<sport>/<month>.jsonl) instead of pm-holders-data. */
  function recBase() { var d = SV2.dev && SV2.dev.param ? SV2.dev.param('recbase') : null; return d ? d.replace(/\/?$/, '/') : null; }
  function getUrl(u, txt, force) {
    var k = force ? Date.now() : Math.floor(Date.now() / 300000);
    return fetch(u + '?t=' + k, { cache: force ? 'no-store' : 'default' })
      .then(function (r) { return r.ok ? (txt ? r.text() : r.json()) : null; }).catch(function () { return null; });
  }
  function get(p, txt, force) { return getUrl((recBase() || BASE) + p, txt, force); }
  /* tier_record.json: published beside live.json on pm-cards-live, rebuilt about every 10 minutes. Same 5 minute cache key as the files above.
     Dev: ?tierrecord=/path on localhost. A failed fetch keeps the file held (stale); an older build never replaces a newer one. */
  var TIER_URL = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-cards-live/tier_record.json';
  function tierSrc() { var d = SV2.dev && SV2.dev.param ? SV2.dev.param('tierrecord') : null; return d || TIER_URL; }
  function loadTier(force) {
    var T = S.tier;
    if (T.busy) return T.busy;
    if (!force && T.state === 'ok' && Date.now() - T.loadedAt < 300000) return Promise.resolve();
    if (T.state !== 'ok') T.state = 'loading';
    var u = tierSrc(), k = force ? Date.now() : Math.floor(Date.now() / 300000);
    T.busy = fetch(u + (u.indexOf('?') < 0 ? '?' : '&') + 't=' + k, { cache: force ? 'no-store' : 'default' })
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
      .then(function (j) {
        if (!j || !rec.tierFileOk(j)) { if (T.data) T.stale = true; else T.state = 'none'; }
        else if (T.data && isNum(T.data.built) && isNum(j.built) && j.built < T.data.built) { T.stale = false; T.loadedAt = Date.now(); }
        else { T.data = j; T.state = 'ok'; T.stale = false; T.loadedAt = Date.now(); }
        T.busy = null; SV2.emit('tierrecord', T.data); paint();
      });
    return T.busy;
  }
  rec.tierFile = function () { return S.tier.data; };
  /* move_grade_record.json: published beside tier_record.json on pm-cards-live. Same 5 minute cache key. Dev: ?mgrecord=/path on localhost. A missing or invalid file
     leaves the section saying it is not published yet, and nothing else changes. A failed refresh keeps the held file; an older build never replaces a newer one. */
  var MG_URL = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/pm-cards-live/move_grade_record.json';
  function mgSrc() { var d = SV2.dev && SV2.dev.param ? SV2.dev.param('mgrecord') : null; return d || MG_URL; }
  function loadMg(force) {
    var M = S.mg;
    if (M.busy) return M.busy;
    if (!force && M.state === 'ok' && Date.now() - M.loadedAt < 300000) return Promise.resolve();
    if (M.state !== 'ok') M.state = 'loading';
    var u = mgSrc(), k = force ? Date.now() : Math.floor(Date.now() / 300000);
    M.busy = fetch(u + (u.indexOf('?') < 0 ? '?' : '&') + 't=' + k, { cache: force ? 'no-store' : 'default' })
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
      .then(function (j) {
        if (!j || !rec.mgFileOk(j)) { if (M.data) M.stale = true; else M.state = 'none'; }
        else if (M.data && isNum(M.data.built) && isNum(j.built) && j.built < M.data.built) { M.stale = false; M.loadedAt = Date.now(); }
        else { M.data = j; M.state = 'ok'; M.stale = false; M.loadedAt = Date.now(); }
        M.busy = null; paint();
      });
    return M.busy;
  }
  rec.mgFile = function () { return S.mg.data; };
  function load(force) {
    loadTier(force);
    loadMg(force);
    if (S.busy) return S.busy;
    if (!force && S.state === 'ok' && Date.now() - S.loadedAt < 300000) return Promise.resolve();
    S.busy = true; if (S.state !== 'ok') S.state = 'loading';
    var months = rec.months(SV2.now()), jobs = [get('cards_record.json', false, force)];
    SPORT_ORDER.forEach(function (sp) { months.forEach(function (m) { jobs.push(get('cards/' + sp + '/' + m + '.jsonl', true, force)); }); });
    S.busy = Promise.all(jobs).then(function (r) {
      var rows = [];
      r.slice(1).forEach(function (t) { if (t) rows = rows.concat(rec.parseJsonl(t)); });
      if (!r[0] && !rows.length) { if (S.state !== 'ok') S.state = 'none'; else S.stale = true; }
      else { S.file = r[0] || S.file; S.rows = rows; S.closes = rec.closeMap(rows); S.state = 'ok'; S.stale = false; S.loadedAt = Date.now(); }
      S.busy = false; paint(); paintFrozen(); loadTl(false); loadFz(false);
    });
    return S.busy;
  }

  function sportNow() { var h = SV2.hostSport(); return h != null ? h : S.sport; }
  function pageNow() { return SV2.route().page === 'following' ? 'following' : 'sharps'; }

  /* ---- Frozen plays box (Sharps rail, under Tiers). The Sharps page asks for the markup with rec.frozenBox(sport) each time it paints its rail;
     this module loads the record lazily (the same load() and 5 minute cache as the Record view, so nothing is fetched twice) and
     refreshes the box in place when data lands or the list is opened. The tier at freeze comes from the stored V2 tier log, read only
     for a sport that has a play cut at or after the log's first row (tier_record.json first_logged_cut), so no file is asked for that cannot exist. */
  function lockedNow() { var c = store && store.cards; return c && Array.isArray(c.locked) ? c.locked : []; }
  /* frozen cards the record has not caught up with: read each one's own stored price and cut, newest first, at most 12 per pass, 5 minutes between
     tries of the same card. Never blocks a paint: the row shows at once without a price and the price joins when the file arrives. */
  function loadFz(force) {
    var F = S.fzc;
    if (F.busy || S.state !== 'ok') return;
    var keys = rec.lockedMissing(S.rows, S.file, lockedNow(), 12).filter(function (k) { return force || !(k in F.map) && !(F.tried[k] && Date.now() - F.tried[k] < 300000); });
    if (!keys.length) return;
    F.busy = true;
    var rb = recBase(), base = rb ? rb + 'pm_cards/' : BASE.replace('pm_record/', 'pm_cards/');
    Promise.all(keys.map(function (k) {
      F.tried[k] = Date.now();
      return getUrl(base + rec.cardPath(k), false, force).then(function (c) { if (c) F.map[k] = rec.cardFacts(c, k); });
    })).then(function () { F.busy = false; paintFrozen(); });
  }
  function tlSports() {
    var T = S.tier.data, first = T && isNum(T.first_logged_cut) ? T.first_logged_cut : null, out = [];
    if (first == null) return out;
    SHOWN.forEach(function (sp) {
      var any = rec.playRows(S.rows || [], sp).some(function (r) { return isNum(r.cut) && r.cut >= first; }) ||
        (S.file && Array.isArray(S.file.open) ? S.file.open : []).concat(lockedNow()).some(function (r) { return r && lc(r.sport) === sp && isNum(r.gst) && r.gst - CUT_LEAD >= first; });
      if (any) out.push(sp);
    });
    return out;
  }
  function loadTl(force) {
    var L = S.tl;
    if (L.busy || S.state !== 'ok') return;
    if (S.tier.state === 'loading' || S.tier.state === 'idle') return;   /* the tier file decides which logs exist: wait for it (its event repaints the rail) */
    if (!force && L.loadedAt && Date.now() - L.loadedAt < 300000) return;
    L.busy = true;
    var base = recBase() ? recBase() + 'tl/' : BASE.replace('pm_record/', 'pm_cards/'), sports = tlSports(), months = rec.months(SV2.now()), jobs = [];
    sports.forEach(function (sp) { months.forEach(function (m) { jobs.push(getUrl(base + sp + '/' + (recBase() ? '' : 'v2_tier/') + m + '.jsonl', true, force)); }); });
    Promise.all(jobs).then(function (r) {
      var rows = []; r.forEach(function (t) { if (t) rows = rows.concat(rec.parseJsonl(t)); });
      if (rows.length || !Object.keys(L.map).length) L.map = rec.tierLogMap(rows);
      if (jobs.length || S.tier.data) L.loadedAt = Date.now();
      L.busy = false; paintFrozen();
    });
  }
  function fzRow(m) {
    var word = m.state === 'open' || m.units == null ? m.word : m.word + ' ' + m.units;
    var kind = m.state === 'win' ? 'win' : m.state === 'loss' ? 'loss' : 'muted';
    var say = m.state === 'win' ? 'Win' : m.state === 'loss' ? 'Loss' : m.state === 'push' ? 'Push' : m.word;
    var meta = '';
    if (isNum(m.cut)) meta += '<span class="sv2-num">' + esc(ct.md(m.cut) + ', ' + ct.time(m.cut)) + '</span>';
    meta += '<span class="sv2-chip sv2-chip--muted"><span>' + esc(sportName(m.sport)) + '</span></span>';
    return '<li class="sv2-fz-r" data-state="' + m.state + '"><div class="sv2-fz-l"><span class="sv2-fz-top"><b class="sv2-fz-title">' + esc(m.label) + '</b>' +
      (m.price ? '<span class="sv2-num sv2-fz-px"><span class="sv2-sr">Price at the freeze </span>' + esc(m.price) + '</span>' : '') + '</span>' +
      '<span class="sv2-fz-meta">' + meta + '</span></div>' +
      '<div class="sv2-fz-rt"><span class="sv2-chip sv2-chip--' + kind + ' sv2-fz-res"><span aria-hidden="true">' + esc(word) + '</span><span class="sv2-sr">' + esc(say + (m.units && m.state !== 'open' ? ', ' + m.units.replace('u', ' units') : '')) + '</span></span>' +
      (m.tier ? ui.tier(m.tier) : '') + '</div></li>';
  }
  function frozenInner() {
    var sp = S.fz.sport, h = '<h2 class="sv2-h2" id="sv2-fz-h">Frozen plays</h2>';
    if (S.state === 'none') return h + '<p class="sv2-rec-railn">Could not load. <button type="button" class="sv2-link" data-sv2-fz-retry>Try again</button></p>';
    if (S.state !== 'ok') return h + ui.skel(3, 'Loading the frozen plays', 'sv2-fz-skel');
    var L = rec.frozenList(S.rows, S.file, S.tl.map, sp, { locked: lockedNow(), cards: S.fzc.map });
    if (L.noSize) return h + '<p class="sv2-rec-railn">CFB shows no size, so no play is listed here. The record tab keeps a tracked CFB record.</p><p class="sv2-rec-railn"><button type="button" class="sv2-sp-lnk" data-sv2-open-record>See the full record</button></p>';
    if (!L.total) return h + '<p class="sv2-rec-railn">No frozen plays yet' + (sp === 'all' ? '' : ' for ' + esc(sportName(sp))) + '.</p>';
    var many = L.total > rec.FROZEN_SHOW, open = many && S.fz.open, list = open ? L.items : L.items.slice(0, rec.FROZEN_SHOW);
    h += '<p class="sv2-fz-sub">' + esc(rec.frozenSub(L)) + '</p>';
    var ul = '<ul class="sv2-fz-list">' + list.map(fzRow).join('') + '</ul>';
    h += open ? '<div class="sv2-fz-scroll" id="sv2-fz-list" tabindex="0" role="region" aria-label="All frozen plays, newest first">' + ul + '</div>' : '<div id="sv2-fz-list">' + ul + '</div>';
    if (many) h += '<button type="button" class="sv2-sp-ctxbtn sv2-press sv2-press-btn sv2-fz-more" data-sv2-fz-more aria-expanded="' + open + '" aria-controls="sv2-fz-list"><span>' +
      (open ? 'Show fewer' : 'Show all (' + fmt.n(L.total) + ')') + '</span>' + ui.icon('chevron', 'sv2-chev') + '</button>';
    return h + '<p class="sv2-rec-railn">Times are Central. Context only, a record and not proof.</p>' +
      '<p class="sv2-rec-railn"><button type="button" class="sv2-sp-lnk" data-sv2-open-record>See the full record</button></p>';
  }
  /* in-place refresh of every frozen box on the page; keeps keyboard focus on the control that was used */
  function paintFrozen(focusSel) {
    var boxes = document.querySelectorAll('[data-sv2-fz]');
    Array.prototype.forEach.call(boxes, function (b) {
      b.innerHTML = frozenInner();
      b.setAttribute('aria-busy', S.state === 'ok' ? 'false' : 'true');
      if (focusSel) { var f = b.querySelector(focusSel); if (f) { try { f.focus({ preventScroll: true }); } catch (e) { /* ignore */ } } }
    });
    if (SV2.rail && SV2.rail.catchUp && boxes.length) SV2.rail.catchUp();
  }
  rec.frozenBox = function (sport) {
    S.fz.sport = sport == null ? 'all' : lc(sport);
    if (S.state === 'idle' || (S.state === 'ok' && !S.busy && Date.now() - S.loadedAt >= 300000)) load(false);   /* lazy: the first paint is never blocked */
    loadTl(false); loadFz(false);
    return '<section class="sv2-box sv2-sp-rb sv2-fz" data-sv2-fz aria-labelledby="sv2-fz-h" aria-busy="' + (S.state === 'ok' ? 'false' : 'true') + '">' + frozenInner() + '</section>';
  };

  /* ---- small renderers */
  function num(x) { return '<span class="sv2-num">' + esc(x) + '</span>'; }
  function signCls(x) { return isNum(x) && x > 0 ? ' sv2-win' : isNum(x) && x < 0 ? ' sv2-loss' : ''; }
  function unitsHtml(t) { return isNum(t.units) && t.n ? '<span class="sv2-num' + signCls(t.units) + '">' + esc(fmt.units(t.units, { signed: true })) + '</span>' : '<span class="sv2-mut">none</span>'; }
  function roiHtml(t) { return isNum(t.roi) && t.n ? '<span class="sv2-num' + signCls(t.roi) + '">' + esc(fmt.pct(t.roi, { signed: true })) + '</span>' : '<span class="sv2-mut">none</span>'; }
  function wl(t) { return t.n ? esc(fmt.wl(t.w, t.l, t.p)) : '0-0'; }
  function clvText(t, unit) {
    if (!t.clv_n) return 'No closing price stored yet';
    return 'vs the close ' + fmt.centsSigned(t.clv_mean) + ' on ' + t.clv_n + ' ' + (unit || 'play') + (t.clv_n === 1 ? '' : 's');
  }
  function flagHtml(t) {
    var m = rec.monitor(t);
    if (m.watch) return '<span class="sv2-chip sv2-chip--caution"><span>Watch closely' + (m.small ? ': small sample, n=' : ': n=') + '<span class="sv2-num">' + fmt.n(m.n) + '</span></span></span>';
    if (m.tiny && m.n > 0) return '<span class="sv2-chip sv2-chip--muted"><span>small sample, n=<span class="sv2-num">' + m.n + '</span></span></span>';
    return '';
  }
  function pill() { return '<span class="sv2-play"><b>1u</b><span>' + esc(copy.play.label) + '</span></span>'; }
  function head(id, title, sub) {
    return '<div class="sv2-rec-h"><h2 class="sv2-h2" id="' + id + '">' + esc(title) + '</h2>' + (sub ? '<p class="sv2-rec-sub">' + sub + '</p>' : '') + '</div>';
  }
  function stat(label, valueHtml, note) {
    return '<div class="sv2-rec-stat"><span class="sv2-rec-k">' + esc(label) + '</span><span class="sv2-rec-v">' + valueHtml + '</span>' + (note ? '<span class="sv2-rec-kn">' + note + '</span>' : '') + '</div>';
  }

  /* ---- record tables: the Plays table design (.sv2-tb in one glass card, sv2.css section 13), with a few sv2-rec-tb modifiers.
     A column is { c, label, k (sortable), num, p (stays in the stacked row), s (1 or 2: leaves the row when the card is narrow, stays in the dropdown), tag }.
     Every row has a dropdown holding what the narrow row leaves out. */
  function idOf(tid, key) { return 'sv2-rx-' + tid + '-' + String(key).replace(/[^a-z0-9]+/gi, '-'); }
  function colCls(c) { return 'c-' + c.c + (c.num ? ' c-num' : '') + (c.s ? ' c-s' + c.s : '') + (c.grp ? ' c-' + c.grp : '') + (c.bar ? ' c-bar' : ''); }
  function theadHtml(tid, cols, groups) {
    var s = rec.cleanSort(S.sort[tid]);
    var g = groups ? '<tr class="sv2-rec-grp">' + groups.map(function (x) {
      return '<th scope="colgroup"' + (x.span > 1 ? ' colspan="' + x.span + '"' : '') + ' class="' + (x.cls || '') + '">' + (x.label ? esc(x.label) : '<span class="sv2-sr">' + esc(x.sr) + '</span>') + '</th>';
    }).join('') + '</tr>' : '';
    return '<thead>' + g + '<tr>' + cols.map(function (c) {
      if (c.sr) return '<th scope="col" class="' + colCls(c) + '"><span class="sv2-sr">' + esc(c.sr) + '</span></th>';
      if (!c.k) return '<th scope="col" class="' + colCls(c) + '">' + (c.tag ? '<span class="sv2-rec-shh"><i class="sv2-rec-shtag"' + (c.tip ? ' title="' + esc(c.tip) + '"' : '') + '>' + esc(c.tag) + '</i>' + esc(c.label) + '</span>' : esc(c.label)) + '</th>';
      var on = s.k === c.k;
      return '<th scope="col" class="' + colCls(c) + ' is-sort" aria-sort="' + (on ? (s.dir === 1 ? 'ascending' : 'descending') : 'none') + '"><button type="button" class="sv2-tb-sort sv2-press sv2-press-chip" data-sv2-rsort="' + tid + ':' + c.k + '">' + esc(c.label) + ui.sortArrow(on, s.dir) + '</button></th>';
    }).join('') + '</tr></thead>';
  }
  /* one cell. kind 'row' is the row header (th scope row); p marks a cell that stays in the stacked row, with its label from data-k */
  function cell(c, html, o) {
    o = o || {};
    var tag = o.row ? 'th' : 'td';
    return '<' + tag + (o.row ? ' scope="row"' : '') + ' class="sv2-tb-c ' + colCls(c) + (c.p ? ' c-p' : '') + (o.cls ? ' ' + o.cls : '') + '"' + (c.p ? ' data-k="' + esc(c.label) + '"' : '') + '>' + html + '</' + tag + '>';
  }
  function chevCell(open, id, label) {
    return '<td class="sv2-tb-c c-chev"><button type="button" class="sv2-tb-tog sv2-press sv2-press-btn" aria-expanded="' + open + '" aria-controls="' + id + '" aria-label="' + esc(label) + '" data-sv2-rx="' + id + '">' + ui.icon('chevron', 'sv2-chev') + '</button></td>';
  }
  /* o: tid, key, attrs (extra tr attributes), cells (html), detail (html), label (what the dropdown is for), ncol */
  function rowHtml(o) {
    var id = idOf(o.tid, o.key), open = !!S.open[id];
    var tr = '<tr class="sv2-tb-r' + (open ? ' is-open' : '') + '"' + (o.attrs || '') + '>' + o.cells + chevCell(open, id, o.label) + '</tr>';
    var dr = '<tr class="sv2-tb-d"><td colspan="' + o.ncol + '"><div class="sv2-x" id="' + id + '"' + (open ? ' data-open' : '') + '><div class="sv2-x-in" role="region" aria-label="' + esc(o.label) + '"><div class="sv2-rec-dd">' + o.detail + '</div></div></div></td></tr>';
    return tr + dr;
  }
  function tableHtml(tid, label, cols, rowsHtml, groups) {
    return '<div class="sv2-card sv2-tb-card sv2-rec-tb" data-tid="' + tid + '"><div class="sv2-tb-scroll"><table class="sv2-tb" aria-label="' + esc(label) + '">' +
      theadHtml(tid, cols, groups) + '<tbody>' + rowsHtml + '</tbody></table></div></div>';
  }
  function dl(items) {
    return '<dl class="sv2-rec-dl">' + items.map(function (x) { return '<div class="' + (x[2] || '') + '"><dt>' + x[0] + '</dt><dd>' + x[1] + '</dd></div>'; }).join('') + '</dl>';
  }
  /* a label cell: the name, then a muted line with the sample note and the flag */
  function labCell(c, title, sub, o) {
    return cell(c, '<span class="sv2-tb-title"><b>' + title + '</b></span>' + (sub ? '<span class="sv2-tb-mu">' + sub + '</span>' : ''), { row: true, cls: 'c-bar' + (o && o.cls ? ' ' + o.cls : '') });
  }
  function clvCell(c, t, unit) {
    var p = rec.clvParts(t, unit);
    return cell(c, p ? '<span class="sv2-num">' + esc(p.value) + '</span><span class="sv2-tb-sub">' + esc(p.sub) + '</span>' : '<span aria-hidden="true">-</span><span class="sv2-sr">No closing price stored yet</span>');
  }
  function tUnits(t) { return '<span class="sv2-num' + signCls(t.units) + '">' + esc(rec.fmtUnits(t)) + '</span>'; }
  function tRoi(t) { return '<span class="sv2-num' + signCls(t.roi) + '">' + esc(rec.fmtRoi(t)) + '</span>'; }
  /* the columns every tally table shares. cols are built once per table. */
  function mcol(label0, o) {
    o = o || {};
    var cols = [{ c: 'lab', label: label0, k: 'def', bar: true }, { c: 'wl', label: 'W-L', num: true, p: true }, { c: 'units', label: 'Units', k: 'units', num: true, p: true }, { c: 'roi', label: 'ROI', k: 'roi', num: true, p: true }];
    if (o.accts) cols.splice(1, 0, { c: 'ac', label: 'Accounts', num: true, p: true });
    cols.push({ c: 'n', label: 'n', k: 'n', num: true, s: 2 });
    if (!o.noClv) cols.push({ c: 'clv', label: 'vs the close', num: true, s: 1 });
    return cols;
  }
  function byC(cols) { var m = {}; cols.forEach(function (c) { m[c.c] = c; }); return m; }
  function tallyCells(C, t, unit, o) {
    return cell(C.wl, num(rec.fmtWl(t))) + (o && o.ac ? cell(C.ac, o.ac) : '') + cell(C.units, tUnits(t)) + cell(C.roi, tRoi(t)) + cell(C.n, num(fmt.n(t.n))) + (C.clv ? clvCell(C.clv, t, unit) : '');
  }
  function clvDetail(t, unit) { var p = rec.clvParts(t, unit); return p ? num(p.value) + ' ' + esc(p.sub) : 'No closing price stored yet'; }
  function tallyDetail(t, unit) { return dl([['n', num(fmt.n(t.n))], ['vs the close', clvDetail(t, unit)]]); }
  /* a plain tally table (sport, market, forward and in-sample): models are { key, label (html), sub (html), t, tag? } */
  function tallyTable(tid, label, firstCol, models, unit, o) {
    var cols = mcol(firstCol), C = byC(cols), ncol = cols.length + 1;
    var order = rec.sortRows(models.map(function (m, i) { m.idx = i; return m; }), S.sort[tid]);
    var rows = order.map(function (m) {
      var fl = flagHtml(m.t), sub = (m.sub || '') + (m.sub && fl ? ' ' : '') + fl;
      return rowHtml({ tid: tid, key: m.key, ncol: ncol, label: m.name + ', detail', attrs: o && o.attrs ? o.attrs(m) : '',
        cells: labCell(C.lab, m.label, sub) + tallyCells(C, m.t, unit), detail: tallyDetail(m.t, unit) });
    }).join('');
    return tableHtml(tid, label, cols, rows);
  }

  /* ---- section 1: plays record */
  function playsSection(sport) {
    var all = rec.playRows(S.rows || [], sport), t = rec.tally(all, S.closes), sp = rec.splitForward(all, FWD_CUT);
    var tf = rec.tally(sp.forward, S.closes), ti = rec.tally(sp.in_sample, S.closes);
    var tracked = sport === 'cfb';
    var html = '<section class="sv2-rec-sec" aria-labelledby="rec-h-plays">' +
      head('rec-h-plays', 'Plays record', tracked ? 'CFB shows no size. This is a tracked record at a flat 1u, not a shown play.' : 'The shown plays at a flat 1u ' + pill()) ;
    if (!t.n) {
      return html + '<p class="sv2-empty-line">No graded plays yet for ' + esc(sport === 'all' ? 'these sports' : sportName(sport)) + '.</p></section>';
    }
    html += '<div class="sv2-card sv2-rec-hero">' +
      stat('Units', unitsHtml(t)) + stat('ROI', roiHtml(t)) + stat('Record', num(wl(t)), 'n=' + num(fmt.n(t.n))) + '</div>' +
      '<p class="sv2-rec-line">' + flagHtml(t) + ' <span class="sv2-rec-clv">' + esc(clvText(t)) + '</span></p>' +
      (rec.seNote(t) ? '<p class="sv2-rec-note">' + esc(rec.seNote(t)) + '</p>' : '') +
      '<p class="sv2-rec-note">A record is context, not proof. It is a shadow test of an untested rule.</p>';
    /* forward and in-sample, read apart: one table, two rows */
    var fcut = 'Cut from ' + esc(ct.md(FWD_CUT) + ', ' + ct.time(FWD_CUT, true)), icut = 'Cut before that. Read it as history, not a test.';
    html += '<h3 class="sv2-rec-h3">Forward and in-sample</h3>' + fwdTable([
      { key: 'forward', name: 'Forward', label: 'Forward', sub: '<span class="sv2-rec-cut">' + fcut + '</span>', t: tf, empty: 'No graded forward plays yet.' },
      { key: 'insample', name: 'In-sample', label: 'In-sample', sub: '<span class="sv2-rec-cut">' + icut + '</span>', t: ti, empty: 'None.' }]);
    /* by sport (all) and by market */
    if (sport === 'all') {
      var rs = SHOWN.concat(['cfb']).map(function (s) {
        var tt = rec.tally(rec.playRows(S.rows || [], s), S.closes);
        return tt.n ? { key: s, name: sportName(s), label: esc(sportName(s)), sub: s === 'cfb' ? '<span class="sv2-rec-tag">no size shown</span>' : '', t: tt } : null;
      }).filter(Boolean);
      if (rs.length) html += '<h3 class="sv2-rec-h3">By sport</h3>' + tallyTable('sport', 'By sport', 'Sport', rs, 'play');
    }
    var ms = MARKETS.map(function (m) {
      var tt = rec.tally(all.filter(function (r) { return r.group === m[0]; }), S.closes);
      return tt.n ? { key: m[0], name: m[1], label: esc(m[1]), sub: '', t: tt } : null;
    }).filter(Boolean);
    if (ms.length) html += '<h3 class="sv2-rec-h3">By market</h3>' + tallyTable('mkt', 'By market', 'Market', ms, 'play');
    /* latest graded */
    html += '<h3 class="sv2-rec-h3">Latest graded plays</h3>' + latestTable(rec.latest(all, 12));
    return html + '</section>';
  }
  /* forward and in-sample: two fixed rows (not sortable), a row with no plays says so */
  function fwdTable(models) {
    var cols = mcol('Plays'), C = byC(cols), ncol = cols.length + 1;
    cols.forEach(function (c) { if (c.k) c.k = null; });
    var rows = models.map(function (m) {
      if (!m.t.n) return '<tr class="sv2-tb-r sv2-rec-none">' + labCell(C.lab, m.label, m.sub) + '<td class="sv2-tb-c c-msg" colspan="' + (ncol - 1) + '">' + esc(m.empty) + '</td></tr>';
      var fl = flagHtml(m.t);
      return rowHtml({ tid: 'fwd', key: m.key, ncol: ncol, label: m.name + ', detail', cells: labCell(C.lab, m.label, m.sub + (fl ? ' ' + fl : '')) + tallyCells(C, m.t, 'play'), detail: tallyDetail(m.t, 'play') });
    }).join('');
    return tableHtml('fwd', 'Forward and in-sample', cols, rows);
  }
  function latestTable(list) {
    var cols = [{ c: 'dt', label: 'Date', p: true, bar: true }, { c: 'sp', label: 'Sport', s: 2 }, { c: 'lab', label: 'Play' }, { c: 'px', label: 'Price', num: true, p: true },
      { c: 'cl', label: 'Close', num: true, s: 1 }, { c: 'res', label: 'Result', p: true }, { c: 'u', label: 'Units', num: true, p: true }], C = byC(cols), ncol = cols.length + 1;
    var rows = list.map(function (r, i) {
      var m = rec.latestModel(r, S.closes && S.closes[r.key]), chip = m.kind === 'win' ? 'sv2-chip--win' : m.kind === 'loss' ? 'sv2-chip--loss' : 'sv2-chip--muted';
      var cells = cell(C.dt, esc(m.date), { row: true, cls: 'c-bar' }) + cell(C.sp, '<span class="sv2-chip sv2-chip--muted"><span>' + esc(sportName(m.sport)) + '</span></span>') +
        cell(C.lab, '<span class="sv2-tb-title"><b>' + esc(m.label) + '</b></span><span class="sv2-tb-mu">' + esc(m.market) + '</span>') +
        cell(C.px, '<span class="sv2-num">' + esc(m.price) + '</span>') + cell(C.cl, m.close ? '<span class="sv2-num">' + esc(m.close) + '</span>' : '<span aria-hidden="true">-</span><span class="sv2-sr">No closing price stored</span>') +
        cell(C.res, '<span class="sv2-chip ' + chip + '"><span>' + m.word + '</span></span>') +
        cell(C.u, '<span class="sv2-num' + signCls(m.flat) + '">' + esc(m.units) + '</span>');
      return rowHtml({ tid: 'latest', key: i + '-' + m.key, ncol: ncol, label: m.label + ', ' + m.word + ', detail', attrs: ' data-res="' + m.kind + '"', cells: cells,
        detail: dl([['Sport', esc(sportName(m.sport))], ['Market', esc(m.market)], ['Price', num(m.price || '-')], ['Close', m.close ? num(m.close) : 'No closing price stored']]) });
    }).join('');
    return tableHtml('latest', 'Latest graded plays', cols, rows);
  }

  /* ---- section 2: tier record (evidence tiers), from tier_record.json */
  function shVals(size, sh) {
    var ss = rec.fmtSize(size), un = rec.fmtShadowUnits(sh), ro = rec.fmtShadowRoi(sh), st = rec.fmtStaked(sh);
    return { size: num(ss), units: num(un) + (ro !== '-' ? ' <span class="sv2-rec-shr">' + esc(ro) + '</span>' : ''), tip: rec.SHADOW_TIP + (st !== '-' ? ' Staked ' + st + '.' : '') };
  }
  var TCOLS = mcol('Tier', { noClv: true }).concat([{ c: 'shs', label: 'Size', num: true, s: 1, tag: 'shadow', tip: rec.SHADOW_TIP, grp: 'sh' }, { c: 'shu', label: 'Units, ROI', num: true, s: 1, tag: 'shadow', tip: rec.SHADOW_TIP, grp: 'sh' }]);
  function tLabel(r) {
    return r.derived ? ui.tier(r.tier) : '<span class="sv2-chip sv2-chip--muted" data-tier="none"><span>Not derivable</span></span>';
  }
  function tierRow(m) {
    var r = m.r, C = byC(TCOLS), ncol = TCOLS.length + 1, v = shVals(r.size, r.shadow), fl = flagHtml(r.t);
    var sub = (r.derived ? '' : '<span class="sv2-rec-tag">no stored facts at the cut</span> ') + fl;
    var name = r.derived ? copy.tier[r.tier].word : 'Not derivable';
    var cells = cell(C.lab, '<span class="sv2-tb-title">' + tLabel(r) + '</span>' + (sub.trim() ? '<span class="sv2-tb-mu">' + sub + '</span>' : ''), { row: true, cls: 'c-bar' }) +
      tallyCells(C, r.t) + cell(C.shs, v.size, { cls: 'sv2-rec-sh' }) + '<td class="sv2-tb-c ' + colCls(C.shu) + ' sv2-rec-sh" title="' + esc(v.tip) + '"><span class="sv2-sr">Shadow units and ROI on staked units, </span>' + v.units + '</td>';
    var share = r.share == null ? 0 : r.share * 100;
    var shareHtml = '<span class="sv2-rec-share"><span class="sv2-rec-bar" data-tier="' + r.tier + '" aria-hidden="true"><i style="width:' + share.toFixed(1) + '%"></i></span>' +
      '<span class="sv2-rec-sharet">' + (r.share == null ? 'no plays' : esc(fmt.pct(r.share, { d: 0 })) + ' of the total') + '</span></span>';
    var detail = shareHtml + dl([['n', num(fmt.n(r.t.n))], ['<i class="sv2-rec-shtag">shadow</i> Size', v.size], ['<i class="sv2-rec-shtag">shadow</i> Units, ROI', v.units]]) + marketSplit(r, name);
    return rowHtml({ tid: 'tier', key: r.tier, ncol: ncol, label: name + ', by market and detail', attrs: ' data-tier="' + r.tier + '"', cells: cells, detail: detail });
  }
  /* the market split of one tier: a nested table, shown when the bucket holds the same plays as all */
  function marketSplit(r, name) {
    if (!r.markets) return '';
    return '<p class="sv2-rec-k">By market</p><table class="sv2-rec-st" aria-label="' + esc(name + ' by market') + '"><thead><tr><th scope="col">Market</th><th scope="col" class="c-num">W-L</th><th scope="col" class="c-num">Units</th><th scope="col" class="c-num">ROI</th><th scope="col" class="c-num">n</th>' +
      '<th scope="col" class="c-num"><i class="sv2-rec-shtag">shadow</i> Size</th><th scope="col" class="c-num"><i class="sv2-rec-shtag">shadow</i> Units, ROI</th></tr></thead><tbody>' +
      r.markets.map(function (m) {
        var v = shVals(r.size, m.shadow);
        return '<tr><th scope="row">' + esc(m.label) + '</th><td class="c-num" data-k="W-L">' + num(rec.fmtWl(m.t)) + '</td><td class="c-num" data-k="Units">' + tUnits(m.t) + '</td><td class="c-num" data-k="ROI">' + tRoi(m.t) + '</td><td class="c-num" data-k="n">' + num(fmt.n(m.t.n)) + '</td>' +
          '<td class="c-num sv2-rec-sh" data-k="Shadow size">' + v.size + '</td><td class="c-num sv2-rec-sh" data-k="Shadow units" title="' + esc(v.tip) + '">' + v.units + '</td></tr>';
      }).join('') + '</tbody></table>';
  }
  function tiersSection(sport) {
    var T = S.tier, html = '<section class="sv2-rec-sec" aria-labelledby="rec-h-tiers">' + head('rec-h-tiers', 'Tier record', 'Each tier read apart, at a flat 1u');
    if (T.state === 'loading' || T.state === 'idle') return html + ui.skel(2, 'Loading the tier record') + '</section>';
    if (!T.data) return html + '<p class="sv2-empty-line">Could not load the tier record. <button type="button" class="sv2-link" data-sv2-rec-retry>Try again</button></p></section>';
    var f = T.data, bucket = S.tSince ? 'since_nov16' : S.tb, tb = rec.tierTable(f, sport, bucket);
    if (!tb) return html + '<p class="sv2-empty-line">No tier record for ' + esc(sportName(sport)) + ' yet.</p></section>';
    var sw = '<div class="sv2-rec-tsw">' + seg.html({ id: 'rec-tbucket', label: 'Which plays', value: S.tSince ? '' : S.tb, size: 'sm', scroll: true,
      items: [{ v: 'all', label: BUCKET_NAME.all }, { v: 'in_sample', label: BUCKET_NAME.in_sample }, { v: 'forward', label: BUCKET_NAME.forward }] }) +
      '<button type="button" class="sv2-rec-since sv2-press sv2-press-btn" data-sv2-tt-since aria-pressed="' + S.tSince + '">Since Nov 16 (tier derived after the fact)</button></div>';
    var note = '';
    if (bucket === 'forward') {
      var fn = String(f.forward_note || 'forward starts at the first logged lock');
      note = '<div class="sv2-card sv2-rec-tnote"><p class="sv2-rec-note"><b>Forward.</b> ' + esc(fn.charAt(0).toUpperCase() + fn.slice(1)) + '. ' +
        (tb.total.n ? '' : 'No tier has been logged at a lock and graded yet, so every row below is zero. Zero is not a record.') +
        ' Logged rows so far: <span class="sv2-num">' + esc(fmt.n(isNum(f.logged_rows) ? f.logged_rows : 0)) + '</span>.</p></div>';
    } else if (bucket === 'since_nov16') {
      note = '<div class="sv2-card sv2-rec-tnote"><p class="sv2-rec-note"><b>Informational only.</b> These are plays cut on or after Nov 16, 12:00 AM Central. Their tier was derived after the fact, so this is not forward.</p></div>';
    } else if (bucket === 'in_sample') {
      note = '<div class="sv2-card sv2-rec-tnote"><p class="sv2-rec-note"><b>In-sample.</b> The tier rule was written after these results. Read it as history, not a test.</p></div>';
    }
    var hero = tb.derived.n ? '<div class="sv2-card sv2-rec-hero">' + stat('Units', tUnits(tb.derived)) + stat('ROI', tRoi(tb.derived)) + stat('Record', num(rec.fmtWl(tb.derived)), 'n=' + num(fmt.n(tb.derived.n)) + ', tiers only') + '</div>' : '';
    var models = rec.sortRows(tb.rows.map(function (r, i) { return { idx: i, r: r, t: r.t }; }), S.sort.tier);
    var tbl = tableHtml('tier', 'Tier record, ' + BUCKET_NAME[bucket], TCOLS, models.map(tierRow).join(''));
    var likeTxt = rec.likeLine(tb.like, bucket);
    var cfbNote = sport === 'cfb' ? 'CFB: the shadow stakes nothing, no size shown.' : '';
    var like = likeTxt || cfbNote ? '<p class="sv2-rec-note sv2-rec-like">' + esc(likeTxt || cfbNote) + '</p>' : '';
    var foot = like + '<p class="sv2-rec-note">Shadow columns: ' + esc(rec.SHADOW_TIP) + ' Sizes by tier (rule v2s-1): Clear 1.5u, Mixed 1u, Thin 0.5u, Contested 0.5u, none for CFB and Not derivable. An ordering by evidence, not fitted to results. The page and the suggested size stay a flat 1u. Per-tier ROI is the same under both rules, only the pooled lines differ. At these samples no difference can be read.</p>' +
      '<p class="sv2-rec-note">' + esc(TIER_FOOT) + '</p>' +
      (bucket !== 'all' && bucket !== 'in_sample' ? '' : '<p class="sv2-rec-note">The market split opens under a tier. It is stored for all plays, so it shows when the bucket holds the same plays.</p>') +
      (sport === 'all' ? '<p class="sv2-rec-note">All pools NBA, NFL and CBB. CFB is not pooled.</p>' : '') +
      (sport === 'cfb' ? '<p class="sv2-rec-note">CFB shows no size on the page. This is a flat 1u record for reference.</p>' : '') +
      '<p class="sv2-rec-note">Units and ROI are flat 1u at the stored price at the cut, not the size the page shows (' + esc(copy.play.label) + '). Not derivable means no stored facts at the cut, so it is never counted in a tier. At n under ' + NEED_N + ' per sport no edge can be read. A record is context, not proof.' +
      (isNum(f.built) ? ' Tier record built ' + esc(ct.md(f.built) + ', ' + ct.time(f.built, true)) + (T.stale ? '. Last refresh failed, showing the earlier file.' : '.') : '') + '</p>';
    return html + sw + note + hero + tbl + foot + '</section>';
  }

  /* ---- the Move grade record: A to D, moved against and no grade, in-sample and forward */
  var MGCOLS = mcol('Move grade', { noClv: true }); MGCOLS.splice(MGCOLS.length - 1 + 1, 0, { c: 'se', label: 'SE', num: true, s: 1 });
  function seText(t) { return isNum(t.se) && t.n > 1 ? '+/-' + (t.se * 100).toFixed(1) + ' pts' : '-'; }
  function mgFlagHtml(r) {
    var m = r.flag;
    if (m.watch) return '<span class="sv2-chip sv2-chip--caution"><span>Watch closely' + (m.small ? ': small sample, n=' : ': n=') + '<span class="sv2-num">' + fmt.n(m.n) + '</span></span></span>';
    if (m.small && m.n > 0) return '<span class="sv2-chip sv2-chip--muted"><span>small sample, n=<span class="sv2-num">' + m.n + '</span></span></span>';
    return '';
  }
  function mgRow(m) {
    var r = m.r, C = byC(MGCOLS), ncol = MGCOLS.length + 1, fl = mgFlagHtml(r);
    var sub = '<span class="sv2-rec-tag">' + esc(r.shown) + '</span>' + (fl ? ' ' + fl : '');
    var cells = cell(C.lab, '<span class="sv2-tb-title"><b>' + esc(r.label) + '</b></span><span class="sv2-tb-mu">' + sub + '</span>', { row: true, cls: 'c-bar' }) + tallyCells(C, r.t) + cell(C.se, '<span class="sv2-num">' + esc(seText(r.t)) + '</span>');
    return rowHtml({ tid: 'mg', key: r.k, ncol: ncol, label: r.label + ', detail', attrs: ' data-mg="' + r.k + '"', cells: cells, detail: dl([['n', num(fmt.n(r.t.n))], ['Standard error of the ROI', num(seText(r.t))], ['Shown on the page as', esc(r.shown)]]) });
  }
  function mgSection(sport) {
    var M = S.mg, html = '<section class="sv2-rec-sec" aria-labelledby="rec-h-mg">' + head('rec-h-mg', 'By Move grade', 'How far the market moved toward the play before it froze, at a flat 1u');
    if (M.state === 'loading' || M.state === 'idle') return html + ui.skel(2, 'Loading the Move grade record') + '</section>';
    if (!M.data) return html + '<p class="sv2-empty-line">Move grade record not published yet.</p></section>';
    var f = M.data, b = MG_BUCKETS.indexOf(S.mgb) >= 0 ? S.mgb : 'in_sample', tb = rec.mgTable(f, sport, b);
    if (!tb) return html + '<p class="sv2-empty-line">No Move grade record for ' + esc(sportName(sport)) + ' yet.</p></section>';
    var sw = '<div class="sv2-rec-mgsw">' + seg.html({ id: 'rec-mgbucket', label: 'Which plays', value: b, size: 'sm', scroll: true, items: MG_BUCKETS.map(function (v) { return { v: v, label: MG_NAME[v] }; }) }) + '</div>';
    var note = '<div class="sv2-card sv2-rec-tnote"><p class="sv2-rec-note"><b>' + esc(MG_NAME[b]) + '.</b> ' + esc(rec.mgNote(f, b)) + (b === 'forward' && !tb.total.n ? ' Every row below is zero. Zero is not a record.' : '') + '</p></div>';
    var models = rec.sortRows(tb.rows.map(function (r, i) { return { idx: i, r: r, t: r.t }; }), S.sort.mg);
    var tbl = tableHtml('mg', 'Move grade record, ' + MG_NAME[b], MGCOLS, models.map(mgRow).join(''));
    var foot = '<p class="sv2-rec-note">The grade describes how far the market moved toward the play (Pinnacle\'s price, the market\'s number) in the 24 hours before it froze. It is not a bet signal and changes no size. In the history so far the letters did not order the results.</p>' +
      '<p class="sv2-rec-note">Units and ROI are flat 1u at the stored price at the cut, not the size the page shows (' + esc(copy.play.label) + '). At n under ' + NEED_N + ' per sport no edge can be read. A record is context, not proof. SE is one standard error of the ROI in points. A small sample is under ' + MG_SMALL + ' plays, the same rule the docs use.' +
      (sport === 'all' ? ' All pools NBA, NFL and CBB. CFB is not pooled.' : '') + (sport === 'cfb' ? ' CFB shows no size on the page. This is a flat 1u record for reference.' : '') +
      (isNum(f.built) ? ' Built ' + esc(ct.md(f.built) + ', ' + ct.time(f.built, true)) + (M.stale ? '. Last refresh failed, showing the earlier file.' : '.') : '') + '</p>' +
      '<details class="sv2-rec-mgd"><summary>What the Move grade means</summary><ul class="sv2-rec-note">' +
      '<li>A: a market-move flag fired toward the play and the move passed the top mark, a size only the largest moves on the tape through Nov 23 reach in that sport and market.</li>' +
      '<li>B: a market-move flag fired toward the play: Pinnacle\'s price, or the market\'s number (the books\' price on a moneyline).</li>' +
      '<li>C: no flag fired, but Pinnacle\'s price or line drifted toward the play by more than a typical day\'s move, and not that far the other way.</li>' +
      '<li>D: the market did not move toward the play by more than a typical day\'s move.</li>' +
      '<li>Moved against: a market-move flag fired against the play. It is shown instead of a letter.</li>' +
      '<li>No grade: neither flag could be read at the freeze.</li>' +
      '<li>Marks are set from the size of 24 hour moves on every started game on the tape through Nov 23, per sport and market (the cutoffs are frozen from it), not from results.</li></ul></details>';
    return html + sw + note + tbl + foot + '</section>';
  }

  /* ---- section 3: accounts record */
  var PAST_NOTE = 'These records come from games before we picked the account, so they were chosen after the fact. They have not held up going forward.';
  function acctCols(first, past) {
    var cols = mcol(first, { accts: true });
    if (past) cols.splice(cols.length, 0, { c: 'pwl', label: 'W-L', num: true, s: 1, grp: 'past' }, { c: 'prt', label: 'Win rate', num: true, s: 1, grp: 'past' }, { c: 'pn', label: 'n', num: true, s: 2, grp: 'past' });
    return cols;
  }
  function pastDetail(g) {
    var pc = rec.pastCell(g.past);
    return ['Past record, picked after the fact', pc ? num(pc.wl) + ' <span class="sv2-rec-shr">win rate ' + num(fmt.pct(pc.rate, { d: 0 })) + ', n=' + num(fmt.n(pc.n)) + '</span>' : '<span class="sv2-mut">none stored</span>', 'is-past'];
  }
  /* rows: { key, name, label (html), accounts, g (aggregate), past } */
  function acctTable(tid, label, firstCol, models, o) {
    var cols = acctCols(firstCol, o.past), C = byC(cols), ncol = cols.length + 1;
    var order = rec.sortRows(models.map(function (m, i) { m.idx = i; m.t = rec.asTally(m.g); return m; }), S.sort[tid]);
    var rows = order.map(function (m) {
      var g = m.g, t = m.t, fl = flagHtml(t);
      var acN = '<span class="sv2-num">' + esc(fmt.n(g.accounts)) + '</span>' + (isNum(g.active) ? '<span class="sv2-tb-sub">' + esc(fmt.n(g.active)) + ' with bets</span>' : '');
      var pc = o.past ? rec.pastCell(g.past) : null, pastCells = '';
      if (o.past) pastCells = (pc ? cell(C.pwl, num(pc.wl), { cls: 'sv2-rec-pst' }) + cell(C.prt, num(fmt.pct(pc.rate, { d: 0 })), { cls: 'sv2-rec-pst' }) + cell(C.pn, num(fmt.n(pc.n)), { cls: 'sv2-rec-pst' })
        : cell(C.pwl, '<span aria-hidden="true">-</span><span class="sv2-sr">No past record stored</span>', { cls: 'sv2-rec-pst' }) + cell(C.prt, '<span aria-hidden="true">-</span>', { cls: 'sv2-rec-pst' }) + cell(C.pn, '<span aria-hidden="true">-</span>', { cls: 'sv2-rec-pst' }));
      var cells = labCell(C.lab, m.label, fl) + cell(C.ac, acN) + tallyCells(C, t, 'bet') + pastCells;
      return rowHtml({ tid: tid, key: m.key, ncol: ncol, label: m.name + ', detail', attrs: m.attrs || '', cells: cells,
        detail: dl([['Accounts', num(fmt.n(g.accounts)) + (isNum(g.active) ? ' <span class="sv2-rec-shr">' + esc(fmt.n(g.active)) + ' with bets</span>' : '')], ['n', num(fmt.n(t.n))], ['vs the close', clvDetail(t, 'bet')]].concat(o.past ? [pastDetail(g)] : [])) });
    }).join('');
    return tableHtml(tid, label, cols, rows, o.past ? [{ span: 1, sr: 'Account tier' }, { span: cols.length - 4, label: 'Forward, since first tracked' }, { span: 3, label: 'Past record, picked after the fact', cls: 'is-past' }, { span: 1, sr: 'Details' }] : null);
  }
  function acctsSection(sport) {
    var f = store.wallets, html = '<section class="sv2-rec-sec" aria-labelledby="rec-h-accts">' + head('rec-h-accts', 'Accounts record', 'Forward since each account was first tracked, apart from its past record');
    if (!f) return html + '<p class="sv2-empty-line">' + (store.state.wallets === 'loading' ? 'Loading accounts.' : 'Could not load the accounts file.') + '</p></section>';
    var a = rec.acctAgg(f, sport);
    if (!a.total.accounts) return html + '<p class="sv2-empty-line">No accounts for ' + esc(sportName(sport)) + '.</p></section>';
    var tiers = copy.acctOrder.map(function (t) { var g = a.tiers[t]; return g && g.accounts ? { key: t, name: copy.acct[t].word, label: ui.acct(t), g: g, attrs: ' data-acct="' + t + '"' } : null; }).filter(Boolean);
    if (!a.fwdPub) {
      html += '<p class="sv2-empty-line">The forward record is not published yet.</p>';
      /* no forward columns: the past record alone, as before */
      return html + '<h3 class="sv2-rec-h3">Past record, picked after the fact</h3><p class="sv2-rec-note">' + PAST_NOTE + '</p>' + pastOnlyTable(tiers) + '</section>';
    }
    var tt = rec.asTally(a.total);
    html += '<div class="sv2-card sv2-rec-hero">' + stat('Units', unitsHtml(tt)) + stat('ROI', roiHtml(tt)) + stat('Record', num(wl(tt)), 'n=' + num(fmt.n(tt.n))) + '</div>' +
      '<p class="sv2-rec-line">' + flagHtml(tt) + ' <span class="sv2-rec-clv">' + esc(clvText(tt, 'bet')) + '</span></p>' +
      '<p class="sv2-rec-note">Flat 1u on each bet at the account\'s own price. Accounts are counted once per sport. Accounts reach this list after a good run, and a bet placed before an account was added can settle after it, so read this as context, not a test. ' + (isNum(a.total.pnl) && a.total.n ? 'In dollars at their own stake sizes: <span class="sv2-num' + signCls(a.total.pnl) + '">' + esc(fmt.usd(a.total.pnl, { full: true })) + '</span>, which a few large accounts drive.' : '') + '</p>';
    html += '<h3 class="sv2-rec-h3">By account tier</h3>' + acctTable('acct', 'By account tier', 'Account tier', tiers, { past: true }) + '<p class="sv2-rec-note">' + PAST_NOTE + '</p>';
    if (sport === 'all') {
      var bs = SPORT_ORDER.filter(function (s) { return a.bySport[s] && a.bySport[s].accounts; }).map(function (s) { return { key: s, name: sportName(s), label: esc(sportName(s)), g: a.bySport[s] }; });
      if (bs.length) html += '<h3 class="sv2-rec-h3">By sport</h3>' + acctTable('asport', 'By sport', 'Sport', bs, { past: false });
    }
    return html + '</section>';
  }
  /* the past record when no forward record is published: tier, W-L, win rate, n */
  function pastOnlyTable(tiers) {
    var cols = [{ c: 'lab', label: 'Account tier' }, { c: 'pwl', label: 'W-L', num: true, p: true }, { c: 'prt', label: 'Win rate', num: true, p: true }, { c: 'pn', label: 'n', num: true, p: true }], C = byC(cols);
    var rows = tiers.map(function (m) {
      var pc = rec.pastCell(m.g.past); if (!pc) return '';
      return '<tr class="sv2-tb-r sv2-rec-flat"' + m.attrs + '>' + labCell(C.lab, m.label, '') + cell(C.pwl, num(pc.wl)) + cell(C.prt, num(fmt.pct(pc.rate, { d: 0 }))) + cell(C.pn, num(fmt.n(pc.n))) + '</tr>';
    }).join('');
    return tableHtml('past', 'Past record', cols, rows);
  }

  /* ---- the page */
  function sportStrip() {
    if (SV2.hostSport() != null) return '';
    var items = [{ v: 'all', label: 'All' }].concat(SPORT_ORDER.map(function (s) { return { v: s, label: sportName(s) }; }));
    return '<div class="sv2-rec-sports">' + seg.html({ id: 'rec-sport', label: 'Sport', value: S.sport, size: 'sm', scroll: true, items: items }) + '</div>';
  }
  function freshLine() {
    var f = S.file, t = f && isNum(f.generated) ? f.generated : null;
    return '<p class="sv2-rec-fresh">' + (t != null ? 'Record updated ' + esc(ct.md(t) + ', ' + ct.time(t, true)) + (S.stale ? '. Last refresh failed, showing the earlier file.' : '.') : '') +
      ' Context only. ' + esc(copy.play.label.charAt(0).toUpperCase() + copy.play.label.slice(1)) + ': the size is a flat 1u.</p>';
  }
  function paint() {
    if (!S.page || !document.contains(S.page)) return;
    var sport = sportNow();
    if (S.state === 'loading' || (S.state === 'idle' && S.view === 'record')) { S.page.innerHTML = ui.skel(3, 'Loading the record'); return; }
    if (S.state === 'none') { S.page.innerHTML = '<div class="sv2-rec"><p class="sv2-err">Could not load the record. <button type="button" class="sv2-link" data-sv2-rec-retry>Try again</button></p>' + (S.tier.data ? tiersSection(sport) : '') + '</div>'; bindTier(); return; }
    if (S.state !== 'ok') return;
    var secs = pageNow() === 'following' ? [acctsSection, playsSection, tiersSection, mgSection] : [playsSection, tiersSection, mgSection, acctsSection];
    S.page.innerHTML = '<div class="sv2-rec">' + sportStrip() + freshLine() + secs.map(function (f) { return f(sport); }).join('') + '</div>';
    if (SV2.rail && SV2.rail.scan) SV2.rail.scan(S.page);
    var st = S.page.querySelector('.sv2-rec-sports .sv2-seg'); if (st) seg.bind(st, function (v) { S.sport = v; paint(); });
    bindTier(); scrollToTier();
  }
  function bindTier() {
    var b = S.page && S.page.querySelector('.sv2-rec-tsw .sv2-seg');
    if (b) seg.bind(b, function (v) { S.tb = v; S.tSince = false; paint(); });
    var m = S.page && S.page.querySelector('.sv2-rec-mgsw .sv2-seg');
    if (m) seg.bind(m, function (v) { S.mgb = v; paint(); });
  }
  function paintSwitch() {
    if (!S.sw) return;
    var pg = pageNow();
    if (S.swPage !== pg) {
      S.swPage = pg;
      S.sw.innerHTML = seg.html({ id: 'rec-view', label: 'View', value: S.view, size: '', fluid: true, items: [{ v: 'main', label: pg === 'following' ? 'Accounts' : 'Plays' }, { v: 'record', label: 'Record' }] });
      var st = S.sw.querySelector('.sv2-seg'); seg.bind(st, function (v) { setView(v); });
    } else seg.set(S.sw.querySelector('.sv2-seg'), S.view);
  }
  function setView(v) {
    S.view = v;
    if (S.main) S.main.setAttribute('data-view', v);
    if (S.page) S.page.hidden = v !== 'record';
    if (v === 'record') { if (S.state === 'idle') S.state = 'loading'; paint(); load(false); }
    var live = document.getElementById('sv2-live'); if (live) live.textContent = v === 'record' ? 'Record' : (pageNow() === 'following' ? 'Accounts' : 'Plays');
  }

  /* the Sharps rail TIERS card links here: switch to the Record view and bring the tier table into view */
  function scrollToTier() {
    if (!S.toTier) return;
    var h = document.getElementById('rec-h-tiers'); if (!h) return;   /* the record is still loading: paint() calls this again */
    S.toTier = false;
    try { h.scrollIntoView({ block: 'start' }); } catch (e) { /* ignore */ }
  }
  rec.openRecord = function () {
    if (!S.main || !document.contains(S.main)) return;
    paintSwitch(); S.toTier = true; setView('record'); paintSwitch();
    scrollToTier();
    var b = S.sw && S.sw.querySelector('button[aria-pressed="true"]'); if (b) { try { b.focus({ preventScroll: true }); } catch (e2) { /* ignore */ } }
  };

  /* called after boot by embed.js and by the standalone page; safe to call again (one wiring per #sv2-main) */
  rec.init = function () {
    var main = document.getElementById('sv2-main'); if (!main) return;
    var page = document.getElementById('sv2-page-record'), sw = document.getElementById('sv2-rec-sw');
    if (!page || !sw) return;
    if (S.main !== main) { S.main = main; S.page = page; S.sw = sw; S.swPage = null; S.view = 'main'; main.setAttribute('data-view', 'main'); page.hidden = true; }
    paintSwitch();
    loadTier(false);
    loadMg(false);
    if (!rec._wired) {
      rec._wired = true;
      SV2.on('sport', function () { if (S.view === 'record') paint(); });
      SV2.on('wallets', function () { if (S.view === 'record' && S.state === 'ok') paint(); });
      SV2.on('route', function () { if (S.main && document.contains(S.main)) { paintSwitch(); if (S.view === 'record') paint(); } });
      SV2.on('refresh', function () { if (S.view === 'record' || document.querySelector('[data-sv2-fz]')) { load(true).then(function () { S.tl.loadedAt = 0; loadTl(true); }); } });
      document.addEventListener('click', function (e) {
        var t = e.target; if (!t || !t.closest) return;
        if (t.closest('[data-sv2-fz-retry]')) { S.state = 'loading'; paintFrozen('[data-sv2-fz-retry]'); load(true); return; }
        if (t.closest('[data-sv2-fz-more]')) { S.fz.open = !S.fz.open; paintFrozen('[data-sv2-fz-more]'); return; }
        if (t.closest('[data-sv2-rec-retry]')) { S.state = 'loading'; if (!S.tier.data) S.tier.state = 'loading'; paint(); load(true); return; }
        var so = t.closest('[data-sv2-rsort]');
        if (so && S.page && S.page.contains(so)) {
          var sp2 = so.getAttribute('data-sv2-rsort').split(':'), tid = sp2[0];
          S.sort[tid] = rec.nextSort(S.sort[tid], sp2[1]); paint();
          var again2 = S.page.querySelector('[data-sv2-rsort="' + so.getAttribute('data-sv2-rsort') + '"]'); if (again2) { try { again2.focus({ preventScroll: true }); } catch (e3) { /* ignore */ } }
          var live = document.getElementById('sv2-live'); if (live) live.textContent = 'Sorted by ' + rec.sortWord(S.sort[tid]);
          return;
        }
        var tr = t.closest('tr.sv2-tb-r');   /* the whole row toggles; the chevron button is the keyboard and screen reader control */
        if (tr && S.page && S.page.contains(tr) && !t.closest('a, button:not(.sv2-tb-tog), .sv2-link')) {
          var btn = tr.querySelector('[data-sv2-rx]'), box = btn && document.getElementById(btn.getAttribute('data-sv2-rx'));
          if (!box) return;
          var open = !box.hasAttribute('data-open');
          if (open) { box.setAttribute('data-open', ''); tr.classList.add('is-open'); } else { box.removeAttribute('data-open'); tr.classList.remove('is-open'); }
          btn.setAttribute('aria-expanded', String(open)); S.open[box.id] = open; return;
        }
        var sn = t.closest('[data-sv2-tt-since]');
        if (sn && S.page && S.page.contains(sn)) { S.tSince = !S.tSince; paint(); var again = S.page.querySelector('[data-sv2-tt-since]'); if (again) { try { again.focus({ preventScroll: true }); } catch (er) { /* ignore */ } } return; }
        if (t.closest('[data-sv2-open-record]')) { e.preventDefault(); rec.openRecord(); }
      });
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(rec.init, 0); }); else setTimeout(rec.init, 0);
})();
