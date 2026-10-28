# PR587 governed-memory research checkpoint

The next authorized increment is memory/evaluation infrastructure under the
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
