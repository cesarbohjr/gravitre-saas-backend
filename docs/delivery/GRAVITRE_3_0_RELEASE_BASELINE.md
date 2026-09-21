# GRAVITRE — 3.0 release baseline (do not auto-start 3.0)

**Baseline date:** 2026-09-20  
**Cesar approval required** before any further Platform Execution 3.0 product work.

This is the healthy pair future 3.0 changes must preserve. It is **not** a declaration that 2.0 or 3.0 programs are complete.

## Exact deployed pair

| Layer | Value |
|-------|--------|
| Backend | Railway `https://api.gravitre.app` SHA **`53a374c13376be865ecad5338003bd821bc45d48`** |
| Frontend | Vercel production `dpl_8JPmpwnf2UoSZNZvU8pUzEquHdLh` SHA **`53a374c1`** |
| Flags | `ai_disabled=false`, `unified_turn_live_enabled=true` |
| Required CI | [35528295674](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35528295674) success |

Kernel restore `42fadd61` is contained in this SHA. Do not revert `42fadd61`.

## Invariants 3.0 must not break

1. Typed and spoken share `execute_task_streaming`. No second chat runtime, Composer, planner, or ContextCompiler.
2. Function-local imports must not shadow `asyncio` / `compose_reply_events` (AST + shared-runtime CI job).
3. Composer is the sole user-prose authority. `shortcut` remains in `MUST_COMPOSE_KINDS` until a measured Option B ships.
4. F1 HMAC compile-before-invoke for READ/WRITE. Do not weaken tests to go green.
5. WRITE “Send an email.” must clarify or PendingAction — never unauthorized send.
6. Tenant isolation / conversation write guard remains enforced.
7. SSE: start → intelligence → text-delta → finish → `[DONE]`; generic `request_failed` toast is Composer copy, not raw exceptions.

## Performance baseline (isolated API @ `53a374c1`, n small)

| Metric | Observation | Status |
|--------|-------------|--------|
| Greeting first text-delta | 7231 ms (A), 6865 ms (B) | P2; not a p95 |
| Greeting wall | 9760 ms / 8941 ms | P2 |
| FAQ first-delta | 8829 ms | informational |
| Traffic clarify first-delta | 22249 ms | honest source ask |
| Email clarify first-delta | 25185 ms | no send |
| Voice first audible PCM | **not measured on this SHA** | BLOCKED |
| Historical voice Metric A | p50 224 / p95 412 ms @ **`43570699` only** | do not reuse as current |

## Evaluation baseline conversations

- Isolated matrix: `22020a9e-e486-41e0-ab09-28c4e42af2ce`
- Isolated smoke-ok: `f9dd81e8-faf8-400a-ac64-dc2692ab9987`

A 3.0 change that breaks typed hello, SSE terminal `[DONE]`, persistence of both hellos, WRITE clarify, or required CI **fails this baseline**.

## What this baseline does **not** include

- Operator-authenticated `/ai` UI (SSO still required).
- Post-fix PCM / barge-in / backchannel on this SHA.
- 2.0 LIVE_USER_PROVEN traffic (GA4/GSC OAuth), unique entity bind, recipes live, WRITE execute, multi-source live, continuity live, voice PCM.
- Customer certification chrome (still unauthorized). Proactive 2.0-M is internal recommend-only.

**READY TO RESUME 3.0 IMPLEMENTATION: YES** (engineering 3.0-H/I only) — Cesar 2026-09-21 deferred remaining human OAuth/browser/mic to the end. Browser + voice evidence still required before program-complete.

## 2026-09-21 note

3.0-H/I source implementation authorized. Human 2.0 package (isolated Google reconnect, Playwright after one login, Voice-C) remains deferred — not closed. Production SHA may lag `main` until Railway/Vercel catch up.

3.0-H/I **not closed:** required CI `35622991537` on `6d563e3d` is a historical FAIL; spoken confirm traces remain NOT RUN until the gateway hold SHA is live.
