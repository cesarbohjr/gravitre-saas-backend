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
        lowered = " ".join(
            [
                self.locator.lower(),
                str(self.source_metadata or {}).lower(),
                str(self.provenance or {}).lower(),
            ]
        )
        for marker in ("access_token", "refresh_token", "api_key", "client_secret", "password"):
            if marker in lowered:
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
