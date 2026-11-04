# PR 601 — Conversational execution continuation checkpoint

## Exact source change
- Spoken ReAct formerly rejected `router._openai is None` **before** shared model failover. This bypassed the configured Anthropic/Gemini fallback even if a candidate was available.
- `backend/app/operators/react_engine.py::_stream_chat_with_tools` now passes the optional OpenAI client to `_complete_unified_turn`, which owns candidate availability, authorization, circuit breaker, and fallback.
- `backend/tests/operators/test_react_spoken_answer_streaming.py::test_spoken_stream_allows_fallback_without_openai_client` covers preservation of the identical system/persona/task message list, returning the successful provider model and an honest response, with no external SDK calls.
- The separate tool-failover regression suite already covers actual mocked 401 → Anthropic dispatch and denial/partial-stream safeguards. This new adapter test **does not** itself prove a live 401 recovery, Outlook read or physical voice quality.

## PR 600 reconciliation — exact overlapping files
PR 600 `b57aad0d1192123300b8c03b57777034aa42cf7a` and PR 601 overlap on precisely:
1. `backend/app/services/providers/provider_tool_router.py`
2. `backend/app/services/unified_turn_reasoning_service.py`

The rest of PR 600's 19 changed paths are disjoint at this checkpoint, including context discovery, intent gateway, clarification repair, auth backoff and PCM diagnostics. **Do not replace** PR 601's canonical tool failover functions with the older PR 600 direct-SDK version; **do not omit** PR 600's authentication backoff. Both contracts must coexist:
- Before each candidate SDK request check the shared credential backoff. HTTP 401 marks only that provider/credential fingerprint unhealthy for the bounded interval; rotation permits retry. Do not reveal a key, exception body or prompt in telemetry.
- Candidate selection and fallback remain owned by `run_tool_failover`, after authorization and narrowed-tool validation. Never replay tool writes or partial text/audio. Backoff is per provider and cannot globally suppress a healthy alternative.
- Unified OpenAI stream and the classical tool dispatcher use the same backoff, but streamed partial output cannot be retried on another provider. Preserve the successful model for accounting.
- PR 600's contextual discovery and clarification logic can be integrated from their existing source paths; do not implement parallel discovery in PR 601.
- Preserve PR 600 worklet cache bump and client/backend PCM diagnostics schema as a unit; inspect production frontend version before claiming listening parity.

## End-to-end acceptance matrix (current evidence)
| Journey | Current outcome | Missing evidence |
| --- | --- | --- |
| Gmail → “What other email provider can you use?” → Outlook read | NOT_RUN/NOT_CERTIFIED | Combined PR 600 context routing, live authorized Outlook connection/status, real read, result provenance, response |
| Model 401 → configured fallback → retained persona/task/history | PARTIAL SOURCE + MOCK REGRESSIONS | Runtime credentials/selected provider, full multi-turn replay, confirmed response |
| Connected tool execution and verified outcome | NOT_CERTIFIED | Correlated tenant-scoped tool receipts, independent readback, no false success |
| Approval-gated multi-step writes and cancellation | PARTIAL CI | Real controlled scenario and independent cross-tenant/write-fence audit |
| Seven intelligence capabilities and personas | SOURCE + OFFLINE CI | Seven per-turn activation/defer traces, final prompt injection and observable output influence |
| Live acoustic, reconnect, barge-in, 20-minute voice | NOT_RUN | Device/transport/audio recordings and human listening; provider jobs skipped |
| PR 600 combined code compatibility | NOT_RUN | Content-aware merge, combined-tree tests and CI at resulting exact SHA |

## Next engineering gate
Create a content-aware integration of PR 600 onto PR 601, preserving both overlapping provider functions. Run combined nonbillable tests including contextual connector discovery, auth backoff, tool provider fallback, unified reasoning, ReAct spoken streaming, PCM output diagnostics and mandatory governed-write suites. Collect exact combined SHA, job-level skip/pass, privacy-safe Outlook journey evidence and security write-fence results. Do not mark live or physical tests PASS from green workflow summaries.

**Disposition:** A targeted source fix and regression have been committed to PR 601. No production writes, provider billing, PR merge, production deployment or live parity certification were performed.
