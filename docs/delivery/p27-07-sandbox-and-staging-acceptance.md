# P27 release gate — sandbox provider and deployed staging execution

Status: **BLOCKED on external account and staging provisioning**. PR #611 remains draft, unmerged, undeployed; `WORKFLOW_ORPHAN_RECOVERY_ENABLED=false`.

## Verified resources

- Connected HubSpot portal `343328749` (Gravitre AI) reports account type `STANDARD`. **Do not use it for synthetic writes**.
- Connected Railway workspace has projects `spirited-communication` (backend and Redis) and `Gravitre front-end`, each with **production only**. No independent staging service or database has been confirmed.
- PR-owned manual workflow: `.github/workflows/master-qa-p27-sandbox-readback.yml`, `workflow_dispatch`, protected environment `p27-provider-sandbox`. The action is not part of ordinary PR CI and cannot execute without specific sandbox credentials, an explicit dispatch input, and environment approval.
- Genuine **two-process** offline crash/restart test: `backend/tests/master_qa/test_worker_process_crash_restart_pg.py` and `_p27_worker_subprocess.py`. Uses disposable PostgreSQL and a SQL-backed provider simulation, **not HubSpot** or an actually deployed Railway worker.

## HubSpot developer-test portal onboarding — operator-owned

1. In HubSpot open **Development → Testing → Test Accounts → Create developer test account**. Name it `Gravitre P27 Release QA`. Select an isolated developer-test environment, not the connected `STANDARD` portal.
2. In that test account, issue an API **Service Key** scoped to CRM contacts read/write (or a supported test-only OAuth app/token). Do not paste it into a PR, chat, or general repository variable.
3. On the GitHub repository create protected environment `p27-provider-sandbox` with required reviewers, protected branch rules and restricted access. Add variables `P27_HUBSPOT_SANDBOX_PORTAL_ID` and `P27_HUBSPOT_QA_EMAIL_DOMAIN` (a dedicated domain you control) and secret `P27_HUBSPOT_SANDBOX_TOKEN`. A token from the connected standard portal must be rejected.
4. Verify the account-info endpoint returns the expected portal ID and a permitted test account type *before* dispatch; do not turn off those checks.
5. Dispatch workflow `P27 HubSpot sandbox authoritative readback — manually approved only` on reviewed PR SHA with input `approval=APPROVE_NONPRODUCTION_WRITE`. Confirm GitHub environment review before execution.
6. Archive the complete Actions run URL, SHA, portal ID, created contact ID, independent CRM GET response and same-email upsert outcome. Review and delete the synthetic contact from the test account when no longer needed. A PASS from local mocks is not live-provider certification.

## Dedicated staging worker crash/restart — operator-owned

1. Provision separate staging backend, Redis and PostgreSQL (new project/environment with **no production database URLs, keys, connector accounts, or domains**). Do not duplicate production secrets. Deploy a reviewed build of the exact P27 SHA after staging migration validation.
2. Apply `supabase/migrations/20261107235500_p27_graph_recovery_leases.sql` to **staging only**, verify role EXECUTE restrictions, and use a staging-only HubSpot developer-test connector.
3. Set `WORKFLOW_ORPHAN_RECOVERY_ENABLED=true` only in staging with short, bounded thresholds and configured alerts. Confirm at least two distinct worker process IDs and separate SQL claim sessions.
4. Create a single approved, synthetic, idempotent contact action and durable `executor_in_flight` checkpoint. Terminate the **worker process** after the provider commits but before local receipt, not the database or a production worker. Keep the source-of-record contact in the test portal.
5. Start a new worker. Prove the SQL claim parks the orphan; inject a second competitor and verify one winner, wrong-token rejection and no new provider write. Force the first recovery worker to exit after claim, expire its lease in staging, and prove replacement owner advances only after independent HubSpot GET/readback.
6. Verify the workflow and step are completed, exactly one test contact exists, the finalizer/outbox delivered once, and the run/claim journal is auditable. Repeat with provider outage/unknown readback: no additional write, run paused, checkpoint retained.
7. Capture staging deployment commit, worker logs/PIDs, SQL lease claim rows, API evidence, CI Actions links, rollback result, and security approval. Leave production rollout disabled pending formal release gate.

## Stop conditions

- No verified nonproduction HubSpot developer-test account / scoped credential.
- No isolated staging backend/DB/Redis.
- No protected GitHub environment approval for the sandbox write.
- Unknown provider readback or mismatch, failed staging reconciliation, lost lease, duplicate resource or missing checkpoint.
- General CI or schema security gates not green.

Do not present the offline two-process test as an actual deployed staging run, and do not interpret HubSpot's existing `STANDARD` portal as a sandbox.
