# Tool Knowledge layer — closeout (2026-08-11)

## Verdict

Shipped Knowledge-only Tool Packs attached to the existing ActionSpec catalog. Observation / Action / Governance were **not** rebuilt. Vendor API docs were **not** bulk-ingested; Wave 1 content is Gravitre-authored under the same `licence_verified` gate as department packs.

## Phase evidence

| Phase | Artifact |
| -- | -- |
| 0 Reconciliation | `tool-knowledge-phase0-reconciliation.md` — 78 vendors / 696 actions; 12 Wave-1 vendors missing connectors |
| 1 Knowledge layer | `tool_knowledge.py`, registry `pack_type=tool_expertise`, orchestrator compose |
| 2 integration_class | `integration_taxonomy.py` + `tool-knowledge-phase2-integration-class.md` |
| 3 Cross-dept reuse | `tool-knowledge-phase3-cross-department.md` — connector-driven, UI hides tool packs |
| 4 Ingest | `tool-knowledge-wave1-ingest-results.json` — 10 vendors, 11 chunks, `compose_pass=true` @ `2026-08-11T23:07:49Z` |
| 5 Governance | `tool-knowledge-phase5-governance-reconciliation.md` — map to existing kind/destructive; no second tier enum |

## Compose test (pre-deploy Supabase)

- Catalog sample: `hubspot.contacts.get`, `hubspot.deals.search`, …
- Fabric: 2 HubSpot tool-expertise citations when packs granted from connected vendors
- `compose_pass: true`

## Deploy

- Commit: `1a7623b5ef956d8093194f2ace6b124b0c24ed46` on `main`
- Live `GET https://api.gravitre.app/health` → `git_sha=1a7623b5ef956d8093194f2ace6b124b0c24ed46` `status=ok` @ `2026-08-11T23:12:12Z`
- Post-deploy compose: `tool-knowledge-postdeploy-compose.json` — `compose_pass=true` (HubSpot actions + 2 tool-expertise citations) @ `2026-08-11T23:13:07Z`
