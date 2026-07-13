"""Phase 1.5 — ONE normalize_source_result dispatcher.

Vendor-specific mappers register into this module; they do not implement parallel
normalize stacks.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

from app.intelligence_packs.shared.schemas import SourceResult


class NormalizedExternalRecord(TypedDict, total=False):
    vendor: str
    entity_type: str
    external_id: str
    title: str
    payload: dict[str, Any]
    provenance: dict[str, Any]
    signal_hints: dict[str, Any]


MapperFn = Callable[[SourceResult], list[NormalizedExternalRecord]]

_MAPPERS: dict[str, MapperFn] = {}


def register_mapper(vendor: str, mapper: MapperFn) -> None:
    """Plug a vendor mapper into the shared dispatcher (idempotent by vendor)."""
    key = str(vendor or "").strip().lower()
    if not key:
        raise ValueError("vendor required")
    _MAPPERS[key] = mapper


def registered_mappers() -> frozenset[str]:
    return frozenset(_MAPPERS.keys())


def normalize_source_result(vendor: str, raw: SourceResult) -> list[NormalizedExternalRecord]:
    """Dispatch to the registered mapper for vendor. Raises if unregistered or not ok."""
    key = str(vendor or raw.get("vendor") or "").strip().lower()
    mapper = _MAPPERS.get(key)
    if mapper is None:
        raise KeyError(f"No mapper registered for vendor={key!r}; register via register_mapper")
    if not raw.get("ok"):
        return []
    records = mapper(raw)
    out: list[NormalizedExternalRecord] = []
    for rec in records or []:
        item = dict(rec)
        item.setdefault("vendor", key)
        item.setdefault("payload", {})
        item.setdefault("provenance", dict(raw.get("provenance") or {}))
        out.append(item)  # type: ignore[arg-type]
    return out
