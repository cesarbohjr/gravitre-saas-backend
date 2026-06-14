# Gravitre AI Intelligence — v0 Frontend Prompts (F1–F5)

Paste these into [v0.dev](https://v0.dev). **Do not implement in Cursor.** For live backend endpoints and branch sync, see [`docs/integration/V0_BACKEND_SYNC.md`](../integration/V0_BACKEND_SYNC.md).

Stack: Next.js App Router, React 19, TypeScript, Tailwind v4, shadcn/ui, SWR, Framer Motion, existing `apps/web/lib/fetcher.ts` and `apps/web/components/gravitre/premium-effects.tsx`.

**Live APIs (prod):** Meson `POST /api/meson/suggestions`, `GET /api/meson/alerts|insights|optimizations/{workflowId}`, agent jobs, assistant chat + conversations, workflow dry-run/execute, runs pause/cancel/resume/step-retry, federation, role packs, CS health/failure scan, semantic search `/api/search`.

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

Poll GET /api/runs/{id} every 2s while status=running or paused.

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
| F1 | `/api/meson/*` | ✅ Wired (`suggestions`, `alerts`, `optimizations/{workflowId}`; Apply/Fix in builder) |
| F2 | Agent stats + `knowledgeDocCount` on `/api/agents` | ✅ Wired (`stats` JSON + RAG/instruction counts; agents + operators merge) |
| F3 | `/api/runs/{id}` step detail + retry/resume | ✅ Wired (`ExecutionTimeline`, step retry, pause resume, poll while paused) |
| F4 | `/api/conversations`, chat `conversation_id`, org context | ✅ Wired (sidebar, streaming chat, org-context pill, submit lock) |
| F5 | Motion only — no new APIs | ✅ Shipped PR #38 (`39cfaba`) — see [`F5_MOTION_HANDOFF.md`](F5_MOTION_HANDOFF.md) |

Shipped in commits `c768f28` (F1–F4 UI), `a9c7ad7` (run ops gaps), `11ad1a7` (Meson Fix + training links), `a5b8cce` (optimizations API + paused polling), `933892a` (search, assistant, agents roster), **`39cfaba`** (F5 motion PR #38). Linear: **STA-149–154**, epic **STA-132** — all **Done**.

---

## F5 — Motion, Lottie & Premium UX Pass

**Status: ✅ Shipped** (PR #38 → `main` `39cfaba`). Full handoff: [`F5_MOTION_HANDOFF.md`](F5_MOTION_HANDOFF.md).

Use **`useMotionPrefs()`** from `apps/web/lib/animations.ts` for any new animated UI. Do not re-run the v0 prompt below on surfaces already listed in the handoff.

<details>
<summary>Original v0 prompt (archived — do not re-apply to shipped surfaces)</summary>

```
You are the frontend design lead for Gravitre Operator AI — an enterprise AI ops platform.
Your job: augment EXISTING production-wired UI with motion, micro-interactions, Lottie,
and modern SaaS UX polish. DO NOT redesign layouts or break API wiring.
… (see git history of this file for full prompt text)
```
</details>
