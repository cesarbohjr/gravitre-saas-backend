# ECO-013 / DEC-005: persisted conversation-plan authority

Base `9905203c3e7991ca73e145d23729ce5757eb3065`. No production code changed in
this batch and no further production defect was reproduced. This adds durable
contract evidence for the previous unfinished-write terminal repair and makes
that evidence mandatory in the existing canonical QA12 lane.

## Completed prerequisite

All ten raw GitHub run records succeeded on the exact base, attempt 1:
Core `45192140018`, Operations `45192140973`, QA04 `45192141275`, QA12
`45192139359`, Identity `45192139895`, Data `45192140348`, Intelligence
`45192140491`, Voice `45192140013`, Browser `45192139730`, Marketing `45192139840`.
[Core](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45192140018)
backend `137753115489` reported **17,565 passed, 70 skipped, 14 passing subtests**;
all five required contexts and later offline checks succeeded. Web `137753115211`,
Shared text/voice `137753116518`, audit `137753117429`, smoke `137753115684` passed.
[Operations](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45192140973)
worker job `137754726877` passed all 25 scenario records with fixture attempt ready;
no retry was requested on this head.

[QA12](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45192139359)
actual-runtime job `137753098663` ran the checksum-pinned PostgREST 16.6 binary,
DEC-008 20 passed/zero skipped, 16 shared gate unit checks, and DEC-011 six
passed/zero skipped on PostgreSQL 18.7. Both actual ZIPs were independently
downloaded, matched to GitHub digests and parsed in the preceding checkpoint;
they were not downloaded again:

| Gate | Artifact | ZIP SHA256 |
| --- | --- | --- |
| DEC-008 | `14826708309` | `3f832f950264dbd980463d81af77d476c05717cc54027e3a30fb770c5a97bed1` |
| DEC-011 | `14826798134` | `c022b8112ab2088e465f8df919f037fd4f9ef73090154ffdca8c6f87d7cf18cc` |

Each JSON has exact base SHA, PASS, its required count, zero skips, external
project false, whole-finding certification false and provider acceptance NOT_RUN.
DEC-011 expected PostgreSQL version is 18.7. Skipped live/provider/billing/signed
jobs and the physical-voice offline schema/simulation placeholder are not live
acceptance. Prior Operations tunnel failures remain in the preceding evidence.

## Actual writer and independent durable observation

The tested path is the existing `ConversationStateService.update_task_state`
and `_persist_state_sync` -> actual adapter/authority helper -> real Supabase SDK
HTTP -> standalone PostgREST 16.6 -> disposable PostgreSQL. Its read/merge/write
and task-revision predicates are not replaced with a synthetic SQL translator or
mock HTTP transport. The fixture reuses the existing loopback disposable-cluster
owner. Local synthetic JWT roles permit SELECT/UPDATE or SELECT-only; no external
project, credentials, providers or customer records are used. No production RLS
policy is copied or certified: tenant-negative cases test application predicates.

Eight cases in `backend/tests/test_eco013_plan_authority_postgrest.py` verify:

1. Stored cancellation with a pending write survives an older approval patch;
   actual service reload and reconstructed ReAct dispatch still stop.
2. Stored blocked status with a running write survives an equal-revision approval.
3. Between the actual HTTP GET and PATCH, a request hook commits cancellation
   through an independent SQL connection. The actual first CAS returns no row;
   the writer reloads and issues revision predicates `eq.8`, then `eq.9`.
   Independent SQL readback sees cancellation, cancelled pending projection,
   task revision 10 and the other writer's retained field. This is a deterministic
   transaction interleaving, not load/timing or multi-process qualification.
4. A legacy row without task revision uses actual PostgREST `is.null` CAS and
   retains its terminal plan at revision one.
5. A foreign org paired with the same conversation ID cannot mutate either row.
6. A distinct new action can request its own approval.
7. Newer terminal evidence can resolve an inconclusive plan under the existing
   authority policy; the test constructs the evidence patch and does not verify
   a provider or grant approval.
8. Actual PostgREST SQL permission denial returns 403 and leaves storage unchanged.

The first fixture draft used its read-only JWT role as the anonymous role, making
the last denial return 401; seven other cases passed. Separating the anonymous
role from the authenticated reader corrected the fixture, preserving the 403
assertion and SELECT-only grants. No production change or softened assertion is
claimed. Both synthetic conversation rows remain before every fixture teardown.
Independent checks found no task PostgreSQL directory or task server left over.

## Required canonical gate and executed local evidence

`backend/scripts/run_eco013_postgrest_gate.py` reuses the existing strict gate
implementation with an independent fixed eight-case file and sanitized artifact.
It requires exact expected 40-character SHA, clean tracked checkout, actual
PostgREST 16.6, expected PostgreSQL numeric version and exactly eight successful
JUnit cases with zero skips/errors/failures. The hosted expected PostgreSQL
version remains 18.7; the local 16.2 profile requires an explicit override.

Retained source `docs/delivery/master-qa-workflow-source-contracts.json` adds
exactly two steps to the existing runtime job: required execution and always-on
artifact retention (missing file is an error). The candidate was regenerated and
the installed QA12 synchronized. Every previous source job/step/security field
was independently compared unchanged. No new job, lane, timeout relaxation or
permission was added. Still **94 sources / 123 jobs / 12 installed workflows**.
The independent DEC-008 20-case and DEC-011 six-case commands/counts are unchanged.

- Actual persisted pytest: **eight passed, zero skipped**, normal conftest.
- Root gate/compiler/event-router checks: **46 passed** (no backend conftest).
- Existing authority plus register/no-unsafe-dict guards: **76 passed**, normal
  backend conftest; separate from the eight persisted cases.
- Actual CLI on clean isolated validation snapshot
  `a1724c3bc1a3cf808e7a2c7795f4f48d3628bc94`, tree
  `de380975ab4f645cdf5ecd00273423a98b62b689`: **eight passed, zero skipped**,
  exact validation SHA, PostgREST 16.6 / PostgreSQL 16.2 with explicit version
  override. No production code changed between that snapshot and final metadata.
- Actual wrong-checkout, missing-binary and wrong-version CLI probes returned
  failure before execution and emitted FAILED evidence without a test count.
- Shared gate's existing fail-closed unit checks remain required; the additional
  four ECO-013 wrapper/JUnit/canonical checks run in the new execution step.

The new hosted eight-case gate and its artifact remain pending on the resulting
head. Local PostgreSQL 16.2 is not hosted 18.7 proof. Core's optional missing-binary
skips do not satisfy the mandatory gate. All source/test observations remain
bounded: no production auth/RLS, live provider, actual customer ingress,
cross-replica deployment, all-writer convergence or rollback certification.

Only ECO-013/DEC-005 receive these linked partial contracts and prior-head CI
evidence. Closure/release booleans are retained. Both audit stores, all existing
owner/main-only signed fixture guards and prior signed QA/cleanup evidence are
preserved. No merge, deployment, live/signed dispatch, provider writes, migrations,
history repair or legacy retirement. **0/43 findings certified closed.**
