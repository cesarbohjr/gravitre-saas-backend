"""Phase 2 connector executors — Linear, GitLab, Shopify, PayPal, Brevo, Meta Marketing."""
from __future__ import annotations

import json
from typing import Any, Callable

import httpx

from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolConnectorNotConnectedError,
    ToolContext,
    ToolValidationError,
)

TIMEOUT_SEC = 30.0

PHASE2_BASE_URLS = {
    "gitlab": "https://gitlab.com/api/v4",
    "shopify": "https://{shop}.myshopify.com/admin/api/2024-01",
    "paypal": "https://api-m.paypal.com",
    "brevo": "https://api.brevo.com/v3",
    "meta_marketing": "https://graph.facebook.com/v21.0",
}


def _format_base_url(vendor: str, conn: dict[str, Any]) -> str:
    cfg = conn.get("config") or {}
    base = PHASE2_BASE_URLS[vendor]
    if vendor == "shopify":
        shop = str(cfg.get("shop") or cfg.get("shop_domain") or cfg.get("subdomain") or "")
        if not shop:
            return base
        return base.replace("{shop}", shop)
    if vendor == "gitlab":
        instance = str(cfg.get("instance_url") or cfg.get("gitlab_url") or "").strip().rstrip("/")
        if instance:
            return f"{instance}/api/v4"
    return base.rstrip("/")


def _resolve_connector(ctx: ToolContext, params: dict[str, Any], connector_type: str) -> dict[str, Any]:
    connector_id = params.get("connector_id") or ctx.connector_id
    if connector_id:
        conn = get_connector(
            ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name
        )
    else:
        conn = get_connector_by_type(
            ctx.client, ctx.org_id, connector_type, environment_name=ctx.environment_name
        )
    if not conn:
        raise ToolConnectorNotConnectedError(f"No active {connector_type} connector")
    return conn


def _oauth_token(
    ctx: ToolContext,
    cid: str,
    vendor: str,
) -> str:
    token, err = ensure_generic_session(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        vendor=vendor,
        environment_name=ctx.environment_name,
    )
    if not token:
        raise ToolAuthExpiredError(err or f"{vendor} OAuth not connected")
    return token


def _linear_token(ctx: ToolContext, cid: str) -> str:
    try:
        return _oauth_token(ctx, cid, "linear")
    except ToolAuthExpiredError:
        token = (
            get_decrypted_secret(ctx.client, cid, "api_token", ctx.settings)
            or get_decrypted_secret(ctx.client, cid, "token", ctx.settings)
            or ""
        ).strip()
        if not token:
            raise ToolAuthExpiredError("Linear OAuth or API token not configured")
        return token


def _brevo_api_key(ctx: ToolContext, cid: str) -> str:
    token = (
        get_decrypted_secret(ctx.client, cid, "api_token", ctx.settings)
        or get_decrypted_secret(ctx.client, cid, "api_key", ctx.settings)
        or get_decrypted_secret(ctx.client, cid, "token", ctx.settings)
        or ""
    ).strip()
    if not token:
        raise ToolAuthExpiredError("Brevo API key not configured")
    return token


def _format_base_url(vendor: str, conn: dict[str, Any]) -> str:
    cfg = conn.get("config") or {}
    base = PHASE2_BASE_URLS[vendor]
    if vendor == "shopify":
        shop = str(cfg.get("shop") or cfg.get("shop_domain") or cfg.get("subdomain") or "")
        if not shop:
            return base
        return base.replace("{shop}", shop)
    if vendor == "gitlab":
        instance = str(cfg.get("instance_url") or cfg.get("gitlab_url") or "").strip().rstrip("/")
        if instance:
            return f"{instance}/api/v4"
    return base.rstrip("/")


def _linear_graphql(token: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Authorization": token, "Content-Type": "application/json"}
    body: dict[str, Any] = {"query": query}
    if variables:
        body["variables"] = variables
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post("https://api.linear.app/graphql", headers=headers, json=body)
    if response.status_code >= 400:
        raise ToolValidationError(f"linear GraphQL failed ({response.status_code}): {response.text[:500]}")
    payload = response.json()
    if payload.get("errors"):
        raise ToolValidationError(f"linear GraphQL error: {payload['errors']}")
    data = payload.get("data") or {}
    return data if isinstance(data, dict) else {"result": data}


def _exec_linear(ctx: ToolContext, params: dict[str, Any], action: str) -> dict[str, Any]:
    conn = _resolve_connector(ctx, params, "linear")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "linear", "linear", cid)
    token = _linear_token(ctx, cid)

    if action == "linear.issues.list":
        first = int(params.get("limit") or params.get("first") or 50)
        data = _linear_graphql(
            token,
            "query ($first: Int) { issues(first: $first) { nodes { id identifier title url state { name } } } }",
            {"first": first},
        )
        return data

    if action == "linear.issues.get":
        issue_id = params.get("issue_id") or params.get("id")
        if not issue_id:
            raise ToolValidationError("issue_id is required")
        return _linear_graphql(
            token,
            "query ($id: String!) { issue(id: $id) { id identifier title description url state { name } } }",
            {"id": str(issue_id)},
        )

    if action == "linear.issues.create":
        title = str(params.get("title") or "").strip()
        team_id = params.get("team_id") or params.get("teamId")
        if not title or not team_id:
            raise ToolValidationError("title and team_id are required")
        issue_input: dict[str, Any] = {"title": title, "teamId": str(team_id)}
        if params.get("description"):
            issue_input["description"] = str(params["description"])
        data = _linear_graphql(
            token,
            "mutation ($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id identifier title url } } }",
            {"input": issue_input},
        )
        created = (data.get("issueCreate") or {}).get("issue") or {}
        if created.get("id"):
            data["entity_id"] = created["id"]
            data["outcome_effect"] = "created"
        return data

    if action == "linear.issues.update":
        issue_id = params.get("issue_id") or params.get("id")
        if not issue_id:
            raise ToolValidationError("issue_id is required")
        issue_input: dict[str, Any] = {}
        for key in ("title", "description", "stateId", "state_id", "priority", "assigneeId", "assignee_id"):
            if params.get(key) is not None:
                camel = key.replace("_id", "Id") if "_id" in key else key
                issue_input[camel] = params[key]
        if not issue_input:
            raise ToolValidationError("At least one field to update is required")
        data = _linear_graphql(
            token,
            "mutation ($id: String!, $input: IssueUpdateInput!) { issueUpdate(id: $id, input: $input) { success issue { id identifier title url } } }",
            {"id": str(issue_id), "input": issue_input},
        )
        updated = (data.get("issueUpdate") or {}).get("issue") or {}
        if updated.get("id"):
            data["entity_id"] = updated["id"]
            data["outcome_effect"] = "updated"
        return data

    if action == "linear.issues.search":
        query_text = str(params.get("query") or params.get("q") or "").strip()
        first = int(params.get("limit") or params.get("first") or 20)
        if not query_text:
            raise ToolValidationError("query is required")
        return _linear_graphql(
            token,
            "query ($query: String!, $first: Int) { issueSearch(query: $query, first: $first) { nodes { id identifier title url state { name } } } }",
            {"query": query_text, "first": first},
        )

    raise ToolValidationError(f"Unsupported Linear action: {action}")


def _rest_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, params=params, json=json_body)
    if response.status_code >= 400:
        raise ToolValidationError(f"Request failed ({response.status_code}): {response.text[:500]}")
    if not response.text:
        return {}
    try:
        data = response.json()
    except Exception:
        return {"raw": response.text[:2000]}
    return data if isinstance(data, dict) else {"result": data}


def _exec_gitlab(ctx: ToolContext, params: dict[str, Any], action: str) -> dict[str, Any]:
    conn = _resolve_connector(ctx, params, "gitlab")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "gitlab", "gitlab", cid)
    token = _oauth_token(ctx, cid, "gitlab")
    base = _format_base_url("gitlab", conn)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    if action == "gitlab.projects.list":
        per_page = int(params.get("limit") or params.get("per_page") or 20)
        return _rest_request(
            method="GET",
            url=f"{base}/projects",
            headers=headers,
            params={"per_page": per_page, "membership": params.get("membership", True)},
        )

    project_id = params.get("project_id") or params.get("projectId")
    if action in {
        "gitlab.issues.list",
        "gitlab.issues.create",
        "gitlab.merge_requests.create",
        "gitlab.merge_requests.list",
    }:
        if not project_id:
            raise ToolValidationError("project_id is required")

    if action == "gitlab.issues.list":
        per_page = int(params.get("limit") or params.get("per_page") or 20)
        return _rest_request(
            method="GET",
            url=f"{base}/projects/{project_id}/issues",
            headers=headers,
            params={"per_page": per_page, "state": params.get("state", "opened")},
        )

    if action == "gitlab.issues.create":
        title = str(params.get("title") or "").strip()
        if not title:
            raise ToolValidationError("title is required")
        body: dict[str, Any] = {"title": title}
        if params.get("description"):
            body["description"] = str(params["description"])
        data = _rest_request(
            method="POST",
            url=f"{base}/projects/{project_id}/issues",
            headers={**headers, "Content-Type": "application/json"},
            json_body=body,
        )
        if data.get("id"):
            data["entity_id"] = data["id"]
            data["outcome_effect"] = "created"
        return data

    if action == "gitlab.merge_requests.create":
        title = str(params.get("title") or "").strip()
        source_branch = params.get("source_branch") or params.get("sourceBranch")
        target_branch = params.get("target_branch") or params.get("targetBranch") or "main"
        if not title or not source_branch:
            raise ToolValidationError("title and source_branch are required")
        body = {"title": title, "source_branch": str(source_branch), "target_branch": str(target_branch)}
        if params.get("description"):
            body["description"] = str(params["description"])
        data = _rest_request(
            method="POST",
            url=f"{base}/projects/{project_id}/merge_requests",
            headers={**headers, "Content-Type": "application/json"},
            json_body=body,
        )
        if data.get("id"):
            data["entity_id"] = data["id"]
            data["outcome_effect"] = "created"
        return data

    if action == "gitlab.merge_requests.list":
        per_page = int(params.get("limit") or params.get("per_page") or 20)
        return _rest_request(
            method="GET",
            url=f"{base}/projects/{project_id}/merge_requests",
            headers=headers,
            params={"per_page": per_page, "state": params.get("state", "opened")},
        )

    raise ToolValidationError(f"Unsupported GitLab action: {action}")


def _exec_shopify(ctx: ToolContext, params: dict[str, Any], action: str) -> dict[str, Any]:
    conn = _resolve_connector(ctx, params, "shopify")
    cid = str(conn["id"])
    cfg = conn.get("config") or {}
    shop = str(cfg.get("shop") or cfg.get("shop_domain") or cfg.get("subdomain") or "").strip()
    if not shop:
        raise ToolValidationError("shopify connector requires shop in config")
    enforce_rate_limit(ctx.client, ctx.org_id, "shopify", "shopify", cid)
    token = _oauth_token(ctx, cid, "shopify")
    base = _format_base_url("shopify", conn)
    headers = {"X-Shopify-Access-Token": token, "Accept": "application/json"}

    if action == "shopify.products.list":
        limit = int(params.get("limit") or 50)
        return _rest_request(method="GET", url=f"{base}/products.json", headers=headers, params={"limit": limit})

    if action == "shopify.orders.list":
        limit = int(params.get("limit") or 50)
        status = params.get("status")
        query = {"limit": limit}
        if status:
            query["status"] = status
        return _rest_request(method="GET", url=f"{base}/orders.json", headers=headers, params=query)

    if action == "shopify.customers.list":
        limit = int(params.get("limit") or 50)
        return _rest_request(method="GET", url=f"{base}/customers.json", headers=headers, params={"limit": limit})

    if action == "shopify.products.create":
        title = str(params.get("title") or "").strip()
        if not title:
            raise ToolValidationError("title is required")
        product: dict[str, Any] = {"title": title}
        if params.get("body_html"):
            product["body_html"] = params["body_html"]
        if params.get("vendor"):
            product["vendor"] = params["vendor"]
        if params.get("product_type"):
            product["product_type"] = params["product_type"]
        data = _rest_request(
            method="POST",
            url=f"{base}/products.json",
            headers={**headers, "Content-Type": "application/json"},
            json_body={"product": product},
        )
        created = data.get("product") or {}
        if created.get("id"):
            data["entity_id"] = created["id"]
            data["outcome_effect"] = "created"
        return data

    if action == "shopify.orders.update":
        order_id = params.get("order_id") or params.get("id")
        if not order_id:
            raise ToolValidationError("order_id is required")
        order_body = params.get("order")
        if not isinstance(order_body, dict):
            order_body = {k: v for k, v in params.items() if k not in {"connector_id", "order_id", "id"}}
        if not order_body:
            raise ToolValidationError("order fields to update are required")
        data = _rest_request(
            method="PUT",
            url=f"{base}/orders/{order_id}.json",
            headers={**headers, "Content-Type": "application/json"},
            json_body={"order": order_body},
        )
        updated = data.get("order") or {}
        if updated.get("id"):
            data["entity_id"] = updated["id"]
            data["outcome_effect"] = "updated"
        return data

    raise ToolValidationError(f"Unsupported Shopify action: {action}")


def _exec_paypal(ctx: ToolContext, params: dict[str, Any], action: str) -> dict[str, Any]:
    conn = _resolve_connector(ctx, params, "paypal")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "paypal", "paypal", cid)
    token = _oauth_token(ctx, cid, "paypal")
    base = _format_base_url("paypal", conn)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}

    if action == "paypal.payments.list":
        count = int(params.get("limit") or params.get("count") or 10)
        return _rest_request(
            method="GET",
            url=f"{base}/v1/payments/payment",
            headers=headers,
            params={"count": count, "start_index": params.get("start_index", 0)},
        )

    if action == "paypal.orders.get":
        order_id = params.get("order_id") or params.get("id")
        if not order_id:
            raise ToolValidationError("order_id is required")
        return _rest_request(method="GET", url=f"{base}/v2/checkout/orders/{order_id}", headers=headers)

    if action == "paypal.refunds.create":
        capture_id = params.get("capture_id") or params.get("captureId")
        if not capture_id:
            raise ToolValidationError("capture_id is required")
        body: dict[str, Any] = {}
        if params.get("amount"):
            body["amount"] = params["amount"]
        if params.get("note_to_payer"):
            body["note_to_payer"] = params["note_to_payer"]
        data = _rest_request(
            method="POST",
            url=f"{base}/v2/payments/captures/{capture_id}/refund",
            headers=headers,
            json_body=body or None,
        )
        if data.get("id"):
            data["entity_id"] = data["id"]
            data["outcome_effect"] = "created"
        return data

    if action == "paypal.payouts.create":
        sender_batch_id = params.get("sender_batch_id") or params.get("senderBatchId")
        items = params.get("items")
        if not sender_batch_id or not items:
            raise ToolValidationError("sender_batch_id and items are required")
        if isinstance(items, str):
            items = json.loads(items)
        data = _rest_request(
            method="POST",
            url=f"{base}/v1/payments/payouts",
            headers=headers,
            json_body={
                "sender_batch_header": {"sender_batch_id": str(sender_batch_id)},
                "items": items,
            },
        )
        batch = data.get("batch_header") or {}
        if batch.get("payout_batch_id"):
            data["entity_id"] = batch["payout_batch_id"]
            data["outcome_effect"] = "created"
        return data

    if action == "paypal.disputes.list":
        count = int(params.get("limit") or params.get("count") or 10)
        return _rest_request(
            method="GET",
            url=f"{base}/v1/customer/disputes",
            headers=headers,
            params={"count": count, "start_index": params.get("start_index", 0)},
        )

    raise ToolValidationError(f"Unsupported PayPal action: {action}")


def _exec_brevo(ctx: ToolContext, params: dict[str, Any], action: str) -> dict[str, Any]:
    conn = _resolve_connector(ctx, params, "brevo")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "brevo", "brevo", cid)
    api_key = _brevo_api_key(ctx, cid)
    base = _format_base_url("brevo", conn)
    headers = {"api-key": api_key, "Accept": "application/json", "Content-Type": "application/json"}

    if action == "brevo.contacts.list":
        limit = int(params.get("limit") or 50)
        offset = int(params.get("offset") or 0)
        return _rest_request(method="GET", url=f"{base}/contacts", headers=headers, params={"limit": limit, "offset": offset})

    if action == "brevo.campaigns.list":
        limit = int(params.get("limit") or 50)
        offset = int(params.get("offset") or 0)
        return _rest_request(
            method="GET",
            url=f"{base}/emailCampaigns",
            headers=headers,
            params={"limit": limit, "offset": offset},
        )

    if action == "brevo.email.send":
        sender = params.get("sender")
        to = params.get("to")
        subject = params.get("subject")
        if not sender or not to or not subject:
            raise ToolValidationError("sender, to, and subject are required")
        body: dict[str, Any] = {
            "sender": sender if isinstance(sender, dict) else {"email": str(sender)},
            "to": to if isinstance(to, list) else [{"email": str(to)}],
            "subject": str(subject),
        }
        if params.get("htmlContent"):
            body["htmlContent"] = params["htmlContent"]
        elif params.get("html_content"):
            body["htmlContent"] = params["html_content"]
        elif params.get("textContent"):
            body["textContent"] = params["textContent"]
        elif params.get("text_content"):
            body["textContent"] = params["text_content"]
        else:
            raise ToolValidationError("htmlContent or textContent is required")
        data = _rest_request(method="POST", url=f"{base}/smtp/email", headers=headers, json_body=body)
        if data.get("messageId"):
            data["entity_id"] = data["messageId"]
            data["outcome_effect"] = "created"
        return data

    if action == "brevo.contacts.create":
        email = str(params.get("email") or "").strip()
        if not email:
            raise ToolValidationError("email is required")
        body = {"email": email}
        if params.get("attributes"):
            body["attributes"] = params["attributes"]
        if params.get("listIds"):
            body["listIds"] = params["listIds"]
        elif params.get("list_ids"):
            body["listIds"] = params["list_ids"]
        data = _rest_request(method="POST", url=f"{base}/contacts", headers=headers, json_body=body)
        if data.get("id"):
            data["entity_id"] = data["id"]
            data["outcome_effect"] = "created"
        return data

    if action == "brevo.contacts.update":
        identifier = params.get("contact_id") or params.get("id") or params.get("email")
        if not identifier:
            raise ToolValidationError("contact_id or email is required")
        body = {k: v for k, v in params.items() if k not in {"connector_id", "contact_id", "id", "email"}}
        if params.get("attributes"):
            body["attributes"] = params["attributes"]
        if not body:
            raise ToolValidationError("At least one field to update is required")
        data = _rest_request(
            method="PUT",
            url=f"{base}/contacts/{identifier}",
            headers=headers,
            json_body=body,
        )
        if data.get("id"):
            data["entity_id"] = data["id"]
            data["outcome_effect"] = "updated"
        return data

    raise ToolValidationError(f"Unsupported Brevo action: {action}")


def _meta_ad_account(conn: dict[str, Any], params: dict[str, Any]) -> str:
    raw = (
        params.get("ad_account_id")
        or params.get("adAccountId")
        or (conn.get("config") or {}).get("ad_account_id")
        or (conn.get("config") or {}).get("adAccountId")
        or ""
    )
    account = str(raw).strip()
    if not account:
        raise ToolValidationError("ad_account_id is required (connector config or params)")
    if not account.startswith("act_"):
        account = f"act_{account}"
    return account


def _exec_meta_marketing(ctx: ToolContext, params: dict[str, Any], action: str) -> dict[str, Any]:
    conn = _resolve_connector(ctx, params, "meta_marketing")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "meta_marketing", "meta_marketing", cid)
    token = _oauth_token(ctx, cid, "meta_marketing")
    base = _format_base_url("meta_marketing", conn)
    headers = {"Authorization": f"Bearer {token}"}
    ad_account = _meta_ad_account(conn, params)

    if action == "meta_marketing.campaigns.list":
        return _rest_request(
            method="GET",
            url=f"{base}/{ad_account}/campaigns",
            headers=headers,
            params={"fields": params.get("fields", "id,name,status,objective"), "limit": params.get("limit", 50)},
        )

    if action == "meta_marketing.adsets.list":
        return _rest_request(
            method="GET",
            url=f"{base}/{ad_account}/adsets",
            headers=headers,
            params={"fields": params.get("fields", "id,name,status,campaign_id"), "limit": params.get("limit", 50)},
        )

    if action == "meta_marketing.campaigns.create":
        name = str(params.get("name") or "").strip()
        objective = str(params.get("objective") or "OUTCOME_AWARENESS").strip()
        if not name:
            raise ToolValidationError("name is required")
        body: dict[str, Any] = {
            "name": name,
            "objective": objective,
            "status": params.get("status", "PAUSED"),
            "special_ad_categories": params.get("special_ad_categories") or [],
        }
        if params.get("daily_budget"):
            body["daily_budget"] = params["daily_budget"]
        data = _rest_request(
            method="POST",
            url=f"{base}/{ad_account}/campaigns",
            headers={**headers, "Content-Type": "application/json"},
            json_body=body,
        )
        if data.get("id"):
            data["entity_id"] = data["id"]
            data["outcome_effect"] = "created"
        return data

    if action == "meta_marketing.campaigns.update":
        campaign_id = params.get("campaign_id") or params.get("id")
        if not campaign_id:
            raise ToolValidationError("campaign_id is required")
        body = {k: v for k, v in params.items() if k not in {"connector_id", "campaign_id", "id", "ad_account_id", "adAccountId"}}
        if not body:
            raise ToolValidationError("At least one field to update is required")
        data = _rest_request(
            method="POST",
            url=f"{base}/{campaign_id}",
            headers={**headers, "Content-Type": "application/json"},
            json_body=body,
        )
        if data.get("success") or data.get("id"):
            data["entity_id"] = str(campaign_id)
            data["outcome_effect"] = "updated"
        return data

    if action == "meta_marketing.adsets.update":
        adset_id = params.get("adset_id") or params.get("id")
        if not adset_id:
            raise ToolValidationError("adset_id is required")
        body = {k: v for k, v in params.items() if k not in {"connector_id", "adset_id", "id", "ad_account_id", "adAccountId"}}
        if not body:
            raise ToolValidationError("At least one field to update is required")
        data = _rest_request(
            method="POST",
            url=f"{base}/{adset_id}",
            headers={**headers, "Content-Type": "application/json"},
            json_body=body,
        )
        if data.get("success") or data.get("id"):
            data["entity_id"] = str(adset_id)
            data["outcome_effect"] = "updated"
        return data

    raise ToolValidationError(f"Unsupported Meta Marketing action: {action}")


_EXECUTORS: dict[str, Callable[[ToolContext, dict[str, Any], str], dict[str, Any]]] = {
    "linear": _exec_linear,
    "gitlab": _exec_gitlab,
    "shopify": _exec_shopify,
    "paypal": _exec_paypal,
    "brevo": _exec_brevo,
    "meta_marketing": _exec_meta_marketing,
}


def make_phase2_executor(action: str):
    from app.connectors.phase2_connector_routes import PHASE2_ROUTES

    if action not in PHASE2_ROUTES:
        raise ValueError(f"Unsupported Phase 2 action: {action}")
    vendor = action.split(".", 1)[0]
    handler = _EXECUTORS.get(vendor)
    if not handler:
        raise ValueError(f"No Phase 2 handler for vendor: {vendor}")

    def _exec(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
        conn = _resolve_connector(ctx, params, vendor)
        cid = str(conn["id"])
        payload = handler(ctx, params, action)
        return NormalizedResult(success=True, action=action, connector_id=cid, data=payload)

    return _exec
