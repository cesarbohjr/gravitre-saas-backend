# Phase 0 — Platform Health / Workflow Intelligence Pack (self-signal)

**Date:** 2026-07-16  
**Mode:** Spec locked for Phase 1 build (self-signal; zero new external connectors)  
**Sequence:** After STA-321 (auto agent selection). Marketing (#6) may proceed in parallel. Canvas node expansion / planner-convergence stay behind.

---

## Goal

Installable marketplace intelligence pack that points Signal / KPI / Recommendation engines at **Gravitre’s own** `audit_events` + workflow run / approval history — approval latency, step failures, flaky connectors, stalled workflows.

**Tone (locked):** quantified ops impact, e.g. “Approval delays are adding **2.4 days** to the median governed write…”

---

## Identity

| Field | Value |
|--------|--------|
| **pack_id / slug** | `platform-health-intelligence-pack` |
| **title** | Platform Health / Workflow Intelligence Pack |
| **department** | `platform` |
| **default_subdomain** | `workflow_reliability` |
| **tier** | `starter` |
| **tags** | `platform`, `ops`, `self-signal`, `intelligence-pack`, `workflow-health` |
| **External connectors** | **None** — vendor label `gravitre_platform` (internal tables only) |

Not the Workflow Intelligence builder drawer. Not Business OS (#12) rollup.

---

## Framework reuse

Mirror **Customer Success** pack (internal-only stop-lines), not Executive (FRED/SEC):

- Catalog → seed → demo install → PackKpiPanel → tip smoke
- Reuse `integration_health_score_service` (STA-124) + `connector_ops_metrics_service` aggregates
- Tip action: `platform.health.snapshot` (read-only; notification cohesion via `emit_pack_source_notification`)

---

## Signals (v1)

| id | Detect | Severity |
|----|--------|----------|
| `platform.approval_latency_elevated` | approval p95 > 24h | high |
| `platform.step_failure_rate_elevated` | step_failed rate > 8% (n≥20) | high |
| `platform.flaky_connector` | vendor tool.invoke fail rate > 10% (n≥10) | high |
| `platform.stalled_workflow` | pending_approval / non-terminal > 48h | medium |
| `platform.connector_auth_churn` | ≥3 connector.auth.failed / type / 7d | medium |

---

## KPIs

| KPI | Source |
|-----|--------|
| `approvalP95Days` | STA-124 approval latency |
| `pendingApprovals` | `workflow_runs.status=pending_approval` |
| `stepFailureRate` | audit step_failed / completed |
| `flakyConnectorCount` | connector_ops spikes |
| `stalledRunCount` | aged non-terminal runs |
| install / agent / workflow counts | shared `pack_kpi_summary` |

---

## Recommendation templates

| id | Example |
|----|---------|
| `rec.approval_sla` | “Approval delays are adding **2.4 days** to the median governed write (p95). Clear the oldest pending approvals or raise approver coverage.” |
| `rec.flaky_connector` | “`{vendor}` failed **18%** of invokes this week (n={n}). Re-auth or quarantine before the next batch.” |
| `rec.step_failures` | “Step failures are elevated on `{workflow_name}`. Fix the step or add a dry-run gate.” |
| `rec.stalled_runs` | “**{count}** runs stalled >48h awaiting approval.” |
| `rec.auth_churn` | “`{connector_type}` hit auth failures **{n}×** in 7 days.” |

---

## Install entities

| Entity | Spec |
|--------|------|
| Agent | Platform Reliability Analyst — `permitted_tools: ["platform"]`, guardrails `read_only_platform_telemetry`, `no_external_enrichment` |
| Workflow | Platform Health Snapshot — single `invoke_tool` `platform.health.snapshot` |
| Assignments | audit-events-telemetry, workflow-run-history, approval-latency-rubric, connector-ops-playbook |
| Connector template | **Omit** |

---

## Stop-lines

1. No HubSpot / Zendesk / FRED / GSC staging for this pack  
2. No new OAuth / BYO vendor  
3. No Memory/KG write of third-party PII  
4. Do not expand into Business OS rollup  
5. Do not confuse with Meson / canvas Workflow Intelligence drawer  

---

## Evidence bar (Phase 1 done)

1. Install demo bundle → `agentId` + `workflowId` + assignments ≥ 1  
2. Tip invoke `platform.health.snapshot` → success + structured KPIs + recommendations  
3. Notification cohesion (title/url tied to invoke)  
4. `pack_kpi_summary` for pack_id shows installed + health dimensions when history exists  
5. Reports UI tab / PackKpiPanel  
6. Artifact: `docs/delivery/phase4-platform-health-pack-live.json` with tip SHA  

---

## Phase 1 file list

| Create | Mirror |
|--------|--------|
| `backend/app/marketplace/intelligence_packs/platform_health_install.py` | `cs_install.py` |
| `backend/app/services/platform_health_tools.py` | thin tip executor |
| `backend/tests/marketplace/test_platform_health_pack.py` | `test_cs_pack.py` |
| `scripts/smoke-phase4-platform-health-pack-live.py` | CS smoke |
| `docs/delivery/phase4-platform-health-pack-live.json` | smoke output |

| Modify | Change |
|--------|--------|
| `catalog.py` | Add spec |
| `service.py` | Dispatch install |
| `shared/kpis.py` | PACK_VENDOR_MAP + optional health fields |
| `tool_service.py` | Register executors |
| `agent_tool_permissions.py` | `platform` demo scopes |
| `apps/web/.../reports/page.tsx` + `surface-copy.ts` | Tab + panel |
| pack count tests | 11 → 12 |
