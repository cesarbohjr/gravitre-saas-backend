"""Tests for Apollo list deep-link resolution."""
from __future__ import annotations

from app.services.connector_output_mappers.apollo import resolve_list_result_url


def test_resolve_list_result_url_from_label_payload():
    assert (
        resolve_list_result_url({"label": {"id": "6a4d6a98461b000010c5ae7b", "name": "MSP Prospects"}})
        == "https://app.apollo.io/#/lists/6a4d6a98461b000010c5ae7b"
    )


def test_resolve_list_result_url_from_flat_label():
    assert resolve_list_result_url({"id": "abc", "name": "X"}) == "https://app.apollo.io/#/lists/abc"


def test_resolve_list_result_url_none_without_id():
    assert resolve_list_result_url({"label": {"name": "MSP Prospects"}}) is None
    assert resolve_list_result_url({}) is None
    assert resolve_list_result_url(None) is None
