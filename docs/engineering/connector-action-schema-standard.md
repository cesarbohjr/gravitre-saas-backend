# Connector action schema standard (enforced)

**Status:** Enforced checklist for every new/edited `ActionSpec`  
**Grounding:** JSON Schema 2020-12 / MCP tool definitions (2026-07-28)  
**CI:** `backend/tests/connectors/test_action_schema_standard_lint.py`

## Seven principles

1. **NAMING** — `vendor.resource.verb` (≥3 dot segments). Legacy short ids keep backward-compat aliases; new ids must not introduce 2-segment exceptions.
2. **DESCRIPTION QUALITY** — Include a when/why cue (`Use when…` / `Use this to…` / `Prefer when…`), not only a mechanical what.
3. **FLAT, ATOMIC SCHEMAS** — One purpose per action; avoid mega-tools toggled by flags.
4. **JSON SCHEMA CONFORMANCE** — Prefer enums, required vs optional, and typed fields in `action_parameters` / `input_schema`.
5. **TOKEN BUDGET** — Keep descriptions concise (one short when/why sentence). Rely on keyword/embedding narrowing for the prompt subset.
6. **ANNOTATIONS** — `readOnlyHint` / `destructiveHint` are **derived** from existing `kind` + `destructive` (same signal as `catalog_write_authority`). Do not invent a parallel marking system.
7. **OUTPUT STRUCTURING** — Writes return parseable fields (`entity_id`, `list_id`, membership counts) suitable for verified-output / population checks.

## PR checklist

- [ ] Action id is `vendor.resource.verb` (or listed alias of a canonical id)
- [ ] Description has a when/why sentence
- [ ] Parameters use JSON Schema (enums where constrained)
- [ ] `kind` / `destructive` / `requires_approval` correct for writes
- [ ] No placeholder (`TODO`, `TBD`, empty) description
- [ ] Chat-visible tools have non-empty resolved schema via `action_parameters` or `input_schema`
