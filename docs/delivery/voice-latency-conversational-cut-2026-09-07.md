# Voice latency cut — conversational depth (2026-09-07)

Human hear gate **bypassed** per Cesar. Target: simple spoken TTFA **700–900ms**.

## Shipped (tip `5c271d54` / measure tip may be this or `0b01c623`)

| Cut | Effect |
|-----|--------|
| Force `gpt-4o-mini` when `reasoning_depth=conversational` | Stops ambiguous simple turns from paying `gpt-5.4-mini` |
| Skip spoken conversational RECALL | RECALL stage **0.0ms** on simple |
| Skip lite dialogue/persona DB + async ledger | Less pre-kernel DB |
| Defer tiktoken on spoken conversational | Less pre-create CPU |
| Skip LIVE channel/meta/pending when no pending family | Guard short-circuit |

Write-shaped path unchanged (full RECALL, full guards, task model tier).

## Live HTTP instrument (not FE mic)

| Tip | Simple TTFA | Model | vs 700–900 |
|-----|------------:|-------|------------|
| Baseline pre-cut `c4dd7ae1` | 1666 | gpt-5.4-mini | miss |
| `0b01c623` (mini+RECALL skip) | **1526** | gpt-4o-mini | miss |
| `5c271d54` (guards skip) | **1596** | gpt-4o-mini | miss (noise vs 1526) |
| Turn2 on `0b01c623` | **990** | gpt-5.4-mini | near |

Evidence: `docs/delivery/voice-latency-phases-live.json`

**Honest:** 700–900 **not met** on cold/simple. Floor ≈ `model_ttft` (~580ms) + `ttft→ttfa` (~200ms TTS) + residual setup (~400–700ms). Next levers would be smaller/faster model (nano), prompt shrink, or speculative first-token — not more RECALL/guard trimming.

Organic hear still OPEN (bypassed, not closed).
