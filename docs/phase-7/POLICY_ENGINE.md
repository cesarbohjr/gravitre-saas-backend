# Phase 7: Policy Engine (Declarative Governance)

## Current Architectural Limitation
- Approval floor and connector restrictions are enforced directly in routers.
- Governance rules are scattered across execute and policy helpers.

## Target Architecture
- Central policy evaluation `evaluate_policy(context) -> Decision`.
- Single place to enforce approval floor, connector restrictions, step limits, and environment rules.

## Minimal Implementation Plan
- Add `backend/app/policy/engine.py` with `PolicyContext` + `PolicyDecision`.
- Execute endpoint calls `evaluate_policy` before run creation.
- Preserve existing policy resolution (workflow/org default) and approval gating logic.

## Required Migrations
- None.

## Integration Changes
- Execute endpoint now:
  - resolves base approvals
  - evaluates policy engine
  - applies approval floor if required
  - denies execution with consistent status codes

## Risks
- Policy defaults must remain non-breaking (limits disabled unless configured).
- Environment policies must align with multi-environment model (Phase 7 Workstream #3).

## Future Scaling Notes
- Add org-level policy config storage (e.g., per-org connector allowlists).
- Add scheduled policy audits and policy versioning.
