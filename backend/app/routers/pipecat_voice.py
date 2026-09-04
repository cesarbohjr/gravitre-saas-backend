"""Pipecat WebSocket voice surface — flag-gated Phase 1 orchestration."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.auth.jwt_verify import decode_supabase_jwt
from app.auth.platform_admin import is_platform_admin
from app.billing.seat_context import assert_agent_voice_use, resolve_seat_context
from app.billing.service import get_supabase_client
from app.billing.voice_access import assert_voice_org_enabled
from app.config import get_settings
from app.core.logging import get_logger
from app.services.org_membership import list_member_org_ids, load_user_primary_org_id, pick_default_org_id

logger = get_logger(__name__)

router = APIRouter(prefix="/api/voice/pipecat", tags=["voice-pipecat"])


def _pipecat_available() -> bool:
    try:
        import pipecat  # noqa: F401

        return True
    except ImportError:
        return False


def _token_from_websocket(websocket: WebSocket) -> str:
    auth = websocket.headers.get("authorization") or websocket.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    q = websocket.query_params
    return (q.get("access_token") or q.get("token") or "").strip()


def _ws_error(detail: Any) -> str:
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("error") or detail)[:300]
    return str(detail)[:300]


@router.websocket("/ws")
async def pipecat_voice_ws(
    websocket: WebSocket,
    agent_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    voice: str | None = Query(default=None),
    org_id: str | None = Query(default=None),
) -> None:
    """Full-duplex Pipecat session: browser JSON/PCM ↔ Deepgram ↔ Cognitive ↔ ElevenLabs.

    Requires VOICE_PIPECAT_ENABLED=true. Governance stays inside GravitreCognitiveLLMService
    → execute_task_streaming(spoken_mode=True).
    """
    await websocket.accept()
    settings = get_settings()
    if not bool(getattr(settings, "voice_pipecat_enabled", False)):
        await websocket.send_json(
            {"type": "error", "error": "VOICE_PIPECAT_ENABLED is false", "error_class": "not_enabled"}
        )
        await websocket.close(code=1008)
        return
    if not _pipecat_available():
        await websocket.send_json(
            {"type": "error", "error": "pipecat-ai not installed", "error_class": "not_configured"}
        )
        await websocket.close(code=1013)
        return

    token = _token_from_websocket(websocket)
    if not token:
        await websocket.send_json(
            {"type": "error", "error": "Missing bearer token", "error_class": "auth"}
        )
        await websocket.close(code=1008)
        return
    try:
        payload = decode_supabase_jwt(token, settings)
    except Exception:  # noqa: BLE001
        await websocket.send_json(
            {"type": "error", "error": "Invalid or expired token", "error_class": "auth"}
        )
        await websocket.close(code=1008)
        return

    user_id = str(payload.get("sub") or payload.get("id") or "").strip()
    if not user_id:
        await websocket.send_json(
            {"type": "error", "error": "Invalid token", "error_class": "auth"}
        )
        await websocket.close(code=1008)
        return

    client = get_supabase_client(settings)
    requested_org = (org_id or websocket.headers.get("x-org-id") or "").strip()
    try:
        member_org_ids = list_member_org_ids(client, user_id)
    except Exception:  # noqa: BLE001
        member_org_ids = []
    platform_admin = is_platform_admin(client, user_id)
    if requested_org:
        if requested_org not in member_org_ids and not platform_admin:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": "Not a member of the requested organization",
                    "error_class": "forbidden",
                }
            )
            await websocket.close(code=1008)
            return
        resolved_org = requested_org
    else:
        primary = load_user_primary_org_id(client, user_id)
        resolved_org = pick_default_org_id(
            member_org_ids,
            primary_org_id=primary,
            requested_org_id=None,
        ) or ""
    if not resolved_org:
        await websocket.send_json(
            {"type": "error", "error": "Organization required", "error_class": "auth"}
        )
        await websocket.close(code=1008)
        return

    try:
        assert_voice_org_enabled(client, org_id=resolved_org)
        seat = resolve_seat_context(client, org_id=resolved_org, user_id=user_id)
        assert_agent_voice_use(client, seat, org_id=resolved_org, agent_id=agent_id)
    except HTTPException as exc:
        await websocket.send_json(
            {
                "type": "error",
                "error": _ws_error(exc.detail),
                "error_class": "forbidden",
            }
        )
        await websocket.close(code=1008)
        return
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json(
            {"type": "error", "error": str(exc)[:300], "error_class": "forbidden"}
        )
        await websocket.close(code=1008)
        return

    agent: dict[str, Any] | None = None
    if agent_id:
        try:
            rows = (
                client.table("agents")
                .select("id,name,voice_profile,department")
                .eq("org_id", resolved_org)
                .eq("id", agent_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            agent = rows[0] if rows else {"id": agent_id}
        except Exception:  # noqa: BLE001
            agent = {"id": agent_id}

    from pipecat.pipeline.runner import PipelineRunner

    from app.services.pipecat_voice.pipeline import build_pipecat_voice_task

    try:
        task = build_pipecat_voice_task(
            websocket=websocket,
            settings=settings,
            org_id=resolved_org,
            user_id=user_id,
            agent=agent,
            conversation_id=conversation_id,
            voice_key=voice,
        )
        await websocket.send_json(
            {
                "type": "session.ready",
                "architecture": "pipecat_deepgram_cognitive_elevenlabs",
                "cognitive_path": "CognitiveTurnKernel",
                "write_confirm_policy": "nl_yes_same_path_as_text",
                "org_id": resolved_org,
                "conversation_id": conversation_id,
            }
        )
        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)
    except WebSocketDisconnect:
        logger.info("pipecat_voice_ws_disconnected org_id=%s", resolved_org)
    except Exception as exc:  # noqa: BLE001
        logger.exception("pipecat_voice_ws_failed error=%s", exc)
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(
                    {"type": "error", "error": str(exc)[:400], "error_class": "service_failure"}
                )
            except Exception:  # noqa: BLE001
                pass
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001
                pass
