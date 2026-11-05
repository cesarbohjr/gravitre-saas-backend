# PR #605 — Tranche 10: exact-head runtime inventory artifact validation and nested router correction
Date: 2026-11-05.

## Verified CI evidence, not just workflow status
- PR605 CI run `42060414251` failed in backend job `127385524920` with `ModuleNotFoundError: No module named 'app'`. Fixed by explicit backend root insertion (commit `3b95f6677192e2f957077be283e828b155c5da1a`).
- Follow-up CI run `42073285770` successfully executed `PR605 runtime mounted-route and dependency export` and uploaded artifact `pr605-runtime-route-dependencies` (artifact ID `13437731631`).
- **Artifact inspected, and a correctness problem found despite the green step:** `route_count=139`, but **134 entries were `_IncludedRouter` containers** with empty path and handler, four generic `Route` entries and one `APIRoute`; import edge count was 1,066. The large import-edge count does NOT prove valid route/handler mapping.
- We therefore **rejected the 139 figure as a production endpoint count**. A green script-execution step is not a certified inventory.
- Corrective code commit `53badcacbbd8c0cc16768b6799d1a5f45222b8ff`: recursively unwrap nested router containers; emit route handler identities, dependency-injection graph and bounded absolute import edges; independently compare against OpenAPI path set; export unresolved wrapper metadata for diagnosis and explicitly **fail** CI when unhandled router containers or unmatched OpenAPI paths remain.
- This corrective implementation is **not yet validated** against the next exact-head CI artifact. Even after successful export, dynamic call sites, event/RPC edges and production traffic coverage remain separate gates.

## Additional engineering gap
**ECO-063 / P0 — CI evidence integrity:** The route inventory must assert semantic completeness, not merely successful process exit and file upload. Commit SHA, package versions, registered route count, unresolved router count, OpenAPI cross-check and representative handler edges must be inspected together. Never certify `app.routes` container counts as actual endpoints.

## Required next steps
1. Inspect new CI job step, artifact counts and uncovered route metadata from latest PR605 commit.
2. Repair unresolved nested router semantics until route coverage has no unexplained gaps. Preserve WebSocket routes that OpenAPI intentionally omits.
3. Add source-relative and dynamic-dispatch call edges with explicit unknown markers, trace frontend caller mapping and correlate against production traffic.
4. Update PR605 governing plan and retirement ledger with evidence; do not delete legacy or mutate run history until certified.

## CI exporter hardening follow-up
Further code review found the revised exporter wrote a literal `\\n` suffix instead of an actual newline and would not fail if OpenAPI schema generation raised an exception. Both are fixed in commit `b7502f83f98b62a52f6f75ad3ba11771807f37bf`; wrapper metadata now tolerates objects without `__dict__`. Exact-head CI and artifact parsing must confirm correctness; none of this constitutes production caller coverage.
