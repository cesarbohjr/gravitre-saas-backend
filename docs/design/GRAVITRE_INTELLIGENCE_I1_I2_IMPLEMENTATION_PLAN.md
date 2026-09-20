# Intelligence I1 + I2 — Implementation Plan (I-A → I-G)

**Authority:** Cesar Intelligence design-review gate + Master Execution Directive 2026-09-20  
**Surface:** Authenticated `/intelligence` (Workstream C) — **not** CES KF-A  
**Current gate:** Harness fidelity → Cesar YES/NO → then production promote  
**Status:** Plan locked for execution; harness in progress; prod swap NOT STARTED

---

## Data contract (do not invent a second fabric)

| Source | Role |
|--------|------|
| `IntelligencePageContextResponse.graph` | Map nodes/edges for field topology |
| `org_entity_relationships` / KG entities | Canonical knowledge — primary I1 nodes |
| Admin summary entity/relationship counts | Metrics must match usable graph endpoints |
| Audit / freshness events | I2 change stream kinds |

**Root cause (0 entities · 32 relationships):** `get_admin_summary` SELECT omitted entity ids while counting relationships that still existed → CoreStats lied relative to rendered MapNodes. Fixed in `knowledge_graph_service.py` (+ unit tests). Deploy required before live count PASS.

---

## Lens model (one canonical graph)

| Lens | Emphasis (LENS_SPEC) | Does not mean |
|------|----------------------|---------------|
| KNOWS | Confirmed entities + relationships | Hide other graph |
| LEARNS | Recently learned / provisional | Separate learning DB |
| PREDICTS | Predicted edges + confidence | Fabricated forecasts |
| ACTS | Actionable / agent-linked | Workflow redesign |
| IMPROVES | Contradictions / freshness debt | Separate “improve” product |

Selection reveals real context, provenance, evidence, and actions. Contextual Ask → canonical AI Workspace only.

---

## I-A — Field topology (I1 PRIMARY)

| Item | Detail |
|------|--------|
| Job | Show what the org **knows** as entity/relationship field |
| Spatial | Entity nodes + typed edges; no hub-only décor graph |
| States | loading · empty · sparse · rich · large · error · selected · reduced-motion · mobile |
| Evidence | Entity/rel provenance chips; confidence honest when unknown |
| Harness | `intelligence-field-prototype.tsx` + KG fixtures |
| Prod | After Cesar gate — replace `IntelligenceGraphStage` presentation only |

## I-B — Change stream (I2 SUPPORTING)

| Item | Detail |
|------|--------|
| Job | Contextual stream of knowledge change |
| Event kinds | new · changed · confirmed · learned · contradiction · archived · freshness |
| Behavior | Select event → highlight related entities; does not replace I1 |
| Ask | Opens AI Workspace with selection context — no second chat runtime |

## I-C — Inspector

| Item | Detail |
|------|--------|
| Shows | Selected entity **or** relationship **or** change event |
| Contents | Type, status, confidence, evidence, available actions |
| Empty honesty | Sparse metrics + usable-endpoint count when graph thin |

## I-D — Lenses

Wire five lenses to `LENS_SPEC` filters on the **same** fixture/prod graph. Verify each lens changes emphasis visibly (opacity / priority / stream filter) without swapping datasets.

## I-E — AI contextual Ask

Button → existing AI Workspace launcher with entity/rel/event payload. No new agent runtime.

## I-F — Responsive + a11y

Mobile scene; reduced-motion; keyboard focus on nodes/stream; Nucleo icons only for functional chrome.

## I-G — Production promote (gated)

1. Cesar visual YES on harness scenes  
2. Deploy KG SELECT fix; verify live entity count ≠ false zero when relationships exist  
3. Swap `/intelligence` to I1+I2 presentation on real contract  
4. Evidence-linked PASS (audit/HTTP + browser) — not harness alone  

---

## Review scenes (harness query `surface=intelligence&scene=…`)

| Scene | Purpose |
|-------|---------|
| compare | CURRENT prod stub vs PROPOSED I1+I2 |
| default | Rich field + stream |
| selected | Entity selected + inspector |
| relationship | Edge selected |
| change | I2 event selected |
| lens-predicts | PREDICTS emphasis |
| inspector | Inspector focus |
| ai-context | Ask affordance |
| loading / empty / sparse / large / error | Honesty states |
| mobile / reduced | Responsive + motion |

---

## YES / NO checklist (Cesar gate — do not self-approve)

| Question | Answer required |
|----------|-----------------|
| I1 reads as KG entity field (not department décor)? | YES / NO |
| I2 event kinds are meaningful and selectable? | YES / NO |
| Five lenses change emphasis on one graph? | YES / NO |
| Selection shows provenance/evidence/actions? | YES / NO |
| Ask stays on AI Workspace (no second chat)? | YES / NO |
| Empty/sparse/error honest (no fake telemetry)? | YES / NO |
| Approve production swap of `/intelligence`? | YES / NO |

**Until YES on production swap:** keep `IntelligenceGraphStage` in prod.

---

## Explicit non-goals

- Do not import CES KF-A storyboard or illustrative marketing data  
- Do not rebuild TRACE / Activity as Intelligence  
- Do not add Three.js/R3F  
- Do not fabricate entities to fill a sparse org  
