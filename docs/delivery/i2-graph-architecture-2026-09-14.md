# I2 — Graph Architecture + Interactions

**Date:** 2026-09-14  
**Status:** SHIPPED (code) — prod verification pending deploy  
**Spec:** `docs/delivery/gravitre-intelligence-experience-rebuild-spec-2026-09-13.md` §4–5, §19

## Architecture (renderer-agnostic)

```
IntelligenceGraph (apps/web/lib/intelligence/graph/intelligence-graph.ts)
        ↓
GraphLayoutEngine (graph-layout-engine.ts — pins, cache, clustering)
        ↓
GraphInteractionController + useGraphInteraction hook
        ↓
GraphRenderer adapter
        ├── DomSvgGraphRenderer (graph-renderer.ts)
        └── WebGlGraphRenderer placeholder (renderers/webgl-renderer.ts)
```

**Rule enforced:** No Sigma imports; WebGL is adapter-only. Topology semantics remain in `IntelligenceGraph` + `canonical-graph-topology.ts`.

## Interactions shipped

| Control | Implementation |
|---------|----------------|
| Wheel / trackpad zoom | `useGraphInteraction.handleWheel` |
| Zoom in / out / fit / reset | Toolbar + controller |
| Click-drag pan | Pointer events on canvas |
| Drag node | Pointer down on node + move |
| Pin / unpin | Double-click node |
| Focus selected | Toolbar crosshair |
| Fullscreen | Fullscreen API on canvas |
| Search nodes | Toolbar search → highlight matches |
| Filter node types | Toolbar dropdown |
| Cluster expand/collapse | Bottom chips when >24 nodes |
| Edge click | SVG edge `onClick` → edge selection |
| Hover path | Connected nodes highlighted on hover |
| Keyboard | Arrow traverse, Enter select, Esc clear |

## UI

- `IntelligenceGraphStage` — composes stack + toolbar + canvas
- `IntelligenceGraphToolbar` — controls bar
- `IntelligenceMap` — thin re-export for backward compatibility

## Tests

- `graph-interaction-controller.test.ts` (4 tests)
- All intelligence vitest suite: **60/60 PASS**

## Next: I3

Living Intelligence Map product polish on top of this engine (not a parallel implementation).
