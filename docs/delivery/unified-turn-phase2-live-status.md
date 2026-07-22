# Unified turn Phase 2 — live verification status

Updated: 2026-07-22

## Verdict

**PASS (core batteries)** on tip `acb44e3b…` via workflow
[29909107895](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29909107895)
(pending 24/24, conversational 20/20, shadow 4/4).

**Expanded program gates** (knowledge-boundary, STA-305, run-history/stale-plan,
persona-drift) re-run locally same tip — see matrix below. Persona-drift remains
**PARTIAL** until shadow task-retention ships past tip.

| Gate | Verdict | Evidence |
|------|---------|----------|
| Prod tip | **PASS** | `/health` → `acb44e3b0fef44845897f96808ff562fcc5a032c` |
| Shadow enabled | **PASS** | `unified_turn.shadow.completed` during batteries |
| Pending-reply | **24/24 PASS** | [`pending-reply-classifier-battery-live.json`](pending-reply-classifier-battery-live.json) |
| Conversational path | **20/20 PASS** | [`conversational-path-battery-live.json`](conversational-path-battery-live.json) |
| Targeted shadow (workflow) | **4/4 PASS** | Workflow [29909107895](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29909107895) |
| Knowledge-boundary FAST | **PASS** | shadow `knowledge_boundary` @ `2026-07-22T10:00:40.855766Z` conv `2696bd7b-…` |
| Status-check pending | **PASS** | shadow `confirmation_request` @ `2026-07-22T10:00:24.86923Z` |
| Run-history + stale-plan | **PASS / PASS** | [`run-history-stale-plan-live.json`](run-history-stale-plan-live.json) |
| STA-305 omit-detail | **PASS** | [`sta305-catalog-kind-prod.json`](sta305-catalog-kind-prod.json) conv `3ce08268-…` |
| Persona-drift 30-turn | **PARTIAL** | [`unified-turn-persona-drift-live.json`](unified-turn-persona-drift-live.json) — 0 cheer/catalog; missing shadow audits under load |
| Full multi-step email | **PARTIAL** | single-turn email intent only |
| TTFT streaming &lt;200ms | **NOT RUN** | Phase 3 — code on `main` (`2f764ef6`), needs tip deploy |
| Cutover | **BLOCKED** | Phase 4 — needs Phase 2 persona clear + Phase 3 TTFT |

## Shadow audit pointers (workflow 4/4)

| Case | Timestamp (UTC) | `outcome_kind` | `latency_ms` |
|------|-----------------|----------------|--------------|
| greeting_no_catalog_leak | `2026-07-22T09:46:16.287442Z` | conversational_reply | 1572 |
| thanks_plain | `2026-07-22T09:46:30.250849Z` | conversational_reply | 952 |
| email_intent_no_catalog_dump | `2026-07-22T09:46:46.523885Z` | clarifying_question | 3705 |
| status_check_pending | `2026-07-22T09:47:08.962893Z` | confirmation_request | 1991 |

## Structural follow-up

Retain fire-and-forget shadow tasks in `_SHADOW_BACKGROUND_TASKS` so conversational
early-exits do not drop audits (root cause of persona-drift PARTIAL). Deploy tip,
then re-run `scripts/verify-unified-turn-persona-drift-live.py`.

## Cutover gates (do not open)

- Persona-drift cleared after tip ships task retention
- Phase 3 true streamed TTFT reported (`docs/delivery/unified-turn-phase3-latency-status.md`)
- Explicit Phase 4 cutover authorization

Standing rule: write-authority / approval / Module A unchanged; shadow does not execute tools.
