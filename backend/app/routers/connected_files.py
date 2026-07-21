"""HTTP API for connected-file picker (browse vendors live; read-only)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.db import get_supabase_client
from app.services.connected_files_browse_service import browse_connected_files, list_connected_file_vendors
from app.services.tool_types import ToolContext

logger = get_logger(__name__)

router = APIRouter(prefix="/api/connected-files", tags=["connected-files"])


class BrowseQuery(BaseModel):
    vendor: str = Field(..., min_length=1)
    connector_id: str | None = None
    folder_id: str | None = None
    search: str | None = None
    page_size: int = Field(default=40, ge=1, le=100)


def _tool_ctx(
    settings: Settings,
    org_id: str,
    user_id: str,
    environment_name: str,
) -> ToolContext:
    client = get_supabase_client(settings)
    return ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=user_id,
        environment_name=environment_name,
    )


@router.get("/vendors")
def get_connected_file_vendors(
    org_id: Annotated[str, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    _user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    vendors = list_connected_file_vendors(client, org_id, environment_name=environment_name)
    return {
        "vendors": vendors,
        "storage_note": (
            "Gravitre reads selected files from your connected accounts for this conversation only. "
            "Files are not uploaded or stored in Gravitre."
        ),
    }


@router.get("/browse")
def browse_files(
    org_id: Annotated[str, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    vendor: str = Query(..., min_length=1),
    connector_id: str | None = Query(default=None),
    folder_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page_size: int = Query(default=40, ge=1, le=100),
) -> dict[str, Any]:
    user_id = str(user.get("user_id") or "")
    ctx = _tool_ctx(settings, org_id, user_id, environment_name)
    try:
        return browse_connected_files(
            ctx,
            vendor=vendor,
            connector_id=connector_id,
            folder_id=folder_id,
            search=search,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("connected_files browse failed org=%s vendor=%s error=%s", org_id, vendor, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not browse files from the connected account. Try again or reconnect the integration.",
        ) from exc
