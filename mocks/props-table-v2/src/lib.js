/* shared helpers for the three Props Table v2 mocks. Data: real rows from the live board (nba/projections.html Props Table), see src/props.json.
   Nothing here is invented: the movement chart draws only the opening line and the current line each book reports. */
const R = window.PROPS;
const pc = (x, d = 0) => x == null ? '' : (x * 100).toFixed(d) + '%';
const sgn = (x, d = 1) => x == null ? '' : (x >= 0 ? '+' : '') + (x * 100).toFixed(d) + '%';
const am = a => a == null ? '' : (a > 0 ? '+' : '') + a;
const initials = n => n.split(' ').map(w => w[0]).slice(0, 2).join('');
const av = r => `<span class="av"><span>${initials(r.name)}</span><img src="https://a.espncdn.com/i/headshots/nba/players/full/${r.p}.png" alt="" loading="lazy" onerror="this.remove()"></span>`;
const hit = h => !h ? `<span class="hit"><b class="muted">none</b><small>&nbsp;</small></span>`
  : `<span class="hit"><b class="${h[0] / h[1] >= .6 ? 'pos' : h[0] / h[1] <= .4 ? 'neg' : ''}">${Math.round(h[0] / h[1] * 100)}%</b><small>${h[0]} of ${h[1]}</small></span>`;
const GATE = {go: 'GO', watch: 'WATCH', 'no-go': 'NO-GO'};
const gate = r => r.best ? `<span class="gate ${r.best[5] === 'go' ? 'go' : r.best[5] === 'watch' ? 'watch' : ''}">${GATE[r.best[5]]}</span>` : '';
const betTxt = r => !r.best ? '' : r.best[0] === 'Kalshi' ? `Kalshi ${r.best[1]} ${r.best[2] + .5}+` : `${r.best[0]} ${r.best[1]} ${r.best[2]}`;
const priceTxt = r => !r.best ? '' : r.best[0] === 'Kalshi' ? Math.round(+r.best[3] * 100) + '¢' : r.best[3];
const edgeTxt = r => !r.best ? '' : `<b class="${r.best[4] > 0 ? 'pos' : 'neg'}">${sgn(r.best[4])}</b>`;
// +EV: the best price at Pinnacle's own number against Pinnacle's no-vig fair. Only props Pinnacle prices have one.
const evTxt = r => !r.ev ? `<span class="muted">none</span>` : `<b class="${r.ev.v >= .02 ? 'pos' : r.ev.v >= 0 ? '' : 'muted'}">${sgn(r.ev.v)}</b>`;
const evWho = r => r.ev ? `${r.ev.bk} ${r.ev.side} ${am(r.ev.px)}` : r.pf == null ? 'no Pinnacle price' : '';
const TELL = {p_pin: ['Pinnacle moved', 'blue'], p_acct: ['Sharp accts', 'up'], p_kal: ['Kalshi money', 'warn'], p_behind: ['Behind Pinnacle', 'up']};
const tellsOf = r => { const t = [...r.tells]; if (r.ev && r.ev.v >= .03) t.push('p_behind'); return [...new Set(t)]; };
const tellChips = r => tellsOf(r).map(t => `<span class="chip ${TELL[t][1]}"><i></i>${TELL[t][0]}</span>`).join('');
const pinBook = r => r.books.find(b => b[0] === 'Pinnacle') || r.books[0];
const moveOf = r => { const b = pinBook(r); return b ? {from: b[4], to: b[1], book: b[0]} : null; };
const moveTxt = r => { const m = moveOf(r); if (!m || m.from == null) return '<span class="muted">none</span>'; const d = m.to - m.from; return d === 0 ? `<span class="muted">${m.to} flat</span>` : `<span>${m.from} <span class="muted">to</span> ${m.to}</span>`; };
const meter = r => `<span class="meter" title="Model ${pc(r.pm)}, market ${pc(r.mkt)}, fair ${pc(r.fair)}"><span class="mid"></span>${[['m-model', r.pm], ['m-mkt', r.mkt], ['m-fair', r.fair]].map(([c, v]) => `<u class="${c}" style="left:${Math.max(3, Math.min(97, v * 100))}%"></u>`).join('')}</span>`;
const COL = {DraftKings: '#5ec269', Pinnacle: '#ff5fa2', Polymarket: '#7ab4ff'};
// movement chart: each book's opening line and its line now. That is all the board stores until the prop tape ships.
const chart = (r, w = 560, h = 170) => {
  const pts = r.books.filter(b => b[4] != null && b[1] != null);
  const ys = pts.flatMap(b => [b[1], b[4]]); if (!ys.length) return '<p class="muted">No book has posted this line yet.</p>';
  let lo = Math.min(...ys), hi = Math.max(...ys); if (hi - lo < 2) { lo -= 1; hi += 1; }
  const L = 34, Rt = 18, T = 14, B = 26, X = (v) => L + v * (w - L - Rt), Y = (v) => T + (hi - v) / (hi - lo) * (h - T - B);
  const steps = Math.round(hi - lo), grid = []; for (let v = Math.ceil(lo); v <= hi; v += Math.max(1, Math.ceil(steps / 4))) grid.push(v);
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Opening line and current line for ${r.name} ${r.stat}">
    ${grid.map(v => `<line class="g" x1="${L}" x2="${w - Rt}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end">${v}</text>`).join('')}
    <text x="${L}" y="${h - 6}">open</text><text x="${w - Rt}" y="${h - 6}" text-anchor="end">now</text>
    ${pts.map(b => { const c = COL[b[0]] || '#a2a7b1', y0 = Y(b[4]), y1 = Y(b[1]); return `<path d="M${X(0)} ${y0} H${X(.55)} V${y1} H${X(1)}" fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round"/><circle cx="${X(1)}" cy="${y1}" r="3.5" fill="${c}"/>`; }).join('')}
  </svg><div class="legend">${pts.map(b => `<span style="--c:${COL[b[0]] || '#a2a7b1'}">${b[0]} <b class="mono">${b[1]}</b></span>`).join('')}</div>
  <p class="note" style="margin-top:8px">Opening line to the line now. Hour by hour history starts when the prop tape ships.</p>`;
};
const bookRows = r => `<div>${r.books.map(b => `<div class="kv"><span>${b[0]} ${b[1]}</span><b>${b[2] == null ? 'no price' : 'O ' + am(b[2])}${b[3] == null ? '' : '  U ' + am(b[3])}</b></div>`).join('')}</div>`;
const form = r => `<div class="kv"><span>Last 5</span><b>${r.l5 ? r.l5[0] + ' of ' + r.l5[1] + ' over' : 'none'}</b></div><div class="kv"><span>Last 10</span><b>${r.l10 ? r.l10[0] + ' of ' + r.l10[1] + ' over' : 'none'}</b></div><div class="kv"><span>Vs ${r.gm.split(' @ ').find(t => t !== r.tm)}</span><b>${r.h2h ? r.h2h[0] + ' of ' + r.h2h[1] + ' over' : 'none'}</b></div>`;
const toggleOn = (el, cls = 'open') => el.classList.toggle(cls);
