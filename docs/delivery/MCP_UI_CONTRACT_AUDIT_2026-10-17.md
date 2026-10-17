# MCP frontend/backend reconciliation — first-pass audit
Date: 2026-10-17
Status: Source-level inspection; live authenticated verification pending.

## Existing frontend components
- `apps/web/app/(app)/marketplace/connectors/page.tsx`: federated marketplace list through `marketplaceApi.listFederatedConnectors`. **Present**; this is a partner catalog, not evidence of a live MCP server tool inventory.
- `apps/web/components/agents/agent-autonomy-panel.tsx`: agent capabilities, allowed connectors, allowed tool patterns, approval-required actions. **Present and API-backed**; test effective permission updates and MCP tool pattern representation.
- `apps/web/components/runs/execution-timeline.tsx`: step-level `awaiting_approval`, waiting evidence chip and secret-key redaction pattern. **Present**; test whether live MCP provider dispatch, denial and quota events map to its step schema.

## Required contract audit (no assumed missing UI)
| Contract | Frontend evidence | Remaining proof |
| --- | --- | --- |
| Connector catalog | `marketplaceApi.listFederatedConnectors` | Identify actual live MCP server management view, discovery endpoint and access policy |
| Agent tool permission | `agentIdentityApi.get`, `/api/agents/{id}/capabilities`, `/api/capabilities` | Verify allowedToolPatterns, denied writes and effective policies against isolated actor |
| Approval checkpoint | `awaiting_approval` timeline step and evidence chip | Confirm pending→approved/rejected/consumed state refresh and no unauthorized dispatch |
| MCP rate limiting | No server-specific quota presentation established by this audit | Inspect server detail and backend response contract before deciding whether user-facing status is needed |
| Execution outcome | Existing timeline supports step statuses | Compare real MCP tool run, retry, denial and 429/quota response payloads |
| Sensitive values | Secret-pattern redaction in timeline | Test nested payloads and error strings for credential leaks |

## Engineering acceptance
1. Identify exact route, component, fetcher, endpoint and response schema for live MCP server registration, tool discovery, permissions and run events.
2. Run role-isolated read/write/denial/quota tests in disposable smoke organization.
3. Add code only for a confirmed missing field, stale-state bug or broken action; otherwise record NO CODE CHANGE.
4. Require tests for authorization, approval consumption, redaction, rate-limit handling and state invalidation.
5. Preserve Gravitre 3.0 Plus information architecture, existing components and accessibility.

No new frontend UI, backend policy, or production flag is authorized by this audit note.
