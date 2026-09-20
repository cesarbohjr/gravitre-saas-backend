# Gravitre 3.0-E — JIT tools + skills (2026-09-19)

**Status:** Source **UNIT_TEST**. Eligible ActionSpec search + versioned procedures from recipes/packs. **Not** a second agent runtime. LIVE_USER_PROVEN **NOT RUN**.

## What shipped

| Piece | Behavior |
|-------|----------|
| Tool search | capability + connected + availability → ≤16 ActionSpecs (hard cap 32) |
| F1 eligible set | F1 READ keys kept when vendor is connected |
| Examples | Enrichment example on narrowed tool descriptions |
| `search_catalog_tools` | Query ranks candidate names by tokens |
| Skills | Recipes + tool-knowledge procedures (`owner`, `version`, `tests`) |
| Runtime | `procedure_only` — no skill `execute()`, WRITE still `react_write_gate` |

## Gate

- Eligible-set tests: `backend/tests/services/test_jit_tool_skills.py`
- Production token/stage vs 3.0-A: **NOT RUN** (shared with 3.0-B)
