# Voice cold-path latency — attribution (tip `fe9828dc`)

Artifact: [`voice-latency-cold-path-breakdown-live.json`](voice-latency-cold-path-breakdown-live.json)  
Cold turn: `1781fe97-6156-467d-b6b7-add79aebc1b4` · TTFT **5440ms** · TTFA **5637ms** · `spoken_streamed=true`

## Where the ~5.4s cold conversational TTFT goes

Wall clocks from `voice.session` start (not including client STT):

| Segment | ms | Share of TTFT | What it is |
|---------|---:|--------------:|------------|
| Early setup → first routing SSE (`classify_setup_ms`) | **975** | 18% | Mode/routing bootstrap before classify |
| Rest of pre-ACT to kernel complete (`pre_act_done_ms` − setup − kernel stages) | **~2736** | **50%** | Sentiment / contextual understand / task classify / enrich / persona / ledger — **not** Knowledge Fabric (skipped) |
| Kernel stage sum (RECALL…) | **166** | 3% | RECALL 166; KNOWLEDGE **0** (conversational depth) |
| Unified pre-model (`pre_model_ms`) | **621** | 11% | Prompt/tool assembly inside unified LIVE |
| Model TTFT (`model_ttft_ms`) | **873** | 16% | OpenAI first token on this workload (`gpt-5.4-mini`) |
| Pre-ACT → voice TTFT residual | ~69 | ~1% | Queue/SSE handoff |
| **TTFT** | **5440** | 100% | |
| TTFT → TTFA | **197** | — | ElevenLabs first audio after speakable chunk |

### What it is *not*

- **Not** TTS waiting for a fuller verified answer — `spoken_streamed=true`; TTFA is only **+197ms** after first text.
- **Not** mandatory critic / Knowledge Fabric on this cold conversational turn (KNOWLEDGE=0; VERIFY=0).
- **Not** primarily raw model generation wall — model first-token is **873ms**; the answer body after that does not block TTFT under streaming.

### Dominant cold-path cost (honest)

**~3.9s before any model token is requested for speech** — early chat pipeline + RECALL — then **~1.5s** unified assembly + model TTFT. Closing cold conversational latency means shrinking the pre-ACT chat/classify/enrich path on spoken conversational turns, not further TTS streaming tweaks.

## Short-answer TTFA bug

| Probe | Text | TTFA | Audio deltas | Verdict |
|-------|------|-----:|-------------:|---------|
| `Four.` | present | **9693** (slow TTS RTT this sample, but not null) | 6 | **PASS** — no longer null |
| bare `4` | present | **6764** | 5 | **PASS** — flush-before-complete |

Fix: terminal punctuation without trailing whitespace in `split_speakable_chunks`, plus defer `voice.turn.complete` until TTS flush.
