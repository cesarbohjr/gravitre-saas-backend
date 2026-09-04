# Agent Collaboration Layer — Phase 0–4 delivery (2026-09-03)

## Pre-flight

- Standing regression battery (council / swarm / handoff / observability / capability / identity): **54 passed** locally before build; collaboration suite + regressions **36 passed** after build.
- Prior CI tip failure `33819358795` was **Dependency audit `ERR_SOCKET_TIMEOUT`** (registry flake), not council/swarm regressions. Department Eval Suites on the same SHA: **success**.

## Phase 0 — Audit (real)

### Architecture

Three stacks already exist (not one bus):

| Stack | Role | Path |
|-------|------|------|
| Council | Sequential cross-exam + vote/synthesis on shared options | `council_service.py` |
| Swarm | Parallel subtasks → council aggregate | `swarm_coordinator_service.py` |
| Workflow handoff (STA-17/18) | Source agent → structured briefing → receiver | `handoff_service.py` |

**Gap closed this pass:** workflow handoff terminated at the receiver. Collaboration layer adds ranked context, response contracts, and **originator reconciliation** (Finance response feeds back into Marketing).

### Production reachability (measure before building)

Queried prod Supabase `smyeexlrqdpymwjmgzqu` 2026-09-04:

| Signal | Total | Last 30d |
|--------|------:|---------:|
| `agent_councils` | 19 | **10** |
| `agent_swarm_runs` | 30 | **0** |
| `agent_handoffs` | **0** | **0** |
| `audit_events` `swarm.started` | 30 | last seen 2026-07-20 |
| `audit_events` `swarm.aggregated` | 7 | last seen 2026-07-20 |
| Council `audit_events` | none (councils persist to `agent_councils` only) | — |

Honest read: council still fires (~10/30d). Swarm is quiet. Structured `agent_handoffs` had **never** been used in prod before this layer.

### Capability ontology

Reuse only: `backend/app/capability_ontology/resolver.py` (`resolve_capability`). Collaboration does **not** add a second resolution layer. Proposed writes still cite `catalog_write_authority` + `react_write_gate` + `agent_identity_service`.

## Phase 1 — Internal structured handoff (shipped)

- Service: `backend/app/services/agent_collaboration_service.py`
- API: `POST /api/agent-collaboration/handoff` (`agent_collaboration.py`), Command tier, **internal only**
- Object: originating/receiving agents + departments, task, ranked context (Context Engine), response contract (`agree|challenge|revise`)
- Feedback: receiver → originator reconciliation pass
- Persistence: reuses `agent_handoffs` + audits:
  - `agent.collaboration.handoff.created`
  - `agent.collaboration.receiver.completed`
  - `agent.collaboration.reconciled`
- Write authority: receiver/originator execute via `run_agent_task` → `AgentIntelligence` → same gates; proposed catalog actions evaluated via shared `invoke_action_requires_write_approval`

## Phase 2 — Finance challenges Marketing (tests + probe)

- Pytest: `tests/services/test_agent_collaboration_service.py`
  - CAC scenario: Marketing 4.2% → Finance **challenge** on 2.6% → Marketing **revise**
  - Visible disagreement trail (`disagreement_visible=True`, label `Marketing → Finance`)
  - **Mutation proof:** stripping `healthcare_hist` from ranked context fails `assert_ranked_context_preserved`
- Probe script: `scripts/verify-agent-collaboration-cac-live.py` (honestly labeled probe-derived LLM stub; real handoff/audit writes when service role available)

### Live probe evidence (probe-derived LLM stub; real DB writes)

| Field | Value |
|-------|-------|
| Verdict | **PASS** |
| `handoff_id` | `a7c7e178-f746-436a-a339-d91502a997d8` |
| Agents | `fbfa6e92…` → `1d556b8e…` (distinct) |
| Label | `Marketing → Finance` |
| `agent.collaboration.receiver.completed` | `2026-09-04 00:30:33.192492Z` stance=`challenge` disagreement=`true` |
| `agent.collaboration.reconciled` | `2026-09-04 00:30:33.40163Z` |
| Artifact | `docs/delivery/agent-collaboration-cac-probe-live.json` |
| Live backend at probe | `git_sha=1b95aa7a…` (includes collaboration commit `b2ed7d30`) |
| Collaboration ship SHA | `b2ed7d3012f5ccc54e64de9fc55569ae6d50b450` confirmed on Railway after deploy |

## Phase 3 — Observability

- `run_observability_service._handoffs_from_audit` now includes collaboration audits with `label`, departments, stance
- UI: `run-observability-console.tsx` **Agent collaboration** list shows `Marketing → Finance` (not buried as opaque run noise)

## Phase 4 — EXTERNAL A2A (diagnosis only — NOT BUILT)

**Do not build without Cesar's separate sign-off.**

Safe external A2A would require, at minimum:

1. **Authentication / identity** — cryptographic agent identity (mTLS or signed Agent Cards), org allowlist, revocation. An external agent is an **untrusted actor by default** — different trust boundary than internal council members.
2. **Content / authority separation** — external output treated as **data, not instruction** (same discipline as Prompt B security gateway / untrusted tool content). No privilege inheritance from the calling Gravitre agent.
3. **Write / trigger governance** — explicit policy of what an external agent may request vs execute; every proposed write still through catalog write-authority + HITL; default deny for spends, messaging, CRM mutations.
4. **Discovery** — if adopting Agentic Resource Discovery / Google A2A patterns, discovery ≠ authority; capability ads must map through **existing** capability ontology, not a parallel catalog.
5. **Observability** — distinct `trust_boundary=external` audit trail; never collapse into internal `Marketing → Finance` labels.
6. **Existing near-miss (not A2A)** — B2B federation handoffs (`b2b_handoff_service.py`) are Gravitre↔Gravitre org briefings, not Google A2A. Do not confuse them.

Schema already **rejects** `trust_boundary=external` on `CollaborationTaskHandoff`.

## Lessons carried

- Class A: extend shared handoff + write-authority helpers, not one-off call sites
- Organic vs probe-derived: volume numbers are organic SQL; CAC disagreement trail in CI is unit-proven; live probe is explicitly labeled probe-derived until organic traffic exists
- Fix shared helper (`_handoffs_from_audit`, collaboration service), not only UI

## Authorization declaration (customer surfaces)

No new customer-facing prices, badges, Enable toggles, or capability claims invented. API is internal Command-tier operator surface.
