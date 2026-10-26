"""Deterministic HubSpot-to-outreach handoff with zero implicit sends.

An approved prospect must be matched to an org-owned HubSpot contact and a
separately authorized outbound campaign. Preparation is pure; execution is
reserved for the canonical PendingAction write gate.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class OutreachHandoff:
    org_id: str
    prospect_contact_id: str
    hubspot_contact_id: str
    sending_provider: str
    sending_connector_id: str
    campaign_id: str
    recipient_email: str
    consent_evidence_id: str
    consent_validated: bool
    suppression_checked: bool
    suppressed: bool
    human_reviewed: bool
    campaign_approved: bool
    approval_action_id: str
    draft_subject: str
    draft_body: str

SUPPORTED_PROVIDERS=frozenset({"smartlead","instantly","quickmail","hunter","snov"})

def prepare_hubspot_outreach_handoff(handoff: OutreachHandoff) -> dict[str,Any]:
    """Validate a proposed cross-provider handoff. No network side effects."""
    if handoff.sending_provider not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported outbound provider")
    required=(handoff.org_id,handoff.prospect_contact_id,handoff.hubspot_contact_id,
      handoff.sending_connector_id,handoff.campaign_id,handoff.recipient_email,
      handoff.consent_evidence_id,handoff.approval_action_id,
      handoff.draft_subject,handoff.draft_body)
    if not all(str(x).strip() for x in required):
        raise ValueError("Incomplete HubSpot outreach handoff")
    if not (handoff.consent_validated and handoff.suppression_checked
            and not handoff.suppressed and handoff.human_reviewed
            and handoff.campaign_approved):
        raise PermissionError("Consent, suppression, human and campaign approval required")
    if "@" not in handoff.recipient_email:
        raise ValueError("Invalid recipient email")
    return {"state":"prepared_pending_action_verification",
      "org_id":handoff.org_id,
      "hubspot_contact_id":handoff.hubspot_contact_id,
      "prospect_contact_id":handoff.prospect_contact_id,
      "provider":handoff.sending_provider,"connector_id":handoff.sending_connector_id,
      "campaign_id":handoff.campaign_id,"approval_action_id":handoff.approval_action_id,
      "recipient_email":handoff.recipient_email,
      "draft_subject":handoff.draft_subject,"draft_body":handoff.draft_body,
      "consent_evidence_id":handoff.consent_evidence_id,
      "pending_action_verified":False,"enrolled":False,"email_sent":False}

def outbound_execution_allowed(*, pending_action_verified:bool,
    live_provider_certified:bool, tenant_scope_verified:bool,
    suppression_rechecked:bool, sender_domain_ready:bool) -> bool:
    return all((pending_action_verified,live_provider_certified,
                tenant_scope_verified,suppression_rechecked,sender_domain_ready))
