# DEC-011: mandatory real-PostgREST QA12 gate

Base `3eaad5dba81c84443e2360bfab8bf048ae964a42`: all ten workflows passed on
that exact SHA. Core `45134038024` passed all five required contexts; backend
job `137555980185` reported 17,516 passed, 70 skipped and 14 passing subtests.
The six additional Core skips were the new optional PostgREST cases, which
motivates this mandatory gate rather than treating source CI as persisted proof.
Operations `45134038090` passed on attempt 2 after the preserved external tunnel
readiness failure, with 25 scenario records/24 worker cases, zero unauthorized
writes and resource cleanup. This does not certify deployed provider acceptance.

The existing QA12 artifact `14798844056` was already independently downloaded,
hashed and parsed: exact base SHA, PASS, 20 tests, zero skips, PostgREST 16.6,
PostgreSQL 18.7, external-project false and whole-finding certification false.
ZIP SHA256 `8d16aad3f27aa7da27e87271266262c97aa875c63ec584c5b37ccd4f02fcea26`.
It is DEC-008 evidence and was not downloaded again or relabeled DEC-011.

## Change and ownership

The existing `master-qa-p0-synthetic` actual-runtime/PostgreSQL job in canonical
QA12 now has a separate, unconditional DEC-011 gate and an always-uploaded
sanitized artifact. The canonical source is
`docs/delivery/master-qa-workflow-source-contracts.json`. Its candidate was
regenerated with `scripts/build-canonical-workflows.py`, installed and checked;
there are still 94 retained sources, 123 jobs and twelve installed lanes.
Existing job steps, checkout protections, permissions, timeouts and guards are
retained. No generated workflow was changed without its source definition.

`backend/scripts/run_dec011_postgrest_gate.py` calls the shared execution and
JUnit validator extracted within the existing DEC-008 script. The existing
DEC-008 CLI still selects its original file and requires exactly 20 complete
cases. The new wrapper selects only the existing six DEC-011 persisted cases:
five actual department-reader cases and the joined actual kernel consumer case.
Neither gate uses a replacement reader. No production memory code changes here.

DEC-011 requires an explicit exact expected SHA, an unchanged tracked checkout,
both database binaries, PostgREST exactly 16.6 and PostgreSQL exactly the expected
numeric version. Canonical CI fixes PostgreSQL to `18.7` via the step environment;
a different installed version fails the gate instead of being silently accepted.
The existing shared PostgREST installation verifies archive SHA256
`335ea29f00145705fb569b1268b9c8e53d062f8f6f9188192e92ea3781d2dca1`.
The existing PostgreSQL installation is retained; the new version check enforces
the DEC-011 version contract after installation.

Pytest must exit successfully and produce exactly six JUnit cases with no skips,
errors or failures. The evidence is written on failure as well as success. On
success it includes exact SHA, binary versions, tests=6, skipped=0, external
project false, provider acceptance NOT_RUN and whole-finding certification false.
Its artifact is `dec011-real-postgrest-<exact-head>`; missing evidence fails upload.
There is no `continue-on-error` or conditional skip on the new execution step.
That step first runs the 16 DEC-008/DEC-011 gate unit checks, then executes the
six-case persisted gate; those unit checks are separate from the six-case JUnit.

## Local verification

The gate/compiler/router selection passed **42 checks**, including negative
contracts for missing binaries, missing or wrong expected SHA, dirty checkout,
wrong PostgREST/PostgreSQL versions, failed pytest and partial/extra/skipped/error
JUnit. Existing DEC-008 tests continue to require its independent 20-case report.

Both actual CLI gates ran in a clean isolated local Git snapshot
`9f9220828fa1e79443176378cc3387bd087ee835` (tree
`62e901119cd65f307d6ec81a2df441381b8f83fa`): DEC-011 **6 passed, zero skips**;
DEC-008 **20 passed, zero skips**. That snapshot contains the prepared gate runner
and persisted test files; the later canonical unit-check command, this document
and register update were added afterward. It is a local validation SHA, not the
published PR head. Wrong-checkout
and missing-binary CLI probes also exited nonzero with FAILED evidence.

Local binaries were PostgREST 16.6 and PostgreSQL 16.2; local DEC-011 validation
explicitly set `DEC011_EXPECTED_PG_VERSION=16.2`. This does not certify the hosted
18.7 version profile. Backend conftest loaded in the persisted cases; only the
existing root script unittest selection ran without backend conftest. No customer
credentials, provider requests or connected database were used. Test-owned
servers/clusters were stopped and removed by the existing disposable harness.

## Remaining gate

Full hosted CI and **both independent exact-head artifacts** remain pending on
the resulting published commit: DEC-008 tests=20/skipped=0 and DEC-011
tests=6/skipped=0, with the required versions and false certification flags.
Neither local nor hosted synthetic fixtures certify production RLS, deployed
flags/fallback activity, all memory/cache/erasure semantics, provider parity,
rollback or owner approval. All 43 findings remain uncertified. Both audit stores,
the PR610 voice boundary and the prior signed QA/cleanup evidence are preserved.
