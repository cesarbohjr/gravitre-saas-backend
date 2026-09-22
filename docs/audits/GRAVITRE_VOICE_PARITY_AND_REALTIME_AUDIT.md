# GRAVITRE — VOICE PARITY AND REALTIME AUDIT

**Audit only. Voice is not a separate product.**  
Captured 2026-09-22.

---

## Implemented pipeline (exact)

```
Microphone or synthesized PCM16
  → Pipecat WebSocket /api/voice/pipecat/ws
  → Deepgram Flux (flux-general-en)
  → Gravitre cognitive_llm.py → execute_task_streaming(spoken_mode=True)
  → ElevenLabs eleven_flash_v2_5
  → PCM back on WS
```

HTTP Talk is a **second ingress** with first-audio / completion metrics (not physical mic).

**WebRTC media in production:** `production_allows_webrtc_media() == false` (**CODE INSPECTED**). JSON PCM WS is the live path.

---

## Evidence

| Probe | Result | Level |
|-------|--------|-------|
| HTTP Talk Metric A first audio | p50 254 ms / p95 300 ms n=5 @ 2026-09-21T21:25:48Z SHA `7a2eaaab` | LIVE |
| HTTP Talk Metric B completion | p50 1832 / p95 2432 | LIVE |
| SAPI PCM into Pipecat | session_ready; transcript `is Apollo connected.`; assistant_text empty on that sample SHA `c7d6b115` | LIVE |
| Physical microphone | EXTERNALLY BLOCKED this program | UNKNOWN in-car |
| Barge-in / false interrupt / backchannel | not measured | UNKNOWN |
| Semantic endpointing | Flux+Pipecat | CODE INSPECTED |

---

## Parity (text vs spoken)

Same: `execute_task_streaming`, HMAC, PendingAction, spoken hold_commit for yes-wait, STA-312.

Different by design: Composer spoken shortness; hold without extra LLM.

Hidden forks:

- HTTP Talk vs Pipecat WS (metrics and empty compose on PCM sample).  
- WebRTC denied vs what a “natural assistant” demo expects.  
- Lane B production audio not authorized.  
- Voice cannot complete Google OAuth in a car — same `pending_auth` as text (**correct governance**, bad UX unless the UI explains).

Car script (“biggest deals” → “closing this month” → “send Sarah” → “don’t send, draft”): **architecture supports** follow-ups via task_state; **LIVE equivalent on isolated org** **UNKNOWN** / HubSpot+mail **BLOCKED**.

**VOICE PARITY: PARTIAL**  
**VOICE NATURALNESS: PARTIAL** (HTTP SLO competitive; conversational interruption unproven)

---

## Why it may not feel like a best-in-class voice assistant

1. Cascaded STT→LLM→TTS adds floor latency vs native realtime (HTTP B ~1.8s is OK for tools-off hold; tool turns will inherit 13s LIVE).  
2. Empty spoken compose on PCM sample = silence after a transcript.  
3. No WebRTC = harder barge-in / AEC.  
4. Business vocabulary: Flux general-en — **UNKNOWN** on “HubSpot” / SKUs.  
5. Approval during voice: PendingAction exists; spoken approval UX **UNKNOWN**.

---

## Technology review (do not replace this week)

| Piece | Keep? | Why |
|-------|-------|-----|
| Deepgram Flux | PRESERVE | Live STT proven |
| ElevenLabs flash | PRESERVE | First-audio SLO |
| Pipecat | PRESERVE | WS orchestration; One Brain not Pipecat LLM |
| Native realtime (OpenAI/Gemini/etc.) | EXTEND eval | Latency/naturalness; must still call same kernel for tools |
| Hybrid | likely target | Cascade for tool-heavy; realtime for chit-chat |

Lock-in: Deepgram+EL is real; observability of PCM is better than a black-box realtime model. Tool execution compatibility favors **keeping the brain outside the speech vendor**.

---

## Composer as semantic layer

One answer, many renders: **intended**. Spoken shorter / progressive / interruptible: **partially implemented**. Text more structured: **yes**. Truth identity: **must remain ExecutionPlan + Observations** — Composer must not invent a second outcome.

---

## Waterfall (voice) — measured vs unknown

| Stage | Status |
|-------|--------|
| speech-end → STT final | UNKNOWN (PCM proves transcript, not endpoint ms) |
| STT → reasoning | UNKNOWN |
| reasoning → first text token | UNKNOWN on WS; HTTP A is first **audio** 254ms on hold path |
| TTS submit → first PCM | included in A on HTTP Talk |
| Full tool voice turn | would include UNIFIED_LIVE_RESOLVED ~13.8s — **INFERRED** as naturalness killer |
