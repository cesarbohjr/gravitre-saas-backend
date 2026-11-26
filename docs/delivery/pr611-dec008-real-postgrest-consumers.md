# DEC-008: actual consumers and real PostgREST verification

2026-11-22. Source under test: PR 611 at
`16176b8a2e6bcf98cd367b4bfedf36bb161acea1`, previously verified green in all ten
hosted workflows. This consumer test batch was first verified locally. Base-head
CI does not constitute hosted verification of the new harness.

## Consumer trace

The static inventory `dec008-audit-consumer-inventory-16176b8.json` identifies
**23 literal table-read sites in 16 backend files**: four for audit_logs and 19 for
audit_events. It is a source inventory, not runtime traffic or exhaustive dynamic
SQL analysis. A syntactic org-filter flag is not an authorization decision.

| Caller chain | Store and semantics | Evidence in this batch |
| --- | --- | --- |
| Settings Audit / Trust & Safety components -> apps/web/lib/settings-api/audit.ts -> /api/audit -> list_audit_logs -> _prepare_logs/_fetch_rows | audit_logs; offset paging of a newest-2000 scan, explicit truncated/scanLimit; created_at fallback to timestamp | Actual _fetch_rows executed over real PostgREST for both schema variants and tenant-negative reads. UI and full API authentication/entitlement chain not exercised. |
| /api/operator/context/run/{run_id} -> build_run_context -> query_audit_events -> audit_query RPC | audit_events; recent five workflow_run events; consumer discards continuation cursor | Actual build_run_context, workflow repository readers and retained SQL RPC executed without function doubles. Foreign-tenant run refused. total_events currently means returned recent-five count, not total history. |
| Workflow run observability route -> build_run_observability -> _audit_for_run | audit_events; up to 200 resource matches plus 300 recent rows scanned for metadata.run_id | Actual _audit_for_run executed and tenant-negative result verified. Full joined route response not certified. |
| query_audit_log | audit_events; repaired timestamp/UUID cursor | No backend/app call site found. Real pagination verified; customer exposure remains unproven. No endpoint was rewired to manufacture usage. |
| Metrics overview/connectors/timeseries/weekly throughput routes | audit_events count and time-window reads, optionally rollups | Source traced only; aggregation and row-cap parity not established. |
| Sources history/activity, connector activity, connector operations metrics, integration suggestions, marketplace sandbox, workspace changes, Meson feedback, platform health | audit_events; independent bounded readers | Literal read sites inventoried; full consumer journeys remain unverified. |
| Admin golden-signals route -> _fetch_rows | audit_events; 500-row offset pages, conditional org filter, platform-wide admin use | Source-reviewed require_admin route; not labeled an unscoped customer read solely because the inventory's chained org flag is false. |
| Enterprise SOC2 export and workforce analytics routes | audit_logs; separate projections | Source traced only; export/analytics parity pending. |

The audit router is mounted by backend/app/main.py:822 and Operator router by
main.py:897. The repaired helper is not used by the current audit-page reader.
Consequently the previous reader fix should not be described as a deployed fix to
the customer audit page. Both stores have distinct active source consumers.

Retention source also keeps both stores in AUDIT_TABLES, a 365-day audit floor and
legal-hold fail-closed handling. No retention operation or migration was executed.
Canonical workflow audit writing acknowledges audit_logs separately from optional
audit_events projection; this batch does not establish dual-store semantic parity.

## Real server setup

Official PostgREST release: https://github.com/PostgREST/postgrest/releases/tag/v16.6

Downloaded asset: postgrest-v16.6-linux-static-x86-64.tar.xz. SHA256 verified against
the release API's published digest:
`335ea29f00145705fb569b1268b9c8e53d062f8f6f9188192e92ea3781d2dca1`.
Binary reports PostgREST 16.6. PostgreSQL is disposable local version 16.2.
The deployed Supabase PostgREST version was not inspected or claimed equivalent.

The actual Supabase SDK connects over real loopback HTTP to real PostgREST, which
executes SQL on the temporary PostgreSQL cluster. No MockTransport, query parser
oracle or mocked application reader is used. The SDK rest_url is configured for
standalone PostgREST's root path instead of Supabase's /rest/v1 reverse proxy.

The fixture has local authenticator/member roles, task-generated JWT signing
material, synthetic memberships and membership-based RLS on both audit stores.
It executes the retained production audit_query SQL function from
supabase/migrations/20250204000005_audit_query_function.sql. Supporting workflow
tables allow the real Operator context builder to run without repository stubs.
These are minimal disposable fixture schemas/policies, not replay of the complete
Supabase schema or proof of deployed authentication/RLS configuration.

Both servers bind only to 127.0.0.1 on ephemeral ports. No external credentials,
customer data, external provider calls, production writes or live dispatches were
used. PostgREST is terminated and waited on; PostgreSQL is stopped and its temporary
data directory removed after each test. Both stores retain all ten fixture rows
before teardown, independently checked through the PostgreSQL owner connection.

## Test result

From the isolated worktree backend directory:

```sh
GRAVITRE_POSTGREST_BIN=/workspace/scratch/e9501fc171b7/postgrest-runtime/postgrest \
GRAVITRE_PG_BIN=/workspace/scratch/e9501fc171b7/dec008-pg-runtime/pgserver/pginstall/bin \
/workspace/scratch/cfe2eca38c2b/qa-venv/bin/python -m pytest \
  tests/test_audit_reader_postgrest.py -q --tb=short
```

**20 passed, 2 warnings in 20.64s**, normal backend conftest loaded, zero skips.

- Six page sizes (1,2,3,5,7,10) traversed all seven org-A records with no loss or duplicates.
- Three page sizes proved actual retained RPC and table-reader ordered results agree.
- Independent RLS denied org-B rows even without the application org filter; anonymous HTTP got 401.
- Three malformed/injected cursor shapes fell back safely within org-A scope.
- Actual customer audit read helper handled created_at and legacy timestamp schemas.
- Actual Operator context returned its current recent-five contract via real RPC;
  foreign run was unavailable. Run-observability audit reader also stayed tenant scoped.
- Member insert attempts into both stores were refused with 42501; counts were unchanged.
- Membership revocation removed table, RPC and audit_logs visibility immediately.
- Equal-timestamp cursor bounds retained action, actor, resource and inclusive date filters.

## Remaining gates and next action

This verifies the repaired reader's PostgREST grammar and local persisted/RLS
behavior, plus the named consumer functions. It does not certify every inventoried
consumer, full dual-store parity, deployed caller traffic, UI, physical devices,
provider-write acceptance or rollback. No store retirement is authorized.
All 43 findings remain uncertified.

## Mandatory canonical QA gate

The retained master-qa-p0-synthetic source contract now adds this gate to QA12's
existing actual-runtime-and-postgres job. Candidate and installed QA12 were
regenerated/synchronized; `build-canonical-workflows.py --check` passes with
94 sources, 123 jobs and exactly twelve installed workflows. No workflow was added.

The job checks out the exact PR head (credentials not persisted), downloads the
pinned PostgREST16.6 archive, checks the published SHA256 before extraction and
exports its binary path. The required step runs
`backend/scripts/run_dec008_postgrest_gate.py`, without continue-on-error or a
conditional skip. Missing binaries, unexpected version or wrong checkout fail.
JUnit must contain exactly twenty cases with zero skips, failures or errors;
otherwise the step fails. Sanitized JSON is retained as a per-head artifact with
whole-finding certification explicitly false.

Local verification of the exact gate command: **20 passed, zero skipped in 20.68s**.
Canonical/gate contracts: **21 passed**. Event router contracts: **9 passed**.
Negative CLI checks independently refused missing PostgREST and wrong checkout.
The JUnit guard also rejects missing/extra cases, skipped cases, failures and errors.

Next: publish this bounded test/evidence/canonical-gate batch with expected-head
protection and verify all ten hosted workflows on the resulting exact SHA.
