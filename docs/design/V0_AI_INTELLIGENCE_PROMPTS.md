# Gravitre AI Intelligence — v0 Frontend Prompts (F1–F4)

Paste these into [v0.dev](https://v0.dev). **Do not implement in Cursor.** Backend APIs referenced here are specified in Phase 3 (B3, B4, B6) — use mock data where endpoints are not live yet.

Stack: Next.js App Router, React 19, TypeScript, Tailwind v4, shadcn/ui, SWR, existing `apps/web/lib/fetcher.ts`.

Visual baseline: match production screenshots — light/dark theme support, Gravitre Labs breadcrumb shell, trial banner, Admin/Lite toggles.

---

## F1 — Meson Copilot Panel (Workflow Builder)

```
You are enhancing an existing enterprise AI platform (Gravitre) built with
Next.js, Tailwind CSS, and shadcn/ui.

DO NOT redesign anything.
FIND existing files first, then enhance.

Find and read:
- apps/web/app/workflows/[id]/builder/page.tsx
- apps/web/components/workflows/intelligence-drawer.tsx (already exists — do not duplicate)
- Any existing Sheet/Drawer patterns

Add a Meson AI Copilot panel to the workflow builder. Meson is the AI that watches
what you build and helps you build better — like GitHub Copilot for workflows.

PLACEMENT: Right side panel (280px), collapsible, slides in from the right edge
of the builder canvas. Toggle: "✨ Meson" button in the builder toolbar
(alongside existing Intelligence drawer trigger if present).

Panel sections:

1. NEXT STEP SUGGESTIONS (top)
   Header: "Meson suggests"
   2–3 node suggestion cards based on last added node.
   Each card: node icon + name, one-line reason, [+ Add] button,
   confidence color (green/yellow), [✕] dismiss.

2. ACTIVE ALERTS (middle)
   Header: "Alerts" with badge count
   Anomalies from workflow run history.
   Each: severity icon, plain English, [Fix] if auto-fixable.
   Empty: "No issues detected" + green check.

3. OPTIMIZATION TIPS (bottom)
   Header: "Optimize"
   1–2 tips with expected improvement, [Apply] button.

Data (when live):
- POST /api/meson/suggestions { workflow_state, last_added_node }
- GET /api/meson/alerts
- GET /api/meson/optimizations/{workflowId}

Until APIs exist: realistic mock data keyed off last node type
(hubspot_trigger → suggest lead_scoring, crm_update).

Behavior:
- Panel auto-opens when user adds a node
- Skeleton loaders while fetching
- Dismissed suggestions stored in localStorage per workflowId
- Match existing button/card/badge styles exactly
```

---

## F2 — Intelligent Agent Cards

```
Enhance existing agent pages in Gravitre (apps/web/app/agents/*).

READ existing agent list and detail components completely before editing.

Add intelligence signals to agent cards (keep existing layout):

Below agent name — compact metrics row:
- Success rate (color by value)
- Tasks today
- Avg response time

Knowledge pill: "[BookOpen] N docs trained" → links to /sources or agent knowledge

Last activity line: "Last ran: 2h ago — [task summary]" (muted, 1 line truncate)
If status Running: pulsing blue dot + "Running task..."

Model badge (top-right of card): "GPT-5.5" / "Claude" subtle pill

Agent detail header — performance row:
[Success Rate] [Tasks] [Avg response] [Model] [Knowledge docs]

Use SWR against existing agent APIs. Mock metrics only if API fields missing.
Do not add new npm dependencies.
```

---

## F3 — Workflow Execution Visualization

```
Enhance the workflow run monitor (apps/web/app/runs/[id] or equivalent).

READ the existing run detail page completely.

Vertical execution timeline (CI/CD style):

Each step:
- Status dot (waiting gray, running blue pulse, success green, failed red,
  skipped strikethrough, awaiting approval amber)
- Step name + node type
- Duration when complete
- Expand on click: input JSON, output JSON, model/tokens if AI step, error + [Retry]

Conditional branches: split visualization with True/False labels; dim untaken path.

Parallel batch: side-by-side nodes + "running in parallel" label.

Human approval gate: yellow pulse, approval context, [Approve] [Reject] prominent.

Poll GET /api/runs/{id} every 2s while status=running.

Match existing badge colors and card styles.
```

---

## F4 — Assistant Intelligence Upgrade

```
Enhance apps/web/app/assistant/page.tsx (and operator page if shared components).

READ the file completely. Do not rebuild from scratch.

1. CONVERSATION SIDEBAR (240px, collapsible)
   Groups: Today / Yesterday / Last 7 days / Older
   Item: title + relative time + model badge
   [+ New] at top
   GET /api/conversations (already exists in backend)

2. MODE SELECTOR (left of input)
   ⚡ Fast | 🧠 Standard | 🔬 Deep | 🤖 Agent
   Pass mode in POST body as task_complexity or mode
   Persist in localStorage; change placeholder per mode

3. ORG CONTEXT PILL (above chat, dismissible)
   "I know about your N agents, M workflows, and K connected tools."
   [?] expands to show agents/workflows/connectors list
   Subtle muted banner — unique Gravitre value vs Claude

4. FOLLOW-UP SUGGESTIONS
   After assistant message: 3 clickable chips from response.suggestions
   Click fills input (does not auto-send)

5. TOOL ACTIVITY
   Running: spinner + tool name
   Done: checkmark + tool name
   Knowledge: expandable sources
   Agent tasks: "→ View run" link

Match dark/light theme. Use installed packages only (recharts already available).
Wire to existing /api/assistant/chat streaming protocol (AI SDK UI stream).
```

---

## Backend dependency matrix

| Prompt | Needs backend | Status today |
|--------|---------------|--------------|
| F1 | `/api/meson/*` | ❌ Not built (B3) |
| F2 | Agent stats fields on `/api/agents` | ⚠️ Partial (`stats` JSON) |
| F3 | `/api/runs/{id}` step detail | ✅ Exists |
| F4 | `/api/conversations`, chat `conversation_id` | ⚠️ CRUD exists; chat not wired (B4) |

Use mocks with clear `// TODO: replace with API` comments until B3/B4 ship.
