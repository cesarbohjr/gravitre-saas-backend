# ECO-004 — Voice STT finality and turn-authority acceptance inventory

**Status:** SOURCE TRACED / NOT CERTIFIED. ECO-004 is independent in the master register (dependencies: []), P0 release-blocking, assigned to **PR #610 Voice V1/V2 owner**, with **PR #611 QA30 integration gate**. Nothing in this record transfers voice turn-authority ownership to the routing-latency workstream.

## Source-to-caller chain and ownership

1. Deepgram Flux native SDK owns STT EndOfTurn and committed TranscriptionFrame. `backend/app/services/pipecat_voice/flux_stt.py` bridges *control-only* interim updates, with per-WebSocket turn indices and reconnect reset; it does not commit text or approve actions. Inspect `InterimAwareFluxSTTService._handle_turn_info`.
2. `backend/app/services/pipecat_voice/pipeline.py` constructs the live path with STT -> `TranscriptRelayProcessor` -> user aggregator, speculative prefetch and cognitive LLM. Speculative coordinator is Flux-specific. This source wiring is not independent runtime proof that deployed Voice 3.0 flags/Deepgram probable-EOT adoption are active.
3. `backend/app/services/pipecat_voice/transcript_relay.py` mirrors each downstream final TranscriptionFrame into an urgent client message. It annotates classified bot echoes, backchannels, explanation-asides and thinking-holds, but **does not suppress repeat final frames** or own durable committed-turn idempotency. Do not add a relay-local text dedupe: identical text can be legitimate on distinct turns and the SDK/turn strategy owns commitment.
4. `backend/app/services/pipecat_voice/speculative_generation.py`, `speculative_prefetch.py`, `app/services/speculative_execution.py` contain cancelable speculative work and write fences; confirm adoption uses confirmed revision, principal/tenant, task and approval versions before any deferred outcome is persisted.
5. Client `use-voice-duplex-session.ts` consumes the emitted final transcript. The browser's rendering is not evidence that a server turn was uniquely committed.

## Existing executable evidence (not full ECO-004 certification)

- `backend/tests/services/pipecat_voice/test_transcript_relay.py`: final transcript emitted and serialized, original STT frame still passed, interim and upstream frames excluded, source pipeline ordering.
- `backend/tests/services/pipecat_voice/test_transcript_relay_backchannel.py`: echo, backchannel, answered question, thinking-hold and explanation-aside behavior.
- `backend/tests/services/pipecat_voice/test_flux_partial_bridge.py`: native EOT ownership, control-only partials, indexed early cancel, reconnect and stale-turn handling.
- `backend/tests/services/pipecat_voice/test_speculative_bounds_and_revisions.py`: bounded speculative work, revision mismatch cancellation, side-effect fences, no speculative approval/connector write.
- PR #610 is currently **draft and unmerged**. Its inspected head `0edac995ea12ae73827a07156461905b7f820157` had 11 successful and 1 failed workflows; its PR description claims a plan/specification, **not a certified voice repair**. Do not import uncertified claims from this head.

## Unmet release gates — owned by PR #610 before PR #611 import

- Capture *actual* Flux confirmed-turn and probable-EOT trace: each provider turn index -> native final STT frame -> relay/browser transcript -> single durable user turn, with explicit duplicate and replay counters, no stored transcript text.
- Add positive and negative exact-turn tests: provider duplicate EndOfTurn, repeated final TranscriptionFrame, distinct turns with identical text, stale out-of-order final after reconnect, cancelled or revised speculative transcript, bot echo and backchannel. Distinguish *client mirrors* from *authoritatively committed turns*; reject duplicates at the existing commit authority, never via text-only relay filters.
- Confirm bounded speculative generation read-only until adoption: zero connector writes, approval consumption, tool dispatch and conversation writes on discarded or stale provisional turns; independent database/provider outcome verification.
- Prove tenant/scope, approvals, cancellation, revocation, audio-barge-in and cross-session restart behavior across real client surfaces.
- Independent iOS device and live provider trace plus exact-head CI, rollback proof and owner approval. Hardware/device testing is not implied by unit tests.

## PR #611 integration gate

Once PR #610 owner provides a passing exact-head SHA and executable evidence, import those specific contracts as QA30 acceptance tests, preserving versioned provider configuration and source/caller identity. Do not merge, deploy or change voice behavior until parity and release safety are independently checked.

**Disposition:** No implementation repair, merge, production deployment, provider write, user-device acceptance, or finding closure is claimed. `ECO-004.fix_verified=false` and `release_blocking=true` remain.
