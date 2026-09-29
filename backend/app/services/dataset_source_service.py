"""Provider-neutral external dataset source references.

This module stores references/index/sample/materialization metadata only.
Provider credentials, downloads, and provider-specific behavior are explicitly
outside this layer.
"""
from __future__ import annotations

from typing import Any

ALLOWED_ACCESS_MODES = frozenset({"reference", "index", "sample", "materialized"})
_FORBIDDEN_SECRET_MARKERS = (
    "access_token=",
    "refresh_token=",
    "client_secret=",
    "api_key=",
    "apikey=",
    "token=",
)


def normalize_provider(value: str) -> str:
    provider = str(value or "").strip().lower()
    if not provider:
        raise ValueError("provider is required")
    return provider


def validate_source_payload(
    *,
    provider: str,
    external_id: str,
    access_mode: str,
    source_uri: str | None = None,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    normalized_provider = normalize_provider(provider)
    normalized_external_id = str(external_id or "").strip()
    normalized_mode = str(access_mode or "").strip().lower()
    if not normalized_external_id:
        raise ValueError("external_id is required")
    if normalized_mode not in ALLOWED_ACCESS_MODES:
        raise ValueError("unsupported dataset source access_mode")
    if sample_limit is not None and sample_limit <= 0:
        raise ValueError("sample_limit must be greater than zero")
    if normalized_mode == "sample" and sample_limit is None:
        raise ValueError("sample access requires sample_limit")
    normalized_uri = str(source_uri).strip() if source_uri else None
    if normalized_uri:
        lowered = normalized_uri.lower()
        if any(marker in lowered for marker in _FORBIDDEN_SECRET_MARKERS):
            raise ValueError("source_uri must not contain provider credentials or tokens")
    return {
        "provider": normalized_provider,
        "external_id": normalized_external_id,
        "access_mode": normalized_mode,
        "source_uri": normalized_uri,
        "sample_limit": sample_limit,
    }


def list_dataset_sources(client: Any, org_id: str, dataset_id: str) -> list[dict[str, Any]]:
    rows = (
        client.table("training_dataset_sources")
        .select(
            "id, dataset_id, provider, external_id, display_name, source_uri, "
            "connection_ref, access_mode, materialization_status, sample_limit, "
            "metadata, created_at, updated_at"
        )
        .eq("org_id", org_id)
        .eq("dataset_id", dataset_id)
        .order("created_at", desc=False)
        .execute()
        .data
        or []
    )
    return [dict(row) for row in rows]


def create_dataset_source(
    client: Any,
    *,
    org_id: str,
    dataset_id: str,
    provider: str,
    external_id: str,
    access_mode: str,
    display_name: str | None = None,
    source_uri: str | None = None,
    connection_ref: str | None = None,
    sample_limit: int | None = None,
    metadata: dict[str, Any] | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    validated = validate_source_payload(
        provider=provider,
        external_id=external_id,
        access_mode=access_mode,
        source_uri=source_uri,
        sample_limit=sample_limit,
    )
    row = {
        "org_id": org_id,
        "dataset_id": dataset_id,
        **validated,
        "display_name": str(display_name).strip() if display_name else None,
        "connection_ref": str(connection_ref).strip() if connection_ref else None,
        "materialization_status": (
            "materialized" if validated["access_mode"] == "materialized" else "not_requested"
        ),
        "metadata": dict(metadata or {}),
        "created_by": created_by,
    }
    response = (
        client.table("training_dataset_sources")
        .upsert(row, on_conflict="org_id,dataset_id,provider,external_id")
        .execute()
    )
    return dict((response.data or [row])[0])
