# PR 601 — Conversational runtime reconciliation and autonomous-agent acceptance

Status: DRAFT. Engineering work authorized; no production deployment or paid-provider calls authorized.

## Objective
Reconcile Gravitre's existing light/medium/deep, One Brain, voice, connector, and governed-action architecture with observed production behavior. Fix proven integration defects, not redesign existing architecture.

## Existing work to preserve and trace
- PR #231: conversational text/voice acceptance gate.
- PR #227: natural response composition and lifecycle wording.
- PR #580: intelligence evidence and live-gate honesty; documented OpenAI 401.
- PR #587: shared intelligence, DSPy, Pipecat/LiveKit and voice reliability.
- PR #600: provider authentication backoff, contextual email discovery, clarification repair and PCM diagnostics.
- Issue #594: separate acoustic cancellation certification.

## Execution stages
1. Build a commit- and runtime-config-bound capability matrix: implemented, deployed, invoked, bypassed, failed, or unverified. Include light/medium/deep, primary and classical fallback, context compiler, response composer, tool inventory, authorization, voice and TTS.
2. Trace the November 2 Outlook failure by correlated conversation/turn IDs: ASR input, active task and heard history, tier choice, intent gateway, model/provider route, connector status and scope, fallback, final reply and played audio. Preserve tenant isolation; redact secrets and message content from retained evidence.
3. Reconcile recurring provider 401 with #580 and #600: effective selected model/provider, credential health and deployment SHA. Do not assume model routing is broken when credentials are invalid.
4. Inspect whether existing acceptance workflows ran on the exact deployed SHA and whether skipped/blocked checks were incorrectly represented as passes. Preserve all existing safety/write fences.
5. Repair only verified root causes in small commits with regression tests for both primary and fallback paths. Do not replace tiered architecture or add vendor-specific special cases where canonical discovery works.
6. Run synthetic end-to-end journeys: Outlook alternative after Gmail unavailable; multi-turn task with interruptions; autonomous authorized research/preparation; approval-gated writes; provider outage recovery; 20-minute voice continuity; genuine stop versus stop-speaking. Include clean/impaired network and physical iOS/browser listening.
7. Compare contemporary ChatGPT on comparable tasks with independent raters, task success, meaningful latency, audio continuity and truthful capability claims. Report non-comparable gaps and costs.

## Required deliverables
- Existing-capability-to-runtime matrix with source references and deployment provenance.
- Turn-level causal timeline separating observed facts from hypotheses.
- Root-cause fixes with exact-head CI and existing combined acceptance suite.
- User-journey pass/fail report, audio measurements and independent safety audit.
- Explicit NOT_RUN/NOT_CERTIFIED labels for unavailable live or paid tests, plus rollback plan.

## Release policy
Remain draft until exact-head tests and permitted live acceptance certify the complete product experience. No new connector grants, autonomous writes outside existing approvals, training on production transcripts, paid inference, production rollout or ChatGPT-parity marketing claim.
