"""Detect connector API gaps and recommend MCP / browser-agent fallbacks."""
from __future__ import annotations

from typing import Any

from app.services.connector_execution_matrix import get_matrix_entry


def native_action_available(vendor: str, action_key: str) -> bool:
    entry = get_matrix_entry(vendor.lower().strip(), action_key.lower().strip())
    if entry is None:
        return False
    return entry.implementation_status != "not_implemented"


def resolve_api_gap_fallback(vendor: str | None, action_key: str | None) -> dict[str, Any]:
    """Return fallback guidance when a vendor action is missing from the native catalog."""
    vendor_key = str(vendor or "").strip().lower()
    action = str(action_key or "").strip().lower()
    if not vendor_key or not action:
        return {
            "missing": False,
            "vendor": vendor_key,
            "action_key": action,
            "recommended_tools": [],
            "guidance": "",
        }
    full_key = action if "." in action else f"{vendor_key}.{action}"
    missing = not native_action_available(vendor_key, full_key)
    recommended: list[str] = []
    guidance_parts: list[str] = []
    if missing:
        recommended.append("browser_agent_read")
        guidance_parts.append(
            f"Native action `{full_key}` is not implemented — use `browser_agent_read` for authenticated web UI reads "
            "or org MCP tools (`mcp_*`) when registered under Admin → MCP."
        )
    else:
        guidance_parts.append(f"Prefer native connector tool `{full_key}` before browser or MCP fallbacks.")
    return {
        "missing": missing,
        "vendor": vendor_key,
        "action_key": full_key,
        "recommended_tools": recommended,
        "guidance": " ".join(guidance_parts),
    }


def gap_recovery_prompt_section(*, connected_integrations: list[str], has_mcp_tools: bool) -> str:
    """System-prompt section for Claude-like gap recovery."""
    real = [c for c in connected_integrations if str(c).lower() not in {"platform", "webhook", "email"}]
    if not real and not has_mcp_tools:
        return ""
    connected_lower = {str(c).lower() for c in real}
    lines = [
        "## API gap recovery",
        (
            "When a connector has no native tool for the user's request, recover in order: "
            "(1) closest native read/write action, (2) org MCP tools whose names start with `mcp_`, "
            "(3) `browser_agent_read` only if no native action exists — and only after explaining the gap."
        ),
        (
            "Use `browser_agent_interact` only for UI actions with no API — it requires human approval. "
            "Never guess credentials; ask the user for a session URL or complete OAuth at /connectors first."
        ),
        (
            "Never ask for an authenticated app URL when a native connector tool can fulfill the request. "
            "Prefer a short clarifying question or an approval to run a native write over browser automation."
        ),
    ]
    if "apollo" in connected_lower:
        lines.append(
            "Apollo is connected: use `apollo_lists_create` / `apollo_people_search` / "
            "`apollo_organizations_search` for lists and prospecting. "
            "Treat user 'segment' requests as contact list/label creation. "
            "Do not ask for an Apollo Lists page URL unless those tools are unavailable."
        )
    if has_mcp_tools:
        lines.append("This org has MCP tools registered — prefer `mcp_*` tools for gaps before browser automation.")
    return "\n".join(lines)
