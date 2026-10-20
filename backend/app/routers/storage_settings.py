"""Storage settings API: usage meter, bring-your-own file storage, file download links.

GET  /api/settings/storage/usage               member: latest snapshot vs plan limit
GET  /api/settings/storage/byo                 admin: target (redacted) and availability
PUT  /api/settings/storage/byo                 admin, entitled, flag on: save target
POST /api/settings/storage/byo/test            admin, entitled, flag on: probe put/head/delete
DELETE /api/settings/storage/byo               admin: remove target
GET  /api/settings/storage/files/download-url  member: time-limited link to an org file

Only files move to an org's own bucket; database rows stay in Supabase.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.errors import error_detail
from app.core.logging import get_logger
from app.services import byo_storage
from app.services.storage_meter import storage_usage_view
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)

router = APIRouter(prefix="/api/settings/storage", tags=["settings"])

BYO_SCOPE_NOTE = (
    "Only uploaded files are stored in your bucket. Database records such as memories, "
    "knowledge chunks and embeddings stay in Gravitre's database."
)


class ByoTargetRequest(BaseModel):
    endpointUrl: str | None = Field(default=None, max_length=300)
    region: str = Field(..., min_length=2, max_length=32)
    bucket: str = Field(..., min_length=3, max_length=63)
    pathPrefix: str | None = Field(default=None, max_length=200)
    accessKeyId: str | None = Field(default=None, max_length=256)
    secretAccessKey: str | None = Field(default=None, max_length=512)


def _resolve_entitlements(settings: Settings, org_id: str) -> dict[str, Any] | None:
    try:
        from app.middleware.entitlements import resolve_entitlements

        return resolve_entitlements(settings, org_id)
    except Exception as exc:  # noqa: BLE001 - usage still renders without a limit
        logger.warning("storage_entitlements_failed org_id=%s error=%s", org_id, type(exc).__name__)
        return None


def _byo_flags(settings: Settings, org_id: str) -> dict[str, bool]:
    flag = getattr(settings, "byo_storage_enabled", False) is True
    entitled = byo_storage.org_entitled(settings, org_id)
    return {"flagEnabled": flag, "entitled": entitled, "available": flag and entitled}


def _require_byo_available(settings: Settings, org_id: str) -> None:
    flags = _byo_flags(settings, org_id)
    if not flags["entitled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Feature unavailable", "UNAUTHORIZED", {"feature": "byo_storage"}),
        )
    if not flags["flagEnabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Bring-your-own storage is not switched on yet", "FEATURE_DISABLED", {}),
        )


@router.get("/usage")
def get_storage_usage(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    if getattr(settings, "storage_meter_enabled", False) is not True:
        return storage_usage_view(None, settings, org_id, None)
    client = shared_service_client(settings, create_client)
    return storage_usage_view(client, settings, org_id, _resolve_entitlements(settings, org_id))


@router.get("/byo")
def get_byo_target(
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = admin_ctx
    flags = _byo_flags(settings, org_id)
    target = None
    if flags["available"]:
        client = shared_service_client(settings, create_client)
        try:
            target = byo_storage.public_target_view(byo_storage.load_target(client, org_id))
        except Exception as exc:  # noqa: BLE001 - migration not applied yet
            logger.warning("byo_storage_read_failed org_id=%s error=%s", org_id, type(exc).__name__)
    return {**flags, "target": target, "scope": BYO_SCOPE_NOTE}


@router.put("/byo")
def put_byo_target(
    body: ByoTargetRequest,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin_ctx
    _require_byo_available(settings, org_id)
    client = shared_service_client(settings, create_client)
    try:
        target = byo_storage.save_target(client, settings, org_id, user.get("user_id"), body.model_dump())
    except byo_storage.ByoStorageError as exc:
        raise HTTPException(status_code=400, detail=error_detail(str(exc), "VALIDATION_ERROR")) from exc
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="storage.byo_target.saved",
        resource_type="org_settings",
        resource_id=str(org_id),
        metadata={
            "bucket": target.get("bucket"),
            "region": target.get("region"),
            "endpointUrl": target.get("endpointUrl"),
            "credentialsChanged": bool(body.accessKeyId or body.secretAccessKey),
        },
    )
    return {"target": target, "scope": BYO_SCOPE_NOTE}


@router.post("/byo/test")
def test_byo_target(
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin_ctx
    _require_byo_available(settings, org_id)
    client = shared_service_client(settings, create_client)
    try:
        result = byo_storage.probe_target(client, settings, org_id)
    except byo_storage.ByoStorageError as exc:
        raise HTTPException(status_code=400, detail=error_detail(str(exc), "VALIDATION_ERROR")) from exc
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="storage.byo_target.tested",
        resource_type="org_settings",
        resource_id=str(org_id),
        metadata={"ok": result["ok"], "steps": result["steps"]},
    )
    return {**result, "target": byo_storage.public_target_view(byo_storage.load_target(client, org_id))}


@router.delete("/byo")
def delete_byo_target(
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin_ctx
    client = shared_service_client(settings, create_client)
    removed = byo_storage.delete_target(client, org_id)
    if removed:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user["user_id"],
            action="storage.byo_target.removed",
            resource_type="org_settings",
            resource_id=str(org_id),
            metadata={},
        )
    return {"removed": removed}


@router.get("/files/download-url")
def get_file_download_url(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    bucket: Annotated[str, Query(min_length=1, max_length=100)],
    path: Annotated[str, Query(min_length=1, max_length=1024)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    allowed = {
        (getattr(settings, "rag_uploads_bucket", "") or "rag-uploads").strip(),
        (getattr(settings, "chat_artifacts_bucket", "") or "chat-artifacts").strip(),
    }
    if bucket not in allowed:
        raise HTTPException(status_code=404, detail="File not found")
    client = shared_service_client(settings, create_client)
    try:
        return byo_storage.resolve_download_url(client, settings, org_id=org_id, logical_bucket=bucket, path=path)
    except byo_storage.ByoStorageUnavailableError as exc:
        raise HTTPException(status_code=409, detail=error_detail(str(exc), "STORAGE_TARGET_REMOVED")) from exc
    except byo_storage.ByoStorageError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
