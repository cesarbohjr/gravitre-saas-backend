"""GET /api/runs/{run_id}/cost: the time and cost record of one run (org members)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from app.auth.dependencies import require_org_member
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.services.run_cost_summary import run_cost_summary

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("/{run_id}/cost")
def get_run_cost(
    run_id: str,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _user, org_id, _role = member
    try:
        uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    summary = run_cost_summary(shared_service_client(settings, create_client), org_id, run_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return summary
