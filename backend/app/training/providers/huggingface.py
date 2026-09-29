"""Bounded Hugging Face Dataset Viewer adapter.

This adapter is intentionally read-only. It never requests gated access, never
downloads full dataset files, and never materializes records. Credentials, when
supplied for an already-authorized private/gated dataset, live only in process
memory and are never written to training_dataset_sources.
"""
from __future__ import annotations

from typing import Any, Callable

import httpx

from app.training.dataset_provider import (
    DatasetProviderAdapter,
    DatasetSample,
    DatasetSourceCapabilities,
    assert_source_mode_supported,
    bounded_sample_limit,
)
from app.training.dataset_sources import DatasetSourceAccessMode, DatasetSourceRef


_DATASET_SERVER = "https://datasets-server.huggingface.co"
_MAX_ROWS = 100


class HuggingFaceDatasetAdapter(DatasetProviderAdapter):
    provider = "huggingface"

    def __init__(
        self,
        *,
        token: str | None = None,
        timeout_seconds: float = 20.0,
        request_get: Callable[..., Any] | None = None,
    ) -> None:
        self._token = str(token or "").strip() or None
        self._timeout_seconds = float(timeout_seconds)
        self._request_get = request_get or httpx.get

    def capabilities(self) -> DatasetSourceCapabilities:
        return DatasetSourceCapabilities(
            reference=True,
            sample=True,
            index=False,
            materialize=False,
            max_sample_records=_MAX_ROWS,
        )

    def validate_source(self, source: DatasetSourceRef) -> None:
        source.validate()
        provider = source.provider.strip().lower().replace("-", "_")
        if provider not in {"huggingface", "hugging_face", "hf"}:
            raise ValueError("Hugging Face adapter requires provider=huggingface")
        locator = source.locator.strip()
        if "://" in locator or "?" in locator or "#" in locator or locator.startswith("/"):
            raise ValueError("Hugging Face locator must be a dataset repository id, not a URL")
        if source.access_mode == DatasetSourceAccessMode.MATERIALIZE:
            raise ValueError("Hugging Face materialization is not enabled")
        assert_source_mode_supported(source, self.capabilities())

    def _headers(self) -> dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    def _get_json(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        response = self._request_get(
            f"{_DATASET_SERVER}{path}",
            params=params,
            headers=self._headers(),
            timeout=self._timeout_seconds,
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code in {401, 403}:
            raise PermissionError(
                "Hugging Face dataset is private/gated or authorization is insufficient; "
                "Gravitre will not request or bypass gated access."
            )
        if status_code >= 400:
            raise RuntimeError(f"Hugging Face dataset viewer request failed: HTTP {status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Hugging Face dataset viewer returned an invalid payload")
        return payload

    def _resolve_config_split(self, source: DatasetSourceRef) -> tuple[str, str]:
        metadata = dict(source.source_metadata or {})
        config = str(metadata.get("config") or "").strip()
        split = str(metadata.get("split") or "").strip()
        if config and split:
            return config, split

        payload = self._get_json("/splits", params={"dataset": source.locator})
        rows = payload.get("splits")
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("Hugging Face dataset exposes no Dataset Viewer splits")
        first = rows[0] if isinstance(rows[0], dict) else {}
        config = config or str(first.get("config") or "").strip()
        split = split or str(first.get("split") or "").strip()
        if not config or not split:
            raise RuntimeError("Hugging Face Dataset Viewer did not return config/split")
        return config, split

    def sample(
        self,
        source: DatasetSourceRef,
        *,
        limit: int,
    ) -> DatasetSample:
        self.validate_source(source)
        if source.access_mode != DatasetSourceAccessMode.SAMPLE:
            raise ValueError("sample() requires dataset source access_mode=sample")

        bounded = bounded_sample_limit(
            limit,
            self.capabilities(),
            absolute_max=_MAX_ROWS,
        )
        config, split = self._resolve_config_split(source)
        payload = self._get_json(
            "/rows",
            params={
                "dataset": source.locator,
                "config": config,
                "split": split,
                "offset": 0,
                "length": bounded,
            },
        )
        raw_rows = payload.get("rows")
        if not isinstance(raw_rows, list):
            raise RuntimeError("Hugging Face Dataset Viewer returned no rows")

        records: list[dict[str, Any]] = []
        for item in raw_rows[:bounded]:
            if not isinstance(item, dict):
                continue
            row = item.get("row")
            if isinstance(row, dict):
                records.append(dict(row))

        return DatasetSample(
            rows=tuple(records),
            total_count=None,
            truncated=len(raw_rows) >= bounded,
            revision=source.revision,
            provenance={
                "provider": "huggingface",
                "dataset": source.locator,
                "config": config,
                "split": split,
                "access": "dataset_viewer_rows",
                "materialized": False,
            },
        )
