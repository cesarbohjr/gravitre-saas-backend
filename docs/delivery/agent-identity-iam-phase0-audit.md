# Phase 0 — Agent Identity IAM permission-model audit (2026-09-03)

**Status:** Migration **APPLIED** 2026-09-03 (`agent_identity_iam`, prod ledger
`20260903215253` / `20260903215303` — duplicate stamp from tooling, schema
verified via `to_regclass`). Code deployed at `56af0d17`. Ops smokes **NOT RUN**
locally — `INTERNAL_API_SECRET` not available in this session; run
`scripts/verify-agent-identity-spend-limit-live.py` and
`scripts/verify-agent-delegation-live.py` from an operator env for live PASS.

## Existing permission dimensions

| Dimension | Storage | Enforcement |
|-----------|---------|-------------|
| Org membership | `organization_members.role` | RLS + `require_org_member` / `require_admin` |
| Department scope | `department_members`, `department_resource_assignments`, `agents.department` (text) | `resolve_seat_context`, Lite USE filters |
| Lite USE vs CONFIGURE | Seat context + entitlements | Meson/voice/workflow gates |
| Write authority | `catalog_write_authority` → `react_write_gate` | ReAct + chat confirm |
| Human HITL | `hitl_policies` | `HitlPolicyService.resolve` |
| Agent tool scope | `agent_tool_permissions` | `assert_agent_tool_permission` |
| Operator spend (not agent) | `operators.auto_run_max_*`, `operator_autonomous_usage_daily` | `autonomous_budget_service` |

## Gap filled (this ship)

| Component | Path |
|-----------|------|
| Identity record (1:1 agent) | `agent_identity_records` migration |
| Daily agent usage | `agent_identity_usage_daily` |
| Delegation grants | `agent_delegation_grants` |
| Service + enforcement | `backend/app/services/agent_identity_service.py` |
| Write-gate hook | `react_write_gate.block_react_write_execution` (+ `agent_id`) |
| Admin API | `backend/app/routers/agent_identity.py` |
| Admin UI | `AgentIdentityGovernanceCard` on `/agents/[id]` Governance tab |
| Ops smokes | `/api/internal/ops/agent-identity-spend-smoke`, `agent-delegation-smoke` |

## Attachment point

Primary FK: `agent_identity_records.agent_id` → `agents.id`. Enforcement reuses `react_write_gate` and HITL — **not** a parallel permission engine.

## Verification

```bash
cd backend && python -m pytest tests/services/test_agent_identity_service.py tests/services/test_react_write_gate.py -q
python scripts/verify-agent-identity-spend-limit-live.py
python scripts/verify-agent-delegation-live.py
```

Evidence bar: ops smoke `PASS` with prod `git_sha` + `audit_events` row for `agent.identity.spend_limit_blocked` or `agent.delegation.granted`.
