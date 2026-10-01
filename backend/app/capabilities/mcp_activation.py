"""Prepare portable package MCP dependencies inside Gravitre governance."""
from __future__ import annotations

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
            auth = spec.get("auth")
            auth_type = (
                str(auth.get("type") or "none").strip().lower()
                if isinstance(auth, dict)
                else str(spec.get("authType") or "none").strip().lower()
            )
        else:
            continue

        parsed = urlparse(url) if url else None
        remote_https = bool(parsed and parsed.scheme == "https" and parsed.hostname)
        out.append(
            {
                "name": str(name).strip() or "mcp-server",
                "url": url or None,
                "transport": transport,
                "authType": auth_type or "none",
                "registrationAllowed": remote_https and transport in {"http", "https", "sse", "streamable_http"},
                "blockedReason": (
                    None
                    if remote_https and transport in {"http", "https", "sse", "streamable_http"}
                    else "Only remote HTTPS MCP dependencies can be prepared automatically; local/stdio execution requires separate review."
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
        "executionOwner": "gravitre",
    }
