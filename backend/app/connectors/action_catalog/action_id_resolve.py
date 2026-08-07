"""Resolve tool registry names → catalog action ids (multi-segment vendors).

``absorb_lms_courses_create`` → ``absorb_lms.courses.create``
(not ``absorb.lms.courses.create``).
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def catalog_vendor_ids() -> tuple[str, ...]:
    from app.connectors.action_catalog.registry import get_vendor_catalog

    return tuple(sorted(get_vendor_catalog().keys(), key=len, reverse=True))


def resolve_action_id_from_tool_name(name: str | None) -> str:
    raw = str(name or "").strip().lower()
    if not raw:
        return ""
    # Already a plausible dotted id with a known vendor prefix.
    if "." in raw:
        for vendor in catalog_vendor_ids():
            if raw == vendor or raw.startswith(vendor + "."):
                return raw
    underscored = raw.replace(".", "_")
    for vendor in catalog_vendor_ids():
        prefix = vendor + "_"
        if underscored.startswith(prefix):
            rest = underscored[len(prefix) :]
            if not rest:
                return vendor
            return vendor + "." + rest.replace("_", ".")
    if "_" in underscored:
        head, tail = underscored.split("_", 1)
        return head + "." + tail.replace("_", ".")
    return underscored


def resolve_integration_from_tool_name(name: str | None) -> str:
    action_id = resolve_action_id_from_tool_name(name)
    if not action_id:
        return ""
    if action_id.startswith("assistant_") or action_id.startswith("assistant."):
        return "platform"
    return action_id.split(".", 1)[0]


def clear_action_id_resolve_cache() -> None:
    catalog_vendor_ids.cache_clear()
