# Gravitre AI chat regression — root cause

**Date:** 2026-09-20  
**Class:** `BACKEND_EXCEPTION` (local-name shadowing in `execute_task_streaming`)  
**Not:** frontend render, auth, SSE schema mismatch, preflight-on-hello, or UX Reset.

## 1. First failing stage

`AgentIntelligence.execute_task_streaming` (`backend/app/operators/agent_intelligence.py`) after Intent Gateway, **before** assistant `text-delta`.

Lifecycle for screenshot “hello”:


| Stage                               | Ran?                | Evidence                                                               |
| ----------------------------------- | ------------------- | ---------------------------------------------------------------------- |
| User submit / `useChat`             | Yes                 | User bubbles persisted; workspace `Error`                              |
| Auth + `POST /api/assistant/chat`   | Yes                 | HTTP 200 SSE                                                           |
| Turn init + Intent Gateway          | Yes                 | SSE `data-intelligence` `intent_gateway:phrase_bank`, `fastPath: true` |
| E1 / E4 / F1 / ReAct                | **No**              | Greeting is gateway shortcut; must not require connectors              |
| Response Composer `_composed_reply` | **Failed to enter** | `NameError: compose_reply_events`                                      |
| SSE `text-delta`                    | No                  | Isolated dump 2026-09-20T07:45Z                                        |
| Composer toast path                 | Yes                 | `emit_stream_error("request_failed")`                                  |
| UI                                  | Yes                 | Toast + presence Error                                                 |


Operator “send an email” failed **earlier in the same function** on `asyncio.gather` (`UnboundLocalError: asyncio`) — same defect class, different first use of the shadowed name.

## 2. Root cause (file/function)

Spoken plan-hold ultra-early path (`303df92f` / `43570699`) added **function-local**:

```python
import asyncio
from app.services.response_composer import compose_reply_events
```

inside `if _plan_hold_spoken_early and conversation_id:`.

Python then treated `asyncio` and `compose_reply_events` as locals for the **entire** `execute_task_streaming`. Typed `/ai` never took that branch, so:

- phrase-bank “hello” → `_composed_reply` → `NameError: compose_reply_events`
- smoke-ok / operator tasks → `asyncio.gather` → `UnboundLocalError: asyncio`

Module already imported both at file top. Nested import was unnecessary and fatal.

Logs (Railway `gravitre-saas-backend`):

- `2026-09-20 07:37:39Z` operator org `cbbf993b-…` `UnboundLocalError` `asyncio`
- `2026-09-20 07:37:52Z`–`07:38:58Z` same org `NameError` `compose_reply_events`
- `2026-09-20 07:42:38Z` isolated org smoke `UnboundLocalError` `asyncio`
- `2026-09-20 07:45:09Z` isolated “hello” `NameError` `compose_reply_events`

Toast copy is Composer `request_failed` (`response_composer.py` `_FALLBACK_BY_KIND`), emitted by `assistant.py` when the unified stream raises before any `text-delta`. Original exception type is **logged**, not shown in UI (by design; not the bug).

## 3. Triggering commit / deployment


| Item               | Value                                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------------------------- |
| Introduced         | `303df92f` plan-hold ultra-early; still present in `43570699` (skip gateway/composer LLM on spoken plan-hold) |
| Broken prod tip    | `43570699e5f5d8e693a618c1abe4f66e3fe97705` (`/health` during outage)                                          |
| Not UX Reset       | Frontend `useChat` received a real SSE `error` event                                                          |
| Not 2.0-A cohesion | 2.0-A did not add those inner imports                                                                         |
| Interaction        | 3.0-C **voice Metric B** change on the **shared** `execute_task_streaming` kernel used by typed `/ai`         |


Last known-working general typed chat on this kernel: tips **before** the inner imports (`12aa048d` / earlier). F2/voice probes on `43570699` could still succeed because they used spoken/plan-hold or other entrypoints.

## 4. Frontend/backend contract

Compatible. Isolated dump:

```
start → start-step → data-intelligence (Understanding…) → data-intelligence (phrase_bank, fastPath) → error → [DONE]
```

HTTP 200. Frontend parsed `errorText` correctly. Assistant deltas were not discarded — they were never sent.

## 5. Fix implemented

Remove nested `import asyncio` and `from app.services.response_composer import compose_reply_events`. Use module-level imports already present.

Commit: `42fadd61` `fix(chat): stop spoken plan-hold inner imports from breaking typed /ai.`

Did **not**: replace E1–E5, weaken WRITE/HMAC, bypass Composer, hard-code hello, add a second workspace, or raise timeouts.

## 6. Files changed (fix + audit)

- `backend/app/operators/agent_intelligence.py`
- `backend/tests/operators/test_agent_intelligence.py`
- `backend/tests/services/test_platform_execution_2_0_a_invariants.py`
- `scripts/verify-ai-chat-regression-live.py`
- this report + 2.0 final audit + requirement ledger



## 7. Tests added

- `test_execute_task_streaming_does_not_rebind_module_imports` (co_varnames)
- `test_execute_task_streaming_does_not_shadow_asyncio_or_composer` (2.0-A invariants)
- Existing `test_gateway_shortcut_composes_before_task_state_reload` (hello / phrase_bank)



## 8. Local test results

`backend/tests/operators/test_agent_intelligence.py` greeting + scoping tests: **2 passed** (2026-09-20).

CI on `42fadd61`: **Backend pytest FAIL**, **Web lint/typecheck/build FAIL** (run `35497980128`). Standing CI red; **not** used as production-fixed proof. Railway production workflow **PASS** (`35497980123`).

## 9. Production evidence


| Check                                | Result                                                                                                                                                                  |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/health` SHA                        | `42fadd6179485971a36b5179834e3601514557b2`                                                                                                                              |
| Isolated smoke                       | **PASS** conv `e0ba3650-8144-444e-8c31-9197930b28af` assistant `smoke-ok` @ `2026-09-20T07:57:25Z`                                                                      |
| Isolated hello+follow-up+READ+email  | **PASS** conv `fd7ef9a1-b081-45f5-b23e-6eb4b0a0d97c` @ `42fadd61`; hello 10897ms; follow-up 5667ms; traffic clarify 4010ms; email clarify 12967ms; persisted 8 messages |
| Vercel production deploy             | `dpl_6kRCG18GGgsVk1EUgcRaTEBUj3Cd` meta SHA `42fadd61`                                                                                                                  |
| Operator-org browser `/ai` after fix | **LIVE NOT RUN** this pass (screenshot was pre-fix)                                                                                                                     |
| Voice greeting audio                 | **LIVE NOT RUN** (no PCM capture)                                                                                                                                       |




## 10. Remaining limitations

- Generic toast still hides `error_type` from operators; structured codes stay in logs.
- Failed user bubbles remain; retry can add another user line (screenshot showed three “hello”) — conversation integrity UX not redesigned here.
- CI main is red independently of this fix.
- Isolated-org traffic READ / email WRITE-shape: see `gravitre-ai-chat-regression-live.json` (filled by live probe).



## 11. Rollback

`git revert 42fadd61` **re-breaks** typed chat. To roll back **voice plan-hold** work instead, revert `303df92f`/`43570699` only after replacing the inner imports with module imports (already done). HMAC/WRITE flags unchanged.

## Scenario matrix (prompt Part 3)


| ID  | Prompt                     | Result                                                                   |
| --- | -------------------------- | ------------------------------------------------------------------------ |
| A   | hello (new conv)           | Isolated API **PASS** — “Hey — I’m here…” `fd7ef9a1-…`; pre-fix **FAIL** |
| B   | hello follow-up            | **PASS** same conv, second assistant reply persisted                     |
| C   | website traffic last month | **PASS** honest clarify (no analytics source); not empty/toast           |
| D   | Send an email              | **PASS** clarification for recipient/subject/body; no send               |
| E   | Voice greeting             | **LIVE NOT RUN** (no audio)                                              |




## 13. Latency before/after (typed)


| Turn     | Before (`43570699`)                    | After (`42fadd61`)                      |
| -------- | -------------------------------------- | --------------------------------------- |
| hello    | ~2856ms then **error** (no text-delta) | 10897ms wall; SSE includes `text-delta` |
| smoke-ok | ~5s **error**                          | ~19s PASS `smoke-ok`                    |


Failure class was **exception**, not timeout. Do not add another model call to fix greetings.