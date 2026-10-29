# PR581 continuation validation

## Implemented checkpoints

- `6db3883c`: shared connector recommendation experience across Marketplace, installed agents, connector settings and shared text/voice prompts.
- `5350b9c1`: seven Project Management agents under Operations, with seven canonical advisory review workflows.
- `707591c2`: 70 software source roles reconciled into 23 destinations (22 new agents plus existing IT triage enrichment), with 23 canonical advisory review workflows. Six hardware/OrgScript exclusions retained.
- Catalog total: 55 AI agent definitions and 50 workflows. No seed execution, live installation, new tool grants, merge or deployment.

## Local evidence

- Focused Marketplace/catalog/recommendation/shared-prompt suite on the software checkpoint: **918 passed** with `tests.offline_network_guard`.
- Full web Vitest suite: **1,960 passed**, 312 files. Final copy-focused rerun: **15 passed** (overlap).
- The default local Turbopack build could not resolve Next.js through the reused external dependency directory. A local Webpack production build with CI-equivalent public placeholder settings completed successfully; this does not replace the standard CI install/Turbopack build gate.
- TypeScript: passed. Touched-file ESLint: zero errors; six existing warnings in connector settings.
- Full backend offline attempt: **12,674 passed, 281 skipped, 1 failed, 9 errors**. The failure was the new connector prompt breaking the existing bare-agent empty-section contract; fixed by omitting connector instructions for an unconfigured identity-only record. The nine Redis integration setup errors require a reachable local Redis service and are incompatible with the all-network guard. This run is **not full-suite PASS**.
- After that correction, affected profile/runtime-wiring/shared-prompt/native-adapter tests: **132 passed** under the network guard. No assertion was weakened for the bare-agent fix.
- An earlier unrestricted full-suite attempt was rejected by automatic review when it attempted an outbound OpenAI request. It was replaced by guarded offline verification; no provider-quality or live acceptance is claimed.

## PR587 compatibility

A detached local merge of PR581 `707591c2` and PR587 `e170472ac60091b9511dddb1dca2a5715f1a767b` was conflict-free, tree `10cfab71b681e497c4f3aaae5f25c6c435fc2a2b`. No remote merge occurred.

The combined Marketplace/capabilities/services run produced **10,217 passed, 2 skipped, 3 failed** under the network guard. One failure was the same bare-agent regression fixed above. The other two are reproducible on PR587 alone, without PR581:

- `test_voice_early_plan_ack.py::test_interrupt_during_ack_stops_it_and_the_engine_never_starts`
- `test_voice_session_service.py::test_stream_voice_turn_emits_audio_chunks_as_they_arrive`

PR587's `voice_session_service.py` joins all TTS chunks before yielding audio. The tests require per-chunk streaming and cancellation after the first acknowledgement chunk. Keep those assertions intact; resolve the implementation/transport behavior on PR587 before combined compatibility can be certified. PR587 source was not modified in this continuation.

The bare-agent correction was also copied into the detached combined tree: its focused runtime/profile/shared-prompt rerun passed **97 tests**. It does not resolve the two voice failures. **Combined compatibility remains FAIL / release blocked.** Earlier 4,164-test compatibility results are historical and do not certify these final changes.

## Remaining gates

Native worker/session and durable Langfuse delivery implementation remains open; see `PR581_NATIVE_ACTIVATION_READINESS.md`. Exact-final-head full CI has not yet been verified. Refreshing the draft PR's closed/open state was used to request fresh checks without merging or deploying; no success is inferred from that request. Keep PR581 open/draft and unmerged. Complete its engineering before proceeding to PR587 and the coordinated release.
