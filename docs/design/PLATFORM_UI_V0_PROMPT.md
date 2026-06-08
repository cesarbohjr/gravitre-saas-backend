# Gravitre Platform UI — v0 Design Prompt (Tiers 1–5)

Use this in [v0.dev](https://v0.dev) as a **senior product designer + frontend engineer** brief. The backend for Tiers 1–5 is largely complete; your job is to make the platform **discoverable, polished, and operator-friendly** — not to invent new APIs.

**Companion docs:** `ENTERPRISE_UI_V0_PROMPT.md` (enterprise admin polish), `POST_TIER5_BACKLOG.md` (UI gap list).

---

## Product context

**Gravitre** is an enterprise AI operations console: connect SaaS apps, build automations (workflows), deploy AI agents, approve high-risk runs, and monitor integration health. Users are RevOps, IT admins, CS teams, and department operators — not developers reading API docs.

**Stack (do not change):** Next.js App Router, React 19, TypeScript, Tailwind v4, shadcn/ui, SWR, `apps/web/lib/api.ts`.

**Visual baseline:** Dark-first navy (`#0B0F14` bg, `#11161D` surfaces), Geist typography, org-overridable `--primary`. Professional, dense admin UI — not marketing fluff.

---

## What exists today (implementation overview for v0)

### Tier 1 — Integration platform (30 days) ✅

| Capability | Backend | Frontend today |
|------------|---------|----------------|
| Unified `invoke_tool` + agent permissions | ✅ | Agent tool permissions implicit in agent setup |
| Real connector OAuth (HubSpot, Zendesk, GitHub, …) | ✅ | `/connectors` — functional but crowded |
| HubSpot 5 core actions + inbound triggers | ✅ | Connector detail pages |
| Cross-agent handoff bus + `next_agent_id` routing | ✅ | Workflow builder metadata; no handoff viz |
| Workflow builder persistence | ✅ | `/workflows/[id]/builder` — baseline graph UI |
| Department-scoped RAG | ✅ | `/sources`, agent knowledge tabs |

### Tier 2 — Department expansion (90 days) ✅

| Capability | Backend | Frontend today |
|------------|---------|----------------|
| Salesforce, QuickBooks, Stripe, Jira, PagerDuty | ✅ | Listed on `/connectors` |
| DevOps cross-tool workflow templates | ✅ | Generic workflow list |
| Notion / Confluence / CRM → RAG sync | ✅ | Sources + training |
| Workflow cron schedules | ✅ | `/workflows/[id]/schedules` — basic |
| Council → workflow branch | ✅ | No council decision UI |
| Agent memory API | ✅ | `/agents/[id]/memory` — basic |

### Tier 3 — Enterprise & marketplace (6 months) ✅

| Capability | Backend | Frontend today |
|------------|---------|----------------|
| NetSuite, Workday, Marketo, Segment, LinkedIn | ✅ | Connectors only |
| Connector SDK + partner submission | ✅ | `/marketplace/submit`, `/marketplace/admin` |
| Marketplace sandbox demo | ✅ | `/marketplace/sandbox` |
| Private signed connector bundles | ✅ | `/marketplace/private` |
| Partner billing (Stripe Connect) | ✅ | `/marketplace/billing` |

### Tier 4 — Enterprise scale (12 months) ✅

| Capability | Backend | Frontend today |
|------------|---------|----------------|
| Data residency, white-label branding, SSO/SCIM | ✅ | `/settings/enterprise` tabs (baseline) |
| Workforce analytics + cost attribution | ✅ | Enterprise Workforce + Cost tabs |
| Autonomous run budgets | ✅ | Enterprise Budgets tab |
| HIPAA BAA + PHI controls | ✅ | Enterprise HIPAA tab |
| EU AI Act transparency logs | ✅ | Enterprise Transparency tab |
| SIEM export | ✅ | Enterprise SIEM tab |
| SOC2 export, execution region | ✅ | API only / minimal |
| Fine-tuning → agent runtime | ✅ | `/training` — separate flow |
| Durable workflow queue (Redis) | ✅ | Invisible to user (good) |

### Tier 5 — Autonomous workforce & vertical scale (18 months) ✅

| Capability | Backend | Frontend today |
|------------|---------|----------------|
| Policy-gated auto-execute, interrupt, rollback | ✅ | Run detail partial; no interrupt button UX |
| Compensating transactions | ✅ | No rollback timeline UI |
| Healthcare / Legal / Real estate vertical packs | ✅ | API install only (`POST /api/verticals/*/install`) |
| B2B federation, delegated tasks, federated consent | ✅ | **No UI** |
| Multi-agent swarm coordinator | ✅ | **No UI** |
| Workflow digital twin (simulate) | ✅ | **No UI** in builder |
| Department role marketplace (4 packs) | ✅ | `/marketplace/role-packs` — **functional baseline** |
| Predictive workflow failure alerts | ✅ | Listed on CS dashboard only |
| Integration suggestions from audit | ✅ | CS dashboard scan + list |
| Customer integration health score | ✅ | CS dashboard — **functional baseline** |

### Recently wired (post–Tier 5, baseline quality)

- **CS Dashboard** — `/settings/enterprise?tab=cs` (default tab): health ring, 4 dimensions, suggestions, failure alerts, snapshot/history
- **Role packs** — `/marketplace/role-packs`: catalog cards, connector checklist, install button
- Sidebar: **BUILD → Role packs**, **SETTINGS → Enterprise**

---

## Design mission

Transform Gravitre from **“API-complete, UI-functional”** to **“enterprise-grade, self-explanatory.”** Every Tier 5 capability should have a **visible front door** with clear next actions, empty states, and success feedback.

**Do not** change API contracts. **Do** propose component structure under `apps/web/components/` matching existing patterns.

---

## Priority 1 — CS Command Center (elevate `/settings/enterprise?tab=cs`)

**APIs (existing):**

| Endpoint | Purpose |
|----------|---------|
| `GET /api/enterprise/integration-health?lookbackDays=30` | `{ score, grade, dimensions, risks, weights, computedAt }` |
| `POST /api/enterprise/integration-health/snapshot` | Persist trend point |
| `GET /api/enterprise/integration-health/history?limit=30` | `{ snapshots[] }` |
| `GET /api/enterprise/integration-suggestions?status=open` | Audit-driven recommendations |
| `POST /api/enterprise/integration-suggestions/scan?lookbackDays=30` | Refresh suggestions |
| `POST /api/enterprise/integration-suggestions/{id}/dismiss` | Dismiss |
| `GET /api/workflows/failure-predictions?status=open` | Pre-failure alerts |
| `POST /api/workflows/{workflowId}/failure-predictions/scan` | Scan workflow |
| `POST /api/workflows/failure-predictions/{alertId}/dismiss` | Dismiss |

**Design goals:**

- **Hero:** Large animated score ring (healthy / at-risk / critical color system), grade badge, last updated, primary CTA “Record snapshot”
- **Dimension grid:** 2×2 cards with icon, score bar, summary, drill-down drawer on click
- **Trend panel:** Real line chart from `history.snapshots` (not placeholder SVG); show delta vs 7 days ago
- **Recommendations feed:** Card stack ranked by `priority`; icons by `suggestionType` (connect / install pack / automate); inline CTAs to `/connectors`, `/marketplace/role-packs`, workflow builder
- **Failure alerts:** Severity-colored left border; group by `workflowId`; “Scan all workflows” batch action
- **Empty states:** Illustration + “Run first scan” when no audit data
- **Mobile:** Stack sections; sticky “Refresh all” bar

---

## Priority 2 — Department Role Packs (elevate `/marketplace/role-packs`)

**APIs:**

| Endpoint | Purpose |
|----------|---------|
| `GET /api/marketplace/role-packs` | `{ packs[] }` with `connectorChecklist`, `installed`, tags |
| `POST /api/marketplace/role-packs/{packId}/install` | One-click install (admin) |

**Design goals:**

- **Catalog layout:** 2-column cards with department color accent (Sales=blue, Marketing=purple, Support=green, Finance=amber)
- **Pack preview:** Expandable “What you get” — agents, workflow name, RAG sources (icons + counts)
- **Connector checklist:** Progress ring `requiredConnectorsConnected / requiredConnectorsTotal`; blocked install state with clear “Connect HubSpot first” path
- **Post-install success:** Confetti-subtle toast + links to installed agents/workflows
- **Compare packs** table for CS teams choosing Sales vs Marketing ops

---

## Priority 3 — Workflow Builder intelligence panel

**APIs:**

| Endpoint | Purpose |
|----------|---------|
| `POST /api/workflows/digital-twin` | Simulate run; `{ runId, status, steps[], fixtureHits, llmPredictions }` |
| `POST /api/workflows/{workflowId}/failure-predictions/scan` | Pre-run risk scan |
| `GET /api/workflows/failure-predictions?workflowId=` | Open alerts for workflow |

**Design goals:**

- **Right drawer** on `/workflows/[id]/builder`: tabs **Simulate** | **Risk scan** | **Dry run**
- **Simulate tab:** Run digital twin; step timeline with predicted outputs, fixture vs LLM badges, risk callouts per step
- **Risk scan tab:** Score + alert list before Execute; “Fix connector auth” deep links
- **Primary actions:** “Simulate safely” (outline) vs “Run live” (solid, requires approval if gated)
- Visual: twin steps use dashed border + “predicted” badge; live steps solid

---

## Priority 4 — Federation & B2B partner hub (new page)

**APIs (backend shipped, no UI yet):**

| Area | Typical paths |
|------|----------------|
| Partnerships | `/api/federation/partnerships` |
| Cross-org handoffs | `/api/federation/handoffs` |
| Delegated external tasks | `/api/federation/delegated-tasks` |
| Federated connector consent | `/api/federation/connectors/consent` |

**Proposed route:** `/settings/federation` or `/partners`

**Design goals:**

- **Partner cards:** Org name, trust status, shared connector scopes
- **Handoff timeline:** Cross-org task delegation with status (pending → accepted → completed)
- **Consent wizard:** Step-by-step federated connector approval
- Empty state: “Invite a partner organization” CTA

---

## Priority 5 — Agent swarm coordinator (new UI)

**APIs:** `/api/agent-swarm/*` (multi-agent runs, subtasks, council aggregation)

**Proposed surface:** Panel on `/assignments/[id]` or `/operator`

**Design goals:**

- **Swarm run graph:** Parent task → sub-agent nodes with live status
- **Council aggregation:** Vote/confidence visualization when swarm completes
- **Controls:** Start swarm, cancel, view audit trail

---

## Priority 6 — Vertical industry packs hub (new page)

**APIs:**

| Endpoint | Purpose |
|----------|---------|
| `POST /api/verticals/healthcare/install` | FHIR sandbox + prior-auth workflow |
| `POST /api/verticals/legal/install` | Clio + intake workflow |
| `POST /api/verticals/real-estate/install` | Listing workflow + agents |

**Proposed route:** `/marketplace/verticals` or section on role-packs page

**Design goals:**

- **Industry tiles:** Healthcare, Legal, Real Estate with compliance badges (HIPAA, Clio, HubSpot/SF)
- **Install wizard:** Prerequisites checklist (connector connected?) → install → open workflow
- **Legal pack:** Prominent Clio OAuth status indicator

---

## Priority 7 — Connectors hub refresh (`/connectors`)

**Context:** 30+ connector types from Tiers 1–4; current page is utilitarian.

**Design goals:**

- **Category tabs:** CRM · Support · DevOps · Finance · HR · Marketing · Data
- **Connection health:** Green/amber/red from auth status; “Reconnect” inline
- **Search + filter:** By department pack requirement, by “used in workflows”
- **Recommended row:** Pull from `integration-suggestions` API — “Connect HubSpot — 60% of your tasks are manual”
- **Card hover:** Shows available actions count + last sync

---

## Priority 8 — Run & approval experience (Tier 5 autonomous)

**APIs:** Run interrupt, compensation/rollback, approval queue

**Design goals:**

- **`/runs/[id]`:** Interrupt button (in-flight), rollback timeline for compensating transactions, policy gate explanation
- **`/approvals`:** Mobile-first card queue; swipe approve/reject; SLA countdown from approval latency metrics
- **Autonomous badge:** When run was auto-executed vs manual trigger

---

## Priority 9 — Enterprise admin polish

Extend `ENTERPRISE_UI_V0_PROMPT.md` scope:

- Branding **live preview** split panel
- DNS verification **stepper** with copy-to-clipboard records
- Workforce KPI **sparklines** (placeholder until time-series API)
- HIPAA / Transparency tabs: export buttons with progress states
- Unify sub-nav with CS Dashboard tab in one cohesive **Enterprise** hub

---

## Cross-cutting UX requirements

1. **Empty states everywhere** — every new panel explains what to do first
2. **Toast + inline success** — install, scan, snapshot, dismiss all confirm visually
3. **Severity language** — map backend `grade`, `severity`, `priority` to consistent color tokens
4. **Deep linking** — suggestions link to connectors, packs, workflows, CS dashboard
5. **Admin vs viewer** — lock icons + upgrade CTAs for non-admin actions
6. **Loading:** skeleton per section, never full-page spinner on tab switch
7. **Accessibility:** WCAG AA, focus rings, aria labels on icon buttons

---

## Out of scope for v0

- New backend endpoints or schema changes
- Logo file upload to storage (URL only)
- Multi-tenant operator cross-org dashboard (Tier 6)
- Mobile native apps

---

## Deliverables (what to generate in v0)

1. **CS Command Center** — full page redesign (`components/enterprise/cs-dashboard-tab.tsx` replacement)
2. **Role Packs catalog** — premium marketplace cards
3. **Workflow builder drawer** — Simulate + Risk scan panels (mock API responses OK in v0)
4. **Federation hub** — new page wireframe with realistic empty + populated states
5. **Connectors hub** — categorized grid with health badges
6. Component specs using shadcn: `Card`, `Badge`, `Alert`, `Dialog`, `Sheet`, `Tabs`, `Progress`, `Chart`

---

## Reference files in repo

| Area | Path |
|------|------|
| CS dashboard (baseline) | `apps/web/components/enterprise/cs-dashboard-tab.tsx` |
| Role packs (baseline) | `apps/web/app/marketplace/role-packs/page.tsx` |
| Enterprise hub | `apps/web/app/settings/enterprise/page.tsx` |
| Connectors | `apps/web/app/connectors/page.tsx` |
| Workflow builder | `apps/web/app/workflows/[id]/builder/page.tsx` |
| Run detail | `apps/web/app/runs/[id]/page.tsx` |
| API client | `apps/web/lib/api.ts` |
| App shell + sidebar | `apps/web/components/gravitre/app-shell.tsx`, `sidebar.tsx` |
| Backlog | `docs/integration/LINEAR_INTEGRATION_BACKLOG.md` |

---

## Prompt shortcut for v0 chat

> Design a premium dark enterprise UI for Gravitre Operator AI. Backend Tiers 1–5 are complete (connectors, workflows, agents, marketplace, enterprise compliance, CS health dashboard, role packs). Focus on: (1) CS Command Center with health score ring, trend chart, recommendations feed, failure alerts; (2) Department role pack catalog with connector checklist progress; (3) Workflow builder side panel for digital twin simulation and pre-run failure scan; (4) Federation partner hub; (5) Connectors hub with categories and health status. Next.js + shadcn + Tailwind v4, navy `#0B0F14`, Geist font. Use existing API contracts only. Make empty states, severity colors, and CTAs delightful and obvious.
