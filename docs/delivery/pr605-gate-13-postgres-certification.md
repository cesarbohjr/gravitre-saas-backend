# PR605 Gate 13 — independent PostgreSQL certification and main CI blockers
Date: 2026-11-05. **All certification claims are exact to the specified GitHub Actions run and commit.**

## Verified PASS: v2 run status contract
- Isolated workflow: [PR605 run status contract certification — run 42094961780](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42094961780)
- Branch commit under test: `4e1dcc59b48ae66b5af52c2bae0ef660234839a4` (GitHub PR test checkout is a merge ref based on that head).
- Real throwaway PostgreSQL 16 instance: **12 passed**, no skipped tests; status constraint, terminal/partial/review projections, v2 metadata, fail-closed SQL mirror, transactional rollback, idempotent migration reapply.
- Focused application mapping tests (excluding unrelated workflow mock paths): **14 passed**, 9 unrelated tests deselected, no skipped; legacy-to-v2 status aliases, review distinctness, partial distinctness, unknown fail closed.
- Independent workflow introduced at `.github/workflows/pr605-run-status-contract.yml`. Earlier failing runs recorded:
  - `42094607417`: test collection blocked by repository-wide `tests/conftest.py` requiring `httpx` in a minimal environment.
  - `42094766936`: 29 tests passed, six unrelated workflow tests failed on missing full Supabase/Pydantic dependencies when using the minimal environment. The scope was narrowed to actual contract and PG tests. The main CI remains responsible for the full workflow test suite.
- **Do not claim production certification**: migration is staged/unapplied, Railway production DB binding not attested, historical rows untouched.

## Current main CI run remains a blocker
- Main CI on the independent-pass SHA: [run 42094961866](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42094961866).
- Backend job `127483248032` has not yet reached its PR605 runtime route export or integrated PostgreSQL certification; last observed in step `Reclaim unused hosted-runner SDKs before Python dependencies`. Therefore no fresh full route inventory artifact can be certified.
- Previous run `42077697942` failed route inventory (134 unresolved FastAPI `_IncludedRouter` wrappers and OpenAPI model undefined). The fixes (`original_router` unwrapping, `CandidateReviewRequest` definition and tests) are committed, but exact-head rerun and artifact inspection remain mandatory.
- Separate Marketing Lighthouse performance gate failed earlier at homepage 0.73/0.74/0.74, below 0.75; do not lower threshold without separately justified product decision.

## Next mandatory release evidence
1. Allow main CI route export to run, verify actual registered handler counts, nested wrappers zero, OpenAPI mismatches zero, generated JSON parseable, and representative voice/assistant/connector routes present. Upload artifact with exact SHA.
2. Verify full backend tests including `test_pr605_run_status_contract_pg.py` and `test_schema_sync.py`, plus web typecheck and migration safety on *same final SHA*. The independent PG pass is necessary but not a substitute for the integrated suite.
3. Investigate any route/OpenAPI generation failure by exact exception and code fix; rerun on resulting commit.
4. Obtain non-secret production Supabase project attestation and authorized, tenant-scoped row list before considering historical reconciliation.
5. Keep historical run-state changes, migrations, production deploy and PR merge **blocked** pending all relevant gates. Reconciliation separately requires explicit operator approval.

## Status
**Independent PostgreSQL contract certified — YES. Full PR / route inventory / database binding / historic reconciliation certified — NO.**
