# Phase 5 — Reporting / insights honesty inventory

Extend the same honesty bar already enforced for BusinessOutcome / Module C /
Phase 4 degeneracy to **every** reporting surface — not only Activity/Outcomes.

## Inventory (canonical)

| id | Route | Source of truth | Honesty notes |
|----|-------|-----------------|---------------|
| activity_outcomes | `/activity` | `workflow_runs` → BusinessOutcome projection | Live per request |
| intelligence_hub | `/intelligence` | outcome events + `runtime_status` | Prefer runtime over catalog TRAINED |
| metrics_ops | `/metrics` | `workflow_runs` / connectors | Ranges **7d\|30d\|90d** only; provenance `live_runs` |
| intelligence_reports | `/intelligence/reports` | outcome events + pack KPIs | Hours/Revenue/Cost = `not_configured` |
| admin_intelligence | `/intelligence/learning` | audits + outcomes + evaluations | Golden signals from live audit |
| golden_signals | learning panel | `audit_events` unified_turn | Live scan |
| built_in_models | `/intelligence/models` | catalog + artifact runtime | Split TRAINED vs `runtime_status` |
| agents_hub | `/agents` | outcomes preferred; else stored | **Never default 100% with 0 runs** |
| lite_results | `/lite/results` | `workflow_runs` | Live |
| pack_kpis | reports pack tabs | installs + signals + cache | Cache TTL disclosed via pack service |
| enterprise_workforce | `/settings/enterprise` | jobs/audit counts | Sparklines labeled illustrative |
| marketplace_analytics | `/marketplace/analytics` | usage; ROI estimates labeled | Estimates ≠ outcomes |

## Fixes shipped this phase

1. Agent BFF + operators legacy map: withhold success rate when no evidence
   (`successRateSource=insufficient_data`); no invented 100%.
2. Metrics UI: drop invalid `1h`/`24h` ranges; default `7d`.
3. Reports ROI: Hours/Revenue/Cost always `measurement_status=not_configured`.
4. Agent skill bars: no invented 40–75% floor.
5. Metrics overview: `honesty.successRateProvenance=live_runs` + series assessment.
6. `GET /api/reporting/honesty-audit` — live inventory + correlation checks.
7. Static-series detector (`assess_metric_series`) — Phase 4 principle on reports.

## Standing tests

- `backend/tests/services/test_reporting_honesty.py`

## Live evidence (tip-matched)

- Tip: `4e807263252399aaa2ff9b44952b02072ce7193a` (`/health` `git_sha`)
- `GET /api/reporting/honesty-audit` → `verdict=PASS`, `surface_count=12`
- Metrics overview `honesty.successRateProvenance=live_runs`; `range=24h` → HTTP 400
- ROI placeholders provenance `not_configured`
- Artifact: `docs/delivery/phase5-reporting-insights-honesty-live.json`
