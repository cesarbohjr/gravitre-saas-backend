"""Optional Krisp VIVA voice isolation for Pipecat (Voice 3.0 Phase 2 eval branch)."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def build_krisp_viva_input_filter(settings: Any) -> tuple[Any | None, dict[str, Any]]:
    """Return (filter, meta). Never raises — missing SDK/credentials → None + honest meta."""
    enabled = bool(getattr(settings, "voice_krisp", False))
    meta: dict[str, Any] = {
        "krisp_requested": enabled,
        "krisp_active": False,
    }
    if not enabled:
        meta["krisp_skip_reason"] = "flag_off"
        return None, meta

    model_path = (getattr(settings, "krisp_viva_filter_model_path", None) or "").strip()
    api_key = (getattr(settings, "krisp_viva_api_key", None) or "").strip()
    if not model_path:
        meta["krisp_skip_reason"] = "missing_model_path"
        logger.warning("voice_krisp_skipped reason=missing_KRISP_VIVA_FILTER_MODEL_PATH")
        return None, meta

    try:
        from pipecat.audio.filters.krisp_viva_filter import KrispVivaFilter
    except ImportError as exc:
        meta["krisp_skip_reason"] = "krisp_audio_not_installed"
        logger.warning("voice_krisp_skipped reason=krisp_audio_not_installed error=%s", exc)
        return None, meta

    try:
        filt = KrispVivaFilter(model_path=model_path, api_key=api_key or None)
    except Exception as exc:  # noqa: BLE001
        meta["krisp_skip_reason"] = "init_failed"
        meta["krisp_init_error"] = str(exc)[:200]
        logger.warning("voice_krisp_init_failed error=%s", exc)
        return None, meta

    meta["krisp_active"] = True
    meta["krisp_model_path"] = model_path
    return filt, meta
