"""Progressive schema loading (Anthropic defer_loading family) for unified turn.

Candidate generation stays on keyword/embedding narrow (≤ max_tools). This module
attaches only name + one-line description stubs plus ``search_catalog_tools``,
and loads full ``input_schema`` on demand.

Write authority (catalog_write_authority) MUST still run after a real tool is
selected with a full schema — progressive disclosure is never a bypass.
"""
from __future__ import annotations

import json
from typing import Any

from app.services.narrowed_tools import NarrowedTools, mark_narrowed

SEARCH_CATALOG_TOOLS_NAME = "search_catalog_tools"


def _fn(tool: dict[str, Any]) -> dict[str, Any]:
    fn = tool.get("function")
    return fn if isinstance(fn, dict) else {}


def tool_name(tool: dict[str, Any]) -> str:
    return str(_fn(tool).get("name") or tool.get("name") or "").strip()


def to_stub(tool: dict[str, Any]) -> dict[str, Any]:
    """Name + one-line description; empty parameters (defer full schema)."""
    fn = _fn(tool)
    name = str(fn.get("name") or "").strip()
    desc = str(fn.get("description") or name or "Catalog tool").strip()
    # Ultra-short stub — system prompt explains search_catalog_tools deferral.
    one_line = desc.splitlines()[0].strip()[:72]
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": one_line,
            "parameters": {"type": "object", "properties": {}},
        },
        "gravitre_deferred": True,
    }


def search_catalog_tools_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": SEARCH_CATALOG_TOOLS_NAME,
            "description": "Load full input_schema for candidate tool name(s) before invoking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_names": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "query": {"type": "string"},
                },
            },
        },
        "gravitre_meta_tool": True,
    }


def select_progressive_preload_names(
    narrowed: list[dict[str, Any]],
    *,
    max_preload: int = 2,
) -> list[str]:
    """Pick top connector candidates to attach with full schemas up front.

    Avoids a second model round via ``search_catalog_tools`` when embedding/keyword
    narrowing already ranked the likely tool(s). Skips platform/meta helpers.
    """
    if max_preload <= 0:
        return []
    names: list[str] = []
    for tool in narrowed:
        if not isinstance(tool, dict):
            continue
        name = tool_name(tool)
        if not name or name == SEARCH_CATALOG_TOOLS_NAME:
            continue
        lower = name.lower()
        if lower.startswith(("platform_", "gravitre_", "catalog_", "assistant_")):
            continue
        if name in names:
            continue
        names.append(name)
        if len(names) >= max_preload:
            break
    return names


def apply_progressive_disclosure(
    narrowed: list[dict[str, Any]],
    *,
    loaded_names: set[str] | None = None,
) -> tuple[NarrowedTools, dict[str, dict[str, Any]], set[str]]:
    """Build attach payload: stubs (or full if loaded) + search tool.

    Returns (attach_list, full_by_name, loaded_names).
    """
    loaded = {str(n).strip() for n in (loaded_names or set()) if str(n).strip()}
    full_by_name: dict[str, dict[str, Any]] = {}
    attach: list[dict[str, Any]] = []
    for tool in narrowed:
        if not isinstance(tool, dict):
            continue
        name = tool_name(tool)
        if not name or name == SEARCH_CATALOG_TOOLS_NAME:
            continue
        # Strip progressive markers from stored full copy.
        full = json.loads(json.dumps(tool))
        full.pop("gravitre_deferred", None)
        full.pop("gravitre_meta_tool", None)
        full_by_name[name] = full
        if name in loaded:
            attach.append(full)
        else:
            attach.append(to_stub(tool))
    attach.append(search_catalog_tools_definition())
    stats = {}
    if isinstance(narrowed, NarrowedTools):
        stats = dict(narrowed.stats or {})
    stats.update(
        {
            "progressiveDisclosure": True,
            "deferredStubCount": sum(1 for t in attach if t.get("gravitre_deferred")),
            "loadedFullSchemaCount": len(loaded),
            "searchCatalogToolsAttached": True,
        }
    )
    return mark_narrowed(attach, stats=stats, source="progressive_tool_schemas"), full_by_name, loaded


def execute_search_catalog_tools(
    args: dict[str, Any] | None,
    *,
    full_by_name: dict[str, dict[str, Any]],
    loaded_names: set[str],
    max_load: int = 5,
) -> tuple[set[str], dict[str, Any]]:
    """Resolve search_catalog_tools call → update loaded set + result payload."""
    payload = args if isinstance(args, dict) else {}
    names: list[str] = []
    raw = payload.get("tool_names") or payload.get("names") or payload.get("tools")
    if isinstance(raw, str) and raw.strip():
        names = [raw.strip()]
    elif isinstance(raw, list):
        names = [str(x).strip() for x in raw if str(x).strip()]
    query = str(payload.get("query") or "").strip().lower()
    if not names and query:
        for name, tool in full_by_name.items():
            blob = f"{name} {json.dumps(tool).lower()}"
            if query in blob:
                names.append(name)
            if len(names) >= max_load:
                break
    if not names:
        # Default: load top max_load by name order (deterministic).
        names = sorted(full_by_name.keys())[:max_load]

    loaded = set(loaded_names)
    schemas: list[dict[str, Any]] = []
    for name in names[:max_load]:
        tool = full_by_name.get(name)
        if not tool:
            continue
        loaded.add(name)
        schemas.append(tool)
    result = {
        "loaded": sorted(loaded),
        "schemas": schemas,
        "count": len(schemas),
        "note": (
            "Full schemas loaded. You may now invoke these tools with real "
            "arguments. Writes still require normal approval gates."
        ),
    }
    return loaded, result


def gate_deferred_tool_call(
    tool_name: str,
    *,
    loaded_names: set[str],
    full_by_name: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    """Return (allowed, reason). Meta search tool always allowed."""
    name = str(tool_name or "").strip()
    if not name:
        return False, "empty_tool_name"
    if name == SEARCH_CATALOG_TOOLS_NAME:
        return True, "meta_search"
    if name not in full_by_name:
        return False, "tool_not_in_candidate_set"
    if name not in loaded_names:
        return False, "full_schema_not_loaded"
    return True, "loaded"


def is_search_catalog_tools(name: str | None) -> bool:
    return str(name or "").strip() == SEARCH_CATALOG_TOOLS_NAME


def payload_bytes(tools: list[dict[str, Any]]) -> int:
    return len(json.dumps(tools, separators=(",", ":")).encode("utf-8"))
