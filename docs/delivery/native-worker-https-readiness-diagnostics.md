# Native worker HTTPS acceptance blocker

PR #611 source inspected: `a43c7c073fe4186589c87ca1e9a497ba189c472c`.

Exact-head automatic CI: nine workflows succeeded; QA 10 Operations failed.
Failing job: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45299544739/job/138140599507

The persisted tenant authorization scenario passed. Execution then stopped at
`owned_https_fixture_readiness`, with both temporary tunnel attempts reporting
`origin_unreachable`. The worker lifecycle cases did not execute. This is not
evidence of a worker lifecycle defect or a successful acceptance run. The prior
artifact does not distinguish DNS, TLS, timeout or connection failure.

The diagnostic change records fixed transport categories and occurrence counts
per attempt. It exports neither exception messages nor the ephemeral hostname,
capability, credentials, private tunnel log or response body. Both bounded
attempts, exact owned-page verification, HTTPS verification, process cleanup and
the failing exit status remain unchanged. No timeout or authorization gate is
relaxed, and no fallback endpoint is introduced.

Local validation: 20 tests passed in
`backend/tests/native_runtime/test_tenant_worker_contract.py`, including raw and
URL-wrapped transport failures, category-only output, two-attempt cleanup,
rejection of unrelated content and successful owned-fixture readiness. Local
testing used isolated pytest discovery because the complete backend dependencies
are not installed here; this does not establish full backend or hosted acceptance.

The next hosted run must establish which transport layer failed before a repair
is selected. Hosted HTTPS reachability and the complete real-worker lifecycle
remain verification pending. No finding is certified closed; the register still
contains 43 NOT_CERTIFIED records, including one administratively consolidated
entry. No merge, production migration or deployment is performed by this change.
