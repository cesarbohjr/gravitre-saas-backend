# PR587: conversational optimization and shared feedback engineering

## Authorization and result

The user authorized full DSPy guidance optimization, fixed-baseline evaluation
and rollback, text/voice behavior certification and feedback integration.
Implementation is complete in source; release/production acceptance follows
engineering, green CI, merge and deployment. Both PRs remain open/draft and no
merge/deployment is performed here. Earlier roadmap planning/package-install
restrictions are superseded for this engineering scope.

DSPy is actual isolated tooling: pinned SDK, hash-locked dependencies, real
LabeledFewShot compilation and credential-free/network-denied CI. Candidate
selection, provider evaluation, complete evidence gates, named review,
source-controlled promotion and compare-and-swap rollback are implemented.
The original synthetic baselines are untouched. No model weight changes or
second brain is introduced. The native baseline remains active until a measured
candidate passes review. Full reproduction, split rules and dependency findings:
`scripts/guidance_optimization/README.md`.

## Voice and feedback

Existing text/voice paths still share the canonical kernel, permissions,
confirmation, speculative adoption, cancellation and provider-commit gates.
The regression certificate exercises those real code paths, including refusal of
uncommitted writes after interruption/revocation, shared intelligence, session
continuity and feedback. Source-level parity does not certify recorded speech,
STT quality, end-of-turn latency or physical interruption. The existing recorded
WAV acceptance analyzer and live voice batteries remain the release-stage proof;
no provider or physical session is simulated into a live PASS.

`run_learn` now integrates structural evaluation feedback after speculative
adoption. Consent comes from authenticated tenant settings, default off; payload
values never enable it. Explicit opt-out erases evaluation rows. Retention is
1–90 days, default 30, with tenant/event-filtered purging. No schema migration is
needed: the existing outcome ledger holds `dialogue_evaluated` observations.
A deterministic tenant/user/turn/evaluator ID makes retries idempotent. Receipt
readback compares scope/event/metrics before reporting `recorded`; missing or
mismatched receipts remain unverified. Feedback failure cannot change ACT.

Metrics are channel, evaluator/schema, bounded stage/error counts and duration.
No prompt, response, transcript, source, credentials or provider error body is
persisted. A bounded tenant-only summary exposes structural regressions for
review, not a quality score or automatic training/promotion. These observations
do not become business success or bias PLAN. PR581 provides the explicit opt-in
metrics-only Langfuse receipt adapter; submitted is not durable remote delivery.
No outbound telemetry is activated or SDK installed in the application.

## Evidence boundaries

- Real SDK compilation: executed locally and required in CI, with zero external
  calls and storage guards exercised. It is compilation, not measured quality.
- Shared kernel/text/voice/cancellation regression: executed under the offline
  network guard. Focused feedback tests exercise canonical LEARN and actual
  tenant filters, receipt readback, idempotency and speculative deferral.
- Provider-generated optimization quality: **NOT_RUN — no provider credential or
  selected generation/judge model in this engineering environment**. No candidate
  is promoted. The fully implemented CLI fails closed without those inputs.
- Physical voice, deployed tenant acceptance and remote telemetry delivery:
  **NOT_RUN — release follows merge/deployment; both PRs remain unmerged**.
- DSPy dependency audit has explicitly contained offline cache/locking findings,
  documented in the runner README; it is not a clean SCA result. No application
  dependency audit is changed.

Current exact-head CI and combined PR581 compatibility are recorded on the PR.
