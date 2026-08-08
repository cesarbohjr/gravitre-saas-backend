"""Async acoustic/prosody signal for GIBE — never blocks the realtime turn loop.

Honesty (Module C): short clear emotional speech literature reports ~78–91%
accuracy; longer complex conversational speech ~54–60%. Insights MUST be labeled
with real confidence and surfaced as flagged-for-review, never autonomous actions.
"""
from __future__ import annotations

import asyncio
import math
import struct
import wave
from io import BytesIO
from typing import Any

from app.core.logging import get_logger
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    label_confidence,
)

logger = get_logger(__name__)

# Documented accuracy bands for honest labeling.
ACCURACY_BAND_SHORT_CLEAR = (0.78, 0.91)
ACCURACY_BAND_LONG_COMPLEX = (0.54, 0.60)


def _pcm_from_wav_or_raw(audio_bytes: bytes) -> tuple[list[float], int]:
    """Best-effort PCM float samples. Supports WAV; otherwise treats as s16le @16k."""
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF":
        try:
            with wave.open(BytesIO(audio_bytes), "rb") as wf:
                rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
                width = wf.getsampwidth()
                nch = wf.getnchannels()
        except Exception:  # noqa: BLE001
            rate = 16000
            frames = audio_bytes
            width = 2
            nch = 1
    else:
        rate = 16000
        frames = audio_bytes
        width = 2
        nch = 1
    if width != 2:
        # Downsample unsupported widths to empty → insufficient_data path
        return [], rate
    count = len(frames) // (2 * nch)
    samples: list[float] = []
    for i in range(count):
        # Take first channel
        off = i * 2 * nch
        val = struct.unpack_from("<h", frames, off)[0] / 32768.0
        samples.append(val)
    return samples, rate


def extract_acoustic_features(audio_bytes: bytes) -> dict[str, Any]:
    """Lightweight prosody features (pitch proxy, pace, pauses, intensity).

    Uses signal-processing heuristics (zero-crossing + energy envelope) as a
    deployable stand-in for Wav2Vec/HuBERT embeddings when those models are not
    loaded. Same honesty labeling applies.
    """
    samples, rate = _pcm_from_wav_or_raw(audio_bytes)
    if len(samples) < rate // 4:
        return {
            "ok": False,
            "reason": "audio_too_short",
            "duration_secs": len(samples) / max(rate, 1),
        }
    duration = len(samples) / rate
    # Frame energy
    frame = max(int(rate * 0.02), 1)
    energies: list[float] = []
    zcrs: list[float] = []
    for i in range(0, len(samples) - frame, frame):
        chunk = samples[i : i + frame]
        e = math.sqrt(sum(x * x for x in chunk) / len(chunk))
        energies.append(e)
        zc = sum(1 for a, b in zip(chunk, chunk[1:]) if (a >= 0) != (b >= 0)) / len(chunk)
        zcrs.append(zc)
    if not energies:
        return {"ok": False, "reason": "no_frames", "duration_secs": duration}
    mean_e = sum(energies) / len(energies)
    var_e = sum((e - mean_e) ** 2 for e in energies) / len(energies)
    mean_z = sum(zcrs) / len(zcrs)
    # Pause: frames below 15% of mean energy
    thresh = mean_e * 0.15
    pause_frames = sum(1 for e in energies if e < thresh)
    pause_ratio = pause_frames / len(energies)
    # Pace proxy: speech frames per second
    speech_frames = len(energies) - pause_frames
    pace = (speech_frames * 0.02) / max(duration, 0.01)
    # Intensity shifts: consecutive energy delta
    shifts = [abs(energies[i] - energies[i - 1]) for i in range(1, len(energies))]
    intensity_shift = sum(shifts) / max(len(shifts), 1)
    # Heuristic affect flags (NOT certain emotion labels)
    flags: list[str] = []
    if var_e > (mean_e**2) * 0.8 and intensity_shift > mean_e * 0.35:
        flags.append("elevated_intensity_variance")
    if pause_ratio > 0.45:
        flags.append("long_pause_pattern")
    if pace > 0.85 and mean_z > 0.12:
        flags.append("rapid_pace")
    if pace < 0.35:
        flags.append("slow_pace")
    band = ACCURACY_BAND_SHORT_CLEAR if duration <= 8.0 else ACCURACY_BAND_LONG_COMPLEX
    # Midpoint of documented band as estimate; Module C labels it heuristic.
    estimated = (band[0] + band[1]) / 2.0
    labeled = label_confidence(estimated, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True)
    honesty_note = (
        f"Acoustic/prosody heuristic on {duration:.1f}s audio. Literature accuracy "
        f"~{int(band[0]*100)}–{int(band[1]*100)}% for "
        f"{'short clear' if duration <= 8 else 'longer conversational'} speech — "
        "not a certain fact."
    )
    return {
        "ok": True,
        "duration_secs": round(duration, 3),
        "features": {
            "pitch_proxy_zcr_mean": round(mean_z, 4),
            "pace": round(pace, 4),
            "pause_ratio": round(pause_ratio, 4),
            "vocal_intensity_mean": round(mean_e, 4),
            "vocal_intensity_variance": round(var_e, 6),
            "intensity_shift_mean": round(intensity_shift, 4),
        },
        "signal_flags": flags,
        "accuracy_band": {"low": band[0], "high": band[1]},
        "confidence": labeled,
        "honesty_note": honesty_note,
        "model_family": "lightweight_energy_zcr_heuristic",
        "model_note": (
            "Production path uses lightweight acoustic features. Wav2Vec/HuBERT-class "
            "embeddings can replace the feature extractor without changing the GIBE "
            "ingest or honesty labeling contract."
        ),
        "autonomous_action": False,
        "review_required": bool(flags),
    }


def schedule_acoustic_analysis(
    *,
    client: Any,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    audio_bytes: bytes,
    agent_id: str | None = None,
) -> None:
    """Fire-and-forget background analysis — never awaited on the turn path."""

    async def _run() -> None:
        try:
            result = await asyncio.to_thread(extract_acoustic_features, audio_bytes)
            await asyncio.to_thread(
                _persist_acoustic_signal,
                client,
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                agent_id=agent_id,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("voice_acoustic_analysis_failed org_id=%s error=%s", org_id, str(exc)[:200])

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        # No loop (sync context) — run inline in a thread from caller if needed
        logger.debug("voice_acoustic_schedule_no_loop org_id=%s", org_id)


def _persist_acoustic_signal(
    client: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    agent_id: str | None,
    result: dict[str, Any],
) -> None:
    """Write into existing learning/flagged surfaces when possible."""
    if not result.get("ok"):
        return
    payload = {
        "org_id": org_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "agent_id": agent_id,
        "signal_type": "voice_acoustic_prosody",
        "surface": "voice",
        "flagged_for_review": bool(result.get("review_required")),
        "confidence": result.get("confidence"),
        "features": result.get("features"),
        "signal_flags": result.get("signal_flags") or [],
        "accuracy_band": result.get("accuracy_band"),
        "autonomous_action": False,
        "metadata": {
            "model_family": result.get("model_family"),
            "model_note": result.get("model_note"),
            "duration_secs": result.get("duration_secs"),
        },
    }
    # Same audit + learning surfaces as text; acoustic is an ADDITIONAL signal.
    try:
        client.table("audit_events").insert(
            {
                "org_id": org_id,
                "actor_id": user_id,
                "action": "voice.acoustic.flagged_for_review"
                if payload["flagged_for_review"]
                else "voice.acoustic.analyzed",
                "resource_type": "voice_turn",
                "resource_id": conversation_id,
                "metadata": payload,
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_acoustic_persist_failed org_id=%s error=%s", org_id, str(exc)[:200])
    try:
        from app.services.learning_signal_aggregator import LearningSignalAggregator

        # Sync bridge: schedule async ingest when a loop exists.
        async def _ingest() -> None:
            agg = LearningSignalAggregator(client)
            await agg.ingest(
                org_id,
                "voice_acoustic_prosody",
                "neutral",
                surface="voice",
                metadata=payload,
            )

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_ingest())
        except RuntimeError:
            pass
    except Exception:  # noqa: BLE001
        pass


def other_missing_ml_capabilities_report() -> list[dict[str, Any]]:
    """Phase 6.3 — honest audit of beneficial missing voice ML (report only)."""
    return [
        {
            "capability": "speaker_diarization_multi_party",
            "benefit": "Separate overlapping speakers in shared-device rooms",
            "fit": "Useful later for conference-mode; not required for 1:1 agent chat",
            "build_now": False,
        },
        {
            "capability": "barge_in_acoustic_cancel",
            "benefit": "Cleaner interruption when user talks over TTS",
            "fit": "Partially covered by provisional turn-taking; full AEC is client/device",
            "build_now": False,
        },
        {
            "capability": "language_id_from_audio",
            "benefit": "Auto-switch STT language",
            "fit": "Nice-to-have; agents declare language on voice_profile today",
            "build_now": False,
        },
    ]
