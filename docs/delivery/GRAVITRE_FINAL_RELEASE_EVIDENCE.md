# GRAVITRE — final release evidence (2026-09-20)

Checked at **2026-09-20T18:28–18:33Z**. Do not treat a successful deploy as a successful product release.

## R0 — SHA reconciliation

| Surface | SHA / id |
|---------|----------|
| Local HEAD | `53a374c13376be865ecad5338003bd821bc45d48` |
| origin/main | `53a374c13376be865ecad5338003bd821bc45d48` |
| Railway `/health` `git_sha` | `53a374c13376be865ecad5338003bd821bc45d48` (`status=ok`, `2026-09-20T18:28:33Z`) |
| Vercel production | `dpl_8JPmpwnf2UoSZNZvU8pUzEquHdLh` meta **`53a374c1`** |
| Required CI | [35528295674](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35528295674) **success** on `53a374c1` |

Reconciled prior SHAs (not assumed current):

| SHA | Role | Deployed now? |
|-----|------|----------------|
| `42fadd61` | Import-shadow kernel restore | **Superseded.** Kernel still present in `53a374c1`. |
| `e2ca5441` | Prior frontend/harness gate | **Superseded** on Vercel by `53a374c1`. |
| `635b8229` | Docs SHA-split note | Intermediate docs commit; not a kernel. |
| `53a374c1` | CI/HMAC/contract/instrumentation + shared-runtime gate expansion | **Yes — frontend and backend pair.** |

**Contract compatibility:** Frontend and backend both expose `53a374c1`. Isolated SSE on `POST /api/assistant/chat` used `start` → `data-intelligence` → `text-start`/`text-delta`/`text-end` → `finish` → `[DONE]`. Cancellation still uses `clear_stop(org_id, conversation_id)`. Voice HTTP session contracts were not re-exercised with PCM on this SHA.

Flags from `/health`: `ai_disabled=false`, `unified_turn_live_enabled=true`, `unified_turn_shadow_enabled=true`. Checks: database **healthy**, cache **healthy**.

## R1 — Required CI

Run **35528295674** conclusion **success**, head `53a374c1`.

| Job | Result |
|-----|--------|
| Web (lint + typecheck + build) | success |
| Backend (pytest) | success |
| Shared runtime text/voice gate | success |
| Integration Smoke Test | success |
| Dependency audit | success (nonblocking annotation history may still show a scanner exit; job conclusion is success) |
| Billing E2E (Playwright) | skipped (not required for this gate) |

HMAC, Composer, tenant isolation, and plan-lineage tests were **not** weakened. Local retest this pass: **62 passed** (`test_platform_execution_2_0_a_invariants`, F1 write preflight, Composer, conversation write guard, shared-kernel typed+spoken plan-hold).

## R2 — Production pair

| Layer | Deploy | SHA |
|-------|--------|-----|
| Backend Railway | `https://api.gravitre.app/health` | `53a374c1` |
| Frontend Vercel | `gravitre.app` ← `dpl_8JPmpwnf2UoSZNZvU8pUzEquHdLh` | `53a374c1` |

Compatible pair: **frontend `53a374c1` + backend `53a374c1`**. No schema-mismatch signal on `/health`.

## R3 — Authenticated `/ai`

**AUTHENTICATED_BROWSER_BLOCKED**

Login page loaded at `https://gravitre.app/login` (Continue with Google / GitHub / Microsoft + email/password). This agent must not complete Cesar’s SSO or capture credentials.

Human steps:

1. Open `https://gravitre.app/login`.
2. Sign in with the operator SSO used for Cesar’s production account (Google, GitHub, or Microsoft). Use email/password only if that account is email-based.
3. Open `/ai`.
4. Run Tests A–F (hello, follow-up hello, “What can you help me with?”, last-month traffic, “Send an email.”, compact/expanded/fullscreen/minimize/restore/navigate/refresh).

Isolated JWT API is **not** a substitute for those steps.

## R3 / R7 — Isolated backend chat (same SHA)

Artifact: `docs/delivery/gravitre-ai-chat-regression-live.json`  
Conversation `22020a9e-e486-41e0-ab09-28c4e42af2ce` org `f07e57c0-1501-4000-8000-c04e57a00001`  
Post-deploy smoke: `f9dd81e8-faf8-400a-ac64-dc2692ab9987` `smoke-ok` ~30s @ same SHA.

| Turn | Prompt | HTTP | first_delta_ms | wall_ms | Terminal | Notes |
|------|--------|------|----------------|---------|----------|-------|
| A | hello | 200 | 7231 | 9760 | `[DONE]`, no error | “Hey — I’m here…” |
| B | hello | 200 | 6865 | 8941 | `[DONE]` | Same conversation; second user hello persisted; no clone of turn A |
| C | What can you help me with? | 200 | 8829 | 10927 | `[DONE]` | Conversational; no connector preflight failure |
| D | website traffic last month | 200 | 22249 | 27081 | `[DONE]` | Honest source clarify; no parameter vocabulary dump |
| E | Send an email. | 200 | 25185 | 34317 | `[DONE]` | “Gmail, or draft it first?” — no send |

Persistence GET 200: 5 user + 5 assistant rows, one pair per turn. Retry/integrity: two “hello” rows are **two submissions**, not automatic cloning. Failed-turn poison: **NOT RUN** (no induced Error state this pass).

Workspace compact/expanded/fullscreen: **NOT RUN** (browser).

## R4 — Shared kernel

CI job **Shared runtime text/voice gate** **PASS** on `53a374c1`.  
Local `test_shared_kernel_typed_and_spoken_plan_hold_both_complete` **PASS**.  
AST import-shadow invariant remains in `test_execute_task_streaming_does_not_shadow_asyncio_or_composer`.  
Live typed path **PASS** (matrix above). Live spoken PCM **BLOCKED**.

## R5 — Post-fix voice PCM

**VOICE_AUDIO_BLOCKED** on `53a374c1`.

Historical Metric A p50 **224 ms** / p95 **412 ms** remains valid **only** for SHA `43570699` and **does not** certify this release.

## R6 — Greeting latency

Path unchanged: Intent Gateway phrase-bank shortcut → Composer `kind=shortcut` ∈ `MUST_COMPOSE_KINDS` → foundation-model rewrite → SSE text.

This SHA, isolated, n=2 greeting-class turns (A cold-ish, B warm follow-up):

- Time to first **text-delta**: 7231 ms, 6865 ms (sample too small for p95).
- Time to final spoken-equivalent text: 9760 ms, 8941 ms.
- Prior isolated hello @ `42fadd61`: 10897 ms / warm 5667 ms. Do not mix crash timeouts with these successes.

Checkpoints exist on `task_state.shortcut_latency_ms` (`client_ready`, `workspace_focus_resolved`, `intent_gateway`, `shortcut_composer_start/end`, `shortcut_first_text_delta`) and `shortcut_composer_used_model`. This probe did not scrape those fields from `data-intelligence`.

**Option A** (faster model-backed Composer): preserve `MUST_COMPOSE_KINDS`, shrink prompt/context, cheaper compose model. **Not implemented.**

**Option B** (deterministic Composer render when bank copy is already English, same skip as `plan_hold`/`progress`): Composer remains sole prose authority; no extra LLM. Needs A13 exception + quality A/B. **Not implemented.** Bank line and composed line remain similar (“Hey — I’m here…”). Shipping B without quality measurement would silently change greeting semantics for latency.

## R8 — Golden verification (this pass)

| Suite | Result |
|-------|--------|
| 2.0-A invariants (E4 compile-before-ReAct, Composer, import shadow, no `Stopped.`) | PASS (included in 62) |
| F1 WRITE preflight / HMAC | PASS |
| Composer + bypass | PASS |
| Conversation write guard (tenant/write isolation) | PASS |
| Shared typed + spoken plan-hold | PASS |
| Full GitHub Backend pytest | PASS (CI job) |
| HubSpot / QuickBooks / Zendesk live HMAC | **NOT RE-RUN** this closure (prior HubSpot @ `67944d59`) |
| Analytics traffic LIVE_USER_PROVEN | **BLOCKED** (GA `pending_auth` historically) |

## R9 — Observability

Reconstructable on this path: `conversation_id`, org, `/health` SHA, SSE event types, HTTP status, first_delta/wall, Composer `request_failed` toast (generic). Backend exception logs include `org_id` + error type. Shortcut logs include `shortcut_latency` checkpoints. `turn_id` / plan ID are present when `data-intelligence` carries `task_state`; this probe did not persist those IDs into the JSON. Secrets were not logged. Correlation gap for operators: generic UI error still lacks a copied request id — **nonblocking**, not a new runtime.

## R11 — Decision

**CONDITIONALLY READY FOR INTERNAL TESTING.**

Blocking for **RELEASE READY**: authenticated production `/ai` Tests A–F, post-fix voice PCM.

Not blocking the original P0 (import-shadow `UnboundLocalError`/`NameError`): fixed `42fadd61`, still present in `53a374c1`, isolated chat **PASS**, required CI **PASS**.
