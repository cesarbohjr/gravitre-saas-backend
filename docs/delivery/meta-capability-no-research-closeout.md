# Meta capability no-research — closeout (2026-08-12)

## Phase 0

Confirmed: `What can you help me with?` on Marketing Analyst billed Serper `research_lookups` (`6e05b8f9…` @ `2026-08-12T18:27:58Z`). Root cause: `re_search_meta` gap → LIVE knowledge prefetch → thin auto-internet. See `meta-capability-no-research-phase0.md`.

## Phase 1

- Expanded `re_search_meta` (full-message capability patterns including UI fallback prompt)
- LIVE short-circuit + `should_augment_unified_turn_with_knowledge` skip
- Answers from `build_capability_snapshot` / agent config only

## Phase 2

- `filter_relevant_internet_results` / relevance floor before cites
- UI: honest empty “No relevant sources found” (no noise chip)

## Phase 3

- CI battery: `backend/tests/services/test_meta_capability_no_research_battery.py` (66 related tests green locally)

## Live after (tip)

`GET https://api.gravitre.app/health` → `git_sha=4dc52508254a5cc3ca6f124753102dcef303908e`

`meta-capability-no-research-after.json` — **PASS** 3/3 · `research_lookups_billed=[false,false,false]` for:
- Marketing: “What can you help me with?”
- Marketing: “what are you able to do?”
- Sales: “what tools do you have access to?”
