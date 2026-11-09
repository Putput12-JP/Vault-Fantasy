// Polymarket Data API v2 (v1 was retired 2026-11-02 and now answers HTTP 410).
//
// v2 differences that matter here:
//   - every response is { data, pagination }, and pagination is cursor-only
//     (an `offset` parameter is rejected, so is `market`: use `condition`).
//   - row fields are snake_case (proxy_wallet, condition_id, outcome_index ...).
//   - on /v2/trades, `start` / `end` are honored only on the `user` shape; a
//     condition feed is newest-first and the cursor walks it with no 10k cap.
//
// pmRow() maps a v2 row back onto the v1 field names the collectors were
// written against, so each call site only swaps its fetch loop.
// PM_FAIL counts failed calls so a collector can exit non-zero after writing
// its data: v1's retirement went unnoticed for a week because every caller
// swallowed the error and logged "0 games updated".

export const PM_DATA = 'https://data-api.polymarket.com/v2';
export const PM_FAIL = { n: 0, ok: 0, last: null };

export function pmRow(x) {
  if (!x || typeof x !== 'object') return x;
  return {
    ...x,
    proxyWallet: x.proxy_wallet,
    conditionId: x.condition_id,
    asset: x.token_id,
    outcomeIndex: x.outcome_index,
    transactionHash: x.transaction_hash,
    eventSlug: x.event_slug,
    usdcSize: x.usdc_size,
    // positions
    ...(x.current_size !== undefined ? {
      size: x.current_size,
      avgPrice: x.avg_price,
      curPrice: x.current_price,
      currentValue: x.current_value,
      initialValue: x.entry_cost_usdc,
      cashPnl: x.current_value != null && x.entry_cost_usdc != null ? x.current_value - x.entry_cost_usdc : null,
      endDate: x.end_date,
    } : {}),
  };
}

function qs(params) {
  return Object.entries(params).filter(([, v]) => v != null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
}

// Yields { rows, more } per page (rows already v1-shaped), up to maxPages.
// `more` is false on the last page the API has. Filters are re-sent with the
// cursor, as the v2 docs ask.
export async function* pmPages(getJSON, path, params, maxPages = 1) {
  let cursor = null;
  for (let p = 0; p < maxPages; p++) {
    const url = `${PM_DATA}${path}?${qs({ ...params, ...(cursor ? { cursor } : {}) })}`;
    let j;
    try { j = await getJSON(url); PM_FAIL.ok++; }
    catch (e) { PM_FAIL.n++; PM_FAIL.last = e.message; throw e; }
    const rows = Array.isArray(j?.data) ? j.data.map(pmRow) : [];
    cursor = j?.pagination?.next_cursor || null;
    const more = !!(j?.pagination?.has_more && cursor);
    yield { rows, more };
    if (!more) return;
  }
}

// Whole list in one go (positions, small feeds).
export async function pmAll(getJSON, path, params, maxPages = 1) {
  const out = [];
  for await (const pg of pmPages(getJSON, path, params, maxPages)) out.push(...pg.rows);
  return out;
}

// True when every call this run failed: the API is down or moved again.
export const pmDead = () => PM_FAIL.n > 0 && PM_FAIL.ok === 0;

// Report a dead API without failing the step: the collector's other sources
// still have to be committed. Leaves `.pm-dead` in the working directory; the
// workflow's last step fails the run on it, after the commit.
export async function pmReportDead(what) {
  if (!pmDead()) return false;
  const msg = `Polymarket Data API: all ${PM_FAIL.n} calls failed (last: ${PM_FAIL.last}). ${what}`;
  console.error('::error::' + msg);
  try { (await import('node:fs')).writeFileSync('.pm-dead', msg + '\n'); } catch (e) { /* best effort */ }
  return true;
}
