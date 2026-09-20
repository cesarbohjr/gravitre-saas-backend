# Gravitre 3.0 — Product Walkthrough & UX Validation

**Date:** 2026-09-20  
**Method:** Code-route discovery + component audit + harness evidence. **Authenticated live click-through: NOT RUN** (explicit gap).  
**Scope:** Authenticated app (`apps/web/app`, excluding `(marketing)` and `/dev/*` except harness reference).

---

## Route inventory summary

**~90 authenticated routes** across WORK, BUILD, ACTIVITY, INTELLIGENCE, MARKETPLACE, SETTINGS, LITE.  
Auth gate: `apps/web/proxy.ts`. Shell: `AppShell` + `GravitrePageHeader` on most hubs.

Full inventory: see audit agent output in program board section C; canonical nav in `components/gravitre/sidebar-nav-config.ts`.

---

## Journey walkthroughs (code-informed)

### LOGIN → HOME

| Step | Expected | Actual (code) | Friction | Priority |
|------|----------|---------------|----------|----------|
| Login | Redirect to welcome or home | Supabase auth via proxy | — | — |
| Home | Situation awareness, next actions | `HomeDashboard` widgets, trends | Generic dashboard template; icon tile header | M |
| Start work | Clear path to Chat or Agents | Shortcuts exist | Multiple equal-weight entry points (Chat, Agents, Assignments, Goals) | M |

**Smells:** GENERIC PAGE INTRO (GravitrePageHeader on home).

---

### HOME → AI (Chat)

| Step | Expected | Actual | Friction | Priority |
|------|----------|--------|----------|----------|
| Sidebar "Chat" | Unified AI workspace | `/ai` → `AiWorkspace` | Label "Chat" vs product term "Gravitre AI" | L |
| Empty state | Identity + composer | Phase 2 simplified | Still chat-bubble SaaS visually | H |
| Operator task | Governance visible | Command OS in source | Transcript doesn't show trace/signal | H |

**Smells:** DUPLICATE MENTAL MODEL (Chat vs Ask Gravitre vs Agent chat — same runtime, different names).

---

### HOME → AGENT → DETAIL → CHAT

| Step | Expected | Actual | Friction | Priority |
|------|----------|--------|----------|----------|
| Agents hub | Find teammate | TEAM default fleet | "Build with Meson" competes with roster | M |
| Agent detail | Config + runs | Text nav; cards on detail | Avatar orbs on editor paths | M |
| Agent chat | Scoped conversation | Summons fullscreen workspace | Route name "chat" again | L |

---

### HOME → WORKFLOW → CREATE → RUN → RESULT

| Step | Expected | Actual | Friction | Priority |
|------|----------|--------|----------|----------|
| Workflows list | Find/run | Table-first | Conventional table; header actions "Create from Goal" + "Build with Meson" | M |
| Builder | Intent + canvas | Meson builder + TRACE overlay | Badge density; live **NOT PROVEN** | M |
| Workflow detail | Inspect runs | **~28 Cards** on `[id]/page` | **REGRESSED vs Reset 2.0 flatten goal** | H |
| Result | Activity/run trace | `/activity`, `/runs/[id]` | "View in Gravitre" label ambiguous | M |

**Smells:** UNNECESSARY CARD (workflow detail); AMBIGUOUS LABEL ("View in Gravitre" in `chat-execution-panel.tsx`).

---

### HOME → CONNECTOR → DISCOVER → CONNECT → MANAGE

| Step | Expected | Actual | Friction | Priority |
|------|----------|--------|----------|----------|
| Connectors hub | Discovery then management | Model B: strip + list | Page very large (`connectors/page.tsx` ~3k lines) | M |
| Browse all | Discovery | Button + strip | OK | L |
| Check live status | Health | Toolbar action | Generic label — user may not know scope | M |
| Detail | Connection ops | **Card-heavy** `[id]/page` | **NOT STARTED flatten** | H |

**Smells:** OVERBUILT REGION (monolithic connectors page); VISUAL DEAD SPACE (management pane right side on wide screens — opportunity for topology context).

---

### HOME → INTELLIGENCE → LEARNING / RELATIONSHIP / EVIDENCE

| Step | Expected | Actual | Friction | Priority |
|------|----------|--------|----------|----------|
| Intelligence hub | System knows / matters | Map + pillars + Ask surface | Supporting sections still column/card quiet | **H** |
| Learning | What changed | `LearningStage` flattened IA | Expert workspace polish open | M |
| Relationships | Graph + evidence | Graph default | Live session **NOT PROVEN** | M |
| Performance | Diagnostic | Outcome-first | No instrumented waterfall yet | M |

**Smells:** UNDERDESIGNED REGION (intelligence sophistication vs runtime); GENERIC SaaS (header + grids).

---

### HOME → ACTIVITY → FAILED RUN → EVIDENCE → RETRY

| Step | Expected | Actual | Friction | Priority |
|------|----------|--------|----------|----------|
| Activity | Execution observability | Two-pane inspector, good direction | Trace story not yet canonical TRACE primitive everywhere | H |
| Failure tab | Alerts | `FailureAlertsPanel` | — | L |
| Run detail | Where/why failed | `/runs/[id]` outcome + trace params | Deep link `?trace=1` — expert-only | M |
| Retry/fix | Obvious next action | Contextual actions vary by type | Not unified recovery pattern | M |

**Smells:** INCONSISTENT TERMINOLOGY (Activity vs Runs vs Outcomes redirects).

---

### HOME → APPROVAL → UNDERSTAND → APPROVE

| Step | Expected | Actual | Friction | Priority |
|------|----------|--------|----------|----------|
| Queue | Decision-first | Queue until selection | Reset 2.0 pattern present | L |
| Inspector | Evidence for decision | Gated on selection | Live click **NOT PROVEN** | M |
| Primary CTA | Approve only primary | Approve primary, Reject secondary | "Estimated confidence" labeling | L |

---

### HOME → SOURCE → ADD → INSPECT

| Step | Expected | Actual | Friction | Priority |
|------|----------|--------|----------|----------|
| Sources list | Infrastructure health | KPI row + **source cards** + mini metrics | **Card-in-card debt** | **H** |
| Add source | Modal flow | `AddDataSourceModal` | OK | L |
| Detail | Inspector model | `[id]/page` mixed patterns | Not infrastructure-first | H |

**Smells:** UNNECESSARY CARD; DUPLICATE METRICS (KPI + per-card metrics).

---

### HOME → MARKETPLACE → DISCOVER → INSTALL

| Step | Expected | Actual | Friction | Priority |
|------|----------|--------|----------|----------|
| Discovery | Premium catalog | Tiles + authorized PriceBadge | Large tiles, tag volume, heavy visually | H |
| Installed | Ops list | Separate route — good | Must not look like discovery cards | M |
| Install | Clear entitlement | Commerce authorized in doc | Live install **NOT PROVEN** | M |

---

## Button / action audit (significant actions)

| Label | Location | Function | Primary? | Issues | AI replace? |
|-------|----------|----------|----------|--------|-------------|
| Ask Gravitre | Intelligence, Activity, Agents headers | Summon AI workspace | Secondary | Duplicated entry pattern | N — but unify affordance |
| Build with Meson | Agents, Workflows | Open Meson wizard | Secondary | Jargon for new users | No — rename/explain in copy audit |
| Create from Goal | Workflows, command palette | Goal wizard | Secondary | Overlaps Goals nav | Partial — command OK |
| Browse all | Connectors | Expand discovery | Tertiary | OK | No |
| Check live status | Connectors | Health probe | Tertiary | **Ambiguous scope** | Could infer on page load |
| View in Gravitre | Chat execution panel | Deep link | Tertiary | **Ambiguous** — View what? | Contextual label needed |
| Approve | Approvals | HITL approve | **Primary** | Correct pattern | No |
| Open / View / Manage | Various tables | Navigation | Varies | Generic labels — audit per route | Often yes via command |

**Generic label hotspots:** OPEN, VIEW, DETAILS, MANAGE, CONNECT, RUN — require per-route copy pass in 3.0 (not blind rename).

---

## Navigation audit

### Left nav (icon rail ~64px)

- **14 primary items** in 5 sections — good consolidation vs 1.0  
- **Icon-only dependency:** tooltips exist but first-time learnability **weak** (prompt §33)  
- **Lite vs Full seat:** locked affordances on BUILD — correct but needs clearer explanation  

**Prototype for Cesar:** current rail vs expandable labeled rail vs contextual groups.

### Top bar

- Workspace + environment + route + search/command + Admin/Lite + launcher + notifications + profile  
- **Risk:** too many equal-weight globals — each must earn space (prompt §34)  

### Duplicate routes (legacy redirects — intentional but confusing)

| Legacy | Canonical |
|--------|-----------|
| `/assistant`, `/operator` | `/ai` |
| `/runs`, `/outcomes`, `/tasks` | `/activity` |
| `/integrations`, `/systems` | `/connectors` |
| `/intelligence/agents` | `/agents` |

**Smell:** DUPLICATE ROUTE (bookmarks/history may hit legacy URLs).

---

## UX smell register (priority)

| Smell | Examples | Severity |
|-------|----------|----------|
| PAGE TEMPLATE REPETITION | GravitrePageHeader on 50+ routes | H |
| CARD-IN-CARD | Sources, connector/workflow detail | H |
| GENERIC SaaS ADMIN | KPI row + bordered table kit | H |
| AMBIGUOUS LABEL | View in Gravitre, Check live status | M |
| DUPLICATE AI ENTRY | Ask Gravitre, header summon, intelligence bar | M |
| ICON-ONLY NAV | Sidebar rail | M |
| VISUAL DEAD SPACE | Connectors management wide layout | M |
| STATUS PILL SPRAWL | CONNECTED, ACTIVE, PRODUCTION everywhere | M |
| NOT PROVEN LIVE | Most Reset 2.0 hub claims | **Blocker for PASS** |

---

## Redundancy analysis (not assumed duplicate — domain check)

| Pair | Relationship | Recommendation |
|------|--------------|----------------|
| Activity vs Runs | Runs list retired → Activity | Keep; document in onboarding |
| Sources vs Connectors | Sources = data infra; Connectors = integrations | Keep separate; clarify IA copy |
| Models vs Intelligence models vs Model Studio | Overlapping entry points | Terminology audit + hub consolidation in 3.0 nav |
| Search (`/chat`) vs Command palette | Search = records; Command = actions+nav | Clarify naming ("Search" vs "Command") |
| Agent chat vs `/ai` | Same runtime, scoped presentation | Keep; unify language |

---

## Terminology draft (canonical — for Cesar review)

| Term | Meaning |
|------|---------|
| Agent | Autonomous operator with tools and memory |
| Workflow | Meson-orchestrated multi-step automation |
| Run | Single execution instance (shown under Activity) |
| Activity | Hub for outcomes, work objects, failures |
| Outcome | Business result of executed work |
| Work object | Tracked unit of operational work |
| Source | Customer data infrastructure |
| Connector | Third-party integration connection |
| Intelligence | Org learning, relationships, predictions |
| Evidence | Provable artifact supporting a claim/decision |
| Approval | Human gate before consequential action |

---

## Functional audit status

**NOT RUN** — this walkthrough is structural/code-based. Before any 3.0 production slice:

- Verify primary CTAs on each hub (route, loading, error, permission)  
- Deep links (`?trace=1`, `?tab=failures`, conversation `c=`)  
- Lite seat locks vs full seat BUILD surfaces  

---

## Recommendations by priority

| Priority | Item |
|----------|------|
| P0 | Authenticated journey recording + friction log with evidence |
| P0 | Complete Reset 2.0 detail flatten (connectors/workflow detail, sources cards) |
| P1 | Intelligence Field concept (replace five quiet columns) |
| P1 | Execution TRACE primitive on Activity/Runs |
| P1 | Page intro variants by job (Command, Queue, Graph, Trace…) |
| P2 | Sidebar learnability prototype |
| P2 | Command palette expansion (Go/Create/Run/Explain current page) |
| P2 | Table 3.0 + status visual hierarchy |

---

**STOP:** No production redesign authorized from this document. Prototype in `/dev/ai-workspace-preview` and future 3.0 harness extensions only.
