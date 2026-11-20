# Master QA P0 — 92-workflow source-level audit checkpoint

**Main baseline:** `cf8b95d25a6a70aa5db3b8eef103e6f86786b773`. **Date:** 2026-11-07.
**Scope:** exact source inspection of the 92 YAML files enumerated under `.github/workflows`, **92/92 source-read success**. Machine inventory: [master-qa-workflow-inventory-baseline.json](./master-qa-workflow-inventory-baseline.json). This is not yet a complete runtime, caller, security or cost audit.

## Verified from workflow files

- 92 workflow YAML definitions inspected; zero source-read failures.
- Static source scan finds **38** files containing a PR-trigger stanza, **37** containing a push-trigger stanza, **88** containing `workflow_dispatch` text and **1** containing `workflow_call` text. Counts can overlap, and textual presence is not evidence a job is currently enabled, eligible, or actually run; inspect filters and GitHub workflow-state readbacks before operational changes.
- Source inventory records each workflow's displayed name, event block excerpt, deployment environment declarations and candidate event presence. **Required status checks, reusable callers, histories, averages, secrets, provider cost/egress, actions and owner disposition still require verified follow-up.**
- `railway-backend-production.yml` has a main-push trigger in source and a separate disabled-manually control documented in the #605 release ledger. Source alone must **never** re-enable it.
- Existing branch protection currently protects `main`; do not alter required-check contexts or approvals until mapping is complete. The owner's solo-maintainer policy is distinct from the initially drafted independent-review proposal.

## Engineering triage — candidates, NOT approved retirements

| Priority | Paths / category | Safe disposition today | Required before disposition |
| --- | --- | --- | --- |
| P0 | `ci.yml`, `connector-governance.yml`, `supabase-migration-safety.yml`, `pr605-gate26-postgres-outbox.yml`, `pr605-run-status-contract.yml` | KEEP / INVESTIGATE | Retrieve branch-required check names and historical coverage; no removal |
| P0 | `railway-backend-production.yml`, `production-release-verification.yml`, `auth-config-sync.yml`, `unified-turn-phase2-live.yml`, `unified-turn-phase4-cutover.yml` | KEEP HOLD / INVESTIGATE | Map actual dispatchers, enabled state, deployment privileges, secrets and release operator |
| P0 | `isolated-acceptance.yml`, `run-acceptance-billing.yml`, `run-acceptance-voice.yml` | KEEP / INVESTIGATE | Verify billing test isolation, manually invoked cost, live-speech boundaries |
| P1 | `voice-*.yml`, `conversation-*.yml`, `conversational-product-acceptance.yml` | INVESTIGATE | Map Voice 3.0 V0–V7, duplicated fixtures and device/provider tests |
| P1 | `release1-*.yml`, `milestone*.yml`, `pr587-*.yml` | INVESTIGATE | Discover current callers, historic-only vs active, paid/live endpoints, status references |
| P1 | all remaining workflows | INVESTIGATE | Owners, triggers, side effects, runtimes and actual last meaningful run |

**No existing workflow has been consolidated, retired, disabled, enabled or had triggers/status-check names changed by PR #611.**

## Cross-workstream Tranche 27 evidence

The [23-entry ECO/P27 evidence matrix](./master-qa-tranche27-findings-evidence-matrix.json) maps **ECO-001 through ECO-015** and **P27-01 through P27-08** from existing audit documents to proposed QA lanes, owner areas and expected proof. P27 tests are NOT RUN in production; historical #605 checks do not get promoted to new-head passes.

New first-prototype fixtures: `backend/tests/master_qa/synthetic_fixture_factory.py`, tests `backend/tests/master_qa/test_synthetic_fixture_factory.py`. These are pure offline simulator contracts for deterministic identities, tenant separation, approval, revoked scopes, idempotency, simulated outbox delivery and deny-socket guard. **They are not app integration or database persistence tests.** Status must remain NOT RUN until actual targeted execution completes.

## Next executable gate

1. Audit enabled/disabled state, every `workflow_call` caller, branch protection required-job names, source and scope of secrets, network/provider effects, run counts/average durations and artifacts. Supply verifiable evidence before proposing KEEP/CONSOLIDATE/RETIRE.
2. Run targeted Python tests at exact PR #611 head; repair actual failures. Then wire the fixture to actual authenticated backend execution adapters and temporary PostgreSQL.
3. Expand Tranche 27 ECO records beyond 015 from other governing registers; link proof to implementation SHA and immutable artifacts.
4. Only then design **additive** QA 00–90 orchestration that preserves existing required checks. No paid nightly or live testing without cost/budget approval.

**Safety:** no merge, production deployment, migration, provider write, telemetry enablement, branch-protection change, workflow retirement or secret edits are authorized by this checkpoint.
