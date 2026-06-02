# v0 Prompt — Workflow Builder UI/UX polish (STA-19 follow-up)

**Prerequisite:** STA-19 backend + thin frontend wiring merged. Persistence and execute already work for real workflow UUIDs. **Do routing first:** `v0-prompt-workflow-builder-real-ids.md` (create workflow → UUID builder URL).

**Branch:** `v0/workflow-builder-ux`  
**Scope:** Frontend only — `apps/web/app/workflows/[id]/builder/page.tsx` and small presentational components you may extract under `apps/web/components/gravitre/workflows/`. **No backend changes.**

**Reference screenshot:** Customer Data Pipeline canvas (node cards, blue edges, suggestions, bottom bar). Match or improve that visual quality while keeping behavior.

---

## Copy-paste prompt for v0

```
Refine and augment the Workflow Builder UI at apps/web/app/workflows/[id]/builder/page.tsx.

GOAL: Polish the existing node-based canvas (like the "Customer Data Pipeline" mock) — layout, states, feedback, accessibility — WITHOUT breaking Save/Load/Run integration with the FastAPI backend.

═══════════════════════════════════════════════════════════════
DO NOT MODIFY (backend contract — hands off)
═══════════════════════════════════════════════════════════════
- backend/**, supabase/**
- apps/web/lib/workflows/builder-persistence.ts  (API mapping — use as-is)
- apps/web/lib/api.ts workflow execute/save endpoints
- apps/web/app/api/**

═══════════════════════════════════════════════════════════════
MUST PRESERVE (behavior)
═══════════════════════════════════════════════════════════════
1. Route: /workflows/[id]/builder — dynamic `id` from use(params).

2. Persistence helpers (import from @/lib/workflows/builder-persistence):
   - loadBuilderGraph(workflowId)
   - saveBuilderGraph(workflowId, nodes, { name?, description? })
   - executeWorkflow(workflowId, parameters?)
   - apiGraphToCanvasNodes(apiNodes, apiEdges)
   - canvasToSavePayload is internal to save — nodes use `connections: string[]` (target node ids)

3. UUID vs demo routing:
   - isPersistableWorkflowId(id) → /^[0-9a-f]{8}-...$/i
   - Real UUID: load on mount, Save → saveBuilderGraph, Run → save then executeWorkflow
   - Non-UUID (e.g. "new", "1"): keep local demo/simulation path; toast that Save/Run need a real workflow

4. Canvas node shape (WorkflowNode / CanvasWorkflowNode):
   - id, type, name, description?, config, position {x,y}, connections[]
   - Optional: state, vendor, decisionConfig, councilConfig, outputPaths

5. Header actions must remain wired:
   - Save → handleSave (async, isSaving, disabled when isLoadingGraph)
   - Run → handleRun for UUID ids (NOT the old pure setTimeout simulation unless non-UUID)

═══════════════════════════════════════════════════════════════
DESIGN SYSTEM (match Gravitre app shell)
═══════════════════════════════════════════════════════════════
- Use existing: AppShell, StatusBadge, EnvironmentBadge, Button, Sheet, toast (sonner)
- Dark-friendly cards on dotted grid canvas; colored left border per node type
- Node types: agent | task | connector | tool | source | approval | decision | council
- Connection lines: curved blue paths between nodes (keep drag-to-connect if present)
- Icons: lucide-react (Bot, Plug, Shield, GitBranch, etc.) — already in file

═══════════════════════════════════════════════════════════════
UI/UX IMPROVEMENTS (in scope)
═══════════════════════════════════════════════════════════════

A) Loading & empty states
- Full-page or canvas skeleton while isLoadingGraph
- Empty canvas CTA when nodes.length === 0 && canPersist: "Add your first step from the library"
- Show workflow name from API (workflowMeta) not hardcoded "Customer Data Pipeline"

B) Save / Run feedback
- Save success toast already exists — add subtle "Last saved" timestamp in header (local state)
- Run in progress: keep execution bar; show step progress from API response when available
- Run completed: link to /runs/{run_id} (already partially implemented — make prominent)
- Run failed: inline error banner + retry button (calls handleRun again)

C) Execution visualization
- Map API step statuses to node.state: completed → success, failed → error, running → running
- Decision nodes: keep "evaluating" pulse during run; show confidence badge when reasoning exists
- Disable canvas edits while isRunning || isSaving

D) Header / wayfinding
- Breadcrumb: Gravitre Labs → Workflows → {workflowMeta.name}
- Settings sheet: bind workflow name/description fields to workflowMeta + pass to saveBuilderGraph on Save
- Version label: show "v{N}" from save response step_count or static until versions API exposed in UI

E) Suggestions panel (bottom-right cards)
- Keep AI Suggestions + Getting started cards visually
- Wire dismiss state (already have dismissedSuggestions) — do not block Save/Run
- Optional: "Add agent handoff" suggestion when graph has agent node without next_agent_id in metadata

F) Node config sheet (right Sheet)
- Ensure agent nodes can edit metadata fields used by backend compiler:
  - agent_id (uuid string), next_agent_id (uuid), task, receiver_task
- Use plain Inputs; store in node.config and/or node.metadata consistently with save payload:
  metadata: { agent_id, next_agent_id, task, receiver_task, decisionConfig?, councilConfig? }

G) Mobile / responsive
- Library panel collapses on md-
- Header buttons: icon-only on sm, labels on md+
- Canvas pan/zoom or horizontal scroll without breaking connection hit targets (min 44px)

H) Accessibility
- Keyboard: Esc closes sheet; selected node announced
- Connection handles: aria-label "Connect from {node name}"
- Run/Save: aria-busy when loading

═══════════════════════════════════════════════════════════════
OPTIONAL EXTRACT (recommended if page > 3500 lines)
═══════════════════════════════════════════════════════════════
Extract presentational only (no API calls inside):
- WorkflowCanvas.tsx — grid, nodes, edges, drag connect
- WorkflowNodeCard.tsx — single node visual + states
- WorkflowBuilderHeader.tsx — title, badges, Save/Run/Settings
- workflow-builder-types.ts — shared WorkflowNode type

Keep all load/save/execute logic in page.tsx or a thin useWorkflowBuilder.ts hook that calls builder-persistence.ts.

═══════════════════════════════════════════════════════════════
API REFERENCE (for UI labels only — do not reimplement)
═══════════════════════════════════════════════════════════════
GET  /api/workflows/{id}/builder  → { workflow_id, name, description, status, nodes[], edges[] }
PUT  /api/workflows/{id}/builder  → body: { nodes[], edges[], name?, description? }
POST /api/workflows/execute       → body: { workflow_id, parameters? } → { run_id, status, steps[] }

Node API fields (camelCase in responses): id, type/node_type, name/title, description, config, metadata, position, position_x/y

═══════════════════════════════════════════════════════════════
VERIFY (manual)
═══════════════════════════════════════════════════════════════
1. Open /workflows/{real-uuid}/builder — graph loads (or hydrates from definition)
2. Edit node positions → Save → refresh → positions persist
3. Run → completes or shows failed steps; run link works
4. /workflows/new/builder — demo graph still visible; Save shows helpful toast
5. No changes under backend/ or builder-persistence.ts API signatures

Do not remove features: council debate dialog, decision paths, connector action picker, model selector on agent nodes, library panel auto-close.
```

---

## What STA-19 already changed on this page

| Area | Status |
|------|--------|
| Same route & layout as screenshot | Yes — `apps/web/app/workflows/[id]/builder/page.tsx` |
| Visual redesign | **No** — still the existing mock canvas for non-UUID ids |
| Save button | **Yes** — calls `PUT /api/workflows/{id}/builder` for UUID workflows |
| Run button | **Yes** — save + `POST /api/workflows/execute` for UUID workflows |
| Load on open | **Yes** — `GET /api/workflows/{id}/builder` |
| Screenshot demo graph (Salesforce → PostgreSQL) | Shown when `id` is not a UUID (e.g. `/workflows/1/builder`) |

To see persistence on the screenshot-style UI, open a workflow created from **Workflows** (real UUID in the URL). Use **`v0-prompt-workflow-builder-real-ids.md`** to remove `/workflows/new/builder` and sample `/workflows/1/builder` links.

---

## Files v0 may touch

- `apps/web/app/workflows/[id]/builder/page.tsx` (primary)
- `apps/web/components/gravitre/workflows/*` (new, optional)
- `apps/web/hooks/use-workflow-builder.ts` (new, optional)

## Files v0 must not touch

- `apps/web/lib/workflows/builder-persistence.ts`
- `backend/app/workflows/builder_sync.py`
- `backend/app/routers/workflows.py`

See also: `docs/integration/WORKFLOW_BUILDER.md`
