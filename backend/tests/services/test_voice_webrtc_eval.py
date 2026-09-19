"""3.0-C WebRTC eval is measurement-only; production stays WebSocket."""
from __future__ import annotations

from app.services.voice_realtime_eval import eval_card, production_allows_lane, LANE_B
from app.services.voice_webrtc_eval import (
    PRODUCTION_MEDIA_TRANSPORT,
    evaluate_webrtc_sample,
    production_allows_webrtc_media,
    production_media_transport,
    webrtc_eval_card,
)


def test_production_transport_is_websocket_not_webrtc():
    assert production_media_transport() == PRODUCTION_MEDIA_TRANSPORT
    assert production_allows_webrtc_media() is False
    card = webrtc_eval_card()
    assert card["not_model_ttft"] is True
    assert card["production_allows_webrtc"] is False


def test_eval_card_includes_webrtc_without_enabling_lane_b():
    card = eval_card(lane="A_CASCADE")
    assert card["webrtc"]["production_transport"] == PRODUCTION_MEDIA_TRANSPORT
    assert production_allows_lane(LANE_B) is False


def test_incomplete_webrtc_sample_is_not_invented_complete():
    scored = evaluate_webrtc_sample({"media_rtt_ms": 40, "region": "iad"})
    assert scored["complete"] is False
    assert "connection_startup_ms" in scored["missing"]


def test_full_webrtc_sample_validates_ranges():
    scored = evaluate_webrtc_sample(
        {
            "connection_startup_ms": 180,
            "media_rtt_ms": 42,
            "jitter_ms": 8,
            "packet_loss_ratio": 0.01,
            "reconnect_ms": 250,
            "region": "sfo",
        }
    )
    assert scored["complete"] is True
    assert scored["numeric_ok"] is True


def test_invalid_loss_ratio_rejected():
    scored = evaluate_webrtc_sample(
        {
            "connection_startup_ms": 1,
            "media_rtt_ms": 1,
            "jitter_ms": 1,
            "packet_loss_ratio": 1.5,
            "reconnect_ms": 1,
            "region": "iad",
        }
    )
    assert scored["complete"] is False
    assert scored["numeric_ok"] is False
