# Vacated share — roster-departure re-projection

`scripts/build_vacated_share.py` → `data/vacated_share.json`, read through
`vacatedInfo()` in `index.html`.

## Why it exists

Vault already reacted when a teammate was hurt (the within-season injury
**usage cascade**, `build_usage_cascade.py`). It was blind to a teammate who
**left the team** — traded, signed elsewhere, retired, cut. A player's history
reflects the room he *shared*; when a same-position starter is gone, that history
can misstate his new role. The injury cascade cannot cover this: a departed
player isn't on the roster to be flagged Out, and the cascade only ever lifts the
man *below* an absence, so the RB1 who loses his RB2 is invisible to it.

This surfaced on Jahmyr Gibbs (2026 Wk1): David Montgomery left DET for HOU, yet
Vault projected Gibbs from his 2025 split-backfield log (61.8 vs an 84.5 line)
and graded the resulting Under an **A** — a confident phantom.

## What it measures

Consecutive nflverse season pairs S → S+1. For each returning player, the ratio
of his per-game volume S+1 / S (carries for RB rushing, targets for WR/TE
receiving), bucketed by:

- **group** (rush / rec),
- his **rank** in the S room (1..3, 3 = rank 4+),
- **direction** of the departure — a real starter ranked **above** him gone, vs a
  committee-mate **below** him gone (isolated: a ratio counts for a direction only
  when the other direction had no departure; mixed cases are skipped),
- **how many** departed (1, or 2+).

Published value is the **net** multiplier = `median(departed) / median(control)`,
where the control is the same rank with nobody departed — this strips out normal
year-over-year drift (aging, scheme, pace). A bucket ships only if it clears
`MIN_EVENTS` **and** stays the same side and > 1 across an **even/odd season
split**. The file also emits `rooms`: last completed season's ranked rooms per
`team|group`, for the live roster diff (matched by `vaultNameKey`, no ids).

## What the data actually said

- **rush, rank-2, 1 higher (lead) left → ×1.29** (stable). The classic backup who
  inherits the job — e.g. Chuba Hubbard after Rico Dowdle left.
- **rush, rank-1, 1 lower (committee-mate) left → net 1.04 but fails the even/odd
  gate (1.06 / 0.99)** → **withheld**. An established lead back does *not*
  reliably absorb a departed RB2's carries; often a new committee-mate just takes
  them. This is the Gibbs case — the model refuses to invent a bump.
- Receiving single-departure cases are mostly too noisy to clear the gate; only a
  couple of multi-departure WR/TE buckets publish.

## How the frontend uses it

`vacatedInfo(r)` returns one of:

- `{ mult, … }` — a stable bucket applies. Folded into `usageMult` alongside the
  injury cascade and QB-out, so the projection moves. The multiplier is shrunk
  toward 1 (`VAC_SHRINK`, single-season noise) and **faded** over the season
  (`VAC_FADE_WEEKS`) because the player's own in-season log increasingly reflects
  the new role — keeping the full bump mid-season would double-count. Shown in the
  detail hero ("Rico Dowdle left ×1.25") and marked green ▲ on the edge chip,
  the same "expected, not a mistake" treatment the cascade gets.
- `{ caution: true, … }` — a real starter left but no reliable bucket is measured
  (or it faded to nothing). The projection is **not** moved; instead `edgeCaution`
  raises a `room?` flag and `cappedGradeLetter` demotes the confident grade. This
  fires even for a correctly-ranked player (Gibbs A → C), unlike the role anchor's
  `role?` tier which only fires when the books contradict the depth chart.
- `null` — nothing changed in the room (or the file hasn't landed → silent no-op,
  pure history, same contract as the cascade / QB-out getters).

## Limits / follow-ups

- Team assignment is nflverse's season team; mid-season traded players are rare
  and shrinkage absorbs the noise.
- The fade is a schedule (not a measured effect size); a per-player convergence
  fit could replace it.
- Only the live **frontend** projection is wired. `scripts/build_best_bets.py`
  runs a separate role blend and does not yet mirror this — a follow-up, like the
  role-guard mirror before it.
- Like the cascade and QB-out, buckets want forward CLV validation
  (`docs/edge-feedback-loop.md`).
