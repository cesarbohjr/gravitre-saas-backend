# Speech interface — Gravitree chat (STT/TTS adapter)

Input/output adapter in front of the existing chat pipeline. Voice input becomes text and enters Module B's turn controller exactly like a typed message.

## Phase 0 — Provider decision and wiring audit

### STT provider

**Browser-native Web Speech API** (`SpeechRecognition` / `webkitSpeechRecognition`).

- Zero cost ($0)
- Streaming interim results into the composer (same UX goal as partial SSE text)
- No backend changes; no shortcut path around Module B

Paid Whisper API deferred unless browser accuracy proves insufficient in real use.

### TTS provider

**Browser-native `speechSynthesis`**.

- Zero cost ($0)
- Per-message "Read aloud" button (safer default than auto-play-all)
- Markdown cleaned before speaking (`apps/web/lib/speech-text.ts`)

Paid ElevenLabs/OpenAI TTS deferred unless quality proves insufficient in real use.

### Message send entry point (confirmed)

| Surface | Frontend entry | Backend entry | Module B |
|---------|----------------|---------------|----------|
| `/ai` chat | `submitPrompt` → `runChat` → `sendMessage({ text })` | `POST /api/assistant/chat` → `assistant_chat()` | `run_connector_turn(source="chat")` |
| Agent chat | `submitText` → `sendMessage({ text })` | same | same |
| ReAct fallback | same HTTP path | `run_connector_fallback_turn` | `run_connector_turn(source="react")` |

Voice transcribed text is injected into the **same** `sendMessage({ text })` / `submitPrompt` path — no special casing.

### Streaming partial content pattern

Partial transcription updates the composer `textarea` value via React state (`onChange`), analogous to streaming assistant `text-delta` updating message parts. No new SSE mechanism.

Relevant files:

- `apps/web/hooks/use-speech-recognition.ts`
- `apps/web/components/gravitre/assistant/voice-input-button.tsx`

## Phase 1 — Speech-to-text

- Mic button in `/ai` composer, landing composer, and agent chat composer
- Tap-to-start / tap-to-stop UX
- Interim + final transcripts stream into the input field; user edits before send
- Clear errors: permission denied, no speech, no microphone, network, unsupported browser
- `Permissions-Policy` updated: `microphone=(self)` in `apps/web/next.config.mjs`

## Phase 2 — Text-to-speech

- Per-message **Read aloud** on `ChatTranscript` and agent chat messages
- `textForSpeech()` strips code blocks, links, markdown structure
- Respects Module D polished assistant text (`polishAssistantText`) before TTS

## Phase 3 — Cost check

| Component | Provider | Cost |
|-----------|----------|------|
| STT | Web Speech API | **$0** |
| TTS | speechSynthesis | **$0** |

**Heavy usage model (1 hr/day voice, 22 business days): $0/month per user.**

Compare to Research Lookups ($35/1k queries above free tier). Voice cost does **not** warrant metering. Ship unmetered, bundled into plan price. **No metering system built.**

## Phase 4 — Accessibility and platform parity

- Mic button: `aria-label`, `aria-pressed`, `title`
- Read aloud: `aria-label`, `aria-pressed`
- Mic hidden when browser lacks SpeechRecognition (graceful degradation)
- Mobile web: same components; browser handles permission prompts (`min-h-[44px]` composer already touch-friendly)

## Files added/changed

```
apps/web/lib/speech-text.ts
apps/web/lib/speech-recognition.ts
apps/web/hooks/use-speech-recognition.ts
apps/web/hooks/use-speech-synthesis.ts
apps/web/components/gravitre/assistant/voice-input-button.tsx
apps/web/components/gravitre/assistant/read-aloud-button.tsx
apps/web/app/ai/_components/ai-workspace.tsx
apps/web/app/ai/_components/ai-landing.tsx
apps/web/components/gravitre/assistant/chat-transcript.tsx
apps/web/app/agents/[id]/chat/page.tsx
apps/web/next.config.mjs
apps/web/__tests__/lib/speech-text.test.ts
```

## Live verification checklist (post-deploy)

Run against deployed tip with fresh `git_sha`:

1. Full voice round-trip: speak → transcribe → send → read aloud
2. Memory: voice-stated value referenced in follow-up (typed or spoken)
3. Permission denied + silence/no-speech → clear toast messages
4. Response with link + code + plain sentence → TTS skips/rephrases non-speakable parts
5. ARIA labels present on mic and read-aloud controls

Status: **NOT RUN** until merge → Railway redeploy → prod chat re-run with trace.
