# Governed memory research checkpoint

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
