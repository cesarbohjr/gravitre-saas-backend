from unittest.mock import MagicMock
import pytest
from app.plays.prospecting_reviews import list_reviews, evaluate_and_record
from app.plays.prospecting_policy import ProspectEvidence

def evidence():
    return ProspectEvidence(
        company_name="Sample", company_domain="sample.ca", company_source_url="https://sample.ca",
        company_fit_score=90,contact_name="Person One",contact_role="CEO",
        identity_source_url="https://sample.ca/team",business_email="one@sample.ca",
        email_domain="sample.ca",verified_by="hunter",verified_at="2026-10-24",
        consent_basis="",consent_source_url="",consent_reviewed_by="",consent_reviewed_at="",
        source_reuse_authorized=True,verification_status="valid")

def test_review_requires_org():
    with pytest.raises(ValueError):
        list_reviews(MagicMock(),"")

def test_review_not_found_blocks_mutation():
    client=MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
    with pytest.raises(LookupError):
        evaluate_and_record(client,"org-a","contact-b",evidence(),reviewer_id="human")
    client.table.return_value.update.assert_not_called()
