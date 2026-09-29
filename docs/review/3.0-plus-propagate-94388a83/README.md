# Gravitre 3.0 Plus — system propagation evidence

## Acceptance record (Cesar, "STRUCTURAL DIRECTION ACCEPTED — PROPAGATE THE SYSTEM")

| Gate | Status |
| --- | --- |
| STRUCTURAL_DIRECTION | ACCEPTED |
| ART_DIRECTION_FOUNDATION | ACCEPTED |
| VISUAL_ACCEPTANCE | PARTIAL (fixture evidence only; awaiting Cesar review) |
| PHASE_8 | CONTINUE |
| OWNER_LIVE_ACCEPTANCE | NOT RUN |

## Build identity

- Branch: `feat/gravitre-3.0-plus-frontend`
- Frontend SHA: `94388a831062edfaab9639613beed6435d50e123`
- Build ID: `0JmPKT8m4AUWx-klv8j5C` (`next build` of the committed `apps/web` tree, served by `next start`)
- Exact-SHA CI: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36326958061

## Evidence classes

- **FIXTURE TENANT** (files 01–28): local production build against production Supabase auth and api.gravitre.app, signed in as the E2E billing fixture test tenant (`billing-e2e+active+…@gravitre.app`). Read-only navigation. Not production customer data, not owner-live.
- **FIXTURE HARNESS** (files 29–37): `/e2e/shots/*` harness on `next dev` at the same SHA with a fixture network layer. The AI reply is a scripted SSE stream literally labelled `FIXTURE REPLY`.
- `axe-results.json`: WCAG 2.1 A/AA axe-core scan, fixture tenant, 15 routes × light/dark, 0 violations.

## Page-family map

| Family | Routes | Pattern |
| --- | --- | --- |
| Operating | `/home`, `/assignments`, `/approvals`, `/workflows`, `/goals`, `/schedules`, `/sources`, `/agents`, `/activity`, `/runs`, `/notifications`, `/outcomes` | Phase band over a ruled list; each page uses its own phases, not the dashboard lanes |
| Expert | `/intelligence/*`, `/models`, `/metrics`, `/agents/:id`, `/connectors`, `/sources/:id`, `/admin`, `/training`, `/settings/approvals` | Context rail + primary field + inspector, with progressive disclosure |
| Immersive | `/workflows/:id/builder`, `/ai`, relationship and knowledge graphs | Canvas dominates; the AI dock sits at the canvas corner |

## Captures

| File | Route | Viewport | Theme | Class |
| --- | --- | --- | --- | --- |
| 01 | /approvals | 1440 | light | fixture tenant |
| 02 | /workflows | 1440 | light | fixture tenant |
| 03 | /goals | 1440 | light | fixture tenant |
| 04 | /schedules | 1440 | light | fixture tenant |
| 05 | /sources | 1440 | light | fixture tenant |
| 06 | /agents | 1440 | light | fixture tenant |
| 07 | /activity | 1440 | light | fixture tenant |
| 08 | /intelligence/model-studio | 1440 | light | fixture tenant |
| 09 | /agents/:id | 1440 | light | fixture tenant |
| 10 | /settings/approvals | 1440 | light | fixture tenant |
| 11 | /connectors | 1440 | light | fixture tenant |
| 12 | /marketplace/assets | 1440 | light | fixture tenant |
| 13 | /workflows/:id/builder | 1440 | light | fixture tenant |
| 14 | /home | 1440 | light | fixture tenant |
| 15–21 | approvals, workflows, connectors, marketplace, model studio, builder, governance | 1440 | dark | fixture tenant |
| 22–24 | workflows, assignments, intelligence | 834 | light | fixture tenant |
| 25–28 | approvals, goals (light); intelligence, agents (dark) | 390 | mixed | fixture tenant |
| 29–31 | AI mobile sheet: start, waiting, answered (mission spine) | 390 | light/dark | fixture harness |
| 32–33 | /ai waiting, answered | 1440 | dark/light | fixture harness |
| 34–36 | assignments (390, 390 scrolled to end with dock clear, 1440) | mixed | light | fixture harness |
| 37 | intelligence evidence rail | 1440 | dark | fixture harness |

## Known open issues

- The Workflows table at 834px crushes the name column. Proposed fix, not committed: add `hidden lg:table-cell` to the Environment and Success rate columns.
- Mobile Intelligence top controls (Field/Matrix, What changed?, Graph/Changes, five counters) are still dense. Reducing them would remove working toggles, so they are left as they are.
- Mobile AI sheet: the Artifact stage does not count hosted files. `hostedFiles` is only passed to the desktop bridge, and passing it to the mobile bridge requires editing the protected `ai-workspace.tsx`.
