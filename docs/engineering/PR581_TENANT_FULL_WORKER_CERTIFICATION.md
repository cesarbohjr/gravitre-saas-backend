# PR581 steps 1–3: tenant boundary and full worker lifecycle

## Prerequisite verified

Full CI run 40999329163 completed successfully on ee543070869671ff02dea50a718256ca11734678, including backend pytest, integration smoke, web, dependency audit and shared text/voice. Manual-only Billing E2E was skipped by workflow design. Native run 40999329160 and Langfuse run 40999329194 passed. No historical fixture result is presented as full tenant/worker certification.

## New execution — PENDING exact-source evidence

The native workflow now has a separate mandatory acceptance-environment tenant-worker-certification job. It reuses the SDK-certified image artifacts and real gVisor runtime, installs the actual backend dependencies and calls the actual worker.build_app, lifespan queue loops, signed /v1/invoke API, NativeRuntime and DockerRunner. The trusted Python runner factory permits constructing the existing opt-in comparison runner; its default remains the original DockerRunner/Browser Use. No client flag, production setting, grant or authority is added.

The job refuses any database except https://aadnwmjzrmbvadszroqt.supabase.co and requires the existing E2E_SUPABASE_URL, E2E_SUPABASE_ALLOWED_URL, E2E_SUPABASE_ANON_KEY, E2E_SUPABASE_SERVICE_ROLE_KEY and E2E_SUPABASE_JWT_SECRET acceptance configuration. It creates one disposable confirmed Auth user without sending an invitation, signs in through Auth, verifies that user, creates two isolated organizations/agents, and grants explicit scoped native execute/read permission. Authenticated-client RLS must allow the owned agent and hide the foreign agent.

Both adapters use the same signed worker API and actual gateway. Negative controls include foreign scope, invalid/expired signatures, changed signed payload, private destination requests, absent/expired execution grants, wrong action digest, a denied CONNECT target and an invalid engine token from inside the actual isolated engine. Membership and grant revocation modify only the newly created test rows and must fence the pending click.

## Matched cases per adapter

- Approved action and server readback.
- Denied action and cancellation.
- Persisted grant revocation and persisted membership revocation.
- Fresh-fingerprint mismatch after approved context changes.
- Actual engine-container kill and actual gateway-container kill.
- SIGKILL of the actual worker app before dispatch and after the receiver commits an approved effect but before it acknowledges the browser.
- Lost submit acknowledgement with exact idempotent job resubmission.
- Lost action-approval acknowledgement, stale approval retry rejection and no duplicate effect.

Every case starts a fresh worker process, private journal and case-specific receiver capability. Broker-crash cases restart that same app on the same encrypted journal, wait for the real standard 60-second lease to expire and require uncertain/reconciled state, deterministic sandbox cleanup and no execution on resubmission. No artificial claim clock, FakeSupabase, alternate HTTP authority or patched authorization guard is used.

## Independent effects and isolation

An owned HTTP receiver runs in a separate OS process with a durable SQLite event log and no application/database/CI credentials. A hash-pinned cloudflared 2026.10.6 test tunnel gives it a temporary public HTTPS origin, so the production gateway's public-DNS and exact-host restrictions remain intact. The tunnel receives no database credentials. Each POST requires an unguessable fixture capability; only actual receiver requests create events. Counter keys remain valid until the end, are distinct per case and are checked again after all cases and receiver shutdown, so delayed writes cannot be masked by a later case's expected write.

The model route is a scripted, authenticated HTTPS fixture on the Docker bridge. Its generated CA reaches only the trusted gateway, not the engine; no external AI provider or customer operation is used. Fixture readback waits for the committed receiver acknowledgement. Tests never call real customer connectors.

Only fixed labels, states, counts, cleanup booleans, source hashes and image digests are evidence fields. No cap, JWT, provider credential, user email, raw DOM, screenshot or private process log is uploaded. Test organizations, memberships, grants, actor sessions and Auth user are cleaned up; failures block the result. Temporary tunnel and sandboxes are terminated.

## Local validation and acceptance bar

Five real local process/import/receiver checks pass, including wrong-capability rejection, per-case counter separation and a committed effect before a held acknowledgement. Changed Python sources and workflow YAML parse. Full backend/SDK execution is delegated to CI; it is not claimed locally.

The new job is PASS only after authenticated RLS proof plus all 24 adapter cases complete, authorized write counts match exactly, unauthorized effects are zero, natural recovery completes, no jobs replay and cleanup succeeds. Missing secrets, blocked tunnel networking, backend/import failures or incomplete scenarios emit BLOCKED and fail CI. The 60-minute job budget accommodates backend dependency installation plus both matched worker suites; the execution step remains bounded at 30 minutes and no test is skipped to make it green.

Production activation/TLS host rollout, live provider quality, representative reliability/cost, historical Browser Use evidence drift and combined PR587 certification remain separate gates. PR581 stays draft/unmerged; no production deployment or adapter switch is performed.
