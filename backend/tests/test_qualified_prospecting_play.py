from dataclasses import replace

from app.plays.catalog import get_platform_play, platform_play_templates
from app.plays.prospecting_policy import (
    ProspectDecision,
    ProspectEvidence,
    crm_write_allowed,
    prospect_admission,
)


def sample():
    return ProspectEvidence(
        company_name="Example MSP",
        company_domain="example.ca",
        company_source_url="https://example.ca/about",
        company_fit_score=90,
        contact_name="Jane Example",
        contact_role="CEO",
        identity_source_url="https://example.ca/team",
        business_email="jane@example.ca",
        email_domain="example.ca",
        verified_by="hunter",
        verified_at="2026-10-24T00:00:00Z",
        verification_status="valid",
        consent_basis="conspicuous_publication_relevant_role",
        consent_source_url="https://example.ca/team",
        consent_reviewed_by="reviewer-1",
        consent_reviewed_at="2026-10-24T00:00:00Z",
        source_reuse_authorized=True,
    )


def test_registered_in_catalog():
    play = get_platform_play("qualified-prospecting")
    assert play is not None
    assert play.name == "Find Qualified Prospects"
    assert {p.key for p in platform_play_templates()} >= {"qualified-prospecting"}


def test_valid_record_is_only_staging_eligible():
    decision, blockers = prospect_admission(sample())
    assert decision == ProspectDecision.CRM_READY
    assert not blockers
    assert not crm_write_allowed(feature_flag=False, approval_present=True, decision=decision)
    assert not crm_write_allowed(feature_flag=True, approval_present=False, decision=decision)


def test_verification_does_not_imply_consent():
    decision, blockers = prospect_admission(replace(sample(), consent_reviewed_by=""))
    assert decision == ProspectDecision.REVIEW
    assert "consent_review_missing" in blockers


def test_suppression_and_unlicensed_source_fail_closed():
    for change in ({"suppressed": True}, {"source_reuse_authorized": False}):
        decision, _ = prospect_admission(replace(sample(), **change))
        assert decision == ProspectDecision.QUARANTINE


def test_name_domain_and_validation_mismatches():
    for change in (
        {"contact_name": ""},
        {"business_email": "jane@another.ca"},
        {"verification_status": "unknown"},
        {"company_fit_score": 20},
    ):
        decision, blockers = prospect_admission(replace(sample(), **change))
        assert decision != ProspectDecision.CRM_READY
        assert blockers
