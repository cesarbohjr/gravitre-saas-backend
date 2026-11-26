# DEC-011: memory mutation and instant-answer cache boundaries

Base: `b1ec821a8521f3eb70e65228db4cc2c3fce85d1b`. All ten exact-head workflows
succeeded on attempt 1, including Core `45153594148` and Operations `45153594441`.
All five Core contexts passed; backend `137620951208` reported 17,516 passed,
70 skipped and 14 passing subtests. Prior CI does not certify this next batch.

Both prior QA12 ZIPs were already independently downloaded/hashed/parsed and
were not downloaded again: DEC-008 artifact `14807598196`, 20 passed/zero skips,
SHA256 `4d3ced174eb63a559a4126e01ac2cc76d217df9223d6bba4d6fbe8da4e7f2624`;
DEC-011 artifact `14808097239`, six passed/zero skips, SHA256
`dce457140526e42c6c3717d2f22d2cacc80c006df8cfd097e8d44d420b10cb70`.
Both match the base SHA, PostgREST 16.6 / PostgreSQL 18.7, external-project false
and whole-finding certification false. The DEC-011 expected version is 18.7.

## Actual source paths and bounded observation

- Authenticated agent-memory create/update/delete routes call the existing
  `agent_memory_service` CRUD functions. The workflow runtime and remember helpers
  also call its create function. Organization, agent and editable guards remain.
- `workspace_memory_service.promote_turn_memories` calls `upsert_temporal_memory`.
  Temporal insertion and supersession can change recalled facts independently of
  documents. These writes previously did not bump a retrieval epoch.
- `deactivate_memory` is called by `forget_by_key` and `apply_forget_request`.
  A named-call source scan found no concrete application caller of those two
  forget utilities. They are exercised directly in tests, not declared active
  production natural-language routes or newly wired into chat.
- `AgentIntelligence.execute_task_streaming` concretely gets and fills the
  Tier-0 answer cache when its existing settings permit it. Memory context can
  enter generation through unified retrieval/kernel/context assembly. The fill
  supplies document IDs, not memory IDs; a no-document cached answer is not
  invalidated by the document fingerprint alone.
- `memory_source_liveness.invalidate_org_retrieval_cache` already owns the
  org-scoped retrieval epoch. `epoch_parts` participates in Tier-0, RAG retrieval
  and source-summary cache keys. Reuse of that owner avoids a second cache or a
  new memory store. This is source tracing, not proof of deployed flags/traffic.

## Reproduction and repair

On unmodified source, eight regression cases failed and six failed-before-write
controls passed. Actual mutation helpers with synthetic storage and the real
in-process CacheService left the old answer accessible after delete, deactivate,
edit, create, temporal supersede and temporal insert. Two further cases reproduced
epoch changes during cache reads/fills: the read returned the old answer, and the
fill wrote old context into the new epoch. No Redis/customer/provider was used.

Successful CRUD, deactivation and temporal writes now invalidate the existing
retrieval epoch for that org, independent of the optional connector-lineage flag.
Temporal supersession invalidates after its new insertion and again after marking
the prior row non-current, including the visible partial-insert boundary. This
does not make its multiple writes transactional or repair historical state.
Equivalent temporal content and writes that fail before mutation do not invalidate.

Tier-0 reads retain their captured key epoch and check it again before returning.
Fills capture an epoch before fingerprint work, reject a changed epoch and always
write under that captured key. An optional internal `source_epoch` lets the actual
streaming caller capture the epoch before recall/generation and reject a late fill
after an intervening memory mutation. Existing direct setter calls retain their
fresh-at-invocation behavior. No public response schema or memory trust policy
changes, no store retirement and no new embeddings feature.

## Executed evidence and remaining limits

All **18 new cases passed**, normal conftest loaded. Coverage includes the eight
baseline failures, failed-before-write controls, unchanged temporal value,
protected delete, stale versus fresh generation fills, and the actual streaming
caller across a synthetic context-change/model boundary. That joined caller case
forces the existing Tier-0 setting on and isolates provider, context and other I/O;
it proves conditional source behavior, not production usage. Successful mutation
cases independently assert that synthetic rows changed and that the other org's
cached answer remains available.

The current focused selection passed **160 tests, zero skipped**, covering CRUD,
source liveness, hardening, Phase-1 recall, performance cache, workspace, lineage
and quarantine suites. An overlapping selection including the existing full typed
streaming file passed 139 tests before four additional new test cases were added;
the production repair was unchanged between those runs. Do not sum those totals.

This evidence uses synthetic storage, no durable DB/Redis barrier or cross-replica
proof. The existing epoch update is best effort and CacheService can fall back to
process-local storage; shared-cache outages and other writers/erasure stores are
not certified. Old cache payloads retain their existing TTL; changing a read key
is not physical cache deletion. No guarantee is claimed for already-sent text, arbitrary direct
database mutations, or every cache surface. Authorization, speculative memory
ownership and complete erasure semantics remain acceptance requirements.

Full hosted CI on the resulting exact SHA must pass, including both unchanged
mandatory QA12 case counts (DEC-008 20 and DEC-011 six). New cache cases are regular
Core tests, not additions to either persisted gate's JUnit count. Canonical workflow
definitions and all twelve installed workflows are unchanged. Prior signed QA
preflight `44863581946` and independent cleanup evidence remain preserved and
unrepeated. Provider/live/rollback acceptance remains deferred; **0/43 certified
closed**, with every closure/release flag retained.
