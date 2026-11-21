# Sharps V2: remaining work, to run after the weekly plan resets

Written 2026-11-21. The weekly plan was 92% used, so the build was cut to what fits. The weekly limit resets
Monday 2026-11-23 at 9:59 AM Central. The 5-hour limit resets tonight at 6:09 PM Central, but the weekly
limit is the binding one, so do not start the items below before Monday 9:59 AM.

## What shipped in the first PR

- V2 pages as a standalone page at `sharp-money/sharps-v2/` (Sharps and Following, hash routes), beside the
  classic pages, which are untouched.
- Account data fields added to `wallets.json` (additive, reviewed, tested, old keys unchanged) plus `since.json`.
- Evidence tiers on the V2 Sharps page computed in the browser from today's `live.json`.

## What was cut, in the order to do it

0. **Embed V2 inside the Sharp Money Sharps and Following tabs (the user's requirement, 2026-11-21).** V2 must render inside the existing
   shell where the old tabs render, not as a separate page and not by redirect (a redirect was tried in PR 542 and reverted).
   The host calls `window.VaultFollowing` (mountPage, Page, openSheet) and the side-cards mount; V2 needs an embed adapter that
   implements those entry points, mounts only the page content (no second header or nav; keep the freshness line, refresh and info
   inside the tab), scopes its CSS under one root class so it cannot leak into the host (tokens off `body.sv2` and `:root` must move
   to the root element), and keeps the open-sheet hook the Sharps cards use. Both shells (index.html and new/index.html) load it, and
   the old files stay for rollback behind a switch. Test with no dev params, in both shells, light and dark, phone and desktop.

1. **Plays data (largest piece).** Opus writes `docs/sharps-v2-plays-spec.md`, Sonnet implements it in
   `scripts/build_side_cards.py`, then three Opus reviewers (point in time, frozen-test integrity, honesty and records).
   - Publish additively in `live.json`: the evidence tier, the conflict block (who holds the other side by account tier),
     "same wallet backs N plays", the shown size (flat 1u NBA/NFL/CBB, 0 CFB) under a new key, the price you would get with its
     age, price vs no-vig fair, and Action Network money % and bet % joined by game key.
   - Forward shadow log of the tier at lock, with a new pre-registration `docs/sharp-tier-v2-prereg.md` (primary metric price at
     the cut vs Pinnacle no-vig close, n >= 300 per sport before any verdict).
   - History (CLAUDE.md records rule): recompute the per-tier record of every graded play from frozen cards, write the
     missing 2026-11-20 CBB re-add entry in `docs/side-card-record.md` with verified old and new numbers (audit read: 37-23
     +4.56u n=60 became 62-42 +9.37u n=104 on plays cut before Nov 20; CBB since 2-3 n=5). Verify before writing.
   - Frozen tests stay untouched: no change to `scripts/sf_rungs.py`, gates, or any existing key.
   - When it lands, switch the V2 Sharps page from the client-side tier to the published tier field.
2. **Full adversarial review of the V2 pages.** The four Opus lenses were cut: contrast and accessibility (measured),
   rules and honesty (traced numbers), click-through behavior at 375 and 1440 in dark and light, motion and performance.
   Then a Sonnet fix pass and an Opus recheck.
3. **Wire V2 into the product.** Add a link from the classic Sharp Money pages once V2 is approved, and decide when V2
   replaces classic. Not done on purpose: the classic pages are held by other open PRs.
4. **Classic page over-claims** (`sharp-money/side-cards.js`, held by PRs 304 and 305): wording that calls the shown rule the
   pre-registered lock "still in its forward test", the Elite and Lock chips, and the "on Polymarket" label on a Pinnacle price.
   Do after those PRs merge.
5. **Deferred data items:** entry price for open positions (needs the wallet's trades, never inferred from the first-seen
   price), a CLV tier for CFB and CBB (needs a registered walk-forward test), a server-side follow store.

## Monday backlog added 2026-11-21 (user requests, after the V2 tabs went live)

Run these together with the plays data, since the record and the size both depend on the saved tier and shown size.

1. **Record page for all sharps.** One Record view covering the Sharps plays and the Sharp Accounts (the wallets), inside the Sharp Money
   tabs and matching the V2 look. Recorded plays only, flat-stake units and ROI with n, forward rows apart from in-sample rows (the cut
   is 2026-11-16 12:00 AM Central), CLV against the close as the lead metric, small samples flagged with their n.
2. **Tiers record.** The record of each evidence tier (Clear, Mixed, Thin, Contested, and the account tiers Beats / Even / Loses / Too few)
   with n, from frozen cards point in time. Needs the tier saved at lock (plays data item 1) and the history re-derived from frozen cards.
3. **Fix the 1u suggestion.** The flat 1u was agreed as an MVP, not as the final rule. Replace it with a real size rule. This changes the
   documented side-card exception in CLAUDE.md (the user's decision, so ask first which rule), and must be tested on forward data, not
   on the data that found it. Any change to the shown size is a tracking change: history and the record must be re-derived with old and
   new numbers in the PR (the audit measured the old ladder at +9.81u versus flat -0.74u over 166 plays, all in-sample). Keep the
   "untested rule" label until a registered forward test passes. The frozen forward tests stay untouched: ship the new size as a
   shadow beside the current one first.
4. **Sharp Account table: bring back ROI, Record and the other old columns.** The old Following directory showed Wallet, Last 10 results,
   Sport, Record, ROI, Bets, Usual stake, Beat the close and Open now, with market filters and a 20+ bets filter. V2's table dropped Record
   and ROI. Restore them (with n, the thin-sample flag, and the "past record, picked after the fact" caveat), keeping the closing-line
   edge as the lead column. The data is already published (`w_`, `l_`, `roi`, `n`, `flat_roi`, `fwd`, `usual`, `legs`).

## Decisions needed from the user

- Which size rule replaces the MVP flat 1u (backlog item 3), and whether a conflicted play (the audit's Watch tier) keeps a size. This changes
  CLAUDE.md, so it is the user's call. Until decided, the flat 1u stays under the "untested rule" label on every tier.
- Whether V2 replaces classic, and when.

## Model assignment for the remaining work

| Step | Model |
|---|---|
| Plays data spec and the three reviews, the page review lenses, rechecks | Opus |
| Plays data build, page fixes, fix passes | Sonnet |
| Lookups, file searches | Haiku |

## Budget note

The first build used about 92% of the week across roughly 25 agents. Items 1 and 2 are each close to that size if run as
full workflows. To fit, run item 1 first, then item 2 with two reviewers instead of four.
