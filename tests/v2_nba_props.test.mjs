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
import { logPlays, settlePlays, noteNbaReads, nbaClose, parseNbaBox, nbaActual, fetchNbaBoxes, ledgerKey, payout } from '../scripts/track-v2-plays.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const gates = createRequire(import.meta.url)(path.join(ROOT, 'sharp-money', 'v2', 'gates.js'));
const { GATES } = gates;
const NOW = 1_800_000_000, TIP = NOW + 3 * 3600;

/* One game, DET @ BOS. Each prop below is one case. Kalshi rung: [line, bid, ask, open mid, bid size, ask size, changed]. Book row: [book, line, over, under, ...]. */
function board(over = {}) {
  const b = {
    t: NOW, src_ok: { kalshi: { ok: NOW - 60 }, pinnacle: { ok: NOW - 60 }, espn: { ok: NOW - 60 } },
    games: [{ id: 'g1', tip: TIP, away: 'DET', home: 'BOS' }],
    players: { 1: ['Play Er', 'BOS', null, 's'], 2: ['Disagree Dan', 'BOS', null, 's'], 3: ['Wide Will', 'BOS', null, 's'], 4: ['Out Olly', 'BOS', null, 's'], 5: ['Move Mo', 'BOS', null, 's'], 6: ['Quest Quinn', 'BOS', 'Questionable', 's'] },
    outs: [[4, 'BOS', 'Out']],
    novig: { asof: NOW - 30, props: {} },
    props: [
      /* 1: Kalshi says over 24.5 is 55%, Pinnacle devigs to 54.3%, DraftKings hangs -108 (51.9%): a play on the over, 5.9% over the exchange */
      { p: 1, s: 'pts', g: 'g1', kal: [[24.5, 0.54, 0.56, 0.55, 10, 10, NOW - 100]], books: [['DraftKings', 24.5, '-108', '-112', 24.5, '+100', NOW - 900], ['Pinnacle', 24.5, '-130', '+110', 24.5, '-110', NOW - 900]] },
      /* 2: the exchange likes the over (55%), Pinnacle prices it the other way (44%) */
      { p: 2, s: 'reb', g: 'g1', kal: [[8.5, 0.54, 0.56, 0.55, 10, 10, NOW - 100]], books: [['DraftKings', 8.5, '-108', '-112', 8.5, '+100', NOW - 900], ['Pinnacle', 8.5, '+120', '-140', 8.5, '+120', NOW - 900]] },
      /* 3: a 20-point-wide Kalshi quote is not a price: only Pinnacle is left, so one reference */
      { p: 3, s: 'ast', g: 'g1', kal: [[5.5, 0.40, 0.60, 0.5, 10, 10, NOW - 100]], books: [['DraftKings', 5.5, '-108', '-112', 5.5, '+100', NOW - 900], ['Pinnacle', 5.5, '-130', '+110', 5.5, '-110', NOW - 900]] },
      /* 4: the same price as 1, on a player who is out */
      { p: 4, s: 'pts', g: 'g1', kal: [[24.5, 0.54, 0.56, 0.55, 10, 10, NOW - 100]], books: [['DraftKings', 24.5, '-108', '-112', 24.5, '+100', NOW - 900], ['Pinnacle', 24.5, '-130', '+110', 24.5, '-110', NOW - 900]] },
      /* 5: DraftKings is on 25.5, Pinnacle on 24.5: the exchange has no rung at 25.5, so nothing at this line has a price to beat */
      { p: 5, s: 'pts', g: 'g1', kal: [[24.5, 0.54, 0.56, 0.55, 10, 10, NOW - 100]], books: [['DraftKings', 25.5, '-108', '-112', 25.5, '+100', NOW - 900], ['Pinnacle', 24.5, '-130', '+110', 24.5, '-110', NOW - 900]] },
      /* 6: a play that is also listed Questionable */
      { p: 6, s: '3pm', g: 'g1', kal: [[2.5, 0.54, 0.56, 0.55, 10, 10, NOW - 100]], books: [['DraftKings', 2.5, '-108', '-112', 2.5, '+100', NOW - 900], ['Pinnacle', 2.5, '-130', '+110', 2.5, '-110', NOW - 900]] },
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
  assert.equal(c.price.book, 'DraftKings'); assert.equal(c.price.am, -108);
  const ex = c.refs.find(r => r.n === 'Exchange'), pn = c.refs.find(r => r.n === 'Pinnacle');
  assert.ok(Math.abs(ex.p - 0.55) < 1e-9, 'the exchange fair is the Kalshi mid at the exact line');
  assert.ok(ex.edge >= GATES.MIN_EDGE && ex.edge <= GATES.BIG_EDGE && pn.edge >= 0);
  assert.equal(c.worst, ex.edge, 'a prop play is ranked by its edge against the exchange, the anchor');
  assert.ok(c.cautions.some(x => /no settled Plays record/.test(x)), 'every NBA prop says its gates are untested here');
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
  const b = board(); b.novig.props['1|pts'] = { p: 1, s: 'pts', g: 'g1', lad: [{ k: 24.5, bid: [0.56, 0.42], ask: [0.58, 0.44], o: ['Over 24.5', 'Under 24.5'] }, { k: 25.5, bid: [0.4, 0.58], ask: [0.42, 0.6] }] };
  const c = pick(cands(b), 'Play Er Over 24.5 Points'), ex = c.refs.find(r => r.n === 'Exchange');
  assert.ok(Math.abs(ex.p - (0.55 + 0.57) / 2) < 1e-9);
  const r = gates.nbaExchangeNow({ N: b, now: NOW }, 1, 'pts', 24.5); assert.equal(r.n, 2); assert.equal(r.src, 'Kalshi+Novig');
  assert.equal(gates.nbaExchangeNow({ N: b, now: NOW }, 1, 'pts', 23.5), null);
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

test('an NBA play is logged once, with the player, game and line it needs to settle', () => {
  const L = { v: 1, plays: {} }, c = playsOf(board())[0];
  const added = logPlays(L, playsOf(board()), NOW, opts);
  assert.ok(added.length >= 2, 'the plain play and the Questionable one');
  const r = L.plays[ledgerKey(c)];
  assert.equal(r.sport, 'nba'); assert.equal(r.start, TIP); assert.equal(r.status, 'open');
  assert.deepEqual({ ...r.prop }, { season: 'nba', week: null, pid: 'nba:1', espnId: 1, gid: 'g1', name: 'Play Er', team: 'BOS', pos: null, mkt: 'pts', label: 'Points', line: 24.5, side: 'over' });
  assert.equal(r.first.price.book, 'DraftKings');
  assert.equal(logPlays(L, playsOf(board()), NOW + 600, opts).length, 0);
});

test('the last exchange read before tip becomes the close, and a stale or moved read does not', () => {
  const L = { v: 1, plays: {} }; logPlays(L, playsOf(board()), NOW, opts);
  const P = Object.values(L.plays).find(x => x.prop.pid === 'nba:1');
  assert.ok(noteNbaReads(L, board(), NOW + 600) >= 1);
  assert.equal(P.lastRead.p, 0.55); assert.equal(P.lastRead.src, 'Kalshi'); assert.equal(P.lastRead.t, NOW + 600);
  const moved = board(); moved.props[0].kal = [[25.5, 0.4, 0.42, 0.41, 1, 1, NOW]];
  noteNbaReads(L, moved, NOW + 1200); assert.equal(P.lastRead.t, NOW + 600, 'no rung at the play\'s line: the earlier read stands');
  assert.deepEqual(nbaClose(P), { p: 0.55, src: 'Kalshi', n: 1, t: NOW + 600 });
  P.lastRead.t = TIP - 4 * 3600; assert.equal(nbaClose(P), null, 'a read 4 hours before tip is not a close');
  const U = { ...P, prop: { ...P.prop, side: 'under' }, lastRead: undefined }; noteNbaReads({ plays: { u: U } }, board(), NOW);
  assert.equal(U.lastRead.p, 0.45, 'the under is the other side of the over read');
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
  assert.equal(P.close.p, 0.55); assert.ok(Math.abs(P.clv - (0.55 / P.first.price.p - 1)) < 1e-3);
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
