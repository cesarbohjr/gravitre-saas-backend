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
    unified_shadow = False
    unified_live = False
    unified_embed_tools = False
    unified_task_tier = ""
    unified_embed_min_catalog = None
    try:
        from app.config import get_settings

        s = get_settings()
        unified_shadow = bool(getattr(s, "unified_turn_shadow_enabled", False))
        unified_live = bool(getattr(s, "unified_turn_live_enabled", False))
        unified_embed_tools = bool(getattr(s, "unified_turn_embedding_tool_retrieval", False))
        unified_task_tier = str(getattr(s, "unified_turn_task_model_tier", "") or "")
        unified_embed_min_catalog = int(getattr(s, "unified_turn_embed_min_catalog_tools", 40) or 40)
    except Exception:  # noqa: BLE001
        unified_shadow = (os.environ.get("UNIFIED_TURN_SHADOW_ENABLED") or "").lower() in {
            "1",
            "true",
            "yes",
        }
        unified_live = (os.environ.get("UNIFIED_TURN_LIVE_ENABLED") or "").lower() in {
            "1",
            "true",
            "yes",
        }
        unified_embed_tools = (os.environ.get("UNIFIED_TURN_EMBEDDING_TOOL_RETRIEVAL") or "true").lower() in {
            "1",
            "true",
            "yes",
        }
        unified_task_tier = os.environ.get("UNIFIED_TURN_TASK_MODEL_TIER") or ""

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": request.app.version,
        "environment": os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "production",
        "git_sha": os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_SHA")
        or "unknown",
        "ai_disabled": _ai_disabled_flag(),
        "unified_turn_shadow_enabled": unified_shadow,
        "unified_turn_live_enabled": unified_live,
        "unified_turn_embedding_tool_retrieval": unified_embed_tools,
        "unified_turn_embed_min_catalog_tools": unified_embed_min_catalog,
        "unified_turn_task_model_tier": unified_task_tier or None,
        "checks": checks,
    }
