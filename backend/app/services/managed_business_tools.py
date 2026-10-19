"""Bounded read executors for business providers. No caller-selected URL/method."""
from __future__ import annotations

from typing import Any

import httpx

from app.connectors.nango_client import proxy_request
from app.connectors.nango_registry import BUSINESS_CONNECTORS
from app.services.managed_service_desk_tools import _managed_connector
from app.services.tool_types import NormalizedResult, ToolAuthExpiredError, ToolValidationError, ToolError


def _executor(spec: dict[str, Any]):
    def execute(ctx: Any, params: dict[str, Any]) -> NormalizedResult:
        allowed = {"connector_id"}
        if spec["vendor"] == "harvest":
            allowed.add("harvest_account_id")
        if spec["vendor"] == "freshsales":
            allowed.add("contact_id")
        unexpected = set(params) - allowed
        if unexpected:
            raise ToolValidationError("Unsupported read parameters")
        headers = {key: value for key, value in spec["headers"].items()}
        path = spec["proxy_path"]
        if spec["vendor"] == "freshsales":
            contact_id = str(params.get("contact_id") or "")
            if not contact_id.isascii() or not contact_id.isdigit() or int(contact_id) < 1:
                raise ToolValidationError("Freshsales requires a positive numeric contact_id")
            path = path.replace("{contact_id}", contact_id)
        if spec["vendor"] == "harvest":
            account_id = str(params.get("harvest_account_id") or "")
            if not account_id.isascii() or not account_id.isdigit():
                raise ToolValidationError("Harvest requires a numeric harvest_account_id")
            headers["Harvest-Account-Id"] = account_id
        cid, connection_id, integration_id = _managed_connector(ctx, spec["vendor"], params)
        try:
            response = proxy_request(ctx.settings, method="GET", endpoint=path,
                                     connection_id=connection_id, integration_id=integration_id,
                                     extra_headers=headers or None, params=spec.get("query"))
            if response.status_code in {401, 403, 424}:
                raise ToolAuthExpiredError("Provider rejected authorization; reconnect or check account permissions")
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise ToolValidationError(f"Provider read failed ({exc.response.status_code})") from exc
        except (httpx.TransportError, ValueError) as exc:
            raise ToolError("Provider read could not be completed", code="connector_read_failed") from exc
        return NormalizedResult(success=True, action=f"{spec['vendor']}.{spec['read_action']}",
                                connector_id=cid, data={"result": data})
    return execute


MANAGED_BUSINESS_TOOL_EXECUTORS = {
    f"{spec['vendor']}.{spec['read_action']}": _executor(spec) for spec in BUSINESS_CONNECTORS
}
