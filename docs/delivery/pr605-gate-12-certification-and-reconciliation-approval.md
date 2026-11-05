# PR #605 — Gate 12: Exact-head certification evidence and historical reconciliation approval dossier
Date: 2026-11-05. This is a **draft / no production mutation** release-gate record.

## Certification: failures actually observed
At draft PR head `bdc42234d067b4a859650ef4ae4a029b03a82abc`:
- Main CI workflow `42077697942` **FAILED**. Backend pytest job `127448519099` failed at the new route-inventory step; required Postgres contract tests were **SKIPPED because earlier CI failed** (not passed).
- Exported artifact `13442726617` was inspected. Its report listed `route_count=5`, `unresolved_wrappers=134`, `openapi_paths=0`, `import_edges=1066`. Thus static imports were enumerated but actual mounted handlers were not. This is a **failed certification**, not usable route coverage.
- Source of wrapper failure: `fastapi.routing._IncludedRouter` stores the wrapped router in `original_router`, omitted from inventory unwrapping. Code now traverses `original_router` (commit `24600f519c5b6d37f9bb80cb2baff4cb6b3d6e8a`).
- OpenAPI generation raised `PydanticUserError` for unresolved `CandidateReviewRequest` on capability marketplace review. Source `backend/app/routers/capabilities.py` had a handler annotation for a class with no definition. The missing strongly typed `CandidateReviewRequest` (`decision: Literal['approve','reject']`; bounded notes) was added (commit `46efef385f4a48ff7c1ce3cd939d49e27668ef60`) with validation/OpenAPI tests (`backend/tests/routers/test_pr605_candidate_review_schema.py`). **Passing full OpenAPI remains to be verified**; there may be other forward references.
- Marketing Lighthouse workflow `42077697787` **FAILED**, independently: homepage performance three scores `0.73, 0.74, 0.74`, below the existing `0.75` requirement; pricing was measured too. Do not weaken threshold or count the perf gate as passed.

At the latest PR commit, exact-head CI is **not yet certified**. For each new failure, inspect its logs/artifact, repair at cause, and rerun until exact-head required checks are green. Retain SHA/run URLs and route coverage evidence.

## Historical status evidence
Connected Supabase project `smyeexlrqdpymwjmgzqu` remains *unattested* as Railway production. Read-only full outer join found:
- 801 `workflow_runs` ↔ `runs` pairs, with 767 compatible under old mapping.
- 30 `run_type=execute` pairs `partial_success/queued`.
- 2 `run_type=execute` pairs `failed/running`.
- 2 `run_type=execute` pairs `flagged_for_review/queued`.
- Two `workflow_runs`-only `flagged_for_review` rows.
- 283 `runs`-only records (do **not** assume orphaned; distinct workloads may write only there).
- 4 `pending_approval/needs_approval` pairs are **correct intentional translations**, not remediation targets.
All numbers are snapshot counts, not invariant future counts.

## Proposed controlled reconciliation — **NOT APPROVED**
### Scope
- Only `run_type=execute` with status divergence from versioned v2 source truth or missing contract projection.
- Preview requires authorized, tenant-scoped, row-level allowlist and before/after values; aggregate-only SQL is already committed in `docs/delivery/pr605-v2-historical-reconciliation-preview.sql`.
- Exact IDs are not included in this plan and must not be extracted without secure tenant-context/authorized operator access. No data repair SQL or jobs run in this gate.

### Exact allowable translations (only after v2 migration)
| Source `workflow_runs.status` | Prior contract row status | Expected v2 `runs.status` | Requires manual confirmation |
|---|---|---|---|
| `partial_success` | `queued` (30) | `partial_success` | Yes; ensure evidence actually supports partial effect and correct metrics |
| `failed` | `running` (2) | `failed` | Yes; verify terminal audit, step and provider observations |
| `flagged_for_review` | `queued` (2) | `flagged_for_review` | Yes; preserve distinct review/warning state |
| `flagged_for_review` | missing contract row (2) | create `flagged_for_review` projection if required | Yes; confirm ownership and absence of deleted/held references |

**No blanket updates.** Do not touch `runs`-only rows or any already-aligned pair.

### Preconditions and mandatory evidence
1. Non-secret database ref attestation from actual deployed Railway settings; confirm correct migrations/RLS/grants before schema change.
2. CI exact-head full pass; isolated PostgreSQL tests must execute, not skip. Inspect real route inventory artifact and OpenAPI proof.
3. Enumerate affected tenant-scoped run IDs and verified evidence; classify fixtures/test/production. Provide reviewer-approved individual proposed mutations.
4. Verify v2 contract read-model parity and UI business outcomes; partial/review must never be counted as full verified success.
5. For each approved run: strong compare-and-set guard on org_id/id/source version/status and contract version/status; no-op on already-converged records.
6. Prevent trigger recursion and avoid generating another terminal `workflow_runs` transition. Persist audit trail, reconcile operation ID, checkpoint and safe rollback strategy.
7. Bound batches, maintain per-tenant isolation, stop on unknown status, mismatch, unauthorized record or outbox anomaly.
8. After each batch verify data parity, approval consumers, analytics and 0 duplicate terminal events, then rerun exact affected tests.
9. Approval must be explicit and separate from PR approval/merge; authorization to execute a dry-run preview is **not** authorization to modify production.

### Approval gate
**PENDING OWNER/ENGINEERING/DB RELEASE SIGN-OFF.** No historical record update, migration, deployment, or PR merge has been authorized or performed in this audit.

## New remediation finding IDs
- ECO-064 P0: FastAPI `_IncludedRouter.original_router` route-introspection gap; inspect exact-head artifact.
- ECO-065 P0: Missing `CandidateReviewRequest` Pydantic model prevented OpenAPI schema generation; verify actual route schema after fix and guard with tests.
- ECO-066 P1: Lighthouse homepage perf 0.73–0.74 below 0.75 threshold; profile and repair; do not lower gate.
- ECO-067 P0: Run-status PostgreSQL tests skipped by upstream inventory failure, so v2 migration unverified; ensure CI ordering + required pass.
- ECO-068 P0: Historical reconciliation approval and tenant-scoped execution controls required as independent release gate.
