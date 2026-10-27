"""Production duplex contract tests: run with pytest -q tests/voice/test_voice_duplex_production_contract.py.

These are source-contract regressions, not substitutes for live audio certification.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "apps/web/hooks/use-voice-duplex-session.ts"


def source():
    return HOOK.read_text(encoding="utf-8")


def test_interruption_reports_playback_before_flush():
    s = source()
    start = s.index("const bargeIn =")
    end = s.index("const runSessionTurn =", start)
    block = s[start:end]
    assert block.index('sendPlaybackProgress("barge_in"') < block.index("stopPlayback()")
    assert "encodePipecatInterrupt({ playbackOffsetMs })" in block


def test_server_speech_stop_preserves_work():
    s = source()
    start = s.index('speechInterruptionKind(msg) === "speech_stop"')
    end = s.index('if (kind === "speech.interrupted")', start)
    block = s[start:end]
    assert "speechMutedRef.current = true" in block
    assert "onSpeechStopped" in block
    assert "stopPcmPlayback()" in block


def test_no_audio_fallback_deduplicates_late_pcm():
    s = source()
    assert "audioFallbackTriggeredRef.current = true" in s
    assert "if (audioFallbackTriggeredRef.current) return" in s
    assert "audibleAudioFramesRef.current === 0" in s


def test_audio_context_recovery_and_queue():
    s = source()
    assert "pcmBlockedQueueRef.current.push" in s
    assert "resumeBlockedPlayback" in s
    assert "ensureAudioOutputRunning(ctx)" in s


def test_transport_error_diagnostics_redact_tokens():
    s = source()
    assert "redactVoiceWsUrl(wsUrlRef.current)" in s
    assert "decideSocketFailure({" in s


def test_mute_disables_capture_track():
    s = source()
    assert "track.enabled = !next" in s
    assert "if (micMutedRef.current) return" in s


def test_microphone_ducking_uses_current_presence():
    s = source()
    assert "const presenceRef = useRef(presence)" in s
    assert "presenceRef.current = presence" in s
    assert 'presenceRef.current === "speaking"' in s


def test_stale_pipecat_socket_events_cannot_mutate_new_session():
    s = source()
    assert 'if (wsRef.current !== ws || !isCurrentStartup()) return' in s
    assert 'if (wsRef.current !== ws || !isCurrentStartup()) {' in s
    assert 'An obsolete socket must never retry or complete a newer session.' in s
    assert 'Ignore delayed frames from a socket replaced during recovery.' in s


def test_legacy_endpointing_holds_thoughtful_pauses():
    s = source()
    assert "const scheduleFinal = useCallback" in s
    assert "legacyEndpointDelayMs(text)" in s
    assert "scheduleFinal(finalized)" in s
    assert "scheduleFinal(transcript)" in s


def test_pending_endpointing_is_cancelled_on_stop_and_unmount():
    s = source()
    assert "const clearPendingFinal = useCallback" in s
    assert s.count("clearPendingFinal()") >= 2
    assert "capturedEpoch !== startupEpochRef.current" in s


def test_legacy_barge_in_requires_transcript_not_just_noise():
    s = source()
    assert "legacyInterruptionIntent(transcript, confidence)" in s
    assert "function legacyInterruptionIntent(" in s


def test_duplicate_stt_final_does_not_start_second_reply():
    s = source()
    assert "normalizeTranscript(transcript) === normalizeTranscript(lastUserFinalRef.current)" in s
    assert "lastUserFinalRef.current = ready" in s
    assert "previousNorm.endsWith(nextNorm)" in s


def test_voice_cleanup_cancels_pending_final_before_teardown():
    s = source()
    start = s.index("const stop = useCallback")
    end = s.index("const toggle = useCallback", start)
    assert "clearPendingFinal()" in s[start:end]
    start = s.index("// Unmount only.")
    end = s.index("return {\n    presence,", start)
    assert "clearPendingFinal()" in s[start:end]


def test_legacy_turn_end_has_contextual_pause_classes():
    s = source()
    assert "function legacyEndpointDelayMs(" in s
    assert "return 1250" in s
    assert "return 380" in s
    assert "return 850" in s


def test_explicit_short_stop_commands_interrupt_without_two_word_requirement():
    s = source()
    assert "stop|wait|pause|hold on|cancel|no stop|hang on" in s
    assert "legacyInterruptionIntent(transcript, confidence)" in s


def test_legacy_tts_preloads_next_segment_and_promotes_standby():
    s = source()
    assert "const preloadNextAudio = useCallback" in s
    assert 'el.preload = "auto"' in s
    assert "standbyBlobRef.current === next" in s
    assert "if (playingRef.current) preloadNextAudio()" in s


def test_interruption_invalidates_pending_media_start_and_releases_urls():
    s = source()
    assert "playbackGenerationRef.current += 1" in s
    assert "generation !== playbackGenerationRef.current" in s
    assert "URL.revokeObjectURL(standbyUrlRef.current)" in s
    assert "URL.revokeObjectURL(playingUrlRef.current)" in s


def test_legacy_tts_uses_single_sample_clock_when_decode_succeeds():
    s = source()
    assert "ctx.decodeAudioData(" in s
    assert "scheduledTtsUntilRef.current" in s
    assert "source.start(startAt)" in s
    assert "ttsDecodeChainRef.current.then(async () =>" in s


def test_legacy_tts_fallback_stays_on_one_output_clock():
    s = source()
    assert "ttsHtmlFallbackRef.current = true" in s
    assert "!ttsHtmlFallbackRef.current && await scheduleDecodedTts" in s


def test_legacy_tts_interruption_stops_scheduled_sources():
    s = source()
    assert "for (const source of scheduledTtsSourcesRef.current)" in s
    assert "scheduledTtsUntilRef.current = 0" in s
