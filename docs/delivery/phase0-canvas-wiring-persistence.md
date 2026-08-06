# Phase 0 — Canvas node-wiring persistence

## Root cause (confirmed)

**Serialization / key-shape bug on save**, not a visual-only or pure race:

1. UI stores connections in `node.connections[]` and Save sends
   `edges: [{ fromNodeId, toNodeId }]` via `canvasToSavePayload`.
2. FastAPI `BuilderGraphEdgeInput` accepts camelCase aliases correctly.
3. `save_workflow_builder` called `model_dump(by_alias=True)`, emitting
   `fromNodeId` / `toNodeId`.
4. `sync_builder_graph` only read `from_node_id` / `from` / `to_node_id` / `to`.
5. Every edge was skipped. `delete_workflow_graph` had already wiped prior
   edges → save returned 200 with nodes, **zero edges**.
6. Reload could look partially wired via sequential/contract fallbacks.

Ruled out as primary cause: frontend edge render (SVG from `connections`),
autosave race (no autosave on connect), loader-only bug.

## Validator gap (separate)

`binding_validation.py` fell back to sequential upstream when edges were
empty, so missing canvas wires did **not** fail save. Added
`binding.canvas_graph_disconnected` when `definition.graph` exists with
nodes/edges key but zero edges and multiple steps.

## Fix

- `edge_endpoints()` accepts camelCase + snake + contract keys.
- Refuse save when requested edges all fail to persist.
- Router dumps edges/nodes with `by_alias=False`.
- Smoke + unit regression coverage.

## Evidence pointers

- Unit: `tests/workflows/test_builder_edge_persistence.py`
- Binding: `test_canvas_graph_disconnected_flagged_when_edges_empty`
- Live: `scripts/smoke-workflow-builder.py` (edge count on save + reload)
- Audit: `scripts/audit-workflow-canvas-edges.py` →
  `docs/delivery/phase0-canvas-edge-audit-live.json`
