# I13 — Graph density / LOD

**Date:** 2026-09-16  
**Status:** SHIPPED (code). Live 60fps proof **NOT RUN** (needs dense graph on deployed SHA).

No invented customer prices, badges, or Enable toggles.

## What changed

- **Collision:** `resolveNodeCollisions` after layout so node centers keep a minimum gap.
- **LOD labels:** `shouldShowNodeLabel` hides satellite copy below scale 0.72 (and below 1.0 when dense); selected/highlighted stay labeled; `sr-only` keeps the name for AT.
- **Cluster expand:** at ≥24 nodes, kind clusters **start collapsed**; Expand chip toggles `expandedClusterIds` (`aria-expanded`).
- **Transform-only pan:** render payload no longer depends on viewport; dense graphs apply CSS `transform` with `transition: none` instead of Framer spring. Hover still does not rebuild the payload.

## Tests

Local: `npx vitest run __tests__/intelligence/graph-lod.test.ts __tests__/intelligence/graph-interaction-controller.test.ts`

## Files

- `apps/web/lib/intelligence/graph/graph-lod.ts`
- `graph-layout-engine.ts`, `intelligence-graph.ts`, `graph-interaction-controller.ts`
- `intelligence-graph-stage.tsx`, `map-satellite-node.tsx`
