"""Compliance service tests (STA-81 / STA-82)."""
from app.services.compliance_service import build_soc2_evidence_bundle, redact_text


def test_redact_text_strict_hashes_email():
    result = redact_text("Contact user@example.com today", mode="strict")
    assert "user@example.com" not in result
    assert result.startswith("Contact ")


def test_soc2_bundle_redacts_metadata():
    bundle = build_soc2_evidence_bundle(
        org_id="org-1",
        audit_logs=[{"action": "tool.invoke.completed", "details": {"email": "a@b.com"}}],
        tool_events=[],
        connector_events=[],
        admin_events=[],
    )
    assert bundle["summary"]["auditLogCount"] == 1
    assert "a@b.com" not in str(bundle)
