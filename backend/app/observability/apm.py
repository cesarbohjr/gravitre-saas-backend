"""Optional APM hooks: Sentry error tracking and Prometheus request metrics."""
from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI, Request, Response

logger = get_logger(__name__)

_HTTP_REQUESTS = None
_HTTP_LATENCY = None


def init_sentry(app_env: str) -> None:
    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed")
        return

    traces_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE") or "0.1")
    sentry_sdk.init(
        dsn=dsn,
        environment=(app_env or "dev").strip(),
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=max(0.0, min(traces_rate, 1.0)),
        send_default_pii=False,
    )
    logger.info("Sentry initialized environment=%s", app_env)


def _prometheus_enabled() -> bool:
    return (os.environ.get("PROMETHEUS_ENABLED") or "").strip().lower() in {"1", "true", "yes"}


def setup_prometheus(app: FastAPI) -> None:
    global _HTTP_REQUESTS, _HTTP_LATENCY
    if not _prometheus_enabled():
        return
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
    except ImportError:
        logger.warning("PROMETHEUS_ENABLED is set but prometheus-client is not installed")
        return

    _HTTP_REQUESTS = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    _HTTP_LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        ["method", "path"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        path = request.url.path
        if path.startswith("/api/"):
            # Collapse high-cardinality paths (IDs) for scrape stability.
            parts = path.split("/")
            if len(parts) > 4 and parts[3] not in {
                "metrics",
                "auth",
                "billing",
                "workflows",
                "connectors",
                "internal",
            }:
                path = "/".join(parts[:4]) + "/{id}"
        _HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        _HTTP_LATENCY.labels(request.method, path).observe(duration)
        return response

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        from fastapi.responses import Response as FastAPIResponse

        return FastAPIResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    logger.info("Prometheus /metrics endpoint enabled")
