# Voice latency — gpt-5.4-nano pin + speculative EOT (2026-09-07)

## Shipped (`5b184ab7`)

| Item | Status |
|------|--------|
| Conversational spoken model pin | **`gpt-5.4-nano`** via `VOICE_CONVERSATIONAL_MODEL` (default); `reasoning_effort=none` |
| Speculative LLM on Flux probable-EOT | **Already live** — tightened punctuation-tolerant adopt + `min_chars=8` |
| Write/full depth | Unchanged (task tier / agent pin) |

## Live HTTP instrument tip `5b184ab7`

| Scenario | TTFT | TTFA | Model | vs 700–900 |
|----------|-----:|-----:|-------|------------|
| Prior (`5c271d54`) simple | 1354 | 1596 | gpt-4o-mini | miss |
| **This tip simple** | **780** | **961** | **gpt-5.4-nano** | **near miss** (~60ms over 900) |

Evidence: `docs/delivery/voice-latency-phases-live.json` claim on tip `5b184ab7`.

**Honest:** Infra + nano cut simple TTFA ~1600→**961**. Still not a clean PASS on 700–900 (961). Speculative EOT helps Pipecat FE path (not this HTTP finalized-text instrument). Override: `VOICE_CONVERSATIONAL_MODEL`.
