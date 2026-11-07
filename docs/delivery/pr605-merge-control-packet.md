# PR #605 merge-control packet — November 6, 2026

This packet covers pre-merge engineering and release controls. It does not
authorize merge, deployment, migrations, provider writes, telemetry, historical
reconciliation, or removal of legacy code. P27-01–08 production acceptance is
NOT RUN until the separately approved production release.

## Reconciliation and billing-runner repair

Reconcile PR head `d0c20f1619ec011ef25e1368a59e09bd3a20c81c` with current main
`82bae7a8b2ecd92d72d3fcbf71b01855ba91c225` using a real three-way merge. The
three incoming paths are the connector toaster component, its CSS, and its
regression test. Retain the PR's modernization changes and all incoming #608
changes. A new resulting head requires new exact-head Actions evidence.

The isolated billing workflow previously invoked the unrestricted default
Playwright configuration despite a dedicated billing acceptance configuration
already existing. Select `playwright.billing.acceptance.config.ts` explicitly
to run the trial-expiry and founder-billing specs only. Use localhost:3000 to
match the sandbox checkout return URL asserted by the existing acceptance
spec. This changes test selection and the local origin, not the assertions or
production application. Retain the exact acceptance-project allowlist, Stripe
test-key check, schema preflight, zero retries, and no production credentials.
Do not substitute mocked browser tests for genuine isolated billing acceptance.

## Temporary production holds

Evidence and restore instructions are recorded in PR comment
https://github.com/cesarbohjr/gravitre-saas-backend/pull/605#issuecomment-6691107339.
Keep all three holds in force throughout pre-merge certification:

- Railway official Source Disable control removes the production branch
  autodeploy trigger while keeping the repository and running deployment.
- Both Vercel projects override Deployment Sources for Production with Git
  blocked. Preview is outside the rule. Do not replace this with build-ignore.
- GitHub Actions `Railway backend production` remains disabled manually because
  its main-push path can force GraphQL deployment independently of autodeploy.

Manual API/CLI and integration deployment paths are not covered by these narrow
holds. Do not dispatch auth-config-sync, milestone2-latency-ab,
unified-turn-phase2-live, or unified-turn-phase4-cutover during the hold.

## Branch protection — APPLIED after explicit owner authorization

The owner separately authorized this exact policy, which was applied and verified
in PR comment 6693200708. Preserve it without weakening or adding bypass actors.
The current follow-up and complete high-advisory reachability inventory are in
`pr605-merge-readiness-followup.md` and `pr605-high-dependency-triage.json`.

Enforced classic rule for main:

| Control | Enforced setting |
| --- | --- |
| Require pull request | Enabled |
| Required approving reviews | 1 independent reviewer |
| Dismiss stale approvals | Enabled |
| Require approval of most recent reviewable push | Enabled |
| Required checks | Backend (pytest); Web (lint + typecheck + build); Dependency audit; Shared runtime text/voice gate; Integration Smoke Test |
| Require branch current with main | Enabled |
| Require resolved conversations | Enabled |
| Apply to administrators | Enabled |
| Force pushes and branch deletion | Disallowed |
| Bypass actors | None configured |

Specialized exact-head workflows remain mandatory in the release evidence ledger
even if they are path-filtered and not configured as unconditional required
checks. Billing Playwright remains a distinct safe-execution gate. Do not make
the manual/production verification workflows unconditional required PR checks.
One review requires an eligible reviewer other than the PR author; do not
pretend the author can approve their own PR.

## Release and rollback worksheet — no actions performed

Baseline backend: deployment `78fb8af7-2c90-4a4f-9a34-180398ad20fb`, commit
`557be844f191767ea51c9f1d1d4958e5b046ca53`; Redis deployment
`55511e94-d758-42bb-8791-ea8c4ffc16c4` is unrelated and must remain unchanged.
Vercel A baseline: `dpl_5zTpqtvFnJ4gYHE7C96oLratfGcC`; B baseline:
`dpl_HVMTUjVoR41JQuLGaUM2Gyn2FHFa`. Refresh these identities at release time.

Before separate deployment approval, record an operator, window, exact approved
merge SHA, baseline 5xx/latency, and abort limits. Abort on wrong SHA, failed
health, database/cache degradation, unauthorized external effects or tenant
isolation failures. Do not enable new telemetry to obtain evidence implicitly.

Rollback rehearsal must identify the Vercel Instant Rollback target for each
project and the Railway retained deployment's rollback action. Verify target
IDs and availability without invoking them during this hold. A rollback must
not rebuild an unknown main tip or replay migrations. Confirm schema
compatibility first; migration reversal and historical data repair require
separate review and authorization. After any approved rollback, verify actual
SHA, API database/cache health, web routes, cancellation and authorization.

This is a prepared procedure, not evidence of executed rollback or production
acceptance. Final exact-head run URLs, test/skip counts and any owner decisions
belong in the PR evidence comment after CI finishes, avoiding another
documentation-only head change after certification.
