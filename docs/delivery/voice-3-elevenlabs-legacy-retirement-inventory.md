# Voice 3.0 — ElevenLabs legacy retirement inventory

Status: **inventory confirmed in source; retirement NOT authorized until dependency and live-path verification**. Scope: older ElevenLabs voice presets, model aliases and HTTP routes, not unrelated Gravitre features.

## Confirmed source inventory

- `backend/app/services/tier1_voice_service.py` exposes named presets `sarah`, `rachel`, `adam`, `josh`, `eric`, with configurable IDs and a default `sarah`. These are **active compatibility inputs**, not proven unused assets.
- `resolve_voice_id` accepts raw case-sensitive ElevenLabs IDs and agent voice-profile overrides; do not break these while retiring old UI choices.
- The same service retains non-Pipecat HTTP TTS and streaming endpoints, Turbo-to-Flash model aliases, and MP3 output-format aliases. Usage is **unverified**; do not delete these routes solely because they are called legacy.
- `backend/app/services/pipecat_voice/tts_factory.py` supports Flash/Turbo/Multilingual streaming protocols and a separate v3 Dialogue adapter.
- `backend/app/services/pipecat_voice/pipeline.py` currently forces `eleven_v3` and several older models back to Flash v2.5 on the live conversational path. The Flash guard is deliberate and **must remain** until paired audio, cancellation and provider protocol acceptance proves a replacement.
- Conversational register expansion and regression tests are in PR #610; those changes do not themselves retire provider assets.

## Retirement sequence and evidence

1. Inventory all callers of named voice keys, raw IDs, model aliases, HTTP TTS routes, agent voice profiles and persisted customer settings. Record actual production configuration without logging secrets or raw audio.
2. Classify each as active, compatibility-required, or unused with call-site and deployment evidence. Identify which voice ID(s) the user approves as the Voice 3.0 default.
3. Add red/green tests for the approved replacement: voice selection, agent overrides, missing IDs, reconnect, mid-sentence pause, barge-in, PCM continuity, TTS model compatibility and rollback.
4. Hide deprecated choices in the Voice 3.0 selection UI **only after** saved configurations have a migration path; keep server compatibility temporarily.
5. Retire unused aliases/routes only after caller inventory, test coverage, rollback plan and controlled deployment confirm no dependency.
6. Never delete ElevenLabs provider-side voice assets without explicit separate approval. Do not remove Flash fallback before v3 Dialogue meets latency, quality and interruption criteria.

## Certification state

No older ElevenLabs voice IDs, routes, or provider assets have been deleted by this inventory change. No live voice provider switch, merge or deployment. Exact-head CI and real-device acceptance remain outstanding.
