# STA-339 append (Linear MCP unavailable at ship time)

Paste into [STA-339](https://linear.app/staqbot/issue/STA-339/mcp-gap-part-3-pack-one-shot-clarify-vs-approve) and set status **Done**.

## Shipped (2026-08-03)

Hard battery **PASS** on tip `2cafd118` (includes pack-common staging `9bacd586`). Artifact commit: `43f0f884`.

### Rates

| Metric | Baseline `722dab11` | Post-fix `2cafd118` |
| -- | -- | -- |
| approve_first_rate | 0.25 | **0.75** |
| clarify_once_rate | 0.0 | **1.0** |
| hard_pass | 0/7 | **6/6** |

### Evidence pointers

* HubSpot MSPs approve-first: `unified_turn.live.completed` @ `2026-08-03T04:24:19.308669Z` audit `e4c73ddb-3916-47ce-bf0b-c4acfb8143c2` · `hubspot.lists.create`
* Ambiguous enrich clarify: audit `7e471272-f8e1-4baf-8f08-c3708c775611`
* Add members clarify: audit `b97b8a21-fd78-4f94-bb77-f30853d9d391`
* Artifact: `docs/delivery/part3-pack-oneshot-approve-battery-live.json`
* Baseline: `docs/delivery/part3-pack-oneshot-approve-battery-baseline-722dab11.json`

### Commits

`cbec815c` pack defaults · `ac538cc8` battery · `21e2afb6` HubSpot mapper · `375422c9` short-circuit · `9bacd586` LIVE staging · `43f0f884` live artifact

### Soft (not hard blockers)

* `clay_enrich_msp_chain` — multi-step still drafts/clarifies (Clay connect / workflow)
* `meta_while_awaiting_params` — HubSpot deal meta control outside pack-common

Related: STA-338 Slice A Done.
