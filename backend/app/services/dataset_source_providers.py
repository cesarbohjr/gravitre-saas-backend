"""Provider-neutral adapter protocol for external dataset catalogs.

Adapters may search/describe/sample remote datasets. They must never be selected
by hardcoded UI/provider branches in core training logic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class DatasetSourceDescriptor:
    provider: str
    external_id: str
    display_name: str
    source_uri: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DatasetSourcePage:
    items: tuple[DatasetSourceDescriptor, ...]
    next_cursor: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": [item.as_dict() for item in self.items],
            "nextCursor": self.next_cursor,
        }


class DatasetSourceProvider(Protocol):
    provider_key: str

    def search(
        self,
        *,
        query: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> DatasetSourcePage: ...

    def describe(self, external_id: str) -> DatasetSourceDescriptor: ...

    def sample(
        self,
        *,
        external_id: str,
        limit: int,
    ) -> list[dict[str, Any]]: ...


_PROVIDERS: dict[str, DatasetSourceProvider] = {}


def register_dataset_source_provider(provider: DatasetSourceProvider) -> None:
    key = str(getattr(provider, "provider_key", "") or "").strip().lower()
    if not key:
        raise ValueError("dataset source provider requires provider_key")
    if key in _PROVIDERS:
        raise ValueError(f"dataset source provider already registered: {key}")
    _PROVIDERS[key] = provider


def get_dataset_source_provider(key: str) -> DatasetSourceProvider | None:
    return _PROVIDERS.get(str(key or "").strip().lower())


def list_dataset_source_provider_keys() -> list[str]:
    return sorted(_PROVIDERS)


def clear_dataset_source_providers_for_tests() -> None:
    _PROVIDERS.clear()
