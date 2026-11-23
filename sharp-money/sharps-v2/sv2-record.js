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

  /* Central month keys to read: this month and the one before */
  rec.months = function (nowT) {
    var k = ct.dateKey(nowT), first = k.slice(0, 7) + '-01', prev = ct.addDays(first, -1).slice(0, 7), cur = k.slice(0, 7);
    return prev >= FIRST_MONTH ? [prev, cur] : [cur];
  };
  rec.SHADOW_SIZE = SHADOW_SIZE; rec.SHADOW_TIP = SHADOW_TIP; rec.TIER_ROWS = TIER_ROWS; rec.BUCKETS = BUCKETS; rec.TIER_FOOT = TIER_FOOT; rec.FWD_CUT = FWD_CUT; rec.FIRST_MONTH = FIRST_MONTH; rec.NEED_N = NEED_N; rec.SMALL_N = SMALL_N; rec.TIER_NONE = TIER_NONE; rec.declared = declared;
  SV2.rec = rec;

  /* ------------------------------------------------------------------ browser side */
  if (typeof document === 'undefined') return;
  var S = { sport: 'all', view: 'main', file: null, rows: null, state: 'idle', loadedAt: 0, main: null, page: null, sw: null, swPage: null, busy: false,
    tier: { data: null, state: 'idle', loadedAt: 0, stale: false, busy: null }, tb: 'all', tSince: false, tOpen: {} };

  function get(p, txt, force) {
    var k = force ? Date.now() : Math.floor(Date.now() / 300000);
    return fetch(BASE + p + '?t=' + k, { cache: force ? 'no-store' : 'default' })
      .then(function (r) { return r.ok ? (txt ? r.text() : r.json()) : null; }).catch(function () { return null; });
  }
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
  function load(force) {
    loadTier(force);
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
      S.busy = false; paint();
    });
    return S.busy;
  }

  function sportNow() { var h = SV2.hostSport(); return h != null ? h : S.sport; }
  function pageNow() { return SV2.route().page === 'following' ? 'following' : 'sharps'; }

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
  /* one row of a record table: label, record, units, ROI; then CLV and flags */
  function row(label, t, o) {
    var clv = o && o.noClv ? '' : '<span class="sv2-rec-clv">' + esc(clvText(t, o && o.unit)) + '</span>';
    return '<li class="sv2-rec-row"><div class="sv2-rec-lab">' + label + '<span class="sv2-rec-n">n=' + num(fmt.n(t.n)) + '</span></div>' +
      '<div class="sv2-rec-c" data-k="W-L">' + num(wl(t)) + '</div><div class="sv2-rec-c" data-k="Units">' + unitsHtml(t) + '</div><div class="sv2-rec-c" data-k="ROI">' + roiHtml(t) + '</div>' +
      '<div class="sv2-rec-x">' + flagHtml(t) + clv + '</div></li>';
  }
  function table(label, rowsHtml) {
    return '<div class="sv2-rec-tbl" role="group" aria-label="' + esc(label) + '"><div class="sv2-rec-th" aria-hidden="true"><span></span><span>W-L</span><span>Units</span><span>ROI</span></div><ul class="sv2-rec-list">' + rowsHtml + '</ul></div>';
  }
  function stat(label, valueHtml, note) {
    return '<div class="sv2-rec-stat"><span class="sv2-rec-k">' + esc(label) + '</span><span class="sv2-rec-v">' + valueHtml + '</span>' + (note ? '<span class="sv2-rec-kn">' + note + '</span>' : '') + '</div>';
  }

  /* ---- section 1: plays record */
  function playsSection(sport) {
    var all = rec.playRows(S.rows || [], sport), t = rec.tally(all, S.closes), sp = rec.splitForward(all, FWD_CUT);
    var tf = rec.tally(sp.forward, S.closes), ti = rec.tally(sp.in_sample, S.closes);
    var tracked = sport === 'cfb';
    var html = '<section class="sv2-card sv2-rec-sec" aria-labelledby="rec-h-plays">' +
      head('rec-h-plays', 'Plays record', tracked ? 'CFB shows no size. This is a tracked record at a flat 1u, not a shown play.' : 'The shown plays at a flat 1u ' + pill()) ;
    if (!t.n) {
      return html + '<p class="sv2-empty-line">No graded plays yet for ' + esc(sport === 'all' ? 'these sports' : sportName(sport)) + '.</p></section>';
    }
    html += '<div class="sv2-card-inset sv2-rec-hero">' +
      stat('Units', unitsHtml(t)) + stat('ROI', roiHtml(t)) + stat('Record', num(wl(t)), 'n=' + num(fmt.n(t.n))) + '</div>' +
      '<p class="sv2-rec-line">' + flagHtml(t) + ' <span class="sv2-rec-clv">' + esc(clvText(t)) + '</span></p>' +
      (rec.seNote(t) ? '<p class="sv2-rec-note">' + esc(rec.seNote(t)) + '</p>' : '') +
      '<p class="sv2-rec-note">A record is context, not proof. It is a shadow test of an untested rule.</p>';
    /* forward and in-sample, read apart */
    html += '<h3 class="sv2-rec-h3">Forward and in-sample</h3><div class="sv2-rec-two">' +
      '<div class="sv2-card-inset"><p class="sv2-rec-k">Forward</p><p class="sv2-rec-kn">Cut from ' + esc(ct.md(FWD_CUT) + ', ' + ct.time(FWD_CUT, true)) + '</p>' + (tf.n ? table('Forward', row('Forward', tf)) : '<p class="sv2-empty-line">No graded forward plays yet.</p>') + '</div>' +
      '<div class="sv2-card-inset"><p class="sv2-rec-k">In-sample</p><p class="sv2-rec-kn">Cut before that. Read it as history, not a test.</p>' + (ti.n ? table('In-sample', row('In-sample', ti)) : '<p class="sv2-empty-line">None.</p>') + '</div></div>';
    /* by sport (all) and by market */
    if (sport === 'all') {
      var rs = SHOWN.concat(['cfb']).map(function (s) {
        var tt = rec.tally(rec.playRows(S.rows || [], s), S.closes);
        return tt.n ? row(sportName(s) + (s === 'cfb' ? ' <span class="sv2-rec-tag">no size shown</span>' : ''), tt) : '';
      }).join('');
      if (rs) html += '<h3 class="sv2-rec-h3">By sport</h3>' + table('By sport', rs);
    }
    var ms = MARKETS.map(function (m) {
      var tt = rec.tally(all.filter(function (r) { return r.group === m[0]; }), S.closes);
      return tt.n ? row(m[1], tt) : '';
    }).join('');
    if (ms) html += '<h3 class="sv2-rec-h3">By market</h3>' + table('By market', ms);
    /* latest graded */
    var lat = rec.latest(all, 12);
    html += '<h3 class="sv2-rec-h3">Latest graded plays</h3><ul class="sv2-rec-plays">' + lat.map(function (r) {
      var res = r.res === 'win' ? 'sv2-chip--win' : r.res === 'loss' ? 'sv2-chip--loss' : 'sv2-chip--muted';
      var word = r.res === 'win' ? 'Win' : r.res === 'loss' ? 'Loss' : 'Push';
      var c = S.closes && S.closes[r.key];
      return '<li class="sv2-rec-play"><div class="sv2-rec-pl"><b>' + esc(rec.playLabel(r)) + '</b><span class="sv2-rec-pm">' + esc(sportName(r.sport)) + ' ' + esc(r.group) +
        (isNum(r.gst) ? ', ' + esc(ct.md(r.gst)) : '') + (isNum(r.price) ? ', ' + esc(fmt.cents(r.price)) : '') + (c ? ', close ' + esc(fmt.centsSigned(c.clv)) : '') + '</span></div>' +
        '<span class="sv2-chip ' + res + '"><span>' + word + '</span></span><span class="sv2-num sv2-rec-pu' + signCls(r.flat) + '">' + esc(fmt.units(r.flat, { signed: true }) || '') + '</span></li>';
    }).join('') + '</ul>';
    return html + '</section>';
  }

  /* ---- section 2: tier record (evidence tiers), from tier_record.json */
  function tUnits(t) { return '<span class="sv2-num' + signCls(t.units) + '">' + esc(rec.fmtUnits(t)) + '</span>'; }
  function tRoi(t) { return '<span class="sv2-num' + signCls(t.roi) + '">' + esc(rec.fmtRoi(t)) + '</span>'; }
  /* shadow cells: muted and tagged, never coloured as a result. Size, then units with the ROI on staked units. */
  function shCells(size, sh) {
    var ss = rec.fmtSize(size), un = rec.fmtShadowUnits(sh), ro = rec.fmtShadowRoi(sh), st = rec.fmtStaked(sh);
    return '<span class="sv2-rec-shw">' +
      '<span class="sv2-rec-c sv2-rec-sh" data-k="Shadow size" data-m="size" title="' + esc(rec.SHADOW_TIP) + '"><span class="sv2-sr">Shadow size, </span>' + num(ss) + '</span>' +
      '<span class="sv2-rec-c sv2-rec-sh" data-k="Shadow units" data-m="units" title="' + esc(rec.SHADOW_TIP + (st !== '-' ? ' Staked ' + st + '.' : '')) + '"><span class="sv2-sr">Shadow units and ROI on staked units, </span>' +
      num(un) + (ro !== '-' ? ' <span class="sv2-rec-shr">' + esc(ro) + '</span>' : '') + '</span></span>';
  }
  function tCells(t) {
    return '<span class="sv2-rec-c" data-k="W-L">' + num(rec.fmtWl(t)) + '</span><span class="sv2-rec-c" data-k="Units">' + tUnits(t) + '</span>' +
      '<span class="sv2-rec-c" data-k="ROI">' + tRoi(t) + '</span><span class="sv2-rec-c" data-k="n">' + num(fmt.n(t.n)) + '</span>';
  }
  function tLabel(r) {
    return r.derived ? ui.tier(r.tier) : '<span class="sv2-chip sv2-chip--muted" data-tier="none"><span>Not derivable</span></span>';
  }
  function tierRow(r) {
    var open = !!S.tOpen[r.tier], id = 'sv2-tt-' + r.tier, hasX = !!r.markets;
    var head = '<span class="sv2-rec-tl">' + tLabel(r) + (r.derived ? '' : '<span class="sv2-rec-tag">no stored facts at the cut</span>') + '</span>' + tCells(r.t) + shCells(r.size, r.shadow);
    var share = r.share == null ? 0 : r.share * 100;
    var line = '<span class="sv2-rec-tx">' + flagHtml(r.t) +
      '<span class="sv2-rec-share"><span class="sv2-rec-bar" data-tier="' + r.tier + '" aria-hidden="true"><i style="width:' + share.toFixed(1) + '%"></i></span>' +
      '<span class="sv2-rec-sharet">' + (r.share == null ? 'no plays' : esc(fmt.pct(r.share, { d: 0 })) + ' of the total') + '</span></span></span>';
    var inner = head + line;
    var top = hasX
      ? '<button type="button" class="sv2-rec-tbtn sv2-press sv2-press-row" data-sv2-tt-x="' + r.tier + '" aria-expanded="' + open + '" aria-controls="' + id + '">' + inner + '<span class="sv2-rec-tchev" aria-hidden="true">' + ui.icon('chevron', 'sv2-chev') + '</span><span class="sv2-sr">By market</span></button>'
      : '<div class="sv2-rec-tbtn sv2-rec-tbtn--flat">' + inner + '</div>';
    var sub = '';
    if (hasX) {
      sub = '<div class="sv2-x" id="' + id + '"' + (open ? ' data-open' : '') + '><div class="sv2-x-in" role="region" aria-label="' + esc((r.derived ? copy.tier[r.tier].word : 'Not derivable') + ' by market') + '"><ul class="sv2-rec-sub">' +
        r.markets.map(function (m) { return '<li class="sv2-rec-subrow"><span class="sv2-rec-tl">' + esc(m.label) + '</span>' + tCells(m.t) + shCells(r.size, m.shadow) + '</li>'; }).join('') + '</ul></div></div>';
    }
    return '<li class="sv2-rec-trow" data-tier="' + r.tier + '">' + top + sub + '</li>';
  }
  function tiersSection(sport) {
    var T = S.tier, html = '<section class="sv2-card sv2-rec-sec" aria-labelledby="rec-h-tiers">' + head('rec-h-tiers', 'Tier record', 'Each tier read apart, at a flat 1u');
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
      note = '<div class="sv2-card-inset sv2-rec-tnote"><p class="sv2-rec-note"><b>Forward.</b> ' + esc(fn.charAt(0).toUpperCase() + fn.slice(1)) + '. ' +
        (tb.total.n ? '' : 'No tier has been logged at a lock and graded yet, so every row below is zero. Zero is not a record.') +
        ' Logged rows so far: <span class="sv2-num">' + esc(fmt.n(isNum(f.logged_rows) ? f.logged_rows : 0)) + '</span>.</p></div>';
    } else if (bucket === 'since_nov16') {
      note = '<div class="sv2-card-inset sv2-rec-tnote"><p class="sv2-rec-note"><b>Informational only.</b> These are plays cut on or after Nov 16, 12:00 AM Central. Their tier was derived after the fact, so this is not forward.</p></div>';
    } else if (bucket === 'in_sample') {
      note = '<div class="sv2-card-inset sv2-rec-tnote"><p class="sv2-rec-note"><b>In-sample.</b> The tier rule was written after these results. Read it as history, not a test.</p></div>';
    }
    var hero = tb.derived.n ? '<div class="sv2-card-inset sv2-rec-hero">' + stat('Units', tUnits(tb.derived)) + stat('ROI', tRoi(tb.derived)) + stat('Record', num(rec.fmtWl(tb.derived)), 'n=' + num(fmt.n(tb.derived.n)) + ', tiers only') + '</div>' : '';
    var th = '<div class="sv2-rec-th sv2-rec-tth" aria-hidden="true"><span></span><span>W-L</span><span>Units</span><span>ROI</span><span>n</span><span class="sv2-rec-shh"><i class="sv2-rec-shtag" title="' + esc(rec.SHADOW_TIP) + '">shadow</i>Size</span><span class="sv2-rec-shh"><i class="sv2-rec-shtag" title="' + esc(rec.SHADOW_TIP) + '">shadow</i>Units, ROI</span></div>';
    var tbl = '<div class="sv2-rec-tbl sv2-rec-ttbl" role="group" aria-label="Tier record, ' + esc(BUCKET_NAME[bucket]) + '">' + th + '<ul class="sv2-rec-list">' + tb.rows.map(tierRow).join('') + '</ul></div>';
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

  /* ---- section 3: accounts record */
  function acctsSection(sport) {
    var f = store.wallets, html = '<section class="sv2-card sv2-rec-sec" aria-labelledby="rec-h-accts">' + head('rec-h-accts', 'Accounts record', 'Forward since each account was first tracked, apart from its past record');
    if (!f) return html + '<p class="sv2-empty-line">' + (store.state.wallets === 'loading' ? 'Loading accounts.' : 'Could not load the accounts file.') + '</p></section>';
    var a = rec.acctAgg(f, sport);
    if (!a.total.accounts) return html + '<p class="sv2-empty-line">No accounts for ' + esc(sportName(sport)) + '.</p></section>';
    if (!a.fwdPub) html += '<p class="sv2-empty-line">The forward record is not published yet.</p>';
    else {
      var tt = rec.asTally(a.total);
      html += '<div class="sv2-card-inset sv2-rec-hero">' + stat('Units', unitsHtml(tt)) + stat('ROI', roiHtml(tt)) + stat('Record', num(wl(tt)), 'n=' + num(fmt.n(tt.n))) + '</div>' +
        '<p class="sv2-rec-line">' + flagHtml(tt) + ' <span class="sv2-rec-clv">' + esc(clvText(tt, 'bet')) + '</span></p>' +
        '<p class="sv2-rec-note">Flat 1u on each bet at the account\'s own price. Accounts are counted once per sport. Accounts reach this list after a good run, and a bet placed before an account was added can settle after it, so read this as context, not a test. ' + (isNum(a.total.pnl) && a.total.n ? 'In dollars at their own stake sizes: <span class="sv2-num' + signCls(a.total.pnl) + '">' + esc(fmt.usd(a.total.pnl, { full: true })) + '</span>, which a few large accounts drive.' : '') + '</p>';
      var rs = copy.acctOrder.map(function (t) {
        var g = a.tiers[t]; if (!g || !g.accounts) return '';
        var tl = rec.asTally(g);
        return row(ui.acct(t) + ' <span class="sv2-rec-tag">' + fmt.n(g.accounts) + ' accounts, ' + fmt.n(g.active) + ' with bets</span>', tl, { unit: 'bet' });
      }).join('');
      html += '<h3 class="sv2-rec-h3">By account tier</h3>' + table('By account tier', rs);
      if (sport === 'all') {
        var bs = SPORT_ORDER.filter(function (s) { return a.bySport[s] && a.bySport[s].accounts; }).map(function (s) {
          var g = a.bySport[s]; return row(esc(sportName(s)) + ' <span class="sv2-rec-tag">' + fmt.n(g.accounts) + ' accounts</span>', rec.asTally(g), { unit: 'bet' });
        }).join('');
        if (bs) html += '<h3 class="sv2-rec-h3">By sport</h3>' + table('By sport', bs);
      }
    }
    /* the past record, apart */
    var past = copy.acctOrder.map(function (t) {
      var g = a.tiers[t]; if (!g || !g.past.n) return '';
      var wr = g.past.n ? g.past.w / g.past.n : null;
      return '<li class="sv2-rec-row sv2-rec-row--past"><div class="sv2-rec-lab">' + ui.acct(t) + '<span class="sv2-rec-n">n=' + num(fmt.n(g.past.n)) + '</span></div>' +
        '<div class="sv2-rec-c" data-k="W-L">' + num(fmt.wl(g.past.w, g.past.l)) + '</div><div class="sv2-rec-c" data-k="Win rate">' + (wr != null ? num(fmt.pct(wr, { d: 0 })) : '') + '</div></li>';
    }).join('');
    html += '<h3 class="sv2-rec-h3">Past record, picked after the fact</h3><div class="sv2-card-inset"><p class="sv2-rec-note">These records come from games before we picked the account, so they were chosen after the fact. They have not held up going forward.</p>' +
      '<div class="sv2-rec-tbl sv2-rec-tbl--past" role="group" aria-label="Past record"><div class="sv2-rec-th" aria-hidden="true"><span></span><span>W-L</span><span>Win rate</span></div><ul class="sv2-rec-list">' + past + '</ul></div></div>';
    return html + '</section>';
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
    var secs = pageNow() === 'following' ? [acctsSection, playsSection, tiersSection] : [playsSection, tiersSection, acctsSection];
    S.page.innerHTML = '<div class="sv2-rec">' + sportStrip() + freshLine() + secs.map(function (f) { return f(sport); }).join('') + '</div>';
    if (SV2.rail && SV2.rail.scan) SV2.rail.scan(S.page);
    var st = S.page.querySelector('.sv2-rec-sports .sv2-seg'); if (st) seg.bind(st, function (v) { S.sport = v; paint(); });
    bindTier(); scrollToTier();
  }
  function bindTier() {
    var b = S.page && S.page.querySelector('.sv2-rec-tsw .sv2-seg');
    if (b) seg.bind(b, function (v) { S.tb = v; S.tSince = false; paint(); });
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
    if (!rec._wired) {
      rec._wired = true;
      SV2.on('sport', function () { if (S.view === 'record') paint(); });
      SV2.on('wallets', function () { if (S.view === 'record' && S.state === 'ok') paint(); });
      SV2.on('route', function () { if (S.main && document.contains(S.main)) { paintSwitch(); if (S.view === 'record') paint(); } });
      SV2.on('refresh', function () { if (S.view === 'record') load(true); });
      document.addEventListener('click', function (e) {
        var t = e.target; if (!t || !t.closest) return;
        if (t.closest('[data-sv2-rec-retry]')) { S.state = 'loading'; if (!S.tier.data) S.tier.state = 'loading'; paint(); load(true); return; }
        var x = t.closest('[data-sv2-tt-x]');
        if (x && S.page && S.page.contains(x)) {
          var k = x.getAttribute('data-sv2-tt-x'), li = x.closest('.sv2-rec-trow'), box = li && li.querySelector('.sv2-x');
          if (!box) return;
          var open = !box.hasAttribute('data-open');
          if (open) box.setAttribute('data-open', ''); else box.removeAttribute('data-open');
          x.setAttribute('aria-expanded', String(open)); S.tOpen[k] = open; return;
        }
        var sn = t.closest('[data-sv2-tt-since]');
        if (sn && S.page && S.page.contains(sn)) { S.tSince = !S.tSince; paint(); var again = S.page.querySelector('[data-sv2-tt-since]'); if (again) { try { again.focus({ preventScroll: true }); } catch (er) { /* ignore */ } } return; }
        if (t.closest('[data-sv2-open-record]')) { e.preventDefault(); rec.openRecord(); }
      });
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(rec.init, 0); }); else setTimeout(rec.init, 0);
})();
