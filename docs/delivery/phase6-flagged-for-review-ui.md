# Phase 6 — Flagged-for-review UI + v0 design handoff

Functional honesty first; visual v0 handoff second (no data-contract changes in v0).

## Functional scope (shipped)

1. **BusinessOutcome DTO** — `VerificationSection` carries:
   - `reviewState` (`flagged_for_review` for Phase 4)
   - `checkFailed` (`batch_degeneracy` | `follow_up_proof` | `effect_unproven`)
   - `finding` (concrete Module D copy, e.g. `6 of 6 records returned the same industry: 'cannot tell'`)
   - `nextActions` (specific operator steps)
2. **Projector** maps `workflow_runs.status=flagged_for_review` + `batch_degeneracy` → never `verified` lifecycle; summary prefers the finding.
3. **Phase 3 vs Phase 4** distinguishable via `checkFailed` (follow-up proof ≠ batch degeneracy).
4. **Surfaces** (same DTO / renderer):
   - Chat + Runs + Activity → `BusinessOutcomeView` fourth state `flagged`
   - Activity filter `flagged_for_review` + warning rail on list rows
   - Browser extension overlay badge / finding / next actions
5. **Reporting honesty** — Intelligence reports call out `not_configured` / `insufficient_data` visually (Phase 5 provenance preserved).
6. **Persistence** — `batch_degeneracy` / `population_verify` merged onto run parameters at finalize so Activity re-projection has the finding.

## Standing tests

- `test_flagged_for_review_phase4_finding_on_business_outcome`
- `test_follow_up_proof_phase3_distinct_from_batch_degeneracy`
- Prior Phase 4 `test_cmumulle72_six_identical_schema_valid_rows_flagged`

## Live verify

```bash
python scripts/verify-phase6-flagged-ui-live.py
```

Artifact: `docs/delivery/phase6-flagged-for-review-ui-live.json`

## v0 handoff (visual only)

See [phase6-flagged-for-review-v0-handoff.md](./phase6-flagged-for-review-v0-handoff.md).
Begin only after tip-matched functional PASS below.

## Live evidence (tip-matched)

_Filled after deploy + verify script._
