# Phase 2 — Pack / template pre-wiring audit

## Bar

Every published pack/workflow must install fully connected with substantive
agent instructions. The only expected user action is connecting third-party
accounts (and declared install variables). Distinct from the connector
install-ready gate.

## Gaps found

1. Many seed `workflow` agent tasks were stubs (&lt;40 chars).
2. Pack install wrote contract edges into `workflows.edges` but never
   `definition.graph` or canvas tables via `sync_builder_graph`.

## Fixes

- Expanded stub agent tasks in `seed_catalog.py` + `seed_catalog_expansion.py`.
- Install embeds sequential `definition.graph` and materializes canvas through
  `sync_builder_graph` (`pack_prewiring.materialize_pack_canvas_graph`).
- Audit: `backend/scripts/audit_published_pack_prewiring.py`
- Tests: `backend/tests/marketplace/test_pack_prewiring.py`
- Live: `scripts/verify-phase2-pack-prewiring-live.py`

## Accounting

See `docs/delivery/published-pack-prewiring-audit.json` and live artifact
`docs/delivery/phase2-pack-prewiring-live.json` after tip-matched verify.
