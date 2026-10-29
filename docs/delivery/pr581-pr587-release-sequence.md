# Coordinated PR581 / PR587 execution record

The user's current release instruction authorizes the six-stage sequence below. Earlier draft/no-deploy language in historical records describes earlier checkpoints; it does not override this later instruction. Authorization does not bypass repository protections or acceptance gates.

| Stage | Required evidence | Current disposition |
| --- | --- | --- |
| 1. PR581 final CI | Every applicable workflow green on the final branch head | Pending final-head certification; the earlier a81ec4e checkpoint is historical |
| 2. Native worker and durable Langfuse | Actual gVisor-isolated OpenHands/Chromium execution and cancellation; real Langfuse OTLP acknowledgement, restart/idempotency and deletion readback | New real-service CI gates present; not certified while actual runs fail |
| 3. Freeze PR581 | Reviewable final source and evidence; remain unmerged while PR587 finishes | Pending stages 1–2 |
| 4. Complete PR587 engineering | Canonical shared intelligence, governed guidance/memory, catalog/channel contracts and reproducible three-dimension product benchmark protocol | Source prepared; final CI pending; actual product quality remains unmeasured |
| 5. Final combined validation | Frozen combined source, full regression and exact-head CI, no unresolved compatibility failures | Focused combined regression passed; broad local run: 16,022 passed / 281 skipped / 9 Redis setup errors under the all-socket offline guard; real Redis must pass in CI |
| 6. Controlled release | Merge through protections, deploy one combined main build, verify both deployed SHAs and production acceptance | Not started; gated on stages 1–5 |

## Mandatory PR587 pre-merge framework selection gates (approved 2026-10-29)

These gates are required **before PR587 merges**, not optional post-release research. Keep PR587 draft until the comparative evidence, selected implementation, and exact-head CI are complete. The existing PR581 dependencies and authorization/security boundaries remain in force.

### Voice and evaluation selection
- Build isolated, functional Pipecat and LiveKit candidate adapters alongside the existing Gravitre/Deepgram/ElevenLabs path; do not introduce a second authoritative agent brain, memory store, permission layer, or action executor.
- Integrate DeepEval in the offline evaluation harness and compare its regression detection and judgment validity against the existing fixed-baseline evaluator and independently human-reviewed examples.
- Run equivalent real-audio pre-merge scenarios for all voice candidates: interruptions/barge-in, turn-taking, corrections, reconnects, text/voice transitions, authorization/revocation and cancelled-write prevention. Capture speech-end-to-first-audio latency, reliability, quality, resource cost, and failures using the same controlled conditions and no customer data.
- Define acceptance thresholds and representative workloads before measurements; retain native where no meaningful advantage is established. Record measured outcomes, evidence hashes, dependency/security/license review, and an explicit adopt/reject decision for each candidate. Implement the selected final architecture before combined regression and exact-head CI. An unavailable physical test environment is a BLOCKED gate, not a pass.

### Mem0 root cause and memory-quality selection
- Trace the tested Mem0 2.2.1 add/update/delete lifecycle through vector and SQLite history persistence. Determine whether retained history is documented behavior, a defect, or an omitted supported erasure API; document source paths, API semantics and a reproducible test. Do not infer the root cause solely from disappearing vector hits.
- Investigate supported complete-erasure remedies without weakening consent, deletion, retention, audit or tenant-isolation requirements. Verify vector removal **and** history-text erasure, restart persistence, scoped deletion, readback and snapshot/backup implications. The prior observed three retained history rows remain a failing baseline until proven otherwise.
- Benchmark Mem0 against Gravitre-native memory using matched consented/synthetic corpora for extraction precision/recall, semantic retrieval relevance, correction/consolidation, false-memory resistance, latency and cost. Include cross-tenant, revoked-source and prompt-injection negative cases.
- Record an explicit adopt/reject decision based on both a hard complete-erasure PASS and meaningful measured quality/efficiency improvement. If either fails or evidence is unavailable, retain Gravitre-native memory; do not install Mem0 in the application runtime or claim it is certified.

### Release enforcement
- Attach evidence and decisions to PR587, update its engineering checklist and CI where automatable, then certify the final combined PR581/PR587 tree. Do not merge PR587 while any required gate is unmeasured, failed or blocked. Production acceptance still follows the approved merge/deployment sequence.

## Production activation dependencies

Railway's existing backend container is not a native sandbox host. Native activation needs a dedicated Linux host with Docker and gVisor/Kata, persistent private storage and private authenticated TLS. The repository supplies a systemd service and read-only preflight under `deploy/native-worker/`. No such accessible host has been identified in the connected infrastructure. Do not run the sandbox broker as an ordinary Railway worker, expose Docker, weaken isolation or enable a native action before this dependency is met.

Langfuse production destination credentials and tenant consent must be configured through approved secret management. The backend currently has no native-runtime/Langfuse activation settings. Disposable CI server credentials and synthetic observations are never production configuration or provider-quality evidence.

## Acceptance after deployment

Verify Railway `/health` reports the merged main SHA and Vercel production serves that same coordinated source. Execute the existing Plays production acceptance and authenticated admin/non-admin UI checks required by `AGENTS.md`; label an inaccessible protected workflow or missing real session `NOT RUN` with the actual blocker.

The reference benchmark protocol is `docs/delivery/pr587-chatgpt-product-benchmark.md`. Actual ChatGPT text, voice and tool sessions, physical audio, contemporary product configuration and two independent blinded human raters are release-stage evidence. Until captured and reviewed, every quality claim remains **NOT CERTIFIED**. Deterministic fixtures, SDK imports and provider API responses cannot stand in for those observations. Native guidance stays selected; the Mem0 complete-erasure failure remains a rejection of adoption.

No production migration is included in the reviewed branch changes. Re-check the final diff before release; any newly introduced production migration must follow the repository's explicit approval policy.
