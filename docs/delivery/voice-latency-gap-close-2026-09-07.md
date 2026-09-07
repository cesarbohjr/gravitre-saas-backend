# Voice latency — remaining gap close (2026-09-07)

Tip **`a9551f91`** (after hotfix `32b4b6d3`).

## Cuts (no write-path change)

| Cut | Scope | Effect |
|-----|--------|--------|
| Early speakable flush | Short buffers `<48` chars: word-boundary flush at `min_chars=12` | `ttft→ttfa` **353→~127–180ms** on simple |
| Omit Module D few-shots | `spoken_mode` + `reasoning_depth=conversational` only | Smaller system prompt; write/full keep few-shots |

## Live HTTP `session/turn` (probe — not organic hear)

Duplex one-brain on tip: **PASS** (barge-in, continuation, `write_governance_voice_path`, cognitive kernel) — `voice-duplex-one-brain-live.json`.

| Run | warm TTFA | simple TTFA | write model | notes |
|-----|----------:|------------:|-------------|-------|
| Post-deploy cold | 938 | **3324** | `retrieve_plan_gate` | Prompt-prefix cache miss after few-shot omit; `model_ttft` 2870 |
| Warm 1 | 2381 | **806** | `retrieve_plan_gate` | simple in **700–900** |
| Warm 2 | **687** | **628** | `retrieve_plan_gate` | both in band |
| Warm 3 | **637** | **985** | `retrieve_plan_gate` | simple ~85ms over (model_ttft 668) |

Evidence: `docs/delivery/voice-latency-phases-live.json` on tip `a9551f91` (last warm run in file may be run 3).

## Honest vs 700–900

- **After cache warm:** simple conversational TTFA repeatedly lands in / near **700–900** (628, 806; one 985 variance).
- **First turn after prompt-shape deploy:** can still spike multi-second until OpenAI prompt cache rebuilds — do not treat single cold post-deploy as the feel bar.
- **Write / governance:** still `retrieve_plan_gate`; duplex write gate **PASS** — no regression on that path.
- **Organic Cesar stopwatch on `/ai`:** still **not closed** by this instrument.

## Residual

Nano `model_ttft` variance (~290–670ms warm) remains the floor; further sub-700 needs model/provider or speculative first-audio work, not more RECALL/guard trimming.
