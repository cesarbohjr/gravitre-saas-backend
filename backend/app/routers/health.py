"""BE-00: Health check. No auth required."""
from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings
from app.coordination.flags import coordination_layer_health

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """GET /health — returns 200 without auth."""
    settings = get_settings()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "coordinationLayer": coordination_layer_health(settings),
    }
