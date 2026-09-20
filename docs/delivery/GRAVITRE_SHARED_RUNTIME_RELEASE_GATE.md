# Shared runtime release gate

**Date:** 2026-09-20  
**Production kernel SHA:** `42fadd6179485971a36b5179834e3601514557b2`  
**Local/docs HEAD at write:** `d7edb73d` (ledger) plus this gate commit.

No further **shared-kernel 3.0** deploy until every row is PASS. This file is the enforceable checklist. Full `CI` workflow remaining red **does not** get relabeled green.

## Gate matrix

| # | Check | Status | Evidence |
|---|--------|--------|----------|
| 1 | Authenticated browser chat | **FAIL** | gravitre.app/login only; no SSO/password in agent env |
| 2 | Backend chat | **PASS** | `fd7ef9a1-…` / `e0ba3650-…` @ `42fadd61` |
| 3 | Text **and** voice regression suite | **PARTIAL** | Unit dual-path PASS; live text PASS; voice PCM post-fix **NOT RUN** |
| 4 | Composer / SSE invariant | **PASS** (unit) | no `Stopped.` raw SSE; `compose_reply_events`; cognitive suite typed-path PASS locally |
| 5 | WRITE governance | **PASS** (not weakened) | email turn clarified; no send |
| 6 | E4 ContextCompiler invariant | **PASS** (unit AST) | compile before ReAct; greeting does not require E4 |
| 7 | E5 plan lineage | **PASS** (unit) | 2.0-A invariants |
| 8 | F1 preflight | **PARTIAL** | unit + HubSpot live older SHA; greeting does not use F1 |
| 9 | No new P0/P1 | **PASS** for import-shadow | latency P2 for 10.9s greeting |
| 10 | Required CI workflow | **FAIL** | `CI` 15 pytest + (pre-fix) web suite; new job `Shared runtime text/voice gate` added |
| 11 | Current production SHA verified | **PASS** | `/health` `42fadd61` matches Vercel meta |

## Cross-modality matrix (permanent)

Run on every shared `execute_task_streaming` change:

| Modality | Case | This pass |
|----------|------|-----------|
| TEXT | greeting | Isolated PASS |
| TEXT | follow-up | Isolated PASS |
| TEXT | FAQ / what can you help | **NOT RUN** (browser) |
| TEXT | READ | Isolated honest clarify PASS |
| TEXT | clarification | PASS (email slots) |
| TEXT | approval | **NOT RUN** |
| TEXT | cancellation | **NOT RUN** |
| TEXT | provider error | **NOT RUN** |
| VOICE | greeting | **NOT RUN** (no PCM @ 42fadd61) |
| VOICE | follow-up | **NOT RUN** |
| VOICE | safe READ | **NOT RUN** |
| VOICE | interruption | Prior HTTP barge-in @ `2c0a85b5` / `43570699` — not re-proven |
| VOICE | correction | **NOT RUN** |
| VOICE | plan-hold | Unit PASS; live SLO @ `43570699` only |
| VOICE | approval interruption | Prior write_gate live; not re-proven |

Mandatory CI: job **Shared runtime text/voice gate** (`test_shared_kernel_typed_and_spoken_plan_hold_both_complete` + import-shadow tests).

## 3.0 vs 2.0 naming (do not obscure production)

| Layer | Fact |
|-------|------|
| 3.0 **specification** | `docs/ai/GRAVITRE_PLATFORM_EXECUTION_3.0.md` exists |
| 3.0 **code already on main** | 3.0-C plan-hold / voice SLO / F2 listing repair **are in the shared kernel** |
| 3.0 **deployed** | Railway `42fadd61` includes that kernel + shadow fix |
| 3.0 **live-proven** | Voice A/B and F2 sibling on `43570699`; typed chat isolated on `42fadd61`; **not** a completed 3.0 program |

Previous “3.0 implementation was not started” referred to **not opening new 3.0 product work in the audit turn**. It did **not** mean 3.0-C was absent from production. That distinction is now explicit.

## 2.0 program (unchanged conclusions)

- STRUCTURAL COMPLETE = **NO**
- TEST PROVEN = **PARTIAL**
- LIVE PROVEN = **PARTIAL**

## Resume 3.0?

**NO** until this gate is PASS (browser + post-fix voice PCM + documented CI).

**SHARED RUNTIME RELEASE GATE: FAIL**
