# fixing-accessibility audit: Sharp Money

Audit only. No site code was changed.

Followed `.agents/skills/fixing-accessibility/SKILL.md` in review mode: quote the issue, state the failure, propose a small fix. Critical issues first (names, keyboard, focus), then semantics, then contrast and motion.

## Method

- Live pages: https://vaultfantasy.com/sharp-money/ and https://vaultfantasy.com/sharp-money/new/
- When: 26 Nov 2026, about 8:06 AM CT
- Code read against worktree commit 9559ebc (origin/main)
- Rendering: Playwright Chromium plus `@axe-core/playwright`, tags wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa
- Viewports: 1400 x 900 and 390 x 844, dark and light color-scheme
- Redirects: at 390px, `/sharp-money/` sends the browser to `new/`. At 1400px, `/sharp-money/new/` sends the browser to the desktop layout. The 390px "desktop" shots and the 1400px "phone" shots are those redirected layouts, not separate designs.
- The phone shell does not paint a light theme. The 390px light runs stayed dark. That is noted below, not counted as an axe violation.
- Axe also left 204 color-contrast nodes as incomplete (it could not decide). Those are not listed as failures.
- Screenshots: `design-plans/shots/`
- Pick cards: desktop `.sm-bd[role=button]` from `PlayCard` in `sharp-money/v2-pages.js`; phone `.v2card` from `v2card()` in `sharp-money/new/index.html`, HTML from `cardHtml`. Any fix that would change their pixels is marked "needs Jacob's explicit OK".

## Counts

Confirmed axe violations, unique page/theme combinations:

| Surface | Theme | color-contrast | html-has-lang | other axe |
| --- | --- | --- | --- | --- |
| Desktop 1400 | dark | 23 | 1 | 0 |
| Desktop 1400 | light | 7 | 1 | 0 |
| Phone 390 | dark (light request also stayed dark) | 2 | 1 | 0 |

Manual checks on top of axe:

- Accessible names: no unnamed visible buttons or links in the Plays default view (37 desktop, 34 phone interactive controls).
- Keyboard focus rings: present. After Tab, desktop `.sm-a` and phone `.chip` showed a 2px solid accent outline (`design-plans/shots/desktop-1400-dark-focus.png`, `phone-390-dark-focus.png`). CSS: `sharp-money/index.html` about lines 426-428; `sharp-money/new/index.html` lines 178-179.
- tabindex greater than 0: none found.
- Headings: 0 `h1`-`h6` or `role=heading` in all eight runs.
- `<main>`: present on the phone shell (`#scr`). Not present as a landmark on the desktop layout.
- Skip link: not present on either layout.
- Team logos: 16 images, all with `alt=""`. Team names appear as text next to the logos, so empty alt is the decorative pattern, not a missing-name failure.
- Reduced motion: CSS exists on both layouts (`sharp-money/index.html` lines 278, 302, 419-422; `sharp-money/new/index.html` lines 180-181). Not flagged.

## Prioritized list

### 1. Missing `lang` on both documents (serious, names/semantics)

- Evidence: axe `html-has-lang` on every run. Live markup was `<html data-theme="dark">` (or light) with no `lang`. Source: `sharp-money/index.html` starts at line 1 with `<title>` and no `<!doctype html>` or `<html lang="...">`. `sharp-money/new/index.html` line 1 is `<!doctype html>` followed by `<meta>` and `<title>`, also with no `<html lang="...">`.
- Why it matters: screen readers need a document language to pronounce the page.
- Proposed minimal fix: add `lang="en"` on the root html element of both files. On the desktop file, also add a doctype and an explicit `<html>` so the existing `document.documentElement.dataset.theme` script still runs on the real root.
- Pick cards: no.

### 2. No heading structure (high, semantics)

- Evidence: zero heading elements in the accessibility tree on desktop and phone. The visible "Plays" title on the phone shell is `<div class="title">` from `head()` in `sharp-money/new/index.html` line 259. The desktop header shows "Plays" and the subtitle "PRICES THAT BEAT TWO INDEPENDENT FAIR PRICES, RANKED BY THE WORST-CASE EDGE" as styled text, not `h1`/`h2`.
- Why it matters: heading navigation is how many keyboard and screen-reader users move through a page.
- Proposed minimal fix: make the page title an `h1` (phone: the `.title` node; desktop: the "Plays" header label). Keep the existing typography classes so the look stays the same.
- Pick cards: no.

### 3. Desktop layout has no `main` landmark (high, semantics)

- Evidence: axe/manual `main: false` on the 1400px desktop runs. The phone shell already has `<main id="scr" aria-live="polite">` at `sharp-money/new/index.html` line 183. Desktop uses a `.sm-main` class on a non-landmark container.
- Why it matters: a main landmark is the target for skip links and screen-reader "jump to content".
- Proposed minimal fix: use `<main class="sm-main">` (or add `role="main"`) on the desktop content column in `sharp-money/index.html`. Do not wrap or restyle the pick cards themselves.
- Pick cards: no.

### 4. No skip link (high, semantics / keyboard)

- Evidence: no `skip-link` or equivalent in either document. Manual check was false on all eight runs.
- Why it matters: keyboard users otherwise tab through the sidebar or tab bar before the plays list.
- Proposed minimal fix: add a visually hidden "Skip to content" link as the first focusable element, pointing at the main landmark from item 3 / `#scr`.
- Pick cards: no.

### 5. Inactive sport and list filters fail contrast (medium, contrast)

- Evidence: axe color-contrast on desktop 1400 dark, 2.76:1, `#6a6a6a` on `#272727`, 12px normal, need 4.5:1. The controls are the unselected radiogroup buttons "NFL 15", "CFB 67", "NBA 26", "CBB 62" and "Open 11", "Watch 6", "Passed 4". On desktop 1400 light the same unselected radios are 4.27:1 (`#737373` on `#f3f3f3`). The dark color matches `textTertiary: "#6a6a6a"` in the theme at `sharp-money/index.html` line 443.
- Why it matters: unselected filter text is hard to read, especially the sport and list switches people use constantly.
- Proposed minimal fix: raise the unselected radio text (or `textTertiary` if that is the only consumer you intend to change) until it meets 4.5:1 against the pill background. Check that the same token is not also used on pick card chrome before shipping. If it is shared, this needs Jacob's explicit OK.
- Pick cards: maybe, if `textTertiary` is reused inside `cardHtml`. Treat as needs Jacob's explicit OK until a token audit shows otherwise.

### 6. Desktop header subtitle fails contrast (medium, contrast)

- Evidence: axe color-contrast on desktop 1400 dark, 3.21:1, `#6a6a6a` on `#1a1a1a`, 10px. Rendered text includes "SHARP MONEY /" and "PRICES THAT BEAT TWO INDEPENDENT FAIR PRICES, RANKED BY THE WORST-CASE EDGE". Same `textTertiary` token as item 5.
- Why it matters: the page subtitle is below AA at its actual size.
- Proposed minimal fix: same as item 5, or a one-off slightly lighter color on the header subtitle only, so pick cards stay untouched.
- Pick cards: no, if the change is scoped to the header. Yes / needs Jacob's explicit OK if it is a global token change.

### 7. Phone helper text and Open count fail contrast (medium, contrast)

- Evidence: axe color-contrast on the 390px shell, both theme requests (the shell stayed dark). `button[data-v="open"] > small` (the "11" on Open) is 3.9:1, `#6a6a6f` on `#000000`, 11.7px. That comes from `.chip { color: var(--mut) }` plus `.chip small { opacity: .7 }` in `sharp-money/new/index.html` lines 18-20 (`--mut: #98989f`). `.sub` ("Each prop against Pinnacle and the exchange. Ordered by worst-case edge.") is 3.5:1, `#636366` on `#000000`, 12px, from `.sub { color: var(--dim) }` at line 23 and `--dim: #636366` at line 10.
- Why it matters: the Open count and section hints are below AA.
- Proposed minimal fix: drop the `.chip small` opacity, and/or lighten `--dim` enough to reach 4.5:1 on `#000`. Warning: phone pick cards use `V2PAL` (`sharp-money/new/index.html` line 1128), where `mut: 'var(--mut)'` and `dim: 'var(--dim)'`. Changing those variables would retint muted text on the pick cards.
- Pick cards: needs Jacob's explicit OK if `--mut` or `--dim` changes. No, if only `.chip small { opacity: 1 }` is changed (that count is not on the card).

### 8. Muted labels on tiles, including pick cards, fail or sit near the line (medium, contrast)

- Evidence: axe reported nine 10px nodes at 2.83:1, `#6a6a6a` on `#252525`, in the main column among the record/play tiles (desktop 1400 dark). A live probe of the same view showed tile labels such as "YOU PAY", "PINNACLE FAIR", "WORST CASE", "RECORD", and "UNITS" at 10.5px. Those labels are painted by `cardHtml` (pick cards, `sharp-money/v2-pages.js` around the `tile()` helper near line 479) and `recordCore` `big()` (line 511), using `pal.mut`. Desktop `pal.mut` is `textSecondary` (`#999999` at line 443). Phone cards use `var(--mut)`.
- Why it matters: the price-tile captions on the play cards, and the record-tile captions above them, are small muted text on a raised tile.
- Proposed minimal fix: a dedicated, slightly lighter caption color used only after Jacob approves a pick-card change, or a card-scoped contrast pass with a pixel check against the locked cards. Do not quietly retint `pal.mut`.
- Pick cards: needs Jacob's explicit OK.

### 9. Desktop Passed and Open rows are clickable but have no key handler (critical if you open those lists; keyboard)

- Evidence: from code, not from the default Plays tab (that tab uses `PlayCard` / kit `K`, which already spreads `Lg(onClick)` at `sharp-money/index.html` line 443: Enter and Space). `PassRow` and `OpenRow` use `ui().row()` in `sharp-money/v2-pages.js` lines 110-112, which sets `role="button"` and `tabIndex=0` but no `onKeyDown`. Used at lines 133-146. The phone shell does not have this gap: `sharp-money/new/index.html` line 1209 sets `role="button"` and `tabIndex=0` on `[data-go]`, and line 1219 handles Enter and Space.
- Why it matters: keyboard users can focus a Passed or Open row on desktop and get no action.
- Proposed minimal fix: reuse the kit `Lg` pattern (or the same Enter/Space handler) inside `row()` when `onClick` is set. Do not change `cardHtml` or `PlayCard`.
- Pick cards: no.

## Checks that passed (so they are not in the list above)

- Visible controls on the Plays view had accessible names.
- Focus rings paint for keyboard users on both shells.
- Phone play cards (`.v2card`) and desktop play cards (kit `K`) are keyboard activatable.
- Logo images use empty alt next to visible team names.
- Reduced-motion CSS is present.
- No positive tabindex found.

## Recommended first fix PR (still not written here)

Keep it to structure only, so pick cards stay pixel-identical:

1. Add `lang="en"` (and a doctype / `<html>` on the desktop file).
2. Promote the visible "Plays" title to `h1` without changing type size or color.
3. Mark the desktop content column as `<main>`.
4. Add a skip link to that main / `#scr`.

A follow-up can add the `row()` keyboard handler for Passed and Open (also no card-pixel change). Contrast work should be a later PR, with a token audit and Jacob's yes if any pick-card caption would move.
