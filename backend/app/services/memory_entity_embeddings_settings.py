"""STA-316 — org opt-in for Memory entity embeddings (Option B). Default OFF."""
from __future__ import annotations

from typing import Any

DEFAULT_MEMORY_ENTITY_EMBEDDINGS: dict[str, Any] = {
    "enabled": False,
    "connectors": [],  # empty = all connectors when enabled; else allowlist
}


def normalize_memory_entity_embeddings(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return dict(DEFAULT_MEMORY_ENTITY_EMBEDDINGS)
    enabled = bool(raw.get("enabled") is True)
    connectors = [
        str(item).strip().lower()
        for item in (raw.get("connectors") or [])
        if str(item).strip()
    ]
    return {"enabled": enabled, "connectors": connectors}


def load_memory_entity_embeddings_settings(client: Any, org_id: str) -> dict[str, Any]:
    row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = (row.data or [{}])[0].get("settings") if row.data else {}
    if not isinstance(settings, dict):
        settings = {}
    raw = settings.get("memoryEntityEmbeddings") or settings.get("memory_entity_embeddings")
    return normalize_memory_entity_embeddings(raw if isinstance(raw, dict) else None)


def save_memory_entity_embeddings_settings(
    client: Any,
    org_id: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    normalized = normalize_memory_entity_embeddings(policy)
    row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = (row.data or [{}])[0].get("settings") if row.data else {}
    if not isinstance(settings, dict):
        settings = {}
    settings = {**settings, "memoryEntityEmbeddings": normalized}
    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()
    return normalized


def memory_embeddings_enabled_for(
    policy: dict[str, Any],
    *,
    integration: str | None = None,
) -> bool:
    normalized = normalize_memory_entity_embeddings(policy)
    if not normalized["enabled"]:
        return False
    allow = normalized["connectors"]
    if not allow:
        return True
    vendor = (integration or "").strip().lower()
    return bool(vendor) and vendor in allow
