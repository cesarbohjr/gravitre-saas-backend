# ECO-012 / DEC-003: confirmed LIVE stop is terminal

Base PR #611 SHA: `04c08b3c183ce1e3c404a72f6de3b582d813c59e`.
All ten PR workflows completed successfully on that exact SHA, attempt 1.
This is prerequisite evidence, not hosted verification of the repair below.

| Workflow | Verified result |
| --- | --- |
| Core | [45087810692](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810692): success |
| Operations | [45087810677](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810677): success |
| QA04 | [45087810681](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810681): success |
| QA12 | [45087810637](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810637): success |
| Identity | [45087810695](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810695): success |
| Data | [45087810687](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810687): success |
| Intelligence | [45087810734](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810734): success |
| Voice | [45087810804](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810804): success |
| Browser | [45087810630](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810630): success |
| Marketing | [45087810776](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810776): success |

Core required contexts all succeeded:
Backend pytest [137410357628](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810692/job/137410357628),
Web lint/typecheck/build [137410357704](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810692/job/137410357704),
Shared text/voice [137410357576](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810692/job/137410357576),
Dependency audit [137410357716](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810692/job/137410357716),
Integration Smoke [137410357641](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810692/job/137410357641).
Backend log: **17,453 passed, 64 skipped, 14 subtests passed**.

QA12 actual guards job137410368138 passed the mandatory real PostgREST16.6
gate with hosted PostgreSQL18.7: **20 passed, zero skips**.
Downloaded and parsed [artifact14780780497](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45087810637/artifacts/14780780497)
has matching base SHA, status PASS, tests20/skipped0, external_project_used false
and certifies_whole_finding false. ZIP SHA256:
`33d9bbaa7cea2620c314906854c96e9de044dd5a1457d8217fe2bfa52daa5489`.
The older artifact14776675351 remains preserved and was not downloaded again.

Skipped live/provider/billing/signed jobs are not acceptance. The successful
physical-voice reserved job ran simulated/schema contracts, not device acceptance.

## Failure reproduced through the actual caller

`run_unified_turn_shadow` observes the existing stop service and returns
`outcome_kind=skipped`, `fallthrough_reason=chat_stop`, `error=stopped`.
`apply_unified_turn_live` previously overwrote that reason with `outcome_skipped`
and returned None, the caller's classical-delegation signal.
`AgentIntelligence.execute_task_streaming` consequently entered ReAct.

The new joined regression failed on the unmodified source with
`AssertionError: Stopped LIVE turn reached the classical executor`.
The shadow result is injected at the model boundary; this reproduces handling
of the real runner's stop-result shape, not the timing of a live stop request.
It does not demonstrate an unauthorized provider write.

## Bounded repair

The result recognizes cancellation only for that exact three-field stop shape.
LIVE preserves the stop reason and returns an explicit cancelled terminal
payload, with no text/tool results. The caller cancels unused context prefetch,
closes an open text part and returns its existing cancelled completion shape.
It does not enter another executor, compose a success response or finalize work.
Partial text already released before a stop is not retroactively erased from UI;
no UI/audio device acceptance is claimed.

The audit action is `unified_turn.live.cancelled`, with
`classical_path_active=false`, `shadow_user_visible=false` and
`turn_terminal_state=cancelled`. Other skipped/error results retain delegation.
The legacy chat_stop field is preserved; it is a terminal marker, not a new
entry in the delegated fallthrough enum. No cancellation flag is cleared.

## Verification and limits

**183 focused checks passed locally** with normal backend conftest:

* 60: new terminal/delegation contracts, existing enum/source contracts and
  dynamic-prefix validation. The new audit matrix exercises all 11 declared
  reasons and two dynamic examples through the actual marker/audit emitter.
  This is not a full branch-by-branch caller journey for each reason.
* 122: existing unified reasoning, write-staging narration, fallback handoff,
  ReAct execution, write-approval and runtime safety suites.
* 1: joined AgentIntelligence/LIVE cancellation regression; no classical call,
  empty cancelled completion, no text deltas, cancellation audit.

The model, context compilation, audit storage and downstream I/O are isolated.
The first reproduction exposed unrelated network work in the existing streaming
helper's context compiler; the new test explicitly stubs that compiler. Tests use
synthetic identities/credentials, not deployed services. Local proxy variables
were unset because this task Python lacks socksio. No test assertion or security
gate was relaxed. Ordinary skip/error delegation is independently retained.

Shared text/spoken-mode decision handling is covered; PR #610 retains ownership
of Voice implementation and physical/audio acceptance. No provider, persistence,
deployed cancellation race, customer UI, rollback or retirement certification is
claimed. Both audit stores and twelve canonical workflows remain.

ECO-012 and DEC-003 receive bounded engineering evidence only. Fresh exact-head
hosted CI is required after publication; all finding-level acceptance criteria
and closure flags remain in force. **0/43 findings certified closed**.
