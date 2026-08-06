"""HTTP middleware — rate limits on sensitive routes (auth, OAuth, webhooks, etc.)."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.rate_limiter import SENSITIVE_RATE_LIMITS, enforce_rate_limit


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method.upper()
        for rule_method, prefix, limit in SENSITIVE_RATE_LIMITS:
            if rule_method not in ("*", method):
                continue
            if not path.startswith(prefix):
                continue
            await enforce_rate_limit(
                request,
                endpoint=prefix,
                limit=limit,
            )
            break
        return await call_next(request)
