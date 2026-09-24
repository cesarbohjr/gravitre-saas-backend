# Gravitre 3.0-F — reasoning / parallel READ (2026-09-20)

**Status:** Source **UNIT_TEST** plus live diagnostic path `diagnostic_parallel_read` (HMAC sealed READs in parallel, 3.0-D artifact bind). LIVE_USER_PROVEN until the serving SHA includes this slice.

## What shipped

| Piece | Behavior |
|-------|----------|
| Labels | FACT / INFERENCE / HYPOTHESIS / RECOMMENDATION |
| Honesty | No live evidence → FACT that evidence is insufficient; no guessed cause |
| Join | Only with accepted BusinessEntity bindings; else independent parallel READs |
| STA-312 | Person joins exact email/alias only; fuzzy names refused |
| Parallel | `read` + `evidence` concurrent; WRITE never in the batch |
| Speculative READ | High confidence, cheap, cancellable, no privacy escalation |
| Speculative WRITE | Forbidden |
| Live path | Causal / why questions skip F1-only short-circuit and run `try_diagnostic_parallel_read_turn` |

## Gate

- Why-pipeline golden: `backend/tests/services/test_reasoning_evidence_pipeline.py` + existing `test_multi_source_diagnostic.py`
- Diagnostic executor: `backend/tests/services/test_diagnostic_parallel_execution.py`
- Live multi-source diagnostic: **NOT RUN** until production SHA includes this file

## Frontend contract (3.0 Plus — do not redesign the panel)

`execution_result.structured` may include:

- `claim_labels`: `[{ "text": string, "label": "FACT"|"INFERENCE"|"HYPOTHESIS"|"RECOMMENDATION" }]`
- `missing_sources`: string[] of honest not-connected copy
- `provider_reinvoked`: boolean (false when stored Observations were reused)

Existing `kind=report` artifacts and GET `/api/assistant/conversation/{id}/state` are unchanged. Presentation remains the current artifact panel / work canvas.
