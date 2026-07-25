# Workflows canvas benchmark (n8n/HubSpot Part A) — 2026-07-25

Scope: Behave Like Claude/Manus canvas parity check. **Not executed in prior UI/UX or unified-turn passes — missed, not deliberately deferred.**

---

## 1. No silent node failure

### FIXED (this pass)
- Failed steps already showed red border + ERROR badge on canvas nodes.
- **HUD/toast now names the failing node** via `formatFailedStepMessage()` — e.g. `HubSpot Create Contact: catalog_write_authority blocked`.
- **Auto-selects failed node** on run failure (`resolveFailedStepNodeId` + `setSelectedNodeId`).
- **Step error text on node card** (`stepError` from `applyRunStepsToNodes`).

Evidence: `apps/web/lib/workflows/run-monitor.ts`, `apps/web/app/workflows/[id]/builder/page.tsx`

---

## 2. Modular vs monolithic (sub-workflows / collapsible groups)

### NAMED GAP — new feature
Flat canvas only (`CanvasNodeType` union in `builder-persistence.ts`). No nested sub-graph, group container, or collapse primitive. Requires new node type + persistence model.

---

## 3. Version history / definition rollback

### NAMED GAP — UI wiring (API exists)
Backend: `POST /workflows/{id}/versions`, `GET …/versions`, `POST …/versions/{version_id}/activate`.  
Frontend client: `workflowsApi.listVersions`, `activateVersion` in `apps/web/lib/api.ts`.  
Builder shows static `v1` label only — no version picker or restore panel.

---

## 4. Pause-for-approval / catalog_write_authority parity

### CONFIRMED ALREADY CORRECT (backend)
- Shared SoT: `canvas_write_gate.py` → `catalog_write_authority.invoke_action_requires_write_approval`
- Policy floor: `engine.py` `_definition_has_write_steps` forces `required_approvals ≥ 1`
- Step gate: `handlers.py` `_enforce_canvas_write_authority` / `block_canvas_write_step`
- Canvas differs from chat by design: **run-level** Decision Queue vs **turn-level** confirm (documented in STA-322)

### FIXED (this pass)
- Canvas execute now tags `parameters: { source: "canvas" }` by default (`executeWorkflow` in `builder-persistence.ts`).

---

## 5. Inline per-node debugging / BusinessOutcome

### FIXED (partial — this pass)
- **Before:** `ConfigPanel` was configuration-only; no shared `BusinessOutcomeView`.
- **After:** `NodeRunDebugPanel` in config sheet when `lastRunId` set — loads run steps + step output JSON + run-level `BusinessOutcomeView` via `businessOutcomesApi.get(runId)`.

### NAMED GAP
- BusinessOutcome projection is **run-level** today (`business_outcomes.py` projects from run id), not per-step DTO slice. True per-node vendor evidence requires backend step→outcome linkage.

---

## Verification

| Item | Status |
|------|--------|
| Code wiring | **PARTIAL** — items 1, 4, 5 wired; 2, 3 named gaps |
| Live prod canvas run | **NOT RUN** — requires authenticated workflow + write-capable connector in prod |
