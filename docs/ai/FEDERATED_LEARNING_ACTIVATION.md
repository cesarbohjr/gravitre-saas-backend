# Federated Learning — Architecture & Activation Requirements

Status: **DISABLED** (Wave A+B domain intelligence does not activate cross-tenant learning).

## Purpose

`FederatedLearningCoordinator` (`backend/app/ml/federated_learning.py`) is a scaffold for privacy-preserving, cross-tenant signal aggregation. It must remain inactive until all activation gates are met.

## What may be aggregated (when enabled)

- Routing effectiveness weights (segment-level, anonymized)
- Recommendation quality scores (aggregated metrics only)
- Model improvement deltas (gradient/statistical aggregates)
- Behavioral pattern frequencies (non-content signals)

## What must never leave a tenant

- Customer documents and file contents
- CRM records, tickets, or message bodies
- PII, credentials, or private business data
- Raw prompts or model outputs

## Activation requirements (ALL required)

1. Legal review and customer consent mechanism documented and deployed
2. Federated learning runtime (e.g. Flower or equivalent) provisioned
3. Differential privacy implementation validated
4. Secure gradient / signal aggregation protocol audited
5. Minimum participating org threshold (100+) met
6. Explicit product/compliance sign-off recorded in Linear

## Current behavior

- Each org's models and learning segments train only on that org's data
- `FederatedLearningCoordinator.predict_structured()` returns `status: disabled`
- Domain intelligence segment keys and outcome logging are **org-scoped only**

## Related scaffolds

- `MetaLearningAdaptor` (`backend/app/ml/meta_learning.py`) — PLANNED, same privacy prerequisites
- `OutcomeLearningService` — active, tenant-isolated
- `StrategyPerformanceLedger` — active, org-scoped bandit segments

## Enabling (future)

1. Complete activation checklist above
2. Set catalog status to TRAINED only after infra + legal gates
3. Feature-flag cross-tenant aggregation in `FederatedLearningCoordinator`
4. Append activation record to this document with date and approver
