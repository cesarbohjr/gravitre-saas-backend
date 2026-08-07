"""Tier 1 voice HTTP surface — TTS/STT only; chat pipeline unchanged."""
from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.services.tier1_voice_service import (
    VoiceProviderError,
    synthesize_speech,
    transcribe_audio,
    voice_status,
)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: str | None = Field(default=None, description="rachel | adam | josh | raw voice id")


@router.get("/status")
def get_voice_status(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[dict, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return voice_status(settings)


@router.post("/tts")
def post_tts(
    body: TtsRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[dict, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    started = time.perf_counter()
    try:
        audio, content_type, meta = synthesize_speech(
            settings, text=body.text, voice_key=body.voice
        )
    except VoiceProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    headers = {
        "X-Voice-Provider": str(meta.get("provider") or ""),
        "X-Voice-Key": str(meta.get("voice_key") or ""),
        "X-Voice-Latency-Ms": str(elapsed_ms),
        "Cache-Control": "no-store",
    }
    return Response(content=audio, media_type=content_type, headers=headers)


@router.post("/stt")
async def post_stt(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[dict, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
) -> dict[str, Any]:
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
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "transcript": transcript,
        "latency_ms": elapsed_ms,
        "meta": meta,
        "pipeline": "text_into_existing_unified_turn",
        "write_confirm_policy": "nl_yes_same_path_as_text",
    }


@router.post("/stt-form")
async def post_stt_form(
    _user: Annotated[dict, Depends(get_current_user)],
    _org: Annotated[dict, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    audio: UploadFile = File(...),
) -> dict[str, Any]:
    """Alias for multipart clients that prefer field name `audio`."""
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
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "transcript": transcript,
        "latency_ms": elapsed_ms,
        "meta": meta,
        "pipeline": "text_into_existing_unified_turn",
        "write_confirm_policy": "nl_yes_same_path_as_text",
    }
