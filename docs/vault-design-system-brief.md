# Vault Fantasy — Design System Brief (for Claude Design)

The full source of truth is `vault-ds.css` (963 lines). This brief is a self-contained
summary you can paste directly into Claude Design. **Inline the token block below at the
top of any mock** — Claude Design opens files standalone, where a `<link>` to
`vault-ds.css` breaks and everything renders unstyled.

Three themes ship: **Vapor Sky** (dark, default), **Americana Paper** (light),
**Onyx & Steel Frost** (dark, muted steel-blue). Switch with `data-theme="light"` /
`data-theme="onyx"` on the root; default (no attribute) is Vapor Sky.

---

## Paste-ready tokens

```css
:root {
  /* VAPOR SKY — dark (default) */
  --bg:#070d18; --surface:#0e1626;
  --s1:#0e1626; --s2:#131d30; --s3:#1b2740; --s4:#243352; --s-bright:#2c3f60;
  --border:rgba(123,170,240,0.10); --border2:rgba(123,170,240,0.17); --border3:rgba(123,170,240,0.30);
  --dim:#1b2740;
  --text:#eaf2fc; --text2:#bdcce2; --muted:#808fa6;
  --primary:#bec6e0; --on-primary:#0a1424;
  --accent:#2f63c4; --accent2:#7bd0ff; --accent3:#b3e0ff;
  --red:#e23a4e; --red2:#ff5a6e;
  --sky:#4d86f0; --sky-dim:#2f63c4;
  /* position colours (light in dark themes; they INVERT in light mode) */
  --qb:#ff6680; --rb:#3DCC7A; --wr:#7bd0ff; --te:#f5c842;
  --suggest:#7bd0ff; --value:#3DCC7A; --reach:#e23a4e; --gold:#f5c842; --navy:#070d18;
  --violet:#a78bfa;
  --pos-ink:#12151c;        /* ink that stays legible on a position-coloured pill */
  --glass-1:rgba(14,22,38,0.55); --glass-2:rgba(20,30,48,0.55);
  --blur-md:blur(22px); --blur-sm:blur(14px);

  /* type */
  --font-sans:'Archivo','Hanken Grotesk',system-ui,sans-serif;
  --font-mono:'JetBrains Mono','Space Mono',monospace;
  --t-hero:34px; --t-title:24px; --t-h1:20px; --t-h2:17px;
  --t-body:15px; --t-secondary:13px; --t-label:11px; --t-micro:10px; --t-nano:9px;
  --lh-hero:1.05; --lh-tight:1.15; --lh-snug:1.3; --lh-body:1.5; --lh-relaxed:1.6;

  /* shape */
  --radius-sm:6px; --radius-md:10px; --radius-lg:16px; --radius-xl:20px; --radius-pill:999px;
  --shadow-card:0 24px 60px -20px rgba(4,9,20,0.62),0 1px 0 rgba(255,255,255,0.06) inset;

  /* motion */
  --ease-out:cubic-bezier(0.16,1,0.3,1);      /* entrances, expanders, movement */
  --ease-sheet:cubic-bezier(0.32,0.72,0,1);   /* bottom sheets (iOS/Vaul) */
  --ease-rail:cubic-bezier(0.65,0,0.35,1);    /* TRAVEL — moving between two known points */
  --ease-spring:cubic-bezier(0.34,1.56,0.64,1); /* ARRIVAL — press-release, pop-in (overshoots) */
  --dur-press:80ms; --dur-release:500ms; --dur-rail:400ms;
  --press-chip:.88; --press-btn:.94; --press-card:.975; --press-row:.99;
}

[data-theme="light"] {  /* AMERICANA PAPER */
  --bg:#f4efe4; --surface:#fffdf8;
  --s1:#fffdf8; --s2:#f3eede; --s3:#ece5d4; --s4:#e1d8c4; --s-bright:#ffffff;
  --border:rgba(29,40,66,0.10); --border2:rgba(29,40,66,0.17); --border3:rgba(29,40,66,0.28);
  --text:#1d2433; --text2:#3a4658; --muted:#606774; --dim:#ece5d4;
  --primary:#16233a; --on-primary:#ffffff;
  --accent:#16233a; --accent2:#2c4063; --accent3:#4a5d80;
  --red:#c22a37; --red2:#c12c38; --sky:#1f4e87; --sky-dim:#16395f;
  --qb:#c22a37; --rb:#067648; --wr:#1a6aab; --te:#955804;
  --suggest:#1f4e87; --value:#067648; --reach:#c22a37; --gold:#955804; --navy:#16233a;
  --violet:#6d3fc4;
  --glass-1:rgba(255,255,255,0.62); --glass-2:rgba(248,244,235,0.62);
  --pos-ink:#ffffff;
  --shadow-card:0 20px 48px -22px rgba(41,50,66,0.24),0 1px 0 rgba(255,255,255,0.5) inset;
}

[data-theme="onyx"] {  /* ONYX & STEEL FROST */
  --bg:#0e0f13; --surface:#16171c;
  --s1:#16171c; --s2:#1c1e24; --s3:#23252c; --s4:#2c2f38; --s-bright:#343844;
  --border:rgba(255,255,255,0.08); --border2:rgba(255,255,255,0.12); --border3:rgba(255,255,255,0.22);
  --text:#f3f4f7; --text2:#c9cdd6; --muted:#868c9b; --dim:#23252c;
  --primary:#8fb4e0; --on-primary:#0b1420;
  --accent:#5e7c9c; --accent2:#8fb4e0; --accent3:#b9d2ec;
  --red:#e23a4e; --red2:#ff5a6e; --sky:#5e7c9c; --sky-dim:#43607d;
  --suggest:#8fb4e0; --value:#5fe09a; --reach:#e23a4e; --gold:#8fb4e0; --navy:#0e0f13;
  --violet:#a78bfa;
  --glass-1:rgba(24,25,30,0.55); --glass-2:rgba(30,32,38,0.55);
  --shadow-card:0 24px 60px -20px rgba(6,6,8,0.62),0 1px 0 rgba(255,255,255,0.05) inset;
}
```

Load the fonts: **Archivo** (UI + reading) and **JetBrains Mono** (numbers/data only) from
Google Fonts. Optional accents used sparingly: **Newsreader** (serif quotes).

---

## Type ramp

One ramp for the whole app. Sans (Archivo) carries all reading + UI text. **Mono is
reserved for numbers/tabular data** — never for UI chrome.

| Class | Size | Role |
|---|---|---|
| `.t-hero` | 34px / 800 | screen hero, empty states |
| `.t-title` | 24px / 800 | screen / page title |
| `.t-h1` | 20px / 700 | major section heading |
| `.t-h2` | 17px / 700 | card title, list-row title |
| `.t-body` | 15px / 400 | default reading text |
| `.t-secondary` | 13px / 400 | supporting / meta text (muted) |
| `.t-label` | 11px mono / 700 uppercase, .1em | kicker / label |
| `.t-data` | mono / 700 tabular-nums | all numbers and stat cells |

---

## Core components

**Cards — exactly two radii, chosen by NESTING not by page:**
- `.v-card` — primary panel. `background:var(--s1); border:1px solid var(--border2); radius 16px`.
- `.v-card-inset` — a tile/row inside a panel. `background:var(--s2); border:1px solid var(--border); radius 10px`.
- Never nest an inset inside an inset. Shadows are opt-in per surface (`var(--shadow-card)`), not baked in — several pages are intentionally flat.

**Glass:** `.v-glass` / `.v-glass-deep` / `.v-glass-lite` — frosted surfaces using
`--glass-1/2` + `backdrop-filter`. Use for overlays and floating chrome.

**Buttons:** `.v-btn` (gradient `--accent → --accent2`, white ink, radius 10px),
`.v-btn.red`, `.v-btn.ghost`, `.v-btn.sm`. Press is built in (asymmetric scale).

**Position badges:** `.v-pos.QB/.RB/.WR/.TE` — tinted 15% background + position colour ink.

**Pills / chips:** `.v-pill` (rounded, translucent), `.v-pill.mono`, `.v-pill.hot` (pulsing red).

**Verdict tags:** `.v-tag.value` (green), `.v-tag.reach` (red), `.v-tag.sugg` (sky), `.v-tag.gold`.

**Segmented control:** ONE primitive — `.vseg` with `<button>` children, no CSS of its
own. Variants: `.sm/.lg` size, `.fluid` even split, `.scroll` overflow, `.free` no
container, `.bar` underline. The active state is a single sliding pill that **travels**
between segments (never blinks). Retint per-scope with `--vseg-bg/--vseg-border/--vseg-ink`.

---

## Motion vocabulary (one system — don't hand-roll transitions)

- **Press** — snap down fast (`--dur-press` 80ms, ease-out), spring back slow
  (`--dur-release` 500ms, `--ease-spring`). The asymmetry IS the effect. Press depth is
  inverse to size: chip `.88`, button `.94`, card `.975`, row `.99`. Overshoot
  (`--ease-spring`) is only ever safe on `transform`, never width/height.
- **Rail** — a tab strip gets ONE shared bar that travels (`--ease-rail`, `--dur-rail`
  400ms), never a per-tab indicator that blinks.
- **Spinner** (`.spinner`, sizes `.xs/.sm/.md/.lg`) — a real SVG arc, linear spin.
  Never a rotating text glyph. Use a **skeleton** (`.skel`) for content arriving into a
  known shape (lists, tables); a spinner is only for a discrete action with unknown wait.
- Colour/opacity feedback ≤150ms may use plain `ease`. Movement never uses bare `ease`.
- Everything degrades under `prefers-reduced-motion:reduce`.

---

## Rules that keep it coherent

- Position colours **invert between themes** — light in dark themes, dark in light. Never
  hardcode ink on a position pill; use `--pos-ink`, which flips per theme.
- Semantic colours (`--red`, `--value`, etc.) are tuned to clear WCAG AA down to `--s3`.
- Reach for a token, not a raw hex — the whole point is one system across three themes.
- Give `body` an explicit `background:var(--bg)` and `color:var(--text)`.
