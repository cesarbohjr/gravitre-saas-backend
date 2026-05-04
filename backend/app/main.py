"""BE-00: FastAPI application skeleton. Auth baseline, health, CORS, logging."""
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import SettingsNotConfiguredError
from app.core.errors import (
    http_exception_handler,
    settings_not_configured_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, request_id_ctx
from app.operator_module import router as operator_router
from app.operators import router as operators_router
from app.routers import (
    ai_system,
    agent_council,
    auth,
    audit,
    billing,
    connectors,
    decisions,
    execution,
    entitlements,
    metrics,
    notifications,
    onboarding,
    optimization,
    org,
    lite,
    ml_models,
    rag,
    rag_enhanced,
    rag_admin,
    scim,
    search,
    sso,
    training,
    workflows,
    sources,
    environments,
    settings,
)
from app.routers.webhooks import stripe as stripe_webhooks
from app.routers.webhooks import workflow_triggers

print("Gravitre backend booting...")
logger = get_logger(__name__)


public_app_url = (os.environ.get("NEXT_PUBLIC_APP_URL") or "").strip()
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if public_app_url:
    allowed_origins.append(public_app_url.rstrip("/"))

app = FastAPI(
    title="Gravitre API",
    description="BE-00 — Foundation & Auth Baseline",
    version="0.1.0",
)


@app.get("/")
def root() -> dict:
    return {"status": "running"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(SettingsNotConfiguredError, settings_not_configured_handler)

# Dev-safe CORS: single-origin proxy preferred (see docs). Bearer token model: credentials=false.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-Id",
        "X-Api-Version",
        "Accept-Version",
        "X-Environment",
    ],
)


def _normalize_version(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().lower()
    if not value:
        return None
    if value.startswith("v"):
        value = value[1:]
    if not value:
        return None
    return f"v{value}"


@app.middleware("http")
async def api_versioning(request: Request, call_next):
    supported_versions = {"v1"}
    default_version = "v1"
    path = request.scope.get("path") or ""
    path_version: str | None = None

    if path.startswith("/api/v"):
        remainder = path[len("/api/"):]  # v1/...
        segment = remainder.split("/", 1)[0]
        path_version = _normalize_version(segment)
        if not path_version or path_version not in supported_versions:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Unsupported API version"},
            )
        suffix = remainder[len(segment):]  # includes leading "/" if present
        new_path = "/api" + suffix
        request.scope["path"] = new_path
        request.scope["raw_path"] = new_path.encode("utf-8")

    header_version = _normalize_version(
        request.headers.get("x-api-version") or request.headers.get("accept-version")
    )
    if header_version and header_version not in supported_versions:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Unsupported API version"},
        )
    if path_version and header_version and path_version != header_version:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "API version mismatch"},
        )

    resolved = header_version or path_version or default_version
    response = await call_next(request)
    if path.startswith("/api") or path.startswith("/api/v"):
        response.headers["x-api-version"] = resolved
    return response


@app.middleware("http")
async def request_tracing(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request_id_ctx.set(request_id)
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s %s %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    # Always set x-request-id for traceability
    if "x-request-id" not in response.headers:
        response.headers["x-request-id"] = request_id
    return response


app.include_router(auth.router)
app.include_router(sso.router)
app.include_router(org.router)
app.include_router(org.organizations_router)
app.include_router(billing.router)
app.include_router(connectors.router)
app.include_router(connectors.connectors_router)
app.include_router(rag.router)
app.include_router(rag_admin.router)
app.include_router(search.router)
app.include_router(training.router)
app.include_router(sources.router)
app.include_router(workflows.router)
app.include_router(workflows.approvals_router)
app.include_router(workflows.runs_router)
app.include_router(audit.router)
app.include_router(metrics.router)
app.include_router(notifications.router)
app.include_router(onboarding.router)
app.include_router(lite.router)
app.include_router(entitlements.router)
app.include_router(environments.router)
app.include_router(settings.router)
app.include_router(stripe_webhooks.router)
app.include_router(workflow_triggers.router)
app.include_router(decisions.router)
app.include_router(agent_council.router)
app.include_router(execution.router)
app.include_router(rag_enhanced.router)
app.include_router(optimization.router)
app.include_router(scim.router)
app.include_router(ml_models.router)
app.include_router(ai_system.router)
app.include_router(operator_router.router)
app.include_router(operators_router.router)
app.include_router(operators_router.agents_router)
app.include_router(operators_router.sessions_router)
