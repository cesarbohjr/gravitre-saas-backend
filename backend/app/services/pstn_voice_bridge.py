"""PSTN Media Streams bridge — server-side Deepgram STT + CognitiveTurnKernel TTS."""
from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, Callable

from app.config import Settings
from app.services.tier1_voice_service import mint_deepgram_live_credentials
from app.services.voice_gateway_service import append_tool_call, append_transcript_entry
from app.services.voice_pstn_policy import VoicePstnPolicy, enforce_pstn_tool_policy
from app.services.voice_session_service import (
    apply_stt_event_to_turn_state,
    is_turn_cancelled,
    request_turn_cancel,
    stream_voice_turn_events,
)
from app.services.voice_turn_taking import TurnTakingState, parse_sensitivity

MID_CALL_TURN_BRIDGE = "run_mid_call_turn"


async def run_mid_call_turn(
    *,
    settings: Settings,
    client: Any,
    session: dict[str, Any],
    user_text: str,
    agent: dict[str, Any] | None,
    policy: VoicePstnPolicy,
    conversation_history: list[dict[str, Any]] | None = None,
    on_audio: Callable[[bytes], None] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Execute one mid-call spoken turn through CognitiveTurnKernel + ulaw TTS."""
    session_id = str(session["id"])
    org_id = str(session["org_id"])
    agent_id = str(session.get("agent_id") or "")
    turn_id = str(uuid.uuid4())
    append_transcript_entry(client, session_id=session_id, speaker="user", text=user_text)

    async for event in stream_voice_turn_events(
        settings=settings,
        org_id=org_id,
        user_id=str((session.get("metadata") or {}).get("user_id") or org_id),
        text=user_text,
        agent=agent,
        conversation_id=str(session.get("conversation_id") or ""),
        conversation_history=conversation_history,
        turn_id=turn_id,
        tts_output_format="ulaw_8000",
        should_cancel=lambda: is_turn_cancelled(turn_id),
    ):
        etype = str(event.get("type") or "")
        if etype == "voice.tool.invoke":
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            action = str(payload.get("action") or "")
            if action:
                try:
                    enforce_pstn_tool_policy(
                        client,
                        org_id=org_id,
                        agent_id=agent_id,
                        action_name=action,
                        policy=policy,
                        action_kind=str(payload.get("kind") or "read"),
                    )
                    append_tool_call(
                        client,
                        session_id=session_id,
                        action_name=action,
                        status="invoked",
                        metadata=payload,
                    )
                except Exception as exc:  # noqa: BLE001
                    append_tool_call(
                        client,
                        session_id=session_id,
                        action_name=action,
                        status="blocked",
                        metadata={"error": str(exc)},
                    )
                    yield {"type": "voice.pstn.tool_blocked", "action": action, "error": str(exc)}
                    continue
        if etype == "voice.audio.delta" and on_audio:
            raw_b64 = event.get("audio_base64")
            if isinstance(raw_b64, str) and raw_b64:
                on_audio(base64.b64decode(raw_b64))
        if etype == "voice.turn.complete":
            text = str(event.get("text") or "")
            if text:
                append_transcript_entry(
                    client, session_id=session_id, speaker="agent", text=text
                )
        yield event


def parse_deepgram_ws_message(raw: str | bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    msg_type = str(data.get("type") or "")
    if msg_type == "Results":
        channel = data.get("channel") or {}
        alts = channel.get("alternatives") or [{}]
        transcript = str(alts[0].get("transcript") or "").strip()
        is_final = bool(data.get("is_final") or data.get("speech_final"))
        return {"type": "transcript", "transcript": transcript, "is_final": is_final}
    if msg_type == "SpeechStarted":
        return {"type": "speech_started"}
    if msg_type == "UtteranceEnd":
        return {"type": "utterance_end"}
    return {"type": msg_type.lower()}


class PstnMediaBridge:
    """Bidirectional Twilio Media Stream ↔ Deepgram ↔ CognitiveTurnKernel."""

    def __init__(
        self,
        *,
        settings: Settings,
        client: Any,
        session: dict[str, Any],
        agent: dict[str, Any] | None,
        policy: VoicePstnPolicy,
    ) -> None:
        self.settings = settings
        self.client = client
        self.session = session
        self.agent = agent
        self.policy = policy
        self.turn_state = TurnTakingState(sensitivity=parse_sensitivity("normal"))
        self.stream_sid: str | None = None
        self._history: list[dict[str, Any]] = []
        self._active_turn_id: str | None = None
        self._outbound_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._running = True
        self._dg_send: Callable[[bytes], Any] | None = None

    async def handle_twilio_message(self, message: dict[str, Any]) -> None:
        event = str(message.get("event") or "")
        if event == "start":
            start = message.get("start") or {}
            self.stream_sid = str(start.get("streamSid") or "")
            return
        if event == "media":
            media = message.get("media") or {}
            payload = media.get("payload")
            if payload and self._dg_send:
                await self._dg_send(base64.b64decode(str(payload)))
        if event == "stop":
            self._running = False
            await self._outbound_queue.put(None)

    async def _emit_outbound_audio(self, chunk: bytes) -> None:
        await self._outbound_queue.put(chunk)

    async def outbound_audio_iter(self) -> AsyncIterator[dict[str, Any]]:
        while self._running:
            chunk = await self._outbound_queue.get()
            if chunk is None:
                break
            if not self.stream_sid:
                continue
            yield {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": base64.b64encode(chunk).decode("ascii")},
            }

    async def _on_deepgram_event(self, event: dict[str, Any]) -> None:
        now_ms = time.time() * 1000
        if event.get("type") == "speech_started" and self._active_turn_id:
            request_turn_cancel(self._active_turn_id)
        state, finalized = apply_stt_event_to_turn_state(
            self.turn_state, event=event, now_ms=now_ms
        )
        self.turn_state = state
        if not finalized:
            return
        self._active_turn_id = str(uuid.uuid4())

        async def _on_audio(b: bytes) -> None:
            await self._emit_outbound_audio(b)

        async for _ev in run_mid_call_turn(
            settings=self.settings,
            client=self.client,
            session=self.session,
            user_text=finalized,
            agent=self.agent,
            policy=self.policy,
            conversation_history=list(self._history),
            on_audio=lambda b: asyncio.create_task(_on_audio(b)),
        ):
            pass
        self._history.append({"role": "user", "content": finalized})

    async def run_deepgram_relay(self) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError("websockets package required for PSTN bridge") from exc

        creds = mint_deepgram_live_credentials(self.settings, ttl_seconds=120, pstn=True)
        headers = {"Authorization": creds["authorization"]}

        async with websockets.connect(creds["ws_url"], additional_headers=headers) as dg_ws:
            async def dg_send(data: bytes) -> None:
                await dg_ws.send(data)

            self._dg_send = dg_send

            async for raw in dg_ws:
                if not self._running:
                    break
                parsed = parse_deepgram_ws_message(raw)
                if parsed:
                    await self._on_deepgram_event(parsed)
