# UI 2.0 — Phase 10: STATUS chip adoption (approvals / BO honesty)

**Date:** 2026-09-04  
**Branch:** `main`  
**Depends on:** Phase 9 `--status-*` + `STATUS` tokens

---

## Scope

Wire Phase 9 semantic status chips into governance / honesty surfaces — no new product claims.

| Surface | Change |
|---------|--------|
| `lib/design-system.ts` | `STATUS_DOT`, `StatusTone`, `resolveStatusTone()` |
| `StatusBadge` / `AutoStatusBadge` | Prefer `tone` → `STATUS` / `STATUS_DOT`; Auto maps API strings via `resolveStatusTone` |
| `/approvals` | Queue + detail use `AutoStatusBadge`; priority chips use `STATUS.*` (no zinc) |
| `approval-batch-panel` | Item status via `AutoStatusBadge` |
| `GibeHonestyStrip` | Count + row chips use `statusTone` (estimate / verified / idle) |
| `ConfidenceBadge` | Estimate path uses `STATUS.estimate` |

---

## Honesty

- No TRAINED / live ops invention.  
- Estimate tones stay visually distinct from verified/approved.  
- **(a)** Authorized continuation of UI 2.0 Phase 9 “still later” list after commit `8d7c4b7e`.

---

## Verification

| Check | Label |
|-------|-------|
| Local typecheck / honesty tests | Run with Phase 10 edits |
| Live Class A `/approvals` | **NOT RUN** |
| Production | **NOT RUN** |
