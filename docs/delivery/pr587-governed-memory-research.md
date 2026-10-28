# PR587 memory engine engineering

## Current scope and implementation

The user's follow-up instructs full engineering implementation and CI rather than
stopping at fixture contracts. It supersedes the planning-only package-install
restriction for this isolated memory increment. Production acceptance follows
release; existing open/draft/no-merge/no-deploy instructions remain in force.

The pinned Mem0 2.2.1 SDK now runs in a disposable process with real local Qdrant
and SQLite, source-hash verification, opaque scope/bindings, bounded protocol and
deadlines, readback, restart and local snapshot restoration. The child receives
no service/provider credentials, disables telemetry before import, blocks network
IO and inference, and always adds with infer=False. An explicit controlled CPU
embedding provider keeps this an SDK/lifecycle comparison, not a neural-quality
or model benchmark. Application requirements and provider clients are untouched.

All 26 canonical governance cases use the actual SDK retrieval/indexing path;
canonical LEARN indexes only rows the existing writer actually accepted. The
host database remains a filter-honoring fixture. Host scope, consent, final
rehydration, liveness and contamination decisions remain real. Default-off gates
prevent SDK construction/calls. Separate cases exercise persistence, scoped
mutations and snapshot restoration. CI executes the actual SDK runner and uploads
a sanitized source/data-bound report; the isolated dependency lock is audited.

## Measured adoption decision

The actual SDK removes a deleted vector from recall but retains memory text in
SQLite history (three history rows after add/update/delete in the lifecycle run).
Complete erasure therefore remains **FAIL**, not a generic deletion PASS. Local
snapshot restoration deliberately restores disposable state and cannot certify
production erasure. The engineering runner reports this failure separately from
successful execution of its scoped lifecycle contracts. No gate is weakened to
permit adoption. The decision is to retain Gravitre-native memory; no measurable
semantic-quality gain has been established with the controlled embedder.

Letta's pinned current source remains an architectural reference. Its current
agent harness/self-editing/cross-agent model is not a drop-in governed retrieval
adapter. The actual Letta runtime remains NOT_RUN, with no invented endpoint,
autonomous import or duplicate brain. This is an explicit compatibility decision,
not a fabricated engine comparison or product-quality ranking.

## Evidence and release limits

Exact-head SDK execution, dependency audit, combined compatibility and final CI
are recorded in the PR description after execution. Engineering evidence does not
certify deployed user behavior. Production/provider/physical-voice acceptance
remains NOT_RUN until the authorized release stage. No merge, deployment,
production migration, live installation, campaign or telemetry activation occurs.
Paid Media's separate later scope and the existing six enrichments are unchanged.

## Historical canonical and fixture-only checkpoints

The earlier reference-only increment was memory/evaluation infrastructure under the
existing phased roadmap. No framework is adopted. Paid Media's separate tranche
approval is retained for later scoped implementation; no catalog, campaign,
spending permission, price or agent installation changes here.

## Implemented and measured

`scripts/memory_benchmark` contains 26 synthetic cases around Gravitre's real
canonical RECALL/LEARN and policy code, plus research-only candidate request/ID
normalization contracts. The fixture database applies tenant and candidate-ID
filters. Reports bind clean source/file hashes, dataset hash, version, case
outcomes and fixture-path latency. They omit raw memory/identity/error bodies;
cost is unknown and production certification is false.

The reference covers independent default-off recall/learning consent, actor
membership, private-subject/agent/tenant isolation, revocation during retrieval,
authoritative corrections and deletions, expiry/retention, source revocation,
inference labels and known injection quarantine. Snapshot restoration checks
authoritative reads; it does not create a new memory rollback API. Only external
storage/retriever/embedding/trace dependencies are fixtures. Candidate retrieval
quality, vector ranking and actual vendor latency remain unmeasured.

## Canonical defects reproduced and fixed

Five new quarantine contracts failed before the fix. Extraction's blocked marker
was only a confidence signal and could still reach embedding and standing-memory
storage. The existing contamination guard now marks known external injections
consistently, including candidates that combine an external marker with a claimed
user-direct class. Workspace promotion and agent creation stop those candidates
before embedding or storage, even with otherwise valid source lineage. Governed
recall excludes known legacy external injections using the existing heuristic.
Explicit trusted user statements and normal external facts retain their treatment.
Malformed final recall hits are ignored instead of crashing. These are bounded
quarantine safeguards, not complete prompt-injection detection.

No database schema, RLS policy, migration, new store, consent default or tool grant
changes. Manual content editing remains a distinct authenticated user-directed
path; its existing provenance semantics are not redefined by this increment.

## Vendor audit and limits

Pinned revisions and source/license SHA-256 hashes are in `upstream_audit.json`:

- Mem0 `26cdefb46600c0fa5953c4b5ee5003c125539fc4`, Apache-2.0. Current OSS search
  uses entity identifiers within `filters`. Default Memory construction initializes
  model, vector and history components; `add` defaults to inference. A future
  adapter must enforce full Gravitre scope, disable unauthorized inference and
  own deletion/readback checks. The new pure request contract and host-owned ID
  mapping are not an executed SDK benchmark.
- Letta `8816d3a8516893bfdc0fa14bfb1235226012e295` redirects current source to
  Letta Code; its old V1 API server is retired.
- Letta Code `5dea67021b99810707ff753db35e4534f70ff1fd`, Apache-2.0, is an agent
  harness with MemFS and self-editing/cross-agent behavior. Its memory-tree limits
  are not Gravitre membership/consent enforcement. This checkpoint defines only
  a read-only scoped snapshot requirement; it invents no endpoint or SDK adapter.

No vendor code is vendored, imported, installed or called. Both vendor engine
results remain **NOT_RUN**, with no numerical ranking or adoption decision. The
canonical reference status is **REFERENCE_GOVERNANCE_PASS** only after all its
cases pass; it cannot certify Mem0, Letta, generated quality or production.

## Delivery evidence

Local regression and exact-head CI evidence are recorded in the PR description
after verification. The reference runner requires clean committed source and
uses the existing offline network guard before loading the kernel. Full CI and
combined PR581 compatibility remain required. No provider call, external memory
transfer, live installation, rollout, merge or deployment is performed. Existing
live provider/voice/production gates remain NOT_RUN under that boundary.

## Candidate replay continuation

The follow-up exercises the existing Mem0 request/ID contracts through the real
kernel, using fixture results at the hybrid retrieval seam. It reuses the 20
recall reference cases and adds 11 malformed/adversarial/timeout result cases.
Canonical learning remains in the separate 26-case reference. Search replay
cannot certify any vendor's learning, durable deletion, retention or rollback.

Default-off consent prevents candidate requests; revocation and final scope
checks remain real. Returned text and claimed authority cannot replace canonical
rows. Unknown/spoofed IDs are dropped, duplicates deduplicated, and malformed or
timed-out responses retain the existing degraded-recall signal. Report tests
force a failure in each arm and prove neither can produce a successful aggregate
or leak exception bodies. Source/data hashes and separate reference/replay states
remain explicit; vendor engines stay NOT_RUN. No production application, database,
policy, Marketplace package, SDK dependency or telemetry change is included.

Exact-head CI and combined regression evidence for this continuation are recorded
in the PR description after execution. The existing no-merge/no-deploy and
no-vendor-install boundary remains in force; the full engine comparison is still
outstanding.
