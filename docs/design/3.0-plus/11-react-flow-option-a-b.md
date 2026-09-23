# React Flow vs custom Workflow Builder — Option A / B

**Status:** Structural decision for Cesar — **do not replace builder yet**  
**Spec recovered fragment (≈ §17):** React Flow / xyflow is the **preferred foundation** for the operational Workflow Builder, subject to audit. RF is the visual interaction layer; canonical workflow definition remains SoT.  
**Repo facts:** `@xyflow/react` installed; used for Intelligence Relationships only. Builder is custom (~6.7k-line page) at `app/workflows/[id]/builder/page.tsx`. Schema bridge: `CanvasWorkflowNode` + `canvasToSavePayload` / load helpers in `lib/workflows/builder-persistence.ts` → `workflowsApi.getBuilder` / `saveBuilder`.

**Capability audit:** [Workflow builder capability audit](69355e98-0b6e-4113-8ec8-85f9064e214c) (2026-09-23).

## Save / load contract (freeze unless Platform Execution owns a schema change)

| Layer | Function |
|-------|----------|
| Page | `loadBuilderGraph` / `saveBuilderGraph` |
| Persistence | `apiGraphToCanvasNodes`, `canvasToSavePayload`, `normalizeCanvasNodeType` |
| HTTP | `GET/PUT /api/workflows/{id}/builder` via `workflowsApi.getBuilder` / `saveBuilder` |
| Related | `execute` / `dryRun`; run poll via `runsApi.getWithSteps`; Meson edit/apply → reload graph |

Edges persist as `{ fromNodeId, toNodeId }` from `node.connections[]`.

## Spec requirements (from recovered Word fragment)

Where backed by existing capabilities, upgraded builder should support: custom nodes, drag/drop, connector/agent/condition/action/approval/knowledge/IO nodes, error paths, branching, nested/subflows, grouping, validation, node/edge inspection, **live execution overlays**, history, AI-assisted editing. Modes: **Design / Live / Explain / History**. One canonical representation for AI + manual edits. Compact previews in AI workspace open into full builder. Visual language: Nodus/Gravitre — not stock RF demos. ELK evaluate for layout; tldraw must not replace builder.

## What the custom builder already does

- Node types: agent, task, connector, tool, source, approval, decision, council, if/switch/merge/loop  
- Edges: handle drag + SVG; decision path dimming; connect/disconnect confirms  
- Inspect: ConfigPanel + `NodeRunDebugPanel` when `lastRunId`  
- Run: save → execute → poll step states onto nodes; pause/cancel; links to approvals/runs  
- Meson: suggest/alert/insight/edit/apply/explain/reliability; reload after apply  
- Intelligence drawer: timing, risk, dry-run  
- Gaps: no pan/zoom/minimap; version-history UI unused; thin keyboard a11y; monolith maintainability

---

## OPTION A — Retain and extend the custom builder

| Dimension | Assessment |
|-----------|------------|
| **Preserved** | Full current surface; lowest chance of breaking `CanvasWorkflowNode` ↔ PUT path |
| **Missing vs §17** | Viewport ops, undo/redo, version history UI, formal Live/Explain/History shells, stronger a11y |
| **Migration complexity** | **S** incremental; **L** to reach RF-parity viewport/a11y without RF |
| **Bundle / perf** | No new dep on builder route; custom SVG re-renders all edges on drag — weak at scale |
| **Accessibility** | Partial labels; mouse-first |
| **Maintainability** | Poor (~6.7k monolith) |
| **Risk to functional agent** | **Low** if schema untouched |
| **Nodus fit** | Token/CSS-first polish without structural change |

**When A wins:** Cesar prioritizes zero migration risk while functional A–J continues.

---

## OPTION B — Adopt React Flow as visual layer only

| Dimension | Assessment |
|-----------|------------|
| **Preserved** | Same PUT body / execute / Meson reload / drawer if adapter is strict; custom node chrome as RF `nodeTypes` |
| **Missing initially** | History/explain product work still required; RF enables overlays, does not invent runtime events |
| **Migration complexity** | **M** (extract canvas → RF shell; connections↔edges; decision multi-out regression). **L** only if persistence rewritten |
| **Bundle / perf** | RF already in app (Relationships); code-split builder chunk; watch dual state |
| **Accessibility** | Better baseline; still need labeled custom nodes |
| **Maintainability** | Better if canvas extracted; reuse Relationships patterns |
| **Risk to functional agent** | **Low–Med** if visual-only; **High** if edge IDs/handles change compile semantics — guard with PUT golden tests + live execute |
| **Nodus fit** | Strong long-term if themed; forbid stock RF look |

**When B wins:** Cesar accepts phased migration for ops ergonomics without rewriting runtime.

---

## Recommendation (for Cesar decision — not a unilateral cutover)

**Prefer B as the target visual foundation**, with **A as interim**. Do **not** auto-replace production builder. Do **not** permanently reject RF because the builder is currently custom.

### Cesar approval ask (G-STRUCT / G-DEP)

1. **Target B** — authorize RF-1 harness (read-only `CanvasWorkflowNode` → xyflow) on this frontend branch  
2. **Stay A** — authorize custom-canvas Design/Live/Explain/History prototypes without RF  
3. **Defer** — docs only until functional track quieter  

---

## Non-negotiables (either option)

- One canonical workflow definition  
- AI (Meson) and manual edits converge on the same SoT  
- Do not change `CanvasWorkflowNode` / `canvasToSavePayload` / `saveBuilder` unless Platform Execution owns a schema revision  
- No fake live execution — overlays only when runtime emits real state
