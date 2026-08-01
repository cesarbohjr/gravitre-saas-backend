"""Generic HTTP executor for catalog connector tools."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.connectors.catalog_http.profiles import VENDOR_HTTP_PROFILES, VendorHttpProfile
from app.connectors.connector_tool_auth import (
    resolve_github_access_token,
    resolve_microsoft365_access_token,
    resolve_slack_bot_token,
    resolve_zendesk_auth,
)
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.services.tool_types import NormalizedResult, ToolAuthExpiredError, ToolContext, ToolValidationError

TIMEOUT_SEC = 30.0

_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")


def _resolve_profile(vendor: str) -> VendorHttpProfile | None:
    return VENDOR_HTTP_PROFILES.get(vendor)


def _format_base_url(profile: VendorHttpProfile, connector: dict[str, Any]) -> str:
    cfg = connector.get("config") or {}
    base = profile.base_url
    replacements = {
        "dc": str(cfg.get("dc") or cfg.get("mailchimp_dc") or "us1"),
        "domain": str(cfg.get("domain") or cfg.get("subdomain") or ""),
        "instance_url": str(cfg.get("instance_url") or cfg.get("base_url") or "").rstrip("/"),
        "cloud_id": str(cfg.get("cloud_id") or cfg.get("atlassian_cloud_id") or ""),
        "munchkin_id": str(cfg.get("munchkin_id") or ""),
        "subdomain": str(cfg.get("subdomain") or ""),
        "account": str(cfg.get("account") or ""),
        "shop": str(cfg.get("shop") or cfg.get("shop_domain") or ""),
        "region": str(cfg.get("region") or "us-east-1"),
    }
    for key, value in replacements.items():
        if value:
            base = base.replace("{" + key + "}", value)
    return base.rstrip("/")


def _infer_route(suffix: str) -> tuple[str, str, tuple[str, ...]]:
    parts = suffix.split(".")
    if len(parts) >= 2 and parts[0] == "batch":
        return "POST", f"/batch/{'/'.join(parts[1:])}", ()
    if len(parts) >= 3 and parts[-2] == "batch":
        return "POST", f"/{'/'.join(parts[:-1])}", ()
    if len(parts) >= 2:
        resource, verb = parts[0], parts[1]
        plural = resource if resource.endswith("s") else f"{resource}s"
        id_param = f"{resource}_id"
        if verb == "get":
            return "GET", f"/{plural}/{{{id_param}}}", (id_param,)
        if verb == "list":
            return "GET", f"/{plural}", ()
        if verb == "create":
            return "POST", f"/{plural}", ()
        if verb in {"update", "modify"}:
            return "PUT", f"/{plural}/{{{id_param}}}", (id_param,)
        if verb == "delete":
            return "DELETE", f"/{plural}/{{{id_param}}}", (id_param,)
        if verb in {"search", "query", "run", "reply", "send", "apply", "trigger", "schedule", "enroll", "add", "upload", "export", "sync", "track", "identify", "group", "comment", "assign", "transition", "acknowledge", "resolve", "escalate", "merge", "notify", "optimize", "set", "status", "subscribe", "generate", "preview", "elect", "pay", "issue", "checklist", "brief", "note", "enrich", "convert", "move", "append", "replace_text", "insert_table", "quick_add", "batch_get", "batch_update", "permissions", "changes", "charts", "pivot", "watch", "drafts", "labels", "threads", "messages", "files", "documents", "values", "spreadsheets", "properties", "reports", "metadata", "audiences", "conversions", "realtime", "funnels", "events", "calendars", "freebusy", "acl", "workbook", "mail", "teams", "excel", "side_conversations", "macros", "automations", "satisfaction", "series", "tags", "rules", "scenarios", "campaigns", "members", "audiences", "segments", "automations", "cohorts", "annotations", "engage", "profiles", "organizations", "people", "sequences", "tasks", "projects", "users", "sections", "stories", "lists", "spaces", "comments", "time_entries", "goals", "pages", "spaces", "labels", "attachments", "contacts", "campaigns", "lists", "tags", "conversations", "tickets", "customers", "macros", "rules", "partners", "sales", "inventory", "invoices", "manufacturing", "crm", "courses", "enrollments", "certificates", "workers", "paystatements", "events", "timecards", "profile", "payroll", "benefits", "bases", "records", "webhooks", "buckets", "objects", "designs", "folders", "exports", "autofill", "brand", "employees", "payrolls", "companies", "contractors", "organizations", "messages", "analytics", "inbox", "approvals", "teams", "channels", "meetings", "tabs", "members", "presence", "sources", "destinations", "trackingplans", "alias", "page", "incidents", "services", "oncalls", "pulls", "issues", "prospects", "leads", "programs", "patients", "appointments", "prior_auth", "matters", "conflicts", "intake", "mls", "handoff", "candidates", "jobs", "offers", "applications", "interviews", "scorecards", "notes", "deals", "accounts", "opportunities", "tasks", "bills", "payments", "vendors", "customers", "accounts", "companyinfo", "subscriptions", "invoices", "transactions", "identity", "investments", "links", "items", "journalentries", "orgunits", "timeoff", "positions", "workers"}:
            return "POST", f"/{plural}/{verb}", ()
    return "POST", f"/{suffix.replace('.', '/')}", ()


def _resolve_auth(
    ctx: ToolContext,
    profile: VendorHttpProfile,
    connector: dict[str, Any],
) -> tuple[dict[str, str], str | None]:
    cid = str(connector["id"])
    headers: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
    for key, value in profile.extra_headers:
        headers[key] = value

    if profile.auth == "slack_bot":
        token = resolve_slack_bot_token(ctx.client, ctx.org_id, cid, ctx.settings)
        if not token:
            raise ToolAuthExpiredError("Slack not connected")
        headers["Authorization"] = f"Bearer {token}"
        return headers, cid

    if profile.auth == "microsoft365":
        token = resolve_microsoft365_access_token(
            ctx.client, ctx.org_id, cid, ctx.settings, environment_name=ctx.environment_name
        )
        if not token:
            raise ToolAuthExpiredError("Microsoft 365 OAuth not connected")
        headers["Authorization"] = f"Bearer {token}"
        return headers, cid

    if profile.auth == "zendesk":
        subdomain, email, api_token, oauth = resolve_zendesk_auth(
            ctx.client, ctx.org_id, connector, ctx.settings, environment_name=ctx.environment_name
        )
        if oauth:
            headers["Authorization"] = f"Bearer {oauth}"
        elif email and api_token:
            import base64

            raw = f"{email}/token:{api_token}"
            headers["Authorization"] = "Basic " + base64.b64encode(raw.encode()).decode()
        else:
            raise ToolAuthExpiredError("Zendesk not connected")
        return headers, cid

    if profile.auth == "github":
        token = resolve_github_access_token(
            ctx.client, ctx.org_id, cid, ctx.settings, environment_name=ctx.environment_name
        )
        if not token:
            raise ToolAuthExpiredError("GitHub not connected")
        headers["Authorization"] = f"Bearer {token}"
        return headers, cid

    if profile.auth == "generic_oauth":
        token, err = ensure_generic_session(
            ctx.client,
            ctx.org_id,
            cid,
            ctx.settings,
            vendor=profile.vendor,
            environment_name=ctx.environment_name,
        )
        if not token:
            raise ToolAuthExpiredError(err or f"{profile.vendor} OAuth not connected")
        headers["Authorization"] = f"Bearer {token}"
        return headers, cid

    if profile.auth == "api_token":
        token = get_decrypted_secret(ctx.client, cid, "api_token", ctx.settings) or get_decrypted_secret(
            ctx.client, cid, "token", ctx.settings
        )
        if not token:
            raise ToolAuthExpiredError(f"{profile.vendor} API token not configured")
        headers["Authorization"] = f"Bearer {token.strip()}"
        return headers, cid

    return headers, cid


def _build_path(path_template: str, params: dict[str, Any], path_params: tuple[str, ...]) -> str:
    path = path_template
    for key in path_params:
        value = params.get(key) or params.get(_camel(key))
        if not value:
            alt = key.replace("_id", "Id") if "_id" in key else key
            value = params.get(alt) or params.get("id")
        if not value:
            raise ToolValidationError(f"Missing path param: {key}")
        path = path.replace("{" + key + "}", str(value))
    return path


def _camel(key: str) -> str:
    parts = key.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def make_catalog_http_executor(action: str) -> Any:
    vendor, _, suffix = action.partition(".")
    if not suffix:
        raise ValueError(f"Invalid catalog action: {action}")

    profile = _resolve_profile(vendor)
    method, path_template, path_params = _infer_route(suffix)

    def _exec(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
        if not profile:
            raise ToolValidationError(f"No HTTP profile for vendor: {vendor}")
        connector_id = params.get("connector_id") or ctx.connector_id
        conn = None
        if connector_id:
            conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
        else:
            conn = get_connector_by_type(
                ctx.client, ctx.org_id, profile.connector_type, environment_name=ctx.environment_name
            )
        if not conn:
            from app.services.tool_types import ToolConnectorNotConnectedError

            raise ToolConnectorNotConnectedError(
                f"No active {profile.display_name if hasattr(profile, 'display_name') else vendor} connector"
            )
        cid = str(conn["id"])
        enforce_rate_limit(ctx.client, ctx.org_id, profile.vendor, profile.connector_type, cid)
        headers, _ = _resolve_auth(ctx, profile, conn)
        base = _format_base_url(profile, conn)
        path = profile.path_prefix + _build_path(path_template, params, path_params)
        url = f"{base}{path}"

        query_keys = ("limit", "top", "page", "page_size", "per_page", "cursor", "offset", "query", "q", "filter", "status")
        query = {k: params[k] for k in query_keys if params.get(k) is not None}
        body_keys = set(params.keys()) - set(query.keys()) - {"connector_id", "path_prefix"}
        json_body = {k: v for k, v in params.items() if k in body_keys and v is not None} or None
        if method in {"GET", "DELETE"}:
            json_body = None

        with httpx.Client(timeout=TIMEOUT_SEC) as client:
            response = client.request(method, url, headers=headers, params=query or None, json=json_body)
        if response.status_code >= 400:
            detail = response.text[:500]
            raise ToolValidationError(f"{action} failed ({response.status_code}): {detail}")
        data: Any = {}
        if response.text:
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text[:2000]}
        payload = data if isinstance(data, dict) else {"result": data}
        # Soft OutcomeEffect tag for mutating catalog HTTP writes.
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            from app.services.connector_outcome_effects import has_effect_proof, is_mutating_action

            if is_mutating_action(action) and "outcome_effect" not in payload:
                payload = dict(payload)
                payload["outcome_effect"] = (
                    "created" if has_effect_proof(payload) else "unknown"
                )
        return NormalizedResult(success=True, action=action, connector_id=cid, data=payload)

    return _exec
