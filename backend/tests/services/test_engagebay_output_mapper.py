"""EngageBay output mapper unit tests."""
from __future__ import annotations

from app.services.connector_output_mappers.engagebay import (
    extract_contact_id,
    resolve_contact_result_url,
    summarize_contact_write,
)


def test_summarize_create_includes_name_and_id():
    summary = summarize_contact_write(
        action="engagebay.contacts.create",
        result_data={"id": "99", "email": "a@b.com", "first_name": "Ada"},
        args={"email": "a@b.com"},
    )
    assert "Created EngageBay contact" in summary
    assert "Ada" in summary
    assert "99" in summary


def test_summarize_update_uses_args_fallback_id():
    summary = summarize_contact_write(
        action="engagebay.contacts.update",
        result_data={"email": "a@b.com"},
        args={"contact_id": "55", "email": "a@b.com"},
    )
    assert "Updated EngageBay contact" in summary
    assert "55" in summary


def test_extract_contact_id_from_nested_contact():
    assert extract_contact_id({"contact": {"id": "nested-1"}}) == "nested-1"


def test_resolve_contact_result_url_none_without_vendor_link():
    assert resolve_contact_result_url({"id": "1", "email": "a@b.com"}) is None


def test_resolve_contact_result_url_when_api_provides_link():
    assert (
        resolve_contact_result_url({"url": "https://app.engagebay.com/list#id=1"})
        == "https://app.engagebay.com/list#id=1"
    )
