# Tool Knowledge — Phase 3 cross-department reuse (2026-08-11)

## One source, many consumers

- Pack id pattern: `pack.tool.{vendor}` (e.g. `pack.tool.hubspot`) — **one** Knowledge Fabric pack / source set per vendor.
- Sources: `tool.{vendor}.expertise` with `pack_type=tool_expertise`.
- Grant path: `tool_packs_for_connected_vendors()` in `backend/app/knowledge_fabric/tool_knowledge.py`.
- Orchestrator: `intelligence_orchestrator` auto-appends those packs into fabric retrieve when the org has the vendor connected — **not** a per-department duplicate corpus.

## Composition with department-pack UI

- Department packs remain manually selectable / recommended via `recommended_pack_ids_for_department()`.
- Tool expertise packs are **hidden** from `agent-knowledge-packs-editor` (`pack_type !== "tool_expertise"`).
- Agent tool-knowledge access is driven by **connector grants**, matching catalog discipline.

## Live compose evidence

See `docs/delivery/tool-knowledge-wave1-ingest-results.json` → `compose_test` + `cross_department`:

- Connected vendors `hubspot` + `slack` → packs `pack.tool.hubspot`, `pack.tool.slack`
- HubSpot catalog actions still live (`hubspot.contacts.get`, …)
- Fabric hits include HubSpot tool-expertise citations
- `compose_pass: true`
