"""Internal cron API for workflow schedule dispatch (STA-47)."""
from __future__ import annotations

import asyncio
import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.services.workflow_schedule_service import dispatch_due_workflow_schedules

router = APIRouter(prefix="/api/internal/workflows", tags=["workflows-internal"])


async def require_internal_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> None:
    secret = (settings.internal_api_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_SECRET is not configured",
        )
    if not x_internal_secret or not hmac.compare_digest(x_internal_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret")


@router.post("/schedules/dispatch-due")
async def internal_dispatch_due_schedules(
    _secret: Annotated[None, Depends(require_internal_secret)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Cron entry: dispatch all workflow schedules that are due."""
    return await asyncio.to_thread(dispatch_due_workflow_schedules, settings)
