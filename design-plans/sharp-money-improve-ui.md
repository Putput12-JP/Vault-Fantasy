# Improve UI report: Sharp Money

Written against: 9559ebc1e29e202a0ddaef1f49bae3bb7d3d88f6 (origin/main at audit time)

Live render: https://vaultfantasy.com/sharp-money/ and https://vaultfantasy.com/sharp-money/new/ on 26 Nov 2026, about 8:06 AM CT.

This file is the improve-ui skill output (steps 1 to 5). No implementation plans were written, because the skill only writes plans for findings that survive its proof gate, and none did. It also says to stop and ask which findings to turn into plans. Accessibility issues were collected separately in `sharp-money-fixing-accessibility.md`, as the skill requires: "Discard accessibility and HTML/ARIA semantic findings unless the user explicitly requests them." Those were requested through the companion fixing-accessibility run, not here.

## Design language
- Audited surface: Vault Fantasy Sharp Money, one product with two entry points that redirect by viewport. `/sharp-money/` is the desktop layout at 768px and up (`sharp-money/index.html`). Below 768px it replaces itself with `new/`. `/sharp-money/new/` is the phone shell (`sharp-money/new/index.html`). At 768px and up it replaces itself with the desktop layout unless `?view=new` is set. Both shells load the same data and rules layer: `sharp-money/v2-pages.js`, `sharp-money/v2/gates.js`, `sharp-money/side-cards.js`, and related scripts.
- Design sources: `CLAUDE.md` (shared motion system, one `.vseg` segmented control, no sub-pages behind tab strips, CSS cascade checks). Standing product rule that Sharp Money and CFB pick cards stay pixel-identical unless Jacob explicitly asks. Appearance notes in `sharp-money/index.html` (theme, accent, density). No `DESIGN.md` was found for this surface. Absence of a DESIGN.md is not a finding.
- Documented decisions: New motion uses the shared Vault tokens and reduced-motion blocks. Segmented filters should use `.vseg` rather than a new control. Pick cards are rendered by `PlayCard` / `cardHtml` in `sharp-money/v2-pages.js` (desktop wraps them in kit `K`; the phone shell wraps them in `.v2card`). The phone shell is dark-first (`:root { color-scheme: dark }` and `theme-color: #000000` in `sharp-money/new/index.html`).
- Governing owners and consumers: Desktop chrome and theme live in `sharp-money/index.html`. Phone chrome, chips, and titles live in `sharp-money/new/index.html`. Shared play cards and the V2 record block live in `sharp-money/v2-pages.js` (`cardHtml`, `recordHtml` / `recordCore`).
- Explicit exceptions: None documented.

## Findings

No supported findings were found.

Candidates that were inspected and rejected (not findings):

1. On the 390px phone shell, the Plays screen opens with a long "V2 PLAY RECORD" note from `recordHtml`, so the play cards start below the fold (see `design-plans/shots/phone-390-dark-fold.png`). The page title is still "Plays". That is a real layout observation, but a fix could be collapsing the note, moving it, or shortening the copy. The skill requires one deterministic correction and rejects a candidate when several corrections are possible or when the change would invent product intent. The note also carries grading caveats, so collapsing it is not a proven design contract.
2. The in-page Plays / Signals / Play record / Sharps / Sharp Accounts row can clip the last label at 390px. The row is already `overflow-x: auto` (`.chips` in `sharp-money/new/index.html` line 17), so this is a scrollable chip strip, not a proven layout bug.
3. The phone shell stayed dark when light theme was requested (the 390px `/sharp-money/` visit redirects into `new/`, which does not implement the desktop Appearance adapter). The Appearance comment in `sharp-money/index.html` talks about sharing theme with Vault NBA, not about this shell. The contract does not clearly govern `new/`.

## Improve first

No supported recommendation.
