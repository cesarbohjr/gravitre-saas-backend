"""BE-00: Health check. No auth required."""
from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


def _ai_disabled_flag() -> bool:
    try:
        from app.config import get_settings

        return bool(get_settings().disable_ai)
    except Exception:
        # Health must succeed even when Settings cannot load (misconfigured env).
        return False


@router.get("/health")
def health(request: Request) -> dict:
    """GET /health — returns 200 without auth."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": request.app.version,
        "ai_disabled": _ai_disabled_flag(),
    }
