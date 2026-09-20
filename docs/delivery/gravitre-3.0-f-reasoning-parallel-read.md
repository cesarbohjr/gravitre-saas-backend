# Gravitre 3.0-F — reasoning / parallel READ (2026-09-20)

**Status:** Source **UNIT_TEST**. Why-pipeline golden with evidence labels. Join only when the entity store has accepted bindings. LIVE_USER_PROVEN **NOT RUN**.

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

## Gate

- Why-pipeline golden: `backend/tests/services/test_reasoning_evidence_pipeline.py` + existing `test_multi_source_diagnostic.py`
- Live multi-source diagnostic: **NOT RUN**
