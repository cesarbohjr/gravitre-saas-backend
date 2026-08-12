# Meta capability → web search — Phase 0 (2026-08-12)

## Reproduction

| Field | Value |
| -- | -- |
| Agent | Marketing Analyst `c4940fc5-357d-5b3e-9bbc-704febe7d86c` |
| Query | `What can you help me with?` |
| Conversation | `21d727ff-36ad-4460-b9c1-032bfc6edc0c` |
| Tip at repro | `40a571526cc06f153e4125a13bd5264c6e5288eb` |
| Path | LIVE `unified_turn.live.completed` |

## Mechanism (confirmed)

1. `re_search_meta` only matched `what can you do` — **not** “help me with”.
2. LIVE meta short-circuit skipped → knowledge prefetch ran (`should_augment` true on `?` / “what”).
3. Internal thin → auto internet → `search_web` (Serper).
4. Billed: `usage_records` id `6e05b8f9-4b29-4432-8f58-6bb317db5e6d` · `metric_type=research_lookups` · `provider=serper` @ `2026-08-12T18:27:58Z`.

Also billed on probe: “what tools do you have access to?” (Sales). “what are you able to do?” did **not** bill in that run (partial prior coverage).

## Historical COGS note

Org sample of 77 recent `research_lookups` rows did not store raw query text in metadata, so class-frequency via metadata was **0 detectable**. Live repro above is the hard COGS evidence for this bug class.

Artifact: `meta-capability-no-research-phase0.json`
