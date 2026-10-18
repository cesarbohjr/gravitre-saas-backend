# Backend → Frontend release integration matrix (2026-10-18)

Repository: `cesarbohjr/gravitre-saas-backend`. This is a **code-surface map**, not a certification that each workflow is functional.

| Capability | Backend router/service | Existing frontend route | Implementation state / next contract verification |
| --- | --- | --- | --- |
| MSP customer consent, action grants, revoke, account health | `backend/app/routers/msp_delegations.py`, `backend/app/services/msp_delegated_access.py` | `apps/web/app/(app)/settings/organizations/page.tsx` | Typed client and owner-only, feature-gated limited-scope grant/revoke panel added on this branch. **Not production enabled.** Missing customer-owner grant-list/audit endpoints, provider discovery, and certified live tests. |
| Organization hierarchy and federation | `backend/app/routers/enterprise.py`, `federation.py` | `settings/enterprise`, `settings/federation` | Audit existing controls; never conflate parent-org relationship with customer data permission. |
| Agent identity and delegated tool permissions | `agent_identity.py`, `agent_tool_permissions.py` | `agents`, `agents/[id]` | Confirm identity, trust level, action scope, and approval states are represented accurately. |
| Agent collaboration, swarm, council | `agent_collaboration.py`, `agent_swarm.py`, `agent_council.py` | `agents/swarm`, `multi-agent-run` | Trace each action from UI to router and permission boundary. |
| Workflows and schedules | `workflows.py`, `schedules.py`, `workflow_schedules_internal.py` | `workflows`, `workflows/[id]`, `schedules` | Verify run/edit/pause, schedule and history contracts and failure recovery. |
| Plays | `plays.py` | `plays`, `plays/[key]` | Confirm authority changes and confirmation actions use actual persisted API state. |
| Connector management | `connectors.py`, `connector_oauth.py`, `managed_connector_auth.py` | `connectors`, `connectors/[id]` | Audit provider catalog, OAuth status, permissions, reconnect and credential safety. |
| Human approvals and audit | `audit.py`, agent permissions, execution approval services | `approvals`, `audit`, `settings/approvals` | Verify durable decisions, audit trails and failure states. |
| Intelligence, context, memory, learning | `intelligence_engine.py`, `intelligence_visibility.py`, `agent_memories.py`, `memory_promotion.py` | `intelligence`, `intelligence/memory`, `intelligence/learning`, `intelligence/performance` | Verify data sources, explanation/visibility flags and real model outputs. |
| Voice and text assistant | `voice.py`, `voice_gateway.py`, `pipecat_voice.py`, `assistant.py` | `assistant`, app voice controls | Verify voice routing, consent, streaming latency, and parity of tool approvals with text. |
| Billing, metering, recovery | `billing.py`, `billing_sync.py` | `settings/billing`, `settings/billing-usage` | Validate durable usage, recovery state, invoice reconciliation and permissions. |

## MSP security gate

1. Run `.github/workflows/msp-isolated-database-security.yml` with disposable local Supabase Auth, PostgREST and PostgreSQL.
2. Execute `test_live_authorized_msp_access`: two independently issued provider-user JWTs; deny before consent; customer-owner grant; both permitted on customer A only; customer B denied; grant audit verified.
3. Execute `test_live_cross_session_revocation`: both sessions permitted, owner revokes through FastAPI RPC, **same** JWTs denied on next request, revocation audit verified.
4. Require green backend/web CI and review before merging; separately verify production deployment and controlled smoke test.
5. Do **not** set `MSP_PARENT_ORG_ENABLED` or `NEXT_PUBLIC_MSP_DELEGATION_UI_ENABLED` to true in production merely because tests were added.

## Contract gaps that must not be disguised in UI

- `POST /api/msp/delegations` returns `stored_not_activated`; it does not activate arbitrary customer access.
- `POST /api/msp/delegations/{id}/revoke?customer_org_id=...` is customer-owner gated.
- `GET /api/msp/delegations/customer/{id}/health?provider_org_id=...` is action scoped and feature gated.
- No verified customer-owner grant-list or MSP audit-history GET contract exists yet. A complete administration UI requires those read contracts and accompanying authorization tests.
- A parent relationship alone does not confer membership or customer data access.
