# Frontend handoff — `GET /api/capabilities` + WRITE governance

Date: 2026-09-28. Core hold exception: capability seam + autonomy reconciliation only.

## Contract

`GET /api/capabilities`

- Auth: Bearer JWT (`get_current_user`) + org member (`require_org_member`).
- Tenant: `X-Org-Id` / org context. 401 without auth, 403 without org membership.
- Mutation: none. Does not refresh OAuth tokens.
- Body is one composed snapshot. It is **not** a second ActionSpec catalog, connector registry, agent registry, workflow runtime, or policy engine.

### Labels (derive from runtime, do not invent)

| Label | Meaning |
|---|---|
| `READ ONLY` | `trust_level=read_only` |
| `ACT WITH APPROVAL` | default, including **no HITL rows** |
| `ACT WITHIN POLICY` | unattended WRITE authorized for **this** agent/context: `trust_level=autonomous` **and** `approval_rule_overrides.write=auto_run`, and no covering HITL policy. F1 / high-risk WRITE never this label. |

`governance.noHitlPolicyMeans` is always `"ACT WITH APPROVAL"`.

Per-action fields:

- `access`: catalog WRITE vs READ (`catalog_action_requires_write_approval`)
- `requires_approval` / `catalogRequiresWriteApproval`: catalog classification
- `runtimeRequiresUserApproval`: org snapshot defaults WRITE → true (PendingAction / confirm). Actual unattended exception is agent-scoped via identity, not “no policy”.

### Duplicate settings (do not merge in UI)

1. `hitl_policies` — covering policy → approval.
2. `agent_identity_records.trust_level` + `approval_rule_overrides` — invoke_tool / ReAct.
3. `operators.execution_mode` + `auto_execute_trusted_scopes` — **workflow** auto-execute only.
4. Intelligence `execution_mode_service` — **post-run label**, not a gate.

Frontend should show (1)+(2) as effective invoke autonomy. Show (3) as workflow auto-execute. Do not OR them into a third “autonomous” toggle.

## Do not implement from this snapshot

Play schema, OutcomeEvent, dashboard templates, datasets, Hugging Face.
