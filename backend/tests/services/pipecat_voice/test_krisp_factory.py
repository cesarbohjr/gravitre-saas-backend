"""Krisp VIVA factory — Voice 3.0 Phase 2 eval branch."""
from __future__ import annotations

from app.services.pipecat_voice.krisp_factory import build_krisp_viva_input_filter


def test_krisp_skipped_when_flag_off():
    filt, meta = build_krisp_viva_input_filter(type("S", (), {"voice_krisp": False})())
    assert filt is None
    assert meta["krisp_skip_reason"] == "flag_off"


def test_krisp_skipped_when_model_path_missing():
    filt, meta = build_krisp_viva_input_filter(
        type("S", (), {"voice_krisp": True, "krisp_viva_filter_model_path": ""})()
    )
    assert filt is None
    assert meta["krisp_skip_reason"] == "missing_model_path"
