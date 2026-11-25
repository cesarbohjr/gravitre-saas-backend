# ECO-002 / ECO-003 bounded performance engineering batch

Source baseline: 8f93f56416baade3c35a0d37e013ddb5beac87f4. No deployed performance claim or release authorization.

## Dependency DAG
Dialogue settings -> sentiment; understanding -> classification -> cluster -> clarification.
Clarification early exit does not need overview policy. Context retrieval -> risk evaluation (conditional) -> dialogue policy -> model selection and optional overview policy (independent scoped reads) -> enrichment eligibility -> governed response dispatch -> guidance.
Existing optional enrichments, model ledger lookups and org snapshot fanout already overlap reads. Do not move approval, risk, dispatch or provider calls ahead of gates.
Context: adaptive/meta policy -> org snapshot -> memory -> RAG (CRM bias depends on org snapshot) -> confidence -> conditional graph/hybrid/research -> assembly. Company snapshot and external research remain after authorized unified retrieval; HTTP authorization errors must stop both. Snapshot fanout: org identity and integrations always; agents/workflows/runs/alerts only when depth enables them. No new cache or altered TTL, identity or invalidation semantics.

## Changes
Move optional overview policy off the clarification path; overlap with model selection only after dialogue policy. Await both and drain async sibling on failure/cancellation. Blocking read already submitted to executor may finish after cancellation; it is read-only. Reduce minimal snapshot scheduled tasks from six to two, retain maximum five threads per snapshot. Propagate explicit HTTP failures from unified retrieval instead of falling back to empty context. Existing permission and provider boundaries unchanged.

## Evidence
Baseline QA12 exact head: 31 real PostgREST, 14 named joined cases, 212 PostgreSQL cohort passed. New tests use synchronization barriers to prove overlap, denial propagation, actual snapshot submission counts by depth, and no downstream company/research on HTTP 401/403/404. No representative latency measurement yet. Stage p50/p95 must be collected from existing opt-in fixed-label metrics with approved isolated representative traffic, stratified by branch and context size; no summation of nested spans. No cross-tenant live proof or real provider readback claimed. Final 12 QA and rollback/owner gates remain.
