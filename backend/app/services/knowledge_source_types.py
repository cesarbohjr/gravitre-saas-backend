"""Canonical agent knowledge source types and validation."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

KNOWLEDGE_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        "google_drive_folder",
        "google_drive_file",
        "sharepoint_site",
        "sharepoint_drive",
        "sharepoint_folder",
        "slack_channel",
        "teams_channel",
        "hubspot_object",
        "salesforce_object",
        "zendesk_view",
        "intercom_collection",
        "confluence_space",
        "notion_page",
        "canva_folder",
        "figma_project",
        "ga4_property",
        "knowledge_pack",
        "manual_rule",
        # Legacy aliases
        "folder",
        "dataset",
    }
)

SYNC_FREQUENCIES: frozenset[str] = frozenset({"manual", "hourly", "daily", "weekly"})

LEGACY_TYPE_ALIASES: dict[str, str] = {
    "folder": "google_drive_folder",
    "dataset": "manual_rule",
}


def normalize_source_type(source_type: str) -> str:
    raw = (source_type or "").strip().lower()
    return LEGACY_TYPE_ALIASES.get(raw, raw)


def validate_source_type(source_type: str) -> str:
    normalized = normalize_source_type(source_type)
    if normalized not in KNOWLEDGE_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported source_type: {source_type}",
        )
    return normalized


def validate_sync_frequency(value: str | None) -> str:
    raw = (value or "daily").strip().lower()
    if raw not in SYNC_FREQUENCIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported sync_frequency: {value}",
        )
    return raw


def connector_vendor_for_source_type(source_type: str) -> str | None:
    mapping = {
        "google_drive_folder": "google_drive",
        "google_drive_file": "google_drive",
        "sharepoint_site": "microsoft365",
        "sharepoint_drive": "microsoft365",
        "sharepoint_folder": "microsoft365",
        "slack_channel": "slack",
        "teams_channel": "microsoft365",
        "hubspot_object": "hubspot",
        "salesforce_object": "salesforce",
        "zendesk_view": "zendesk",
        "intercom_collection": "intercom",
        "confluence_space": "confluence",
        "notion_page": "notion",
        "canva_folder": "canva",
        "figma_project": "figma",
        "ga4_property": "google_analytics",
    }
    return mapping.get(normalize_source_type(source_type))


def build_sync_rules(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize include/exclude/sync rule fields from API payload."""
    metadata = dict(payload.get("metadata") or {})
    include_rules = list(payload.get("include_rules") or payload.get("includeRules") or [])
    exclude_rules = list(payload.get("exclude_rules") or payload.get("excludeRules") or [])
    return {
        "include_rules": include_rules,
        "exclude_rules": exclude_rules,
        "tags_required": list(payload.get("tags_required") or payload.get("tagsRequired") or metadata.get("tags_required") or []),
        "tags_excluded": list(payload.get("tags_excluded") or payload.get("tagsExcluded") or metadata.get("tags_excluded") or []),
        "sync_frequency": payload.get("sync_frequency") or payload.get("syncFrequency") or payload.get("sync_schedule") or "daily",
        "freshness_policy": dict(payload.get("freshness_policy") or payload.get("freshnessPolicy") or metadata.get("freshness_policy") or {}),
        "permission_policy": dict(payload.get("permission_policy") or payload.get("permissionPolicy") or metadata.get("permission_policy") or {}),
    }
