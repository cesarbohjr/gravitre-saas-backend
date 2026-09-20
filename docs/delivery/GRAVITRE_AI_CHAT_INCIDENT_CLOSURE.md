# AI chat incident closure

**Date:** 2026-09-20  
**Incident:** Typed `/ai` generic `request_failed` toast; no assistant bubbles.

## 1. Production state (checked, not assumed)

| Surface | Value |
|---------|--------|
| Local / origin/main | **`e2ca544135ed8fd7210f2408845862e9b6ce8182`** (2026-09-20T08:46Z re-check; harness/docs after kernel fix) |
| Railway `/health` | **`42fadd6179485971a36b5179834e3601514557b2`** @ `2026-09-20T08:46:13Z` (`ai_disabled=false`, `unified_turn_live_enabled=true`, shadow+QA hooks on) |
| Vercel production | **`dpl_Ah8SPrV3v79eRjyxKAw2csQzHKz9`** meta SHA **`e2ca5441`** (frontend). Prior alias `dpl_6kRCG18GGgsVk1EUgcRaTEBUj3Cd` was `42fadd61`. |
| Kernel vs frontend | Docs/harness commits after `42fadd61` **did not** move Railway SHA. Chat kernel in prod API remains `42fadd61`. |

Shared-runtime changes since last independently verified **typed** chat (pre-`303df92f`): 3.0-C plan-hold ultra-early + composer skip on spoken path (`303df92f`, `9f98393a`, `43570699`) then import-shadow fix `42fadd61`.

## 2. Authenticated production `/ai` (browser)

**LIVE NOT RUN / gate FAIL.**

`https://gravitre.app/login` loaded (screenshot). Password env keys are **absent** in operator dotenv; SSO (Google/GitHub/Microsoft) cannot be completed by this agent. Isolated JWT API is **not** a browser session.

## 3. Backend chat

**PASS** isolated org, SHA `42fadd61`:

- Smoke: conv `e0ba3650-8144-444e-8c31-9197930b28af` `smoke-ok`
- Matrix: conv `fd7ef9a1-b081-45f5-b23e-6eb4b0a0d97c`
  - hello → “Hey — I’m here…” 10897ms
  - follow-up hello 5667ms
  - traffic last month → honest clarify 4010ms
  - Send an email → recipient/subject/body clarify 12967ms
  - 8 messages persisted HTTP 200

## 4. Voice live

| Claim | Status |
|-------|--------|
| Text of spoken plan-hold / Metric A/B | Prior artifact `voice-slo-two-metric-live.json` @ **`43570699`** (not re-run on `42fadd61`) |
| First audible PCM after `42fadd61` | **LIVE NOT RUN** |
| Browser Talk | **LIVE NOT RUN** |

A voice-only prior probe **cannot** certify post-fix typed runtime; a text-only probe **cannot** certify audio.

## 5. CI

| Job | Result on `42fadd61` (`35497980128`) | First known (this window) | Root cause | Runtime relevant? | Owner | Disposition |
|-----|--------------------------------------|---------------------------|------------|-------------------|-------|-------------|
| Backend (pytest) | **FAIL** 15 failed / 6478 passed | Present on `43570699` and `bafdffe7` same day | Mixed: F1 compile-before-invoke on slack tests; ActionSpec identity; overlap-guard source shape; Anthropic fixture; lint dict-coercion; `business_entities` table lint; voice perceive assertion | Mixed — several **are** 2.0 compile/HMAC; **not** the import-shadow bug | Runtime / catalog | **Do not call CI green.** Track as standing-red. |
| Web (lint + typecheck + build) | **FAIL** at Cognitive regression suite | `43570699` 3.0-C | Naive source-order: first `get_cognitive_loop_controller` was spoken plan-hold **before** gateway | Scanner false-positive vs typed path | Runtime | **Fixed** scanner to score typed path after plan-hold branch (`scripts/cognitive-regression-suite.mjs` local PASS) |
| Marketing Lighthouse | FAIL on docs commit | unrelated | marketing | No | Creative | Non-blocking for kernel |
| Railway backend production | **PASS** `35497980123` | n/a | deploy+isolated smokes | Yes | Ops | Required for prod SHA |

**Required GitHub workflow `CI` remains red** until the 15 pytest failures are owned. Job **Shared runtime text/voice gate** is the **mandatory kernel gate** (does not hide full CI). Evidence: **PASS** on `e2ca5441` run `35500286861` job `106050747907` (typed greeting + spoken plan-hold + import-shadow tests). Full `CI` on `42fadd61` is still **FAIL** `35497980128`.

## 6. Greeting latency

Not a timeout. Path is Intent Gateway **phrase_bank shortcut** then Composer `kind=shortcut` which is in `MUST_COMPOSE_KINDS` → **foundation-model rewrite** of an already-English bank line.

Measured (isolated, `42fadd61`):

| Sample | Wall to complete | Notes |
|--------|------------------|-------|
| hello (first in new conv) | 10897ms | SSE includes `text-start/delta/end`; no error |
| hello follow-up (warm conv) | 5667ms | Same phrase-bank path |
| Failed hello on `43570699` | ~2856ms | **Exception**, not a valid faster answer |

Critical path (proven): gateway shortcut **does** run (intelligence `intent_gateway:phrase_bank`) → `_composed_reply` LLM compose → first text-delta. No F1/preflight/ReAct on greeting. Workspace focus + task_state load still run **before** shortcut return.

**Not done this pass:** skip Composer LLM for safe shortcut drafts (would need A13 exception). No new hello handler.

## 7. Import-shadowing protection

- `co_varnames` tests (existing)
- AST: no branch-local `import asyncio` / `compose_reply_events` in `execute_task_streaming`
- **Behavioral:** `test_shared_kernel_typed_and_spoken_plan_hold_both_complete` — typed hello + spoken plan-hold both emit Composer `text-delta` + `AssistantStreamComplete`
- Surrounding kernel: `_prepare_turn_context` already documents a prior closure NameError on `intelligence_orchestrator`; left as-is (proven fix pattern). No additional UnboundLocal found for `asyncio`/`compose_reply_events`.

## 8. Retry integrity

Screenshot three “hello”s = **three separate submits** after stream errors, not one request cloning the user turn. `submitLockRef` blocks overlapping send. `regenerate` keeps the user turn and replaces assistant. Failed turns did not resume a PendingAction. WRITE not invoked on greeting. **No code change** — no demonstrated single-request duplication.

## 9. Benchmark (honest)

p50/p95 **not** claimed (n=2 greetings). Voice PCM n=5 exists only on **pre-fix** SHA `43570699` (Metric A p50 224 / p95 412). Do not compare 10.9s success to 2.8s crash.

## 10. Closure

Incident **code** is fixed on Railway `42fadd61`. Incident **closure** requires browser `/ai`, post-fix voice PCM, and an honest CI story.

**AI CHAT INCIDENT CLOSED: NO**
