"""Provider-neutral dataset-source contracts.

An external source augments an existing training_datasets row. This module does
not fetch a provider, store credentials, or create a second dataset product.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DatasetSourceAccessMode(StrEnum):
    REFERENCE = "reference"
    SAMPLE = "sample"
    INDEX = "index"
    MATERIALIZE = "materialize"


class DatasetSourceStatus(StrEnum):
    CONFIGURED = "configured"
    READY = "ready"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass(frozen=True)
class DatasetSourceRef:
    provider: str
    locator: str
    access_mode: DatasetSourceAccessMode
    revision: str | None = None
    license_name: str | None = None
    provenance: dict[str, Any] | None = None
    source_metadata: dict[str, Any] | None = None

    def validate(self) -> None:
        if not self.provider.strip():
            raise ValueError("dataset source provider is required")
        if not self.locator.strip():
            raise ValueError("dataset source locator is required")
        def _contains_secret_key(value: Any) -> bool:
            if isinstance(value, dict):
                for key, nested in value.items():
                    normalized = str(key).strip().lower().replace("-", "_")
                    if normalized in {
                        "token",
                        "access_token",
                        "refresh_token",
                        "api_key",
                        "apikey",
                        "client_secret",
                        "secret",
                        "password",
                        "authorization",
                    }:
                        return True
                    if _contains_secret_key(nested):
                        return True
            elif isinstance(value, list):
                return any(_contains_secret_key(item) for item in value)
            return False

        if _contains_secret_key(self.source_metadata or {}) or _contains_secret_key(self.provenance or {}):
            raise ValueError("dataset source metadata must not contain credentials")

    def storage_payload(
        self,
        *,
        org_id: str,
        dataset_id: str,
        created_by: str | None,
    ) -> dict[str, Any]:
        self.validate()
        return {
            "org_id": org_id,
            "dataset_id": dataset_id,
            "provider": self.provider.strip().lower(),
            "locator": self.locator.strip(),
            "revision": self.revision,
            "access_mode": self.access_mode.value,
            "status": DatasetSourceStatus.CONFIGURED.value,
            "license_name": self.license_name,
            "provenance": dict(self.provenance or {}),
            "source_metadata": dict(self.source_metadata or {}),
            "created_by": created_by,
        }


def list_dataset_sources(client: Any, org_id: str, dataset_id: str) -> list[dict[str, Any]]:
    rows = (
        client.table("training_dataset_sources")
        .select(
            "id, dataset_id, provider, locator, revision, access_mode, status, "
            "license_name, provenance, source_metadata, created_at, updated_at"
        )
        .eq("org_id", org_id)
        .eq("dataset_id", dataset_id)
        .order("created_at", desc=False)
        .execute()
        .data
        or []
    )
    return [dict(row) for row in rows]


def register_dataset_source(
    client: Any,
    *,
    org_id: str,
    dataset_id: str,
    created_by: str | None,
    source: DatasetSourceRef,
) -> dict[str, Any]:
    dataset = (
        client.table("training_datasets")
        .select("id")
        .eq("org_id", org_id)
        .eq("id", dataset_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not dataset:
        raise LookupError("Dataset not found")

    payload = source.storage_payload(
        org_id=org_id,
        dataset_id=dataset_id,
        created_by=created_by,
    )
    response = (
        client.table("training_dataset_sources")
        .upsert(
            payload,
            on_conflict="org_id,dataset_id,provider,locator,access_mode",
        )
        .execute()
    )
    return dict((response.data or [payload])[0])


def get_dataset_source(
    client: Any,
    org_id: str,
    dataset_id: str,
    source_id: str,
) -> dict[str, Any] | None:
    rows = (
        client.table("training_dataset_sources")
        .select(
            "id, dataset_id, provider, locator, revision, access_mode, status, "
            "license_name, provenance, source_metadata, created_at, updated_at"
        )
        .eq("org_id", org_id)
        .eq("dataset_id", dataset_id)
        .eq("id", source_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return dict(rows[0]) if rows else None


def source_ref_from_row(row: dict[str, Any]) -> DatasetSourceRef:
    return DatasetSourceRef(
        provider=str(row.get("provider") or ""),
        locator=str(row.get("locator") or ""),
        access_mode=DatasetSourceAccessMode(str(row.get("access_mode") or "")),
        revision=(str(row.get("revision")) if row.get("revision") is not None else None),
        license_name=(
            str(row.get("license_name")) if row.get("license_name") is not None else None
        ),
        provenance=(
            dict(row.get("provenance")) if isinstance(row.get("provenance"), dict) else {}
        ),
        source_metadata=(
            dict(row.get("source_metadata"))
            if isinstance(row.get("source_metadata"), dict)
            else {}
        ),
    )
