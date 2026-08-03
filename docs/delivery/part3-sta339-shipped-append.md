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

### Soft leftovers follow-up (2026-08-03) — re-verified

Tip `49e4a75d` (includes `22451f99` pack-common MSP Clay enrich).

| Metric | Was | Now |
|--------|-----|-----|
| approve_first_rate | 0.75 | **0.8** (4/5) |
| hard_pass | 6/6 | **7/7** |
| soft_fail | 2 | **0** |

* `clay_enrich_msp_chain` — **PASS approve_first** · `assistant.create_workflow` · audit `37359b12-c2a6-4db7-80ce-990eba5e2006` @ `2026-08-03T09:28:06.60745Z` (prior run; re-battery PASS on tip)
* `meta_while_awaiting_params` — soft control OK (seed deal clarify; non-executing follow-up)
* Artifact: `docs/delivery/part3-pack-oneshot-approve-battery-live.json` verdict **PASS**

Related: STA-338 Slice A Done · Part 2 `a64d91b1` · STA-337 remediation `8502cad7`.
