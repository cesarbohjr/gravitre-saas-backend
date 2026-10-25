from dataclasses import replace
import pytest
from app.plays.prospecting_hubspot_outreach import OutreachHandoff,prepare_hubspot_outreach_handoff,outbound_execution_allowed

def valid_handoff():
    return OutreachHandoff(org_id="org-a",prospect_contact_id="prospect-1",
      hubspot_contact_id="1001",sending_provider="smartlead",sending_connector_id="c-1",
      campaign_id="campaign-2",recipient_email="approved@example.ca",
      consent_evidence_id="consent-1",consent_validated=True,
      suppression_checked=True,suppressed=False,human_reviewed=True,
      campaign_approved=True,approval_action_id="approval-5",
      draft_subject="Relevant discussion",draft_body="Hello - approved content")

def test_hubspot_to_smartlead_handoff_never_implicitly_sends():
    result=prepare_hubspot_outreach_handoff(valid_handoff())
    assert result["hubspot_contact_id"]=="1001"
    assert result["provider"]=="smartlead"
    assert result["enrolled"] is False and result["email_sent"] is False
    assert result["pending_action_verified"] is False

@pytest.mark.parametrize("field,value", [
    ("consent_validated",False),("suppression_checked",False),
    ("suppressed",True),("human_reviewed",False),("campaign_approved",False),
])
def test_each_compliance_gate_fails_closed(field,value):
    with pytest.raises(PermissionError):
        prepare_hubspot_outreach_handoff(replace(valid_handoff(),**{field:value}))

def test_cross_provider_execution_requires_all_five_runtime_proofs():
    args=dict(pending_action_verified=True,live_provider_certified=True,
      tenant_scope_verified=True,suppression_rechecked=True,sender_domain_ready=True)
    assert outbound_execution_allowed(**args)
    for field in args:
        assert not outbound_execution_allowed(**(args|{field:False}))
