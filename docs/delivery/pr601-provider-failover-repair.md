# PR 601: shared tool-model failover repair

## Source mapping and defect

`ModelRouter` uses `providers.failover.build_priority`, `run_failover` and its
shared circuit breaker for standard completions. In contrast,
`provider_tool_router.complete_with_tools` dispatched directly to one SDK.
Unified reasoning streamed OpenAI directly, and classical ReAct had a separate
OpenAI streaming entrypoint. Consequently an SDK 401 escaped these paths into
the unified error/fallthrough boundary instead of trying the configured chain.

## Targeted change

Tool completions now adapt inference callbacks to the existing `run_failover`
executor, `build_priority` tier ordering and ModelRouter circuit breaker. The
requested model is first, followed by other providers in the matching tier
(medium for unknown model IDs), only when `ai_failover_enabled` is true.
Missing credentials and open circuits are skipped by the existing executor.
Every candidate passes the existing model-policy/budget authorization before
SDK dispatch; policy failures do not trigger recovery. HTTP 401/403/408/429/5xx
are mapped to sanitized availability failures. Bad input and unrelated errors
still propagate. No new connector execution loop or credential store is added.

Unified voice and classical ReAct streaming share this inference boundary.
History, system/personality prompt, narrowed schemas and tool-result messages
are retained across attempts. Recovery stops once text or tool deltas have
arrived; it cannot concatenate a second answer or replay a partial tool stream.
Only inference is retried, not connector execution. Unified usage and classical
ReAct tool-loop usage record the actual successful model.

## Local validation

95 passed, one existing Starlette deprecation warning:

```sh
PYTHONPATH=backend python -m pytest \
  backend/tests/services/test_tool_provider_failover.py \
  backend/tests/services/test_failover.py \
  backend/tests/services/test_provider_tool_router.py \
  backend/tests/services/test_unified_turn_conversational_model.py \
  backend/tests/operators/test_react_spoken_answer_streaming.py \
  backend/tests/services/test_unified_turn_reasoning.py -q --tb=short
```

New regressions cover classical 401 recovery with unchanged state, invalid-input
non-recovery, disabled failover, sanitized exhaustion, policy denial, unified
recovery, partial text/tool non-replay, and actual unified OpenAI dispatch failing
401 followed by an Anthropic tool completion. Provider transports are mocked;
no billable inference or production writes occurred. `git diff --check` passed.

## Remaining certification boundaries

This repairs the observed authentication recovery handoff; it does not repair an
invalid credential. No production deployment, live task completion, audio listening,
full standing live batteries or ChatGPT parity certification was performed.
Cross-turn auth backoff and conversation repair from PR 600 remain separate.
The classical `_run_reasoning_only` path still directly uses OpenAI and needs its
own reconciliation; this report does not certify it. End-to-end task completion,
seven-layer/personality invocation and effective production configuration remain
open gates. Non-OpenAI fallback currently buffers its completion, preserving the
existing behavior rather than claiming native streaming parity.
