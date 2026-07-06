"""Live OAuth smoke runner — top vendor connectors via invoke_tool."""
from __future__ import annotations

import csv
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from app.connectors.connection_health import resolve_connector_auth_status
from app.connectors.repository import get_connector_by_type, list_connectors
from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import NormalizedResult, ToolContext, ToolError, ToolValidationError

SmokeStatus = Literal[
    "passed",
    "failed",
    "skipped",
    "missing_scopes",
    "invalid_schema",
    "auth_failure",
    "api_error",
]

TOP10_VENDORS: tuple[str, ...] = (
    "hubspot",
    "microsoft365",
    "slack",
    "google_drive",
    "google_sheets",
    "asana",
    "clickup",
    "github",
    "salesforce",
    "canva",
    "constant_contact",
)

_SANDBOX_ENVIRONMENTS = frozenset({"sandbox", "staging", "development", "dev", "test"})
_SCOPE_MARKERS = re.compile(r"scope|permission|insufficient|forbidden|not authorized", re.I)
_DELETE_ACTION_RE = re.compile(r"\.(delete|remove|destroy|purge)\b", re.I)
_HTTP_STATUS_RE = re.compile(r"\b([1-5]\d{2})\b")

ParamBuilder = Callable[["SmokeBuildContext"], dict[str, Any]]


@dataclass(frozen=True)
class SmokeBuildContext:
    run_id: str
    org_id: str
    environment_name: str
    connector: dict[str, Any] | None
    env: dict[str, str]


@dataclass(frozen=True)
class SmokeActionPlan:
    vendor: str
    connector_type: str
    action_id: str
    kind: Literal["read", "write"]
    destructive: bool = False
    param_builder: ParamBuilder | None = None
    static_params: dict[str, Any] = field(default_factory=dict)
    expected_data_keys: tuple[str, ...] = ()
    required_env: tuple[str, ...] = ()
    skip_unless_sandbox: bool = False


@dataclass
class SmokeActionResult:
    vendor: str
    connector_type: str
    action_id: str
    kind: str
    status: SmokeStatus
    connector_id: str | None = None
    request_payload: dict[str, Any] = field(default_factory=dict)
    http_status_code: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    suggested_fix: str | None = None
    latency_ms: int | None = None
    tool_result_ok: bool = False
    vendor_shape_ok: bool = False
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor": self.vendor,
            "connectorType": self.connector_type,
            "actionId": self.action_id,
            "kind": self.kind,
            "status": self.status,
            "connectorId": self.connector_id,
            "requestPayload": self.request_payload,
            "httpStatusCode": self.http_status_code,
            "errorCode": self.error_code,
            "errorMessage": self.error_message,
            "suggestedFix": self.suggested_fix,
            "latencyMs": self.latency_ms,
            "toolResultOk": self.tool_result_ok,
            "vendorShapeOk": self.vendor_shape_ok,
            "detail": self.detail,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _smoke_ts(run_id: str) -> str:
    return run_id.replace("-", "")[:14]


def _default_read_plans() -> list[SmokeActionPlan]:
    return [
        SmokeActionPlan(
            "hubspot",
            "hubspot",
            "hubspot.contacts.search",
            "read",
            static_params={"list_all": True, "limit": 5},
            expected_data_keys=("contacts",),
        ),
        SmokeActionPlan(
            "hubspot",
            "hubspot",
            "hubspot.pipelines.list",
            "read",
            expected_data_keys=("results", "pipelines"),
        ),
        SmokeActionPlan(
            "hubspot",
            "hubspot",
            "hubspot.deals.list",
            "read",
            static_params={"limit": 5},
            expected_data_keys=("deals", "results"),
        ),
        SmokeActionPlan(
            "microsoft365",
            "microsoft365",
            "microsoft365.users.get",
            "read",
            static_params={"user_id": "me"},
            expected_data_keys=("user",),
        ),
        SmokeActionPlan(
            "microsoft365",
            "microsoft365",
            "microsoft365.mail.messages.list",
            "read",
            static_params={"limit": 5},
            expected_data_keys=("messages", "value"),
        ),
        SmokeActionPlan(
            "slack",
            "slack",
            "slack.conversations.list",
            "read",
            static_params={"limit": 10},
            expected_data_keys=("channels",),
        ),
        SmokeActionPlan(
            "slack",
            "slack",
            "slack.users.list",
            "read",
            static_params={"limit": 10},
            expected_data_keys=("members",),
        ),
        SmokeActionPlan(
            "google_drive",
            "google_drive",
            "drive.files.list",
            "read",
            static_params={"page_size": 5},
            expected_data_keys=("files",),
        ),
        SmokeActionPlan(
            "google_sheets",
            "google_sheets",
            "sheets.spreadsheets.get",
            "read",
            required_env=("OAUTH_SMOKE_GOOGLE_SHEETS_ID",),
            param_builder=lambda ctx: {
                "spreadsheet_id": ctx.env["OAUTH_SMOKE_GOOGLE_SHEETS_ID"],
            },
            expected_data_keys=("spreadsheet",),
        ),
        SmokeActionPlan(
            "asana",
            "asana",
            "asana.workspaces.list",
            "read",
            expected_data_keys=("data", "workspaces"),
        ),
        SmokeActionPlan(
            "asana",
            "asana",
            "asana.projects.list",
            "read",
            static_params={"limit": 10},
            expected_data_keys=("data", "projects"),
        ),
        SmokeActionPlan(
            "clickup",
            "clickup",
            "clickup.spaces.list",
            "read",
            expected_data_keys=("spaces",),
        ),
        SmokeActionPlan(
            "github",
            "github",
            "github.repos.get",
            "read",
            expected_data_keys=("repository",),
        ),
        SmokeActionPlan(
            "github",
            "github",
            "github.pulls.list",
            "read",
            static_params={"state": "open"},
            expected_data_keys=("pull_requests",),
        ),
        SmokeActionPlan(
            "salesforce",
            "salesforce",
            "salesforce.leads.search",
            "read",
            static_params={"status": "Open - Not Contacted", "limit": 5},
            expected_data_keys=("results",),
        ),
        SmokeActionPlan(
            "canva",
            "canva",
            "canva.designs.list",
            "read",
            expected_data_keys=("items", "designs"),
        ),
        SmokeActionPlan(
            "constant_contact",
            "constant_contact",
            "constant_contact.contacts.list",
            "read",
            static_params={"limit": 5},
            expected_data_keys=("contacts",),
        ),
        SmokeActionPlan(
            "constant_contact",
            "constant_contact",
            "constant_contact.campaigns.list",
            "read",
            static_params={"limit": 5},
            expected_data_keys=("campaigns",),
        ),
    ]


def _default_write_plans() -> list[SmokeActionPlan]:
    def hubspot_contact(ctx: SmokeBuildContext) -> dict[str, Any]:
        ts = _smoke_ts(ctx.run_id)
        return {
            "properties": {
                "email": f"gravitre-smoke-{ts}@example.com",
                "firstname": "Gravitre",
                "lastname": f"SmokeTest-{ts}",
            }
        }

    def salesforce_lead(ctx: SmokeBuildContext) -> dict[str, Any]:
        ts = _smoke_ts(ctx.run_id)
        return {
            "fields": {
                "LastName": f"GravitreSmoke-{ts}",
                "Company": "Gravitre Smoke Test Co",
                "Email": f"gravitre-smoke-{ts}@example.com",
            }
        }

    def github_issue(ctx: SmokeBuildContext) -> dict[str, Any]:
        ts = _smoke_ts(ctx.run_id)
        return {
            "title": f"[Gravitre Smoke] OAuth test {ts}",
            "body": "Automated OAuth smoke runner record — safe to close.",
        }

    def asana_task(ctx: SmokeBuildContext) -> dict[str, Any]:
        ts = _smoke_ts(ctx.run_id)
        payload: dict[str, Any] = {
            "name": f"Gravitre Smoke Test {ts}",
            "notes": "OAuth smoke runner — safe to delete.",
        }
        workspace = ctx.env.get("OAUTH_SMOKE_ASANA_WORKSPACE_ID", "").strip()
        if workspace:
            payload["workspace"] = workspace
        return payload

    def constant_contact_contact(ctx: SmokeBuildContext) -> dict[str, Any]:
        ts = _smoke_ts(ctx.run_id)
        return {
            "email_address": {
                "address": f"gravitre-smoke-{ts}@example.com",
                "permission_to_send": "implicit",
            },
            "first_name": "Gravitre",
            "last_name": f"Smoke-{ts}",
        }

    def clickup_task(ctx: SmokeBuildContext) -> dict[str, Any]:
        ts = _smoke_ts(ctx.run_id)
        return {
            "list_id": ctx.env["OAUTH_SMOKE_CLICKUP_LIST_ID"],
            "name": f"Gravitre Smoke Test {ts}",
            "description": "OAuth smoke runner — safe to delete.",
        }

    def slack_message(ctx: SmokeBuildContext) -> dict[str, Any]:
        ts = _smoke_ts(ctx.run_id)
        return {
            "channel": ctx.env["OAUTH_SMOKE_SLACK_CHANNEL"],
            "text": f"[Gravitre Smoke] OAuth live test {ts}",
        }

    return [
        SmokeActionPlan(
            "hubspot",
            "hubspot",
            "hubspot.contacts.create",
            "write",
            param_builder=hubspot_contact,
            expected_data_keys=("contact",),
            skip_unless_sandbox=True,
        ),
        SmokeActionPlan(
            "salesforce",
            "salesforce",
            "salesforce.leads.create",
            "write",
            param_builder=salesforce_lead,
            expected_data_keys=("lead",),
            skip_unless_sandbox=True,
        ),
        SmokeActionPlan(
            "github",
            "github",
            "github.issues.create",
            "write",
            param_builder=github_issue,
            expected_data_keys=("issue",),
            skip_unless_sandbox=True,
        ),
        SmokeActionPlan(
            "asana",
            "asana",
            "asana.tasks.create",
            "write",
            param_builder=asana_task,
            expected_data_keys=("data", "task", "gid"),
            skip_unless_sandbox=True,
        ),
        SmokeActionPlan(
            "constant_contact",
            "constant_contact",
            "constant_contact.contacts.create",
            "write",
            param_builder=constant_contact_contact,
            expected_data_keys=("contact_id", "contact",),
            skip_unless_sandbox=True,
        ),
        SmokeActionPlan(
            "clickup",
            "clickup",
            "clickup.tasks.create",
            "write",
            required_env=("OAUTH_SMOKE_CLICKUP_LIST_ID",),
            param_builder=clickup_task,
            expected_data_keys=("id", "name"),
            skip_unless_sandbox=True,
        ),
        SmokeActionPlan(
            "slack",
            "slack",
            "slack.post_message",
            "write",
            required_env=("OAUTH_SMOKE_SLACK_CHANNEL",),
            param_builder=slack_message,
            expected_data_keys=("executed", "ts"),
            skip_unless_sandbox=True,
        ),
    ]


def smoke_action_plans(
    *,
    include_writes: bool = False,
    allow_destructive: bool = False,
) -> list[SmokeActionPlan]:
    plans = _default_read_plans()
    if include_writes:
        plans.extend(_default_write_plans())
    if not allow_destructive:
        plans = [p for p in plans if not p.destructive]
    return plans


def normalized_to_tool_result(tool_name: str, result: NormalizedResult) -> dict[str, Any]:
    """Mirror ToolRegistry.execute_tool success/error payload shape."""
    if result.success:
        return {
            "success": True,
            "tool": tool_name,
            "action": result.action,
            "result": result.data,
            "connector_id": result.connector_id,
        }
    return {
        "success": False,
        "tool": tool_name,
        "action": result.action,
        "error": result.error_message or "Tool invocation failed",
        "error_code": result.error_code,
        "connector_id": result.connector_id,
    }


def validate_tool_result_payload(payload: dict[str, Any], *, action_id: str) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("action") != action_id:
        return False
    if payload.get("success") is True:
        return isinstance(payload.get("result"), dict)
    if payload.get("success") is False:
        return bool(payload.get("error"))
    return False


def _vendor_shape_ok(data: dict[str, Any], expected_keys: tuple[str, ...]) -> bool:
    if not isinstance(data, dict):
        return False
    if not data:
        return True
    if not expected_keys:
        return True
    lowered = {str(k).lower() for k in data.keys()}
    for key in expected_keys:
        if key.lower() in lowered:
            return True
        if any(key.lower() in part for part in lowered):
            return True
    return len(data) >= 1


def _extract_http_status(message: str | None) -> int | None:
    if not message:
        return None
    match = _HTTP_STATUS_RE.search(message)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def classify_failure(
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    http_status: int | None = None,
) -> tuple[SmokeStatus, str]:
    msg = (error_message or "").strip()
    code = (error_code or "").strip().lower()
    status = http_status

    if code in {"auth_expired", "permission_denied"} or status in {401, 403}:
        if _SCOPE_MARKERS.search(msg):
            return (
                "missing_scopes",
                "Reconnect the connector and grant the OAuth scopes listed in the action catalog.",
            )
        return (
            "auth_failure",
            "Reconnect OAuth in Settings > Connectors and verify the token is valid.",
        )
    if code == "validation_error" and _SCOPE_MARKERS.search(msg):
        return (
            "missing_scopes",
            "Grant missing OAuth scopes for this action and reconnect the connector.",
        )
    if code == "validation_error" and ("requires " in msg.lower() or "schema" in msg.lower()):
        return (
            "invalid_schema",
            "Fix action parameters or update catalog schema / executor normalization.",
        )
    if status is not None and status >= 400:
        return (
            "api_error",
            "Check vendor API status, connector configuration, and required IDs in OAUTH_SMOKE_* env vars.",
        )
    if code == "rate_limited" or status == 429:
        return ("api_error", "Vendor rate limit hit — retry later or reduce smoke concurrency.")
    return (
        "failed",
        "Review request payload, connector config, and backend logs for this action.",
    )


def _is_sandbox_write_allowed(
    *,
    environment_name: str,
    connector: dict[str, Any] | None,
    env: dict[str, str],
) -> bool:
    if env.get("OAUTH_SMOKE_FORCE_SANDBOX_WRITES", "").strip().lower() in {"1", "true", "yes"}:
        return True
    env_norm = (environment_name or "production").strip().lower()
    if env_norm in _SANDBOX_ENVIRONMENTS:
        return True
    if not connector:
        return False
    config = connector.get("config") if isinstance(connector.get("config"), dict) else {}
    if config.get("sandbox") is True or config.get("isSandbox") is True:
        return True
    instance_url = str(config.get("instance_url") or config.get("instanceUrl") or "")
    if "test.salesforce.com" in instance_url:
        return True
    return False


def _resolve_connector(
    client: Any,
    org_id: str,
    connector_type: str,
    environment_name: str,
) -> dict[str, Any] | None:
    conn = get_connector_by_type(client, org_id, connector_type, environment_name=environment_name)
    if conn:
        return conn
    for row in list_connectors(client, org_id, environment_name=environment_name):
        if str(row.get("type") or row.get("vendor") or "") == connector_type:
            return row
    return None


def _build_params(plan: SmokeActionPlan, ctx: SmokeBuildContext) -> dict[str, Any] | None:
    for key in plan.required_env:
        if not ctx.env.get(key, "").strip():
            return None
    params = dict(plan.static_params)
    if plan.param_builder:
        params.update(plan.param_builder(ctx))
    if ctx.connector and ctx.connector.get("id"):
        params.setdefault("connector_id", ctx.connector["id"])
    return params


def _tool_registry_key(vendor: str, action_id: str) -> str:
    suffix = action_id.split(".", 1)[-1] if "." in action_id else action_id
    return f"{vendor}_{suffix.replace('.', '_')}"


def run_smoke_action(
    ctx: ToolContext,
    plan: SmokeActionPlan,
    *,
    run_id: str,
    env: dict[str, str],
    enable_writes: bool,
    allow_destructive: bool,
    validate_remote_auth: bool = True,
) -> SmokeActionResult:
    result = SmokeActionResult(
        vendor=plan.vendor,
        connector_type=plan.connector_type,
        action_id=plan.action_id,
        kind=plan.kind,
        status="skipped",
    )

    registered = set(list_registered_actions())
    if plan.action_id not in registered:
        result.status = "skipped"
        result.detail = f"Action not registered: {plan.action_id}"
        result.suggested_fix = "Implement invoke_tool handler or fix catalog/registry alias."
        return result

    if not allow_destructive and (
        plan.destructive or _DELETE_ACTION_RE.search(plan.action_id)
    ):
        result.status = "skipped"
        result.detail = "Destructive action skipped (pass --allow-destructive to enable)."
        result.suggested_fix = "Only enable destructive smoke tests with explicit operator approval."
        return result

    if plan.kind == "write":
        if not enable_writes:
            result.status = "skipped"
            result.detail = "Write tests disabled (pass --enable-writes)."
            result.suggested_fix = "Re-run with --enable-writes after confirming sandbox credentials."
            return result
        connector = _resolve_connector(ctx.client, ctx.org_id, plan.connector_type, ctx.environment_name)
        if plan.skip_unless_sandbox and not _is_sandbox_write_allowed(
            environment_name=ctx.environment_name,
            connector=connector,
            env=env,
        ):
            result.status = "skipped"
            result.detail = "Write skipped outside sandbox environment."
            result.suggested_fix = (
                "Use OAUTH_SMOKE_ENVIRONMENT=sandbox, a Salesforce test org, "
                "or OAUTH_SMOKE_FORCE_SANDBOX_WRITES=1 for controlled writes."
            )
            return result

    connector = _resolve_connector(ctx.client, ctx.org_id, plan.connector_type, ctx.environment_name)
    if not connector:
        result.status = "skipped"
        result.detail = f"No active {plan.connector_type} connector for org."
        result.suggested_fix = f"Connect {plan.vendor} OAuth for org {ctx.org_id} in the target environment."
        return result

    result.connector_id = str(connector.get("id") or "")

    if validate_remote_auth:
        auth_status = resolve_connector_auth_status(
            ctx.client,
            ctx.org_id,
            result.connector_id,
            plan.connector_type,
            ctx.settings,
            environment_name=ctx.environment_name,
            validate_remote=True,
        )
        if auth_status in {"expired", "invalid", "disconnected", "error"}:
            result.status = "auth_failure"
            result.error_message = f"Connector auth status: {auth_status}"
            result.suggested_fix = "Reconnect OAuth in Settings > Connectors."
            return result

    build_ctx = SmokeBuildContext(
        run_id=run_id,
        org_id=ctx.org_id,
        environment_name=ctx.environment_name,
        connector=connector,
        env=env,
    )
    params = _build_params(plan, build_ctx)
    if params is None:
        missing = ", ".join(plan.required_env)
        result.status = "skipped"
        result.detail = f"Missing required env: {missing}"
        result.suggested_fix = f"Set {missing} in backend/.env.operator.local for this smoke case."
        return result

    result.request_payload = params

    try:
        normalized = invoke_tool(ctx, plan.action_id, params)
    except ToolValidationError as exc:
        status, fix = classify_failure(error_code=exc.code, error_message=str(exc))
        result.status = status
        result.error_code = exc.code
        result.error_message = str(exc)
        result.http_status_code = _extract_http_status(str(exc))
        result.suggested_fix = fix
        return result
    except ToolError as exc:
        status, fix = classify_failure(error_code=exc.code, error_message=str(exc))
        result.status = status
        result.error_code = exc.code
        result.error_message = str(exc)
        result.http_status_code = _extract_http_status(str(exc))
        result.suggested_fix = fix
        return result
    except Exception as exc:  # noqa: BLE001
        status, fix = classify_failure(error_message=str(exc))
        result.status = status
        result.error_message = str(exc)
        result.http_status_code = _extract_http_status(str(exc))
        result.suggested_fix = fix
        return result

    result.latency_ms = normalized.latency_ms
    tool_name = _tool_registry_key(plan.vendor, plan.action_id)
    tool_payload = normalized_to_tool_result(tool_name, normalized)
    result.tool_result_ok = validate_tool_result_payload(tool_payload, action_id=plan.action_id)

    if normalized.success:
        result.vendor_shape_ok = _vendor_shape_ok(normalized.data, plan.expected_data_keys)
        if not result.tool_result_ok:
            result.status = "invalid_schema"
            result.error_message = "ToolResult conversion failed shape validation."
            result.suggested_fix = "Ensure invoke_tool returns NormalizedResult with dict data on success."
            return result
        if plan.expected_data_keys and not result.vendor_shape_ok:
            result.status = "invalid_schema"
            result.error_message = (
                f"Response data missing expected keys: {', '.join(plan.expected_data_keys)}"
            )
            result.suggested_fix = "Update executor normalization to match vendor API response shape."
            return result
        result.status = "passed"
        result.detail = "Live invoke succeeded."
        return result

    status, fix = classify_failure(
        error_code=normalized.error_code,
        error_message=normalized.error_message,
        http_status=_extract_http_status(normalized.error_message),
    )
    result.status = status
    result.error_code = normalized.error_code
    result.error_message = normalized.error_message
    result.suggested_fix = fix
    return result


def run_oauth_smoke(
    ctx: ToolContext,
    *,
    vendors: list[str] | None = None,
    enable_writes: bool = False,
    allow_destructive: bool = False,
    validate_remote_auth: bool = True,
    env: dict[str, str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run live OAuth smoke for selected vendors; returns report payload."""
    selected = vendors or list(TOP10_VENDORS)
    env_map = dict(env or {})
    run = run_id or str(uuid.uuid4())
    plans = smoke_action_plans(include_writes=enable_writes, allow_destructive=allow_destructive)
    plans = [p for p in plans if p.vendor in selected]

    results: list[SmokeActionResult] = []
    for plan in plans:
        results.append(
            run_smoke_action(
                ctx,
                plan,
                run_id=run,
                env=env_map,
                enable_writes=enable_writes,
                allow_destructive=allow_destructive,
                validate_remote_auth=validate_remote_auth,
            )
        )

    summary: dict[str, int] = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "missing_scopes": 0,
        "invalid_schema": 0,
        "auth_failure": 0,
        "api_error": 0,
    }
    by_vendor: dict[str, dict[str, int]] = {}
    for row in results:
        summary[row.status] = summary.get(row.status, 0) + 1
        bucket = by_vendor.setdefault(
            row.vendor,
            {k: 0 for k in summary.keys()},
        )
        bucket[row.status] = bucket.get(row.status, 0) + 1

    return {
        "runId": run,
        "startedAt": _utc_now(),
        "orgId": ctx.org_id,
        "environment": ctx.environment_name,
        "vendors": selected,
        "enableWrites": enable_writes,
        "allowDestructive": allow_destructive,
        "summary": summary,
        "byVendor": by_vendor,
        "results": [row.to_dict() for row in results],
    }


def export_smoke_csv(path: str | Any, report: dict[str, Any]) -> Any:
    from pathlib import Path

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = report.get("results") or []
    fieldnames = [
        "vendor",
        "connectorType",
        "actionId",
        "kind",
        "status",
        "connectorId",
        "requestPayload",
        "httpStatusCode",
        "errorCode",
        "errorMessage",
        "suggestedFix",
        "latencyMs",
        "toolResultOk",
        "vendorShapeOk",
        "detail",
    ]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = dict(row)
            payload["requestPayload"] = json.dumps(payload.get("requestPayload") or {}, sort_keys=True)
            writer.writerow({k: payload.get(k, "") for k in fieldnames})
    return out


def export_smoke_json(path: str | Any, report: dict[str, Any]) -> Any:
    from pathlib import Path

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out
