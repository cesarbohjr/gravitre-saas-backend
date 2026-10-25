"""Outbound outreach draft handoff for Qualified Prospecting Play.

No transport, network side effects or email sending. The caller must execute
the canonical PendingAction-approved email capability separately.
"""
from __future__ import annotations
from dataclasses import dataclass
from app.plays.prospecting_policy import ProspectDecision

@dataclass(frozen=True)
class OutreachDraft:
    recipient_email: str
    subject: str
    body: str
    sender_business_name: str
    sender_postal_address: str
    contact_method: str
    unsubscribe_url: str
    consent_evidence_id: str

def prepare_outreach_draft(
    draft: OutreachDraft, *, decision: ProspectDecision,
    suppressed: bool, source_prohibition: bool,
) -> dict[str,object]:
    if decision != ProspectDecision.CRM_READY or suppressed or source_prohibition:
        raise PermissionError("Prospect not eligible for outreach preparation")
    if not all((
        draft.recipient_email,draft.subject,draft.body,draft.sender_business_name,
        draft.sender_postal_address,draft.contact_method,draft.unsubscribe_url,
        draft.consent_evidence_id,
    )):
        raise ValueError("Sender identity, consent reference and unsubscribe details are mandatory")
    if not draft.unsubscribe_url.startswith("https://"):
        raise ValueError("Unsubscribe must use HTTPS")
    if "@" not in draft.recipient_email:
        raise ValueError("Recipient must be a business email address")
    return {
        "type":"draft",
        "to":draft.recipient_email,
        "subject":draft.subject,
        "body":draft.body,
        "sender_identity":draft.sender_business_name,
        "postal_address":draft.sender_postal_address,
        "contact_method":draft.contact_method,
        "unsubscribe_url":draft.unsubscribe_url,
        "consent_evidence_id":draft.consent_evidence_id,
        "transport":"existing_canonical_email_connector",
        "pending_action_required":True,
        "sent":False,
    }
