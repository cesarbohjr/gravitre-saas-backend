"""BE-00: Health check. No auth required."""
import os
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


def _dependency_checks() -> dict[str, str]:
    checks: dict[str, str] = {}

    try:
        from app.config import get_settings
        from app.workflows.repository import get_supabase_client

        settings = get_settings()
        client = get_supabase_client(settings)
        client.table("organizations").select("id").limit(1).execute()
        checks["database"] = "healthy"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"unhealthy: {type(exc).__name__}"

    try:
        from app.config import get_settings
        from app.core.redis_client import get_sync_redis

        redis = get_sync_redis(get_settings())
        if redis is None:
            checks["cache"] = "unavailable"
        else:
            redis.ping()
            checks["cache"] = "healthy"
    except Exception:  # noqa: BLE001
        checks["cache"] = "unavailable"

    if os.environ.get("TEMPORAL_HOST"):
        checks["temporal"] = "configured"
    if os.environ.get("CLICKHOUSE_HOST"):
        checks["clickhouse"] = "configured"

    return checks


@router.get("/health")
def health(request: Request) -> dict:
    """GET /health — returns 200 without auth (Railway healthcheck target)."""
    checks = _dependency_checks()
    db_ok = checks.get("database") == "healthy"
    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": request.app.version,
        "environment": os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "production",
        "git_sha": os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_SHA")
        or "unknown",
        "ai_disabled": _ai_disabled_flag(),
        "checks": checks,
    }
