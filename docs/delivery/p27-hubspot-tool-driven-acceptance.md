# P27 — Tool-driven, protected HubSpot provider acceptance

**Scope:** one synthetic contact in the existing STANDARD HubSpot portal `343328749`.
**Owning PR:** #611. **Deployment:** none as part of enabling this workflow.
**Separation:** PR #610 owns Voice 3.0; this workflow only verifies HubSpot provider behavior.
**Status:** tool-based read-only preflight has executed successfully; live provider acceptance is **NOT RUN**.

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
  compatible with the intended PR-head test. **The current connector cannot
  inspect environment protection settings**. This must be confirmed in
  repository Settings before applying the live label.
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
Independent review and environment protections remain unverified. The
implementation changes are only on PR #611, not yet in `main`, and have
not been deployed to Railway.
