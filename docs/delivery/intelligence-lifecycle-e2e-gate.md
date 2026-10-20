# Intelligence lifecycle E2E acceptance gate

The workflow `Intelligence lifecycle E2E acceptance` is **manual and fail-closed**.
It is an evidence verifier, **not yet an automated scenario executor**. Do not
mark full production E2E complete from deployment and anonymous smoke alone.

## Required protected GitHub environment: `intelligence-e2e`

- Environment variable `GRAVITRE_E2E_ORG_ID`: canonical isolated E2E
  organization, never a customer organization.
- Secret `GRAVITRE_E2E_BEARER_TOKEN`: short-lived authorized token with read
  access to the isolated organization. Rotate/revoke after test.
- Secret `GRAVITRE_E2E_EVIDENCE_JSON`: JSON generated from authenticated
  runtime readbacks of the same uniquely traced scenario, not a hand-authored
  array of assertions. It must not contain PII, credentials or provider payloads.

## Scenario to execute in isolated tenant

1. Submit the synthetic frustrated onboarding/customer-renewal message with a
   unique trace identifier. Capture signal, context, sentiment, and selected
   native remedy identifiers and readbacks.
2. Stage the native assignment, verify nothing ran before approval, then approve
   with the authenticated actor. Test wrong actor/org/conversation, modified
   draft and duplicate confirmation against the same bound action.
3. Verify one persisted provider/native write and its independent readback.
   Queue acknowledgment is **not** business completion.
4. Observe real execution and actual verified business metric result. Capture
   the outcome's lineage and the corresponding learning handler delivery row.
   Do not create fictitious production outcomes or turn on previously declined
   feature flags. Capture cross-tenant isolation and negative controls.
5. Serialize the independent identifiers and controls into evidence JSON,
   manually trigger the workflow, inspect the verdict artifact. An absent
   evidence bundle, disabled handler, missing token or any failed condition
   must fail.

## Current limitations

The verifier checks supplied evidence correlations and the live delivery health
endpoint, but cannot independently attest that every statement in the JSON
originated from the production database. A future execution harness must
collect attestable readbacks and invoke the verifier directly. Until then this
is an incremental operator gate, **not a complete authenticated E2E proof**.
