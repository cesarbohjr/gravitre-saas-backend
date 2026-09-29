"""Provider-neutral external dataset adapter contract.

Named providers implement this protocol later. The default contract makes
bounded reference/sample/index access explicit and keeps materialization opt-in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.training.dataset_sources import DatasetSourceAccessMode, DatasetSourceRef


@dataclass(frozen=True)
class DatasetSourceCapabilities:
    reference: bool = True
    sample: bool = False
    index: bool = False
    materialize: bool = False
    max_sample_records: int | None = None

    def supports(self, mode: DatasetSourceAccessMode) -> bool:
        return {
            DatasetSourceAccessMode.REFERENCE: self.reference,
            DatasetSourceAccessMode.SAMPLE: self.sample,
            DatasetSourceAccessMode.INDEX: self.index,
            DatasetSourceAccessMode.MATERIALIZE: self.materialize,
        }[mode]


@dataclass(frozen=True)
class DatasetSample:
    rows: tuple[dict[str, Any], ...]
    total_count: int | None = None
    truncated: bool = False
    revision: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DatasetProviderAdapter(Protocol):
    """Contract for future external provider implementations.

    Credentials are supplied out-of-band by the adapter's own secure auth
    mechanism. They are never persisted in training_dataset_sources.
    """

    provider: str

    def capabilities(self) -> DatasetSourceCapabilities: ...

    def validate_source(self, source: DatasetSourceRef) -> None: ...

    def sample(
        self,
        source: DatasetSourceRef,
        *,
        limit: int,
    ) -> DatasetSample: ...


def bounded_sample_limit(
    requested: int,
    capabilities: DatasetSourceCapabilities,
    *,
    absolute_max: int = 500,
) -> int:
    """Clamp all provider sampling before an adapter is called."""
    if requested < 1:
        raise ValueError("sample limit must be at least 1")
    limit = min(int(requested), int(absolute_max))
    if capabilities.max_sample_records is not None:
        limit = min(limit, int(capabilities.max_sample_records))
    return max(1, limit)


def assert_source_mode_supported(
    source: DatasetSourceRef,
    capabilities: DatasetSourceCapabilities,
) -> None:
    if not capabilities.supports(source.access_mode):
        raise ValueError(
            f"provider does not support dataset access mode: {source.access_mode.value}"
        )
