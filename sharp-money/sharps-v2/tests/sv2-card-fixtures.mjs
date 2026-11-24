/* Synthetic plays shared by the alert card tests and the share-data golden file. No network, no stored data. */
export const NOW = 1795278675; // Sat Nov 21 2026 10:31 AM CST

export const PIN = (state, pts) => ({ state, pts: pts == null ? 2.3 : pts, t_a: 1.5, from: 105, to: -129, line: -3.5, rows: 12 });
export const LIN = (state, kind) => ({ kind: kind || 'line', state, t_c: 1, pin: kind === 'price' ? { from: 105, to: -129 } : { from: 22, to: 19 }, books: 6, same_way: 4, by_book: { Pinnacle: [22, 19], DraftKings: [22.5, 19.5] }, extreme: { book: 'BetMGM', value: 18.5 } });
export const FL = (pin, line, extra) => Object.assign({ rule: 'v2f-2', span_min: 1290, window_min: 1440, pin, line, limit: { from: 1100, to: 1450, rows: 14 } }, extra || {});
export const GRADE_A = { rule: 'mg-1', letter: 'A', against: false, basis: 'a_mark', a: 'toward', c: 'quiet', a_pts: 2.31, c_pts: null, cut: { m_a: 0.5, t_a: 1.5, x_a: 2.0, m_c: 1.0, t_c: 2.0, x_c: 3.5 }, why: null };
export const GRADE_B = { rule: 'mg-1', letter: 'B', against: false, basis: 'fired', a: 'toward', c: 'quiet', a_pts: 1.8, c_pts: null, cut: GRADE_A.cut, why: null };
export const GRADE_AGAINST = { rule: 'mg-1', letter: null, against: true, basis: 'against', a: 'away', c: 'quiet', cut: GRADE_A.cut };
export const SIDE = (usd, holders) => ({ usd, holders, past_winner: { n: 3, usd: 3700 }, losing_record: { n: 2, usd: 504 }, beats: { n: 3, usd: 14900 }, loses: { n: 2, usd: 504 } });
export const NOVIG = (px, extra) => Object.assign({ px, t: NOW - 1200, since_min: 14 }, extra || {});
export const SPREAD = (extra) => Object.assign({ v: 1, asof: NOW, span_min: 1440, pin: [-3.5, -5.5], books: 6, toward: 5, away: 0 }, extra || {});

/* one play on any market: g is ml, spread or total; v2 is that market's stored v2 block */
export function play(v2, o) {
  o = o || {};
  const g = o.g || 'spread', team = o.team || 'Hornets';
  const mk = {}; mk[g] = { v2: Object.assign({ side: g === 'total' ? 'Over 220.5' : team }, v2) };
  return {
    game: { ev: 'e1', sport: o.sport || 'nba', gst: NOW + 7200, cut: NOW + 6300, frozen: !!o.frozen,
      vault: { away: 'MEM', home: 'CHA', teams: { away: ['Memphis Grizzlies', 'Grizzlies'], home: ['Charlotte Hornets', team] } }, markets: mk },
    g, sf: { side: g === 'total' ? 'Over 220.5' : team, line: g === 'ml' ? null : g === 'total' ? 220.5 : -3.5, price: 0.525, price_t: NOW - 240 }, key: 'e1|' + g, sport: o.sport || 'nba',
    units: o.sport === 'cfb' ? 0 : 1, tier: o.tier || 'mixed', cut: NOW + 6300, facts: { tiered: o.sport !== 'cfb' && o.sport !== 'cbb' }
  };
}
const FULL = () => ({
  flags: FL(PIN('toward'), LIN('toward')), move_grade: GRADE_A,
  exec: { us_best: { book: 'BetMGM', odds: -102 }, novig: NOVIG(0.51) }, vs_fair: { pts: 0.4, fair: 0.521, line: -3.5, why: null },
  sides: { Grizzlies: SIDE(30000, 14), Hornets: SIDE(20000, 17) }
});
/* the plays the share-data golden file is built from (none carries a spread_ctx, so an old build and a new build must agree byte for byte) */
export function goldenPlays() {
  const mlFlags = FL(PIN('toward'), LIN('toward', 'price'));
  return {
    spread_full: play(FULL(), { tier: 'clear' }),
    spread_frozen: play(FULL(), { tier: 'clear', frozen: true }),
    spread_against: play(Object.assign(FULL(), { move_grade: GRADE_AGAINST, flags: FL(PIN('away'), LIN('quiet')) })),
    spread_quiet_nolabel: play({ flags: FL(PIN('quiet'), LIN('quiet')), exec: { novig: NOVIG(0.51) }, vs_fair: { pts: 0.4, fair: 0.521, line: -3.5, why: null } }),
    ml_full: play(Object.assign(FULL(), { flags: mlFlags }), { g: 'ml', tier: 'clear' }),
    ml_stale_novig: play(Object.assign(FULL(), { flags: mlFlags, exec: { novig: NOVIG(0.51, { since_min: 2272, t: NOW - 136320 }) } }), { g: 'ml' }),
    total_full: play(Object.assign(FULL(), { flags: FL(PIN('toward'), LIN('toward')) }), { g: 'total' }),
    cfb_ml: play(Object.assign(FULL(), { flags: mlFlags }), { g: 'ml', sport: 'cfb' }),
    bare: play({}, {})
  };
}
export { FULL };
