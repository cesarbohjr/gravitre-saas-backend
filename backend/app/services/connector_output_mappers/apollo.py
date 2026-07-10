"""Apollo-specific output URL helpers for chat ExecutionResult deep links."""
from __future__ import annotations

from typing import Any

APOLLO_LIST_URL_PREFIX = "https://app.apollo.io/#/lists/"


def resolve_list_result_url(result_data: dict[str, Any] | None) -> str | None:
    """Build an Apollo UI deep link for a contact/account list (label).

    Apollo's create/list APIs do not return a web URL; the product UI uses
    ``https://app.apollo.io/#/lists/{id}`` (see e2e execution-result harness).
    """
    if not isinstance(result_data, dict):
        return None
    label = result_data.get("label") if isinstance(result_data.get("label"), dict) else result_data
    if not isinstance(label, dict):
        return None
    list_id = label.get("id") or label.get("_id") or label.get("key")
    if list_id is None:
        return None
    list_id_str = str(list_id).strip()
    if not list_id_str:
        return None
    return f"{APOLLO_LIST_URL_PREFIX}{list_id_str}"
