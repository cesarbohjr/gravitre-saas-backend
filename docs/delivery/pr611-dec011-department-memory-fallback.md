# DEC-011: department-memory fallback eligibility

Base: `e263ac859c6d197533be158e3447acf9fe140718`. Bounded reader repair;
DEC-011 and all other findings remain uncertified. No store is removed, no
feature is enabled, and no external project or provider is used.

## Prerequisite verification

All ten base-head workflows succeeded, verified against raw exact-SHA run records.
[Core 45119382310](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45119382310)
passed all five required contexts; backend job `137509473183` reported 17,508
passed, 64 skipped and 14 passing subtests. Operations
[45119382268](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45119382268)
passed on attempt 2 after the previously diagnosed fixture-tunnel startup failure.
Retry job `137522933713` completed 25 scenario records, including 24 worker
cases, zero unauthorized writes and resource cleanup. The original failed
artifact `14792643944` remains part of the evidence history.

The previously downloaded QA12
[artifact 14792858947](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45119382274/artifacts/14792858947)
matches the base SHA, PASS, 20 tests, zero skips, PostgREST 16.6 / PostgreSQL 18.7,
external-project false and whole-finding certification false. ZIP SHA256:
`5e1d9fee63d37b061828c0594aae6f816e4c18a71fccf6c9143d878df5436f13`.
It was not downloaded again. Skipped live/provider/billing/signed jobs and the
physical-voice offline placeholder are not acceptance.

## Source ownership inventory

The accompanying `dec011-memory-source-inventory-e263ac8.json` records 109 literal
table/RPC call sites in 26 backend application files. It selects names containing
`memor` plus the three hybrid graph/glossary/query-cluster stores and the named
entity-resolution store. It excludes dynamic names, nonliteral storage wrappers,
conversation JSON fields and external caches; it is not a complete runtime-store
inventory or evidence that every source site is active.

| Source path / owner | Storage and reader semantics observed |
|---|---|
| `ContextAssembler` -> `UnifiedRetrievalService` | Agent memory through `build_task_retrieval_context`; org snapshot and knowledge sources have separate owners. Existing explicit scope-denial propagation remains. |
| `CognitiveTurnKernel._recall` | Parallel hybrid, per-agent, department, ledger and workspace readers. Department resolution calls actual `search_department_memories`; merge preserves source and org. |
| `HybridMemoryService` | `agent_memories`, `org_entity_relationships`, `org_glossary_terms`, `org_query_clusters`; existing active/current/expiry constraints on agent rows. |
| Agent/workspace and temporal/lifecycle services | `agent_memories`, `agent_memory_history`; `deactivate_memory` sets active/current false, temporal supersession clears current, expiry is independent. Department fallback previously ignored those states. |
| Cross-conversation ledger and opaque entity memory | Entity-resolution wrapper and optional HMAC-based embedding RPCs; not replaced or enabled here. Exact opaque matching is not fuzzy resolution. |
| Conversation memory engine | Conversation task-state JSON, not a new memory table; scoped through conversation-state service. Not certified by this batch. |
| Source-liveness/cache owner | `memory_source_liveness` filters revoked connector lineage when enabled, and invalidates org retrieval epochs/derived caches. Department fallback has no cache of its own. Global erasure/cache parity remains open. |

The kernel's optional `dialogue_memory_governance_v1` adds a later authoritative
snapshot filter. Tests explicitly disable it to exercise the department reader's
own contract independently. Production flag values and actual fallback frequency
are unknown; no deployed stale-memory exposure or authorization bypass is claimed.

## Reproduction and repair

The retained RPC SQL in `20261011192424_phase1_memory_recall.sql` checks active,
current, unexpired and requested category. The Python compatibility fallback
checked only organization and department, ordered newest-first and limited rows.
It also caught arbitrary errors, including actual SDK `APIError` denials/outages,
and tried a second table read. Existing tests covered Python `PermissionError`
and FastAPI `HTTPException`, not those SDK exceptions or stale fallback rows.

Before repair:

- Six SDK error responses (permission denied, JWT failure, timeout, connection
  failure, missing column and SQL undefined-function) plus a repository exception
  all incorrectly attempted table fallback: seven negative cases failed; the
  successful-RPC control passed.
- Five actual SDK -> standalone PostgREST 16.6 -> disposable PostgreSQL 16.2
  cases failed on unmodified source after fixture setup was corrected. No-category
  recall returned eight rows instead of four; a two-row limit selected expired
  records instead of eligible records. Category-specific and `all` controls also
  failed. Cross-org and cross-department fixture rows remained out of scope.
- Initial local fixture errors (synthetic bearer without a local JWT secret,
  then Supabase's `/rest/v1` prefix against standalone PostgREST) were harness
  errors, not production defects. The retained baseline failures above occurred
  after both were corrected.

Repair is confined to `search_department_memories`:

1. Permit compatibility fallback only for actual PostgREST missing-function
   schema-cache code `PGRST202`. All other errors propagate; existing explicit
   denial behavior is preserved.
2. Apply `IS NOT FALSE` to active/current, matching the RPC's legacy-null
   `COALESCE(..., true)` semantics; require null expiry or strict future expiry.
3. Apply normalized requested category before order/limit. Keep org and department
   predicates, lineage filtering, output shape, recency ordering and zero fallback
   similarity score. This does not make recency fallback equal vector ranking.

## Verification and limits

**145 focused tests passed, zero skipped**, normal backend conftest loaded. Of
these, 14 are new: eight SDK/error/control cases and six real-PostgREST cases.
The sixth persisted case joins the actual kernel department recall and prompt
assembly to the real reader while isolating the other stores. The five standalone
cases cover nullable legacy flags, inactive/superseded/expired/exact-expiry rows,
future expiry, categories, limit ordering and tenant/department negatives.

The fixture retains all ten persisted rows per case, uses a local synthetic JWT
and read-only fixture role, and stops the server/removes its cluster on teardown.
Independent process/directory checks found no remaining task servers or clusters.
Embedding I/O is stubbed; there is no transport double in the six persisted cases.
The fixture grants table SELECT without production RLS: application predicates
are exercised, not production authorization policy. The eight offline cases use
recording SDK HTTP/repository doubles and do not prove real permission denial.

Verification selection includes new files plus existing agent memory, department,
Phase-1 recall, source liveness, hardening, unified retrieval, dialogue policy and
cognitive kernel suites. `GRAVITRE_PG_BIN` and `GRAVITRE_POSTGREST_BIN` select local
disposable binaries. Proxy variables were unset because task Python lacks socksio.

Full hosted CI on the resulting exact head remains required. The six new local
PostgREST cases skip when binaries are absent; they are not yet mandatory in QA12.
The existing independent DEC-008 mandatory gate remains exactly 20 cases and is
unchanged. Next after green CI: make the new DEC-011 persisted cases mandatory in
the existing canonical QA lane without weakening or replacing the DEC-008 gate.
Full memory-store/cache/erasure parity, deployed caller evidence, owner approval,
provider observation and rollback remain pending. No finding is closed.
