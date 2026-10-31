# Phase 3: shared One Brain integration

Implementation is on `feat/phase2-dialogue-intelligence` / PR #587. This report
covers source integration and executed offline contracts, not production or full
business-journey certification. The roadmap acceptance requirements remain intact.

## Runtime path

Text and voice retain the existing AgentIntelligence / CognitiveTurnKernel path.
The canonical capability names remain contextual, sentiment, causal, temporal,
relational, adaptive and predictive. No new reasoning engine, model family,
training path, execution authority, database table or migration is introduced.

The existing execution-intelligence collector now returns a tenant-bound packet
as well as its compatibility prompt wrapper. Non-chat intake supplies this packet
to the same kernel. Missing organization and explicit foreign-agent bindings are
rejected; a packet for a different organization is rejected by the kernel. Missing
or failed optional enrichment remains seven explicit unavailable slots. Disabled
kernel intake does not activate the new collection. Packets are copied per turn;
only allowlisted status enums enter trace summaries and job audit metadata.

The shared compiler, unified fallback, classical agent prompt and council evidence
handoff consume the fenced advisory packet. Council handoffs also retain dialogue
interpretation and scoped session continuity. Synchronous adapters inherit context
variables, preserving cancellation/speculation context across their worker thread.
Background agents reuse the same collector and attach status/turn identity to the
existing audit/LEARN path. Evidence never supplies permissions or executable plans.

## Execution and feedback integrity

The duplicate read-plan reconciler now delegates to the canonical reconciler.
Successful reads cannot complete pending writes or revive cancelled plans. Read
exceptions produce failed, correctly attributed observations without logging
provider exception bodies. Mismatched step/connector/plan observations are refused;
the canonical reconciler excludes foreign-plan and unknown-step observations.

Existing final tool-write gates, approval binding, actor/agent permissions,
organization/MSP policy, idempotency, workflow checkpoints, compensation and
source-of-record verification remain the execution authority. Strategic kernel
plans stay non-executable. No operating mode or organization consent was enabled.

Existing Play measurement events feed the same outcome ledger and next-decision
bias. Natural-language requests can now match an exact stored entity identifier;
unrelated entities are excluded before computing the advisory weight. Workflow/tool
acceptance remains execution evidence, not business improvement. This change does
not train a model, promote an artifact or bypass existing consent/promotion rules.

Customer Rescue (`customer-rescue`) and Process Drift
(`process-drift-detector`) are exercised through the real Play catalog and run
handler with fixture DB/workflow boundaries: approval staging, refusal before any
start when a bound workflow lacks approval, and partial-start honesty. The operator
package now loads its HTTP router lazily, fixing standalone workflow-route imports
without relying on test collection order; explicit router imports remain supported.

## Executable gates

`test_phase3_one_brain_contract.py` crosses all seven capabilities, all eight
inventory surface labels, every current `AGENT_PERSONAS` entry (ten), and text/voice:
1,120 shared-adapter cases. Real router assembly, kernel intake, context compiler,
handoff fencing and governance are exercised with fixture data services. Changed
capability evidence must change downstream context without granting write approval.
These cases prove the common handoff contract, not each complete surface endpoint.

The coverage CLI consumes executed JUnit properties. A cell only gets
`PASS_OFFLINE_CONTRACT` when every role/channel variant ran and passed. Missing,
skipped, duplicated or failed evidence cannot pass the gate. All 56 cells were
observed as offline contract passes; live-verified count remains zero and
`full_product_journeys_verified` stays false. Bare inventory is still NOT_TESTED.

The Phase 3 coverage workflow now runs these contracts plus existing approval,
MSP, tenant isolation, idempotency, cancellation, Play handoff, compensation and
feedback guards, and uploads JUnit plus the scoped coverage report. The twelve-case
offline scenario workflow also triggers on the relevant runtime changes. Its
synthetic/fixture results remain distinct from provider or physical voice evidence.

## Local evidence

- Broader governed-execution run: 1,224 tests passed; no failures or skips.
- All twelve existing offline scenario groups passed (170 test executions across
  overlapping groups; not a claim of 170 distinct scenarios).
- Coverage parser observed 56/56 complete role/channel adapter-contract cells.
- Additional latest-source and explicit required-Play checks are recorded on PR #587.

The manual post-deployment generated-response quality workflow remains manual.
Actual production deployment, authenticated live business journeys, provider
readbacks, generated-response quality, physical voice latency/continuity and
measured model improvement are not certified by this report. Full CI must be
observed separately; submitting a branch or running tests locally is not CI PASS.

Final latest-source combined regression: **1,384 passed**, no failures/errors/skips
(one existing Starlette deprecation warning). This includes the matrix, required
Play routes, kernel/compiler/router, execution lifecycle, operator prompts and
actual FastAPI Plays/rollback routes. Five manual-workflow contracts also passed.
The twenty hold-refusal unit trials use deterministic expiration to avoid twenty
production-length 30-second waits; they still invoke the real classifier, pause
state and final provider gate and require zero provider calls. Existing timing and
resume tests are retained. These are not microphone or wall-clock latency claims.

The manual quality workflow now checks the live backend health `git_sha`, in
addition to comparing the supplied revision with checkout, before evaluation.
No live quality run or application deployment was performed by this increment.
