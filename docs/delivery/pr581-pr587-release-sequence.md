# Coordinated PR581 / PR587 execution record

The user's current release instruction authorizes the six-stage sequence below. Earlier draft/no-deploy language in historical records describes earlier checkpoints; it does not override this later instruction. Authorization does not bypass repository protections or acceptance gates.

| Stage | Required evidence | Current disposition |
| --- | --- | --- |
| 1. PR581 final CI | Every applicable workflow green on the final branch head | Pending final-head certification; the earlier a81ec4e checkpoint is historical |
| 2. Native worker and durable Langfuse | Actual gVisor-isolated OpenHands/Chromium execution and cancellation; real Langfuse OTLP acknowledgement, restart/idempotency and deletion readback | New real-service CI gates present; not certified while actual runs fail |
| 3. Freeze PR581 | Reviewable final source and evidence; remain unmerged while PR587 finishes | Pending stages 1–2 |
| 4. Complete PR587 engineering | Canonical shared intelligence, governed guidance/memory, catalog/channel contracts and reproducible three-dimension product benchmark protocol | Source prepared; final CI pending; actual product quality remains unmeasured |
| 5. Final combined validation | Frozen combined source, full regression and exact-head CI, no unresolved compatibility failures | Focused combined regression passed; broad local run: 16,022 passed / 281 skipped / 9 Redis setup errors under the all-socket offline guard; real Redis must pass in CI |
| 6. Controlled release | Merge through protections, deploy one combined main build, verify both deployed SHAs and production acceptance | Not started; gated on stages 1–5 |

## Production activation dependencies

Railway's existing backend container is not a native sandbox host. Native activation needs a dedicated Linux host with Docker and gVisor/Kata, persistent private storage and private authenticated TLS. The repository supplies a systemd service and read-only preflight under `deploy/native-worker/`. No such accessible host has been identified in the connected infrastructure. Do not run the sandbox broker as an ordinary Railway worker, expose Docker, weaken isolation or enable a native action before this dependency is met.

Langfuse production destination credentials and tenant consent must be configured through approved secret management. The backend currently has no native-runtime/Langfuse activation settings. Disposable CI server credentials and synthetic observations are never production configuration or provider-quality evidence.

## Acceptance after deployment

Verify Railway `/health` reports the merged main SHA and Vercel production serves that same coordinated source. Execute the existing Plays production acceptance and authenticated admin/non-admin UI checks required by `AGENTS.md`; label an inaccessible protected workflow or missing real session `NOT RUN` with the actual blocker.

The reference benchmark protocol is `docs/delivery/pr587-chatgpt-product-benchmark.md`. Actual ChatGPT text, voice and tool sessions, physical audio, contemporary product configuration and two independent blinded human raters are release-stage evidence. Until captured and reviewed, every quality claim remains **NOT CERTIFIED**. Deterministic fixtures, SDK imports and provider API responses cannot stand in for those observations. Native guidance stays selected; the Mem0 complete-erasure failure remains a rejection of adoption.

No production migration is included in the reviewed branch changes. Re-check the final diff before release; any newly introduced production migration must follow the repository's explicit approval policy.
