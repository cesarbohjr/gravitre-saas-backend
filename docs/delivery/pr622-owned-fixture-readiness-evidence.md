# PR #622 — owned HTTPS fixture readiness

## Scope and observed failure

Source parent: `b8f81825bee7906fa01516571ff7cc8cde64d0ad`.
Integration owner remains PR #611 at `a43c7c073fe4186589c87ca1e9a497ba189c472c`.
This is an acceptance-harness diagnostic repair associated with the existing
P27-08 isolated-native-recovery gate. It does not certify that finding, change
the original 43 finding IDs, or authorize production/live acceptance.

[Operations run 45439289658](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45439289658)
failed in [job 138607352869](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45439289658/job/138607352869),
step `Execute both real workers through persisted acceptance IAM`.
The emitted evidence identifies `owned_https_fixture_readiness`, `TimeoutError`,
and two `origin_unreachable` attempts. The authenticated actor/cross-tenant RLS
scenario passed; worker lifecycle scenarios had not started. The prior evidence
cannot distinguish DNS, TLS, connection refusal/reset, timeout, or other transport
failure. The tunnel's private log was removed by existing temporary-file cleanup.
The network root cause remains unproven.

The separate paired Chromium comparison passed on the same parent:
[artifact 14945291992](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45439289658/artifacts/14945291992).
The archive SHA-256 is
`bb4cb853d5f8767951ccfc85019bf5a1d4a12fc42d9e9496ea6a4c7d5d74dc56`.
Its embedded SHA matches the source parent. All five Browser Use and five
Playwright trials passed approved-click readback, denied/cancelled/stale no-write
controls and independent server write counters; unauthorized writes were zero.
This is a fixture microbenchmark, not full tenant gateway or production evidence.

## Engineering change

- Check the local independent receiver's exact `/page` before launching a tunnel.
  A wrong page or unreachable receiver fails before any tunnel process starts.
- Share the exact status, final URL and bounded byte comparison between local and
  public probes. A redirect, extra bytes, unrelated page or non-200 response fails.
- Preserve only fixed transport categories and HTTP status in public evidence.
  Exception text, URLs, capabilities, credentials, response bodies and raw logs
  are not exported.
- Before private logs are cleaned up, extract three allowlisted booleans:
  connection registered, origin connection error, and edge connection error.
- Retain the existing two attempts, 45-second readiness wait and five-second
  request timeout. Retain fail-closed exit status and process termination.

No production runtime, approval identity/evidence, tenant permission, image,
network allowlist, compiler source, workflow trigger or timeout is changed.
This improves failure attribution; it does not claim to repair the unidentified
network outage.

## Local verification

Command (an isolated environment with pytest, pytest-asyncio, cryptography and
Pillow; repository dependencies unchanged):

```sh
PYTHONPATH=backend python -m pytest --confcutdir=backend/tests/native_runtime \
  backend/tests/native_runtime/test_tenant_worker_contract.py \
  backend/tests/native_runtime/test_broker_process_contract.py \
  backend/tests/native_runtime/test_browser_adapter_benchmark.py \
  backend/tests/native_runtime/test_browser_evidence.py -q
```

Result: **84 passed, zero skipped**. This intentionally excludes the backend-wide
conftest/application fixtures. New cases cover category sanitization, local
preflight refusal, exact page/URL/status, closed HTTP-error responses, retained
diagnostics across both failed attempts, process-exit/no-announcement cleanup and
a real independent local HTTP receiver with zero writes. Neighboring process,
approval and browser evidence checks run unchanged. No Docker/gVisor, hosted
acceptance database or external tunnel is executed locally.

## Remaining gates

The parent Core run is still executing; its dedicated ten-case step is marked
successful, but actual verbose/JUnit evidence is not yet available from the
unfinished job. Do not claim ten executed/zero skipped from the step status.
Publishing to #622 would cancel that run under its PR concurrency policy; preserve
it until completed, read the ten actual case outcomes and full backend result,
then publish the prepared correction using an expected-head check.

After publication, verify all ten workflows on the new exact SHA, including the
actual dedicated ten-case logs and the new sanitized tunnel evidence. Diagnose
the specific transport stage if it still fails; do not blindly rerun. Keep #611,
production, migrations, live provider actions, permissions and finding closure
unchanged. Engineering diagnostic gap addressed; hosted verification pending;
zero newly certified findings.
