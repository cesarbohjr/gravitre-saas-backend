# Phase 9 — Cascaded voice architecture: deliberate, not a compromise

Date: 2026-09-05

## Decision

Gravitre's live voice path stays **cascaded**: Deepgram (STT) → CognitiveTurnKernel
→ LLM (via `model_router`) → ElevenLabs (TTS), rather than a native
speech-to-speech model (e.g. a single end-to-end audio-in/audio-out model).

This is restated here, explicitly, so it is not silently reconsidered later by
a future latency pass without this context.

## Why (real, current requirements, not hypothetical)

A native speech-to-speech model collapses STT/reasoning/TTS into one opaque
model call. That is incompatible with requirements this program has already
built and depends on, all of which require sitting *in the middle* of the
pipeline with a real, inspectable text representation of the turn:

1. **Governance / GOVERN stage** (`app/services/cognitive_turn_kernel.py`,
   stage 6 `GOVERN`) — every turn passes an explicit ACL/approval check before
   ACT. A speech-to-speech model has no seam at which to insert this.
2. **RAG / Knowledge Fabric** (`cognitive_knowledge_layer.merge`) — retrieval
   results are injected as text into the prompt. There is no equivalent
   injection point in an end-to-end audio model.
3. **Tool / connector permissions** — the ReAct loop and `run_connector_turn`
   both operate on real, typed tool-call JSON with per-org permission checks.
   Native speech-to-speech models that support tool-calling still require a
   text/JSON intermediate representation for this — i.e. they are not actually
   more "native" for this requirement, just differently packaged.
4. **Auditability** (`write_audit_event`, `audit_events` table, this program's
   own evidence-linked-PASS standard) — every stage of RETRIEVE→RECALL→
   KNOWLEDGE→PLAN→VERIFY→GOVERN is logged as a discrete, inspectable
   `StageRecord`. An opaque audio-to-audio model cannot produce this audit
   trail at all.
5. **Cross-provider flexibility** (`model_router.py`, provider failover across
   OpenAI/Anthropic/Gemini) — the reasoning stage is provider-agnostic by
   design. Coupling voice to one vendor's proprietary speech-to-speech model
   would remove that flexibility for the voice surface specifically, while
   text keeps it — an inconsistency with no real benefit given (1)-(4) already
   force a text seam regardless.

## What this costs, honestly

The cascaded design is the reason STT-finalization + pre-kernel governance
overhead sits on the critical path at all (see
`docs/delivery/voice-latency-8to13s-gap-rootcause-2026-09-04.md` and this
pass's Phase 0 finding). A speech-to-speech model would remove that overhead
by removing the seam — but removing the seam also removes items (1)-(5). This
is the correct trade for Gravitre's actual requirements, not an oversight.

## Scope

This is a documentation-only phase. No code changed as part of Phase 9.
