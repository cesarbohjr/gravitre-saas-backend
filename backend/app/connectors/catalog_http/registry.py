"""Build catalog HTTP executors for all catalog-declared tools."""
from __future__ import annotations

from app.connectors.action_catalog.registry import all_catalog_action_specs, get_vendor_catalog
from app.connectors.action_catalog.tool_aliases import registry_keys_for_catalog_tool
from app.connectors.catalog_http.executor import make_catalog_http_executor
from app.connectors.twilio_tools import TWILIO_ROUTES, make_twilio_executor


def _catalog_tool_keys() -> set[str]:
    """Canonical catalog action ids only (no short-prefix aliases).

    Aliases like ``drive.search_files`` for ``google_drive.search_files`` must
    not become standalone catalog-HTTP stubs — that shadows dedicated executors
    and breaks resolve/tool sequencing.
    """
    keys: set[str] = set()
    for vendor_spec in get_vendor_catalog().values():
        for action in vendor_spec.all_actions():
            tool_key = action.id
            if "." not in tool_key or tool_key.split(".", 1)[0] != vendor_spec.vendor:
                tool_key = f"{vendor_spec.vendor}.{action.id}"
            keys.add(tool_key)
    _ = all_catalog_action_specs  # keep import stable for tooling
    return keys


def build_catalog_http_executors(*, skip: set[str] | None = None) -> dict[str, object]:
    skip = skip or set()
    executors: dict[str, object] = {}
    for tool in sorted(_catalog_tool_keys()):
        # Skip when this catalog key *or any registry alias* already has a
        # dedicated executor (e.g. googleads.* implements google_ads.*).
        if registry_keys_for_catalog_tool(tool) & skip:
            continue
        vendor = tool.split(".", 1)[0]
        if vendor in {"email", "webhook"}:
            continue
        if tool not in executors:
            # Twilio uses Account SID paths + Basic auth + form bodies — not generic JSON HTTP.
            if vendor == "twilio" and tool in TWILIO_ROUTES:
                executors[tool] = make_twilio_executor(tool)
            elif vendor == "twilio":
                # Remaining advanced Studio/Verify actions stay on generic stub until wired.
                executors[tool] = make_catalog_http_executor(tool)
            else:
                executors[tool] = make_catalog_http_executor(tool)
    return executors
