"""Voice Gateway — PSTN sessions bridged to CognitiveTurnKernel (not a third voice stack).

Agents call start_voice_session(contact, objective, agent, policy) without Twilio/
Deepgram/ElevenLabs specifics. Reuses:
  - stream_voice_turn_events (CognitiveTurnKernel + progressive TTS)
  - Twilio REST connector (approval-gated create + SID verification)
  - Agent Identity IAM for per-agent PSTN policy
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.voice_pstn_policy import VoicePstnPolicy, resolve_voice_pstn_policy
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)

PSTN_SESSION_TABLE = "voice_pstn_sessions"
AUDIT_PSTN_STARTED = "voice.pstn.session.started"
AUDIT_PSTN_ANSWERED = "voice.pstn.session.answered"
AUDIT_PSTN_COMPLETED = "voice.pstn.session.completed"
AUDIT_PSTN_VOICEMAIL = "voice.pstn.voicemail.detected"
AUDIT_PSTN_TOOL = "voice.pstn.tool.invoked"

VoiceSessionDirection = Literal["inbound", "outbound"]
VoiceSessionStatus = Literal[
    "pending",
    "ringing",
    "answered",
    "in_progress",
    "voicemail",
    "completed",
    "failed",
    "cancelled",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("policy", "transcript", "tool_calls", "approval_events", "outcome", "metadata"):
        if key in out and isinstance(out[key], dict):
            out[key] = safe_normalize_stored_dict(out[key])
        elif key in out and isinstance(out[key], list):
            out[key] = list(out[key])
    return out


def _public_api_base(settings: Settings) -> str:
    base = (settings.api_public_url or settings.public_app_url or "").strip().rstrip("/")
    if not base:
        base = "https://api.gravitre.app"
    return base


def pstn_twiml_connect_url(settings: Settings, session_id: str) -> str:
    """TwiML webhook that returns <Connect><Stream> for Media Streams."""
    return f"{_public_api_base(settings)}/api/webhooks/twilio/voice/connect/{session_id}"


def pstn_media_stream_ws_url(settings: Settings, session_id: str) -> str:
    ws_base = _public_api_base(settings).replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_base}/api/voice-gateway/pstn/media/{session_id}"


def pstn_status_callback_url(settings: Settings) -> str:
    return f"{_public_api_base(settings)}/api/webhooks/twilio/voice/status"


def create_voice_pstn_session(
    client: Any,
    *,
    org_id: str,
    contact_phone: str,
    direction: VoiceSessionDirection = "outbound",
    agent_id: str | None = None,
    work_object_id: str | None = None,
    contact_id: str | None = None,
    from_phone: str | None = None,
    objective: str | None = None,
    department: str | None = None,
    agent_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = resolve_voice_pstn_policy(
        client,
        org_id=org_id,
        agent_id=agent_id,
        department=department,
        agent_name=agent_name,
    )
    row = {
        "org_id": org_id,
        "agent_id": agent_id,
        "work_object_id": work_object_id,
        "contact_id": contact_id,
        "contact_phone": contact_phone.strip(),
        "from_phone": (from_phone or "").strip() or None,
        "direction": direction,
        "objective": (objective or "").strip() or None,
        "status": "pending",
        "conversation_id": str(uuid.uuid4()),
        "policy": policy.to_dict(),
        "transcript": [],
        "tool_calls": [],
        "approval_events": [],
        "outcome": {},
        "metadata": safe_normalize_stored_dict(metadata or {}),
    }
    inserted = client.table(PSTN_SESSION_TABLE).insert(row).execute()
    data = (inserted.data or [None])[0]
    if not data:
        raise RuntimeError("Failed to create voice PSTN session")
    return _normalize_row(data)


def get_voice_pstn_session(client: Any, *, org_id: str, session_id: str) -> dict[str, Any] | None:
    resp = (
        client.table(PSTN_SESSION_TABLE)
        .select("*")
        .eq("org_id", org_id)
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _normalize_row(rows[0]) if rows else None


def get_voice_pstn_session_by_call_sid(client: Any, *, call_sid: str) -> dict[str, Any] | None:
    resp = (
        client.table(PSTN_SESSION_TABLE)
        .select("*")
        .eq("twilio_call_sid", call_sid)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _normalize_row(rows[0]) if rows else None


def update_voice_pstn_session(
    client: Any,
    *,
    session_id: str,
    patch: dict[str, Any],
) -> dict[str, Any] | None:
    patch = dict(patch)
    patch["updated_at"] = _now_iso()
    resp = client.table(PSTN_SESSION_TABLE).update(patch).eq("id", session_id).execute()
    rows = resp.data or []
    return _normalize_row(rows[0]) if rows else None


def append_transcript_entry(
    client: Any,
    *,
    session_id: str,
    speaker: str,
    text: str,
    is_final: bool = True,
) -> None:
    session = (
        client.table(PSTN_SESSION_TABLE).select("transcript").eq("id", session_id).limit(1).execute()
    )
    rows = session.data or []
    if not rows:
        return
    transcript = list(rows[0].get("transcript") or [])
    transcript.append(
        {
            "speaker": speaker,
            "text": text,
            "is_final": is_final,
            "at": _now_iso(),
        }
    )
    update_voice_pstn_session(client, session_id=session_id, patch={"transcript": transcript})


def append_tool_call(
    client: Any,
    *,
    session_id: str,
    action_name: str,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    session = (
        client.table(PSTN_SESSION_TABLE).select("tool_calls").eq("id", session_id).limit(1).execute()
    )
    rows = session.data or []
    if not rows:
        return
    tool_calls = list(rows[0].get("tool_calls") or [])
    tool_calls.append(
        {
            "action": action_name,
            "status": status,
            "at": _now_iso(),
            "metadata": safe_normalize_stored_dict(metadata or {}),
        }
    )
    update_voice_pstn_session(client, session_id=session_id, patch={"tool_calls": tool_calls})


def build_connect_twiml(settings: Settings, session_id: str, *, disclosure: str | None = None) -> str:
    stream_url = pstn_media_stream_ws_url(settings, session_id)
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<Response>"]
    if disclosure:
        parts.append(f"<Say>{disclosure}</Say>")
    parts.append("<Connect>")
    parts.append(f'<Stream url="{stream_url}" />')
    parts.append("</Connect>")
    parts.append("</Response>")
    return "".join(parts)


async def start_voice_session_outbound(
    settings: Settings,
    client: Any,
    *,
    org_id: str,
    user_id: str,
    contact_phone: str,
    from_phone: str,
    agent_id: str | None = None,
    work_object_id: str | None = None,
    contact_id: str | None = None,
    objective: str | None = None,
    department: str | None = None,
    agent_name: str | None = None,
    connector_id: str | None = None,
) -> dict[str, Any]:
    """Start outbound PSTN call via governed Twilio connector."""
    from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
    from app.services.tool_types import ToolContext

    session = create_voice_pstn_session(
        client,
        org_id=org_id,
        contact_phone=contact_phone,
        direction="outbound",
        agent_id=agent_id,
        work_object_id=work_object_id,
        contact_id=contact_id,
        from_phone=from_phone,
        objective=objective,
        department=department,
        agent_name=agent_name,
    )
    session_id = str(session["id"])
    policy = resolve_voice_pstn_policy(
        client, org_id=org_id, agent_id=agent_id, department=department, agent_name=agent_name
    )
    twiml_url = pstn_twiml_connect_url(settings, session_id)
    status_url = pstn_status_callback_url(settings)

    if connector_id:
        conn = get_connector(client, org_id, connector_id)
    else:
        conn = get_connector_by_type(client, org_id, "twilio")
    if not conn:
        update_voice_pstn_session(
            client, session_id=session_id, patch={"status": "failed", "outcome": {"error": "no_twilio"}}
        )
        raise RuntimeError("No active Twilio connector")

    cid = str(conn["id"])
    cfg = conn.get("config") or {}
    account_sid = str(cfg.get("account_sid") or cfg.get("AccountSid") or "").strip()
    if not account_sid:
        account_sid = (get_decrypted_secret(client, cid, "account_sid", settings) or "").strip()
    token = (
        get_decrypted_secret(client, cid, "auth_token", settings)
        or get_decrypted_secret(client, cid, "api_token", settings)
        or ""
    ).strip()
    if not account_sid or not token:
        update_voice_pstn_session(
            client,
            session_id=session_id,
            patch={"status": "failed", "outcome": {"error": "twilio_credentials"}},
        )
        raise RuntimeError("Twilio credentials incomplete")

    form = {
        "To": contact_phone,
        "From": from_phone,
        "Url": twiml_url,
        "StatusCallback": status_url,
        "StatusCallbackEvent": "initiated ringing answered completed",
        "StatusCallbackMethod": "POST",
        "Record": "true" if policy.recording_consent_required else "false",
    }
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
    import base64

    auth = "Basic " + base64.b64encode(f"{account_sid}:{token}".encode()).decode()
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(url, headers={"Authorization": auth}, data=form)
    if resp.status_code >= 400:
        update_voice_pstn_session(
            client,
            session_id=session_id,
            patch={"status": "failed", "outcome": {"error": resp.text[:500]}},
        )
        raise RuntimeError(f"Twilio call create failed: HTTP {resp.status_code}")

    payload = resp.json()
    call_sid = str(payload.get("sid") or payload.get("Sid") or "").strip()
    if not call_sid:
        update_voice_pstn_session(
            client, session_id=session_id, patch={"status": "failed", "outcome": {"error": "no_sid"}}
        )
        raise RuntimeError("Twilio call create returned no Call SID")

    updated = update_voice_pstn_session(
        client,
        session_id=session_id,
        patch={
            "status": "ringing",
            "twilio_call_sid": call_sid,
            "started_at": _now_iso(),
        },
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user_id,
        action=AUDIT_PSTN_STARTED,
        resource_type="voice_pstn_session",
        resource_id=session_id,
        metadata={
            "call_sid": call_sid,
            "direction": "outbound",
            "contact_phone": contact_phone,
            "agent_id": agent_id,
            "work_object_id": work_object_id,
        },
    )
    return updated or session


def handle_twilio_status_event(
    client: Any,
    *,
    call_sid: str,
    call_status: str,
    recording_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    session = get_voice_pstn_session_by_call_sid(client, call_sid=call_sid)
    if not session:
        return None
    session_id = str(session["id"])
    org_id = str(session["org_id"])
    status_map = {
        "initiated": "ringing",
        "ringing": "ringing",
        "in-progress": "in_progress",
        "answered": "answered",
        "completed": "completed",
        "busy": "failed",
        "failed": "failed",
        "no-answer": "failed",
        "canceled": "cancelled",
    }
    mapped = status_map.get((call_status or "").strip().lower(), "in_progress")
    patch: dict[str, Any] = {"status": mapped}
    if mapped == "answered":
        patch["answered_at"] = _now_iso()
    if mapped in {"completed", "failed", "cancelled"}:
        patch["ended_at"] = _now_iso()
    if recording_url:
        patch["recording_url"] = recording_url
    updated = update_voice_pstn_session(client, session_id=session_id, patch=patch)
    action = AUDIT_PSTN_COMPLETED if mapped == "completed" else AUDIT_PSTN_ANSWERED
    if mapped == "completed":
        action = AUDIT_PSTN_COMPLETED
    elif mapped == "answered":
        action = AUDIT_PSTN_ANSWERED
    else:
        action = f"voice.pstn.status.{mapped}"
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=None,
        action=action,
        resource_type="voice_pstn_session",
        resource_id=session_id,
        metadata={"call_sid": call_sid, "call_status": call_status, **(metadata or {})},
    )
    return updated


def mark_voicemail_detected(client: Any, *, session_id: str) -> dict[str, Any] | None:
    updated = update_voice_pstn_session(
        client,
        session_id=session_id,
        patch={"status": "voicemail", "ended_at": _now_iso()},
    )
    if updated:
        write_audit_event(
            client,
            org_id=str(updated["org_id"]),
            actor_id=None,
            action=AUDIT_PSTN_VOICEMAIL,
            resource_type="voice_pstn_session",
            resource_id=session_id,
            metadata={},
        )
    return updated
