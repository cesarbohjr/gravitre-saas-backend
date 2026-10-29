# Governed memory engineering

The actual pinned Mem0 OSS SDK is now implemented in `sdk_worker.py`, with a
bounded host client, executable canonical-kernel integration and a required CI
gate. This supersedes the earlier installation restriction for this engineering
increment following the user's instruction to proceed with full implementation.
No application dependency, production memory store, model provider, telemetry,
Marketplace package, policy, merge or deployment is changed by SDK evaluation.

The worker runs real Mem0 Memory, local Qdrant and SQLite lifecycle code. It uses
an explicit fixed CPU token-hash embedder and a forbidden-inference provider via
Mem0's factory extension points. **SDK add/search/update/delete/persistence are
real; neural embedding quality, model extraction and provider SLA are not tested.**
No provider credentials enter the child process. Network guards are installed
before SDK import; telemetry is off; `add(infer=False)` is mandatory. A failed
protocol, source mismatch, timeout, inference attempt or network attempt fails
the engineering gate. Source hashes and the SDK version are verified at startup.

`run_engine.py` executes all 26 canonical cases with the SDK, including canonical
learning, plus local lifecycle checks for namespace filters, cross-scope mutation
denial, update/readback, deletion/readback, restart and authorized local snapshot
restoration. The host's canonical memory gates remain authoritative. Fixture
storage is still used for Gravitre's database; no deployed acceptance is claimed.
The worker dependency lock is separate from all application requirements and is
audited in CI, preserving the existing OpenAI/provider dependency graph.

## Executing the actual SDK path

Use Python 3.12. In a disposable SDK environment install
`engine-requirements.lock`, then install the repository/revision in
`engine_source.json` with `pip install --no-deps /path/to/pinned/mem0-source`.
The host interpreter uses existing backend dev requirements. From clean committed
source, with synthetic backend environment values:

```
python scripts/memory_benchmark/run_engine.py --engine-python /absolute/disposable/venv/bin/python --output /absolute/scratch/mem0-sdk-report.json
```

The runner deletes all temporary SDK stores, snapshots and logs at exit. Only a
sanitized source/data-bound report is retained; CI uploads that report as an
artifact. No raw memory, identity or vendor exception body appears in it.

## Decision gates

`audit_erasure.py` independently verifies the pinned `Memory` deletion call
chain and executes upstream `SQLiteManager` with disposable synthetic records.
It needs only Python's standard library and the exact source tree:

```
python scripts/memory_benchmark/audit_erasure.py --package-root /path/to/pinned/mem0-source --output /absolute/scratch/mem0-erasure-audit.json
```

CI runs it alongside the existing full SDK lifecycle runner. Exit zero certifies
that the investigation reproduced its assertions; the report still records
`complete_erasure_gate=FAIL`. This storage probe does not run Qdrant, embeddings,
inference, a native-quality comparison, or production erasure. It confirms that
restart retains history, global reset also removes another scope's history, and
a pre-reset SQLite backup still contains the original history.

A successful SDK engineering run is **not approval to adopt Mem0**. The observed
SDK deletion removes vectors but retains text in SQLite history; this is recorded
as `complete_erasure_gate=FAIL`, separately from engineering correctness. Snapshot
restoration also intentionally restores that disposable history. It is not a
production erasure or rollback contract. Gravitre-native memory remains selected;
no semantic-quality improvement has been measured with the controlled embedder.

Letta Code remains an architectural reference, with its actual runtime NOT_RUN.
The current agent harness is not a drop-in retrieval implementation and its
self-editing/cross-agent behavior conflicts with the existing One Brain boundary.
No legacy Letta endpoint is fabricated and no duplicate agent runtime is adopted.

## Prior canonical and fixture replay evidence

The following v1/v2 descriptions are historical boundaries for their own runners.
Their NOT_RUN candidate labels remain correct: those runners do not execute SDKs.
The new SDK runner above has its own execution status and evidence.

This increment exercises **Gravitre's current governance implementation** and
defines candidate comparison boundaries. Mem0 and Letta SDK/runtime retrieval
scores are **NOT_RUN**. Contract fixtures and upstream source review are not a
vendor comparison, a selected winner or production certification.

`cases.json` contains 26 synthetic reference cases. They run the real canonical
kernel RECALL/LEARN, membership/consent checks, final authoritative rehydration,
source liveness, contamination labeling and promotion paths. Only external
retrieval, storage, embeddings and trace persistence are fixtures. The database
double applies identity and candidate-ID filters. Cases cover default-off and
independent recall/learning consent, subject/agent/tenant scope, revocation while
retrieving, correction, deleted/stale hits, retention, validity windows, source
disconnects, inference labels, known injection quarantine and authorized snapshot
restoration. The latter checks authoritative recall, not a new rollback API.

The benchmark found that extraction's blocked-injection marker could still reach
embedding and standing-memory storage. Canonical promotion and agent creation
now reject known quarantined external candidates before those effects. Governed
recall also excludes known legacy external injections using the existing
heuristic. Explicit trusted user statements and normal external facts keep their
current treatment. This is a bounded safeguard, not a claim to detect every
prompt injection. Malformed final recall hits are ignored rather than crashing.
No schema, migration, new memory store, consent default or permission is added.

`contracts.py` is research-only request/normalization code with no SDK import or
transport. The audited current Mem0 search API takes identity inside `filters`;
tenant-bound HMAC namespace references and host-owned ID bindings precede the
canonical final gates. Provider text and metadata cannot become authoritative
memory. The current Letta repository redirects to Letta Code; the retired V1 API
is not assumed. Its proposed comparison boundary is read-only scoped snapshots,
with no self-editing, cross-agent lookup or prompt/skill mutation. It is explicitly
**not** an implemented vendor API adapter.

Immutable revisions, source/license hashes and concrete API/runtime findings are
in `upstream_audit.json`. No upstream code is vendored, imported or installed.
Future isolated SDK execution still needs the existing installation/data-handling
boundary resolved; no external memory transfer, model call, new service or package
adoption is implied here. Mem0's model/vector/history/telemetry initialization and
default `infer=True` cannot be activated casually. Letta is an architecture
reference at this checkpoint, not a replacement for One Brain.

## Running the reference

From a clean committed repository, using the existing backend dev dependencies:

```
python scripts/memory_benchmark/run.py --output /absolute/scratch/reference.json
```

The runner installs the existing offline guard before importing the kernel and
rejects any attempted external access. Reports contain source/dataset hashes,
version, case outcomes and fixture-path latency, with unknown cost and explicit
NOT_RUN vendor results. They omit memory text, raw identity and exception bodies.
`REFERENCE_GOVERNANCE_PASS` is not retrieval quality, actual vendor latency,
embedding privacy certification, durable production deletion or physical voice
evidence. No automatic ranking, adoption, rollout or fallback decision is made.

Offline contracts (from `backend`):

```
python -m pytest -p tests.offline_network -q tests/services/test_governed_memory_benchmark.py tests/services/test_memory_quarantine_boundaries.py
```

## Candidate result replay (v2)

The next increment adds **31 Mem0-shaped fixture replays** through the real
canonical kernel: the 20 existing recall cases plus 11 response-boundary cases.
The latter cover missing/malformed/oversized results, unknown and spoofed IDs,
duplicates, empty results, claimed foreign-row authority, injected vendor text,
and a simulated timeout. Learning is deliberately excluded: a search replay
cannot certify a candidate's write, deletion or retention implementation.

The fixture builds the pinned request shape only after the real consent gate
allows recall. Host-owned bindings reduce fixture results to canonical IDs;
final authoritative rehydration decides scope, current content, liveness and
quarantine. Returned memory text and authority metadata never enter the prompt.
Malformed responses/timeouts produce the kernel's existing degraded hybrid
signal, rather than a successful empty-memory claim. This is an injection of
fixture responses at the hybrid retrieval seam, not application wiring or an
implemented network/SDK adapter.

Reports keep the original 26 reference outcomes separate from
`contract_replay.status=FIXTURE_CONTRACT_PASS`. Both arms must pass for the CLI
to succeed. Replay evidence includes source/data hashes and safe counts only;
no vendor quality score, latency comparison, cost estimate or winner is emitted.
Both actual engine statuses remain **NOT_RUN**. No Mem0/Letta install or runtime
is implied. The actual isolated engine comparison remains an outstanding step;
this replay closes the contract-to-canonical-gate gap, not the whole benchmark.

## Shared-visibility positive control

The executable SDK corpus also includes an organization-shared memory authored
by another user. The native kernel permits that fact for the authorized reader;
the SDK materialized view now preserves that visibility rather than incorrectly
using the creator as its private namespace. Private memories remain narrowed to
their owning subject. This adds one SDK-specific case to the unchanged 26-case
canonical reference, for 27 SDK governance cases, plus 16 lifecycle checks.
