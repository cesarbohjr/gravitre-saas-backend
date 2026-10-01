"""Prepare portable package MCP dependencies inside Gravitre governance."""
from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlparse


def declared_mcp_dependencies(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("mcpServers")
    if raw is None:
        raw = manifest.get("mcp_servers")
    if not isinstance(raw, (dict, list)):
        return []

    if isinstance(raw, dict):
        items = list(raw.items())
    else:
        items = [
            (str(row.get("name") or f"server-{index + 1}"), row)
            for index, row in enumerate(raw)
            if isinstance(row, dict)
        ]

    out: list[dict[str, Any]] = []
    for name, spec in items:
        if isinstance(spec, str):
            url = spec.strip()
            transport = "http"
            auth_type = "none"
        elif isinstance(spec, dict):
            url = str(spec.get("url") or spec.get("serverUrl") or "").strip()
            transport = str(spec.get("transport") or ("http" if url else "stdio")).strip().lower()
            transport = transport.replace("-", "_")
            if transport == "streamablehttp":
                transport = "streamable_http"
            auth = spec.get("auth")
            auth_type = (
                str(auth.get("type") or "none").strip().lower()
                if isinstance(auth, dict)
                else str(spec.get("authType") or "none").strip().lower()
            )
        else:
            continue

        parsed = urlparse(url) if url else None
        hostname = (parsed.hostname or "").lower() if parsed else ""
        safe_host = bool(hostname) and hostname not in {"localhost", "localhost.localdomain"} and not hostname.endswith(".local")
        if safe_host:
            try:
                address = ipaddress.ip_address(hostname)
            except ValueError:
                address = None
            if address and (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
            ):
                safe_host = False
        remote_https = bool(
            parsed
            and parsed.scheme == "https"
            and safe_host
            and not parsed.username
            and not parsed.password
        )
        registration_allowed = remote_https and transport in {"http", "sse", "streamable_http"}
        out.append(
            {
                "name": str(name).strip() or "mcp-server",
                "url": url or None,
                "transport": transport,
                "authType": auth_type or "none",
                "registrationAllowed": registration_allowed,
                "blockedReason": (
                    None
                    if registration_allowed
                    else "Only reviewed remote HTTPS MCP dependencies using Gravitre-supported HTTP/SSE/Streamable HTTP transport can be prepared automatically; local/stdio, private-network, or unsupported transports require separate review."
                ),
            }
        )
    return out


def prepare_mcp_dependencies(
    client: Any,
    *,
    org_id: str,
    package_id: str,
    manifest: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for dependency in declared_mcp_dependencies(manifest):
        if not dependency["registrationAllowed"]:
            blocked.append(dependency)
            continue
        row = {
            "org_id": org_id,
            "server_name": dependency["name"],
            "server_url": dependency["url"],
            "transport": dependency["transport"],
            "auth_type": dependency["authType"],
            "auth_config": {},
            "enabled": False,
            "verified_by_gravitre": False,
            "created_by": user_id or None,
            "source_capability_package_id": package_id,
            "activation_state": "pending_review",
        }
        existing = (
            client.table("mcp_servers")
            .select("id,server_name,server_url,enabled,activation_state")
            .eq("org_id", org_id)
            .eq("source_capability_package_id", package_id)
            .eq("server_url", dependency["url"])
            .limit(1)
            .execute()
        )
        if existing.data:
            created.append(existing.data[0])
            continue
        inserted = client.table("mcp_servers").insert(row).execute()
        created.append((inserted.data or [row])[0])
    return {
        "prepared": created,
        "blocked": blocked,
        "enabled": 0,
        "credentialsCopiedFromPackage": False,
        "activationState": "pending_review",
        "executionOwner": "gravitre",
    }


def deactivate_package_mcp_dependencies(
    client: Any,
    *,
    org_id: str,
    package_id: str,
    activation_state: str = "disabled",
) -> dict[str, Any]:
    """Disable all MCP dependencies owned by a portable package and refresh runtime."""
    rows = (
        client.table("mcp_servers")
        .select("id")
        .eq("org_id", org_id)
        .eq("source_capability_package_id", package_id)
        .execute()
        .data
        or []
    )
    server_ids = [str(row.get("id") or "") for row in rows if row.get("id")]
    for server_id in server_ids:
        (
            client.table("mcp_servers")
            .update({"enabled": False, "activation_state": activation_state})
            .eq("org_id", org_id)
            .eq("id", server_id)
            .execute()
        )
        (
            client.table("mcp_tools")
            .update({"enabled": False})
            .eq("org_id", org_id)
            .eq("server_id", server_id)
            .execute()
        )
        try:
            from app.services.mcp_client_service import refresh_package_mcp_runtime_registration

            refresh_package_mcp_runtime_registration(
                client,
                org_id=org_id,
                server_id=server_id,
            )
        except Exception:
            # DB deactivation is authoritative; runtime refresh is best-effort
            # during rolling deploys and will be rebuilt on next process load.
            pass
    return {
        "packageId": package_id,
        "serverIds": server_ids,
        "disabledServers": len(server_ids),
        "executionOwner": "gravitre",
    }
