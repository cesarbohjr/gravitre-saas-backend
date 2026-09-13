# G4 — Conversation ↔ Visualization (Delivery Report)

**Date:** 2026-09-13  
**G4 COMPLETE:** **PARTIAL** — SSE visualization wired to map; prod live verify **NOT RUN**

---

## Objective

Ask Gravitre on the Intelligence hub should **actively focus the map** using the canonical `AssistantVisualization` contract from G1 — not only client-side keyword heuristics.

---

## Shipped

### Frontend
- `apps/web/lib/intelligence/assistant-visualization.ts` — parse SSE payload, validate node ids against canonical graph, map to lens/highlight/dim/focus/selection
- `AskGravitreComposer` — consumes `visualization` on `data-intelligence` events; calls `onVisualization`
- Intelligence Overview hub — dual path:
  1. **Optimistic** heuristic focus on submit (`resolveAskMapFocus`)
  2. **Authoritative** canonical focus when SSE arrives (overrides heuristic)
- `IntelligenceMap` — `dimNodeIds`, `focusNodeIds` (spatial camera), dim/grayscale styling for inactive agents

### Backend (already on main from G1)
- `compile_intelligence_context_for_query()` emits `AssistantVisualization`
- `assistant.py` streams `visualization` on `data-intelligence` (deterministic fast-path + full stream)

### Tests
- `apps/web/__tests__/intelligence/assistant-visualization.test.ts` (vitest)

---

## Architecture

```
User question (surface=intelligence_hub)
        │
        ▼
compile_intelligence_context_for_query()
        │
        ├── markdown context → LLM / deterministic answer
        └── AssistantVisualization
                │
                ▼
        SSE data-intelligence.visualization
                │
                ▼
parseAssistantVisualization()
                │
                ▼
applyAssistantVisualizationToMapState()
  (validate ids vs pageContext.graph)
                │
                ▼
IntelligenceMap lens + highlight + dim + focus + inspector selection
```

---

## Acceptance (local)

| Check | Status |
|-------|--------|
| Agent question → acts lens + agent node ids from SSE | **CODE** (pytest G1 + vitest G4) |
| Prediction question → predicts lens + prediction ids | **CODE** |
| Node ids filtered to current canonical graph | **CODE** |
| Dim inactive agents on active-agent queries | **CODE** |
| Prod chat → map focus alignment | **NOT RUN** |

---

## Deferred

- `expandNodeIds` / `edgeTypes` rendering (schema exists; no map behavior yet)
- Inspector auto-open for learning/outcome satellite nodes
- Remove heuristic fallback once prod proves SSE always arrives (G6)

---

## Files changed

- `apps/web/lib/intelligence/assistant-visualization.ts` (new)
- `apps/web/components/intelligence/ask-gravitre-composer.tsx`
- `apps/web/app/intelligence/page.tsx`
- `apps/web/components/intelligence/map/intelligence-map.tsx`
- `apps/web/__tests__/intelligence/assistant-visualization.test.ts` (new)
