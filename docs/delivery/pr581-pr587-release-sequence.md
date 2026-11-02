# Coordinated PR581 / PR587 execution record

The user's current release instruction authorizes the six-stage sequence below. Earlier draft/no-deploy language in historical records describes earlier checkpoints; it does not override this later instruction. Authorization does not bypass repository protections or acceptance gates.

## Completion review after `146b3b0`

The mandatory pre-merge comparisons below remain the acceptance criteria. This
review does not waive missing provider, physical-device or independent-review evidence.

- Latest connected RTC run [41170086062](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41170086062)
  failed after recorded ingress while cancelling the receive drain. A deterministic
  test reproduced cancellation being swallowed during child-task cleanup. The
  candidate fix cancels both child waits and gathers them together, preserving
  parent cancellation. All 12 real-SDK unit contracts pass locally, including the
  new cleanup-race and queue-waiter/reuse cases.
  Fresh [connected CI 41170496665](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41170496665)
  passed on `77e5d55e3e11099f56fb6390541afcba56b4e35a`: recorded ingress/egress,
  waveform correlation 0.9772, pinned interrupt delivery 9.32 ms, fresh-peer
  rejoin 92.36 ms, foreign control rejection and old-session closure. These are
  loopback transport measurements, not provider quality or physical playout.
- Live-provider run [41170086100](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41170086100)
  failed at ElevenLabs synthesis with upstream HTTP 401 and fixed provider reason
  `quota_exceeded`. Restore dedicated acceptance-provider quota before live audio
  can pass. No alternate credentials, account or provider is substituted.
- The local loopback server could not start: network-route discovery is denied
  (`netlinkrib: operation not permitted`). Local unit results do not replace the
  connected CI run or physical microphone/speaker evidence.
- Paired audio is now dependent on the bounded provider preflight, preventing
  further repeated audio attempts when it fails. Standing Anthropic batteries
  can still execute after that skipped audio job; they wait for older acceptance
  runs before touching the shared smoke actor. Orchestration deadlines cover the
  existing six 900-second phases and predecessor wait; per-test deadlines,
  repetitions, failure retention and the audio cutoff threshold are unchanged.
- Next execution order remains: matched three-repetition audio and independent
  write audits; full standing intelligence batteries; fault/reconnect recovery;
  remaining comparative quality/cost/privacy and independent review; final combined
  PR581/PR587 source reconciliation and exact-head CI; protected coordinated release
  and deployed acceptance. Preserve every failed result rather than retrying it away.
- Runtime decisions remain unchanged: native governed memory selected, Mem0
  adoption rejected while scoped complete erasure fails, Browser Use production
  default, and LiveKit comparison-only. No merge, deployment, production migration,
  native activation or customer action is certified by this review.

| Stage | Required evidence | Current disposition |
| --- | --- | --- |
| 1. PR581 final CI | Every applicable workflow green on the final branch head | Pending final-head certification; the earlier a81ec4e checkpoint is historical |
| 2. Native worker and durable Langfuse | Actual gVisor-isolated OpenHands/Chromium execution and cancellation; real Langfuse OTLP acknowledgement, restart/idempotency and deletion readback | New real-service CI gates present; not certified while actual runs fail |
| 3. Freeze PR581 | Reviewable final source and evidence; remain unmerged while PR587 finishes | Pending stages 1–2 |
| 4. Complete PR587 engineering | Canonical shared intelligence, governed guidance/memory, catalog/channel contracts and reproducible three-dimension product benchmark protocol | Source prepared; final CI pending; actual product quality remains unmeasured |
| 5. Final combined validation | Frozen combined source, full regression and exact-head CI, no unresolved compatibility failures | Focused combined regression passed; broad local run: 16,022 passed / 281 skipped / 9 Redis setup errors under the all-socket offline guard; real Redis must pass in CI |
| 6. Controlled release | Merge through protections, deploy one combined main build, verify both deployed SHAs and production acceptance | Not started; gated on stages 1–5 |

## Current executed framework checkpoint (2026-10-29)

This checkpoint supersedes historical pending/failure descriptions above only
for the exact sources and measured scopes named here. Every subsequent source
change still requires its own full CI and real-service certification.

- PR581 `3b4bb68c89c47d840680612ae902463232ed81c8` completed full CI and
  native/Langfuse certification. That is historical evidence after later edits.
- The first paired adapter experiment on PR587 head
  `a1b0b76aed29854ca6d3e380d3f8dfa8c922d9a1` passed original runtime
  certification and **10/10** real gVisor trials. See
  `../engineering/PR581_BROWSER_ADAPTER_COMPARISON.md` and its saved report for
  merge SHA, image/artifact hashes, measured timings and limitations. Repeated
  SDK-configuration wrapping was a harness confound and is corrected in this
  increment; rerun before selection.
- A parallel PR581 run failed intermittently before any browser model request
  at the dialog handler's CDP `Page.enable`. The follow-up defers activation out
  of the bootstrap event and requires readiness before model execution, review
  and completion. The **48** affected local native tests pass. Exact-head real
  certification after this candidate correction remains required.
- DeepEval's actual SDK detected **12/12** synthetic exact-tool trace labels,
  matching a strict trace reference, with zero inference/network calls. Its
  complete isolated 66-package audit found no known vulnerabilities at this
  checkpoint. This is **not** the existing fixed conversational judge or an
  independently human-reviewed quality comparison; overall selection is open.
- Voice aggregate validation has **19** passing local contracts and now covers
  native duplex, Pipecat and LiveKit descriptively. Favorable raw aggregate rows
  cannot select an engine. Functional candidate adapters and equivalent real
  audio interruption/turn-taking/reconnect/authorization scenarios remain open;
  no measured framework voice result is claimed.
- Mem0's retained SQLite history remains a complete-erasure **FAIL**. A supported
  scoped remedy and matched native/Mem0 semantic extraction/retrieval/correction
  quality and efficiency comparison remain open. Native memory stays selected.

Final combined certification is **BLOCKED** by unfinished comparative and audio
evidence, plus fresh exact-head CI after these changes. No merge, deployment,
production migration, tenant action or native activation occurs at this checkpoint.
Physical voice and independent review require an actual controlled device/session
and reviewers; SDK/fixture success cannot substitute for them.

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

### Capability parity: benchmark first, then decide integrate or replicate
- The decision target is measurable capability parity or superiority, **not mandatory third-party adoption**. For each candidate (Pipecat, LiveKit Agents, DeepEval, Mem0), identify gaps against Gravitre-native behavior, and evaluate three paths: retain native unchanged, engineer the missing capability natively, or integrate a narrowly scoped library.
- **First benchmark** the existing Gravitre implementation against runnable candidate frameworks under equivalent representative workloads and predeclared acceptance thresholds. Capture measured quality, latency, reliability, privacy/security, tenant isolation, cancellation, maintenance burden, licensing and total engineering/operating cost. Do not choose an implementation path before reviewing the comparison. If a candidate cannot be run, record BLOCKED rather than treating literature or fixtures as measured superiority.
- **Only after baseline benchmark results**, decide for each demonstrated gap whether to retain native unchanged, replicate the superior capability natively, or integrate a narrowly scoped library. Document why the selected path wins on evidence and feasibility. Implement the chosen path fully and rerun the same representative fixed-baseline and real-audio tests against the final result. A replicated capability must pass the same acceptance thresholds as an integrated library. Preserve the canonical Gravitre intelligence, authorization, memory consent/deletion and action-execution boundaries.
- Document evidence, alternatives, and an explicit integrate/replicate/retain/reject decision per capability in PR587. Unmeasured or unavailable evidence blocks the gate. Complete all gates before merge; production acceptance remains after deployment.

### Release enforcement
- Attach evidence and decisions to PR587, update its engineering checklist and CI where automatable, then certify the final combined PR581/PR587 tree. Do not merge PR587 while any required gate is unmeasured, failed or blocked. Production acceptance still follows the approved merge/deployment sequence.

## Production activation dependencies

Railway's existing backend container is not a native sandbox host. Native activation needs a dedicated Linux host with Docker and gVisor/Kata, persistent private storage and private authenticated TLS. The repository supplies a systemd service and read-only preflight under `deploy/native-worker/`. No such accessible host has been identified in the connected infrastructure. Do not run the sandbox broker as an ordinary Railway worker, expose Docker, weaken isolation or enable a native action before this dependency is met.

Langfuse production destination credentials and tenant consent must be configured through approved secret management. The backend currently has no native-runtime/Langfuse activation settings. Disposable CI server credentials and synthetic observations are never production configuration or provider-quality evidence.

## Acceptance after deployment

Verify Railway `/health` reports the merged main SHA and Vercel production serves that same coordinated source. Execute the existing Plays production acceptance and authenticated admin/non-admin UI checks required by `AGENTS.md`; label an inaccessible protected workflow or missing real session `NOT RUN` with the actual blocker.

The reference benchmark protocol is `docs/delivery/pr587-chatgpt-product-benchmark.md`. Actual ChatGPT text, voice and tool sessions, physical audio, contemporary product configuration and two independent blinded human raters are release-stage evidence. Until captured and reviewed, every quality claim remains **NOT CERTIFIED**. Deterministic fixtures, SDK imports and provider API responses cannot stand in for those observations. Native guidance stays selected; the Mem0 complete-erasure failure remains a rejection of adoption.

No production migration is included in the reviewed branch changes. Re-check the final diff before release; any newly introduced production migration must follow the repository's explicit approval policy.
