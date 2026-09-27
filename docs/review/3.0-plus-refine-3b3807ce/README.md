# Gravitre 3.0 Plus — refinement pass (code SHA 3b3807ce)

VISUAL_ACCEPTANCE: **not final** — awaiting Cesar's review. Not merged, not deployed, not propagated to other routes.

## Identity

| Set | Images | Branch | Code SHA | Build | Server | Data |
| --- | --- | --- | --- | --- | --- | --- |
| Harness | 01–17 | `feat/gravitre-3.0-plus-frontend` | `3b3807ceb3f7b6bd7a186cfe245b9c972112d97a` | dev (no build ID) — `next dev :3001`, same `apps/web` tree as the commit | `/e2e/shots/*` | **FIXTURE** — fictional Northwind data from `lib/e2e-shot-fixtures.ts`; AI reply is a mocked `/api/chat` stream prefixed "FIXTURE REPLY" |
| Test tenant | 18–19 | `feat/gravitre-3.0-plus-frontend` | `3b3807ceb3f7b6bd7a186cfe245b9c972112d97a` | `JOx3GE_rgL0q3NgT-hXuP` — `next build` + `next start :3000` | `/home`, `/assignments` | **TEST TENANT** — E2E billing fixture account against production auth/API; not owner-live |

Viewports: 1440×900, 1024×768, 834×1112, 390×844. Theme per filename.

## Images

| # | File | Surface | Viewport | Theme | Class |
| --- | --- | --- | --- | --- | --- |
| 01 | `01-dashboard-1440-light.png` | Dashboard | 1440 | light | fixture |
| 02 | `02-dashboard-1440-dark.png` | Dashboard | 1440 | dark | fixture |
| 03 | `03-assignments-1440-light.png` | Assignments | 1440 | light | fixture |
| 04 | `04-assignments-1440-dark.png` | Assignments | 1440 | dark | fixture |
| 05 | `05-ai-start-1440-dark.png` | AI workspace — objective start | 1440 | dark | fixture |
| 06 | `06-ai-waiting-1440-dark.png` | AI workspace — mid-turn (stream delayed) | 1440 | dark | fixture / mocked stream |
| 07 | `07-ai-answered-1440-light.png` | AI workspace — answered | 1440 | light | fixture / mocked stream |
| 08 | `08-intelligence-1440-light.png` | Intelligence — field | 1440 | light | fixture |
| 09 | `09-intelligence-evidence-1440-light.png` | Intelligence — node selected, evidence rail | 1440 | light | fixture |
| 10 | `10-intelligence-evidence-1440-dark.png` | Intelligence — node selected, evidence rail | 1440 | dark | fixture |
| 11 | `11-dashboard-1024-light.png` | Dashboard | 1024 | light | fixture |
| 12 | `12-intelligence-1024-dark.png` | Intelligence | 1024 | dark | fixture |
| 13 | `13-assignments-834-light.png` | Assignments (lane scroll) | 834 | light | fixture |
| 14 | `14-dashboard-834-dark.png` | Dashboard (lane scroll) | 834 | dark | fixture |
| 15 | `15-dashboard-390-light.png` | Dashboard (lane tabs) | 390 | light | fixture |
| 16 | `16-assignments-390-dark.png` | Assignments (phase tabs) | 390 | dark | fixture |
| 17 | `17-intelligence-390-light.png` | Intelligence (relationship paths) | 390 | light | fixture |
| 18 | `18-tenant-dashboard-1440-light.png` | Dashboard, real route | 1440 | light | test tenant |
| 19 | `19-tenant-assignments-1440-dark.png` | Assignments, real route (empty tenant) | 1440 | dark | test tenant |

The dev-only "1 Issue" badge in some harness images is the pre-existing CSP block of `va.vercel-scripts.com` in `next dev`.
