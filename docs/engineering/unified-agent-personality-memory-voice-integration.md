# Gravitre unified agent experience — integration contract (PR #587)

Status: **implementation planned, not integrated or certified**. This document captures the approved scope: preserve Agency Agents and layer personality, durable memory, and real-time dialogue on Gravitre's existing One Brain. No production rollout or new hosted service is authorized by this document.

## Upstream candidates (verify source, license, security and pinned revision before code import)

- Agency Agents: https://github.com/msitarzewski/agency-agents — role/persona knowledge and specialist workflow definitions. Adapt declarative profiles; never import executable instructions as privileged policy.
- Persona Engine: https://github.com/caty-ai/persona-engine — personality, expression, style modulation. **Unverified adoption candidate**; validate repository provenance, maintenance and license before selecting.
- Letta: https://github.com/letta-ai/letta — memory architecture reference; use Gravitre's existing tenant-scoped storage and consent lifecycle unless a separate persistence deployment is explicitly approved.
- Pipecat: https://github.com/pipecat-ai/pipecat — real-time dialogue/voice pipeline reference; compare against existing voice runtime before introducing a second orchestrator.

## Single-brain invariants

1. Preserve canonical seven-capability intelligence coordinator (contextual, sentiment, causal, temporal, relational, adaptive, predictive) and shared text/voice behavior; no parallel agent brain.
2. Preserve existing agent identity, tenant/org scope, IAM, consent, connector permissions, approvals, audit, idempotency, verified-write and source-of-record controls. Personality/memory are advisory and never grant actions.
3. Specialist role definitions (Engineering, QA, Security, Agency) are distinct from stylistic persona configuration; role capability tags are not permissions. Reconcile PR #581's manifest with #587 without duplicate registries.
4. Personality output is a bounded, untrusted style profile (tone, expressiveness, brevity, empathy), subordinate to factual accuracy, safety and task completion. Do not infer sensitive traits or claim emotions as facts.
5. Memory retrieval/write requires tenant+agent+subject scope, explicit applicable consent, retention/deletion controls, provenance, and no cross-tenant leakage. Missing memory must degrade gracefully.
6. Voice interaction must preserve interruption/turn-taking behavior, latency budgets, and the same policy gates as text. Avoid replacing Deepgram/ElevenLabs or existing voice transports without compatibility evidence.
7. External prompts, knowledge and repositories are untrusted; pin immutable revisions, verify SPDX/license and redistribution terms, scan dependencies and check prompt-injection and supply-chain exposure before vendoring or installing.

## Delivery stages and acceptance

**Stage A — upstream audit and compatibility:** record verified repo URL, commit pin, license, security/maintenance, dependencies, Python/TypeScript runtime fit, licensing obligations, voice transport overlap and rollback plan. Reject or replace any unsuitable candidate.

**Stage B — role/profile adapter:** reuse canonical role manifest, import approved Agency Agents role knowledge as sanitized bounded data, maintain role selection and explicit provenance; test unknown role, permission escalation, tenant mismatch and injection denial.

**Stage C — personality adapter:** one canonical style envelope used by both text and voice, with deterministic defaults and safe fallback. Test all four roles x seven capabilities; ensure role expertise is not overwritten by style and safety policy cannot be weakened.

**Stage D — memory adapter:** consent-gated scoped read/write and retrieval, explicit retention/deletion, no external persistence without approval. Test unauthorized/cross-tenant read and write, revoked consent, stale/conflicting memory and no-memory behavior.

**Stage E — voice adapter:** compare Pipecat against current voice orchestration; adopt only needed compatible components. Test interruptions, barge-in, turn completion, handoff, streaming, timeouts and text/voice policy parity.

**Stage F — combined validation:** targeted unit and integration tests, four-role/seven-capability/surface matrix, negative security cases, full CI and regression checks. Keep live provider, physical voice, source-of-record outcomes and production certification separate and blocking. Do not treat offline contracts as live certification. Perform live acceptance last, after authorized deployment.

## Merge policy

Implement on PR #587 branch in small reviewable commits; do not merge #581 or close it until its requirements are mapped to verified code and tests. No unreviewed dependency install, expensive synthetic evaluation, new Railway service, migration, or production deployment. Record actual evidence and blockers rather than asserting completion.
