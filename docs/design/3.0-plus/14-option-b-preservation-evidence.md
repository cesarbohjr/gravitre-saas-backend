# Option B — React Flow prototype: functionality preservation evidence

**Status:** Isolated harness only (`?s=workflow-rf`)  
**Authorization:** Cesar Option B design direction for prototyping (2026-09-23)  
**Not authorized:** Replace production `app/workflows/[id]/builder/page.tsx`

## Contract used (unchanged)

| Item | Path / symbol |
|------|----------------|
| Schema | `CanvasWorkflowNode`, `CanvasNodeType`, `NodeState` |
| Save shape | `canvasToSavePayload` → `{ nodes, edges: { fromNodeId, toNodeId }[] }` |
| HTTP (not called in harness) | `workflowsApi.getBuilder` / `saveBuilder` |

## Demonstrated in prototype

| Capability | Evidence |
|------------|----------|
| Canonical nodes on RF | Fixture covers source, agent, decision, connector, task, approval |
| Connections ↔ edges | `canvasToRf` / `rfToCanvas`; Design mode reconnect updates payload edges |
| Persistence shape | Inspector “Persistence evidence” panel serializes `canvasToSavePayload` output |
| Design mode | Drag, connect, pan/zoom, minimap, Controls |
| Live composition | NodeState-colored chrome from fixture (not execute API) |
| Explain composition | `decisionConfig.reasoning` when present |
| History composition | Version list UI shell only |

## Preserved if production migration stays visual-layer-only

getBuilder/saveBuilder · execute/dryRun · Meson reload · approvals · governance · CanvasWorkflowNode fields

## Gaps / would regress without more work

| Gap | Severity | Owner |
|-----|----------|-------|
| Decision multi-out handle dimming | Med | Frontend migration |
| Council debate UI | Med | Frontend + existing config |
| Meson suggest/apply on RF canvas | Med | Frontend; keep Meson contracts |
| Version restore API | High if History is product | Functional |
| Live step map from runsApi | Med | Consume existing run poll; no fake SSE |
| Full keyboard a11y on custom nodes | Med | Frontend |
| Dual React Flow instances (Relationships + Builder) | Low–Med bundle | Code-split already pattern |

## Cutover ask (later)

Present this harness + golden PUT fixture tests to Cesar before any production builder swap. Runtime/execution engine remains functional-agent owned.
