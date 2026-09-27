# 3.0 Plus: Carbon Intelligence visual maturity + Workflow Builder override

Images first. Every image states branch, SHA, build, route, viewport, theme and evidence class.
Nothing here is owner-live or production data. Not merged, not deployed.

- Branch `feat/gravitre-3.0-plus-frontend`
- Code SHA `dc5d8bbc66e201990da7f5062cccffae958f2f18` (build `-98WrvCbBjbx-_DxjoPvW`), for builder gate, design board and accessibility
- Product-route AFTER set: SHA `71a261b8e9f219a2f27941be347644f0c300e9c3` (build `DTfX6C0Yq-cS7cgfP_CRm`). The only later change, in `dc5d8bbc`, is accessibility: delete-step button names, the connector icon's `role="img"`, the builder node's method-chip ink, and ion text on ion wash in two intelligence components
- BEFORE set: SHA `94388a831062edfaab9639613beed6435d50e123` (build `0JmPKT8m4AUWx-klv8j5C`)
- Server: `next start` of the committed tree on `127.0.0.1:3010`, built with `PLAYWRIGHT_E2E=1` so the `/e2e/shots` harness is reachable

Base: `https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/`

## 1. Workflow Builder gate (fixture, `/e2e/shots/builder`, harness seed graph, no backend)

| Shot | Viewport | Theme | What it shows |
| --- | --- | --- | --- |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/01-desktop-light-overview.png) | 1440×900 | light | Left builder nav, identity bar, toolbar, canvas, inspector in Configure with the workflow overview |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/02-desktop-dark-overview.png) | 1440×900 | dark | Same, carbon |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/03-desktop-light-agent.png) | 1440×900 | light | Agent node selected (signal edge), Configure shows the agent configuration |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/04-desktop-dark-agent.png) | 1440×900 | dark | Agent node + inspector, carbon |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/05-desktop-light-connector.png) | 1440×900 | light | Connector node (PostgreSQL) + connector inspector |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/06-desktop-light-start-inputs.png) | 1440×900 | light | Start · inputs: the entry step and its configured input keys; `Start` marker on the canvas |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/07-desktop-light-end-output.png) | 1440×900 | light | End · output: the terminal step; `End` marker on the canvas |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/08-desktop-light-meson.png) | 1440×900 | light | Meson mode inside the inspector (no permanent column) |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/09-desktop-dark-meson.png) | 1440×900 | dark | Meson mode, carbon |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/10-desktop-light-trace.png) | 1440×900 | light | Run / Trace mode: trace overlay on, graph in view, per-step state list. **No run executed** (idle) |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/11-desktop-dark-trace.png) | 1440×900 | dark | Run / Trace, carbon. **No run executed** |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/12-tablet-light-overview.png) | 1024×768 | light | Tablet: nav collapses to icons, inspector 300px |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/13-tablet-light-agent.png) | 1024×768 | light | Tablet: agent selected |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/14-mobile-light.png) | 390×844 | light | Mobile: identity bar + icon toolbar, canvas |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/15-mobile-dark.png) | 390×844 | dark | Mobile, carbon |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/builder/16-mobile-light-agent-sheet.png) | 390×844 | light | Mobile: inspector folds into a sheet on selection |

Probe output per shot (inspector mode, visibility, graph-end markers, horizontal scroll) is in `builder/manifest.json`.

## 2. Design board (internal, `/dev/carbon-board`, placeholder content, dc5d8bbc)

| Light | Dark |
| --- | --- |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/board/board-1440-light.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/board/board-1440-dark.png) |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/board/board-1440-light-grayscale.png) grayscale | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/board/board-1440-dark-grayscale.png) grayscale |
| ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/board/board-390-light.png) 390 | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/board/board-390-dark.png) 390 |

## 3. Before / after, product routes (fixture tenant, E2E billing test account)

BEFORE = 94388a83 · AFTER = 71a261b8. Class: VISUAL_ACCEPTANCE (fixture tenant), not owner-live.

| Route | Viewport / theme | Before | After |
| --- | --- | --- | --- |
| Dashboard | desktop light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-light/dashboard.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-light/dashboard.png) |
| Workflows | desktop light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-light/workflows.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-light/workflows.png) |
| Approvals | desktop light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-light/approvals.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-light/approvals.png) |
| Agents | desktop light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-light/agents.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-light/agents.png) |
| Intelligence | desktop light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-light/intelligence.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-light/intelligence.png) |
| Workflow builder | desktop light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-light/workflow-builder.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-light/workflow-builder.png) |
| Connectors | desktop light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-light/connectors.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-light/connectors.png) |
| Governance | desktop light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-light/governance.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-light/governance.png) |
| Dashboard | desktop dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-dark/dashboard.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-dark/dashboard.png) |
| Workflows | desktop dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-dark/workflows.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-dark/workflows.png) |
| Approvals | desktop dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-dark/approvals.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-dark/approvals.png) |
| Intelligence | desktop dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-dark/intelligence.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-dark/intelligence.png) |
| Workflow builder | desktop dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-dark/workflow-builder.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-dark/workflow-builder.png) |
| Connectors | desktop dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/desktop-dark/connectors.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/desktop-dark/connectors.png) |
| Workflows | tablet light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/tablet-light/workflows.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/tablet-light/workflows.png) |
| Workflow builder | tablet light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/tablet-light/workflow-builder.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/tablet-light/workflow-builder.png) |
| Approvals | tablet light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/tablet-light/approvals.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/tablet-light/approvals.png) |
| Dashboard | mobile light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/mobile-light/dashboard.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/mobile-light/dashboard.png) |
| Approvals | mobile light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/mobile-light/approvals.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/mobile-light/approvals.png) |
| Workflow builder | mobile light | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/mobile-light/workflow-builder.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/mobile-light/workflow-builder.png) |
| Dashboard | mobile dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/mobile-dark/dashboard.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/mobile-dark/dashboard.png) |
| Workflows | mobile dark | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/before/mobile-dark/workflows.png) | ![](https://raw.githubusercontent.com/cesarbohjr/gravitre-saas-backend/__EVSHA__/docs/review/3.0-plus-carbon-dc5d8bbc/after/mobile-dark/workflows.png) |

## 4. Accessibility (dc5d8bbc, fixture tenant)

axe-core WCAG 2.1 A/AA, 15 routes × light/dark = 30 scans, **0 violations**. Routes: `/home`, `/workflows`, `/approvals`, `/agents`, `/activity`, `/connectors`, `/intelligence`, `/ai`, `/marketplace/assets`, `/schedules`, `/sources`, `/goals`, `/settings/approvals`, `/dev/carbon-board`, `/e2e/shots/builder`. Raw output: `axe-results.json`.

## Labels

- Builder gate: PASS for the composition (fixture harness). Run/Trace with a live execution is **NOT RUN**; the harness executes nothing, so shots 10–11 show the idle trace state.
- Product routes: VISUAL PARTIAL (fixture tenant). OWNER_LIVE: **NOT RUN**.
- Not merged, not deployed.
