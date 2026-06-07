"""Custom domain verification tests."""
from unittest.mock import patch

from app.services.domain_verification_service import (
    build_verification_instructions,
    verification_txt_host,
    verify_custom_domain,
)


def test_verification_txt_host():
    assert verification_txt_host("app.example.com") == "_gravitre.app.example.com"


def test_build_verification_instructions():
    payload = build_verification_instructions(
        domain="app.example.com",
        token="abc123",
        cname_target="cname.gravitre.app",
    )
    assert payload["cnameRecord"]["value"] == "cname.gravitre.app"
    assert "gravitre-verify=abc123" in payload["txtRecord"]["value"]


def test_verify_custom_domain_accepts_txt_match():
    with patch(
        "app.services.domain_verification_service._resolve_cname",
        return_value=[],
    ), patch(
        "app.services.domain_verification_service._resolve_txt",
        return_value=["gravitre-verify=token-1"],
    ):
        result = verify_custom_domain(
            domain="app.example.com",
            token="token-1",
            cname_target="cname.gravitre.app",
        )
    assert result["verified"] is True
    assert result["method"] == "txt"
