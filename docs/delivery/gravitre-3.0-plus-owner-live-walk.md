# Gravitre 3.0 Plus — owner-live walk (acceptance gate)

OWNER_LIVE_ACCEPTANCE = **NOT_RUN**. MERGE_READY = **NO**.

Branch `feat/gravitre-3.0-plus-frontend`. Preview: the Vercel Preview for the final branch SHA (see the delivery message).
Only Cesar's real signed-in owner session counts. Fixture, `/e2e/*`, `/dev/*` and harness routes are not owner-live proof.
Sign-in: Cesar's existing email/password owner account. No new account, bypass, credential change or saved browser storage.

## How to record

For each row, record the result, the evidence (time + what was seen, request id or run/conversation id when shown), and, if it fails, one classification:

- FRONTEND WIRING DEFECT
- CORE/API DEFECT
- AUTH/SESSION DEFECT
- DATA AVAILABILITY (the org genuinely has no such data; the surface says so honestly)
- EXTERNAL CONNECTION STATE (depends on a vendor connection that is absent or unhealthy)

Defects are fixed from canonical state only. No local mock logic.

## Per-route checks (apply to every row)

1. Real organization data appears (or an honest empty / not-connected / not-measured state).
2. Navigation in and out works; deep links reload correctly.
3. No fixture or demo state leaks (e.g. "Customer Data Pipeline", sample agents, invented percentages).
4. No stale or deprecated endpoint (browser Network tab: no 404/405 on `/api/*`).
5. Ask Gravitre opened from the surface carries the surface's context.

## Walk

| # | Surface | Route | Surface-specific check | Result | Evidence | Classification |
|---|---|---|---|---|---|---|
| 1 | Dashboard | `/home` | KPIs come from real org data; 1h/24h show the "last 7 days" note; admin cards load for owner | | | |
| 2 | AI Workspace | `/ai` | A prompt streams token by token; a read action returns a canonical artifact (table/report renders); a write prepares an approval and does not run silently | | | |
| 3 | Assignments | `/assignments` | Real jobs; open one; state matches the backend | | | |
| 4 | Agents | `/agents` | Real org agents; run counts match backend | | | |
| 5 | Agent Detail | `/agents/{id}` | "Total runs" (not "Tasks today"); Autonomy panel shows recorded policy only, never promises unattended writes | | | |
| 6 | Approvals | `/approvals` | Pending items match governed runtime (approve/reject only on a safe, owner-chosen item) | | | |
| 7 | Workflows | `/workflows` | Real list, run counts, last run, success rate "—" when no runs | | | |
| 8 | Workflow Builder | `/workflows/new/builder` and an existing workflow | New starts empty (no mock graph); connector steps show real connection state; catalog actions validate | | | |
| 9 | Connectors | `/connectors` | Connection status matches reality; action catalog loads | | | |
| 10 | Sources | `/sources` | Real sources and ingestion state | | | |
| 11 | Intelligence | `/intelligence` | No invented state; empty areas say so | | | |
| 12 | Marketplace | `/marketplace/assets` | Real listings; no working Enable/price that is not authorized | | | |
| 13 | Model Studio | `/intelligence/model-studio` | Real models/registry; no invented metrics | | | |
| 14 | Governance | `/settings/approvals`, `/audit` | Approval policies as stored; audit rows are real org events | | | |

## Cross-cutting checks

| Check | Result | Evidence |
|---|---|---|
| Artifacts render from canonical `execution_result` data (not client-built) | | |
| Workflow run state matches backend execution state (run page vs Activity) | | |
| Approvals reflect governed runtime state (an approval prepared in AI Workspace appears in Approvals) | | |
| Agent permissions match canonical backend identity/trust record | | |
| Connector capability state matches actual connections and the action catalog | | |
| Ask Gravitre preserves the current surface context | | |
| AI streams correctly (no stalled or duplicated stream) | | |
| One `/api/chat` request per question (DevTools Network tab) | | |
| Sidebar navigation Marketplace → Workflows and Agents → Assignments land promptly | | |
| Intelligence leaves "Loading intelligence" within a couple of seconds after sidebar navigation | | |
| Intelligence map renders for an org with a knowledge graph (CI fixture org has none, so CI cannot prove it) | | |
| No 403 on `/api/meson/insights` in the console on `/agents` or any page (fallback now only for Control+ tier) | | |

## Gate

OWNER_LIVE_ACCEPTANCE becomes PASS only when every row is PASS or honestly classified DATA AVAILABILITY / EXTERNAL CONNECTION STATE, and no FRONTEND WIRING, CORE/API or AUTH/SESSION defect remains open.
