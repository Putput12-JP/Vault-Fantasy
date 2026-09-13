# Vault — Programmatic SEO Plan

**Status:** proposal / needs go-ahead · **Date:** 2026-08-20
**Goal alignment:** 2026 GTM is free / land-grab. These pages are a *compounding, durable* acquisition channel that feeds the north star (connect a Sleeper league). Content, not price.

---

## Why this works for Vault specifically

Programmatic SEO lives or dies on **unique value per page** and **data defensibility**. Vault sits at the top of that hierarchy: our pages would be powered by **proprietary, product-derived data** that competitors can't copy.

- `data/trade_market.json` — values fit from **251,314 real Sleeper trades / 26,282 leagues**
- `data/sleeper_adp_stats.json` — ADP from **38,566 real drafts / 5.3M+ picks**

Every competitor page ("[Player] dynasty value") is either crowd-vote (KTC), editorial (DLF), or a black-box "algorithm." Ours would show **what the player actually traded for, in real leagues** — genuinely unique content on every page, which is exactly what avoids thin-content penalties. This is the moat, pointed at search.

---

## The technical reality (and the fix)

**Problem:** Vault is a client-rendered SPA (`index.html`) on GitHub Pages. Crawlers see almost no content, which is the ceiling the SEO fundamentals hit. We can't just "add pages" to the SPA.

**Fix:** Pre-generate **static, self-contained HTML pages at build time** (same pattern as `marketing/trade-card/make_trade_card.py` and the graphics pipeline: Python + a template, output real HTML). Each page is fully readable without JS, lives at a clean subfolder URL, is listed in a sitemap, and links to the app. Regenerate on the **existing data cron** so pages stay fresh as the models update (freshness is a ranking signal and ours is automatic).

- **Subfolders, not subdomains** (`vaultfantasy.com/players/…`) to consolidate domain authority.
- Static files serve fine from GitHub Pages; no server needed.

---

## Playbooks, prioritized by (intent × our data × competition)

| Priority | Playbook | Pattern | Why | Page count |
|---|---|---|---|---|
| **P0 pilot** | Profiles | `/players/<slug>/` — "[Player] dynasty/redraft value" | Our strongest data, clear intent, huge volume | ~300–800 |
| **P1** | Comparisons (competitor) | `/keeptradecut-alternative/`, `/fantasycalc-alternative/`, `/best-dynasty-trade-calculator/` | Highest commercial intent, low page count, big payoff, ranks faster on a new domain | ~10–20 |
| **P2** | ADP + Rookie picks | `/adp/…`, "[Player] ADP", "2026 1st round pick value" | Draft-season intent, proprietary ADP | ~50–150 |
| **P3** | Comparisons (player) | `/trade-value/<a>-vs-<b>/` — "[A] vs [B] trade value" | Long-tail, proprietary, but n² — quality-gate hard | gated |
| **P3** | Glossary | `/fantasy-football/what-is-superflex/` | Top-funnel, easy wins, low competition | ~30–50 |

Competitor pages (P1) use the **`competitors` skill** framework; schema on all pages uses the **`schema` skill**.

---

## P0 pilot: player value pages (the proof)

**URL:** `vaultfantasy.com/players/jamarr-chase/` (one canonical page per player; target dynasty + redraft + SF/1QB on-page rather than splitting into cannibalizing URLs).

**Template (each section is real data, not swapped variables):**
- **H1:** "Ja'Marr Chase — Dynasty & Redraft Trade Value (2026)"
- **Unique intro, generated from the data:** e.g. "Ja'Marr Chase is the dynasty superflex WR1, up 4% over the last 30 days…" — different sentence per player, driven by their real numbers.
- **Real-market value** across formats (dynasty SF/1QB, redraft), with a format toggle.
- **ADP + movers** (7/30/90-day trend from our snapshots).
- **The killer section — "What he's actually traded for":** real comps pulled from the trade corpus. No competitor page has this.
- **Grade Keys** (Upside / Floor / Risk / Fit), age, position/overall rank, tier.
- **Related players** (internal links: same position tier, players he's traded alongside) — hub-and-spoke, no orphans.
- **CTA:** "See Chase's value in *your* league → connect a league" (free). Ties every page to the activation north star.
- **Schema:** `Person`/`SportsPerson` + `Dataset`/`FAQPage` JSON-LD; unique `<title>` and meta per page.

**Quality gate (critical):** only generate a page when the player has enough real trade/ADP data for the sections to be substantive. Obscure players with thin data get skipped or `noindex` — 300 great pages beat 3,000 thin ones.

**Hub:** `/players/` browsable index (by position, by tier) so every spoke is reachable and crawlable; add a `sitemap-players.xml`.

---

## Guardrails (avoid the penalties this skill warns about)

- **Unique value per page** — enforced by the "what he traded for" + generated intro; never just a name swap.
- **No cannibalization** — one canonical URL per player; multiple keywords on one rich page.
- **Quality over quantity** — data-gated generation, `noindex` the thin tail.
- **Free-season messaging** — pages are content with a connect-a-league CTA; never market price.
- **Freshness** — regenerate on the existing cron; stale sports data ranks poorly and misleads users.

---

## Phasing

- **Phase 0 (2–3 wks):** build the generator + template + hub + `sitemap-players.xml`; ship top ~300 players; submit to Search Console; measure indexation and first rankings. Validates the whole approach with our best asset.
- **Phase 1:** competitor-alternative + "best … calculator" pages (P1) — fastest commercial wins on a young domain.
- **Phase 2:** ADP + rookie-pick pages (P2), timed to draft/rookie season.
- **Phase 3:** gated player-vs-player long-tail + glossary (P3).

---

## Prerequisites & honest risks

- **Google Search Console** must be set up (verify the domain) or we're blind on indexation/rankings. Pairs with the activation-analytics thread so we can attribute organic → connect-a-league.
- **New-domain authority is ~zero.** Head terms ("dynasty trade value") take months and heavy competition. **Competitor-alternative and long-tail pages rank first** — that's why P1 is weighted early despite lower volume.
- **Build integration** — the generator must run in the Pages build / cron without bloating the repo or the SPA.

## Success metrics
Indexed page count (GSC coverage) → impressions/clicks by page type → **connect-a-league conversions from organic** (the one that matters; needs GSC + activation analytics).
