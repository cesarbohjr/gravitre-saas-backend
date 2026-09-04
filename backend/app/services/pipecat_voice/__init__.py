"""Pipecat voice orchestration — Deepgram STT + CognitiveTurnKernel + ElevenLabs TTS.

Phase 1: flag-gated (`VOICE_PIPECAT_ENABLED`). Existing `/api/voice/session/turn` duplex
remains the default path. This package does NOT replace governance, memory, or honesty —
`GravitreCognitiveLLMService` calls `execute_task_streaming(spoken_mode=True)`.
"""
