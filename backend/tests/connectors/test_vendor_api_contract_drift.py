"""CI — stored ActionSpec must match pinned vendor HTTP contracts."""
from __future__ import annotations

import httpx
import pytest

from app.connectors.action_catalog.vendor_api_contracts import (
    APOLLO_LISTS_CREATE_CONTRACT,
    VENDOR_HTTP_CONTRACTS,
    drift_report,
)


def test_apollo_lists_create_catalog_matches_pinned_vendor_contract():
    issues = drift_report("apollo.lists.create")
    assert not issues, issues


def test_apollo_openapi_labels_post_still_matches_pinned_contract():
    """Live fetch — Apollo docs OpenAPI must not drift from our pinned snapshot."""
    url = "https://docs.apollo.io/openapi/apollo-rest-api.json"
    try:
        spec = httpx.get(url, timeout=30.0).json()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Apollo OpenAPI unreachable: {exc}")
    post = (spec.get("paths") or {}).get("/labels", {}).get("post") or {}
    schema = (
        post.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    required = tuple(sorted(schema.get("required") or []))
    props = set((schema.get("properties") or {}).keys())
    assert required == tuple(sorted(APOLLO_LISTS_CREATE_CONTRACT.required_body_fields))
    for field in APOLLO_LISTS_CREATE_CONTRACT.required_body_fields:
        assert field in props
    for field in APOLLO_LISTS_CREATE_CONTRACT.optional_body_fields:
        assert field in props


def test_every_pinned_contract_has_drift_report_entry():
    for action_key in VENDOR_HTTP_CONTRACTS:
        assert isinstance(drift_report(action_key), list)
