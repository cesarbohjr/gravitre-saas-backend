"""BE-00: FastAPI application skeleton. Auth baseline, health, CORS, logging."""
import asyncio
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
    admin_intelligence,
    mcp_admin,
    ai_system,
    agent_council,
    agent_interrupts,
    agent_jobs,
    agent_swarm,
    assistant,
    auth,
    audit,
    billing,
    billing_sync,
    connector_oauth,
    connectors,
    marketplace,
    conversations,
    meson,
    decisions,
    execution,
    entitlements,
    feedback_mode,
    metrics,
    memory_promotion,
    notifications,
    onboarding,
    optimization,
    optimization_suggestions,
    goals,
    health,
    org,
    lite,
    ml_models,
    ml_admin,
    ai_architecture_admin,
    rag,
    rag_enhanced,
    rag_admin,
    scim,
    schedules,
    search,
    sso,
    training,
    workflows,
    sources,
    environments,
    enterprise,
    federation,
    settings,
    slack_commands,
    verticals_healthcare,
    verticals_legal,
    verticals_real_estate,
    platform,
    platform_cs_internal,
    ops_internal,
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
            "(billing/sync-usage, knowledge/sync-due, workflows/schedules/dispatch-due, "
            "ops/rollup-daily, ops/connector-health) are unprotected"
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
    from app.data.source_sync_scheduler import (
        start_source_sync_scheduler,
        stop_source_sync_scheduler,
    )
    from app.knowledge.sync_scheduler import (
        start_knowledge_sync_scheduler,
        stop_knowledge_sync_scheduler,
    )
    from app.operators.agent_jobs import start_agent_job_worker, stop_agent_job_worker
    from app.workflows.schedule_scheduler import (
        start_workflow_schedule_scheduler,
        stop_workflow_schedule_scheduler,
    )
    from app.connectors.health_scheduler import (
        start_connector_health_scheduler,
        stop_connector_health_scheduler,
    )
    from app.schedulers.company_intelligence_scheduler import (
        start_company_intelligence_scheduler,
        stop_company_intelligence_scheduler,
    )
    from app.schedulers.memory_promotion_scheduler import (
        start_memory_expiration_scheduler,
        start_memory_promotion_scheduler,
        stop_scheduler as stop_memory_scheduler,
    )
    from app.schedulers.cache_warming_scheduler import (
        start_cache_warming_scheduler,
        stop_cache_warming_scheduler,
    )
    from app.workers.workflow_worker import start_workflow_run_worker, stop_workflow_run_worker

    temporal_host = (os.environ.get("TEMPORAL_HOST") or "").strip()
    use_temporal = bool(temporal_host)

    app.state.usage_sync_task = start_usage_sync_scheduler()
    app.state.knowledge_sync_task = start_knowledge_sync_scheduler()
    app.state.source_sync_task = start_source_sync_scheduler()
    app.state.workflow_schedule_task = start_workflow_schedule_scheduler()
    app.state.connector_health_task = start_connector_health_scheduler()
    if use_temporal:
        logger.info(
            "Temporal enabled — company intelligence, memory promotion/outcomes, "
            "and marketplace installs use durable workflows (asyncio fallback disabled)"
        )
        app.state.company_intelligence_task = None
        app.state.memory_promotion_task = None
        from app.temporal.worker import start_temporal_worker

        app.state.temporal_worker_task = asyncio.create_task(start_temporal_worker())
    else:
        logger.warning(
            "TEMPORAL_HOST not set — durable workflow execution disabled. "
            "Company intelligence, marketplace installs, and outcome measurement "
            "will use asyncio fallback (no retry on restart)."
        )
        app.state.company_intelligence_task = start_company_intelligence_scheduler()
        app.state.memory_promotion_task = start_memory_promotion_scheduler()
        app.state.temporal_worker_task = None
    app.state.memory_expiration_task = start_memory_expiration_scheduler()
    app.state.cache_warming_task = start_cache_warming_scheduler()
    app.state.agent_job_task = start_agent_job_worker()
    app.state.workflow_run_task = start_workflow_run_worker()
    _log_billing_startup_config()
    try:
        yield
    finally:
        await stop_usage_sync_scheduler(getattr(app.state, "usage_sync_task", None))
        await stop_knowledge_sync_scheduler(getattr(app.state, "knowledge_sync_task", None))
        await stop_source_sync_scheduler(getattr(app.state, "source_sync_task", None))
        await stop_workflow_schedule_scheduler(getattr(app.state, "workflow_schedule_task", None))
        await stop_connector_health_scheduler(getattr(app.state, "connector_health_task", None))
        await stop_company_intelligence_scheduler(getattr(app.state, "company_intelligence_task", None))
        await stop_memory_scheduler(getattr(app.state, "memory_promotion_task", None))
        temporal_task = getattr(app.state, "temporal_worker_task", None)
        if temporal_task is not None:
            temporal_task.cancel()
            try:
                await temporal_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                logger.warning("temporal worker stop error: %s", exc)
        await stop_memory_scheduler(getattr(app.state, "memory_expiration_task", None))
        await stop_cache_warming_scheduler(getattr(app.state, "cache_warming_task", None))
        await stop_agent_job_worker(getattr(app.state, "agent_job_task", None))
        await stop_workflow_run_worker(getattr(app.state, "workflow_run_task", None))


app = FastAPI(
    title="Gravitre API",
    description="BE-00 — Foundation & Auth Baseline",
    version="0.1.0",
    lifespan=lifespan,
)

from app.observability.apm import init_sentry, setup_prometheus

try:
    from app.config import get_settings as _get_settings_for_apm

    _apm_settings = _get_settings_for_apm()
    init_sentry(_apm_settings.app_env)
except Exception as exc:  # noqa: BLE001
    logger.warning("APM initialization skipped: %s", exc)

setup_prometheus(app)


@app.get("/")
def root() -> dict:
    return {"status": "running"}


app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(SettingsNotConfiguredError, settings_not_configured_handler)

# Dev-safe CORS: single-origin proxy preferred (see docs). Bearer token model: credentials=false.
from app.middleware.billing_gate import billing_access_gate_middleware

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
        remainder = path[len("/api/"):]  # v1/... or verticals/...
        segment = remainder.split("/", 1)[0]
        # Only /api/v1/... is versioned — not /api/verticals, /api/vendors, etc.
        if len(segment) >= 2 and segment[0] == "v" and segment[1].isdigit():
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


@app.middleware("http")
async def billing_access_gate(request: Request, call_next):
    return await billing_access_gate_middleware(request, call_next)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(sso.router)
app.include_router(org.router)
app.include_router(org.organizations_router)
app.include_router(billing.router)
app.include_router(billing_sync.internal_router)
app.include_router(billing_sync.admin_router)
app.include_router(ops_internal.router)
app.include_router(knowledge_sync.internal_router)
app.include_router(knowledge_sync.admin_router)
app.include_router(knowledge_sync.customer_router)
app.include_router(knowledge_sync.webhook_router)
app.include_router(workflow_schedules_internal.router)
app.include_router(platform_cs_internal.router)
app.include_router(connectors.router)
app.include_router(connectors.connectors_router)
app.include_router(connector_oauth.router)
app.include_router(marketplace.router)
app.include_router(rag.router)
app.include_router(rag_admin.router)
app.include_router(search.router)
app.include_router(training.router)
app.include_router(schedules.router)
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
app.include_router(platform.router)
app.include_router(federation.router)
app.include_router(verticals_healthcare.router)
app.include_router(verticals_legal.router)
app.include_router(verticals_real_estate.router)
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
app.include_router(agent_swarm.router)
app.include_router(execution.router)
app.include_router(rag_enhanced.router)
app.include_router(optimization.router)
app.include_router(goals.router)
app.include_router(scim.router)
app.include_router(ml_models.router)
    app.include_router(ml_admin.router)
    app.include_router(ai_architecture_admin.router)
app.include_router(ai_system.router)
app.include_router(assistant.router)
app.include_router(conversations.router)
app.include_router(meson.router)
app.include_router(agent_interrupts.router)
app.include_router(agent_jobs.router)
app.include_router(slack_commands.router)
app.include_router(operator_router.router)
app.include_router(operators_router.router)
app.include_router(operators_router.agents_router)
app.include_router(agent_memories.router)
app.include_router(admin_intelligence.router)
app.include_router(mcp_admin.router)
app.include_router(optimization_suggestions.router)
app.include_router(feedback_mode.router)
app.include_router(memory_promotion.router)
app.include_router(agent_tool_permissions.router)
app.include_router(operators_router.sessions_router)
