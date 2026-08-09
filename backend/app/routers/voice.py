"""Voice HTTP surface — streaming session, library, custom design, TTS/STT."""
from __future__ import annotations

import json
import time
import uuid
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.billing.seat_context import assert_agent_voice_use
from app.billing.service import get_supabase_client
from app.billing.voice_access import assert_voice_org_enabled
from app.config import Settings, get_settings
from app.middleware.entitlements import (
    require_seat_context,
    require_voice_configure,
)
from app.services.tier1_voice_service import (
    VoiceProviderError,
    synthesize_speech,
    synthesize_speech_stream,
    transcribe_audio,
    voice_status,
)
from app.services.voice_provider_errors import error_public_payload
from app.services.voice_qa_hooks import (
    QA_FORCE_VOICE_ERROR_HEADER,
    forced_voice_provider_error,
    resolve_qa_force_voice_error,
)

# Plan-included voice (2026-08-08): no Meson $49 purchase gate.
# Org admin may disable via subscriptions.voice_enabled.
# B1: Lite USE vs full/manager CONFIGURE unchanged.
async def _require_voice_org_enabled(
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    return assert_voice_org_enabled(client, org_id=org_id)


router = APIRouter(
    prefix="/api/voice",
    tags=["voice"],
    dependencies=[Depends(_require_voice_org_enabled)],
)


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: str | None = Field(default=None, description="library key | raw voice id")
    model: str | None = None
    agent_id: str | None = Field(
        default=None, description="Required for Lite USE scoping (assigned agents)"
    )


class TurnEventRequest(BaseModel):
    sensitivity: str | None = "normal"
    event: dict[str, Any]
    state: dict[str, Any] | None = None


class SessionTurnRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    conversation_id: str | None = None
    agent_id: str | None = None
    voice: str | None = None
    model: str | None = None
    history: list[dict[str, Any]] | None = None


class DesignVoiceRequest(BaseModel):
    voice_description: str | None = None
    guided: dict[str, Any] | None = None
    model_id: str = "eleven_ttv_v3"
    auto_generate_text: bool = True
    text: str | None = None
    guidance_scale: float = 5.0
    loudness: float = 0.5
    seed: int | None = None
    should_enhance: bool = True


class SaveCustomVoiceRequest(BaseModel):
    generated_voice_id: str
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    personality_attributes: dict[str, Any] | None = None


class PreviewRequest(BaseModel):
    text: str = Field(
        default="Hi — this is a quick preview of how I'll sound in conversation.",
        min_length=1,
        max_length=500,
    )
    voice: str = Field(..., min_length=1)
    model: str | None = "eleven_flash_v2_5"


class MeterMinutesRequest(BaseModel):
    minutes: float = Field(..., gt=0, le=240)
    source_id: str | None = None
    conversation_id: str | None = None
    agent_id: str | None = None
    stt_seconds: float = 0
    tts_seconds: float = 0


class AcousticAnalyzeRequest(BaseModel):
    # Optional: client may POST multipart instead; this accepts base64 for tests.
    audio_base64: str | None = None
    conversation_id: str | None = None
    agent_id: str | None = None


class AgentVoiceProfileRequest(BaseModel):
    voice_profile: dict[str, Any]


def _http_error(exc: VoiceProviderError) -> HTTPException:
    payload = error_public_payload(exc)
    return HTTPException(
        status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
        detail=payload,
    )


@router.get("/status")
def get_voice_status(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    from app.billing.voice_minutes_plan_rates import cogs_report

    status_body = voice_status(settings)
    status_body["cogs_report"] = cogs_report()
    return status_body


@router.get("/library")
def get_voice_library(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
    _seat: Annotated[dict, Depends(require_voice_configure())],
    settings: Annotated[Settings, Depends(get_settings)],
    category: str | None = None,
    language: str | None = None,
    gender: str | None = None,
    archetype: str | None = None,
) -> dict[str, Any]:
    from app.services.voice_library_service import list_voice_library

    try:
        return list_voice_library(
            settings,
            category=category,
            language=language,
            gender=gender,
            archetype=archetype,
        )
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc


@router.get("/library/recommendations")
def get_voice_recommendations(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
    _seat: Annotated[dict, Depends(require_voice_configure())],
    settings: Annotated[Settings, Depends(get_settings)],
    department: str | None = None,
    model: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    from app.services.voice_library_service import recommend_voices_for_agent

    return {
        "recommendations": recommend_voices_for_agent(
            settings,
            department=department,
            model=model,
            limit=limit,
        ),
        "override_allowed": True,
    }


@router.get("/library/multiplier-audit")
def get_voice_multiplier_audit(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
    _seat: Annotated[dict, Depends(require_voice_configure())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Live GET /v1/voices audit for curated presets — credit multiplier flags."""
    from app.services.voice_library_service import audit_curated_voice_multipliers

    try:
        return audit_curated_voice_multipliers(settings)
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc


def _maybe_qa_force_voice_error(request: Request, settings: Settings) -> None:
    """Raise a synthetic VoiceProviderError when QA force header is active."""
    try:
        forced = resolve_qa_force_voice_error(
            settings,
            header_value=request.headers.get(QA_FORCE_VOICE_ERROR_HEADER),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if forced:
        raise forced_voice_provider_error(forced)


@router.post("/tts")
def post_tts(
    body: TtsRequest,
    request: Request,
    _user: Annotated[dict, Depends(get_current_user)],
    org: Annotated[str | None, Depends(get_org_context)],
    seat: Annotated[dict, Depends(require_seat_context())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    client = get_supabase_client(settings)
    assert_agent_voice_use(client, seat, org_id=str(org or ""), agent_id=body.agent_id)
    try:
        _maybe_qa_force_voice_error(request, settings)
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc
    started = time.perf_counter()
    try:
        audio, content_type, meta = synthesize_speech(
            settings, text=body.text, voice_key=body.voice, model_id=body.model
        )
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    headers = {
        "X-Voice-Provider": str(meta.get("provider") or ""),
        "X-Voice-Key": str(meta.get("voice_key") or ""),
        "X-Voice-Latency-Ms": str(elapsed_ms),
        "X-Voice-Error-Class": "ok",
        "Cache-Control": "no-store",
    }
    return Response(content=audio, media_type=content_type, headers=headers)


@router.post("/tts/stream")
def post_tts_stream(
    body: TtsRequest,
    request: Request,
    _user: Annotated[dict, Depends(get_current_user)],
    org: Annotated[str | None, Depends(get_org_context)],
    seat: Annotated[dict, Depends(require_seat_context())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    client = get_supabase_client(settings)
    assert_agent_voice_use(client, seat, org_id=str(org or ""), agent_id=body.agent_id)
    try:
        _maybe_qa_force_voice_error(request, settings)
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc

    def gen():
        try:
            for chunk in synthesize_speech_stream(
                settings, text=body.text, voice_key=body.voice, model_id=body.model
            ):
                yield chunk
        except VoiceProviderError as exc:
            # StreamingResponse can't raise mid-flight cleanly for clients that
            # already started; emit empty and log via exception for tests.
            raise _http_error(exc) from exc

    return StreamingResponse(
        gen(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "X-Voice-Stream": "elevenlabs"},
    )


@router.post("/preview")
def post_voice_preview(
    body: PreviewRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
    _seat: Annotated[dict, Depends(require_voice_configure())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Mandatory live audio preview before confirming any voice assignment."""
    started = time.perf_counter()
    try:
        audio, content_type, meta = synthesize_speech(
            settings, text=body.text, voice_key=body.voice, model_id=body.model
        )
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return Response(
        content=audio,
        media_type=content_type,
        headers={
            "X-Voice-Preview": "1",
            "X-Voice-Latency-Ms": str(elapsed_ms),
            "X-Voice-Key": str(meta.get("voice_key") or ""),
            "Cache-Control": "no-store",
        },
    )


@router.post("/stt")
async def post_stt(
    user: Annotated[dict, Depends(get_current_user)],
    org: Annotated[str | None, Depends(get_org_context)],
    seat: Annotated[dict, Depends(require_seat_context())],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
    conversation_id: str | None = None,
    agent_id: str | None = None,
    analyze_acoustic: bool = False,
) -> dict[str, Any]:
    org_id = str(org or "")
    client = get_supabase_client(settings)
    assert_agent_voice_use(client, seat, org_id=org_id, agent_id=agent_id)
    started = time.perf_counter()
    raw = await file.read()
    try:
        transcript, meta = transcribe_audio(
            settings,
            audio_bytes=raw,
            content_type=file.content_type or "application/octet-stream",
            filename=file.filename or "audio.webm",
        )
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if analyze_acoustic and raw:
        # Do NOT re-import get_supabase_client here — a local import makes the
        # name local for the whole function and raises UnboundLocalError on the
        # earlier client = get_supabase_client(settings) call (Dictate 500).
        from app.services.voice_acoustic_signal import schedule_acoustic_analysis

        schedule_acoustic_analysis(
            client=client,
            org_id=str(org or ""),
            user_id=str(user.get("id") or user.get("user_id") or "") or None,
            conversation_id=conversation_id,
            audio_bytes=raw,
            agent_id=agent_id,
        )
    return {
        "transcript": transcript,
        "latency_ms": elapsed_ms,
        "meta": meta,
        "pipeline": "text_into_existing_unified_turn",
        "write_confirm_policy": "nl_yes_same_path_as_text",
        "acoustic_analysis": "scheduled_async" if analyze_acoustic else "not_requested",
    }


@router.post("/stt-form")
async def post_stt_form(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    audio: UploadFile = File(...),
) -> dict[str, Any]:
    started = time.perf_counter()
    raw = await audio.read()
    try:
        transcript, meta = transcribe_audio(
            settings,
            audio_bytes=raw,
            content_type=audio.content_type or "application/octet-stream",
            filename=audio.filename or "audio.webm",
        )
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "transcript": transcript,
        "latency_ms": elapsed_ms,
        "meta": meta,
        "pipeline": "text_into_existing_unified_turn",
        "write_confirm_policy": "nl_yes_same_path_as_text",
    }


@router.post("/turn-taking/event")
def post_turn_taking_event(
    body: TurnEventRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
) -> dict[str, Any]:
    from app.services.voice_session_service import (
        apply_stt_event_to_turn_state,
        new_turn_state,
        turn_state_snapshot,
    )
    from app.services.voice_turn_taking import TurnSensitivity, parse_sensitivity

    state = new_turn_state(body.sensitivity)
    if body.state:
        # Restore lightweight fields
        state.provisional_user_text = str(body.state.get("provisional_user_text") or "")
        state.pending_finalize = bool(body.state.get("pending_finalize"))
        state.agent_speaking = bool(body.state.get("agent_speaking"))
        sens = parse_sensitivity(str(body.state.get("sensitivity") or body.sensitivity or "normal"))
        state.sensitivity = sens if isinstance(sens, TurnSensitivity) else TurnSensitivity.NORMAL
    state, finalized = apply_stt_event_to_turn_state(state, event=body.event)
    return {
        "state": turn_state_snapshot(state),
        "finalized_transcript": finalized,
        "default_sensitivity": "normal",
        "sensitivities": ["eager", "normal", "patient"],
    }


@router.post("/session/turn")
async def post_session_turn(
    body: SessionTurnRequest,
    request: Request,
    user: Annotated[dict, Depends(get_current_user)],
    org: Annotated[str | None, Depends(get_org_context)],
    seat: Annotated[dict, Depends(require_seat_context())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Streaming voice turn: unified-turn reasoning + progressive TTS (SSE JSON lines)."""
    from app.services.voice_session_service import stream_voice_turn_events

    org_id = str(org or "")
    user_id = str(user.get("id") or user.get("user_id") or "")
    client = get_supabase_client(settings)
    assert_agent_voice_use(client, seat, org_id=org_id, agent_id=body.agent_id)
    agent: dict[str, Any] | None = None
    if body.agent_id:
        try:
            rows = (
                client.table("agents")
                .select("*")
                .eq("org_id", org_id)
                .eq("id", body.agent_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            agent = rows[0] if rows else {"id": body.agent_id}
        except Exception:  # noqa: BLE001
            agent = {"id": body.agent_id}

    qa_force_header = request.headers.get(QA_FORCE_VOICE_ERROR_HEADER)

    async def gen() -> AsyncIterator[bytes]:
        try:
            forced = resolve_qa_force_voice_error(settings, header_value=qa_force_header)
            if forced:
                raise forced_voice_provider_error(forced)
            async for event in stream_voice_turn_events(
                settings=settings,
                org_id=org_id,
                user_id=user_id,
                text=body.text,
                agent=agent,
                conversation_id=body.conversation_id,
                conversation_history=body.history,
                voice_id=body.voice,
                tts_model=body.model,
            ):
                yield (json.dumps(event) + "\n").encode("utf-8")
        except VoiceProviderError as exc:
            yield (json.dumps({"type": "voice.error", **error_public_payload(exc)}) + "\n").encode(
                "utf-8"
            )
        except ValueError as exc:
            yield (
                json.dumps(
                    {
                        "type": "voice.error",
                        "detail": str(exc),
                        "error_class": "service_failure",
                        "billing_issue": False,
                    }
                )
                + "\n"
            ).encode("utf-8")

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-store",
            "X-Voice-Session": "1",
            "X-Write-Confirm-Policy": "nl_yes_same_path_as_text",
        },
    )


@router.put("/agents/{agent_id}/voice-profile")
def put_agent_voice_profile(
    agent_id: str,
    body: AgentVoiceProfileRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org: Annotated[str | None, Depends(get_org_context)],
    _seat: Annotated[dict, Depends(require_voice_configure())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """CONFIGURE: assign/change agent voice_profile (full or manager seat)."""
    from app.services.voice_agent_profile import normalize_voice_profile

    org_id = str(org or "")
    profile = normalize_voice_profile(body.voice_profile)
    client = get_supabase_client(settings)
    try:
        existing = (
            client.table("agents")
            .select("id")
            .eq("org_id", org_id)
            .eq("id", agent_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Agent not found")
        client.table("agents").update({"voice_profile": profile}).eq("org_id", org_id).eq(
            "id", agent_id
        ).execute()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)[:200]) from exc
    return {"agent_id": agent_id, "voice_profile": profile}


@router.post("/design")
def post_design_voice(
    body: DesignVoiceRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
    _seat: Annotated[dict, Depends(require_voice_configure())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    from app.services.voice_design_service import design_custom_voice

    try:
        return design_custom_voice(
            settings,
            voice_description=body.voice_description,
            guided=body.guided,
            model_id=body.model_id,
            auto_generate_text=body.auto_generate_text,
            text=body.text,
            guidance_scale=body.guidance_scale,
            loudness=body.loudness,
            seed=body.seed,
            should_enhance=body.should_enhance,
        )
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc


@router.get("/design/examples")
def get_design_examples(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
    _seat: Annotated[dict, Depends(require_voice_configure())],
) -> dict[str, Any]:
    from app.services.voice_design_service import design_examples

    return {"examples": design_examples()}


@router.post("/design/save")
def post_save_custom_voice(
    body: SaveCustomVoiceRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org: Annotated[str | None, Depends(get_org_context)],
    _seat: Annotated[dict, Depends(require_voice_configure())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    from app.services.voice_design_service import create_voice_from_preview

    try:
        created = create_voice_from_preview(
            settings,
            generated_voice_id=body.generated_voice_id,
            name=body.name,
            description=body.description,
        )
    except VoiceProviderError as exc:
        raise _http_error(exc) from exc
    org_id = str(org or "")
    row = {
        "org_id": org_id,
        "elevenlabs_voice_id": created.get("voice_id"),
        "name": body.name,
        "description": body.description,
        "generated_voice_id": body.generated_voice_id,
        "model_id": "eleven_ttv_v3",
        "personality_attributes": body.personality_attributes or {},
        "created_by": user.get("id") or user.get("user_id"),
    }
    try:
        client = get_supabase_client(settings)
        client.table("agent_custom_voices").upsert(
            row, on_conflict="org_id,elevenlabs_voice_id"
        ).execute()
    except Exception as exc:  # noqa: BLE001
        created["persist_warning"] = str(exc)[:200]
    created["reusable_across_org_agents"] = True
    return created


@router.get("/custom-voices")
def list_custom_voices(
    _user: Annotated[dict, Depends(get_current_user)],
    org: Annotated[str | None, Depends(get_org_context)],
    _seat: Annotated[dict, Depends(require_voice_configure())],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    org_id = str(org or "")
    try:
        client = get_supabase_client(settings)
        rows = (
            client.table("agent_custom_voices")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        rows = []
    return {
        "voices": rows,
        "reusable_across_org_agents": True,
        "reuse_note": "Saved Custom Voices are reusable across agents in this organization.",
    }


@router.post("/meter/minutes")
def post_meter_voice_minutes(
    body: MeterMinutesRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    from app.billing.service import get_supabase_client
    from app.services.voice_minutes_metering import record_voice_minutes

    org_id = str(org or "")
    client = get_supabase_client(settings)
    return record_voice_minutes(
        client,
        org_id=org_id,
        minutes=body.minutes,
        source_id=body.source_id or str(uuid.uuid4()),
        conversation_id=body.conversation_id,
        agent_id=body.agent_id,
        stt_seconds=body.stt_seconds,
        tts_seconds=body.tts_seconds,
    )


@router.get("/cogs")
def get_voice_cogs(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
) -> dict[str, Any]:
    from app.billing.voice_minutes_plan_rates import cogs_report

    return cogs_report()


@router.get("/ml/missing-capabilities")
def get_missing_ml_capabilities(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[str | None, Depends(get_org_context)],
) -> dict[str, Any]:
    from app.services.voice_acoustic_signal import other_missing_ml_capabilities_report

    return {"capabilities": other_missing_ml_capabilities_report(), "built_now": False}
