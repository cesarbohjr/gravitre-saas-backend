"""Activation planning for imported portable capability packages.

Plans describe how package dependencies map to existing Gravitre systems.
They do not execute tools, create OAuth grants, or enable MCP servers.
"""
from __future__ import annotations

from typing import Any


def _mcp_servers(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("mcpServers")
    if raw is None:
        raw = manifest.get("mcp_servers")
    out: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = [
            (str(row.get("name") or f"server-{index + 1}"), row)
            for index, row in enumerate(raw)
            if isinstance(row, dict)
        ]
    else:
        items = []
    for name, spec in items:
        if isinstance(spec, str):
            url, transport = spec, "http"
        elif isinstance(spec, dict):
            url = str(spec.get("url") or spec.get("serverUrl") or "").strip()
            transport = str(spec.get("transport") or ("http" if url else "stdio")).strip()
        else:
            continue
        out.append(
            {
                "name": str(name),
                "url": url or None,
                "transport": transport,
                "activation": "admin_review_required",
                "discovery": "existing /api/admin/mcp/servers/{id}/discover",
            }
        )
    return out


def build_activation_plan(manifest: dict[str, Any], inspection: dict[str, Any]) -> dict[str, Any]:
    components = inspection.get("components") if isinstance(inspection.get("components"), list) else []
    connectors = [
        row.get("name") for row in components
        if isinstance(row, dict) and row.get("kind") == "connector" and row.get("name")
    ]
    component_plan: list[dict[str, Any]] = []
    for row in components:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "")
        name = str(row.get("name") or "")
        if kind == "skill":
            activation = "lazy_context"
            supported = True
        elif kind == "mcp":
            activation = "admin_prepare_discover_enable"
            supported = True
        elif kind == "connector":
            activation = "existing_connector_oauth_or_credentials"
            supported = True
        elif kind == "agent":
            activation = "admin_bind_to_existing_agent"
            supported = False
        elif kind == "play":
            activation = "admin_bind_to_existing_play_or_workflow"
            supported = False
        elif kind == "template":
            activation = "admin_bind_to_existing_marketplace_asset"
            supported = False
        elif kind == "trigger":
            activation = "admin_bind_to_existing_workflow_schedule"
            supported = False
        elif kind == "ui_extension":
            activation = "declaration_only_native_adapter_required"
            supported = False
        elif kind in {"command", "hook"}:
            activation = "inert_script_metadata_only"
            supported = False
        else:
            activation = "declaration_only"
            supported = False
        component_plan.append(
            {
                "kind": kind,
                "name": name,
                "supportedActivation": supported,
                "activation": activation,
                "executable": bool(row.get("executable")),
            }
        )

    return {
        "executionOwner": "gravitre",
        "directImportedCodeExecution": False,
        "packageRisk": inspection.get("risk"),
        "requiresSecurityReview": inspection.get("risk") in {"high", "blocked"},
        "components": component_plan,
        "mcpServers": _mcp_servers(manifest),
        "connectors": [
            {
                "vendor": str(name),
                "activation": "existing_connector_oauth_or_credentials",
                "runtime": "canonical connector tool service",
            }
            for name in connectors
        ],
        "writePolicy": {
            "approval": "existing Gravitre write governance",
            "terminalSuccess": "source-of-record verification only",
            "providerAcceptanceIsSuccess": False,
        },
        "skillLoading": "lazy relevance selection",
        "unsupportedDeclarationsRemainInert": True,
    }
