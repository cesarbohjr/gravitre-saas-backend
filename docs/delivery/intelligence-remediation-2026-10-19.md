# Intelligence acceptance remediation

Baseline: `1112c4dc0363b35a30167a94525d46a0a31534aa`.
Reproduced production conversation: `cd587a3a-6a7e-4818-9aaa-a1d954f02c6c`.
Trace marker: `ACC-20261019-2344`; isolated org: `f07e57c0-1501-4000-8000-c04e57a00001`.

## Changes

- Keep authenticated ReAct requests at user instruction priority. Retrieved content and tool observations retain their external-data fences; backend authorization and approval gates remain authoritative.
- Require the model to stage a governed write before presenting an approval request. Recognize `Approve` in the shared confirmation vocabulary without accepting edits as confirmations.
- Let a new single-connector request reach the governed connector path after an old orchestration is blocked. Active orchestration approval gates retain ownership.
- Route affirmative clauses rather than prohibitions or trace/reporting instructions. Email fields are not Gmail requests. Preserve quoted payloads and extract arguments from the original request.
- Recognize every accepted required-field alias before invoking model extraction (e.g. Slack `message` or `text`). Bound optional extraction to three seconds and retain known arguments on timeout.
- Fix unreachable uncertainty adaptation, phrase-boundary matching, and false urgency/frustration on ordinary “today” / “again” requests. Sentiment continues to affect presentation only.
- Recover nonempty partial responses only for the identical persisted message and prompt. Ignore late recoveries after a conversation or turn change, and clear transport errors after successful recovery.
- Scope intelligence caches by organization and avoid retaining another organization's snapshot while loading.
- Add member-authorized `GET /api/admin/intelligence/outcomes/delivery`: effective flags, registered handler, tenant-filtered queued events and count. The Intelligence page distinguishes paused/queued delivery from actual verified learning.

No new customer prices, toggles, or capability claims were added. The delivery notice is explicitly requested diagnostic behavior, backed by the native endpoint. No schema or billing changes.

## Local verification

- Web full suite: 291 files / 1,870 tests passed, including the tenant-switch regression.
- Web TypeScript and production build passed. Changed-file lint: zero errors (existing warnings remain).
- Chat-surface drift guard passed.
- Backend targeted suites passed: orchestration, connector mapping, ReAct, approval identity binding and duplicate protection, guardrails, model router, tenant access, context compilation, source lineage, replay and learning handler. Batches overlap; their totals must not be summed as unique tests.
- Full backend suite: incomplete. It progressed beyond 20% with no reported failures before automatic approval review blocked further execution because unmocked tests may send repository or test data to api.openai.com. Do not retry that execution path or trigger the same suite indirectly without explicit authorization. Targeted regression results remain valid; this is not a full-suite PASS.

## Production acceptance still required

This document is not an end-to-end PASS. Use a fresh authenticated conversation in the isolated org, create a uniquely labelled synthetic proposal, approve the exact pending action, verify exactly one provider write, and correlate its new run/event with `outcome_learning.record_run_outcome` in `delivered_handlers` and runtime logs. Confirm learning records only for verified business results, never from successful API delivery alone. Verify chat and voice paths independently, plus wrong-tenant/actor/conversation denial, changed-draft reapproval, and duplicate confirmation behavior.

`OUTCOME_LEARNING_HANDLER_ENABLED=true` was staged in Railway patch `db6f4b1c-39d9-4dec-b98f-9ed70460fd5d`; its earlier deploy request was declined. Do not bypass that decision or report the staged setting as live. Inspect the native delivery endpoint after deployment to establish the effective state.
