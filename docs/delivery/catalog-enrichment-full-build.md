# Catalog-wide retrieval enrichment — full build

**Status:** DONE — adopt default ON  
**Tip:** `45ae7d052d1f88236d2aacb675b84cece751d825` (`/health` git_sha live)  
**Catalog count:** **690** actions / **77** vendors (`all_catalog_action_specs()`)

## Part 1 — Enriched content

- Generator: `scripts/generate-action-retrieval-enrichment.py`
- Artifact: `backend/app/connectors/action_catalog/data/action_retrieval_enrichment_full.json`
- Method: LLM batch (`gpt-4o-mini`, 35 batches) + schema/behavior validation + deterministic repair
- Coverage: **690/690 (100%)**, 685 LLM-ok, 5 repaired, 0 failures
- Per action: 3–5 natural-language examples + 5–9 functional tags (shared taxonomy)

Report: `docs/delivery/action-retrieval-enrichment-generation-report.json`

## Part 2 — Semantic retrieval wiring

- Embed doc = name + integration + when/why description + invoke id + **tags + up to 5 examples**
- Module: `action_retrieval_enrichment.py` — `ENRICHMENT_ENABLED=True` by default (env override)
- Progressive disclosure unchanged (stubs → search_catalog_tools); enrichment only improves candidate ranking
- Vendor ID fix: `action_id_resolve.py` so `absorb_lms_*` / `google_sheets_*` map correctly (was first-underscore split)
- OpenAI payloads strip `invoke_action`/`integration` via `openai_tool_payload`

## Part 3 — Measurement (hard targets)

Artifact: `docs/delivery/catalog-enrichment-nl-variance-live.json`  
Live tip verify `@ 2026-08-06T09:39:09Z` against `api_git_sha=45ae7d05…`

| Target | Result |
|--------|--------|
| ≥200 cases, all 77 vendors | **770 cases / 77 vendors** |
| Correct-tool (top-k) ≥90% | **95.06%** PASS |
| Withhold battery 100% (3 cats) | **PASS** (standing tests with enrichment ON) |
| Latency unregressed | narrow p50 **27ms**, embed_query p50 **20ms** — PASS |
| Coverage | **690/690** enriched (`full_coverage=true`) |
| A/B sample | **delta_correct=+1** (off→on) |

**Recommendation:** permanent default ON (`adopt_enrichment_default_on`).  
**Verdict:** `overall_pass=true`

## Part 4 — Standing protection

- CI lint: `test_every_action_has_retrieval_enrichment_examples_and_tags` in `test_action_schema_standard_lint.py`
- Schema standard doc updated (principle 2b)
- Workflow: `.github/workflows/catalog-enrichment-nl-variance.yml` (push path + weekly)

## Governance (unchanged)

`catalog_write_authority`, approval gates, and write execution paths are untouched — enrichment only changes HOW actions are found.
