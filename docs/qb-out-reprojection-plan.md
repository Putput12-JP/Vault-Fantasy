# QB-out (bounded re-projection) — data-fit plan

Status: **scoped, not built.** Extends the withhold+flag system shipped in
`fetch-pickem-props.mjs` / `build_best_bets.mjs` / `index.html` (see
`[[project_gameday_inactive_props]]`). Goal: when a projected starter is OUT,
stop merely *withholding* impacted teammates' leans and instead **re-project
them by a measured amount**, so a genuine next-man-up edge is surfaced (green)
and a phantom Over disappears on its own.

## Why the existing cascade isn't enough

`data/usage_cascade.json` (`scripts/build_usage_cascade.py`, read via
`cascadeInfo` → `usageMult`) already measures next-man-up volume, but only:

- **Same position group** — rec (WR/TE targets) and rush (RB carries).
- **Upward only** — `mult > 1` (a teammate absent ⇒ you see more).
- **Triggered by a same-group teammate**, ranked by baseline volume.

It has no concept of a **QB** being out, which is the highest-impact case and is
**cross-market and bidirectional**:

| Impacted player | Market | Direction when QB1 out |
|---|---|---|
| WR1 (Drake London) | rec_yd, rec | **down** (lower volume, shorter aDOT) |
| TE (Kyle Pitts) | rec | flat/up; rec_yd, TDs **down** |
| RB (Bijan) | rush_att, rush_yd | **up** (run-lean script) |
| RB (Bijan) | rec | up (checkdowns) — but game-script dependent |
| backup QB | pass_yd, pass_td | real, but **below** the starter's line |
| team | pass_td share | down; rush_td share to RB up |

The current system flags all of these `LINEUP` and withholds. This plan measures
the multipliers so we can move them.

## Methodology — mirror `build_usage_cascade.py`

New script `scripts/build_qb_out_impact.py` → `data/qb_out_impact.json`. Same
disciplined shape as the usage cascade (measure, don't invent; publish only what
validates):

1. **Source:** `data/nflverse_stats_<season>.json`, many seasons (`--since 2014`).
2. **Identify each team-season's QB1** = the QB with the most pass attempts /
   most starts. (Not depth_chart_order — same stale-dco reason the frontend uses
   pass-props presence, see project memory.)
3. **QB1-absent week proxy:** QB1 has ≥ `MIN_PRESENT` games that season but no
   row in week W and the team played W (identical absence proxy to the usage
   cascade). Optionally corroborate with the injuries archive when present.
4. **Baseline per teammate p, per market m** = median of p's per-game value in
   weeks where **QB1 was present** (his "normal with the starter").
5. **Effect** = `value_p,m(W) / baseline_p,m` for QB1-absent weeks, bucketed by
   `(pos, market)` — e.g. `WR|rec_yd`, `RB|rush_att`, `TE|rec`, `QB|pass_yd`
   (the backup's line vs the starter's baseline).
6. **Publish the MEDIAN** multiplier per bucket with `n` and IQR, only where
   `n ≥ MIN_EVENTS` (start at 40, as the usage cascade does). Buckets can be
   split by **spread tier** later (a QB downgrade on a favorite vs a dog changes
   the run/pass script), but ship the pooled bucket first.

Output shape (extends the cascade's convention):

```json
{ "generated":"…", "since":2014, "min_events":40,
  "note":"median teammate market multiplier when the team's QB1 is out; nflverse weekly",
  "buckets": {
    "WR|rec_yd": { "mult":0.90, "n":312, "iqr":[0.7,1.1] },
    "RB|rush_att": { "mult":1.08, "n":280, "iqr":[0.9,1.3] },
    "QB|pass_yd": { "mult":0.86, "n":190, "iqr":[0.7,1.0] }
  } }
```

## Wiring (frontend)

- `qbOutImpact()` loader + `qbOutMult(r)` mirroring `cascadeData()` /
  `cascadeInfo(r)`: returns the bucket multiplier for a row whose team has a
  QB1-out flag (reuse `window._vaultStatusById` / `impactedBy === 'QB out'`).
- Pass it into `PM.fairProbOver(...)` as a new factor **alongside** `usageMult`,
  `oppMult`, `envMult`, `scriptMult` (multiplicative, shrunk by a `CASCADE_SHRINK`
  and capped like the others).
- Display: an adjusted-**up** projection keeps the existing green ▲ cascade
  treatment ("QB out — raised ×1.08, expected"); an adjusted-**down** projection
  needs a new ▼ note ("QB out — lowered ×0.90"). Once a bucket is applied the row
  is **no longer withheld** — the number is now trustworthy — so `edgeCaution`
  tier-0 should defer to a *present* `qbOutMult` (apply, don't withhold) and keep
  withholding only where no measured bucket exists (RB1/WR1 same-group already
  handled by the usage cascade; positions/markets with no QB-out bucket stay
  `LINEUP`).
- `build_best_bets.mjs`: same — apply the multiplier where a bucket exists, keep
  skipping where it doesn't.

## Validation / no-go (hard gates)

Same bar as the rejected DvP/opponent work — a plausible adjustment that doesn't
hold up does not ship:

1. **Monotonicity / sign sanity:** pass markets ≤ 1, rush markets ≥ 1; anything
   that comes out backwards is dropped, not shipped.
2. **Season-holdout backtest:** fit on seasons ≤ Y, measure whether applying the
   multiplier reduces projection error on QB1-out games in season Y+1 vs (a) no
   adjustment and (b) the current withhold. Must beat both to ship a bucket.
3. **Min events per bucket** (≥40; thin buckets stay withheld, never shipped at
   `mult=1`).
4. Every getter returns `null` until the file lands; callers fall back to the
   withhold behavior (cold cache costs nothing) — the pattern the trade-market
   getters use.

## Scope boundaries / effort

- **In:** QB1-out cross-market multipliers (the user's Tua→London/Bijan/Pitts
  case). ~1 new Python script + 1 data file + ~40 lines of frontend wiring +
  the same in `build_best_bets.mjs`. Reuses all the plumbing shipped this session.
- **Out (later):** spread-tier split of the buckets; RB1/WR1 cross-*market*
  effects (their same-group volume is already covered); a full team-level
  re-sim. Desktop + mobile parity follows the existing prop surfaces.
- **Risk:** small — bidirectional multipliers can only help if they validate, and
  the no-go gates + null-fallback mean a bad fit degrades to today's withhold.
