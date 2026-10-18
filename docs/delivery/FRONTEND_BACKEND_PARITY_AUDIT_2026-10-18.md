# Frontend-to-backend parity audit — 2026-10-18

This document records inspected code paths on `main` and changes in PR #502. It does not certify production functionality.

| Area | Existing frontend verified in source | Backend contract / UI gap | Change in this branch | Remaining acceptance |
| --- | --- | --- | --- | --- |
| Agents | `/agents/[id]` Governance tab includes `AgentIdentityGovernanceCard`, `AgentAutonomyPanel`; `/multi-agent-run` uses `agentSwarmApi` and real roster agents | `GET/PUT/DELETE /api/agents/{agent_id}/tool-permissions` existed but no agent-specific permission management UI was found in the detail tab | Typed permission client; explicit active-connector selection; expiring scopes; list, grant and revoke; 204-safe handling and tests | Real org-admin grant/revoke and non-admin denial E2E; review wildcard scope and connector catalog semantics |
| Workflows | `/workflows` already calls `workflowsApi.execute`, `workflowsApi.update` and refreshes list every 60s | Confirm run detail, approvals, retry and cross-view invalidation | No redundant workflow screen added | Real execute → approval → completion/error run tests |
| Plays | `/plays` already has board/table/cards, backend authority changes, and `playsApi.impact` | Impact was not focus-refreshed or refreshed after authority changes | Refresh verified impact on focus, every 60s, and after authority change | Confirm authority and impact responses agree with backend truth |
| Schedules | `useSchedules` prefers unified `/api/schedules`, marks legacy coverage unknown | Hook did not revalidate on focus or poll | 30s polling, focus and reconnect revalidation | Verify cross-session pause/resume and run-status propagation |
| Connectors | `/connectors` already has provider catalog, OAuth/reconnect, sync, connection test, managed auth | Connector list SWR did not revalidate on focus | 30s polling and focus/reconnect revalidation | Verify OAuth callback, expiry, reconnect and permission boundaries |
| Intelligence | `/intelligence` already uses canonical `useIntelligenceSnapshot`, trust, outcomes, connectors and memory candidates; learning and impact pages exist | Canonical snapshot hook did not revalidate on focus | 120s polling and focus/reconnect revalidation | Verify context/sentiment claims against actual evidence, flags, privacy, and freshness |
| Voice / chat | Shared `buildDuplexControls` is used to forward voice controls across chat surfaces | Supported check only tested presence of `navigator.mediaDevices`, not actual `getUserMedia` | Require functional microphone capture API; add capability and playback tests | Live duplex, interruption, tool approvals, voice/text parity and latency instrumentation |
| Governance | `/approvals` uses `approvalsApi.approve/reject`, pending/history polling and cross-view invalidation; `/audit` displays backend evidence | Audit logs and summary were not refreshed on focus | Audit 60s, summary 120s, focus/reconnect revalidation | Approve/reject idempotency, permissions and audit evidence E2E |
| Billing | `/settings/billing` uses overview, invoices, portal, voice top-up and subscription actions | Overview and voice access did not refresh on focus | Billing overview 120s, focus/reconnect; voice access focus/reconnect | Durable recovery and reconciliation must use authorized billing backend, not unverified client-derived totals |

## Release gates

- PR #502 is an isolated **draft**; PR #501 (MSP) remains independent.
- Never infer that UI availability confers backend authority. Server-side org membership, scopes, human approvals and audit remain authoritative.
- Run web lint, typecheck, build and tests, shared text/voice gate and backend tests.
- Review behavior with real authenticated sessions before merging; do not enable disabled production flags.
- Do not describe frontend parity as complete until all E2E acceptance checks above are recorded.
