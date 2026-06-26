from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings


def test_eval_scheduler_respects_interval():
    settings = Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="jwt",
        memory_promotion_eval_interval_seconds=28800,
    )
    assert settings.memory_promotion_eval_interval_seconds == 28800


def test_expiration_scheduler_respects_interval():
    settings = Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="jwt",
        memory_expiration_check_interval_seconds=86400,
    )
    assert settings.memory_expiration_check_interval_seconds == 86400


@pytest.mark.asyncio
async def test_manual_trigger_endpoints_require_internal_secret():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        promo = await client.post("/api/internal/ops/memory-promotion-run")
        expire = await client.post("/api/internal/ops/memory-expiration-run")
    assert promo.status_code in {401, 503}
    assert expire.status_code in {401, 503}
