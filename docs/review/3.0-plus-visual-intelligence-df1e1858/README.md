# 3.0 Plus: AI-native component + visual intelligence pass

Images first. Every row states route, viewport, theme and evidence class. Nothing here is owner-live or production data. Not merged, not deployed. OWNER_LIVE_ACCEPTANCE = NOT_RUN.

- Branch `feat/gravitre-3.0-plus-frontend`
- AFTER: code SHA `df1e18581c9ef4ba06e890d1a64e7d2e67f70f17`, build `QmVxsTJ-dsX3aLACR5iAi`, `next start` on `127.0.0.1:3010`, built with `PLAYWRIGHT_E2E=1`
- BEFORE (dashboard, agent detail): code SHA `3a76a630` plus only the new harness route `app/e2e/shots/agent-detail/page.tsx` and the updated shot fixtures (no product code), build `goTy_G31gkd9wZQVXIQHn`, port 3011
- BEFORE (connectors, agents, builder): the committed identity set `3.0-plus-identity-976451be/after` (visual state unchanged at `3a76a630`, which only moved the logo fallback out of render)
- Capture script: `apps/web/scripts/capture-visual-intelligence.mjs`; per-shot console errors and horizontal-scroll probe in `after/manifest.json`. The only console error on every shot is the Vercel Insights script 404 on localhost.
- Evidence class: `fixture harness` = `/e2e/shots/*` rendering the real page with `lib/e2e-shot-fixtures.ts` (labelled FIXTURE); `internal board` = `/dev/carbon-board`, placeholder content, charts tagged "Placeholder data" on screen.

## 1. Connectors (`/e2e/shots/connectors`, fixture harness)

| View | Viewport | Theme | Before | After |
| --- | --- | --- | --- | --- |
| Overview | 1440 | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/H-connectors-overview-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/connectors-light.png) |
| Overview | 1440 | dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/H-connector-list-dark.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/connectors-dark.png) |
| Discovery strip | 1440 | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/G-connector-discovery-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/connectors-discovery-light.png) |
| Discovery strip | 1440 | dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/G-connector-discovery-dark.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/connectors-discovery-dark.png) |
| Attention + connected list | 1440 | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/H-connector-list-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/connectors-list-light.png) |
| Inspector (HubSpot selected) | 1440 | light | — (no inspector before) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/connectors-inspector-light.png) |
| Inspector (HubSpot selected) | 1440 | dark | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/connectors-inspector-dark.png) |
| Tablet | 1024 | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/connectors-tablet-light.png) |
| Mobile | 390 | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/connectors-mobile-light.png) |

## 2. Agents (`/e2e/shots/agents`, `/e2e/shots/agent-detail`, fixture harness)

| View | Viewport | Theme | Before | After |
| --- | --- | --- | --- | --- |
| Roster ("1 working" contrast) | 1440 | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/I-agents-roster-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/agents-roster-light.png) |
| Roster | 1440 | dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/I-agents-roster-dark.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/agents-roster-dark.png) |
| Agent detail | 1440 | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/before/agent-detail-before-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/agent-detail-light.png) |
| Agent detail | 1440 | dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/before/agent-detail-before-dark.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/agent-detail-dark.png) |
| Autonomy and access panel | 1440 | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/agent-autonomy-light.png) |
| Autonomy and access panel | 1440 | dark | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/agent-autonomy-dark.png) |
| Agent detail | 390 | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/agent-detail-mobile-light.png) |

## 3. Dashboard (`/e2e/shots/home`, fixture harness; ops-summary fixture)

| View | Viewport | Theme | Before | After |
| --- | --- | --- | --- | --- |
| Operating Flow first, Measure below | 1440 | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/before/dashboard-before-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/dashboard-light.png) |
| Dashboard | 1440 | dark | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/dashboard-dark.png) |
| Outcome flow sankey (end of Measure) | 1440 | light | — (not present) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/dashboard-outcome-flow-light.png) |
| Outcome flow sankey | 1440 | dark | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/dashboard-outcome-flow-dark.png) |
| Tablet | 1024 | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/dashboard-tablet-light.png) |
| Mobile | 390 | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/dashboard-mobile-light.png) |

## 4. Builder node family (`/e2e/shots/builder`, fixture seed graph, 1440x900)

| View | Theme | Before | After |
| --- | --- | --- | --- |
| Canvas | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/A-builder-desktop-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/builder-light.png) |
| Canvas | dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/B-builder-desktop-dark.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/builder-dark.png) |
| Council selected | light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/E-council-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/builder-council-selected-light.png) |
| Council selected | dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/ba825a09048da61df5b551b4639bea1705d5ddbf/docs/review/3.0-plus-identity-976451be/after/E-council-dark.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/builder-council-selected-dark.png) |
| Decision selected (2 real branches) | light | — (no decision in seed) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/builder-decision-selected-light.png) |
| Tablet 1024 | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/builder-tablet-light.png) |
| Mobile 390 | light | — | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/builder-mobile-light.png) |

Node crops (unselected):

| Node | Light | Dark |
| --- | --- | --- |
| Source | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-source-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-source-dark.png) |
| Agent | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-agent-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-agent-dark.png) |
| Task | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-task-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-task-dark.png) |
| Decision | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-decision-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-decision-dark.png) |
| Council | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-council-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-council-dark.png) |
| Approval | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-approval-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-approval-dark.png) |
| Connector | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-connector-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/node-connector-dark.png) |

## 5. AI-native primitives + Evil Charts (`/dev/carbon-board`, internal board, placeholder content)

| Theme | Capture |
| --- | --- |
| light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/board-ai-native-light.png) |
| dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-visual-intelligence-df1e1858/after/board-ai-native-dark.png) |

## 6. Accessibility (axe-core, WCAG 2.1 A/AA tags, build `QmVxsTJ-dsX3aLACR5iAi`)

`after/axe-results.json`: 0 violations on `/e2e/shots/connectors`, `/e2e/shots/agents`, `/e2e/shots/agent-detail`, `/e2e/shots/home`, `/e2e/shots/builder`, `/dev/carbon-board`, each in light and dark color scheme. The board has its own theme toggle, so its dark-scheme axe run scans the board's light rendering; the board dark capture above is visual only.

## 7. Real vs fixture

- Product code reads only real fields: connector `availability` + action catalog + `/api/agents` permissions; agent identity policy (`GET /api/agents/{id}/identity`) + capability profile (`/capabilities`); outcome ledger rollup (`/api/workflows/execution-outcomes/ops-summary`, `by_connector` counts).
- Every value in these captures comes from `lib/e2e-shot-fixtures.ts` (labelled FIXTURE) or the board (labelled placeholder on screen). The connector action catalog fixture is exported from the backend catalog by `apps/web/scripts/export-shot-action-catalog.py`.
- Agent strength radar: not drawn in product. No per-dimension agent scores exist; agent detail states "Not measured".
