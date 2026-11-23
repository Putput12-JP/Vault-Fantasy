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
  rec.FWD_CUT = FWD_CUT; rec.FIRST_MONTH = FIRST_MONTH; rec.NEED_N = NEED_N; rec.SMALL_N = SMALL_N; rec.TIER_NONE = TIER_NONE; rec.declared = declared;
  SV2.rec = rec;

  /* ------------------------------------------------------------------ browser side */
  if (typeof document === 'undefined') return;
  var S = { sport: 'all', view: 'main', file: null, rows: null, state: 'idle', loadedAt: 0, main: null, page: null, sw: null, swPage: null, busy: false };

  function get(p, txt, force) {
    var k = force ? Date.now() : Math.floor(Date.now() / 300000);
    return fetch(BASE + p + '?t=' + k, { cache: force ? 'no-store' : 'default' })
      .then(function (r) { return r.ok ? (txt ? r.text() : r.json()) : null; }).catch(function () { return null; });
  }
  function load(force) {
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

  /* ---- section 2: tier record (play evidence tiers) */
  function tiersSection(sport) {
    var tr = rec.tierRecord(S.rows || [], S.file, sport, S.closes);
    var html = '<section class="sv2-card sv2-rec-sec" aria-labelledby="rec-h-tiers">' + head('rec-h-tiers', 'Tier record', 'Clear, Mixed, Thin and Contested plays, read apart');
    if (!tr) return html + '<p class="sv2-empty-line">' + esc(TIER_NONE) + '</p><p class="sv2-rec-note">The tier is a label of the facts stored for and against a play. It is never worked out afterwards for plays already played.</p></section>';
    var rs = copy.tierOrder.map(function (t) {
      var tt = tr.byTier[t]; if (!tt || !tt.n) return '';
      return row(ui.tier(t), tt);
    }).join('');
    return html + (rs ? table('Tier record', rs) : '<p class="sv2-empty-line">No graded plays with a tier yet.</p>') +
      '<p class="sv2-rec-note">Tiers do not change the size, which stays a flat 1u (' + esc(copy.play.label) + ').</p></section>';
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
    if (S.state === 'none') { S.page.innerHTML = '<p class="sv2-err">Could not load the record. <button type="button" class="sv2-link" data-sv2-rec-retry>Try again</button></p>'; return; }
    if (S.state !== 'ok') return;
    var secs = pageNow() === 'following' ? [acctsSection, playsSection, tiersSection] : [playsSection, tiersSection, acctsSection];
    S.page.innerHTML = '<div class="sv2-rec">' + sportStrip() + freshLine() + secs.map(function (f) { return f(sport); }).join('') + '</div>';
    if (SV2.rail && SV2.rail.scan) SV2.rail.scan(S.page);
    var st = S.page.querySelector('.sv2-rec-sports .sv2-seg'); if (st) seg.bind(st, function (v) { S.sport = v; paint(); });
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

  /* called after boot by embed.js and by the standalone page; safe to call again (one wiring per #sv2-main) */
  rec.init = function () {
    var main = document.getElementById('sv2-main'); if (!main) return;
    var page = document.getElementById('sv2-page-record'), sw = document.getElementById('sv2-rec-sw');
    if (!page || !sw) return;
    if (S.main !== main) { S.main = main; S.page = page; S.sw = sw; S.swPage = null; S.view = 'main'; main.setAttribute('data-view', 'main'); page.hidden = true; }
    paintSwitch();
    if (!rec._wired) {
      rec._wired = true;
      SV2.on('sport', function () { if (S.view === 'record') paint(); });
      SV2.on('wallets', function () { if (S.view === 'record' && S.state === 'ok') paint(); });
      SV2.on('route', function () { if (S.main && document.contains(S.main)) { paintSwitch(); if (S.view === 'record') paint(); } });
      SV2.on('refresh', function () { if (S.view === 'record') load(true); });
      document.addEventListener('click', function (e) { if (e.target.closest && e.target.closest('[data-sv2-rec-retry]')) { S.state = 'loading'; paint(); load(true); } });
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(rec.init, 0); }); else setTimeout(rec.init, 0);
})();
