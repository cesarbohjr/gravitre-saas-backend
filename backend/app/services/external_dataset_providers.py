"""Provider-neutral external dataset discovery for Model Studio.

External datasets are reference sources, not training_datasets. Discovery and
inspection are read-only. Materialization into Gravitre storage must be an
explicit later action with purpose/governance checks.

The first adapter is Hugging Face because it exposes a public metadata API.
No provider-specific behavior leaks into Model Studio callers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Any, Protocol
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class DatasetProviderDescriptor:
    id: str
    label: str
    capabilities: tuple[str, ...]
    auth: str
    materialization: str
    notes: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExternalDatasetSummary:
    provider: str
    dataset_id: str
    name: str
    author: str | None
    description: str | None
    tags: tuple[str, ...]
    downloads: int | None
    likes: int | None
    private: bool
    gated: bool
    reference_url: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExternalDatasetProvider(Protocol):
    descriptor: DatasetProviderDescriptor

    def search(self, query: str, *, limit: int = 20) -> list[ExternalDatasetSummary]: ...

    def inspect(self, dataset_id: str) -> dict[str, Any]: ...


class HuggingFaceDatasetProvider:
    BASE = "https://huggingface.co"
    descriptor = DatasetProviderDescriptor(
        id="huggingface",
        label="Hugging Face",
        capabilities=("search", "inspect", "reference"),
        auth="optional_token",
        materialization="explicit_only",
        notes=(
            "Public metadata discovery only. Gated/private datasets are never bypassed "
            "and no dataset is automatically downloaded."
        ),
    )

    def _headers(self) -> dict[str, str]:
        token = str(os.environ.get("HUGGINGFACE_TOKEN") or "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def search(self, query: str, *, limit: int = 20) -> list[ExternalDatasetSummary]:
        q = str(query or "").strip()
        if not q:
            return []
        with httpx.Client(base_url=self.BASE, headers=self._headers(), timeout=20.0) as client:
            response = client.get(
                "/api/datasets",
                params={"search": q, "limit": max(1, min(int(limit), 50)), "full": "true"},
            )
            response.raise_for_status()
            payload = response.json()
        rows = payload if isinstance(payload, list) else []
        return [self._summary(row) for row in rows if isinstance(row, dict)]

    def inspect(self, dataset_id: str) -> dict[str, Any]:
        did = str(dataset_id or "").strip().strip("/")
        if not did:
            raise ValueError("dataset_id is required")
        lowered = did.lower()
        if "://" in did or "?" in did or "#" in did or any(
            marker in lowered
            for marker in ("token=", "api_key=", "apikey=", "client_secret=", "authorization=")
        ):
            raise ValueError("dataset_id must be a provider repository id without credentials or URL parameters")
        encoded = quote(did, safe="/")
        with httpx.Client(base_url=self.BASE, headers=self._headers(), timeout=20.0) as client:
            response = client.get(f"/api/datasets/{encoded}")
            if response.status_code in {401, 403}:
                raise PermissionError("Dataset is private or gated and requires authorized provider access")
            response.raise_for_status()
            row = response.json()
        if not isinstance(row, dict):
            raise RuntimeError("Provider returned an invalid dataset payload")
        summary = self._summary(row).as_dict()
        siblings = []
        for item in row.get("siblings") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("rfilename") or "").strip()
            if name:
                siblings.append({"path": name})
        return {
            **summary,
            "cardData": row.get("cardData") if isinstance(row.get("cardData"), dict) else {},
            "files": siblings[:500],
            "fileCount": len(siblings),
            "materialized": False,
            "materializationAllowed": not bool(row.get("private")) and not bool(row.get("gated")),
            "truthRule": (
                "Inspection is metadata-only. Gravitre does not download or treat an "
                "external dataset as training/runtime data until an explicit materialization step."
            ),
        }

    def _summary(self, row: dict[str, Any]) -> ExternalDatasetSummary:
        did = str(row.get("id") or row.get("name") or "").strip()
        author = str(row.get("author") or "").strip() or (did.split("/", 1)[0] if "/" in did else None)
        card = row.get("cardData") if isinstance(row.get("cardData"), dict) else {}
        description = str(row.get("description") or card.get("pretty_name") or "").strip() or None
        tags = tuple(str(tag) for tag in (row.get("tags") or []) if isinstance(tag, str))
        gated_raw = row.get("gated")
        gated = bool(gated_raw) and str(gated_raw).lower() not in {"false", "none", ""}
        return ExternalDatasetSummary(
            provider="huggingface",
            dataset_id=did,
            name=did.split("/", 1)[-1] if did else "dataset",
            author=author,
            description=description,
            tags=tags[:40],
            downloads=int(row["downloads"]) if isinstance(row.get("downloads"), int) else None,
            likes=int(row["likes"]) if isinstance(row.get("likes"), int) else None,
            private=bool(row.get("private")),
            gated=gated,
            reference_url=f"{self.BASE}/datasets/{did}",
        )


class KaggleDatasetProvider:
    BASE = "https://www.kaggle.com"
    descriptor = DatasetProviderDescriptor(
        id="kaggle",
        label="Kaggle",
        capabilities=("search", "inspect", "reference"),
        auth="optional_token",
        materialization="explicit_only",
        notes=(
            "Public Kaggle dataset discovery is free. Inspection is metadata-only; "
            "restricted/private datasets are never bypassed or automatically downloaded."
        ),
    )

    def _headers(self) -> dict[str, str]:
        token = str(os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_TOKEN") or "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}

    @staticmethod
    def _dataset_id(value: str) -> str:
        did = str(value or "").strip().strip("/")
        lowered = did.lower()
        if (
            not did
            or did.count("/") != 1
            or "://" in did
            or "?" in did
            or "#" in did
            or any(marker in lowered for marker in ("token=", "api_key=", "apikey=", "authorization="))
        ):
            raise ValueError("dataset_id must be a Kaggle owner/dataset handle without credentials or URL parameters")
        return did

    def search(self, query: str, *, limit: int = 20) -> list[ExternalDatasetSummary]:
        q = str(query or "").strip()
        if not q:
            return []
        requested = max(1, min(int(limit), 50))
        with httpx.Client(base_url=self.BASE, headers=self._headers(), timeout=20.0) as client:
            response = client.get(
                "/api/v1/datasets/list",
                params={"search": q, "page": 1, "sortBy": "hottest"},
            )
            response.raise_for_status()
            payload = response.json()
        rows = payload if isinstance(payload, list) else []
        return [self._summary(row) for row in rows[:requested] if isinstance(row, dict)]

    def inspect(self, dataset_id: str) -> dict[str, Any]:
        did = self._dataset_id(dataset_id)
        encoded = quote(did, safe="/")
        with httpx.Client(base_url=self.BASE, headers=self._headers(), timeout=20.0) as client:
            response = client.get(f"/api/v1/datasets/view/{encoded}")
            if response.status_code in {401, 403}:
                raise PermissionError("Dataset requires authorized Kaggle access")
            response.raise_for_status()
            row = response.json()
        if not isinstance(row, dict):
            raise RuntimeError("Kaggle returned an invalid dataset payload")
        summary = self._summary({**row, "ref": did}).as_dict()
        files = []
        for item in row.get("datasetFiles") or row.get("files") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("ref") or "").strip()
            if name:
                files.append({"path": name, "size": item.get("totalBytes") or item.get("size")})
        return {
            **summary,
            "title": row.get("title"),
            "subtitle": row.get("subtitle"),
            "license": row.get("licenseName"),
            "totalBytes": row.get("totalBytes"),
            "lastUpdated": row.get("lastUpdated"),
            "files": files[:500],
            "fileCount": len(files),
            "materialized": False,
            "materializationAllowed": not bool(row.get("isPrivate")),
            "truthRule": (
                "Inspection is metadata-only. Gravitre does not download or treat a Kaggle "
                "dataset as training/runtime data until an explicit materialization step."
            ),
        }

    def _summary(self, row: dict[str, Any]) -> ExternalDatasetSummary:
        did = str(row.get("ref") or row.get("id") or "").strip()
        author = did.split("/", 1)[0] if "/" in did else None
        description = str(row.get("subtitle") or row.get("description") or row.get("title") or "").strip() or None
        tags_raw = row.get("tags") or []
        tags = tuple(
            str(tag.get("name") if isinstance(tag, dict) else tag)
            for tag in tags_raw
            if isinstance(tag, (str, dict))
        )
        return ExternalDatasetSummary(
            provider="kaggle",
            dataset_id=did,
            name=str(row.get("title") or (did.split("/", 1)[-1] if did else "dataset")),
            author=author,
            description=description,
            tags=tags[:40],
            downloads=int(row["downloadCount"]) if isinstance(row.get("downloadCount"), int) else None,
            likes=int(row["voteCount"]) if isinstance(row.get("voteCount"), int) else None,
            private=bool(row.get("isPrivate")),
            gated=False,
            reference_url=str(row.get("url") or f"{self.BASE}/datasets/{did}"),
        )


_PROVIDERS: dict[str, ExternalDatasetProvider] = {
    "huggingface": HuggingFaceDatasetProvider(),
    "kaggle": KaggleDatasetProvider(),
}


def list_external_dataset_providers() -> list[dict[str, Any]]:
    return [provider.descriptor.as_dict() for provider in _PROVIDERS.values()]


def get_external_dataset_provider(provider_id: str) -> ExternalDatasetProvider:
    key = str(provider_id or "").strip().lower()
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise LookupError(f"Unsupported dataset provider: {provider_id}")
    return provider


def search_external_datasets(
    provider_id: str,
    query: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    provider = get_external_dataset_provider(provider_id)
    return [row.as_dict() for row in provider.search(query, limit=limit)]


def inspect_external_dataset(provider_id: str, dataset_id: str) -> dict[str, Any]:
    return get_external_dataset_provider(provider_id).inspect(dataset_id)
