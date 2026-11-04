/* NBA props in Sharp Money Plays: the same gates as the NFL props, run on the NBA live board (nba-live/board.json), and the ledger rows they leave.
   The board here is built by hand so every case is one line of the board: a price that beats the exchange, one Pinnacle prices the other way, a quote
   too wide to be a price, a source that has gone quiet, a player who is out.
   run: node --test tests/v2_nba_props.test.mjs */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { loadFixtures, runPage } from './v2_page_harness.mjs';
import { tagNbaShop, logPlays, settlePlays, noteNbaReads, nbaClose, parseNbaBox, nbaActual, fetchNbaBoxes, ledgerKey, payout } from '../scripts/track-v2-plays.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const gates = createRequire(import.meta.url)(path.join(ROOT, 'sharp-money', 'v2', 'gates.js'));
const { GATES } = gates;
const NOW = 1_800_000_000, TIP = NOW + 1800;   // half an hour to tip: past the nightly NBA cap's lock (GATES.NBA_LOCK_MIN), so plays log

/* One game, DET @ BOS. Each prop below is one case. Kalshi rung: [line, bid, ask, open mid, bid size, ask size, changed]. Book row: [book, line, over, under, ...]. */
function board(over = {}) {
  const b = {
    t: NOW, src_ok: { kalshi: { ok: NOW - 60 }, pinnacle: { ok: NOW - 60 }, espn: { ok: NOW - 60 } },
    games: [{ id: 'g1', tip: TIP, away: 'DET', home: 'BOS' }],
    players: { 1: ['Play Er', 'BOS', null, 's'], 2: ['Disagree Dan', 'BOS', null, 's'], 3: ['Wide Will', 'BOS', null, 's'], 4: ['Out Olly', 'BOS', null, 's'], 5: ['Move Mo', 'BOS', null, 's'], 6: ['Quest Quinn', 'BOS', 'Questionable', 's'] },
    outs: [[4, 'BOS', 'Out']],
    novig: { asof: NOW - 30, props: {} },
    props: [
      /* 1: Kalshi says over 24.5 is 60%, Pinnacle devigs to 60.1%, DraftKings hangs -125 (55.6%): a play on the over, 7.9% over the exchange */
      { p: 1, s: 'pts', g: 'g1', kal: [[24.5, 0.59, 0.61, 0.60, 10, 10, NOW - 100]], books: [['DraftKings', 24.5, '-125', '-105', 24.5, '+100', NOW - 900], ['Pinnacle', 24.5, '-160', '+140', 24.5, '-110', NOW - 900]] },
      /* 2: the exchange likes the over (55%), Pinnacle prices it the other way (44%) */
      { p: 2, s: 'reb', g: 'g1', kal: [[8.5, 0.59, 0.61, 0.60, 10, 10, NOW - 100]], books: [['DraftKings', 8.5, '-125', '-105', 8.5, '+100', NOW - 900], ['Pinnacle', 8.5, '+120', '-140', 8.5, '+120', NOW - 900]] },
      /* 3: a 20-point-wide Kalshi quote is not a price: only Pinnacle is left, so one reference */
      { p: 3, s: 'ast', g: 'g1', kal: [[5.5, 0.40, 0.60, 0.5, 10, 10, NOW - 100]], books: [['DraftKings', 5.5, '-125', '-105', 5.5, '+100', NOW - 900], ['Pinnacle', 5.5, '-150', '+130', 5.5, '-110', NOW - 900]] },
      /* 4: the same price as 1, on a player who is out */
      { p: 4, s: 'pts', g: 'g1', kal: [[24.5, 0.59, 0.61, 0.60, 10, 10, NOW - 100]], books: [['DraftKings', 24.5, '-125', '-105', 24.5, '+100', NOW - 900], ['Pinnacle', 24.5, '-160', '+140', 24.5, '-110', NOW - 900]] },
      /* 5: DraftKings is on 25.5, Pinnacle on 24.5: the exchange has no rung at 25.5, so nothing at this line has a price to beat */
      { p: 5, s: 'pts', g: 'g1', kal: [[24.5, 0.59, 0.61, 0.60, 10, 10, NOW - 100]], books: [['DraftKings', 25.5, '-125', '-105', 25.5, '+100', NOW - 900], ['Pinnacle', 24.5, '-160', '+140', 24.5, '-110', NOW - 900]] },
      /* 6: a play that is also listed Questionable */
      { p: 6, s: '3pm', g: 'g1', kal: [[2.5, 0.59, 0.61, 0.60, 10, 10, NOW - 100]], books: [['DraftKings', 2.5, '-125', '-105', 2.5, '+100', NOW - 900], ['Pinnacle', 2.5, '-160', '+140', 2.5, '-110', NOW - 900]] },
    ],
  };
  return Object.assign(b, over);
}
const cands = (N, now = NOW) => gates.build({ N, now, D: { games: [] }, P: null, T: null, E: null }).all.filter(c => c.sport === 'nba' && c.kind === 'prop');
const pick = (list, title) => list.find(c => c.title === title);

test('a DraftKings price that beats the exchange, with Pinnacle agreeing, is an NBA play', () => {
  const c = pick(cands(board()), 'Play Er Over 24.5 Points');
  assert.equal(c.tier, 'play');
  assert.equal(c.kind, 'prop'); assert.equal(c.sport, 'nba'); assert.equal(c.start, TIP);
  assert.equal(c.price.book, 'DraftKings'); assert.equal(c.price.am, -125);
  const ex = c.refs.find(r => r.n === 'Exchange'), pn = c.refs.find(r => r.n === 'Pinnacle');
  assert.ok(Math.abs(ex.p - 0.6) < 1e-9, 'the exchange fair is the Kalshi mid at the exact line');
  assert.ok(ex.edge >= GATES.MIN_EDGE && ex.edge <= GATES.BIG_EDGE && pn.edge >= 0);
  assert.equal(c.worst, ex.edge, 'a prop play is ranked by its edge against the exchange, the anchor');
  assert.ok(c.cautions.some(x => /rule C/.test(x) && /live test/.test(x)), 'every NBA prop says its rule was found in-sample');
  assert.equal(c.price.kal, true, 'Kalshi quoted the line, and the row stores it');
  assert.equal(c.row.pid, 'nba:1'); assert.deepEqual(c.matchup, { away: 'DET', home: 'BOS' });
  assert.equal(pick(cands(board()), 'Play Er Under 24.5 Points').tier, 'none', 'the other side of the same market is not a play');
});

test('the gates hold: Pinnacle the other way, a quote too wide, a player who is out, a line with no exchange rung', () => {
  const l = cands(board());
  const d = pick(l, 'Disagree Dan Over 8.5 Rebounds'); assert.equal(d.tier, 'pass'); assert.match(d.reasons[0], /Pinnacle|Both sides/);
  const w = pick(l, 'Wide Will Over 5.5 Assists'); assert.equal(w.tier === 'watch' || w.tier === 'none', true); assert.deepEqual(w.refs.map(r => r.n), ['Pinnacle']);
  assert.equal(l.some(c => c.row.name === 'Out Olly'), false, 'a player who is out has no price worth taking');
  const m = pick(l, 'Move Mo Over 25.5 Points'); assert.deepEqual(m.refs, [], 'Pinnacle is at 24.5 and the exchange has no rung at 25.5: no reference at the line');
  assert.equal(m.tier, 'none');
  assert.ok(pick(l, 'Quest Quinn Over 2.5 3-Pointers').cautions.some(x => /questionable/i.test(x)));
});

test('a source that has gone quiet is not a price, and a game that has tipped is not pregame', () => {
  const stale = board({ src_ok: { kalshi: { ok: NOW - GATES.MAX_AGE - 5 }, pinnacle: { ok: NOW - 60 }, espn: { ok: NOW - 60 } }, novig: { asof: NOW - GATES.MAX_AGE - 5, props: {} } });
  assert.equal(cands(stale).length, 0, 'no exchange read in the last 45 minutes: no NBA prop candidates at all');
  const noBook = board({ src_ok: { kalshi: { ok: NOW - 60 }, pinnacle: { ok: NOW - 60 }, espn: { ok: NOW - GATES.MAX_AGE - 5 } } });
  assert.equal(cands(noBook).length, 0, 'the book source is stale');
  const noPin = cands(board({ src_ok: { kalshi: { ok: NOW - 60 }, pinnacle: { ok: NOW - GATES.MAX_AGE - 5 }, espn: { ok: NOW - 60 } } }));
  assert.equal(pick(noPin, 'Play Er Over 24.5 Points').tier, 'watch', 'a stale Pinnacle leaves one reference, so Watch');
  assert.equal(cands(board(), TIP + 1).length, 0, 'tipped');
  assert.deepEqual(gates.build({ now: NOW, D: { games: [] }, P: null, T: null, E: null }).all, [], 'no board, no NBA props');
});

test('Novig at the exact line is a second exchange read, and the two are averaged', () => {
  const b = board(); b.novig.props['1|pts'] = { p: 1, s: 'pts', g: 'g1', lad: [{ k: 24.5, bid: [0.61, 0.37], ask: [0.63, 0.39], o: ['Over 24.5', 'Under 24.5'] }, { k: 25.5, bid: [0.4, 0.58], ask: [0.42, 0.6] }] };
  const c = pick(cands(b), 'Play Er Over 24.5 Points'), ex = c.refs.find(r => r.n === 'Exchange');
  assert.ok(Math.abs(ex.p - (0.6 + 0.62) / 2) < 1e-9);
  const r = gates.nbaExchangeNow({ N: b, now: NOW }, 1, 'pts', 24.5); assert.equal(r.n, 2); assert.equal(r.src, 'Kalshi+Novig');
  assert.equal(gates.nbaExchangeNow({ N: b, now: NOW }, 1, 'pts', 23.5), null);
});

test('the other US books (Action Network, row.shop) are shopped for the best price, each only while its own feed answers', () => {
  const ok = { kalshi: { ok: NOW - 60 }, pinnacle: { ok: NOW - 60 }, espn: { ok: NOW - 60 }, actionprops: { ok: NOW - 60 } };
  const b = board({ src_ok: ok });
  b.props[0].shop = [['FanDuel', 24.5, '-123', '-104', 24.5, '-123', NOW - 600], ['bet365', 24.5, '-124', '+100', null, null, NOW - 600], ['BetMGM', 25.5, '+105', '-125', null, null, NOW - 600]];
  const c = pick(cands(b), 'Play Er Over 24.5 Points');
  assert.equal(c.tier, 'play'); assert.equal(c.price.book, 'FanDuel'); assert.equal(c.price.am, -123, 'the best over at 24.5 across DraftKings and the shop rows');
  assert.deepEqual(c.price.shop, ['DraftKings', 'FanDuel', 'bet365'], 'every US book quoting this line, so the record can tell one book from many');
  assert.equal(pick(cands(board({ src_ok: ok })), 'Play Er Over 24.5 Points').price.shop.length, 1, 'DraftKings only when no shop row exists');

  const quietShop = board({ src_ok: { ...ok, actionprops: { ok: NOW - GATES.MAX_AGE - 5 } } }); quietShop.props[0].shop = b.props[0].shop;
  assert.equal(pick(cands(quietShop), 'Play Er Over 24.5 Points').price.book, 'DraftKings', 'a quiet Action Network feed is not a price');

  const quietEspn = board({ src_ok: { ...ok, espn: { ok: NOW - GATES.MAX_AGE - 5 } } }); quietEspn.props[0].shop = b.props[0].shop;
  const q = pick(cands(quietEspn), 'Play Er Over 24.5 Points');
  assert.equal(q.price.book, 'FanDuel'); assert.deepEqual(q.price.shop, ['FanDuel', 'bet365'], 'a quiet ESPN feed drops DraftKings, not the other books');

  const L = { v: 1, plays: {} }; logPlays(L, [c], NOW, opts);
  assert.deepEqual(L.plays[ledgerKey(c)].first.price.shop, ['DraftKings', 'FanDuel', 'bet365'], 'the ledger keeps the books checked at first sight');
});

test('the page and the headless module decide the NBA props identically', async () => {
  const fx = loadFixtures(), N = board({ t: fx.data.ts }), now = fx.data.ts + 60;
  const shift = x => JSON.parse(JSON.stringify(x).replace(new RegExp(String(NOW), 'g'), String(fx.data.ts)).replace(new RegExp(String(TIP), 'g'), String(fx.data.ts + 3 * 3600)));
  const nb = shift(N); nb.novig.asof = fx.data.ts - 30;
  const page = await runPage({ html: path.join(ROOT, 'sharp-money', 'v2', 'index.html'), fixtures: { ...fx, nba: nb }, now, pages: [] });
  const mod = gates.build({ D: fx.data, P: fx.props, T: fx.tape, E: fx.edge, N: nb, now }).all.filter(c => c.sport === 'nba' && c.kind === 'prop');
  const pn = page.all.filter(c => c.sport === 'nba' && c.kind === 'prop');
  assert.ok(pn.length > 0 && pn.length === mod.length);
  assert.deepEqual(pn.map(c => [c.id, c.tier]), mod.map(c => [c.id, c.tier]));
  assert.ok(pn.some(c => c.tier === 'play'));
  assert.equal(gates.build({ D: fx.data, P: fx.props, T: fx.tape, E: fx.edge, now }).all.filter(c => c.sport === 'nba' && c.kind === 'prop').length, 0, 'without the board there are no NBA props and nothing else changes');
});

/* ---- the ledger ---- */
const opts = { edgeGenerated: 1, season: '2026', week: 6 };
const playsOf = N => cands(N).filter(c => c.tier === 'play');
function box(rows, minutes = 240) {   // ESPN summary: keys list, one stats string array per athlete
  const keys = ['minutes', 'fieldGoalsMade-fieldGoalsAttempted', 'threePointFieldGoalsMade-threePointFieldGoalsAttempted', 'rebounds', 'assists', 'steals', 'blocks', 'points'];
  const ath = Object.entries(rows).map(([id, v]) => v == null ? { athlete: { id }, didNotPlay: true, stats: [] } : { athlete: { id }, stats: [String(v.min ?? minutes / Object.keys(rows).length), '5-10', `${v.tpm ?? 0}-3`, String(v.reb ?? 0), String(v.ast ?? 0), '0', '0', String(v.pts ?? 0)] });
  return { header: { competitions: [{ status: { type: { completed: true } } }] }, boxscore: { players: [{ statistics: [{ keys, athletes: ath }] }] } };
}

/* Rule C: NBA props play when Pinnacle and the exchange agree within 1 point and Kalshi quotes the line, with no 55% price floor. */
const one = (prop, pl = ['Rule Ray', 'BOS', null, 's']) => board({ players: { 7: pl }, outs: [], props: [{ p: 7, g: 'g1', ...prop }] });
const ray = (b, t) => pick(cands(b), 'Rule Ray ' + t);

test('rule C: a plus-money price is a play when the fairs agree within 1 point and Kalshi quotes the line', () => {
  /* Kalshi 52%, Pinnacle -120/+100 devigs to 52.2%, DraftKings +105 (48.8%): 6.6% over the exchange, under the old 55% floor */
  const c = ray(one({ s: 'pts', kal: [[20.5, 0.51, 0.53, 0.52, 10, 10, NOW - 100]], books: [['DraftKings', 20.5, '+105', '-125', 20.5, '+100', NOW - 900], ['Pinnacle', 20.5, '-120', '+100', 20.5, '-110', NOW - 900]] }), 'Over 20.5 Points');
  assert.ok(c.price.p < GATES.MIN_PRICE);
  assert.equal(c.tier, 'play', c.reasons.join(' '));
  assert.equal(c.price.kal, true);
});

test('rule C: fairs 1 point or more apart, or no Kalshi quote, is a Pass with the reason', () => {
  /* the old fixture Pinnacle (-150/+130, 58.4%) against Kalshi 60%: 1.6 points apart, inside the old 4-point check */
  const gap = ray(one({ s: 'pts', kal: [[24.5, 0.59, 0.61, 0.60, 10, 10, NOW - 100]], books: [['DraftKings', 24.5, '-125', '-105', 24.5, '+100', NOW - 900], ['Pinnacle', 24.5, '-150', '+130', 24.5, '-110', NOW - 900]] }), 'Over 24.5 Points');
  assert.equal(gap.tier, 'pass'); assert.match(gap.reasons.join(' '), /1\.6 points apart/);
  /* Novig alone at 60%, Kalshi has no rung at the line: the fairs agree but rule C needs Kalshi */
  const b = one({ s: 'pts', kal: [], books: [['DraftKings', 24.5, '-125', '-105', 24.5, '+100', NOW - 900], ['Pinnacle', 24.5, '-160', '+140', 24.5, '-110', NOW - 900]] });
  b.novig.props['7|pts'] = { p: 7, s: 'pts', g: 'g1', lad: [{ k: 24.5, bid: [0.59, 0.39], ask: [0.61, 0.41] }] };
  const nk = ray(b, 'Over 24.5 Points');
  assert.equal(nk.price.kal, false); assert.equal(nk.tier, 'pass'); assert.match(nk.reasons.join(' '), /Kalshi is not quoting/);
  /* an NFL prop is still held by the price floor: rule C is NBA only */
  assert.equal(gates.judge({ kind: 'prop', sport: 'nfl', price: { p: 0.5 }, hoursOut: 5, cautions: [], refs: [{ n: 'Pinnacle', p: 0.53 }, { n: 'Exchange', p: 0.53 }] }).tier, 'pass');
});

test('rule C: under 3% over the exchange is a Pass for NBA props, stored or live', () => {
  /* Kalshi 52%, DraftKings -103 (50.7%): 2.5% over the exchange, enough for NFL props (2%) but under the NBA floor */
  const c = ray(one({ s: 'pts', kal: [[20.5, 0.51, 0.53, 0.52, 10, 10, NOW - 100]], books: [['DraftKings', 20.5, '-103', '-117', 20.5, '+100', NOW - 900], ['Pinnacle', 20.5, '-120', '+100', 20.5, '-110', NOW - 900]] }), 'Over 20.5 Points');
  assert.equal(GATES.NBA_MIN_EDGE, 0.03);
  assert.equal(c.tier, 'pass'); assert.match(c.reasons.join(' '), /need 3% or more/);
  const row = { id: 'x', sport: 'nba', kind: 'prop', start: TIP, firstSeen: TIP - 3600, first: { price: { p: 0.507, kal: true }, refs: [{ n: 'Pinnacle', p: 0.522, edge: 0.03 }, { n: 'Exchange', p: 0.52, edge: 0.025 }] } };
  assert.deepEqual(gates.heldBack(row), ['edge']);
  row.first.refs[1].edge = 0.031; assert.deepEqual(gates.heldBack(row), []);
});

test('rule C re-scores stored NBA rows: the stored Kalshi flag first, then the Kalshi reads file; Passed rows it would play are promoted', () => {
  const row = (o = {}) => ({ id: 'n|9|pts|20.5|over|' + TIP, sport: 'nba', kind: 'prop', start: TIP, firstSeen: TIP - 3 * 3600, status: 'won', units: 1.05,
    first: { price: { p: 0.488, am: 105, book: 'DraftKings', ...(o.price || {}) }, refs: o.refs || [{ n: 'Pinnacle', p: 0.522, edge: 0.07 }, { n: 'Exchange', p: 0.52, edge: 0.066 }] } });
  try {
    gates.setKalshiReads(null);
    assert.deepEqual(gates.heldBack(row({ price: { kal: true } })), [], 'agreeing fairs, Kalshi stored, no price floor');
    assert.deepEqual(gates.heldBack(row({ price: { kal: false } })), ['kalshi']);
    assert.deepEqual(gates.heldBack(row()), ['kalshi'], 'no stored flag and no read: Kalshi absent');
    gates.setKalshiReads({ rows: { ['n|9|pts|20.5|over|' + TIP]: [0.51, 0.53, TIP - 4 * 3600] } });
    assert.deepEqual(gates.heldBack(row()), [], 'the read at first sight counts');
    gates.setKalshiReads({ rows: { ['n|9|pts|20.5|over|' + TIP]: [0.40, 0.60, TIP - 4 * 3600] } });
    assert.deepEqual(gates.heldBack(row()), ['kalshi'], 'a quote wider than MAX_EXCH_SPREAD is not a price');
    assert.deepEqual(gates.heldBack(row({ price: { kal: true }, refs: [{ n: 'Pinnacle', p: 0.54, edge: 0.107 }, { n: 'Exchange', p: 0.52, edge: 0.066 }] })), ['fairs']);
    assert.deepEqual(gates.heldBack(row({ price: { kal: true }, refs: [{ n: 'Pinnacle', p: 0.522, edge: 0.07 }, { n: 'Exchange', p: 0.52, edge: 0.15 }] })), ['edge'], 'over BIG_EDGE');
    const before = { firstSeen: GATES.NBA_FAIR_SINCE - 3600, start: GATES.NBA_FAIR_SINCE + 3600 };
    assert.equal(gates.promoted({ ...row({ price: { kal: true } }), ...before }), true);
    assert.equal(gates.promoted({ ...row({ price: { kal: true } }), ...before, sport: 'nfl' }), false, 'only NBA props are promoted');
    assert.equal(gates.promoted({ ...row({ price: { kal: true } }), firstSeen: GATES.NBA_FAIR_SINCE + 1 }), false,
      'first seen after rule C: the ledger passed it on purpose (e.g. outside the night\'s top 5), so it stays a Pass');
    assert.equal(gates.oldGate(row({ price: { kal: true } })), false, 'under 55%: the price floor held it');
    assert.equal(gates.oldGate({ ...row({ price: { kal: true, p: 0.56 } }), firstSeen: GATES.NBA_FAIR_SINCE + 1 }), false, 'first seen after rule C: not part of the before record');
  } finally { gates.setKalshiReads(null); }
});

/* The nightly cap: 7 NBA plays on one night, edges 4% to 9.2% over the exchange (Kalshi 52%, Pinnacle 52.2%), DraftKings over +100 to +110. */
const PRICES = ['+110', '+108', '+106', '+105', '+104', '+102', '+100'];
const seven = (tip = TIP) => board({ games: [{ id: 'g1', tip, away: 'DET', home: 'BOS' }], outs: [], players: Object.fromEntries(PRICES.map((_, i) => [10 + i, ['Cap ' + i, 'BOS', null, 's']])),
  props: PRICES.map((am, i) => ({ p: 10 + i, s: 'pts', g: 'g1', kal: [[20.5, 0.51, 0.53, 0.52, 10, 10, NOW - 100]], books: [['DraftKings', 20.5, am, '-130', 20.5, '+100', NOW - 900], ['Pinnacle', 20.5, '-120', '+100', 20.5, '-110', NOW - 900]] })) });
const capPlays = (N, now, L) => gates.build({ N, now, L, D: { games: [] }, P: null, T: null, E: null }).all.filter(c => c.sport === 'nba' && c.title.endsWith('Over 20.5 Points'));

test('nightly cap: before the lock the top 5 by edge show as Plays not yet locked, the rest Pass, and nothing is logged', () => {
  const tip = NOW + 3 * 3600, l = capPlays(seven(tip), NOW);
  const pl = l.filter(c => c.tier === 'play'), ps = l.filter(c => c.tier === 'pass');
  assert.equal(GATES.NBA_CAP, 5); assert.equal(pl.length, 5); assert.equal(ps.length, 2);
  assert.deepEqual(pl.map(c => c.title).sort(), ['Cap 0', 'Cap 1', 'Cap 2', 'Cap 3', 'Cap 4'].map(n => n + ' Over 20.5 Points'), 'the five biggest edges');
  assert.ok(pl.every(c => c.capPending && /Not locked yet/.test(c.cautions[0])));
  assert.match(ps[0].reasons[0], /Outside tonight.s top 5/);
  const L = { v: 1, plays: {} }; assert.equal(logPlays(L, pl, NOW, opts).length, 0, 'the ledger waits for the lock');
});

test('nightly cap: after the lock the top 5 log, and a later play only fills a slot left open', () => {
  const L = { v: 1, plays: {} }, l = capPlays(seven(), NOW, L);
  assert.equal(l.filter(c => c.tier === 'play' && !c.capPending).length, 5);
  assert.equal(logPlays(L, l, NOW, opts).length, 5);
  const again = capPlays(seven(), NOW + 300, L);
  assert.equal(again.filter(c => c.tier === 'play').length, 5, 'the logged five stay Plays');
  assert.equal(logPlays(L, again, NOW + 300, opts).length, 0, 'no slot left');
  delete L.plays[Object.keys(L.plays)[0]];
  assert.equal(capPlays(seven(), NOW + 600, L).filter(c => c.tier === 'play').length, 5, 'with 4 logged, one open slot goes to the next best');
});

test('nightly cap: plays logged before the cap shipped compete at the lock, and the ledger stamps each picked or capped', () => {
  /* Cap 4, 5 and 6 (the 5th to 7th biggest edges) were logged before NBA_CAP_SINCE, for a night that locks after it */
  const pre = i => { const c = capPlays(seven(), NOW).find(x => x.title === 'Cap ' + i + ' Over 20.5 Points'); return { id: ['p', c.start, c.row.pid, c.row.mkt, c.row.line, c.side].join('|'), sport: 'nba', kind: 'prop', status: 'open', start: c.start, firstSeen: GATES.NBA_CAP_SINCE - 100, first: { worst: c.worst, price: { p: c.price.p, kal: true }, refs: c.refs.map(r => ({ n: r.n, p: r.p, edge: r.edge })) } } };
  const L = { v: 1, plays: Object.fromEntries([4, 5, 6].map(i => { const r = pre(i); return [r.id, r] })) };
  /* before the lock they hold no slot: the top 5 are Cap 0 to 4, pending, and 5 and 6 are Passes */
  const tip = NOW + 3 * 3600, before = capPlays(seven(tip), NOW, { v: 1, plays: Object.fromEntries(Object.values(L.plays).map(r => [r.id.replace('|' + TIP + '|', '|' + tip + '|'), { ...r, id: r.id.replace('|' + TIP + '|', '|' + tip + '|'), start: tip }])) });
  assert.deepEqual(before.filter(c => c.tier === 'play').map(c => c.title.split(' ')[1]).sort(), ['0', '1', '2', '3', '4']);
  assert.ok(before.filter(c => c.tier === 'play').every(c => c.capPending));
  /* at the lock: Cap 0 to 3 log, Cap 4 is already there, and the stamps decide 4, 5 and 6 */
  const all = gates.build({ N: seven(), now: NOW, L, D: { games: [] }, P: null, T: null, E: null }).all;
  assert.equal(logPlays(L, all.filter(c => c.tier === 'play'), NOW, opts).length, 4);
  const stale = seven(); stale.src_ok = { kalshi: { ok: NOW - GATES.MAX_AGE - 5 }, pinnacle: { ok: NOW - 60 }, espn: { ok: NOW - GATES.MAX_AGE - 5 } }; stale.novig.asof = NOW - GATES.MAX_AGE - 5;
  assert.equal(gates.capStamp(L, all, { N: stale, now: NOW }), 0, 'no live prices: no stamps this run');
  assert.equal(gates.capStamp(L, all, { N: seven(), now: NOW }), 3);
  const by = i => L.plays[pre(i).id];
  assert.equal(by(4).capPick, true); assert.equal(by(5).capOut, true); assert.equal(by(6).capOut, true);
  assert.deepEqual([...gates.capOut(Object.values(L.plays))].sort(), [pre(5).id, pre(6).id].sort(), 'the record keeps the five the lock picked');
  assert.equal(gates.capStamp(L, all, { N: seven(), now: NOW + 600 }), 0, 'stamped once');
  assert.equal(capPlays(seven(), NOW + 600, L).filter(c => c.tier === 'play').length, 5);
});

test('nightly cap on the stored record: the top 5 by first-sight edge seen by the lock, then later rows by time', () => {
  const row = (i, edge, seen) => ({ id: 'r' + i, sport: 'nba', kind: 'prop', status: 'won', start: TIP, firstSeen: seen, first: { worst: edge } });
  const lock = TIP - GATES.NBA_LOCK_MIN * 60;
  /* six seen by the lock: the five best edges stay, the smallest (r1, 3%) and both later rows are held */
  const six = [row(1, .03, lock - 9000), row(2, .09, lock - 9000), row(3, .05, lock - 60), row(4, .04, lock - 60), row(6, .07, lock - 9000), row(8, .045, lock - 10), row(5, .08, lock + 60), row(7, .06, lock + 30)];
  assert.deepEqual([...gates.capOut(six)].sort(), ['r1', 'r5', 'r7']);
  /* three seen by the lock: two slots left, filled by the later rows in time order, not by edge */
  const three = [row(1, .03, lock - 9000), row(2, .09, lock - 60), row(3, .05, lock - 60), row(5, .08, lock + 600), row(6, .04, lock + 30), row(7, .06, lock + 300)];
  assert.deepEqual([...gates.capOut(three)].sort(), ['r5']);
  assert.equal(gates.capOut([{ ...row(9, .05, 0), sport: 'nfl' }]).size, 0, 'NBA props only');
});

test('an NBA play is logged once, with the player, game and line it needs to settle', () => {
  const L = { v: 1, plays: {} }, c = playsOf(board())[0];
  const added = logPlays(L, playsOf(board()), NOW, opts);
  assert.ok(added.length >= 2, 'the plain play and the Questionable one');
  const r = L.plays[ledgerKey(c)];
  assert.equal(r.sport, 'nba'); assert.equal(r.start, TIP); assert.equal(r.status, 'open');
  assert.deepEqual({ ...r.prop }, { season: 'nba', week: null, pid: 'nba:1', espnId: 1, gid: 'g1', name: 'Play Er', team: 'BOS', pos: null, mkt: 'pts', label: 'Points', line: 24.5, side: 'over' });
  assert.equal(r.first.price.book, 'DraftKings');
  assert.equal(r.first.price.kal, true, 'the row stores that Kalshi quoted the line, which rule C re-scores it from');
  assert.equal(logPlays(L, playsOf(board()), NOW + 600, opts).length, 0);
});

test('the last exchange read before tip becomes the close, and a stale or moved read does not', () => {
  const L = { v: 1, plays: {} }; logPlays(L, playsOf(board()), NOW, opts);
  const P = Object.values(L.plays).find(x => x.prop.pid === 'nba:1');
  assert.ok(noteNbaReads(L, board(), NOW + 600) >= 1);
  assert.equal(P.lastRead.p, 0.6); assert.equal(P.lastRead.src, 'Kalshi'); assert.equal(P.lastRead.t, NOW + 600);
  const moved = board(); moved.props[0].kal = [[25.5, 0.4, 0.42, 0.41, 1, 1, NOW]];
  noteNbaReads(L, moved, NOW + 1200); assert.equal(P.lastRead.t, NOW + 600, 'no rung at the play\'s line: the earlier read stands');
  assert.deepEqual(nbaClose(P), { p: 0.6, src: 'Kalshi', n: 1, t: NOW + 600 });
  P.lastRead.t = TIP - 4 * 3600; assert.equal(nbaClose(P), null, 'a read 4 hours before tip is not a close');
  const U = { ...P, prop: { ...P.prop, side: 'under' }, lastRead: undefined }; noteNbaReads({ plays: { u: U } }, board(), NOW);
  assert.equal(U.lastRead.p, 0.4, 'the under is the other side of the over read');
  const before = P.lastRead.t; noteNbaReads(L, board(), TIP + 5); assert.equal(P.lastRead.t, before, 'nothing is read after tip');
});

test('NBA props settle from the box score: win pays 1/price - 1, loss -1, push 0, did not play void', () => {
  const run = (rows, minutesOk = true, extra = {}) => {
    const L = { v: 1, plays: {} }; logPlays(L, playsOf(board()), NOW, opts);
    const P = Object.values(L.plays).find(x => x.prop.pid === 'nba:1'); noteNbaReads(L, board({ src_ok: { kalshi: { ok: TIP - 700 }, pinnacle: { ok: TIP - 700 }, espn: { ok: TIP - 700 } }, novig: { asof: TIP - 700, props: {} } }), TIP - 600);
    const b = parseNbaBox(box(rows)); const out = settlePlays(L, { statsFor: () => null, finals: () => null, T: {}, nowS: TIP + 4 * 3600, nbaBoxes: b ? { g1: b } : {}, ...extra });
    return { P, out };
  };
  let { P } = run({ 1: { pts: 30, min: 36 }, 2: { pts: 9, min: 300 } }); assert.equal(P.status, 'won'); assert.equal(P.actual, 30); assert.equal(P.units, +payout(P.first.price.p).toFixed(3));
  assert.equal(P.close.p, 0.6); assert.ok(Math.abs(P.clv - (0.6 / P.first.price.p - 1)) < 1e-3);
  ({ P } = run({ 1: { pts: 20, min: 30 }, 2: { min: 300 } })); assert.equal(P.status, 'lost'); assert.equal(P.units, -1);
  ({ P } = run({ 1: { pts: 24.5, min: 30 }, 2: { min: 300 } })); assert.equal(P.status, 'push'); assert.equal(P.units, 0);
  ({ P } = run({ 1: null, 2: { min: 300 } })); assert.equal(P.status, 'void'); assert.equal(P.units, 0);
  ({ P } = run({ 2: { min: 300 } })); assert.equal(P.status, 'void', 'a player missing from a final box did not play');
});

test('an NBA prop waits 3 hours, waits for a final box, and goes void 36 hours after tip with none', () => {
  const L = { v: 1, plays: {} }; logPlays(L, playsOf(board()), NOW, opts);
  const P = Object.values(L.plays).find(x => x.prop.pid === 'nba:1'), full = { g1: parseNbaBox(box({ 1: { pts: 30, min: 36 }, 2: { min: 300 } })) };
  settlePlays(L, { statsFor: () => null, finals: () => null, T: {}, nowS: TIP + 2 * 3600, nbaBoxes: full }); assert.equal(P.status, 'open');
  settlePlays(L, { statsFor: () => null, finals: () => null, T: {}, nowS: TIP + 20 * 3600, nbaBoxes: {} }); assert.equal(P.status, 'open');
  settlePlays(L, { statsFor: () => null, finals: () => null, T: {}, nowS: TIP + 37 * 3600, nbaBoxes: {} }); assert.equal(P.status, 'void');
  assert.equal(P.close, false, 'settled with no read before tip: no close is claimed');
});

test('a box that is not final, or not filled in, is not a box; combined stats add up', () => {
  const b = box({ 1: { pts: 30, reb: 8, ast: 5, tpm: 3, min: 36 }, 2: { min: 300 } });
  assert.equal(parseNbaBox({ ...b, header: { competitions: [{ status: { type: { completed: false } } }] } }), null);
  assert.equal(parseNbaBox(box({ 1: { pts: 30, min: 36 }, 2: { min: 60 } })), null, 'under 300 player minutes: ESPN flipped it to completed before filling the box');
  const ok = parseNbaBox(b);
  assert.equal(nbaActual(ok, 1, 'pts'), 30); assert.equal(nbaActual(ok, 1, '3pm'), 3); assert.equal(nbaActual(ok, 1, 'pra'), 43); assert.equal(nbaActual(ok, 1, 'pa'), 35);
  assert.equal(nbaActual(ok, 99, 'pts'), null); assert.equal(nbaActual(ok, 1, 'tov'), null);
});

test('only plays that are open, NBA and 3+ hours past tip are looked up', async () => {
  const L = { v: 1, plays: {} }; logPlays(L, playsOf(board()), NOW, opts);
  const seen = [], f = async u => { seen.push(u); return box({ 1: { pts: 30, min: 36 }, 2: { min: 300 } }); };
  assert.deepEqual(await fetchNbaBoxes(L, TIP + 3600, f), {}); assert.equal(seen.length, 0);
  const got = await fetchNbaBoxes(L, TIP + 4 * 3600, f); assert.deepEqual(Object.keys(got), ['g1']); assert.equal(seen.length, 1, 'one call per game, not per play');
  assert.deepEqual(await fetchNbaBoxes(L, TIP + 4 * 3600, async () => { throw new Error('espn down'); }), {});
});

test('older NBA prop rows are labelled DraftKings only, once, and nothing else is touched', () => {
  const L = { v: 1, plays: {
    a: { sport: 'nba', kind: 'prop', first: { price: { book: 'DraftKings', am: -125 } } },
    b: { sport: 'nba', kind: 'prop', first: { price: { book: 'FanDuel', am: -120, shop: ['DraftKings', 'FanDuel'] } } },
    c: { sport: 'nfl', kind: 'prop', first: { price: { book: 'DraftKings' } } },
    d: { sport: 'nba', kind: 'book', first: { price: { book: 'DraftKings' } } } } };
  assert.equal(tagNbaShop(L), 1);
  assert.deepEqual(L.plays.a.first.price.shop, ['DraftKings']);
  assert.deepEqual(L.plays.b.first.price.shop, ['DraftKings', 'FanDuel']);
  assert.equal(L.plays.c.first.price.shop, undefined); assert.equal(L.plays.d.first.price.shop, undefined);
  assert.equal(tagNbaShop(L), 0, 'a second run changes nothing');
});
