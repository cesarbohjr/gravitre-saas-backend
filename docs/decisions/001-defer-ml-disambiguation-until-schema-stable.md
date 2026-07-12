# ADR 001: Defer ML/embeddings assignee disambiguation until workflow schema is stable

**Status:** Accepted (deferred) — schema-gate closed engineering-only; Memory embeddings closed-for-now  
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

## Reopen proposal (2026-07-12) — pending human sign-off

**Status:** Proposed reopen — **not authorized for Memory Phase 1 until human signs off.**

### Triggers met (evidence)

| Trigger | Evidence |
| --- | --- |
| `PENDING_WORKFLOW_SCHEMA_ALLOWLIST` ≤141 | Observed length **0** — `docs/delivery/adr001-memory-authorization-review.json` |
| `ORPHAN_HANDLER_ALLOWLIST` / `API_IMPORT_EXCEPTION_ALLOWLIST` shrink ≥2 | Observed length **0** each — same review artifact |
| ≥5 priority connectors with multi-field write schemas + assignee/email-style **sensitive** fields | Baseline **NOT MET** frozen in `docs/delivery/adr001-sensitive-schema-audit.json`; after schema flags: HubSpot / Asana / Apollo / Slack / Jira all qualify |

### Schema evidence paths (post-flag)

- Asana `asana.tasks.create` — `assignee` / `due_on` already `sensitive=True` (`action_workflow_schema.py`)
- HubSpot `hubspot.contacts.create` — email-style identity field `sensitive=True` (`action_workflow_schema.py`)
- Apollo `apollo.contacts.create` — email-or-name field `sensitive=True` (`workflow_schemas_batch_25.py`)
- Jira `jira.issues.create` — optional assignee `sensitive=True` (`workflow_schemas_batch_25.py`)
- Slack `slack.post_message` — channel marked `sensitive=True` as entity-resolution analogue (`action_workflow_schema.py`)

### Memory Phase 1 constraint (unchanged)

Embeddings must attach to `WorkflowFieldSpec` only (sensitive / inferrable flags) — **no** parallel one-off heuristics per vendor. Do not implement the embedding index or vector search until this reopen is **explicitly signed off**.

## Human decision (2026-07-12) — schema-gate closed; Memory embeddings closed-for-now

**Category boundary:** The schema-gate criterion being met in code is accepted as **engineering-only evidence**. It does **not** authorize sending customer identity fields (email, assignee, channel) to a third-party embedding provider. Collapsing those claims is the same failure shape as treating backend-only Done as full-path PASS.

| Decision | Outcome |
| --- | --- |
| Freeze schema-gate audit | Closed — `docs/delivery/adr001-sensitive-schema-audit.json` |
| Memory Phase 1 embeddings | **Closed-for-now** on engineering roadmap (not In Progress) |
| Data-handling design | `docs/delivery/memory-phase1-data-handling-design.md` (written) |
| Organizational decision | [STA-312](https://linear.app/staqbot/issue/STA-312) — name data-governance owner; only that unblocks Memory embeddings |
| Reopen when | STA-312 names owner **and** owner selects Option A/B/C in writing |
| STA-305 / STA-309 / STA-310 / STA-311 | Unaffected; remain closed |
| Unblocked next eng | Knowledge Phase 2 ([STA-313](https://linear.app/staqbot/issue/STA-313)), Recommendation heuristics ([STA-314](https://linear.app/staqbot/issue/STA-314)), maxDuration residual ([STA-315](https://linear.app/staqbot/issue/STA-315)), stale title ([STA-308](https://linear.app/staqbot/issue/STA-308)) |

Until STA-312 is resolved, **no Memory embedding code**. That pause may last indefinitely; that is correct.
