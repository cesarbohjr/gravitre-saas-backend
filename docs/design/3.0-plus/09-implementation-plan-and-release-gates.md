# 09 — Implementation plan and release gates

**Authority:** Master §§42–48. Frontend track only.

## Master phase mapping

| Master phase | Frontend status |
|--------------|-----------------|
| 0 Repository audit | ✅ `01-current-state-architecture-audit.md` |
| 1 Product inventory | ✅ `02-route-interaction-inventory.md` (expand nested routes ongoing) |
| 2 Technology matrix | ✅ `03-technology-adoption-matrix.md` (reconciled to §7) |
| 3 AI-native architecture | ✅ `08-ai-native-interaction-architecture.md` |
| 4 Reference research | ✅ `05-reference-selection-matrix.md` (deepen per family as prototypes need) |
| 5 Design-system consolidation | ✅ Master + `GRAVITRE_*.md` companions |
| 6 Structural prototypes | ✅ Partial — see `13-phase6-prototype-queue.md` |
| 7 Validation | Structural selection **done** (G-STRUCT 2026-09-24). Harness PARTIAL. Full product UX acceptance **pending**. |
| 8 Production implementation | **Slice 0 AUTHORIZED** (2026-09-24). Areas 4–15 + RF cutover still separately gated. |

## Release gates

| Gate | Required | Blocks |
|------|----------|--------|
| **G-STRUCT** | Cesar records page-intro vocabulary/map, WM policy, Intelligence structure, AI/Model Studio direction, RF Option B as direction-only (not cutover) | Broad Phase 8 — **PASSED 2026-09-24** (see `20`) |
| **G-DEP** | Cesar approves new platform deps | Installs |
| **G-FUNC** | No overwrite of Platform Execution contracts | Shared file PRs |
| **G-PROOF** | Authenticated journey PASS with evidence pointer | “Shipped UX” claims |
| **G-HONEST** | No invented prices/badges/confidence/artifacts | Any customer surface |
| **§43 coverage** | Routes dispositioned in `15-coverage-matrix.md` | Declaring redesign complete |

## First production slice (after G-STRUCT)

**Slice 0 (AUTHORIZED 2026-09-24):** tokens/typography → shared primitives → Window Manager presentation shell (contextual default + preference; presentation-only). See `20-g-struct-decision-package.md` §9 · `21-slice-0-foundation.md`.

## Safe defect track (not Phase 8)

Assignments confidence display · workflows developer copy · org membership recovery (main)

## Parallel with functional agent

Frontend prototypes consume stable contracts. Functional agent owns CognitiveTurnKernel, ExecutionPlan, ActionSpec, PendingAction, Observations, Composer, voice runtime, SSE, durable deliverables, workflow execution.
