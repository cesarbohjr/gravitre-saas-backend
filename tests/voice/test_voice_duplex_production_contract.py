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
