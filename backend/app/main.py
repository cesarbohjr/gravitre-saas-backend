"""BE-00: FastAPI application skeleton. Auth baseline, health, CORS, logging."""
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

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
    agent_memories,
    agent_tool_permissions,
    ai_system,
    agent_council,
    agent_interrupts,
    agent_jobs,
    assistant,
    auth,
    audit,
    billing,
    billing_sync,
    connector_oauth,
    connectors,
    marketplace,
    conversations,
    decisions,
    execution,
    entitlements,
    metrics,
    notifications,
    onboarding,
    optimization,
    goals,
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
    enterprise,
    settings,
    slack_commands,
)
from app.routers import (
    hubspot_triggers,
    knowledge_sync,
    workflow_schedules_internal,
    confluence_sync,
    notion_sync,
    google_analytics,
    pagerduty_triggers,
    salesforce_triggers,
    segment_triggers,
    workday_sync,
)
from app.routers.webhooks import hubspot_inbound, pagerduty_inbound, salesforce_inbound, segment_inbound
from app.routers.webhooks import stripe as stripe_webhooks
from app.samples.stripe_connect_v2.router import router as stripe_connect_sample_router
from app.routers.webhooks import workflow_triggers

print("Gravitre backend booting...")
logger = get_logger(__name__)


def _log_billing_startup_config() -> None:
    """Log billing configuration warnings at startup (observability only)."""
    try:
        from app.config import get_settings

        settings = get_settings()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Billing configuration check skipped: %s", str(exc))
        return

    stripe_key = (settings.stripe_secret_key or "").strip()
    if settings.app_env == "prod" and stripe_key and not stripe_key.startswith("sk_live_"):
        logger.warning("Billing configuration: STRIPE_SECRET_KEY appears to be a test key in production")
    if not stripe_key:
        logger.warning("Billing configuration: STRIPE_SECRET_KEY is missing")

    meter_name = (settings.stripe_meter_event_name or "").strip()
    if not meter_name:
        logger.warning("Billing configuration: STRIPE_METER_EVENT_NAME is missing")

    metered = [
        settings.stripe_metered_price_id_node,
        settings.stripe_metered_price_id_control,
        settings.stripe_metered_price_id_command,
    ]
    missing_metered = sum(1 for value in metered if not (value or "").strip())
    if not (settings.internal_api_secret or "").strip():
        logger.warning(
            "INTERNAL_API_SECRET is missing — internal cron endpoints "
            "(billing/sync-usage, knowledge/sync-due, workflows/schedules/dispatch-due) are unprotected"
        )

    logger.info(
        "Billing configuration: Stripe=%s, Metered prices=%s, Usage sync=%s",
        "configured" if stripe_key else "missing",
        "all set" if missing_metered == 0 else f"{missing_metered} missing",
        "scheduled via GitHub Actions and in-process scheduler",
    )


public_app_url = (os.environ.get("NEXT_PUBLIC_APP_URL") or "").strip()
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if public_app_url:
    allowed_origins.append(public_app_url.rstrip("/"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background loops: hourly usage-sync (idempotent Stripe metering) + the
    # durable async agent-job worker. Both are gated by env flags.
    from app.billing.usage_scheduler import start_usage_sync_scheduler, stop_usage_sync_scheduler
    from app.knowledge.sync_scheduler import (
        start_knowledge_sync_scheduler,
        stop_knowledge_sync_scheduler,
    )
    from app.operators.agent_jobs import start_agent_job_worker, stop_agent_job_worker
    from app.workflows.schedule_scheduler import (
        start_workflow_schedule_scheduler,
        stop_workflow_schedule_scheduler,
    )
    from app.workers.workflow_worker import start_workflow_run_worker, stop_workflow_run_worker

    app.state.usage_sync_task = start_usage_sync_scheduler()
    app.state.knowledge_sync_task = start_knowledge_sync_scheduler()
    app.state.workflow_schedule_task = start_workflow_schedule_scheduler()
    app.state.agent_job_task = start_agent_job_worker()
    app.state.workflow_run_task = start_workflow_run_worker()
    _log_billing_startup_config()
    try:
        yield
    finally:
        await stop_usage_sync_scheduler(getattr(app.state, "usage_sync_task", None))
        await stop_knowledge_sync_scheduler(getattr(app.state, "knowledge_sync_task", None))
        await stop_workflow_schedule_scheduler(getattr(app.state, "workflow_schedule_task", None))
        await stop_agent_job_worker(getattr(app.state, "agent_job_task", None))
        await stop_workflow_run_worker(getattr(app.state, "workflow_run_task", None))


app = FastAPI(
    title="Gravitre API",
    description="BE-00 — Foundation & Auth Baseline",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root() -> dict:
    return {"status": "running"}


@app.get("/health")
def health() -> dict:
    """Unauthenticated liveness probe for Railway / deployment monitors."""
    ai_disabled = False
    try:
        from app.config import get_settings

        ai_disabled = bool(get_settings().disable_ai)
    except Exception:
        # Health must succeed even when Settings cannot load (misconfigured env).
        pass
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": app.version,
        "ai_disabled": ai_disabled,
    }


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
        "X-Org-Id",
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
app.include_router(billing_sync.internal_router)
app.include_router(billing_sync.admin_router)
app.include_router(knowledge_sync.internal_router)
app.include_router(knowledge_sync.admin_router)
app.include_router(knowledge_sync.webhook_router)
app.include_router(workflow_schedules_internal.router)
app.include_router(connectors.router)
app.include_router(connectors.connectors_router)
app.include_router(connector_oauth.router)
app.include_router(marketplace.router)
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
app.include_router(enterprise.router)
app.include_router(stripe_webhooks.router)
app.include_router(stripe_connect_sample_router)
app.include_router(hubspot_inbound.router)
app.include_router(salesforce_inbound.router)
app.include_router(pagerduty_inbound.router)
app.include_router(workflow_triggers.router)
app.include_router(hubspot_triggers.router)
app.include_router(salesforce_triggers.router)
app.include_router(pagerduty_triggers.router)
app.include_router(notion_sync.router)
app.include_router(confluence_sync.router)
app.include_router(workday_sync.router)
app.include_router(google_analytics.router)
app.include_router(segment_triggers.router)
app.include_router(segment_inbound.router)
app.include_router(decisions.router)
app.include_router(agent_council.router)
app.include_router(execution.router)
app.include_router(rag_enhanced.router)
app.include_router(optimization.router)
app.include_router(goals.router)
app.include_router(scim.router)
app.include_router(ml_models.router)
app.include_router(ai_system.router)
app.include_router(assistant.router)
app.include_router(conversations.router)
app.include_router(agent_interrupts.router)
app.include_router(agent_jobs.router)
app.include_router(slack_commands.router)
app.include_router(operator_router.router)
app.include_router(operators_router.router)
app.include_router(operators_router.agents_router)
app.include_router(agent_memories.router)
app.include_router(agent_tool_permissions.router)
app.include_router(operators_router.sessions_router)
