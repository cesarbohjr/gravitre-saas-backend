# Phase 4 — Degenerate / low-information batch detector

## Approach (explicitly not a second AI)

Statistical check on value **distribution** across multi-record results.
Schema-valid + Phase-3-passing batches can still be flagged when fields are
identical or placeholder-dominated.

## Thresholds (chosen + rationale)

| Batch class | min_batch | identical_ratio | placeholder_ratio | Why |
|-------------|----------:|----------------:|------------------:|-----|
| `enrichment` | 3 | 0.80 | 0.50 | Enrichment fields (industry, headcount, fit) should vary across companies; 5/6 identical is already suspicious; 6/6 must flag |
| `list_population` | 3 | 0.85 | 0.50 | Contact payloads can share list metadata but content fields should differ; slightly higher identical bar to avoid false positives on shared list tags |
| `default` | 3 | 0.85 | 0.55 | Conservative default for other multi-record writes |

Batches with &lt;3 records are skipped (`batch_too_small`) — variance is not meaningful.

## Outcome

Flagged batches terminate as **`flagged_for_review`** (DB + Module A), never
`completed` / verified. Distinct from `partial_success` (empty-shell / async)
and `failed`. UI surfacing is Phase 6.

## Wire points

- Chat finalize (`chat_connector_execution_service`)
- Extension finalize (`extension_bridge_service`)
- Workflow honesty (`apply_connector_run_honesty`)

## Standing regression

`test_cmumulle72_six_identical_schema_valid_rows_flagged` — six schema-valid
identical rows → `flagged_for_review`.

## Live evidence (tip-matched)

- Tip: `84f729dbe50802a87a5f36b67dc4dfc1e8f12da5` (`/health` `git_sha`)
- Scenario: cmumulle72 six identical schema-valid enrichment rows
- Detector: `flagged=true`, reason=`identical_value_dominance`, ratios 1.0/1.0
- Persist: `workflow_runs.id=c19876ec-7c0f-4337-b2bd-13c620f4ee62` status=`flagged_for_review`
- Artifact: `docs/delivery/phase4-batch-degeneracy-live.json`
- DB: `workflow_runs_status_check` includes `flagged_for_review` (applied 2026-08-07)
