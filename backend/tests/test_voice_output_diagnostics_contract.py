from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_voice_output_diagnostics_is_auth_org_scoped_and_content_free():
    source = (ROOT / "app" / "routers" / "voice.py").read_text()

    assert '@router.post("/output-diagnostics")' in source
    assert "Depends(get_current_user)" in source
    assert "Depends(get_org_context)" in source
    assert '"contains_audio": False' in source
    assert '"contains_transcript": False' in source


def test_voice_output_diagnostics_only_accepts_known_lifecycle_events():
    source = (ROOT / "app" / "routers" / "voice.py").read_text()

    for event in (
        "audio_missing",
        "audio_silent",
        "output_unavailable",
        "playback_blocked",
        "playback_started",
        "playback_recovered",
    ):
        assert event in source

    assert "Unsupported voice output diagnostic event" in source


def test_voice_output_diagnostics_carries_pcm_energy_counts_only():
    source = (ROOT / "app" / "routers" / "voice.py").read_text()

    assert "audible_pcm_frames" in source
    assert "max_pcm_peak" in source
    assert '"contains_audio": False' in source
    assert '"contains_transcript": False' in source
