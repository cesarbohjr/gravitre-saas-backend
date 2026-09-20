# Shared runtime release gate

**Date:** 2026-09-20  
**Production kernel SHA (Railway `/health` 2026-09-20T18:28:33Z):** `53a374c13376be865ecad5338003bd821bc45d48`  
**Frontend Vercel production:** `53a374c1` (`dpl_8JPmpwnf2UoSZNZvU8pUzEquHdLh`)  
**origin/main:** `53a374c1`

No further **shared-kernel 3.0** deploy until Cesar approves. Full `CI` on this SHA is green; the **product** gate still requires browser + post-fix PCM.

## Gate matrix

| # | Check | Status | Evidence |
|---|--------|--------|----------|
| 1 | Authenticated browser chat | **BLOCKED** | gravitre.app/login SSO; agent must not complete Cesar’s session |
| 2 | Backend chat | **PASS** | Isolated `22020a9e-…` + smoke `f9dd81e8-…` @ Railway `53a374c1` |
| 3 | Text **and** voice regression suite | **PARTIAL** | CI shared-runtime job PASS; live text PASS; PCM **VOICE_AUDIO_BLOCKED** |
| 4 | Composer / SSE invariant | **PASS** | Live `[DONE]` no toast; unit Composer + no `Stopped.` |
| 5 | WRITE governance | **PASS** (this SHA isolated) | “Send an email.” → Gmail vs draft; no send |
| 6 | E4 ContextCompiler invariant | **PASS** (unit) | compile before ReAct; greeting does not require E4 |
| 7 | E5 plan lineage | **PASS** (unit) | 2.0-A invariants |
| 8 | F1 preflight | **PARTIAL** | unit PASS on this SHA; HubSpot live older SHA; greeting does not use F1 |
| 9 | No new P0/P1 | **PASS** for import-shadow | greeting first-delta ~7s is P2 |
| 10 | Required CI workflow | **PASS** | `35528295674` all required jobs success |
| 11 | Current production SHA verified | **PASS** | Railway + Vercel **`53a374c1`** |

## Cross-modality matrix (permanent)

| Modality | Case | This pass |
|----------|------|-----------|
| TEXT | greeting | Isolated PASS @ `53a374c1` |
| TEXT | follow-up | Isolated PASS |
| TEXT | FAQ | Isolated PASS |
| TEXT | READ | Isolated honest clarify PASS |
| TEXT | clarification | Isolated email slots PASS |
| TEXT | approval | **NOT RUN** (no PendingAction execute) |
| TEXT | cancellation | **NOT RUN** |
| TEXT | provider error | **NOT RUN** |
| VOICE | greeting | **NOT RUN** (no PCM @ `53a374c1`) |
| VOICE | follow-up | **NOT RUN** |
| VOICE | safe READ | **NOT RUN** |
| VOICE | interruption | Prior HTTP barge-in @ `43570699` — not re-proven |
| VOICE | correction | **NOT RUN** |
| VOICE | plan-hold | Unit PASS; live SLO @ `43570699` only |
| VOICE | approval interruption | Prior write_gate live; not re-proven |

Mandatory CI: job **Shared runtime text/voice gate** — **PASS** on `53a374c1`.

## 3.0 vs 2.0 naming

| Layer | Fact |
|-------|------|
| 3.0 specification | exists |
| 3.0 code already on main | 3.0-C plan-hold / voice SLO / F2 listing repair in shared kernel |
| 3.0 deployed | Railway `53a374c1` includes that kernel + shadow fix + CI alignments |
| 3.0 live-proven | Voice A/B on `43570699`; typed isolated chat on `53a374c1`; browser NOT RUN |

## 2.0 program

- STRUCTURAL COMPLETE = **NO**
- TEST PROVEN = **PARTIAL**
- LIVE PROVEN = **PARTIAL**

## Resume 3.0?

**NO** — Cesar’s release approval. Browser + post-fix PCM remain open. See `GRAVITRE_3_0_RELEASE_BASELINE.md`.

**SHARED RUNTIME RELEASE GATE: FAIL** (required CI job PASS; product PCM/browser open)
