# P27 — Tool-driven, protected HubSpot provider acceptance

**Scope:** one synthetic contact in the existing STANDARD HubSpot portal `343328749`.
**Owning PR:** #611. **Deployment:** none as part of enabling this workflow.
**Separation:** PR #610 owns Voice 3.0; this workflow only verifies HubSpot provider behavior.
**Status:** tool-based read-only preflight has executed successfully; live provider acceptance is **NOT RUN**.

## Release gate inspection — 2026-11-08

Read-only GitHub API inspection of
`GET /repos/cesarbohjr/gravitre-saas-backend/environments/p27-provider-sandbox`
confirmed **`protection_rules: []` and `deployment_branch_policy: null`**.
The named environment exists, but it is **not protected**. Independent PR
reviews were also empty at `e4538637a82276b2961b8b9a5c7964303065ce72`.
Do not apply the live label or use the manual live path in this state.

The existing `p27_hubspot_dispatch_guard.py` now reads the actual environment
metadata and rejects both live dispatch paths unless required reviewers,
prevention of self-review and a deployment branch policy are configured.
An independent user or team must be eligible to review; absent, malformed or
unavailable metadata fails closed. GitHub remains responsible for enforcing
the configured branch compatibility and deployment approval; no new approval
engine is introduced. No environment settings, secrets or provider records
were changed by this repair. Regression coverage includes both dispatch paths,
unprotected/author-only/self-review/branch-policy failures, missing metadata
and a scoped read-only metadata request.

Pre-repair head evidence:
- [Master QA 42547495248](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42547495248):
  181 runtime guard tests and 49 disposable PostgreSQL acceptance tests passed,
  zero skips. SQL provider fixtures remain simulated provider evidence.
- [Read-only dispatch 42547860494](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42547860494):
  preflight passed; provider write job skipped.
- Existing backend health returned 200 at SHA `557be844f191767ea51c9f1d1d4958e5b046ca53`;
  `gravitre.app` mapped to frontend SHA `2e78e03a58e29e03019687b03ad90fd6ad420e84`.
  Neither deployment contains this PR. Production E2E acceptance of the PR
  remains NOT RUN; no service restart or migration was performed.

The environment guard repair creates a new head and requires new exact-head
CI. Passing checks on `e4538637` cannot certify the new commit.

## Why label dispatch exists

The connected GitHub integration supports `label_pr` but not GitHub's
`workflow_dispatch` POST endpoint. Instead of weakening the approval gate
or directly operating on an existing HubSpot contact, the workflow accepts a
specific `pull_request: labeled` event on PR #611. Its manual
`workflow_dispatch` path remains supported from `main`.

**Tool path (read-only):**
- Apply GitHub PR label `p27-hubspot-preflight` to #611 using the connected
  GitHub tool. This starts `label-preflight` with **no HubSpot token**, no
  provider request, and no contact mutation.
- Verified initial run:
  [GitHub Actions 42515006667](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42515006667):
  read-only preflight SUCCESS; provider readback job SKIPPED.
- Labels only generate a new `labeled` event when added; if the label already
  exists, remove it before running the preflight again. Do not use the live
  label for ordinary CI/retries.

**Tool path (controlled live acceptance, separate authorization):**
- Configure and independently verify GitHub environment
  `p27-provider-sandbox` on the repository: required reviewer(s) independent
  of the PR author, prohibit self-approval, and a branch/deployment restriction
  compatible with the intended PR-head test. Inspect the environment through
  GitHub's environment API or repository Settings before applying the live
  label; the live dispatch guard independently checks these controls again.
- Put `P27_HUBSPOT_LIVE_TEST_TOKEN` in that environment's secrets, not in
  normal repo variables. Restrict it to the least permissions needed for
  account details and CRM contacts read/upsert/delete. Set
  `P27_HUBSPOT_EXPECTED_PORTAL_ID=343328749` and a dedicated non-public
  `P27_HUBSPOT_QA_EMAIL_DOMAIN` under environment variables.
- Confirm an independent submitted `APPROVED` PR review refers to the
  current exact head SHA. An approval from the repository/PR owner or an
  approval on an earlier SHA **does not qualify**.
- Only then apply `p27-hubspot-live-approved` label to PR #611 via the
  connected GitHub label tool. This triggers GitHub Actions, uses the protected
  environment, and checks actor, repository, PR number, actual checkout
  SHA and currently published PR head **before touching HubSpot**.
- Environment reviewers must approve the actual job deployment. An
  unavailable or improperly configured environment is **not** evidence of
  authorization.
- The existing adapter checks the exact connected HubSpot portal and STANDARD
  account type, constructs one randomized `p27qa...` contact, performs one
  upsert + independent GET + same-key upsert + GET, independently re-verifies
  all synthetic marker properties before DELETE, and requires final GET 404.
  Uncertain result/cleanup always fails and must be reconciled manually,
  never called PASS.
- Successful run uploads an evidence artifact named
  `p27-hubspot-live-verified-<run-id>`, retained seven days. The raw artifact
  includes synthetic contact ID/marker; logs print only a sanitized PASS
  summary. Record the exact run URL and outcome in PR #611 after inspection.

## Hard stops

- Do **not** apply the live label before environment reviewer controls are
  verified and exact-head independent review exists.
- Do not substitute a direct connected-HubSpot write for the approved harness;
  that path does not enforce the same pre-delete ownership check, replay
  proof, and error/cleanup journal.
- Do not use owner approval to substitute for independent review. Do not
  approve production migration or merge solely because the provider smoke
  passes; the 43-finding remediation and QA00–90 release gates are separate.
- No extra Railway/Supabase/Redis/staging infrastructure is needed.
- A successful smoke validates **provider readback and cleanup**, not the
  complete agent → Play → workflow → provider → outbox → consumer journey.

## Code and tests

- Workflow: `.github/workflows/master-qa-p27-sandbox-readback.yml`
- Exact-head/reviewer/evidence guard:
  `backend/scripts/p27_hubspot_dispatch_guard.py`
- One-record provider adapter:
  `backend/scripts/p27_hubspot_sandbox_readback.py`
- No-network negative/contract tests:
  `backend/tests/master_qa/test_p27_hubspot_tool_dispatch.py` and
  `backend/tests/master_qa/test_hubspot_sandbox_readback_contract.py`
- Master QA includes both regression files.

## Current execution evidence and release truth

As of the initial tool-driven implementation, no live HubSpot record has
been created, updated or deleted by this workflow. The GitHub Actions
preflight job has passed with the live provider job explicitly skipped.
Independent review is absent and environment protections were confirmed missing
at the release-gate inspection above. The
implementation changes are only on PR #611, not yet in `main`, and have
not been deployed to Railway.
