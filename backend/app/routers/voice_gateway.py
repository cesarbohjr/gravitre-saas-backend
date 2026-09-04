"""Voice Gateway HTTP + Twilio PSTN webhooks."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.billing.service import get_supabase_client
from app.billing.voice_access import assert_voice_org_enabled
from app.config import Settings, get_settings
from app.services.voice_gateway_service import (
    build_connect_twiml,
    create_voice_pstn_session,
    get_voice_pstn_session,
    get_voice_pstn_session_by_call_sid,
    handle_twilio_status_event,
    mark_voicemail_detected,
    start_voice_session_outbound,
    update_voice_pstn_session,
)
from app.services.voice_pstn_policy import resolve_voice_pstn_policy
from app.services.pstn_voice_bridge import PstnMediaBridge

router = APIRouter(prefix="/api/voice-gateway", tags=["voice-gateway"])


class StartVoiceSessionRequest(BaseModel):
    contact_phone: str = Field(..., min_length=8, max_length=32)
    from_phone: str = Field(..., min_length=8, max_length=32)
    agent_id: str | None = None
    work_object_id: str | None = None
    contact_id: str | None = None
    objective: str | None = Field(default=None, max_length=2000)
    department: str | None = None
    agent_name: str | None = None
    connector_id: str | None = None


async def _voice_org(
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization required")
    client = get_supabase_client(settings)
    assert_voice_org_enabled(client, org_id=org_id)
    return org_id


@router.post("/sessions")
async def start_voice_session_route(
    body: StartVoiceSessionRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str, Depends(_voice_org)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Agent-facing: start_voice_session(contact, objective, agent, policy)."""
    client = get_supabase_client(settings)
    session = await start_voice_session_outbound(
        settings,
        client,
        org_id=org_id,
        user_id=str(user.get("sub") or user.get("id") or ""),
        contact_phone=body.contact_phone,
        from_phone=body.from_phone,
        agent_id=body.agent_id,
        work_object_id=body.work_object_id,
        contact_id=body.contact_id,
        objective=body.objective,
        department=body.department,
        agent_name=body.agent_name,
        connector_id=body.connector_id,
    )
    return {"session": session}


@router.get("/sessions/{session_id}")
async def get_voice_session_route(
    session_id: str,
    org_id: Annotated[str, Depends(_voice_org)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    session = get_voice_pstn_session(client, org_id=org_id, session_id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session}


twilio_router = APIRouter(prefix="/api/webhooks/twilio/voice", tags=["twilio-voice-webhooks"])


def _verify_twilio_signature(
    settings: Settings,
    request: Request,
    body: bytes,
    auth_token: str,
) -> bool:
    signature = request.headers.get("X-Twilio-Signature") or ""
    if not signature or not auth_token:
        return False
    url = str(request.url)
    params: dict[str, str] = {}
    if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        from urllib.parse import parse_qsl

        params = dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
    sorted_params = "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(auth_token.encode(), (url + sorted_params).encode(), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


async def _twilio_auth_token(settings: Settings, org_id: str | None = None) -> str:
    token = (settings.twilio_auth_token or "").strip()
    if token:
        return token
    if org_id:
        from app.connectors.repository import get_connector_by_type, get_decrypted_secret

        client = get_supabase_client(settings)
        conn = get_connector_by_type(client, org_id, "twilio")
        if conn:
            return (
                get_decrypted_secret(client, str(conn["id"]), "auth_token", settings) or ""
            ).strip()
    return ""


@twilio_router.post("/connect/{session_id}")
async def twilio_connect_twiml(
    session_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlainTextResponse:
    client = get_supabase_client(settings)
    session = (
        client.table("voice_pstn_sessions").select("*").eq("id", session_id).limit(1).execute()
    )
    rows = session.data or []
    if not rows:
        return PlainTextResponse(
            '<?xml version="1.0"?><Response><Say>Session not found.</Say></Response>',
            media_type="application/xml",
        )
    row = rows[0]
    policy_raw = row.get("policy") or {}
    disclosure = policy_raw.get("disclosure_script") if isinstance(policy_raw, dict) else None
    twiml = build_connect_twiml(settings, session_id, disclosure=disclosure)
    update_voice_pstn_session(client, session_id=session_id, patch={"status": "answered"})
    return PlainTextResponse(twiml, media_type="application/xml")


@twilio_router.post("/status")
async def twilio_status_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    body = await request.body()
    client = get_supabase_client(settings)
    from urllib.parse import parse_qsl

    form = dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
    call_sid = str(form.get("CallSid") or "")
    call_status = str(form.get("CallStatus") or "")
    recording_url = str(form.get("RecordingUrl") or "") or None
    if form.get("AnsweredBy") == "machine_start":
        session = get_voice_pstn_session_by_call_sid(client, call_sid=call_sid)
        if session:
            mark_voicemail_detected(client, session_id=str(session["id"]))
    handle_twilio_status_event(
        client,
        call_sid=call_sid,
        call_status=call_status,
        recording_url=recording_url,
        metadata=form,
    )
    return {"ok": "true"}


@twilio_router.post("/inbound")
async def twilio_inbound_voice(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlainTextResponse:
    """Inbound PSTN: create session from To/From and connect Media Stream."""
    body = await request.body()
    from urllib.parse import parse_qsl

    form = dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
    from_phone = str(form.get("From") or "")
    to_phone = str(form.get("To") or "")
    call_sid = str(form.get("CallSid") or "")
    client = get_supabase_client(settings)
    # Org resolution for inbound requires number→org mapping; honest scaffold uses metadata.
    org_id = (settings.twilio_default_org_id or "").strip()
    if not org_id:
        return PlainTextResponse(
            '<?xml version="1.0"?><Response><Say>Inbound routing not configured.</Say></Response>',
            media_type="application/xml",
        )
    session = create_voice_pstn_session(
        client,
        org_id=org_id,
        contact_phone=from_phone,
        from_phone=to_phone,
        direction="inbound",
        metadata={"inbound_call_sid": call_sid},
    )
    if call_sid:
        update_voice_pstn_session(
            client,
            session_id=str(session["id"]),
            patch={"twilio_call_sid": call_sid, "status": "ringing", "started_at": session.get("created_at")},
        )
    twiml = build_connect_twiml(settings, str(session["id"]))
    return PlainTextResponse(twiml, media_type="application/xml")


@router.websocket("/pstn/media/{session_id}")
async def pstn_media_stream_ws(
    websocket: WebSocket,
    session_id: str,
) -> None:
    settings = get_settings()
    await websocket.accept()
    client = get_supabase_client(settings)
    resp = client.table("voice_pstn_sessions").select("*").eq("id", session_id).limit(1).execute()
    rows = resp.data or []
    if not rows:
        await websocket.close(code=4404)
        return
    session = rows[0]
    org_id = str(session["org_id"])
    agent_id = session.get("agent_id")
    agent: dict[str, Any] | None = None
    if agent_id:
        ag = (
            client.table("agents")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", agent_id)
            .limit(1)
            .execute()
        )
        agent_rows = ag.data or []
        agent = agent_rows[0] if agent_rows else None
    policy = resolve_voice_pstn_policy(
        client,
        org_id=org_id,
        agent_id=str(agent_id) if agent_id else None,
        department=(agent or {}).get("department"),
        agent_name=(agent or {}).get("name"),
    )
    bridge = PstnMediaBridge(
        settings=settings,
        client=client,
        session=session,
        agent=agent,
        policy=policy,
    )
    update_voice_pstn_session(client, session_id=session_id, patch={"status": "in_progress"})

    dg_task = asyncio.create_task(bridge.run_deepgram_relay())
    outbound_task = asyncio.create_task(_pump_outbound(websocket, bridge))

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            await bridge.handle_twilio_message(msg)
            if not bridge._running:
                break
    except WebSocketDisconnect:
        pass
    finally:
        bridge._running = False
        dg_task.cancel()
        outbound_task.cancel()
        update_voice_pstn_session(
            client,
            session_id=session_id,
            patch={"status": "completed"},
        )


async def _pump_outbound(websocket: WebSocket, bridge: PstnMediaBridge) -> None:
    import json

    async for msg in bridge.outbound_audio_iter():
        await websocket.send_text(json.dumps(msg))
