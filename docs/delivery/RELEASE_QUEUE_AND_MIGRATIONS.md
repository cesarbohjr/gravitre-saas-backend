# Gravitre release queue and controlled migration rollout

Status: proposed; **not a production migration executor**. Updated 2026-10-13.

## Current release blockers

- PR #424: GitHub CI passed, but Vercel `web` status failed; its production-verification workflow has not been tested against a live `/health` JSON response. Do not merge until the failed check is diagnosed and verification is validated.
- PR #425: GitHub CI and migration-safety job passed, but Vercel `web` status failed. Do not bypass the check.
- The existing Railway backend production workflow already tests `https://api.gravitre.app/health` and expects `git_sha`; this is evidence of the intended schema **in code**, not proof of a current live response.
- This execution environment could not resolve the production API hostname, so live response validation remains open.

## Production migration prerequisites — fail closed

1. Provision an isolated Supabase staging project with reviewed masked/fixture data and verify staging project ID explicitly differs from production `smyeexlrqdpymwjmgzqu`.
2. Reconcile migration versions and checksums of checked-in SQL against staging and production before planning any apply. Investigate out-of-band SQL and schema drift.
3. Run all new SQL on staging; run representative application smoke tests, tenant/RLS/grant checks, backward compatibility checks, query and lock impact tests.
4. Establish and **test** a recovery procedure: confirm the latest Supabase backup/PITR entitlement and timestamps; snapshot critical table data where appropriate; document restore drills and the irreversibility of destructive SQL.
5. GitHub administrator creates protected environments `supabase-staging` and `supabase-production`. Production requires independent reviewer approval, restricts deployment branches to `main`, and prevents self-approval. Do not place production credentials in repository-level secrets.
6. Store separate, least-privilege staging and production database deployment credentials in their respective *environment* secrets. Confirm both are present without printing their values; rotate any previously exposed credentials. Pin the migration runner and dependencies.
7. Establish a **single migration execution authority** and concurrency group, with an explicit migration version and immutable main SHA. Preview and approval must refer to that SHA. Recheck history immediately before execution; abort on drift or unexpected pending migrations.
8. Record result in an append-only deployment log: migration IDs, operator, approval, checksums, SHA, staging test run, backup checkpoint, execution time and post-deploy smoke evidence.
9. Apply backward-compatible schema before backend, and destructive cleanup only in a separate approved release. Stop immediately and escalate on partial execution.

**Do not enable GitHub Actions production SQL execution until steps 1–8 have been separately verified.** A GitHub `environment:` reference alone does not prove reviewers, restricted branches, or protected secrets are configured.

## Pending pull requests: preliminary grouping, not merge authorization

| Priority | PRs | Release theme | Prerequisites |
|---|---|---|---|
| P0 | #424, #425 | Production verification and migration safety | Fix failed Vercel web checks; validate live health contract |
| P1 | #361, #398 | Foundation repairs; audit retention/storage (draft) | Security review, migration/version reconciliation, staged flags, test and owner approval |
| P1 | #382, #354, #347, #336, #325 | Voice/chat latency, interruptions, context and tools | Group by overlapping backend paths, rebase in dependency order, realistic live acceptance |
| P2 | #289, #277, #278, #276, #275, #273, #267, #272, #271, #265, #263, #264, #261 | Marketplace, Revenue Ops, Security Ops, MSP | Identify superseded PRs and canonical latest implementation; avoid merging duplicate overlapping phases |
| P2 | #251, #250, #249, #248, #247, #246, #245, #231 | Connector proof, execution governance, UI and acceptance | Determine dependency order, cross-branch overlap, security tests |
 
Other unpublished branches and local-only patches cannot be considered deployment-ready. Retrieve commit and branch evidence before including them in a merge train.

## Per-PR release gate

For each proposed release, record: source ref, head SHA, changed paths, open migrations, tests, GitHub checks, Vercel project statuses, Railway requirements, feature flags, conflicts, rollback/recovery, owner acceptance, deployed SHA, and post-deploy smoke evidence.

- Never merge a PR on failed required checks or unverified deployment dependencies.
- Batch only independent and fully validated PRs; advance one merge at a time and verify the resulting `main` deploy.
- Do not confuse successful CI, GitHub merge, Vercel preview, Railway rollout, or production owner acceptance.
