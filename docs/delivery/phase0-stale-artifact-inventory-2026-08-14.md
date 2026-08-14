# Phase 0 inventory — removal/archive candidates (NO ACTIONS TAKEN)

**Date:** 2026-08-14  
**Status:** AWAITING CESAR SIGN-OFF — nothing deleted or archived yet.  
**Guardrail:** No real customer/org billing/audit data. Scope = test/demo/smoke/scaffold only.

## Sign-off required before any execution

Reply with an explicit named choice, for example:
- `Approve A1–A4 only (SAFE_HARD_DELETE underscore scratch)`
- `Approve A + C1 (scratch docs + scripts/_probe*)`
- `Defer all deletes; archive *-live*.json later`
- Or itemized overrides

Anything classified **NEEDS_CESAR_CONFIRM** will not run without a specific named choice.

## Recommended buckets (summary)

| ID | Bucket | Class | Approx size |
|----|--------|-------|-------------|
| A1–A4 | `docs/delivery/_*` scratch dumps | SAFE_HARD_DELETE | ~77 files |
| B2 | Named `*-probe.json` / saylor probes | SAFE_HARD_DELETE (most) | ~10 |
| C1 | `scripts/_probe_saylor_*` | SAFE_HARD_DELETE | 5 |
| C2 | Most other `scripts/_*` one-offs | SAFE_HARD_DELETE / some CONFIRM | ~20 |
| C3 | `scripts/probe-*.py` | SAFE_HARD_DELETE | 11 |
| B4 | `docs/delivery/*-live*.json` | ARCHIVE_NOT_DELETE (relocate) | ~203 |
| Meson SKUs | scaffolding addons | ARCHIVE_NOT_DELETE (already archived in DB) | done |
| C4 | `scripts/smoke-*.py` (CI-wired) | NEEDS_CESAR_CONFIRM — keep unless retiring CI | ~91 |
| F | Operator org / Apollo CanvasGov / react-gate lists | NEEDS_CESAR_CONFIRM | vendor + org data |
| Seeds | Acme demo seeds / sandbox | NEEDS_CESAR_CONFIRM | several |

## Explicit non-candidates

- Real billing / Stripe / customer subscriptions
- Production `audit_events` / `workflow_runs` bulk wipes
- CI workflows and `backend/tests/**`
- Archive migration + Meson honesty gates

## Full inventory

See agent inventory from Phase 0 explore (exhaustive path lists for A1–A4, B, C, D, E, F).  
This file is the sign-off gate; execute only after Cesar confirms buckets by name.

## Phase 1 note (orthogonal — code fix, not Phase 0)

Live MSP run `978a2a90-6562-4290-8f42-10dcf9de42ad` failed at agent step with:
`asyncio.run() cannot be called from a running event loop`
Root cause: sync workflow agent/council/rag handlers used `asyncio.run` under an already-running FastAPI loop. Fix landed in `app.core.async_bridge.run_coro_sync` + handlers (not a data wipe).
