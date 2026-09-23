# 09 — Implementation plan and release gates

## Dependency order (frontend track)

```
P0 Ownership matrix + conflict freeze          ✅ (this package)
P1 Architecture + route/state inventory        ✅
P2 Technology matrix                           ✅
P3 Design-system + window + RF + AI-native docs ✅
P4 Harness structural prototypes (isolated)
    - Page intro variants
    - Docked window concept
    - Intelligence Field primacy composition
    - RF-1 read-only workflow
P5 Cesar structural design gate  ← STOP (no broad Phase 8)
P6 Coordinated production slices (one at a time)
    - Honesty defects (confidence %, meta copy) can ship earlier as defects
P7 Journey proof per slice (authenticated browser)
```

## Release gates

| Gate | Required | Blocks |
|------|----------|--------|
| **G-STRUCT** | Cesar approves window + Field primacy + RF migration direction | Broad production redesign |
| **G-DEP** | Cesar approves any new npm platform dependency | Installs |
| **G-FUNC** | No overwrite of 3.0-D artifact/SSE contracts | Shared file PRs |
| **G-PROOF** | Authenticated journey PASS with evidence pointer | “Shipped UX” claims |
| **G-HONEST** | No invented prices/badges/confidence/artifacts | Any customer surface |

## Safe to fix now (defect track, not redesign)

- Assignments confidence display bug (`3500%`)  
- Workflows totals developer copy leak  
- Org membership 403 recovery (already on main)  

These do **not** count as Phase 8 redesign.

## Structural prototypes (approved venue)

`/dev/ai-workspace-preview` only until G-STRUCT.

## Parallel with functional agent

Frontend may **inspect** artifact presentation and prototype improvements against the documented contract. Functional agent owns schema/lifecycle. Merge incompatibilities only via coordinated integration, not drive-by main edits from this worktree.
