# ECO-001 → ECO-002 administrative consolidation (2026-11-13)

**Decision:** ECO-001 is closed **as a separately tracked administrative work item only**, and every unresolved ECO-001 acceptance requirement is transferred intact into ECO-002. This decision is **not a successful remediation**, **not a verified production fix**, **not technical retirement**, and **not release authorization**. ECO-002 remains P0 and release-blocking until both its latency requirements and all inherited ECO-001 orchestration/authority requirements pass. The original 43-finding register keeps both IDs for audit traceability, with 42 independent active queues and one administratively consolidated item. The original ECO-001 historical test evidence, source hypotheses, and unverified statuses are retained.

## Ownership and scope of the combined ECO-002

The consolidated ECO-002 owns **both** (A) governed Chat/Agent orchestration and single-authority execution from ECO-001 (QA20, source `backend/app/operators/agent_intelligence.py`) and (B) routing latency and dependency measurements from ECO-002 (QA30, source `backend/app/services/intelligence_router.py`). Any optimization or routing parallelization must preserve A, including denial, approval, cancellation, revocation, durable terminal outcomes, authorization, tenant separation, replay safety, and source-to-caller authority ownership.

## ECO-001 acceptance debt transferred without waiver

1. Independently identify active Chat, Agent, Voice, Play, and Canvas call paths/feature flags to canonical decision authority. Resolve competing-writer hypothesis with source **and runtime evidence**, not assumption.
2. Pass actual deployed QA FastAPI ingress proof: `GET /health` JSON reports exact deployed SHA, a nonproduction environment, and `checks.database=healthy`; anonymous protected conversation-state `GET` must return 401 or 403. Previously observed Railway healthcheck HTTP 200 alone is insufficient.
3. Establish isolated QA with no scheduled background writers, and protect internal cron endpoints with QA-only `INTERNAL_API_SECRET`. The QA HTTP-only safeguard is committed but pending exact-SHA CI and deployment.
4. Prove allowed/denied/cancelled/revoked/inflight/crash-restart/idempotent-replay outcomes with an independently persisted ledger, source-to-provider/consumer readback and negative unauthorized-write tests; existing isolated PostgreSQL receiver fixtures are partial evidence, not production provider proof.
5. Establish cross-surface parity, exact-SHA CI, deployment and rollback evidence, and explicit independent owner approval. None are implied by this administrative consolidation.

## ECO-002 existing performance acceptance debt

Record real stage-level p50/p95 and sample counts, request/context payload size and voice time-to-first-audio as applicable; document dependency DAG and baseline-derived targets. Parallelize only genuinely independent stages after timing data and parity tests, preserving execution governance and cancellation semantics. The opt-in timing code, static labels and test source do not establish measured latency improvements.

## Evidence references

- `docs/delivery/eco-001-authority-acceptance-certification.md` — earlier isolated source and test evidence, incomplete finding.
- `backend/tests/db/test_eco001_joined_chat_http_receiver_pg.py`, `backend/tests/db/test_eco001_joined_agent_worker_pg_receiver.py` — independent database fixture coverage.
- `backend/scripts/eco001_deployed_ingress_preflight.py` and `.github/workflows/eco-001-deployed-ingress.yml` — read-only deployed QA preflight still needing independent runtime results.
- `docs/delivery/eco-002-routing-latency-baseline.md`, `backend/app/services/routing_stage_metrics.py`, `backend/tests/master_qa/test_eco002_route_stage_metrics.py` — ECO-002 staged instrumentation and tests.
- Railway isolated QA deployment `830c9af4-ccfd-4b09-a049-17cbd4f73aa7` at source SHA `79264d973d8d56990a8db7e566efed56df7f4675` previously returned HTTP 200 for Railway healthcheck; independent JSON/auth preflight remains unverified. Later QA source changes were staged, not certified deployed at time of consolidation.

## Closure semantics

- ECO-001: `implementation_state=CONSOLIDATED_INTO_ECO-002`, `administrative_closed=true`, `closure_disposition=CONSOLIDATED_NOT_REMEDIATED`, `fix_verified=false`, `retirement_authorized=false`, `owner_approval=false`, `live_status=NOT_RUN`, and `release_blocking=false` **only because ECO-002 is now the sole blocking owner for the exact same requirements**.
- ECO-002: `release_blocking=true`, `fix_verified=false`, `retirement_authorized=false`, `owner_approval=false`, `live_status=NOT_RUN`. All inherited ECO-001 unmet acceptance obligations are mandatory; no gate is deleted.
- No merge, provider write, production deployment, rollback attestation, owner signoff or global release authorization is claimed or performed.
