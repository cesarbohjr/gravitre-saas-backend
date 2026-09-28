# 3.0 Plus: final product composition

Images first. Every row states route, viewport, theme and evidence class. Nothing here is owner-live or production data. Not merged, not deployed to production. OWNER_LIVE_ACCEPTANCE = NOT_RUN.

- Branch `feat/gravitre-3.0-plus-frontend`
- AFTER: code SHA `e68e27dba878daf245c66f9f93c6082f9e4fa4fd`, build `08FOpW_YbyjBdGfSrzxEl`, `next start` on port 3012, built with `PLAYWRIGHT_E2E=1`
- BEFORE: code SHA `af9e8f47568c228fd4da216e8150a26fd0706b3b`, build `5nvk1_BIwHZ8T3Q-FihIh`
- Capture script: `apps/web/scripts/capture-final-composition.mjs`. Per-shot metrics, console errors and horizontal-scroll probe are in `before/manifest.json` and `after/manifest.json`. Console errors on every shot are the unauthenticated harness session redirect being blocked by CSP (no product signal).
- Evidence class: `fixture harness` = `/e2e/shots/*` rendering the real page with `lib/e2e-shot-fixtures.ts`. Not owner-live evidence.

## 1. Dashboard density (`/e2e/shots/home`, fixture harness)

Operating Flow desktop lanes are now content-height (min 168px, lane lists capped at 360px on `md`, 440px on `xl`) instead of a viewport-derived height. Measure follows immediately.

| Viewport | Flow height before → after | Measure top before → after |
| --- | --- | --- |
| 1440×900 | 500px → 448px | 642px → 590px |
| 1920×1080 | 680px → 401px | 822px → 543px |

| Viewport | Theme | Before | After |
| --- | --- | --- | --- |
| 1440×900 | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/before/dashboard-1440x900-light-before.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/dashboard-1440x900-light-after.png) |
| 1920×1080 | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/before/dashboard-1920x1080-light-before.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/dashboard-1920x1080-light-after.png) |
| 1920×1080 | dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/before/dashboard-1920x1080-dark-before.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/dashboard-1920x1080-dark-after.png) |
| 1024 tablet | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/dashboard-tablet-light.png) |
| 390 mobile | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/dashboard-mobile-light.png) |

## 2. Measure region (fixture harness)

KPI strip unchanged. The execution-outcome Sankey moved directly under it and stays subordinate (240px). A ruled per-system list beside it shows passed / failed / cancelled counts and pass rate = passed ÷ (passed + failed) from `ops-summary`. No revenue, savings, ROI or attribution.

| Theme | Image |
| --- | --- |
| light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/dashboard-measure-light.png) |
| dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/dashboard-measure-dark.png) |

## 3. Agent detail (`/e2e/shots/agent-detail`, fixture harness)

Main field: Autonomy and access (panel unchanged), Strength profile ("Not measured", no radar), Capabilities, Connected systems, Recent work. Rail: Reference sources, then Knowledge and learning (knowledge health, learning state, freshness, domain health, outcomes, capability visibility). Ruled sections; one column below `lg`.

| View | Before | After |
| --- | --- | --- |
| 1440 tall, light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/before/agent-detail-1440-tall-light-before.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/agent-detail-1440-tall-light-after.png) |
| 1440 tall, dark | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/agent-detail-1440-tall-dark.png) |
| 1920×1080, light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/agent-detail-1920x1080-light.png) |
| 1024 tablet | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/agent-detail-tablet-light.png) |
| 390 mobile | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/agent-detail-mobile-light.png) |

## 4. Connectors (`/e2e/shots/connectors`, fixture harness)

No selection on `xl`: the inspector region shows an operating summary built only from connector fields already on the page (executable count, attention kinds, catalog read/write counts, `availability.lastCheckedAt`). Selecting a row turns the same region into the Context Card inspector. No new column.

| View | Theme | Image |
| --- | --- | --- |
| No selection, before (1440) | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/before/connectors-1440-noselection-light-before.png) |
| No selection, after (1440) | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/connectors-1440-noselection-light-after.png) |
| No selection, list region (1440 tall) | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/connectors-1440-tall-noselection-light.png) |
| No selection, list region (1440 tall) | dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/connectors-1440-tall-noselection-dark.png) |
| Selected (1440 tall) | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/connectors-1440-tall-selected-light.png) |
| Selected (1440 tall) | dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/connectors-1440-tall-selected-dark.png) |
| No selection, 1920×1080 | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/connectors-1920x1080-light.png) |
| Tablet 1024 (summary hidden below `xl`) | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/e68e27dba878daf245c66f9f93c6082f9e4fa4fd/docs/review/3.0-plus-final-composition/after/connectors-tablet-light.png) |

The "1440 tall" element shots are cropped to the list region; the right edge of the summary is cut by the crop, not by layout (see the 1920 shot).

## 5. Accessibility

`apps/web/scripts/axe-harness-scan.mjs` (axe-core, WCAG 2.1 A/AA) on build `08FOpW_YbyjBdGfSrzxEl`: 0 violations on `/e2e/shots/{home,agent-detail,connectors,agents,builder}` and `/dev/carbon-board`, light and dark. Raw: `after/axe-results.json`.

## 6. Declaration

No new customer-facing price, claim, badge or Enable toggle. The operating summary and the pass-rate list are derived from existing runtime fields only.
