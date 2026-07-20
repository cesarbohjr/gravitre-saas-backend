"""Typed capability-fallback responses for intelligence sources."""
from __future__ import annotations

from typing import Any, TypedDict

from app.services.confidence_honesty import CONFIDENCE_SOURCE_HEURISTIC, label_confidence


class SourceResult(TypedDict, total=False):
    ok: bool
    vendor: str
    auth_mode: str
    data: list[dict[str, Any]] | dict[str, Any] | None
    error_code: str | None
    message: str | None
    provenance: dict[str, Any]


def unavailable(vendor: str, *, auth_mode: str, error_code: str, message: str) -> SourceResult:
    return {
        "ok": False,
        "vendor": vendor,
        "auth_mode": auth_mode,
        "data": None,
        "error_code": error_code,
        "message": message,
        "provenance": {"source": vendor, "available": False},
    }


def ok_result(
    vendor: str,
    *,
    auth_mode: str,
    data: list[dict[str, Any]] | dict[str, Any],
    provenance: dict[str, Any] | None = None,
) -> SourceResult:
    return {
        "ok": True,
        "vendor": vendor,
        "auth_mode": auth_mode,
        "data": data,
        "error_code": None,
        "message": None,
        "provenance": provenance
        or {
            "source": vendor,
            "available": True,
            **label_confidence(0.85, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
        },
    }
