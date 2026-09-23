# 02 — Route and interaction inventory (Phase 1)

Condensed from repo audit (2026-09-23). Canonical nav: `sidebar-nav-config.ts`, `app-routes.ts`.

## Route groups

| Group | Primary routes |
|-------|----------------|
| AI / Chat | `/ai`, `/ai?mode=*`, `/chat` (legacy), `/search`, `/welcome` |
| Intelligence | `/intelligence` (+ performance, learning, memory, predictive, reports, model-studio, models) |
| Workflows | `/workflows`, `/workflows/[id]`, `/workflows/[id]/builder`, `/runs/[id]`, `/schedules` |
| Agents | `/agents`, `/agents/new`, `/agents/[id]`, `/multi-agent-run`, `/training` |
| Work | `/assignments*`, `/goals*` |
| Marketplace | `/marketplace/assets` (+ installed, connectors, billing, publisher, admin…) |
| Connectors / Sources | `/connectors*`, `/sources*` |
| Home / Lite | `/home`, `/lite*` |
| Settings | `/settings*` |
| Approvals / Activity | `/activity`, `/approvals`, `/notifications`, `/audit`, `/metrics` |
| Harness | `/dev/ai-workspace-preview`, `/e2e/*` |

## Interaction inventory (core loops)

| Loop | Entry | Result surface | Notes |
|------|-------|----------------|-------|
| Ask / delegate | Ask summon, helper orb, `/ai` composer | Transcript + optional work canvas | One runtime |
| Approve WRITE | Approvals queue / in-chat chrome | Continue / reject | Functional gate |
| Inspect Intelligence | Lenses Matrix/Field, node select | Inspector / Ask | Field must regain primacy |
| Edit workflow | Builder canvas + Meson | Save → canonical nodes/edges | Custom canvas today |
| Install pack | Marketplace Install | Installed ops list | No invented prices |
| Run / Activity | Runs, Activity TRACE | Outcome / failure | TRACE grammar continues |

## Component inventory (systems)

| System | Locations |
|--------|-----------|
| AppShell / Sidebar / TopBar | `components/gravitre/app-shell.tsx`, `sidebar*.tsx`, `top-bar.tsx` |
| AI shells | `ai-workspace*.tsx`, `ai-floating-workspace.tsx`, `ai-workspace-shell.tsx`, `ai-helper.tsx` |
| Assistant panels | `components/gravitre/assistant/**` |
| Intelligence map/matrix | `components/intelligence/**` |
| Workflows | `app/workflows/**`, `components/workflows/**` |
| Design primitives | `components/ui/**`, `nodus-product/**`, `icons/nucleo/**` |

## State inventory (client)

| State | Owner | Persist |
|-------|-------|---------|
| Presentation mode | `ai-workspace-provider` | Session / URL `/ai` |
| Org selection | `org-context` localStorage | Yes — membership-validated |
| Environment | `environment-context` | Yes |
| Chat / taskState | `ai-workspace` + backend | Server authoritative |
| Intelligence lens / selection | Intelligence pages | URL deep-link partial |
| Workflow canvas nodes | Builder page + `builder-persistence` | Server on save |

## Journey inventory (must stay proven)

1. Sign-in → org ready → Home  
2. Ask → READ tool → honest answer  
3. Ask → WRITE → approval → evidence  
4. Intelligence Field/Matrix lens switch + select  
5. Workflow builder edit → save → run  
6. Marketplace install → open installed  
7. Activity / Approvals continue path  

Label remains **NOT PROVEN** until authenticated browser evidence (per standing audit rules).
