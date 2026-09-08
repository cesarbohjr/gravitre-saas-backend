# Default voice swap — Rachel → Sarah (2026-09-07)

## Last human test context

Addendum 8 (`voice-slo-parallelism-standard-2026-09-05.md`) human gate was about **glued TTS sentences** (`.Found` / `.I`) making speech sound robotic — fixed with word-boundary spaces. That was **not** a voice-identity change; product default remained **Rachel**.

Cesar re-tested live and reported the voice still sounds unnatural / robotic — request: pick a better, more normal default.

## Change

| Before | After |
|--------|-------|
| Default key `rachel` (`21m00Tcm4TlvDq8ikWAM`) | Default key **`sarah`** (`EXAVITQu4vr4xnSDxMaL`) |
| Descriptor: clear professional | Soft, reassuring, natural conversational (curated library) |
| HTTP TTS stability 0.4 / sim 0.75 | Slightly more expressive: **0.35 / 0.8** |

Rachel / Adam / Josh remain selectable; Eric added as a friendly male shortcut.

Agents with an explicit `voice_profile.voice_id` are unchanged — only the unset/default path moves to Sarah.

## Verify

1. Talk on `/ai` without a custom agent voice — hear Sarah.
2. If an agent still has Rachel assigned, re-pick Sarah (or another library voice) in voice assignment.
3. Organic hear still closes quality; this commit only changes the default identity + mild settings.
