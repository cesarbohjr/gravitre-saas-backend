"""BE-00: Auth endpoints. GET /api/auth/me requires auth."""
from typing import Annotated

from fastapi import APIRouter, Depends
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
async def me(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """GET /api/auth/me — returns user_id, org_id?, email? (requires valid JWT)."""
    role: str | None = None
    if org_id:
        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        r = (
            client.table("organization_members")
            .select("role")
            .eq("org_id", org_id)
            .eq("user_id", current_user["user_id"])
            .limit(1)
            .execute()
        )
        if r.data and len(r.data) > 0:
            role = (r.data[0].get("role") or "").strip().lower() or None
    return {
        "user_id": current_user["user_id"],
        "org_id": org_id,
        "email": current_user.get("email"),
        "role": role,
    }
