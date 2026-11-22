# DEC-008: local audit-reader repair and disposable PostgreSQL verification

Date: 2026-11-22. Base: PR 611 at `9b136df947a05bac56d7ec20b240e3f904ea8cf5`.
This is an unpublished local repair, not hosted or deployed verification.
The previous base-head CI and reproduction evidence remain in
`pr611-dec008-reader-reproduction-9b136df.md`; base-head CI does not verify this diff.

## Change

`backend/app/audit/query.py` now keeps both decoded cursor fields and applies:

```text
org_id = requested_org AND all_requested_filters AND
(created_at < cursor_timestamp OR (created_at = cursor_timestamp AND id < cursor_id))
```

Descending `(created_at,id)` ordering and limit-plus-one pagination are preserved.
The decoder rejects non-object JSON, non-string/missing/malformed fields, naive
timestamps and invalid UUIDs. It canonicalizes timezone-aware timestamps and UUIDs
before placing them in the PostgREST filter expression, preventing cursor fields
from injecting extra filter grammar. Invalid cursors retain the existing scoped
first-page fallback. The sibling RPC reader shares this parser.

No change was made to either audit store, audit writers, retained source workflow
definitions, installed workflow count, prior signed QA evidence or live acceptance.

## Before/after evidence

The existing disposable PostgreSQL harness was not usable in this sandbox because
Unix sockets are disallowed. PostgreSQL 16.2 binaries from pgserver 0.1.4 were
installed in a task-local directory. A test helper starts private temporary
clusters bound only to 127.0.0.1 with an ephemeral port and Unix sockets disabled.
Each cluster is stopped and its data directory removed in a finally block.
No external database or credentials are used.

The actual reader and actual Supabase SDK execute. A MockTransport translates the
small emitted PostgREST predicate subset into parameterized SQL. PostgreSQL owns
the persisted UUID/timestamptz rows, constraints, comparisons, AND/OR filtering,
ordering and limit. Fixture row counts are independently read from PostgreSQL.
This is PostgreSQL-backed reader evidence; a running PostgREST server, production
authentication, RLS and customer reachability are not exercised.

Before production-source repair, the PostgreSQL selection reported:
**1 failed, 6 passed, 13 deselected in 7.35s**. The failing completeness assertion
returned `[90,15]`, then `[1]`, losing IDs 14,13,12,11 at the same timestamp.
These IDs are UUID integer suffixes. All original result assertions were retained.
A duplicate cross-tenant fixture ID was corrected to a distinct ID for the real
primary-key schema; no expected result or tenant assertion was weakened.

After the repair, the original expanded suite reported **20 passed in 8.09s**.
Additional malformed/injected-field and combined-filter cases were then added.
Final focused reader + existing writer/receipt command, from `backend`:

```sh
GRAVITRE_PG_BIN=/workspace/scratch/e9501fc171b7/dec008-pg-runtime/pgserver/pginstall/bin \
/workspace/scratch/cfe2eca38c2b/qa-venv/bin/python -m pytest \
  tests/test_audit_reader_dec008_reproduction.py \
  tests/services/test_durable_outcome_delivery.py \
  tests/services/test_execution_outcome_restart_receipts.py -q --tb=short
```

**83 passed, 2 warnings in 15.56s**, with normal repository conftest loaded:

- 41 reader/parser cases: 17 PostgreSQL-backed, 17 memory-transport, 7 parser/RPC
  payload cases.
- 42 existing durable dual-store delivery and restart receipt cases.
- Same-timestamp traversal returns every expected row in descending order.
- Interleaved other-tenant rows, foreign cursor, newer/older timestamp boundaries,
  inclusive time window and combined action/actor/resource/org filters pass.
- Invalid non-object, empty, mistyped, naive, malformed and injected cursors are
  rejected without bypassing org restriction; UTC and UUID canonicalization pass.
- The sibling RPC reader retains both cursor fields and org in its payload.

The memory oracle was extended to handle the new AND/OR predicate syntax. Existing
assertions were not weakened or removed. PostgreSQL evaluation is independent of
the memory comparisons, though both use the small transport predicate parser.

## Remaining verification

`tests/test_audit_trail.py` and `tests/test_audit_trail_filters.py` could not collect
in the partial local environment. The initial missing `temporalio` dependency was
installed into a task-local dependency directory without changing the shared test
environment; collection then stopped at missing `onelogin` in the app's SSO router.
These suites are NOT RUN here, not failed assertions. Full hosted CI on a future
published repair commit remains required. No unchanged failing hosted run was retried.

The source/transport and persisted SQL evidence do not prove audit_logs/audit_events
consumer parity, a deployed caller, physical-device acceptance, provider acceptance
or rollback. All original DEC-008 acceptance criteria remain applicable.
All 43 findings remain uncertified.

Next: publish this bounded repaired batch to PR 611 using expected-head protection,
then verify full hosted CI on its exact resulting SHA, including the API audit suites.
