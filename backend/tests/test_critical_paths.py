"""Production hardening — critical path tests."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.rate_limiter import RateLimiter, enforce_rate_limit
from app.main import global_exception_handler


@pytest.mark.asyncio
async def test_rate_limit_returns_429_with_retry_after():
    limiter = RateLimiter()
    identifier = "test:endpoint:org:org-1"
    first = await limiter.check(identifier, limit=1, window_seconds=60)
    assert first["allowed"] is True
    second = await limiter.check(identifier, limit=1, window_seconds=60)
    assert second["allowed"] is False
    assert second["retry_after"] is not None


@pytest.mark.asyncio
async def test_enforce_rate_limit_raises_http_429():
    limiter = RateLimiter()
    scope = {"type": "http", "method": "POST", "path": "/api/auth/login", "headers": []}
    request = Request(scope)

    async def _check(identifier: str, limit: int, window_seconds: int = 60):
        return await limiter.check(identifier, limit, window_seconds)

    with patch("app.core.rate_limiter.get_rate_limiter") as factory:
        factory.return_value.check = _check
        with patch("app.core.rate_limiter._org_or_ip", return_value="ip:127.0.0.1"):
            await enforce_rate_limit(request, endpoint="/api/auth", limit=1)
            with pytest.raises(HTTPException) as exc:
                await enforce_rate_limit(request, endpoint="/api/auth", limit=1)
    assert exc.value.status_code == 429
    assert exc.value.headers.get("Retry-After")


@pytest.mark.asyncio
async def test_global_exception_handler_returns_structured_500():
    scope = {"type": "http", "method": "GET", "path": "/boom", "headers": []}
    request = Request(scope)
    response = await global_exception_handler(request, RuntimeError("secret internal detail"))
    assert response.status_code == 500
    body = response.body.decode()
    assert "secret internal detail" not in body
    assert "INTERNAL_ERROR" in body
