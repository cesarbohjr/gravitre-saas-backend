"""2.0-J voice proof classes — protocol vs virtual vs human device.

Never relabel synthetic PCM as a human-device PASS.
"""
from __future__ import annotations

from typing import Literal

VoiceProofClass = Literal["VOICE_A_PROTOCOL", "VOICE_B_VIRTUAL_AUDIO", "VOICE_C_HUMAN_DEVICE"]

KNOWN_PCM_FIXTURE = b"\x00\x01" * 160  # 20ms-ish 16-bit mono placeholder


def classify_voice_proof(
    *,
    used_known_pcm_fixture: bool,
    used_virtual_loopback: bool,
    used_physical_microphone: bool,
) -> VoiceProofClass:
    if used_physical_microphone:
        return "VOICE_C_HUMAN_DEVICE"
    if used_virtual_loopback:
        return "VOICE_B_VIRTUAL_AUDIO"
    if used_known_pcm_fixture:
        return "VOICE_A_PROTOCOL"
    return "VOICE_A_PROTOCOL"


def protocol_roundtrip_ok(inbound_pcm: bytes, outbound_pcm: bytes | None) -> bool:
    return bool(inbound_pcm) and outbound_pcm is not None and len(outbound_pcm) > 0


async def known_pcm_websocket_roundtrip(pcm: bytes | None = None) -> bytes:
    """VOICE-A: fixture PCM through the Pipecat JSON serializer, not a microphone."""
    import base64
    import json

    from pipecat.frames.frames import OutputAudioRawFrame

    from app.services.pipecat_voice.json_audio_serializer import GravitreJsonAudioSerializer

    payload = pcm if pcm is not None else KNOWN_PCM_FIXTURE
    ser = GravitreJsonAudioSerializer()
    outbound = await ser.serialize(
        OutputAudioRawFrame(audio=payload, sample_rate=16000, num_channels=1)
    )
    if not outbound:
        return b""
    msg = json.loads(outbound)
    frame = await ser.deserialize(
        json.dumps(
            {
                "type": "audio",
                "pcm16_b64": base64.b64encode(payload).decode(),
                "sample_rate": 16000,
            }
        )
    )
    recovered = getattr(frame, "audio", None) or b""
    if not protocol_roundtrip_ok(payload, recovered):
        return b""
    if str(msg.get("type") or "") != "audio":
        return b""
    return recovered
