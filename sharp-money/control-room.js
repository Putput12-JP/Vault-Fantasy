/* Sharp Money Control Room: the operations view for the price jobs and the Sharp board.
   Same layout as Vault NBA's Control Room (nba/ui/projections.template.html). Run history comes live from
   GitHub's public Actions API (the repo is public). "Run now" goes through the sharp-refresh Worker after Turnstile.
   One module shared by the classic page and new/. */
(function (root) {
  'use strict';

  var REPO = 'Putput12-JP/Vault-Fantasy';
  var DEFAULT_WORKER = 'https://sharp-refresh.vaultfantasy.workers.dev';
  var TZ = 'America/Chicago', TZL = 'CT';
  var TICK_MIN = 10;

  var ICON = {
    pts: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/></svg>',
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/></svg>',
    edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>'
  };

  /* Cadences and cron strings match workers/sharp-refresh/src/price-jobs.js (UTC, 5 fields).
     update-sharp-money is started on every 10-minute Worker tick; the workflow gate then decides whether to run. */
  var JOBS = [
    { id: 'update-sharp-money', wf: 'update-sharp-money.yml', name: 'Sharp Money refresh',
      kind: 'sharp', cadenceSec: 10 * 60,
      how: 'The sharp-refresh Cloudflare Worker starts it on every 10-minute tick. The job then decides whether to run: busy windows (Central) Monday and Thursday 5-11pm, Saturday 10am-11pm, and Sunday 8am-8pm every 10 minutes; other days 9am-11pm every 30 minutes; plus one 6:00 AM Central run. A GitHub schedule at 3 minutes past each 10-minute mark is the backup. Run now or Refresh forces a run.' },
    { id: 'nfl-book-tape', wf: 'nfl-book-tape.yml', name: 'NFL book tape',
      crons: ['*/20 * * * *'], cadenceSec: 20 * 60,
      how: 'The sharp-refresh Cloudflare Worker starts it on its 10-minute tick whenever the old schedule is due, every 20 minutes.' },
    { id: 'update-props', wf: 'update-props.yml', name: 'PrizePicks props',
      crons: ['17 * * * *'], cadenceSec: 60 * 60,
      how: 'The Worker starts it on its 10-minute tick at :10 past each hour, for the :17 UTC slot it used to run on.' },
    { id: 'update-prop-history', wf: 'update-prop-history.yml', name: 'Prop history',
      crons: ['27 * * * *'], cadenceSec: 60 * 60,
      how: 'The Worker starts it on its 10-minute tick at :20 past each hour, for the :27 UTC slot it used to run on.' },
    { id: 'update-game-history', wf: 'update-game-history.yml', name: 'Game line history',
      crons: ['29 * * * *'], cadenceSec: 60 * 60,
      how: 'The Worker starts it on its 10-minute tick at :20 past each hour, for the :29 UTC slot it used to run on. The Sharp Money refresh also starts it when that job goes.' },
    { id: 'update-kalshi', wf: 'update-kalshi.yml', name: 'Kalshi prices',
      crons: ['37 * * * *'], cadenceSec: 60 * 60,
      how: 'The Worker starts it on its 10-minute tick at :30 past each hour, for the :37 UTC slot it used to run on.' },
    { id: 'update-polymarket', wf: 'update-polymarket.yml', name: 'Polymarket prices',
      crons: ['47 * * * *'], cadenceSec: 60 * 60,
      how: 'The Worker starts it on its 10-minute tick at :40 past each hour, for the :47 UTC slot it used to run on.' },
    { id: 'update-line-history', wf: 'update-line-history.yml', name: 'Line history',
      crons: ['47 * * * *'], cadenceSec: 60 * 60,
      how: 'The Worker starts it on its 10-minute tick at :40 past each hour, for the :47 UTC slot it used to run on.' },
    { id: 'update-lineup', wf: 'update-lineup.yml', name: 'US books (ParlayAPI)',
      crons: [
        '0 9 * 2,3,4,5,6,7,8 *',
        '0 8 * 9,10,11,12,1 *',
        '0 13,17,21 * 9,10,11,12,1 2,3,5',
        '0 16 * 9,10,11,12,1 6',
        '0 14,16,18,20,22,23 * 9,10,11,12,1 4',
        '0 13,14,15,16,18,19,20,22,23 * 9,10,11,12,1 0',
        '0 17,19,21,23 * 9,10,11,12,1 1'
      ], cadenceSec: 60 * 60,
      how: 'The Worker starts it on its 10-minute tick when the seasonal schedule is due: one morning run every day, plus extra game-day slots in season (September through January). A Refresh click can start it at most once per 45 minutes, and never past the monthly credit cap. Run now uses the same cap.' }
  ];

  var JOB_BY_WF = {};
  JOBS.forEach(function (j) { JOB_BY_WF[j.wf] = j; JOB_BY_WF[j.id] = j; });

  /* ---------- cron (same rules as workers/sharp-refresh/src/price-jobs.js) ---------- */
  var RANGES = [[0, 59], [0, 23], [1, 31], [1, 12], [0, 7]];
  function field(spec, lohi) {
    var lo = lohi[0], hi = lohi[1], out = {};
    spec.split(',').forEach(function (part) {
      var bits = part.split('/'), rng = bits[0], step = bits[1] ? +bits[1] : 1;
      var a = lo, b = hi;
      if (rng !== '*') {
        var m = rng.split('-').map(Number);
        a = m[0];
        b = m.length > 1 ? m[1] : (bits[1] ? hi : m[0]);
      }
      if (!(step > 0) || isNaN(a) || isNaN(b) || a < lo || b > hi || a > b) throw new Error('bad cron field: ' + spec);
      for (var v = a; v <= b; v += step) out[v] = 1;
    });
    return out;
  }
  function parseCron(expr) {
    var f = expr.trim().split(/\s+/);
    if (f.length !== 5) throw new Error('cron needs 5 fields: ' + expr);
    var mi = field(f[0], RANGES[0]), h = field(f[1], RANGES[1]), dom = field(f[2], RANGES[2]), mon = field(f[3], RANGES[3]), dow = field(f[4], RANGES[4]);
    if (dow[7]) dow[0] = 1;
    return { mi: mi, h: h, dom: dom, mon: mon, dow: dow, domAny: f[2] === '*', dowAny: f[4] === '*' };
  }
  function cronMatches(c, d) {
    if (!c.mi[d.getUTCMinutes()] || !c.h[d.getUTCHours()] || !c.mon[d.getUTCMonth() + 1]) return false;
    var dm = !!c.dom[d.getUTCDate()], dw = !!c.dow[d.getUTCDay()];
    return c.domAny && c.dowAny ? true : c.domAny ? dw : c.dowAny ? dm : dm || dw;
  }
  var PARSED = JOBS.map(function (j) {
    return { job: j, parsed: (j.crons || []).map(parseCron) };
  });
  function priceJobDueAtTick(job, tickMs, windowMin) {
    windowMin = windowMin == null ? TICK_MIN : windowMin;
    var start = Math.floor(tickMs / 60000) * 60000;
    var row = PARSED.filter(function (p) { return p.job.id === job.id; })[0];
    if (!row || !row.parsed.length) return false;
    for (var i = 0; i < windowMin; i++) {
      if (row.parsed.some(function (c) { return cronMatches(c, new Date(start + i * 60000)); })) return true;
    }
    return false;
  }

  /* Sharp Money gate, in Central, evaluated at the Worker tick time. */
  function chicagoParts(ms) {
    var parts = new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', hour: 'numeric', minute: 'numeric', hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit' })
      .formatToParts(new Date(ms));
    var o = {};
    parts.forEach(function (p) { o[p.type] = p.value; });
    return { weekday: o.weekday, h: +o.hour, m: +o.minute };
  }
  function sharpGateOpen(ms) {
    var p = chicagoParts(ms), d = p.weekday, h = p.h, m = p.m, go = false;
    if (d === 'Mon' || d === 'Thu') go = h >= 17 && h <= 23;
    else if (d === 'Sat') go = h >= 10 && h <= 23;
    else if (d === 'Sun') go = h >= 8 && h <= 20;
    if (h === 6 && m < 10) go = true;
    if (!go && h >= 9 && h <= 23 && (m < 10 || (m >= 30 && m < 40))) go = true;
    return go;
  }
  function jobDueAtTick(job, tickMs) {
    if (job.kind === 'sharp') return sharpGateOpen(tickMs);
    return priceJobDueAtTick(job, tickMs);
  }
  function tickFloor(ms) { return Math.floor(ms / (TICK_MIN * 60000)) * (TICK_MIN * 60000); }
  function dueTimes(job, fromMs, toMs) {
    var out = [], t0 = tickFloor(fromMs);
    for (var t = t0; t <= toMs; t += TICK_MIN * 60000) if (jobDueAtTick(job, t)) out.push(t);
    return out;
  }
  function expectedLast(job, nowMs) {
    var from = nowMs - 48 * 3600 * 1000;
    var times = dueTimes(job, from, nowMs);
    return times.length ? times[times.length - 1] : null;
  }
  function cadenceAt(job, atMs, nowMs) {
    var from = (atMs != null ? atMs : nowMs) - 48 * 3600 * 1000;
    var to = (atMs != null ? atMs : nowMs);
    var times = dueTimes(job, from, to);
    if (times.length >= 2) return (times[times.length - 1] - times[times.length - 2]) / 1000;
    return job.cadenceSec;
  }
  function isStale(job, lastOkT, nowMs) {
    nowMs = nowMs == null ? Date.now() : nowMs;
    var exp = expectedLast(job, nowMs);
    if (exp == null) return false;
    var cad = cadenceAt(job, exp, nowMs);
    if (lastOkT == null) return nowMs >= exp;
    return (nowMs / 1000 - lastOkT) > 2 * cad;
  }
  function nextDueAt(job, nowMs) {
    nowMs = nowMs == null ? Date.now() : nowMs;
    var t = tickFloor(nowMs);
    if (t < nowMs) t += TICK_MIN * 60000;
    var end = nowMs + 14 * 24 * 3600 * 1000;
    for (; t <= end; t += TICK_MIN * 60000) if (jobDueAtTick(job, t)) return t;
    return null;
  }
  function nextDueJob(nowMs) {
    nowMs = nowMs == null ? Date.now() : nowMs;
    var best = null;
    JOBS.forEach(function (j) {
      var at = nextDueAt(j, nowMs);
      if (at != null && (!best || at < best.at || (at === best.at && JOBS.indexOf(j) < JOBS.indexOf(best.job)))) best = { job: j, at: at };
    });
    return best;
  }

  /* ---------- time / copy ---------- */
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function etFmt(t, o) { return new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: TZ }, o)).format(new Date(t * 1000)); }
  function clock(t) { return etFmt(t, { hour: 'numeric', minute: '2-digit' }); }
  function stamp(t) { return etFmt(t, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); }
  function agoFrom(t, ref) {
    var s = Math.max(0, Math.round(ref - t));
    if (s < 90) return 'just now';
    if (s < 5400) return Math.round(s / 60) + ' min ago';
    if (s < 172800) return Math.round(s / 3600) + ' h ago';
    return Math.round(s / 86400) + ' days ago';
  }
  function inFrom(ms, nowMs) {
    var s = Math.max(0, Math.round((ms - nowMs) / 1000));
    if (s < 90) return 'Now';
    if (s < 5400) return 'in ' + Math.round(s / 60) + ' min';
    if (s < 172800) return 'in ' + Math.round(s / 3600) + ' h';
    return 'in ' + Math.round(s / 86400) + ' days';
  }
  function pill(cls, text) { return '<span class="pill ' + cls + '">' + text + '</span>'; }
  function crStatus(r) {
    if (r.st !== 'completed') return pill('warn', 'Running');
    if (r.c === 'success') return pill('ok', 'Success');
    if (r.c === 'cancelled') return pill('idle', 'Cancelled');
    return pill('bad', 'Failed');
  }
  function durationLabel(r) {
    if (r.st !== 'completed' || r.end == null || r.t == null) return '';
    var sec = Math.max(1, Math.round(r.end - r.t));
    if (sec < 60) return sec + ' sec';
    return Math.max(1, Math.round(sec / 60)) + ' min';
  }
  function triggerLabel(r) {
    if (r.ev === 'schedule') return 'GitHub schedule';
    if (r.ev !== 'workflow_dispatch') return r.ev ? String(r.ev) : '';
    var title = (r.title || '') + ' ' + (r.name || '');
    if (/\bRun now\b/i.test(title)) return 'Run now';
    if (/\bWorker dispatch\b/i.test(title)) return 'Worker dispatch';
    return 'Worker or Run now';
  }
  function onSiteHost(hostname) {
    return /^(vaultfantasy\.com|.*\.github\.io|localhost|127\.0\.0\.1)$/.test(hostname || '');
  }
  function workerUrl() {
    try {
      var q = (root.location && root.location.search || '').match(/[?&]rfurl=([^&]+)/);
      if (q) return decodeURIComponent(q[1]);
    } catch (e) {}
    return DEFAULT_WORKER;
  }

  function boardCounts(D, now) {
    var games = (D && D.games) || [];
    var upcoming = games.filter(function (g) { return g && g.start > now; }).length;
    var propRows = D && D.props && Array.isArray(D.props.rows) ? D.props.rows.length : 0;
    var ts = D && D.ts;
    return { games: games.length, upcoming: upcoming, props: propRows, ts: ts };
  }

  function lastOf(runs, id) { return (runs || []).filter(function (r) { return r.flow === id; })[0]; }
  function lastOkOf(runs, id) { return (runs || []).filter(function (r) { return r.flow === id && r.c === 'success'; })[0]; }

  function feedStatus(runs, nowMs, meta) {
    if (meta && meta.err) return { value: 'n/a', hint: 'could not load run history', tone: '' };
    if (!runs) return { value: '...', hint: 'loading run history', tone: '' };
    var failed = 0, stale = 0, running = 0, names = [];
    JOBS.forEach(function (j) {
      var last = lastOf(runs, j.id), ok = lastOkOf(runs, j.id);
      if (last && last.st !== 'completed' ) { running++; return; }
      if (last && last.c && last.c !== 'success' && last.c !== 'cancelled') { failed++; names.push(j.name); return; }
      if (isStale(j, ok ? ok.t : null, nowMs)) { stale++; names.push(j.name); }
    });
    if (failed) return { value: failed === 1 ? '1 failed' : failed + ' failed', hint: names.slice(0, 3).join(', ') + (names.length > 3 ? ' and ' + (names.length - 3) + ' more' : ''), tone: 'bad' };
    if (stale) return { value: stale === 1 ? '1 stale' : stale + ' stale', hint: names.slice(0, 3).join(', ') + (names.length > 3 ? ' and ' + (names.length - 3) + ' more' : ''), tone: 'warn' };
    if (running && !(runs || []).length) return { value: '...', hint: 'loading run history', tone: '' };
    return { value: 'All fresh', hint: running ? running + ' running now' : 'all nine jobs on cadence', tone: 'ok' };
  }

  /* ---------- GitHub runs ---------- */
  var CR = { runs: null, at: 0, err: null, busy: false };

  function normalizeRun(r, flow) {
    return {
      t: Date.parse(r.created_at) / 1000,
      end: Date.parse(r.updated_at) / 1000,
      ev: r.event,
      st: r.status,
      c: r.conclusion,
      flow: flow,
      url: r.html_url,
      title: r.display_title || '',
      name: r.name || ''
    };
  }
  function loadRuns(fetchFn) {
    fetchFn = fetchFn || (root.fetch && root.fetch.bind(root));
    if (!fetchFn || CR.busy) return Promise.resolve(CR);
    CR.busy = true;
    var one = function (wf) {
      return fetchFn('https://api.github.com/repos/' + REPO + '/actions/workflows/' + wf + '/runs?per_page=12', { headers: { Accept: 'application/vnd.github+json' } })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); });
    };
    return Promise.all(JOBS.map(function (j) { return one(j.wf); })).then(function (all) {
      var runs = [];
      all.forEach(function (pack, i) {
        ((pack && pack.workflow_runs) || []).forEach(function (r) { runs.push(normalizeRun(r, JOBS[i].id)); });
      });
      runs.sort(function (a, b) { return b.t - a.t; });
      CR.runs = runs; CR.at = Date.now() / 1000; CR.err = null;
    }).catch(function (e) { CR.err = String(e); }).then(function () { CR.busy = false; return CR; });
  }

  /* ---------- Turnstile + Run now (same Worker as the Sharp Money Refresh button) ---------- */
  function turnstileToken(sitekey) {
    return new Promise(function (res, rej) {
      var timer = setTimeout(function () { rej(new Error('turnstile')); }, 20000);
      var go = function () {
        var el = root.document.getElementById('sm-cr-turnstile');
        if (!el) {
          el = root.document.createElement('div');
          el.id = 'sm-cr-turnstile';
          el.style.cssText = 'position:fixed;right:16px;bottom:96px;z-index:1100';
          root.document.body.appendChild(el);
        }
        if (el.dataset.wid) { try { root.turnstile.remove(el.dataset.wid); } catch (e) {} }
        el.dataset.wid = root.turnstile.render(el, {
          sitekey: sitekey,
          callback: function (t) { clearTimeout(timer); res(t); },
          'error-callback': function () { clearTimeout(timer); rej(new Error('turnstile')); },
          'timeout-callback': function () { clearTimeout(timer); rej(new Error('turnstile')); }
        });
      };
      if (root.turnstile) go();
      else {
        var sc = root.document.createElement('script');
        sc.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        sc.async = true;
        sc.onload = go;
        sc.onerror = function () { clearTimeout(timer); rej(new Error('turnstile')); };
        root.document.head.appendChild(sc);
      }
    });
  }
  function clearTurnstile() {
    var w = root.document && root.document.getElementById('sm-cr-turnstile');
    if (w) w.remove();
  }
  function runNow(jobId, fetchFn) {
    fetchFn = fetchFn || (root.fetch && root.fetch.bind(root));
    var url = workerUrl();
    return fetchFn(url + '/sitekey', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (sk) {
      var tok = Promise.resolve('');
      if (sk && sk.sitekey) tok = turnstileToken(sk.sitekey);
      return tok.then(function (token) {
        return fetchFn(url + '/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: token, job: jobId }) });
      }).then(function (r) { return r.json().then(function (j) { return { http: r.status, body: j }; }); });
    }).finally(clearTurnstile);
  }

  /* ---------- render ---------- */
  function kpiHtml(label, icon, val, hint) {
    return '<section class="card kpi"><div class="card-h"><h2>' + label + '</h2>' + icon + '</div><div class="card-b"><p class="val">' + val + '</p><p class="hint">' + hint + '</p></div></section>';
  }
  function renderHtml(opts) {
    opts = opts || {};
    var D = opts.board || opts.D || null;
    var nowMs = opts.nowMs != null ? opts.nowMs : Date.now();
    var now = nowMs / 1000;
    var site = opts.onSite != null ? opts.onSite : onSiteHost(root.location && root.location.hostname);
    var loaded = CR.runs != null && !CR.err;
    var runs = loaded ? CR.runs : [];
    var bc = boardCounts(D, now);
    var feeds = feedStatus(loaded ? runs : (CR.err ? [] : null), nowMs, { err: CR.err });
    var lastSm = lastOf(runs, 'update-sharp-money');
    var lastSmOk = lastOkOf(runs, 'update-sharp-money');
    var nxt = nextDueJob(nowMs);
    var boardVal = bc.ts ? agoFrom(bc.ts, now) : 'n/a';
    var boardHint = (bc.upcoming ? bc.upcoming + ' upcoming · ' : '') + bc.games + ' games' + (bc.props ? ' · ' + bc.props + ' props' : '');
    var smVal = lastSmOk ? agoFrom(lastSmOk.t, now) : (site ? (CR.err || loaded ? 'n/a' : '...') : 'n/a');
    var smHint = lastSmOk ? 'last success' : (CR.err ? 'could not load run history' : (site ? (loaded ? 'needs a successful run' : 'loading run history') : 'needs the website'));
    var nxtVal = nxt ? inFrom(nxt.at, nowMs) : 'None';
    var nxtHint = nxt ? esc(nxt.job.name) : 'No job is scheduled';

    var banner = site ? '' : '<div class="banner"><b>Live run history needs the website.</b><span>The published artifact cannot reach GitHub or the Worker, so run times and the Run now buttons work on vaultfantasy.com.</span></div>';
    if (site && !banner) banner = '';

    var mode = '<div class="mode">' + (bc.ts && now - bc.ts > 75 * 60 ? pill('warn', 'Board behind') : pill('ok', 'Live')) + '<span>Board ' + (bc.ts ? agoFrom(bc.ts, now) : 'not loaded') + '</span></div>';

    var kpis = '<div class="kpis">' +
      kpiHtml('Price feeds', ICON.clock, esc(feeds.value), esc(feeds.hint || (site ? '...' : 'needs the website'))) +
      kpiHtml('Sharp board', ICON.pts, esc(boardVal), esc(boardHint)) +
      kpiHtml('Sharp Money refresh', ICON.star, esc(smVal), esc(smHint)) +
      kpiHtml('Next due job', ICON.edit, esc(nxtVal), nxtHint) +
      '</div>';

    var rows = JOBS.map(function (j) {
      var r = lastOf(runs, j.id);
      var ok = lastOkOf(runs, j.id);
      var stale = loaded && isStale(j, ok ? ok.t : null, nowMs);
      var result = r ? crStatus(r) + (stale ? ' ' + pill('warn', 'Stale') : '') : (stale ? pill('warn', 'Stale') : '');
      return '<tr' + (stale ? ' class="stale"' : '') + '><td class="l"><b>' + esc(j.name) + '</b><small>' + esc(j.wf) + '</small></td>' +
        '<td class="l"><small style="white-space:normal;max-width:46ch">' + esc(j.how) + '</small></td>' +
        '<td class="num">' + (r ? agoFrom(r.t, now) + '<small>' + stamp(r.t) + ' ' + TZL + '</small>' : '<span class="muted">n/a</span>') + '</td>' +
        '<td>' + result + '</td>' +
        '<td>' + (site ? '<button class="btn" type="button" data-run="' + esc(j.id) + '">Run now</button>' : '') + '</td></tr>';
    }).join('');

    var jobs = '<section class="card"><div class="card-h"><div><h2>Pipelines</h2><p>What keeps the board and the models fresh, and when each last ran.</p></div></div>' +
      '<div class="card-b"><div class="nt-tw"><table class="nt"><thead><tr><th class="l">Job</th><th class="l">How it runs</th><th>Last run</th><th>Result</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div></div></section>';

    var recentList = runs.slice(0, 12);
    var recentBody;
    if (CR.err) recentBody = '<p class="muted">Could not load run history (' + esc(CR.err) + '). GitHub allows 60 requests an hour per address; try again later.</p>';
    else if (recentList.length) {
      recentBody = '<div class="cr-ms cr-rn">' + recentList.map(function (r) {
        var job = JOB_BY_WF[r.flow];
        var dur = durationLabel(r);
        var src = triggerLabel(r);
        return '<div><span class="num">' + etFmt(r.t, { month: 'short', day: 'numeric' }) + '<small>' + clock(r.t) + '</small></span>' +
          '<div><b>' + esc(job ? job.name : r.flow) + '</b><small>' + esc(src) + (dur ? ' · ' + dur : '') + '</small></div>' + crStatus(r) + '</div>';
      }).join('') + '</div>';
    } else recentBody = '<p class="muted">' + (site ? 'Loading run history...' : 'Run history shows on the website.') + '</p>';

    var recent = '<section class="card"><div class="card-h"><div><h2>Recent runs</h2><p>The last twelve runs of these jobs, newest first.</p></div></div><div class="card-b">' + recentBody + '</div></section>';

    var foot = '<div class="sm-cr-foot"><div><b>Why a Control Room.</b> This page says what is scheduled, what ran, and whether a feed has gone stale (more than twice its usual wait), so a missed job is visible instead of a quietly old board.</div>' +
      '<div><b>Run now</b> asks the sharp-refresh Worker to start that job on GitHub, after a bot check (a one-minute cooldown). The Worker must be redeployed after this page ships before these buttons can start a named job.</div></div>';

    return '<div class="sm-cr">' + mode + (site ? '' : banner) + kpis + jobs + recent + foot + '</div>';
  }

  function bind(el) {
    if (!el || el._smCrBound) return;
    el._smCrBound = true;
    el.addEventListener('click', function (e) {
      var b = e.target.closest('[data-run]');
      if (!b || b.disabled) return;
      b.disabled = true;
      var t0 = b.textContent;
      b.textContent = 'Starting...';
      runNow(b.dataset.run).then(function (out) {
        var j = (out && out.body) || {};
        b.textContent = j.ok ? 'Started' : (j.error === 'cooldown' ? 'Just started' : (j.lineup === 'recent' || j.lineup === 'budget' ? 'Not now' : 'Could not start'));
        if (j.ok) {
          setTimeout(function () { loadRuns().then(function () { paint(el); }); }, 20000);
          setTimeout(function () { loadRuns().then(function () { paint(el); }); }, 80000);
        }
      }).catch(function () { b.textContent = 'Could not start'; }).then(function () {
        setTimeout(function () { b.disabled = false; b.textContent = t0; }, 30000);
      });
    });
  }

  function paint(el, opts) {
    if (!el) return;
    if (opts) el._smCrOpts = Object.assign({}, el._smCrOpts || {}, opts);
    el.innerHTML = renderHtml(el._smCrOpts || {});
  }

  function mount(el, opts) {
    opts = opts || {};
    if (!el) return;
    el.classList.add('sm-cr-host');
    paint(el, opts);
    bind(el);
    var site = opts.onSite != null ? opts.onSite : onSiteHost(root.location && root.location.hostname);
    if (site && (!CR.runs || Date.now() / 1000 - CR.at > 120)) {
      loadRuns().then(function () { paint(el); });
    }
    return { refresh: function (next) { paint(el, next || {}); } };
  }

  var api = {
    JOBS: JOBS,
    parseCron: parseCron,
    cronMatches: cronMatches,
    jobDueAtTick: jobDueAtTick,
    sharpGateOpen: sharpGateOpen,
    isStale: isStale,
    nextDueAt: nextDueAt,
    nextDueJob: nextDueJob,
    cadenceAt: cadenceAt,
    expectedLast: expectedLast,
    triggerLabel: triggerLabel,
    crStatus: crStatus,
    durationLabel: durationLabel,
    agoFrom: agoFrom,
    boardCounts: boardCounts,
    feedStatus: feedStatus,
    renderHtml: renderHtml,
    loadRuns: loadRuns,
    runNow: runNow,
    mount: mount,
    _state: CR
  };
  if (typeof root !== 'undefined') root.VaultControlRoom = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : this);
