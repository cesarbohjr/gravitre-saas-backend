"""WebRTC media-path eval — not a production transport swap.

Production voice stays JSON PCM16 over FastAPI WebSocket. Native WebRTC is an
eval lane that measures *connection* quality, never model TTFT and never
replaces cascade lane A.

Metrics (3.0-C): connection startup, media RTT, jitter, packet loss, reconnect,
region.
"""
from __future__ import annotations

from typing import Any

PRODUCTION_MEDIA_TRANSPORT = "websocket_pcm16_json"
EVAL_MEDIA_TRANSPORT = "webrtc"

WEBRTC_EVAL_METRICS = (
    "connection_startup_ms",
    "media_rtt_ms",
    "jitter_ms",
    "packet_loss_ratio",
    "reconnect_ms",
    "region",
)

AUDIT_WEBRTC_EVAL = "voice.webrtc.eval_sample"


def production_media_transport() -> str:
    return PRODUCTION_MEDIA_TRANSPORT


def production_allows_webrtc_media() -> bool:
    return False


def webrtc_eval_card() -> dict[str, Any]:
    return {
        "production_transport": PRODUCTION_MEDIA_TRANSPORT,
        "eval_transport": EVAL_MEDIA_TRANSPORT,
        "production_allows_webrtc": production_allows_webrtc_media(),
        "metrics": list(WEBRTC_EVAL_METRICS),
        "not_model_ttft": True,
        "not_metric_a": True,
        "not_metric_b": True,
    }


def evaluate_webrtc_sample(sample: dict[str, Any] | None) -> dict[str, Any]:
    """Validate an eval sample. Missing fields stay missing — do not invent."""
    row = sample if isinstance(sample, dict) else {}
    present = [k for k in WEBRTC_EVAL_METRICS if row.get(k) is not None]
    missing = [k for k in WEBRTC_EVAL_METRICS if k not in present]
    numeric_ok = True
    for key in (
        "connection_startup_ms",
        "media_rtt_ms",
        "jitter_ms",
        "reconnect_ms",
    ):
        val = row.get(key)
        if val is None:
            continue
        try:
            if float(val) < 0:
                numeric_ok = False
        except (TypeError, ValueError):
            numeric_ok = False
    loss = row.get("packet_loss_ratio")
    if loss is not None:
        try:
            ratio = float(loss)
            if ratio < 0 or ratio > 1:
                numeric_ok = False
        except (TypeError, ValueError):
            numeric_ok = False
    return {
        **webrtc_eval_card(),
        "present": present,
        "missing": missing,
        "complete": not missing and numeric_ok,
        "numeric_ok": numeric_ok,
        "region": row.get("region"),
    }
