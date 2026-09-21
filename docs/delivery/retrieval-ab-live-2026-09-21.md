# retrieval_ab live probe — 2026-09-21T16:50Z

**Result:** probe `pass: true` against Railway `/health` **`6d563e3dbc28034d6b7c9638d8e7679c18c3beb5`**.

`166759e7` (named gateway regression) did **not** change the production kernel — Railway skipped deploy (tests/scripts only). The honesty product path (`6e070c07`) is contained in `6d563e3d`.

Isolated org `f07e57c0-1501-4000-8000-c04e57a00001`. Artifact: `docs/delivery/retrieval-ab-live-latest.json`.

| Query | Pass | Evidence |
|-------|------|----------|
| A_fast_connectors | true | `tool_names: ["getConnectorStatus"]`; text_head is not the 2026-09-21 four-slug false claim |
| B_write_intent_gate | true | pending approve, no send |
| C_org_kb | true | `searchKnowledgeBase` |
| D_thin_broaden | true | `internal_thin: true` |
| E_fast_honesty | true | effectiveMode fast |

Query A named list after the tool: `You have Apollo, Google Ads, and Hubspot connected.` That is **not** the unverified four-slug sentence (`…and Hubspot` plus Search Console with empty tools). It ran `getConnectorStatus`. Vendor-row truth vs executable remains a later audit; this probe bar is closed.

**3.0-H/I not closed.** Required CI [35622991537](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35622991537) on `6d563e3d` **failure**. Spoken confirm traces **NOT RUN**.
