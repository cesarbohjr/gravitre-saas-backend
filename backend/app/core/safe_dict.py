"""Safe normalization for stored dictionary-like payloads."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def safe_normalize_stored_dict(value: Any, *, key: str | None = None) -> dict[str, Any]:
    """Return a dictionary from stored payloads without raising.

    Behavior:
    - If ``value`` is a dict (or mapping), return a shallow dict copy.
    - If ``value`` is a JSON string containing an object, parse and return it.
    - Otherwise, return ``{}``.

    When ``key`` is provided, the function first normalizes ``value`` as a
    container dict, looks up ``container[key]``, and then normalizes that value.
    This safely handles legacy rows where the container itself may be malformed.
    """

    if key is not None:
        container = safe_normalize_stored_dict(value)
        return safe_normalize_stored_dict(container.get(key))

    if isinstance(value, Mapping):
        return dict(value)

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:  # noqa: BLE001
            return {}
        if isinstance(parsed, Mapping):
            return dict(parsed)
        return {}

    return {}
