# ADR 001: Defer ML/embeddings assignee disambiguation until workflow schema is stable

**Status:** Accepted (deferred)  
**Date:** 2026-07-07  
**Context:** Connector chat execution (Phases A–D), registration contract shrink work

## Decision

Defer ML/embeddings-based assignee and entity disambiguation until declarative `workflow_schema` coverage is stable across a meaningful slice of priority write actions.

## Rationale

1. **Schema-first governance is the bottleneck.** Parameter inference, validation, and approval copy all key off `ActionWorkflowSchema`. Shipping embeddings before schemas are stable would disambiguate into fields we cannot yet validate or present consistently.
2. **Current path is sufficient for v1.** Rule-based inference (`connector_parameter_inference.py`), session entity binding (`connector_session_state.py`), and explicit assignee resolution (`resolve_assignee_disambiguation`) cover the two schema-backed actions today (`asana.tasks.create`, `apollo.lists.create`).
3. **Same shrink pattern applies.** The registration contract tracks `PENDING_WORKFLOW_SCHEMA_ALLOWLIST` (166 write actions). Revisit ML disambiguation when that list has materially shrunk — target **N ≥ 25** priority write actions with schemas across HubSpot, Asana, Apollo, Slack, and Jira — not when individual connectors are patched ad hoc.
4. **Avoid repeating the “166 at once” mistake.** Embeddings should attach to schema field specs (`WorkflowFieldSpec.inferrable`, sensitive flags), not parallel one-off heuristics per vendor.

## Revisit trigger

Re-open this ADR when **all** of the following are true:

- `PENDING_WORKFLOW_SCHEMA_ALLOWLIST` has shrunk by at least 25 entries from baseline (166 → ≤141) via batched schema migrations (Step 3).
- At least 5 priority connectors have multi-field write schemas with assignee/email-style sensitive fields.
- Registration contract Step 1 allowlists (`ORPHAN_HANDLER_ALLOWLIST`, `API_IMPORT_EXCEPTION_ALLOWLIST`) have each shrunk by ≥2 entries without regressions in scoped CI.

## Consequences

- **Now:** Continue rule-based disambiguation; document ambiguous cases in approval messages.
- **Not now:** No embedding index, no vector search over org users/contacts for chat parameter fill.
- **When reopened:** Design embeddings as a pluggable resolver behind `WorkflowFieldSpec`, with fallbacks to today’s rules and explicit low-confidence approval UX (already wired in Phase D).

## Related work

- `backend/app/services/connector_registration_contract.py` — allowlist shrink tracker
- `backend/app/services/connector_parameter_inference.py` — context-aware inference (Feature 1)
- `backend/app/connectors/action_catalog/action_workflow_schema.py` — declarative schemas
- Scoped CI: `.github/workflows/connector-governance.yml`
