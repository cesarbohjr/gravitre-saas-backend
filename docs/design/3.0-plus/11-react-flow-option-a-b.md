# React Flow vs custom Workflow Builder — Option A / B

**Status:** Structural decision for Cesar — **do not replace builder yet**  
**Spec recovered fragment (≈ §17):** React Flow / xyflow is the **preferred foundation** for the operational Workflow Builder, subject to audit. RF is the visual interaction layer; canonical workflow definition remains SoT.  
**Repo facts:** `@xyflow/react` installed; used for Intelligence Relationships only. Builder is custom at `app/workflows/[id]/builder/page.tsx`. Schema bridge: `CanvasWorkflowNode` + `canvasToSavePayload` / load helpers in `lib/workflows/builder-persistence.ts` → `workflowsApi.getBuilder` / `saveBuilder`.

## Spec requirements (from recovered Word fragment)

Where backed by existing capabilities, upgraded builder should support: custom nodes, drag/drop, connector/agent/condition/action/approval/knowledge/IO nodes, error paths, branching, nested/subflows, grouping, validation, node/edge inspection, **live execution overlays**, history, AI-assisted editing. Modes: **Design / Live / Explain / History**. One canonical representation for AI + manual edits. Compact previews in AI workspace open into full builder. Visual language: Nodus/Gravitre — not stock RF demos. ELK evaluate for layout; tldraw must not replace builder.

---

## OPTION A — Retain and extend the custom builder

| Dimension | Assessment |
|-----------|------------|
| **Preserved** | Existing custom canvas, Meson panel hooks, `CanvasWorkflowNode` types (agent/task/connector/approval/decision/council/if/switch/merge/loop), connector bind, dry-run / intelligence drawer integration, save/load via builder API |
| **Missing vs §17** | Formal Live/Explain/History mode shells; first-class live execution overlays; RF ecosystem (minimap, controls, a11y plugins); likely weaker graph layout for AI-generated graphs |
| **Migration complexity** | N/A (no migration) — feature work is **Large** to reach Design/Live/Explain/History parity |
| **Bundle / perf** | Avoids second canvas engine on builder route; RF already paid on Relationships route |
| **Accessibility** | Custom canvas must be audited; no RF keyboard defaults |
| **Maintainability** | Owns all interaction code; higher long-term cost vs RF community patterns |
| **Risk to functional agent** | **Lowest** if schema/persistence untouched |
| **Nodus fit** | Full control of node chrome — good if disciplined |

**When A wins:** Cesar prioritizes zero migration risk and incremental hardening of current canvas while functional A–J continues.

---

## OPTION B — Adopt React Flow as visual layer only

| Dimension | Assessment |
|-----------|------------|
| **Preserved** | Canonical schema/persistence/execution/approvals/governance via adapter: RF nodes/edges ↔ `CanvasWorkflowNode` / save payload — **no second workflow definition** |
| **Missing initially** | Custom node chrome rewrite; Meson sync must target same SoT; Live/Explain/History still need product work (RF enables overlays, does not invent runtime events) |
| **Migration complexity** | **Large** (builder page is a major surface) but bounded if phased: read-only RF → editable → flag cutover |
| **Bundle / perf** | RF already in app; builder route would load it (acceptable if code-split) |
| **Accessibility** | Better starting point (RF focus/keyboard) + custom node a11y still required |
| **Maintainability** | Aligns with preferred §17 foundation; shared skills with Relationships graph |
| **Risk to functional agent** | **Medium** if save payload drifts — mitigated by golden tests on `canvasToSavePayload` / load round-trip and no backend schema change |
| **Nodus fit** | Must theme heavily — stock RF look is explicitly forbidden |

**When B wins:** Cesar accepts a migration to hit Live overlays, layout, and long-term maintainability without rewriting runtime.

---

## Recommendation (for Cesar decision — not a unilateral cutover)

**Prefer B as the target visual foundation**, with **A as interim** until RF-1 (read-only harness) and RF-2 (editable same payload) pass contract tests. Do **not** auto-replace production builder. Do **not** permanently reject RF because the builder is currently custom.

### Cesar approval ask (G-STRUCT / G-DEP)

Choose one:

1. **Target B** — authorize RF-1 harness prototype on this frontend branch  
2. **Stay A** — authorize custom-canvas Design/Live/Explain/History prototypes without RF  
3. **Defer** — keep documenting; no builder visual work until functional 3.0-D+ quieter

---

## Non-negotiables (either option)

- One canonical workflow definition  
- AI (Meson) and manual edits converge on the same SoT  
- No rewrite of workflow execution / approvals / HMAC / Observations  
- No fake live execution — overlays only when runtime emits real state
