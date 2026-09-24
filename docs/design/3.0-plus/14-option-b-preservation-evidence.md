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

| Gap | Severity | Owner | In this package |
|-----|----------|-------|-----------------|
| Decision multi-out handle dimming | Med | Frontend migration | **Not demonstrated** |
| Council debate UI | Med | Frontend + existing config | **Not demonstrated** |
| Meson suggest/apply on RF canvas | Med | Frontend; keep Meson contracts | **Not demonstrated** |
| Version restore API | High if History is product | Functional | History UI shell only |
| Live step map from runsApi | Med | Consume existing run poll; no fake SSE | Fixture NodeState only |
| Full keyboard a11y on custom nodes | Med | Frontend | PARTIAL |
| Dual React Flow instances (Relationships + Builder) | Low–Med bundle | Code-split already pattern | Acceptable for harness |

## Newly demonstrated (Phase 6 selection package)

| Capability | Where |
|------------|--------|
| Edge inspection | `?s=workflow-rf` edge inspector |
| AI-generated → compact preview → RF | `?s=workflow-gen` + `scene=ai-preview` |
| Demonstrated vs conceptual callout | RF prototype footer |

## Cutover ask (later)

Present this harness + golden PUT fixture tests to Cesar before any production builder swap. Runtime/execution engine remains functional-agent owned. **Do not request cutover from text-only report.**
